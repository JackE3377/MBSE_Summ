"""
==========================================================
MBSE 최신 동향 자동화 에이전트
----------------------------------------------------------
웹 스크래핑 → 중복 필터링 → Gemini AI 요약 → 브리핑 파일 생성
==========================================================
"""

import os
import re
import hashlib
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from google import genai


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 환경 설정
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    raise SystemExit("❌ .env 파일에 GEMINI_API_KEY 또는 GOOGLE_API_KEY를 설정해주세요.")

BASE_DIR = Path(__file__).parent
HISTORY_FILE = BASE_DIR / "sent_history.txt"
OUTPUT_FILE = BASE_DIR / "kakao_daily_mbse_briefing.txt"

DAYS_BACK = 7
CUTOFF_DATE = datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )
}

# 검색/수집 키워드
KEYWORDS = [
    "MBSE", "Model-Based Systems Engineering",
    "SysML", "Systems Modeling Language",
    "UAF", "Unified Architecture Framework",
    "Digital Engineering", "Digital Twin",
    "Systems Architecture", "Digital Thread",
]

# ── Google News RSS 검색 쿼리 ──────────────────────────
# A) 핵심 키워드 쿼리 (글로벌)
KEYWORD_QUERIES = [
    'MBSE "Model-Based Systems Engineering"',
    'SysML "Systems Modeling Language"',
    '"Digital Engineering" defense OR military OR aerospace',
    '"Digital Twin" defense OR military OR aerospace',
    '"Systems Architecture" defense OR MBSE',
    'UAF "Unified Architecture Framework"',
    '"Digital Thread" systems engineering',
    'SysML 2.0',
    '"model based" "systems engineering" defense',
]

