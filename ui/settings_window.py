"""Settings Toplevel windows.

Each function opens a modal Toplevel and calls a callback with the new
config dict when the user saves.  No business logic lives here.
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from utils import DEFAULT_WEIGHTS


def show_settings_window(parent_root, config: dict, on_save, is_initial=False):
    """Open the path/API settings Toplevel.

    Args:
        parent_root: tk root or Toplevel to attach to
        config:      current config dict (read-only; changes returned via on_save)
        on_save:     callable(new_config: dict) — called after user confirms
        is_initial:  True for first-run setup mode
    """
    win = tk.Toplevel(parent_root)
    win.title("Initial Setup" if is_initial else "Settings")
    win.geometry("650x450")
    win.transient(parent_root)
    win.grab_set()

    frame = ttk.Frame(win, padding="20")
    frame.pack(expand=True, fill="both")

    if is_initial:
        ttk.Label(frame, text="Welcome! Please configure your Steam paths.",
                  font=("Arial", 10, "bold"), foreground="blue").grid(
                      row=0, column=0, columnspan=3, pady=(0, 15))

    use_api_var = tk.BooleanVar(value=config.get("use_api", False))
    ttk.Checkbutton(frame, text="Enable Steam API (Required for accurate playtime)",
                    variable=use_api_var).grid(
                        row=1 if is_initial else 0, column=0, columnspan=2, sticky="w", pady=5)

    fields = [
        ("HDD Steam Path:", "hdd_path", "D:\\SteamLibrary"),
        ("SSD Steam Path:", "ssd_path", "C:\\SteamLibrary"),
        ("Steam API Key:", "api_key", ""),
        ("SteamID64:", "steam_id", ""),
    ]
    entries = {}
    start_offset = 2 if is_initial else 1

    def browse_folder(entry_field):
        folder = filedialog.askdirectory()
        if folder:
            entry_field.delete(0, tk.END)
            entry_field.insert(0, folder.replace("/", "\\"))

    for i, (label_text, key, default) in enumerate(fields):
        ttk.Label(frame, text=label_text).grid(row=i + start_offset, column=0, sticky="w", pady=5)
        entry = ttk.Entry(frame, width=50)
        entry.insert(0, config.get(key, default))
        entry.grid(row=i + start_offset, column=1, padx=10, pady=5)
        entries[key] = entry
        if "path" in key:
            ttk.Button(frame, text="Browse...",
                       command=lambda e=entry: browse_folder(e)).grid(
                           row=i + start_offset, column=2, padx=5)

    def save_action():
        new_config = dict(config)
        new_config["use_api"] = use_api_var.get()
        for key, entry in entries.items():
            new_config[key] = entry.get()
        win.destroy()
        on_save(new_config)

    def cancel_action():
        if is_initial:
            if messagebox.askyesno("Exit", "Setup is required. Exit application?"):
                parent_root.destroy()
        else:
            win.destroy()

    btn_frame = ttk.Frame(frame)
    btn_frame.grid(row=len(fields) + start_offset, column=0, columnspan=3, pady=20)
    ttk.Button(btn_frame, text="Save Settings", command=save_action).pack(side="left", padx=5)
    ttk.Button(btn_frame, text="Cancel", command=cancel_action).pack(side="left", padx=5)

    if is_initial:
        win.protocol("WM_DELETE_WINDOW", cancel_action)
        parent_root.wait_window(win)


def show_weight_settings(parent_root, config: dict, on_save):
    """Open the recommendation-weights Toplevel.

    Args:
        parent_root: tk root or Toplevel
        config:      current config dict
        on_save:     callable(new_weights: dict)
    """
    win = tk.Toplevel(parent_root)
    win.title("Recommendation Weights")
    win.geometry("400x450")
    win.transient(parent_root)
    win.grab_set()

    frame = ttk.Frame(win, padding="20")
    frame.pack(expand=True, fill="both")

    ttk.Label(frame, text="Adjust Recommendation Weights",
              font=("Arial", 12, "bold")).pack(pady=(0, 10))
    ttk.Label(frame, text="Higher total score = Better candidate for SSD",
              font=("Arial", 8, "italic")).pack(pady=(0, 20))

    weights = config.get("weights", DEFAULT_WEIGHTS)
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
        win.destroy()
        on_save(new_weights)

    btn_frame = ttk.Frame(frame)
    btn_frame.pack(pady=20)
    ttk.Button(btn_frame, text="Save Weights", command=save_weights).pack(side="left", padx=5)
    ttk.Button(btn_frame, text="Cancel", command=win.destroy).pack(side="left", padx=5)
