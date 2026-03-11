import os
from dotenv import load_dotenv
from crewai import LLM

load_dotenv()
API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

try:
    print("Testing gemini/gemini-3-flash-preview...")
    # LLM via crewai
    llm = LLM(model="gemini/gemini-3-flash-preview", api_key=API_KEY)
    response = llm.call(messages=[{"role": "user", "content": "What is MBSE? Reply in 1 sentence."}])
    print("SUCCESS!")
    print(response)
except Exception as e:
    print(f"FAILED: {e}")
