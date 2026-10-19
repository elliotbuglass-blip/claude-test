"""Posts a finished video to Instagram as a trial reel.

Two ways, set by posting.backend in config.yaml:
- "graph": straight to Meta's Graph API (free; needs a Meta developer app + token).
  Flow: make a container -> upload the file -> wait -> publish.
- "metricool": schedules through Metricool (paid plan), which supports TRIAL_REEL.
  Flow: upload to a temporary file host -> Metricool downloads it and publishes at the set time.
"""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

from .settings import env


def post_reel(video_path, caption, posting, slot=0, video_url=None):
    """Returns an id. For Metricool, `slot` spaces posts out by minutes_between_posts.
    video_url: a public link Instagram can fetch the video from (trial reels need this way of publishing)."""
    if posting.get("backend") == "metricool":
        when = datetime.now() + timedelta(minutes=5 + slot * posting["minutes_between_posts"])
        return _metricool(video_path, caption, posting, when)
    return _graph(video_path, caption, posting, video_url)


def _metricool(video_path, caption, posting, when):
    with open(video_path, "rb") as f:
        up = requests.post("https://tmpfiles.org/api/v1/upload", files={"file": f}, timeout=300)
    up.raise_for_status()
    video_url = up.json()["data"]["url"].replace("tmpfiles.org/", "tmpfiles.org/dl/")

    resp = requests.post(
        "https://app.metricool.com/api/v2/scheduler/posts",
        headers={"X-Mc-Auth": env("METRICOOL_API_TOKEN")},
        params={"userId": env("METRICOOL_USER_ID"), "blogId": env("METRICOOL_BLOG_ID")},
        json={
            "text": caption,
            "publicationDate": {"dateTime": when.strftime("%Y-%m-%dT%H:%M:%S"),
                                "timezone": posting.get("timezone", "Europe/London")},
            "draft": False,
            "autoPublish": True,
            "saveExternalMediaFiles": True,
            "providers": [{"network": "INSTAGRAM"}],
            "instagramData": {"type": "TRIAL_REEL" if posting.get("trial_reel") else "REEL",
                              "shareTrialAutomatically": posting.get("graduation") == "SS_PERFORMANCE"},
            "media": [video_url],
        },
        timeout=60,
    )
    # Never retry blindly: the post may exist even if the response errored. Check Metricool first.
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Metricool error ({resp.status_code}): {resp.text[:300]} "
                           "- check the Metricool planner before retrying, to avoid duplicates.")
    return f"metricool:{resp.json().get('data', {}).get('id')} @ {when:%Y-%m-%d %H:%M}"


def _graph(video_path, caption, posting, video_url=None):
    version = posting["graph_api_version"]
    user_id = env("IG_USER_ID")
    # The token is either an env var, or added to requests by a Claude Code network secret
    # (Authorization header on graph.facebook.com / rupload.facebook.com) — then it's blank here.
    token = env("IG_ACCESS_TOKEN", required=False)
    auth = {"access_token": token} if token else {}
    graph = f"https://graph.facebook.com/{version}"

    if posting.get("trial_reel") and not video_url:
        raise RuntimeError("Not posted: trial reels need Creatr's public web address (PUBLIC_URL), so it refused "
                           "rather than post a normal reel to your followers.")
    params = {"media_type": "REELS", "caption": caption, **auth}
    # Every documented trial-reel example passes video_url; the resumable upload route dropped trial_params.
    params.update({"video_url": video_url} if video_url else {"upload_type": "resumable"})
    if posting.get("trial_reel"):
        params["trial_params"] = json.dumps({"graduation_strategy": posting.get("graduation", "MANUAL")})
    # Meta documents trial_params as a query parameter: sent in the body it was silently ignored.
    container = _ok(requests.post(f"{graph}/{user_id}/media", params=params, timeout=60))["id"]

    if not video_url:
        video = Path(video_path).read_bytes()
        _ok(requests.post(
            f"https://rupload.facebook.com/ig-api-upload/{version}/{container}",
            headers={**({"Authorization": f"OAuth {token}"} if token else {}),
                     "offset": "0", "file_size": str(len(video))},
            data=video,
            timeout=600,
        ))

    for _ in range(60):  # Instagram processes the video; wait up to ~5 minutes
        status = _ok(requests.get(f"{graph}/{container}",
                                  params={"fields": "status_code,status", **auth},
                                  timeout=30))
        if status.get("status_code") == "FINISHED":
            break
        if status.get("status_code") == "ERROR":
            raise RuntimeError(f"Instagram couldn't process the video: {status.get('status')}")
        time.sleep(5)
    else:
        raise RuntimeError("Instagram took too long to process the video.")

    published = _ok(requests.post(f"{graph}/{user_id}/media_publish",
                                  data={"creation_id": container, **auth},
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
