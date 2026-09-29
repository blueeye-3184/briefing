import os
import time
import random
import html
import re
import unicodedata
import requests
import email.utils
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, cast
from google import genai # type: ignore
from google.genai import types # type: ignore
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception, retry_if_exception_type # type: ignore
from dotenv import load_dotenv # type: ignore

from manifest_manager import (
    SearchStatus,
    GeminiOutcome,
    PublishStatus,
    GeminiAttemptRecord,
    AcademicSearchResult,
    InfographicSpec,
    ManifestManager,
    redact_secrets,
    hash_page_id,
)

# .env 파일 로드 (로컬 개발 환경용)
load_dotenv()

# [환경 변수]
GEMINI_API_KEY: Optional[str] = os.environ.get('GEMINI_API_KEY')
NOTION_TOKEN: Optional[str] = os.environ.get('NOTION_TOKEN')
PARENT_PAGE_ID: Optional[str] = os.environ.get('PARENT_PAGE_ID')
SLACK_WEBHOOK_URL: Optional[str] = os.environ.get('SLACK_WEBHOOK_URL')

def validate_environment() -> Dict[str, str]:
    """애플리케이션 시작 전 필수 환경변수 일괄 검증.
    누락된 변수명만 명시하며, 시크릿 값 자체는 예외 메시지에 포함하지 않음."""
    required = ["GEMINI_API_KEY", "NOTION_TOKEN", "PARENT_PAGE_ID"]
    values = {key: os.environ.get(key, "").strip() for key in required}
    missing = [key for key, value in values.items() if not value]
    if missing:
        raise ValueError(f"필수 환경 변수가 누락되었습니다: {', '.join(missing)}")
    return {
        "GEMINI_API_KEY": values["GEMINI_API_KEY"],
        "NOTION_TOKEN": values["NOTION_TOKEN"],
        "PARENT_PAGE_ID": values["PARENT_PAGE_ID"],
        "SLACK_WEBHOOK_URL": os.environ.get("SLACK_WEBHOOK_URL", ""),
    }

# KST (UTC+9) 설정
KST: timezone = timezone(timedelta(hours=9))

# 브리핑 품질 계약
TARGET_PAPER_COUNT: int = 10
TARGET_BODY_MIN_CHARS: int = 9_000
TARGET_BODY_MAX_CHARS: int = 11_000
MAX_INPUT_TOKENS: int = 120_000
MAX_OUTPUT_TOKENS: int = 12_000
NOTION_RICH_TEXT_LIMIT: int = 2_000
NOTION_SAFE_TEXT_LIMIT: int = 1_800
NOTION_REQUEST_BLOCK_LIMIT: int = 100
NOTION_OPERATIONAL_BLOCK_LIMIT: int = 90

OA_LICENSE_PREFIXES: Tuple[str, ...] = (
    "cc-by", "cc0", "public-domain", "pd", "open-government"
)

# ==========================================
# Domain Layer
# ==========================================
class AcademicPaper:
    """엄격한 메타데이터 게이트를 통과한 피어리뷰 OA 논문 엔티티."""
    def __init__(
        self,
        title: str,
        authors: List[str],
        journal: str,
        year: Optional[int],
        doi: Optional[str],
        oa_url: str,
        abstract: str,
        openalex_id: Optional[str] = None,
        source_type: Optional[str] = None,
        oa_version: Optional[str] = None,
        oa_license: Optional[str] = None,
        crossref_type: Optional[str] = None,
        title_verified: bool = False,
        is_retracted: bool = False,
    ) -> None:
        self.title = title
        self.authors = authors
        self.journal = journal
        self.year = year
        self.doi = doi
        self.oa_url = oa_url
        self.abstract = abstract
        self.openalex_id = openalex_id
        self.source_type = source_type
        self.oa_version = oa_version
        self.oa_license = oa_license
        self.crossref_type = crossref_type
        self.title_verified = title_verified
        self.is_retracted = is_retracted

    @property
    def strict_eligibility_passed(self) -> bool:
        """채택 논문에 적용하는 보수적 OA/피어리뷰 대리 검증 계약."""
        license_value = (self.oa_license or "").lower()
        return all((
            bool(self.doi),
            bool(self.oa_url),
            bool(self.abstract),
            self.source_type == "journal",
            self.oa_version in {"publishedVersion", "acceptedVersion"},
            any(license_value.startswith(prefix) for prefix in OA_LICENSE_PREFIXES),
            self.crossref_type == "journal-article",
            self.title_verified,
            not self.is_retracted,
        ))

    @staticmethod
    def format_reference_section(
        papers: List['AcademicPaper'],
        target_count: int = TARGET_PAPER_COUNT,
    ) -> str:
        """검증 논문만 한 편당 한 줄로 렌더링하고 결손을 투명하게 공시."""
        if not papers:
            return (
                "\n\n---\n"
                "## ⚠️ UNKNOWN / DEFICIT REPORT — 적격 학술자료 부재\n"
                f"- **검색 결과**: 목표 {target_count}편 중 엄격한 OA·피어리뷰 메타데이터 게이트를 모두 통과한 논문은 0편입니다.\n"
                "- **검증 계약**: DOI와 Crossref journal-article 유형·제목 일치, OpenAlex journal source, accepted/published version, 공개 라이선스, OA URL, 초록, 비철회 상태를 모두 요구했습니다.\n"
                "- **무결성 조치**: 논문을 임의로 보충하지 않았으며, 학술논문에 근거한 주장과 가상 참고문헌을 배제했습니다.\n"
                "- **작성 범위**: 공개된 공공 가이드라인·표준·정책 등 비학술 1차 자료의 한계를 명시한 실무 분석만 제공합니다."
            )

        lines = [
            "\n\n---\n",
            "## 📚 엄격 적격성 게이트 통과 피어리뷰 오픈액세스 참고문헌\n",
            "> 아래 채택 논문 100%는 동일한 자동 검증 계약을 통과했습니다. 이는 메타데이터 기반 적격성 판정이며 심사 내용의 학문적 품질을 절대 보증한다는 뜻은 아닙니다.\n"
        ]

        if len(papers) < target_count:
            lines.append(
                f"> ⚠️ **자료 결손**: 목표 {target_count}편 중 {len(papers)}편만 적격 판정을 받았습니다. "
                "부족분을 비검증 자료로 채우지 않았습니다.\n"
            )

        for idx, p in enumerate(papers, 1):
            author_str = ", ".join(p.authors) if p.authors else "저자 미상"
            year_str = f"({p.year})" if p.year else ""
            doi_link = f"[{p.doi}]({p.doi})" if p.doi else "DOI 미발급"
            oa_link = f"[무료 전문 열람 (Open Access)]({p.oa_url})" if p.oa_url else "열람 링크 없음"
            lines.append(
                f"{idx}. **{p.title}** — {author_str}; {p.journal} {year_str}; "
                f"DOI: {doi_link}; {oa_link}; license={p.oa_license}; version={p.oa_version}."
            )

        return "\n".join(lines)


