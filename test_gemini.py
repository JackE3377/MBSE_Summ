import os
from dotenv import load_dotenv
from google import genai

# 1. .env 파일에서 API 키 로드
load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")

if not API_KEY or API_KEY == "여기에_발급받으신_키를_그대로_붙여넣으세요":
    print("❌ [오류] .env 파일에 GOOGLE_API_KEY를 설정해주세요.")
    print("   .env 파일을 열어 발급받은 API 키를 붙여넣으세요.")
    exit(1)

# 2. 새로운 google-genai 클라이언트 생성
client = genai.Client(api_key=API_KEY)

# 3. 구글 서버로 테스트 프롬프트 전송
print("구글 AI 서버와 통신을 시도합니다. (과금 없음)...\n")
try:
    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents="MBSE(모델 기반 시스템 엔지니어링)의 가장 큰 장점 1가지를 "
                 "시스템 엔지니어 관점에서 한 문장으로 말해줘.",
    )

    # 4. 결과 출력
    print("✅ [통신 성공! AI의 응답 결과]")
    print(response.text)
except Exception as e:
    print("❌ [오류 발생] API 키가 잘못되었거나 설정에 문제가 있습니다.")
    print(e)
