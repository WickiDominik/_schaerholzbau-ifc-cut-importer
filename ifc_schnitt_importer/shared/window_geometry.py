"""Fensterposition relativ zum Cadwork-Hauptfenster, DPI und Arbeitsbereich des Monitors (Kopie von shb_toolcenter.shared.window_geometry)."""

import ctypes
from ctypes import wintypes

FALLBACK_POSITION = (100, 100)
OFFSET = 120   # px vom linken oberen Rand des Cadwork-Fensters

# windll gibt es nur unter Windows; anderswo gelten Fallback-Position und ganzer Bildschirm.
_user32 = ctypes.windll.user32 if hasattr(ctypes, "windll") else None


def _cadwork_hwnd():
    from ifc_schnitt_importer.cadwork_api import project as uc

    return uc.get_3d_hwnd()


def get_window_geometry():
    """Position (x, y) leicht versetzt zum Cadwork-Fenster; ausserhalb von Windows/Cadwork der Fallback."""
    try:
        rect = wintypes.RECT()
        if not _user32.GetWindowRect(_cadwork_hwnd(), ctypes.byref(rect)):
            return FALLBACK_POSITION
        return int(rect.left + OFFSET), int(rect.top + OFFSET)
    except Exception:
        return FALLBACK_POSITION


def get_cadwork_dpi():
    """DPI des Monitors mit dem Cadwork-Fenster (z.B. 144 bei 150 %), sonst None."""
    if _user32 is None or not hasattr(_user32, "GetDpiForWindow"):
        return None
    try:
        dpi = int(_user32.GetDpiForWindow(_cadwork_hwnd()))
        return dpi if dpi >= 72 else None
    except Exception:
        return None


class _MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
    ]


_MONITOR_DEFAULTTONEAREST = 2


def get_work_area(window, x=0, y=0):
    """(links, oben, rechts, unten) des nutzbaren Bereichs um den Punkt (x, y).

    Unter Windows der Arbeitsbereich (ohne Taskleiste) des Monitors mit diesem Punkt, damit mehrere
    Monitore funktionieren; anderswo der ganze Bildschirm von *window*.
    """
    if _user32 is not None:
        try:
            monitor = _user32.MonitorFromPoint(wintypes.POINT(int(x), int(y)), _MONITOR_DEFAULTTONEAREST)
            info = _MONITORINFO()
            info.cbSize = ctypes.sizeof(_MONITORINFO)
            if monitor and _user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                work = info.rcWork
                return work.left, work.top, work.right, work.bottom
        except Exception:
            pass
    return 0, 0, window.winfo_screenwidth(), window.winfo_screenheight()
