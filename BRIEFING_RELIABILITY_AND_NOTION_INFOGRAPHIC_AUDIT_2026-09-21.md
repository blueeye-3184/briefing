# 브리핑 신뢰성·Notion 인포그래픽 개선 검토서

- 작성일: 2026-09-21 (KST)
- 검토 대상: `briefing_auto.py`, `tests/`, `.github/workflows/daily_briefing.yml`, 보안 제외 정책
- 목표: 본문 약 10,000자, 공개 열람 가능한 연구자료 5편 이상, 인포그래픽 5개 이상을 매일 재현 가능하게 생성·검증·게시
- 결론: **구현 가능. 다만 현재 스크립트는 요구사항을 충족하지 않으므로 검색·검증·생성·시각화·게시를 분리한 2단계 개편이 필요하다.**

## 1. 핵심 판정

현재 파이프라인은 “논문 메타데이터를 먼저 수집하고 생성 모델에는 수집 결과만 제공한다”는 방향이 좋다. 무근거 서지를 모델이 직접 만들게 하지 않는 점, 논문이 없을 때 abstention을 표시하는 점, 예외를 다시 발생시켜 자동 실행의 거짓 성공을 방지하는 점도 유지할 가치가 있다. 그러나 현재의 `100% 피어리뷰`, `100% 검증`, `환각 0%` 표현은 코드가 실제로 입증하는 범위를 넘어선다. OpenAlex의 `type=article`은 문서 유형이고 `is_oa=true`는 무료 열람 가능성이지, 동료평가 완료를 보증하는 독립 필드가 아니다. OpenAlex 문서도 OA를 “로그인이나 결제 없이 읽을 수 있음”으로 폭넓게 정의한다. 따라서 앞으로는 **“OpenAlex/Crossref 메타데이터 교차 확인”**과 **“동료평가 가능성이 높은 학술지 게재본”**처럼 검증 수준을 정확히 표현해야 한다.

요청한 산출 규격과 현재 구현의 차이는 명확하다.

| 항목 | 요청 기준 | 현재 구현 | 판정 |
|---|---:|---:|---|
| 본문 분량 | 약 10,000자 | 프롬프트상 4,000~5,000자 | 미충족 |
| 공개 논문 | 5편 이상 | 최대 3편 | 미충족 |
| 검색 범위 | 주제별 충분한 근거 | 첫 성공 키워드 결과만 반환 | 미충족 |
| 인포그래픽 | 5개 이상 | 생성·저장·게시 코드 없음 | 미충족 |
| 본문 인라인 근거 | 주요 주장과 출처 연결 | 참고문헌을 끝에 일괄 부착 | 부분 충족 |
| 논문 검증 | OA·서지·동료평가·철회 여부 | OA와 article 중심 | 부분 충족 |
| Notion 전체 게시 | 10,000자와 이미지 모두 | 최초 100블록만 전송 | 위험 |
| 자동 품질 게이트 | 분량·근거 수·그림 수·지원율 | 없음 | 미충족 |

권고 배포 순서는 다음과 같다. 1차에서는 신뢰성 계약, 검색 다변화, 인라인 근거, 100블록 초과 게시, 정적 인포그래픽을 구현한다. 2차에서는 독립 검증 패스와 대화형 HTML 시각화를 선택적으로 추가한다. 정적 이미지 경로만으로도 사용자의 최소 목표는 달성할 수 있으므로 대화형 기능을 필수 조건으로 두지 않는다.

## 2. 보안 및 Git 연동 점검

`01_Standard_Procedures`는 검토 시작 시 이미 5개 파일이 Git 추적 대상이었다. 하위 폴더 안의 `.gitignore`는 폴더 자신을 상위 저장소로부터 숨기지 못하며, 이미 추적된 파일에도 적용되지 않는다. 이번 점검에서 루트 `.gitignore`에 `/01_Standard_Procedures/`를 추가했고, 로컬 파일을 삭제하지 않은 채 Git 인덱스에서 해당 5개 파일을 제거했다. 현재 보이는 staged deletion은 **원격 저장소에서 제거하기 위한 인덱스 변경**이며 로컬 원본은 남아 있다.

일반적인 API 키 형식에 대한 경로 전용 검사에서는 현재 브랜치와 해당 디렉터리의 Git 이력에서 일치 항목을 찾지 못했다. 그러나 정규식 검사는 사용자 정의 토큰, 암호 문장, 짧은 키, 난독화된 값까지 보증하지 못한다. 또한 이 폴더를 건드린 과거 커밋이 존재하므로, 민감값이 한 번이라도 커밋되었다고 의심되면 다음 원칙을 적용해야 한다.

1. 키를 먼저 폐기·재발급한다. Git 기록 삭제보다 자격증명 회전이 우선이다.
2. 이번 `.gitignore` 및 추적 해제 변경을 커밋하고 원격에 반영한다.
3. 과거 Git 기록 자체에서 제거해야 한다면 별도 승인 아래 `git filter-repo` 등으로 이력을 재작성하고 강제 푸시한다. 이는 협업자 clone과 열린 PR에 영향을 주므로 자동 수행하지 않는다.
4. GitHub Actions의 값은 코드나 Markdown이 아니라 Repository/Environment Secrets에만 둔다.
5. CI에 비밀 탐지 도구를 추가하고, `01_Standard_Procedures/**`가 추적되면 실패하는 명시적 테스트를 둔다.

