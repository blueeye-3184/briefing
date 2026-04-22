
import pytest
from datetime import datetime, timedelta, timezone
from briefing_auto import BriefingSchedule, KST

def test_briefing_schedule_monday():
    """월요일(0) 주제를 정확히 가져오는지 테스트"""
    # 2026-04-13은 월요일입니다.
    mock_now = datetime(2026, 4, 13, 10, 0, 0, tzinfo=KST)
    
    # 클래스 메서드 내에서 datetime.now(KST)를 직접 호출하므로, 
    # 테스트를 위해 로직을 약간 분리하거나 머킹이 필요합니다.
    # 여기서는 고정된 스케줄 딕셔너리 값을 직접 확인하는 방식으로 도메인 규칙을 검증합니다.
    day_idx = mock_now.weekday()
    day_name, topic = BriefingSchedule.SCHEDULE[day_idx]
    
    assert day_idx == 0
    assert day_name == "월요일"
    assert "부동산" in topic

def test_briefing_schedule_tuesday():
    """화요일(1) 주제를 정확히 가져오는지 테스트"""
    # 2026-04-14는 화요일입니다.
    mock_now = datetime(2026, 4, 14, 10, 0, 0, tzinfo=KST)
    day_idx = mock_now.weekday()
    day_name, topic = BriefingSchedule.SCHEDULE[day_idx]
    
    assert day_idx == 1
    assert day_name == "화요일"
    assert "친환경" in topic

def test_kst_timezone_offset():
    """KST 타임존이 UTC+9인지 확인"""
    assert KST.utcoffset(None) == timedelta(hours=9)
