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
        abstract="BIM의 실무적 적용을 위한 파라메트릭 분류체계를 제안한다.",
        source_type="journal",
        oa_version="publishedVersion",
        oa_license="cc-by",
        crossref_type="journal-article",
        title_verified=True,
    )
    section = AcademicPaper.format_reference_section([paper])
    assert "엄격 적격성 게이트" in section
    assert "자료 결손" in section
    assert "실무적 BIM 객체분류체계 연구" in section
    assert "정영수, 김예솔" in section
    assert "https://doi.org/10.9999/bim.2013" in section
    assert "http://koreascience.or.kr/article/sample.pdf" in section
    assert "검증된 연구 초록 요약" not in section
    assert paper.strict_eligibility_passed

def test_academic_paper_reference_formatting_abstention():
    section = AcademicPaper.format_reference_section([])
    assert "UNKNOWN / DEFICIT REPORT" in section
    assert "목표 10편" in section
    assert "0편" in section
    assert "논문을 임의로 보충하지 않았으며" in section

def test_briefing_schedule_all_days_have_keywords():
    for day_idx in range(7):
        assert day_idx in BriefingSchedule.SEARCH_KEYWORDS
        kws = BriefingSchedule.SEARCH_KEYWORDS[day_idx]
        assert isinstance(kws, list)
        assert len(kws) >= 2

@patch('requests.get')
def test_academic_provider_search_success(mock_get):
    openalex_res = MagicMock(status_code=200)
    openalex_res.json.return_value = {
        "results": [{
            "id": "https://openalex.org/W1",
            "title": "Sample OA Paper",
            "doi": "https://doi.org/10.1000/sample",
            "publication_year": 2022,
            "authorships": [{"author": {"display_name": "김연구"}}],
            "primary_location": {
                "source": {"display_name": "대한건축학회논문집", "type": "journal"}
            },
            "best_oa_location": {
                "is_oa": True,
                "pdf_url": "https://example.com/paper.pdf",
                "version": "publishedVersion",
                "license": "cc-by",
            },
            "is_retracted": False,
            "abstract_inverted_index": {"건축": [0], "설계": [1], "연구": [2]},
        }]
    }
    crossref_res = MagicMock(status_code=200)
    crossref_res.json.return_value = {
        "message": {"type": "journal-article", "title": ["Sample OA Paper"]}
    }

    def request_side_effect(url, **kwargs):
        return crossref_res if "api.crossref.org" in url else openalex_res

    mock_get.side_effect = request_side_effect

    provider = AcademicProvider()
    papers = provider.search_peer_reviewed_oa_papers(["건축 설계"], max_papers=1)

    assert len(papers) == 1
    assert papers[0].title == "Sample OA Paper"
    assert papers[0].authors == ["김연구"]
    assert papers[0].year == 2022
    assert papers[0].journal == "대한건축학회논문집"
    assert papers[0].abstract == "건축 설계 연구"
    assert papers[0].strict_eligibility_passed
    assert provider.last_audit["eligible_count"] == 1


@patch('requests.get')
def test_academic_provider_rejects_non_open_license(mock_get):
    mock_res = MagicMock(status_code=200)
    mock_res.json.return_value = {
        "results": [{
            "title": "Closed License Paper",
            "doi": "https://doi.org/10.1000/closed",
            "publication_year": 2024,
            "authorships": [],
            "primary_location": {
                "source": {"display_name": "Journal", "type": "journal"}
            },
            "best_oa_location": {
                "is_oa": True,
                "landing_page_url": "https://example.com/article",
                "version": "publishedVersion",
                "license": None,
            },
            "is_retracted": False,
            "abstract_inverted_index": {"abstract": [0]},
        }]
    }
    mock_get.return_value = mock_res

    provider = AcademicProvider()
    assert provider.search_peer_reviewed_oa_papers(["test"], max_papers=10) == []
    assert provider.last_audit["rejections"]["missing_open_license"] == 1


@patch('requests.get')
def test_academic_provider_rejects_doi_title_mismatch(mock_get):
    openalex_res = MagicMock(status_code=200)
    openalex_res.json.return_value = {
        "results": [{
            "title": "Expected Title",
            "doi": "https://doi.org/10.1000/mismatch",
            "publication_year": 2025,
            "authorships": [],
            "primary_location": {
                "source": {"display_name": "Journal", "type": "journal"}
            },
            "best_oa_location": {
                "is_oa": True,
                "pdf_url": "https://example.com/paper.pdf",
                "version": "acceptedVersion",
                "license": "cc-by-nc",
            },
            "is_retracted": False,
            "abstract_inverted_index": {"abstract": [0]},
        }]
    }
    crossref_res = MagicMock(status_code=200)
    crossref_res.json.return_value = {
        "message": {"type": "journal-article", "title": ["Different Title"]}
    }
    mock_get.side_effect = lambda url, **kwargs: (
        crossref_res if "api.crossref.org" in url else openalex_res
    )

    provider = AcademicProvider()
    assert provider.search_peer_reviewed_oa_papers(["test"], max_papers=10) == []
    assert provider.last_audit["rejections"]["doi_title_mismatch"] == 1

@patch('requests.get')
def test_academic_provider_api_error_returns_empty(mock_get):
    mock_get.side_effect = Exception("Network error")
    provider = AcademicProvider()
    papers = provider.search_peer_reviewed_oa_papers(["키워드"], max_papers=1)
    assert papers == []
