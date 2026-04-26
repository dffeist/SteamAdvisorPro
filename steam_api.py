"""Steam external integrations: Web API playtime fetch and process detection."""
import logging
import subprocess

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


def is_steam_running() -> bool:
    """Return True if steam.exe is currently running."""
    try:
        return "steam.exe" in subprocess.check_output("tasklist", shell=True).decode().lower()
    except (OSError, subprocess.SubprocessError) as e:
        logging.warning("Could not check for Steam process: %s", e)
        return False
