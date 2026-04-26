import os
import sys
import vdf
import shutil
import json
import logging
import subprocess
import requests
import re
import tempfile
import threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

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
# Pure helper functions (testable without a GUI)
# ---------------------------------------------------------------------------

def format_gb(byte_count, decimals=2):
    """Return byte_count formatted as 'X.XXgb'."""
    return f"{round(byte_count / GB_BYTES, decimals)}GB"


def format_drive_space(path, label, is_boot=False):
    """Return a human-readable drive usage string, or an error string."""
    try:
        total, used, free = shutil.disk_usage(path)
        if is_boot:
            label = f"{label} (Boot Drive)"
        return f"{label}: {used // GB_BYTES}GB Used / {free // GB_BYTES}GB Free"
    except OSError as e:
        logging.warning("Disk usage query failed for %s: %s", path, e)
        return f"{label}: Path Error"


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


def score_games(all_game_data, metadata_map, priority_map, weights):
    """Return a list of (appid, info_dict, score) sorted by nothing (caller sorts)."""
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


# ---------------------------------------------------------------------------
# Main application class
# ---------------------------------------------------------------------------

class SteamAdvisorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Steam Storage Advisor Pro")
        self.root.geometry("1150x850")

        if self.is_steam_running():
            messagebox.showerror("Steam Running", "Steam must not be running to use Steam Advisor Pro app. Quit steam first then relaunch Steam Advisor Pro.")
            self.root.destroy()
            return

        if getattr(sys, "frozen", False):
            application_path = os.path.dirname(os.path.abspath(sys.executable))
        else:
            application_path = os.path.dirname(os.path.abspath(__file__))
        self.config_file = os.path.normpath(os.path.join(application_path, "steam_advisor_config.json"))

        self.api_playtime_cache = {}
        self.all_game_data = {}
        self.scan_all_enabled = False
        self.hide_uninstalled_var = tk.BooleanVar(value=False)
        self._meta_lock = threading.Lock()

        self.config = DEFAULT_CONFIG.copy()
        self.refresh_internal_paths()

        self.load_config()
        self.setup_widgets()
        self.refresh_data()

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def load_config(self):
        """Load config from disk, falling back to defaults on any error."""
        config_path = self.config_file
        exists = os.path.exists(config_path) and os.path.getsize(config_path) > 0
        if exists:
            try:
                with open(config_path, "r") as f:
                    loaded = json.load(f)
                self.config = {**DEFAULT_CONFIG, **loaded}
                self.refresh_internal_paths()
            except json.JSONDecodeError as e:
                logging.warning("Config parse failed (%s); resetting to defaults", e)
                self.config = DEFAULT_CONFIG.copy()
                self.show_settings_window(is_initial=True)
        else:
            if messagebox.askyesno("Initalize or Reset Application", "No configuration file found (steam_advisor_config.json).\n\nWarning: Proceeding will reset all settings to default.\n\nProceed?"):
                self.config = DEFAULT_CONFIG.copy()
                self.show_settings_window(is_initial=True)
            else:
                self.root.destroy()

    def refresh_internal_paths(self):
        """Sync instance variables from self.config."""
        self.hdd_path = Path(str(self.config.get("hdd_path", "")))
        self.ssd_path = Path(str(self.config.get("ssd_path", "")))
        self.priority_map = self.config.get("priorities", {})
        self.api_key = self.config.get("api_key", "")
        self.steam_id = self.config.get("steam_id", "")
        self.use_api = self.config.get("use_api", False)
        self.boot_reserve_pct = self.config.get("boot_reserve_pct", BOOT_RESERVE_MIN_PCT)
        self.metadata_map = self.config.get("metadata", {})
        self.hide_uninstalled_var.set(self.config.get("hide_uninstalled", False))
        self.ssd_is_boot = self.check_is_boot(self.ssd_path)
        self.hdd_is_boot = self.check_is_boot(self.hdd_path)

    def check_is_boot(self, path):
        """Return True if *path* is on the system boot drive."""
        try:
            drive = os.path.splitdrive(os.path.abspath(path))[0].upper()
            boot = os.path.splitdrive(os.environ.get("SystemRoot", "C:"))[0].upper()
            return drive == boot
        except OSError as e:
            logging.warning("Boot drive check failed for %s: %s", path, e)
            return False

    def save_config(self):
        self.config["priorities"] = self.priority_map
        self.config["metadata"] = self.metadata_map
        self.config["hide_uninstalled"] = self.hide_uninstalled_var.get()
        self.config["boot_reserve_pct"] = self.boot_reserve_pct
        try:
            with open(self.config_file, "w") as f:
                json.dump(self.config, f, indent=4)
        except OSError as e:
            messagebox.showerror("Save Error",
                                 f"Could not save configuration to:\n{self.config_file}\n\nError: {e}\n\nEnsure the application folder is writable.")

    # ------------------------------------------------------------------
    # Settings windows
    # ------------------------------------------------------------------

    def show_settings_window(self, is_initial=False):
        """Unified window for setup and updates with Browse buttons."""
        settings_win = tk.Toplevel(self.root)
        settings_win.title("Initial Setup" if is_initial else "Settings")
        settings_win.geometry("650x450")
        settings_win.transient(self.root)
        settings_win.grab_set()

        frame = ttk.Frame(settings_win, padding="20")
        frame.pack(expand=True, fill="both")

        if is_initial:
            ttk.Label(frame, text="Welcome! Please configure your Steam paths.",
                      font=("Arial", 10, "bold"), foreground="blue").grid(row=0, column=0, columnspan=3, pady=(0, 15))

        use_api_var = tk.BooleanVar(value=self.config.get("use_api", False))
        ttk.Checkbutton(frame, text="Enable Steam API (Required for accurate playtime)",
                        variable=use_api_var).grid(row=1 if is_initial else 0, column=0, columnspan=2, sticky="w", pady=5)

        fields = [
            ("HDD Steam Path:", "hdd_path", "D:\\SteamLibrary"),
            ("SSD Steam Path:", "ssd_path", "C:\\SteamLibrary"),
            ("Steam API Key:", "api_key", ""),
            ("SteamID64:", "steam_id", "")
        ]

        entries = {}
        start_offset = 2 if is_initial else 1

        def browse_folder(entry_field):
            folder_selected = filedialog.askdirectory()
            if folder_selected:
                entry_field.delete(0, tk.END)
                entry_field.insert(0, folder_selected.replace("/", "\\"))

        for i, (label_text, key, default) in enumerate(fields):
            ttk.Label(frame, text=label_text).grid(row=i + start_offset, column=0, sticky="w", pady=5)
            entry = ttk.Entry(frame, width=50)
            entry.insert(0, self.config.get(key, default))
            entry.grid(row=i + start_offset, column=1, padx=10, pady=5)
            entries[key] = entry
            if "path" in key:
                ttk.Button(frame, text="Browse...",
                           command=lambda e=entry: browse_folder(e)).grid(row=i + start_offset, column=2, padx=5)

        def save_action():
            self.config["use_api"] = use_api_var.get()
            for key, entry in entries.items():
                self.config[key] = entry.get()
            self.save_config()
            self.refresh_internal_paths()
            settings_win.destroy()
            self.refresh_data()

        def cancel_action():
            if is_initial:
                if messagebox.askyesno("Exit", "Setup is required. Exit application?"):
                    self.root.destroy()
            else:
                settings_win.destroy()

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=len(fields) + start_offset, column=0, columnspan=3, pady=20)
        ttk.Button(btn_frame, text="Save Settings", command=save_action).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=cancel_action).pack(side="left", padx=5)

        if is_initial:
            settings_win.protocol("WM_DELETE_WINDOW", cancel_action)
            self.root.wait_window(settings_win)

    def show_weight_settings(self):
        """Window to adjust recommendation algorithm weights."""
        weight_win = tk.Toplevel(self.root)
        weight_win.title("Recommendation Weights")
        weight_win.geometry("400x450")
        weight_win.transient(self.root)
        weight_win.grab_set()

        frame = ttk.Frame(weight_win, padding="20")
        frame.pack(expand=True, fill="both")

        ttk.Label(frame, text="Adjust Recommendation Weights", font=("Arial", 12, "bold")).pack(pady=(0, 10))
        ttk.Label(frame, text="Higher total score = Better candidate for SSD", font=("Arial", 8, "italic")).pack(pady=(0, 20))

        weights = self.config.get("weights", DEFAULT_WEIGHTS)
        sliders = {}
        fields = [
            ("priority", "User Priority"),
            ("recency", "Recency (Last Played)"),
            ("playtime", "Total Playtime"),
            ("size", "Game Install Size"),
        ]

        for key, label in fields:
            lbl_frame = ttk.Frame(frame)
            lbl_frame.pack(fill="x", pady=5)
            ttk.Label(lbl_frame, text=label).pack(side="left")
            val_label = ttk.Label(lbl_frame, text=str(weights.get(key, 0)))
            val_label.pack(side="right")
            s = ttk.Scale(frame, from_=1, to=5, orient="horizontal", value=weights.get(key, 3))
            s.pack(fill="x", pady=(0, 10))
            s.configure(command=lambda v, l=val_label: l.config(text=str(int(float(v)))))
            sliders[key] = s

        def save_weights():
            new_weights = {k: int(s.get()) for k, s in sliders.items()}
            self.config["weights"] = new_weights
            self.save_config()
            weight_win.destroy()
            messagebox.showinfo("Success", "Weights updated and saved.")

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=20)
        ttk.Button(btn_frame, text="Save Weights", command=save_weights).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=weight_win.destroy).pack(side="left", padx=5)

    # ------------------------------------------------------------------
    # Disk utilities
    # ------------------------------------------------------------------

    def get_drive_space_text(self, path, label):
        return format_drive_space(path, label, is_boot=self.check_is_boot(path))

    def get_boot_available_pct(self):
        """Return current free-space percentage on the boot drive, or 0.0."""
        boot_path = None
        if self.ssd_is_boot:
            boot_path = self.ssd_path
        elif self.hdd_is_boot:
            boot_path = self.hdd_path

        if boot_path:
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
        ttk.Button(top_frame, text="Move Selected", command=self.start_move_thread).pack(side="left", padx=5)
        ttk.Button(top_frame, text="Get Recommendations", command=self.open_recommendations).pack(side="left", padx=5)
        ttk.Button(top_frame, text="Weights", command=self.show_weight_settings).pack(side="left", padx=5)
        ttk.Button(top_frame, text="Edit Priority", command=self.handle_edit_priority).pack(side="left", padx=5)
        ttk.Button(top_frame, text="Refresh", command=self.refresh_data).pack(side="left", padx=5)

        self.boot_reserve_frame = ttk.Frame(top_frame)
        self.boot_avail_label = ttk.Label(self.boot_reserve_frame, text="Boot Available: --%")
        self.boot_avail_label.pack(side="left", padx=(0, 10))
        self.reserve_label = ttk.Label(self.boot_reserve_frame, text="Boot Reserve %:")
        self.reserve_label.pack(side="left")

        self.reserve_var = tk.StringVar(value=str(self.boot_reserve_pct))
        self.reserve_spin = ttk.Spinbox(self.boot_reserve_frame, from_=BOOT_RESERVE_MIN_PCT, to=99, width=5,
                                        textvariable=self.reserve_var, command=self.update_reserve)
        self.reserve_spin.pack(side="left", padx=5)
        self.reserve_spin.bind("<FocusOut>", lambda e: self.update_reserve())
        self.reserve_spin.bind("<Return>", self.on_reserve_enter)

        self.hide_chk = ttk.Checkbutton(top_frame, text="Hide Not Installed (0 size)",
                        variable=self.hide_uninstalled_var, command=lambda: [self.refresh_data(), self.save_config()])
        self.hide_chk.pack(side="left", padx=5)
        ttk.Button(top_frame, text="Settings", command=self.show_settings_window).pack(side="right", padx=5)

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
        self.tree = ttk.Treeview(table_container, columns=columns, show="headings",
                                selectmode="extended", yscrollcommand=self.v_scrollbar.set)

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
            if messagebox.askyesno("Confirm Boot Reserve",
                                   f"Are you sure you want to set the Boot Reserve to {val}%?\n\n"
                                   "This threshold prevents moving games to the boot drive if it would fall below this percentage."):
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
            self.save_config()
        except ValueError:
            pass

    # ------------------------------------------------------------------
    # Data refresh and display
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
        self.fetch_web_api_data()
        self.all_game_data = {**self.get_library_data(self.hdd_path, "HDD"), **self.get_library_data(self.ssd_path, "SSD")}

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

            self.tree.insert("", "end", values=(aid, info["name"], info["drive"], prio, info["last_played"], info["playtime"], scan_status, size_display))

    def get_library_data(self, path, drive_type):
        manifest_path = Path(path) / "steamapps"
        games = {}
        if not manifest_path.exists():
            return games
        for file in manifest_path.glob("appmanifest_*.acf"):
            try:
                with open(file, "r") as f:
                    data = vdf.load(f)
                state = data["AppState"]
                aid = str(state["appid"])
                api_val = self.api_playtime_cache.get(aid)
                playtime_val = api_val if api_val is not None else round(int(state.get("PlaytimeForever", 0)) / 60, 1)
                lp_unix = int(state.get("LastUpdated", 0))
                buildid = state.get("buildid", "0")
                games[aid] = {
                    "name": re.sub(r"[^a-zA-Z0-9 ]", "", state["name"]),
                    "install_dir": state.get("installdir", state["name"]),
                    "drive": drive_type,
                    "last_played_unix": lp_unix,
                    "last_played": datetime.fromtimestamp(lp_unix).strftime("%Y-%m-%d") if lp_unix > 0 else "Never",
                    "playtime_raw": playtime_val,
                    "playtime": f"{playtime_val}h" + ("" if api_val is not None else "*"),
                    "buildid": buildid,
                    "manifest": file,
                    "path": path,
                }
            except (OSError, KeyError, ValueError, SyntaxError) as e:
                logging.warning("Skipping manifest %s: %s", file, e)
                continue
        return games

    # ------------------------------------------------------------------
    # Scanning (folder size)
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
                self.show_scan_progress_popup(to_scan)
            else:
                self.refresh_data()

    def show_scan_progress_popup(self, to_scan):
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

        def run_batch():
            for appid, info in to_scan:
                size = calculate_folder_size(Path(info["path"]) / "steamapps" / "common" / info["install_dir"])
                with self._meta_lock:
                    self.metadata_map[appid] = {"enabled": True, "size": size, "version": info["buildid"]}
            self.root.after(0, finish_ui)

        def finish_ui():
            pb.stop()
            pb.pack_forget()
            label.config(text="Scanning process has been completed.")
            ttk.Button(popup, text="OK", command=lambda: [self.save_config(), self.refresh_data(), popup.destroy()]).pack(pady=10)

        threading.Thread(target=run_batch, daemon=True).start()

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
            threading.Thread(target=self._scan_single, args=(appid, info), daemon=True).start()

        self.save_config()
        self.refresh_data()

    def _scan_single(self, appid, info):
        size = calculate_folder_size(Path(info["path"]) / "steamapps" / "common" / info["install_dir"])
        with self._meta_lock:
            self.metadata_map[appid] = {"enabled": True, "size": size, "version": info["buildid"]}
        self.root.after(0, lambda: (self.save_config(), self.refresh_data()))

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

    def calculate_scores(self):
        weights = self.config.get("weights", DEFAULT_WEIGHTS)
        with self._meta_lock:
            meta_snapshot = dict(self.metadata_map)
        return score_games(self.all_game_data, meta_snapshot, self.priority_map, weights)

    def open_recommendations(self):
        rec_win = tk.Toplevel(self.root)
        rec_win.title("Smart Recommendations")
        rec_win.geometry("900x600")
        scores = self.calculate_scores()
        notebook = ttk.Notebook(rec_win)
        notebook.pack(expand=True, fill="both", padx=10, pady=10)

        def create_rec_tab(parent, title, games_list, button_text):
            frame = ttk.Frame(parent)
            parent.add(frame, text=title)
            cols = ("AID", "Game", "Score")
            tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="extended")
            for c in cols:
                tree.heading(c, text=c)
                if c in ("AID", "Score"):
                    tree.column(c, anchor="center")
                else:
                    tree.column(c, width=300, anchor="w")
            tree.pack(expand=True, fill="both")
            for aid, info, score in games_list:
                tree.insert("", "end", values=(aid, info["name"], score))

            def trigger_move():
                sel = tree.selection()
                if sel:
                    aids = [str(tree.item(i)["values"][0]) for i in sel]
                    rec_win.destroy()
                    self.start_move_thread(manual_aids=aids)

            ttk.Button(frame, text=button_text, command=trigger_move).pack(pady=5)

        current_weights = self.config.get("weights", DEFAULT_WEIGHTS)
        max_possible_score = sum(current_weights.values())
        promote_list = [(a, i, s) for a, i, s in scores if i["drive"] == "HDD" and s > (max_possible_score * 0.5)]
        demote_list = [(a, i, s) for a, i, s in scores if i["drive"] == "SSD" and s < (max_possible_score * 0.4)]
        create_rec_tab(notebook, "Promote to SSD", sorted(promote_list, key=lambda x: x[2], reverse=True), "Move to SSD")
        create_rec_tab(notebook, "Demote to HDD", sorted(demote_list, key=lambda x: x[2]), "Move to HDD")

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
            self.save_config()
            self.refresh_data()

    # ------------------------------------------------------------------
    # Steam API
    # ------------------------------------------------------------------

    def fetch_web_api_data(self):
        if not self.use_api or not self.api_key or not self.steam_id:
            return
        url = (
            f"http://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/"
            f"?key={self.api_key}&steamid={self.steam_id}&format=json"
        )
        try:
            r = requests.get(url, timeout=5).json()
            if "response" in r and "games" in r["response"]:
                for g in r["response"]["games"]:
                    self.api_playtime_cache[str(g["appid"])] = round(g.get("playtime_forever", 0) / 60, 1)
        except requests.RequestException as e:
            logging.warning("Steam API request failed: %s", e)
            messagebox.showwarning("API Warning", f"Could not reach Steam API:\n{e}\n\nPlaytime data may be unavailable.")

    # ------------------------------------------------------------------
    # Move operations
    # ------------------------------------------------------------------

    def start_move_thread(self, manual_aids=None):
        if self.is_steam_running():
            messagebox.showerror("Error", "Close Steam first.")
            return

        if manual_aids:
            aids = manual_aids if isinstance(manual_aids, list) else [manual_aids]
        else:
            sel = self.tree.selection()
            if not sel:
                return
            aids = [str(self.tree.item(item_id)["values"][0]) for item_id in sel]

        targets = {"SSD": 0, "HDD": 0}
        move_list_msg = ""
        total_bytes = 0

        for aid in aids:
            info = self.all_game_data.get(aid)
            if info:
                with self._meta_lock:
                    meta = self.metadata_map.get(str(aid), {})
                size = meta.get("size", -1)
                if size == -1:
                    size = calculate_folder_size(Path(info["path"]) / "steamapps" / "common" / info["install_dir"])
                src, dst = info["drive"], ("SSD" if info["drive"] == "HDD" else "HDD")
                targets[dst] += size
                total_bytes += size
                move_list_msg += f"• {info['name']} ({format_gb(size, 2)}): {src} -> {dst}\n"

        for label, req_size in targets.items():
            if req_size == 0:
                continue
            target_path = self.ssd_path if label == "SSD" else self.hdd_path
            try:
                total, used, free = shutil.disk_usage(target_path)
            except OSError as e:
                messagebox.showerror("Disk Space Error", f"Could not read disk usage for {label}:\n{e}")
                return

            if self.check_is_boot(target_path):
                reserve_ratio = self.boot_reserve_pct / 100.0
                if (free - req_size) < (total * reserve_ratio):
                    messagebox.showerror("Disk Space Error",
                                         f"Insufficient space on {label} (Boot Drive).\n\n"
                                         f"Moving these games would leave less than {self.boot_reserve_pct}% free space, "
                                         "which is required for system stability.")
                    return
            elif free < req_size:
                messagebox.showerror("Disk Space Error",
                                     f"Insufficient space on {label}.\n\n"
                                     f"Required: {format_gb(req_size)}\nAvailable: {format_gb(free)}")
                return

        if aids and messagebox.askyesno("Confirm Move",
                                        f"Are you sure you want to move these {len(aids)} game(s) "
                                        f"({format_gb(total_bytes)} total)?\n\n{move_list_msg}"):
            threading.Thread(target=self.threaded_move, args=(aids,), daemon=True).start()

    def threaded_move(self, appids):
        def update_ui(progress, copied, total, name):
            self.progress_var.set(progress)
            self.status_label.config(text=f"Moving {name}: {copied // MB_BYTES}MB/{total // MB_BYTES}MB")

        try:
            for appid in appids:
                info = self.all_game_data.get(appid)
                if not info:
                    continue
                target_lib = self.ssd_path if info["drive"] == "HDD" else self.hdd_path
                src_dir = Path(info["path"]) / "steamapps" / "common" / info["install_dir"]
                dst_dir = Path(target_lib) / "steamapps" / "common" / info["install_dir"]
                src_manifest = Path(info["manifest"])
                dst_manifest = Path(target_lib) / "steamapps" / src_manifest.name

                total_size = calculate_folder_size(src_dir)
                (Path(target_lib) / "steamapps" / "common").mkdir(parents=True, exist_ok=True)

                # Copy to a temp directory first for safe rollback on failure
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
                                    p = (copied / total_size) * 100 if total_size > 0 else 0
                                    p_snap, c_snap, t_snap, n_snap = p, copied, total_size, info["name"]
                                    self.root.after(0, lambda _p=p_snap, _c=c_snap, _t=t_snap, _n=n_snap: update_ui(_p, _c, _t, _n))

                    # Rename temp dir to final destination only after full copy
                    tmp_dir.rename(dst_dir)
                except OSError:
                    shutil.rmtree(tmp_dir, ignore_errors=True)
                    raise

                shutil.move(str(src_manifest), str(dst_manifest))
                shutil.rmtree(src_dir)

            self.root.after(0, lambda: (
                messagebox.showinfo("Done", "All selected games have been moved."),
                self.refresh_data(),
                self.progress_var.set(0),
            ))
        except Exception as e:
            logging.error("Move failed: %s", e)
            self.root.after(0, lambda m=str(e): messagebox.showerror("Move Error", m))

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def is_steam_running(self):
        try:
            return "steam.exe" in subprocess.check_output("tasklist", shell=True).decode().lower()
        except (OSError, subprocess.SubprocessError) as e:
            logging.warning("Could not check for Steam process: %s", e)
            return False


if __name__ == "__main__":
    root = tk.Tk()
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Vertical.TScrollbar", background="#666", arrowcolor="white")
    app = SteamAdvisorGUI(root)
    root.mainloop()
