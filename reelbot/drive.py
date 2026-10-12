"""Small Google Drive client: list, download, upload and move files in your ReelBot folder.

Signs in as you with a saved "refresh token" (made once in Google's OAuth Playground),
so nothing has to be installed or logged into on a computer.
"""

import json
from pathlib import Path

import requests

from .settings import env

API = "https://www.googleapis.com/drive/v3/files"
UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"
FOLDER = "application/vnd.google-apps.folder"


class Drive:
    def __init__(self):
        resp = requests.post("https://oauth2.googleapis.com/token", data={
            "client_id": env("GOOGLE_CLIENT_ID"),
            "client_secret": env("GOOGLE_CLIENT_SECRET"),
            "refresh_token": env("GOOGLE_REFRESH_TOKEN"),
            "grant_type": "refresh_token",
        }, timeout=30)
        if not resp.ok:
            raise SystemExit(f"Google sign-in failed: {resp.text[:300]}\n"
                             "Re-check GOOGLE_CLIENT_ID / SECRET / REFRESH_TOKEN in GitHub secrets.")
        self.s = requests.Session()
        self.s.headers["Authorization"] = f"Bearer {resp.json()['access_token']}"

    def _ok(self, resp):
        if not resp.ok:
            raise RuntimeError(f"Google Drive error ({resp.status_code}): {resp.text[:300]}")
        return resp

    def list(self, folder_id):
        files, page = [], None
        while True:
            params = {"q": f"'{folder_id}' in parents and trashed = false",
                      "fields": "nextPageToken, files(id, name, mimeType, description, size)",
                      "pageSize": 1000}
            if page:
                params["pageToken"] = page
            data = self._ok(self.s.get(API, params=params, timeout=60)).json()
            files += data.get("files", [])
            page = data.get("nextPageToken")
            if not page:
                return files

    def ensure_folders(self, root_id, names):
        """Find (or create) each subfolder of the ReelBot folder. Returns {name: id}."""
        existing = {f["name"]: f["id"] for f in self.list(root_id) if f["mimeType"] == FOLDER}
        for name in names:
            if name not in existing:
                meta = {"name": name, "mimeType": FOLDER, "parents": [root_id]}
                existing[name] = self._ok(self.s.post(API, json=meta, timeout=30)).json()["id"]
        return existing

    def download(self, file_id, dest):
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with self._ok(self.s.get(f"{API}/{file_id}", params={"alt": "media"}, stream=True, timeout=600)) as r:
            with dest.open("wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
        return dest

    def upload(self, path, folder_id, description=None, replace_id=None):
        """Upload a file (or overwrite an existing one when replace_id is given)."""
        path = Path(path)
        if replace_id:
            self._ok(self.s.patch(f"{UPLOAD}/{replace_id}", params={"uploadType": "media"},
                                  data=path.read_bytes(), timeout=600))
            return replace_id
        meta = {"name": path.name, "parents": [folder_id]}
        if description:
            meta["description"] = description
        start = self._ok(self.s.post(UPLOAD, params={"uploadType": "resumable"}, json=meta, timeout=60))
        with path.open("rb") as f:
            done = self._ok(requests.put(start.headers["Location"], data=f, timeout=1200))
        return done.json()["id"]

    def move(self, file_id, from_folder, to_folder, description=None):
        body = {"description": description} if description is not None else {}
        self._ok(self.s.patch(f"{API}/{file_id}", params={"addParents": to_folder, "removeParents": from_folder},
                              json=body, timeout=60))

    def sync_down(self, folder_id, local_dir):
        """Download every file in a Drive folder into local_dir."""
        files = [f for f in self.list(folder_id) if f["mimeType"] != FOLDER]
        for f in files:
            self.download(f["id"], Path(local_dir) / f["name"])
        return files

    def sync_up(self, local_dir, folder_id):
        """Upload every file in local_dir, overwriting same-named files in the Drive folder."""
        remote = {f["name"]: f["id"] for f in self.list(folder_id)}
        for p in Path(local_dir).glob("*"):
            if p.is_file():
                self.upload(p, folder_id, replace_id=remote.get(p.name))


def meta_from_description(text):
    try:
        return json.loads(text or "{}")
    except json.JSONDecodeError:
        return {}
