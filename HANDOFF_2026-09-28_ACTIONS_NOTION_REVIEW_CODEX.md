# HANDOFF: G1~G4 독립 검토 및 보완 (Codex)

[Gate] REVIEW — G1 / G2 / G3 / G4
[Status] COMPLETE
[Agent] Codex
[Started] 2026-09-28 18:47 KST
[Finished] 2026-09-28 19:18 KST
[Baseline] `origin/main@dd164b06b7c455425432e16ec08c455449a0f388`; 검토 대상 `5fcc07b6e0c01df9eba0cd844a8bd4fd118f6088`; 보완 branch `fix/actions-provider-observability-review-2026-09-28`
[Scope]
- AGY의 G1~G4 구현 diff, 인계서, workflow, provider 상태 계약, manifest 보존과 테스트를 독립 검토했다.
- G5~G6 구현 및 운영 API 실행은 수행하지 않았다.

[Verified Before Fix]
- 공식 action tag SHA를 각 공급자 저장소의 `git ls-remote`로 대조했다.
  - checkout v7.0.1: `3d3c42e5aac5ba805825da76410c181273ba90b1`
  - setup-python v7.0.0: `5fda3b95a4ea91299a34e894583c3862153e4b97`
  - upload-artifact v7.0.1: `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`
- AGY 원본 commit에서 `python -m pytest -q tests -p no:cacheprovider`: 102 passed.

[Findings]
- Critical 1 — `secret_...` redaction 정규식이 전체 token을 capture group으로 다시 삽입해 원문 Secret을 보존했다.
- High 1 — OpenAlex 후보가 존재하지만 Crossref가 timeout/429/5xx로 실패할 때 `SEARCH_GENUINE_EMPTY`로 오분류될 수 있었다.
- High 1 — Gemini CONDENSE 중 provider 오류가 별도 attempt로 기록되지 않았고 UNKNOWN/INVALID/SAFETY 오류도 다음 모델 fallback으로 진행했다.
- Medium 1 — 명세에 요구된 OpenAlex query 간 최소 간격이 구현되지 않았고 5xx/exception backoff에 `max_backoff` 상한이 일관 적용되지 않았다.

[Changed]
- `manifest_manager.py`: legacy `secret_` 및 현재 `ntn_` Notion token을 suffix 전체 비노출 형태로 수정했다.
- `briefing_auto.py`:
  - query 간 주입 가능한 간격을 추가했다.
  - 모든 exponential backoff에 상한을 적용했다.
  - Crossref rate limit/unavailable/invalid response가 genuine-empty로 사라지지 않게 상태를 승격했다.
  - Gemini fallback을 rate limit/unavailable/timeout으로 제한했다.
  - 404/model-not-found는 model unavailable로 명시 분류했다.
  - CONDENSE provider 오류를 `attempt_type=CONDENSE`로 기록한 뒤 허용된 경우에만 다음 모델로 이동한다.
- `tests/test_g1_to_g4_actions_and_providers.py`: 위 finding 5개 경로에 대한 회귀 테스트를 추가했다.
- `WORK_DIRECTIVE_2026-09-28_ACTIONS_NOTION_INFOGRAPHIC.md`: 로컬 검증 및 검토 상태를 원장에 반영했다.

[State Contract]
- OpenAlex 정상 empty와 OpenAlex/Crossref provider failure는 분리된다.
- Gemini 모델 회전은 `RATE_LIMITED`, `UNAVAILABLE`, `TIMEOUT`에만 허용된다.
- FULL과 CONDENSE는 독립 attempt로 기록된다.

[Verified]
- 보완 대상: 27 passed in 19.62s.
- 전체: 107 passed in 26.86s.
- `git diff --check`: 0 issues.
- pyright는 로컬에 설치되지 않아 미실행. 프로젝트 필수 gate에는 포함되지 않는다.

[Remote Sync]
- 현재 보완 브랜치는 로컬 상태이며 push/PR 전이다.
- `origin/main`은 `dd164b0`; main 병합은 수행하지 않았다.

[Security]
- 실제 Secret 조회·출력 없음.
- 실제 OpenAlex/Notion/Gemini/Slack 운영 API 호출 없음.
- 회귀 테스트의 가상 token sentinel만 사용했다.

[Findings After Fix]
- Critical: 0 open
- High: 0 open
- Medium: 0 open
- Low: 0 open

[Risks]
- PR CI가 아직 실행되지 않았다.
- G5~G6 및 전체 통합 독립 검토가 남아 있다.
- 운영 workflow/Notion read-back은 User 승인 전까지 미실행이다.

[Next Eligible Agent] Agent B — G5~G6, 단 G1~G4 보완 브랜치의 push 및 PR CI 성공 후 착수
[Next Terminal] 현재 Codex worktree 또는 User가 지정한 G5~G6 작업트리
[Next Model] KEEP_CURRENT
[User Prompt] G1~G4 보완 PR의 CI 성공을 확인한 뒤 해당 head에서 G5~G6을 구현하세요. InfographicSpec 검증, headless PNG, Notion File Upload/image block/read-back, idempotent resume를 테스트·커밋·인계하고 운영 API는 실행하지 마세요.
[User Gate] PR 생성은 허용된 개발 흐름이다. main 병합과 운영 실행은 별도 User 승인 필요.
