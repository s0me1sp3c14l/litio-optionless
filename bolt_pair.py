from bolt_scan import add_bolt_device
import os, time, glob, select, subprocess

def open_bolt_fd():
    for hp in sorted(glob.glob("/dev/hidraw*"), reverse=True):
        bn = os.path.basename(hp)
        try:
            ue = open(f"/sys/class/hidraw/{bn}/device/uevent", encoding="utf-8").read().lower()
            if "046d" in ue and "c548" in ue:
                fd = os.open(hp, os.O_RDWR | os.O_NONBLOCK)
                os.write(fd, bytes.fromhex("10ff8000000900"))
                r, _, _ = select.select((fd,), (), (), 0.25)
                if r and not os.read(fd, 64).hex().startswith("10ff8f"):
                    return fd, hp
                os.close(fd)
        except Exception:
            pass
    return None, None
def run_bolt_pair(status_cb):
    subprocess.run(("sudo", "-n", "systemctl", "stop", "logid"), check=False)
    time.sleep(0.25)
    fd, hp = open_bolt_fd()
    try:
        if fd is None:
            status_cb("⚠ Konnte Logi Bolt Port nicht öffnen.")
            return
        os.write(fd, bytes.fromhex("10ff8000000900"))
        time.sleep(0.05)
        os.write(fd, bytes.fromhex("11ff82c102") + bytes(15))
        time.sleep(0.15)
        while True:
            try:
                os.read(fd, 64)
            except BlockingIOError:
                break
        os.write(fd, bytes.fromhex("10ff80c01e0100"))
        status_cb("🔍 Suche MX Master 4 (30s)... Easy-Switch 3s gedrückt halten!")
        t0 = time.monotonic()
        paired = False
        addr = b""
        auth = b"\x02"
        steps = []
        clicks = 0
        def render_steps():
            if clicks >= len(steps):
                return f"✅ Alle {len(steps)} Klicks erfasst!\n👉 Jetzt LINKS + RECHTS gleichzeitig drücken!"
            done = " · ".join(f"✓{s}" for s in steps[:clicks])
            cur = f"👉 SCHRITT {clicks+1}/{len(steps)}: 【 {steps[clicks]} 】"
            rest = " → ".join(steps[clicks+1:])
            return "\n".join(x for x in (done, cur, f"Danach: {rest}" if rest else "") if x)
        while time.monotonic() - t0 < 50.0:
            r, _, _ = select.select((fd,), (), (), 0.25)
            if not r:
                continue
            pkt = os.read(fd, 64)
            hx = pkt.hex()
            if hx.startswith("11ff4f") and len(pkt) >= 19 and pkt[5:6] == bytes(1):
                addr = pkt[10:16]
                auth = pkt[18:19]
            elif hx.startswith("11ff4f") and len(pkt) >= 7 and pkt[5:6] == bytes.fromhex("01") and len(addr) == 6 and not paired:
                paired = True
                status_cb("🤝 MX Master 4 erkannt! Starte Passkey-Handshake...")
                os.write(fd, bytes.fromhex("11ff82c10100") + addr + auth + bytes.fromhex("0a") + bytes(6))
            elif hx.startswith("11ff4d") and len(pkt) >= 10:
                pk = pkt[4:10].decode("ascii", errors="ignore")
                if pk.isdigit():
                    bits = f"{int(pk):010b}"
                    steps = ["RECHTS" if b == "1" else "LINKS" for b in bits]
                    clicks = 0
                    status_cb(render_steps())
            elif hx.startswith("11ff4e") and steps:
                ev = pkt[3:4].hex()
                if ev == "01":
                    clicks += 1
                    status_cb(render_steps())
                elif ev == "04":
                    clicks = 0
                    status_cb("↺ Zurückgesetzt – starte von vorn:\n" + render_steps())
            elif paired and hx.startswith("11ff54") and len(pkt) >= 12:
                st = pkt[3:5].hex()
                if st == "0200":
                    sl = pkt[11:12].hex()
                    add_bolt_device("MX Master 4")
                    status_cb(f"✅ MX Master 4 erfolgreich auf Slot {sl} mit Logi Bolt gekoppelt!")
                    return
                elif st.startswith("02"):
                    paired = False
                    status_cb(f"⚠ Pairing abgebrochen ({st}) – bitte nochmal auf «Mit Logi Bolt koppeln» klicken.")
                    return
        status_cb("⏱ Zeit abgelaufen – bitte nochmal versuchen.")
    finally:
        if fd is not None:
            os.close(fd)
        subprocess.run(("sudo", "-n", "systemctl", "start", "logid"), check=False)
