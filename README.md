# Steam Advisor Pro

Steam Advisor Pro is a storage management utility designed to help you optimize your gaming experience by intelligently managing where your Steam games are installed.

As games grow in size, managing limited SSD space becomes a chore. This program scans your Steam libraries across two different drives (typically a fast SSD and a large HDD) and uses a scoring algorithm to recommend which games should be moved to faster storage and which can be safely archived to a mechanical drive.

---

## 🚀 Features

- **Smart Recommendations**: A scoring algorithm (0-100) based on Priority, Recency, Playtime, and Game Size.
- **Library Management**: Easily move games between HDD and SSD while maintaining Steam library integrity.
- **Disk Space Monitoring**: Real-time display of drive space and boot drive protection.
- **Boot Reserve Protection**: Configurable safety margin (default 15%) to prevent your system drive from running out of space.
- **Steam API Integration**: Fetch accurate playtime data directly from Steam servers.
- **Folder Size Scanning**: Calculate and cache game installation sizes to identify storage hogs.

---

## 🛠️ Getting Started

### 1. Prerequisites
- **Close Steam**: Steam must be completely closed before running this application.
- **Admin Permissions**: Ensure the application folder is writable.

### 2. Initial Configuration
On the first launch, you will be prompted to set up your environment:
- **Steam API Key**: (Optional) Get your key from [Steam Web API](https://steamcommunity.com/dev/apikey).
- **SteamID64**: Your 17-digit Steam ID (Found in your Profile URL).
- **Drive Paths**: Browse to your HDD and SSD Steam library root folders (e.g., `D:\SteamLibrary`).

---

## 📊 Scoring Logic

The recommendation score is calculated using a weighted system (configurable in Version A1.2+):
1. **User Priority (1-5)**: Your personal ranking of the game's importance.
2. **Recency**: How recently the game was played (weighted for the last 90 days).
3. **Usage**: Total playtime compared to your most-played titles.
4. **Game Size**: (New in A1.2) Larger games receive a higher priority for SSD placement.

---

## 🎮 Interface Guide

### Controls
- **Move Selected**: Transfer selected games between drives. Includes a pre-flight disk space check.
- **Get Recommendations**: Lists candidates for promotion to SSD or demotion to HDD.
- **Weights**: Adjust the influence of Priority, Recency, Playtime, and Size on the scoring algorithm.
- **Edit Priority**: Assign a 1-5 importance rating to games.
- **Refresh**: Rescan libraries for external changes.
- **Hide Not Installed**: Filter out games with 0 size (scanned games only).

### Game Table
- **AppID / Game Name**: Steam metadata.
- **Drive**: Current installation location (HDD/SSD).
- **Last Played / Playtime**: Usage statistics (Live API data marked with `*`).
- **Game Size**: Scan individual games (☑) or the entire library (Header checkbox). A `↻` indicates an update is available on Steam.

---

## 🔒 Safety & Troubleshooting

- **Atomic File Transfers**: Files are copied before deletion to prevent data loss.
- **Boot Drive Safety**: Prevent transfers that would violate the "Boot Reserve" threshold.
- **Process Check**: Prevents startup if `steam.exe` is running to avoid library corruption.
- **API Errors**: Ensure your Steam Profile is set to **Public** for playtime data.

---

## 📜 Version History

### A1.2
- Added game folder size to the weighted algorithm.
- Added a weight adjustment GUI for custom recommendations.

### A1.1
- Added Boot Drive detection and available space display.
- Added configurable Boot Reserve percentage (default 15%).
- Added visual feedback (Red text) for boot space warnings.
- Fixed priority input validation (constrained to 1-5).


```





