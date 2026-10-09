#!/usr/bin/env bash
# Preparação futura de D1 na VPS: chave exclusiva da conta integrador.
set -euo pipefail
umask 077
[[ $EUID -eq 0 && $# -eq 0 ]] || { echo "uso: root D1-chave-integrador.sh" >&2; exit 2; }
[[ "$(id -nG integrador)" == integrador ]] || {
  echo "integrador deve ter apenas seu grupo próprio" >&2; exit 2;
}
repo=/var/lib/meshcraft-integrador/codigo/repo.git
[[ -d "$repo" && "$(stat -c %U "$repo")" == integrador ]] || {
  echo "espelho independente ausente ou com dono inesperado" >&2; exit 2;
}
install -d -o integrador -g integrador -m 700 /home/integrador/.ssh
hostfile=/home/integrador/.ssh/known_hosts
[[ -f "$hostfile" ]] && ssh-keygen -F github.com -f "$hostfile" >/dev/null || {
  echo "host GitHub não está fixado; conferir fingerprint oficial antes" >&2; exit 2;
}
chave=/home/integrador/.ssh/integrador
if [[ ! -f "$chave" && ! -f "$chave.pub" ]]; then
  runuser -u integrador -- ssh-keygen -q -t ed25519 -N '' -C integrador-vps -f "$chave"
fi
[[ -f "$chave" && -f "$chave.pub" ]] || { echo "par de chaves incompleto" >&2; exit 2; }
[[ "$(stat -c %U "$chave")" == integrador ]] || {
  echo "chave privada com dono inesperado" >&2; exit 2;
}
chmod 600 "$chave"
chmod 644 "$chave.pub"
if runuser -u integrador -- git --git-dir="$repo" remote get-url integrador >/dev/null 2>&1; then
  [[ "$(runuser -u integrador -- git --git-dir="$repo" remote get-url integrador)" == \
    git@github.com:abundanciabr/sitesdoreino.git ]] || {
    echo "remoto integrador inesperado" >&2; exit 2;
  }
else
  runuser -u integrador -- git --git-dir="$repo" remote add integrador \
    git@github.com:abundanciabr/sitesdoreino.git
fi
echo "Chave pública para cadastrar: $chave.pub"
ssh-keygen -lf "$chave.pub" -E sha256 | awk '{print "Fingerprint: " $2}'
