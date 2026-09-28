"""
Comprehensive verification tests for G1 ~ G4 gates:
- G1: GitHub Actions runtime (ubuntu-24.04, node24 actions, security boundaries, artifact paths)
- G2: OpenAlex rate limit (429), Retry-After, exponential backoff, and status separation
- G3: Gemini length contract (9,000~11,000 chars), CONDENSE prompt, fallback isolation, attempt metrics
- G4: Early skeleton artifact preservation (run.log, manifest.json), failure injection, secret scrubbing
"""

import os
import json
import time
import pytest
from unittest.mock import MagicMock, patch
from collections import Counter
from datetime import datetime, timezone, timedelta

from manifest_manager import (
    SearchStatus,
    GeminiOutcome,
    PublishStatus,
    GeminiAttemptRecord,
    AcademicSearchResult,
    InfographicSpec,
    ManifestManager,
    redact_secrets,
    hash_page_id,
)
from briefing_auto import (
    AcademicPaper,
    AcademicProvider,
    GeminiProvider,
    NotionPublisher,
    SlackNotifier,
    BriefingApplicationService,
    BriefingSchedule,
    parse_retry_after,
    TARGET_BODY_MIN_CHARS,
    TARGET_BODY_MAX_CHARS,
    TARGET_PAPER_COUNT,
)


# ==============================================================================
# G1: GitHub Actions Runtime & Workflow Policy Tests
# ==============================================================================

