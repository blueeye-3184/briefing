"""official_sources.adapters.kaia

KAIA (국토교통과학기술진흥원) 공식 R&D 사업공고 수집 어댑터:
- 도메인: kaia.re.kr
- 발행처: 국토교통과학기술진흥원
- 안전 규칙:
  1. 상세 페이지 검증 여부에 따라 metadata["list_only_unverified"] 처리
  2. 수정공고 감지 시 metadata["supersedes"] 관계 보존
  3. KST 시간 정규화
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
import hashlib
import json
import re
from official_sources.adapters.official_board import parse_kst_date
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


class KaiaAnnouncementProvider:
    """KAIA 공식 국토교통 R&D 사업공고 어댑터"""
    provider_id: str = "kaia_official_announcement"

    def __init__(self, transport: HttpTransport | None = None) -> None:
        self.transport = transport

    def supports(self, policy: TopicPolicy) -> bool:
        return "kaia.re.kr" in policy.allowed_domains

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
            discovery_url = "https://www.kaia.re.kr/portal/sub.do?m=010201"
            try:
                resp = self.transport.get(discovery_url)
                raw_items = []
                if isinstance(resp, dict):
                    raw_items = resp.get("items", resp.get("list", []))
                elif isinstance(resp, list):
                    raw_items = resp
                elif isinstance(resp, str):
                    resp_clean = resp.strip()
                    if resp_clean.startswith("{") or resp_clean.startswith("["):
                        try:
                            data = json.loads(resp_clean)
                            raw_items = data.get("items", data.get("list", data)) if isinstance(data, dict) else data
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
                            "detail_verified": False,
                        })

                for item in raw_items:
                    ancm_id = str(item.get("ancmId") or item.get("id") or "")
                    ancm_title = str(item.get("ancmNm") or item.get("title") or "")
                    date_str = str(item.get("ancmDe") or item.get("published_at") or "")
                    detail_url = str(item.get("url") or f"https://www.kaia.re.kr/portal/view.do?ancmId={ancm_id}")

                    if not ancm_title:
                        continue

                    pub_date = parse_kst_date(date_str) or now
                    is_detail_verified = bool(item.get("detail_verified", False))

                    metadata: dict[str, object] = {
                        "announcement_id": ancm_id,
                        "list_only_unverified": not is_detail_verified,
                    }

                    # 수정/정정 공고 관계 보존
                    supersedes_id = item.get("supersedes")
                    if supersedes_id:
                        metadata["supersedes"] = str(supersedes_id)
                    elif "[정정]" in ancm_title or "[수정]" in ancm_title:
                        base_clean = re.sub(r"\[(정정|수정)\]", "", ancm_title).strip()
                        metadata["supersedes"] = f"base:{hashlib.sha256(base_clean.encode()).hexdigest()[:10]}"

                    excerpt = (
                        f"[KAIA R&D 사업공고] {ancm_title} - "
                        f"국토교통 R&D 사업 상세 지원내용 및 제안서 접수 안내"
                    )
                    content_hash = hashlib.sha256(
                        f"{ancm_title}|{excerpt}|{detail_url}".encode("utf-8")
                    ).hexdigest()

                    status = VerificationStatus.DISCOVERED if is_detail_verified else VerificationStatus.NOT_VERIFIED

                    candidates.append(
                        OfficialSource(
                            source_id=f"kaia_{ancm_id}" if ancm_id else f"kaia_{hashlib.sha256(detail_url.encode()).hexdigest()[:12]}",
                            title=f"KAIA 공고: {ancm_title}",
                            publisher="국토교통과학기술진흥원",
                            published_at=pub_date,
                            effective_at=pub_date,
                            retrieved_at=now,
                            url=detail_url,
                            canonical_url=detail_url,
                            source_type=SourceType.ANNOUNCEMENT,
                            evidence_excerpt=excerpt,
                            content_hash=content_hash,
                            verification_status=status,
                            final_domain="kaia.re.kr",
                            topic_id=policy.topic_id,
                            metadata=metadata,
                        )
                    )
            except Exception:
                pass

        return ProviderResult(
            provider_id=self.provider_id,
            queries=(f"kaia:topic={query.topic_id}",),
            candidates=tuple(candidates),
            rejection_counts={},
        )
