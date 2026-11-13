# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import subprocess
import json
import math
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
import vlc
from PyQt6.QtCore import QThread, pyqtSignal

from .utils import audio_id_for, ffprobe_duration_ms
from .xdg import cache_dir, ensure_subdir


@dataclass
class WaveformResult:
    mins: np.ndarray
    maxs: np.ndarray
    duration_ms: int
    points_per_second: int


def _effective_pps(duration_ms: int, requested_pps: int, max_points: int = 15_000) -> int:
    """Choose a low-cost points-per-second that caps the total points for very long files."""
    duration_s = max(0.001, max(0, int(duration_ms)) / 1000.0)
    pps_from_cap = int(round(max_points / duration_s))
    return int(max(1, min(int(requested_pps), max(1, pps_from_cap))))


def _wave_cache_path(audio_path: str, duration_ms: int, requested_pps: int) -> str:
    """Cache path includes the effective points-per-second so we don't mix caches."""
    aid = audio_id_for(audio_path)
    base = ensure_subdir(cache_dir(), "waveforms")
    pps = _effective_pps(duration_ms, requested_pps)
    return str(base / f"{aid}_{pps}pps.npz")


def _load_waveform_cache(audio_path: str, duration_ms: int, requested_pps: int) -> Optional[Tuple[np.ndarray, np.ndarray, int]]:
    p = _wave_cache_path(audio_path, duration_ms, requested_pps)
    if not os.path.exists(p):
        return None
    try:
        data = np.load(p)
        pps = int(data.get("pps", _effective_pps(duration_ms, requested_pps)))
        return (data["mins"], data["maxs"], pps)
    except Exception:
        return None


def _save_waveform_cache(audio_path: str, duration_ms: int, requested_pps: int, mins: np.ndarray, maxs: np.ndarray, pps: int) -> None:
    p = _wave_cache_path(audio_path, duration_ms, requested_pps)
    try:
        np.savez_compressed(p, mins=mins.astype(np.float32), maxs=maxs.astype(np.float32), pps=int(pps))
    except Exception:
        pass



def _which(cmd: str) -> Optional[str]:
    for p in os.environ.get("PATH", "").split(os.pathsep):
        c = os.path.join(p, cmd)
        if os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


def compute_waveform_audiowaveform(
    path: str,
    duration_ms: int,
    requested_pps: int = 60,
    *,
    max_points: int = 15_000
) -> WaveformResult:
    """
    Audipo-like waveform generation using BBC's `audiowaveform` (fast C++).

    We keep it coarse for long files by capping the *total* number of points.
    """
    aw = _which("audiowaveform")
    if aw is None:
        raise RuntimeError("audiowaveform not found")

    pps = _effective_pps(duration_ms, requested_pps, max_points=max_points)

    # Use JSON output (easy to parse). Keep it small: 8-bit.
    base = ensure_subdir(cache_dir(), "waveforms_tmp")
    tmp_json = str(base / f"{audio_id_for(path)}_{pps}pps.json")

    # Generate waveform JSON.
    # -q : quiet
    # --pixels-per-second : coarse control
    # -b 8 : smaller output
    cmd = [aw, "-i", path, "-o", tmp_json, "--pixels-per-second", str(pps), "-b", "8", "-q"]
    subprocess.run(cmd, check=True)

    # Parse JSON: expected "data": [min,max,min,max,...] with 8-bit signed ints.
    with open(tmp_json, "r", encoding="utf-8") as f:
        obj = json.load(f)

    data = obj.get("data", [])
    if not isinstance(data, list) or len(data) < 2:
        raise RuntimeError("Invalid audiowaveform JSON")

    # Convert pairs to float32 in [-1, 1]
    # audiowaveform typically stores min/max per point as signed 8-bit ints.
    n_pairs = len(data) // 2
    mins = np.empty((n_pairs,), dtype=np.float32)
    maxs = np.empty((n_pairs,), dtype=np.float32)

    for i in range(n_pairs):
        a = float(data[2 * i])
        b = float(data[2 * i + 1])
        lo = min(a, b)
        hi = max(a, b)
        mins[i] = lo / 128.0
        maxs[i] = hi / 128.0

    try:
        os.remove(tmp_json)
    except Exception:
        pass

    return WaveformResult(mins=mins, maxs=maxs, duration_ms=int(duration_ms), points_per_second=int(pps))