# B) 사이트별 검색 — 직접 스크래핑이 차단되는 사이트도 Google News 경유로 수집
SITE_QUERIES_MAP = {
    # ── 표준/학술 기관 ──
    "INCOSE":           'site:incose.org MBSE OR SysML OR "systems engineering"',
    "DAU":              'site:dau.edu "digital engineering" OR MBSE OR "systems engineering"',
    "MITRE":            'site:mitre.org "digital twin" OR MBSE OR "systems engineering"',
    "OMG":              'site:omg.org SysML OR UAF OR "systems modeling"',
    "NIST":             'site:nist.gov "digital twin" OR MBSE OR "model-based"',
    "SEI/CMU":          'site:sei.cmu.edu MBSE OR "systems engineering" OR "digital engineering"',

    # ── 학계 ──
    "Georgia Tech":     'site:gatech.edu MBSE OR SysML OR "systems engineering" OR "digital twin"',
    "MIT":              'site:mit.edu MBSE OR "digital engineering" OR "systems architecture"',
    "Stevens":          'site:stevens.edu MBSE OR "systems engineering"',
    "Purdue":           'site:purdue.edu MBSE OR "digital engineering" OR "systems engineering"',

    # ── 방위산업체 (Prime Contractors) ──
    "Lockheed Martin":  'site:lockheedmartin.com MBSE OR "digital engineering" OR "digital twin" OR "digital thread"',
    "Boeing":           'site:boeing.com MBSE OR "digital engineering" OR "digital twin" OR "model-based"',
    "Northrop Grumman": 'site:northropgrumman.com MBSE OR "digital engineering" OR "digital twin"',
    "RTX/Raytheon":     'site:rtx.com MBSE OR "digital engineering" OR "digital twin" OR "model-based"',
    "BAE Systems":      'site:baesystems.com MBSE OR "digital engineering" OR "digital twin"',
    "L3Harris":         'site:l3harris.com MBSE OR "digital engineering" OR "digital twin"',
    "General Dynamics": 'site:gd.com MBSE OR "digital engineering" OR "digital twin"',
    "SAIC":             'site:saic.com MBSE OR "digital twin" OR "digital engineering"',
    "Leidos":           'site:leidos.com MBSE OR "digital engineering" OR "digital twin"',

    # ── 군/정부 기관 ──
    "Defense.gov":      'site:defense.gov "digital engineering" OR "digital twin" OR MBSE',
    "USAF":             'site:af.mil "digital engineering" OR MBSE OR "digital twin"',
    "US Army":          'site:army.mil "digital engineering" OR MBSE OR "digital twin"',
    "US Navy":          'site:navy.mil "digital engineering" OR MBSE OR "digital twin"',
    "NASA":             'site:nasa.gov MBSE OR "model-based" OR "digital twin" OR SysML',
    "DARPA":            'site:darpa.mil "digital engineering" OR "digital twin" OR MBSE',

    # ── FFRDC (연방 연구개발센터) ──
    "RAND":             'site:rand.org "digital engineering" OR MBSE OR "systems engineering" OR "digital twin"',
    "Aerospace Corp":   'site:aerospace.org MBSE OR "digital engineering" OR "digital twin" OR "systems architecture"',
    "IDA":              'site:ida.org MBSE OR "digital engineering" OR "systems engineering"',
    "MIT Lincoln Lab":  'site:ll.mit.edu MBSE OR "digital engineering" OR "digital twin"',
    "JHU APL":          'site:jhuapl.edu MBSE OR "digital engineering" OR "digital twin" OR "systems engineering"',

    # ── 군 연구소 ──
    "AFRL":             'site:afresearchlab.com "digital engineering" OR MBSE OR "digital twin"',
    "ARL":              'site:arl.army.mil MBSE OR "digital engineering" OR "digital twin"',
    "NRL":              'site:nrl.navy.mil MBSE OR "digital engineering" OR "digital twin"',
    "DEVCOM":           'site:devcom.army.mil MBSE OR "digital engineering" OR "digital twin"',

    # ── 획득/정책/연구센터 ──
    "OUSD R&E":         'site:cto.mil "digital engineering" OR MBSE OR "digital twin"',
    "DTIC":             'site:dtic.mil MBSE OR "digital engineering" OR "model-based"',
    "SERC":             'site:sercuarc.org MBSE OR "digital engineering" OR "systems engineering"',
    "DSIAC":            'site:dsiac.org MBSE OR "digital engineering" OR "digital twin"',

    # ── 국제 ──
    "NATO":             'site:nato.int MBSE OR "architecture framework" OR "digital transformation" OR NAF',
    "UK MOD":           'site:gov.uk MBSE OR "digital engineering" OR "digital twin" defence',

    # ── 국내 방산/연구/정부 기관 ──
    "ADD(국방과학연구소)": 'site:add.re.kr MBSE OR "디지털 엔지니어링" OR "디지털 트윈" OR "시스템 엔지니어링"',
    "DAPA(방위사업청)":    'site:dapa.go.kr MBSE OR "디지털 엔지니어링" OR "디지털 트윈" OR "무기체계"',
    "KEIT":              'site:keit.re.kr MBSE OR "디지털 엔지니어링" OR "디지털 트윈"',
    "DTaQ(기품원)":        'site:dtaq.re.kr MBSE OR "디지털 엔지니어링" OR "디지털 트윈"',
    "KRIT(국기연)":        'site:krit.re.kr MBSE OR "디지털 엔지니어링" OR "디지털 트윈"',
    "KAI(한국항공우주)":   'site:koreaaero.com MBSE OR "디지털 엔지니어링" OR "디지털 트윈" OR SysML',
    "Hanwha Aerospace":  'site:hanwhaaerospace.co.kr MBSE OR "디지털 엔지니어링" OR "디지털 트윈"',
    "LIG Nex1":          'site:lignex1.com MBSE OR "디지털 엔지니어링" OR "디지털 트윈"',

    # ── 도구 벤더 ──
    "Dassault":         'site:3ds.com MBSE OR SysML OR "Cameo" OR "MagicDraw" OR "digital twin"',
    "Siemens":          'site:siemens.com MBSE OR "digital twin" OR "systems engineering" OR Teamcenter',
    "IBM":              'site:ibm.com MBSE OR "Rhapsody" OR "digital engineering" OR "systems engineering"',

    # ── 국방/항공우주 전문 미디어 ──
    "Defense News":     'site:defensenews.com "digital engineering" OR MBSE OR "digital twin"',
    "Aviation Week":    'site:aviationweek.com MBSE OR "digital engineering" OR "digital twin"',
    "Breaking Defense": 'site:breakingdefense.com "digital engineering" OR MBSE OR "digital twin"',
    "C4ISRNet":         'site:c4isrnet.com "digital engineering" OR MBSE OR "digital twin"',
    "SpaceNews":        'site:spacenews.com "digital engineering" OR MBSE OR "digital twin"',
    "Janes":            'site:janes.com MBSE OR "digital engineering" OR "digital twin"',
    "AFCEA Signal":     'site:afcea.org MBSE OR "digital engineering" OR "digital twin"',
}

