#!/usr/bin/env python3
import os, json, time, subprocess, threading
from pynput import mouse
import gi
gi.require_version("Atspi", "2.0")
from gi.repository import Atspi
import haptic_mx4

PROFILES_FILE = os.path.expanduser("~/.config/litio-optionless/profiles.json")
ROLE_GROUPS = {
    "buttons": {"push button", "toggle button", "check box", "radio button", "tool item", "icon", "slider"},
    "tabs": {"page tab", "menu item", "menu", "check menu item"},
    "links": {"link"},
}
APP_KEYS = {
    "thunderbird": ["thunderbird"], "element": ["element", "matrix"], "telegram": ["telegram"],
    "signal": ["signal"], "discord": ["discord"], "slack": ["slack"],
}

def _notify_loop():
    last_ts, buf, active = {}, [], False
    proc = subprocess.Popen(["dbus-monitor", "--session", "member='Notify'", "member='AddNotification'"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    for line in proc.stdout:
        st = line.strip()
        if "member=Notify" in st or "member=AddNotification" in st:
            active, buf = True, []; continue
        if active:
            if st.startswith('string "'): buf.append(st.lower())
            if len(buf) >= 3 or st.startswith("array ["):
                active = False; blob = " ".join(buf)
                cfg = json.load(open(PROFILES_FILE, encoding="utf-8")).get("notify_haptic", {}) if os.path.exists(PROFILES_FILE) else {}
                matched = next((k for k, words in APP_KEYS.items() if any(w in blob for w in words)), "other")
                pat = int(cfg.get(matched, -1))
                if pat >= 0 and time.monotonic() - last_ts.get(matched, 0.0) >= 2.0:
                    last_ts[matched] = time.monotonic()
                    full = json.load(open(PROFILES_FILE, encoding="utf-8")) if os.path.exists(PROFILES_FILE) else {}
                    base_lv = full.get("mx4_haptic", {}).get("level", 60)
                    haptic_mx4.play_pulse(pat, int(cfg.get("notify_level", base_lv)), base_lv, priority=True)

def _find_deep(node, px, py, allowed, depth=0):
    if not node or depth > 18: return None
    try:
        if node.get_role_name() in allowed: return node
        sub = Atspi.Component.get_accessible_at_point(node, px, py, Atspi.CoordType.SCREEN)
        if sub and sub != node:
            res = _find_deep(sub, px, py, allowed, depth + 1)
            if res: return res
    except Exception: pass
    return None

def start_hover_bridge(get_profile_fn):
    threading.Thread(target=_notify_loop, daemon=True).start()
    def _loop():
        try: Atspi.init()
        except Exception: pass
        m = mouse.Controller(); last_pos, last_obj, last_tick = (0, 0), None, 0.0
        while True:
            time.sleep(0.08)
            try:
                _, pd, gl = get_profile_fn()
                hc = pd.get("hover_haptic") if isinstance(pd.get("hover_haptic"), dict) else gl.get("hover_haptic", {})
                if not hc or not hc.get("enabled"): last_obj = None; continue
                px, py = map(int, m.position); pos = (px, py)
                if pos == last_pos: continue
                last_pos = pos
                allowed = {r for k, roles in ROLE_GROUPS.items() if hc.get(k) for r in roles}
                if not allowed: continue
                desk = Atspi.get_desktop(0); hit = None
                for i in range(desk.get_child_count()):
                    app = desk.get_child_at_index(i)
                    if not app or (app.get_name() or "").lower() in ("cinnamon", "muffin", "gnome-shell"): continue
                    for w in range(app.get_child_count()):
                        win = app.get_child_at_index(w)
                        hit = _find_deep(win, px, py, allowed)
                        if hit: break
                    if hit: break
                if hit is not None and hit != last_obj and time.monotonic() - last_tick >= 0.14:
                    last_tick = time.monotonic(); full = json.load(open(PROFILES_FILE, encoding="utf-8")) if os.path.exists(PROFILES_FILE) else {}
                    base_lv = full.get("mx4_haptic", {}).get("level", 60); hlv = int(hc.get("level", base_lv))
                    haptic_mx4.play_pulse(int(hc.get("pattern", 0)), hlv, base_lv)
                last_obj = hit
            except Exception: time.sleep(0.5)
    threading.Thread(target=_loop, daemon=True).start()
