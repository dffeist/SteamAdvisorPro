"""Recommendations Toplevel window."""
import tkinter as tk
from tkinter import ttk

from utils import DEFAULT_WEIGHTS


def open_recommendations(parent_root, scores: list, config: dict, on_move):
    """Open the Smart Recommendations Toplevel.

    Args:
        parent_root: tk root or Toplevel
        scores:      list of (appid, info_dict, score) from score_games()
        config:      current config dict (used to read weights)
        on_move:     callable(aids: list) triggered when user clicks a move button
    """
    win = tk.Toplevel(parent_root)
    win.title("Smart Recommendations")
    win.geometry("900x600")

    notebook = ttk.Notebook(win)
    notebook.pack(expand=True, fill="both", padx=10, pady=10)

    current_weights = config.get("weights", DEFAULT_WEIGHTS)
    max_possible_score = sum(current_weights.values())

    promote_list = sorted(
        [(a, i, s) for a, i, s in scores if i["drive"] == "HDD" and s > max_possible_score * 0.5],
        key=lambda x: x[2], reverse=True,
    )
    demote_list = sorted(
        [(a, i, s) for a, i, s in scores if i["drive"] == "SSD" and s < max_possible_score * 0.4],
        key=lambda x: x[2],
    )

    def create_tab(title, games_list, button_text):
        frame = ttk.Frame(notebook)
        notebook.add(frame, text=title)
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
                win.destroy()
                on_move(aids)

        ttk.Button(frame, text=button_text, command=trigger_move).pack(pady=5)

    create_tab("Promote to SSD", promote_list, "Move to SSD")
    create_tab("Demote to HDD", demote_list, "Move to HDD")
