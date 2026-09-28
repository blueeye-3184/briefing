"""official_sources.adapters.gumi

구미시 공식 고시공고 수집 어댑터:
- 도메인: gumi.go.kr
- 발행처: 구미시
- 유형: SourceType.NOTICE
- 정해진 고시공고 목록 테이블 파싱
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
import hashlib
from official_sources.adapters.official_board import parse_board_table, parse_kst_date
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


class GumiNoticeProvider:
    """구미시 고시공고 공식 수집 어댑터"""
    provider_id: str = "gumi_official_notice"

    def __init__(self, transport: HttpTransport | None = None) -> None:
        self.transport = transport

    def supports(self, policy: TopicPolicy) -> bool:
        return "gumi.go.kr" in policy.allowed_domains

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
            list_url = "https://www.gumi.go.kr/portal/saeol/gosiList.do"
            try:
                resp = self.transport.get(list_url)
                if isinstance(resp, str) and "<table" in resp:
                    items = parse_board_table(resp, list_url)
                    for item in items:
                        pub_date = parse_kst_date(item.published_date_str) or now
                        source_id = (
                            f"gumi_notice_{item.item_id}"
                            if item.item_id and item.item_id.isalnum()
                            else f"gumi_{hashlib.sha256(item.detail_url.encode('utf-8')).hexdigest()[:12]}"
                        )
                        title = f"구미시 고시공고: {item.title}"
                        excerpt = (
                            f"[구미시 고시공고] {item.title} "
                            f"(담당: {item.department or '구미시청'}) - 행정/도시/부동산 관련 공고 원문"
                        )
                        content_hash = hashlib.sha256(
                            f"{title}|{excerpt}|{item.detail_url}".encode("utf-8")
                        ).hexdigest()

                        candidates.append(
                            OfficialSource(
                                source_id=source_id,
                                title=title,
                                publisher="구미시",
                                published_at=pub_date,
                                effective_at=pub_date,
                                retrieved_at=now,
                                url=item.detail_url,
                                canonical_url=item.detail_url,
                                source_type=SourceType.NOTICE,
                                evidence_excerpt=excerpt,
                                content_hash=content_hash,
                                verification_status=VerificationStatus.DISCOVERED,
                                final_domain="gumi.go.kr",
                                topic_id=policy.topic_id,
                                metadata={
                                    "department": item.department,
                                    "notice_no": item.item_id,
                                },
                            )
                        )
            except Exception:
                pass

        return ProviderResult(
            provider_id=self.provider_id,
            queries=(f"gumi:topic={query.topic_id}",),
            candidates=tuple(candidates),
            rejection_counts={},
        )
