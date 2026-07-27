import os
import sys
import time
from google import genai

sys.stdout.reconfigure(encoding='utf-8')

def main():
    api_key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if not api_key:
        print("❌ GOOGLE_API_KEY is missing!")
        exit(1)
    
    print("✅ Google API Key loaded successfully!")
    
    client = genai.Client(api_key=api_key)
    
    # Retry logic for 429 errors
    for attempt in range(5):
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents="Hello, are you working?"
            )
            print("✅ Gemini says:", response.text[:50] + "...")
            print("🎯 All tests passed! Project is ready.")
            return
        except Exception as e:
            error_str = str(e)
            if "429" in error_str:
                wait = (attempt + 1) * 3
                print(f"⚠️ Quota exceeded. Retrying in {wait}s...")
                time.sleep(wait)
            else:
                print(f"❌ Error: {e}")
                exit(1)
    
    print("❌ Max retries exceeded.")
    exit(1)

if __name__ == "__main__":
    main()
