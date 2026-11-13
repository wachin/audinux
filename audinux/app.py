# -*- coding: utf-8 -*-
from __future__ import annotations
import os
import sys
from pathlib import Path

import numpy as np

from PyQt6.QtCore import Qt, QTimer, QByteArray
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFileDialog, QSlider, QListWidget, QGroupBox, QLineEdit, QMessageBox,
    QScrollArea, QCheckBox, QSplitter
)

from .settings import AppSettings
from .audio import AudioProcessor
from .markers import MarkersManager
from .playlist import Playlist
from .waveform import WaveformWidget, ms_to_time
from .i18n import tr, load_translators

CTX = "Audinux"


def app_icon() -> QIcon:
    """Locate the Audinux icon in source, frozen and installed layouts."""
    roots = []
    frozen = getattr(sys, "_MEIPASS", None)
    if frozen:
        roots.append(Path(frozen) / "packaging")
    # Running from a source checkout: <repo>/packaging
    roots.append(Path(__file__).resolve().parent.parent / "packaging")
    # Installed data files (pip / system package)
    roots.append(Path(sys.prefix) / "share" / "icons" / "hicolor" / "scalable" / "apps")
    roots.append(Path("/usr/share/icons/hicolor/scalable/apps"))

    for root in roots:
        for name in ("audinux.svg", "audinux.png"):
            path = root / name
            if path.is_file():
                return QIcon(str(path))

    # Last resort: whatever icon theme is active.
    return QIcon.fromTheme("audinux")


class AudioPlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = AppSettings()
        self.audio = AudioProcessor()
        self.markers = MarkersManager()
        self.playlist = Playlist()

        # Waveform resolution is computed dynamically per file based on the
        # available view size (Audipo-like: enough detail to navigate, but fast).
        self._default_rows_target = 12

        self.timer = QTimer(self)
        self.timer.setInterval(200)
        self.timer.timeout.connect(self.on_tick)

        self._build_ui()

        self.rate_slider.setValue(int(self.settings.last_rate() * 100))

    def _build_ui(self):
        self.setWindowTitle(tr(CTX, "Audinux"))

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)

        # Main splitter (left waveform / right panels)
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setHandleWidth(6)
        outer.addWidget(self.main_splitter, 1)

        # Left panel
        left_widget = QWidget()
        left = QVBoxLayout(left_widget)
        self.main_splitter.addWidget(left_widget)

        topbar = QHBoxLayout()
        left.addLayout(topbar)

        self.btn_open = QPushButton(tr(CTX, "Open… (Ctrl+O)"))
        self.btn_open.clicked.connect(self.open_file)
        topbar.addWidget(self.btn_open)

        self.btn_play = QPushButton(tr(CTX, "Play/Pause (Space)"))
        self.btn_play.clicked.connect(self.toggle_play)
        topbar.addWidget(self.btn_play)

        self.btn_stop = QPushButton(tr(CTX, "Stop (S)"))
        self.btn_stop.clicked.connect(self.stop)
        topbar.addWidget(self.btn_stop)

        topbar.addStretch(1)
        self.time_label = QLabel("00:00 / 00:00")
        topbar.addWidget(self.time_label)

        self.follow_chk = QCheckBox(tr(CTX, "Follow"))
        self.follow_chk.setChecked(True)
        topbar.addWidget(self.follow_chk)

        # NOTE: splitter sizing/state restore happens later, after the right splitter is created.

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.waveform = WaveformWidget()
        # zoom disabled
        #         self.waveform._update_geometry()

        self.waveform.clicked.connect(self.seek_ms)
        self.waveform.ensure_visible_requested.connect(self._ensure_wave_row_visible)
        self.scroll.setWidget(self.waveform)
        left.addWidget(self.scroll, 1)

        # Right panel
        right_widget = QWidget()
        right = QVBoxLayout(right_widget)
        self.main_splitter.addWidget(right_widget)

        spd = QHBoxLayout()
        right.addLayout(spd)
        spd.addWidget(QLabel(tr(CTX, "Speed:")))
        self.rate_slider = QSlider(Qt.Orientation.Horizontal)
        self.rate_slider.setRange(50, 200)
        self.rate_slider.setValue(100)
        self.rate_slider.valueChanged.connect(self.on_rate)
        spd.addWidget(self.rate_slider)
        self.rate_label = QLabel("1.00x")
        spd.addWidget(self.rate_label)

        vol = QHBoxLayout()
        right.addLayout(vol)
        vol.addWidget(QLabel(tr(CTX, "Volume:")))
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(70)
        self.vol_slider.valueChanged.connect(self.on_volume)
        vol.addWidget(self.vol_slider)
        self.vol_label = QLabel("70")
        vol.addWidget(self.vol_label)

        # Panels splitter so you can resize the right side areas.
        self.right_splitter = QSplitter(Qt.Orientation.Vertical)
        self.right_splitter.setChildrenCollapsible(False)
        right.addWidget(self.right_splitter, 1)

        # Splitters behavior / initial sizes
        self.main_splitter.setChildrenCollapsible(False)
        # Give more space to the waveform by default.
        self.main_splitter.setStretchFactor(0, 4)
        self.main_splitter.setStretchFactor(1, 1)
        self.right_splitter.setStretchFactor(0, 1)
        self.right_splitter.setStretchFactor(1, 1)

        # Restore last splitter positions
        state_main = self.settings.get("ui/splitter_main")
        if state_main:
            try:
                self.main_splitter.restoreState(state_main)
            except Exception:
                pass
        state_right = self.settings.get("ui/splitter_right")
        if state_right:
            try:
                self.right_splitter.restoreState(state_right)
            except Exception:
                pass

        grp_pl = QGroupBox(tr(CTX, "Playlist"))
        self.right_splitter.addWidget(grp_pl)
        pl_lay = QVBoxLayout(grp_pl)
        self.pl_list = QListWidget()
        self.pl_list.itemDoubleClicked.connect(self.on_playlist_double_click)
        pl_lay.addWidget(self.pl_list)

        pl_btns = QHBoxLayout()
        pl_lay.addLayout(pl_btns)
        self.btn_add = QPushButton(tr(CTX, "Add… (Ctrl+P)"))
        self.btn_add.clicked.connect(self.add_to_playlist)
        self.btn_prev = QPushButton(tr(CTX, "◀◀ Previous"))
        self.btn_prev.clicked.connect(self.prev_track)
        self.btn_next = QPushButton(tr(CTX, "Next ▶▶"))
        self.btn_next.clicked.connect(self.next_track)
        pl_btns.addWidget(self.btn_add)
        pl_btns.addWidget(self.btn_prev)
        pl_btns.addWidget(self.btn_next)

        grp_m = QGroupBox(tr(CTX, "Markers"))
        self.right_splitter.addWidget(grp_m)
        m_lay = QVBoxLayout(grp_m)
        self.mk_list = QListWidget()
        self.mk_list.itemDoubleClicked.connect(self.on_marker_double_click)
        m_lay.addWidget(self.mk_list)

        m_add = QHBoxLayout()
        m_lay.addLayout(m_add)
        self.mk_name = QLineEdit()
        self.mk_name.setPlaceholderText(tr(CTX, "Marker name…"))
        self.btn_add_mk = QPushButton(tr(CTX, "Add (M)"))
        self.btn_add_mk.clicked.connect(self.add_marker)

        self.btn_loop = QPushButton(tr(CTX, "Loop A↔B (L)"))
        self.btn_loop.setCheckable(True)
        self.btn_loop.clicked.connect(self.toggle_loop)

        m_add.addWidget(self.mk_name, 1)
        m_add.addWidget(self.btn_add_mk)
        m_add.addWidget(self.btn_loop)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Space:
            self.toggle_play()
        elif e.key() == Qt.Key.Key_S:
            self.stop()
        elif e.key() == Qt.Key.Key_M:
            self.add_marker()
        elif e.key() == Qt.Key.Key_L:
            self.toggle_loop()
        elif e.key() == Qt.Key.Key_O and e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.open_file()
        elif e.key() == Qt.Key.Key_P and e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.add_to_playlist()
        else:
            super().keyPressEvent(e)

    def open_file(self):
        start = self.settings.last_dir() or os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(
            self, tr(CTX, "Open audio"), start,
            tr(CTX, "Audio") + " (*.mp3 *.wav *.flac *.ogg *.m4a *.aac);;" + tr(CTX, "All files") + " (*)"
        )
        if not path:
            return
        self.settings.set_last_dir(os.path.dirname(path))
        self.load_track(path, add_to_playlist=True)

    def add_to_playlist(self):
        start = self.settings.last_dir() or os.path.expanduser("~")
        paths, _ = QFileDialog.getOpenFileNames(
            self, tr(CTX, "Add audio files"), start,
            tr(CTX, "Audio") + " (*.mp3 *.wav *.flac *.ogg *.m4a *.aac);;" + tr(CTX, "All files") + " (*)"
        )
        if not paths:
            return
        self.settings.set_last_dir(os.path.dirname(paths[0]))
        for p in paths:
            self.playlist.add(p)
            self.pl_list.addItem(os.path.basename(p))
        if self.audio.audio_path is None and self.playlist.current():
            self.load_track(self.playlist.current().path, add_to_playlist=False)

    def on_playlist_double_click(self, item):
        row = self.pl_list.row(item)
        if 0 <= row < len(self.playlist.items):
            self.playlist.index = row
            self.load_track(self.playlist.items[row].path, add_to_playlist=False)

    def prev_track(self):
        it = self.playlist.prev()
        if it:
            self.load_track(it.path, add_to_playlist=False)

    def next_track(self):
        it = self.playlist.next()
        if it:
            self.load_track(it.path, add_to_playlist=False)

    def _compute_wave_pps(self, duration_ms: int) -> int:
        """Compute an Audipo-like pixels-per-second resolution.

        Goal: fast loading for hours-long audio while keeping enough detail
        to navigate. We target roughly (viewport_width * rows) waveform points
        in total across the whole file.
        """
        duration_s = max(1.0, duration_ms / 1000.0)
        view_w = max(200, self.scroll.viewport().width())
        rows = max(6, getattr(self, "_default_rows_target", 12))

        total_points_target = view_w * rows
        pps = int(total_points_target / duration_s)

        # Hard bounds: never below 1, never too high for short files.
        pps = max(1, min(pps, 50))
        return pps

    def load_track(self, path: str, add_to_playlist: bool = False):
        if not self.audio.load(path):
            QMessageBox.warning(self, tr(CTX, "Audinux"), tr(CTX, "Could not open this file."))
            return

        self.setWindowTitle(f"{tr(CTX, 'Audinux')} — {os.path.basename(path)}")
        self.audio.set_volume(self.vol_slider.value())

        self.markers.load_for(path)
        self.refresh_markers()

        # Waveform computation is expensive for hours-long audio.
        # We compute it progressively: you see the first minutes quickly, then
        # the rest appears while you can already listen.
        pps = self._compute_wave_pps(self.audio.duration_ms)

        # Clear waveform immediately (avoids showing previous file content).
        self.waveform.clear()

        def _wf_meta(duration_ms: int, pps_eff: int, total_points: int):
            self.waveform.init_placeholder(duration_ms, pps_eff, total_points)

        def _wf_segment(start_idx: int, mins: np.ndarray, maxs: np.ndarray):
            self.waveform.update_segment(start_idx, mins, maxs)

        def _wf_done():
            # nothing else; we keep the progressively-filled buffers
            return

        wave_w = max(200, self.scroll.viewport().width())
        max_points = int(wave_w * max(6, getattr(self, "_default_rows_target", 12)))
        self.audio.start_waveform_progressive(pps, _wf_meta, _wf_segment, _wf_done, max_points=max_points)

        if add_to_playlist:
            self.playlist.add(path)
            self.pl_list.addItem(os.path.basename(path))
            self.pl_list.setCurrentRow(self.playlist.index)

        self.timer.start()
        self.audio.play()

    def toggle_play(self):
        self.audio.toggle()

    def stop(self):
        self.audio.stop()
        self.timer.stop()
        self.waveform.set_playhead(0, request_ensure_visible=False)

    def seek_ms(self, ms: int):
        self.audio.set_position_ms(ms)
        self.waveform.set_playhead(ms, request_ensure_visible=True)

    def on_rate(self, v: int):
        rate = max(0.5, min(2.0, v / 100.0))
        self.audio.set_rate(rate)
        self.settings.set_last_rate(rate)
        self.rate_label.setText(f"{rate:.2f}x")

    def on_volume(self, v: int):
        self.audio.set_volume(v)
        self.vol_label.setText(str(v))

    def add_marker(self):
        if not self.audio.audio_path:
            return
        ms = self.audio.get_position_ms()
        name = self.mk_name.text().strip() or ms_to_time(ms)
        self.markers.add(name, ms)
        self.mk_name.setText("")
        self.refresh_markers()

    def refresh_markers(self):
        self.mk_list.clear()
        for m in self.markers.list():
            self.mk_list.addItem(f"{m.name} — {ms_to_time(m.ms)}")

    def on_marker_double_click(self, item):
        row = self.mk_list.row(item)
        ms = self.markers.list()[row].ms
        self.seek_ms(ms)

    def toggle_loop(self):
        if not self.audio.audio_path:
            self.btn_loop.setChecked(False)
            return
        if not self.btn_loop.isChecked():
            self.markers.set_loop(None, None)
            return
        cur = self.audio.get_position_ms()
        a = self.markers.nearest_before(cur)
        b = self.markers.nearest_after(cur)
        if not a or not b:
            QMessageBox.information(
                self, tr(CTX, "Audinux"),
                tr(CTX, "To use Loop A↔B, create a marker before and after the current position.")
            )
            self.btn_loop.setChecked(False)
            return
        self.markers.set_loop(a.ms, b.ms)

    def _ensure_wave_row_visible(self, y_top: int, y_bottom: int):
        if hasattr(self, 'follow_chk') and (not self.follow_chk.isChecked()):
            return
        bar = self.scroll.verticalScrollBar()
        view_top = bar.value()
        view_bottom = view_top + self.scroll.viewport().height()
        margin = 20
        if y_top - margin < view_top:
            bar.setValue(max(0, y_top - margin))
        elif y_bottom + margin > view_bottom:
            bar.setValue(max(0, y_bottom + margin - self.scroll.viewport().height()))

    def on_tick(self):
        if not self.audio.audio_path:
            return
        cur = self.audio.get_position_ms()
        dur = max(0, self.audio.duration_ms)
        follow = True
        try:
            follow = bool(getattr(self, "follow_chk").isChecked())
        except Exception:
            pass
        self.waveform.set_playhead(cur, request_ensure_visible=follow)
        self.time_label.setText(f"{ms_to_time(cur)} / {ms_to_time(dur)}")
        loop_to = self.markers.should_loop(cur)
        if loop_to is not None:
            self.seek_ms(loop_to)

    def closeEvent(self, event):
        # Persist splitter positions (useful on laptops)
        try:
            if hasattr(self, "main_splitter"):
                self.settings.set("ui/splitter_main", self.main_splitter.saveState())
            if hasattr(self, "right_splitter"):
                self.settings.set("ui/splitter_right", self.right_splitter.saveState())
        except Exception:
            pass
        super().closeEvent(event)

def run():
    app = QApplication([])
    # Wayland compositors match the window to its .desktop entry for the taskbar.
    app.setDesktopFileName("audinux")
    app.setWindowIcon(app_icon())
    _trs = load_translators(app)
    w = AudioPlayer()
    w.setWindowIcon(app.windowIcon())
    w.resize(1100, 720)
    w.show()
    app.exec()
