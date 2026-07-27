# Gemini SDK patch for src/generator.py
# Copy the imports and functions below into src/generator.py.
# Keep your existing Pexels, TTS, video, thumbnail, and YouTube code unchanged.

import json
import os
import time
from typing import Any

from google import genai
from google.genai import types


MODEL_CANDIDATES = [
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-flash-latest",
]

_CLIENT: genai.Client | None = None
_MODEL_NAME: str | None = None


def _clean_text(value: str) -> str:
    """Remove hidden characters that previously caused header/encoding errors."""
    return (
        value.replace("\u2028", " ")
        .replace("\u2029", " ")
        .replace("\r", " ")
        .strip()
    )


def _available_generate_models(client: genai.Client) -> list[str]:
    """Return model names available to this API key."""
    names: list[str] = []

    for model in client.models.list():
        name = str(getattr(model, "name", "") or "").replace("models/", "")
        if not name:
            continue

        actions = getattr(model, "supported_actions", None)
        if actions and "generateContent" not in actions:
            continue

        names.append(name)

    print(f"Available Gemini models: {names}")
    return names


def _choose_model(client: genai.Client) -> str:
    """Choose a usable text model without repeatedly retrying an unavailable model."""
    available = _available_generate_models(client)

    for candidate in MODEL_CANDIDATES:
        if candidate in available:
            print(f"Selected Gemini model: {candidate}")
            return candidate

    # Safe fallback: choose an available Flash text model.
    blocked_words = ("image", "tts", "audio", "embedding", "robotics", "computer-use")
    for name in available:
        lower_name = name.lower()
        if "flash" in lower_name and not any(word in lower_name for word in blocked_words):
            print(f"Selected fallback Gemini model: {name}")
            return name

    raise RuntimeError(
        "No usable Gemini text model is available for this API key. "
        f"Available models: {available}"
    )


def get_client_and_model() -> tuple[genai.Client, str]:
    """Create the Gemini client and select the model once per workflow run."""
    global _CLIENT, _MODEL_NAME

    if _CLIENT is None:
        api_key = _clean_text(os.environ.get("GOOGLE_API_KEY", ""))
        if not api_key:
            raise ValueError("GOOGLE_API_KEY is missing or empty.")
        _CLIENT = genai.Client(api_key=api_key)

    if _MODEL_NAME is None:
        _MODEL_NAME = _choose_model(_CLIENT)

    return _CLIENT, _MODEL_NAME


def _generate_json(prompt: str, retries: int = 2) -> dict[str, Any]:
    """Generate and parse a JSON object. Retry only temporary 429/503 errors."""
    client, model_name = get_client_and_model()
    clean_prompt = _clean_text(prompt)

    for attempt in range(retries + 1):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=clean_prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.7,
                ),
            )

            text = (response.text or "").strip()
            if not text:
                raise ValueError("Gemini returned an empty response.")

            # Extra protection if a model still adds Markdown fences.
            text = text.removeprefix("```json").removeprefix("```")
            text = text.removesuffix("```").strip()

            result = json.loads(text)
            if not isinstance(result, dict):
                raise ValueError("Gemini response must be a JSON object.")

            return result

        except Exception as exc:
            message = str(exc)

            # Never retry an unavailable-model 404 with the same model.
            if "404" in message or "NOT_FOUND" in message:
                raise RuntimeError(
                    f"Selected model '{model_name}' became unavailable: {exc}"
                ) from exc

            temporary = "429" in message or "503" in message
            if temporary and attempt < retries:
                wait_seconds = 5 * (2 ** attempt)
                print(f"Temporary Gemini error. Retrying in {wait_seconds}s: {exc}")
                time.sleep(wait_seconds)
                continue

            raise


def generate_curriculum(previous_titles: list[str] | None = None) -> dict[str, Any]:
    """Return the exact curriculum structure expected by main.py."""
    history = ""
    if previous_titles:
        formatted = "\n".join(
            f"{index + 1}. {title}" for index, title in enumerate(previous_titles)
        )
        history = (
            "\nThese lessons have already been created. Do not repeat them:\n"
            f"{formatted}\nContinue from where the series stopped.\n"
        )

    prompt = f"""
You are an expert AI educator creating a YouTube course named
"AI for Developers".

The viewer is a complete beginner. Use simple language, practical examples,
and a logical progression from beginner to advanced topics.
{history}

Return ONLY one valid JSON object in exactly this structure:

{{
  "lessons": [
    {{
      "chapter": "Chapter 1",
      "part": "Part 1",
      "title": "Clear lesson title",
      "status": "pending",
      "youtube_id": ""
    }}
  ]
}}

Rules:
- Create 20 lessons.
- Every lesson must contain chapter, part, title, status and youtube_id.
- status must always be "pending".
- youtube_id must always be an empty string.
- Do not include Markdown or explanatory text outside the JSON.
"""

    result = _generate_json(prompt)

    lessons = result.get("lessons")
    if not isinstance(lessons, list) or not lessons:
        raise ValueError("Curriculum JSON is missing a non-empty 'lessons' list.")

    cleaned_lessons: list[dict[str, str]] = []
    for index, lesson in enumerate(lessons, start=1):
        if not isinstance(lesson, dict):
            continue

        title = str(lesson.get("title", "")).strip()
        if not title:
            continue

        cleaned_lessons.append(
            {
                "chapter": str(lesson.get("chapter") or f"Chapter {index}").strip(),
                "part": str(lesson.get("part") or f"Part {index}").strip(),
                "title": title,
                "status": "pending",
                "youtube_id": "",
            }
        )

    if not cleaned_lessons:
        raise ValueError("Gemini returned no valid curriculum lessons.")

    return {"lessons": cleaned_lessons}


def generate_lesson_content(lesson_title: str) -> dict[str, Any]:
    """Return the exact lesson structure expected by main.py."""
    safe_title = _clean_text(str(lesson_title))

    prompt = f"""
Create one beginner-friendly YouTube lesson about:

{safe_title}

Return ONLY one valid JSON object in exactly this structure:

{{
  "long_form_slides": [
    {{
      "title": "Slide title",
      "content": "Clear slide explanation"
    }}
  ],
  "short_form_highlight": "A punchy 1-2 sentence summary for a YouTube Short.",
  "hashtags": "#AI #Developer #LearnAI"
}}

Rules:
- Create 7 to 8 long_form_slides.
- Each slide must contain both title and content.
- Explain concepts simply with examples and analogies.
- short_form_highlight must be concise and understandable by itself.
- hashtags must contain 5 to 7 relevant, space-separated hashtags.
- Do not include Markdown or explanatory text outside the JSON.
"""

    result = _generate_json(prompt)

    slides = result.get("long_form_slides")
    if not isinstance(slides, list) or not slides:
        raise ValueError(
            "Lesson JSON is missing a non-empty 'long_form_slides' list."
        )

    cleaned_slides: list[dict[str, str]] = []
    for slide in slides:
        if not isinstance(slide, dict):
            continue

        title = str(slide.get("title", "")).strip()
        content = str(slide.get("content", "")).strip()
        if title and content:
            cleaned_slides.append({"title": title, "content": content})

    if not cleaned_slides:
        raise ValueError("Gemini returned no valid lesson slides.")

    highlight = str(result.get("short_form_highlight", "")).strip()
    hashtags = str(result.get("hashtags", "")).strip()

    if not highlight:
        highlight = f"Quick lesson: {safe_title}"
    if not hashtags:
        hashtags = "#AI #Developer #LearnAI #Programming #Technology"

    return {
        "long_form_slides": cleaned_slides,
        "short_form_highlight": highlight,
        "hashtags": hashtags,
        }
