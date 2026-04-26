"""Pure helper functions and application-wide constants.

No GUI, no threading, no external state — safe to import anywhere.
"""
import os
import shutil
import logging
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
GB_BYTES = 1024 ** 3
MB_BYTES = 1024 * 1024
BOOT_RESERVE_MIN_PCT = 15
COPY_CHUNK_BYTES = MB_BYTES
RECENCY_DECAY_DAYS = 90
NEVER_PLAYED_DAYS = 365
DEFAULT_WEIGHTS = {"priority": 3, "recency": 3, "playtime": 3, "size": 3}
DEFAULT_CONFIG = {
    "lib_paths": [], "use_api": False, "api_key": "",
    "steam_id": "", "hide_uninstalled": False,
    "boot_reserve_pct": BOOT_RESERVE_MIN_PCT,
    "priorities": {}, "metadata": {},
    "weights": DEFAULT_WEIGHTS,
}

# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def format_gb(byte_count, decimals=2):
    """Return *byte_count* formatted as 'X.XXgb'."""
    return f"{round(byte_count / GB_BYTES, decimals)}GB"


def format_drive_space(path, label, is_boot=False):
    """Return a human-readable drive usage string, or an error string on failure."""
    try:
        total, used, free = shutil.disk_usage(path)
        if is_boot:
            label = f"{label} (Boot Drive)"
        return f"{label}: {used // GB_BYTES}GB Used / {free // GB_BYTES}GB Free"
    except OSError as e:
        logging.warning("Disk usage query failed for %s: %s", path, e)
        return f"{label}: Path Error"

# ---------------------------------------------------------------------------
# File system helpers
# ---------------------------------------------------------------------------

def calculate_folder_size(path):
    """Walk *path* and return the total byte count of all files inside."""
    total = 0
    try:
        for dirpath, _, filenames in os.walk(path):
            for f in filenames:
                try:
                    total += os.path.getsize(os.path.join(dirpath, f))
                except OSError:
                    pass
    except OSError as e:
        logging.warning("Folder size calculation failed for %s: %s", path, e)
    return total

# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def score_games(all_game_data, metadata_map, priority_map, weights):
    """Return a list of (appid, info_dict, score) for every game in *all_game_data*."""
    scored = []
    now = datetime.now().timestamp()
    if not all_game_data:
        return scored

    wp = weights.get("priority", 3)
    wr = weights.get("recency", 3)
    wu = weights.get("playtime", 3)
    ws = weights.get("size", 3)

    max_playtime = max((g["playtime_raw"] for g in all_game_data.values()), default=1) or 1
    sizes = [
        metadata_map.get(str(aid), {}).get("size", 0)
        for aid in all_game_data
        if metadata_map.get(str(aid), {}).get("enabled")
    ]
    max_size = max(sizes) if sizes and max(sizes) > 0 else 1

    for aid, info in all_game_data.items():
        prio = int(priority_map.get(str(aid), 3))
        p_score = (prio / 5) * wp

        days = (now - info["last_played_unix"]) / 86400 if info["last_played_unix"] > 0 else NEVER_PLAYED_DAYS
        r_score = max(0, (1 - (min(days, RECENCY_DECAY_DAYS) / RECENCY_DECAY_DAYS))) * wr

        u_score = (min(info["playtime_raw"], max_playtime) / max_playtime) * wu

        meta = metadata_map.get(str(aid), {})
        g_size = meta.get("size", 0) if meta.get("enabled") else 0
        s_score = (g_size / max_size) * ws

        total = round(p_score + r_score + u_score + s_score, 1)
        scored.append((aid, info, total))
    return scored
