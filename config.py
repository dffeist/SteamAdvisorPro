"""Configuration load/save and path/boot-drive resolution.

All functions are stateless — they accept and return plain dicts/values.
"""
import os
import json
import logging
from pathlib import Path

from utils import DEFAULT_CONFIG, BOOT_RESERVE_MIN_PCT


def check_is_boot(path) -> bool:
    """Return True if *path* resides on the system boot drive."""
    try:
        drive = os.path.splitdrive(os.path.abspath(path))[0].upper()
        boot = os.path.splitdrive(os.environ.get("SystemRoot", "C:"))[0].upper()
        return drive == boot
    except OSError as e:
        logging.warning("Boot drive check failed for %s: %s", path, e)
        return False


def load_config(config_file: str) -> dict:
    """Load config from *config_file*, merging with defaults.

    Returns the merged config dict.  Does NOT open any GUI dialogs —
    callers are responsible for reacting to a missing/corrupt file.

    Raises:
        FileNotFoundError  — file does not exist or is empty
        json.JSONDecodeError — file exists but is not valid JSON
    """
    if not os.path.exists(config_file) or os.path.getsize(config_file) == 0:
        raise FileNotFoundError(config_file)
    with open(config_file, "r") as f:
        loaded = json.load(f)
    return {**DEFAULT_CONFIG, **loaded}


def save_config(config_file: str, config: dict) -> None:
    """Serialize *config* to *config_file* as indented JSON.

    Raises OSError on write failure — callers show the error dialog.
    """
    with open(config_file, "w") as f:
        json.dump(config, f, indent=4)


def resolve_paths(config: dict) -> dict:
    """Derive runtime path/flag values from *config*.

    Returns a dict with keys:
        hdd_path, ssd_path, priority_map, api_key, steam_id,
        use_api, boot_reserve_pct, metadata_map,
        ssd_is_boot, hdd_is_boot
    """
    hdd_path = Path(str(config.get("hdd_path", "")))
    ssd_path = Path(str(config.get("ssd_path", "")))
    return {
        "hdd_path": hdd_path,
        "ssd_path": ssd_path,
        "priority_map": config.get("priorities", {}),
        "api_key": config.get("api_key", ""),
        "steam_id": config.get("steam_id", ""),
        "use_api": config.get("use_api", False),
        "boot_reserve_pct": config.get("boot_reserve_pct", BOOT_RESERVE_MIN_PCT),
        "metadata_map": config.get("metadata", {}),
        "hide_uninstalled": config.get("hide_uninstalled", False),
        "ssd_is_boot": check_is_boot(ssd_path),
        "hdd_is_boot": check_is_boot(hdd_path),
    }