def compute_waveform_ffmpeg(
    path: str,
    duration_ms: int,
    requested_pps: int = 60,
    *,
    max_points: int = 15_000,
    sample_rate: int = 1000
) -> WaveformResult:
    """
    Fast, low-memory waveform computation for VERY long files.

    Strategy:
      - Get mono PCM from ffmpeg at a low sample rate (default 8kHz)
      - Compute min/max peaks per time-window (pps)
      - Cap total points to max_points (so 6h doesn't explode)

    This matches the "draw once, coarse but useful" behavior you observed in Audipo.
    """
    duration_ms = max(0, int(duration_ms))
    duration_s = max(0.001, duration_ms / 1000.0)

    # Adapt points_per_second so total points stays bounded.
    # For very long files we allow pps to go down to 1 to avoid decoding forever.
    pps = int(max(1, min(int(requested_pps), int(max_points / duration_s))))
    total_points = int(math.ceil(duration_s * pps))

    mins = np.zeros(total_points, dtype=np.float32)
    maxs = np.zeros(total_points, dtype=np.float32)

    # samples per point window
    block = max(1, int(sample_rate / max(1, pps)))

    cmd = [
        "ffmpeg",
        "-hide_banner", "-loglevel", "error",
        "-i", path,
        "-vn",
        "-ac", "1",
        "-ar", str(sample_rate),
        "-f", "s16le",
        "pipe:1",
    ]

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    buf = np.empty(0, dtype=np.int16)
    idx = 0
    try:
        assert proc.stdout is not None
        while True:
            chunk = proc.stdout.read(65536)
            if not chunk:
                break
            arr = np.frombuffer(chunk, dtype=np.int16)
            if arr.size == 0:
                continue
            if buf.size == 0:
                buf = arr
            else:
                buf = np.concatenate([buf, arr])

            # consume full blocks
            while idx < total_points and buf.size >= block:
                w = buf[:block]
                buf = buf[block:]
                mn = float(w.min())
                mx = float(w.max())
                mins[idx] = mn
                maxs[idx] = mx
                idx += 1

            if idx >= total_points:
                break

        # If we ran out early, fill remaining with last value
        if idx > 0 and idx < total_points:
            mins[idx:] = mins[idx - 1]
            maxs[idx:] = maxs[idx - 1]
    finally:
        try:
            proc.stdout and proc.stdout.close()
        except Exception:
            pass
        proc.terminate()
        proc.wait(timeout=2)

    # normalize to [-1, 1] like before
    peak = max(abs(float(mins.min())), abs(float(maxs.max())), 1.0)
    mins /= peak
    maxs /= peak

    return WaveformResult(mins=mins, maxs=maxs, duration_ms=duration_ms, points_per_second=pps)


class WaveformProgressWorker(QThread):
    """Compute waveform progressively and stream segments to the UI.

    The first segment arrives quickly, then the rest fills in while audio plays.
    """

    meta = pyqtSignal(int, int, int)  # duration_ms, pps, total_points
    segment = pyqtSignal(int, object, object)  # start_idx, mins(np.ndarray), maxs(np.ndarray)
    done = pyqtSignal()

    def __init__(self, path: str, duration_ms: int, requested_pps: int, max_points: int = 15_000, sample_rate: int = 1000):
        super().__init__()
        self.path = path
        self.duration_ms = int(duration_ms)
        self.requested_pps = int(requested_pps)
        self.max_points = int(max_points)
        self.sample_rate = int(sample_rate)
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        duration_ms = max(0, int(self.duration_ms))
        duration_s = max(0.001, duration_ms / 1000.0)
        pps = _effective_pps(duration_ms, self.requested_pps, max_points=self.max_points)
        total_points = int(math.ceil(duration_s * pps))
        self.meta.emit(duration_ms, int(pps), int(total_points))

        # Cache first (full waveform)
        cached = _load_waveform_cache(self.path, duration_ms, self.requested_pps)
        if cached is not None:
            mins, maxs, pps_cached = cached
            self.segment.emit(0, mins, maxs)
            self.done.emit()
            return

        # Progressive computation using a single ffmpeg decode pass.
        block = max(1, int(self.sample_rate / max(1, pps)))

        cmd = [
            "ffmpeg",
            "-hide_banner", "-loglevel", "error",
            "-i", self.path,
            "-vn",
            "-ac", "1",
            "-ar", str(self.sample_rate),
            "-f", "s16le",
            "pipe:1",
        ]

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        buf = np.empty(0, dtype=np.int16)
        idx = 0
        last_emit = 0
        # Emit frequently at the beginning; then in bigger chunks.
        emit_every = max(200, int(pps * 10))  # ~10 seconds worth, but at least 200 points

        mins_all = np.empty((total_points,), dtype=np.float32)
        maxs_all = np.empty((total_points,), dtype=np.float32)

        try:
            assert proc.stdout is not None
            while not self._stop:
                chunk = proc.stdout.read(65536)
                if not chunk:
                    break
                arr = np.frombuffer(chunk, dtype=np.int16)
                if arr.size == 0:
                    continue
                buf = arr if buf.size == 0 else np.concatenate([buf, arr])

                while idx < total_points and buf.size >= block:
                    w = buf[:block]
                    buf = buf[block:]
                    mins_all[idx] = float(w.min())
                    maxs_all[idx] = float(w.max())
                    idx += 1

                    if idx - last_emit >= emit_every:
                        s = last_emit
                        e = idx
                        # normalize this segment using int16 full-scale (fast, stable)
                        seg_min = mins_all[s:e] / 32768.0
                        seg_max = maxs_all[s:e] / 32768.0
                        self.segment.emit(s, seg_min.astype(np.float32, copy=False), seg_max.astype(np.float32, copy=False))
                        last_emit = idx

                if idx >= total_points:
                    break

            # Flush last partial segment
            if not self._stop and idx > last_emit:
                s = last_emit
                e = idx
                seg_min = mins_all[s:e] / 32768.0
                seg_max = maxs_all[s:e] / 32768.0
                self.segment.emit(s, seg_min.astype(np.float32, copy=False), seg_max.astype(np.float32, copy=False))

            # If ended early, repeat last value
            if not self._stop and idx > 0 and idx < total_points:
                mins_all[idx:] = mins_all[idx - 1]
                maxs_all[idx:] = maxs_all[idx - 1]
                s = idx
                e = total_points
                self.segment.emit(s, (mins_all[s:e] / 32768.0).astype(np.float32, copy=False),
                                  (maxs_all[s:e] / 32768.0).astype(np.float32, copy=False))

            if not self._stop:
                # Save full cache (normalized)
                _save_waveform_cache(self.path, duration_ms, self.requested_pps,
                                     (mins_all / 32768.0).astype(np.float32),
                                     (maxs_all / 32768.0).astype(np.float32),
                                     int(pps))

        finally:
            try:
                proc.stdout and proc.stdout.close()
            except Exception:
                pass
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except Exception:
                pass

        self.done.emit()

