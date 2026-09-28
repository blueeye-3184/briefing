"""tests.official_sources.test_service

OfficialEvidenceService의 결손 판정, 중복 제거, 결정론적 정렬 및 Provider 오류 내구성 테스트.
"""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock
import pytest
from official_sources.models import (
    EvidenceStatus,
    OfficialSource,
    ProviderResult,
    SourceQuery,
    SourceType,
    TopicPolicy,
    VerificationStatus,
)
from official_sources.ports import OfficialSourceProvider
from official_sources.registry import TopicPolicyRegistry
from official_sources.service import OfficialEvidenceService
from official_sources.verification import OfficialSourceVerifier

KST = timezone(timedelta(hours=9))


class MockProvider:
    def __init__(
        self,
        provider_id: str,
        supported_domains: tuple[str, ...],
        candidates: tuple[OfficialSource, ...] = (),
        should_fail: bool = False,
    ) -> None:
        self.provider_id = provider_id
        self.supported_domains = supported_domains
        self.candidates = candidates
        self.should_fail = should_fail
        self.call_count = 0

    def supports(self, policy: TopicPolicy) -> bool:
        return any(d in policy.allowed_domains for d in self.supported_domains)

    def collect(self, query: SourceQuery, policy: TopicPolicy) -> ProviderResult:
        self.call_count += 1
        if self.should_fail:
            raise RuntimeError("Provider connection error")
        return ProviderResult(
            provider_id=self.provider_id,
            queries=(f"topic={query.topic_id}",),
            candidates=self.candidates,
        )


def _make_source(
    source_id: str,
    title: str,
    publisher: str,
    domain: str,
    source_type: SourceType,
    published_at: datetime,
    topic_id: str,
    canonical_url: str | None = None,
    list_only_unverified: bool = False,
) -> OfficialSource:
    url = canonical_url or f"https://{domain}/view/{source_id}"
    return OfficialSource(
        source_id=source_id,
        title=title,
        publisher=publisher,
        published_at=published_at,
        effective_at=published_at,
        retrieved_at=published_at,
        url=url,
        canonical_url=url,
        source_type=source_type,
        evidence_excerpt=f"[{publisher}] {title} - 상세 검증 완료 공식 본문 데이터",
        content_hash="mock_content_hash",
        verification_status=VerificationStatus.DISCOVERED,
        final_domain=domain,
        topic_id=topic_id,
        metadata={"list_only_unverified": list_only_unverified},
    )


# --- Monday Deficit & Configuration Tests ---

def test_monday_configuration_deficit():
    # 월요일 정책에 정량 통계 provider가 하나도 없는 경우 (configuration deficit)
    policy = TopicPolicyRegistry.get_by_day(0)
    verifier = OfficialSourceVerifier()

    # 정량 provider 없이 고시공고 provider만 주입
    notice_provider = MockProvider("gumi_official_notice", ("gumi.go.kr",))
    service = OfficialEvidenceService([notice_provider], verifier)

    pack = service.collect(policy, date(2026, 3, 23))
    assert pack.status == EvidenceStatus.SOURCE_DEFICIT
    assert any("configuration_deficit" in d for d in pack.deficits)
    assert len(pack.official_sources) == 0


def test_monday_quantitative_deficit_when_zero_statistics():
    # 총 2건이 있어도 정량 통계가 0건이면 SOURCE_DEFICIT
    policy = TopicPolicyRegistry.get_by_day(0)
    verifier = OfficialSourceVerifier()
    eval_date = date(2026, 3, 23)
    now = datetime(2026, 3, 23, 10, 0, 0, tzinfo=KST)

    # KOSIS provider는 등록되었으나 후보 없음
    kosis_prov = MockProvider("kosis_official_api", ("kosis.kr",), candidates=())
    # 공고/정책 2건 수집
    p1 = _make_source("molit_1", "국토부 보도자료", "국토교통부", "molit.go.kr", SourceType.POLICY, now, policy.topic_id)
    p2 = _make_source("gumi_1", "구미시 고시공고", "구미시", "gumi.go.kr", SourceType.NOTICE, now, policy.topic_id)
    board_prov = MockProvider("board_provider", ("molit.go.kr", "gumi.go.kr"), candidates=(p1, p2))

    service = OfficialEvidenceService([kosis_prov, board_prov], verifier)
    pack = service.collect(policy, eval_date)

    assert pack.status == EvidenceStatus.SOURCE_DEFICIT
    assert any("monday_quantitative_deficit" in d for d in pack.deficits)


