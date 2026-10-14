# 🚨 장애 원인 분석 및 개선 계획 보고서 (Incident Report)

- **일자**: 2026-10-14 (수요일)
- **작업명**: Daily Gemini-Notion Briefing (KST Optimized)
- **실행 ID**: GitHub Actions Run #38498228294
- **주제**: `설계 자동화 기술 및 BIM (Building Information Modeling) 최신 동향`
- **상태**: **FAILED** (Notion 전송 단계 진입 전 차단)
- **담당 시스템**: BriefingAuto v9.3.2 / G1~G4 Governance Pipeline

---

## 1. 깃허브 액션 실행 로그 분석 (GitHub Actions Log Analysis)

### 1.1 실행 요약
- **Trigger**: Schedule (UTC 23:17 / KST 08:17)
- **전체 실행 시간**: 1분 59초
- **세부 Job 상태**:
  1. `Unit Test & Verification Gate` (ID: 115638800650): ✅ **SUCCESS** (32초)
  2. `Run Daily Briefing` (ID: 115638958538): ❌ **FAILED** (1분 21초)
     - `Pre-flight Secret Validation`: 통과 (`GEMINI_API_KEY`, `NOTION_TOKEN`, `PARENT_PAGE_ID` 확인 완료)
     - `python briefing_auto.py`: **RuntimeError 발생 후 비정상 종료 (Exit Code 1)**
     - `Upload Run Artifacts`: 항상 실행(`if: always()`)으로 `manifest.json` 및 `run.log` 업로드 완료

### 1.2 오류 로그 (Traceback & Error Message)
```text
Traceback (most recent call last):
  File "/home/runner/work/briefing/briefing/briefing_auto.py", line 1375, in <module>
    service.run_daily_briefing()
  File "/home/runner/work/briefing/briefing/briefing_auto.py", line 1365, in run_daily_briefing
    raise e
  File "/home/runner/work/briefing/briefing/briefing_auto.py", line 1311, in run_daily_briefing
    raise RuntimeError(
        f"학술 DB 공급자 장애({search_result.status.value})로 검색이 전면 실패했습니다. "
        "정상 브리핑 생성을 중단하고 장애 상태를 기록합니다."
    )
RuntimeError: 학술 DB 공급자 장애(OPENALEX_RATE_LIMITED)로 검색이 전면 실패했습니다. 정상 브리핑 생성을 중단하고 장애 상태를 기록합니다.
```

### 1.3 실행 아티팩트 메트릭 (`manifest.json` 분석)
다운로드된 실행 아티팩트(`briefing-run-artifacts-38498228294/manifest.json`)의 지표:
```json
{
  "run": {
    "run_id": "38498228294",
    "topic": "설계 자동화 기술 및 BIM (Building Information Modeling) 최신 동향",
    "status": "FAILED"
  },
  "academic_search": {
    "status": "OPENALEX_RATE_LIMITED",
    "query_count": 3,
    "request_count": 9,
    "rate_limited_count": 9,
    "success_count": 0,
    "eligible_paper_count": 0,
    "polite_pool_configured": false
  },
  "notion": {
    "status": "NOT_STARTED",
    "page_id_hash": null
  },
  "failure": {
    "stage": "ACADEMIC_SEARCH",
    "error_type": "RuntimeError",
    "error_message_safe": "학술 DB 공급자 장애(OPENALEX_RATE_LIMITED)로 검색이 전면 실패했습니다. 정상 브리핑 생성을 중단하고 장애 상태를 기록합니다."
  }
}
```

---

## 2. 노션 전송 실패의 근본 원인 (Root Cause Analysis)

### 📌 요약: 노션 전송이 실패한 이유는 "노션 API 오류"가 아니라, "학술 DB(OpenAlex) 429 차단으로 인해 거버넌스 가드(G2 Guard)가 허위 브리핑 생성을 원천 차단"했기 때문입니다.

1. **GitHub Actions Runner의 공용 IP 대역에 대한 OpenAlex 429 Throttling**:
   - GitHub Actions의 Ubuntu 호스트는 Microsoft Azure 데이터센터의 공용 IP 풀을 사용합니다.
   - 전 세계의 무수한 CI/CD 파이프라인이 이 IP 풀을 공유하므로, OpenAlex의 익명 IP 제한(초당 10회 풀)이 쉽게 고갈되어 `HTTP 429 Too Many Requests`가 반환되었습니다.
   - 총 3개의 검색 쿼리(`'BIM 설계 자동화'`, `'BIM 건축'`, `'설계 자동화'`) 각각 3회씩 총 9회의 HTTP 요청이 발생했으나 **9회 모두 429 응답**을 받았습니다.

2. **워크플로우 환경 변수에 `OPENALEX_MAILTO` 누락**:
   - OpenAlex는 Polite Pool 진입을 위해 이메일 등록을 요구합니다.
   - 하지만 `.github/workflows/daily_briefing.yml`에 `OPENALEX_MAILTO` 환경 변수가 누락되어 있었고, 그 결과 `polite_pool_configured: false`로 작동하였습니다.

