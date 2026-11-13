# -*- coding: utf-8 -*-
from __future__ import annotations

import math
from typing import Optional

import numpy as np
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QFontMetrics
from PyQt6.QtWidgets import QWidget


def ms_to_time(ms: int) -> str:
    ms = max(0, int(ms))
    s = ms // 1000
    m = s // 60
    h = m // 60
    s %= 60
    m %= 60
    if h > 0:
        return f"{h:d}:{m:02d}:{s:02d}"
    return f"{m:d}:{s:02d}"


class WaveformWidget(QWidget):
    """
    Audipo-like multi-line waveform that ALWAYS fits the full audio duration
    into the available widget height (no zoom).

    - No zoom controls (user request)
    - No vertical scrolling needed: the waveform is re-flowed to fit.
    - Click to seek
    - Current row highlight + playhead indicator
    """
    clicked = pyqtSignal(int)  # ms
    ensure_visible_requested = pyqtSignal(int, int)  # y_top, y_bottom

    def __init__(self, parent=None):
        super().__init__(parent)
        # mins/maxs are per-point amplitudes in [-1, 1].
        # For progressive loading, missing points are NaN.
        self.mins = np.array([], dtype=np.float32)
        self.maxs = np.array([], dtype=np.float32)
        self.duration_ms = 0
        self.points_per_second = 1

        # visual params (good for 14" laptops)
        self.row_height = 46
        self.row_gap = 10
        self.left_gutter = 86
        self.right_pad = 12
        self.top_pad = 10
        self.bottom_pad = 10

        self.playhead_ms = 0
        self._last_rows: Optional[int] = None
        self._last_follow_row: Optional[int] = None

        self.setMinimumWidth(900)
        self.setMinimumHeight(350)

    def set_waveform(self, mins: np.ndarray, maxs: np.ndarray, duration_ms: int, points_per_second: int):
        self.mins = mins if mins is not None else np.array([], dtype=np.float32)
        self.maxs = maxs if maxs is not None else np.array([], dtype=np.float32)
        self.duration_ms = int(duration_ms or 0)
        self.points_per_second = max(1, int(points_per_second or 1))
        self.update()

    def clear(self):
        self.mins = np.array([], dtype=np.float32)
        self.maxs = np.array([], dtype=np.float32)
        self.duration_ms = 0
        self.points_per_second = 0
        self.update()

    def init_placeholder(self, duration_ms: int, points_per_second: int, total_points: int):
        """Initialize buffers for progressive loading.

        Missing points are represented by NaN.
        """
        self.duration_ms = int(duration_ms)
        self.points_per_second = int(points_per_second)
        tp = max(0, int(total_points))
        self.mins = np.full((tp,), np.nan, dtype=np.float32)
        self.maxs = np.full((tp,), np.nan, dtype=np.float32)
        self.update()

    def update_segment(self, start_idx: int, mins: np.ndarray, maxs: np.ndarray):
        """Fill a segment [start_idx, start_idx+len(mins)) with computed data."""
        if self.mins.size == 0 or self.maxs.size == 0:
            return
        s = max(0, int(start_idx))
        e = min(self.mins.size, s + int(len(mins)))
        if e <= s:
            return
        self.mins[s:e] = mins[: e - s]
        self.maxs[s:e] = maxs[: e - s]
        self.update()

    # (duplicate helper methods removed)

    def set_playhead(self, ms: int, request_ensure_visible: bool = False):
        self.playhead_ms = int(ms)

        # Ask the ScrollArea to keep the current row visible (Audipo-like follow).
        # The parent decides whether to follow (checkbox). We only emit when requested.
        if request_ensure_visible:
            rows = self._rows_visible()
            if rows > 0 and self.duration_ms > 0:
                row_ms = self._row_ms(rows)
                row_idx = int(min(rows - 1, max(0, self.playhead_ms // row_ms)))
                if self._last_follow_row != row_idx:
                    self._last_follow_row = row_idx
                    row_full = self.row_height + self.row_gap
                    y_top = int(self.top_pad + row_idx * row_full)
                    y_bottom = int(y_top + self.row_height)
                    self.ensure_visible_requested.emit(y_top, y_bottom)

        self.update()

    def _rows_visible(self) -> int:
        h = max(1, self.height() - self.top_pad - self.bottom_pad)
        row_full = self.row_height + self.row_gap
        rows = max(1, (h + self.row_gap) // row_full)
        # a sensible range: too many rows wastes space, too few reduces readability
        return int(max(4, min(18, rows)))

    def _row_ms(self, rows: int) -> int:
        if self.duration_ms <= 0:
            return 60_000
        return int(math.ceil(self.duration_ms / float(rows)))

    def sizeHint(self):
        return QSize(max(900, self.minimumWidth()), max(350, self.minimumHeight()))

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self.duration_ms <= 0 or self.mins.size == 0:
            return

        x = int(event.position().x())
        y = int(event.position().y())

        rows = self._rows_visible()
        row_full = self.row_height + self.row_gap
        # map y to row index (clamped)
        row_idx = int((y - self.top_pad) // row_full)
        row_idx = max(0, min(rows - 1, row_idx))

        row_ms = self._row_ms(rows)
        row_start_ms = row_idx * row_ms

        waveform_x0 = self.left_gutter
        waveform_w = max(10, self.width() - waveform_x0 - self.right_pad)

        if x < waveform_x0:
            ms = row_start_ms
        else:
            rel = min(1.0, max(0.0, (x - waveform_x0) / waveform_w))
            ms = row_start_ms + int(rel * row_ms)

        ms = max(0, min(self.duration_ms, ms))
        self.clicked.emit(ms)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().base())

        if self.duration_ms <= 0 or self.mins.size == 0 or self.maxs.size == 0:
            painter.end()
            return

        rows = self._rows_visible()
        row_ms = self._row_ms(rows)

        fm = QFontMetrics(painter.font())
        text_pen = QPen(self.palette().text().color())
        border_pen = QPen(self.palette().mid().color())
        wave_pen = QPen(self.palette().text().color())
        wave_pen.setWidth(1)

        played_brush = self.palette().highlight()
        current_row_brush = self.palette().alternateBase()

        waveform_x0 = self.left_gutter
        waveform_w = max(10, self.width() - waveform_x0 - self.right_pad)

        total_pts = int(self.mins.size)
        pps = float(self.points_per_second)

        # which row contains playhead?
        current_row = int(self.playhead_ms // row_ms) if row_ms > 0 else 0
        current_row = max(0, min(rows - 1, current_row))

        for r in range(rows):
            y0 = self.top_pad + r * (self.row_height + self.row_gap)
            rect_x = waveform_x0
            rect_y = y0
            rect_h = self.row_height
            mid = rect_y + rect_h // 2

            row_start_ms = r * row_ms
            row_end_ms = min(self.duration_ms, row_start_ms + row_ms)

            # left label
            painter.setPen(text_pen)
            painter.drawText(8, rect_y + fm.ascent() + 6, ms_to_time(row_start_ms))

            # background for current row
            if r == current_row:
                painter.fillRect(rect_x, rect_y, waveform_w, rect_h, current_row_brush)

            # border
            painter.setPen(border_pen)
            painter.drawRoundedRect(rect_x, rect_y, waveform_w, rect_h, 8, 8)

            # played region in this row
            if self.playhead_ms > row_start_ms:
                played_ms_in_row = min(row_ms, max(0, self.playhead_ms - row_start_ms))
                played_w = int((played_ms_in_row / float(row_ms)) * waveform_w) if row_ms > 0 else 0
                painter.fillRect(rect_x, rect_y, played_w, rect_h, played_brush)

            # indices for this row
            start_s = row_start_ms / 1000.0
            end_s = row_end_ms / 1000.0
            start_pt = int(start_s * pps)
            end_pt = int(end_s * pps)

            start_pt = max(0, min(total_pts, start_pt))
            end_pt = max(0, min(total_pts, end_pt))

            if end_pt <= start_pt + 1:
                continue

            row_pts = end_pt - start_pt
            step = waveform_w / float(row_pts)

            amp = (rect_h / 2) - 6
            painter.setPen(wave_pen)
            for i in range(row_pts):
                x = rect_x + int(i * step)
                idx = start_pt + i
                if idx >= total_pts:
                    break
                if np.isnan(self.mins[idx]) or np.isnan(self.maxs[idx]):
                    # Not computed yet.
                    continue
                y_top = int(mid - (self.maxs[idx] * amp))
                y_bot = int(mid - (self.mins[idx] * amp))
                painter.drawLine(x, y_top, x, y_bot)

            # playhead in this row
            if row_start_ms <= self.playhead_ms <= row_end_ms:
                rel = (self.playhead_ms - row_start_ms) / float(row_ms) if row_ms > 0 else 0.0
                phx = rect_x + int(rel * waveform_w)
                ph_pen = QPen(Qt.GlobalColor.white)
                ph_pen.setWidth(3)
                painter.setPen(ph_pen)
                painter.drawLine(phx, rect_y + 2, phx, rect_y + rect_h - 2)

        painter.end()
