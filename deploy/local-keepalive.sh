#!/usr/bin/env bash
# Keep a local `field-notes serve` up. Designed for cron:
#   @reboot      /path/to/local-keepalive.sh
#   */2 * * * *  /path/to/local-keepalive.sh
# If the server is down (crash, reboot, never started) it relaunches it detached.
# A lock prevents racing launches; crash output is kept in server.log so a real
# bug stays visible instead of being silently resurrected.
set -u
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$HOME/.local/bin"

PORT="${FIELD_NOTES_PORT:-8000}"
DATA_DIR="${FIELD_NOTES_DATA_DIR:-$HOME/.field-notes}"
# Resolve the field-notes binary: explicit override, else PATH, else fail loud.
BIN="${FIELD_NOTES_BIN:-$(command -v field-notes || true)}"

LOCK="$DATA_DIR/.keepalive.lock"; KLOG="$DATA_DIR/keepalive.log"; SLOG="$DATA_DIR/server.log"
mkdir -p "$DATA_DIR"
exec 9>"$LOCK"; flock -n 9 || exit 0
ts() { date '+%Y-%m-%d %H:%M:%S'; }

if [ -z "$BIN" ]; then echo "[$(ts)] field-notes binary not found (set FIELD_NOTES_BIN)" >> "$KLOG"; exit 1; fi
if curl -fsS --max-time 5 "http://127.0.0.1:$PORT/healthz" >/dev/null 2>&1; then exit 0; fi

echo "[$(ts)] server not healthy on :$PORT — relaunching" >> "$KLOG"
setsid nohup "$BIN" serve --host 127.0.0.1 --port "$PORT" --data-dir "$DATA_DIR" --no-browser >> "$SLOG" 2>&1 &
echo "[$(ts)] launched pid $! (logging to $SLOG)" >> "$KLOG"
