# 2026-09-23 작업지시서 — Codex 주도 다중 에이전트 통합·검증

## 0. 문서 통제

| 항목 | 값 |
|---|---|
| 적용일 | 2026-09-23 KST |
| 대상 저장소 | `blueeye-3184/briefing` |
| 지시서 작성·최초 기준선 책임 | Codex |
| 구현 책임 | AGY |
| 조건부 독립 검토 책임 | Claude — Codex L3 판정 시에만 |
| 최종 검증·종료 선언 책임 | Codex |
| 에이전트 호출 권한 | User 전용 |
| 문서 상태 | `READY_FOR_USER_REVIEW` |
| 원격 기준 | `origin/main@37289e8` |
| 최근 운영 복구 | PR #2, Actions run `35815600995` 성공 |
| P0-4 로컬 후보 | `agents/agy@5180510` (`f7037ff` + `5180510`) |
| P0-4 이전 원격 AGY | `origin/agents/agy@f4bf6b6` — 로컬 후보와 분기됨 |

이 문서는 2026-09-23 작업의 단일 인계 기준이다. 각 에이전트는 작업을 시작하기 전에 이 문서의 기준 커밋, 현재 단계, 허용 범위, 완료 조건을 확인한다.

## 1. 오늘의 목표와 우선순위

### 1.1 필수 완료 목표

1. P0-4 공식자료 수집 기능을 최신 `origin/main@37289e8` 위에 안전하게 통합한다.
2. P0-4 전체 회귀 테스트와 문서 동기화를 검증한다.
3. Codex가 먼저 diff·테스트·운영 경계를 검증하고 Claude 추가 검토가 필요한지 위험 기반으로 판정한다.
4. Claude는 Critical/High 가능성이나 독립 교차검증 필요성이 확인된 경우에만 제한된 범위로 호출한다.
5. 필요한 수정은 AGY가 별도 커밋으로 반영하고 다시 검증한다.
6. Codex가 로컬·원격·PR·CI·실행 상태를 최종 대조한 뒤에만 작업 종료를 선언한다.

### 1.2 조건부 후속 목표

P0-4 최종 검증이 끝난 뒤 User가 명시적으로 다음 에이전트를 호출한 경우에만 진행한다.

1. P0-5 논문 0편 경로 안전화
2. P0-6 Claim–Evidence 품질 게이트 설계·테스트 계약
3. P0-7 Notion pagination·upsert·retry·read-back 구현 준비
4. GitHub Actions Node.js 20 중단 경고와 Ubuntu 이미지 전환 대응

조건부 목표는 선행 게이트 미완료 상태에서 자동 착수하지 않는다.

## 2. 운영 원칙 — 사용자 개입 최소화와 명시적 인계

### 2.1 기본 원칙

1. 모든 작업은 Codex가 시작한다. Codex는 저장소 기준선, 원격 동기화 상태, 선행 커밋과 위험을 확인하고 이 문서에 기록한다.
2. 에이전트 전환은 User만 수행한다. Codex, AGY, Claude는 다른 에이전트를 직접 호출하거나 하위 에이전트를 생성하지 않는다.
3. 한 에이전트가 작업을 시작하면, 해당 단계의 허용 범위 안에서는 중간 승인 질문 없이 구현·검증·기록까지 연속 수행한다.
4. User 개입 지점은 원칙적으로 각 에이전트의 단계 완료 후이다. 완료한 에이전트는 표준 인계 기록을 남기고 정지한다.
5. User는 인계 기록을 직접 확인한 뒤 다음 에이전트를 호출할지 판단한다.
6. 전체 작업의 종료는 Codex의 최종 검증과 종료 선언이 있어야 성립한다. 다른 에이전트의 `완료` 보고만으로 전체 작업을 종료하지 않는다.

### 2.2 단계 중 별도 승인 없이 수행하도록 사전 승인된 작업

각 에이전트는 자신에게 배정된 단계에서 아래 작업을 추가 질의 없이 수행한다.