SEARCH_QUERIES = KEYWORD_QUERIES + list(SITE_QUERIES_MAP.values())


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 히스토리(State) 관리
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def load_history() -> set[str]:
    """sent_history.txt에서 이미 전송된 기사 키 로드."""
    if HISTORY_FILE.exists():
        lines = HISTORY_FILE.read_text(encoding="utf-8").strip().splitlines()
        return set(line.strip() for line in lines if line.strip())
    return set()


def save_history(history: set[str]) -> None:
    """sent_history.txt에 히스토리 저장."""
    HISTORY_FILE.write_text(
        "\n".join(sorted(history)) + "\n", encoding="utf-8"
    )


def _normalize_title(title: str) -> str:
    """제목에서 특수문자/공백 제거 후 소문자 해시 → 동일 기사 다른 URL 감지."""
    cleaned = re.sub(r"[^a-z0-9가-힣]", "", title.lower())
    return hashlib.md5(cleaned.encode("utf-8")).hexdigest()[:12]


def make_article_keys(url: str, title: str) -> list[str]:
    """기사당 복수 키 반환: URL 키 + 제목 해시 키. 둘 중 하나라도 히스토리에 있으면 중복."""
    keys = []
    if url and url.startswith("http"):
        keys.append("url:" + url.strip())
    if title:
        keys.append("title:" + _normalize_title(title))
    return keys


def is_in_history(history: set[str], url: str, title: str) -> bool:
    """URL 또는 제목 기반으로 히스토리에 존재하는지 확인."""
    return any(k in history for k in make_article_keys(url, title))


def add_to_history(history: set[str], url: str, title: str) -> None:
    """URL + 제목 해시 키를 모두 히스토리에 추가."""
    for k in make_article_keys(url, title):
        history.add(k)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1) Google News RSS 수집
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def fetch_google_news_rss(query: str) -> list[dict]:
    """Google News RSS에서 기사를 수집한다."""
    articles: list[dict] = []
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

            # pubDate 파싱 & 7일 필터
            pub_date = None
            if pub_date_str:
                try:
                    pub_date = datetime.strptime(
                        pub_date_str, "%a, %d %b %Y %H:%M:%S %Z"
                    )
                    pub_date = pub_date.replace(tzinfo=timezone.utc)
                except ValueError:
                    pass

            if pub_date and pub_date < CUTOFF_DATE:
                continue

            # description에서 HTML 태그 제거
            if description:
                description = BeautifulSoup(
                    description, "html.parser"
                ).get_text(separator=" ", strip=True)

            articles.append({
                "title": title,
                "url": link,
                "date": pub_date_str,
                "description": description,
                "source": source_name,
            })

    except Exception as e:
        print(f"  ⚠️  Google News 수집 실패 ({query[:35]}…): {e}")

    return articles


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2) 직접 사이트 스크래핑
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _scrape_generic(site_url: str, source_name: str,
                    link_selector: str, base_url: str) -> list[dict]:
    """범용 사이트 스크래퍼. CSS selector로 링크를 추출한다."""
    articles: list[dict] = []
    try:
        resp = requests.get(site_url, headers=HEADERS, timeout=15)
        if resp.status_code == 403:
            print(f"  ℹ️  {source_name}: 봇 차단(403) — Google News 사이트별 검색으로 대체됩니다.")
            return articles
        if resp.status_code >= 400:
            print(f"  ℹ️  {source_name}: HTTP {resp.status_code} — 스킵")
            return articles
        soup = BeautifulSoup(resp.text, "html.parser")

        seen_links: set[str] = set()
        for tag in soup.select(link_selector):
            title = tag.get_text(strip=True)
            href = tag.get("href", "")

            if not title or len(title) < 10:
                continue
            if href and not href.startswith("http"):
                href = base_url.rstrip("/") + "/" + href.lstrip("/")
            if href in seen_links:
                continue
            seen_links.add(href)

            articles.append({
                "title": title[:200],
                "url": href,
                "date": "",
                "description": "",
                "source": source_name,
            })
    except Exception as e:
        print(f"  ⚠️  {source_name} 스크래핑 실패: {e}")
    return articles


