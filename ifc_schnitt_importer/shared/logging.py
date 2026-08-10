"""Minimal JSON logging for the IFC Schnitt Importer plugin.

Deliberately smaller than shb_toolcenter's logging module (no shared
network log target yet) but keeps the same log-entry shape so the two
plugins' logs could be merged/viewed with the same tooling later if
desired.
"""

import datetime
import json
import os
import sys
import traceback
import uuid
from typing import Any, Optional

_LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logs"))
_LOG_FILE = os.path.join(_LOG_DIR, "ifc_schnitt_importer_logs.json")


def _load_log_data():
    try:
        if os.path.exists(_LOG_FILE):
            with open(_LOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {"logs": []}


def _save_log_data(data):
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
        with open(_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[ifc_schnitt_importer] logging error: {e}")


def log_error_json(
    error: BaseException,
    *,
    module: Optional[str] = None,
    action: str = "exception",
    function_name: Optional[str] = None,
    context: Optional[dict] = None,
):
    try:
        entry = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.datetime.now().isoformat(),
            "user": os.environ.get("USERNAME", ""),
            "action": action,
            "module": module or "unknown",
            "function_name": function_name or "",
            "error_type": type(error).__name__,
            "error_message": str(error),
            "stack_trace": traceback.format_exc(),
            "context": context or {},
        }
        data = _load_log_data()
        data["logs"].append(entry)
        data["logs"] = data["logs"][-1000:]
        _save_log_data(data)
    except Exception as e:
        print(f"[ifc_schnitt_importer] JSON error logging failed: {e}")


def install_exception_hooks(default_module: str = "unknown"):
    previous = getattr(sys, "excepthook", None)

    def _hook(exc_type, exc_value, exc_tb):
        try:
            if isinstance(exc_value, BaseException):
                log_error_json(exc_value, module=default_module, action="uncaught_exception")
        finally:
            if callable(previous):
                previous(exc_type, exc_value, exc_tb)

    sys.excepthook = _hook
