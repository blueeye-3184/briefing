"""tests.official_sources.test_models

도메인 모델 불변성, Enum 값 및 필드 유효성 테스트.
"""

from datetime import date, datetime, timezone
import pytest
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


def test_source_type_values():
    assert SourceType.STATISTICS.value == "statistics"
    assert SourceType.POLICY.value == "policy"
    assert SourceType.NOTICE.value == "notice"
    assert SourceType.ANNOUNCEMENT.value == "announcement"
    assert SourceType.GUIDANCE.value == "guidance"


def test_verification_status_values():
    assert VerificationStatus.DISCOVERED.value == "discovered"
    assert VerificationStatus.VERIFIED.value == "verified"
    assert VerificationStatus.REJECTED.value == "rejected"
    assert VerificationStatus.NOT_VERIFIED.value == "not_verified"


def test_evidence_status_values():
    assert EvidenceStatus.READY.value == "ready"
    assert EvidenceStatus.SOURCE_DEFICIT.value == "source_deficit"


def test_official_source_immutability():
    now = datetime.now(timezone.utc)
    src = OfficialSource(
        source_id="test_01",
        title="테스트 출처",
        publisher="통계청",
        published_at=now,
        effective_at=now,
        retrieved_at=now,
        url="https://kosis.kr/test",
        canonical_url="https://kosis.kr/test",
        source_type=SourceType.STATISTICS,
        evidence_excerpt="테스트 통계 데이터 발췌록입니다.",
        content_hash="abc123hash",
        verification_status=VerificationStatus.VERIFIED,
        final_domain="kosis.kr",
        topic_id="real_estate_local_policy",
        metadata={"key": "val"},
    )

    assert src.source_id == "test_01"
    assert src.source_type == SourceType.STATISTICS
    assert src.metadata["key"] == "val"

    # 불변(frozen) 확인
    with pytest.raises(AttributeError):
        src.title = "수정 시도"  # type: ignore


def test_topic_policy_model():
    pol = TopicPolicy(
        topic_id="test_topic",
        day_of_week=0,
        title="월요일 주제",
        subtopics=("하위1", "하위2"),
        academic_target=5,
        academic_minimum=2,
        official_target=2,
        official_minimum=2,
        freshness_days=90,
        allowed_domains=("kosis.kr", "molit.go.kr"),
        required_keywords=("부동산",),
    )

    assert pol.topic_id == "test_topic"
    assert pol.official_minimum == 2
    assert "kosis.kr" in pol.allowed_domains


def test_source_query_and_provider_result():
    q = SourceQuery(
        topic_id="real_estate",
        keywords=("부동산", "지가"),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 3, 20),
        limit=10,
    )
    assert q.topic_id == "real_estate"
    assert q.limit == 10

    res = ProviderResult(
        provider_id="mock_provider",
        queries=("query1",),
        candidates=(),
        rejection_counts={"stale": 2},
    )
    assert res.provider_id == "mock_provider"
    assert res.rejection_counts["stale"] == 2


def test_evidence_pack():
    now = datetime.now(timezone.utc)
    pack = EvidencePack(
        topic_id="test_topic",
        official_sources=(),
        provider_results=(),
        status=EvidenceStatus.SOURCE_DEFICIT,
        deficits=("test_deficit",),
        collected_at=now,
    )
    assert pack.status == EvidenceStatus.SOURCE_DEFICIT
    assert "test_deficit" in pack.deficits
