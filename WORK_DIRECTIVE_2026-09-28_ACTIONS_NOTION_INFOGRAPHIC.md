# 2026-09-28 작업지시서 — GitHub Actions 반복 실패 복구 및 Notion 인포그래픽 게시

## 0. 문서 통제 정보

| 항목 | 값 |
|---|---|
| 문서 상태 | `READY_FOR_IMPLEMENTATION` |
| 대상 저장소 | `blueeye-3184/briefing` |
| 장애 분석 run | `36366832887` |
| 장애 run URL | <https://github.com/blueeye-3184/briefing/actions/runs/36366832887> |
| 장애 checkout SHA | `37289e8aa4536f6c8e77b857a34d8ae54f197490` |
| 작업 기준 원격 SHA | `origin/main@dd164b06b7c455425432e16ec08c455449a0f388` |
| 선행 작업 | 2026-09-23 P0-4 공식자료 인터페이스 통합 완료, PR #3 병합 |
| 작성 기준 | 2026-09-28 KST |
| 최종 완료 선언자 | Codex 최종 검증 단계 |

이 문서는 다른 대화의 문맥을 전혀 받지 않은 agent도 작업할 수 있도록 작성한 단일 실행 기준이다. 구현 agent는 작업 전에 이 문서 전체를 읽고 원격 상태를 새로 조회한 다음 자신의 기준선을 인계 파일에 기록한다.

`READY_FOR_IMPLEMENTATION`은 지시서가 준비됐다는 뜻이지 구현 완료가 아니다. 현재 G1~G6은 모두 미착수다.

---

## 1. 목적과 최종 성공 상태

### 1.1 목적

기존 P0-4 공식자료 통합 결과를 보존하면서 다음 운영 결함을 함께 해결한다.

1. `ubuntu-latest`와 Node.js 20 기반 GitHub Action에 따른 환경 경고와 재현성 저하
2. OpenAlex HTTP 429를 정상 검색 결과 0건처럼 취급하는 상태 분류 결함
3. Gemini 출력 길이 초과와 provider 장애를 같은 fallback 흐름으로 처리하는 결함
4. 실패 run에서 `run.log`와 `manifest.json`이 만들어지지 않아 artifact가 남지 않는 결함
5. Notion에 검증 가능한 인포그래픽 PNG를 생성·업로드하지 않는 기능 공백
6. 재실행 시 페이지나 이미지가 중복될 수 있는 idempotency 공백

### 1.2 최종 성공 조건

- OpenAlex 429와 genuine-empty가 서로 다른 상태로 기록된다.
- provider failure를 근거 논문이 있는 정상 보고서처럼 조용히 게시하지 않는다.
- Gemini 429/503/timeout/길이 오류가 분리되고, 길이 초과는 제한된 축약 재생성을 사용한다.
- 모든 실행에서 시작 직후 `run.log`와 `manifest.json`이 생성되며 성공·실패와 무관하게 artifact 대상이 된다.
- runner가 `ubuntu-24.04`로 고정되고 Node.js 20 deprecated 경고가 0건이다.
- 검증된 수치만 사용한 PNG를 Notion File Upload API와 image block으로 게시한다.
- 게시 후 read-back으로 텍스트와 이미지 수를 확인한다.
- 동일 run/decision 재실행에서 중복 페이지와 중복 이미지가 생기지 않는다.
- 전체 단위 테스트, `git diff --check`, PR CI가 성공한다.
- User가 승인한 운영 수동 실행에서 텍스트와 이미지가 실제 확인된다.
- Critical/High 미해결 finding이 0건이다.

운영 Notion 페이지에서 이미지까지 확인하지 못하면 코드와 CI가 성공해도 전체 상태는 `PARTIAL`이다.

---

## 2. 확정된 장애 사실

### 2.1 Run 36366832887

Run은 2026-09-28 10:39:48 KST에 schedule로 시작해 10:49:08 KST에 실패했다.

| 단계 | 결과 | 확인 내용 |
|---|---|---|
| Unit Test & Verification Gate | 성공 | 설치, 단위 테스트, diff 점검 성공 |
| Checkout | 성공 | `main@37289e8` checkout |
| Python | 성공 | Python 3.13.15 |
| Secret pre-flight | 성공 | 필수 Secret 누락이 직접 원인이 아님 |
| Run Daily Briefing | 실패 | OpenAlex 429 이후 Gemini fallback 전체 실패 |
| Upload Run Artifacts | step 성공 | 파일이 없어 실제 artifact는 0개 |
| 최종 conclusion | failure | Python `ValueError`, exit code 1 |

