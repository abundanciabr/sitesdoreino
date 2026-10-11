#!/usr/bin/env python3
"""Instala o executor já conferido; credenciais existentes vêm de arquivo privado.

Não altera aplicação, imagem, gateway, bancos ou o publicador. Conserva cópia dos
arquivos anteriores antes de trocar o próprio serviço.
"""
from datetime import datetime, timezone
import os
from pathlib import Path
import pwd
import shutil
import subprocess

CODIGO = Path("/usr/local/lib/meshcraft-super-equipe")
DADOS = Path("/var/lib/meshcraft-super-equipe")
PRIVADO = Path("/etc/meshcraft-super-equipe/credenciais")
SERVICO = """[Unit]
Description=Super equipe Meshcraft - executor permanente
After=network-online.target meshcraft-robo.service
Wants=network-online.target
[Service]
User=robo
Group=robo
EnvironmentFile=/etc/meshcraft-super-equipe/credenciais
ExecStart=/usr/bin/python3 /usr/local/lib/meshcraft-super-equipe/executor.py
Restart=always
RestartSec=30
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/meshcraft-super-equipe
MemoryMax=512M
[Install]
WantedBy=multi-user.target
"""
COLETOR = """[Unit]
Description=Contagens locais da Super equipe (sem logs brutos)
[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /usr/local/lib/meshcraft-super-equipe/coletor.py
RuntimeDirectory=meshcraft-super-equipe
RuntimeDirectoryMode=0755
RuntimeDirectoryPreserve=yes
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
ReadWritePaths=/run/meshcraft-super-equipe
"""
TIMER = """[Unit]
Description=Atualiza a fotografia da VPS a cada minuto
[Timer]
OnBootSec=30
OnUnitActiveSec=60
[Install]
WantedBy=timers.target
"""


def main():
    if os.geteuid() != 0:
        raise SystemExit("Instalação requer a administração da VPS.")
    # Somente verifica presença e permissões; nunca imprime o conteúdo.
    if not PRIVADO.is_file() or PRIVADO.stat().st_mode & 0o077 or PRIVADO.stat().st_uid != 0:
        raise SystemExit("Arquivo privado de credenciais ainda não está preparado.")
    robo = pwd.getpwnam("robo")
    arquivos = {"executor.py": "super_equipe_executor.py", "coletor.py": "super_equipe_coletor.py",
                "git_askpass.py": "super_equipe_git_askpass.py"}
    unidades = {"meshcraft-super-equipe.service": SERVICO, "meshcraft-super-equipe-coletor.service": COLETOR,
                "meshcraft-super-equipe-coletor.timer": TIMER}
    copia = Path("/opt/plataforma/backups-de-codigo")/("super-equipe-executor-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    copia.mkdir(parents=True, mode=0o700)
    if CODIGO.exists():
        shutil.copytree(CODIGO, copia/"codigo")
    for nome in unidades:
        anterior = Path("/etc/systemd/system")/nome
        if anterior.exists():
            shutil.copy2(anterior, copia/nome)
    CODIGO.mkdir(mode=0o755, exist_ok=True)
    CODIGO.chmod(0o755)
    DADOS.mkdir(mode=0o700, exist_ok=True)
    os.chown(DADOS, robo.pw_uid, robo.pw_gid)
    for nome, fonte in arquivos.items():
        shutil.copyfile(Path(__file__).parent/fonte, CODIGO/nome)
        (CODIGO/nome).chmod(0o755 if nome == "git_askpass.py" else 0o644)
    for nome, conteudo in unidades.items():
        (Path("/etc/systemd/system")/nome).write_text(conteudo)
    subprocess.run(["systemctl", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "enable", "--now", "meshcraft-super-equipe-coletor.timer", "meshcraft-super-equipe.service"], check=True)
    subprocess.run(["systemctl", "restart", "meshcraft-super-equipe.service", "meshcraft-super-equipe-coletor.service"], check=True)
    print("Executor instalado; backup somente do código em", copia)


if __name__ == "__main__":
    main()
