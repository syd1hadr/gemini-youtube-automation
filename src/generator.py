# FILE: src/generator.py
"""Gemini content generation, TTS, visuals, and video rendering."""

from __future__ import annotations

import json
import os
import time
from io import BytesIO
from pathlib import Path
from typing import Any

import requests
from google import genai
from google.genai import types
from gtts import gTTS
from moviepy.config import change_settings
from moviepy.editor import (
    AudioFileClip,
    CompositeAudioClip,
    ImageClip,
    concatenate_videoclips,
    vfx,
)
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pydub import AudioSegment


ASSETS_PATH = Path("assets")
FONT_FILE = ASSETS_PATH / "fonts/arial.ttf"
BACKGROUND_MUSIC_PATH = ASSETS_PATH / "music/bg_music.mp3"
FALLBACK_THUMBNAIL_FONT = ImageFont.load_default()
YOUR_NAME = os.getenv("CHANNEL_NAME", "Chaitanya")

MODEL_CANDIDATES = [
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-flash-latest",
]

_CLIENT: genai.Client | None = None
_MODEL_NAME: str | None = None

if os.name == "posix":
    change_settings({"IMAGEMAGICK_BINARY": "/usr/bin/convert"})


def _clean_text(value: str) -> str:
    return (
        str(value)
        .replace("\u2028", " ")
        .replace("\u2029", " ")
        .replace("\r", " ")
        .strip()
    )


def _get_client() -> genai.Client:
    global _CLIENT
    if _CLIENT is None:
        api_key = _clean_text(os.environ.get("GOOGLE_API_KEY", ""))
        if not api_key:
            raise ValueError("GOOGLE_API_KEY is missing or empty.")
        _CLIENT = genai.Client(api_key=api_key)
    return _CLIENT


def _list_model_names(client: genai.Client) -> list[str]:
    names: list[str] = []
    for model in client.models.list():
        name = str(getattr(model, "name", "") or "").replace("models/", "")
        if name:
            names.append(name)
    print(f"â Available Gemini models: {names}")
    return names


def _choose_model(client: genai.Client) -> str:
    global _MODEL_NAME
    if _MODEL_NAME:
        return _MODEL_NAME

    available = _list_model_names(client)

    for candidate in MODEL_CANDIDATES:
        if candidate in available:
            _MODEL_NAME = candidate
            print(f"ð¯ Selected Gemini model: {_MODEL_NAME}")
            return _MODEL_NAME

    blocked = (
        "image",
        "tts",
        "audio",
        "embedding",
        "robotics",
        "computer-use",
        "lyria",
        "deep-research",
    )
    for name in available:
        lower = name.lower()
        if "flash" in lower and not any(word in lower for word in blocked):
            _MODEL_NAME = name
            print(f"ð¯ Selected fallback Gemini model: {_MODEL_NAME}")
            return _MODEL_NAME

    raise RuntimeError(
        "No usable Gemini text model is available. "
        f"Available models: {available}"
    )


def _extract_json(text: str) -> dict[str, Any]:
    cleaned = (text or "").strip()
    cleaned = cleaned.removeprefix("```json").removeprefix("```")
    cleaned = cleaned.removesuffix("```").strip()
    parsed = json.loads(cleaned)
    if not isinstance(parsed, dict):
        raise ValueError("Gemini response must be a JSON object.")
    return parsed


def _candidate_models(client: genai.Client) -> list[str]:
    """Return preferred available text models in fallback order."""
    available = _list_model_names(client)
    ordered: list[str] = []

    for candidate in MODEL_CANDIDATES:
        if candidate in available and candidate not in ordered:
            ordered.append(candidate)

    blocked = (
        "image",
        "tts",
        "audio",
        "embedding",
        "robotics",
        "computer-use",
        "lyria",
        "deep-research",
        "live",
    )
    for name in available:
        lower = name.lower()
        if (
            "flash" in lower
            and not any(word in lower for word in blocked)
            and name not in ordered
        ):
            ordered.append(name)

    if not ordered:
        raise RuntimeError(
            "No usable Gemini text model is available. "
            f"Available models: {available}"
        )

    print(f"ð Gemini fallback order: {ordered}")
    return ordered


