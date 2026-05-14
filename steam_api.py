"""Steam external integrations: Web API playtime fetch and process detection."""
import logging
import re
import subprocess
import threading
import time

import requests


def fetch_playtime(api_key: str, steam_id: str) -> dict:
    """Fetch per-game playtime from the Steam Web API.

    Returns a dict mapping appid (str) -> playtime in hours (float).
    Returns an empty dict and logs a warning on network or parse failure.
    """
    url = (
        "http://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/"
        f"?key={api_key}&steamid={steam_id}&format=json"
    )
    try:
        r = requests.get(url, timeout=5).json()
        if "response" in r and "games" in r["response"]:
            return {
                str(g["appid"]): round(g.get("playtime_forever", 0) / 60, 1)
                for g in r["response"]["games"]
            }
        return {}
    except requests.RequestException as e:
        logging.warning("Steam API request failed: %s", e)
        raise


def fetch_ssd_requirements(
    appids: list,
    progress_cb=None,
    cancel_event: threading.Event = None,
) -> dict:
    """Query the Steam Store API for each appid and classify SSD requirement.

    Returns a dict mapping appid (str) -> one of:
        "SSDReq"  — SSD listed in minimum requirements
        "SSDRec"  — SSD listed only in recommended requirements
        "NoSSD"   — SSD not mentioned in either

    Sleeps 1 second between requests to respect Steam rate limits.
    Skips games that fail or return no requirement data.
    """
    _HTML_TAG = re.compile(r"<[^>]+>")
    results = {}
    total = len(appids)
    for i, appid in enumerate(appids):
        if cancel_event and cancel_event.is_set():
            break
        if progress_cb:
            progress_cb(i + 1, total)
        url = f"https://store.steampowered.com/api/appdetails?appids={appid}"
        try:
            data = requests.get(url, timeout=10).json()
            app_data = data.get(str(appid), {})
            if not app_data.get("success"):
                results[str(appid)] = "NoSSD"
                continue
            data = app_data.get("data", {})
            if not isinstance(data, dict):
                results[str(appid)] = "NoSSD"
                continue
            reqs = data.get("pc_requirements", {})
            if not isinstance(reqs, dict):
                results[str(appid)] = "NoSSD"
                continue
            minimum = _HTML_TAG.sub(" ", reqs.get("minimum", "")).lower()
            # Collect all other requirement text fields (recommended, notes, etc.)
            other = " ".join(
                _HTML_TAG.sub(" ", v).lower()
                for k, v in reqs.items()
                if k != "minimum" and isinstance(v, str)
            )
            if "ssd" in minimum:
                results[str(appid)] = "SSDReq"
            elif "ssd" in other:
                results[str(appid)] = "SSDRec"
            else:
                results[str(appid)] = "NoSSD"
        except requests.RequestException as e:
            logging.warning("SSD requirements fetch failed for appid %s: %s", appid, e)
        time.sleep(1)
    return results


def is_steam_running() -> bool:
    """Return True if steam.exe is currently running."""
    try:
        return "steam.exe" in subprocess.check_output("tasklist", shell=True).decode().lower()
    except (OSError, subprocess.SubprocessError) as e:
        logging.warning("Could not check for Steam process: %s", e)
        return False
