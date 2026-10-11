"""Posts a finished video to Instagram as a trial reel via Meta's Graph API.

Flow (Meta's "resumable upload"): make a container -> upload the file -> wait -> publish.
Uploading the file directly means you don't need to host videos anywhere.
"""

import json
import time
from pathlib import Path

import requests

from .settings import env


def post_reel(video_path, caption, posting):
    version = posting["graph_api_version"]
    user_id = env("IG_USER_ID")
    token = env("IG_ACCESS_TOKEN")
    graph = f"https://graph.facebook.com/{version}"

    params = {
        "media_type": "REELS",
        "upload_type": "resumable",
        "caption": caption,
        "access_token": token,
    }
    if posting.get("trial_reel"):
        params["trial_params"] = json.dumps({"graduation_strategy": posting.get("graduation", "MANUAL")})
    container = _ok(requests.post(f"{graph}/{user_id}/media", data=params, timeout=60))["id"]

    video = Path(video_path).read_bytes()
    _ok(requests.post(
        f"https://rupload.facebook.com/ig-api-upload/{version}/{container}",
        headers={"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(len(video))},
        data=video,
        timeout=600,
    ))

    for _ in range(60):  # Instagram processes the video; wait up to ~5 minutes
        status = _ok(requests.get(f"{graph}/{container}",
                                  params={"fields": "status_code,status", "access_token": token},
                                  timeout=30))
        if status.get("status_code") == "FINISHED":
            break
        if status.get("status_code") == "ERROR":
            raise RuntimeError(f"Instagram couldn't process the video: {status.get('status')}")
        time.sleep(5)
    else:
        raise RuntimeError("Instagram took too long to process the video.")

    published = _ok(requests.post(f"{graph}/{user_id}/media_publish",
                                  data={"creation_id": container, "access_token": token},
                                  timeout=60))
    return published["id"]


def _ok(resp):
    if not resp.ok:
        try:
            message = resp.json().get("error", {}).get("message", resp.text)
        except ValueError:
            message = resp.text
        raise RuntimeError(f"Instagram API error ({resp.status_code}): {message}")
    return resp.json()
