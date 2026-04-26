"""Game file move operations: validation and threaded execution.

validate_move() is called on the UI thread to check preconditions.
move_games() runs on a background thread and reports progress via callbacks.
"""
import logging
import os
import shutil
import tempfile
import threading
from pathlib import Path

from config import check_is_boot
from utils import calculate_folder_size, format_gb, MB_BYTES, COPY_CHUNK_BYTES


def validate_move(
    aids: list,
    all_game_data: dict,
    metadata_map: dict,
    meta_lock,
    ssd_path: Path,
    hdd_path: Path,
    boot_reserve_pct: int,
) -> tuple:
    """Check disk space and build the move list.

    Returns:
        (True, move_list, summary_msg)   — validation passed
        (False, [], error_msg)           — validation failed; show error_msg to user
    """
    targets = {"SSD": 0, "HDD": 0}
    move_list = []
    summary_lines = []

    for aid in aids:
        info = all_game_data.get(aid)
        if not info:
            continue
        with meta_lock:
            meta = metadata_map.get(str(aid), {})
        size = meta.get("size", -1)
        if size == -1:
            folder = Path(info["path"]) / "steamapps" / "common" / info["install_dir"]
            size = calculate_folder_size(folder)

        src = info["drive"]
        dst = "SSD" if src == "HDD" else "HDD"
        targets[dst] += size
        move_list.append((aid, info, size, dst))
        summary_lines.append(f"• {info['name']} ({format_gb(size)}): {src} -> {dst}")

    for label, req_size in targets.items():
        if req_size == 0:
            continue
        target_path = ssd_path if label == "SSD" else hdd_path
        try:
            total, used, free = shutil.disk_usage(target_path)
        except OSError as e:
            return False, [], f"Could not read disk usage for {label}:\n{e}"

        if check_is_boot(target_path):
            reserve_ratio = boot_reserve_pct / 100.0
            if (free - req_size) < (total * reserve_ratio):
                return False, [], (
                    f"Insufficient space on {label} (Boot Drive).\n\n"
                    f"Moving these games would leave less than {boot_reserve_pct}% free space, "
                    "which is required for system stability."
                )
        elif free < req_size:
            return False, [], (
                f"Insufficient space on {label}.\n\n"
                f"Required: {format_gb(req_size)}\nAvailable: {format_gb(free)}"
            )

    total_bytes = sum(s for _, _, s, _ in move_list)
    summary = f"Move {len(move_list)} game(s) ({format_gb(total_bytes)} total):\n\n" + "\n".join(summary_lines)
    return True, move_list, summary


def move_games(move_list: list, ssd_path: Path, hdd_path: Path, progress_cb, done_cb, error_cb):
    """Copy games to their destination drives in a background thread.

    Args:
        move_list:   list of (appid, info_dict, size_bytes, dst_label)
        ssd_path:    Path to SSD library root
        hdd_path:    Path to HDD library root
        progress_cb: called as progress_cb(pct, copied_bytes, total_bytes, game_name)
        done_cb:     called with no args on success
        error_cb:    called as error_cb(message_str) on failure
    """
    def _run():
        try:
            for appid, info, _size, dst_label in move_list:
                target_lib = ssd_path if dst_label == "SSD" else hdd_path
                src_dir = Path(info["path"]) / "steamapps" / "common" / info["install_dir"]
                dst_dir = Path(target_lib) / "steamapps" / "common" / info["install_dir"]
                src_manifest = Path(info["manifest"])
                dst_manifest = Path(target_lib) / "steamapps" / src_manifest.name

                total_size = calculate_folder_size(src_dir)
                (Path(target_lib) / "steamapps" / "common").mkdir(parents=True, exist_ok=True)

                tmp_dir = Path(tempfile.mkdtemp(dir=Path(target_lib) / "steamapps" / "common"))
                try:
                    copied = 0
                    for r, dirs, files in os.walk(src_dir):
                        rel = os.path.relpath(r, src_dir)
                        (tmp_dir / rel).mkdir(parents=True, exist_ok=True)
                        for f in files:
                            src_file = Path(r) / f
                            dst_file = tmp_dir / rel / f
                            with open(src_file, "rb") as fs, open(dst_file, "wb") as fd:
                                while chunk := fs.read(COPY_CHUNK_BYTES):
                                    fd.write(chunk)
                                    copied += len(chunk)
                                    pct = (copied / total_size) * 100 if total_size > 0 else 0
                                    progress_cb(pct, copied, total_size, info["name"])
                    tmp_dir.rename(dst_dir)
                except OSError:
                    shutil.rmtree(tmp_dir, ignore_errors=True)
                    raise

                shutil.move(str(src_manifest), str(dst_manifest))
                shutil.rmtree(src_dir)

            done_cb()
        except Exception as e:
            logging.error("Move failed: %s", e)
            error_cb(str(e))

    threading.Thread(target=_run, daemon=True).start()