- 저장소·브랜치·커밋·diff·원격 추적 상태의 읽기
- 작업지시서 범위 안의 코드·테스트·문서 수정
- 선언된 개발 의존성 설치와 로컬 테스트·정적 검사
- 새 작업 브랜치 생성과 로컬 커밋
- 해당 작업 브랜치의 일반 push, PR 생성, PR CI 재실행과 결과 확인
- 실패 원인이 명확하고 범위 내인 경우 수정 후 재검증
- 작업 결과 및 인계 원장 갱신

각 에이전트는 안전한 기본값을 선택하고, 사소한 구현 선택을 User에게 되묻지 않는다. 여러 명령을 실행해야 할 때는 가능한 한 검증 단위로 묶어 불필요한 승인 왕복을 줄인다.

### 2.3 자동 생략할 수 없는 승인과 즉시 중단 조건

작업지시서는 애플리케이션의 샌드박스, 운영체제 권한, 비밀정보 보호, 외부 서비스 정책을 무효화하지 않는다. 다음 항목은 문서만으로 자동 승인 처리할 수 없으며, 필요한 경우 에이전트는 한 번의 명확한 요청으로 중단 사유를 보고한다.

- Secret 값 조회·출력·복사·교체 또는 새 자격증명 등록
- `main` 직접 push, force-push, 원격 브랜치 강제 덮어쓰기
- tag/release 생성·삭제
- 실서비스 Notion·Slack·Gemini 쓰기 또는 유료 대량 API 호출
- 데이터 삭제, 재귀 삭제, 이력 파괴 등 복구 곤란 작업
- 기존 사용자 미커밋 변경과 충돌
- 작업 범위를 바꾸는 아키텍처 결정 또는 요구사항 불일치
- 보안 정책이나 플랫폼이 강제하는 권한 상승 프롬프트

원격 `main` 병합과 운영 수동 실행은 최종 Codex 단계에서만 수행한다. User가 Codex 최종 단계를 호출한 사실을 해당 단계 수행 승인으로 본다. 단, 보호 규칙이나 플랫폼 승인 UI는 그대로 따른다.

### 2.4 현재 3개 터미널과 기본 모델

현재 VS Code 작업은 `Codex`, `agy`, `Claude` 세 개의 전용 터미널과 독립 worktree로 구성돼 있다. 새 에이전트 터미널을 추가하지 않는다.

| 터미널 | worktree | 현재 시작 방식 | 기본 모델·상태 | 기본 용도 |
|---|---|---|---|---|
| `Codex` | `briefing-worktrees/codex` | `codex` | 사용자 설정 `gpt-5.6-sol`, reasoning `medium` | 시작, 명세, 위험 판정, 최종 검증·종료 |
| `agy` | `briefing-worktrees/agy` | `agy` | 런처에서 모델 미고정; 실제 세션 기본 모델을 시작 보고에 기록 | 구현, 테스트, 수정, 로컬·원격 작업 브랜치 준비 |
| `Claude` | `briefing-worktrees/claude` | `Invoke-ClaudeSecure.ps1` | `claude-sonnet-5` | L3 조건을 만족한 독립 pinpoint 검토만 수행 |

`Codex`와 `agy` 터미널 런처는 상호 공급자의 API 자격증명을 제거한다. `Claude`는 DPAPI 보안 래퍼가 학교 Gateway 키를 프로세스에만 주입한다. 한 터미널의 Secret이나 인증 상태를 다른 터미널로 복사하지 않는다.

### 2.5 유연한 모델 라우팅

기본 원칙은 **현재 모델 유지**다. 모델 변경은 검증 강도를 높이거나 비용을 낮출 분명한 이유가 있을 때만 한다.

