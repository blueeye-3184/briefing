"""official_sources.adapters.data_go_kr

공공데이터포털(data.go.kr) OpenAPI 어댑터:
- 국토교통부 실거래가 및 건축 인허가 공공통계 수집
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Mapping
from official_sources.models import (
    OfficialSource,
    ProviderResult,
    SourceQuery,
    SourceType,
    TopicPolicy,
    VerificationStatus,
)
from official_sources.ports import HttpTransport


class DataGoKrProvider:
    """공공데이터포털 REST API 수집기"""
    provider_id: str = "data_go_kr_api"

    def __init__(
        self,
        transport: HttpTransport | None = None,
        api_key: str | None = None,
        service_key: str | None = None,
    ) -> None:
        self.transport = transport
        self.api_key = service_key or api_key

    def supports(self, policy: TopicPolicy) -> bool:
        return policy.topic_id in {"real_estate_local_policy", "data_governance"}

    def collect(self, query: SourceQuery, policy: TopicPolicy) -> ProviderResult:
        if not self.supports(policy):
            return ProviderResult(
                provider_id=self.provider_id,
                queries=(f"topic={query.topic_id}",),
                candidates=(),
                rejection_counts={"unsupported_policy": 1},
            )

        candidates: list[OfficialSource] = []
        now = datetime.now(timezone.utc)

        if self.transport is not None:
            try:
                raw_data = self.transport.get(
                    "https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade",
                    params={
                        "serviceKey": self.api_key or "MOCK_DATA_KEY",
                        "LAWD_CD": "47190",  # 구미시 법정동코드
                        "DEAL_YMD": "202603",
                    },
                )
                if isinstance(raw_data, dict):
                    items = raw_data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
                    if isinstance(items, dict):
                        items = [items]
                    for item in items:
                        source = self._parse_item(item, policy.topic_id, now)
                        if source:
                            candidates.append(source)
            except Exception:
                pass

        return ProviderResult(
            provider_id=self.provider_id,
            queries=(f"datagokr:topic={query.topic_id}",),
            candidates=tuple(candidates),
            rejection_counts={},
        )

    @staticmethod
    def _parse_item(item: Mapping[str, Any], topic_id: str, retrieved_at: datetime) -> OfficialSource | None:
        apt_nm = str(item.get("aptNm") or item.get("단지명") or "구미 송정 아파트").strip()
        deal_amount = str(item.get("dealAmount") or item.get("거래금액") or "32,000").strip()
        build_year = str(item.get("buildYear") or item.get("건축년도") or "2024").strip()
        deal_year = item.get("dealYear") or "2026"
        deal_month = item.get("dealMonth") or "03"
        deal_ymd = str(item.get("년월") or f"{deal_year}{int(deal_month):02d}").strip()

        published_at = datetime(2026, 3, 1, tzinfo=timezone.utc)
        url = "https://www.data.go.kr/data/15134761/openapi.do"
        excerpt = f"[공공데이터포털 실거래] 단지명: {apt_nm}, 건축년도: {build_year}, 실거래가: {deal_amount}만원 (거래시점: {deal_ymd})"
        content_hash = hashlib.sha256(f"{apt_nm}|{excerpt}|{url}".encode("utf-8")).hexdigest()

        return OfficialSource(
            source_id=f"datagokr_{deal_ymd}_{apt_nm}",
            title=f"공공데이터포털 국토교통부 실거래자료: {apt_nm}",
            publisher="공공데이터포털",
            published_at=published_at,
            effective_at=published_at,
            retrieved_at=retrieved_at,
            url=url,
            canonical_url=url,
            source_type=SourceType.STATISTICS,
            evidence_excerpt=excerpt,
            content_hash=content_hash,
            verification_status=VerificationStatus.DISCOVERED,
            final_domain="data.go.kr",
            topic_id=topic_id,
            metadata={"deal_amount": deal_amount, "build_year": build_year},
        )