def test_monday_ready_with_quant_and_notice():
    # 정량 1건 + 공고 1건 = READY (최소 2건 충족)
    policy = TopicPolicyRegistry.get_by_day(0)
    verifier = OfficialSourceVerifier()
    eval_date = date(2026, 3, 23)
    now = datetime(2026, 3, 23, 10, 0, 0, tzinfo=KST)

    s1 = _make_source("kosis_1", "지가변동률 통계", "통계청", "kosis.kr", SourceType.STATISTICS, now, policy.topic_id)
    s2 = _make_source("gumi_1", "구미시 고시공고", "구미시", "gumi.go.kr", SourceType.NOTICE, now, policy.topic_id)

    kosis_prov = MockProvider("kosis_official_api", ("kosis.kr",), candidates=(s1,))
    gumi_prov = MockProvider("gumi_official_notice", ("gumi.go.kr",), candidates=(s2,))

    service = OfficialEvidenceService([kosis_prov, gumi_prov], verifier)
    pack = service.collect(policy, eval_date)

    assert pack.status == EvidenceStatus.READY
    assert len(pack.deficits) == 0
    assert len(pack.official_sources) == 2


# --- Friday Deficit Tests ---

def test_friday_announcement_detail_deficit():
    # 금요일: 상세 검증 공고가 0건이면 총 2건이어도 SOURCE_DEFICIT
    policy = TopicPolicyRegistry.get_by_day(4)  # Friday architecture R&D
    verifier = OfficialSourceVerifier()
    eval_date = date(2026, 3, 27)
    now = datetime(2026, 3, 27, 10, 0, 0, tzinfo=KST)

    # 1. 안내자료(GUIDANCE) 1건
    g1 = _make_source("iris_guide", "IRIS 신청 가이드", "범부처통합연구지원시스템", "iris.go.kr", SourceType.GUIDANCE, now, policy.topic_id)
    # 2. 목록만 있는 미검증 공고 1건 (list_only_unverified=True)
    a1 = _make_source("iris_ancm", "IRIS R&D 공고", "범부처통합연구지원시스템", "iris.go.kr", SourceType.ANNOUNCEMENT, now, policy.topic_id, list_only_unverified=True)

    iris_prov = MockProvider("iris_official_announcement", ("iris.go.kr",), candidates=(g1, a1))

    service = OfficialEvidenceService([iris_prov], verifier)
    pack = service.collect(policy, eval_date)

    assert pack.status == EvidenceStatus.SOURCE_DEFICIT
    assert any("friday_announcement_detail_deficit" in d for d in pack.deficits)


def test_friday_ready_with_verified_announcements():
    # 금요일: 상세 검증 공고 2건 = READY
    policy = TopicPolicyRegistry.get_by_day(4)
    verifier = OfficialSourceVerifier()
    eval_date = date(2026, 3, 27)
    now = datetime(2026, 3, 27, 10, 0, 0, tzinfo=KST)

    a1 = _make_source("iris_1", "건축 BIM R&D 공고", "범부처통합연구지원시스템", "iris.go.kr", SourceType.ANNOUNCEMENT, now, policy.topic_id, list_only_unverified=False)
    a2 = _make_source("kaia_1", "국토교통 R&D 사업공고", "국토교통과학기술진흥원", "kaia.re.kr", SourceType.ANNOUNCEMENT, now, policy.topic_id, list_only_unverified=False)

    iris_prov = MockProvider("iris_official_announcement", ("iris.go.kr",), candidates=(a1,))
    kaia_prov = MockProvider("kaia_official_announcement", ("kaia.re.kr",), candidates=(a2,))

    service = OfficialEvidenceService([iris_prov, kaia_prov], verifier)
    pack = service.collect(policy, eval_date)

    assert pack.status == EvidenceStatus.READY
    assert len(pack.deficits) == 0
    assert len(pack.official_sources) == 2


# --- Deduplication, Error Tolerance & Deterministic Sorting ---

def test_service_deduplication():
    policy = TopicPolicyRegistry.get_by_day(0)
    verifier = OfficialSourceVerifier()
    eval_date = date(2026, 3, 23)
    now = datetime(2026, 3, 23, 10, 0, 0, tzinfo=KST)

    s1 = _make_source("kosis_1", "지가변동률 통계", "통계청", "kosis.kr", SourceType.STATISTICS, now, policy.topic_id)
    # 동일한 source_id 및 URL을 가진 중복 후보
    s1_dup = _make_source("kosis_1", "지가변동률 통계 중복", "통계청", "kosis.kr", SourceType.STATISTICS, now, policy.topic_id)

    kosis_prov = MockProvider("kosis_official_api", ("kosis.kr",), candidates=(s1, s1_dup))
    service = OfficialEvidenceService([kosis_prov], verifier)

    pack = service.collect(policy, eval_date)
    # 1건만 유지
    assert len(pack.official_sources) == 1


def test_provider_fault_tolerance():
    # 한 provider가 예외를 발생시켜도 다른 provider의 결과는 정상 보존됨
    policy = TopicPolicyRegistry.get_by_day(0)
    verifier = OfficialSourceVerifier()
    eval_date = date(2026, 3, 23)
    now = datetime(2026, 3, 23, 10, 0, 0, tzinfo=KST)

    s1 = _make_source("kosis_1", "지가변동률 통계", "통계청", "kosis.kr", SourceType.STATISTICS, now, policy.topic_id)
    kosis_prov = MockProvider("kosis_official_api", ("kosis.kr",), candidates=(s1,))
    failing_prov = MockProvider("failing_provider", ("molit.go.kr",), should_fail=True)

    service = OfficialEvidenceService([kosis_prov, failing_prov], verifier)
    pack = service.collect(policy, eval_date)

    assert len(pack.provider_results) == 2
    failing_res = next(r for r in pack.provider_results if r.provider_id == "failing_provider")
    assert "provider_schema_error" in failing_res.rejection_counts
    assert len(pack.official_sources) == 1


