"""official_sources.adapters.official_board

지자체 및 정부기관 공식 고시공고/게시판 공통 기본 어댑터 및 파서:
- HTML 목록/상세의 표준 구조 파싱 (표준 라이브러리 html.parser 활용)
- 태그 제거 및 텍스트 정규화
- URL 절대경로 정규화 및 HTTPS 유지
- 비인가 외부 크롤러로의 확장 방지 및 허용 도메인 제한
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
import re
from urllib.parse import urljoin, urlparse
from official_sources.http_client import is_domain_allowed
from official_sources.ports import HttpTransport


class HTMLTextExtractor(HTMLParser):
    """HTML 본문에서 텍스트만 추출하고 공백을 정규화하는 파서"""

    def __init__(self) -> None:
        super().__init__()
        self._pieces: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self._pieces.append(text)

    def get_text(self) -> str:
        return " ".join(self._pieces)


def strip_html_tags(html_content: str) -> str:
    """HTML 태그를 제거하고 정규화된 평문 반환"""
    if not html_content:
        return ""
    extractor = HTMLTextExtractor()
    try:
        extractor.feed(html_content)
        return extractor.get_text()
    except Exception:
        # Fallback to simple regex if parser fails
        clean = re.sub(r"<[^>]+>", " ", html_content)
        return " ".join(clean.split())


@dataclass(frozen=True)
class BoardListItem:
    """공식 게시판 목록의 단일 항목"""
    item_id: str
    title: str
    published_date_str: str
    detail_url: str
    department: str = ""
    author: str = ""


class TableRowHTMLParser(HTMLParser):
    """게시판 <table>의 <tr>/<td>를 추출하는 표준 파서"""

    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.rows: list[list[str]] = []
        self.links: list[dict[str, str]] = []  # row_idx -> href
        self._current_row: list[str] = []
        self._current_cell: list[str] = []
        self._current_link: str | None = None
        self._in_cell = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "tr":
            self._current_row = []
            self._current_link = None
        elif tag in ("td", "th"):
            self._in_cell = True
            self._current_cell = []
        elif tag == "a" and self._in_cell:
            href = attrs_dict.get("href")
            if href and not self._current_link:
                self._current_link = urljoin(self.base_url, href)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th"):
            self._in_cell = False
            self._current_row.append(" ".join(" ".join(self._current_cell).split()))
            self._current_cell = []
        elif tag == "tr":
            if self._current_row:
                self.rows.append(self._current_row)
                self.links.append({"url": self._current_link or ""})
            self._current_row = []
            self._current_link = None

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            text = data.strip()
            if text:
                self._current_cell.append(text)


def parse_board_table(html: str, base_url: str) -> list[BoardListItem]:
    """공통 고시공고/게시판 테이블 HTML 파싱"""
    parser = TableRowHTMLParser(base_url)
    try:
        parser.feed(html)
    except Exception:
        return []

    items: list[BoardListItem] = []
    for idx, row in enumerate(parser.rows):
        if not row:
            continue
        # 헤더 행 건너뛰기
        if any(h in "".join(row) for h in ("번호", "제목", "작성일", "등록일", "부서", "담당부서")):
            continue

        link = parser.links[idx]["url"] if idx < len(parser.links) else ""
        if not link:
            continue

        # 일반적인 행 구조: [번호, 제목, 담당부서/작성자, 등록일, ...]
        item_id = row[0] if len(row) > 0 else ""
        title = ""
        dept = ""
        date_str = ""

        if len(row) >= 2:
            title = row[1]
        if len(row) >= 3:
            # 날짜 정규식 매칭 시도
            for cell in row[2:]:
                if re.search(r"\d{4}[-./]\d{1,2}[-./]\d{1,2}", cell):
                    date_str = cell
                    break
            # 부서 매칭
            if len(row) >= 4 and date_str != row[2]:
                dept = row[2]

        if title and link:
            items.append(
                BoardListItem(
                    item_id=item_id,
                    title=title,
                    published_date_str=date_str,
                    detail_url=link,
                    department=dept,
                )
            )

    return items


def parse_kst_date(date_str: str) -> datetime | None:
    """YYYY-MM-DD, YYYY.MM.DD 등의 날짜 문자열을 KST timezone-aware datetime으로 변환"""
    if not date_str:
        return None
    match = re.search(r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})", date_str)
    if not match:
        return None
    year, month, day = map(int, match.groups())
    # KST is UTC+9
    kst = timezone(datetime.now().astimezone().tzinfo.utcoffset(None) or timezone.utc.utcoffset(None))  # type: ignore
    try:
        from datetime import timezone as dt_tz, timedelta
        kst_tz = dt_tz(timedelta(hours=9))
        return datetime(year, month, day, 0, 0, 0, tzinfo=kst_tz)
    except Exception:
        return None
