"""UI window utilities shared by all feature windows.

Copied/adapted from shb_toolcenter.shared.window_utils so this plugin
behaves correctly both from the Cadwork Shell (no Tk root yet) and from
the live Cadwork API (a Tk root may already exist).
"""

import tkinter as tk
from typing import Optional


def get_or_create_root(parent: Optional[tk.Tk] = None) -> tk.Tk:
    if parent is not None:
        return tk.Toplevel(parent)

    root_exists = False
    if tk._default_root is not None:
        try:
            root_exists = bool(tk._default_root.winfo_exists())
        except tk.TclError:
            root_exists = False

    if root_exists:
        return tk.Toplevel(tk._default_root)
    return tk.Tk()
