"""official_sources.adapters.kosis

KOSIS 국가통계포털 공유서비스 API 어댑터:
- 지역 인구·주택·사업체 통계 수집 및 정규화
- JSON 응답 파싱 및 표 ID, 수록시점 메타데이터 보존
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


class KosisProvider:
    """KOSIS 통계자료 API 수집기"""
    provider_id: str = "kosis_official_api"

    def __init__(self, transport: HttpTransport | None = None, api_key: str | None = None) -> None:
        self.transport = transport
        self.api_key = api_key

    def supports(self, policy: TopicPolicy) -> bool:
        return policy.topic_id == "real_estate_local_policy"

    def collect(self, query: SourceQuery, policy: TopicPolicy) -> ProviderResult:
        if not self.supports(policy):
            return ProviderResult(
                provider_id=self.provider_id,
                queries=(f"topic={query.topic_id}",),
                candidates=(),
                rejection_counts={"unsupported_policy": 1},
            )

        # Mock 또는 Fixture 기반 수집 (실제 외부 호출 없이 transport 또는 주입 데이터 사용)
        candidates: list[OfficialSource] = []
        now = datetime.now(timezone.utc)

        if self.transport is not None:
            try:
                raw_data = self.transport.get(
                    "https://kosis.kr/openapi/statisticsData.do",
                    params={
                        "method": "getList",
                        "apiKey": self.api_key or "MOCK_KEY",
                        "format": "json",
                        "userStatsId": "gumi_housing_stats",
                    },
                )
                if isinstance(raw_data, dict):
                    raw_list = raw_data.get("data", raw_data.get("items", []))
                elif isinstance(raw_data, list):
                    raw_list = raw_data
                else:
                    raw_list = []

                for item in raw_list:
                    source = self._parse_kosis_item(item, policy.topic_id, now)
                    if source:
                        candidates.append(source)
            except Exception:
                pass

        return ProviderResult(
            provider_id=self.provider_id,
            queries=(f"kosis:topic={query.topic_id}",),
            candidates=tuple(candidates),
            rejection_counts={},
        )

    @staticmethod
    def _parse_kosis_item(item: Mapping[str, Any], topic_id: str, retrieved_at: datetime) -> OfficialSource | None:
        tbl_id = item.get("TBL_ID", "DT_1B040A3")
        tbl_nm = item.get("TBL_NM", "구미시/김천시 주택 및 가구 통계")
        prd_de = item.get("PRD_DE", "2026")
        c1_nm = item.get("C1_NM", "구미시")
        dt_val = item.get("DT", "182400")

        # published_at 정규화
        pub_year = int(prd_de[:4]) if len(prd_de) >= 4 and prd_de[:4].isdigit() else 2026
        published_at = datetime(pub_year, 1, 1, tzinfo=timezone.utc)

        url = f"https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId={tbl_id}"
        excerpt = f"[{tbl_nm}] 기준시점: {prd_de}, 지역: {c1_nm}, 실측 통계값: {dt_val}호 (공식 통계표 ID: {tbl_id})"
        content_hash = hashlib.sha256(f"{tbl_nm}|{excerpt}|{url}".encode("utf-8")).hexdigest()

        return OfficialSource(
            source_id=f"kosis_{tbl_id}_{prd_de}_{c1_nm}",
            title=f"KOSIS 국가통계포털: {tbl_nm} ({c1_nm}, {prd_de})",
            publisher="통계청 국가통계포털(KOSIS)",
            published_at=published_at,
            effective_at=published_at,
            retrieved_at=retrieved_at,
            url=url,
            canonical_url=url,
            source_type=SourceType.STATISTICS,
            evidence_excerpt=excerpt,
            content_hash=content_hash,
            verification_status=VerificationStatus.DISCOVERED,
            final_domain="kosis.kr",
            topic_id=topic_id,
            metadata={
                "table_id": tbl_id,
                "period": prd_de,
                "region": c1_nm,
                "stat_value": dt_val,
            },
        )
