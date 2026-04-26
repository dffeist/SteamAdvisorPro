# Steam Advisor Pro — Release Notes

---

## 0.0.1B1 — First Public Release

### Overview
Beta 1.0 is the first release prepared for public distribution on GitHub. The primary focus of this release is code quality, reliability, and safety. No new user-facing features were added; all changes improve stability and maintainability.

---

### 🗂️ Modular Codebase
The original single-file script (~850 lines) has been split into focused, independently maintainable modules:

| Module | Responsibility |
|--------|----------------|
| `utils.py` | Constants and pure helper functions (`format_gb`, `calculate_folder_size`, `score_games`) |
| `config.py` | Config load/save, path resolution, boot-drive detection |
| `steam_api.py` | Steam Web API playtime fetch and `steam.exe` process check |
| `library.py` | Steam manifest (`.acf`) parsing into game data dicts |
| `scanner.py` | Background folder-size scanning with thread-safe metadata updates |
| `mover.py` | Disk-space validation and staged game-move operations |
| `ui/settings_window.py` | Settings and weight Toplevel windows |
| `ui/recommendations.py` | Recommendations Toplevel window |
| `SteamAdvisorPro.py` | GUI coordinator and `tkinter` entry point |

---

### 🔒 Reliability & Safety Fixes

**Staged File Transfers with Rollback**
Files are now copied into a temporary directory on the destination drive first. The source is deleted only after the full copy succeeds and the temp directory is renamed to its final location. Any `OSError` mid-copy removes the partial temp directory and leaves the source intact — no data loss on failure.

**Thread-Safe Metadata**
All reads and writes to the shared `metadata_map` (used by background scan threads) are now protected by a `threading.Lock`. Previously, concurrent reads from the UI thread and writes from scan threads could corrupt metadata silently.

**Typed Exception Handling + Logging**
All bare `except:` and `except Exception: pass` clauses have been replaced with typed catches (`OSError`, `json.JSONDecodeError`, `requests.RequestException`, etc.) and `logging.warning()` calls. Errors are now visible in the console rather than disappearing silently.

**Steam API Warning on Failure**
API fetch failures now surface a warning dialog to the user. Previously, a network error or bad API key was silently swallowed — users had no indication their playtime data was stale.

**Division-by-Zero Guard**
The move-progress percentage calculation is now guarded against a zero total size: `pct = (copied / total_size) * 100 if total_size > 0 else 0`.

**Malformed Manifest Handling**
Steam `.acf` manifest files with non-standard syntax (e.g. `appmanifest_730.acf` containing `MENUProperty` lines) previously caused an unhandled `SyntaxError` that crashed the app on startup. These files are now caught and skipped with a warning.

---

### ⚙️ Internal Improvements

- All magic numbers extracted to named constants (`GB_BYTES`, `BOOT_RESERVE_MIN_PCT`, `RECENCY_DECAY_DAYS`, etc.)
- Default config and default weights defined once (`DEFAULT_CONFIG`, `DEFAULT_WEIGHTS`) — previously duplicated 5+ times
- Pure business logic functions (`score_games`, `calculate_folder_size`, `validate_move`) are now stateless module-level functions, enabling future unit testing without a GUI
- `config.py` functions raise exceptions; the GUI decides what dialog to show — clean separation between logic and presentation

---

### 📦 How to Install

1. Ensure **Steam is closed**.
2. Clone or download the repository.
3. Install dependencies:
   ```
   pip install vdf requests
   ```
4. Run:
   ```
   python SteamAdvisorPro.py
   ```
5. Complete the first-run setup wizard (drive paths, optional API key and SteamID).

Your `steam_advisor_config.json` is created in the same folder as the script. This file contains your Steam API key — **do not commit or share it**. It is listed in `.gitignore`.

---

## 0.0.1A2

### Overview
Refined the recommendation engine by standardizing the weighting system and improving the initial configuration experience.

### Changes
- **Standardized Weighting Scale**: All 4 components (Priority, Recency, Playtime, Size) now use a consistent 1–5 range
- **Balanced Defaults**: New installations default to weight 3 for all components
- **Dynamic Scoring Thresholds**: Promote/Demote thresholds scale with the sum of current weights
- **Weight Settings UI**: New Weights window for adjusting algorithm influence per component
- **Technical**: Improved persistence logic for weight settings during initial setup; added `weights` key to default config

---

## 0.0.1A1

### Changes
- Added Boot Drive detection and available space display
- Added configurable Boot Reserve percentage (default 15%)
- Added visual feedback (red text) when boot space is below the reserve threshold
- Fixed priority input validation (constrained to 1–5)

---

*Happy Gaming!*
