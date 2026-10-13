"""Instala o canal autorizado em 13/10/2026. Não altera prévias existentes."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

HERE=Path(__file__).resolve().parent
DEST=Path('/usr/local/lib/meshcraft-previas')
ROOT=Path('/opt/plataforma/previas/operacionais')
COMMAND=Path('/usr/local/lib/meshcraft-acessos/robo_comando.py')
ROUTES=Path('/opt/plataforma/traefik/dynamic')
ROUTE=ROUTES/'previas-operacionais.yml'
NAME='meshcraft-previas-portal'


def run(args,timeout=60):
    return subprocess.run(args,check=True,capture_output=True,text=True,timeout=timeout).stdout.strip()


def put(path,body,mode=0o644):
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o755)
    tmp=path.with_name(path.name+'.previa-new')
    tmp.write_text(body)
    tmp.chmod(mode)
    os.replace(tmp,path)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def http(url):
    try:
        with urllib.request.urlopen(url,timeout=15) as response:return response.status
    except urllib.error.HTTPError as error:return error.code


def query(args):
    result=subprocess.run(['/usr/sbin/runuser','-u','robo','--','/usr/bin/python3',str(COMMAND)],env=dict(os.environ,SSH_ORIGINAL_COMMAND=' '.join(args)),capture_output=True,text=True,timeout=30)
    return result.returncode,json.loads(result.stdout)


def main():
    assert os.geteuid()==0
    os.umask(0o022)
    assert not DEST.exists() and not ROUTE.exists() and not ROOT.exists(),'Já instalado; preservar operação'
    source=COMMAND.read_text()
    marker='    consulta = atender(args, __file__)'
    assert source.count(marker)==1 and source.count('import sys\n')==1
    updated=source.replace('import sys\n','import sys\nfrom previas_cliente import atender_previas\n').replace(marker,
        '    previa = atender_previas(args)\n    if previa is not None:\n        return previa\n'+marker)
    compile(updated,str(COMMAND),'exec')
    run(['/usr/bin/python3','-m','unittest','test_previas.py'],30) if Path.cwd()==HERE else run(['/usr/bin/python3',str(HERE/'test_previas.py')],30)
    anchors=[Path('/home/robo/.ssh/authorized_keys'),Path('/home/deploy/.ssh/authorized_keys'),Path('/opt/plataforma/docker-compose.yml')]
    anchors+=list(ROUTES.glob('*'))+list(Path('/opt/plataforma/env').glob('*.env'))
    for root in {Path('/usr/local/lib/meshcraft-publicador/v1-20261006T184415Z'),Path('/usr/local/lib/meshcraft-publicador/atual').resolve()}:
        for glob in ('mercadopago/*','docs/*','satisfacao/*','infra/publicar.py'):
            anchors+=list(root.glob(glob))
    anchors=[p for p in anchors if p.is_file()]
    before={str(p):sha(p) for p in anchors}
    containers=json.loads(run(['docker','inspect']+run(['docker','ps','-q']).split()))
    existing={d['Name']:(d['Id'],d['State']['StartedAt'],d['Image']) for d in containers}
    assert http('https://meshcraft.top/')==200
    backup=Path('/opt/plataforma/backups-de-codigo')/('canal-previas-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    backup.mkdir(mode=0o700)
    shutil.copy2(COMMAND,backup/'robo_comando.py')
    shutil.copy2(COMMAND.parent/'operacao_contexto.py',backup/'operacao_contexto.py')
    (backup/'referencias.json').write_text(json.dumps(before))
    (backup/'containers.json').write_text(json.dumps(existing))
    changed=False
    try:
        DEST.mkdir(mode=0o755)
        ROOT.mkdir(mode=0o755)
        for folder in ('operations','releases','backups'):(ROOT/folder).mkdir(mode=0o700 if folder=='backups' else 0o755)
        for name in ('previas.py','previas_portal.mjs'):
            put(DEST/name,(HERE/name).read_text())
        node=run(['docker','image','inspect','node:22-alpine','--format','{{.Id}}'])
        run(['docker','pull','python:3.12-slim'],180)
        python=run(['docker','image','inspect','python:3.12-slim','--format','{{.Id}}'])
        put(DEST/'config.json',json.dumps({'images':{'node':node,'python':python}}))
        put(ROOT/'active.json','{}')
        put(ROOT/'public.json',json.dumps({'previas':{},'operacoes':[]}))
        unit='[Unit]\nDescription=Meshcraft previas isoladas\nAfter=docker.service network-online.target\n[Service]\nExecStart=/usr/bin/python3 /usr/local/lib/meshcraft-previas/previas.py\nRestart=always\nRestartSec=3\nUser=root\nGroup=root\nUMask=0022\nNoNewPrivileges=true\nPrivateTmp=true\nProtectHome=true\nProtectSystem=strict\nReadWritePaths=/opt/plataforma/previas/operacionais\nMemoryMax=256M\nTasksMax=48\n[Install]\nWantedBy=multi-user.target\n'
        sock='[Unit]\nDescription=Meshcraft canal restrito de previas\n[Socket]\nListenStream=/run/meshcraft-previas.sock\nSocketUser=root\nSocketGroup=robo\nSocketMode=0660\n[Install]\nWantedBy=sockets.target\n'
        put(Path('/etc/systemd/system/meshcraft-previas.service'),unit)
        put(Path('/etc/systemd/system/meshcraft-previas.socket'),sock)
        run(['systemctl','daemon-reload'])
        run(['systemctl','enable','--now','meshcraft-previas.socket','meshcraft-previas.service'])
        run(['docker','run','-d','--name',NAME,'--pull','never','--restart','unless-stopped','--read-only','--user','65534:65534','--cap-drop','ALL','--security-opt','no-new-privileges','--network','edge','--memory','128m','--cpus','0.25','--pids-limit','24','--log-driver','none','--mount','type=bind,src='+str(DEST)+',dst=/control,readonly','--mount','type=bind,src='+str(ROOT)+',dst=/state,readonly','--entrypoint','node',node,'/control/previas_portal.mjs'])
        run(['docker','network','connect','meshcraft-funil',NAME])
        route={'http':{'routers':{'previas-operacionais':{'rule':'Host(`meshcraft.top`) && (Path(`/admin/previas-operacionais`) || PathPrefix(`/admin/previas-operacionais/`))','priority':1200,'entryPoints':['websecure'],'tls':{},'service':'previas-operacionais','middlewares':['seguranca@file']}},'services':{'previas-operacionais':{'loadBalancer':{'servers':[{'url':'http://'+NAME+':8080'}]}}}}}
        put(ROUTE,json.dumps(route))
        put(COMMAND.parent/'previas_cliente.py',(HERE/'previas_cliente.py').read_text())
        st=COMMAND.stat()
        put(COMMAND,updated,st.st_mode&0o777)
        os.chown(COMMAND,st.st_uid,st.st_gid)
        changed=True
        put(COMMAND.parent/'operacao_contexto.py',(HERE/'operacao_contexto.py').read_text())
        for _ in range(10):
            if http('https://meshcraft.top/admin/previas-operacionais/')==403:break
            time.sleep(1)
        assert http('https://meshcraft.top/admin/previas-operacionais/')==403
        assert query(['previas','listar'])[0]==0
        for args in (['previas','exec','id'],['previas','consultar','../etc/shadow'],['shell']):assert query(args)[0]==2
        assert {str(p):sha(p) for p in anchors}==before
        # Nenhum contêiner que já estava executando foi reiniciado ou substituído por esta instalação.
        after=json.loads(run(['docker','inspect']+[d['Id'] for d in containers]))
        assert all((d['Id'],d['State']['StartedAt'],d['Image'])==existing[d['Name']] for d in after)
        assert http('https://meshcraft.top/')==200
        result={'instalado':True,'backup':str(backup),'referencias_preservadas':len(before),'containers_existentes_preservados':len(existing),'anonimo_http':403,'site_http':200,'banco_alterado':False,'images':{'node':node,'python':python}}
        put(backup/'resultado.json',json.dumps(result))
        print(json.dumps(result))
    except BaseException:
        if changed:
            put(COMMAND,(backup/'robo_comando.py').read_text(),st.st_mode&0o777)
            os.chown(COMMAND,st.st_uid,st.st_gid)
            put(COMMAND.parent/'operacao_contexto.py',(backup/'operacao_contexto.py').read_text())
        if ROUTE.exists():shutil.move(str(ROUTE),str(backup/'rota-retirada.yml'))
        subprocess.run(['docker','stop',NAME],capture_output=True)
        subprocess.run(['systemctl','disable','--now','meshcraft-previas.socket','meshcraft-previas.service'],capture_output=True)
        put(backup/'resultado.json',json.dumps({'instalado':False,'codigo_recuperado':True,'banco_alterado':False}))
        raise


if __name__=='__main__':main()