| 작업 성격 | 실행 터미널 | 모델·reasoning | 변경 판단 |
|---|---|---|---|
| 명세 작성, 일반 코드 검토, 최종 통합 | `Codex` | `gpt-5.6-sol`, medium | 기본값 유지 |
| 단순 diff 분류, 로그 요약, 반복 검증 | `Codex` | `gpt-5.6-luna`, medium 또는 high | 현재 Codex의 `/model` 목록에서 사용 가능할 때만 일시 변경; 없으면 `gpt-5.6-sol` 유지 후 범위·reasoning 축소 |
| 복잡한 회귀 분석, 여러 계약의 충돌 검증 | `Codex` | `gpt-5.6-sol`, high 또는 xhigh | 모델은 유지하고 reasoning만 상향 |
| 구현·테스트·충돌 해결 | `agy` | 현재 세션이 보고한 모델·effort | 런처가 모델·effort를 고정하지 않으므로 시작 보고로 확인; 구현 실패가 반복되거나 AGY가 한계를 근거로 보고할 때만 변경 검토 |
| 공급자 독립 보안·운영 경계 검토 | `Claude` | `claude-sonnet-5` | L3 조건 충족 + User 호출 때만 실행 |

`gpt-5.5`는 학교 Gateway에서 사용 가능하지만 현재 Codex 기본 모델보다 이전 세대이므로 일반 검증을 위해 우선 전환하지 않는다. 동일 입력의 교차 비교가 필요하다는 근거가 있을 때만 제한적으로 사용한다.

학교 Gateway의 모델 사용 가능 여부와 현재 Codex 터미널에서 즉시 선택 가능한지는 별개다. 현재 Codex 사용자 설정에는 FactChat custom provider가 활성화되어 있지 않고 터미널 런처도 API 자격증명을 제거하므로, 별도의 보안 주입·provider 구성이 완료되기 전에는 Gateway 모델을 현재 세션에서 사용할 수 있다고 가정하지 않는다.

Codex 인터랙티브 세션에서는 `/model`로 모델과 reasoning을 바꿀 수 있다. 새 세션은 `codex -m <MODEL>` 또는 비대화형 검증은 `codex exec -m <MODEL> "<PROMPT>"`를 사용한다. 기본 설정 파일을 매번 고치지 말고 일시 변경을 우선한다.

AGY는 새 세션을 시작할 때 `agy --model <MODEL> --effort <low|medium|high>`를 사용할 수 있으나, 모델 이름은 AGY 터미널에서 실제 사용 가능 목록을 확인한 경우에만 지정한다. 현재 런처는 모델을 강제하지 않으므로 추정 모델명을 작업지시서에 하드코딩하지 않는다.

Claude는 현재 보안 래퍼의 기본 `claude-sonnet-5`를 유지한다. Claude 모델 변경이 필요하면 호출 전에 Codex가 변경 사유와 목표 모델을 보고하고 User가 Claude 단계를 호출할 때 확정한다.

### 2.6 다음 터미널·모델 안내 의무

각 에이전트는 단계 종료 보고의 마지막에 다음 네 항목을 반드시 사용자에게 제시한다.

1. **다음 실행 터미널**: `Codex`, `agy`, `Claude`, 또는 `NONE`
2. **권장 모델**: 정확한 모델 ID 또는 `KEEP_CURRENT`
3. **모델 변경 여부**: `NO` 또는 `YES — 변경 사유`
4. **사용자가 전달할 지시문**: 다음 터미널에 붙여 넣을 한 개의 완성된 문장

에이전트는 다음 에이전트를 직접 호출하지 않는다. User가 위 안내를 보고 해당 터미널에서 지시문을 전달한다. 모델 변경이 필요 없으면 불필요한 `/model` 조작을 요구하지 않는다.

## 3. 단계별 책임과 정지 게이트

### G0 — Codex 시작·기준선 확정

상태: `COMPLETE`

Codex 책임:

1. 최신 원격 상태와 작업트리 청결성을 확인한다.
2. P0-4 후보 커밋과 원격 AGY 브랜치의 분기 사실을 확인한다.
3. 당일 장애·핫픽스·CI 실행 결과를 기준선에 반영한다.
4. 에이전트별 범위, 완료 조건, 인계 양식을 작성한다.
5. 학교 BAZE API Gateway의 Codex·모델 지원 여부를 문서와 라이브 모델 목록으로 검증한다.

Codex는 본 지시서를 User에게 보고한 뒤 정지한다. 다음 단계는 User가 AGY를 직접 호출한 경우에만 시작한다.

