#!/usr/bin/env bash
cd /opt/ai-workspace/litio-optionless
pgrep -f "[l]itio_daemon.py" >/dev/null || DISPLAY=${DISPLAY:-:0} python3 -u litio_daemon.py >/tmp/litio.log 2>&1 &
exec python3 gui.py "$@"
