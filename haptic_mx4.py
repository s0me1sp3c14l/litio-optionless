#!/usr/bin/env python3
import os, glob, json, select, time, threading

PROFILES_FILE = os.path.expanduser("~/.config/litio-optionless/profiles.json")
CID_SLOTS = {
    b'\x00\x52': "middle_click", b'\x00\x53': "back", b'\x00\x56': "forward",
    b'\x00\xc3': "gesture_click", b'\x00\xc4': "mode_shift", b'\x01\xa0': "haptic_panel",
}

def _open_mx4():
    for p in sorted(glob.glob('/dev/hidraw*')):
        b = os.path.basename(p)
        u, r = f"/sys/class/hidraw/{b}/device/uevent", f"/sys/class/hidraw/{b}/device/report_descriptor"
        if os.path.exists(u) and os.path.exists(r):
            ut = open(u).read().upper()
            if "C548" in ut and b'\x06\x00\xff\x09\x02' in open(r, 'rb').read():
                return os.open(p, os.O_RDWR | os.O_NONBLOCK), 0x01
            if "0000046D:0000B042" in ut:
                return os.open(p, os.O_RDWR | os.O_NONBLOCK), 0xFF
    return None, None

def _send(feat_idx, fn, payload=b''):
    fd, slot = _open_mx4()
    if fd is None: return None
    try:
        os.write(fd, bytes([0x11, slot, feat_idx, (fn << 4) | 0x0A]) + payload.ljust(16, b'\x00'))
        t0 = time.time()
        while time.time() - t0 < 0.5:
            r, _, _ = select.select([fd], [], [], 0.1)
            if r:
                d = os.read(fd, 64)
                if d.startswith(bytes([0x11, slot, feat_idx])): return d
    except Exception: pass
    finally: os.close(fd)

def play_haptic(pattern=1):
    return _send(0x0B, 4, bytes([max(0, min(14, int(pattern)))]))

def set_haptic_level(enabled=True, level=60):
    return _send(0x0B, 2, bytes([1 if enabled else 0, max(0, min(100, int(level)))]))

def set_force_threshold(val=4646):
    v = max(274, min(8974, int(val)))
    return _send(0x0C, 3, bytes([(v >> 8) & 0xFF, v & 0xFF]))

def _init_mx4(fd, slot):
    for cid_b in CID_SLOTS:
        os.write(fd, bytes([0x11, slot, 13, (3 << 4) | 0x0A]) + cid_b + b'\x03' + bytes(13))
        time.sleep(0.03)
    if os.path.exists(PROFILES_FILE):
        hc = json.load(open(PROFILES_FILE, encoding="utf-8")).get("mx4_haptic", {})
        lv, frc = hc.get("level", 60), hc.get("force", 4646)
        os.write(fd, bytes([0x11, slot, 0x0B, (2 << 4) | 0x0A, 1 if lv > 0 else 0, lv]) + bytes(14))
        time.sleep(0.03)
        os.write(fd, bytes([0x11, slot, 0x0C, (3 << 4) | 0x0A, (frc >> 8) & 0xFF, frc & 0xFF]) + bytes(14))

def start_mx4_bridge(on_slot):
    def _loop():
        active_slot = None
        while True:
            fd, slot = _open_mx4()
            if fd is None: time.sleep(2.0); continue
            try:
                _init_mx4(fd, slot)
                hdr = bytes([0x11, slot, 0x0D, 0x00])
                while True:
                    r, _, _ = select.select([fd], [], [], 1.5)
                    if not r:
                        os.write(fd, bytes([0x11, slot, 13, (3 << 4) | 0x0A, 0x01, 0xA0, 0x03]) + bytes(13)); continue
                    d = os.read(fd, 64)
                    if d.startswith(bytes([0x10, slot, 0x41])): _init_mx4(fd, slot)
                    elif d.startswith(hdr):
                        hit = next((s for b_cid, s in CID_SLOTS.items() if b_cid in d), None)
                        if hit: active_slot = hit; on_slot(active_slot, True)
                        elif active_slot: on_slot(active_slot, False); active_slot = None
            except Exception: time.sleep(1.0)
            finally:
                try: os.close(fd)
                except Exception: pass
    threading.Thread(target=_loop, daemon=True).start()

def _open_any_mx():
    res = []
    for p in sorted(glob.glob('/dev/hidraw*')):
        b = os.path.basename(p)
        u, r = f"/sys/class/hidraw/{b}/device/uevent", f"/sys/class/hidraw/{b}/device/report_descriptor"
        if os.path.exists(u) and os.path.exists(r):
            ut = open(u).read().upper()
            if ("C548" in ut or "C52B" in ut) and b'\x06\x00\xff\x09\x02' in open(r, 'rb').read():
                for sl in range(1, 7): res.append((p, sl))
            elif "0000046D:0000B042" in ut or "0000046D:0000B019" in ut:
                res.append((p, 0xFF))
    return res

def toggle_smartshift():
    for path, sl in _open_any_mx():
        try: fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
        except Exception: continue
        try:
            for feat, fn_g, fn_s in ((0x2111, 1, 2), (0x2110, 0, 1)):
                os.write(fd, bytes([0x11, sl, 0x00, 0x0A, (feat >> 8) & 0xFF, feat & 0xFF]) + bytes(14))
                r = os.read(fd, 64) if select.select([fd], [], [], 0.15)[0] else None
                if r and len(r) >= 5 and r[2] == 0x00 and r[4] != 0:
                    idx = r[4]
                    os.write(fd, bytes([0x11, sl, idx, (fn_g << 4) | 0x0A]) + bytes(16))
                    cur = os.read(fd, 64) if select.select([fd], [], [], 0.15)[0] else None
                    if cur and len(cur) >= 5:
                        nxt = 1 if cur[4] == 2 else 2
                        os.write(fd, bytes([0x11, sl, idx, (fn_s << 4) | 0x0A, nxt, 0x00, 0x00]) + bytes(13))
                        select.select([fd], [], [], 0.15)
                        return nxt
        except Exception: pass
        finally: os.close(fd)
    return None

_rst_timer = None
BUSY_FILE = "/tmp/litio_haptic_busy"
def play_pulse(pattern, level, base_level=60, priority=False):
    global _rst_timer
    now = time.time()
    if not priority and os.path.exists(BUSY_FILE):
        try:
            if now < float(open(BUSY_FILE).read().strip()): return
        except Exception: pass
    if _rst_timer: _rst_timer.cancel()
    set_haptic_level(level > 0, level)
    play_haptic(pattern)
    wait = 4.3 if int(pattern) >= 10 else 0.7
    if priority:
        try: open(BUSY_FILE, "w").write(str(now + wait))
        except Exception: pass
    _rst_timer = threading.Timer(wait, lambda: set_haptic_level(base_level > 0, base_level))
    _rst_timer.daemon = True; _rst_timer.start()