def scrape_incose() -> list[dict]:
    return _scrape_generic(
        "https://www.incose.org/incose-member-resources/newsroom",
        "INCOSE",
        "a[href*='newsroom'], a[href*='news'], .news-item a, h3 a, h2 a",
        "https://www.incose.org",
    )


def scrape_dau() -> list[dict]:
    return _scrape_generic(
        "https://www.dau.edu/blogs",
        "DAU",
        ".card a, .blog-item a, h3 a, h2 a, a[href*='blog'], a[href*='news']",
        "https://www.dau.edu",
    )


def scrape_mitre() -> list[dict]:
    return _scrape_generic(
        "https://www.mitre.org/news-insights",
        "MITRE",
        ".card a, .teaser a, h3 a, h2 a, a[href*='news-insights']",
        "https://www.mitre.org",
    )


def scrape_defense_gov() -> list[dict]:
    return _scrape_generic(
        "https://www.defense.gov/News/News-Stories/",
        "Defense.gov",
        ".listing-item a, .title a, h3 a, h2 a, a[href*='/News/']",
        "https://www.defense.gov",
    )


def scrape_saic() -> list[dict]:
    return _scrape_generic(
        "https://www.saic.com/news",
        "SAIC",
        ".news-card a, .card a, h3 a, h2 a, a[href*='news'], a[href*='press']",
        "https://www.saic.com",
    )


DIRECT_SCRAPERS = [
    ("INCOSE", scrape_incose),
    ("DAU", scrape_dau),
    ("MITRE", scrape_mitre),
    ("Defense.gov", scrape_defense_gov),
    ("SAIC", scrape_saic),
]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3) 유틸리티: 키워드 매칭, 중복 제거, 본문 추출
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def has_keyword_match(article: dict) -> bool:
    """기사 제목+설명에 MBSE 관련 키워드가 포함되는지 확인."""
    text = (
        article.get("title", "") + " " + article.get("description", "")
    ).lower()
    return any(kw.lower() in text for kw in KEYWORDS)


def deduplicate_articles(articles: list[dict]) -> list[dict]:
    """URL + 제목 이중 기반 중복 제거."""
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    unique: list[dict] = []
    for a in articles:
        url = a.get("url", "").strip()
        title_hash = _normalize_title(a.get("title", ""))

        # URL 또는 제목 해시가 이미 있으면 중복
        if (url and url in seen_urls) or (title_hash in seen_titles):
            continue
        if url:
            seen_urls.add(url)
        seen_titles.add(title_hash)
        unique.append(a)
    return unique


def fetch_article_text(url: str, max_chars: int = 3000) -> str:
    """기사 URL에서 본문 텍스트를 추출한다 (최대 max_chars)."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # 불필요한 태그 제거
        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()

        # 본문 영역 탐색
        main = (
            soup.find("article")
            or soup.find("main")
            or soup.find("div", class_=re.compile(r"content|article|post|body"))
        )
        text = (main or soup).get_text(separator="\n", strip=True)

        # 공백 정리
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        return "\n".join(lines)[:max_chars]

    except Exception:
        return ""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4) Gemini AI 요약
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GEMINI_PROMPT_TEMPLATE = """\
너는 최고 수준의 MBSE(Model-Based Systems Engineering) 산업 분석가 겸 아키텍트야.
다음 웹 문서들을 읽고, 단순한 회사 홍보, 스팸, 무의미한 행사 안내 등 \
전혀 가치 없는 글만 무시(Drop)하되, 아래의 [중요 규칙]을 반드시 지켜줘.

