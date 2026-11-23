import re
#!/usr/bin/env python3
import os, json, time, select, threading, subprocess, evdev
from pynput import mouse, keyboard

CONFIG_DIR = os.path.expanduser("~/.config/litio-optionless")
PROFILES_FILE = os.path.join(CONFIG_DIR, "profiles.json")
KEY_SLOTS = {evdev.ecodes.KEY_F13: "gesture_click", evdev.ecodes.KEY_F14: "back", evdev.ecodes.KEY_F15: "forward", evdev.ecodes.KEY_F16: "middle_click", evdev.ecodes.KEY_F17: "thumb_down", evdev.ecodes.KEY_F18: "thumb_up", evdev.ecodes.KEY_F19: "mode_shift"}
HOLD_MAP = {"Control_L": keyboard.Key.ctrl_l, "Control_R": keyboard.Key.ctrl_r, "Shift_L": keyboard.Key.shift_l, "Shift_R": keyboard.Key.shift_r, "Alt_L": keyboard.Key.alt_l, "Alt_R": keyboard.Key.alt_r, "Super_L": keyboard.Key.cmd}
KB = keyboard.Controller()

def ensure_config():
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if not os.path.exists(PROFILES_FILE):
        json.dump({"language": "de", "volume_step": 3, "profiles": {"Global (Standard)": {"buttons": {}, "gestures": {}}}}, open(PROFILES_FILE, "w", encoding="utf-8"), indent=2)

def send_combo(sc):
    parts = [p.strip() for p in sc.split("+") if p.strip()]
    mod_map = {"ctrl": keyboard.Key.ctrl_l, "control_l": keyboard.Key.ctrl_l, "alt": keyboard.Key.alt_l, "alt_l": keyboard.Key.alt_l, "shift": keyboard.Key.shift_l, "super_l": keyboard.Key.cmd}
    sp_map = {"up": keyboard.Key.up, "down": keyboard.Key.down, "left": keyboard.Key.left, "right": keyboard.Key.right, "return": keyboard.Key.enter, "escape": keyboard.Key.esc, "tab": keyboard.Key.tab, "backspace": keyboard.Key.backspace, "delete": keyboard.Key.delete, "space": keyboard.Key.space, "plus": "+", "minus": "-", "percent": "%", "bracketleft": "[", "bracketright": "]", "xf86audioprev": keyboard.Key.media_previous, "xf86audionext": keyboard.Key.media_next, "xf86audioplay": keyboard.Key.media_play_pause}
    held = []
    for p in parts[:-1]:
        mk = mod_map.get(p.lower())
        if mk: KB.press(mk); held.append(mk)
    last = parts[-1] if parts else ""
    try:
        if last == "%" or last.lower() == "percent":
            KB.press(keyboard.Key.shift_l); time.sleep(0.012)
            KB.press("5"); time.sleep(0.012); KB.release("5")
            time.sleep(0.012); KB.release(keyboard.Key.shift_l)
        else:
            key_obj = sp_map.get(last.lower()) or (getattr(keyboard.Key, last.lower()) if last.lower().startswith("f") and last[1:].isdigit() else (last if len(last) == 1 else None))
            if key_obj:
                KB.press(key_obj); time.sleep(0.01); KB.release(key_obj)
    finally:
        for mk in reversed(held):
            try: KB.release(mk)
            except Exception: pass
        try: KB.release(keyboard.Key.shift_l); KB.release(keyboard.Key.shift_r)
        except Exception: pass

