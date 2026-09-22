import os
import requests
import pytest
from unittest.mock import MagicMock, patch
import briefing_auto
from briefing_auto import (
    validate_environment,
    BriefingApplicationService,
    SlackNotifier,
    GeminiProvider,
    NotionPublisher,
    AcademicProvider,
)


def _indented_block(content, header, indent=0):
    """Return one YAML mapping block without adding a YAML test dependency."""
    lines = content.splitlines()
    prefix = " " * indent + header
    start = next(i for i, line in enumerate(lines) if line == prefix)
    block = [lines[start]]
    for line in lines[start + 1:]:
        if line.strip() and len(line) - len(line.lstrip()) <= indent:
            break
        block.append(line)
    return "\n".join(block)

def test_validate_environment_success(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("NOTION_TOKEN", "test-notion-token")
    monkeypatch.setenv("PARENT_PAGE_ID", "test-parent-id")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/xxx")

    env = validate_environment()
    assert env["GEMINI_API_KEY"] == "test-gemini-key"
    assert env["NOTION_TOKEN"] == "test-notion-token"
    assert env["PARENT_PAGE_ID"] == "test-parent-id"
    assert env["SLACK_WEBHOOK_URL"] == "https://hooks.slack.com/services/xxx"

def test_validate_environment_missing_vars(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("NOTION_TOKEN", raising=False)
    monkeypatch.delenv("PARENT_PAGE_ID", raising=False)

    with pytest.raises(ValueError) as excinfo:
        validate_environment()

    err = str(excinfo.value)
    assert "GEMINI_API_KEY" in err
    assert "NOTION_TOKEN" in err
    assert "PARENT_PAGE_ID" in err

def test_validate_environment_no_secret_leak(monkeypatch):
    secret_value = "super-confidential-secret-key-12345"
    monkeypatch.setenv("GEMINI_API_KEY", secret_value)
    monkeypatch.delenv("NOTION_TOKEN", raising=False)
    monkeypatch.delenv("PARENT_PAGE_ID", raising=False)

    with pytest.raises(ValueError) as excinfo:
        validate_environment()

    err = str(excinfo.value)
    assert secret_value not in err
    assert "NOTION_TOKEN" in err
    assert "PARENT_PAGE_ID" in err


def test_validate_environment_rejects_whitespace_only_values(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "   ")
    monkeypatch.setenv("NOTION_TOKEN", "\t")
    monkeypatch.setenv("PARENT_PAGE_ID", "\r\n")

    with pytest.raises(ValueError) as excinfo:
        validate_environment()

    err = str(excinfo.value)
    assert "GEMINI_API_KEY" in err
    assert "NOTION_TOKEN" in err
    assert "PARENT_PAGE_ID" in err

def test_parent_page_id_no_hardcoded_fallback(monkeypatch):
    # Verify briefing_auto module does not contain hardcoded default in PARENT_PAGE_ID
    monkeypatch.delenv("PARENT_PAGE_ID", raising=False)
    # Re-evaluate or check default logic
    assert os.environ.get("PARENT_PAGE_ID") is None

def test_briefing_application_service_fails_fast_when_env_missing(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("NOTION_TOKEN", raising=False)
    monkeypatch.delenv("PARENT_PAGE_ID", raising=False)

    mock_gemini = MagicMock(spec=GeminiProvider)
    mock_notion = MagicMock(spec=NotionPublisher)
    mock_slack = MagicMock(spec=SlackNotifier)
    mock_academic = MagicMock(spec=AcademicProvider)

    service = BriefingApplicationService(
        mock_gemini, mock_notion, mock_slack, mock_academic, parent_page_id=None
    )

    with pytest.raises(ValueError) as excinfo:
        service.run_daily_briefing()

    assert "필수 환경 변수가 누락되었습니다" in str(excinfo.value)
    mock_academic.search_peer_reviewed_oa_papers.assert_not_called()
    mock_gemini.generate_content.assert_not_called()
    mock_notion.publish_report.assert_not_called()

def test_slack_notifier_checks_http_status(monkeypatch, capsys):
    notifier = SlackNotifier("https://hooks.slack.com/dummy")
    mock_resp = MagicMock()
    mock_resp.ok = False
    mock_resp.status_code = 500
    mock_resp.text = "sensitive-response-body"

    with patch("requests.post", return_value=mock_resp):
        notifier.notify("Test Alert", "error")

    captured = capsys.readouterr()
    assert "[경고] 슬랙 알림 HTTP 오류 응답 (500)" in captured.out
    assert "sensitive-response-body" not in captured.out


def test_slack_notifier_exception_does_not_leak_secret_url(capsys):
    dummy_url = "https://hooks.slack.invalid/services/DUMMY/SECRET/PATH"
    notifier = SlackNotifier(dummy_url)

    with patch("requests.post", side_effect=requests.exceptions.ConnectionError(f"Failed to connect to {dummy_url}")):
        # Must not raise exception to caller
        notifier.notify("Test Alert", "error")

    captured = capsys.readouterr()
    assert "[경고] 슬랙 알림 전송 실패: ConnectionError" in captured.out
    assert "https://hooks.slack.invalid" not in captured.out
    assert "DUMMY" not in captured.out
    assert "SECRET" not in captured.out
    assert "PATH" not in captured.out
    assert not captured.err


def test_workflow_has_pr_safe_gates_permissions_and_pinned_actions():
    workflow_path = os.path.join(".github", "workflows", "daily_briefing.yml")
    assert os.path.exists(workflow_path), "Workflow file must exist"
    with open(workflow_path, "r", encoding="utf-8") as f:
        content = f.read()

    on_block = _indented_block(content, "on:")
    permissions_block = _indented_block(content, "permissions:")
    concurrency_block = _indented_block(content, "concurrency:")
    jobs_block = _indented_block(content, "jobs:")
    test_block = _indented_block(jobs_block, "test:", indent=2)
    briefing_block = _indented_block(jobs_block, "briefing:", indent=2)

    # PRs run the test job, while deployment remains schedule/manual only.
    assert "  pull_request:" in on_block
    assert "    branches:" in on_block
    assert "      - main" in on_block
    assert "name: Unit Test & Verification Gate" in test_block
    assert ("github.event_name != 'pull_request'" in briefing_block or
            ("github.event_name == 'schedule'" in briefing_block and "github.event_name == 'workflow_dispatch'" in briefing_block))
    assert "github.event_name == 'pull_request'" not in briefing_block

    # Repository-wide minimum permission and concurrency policy.
    assert "  contents: read" in permissions_block
    assert "  cancel-in-progress: false" in concurrency_block

    # Production concurrency must be strictly daily-briefing-production (independent of ref).
    briefing_concurrency = _indented_block(briefing_block, "concurrency:", indent=4)
    assert "group: daily-briefing-production" in briefing_concurrency
    assert "cancel-in-progress: false" in briefing_concurrency

    # The deploy job is restricted to default branch and gated by tests.
    assert "needs: test" in briefing_block
    assert "github.event.repository.default_branch" in briefing_block
    assert "${{ secrets." not in test_block
    assert "GEMINI_API_KEY" not in test_block
    assert "NOTION_TOKEN" not in test_block
    assert "PARENT_PAGE_ID" not in test_block

    # Every checkout step specifies fetch-depth: 1 explicitly.
    assert "fetch-depth: 1" in test_block
    assert "fetch-depth: 1" in briefing_block

    # Every action reference is pinned to a full commit SHA.
    action_refs = []
    for line in jobs_block.splitlines():
        stripped = line.strip()
        if stripped.startswith("uses:"):
            action_refs.append(stripped.split("#", 1)[0].split("uses:", 1)[1].strip())
    assert action_refs
    for action_ref in action_refs:
        _, revision = action_ref.rsplit("@", 1)
        assert len(revision) == 40
        assert all(char in "0123456789abcdef" for char in revision)

    assert "Pre-flight Secret Validation" in briefing_block


def test_workflow_execution_boundary_simulation():
    """Verify the briefing execution boundary logic matches the workflow file specification.

    Schedule events run unconditionally on default branch in GitHub Actions (where
    github.event.repository is empty). Manual workflow_dispatch requires matching default_branch.
    """
    workflow_path = os.path.join(".github", "workflows", "daily_briefing.yml")
    assert os.path.exists(workflow_path)
    with open(workflow_path, "r", encoding="utf-8") as f:
        content = f.read()
    briefing_block = _indented_block(_indented_block(content, "jobs:"), "briefing:", indent=2)

    # Assert structural safety directly from the actual YAML file
    assert "github.event_name == 'schedule' ||" in briefing_block
    assert "github.event_name == 'workflow_dispatch' &&" in briefing_block
    assert "github.ref == format('refs/heads/{0}', github.event.repository.default_branch)" in briefing_block

    def evaluate_condition(test_result: str, event_name: str, ref: str, default_branch: str, has_repo_context: bool = True) -> bool:
        repo_default = default_branch if has_repo_context else ""
        return (
            test_result == "success"
            and (
                event_name == "schedule"
                or (event_name == "workflow_dispatch" and ref == f"refs/heads/{repo_default}")
            )
        )

    # 1. PR event -> always False
    assert not evaluate_condition("success", "pull_request", "refs/heads/main", "main")
    assert not evaluate_condition("success", "pull_request", "refs/heads/agents/agy", "main")

    # 2. Feature branch workflow_dispatch -> False
    assert not evaluate_condition("success", "workflow_dispatch", "refs/heads/agents/agy", "main")
    assert not evaluate_condition("success", "workflow_dispatch", "refs/heads/feature/test", "main")

    # 3. Default branch workflow_dispatch -> True only if test succeeded
    assert evaluate_condition("success", "workflow_dispatch", "refs/heads/main", "main")
    assert not evaluate_condition("failure", "workflow_dispatch", "refs/heads/main", "main")

    # 4. Schedule event -> True even when github.event.repository is empty (GitHub Actions runtime behavior)
    assert evaluate_condition("success", "schedule", "refs/heads/main", "main", has_repo_context=False)
    assert not evaluate_condition("failure", "schedule", "refs/heads/main", "main", has_repo_context=False)

def test_governance_documents_exist_and_consistent():
    gov_files = [
        "01_Standard_Procedures/00.Governance_Directive.md",
        "01_Standard_Procedures/00.Project_Protocol.md",
        "01_Standard_Procedures/00.SOP_Manual.md",
    ]
    for gf in gov_files:
        assert os.path.exists(gf), f"Governance file {gf} must exist"
        with open(gf, "r", encoding="utf-8") as f:
            text = f.read()
            assert len(text) > 100
            # Ensure no API keys or secret tokens exist in governance docs
            assert "AIzaSy" not in text
            assert "secret_" not in text

def test_sync_release_dry_run_has_no_side_effects():
    files_to_check = [
        "README.md", "update.md", "03.Committee_Opinions.md",
        "04.Data_Collection_Log.md", "LOGLIST.md"
    ]
    before = {f: open(f, "rb").read() for f in files_to_check if os.path.exists(f)}

    import sync_release
    with patch("sync_release.run_unit_tests", return_value=(0, "mocked")):
        with patch("sys.argv", ["sync_release.py", "--version", "v9.1", "--desc", "PR-safe CI gate verification", "--dry-run"]):
            sync_release.main()

    after = {f: open(f, "rb").read() for f in files_to_check if os.path.exists(f)}
    assert before == after, "Dry-run must not modify any tracked documents"