권장 게이트는 `git ls-files --error-unmatch 01_Standard_Procedures/...`가 성공하면 실패하도록 만드는 방식이다. 이 검사는 내용에 접근하지 않고도 보호 폴더가 다시 추적되는 회귀를 막는다. `.env`는 이미 루트에서 제외되고 `.env.example`만 추적되므로 이 정책은 유지한다.

## 3. 현재 스크립트의 신뢰성 문제

### 3.1 검색이 “최대 3편, 첫 성공 키워드”에 고정됨

`search_peer_reviewed_oa_papers()`는 키워드를 순회하다 한 키워드에서 결과가 나오면 즉시 반환한다. 실제 호출도 `max_papers=3`이다. 이 방식은 최소 5편이라는 요구를 절대 충족하지 못하고, 첫 키워드의 표현 편향을 그대로 받아들인다. 관련성이 낮은 인기 논문 3편이 먼저 나오면 더 적합한 다음 키워드는 시도조차 하지 않는다.

개선안은 모든 키워드에서 후보를 넉넉히 모은 뒤 DOI, OpenAlex ID, 정규화 제목으로 중복 제거하고 점수화하는 것이다. 예를 들어 키워드당 10편, 전체 후보 20~30편을 확보한 후 최소 5편, 권장 7~10편을 선택한다. 점수에는 제목·초록의 주제 관련도, 발행연도, `primary_location.source.type=journal`, DOI 존재, 초록 존재, 공개 전문 URL, 게재본 버전, 철회 여부를 포함한다. 인용 수는 보조 신호일 뿐 최신 논문을 과도하게 불리하게 만들 수 있으므로 낮은 가중치를 둔다.

### 3.2 “article + OA = 100% peer reviewed”라는 과대 주장

OpenAlex `type`은 정규화된 저작물 유형이고, `is_oa`는 무료로 읽을 수 있는 사본의 존재다. 코드에는 학술지 여부, 철회 여부, 게시·수락 버전, Crossref의 `journal-article` 여부를 모두 검증하는 조건이 없다. `Crossref` 조회 역시 현재는 `original-title` 보강에만 사용되며 상태 검증 역할을 거의 하지 않는다. 그러므로 배지의 `100%`, README의 “가짜 논문 환각 0%”, “전수 검증” 문구는 품질 지표로 교체해야 한다.

권장 검증 필드는 다음과 같다.

- OpenAlex: `id`, `doi`, `type`, `is_retracted=false`, `primary_location.source.type=journal`, `best_oa_location.version`, `has_abstract`, `publication_date`.
- Crossref: DOI 해석 성공, `type=journal-article`, 제목·저자·연도 일치율, `relation` 또는 갱신 메타데이터.
- 선택 강화: DOAJ 등재 또는 출판사/학회 원문, Retraction Watch가 반영된 OpenAlex 철회 플래그.
- 결과 표기: `verified_fields`, `verification_warnings`, `retrieved_at`, `source_ids`를 논문 객체에 보존.

어떤 메타데이터 조합도 실제 심사 과정의 품질을 100% 보장하지는 않는다. 따라서 배지는 `Metadata checks 6/7 passed`, `Retraction flag: false`, `OA copy: confirmed`처럼 관찰 가능한 사실만 표시하는 편이 신뢰도가 높다.

### 3.3 초록만으로 10,000자 분석을 만들 때의 근거 희석

현재 생성 입력은 논문당 초록뿐이다. 3~5개의 짧은 초록으로 10,000자를 요구하면 모델이 빈틈을 일반 지식으로 채울 가능성이 커진다. 공개 전문을 무조건 대량 수집하는 것도 저작권, 파싱 오류, 토큰 비용 문제가 있다. 현실적인 중간안은 초록, 제목, 서지, 주제어와 함께 공개 전문에서 합법적으로 얻은 핵심 구간 또는 공식기관 자료를 “근거 카드”로 만드는 것이다.

각 근거 카드는 `evidence_id`, 원문 URL, 자료 유형, 발행일, 발행기관, 1~3개의 짧은 근거 문장, 그 근거가 지지하는 주장 범위를 가져야 한다. 본문은 `[E01]` 같은 식별자를 문단 안에 사용하고, 최종 변환기가 이를 실제 링크와 각주 블록으로 바꾼다. 모델이 출처 목록을 임의로 쓰는 것은 계속 금지하되, 모델이 어느 근거를 사용했는지는 구조화된 출력으로 제출하게 한다.

### 3.4 지역 정책·시장·공모 정보는 논문만으로 최신성을 확보할 수 없음

월요일 부동산 정책, 금요일 R&D 공모 같은 주제는 최신 공고와 통계가 핵심이다. 학술논문 5편만 강제하면 오히려 현재 사실과 동떨어진 브리핑이 될 수 있다. 출처를 다음 세 층으로 분리하는 것이 적절하다.

- A급 1차 자료: 법령, 국토교통부·통계청·지자체·IRIS 공고, 공공데이터, 표준 원문.
- B급 학술 자료: DOI와 OA 원문이 확인된 학술지 논문 및 리뷰 논문.
- C급 보조 자료: 신뢰할 수 있는 기관 보고서와 업계 데이터. 단독으로 핵심 주장을 확정하지 않는다.

