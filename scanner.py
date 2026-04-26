"""Background folder-size scanning coordination.

The GUI owns the progress popup UI; this module owns the threading logic
and metadata updates.
"""
import threading
from pathlib import Path

from utils import calculate_folder_size


def scan_games_batch(to_scan: list, metadata_map: dict, meta_lock: threading.Lock, on_complete):
    """Scan game folder sizes in a background thread.

    Args:
        to_scan:      list of (appid: str, info: dict) pairs to scan
        metadata_map: shared dict updated under *meta_lock*
        meta_lock:    threading.Lock guarding *metadata_map*
        on_complete:  zero-arg callable invoked on the background thread
                      when all scans are done (caller must marshal to UI
                      thread via root.after if needed)
    """
    def _run():
        for appid, info in to_scan:
            folder = Path(info["path"]) / "steamapps" / "common" / info["install_dir"]
            size = calculate_folder_size(folder)
            with meta_lock:
                metadata_map[appid] = {"enabled": True, "size": size, "version": info["buildid"]}
        on_complete()

    threading.Thread(target=_run, daemon=True).start()


def scan_single(appid: str, info: dict, metadata_map: dict, meta_lock: threading.Lock, on_complete):
    """Scan one game's folder in a background thread.

    Same callback contract as scan_games_batch.
    """
    def _run():
        folder = Path(info["path"]) / "steamapps" / "common" / info["install_dir"]
        size = calculate_folder_size(folder)
        with meta_lock:
            metadata_map[appid] = {"enabled": True, "size": size, "version": info["buildid"]}
        on_complete()

    threading.Thread(target=_run, daemon=True).start()
