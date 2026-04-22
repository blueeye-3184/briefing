import os
import time
import random
import requests
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple, cast
from google import genai # type: ignore
from google.genai import types # type: ignore
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type # type: ignore
from dotenv import load_dotenv # type: ignore

# .env 파일 로드 (로컬 개발 환경용)
load_dotenv()

# [환경 변수]
GEMINI_API_KEY: Optional[str] = os.environ.get('GEMINI_API_KEY')
NOTION_TOKEN: Optional[str] = os.environ.get('NOTION_TOKEN')
PARENT_PAGE_ID: str = os.environ.get('PARENT_PAGE_ID', '30da70ceb29b81f28bfde4bd8a03d3e0')

# KST (UTC+9) 설정
KST: timezone = timezone(timedelta(hours=9))

# ==========================================
# Domain Layer
# ==========================================
class BriefingSchedule:
    """요일별 주제 관리 도메인"""
    SCHEDULE: Dict[int, Tuple[str, str]] = {
        0: ("월요일", "구미/김천 지역 부동산 정책 및 시장 흐름 분석"),
        1: ("화요일", "친환경 건축 기술 (목조 건축, 현대 황토 건축) 최신 트렌드"),
        2: ("수요일", "설계 자동화 기술 및 BIM (Building Information Modeling) 최신 동향"),
        3: ("목요일", "최신 조경 디자인 및 외부 공간 설계 트렌드"),
        4: ("금요일", "건축 관련 R&D 국책 과제 및 IRIS 공모전 동향"),
        5: ("토요일", "건축사사무소 운영 시스템 효율화 방안"),
        6: ("일요일", "건축 관련 데이터베이스(DB) 관리 및 활용 방안")
    }

    @classmethod
    def get_today_topic(cls) -> Tuple[str, str]:
        now: datetime = datetime.now(KST)
        day_idx: int = now.weekday()
        topic_tuple: Optional[Tuple[str, str]] = cls.SCHEDULE.get(day_idx)
        return topic_tuple if topic_tuple is not None else ("오늘", "일반 주제")

class BriefingReport:
    """생성된 리포트 데이터 모델"""
    def __init__(self, day_name: str, topic: str, content: str) -> None:
        self.date: datetime = datetime.now(KST)
        self.day_name: str = day_name
        self.topic: str = topic
        self.content: str = content

    @property
    def folder_names(self) -> Tuple[str, str]:
        # 월 폴더: '2026년 04월' (표준화)
        month_str: str = self.date.strftime('%Y년 %m월')
        
        # 주차 폴더: 'X주차 분석' (사용자 실사 결과 반영)
        week_num: int = (self.date.day - 1) // 7 + 1
        week_str: str = f"{week_num}주차 분석"
        return month_str, week_str

    @property
    def page_title(self) -> str:
        # 페이지 제목: '요일 주간 보고: 주제' (사용자 실사 결과 반영)
        return f"{self.day_name} 주간 보고: {self.topic}"

