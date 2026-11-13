# -*- coding: utf-8 -*-
from __future__ import annotations
from PyQt6.QtCore import QSettings

class AppSettings:
    def __init__(self):
        self.s = QSettings("Audinux", "Audinux")

    def get(self, key: str, default=None):
        return self.s.value(key, default)

    def set(self, key: str, value):
        self.s.setValue(key, value)

    def last_dir(self) -> str:
        return str(self.get("last_dir", ""))

    def set_last_dir(self, path: str):
        self.set("last_dir", path)

    def last_rate(self) -> float:
        return float(self.get("last_rate", 1.0))

    def set_last_rate(self, r: float):
        self.set("last_rate", r)


    # Waveform display zoom preset index (0=most zoomed-in, 2=fit default).
    def waveform_zoom_index(self) -> int:
        try:
            return int(self.get('waveform_zoom_index', 2))
        except Exception:
            return 2

    def set_waveform_zoom_index(self, idx: int):
        self.set('waveform_zoom_index', int(idx))

    # Backward-compat: older versions stored a fixed ms-per-row.
    # Kept here so upgrades don't break settings, but the new widget uses fit+zoom_index.
    def waveform_row_ms(self) -> int:
        return int(self.get('waveform_row_ms', 180000))

    def set_waveform_row_ms(self, ms: int):
        self.set('waveform_row_ms', int(ms))