실제 runner 이미지는 Ubuntu 24.04였지만 workflow 선언은 `ubuntu-latest`였다. 우연히 24.04가 선택된 것이므로 고정 상태가 아니다.

### 2.2 실패 흐름

1. OpenAlex 익명 검색 3개 쿼리가 모두 HTTP 429 `Rate limit exceeded`를 반환했다.
2. 현재 코드는 이를 `openalex_http_error: 3`으로만 집계하고 검색 결과 0건과 유사한 흐름으로 계속했다.
3. 엄격 적격성 게이트는 `0/10`이었다.
4. Gemini 입력은 논문 근거가 없는 251 tokens였다.
5. `gemini-3.8-flash`: 12,419자로 9,000~11,000자 계약 초과.
6. `gemini-3.7-flash`: HTTP 503 `UNAVAILABLE`.
7. `gemini-3.6-flash`: 11,574자, `gemini-2.5-flash`: 12,650자, `gemini-2.5-flash-lite`: 11,555자로 모두 상한 초과.
8. 마지막 길이 오류가 `ValueError`로 전파되어 exit code 1이 됐다.
9. workflow는 `*.log`와 `manifest.json`을 찾았지만 생성된 파일이 없어 artifact가 0개였다.
10. 보고서 생성 전에 종료되어 Notion 게시 단계에는 도달하지 못했다.

### 2.3 직접 원인과 비원인

직접 원인:

- rate limit/provider failure와 genuine-empty를 구분하지 않는 상태 모델
- 근거 논문 0건이어도 정상 장문 생성을 시도하는 오케스트레이션
- 길이 초과 때 동일 full generation을 다음 모델에서 반복하는 fallback
- 실행 시작 시 진단 파일을 만들지 않는 로깅 구조

직접 원인이 아닌 것:

- Secret 누락과 의존성 설치: 모두 성공했다.
- Notion API 장애: 게시 단계에 도달하지 않았다.
- AFC 경고: 개선 대상일 수 있지만 exit code 1의 원인은 아니다.
- Node.js 20 경고: 직접 원인은 아니지만 G1에서 제거할 운영 부채다.

### 2.4 기준선 주의

장애 run은 `37289e8`에서 실행됐다. 이후 2026-09-28 12:43 KST에 PR #3이 `main@dd164b0`으로 병합됐다. 구현 agent는 장애 SHA가 아니라 최신 `origin/main`에서 시작해야 한다. 장애 재현 테스트에는 `37289e8` 로그의 입력·오류 순서를 fixture로 보존한다.

---

## 3. 보안·운영 불변조건

- Secret, token, webhook URL, Notion page ID 원문을 조회·출력·복사·artifact 저장·커밋하지 않는다.
- 환경변수는 존재 여부만 검사하고 값은 로그에 쓰지 않는다.
- `Authorization`, `Cookie`, API key query parameter와 request header 전체를 직렬화하지 않는다.
- 테스트는 실제 Notion, Gemini, Slack, OpenAlex 운영 API를 호출하지 않는다.
- 운영 `workflow_dispatch`, Notion 게시, Slack 전송은 User 승인 전 실행하지 않는다.
- `permissions: contents: read`, timeout, concurrency, PR production skip 경계를 약화하지 않는다.
- 실패를 숨기려고 예외를 삼키거나 `continue-on-error`를 추가하지 않는다.
- 길이를 맞추려고 문자열을 임의 절단해 게시하지 않는다.
- Gemini가 이미지 URL, 파일 경로, 수치, source ID를 임의 생성하게 하지 않는다.
- 외부 공개 이미지 호스팅, 임의 embed, 대화형 HTML은 범위 밖이다.

---

## 4. 시작 절차와 주요 코드 위치

### 4.1 기준선 기록

모든 agent는 아래 결과를 인계 파일 `[Baseline]`에 기록한다.

```powershell
git fetch origin --prune
git rev-parse HEAD
git rev-parse origin/main
git status --short --branch
git rev-list --left-right --count HEAD...origin/main
```

작업 브랜치는 최신 `origin/main`에서 만든다.

