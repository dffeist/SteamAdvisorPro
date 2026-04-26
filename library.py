"""Steam library manifest parsing.

Reads appmanifest_*.acf files from a Steam library directory and returns
a dict of game data.  No GUI, no threading.
"""
import logging
import re
from datetime import datetime
from pathlib import Path

import vdf


def get_library_data(path, drive_type: str, api_playtime_cache: dict) -> dict:
    """Parse all appmanifest_*.acf files under *path*/steamapps/.

    Returns a dict mapping appid (str) -> game info dict.
    Malformed or unreadable manifests are skipped with a warning.
    """
    manifest_path = Path(path) / "steamapps"
    games = {}
    if not manifest_path.exists():
        return games

    for file in manifest_path.glob("appmanifest_*.acf"):
        try:
            with open(file, "r", encoding="utf-8-sig", errors="replace") as f:
                data = vdf.load(f)
            state = data["AppState"]
            aid = str(state["appid"])
            api_val = api_playtime_cache.get(aid)
            playtime_val = (
                api_val if api_val is not None
                else round(int(state.get("PlaytimeForever", 0)) / 60, 1)
            )
            lp_unix = int(state.get("LastUpdated", 0))
            buildid = state.get("buildid", "0")
            games[aid] = {
                "name": re.sub(r"[^a-zA-Z0-9 ]", "", state["name"]),
                "install_dir": state.get("installdir", state["name"]),
                "drive": drive_type,
                "last_played_unix": lp_unix,
                "last_played": (
                    datetime.fromtimestamp(lp_unix).strftime("%Y-%m-%d")
                    if lp_unix > 0 else "Never"
                ),
                "playtime_raw": playtime_val,
                "playtime": f"{playtime_val}h" + ("" if api_val is not None else "*"),
                "buildid": buildid,
                "manifest": file,
                "path": path,
            }
        except (OSError, KeyError, ValueError, SyntaxError, UnicodeDecodeError) as e:
            logging.warning("Skipping manifest %s: %s", file, e)
            continue

    return games
