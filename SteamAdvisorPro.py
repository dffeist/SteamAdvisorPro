"""Steam Storage Advisor Pro — main entry point.

This file contains only the GUI coordinator class and the tkinter main loop.
All business logic lives in the imported modules.
"""
import logging
import os
import re
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

import config as cfg
import steam_api
from library import get_library_data
from mover import move_games, validate_move
from scanner import scan_games_batch, scan_single
from ui.recommendations import open_recommendations
from ui.settings_window import show_settings_window, show_weight_settings
from utils import (
    BOOT_RESERVE_MIN_PCT, DEFAULT_CONFIG, DEFAULT_WEIGHTS,
    MB_BYTES, format_drive_space, format_gb, score_games,
)

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")


class SteamAdvisorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Steam Storage Advisor Pro")
        self.root.geometry("1150x850")

        if steam_api.is_steam_running():
            messagebox.showerror(
                "Steam Running",
                "Steam must not be running to use Steam Advisor Pro app. "
                "Quit steam first then relaunch Steam Advisor Pro.",
            )
            self.root.destroy()
            return

        if getattr(sys, "frozen", False):
            application_path = os.path.dirname(os.path.abspath(sys.executable))
        else:
            application_path = os.path.dirname(os.path.abspath(__file__))
        self.config_file = os.path.normpath(
            os.path.join(application_path, "steam_advisor_config.json")
        )

        self.api_playtime_cache = {}
        self.all_game_data = {}
        self.scan_all_enabled = False
        self.hide_uninstalled_var = tk.BooleanVar(value=False)
        self._meta_lock = threading.Lock()

        self.config = DEFAULT_CONFIG.copy()
        self._apply_config(self.config)

        self._load_config_with_ui()
        self.setup_widgets()
        self.refresh_data()

    # ------------------------------------------------------------------
    # Config management
    # ------------------------------------------------------------------

    def _apply_config(self, new_config: dict):
        """Store *new_config* and sync all derived instance vars."""
        self.config = new_config
        paths = cfg.resolve_paths(new_config)
        self.hdd_path = paths["hdd_path"]
        self.ssd_path = paths["ssd_path"]
        self.priority_map = paths["priority_map"]
        self.api_key = paths["api_key"]
        self.steam_id = paths["steam_id"]
        self.use_api = paths["use_api"]
        self.boot_reserve_pct = paths["boot_reserve_pct"]
        self.metadata_map = paths["metadata_map"]
        self.hide_uninstalled_var.set(paths["hide_uninstalled"])
        self.ssd_is_boot = paths["ssd_is_boot"]
        self.hdd_is_boot = paths["hdd_is_boot"]

    def _load_config_with_ui(self):
        """Load config from disk; prompt for setup if missing or corrupt."""
        try:
            loaded = cfg.load_config(self.config_file)
            self._apply_config(loaded)
        except FileNotFoundError:
            if messagebox.askyesno(
                "Initalize or Reset Application",
                "No configuration file found (steam_advisor_config.json).\n\n"
                "Warning: Proceeding will reset all settings to default.\n\nProceed?",
            ):
                self.config = DEFAULT_CONFIG.copy()
                self._open_settings(is_initial=True)
            else:
                self.root.destroy()
        except Exception as e:
            logging.warning("Config parse failed (%s); resetting to defaults", e)
            self.config = DEFAULT_CONFIG.copy()
            self._open_settings(is_initial=True)

    def _save_config(self):
        """Flush current state back into self.config and write to disk."""
        self.config["priorities"] = self.priority_map
        self.config["metadata"] = self.metadata_map
        self.config["hide_uninstalled"] = self.hide_uninstalled_var.get()
        self.config["boot_reserve_pct"] = self.boot_reserve_pct
        try:
            cfg.save_config(self.config_file, self.config)
        except OSError as e:
            messagebox.showerror(
                "Save Error",
                f"Could not save configuration to:\n{self.config_file}\n\n"
                f"Error: {e}\n\nEnsure the application folder is writable.",
            )

    def _open_settings(self, is_initial=False):
        show_settings_window(
            self.root,
            self.config,
            on_save=self._on_settings_saved,
            is_initial=is_initial,
        )

    def _on_settings_saved(self, new_config: dict):
        self._apply_config(new_config)
        self._save_config()
        self.refresh_data()

    def _open_weight_settings(self):
        show_weight_settings(
            self.root,
            self.config,
            on_save=self._on_weights_saved,
        )

    def _on_weights_saved(self, new_weights: dict):
        self.config["weights"] = new_weights
        self._save_config()
        messagebox.showinfo("Success", "Weights updated and saved.")

    # ------------------------------------------------------------------
    # Disk utilities
    # ------------------------------------------------------------------

    def get_drive_space_text(self, path, label):
        return format_drive_space(path, label, is_boot=cfg.check_is_boot(path))

    def get_boot_available_pct(self) -> float:
        boot_path = None
        if self.ssd_is_boot:
            boot_path = self.ssd_path
        elif self.hdd_is_boot:
            boot_path = self.hdd_path
        if boot_path:
            import shutil
            try:
                total, used, free = shutil.disk_usage(boot_path)
                return (free / total) * 100
            except OSError as e:
                logging.warning("Boot drive space query failed: %s", e)
        return 0.0

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def setup_widgets(self):
        self.stats_frame = ttk.Frame(self.root, padding="5", relief="sunken")
        self.stats_frame.pack(fill="x", side="top")
        self.hdd_stats_label = ttk.Label(self.stats_frame, text="HDD: Loading...")
        self.hdd_stats_label.pack(side="left", padx=20)
        self.ssd_stats_label = ttk.Label(self.stats_frame, text="SSD: Loading...")
        self.ssd_stats_label.pack(side="right", padx=20)

        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.pack(fill="x")
        ttk.Button(top_frame, text="Move Selected", command=self.start_move).pack(side="left", padx=5)
        ttk.Button(top_frame, text="Get Recommendations", command=self._show_recommendations).pack(side="left", padx=5)
        ttk.Button(top_frame, text="Weights", command=self._open_weight_settings).pack(side="left", padx=5)
        ttk.Button(top_frame, text="Edit Priority", command=self.handle_edit_priority).pack(side="left", padx=5)
        ttk.Button(top_frame, text="Refresh", command=self.refresh_data).pack(side="left", padx=5)

        self.boot_reserve_frame = ttk.Frame(top_frame)
        self.boot_avail_label = ttk.Label(self.boot_reserve_frame, text="Boot Available: --%")
        self.boot_avail_label.pack(side="left", padx=(0, 10))
        self.reserve_label = ttk.Label(self.boot_reserve_frame, text="Boot Reserve %:")
        self.reserve_label.pack(side="left")

        self.reserve_var = tk.StringVar(value=str(self.boot_reserve_pct))
        self.reserve_spin = ttk.Spinbox(
            self.boot_reserve_frame, from_=BOOT_RESERVE_MIN_PCT, to=99, width=5,
            textvariable=self.reserve_var, command=self.update_reserve,
        )
        self.reserve_spin.pack(side="left", padx=5)
        self.reserve_spin.bind("<FocusOut>", lambda e: self.update_reserve())
        self.reserve_spin.bind("<Return>", self.on_reserve_enter)

        self.hide_chk = ttk.Checkbutton(
            top_frame, text="Hide Not Installed (0 size)",
            variable=self.hide_uninstalled_var,
            command=lambda: [self.refresh_data(), self._save_config()],
        )
        self.hide_chk.pack(side="left", padx=5)
        ttk.Button(top_frame, text="Settings", command=self._open_settings).pack(side="right", padx=5)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.root, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill="x", padx=15, pady=5)
        self.status_label = ttk.Label(self.root, text="Ready")
        self.status_label.pack(padx=15, anchor="w")

        table_container = ttk.Frame(self.root)
        table_container.pack(expand=True, fill="both", padx=10, pady=10)

        self.v_scrollbar = ttk.Scrollbar(table_container, orient="vertical")
        self.v_scrollbar.pack(side="right", fill="y")

        columns = ("AppID", "Game Name", "Drive", "Priority", "Last Played", "Playtime", "Scan", "Game Size")
        self.tree = ttk.Treeview(
            table_container, columns=columns, show="headings",
            selectmode="extended", yscrollcommand=self.v_scrollbar.set,
        )
        for col in columns:
            if col == "Scan":
                self.tree.heading(col, text="☐ Show All Sizes", command=self.toggle_scan_all)
            else:
                self.tree.heading(col, text=col, command=lambda _c=col: self.sort_column(self.tree, _c, False))
            self.tree.column(col, width=120, anchor="center")
        self.tree.column("AppID", width=80, anchor="center")
        self.tree.column("Game Name", width=350, anchor="w")
        self.tree.column("Scan", width=110, anchor="center")
        self.tree.column("Game Size", width=120, anchor="center")
        self.tree.pack(side="left", expand=True, fill="both")
        self.v_scrollbar.config(command=self.tree.yview)
        self.tree.bind("<ButtonRelease-1>", self.on_tree_click)

    # ------------------------------------------------------------------
    # Boot reserve controls
    # ------------------------------------------------------------------

    def on_reserve_enter(self, event=None):
        try:
            val = int(self.reserve_var.get())
            if messagebox.askyesno(
                "Confirm Boot Reserve",
                f"Are you sure you want to set the Boot Reserve to {val}%?\n\n"
                "This threshold prevents moving games to the boot drive if it "
                "would fall below this percentage.",
            ):
                self.update_reserve()
                self.root.focus_set()
        except ValueError:
            pass

    def update_reserve(self):
        try:
            val = int(self.reserve_var.get())
            if val < BOOT_RESERVE_MIN_PCT:
                val = BOOT_RESERVE_MIN_PCT
                self.reserve_var.set(str(BOOT_RESERVE_MIN_PCT))
            self.boot_reserve_pct = val
            avail = self.get_boot_available_pct()
            self.reserve_label.config(foreground="red" if self.boot_reserve_pct > avail else "")
            self._save_config()
        except ValueError:
            pass

    # ------------------------------------------------------------------
    # Data refresh and tree population
    # ------------------------------------------------------------------

    def refresh_data(self):
        self.hdd_stats_label.config(text=self.get_drive_space_text(self.hdd_path, "HDD"))
        self.ssd_stats_label.config(text=self.get_drive_space_text(self.ssd_path, "SSD"))

        if self.ssd_is_boot or self.hdd_is_boot:
            self.boot_reserve_frame.pack(side="left", padx=10, before=self.hide_chk)
            avail = self.get_boot_available_pct()
            self.boot_avail_label.config(text=f"Boot Available: {round(avail, 1)}%")
            self.reserve_var.set(str(self.boot_reserve_pct))
            self.reserve_label.config(foreground="red" if self.boot_reserve_pct > avail else "")
        else:
            self.boot_reserve_frame.pack_forget()

        show_playtime = bool(self.use_api and self.api_key and self.steam_id)
        all_cols = self.tree["columns"]
        self.tree["displaycolumns"] = all_cols if show_playtime else [c for c in all_cols if c != "Playtime"]

        for item in self.tree.get_children():
            self.tree.delete(item)

        if self.use_api and self.api_key and self.steam_id:
            try:
                self.api_playtime_cache = steam_api.fetch_playtime(self.api_key, self.steam_id)
            except Exception:
                messagebox.showwarning(
                    "API Warning",
                    "Could not reach Steam API.\nPlaytime data may be unavailable.",
                )

        self.all_game_data = {
            **get_library_data(self.hdd_path, "HDD", self.api_playtime_cache),
            **get_library_data(self.ssd_path, "SSD", self.api_playtime_cache),
        }

        with self._meta_lock:
            meta_snapshot = dict(self.metadata_map)

        for aid, info in self.all_game_data.items():
            prio = self.priority_map.get(str(aid), 3)
            meta = meta_snapshot.get(str(aid), {"enabled": False})

            if self.hide_uninstalled_var.get() and meta.get("enabled") and meta.get("size") == 0:
                continue

            scan_status = "☐"
            size_display = "--"
            if meta.get("enabled"):
                scan_status = "☑"
                if meta.get("size") == -1:
                    size_display = "Scanning..."
                else:
                    size_display = format_gb(meta.get("size", 0))
                    if str(meta.get("version", "")) != str(info.get("buildid", "")):
                        size_display += " ↻"

            self.tree.insert("", "end", values=(
                aid, info["name"], info["drive"], prio,
                info["last_played"], info["playtime"], scan_status, size_display,
            ))

    # ------------------------------------------------------------------
    # Scanning
    # ------------------------------------------------------------------

    def toggle_scan_all(self):
        self.scan_all_enabled = not self.scan_all_enabled
        char = "☑" if self.scan_all_enabled else "☐"
        self.tree.heading("Scan", text=f"{char} Show All Sizes")

        if self.scan_all_enabled:
            with self._meta_lock:
                to_scan = [
                    (str(aid), info)
                    for aid, info in self.all_game_data.items()
                    if not self.metadata_map.get(str(aid), {}).get("enabled")
                ]
            if to_scan:
                self._show_scan_popup(to_scan)
            else:
                self.refresh_data()

    def _show_scan_popup(self, to_scan: list):
        popup = tk.Toplevel(self.root)
        popup.title("Scanning Game Folders")
        popup.geometry("350x180")
        popup.resizable(False, False)
        popup.transient(self.root)
        popup.grab_set()

        label = ttk.Label(popup, text=f"Scanning {len(to_scan)} game folders...", padding=20, wraplength=300)
        label.pack()
        pb = ttk.Progressbar(popup, mode="indeterminate", length=250)
        pb.pack(pady=10)
        pb.start(10)

        def on_complete():
            self.root.after(0, finish_ui)

        def finish_ui():
            pb.stop()
            pb.pack_forget()
            label.config(text="Scanning process has been completed.")
            ttk.Button(
                popup, text="OK",
                command=lambda: [self._save_config(), self.refresh_data(), popup.destroy()],
            ).pack(pady=10)

        scan_games_batch(to_scan, self.metadata_map, self._meta_lock, on_complete)

    def _save_and_refresh(self):
        self._save_config()
        self.refresh_data()

    def on_tree_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        column = self.tree.identify_column(event.x)
        if self.tree.column(column, "id") != "Scan":
            return
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return

        appid = str(self.tree.item(item_id)["values"][0])
        info = self.all_game_data.get(appid)
        if not info:
            return

        with self._meta_lock:
            meta = self.metadata_map.get(appid, {"enabled": False})
            new_state = not meta.get("enabled", False)
            if new_state:
                self.metadata_map[appid] = {"enabled": True, "size": -1, "version": info["buildid"]}
            else:
                self.metadata_map[appid]["enabled"] = False

        if new_state:
            scan_single(
                appid, info, self.metadata_map, self._meta_lock,
                on_complete=lambda: self.root.after(0, self._save_and_refresh),
            )

        self._save_config()
        self.refresh_data()

    # ------------------------------------------------------------------
    # Sorting
    # ------------------------------------------------------------------

    def sort_column(self, tree, col, reverse):
        rows = [(tree.set(k, col), k) for k in tree.get_children("")]
        try:
            rows.sort(key=lambda t: float(re.sub(r"[^\d.]", "", t[0])), reverse=reverse)
        except ValueError:
            rows.sort(reverse=reverse)
        for i, (_, k) in enumerate(rows):
            tree.move(k, "", i)
        tree.heading(col, command=lambda: self.sort_column(tree, col, not reverse))

    # ------------------------------------------------------------------
    # Recommendations
    # ------------------------------------------------------------------

    def _show_recommendations(self):
        weights = self.config.get("weights", DEFAULT_WEIGHTS)
        with self._meta_lock:
            meta_snapshot = dict(self.metadata_map)
        scores = score_games(self.all_game_data, meta_snapshot, self.priority_map, weights)
        open_recommendations(self.root, scores, self.config, on_move=self.start_move)

    # ------------------------------------------------------------------
    # Priority editing
    # ------------------------------------------------------------------

    def handle_edit_priority(self):
        selections = self.tree.selection()
        if not selections:
            return
        initial_prio = self.tree.item(selections[0])["values"][3]
        count = len(selections)
        prompt = f"Set Priority (1-5) for {count} selected games:" if count > 1 else "Set Priority (1-5):"
        val = simpledialog.askinteger("Priority", prompt, initialvalue=initial_prio, minvalue=1, maxvalue=5)
        if val is not None:
            for item_id in selections:
                appid = str(self.tree.item(item_id)["values"][0])
                self.priority_map[appid] = val
            self._save_config()
            self.refresh_data()

    # ------------------------------------------------------------------
    # Move operations
    # ------------------------------------------------------------------

    def start_move(self, manual_aids=None):
        if steam_api.is_steam_running():
            messagebox.showerror("Error", "Close Steam first.")
            return

        if manual_aids:
            aids = manual_aids if isinstance(manual_aids, list) else [manual_aids]
        else:
            sel = self.tree.selection()
            if not sel:
                return
            aids = [str(self.tree.item(i)["values"][0]) for i in sel]

        ok, move_list, message = validate_move(
            aids, self.all_game_data, self.metadata_map, self._meta_lock,
            self.ssd_path, self.hdd_path, self.boot_reserve_pct,
        )

        if not ok:
            messagebox.showerror("Disk Space Error", message)
            return

        if messagebox.askyesno("Confirm Move", f"Are you sure you want to proceed?\n\n{message}"):
            move_games(
                move_list, self.ssd_path, self.hdd_path,
                progress_cb=self._on_move_progress,
                done_cb=self._on_move_done,
                error_cb=self._on_move_error,
            )

    def _on_move_progress(self, pct, copied, total, name):
        def _update():
            self.progress_var.set(pct)
            self.status_label.config(text=f"Moving {name}: {copied // MB_BYTES}MB/{total // MB_BYTES}MB")
        self.root.after(0, _update)

    def _on_move_done(self):
        def _finish():
            messagebox.showinfo("Done", "All selected games have been moved.")
            self.refresh_data()
            self.progress_var.set(0)
        self.root.after(0, _finish)

    def _on_move_error(self, message: str):
        self.root.after(0, lambda m=message: messagebox.showerror("Move Error", m))


if __name__ == "__main__":
    root = tk.Tk()
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Vertical.TScrollbar", background="#666", arrowcolor="white")
    app = SteamAdvisorGUI(root)
    root.mainloop()