“공개 논문 5편 이상”은 유지하되, 시의성이 중요한 수치와 일정은 A급 자료를 별도로 요구해야 한다. 모든 시변 정보에는 기준일을 붙이고, 과거 자료와 현재 상태를 섞지 않는다.

### 3.5 생성 후 독립 검증과 품질 게이트가 없음

현재 파이프라인은 모델 응답이 비어 있지 않으면 바로 게시한다. 글자 수, 인용된 근거 수, 출처와 주장 일치 여부, 인포그래픽 수, 금지 표현, 상충 수치가 검사되지 않는다. 최소 게이트는 다음과 같다.

- 본문 글자 수: 참고문헌·감사 배지 제외 9,000~11,000자. 범위를 벗어나면 1회 보정 생성.
- 독립 자료 수: 공개 논문 5편 이상, 중복 DOI 없음, 핵심 주제 관련성 하한 통과.
- 인라인 근거: 검증 가능한 핵심 주장 100%에 evidence ID 존재.
- 근거 지원율: 원자 주장 단위로 `supported / partially_supported / unsupported / unverifiable` 판정.
- 숫자 검증: 숫자·날짜·퍼센트가 원문 근거에 존재하는지 확인.
- 시각물: 이미지 5개 이상, 캡션·데이터 출처·생성시각 존재.
- 게시 검증: 생성한 블록 수와 Notion에서 다시 읽은 블록 수 일치.
- 실패 정책: 기준 미달이면 게시하지 않고 초안 파일 및 검증 보고서만 보존한 뒤 Slack에 원인을 알림.

생성 모델과 검증 모델이 같더라도 프롬프트와 입력을 분리하고, 검증 단계에는 원문 근거와 완성된 주장만 제공한다. 가장 중요한 주장 일부는 규칙 기반 검사와 사람이 확인할 수 있는 표로 남긴다. “검증 통과”는 모델의 자신감이 아니라 위 게이트 결과를 의미해야 한다.

## 4. 연구 근거에 따른 권고

다음 자료는 모두 공개 페이지 또는 공개 PDF로 확인할 수 있으며, 시스템 설계의 근거로 사용할 수 있다.