[🔥 중요: 방산업체 채용공고 포함 규칙]
미국 메이저 방산업체(Boeing, Lockheed Martin, RTX 등)나 국내 기관/기업(ADD, KAI, 한화, LIG 등)의 \
'채용 공고(Job Posting, Careers, Engineer 모집 등)'는 절대 무시하지 마!
방산업체의 MBSE 채용 공고는 해당 기업이 새로 진입하는 프로젝트, 신규 군수 통합 사업, \
도입 중인 툴체인(SysML, MagicDraw 등)을 유추할 수 있는 매우 중요한 '고급 산업 동향 정보'야.

오직 SysML, UAF, 국방/항공우주 적용 사례, 디지털 트윈 기술 뉴스와 \
방산업체의 'MBSE/시스템 엔지니어 채용 공고'를 모두 포함하여 엄선해줘.

선택된 기사(또는 채용 공고)만 아래 포맷으로 요약해 줘:

🚀 [제목 (한글 번역)]
📌 [분석] 핵심 3줄 요약 (기사 내용 또는 채용 직무/요구 기술 분석):
  1. (어떤 프로젝트/사업/분야를 위한 소식 또는 채용인지)
  2. (언급된 구체적인 요구 기술, MBSE 툴체인, 아키텍처 등)
  3. (기타 눈여겨볼 중요 포인트)
💡 산업 동향 인사이트: (이 소식/채용공고를 통해 엿볼 수 있는 방산 업계의 흐름이나 기술적 시사점 1줄)
🔗 원문: (URL)

---

중요한 규칙:
- 채용 공고는 단순 복붙이 아니라, "이 회사가 요즘 이쪽 분야를 강화하고 있다"는 뉘앙스로 분석해줘.
- 만약 모든 기사가 진짜 무가치한 스팸이라면, 정확히 다음 한 단어만 출력해: NONE
- 답변은 한글로 알기 쉽게 작성해 줘.
- 각 기사/채용 정보 사이에 --- 구분선을 넣어.

