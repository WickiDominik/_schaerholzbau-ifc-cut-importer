"""Minimal JSON logging for the IFC Schnitt Importer plugin.

Deliberately smaller than shb_toolcenter's logging module (no shared
network log target yet) but keeps the same log-entry shape so the two
plugins' logs could be merged/viewed with the same tooling later if
desired.
"""

import datetime
import json
import os
import traceback
import uuid
from typing import Optional

from ifc_schnitt_importer.shared.user_paths import user_data_dir

_LOG_FILENAME = "ifc_schnitt_importer_logs.json"


def _log_file() -> str:
    return os.path.join(user_data_dir("logs"), _LOG_FILENAME)


def _load_log_data():
    try:
        log_file = _log_file()
        if os.path.exists(log_file):
            with open(log_file, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {"logs": []}


def _save_log_data(data):
    try:
        with open(_log_file(), "w", encoding="utf-8") as f:
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
            # Aus dem Exception-Objekt selbst, nicht format_exc(): log_error_json
            # wird auch ausserhalb eines except-Blocks aufgerufen (z.B. mit
            # einer Exception aus dem Generator-Thread), dort lieferte
            # format_exc() nur "NoneType: None".
            "stack_trace": "".join(traceback.format_exception(type(error), error, error.__traceback__)),
            "context": context or {},
        }
        data = _load_log_data()
        data["logs"].append(entry)
        data["logs"] = data["logs"][-1000:]
        _save_log_data(data)
    except Exception as e:
        print(f"[ifc_schnitt_importer] JSON error logging failed: {e}")