def _generate_json(prompt: str) -> dict[str, Any]:
    """
    Generate JSON with model fallback.

    For each model:
    - Try immediately.
    - Retry temporary 429/503 errors after 10, 30, and 60 seconds.
    - On persistent 429/503 or a 404, move to the next available model.
    """
    client = _get_client()
    prompt = _clean_text(prompt)
    models = _candidate_models(client)
    wait_times = (10, 30, 60)
    errors: list[str] = []

    global _MODEL_NAME

    for model_name in models:
        print(f"ð¯ Trying Gemini model: {model_name}")

        for attempt in range(len(wait_times) + 1):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.7,
                    ),
                )

                if not response.text:
                    raise ValueError("Gemini returned an empty response.")

                result = _extract_json(response.text)
                _MODEL_NAME = model_name
                print(f"â Gemini request succeeded with: {model_name}")
                return result

            except Exception as exc:
                message = str(exc)
                is_not_found = "404" in message or "NOT_FOUND" in message
                is_temporary = "429" in message or "503" in message

                if is_not_found:
                    print(
                        f"â ï¸ Model unavailable: {model_name}. "
                        "Trying the next model."
                    )
                    errors.append(f"{model_name}: {message}")
                    break

                if is_temporary:
                    if attempt < len(wait_times):
                        wait = wait_times[attempt]
                        print(
                            f"â ï¸ Temporary error on {model_name}. "
                            f"Retrying in {wait}s: {exc}"
                        )
                        time.sleep(wait)
                        continue

                    print(
                        f"â ï¸ {model_name} stayed unavailable after all retries. "
                        "Trying the next model."
                    )
                    errors.append(f"{model_name}: {message}")
                    break

                raise

    raise RuntimeError(
        "All available Gemini models failed. Errors: "
        + " | ".join(errors)
    )


def get_pexels_image(query: str, video_type: str) -> Image.Image | None:
    """Fetch one relevant background image from Pexels."""
    pexels_api_key = _clean_text(os.getenv("PEXELS_API_KEY", ""))
    if not pexels_api_key:
        print("â ï¸ PEXELS_API_KEY missing. Using a solid background.")
        return None

    orientation = "landscape" if video_type == "long" else "portrait"
    try:
        response = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": pexels_api_key},
            params={
                "query": f"abstract {query}",
                "per_page": 1,
                "orientation": orientation,
            },
            timeout=20,
        )
        response.raise_for_status()
        photos = response.json().get("photos", [])
        if not photos:
            return None

        image_url = photos[0]["src"]["large2x"]
        image_response = requests.get(image_url, timeout=20)
        image_response.raise_for_status()
        return Image.open(BytesIO(image_response.content)).convert("RGBA")
    except Exception as exc:
        print(f"â ï¸ Pexels image unavailable for '{query}': {exc}")
        return None


def text_to_speech(text: str, output_path: Path) -> Path:
    """Convert narration to WAV for reliable MoviePy audio."""
    print("ð¤ Converting script to speech...")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    temp_mp3 = output_path.with_name(f"{output_path.stem}_temp.mp3")
    wav_path = output_path.with_suffix(".wav")

    try:
        gTTS(text=_clean_text(text), lang="en", slow=False).save(str(temp_mp3))
        audio = AudioSegment.from_mp3(str(temp_mp3))
        audio.export(str(wav_path), format="wav", codec="pcm_s16le")
        temp_mp3.unlink(missing_ok=True)
        print("â Speech generated successfully.")
        return wav_path
    except Exception:
        temp_mp3.unlink(missing_ok=True)
        raise


def generate_curriculum(
    previous_titles: list[str] | None = None,
) -> dict[str, Any]:
    """Generate the exact curriculum structure expected by main.py."""
    print("ð¤ Generating curriculum...")

    history = ""
    if previous_titles:
        formatted = "\n".join(
            f"{index + 1}. {title}"
            for index, title in enumerate(previous_titles)
        )
        history = (
            "These lessons have already been created. Do not repeat them:\n"
            f"{formatted}\nContinue from where the series stopped.\n"
        )

    prompt = f"""
You are an expert AI educator creating a beginner-friendly YouTube course
called "AI for Developers by {YOUR_NAME}".

{history}

Return ONLY one valid JSON object with exactly this structure:
{{
  "lessons": [
    {{
      "chapter": "1",
      "part": "1",
      "title": "A clear lesson title",
      "status": "pending",
      "youtube_id": null
    }}
  ]
}}

Rules:
- Create exactly 20 lessons.
- Progress logically from beginner to advanced AI.
- Every lesson must contain chapter, part, title, status, and youtube_id.
- status must be "pending".
- youtube_id must be null.
- Do not include Markdown or explanations outside JSON.
"""
    result = _generate_json(prompt)
    lessons = result.get("lessons")
    if not isinstance(lessons, list) or not lessons:
        raise ValueError("Gemini returned no valid 'lessons' list.")

    clean_lessons: list[dict[str, Any]] = []
    for index, lesson in enumerate(lessons, start=1):
        if not isinstance(lesson, dict):
            continue
        title = _clean_text(lesson.get("title", ""))
        if not title:
            continue
        clean_lessons.append(
            {
                "chapter": _clean_text(lesson.get("chapter", index)),
                "part": _clean_text(lesson.get("part", index)),
                "title": title,
                "status": "pending",
                "youtube_id": None,
            }
        )

    if not clean_lessons:
        raise ValueError("Gemini returned no usable lessons.")
    return {"lessons": clean_lessons}


