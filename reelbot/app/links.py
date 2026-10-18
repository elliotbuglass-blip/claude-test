"""Private, expiring links to a finished reel, so Instagram can fetch the video itself (needed for trial reels)."""

import hashlib
import hmac
import os
import time


def _secret():
    return (os.environ.get("APP_PASSWORD") or os.environ.get("ANTHROPIC_API_KEY") or "reelbot").encode()


def sign(reel_id, expires):
    return hmac.new(_secret(), f"{reel_id}:{expires}".encode(), hashlib.sha256).hexdigest()[:32]


def public_video_url(reel_id, minutes=60):
    """https://<your ReelBot address>/public/<id>.mp4?e=..&s=.. or None when the site has no public address."""
    host = os.environ.get("PUBLIC_URL") or os.environ.get("RAILWAY_PUBLIC_DOMAIN")
    if not host:
        return None
    host = host if host.startswith("http") else f"https://{host}"
    expires = int(time.time()) + minutes * 60
    return f"{host.rstrip('/')}/public/{reel_id}.mp4?e={expires}&s={sign(reel_id, expires)}"


def valid(reel_id, expires, signature):
    try:
        return int(expires) > time.time() and hmac.compare_digest(sign(reel_id, int(expires)), signature or "")
    except ValueError:
        return False
