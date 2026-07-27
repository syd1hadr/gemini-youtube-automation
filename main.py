import os
import sys
from src.generator import generate_curriculum, generate_lesson_content

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
    
    # Test Gemini
    import google.generativeai as genai
    genai.configure(api_key=google_api_key)
    
    model = genai.GenerativeModel('gemini-2.0-flash')
    response = model.generate_content("Hello, are you working?")
    print("✅ Gemini says:", response.text)
    
    # Generate curriculum
    print("📚 Generating curriculum...")
    curriculum = generate_curriculum()
    print("✅ Curriculum generated!")
    
    # Generate lesson
    print("📝 Generating lesson...")
    lesson = generate_lesson_content("AI Basics")
    print("✅ Lesson generated!")

if __name__ == "__main__":
    main()