def generate_lesson_content(lesson_title: str) -> dict[str, Any]:
    """Generate long-form slides, a Short highlight, and hashtags."""
    lesson_title = _clean_text(lesson_title)
    print(f"ð¤ Generating content for lesson: '{lesson_title}'...")

    prompt = f"""
Create a beginner-friendly YouTube lesson for
"AI for Developers by {YOUR_NAME}".

Topic: {lesson_title}

Return ONLY one valid JSON object with exactly this structure:
{{
  "long_form_slides": [
    {{
      "title": "Slide title",
      "content": "Simple and useful slide explanation"
    }}
  ],
  "short_form_highlight": "A punchy 1-2 sentence summary.",
  "hashtags": "#AI #Developer #LearnAI"
}}

Rules:
- Create 7 to 8 long_form_slides.
- Each slide must contain title and content.
- Use simple explanations, examples, and analogies.
- The highlight must work as a standalone YouTube Short.
- Include 5 to 7 relevant space-separated hashtags.
- Do not include Markdown or explanations outside JSON.
"""
    result = _generate_json(prompt)

    slides = result.get("long_form_slides")
    if not isinstance(slides, list) or not slides:
        raise ValueError("Gemini returned no valid long_form_slides.")

    clean_slides: list[dict[str, str]] = []
    for slide in slides:
        if not isinstance(slide, dict):
            continue
        title = _clean_text(slide.get("title", ""))
        content = _clean_text(slide.get("content", ""))
        if title and content:
            clean_slides.append({"title": title, "content": content})

    if not clean_slides:
        raise ValueError("Gemini returned no usable slides.")

    highlight = _clean_text(result.get("short_form_highlight", ""))
    hashtags = _clean_text(result.get("hashtags", ""))

    return {
        "long_form_slides": clean_slides,
        "short_form_highlight": highlight or f"Quick AI lesson: {lesson_title}",
        "hashtags": hashtags
        or "#AI #Developer #LearnAI #Programming #Technology",
    }


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype(str(FONT_FILE), size)
    except OSError:
        return FALLBACK_THUMBNAIL_FONT


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    words = str(text).split()
    if not words:
        return [""]

    lines: list[str] = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        box = draw.textbbox((0, 0), test, font=font)
        if box[2] - box[0] <= max_width or not current:
            current = test
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def generate_visuals(
    output_dir: Path,
    video_type: str,
    slide_content: dict[str, str] | None = None,
    thumbnail_title: str | None = None,
    slide_number: int = 0,
    total_slides: int = 0,
) -> str:
    """Create one slide or thumbnail."""
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True, parents=True)

    is_thumbnail = thumbnail_title is not None
    width, height = (1920, 1080) if video_type == "long" else (1080, 1920)
    slide_content = slide_content or {}
    title = _clean_text(
        thumbnail_title if is_thumbnail else slide_content.get("title", "")
    )

    bg_image = get_pexels_image(title, video_type)
    if bg_image is None:
        bg_image = Image.new("RGBA", (width, height), color=(12, 17, 29))

    bg_image = bg_image.resize((width, height)).filter(
        ImageFilter.GaussianBlur(5)
    )
    darken = Image.new("RGBA", bg_image.size, (0, 0, 0, 150))
    final_bg = Image.alpha_composite(bg_image, darken).convert("RGB")
    draw = ImageDraw.Draw(final_bg)

    title_font = _font(80 if video_type == "long" else 90)
    content_font = _font(45 if video_type == "long" else 55)
    footer_font = _font(25 if video_type == "long" else 35)

    if is_thumbnail:
        title_lines = _wrap_text(draw, title, title_font, int(width * 0.85))
        line_height = max(title_font.getbbox("Ag")[3] + 12, 30)
        start_y = (height - len(title_lines) * line_height) / 2
        for line in title_lines:
            box = draw.textbbox((0, 0), line, font=title_font)
            x = (width - (box[2] - box[0])) / 2
            draw.text(
                (x, start_y),
                line,
                font=title_font,
                fill=(255, 255, 255),
                stroke_width=2,
                stroke_fill="black",
            )
            start_y += line_height
    else:
        header_height = int(height * 0.18)
        draw.rectangle(
            (0, 0, width, header_height),
            fill=(25, 40, 65, 200),
        )

        title_lines = _wrap_text(draw, title, title_font, int(width * 0.9))
        title_line_height = max(title_font.getbbox("Ag")[3] + 10, 30)
        title_y = (
            header_height - len(title_lines) * title_line_height
        ) / 2
        for line in title_lines:
            box = draw.textbbox((0, 0), line, font=title_font)
            x = (width - (box[2] - box[0])) / 2
            draw.text(
                (x, title_y),
                line,
                font=title_font,
                fill=(255, 255, 255),
            )
            title_y += title_line_height

        content = _clean_text(slide_content.get("content", ""))
        content_lines = _wrap_text(
            draw,
            content,
            content_font,
            int(width * 0.82),
        )
        content_line_height = max(content_font.getbbox("Ag")[3] + 15, 25)
        content_y = header_height + 100
        if len(content.split()) < 10:
            content_y = (
                height - len(content_lines) * content_line_height
            ) / 2

        for line in content_lines:
            box = draw.textbbox((0, 0), line, font=content_font)
            x = (width - (box[2] - box[0])) / 2
            draw.text(
                (x, content_y),
                line,
                font=content_font,
                fill=(230, 230, 230),
            )
            content_y += content_line_height

        footer_height = int(height * 0.06)
        draw.rectangle(
            (0, height - footer_height, width, height),
            fill=(25, 40, 65, 200),
        )
        draw.text(
            (40, height - footer_height + 12),
            f"AI for Developers by {YOUR_NAME}",
            font=footer_font,
            fill=(180, 180, 180),
        )
        if total_slides:
            slide_text = f"Slide {slide_number} of {total_slides}"
            box = draw.textbbox((0, 0), slide_text, font=footer_font)
            draw.text(
                (width - (box[2] - box[0]) - 40, height - footer_height + 12),
                slide_text,
                font=footer_font,
                fill=(180, 180, 180),
            )

    prefix = "thumbnail" if is_thumbnail else f"slide_{slide_number:02d}"
    path = output_dir / f"{prefix}.png"
    final_bg.save(path)
    return str(path)


