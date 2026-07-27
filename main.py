import os
import sys
import google.generativeai as genai

# Force UTF-8
sys.stdout.reconfigure(encoding='utf-8')

def main():
    # Sanitize API key
    google_api_key = os.environ.get("GOOGLE_API_KEY", "")
    google_api_key = (
        google_api_key
        .replace("\u2028", "")
        .replace("\u2029", "")
        .replace("\r", "")
        .replace("\n", "")
        .strip()
    )
    
    if not google_api_key:
        print("❌ GOOGLE_API_KEY is missing or empty!")
        exit(1)
    
    print("✅ Google API Key loaded successfully!")
    
    # Configure Gemini
    genai.configure(api_key=google_api_key)
    
    # Test Gemini
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content("Hello, are you working?")
        print("✅ Gemini says:", response.text[:50], "...")
    except Exception as e:
        print("❌ Gemini test failed:", e)
        exit(1)
    
    print("🎯 All tests passed! Project is ready.")
    print("📝 Now you can add video generation code here.")

if __name__ == "__main__":
    main()
