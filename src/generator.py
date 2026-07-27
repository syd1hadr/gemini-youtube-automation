import os
import json
import google.generativeai as genai

def generate_curriculum():
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
        raise ValueError("GOOGLE_API_KEY is missing or empty")
    
    # Configure Gemini
    genai.configure(api_key=google_api_key)
    
    prompt = """Generate a simple curriculum for an AI course. 
    Include 5 lessons with titles and brief descriptions.
    Format: Return a JSON array with each lesson having 'title' and 'description' keys.
    Keep it simple and educational."""
    
    model = genai.GenerativeModel('gemini-2.0-flash')
    response = model.generate_content(prompt)
    
    return response.text

def generate_lesson_content(title):
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
        raise ValueError("GOOGLE_API_KEY is missing or empty")
    
    # Configure Gemini
    genai.configure(api_key=google_api_key)
    
    prompt = f"""Write a detailed lesson about: {title}
    
    Format:
    - Introduction (2-3 sentences)
    - Main Content (5-6 sentences)
    - Conclusion (2-3 sentences)
    - 3 Key Takeaways
    
    Keep it simple and educational."""
    
    # Remove hidden Unicode characters
    prompt = prompt.replace("\u2028", " ")
    prompt = prompt.replace("\u2029", " ")
    
    model = genai.GenerativeModel('gemini-2.0-flash')
    response = model.generate_content(prompt)
    
    return response.text
