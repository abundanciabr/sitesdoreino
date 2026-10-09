#!/usr/bin/env bash
# Instala a ligação persistente depois que D2 criou a conta e seu espelho.
# Não muda chaves, regras GitHub, contêineres nem versões publicadas.
set -euo pipefail

[[ $EUID -eq 0 && $# -eq 0 ]] || { echo 'uso: root instalar-ligacao-entregas.sh' >&2; exit 2; }
base=$(cd -- "$(dirname -- "$0")" && pwd -P)
origem=/var/lib/meshcraft-integrador
destino=/usr/local/lib/meshcraft-integrador
publicador=/usr/local/lib/meshcraft-publicador/atual

for programa in git cmp setfacl systemctl systemd-analyze runuser; do
  command -v "$programa" >/dev/null || { echo "programa ausente: $programa" >&2; exit 2; }
done
[[ "$(id -nG integrador)" == integrador ]] || { echo 'integrador tem grupos inesperados' >&2; exit 2; }
[[ "$(id -nG deploy)" == *docker* ]] || { echo 'conta publicadora sem Docker' >&2; exit 2; }
[[ -d "$origem/codigo/repo.git" && -d "$origem/entregas" ]] || {
  echo 'espelho de D2 ausente; ligação não instalada' >&2; exit 2;
}
[[ -d "$publicador/infra" ]] || { echo 'publicador independente ausente' >&2; exit 2; }
[[ -f "$publicador/infra/ponte_entregas.py" ]] || {
  echo 'nova versão confiável do publicador ainda não contém a ponte' >&2; exit 2;
}
cmp -s "$base/ponte_entregas.py" "$publicador/infra/ponte_entregas.py" || {
  echo 'ponte instalada difere da candidata revisada' >&2; exit 2;
}

install -d -o root -g root -m 755 "$destino"
for arquivo in entregas.py entregas_migracoes.py integrador_servico.py ponte_entregas.py; do
  install -o root -g root -m 644 "$base/$arquivo" "$destino/$arquivo"
done

# Somente deploy recebe leitura/travessia do espelho, nunca escrita nem acesso
# à chave SSH do integrador. A ACL padrão cobre registros/objetos Git novos.
setfacl -m u:deploy:rx "$origem" "$origem/codigo" "$origem/codigo/repo.git" "$origem/entregas"
setfacl -R -m u:deploy:rX "$origem/codigo/repo.git" "$origem/entregas"
find "$origem/codigo/repo.git" "$origem/entregas" -type d -exec setfacl -m d:u:deploy:rX {} +
runuser -u deploy -- test -r "$origem/codigo/repo.git/HEAD"
runuser -u deploy -- git -c "safe.directory=$origem/codigo/repo.git" \
  --git-dir="$origem/codigo/repo.git" rev-parse --verify refs/heads/main >/dev/null
runuser -u deploy -- test -x "$origem/entregas"
runuser -u integrador -- test ! -r /var/run/docker.sock
amostra=$(runuser -u integrador -- mktemp "$origem/entregas/.acl-XXXXXXXX")
trap 'rm -f -- "$amostra"' EXIT
runuser -u integrador -- chmod 640 "$amostra"
runuser -u deploy -- test -r "$amostra"
runuser -u deploy -- test ! -w "$amostra"
rm -f -- "$amostra"
trap - EXIT

cat > /etc/systemd/system/meshcraft-entregas-publicador.socket <<'UNIT'
[Unit]
Description=Ponte tipada para publicação de entregas

[Socket]
ListenStream=/run/meshcraft-entregas-publicador.sock
SocketUser=deploy
SocketGroup=integrador
SocketMode=0660
RemoveOnStop=yes

[Install]
WantedBy=sockets.target
UNIT

cat > /etc/systemd/system/meshcraft-entregas-publicador.service <<'UNIT'
[Unit]
Description=Autoridade tipada das entregas
Requires=meshcraft-entregas-publicador.socket
After=meshcraft-entregas-publicador.socket

[Service]
Type=simple
User=deploy
Group=deploy
WorkingDirectory=/opt/plataforma
Environment=PLATAFORMA_DIR=/opt/plataforma
ExecStart=/usr/bin/python3 /usr/local/lib/meshcraft-publicador/atual/infra/ponte_entregas.py servir
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/opt/plataforma
ReadOnlyPaths=/var/lib/meshcraft-integrador /usr/local/lib/meshcraft-publicador
Restart=on-failure

[Install]
WantedBy=multi-user.target
UNIT

cat > /etc/systemd/system/meshcraft-integrador.service <<'UNIT'
[Unit]
Description=Integração persistente das entregas
After=network-online.target meshcraft-entregas-publicador.socket
Wants=network-online.target meshcraft-entregas-publicador.socket

[Service]
Type=simple
User=integrador
Group=integrador
WorkingDirectory=/var/lib/meshcraft-integrador
Environment=PLATAFORMA_DIR=/var/lib/meshcraft-integrador
Environment="GIT_SSH_COMMAND=/usr/bin/ssh -i /home/integrador/.ssh/integrador -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes"
ExecStart=/usr/bin/python3 /usr/local/lib/meshcraft-integrador/integrador_servico.py continuo
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/var/lib/meshcraft-integrador
ReadOnlyPaths=/usr/local/lib/meshcraft-integrador
InaccessiblePaths=/opt/plataforma /var/run/docker.sock /run/docker.sock
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
UNIT

systemd-analyze verify /etc/systemd/system/meshcraft-entregas-publicador.socket \
  /etc/systemd/system/meshcraft-entregas-publicador.service \
  /etc/systemd/system/meshcraft-integrador.service
systemctl daemon-reload
echo 'Ligação instalada e verificada; serviços não ativados.'
echo 'A ponte permanece na versão confiável do publicador; a instalação não altera a versão antiga.'
echo 'Após D1/D2 e piloto: systemctl enable --now meshcraft-entregas-publicador.socket meshcraft-integrador.service'