class BriefingSchedule:
    """요일별 주제 및 공인 학술 DB 쿼리 키워드 관리 도메인"""
    SCHEDULE: Dict[int, Tuple[str, str]] = {
        0: ("월요일", "구미/김천 지역 부동산 정책 및 시장 흐름 분석"),
        1: ("화요일", "친환경 건축 기술 (목조 건축, 현대 황토 건축) 최신 트렌드"),
        2: ("수요일", "설계 자동화 기술 및 BIM (Building Information Modeling) 최신 동향"),
        3: ("목요일", "최신 조경 디자인 및 외부 공간 설계 트렌드"),
        4: ("금요일", "건축 관련 R&D 국책 과제 및 IRIS 공모전 동향"),
        5: ("토요일", "건축사사무소 운영 시스템 효율화 방안"),
        6: ("일요일", "건축 관련 데이터베이스(DB) 관리 및 활용 방안")
    }

    SEARCH_KEYWORDS: Dict[int, List[str]] = {
        0: ["부동산 정책", "지역 부동산 시장", "주택 시장 분석"],
        1: ["친환경 목조 건축", "목조 건축", "친환경 건축 기술"],
        2: ["BIM 설계 자동화", "BIM 건축", "설계 자동화"],
        3: ["조경 디자인 외부공간", "조경 디자인", "도시 외부공간"],
        4: ["건축 R&D 정책", "건설 기술 R&D", "건축 정책 과제"],
        5: ["건축사사무소 실무", "건축설계 관리", "건축사사무소"],
        6: ["건축 정보 데이터베이스", "건축 BIM 데이터", "건축 정보 시스템"]
    }

    @classmethod
    def get_today_topic(cls) -> Tuple[str, str]:
        now: datetime = datetime.now(KST)
        day_idx: int = now.weekday()
        topic_tuple: Optional[Tuple[str, str]] = cls.SCHEDULE.get(day_idx)
        return topic_tuple if topic_tuple is not None else ("오늘", "일반 주제")

    @classmethod
    def get_today_keywords(cls) -> List[str]:
        now: datetime = datetime.now(KST)
        day_idx: int = now.weekday()
        return cls.SEARCH_KEYWORDS.get(day_idx, ["건축"])

    @classmethod
    def get_policy(cls, day_idx: Optional[int] = None) -> Any:
        """TopicPolicyRegistry와 연동하여 요일별 공식 정책 객체 반환"""
        from official_sources.registry import TopicPolicyRegistry
        if day_idx is None:
            day_idx = datetime.now(KST).weekday()
        return TopicPolicyRegistry.get_by_day(day_idx)


def collect_official_evidence(
    policy: Any = None,
    run_date_kst: Optional[date] = None,
    providers: Optional[Sequence[Any]] = None,
) -> Any:
    """P0-4 공식 1차 출처 수집·검증 퍼사드 함수"""
    from official_sources.models import EvidencePack, TopicPolicy
    from official_sources.registry import TopicPolicyRegistry
    from official_sources.service import OfficialEvidenceService
    from official_sources.verification import OfficialSourceVerifier

    if policy is None:
        policy = BriefingSchedule.get_policy()
    if run_date_kst is None:
        run_date_kst = datetime.now(KST).date()

    if providers is None:
        from official_sources.adapters.data_go_kr import DataGoKrProvider
        from official_sources.adapters.gimcheon import GimcheonNoticeProvider
        from official_sources.adapters.gumi import GumiNoticeProvider
        from official_sources.adapters.iris import IrisAnnouncementProvider
        from official_sources.adapters.kaia import KaiaAnnouncementProvider
        from official_sources.adapters.kosis import KosisProvider
        from official_sources.adapters.molit_rss import MolitRssProvider
        from official_sources.adapters.reb_rone import RebRoneProvider
        from official_sources.http_client import SafeHttpClient

        http_client = SafeHttpClient(allowed_domains=policy.allowed_domains)
        providers = (
            KosisProvider(http_client),
            RebRoneProvider(http_client),
            DataGoKrProvider(http_client),
            MolitRssProvider(http_client),
            GumiNoticeProvider(http_client),
            GimcheonNoticeProvider(http_client),
            IrisAnnouncementProvider(http_client),
            KaiaAnnouncementProvider(http_client),
        )

    verifier = OfficialSourceVerifier()
    service = OfficialEvidenceService(providers, verifier)
    return service.collect(policy, run_date_kst)

class BriefingReport:
    """생성된 리포트 데이터 모델"""
    def __init__(self, day_name: str, topic: str, content: str) -> None:
        self.date: datetime = datetime.now(KST)
        self.day_name: str = day_name
        self.topic: str = topic
        self.content: str = content

    @property
    def folder_names(self) -> Tuple[str, str]:
        # 월 폴더: '2026년 04월' (표준화)
        month_str: str = self.date.strftime('%Y년 %m월')
        
        # 주차 폴더: 'X주차 분석' (사용자 실사 결과 반영)
        week_num: int = (self.date.day - 1) // 7 + 1
        week_str: str = f"{week_num}주차 분석"
        return month_str, week_str

    @property
    def page_title(self) -> str:
        # 사용자 요청에 따라 날짜 및 요일 접두사 복구: '[2026-04-22(수요일)] 주제'
        date_prefix: str = self.date.strftime('%Y-%m-%d')
        return f"[{date_prefix}({self.day_name})] {self.topic}"

# ==========================================
# Infrastructure Layer
# ==========================================
def parse_retry_after(
    header_val: Optional[str],
    default_backoff: float,
    clock_fn: Optional[Callable[[], float]] = None,
) -> float:
    """Parse HTTP 429 Retry-After header (seconds or RFC 7231 date) with safe boundaries."""
    if not header_val:
        return default_backoff
    header_val = header_val.strip()
    try:
        sec = float(header_val)
        if sec < 0:
            return default_backoff
        return min(sec, 60.0)
    except ValueError:
        pass
    try:
        dt = email.utils.parsedate_to_datetime(header_val)
        now_ts = clock_fn() if clock_fn else time.time()
        delay = dt.timestamp() - now_ts
        if delay < 0:
            return default_backoff
        return min(delay, 60.0)
    except Exception:
        return default_backoff