- G1~G4 권장: `fix/actions-provider-observability-2026-09-28`
- G5~G6 권장: `feat/notion-infographic-2026-09-28`

사용자 변경이 있으면 덮어쓰거나 삭제하지 않는다. 충돌 가능성이 있으면 파일과 범위를 먼저 보고한다.

### 4.2 코드 위치

| 관심사 | 현재 위치 | 테스트 위치 |
|---|---|---|
| workflow | `.github/workflows/daily_briefing.yml` | governance 또는 신규 workflow 정책 테스트 |
| OpenAlex 검색 | `briefing_auto.py`의 AcademicProvider | `tests/test_academic_provider.py` |
| Gemini | `briefing_auto.py`의 `GeminiProvider` | `tests/test_gemini_provider.py` |
| Notion | `briefing_auto.py`의 `NotionPublisher` | `tests/test_notion_infrastructure.py` |
| orchestration | `BriefingService.run_daily_briefing` | governance/domain 테스트 |
| P0-4 공식자료 | `official_sources/` | `tests/official_sources/` |

책임 분리가 필요하면 작은 패키지로 분리할 수 있지만 공개 인터페이스와 기존 테스트 호환성을 보존하고 대규모 재작성은 피한다.

---

## 5. 공통 상태·데이터 계약

문자열 로그만으로 상태를 표현하지 말고 enum/dataclass 또는 동등한 typed model을 정의한다. 명칭은 스타일에 맞게 조정할 수 있지만 의미는 유지한다.

### 5.1 검색 상태

```text
SEARCH_OK                 정상 응답, 후보 또는 적격 결과 존재
SEARCH_GENUINE_EMPTY      모든 요청이 정상 응답했으나 결과 없음
OPENALEX_RATE_LIMITED     재시도 후에도 429 지속
PROVIDER_UNAVAILABLE      timeout, 연결 오류, 재시도 가능한 5xx 지속
PROVIDER_INVALID_RESPONSE JSON/schema 오류 또는 검증 불가 응답
```

- `OPENALEX_RATE_LIMITED`를 `SEARCH_GENUINE_EMPTY`로 변환하지 않는다.
- 일부 쿼리 실패 시 성공·실패 수와 사용 결과를 함께 기록한다.
- 모든 쿼리가 실패하고 적격 자료가 0건이면 정상 품질로 승격하지 않는다.

### 5.2 Gemini 시도 결과

```text
SUCCESS / RATE_LIMITED / UNAVAILABLE / TIMEOUT
OUTPUT_TOO_SHORT / OUTPUT_TOO_LONG / INVALID_RESPONSE
SAFETY_BLOCKED / UNKNOWN_ERROR
```

각 시도는 모델명, 시도 종류(`FULL`/`CONDENSE`), 결과 분류, 본문 길이, 경과시간을 기록한다. 오류 전문과 Secret은 manifest에 넣지 않는다.

### 5.3 전체 실행/게시 상태

```text
PUBLISHED_TEXT_AND_IMAGES
PUBLISHED_TEXT_IMAGE_PARTIAL
DEGRADED_PROVIDER_FAILURE
PUBLISH_FAILED
GENERATE_FAILED
```

- `PUBLISHED_TEXT_AND_IMAGES`: 텍스트, 모든 이미지, image block, read-back 일치
- `PUBLISHED_TEXT_IMAGE_PARTIAL`: 텍스트는 게시됐으나 이미지 일부 또는 read-back 불일치
- `DEGRADED_PROVIDER_FAILURE`: 공급자 실패가 품질 상태에 명시되고 정상 보고서로 위장되지 않음
- `PUBLISH_FAILED`: 생성물은 준비됐지만 Notion 게시 실패
- `GENERATE_FAILED`: 생성 계약 미충족

### 5.4 InfographicSpec

```text
InfographicSpec
- infographic_id: 결정적 식별자
- title: str
- chart_type: allowlist 값(bar, line, horizontal_bar 등)
- labels: list[str]
- values: list[finite number]
- unit: str
- source_ids: list[str] 또는 항목별 mapping
- caption: str
- alt_text: str
```

검증 규칙:

