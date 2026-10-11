"""Loads config.yaml and .env so every module reads settings the same way."""

import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUTPUT = ROOT / "output"
REVIEW = OUTPUT / "review"
APPROVED = OUTPUT / "approved"
POSTED = OUTPUT / "posted"


def _load_env():
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def load_config():
    _load_env()
    path = ROOT / "config.yaml"
    if not path.exists():
        path = ROOT / "config.example.yaml"
    return yaml.safe_load(path.read_text())


def env(name, required=True):
    value = os.environ.get(name, "")
    if required and not value:
        raise SystemExit(f"Missing {name}. Add it to your .env file (see .env.example).")
    return value
