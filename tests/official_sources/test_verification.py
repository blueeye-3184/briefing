"""tests.official_sources.test_verification

공식 1차 자료 검증 게이트(OfficialSourceVerifier) 및 Rejection Code 단위 테스트.
"""

from datetime import datetime, timedelta, timezone
from official_sources.models import (
    OfficialSource,
    SourceType,
    TopicPolicy,
    VerificationStatus,
)
from official_sources.verification import OfficialSourceVerifier, calculate_content_hash

KST = timezone(timedelta(hours=9))


def _sample_policy() -> TopicPolicy:
    return TopicPolicy(
        topic_id="real_estate_local_policy",
        day_of_week=0,
        title="월요일 부동산",
        subtopics=("지가변동률",),
        academic_target=5,
        academic_minimum=2,
        official_target=2,
        official_minimum=2,
        freshness_days=90,
        allowed_domains=("kosis.kr", "reb.or.kr", "molit.go.kr", "gumi.go.kr", "gc.go.kr"),
        required_keywords=("부동산",),
    )


def _valid_source(eval_time: datetime) -> OfficialSource:
    pub_date = eval_time - timedelta(days=10)
    url = "https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1ML0001"
    excerpt = "2026년 3월 경북 구미시 지가변동률 0.15% 상승 기록 공식 통계 데이터"
    return OfficialSource(
        source_id="kosis_101_DT_1ML0001",
        title="행정구역별 지가변동률",
        publisher="통계청",
        published_at=pub_date,
        effective_at=pub_date,
        retrieved_at=eval_time,
        url=url,
        canonical_url=url,
        source_type=SourceType.STATISTICS,
        evidence_excerpt=excerpt,
        content_hash=calculate_content_hash("행정구역별 지가변동률", excerpt, url),
        verification_status=VerificationStatus.DISCOVERED,
        final_domain="kosis.kr",
        topic_id="real_estate_local_policy",
    )


def test_valid_source_passes():
    verifier = OfficialSourceVerifier()
    eval_time = datetime(2026, 3, 22, 12, 0, 0, tzinfo=KST)
    policy = _sample_policy()
    source = _valid_source(eval_time)

    verified, reason = verifier.verify(source, policy, evaluation_time=eval_time)
    assert reason is None
    assert verified.verification_status == VerificationStatus.VERIFIED


def test_missing_required_field():
    verifier = OfficialSourceVerifier()
    eval_time = datetime(2026, 3, 22, 12, 0, 0, tzinfo=KST)
    policy = _sample_policy()

    # 빈 title
    source = OfficialSource(
        source_id="id1",
        title="",
        publisher="통계청",
        published_at=eval_time,
        effective_at=eval_time,
        retrieved_at=eval_time,
        url="https://kosis.kr/test",
        canonical_url="https://kosis.kr/test",
        source_type=SourceType.STATISTICS,
        evidence_excerpt="유효한 발췌 데이터입니다.",
        content_hash="hash",
        verification_status=VerificationStatus.DISCOVERED,
        final_domain="kosis.kr",
        topic_id="real_estate_local_policy",
    )
    res, reason = verifier.verify(source, policy, evaluation_time=eval_time)
    assert reason == "missing_required_field"
    assert res.verification_status == VerificationStatus.REJECTED


def test_non_https_url():
    verifier = OfficialSourceVerifier()
    eval_time = datetime(2026, 3, 22, 12, 0, 0, tzinfo=KST)
    policy = _sample_policy()

    source = _valid_source(eval_time)
    http_source = OfficialSource(
        source_id=source.source_id,
        title=source.title,
        publisher=source.publisher,
        published_at=source.published_at,
        effective_at=source.effective_at,
        retrieved_at=source.retrieved_at,
        url="http://kosis.kr/insecure",
        canonical_url="http://kosis.kr/insecure",
        source_type=source.source_type,
        evidence_excerpt=source.evidence_excerpt,
        content_hash=source.content_hash,
        verification_status=source.verification_status,
        final_domain=source.final_domain,
        topic_id=source.topic_id,
    )
    res, reason = verifier.verify(http_source, policy, evaluation_time=eval_time)
    assert reason == "non_https_url"
    assert res.verification_status == VerificationStatus.REJECTED