- labels/values 길이가 같고 1개 이상이어야 한다.
- 값은 NaN/Infinity가 아닌 finite number여야 한다.
- 모든 값 또는 series는 검증된 source ID와 연결돼야 한다.
- title/caption/alt text는 비어 있으면 안 된다.
- chart type은 allowlist만 허용한다.
- 빈 데이터는 이미지 생성 대신 `NO_INFOGRAPHIC_DATA`로 처리한다.
- renderer는 외부 URL을 가져오지 않는다.
- 파일명은 사용자 입력이 아니라 `infographic_id` 기반 안전한 이름을 사용한다.

### 5.5 Idempotency key

1. Actions: `GITHUB_RUN_ID` + topic/decision ID
2. 로컬/테스트: 명시적으로 주입한 decision ID
3. 날짜 기반 제목만을 유일키로 쓰지 않는다.

동일 key 재실행 시 기존 페이지/블록을 조회하고 재사용하거나 안전하게 갱신한다. 제목 검색 후 이미지를 무조건 append하는 구현은 금지한다.

---

## 6. Gate별 작업 명세

### G1 — GitHub Actions runtime 고정

목표: runner와 action runtime을 재현 가능하게 고정하고 Node.js 20 경고를 제거한다.

작업:

1. workflow의 모든 `ubuntu-latest`를 `ubuntu-24.04`로 변경한다.
2. checkout/setup-python/upload-artifact를 작업 시점의 공식 Node.js 24 지원 stable release로 갱신한다.
3. 공식 저장소 release/tag와 commit을 확인한 뒤 full SHA로 고정한다. 추측 SHA는 금지한다.
4. 주석에 release 버전을 남긴다.
5. Python 3.13, 권한, timeout, concurrency, PR production skip 조건을 유지한다.
6. artifact의 `if: always()`를 유지하고 G4 생성 경로와 맞춘다.
7. 정책 테스트로 `ubuntu-latest` 0건, 허용 action의 40자리 SHA, production 보안 경계를 검증한다.

완료 조건:

- 정적 테스트 성공, CI에서 Node.js 20 경고 0건, Ubuntu 24.04 확인
- 인계서에 action/release/full SHA/공식 확인 URL/확인 시각 기록

공식 Node.js 24 release/SHA를 확인할 수 없으면 임의 진행하지 말고 `BLOCKED`로 기록한다.

### G2 — OpenAlex 429 및 provider failure 방어

목표: rate limit, provider 장애, genuine-empty를 분리하고 근거 부족 상태를 생성·게시까지 전달한다.

작업:

1. OpenAlex 호출을 테스트 가능한 adapter 경계로 분리한다.
2. 429의 `Retry-After` 정수 초와 HTTP-date를 지원한다. 비정상·음수·과도한 값은 bounded fallback을 사용한다.
3. header가 없으면 bounded exponential backoff를 적용한다.
4. 재시도 수, 기본/최대 backoff, 쿼리 간격을 한 설정 위치에서 관리한다.
5. sleep/clock을 주입해 테스트에서 실제 대기하지 않는다.
6. `OPENALEX_MAILTO` 같은 polite-pool 식별자를 선택 주입하되 값은 숨긴다. manifest에는 설정 여부만 기록한다.
7. query별 요청 수, 429 수, 성공 여부, 결과 수를 수집한다.
8. 지속 429, timeout/5xx, 정상 200 empty를 서로 다른 상태로 반환한다.
9. 모든 query 실패 + 논문 0건에서는 정상 장문 생성으로 바로 진행하지 않는다.
10. 일부 성공 시 사용 자료와 degraded 상태를 함께 전달한다.

권장 반환 구조:

```text
AcademicSearchResult
- papers
- status
- query_metrics
- rejection_counts
- provider_failures
- degraded: bool
```

필수 테스트:

- 200 결과 있음/진짜 empty
- 429 + Retry-After 후 성공
- 429 최대 재시도 후 rate-limited
- Retry-After HTTP-date와 비정상 값
- timeout/5xx
- 일부 query 성공 + 일부 429
- 모든 query 실패 + 0건에서 정상 생성 차단
- polite-pool 값과 인증 정보 비노출

완료 조건: 429가 `openalex_http_error` 숫자만 남기고 empty 흐름으로 사라지는 경로가 없어야 한다.

### G3 — Gemini 길이 계약과 fallback 수정

목표: provider 오류와 콘텐츠 계약 오류를 분리하고 길이 초과를 제한된 축약 재생성으로 처리한다.

작업:

