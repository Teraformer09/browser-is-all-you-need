#!/usr/bin/env bash
set -euo pipefail

mkdir -p /var/run/sshd /root/.ssh
chmod 700 /root/.ssh

if [[ -n "${PUBLIC_KEY:-}" ]]; then
  echo "$PUBLIC_KEY" > /root/.ssh/authorized_keys
  chmod 600 /root/.ssh/authorized_keys
fi

if [[ -n "${SSH_PORT:-}" ]]; then
  sed -i '/^#*Port /d' /etc/ssh/sshd_config
  echo "Port $SSH_PORT" >> /etc/ssh/sshd_config
fi

if [[ -z "$(ls /etc/ssh/ssh_host_* 2>/dev/null || true)" ]]; then
  ssh-keygen -A
fi

echo "Starting SSH server on port ${SSH_PORT:-22}"
exec /usr/sbin/sshd -D