3. **OpenAlex API 요청 URL에 `mailto=` 쿼리 파라미터 미포함**:
   - 현재 코드(`briefing_auto.py`)는 `User-Agent: BriefingAuto/9.0 (mailto:...)` 헤더에만 의존하고 있었습니다.
   - OpenAlex 앞단의 Cloudflare 리버스 프록시 및 API 라우터는 헤더보다 URL 쿼리 파라미터 `&mailto=your_email` 또는 `&api_key=your_key`를 기준으로 Polite Pool을 신뢰성 있게 라우팅합니다. 헤더만 있는 경우 공유 IP 풀로 간주되어 차단될 가능성이 높습니다.

4. **단기 Backoff 재시도 한계 (7초 내 3회 소진)**:
   - `base_backoff=1.0s`, `max_backoff=10.0s`, `max_retries=3` 구조로 인해, OpenAlex가 15~30초 이상 레이트 리밋을 적용할 때 1s, 2s, 4s 간격으로 빠르게 3회를 소진하여 복구될 기회를 얻지 못했습니다.

5. **G2 Guard의 정상적인 안전 차단 동작**:
   - 피어리뷰 학술 논문이 0건(`eligible_paper_count: 0`)인 상태에서 Gemini 생성을 진행하면 **허위 사실 날조(Hallucination) 및 근거 없는 가짜 브리핑**이 생성됩니다.
   - 이를 방지하기 위해 설계된 G2 거버넌스 가드(`briefing_auto.py:1310`)가 의도대로 `RuntimeError`를 발생시켜 즉시 프로세스를 중단하였고, 이에 따라 Notion 발행 단계는 `NOT_STARTED` 상태로 안전하게 보류되었습니다.

---

## 3. 수정 및 재발 방지 대책 (Resolution & Action Plan)

### 3.1 [대책 1] OpenAlex Polite Pool URL 쿼리 파라미터 & API Key 지원 (`briefing_auto.py`)
- OpenAlex API 호출 시 쿼리 파라미터에 `&mailto={actual_email}`을 항상 명시적으로 추가하여 Cloudflare/공용 IP 차단을 우회.
- 무료 발급 가능한 OpenAlex 공식 API Key(`OPENALEX_API_KEY`)를 지원하도록 어댑터 확장 (`api-key` 헤더 및 `api_key=` 쿼리 파라미터 지원).

```python
# 수정 방안 예시: OpenAlex URL 구성 보강
params = [
    f"search={requests.utils.quote(query)}",
    "filter=open_access.is_oa:true,type:article,is_retracted:false,primary_location.source.type:journal,has_abstract:true",
    f"per_page={max_papers}",
]
if self.actual_email:
    params.append(f"mailto={requests.utils.quote(self.actual_email)}")
if self.api_key:
    params.append(f"api_key={requests.utils.quote(self.api_key)}")
url = f"https://api.openalex.org/works?{'&'.join(params)}"
```

### 3.2 [대책 2] GitHub Actions 워크플로우 환경 변수 주입 (`daily_briefing.yml`)
- `.github/workflows/daily_briefing.yml`의 `Run Daily Briefing` step에 환경 변수 추가:
```yaml
      - name: Run Daily Briefing
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          NOTION_TOKEN: ${{ secrets.NOTION_TOKEN }}
          PARENT_PAGE_ID: ${{ secrets.PARENT_PAGE_ID }}
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
          OPENALEX_MAILTO: ${{ secrets.OPENALEX_MAILTO || 'blueeye.research@gmail.com' }}
          OPENALEX_API_KEY: ${{ secrets.OPENALEX_API_KEY }}
        run: |
          python briefing_auto.py
```

### 3.3 [대책 3] 429 지수 백오프 및 지터(Jitter) 강화
- Azure 공용 IP 대역의 일시적 레이트 리밋을 통과할 수 있도록 재시도 대기 시간을 점진적으로 확대:
  - `base_backoff`: 1.0초 -> 2.0초
  - `max_backoff`: 10.0초 -> 30.0초
  - 쿼리 간격(`query_interval`): 0.25초 -> 0.75초
  - `Retry-After` 헤더 반영 시 상한 60초까지 안전하게 대기.

### 3.4 [대책 4] 공급자 완전 장애 시 노션 '시스템 장애 알림 페이지' 기록 (선택 사항)
- 현재는 전면 중단되지만, 사용자가 노션에서도 실패 상태를 인지할 수 있도록 `[긴급 공지] 학술 DB 공급자 장애로 인한 당일 브리핑 생성 보류` 형태의 간이 공지 블록을 Notion에 게시하는 Fallback 모드를 고려할 수 있습니다.

---

## 4. 검증 계획
1. 단위 테스트(`tests/test_g1_to_g4_actions_and_providers.py`)에서 `mailto` 쿼리 파라미터 및 `OPENALEX_MAILTO` 주입 시의 `polite_pool_configured` 동작 검증.
2. `git diff --check` 및 전체 111개 테스트 무결성 확인.
3. PR 생성 및 GitHub Actions 단위 테스트 게이트 검증.