class AudioProcessor:
    def __init__(self):
        self.instance = vlc.Instance(["--no-video"])
        self.player = self.instance.media_player_new()
        self.media: Optional[vlc.Media] = None
        self.audio_path: Optional[str] = None
        self.duration_ms: int = 0
        self.waveform_cache: Tuple[np.ndarray, np.ndarray] = (np.array([], dtype=np.float32), np.array([], dtype=np.float32))
        self._wf_worker: Optional[WaveformProgressWorker] = None

    def load(self, path: str) -> bool:
        if not os.path.exists(path):
            return False
        self.audio_path = path
        self.media = self.instance.media_new(path)
        self.player.set_media(self.media)

        # Get duration quickly (does NOT decode the whole file)
        self.duration_ms = ffprobe_duration_ms(path)

        # Prime VLC
        self.player.play()
        self.player.pause()
        return True

    def play(self): self.player.play()
    def pause(self): self.player.pause()
    def stop(self): self.player.stop()

    def toggle(self):
        if self.player.is_playing():
            self.pause()
        else:
            self.play()

    def set_position_ms(self, ms: int):
        if self.duration_ms <= 0:
            return
        ms = max(0, min(self.duration_ms, int(ms)))
        self.player.set_time(ms)

    def get_position_ms(self) -> int:
        return int(self.player.get_time() or 0)

    def set_rate(self, rate: float):
        self.player.set_rate(float(rate))

    def get_rate(self) -> float:
        return float(self.player.get_rate() or 1.0)

    def set_volume(self, vol: int):
        self.player.audio_set_volume(int(vol))

    def get_volume(self) -> int:
        return int(self.player.audio_get_volume() or 0)

    def start_waveform_progressive(
        self,
        requested_pps: int,
        on_meta,
        on_segment,
        on_done,
        *,
        max_points: int = 15_000,
    ):
        """Compute waveform progressively in a background thread.

        - `on_meta(duration_ms, pps, total_points)` is called once.
        - `on_segment(start_idx, mins, maxs)` is called many times.
        - `on_done()` is called at the end.
        """
        if not self.audio_path:
            return
        if self._wf_worker and self._wf_worker.isRunning():
            try:
                self._wf_worker.stop()
            except Exception:
                pass
            self._wf_worker.quit()
            self._wf_worker.wait(2000)

        self._wf_worker = WaveformProgressWorker(self.audio_path, self.duration_ms, requested_pps, max_points=max_points)
        self._wf_worker.meta.connect(on_meta)
        self._wf_worker.segment.connect(on_segment)
        self._wf_worker.done.connect(on_done)
        self._wf_worker.start()
