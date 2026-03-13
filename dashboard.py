import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime

st.set_page_config(page_title="MBSE HotBoard", page_icon="🔥", layout="wide", initial_sidebar_state="collapsed")

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mbse_history.db")

# ── Apple-style CSS (모바일 반응형) ──
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* Global */
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}
.stApp {
    background: linear-gradient(180deg, #0a0a0a 0%, #1a1a2e 100%);
}
header[data-testid="stHeader"] { background: transparent; }

/* Hide Streamlit chrome */
#MainMenu, footer, .stDeployButton,
header[data-testid="stHeader"] .stActionButton,
[data-testid="manage-app-button"],
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
.viewerBadge_container__r5tak,
.styles_viewerBadge__CvC9N,
[class*="viewerBadge"],
[class*="ViewerBadge"],
.viewerBadge_link__qRIco,
[class*="StatusWidget"],
a[href*="streamlit.io"],
a[href*="github.com/JackE3377"],
iframe[src*="github"],
.stApp > footer,
.reportview-container .main footer {
    display: none !important;
    visibility: hidden !important;
    height: 0 !important;
    overflow: hidden !important;
}

/* Hero */
.hero-title {
    font-size: clamp(1.8rem, 6vw, 2.8rem);
    font-weight: 700;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    text-align: center;
    margin-bottom: 0.2rem;
    letter-spacing: -0.02em;
}
.hero-subtitle {
    text-align: center;
    color: #8e8ea0;
    font-size: clamp(0.75rem, 2.5vw, 1rem);
    font-weight: 300;
    margin-bottom: 1.5rem;
}

/* Compact stats bar */
.stats-bar {
    display: flex;
    justify-content: center;
    gap: 1.5rem;
    flex-wrap: wrap;
    margin-bottom: 1rem;
    padding: 0.5rem 0;
}
.stats-bar .stat {
    font-size: 0.8rem;
    color: #8e8ea0;
    font-weight: 400;
}
.stats-bar .stat b {
    color: #e4e4e7;
    font-weight: 600;
    margin-right: 0.2rem;
}
.stats-bar .stat.mega b {
    color: #f87171;
}

/* Date radio pills — Streamlit st.radio 스타일 오버라이드 */
div[data-testid="stRadio"] > div {
    display: flex;
    gap: 0.5rem;
    overflow-x: auto;
    padding: 0.5rem 0 1rem 0;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
    flex-wrap: wrap;
}
div[data-testid="stRadio"] > div::-webkit-scrollbar { display: none; }
div[data-testid="stRadio"] label {
    padding: 0.45rem 1rem !important;
    border-radius: 999px !important;
    font-size: 0.8rem !important;
    font-weight: 500 !important;
    cursor: pointer;
    border: 1px solid rgba(255,255,255,0.1) !important;
    background: rgba(255,255,255,0.04) !important;
    color: #a1a1aa !important;
    transition: all 0.2s;
    white-space: nowrap;
}
div[data-testid="stRadio"] label:hover {
    background: rgba(102,126,234,0.15) !important;
    border-color: rgba(102,126,234,0.4) !important;
    color: #c4b5fd !important;
}
div[data-testid="stRadio"] label[data-checked="true"],
div[data-testid="stRadio"] label:has(input:checked) {
    background: linear-gradient(135deg, #667eea, #764ba2) !important;
    color: #fff !important;
    border-color: transparent !important;
    font-weight: 600 !important;
}

/* Article cards */
.article-card {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 16px;
    padding: clamp(1rem, 3vw, 1.5rem) clamp(1rem, 4vw, 1.8rem);
    margin-bottom: 0.8rem;
    transition: all 0.25s ease;
}
.article-card:hover {
    background: rgba(255,255,255,0.06);
    border-color: rgba(102,126,234,0.3);
    transform: translateY(-1px);
}
.article-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.4rem;
}
.article-date {
    font-size: clamp(0.65rem, 2vw, 0.75rem);
    color: #6b6b80;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.article-title {
    font-size: clamp(0.95rem, 3vw, 1.15rem);
    font-weight: 600;
    color: #e4e4e7;
    margin: 0.4rem 0 0.6rem 0;
    line-height: 1.4;
}
.article-summary {
    font-size: clamp(0.8rem, 2.5vw, 0.9rem);
    color: #a1a1aa;
    line-height: 1.7;
    margin-bottom: 0.8rem;
}
.article-insight {
    font-size: clamp(0.78rem, 2.5vw, 0.88rem);
    color: #c4b5fd;
    font-style: italic;
    border-left: 3px solid #7c3aed;
    padding-left: 0.8rem;
    margin: 0.8rem 0;
}
.article-link {
    display: inline-block;
    font-size: clamp(0.7rem, 2vw, 0.8rem);
    color: #667eea;
    text-decoration: none;
    font-weight: 500;
}
.article-link:hover { color: #818cf8; text-decoration: underline; }

/* Level badges */
.badge {
    display: inline-block;
    padding: 0.2rem 0.7rem;
    border-radius: 999px;
    font-size: clamp(0.6rem, 1.8vw, 0.7rem);
    font-weight: 600;
    letter-spacing: 0.03em;
}
.badge-3 { background: rgba(239,68,68,0.15); color: #f87171; border: 1px solid rgba(239,68,68,0.3); }
.badge-2 { background: rgba(251,191,36,0.12); color: #fbbf24; border: 1px solid rgba(251,191,36,0.3); }
.badge-1 { background: rgba(96,165,250,0.12); color: #60a5fa; border: 1px solid rgba(96,165,250,0.3); }

/* Streamlit inputs */
.stTextInput > div > div > input {
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 12px !important;
    color: #e4e4e7 !important;
    font-family: 'Inter', sans-serif !important;
}
.stSelectbox > div > div {
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 12px !important;
}

/* Divider */
.section-divider {
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.08), transparent);
    margin: 1.5rem 0;
}

/* Footer hide */
.stApp > footer { display: none !important; }
</style>
""", unsafe_allow_html=True)

import re as _re

def _linkify(text: str) -> str:
    """insight 텍스트 내 raw URL을 클릭 가능한 하이퍼링크로 변환"""
    return _re.sub(
        r'(https?://[^\s\)\]>\'",]+)',
        r'<a class="article-link" href="\1" target="_blank" style="font-style:normal">🔗 링크</a>',
        text
    )

def load_metadata():
    """날짜 메타정보만 조회 — 전체 기사 로드 없이 첫 화면 빠른 렌더링"""
    if not os.path.exists(DB_PATH):
        return None
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM articles")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM articles WHERE importance_level = 3")
    mega = cursor.fetchone()[0]
    cursor.execute("SELECT MAX(date) FROM articles")
    latest = cursor.fetchone()[0] or '-'
    cursor.execute("SELECT date, COUNT(*) FROM articles GROUP BY date ORDER BY date DESC")
    date_counts = dict(cursor.fetchall())
    conn.close()
    return {"total": total, "mega": mega, "latest": latest, "date_counts": date_counts}

def load_articles(selected_date):
    """선택된 날짜 기사만 SQL 레벨에서 필터링해 로드"""
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()
    conn = sqlite3.connect(DB_PATH)
    if selected_date == "전체":
        df = pd.read_sql_query(
            "SELECT * FROM articles ORDER BY importance_level DESC, date DESC",
            conn
        )
    else:
        df = pd.read_sql_query(
            "SELECT * FROM articles WHERE date = ? ORDER BY importance_level DESC, created_at DESC",
            conn, params=(selected_date,)
        )
    conn.close()
    # Google News 리디렉트 URL → 실제 원문 URL (조회된 기사만 디코딩)
    if not df.empty and 'original_url' in df.columns:
        mask = df['original_url'].str.contains('news.google.com', na=False)
        if mask.any():
            try:
                from googlenewsdecoder import new_decoderv1
                for idx in df[mask].index:
                    try:
                        result = new_decoderv1(df.at[idx, 'original_url'])
                        if result.get('status') and result.get('decoded_url'):
                            df.at[idx, 'original_url'] = result['decoded_url']
                    except Exception:
                        pass
            except ImportError:
                pass
    return df

# ── Hero ──
st.markdown('<div class="hero-title">🔥 MBSE HotBoard</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-subtitle">AI가 매일 수집 · 분석하는 글로벌 방산/항공우주 MBSE 트렌드</div>', unsafe_allow_html=True)

# 메타정보 먼저 조회 (전체 기사 없이 날짜/통계만)
meta = load_metadata()

if meta is None or meta["total"] == 0:
    st.warning("아직 수집된 데이터가 없습니다. AI 에이전트를 먼저 실행해주세요.")
    st.stop()

total = meta["total"]
mega = meta["mega"]
latest = meta["latest"]
date_counts = meta["date_counts"]
available_dates = sorted(date_counts.keys(), reverse=True)

# ── Compact stats bar ──
st.markdown(f"""
<div class="stats-bar">
    <span class="stat"><b>{total}</b>누적</span>
    <span class="stat mega"><b>{mega}</b>🔥 메가트렌드</span>
    <span class="stat"><b>{latest}</b>최근 수집</span>
</div>
""", unsafe_allow_html=True)

# ── Date pills (Streamlit 네이티브 radio — iframe 안전) ──
today_str = datetime.now().strftime("%Y-%m-%d")
default_date = today_str if today_str in available_dates else available_dates[0]

date_options = ["전체"] + list(available_dates)
date_labels = {"전체": f"전체 ({total})"}
for d in available_dates:
    short = d[5:].replace("-", ".")
    date_labels[d] = f"{short} ({date_counts.get(d, 0)})"

default_idx = date_options.index(default_date) if default_date in date_options else 0

selected_date = st.radio(
    "날짜",
    options=date_options,
    format_func=lambda x: date_labels.get(x, x),
    horizontal=True,
    index=default_idx,
    label_visibility="collapsed"
)

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

# ── Filters ──
col_search, col_level = st.columns([3, 1])
with col_search:
    search_query = st.text_input("🔍 검색", placeholder="Boeing, SysML, Digital Twin ...", label_visibility="collapsed")
with col_level:
    level_filter = st.selectbox("중요도", ["전체", "🔥🔥🔥 메가트렌드", "🔥🔥 실무", "🔥 일반"], label_visibility="collapsed")

# ── 선택 날짜 기사만 로드 (SQL 필터 — 전체 테이블 로드 없음) ──
df = load_articles(selected_date)

# ── Apply filters ──
filtered_df = df.copy()

# 검색 필터 (날짜는 SQL에서 이미 처리)
if search_query:
    filtered_df = filtered_df[
        filtered_df['title_kr'].str.contains(search_query, case=False, na=False) |
        filtered_df['insight'].str.contains(search_query, case=False, na=False) |
        filtered_df['summary_1'].str.contains(search_query, case=False, na=False)
    ]

# 중요도 필터
level_map = {"🔥🔥🔥 메가트렌드": 3, "🔥🔥 실무": 2, "🔥 일반": 1}
if level_filter in level_map:
    filtered_df = filtered_df[filtered_df['importance_level'] == level_map[level_filter]]

# 중요도 기준 정렬 (MEGA TREND 먼저)
filtered_df = filtered_df.sort_values(by=['importance_level', 'date'], ascending=[False, False])

st.markdown(f'<p style="color:#6b6b80;font-size:0.85rem;margin-bottom:1rem">{len(filtered_df)}건의 기사</p>', unsafe_allow_html=True)

# ── Article Cards ──
for _, row in filtered_df.iterrows():
    lvl = int(row['importance_level'])
    badge_class = f"badge-{lvl}"
    badge_labels = {3: "MEGA TREND", 2: "PRACTICAL", 1: "GENERAL"}
    badge_text = badge_labels.get(lvl, "")

    card_html = f"""
    <div class="article-card">
        <div class="article-header">
            <span class="article-date">{row['date']}</span>
            <span class="badge {badge_class}">{badge_text}</span>
        </div>
        <div class="article-title">{row['title_kr']}</div>
        <div class="article-summary">
            <strong>1.</strong> {row['summary_1']}<br/>
            <strong>2.</strong> {row['summary_2']}<br/>
            <strong>3.</strong> {row['summary_3']}
        </div>
        <div class="article-insight">💡 {_linkify(str(row['insight']))}</div>
        <a class="article-link" href="{row['original_url']}" target="_blank">원문 보기 →</a>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)

# ── 빈 공간으로 마무리 (footer 대체) ──
st.markdown('<div style="height:3rem"></div>', unsafe_allow_html=True)
