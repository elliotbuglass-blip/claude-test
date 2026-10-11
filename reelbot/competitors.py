"""Looks up competitor accounts through Instagram's official Business Discovery API.

This only reads public numbers and captions (no downloading other people's videos),
and works for Business/Creator accounts.
"""

import json

import requests

from .settings import DATA, env

COMPETITORS = DATA / "competitors.json"


def refresh(usernames, api_version, per_account=30):
    user_id = env("IG_USER_ID")
    token = env("IG_ACCESS_TOKEN")
    posts = []
    for name in usernames:
        fields = (
            f"business_discovery.username({name})"
            f"{{followers_count,media.limit({per_account})"
            "{caption,like_count,comments_count,media_product_type,timestamp,permalink}}"
        )
        resp = requests.get(
            f"https://graph.facebook.com/{api_version}/{user_id}",
            params={"fields": fields, "access_token": token},
            timeout=60,
        )
        if not resp.ok:
            print(f"  ! couldn't read @{name}: {resp.json().get('error', {}).get('message', resp.text)}")
            continue
        info = resp.json()["business_discovery"]
        followers = info.get("followers_count") or 1
        for m in info.get("media", {}).get("data", []):
            if m.get("media_product_type") != "REELS":
                continue
            likes = m.get("like_count") or 0
            posts.append({
                "account": name,
                "caption": m.get("caption") or "",
                "likes": likes,
                "comments": m.get("comments_count") or 0,
                # likes per 1k followers lets small and big accounts be compared fairly
                "likes_per_1k_followers": round(likes / followers * 1000, 1),
                "timestamp": m.get("timestamp"),
                "permalink": m.get("permalink"),
            })
        print(f"  ✓ @{name}: {followers:,} followers")
    DATA.mkdir(exist_ok=True)
    COMPETITORS.write_text(json.dumps(posts, ensure_ascii=False, indent=1))
    return posts


def load():
    if not COMPETITORS.exists():
        return []
    return json.loads(COMPETITORS.read_text())


def top_posts(n=20):
    return sorted(load(), key=lambda p: p["likes_per_1k_followers"], reverse=True)[:n]
