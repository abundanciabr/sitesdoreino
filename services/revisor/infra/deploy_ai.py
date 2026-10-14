"""Own delivery using existing provider; never opens Internet access for Revisor."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import sys
import runpy

ROOT=Path('/opt/plataforma')
OWN=ROOT/'revisor'
PRIVATE=ROOT/'revisor-private'
STATE=OWN/'ai-delivery.json'
operations=runpy.run_path(str(OWN/'deploy_network.py'))
run=operations['run']
freeze=operations['freeze']


def prepare():
    os.umask(0o077)
    freeze()
    if STATE.exists():
        print(STATE.read_text()); return
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup=ROOT/'backups-de-codigo'/('revisor-ai-'+stamp)
    backup.mkdir(mode=0o700)
    paths={'admin.env':ROOT/'env/admin.env','http.json':PRIVATE/'http.json','gateway.py':OWN/'gateway.py'}
    manifest={}
    for name,path in paths.items():
        shutil.copy2(path,backup/name); os.chmod(backup/name,0o600)
        manifest[name]={'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                        'uid':path.stat().st_uid,'gid':path.stat().st_gid,'mode':path.stat().st_mode&0o777}
    (backup/'iptables.txt').write_text(run(['iptables-save']))
    (backup/'manifest.json').write_text(json.dumps(manifest))
    token=secrets.token_hex(32)
    path=paths['admin.env']; original=path.read_bytes()
    assert b'REVISOR_AI_TOKEN=' not in original
    tmp=path.with_suffix('.revisor-ai.tmp')
    tmp.write_bytes(original+b'\nREVISOR_AI_TOKEN='+token.encode()+b'\n')
    shutil.copystat(path,tmp); os.chown(tmp,path.stat().st_uid,path.stat().st_gid); os.replace(tmp,path)
    cfg=json.loads(paths['http.json'].read_text())
    cfg['tokens']['revisor_ai']=token; cfg['ai_enabled']=False
    paths['http.json'].write_text(json.dumps(cfg))
    STATE.write_text(json.dumps({'backup':str(backup),'state':'prepared_pending_provider_reload',
        'provider':'existing_admin_executor','direct_internet':'closed','disclosure':'pending'}))
    freeze(); print(STATE.read_text())


def activate():
    state=json.loads(STATE.read_text()); freeze()
    source=Path(__file__).with_name('gateway.py')
    cfgpath=PRIVATE/'http.json'; cfg=json.loads(cfgpath.read_text())
    # First verify provider has loaded the pair, without making a paid request.
    probe='''import http.client,json
from pathlib import Path
c=json.loads(Path('/run/revisor/config.json').read_text())
h=http.client.HTTPConnection(c['upstream_ip'],8000,timeout=5)
h.request('POST','/admin/interno/revisor/v1/explicacao',body='{}',headers={'Host':'meshcraft.top','Content-Type':'application/json','Authorization':'Bearer '+c['tokens']['revisor_ai']})
r=h.getresponse(); print(r.status); r.read()
'''
    assert run(['docker','exec','meshcraft-revisor-http','python','-c',probe]).strip()=='400'
    shutil.copyfile(source,OWN/'gateway.py')
    cfg['ai_enabled']=True; cfgpath.write_text(json.dumps(cfg))
    try:
        run(['docker','compose','-p','revisor','-f',str(OWN/'compose.yml'),'up','-d','--force-recreate','--no-deps','http'])
        freeze()
    except Exception:
        cfg['ai_enabled']=False; cfgpath.write_text(json.dumps(cfg))
        shutil.copyfile(Path(state['backup'])/'gateway.py',OWN/'gateway.py')
        run(['docker','compose','-p','revisor','-f',str(OWN/'compose.yml'),'up','-d','--force-recreate','--no-deps','http'])
        raise
    state['state']='active_pending_paid_proof'; STATE.write_text(json.dumps(state))
    print(STATE.read_text())


if __name__=='__main__':
    {'prepare':prepare,'activate':activate}[sys.argv[1]]()