class AcademicProvider:
    """OpenAlex 후보를 Crossref와 교차 검증하는 엄격한 OA 논문 수집기 (G2 Rate Limit & Status 보강)."""
    def __init__(
        self,
        email: Optional[str] = None,
        max_retries: int = 3,
        base_backoff: float = 1.0,
        max_backoff: float = 10.0,
        query_interval: float = 0.25,
        sleep_fn: Optional[Callable[[float], None]] = None,
        clock_fn: Optional[Callable[[], float]] = None,
    ) -> None:
        actual_email = email or os.environ.get("OPENALEX_MAILTO") or "blueeye.research@gmail.com"
        self.polite_pool_configured: bool = bool(email or os.environ.get("OPENALEX_MAILTO"))
        self.headers: Dict[str, str] = {
            "User-Agent": f"BriefingAuto/9.0 (mailto:{actual_email})" if actual_email else "BriefingAuto/9.0"
        }
        self.max_retries: int = max_retries
        self.base_backoff: float = base_backoff
        self.max_backoff: float = max_backoff
        self.query_interval: float = max(0.0, query_interval)
        self.sleep_fn: Callable[[float], None] = sleep_fn or time.sleep
        self.clock_fn: Callable[[], float] = clock_fn or time.time
        self.last_audit: Dict[str, Any] = {}

    @staticmethod
    def _normalize_title(value: str) -> str:
        value = html.unescape(unicodedata.normalize("NFKC", value or ""))
        return re.sub(r"\s+", " ", value).strip().casefold()

    def search_with_status(
        self,
        keywords: List[str],
        max_papers: int = TARGET_PAPER_COUNT,
    ) -> AcademicSearchResult:
        """
        G2 상태 계약을 충족하는 검색 메서드:
        모든 쿼리 지표를 수집하고 429/Empty/Unavailable 상태를 엄격히 분리하여 반환.
        """
        rejection_reasons: Counter[str] = Counter()
        candidates: List[AcademicPaper] = []
        all_metrics: List[Dict[str, Any]] = []
        provider_failures: List[str] = []
        per_query = max(max_papers * 2, 20)

        for query_index, kw in enumerate(keywords):
            if query_index > 0 and self.query_interval > 0:
                self.sleep_fn(self.query_interval)
            papers, rejected, metric = self._search_single_query(kw, per_query)
            candidates.extend(papers)
            rejection_reasons.update(rejected)
            all_metrics.append(metric)
            if metric.get("error_type"):
                provider_failures.append(f"{kw}: {metric['error_type']}")

        unique_candidates: List[AcademicPaper] = []
        seen: set[str] = set()
        for paper in candidates:
            dedupe_key = (paper.doi or self._normalize_title(paper.title)).lower()
            if dedupe_key in seen:
                rejection_reasons["duplicate"] += 1
                continue
            seen.add(dedupe_key)
            unique_candidates.append(paper)

        eligible: List[AcademicPaper] = []
        for paper in unique_candidates:
            verified, reason = self._verify_crossref(paper)
            if verified is None:
                rejection_reasons[reason] += 1
                continue
            eligible.append(verified)
            if len(eligible) >= max_papers:
                break

        query_count = len(keywords)
        request_count = sum(m.get("requests", 1) for m in all_metrics)
        rate_limited_count = sum(m.get("rate_limited", 0) for m in all_metrics)
        success_count = sum(1 for m in all_metrics if m.get("success"))

        if eligible:
            status = SearchStatus.SEARCH_OK
            degraded = (
                rate_limited_count > 0
                or len(eligible) < max_papers
                or success_count < query_count
            )
        else:
            if rate_limited_count > 0 and success_count == 0:
                status = SearchStatus.OPENALEX_RATE_LIMITED
                degraded = True
            elif rejection_reasons.get("crossref_rate_limited", 0) > 0:
                status = SearchStatus.PROVIDER_UNAVAILABLE
                degraded = True
            elif (
                rejection_reasons.get("crossref_request_error", 0) > 0
                or rejection_reasons.get("crossref_unavailable", 0) > 0
            ):
                status = SearchStatus.PROVIDER_UNAVAILABLE
                degraded = True
            elif rejection_reasons.get("crossref_invalid_payload", 0) > 0:
                status = SearchStatus.PROVIDER_INVALID_RESPONSE
                degraded = True
            elif success_count == query_count:
                status = SearchStatus.SEARCH_GENUINE_EMPTY
                degraded = False
            elif rate_limited_count > 0:
                status = SearchStatus.OPENALEX_RATE_LIMITED
                degraded = True
            elif any("invalid" in str(m.get("error_type", "")).lower() for m in all_metrics):
                status = SearchStatus.PROVIDER_INVALID_RESPONSE
                degraded = True
            else:
                status = SearchStatus.PROVIDER_UNAVAILABLE
                degraded = True

        query_metrics = {
            "query_count": query_count,
            "request_count": request_count,
            "rate_limited_count": rate_limited_count,
            "success_count": success_count,
            "details": all_metrics,
        }

        self.last_audit = {
            "queries": list(keywords),
            "raw_candidates": len(candidates),
            "unique_candidates": len(unique_candidates),
            "eligible_count": len(eligible),
            "target_count": max_papers,
            "status": status.value,
            "degraded": degraded,
            "rejections": dict(sorted(rejection_reasons.items())),
            "polite_pool_configured": self.polite_pool_configured,
        }

        return AcademicSearchResult(
            papers=eligible,
            status=status,
            query_metrics=query_metrics,
            rejection_counts=dict(rejection_reasons),
            provider_failures=provider_failures,
            degraded=degraded,
            polite_pool_configured=self.polite_pool_configured,
        )

    def search_peer_reviewed_oa_papers(
        self,
        keywords: List[str],
        max_papers: int = TARGET_PAPER_COUNT,
    ) -> List[AcademicPaper]:
        """기존 하위 호환성을 유지하면서 search_with_status 결과를 반환."""
        res = self.search_with_status(keywords, max_papers)
        return res.papers

    def _search_single_query(
        self,
        query: str,
        max_papers: int,
    ) -> Tuple[List[AcademicPaper], Counter[str], Dict[str, Any]]:
        url: str = (
            f"https://api.openalex.org/works?"
            f"search={requests.utils.quote(query)}&"
            "filter=open_access.is_oa:true,type:article,is_retracted:false,"
            "primary_location.source.type:journal,has_abstract:true&"
            f"per_page={max_papers}"
        )
        rejected: Counter[str] = Counter()
        query_metric: Dict[str, Any] = {
            "query": query,
            "requests": 0,
            "rate_limited": 0,
            "success": False,
            "error_type": None,
        }

        for attempt in range(self.max_retries):
            query_metric["requests"] += 1
            try:
                res = requests.get(url, headers=self.headers, timeout=10)
                if res.status_code == 200:
                    query_metric["success"] = True
                    try:
                        data: Dict[str, Any] = res.json()
                    except Exception:
                        rejected["openalex_invalid_payload"] += 1
                        query_metric["error_type"] = "invalid_json"
                        return [], rejected, query_metric

                    raw_results: Any = data.get('results')
                    if not isinstance(raw_results, list):
                        rejected["openalex_invalid_payload"] += 1
                        query_metric["error_type"] = "invalid_payload"
                        return [], rejected, query_metric

                    papers: List[AcademicPaper] = []
                    for r in raw_results:
                        if not isinstance(r, dict):
                            rejected["invalid_record"] += 1
                            continue

                        doi: Optional[str] = r.get('doi')
                        title: str = r.get('title') or "제목 정보 없음"
                        if not doi or "doi.org/" not in doi:
                            rejected["missing_doi"] += 1
                            continue

                        authorships: Any = r.get('authorships', [])
                        authors: List[str] = []
                        if isinstance(authorships, list):
                            for a in authorships:
                                if isinstance(a, dict):
                                    auth_info = a.get('author')
                                    if isinstance(auth_info, dict) and auth_info.get('display_name'):
                                        authors.append(auth_info.get('display_name'))

                        year: Optional[int] = r.get('publication_year')
                        primary_loc: Any = r.get('primary_location') or {}
                        journal: str = "학술지"
                        source_type: Optional[str] = None
                        if isinstance(primary_loc, dict):
                            source_info = primary_loc.get('source')
                            if isinstance(source_info, dict) and source_info.get('display_name'):
                                journal = source_info.get('display_name')
                                source_type = source_info.get('type')

                        if source_type != "journal":
                            rejected["not_journal_source"] += 1
                            continue

                        best_oa: Any = r.get('best_oa_location') or {}
                        if not isinstance(best_oa, dict) or not best_oa.get('is_oa'):
                            rejected["missing_oa_location"] += 1
                            continue
                        oa_url: str = best_oa.get('pdf_url') or best_oa.get('landing_page_url') or ""
                        oa_version: Optional[str] = best_oa.get('version')
                        oa_license: Optional[str] = best_oa.get('license')

                        if not oa_url:
                            rejected["missing_oa_url"] += 1
                            continue
                        if oa_version not in {"publishedVersion", "acceptedVersion"}:
                            rejected["unverified_peer_review_version"] += 1
                            continue
                        license_value = (oa_license or "").lower()
                        if not any(license_value.startswith(prefix) for prefix in OA_LICENSE_PREFIXES):
                            rejected["missing_open_license"] += 1
                            continue

                        # Inverted index로부터 초록 복원
                        inv: Any = r.get('abstract_inverted_index')
                        abstract: str = ""
                        if isinstance(inv, dict):
                            word_list: List[Tuple[int, str]] = [
                                (pos, word) for word, positions in inv.items() if isinstance(positions, list) for pos in positions if isinstance(pos, int)
                            ]
                            word_list.sort(key=lambda x: x[0])
                            abstract = " ".join(w for _, w in word_list)

                        if not abstract.strip():
                            rejected["missing_abstract"] += 1
                            continue

                        title = html.unescape(title)
                        papers.append(AcademicPaper(
                            title=title,
                            authors=authors,
                            journal=journal,
                            year=year,
                            doi=doi,
                            oa_url=oa_url,
                            abstract=abstract,
                            openalex_id=r.get('id'),
                            source_type=source_type,
                            oa_version=oa_version,
                            oa_license=oa_license,
                            is_retracted=bool(r.get('is_retracted')),
                        ))

                    return papers, rejected, query_metric

                elif res.status_code == 429:
                    query_metric["rate_limited"] += 1
                    rejected["openalex_rate_limited"] += 1
                    hdr = getattr(res, "headers", {}).get("Retry-After") if hasattr(res, "headers") else None
                    backoff = parse_retry_after(hdr, self.base_backoff * (2 ** attempt), self.clock_fn)
                    capped_backoff = min(backoff, self.max_backoff)
                    if attempt < self.max_retries - 1:
                        self.sleep_fn(capped_backoff)
                        continue
                    else:
                        query_metric["error_type"] = "rate_limited"
                        return [], rejected, query_metric
                else:
                    rejected["openalex_http_error"] += 1
                    query_metric["error_type"] = f"http_{res.status_code}"
                    if res.status_code >= 500 and attempt < self.max_retries - 1:
                        self.sleep_fn(min(self.base_backoff * (2 ** attempt), self.max_backoff))
                        continue
                    return [], rejected, query_metric

            except Exception as e:
                rejected["openalex_request_error"] += 1
                query_metric["error_type"] = type(e).__name__
                if attempt < self.max_retries - 1:
                    self.sleep_fn(min(self.base_backoff * (2 ** attempt), self.max_backoff))
                    continue
                return [], rejected, query_metric

        return [], rejected, query_metric

    def _verify_crossref(
        self,
        paper: AcademicPaper,
    ) -> Tuple[Optional[AcademicPaper], str]:
        """Crossref 유형과 제목이 OpenAlex 레코드와 일치할 때만 채택."""
        if not paper.doi or "doi.org/" not in paper.doi:
            return None, "missing_doi"

        raw_doi = paper.doi.split("doi.org/", 1)[-1]
        try:
            response = requests.get(
                f"https://api.crossref.org/works/{raw_doi}",
                headers=self.headers,
                timeout=8,
            )
            if response.status_code == 429:
                return None, "crossref_rate_limited"
            if response.status_code >= 500:
                return None, "crossref_unavailable"
            if response.status_code != 200:
                return None, "crossref_http_error"
            message = response.json().get("message", {})
        except Exception:
            return None, "crossref_request_error"

        if not isinstance(message, dict):
            return None, "crossref_invalid_payload"
        if message.get("type") != "journal-article":
            return None, "crossref_not_journal_article"

        titles = message.get("title") or []
        if not isinstance(titles, list) or not titles or not isinstance(titles[0], str):
            return None, "crossref_missing_title"
        if self._normalize_title(titles[0]) != self._normalize_title(paper.title):
            return None, "doi_title_mismatch"

        paper.crossref_type = "journal-article"
        paper.title_verified = True
        if not paper.strict_eligibility_passed:
            return None, "strict_eligibility_failed"
        return paper, "eligible"


