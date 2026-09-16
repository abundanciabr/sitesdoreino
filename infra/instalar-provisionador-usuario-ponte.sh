#!/usr/bin/env bash
set -euo pipefail

ORIGEM=${1:?informe o caminho local de infra/provisionar-usuario-ponte.sh}
DESTINO=/usr/local/sbin/provisionar-usuario-ponte
SUDOERS=/etc/sudoers.d/90-deploy-provisionar-ponte

[ "$(id -u)" -eq 0 ] || {
  echo "ERRO: rode este instalador como root; nada foi alterado." >&2
  exit 1
}
[ -f "$ORIGEM" ] || {
  echo "ERRO: não encontrei o provisionador em $ORIGEM; confira o caminho e tente novamente." >&2
  exit 1
}

install -o root -g root -m 755 "$ORIGEM" "$DESTINO"
printf '%s\n' 'deploy ALL=(root) NOPASSWD: /usr/local/sbin/provisionar-usuario-ponte' > "$SUDOERS"
chmod 440 "$SUDOERS"
visudo -cf "$SUDOERS"

echo "OK: provisionador instalado como root em $DESTINO."
echo "OK: deploy pode executar somente esse caminho, sem argumentos e sem senha."
