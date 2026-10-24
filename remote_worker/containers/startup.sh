#!/bin/sh
export FOLD_ENGINE_ROLE=cloud
export FOLD_COMPUTE_PROVIDER=${FOLD_COMPUTE_PROVIDER:-vast}
set -eu
if [ -n "${RAPID_DEFAULT_CONFIG:-}" ] && [ ! -e "${RAPID_ROOT}/config.json" ]; then
  mkdir -p "$RAPID_ROOT"
  cp "$RAPID_DEFAULT_CONFIG" "$RAPID_ROOT/config.json"
fi
python3 - <<'PY'
import json,os,pathlib
root=pathlib.Path.home()/'.local/share/fold-studio-rapid';root.mkdir(parents=True,exist_ok=True,mode=0o700)
active=root/'active.json'
if not active.exists():active.write_text(json.dumps({'state':'installed','version':'0.2.0','python':'/opt/fold-rapid/bin/python','release':os.environ['RAPID_RELEASE_DIR'],'root':os.environ['RAPID_ROOT']}))
PY
if [ "${1:-}" != serve-ssh ]; then exec "$@"; fi
# Vast injects the user's public key. Never enable passwords or an anonymous API.
if [ -n "${PUBLIC_KEY:-}" ]; then
  case "$PUBLIC_KEY" in ssh-ed25519\ *|ssh-rsa\ *|ecdsa-sha2-*\ *) ;; *) echo 'Invalid injected SSH public key' >&2; exit 2 ;; esac
  printf '%s\n' "$PUBLIC_KEY" >> /root/.ssh/authorized_keys
fi
test -s /root/.ssh/authorized_keys || { echo 'Supply PUBLIC_KEY or mount authorized_keys; refusing unauthenticated startup.' >&2; exit 2; }
chmod 600 /root/.ssh/authorized_keys
ssh-keygen -A
exec /usr/sbin/sshd -D -e -o PasswordAuthentication=no -o KbdInteractiveAuthentication=no -o PermitRootLogin=prohibit-password -o AllowTcpForwarding=no -o X11Forwarding=no