1. 최소·최대 길이와 재생성 횟수를 한 설정 위치에서 관리한다. 기본 계약은 9,000~11,000자다.
2. 429, 503, timeout, safety, invalid response, unknown 오류를 분류한다.
3. 최초 생성은 `FULL` 시도로 기록한다.
4. 너무 길면 동일 텍스트를 입력으로 `CONDENSE` prompt를 사용한다. 길이, 인용/source ID/핵심 수치 보존, 새 사실·URL 추가 금지를 명시한다.
5. 너무 짧은 경우도 별도 계약 오류로 분류하고 보강 횟수를 제한한다.
6. 재생성 횟수는 작은 명시적 상한을 둔다. 상한 소진 후 모든 모델에서 full generation을 반복하지 않는다.
7. provider 429/503/timeout일 때만 다음 모델 fallback을 고려한다.
8. 모든 시도와 최종 실패 요약을 manifest에 남긴다.
9. 검색 degraded 상태를 prompt와 최종 품질 메타데이터에 반영한다.
10. 임의 truncation은 금지한다.

필수 테스트:

- 정상 범위 첫 성공
- 503 후 다음 모델 성공
- 429/timeout 분류
- 길이 초과 → CONDENSE 성공
- CONDENSE 횟수 제한과 최종 실패
- 길이 오류 때문에 모든 모델 full generation을 반복하지 않음
- 전체 실패 원인 집계
- degraded 정보 반영과 truncation 부재

완료 조건: 장애 run처럼 여러 모델이 같은 길이 초과를 반복하는 흐름이 재현 테스트에서 차단돼야 한다.

### G4 — 실행 로그와 artifact 보존

목표: 어느 단계에서 실패해도 최소 진단 artifact가 남게 한다.

작업:

1. 외부 API 호출 전에 `artifacts/run.log`, `artifacts/manifest.json`을 생성한다.
2. manifest skeleton을 atomic write하고 각 단계 후 갱신한다.
3. top-level handler가 상태, 실패 단계, 안전한 오류 분류를 기록한 뒤 실패 exit code를 유지한다.
4. run.log는 사람용, manifest는 구조화 데이터로 구분한다.
5. Secret redaction을 공통 적용한다.
6. artifact 이름에 run ID를 포함한다.
7. workflow upload 경로를 `artifacts/`와 일치시킨다.
8. skeleton 테스트가 안정화되면 파일 누락을 조용히 무시하지 않도록 `if-no-files-found` 정책을 강화한다.

manifest 최소 스키마:

```json
{
  "schema_version": 1,
  "run": {
    "run_id": null,
    "decision_id": "string",
    "commit_sha": null,
    "topic": "string",
    "started_at": "ISO-8601",
    "finished_at": null,
    "status": "RUNNING"
  },
  "academic_search": {
    "status": "NOT_STARTED",
    "query_count": 0,
    "request_count": 0,
    "rate_limited_count": 0,
    "success_count": 0,
    "eligible_paper_count": 0,
    "polite_pool_configured": false
  },
  "gemini_attempts": [],
  "report": {"body_length": null, "quality_state": null},
  "notion": {
    "status": "NOT_STARTED",
    "page_id_hash": null,
    "expected_image_count": 0,
    "uploaded_image_count": 0,
    "read_back_image_count": 0
  },
  "infographics": [],
  "failure": null
}
```

page ID는 원문 대신 필요하면 단방향 hash의 짧은 식별자를 기록한다. traceback은 안전하게 기록할 수 있지만 headers/body 전체는 금지한다.

필수 테스트:

- 시작 즉시 skeleton 생성
- 검색/Gemini/Notion 단계별 예외에서도 두 파일 존재
- JSON atomic update 후 항상 유효
- 이전 단계 메트릭 보존
- Secret sentinel이 log/manifest에 없음
- workflow와 생성 경로 일치

완료 조건: 각 주요 단계 실패 주입 테스트에서 유효한 두 artifact가 생성돼야 한다.

### G5 — 정적 PNG 생성 및 Notion 이미지 게시

목표: 검증된 데이터로 PNG를 만들고 Notion File Upload API와 image block으로 게시한 뒤 read-back한다.

구현 순서:

