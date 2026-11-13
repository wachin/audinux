# Audinux

Audinux is a **long-audio player** inspired by **Audipo (Android)**.

It is built for **minutes to multi-hour files** (1–6+ hours): Bible audiobooks, sermons, lectures, podcasts.

## Features

- **Audipo-style multi-line waveform**: the entire audio fits on screen as stacked rows (no vertical scrolling in the default “fit” view)
- **Progressive waveform loading** for very long files: playback starts immediately; the waveform appears and fills in gradually
- **Fast waveform for long files** (coarse overview like Audipo) with on-disk cache (second open is faster)
- **Markers** with names (saved per audio file)
- **VLC playback** (plays the original audio file, no quality loss)
- **Internationalization-ready (Qt .ts workflow)**: UI strings are prepared for translation

## Requirements (Debian / Ubuntu)

Recommended system packages:

```bash
sudo apt update
sudo apt install -y python3-pyqt6 python3-pyqt6.qtsvg vlc ffmpeg python3-vlc
```

### python3-vlc

The `python3-vlc` package is available in the Debian/Ubuntu repositories and provides the VLC Python bindings. This avoids the need to install `python-vlc` via pip. Install it alongside the other recommended system packages above.

### Optional (recommended): audiowaveform

To generate waveforms much faster for very long MP3 files, install **audiowaveform**.

Audinux will automatically use `audiowaveform` when found in `PATH`, and fall back to `ffmpeg` otherwise.

## Run (Linux)

From the project folder:

```bash
python3 -m audinux
```

### Without pip

If you prefer not to use pip, you can install the required dependencies via the system package manager:

```bash
sudo apt install -y python3-pyqt6 python3-pyqt6.qtsvg vlc ffmpeg python3-vlc
```

`numpy` is also available as `python3-numpy`, so the command above is all that is needed.

## Development install (Linux editable)

Create a venv that can see system packages (PyQt6, VLC bindings installed via apt):

```bash
python3 -m venv .venv --system-site-packages
source .venv/bin/activate
```

Install Audinux in editable mode **without pulling PyQt6 from PyPI**:

```bash
pip install -e . --no-deps
```

Install the remaining dependency from apt:

```bash
sudo apt install -y python3-numpy
```

---

## Windows 10

Audinux works on Windows 10. Playback uses **VLC** (libVLC), so VLC must be installed.

### 1) Install prerequisites

1. **Install Python 3.11+ (64-bit recommended)**  
   During installation, check **“Add Python to PATH”**.

2. **Install VLC (VideoLAN)**  
   Install the normal VLC Windows build. Audinux relies on VLC’s `libvlc.dll` and plugins.

3. (Optional) Install **FFmpeg** if you want the waveform fallback to work when `audiowaveform` is not present.  
   - Easiest: install FFmpeg and ensure `ffmpeg.exe` is on `PATH`.

### 2) Quick run (no venv)

In PowerShell, inside the project folder:

```powershell
pip install PyQt6 numpy python-vlc
python -m audinux
```

### 3) Developer run (with venv) — recommended for development

```powershell
python -m venv .venv
.\.venv\Scriptsctivate
pip install -U pip
pip install PyQt6 numpy python-vlc
python -m audinux
```

### VLC message in PowerShell

You may see something like:

```
main input error: ES_OUT_SET_(GROUP_)PCR is called too late (pts_delay increased to 1000 ms)
```

This is a **VLC timing warning** (PCR/PTS sync). It’s usually harmless if audio plays normally.  
It can happen on slower machines, with certain MP3 encodings, or when the system is under load.  
If you do notice stutter, try closing heavy apps, or use a different MP3 encoder/bitrate.

---

## Packaging (PyInstaller on Windows)

You can package Audinux into a folder containing an `.exe`.

### Build

From PowerShell in the project folder:

```powershell
python -m pip install -U pip
pip install pyinstaller
pyinstaller --noconfirm --windowed --name Audinux -p . audinux\__main__.py
```

Result:

- `dist\Audinux\Audinux.exe`

### VLC requirement

For simplest distribution, **require users to install VLC** (and mention it in your installer/README).  
If you want a fully portable build, you must bundle VLC’s `libvlc.dll` and `plugins\` folder next to the `.exe`.

### Bundling extra tools (optional)

If you want the waveform fallback to work everywhere, ship `ffmpeg.exe` alongside the `.exe` and make Audinux look for it
next to the executable first (then `PATH`).

---

## Notes about performance

- For long files (hours), Audinux intentionally generates a **coarse waveform overview** (like Audipo) so it appears quickly.
- The waveform is cached in the user cache directory. The **second open** of the same file should be much faster.

## Packaging layout (Linux)

This project is structured to install cleanly on Linux, similar to OpenLP:

- Python package: `audinux/`
- Desktop file & icon: `packaging/`
- Translations: `i18n/`

## License

See `LICENSE`.