def test_g1_workflow_ubuntu_2404_pinned_and_no_ubuntu_latest():
    """G1: Verify that all jobs use ubuntu-24.04 and 0 instances of ubuntu-latest remain."""
    workflow_path = os.path.join(".github", "workflows", "daily_briefing.yml")
    assert os.path.exists(workflow_path), f"Workflow file {workflow_path} not found"
    with open(workflow_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "ubuntu-latest" not in content, "ubuntu-latest must not be used anywhere in daily_briefing.yml"
    assert "runs-on: ubuntu-24.04" in content, "Jobs must be pinned to ubuntu-24.04"
    assert content.count("runs-on: ubuntu-24.04") >= 2, "Both test and briefing jobs must run on ubuntu-24.04"


def test_g1_workflow_actions_pinned_to_node24_full_shas():
    """G1: Verify actions/checkout, setup-python, upload-artifact are pinned to full 40-char SHAs."""
    workflow_path = os.path.join(".github", "workflows", "daily_briefing.yml")
    with open(workflow_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    expected_shas = {
        "actions/checkout": "3d3c42e5aac5ba805825da76410c181273ba90b1",  # v7.0.1 (node24)
        "actions/setup-python": "5fda3b95a4ea91299a34e894583c3862153e4b97",  # v7.0.0 (node24)
        "actions/upload-artifact": "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",  # v7.0.1 (node24)
    }

    found_actions = {}
    for line in lines:
        line_clean = line.strip()
        if line_clean.startswith("uses:"):
            action_spec = line_clean.split("uses:", 1)[1].strip()
            action_part, comment_part = (action_spec.split("#", 1) + [""])[:2]
            action_name, sha = action_part.strip().split("@", 1)
            found_actions[action_name] = (sha, comment_part.strip())
            assert len(sha) == 40, f"Action {action_name} must use 40-char commit SHA, got {sha}"
            assert all(c in "0123456789abcdef" for c in sha), f"SHA {sha} must be lowercase hex"
            if action_name in expected_shas:
                assert sha == expected_shas[action_name], f"Mismatch for {action_name}: expected {expected_shas[action_name]}, got {sha}"
                assert "node24" in comment_part, f"Comment for {action_name} should document node24 support"

    assert "actions/checkout" in found_actions
    assert "actions/setup-python" in found_actions
    assert "actions/upload-artifact" in found_actions


def test_g1_workflow_artifact_upload_contract():
    """G1/G4: Verify artifact upload step always runs, includes run_id, and targets artifacts/ directory."""
    workflow_path = os.path.join(".github", "workflows", "daily_briefing.yml")
    with open(workflow_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "if: always()" in content, "Artifact upload step must specify if: always()"
    assert "briefing-run-artifacts-${{ github.run_id }}" in content, "Artifact name must include github.run_id"
    assert "artifacts/run.log" in content, "Artifact path must include artifacts/run.log"
    assert "artifacts/manifest.json" in content, "Artifact path must include artifacts/manifest.json"
    assert "if-no-files-found: warn" in content, "if-no-files-found policy should be warn or error"


# ==============================================================================
# G2: OpenAlex 429 & Rate Limit Defense Tests
# ==============================================================================

def test_g2_parse_retry_after_integer_and_http_date():
    """G2: Test Retry-After parsing with integer seconds, RFC 7231 dates, negative, and excessive values."""
    assert parse_retry_after("15", default_backoff=2.0) == 15.0
    assert parse_retry_after("0", default_backoff=2.0) == 0.0
    assert parse_retry_after("-5", default_backoff=2.0) == 2.0  # negative -> fallback
    assert parse_retry_after("3600", default_backoff=2.0) == 60.0  # capped at 60s
    assert parse_retry_after("", default_backoff=3.0) == 3.0
    assert parse_retry_after(None, default_backoff=3.0) == 3.0
    assert parse_retry_after("invalid-string", default_backoff=4.0) == 4.0

    # RFC 7231 HTTP-date
    fake_now = 1700000000.0
    future_date_str = "Tue, 14 Nov 2023 22:13:30 GMT"  # timestamp = 1700000010
    parsed_delay = parse_retry_after(future_date_str, default_backoff=2.0, clock_fn=lambda: fake_now)
    assert parsed_delay == 10.0


def test_g2_academic_provider_429_retry_success():
    """G2: 429 received first, followed by Retry-After wait and subsequent 200 OK success."""
    sleep_calls = []

    res_429 = MagicMock(status_code=429)
    res_429.headers = {"Retry-After": "3"}
    res_200 = MagicMock(status_code=200)
    res_200.json.return_value = {
        "results": [{
            "id": "https://openalex.org/W1",
            "title": "Retry Success Paper",
            "doi": "https://doi.org/10.1000/retry",
            "publication_year": 2026,
            "authorships": [{"author": {"display_name": "테스트"}}],
            "primary_location": {"source": {"display_name": "학술지", "type": "journal"}},
            "best_oa_location": {
                "is_oa": True,
                "pdf_url": "https://example.com/p.pdf",
                "version": "publishedVersion",
                "license": "cc-by",
            },
            "is_retracted": False,
            "abstract_inverted_index": {"내용": [0]},
        }]
    }
    crossref_res = MagicMock(status_code=200)
    crossref_res.json.return_value = {
        "message": {"type": "journal-article", "title": ["Retry Success Paper"]}
    }

    call_seq = [res_429, res_200, crossref_res]

    def mock_get(url, **kwargs):
        if "crossref.org" in url:
            return crossref_res
        return call_seq.pop(0) if call_seq else res_200

    provider = AcademicProvider(sleep_fn=lambda s: sleep_calls.append(s), max_retries=3)
    with patch("requests.get", side_effect=mock_get):
        result = provider.search_with_status(["테스트 쿼리"], max_papers=1)

    assert len(sleep_calls) == 1
    assert sleep_calls[0] == 3.0
    assert result.status == SearchStatus.SEARCH_OK
    assert len(result.papers) == 1
    assert result.degraded is True  # Rate limit occurred on query, so marked degraded
    assert result.query_metrics["rate_limited_count"] == 1


def test_g2_academic_provider_persistent_429_marked_rate_limited_not_empty():
    """G2: Persistent 429 returns OPENALEX_RATE_LIMITED and is NEVER converted to genuine empty."""
    res_429 = MagicMock(status_code=429)
    res_429.headers = {"Retry-After": "2"}
    sleep_calls = []

    provider = AcademicProvider(sleep_fn=lambda s: sleep_calls.append(s), max_retries=2)
    with patch("requests.get", return_value=res_429):
        result = provider.search_with_status(["부동산 정책"], max_papers=5)

    assert result.status == SearchStatus.OPENALEX_RATE_LIMITED
    assert result.status != SearchStatus.SEARCH_GENUINE_EMPTY
    assert len(result.papers) == 0
    assert result.degraded is True
    assert result.query_metrics["rate_limited_count"] == 2  # 2 attempts
    assert len(sleep_calls) == 1  # 1 retry slept


def test_g2_academic_provider_genuine_empty_status():
    """G2: 200 OK with empty results returns SEARCH_GENUINE_EMPTY without error."""
    res_200 = MagicMock(status_code=200)
    res_200.json.return_value = {"results": []}

    provider = AcademicProvider()
    with patch("requests.get", return_value=res_200):
        result = provider.search_with_status(["존재하지 않는 특이 주제"], max_papers=5)

    assert result.status == SearchStatus.SEARCH_GENUINE_EMPTY
    assert len(result.papers) == 0
    assert result.degraded is False
    assert result.query_metrics["rate_limited_count"] == 0


def test_g2_academic_provider_provider_unavailable_on_timeout():
    """G2: Network timeout / connection error returns PROVIDER_UNAVAILABLE."""
    provider = AcademicProvider(sleep_fn=lambda s: None, max_retries=2)
    with patch("requests.get", side_effect=Exception("Connection timed out")):
        result = provider.search_with_status(["네트워크 오류 테스트"], max_papers=5)

    assert result.status == SearchStatus.PROVIDER_UNAVAILABLE
    assert result.degraded is True
    assert len(result.papers) == 0


def test_g2_polite_pool_configured_and_email_not_leaked():
    """G2: Polite pool boolean is tracked, but email value is not leaked in manifest or audit."""
    provider = AcademicProvider(email="secret_researcher@example.com")
    assert provider.polite_pool_configured is True
    assert "secret_researcher" in provider.headers["User-Agent"]

    res_200 = MagicMock(status_code=200)
    res_200.json.return_value = {"results": []}
    with patch("requests.get", return_value=res_200):
        result = provider.search_with_status(["키워드"], max_papers=1)

    assert result.polite_pool_configured is True
    # Verify audit trail does not leak raw email address
    audit_json = json.dumps(provider.last_audit)
    assert "secret_researcher@example.com" not in audit_json


def test_g2_guard_blocks_generation_when_all_queries_rate_limited(tmp_path):
    """G2: Service completely blocks normal generation if all queries are rate limited."""
    mock_gemini = MagicMock(spec=GeminiProvider)
    mock_notion = MagicMock(spec=NotionPublisher)
    mock_slack = MagicMock(spec=SlackNotifier)
    mock_academic = MagicMock(spec=AcademicProvider)

    # Return rate limited result with 0 papers
    mock_academic.search_with_status.return_value = AcademicSearchResult(
        papers=[],
        status=SearchStatus.OPENALEX_RATE_LIMITED,
        query_metrics={"query_count": 3, "request_count": 6, "rate_limited_count": 6, "success_count": 0},
        degraded=True,
    )

    manifest_mgr = ManifestManager(artifacts_dir=str(tmp_path / "artifacts"))
    service = BriefingApplicationService(
        gemini=mock_gemini,
        notion=mock_notion,
        slack=mock_slack,
        academic=mock_academic,
        parent_page_id="test-parent-page",
        manifest_manager=manifest_mgr,
    )

    with patch.dict(os.environ, {"GEMINI_API_KEY": "k", "NOTION_TOKEN": "t", "PARENT_PAGE_ID": "p"}):
        with pytest.raises(RuntimeError, match="학술 DB 공급자 장애"):
            service.run_daily_briefing()

    # Gemini generation and Notion publish must NOT have been called!
    mock_gemini.generate_content.assert_not_called()
    mock_notion.publish_report.assert_not_called()

    # Manifest must preserve the failure stage
    manifest_file = tmp_path / "artifacts" / "manifest.json"
    assert manifest_file.exists()
    with open(manifest_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["academic_search"]["status"] == SearchStatus.OPENALEX_RATE_LIMITED.value
    assert data["failure"]["stage"] == "ACADEMIC_SEARCH"
    assert data["run"]["status"] == "FAILED"


# ==============================================================================
# G3: Gemini Length Contract, Condense & Fallback Tests
# ==============================================================================

def test_g3_gemini_success_on_first_full_generation(tmp_path):
    """G3: Normal output within 9,000~11,000 chars succeeds on first FULL attempt."""
    provider = GeminiProvider(api_key="mock_key")
    provider.client = MagicMock()
    provider.client.models.count_tokens.return_value.total_tokens = 500

    target_body = "가" * 10_000
    provider.client.models.generate_content.return_value.text = target_body

    manifest_mgr = ManifestManager(artifacts_dir=str(tmp_path / "artifacts"))
    manifest_mgr.initialize("dec-001", "주제")

    result = provider.generate_content("주제", papers=[], manifest_manager=manifest_mgr)
    assert target_body in result
    assert len(manifest_mgr.manifest_data["gemini_attempts"]) == 1
    attempt = manifest_mgr.manifest_data["gemini_attempts"][0]
    assert attempt["model"] == "models/gemini-3.8-flash"
    assert attempt["attempt_type"] == "FULL"
    assert attempt["outcome"] == GeminiOutcome.SUCCESS.value
    assert attempt["char_count"] == 10_000


def test_g3_gemini_condense_triggered_when_too_long(tmp_path):
    """G3: Output > 11,000 chars triggers CONDENSE prompt on the same model and succeeds."""
    provider = GeminiProvider(api_key="mock_key")
    provider.client = MagicMock()
    provider.client.models.count_tokens.return_value.total_tokens = 500

    too_long_body = "가" * 12_500  # Exceeds 11,000 max
    condensed_body = "나" * 9_800   # Within 9,000~11,000 range

    call_seq = [
        MagicMock(text=too_long_body),
        MagicMock(text=condensed_body),
    ]
    provider.client.models.generate_content.side_effect = lambda **kwargs: call_seq.pop(0)

    manifest_mgr = ManifestManager(artifacts_dir=str(tmp_path / "artifacts"))
    manifest_mgr.initialize("dec-002", "주제")

    result = provider.generate_content("주제", papers=[], manifest_manager=manifest_mgr)
    assert condensed_body in result

    # Verify attempts in manifest: first FULL (OUTPUT_TOO_LONG), then CONDENSE (SUCCESS)
    attempts = manifest_mgr.manifest_data["gemini_attempts"]
    assert len(attempts) == 2
    assert attempts[0]["attempt_type"] == "FULL"
    assert attempts[0]["outcome"] == GeminiOutcome.OUTPUT_TOO_LONG.value
    assert attempts[0]["char_count"] == 12_500

    assert attempts[1]["attempt_type"] == "CONDENSE"
    assert attempts[1]["outcome"] == GeminiOutcome.SUCCESS.value
    assert attempts[1]["char_count"] == 9_800


def test_g3_gemini_condense_failure_terminates_without_full_rotation(tmp_path):
    """G3: If CONDENSE still exceeds 11,000 chars, execution halts without rotating through all models."""
    provider = GeminiProvider(api_key="mock_key")
    provider.client = MagicMock()
    provider.client.models.count_tokens.return_value.total_tokens = 500

    # Both FULL and CONDENSE exceed length
    provider.client.models.generate_content.return_value = MagicMock(text="가" * 12_000)

    manifest_mgr = ManifestManager(artifacts_dir=str(tmp_path / "artifacts"))
    manifest_mgr.initialize("dec-003", "주제")

    with pytest.raises(ValueError, match="허용 범위를 벗어났습니다"):
        provider.generate_content("주제", papers=[], manifest_manager=manifest_mgr)

    # Exactly 2 attempts on gemini-3.8-flash, and no subsequent models called!
    attempts = manifest_mgr.manifest_data["gemini_attempts"]
    assert len(attempts) == 2
    assert all(a["model"] == "models/gemini-3.8-flash" for a in attempts)
    assert attempts[0]["attempt_type"] == "FULL"
    assert attempts[0]["outcome"] == GeminiOutcome.OUTPUT_TOO_LONG.value
    assert attempts[1]["attempt_type"] == "CONDENSE"
    assert attempts[1]["outcome"] == GeminiOutcome.OUTPUT_TOO_LONG.value


def test_g3_gemini_503_fallback_to_next_model(tmp_path):
    """G3: Provider error 503 UNAVAILABLE on first model falls back to second model."""
    provider = GeminiProvider(api_key="mock_key")
    provider.client = MagicMock()
    provider.client.models.count_tokens.return_value.total_tokens = 500

    def mock_generate(**kwargs):
        model = kwargs.get("model")
        if model == "models/gemini-3.8-flash":
            raise Exception("HTTP 503 Service Unavailable")
        return MagicMock(text="다" * 10_000)

    provider.client.models.generate_content.side_effect = mock_generate

    manifest_mgr = ManifestManager(artifacts_dir=str(tmp_path / "artifacts"))
    manifest_mgr.initialize("dec-004", "주제")

    result = provider.generate_content("주제", papers=[], manifest_manager=manifest_mgr)
    assert "다" * 10_000 in result

    attempts = manifest_mgr.manifest_data["gemini_attempts"]
    assert len(attempts) == 2
    assert attempts[0]["model"] == "models/gemini-3.8-flash"
    assert attempts[0]["outcome"] == GeminiOutcome.UNAVAILABLE.value
    assert attempts[1]["model"] == "models/gemini-3.7-flash"
    assert attempts[1]["outcome"] == GeminiOutcome.SUCCESS.value


# ==============================================================================
# G4: Run Log & Manifest Skeleton Preservation Tests
# ==============================================================================

def test_g4_manifest_skeleton_created_before_external_calls(tmp_path):
    """G4: ManifestManager creates skeleton manifest.json and run.log immediately upon initialization."""
    artifacts_dir = str(tmp_path / "artifacts")
    mgr = ManifestManager(artifacts_dir=artifacts_dir)
    mgr.initialize(decision_id="dec-init-test", topic="인공지능 건축", run_id="12345", commit_sha="abcdef")

    manifest_file = os.path.join(artifacts_dir, "manifest.json")
    log_file = os.path.join(artifacts_dir, "run.log")

    assert os.path.exists(manifest_file), "manifest.json must exist immediately"
    assert os.path.exists(log_file), "run.log must exist immediately"

    with open(manifest_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Validate exact minimum schema from §6.1
    assert data["schema_version"] == 1
    assert data["run"]["run_id"] == "12345"
    assert data["run"]["decision_id"] == "dec-init-test"
    assert data["run"]["commit_sha"] == "abcdef"
    assert data["run"]["topic"] == "인공지능 건축"
    assert data["run"]["status"] == "RUNNING"
    assert data["academic_search"]["status"] == "NOT_STARTED"
    assert data["gemini_attempts"] == []
    assert data["report"]["body_length"] is None
    assert data["notion"]["status"] == "NOT_STARTED"
    assert data["infographics"] == []
    assert data["failure"] is None


def test_g4_failure_injection_preserves_artifacts_at_all_stages(tmp_path):
    """G4: Verify that injected failures at each stage preserve manifest and run.log with correct error type."""
    stages = ["ACADEMIC_SEARCH", "GEMINI_GENERATION", "NOTION_PUBLISH"]

    for stage_idx, fail_stage in enumerate(stages):
        sub_dir = str(tmp_path / f"artifacts_fail_{stage_idx}")
        mgr = ManifestManager(artifacts_dir=sub_dir)

        mock_gemini = MagicMock(spec=GeminiProvider)
        mock_notion = MagicMock(spec=NotionPublisher)
        mock_slack = MagicMock(spec=SlackNotifier)
        mock_academic = MagicMock(spec=AcademicProvider)

        if fail_stage == "ACADEMIC_SEARCH":
            mock_academic.search_with_status.side_effect = TimeoutError("OpenAlex connect timeout")
        elif fail_stage == "GEMINI_GENERATION":
            mock_academic.search_with_status.return_value = AcademicSearchResult(
                papers=[], status=SearchStatus.SEARCH_GENUINE_EMPTY, degraded=False
            )
            mock_gemini.generate_content.side_effect = ValueError("Gemini length contract breached")
        elif fail_stage == "NOTION_PUBLISH":
            mock_academic.search_with_status.return_value = AcademicSearchResult(
                papers=[], status=SearchStatus.SEARCH_GENUINE_EMPTY, degraded=False
            )
            mock_gemini.generate_content.return_value = "본문 텍스트" * 1000
            mock_notion.get_or_create_page.side_effect = RuntimeError("Notion API 500 error")

        service = BriefingApplicationService(
            gemini=mock_gemini,
            notion=mock_notion,
            slack=mock_slack,
            academic=mock_academic,
            parent_page_id="test-parent",
            manifest_manager=mgr,
        )

        with patch.dict(os.environ, {"GEMINI_API_KEY": "k", "NOTION_TOKEN": "t", "PARENT_PAGE_ID": "p"}):
            with pytest.raises(Exception):
                service.run_daily_briefing()

        manifest_path = os.path.join(sub_dir, "manifest.json")
        log_path = os.path.join(sub_dir, "run.log")

        assert os.path.exists(manifest_path), f"manifest.json must exist when {fail_stage} fails"
        assert os.path.exists(log_path), f"run.log must exist when {fail_stage} fails"

        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["run"]["status"] == "FAILED"
        assert data["failure"]["stage"] == fail_stage
        assert data["failure"]["error_type"] in ("TimeoutError", "ValueError", "RuntimeError")

        with open(log_path, "r", encoding="utf-8") as f:
            log_text = f.read()
        assert fail_stage in log_text
        assert "ERROR" in log_text


def test_g4_secret_redaction_in_log_and_manifest(tmp_path):
    """G4: Secret sentinels (keys, tokens, hooks, emails) are completely masked in log and manifest."""
    sub_dir = str(tmp_path / "artifacts_redaction")
    mgr = ManifestManager(artifacts_dir=sub_dir)
    mgr.initialize(decision_id="dec-redact", topic="주제")

    secret_key = "AIzaSySecretTokenKey123456789012345678"
    secret_bearer = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    secret_slack = "https://hooks.slack.com/services/T000/B000/SECRET123"
    secret_email = "mailto:confidential_agent@example.com"

    mgr.log(f"Received secret key: {secret_key}")
    mgr.log(f"Authorization header: {secret_bearer}")
    mgr.log(f"Notification url: {secret_slack}")
    mgr.log(f"Openalex user agent: {secret_email}")
    mgr.record_failure("STAGE", "SecretError", f"Failed with {secret_key} and {secret_slack}")

    with open(mgr.log_path, "r", encoding="utf-8") as f:
        log_content = f.read()
    with open(mgr.manifest_path, "r", encoding="utf-8") as f:
        manifest_content = f.read()

    for sentinel in [secret_key, secret_bearer, secret_slack, secret_email]:
        assert sentinel not in log_content, f"Sentinel {sentinel} leaked into run.log!"
        assert sentinel not in manifest_content, f"Sentinel {sentinel} leaked into manifest.json!"

    assert "[REDACTED]" in log_content
    assert "[REDACTED]" in manifest_content


def test_g4_atomic_write_manifest_produces_valid_json(tmp_path):
    """G4: Rapid successive updates maintain atomic validity of manifest.json."""
    sub_dir = str(tmp_path / "artifacts_atomic")
    mgr = ManifestManager(artifacts_dir=sub_dir)
    mgr.initialize("atomic-test", "주제")

    for i in range(10):
        mgr.record_gemini_attempt(f"model-{i}", "FULL", "OUTCOME", i * 1000, 0.5)

    with open(mgr.manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert len(data["gemini_attempts"]) == 10
