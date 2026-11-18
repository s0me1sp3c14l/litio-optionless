#!/usr/bin/env bash
set -e
APP_DIR="/opt/ai-workspace/litio-optionless"
sudo apt-get update && sudo apt-get install -y logid python3-pyqt6 python3-pyqt6.qtsvg python3-evdev python3-pynput xdotool x11-utils
sudo mkdir -p "$APP_DIR"
sudo cp -r ./* "$APP_DIR"/
sudo chmod +x "$APP_DIR/gui.py" "$APP_DIR/litio_daemon.py" "$APP_DIR/start.sh"
sudo ln -sf "$APP_DIR/start.sh" /usr/local/bin/litio
mkdir -p ~/.local/share/applications
cat << 'DESKTOP' > ~/.local/share/applications/litio-optionless.desktop
[Desktop Entry]
Name=Litio Optionless
Comment=Linux Mouse & Gesture Configuration Tool
Exec=/usr/local/bin/litio
Icon=input-mouse
Terminal=false
Type=Application
Categories=Settings;HardwareSettings;
DESKTOP
echo "Installation abgeschlossen! Starte mit: litio"
