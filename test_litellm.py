import os
from dotenv import load_dotenv
from crewai import LLM, Agent, Task, Crew

load_dotenv()
API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

try:
    print("Testing gemini/gemini-1.5-flash...")
    llm1 = LLM(model="gemini/gemini-1.5-flash", api_key=API_KEY)
    res = llm1.call(messages=[{"role": "user", "content": "hi"}])
    print("Success:", res)
except Exception as e:
    print("Error 1.5:", e)

try:
    print("Testing gemini/gemini-2.5-flash...")
    llm2 = LLM(model="gemini/gemini-2.5-flash", api_key=API_KEY)
    res = llm2.call(messages=[{"role": "user", "content": "hi"}])
    print("Success:", res)
except Exception as e:
    print("Error 2.5:", e)

try:
    print("Testing gemini/gemini-3.0-flash...")
    llm3 = LLM(model="gemini/gemini-3.0-flash", api_key=API_KEY)
    res = llm3.call(messages=[{"role": "user", "content": "hi"}])
    print("Success:", res)
except Exception as e:
    print("Error 3.0:", e)