def test_disallowed_domain_and_suffix_attack_prevention():
    verifier = OfficialSourceVerifier()
    eval_time = datetime(2026, 3, 22, 12, 0, 0, tzinfo=KST)
    policy = _sample_policy()

    # 1. 완전 미허용 도메인
    bad_domain_source = OfficialSource(
        source_id="bad1",
        title="임의 블로그",
        publisher="통계청",
        published_at=eval_time,
        effective_at=eval_time,
        retrieved_at=eval_time,
        url="https://evil.com/fake-stats",
        canonical_url="https://evil.com/fake-stats",
        source_type=SourceType.STATISTICS,
        evidence_excerpt="허위 통계 데이터입니다.",
        content_hash="hash",
        verification_status=VerificationStatus.DISCOVERED,
        final_domain="evil.com",
        topic_id="real_estate_local_policy",
    )
    res, reason = verifier.verify(bad_domain_source, policy, evaluation_time=eval_time)
    assert reason == "disallowed_domain"

    # 2. 도메인 Suffix 공격 시도 (kosis.kr.attacker.com)
    attacker_source = OfficialSource(
        source_id="bad2",
        title="위조 KOSIS 통계",
        publisher="통계청",
        published_at=eval_time,
        effective_at=eval_time,
        retrieved_at=eval_time,
        url="https://kosis.kr.attacker.com/data",
        canonical_url="https://kosis.kr.attacker.com/data",
        source_type=SourceType.STATISTICS,
        evidence_excerpt="공격자 사이트의 위조 데이터입니다.",
        content_hash="hash",
        verification_status=VerificationStatus.DISCOVERED,
        final_domain="kosis.kr.attacker.com",
        topic_id="real_estate_local_policy",
    )
    res, reason = verifier.verify(attacker_source, policy, evaluation_time=eval_time)
    assert reason == "disallowed_domain"


def test_publisher_domain_mismatch():
    verifier = OfficialSourceVerifier()
    eval_time = datetime(2026, 3, 22, 12, 0, 0, tzinfo=KST)
    policy = _sample_policy()

    # kosis.kr 도메인인데 publisher가 "사설부동산블로그"
    mismatch_source = OfficialSource(
        source_id="mis1",
        title="지가변동률 분석",
        publisher="사설부동산블로그",
        published_at=eval_time - timedelta(days=5),
        effective_at=eval_time - timedelta(days=5),
        retrieved_at=eval_time,
        url="https://kosis.kr/statHtml",
        canonical_url="https://kosis.kr/statHtml",
        source_type=SourceType.STATISTICS,
        evidence_excerpt="통계청 출처라고 주장하는 블로그 요약",
        content_hash="hash",
        verification_status=VerificationStatus.DISCOVERED,
        final_domain="kosis.kr",
        topic_id="real_estate_local_policy",
    )
    res, reason = verifier.verify(mismatch_source, policy, evaluation_time=eval_time)
    assert reason == "publisher_domain_mismatch"


def test_gumi_and_gimcheon_publisher():
    verifier = OfficialSourceVerifier()
    eval_time = datetime(2026, 3, 22, 12, 0, 0, tzinfo=KST)
    policy = _sample_policy()

    # 구미시 통과
    gumi_source = OfficialSource(
        source_id="gumi_1",
        title="구미시 고시공고 제2026-101호",
        publisher="구미시",
        published_at=eval_time - timedelta(days=2),
        effective_at=eval_time - timedelta(days=2),
        retrieved_at=eval_time,
        url="https://www.gumi.go.kr/portal/saeol/gosiView.do",
        canonical_url="https://www.gumi.go.kr/portal/saeol/gosiView.do",
        source_type=SourceType.NOTICE,
        evidence_excerpt="구미시 도시관리계획 결정 고시 본문 내용입니다.",
        content_hash="hash",
        verification_status=VerificationStatus.DISCOVERED,
        final_domain="gumi.go.kr",
        topic_id="real_estate_local_policy",
    )
    res, reason = verifier.verify(gumi_source, policy, evaluation_time=eval_time)
    assert reason is None
    assert res.verification_status == VerificationStatus.VERIFIED

    # 김천시 통과
    gc_source = OfficialSource(
        source_id="gc_1",
        title="김천시 고시공고 제2026-202호",
        publisher="김천시청",
        published_at=eval_time - timedelta(days=3),
        effective_at=eval_time - timedelta(days=3),
        retrieved_at=eval_time,
        url="https://www.gc.go.kr/portal/saeol/gosiView.do",
        canonical_url="https://www.gc.go.kr/portal/saeol/gosiView.do",
        source_type=SourceType.NOTICE,
        evidence_excerpt="김천시 건축정비구역 지정 공고 내용입니다.",
        content_hash="hash",
        verification_status=VerificationStatus.DISCOVERED,
        final_domain="gc.go.kr",
        topic_id="real_estate_local_policy",
    )
    res, reason = verifier.verify(gc_source, policy, evaluation_time=eval_time)
    assert reason is None
    assert res.verification_status == VerificationStatus.VERIFIED


