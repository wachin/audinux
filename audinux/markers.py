# -*- coding: utf-8 -*-
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .xdg import data_dir, ensure_subdir
from .utils import load_json, save_json, audio_id_for

@dataclass
class Marker:
    name: str
    ms: int

class MarkersManager:
    def __init__(self):
        self._markers: List[Marker] = []
        self._audio_path: Optional[str] = None
        self._audio_id: Optional[str] = None
        self.loop_enabled = False
        self.loop_start: Optional[int] = None
        self.loop_end: Optional[int] = None

    def _markers_file(self) -> Optional[Path]:
        if not self._audio_id:
            return None
        base = ensure_subdir(data_dir(), "markers")
        return base / f"{self._audio_id}.json"

    def load_for(self, audio_path: str):
        self._audio_path = audio_path
        self._audio_id = audio_id_for(audio_path)
        f = self._markers_file()
        payload = load_json(f, {"markers": []}) if f else {"markers": []}
        data = payload.get("markers", [])
        self._markers = [Marker(m.get("name", ""), int(m.get("ms", 0))) for m in data]
        self._markers.sort(key=lambda m: m.ms)

    def save(self) -> bool:
        f = self._markers_file()
        if not f:
            return False
        payload = {
            "audio_path": self._audio_path,
            "audio_id": self._audio_id,
            "markers": [{"name": m.name, "ms": int(m.ms)} for m in self._markers],
        }
        return save_json(f, payload)

    def list(self) -> List[Marker]:
        return list(self._markers)

    def add(self, name: str, ms: int):
        self._markers.append(Marker(name, int(ms)))
        self._markers.sort(key=lambda m: m.ms)
        self.save()

    def remove_at(self, idx: int):
        if 0 <= idx < len(self._markers):
            self._markers.pop(idx)
            self.save()

    def nearest_before(self, ms: int) -> Optional[Marker]:
        prev = [m for m in self._markers if m.ms < ms]
        return prev[-1] if prev else None

    def nearest_after(self, ms: int) -> Optional[Marker]:
        nxt = [m for m in self._markers if m.ms > ms]
        return nxt[0] if nxt else None

    def set_loop(self, start_ms: Optional[int], end_ms: Optional[int]):
        self.loop_start = start_ms
        self.loop_end = end_ms
        self.loop_enabled = (
            start_ms is not None and end_ms is not None and int(start_ms) < int(end_ms)
        )

    def should_loop(self, current_ms: int) -> Optional[int]:
        if not self.loop_enabled or self.loop_start is None or self.loop_end is None:
            return None
        if current_ms >= self.loop_end:
            return self.loop_start
        return None
