# Steam Advisor Pro

Steam Advisor Pro is a storage management utility designed to help you optimize your gaming experience by intelligently managing where your Steam games are installed.

As the number of games grow in size, managing limited SSD space becomes a chore. Often your SSD is your C: or boot drive and has limited room for all your games. You have a choice, delete games you're not often playing, something you do not really want to do especially if you have a slow internet connection or you are have metered bandwidth. The other option is to move the games to a second larger, slower, and cheaper HDD. Now you have to deal with a game that may not run as well. 

This program scans your Steam libraries across two different drives (typically a fast SSD and a large HDD) and uses a scoring algorithm to recommend which games should be moved to faster storage and which can be safely archived to a mechanical drive. The program finds the games you want to play without constant micro-stutters and will move them back to your SSD.

---

## 🚀 Features

- **Smart Recommendations**: A scoring algorithm based on Priority, Recency, Playtime, and Game Size — with user-adjustable weights.
- **Library Management**: Safely move games between HDD and SSD while maintaining Steam library integrity.
- **Disk Space Monitoring**: Real-time display of drive space and boot drive protection.
- **Boot Reserve Protection**: Configurable safety margin (default 15%) to prevent your system drive from running out of space.
- **Steam API Integration**: Fetch accurate playtime data directly from Steam servers.
- **Folder Size Scanning**: Calculate and cache game installation sizes to identify storage hogs.
- **Safe File Transfers**: Games are staged in a temporary directory before replacing the destination — no partial moves left behind on failure.

---

## 🛠️ Getting Started

### Prerequisites (If you download the code)
- **Python 3.10+** with the following packages: `vdf`, `requests`
  ```
  pip install vdf requests
  ```
- **Close Steam**: Steam must be completely closed before running this application.
- **Admin Permissions**: Ensure the application folder is writable (config is saved alongside the script).

### Running the App
```
python SteamAdvisorPro.py
```

### Initial Configuration
On first launch you will be prompted to configure your environment:
- **HDD Steam Path**: Browse to your HDD Steam library root (e.g. `D:\SteamLibrary`)
- **SSD Steam Path**: Browse to your SSD Steam library root (e.g. `C:\SteamLibrary`)
- **Steam API Key** *(Optional)*: Get your key at [steamcommunity.com/dev/apikey](https://steamcommunity.com/dev/apikey)
- **SteamID64** *(Optional)*: Your 17-digit Steam ID (visible in your profile URL)

API and SteamID together enable live per-game playtime lookups. Without them, playtime is read from local manifest files (marked with `*` in the table).

Configuration is saved to `steam_advisor_config.json` alongside the script. **Do not share this file** — it contains your API key.

---

## 📊 Scoring Algorithm

The recommendation score is calculated from four weighted components (each configurable 1–5 via the **Weights** button):

| Component | Description |
|-----------|-------------|
| **Priority** | Your personal 1–5 importance rating for the game |
| **Recency** | How recently played, weighted over the last 90 days |
| **Playtime** | Total hours relative to your most-played title |
| **Size** | Install size — larger games benefit more from SSD speeds |

Thresholds for "Promote to SSD" and "Demote to HDD" scale dynamically with your weight settings.

---

## 🎮 Interface Guide

### Toolbar Controls

| Button | Description |
|--------|-------------|
| **Move Selected** | Move highlighted games between drives (runs a disk space preflight check) |
| **Get Recommendations** | Open the scored promote/demote candidate list |
| **Weights** | Adjust algorithm weights (1–5) for each scoring component |
| **Edit Priority** | Assign a 1–5 importance rating to selected games |
| **Refresh** | Re-scan libraries for changes made outside the app |
| **Settings** | Update drive paths, API key, and SteamID |
| **Hide Not Installed** | Filter out scanned games reporting 0 bytes |

### Game Table Columns

| Column | Description |
|--------|-------------|
| **AppID / Game Name** | Steam metadata |
| **Drive** | Current install location (HDD or SSD) |
| **Priority** | Your assigned rating (default 3) |
| **Last Played** | Date last launched |
| **Playtime** | Hours played; `*` means local data (no API) |
| **Scan** | Click ☐ to measure this game's folder size; click the column header to scan all |
| **Game Size** | Cached folder size; `↻` means a Steam update was detected since last scan |

### Boot Reserve
When a library is on the boot drive, a **Boot Available** indicator and **Boot Reserve %** spinner appear in the toolbar. The app blocks any move that would leave less free space than the reserve threshold.

---

## 🔒 Safety Features

- **Staged Transfers**: Files are copied to a temp directory on the destination drive first. The source is only deleted after a verified, complete copy. A failed copy leaves the source untouched.
- **Boot Drive Guard**: Moves are blocked if they would push free space below the configured reserve.
- **Steam Process Check**: The app refuses to start if `steam.exe` is running, preventing library corruption.
- **Thread-Safe Scanning**: Folder-size scans run in background threads with a lock protecting shared metadata — no race conditions.

---

## 🗂️ Project Structure

```
SteamGameDrive/
├── SteamAdvisorPro.py      # GUI coordinator and entry point
├── utils.py                # Constants and pure helper functions
├── config.py               # Config load/save and path resolution
├── steam_api.py            # Steam Web API and process detection
├── library.py              # Steam manifest (.acf) parsing
├── scanner.py              # Background folder-size scanning
├── mover.py                # Validated, staged game-move operations
└── ui/
    ├── settings_window.py  # Settings and weight Toplevel windows
    └── recommendations.py  # Recommendations Toplevel window
```

---

## 📜 Version History

### 0.0.1B1 — First Public Release
- Modularized codebase: single script split into focused modules (`utils`, `config`, `steam_api`, `library`, `scanner`, `mover`, `ui/`)
- Staged file transfers with automatic rollback on failure (temp-dir copy before source delete)
- Thread-safe metadata map protected by a `threading.Lock`
- All bare `except` clauses replaced with typed catches and `logging` output
- Steam API failure now surfaces a visible warning instead of silently failing
- Division-by-zero guard in move progress calculation
- Malformed Steam manifest files (e.g. non-standard `.acf` syntax) are now skipped with a warning instead of crashing

### 0.0.1A2
- Added game folder size to the weighted scoring algorithm
- Added a weight adjustment GUI for custom recommendations
- Standardized all weight scales to 1–5 with a default of 3
- Dynamic "Promote / Demote" thresholds based on sum of current weights

### 0.0.1A1
- Added Boot Drive detection and available space display
- Added configurable Boot Reserve percentage (default 15%)
- Added visual feedback (red text) for boot space warnings
- Fixed priority input validation (constrained to 1–5)