1. 검증된 source record로 `InfographicSpec` 생성
2. 계약 validator 실행
3. headless Python renderer로 정적 PNG 생성
4. MIME signature, 크기 상한, width/height, SHA-256 검증
5. Notion File Upload API의 현재 공식 version/request sequence 확인
6. upload 생성 → byte 전송/완료 → file ID 확보를 adapter로 캡슐화
7. file ID로 image block 생성
8. caption 포함. alt 전용 필드가 공식 API에 없으면 검증 가능한 대체 표현을 쓰고 제한 기록
9. 텍스트와 이미지 block을 결정적 순서로 게시
10. page children을 pagination read-back해 image 수와 file ID 확인

Renderer 요구사항:

- Ubuntu 24.04 headless에서 동작하고 외부 폰트를 다운로드하지 않는다.
- 축, 단위, 출처를 표시하고 색상만으로 series를 구분하지 않는다.
- 크기/DPI는 상수 관리하며 데이터 과다는 validation/명시적 aggregation으로 처리한다.
- PNG checksum을 manifest에 기록한다.

Notion adapter 요구사항:

- API version, timeout, 제한 retry를 한 곳에서 관리한다.
- 인증 header와 민감 upload URL을 로그에 남기지 않는다.
- upload 성공과 block attach 성공을 별도 상태로 기록한다.
- 부분 실패 리소스를 idempotency 상태에 남긴다.

필수 테스트:

- 정상 spec과 빈 배열/길이 불일치/NaN/Infinity/source ID 누락
- PNG signature/checksum/크기
- File Upload create/send/complete mock
- image block payload/caption
- read-back pagination과 count 불일치
- API timeout/429/5xx
- Secret/upload URL 비노출

완료 조건: mock 테스트와 로컬 PNG decode가 성공하고, User 승인 운영 실행에서 image block read-back과 화면 확인이 일치해야 한다.

### G6 — 부분 성공, 재실행 및 중복 방지

목표: 부분 실패를 정확히 표현하고 동일 실행 재시도에서 중복을 만들지 않는다.

작업:

1. decision/run key를 Notion 페이지 속성 또는 결정적으로 검색 가능한 메타데이터에 저장한다.
2. 게시 전 existing resource를 조회한다.
3. 동일 key 완료 페이지면 새 페이지를 만들지 않고 read-back 후 재사용 결과를 반환한다.
4. 텍스트 완료·이미지 일부면 누락된 이미지부터 재개한다.
5. upload 완료·block 실패면 기존 file ID 재사용 가능성을 먼저 확인한다.
6. checksum 또는 infographic ID로 중복 block을 탐지한다.
7. 최종 상태를 공통 게시 상태로 정규화한다.
8. Slack 알림은 manifest 최종 상태와 일치해야 한다.

필수 테스트:

- 첫 실행 신규 생성, 동일 key 두 번째 실행에서 페이지 0개 증가
- 텍스트 성공/이미지 실패 재개
- upload 성공/block 실패 재개
- 동일 checksum 이미지 중복 방지
- read-back 불일치를 완전 성공으로 승격하지 않음
- Slack과 manifest 상태 일치

완료 조건: 같은 fixture/decision ID로 두 번 호출했을 때 page와 image block 수가 증가하지 않아야 한다.

---

## 7. Gate 의존성과 agent 배정

| 순서 | 담당 범위 | 선행 조건 | 결과물 | 정지 지점 |
|---|---|---|---|---|
| Agent A | G1~G4 | 최신 `origin/main` | runtime/provider/Gemini/artifact 수정·테스트·인계 | 커밋·PR 또는 User 지정 지점 |
| Agent B | G5~G6 | G1~G4 계약 확정 | infographic/Notion/idempotency 수정·테스트·인계 | 커밋·PR 또는 User 지정 지점 |
| 독립 검토 | 전체 diff | 구현 PR 준비 | Critical~Low finding | 코드 수정 없이 보고 |
| 보완 agent | 확인된 finding | User가 단계 호출 | 수정·회귀 테스트 | PR 갱신 후 보고 |
| Codex 최종 | 전체 | CI 성공, Critical/High 0 | 병합 판단·운영 검증·원장 | 외부 실행 승인 앞에서 정지 |

G2~G4가 실행 상태 계약을 제공하므로 G5~G6보다 먼저 인터페이스를 확정한다. 병렬 개발 시 typed contract와 manifest schema를 먼저 합의·커밋한다. 에이전트는 범위를 넘어 운영 실행이나 main 병합을 임의 수행하지 않는다.

