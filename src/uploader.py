# FILE: src/uploader.py
"""YouTube OAuth authentication and video upload."""

from __future__ import annotations

import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


CLIENT_SECRETS_FILE = Path("client_secrets.json")
CREDENTIALS_FILE = Path("credentials.json")
YOUTUBE_UPLOAD_SCOPE = [
    "https://www.googleapis.com/auth/youtube.upload"
]


def get_authenticated_service():
    credentials = None

    if CREDENTIALS_FILE.exists() and CREDENTIALS_FILE.stat().st_size > 0:
        credentials = Credentials.from_authorized_user_file(
            str(CREDENTIALS_FILE),
            YOUTUBE_UPLOAD_SCOPE,
        )

    if not credentials or not credentials.valid:
        if (
            credentials
            and credentials.expired
            and credentials.refresh_token
        ):
            print("â¹ï¸ Refreshing YouTube credentials...")
            credentials.refresh(Request())
            CREDENTIALS_FILE.write_text(
                credentials.to_json(),
                encoding="utf-8",
            )
        else:
            if os.getenv("GITHUB_ACTIONS") == "true":
                raise RuntimeError(
                    "credentials.json is missing or invalid. "
                    "Create CREDENTIALS_B64 from a valid OAuth credentials.json."
                )
            if not CLIENT_SECRETS_FILE.exists():
                raise FileNotFoundError(
                    "client_secrets.json was not found."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CLIENT_SECRETS_FILE),
                scopes=YOUTUBE_UPLOAD_SCOPE,
            )
            credentials = flow.run_local_server(port=0)
            CREDENTIALS_FILE.write_text(
                credentials.to_json(),
                encoding="utf-8",
            )

    return build("youtube", "v3", credentials=credentials)


def upload_to_youtube(
    video_path,
    title,
    description,
    tags,
    thumbnail_path=None,
):
    """Upload a video and optionally its thumbnail."""
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    print(f"â¬ï¸ Uploading '{video_path}' to YouTube...")
    youtube = get_authenticated_service()

    request_body = {
        "snippet": {
            "title": str(title)[:100],
            "description": str(description)[:5000],
            "tags": [
                tag.strip()
                for tag in str(tags).split(",")
                if tag.strip()
            ],
            "categoryId": "28",
        },
        "status": {
            "privacyStatus": os.getenv(
                "YOUTUBE_PRIVACY_STATUS",
                "public",
            ),
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        str(video_path),
        chunksize=-1,
        resumable=True,
    )
    request = youtube.videos().insert(
        part="snippet,status",
        body=request_body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Uploaded {int(status.progress() * 100)}%.")

    video_id = response.get("id")
    if not video_id:
        raise RuntimeError("YouTube returned no video ID.")

    print(f"â Video uploaded successfully! Video ID: {video_id}")

    if thumbnail_path and Path(thumbnail_path).exists():
        try:
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(str(thumbnail_path)),
            ).execute()
            print("â Thumbnail uploaded successfully!")
        except Exception as exc:
            print(f"â ï¸ Thumbnail upload failed: {exc}")

    return video_id
