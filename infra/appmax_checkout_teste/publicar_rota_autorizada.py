"""Publish the exact sandbox checkout, with automatic route-only recovery."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import re
import subprocess
import time
import urllib.request
import fcntl
from urllib.parse import urlparse

import aplicar_referencia_rota_root as reference
import preparar_publicacao_rota as preparation

ROOT=Path('/opt/plataforma')
TASK=ROOT/'appmax-clones/checkout-roblox-20261009'
TOOLS=Path('/usr/local/lib/meshcraft-publicador/v1-20261006T184415Z')
WEB='meshcraft-checkout-appmax-roblox-20261009'
URL='https://meshcraft.top/checkout/comprar-desafio-como-ganhar-em-dolar-com-roblox/'


def run(args,data=None):
    result=subprocess.run(args,input=data,capture_output=True,text=True,timeout=120)
    if result.returncode:raise RuntimeError('Administrative route operation failed')
    return result.stdout


def switch(action):
    # The maintainer runs this natively as root in the hosting console.
    # This helper neither obtains administrative access nor changes SSH access.
    result=reference.perform_locked(action)
    if not result.get('somente_rota_autorizada'):raise RuntimeError('Route swap not proven')
    return result


def fetch(url,host=None):
    request=urllib.request.Request(url,headers={'Host':host} if host else {})
    with urllib.request.urlopen(request,timeout=15) as response:
        return response.status,response.read().decode()


def assert_test_copy(current):
    if not current['State']['Running']:
        raise RuntimeError('Test copy is not running')
    if 'meshcraft-appmax-roblox-sandbox-20261009' not in current['NetworkSettings']['Networks']:
        raise RuntimeError('Exclusive sandbox network is absent')
    mounts={mount['Destination']:mount for mount in current.get('Mounts',[])}
    for destination,name in (('/clone','servico'),('/approved','codigo-aprovado-copia'),('/run/plataforma-env','env-privado')):
        mount=mounts.get(destination,{})
        if mount.get('Source')!=str(TASK/name) or mount.get('RW') is not False:
            raise RuntimeError('Read-only sandbox package mounts differ')
    for service in ('checkout','pagamentos'):
        values=preparation.env(TASK/'env-privado'/(service+'.env'))
        if values.get('APPMAX_API_URL')!='https://api.sandboxappmax.com.br':
            raise RuntimeError('Sandbox provider configuration is absent')
        database=urlparse(values['DATABASE_URL'])
        if database.hostname!='postgres' or database.username!='appmax_clone':
            raise RuntimeError('Exclusive sandbox database is absent')
        if any(value for key,value in values.items() if key.startswith('MP_')):
            raise RuntimeError('A Mercado Pago credential is present in the copy')
    source=Path(__file__).resolve().parents[2]/'services/checkout_appmax'
    for name in ('server.py','wrapper.py','worker.py','assets/checkout.html','assets/checkout.css','assets/checkout.js'):
        if (source/name).read_bytes()!=(TASK/'servico'/name).read_bytes():
            raise RuntimeError('Private copy differs from the delivered source')
    code,page=fetch('http://127.0.0.1:18049'+urlparse(URL).path,host='meshcraft.top')
    config=json.loads(re.search(r'<script id="checkout-config" type="application/json">(.*?)</script>',page,re.S).group(1))
    if code!=200 or config.get('environment')!='sandbox' or config.get('scriptURL')!='https://scripts.sandboxappmax.com.br/appmax.min.js':
        raise RuntimeError('Private sandbox page proof failed')


def current_pair(prepared):
    route=hashlib.sha256(reference.ROUTES.read_bytes()).hexdigest()
    policy=hashlib.sha256(reference.POLICY.read_bytes()).hexdigest()
    for state,suffix in (('before','anterior'),('after','candidata')):
        if route==prepared[f'rota_{suffix}_arquivo_sha256'] and policy==prepared[f'politica_{suffix}_sha256']:
            return state
    raise RuntimeError('Route recovery cannot identify the current reference')


def assert_frozen():
    frozen=reference.load_checker()
    policy=json.loads(reference.POLICY.read_text())
    approved=json.loads((ROOT/'publicacoes/aplicacao.json').read_text())['aprovada']
    frozen.conferir_ambiente(ROOT,policy)
    frozen.conferir_pacote(approved['codigo'],approved['imagem'],policy)
    frozen.conferir_pacote(TASK/'codigo-aprovado-copia',approved['imagem'],policy)
    frozen.conferir_rotas(ROOT,policy)


def activate_locked():
    current=json.loads(run(['docker','inspect',WEB]))[0]
    assert_test_copy(current)
    preparation.main()
    prepared=json.loads((TASK/'publicacao-rota-preparada.json').read_text())
    current=json.loads(run(['docker','inspect',WEB]))[0]
    if current['Image']!=prepared['imagem']:raise RuntimeError('Clone image changed')
    network_added='edge' not in current['NetworkSettings']['Networks']
    if network_added:
        run(['docker','network','connect','edge',WEB])
    applied=False
    try:
        administrative=switch('apply');applied=True
        for attempt in range(15):
            try:
                code,page=fetch(URL)
                config=json.loads(re.search(r'<script id="checkout-config" type="application/json">(.*?)</script>',page,re.S).group(1))
                if code==200 and config.get('environment')=='sandbox' and config.get('scriptURL')=='https://scripts.sandboxappmax.com.br/appmax.min.js':
                    break
            except Exception:
                if attempt==14:raise RuntimeError('Published sandbox proof failed')
                time.sleep(1)
        else:raise RuntimeError('Published sandbox proof failed')
        http={URL:code}
        for url in ('https://meshcraft.top/','https://meshcraft.top/checkout/desafio-como-ganhar-em-dolar-com-roblox/',
                    URL+'assets/checkout.css',URL+'assets/checkout.js'):
            http[url]=fetch(url)[0]
        if any(status!=200 for status in http.values()):raise RuntimeError('Live health proof failed')
        if current_pair(prepared)!='after':raise RuntimeError('Authorized route reference changed')
        assert_frozen()
        proof={'publicado':True,'url':URL,'ambiente':'sandbox','cobrancas_reais_criadas':0,
            'mercado_pago_codigo_imagem_credenciais_preservados':True,'alteracao_apenas_rota_autorizada':True,
            'referencia_de_rotas_atualizada':True,'verificador_independente_preservado':True,
            'backup_privado':prepared['backup_privado'],'bancos_restaurados':False,'http':http,
            'operacao_administrativa':administrative,
            'conferido_em':datetime.datetime.now(datetime.timezone.utc).isoformat()}
        (TASK/'prova-publicacao.json').write_text(json.dumps(proof,indent=2,ensure_ascii=False));os.chmod(TASK/'prova-publicacao.json',0o600)
        print(json.dumps(proof,ensure_ascii=False))
    except Exception:
        if current_pair(prepared)=='after':
            switch('rollback')
            applied=True
        if current_pair(prepared)!='before':raise RuntimeError('Route recovery was not proven')
        assert_frozen()
        if network_added:
            run(['docker','network','disconnect','edge',WEB])
        print(json.dumps({'publicado':False,'rota_anterior_restaurada':applied,'bancos_restaurados':False}))
        raise


def main():
    if not hasattr(os,'geteuid') or os.geteuid()!=0:
        raise RuntimeError('Use the maintainer administrative hosting console')
    with (ROOT/'publicacoes/.receber.lock').open('a') as receiving, (ROOT/'publicacoes/.ativacao.lock').open('a') as activation:
        fcntl.flock(receiving,fcntl.LOCK_EX)
        fcntl.flock(activation,fcntl.LOCK_EX)
        activate_locked()


if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps({'publicado':False,'erro_tipo':type(error).__name__}))
        raise SystemExit(1)
