# Litio Optionless

Modern PyQt6 desktop configurator and low-latency background daemon for multi-button wireless mice on Linux (built on top of `logiops` / `logid`, `evdev`, and `pynput`).

## Features
- **Interactive Vector Device View:** Clickable button callouts with automatic device detection and live battery/connection status.
- **Smooth Proportional 4-Way Gestures:** Hold the thumb gesture button and move the mouse to smoothly adjust display brightness, volume (with native desktop OSD), or trigger custom shortcuts.
- **Application-Specific Profiles:** Automatic `WM_CLASS` window detection, one-click window class picker, profile duplication, and `.json` import/export (`YYYYMMDD_litio_<profile>.json`).
- **Pointer & Scroll Tuning:** Live DPI slider (`400`–`4000 DPI`), SmartShift threshold control, scroll inversion, and native horizontal thumbwheel pass-through (`divert: false`).

## Quick Install (Debian / Ubuntu / Linux Mint)
```bash
git clone https://github.coms0me1sp3c14l/litio-optionless.git
cd litio-optionless
./install.sh
```

## Disclaimer
Litio Optionless is an independent open-source project and is not affiliated with, endorsed by, or sponsored by Logitech International S.A. All product names and trademarks belong to their respective owners.
