"""
================================================================================
💡 MBSE Multi-Agent 오케스트레이터 (CrewAI + Gemini 3.0 Flash)
--------------------------------------------------------------------------------
이 스크립트를 구동하기 전에 가상환경에 다음 패키지들이 설치되어 있어야 합니다:
pip install crewai crewai-tools langchain-google-genai python-dotenv requests beautifulsoup4
================================================================================
"""

import os
import hashlib
from datetime import datetime
from dotenv import load_dotenv

import requests
from bs4 import BeautifulSoup

# CrewAI 패키지
from crewai import Agent, Task, Crew, Process
from crewai.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI

# [1. 환경 및 시스템 기본 설정]
load_dotenv()
API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

if not API_KEY:
    print("❌ .env 파일에 GEMINI_API_KEY 또는 GOOGLE_API_KEY가 필요합니다.")
    exit(1)

# LLM 설정: Gemini 1.5 Flash 모델 연동 (CrewAI 백엔드)
from crewai import LLM

llm = LLM(
    model="gemini/gemini-3-flash-preview",
    api_key=API_KEY,
    temperature=0.3
)

# 상태 관리 (State) 파일
HISTORY_FILE = "crewai_sent_history.txt"
OUTPUT_FILE = "crewai_daily_mbse_briefing.txt"

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(history)) + "\n")

import re
import xml.etree.ElementTree as ET
from datetime import timedelta, timezone
from urllib.parse import quote_plus
import time

# [새로 이식된 실제 스크래핑 설정]
DAYS_BACK = 7
CUTOFF_DATE = datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"
}
KEYWORDS = [
    "MBSE", "Model-Based Systems Engineering", "SysML", "Systems Modeling Language",
    "UAF", "Unified Architecture Framework", "Digital Engineering", "Digital Twin",
    "Systems Architecture", "Digital Thread",
]

