# KeepAwake

> A lightweight Windows utility that prevents your PC from sleeping, locking, or showing a screensaver — with smart human-like simulation, scheduled hours, and system tray integration.

---

## Features

- **Multiple prevention methods** — F15 key (silent default), F16 key, Scroll Lock, or 1-pixel mouse nudge
- **Smart AFK simulation** — periodically pauses activity to mimic natural usage patterns, so you don't appear "always online"
- **Scheduled hours** — automatically runs only between set times (e.g. 09:00–17:00)
- **Global hotkeys** — toggle prevention or hide the window without clicking
- **System tray** — runs silently in the background; right-click the tray icon to show or quit
- **Session statistics** — tracks total actions and uptime, stored locally in SQLite
- **Dark / light theme** — switch between themes from within the app
- **Auto-start on launch** — optionally start prevention automatically when the app opens
- **CPU & memory monitor** — live performance stats in the dashboard

---

## Requirements

- Windows 10 / 11
- Python 3.8 or newer

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/sokiicz/KeepAwake.git
cd KeepAwake
```

### 2. Install dependencies

```bash
pip install customtkinter pystray pillow pynput psutil
```

Or let the launcher handle it automatically (see below).

---

## Running

### Option A — Double-click launcher (recommended)

Double-click **`START_Fixed_KeepAwake_Pro.bat`**

The launcher will:
1. Verify and install any missing dependencies
2. Start the app silently in the background (no console window)
3. Place an icon in your system tray

### Option B — Run directly with Python

```bash
pythonw keepawake_pro.py
```

> Use `pythonw` (not `python`) to suppress the console window on Windows.

---

## Usage

| Action | How |
|--------|-----|
| Start / stop prevention | Click the button on the dashboard, or press **Ctrl+Alt+K** |
| Show / hide window | Press **Ctrl+Alt+H**, or right-click the tray icon |
| Quit | Right-click the tray icon → Quit |

---

## Settings

Open the **Settings** tab to configure:

| Setting | Description |
|---------|-------------|
| **Interval** | Seconds between each prevention action (default: 59s) |
| **Prevention method** | F15 key · F16 key · Scroll Lock · Mouse nudge |
| **Auto-start** | Begin prevention automatically when the app launches |
| **Smart AFK** | Periodically simulate being away to appear more natural |
| **AFK duration** | Min/max seconds for each AFK simulation period |
| **AFK probability** | Chance (%) of triggering AFK simulation after inactivity |
| **Scheduled hours** | Only run prevention between two times (24h format) |

---

## Global Hotkeys

| Hotkey | Action |
|--------|--------|
| `Ctrl + Alt + K` | Toggle prevention on / off |
| `Ctrl + Alt + H` | Show / hide the main window |

Hotkeys work even when the window is hidden or minimised to tray.

---

## Smart AFK

Smart AFK makes KeepAwake behave more like a real user:

- After 5 minutes of steady prevention actions, there's a configurable chance (default 25%) that KeepAwake will pause for 30–120 seconds
- During this pause, no keypress or mouse action is sent — simulating you stepping away briefly
- After the pause, normal prevention resumes automatically
- Interval timing is randomised slightly to avoid predictable patterns

---

## Data & Logs

All data is stored in your home directory:

```
~/.keepawake_pro/
├── config.json        # saved settings
├── statistics.db      # session history (SQLite)
└── logs/              # timestamped log files
```

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `customtkinter` | Modern dark/light GUI framework |
| `pystray` | System tray icon |
| `pillow` | Tray icon image rendering |
| `pynput` | Global hotkeys & keyboard/mouse control |
| `psutil` | CPU & memory monitoring |

---

## License

MIT — free to use, modify, and distribute.