---

## 8. 테스트와 PR 검증

### 8.1 로컬 필수 명령

```powershell
python -m pytest -q tests -p no:cacheprovider
git diff --check
git status --short --branch
```

테스트 수와 소요시간을 인계서에 기록한다. 기존 테스트 삭제나 assertion 약화로 통과시키지 않는다.

추가 확인:

- workflow YAML parse/정책 테스트
- 네트워크 호출 전부 mock
- 임시 디렉터리 artifact 생성
- PNG를 decoder로 다시 열어 유효성 확인
- manifest 필수 key 확인
- Secret sentinel 검색
- 동일 decision ID 2회 통합 테스트

### 8.2 PR CI 판정

- test job 성공
- PR 이벤트에서 production briefing job skip
- Ubuntu 24.04 runner
- Node.js 20 경고 0건
- 필수 check 실패/취소 0건

PR URL, run ID/URL, head SHA를 인계서에 기록한다.

---

## 9. 운영 검증과 User Gate

코드·로컬 테스트·PR CI 성공 후 User가 명시적으로 승인한 경우에만 수행한다.

1. 최신 main 또는 승인 ref SHA 확인
2. `workflow_dispatch` 실행
3. test/production job 확인
4. 실제 API에 고의 부하 없이 정상 provider와 제한 상태 검증
5. Actions log의 Secret 비노출과 Node.js 20 경고 0건 확인
6. `run.log`, `manifest.json`, PNG artifact 확인
7. Notion 텍스트, 이미지, caption/alt 대체 표현 육안 확인
8. read-back count와 manifest 대조
9. 동일 decision/run 재검증으로 중복 확인
10. 다음 schedule 결과 확인

운영 실행은 외부 쓰기와 비용을 발생시킨다. 승인 없이 `gh workflow run`, 실제 Notion/Gemini/Slack 호출을 하지 않는다.

---

## 10. 완료 판정표

| ID | 조건 | 증거 | 상태 |
|---|---|---|---|
| C1 | run 36366832887 원인 문서화 | §2 | COMPLETE |
| C2 | runner/action Node 24 전환 | workflow diff + 정책 테스트(test_g1_workflow_*) | COMPLETE |
| C3 | OpenAlex 429/empty 분리 | 단위 테스트(test_g2_*) + manifest | COMPLETE |
| C4 | Gemini 오류/길이 분리 | 단위 테스트(test_g3_*) + attempts | COMPLETE |
| C5 | 실패 artifact 보존 | 실패 주입 테스트(test_g4_*) + atomic write | COMPLETE |
| C6 | InfographicSpec/PNG | 테스트 + PNG | TODO |
| C7 | Notion upload/image/read-back | mock + 승인 운영 실행 | TODO |
| C8 | idempotency | 2회 실행 + 운영 확인 | TODO |
| C9 | 전체 테스트/CI | pytest 102/102 통과, diff clean | IN_PROGRESS |
| C10 | Critical/High 0건 | 독립 검토 | TODO |
| C11 | 운영 텍스트·이미지 확인 | 승인 run + Notion | TODO |

상태는 `TODO`, `IN_PROGRESS`, `COMPLETE`, `PARTIAL`, `BLOCKED`만 사용한다. 증거 없는 `COMPLETE`는 금지한다.

---

## 11. 인계 파일 규격

파일명:

```text
HANDOFF_2026-09-28_ACTIONS_NOTION_<GATE>_<AGENT>.md
```

예: `HANDOFF_2026-09-28_ACTIONS_NOTION_G1-G4_CODEX.md`

필수 본문:

```text
[Gate] G1 / G2 / G3 / G4 / G5 / G6 / REVIEW / FINAL
[Status] COMPLETE / PARTIAL / BLOCKED
[Agent] 실제 agent
[Started] KST
[Finished] KST
[Baseline] branch, HEAD, origin/main, ahead/behind, 작업트리
[Scope] 수행/미수행 gate
[Changed] 파일별 이유와 인터페이스
[Failure Root Cause] OpenAlex 429, Gemini 503, 길이 초과 관계
[State Contract] 상태와 호환성
[Actions Runtime] runner, release, full SHA, 공식 URL/시각
[OpenAlex] retry/backoff/status
[Gemini] 분류/regeneration/fallback
[Artifacts] 경로와 실패 주입 결과
[Infographic] spec/PNG/checksum/upload/block/read-back
[Idempotency] key와 2회 실행 결과
[Verified] 명령, 테스트 수, 시간, 결과
[Remote Sync] SHA, ahead/behind, PR, CI
[Security] Secret 비노출, 실서비스 호출 여부
[Findings] 심각도별 결과
[Risks] 잔여 위험과 운영 미검증
[Next Eligible Agent] 다음 역할
[Next Terminal] 다음 worktree
[Next Model] 모델 또는 KEEP_CURRENT
[User Prompt] 다음 agent 전달 문장
[User Gate] 승인 필요한 외부 작업
```

