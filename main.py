# FILE: main.py
"""Autonomous lesson production pipeline."""

from __future__ import annotations

import datetime
import json
import os
import re
import sys
import time
import traceback
from pathlib import Path

from src.generator import (
    YOUR_NAME,
    create_video,
    generate_curriculum,
    generate_lesson_content,
    generate_visuals,
    text_to_speech,
)
from src.uploader import upload_to_youtube


CONTENT_PLAN_FILE = Path("content_plan.json")
OUTPUT_DIR = Path("output")
LESSONS_PER_RUN = 1


def get_content_plan():
    if not CONTENT_PLAN_FILE.exists():
        print("📄 content_plan.json not found. Generating a new plan...")
        new_plan = generate_curriculum()
        update_content_plan(new_plan)
        return new_plan

    try:
        with CONTENT_PLAN_FILE.open("r", encoding="utf-8") as file:
            plan = json.load(file)
        if not isinstance(plan.get("lessons"), list) or not plan["lessons"]:
            raise ValueError("Invalid or empty lesson plan.")
        return plan
    except Exception as exc:
        print(f"❌ Could not load content plan: {exc}. Regenerating...")
        new_plan = generate_curriculum()
        update_content_plan(new_plan)
        return new_plan


def update_content_plan(plan):
    with CONTENT_PLAN_FILE.open("w", encoding="utf-8") as file:
        json.dump(plan, file, indent=2, ensure_ascii=False)


def _safe_name(value):
    cleaned = re.sub(r"[^\w-]", "_", str(value), flags=re.UNICODE)
    return cleaned.strip("_") or "unknown"


def produce_lesson_videos(lesson):
    print(f"\n▶️ Starting production for lesson: '{lesson['title']}'")

    chapter_safe = _safe_name(lesson.get("chapter", "chapter"))
    part_safe = _safe_name(lesson.get("part", "part"))
    unique_id = (
        f"{datetime.datetime.now().strftime('%Y%m%d')}_"
        f"{chapter_safe}_{part_safe}"
    )

    lesson_content = generate_lesson_content(lesson["title"])

    print("\n--- Producing Long-Form Video ---")
    intro_slide = {
        "title": lesson["title"],
        "content": (
            f"Chapter {lesson.get('chapter', '')} | "
            f"Part {lesson.get('part', '')}"
        ),
    }
    outro_slide = {
        "title": "Thanks for Watching!",
        "content": (
            "Like, share, and subscribe for more daily AI content!"
        ),
    }

    content_slides = lesson_content["long_form_slides"]
    all_slides = [intro_slide, *content_slides, outro_slide]
    slide_scripts = [
        (
            f"Hello and welcome to AI for Developers. "
            f"I'm {YOUR_NAME} talking bot. "
            f"Today's lesson is {lesson['title']}."
        ),
        *[slide["content"] for slide in content_slides],
        (
            "Thanks for watching. Subscribe to the channel "
            "for more beginner-friendly AI lessons."
        ),
    ]

    slide_audio_paths = []
    for index, script in enumerate(slide_scripts, start=1):
        audio_path = OUTPUT_DIR / f"audio_slide_{index}_{unique_id}.mp3"
        slide_audio_paths.append(text_to_speech(script, audio_path))

    slide_dir = OUTPUT_DIR / f"slides_long_{unique_id}"
    slide_paths = []
    for index, slide in enumerate(all_slides, start=1):
        slide_paths.append(
            generate_visuals(
                output_dir=slide_dir,
                video_type="long",
                slide_content=slide,
                slide_number=index,
                total_slides=len(all_slides),
            )
        )

    long_video_path = OUTPUT_DIR / f"long_video_{unique_id}.mp4"
    create_video(
        slide_paths,
        slide_audio_paths,
        long_video_path,
        "long",
    )

    long_thumb_path = generate_visuals(
        output_dir=OUTPUT_DIR,
        video_type="long",
        thumbnail_title=lesson["title"],
    )

    print("\n--- Producing Short Video ---")
    highlight = (
        lesson_content.get("short_form_highlight")
        or f"AI Quick Tip: {lesson['title']}"
    ).strip()
    short_script = (
        f"{highlight}\n\n"
        "The full lesson is linked in the description."
    )
    short_audio_path = text_to_speech(
        short_script,
        OUTPUT_DIR / f"short_audio_{unique_id}.mp3",
    )

    short_slide_path = generate_visuals(
        output_dir=OUTPUT_DIR / f"slides_short_{unique_id}",
        video_type="short",
        slide_content={
            "title": "Quick Tip!",
            "content": highlight,
        },
        slide_number=1,
        total_slides=1,
    )

    short_video_path = OUTPUT_DIR / f"short_video_{unique_id}.mp4"
    create_video(
        [short_slide_path],
        [short_audio_path],
        short_video_path,
        "short",
    )

    short_thumb_path = generate_visuals(
        output_dir=OUTPUT_DIR,
        video_type="short",
        thumbnail_title=f"Quick Tip: {lesson['title']}",
    )

    print("\n📤 Uploading to YouTube...")
    hashtags = lesson_content.get(
        "hashtags",
        "#AI #Developer #LearnAI",
    )
    long_description = (
        f"Part of the AI for Developers series by {YOUR_NAME}.\n\n"
        f"Today's lesson: {lesson['title']}\n\n"
        f"{hashtags}"
    )
    long_tags = (
        "AI,Artificial Intelligence,Developer,Programming,Tutorial,"
        + lesson["title"].replace(" ", ",")
    )

    long_video_id = upload_to_youtube(
        long_video_path,
        lesson["title"],
        long_description,
        long_tags,
        long_thumb_path,
    )
    if not long_video_id:
        return None

    print("⏳ Waiting 30 seconds before uploading the Short...")
    time.sleep(30)

    short_title = f"{highlight[:90].rstrip()} #Shorts"
    short_description = (
        f"{highlight}\n\n"
        f"Watch the full lesson here: "
        f"https://www.youtube.com/watch?v={long_video_id}\n\n"
        f"{hashtags}"
    )
    upload_to_youtube(
        short_video_path,
        short_title,
        short_description,
        "AI,Shorts,TechTip",
        short_thumb_path,
    )
    return long_video_id