# ==========================================
# Infrastructure Layer
# ==========================================
class GeminiProvider:
    """Gemini API 제공자 (안정적인 1.5 모델 기반 회피 로직)"""
    def __init__(self, api_key: Optional[str]) -> None:
        # Pylance UnknownMemberType 회피를 위한 Any 캐스팅
        self.client: Any = None
        if api_key:
            # v1beta API 버전이 Search Grounding 등 도구 지원에 더 적합함
            client_instance: Any = genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(api_version='v1beta')
            ) # type: ignore
            self.client = client_instance
        # 2026년 4월 기준 실제 지원 모델 리스트
        self.models: List[str] = [
            "gemini-2.0-flash",       # 범용 안정판
            "gemini-2.0-pro",         # 고성능
            "gemini-2.5-flash",       # 최신 주력
            "gemini-1.5-flash",       # 레거시 안정
            "gemini-2.0-flash-lite"   # 경량
        ] 

    def generate_content(self, topic: str) -> str:
        if self.client is None:
            raise ValueError("GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")
        
        if os.environ.get('GITHUB_ACTIONS'):
            jitter: int = random.randint(0, 300)
            print(f"[정보] 트래픽 분산을 위해 {jitter}초 대기 후 시작합니다...")
            time.sleep(jitter)

        last_err: Optional[Exception] = None
        for model_name in self.models:
            try:
                print(f"[시도] {model_name} 모델로 리포트 생성 중...")
                return self._call_api(model_name, topic)
            except Exception as e:
                # 400 에러(Invalid Argument) 발생 시 도구 없이 다시 시도해봄
                if "400" in str(e) or "tools" in str(e).lower():
                    try:
                        print(f"[정보] {model_name} 도구 제외 후 재시도...")
                        return self._call_api(model_name, topic, use_tools=False)
                    except Exception as e2:
                        print(f"[경고] {model_name} 최종 실패: {e2}")
                        last_err = e2
                else:
                    print(f"[경고] {model_name} 실패: {e}")
                    last_err = e
                
                time.sleep(10)
                continue
        
        if isinstance(last_err, Exception):
            raise last_err
        return "리포트 생성 실패"

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(4 if os.environ.get('GITHUB_ACTIONS') else 2),
        wait=wait_exponential(multiplier=20 if os.environ.get('GITHUB_ACTIONS') else 10, min=60, max=600), 
        reraise=True
    )
    def _call_api(self, model_name: str, topic: str, use_tools: bool = True) -> str:
        prompt: str = (
            f"[{topic}]에 대해 대한민국 건축 분야 전문가 수준의 '학술적 심층 분석 리포트'를 작성해줘.\n\n"
            f"다음 요구사항을 엄격히 준수할 것:\n"
            f"1. 분량: 공백 포함 5,000자 내외의 전문적인 내용을 담을 것.\n"
            f"2. 핵심 출처 타겟팅: 반드시 '대한건축학회(AIK)', 'DBpia', 'RISS', '구글 스칼라'에서 검색되는 최신 논문과 기술 보고서의 데이터를 인용할 것.\n"
            f"3. 전문성: 단순 뉴스보다는 학술적 이론, 실험 데이터, 설계 표준(KDS/KCS) 등을 언급하며 깊이 있게 서술할 것.\n"
            f"4. 자료 명시: 인용 시 [논문명 / 저자 / 대한건축학회 / 발행연도] 식으로 출처를 정밀하게 표기할 것.\n"
            f"5. 검색 전략: 검색 도구를 활용해 위 학술 사이트들의 공개된 인덱스 정보를 최대한 활용할 것."
        )
        
        tools: List[Any] = []
        if use_tools:
            try:
                search_tool = types.Tool(google_search_retrieval=types.GoogleSearchRetrieval())
                tools.append(search_tool)
            except Exception:
                pass
        
        client: Any = self.client
        config_args: Dict[str, Any] = {}
        if tools:
            config_args["tools"] = tools

        response: Any = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(**config_args)
        )
        
        text_val: Optional[Any] = getattr(response, 'text', None)
        if not isinstance(text_val, str) or not text_val:
            raise ValueError(f"{model_name} 모델로부터 유효한 텍스트 응답을 받지 못했습니다.")
            
        return text_val