def fetch_google_news_rss(query: str) -> list[dict]:
    articles = []
    encoded = quote_plus(query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=en&gl=US&ceid=US:en"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub_date_str = (item.findtext("pubDate") or "").strip()
            description = (item.findtext("description") or "").strip()
            source_elem = item.find("source")
            source_name = source_elem.text if source_elem is not None else ""
            
            pub_date = None
            if pub_date_str:
                try:
                    pub_date = datetime.strptime(pub_date_str, "%a, %d %b %Y %H:%M:%S %Z")
                    pub_date = pub_date.replace(tzinfo=timezone.utc)
                except ValueError:
                    pass
            if pub_date and pub_date < CUTOFF_DATE:
                continue
            if description:
                description = BeautifulSoup(description, "html.parser").get_text(separator=" ", strip=True)
            articles.append({"title": title, "url": link, "date": pub_date_str, "description": description, "source": source_name})
    except Exception as e:
        print(f"⚠️ RSS 수집 실패 ({query[:30]}…): {e}")
    return articles

def fetch_article_text(url: str, max_chars: int = 3000) -> str:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()
        main = soup.find("article") or soup.find("main") or soup.find("div", class_=re.compile(r"content|article|post|body"))
        text = (main or soup).get_text(separator="\n", strip=True)
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        return "\n".join(lines)[:max_chars]
    except Exception:
        return ""

# 도구 설정 (Scraping Tool)
@tool("Web Scraping and Search Tool")
def search_and_scrape(query: str) -> str:
    """방산/항공우주 기관 사이트(INCOSE, KAI 등) 및 단일 키워드나 쿼리에 대한 최신 트렌드를 검색하고 원본 텍스트를 추출하는 실제 툴입니다.
    입력(query)으로는 Google News RSS 검색어 문법이나 탐색할 문자열을 받습니다."""
    print(f"🔎 [Agent Tool] 실제 웹 검색 중: '{query}'")
    articles = fetch_google_news_rss(query)
    if not articles:
        return f"[{query}]에 대한 7일 이내 뉴스 검색 결과가 없습니다."
        
    result_text = f"[{query}]에 대한 최신 실제 수집 데이터 (상위 3건):\n"
    for idx, a in enumerate(articles[:3], 1): # 속도를 위해 상위 3건만 본문 추출
        full_text = fetch_article_text(a["url"], max_chars=1000)
        result_text += (
            f"\n--- {idx} ---\n"
            f"출처: {a['source']} | 제목: {a['title']}\n"
            f"설명: {a['description']}\n"
            f"본문 일부: {full_text}\n"
            f"URL: {a['url']}\n"
        )
    return result_text

# [2. 3-Agent 오케스트레이션 설계]

# Agent 1: Source Scout
source_scout = Agent(
    role="Source Scout",
    goal="방산/항공우주 기관 및 채용 사이트를 탐색해 '최근 7일' 이내의 데이터를 수집하되, 탐색 중 새롭게 발견된 웹사이트/PDF 출처의 공신력과 산업 내 영향력을 매우 엄격하게 평가하여 가치 있는 곳만 '신규 소싱 출처 리스트'에 추가한다.",
    backstory=(
        "당신은 전 세계의 보안/방산 및 항공우주 도메인을 누비는 최고의 정보 수집 요원이다. "
        "어떤 숨겨진 채용 공고나 PDF 문서의 흔적도 놓치지 않고 수집하며 뛰어난 멀티모달 능력으로 문맥을 읽어낸다. "
        "특히 무분별한 소싱을 방지하기 위해, 단순히 관련만 있는 사이트는 무시하고 해당 업계 내 영향력과 공신력을 확신할 수 있는 확실한 기관(예: 국방부 산하, 대형 방산기업 등)만 소스로 편입시키는 깐깐함을 자랑한다."
    ),
    tools=[search_and_scrape],
    llm=llm,
    verbose=True,
    allow_delegation=False
)

# Agent 2: Trend Analyzer
trend_analyzer = Agent(
    role="Trend Analyzer",
    goal="Source Scout이 수집한 원문을 분석하여 업계에서 새롭게 떠오르는 MBSE/UAF/SysML 관련 핵심 키워드를 추출한다.",
    backstory=(
        "당신은 수집된 파편화된 데이터 속에서 미래의 거대한 기술 트렌드를 읽어내는 날카로운 트렌드 분석가이다. "
        "MBSE 도메인과 직접 연관된 기술적 진보나 표준의 변화를 포착하는 데 천부적인 소질이 있다."
    ),
    llm=llm,
    verbose=True,
    allow_delegation=False
)

# Agent 3: Chief Evaluator
chief_evaluator = Agent(
    role="Chief Evaluator",
    goal="수집된 자료의 중요도를 1단계(일반), 2단계(실무 인사이트), 3단계(막대한 영향력/핵심적 기술 진보)로 평가하며, 3단계 문서 발견 시 다른 요원들에게 파생 키워드 및 추가 소싱 발굴 업무를 위임(Delegate)하여 최종 브리핑을 조율한다.",
    backstory=(
        "당신은 국방/항공우주 분야에서 20년 이상 MBSE를 연구하고 실무에 적용한 최고 책임형 수석 아키텍트(Chief Systems Engineer)이다. "
        "기준이 매우 높아서 가치 없는 홍보용 문서는 과감히 폐기한다. "
        "가장 중요하게 여기는 '3단계' 문서를 포착하게 되면, 스스로 결론을 내리기보다는 완벽을 기하기 위해 즉각 Source Scout 요원에게 유사 고신뢰도 출처의 추가 탐색을 지시하고, Trend Analyzer 요원에게는 해당 문서만의 딥다이브 파생 키워드 추출을 지시하는 철저한 원칙주의자다."
    ),
    llm=llm,
    verbose=True,
    allow_delegation=True
)

# [3. 태스크(Task) 및 프로세스 정의]

task1 = Task(
    description=(
        "웹 검색/스크래핑 툴을 활용해 기본 타겟 사이트에서 최신 데이터를 수집하라. "
        "'최근 7일' 내의 MBSE, SysML, UAF 관련 문서, 이미지/PDF 문맥 등 최신 데이터를 수집하라. "
        "수집 과정 중 기존에 없던 새로운 웹 자료나 PDF 출처가 발견되는 경우, 해당 기관의 방산/항공우주 산업 내 영향력과 신뢰성을 철저히 평가하여 가치 있다고 검증된 곳만 '신규 발굴 공식 소싱 리스트'로 함께 정리해 두어라."
    ),
    expected_output="최근 7일 이내의 정보 소스/원문 텍스트 데이터 및 공신력 검증을 통과한 [신규 발굴 소싱 출처 리스트]",
    agent=source_scout
)

task2 = Task(
    description=(
        "Task 1의 수집 결과를 바탕으로 '앞으로의 정보 획득 및 검색에 추가할 신규 키워드'를 생성하라. "
        "[핵심 제약사항]: 수집된 문맥들에서 반복 등장하는 '기술적 핵심 트렌드'만 선택하고, 무관한 단어로 인한 수집 폭증을 막기 위해 "
        "MBSE/UAF 도메인과 직접 연관된 키워드만 '하루 최대 1~2개'로 제한하여 도출하라."
    ),
    expected_output="향후 탐색 시 활용할 MBSE 연관 신규 키워드 1~2개",
    agent=trend_analyzer
)

task3 = Task(
    description=(
        "Task 1 데이터를 바탕으로 각 문서의 중요도를 1단계(일반), 2단계(실무 인사이트), 3단계(게임 체인저/대규모 도입/핵심 정책 변화)로 분류하라.\n"
        "만약 평가 내용 중 '3단계' 최고 중요도 항목이 하나라도 포착되었다면, 동료 요원에게 구체적으로 업무를 위임(Delegate)하여 다음 조치를 반드시 취하라:\n"
        "  1) Source Scout 요원 위임 지시: 3단계 문서와 연관된 또 다른 공신력 있는 기관의 관련 자료나 추가 출처 탐색 명령.\n"
        "  2) Trend Analyzer 요원 위임 지시: 해당 3단계 문서 한정으로 도출될 수 있는 '핵심 파생 신규 키워드' 추가 도출 명령.\n\n"
        "마지막으로 위임 결과까지 모두 취합하여, 실무 가치가 높은 분석만을 엄선해 다음 정확한 포맷으로 요약하라:\n"
        "1) 🚀 제목 (한글) [중요도: X단계]\n"
        "2) 📌 핵심 기술 내용 3줄 요약\n"
        "3) 💡 MBSE 실무 적용 인사이트 1줄\n\n"
        "결과물 맨 끝에는 다음의 두 항목을 반드시 포함하라:\n"
        "[💡 AI 추천 향후 탐색 키워드: (Task 2 키워드 및 추가 지시로 도출한 전체 내용)]\n"
        "[🔗 엄선된 신규 소싱 출처: (Task 1 및 위임 탐색으로 추가된 새 출처 목록)]\n\n"
        "만약 평가 결과 모두 무가치하다면 '새로 업데이트된 소식이 없습니다.' 문장만 반환하라."
    ),
    expected_output="중요도 평가(1~3단계), [신규 검색 키워드], [신규 소싱 출처]가 포함된 최종 브리핑(이모지 포함) 또는 '새로 업데이트된 소식이 없습니다.'",
    agent=chief_evaluator
)

# [4. 최종 출력 및 예외 처리 (오케스트레이션)]
crew = Crew(
    agents=[source_scout, trend_analyzer, chief_evaluator],
    tasks=[task1, task2, task3],
    process=Process.sequential,
    verbose=True
)

def main():
    print("🚀 CrewAI 기반 MBSE 멀티 에이전트 오케스트레이터 구동 시작...")
    
    # 신규 상태 관리 이력 로드
    history = load_history()
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    if today_str in history:
        print("ℹ️ 오늘 이미 오케스트레이터가 실행된 이력이 있습니다 (테스트 시 무시).")
        
    try:
        # CrewAI 프로세스 실행 (순차적 3-Agent 파이프라인)
        result = crew.kickoff()
        output_data = str(result).strip()
        
        # 새로운 정보 유무 및 예외 처리
        valid_keywords = ["새로 업데이트된 소식이 없습니다.", "새로 업데이트된 소식이 없습니다"]
        if any(kw in output_data for kw in valid_keywords) or not output_data:
            final_text = "새로 업데이트된 소식이 없습니다."
            print(f"\n📭 {final_text}")
        else:
            final_text = output_data
            print(f"\n✅ 오케스트레이션 완료! 최종 결과물:\n{'-'*60}\n{final_text}\n{'-'*60}")
            
            # 신규 이력 추가
            history.add(today_str)
            save_history(history)
            
        # 신규 파일로 저장
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(final_text)
            
        print(f"\n💾 결과가 '{OUTPUT_FILE}' 파일에 저장되었습니다.")
        
    except Exception as e:
        # 강력한 Try-Except 예외 처리
        error_msg = f"❌ 에이전트 오케스트레이션 구동 중 치명적 오류 발생: {e}"
        print(error_msg)
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(error_msg)

if __name__ == "__main__":
    main()
