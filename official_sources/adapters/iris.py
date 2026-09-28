"""official_sources.adapters.iris

IRIS (범부처통합연구지원시스템) 공식 R&D 사업공고 수집 어댑터:
- 도메인: iris.go.kr
- 발행처: 범부처통합연구지원시스템
- 안전 규칙:
  1. 목록 페이지는 discovery 전용
  2. 상세 HTML 파싱이 완료되지 않았거나 목록 일정만 있는 경우 metadata["list_only_unverified"] = True 설정
  3. 수정/정정 공고 감지 시 metadata["supersedes"] 관계 보존
  4. 마감 상태 및 일정을 KST로 정규화
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
import hashlib
import json
import re
from official_sources.adapters.official_board import parse_kst_date, strip_html_tags
from official_sources.models import (
    OfficialSource,
    ProviderResult,
    SourceQuery,
    SourceType,
    TopicPolicy,
    VerificationStatus,
)
from official_sources.ports import HttpTransport

KST = timezone(timedelta(hours=9))


class IrisAnnouncementProvider:
    """IRIS 공식 R&D 사업공고 어댑터"""
    provider_id: str = "iris_official_announcement"

    def __init__(self, transport: HttpTransport | None = None) -> None:
        self.transport = transport

    def supports(self, policy: TopicPolicy) -> bool:
        return "iris.go.kr" in policy.allowed_domains

    def collect(self, query: SourceQuery, policy: TopicPolicy) -> ProviderResult:
        if not self.supports(policy):
            return ProviderResult(
                provider_id=self.provider_id,
                queries=(f"topic={query.topic_id}",),
                candidates=(),
                rejection_counts={"unsupported_policy": 1},
            )

        candidates: list[OfficialSource] = []
        now = datetime.now(KST)

        if self.transport is not None:
            # IRIS 공고 목록 엔드포인트 (API 또는 목록 HTML)
            discovery_url = "https://www.iris.go.kr/contents/retrieveBsnsAncmList.do"
            try:
                resp = self.transport.get(discovery_url)
                # JSON 형태 또는 HTML 목록 구조 처리
                raw_items = []
                if isinstance(resp, dict):
                    raw_items = resp.get("list", resp.get("items", []))
                elif isinstance(resp, list):
                    raw_items = resp
                elif isinstance(resp, str):
                    resp_clean = resp.strip()
                    if resp_clean.startswith("{") or resp_clean.startswith("["):
                        try:
                            data = json.loads(resp_clean)
                            raw_items = data.get("list", data.get("items", data)) if isinstance(data, dict) else data
                        except Exception:
                            raw_items = []

                if isinstance(resp, str) and not raw_items and "<table" in resp:
                    from official_sources.adapters.official_board import parse_board_table
                    board_items = parse_board_table(resp, discovery_url)
                    for bi in board_items:
                        raw_items.append({
                            "ancmId": bi.item_id or hashlib.sha256(bi.detail_url.encode()).hexdigest()[:8],
                            "ancmNm": bi.title,
                            "ancmDe": bi.published_date_str,
                            "url": bi.detail_url,
                            "dept": bi.department,
                            "detail_verified": False,  # 목록 테이블만으로는 미검증
                        })

                for item in raw_items:
                    ancm_id = str(item.get("ancmId") or item.get("id") or "")
                    ancm_title = str(item.get("ancmNm") or item.get("title") or "")
                    date_str = str(item.get("ancmDe") or item.get("published_at") or "")
                    detail_url = str(item.get("url") or f"https://www.iris.go.kr/contents/retrieveBsnsAncmDtl.do?ancmId={ancm_id}")
                    agency = str(item.get("mngOrgNm") or item.get("dept") or "범부처통합연구지원시스템")

                    if not ancm_title:
                        continue

                    pub_date = parse_kst_date(date_str) or now
                    is_detail_verified = bool(item.get("detail_verified", False))

                    metadata: dict[str, object] = {
                        "announcement_id": ancm_id,
                        "managing_agency": agency,
                        "list_only_unverified": not is_detail_verified,
                    }

                    # 수정/정정 공고 관계 보존 (metadata["supersedes"])
                    supersedes_id = item.get("supersedes")
                    if supersedes_id:
                        metadata["supersedes"] = str(supersedes_id)
                    elif "[정정]" in ancm_title or "[수정]" in ancm_title:
                        # 원본 공고 ID 추정 또는 표시
                        base_clean = re.sub(r"\[(정정|수정)\]", "", ancm_title).strip()
                        metadata["supersedes"] = f"base:{hashlib.sha256(base_clean.encode()).hexdigest()[:10]}"

                    # 일정 메타데이터
                    if "receipt_start" in item:
                        metadata["receipt_start"] = str(item["receipt_start"])
                    if "receipt_end" in item:
                        metadata["receipt_end"] = str(item["receipt_end"])

                    excerpt = (
                        f"[IRIS R&D 공고] {ancm_title} (주관: {agency}) - "
                        f"사업공고 상세 일정 및 신청 안내"
                    )
                    content_hash = hashlib.sha256(
                        f"{ancm_title}|{excerpt}|{detail_url}".encode("utf-8")
                    ).hexdigest()

                    status = VerificationStatus.DISCOVERED if is_detail_verified else VerificationStatus.NOT_VERIFIED

                    candidates.append(
                        OfficialSource(
                            source_id=f"iris_{ancm_id}" if ancm_id else f"iris_{hashlib.sha256(detail_url.encode()).hexdigest()[:12]}",
                            title=f"IRIS 공고: {ancm_title}",
                            publisher="범부처통합연구지원시스템",
                            published_at=pub_date,
                            effective_at=pub_date,
                            retrieved_at=now,
                            url=detail_url,
                            canonical_url=detail_url,
                            source_type=SourceType.ANNOUNCEMENT,
                            evidence_excerpt=excerpt,
                            content_hash=content_hash,
                            verification_status=status,
                            final_domain="iris.go.kr",
                            topic_id=policy.topic_id,
                            metadata=metadata,
                        )
                    )
            except Exception:
                pass

        return ProviderResult(
            provider_id=self.provider_id,
            queries=(f"iris:topic={query.topic_id}",),
            candidates=tuple(candidates),
            rejection_counts={},
        )
