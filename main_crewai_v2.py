"""
================================================================================
🚀 MBSE V2 Self-Evolving Agent (CrewAI + Pydantic + Dynamic Queries)
--------------------------------------------------------------------------------
기존 하드코딩된 쿼리를 폐기하고, AI가 스스로 검색 방향성을 진화시키는 구조입니다.
Pydantic을 적용하여 출력 포맷을 엄격하게 제한(Strict Formatting)합니다.
================================================================================
"""

import os
import json
import hashlib
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from dotenv import load_dotenv

from pydantic import BaseModel, Field
from typing import List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential

from crewai import Agent, Task, Crew, Process
from crewai.tools import tool
from crewai import LLM

# [1. 환경 설정 및 LLM 연동]
load_dotenv()
API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
if not API_KEY:
    raise SystemExit("❌ .env 파일에 GEMINI_API_KEY 설정이 필요합니다.")

import database
import sys

# Gemini 3.1 Flash Lite Preview 모델
llm = LLM(
    model="gemini/gemini-3.1-flash-lite-preview",
    api_key=API_KEY,
    temperature=0.2 # 포맷 준수를 위해 약간 낮춤
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CORE_QUERIES_FILE = os.path.join(BASE_DIR, "core_queries.json")
DYNAMIC_QUERIES_FILE = os.path.join(BASE_DIR, "dynamic_queries.json")
HISTORY_FILE = os.path.join(BASE_DIR, "crewai_sent_history_v2.txt")
OUTPUT_FILE = os.path.join(BASE_DIR, "kakao_daily_mbse_briefing.txt")

# [2. Pydantic 스키마 정의 (출력 포맷 강제화)]

class ArticleSummary(BaseModel):
    """단일 기사 요약 데이터 모델"""
    title_kr: str = Field(..., description="기사의 한글 번역 제목 (예: [보잉] 신규 MBSE 도입 프로세스 발표)")
    importance_level: int = Field(..., description="분석 중요도 (1: 일반, 2: 실무인사이트, 3: 메가트렌드/핵심도입)")
    summary_1: str = Field(..., description="1번째 줄 요약: 어떤 프로젝트/사업/배경에 대한 내용인지")
    summary_2: str = Field(..., description="2번째 줄 요약: 언급된 구체적인 요구 기술, 툴체인, 변화 포인트")
    summary_3: str = Field(..., description="3번째 줄 요약: 시스템/아키텍처 관점에서의 핵심 목표 및 성과 분석")
    insight: str = Field(..., description="실무 적용 인사이트 한 줄 (💡 파급력). 문서 상단의 [과거 연관 데이터베이스] 목록과 연관된 내용이 있다면 반드시 '[과거 기사 제목](원문링크)' 처럼 마크다운 하이퍼링크를 넣어 연속성을 서술할 것.")
    original_url: str = Field(..., description="기사 원문 URL")
    source_type: str = Field(default="news", description="소스 유형: 'news'(뉴스기사) 또는 'paper'(학술논문)")

class BriefingOutput(BaseModel):
    """최종 브리핑 출력 전체 구조체"""
    date: str = Field(..., description="오늘 날짜 (YYYY-MM-DD)")
    articles: List[ArticleSummary] = Field(..., description="분석된 전체 기사들의 요약 목록")

class DynamicQueryUpdate(BaseModel):
    """Trend Analyzer가 출력할 진화된 새 검색 쿼리 모델"""
    new_keyword_queries: List[str] = Field(..., description="구글 뉴스 검색에 새로 추가할 트렌드 쿼리 (최대 2개)")
    obsolete_queries: List[str] = Field(..., description="더 이상 성과가 안나와 삭제할 기존 dynamic_queries.json 내 쿼리 목록. 없으면 빈 리스트.")

# [3. Query 로딩 및 크롤링 모듈]

def load_json(filepath: str, default_data: dict) -> dict:
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"JSON 로드 오류 ({filepath}): {e}")
    return default_data

def get_combined_queries():
    core = load_json(CORE_QUERIES_FILE, {"keywords":[], "keyword_queries":[], "site_queries":{}, "paper_queries":[]})
    dyn = load_json(DYNAMIC_QUERIES_FILE, {"dynamic_keywords":[], "dynamic_keyword_queries":[]})
    
    keywords = core.get("keywords", []) + dyn.get("dynamic_keywords", [])
    queries = core.get("keyword_queries", []) + dyn.get("dynamic_keyword_queries", [])
    site_queries_list = list(core.get("site_queries", {}).values())
    paper_queries = core.get("paper_queries", [])
    
    # 중복 제거
    return list(set(keywords)), list(set(queries + site_queries_list)), paper_queries

