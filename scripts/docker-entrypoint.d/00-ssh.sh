#!/bin/sh
# 00-ssh.sh — Drop-in: enable SSH server in the container.
#
# Copied to /docker-entrypoint.d/ by the Dockerfile.
# Run automatically by the generic entrypoint.
#
# Environment variables:
#   SSH_ENABLED        — true/false (default: true)
#   SSH_ROOT_PASSWORD  — root password (REQUIRED if SSH_ENABLED=true)
#   SSH_PORT           — SSH port (default: 22)

if [ "${SSH_ENABLED}" != "true" ]; then
    log "SSH disabled (SSH_ENABLED=${SSH_ENABLED})"
    return 0 2>/dev/null || exit 0
fi

# Verify password
if [ -z "${SSH_ROOT_PASSWORD}" ]; then
    log "WARN: SSH_ROOT_PASSWORD not set — sshd will not start"
    log "WARN: Use: docker run -e SSH_ROOT_PASSWORD=..."
    return 0 2>/dev/null || exit 0
fi

log "SSH enabled on port ${SSH_PORT:-22}"

# Set root password
if echo "root:${SSH_ROOT_PASSWORD}" | chpasswd 2>/dev/null; then
    log "Root password set"
else
    log "WARN: chpasswd failed, SSH may not work"
fi

# Update port if different from default
if [ -n "${SSH_PORT}" ] && [ "${SSH_PORT}" != "22" ]; then
    sed -i "s/^Port .*/Port ${SSH_PORT}/" /etc/ssh/sshd_config
    log "SSH port set to ${SSH_PORT}"
fi

# Generate host keys (clear any empty leftover files first)
rm -f /etc/ssh/ssh_host_*_key /etc/ssh/ssh_host_*_key.pub 2>/dev/null
ssh-keygen -A 2>/dev/null
log "Host keys generated"

# Start sshd in background
/usr/sbin/sshd -D -e &
SSHD_PID=$!

# Verify it started
sleep 0.5
if kill -0 "$SSHD_PID" 2>/dev/null; then
    log "SSH server started (PID: ${SSHD_PID})"
else
    log "WARN: sshd did not start, continuing without SSH"
fi
