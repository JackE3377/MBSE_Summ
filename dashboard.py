import streamlit as st
import sqlite3
import pandas as pd
import os

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
.viewerBadge_container__r5tak,
.styles_viewerBadge__CvC9N {
    display: none !important;
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

/* Date pills */
.date-scroll {
    display: flex;
    gap: 0.5rem;
    overflow-x: auto;
    padding: 0.5rem 0 1rem 0;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
}
.date-scroll::-webkit-scrollbar { display: none; }
.date-pill {
    flex-shrink: 0;
    padding: 0.45rem 1rem;
    border-radius: 999px;
    font-size: 0.8rem;
    font-weight: 500;
    cursor: pointer;
    border: 1px solid rgba(255,255,255,0.1);
    background: rgba(255,255,255,0.04);
    color: #a1a1aa;
    text-decoration: none;
    transition: all 0.2s;
    white-space: nowrap;
}
.date-pill:hover {
    background: rgba(102,126,234,0.15);
    border-color: rgba(102,126,234,0.4);
    color: #c4b5fd;
}
.date-pill.active {
    background: linear-gradient(135deg, #667eea, #764ba2);
    color: #fff;
    border-color: transparent;
    font-weight: 600;
}
.date-pill .pill-count {
    display: inline-block;
    background: rgba(0,0,0,0.25);
    padding: 0.1rem 0.4rem;
    border-radius: 999px;
    font-size: 0.65rem;
    margin-left: 0.3rem;
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

def load_data():
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()
    conn = sqlite3.connect(DB_PATH)
    query = "SELECT * FROM articles ORDER BY created_at DESC"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

# ── Hero ──
st.markdown('<div class="hero-title">🔥 MBSE HotBoard</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-subtitle">AI가 매일 수집 · 분석하는 글로벌 방산/항공우주 MBSE 트렌드</div>', unsafe_allow_html=True)

df = load_data()

if df.empty:
    st.warning("아직 수집된 데이터가 없습니다. AI 에이전트를 먼저 실행해주세요.")
    st.stop()

# ── Compact stats bar ──
total = len(df)
mega = len(df[df['importance_level'] == 3])
latest = df['date'].iloc[0] if 'date' in df.columns else '-'

st.markdown(f"""
<div class="stats-bar">
    <span class="stat"><b>{total}</b>누적</span>
    <span class="stat mega"><b>{mega}</b>🔥 메가트렌드</span>
    <span class="stat"><b>{latest}</b>최근 수집</span>
</div>
""", unsafe_allow_html=True)

# ── Date pills (데이터 있는 날짜만 표시) ──
available_dates = sorted(df['date'].unique(), reverse=True)

# Streamlit의 query_params로 날짜 선택 상태 관리
params = st.query_params
selected_date = params.get("date", "전체")

date_pills_html = ""
all_active = "active" if selected_date == "전체" else ""
date_pills_html += f'<a class="date-pill {all_active}" href="?date=전체">전체 <span class="pill-count">{total}</span></a>'

for d in available_dates:
    count = len(df[df['date'] == d])
    active = "active" if selected_date == d else ""
    # 날짜 표시 간소화 (MM.DD)
    try:
        short = d[5:].replace("-", ".")
    except:
        short = d
    date_pills_html += f'<a class="date-pill {active}" href="?date={d}">{short} <span class="pill-count">{count}</span></a>'

st.markdown(f'<div class="date-scroll">{date_pills_html}</div>', unsafe_allow_html=True)

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

# ── Filters ──
col_search, col_level = st.columns([3, 1])
with col_search:
    search_query = st.text_input("🔍 검색", placeholder="Boeing, SysML, Digital Twin ...", label_visibility="collapsed")
with col_level:
    level_filter = st.selectbox("중요도", ["전체", "🔥🔥🔥 메가트렌드", "🔥🔥 실무", "🔥 일반"], label_visibility="collapsed")

# ── Apply filters ──
filtered_df = df.copy()

# 날짜 필터
if selected_date != "전체" and selected_date in available_dates:
    filtered_df = filtered_df[filtered_df['date'] == selected_date]

# 검색 필터
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

    # Google 검색 링크 생성 (원문 URL이 Google News 리디렉트이므로)
    from urllib.parse import quote_plus
    search_q = quote_plus(row['title_kr'].replace('[', '').replace(']', ''))

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
        <div class="article-insight">💡 {row['insight']}</div>
        <a class="article-link" href="https://www.google.com/search?q={search_q}" target="_blank">원문 검색 →</a>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)

# ── 빈 공간으로 마무리 (footer 대체) ──
st.markdown('<div style="height:3rem"></div>', unsafe_allow_html=True)
