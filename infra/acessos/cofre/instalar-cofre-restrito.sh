#!/usr/bin/env bash
# Preparado, não executado. Instala uma NOVA chave de leitura do cofre em deploy.
# Uso futuro na VPS, após decisão D2: root instalar-cofre-restrito.sh /caminho/chave-nova.pub
set -euo pipefail
umask 077
[[ $EUID -eq 0 && $# -eq 1 && -f "$1" ]] || { echo 'chave pública nova ausente' >&2; exit 2; }
base=$(cd -- "$(dirname -- "$0")" && pwd -P)
pub=$(cat -- "$1")
[[ $(wc -l < "$1") -eq 1 && "$pub" =~ ^ssh-ed25519[[:space:]][A-Za-z0-9+/=]+([[:space:]][A-Za-z0-9@._-]+)?$ ]] || {
  echo 'chave pública ed25519 inválida' >&2; exit 2;
}
[[ -f "$base/cofre_dispatcher.py" ]] || { echo 'dispatcher ausente' >&2; exit 2; }
chaves=/home/deploy/.ssh/authorized_keys
[[ -f "$chaves" && ! -L "$chaves" ]] || { echo 'authorized_keys ausente' >&2; exit 2; }
fingerprint=$(ssh-keygen -lf "$1" -E sha256 | awk '{print $2}')
[[ "$fingerprint" == SHA256:* ]] || { echo 'fingerprint inválido' >&2; exit 2; }
if ssh-keygen -lf "$chaves" -E sha256 | awk '{print $2}' | grep -qxF "$fingerprint"; then
  echo 'chave já presente em deploy; recusa para não reutilizar acesso amplo' >&2
  exit 2
fi

destino=/usr/local/lib/meshcraft-cofre
install -d -o root -g root -m 755 "$destino"
install -o root -g root -m 755 "$base/cofre_dispatcher.py" "$destino/cofre_dispatcher.py"
python3 -m py_compile "$destino/cofre_dispatcher.py"
linha="restrict,command=\"/usr/bin/python3 $destino/cofre_dispatcher.py\" $pub"

backups=/var/backups/meshcraft-acessos
install -d -o root -g root -m 700 "$backups"
carimbo=$(date -u +%Y%m%dT%H%M%S%NZ)
install -o root -g root -m 600 "$chaves" "$backups/deploy-authorized_keys-cofre-$carimbo"
temporario=$(mktemp "${chaves}.cofre.XXXXXXXX")
trap 'rm -f -- "$temporario"' EXIT
cat "$chaves" > "$temporario"
printf '%s\n' "$linha" >> "$temporario"
chown --reference="$chaves" "$temporario"
chmod 600 "$temporario"
mv -f -- "$temporario" "$chaves"
trap - EXIT
echo "Chave restrita preparada: $fingerprint. Tarefa agendada não foi alterada; chave ampla não foi removida."
