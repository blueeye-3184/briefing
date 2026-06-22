
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

    # 1. 먼저 자식 블록 조회 시 동일한 타이틀이 있는 것으로 가정 (Mocking)
    def mock_request(method, url, data=None):
        if method == "GET" and f"blocks/{parent_id}/children" in url:
            return {
                "results": [
                    {
                        "type": "child_page",
                        "child_page": {"title": title},
                        "id": existing_id
                    }
                ]
            }
        return {}

    with patch.object(NotionPublisher, 'request', side_effect=mock_request) as mock_req:
        page_id = mock_notion.get_or_create_page(parent_id, title)
        
        assert page_id == existing_id
        # 중요: 검색에 성공했으므로 POST(생성) 요청은 호출되지 않아야 함
        assert not any(call.args[0] == "POST" for call in mock_req.call_args_list)

def test_get_or_create_page_creates_new_if_not_exists(mock_notion):
    """존재하는 페이지가 없을 경우 새로 생성하는지 테스트"""
    parent_id = "parent_123"
    title = "새로운 폴더"
    new_id = "new_page_789"

    # 1. 자식 블록 조회 시 결과가 비어 있고, 생성 요청(POST)에 대해 새 ID를 반환하도록 가정
    def mock_request(method, url, data=None):
        if method == "GET" and f"blocks/{parent_id}/children" in url:
            return {"results": []}
        elif method == "POST" and "pages" in url:
            return {"id": new_id}
        return {}

    with patch.object(NotionPublisher, 'request', side_effect=mock_request) as mock_req:
        page_id = mock_notion.get_or_create_page(parent_id, title)
        
        assert page_id == new_id
        # 검색 실패 후 POST(생성) 요청이 호출되어야 함
        assert mock_req.call_count == 2
        assert mock_req.call_args_list[0].args[0] == "GET"
        assert mock_req.call_args_list[1].args[0] == "POST"

