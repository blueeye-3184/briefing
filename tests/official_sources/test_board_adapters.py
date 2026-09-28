"""tests.official_sources.test_board_adapters

국토부 RSS, 지자체 고시공고(구미/김천), IRIS 및 KAIA R&D 사업공고 어댑터 단위 테스트.
"""

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping
from official_sources.adapters.gimcheon import GimcheonNoticeProvider
from official_sources.adapters.gumi import GumiNoticeProvider
from official_sources.adapters.iris import IrisAnnouncementProvider
from official_sources.adapters.kaia import KaiaAnnouncementProvider
from official_sources.adapters.molit_rss import MolitRssProvider
from official_sources.adapters.official_board import parse_board_table, strip_html_tags
from official_sources.models import SourceQuery, SourceType, VerificationStatus
from official_sources.registry import TopicPolicyRegistry

FIXTURES_DIR = Path(__file__).parent / "fixtures"
KST = timezone(timedelta(hours=9))


class FakeTransport:
    def __init__(self, responses: dict[str, Any]) -> None:
        self.responses = responses

    def get(
        self,
        url: str,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: tuple[float, float] = (5.0, 20.0),
    ) -> Any:
        for prefix, resp in self.responses.items():
            if prefix in url:
                return resp
        return ""


# --- MOLIT RSS Provider Tests ---

def test_molit_rss_provider_preserves_detail_url():
    xml_content = (FIXTURES_DIR / "molit_fixture.xml").read_text(encoding="utf-8")
    transport = FakeTransport({"molit.go.kr": xml_content})
    provider = MolitRssProvider(transport=transport)
    policy = TopicPolicyRegistry.get_by_day(0)

    query = SourceQuery(
        topic_id=policy.topic_id,
        keywords=policy.required_keywords,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 3, 20),
    )

    result = provider.collect(query, policy)
    assert result.provider_id == "molit_official_rss"
    assert len(result.candidates) == 1

    cand = result.candidates[0]
    assert cand.source_type == SourceType.POLICY
    assert cand.publisher == "국토교통부"
    assert cand.final_domain == "molit.go.kr"
    # 상세 URL이 canonical_url로 온전히 유지되어야 함
    assert "dtl.jsp?lcls=NEWS&id=123456" in cand.canonical_url


# --- Official Board Table Parser & Gumi / Gimcheon Tests ---

def test_official_board_table_parsing():
    html_content = (FIXTURES_DIR / "board_fixture.html").read_text(encoding="utf-8")
    items = parse_board_table(html_content, "https://www.gumi.go.kr")

    assert len(items) == 2
    assert items[0].item_id == "2026-101"
    assert "도시계획시설" in items[0].title
    assert "gosiView.do" in items[0].detail_url
    assert items[0].department == "도시계획과"


def test_strip_html_tags():
    raw_html = "<p>도시계획 <strong>결정</strong> 고시입니다.<br>참조하세요.</p>"
    cleaned = strip_html_tags(raw_html)
    assert cleaned == "도시계획 결정 고시입니다. 참조하세요."


def test_gumi_notice_provider():
    html_content = (FIXTURES_DIR / "board_fixture.html").read_text(encoding="utf-8")
    transport = FakeTransport({"gumi.go.kr": html_content})
    provider = GumiNoticeProvider(transport=transport)
    policy = TopicPolicyRegistry.get_by_day(0)

    query = SourceQuery(
        topic_id=policy.topic_id,
        keywords=policy.required_keywords,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 3, 20),
    )

    result = provider.collect(query, policy)
    assert result.provider_id == "gumi_official_notice"
    assert len(result.candidates) == 2

    cand = result.candidates[0]
    assert cand.source_type == SourceType.NOTICE
    assert cand.publisher == "구미시"
    assert cand.final_domain == "gumi.go.kr"
    assert cand.metadata["department"] == "도시계획과"


def test_gimcheon_notice_provider():
    html_content = (FIXTURES_DIR / "board_fixture.html").read_text(encoding="utf-8")
    transport = FakeTransport({"gc.go.kr": html_content})
    provider = GimcheonNoticeProvider(transport=transport)
    policy = TopicPolicyRegistry.get_by_day(0)

    query = SourceQuery(
        topic_id=policy.topic_id,
        keywords=policy.required_keywords,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 3, 20),
    )

    result = provider.collect(query, policy)
    assert result.provider_id == "gimcheon_official_notice"
    assert len(result.candidates) == 2

    cand = result.candidates[0]
    assert cand.source_type == SourceType.NOTICE
    assert cand.publisher == "김천시"
    assert cand.final_domain == "gc.go.kr"


# --- IRIS Provider & Detail Verification / Supersedes Tests ---

def test_iris_announcement_provider_and_supersedes():
    iris_json = (FIXTURES_DIR / "iris_fixture.json").read_text(encoding="utf-8")
    transport = FakeTransport({"iris.go.kr": iris_json})
    provider = IrisAnnouncementProvider(transport=transport)
    fri_policy = TopicPolicyRegistry.get_by_day(4)  # Friday architecture R&D calls

    query = SourceQuery(
        topic_id=fri_policy.topic_id,
        keywords=fri_policy.required_keywords,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 3, 20),
    )

    result = provider.collect(query, fri_policy)
    assert result.provider_id == "iris_official_announcement"
    assert len(result.candidates) == 3

    # 첫 번째: 상세 검증 완료 공고
    c1 = result.candidates[0]
    assert c1.source_type == SourceType.ANNOUNCEMENT
    assert c1.metadata["list_only_unverified"] is False
    assert c1.verification_status == VerificationStatus.DISCOVERED

    # 두 번째: [정정] 공고이며 supersedes 관계 보존 확인
    c2 = result.candidates[1]
    assert "supersedes" in c2.metadata
    assert c2.metadata["supersedes"] == "IRIS-2026-BASE"

    # 세 번째: 목록만 있는 미검증 공고 -> metadata["list_only_unverified"] is True
    c3 = result.candidates[2]
    assert c3.metadata["list_only_unverified"] is True
    assert c3.verification_status == VerificationStatus.NOT_VERIFIED


def test_kaia_announcement_provider():
    kaia_raw = """
    {
      "items": [
        {
          "ancmId": "KAIA-2026-99",
          "ancmNm": "2026 스마트건설 디지털 트윈 플랫폼 기술 R&D",
          "ancmDe": "2026-03-21",
          "detail_verified": true
        }
      ]
    }
    """
    transport = FakeTransport({"kaia.re.kr": kaia_raw})
    provider = KaiaAnnouncementProvider(transport=transport)
    fri_policy = TopicPolicyRegistry.get_by_day(4)

    query = SourceQuery(
        topic_id=fri_policy.topic_id,
        keywords=fri_policy.required_keywords,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 3, 20),
    )

    result = provider.collect(query, fri_policy)
    assert result.provider_id == "kaia_official_announcement"
    assert len(result.candidates) == 1
    assert result.candidates[0].publisher == "국토교통과학기술진흥원"
    assert result.candidates[0].final_domain == "kaia.re.kr"
