import streamlit as st
import sqlite3
import pandas as pd
import os

st.set_page_config(page_title="MBSE HotBoard", page_icon="🔥", layout="wide")

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mbse_history.db")

# ── Apple-style CSS ──
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
header[data-testid="stHeader"] {
    background: transparent;
}

/* Hide default decorations */
#MainMenu, footer, .stDeployButton {display: none;}

/* Hero title */
.hero-title {
    font-size: 2.8rem;
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
    font-size: 1rem;
    font-weight: 300;
    margin-bottom: 2rem;
}

/* Metric cards */
.metric-card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px;
    padding: 1.5rem;
    text-align: center;
    backdrop-filter: blur(20px);
    transition: transform 0.2s, border-color 0.2s;
}
.metric-card:hover {
    transform: translateY(-2px);
    border-color: rgba(102,126,234,0.4);
}
.metric-value {
    font-size: 2.2rem;
    font-weight: 700;
    color: #ffffff;
    line-height: 1.2;
}
.metric-label {
    font-size: 0.85rem;
    color: #8e8ea0;
    margin-top: 0.3rem;
    font-weight: 400;
}

/* Article cards */
.article-card {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 16px;
    padding: 1.5rem 1.8rem;
    margin-bottom: 1rem;
    transition: all 0.25s ease;
}
.article-card:hover {
    background: rgba(255,255,255,0.06);
    border-color: rgba(102,126,234,0.3);
    transform: translateY(-1px);
}
.article-date {
    font-size: 0.75rem;
    color: #6b6b80;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.article-title {
    font-size: 1.15rem;
    font-weight: 600;
    color: #e4e4e7;
    margin: 0.4rem 0 0.6rem 0;
    line-height: 1.4;
}
.article-summary {
    font-size: 0.9rem;
    color: #a1a1aa;
    line-height: 1.7;
    margin-bottom: 0.8rem;
}
.article-insight {
    font-size: 0.88rem;
    color: #c4b5fd;
    font-style: italic;
    border-left: 3px solid #7c3aed;
    padding-left: 0.8rem;
    margin: 0.8rem 0;
}
.article-link {
    display: inline-block;
    font-size: 0.8rem;
    color: #667eea;
    text-decoration: none;
    font-weight: 500;
}
.article-link:hover {
    color: #818cf8;
    text-decoration: underline;
}

/* Level badges */
.badge {
    display: inline-block;
    padding: 0.2rem 0.7rem;
    border-radius: 999px;
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.03em;
}
.badge-3 {
    background: rgba(239,68,68,0.15);
    color: #f87171;
    border: 1px solid rgba(239,68,68,0.3);
}
.badge-2 {
    background: rgba(251,191,36,0.12);
    color: #fbbf24;
    border: 1px solid rgba(251,191,36,0.3);
}
.badge-1 {
    background: rgba(96,165,250,0.12);
    color: #60a5fa;
    border: 1px solid rgba(96,165,250,0.3);
}

/* Search */
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

/* Section divider */
.section-divider {
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.08), transparent);
    margin: 2rem 0;
}
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
st.markdown('<div class="hero-title">MBSE HotBoard</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-subtitle">AI가 매일 수집 · 분석하는 글로벌 방산/항공우주 MBSE 트렌드</div>', unsafe_allow_html=True)

df = load_data()

if df.empty:
    st.warning("아직 수집된 데이터가 없습니다. AI 에이전트를 먼저 실행해주세요.")
    st.stop()

# ── Metrics ──
total = len(df)
mega = len(df[df['importance_level'] == 3])
latest = df['date'].iloc[0] if 'date' in df.columns else '-'

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(f'<div class="metric-card"><div class="metric-value">{total}</div><div class="metric-label">누적 기사</div></div>', unsafe_allow_html=True)
with col2:
    st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#f87171">{mega}</div><div class="metric-label">🔥 메가트렌드</div></div>', unsafe_allow_html=True)
with col3:
    st.markdown(f'<div class="metric-card"><div class="metric-value" style="font-size:1.4rem">{latest}</div><div class="metric-label">최근 수집일</div></div>', unsafe_allow_html=True)

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

# ── Filters ──
col_search, col_level = st.columns([3, 1])
with col_search:
    search_query = st.text_input("🔍 검색", placeholder="Boeing, SysML, Digital Twin ...", label_visibility="collapsed")
with col_level:
    level_filter = st.selectbox("중요도", ["전체", "🔥🔥🔥 메가트렌드", "🔥🔥 실무", "🔥 일반"], label_visibility="collapsed")

filtered_df = df.copy()
if search_query:
    filtered_df = filtered_df[
        filtered_df['title_kr'].str.contains(search_query, case=False, na=False) |
        filtered_df['insight'].str.contains(search_query, case=False, na=False) |
        filtered_df['summary_1'].str.contains(search_query, case=False, na=False)
    ]

level_map = {"🔥🔥🔥 메가트렌드": 3, "🔥🔥 실무": 2, "🔥 일반": 1}
if level_filter in level_map:
    filtered_df = filtered_df[filtered_df['importance_level'] == level_map[level_filter]]

st.markdown(f'<p style="color:#6b6b80;font-size:0.85rem;margin-bottom:1rem">{len(filtered_df)}건의 기사</p>', unsafe_allow_html=True)

# ── Article Cards ──
for _, row in filtered_df.iterrows():
    lvl = int(row['importance_level'])
    badge_class = f"badge-{lvl}"
    badge_labels = {3: "MEGA TREND", 2: "PRACTICAL", 1: "GENERAL"}
    badge_text = badge_labels.get(lvl, "")

    card_html = f"""
    <div class="article-card">
        <div style="display:flex;justify-content:space-between;align-items:center">
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
        <a class="article-link" href="{row['original_url']}" target="_blank">원문 보기 →</a>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)
