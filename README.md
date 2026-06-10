# 📅 Daily Gemini-Notion Briefing Automation (Grand Final Version)

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

## 🚀 주요 기능 및 인프라
- **매일 자동 실행**: GitHub Actions를 통해 매일 아침 **08:17 (KST)** 실행.
- **학술적 심층 분석**: 공백 포함 5,000자 내외의 SCI 리뷰어급 대용량 리포트 생성.
- **실시간 학술 DB 연동**: Google Search Grounding을 통한 대한건축학회(AIK), DBpia, RISS 실시간 참조.
- **5중 에러 방어 체계**: Gemini 2.5/2.0 시리즈 기반 5단계 모델 폴백 및 지수 백오프 적용.
- **노션 자동 구조화**: '년-월 > 주차 > 요일' 계층 구조 자동 유지 및 블록 단위 분할 저장.

## 📂 파일 구조
- `briefing_auto.py`: 핵심 로직 (Gemini + Notion Integration)
- `01_Standard_Procedures/`: 최상위 거버넌스 및 표준 작업 절차서 (GRID, IRD-DP, SOP)
- `tests/`: 시스템 무결성 검증을 위한 DDD/TDD 테스트 수트
- `LOGLIST.md`: 브리핑 실행 이력 및 API 응답 로그 아카이브
- `update.md`: 프로젝트 업데이트 및 릴리즈 노트

## 🛠 실행 방법
1. 로컬 환경에 `.env` 파일을 생성하고 `GEMINI_API_KEY`, `NOTION_TOKEN`, `PARENT_PAGE_ID`를 설정합니다.
2. 필요한 패키지를 설치합니다 (`pip install google-genai requests tenacity python-dotenv`).
3. 아래 명령어를 실행합니다.
```bash
python briefing_auto.py
```

---
*본 프로젝트는 개인 연구(LOD 400 기반 설계 자동화)의 인프라로서 구축되었으며, 13인 위원회의 엄격한 적대적 검증을 통과했습니다.*
