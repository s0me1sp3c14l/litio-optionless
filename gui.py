#!/usr/bin/env python3
import sys, os, re, json, datetime, subprocess, xml.etree.ElementTree as ET
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QComboBox, QLineEdit, QMessageBox, QFrame, QStackedWidget, QListWidget,
    QSystemTrayIcon, QMenu, QInputDialog, QGraphicsOpacityEffect, QSlider, QCheckBox, QFileDialog
)
from PyQt6.QtCore import Qt, QPointF, QRect, QRectF, QByteArray, QTimer, QPropertyAnimation, QVariantAnimation, QEasingCurve
from PyQt6.QtGui import QIcon, QPainter, QColor, QPen, QBrush
from PyQt6.QtSvg import QSvgRenderer
from litio_daemon import ensure_config

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.expanduser("~/.config/litio-optionless")
PROFILES_FILE = os.path.join(CONFIG_DIR, "profiles.json")
DEVICES_FILE = os.path.join(APP_DIR, "devices.json")
ANCHORS_FILE = os.path.join(APP_DIR, "callout_anchors.json")
MODEL_ORDER = ["MX Master", "MX Master 2S", "MX Master 3", "MX Master 3S", "MX Master 4"]
ACTION_LABELS = {"gesture_click": "Daumen-Gestentaste", "back": "Zurück-Taste", "forward": "Vorwärts-Taste", "thumb_up": "Daumenrad Hoch", "thumb_down": "Daumenrad Runter", "middle_click": "Scrollrad-Klick", "mode_shift": "Modus-Taste"}
PRESET_SHORTCUTS = [("Benutzerdefiniert...", ""), ("Gestentaste (4 Maus-Richtungen)", "gesture_mode"), ("Mausrad-Modus (Freilauf / Raster)", "smartshift_toggle"), ("Horizontal Scrollen Links (◀)", "hscroll_left"), ("Horizontal Scrollen Rechts (▶)", "hscroll_right"), ("Lautstärke Hoch", "XF86AudioRaiseVolume"), ("Lautstärke Runter", "XF86AudioLowerVolume"), ("Ton Stumm", "XF86AudioMute"), ("Play / Pause", "XF86AudioPlay"), ("Vorheriger Track (Media Prev)", "XF86AudioPrev"), ("Nächster Track (Media Next)", "XF86AudioNext"), ("Fenster wechseln (Alt+Tab)", "alt+tab"), ("Desktop links wechseln", "ctrl+alt+left"), ("Desktop rechts wechseln", "ctrl+alt+right"), ("Helligkeit Hoch", "XF86MonBrightnessUp"), ("Helligkeit Runter", "XF86MonBrightnessDown"), ("Ausschneiden (Strg+X)", "ctrl+x"), ("Rückgängig (Strg+Z)", "ctrl+z"), ("Fenster maximieren", "alt+F10"), ("Fenster minimieren", "window_minimize"), ("Super / Startmenü", "Super_L"), ("Computer sperren", "system_lock"), ("Computer Standby", "system_suspend"), ("Global übernehmen (Standard)", ""), ("Deaktiviert / Natives Verhalten", "none")]
SUB_PRESET_SHORTCUTS = [p for p in PRESET_SHORTCUTS if p[1] != "gesture_mode"]

STYLESHEET = """
QMainWindow, QWidget { background-color: #14121A; color: #F3F0F8; font-family: 'Segoe UI', 'Ubuntu', sans-serif; font-size: 13px; }
QFrame#TopBar { background-color: #1A1724; border-bottom: 1px solid #2C273A; }
QFrame#BottomBar { background-color: #110F17; border-top: 1px solid #2C273A; }
QFrame#Card { background-color: #1C1926; border-radius: 14px; border: 1px solid #2E293D; }
QFrame#StatusPill { background-color: #100E15; border-radius: 8px; border: 1px solid #2A2538; }
QPushButton#TabBtn { background-color: transparent; color: #9C94AD; padding: 14px 20px; border: none; border-bottom: 3px solid transparent; font-size: 14px; font-weight: 600; }
QPushButton#TabBtn:hover { color: #F3F0F8; }
QPushButton#TabBtn[active="true"] { color: #C084FC; border-bottom: 3px solid #A855F7; font-weight: 700; }
QPushButton#AccentBtn { background-color: #9333EA; color: #FFFFFF; font-weight: 700; padding: 10px 18px; border-radius: 8px; border: none; }
QPushButton#AccentBtn:hover { background-color: #A855F7; }
QPushButton#SecondaryBtn { background-color: #252133; color: #E8E3F2; font-weight: 600; padding: 9px 14px; border-radius: 8px; border: 1px solid #3A334F; }
QPushButton#SecondaryBtn:hover { background-color: #322C45; }
QPushButton#HotspotBtn { background-color: #1C1926; color: #EDE8F5; border: 1.5px solid #9333EA; border-radius: 14px; padding: 5px 13px; font-size: 12px; font-weight: 600; }
QPushButton#HotspotBtn:hover, QPushButton#HotspotBtn[selected="true"] { background-color: #A855F7; color: #120E1A; font-weight: 700; }
QComboBox, QLineEdit { background-color: #121018; border: 1px solid #342E47; border-radius: 7px; padding: 7px 11px; color: #F3F0F8; }
QComboBox:focus, QLineEdit:focus { border: 1.5px solid #A855F7; }
QListWidget { background-color: #121018; border: 1px solid #2E293D; border-radius: 8px; padding: 4px; }
QListWidget::item { padding: 9px 11px; border-radius: 6px; }
QListWidget::item:selected { background-color: #9333EA; color: #FFFFFF; font-weight: 700; }
"""

def query_connected_mice(devices_dict):
    raw_bt, raw_up, raw_usb = "", "", ""
    for cmd, trg in [(["bluetoothctl", "devices", "Connected"], "bt"), (["upower", "-d"], "up"), (["lsusb"], "usb")]:
        try:
            out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=1.0).decode("utf-8", "ignore")
            if trg == "bt": raw_bt = out
            elif trg == "up": raw_up = out
            else: raw_usb = out
        except Exception: pass
    found = {}
    if "046d:c548" in raw_usb.lower() or "bolt receiver" in raw_usb.lower(): found["MX Master 3S"] = "Bolt / USB"
    elif "046d:c52b" in raw_usb.lower() or "unifying" in raw_usb.lower(): found["MX Master 2S"] = "Bolt / USB"
    bt_low = raw_bt.lower()
    for m in reversed(MODEL_ORDER):
        if m in devices_dict and re.search(rf"\b{re.escape(m.lower())}\b", bt_low):
            found[m] = "Bluetooth"; bt_low = bt_low.replace(m.lower(), "")
    res = []
    for m in MODEL_ORDER:
        if m in found:
            pct = 80
            for ublk in raw_up.split("Device:"):
                if m.lower() in ublk.lower():
                    mm = re.search(r"percentage:\s*(\d+)%", ublk)
                    if mm: pct = int(mm.group(1))
            res.append({"name": m, "conn": found[m], "battery": pct})
    return res if res else [{"name": "MX Master 3S", "conn": "Bolt / USB", "battery": 85}]