def test_future_and_stale_dates():
    verifier = OfficialSourceVerifier()
    eval_time = datetime(2026, 3, 22, 12, 0, 0, tzinfo=KST)
    policy = _sample_policy()

    base = _valid_source(eval_time)

    # 1. 미래 날짜
    future_source = OfficialSource(
        source_id=base.source_id,
        title=base.title,
        publisher=base.publisher,
        published_at=eval_time + timedelta(days=5),
        effective_at=eval_time + timedelta(days=5),
        retrieved_at=eval_time,
        url=base.url,
        canonical_url=base.canonical_url,
        source_type=base.source_type,
        evidence_excerpt=base.evidence_excerpt,
        content_hash=base.content_hash,
        verification_status=base.verification_status,
        final_domain=base.final_domain,
        topic_id=base.topic_id,
    )
    res, reason = verifier.verify(future_source, policy, evaluation_time=eval_time)
    assert reason == "future_published_at"

    # 2. 만료된 오래된 자료 (freshness_days = 90)
    stale_source = OfficialSource(
        source_id=base.source_id,
        title=base.title,
        publisher=base.publisher,
        published_at=eval_time - timedelta(days=120),
        effective_at=eval_time - timedelta(days=120),
        retrieved_at=eval_time,
        url=base.url,
        canonical_url=base.canonical_url,
        source_type=base.source_type,
        evidence_excerpt=base.evidence_excerpt,
        content_hash=base.content_hash,
        verification_status=base.verification_status,
        final_domain=base.final_domain,
        topic_id=base.topic_id,
    )
    res, reason = verifier.verify(stale_source, policy, evaluation_time=eval_time)
    assert reason == "stale_source"


def test_missing_evidence_excerpt():
    verifier = OfficialSourceVerifier()
    eval_time = datetime(2026, 3, 22, 12, 0, 0, tzinfo=KST)
    policy = _sample_policy()
    base = _valid_source(eval_time)

    short_source = OfficialSource(
        source_id=base.source_id,
        title=base.title,
        publisher=base.publisher,
        published_at=base.published_at,
        effective_at=base.effective_at,
        retrieved_at=base.retrieved_at,
        url=base.url,
        canonical_url=base.canonical_url,
        source_type=base.source_type,
        evidence_excerpt="짧음",  # < 10 chars
        content_hash=base.content_hash,
        verification_status=base.verification_status,
        final_domain=base.final_domain,
        topic_id=base.topic_id,
    )
    res, reason = verifier.verify(short_source, policy, evaluation_time=eval_time)
    assert reason == "missing_evidence_excerpt"


def test_announcement_detail_unverified_flag():
    verifier = OfficialSourceVerifier()
    eval_time = datetime(2026, 3, 22, 12, 0, 0, tzinfo=KST)
    fri_policy = TopicPolicy(
        topic_id="architecture_rnd_calls",
        day_of_week=4,
        title="금요일 R&D",
        subtopics=("국책과제",),
        academic_target=5,
        academic_minimum=2,
        official_target=2,
        official_minimum=2,
        freshness_days=60,
        allowed_domains=("iris.go.kr", "kaia.re.kr"),
        required_keywords=("R&D",),
    )

    unverified_announcement = OfficialSource(
        source_id="iris_01",
        title="IRIS R&D 신규과제",
        publisher="범부처통합연구지원시스템",
        published_at=eval_time - timedelta(days=2),
        effective_at=eval_time - timedelta(days=2),
        retrieved_at=eval_time,
        url="https://www.iris.go.kr/detail",
        canonical_url="https://www.iris.go.kr/detail",
        source_type=SourceType.ANNOUNCEMENT,
        evidence_excerpt="상세 HTML 일정이 확인되지 않은 목록 데이터",
        content_hash="hash",
        verification_status=VerificationStatus.NOT_VERIFIED,
        final_domain="iris.go.kr",
        topic_id="architecture_rnd_calls",
        metadata={"list_only_unverified": True},
    )

    res, reason = verifier.verify(unverified_announcement, fri_policy, evaluation_time=eval_time)
    assert reason == "announcement_detail_unverified"
    assert res.verification_status == VerificationStatus.REJECTED


def test_content_hash_determinism():
    h1 = calculate_content_hash("제목A", "발췌문A", "https://kosis.kr/1")
    h2 = calculate_content_hash("제목A", "발췌문A", "https://kosis.kr/1")
    h3 = calculate_content_hash("제목B", "발췌문A", "https://kosis.kr/1")

    assert h1 == h2
    assert h1 != h3
    assert len(h1) == 64  # sha256 hex string
