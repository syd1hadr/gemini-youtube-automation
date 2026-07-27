import os
import sys
import time
from google import genai

sys.stdout.reconfigure(encoding='utf-8')

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
        return "gemini-2.0-flash-exp"
    
    raise RuntimeError("No model supporting generateContent is available.")

def main():
    api_key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if not api_key:
        print("❌ GOOGLE_API_KEY is missing!")
        exit(1)
    
    print("✅ Google API Key loaded successfully!")
    
    client = genai.Client(api_key=api_key)
    
    # Find available model automatically
    model_name = get_available_model(client)
    print(f"🎯 Using model: {model_name}")
    
    for attempt in range(5):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents="Hello, are you working?"
            )
            print("✅ Gemini says:", response.text[:100] + "...")
            print("🎯 All tests passed! Project is ready.")
            return
        except Exception as e:
            error_str = str(e)
            if "429" in error_str:
                wait = (attempt + 1) * 3
                print(f"⚠️ Quota exceeded. Retrying in {wait}s...")
                time.sleep(wait)
            elif "404" in error_str:
                print("⚠️ Model not available, trying another...")
                model_name = get_available_model(client)
                print(f"🎯 Retrying with: {model_name}")
            else:
                print(f"❌ Error: {e}")
                exit(1)
    
    print("❌ Max retries exceeded.")
    exit(1)

if __name__ == "__main__":
    main()
