"""Paid proof with synthetic facts only. Run once after authorised activation."""
import json
from pathlib import Path
import runpy
import subprocess

OWN=Path('/opt/plataforma/revisor')
PRIVATE=Path('/opt/plataforma/revisor-private')


def main():
    state=json.loads((OWN/'ai-delivery.json').read_text())
    destination=Path(state['backup'])/'ai-proof.json'
    if destination.exists():
        print(destination.read_text()); return
    pending=Path(state['backup'])/'ai-proof.pending'
    if pending.exists():
        raise RuntimeError('Previous proof outcome unknown; reconcile provider ledger before retrying')
    pending.write_text('Synthetic proof started; reconcile before any retry.')
    cfg=json.loads((PRIVATE/'http.json').read_text())
    probe='''import json,http.client,socket,sys
c=json.loads(sys.stdin.read()); out={'examples':[]}
for language,code,value,limit in [('pt-br','triangle_budget',5000,4000),('en','texture_budget',4096,2048),('es','triangle_budget',5000,4000)]:
 data={'version':1,'language':language,'profile':'rigid','grade':'needs_work','coverage_complete':False,'omitted_checks':0,'checks':[{'index':0,'code':code,'state':'fail','severity':'blocks','count':1,'evidence':{'value':value,'limit':limit}},{'index':1,'code':'ngons','state':'unverifiable','severity':None,'count':None,'evidence':{'reason':'export_triangulated'}}]}
 h=http.client.HTTPConnection('172.16.20.3',8080,timeout=30)
 h.request('POST','/api/revisor/v1/explicacao',json.dumps(data),{'Content-Type':'application/json','Authorization':'Bearer '+c['client_token']})
 r=h.getresponse(); body=json.loads(r.read(65536)); h.close()
 out['examples'].append({'language':language,'status':r.status,'result':body})
 if r.status!=200: break
for label,host,port in [('internet','1.1.1.1',443),('database_direct',c['postgres_ip'],5432),('host','172.16.20.1',22)]:
 try: s=socket.create_connection((host,port),1); s.close(); out[label+'_blocked']=False
 except OSError: out[label+'_blocked']=True
print(json.dumps(out))
'''
    network=json.loads((OWN/'network.json').read_text())
    p=subprocess.run(['docker','run','--rm','-i','--network','meshcraft-revisor',
      '--cap-drop','ALL','--security-opt','no-new-privileges','python:3.12-slim','python','-c',probe],
      input=json.dumps({'client_token':cfg['client_token'],'postgres_ip':network['postgres_ip']}),
      capture_output=True,text=True,timeout=110)
    if p.returncode: raise RuntimeError('proof did not complete; inspect before retrying')
    report=json.loads(p.stdout)
    report['passed']=(len(report['examples'])==3 and all(x['status']==200 and x['result'].get('fallback') is False
        for x in report['examples']) and all(report[k] for k in ['internet_blocked','database_direct_blocked','host_blocked']))
    report['disclosure']='pending'
    runpy.run_path(str(OWN/'deploy_network.py'))['freeze']()
    report['mercadopago_freeze']=True
    destination.write_text(json.dumps(report,ensure_ascii=False,indent=2))
    state['state']='proven' if report['passed'] else 'proof_failed_closed'
    if not report['passed']:
        cfg['ai_enabled']=False; (PRIVATE/'http.json').write_text(json.dumps(cfg))
        subprocess.run(['docker','compose','-p','revisor','-f',str(OWN/'compose.yml'),
            'up','-d','--force-recreate','--no-deps','http'],check=True,capture_output=True)
    (OWN/'ai-delivery.json').write_text(json.dumps(state))
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if not report['passed']: raise SystemExit(1)


if __name__=='__main__': main()
