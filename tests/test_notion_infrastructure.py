
import pytest
from unittest.mock import MagicMock, patch
from briefing_auto import NotionPublisher

@pytest.fixture
def mock_notion():
    return NotionPublisher("fake_token")

def test_get_or_create_page_finds_existing(mock_notion):
    """이미 존재하는 페이지가 있을 경우 새로 생성하지 않고 기존 ID를 반환하는지 테스트"""
    parent_id = "parent_123"
    title = "2026년 04월"
    existing_id = "existing_page_456"

    # 1. 먼저 검색 결과에 해당 타이틀이 있는 것으로 가정 (Mocking)
    # Notion API의 'query a database'나 'list block children' 등을 모방해야 함
    # 여기서는 새로 구현할 'find_page_by_title' 메서드가 동작한다고 가정
    with patch.object(NotionPublisher, 'find_page_by_title', return_value=existing_id):
        with patch.object(NotionPublisher, 'request') as mock_request:
            page_id = mock_notion.get_or_create_page(parent_id, title)
            
            assert page_id == existing_id
            # 중요: 검색에 성공했으므로 POST(생성) 요청은 호출되지 않아야 함
            assert not any(call.args[0] == "POST" for call in mock_request.call_args_list)

def test_get_or_create_page_creates_new_if_not_exists(mock_notion):
    """존재하는 페이지가 없을 경우 새로 생성하는지 테스트"""
    parent_id = "parent_123"
    title = "새로운 폴더"
    new_id = "new_page_789"

    # 1. 검색 결과가 없는 것으로 가정
    with patch.object(NotionPublisher, 'find_page_by_title', return_value=None):
        with patch.object(NotionPublisher, 'request', return_value={'id': new_id}) as mock_request:
            page_id = mock_notion.get_or_create_page(parent_id, title)
            
            assert page_id == new_id
            # 검색에 실패했으므로 POST(생성) 요청이 호출되어야 함
            mock_request.assert_called_once()
            assert mock_request.call_args[0][0] == "POST"