### G1 — AGY P0-4 통합 구현

시작 조건: User가 AGY에 본 지시서를 지정하여 작업을 토스함.

AGY 필수 작업:

1. 시작 즉시 `git fetch origin --prune`, 현재 브랜치, `git status --short`, `origin/main` SHA를 기록한다.
2. 기존 `origin/agents/agy@f4bf6b6`를 force-push로 덮어쓰지 않는다.
3. 최신 `origin/main@37289e8`에서 새 통합 브랜치를 만든다.
4. P0-4 커밋 `f7037ff`과 문서 동기화 커밋 `5180510`을 순서대로 검토하여 cherry-pick하거나, 충돌 시 의미를 보존해 재적용한다.
5. 공식자료 어댑터, `EvidencePack`, 검증 게이트, 주제 정책과 기존 브리핑 계약의 호환성을 확인한다.
6. 테스트 중 실제 Notion·Slack·Gemini·외부 운영 API 쓰기를 수행하지 않는다.
7. 전체 테스트, `git diff --check`, 필요 시 `sync_release.py --dry-run`을 실행한다.
8. 새 브랜치에 커밋하고 일반 push 및 PR 생성까지 수행한다.
9. CI 결과, PR URL, 로컬 HEAD, 원격 HEAD, ahead/behind 상태를 인계 기록에 남긴다.

G1 완료 조건:

- 최신 `origin/main` 기반의 P0-4 통합 커밋 존재
- 전체 테스트 통과 또는 실패 테스트와 원인이 명시됨
- 작업트리에 의도하지 않은 변경이 없음
- 원격 작업 브랜치와 로컬 HEAD가 일치
- PR과 CI 상태가 기록됨
- AGY가 다른 에이전트를 호출하지 않고 정지함

### G2 — 조건부 독립 검토

기본 상태: `OPTIONAL — DEFAULT SKIP`

검증만을 목적으로 Claude를 관성적으로 호출하지 않는다. G1 이후 User가 Codex를 호출하면 Codex가 먼저 변경 범위, 테스트 강도, 외부 효과와 잔여 불확실성을 확인하여 아래 세 단계 중 하나를 권고한다.

1. **L1 — Codex 단독 검증**: 테스트와 명세로 판단 가능한 일반 변경. 기본 경로다.
2. **L2 — 저비용 보조 검토**: 불확실성은 있으나 보안·실서비스 Critical 위험은 낮은 경우. 현재 Codex의 `/model` 목록에서 `gpt-5.6-luna`를 실제 선택할 수 있을 때만 사용하고 입력 12K·출력 1.5K 토큰을 상한으로 한다. 사용할 수 없으면 `gpt-5.6-sol`을 유지한 채 검토 범위와 reasoning을 낮춰 동일한 토큰 상한을 적용한다.
3. **L3 — Claude pinpoint 검토**: 아래 호출 조건이 하나 이상 충족된 경우에만 사용한다.

Claude 호출 조건:

- Secret 처리, 권한, 인증, prompt injection 또는 데이터 유출 가능성
- GitHub Actions production 경계, 동시 실행, schedule 조건처럼 테스트가 실제 플랫폼 동작을 완전히 모사하기 어려운 변경
- Notion·Slack·Gemini 등 실서비스 쓰기 또는 중복 발행 위험
- 외부 자료의 진위·출처 연결 오류가 게시 신뢰성을 직접 훼손할 가능성
- Codex 검증에서 Critical/High 후보가 발견됐으나 결론이 불명확함
- 핵심 계약 변경이 5개 파일 또는 핵심 diff 300줄을 넘어 한 모델의 단독 검토 위험이 큼

시작 조건: Codex가 L3 필요 사유와 최소 검토 범위를 인계 기록에 남기고, User가 이를 확인한 뒤 Claude를 직접 호출함.

Claude 검토 범위:

