"""Connect Instagram: log in with Facebook instead of pasting tokens.

Facebook Login → a long-lived user token → the Page linked to the Instagram account → that Page's token, which
never expires. Kept in the database (on the server's disk) and loaded into IG_ACCESS_TOKEN / IG_USER_ID, so every
part of ReelBot that posts or reads Instagram uses it.

Needs META_APP_ID and META_APP_SECRET (Railway Variables), and this site's /connect/instagram/done address added
under "Valid OAuth Redirect URIs" in the Meta app's Facebook Login settings.
"""

import os
import secrets
import time

import requests

from . import db

HAND_SET = {k: os.environ.get(k) for k in ("IG_ACCESS_TOKEN", "IG_USER_ID")}  # Railway Variables, if any

SCOPES = ["instagram_basic", "instagram_content_publish", "instagram_manage_insights", "pages_show_list",
          "pages_read_engagement", "business_management"]


def _graph():
    from . import jobs
    return f"https://graph.facebook.com/{jobs.cfg()['posting']['graph_api_version']}"


def ready():
    return bool(os.environ.get("META_APP_ID") and os.environ.get("META_APP_SECRET"))


def redirect_uri():
    host = os.environ.get("PUBLIC_URL") or os.environ.get("RAILWAY_PUBLIC_DOMAIN") or "localhost:8000"
    host = host if host.startswith("http") else f"https://{host}"
    return f"{host.rstrip('/')}/connect/instagram/done"


def login_url():
    state = secrets.token_urlsafe(24)
    db.set_setting("connect_state", {"state": state, "at": time.time()})
    version = _graph().rsplit("/", 1)[1]
    params = {"client_id": os.environ["META_APP_ID"], "redirect_uri": redirect_uri(), "state": state, "response_type": "code"}
    if os.environ.get("META_LOGIN_CONFIG_ID"):  # "Facebook Login for Business" apps pick permissions in a configuration
        params["config_id"] = os.environ["META_LOGIN_CONFIG_ID"]
    else:
        params["scope"] = ",".join(SCOPES)
    return f"https://www.facebook.com/{version}/dialog/oauth?" + requests.compat.urlencode(params)


def _get(path, **params):
    r = requests.get(f"{_graph()}/{path}", params=params, timeout=30)
    data = r.json() if r.content else {}
    if not r.ok:
        raise RuntimeError((data.get("error") or {}).get("message") or r.reason)
    return data


def finish(code, state):
    """Facebook sent the user back: swap the code for a Page token and remember the Instagram account."""
    saved = db.get_setting("connect_state") or {}
    if not state or state != saved.get("state") or time.time() - saved.get("at", 0) > 900:
        raise RuntimeError("That login link expired. Press Connect Instagram again.")
    db.set_setting("connect_state", None)
    app = {"client_id": os.environ["META_APP_ID"], "client_secret": os.environ["META_APP_SECRET"]}
    short = _get("oauth/access_token", redirect_uri=redirect_uri(), code=code, **app)["access_token"]
    long_lived = _get("oauth/access_token", grant_type="fb_exchange_token", fb_exchange_token=short, **app)["access_token"]
    pages = _get("me/accounts", access_token=long_lived,
                 fields="name,access_token,instagram_business_account{id,username}").get("data", [])
    linked = [p for p in pages if p.get("instagram_business_account")]
    if not linked:
        raise RuntimeError("No Instagram account found. Your Instagram must be a Creator or Business account linked to a "
                           "Facebook Page, and you need to tick that Page when Facebook asks.")
    page = linked[0]  # one account per ReelBot for now
    ig = page["instagram_business_account"]
    db.set_setting("instagram", {"user_id": ig["id"], "username": ig.get("username"), "page": page["name"],
                                 "token": page["access_token"], "connected_at": db.now()})
    apply()
    db.log(f"Instagram connected: @{ig.get('username')} (via the Facebook Page “{page['name']}”)")
    return ig.get("username")


def apply():
    """Use the connected account everywhere (it wins over IG_* variables set by hand)."""
    conn = db.get_setting("instagram")
    if conn and conn.get("token"):
        os.environ["IG_ACCESS_TOKEN"] = conn["token"]
        os.environ["IG_USER_ID"] = conn["user_id"]


def status():
    conn = db.get_setting("instagram")
    if conn and conn.get("token"):
        return {"connected": True, "username": conn.get("username"), "page": conn.get("page"), "how": "button"}
    if os.environ.get("IG_ACCESS_TOKEN") and os.environ.get("IG_USER_ID"):
        return {"connected": True, "username": None, "page": None, "how": "variables"}
    return {"connected": False}


def disconnect():
    conn = db.get_setting("instagram")
    db.set_setting("instagram", None)
    if conn:
        for k, v in HAND_SET.items():  # back to the Railway Variables, if there are any
            if v:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)
        db.log("Instagram disconnected")
