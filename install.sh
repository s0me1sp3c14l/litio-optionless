#!/usr/bin/env bash
set -e
APP_DIR="/opt/ai-workspace/litio-optionless"
sudo apt-get update
sudo apt-get install -y python3-pyqt6 python3-pyqt6.qtsvg python3-evdev python3-pynput xdotool x11-utils playerctl
sudo apt-get install -y logid 2>/dev/null || sudo apt-get install -y logiops 2>/dev/null || echo "Hinweis: logid/logiops nicht in apt gefunden (MX Master 4 Bridge läuft nativ)."
sudo mkdir -p "$APP_DIR"
sudo cp -r ./* "$APP_DIR"/
sudo chmod +x "$APP_DIR/gui.py" "$APP_DIR/litio_daemon.py" "$APP_DIR/start.sh" "$APP_DIR/orbit_ring.py"
sudo ln -sf "$APP_DIR/start.sh" /usr/local/bin/litio
echo 'SUBSYSTEM=="hidraw", ATTRS{idVendor}=="046d", ATTRS{idProduct}=="c548", MODE="0666"' | sudo tee /etc/udev/rules.d/99-litio-bolt.rules >/dev/null
sudo udevadm control --reload-rules 2>/dev/null || true
sudo udevadm trigger 2>/dev/null || true
sudo mkdir -p /usr/share/icons/hicolor/scalable/apps /usr/share/icons/hicolor/256x256/apps
sudo cp "$APP_DIR/litio-icon.svg" /usr/share/icons/hicolor/scalable/apps/litio-optionless.svg
sudo cp "$APP_DIR/litio-icon.png" /usr/share/icons/hicolor/256x256/apps/litio-optionless.png
sudo gtk-update-icon-cache -f /usr/share/icons/hicolor 2>/dev/null || true
mkdir -p ~/.local/share/applications
cat << 'DESKTOP' > ~/.local/share/applications/litio-optionless.desktop
[Desktop Entry]
Name=Litio Optionless
Comment=Linux Mouse & Gesture Configuration Tool
Exec=/usr/local/bin/litio
Icon=litio-optionless
Terminal=false
Type=Application
Categories=Settings;HardwareSettings;
DESKTOP
update-desktop-database ~/.local/share/applications 2>/dev/null || true
echo "Installation abgeschlossen! Starte mit: litio"