1. 기준은 `origin/main@37289e8..G1_HEAD`와 본 작업지시서다.
2. 최대 5개 핵심 파일 또는 핵심 diff 300줄만 검토한다.
3. P0-4 출처 진위, 실패 폐쇄, 중복 제거, timeout/retry, 주제 정책 정합성을 집중 검토한다.
4. 기존 9,000~11,000자 본문 계약, 검증된 서지 계약, Notion 안전 분할의 회귀 여부를 확인한다.
5. 각 finding은 심각도, 파일·라인, 재현 조건, 위험, 최소 수정안을 포함한다.
6. 근거 없는 광범위 리팩터링이나 직접 구현은 하지 않는다.
7. 입력 20K·출력 2K 토큰을 기본 상한으로 하고, findings는 최대 5건으로 제한한다.

G2를 실행한 경우의 완료 조건:

- `Critical`, `High`, `Medium`, `Low`별 finding 또는 `No finding` 명시
- 실행한 검증 명령과 결과 기록
- 수정 필요 여부와 재현 가능한 최소 지시 제공
- Claude가 AGY나 Codex를 직접 호출하지 않고 정지함

Claude 호출 조건이 없으면 Codex는 G2를 `SKIPPED_BY_RISK_GATE`로 기록하고, G1 검토를 위해 호출된 동일 세션에서 추가 User 승인이나 재호출 없이 G4 최종 검증까지 연속 진행한다. 이 경우 Claude 미호출은 검증 누락이 아니다.

### G3 — AGY 보완 작업

시작 조건: G1 이후의 Codex 검토 또는 실행한 G2 검토에서 코드 수정 사항이 확인되고 User가 AGY를 다시 호출함.

AGY는 finding별 재현 → 최소 수정 → 회귀 테스트 → 별도 커밋 → PR 갱신 순서로 수행한다. 각 finding의 처리 상태를 `resolved`, `accepted risk`, `not reproducible` 중 하나로 기록하고 근거를 남긴다.

Critical 또는 High가 해결되지 않은 상태에서는 최종 병합 준비 완료로 보고하지 않는다.

### G4 — Codex 최종 검증·통합·종료

시작 조건: User가 구현 결과와, 실행한 경우 독립 검토·보완 결과를 확인한 뒤 Codex를 호출함.

Codex 필수 검증:

1. `git fetch origin --prune` 후 `origin/main`, PR HEAD, 로컬 후보 HEAD를 다시 읽는다.
2. 작업지시서의 기준선 이후 모든 커밋과 부모 관계를 확인한다.
3. 로컬·원격 작업 브랜치가 동기화됐는지 확인한다.
4. 변경 파일과 G1/G2/G3 인계 기록을 대조한다.
5. 전체 테스트와 필수 정적 검사를 독립 재실행한다.
6. PR CI와 required check가 성공했는지 확인한다.
7. 미해결 Critical/High finding이 0건인지 확인한다. G2를 생략했다면 위험 게이트 생략 사유가 타당한지 재확인한다.
8. 조건 충족 시 보호된 PR 경로로 병합하고, 최신 `main`에서 필요한 운영 수동 실행을 확인한다.
9. 상태 문서·날짜별 이력·Decision ID·5대 문서의 동기화 여부를 확인한다.
10. 최종 원격 `main` SHA, PR, CI/run URL, 테스트 수, 잔여 위험을 보고한다.

Codex만 전체 작업에 대해 `COMPLETE`를 선언할 수 있다. 하나라도 검증되지 않으면 `PARTIAL` 또는 `BLOCKED`로 보고하고 종료를 선언하지 않는다.

## 4. 표준 인계 기록

각 에이전트는 단계 종료 시 아래 형식을 응답과 자신의 worktree에 있는 단계별 인계 파일에 동일하게 남긴다. 원본 작업지시서는 Codex worktree에 있으므로 AGY와 Claude는 이를 읽기 전용 기준으로 사용하고 직접 수정하지 않는다.