1. Lewis et al., **Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks** (2020). 파라미터 내부 지식만 사용하는 모델보다 검색된 외부 지식을 결합한 생성이 지식 집약 과제에서 더 구체적이고 사실적인 결과를 낼 수 있음을 제시한다. 현재의 선검색·후생성 방향을 지지하지만, 검색 품질과 provenance 보존이 필수라는 점도 시사한다. [공개 원문](https://arxiv.org/abs/2005.11401)
2. Min et al., **FActScore: Fine-grained Atomic Evaluation of Factual Precision in Long Form Text Generation** (EMNLP 2023). 장문을 원자적 사실로 분해하고 신뢰 가능한 지식원에 의해 지지되는 비율을 측정한다. 보고서 전체에 “통과” 배지를 하나 붙이는 대신 주장별 지원율을 산출해야 하는 직접 근거다. [ACL Anthology](https://aclanthology.org/2023.emnlp-main.741/)
3. Asai et al., **Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection** (ICLR 2024). 고정 개수 자료를 무조건 넣는 방식보다 필요성·관련성·지원 여부를 평가하는 검색·비평 단계가 장문 사실성과 인용 정확도를 높일 수 있음을 보인다. 후보 수집 뒤 관련성 평가와 독립 비평 패스를 두는 설계에 해당한다. [OpenReview 공개 PDF](https://openreview.net/pdf?id=hSyW5go0v8)
4. Ru et al., **RAGChecker: A Fine-grained Framework for Diagnosing Retrieval-Augmented Generation** (2024). 검색 모듈과 생성 모듈을 분리해 세부 지표로 진단해야 한다고 제안하며, 인간 판단과의 상관을 메타 평가한다. `retrieval_recall`, `context_relevance`, `claim_support`를 별도 로그로 남기는 근거다. [공개 원문](https://arxiv.org/abs/2408.08067)
5. Song et al., **VeriScore: Evaluating the Factuality of Verifiable Claims in Long-form Text Generation** (Findings of EMNLP 2024). 사실성 점수가 과제별로 동일하게 움직이지 않을 수 있음을 보여준다. 부동산, BIM, 정책, 조경을 하나의 임계값으로 평가하지 말고 주제별 검증 규칙을 두어야 한다. [ACL Anthology](https://aclanthology.org/2024.findings-emnlp.552/)
6. Bishop et al., **LongDocFACTScore: Evaluating the Factuality of Long Document Abstractive Summarisation** (LREC-COLING 2024). 과학 문서의 긴 요약에 대해 세밀한 사실 일관성 평가가 필요함을 다룬다. 10,000자 브리핑을 짧은 응답과 같은 방식으로 검사해서는 안 된다는 근거다. [ACL Anthology](https://aclanthology.org/2024.lrec-main.941/)

이 연구들은 “RAG를 쓰면 자동으로 신뢰할 수 있다”는 결론이 아니라, 검색·출처 추적·주장 분해·세부 평가를 함께 해야 한다는 결론을 지지한다. 따라서 최소 논문 수는 입력 조건일 뿐 품질 점수 자체가 아니다. 관련성이 약한 논문 10편보다 주장을 직접 지지하는 논문 5편과 최신 1차 자료가 낫다.

## 5. Notion 인포그래픽 가능성

### 5.1 판정: 가능

Notion 공식 API의 block 객체는 공개 URL을 가리키는 `image` 블록을 지원하고, 직접 호스팅된 PNG·JPG·SVG 등을 표시할 수 있다. File Upload API로 이미지를 Notion에 업로드한 뒤 `file_upload` ID를 이미지 블록에 연결하는 방법도 가능하다. 최신 API 문서에는 업로드한 `.html` 파일을 sandboxed iframe으로 표시하는 HTML 블록 절차도 기재되어 있다. Notion UI는 외부 서비스 임베드를 폭넓게 지원하지만, API로 만든 embed는 UI에서 직접 붙인 embed와 모양이나 메타데이터 처리가 다를 수 있다는 공식 주의사항이 있다.

따라서 권장 순서는 다음과 같다.

1. **기본안: 정적 PNG** — GitHub Actions에서 생성하고 File Upload API로 Notion에 저장한다. 외부 공개 버킷이 필요 없고 링크 만료·핫링크 문제를 줄인다.
2. **보조안: SVG** — 텍스트와 선이 선명하지만 폰트 호환성과 보안 정책을 사전 확인한다.
3. **선택안: 대화형 HTML** — 필터와 hover가 필요한 한두 개 그림에만 사용한다. 모바일·내보내기·접근성에서 정적 이미지보다 불리할 수 있다.
4. **비권장 기본안: 외부 대시보드 embed** — 외부 서비스 장애, 로그인 요구, viewer IP 전달, URL 만료와 프라이버시 문제를 운영 부담으로 남긴다.

관련 공식 문서: [Notion Block API](https://developers.notion.com/reference/block), [Notion File Upload API](https://developers.notion.com/reference/create-file), [Notion embed 도움말](https://www.notion.com/help/embed-and-connect-other-apps).

### 5.2 매일 생성할 최소 5개 인포그래픽

각 그림은 모델이 임의 숫자를 그리지 않도록 `visual_data.json`의 검증된 수치만 사용해야 한다. 데이터가 부족하면 “데이터 부족” 패널을 만들고 추정 그래프를 생성하지 않는다.

| 번호 | 인포그래픽 | 목적 | 필수 데이터 | 권장 형식 |
|---:|---|---|---|---|
| 1 | 핵심 지표 카드 | 오늘의 4~6개 핵심 수치와 기준일 전달 | 값, 단위, 전일/전년 비교, evidence ID | PNG |
| 2 | 추세 차트 | 시간에 따른 변화와 변곡점 표현 | 날짜, 값, 단위, 결측 표시 | 선/막대 PNG |
| 3 | 근거 품질 퍼널 | 후보→중복제거→검증→최종 인용 수 공개 | 단계별 건수와 탈락 사유 | 퍼널 PNG |
| 4 | 주장–출처 매트릭스 | 어떤 핵심 주장이 어떤 자료로 지지되는지 표시 | claim ID, evidence ID, 지원 등급 | 히트맵 PNG |
| 5 | 기회–위험 2×2 | 실무 우선순위와 불확실성 전달 | 영향도, 실현 가능성, 근거 강도 | 산점도 PNG |
| 6 | 선택: 프로세스/로드맵 | 정책·기술 도입 순서 표현 | 단계, 선행조건, 기간 | 타임라인 PNG/HTML |

모든 그림에는 제목, 한 문장 해석, 축·단위, 데이터 기준일, 출처 ID, 대체 텍스트를 넣는다. 색만으로 의미를 구분하지 않고 모양·라벨을 함께 사용한다. 모바일 폭을 고려해 1,600×900 또는 세로형 1,200×1,500을 주 규격으로 정하고, 한글 폰트를 CI에 명시적으로 설치한다.

### 5.3 현재 Notion 게시 코드의 장애 요소

- `publish_report()`는 Markdown을 한 줄씩 잘라 heading/list/paragraph만 만들며 이미지, 표, 링크, 굵게, 인용, 코드, divider를 처리하지 않는다.
- Markdown 링크가 rich text hyperlink가 아니라 글자 그대로 보일 수 있다. 참고문헌 클릭성과 가독성이 저하된다.
- `blocks[:100]` 때문에 101번째 이후 블록은 경고 없이 유실된다. 10,000자, 참고문헌, 그림 5개를 함께 게시하면 실제 유실 가능성이 있다.
- 번호 목록 판정이 `1.`부터 `5.`까지만 하드코딩되어 `6.` 이상은 일반 문단이 된다.
- 긴 heading/list를 2,000자씩 나누면 두 번째 조각도 같은 블록 유형이 되어 의미가 왜곡될 수 있다.
- page child 조회에 pagination 처리가 없어 자식이 100개를 넘으면 기존 월/주차 페이지를 놓치고 중복을 만들 수 있다.
- Notion 요청에 timeout과 429 재시도, `Retry-After` 처리가 없다.
- 게시 후 페이지 ID나 URL을 저장하지 않고 read-back 검증도 하지 않는다.

권장 구현은 먼저 페이지를 만들고, 본문 블록을 100개 이하 batch로 `append block children`에 순차 전송한 다음 이미지 블록을 추가하는 방식이다. 각 batch에는 idempotency용 run ID와 게시 manifest를 남긴다. 중간 실패 시 같은 제목의 불완전 페이지를 무작정 새로 만들지 말고 run ID로 재개 또는 교체한다.

## 6. 제안 아키텍처

```text
주제/기준일
  → SourceCollector (OpenAlex, Crossref, 공공 1차 자료)
  → EvidenceNormalizer (DOI/제목 중복 제거, 철회·버전·OA 점검)
  → EvidenceRanker (관련성/최신성/자료등급)
  → EvidencePack.json (최소 논문 5편 + 필요 시 1차 자료)
  → ReportGenerator (구조화 JSON, 9,000~11,000자)
  → ClaimVerifier (주장별 support 판정, 숫자/날짜 검사)
  → VisualRenderer (검증된 JSON으로 PNG 5개 이상)
  → QualityGate
  → NotionPublisher (batch, image upload, read-back)
  → RunManifest + Slack 요약
```

핵심 산출물은 단순 Markdown 하나가 아니라 다음 4종이어야 한다.

- `evidence_pack.json`: 검색 쿼리, 후보, 선택/탈락 사유, 서지정보, 검색시각.
- `report.json`: 섹션, 문단, claim ID, evidence ID, 표, 시각화 명세.
- `report.md`: 사람이 읽고 Git diff로 검토할 수 있는 렌더링 결과.
- `run_manifest.json`: 코드 버전, 모델명, 입력 해시, 글자 수, 논문 수, 그림 수, 게이트 결과, Notion page ID.

구조화 출력은 모델이 Markdown 문법을 즉흥적으로 결정하는 문제를 줄이고, 같은 데이터로 Markdown과 Notion 블록, 그림을 일관되게 만들 수 있게 한다. 모델이 작성할 필드는 내용과 claim–evidence 연결이고, URL·서지·검증 배지는 코드가 원본 데이터에서 렌더링한다.

## 7. 구체적 코드 변경 목록

### P0 — 즉시 수정

1. 설정 상수 추가: `MIN_PAPERS=5`, `TARGET_BODY_CHARS=10000`, 허용 범위 `9000..11000`, `MIN_INFOGRAPHICS=5`.
2. 모든 검색 키워드 결과를 합치고 DOI/OpenAlex ID/제목으로 중복 제거한다. 첫 성공 즉시 반환을 제거한다.
3. OpenAlex 필터와 후처리에 `is_retracted=false`, 학술지 source, abstract 존재를 반영하고 Crossref 일치 결과를 저장한다.
4. `AcademicPaper`를 dataclass로 바꾸고 OpenAlex ID, 발행일, source type, version, retraction, 검증 경고를 추가한다.
5. 생성 응답을 JSON schema로 제한해 `sections`, `claims`, `evidence_ids`, `visual_specs`를 받는다.
6. 글자 수·논문 수·인포그래픽 수·지원되지 않은 claim 수를 검사하는 `QualityGate`를 추가한다.
7. Notion 페이지 생성과 children append를 분리하고 100개 단위 batch 전송을 구현한다.
8. Markdown 링크와 강조를 Notion rich text annotation으로 변환한다.
9. `requests` 공통 세션에 connect/read timeout, 429/5xx 재시도, `Retry-After`를 적용한다.
10. “100%”, “환각 0%”를 관찰 가능한 검증 결과 문구로 교체한다.

### P1 — 인포그래픽과 운영 안정성

1. 검증된 `visual_data.json`만 받는 `VisualRenderer`를 만든다.
2. Matplotlib 또는 Plotly+Kaleido 중 하나로 정적 PNG 5개를 생성한다. 의존성과 한글 폰트를 Actions에 고정한다.
3. Notion File Upload API를 통해 그림을 올리고 캡션·alt text·근거 ID를 포함한 image block을 추가한다.
4. 업로드 후 페이지를 다시 읽어 텍스트 블록 수, image block 수, 마지막 감사 블록 존재를 확인한다.
5. 실패 시 불완전 페이지 표시 또는 안전한 재개 전략을 구현한다.
6. run manifest와 검증 요약을 artifact로 보존한다. 원문 전문은 라이선스가 허용될 때만 보존한다.

### P2 — 고도화

1. 원자 주장 검증과 주제별 임계값을 추가한다.
2. 검색 관련성 평가용 작은 benchmark를 요일별로 만든다.
3. 필요할 때만 대화형 HTML 차트 1~2개를 추가하고 PNG fallback을 항상 제공한다.
4. 월별로 사람 검토 표본을 뽑아 자동 점수와 비교한다.

## 8. 테스트 체계 보완

초기 감사 당시 테스트 15개가 통과했고, v9.0 베이스라인 구현 후에는 21개가 `py -3.13 -m pytest -q`에서 모두 통과했다. 반면 PATH의 `pytest -q` 실행은 모듈 import 단계에서 실패했고, `python.exe`는 Python 3.12 환경에 pytest가 설치되지 않아 실패했다. 즉 코드 회귀와 별개로 개발 환경 진입점이 일관되지 않다. CI는 `python -m pytest`로 고정하고, 로컬도 가상환경과 Python 버전을 명시해야 한다.

테스트 내용에도 중요한 허점이 있다. Markdown 테스트는 실제 `publish_report()` 또는 변환 함수를 호출하지 않고 테스트 내부에서 같은 취지의 로직을 다시 구현한다. 따라서 실제 코드가 깨져도 테스트가 통과할 수 있다. 다음 테스트를 추가해야 한다.

- 모든 키워드 결과 병합, DOI 중복 제거, 관련성 정렬, 5편 미달 실패.
- 철회 논문 제외, journal source/게재본 버전/DOI 불일치 경고.
- 8,999자와 11,001자 거부, 참고문헌 제외 글자 수 계산.
- 근거 없는 숫자·날짜와 존재하지 않는 evidence ID 거부.
- 실제 Markdown→Notion 변환기의 링크·강조·6번 이상 번호 목록·표·이미지 테스트.
- 101개와 205개 블록이 각각 2회와 3회 batch로 모두 전송되는지 확인.
- child pagination, 429 `Retry-After`, timeout, 부분 실패 후 재개 테스트.
- 그림 4개일 때 실패, 5개일 때 통과, 각 그림의 캡션과 출처 검증.
- 게시 후 read-back 불일치 시 성공 알림을 보내지 않는지 확인.
- `01_Standard_Procedures` 또는 `.env`가 Git 추적 목록에 나타나면 실패.

GitHub Actions에는 테스트 단계를 현재 daily workflow 앞에 추가해야 한다. 지금 workflow는 의존성 설치 후 곧바로 실서비스 브리핑을 실행하므로, 테스트가 깨진 커밋도 Notion과 Slack을 변경할 수 있다. `test` job이 성공해야 `briefing` job이 실행되도록 의존성을 건다.

## 9. 완료 정의와 운영 지표

다음 조건을 모두 만족할 때 “신뢰성 강화 브리핑”이 완료된 것으로 정의한다.

1. 참고문헌을 제외한 본문이 9,000~11,000자이고, 요약·분석·반론/한계·실무 권고가 구분된다.
2. 주제 관련 공개 학술논문이 최소 5편이며 DOI 또는 OpenAlex ID로 중복되지 않는다.
3. 최신 정책·공고·통계 주제는 최소 2개의 공식 1차 자료를 추가한다.
4. 각 핵심 주장과 모든 숫자·날짜에 유효한 evidence ID가 연결된다.
5. 미지원 핵심 주장은 0건이며, 부분 지원 주장은 불확실성을 본문에 표시한다.
6. 검증된 데이터로 만든 인포그래픽이 최소 5개이고 각각 캡션·기준일·출처·alt text를 가진다.
7. Notion 게시 전후 블록 수와 그림 수가 일치하며 마지막 검증 요약 블록이 존재한다.
8. 실패한 실행은 성공 알림이나 `PASSED` 배지를 남기지 않는다.
9. run manifest만으로 사용 모델, 코드 버전, 검색시각, 선택 자료, 품질 결과를 재현할 수 있다.
10. 보호 폴더와 비밀 파일은 Git 추적 대상이 아니다.

주간 대시보드에는 성공률만 표시하지 말고 `검색 후보 수`, `최종 논문 수`, `공식 1차 자료 수`, `중복 제거 수`, `철회/불일치 제외 수`, `주장 지원율`, `부분 지원률`, `본문 글자 수`, `그림 수`, `게시 read-back 일치 여부`, `총 소요시간`을 기록한다. 이 지표가 있어야 실제 품질 저하를 조기에 발견할 수 있다.

## 10. 최종 권고

현재 시스템을 폐기할 필요는 없다. AcademicProvider–GeminiProvider–NotionPublisher의 큰 경계는 유지하되, 그 사이에 EvidenceNormalizer, ClaimVerifier, VisualRenderer, QualityGate를 명시적으로 추가하는 편이 가장 안전하다. 첫 구현 목표는 “더 그럴듯한 10,000자”가 아니라 **각 주장과 그림이 동일한 검증 데이터에서 파생되고, 기준 미달 결과는 게시되지 않는 파이프라인**이어야 한다.

Notion에서 인포그래픽을 보여주는 것은 기술적으로 가능하며, 최소 5개의 정적 PNG를 Notion File Upload API로 올리는 방식을 기본안으로 권고한다. 대화형 HTML은 가능한 기능이지만 신뢰성 목표 달성에 필수는 아니다. 먼저 정적 그림, 전체 블록 batch 게시, read-back 검증을 완성한 뒤 필요할 때 제한적으로 도입한다.

보안 측면에서는 루트 ignore와 Git 추적 해제를 이번에 적용했다. 이 변경이 실제 GitHub에서 효력을 가지려면 커밋·푸시되어야 한다. 과거 커밋에 민감값이 있었을 가능성은 정규식 검사만으로 완전히 배제할 수 없으므로, 의심되는 자격증명은 반드시 회전하고 필요하면 별도 절차로 Git 이력을 정리한다.

## 11. 추가 검토: Notion 블록 예산, Gemini 검색, 논문 10편 토큰

### 11.1 Notion 제한의 정확한 적용

운영 요구사항은 다음과 같이 고정한다.

- 하나의 rich text `text.content`는 최대 2,000자다. 경계값 오류와 링크·annotation 처리를 고려해 실제 분할 목표는 **블록당 1,600~1,800자 이하**로 둔다.
- block 배열은 한 요청에서 최대 100개다. Notion 공식 문서상 이는 **페이지 전체의 100블록 한도라기보다 요청 payload 내 배열의 100개 한도**다. 즉 페이지를 만든 뒤 `append block children`을 여러 번 호출하면 100개를 넘는 페이지도 기술적으로 게시할 수 있다.
- 그러나 본 프로젝트에서는 사용자의 운영 원칙을 더 엄격하게 적용하여 **한 브리핑 페이지당 90블록 이하**를 품질 게이트로 둔다. 10블록은 향후 경고·수정·추가 그림을 위한 여유분으로 남긴다.
- API 전체 payload에는 500KB 한도도 있으므로 블록 수와 별개로 직렬화된 요청 크기를 검사한다.
- 100블록을 초과한 결과를 `blocks[:100]`으로 자르는 것은 금지한다. 90블록을 넘으면 먼저 참고문헌과 캡션을 압축하고, 그래도 넘으면 명시적으로 실패시켜 재구성한다. 조용한 유실은 허용하지 않는다.

공식 제한은 [Notion Request limits](https://developers.notion.com/reference/request-limits)에 명시되어 있다. 이 문서는 `text.content` 2,000자, block/rich text 등 block-type 배열 100개, payload 500KB를 각각 별도 제한으로 설명한다.

#### 권장 90블록 예산

| 용도 | 목표 블록 수 | 작성 규칙 |
|---|---:|---|
| 제목·실행상태·목차 | 4 | 짧은 callout/heading |
| 10,000자 본문 | 18~25 | 문단당 약 400~900자, 최대 1,800자 |
| 표·핵심 권고 | 6~10 | 큰 표는 이미지 또는 여러 행으로 분리 |
| 인포그래픽 5개 | 15 | 그림마다 heading 1 + image 1 + caption 1 |
| 논문 10편 | 11 | 참고문헌 heading 1 + 논문당 paragraph 1 |
| 공식 1차 자료 | 5 | 자료당 1블록 또는 통합 목록 |
| 검증·감사 정보 | 5~8 | 품질 점수, 모델, 시각, run ID |
| 합계 | 64~78 | 상한 90, 여유 12~26 |

현재 참고문헌 렌더러처럼 논문 한 편을 heading, 저자, 학술지, DOI, 원문 링크, 초록 요약 등 6개 이상의 블록으로 만들면 10편만으로 약 60블록을 사용한다. 이는 본문과 그림을 더할 때 100개를 넘기기 쉽다. 논문 한 편의 서지정보와 링크는 하나의 paragraph 블록 안에서 rich text 줄바꿈과 hyperlink로 표현해야 한다. 초록 요약은 본문 근거 카드에서 이미 사용하므로 참고문헌에서 반복하지 않는다.

### 11.2 현재 검색 경로의 실사 결과

현재 스크립트에서 Gemini는 검색엔진이 아니다.

1. `AcademicProvider`가 `https://api.openalex.org/works`에 직접 요청하여 논문 후보를 얻는다.
2. DOI가 있으면 Crossref `/works/{doi}`를 호출하지만 현재는 주로 `original-title`을 보강한다.
3. `GeminiProvider._call_api()`는 수집된 제목·저자·학술지·초록을 prompt에 넣어 본문을 생성한다.
4. `_call_api()`에 `use_tools` 인자는 있으나 실제 `generate_content()` 요청에는 `tools` 설정이 없다. 따라서 Google Search Grounding은 현재 실행되지 않는다.

결론적으로 현재 시스템은 **OpenAlex 학술 검색 + 제한적 Crossref 보강 + Gemini 작성** 구조다. “Gemini 검색이 충분한가”가 아니라 “OpenAlex 한 곳의 검색 결과가 충분한가”를 물어야 하며, 답은 주제에 따라 충분하지 않다.

### 11.3 권장 하이브리드 검색 구조

Gemini의 Google Search Grounding은 최신 웹 사실과 다양한 출처를 찾고 응답에 URL citation을 연결할 수 있어 정책, 공고, 시장 동향에는 유용하다. 하지만 검색 쿼리와 순위가 모델 판단에 의존하고, 학술 문서 유형·철회·DOI·중복을 정밀 제어하는 전용 서지 API를 대체하지는 못한다. 공식 설명도 Google Search를 최신 사실에 대한 grounding 도구로 설명한다. [Gemini Google Search Grounding](https://ai.google.dev/gemini-api/docs/google-search)

권장 역할 분담은 다음과 같다.

| 검색 채널 | 담당 역할 | 단독 사용 여부 |
|---|---|---|
| OpenAlex | OA 후보, 서지, 초록, 철회 플래그, 학술지 위치 | 논문 후보의 주 검색원 |
| Crossref | DOI 해석, 제목·저자·연도·유형 교차 확인 | 검증 보조 |
| 국내 학술 소스 | 한국어·지역 건축 연구의 누락 보완 | 화·수·목·토·일 주제에 권장 |
| 정부·지자체·IRIS 공식 원문 | 정책, 통계, 공모 일정의 1차 증거 | 월·금 주제에 필수 |
| Gemini Google Search | 최신 웹 탐색, 공식 페이지 발견, 상충 정보 탐색 | 보조 검색원 |
| Gemini 생성 모델 | 근거팩을 사용한 종합·서술 | 검색 결과를 검증 없이 확정하면 안 됨 |

가장 안전한 흐름은 OpenAlex에서 논문 후보 30편을 수집하고, Crossref 및 메타데이터 규칙으로 검증·중복 제거한 뒤 상위 10편을 선택하는 것이다. 동시에 Google Search Grounding으로 최신 공식 자료를 찾되 `go.kr`, 지자체, IRIS 등 1차 도메인을 우선하고, 반환된 URL을 코드가 다시 요청해 제목·발행기관·기준일을 확인한다. Gemini가 검색 결과를 요약한 문장을 그대로 증거로 삼지 않고, 실제 원문 URL과 근거 구간을 evidence pack에 저장한다.

### 11.4 논문 10편의 토큰 예산

현재 사용 중인 Gemini 3.8/3.7/3.6 Flash 및 2.5 Flash 계열의 공식 입력 한도는 각각 약 1,048,576 tokens, 출력 한도는 65,536 tokens다. 따라서 **논문 10편이라는 개수만으로 토큰이 부족해지지는 않는다.** 공식 토큰 안내는 대략 1 token을 4 characters, 100 tokens를 60~80 English words 정도로 설명하지만 실제 한국어·수식·표·PDF는 차이가 있으므로 API의 `count_tokens`로 실행 직전에 측정해야 한다. [Gemini 3.8 Flash 사양](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash), [Gemini token 계산](https://ai.google.dev/gemini-api/docs/tokens)

| 입력 방식 | 논문당 예상 | 10편 합계 | 판정 |
|---|---:|---:|---|
| 서지 + 초록 | 약 500~1,000 tokens | 약 5,000~10,000 | 매우 여유 있음 |
| 초록 + 핵심 근거 구간 3~5개 | 약 1,500~3,000 | 약 15,000~30,000 | 권장 |
| 정제된 원문 전체 | 약 8,000~15,000 | 약 80,000~150,000 | 기술적으로 가능, 비권장 기본값 |
| 표·참고문헌·OCR 잡음을 포함한 PDF 전체 | 약 20,000~50,000 이상 | 약 200,000~500,000 이상 | 문서별 편차 큼, 비용·정확도 위험 |

10,000자 한국어 출력은 단순 4자/token 근사로 약 2,500 tokens지만 한국어 토큰화와 Markdown, 인용, 구조화 JSON을 고려해 **출력 예산 8,000~12,000 tokens**를 예약한다. 입력에는 prompt, tool 결과, 논문, 공식 자료가 모두 포함되므로 다음 예산을 코드로 강제하는 것이 안전하다.

- 목표 입력: 60,000 tokens 이하.
- 경고 구간: 60,001~120,000 tokens.
- 강제 요약/재선별: 120,000 tokens 초과.
- 절대 실행 상한: 사용 모델의 실시간 `input_token_limit`에서 출력 예약량과 10% 안전 여유를 뺀 값.
- 출력 예약: 최소 12,000 tokens. `max_output_tokens`를 명시하고 생성 후 9,000~11,000자 게이트를 별도로 검사한다.

원문 전체 10편이 1M context 안에 들어가더라도 모두 한 prompt에 넣는 방식은 권장하지 않는다. 장문 모델은 관련 정보가 입력 중간에 있을 때 활용률이 떨어질 수 있으며, 문서 수 자체가 늘어도 성능이 저하될 수 있다는 연구가 있다. [Lost in the Middle](https://direct.mit.edu/tacl/article/doi/10.1162/tacl_a_00638/119630/Lost-in-the-Middle-How-Language-Models-Use-Long), [More Documents, Same Length](https://aclanthology.org/2025.findings-emnlp.1064/)

따라서 권장 파이프라인은 두 단계다.

1. 논문별 추출 단계: 각 논문에서 연구질문, 방법, 표본, 주요 결과, 수치, 한계, 인용 가능한 근거 구간을 구조화 JSON으로 추출한다. 논문마다 별도 호출하거나 batch 처리하고 실제 token 사용량을 기록한다.
2. 종합 단계: 10개 구조화 요약과 필요한 핵심 근거 구간만 Gemini에 넣어 10,000자 보고서를 생성한다. 논문 원문은 검증 단계에서 필요한 주장에 대해서만 다시 참조한다.

이 방식이면 종합 prompt는 대체로 20,000~40,000 tokens 안에 유지할 수 있고, 10편을 모두 반영했는지 논문별 claim ID로 검사하기도 쉽다. Context Caching을 적용하면 동일 논문을 초안·검증·수정 호출에서 반복 사용할 때 전송 비용을 줄일 수 있다.

### 11.5 최종 판정

- **Notion:** 10,000자 + 논문 10편 + 그림 5개는 90블록 예산 안에서 충분히 게시 가능하다. 단, 논문당 한 블록, 그림당 세 블록 원칙과 1,800자 안전 분할이 필요하다.
- **검색:** 현재 Gemini 검색은 활성화되어 있지 않다. OpenAlex 단독도 충분하지 않다. OpenAlex/Crossref/국내 학술 소스/공식 1차 자료를 기본으로 하고 Gemini Google Search를 최신성 보조로 추가하는 하이브리드 구성이 적절하다.
- **토큰:** 논문 10편을 초록 또는 선별 근거 구간으로 투입하면 매우 충분하다. 정제 원문 전체도 모델 한도에는 대체로 들어가지만, 비용과 장문 활용 정확도 때문에 논문별 추출 후 종합하는 2단계 방식이 더 신뢰할 수 있다.