def resolve_google_news_url(google_url: str) -> str:
    """Google News 리디렉트 URL을 실제 원문 URL로 변환"""
    if not google_url or 'news.google.com' not in google_url:
        return google_url
    try:
        from googlenewsdecoder import new_decoderv1
        result = new_decoderv1(google_url)
        if result.get('status') and result.get('decoded_url'):
            return result['decoded_url']
    except Exception:
        pass
    return google_url

def fetch_google_news_rss(query: str, cutoff_date: datetime) -> list[dict]:
    articles = []
    encoded = quote_plus(query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=en&gl=US&ceid=US:en"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            desc = (item.findtext("description") or "").strip()
            pub_date_str = (item.findtext("pubDate") or "").strip()
            source_el = item.find("source")
            source = source_el.text if source_el is not None else ""
            source_url = source_el.get("url", "") if source_el is not None else ""
            
            pub_date = None
            if pub_date_str:
                try:
                    pub_date = datetime.strptime(pub_date_str, "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=timezone.utc)
                except ValueError: pass
            
            if pub_date and pub_date < cutoff_date: continue
            
            if desc:
                desc = BeautifulSoup(desc, "html.parser").get_text(separator=" ", strip=True)
            
            # Google News 리디렉트 → 실제 원문 URL 추출
            real_url = resolve_google_news_url(link)
            
            articles.append({"title": title, "url": real_url, "desc": desc, "source": source, "source_url": source_url})
    except Exception:
        pass
    return articles

def fetch_article_text(url: str, max_chars=3000):
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer"]): tag.decompose()
        return soup.get_text(separator="\n", strip=True)[:max_chars]
    except Exception:
        return ""

# [3-2. 학술 논문 수집 모듈 (arXiv + Semantic Scholar)]

def fetch_arxiv_papers(query: str, max_results: int = 5) -> list[dict]:
    """arXiv API로 MBSE 관련 논문 검색 (Abstract 기반 — PDF 다운로드 불필요)"""
    encoded = quote_plus(query)
    url = f"http://export.arxiv.org/api/query?search_query=all:{encoded}&start=0&max_results={max_results}&sortBy=submittedDate&sortOrder=descending"
    papers = []
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        root = ET.fromstring(resp.content)
        for entry in root.findall('atom:entry', ns):
            title = (entry.findtext('atom:title', '', ns) or '').strip().replace('\n', ' ')
            abstract = (entry.findtext('atom:summary', '', ns) or '').strip().replace('\n', ' ')
            link_el = entry.find("atom:link[@type='text/html']", ns)
            link = link_el.get('href', '') if link_el is not None else ''
            published = (entry.findtext('atom:published', '', ns) or '')[:10]  # YYYY-MM-DD
            authors = [a.findtext('atom:name', '', ns) for a in entry.findall('atom:author', ns)]
            
            if not title or not abstract:
                continue
            papers.append({
                'title': title,
                'url': link,
                'desc': abstract[:500],
                'full_text': abstract,
                'source': 'arXiv',
                'source_url': 'https://arxiv.org',
                'source_type': 'paper',
                'authors': ', '.join(authors[:3]),
                'published': published
            })
    except Exception as e:
        print(f"⚠️ arXiv 검색 실패 ({query[:30]}...): {e}")
    return papers

def fetch_semantic_scholar(query: str, max_results: int = 5) -> list[dict]:
    """Semantic Scholar API로 MBSE 관련 논문 검색 (TLDR + Abstract 제공)"""
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        'query': query,
        'limit': max_results,
        'fields': 'title,abstract,url,year,authors,citationCount,tldr',
        'sort': 'relevance'
    }
    papers = []
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        for p in data.get('data', []):
            title = (p.get('title') or '').strip()
            abstract = (p.get('abstract') or '').strip()
            tldr = ''
            if p.get('tldr') and p['tldr'].get('text'):
                tldr = p['tldr']['text']
            paper_url = p.get('url', '')
            year = p.get('year', '')
            authors = [a.get('name', '') for a in (p.get('authors') or [])[:3]]
            citations = p.get('citationCount', 0)
            
            desc_text = tldr if tldr else (abstract[:500] if abstract else '')
            if not title or not desc_text:
                continue
            papers.append({
                'title': title,
                'url': paper_url,
                'desc': desc_text,
                'full_text': abstract or desc_text,
                'source': 'Semantic Scholar',
                'source_url': 'https://semanticscholar.org',
                'source_type': 'paper',
                'authors': ', '.join(authors),
                'published': str(year) if year else '',
                'citations': citations
            })
    except Exception as e:
        print(f"⚠️ Semantic Scholar 검색 실패 ({query[:30]}...): {e}")
    return papers

# [4. History 관리]
def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def make_hash(url: str, title: str):
    return hashlib.md5((url + title).lower().encode()).hexdigest()[:12]

# [5. CrewAI Agent 및 Task 설정 (Pydantic 연동)]

chief_evaluator = Agent(
    role="Chief Evaluator & Summarizer",
    goal="수집된 기사들의 중요도를 평가하고, 무가치한 스팸이나 단순 시스템 관리자 채용공고는 버린 뒤, Pydantic 기반의 엄격한 3줄 요약 포맷으로 구조화된 JSON 응답을 반환한다.",
    backstory="당신은 방산 및 항공우주 도메인의 최고 책임형 수석 아키텍트다. 형식 파괴를 결코 용납하지 않는 엄격한 원칙주의자이며, Pydantic 스키마 형식을 100% 준수하여 보고서를 작성한다.",
    llm=llm,
    verbose=True
)

trend_analyzer = Agent(
    role="Trend Analyzer & Query Evolving Architect",
    goal="요약된 기사 데이터를 분석하여 시장의 새로운 기술 트렌드를 포착하고, 다음 시스템 크롤링 시 사용될 새로운 구글 검색 쿼리를 창조해낸다.",
    backstory="당신의 임무는 파이썬 스크립트가 내일 검색할 '구글 뉴스 쿼리'를 스스로 발전(State Self-Feeding)시키는 것이다.",
    llm=llm,
    verbose=True
)

def run_v2_orchestrator():
    print("======================================================")
    print("🚀 [V2 아키텍처] MBSE Self-Evolving Agent 시작")
    print("======================================================")
    
    history = load_history()
    keywords, queries, paper_queries = get_combined_queries()
    
    print(f"📡 [Phase 1] 동적/코어 쿼리 병합 (총 {len(queries)}개 뉴스 쿼리 + {len(paper_queries)}개 논문 쿼리) ...")
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    
    # 뉴스 기사 수집
    raw_articles = []
    for q in queries:
        raw_articles.extend(fetch_google_news_rss(q, cutoff))
    
    # 뉴스 기사에 source_type 태깅
    for a in raw_articles:
        a['source_type'] = 'news'
    
    # [Phase 1.5] 학술 논문 수집 (arXiv + Semantic Scholar)
    print(f"\n📚 [Phase 1.5] 학술 논문 수집 ({len(paper_queries)}개 쿼리) ...")
    raw_papers = []
    for pq in paper_queries:
        raw_papers.extend(fetch_arxiv_papers(pq, max_results=3))
        raw_papers.extend(fetch_semantic_scholar(pq, max_results=3))
    print(f"📄 논문 수집 완료: {len(raw_papers)}건")
    
    # 뉴스 + 논문 통합
    all_raw = raw_articles + raw_papers
        
    unique_arts = []
    seen = set()
    for a in all_raw:
        h = make_hash(a['url'], a['title'])
        if h not in seen and h not in history:
            seen.add(h)
            unique_arts.append(a)
            
    news_count = sum(1 for a in unique_arts if a.get('source_type') != 'paper')
    paper_count = sum(1 for a in unique_arts if a.get('source_type') == 'paper')
    print(f"📊 수집 완료: 중복 제외 신규 {len(unique_arts)}건 (뉴스 {news_count} + 논문 {paper_count})")
    if not unique_arts:
        print("📭 신규 기사 없음.")
        return
    
    # [Anti-Bias] 특정 출처 편중 방지: 동일 소스 최대 2건
    MAX_PER_SOURCE = 2
    source_count = {}
    balanced_arts = []
    for a in unique_arts:
        src = (a.get('source') or '').strip().lower()
        # URL 기반 도메인도 체크 (source 태그가 없는 경우 대비)
        if not src:
            try:
                from urllib.parse import urlparse
                src = urlparse(a.get('url', '')).netloc.replace('www.', '')
            except:
                src = 'unknown'
        source_count[src] = source_count.get(src, 0) + 1
        if source_count[src] <= MAX_PER_SOURCE:
            balanced_arts.append(a)
        else:
            print(f"  ⚖️ 편중 방지: [{src}] 초과 기사 제외 → {a['title'][:40]}")
    
    print(f"⚖️ 소스 균형 조정 후: {len(balanced_arts)}건 (원본 {len(unique_arts)}건)")
    
    # 상위 10건(속도 조절) 본문 추출 (논문은 이미 full_text 보유)
    target_arts = balanced_arts[:10]
    for a in target_arts:
        if a.get('source_type') != 'paper' and not a.get('full_text'):
            a['full_text'] = fetch_article_text(a['url'])
        history.add(make_hash(a['url'], a['title']))
        
    articles_payload = json.dumps(target_arts, ensure_ascii=False)
    
    # DB 연동 초기화
    database.init_db()
    
    # RAG Context 준비
    rag_context = database.build_rag_context(articles_payload)
    eval_text = f"{rag_context}\n\n[오늘 수집된 최신 기사 및 논문 목록]\n{articles_payload[:18000]}"

    print("\n🤖 [Phase 2] CrewAI Pydantic 기반 평가 및 쿼리 발전 구조 진입")

    # Task 1: Pydantic으로 엄격한 3줄 요약 구조화
    task_evaluate = Task(
        description=f"다음 텍스트 형태의 수집 목록과 과거 데이터베이스를 읽어라:\n\n{eval_text}\n\n"
                    f"스팸이나 단순 직무 공고는 무시하고, 기술 동향 및 메가트렌드를 담은 최고 수준의 기사/논문만 골라 정리하라.\n"
                    f"학술 논문(source_type='paper')의 경우, 제목 앞에 [논문] 태그를 붙이고, source_type은 반드시 'paper'로 설정하라.\n"
                    f"뉴스 기사(source_type='news')의 경우, source_type을 'news'로 설정하라.\n"
                    f"인사이트를 작성할 때 과거 DB의 내용과 연결된다면, 과거 링크를 참조문헌처럼 하이퍼링크로 꼭 작성하라.",
        expected_output="엄격한 `BriefingOutput` JSON 스키마 구조로 맵핑된 결과",
        agent=chief_evaluator,
        output_pydantic=BriefingOutput  # 핵심 기능: 포맷 100% 강제화
    )
    
    # Task 2: Pydantic으로 동적 쿼리 응답 생성
    task_evolve = Task(
        description="이전 Task에서 도출된 최신 중요 기사들을 분석하라. 현재의 MBSE, SysML 트렌드에서 새롭게 떠오르는 기술 스택(예: UAF(Unified Architecture Framework), Cameo, SysML v2 API)이나 특정 국방 프로젝트명이 등장했다면 이를 구글 뉴스 검색이 가능한 검색어 쿼리(예: 'SysML v2' OR 'API')로 1~2개 만들어라.\n\n"
                    "⚠️ 중요 규칙:\n"
                    "1) 특정 기업명(RTX, Boeing, Lockheed 등)이나 기업 고유 프로젝트명(LTAMDS, JPALS 등)을 쿼리에 넣지 마라. 기업별 수집은 이미 site_queries가 담당한다.\n"
                    "2) UAF는 반드시 MBSE 문맥의 Unified Architecture Framework를 의미한다. 우크라이나 군(Ukrainian Armed Forces) 관련 기사는 MBSE와 무관하므로 반드시 제외하라. UAF 관련 쿼리 생성 시 반드시 'UAF \"Unified Architecture Framework\"' 형태로 작성하라.\n"
                    "3) 동적 쿼리는 반드시 범용 기술 트렌드 키워드(예: Digital Thread, MOSA, SysML v2)로만 구성하라.",
        expected_output="`DynamicQueryUpdate` JSON 스키마 구조로 된 신규 트렌드 쿼리 목록",
        agent=trend_analyzer,
        output_pydantic=DynamicQueryUpdate
    )
    
    crew = Crew(
        agents=[chief_evaluator, trend_analyzer],
        tasks=[task_evaluate, task_evolve],
        process=Process.sequential,
        verbose=True
    )
    
    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1.5, min=10, max=60))
    def execute_with_retry():
        print("⏳ [API 호출] Crew AI 작업 시작 (실패 시 자동 재시도)")
        return crew.kickoff()
        
    execute_with_retry()
    
    # Pydantic 파싱된 결과 추출
    final_briefing_obj = task_evaluate.output.pydantic
    dynamic_update_obj = task_evolve.output.pydantic
    
    # 날짜를 AI 출력 대신 실제 실행일로 강제 설정
    today_str = datetime.now().strftime("%Y-%m-%d")
    if hasattr(final_briefing_obj, "date"):
        final_briefing_obj.date = today_str
    
    # [Phase 3] 카카오톡 텍스트 포맷으로 마크다운 변환 및 저장
    if hasattr(final_briefing_obj, "articles") and final_briefing_obj.articles:
        text_out = f"📋 MBSE 데일리 브리핑 (V2) ({today_str})\n"
        text_out += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for art in final_briefing_obj.articles:
            level_str = "🔥 "*art.importance_level
            text_out += f"🚀 {art.title_kr} [중요도: {art.importance_level}단계 {level_str}]\n"
            text_out += f"📌 [분석] 핵심 3줄 요약:\n"
            text_out += f"  1. {art.summary_1}\n"
            text_out += f"  2. {art.summary_2}\n"
            text_out += f"  3. {art.summary_3}\n"
            text_out += f"💡 산업 동향 인사이트: {art.insight}\n"
            text_out += f"🔗 원문: {art.original_url}\n"
            text_out += f"{'-'*40}\n"
            
            # DB 저장 연동
            source_type = getattr(art, 'source_type', 'news') or 'news'
            database.insert_article(
                date=final_briefing_obj.date,
                title_kr=art.title_kr,
                importance_level=art.importance_level,
                summary_1=art.summary_1,
                summary_2=art.summary_2,
                summary_3=art.summary_3,
                insight=art.insight,
                original_url=art.original_url,
                source_type=source_type
            )
            
        text_out += "\n🤖 [자가진화(Self-Evolving) 알림]\n"
        if hasattr(dynamic_update_obj, "new_keyword_queries") and dynamic_update_obj.new_keyword_queries:
            text_out += f"▶ 내일을 위해 Trend Analyzer가 신규 구글 검색 쿼리를 자동 추가했습니다:\n"
            for q in dynamic_update_obj.new_keyword_queries:
                text_out += f"  - [{q}]\n"
                
            # Dynamic_queries.json 실제 업데이트 반영
            dyn = load_json(DYNAMIC_QUERIES_FILE, {"dynamic_keywords":[], "dynamic_keyword_queries":[]})
            dyn.setdefault("dynamic_keyword_queries", []).extend(dynamic_update_obj.new_keyword_queries)
            # 중복 제거 및 저장
            dyn["dynamic_keyword_queries"] = list(set(dyn["dynamic_keyword_queries"]))
            with open(DYNAMIC_QUERIES_FILE, 'w', encoding='utf-8') as f:
                json.dump(dyn, f, ensure_ascii=False, indent=4)
    else:
        text_out = "📭 가치 있는 신규 기사가 없습니다."
        
    print(f"\n{text_out}")
    
    # 카카오톡 전송 트리거 (200자 제한 요약 메시지)
    try:
        from kakao_sender import send_to_kakao
        # 카카오 text 템플릿은 200자 제한이므로 요약본 생성
        kakao_msg = f"📋 MBSE 브리핑 ({final_briefing_obj.date if hasattr(final_briefing_obj, 'date') else datetime.now().strftime('%Y-%m-%d')})\n"
        if hasattr(final_briefing_obj, 'articles') and final_briefing_obj.articles:
            for i, art in enumerate(final_briefing_obj.articles[:5], 1):
                level_mark = '🔥' * art.importance_level
                title_short = art.title_kr[:30] + ('...' if len(art.title_kr) > 30 else '')
                kakao_msg += f"{i}. {level_mark} {title_short}\n"
            kakao_msg += "\n💻 전체 분석은 대시보드에서 확인"
        else:
            kakao_msg = "📭 오늘은 신규 기사가 없습니다."
        send_to_kakao(kakao_msg)
    except Exception as e:
        print(f"카카오 전송 에러: {e}")
        
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(text_out)
        
    # 히스토리 갱신
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(list(history)))

    # Streamlit Cloud 자동 반영: DB + 동적 쿼리 git push
    try:
        import subprocess
        today_tag = datetime.now().strftime('%Y-%m-%d')
        subprocess.run(['git', 'add', 'mbse_history.db', 'dynamic_queries.json'], check=True)
        result = subprocess.run(
            ['git', 'commit', '-m', f'Auto-sync: DB + queries ({today_tag})'],
            capture_output=True, text=True
        )
        if 'nothing to commit' not in result.stdout:
            subprocess.run(['git', 'push'], check=True)
            print('✅ Git push 완료 — Streamlit Cloud에 자동 반영됩니다.')
        else:
            print('ℹ️ 변경 없음 — git push 생략.')
    except Exception as e:
        print(f'⚠️ Git push 실패 (수동으로 push 필요): {e}')

if __name__ == "__main__":
    run_v2_orchestrator()
