import os
import time
from google import genai

def generate_curriculum():
    api_key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GOOGLE_API_KEY is missing!")
    
    client = genai.Client(api_key=api_key)
    
    prompt = """Generate a simple curriculum for an AI course.
    Include 5 lessons with titles and brief descriptions.
    Return as JSON array with 'title' and 'description' keys.
    Keep it simple and educational."""
    
    for attempt in range(5):
        try:
            response = client.models.generate_content(
                model='gemini-1.5-flash',
                contents=prompt
            )
            return response.text
        except Exception as e:
            if "429" in str(e):
                wait = (attempt + 1) * 2
                print(f"⚠️ Quota exceeded. Retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise e
    raise Exception("Max retries exceeded.")

def generate_lesson_content(title):
    api_key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GOOGLE_API_KEY is missing!")
    
    client = genai.Client(api_key=api_key)
    
    prompt = f"""Write a detailed lesson about: {title}
    
    Format:
    - Introduction (2-3 sentences)
    - Main Content (5-6 sentences)
    - Conclusion (2-3 sentences)
    - 3 Key Takeaways
    
    Keep it simple and educational."""
    
    prompt = prompt.replace("\u2028", " ")
    prompt = prompt.replace("\u2029", " ")
    
    for attempt in range(5):
        try:
            response = client.models.generate_content(
                model='gemini-1.5-flash',
                contents=prompt
            )
            return response.text
        except Exception as e:
            if "429" in str(e):
                wait = (attempt + 1) * 2
                print(f"⚠️ Quota exceeded. Retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise e
    raise Exception("Max retries exceeded.")
