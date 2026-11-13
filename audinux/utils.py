# -*- coding: utf-8 -*-
from __future__ import annotations
import json
import os
import hashlib
import subprocess
from pathlib import Path
from typing import Any

def load_json(path: Path, default: Any):
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path: Path, data: Any) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

def audio_id_for(path: str) -> str:
    """Robust ID for markers/cache: hash(ABS_PATH + SIZE + MTIME_NS)."""
    ap = os.path.abspath(path)
    st = os.stat(ap)
    mtime_ns = getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9))
    key = f"{ap}|{st.st_size}|{mtime_ns}"
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return h[:16]


def ffprobe_duration_ms(path: str) -> int:
    """Fast duration in ms using ffprobe (no full decode). Returns 0 if unknown."""
    try:
        # ffprobe prints duration in seconds (float)
        out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            stderr=subprocess.DEVNULL,
            text=True
        ).strip()
        if not out:
            return 0
        sec = float(out)
        if sec <= 0:
            return 0
        return int(sec * 1000)
    except Exception:
        return 0