def test_deterministic_ordering():
    policy = TopicPolicyRegistry.get_by_day(1)  # Tuesday (official_minimum=0)
    verifier = OfficialSourceVerifier()
    eval_date = date(2026, 3, 24)
    t1 = datetime(2026, 3, 20, 10, 0, 0, tzinfo=KST)
    t2 = datetime(2026, 3, 22, 10, 0, 0, tzinfo=KST)

    # 발행일이 다른 출처
    s_older = _make_source("molit_old", "이전 발표", "국토교통부", "molit.go.kr", SourceType.POLICY, t1, policy.topic_id)
    s_newer = _make_source("molit_new", "최신 발표", "국토교통부", "molit.go.kr", SourceType.POLICY, t2, policy.topic_id)

    # 순서를 뒤섞어서 전달
    prov = MockProvider("test_prov", ("molit.go.kr",), candidates=(s_older, s_newer))
    service = OfficialEvidenceService([prov], verifier)

    pack = service.collect(policy, eval_date)
    # 최신순 정렬 확인
    assert pack.official_sources[0].source_id == "molit_new"
    assert pack.official_sources[1].source_id == "molit_old"


# --- Provider Failure vs Genuine-Empty Deficit Tests ---

def test_service_fail_closed_when_all_providers_fail_on_optional_policy():
    policy = TopicPolicyRegistry.get_by_day(1)  # Tuesday (official_minimum=0)
    verifier = OfficialSourceVerifier()
    eval_date = date(2026, 3, 24)

    # 모든 provider가 예외 발생
    failing_prov1 = MockProvider("prov_1", ("molit.go.kr",), should_fail=True)
    failing_prov2 = MockProvider("prov_2", ("data.go.kr",), should_fail=True)

    service = OfficialEvidenceService([failing_prov1, failing_prov2], verifier)
    pack = service.collect(policy, eval_date)

    assert pack.status == EvidenceStatus.SOURCE_DEFICIT
    assert any("provider_failure_deficit" in d for d in pack.deficits)
    assert len(pack.official_sources) == 0


def test_service_fail_closed_when_provider_fails_with_zero_sources_on_optional_policy():
    policy = TopicPolicyRegistry.get_by_day(1)  # Tuesday (official_minimum=0)
    verifier = OfficialSourceVerifier()
    eval_date = date(2026, 3, 24)

    # 하나는 실패하고, 다른 하나는 정상이나 0건 반환 (불완전 수집 상태에서 0건)
    failing_prov = MockProvider("prov_fail", ("molit.go.kr",), should_fail=True)
    empty_prov = MockProvider("prov_empty", ("data.go.kr",), candidates=())

    service = OfficialEvidenceService([failing_prov, empty_prov], verifier)
    pack = service.collect(policy, eval_date)

    assert pack.status == EvidenceStatus.SOURCE_DEFICIT
    assert any("provider_failure_deficit" in d for d in pack.deficits)
    assert len(pack.official_sources) == 0


def test_service_genuine_empty_ready_on_optional_policy():
    policy = TopicPolicyRegistry.get_by_day(1)  # Tuesday (official_minimum=0)
    verifier = OfficialSourceVerifier()
    eval_date = date(2026, 3, 24)

    # 모든 provider가 정상 실행되었으나 검색 결과가 0건인 경우 (정상적인 genuine-empty)
    empty_prov1 = MockProvider("prov_1", ("molit.go.kr",), candidates=())
    empty_prov2 = MockProvider("prov_2", ("data.go.kr",), candidates=())

    service = OfficialEvidenceService([empty_prov1, empty_prov2], verifier)
    pack = service.collect(policy, eval_date)

    assert pack.status == EvidenceStatus.READY
    assert len(pack.deficits) == 0
    assert len(pack.official_sources) == 0


def test_service_configuration_deficit_when_no_supported_providers():
    policy = TopicPolicyRegistry.get_by_day(1)  # Tuesday (allowed: molit.go.kr, etc.)
    verifier = OfficialSourceVerifier()
    eval_date = date(2026, 3, 24)

    # 화요일 도메인을 전혀 지원하지 않는 provider만 주입
    unsupported_prov = MockProvider("unsupported", ("unknown-domain.kr",))

    service = OfficialEvidenceService([unsupported_prov], verifier)
    pack = service.collect(policy, eval_date)

    assert pack.status == EvidenceStatus.SOURCE_DEFICIT
    assert any("configuration_deficit" in d for d in pack.deficits)