class DeviceStatusPill(QFrame):
    def __init__(self, conn="Bolt / USB", battery=85, parent=None):
        super().__init__(parent)
        self.setObjectName("StatusPill"); self.setFixedSize(96, 34); self.conn, self.battery = conn, battery
    def set_status(self, conn, battery): self.conn, self.battery = conn, battery; self.update()
    def paintEvent(self, e):
        super().paintEvent(e); p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        is_bt = "bluetooth" in self.conn.lower(); p.setPen(QPen(QColor("#818CF8" if is_bt else "#A3B83B"), 1.8))
        if is_bt:
            p.drawLine(22, 9, 22, 25); p.drawLine(22, 9, 28, 14); p.drawLine(28, 14, 17, 21); p.drawLine(22, 25, 28, 20); p.drawLine(28, 20, 17, 13)
        else:
            p.drawRoundedRect(16, 11, 14, 12, 3, 3); p.drawLine(20, 17, 26, 17); p.drawLine(23, 14, 23, 20)
        p.setPen(QPen(QColor("#2A2538"), 1)); p.drawLine(44, 7, 44, 27)
        col = QColor("#249E57") if self.battery > 45 else (QColor("#B89B28") if self.battery > 20 else QColor("#B83B3B"))
        p.setPen(QPen(col, 1.6)); p.setBrush(Qt.BrushStyle.NoBrush); p.drawRoundedRect(54, 11, 24, 12, 2, 2)
        p.setBrush(QBrush(col)); p.setPen(Qt.PenStyle.NoPen); p.drawRect(79, 14, 2, 6)
        p.drawRect(56, 13, max(2, int(20 * min(100, max(0, self.battery)) / 100.0)), 8)

class DevicePickerCard(QWidget):
    def __init__(self, dev_info, on_pick, parent=None):
        super().__init__(parent)
        self.dev, self.on_pick, self._scale = dev_info, on_pick, 1.0
        self.setFixedSize(260, 340); self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.anim = QVariantAnimation(self); self.anim.setDuration(180); self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.valueChanged.connect(lambda v: (setattr(self, "_scale", float(v)), self.update()))
        vl = QVBoxLayout(self); vl.setContentsMargins(12, 225, 12, 12); vl.setSpacing(10); vl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl = QLabel(dev_info["name"]); lbl.setStyleSheet("font-size: 16px; font-weight: 700; color: #F3F0F8; background: transparent;"); lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); vl.addWidget(lbl)
        row = QHBoxLayout(); row.addStretch(); row.addWidget(DeviceStatusPill(dev_info["conn"], dev_info["battery"])); row.addStretch(); vl.addLayout(row)
    def enterEvent(self, e): self.anim.stop(); self.anim.setStartValue(self._scale); self.anim.setEndValue(1.08); self.anim.start()
    def leaveEvent(self, e): self.anim.stop(); self.anim.setStartValue(self._scale); self.anim.setEndValue(1.0); self.anim.start()
    def mousePressEvent(self, e): self.on_pick(self.dev)
    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        mk = {"MX Master": "mx_master", "MX Master 2S": "mx_master_2s", "MX Master 3": "mx_master_3s", "MX Master 3S": "mx_master_3s", "MX Master 4": "mx_master_4"}.get(self.dev["name"], "mx_master_3s")
        sp = os.path.join(APP_DIR, f"{mk}.svg"); bw, bh = 135 * self._scale, 195 * self._scale; rx, ry = (self.width() - bw) / 2.0, 20 + (195 - bh) / 2.0
        if os.path.exists(sp):
            rx_xml = ET.fromstring(open(sp, encoding="utf-8").read())
            for pe in list(rx_xml.iter()):
                for ce in list(pe):
                    if ce.get("id", "") in {"switches", "mbleft", "mbright", "thback", "thfwd", "thmb_gest", "haptic"}: pe.remove(ce)
            for el in rx_xml.iter():
                if el.get("id", "") in {"controls", "scrollwheel", "thumbwheel", "modeswitch"}:
                    for sub in el.iter():
                        if "stroke" in sub.attrib: sub.set("stroke", "#00ffff")
                        if sub.get("fill") not in (None, "none"): sub.set("fill", "#00ffff")
                        if "style" in sub.attrib: sub.set("style", re.sub(r"stroke:[^;]+", "stroke:#00ffff", sub.get("style")))
            rnd = QSvgRenderer(QByteArray(ET.tostring(rx_xml, encoding="utf-8"))); ds = rnd.defaultSize()
            if ds.width() > 0 and ds.height() > 0:
                sc = min(bw / ds.width(), bh / ds.height()); nw, nh = ds.width() * sc, ds.height() * sc; rnd.render(p, QRectF(rx + (bw - nw) / 2.0, ry + (bh - nh) / 2.0, nw, nh))

class ShortcutRecorderEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent); self.setPlaceholderText("Klicke & drücke Tastenkombination...")
    def focusInEvent(self, e): super().focusInEvent(e); self.setStyleSheet("border: 1.5px solid #A855F7; background-color: #1A1626;")
    def focusOutEvent(self, e): super().focusOutEvent(e); self.setStyleSheet("")
    def keyPressEvent(self, e):
        k = e.key(); solo = {Qt.Key.Key_Control: "Control_L", Qt.Key.Key_Shift: "Shift_L", Qt.Key.Key_Alt: "Alt_L", Qt.Key.Key_Super_L: "Super_L", Qt.Key.Key_Super_R: "Super_L"}
        if k in solo: self.setText(solo[k]); e.accept(); return
        mods = [n for flag, n in [(Qt.KeyboardModifier.ControlModifier, "ctrl"), (Qt.KeyboardModifier.AltModifier, "alt"), (Qt.KeyboardModifier.ShiftModifier, "shift"), (Qt.KeyboardModifier.MetaModifier, "Super_L")] if e.modifiers() & flag]
        sp = {Qt.Key.Key_Return: "Return", Qt.Key.Key_Enter: "Return", Qt.Key.Key_Escape: "Escape", Qt.Key.Key_Tab: "Tab", Qt.Key.Key_Backspace: "BackSpace", Qt.Key.Key_Delete: "Delete", Qt.Key.Key_Space: "space", Qt.Key.Key_Plus: "plus", Qt.Key.Key_Minus: "minus", Qt.Key.Key_Left: "Left", Qt.Key.Key_Right: "Right", Qt.Key.Key_Up: "Up", Qt.Key.Key_Down: "Down"}
        if k in sp: ks = sp[k]
        elif Qt.Key.Key_F1 <= k <= Qt.Key.Key_F24: ks = f"F{k - Qt.Key.Key_F1 + 1}"
        else:
            tc = e.text()
            if tc and len(tc) == 1 and tc.isprintable() and "ctrl" not in mods and "alt" not in mods: self.setText(tc); e.accept(); return
            ks = chr(k).lower() if (Qt.Key.Key_A <= k <= Qt.Key.Key_Z or Qt.Key.Key_0 <= k <= Qt.Key.Key_9) else ""
        if ks: self.setText("+".join(mods + [ks]) if mods else ks)
        e.accept()

