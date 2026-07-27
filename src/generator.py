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
    
    client = genai.Client(api_key=google_api_key)
    
    prompt = "Generate a curriculum for a simple AI course."
    
    response = client.models.generate_content(
        model='gemini-2.0-flash',
        contents=prompt
    )
    
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
    
    client = genai.Client(api_key=google_api_key)
    
    prompt = f"Write a detailed lesson about {title}."
    
    # Remove hidden Unicode characters from prompt
    prompt = prompt.replace("\u2028", " ")
    prompt = prompt.replace("\u2029", " ")
    
    response = client.models.generate_content(
        model='gemini-2.0-flash',
        contents=prompt
    )
    
    return response.text
