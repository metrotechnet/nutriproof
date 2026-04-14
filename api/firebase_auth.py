import os
import json
import threading

# === Local page-count tracker (replaces Firestore usage tracking) ===

_usage_lock = threading.Lock()
_usage_file = None  # set by init_usage_tracker()


def init_usage_tracker(local_folder):
    """Call once at startup to set the path to the local usage file."""
    global _usage_file
    _usage_file = os.path.join(local_folder, "_usage.json")


def get_total_pages():
    """Return the current total_pages count from the local usage file."""
    with _usage_lock:
        if _usage_file and os.path.exists(_usage_file):
            with open(_usage_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("total_pages", 0)
    return 0


def increment_total_pages(n):
    """Add *n* to the running total_pages counter."""
    with _usage_lock:
        data = {}
        if _usage_file and os.path.exists(_usage_file):
            with open(_usage_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        data["total_pages"] = data.get("total_pages", 0) + n
        with open(_usage_file, "w", encoding="utf-8") as f:
            json.dump(data, f)
