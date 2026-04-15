import os
import json
import hmac
import hashlib
import threading

# === Local page-count tracker (replaces Firestore usage tracking) ===

_usage_lock = threading.Lock()
_usage_file = None  # set by init_usage_tracker()
_HMAC_KEY = b"NP2025#uSaGe!sIgN"


def _compute_signature(data: dict) -> str:
    """Compute HMAC-SHA256 signature for the usage payload."""
    payload = json.dumps({"total_pages": data.get("total_pages", 0)}, sort_keys=True)
    return hmac.new(_HMAC_KEY, payload.encode("utf-8"), hashlib.sha256).hexdigest()


def _read_usage() -> dict:
    """Read and verify the usage file. Returns data if valid, else resets to 0."""
    if not _usage_file or not os.path.exists(_usage_file):
        return {"total_pages": 0}
    with open(_usage_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    expected_sig = _compute_signature(data)
    if not hmac.compare_digest(data.get("_sig", ""), expected_sig):
        # Tampered or legacy file — reset to 0
        return {"total_pages": 0}
    return data


def _write_usage(data: dict):
    """Write the usage file with an HMAC signature."""
    data["_sig"] = _compute_signature(data)
    with open(_usage_file, "w", encoding="utf-8") as f:
        json.dump(data, f)


def init_usage_tracker(local_folder):
    """Call once at startup to set the path to the local usage file."""
    global _usage_file
    _usage_file = os.path.join(local_folder, "_usage.json")
    # Migrate legacy unsigned file
    with _usage_lock:
        if _usage_file and os.path.exists(_usage_file):
            with open(_usage_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "_sig" not in data:
                _write_usage(data)


def get_total_pages():
    """Return the current total_pages count from the local usage file."""
    with _usage_lock:
        data = _read_usage()
        return data.get("total_pages", 0)


def increment_total_pages(n):
    """Add *n* to the running total_pages counter."""
    with _usage_lock:
        data = _read_usage()
        data["total_pages"] = data.get("total_pages", 0) + n
        _write_usage(data)
