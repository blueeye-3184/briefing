# 📅 Daily Gemini-Notion Briefing Automation

본 프로젝트는 **Google Gemini AI**와 **Notion API**를 결합하여, 매일 정해진 주제에 대해 전문가 수준의 분석 리포트를 생성하고 노션 페이지에 자동으로 기록하는 시스템입니다. **GRID/IRD-DP v6.2** 거버넌스와 **DDD/TDD 아키텍처**를 적용하여 산업용 수준의 안정성과 학술적 무결성을 확보했습니다.

## 🏛️ 거버넌스 및 연구 철학 (Governance & Philosophy)
본 시스템은 **Integrated R&D Documentation Protocol (IRD-DP) v6.2** 규준에 따라 운영되며, 모든 활동은 **Governance Revision & Integrity Directive (GRID)**의 통제를 받습니다.

### 1. 문서 및 지침 위계 (Hierarchy)
- **GRID (Directive)**: 최상위 안전장치. 규준 개정 절차 및 마스터 이력 관리.
- **IRD-DP (Protocol)**: 연구 헌법. 도메인 공리, 거버넌스 위계 및 기술 명세 정의.
- **SOP (Manual)**: 표준 작업 절차서. 현장 작업의 구체적 방법론 및 자동 검증 규정.
- **README (Hub)**: 운영 창구. 프로젝트 로드맵 및 연구 자산 대시보드.

### 2. 연구 공학적 원칙
- **Axiomatic Grounding**: 모든 추론은 물리 법칙 및 지배 방정식에서 연역적으로 유도하여 환각(Hallucination)을 배격합니다.
- **Adversarial Resilience**: 모든 결과물은 13인 위원회의 '적대적 공격'을 방어한 생존 결과물이어야 합니다.
- **Tiered Operation**: 
    - **Tier 1 (Critical)**: 아키텍처 변경 등 중대 사항은 연구자(User)의 명시적 비준 필수.
    - **Tier 2 (Standard)**: 검증 훅(Validation Hooks) 통과 시 **Adversarial Autopilot**에 의한 자율 실행.

## 🛡️ 13인 적대적 검증 위원회 (Adversarial Reviewers)
**IRD-DP v6.2**의 Full-Spec을 준수하며, 13인의 페르소나가 연구 무결성을 전수 감시합니다.

| ID | Persona | 핵심 직무 (Core Missions) | 적대적 공격 임무 (Adversarial Duties) |
| :--- | :--- | :--- | :--- |
| 1 | **Lead Architect** 👑 | 전체 로드맵 및 위계 간 정합성 관리 | "위계 간 논리적 단절" 및 "시공 불가성" 공격 |
| 2 | **Core Engine Dev** | 수치 해석 알고리즘 및 수식 무결성 책임 | "수치적 발산" 및 "수학적 결함" 타격 |
| 3 | **Domain Engineer** | KDS 기준 및 구조 공학 전문 지식 비준 | "설계 기준 위반" 및 "구조 역학적 모순" 추국 |
| 4 | **Integration Dev** | 데이터 동기화 및 DDD 파이프라인 관리 | "Bounded Context 훼손" 및 "데이터 오염" 공격 |
| 5 | **Quality Director** 👑👑 | **[의장]** 전체 공정 비준 및 리젝트 결정 | 방어 실패 논리에 대한 **최종 리젝트(Reject)** |
| 6 | **Data Auditor** | 수치 정합성 및 통계적 유의성 조사 | "통계적 무의미" 및 "데이터 조작" 집중 타격 |
| 7 | **Regression Spec** | 수정 시 기존 물리 정합성 유지 확인 | "시스템 성능 퇴행(Trade-off)" 및 "부작용" 공격 |
| 8 | **API/Spec Validator** | 표준 마크업 및 공학용어 규격 준수 | "문서 규격 미달" 및 "용어 오용" 즉시 반려 |
| 9 | **Content Integrity** | 학술적 맥락 유지 및 엔지니어링 엣지 | "공학적 비약(Hallucination)" 공격 |
| 10 | **Chief Record Mgr** 👑 | 4대 마스터 문서 상호 참조 총괄 | "기록 누락" 및 "문서 간 모순" 추적성 공격 |
| 11 | **Session Recorder** | 사고 체인(CoT) 및 진화 경로 기록 | "추론 경로 불투명성" 및 "사고 위조" 공격 |
| 12 | **History Guardian** | 체크포인트 설정 및 데이터 보존 확인 | "컨텍스트 전이(Bleeding)" 및 "초기화 실패" 공격 |
| 13 | **Security Officer** | 연구 윤리 준수 및 데이터 보안 감사 | "보안 취약" 및 "데이터 폐쇄성/윤리 결함" 타격 |

