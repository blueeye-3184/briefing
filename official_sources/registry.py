"""official_sources.registry

7대 요일별 TopicPolicy Registry 정의.
Codex P0-4 명세(§8 TopicPolicy 최소 계약)를 구현합니다.
"""

from __future__ import annotations

from official_sources.models import TopicPolicy

POLICIES: dict[int, TopicPolicy] = {
    0: TopicPolicy(
        topic_id="real_estate_local_policy",
        day_of_week=0,
        title="구미/김천 지역 부동산 정책 및 시장 흐름 분석",
        subtopics=("구미/김천 부동산 시장", "지역 주택 정책", "부동산 통계"),
        academic_target=3,
        academic_minimum=1,
        official_target=3,
        official_minimum=2,
        freshness_days=365,
        allowed_domains=(
            "kosis.kr",
            "reb.or.kr",
            "data.go.kr",
            "molit.go.kr",
            "gumi.go.kr",
            "gc.go.kr",
            "gb.go.kr",
        ),
        required_keywords=("부동산", "주택", "지가", "거래", "정책", "통계"),
        excluded_keywords=(),
        required_sections=("정량통계", "지역정책"),
        deficit_scope="월요일 정책: 정량 통계 API(KOSIS/R-ONE) 최소 1건 및 지자체/국토부 공식자료 최소 1건 필수",
    ),
    1: TopicPolicy(
        topic_id="low_carbon_materials",
        day_of_week=1,
        title="친환경 건축 기술 (목조 건축, 현대 황토 건축) 최신 트렌드",
        subtopics=("친환경 목조 건축", "현대 황토 건축", "탄소중립 건축 기준"),
        academic_target=3,
        academic_minimum=1,
        official_target=1,
        official_minimum=0,
        freshness_days=730,
        allowed_domains=("molit.go.kr", "kict.re.kr", "me.go.kr", "data.go.kr"),
        required_keywords=("친환경", "목조", "황토", "건축기준", "녹색건축"),
        deficit_scope="화요일 정책: 학술 논문 중심, 공식 기준·인증 보조",
    ),
    2: TopicPolicy(
        topic_id="bim_ai_automation",
        day_of_week=2,
        title="설계 자동화 기술 및 BIM (Building Information Modeling) 최신 동향",
        subtopics=("BIM 설계 자동화", "생성형 AI 건축설계", "스마트 건설 기준"),
        academic_target=3,
        academic_minimum=1,
        official_target=1,
        official_minimum=0,
        freshness_days=730,
        allowed_domains=("molit.go.kr", "kaia.re.kr", "kict.re.kr", "data.go.kr"),
        required_keywords=("BIM", "설계자동화", "스마트건설", "표준"),
        deficit_scope="수요일 정책: 학술 논문 중심, 국가 BIM 표준 보조",
    ),
    3: TopicPolicy(
        topic_id="landscape_resilience",
        day_of_week=3,
        title="최신 조경 디자인 및 외부 공간 설계 트렌드",
        subtopics=("도시 조경 디자인", "기후적응 외부공간", "공공 공간 설계기준"),
        academic_target=3,
        academic_minimum=1,
        official_target=1,
        official_minimum=0,
        freshness_days=730,
        allowed_domains=("molit.go.kr", "lh.or.kr", "me.go.kr"),
        required_keywords=("조경", "외부공간", "도시숲", "설계지침"),
        deficit_scope="목요일 정책: 학술 논문 중심, 공공 디자인 지침 보조",
    ),
    4: TopicPolicy(
        topic_id="architecture_rnd_calls",
        day_of_week=4,
        title="건축 관련 R&D 국책 과제 및 IRIS 공모전 동향",
        subtopics=("국토교통 R&D 사업공고", "범부처 IRIS 지원사업", "건축 정책 과제"),
        academic_target=3,
        academic_minimum=1,
        official_target=3,
        official_minimum=2,
        freshness_days=90,  # 공고는 90일 이내의 높은 최신성 요구
        allowed_domains=("iris.go.kr", "kaia.re.kr", "molit.go.kr", "ntis.go.kr"),
        required_keywords=("R&D", "공고", "과제", "사업", "연구", "공모"),
        required_sections=("상세공고", "접수일정"),
        deficit_scope="금요일 정책: 상세 페이지가 검증된 국책 R&D 공고 최소 2건(또는 공고 1건+안내자료 1건) 필수",
    ),
    5: TopicPolicy(
        topic_id="practice_management",
        day_of_week=5,
        title="건축사사무소 운영 시스템 효율화 방안",
        subtopics=("건축사 실무 프로세스", "사무소 경영 효율화", "건축사법 및 표준계약"),
        academic_target=3,
        academic_minimum=1,
        official_target=1,
        official_minimum=0,
        freshness_days=730,
        allowed_domains=("molit.go.kr", "kira.or.kr", "law.go.kr"),
        required_keywords=("건축사", "사무소", "실무", "법령", "표준"),
        deficit_scope="토요일 정책: 학술/실무 분석 중심, 공공 표준계약 보조",
    ),
    6: TopicPolicy(
        topic_id="data_governance",
        day_of_week=6,
        title="건축 관련 데이터베이스(DB) 관리 및 활용 방안",
        subtopics=("건축 공간정보 DB", "공공 데이터 거버넌스", "건축 인허가 데이터"),
        academic_target=3,
        academic_minimum=1,
        official_target=1,
        official_minimum=0,
        freshness_days=730,
        allowed_domains=("data.go.kr", "molit.go.kr", "nia.or.kr"),
        required_keywords=("데이터베이스", "공간정보", "공공데이터", "표준"),
        deficit_scope="일요일 정책: 학술 논문 중심, 공공 데이터 개방 표준 보조",
    ),
}

TOPIC_ID_MAP: dict[str, TopicPolicy] = {p.topic_id: p for p in POLICIES.values()}


class TopicPolicyRegistry:
    """7대 요일별 정책 저장소 및 조회 파사드"""

    @classmethod
    def get_by_day(cls, day_of_week: int) -> TopicPolicy:
        if day_of_week not in POLICIES:
            raise ValueError(f"유효하지 않은 요일 인덱스입니다: {day_of_week} (0=월 ~ 6=일)")
        return POLICIES[day_of_week]

    @classmethod
    def get_policy_for_day(cls, day_of_week: int) -> TopicPolicy:
        return cls.get_by_day(day_of_week)

    @classmethod
    def get_by_topic_id(cls, topic_id: str) -> TopicPolicy | None:
        return TOPIC_ID_MAP.get(topic_id)

    @classmethod
    def get_policy_by_id(cls, topic_id: str) -> TopicPolicy:
        policy = cls.get_by_topic_id(topic_id)
        if policy is None:
            raise KeyError(f"등록되지 않은 topic_id 입니다: {topic_id}")
        return policy

    @classmethod
    def get_all_policies(cls) -> tuple[TopicPolicy, ...]:
        return tuple(POLICIES.values())

    @classmethod
    def all_policies(cls) -> tuple[TopicPolicy, ...]:
        return cls.get_all_policies()
