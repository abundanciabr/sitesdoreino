"""Instala somente o processador desta ferramenta, com backup antes e prova real."""
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import urllib.request

ROOT=Path('/opt/plataforma')
TARGET=ROOT/'diagnostico-texturas'
SOURCE=Path(__file__).resolve().parents[1]/'services/encomendas/analise_texturas'
ARCHIVE='blender-4.5.9-linux-x64.tar.xz'
SHA='dcdc3eca6c9825bb35a8033b689c053f3cb5a9b0cd2a61b2eac2a49436b4ad3d'
IMAGE='sha256:e067accf6a9183c27f66c7181fe27659dba607d7f79a285acb08cb2f913b4a9c'
UNIT=Path('/etc/systemd/system/meshcraft-diagnostico-texturas.service')


def run(args,timeout=900,**kwargs):
    kwargs.setdefault('check',True)
    return subprocess.run(args,timeout=timeout,**kwargs)


def main():
    if os.geteuid()!=0:raise RuntimeError('Execute no console administrativo.')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup=ROOT/'backups-de-codigo'/('diagnostico-texturas-'+stamp)
    backup.mkdir(mode=0o700,parents=True)
    with (backup/'bancos.log').open('w') as log:run([str(ROOT/'bin/plataforma'),'backup'],stdout=log,stderr=subprocess.STDOUT)
    with tarfile.open(backup/'codigo-configuracoes.tar','w') as tar:
        for path in [ROOT/'env',ROOT/'publicacoes',TARGET,UNIT]:
            if path.exists():tar.add(path,arcname=str(path).lstrip('/'))
    print('BACKUP_OK',str(backup),flush=True)
    TARGET.mkdir(mode=0o755,exist_ok=True)
    bundle=TARGET/ARCHIVE
    if not bundle.is_file() or hashlib.file_digest(bundle.open('rb'),'sha256').hexdigest()!=SHA:
        urllib.request.urlretrieve('https://download.blender.org/release/Blender4.5/'+ARCHIVE,bundle)
    with bundle.open('rb') as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest()!=SHA:raise RuntimeError('Distribuição do Blender divergente.')
    blender=TARGET/'blender-4.5.9-linux-x64'
    if not blender.is_dir():
        with tarfile.open(bundle) as tar:tar.extractall(TARGET,filter='data')
    code=TARGET/('v1-'+stamp)
    shutil.copytree(SOURCE,code)
    run(['docker','run','--rm','--network','none','--entrypoint','/blender/blender',
         '--mount','type=bind,src='+str(blender)+',dst=/blender,readonly',IMAGE,'--background','--version'],stdout=subprocess.DEVNULL)
    samples=TARGET/('prova-'+stamp)
    samples.mkdir(mode=0o777)
    samples.chmod(0o777)
    args=['docker','run','--rm','--network','none','--read-only','--cap-drop','ALL',
          '--security-opt','no-new-privileges','--memory','1536m','--cpus','1.5',
          '--tmpfs','/tmp:rw,noexec,nosuid,size=512m','-e','HOME=/tmp',
          '--mount','type=bind,src='+str(blender)+',dst=/blender,readonly',
          '--mount','type=bind,src='+str(code)+',dst=/ferramenta,readonly',
          '--mount','type=bind,src='+str(samples)+',dst=/prova','--entrypoint','/blender/blender',IMAGE,
          '--background','--factory-startup','--disable-autoexec','--threads','2','--python-exit-code','2']
    run(args+['--python','/ferramenta/criar_amostras.py','--','/prova'],stdout=subprocess.DEVNULL)
    proofs={}
    for name,expected in [('uv-repetida','uv_compartilhada'),('uv-separada',None),('peca-duplicada','geometria_sobreposta'),('imagem-ausente','imagem_indisponivel'),('no-nao-usado',None),('sem-uv','sem_uv')]:
        output=samples/name
        output.mkdir(mode=0o777)
        output.chmod(0o777)
        run(args+['--python','/ferramenta/examinar_blender.py','--','/prova/'+name+'.blend','/prova/'+name],stdout=subprocess.DEVNULL)
        report=json.loads((output/'resultado.json').read_text())
        codes={a['codigo'] for a in report['achados']}
        if report['estado']!='concluida' or (expected and expected not in codes) or (not expected and codes):
            raise RuntimeError('A prova de conteúdo falhou: '+name)
        proofs[name]={'estado':report['estado'],'codigos':sorted(codes),'vistas':len(report['imagens'])}
    run(args+['--python','/ferramenta/examinar_blender.py','--','/prova/invalido.blend','/prova/invalido'],stdout=subprocess.DEVNULL,check=False)
    invalid=json.loads((samples/'invalido/resultado.json').read_text())
    if invalid['estado']!='falha':raise RuntimeError('Arquivo inválido não foi reconhecido.')
    proofs['invalido']={'estado':'falha_identificada'}
    old=UNIT.read_bytes() if UNIT.exists() else None
    owner=(ROOT/'encomendas-arquivos/marketplace').stat()
    queue=ROOT/'encomendas-arquivos/marketplace/diagnosticos-texturas'
    queue.mkdir(mode=0o700,exist_ok=True)
    os.chown(queue,owner.st_uid,owner.st_gid)
    unit='''[Unit]
Description=Diagnostico privado de texturas dos projetos do Blender
After=docker.service
[Service]
ExecStart=/usr/bin/python3 CODE/worker.py
User=root
UMask=0077
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/opt/plataforma/encomendas-arquivos/marketplace/diagnosticos-texturas
Restart=on-failure
RestartSec=5
[Install]
WantedBy=multi-user.target
'''.replace('CODE',str(code))
    try:
        UNIT.write_text(unit)
        run(['systemd-analyze','verify',str(UNIT)],timeout=30)
        run(['systemctl','daemon-reload'],timeout=30)
        run(['systemctl','enable','--now','meshcraft-diagnostico-texturas.service'],timeout=30)
        run(['systemctl','is-active','--quiet','meshcraft-diagnostico-texturas.service'],timeout=30)
    except BaseException:
        if old:
            UNIT.write_bytes(old)
            subprocess.run(['systemctl','daemon-reload'])
            subprocess.run(['systemctl','restart','meshcraft-diagnostico-texturas.service'])
        else:
            subprocess.run(['systemctl','disable','--now','meshcraft-diagnostico-texturas.service'])
        raise
    evidence={'backup':str(backup),'codigo':str(code),'blender':'4.5.9','provas':proofs,'estado':'instalado'}
    (TARGET/'instalacao.json').write_text(json.dumps(evidence,ensure_ascii=False))
    print('INSTALADO_E_CONFERIDO',json.dumps(evidence,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