## 🚀 주요 기능 및 인프라 (v9.2 Academic OpenAccess Architecture)
- **GitHub Actions 2단계 검증 게이트**: Pull Request에서는 운영 secret 없이 `test` job만 실행하고, `schedule` 또는 수동 실행에서 테스트가 전수 통과한 경우에만 `briefing` job이 실행된다. `permissions: contents: read` 및 중복 실행 방지 `concurrency` 적용.
- **사전 환경변수 무결성 검증**: `PARENT_PAGE_ID` 하드코딩 기본값을 제거하고, 필수 시크릿(`GEMINI_API_KEY`, `NOTION_TOKEN`, `PARENT_PAGE_ID`) 누락 시 외부 API 호출 전 즉시 차단 (시크릿 누출 방지).
- **거버넌스 원문 추적성 복원**: 저장소용 공개 사본(`01_Standard_Procedures/00.*`)을 복원하고 로컬 작업트리 및 민감정보를 격리.
- **매일 자동 실행**: GitHub Actions를 통해 매일 아침 **08:17 (KST)** 정기 실행 및 Slack 실시간 알림(HTTP 상태 검증 포함).
- **엄격 적격성 게이트를 통과한 OA 논문 최대 10편**: OpenAlex 후보를 모든 검색 키워드에서 수집하고 DOI 중복 제거 후 Crossref `journal-article` 유형·제목 일치, OpenAlex journal source, accepted/published version, 공개 라이선스, OA URL, 초록, 비철회 상태를 모두 통과한 논문만 채택.
- **논문 원문 미주입**: Gemini에는 논문 전문이나 PDF를 넣지 않고 검증된 서지정보와 초록만 제공. 입력 120,000 tokens 운영 상한과 출력 12,000 tokens 예약을 코드로 검사.
- **10,000자 브리핑 계약**: 참고문헌을 제외한 본문을 공백 포함 9,000~11,000자로 검증하고, 제공되지 않은 원문 내용이나 수치를 추정하지 않도록 제한.
- **결손 투명 공시**: 목표 10편에 미달하면 실제 채택 수와 부족 상태를 표시하고, 0편이면 `UNKNOWN / DEFICIT REPORT`를 자동 부착한 뒤 허위 학술 인용 없이 작성.
- **코드 레벨 서지 렌더링**: 모델이 참고문헌을 작성하지 않으며 DOI와 OA 링크는 검증 객체에서 코드가 직접 생성. Notion 블록을 절약하기 위해 논문당 한 블록으로 렌더링.
- **5중 모델 회피 체계**: Gemini 3.8/3.7/3.6 및 2.5 Flash 계열 5단계 모델 폴백과 지수 백오프 적용.
- **노션 안전 게시**: '년-월 > 주차 > 요일' 계층 구조 자동 탐색/생성, rich text 2,000자 제한 대비 1,800자 안전 분할, 페이지당 90블록 운영 상한 적용. 초과 결과는 잘라내지 않고 게시 전 실패 처리.

## 📂 파일 구조
- `briefing_auto.py`: 핵심 파이프라인 (AcademicProvider + GeminiProvider + NotionPublisher + SlackNotifier + ApplicationService)
- `01_Standard_Procedures/`: 최상위 거버넌스 및 표준 작업 절차서 (GRID, IRD-DP, SOP 공개 사본)
- `03.Committee_Opinions.md`: 13인 위원회 Tier 1 전략 비준 및 의사결정 로그 (Decision IDs)
- `04.Data_Collection_Log.md`: 실시간 실행 및 파이프라인 무결성 감사 로그
- `LOGLIST.md`: 브리핑 실행 이력 및 API 응답 로그 아카이브
- `update.md`: 프로젝트 주요 릴리즈 노트 (v1.0 ~ v9.1)
- `tests/`: 시스템 무결성 검증을 위한 30개 단위 테스트 수트 (Domain, Academic, Gemini, Notion, Markdown, Governance/Config)

## 🛠 실행 및 검증 방법
1. 로컬 환경에 `.env` 파일을 생성하고 `GEMINI_API_KEY`, `NOTION_TOKEN`, `PARENT_PAGE_ID` (선택: `SLACK_WEBHOOK_URL`)를 설정합니다.
2. 필수 의존 패키지를 설치합니다:
```bash
pip install -r requirements.txt
pip install pytest
```
3. 시스템 단위 테스트를 실행합니다 (현재 30개 테스트 전수 통과 확인):
```bash
pytest
```
4. 일일 자동 브리핑을 실행합니다:
```bash
python briefing_auto.py
```

---
*본 프로젝트는 개인 연구(LOD 400 기반 설계 자동화)의 인프라로서 구축되었으며, 13인 위원회의 엄격한 적대적 검증 및 Tier 1 비준을 통과했습니다.*