`COMPLETE`에는 gate 완료 조건과 증거가 모두 필요하다. 운영 검증을 안 했다면 `[Risks]`와 `[User Gate]`에 명시한다.

---

## 12. Finding 심각도와 차단 규칙

- `Critical`: Secret 노출, 잘못된 대상 게시, 무제한 외부 호출, 데이터 손상. 즉시 중단·병합 금지.
- `High`: provider failure를 정상 게시, 중복 대량 생성, artifact 완전 유실, read-back 없이 성공 처리. 해결 전 병합 금지.
- `Medium`: 일부 상태/메트릭 누락, 제한된 접근성 문제, 진단성 저하. 해결 또는 명시적 accepted risk 필요.
- `Low`: 문서·명명·비핵심 유지보수성. 후속 이관 가능.

Critical/High가 하나라도 열려 있으면 전체 `COMPLETE`를 선언하지 않는다.

---

## 13. 금지되는 성급한 해결

- 429를 빈 list로 바꾸고 계속 진행
- 출력을 잘라 11,000자로 맞춤
- 길이 오류마다 모델만 바꿔 full prompt 반복
- artifact upload에 `ignore`만 유지하고 파일 생성 미구현
- base64 이미지나 외부 공개 URL로 Notion upload 대체
- Gemini 생성 이미지 URL을 신뢰
- 제목만으로 기존 페이지 판단 후 이미지 무조건 append
- 테스트에서 운영 API 호출
- CI 통과만으로 Notion 실게시까지 완료 기록

---

## 14. 다음 agent 시작 문장

```text
WORK_DIRECTIVE_2026-09-28_ACTIONS_NOTION_INFOGRAPHIC.md 전체를 읽고 최신 origin/main에서 시작하세요. 우선 G1~G4만 구현해 Actions runtime 고정, OpenAlex 429/empty 분리, Gemini 길이 재생성 계약, 실패 시 run.log/manifest 보존을 완료하고 테스트·커밋·인계 파일까지 남기세요. Secret을 조회하거나 운영 workflow/Notion/Gemini를 실제 실행하지 말고 완료 후 다음 단계로 임의 진행하지 마세요.
```

---

## 15. 단계 원장

| Gate | 담당 | 상태 | 기준/증거 | 다음 행동 |
|---|---|---|---|---|
| 분석 | Codex | COMPLETE | Run 36366832887 로그·artifact·main 확인 | 구현 시작 |
| G1 | Agent A | COMPLETE | ubuntu-24.04 고정, Node 24 action full SHA 고정, 정책 테스트 18/18 통과 | Agent B |
| G2 | Agent A | COMPLETE | 429 Retry-After, backoff, SearchStatus 분리, 가짜 보고서 차단 | Agent B |
| G3 | Agent A | COMPLETE | 길이 초과 시 CONDENSE 축약, 상한 초과 시 fallback 중단, 시도 기록 | Agent B |
| G4 | Agent A | COMPLETE | 실행 즉시 run.log/manifest.json 생성, 단계별 실패 주입 보존, 마스킹 | Agent B |
| G5 | Agent B | TODO | PNG/File Upload/image/read-back 미구현 | Agent B |
| G6 | Agent B | TODO | run/decision 중복 방지 미구현 | Agent B |
| 독립 검토 | 미배정 | TODO | 구현 후 수행 | 검토 agent |
| 운영 검증 | Codex + User 승인 | TODO | 외부 쓰기 미실행 | CI 성공 후 승인 |
| 최종 종료 | Codex | TODO | C1~C11 대조 필요 | 전체 증거 확인 |

과거 결과를 지우지 말고 상태 변경 시 증거와 함께 원장을 갱신한다.
