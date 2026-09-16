#!/usr/bin/env bash
set -euo pipefail

USUARIO=ponte
CHAVE='ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDFmhu8QkiIPwN0gqmYSmSrN9E2Wr8PdAk2N3qglquu6 davi@DESKTOP-V8F32JA'
CONFIG='/etc/ssh/sshd_config.d/90-ponte.conf'
HOME_USUARIO="/home/$USUARIO"
AUTHORIZED_KEYS="$HOME_USUARIO/.ssh/authorized_keys"
TEMP_CONFIG=$(mktemp)
TEMP_KEYS=$(mktemp)
BACKUP_DIR=$(mktemp -d /var/backups/ponte-ssh.XXXXXX)

cleanup() {
  rm -f "$TEMP_CONFIG" "$TEMP_KEYS"
}
trap cleanup EXIT

[ "$(id -u)" -eq 0 ] || {
  echo "ERRO: o provisionador SSH precisa de root via sudo -n; nada foi alterado." >&2
  exit 1
}

cat > "$TEMP_CONFIG" <<'EOF'
Match User ponte
    AuthenticationMethods publickey
    PasswordAuthentication no
    KbdInteractiveAuthentication no
    PubkeyAuthentication yes
    AllowTcpForwarding local
    PermitOpen 127.0.0.1:8443
    PermitTTY no
    X11Forwarding no
    AllowAgentForwarding no
    PermitTunnel no
    ForceCommand /usr/bin/false
Match all
EOF
printf 'no-agent-forwarding,no-X11-forwarding,no-pty,no-user-rc,%s\n' "$CHAVE" > "$TEMP_KEYS"

if id "$USUARIO" >/dev/null 2>&1; then
  echo "OK: usuário $USUARIO já existe; configuração será reconciliada."
else
  useradd --system --create-home --shell /usr/sbin/nologin "$USUARIO"
  passwd --lock "$USUARIO" >/dev/null
fi

install -d -m 700 -o "$USUARIO" -g "$USUARIO" "$HOME_USUARIO/.ssh"

if [ -f "$CONFIG" ]; then cp -a "$CONFIG" "$BACKUP_DIR/90-ponte.conf"; fi
if [ -f "$AUTHORIZED_KEYS" ]; then cp -a "$AUTHORIZED_KEYS" "$BACKUP_DIR/authorized_keys"; fi
cp "$TEMP_CONFIG" "$CONFIG"
install -m 600 -o "$USUARIO" -g "$USUARIO" "$TEMP_KEYS" "$AUTHORIZED_KEYS"

if ! sshd -t; then
  echo "ERRO: sshd -t reprovou a configuração da ponte; restaurando antes do reload." >&2
  if [ -f "$BACKUP_DIR/90-ponte.conf" ]; then cp -a "$BACKUP_DIR/90-ponte.conf" "$CONFIG"; else rm -f "$CONFIG"; fi
  if [ -f "$BACKUP_DIR/authorized_keys" ]; then cp -a "$BACKUP_DIR/authorized_keys" "$AUTHORIZED_KEYS"; else rm -f "$AUTHORIZED_KEYS"; fi
  exit 1
fi
echo "OK: sshd -t verde antes do reload."

if ! systemctl reload sshd 2>/dev/null && ! systemctl reload ssh 2>/dev/null; then
  echo "ERRO: reload do SSH falhou; restaurando os arquivos anteriores." >&2
  if [ -f "$BACKUP_DIR/90-ponte.conf" ]; then cp -a "$BACKUP_DIR/90-ponte.conf" "$CONFIG"; else rm -f "$CONFIG"; fi
  if [ -f "$BACKUP_DIR/authorized_keys" ]; then cp -a "$BACKUP_DIR/authorized_keys" "$AUTHORIZED_KEYS"; else rm -f "$AUTHORIZED_KEYS"; fi
  sshd -t
  exit 1
fi

echo "OK: usuário $USUARIO provisionado; reload do SSH concluído."
echo "Backup SSH: $BACKUP_DIR"