```text
[Gate] G1 / G2 / G3 / G4
[Status] COMPLETE / PARTIAL / BLOCKED
[Agent] Codex / AGY / Claude
[Current Model] 실제 런타임 모델 ID와 reasoning/effort — 확인할 수 없으면 UNKNOWN과 사유
[Started] YYYY-MM-DD HH:mm:ss KST
[Finished] YYYY-MM-DD HH:mm:ss KST
[Baseline] origin/main SHA, 시작 브랜치, 시작 HEAD
[Changed] 파일별 변경 이유 또는 read-only 검토 범위
[Commits] 생성·검토한 커밋 SHA
[Verified] 명령, 테스트 수, 결과
[Remote Sync] local HEAD, upstream HEAD, ahead/behind, PR, CI
[Security] Secret 비노출, 실서비스 호출 여부
[Findings] 심각도별 결과와 미해결 항목
[Risks] 남은 위험과 영향
[Next Eligible Agent] 권고 대상만 기록 — 직접 호출 금지
[Next Terminal] Codex / agy / Claude / NONE
[Next Model] 정확한 모델 ID / KEEP_CURRENT
[Model Change] NO / YES — 변경 사유
[User Prompt] 다음 터미널에 전달할 완성된 한 문장
[User Gate] 다음 에이전트 호출 전 User 확인 필요
```

단계별 인계 파일은 worktree 루트의 `HANDOFF_2026-09-23_<GATE>_<AGENT>.md`로 고정한다. 예를 들어 G1 AGY 결과는 `$env:AGY_WORKTREE\HANDOFF_2026-09-23_G1_AGY.md`에 작성하고 해당 단계 커밋에 포함한다. Codex는 다음 호출에서 인계 파일의 커밋·SHA·실행 증거를 검증한 뒤 이 문서의 단계 원장을 갱신한다.

## 5. 실시간 동기화 판단 규칙

에이전트는 `최신`, `동기화 완료`, `병합 가능`을 추정으로 쓰지 않는다. 반드시 아래 증거를 함께 기록한다.

1. `git rev-parse HEAD`
2. `git rev-parse origin/main`
3. `git rev-parse @{upstream}` 또는 upstream 미설정 사실
4. `git rev-list --left-right --count HEAD...@{upstream}`
5. `git status --short --branch`
6. PR 상태와 CI URL

fetch 이전의 원격 추적 ref는 실시간 상태로 간주하지 않는다. 시각은 KST로 기록하며, 확인하지 못한 시각은 추정하지 않는다.

## 6. 학교 BAZE API Gateway 및 Codex 모델 확인

### 6.1 확인한 공식 문서

- 학교 Gateway 개요: `https://docs.factchat.kr/docs/kumoh/api-gateway/getting-started/overview`
- 학교 Gateway 모델 목록: `https://docs.factchat.kr/docs/kumoh/api-gateway/getting-started/models`
- 학교 Gateway Codex CLI 연동: `https://docs.factchat.kr/docs/kumoh/api-gateway/integrations/codex-cli`
- OpenAI Codex 인증: `https://learn.chatgpt.com/docs/auth`
- OpenAI custom provider 설정: `https://learn.chatgpt.com/docs/config-file/config-advanced`

### 6.2 판정

1. 사용자가 발급받은 키는 Anthropic 전용 Claude 키가 아니라 국립금오공과대학교 BAZE API Gateway 키다.
2. 이 키 하나로 학교 Gateway에 허용된 Claude, GPT, Gemini 등 여러 제공업체 모델을 호출할 수 있다.
3. Codex CLI는 `model_provider = "factchat"`, Gateway Base URL, `env_key = "FACTCHAT_API_KEY"`, `wire_api = "responses"` 구성으로 연결할 수 있다.
4. OpenAI 공식 카탈로그에는 `gpt-5.5`와 `gpt-5.4-nano`가 별개 모델로 존재하며 `gpt-5.5-nano`는 확인되지 않는다.
5. 학교 Gateway 문서에도 `gpt-5.5-nano`는 없다. `gpt-5.4-nano`는 레거시이며 권장 대체 모델은 `gpt-5.6-luna`다.
6. `gpt-5-nano`는 학교 Gateway의 무료 모델로 분류되어 API 호출 대상에서 제외된다.

### 6.3 2026-09-23 라이브 계정 확인

DPAPI로 암호화 저장된 사용자 Gateway 키를 메모리에서만 사용해 `/v1/gateway/models/`를 조회했다. 키 값은 출력·기록하지 않았다.

