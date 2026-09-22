"""tests.official_sources.test_api_adapters

HTTP 클라이언트 보안/재시도 및 정량 API 어댑터(KOSIS, REB R-ONE, data.go.kr) 단위 테스트.
"""

from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any, Mapping
from unittest.mock import MagicMock, patch
import pytest
import requests
from official_sources.adapters.data_go_kr import DataGoKrProvider
from official_sources.adapters.kosis import KosisProvider
from official_sources.adapters.reb_rone import RebRoneProvider
from official_sources.http_client import SafeHttpClient, sanitize_url
from official_sources.models import SourceQuery, SourceType, TopicPolicy
from official_sources.registry import TopicPolicyRegistry

FIXTURES_DIR = Path(__file__).parent / "fixtures"
KST = timezone(timedelta(hours=9))


class FakeTransport:
    """테스트용 Fake HTTP Transport"""

    def __init__(self, responses: dict[str, Any]) -> None:
        self.responses = responses
        self.call_history: list[str] = []

    def get(
        self,
        url: str,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: tuple[float, float] = (5.0, 20.0),
    ) -> Any:
        self.call_history.append(url)
        for prefix, resp in self.responses.items():
            if prefix in url:
                return resp
        return None


# --- HTTP Client & Security Tests ---

def test_sanitize_url_redacts_api_keys():
    raw_url = "https://kosis.kr/openapi/data?apiKey=SECRET_12345&tblId=DT_1ML0001"
    sanitized = sanitize_url(raw_url)
    assert "SECRET_12345" not in sanitized
    assert "apiKey=%5BREDACTED%5D" in sanitized or "apiKey=[REDACTED]" in sanitized

    raw_url2 = "https://apis.data.go.kr/1613000/data?serviceKey=ANOTHER_SECRET&page=1"
    sanitized2 = sanitize_url(raw_url2)
    assert "ANOTHER_SECRET" not in sanitized2
    assert "serviceKey=" in sanitized2


def test_safe_http_client_login_captcha_detection():
    client = SafeHttpClient(allowed_domains=["molit.go.kr"])
    mock_resp = MagicMock(spec=requests.Response)
    mock_resp.status_code = 200
    mock_resp.url = "https://www.molit.go.kr/login.do"
    mock_resp.headers = {"Content-Type": "text/html"}
    mock_resp.text = "<html><body>Please enter your username and password or captcha</body></html>"

    with patch("requests.Session.send", return_value=mock_resp):
        with pytest.raises(PermissionError) as exc_info:
            client.get("https://www.molit.go.kr/login.do")
        assert "captcha" in str(exc_info.value).lower()


def test_safe_http_client_disallowed_redirect():
    client = SafeHttpClient(allowed_domains=["kosis.kr"])
    mock_resp = MagicMock(spec=requests.Response)
    mock_resp.status_code = 200
    mock_resp.url = "https://attacker.com/malicious"
    mock_resp.headers = {}
    mock_resp.text = "malicious payload"

    with patch("requests.Session.send", return_value=mock_resp):
        with pytest.raises(PermissionError) as exc_info:
            client.get("https://kosis.kr/data")
        assert "attacker.com" in str(exc_info.value)


# --- KOSIS Provider Tests ---

def test_kosis_provider_normalization():
    fixture_path = FIXTURES_DIR / "kosis_fixture.json"
    fixture_data = json.loads(fixture_path.read_text(encoding="utf-8"))

    transport = FakeTransport({"kosis.kr": fixture_data})
    provider = KosisProvider(transport=transport, api_key="TEST_KEY")
    policy = TopicPolicyRegistry.get_by_day(0)  # Monday policy

    query = SourceQuery(
        topic_id=policy.topic_id,
        keywords=policy.required_keywords,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 3, 20),
        limit=5,
    )

    result = provider.collect(query, policy)
    assert result.provider_id == "kosis_official_api"
    assert len(result.candidates) >= 1

    cand = result.candidates[0]
    assert cand.source_type == SourceType.STATISTICS
    assert "통계청" in cand.publisher
    assert cand.final_domain == "kosis.kr"
    assert "지가변동률" in cand.title
    assert "0.15" in cand.evidence_excerpt or "0.08" in cand.evidence_excerpt


# --- REB R-ONE Provider Tests & Sample Mode Disqualification ---

def test_reb_rone_provider_normalization():
    fixture_path = FIXTURES_DIR / "reb_fixture.json"
    fixture_data = json.loads(fixture_path.read_text(encoding="utf-8"))

    transport = FakeTransport({"reb.or.kr": fixture_data})
    provider = RebRoneProvider(transport=transport, api_key="TEST_KEY")
    policy = TopicPolicyRegistry.get_by_day(0)

    query = SourceQuery(
        topic_id=policy.topic_id,
        keywords=policy.required_keywords,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 3, 20),
        limit=5,
    )

    result = provider.collect(query, policy)
    assert result.provider_id == "reb_rone_api"
    assert len(result.candidates) == 1

    cand = result.candidates[0]
    assert cand.source_type == SourceType.STATISTICS
    assert "한국부동산원" in cand.publisher
    assert cand.final_domain == "reb.or.kr"
    assert "구미시" in cand.evidence_excerpt


def test_reb_rone_sample_mode_rejection():
    # 샘플 모드 데이터 fixture (운영 모드 거부 필수)
    sample_data = {
        "status": "success",
        "is_sample": True,
        "mode": "sample",
        "data": [
            {
                "region_name": "구미시",
                "index_type": "샘플용 지수",
                "base_date": "2026-03-01",
                "index_value": 100.0,
            }
        ],
    }

    transport = FakeTransport({"reb.or.kr": sample_data})
    provider = RebRoneProvider(transport=transport, api_key="TEST_KEY")
    policy = TopicPolicyRegistry.get_by_day(0)

    query = SourceQuery(
        topic_id=policy.topic_id,
        keywords=policy.required_keywords,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 3, 20),
        limit=5,
    )

    result = provider.collect(query, policy)
    # 샘플 모드인 경우 후보군에 등록되지 않아야 함
    assert len(result.candidates) == 0
    assert result.rejection_counts.get("sample_mode_rejected", 0) >= 1


# --- Data.go.kr Provider Tests ---

def test_data_go_kr_provider_normalization():
    fixture_path = FIXTURES_DIR / "data_go_kr_fixture.json"
    fixture_data = json.loads(fixture_path.read_text(encoding="utf-8"))

    transport = FakeTransport({"apis.data.go.kr": fixture_data})
    provider = DataGoKrProvider(transport=transport, service_key="TEST_KEY")
    policy = TopicPolicyRegistry.get_by_day(0)

    query = SourceQuery(
        topic_id=policy.topic_id,
        keywords=policy.required_keywords,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 3, 20),
        limit=5,
    )

    result = provider.collect(query, policy)
    assert result.provider_id == "data_go_kr_api"
    assert len(result.candidates) == 1

    cand = result.candidates[0]
    assert cand.source_type == SourceType.STATISTICS
    assert cand.publisher == "공공데이터포털"
    assert cand.final_domain == "data.go.kr"
    assert "35,000" in cand.evidence_excerpt
