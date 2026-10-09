#!/usr/bin/env bash
# Preparação de D2: instalar só após a decisão do mantenedor.
# Uso: sudo bash D2-usuario-robo.sh /caminho/privado/chave-robo.pub
set -euo pipefail
umask 077

if [[ $EUID -ne 0 || $# -ne 1 || ! -f "$1" ]]; then
  echo "uso: root D2-usuario-robo.sh /caminho/chave-robo.pub" >&2
  exit 2
fi
base="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
for source in robo_comando.py robo_broker.py ../entregas.py ../entregas_migracoes.py; do
  [[ -f "$base/$source" ]] || { echo "arquivo de instalação ausente: $source" >&2; exit 2; }
done
pub="$(head -n 1 -- "$1")"
[[ "$(wc -l < "$1")" -eq 1 ]] || { echo "arquivo público deve ter uma linha" >&2; exit 2; }
[[ "$pub" =~ ^ssh-ed25519[[:space:]][A-Za-z0-9+/=]+([[:space:]][A-Za-z0-9@._-]+)?$ ]] || {
  echo "chave pública ed25519 inválida" >&2; exit 2;
}
fingerprint="$(ssh-keygen -lf "$1" -E sha256 | awk '{print $2}')"
[[ "$fingerprint" == SHA256:* ]] || { echo "fingerprint inválido" >&2; exit 2; }
if ssh-keygen -lf /home/deploy/.ssh/authorized_keys -E sha256 | awk '{print $2}' | grep -qxF "$fingerprint"; then
  echo "a mesma chave ainda tem acesso amplo em deploy; use chave nova" >&2
  exit 2
fi
if id robo >/dev/null 2>&1; then
  [[ "$(getent passwd robo | cut -d: -f7)" == /bin/sh ]] || {
    echo "conta robo existente com shell inesperado" >&2; exit 2;
  }
  [[ "$(id -nG robo)" == robo ]] || {
    echo "conta robo existente com grupos inesperados" >&2; exit 2;
  }
else
  useradd --create-home --user-group --shell /bin/sh robo
fi
[[ "$(passwd -S robo | awk '{print $2}')" == L ]] || {
  echo "conta robo com senha não bloqueada" >&2; exit 2;
}
if id integrador >/dev/null 2>&1; then
  [[ "$(getent passwd integrador | cut -d: -f7)" == /usr/sbin/nologin ]] || {
    echo "conta integrador existente com shell inesperado" >&2; exit 2;
  }
  [[ "$(id -nG integrador)" == integrador ]] || {
    echo "conta integrador existente com grupos inesperados" >&2; exit 2;
  }
else
  useradd --system --create-home --home-dir /home/integrador --user-group \
    --shell /usr/sbin/nologin integrador
fi
[[ "$(passwd -S integrador | awk '{print $2}')" == L ]] || {
  echo "conta integrador com senha não bloqueada" >&2; exit 2;
}
install -d -o integrador -g integrador -m 700 /var/lib/meshcraft-integrador
install -d -o integrador -g integrador -m 700 /var/lib/meshcraft-integrador/codigo
install -d -o integrador -g integrador -m 700 /var/lib/meshcraft-integrador/entregas
repo=/var/lib/meshcraft-integrador/codigo/repo.git
if [[ ! -d "$repo" ]]; then
  runuser -u integrador -- git init --bare -q "$repo"
fi
[[ "$(stat -c %U "$repo")" == integrador ]] || {
  echo "espelho independente não pertence ao integrador" >&2; exit 2;
}
if ! runuser -u integrador -- git --git-dir="$repo" remote get-url origin >/dev/null 2>&1; then
  runuser -u integrador -- git --git-dir="$repo" remote add origin \
    https://github.com/abundanciabr/sitesdoreino.git
fi
[[ "$(runuser -u integrador -- git --git-dir="$repo" remote get-url origin)" == \
  https://github.com/abundanciabr/sitesdoreino.git ]] || {
  echo "origin do integrador inesperado" >&2; exit 2;
}
runuser -u integrador -- git --git-dir="$repo" fetch --quiet origin \
  main:refs/heads/main

install -d -o root -g root -m 755 /usr/local/lib/meshcraft-acessos
install -d -o root -g root -m 755 /usr/local/lib/meshcraft-integrador
install -o root -g root -m 644 "$base/../entregas.py" /usr/local/lib/meshcraft-integrador/entregas.py
install -o root -g root -m 644 "$base/../entregas_migracoes.py" /usr/local/lib/meshcraft-integrador/entregas_migracoes.py
install -o root -g root -m 755 "$base/robo_comando.py" /usr/local/lib/meshcraft-acessos/robo_comando.py
install -o root -g root -m 755 "$base/robo_broker.py" /usr/local/lib/meshcraft-acessos/robo_broker.py
cat > /etc/systemd/system/meshcraft-robo.socket <<'UNIT'
[Unit]
Description=Entrada restrita das entregas de robôs

[Socket]
ListenStream=/run/meshcraft-robo.sock
SocketUser=integrador
SocketGroup=robo
SocketMode=0660
RemoveOnStop=yes

[Install]
WantedBy=sockets.target
UNIT
cat > /etc/systemd/system/meshcraft-robo.service <<'UNIT'
[Unit]
Description=Despacho restrito das entregas de robôs
Requires=meshcraft-robo.socket
After=meshcraft-robo.socket

[Service]
Type=simple
User=integrador
Group=integrador
Environment=PLATAFORMA_DIR=/var/lib/meshcraft-integrador
ExecStart=/usr/bin/python3 /usr/local/lib/meshcraft-acessos/robo_broker.py
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ReadWritePaths=/var/lib/meshcraft-integrador
ProtectHome=read-only
Restart=on-failure
UNIT
systemd-analyze verify /etc/systemd/system/meshcraft-robo.socket /etc/systemd/system/meshcraft-robo.service
systemctl daemon-reload
systemctl enable --now meshcraft-robo.socket

chown root:root /home/robo
chmod 755 /home/robo
# sshd abre authorized_keys sob UID do usuário; leitura pública não dá escrita.
install -d -m 750 -o root -g robo /home/robo/.ssh
keys=/home/robo/.ssh/authorized_keys
touch "$keys"
chown root:robo "$keys"
chmod 640 "$keys"
line="restrict,command=\"/usr/bin/python3 /usr/local/lib/meshcraft-acessos/robo_comando.py\" $pub"
if ! grep -qxF -- "$line" "$keys"; then
  if grep -Fq -- "$pub" "$keys"; then
    echo "mesma chave já presente sem restrição esperada" >&2
    exit 2
  fi
  printf '%s\n' "$line" >> "$keys"
fi
echo "D2 preparada para fingerprint $fingerprint; chave de deploy ainda NÃO foi retirada."
