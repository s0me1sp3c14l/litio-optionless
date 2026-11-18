#!/usr/bin/env bash
cd /opt/ai-workspace/litio-optionless
pgrep -f "litio_daemon.py" >/dev/null || python3 litio_daemon.py &
python3 gui.py
