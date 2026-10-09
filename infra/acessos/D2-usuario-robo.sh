#!/usr/bin/env bash
# Rodar como root na VPS. Idempotente. Uso: D2-usuario-robo.sh "<chave publica do robo>"
set -euo pipefail
CHAVE="${1:-}"

getent group plataforma >/dev/null || groupadd plataforma
id robo >/dev/null 2>&1 || useradd -m -s /bin/bash -G plataforma robo
gpasswd -d robo docker >/dev/null 2>&1 || true
usermod -aG plataforma robo
id -nG deploy | grep -qw plataforma || usermod -aG plataforma deploy

mkdir -p /opt/plataforma/entregas /opt/plataforma/bin
chgrp plataforma /opt/plataforma/entregas
chmod g+ws /opt/plataforma/entregas

cat > /opt/plataforma/bin/robo-comando <<'DISP'
#!/bin/sh
set -eu
set -- ${SSH_ORIGINAL_COMMAND:-}
CMD="${1:-}"
[ "$#" -gt 0 ] && shift
case "$CMD" in
  entregar|consultar|estado)
    exec python3 /opt/plataforma/integrador/entregas.py "$CMD" "$@" ;;
  *)
    echo "comando nao permitido: use entregar, consultar ou estado" >&2
    exit 2 ;;
esac
DISP
chown root:plataforma /opt/plataforma/bin/robo-comando
chmod 755 /opt/plataforma/bin/robo-comando

install -d -m 700 -o robo -g robo /home/robo/.ssh
touch /home/robo/.ssh/authorized_keys
chown robo:robo /home/robo/.ssh/authorized_keys
chmod 600 /home/robo/.ssh/authorized_keys

if [ -n "$CHAVE" ]; then
  LINHA="command=\"/opt/plataforma/bin/robo-comando\",no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty $CHAVE"
  grep -qxF "$LINHA" /home/robo/.ssh/authorized_keys || echo "$LINHA" >> /home/robo/.ssh/authorized_keys
  echo "Linha de authorized_keys do robo:"
  echo "$LINHA"
else
  echo "Linha modelo (cole a chave publica no fim):"
  echo "command=\"/opt/plataforma/bin/robo-comando\",no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty <CHAVE-PUBLICA>"
fi
