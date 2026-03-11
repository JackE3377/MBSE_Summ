import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

client = genai.Client(api_key=API_KEY)
# In version google-genai, the method is client.models.list()
try:
    models = client.models.list()
    print("Available models containing 'gemini':")
    for m in models:
        try:
            name = getattr(m, 'name', '')
            if 'gemini' in name:
                print(f" - {name}")
        except:
            print(f" - {m}")
except Exception as e:
    print(f"Listing models failed: {e}")
