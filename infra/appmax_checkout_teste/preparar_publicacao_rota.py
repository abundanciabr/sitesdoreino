"""Back up the approved site and prepare only the human-authorized test route."""
from pathlib import Path
from urllib.parse import urlparse, unquote
import datetime
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import tarfile

ROOT=Path('/opt/plataforma')
TASK=ROOT/'appmax-clones/checkout-roblox-20261009'
TOOLS=Path('/usr/local/lib/meshcraft-publicador/v1-20261006T184415Z')
POLICY=TOOLS/'mercadopago/politica.json'
ROUTES=ROOT/'traefik/dynamic/plataforma.yml'
BASE='/checkout/comprar-desafio-como-ganhar-em-dolar-com-roblox'
ROUTER='checkout-appmax-roblox-teste'


def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            digest.update(block)
    return digest.hexdigest()


def env(path):
    values={}
    for raw in path.read_text().splitlines():
        line=raw.strip()
        if not line or line.startswith('#'):continue
        if line.startswith('export '):line=line[7:].lstrip()
        key,sep,value=line.partition('=')
        if sep:
            value=value.strip()
            if value[:1] in ('"',"'") and value[-1:]==value[:1]:value=value[1:-1]
            elif ' #' in value:value=value.split(' #',1)[0].rstrip()
            values[key.strip()]=value
    return values


