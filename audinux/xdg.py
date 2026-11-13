# -*- coding: utf-8 -*-
from __future__ import annotations
import os
from pathlib import Path

APP_NAME = "audinux"

def _env_path(var: str) -> Path | None:
    v = os.environ.get(var)
    return Path(v).expanduser() if v else None

def config_dir() -> Path:
    base = _env_path("XDG_CONFIG_HOME") or (Path.home() / ".config")
    p = base / APP_NAME
    p.mkdir(parents=True, exist_ok=True)
    return p

def data_dir() -> Path:
    base = _env_path("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
    p = base / APP_NAME
    p.mkdir(parents=True, exist_ok=True)
    return p

def cache_dir() -> Path:
    base = _env_path("XDG_CACHE_HOME") or (Path.home() / ".cache")
    p = base / APP_NAME
    p.mkdir(parents=True, exist_ok=True)
    return p

def ensure_subdir(base: Path, name: str) -> Path:
    p = base / name
    p.mkdir(parents=True, exist_ok=True)
    return p
