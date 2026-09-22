"""tests.official_sources.test_topic_policies

7요일 정책 정의, 등록부 조회 및 최소 근거 계약 테스트.
"""

import pytest
from official_sources.registry import TopicPolicyRegistry


def test_registry_contains_all_seven_days():
    policies = TopicPolicyRegistry.get_all_policies()
    assert len(policies) == 7

    days = {p.day_of_week for p in policies}
    assert days == {0, 1, 2, 3, 4, 5, 6}


def test_monday_policy_contract():
    policy = TopicPolicyRegistry.get_by_day(0)
    assert policy.day_of_week == 0
    assert policy.topic_id == "real_estate_local_policy"
    assert policy.official_minimum == 2
    assert policy.official_target >= 2
    assert policy.freshness_days == 365

    # 필수 도메인 확인
    required_domains = {"kosis.kr", "reb.or.kr", "data.go.kr", "molit.go.kr", "gumi.go.kr", "gc.go.kr"}
    assert required_domains.issubset(set(policy.allowed_domains))


def test_friday_policy_contract():
    policy = TopicPolicyRegistry.get_by_day(4)
    assert policy.day_of_week == 4
    assert policy.topic_id == "architecture_rnd_calls"
    assert policy.official_minimum == 2
    assert policy.official_target >= 2
    assert policy.freshness_days == 90

    # 필수 도메인 확인
    required_domains = {"iris.go.kr", "kaia.re.kr", "molit.go.kr"}
    assert required_domains.issubset(set(policy.allowed_domains))


def test_tue_wed_thu_sat_sun_policies():
    # 화, 수, 목, 토, 일의 공식 최소치는 0 (선택적)
    for day in (1, 2, 3, 5, 6):
        policy = TopicPolicyRegistry.get_by_day(day)
        assert policy.day_of_week == day
        assert policy.official_minimum == 0


def test_registry_lookup_by_topic_id():
    mon = TopicPolicyRegistry.get_by_topic_id("real_estate_local_policy")
    assert mon is not None
    assert mon.day_of_week == 0

    fri = TopicPolicyRegistry.get_by_topic_id("architecture_rnd_calls")
    assert fri is not None
    assert fri.day_of_week == 4

    unknown = TopicPolicyRegistry.get_by_topic_id("non_existent_topic")
    assert unknown is None


def test_registry_invalid_day():
    with pytest.raises(ValueError):
        TopicPolicyRegistry.get_by_day(7)
    with pytest.raises(ValueError):
        TopicPolicyRegistry.get_by_day(-1)