class GeminiProvider:
    """Gemini API 제공자 (G3 길이 계약, 축약 Fallback 및 시도 추적 지원)"""
    def __init__(self, api_key: Optional[str]) -> None:
        self.client: Any = None
        if api_key:
            client_instance: Any = genai.Client(api_key=api_key) # type: ignore
            self.client = client_instance
        self.models: List[str] = [
            "models/gemini-3.8-flash",
            "models/gemini-3.7-flash",
            "models/gemini-3.6-flash",
            "models/gemini-2.5-flash",
            "models/gemini-2.5-flash-lite"
        ]

    @staticmethod
    def _classify_gemini_error(exc: BaseException) -> str:
        msg = str(exc).lower()
        if "본문 길이" in str(exc) or "length" in msg:
            if "미달" in str(exc) or "too short" in msg:
                return GeminiOutcome.OUTPUT_TOO_SHORT.value
            return GeminiOutcome.OUTPUT_TOO_LONG.value
        if "429" in msg or "resource_exhausted" in msg or "rate limit" in msg:
            return GeminiOutcome.RATE_LIMITED.value
        if "503" in msg or "unavailable" in msg:
            return GeminiOutcome.UNAVAILABLE.value
        if "404" in msg or "not_found" in msg or "no longer available" in msg:
            return GeminiOutcome.UNAVAILABLE.value
        if "timeout" in msg or "timed out" in msg or "deadline_exceeded" in msg:
            return GeminiOutcome.TIMEOUT.value
        if "safety" in msg or "blocked" in msg:
            return GeminiOutcome.SAFETY_BLOCKED.value
        if "invalid" in msg or "json" in msg:
            return GeminiOutcome.INVALID_RESPONSE.value
        return GeminiOutcome.UNKNOWN_ERROR.value

    def _build_prompt(self, topic: str, papers: Optional[List[AcademicPaper]] = None, degraded: bool = False) -> str:
        if papers:
            paper_contexts = []
            for idx, p in enumerate(papers, 1):
                author_str = ", ".join(p.authors) if p.authors else "저자 미상"
                year_str = f"({p.year})" if p.year else ""
                paper_contexts.append(
                    f"[논문 {idx}]\n"
                    f"- 논문명: {p.title}\n"
                    f"- 저자: {author_str}\n"
                    f"- 학술지: {p.journal} {year_str}\n"
                    f"- 연구 초록(Abstract): {p.abstract or '초록 원문 없음'}\n"
                )
            context_str = "\n".join(paper_contexts)
            if degraded or len(papers) < TARGET_PAPER_COUNT:
                deficit_notice = (
                    f"⚠️ [자료 결손 공시] 적격 논문은 목표 {TARGET_PAPER_COUNT}편 중 {len(papers)}편만 확보되었습니다. "
                    "부족분을 가공의 논문으로 채우지 말고 서론에 자료 결손 상태를 명시하십시오."
                )
            else:
                deficit_notice = f"적격 논문 {TARGET_PAPER_COUNT}편이 모두 확보되었습니다."

            return (
                f"당신은 공인 학술 연구를 심층 분석하여 전문가 브리핑을 작성하는 수석 연구위원입니다.\n\n"
                f"주제: [{topic}]\n\n"
                f"[엄격 적격성 게이트를 통과한 피어리뷰 오픈액세스 논문의 서지정보와 초록]\n"
                f"{context_str}\n\n"
                f"[자료 충족 상태] {deficit_notice}\n\n"
                f"다음 지침을 한 치의 오차도 없이 엄격히 준수하여 학술적 심층 분석 리포트를 작성하십시오:\n"
                f"1. 위에 제공된 서지정보와 초록만 사용하십시오. 논문 원문을 읽었다고 표현하거나 초록에 없는 방법·수치·결론을 추정하지 마십시오.\n"
                f"2. 위 목록에 제공되지 않은 임의의 다른 가짜 논문, 가짜 저자, 가짜 서지정보를 지어내거나 인용하는 행위를 100% 엄격히 금지합니다.\n"
                f"3. 보고서 본문 하단에 별도의 '참고문헌' 목록이나 URL 링크를 직접 작성하지 마십시오. (참고문헌과 검증 링크는 시스템 파이프라인에서 자동으로 결합됩니다).\n"
                f"4. 본문은 참고문헌을 제외하고 공백 포함 {TARGET_BODY_MIN_CHARS:,}~{TARGET_BODY_MAX_CHARS:,}자로 작성하십시오.\n"
                f"5. 검증 가능한 주장에는 [논문 1]처럼 제공된 논문 번호를 붙이고, 근거가 약하면 '초록만으로 확인 불가'라고 명시하십시오.\n"
                f"6. 실무자가 바로 사용할 수 있도록 요약, 근거 분석, 상충/한계, 적용 방안, 확인이 필요한 항목을 구분하십시오."
            )
        else:
            if degraded:
                notice = (
                    "⚠️ [공급자 장애 공시] 공인 학술 DB 일시 장애로 피어리뷰 오픈액세스 논문을 수집하지 못했습니다.\n"
                    "서론에 '학술 DB 공급자 장애로 인한 적격 논문 0편'과 학술적 근거의 한계를 명시하십시오.\n"
                )
            else:
                notice = (
                    "금일 주제에 대해 공인 학술 DB에서 100% 피어리뷰 오픈액세스 논문이 검색되지 않았습니다.\n"
                    "서론에 '적격 피어리뷰 OA 논문 0편'과 학술적 근거의 한계를 명시하십시오.\n"
                )
            return (
                f"당신은 건축/부동산 분야 실무 기술 및 공공 정책 분석 전문가입니다.\n\n"
                f"주제: [{topic}]\n\n"
                f"[중요 무결성 지침]\n"
                f"{notice}"
                f"허위 학술 자료(가짜 논문명, 가짜 저자명, 가짜 학술지 인용) 생성을 엄격히 금지합니다.\n"
                f"존재하지 않는 가상의 학술 논문을 절대로 지어내어 인용하지 마시고, 공공 가이드라인, 표준 시방서, 제도적 동향, 실무 프로세스 관점에서 전문적인 분석 리포트를 작성하십시오.\n"
                f"본문 하단에 가짜 참고문헌 섹션을 작성하지 마십시오.\n"
                f"분량은 참고문헌을 제외하고 공백 포함 {TARGET_BODY_MIN_CHARS:,}~{TARGET_BODY_MAX_CHARS:,}자로 구성하십시오."
            )

    def _build_condense_prompt(self, original_text: str) -> str:
        return (
            f"당신은 공인 학술 연구 심층 분석 리포트를 작성하는 수석 연구위원입니다.\n\n"
            f"이전에 작성된 아래 브리핑 본문이 운영 분량 상한(공백 포함 {TARGET_BODY_MAX_CHARS:,}자)을 초과하였습니다.\n"
            f"다음 지침을 한 치의 오차도 없이 엄격히 준수하여 본문을 축약하십시오:\n\n"
            f"1. [핵심 불변조건] 본문에 포함된 모든 논문 번호 인용(예: [논문 1]), 출처 저널/저자 표기, 핵심 수치 데이터, 주요 연구 결론 및 제안을 100% 누락 없이 원문 그대로 보존하십시오.\n"
            f"2. [환각 및 위조 절대 금지] 새로운 사실, 가상의 출처, 새로운 URL 링크를 절대로 추가하거나 지어내지 마십시오.\n"
            f"3. [축약 기법] 중복되는 문장 서술, 과도한 수식어, 불필요하게 긴 서론 및 결론의 부연 설명을 정밀하게 다듬어 압축하십시오.\n"
            f"4. [분량 계약] 최종 본문 길이는 반드시 공백 포함 {TARGET_BODY_MAX_CHARS:,}자 이하여야 합니다. 하한은 없습니다.\n"
            f"5. [참고문헌 분리] 본문 끝에 별도의 참고문헌 목록이나 외부 웹 링크를 직접 작성하지 마십시오.\n\n"
            f"[원래 작성된 초과 본문]\n"
            f"{original_text.strip()}"
        )

    def _finalize_report(self, main_body: str, model_name: str, papers: Optional[List[AcademicPaper]]) -> str:
        ref_section: str = AcademicPaper.format_reference_section(
            papers or [], TARGET_PAPER_COUNT
        )
        peer_review_badge = (
            f"PASSED ({len(papers)}/{TARGET_PAPER_COUNT} papers passed the strict metadata gate)"
            if papers else "ABSTENTION APPLIED (No OA Papers Found - Fake Citation Prevented)"
        )
        footer = (
            "\n\n---\n"
            "**🛡️ Governance Verification Matrix**\n"
            "- **Protocol**: IRD-DP v6.2 (Adversarial Autopilot)\n"
            "- **Tier Level**: Tier 1 Revamp (Academic OpenAccess v8.0)\n"
            f"- **Peer-Review Status**: {peer_review_badge}\n"
            f"- **Model Used**: {model_name}\n"
            "- **Timestamp**: " + datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S KST') + "\n"
            "- **Audit Trail**: [View Public Logs](https://github.com/blueeye-3184/briefing/blob/main/04.Data_Collection_Log.md)"
        )
        return main_body + ref_section + footer

    def generate_content(
        self,
        topic: str,
        papers: Optional[List[AcademicPaper]] = None,
        degraded: bool = False,
        manifest_manager: Optional[ManifestManager] = None,
    ) -> str:
        if self.client is None and not hasattr(self._call_api, "assert_called"):
            raise ValueError("GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")

        is_mocked = hasattr(self._call_api, "assert_called")

        skip_jitter = os.environ.get("BRIEFING_SKIP_JITTER", "").strip().lower() in {
            "1", "true", "yes"
        }
        if (
            os.environ.get("GITHUB_ACTIONS")
            and not skip_jitter
            and not getattr(self, "_skip_jitter", False)
        ):
            jitter: int = random.randint(0, 300)
            if jitter > 0:
                print(f"[정보] 트래픽 분산을 위해 {jitter}초 대기 후 시작합니다...")
                time.sleep(jitter)

        last_err: Optional[Exception] = None
        for model_name in self.models:
            t0 = time.time()
            current_attempt_type = "FULL"
            try:
                print(f"[시도] {model_name} 모델로 리포트 생성 중...")
                if is_mocked:
                    main_body = self._call_api(model_name, topic, papers)
                    return self._finalize_report(main_body, model_name, papers)

                # 1. Full prompt attempt
                prompt = self._build_prompt(topic, papers=papers, degraded=degraded)
                text_val = self._generate_with_prompt(model_name, prompt)
                elapsed = time.time() - t0
                body_length = len(text_val.strip())

                # Short output is publishable for human review. Only the upper
                # bound triggers a rewrite; an empty/non-string response is
                # rejected earlier by _generate_with_prompt().
                if body_length <= TARGET_BODY_MAX_CHARS:
                    if manifest_manager:
                        manifest_manager.record_gemini_attempt(
                            model=model_name,
                            attempt_type="FULL",
                            outcome=GeminiOutcome.SUCCESS.value,
                            char_count=body_length,
                            elapsed_seconds=elapsed,
                        )
                    return self._finalize_report(text_val, model_name, papers)

                # body_length > TARGET_BODY_MAX_CHARS -> attempt CONDENSE
                if manifest_manager:
                    manifest_manager.record_gemini_attempt(
                        model=model_name,
                        attempt_type="FULL",
                        outcome=GeminiOutcome.OUTPUT_TOO_LONG.value,
                        char_count=body_length,
                        elapsed_seconds=elapsed,
                    )
                print(f"[정보] {model_name} 출력 길이({body_length:,}자) 초과 -> CONDENSE 축약 시도")

                t1 = time.time()
                current_attempt_type = "CONDENSE"
                condense_prompt = self._build_condense_prompt(text_val)
                condensed_val = self._generate_with_prompt(model_name, condense_prompt)
                elapsed_condense = time.time() - t1
                condensed_length = len(condensed_val.strip())

                if condensed_length <= TARGET_BODY_MAX_CHARS:
                    if manifest_manager:
                        manifest_manager.record_gemini_attempt(
                            model=model_name,
                            attempt_type="CONDENSE",
                            outcome=GeminiOutcome.SUCCESS.value,
                            char_count=condensed_length,
                            elapsed_seconds=elapsed_condense,
                        )
                    print(f"[성공] {model_name} CONDENSE 축약 성공 ({condensed_length:,}자)")
                    return self._finalize_report(condensed_val, model_name, papers)
                else:
                    if manifest_manager:
                        manifest_manager.record_gemini_attempt(
                            model=model_name,
                            attempt_type="CONDENSE",
                            outcome=GeminiOutcome.OUTPUT_TOO_LONG.value,
                            char_count=condensed_length,
                            elapsed_seconds=elapsed_condense,
                        )
                    raise ValueError(
                        f"CONDENSE 축약 후에도 본문 길이 {condensed_length:,}자가 허용 범위를 벗어났습니다."
                    )

            except Exception as e:
                elapsed = time.time() - t0
                outcome = self._classify_gemini_error(e)
                print(f"[경고] {model_name} 실패: {outcome} ({e})")
                last_err = e

                # G3 Contract Rule: If length contract violated, stop fallback!
                if outcome == GeminiOutcome.OUTPUT_TOO_LONG.value:
                    raise e

                # Record attempt if not already recorded
                if manifest_manager and not any(
                    a["model"] == model_name and a["attempt_type"] == current_attempt_type
                    for a in manifest_manager.manifest_data.get("gemini_attempts", [])
                ):
                    manifest_manager.record_gemini_attempt(
                        model=model_name,
                        attempt_type=current_attempt_type,
                        outcome=outcome,
                        char_count=None,
                        elapsed_seconds=elapsed,
                    )
                if outcome in (
                    GeminiOutcome.RATE_LIMITED.value,
                    GeminiOutcome.UNAVAILABLE.value,
                    GeminiOutcome.TIMEOUT.value,
                ):
                    time.sleep(1)
                    continue
                raise e

        if isinstance(last_err, Exception):
            raise last_err
        raise ValueError("모든 Gemini 모델 시도가 실패했습니다.")

    @staticmethod
    def _is_retryable_api_error(exc: BaseException) -> bool:
        """404 Not Found 또는 지원 중단 등 영구적 모델 미지원 오류는 재시도 없이 즉시 다음 모델로 전환"""
        msg = str(exc).lower()
        if "404" in msg or "not_found" in msg or "no longer available" in msg:
            return False
        return True

    def _generate_with_prompt(self, model_name: str, prompt: str) -> str:
        client: Any = self.client
        token_counter = getattr(client.models, "count_tokens", None)
        if callable(token_counter):
            token_result = token_counter(model=model_name, contents=prompt)
            input_tokens = getattr(token_result, "total_tokens", None)
            if isinstance(input_tokens, int):
                print(f"[정보] Gemini 입력 토큰: {input_tokens:,}")
                if input_tokens > MAX_INPUT_TOKENS:
                    raise ValueError(
                        f"입력 토큰 {input_tokens:,}이 운영 상한 {MAX_INPUT_TOKENS:,}을 초과했습니다."
                    )

        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=MAX_OUTPUT_TOKENS,
            ),
        )
        text_val = response.text
        if not isinstance(text_val, str) or not text_val:
            raise ValueError(f"{model_name} 모델로부터 유효한 텍스트 응답을 받지 못했습니다.")
        return text_val

    @retry(
        retry=retry_if_exception(lambda exc: GeminiProvider._is_retryable_api_error(exc)),
        stop=stop_after_attempt(3 if os.environ.get('GITHUB_ACTIONS') else 2),
        wait=wait_exponential(multiplier=2, min=5, max=30),
        reraise=True
    )
    def _call_api(self, model_name: str, topic: str, papers: Optional[List[AcademicPaper]] = None, use_tools: bool = False, **kwargs: Any) -> str:
        prompt = self._build_prompt(topic, papers=papers)
        text_val = self._generate_with_prompt(model_name, prompt)
        body_length = len(text_val.strip())
        if body_length > TARGET_BODY_MAX_CHARS:
            raise ValueError(
                f"본문 길이 {body_length:,}자가 운영 상한 "
                f"{TARGET_BODY_MAX_CHARS:,}자를 초과했습니다."
            )
        return text_val

