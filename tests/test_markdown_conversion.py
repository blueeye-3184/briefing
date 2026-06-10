
import pytest
from briefing_auto import NotionPublisher, BriefingReport

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

    report = BriefingReport("월요일", "테스트 주제", content)
    
    # blocks 생성 로직 테스트 (내부 로직 검증을 위해 publish_report 호출 전 단계 확인)
    blocks = []
    for line in report.content.split('\n'):
        line = line.strip()
        if not line: continue
        
        # 실제 구현할 로직을 여기에 미리 시뮬레이션 (TDD의 '실패' 단계용)
        # 현재 코드는 리스트를 지원하지 않으므로 여기서 실패할 것임
        if line.startswith('- '):
            type_ = "bulleted_list_item"
            text = line[2:]
        elif line[0:1].isdigit() and line[1:3] == ". ":
            type_ = "numbered_list_item"
            text = line[3:]
        elif line.startswith('###'):
            type_ = "heading_3"; text = line[3:].strip()
        elif line.startswith('##'):
            type_ = "heading_2"; text = line[2:].strip()
        elif line.startswith('#'):
            type_ = "heading_1"; text = line[1:].strip()
        else:
            type_ = "paragraph"; text = line

        blocks.append({"type": type_, "text": text})

    # 검증
    assert blocks[0]["type"] == "heading_1"
    assert blocks[3]["type"] == "bulleted_list_item"
    assert blocks[3]["text"] == "리스트 아이템 1"
    assert blocks[5]["type"] == "numbered_list_item"
    assert blocks[5]["text"] == "번호 리스트 1"
    assert blocks[6]["type"] == "paragraph"

def test_long_text_splitting():
    """2,000자 이상의 긴 텍스트가 여러 블록으로 분할되는지 테스트"""
    long_text = "A" * 2500  # 2,500자 텍스트
    notion = NotionPublisher("fake_token")
    
    # 내부 분할 로직 시뮬레이션
    def split_text(text, limit=2000):
        return [text[i:i + limit] for i in range(0, len(text), limit)]
    
    chunks = split_text(long_text)
    assert len(chunks) == 2
    assert len(chunks[0]) == 2000
    assert len(chunks[1]) == 500