def run_file(command,target,data=None):
    with os.fdopen(os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as file:
        result=subprocess.run(command,input=data,stdout=file,stderr=subprocess.PIPE,timeout=300)
    if result.returncode:raise RuntimeError('Private backup failed')


def main():
    if not hasattr(os,'geteuid') or os.geteuid()!=0:
        raise RuntimeError('Use the maintainer administrative hosting console')
    spec=importlib.util.spec_from_file_location('frozen',TOOLS/'infra/mercadopago_congelado.py')
    frozen=importlib.util.module_from_spec(spec);spec.loader.exec_module(frozen)
    policy=json.loads(POLICY.read_text())
    approved=json.loads((ROOT/'publicacoes/aplicacao.json').read_text())['aprovada']
    frozen.conferir_ambiente(ROOT,policy)
    frozen.conferir_pacote(approved['codigo'],approved['imagem'],policy)
    frozen.conferir_rotas(ROOT,policy)
    old=ROUTES.read_text()
    if re.search(r'(?m)^    '+re.escape(ROUTER)+r':\s*$',old):
        raise RuntimeError('Authorized route already exists; inspect it first')
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup=TASK/('backup-antes-publicar-rota-'+stamp)
    backup.mkdir(mode=0o700)
    authorization={'pedido':'Publicar somente a rota do checkout Appmax em modo de teste',
        'url':'https://meshcraft.top'+BASE+'/',
        'resposta_do_mantenedor':'Autorizar somente essa rota em modo de teste'}
    (backup/'autorizacao.json').write_text(json.dumps(authorization,indent=2,ensure_ascii=False))
    os.chmod(backup/'autorizacao.json',0o600)
    for source,name in ((POLICY,'politica-anterior.json'),(ROUTES,'rotas-anteriores.yml')):
        (backup/name).write_bytes(source.read_bytes());os.chmod(backup/name,0o600)
    archive_path=backup/'codigo-configuracao-antes.tar.gz'
    with os.fdopen(os.open(archive_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as file:
        with tarfile.open(fileobj=file,mode='w:gz') as archive:
            for source,name in ((Path(approved['codigo']),'codigo-original'),(ROOT/'.env','configuracao/.env'),
                                (ROOT/'docker-compose.yml','configuracao/docker-compose.yml'),
                                (ROOT/'traefik','configuracao/traefik'),
                                (ROOT/'publicacoes/aplicacao.json','configuracao/aplicacao.json'),
                                (POLICY,'configuracao/politica.json')):
                archive.add(source,arcname=name)
            for source in (ROOT/'env').glob('*.env'):
                archive.add(source,arcname='configuracao/env/'+source.name)
            for source in (TASK/'env-privado').glob('*.env'):
                archive.add(source,arcname='configuracao-clone/'+source.name)
            archive.add(TASK/'servico',arcname='servico-clone')
            archive.add(TASK/'codigo-aprovado-copia',arcname='codigo-aprovado-clone')
    with tarfile.open(archive_path,'r:gz') as archive:
        if len(archive.getmembers())<50:raise RuntimeError('Source backup incomplete')
    print(json.dumps({'etapa':'backup_codigo_e_configuracao_conferido'}),flush=True)
    image=backup/'imagem-aprovada.tar'
    run_file(['docker','image','save',approved['imagem']],image)
    with tarfile.open(image) as archive:
        manifest=json.loads(archive.extractfile('manifest.json').read())
        config=archive.extractfile(manifest[0]['Config']).read()
        expected_blob='blobs/sha256/'+approved['imagem'].split(':',1)[1]
        config_matches='sha256:'+hashlib.sha256(config).hexdigest()==approved['imagem']
        oci_matches=expected_blob in archive.getnames() and (
            'sha256:'+hashlib.sha256(archive.extractfile(expected_blob).read()).hexdigest()==approved['imagem'])
        if not config_matches and not oci_matches:
            raise RuntimeError('Image backup does not match approved image')
    databases={}
    for service in ('checkout','pagamentos'):
        source=urlparse(env(ROOT/'env'/(service+'.env'))['DATABASE_URL'])
        values=tuple(unquote(v) for v in (source.username or '',source.password or '',source.path.lstrip('/')))
        if any('\n' in v or '\r' in v for v in values):raise RuntimeError('Invalid database connection format')
        command='IFS= read -r PGUSER; IFS= read -r PGPASSWORD; IFS= read -r PGDATABASE; export PGUSER PGPASSWORD PGDATABASE; exec pg_dump --format=custom --no-owner --no-privileges'
        target=backup/(service+'.dump')
        run_file(['docker','exec','-i','plataforma-postgres-1','sh','-c',command],target,('\n'.join(values)+'\n').encode())
        checked=subprocess.run(['docker','exec','-i','plataforma-postgres-1','pg_restore','--list'],input=target.read_bytes(),capture_output=True,timeout=120)
        if checked.returncode or len(checked.stdout.splitlines())<20:
            raise RuntimeError('Database backup cannot be read')
        databases[service]={'arquivo':str(target),'sha256':sha(target),'bytes':target.stat().st_size,'arquivo_conferido':True}
    clone_databases={}
    clone_folder=backup/'bancos-clone';clone_folder.mkdir(mode=0o700)
    for path in sorted((TASK/'env-privado').glob('*.env')):
        database_url=env(path).get('DATABASE_URL')
        if not database_url:continue
        source=urlparse(database_url)
        if source.hostname!='postgres' or source.username!='appmax_clone':
            raise RuntimeError('A clone database is not isolated')
        values=tuple(unquote(v) for v in (source.username or '',source.password or '',source.path.lstrip('/')))
        if any('\n' in v or '\r' in v for v in values):raise RuntimeError('Invalid clone database connection')
        command='IFS= read -r PGUSER; IFS= read -r PGPASSWORD; IFS= read -r PGDATABASE; export PGUSER PGPASSWORD PGDATABASE; exec pg_dump --format=custom --no-owner --no-privileges'
        target=clone_folder/(path.stem+'.dump')
        container='meshcraft-appmax-roblox-sandbox-postgres-20261009'
        run_file(['docker','exec','-i',container,'sh','-c',command],target,('\n'.join(values)+'\n').encode())
        checked=subprocess.run(['docker','exec','-i',container,'pg_restore','--list'],input=target.read_bytes(),capture_output=True,timeout=120)
        if checked.returncode or len(checked.stdout.splitlines())<20:
            raise RuntimeError('Clone database backup cannot be read')
        clone_databases[path.stem]={'arquivo':str(target),'sha256':sha(target),'bytes':target.stat().st_size,'arquivo_conferido':True}
    if not all(name in clone_databases for name in ('catalogo','checkout','pagamentos')):
        raise RuntimeError('Related clone database backups are incomplete')
    print(json.dumps({'etapa':'backup_imagem_e_dois_bancos_conferido'}),flush=True)
    router=f'''    {ROUTER}:
      rule: "Host(`meshcraft.top`) && (Path(`{BASE}`) || PathPrefix(`{BASE}/`))"
      service: "{ROUTER}"
      entryPoints: ["websecure"]
      priority: 30
      middlewares: ["seguranca"]
      tls: {{}}
'''
    service=f'''    {ROUTER}:
      loadBalancer:
        servers: [ {{ url: "http://meshcraft-checkout-appmax-roblox-20261009:8000" }} ]
'''
    marker='  services:\n'
    if old.count(marker)!=1:raise RuntimeError('Unexpected services section')
    candidate=old.replace(marker,router+marker,1)
    start=candidate.index(marker)+len(marker)
    following=re.search(r'(?m)^  [A-Za-z][A-Za-z0-9_-]*:[ \t]*$',candidate[start:])
    end=start+following.start() if following else len(candidate)
    candidate=candidate[:end]+service+candidate[end:]
    if candidate.replace(router,'',1).replace(service,'',1)!=old:
        raise RuntimeError('Changes exceed authorized router and service')
    new_router={'rule':f'Host(`meshcraft.top`) && (Path(`{BASE}`) || PathPrefix(`{BASE}/`))',
        'service':ROUTER,'entryPoints':['websecure'],'priority':30,'middlewares':['seguranca'],'tls':{}}
    new_service={'loadBalancer':{'servers':[{'url':'http://meshcraft-checkout-appmax-roblox-20261009:8000'}]}}
    candidate_root=backup/'candidata'
    route_folder=candidate_root/'traefik/dynamic';route_folder.mkdir(parents=True,mode=0o700)
    candidate_path=route_folder/'plataforma.yml'
    candidate_path.write_text(candidate);os.chmod(candidate_path,0o600)
    new_hash=frozen.capturar_rotas(candidate_root)
    candidate_policy=dict(policy);candidate_policy['rotas_sha256']=new_hash
    frozen.conferir_rotas(candidate_root,candidate_policy)
    original_policy_bytes=POLICY.read_bytes()
    pattern=rb'("rotas_sha256"\s*:\s*")'+policy['rotas_sha256'].encode()+rb'(")'
    if len(re.findall(pattern,original_policy_bytes))!=1:raise RuntimeError('Unexpected policy representation')
    proposed_policy=re.sub(pattern,lambda match:match.group(1)+new_hash.encode()+match.group(2),original_policy_bytes)
    if json.loads(proposed_policy)!=candidate_policy:raise RuntimeError('Unauthorized policy change')
    (backup/'politica-candidata.json').write_bytes(proposed_policy);os.chmod(backup/'politica-candidata.json',0o600)
    # A concurrent normal funnel publication is allowed by the independent
    # checker, but this prepared candidate must still match its exact source.
    if ROUTES.read_text()!=old or POLICY.read_bytes()!=original_policy_bytes:
        raise RuntimeError('Live reference changed while preparing backup')
    frozen.conferir_ambiente(ROOT,policy)
    frozen.conferir_pacote(approved['codigo'],approved['imagem'],policy)
    proof={'backup_privado':str(backup),'codigo_original':approved['codigo'],'imagem':approved['imagem'],
        'codigo_configuracao_sha256':sha(archive_path),'imagem_backup_sha256':sha(image),'bancos':databases,
        'bancos_clone':clone_databases,
        'rota_anterior_arquivo_sha256':sha(ROUTES),'politica_anterior_sha256':sha(POLICY),
        'rota_candidata_arquivo_sha256':sha(candidate_path),'politica_candidata_sha256':sha(backup/'politica-candidata.json'),
        'rotas_normalizadas_antes':policy['rotas_sha256'],'rotas_normalizadas_depois':new_hash,
        'escopo':['adicionar somente router e service '+ROUTER,'atualizar somente rotas_sha256'],
        'novas_rotas':new_router,'novo_destino':new_service,'publicado':False,'original_alterado':False,
        'bancos_restaurados':False,'autorizacao':authorization,
        'conferido_em':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    (backup/'preparacao.json').write_text(json.dumps(proof,indent=2,ensure_ascii=False));os.chmod(backup/'preparacao.json',0o600)
    (TASK/'publicacao-rota-preparada.json').write_text(json.dumps(proof,indent=2,ensure_ascii=False));os.chmod(TASK/'publicacao-rota-preparada.json',0o600)
    print(json.dumps({'backup_privado':str(backup),'bancos_conferidos':2,'imagem_conferida':True,
        'diferenca_apenas_rota_autorizada':True,'publicado':False},ensure_ascii=False))


if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps({'preparado':False,'erro_tipo':type(error).__name__,'original_alterado':False}))
        raise SystemExit(1)