_vol_pending = 0
_vol_running = False
_vol_lock = threading.Lock()
def _queue_fine_vol(delta):
    global _vol_pending, _vol_running
    with _vol_lock:
        _vol_pending += delta
        if _vol_running: return
        _vol_running = True
    def _worker():
        global _vol_pending, _vol_running
        try:
            with _vol_lock:
                d_val = max(-6, min(6, _vol_pending)); _vol_pending = 0
            if d_val != 0:
                out = subprocess.check_output(["pactl", "get-sink-volume", "@DEFAULT_SINK@"], stderr=subprocess.DEVNULL).decode()
                m = re.search(r"(\d+)%", out)
                cur_v = int(m.group(1)) if m else 50
                new_v = max(0, min(150, cur_v + d_val))
                subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{new_v}%"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                osd_v = min(100, int(round(new_v * 100 / 150)))
                ico = "audio-volume-muted" if new_v == 0 else ("audio-volume-low" if new_v < 50 else ("audio-volume-medium" if new_v < 105 else "audio-volume-high"))
                subprocess.Popen(["gdbus", "call", "--session", "--dest", "org.Cinnamon", "--object-path", "/org/Cinnamon", "--method", "org.Cinnamon.ShowOSD", f"{{'icon': <'{ico}'>, 'level': <int32 {osd_v}>}}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        finally:
            with _vol_lock: _vol_running = False
    threading.Thread(target=_worker, daemon=True).start()

def execute_action(sc, step=3, pressed=True):
    if not sc or sc in ("none", "gesture_mode", "smartshift_toggle"): return
    if sc in HOLD_MAP:
        KB.press(HOLD_MAP[sc]) if pressed else KB.release(HOLD_MAP[sc]); return
    if not pressed: return
    if sc in ("XF86AudioRaiseVolume", "XF86AudioLowerVolume", "XF86AudioMute", "XF86MonBrightnessUp", "XF86MonBrightnessDown"):
        subprocess.Popen(["xdotool", "key", "--clearmodifiers", sc])
    elif sc in ("fine_vol_up", "fine_vol_down"):
        step_s = "+2%" if sc == "fine_vol_up" else "-2%"
        subprocess.Popen(["bash", "-c", f"pactl set-sink-volume @DEFAULT_SINK@ {step_s}; v=$(pactl get-sink-volume @DEFAULT_SINK@ | grep -oE '[0-9]+%' | head -n1 | tr -d '%'); [ $v -gt 150 ] && pactl set-sink-volume @DEFAULT_SINK@ 150% && v=150; ov=$((v*100/150)); gdbus call --session --dest org.Cinnamon --object-path /org/Cinnamon --method org.Cinnamon.ShowOSD \"{{\'icon\': <\'audio-volume-high\'>, \'level\': <int32 $ov>}}\" >/dev/null 2>&1"])
    elif sc == "system_lock": subprocess.Popen(["loginctl", "lock-session"])
    elif sc == "system_suspend": subprocess.Popen(["systemctl", "suspend"])
    elif sc in ("%", "percent"): subprocess.Popen(["xdotool", "key", "--clearmodifiers", "percent"])
    else: send_combo(sc)

def active_wm_class():
    try:
        wid = subprocess.check_output(["xdotool", "getactivewindow"], stderr=subprocess.DEVNULL).decode().strip()
        return subprocess.check_output(["xprop", "-id", wid, "WM_CLASS"], stderr=subprocess.DEVNULL).decode().lower()
    except Exception: return ""

class LitioDaemon:
    def __init__(self):
        ensure_config(); self.m_ctrl = mouse.Controller(); self.gest_starts, self.last_tap = {}, {}
    def get_profile(self):
        cfg = json.load(open(PROFILES_FILE, encoding="utf-8")); wm = active_wm_class()
        for name, pd in cfg.get("profiles", {}).items():
            if name != "Global (Standard)" and any(c in wm for c in pd.get("wm_classes", [])):
                return cfg, pd, cfg["profiles"].get("Global (Standard)", {})
        gl = cfg.get("profiles", {}).get("Global (Standard)", {}); return cfg, gl, gl
    def handle_slot(self, slot, pressed):
        cfg, pd, gl = self.get_profile(); sc = pd.get("buttons", {}).get(slot) or gl.get("buttons", {}).get(slot, "")
        if sc == "gesture_mode":
            gcfg = (pd.get("gestures", {}).get(slot) if pd.get("gestures", {}).get(slot) else None) or gl.get("gestures", {}).get(slot) or {}
            if pressed:
                self.gest_starts[slot] = self.m_ctrl.position
                def _track(s=slot, gc=gcfg, st=cfg.get("volume_step", 3)):
                    while s in self.gest_starts:
                        time.sleep(0.028)
                        if s not in self.gest_starts: break
                        sx, sy = self.gest_starts[s]; ex, ey = self.m_ctrl.position; dx, dy = ex - sx, ey - sy
                        if abs(dx) >= 24 or abs(dy) >= 24:
                            d = ("right" if dx > 0 else "left") if abs(dx) > abs(dy) else ("down" if dy > 0 else "up")
                            execute_action(gc.get(d, ""), st, True); self.gest_starts[s] = (ex, ey)
                threading.Thread(target=_track, daemon=True).start()
            else: self.gest_starts.pop(slot, None)
        else:
            if pressed and sc not in HOLD_MAP:
                now = time.monotonic()
                if not slot.startswith("thumb_") and now - self.last_tap.get(slot, 0.0) < 0.35: return
                self.last_tap[slot] = now
            eff_sc = ("fine_vol_up" if sc == "XF86AudioRaiseVolume" else ("fine_vol_down" if sc == "XF86AudioLowerVolume" else sc)) if slot.startswith("thumb_") else sc
            execute_action(eff_sc, cfg.get("volume_step", 3), pressed)

def scan_devs(known):
    for p in evdev.list_devices():
        if p in known: continue
        try:
            dev = evdev.InputDevice(p)
            if any(k in dev.name.lower() for k in ("logiops", "virtual", "mx master", "usb receiver mouse", "consumer control")): known[p] = dev
        except Exception: pass

def run():
    d = LitioDaemon(); known = {}; hw_acc = 0
    while True:
        scan_devs(known)
        if not known: time.sleep(1.0); continue
        try:
            r, _, _ = select.select(list(known.values()), [], [], 1.0)
            for dev in r:
                try:
                    for ev in dev.read():
                        if ev.type == evdev.ecodes.EV_KEY and ev.code in KEY_SLOTS and ev.value in (0, 1):
                            d.handle_slot(KEY_SLOTS[ev.code], ev.value == 1)
                        elif ev.type == evdev.ecodes.EV_REL and ev.code == 12 and ev.value != 0:
                            hw_acc += ev.value
                            while abs(hw_acc) >= 75:
                                d.handle_slot("thumb_up" if hw_acc < 0 else "thumb_down", True)
                                hw_acc += 75 if hw_acc < 0 else -75
                except OSError: known.pop(dev.path, None)
        except Exception: known.clear(); time.sleep(0.5)

if __name__ == "__main__":
    run()
