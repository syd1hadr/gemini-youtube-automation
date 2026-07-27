import os
import time
from google import genai

def get_available_model(client):
    """Automatically find which model supports generateContent"""
    preferred_models = [
        "gemini-2.5-flash",
        "gemini-2.0-flash-exp",
        "gemini-1.5-flash",
        "gemini-2.0-flash"
    ]
    
    available_models = []
    
    try:
        for model in client.models.list():
            model_name = model.name.replace("models/", "")
            supported_actions = getattr(model, "supported_actions", []) or []
            
            if "generateContent" in supported_actions:
                available_models.append(model_name)
        
        print(f"✅ Available models: {available_models}")
        
        for preferred in preferred_models:
            if preferred in available_models:
                return preferred
        
        for model_name in available_models:
            if "flash" in model_name.lower():
                return model_name
        
        if available_models:
            return available_models[0]
            
    except Exception as e:
        print(f"⚠️ Could not list models: {e}")
        return "gemini-2.0-flash-exp"  # fallback
    
    raise RuntimeError("No model supporting generateContent is available.")

# Global model name - will be set when client is created
MODEL_NAME = None

def get_client_and_model():
    """Initialize client and get available model"""
    global MODEL_NAME
    
    api_key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GOOGLE_API_KEY is missing!")
    
    client = genai.Client(api_key=api_key)
    
    if MODEL_NAME is None:
        MODEL_NAME = get_available_model(client)
        print(f"🎯 Using model: {MODEL_NAME}")
    
    return client, MODEL_NAME

def generate_curriculum():
    client, model_name = get_client_and_model()
    
    prompt = """Generate a simple curriculum for an AI course.
    Include 5 lessons with titles and brief descriptions.
    Return as JSON array with 'title' and 'description' keys.
    Keep it simple and educational."""
    
    for attempt in range(5):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            return response.text
        except Exception as e:
            error_str = str(e)
            if "429" in error_str:
                wait = (attempt + 1) * 3
                print(f"⚠️ Quota exceeded. Retrying in {wait}s...")
                time.sleep(wait)
            elif "404" in error_str:
                # Model not available, try to find another
                print("⚠️ Model not available, finding another...")
                global MODEL_NAME
                MODEL_NAME = None
                _, MODEL_NAME = get_client_and_model()
            else:
                raise e
    raise Exception("Max retries exceeded.")

def generate_lesson_content(title):
    client, model_name = get_client_and_model()
    
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
    
    for attempt in range(5):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            return response.text
        except Exception as e:
            error_str = str(e)
            if "429" in error_str:
                wait = (attempt + 1) * 3
                print(f"⚠️ Quota exceeded. Retrying in {wait}s...")
                time.sleep(wait)
            elif "404" in error_str:
                # Model not available, try to find another
                print("⚠️ Model not available, finding another...")
                global MODEL_NAME
                MODEL_NAME = None
                _, MODEL_NAME = get_client_and_model()
            else:
                raise e
    raise Exception("Max retries exceeded.")