=== 분석 대상 기사 목록 ===
{articles_block}
"""


def _build_articles_block(articles: list[dict]) -> str:
    """프롬프트에 삽입할 기사 블록 문자열 생성."""
    parts: list[str] = []
    for i, a in enumerate(articles, 1):
        lines = [
            f"\n--- 기사 {i} ---",
            f"제목: {a['title']}",
            f"출처: {a.get('source') or 'N/A'}",
            f"URL: {a['url']}",
        ]
        if a.get("description"):
            lines.append(f"요약: {a['description']}")
        if a.get("full_text"):
            lines.append(f"본문:\n{a['full_text'][:2000]}")
        parts.append("\n".join(lines))
    return "\n".join(parts)


def summarize_with_gemini(articles: list[dict]) -> str | None:
    """Gemini 3 Flash로 기사를 필터링·요약한다. (최대 3회 재시도)"""
    client = genai.Client(api_key=API_KEY)
    prompt = GEMINI_PROMPT_TEMPLATE.format(
        articles_block=_build_articles_block(articles)
    )

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=prompt,
            )
            return response.text.strip()
        except Exception as e:
            err_str = str(e)
            is_rate_limit = any(
                kw in err_str for kw in ["429", "RESOURCE_EXHAUSTED", "UNAVAILABLE"]
            )
            if is_rate_limit and attempt < max_retries:
                wait = 10 * (2 ** (attempt - 1))  # 10s, 20s, 40s
                print(f"  ⏳ Rate Limit 감지. {wait}초 후 재시도... ({attempt}/{max_retries})")
                time.sleep(wait)
            else:
                print(f"  ❌ Gemini API 호출 실패: {e}")
                return None
    return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5) 메인 파이프라인
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"\n{'='*60}")
    print(f"🔍 MBSE 최신 동향 브리핑 에이전트 ({today})")
    print(f"{'='*60}")

    # ── 히스토리 로드 ──
    history = load_history()
    print(f"\n📂 기존 히스토리: {len(history)}건")

    # ── [1단계] Google News RSS 수집 ──
    print("\n📡 [1단계] Google News RSS 수집 중...")
    all_articles: list[dict] = []

    for query in SEARCH_QUERIES:
        found = fetch_google_news_rss(query)
        all_articles.extend(found)
        print(f"  ✓ '{query[:45]}' → {len(found)}건")
        time.sleep(0.5)  # 부하 방지

    # ── [2단계] 직접 사이트 스크래핑 ──
    print("\n🌐 [2단계] 주요 사이트 직접 스크래핑 중...")

    for name, scraper_fn in DIRECT_SCRAPERS:
        raw = scraper_fn()
        matched = [a for a in raw if has_keyword_match(a)]
        all_articles.extend(matched)
        print(f"  ✓ {name:<12} → {len(raw):>3}건 수집, {len(matched):>3}건 키워드 매칭")
        time.sleep(0.3)

    print(f"\n📊 총 수집: {len(all_articles)}건")

    # ── 중복 제거 ──
    unique = deduplicate_articles(all_articles)
    print(f"📊 중복 제거 후: {len(unique)}건")

    # ── 히스토리 대조 → 신규 기사만 (URL + 제목 이중 검사) ──
    new_articles = [
        a for a in unique
        if not is_in_history(history, a["url"], a["title"])
    ]
    print(f"📊 신규 기사: {len(new_articles)}건")

    # ── 신규 기사 없음 ──
    if not new_articles:
        msg = "오늘은 공유할 만한 고가치의 MBSE 기술 소식이 없습니다."
        print(f"\n📭 {msg}")
        OUTPUT_FILE.write_text(msg, encoding="utf-8")
        print(f"💾 '{OUTPUT_FILE.name}' 저장 완료")
        return

    # ── [3단계] 기사 본문 수집 (상위 20건) ──
    target = new_articles[:20]
    print(f"\n📖 [3단계] 기사 본문 수집 중 (최대 {len(target)}건)...")

    for i, a in enumerate(target, 1):
        if a.get("url"):
            a["full_text"] = fetch_article_text(a["url"])
            status = "OK" if a["full_text"] else "본문 없음"
            print(f"  ✓ ({i}/{len(target)}) [{status}] {a['title'][:50]}…")
            time.sleep(0.3)

    # ── [4단계] Gemini AI 분석 & 요약 ──
    print("\n🤖 [4단계] Gemini AI 분석 및 요약 중...")
    summary = summarize_with_gemini(target)

    # ── [5단계] 결과 포맷팅 & 저장 ──
    if summary is None:
        print("  ❌ AI 요약에 실패하거나 요약할 만한 가치 있는 기사가 없습니다.")
        final_text = "오늘은 요약할 기사가 없습니다."
    elif summary.strip().upper() == "NONE":
        final_text = "오늘은 요약할 기사가 없습니다."
    else:
        final_text = (
            f"📋 MBSE 데일리 브리핑 ({today})\n"
            f"{'━' * 30}\n\n"
            f"{summary}\n\n"
            f"{'━' * 30}\n"
            f"🤖 Gemini AI가 엄선한 기술 브리핑입니다."
        )

    # 터미널 출력
    print(f"\n{'=' * 60}")
    print(final_text)
    print(f"{'=' * 60}")

    # 파일 저장
    OUTPUT_FILE.write_text(final_text, encoding="utf-8")
    print(f"\n💾 '{OUTPUT_FILE.name}' 저장 완료!")

    # 카카오톡으로 전송
    try:
        from kakao_sender import send_to_kakao
        send_to_kakao(final_text)
    except ImportError:
        print("  ⚠️ kakao_sender.py 모듈을 찾을 수 없어 카카오톡 알림을 건너뜁니다.")

    # ── 히스토리 업데이트 (URL + 제목 해시 이중 저장) ──
    for a in new_articles:
        add_to_history(history, a["url"], a["title"])
    save_history(history)
    print(f"📝 히스토리 업데이트 완료 (총 {len(history)}건)")


if __name__ == "__main__":
    main()
