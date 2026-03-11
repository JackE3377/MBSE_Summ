import os
import time
from datetime import datetime
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, LLM

# 기존 main.py 스크래핑 모듈 재사용
from main import (
    load_history, save_history, fetch_google_news_rss, DIRECT_SCRAPERS,
    has_keyword_match, deduplicate_articles, is_in_history, add_to_history,
    fetch_article_text, _build_articles_block, SEARCH_QUERIES
)

def format_articles(articles):
    return _build_articles_block(articles)

def run_hybrid_orchestrator():
    load_dotenv()
    API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    today = datetime.now().strftime("%Y-%m-%d")
    
    print("\n" + "="*70)
    print(f"🚀 [하이브리드 아키텍처] API 최적화 오케스트레이터 ({today})")
    print("="*70)

    # 히스토리 로드
    history = load_history()
    print(f"\n📂 기존 히스토리: {len(history)}건")

    # [1단계] Python 스크립트를 통한 데이터 사전 수집
    print("\n📡 [1단계] Python 기반 웹 크롤러 사전 수집 중 (API 호출: 0회) ...")
    all_articles = []
    
    for query in SEARCH_QUERIES:
        found = fetch_google_news_rss(query)
        all_articles.extend(found)
        print(f"  ✓ RSS '{query[:45]}' → {len(found)}건")
        time.sleep(0.5)
        
    for name, scraper_fn in DIRECT_SCRAPERS:
        raw = scraper_fn()
        matched = [a for a in raw if has_keyword_match(a)]
        all_articles.extend(matched)
        print(f"  ✓ {name:<12} → {len(raw):>3}건 수집, {len(matched):>3}건 키워드 매칭")
        time.sleep(0.3)

    unique = deduplicate_articles(all_articles)
    
    # 신규 기사 필터링
    new_articles = [a for a in unique if not is_in_history(history, a["url"], a["title"])]
    print(f"\n📊 총 수집: {len(all_articles)}건 -> 중복/과거 제외 신규: {len(new_articles)}건")
    
    if not new_articles:
        final_output = "오늘은 공유할 만한 고가치의 신규 MBSE 기술 소식이 없습니다."
        print(f"\n📭 {final_output}")
        _finish_and_send(final_output)
        return

    # -----------------------------------------------------
    # 기사 본문 수집 (최대 20건)
    # -----------------------------------------------------
    target = new_articles[:20]
    print(f"\n📖 신규 정보 본문 수집 중 (최대 {len(target)}건)...")
    for i, a in enumerate(target, 1):
        if a.get("url"):
            a["full_text"] = fetch_article_text(a["url"], max_chars=1200) # 토큰 최적화를 위해 max 1200자 제한
            status = "OK" if a["full_text"] else "본문 없음"
            print(f"  ✓ ({i}/{len(target)}) [{status}] {a['title'][:50]}…")
            time.sleep(0.3)

    articles_str = format_articles(target)

    # -----------------------------------------------------
    # [2단계] Chief Evaluator 투입
    # -----------------------------------------------------
    print("\n🤖 [2단계] 수석 분석가(Chief Evaluator) 단독 투입 (필터링 및 요약)...")
    llm = LLM(model="gemini/gemini-3-flash-preview", api_key=API_KEY, temperature=0.3)
    
    chief_evaluator = Agent(
        role="Chief Evaluator",
        goal="자료의 중요도를 1단계(일반), 2단계(실무 인사이트), 3단계(게임 체인저/대규모 기술/채용 변화)로 엄격하게 평가한다.",
        backstory="최고 책임형 수석 아키텍트 시스템 엔지니어. 시간낭비를 싫어하며 가치 없는 문서는 철저히 폐기하고 3단계 문서를 포착한다.",
        llm=llm,
        allow_delegation=False
    )
    
    task_eval = Task(
        description=(
            f"다음 웹 문서들을 읽고, 무관하거나 가치 없는 기사는 즉각 폐기하라.\n"
            f"주목할 만한 기술적 가치가 있거나 주요 메이저 기업(KAI/록히드/보잉 등)의 채용/프로젝트 기사들은 엄선해서 1~3단계로 분류하고 단문 요약하라.\n"
            f"포맷: 🚀 [제목] [중요도: X단계]\n"
            f"📌 내용 요약: [1~2줄 핵심 요약]\n"
            f"🔗 원문: [URL]\n\n"
            f"🎯 [수석 엔지니어 필수 행동]: 평가 내용 중 '3단계' (가장 최고 중요도) 항목이 단 하나라도 포함되어 있다면, 전체 답변의 맨 마지막 줄에 정확히 '[LEVEL_3_FOUND]' 라는 문자열을 반드시 적어라.\n\n"
            f"=== 기사 목록 ===\n{articles_str}"
        ),
        expected_output="[필요시 폐기 처리] 중요도 평가 요약 리포트, 각 기사의 URL 포함, 3단계 문서 여부 확인 플래그",
        agent=chief_evaluator
    )
    
    crew_eval = Crew(agents=[chief_evaluator], tasks=[task_eval], verbose=False)
    eval_result = crew_eval.kickoff()
    final_text = str(eval_result.raw).strip()

    # -----------------------------------------------------
    # [3단계] 조건부 요원 투입
    # -----------------------------------------------------
    sub_results_text = ""
    if "[LEVEL_3_FOUND]" in final_text or "3단계" in final_text:
        print("\n🚨 [LEVEL_3_FOUND] 3단계 집중 분석 대상 포착!")
        print("  ▶ 수석 분석가의 지시로 Agent 1(Source Scout) 및 Agent 2(Trend Analyzer)가 긴급 투입됩니다.")
        
        final_text = final_text.replace("[LEVEL_3_FOUND]", "").strip() # 결과 텍스트에서 토글 제거
        
        source_scout = Agent(
            role="Source Scout",
            goal="의뢰된 3단계 문서를 지원할 추가 공신력 있는 웹 출처(국방부, 대형 방산기업, 학회 블로그 등)를 명확히 제시한다.",
            backstory="신뢰성 기반 깐깐한 정보 소싱 검색 전문가",
            llm=llm
        )
        
        trend_analyzer = Agent(
            role="Trend Analyzer",
            goal="의뢰된 3단계 문서를 바탕으로 추후 정보 자동 수집 망에 등록할 신규 기술 키워드를 정확히 도출한다.",
            backstory="데이터에서 산업 변화를 읽어내는 트렌드 예측가",
            llm=llm
        )
        
        task_scout = Task(
            description=f"수석의 다음 3단계 요약 리포트를 바탕으로, 이 현안을 더 깊게 교차 검증하기 위해 탐색해야 할 공신력 있는(방산/항공우주 관련) 출처나 웹사이트 2곳의 이름과 이유를 제안하라.\n{final_text}",
            expected_output="확장 탐색을 권장하는 공신력 추천 출처 2개",
            agent=source_scout
        )
        
        task_trend = Task(
            description=f"다음 3단계 요약 리포트를 면밀히 분석하여, 향후 시스템의 '매일 검색 키워드'에 추가할 만한 신규 파생 MBSE/우주항공 기술 키워드 2개를 명확히 추출하라.\n{final_text}",
            expected_output="검색엔진에 등재할 신규 파생 트렌드 키워드 2개",
            agent=trend_analyzer
        )
        
        crew_sub = Crew(agents=[source_scout, trend_analyzer], tasks=[task_scout, task_trend], verbose=False)
        sub_results = crew_sub.kickoff()
        sub_results_text = str(sub_results.raw).strip()
    
    # -----------------------------------------------------
    # 카카오톡 메시지 포매팅
    # -----------------------------------------------------
    final_output = f"📋 [하이브리드 AI] MBSE 데일리 브리핑 ({today})\n"
    final_output += "=" * 30 + "\n\n"
    final_output += final_text + "\n\n"
    
    if sub_results_text:
         final_output += "🚀 [별첨: 추가 분석 요원 확장 리포트]\n"
         final_output += sub_results_text + "\n\n"
         
    final_output += "=" * 30 + "\n"
    final_output += "🤖 Gemini 2.5 Flash 기반 다중 에이전트 브리핑 (API 최적화 버전)"

    # 구동 이력(History) 갱신
    for a in new_articles:
        add_to_history(history, a["url"], a["title"])
    save_history(history)
    print(f"\n📝 히스토리 업데이트 완료 (총 {len(history)}건)")

    # 카카오톡 & 로컬 저장소 전송
    _finish_and_send(final_output)

def _finish_and_send(final_output: str):
    OUTPUT_FILE = "kakao_daily_mbse_briefing.txt"
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(final_output)
    print(f"💾 '{OUTPUT_FILE}' 파일에 저장되었습니다.")
    
    try:
        from kakao_sender import send_to_kakao
        send_to_kakao(final_output)
        print("📲 카카오톡 전송 성공!")
    except ImportError:
        print("  ⚠️ kakao_sender.py 모듈을 찾을 수 없습니다.")
    except Exception as e:
        print(f"  ⚠️ 카카오톡 전송 중 오류 발생: {e}")

if __name__ == "__main__":
    run_hybrid_orchestrator()
