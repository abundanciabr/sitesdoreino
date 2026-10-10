"""Apply or restore only the exact test route authorized by the maintainer.

Runs natively in the maintainer's administrative hosting console. The
independent checker remains unchanged and validates before and after.
"""
from pathlib import Path
import fcntl
import hashlib
import importlib.util
import json
import os
import secrets
import sys

ROOT=Path('/opt/plataforma')
TASK=ROOT/'appmax-clones/checkout-roblox-20261009'
TOOLS=Path('/usr/local/lib/meshcraft-publicador/v1-20261006T184415Z')
POLICY=TOOLS/'mercadopago/politica.json'
ROUTES=ROOT/'traefik/dynamic/plataforma.yml'


def sha(content):return hashlib.sha256(content).hexdigest()


def load_checker():
    spec=importlib.util.spec_from_file_location('frozen',TOOLS/'infra/mercadopago_congelado.py')
    frozen=importlib.util.module_from_spec(spec);spec.loader.exec_module(frozen)
    return frozen


def replace(path,content):
    original=path.stat()
    if path.is_symlink():raise RuntimeError('Symbolic target refused')
    temporary=path.with_name(path.name+'.appmax-autorizado-'+secrets.token_hex(4)+'.tmp')
    with os.fdopen(os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,original.st_mode&0o777),'wb') as file:
        file.write(content);file.flush();os.fsync(file.fileno())
    os.chown(temporary,original.st_uid,original.st_gid)
    os.chmod(temporary,original.st_mode&0o777)
    os.replace(temporary,path)


def perform_locked(action):
    if os.geteuid()!=0:raise RuntimeError('Administrative execution required')
    if action not in ('apply','rollback'):raise RuntimeError('Invalid operation')
    proof=json.loads((TASK/'publicacao-rota-preparada.json').read_text())
    backup=Path(proof['backup_privado'])
    if backup.parent!=TASK or not backup.name.startswith('backup-antes-publicar-rota-'):
        raise RuntimeError('Unexpected backup')
    old_routes=(backup/'rotas-anteriores.yml').read_bytes()
    new_routes=(backup/'candidata/traefik/dynamic/plataforma.yml').read_bytes()
    old_policy=(backup/'politica-anterior.json').read_bytes()
    new_policy=(backup/'politica-candidata.json').read_bytes()
    for content,key in ((old_routes,'rota_anterior_arquivo_sha256'),(new_routes,'rota_candidata_arquivo_sha256'),
                        (old_policy,'politica_anterior_sha256'),(new_policy,'politica_candidata_sha256')):
        if sha(content)!=proof[key]:raise RuntimeError('Prepared bytes changed')
    before_policy=json.loads(old_policy);after_policy=json.loads(new_policy)
    expected=dict(before_policy);expected['rotas_sha256']=proof['rotas_normalizadas_depois']
    if after_policy!=expected or before_policy['rotas_sha256']!=proof['rotas_normalizadas_antes']:
        raise RuntimeError('Policy change exceeds authorized route reference')
    if proof['autorizacao']['resposta_do_mantenedor']!='Autorizar somente essa rota em modo de teste':
        raise RuntimeError('Specific authorization absent')
    frozen=load_checker()
    source_routes,target_routes=(old_routes,new_routes) if action=='apply' else (new_routes,old_routes)
    source_policy,target_policy=(old_policy,new_policy) if action=='apply' else (new_policy,old_policy)
    if ROUTES.read_bytes()!=source_routes or POLICY.read_bytes()!=source_policy:
        raise RuntimeError('Live state differs from coordinated operation')
    approved=json.loads((ROOT/'publicacoes/aplicacao.json').read_text())['aprovada']
    frozen.conferir_ambiente(ROOT,json.loads(source_policy))
    frozen.conferir_pacote(approved['codigo'],approved['imagem'],json.loads(source_policy))
    frozen.conferir_rotas(ROOT,json.loads(source_policy))
    frozen.conferir_rotas(backup/'candidata',after_policy)
    try:
        replace(POLICY,target_policy)
        replace(ROUTES,target_routes)
        frozen.conferir_ambiente(ROOT,json.loads(target_policy))
        frozen.conferir_pacote(approved['codigo'],approved['imagem'],json.loads(target_policy))
        frozen.conferir_rotas(ROOT,json.loads(target_policy))
    except Exception:
        replace(ROUTES,source_routes);replace(POLICY,source_policy)
        frozen.conferir_ambiente(ROOT,json.loads(source_policy))
        frozen.conferir_rotas(ROOT,json.loads(source_policy))
        raise
    return {'operacao':action,'somente_rota_autorizada':True,'verificador_preservado':True,
        'codigo_imagem_configuracoes_mp_preservados':True,'politica_modo':oct(POLICY.stat().st_mode&0o777)}


def main():
    action=sys.argv[1] if len(sys.argv)==2 else ''
    with (ROOT/'publicacoes/.receber.lock').open('a') as receiving, (ROOT/'publicacoes/.ativacao.lock').open('a') as activation:
        fcntl.flock(receiving,fcntl.LOCK_EX);fcntl.flock(activation,fcntl.LOCK_EX)
        print(json.dumps(perform_locked(action)))


if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps({'operacao_concluida':False,'erro_tipo':type(error).__name__}))
        raise SystemExit(1)
