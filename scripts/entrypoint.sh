#!/bin/sh
# entrypoint.sh — Generic, reusable entrypoint for Docker containers.
#
# Behavior:
#   1. Runs every .sh script in /docker-entrypoint.d/ in lexical order
#   2. Passes control to the Dockerfile CMD via exec "$@"
#
# Use in Dockerfile:
#   COPY entrypoint.sh /entrypoint.sh
#   RUN chmod +x /entrypoint.sh
#   ENTRYPOINT ["/entrypoint.sh"]
#   CMD ["python3", "-u", "/app/myapp.py"]
#
# To add services (SSH, logging, etc.):
#   Drop a .sh script into /docker-entrypoint.d/.
#   It will run automatically before the application.

# Do NOT use 'set -e' — if an init script fails, the app must still start.

log() {
    echo "[$(date +%H:%M:%S)] [ENTRYPOINT] $1"
}

log "=== Container started ==="
log "PID: $$"

# ── Run drop-in init scripts ─────────────────────────────────────────

INIT_DIR="/docker-entrypoint.d"

if [ -d "${INIT_DIR}" ]; then
    for f in "${INIT_DIR}"/*.sh; do
        [ -f "$f" ] || continue
        log "Running init script: $(basename "$f")"
        . "$f"
    done
else
    log "No ${INIT_DIR} directory, skipping init scripts"
fi

# ── Start application (Dockerfile CMD) ───────────────────────────────

if [ $# -gt 0 ]; then
    log "Starting command: $*"
    exec "$@"
else
    log "ERROR: no CMD specified in Dockerfile or docker run command line"
    exit 1
fi
