
import pytest
from unittest.mock import MagicMock, patch
from briefing_auto import GeminiProvider

def test_gemini_provider_model_configuration():
    """GeminiProvider가 승인된 올바른 모델 리스트를 가지고 있는지 확인"""
    provider = GeminiProvider(api_key="mock_key")
    
    # 2026년 4월 기준 실제 지원 모델 리스트 검증
    expected_models = [
        "gemini-2.5-flash",       # 최신 주력
        "gemini-2.5-pro",         # 고성능 분석
        "gemini-2.5-flash-lite",  # 최신 경량
        "gemini-2.0-flash-001",   # 정식 릴리즈 안정판
        "gemini-2.0-flash",       # 범용 백업
        "gemini-2.0-flash-lite"   # 안정 경량
    ]
    assert provider.models == expected_models
    assert len(provider.models) == 6

@patch('briefing_auto.GeminiProvider._call_api')
def test_gemini_provider_fallback_logic(mock_call_api):
    """상위 모델 실패 시 하위 모델로 폴백되는지 로직 검증"""
    provider = GeminiProvider(api_key="mock_key")
    
    # 상위 5개 모델은 실패하고, 마지막 경량 모델만 성공하도록 설정
    def side_effect(model_name, topic):
        if "2.5" in model_name or "flash-001" in model_name or model_name == "gemini-2.0-flash":
            raise Exception("404 Not Found")
        elif model_name == "gemini-2.0-flash-lite":
            return "분석 리포트 결과"
        return "실패"

    mock_call_api.side_effect = side_effect

    # 실행
    with patch('time.sleep', return_value=None):
        content = provider.generate_content("테스트 주제")

    # 검증
    assert content == "분석 리포트 결과"
    assert mock_call_api.call_count == 6