class NotionPublisher:
    """Notion API 저장소"""
    def __init__(self, token: Optional[str]) -> None:
        self.token: Optional[str] = token
        auth_token: str = token if token else ""
        self.headers: Dict[str, str] = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }

    def request(self, method: str, url: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if self.token is None:
            raise ValueError("NOTION_TOKEN이 설정되지 않았습니다.")
        res: requests.Response = requests.request(method, url, headers=self.headers, json=data)
        try:
            res.raise_for_status()
        except requests.exceptions.HTTPError as e:
            print(f"[오류 상세] Notion API Response: {res.text}")
            raise e
        return cast(Dict[str, Any], res.json())

    def get_or_create_page(self, parent_id: str, title: str, icon: str = "📝") -> str:
        existing_id: Optional[str] = self.find_page_by_title(title)
        if existing_id is not None:
            print(f"[정보] 기존 페이지 발견: {title} ({existing_id})")
            return existing_id

        data: Dict[str, Any] = {
            "parent": {"page_id": parent_id},
            "icon": {"type": "emoji", "emoji": icon},
            "properties": {"title": {"title": [{"text": {"content": title}}]}}
        }
        res: Dict[str, Any] = self.request("POST", "https://api.notion.com/v1/pages", data)
        new_id: Any = res.get('id')
        if not isinstance(new_id, str):
            raise ValueError("페이지 생성 후 ID를 받지 못했습니다.")
        return new_id

    def find_page_by_title(self, title: str) -> Optional[str]:
        """제목으로 기존 페이지 검색"""
        data: Dict[str, Any] = {
            "query": title,
            "filter": {"value": "page", "property": "object"},
            "sort": {"direction": "descending", "timestamp": "last_edited_time"}
        }
        res: Dict[str, Any] = self.request("POST", "https://api.notion.com/v1/search", data)
        
        # Pylance UnknownMemberType 에러 방지를 위한 촘촘한 타입 가드
        raw_results: Any = res.get('results')
        if not isinstance(raw_results, list):
            return None

        for result in raw_results:
            if not isinstance(result, dict): continue
            res_dict = cast(Dict[str, Any], result)
            
            props: Any = res_dict.get('properties')
            if not isinstance(props, dict): continue
            props_dict = cast(Dict[str, Any], props)
            
            title_container: Any = props_dict.get('title')
            if not isinstance(title_container, dict): continue
            tc_dict = cast(Dict[str, Any], title_container)
                
            title_list: Any = tc_dict.get('title')
            if isinstance(title_list, list) and len(title_list) > 0:
                first_node: Any = title_list[0]
                if isinstance(first_node, dict):
                    fn_dict = cast(Dict[str, Any], first_node)
                    if fn_dict.get('plain_text') == title:
                        f_id: Any = res_dict.get('id')
                        return cast(str, f_id) if isinstance(f_id, str) else None
        return None

    def publish_report(self, parent_id: str, report: BriefingReport) -> None:
        """마크다운을 Notion 블록으로 변환하여 발행"""
        blocks: List[Dict[str, Any]] = []
        for line in report.content.split('\n'):
            raw: str = line.strip()
            if not raw: continue
            
            b_t: str = "paragraph"
            txt: str = raw
            if raw.startswith('###'): b_t = "heading_3"; txt = raw[3:].strip()
            elif raw.startswith('##'): b_t = "heading_2"; txt = raw[2:].strip()
            elif raw.startswith('#'): b_t = "heading_1"; txt = raw[1:].strip()
            elif raw.startswith(('- ', '* ')): b_t = "bulleted_list_item"; txt = raw[2:].strip()
            elif raw.startswith(('1. ', '2. ', '3. ', '4. ', '5. ')): b_t = "numbered_list_item"; txt = raw[3:].strip()

            if not txt: continue # 텍스트 내용이 없으면 블록 생성 건너뜀

            limit: int = 2000
            chunks: List[str] = [txt[i:i + limit] for i in range(0, len(txt), limit)]
            for chunk in chunks:
                if not chunk.strip(): continue # 공백만 있는 청크 제외
                blocks.append({
                    "object": "block",
                    "type": b_t,
                    b_t: {"rich_text": [{"text": {"content": chunk}}]}
                })

        # 노션 API는 한 번에 최대 100개의 블록만 생성 가능
        data: Dict[str, Any] = {
            "parent": {"page_id": parent_id},
            "properties": {"title": {"title": [{"text": {"content": report.page_title}}]}},
            "children": blocks[:100]
        }
        self.request("POST", "https://api.notion.com/v1/pages", data)

# ==========================================
# Application Layer
# ==========================================
class BriefingApplicationService:
    def __init__(self, gemini: GeminiProvider, notion: NotionPublisher) -> None:
        self.gemini = gemini
        self.notion = notion

    def run_daily_briefing(self) -> None:
        day_name, topic = BriefingSchedule.get_today_topic()
        print(f"[{datetime.now(KST).strftime('%Y-%m-%d')}] 주제: {topic}")

        try:
            content: str = self.gemini.generate_content(topic)
            report: BriefingReport = BriefingReport(day_name, topic, content)
            
            names: Tuple[str, str] = report.folder_names
            m_id: str = self.notion.get_or_create_page(PARENT_PAGE_ID, names[0], "📁")
            w_id: str = self.notion.get_or_create_page(m_id, names[1], "📂")
            
            self.notion.publish_report(w_id, report)
            print(f"[성공] 노션 저장 완료")
        except Exception as e:
            print(f"[실패] 오류 발생: {e}")

    # 인자 이름 불일치 가능성을 방지하기 위한 오버로딩 또는 직접 호출 수정
    def _publish(self, pid: str, r: BriefingReport) -> None:
        self.notion.publish_report(pid, r)

if __name__ == "__main__":
    g_p = GeminiProvider(GEMINI_API_KEY)
    n_p = NotionPublisher(NOTION_TOKEN)
    service = BriefingApplicationService(g_p, n_p)
    service.run_daily_briefing()
