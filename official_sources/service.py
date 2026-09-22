"""official_sources.service

공식 1차 자료 수집 서비스(OfficialEvidenceService):
- Provider 호출 및 결과 집계
- Verifier를 통한 정합성/보안/규격 검증
- Canonical URL 및 Source ID 기준 중복 제거
- 요일별/정책별 최소 및 필수 구성(정량, 상세공고) 검사
- READY 또는 SOURCE_DEFICIT 상태 결정론적 판정
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Sequence
from official_sources.models import (
    EvidencePack,
    EvidenceStatus,
    OfficialSource,
    ProviderResult,
    SourceQuery,
    SourceType,
    TopicPolicy,
    VerificationStatus,
)
from official_sources.ports import OfficialSourceProvider
from official_sources.verification import OfficialSourceVerifier

KST = timezone(timedelta(hours=9))


class OfficialEvidenceService:
    """공식 1차 출처 수집 및 검증 총괄 서비스"""

    def __init__(
        self,
        providers: Sequence[OfficialSourceProvider],
        verifier: OfficialSourceVerifier,
    ) -> None:
        self._providers = tuple(providers)
        self._verifier = verifier

    def collect(self, policy: TopicPolicy, run_date_kst: date) -> EvidencePack:
        """주어진 정책과 KST 기준일에 따라 공식 자료를 수집·검증하고 EvidencePack 생성"""
        eval_time = datetime(
            run_date_kst.year,
            run_date_kst.month,
            run_date_kst.day,
            12,
            0,
            0,
            tzinfo=KST,
        )

        # 1. 월요일 정량 provider 설정 결손(configuration deficit) 사전 검사
        is_monday = policy.day_of_week == 0 or policy.topic_id == "real_estate_local_policy"
        if is_monday:
            quant_provider_ids = {"kosis_official_api", "reb_rone_api", "data_go_kr_api"}
            has_quant_provider = any(
                p.supports(policy) and getattr(p, "provider_id", "") in quant_provider_ids
                for p in self._providers
            )
            if not has_quant_provider:
                return EvidencePack(
                    topic_id=policy.topic_id,
                    official_sources=(),
                    provider_results=(),
                    status=EvidenceStatus.SOURCE_DEFICIT,
                    deficits=(
                        "configuration_deficit: no quantitative statistics provider configured for monday policy",
                    ),
                    collected_at=eval_time,
                )

        # 2. 질의(SourceQuery) 생성
        start_date = (
            run_date_kst - timedelta(days=policy.freshness_days)
            if policy.freshness_days > 0
            else run_date_kst
        )
        query = SourceQuery(
            topic_id=policy.topic_id,
            keywords=policy.required_keywords,
            start_date=start_date,
            end_date=run_date_kst,
            region_codes=("47190", "47150") if is_monday else (),
            limit=20,
        )

        # 3. Provider 호출 및 후보군 수집 (개별 실패 허용)
        provider_results: list[ProviderResult] = []
        raw_candidates: list[OfficialSource] = []

        for provider in self._providers:
            if not provider.supports(policy):
                continue
            try:
                res = provider.collect(query, policy)
                provider_results.append(res)
                raw_candidates.extend(res.candidates)
            except Exception as exc:
                provider_results.append(
                    ProviderResult(
                        provider_id=getattr(provider, "provider_id", "unknown_provider"),
                        queries=(f"error: {type(exc).__name__}",),
                        candidates=(),
                        rejection_counts={"provider_schema_error": 1},
                    )
                )

        # 4. 검증 및 중복 제거
        seen_source_ids: set[str] = set()
        seen_canonical_urls: set[str] = set()
        verified_sources: list[OfficialSource] = []

        for candidate in raw_candidates:
            # Canonical URL 정규화
            canon = candidate.canonical_url.strip().rstrip("/")

            # 중복 검사
            if candidate.source_id in seen_source_ids or canon in seen_canonical_urls:
                continue

            # 게이트웨이 검증
            verified_cand, reason = self._verifier.verify(
                candidate, policy, evaluation_time=eval_time
            )
            if reason is not None or verified_cand.verification_status != VerificationStatus.VERIFIED:
                continue

            seen_source_ids.add(verified_cand.source_id)
            seen_canonical_urls.add(canon)
            verified_sources.append(verified_cand)

        # 5. 결정론적 정렬 (발행일 최신순, source_id 오름차순)
        verified_sources.sort(
            key=lambda s: (-s.published_at.timestamp(), s.source_id, s.title)
        )

        # 6. 정책별 최소 요건 및 구성 결손(Deficit) 판정
        deficits: list[str] = []

        if len(verified_sources) < policy.official_minimum:
            deficits.append(
                f"minimum_count_deficit: verified official sources {len(verified_sources)} < required minimum {policy.official_minimum}"
            )

        if is_monday:
            # 월요일: 정량 API(SourceType.STATISTICS) 최소 1건 필수
            stats_count = sum(1 for s in verified_sources if s.source_type == SourceType.STATISTICS)
            if stats_count == 0:
                deficits.append(
                    "monday_quantitative_deficit: at least 1 verified quantitative statistics source required"
                )

        is_friday = policy.day_of_week == 4 or policy.topic_id == "architecture_rnd_calls"
        if is_friday:
            # 금요일: 상세 검증 공고(SourceType.ANNOUNCEMENT) 최소 1건 필수
            detailed_announcements = [
                s for s in verified_sources
                if s.source_type == SourceType.ANNOUNCEMENT
                and not s.metadata.get("list_only_unverified", False)
            ]
            if len(detailed_announcements) == 0:
                deficits.append(
                    "friday_announcement_detail_deficit: at least 1 verified detailed announcement required"
                )

        status = EvidenceStatus.SOURCE_DEFICIT if deficits else EvidenceStatus.READY

        return EvidencePack(
            topic_id=policy.topic_id,
            official_sources=tuple(verified_sources),
            provider_results=tuple(provider_results),
            status=status,
            deficits=tuple(deficits),
            collected_at=eval_time,
        )