- 인증: 성공
- 계정에 반환된 전체 모델: 75개
- 확인된 OpenAI 모델: `gpt-5.5`, `gpt-5.6-luna`, `gpt-5.6-sol`, `gpt-5.6-terra`
- 라이브 목록에서 미확인: `gpt-5.5-nano`, `gpt-5.4-nano`, `gpt-5-nano`

따라서 이 계정으로 Codex CLI에서 `gpt-5.5`를 선택하는 구성은 지원 대상이다. 저비용·고속 작업 모델이 필요하면 현재 계정에서 실제 확인된 `gpt-5.6-luna`를 사용한다. 모델 가용성은 조직 설정에 따라 바뀔 수 있으므로 실행 시작 시 `/models/`를 다시 확인한다.

### 6.4 Codex 설정 기준

```toml
model = "gpt-5.5"
model_provider = "factchat"

[model_providers.factchat]
name = "BAZE"
base_url = "https://factchat.mindlogic-kr-api.com/v1/gateway"
env_key = "FACTCHAT_API_KEY"
wire_api = "responses"
```

Secret은 저장소나 작업지시서에 기록하지 않는다. 현재 키는 Claude 보안 실행용 DPAPI 파일에 보관돼 있으므로 Codex 연결을 실제 활성화하려면 같은 키를 평문 파일로 복제하지 않는 별도 보안 주입 절차가 필요하다. 이 문서 작성 단계에서는 사용자 전역 Codex 설정과 Secret 저장 방식을 변경하지 않는다.

## 7. 오늘 작업 종료 기준

아래 조건을 모두 만족해야 Codex가 종료를 선언한다.

- P0-4가 최신 `main` 계열에 통합됨
- 전체 로컬 테스트와 PR CI 통과
- 미해결 Critical/High finding 0건. Claude 미호출 시 Codex 위험 게이트 판정 근거 존재
- 원격 `main`, PR HEAD, 로컬 기록의 SHA 일치 관계 확인
- 실서비스 호출 여부와 결과가 명시됨
- 상태·이력·거버넌스 문서가 실제 상태와 일치
- 최종 PR과 Actions run URL 보존
- Codex 최종 검증 보고 완료

## 8. 단계 원장

| Gate | 담당 | 상태 | 기준/결과 | 다음 사용자 판단 |
|---|---|---|---|---|
| G0 | Codex | COMPLETE | `origin/main@37289e8`, 지시서 작성, Gateway 라이브 모델 확인 | 지시서 검토 후 AGY 호출 완료 |
| G1 | AGY | COMPLETE | P0-4 최신 main 통합, PR #3 생성 (`commit 554f481`), 78 tests 통과 | G1 확인 후 Codex G2 검토 호출 완료 |
| G2 | Codex | COMPLETE | Codex 대체 검토, 2건의 Medium Finding 도출 (`HANDOFF_2026-09-23_G2_CODEX.md`) | G2 확인 후 AGY G3 보완 호출 완료 |
| G3 | AGY | COMPLETE | G2 Finding 2건 조치 (`commit 26f26fa`, `96cebbe`), 84 tests 통과, PR #3 CI 성공 | G3 확인 후 Codex G4 최종 검증 호출 완료 |
| G4 | Codex | COMPLETE | PR #3 최종 검증 및 main 병합 (`dd164b0`), 84 tests 통과, 전체 작업 완료 | 전체 P0-4 작업 종료 선언 |

이 원장은 상태 변경 시 과거 결과를 삭제하지 않고 Codex가 갱신한다. AGY와 Claude는 자신의 worktree에 단계별 인계 파일을 남기며, 다른 단계의 완료나 전체 작업 완료를 대신 선언하지 않는다.

## 9. 현재 사용자 실행 안내

```text
[Next Terminal] NONE
[Next Model] NONE
[Model Change] NO
[User Prompt] P0-4 공식자료 수집 인터페이스 통합 및 검증, PR #3 main 병합이 성공적으로 완료되었습니다.
```