def create_video(
    slide_paths: list[str],
    audio_paths: list[Path],
    output_path: Path,
    video_type: str,
) -> None:
    """Create final video from slides and synchronized narration."""
    print(f"ð¬ Creating {video_type} video...")
    if not slide_paths or len(slide_paths) != len(audio_paths):
        raise ValueError("Slides and audio counts do not match.")

    image_clips = []
    opened_audio = []
    bg_music = None
    final_video = None

    try:
        for image_path, audio_path in zip(slide_paths, audio_paths):
            audio_clip = AudioFileClip(str(audio_path))
            opened_audio.append(audio_clip)
            duration = audio_clip.duration + 0.5
            clip = (
                ImageClip(str(image_path))
                .set_duration(duration)
                .set_audio(audio_clip)
                .fadein(0.5)
                .fadeout(0.5)
            )
            image_clips.append(clip)

        final_video = concatenate_videoclips(image_clips, method="compose")

        if BACKGROUND_MUSIC_PATH.exists():
            print("ðµ Adding background music...")
            bg_music = AudioFileClip(str(BACKGROUND_MUSIC_PATH)).volumex(0.05)
            if bg_music.duration < final_video.duration:
                bg_music = bg_music.fx(vfx.loop, duration=final_video.duration)
            else:
                bg_music = bg_music.subclip(0, final_video.duration)

            final_video = final_video.set_audio(
                CompositeAudioClip(
                    [final_video.audio.volumex(1.2), bg_music]
                )
            )

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        final_video.write_videofile(
            str(output_path),
            fps=24,
            codec="libx264",
            audio_codec="aac",
            audio_bitrate="192k",
            preset="medium",
            threads=4,
        )
        print(f"â {video_type.capitalize()} video created successfully!")
    finally:
        if final_video is not None:
            final_video.close()
        if bg_music is not None:
            bg_music.close()
        for clip in image_clips:
            clip.close()
        for audio in opened_audio:
            audio.close()