def main():
    print("🚀 Starting Autonomous AI Course Generator")
    print(f"📁 Working directory: {os.getcwd()}")

    OUTPUT_DIR.mkdir(exist_ok=True)
    plan = get_content_plan()
    pending = [
        lesson
        for lesson in plan["lessons"]
        if lesson.get("status") == "pending"
    ]

    if not pending:
        print("🎉 All lessons complete. Extending the curriculum...")
        previous_titles = [
            lesson["title"]
            for lesson in plan["lessons"]
            if lesson.get("title")
        ]
        plan = generate_curriculum(previous_titles=previous_titles)
        update_content_plan(plan)
        pending = [
            lesson
            for lesson in plan["lessons"]
            if lesson.get("status") == "pending"
        ]

    if not pending:
        raise RuntimeError("No pending lesson is available.")

    failed_lessons = []
    for lesson in pending[:LESSONS_PER_RUN]:
        try:
            video_id = produce_lesson_videos(lesson)
            if not video_id:
                raise RuntimeError("YouTube returned no video ID.")

            lesson["status"] = "complete"
            lesson["youtube_id"] = video_id
            print(f"✅ Completed lesson: {lesson['title']}")
        except Exception:
            print(f"❌ Failed producing lesson: {lesson.get('title')}")
            traceback.print_exc()
            failed_lessons.append(lesson.get("title", "Unknown lesson"))
        finally:
            update_content_plan(plan)
            print("📦 Content plan saved.")

    for wav_file in OUTPUT_DIR.glob("*.wav"):
        try:
            wav_file.unlink()
        except OSError as exc:
            print(f"⚠️ Could not delete {wav_file}: {exc}")

    if failed_lessons:
        print(f"\n❌ PIPELINE FAILED: {failed_lessons}")
        sys.exit(1)


if __name__ == "__main__":
    main()
