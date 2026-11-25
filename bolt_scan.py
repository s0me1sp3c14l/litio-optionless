import os, json

CACHE_FILE = os.path.expanduser("~/.config/litio-optionless/bolt_devices.json")

def add_bolt_device(name):
    if not name:
        return
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        existing = json.load(open(CACHE_FILE, encoding="utf-8")) if os.path.exists(CACHE_FILE) else []
        if name not in existing:
            existing.append(name)
            json.dump(existing, open(CACHE_FILE, "w", encoding="utf-8"))
    except Exception:
        pass

def get_bolt_names():
    if os.path.exists(CACHE_FILE):
        try:
            return json.load(open(CACHE_FILE, encoding="utf-8"))
        except Exception:
            pass
    return []