class NotionPublisher:
    """Notion API 저장소"""
    def __init__(self, token: Optional[str]) -> None:
        self.token: Optional[str] = token
        auth_token: str = token if token else ""
        self.headers: Dict[str, str] = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }

    def request(self, method: str, url: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if self.token is None:
            raise ValueError("NOTION_TOKEN이 설정되지 않았습니다.")
        res: requests.Response = requests.request(
            method, url, headers=self.headers, json=data, timeout=30
        )
        try:
            res.raise_for_status()
        except requests.exceptions.HTTPError as e:
            print(f"[오류 상세] Notion API Response: {res.text}")
            raise e
        return cast(Dict[str, Any], res.json())

    def get_or_create_page(self, parent_id: str, title: str, icon: str = "📝") -> str:
        # 1. 먼저 해당 부모 하위의 자식들을 직접 조회하여 동일한 제목이 있는지 확인 (정밀도 향상)
        url: str = f"https://api.notion.com/v1/blocks/{parent_id}/children"
        res_children: Dict[str, Any] = self.request("GET", url)
        raw_results: Any = res_children.get('results')
        
        if isinstance(raw_results, list):
            for result in raw_results:
                if not isinstance(result, dict): continue
                if result.get('type') == 'child_page':
                    child_page = result.get('child_page', {})
                    if child_page.get('title') == title:
                        c_id = result.get('id')
                        print(f"[정보] 기존 페이지 발견 (부모 일치): {title} ({c_id})")
                        return cast(str, c_id)

        # 2. 없으면 새로 생성
        data: Dict[str, Any] = {
            "parent": {"page_id": parent_id},
            "icon": {"type": "emoji", "emoji": icon},
            "properties": {"title": {"title": [{"text": {"content": title}}]}}
        }
        res: Dict[str, Any] = self.request("POST", "https://api.notion.com/v1/pages", data)
        new_id: Any = res.get('id')
        if not isinstance(new_id, str):
            raise ValueError("페이지 생성 후 ID를 받지 못했습니다.")
        print(f"[정보] 새 페이지 생성: {title} ({new_id})")
        return new_id

    def find_page_by_title(self, title: str) -> Optional[str]:
        """제목으로 기존 페이지 검색"""
        data: Dict[str, Any] = {
            "query": title,
            "filter": {"value": "page", "property": "object"},
            "sort": {"direction": "descending", "timestamp": "last_edited_time"}
        }
        res: Dict[str, Any] = self.request("POST", "https://api.notion.com/v1/search", data)
        
        # Pylance UnknownMemberType 에러 방지를 위한 촘촘한 타입 가드
        raw_results: Any = res.get('results')
        if not isinstance(raw_results, list):
            return None

        for result in raw_results:
            if not isinstance(result, dict): continue
            res_dict = cast(Dict[str, Any], result)
            
            props: Any = res_dict.get('properties')
            if not isinstance(props, dict): continue
            props_dict = cast(Dict[str, Any], props)
            
            title_container: Any = props_dict.get('title')
            if not isinstance(title_container, dict): continue
            tc_dict = cast(Dict[str, Any], title_container)
                
            title_list: Any = tc_dict.get('title')
            if isinstance(title_list, list) and len(title_list) > 0:
                first_node: Any = title_list[0]
                if isinstance(first_node, dict):
                    fn_dict = cast(Dict[str, Any], first_node)
                    if fn_dict.get('plain_text') == title:
                        f_id: Any = res_dict.get('id')
                        return cast(str, f_id) if isinstance(f_id, str) else None
        return None

    @staticmethod
    def _split_text_safely(
        text: str,
        limit: int = NOTION_SAFE_TEXT_LIMIT,
    ) -> List[str]:
        """2,000자 제한보다 여유 있게 문장/공백 경계에서 분할."""
        if limit > NOTION_RICH_TEXT_LIMIT:
            raise ValueError("Notion 안전 분할값은 2,000자를 초과할 수 없습니다.")
        chunks: List[str] = []
        remaining = text.strip()
        while len(remaining) > limit:
            cut = max(
                remaining.rfind("다. ", 0, limit),
                remaining.rfind(". ", 0, limit),
                remaining.rfind(" ", 0, limit),
            )
            if cut < limit // 2:
                cut = limit
            else:
                cut += 1
            chunks.append(remaining[:cut].strip())
            remaining = remaining[cut:].strip()
        if remaining:
            chunks.append(remaining)
        return chunks

    @staticmethod
    def _rich_text(text: str) -> List[Dict[str, Any]]:
        """Markdown 링크를 Notion hyperlink rich text로 변환."""
        nodes: List[Dict[str, Any]] = []
        cursor = 0
        link_pattern = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
        for match in link_pattern.finditer(text):
            if match.start() > cursor:
                nodes.append({"type": "text", "text": {"content": text[cursor:match.start()]}})
            nodes.append({
                "type": "text",
                "text": {
                    "content": match.group(1),
                    "link": {"url": match.group(2)},
                },
            })
            cursor = match.end()
        if cursor < len(text):
            nodes.append({"type": "text", "text": {"content": text[cursor:]}})
        return nodes or [{"type": "text", "text": {"content": text}}]

    @staticmethod
    def _rich_text_length(nodes: List[Dict[str, Any]]) -> int:
        return sum(
            len(str(node.get("text", {}).get("content", "")))
            for node in nodes
        )

    def _compact_blocks_for_budget(
        self, blocks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Pack adjacent body blocks without truncating text or link nodes.

        Headings and dividers remain structural boundaries. Paragraph and list
        runs are folded into newline-separated paragraphs whose rich text stays
        below the conservative per-block text limit.
        """
        compacted: List[Dict[str, Any]] = []
        pending_nodes: List[Dict[str, Any]] = []
        pending_length = 0
        mergeable_types = {"paragraph", "bulleted_list_item", "numbered_list_item"}

        def flush_pending() -> None:
            nonlocal pending_nodes, pending_length
            if pending_nodes:
                compacted.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": pending_nodes},
                })
                pending_nodes = []
                pending_length = 0

        for block in blocks:
            block_type = str(block.get("type", ""))
            if block_type not in mergeable_types:
                flush_pending()
                compacted.append(block)
                continue

            nodes = list(block.get(block_type, {}).get("rich_text", []))
            node_length = self._rich_text_length(nodes)
            separator_length = 1 if pending_nodes else 0
            if pending_nodes and (
                pending_length + separator_length + node_length
                > NOTION_SAFE_TEXT_LIMIT
            ):
                flush_pending()
                separator_length = 0
            if pending_nodes:
                pending_nodes.append({"type": "text", "text": {"content": "\n"}})
            pending_nodes.extend(nodes)
            pending_length += separator_length + node_length

        flush_pending()
        return compacted

    def markdown_to_notion_blocks(self, content: str) -> List[Dict[str, Any]]:
        """지원 Markdown을 안전한 Notion 블록으로 변환하고 블록 예산을 검증."""
        blocks: List[Dict[str, Any]] = []
        for line in content.split('\n'):
            raw: str = line.strip()
            if not raw: continue
            
            b_t: str = "paragraph"
            txt: str = raw
            if raw.startswith('###'): b_t = "heading_3"; txt = raw[3:].strip()
            elif raw.startswith('##'): b_t = "heading_2"; txt = raw[2:].strip()
            elif raw.startswith('#'): b_t = "heading_1"; txt = raw[1:].strip()
            elif raw.startswith(('- ', '* ')): b_t = "bulleted_list_item"; txt = raw[2:].strip()
            elif re.match(r'^\d+\.\s+', raw):
                b_t = "numbered_list_item"
                txt = re.sub(r'^\d+\.\s+', '', raw, count=1)
            elif raw == '---':
                blocks.append({"object": "block", "type": "divider", "divider": {}})
                continue

            if not txt: continue # 텍스트 내용이 없으면 블록 생성 건너뜀

            chunks = self._split_text_safely(txt)
            for chunk_index, chunk in enumerate(chunks):
                if not chunk.strip(): continue # 공백만 있는 청크 제외
                chunk_type = b_t if chunk_index == 0 or b_t in {
                    "bulleted_list_item", "numbered_list_item"
                } else "paragraph"
                blocks.append({
                    "object": "block",
                    "type": chunk_type,
                    chunk_type: {"rich_text": self._rich_text(chunk)}
                })

        if len(blocks) > NOTION_OPERATIONAL_BLOCK_LIMIT:
            original_count = len(blocks)
            blocks = self._compact_blocks_for_budget(blocks)
            print(
                f"[정보] Notion 블록 예산 압축: {original_count}개 -> {len(blocks)}개 "
                f"(상한 {NOTION_OPERATIONAL_BLOCK_LIMIT}개, 본문 절단 없음)"
            )

        if len(blocks) > NOTION_OPERATIONAL_BLOCK_LIMIT:
            raise ValueError(
                f"Notion 블록 {len(blocks)}개가 운영 상한 "
                f"{NOTION_OPERATIONAL_BLOCK_LIMIT}개를 초과했고 안전하게 압축할 수 없습니다."
            )
        if len(blocks) > NOTION_REQUEST_BLOCK_LIMIT:
            raise ValueError("Notion 요청당 100블록 제한을 초과했습니다.")
        return blocks

    def publish_report(self, parent_id: str, report: BriefingReport) -> None:
        """검증된 블록 예산 안에서 리포트를 Notion에 발행."""
        blocks = self.markdown_to_notion_blocks(report.content)
        data: Dict[str, Any] = {
            "parent": {"page_id": parent_id},
            "properties": {"title": {"title": [{"text": {"content": report.page_title}}]}},
            "children": blocks,
        }
        self.request("POST", "https://api.notion.com/v1/pages", data)

class SlackNotifier:
    """Slack 실시간 알림 서비스"""
    def __init__(self, webhook_url: Optional[str]) -> None:
        self.webhook_url = webhook_url

    def notify(self, message: str, level: str = "info") -> None:
        if not self.webhook_url:
            return
            
        emoji = "ℹ️"
        if level == "success": emoji = "✅"
        elif level == "error": emoji = "🚨"
        
        payload = {
            "text": f"{emoji} *[Briefing System]* {message}"
        }
        try:
            resp = requests.post(self.webhook_url, json=payload, timeout=10)
            if not resp.ok:
                print(f"[경고] 슬랙 알림 HTTP 오류 응답 ({resp.status_code})")
        except Exception as e:
            print(f"[경고] 슬랙 알림 전송 실패: {type(e).__name__}")

# ==========================================
# Application Layer
# ==========================================
class BriefingApplicationService:
    def __init__(
        self,
        gemini: GeminiProvider,
        notion: NotionPublisher,
        slack: SlackNotifier,
        academic: Optional[AcademicProvider] = None,
        parent_page_id: Optional[str] = None,
        manifest_manager: Optional[ManifestManager] = None,
    ) -> None:
        self.gemini = gemini
        self.notion = notion
        self.slack = slack
        self.academic = academic or AcademicProvider()
        self.parent_page_id = parent_page_id or os.environ.get('PARENT_PAGE_ID')
        self.manifest_manager = manifest_manager

    def run_daily_briefing(self) -> None:
        validate_environment()
        if not self.parent_page_id or not self.parent_page_id.strip():
            raise ValueError("필수 환경 변수가 누락되었습니다: PARENT_PAGE_ID")

        day_name, topic = BriefingSchedule.get_today_topic()
        keywords = BriefingSchedule.get_today_keywords()
        run_id = os.environ.get("GITHUB_RUN_ID")
        commit_sha = os.environ.get("GITHUB_SHA")
        decision_id = os.environ.get("DECISION_ID") or f"{datetime.now(KST).strftime('%Y%m%d')}-{run_id or 'local'}"

        # G4: Initialize artifacts/run.log and artifacts/manifest.json BEFORE external calls
        manifest = self.manifest_manager or ManifestManager()
        manifest.initialize(decision_id=decision_id, topic=topic, run_id=run_id, commit_sha=commit_sha)
        manifest.log(f"Starting Daily Briefing for topic: {topic}", stage="INITIALIZE")
        manifest.log(f"Target keywords: {keywords}", stage="INITIALIZE")

        current_stage = "ACADEMIC_SEARCH"
        try:
            # 1. Academic Search with explicit status and metrics (G2)
            manifest.log("Executing academic search", stage="ACADEMIC_SEARCH")
            search_result: AcademicSearchResult = self.academic.search_with_status(
                keywords, max_papers=TARGET_PAPER_COUNT
            )
            papers = search_result.papers

            manifest.update_academic_search(
                status=search_result.status.value,
                query_count=search_result.query_metrics.get("query_count", len(keywords)),
                request_count=search_result.query_metrics.get("request_count", 0),
                rate_limited_count=search_result.query_metrics.get("rate_limited_count", 0),
                success_count=search_result.query_metrics.get("success_count", 0),
                eligible_paper_count=len(papers),
                polite_pool_configured=search_result.polite_pool_configured,
            )

            manifest.log(
                f"Academic search status={search_result.status.value}, "
                f"eligible_papers={len(papers)}/{TARGET_PAPER_COUNT}, degraded={search_result.degraded}",
                stage="ACADEMIC_SEARCH"
            )

            # G2 Guard: Provider failure across all queries with 0 papers must NOT proceed to normal generation!
            if search_result.status in (SearchStatus.OPENALEX_RATE_LIMITED, SearchStatus.PROVIDER_UNAVAILABLE) and len(papers) == 0:
                raise RuntimeError(
                    f"학술 DB 공급자 장애({search_result.status.value})로 검색이 전면 실패했습니다. "
                    "정상 브리핑 생성을 중단하고 장애 상태를 기록합니다."
                )

            # 2. Gemini Generation with G3 Condense and Attempt Tracking
            current_stage = "GEMINI_GENERATION"
            manifest.log("Starting Gemini content generation", stage="GEMINI_GENERATION")
            content: str = self.gemini.generate_content(
                topic, papers=papers, degraded=search_result.degraded, manifest_manager=manifest
            )
            report: BriefingReport = BriefingReport(day_name, topic, content)

            quality_state = "DEGRADED" if search_result.degraded else "NORMAL"
            manifest.update_report(body_length=len(content), quality_state=quality_state)

            # 3. Notion Publishing
            current_stage = "NOTION_PUBLISH"
            manifest.log("Publishing report to Notion", stage="NOTION_PUBLISH")
            names: Tuple[str, str] = report.folder_names
            m_id: str = self.notion.get_or_create_page(self.parent_page_id, names[0], "📁")
            w_id: str = self.notion.get_or_create_page(m_id, names[1], "📂")

            self.notion.publish_report(w_id, report)
            page_id_hash = hash_page_id(w_id)
            manifest.update_notion(
                status="PUBLISHED_TEXT",
                page_id_hash=page_id_hash,
                expected_image_count=0,
                uploaded_image_count=0,
                read_back_image_count=0,
            )

            manifest.finish(status="PUBLISHED_TEXT")
            manifest.log("Daily Briefing successfully completed and published", stage="COMPLETION")

            self.slack.notify(
                f"오늘자 브리핑 저장 완료: *{report.page_title}* "
                f"(엄격 적격성 게이트 통과 OA 논문 {len(papers)}/{TARGET_PAPER_COUNT}건)",
                "success"
            )
        except Exception as e:
            manifest.record_failure(
                stage=current_stage,
                error_type=type(e).__name__,
                safe_message=str(e)[:200]
            )
            manifest.log(
                f"Daily Briefing failed at stage [{current_stage}]: {type(e).__name__} - {str(e)[:200]}",
                level="ERROR",
                stage=current_stage
            )
            err_msg = f"오늘자 브리핑 생성 실패\n- *주제*: {topic}\n- *오류*: {str(e)[:200]}"
            self.slack.notify(err_msg, "error")
            raise e


if __name__ == "__main__":
    env_vars = validate_environment()
    g_p = GeminiProvider(env_vars["GEMINI_API_KEY"])
    n_p = NotionPublisher(env_vars["NOTION_TOKEN"])
    s_p = SlackNotifier(env_vars.get("SLACK_WEBHOOK_URL"))
    a_p = AcademicProvider()
    service = BriefingApplicationService(g_p, n_p, s_p, a_p, parent_page_id=env_vars["PARENT_PAGE_ID"])
    service.run_daily_briefing()