class GestureVisualPad(QWidget):
    def __init__(self, on_dir, parent=None):
        super().__init__(parent); self.on_dir, self.sel_dir, self.model = on_dir, "up", "MX Master 3S"; self.dir_values = {"up": "", "down": "", "left": "", "right": "", "click": ""}; self.setFixedSize(360, 252)
        self.zones = {"up": QRectF(125, 2, 110, 32), "down": QRectF(125, 218, 110, 32), "left": QRectF(4, 110, 102, 32), "right": QRectF(254, 110, 102, 32), "click": QRectF(132, 110, 96, 32)}
    def set_values(self, vals):
        for k in self.dir_values: self.dir_values[k] = vals.get(k, "") if isinstance(vals, dict) else ""
        self.update()
    def mousePressEvent(self, e):
        for d, r in self.zones.items():
            if r.contains(QPointF(e.position())): self.sel_dir = d; self.update(); self.on_dir(d); return
    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing); cx, cy = self.width() / 2.0, self.height() / 2.0
        mk = {"MX Master": "mx_master", "MX Master 2S": "mx_master_2s", "MX Master 3": "mx_master_3s", "MX Master 3S": "mx_master_3s", "MX Master 4": "mx_master_4"}.get(self.model, "mx_master_3s"); sp = os.path.join(APP_DIR, f"{mk}.svg")
        if os.path.exists(sp):
            rx_xml = ET.parse(sp).getroot()
            for el_x in list(rx_xml.iter()):
                for ch in list(el_x):
                    if any(k in ch.get("id", "") for k in ("thfwd", "thback", "thmb_gest", "modeswitch", "hotspot", "switch")): el_x.remove(ch)
                if "stroke" in el_x.attrib and el_x.get("stroke") != "none": el_x.set("stroke", "#00ffff"); el_x.set("stroke-width", str(float(el_x.get("stroke-width", "1.5")) * 1.9))
                if "style" in el_x.attrib: el_x.set("style", re.sub(r"stroke:[^;]+", "stroke:#00ffff", el_x.get("style")))
            rnd = QSvgRenderer(QByteArray(ET.tostring(rx_xml, encoding="utf-8"))); ds = rnd.defaultSize()
            if ds.width() > 0: sc = min(98.0 / ds.width(), 128.0 / ds.height()); rnd.render(p, QRectF(cx - ds.width()*sc/2, cy - ds.height()*sc/2, ds.width()*sc, ds.height()*sc))
        arrows = {"up": "↑", "down": "↓", "left": "←", "right": "→", "click": "●"}
        for d, r in self.zones.items():
            sel = (d == self.sel_dir); p.setPen(QPen(QColor("#C084FC" if sel else "#3A334F"), 1.6 if sel else 1.1)); p.setBrush(QBrush(QColor("#2D2142" if sel else "#121018"))); p.drawRoundedRect(r, 8, 8)
            val = self.dir_values.get(d) or "—"; val = val[:9] + "…" if len(val) > 10 else val; p.setPen(QColor("#FFFFFF" if sel else "#C8C1D6")); p.drawText(r, Qt.AlignmentFlag.AlignCenter, f"{arrows[d]} {val}")

class MouseVisualWidget(QWidget):
    def __init__(self, on_sel, parent=None):
        super().__init__(parent); self.on_sel, self.sel_slot, self.model = on_sel, "gesture_click", "MX Master 3S"; self.setMinimumSize(560, 440)
        self.anchors = json.load(open(ANCHORS_FILE, encoding="utf-8")) if os.path.exists(ANCHORS_FILE) else {}
        self.slots = {"forward": ("left", 55, "thfwd", 0.20, 0.47), "back": ("left", 125, "thback", 0.20, 0.54), "thumb_up": ("left", 205, "thumbwheel", 0.28, 0.48), "thumb_down": ("left", 275, "thumbwheel", 0.28, 0.50), "gesture_click": ("left", 355, "thmb_gest", 0.09, 0.59), "middle_click": ("right", 90, "scrollwheel", 0.61, 0.21), "mode_shift": ("right", 190, "modeswitch", 0.62, 0.39)}
        self.btns = {}
        for slot, (side, y, _, _, _) in self.slots.items():
            b = QPushButton(ACTION_LABELS[slot], self); b.setObjectName("HotspotBtn"); b.setFixedSize(b.sizeHint().width() + 24, 32); b.clicked.connect(lambda _, sl=slot: self.select_slot(sl)); self.btns[slot] = b
    def set_model(self, m): self.model = m; self.update()
    def select_slot(self, s):
        self.sel_slot = s
        for k, b in self.btns.items(): b.setProperty("selected", "true" if k == s else "false"); b.style().unpolish(b); b.style().polish(b)
        self.on_sel(s)
    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing); w, h = self.width(), self.height()
        mk = {"MX Master": "mx_master", "MX Master 2S": "mx_master_2s", "MX Master 3": "mx_master_3s", "MX Master 3S": "mx_master_3s", "MX Master 4": "mx_master_4"}.get(self.model, "mx_master_3s")
        sp = os.path.join(APP_DIR, f"{mk}.svg"); bw, bh = 240, 360; rx, ry, rw, rh = (w - bw) / 2.0, (h - bh) / 2.0, float(bw), float(bh)
        if os.path.exists(sp):
            rnd = QSvgRenderer(sp); ds = rnd.defaultSize()
            if ds.width() > 0 and ds.height() > 0: sc = min(bw / ds.width(), bh / ds.height()); rw, rh = ds.width() * sc, ds.height() * sc; rx, ry = (w - rw) / 2.0, (h - rh) / 2.0; rnd.render(p, QRectF(rx, ry, rw, rh))
        ma = self.anchors.get(mk, {})
        for slot, (side, y, a_key, fx, fy) in self.slots.items():
            b = self.btns[slot]; b.move(12 if side == "left" else w - b.width() - 12, y); ax, ay = ma.get(a_key, [fx, fy])
            if slot == "thumb_down": ay = min(0.95, ay + 0.035)
            tx, ty = rx + ax * rw, ry + ay * rh; sx = b.x() + b.width() if side == "left" else b.x(); sy = b.y() + b.height() / 2.0
            sel = (slot == self.sel_slot); p.setPen(QPen(QColor("#A855F7" if sel else "#3B354D"), 2.2 if sel else 1.4)); p.drawLine(QPointF(sx, sy), QPointF(tx, ty))

class LitioOptionlessWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Litio Optionless"); self.setWindowIcon(QIcon("/opt/ai-workspace/litio-optionless/litio-icon.svg")); self.setFixedSize(1080, 700)
        self.devices = json.load(open(DEVICES_FILE, encoding="utf-8")) if os.path.exists(DEVICES_FILE) else {"MX Master 3S": {"logid_name": "MX Master 3S", "cids": {"gesture": "0xc3", "back": "0x53", "forward": "0x56", "middle": "0x52", "mode_shift": "0xd7"}}}
        os.makedirs(CONFIG_DIR, exist_ok=True); ensure_config()
        self.config = json.load(open(PROFILES_FILE, encoding="utf-8")) if os.path.exists(PROFILES_FILE) else {"language": "de", "profiles": {"Global (Standard)": {"buttons": {}}}}
        self.connected = query_connected_mice(self.devices); self.active_dev = next(iter(self.connected)); self.current_profile, self.current_slot = "Global (Standard)", "gesture_click"
        if subprocess.run(["pgrep", "-f", "[l]ogimx_daemon.py"], stdout=subprocess.DEVNULL).returncode != 0:
            subprocess.Popen(["python3", "-u", os.path.join(APP_DIR, "litio_daemon.py")], env={**os.environ, "DISPLAY": os.environ.get("DISPLAY", ":0")}, stdout=open("/tmp/litio.log", "w"), stderr=subprocess.STDOUT)
        self.root_stack = QStackedWidget(); self.setCentralWidget(self.root_stack)
        self.root_stack.addWidget(self.build_picker_screen()); self.root_stack.addWidget(self.build_config_screen()); self.setup_tray()
        self.open_device(next(iter(self.connected))) if len(self.connected) == 1 else self.root_stack.setCurrentIndex(0)
    def build_picker_screen(self):
        w = QWidget(); vl = QVBoxLayout(w); vl.setContentsMargins(24, 26, 24, 24)
        hdr = QLabel("Litio Optionless"); hdr.setStyleSheet("font-size: 22px; font-weight: 800; color: #C084FC;"); hdr.setAlignment(Qt.AlignmentFlag.AlignCenter); vl.addWidget(hdr)
        sub = QLabel("Wähle ein verbundenes Gerät zur Konfiguration"); sub.setStyleSheet("color: #9C94AD; margin-bottom: 8px;"); sub.setAlignment(Qt.AlignmentFlag.AlignCenter); vl.addWidget(sub)
        self.carousel_stage = QWidget(); self.carousel_stage.setFixedSize(1032, 380)
        self.btn_prev = QPushButton("◀", self.carousel_stage); self.btn_prev.setObjectName("SecondaryBtn"); self.btn_prev.setFixedSize(42, 64); self.btn_prev.move(8, 158)
        self.btn_next = QPushButton("▶", self.carousel_stage); self.btn_next.setObjectName("SecondaryBtn"); self.btn_next.setFixedSize(42, 64); self.btn_next.move(982, 158)
        self.btn_prev.clicked.connect(lambda: self._shift_carousel(-1)); self.btn_next.clicked.connect(lambda: self._shift_carousel(1))
        self.carousel_offset = 0; self.card_widgets = {}; self._card_anims = []
        vl.addStretch(); vl.addWidget(self.carousel_stage, 0, Qt.AlignmentFlag.AlignCenter); vl.addStretch()
        self._refresh_picker_cards(animate=False)
        self.scan_timer = QTimer(self); self.scan_timer.timeout.connect(self._poll_devices); self.scan_timer.start(2200)
        foot = QHBoxLayout(); foot.addStretch(); ab = QPushButton("+ Gerät hinzufügen"); ab.setObjectName("SecondaryBtn"); ab.clicked.connect(self.open_add_device_overlay); foot.addWidget(ab); foot.addStretch(); vl.addLayout(foot); return w
    def open_add_device_overlay(self):
        ov = QFrame(self); ov.setGeometry(0, 0, self.width(), self.height()); ov.setStyleSheet("background-color: rgba(12, 10, 18, 215);")
        card = QFrame(ov); card.setObjectName("Card"); card.setFixedSize(520, 290); card.move((self.width() - 520) // 2, (self.height() - 290) // 2)
        cl = QVBoxLayout(card); cl.setContentsMargins(24, 22, 24, 22); cl.setSpacing(14)
        h = QLabel("+ Logitech-Maus verbinden"); h.setStyleSheet("font-size: 17px; font-weight: 700; color: #C084FC; background: transparent;"); cl.addWidget(h)
        info = QLabel("1. Halte die Easy-Switch-Taste (1 / 2 / 3) unter deiner Maus 3 Sekunden gedrückt, bis die LED schnell blinkt.\n\n2. Öffne die Bluetooth-Kopplung oder stecke deinen Logi Bolt / Unifying-Empfänger ein — Litio erkennt die Maus danach automatisch im Karussell."); info.setWordWrap(True); info.setStyleSheet("color: #E8E3F2; background: transparent;"); cl.addWidget(info); cl.addStretch()
        row = QHBoxLayout(); bt_b = QPushButton("Bluetooth-Kopplung öffnen"); bt_b.setObjectName("AccentBtn"); bt_b.clicked.connect(lambda: subprocess.Popen(["bash", "-c", "blueman-manager || cinnamon-settings bluetooth"])); row.addWidget(bt_b)
        cl_b = QPushButton("Schließen"); cl_b.setObjectName("SecondaryBtn"); cl_b.clicked.connect(ov.deleteLater); row.addWidget(cl_b); cl.addLayout(row); ov.show()
    def _shift_carousel(self, delta):
        self.carousel_offset = max(0, min(max(0, len(self.connected) - 3), self.carousel_offset + delta)); self._refresh_picker_cards(animate=True)
    def _refresh_picker_cards(self, animate=True):
        self._card_anims.clear(); total = len(self.connected); self.carousel_offset = max(0, min(max(0, total - 3), self.carousel_offset))
        visible = self.connected[self.carousel_offset:self.carousel_offset + 3]; vis_names = {d["name"] for d in visible}
        self.btn_prev.setVisible(total > 3 and self.carousel_offset > 0); self.btn_next.setVisible(total > 3 and self.carousel_offset + 3 < total)
        for name in list(self.card_widgets.keys()):
            if name not in vis_names: w = self.card_widgets.pop(name); w.hide(); w.deleteLater()
        cw, ch, gap = 260, 340, 28; n = len(visible); start_x = (self.carousel_stage.width() - (n * cw + max(0, n - 1) * gap)) // 2
        for idx, dev in enumerate(visible):
            tx, ty = start_x + idx * (cw + gap), 20; is_new = dev["name"] not in self.card_widgets
            card = self.card_widgets.get(dev["name"]) or DevicePickerCard(dev, self.open_device, self.carousel_stage); self.card_widgets[dev["name"]] = card
            if is_new:
                card.setGeometry(tx, ty + 14, cw, ch); card.show(); eff = QGraphicsOpacityEffect(card); card.setGraphicsEffect(eff)
                fa = QPropertyAnimation(eff, b"opacity", self); fa.setDuration(260); fa.setStartValue(0.0); fa.setEndValue(1.0); fa.start(); self._card_anims.append(fa)
            if animate:
                pa = QPropertyAnimation(card, b"geometry", self); pa.setDuration(260); pa.setEasingCurve(QEasingCurve.Type.OutCubic)
                pa.setStartValue(card.geometry()); pa.setEndValue(QRect(tx, ty, cw, ch)); pa.start(); self._card_anims.append(pa)
            else: card.setGeometry(tx, ty, cw, ch); card.show()
    def _poll_devices(self):
        fresh = query_connected_mice(self.devices); fresh_names = {d["name"] for d in fresh}
        if self.root_stack.currentIndex() == 1:
            if self.active_dev and self.active_dev.get("name") not in fresh_names:
                self.connected = fresh; self._refresh_picker_cards(animate=True); self.root_stack.setCurrentIndex(0)
            return
        if fresh != self.connected: self.connected = fresh; self._refresh_picker_cards(animate=True)
    def open_device(self, dev):
        self.active_dev = dev; self.mouse_vis.set_model(dev["name"]); self.foot_dev_lbl.setText(dev["name"]); self.foot_pill.set_status(dev["conn"], dev["battery"])
        self.on_profile_changed(self.current_profile); self.root_stack.setCurrentIndex(1)
    def build_config_screen(self):
        w = QWidget(); ml = QVBoxLayout(w); ml.setContentsMargins(0, 0, 0, 0); ml.setSpacing(0)
        top = QFrame(); top.setObjectName("TopBar"); top.setFixedHeight(58); tl = QHBoxLayout(top); tl.setContentsMargins(20, 0, 20, 0); tl.setSpacing(8)
        bb = QPushButton("← Geräte"); bb.setObjectName("SecondaryBtn"); bb.clicked.connect(lambda: self.root_stack.setCurrentIndex(0)); tl.addWidget(bb)
        self.tab_btns = []
        for idx, lbl in enumerate(["Maus", "Zeigen & Scrollen", "App-Profile"]):
            tb = QPushButton(lbl); tb.setObjectName("TabBtn"); tb.setProperty("active", "true" if idx == 0 else "false"); tb.clicked.connect(lambda _, i=idx: self.switch_tab(i)); tl.addWidget(tb); self.tab_btns.append(tb)
        tl.addStretch(); tl.addWidget(QLabel("Anwendung:"))
        self.prof_combo = QComboBox(); self.prof_combo.setMinimumWidth(200); self.prof_combo.addItems(list(self.config["profiles"].keys())); self.prof_combo.currentTextChanged.connect(self.on_profile_changed); tl.addWidget(self.prof_combo); ml.addWidget(top)
        self.tab_stack = QStackedWidget(); self.tab_stack.addWidget(self.build_mouse_tab()); self.tab_stack.addWidget(self.build_scroll_tab()); self.tab_stack.addWidget(self.build_profiles_tab()); ml.addWidget(self.tab_stack, 1)
        bot = QFrame(); bot.setObjectName("BottomBar"); bot.setFixedHeight(56); bl = QHBoxLayout(bot); bl.setContentsMargins(24, 0, 24, 0); bl.setSpacing(14)
        logo = QLabel("litio"); logo.setStyleSheet("font-size: 20px; font-weight: 900; color: #C084FC;"); bl.addWidget(logo); bl.addStretch()
        self.foot_dev_lbl = QLabel(self.active_dev["name"]); self.foot_dev_lbl.setStyleSheet("font-weight: 600;"); bl.addWidget(self.foot_dev_lbl)
        self.foot_pill = DeviceStatusPill(self.active_dev["conn"], self.active_dev["battery"]); bl.addWidget(self.foot_pill)
        ad = QPushButton("GERÄT HINZUFÜGEN"); ad.setObjectName("SecondaryBtn"); ad.clicked.connect(lambda: subprocess.Popen(["solaar", "pair"])); bl.addWidget(ad); ml.addWidget(bot); return w
    def build_mouse_tab(self):
        p = QWidget(); l = QHBoxLayout(p); l.setContentsMargins(24, 18, 24, 18); l.setSpacing(20)
        self.mouse_vis = MouseVisualWidget(self.select_slot); l.addWidget(self.mouse_vis, 3)
        right = QFrame(); right.setObjectName("Card"); right.setFixedWidth(360); rl = QVBoxLayout(right); rl.setContentsMargins(18, 18, 18, 18); rl.setSpacing(10)
        self.slot_title = QLabel("Daumen-Gestentaste"); self.slot_title.setStyleSheet("font-size: 16px; font-weight: 700; color: #C084FC;"); rl.addWidget(self.slot_title)
        self.preset_combo = QComboBox()
        for lbl, sc in PRESET_SHORTCUTS: self.preset_combo.addItem(lbl, sc)
        self.preset_combo.currentIndexChanged.connect(lambda i: self.shortcut_edit.setText(self.preset_combo.itemData(i)) if i > 0 else None); rl.addWidget(self.preset_combo)
        self.shortcut_edit = ShortcutRecorderEdit(); self.shortcut_edit.textChanged.connect(lambda t: self.gest_box.setVisible(t.strip() == "gesture_mode")); rl.addWidget(self.shortcut_edit)
        self.gest_box = QPushButton("⚙ 4-Wege-Gesten konfigurieren…"); self.gest_box.setObjectName("SecondaryBtn"); self.gest_box.clicked.connect(self.open_gesture_overlay)
        self.gest_values = {"up": "", "down": "", "left": "", "right": "", "click": ""}; self.gest_box.setVisible(False); rl.addWidget(self.gest_box)
        self.wm_class_edit = QLineEdit(); self.wm_class_edit.setPlaceholderText("WM_CLASS (z.B. inkscape, firefox)"); rl.addWidget(self.wm_class_edit)
        sb = QPushButton("Belegung speichern"); sb.setObjectName("AccentBtn"); sb.clicked.connect(self.save_current_slot); rl.addWidget(sb)
        self.ov_box = QLabel(""); self.ov_box.setStyleSheet("background-color: #100E15; border-radius: 8px; padding: 10px; font-family: monospace; font-size: 11px; color: #C084FC;"); self.ov_box.setWordWrap(True); rl.addWidget(self.ov_box); rl.addStretch(); l.addWidget(right); return p
    def open_gesture_overlay(self):
        ov = QFrame(self); ov.setGeometry(0, 0, self.width(), self.height()); ov.setStyleSheet("background-color: rgba(12, 10, 18, 215);")
        card = QFrame(ov); card.setObjectName("Card"); card.setFixedSize(740, 436); card.move((self.width() - 740) // 2, (self.height() - 436) // 2)
        cl = QVBoxLayout(card); cl.setContentsMargins(24, 20, 24, 20); cl.setSpacing(14)
        hdr = QLabel(f"4-Wege-Gesten — {ACTION_LABELS.get(self.current_slot, self.current_slot)}"); hdr.setStyleSheet("font-size: 17px; font-weight: 700; color: #C084FC; background: transparent;"); cl.addWidget(hdr)
        body = QHBoxLayout(); body.setSpacing(24); pad = GestureVisualPad(lambda d: _sel(d)); pad.model = self.mouse_vis.model; pad.set_values(self.gest_values); body.addWidget(pad)
        ctrl = QVBoxLayout(); ctrl.setSpacing(10); dlbl = QLabel("Richtung ↑ Hoch:"); dlbl.setStyleSheet("color: #E8E3F2; font-weight: 600; background: transparent;"); ctrl.addWidget(dlbl)
        pre = QComboBox()
        for lbl, sc in SUB_PRESET_SHORTCUTS: pre.addItem(lbl, sc)
        ctrl.addWidget(pre); ded = ShortcutRecorderEdit(); ctrl.addWidget(ded); ctrl.addStretch(); body.addLayout(ctrl, 1); cl.addLayout(body)
        names = {"up": "↑ Hoch", "down": "↓ Runter", "left": "← Links", "right": "→ Rechts", "click": "● Klick (ohne Bewegung)"}
        def _sel(d): dlbl.setText(f"Richtung {names.get(d, d)}:"); gv = self.gest_values.get(d, ""); gi = pre.findData(gv); pre.blockSignals(True); pre.setCurrentIndex(gi if gi > 0 else 0); pre.blockSignals(False); ded.blockSignals(True); ded.setText(gv); ded.blockSignals(False)
        _sel("up")
        def _chg(txt): self.gest_values[pad.sel_dir] = txt.strip(); pad.set_values(self.gest_values)
        pre.currentIndexChanged.connect(lambda i: ded.setText(pre.itemData(i)) if i > 0 else None); ded.textChanged.connect(_chg); _sel(pad.sel_dir)
        foot = QHBoxLayout(); foot.addStretch(); ok_b = QPushButton("Übernehmen & Schließen"); ok_b.setObjectName("AccentBtn"); ok_b.clicked.connect(lambda: (self.save_current_slot(), ov.deleteLater())); foot.addWidget(ok_b); cl.addLayout(foot); ov.show()
    def build_scroll_tab(self):
        p = QWidget(); l = QVBoxLayout(p); l.setContentsMargins(28, 24, 28, 24); c = QFrame(); c.setObjectName("Card"); cl = QVBoxLayout(c); cl.setContentsMargins(24, 22, 24, 22); cl.setSpacing(16)
        h = QLabel("Zeigen, Scrollen & Hardware-Brücke"); h.setStyleSheet("font-size: 17px; font-weight: 700; color: #C084FC;"); cl.addWidget(h)
        dpi_val = int(self.config.get("dpi", 1200))
        self.dpi_lbl = QLabel(f"Zeigergeschwindigkeit (DPI): {dpi_val} DPI"); self.dpi_lbl.setStyleSheet("font-weight: 600;"); cl.addWidget(self.dpi_lbl)
        self.dpi_slider = QSlider(Qt.Orientation.Horizontal); self.dpi_slider.setRange(400, 4000); self.dpi_slider.setSingleStep(100); self.dpi_slider.setValue(dpi_val)
        self.dpi_slider.valueChanged.connect(lambda v: self.dpi_lbl.setText(f"Zeigergeschwindigkeit (DPI): {v} DPI")); cl.addWidget(self.dpi_slider)
        ss_val = int(self.config.get("smartshift", {}).get("threshold", 15))
        self.ss_lbl = QLabel(f"SmartShift Freilauf-Schwelle: {ss_val}"); self.ss_lbl.setStyleSheet("font-weight: 600;"); cl.addWidget(self.ss_lbl)
        self.ss_slider = QSlider(Qt.Orientation.Horizontal); self.ss_slider.setRange(5, 50); self.ss_slider.setValue(ss_val)
        self.ss_slider.valueChanged.connect(lambda v: self.ss_lbl.setText(f"SmartShift Freilauf-Schwelle: {v}")); cl.addWidget(self.ss_slider)
        tq_val = int(self.config.get("smartshift", {}).get("torque", 50))
        self.tq_lbl = QLabel(f"Scrollrad-Widerstand (Raster-Drehmoment): {tq_val}%"); self.tq_lbl.setStyleSheet("font-weight: 600;"); cl.addWidget(self.tq_lbl)
        self.tq_slider = QSlider(Qt.Orientation.Horizontal); self.tq_slider.setRange(10, 100); self.tq_slider.setValue(tq_val)
        self.tq_slider.valueChanged.connect(lambda v: self.tq_lbl.setText(f"Scrollrad-Widerstand (Raster-Drehmoment): {v}%")); cl.addWidget(self.tq_slider)
        self.inv_scroll_cb = QCheckBox("Natürliches Scrollen (Scrollrad-Richtung invertieren)"); self.inv_scroll_cb.setChecked(bool(self.config.get("invert_scroll", False))); cl.addWidget(self.inv_scroll_cb)
        self.hw_btn = QPushButton("Einstellungen übernehmen & in Hardware schreiben"); self.hw_btn.setObjectName("AccentBtn"); self.hw_btn.clicked.connect(self.apply_hw); cl.addWidget(self.hw_btn); cl.addStretch(); l.addWidget(c); return p
    def build_profiles_tab(self):
        p = QWidget(); l = QVBoxLayout(p); l.setContentsMargins(28, 24, 28, 24); c = QFrame(); c.setObjectName("Card"); cl = QVBoxLayout(c); cl.setContentsMargins(24, 22, 24, 22); cl.setSpacing(14)
        h = QLabel("Anwendungs-Profile & Import / Export"); h.setStyleSheet("font-size: 17px; font-weight: 700; color: #C084FC;"); cl.addWidget(h)
        self.prof_list = QListWidget(); self.prof_list.addItems(list(self.config["profiles"].keys())); cl.addWidget(self.prof_list)
        r1 = QHBoxLayout()
        ab = QPushButton("+ Neues Profil"); ab.setObjectName("AccentBtn"); ab.clicked.connect(self.add_profile); r1.addWidget(ab)
        self.pick_win_btn = QPushButton("⊕ Fensterklasse per Klick erfassen"); self.pick_win_btn.setObjectName("SecondaryBtn"); self.pick_win_btn.clicked.connect(self.start_window_pick); r1.addWidget(self.pick_win_btn)
        dp = QPushButton("Duplizieren"); dp.setObjectName("SecondaryBtn"); dp.clicked.connect(self.dup_profile); r1.addWidget(dp); cl.addLayout(r1)
        r2 = QHBoxLayout()
        ex = QPushButton("↓ Profil exportieren (.json)"); ex.setObjectName("SecondaryBtn"); ex.clicked.connect(self.export_profile); r2.addWidget(ex)
        im = QPushButton("↑ Profil importieren (.json)"); im.setObjectName("SecondaryBtn"); im.clicked.connect(self.import_profile); r2.addWidget(im)
        db = QPushButton("Profil löschen"); db.setObjectName("SecondaryBtn"); db.clicked.connect(self.del_profile); r2.addWidget(db); cl.addLayout(r2)
        l.addWidget(c); return p
    def switch_tab(self, idx):
        self.tab_stack.setCurrentIndex(idx)
        for i, b in enumerate(self.tab_btns): b.setProperty("active", "true" if i == idx else "false"); b.style().unpolish(b); b.style().polish(b)
    def on_profile_changed(self, name):
        self.current_profile = name; pd = self.config["profiles"].get(name, {}); self.wm_class_edit.setText(", ".join(pd.get("wm_classes", []))); self.wm_class_edit.setEnabled(name != "Global (Standard)"); self.select_slot(self.current_slot)
    def select_slot(self, slot):
        self.current_slot = slot; self.slot_title.setText(ACTION_LABELS.get(slot, slot)); pd = self.config["profiles"].get(self.current_profile, {})
        self.shortcut_edit.setText(pd.get("buttons", {}).get(slot, "")); idx = self.preset_combo.findData(self.shortcut_edit.text().strip()); self.preset_combo.blockSignals(True); self.preset_combo.setCurrentIndex(idx if idx > 0 else 0); self.preset_combo.blockSignals(False); gd = pd.get("gestures", {}).get(slot, {})
        self.gest_values = {k: (gd.get(k, "") if isinstance(gd, dict) else "") for k in ("up", "down", "left", "right", "click")}
        btns = pd.get("buttons", {}); self.ov_box.setText("\n".join([f"{ACTION_LABELS.get(k, k)}: {btns.get(k, 'none')}" for k in ["gesture_click", "back", "forward", "thumb_up", "thumb_down", "middle_click", "mode_shift"]]))
    def save_current_slot(self):
        pd = self.config["profiles"][self.current_profile]
        if self.current_profile != "Global (Standard)": pd["wm_classes"] = [c.strip().lower() for c in self.wm_class_edit.text().split(",") if c.strip()]
        sc = self.shortcut_edit.text().strip()
        if not sc and self.current_profile != "Global (Standard)":
            pd.setdefault("buttons", {}).pop(self.current_slot, None)
            pd.get("gestures", {}).pop(self.current_slot, None)
        else:
            pd.setdefault("buttons", {})[self.current_slot] = sc or "none"
        if sc == "gesture_mode": pd.setdefault("gestures", {})[self.current_slot] = {"enabled": True, **self.gest_values}
        json.dump(self.config, open(PROFILES_FILE, "w", encoding="utf-8"), indent=2); self.select_slot(self.current_slot)
    def _sync_profiles_ui(self, select_name=None):
        json.dump(self.config, open(PROFILES_FILE, "w", encoding="utf-8"), indent=2)
        names = list(self.config["profiles"].keys())
        self.prof_list.clear(); self.prof_list.addItems(names)
        self.prof_combo.blockSignals(True); self.prof_combo.clear(); self.prof_combo.addItems(names); self.prof_combo.blockSignals(False)
        if select_name and select_name in names: self.prof_combo.setCurrentText(select_name)
    def add_profile(self):
        n, ok = QInputDialog.getText(self, "Neues Profil", "Profilname:")
        if ok and n.strip():
            self.config["profiles"][n.strip()] = {"wm_classes": [n.strip().lower()], "buttons": {}, "gestures": {}}
            self._sync_profiles_ui(n.strip())
    def dup_profile(self):
        it = self.prof_list.currentItem()
        if not it: return
        src = it.text(); n, ok = QInputDialog.getText(self, "Profil duplizieren", "Neuer Name:", text=f"{src} (Kopie)")
        if ok and n.strip():
            self.config["profiles"][n.strip()] = json.loads(json.dumps(self.config["profiles"][src]))
            self._sync_profiles_ui(n.strip())
    def del_profile(self):
        it = self.prof_list.currentItem()
        if not it or it.text() == "Global (Standard)": return
        ans = QMessageBox.question(self, "Profil löschen", f"Möchtest du das Profil „{it.text()}“ wirklich unwiderruflich löschen?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if ans == QMessageBox.StandardButton.Yes:
            del self.config["profiles"][it.text()]; self._sync_profiles_ui("Global (Standard)")
    def start_window_pick(self):
        self._pick_sec = 3; self.pick_win_btn.setEnabled(False); self.pick_win_btn.setText("Wechsle ins Fenster (3s)...")
        self._pick_tmr = QTimer(self); self._pick_tmr.timeout.connect(self._tick_window_pick); self._pick_tmr.start(1000)
    def _tick_window_pick(self):
        self._pick_sec -= 1
        if self._pick_sec > 0: self.pick_win_btn.setText(f"Wechsle ins Fenster ({self._pick_sec}s)..."); return
        self._pick_tmr.stop(); self.pick_win_btn.setEnabled(True); self.pick_win_btn.setText("⊕ Fensterklasse per Klick erfassen")
        try:
            wid = subprocess.check_output(["xdotool", "getactivewindow"], stderr=subprocess.DEVNULL).decode().strip()
            raw = subprocess.check_output(["xprop", "-id", wid, "WM_CLASS"], stderr=subprocess.DEVNULL).decode()
            parts = re.findall(r'"([^"]+)"', raw); wm = parts[-1].lower() if parts else ""
            if wm and "gui.py" not in wm:
                pname = parts[-1] if parts else wm
                self.config["profiles"][pname] = {"wm_classes": [wm], "buttons": {}, "gestures": {}}
                self._sync_profiles_ui(pname); self.on_profile_changed(pname)
        except Exception: pass
    def export_profile(self):
        it = self.prof_list.currentItem(); pname = it.text() if it else self.current_profile
        safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", pname).strip("_").lower() or "profil"
        default_fn = f"{datetime.date.today().strftime('%Y%m%d')}_litio_{safe}.json"
        path, _ = QFileDialog.getSaveFileName(self, "Profil exportieren", os.path.expanduser(f"~/{default_fn}"), "JSON (*.json)")
        if path:
            json.dump({"litio_profile": pname, "data": self.config["profiles"][pname]}, open(path, "w", encoding="utf-8"), indent=2)
    def import_profile(self):
        path, _ = QFileDialog.getOpenFileName(self, "Profil importieren", os.path.expanduser("~"), "JSON (*.json)")
        if not path: return
        raw = json.load(open(path, encoding="utf-8"))
        if "litio_profile" in raw and "data" in raw:
            self.config["profiles"][raw["litio_profile"]] = raw["data"]; self._sync_profiles_ui(raw["litio_profile"])
        elif isinstance(raw, dict):
            for k, v in raw.items():
                if isinstance(v, dict) and "buttons" in v: self.config["profiles"][k] = v
            self._sync_profiles_ui()
    def apply_hw(self):
        dpi = self.dpi_slider.value(); thr = self.ss_slider.value(); tq = self.tq_slider.value(); inv = self.inv_scroll_cb.isChecked()
        tq_hw = max(25, min(255, int(tq * 2.55)))
        self.config["dpi"] = dpi; self.config["invert_scroll"] = inv; self.config["smartshift"] = {"on": True, "threshold": thr, "torque": tq}
        json.dump(self.config, open(PROFILES_FILE, "w", encoding="utf-8"), indent=2)
        inv_s = "true" if inv else "false"; blocks = []
        for m_name, d in self.devices.items():
            if "4" in m_name: continue
            c = d["cids"]; tq_s = f" torque: {tq_hw};" if "3" in m_name else ""
            ss_line = f"    smartshift: {{ on: true; threshold: {thr};{tq_s} }};\n"
            blocks.append(f'{{\n    name: "{d.get("logid_name", m_name)}";\n{ss_line}    hiresscroll: {{ hires: false; invert: {inv_s}; target: false; }};\n    dpi: {dpi};\n    thumbwheel: {{ divert: false; invert: false; left: {{ mode: "OnInterval"; interval: 2; action: {{ type: "Keypress"; keys: ["KEY_F17"]; }}; }}; right: {{ mode: "OnInterval"; interval: 2; action: {{ type: "Keypress"; keys: ["KEY_F18"]; }}; }}; }};\n    buttons: (\n        {{ cid: {c["gesture"]}; action = {{ type: "Keypress"; keys: ["KEY_F13"]; }}; }},\n        {{ cid: {c["back"]}; action = {{ type: "Keypress"; keys: ["KEY_F14"]; }}; }},\n        {{ cid: {c["forward"]}; action = {{ type: "Keypress"; keys: ["KEY_F15"]; }}; }},\n        {{ cid: {c["middle"]}; action = {{ type: "Keypress"; keys: ["KEY_F16"]; }}; }},\n        {{ cid: {c["mode_shift"]}; action = {{ type: "Keypress"; keys: ["KEY_F19"]; }}; }}\n    );\n}}')
        open("/tmp/logid_new.cfg", "w").write("devices: (\n" + ",\n".join(blocks) + "\n);\n")
        subprocess.run(["pkexec", "bash", "-c", "cp /tmp/logid_new.cfg /etc/logid.cfg && systemctl restart logid"])
        subprocess.run(["pkill", "-f", "[l]itio_daemon.py"], stderr=subprocess.DEVNULL)
        subprocess.Popen(["python3", "-u", os.path.join(APP_DIR, "litio_daemon.py")], env={**os.environ, "DISPLAY": os.environ.get("DISPLAY", ":0")}, stdout=open("/tmp/litio.log", "w"), stderr=subprocess.STDOUT)
        self.hw_btn.setText("✓ Gespeichert & Profile aktiv"); QTimer.singleShot(3000, lambda: self.hw_btn.setText("Einstellungen übernehmen & in Hardware schreiben"))
    def setup_tray(self):
        self.tray = QSystemTrayIcon(QIcon("/opt/ai-workspace/litio-optionless/litio-icon.svg"), self); self.tray.setToolTip("LITIO"); m = QMenu(); m.addAction("Öffnen", self.showNormal); m.addAction("Beenden", QApplication.instance().quit); self.tray.setContextMenu(m)
        self.tray.activated.connect(lambda r: (self.showNormal(), self._center_on_screen(), self.raise_(), self.activateWindow()) if r in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick) else None)
        self.tray.show()
    def _center_on_screen(self):
        scr = QApplication.primaryScreen()
        if scr:
            fg = self.frameGeometry(); fg.moveCenter(scr.availableGeometry().center()); self.move(fg.topLeft())
    def closeEvent(self, ev):
        ev.ignore(); self.hide()
if __name__ == "__main__":
    import socket
    _lock_sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        _lock_sock.bind("\0litio_optionless_single_instance")
    except OSError:
        sys.exit(0)
    app = QApplication(sys.argv); app.setApplicationName("LITIO"); app.setDesktopFileName("litio-optionless"); app.setStyleSheet(STYLESHEET); w = LitioOptionlessWindow()
    if "--minimized" not in sys.argv: w.show(); w._center_on_screen()
    sys.exit(app.exec())
