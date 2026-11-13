# Changelog

## 0.6.2 - 2026-11-13
- Application icon, installed at the standard hicolor sizes (16 to 512 px plus a scalable SVG) and used for the window and taskbar
- Reworked desktop entry: generic name, keywords, Spanish name and comment, audio MIME types
- Files given on the command line are opened on startup, so the desktop entry's `Exec=audinux %f` works
- License metadata corrected to GPL-3.0-only
- Debian packaging (`debian/`), man page and autopkgtest

## 0.6.1 - 2026-02-12
- Progressive waveform loading for multi-hour audio (waveform fills in gradually while playback starts immediately)
- Audipo-like “fit” waveform overview for faster initial rendering on long tracks
- Resizable UI panels (splitters) for waveform vs playlist/markers
- Windows 10 support notes and workflow (PyQt6 + VLC/libVLC)

## 0.6.0 - 2026-01-21
- Multi-line waveform (Audipo-style) + auto-follow playhead
- Highlight current row (Audipo pro-like)
- English UI + Qt i18n scaffolding
