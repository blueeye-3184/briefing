import pytest
from unittest.mock import patch, MagicMock
from briefing_auto import AcademicPaper, AcademicProvider, BriefingSchedule

def test_academic_paper_attributes():
    paper = AcademicPaper(
        title="고층 목조 건축의 구조 및 내화 분석",
        authors=["엄현진", "공순구"],
        journal="한국공간디자인학회 논문집",
        year=2019,
        doi="https://doi.org/10.1234/test.2019",
        oa_url="http://dspace.kci.go.kr/handle/kci/200224",
        abstract="본 연구는 고층 목조 건축의 구조 및 내화 특성을 분석하였다."
    )
    assert paper.title == "고층 목조 건축의 구조 및 내화 분석"
    assert len(paper.authors) == 2
    assert paper.year == 2019
    assert paper.doi == "https://doi.org/10.1234/test.2019"
    assert paper.oa_url == "http://dspace.kci.go.kr/handle/kci/200224"

def test_academic_paper_reference_formatting_with_papers():
    paper = AcademicPaper(
        title="실무적 BIM 객체분류체계 연구",
        authors=["정영수", "김예솔"],
        journal="한국건설관리학회논문집",
        year=2013,
        doi="https://doi.org/10.9999/bim.2013",
        oa_url="http://koreascience.or.kr/article/sample.pdf",
        abstract="BIM의 실무적 적용을 위한 파라메트릭 분류체계를 제안한다."
    )
    section = AcademicPaper.format_reference_section([paper])
    assert "피어리뷰" in section
    assert "Open Access" in section
    assert "실무적 BIM 객체분류체계 연구" in section
    assert "정영수, 김예솔" in section
    assert "https://doi.org/10.9999/bim.2013" in section
    assert "http://koreascience.or.kr/article/sample.pdf" in section
    assert "검증된 연구 초록 요약" in section

def test_academic_paper_reference_formatting_abstention():
    section = AcademicPaper.format_reference_section([])
    assert "Abstention Notice" in section
    assert "100% 피어리뷰" in section
    assert "허위 학술 자료" in section
    assert "가상 인용을 일체 배제" in section

def test_briefing_schedule_all_days_have_keywords():
    for day_idx in range(7):
        assert day_idx in BriefingSchedule.SEARCH_KEYWORDS
        kws = BriefingSchedule.SEARCH_KEYWORDS[day_idx]
        assert isinstance(kws, list)
        assert len(kws) >= 2

@patch('requests.get')
def test_academic_provider_search_success(mock_get):
    mock_res = MagicMock()
    mock_res.status_code = 200
    mock_res.json.return_value = {
        "results": [
            {
                "title": "Sample OA Paper",
                "doi": "https://doi.org/10.1000/sample",
                "publication_year": 2022,
                "authorships": [{"author": {"display_name": "김연구"}}],
                "primary_location": {"source": {"display_name": "대한건축학회논문집"}},
                "open_access": {"oa_url": "https://example.com/paper.pdf"},
                "abstract_inverted_index": {"건축": [0], "설계": [1], "연구": [2]}
            }
        ]
    }
    mock_get.return_value = mock_res

    provider = AcademicProvider()
    papers = provider.search_peer_reviewed_oa_papers(["건축 설계"], max_papers=1)

    assert len(papers) == 1
    assert papers[0].title == "Sample OA Paper"
    assert papers[0].authors == ["김연구"]
    assert papers[0].year == 2022
    assert papers[0].journal == "대한건축학회논문집"
    assert papers[0].abstract == "건축 설계 연구"

@patch('requests.get')
def test_academic_provider_api_error_returns_empty(mock_get):
    mock_get.side_effect = Exception("Network error")
    provider = AcademicProvider()
    papers = provider.search_peer_reviewed_oa_papers(["키워드"], max_papers=1)
    assert papers == []
