
import pytest
from briefing_auto import (
    NOTION_OPERATIONAL_BLOCK_LIMIT,
    NOTION_SAFE_TEXT_LIMIT,
    NotionPublisher,
)

def test_markdown_to_notion_blocks():
    """마크다운 형식이 노션 블록으로 올바르게 변환되는지 테스트"""
    notion = NotionPublisher("fake_token")
    
    content = """# 제목 1
## 제목 2
### 제목 3
- 리스트 아이템 1
- 리스트 아이템 2
1. 번호 리스트 1
일반 텍스트입니다."""

    blocks = notion.markdown_to_notion_blocks(content)

    # 검증
    assert blocks[0]["type"] == "heading_1"
    assert blocks[3]["type"] == "bulleted_list_item"
    assert blocks[3]["bulleted_list_item"]["rich_text"][0]["text"]["content"] == "리스트 아이템 1"
    assert blocks[5]["type"] == "numbered_list_item"
    assert blocks[5]["numbered_list_item"]["rich_text"][0]["text"]["content"] == "번호 리스트 1"
    assert blocks[6]["type"] == "paragraph"

def test_long_text_splitting():
    """1,800자 안전 한도 이상의 텍스트가 여러 블록으로 분할되는지 테스트"""
    long_text = "A" * 2500  # 2,500자 텍스트
    notion = NotionPublisher("fake_token")

    chunks = notion._split_text_safely(long_text)
    assert len(chunks) == 2
    assert len(chunks[0]) == NOTION_SAFE_TEXT_LIMIT
    assert len(chunks[1]) == 2500 - NOTION_SAFE_TEXT_LIMIT
    assert all(len(chunk) <= NOTION_SAFE_TEXT_LIMIT for chunk in chunks)


def test_numbered_list_supports_ten_references_and_links():
    notion = NotionPublisher("fake_token")
    blocks = notion.markdown_to_notion_blocks(
        "10. [논문 DOI](https://doi.org/10.1000/example)"
    )
    assert blocks[0]["type"] == "numbered_list_item"
    rich_text = blocks[0]["numbered_list_item"]["rich_text"]
    assert rich_text[0]["text"]["content"] == "논문 DOI"
    assert rich_text[0]["text"]["link"]["url"] == "https://doi.org/10.1000/example"


def test_notion_operational_block_limit_is_enforced():
    notion = NotionPublisher("fake_token")
    content = "\n".join(f"문단 {i}" for i in range(NOTION_OPERATIONAL_BLOCK_LIMIT + 1))
    with pytest.raises(ValueError, match="운영 상한"):
        notion.markdown_to_notion_blocks(content)
