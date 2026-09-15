
import pytest
from unittest.mock import MagicMock, patch
from briefing_auto import GeminiProvider

def test_gemini_provider_model_configuration():
    """GeminiProvider가 승인된 올바른 모델 리스트를 가지고 있는지 확인"""
    provider = GeminiProvider(api_key="mock_key")

    # 2026년 9월 기준 실제 지원 플래시 모델 리스트 검증
    expected_models = [
        "models/gemini-3.8-flash",
        "models/gemini-3.7-flash",
        "models/gemini-3.6-flash",
        "models/gemini-2.5-flash",
        "models/gemini-2.5-flash-lite"
    ]
    assert provider.models == expected_models
    assert len(provider.models) == 5

@patch('briefing_auto.GeminiProvider._call_api')
def test_gemini_provider_fallback_logic(mock_call_api):
    """상위 모델 실패 시 하위 모델로 폴백되는지 로직 검증"""
    provider = GeminiProvider(api_key="mock_key")

    # 상위 4개 모델은 실패하고, 마지막 경량 모델만 성공하도록 설정
    def side_effect(model_name, topic, use_tools=True):
        if model_name in [
            "models/gemini-3.8-flash",
            "models/gemini-3.7-flash",
            "models/gemini-3.6-flash",
            "models/gemini-2.5-flash"
        ]:
            raise Exception("404 Not Found")
        elif model_name == "models/gemini-2.5-flash-lite":
            return "분석 리포트 결과"
        return "실패"

    mock_call_api.side_effect = side_effect

    # 실행
    with patch('time.sleep', return_value=None):
        content = provider.generate_content("테스트 주제")

    # 검증
    assert "분석 리포트 결과" in content
    assert mock_call_api.call_count == 5

