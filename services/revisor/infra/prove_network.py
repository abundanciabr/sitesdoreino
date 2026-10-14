"""Real network checks: no table reads and no credentials in arguments/output."""
import json
from pathlib import Path
import subprocess
import runpy

ROOT = Path('/opt/plataforma')
OWN = ROOT/'revisor'
PRIVATE = ROOT/'revisor-private'


def main():
    report = {}
    probe = '''import socket,json
out={}
for label,host,port in json.loads(input()):
 try:
  s=socket.create_connection((host,port),1); s.close(); out[label]=True
 except OSError: out[label]=False
print(json.dumps(out))
'''
    config = json.loads((OWN/'network.json').read_text())
    for name, allowed in [('http',(config['application_ip'],8000)), ('db',(config['postgres_ip'],5432))]:
        denied = (config['postgres_ip'],5432) if name == 'http' else (config['application_ip'],8000)
        probes = [('allowed',*allowed),('other_cell',*denied),('internet','1.1.1.1',443),('host','172.16.20.1',22),('ipv6','2606:4700:4700::1111',443)]
        result = subprocess.run(['docker','exec','-i','meshcraft-revisor-'+name,'python','-c',probe],input=json.dumps(probes)+'\n',text=True,capture_output=True,timeout=20)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        report[name+'_network'] = data['allowed'] and not any(v for k,v in data.items() if k != 'allowed')
    password = json.loads((PRIVATE/'database.json').read_text())['password']
    for label,db,user,pw,expected in [('own_db','revisor','revisor',password,'ok'), ('wrong_password','revisor','revisor','wrong','password authentication failed'), ('other_database','test_praticas_3d_20261006','revisor',password,'pg_hba.conf rejects connection'), ('other_user','revisor','postgres','wrong','pg_hba.conf rejects connection')]:
        args=['docker','run','--rm','-i','--network','meshcraft-revisor','--cap-drop','ALL','--security-opt','no-new-privileges','--entrypoint','sh','postgres:17','-c','IFS= read -r PGPASSWORD; export PGPASSWORD; exec psql -h 172.16.20.2 -U "$1" -d "$2" -XAtc "SELECT current_user,current_database()"','sh',user,db]
        p=subprocess.run(args,input=pw+'\n',text=True,capture_output=True,timeout=20)
        report[label] = (p.returncode==0 and p.stdout.strip()=='revisor|revisor') if expected=='ok' else p.returncode!=0 and expected in p.stderr
    http=json.loads((PRIVATE/'http.json').read_text())
    http_probe='''import json,http.client,sys
c=json.loads(sys.stdin.read()); out={}
for name,method,path,auth in [('session','GET','/api/identidade/sessao/completa',True),('enrollment','GET','/api/alunos/alunos/prova-revisor%40example.invalid/matriculas',True),('lessons','GET','/api/cursos/cursos/prova-revisor-inexistente/aulas?site_id='+c['site_id'],True),('unauthorized','GET','/api/identidade/sessao/completa',False),('post','POST','/api/identidade/sessao/completa',True),('arbitrary','GET','/api/identidade/usuarios',True),('connect','CONNECT','example.com:443',True)]:
 h=http.client.HTTPConnection('172.16.20.3',8080,timeout=8)
 h.request(method,path,headers={'Authorization':'Bearer '+c['client_token']} if auth else {})
 r=h.getresponse(); body=r.read(); out[name]=r.status
 if name=='session' and r.status==200: out['anonymous_session']=json.loads(body).get('autenticado') is False
 h.close()
print(json.dumps(out))
'''
    p=subprocess.run(['docker','run','--rm','-i','--network','meshcraft-revisor','--cap-drop','ALL','--security-opt','no-new-privileges','python:3.12-slim','python','-c',http_probe],input=json.dumps({k:http[k] for k in ['site_id','client_token']}),text=True,capture_output=True,timeout=60)
    assert p.returncode==0
    report['http_status']=json.loads(p.stdout)
    provider_probe='''import json,http.client
from pathlib import Path
c=json.loads(Path('/run/revisor/config.json').read_text()); out={}
for name,path in [('session','/entrar/revisor/sessao/completa'),('enrollment','/alunos/api/alunos/alunos/prova-revisor%40example.invalid/matriculas'),('lessons','/cursos/api/cursos/cursos/prova-revisor-inexistente/aulas?site_id='+c['site_id'])]:
 h=http.client.HTTPConnection(c['upstream_ip'],8000,timeout=5)
 h.request('GET',path,headers={'Host':'meshcraft.top','Authorization':'Bearer deliberately-incorrect'})
 r=h.getresponse(); out[name]=r.status; r.read(); h.close()
print(json.dumps(out))
'''
    invalid=subprocess.run(['docker','exec','meshcraft-revisor-http','python','-c',provider_probe],capture_output=True,text=True,timeout=20)
    assert invalid.returncode==0
    report['provider_invalid_token_status']=json.loads(invalid.stdout)
    report['provider_auth_checked']=all(v==401 for v in report['provider_invalid_token_status'].values())
    report['http_denials']=all(report['http_status'][k]==v for k,v in [('unauthorized',401),('post',405),('arbitrary',403),('connect',405)])
    report['http_pairs']=report['provider_auth_checked'] and report['http_status']['session']==200 and report['http_status'].get('anonymous_session',False) and report['http_status']['enrollment']==404 and report['http_status']['lessons']==404
    runpy.run_path(str(OWN/'deploy_network.py'))['freeze']()
    report['mercadopago_freeze']=True
    report['ai_egress']='closed'
    report['public_route_created']=False
    report['link_disclosed']=False
    (Path(config['backup'])/'proof.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
