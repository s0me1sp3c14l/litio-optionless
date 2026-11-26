#!/usr/bin/env python3
import os, sys, json, math, signal, threading
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import Qt, QPointF, QRectF, QTimer
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QCursor, QPainterPath

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import haptic_mx4, litio_daemon

PROFILES_FILE = os.path.expanduser("~/.config/litio-optionless/profiles.json")
PID_FILE = "/tmp/litio_orbit.pid"
DEFAULT_SLOTS = [
    {"label": "Kopieren", "icon": "📋", "action": "ctrl+c"},
    {"label": "Einfügen", "icon": "📥", "action": "ctrl+v"},
    {"label": "Play/Pause", "icon": "⏯", "action": "XF86AudioPlay"},
    {"label": "Nächster", "icon": "⏭", "action": "XF86AudioNext"},
    {"label": "Desktop →", "icon": "🖥", "action": "ctrl+alt+right"},
    {"label": "Fenster", "icon": "🗔", "action": "alt+tab"},
    {"label": "Desktop ←", "icon": "🖥", "action": "ctrl+alt+left"},
    {"label": "Stumm", "icon": "🔇", "action": "XF86AudioMute"},
]

class OrbitRingOverlay(QWidget):
    def __init__(self, slots):
        super().__init__()
        self.slots, self.hovered = slots if slots else DEFAULT_SLOTS, -1
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool | Qt.WindowType.X11BypassWindowManagerHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(440, 440)
        pos = QCursor.pos(); scr = QApplication.primaryScreen().availableGeometry()
        self.move(max(scr.left() + 8, min(pos.x() - 220, scr.right() - 448)), max(scr.top() + 8, min(pos.y() - 220, scr.bottom() - 448)))
        self.setMouseTracking(True)

    def _update_hover(self, gx, gy):
        dx, dy = (gx - self.x()) - 220, (gy - self.y()) - 220
        dist = math.hypot(dx, dy)
        idx = int(((math.degrees(math.atan2(dy, dx)) + 90 + 22.5) % 360) // 45) % len(self.slots) if 78 <= dist <= 215 else -1
        if idx != self.hovered:
            self.hovered = idx
            if idx >= 0: threading.Thread(target=lambda: haptic_mx4.play_haptic(0), daemon=True).start()
            self.update()

    def trigger_and_close(self):
        if self.hovered >= 0:
            act = self.slots[self.hovered].get("action", "")
            self.hide(); QApplication.processEvents(); litio_daemon.execute_action(act, 3, True)
        QApplication.quit()

    def mouseMoveEvent(self, ev): self._update_hover(int(ev.globalPosition().x()), int(ev.globalPosition().y()))
    def mousePressEvent(self, ev): self.trigger_and_close() if (ev.button() == Qt.MouseButton.LeftButton and self.hovered >= 0) else QApplication.quit()
    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key.Key_Escape: QApplication.quit()

    def paintEvent(self, ev):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        ring = QPainterPath(); ring.addEllipse(QPointF(220, 220), 204, 204)
        hole = QPainterPath(); hole.addEllipse(QPointF(220, 220), 76, 76)
        p.setPen(QPen(QColor(147, 51, 234, 120), 2)); p.setBrush(QBrush(QColor(20, 18, 26, 210)))
        p.drawPath(ring.subtracted(hole))
        for i, item in enumerate(self.slots):
            rad = math.radians(i * (360 / len(self.slots)) - 90)
            bx, by = 220 + math.cos(rad) * 140, 220 + math.sin(rad) * 140
            act = (i == self.hovered)
            p.setPen(QPen(QColor("#E9D5FF" if act else "#6B21A8"), 2.5 if act else 1.5))
            p.setBrush(QBrush(QColor("#9333EA" if act else "#231E30")))
            rb = 44 if act else 39; p.drawEllipse(QPointF(bx, by), rb, rb)
            p.setPen(QColor("#FFFFFF")); p.setFont(QFont("Sans", 15))
            p.drawText(QRectF(bx - 36, by - 27, 72, 28), Qt.AlignmentFlag.AlignCenter, item.get("icon", "•"))
            p.setFont(QFont("Sans", 8, QFont.Weight.Bold if act else QFont.Weight.Normal))
            p.drawText(QRectF(bx - 38, by + 4, 76, 22), Qt.AlignmentFlag.AlignCenter, item.get("label", ""))

class OrbitVisualPad(QWidget):
    def __init__(self, slots, on_pick):
        super().__init__(); self.slots, self.on_pick, self.sel = slots, on_pick, 0
        self.setFixedSize(310, 310); self.setCursor(Qt.CursorShape.PointingHandCursor)
    def mousePressEvent(self, ev):
        for i in range(8):
            rad = math.radians(i * 45 - 90)
            if math.hypot(ev.position().x() - (155 + math.cos(rad) * 102), ev.position().y() - (155 + math.sin(rad) * 102)) <= 34:
                self.sel = i; self.update(); self.on_pick(i); break
    def paintEvent(self, ev):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        ring = QPainterPath(); ring.addEllipse(QPointF(155, 155), 146, 146); hole = QPainterPath(); hole.addEllipse(QPointF(155, 155), 52, 52)
        p.setPen(QPen(QColor("#3B2D5E"), 2)); p.setBrush(QBrush(QColor("#14121A"))); p.drawPath(ring.subtracted(hole))
        for i, item in enumerate(self.slots):
            rad = math.radians(i * 45 - 90); bx, by = 155 + math.cos(rad) * 102, 155 + math.sin(rad) * 102; act = (i == self.sel)
            p.setPen(QPen(QColor("#E9D5FF" if act else "#581C87"), 2.5 if act else 1.5)); p.setBrush(QBrush(QColor("#9333EA" if act else "#231E30")))
            p.drawEllipse(QPointF(bx, by), 31, 31); p.setPen(QColor("#FFFFFF")); p.setFont(QFont("Sans", 12))
            p.drawText(QRectF(bx - 28, by - 21, 56, 22), Qt.AlignmentFlag.AlignCenter, item.get("icon", "•"))
            p.setFont(QFont("Sans", 7, QFont.Weight.Bold if act else QFont.Weight.Normal)); p.drawText(QRectF(bx - 30, by + 1, 60, 20), Qt.AlignmentFlag.AlignCenter, item.get("label", ""))

if __name__ == "__main__":
    open(PID_FILE, "w").write(str(os.getpid()))
    app = QApplication(sys.argv)
    cfg = json.load(open(PROFILES_FILE, encoding="utf-8")) if os.path.exists(PROFILES_FILE) else {}
    w = OrbitRingOverlay(cfg.get("orbit_ring", DEFAULT_SLOTS))
    signal.signal(signal.SIGUSR1, lambda *_: QTimer.singleShot(0, w.trigger_and_close))
    signal.signal(signal.SIGTERM, lambda *_: QTimer.singleShot(0, QApplication.quit))
    t = QTimer(); t.timeout.connect(lambda: w._update_hover(QCursor.pos().x(), QCursor.pos().y())); t.start(25)
    w.show(); w.activateWindow()
    try: sys.exit(app.exec())
    finally:
        if os.path.exists(PID_FILE): os.remove(PID_FILE)
