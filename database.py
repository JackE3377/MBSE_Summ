import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mbse_history.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # 기사 메타데이터 및 분석 결과 저장 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            title_kr TEXT,
            importance_level INTEGER,
            summary_1 TEXT,
            summary_2 TEXT,
            summary_3 TEXT,
            insight TEXT,
            original_url TEXT UNIQUE,
            source_type TEXT DEFAULT 'news',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # 기존 DB에 source_type 컬럼이 없으면 추가 (마이그레이션)
    try:
        cursor.execute("SELECT source_type FROM articles LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE articles ADD COLUMN source_type TEXT DEFAULT 'news'")
    conn.commit()
    conn.close()

def insert_article(date, title_kr, importance_level, summary_1, summary_2, summary_3, insight, original_url, source_type='news'):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO articles 
            (date, title_kr, importance_level, summary_1, summary_2, summary_3, insight, original_url, source_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(original_url) DO UPDATE SET
                date = excluded.date,
                title_kr = excluded.title_kr,
                importance_level = excluded.importance_level,
                summary_1 = excluded.summary_1,
                summary_2 = excluded.summary_2,
                summary_3 = excluded.summary_3,
                insight = excluded.insight,
                source_type = excluded.source_type
        ''', (date, title_kr, importance_level, summary_1, summary_2, summary_3, insight, original_url, source_type))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB Insert Error: {e}")

def get_past_articles(query="", limit=5, days=30):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # 단순 키워드 매칭 형태의 간이 RAG 검색 (나중에 ChromaDB로 교체 가능)
    if query:
        search_term = f"%{query}%"
        cursor.execute('''
            SELECT date, title_kr, insight, original_url FROM articles 
            WHERE (title_kr LIKE ? OR summary_1 LIKE ? OR insight LIKE ?)
            ORDER BY created_at DESC LIMIT ?
        ''', (search_term, search_term, search_term, limit))
    else:
        cursor.execute('''
            SELECT date, title_kr, insight, original_url FROM articles 
            ORDER BY created_at DESC LIMIT ?
        ''', (limit,))
    
    results = cursor.fetchall()
    conn.close()
    
    formatted = []
    for r in results:
        formatted.append({
            "date": r[0],
            "title_kr": r[1],
            "insight": r[2],
            "original_url": r[3]
        })
    return formatted

def build_rag_context(new_articles_text):
    """오늘 수집된 기사 텍스트를 바탕으로 핵심 명사(키워드)를 추출하여 과거 DB를 조회하는 함수"""
    # 임시 휴리스틱: 텍스트 내 주요 벤더나 키워드 추출
    keywords = ["Lockheed", "Boeing", "SysML", "UAF", "Digital Twin", "Northrop", "MBSE"]
    found_keywords = [k for k in keywords if k.lower() in new_articles_text.lower()]
    
    if not found_keywords:
        return ""
        
    context_str = "📚 [과거 연관 데이터베이스 (RAG Context)]\n"
    for k in found_keywords:
        past = get_past_articles(query=k, limit=2)
        if past:
            for p in past:
                context_str += f"- [{p['date']}] {p['title_kr']} (인사이트: {p['insight']})\n"
                
    return context_str

if __name__ == "__main__":
    init_db()
    print("Database initialized.")
