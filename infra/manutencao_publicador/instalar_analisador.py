#!/usr/bin/env python3
"""Instala a extensão autorizada do canal, com backup e retorno do código em falha."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tarfile
import time
import urllib.request

HERE = Path(__file__).resolve().parent
# Aceita o pacote fechado da instalação e a árvore versionada do repositório.
SOURCES = HERE if (HERE / 'analisador_manutencao.py').is_file() else HERE.parent / 'acessos'
ROOT = Path('/opt/plataforma')
BASE = Path('/usr/local/lib/meshcraft-analisador')
STATE = Path('/var/lib/meshcraft-analisador')
ACCESS = Path('/usr/local/lib/meshcraft-acessos')
EXEC = ROOT / 'analise-pratica/20261008-v3/executor_host.py'
IMAGE = 'meshcraft-analise-pratica:20261008-v3'
EXPECTED_IMAGE = 'sha256:e067accf6a9183c27f66c7181fe27659dba607d7f79a285acb08cb2f913b4a9c'
EXPECTED = {'robo_broker.py': 'b96e5a8cda01e224025d1209ed8dbc12fc934210126d7c1b563dd9480cfde02e',
            'robo_comando.py': '33239626420e6a6c9c4143076114b862326832a005ae40542bfc9ce2c9c57c6a'}
EXPECTED_EXEC = '4a1983010ac0327e90f23745020099d79dd9f32edb4b676f3b760db2680665f8'
UNITS = {
 'meshcraft-analisador-manutencao.socket': '''[Unit]
Description=Operacoes fechadas de manutencao do analisador
[Socket]
ListenStream=/run/meshcraft-analisador-manutencao.sock
SocketUser=root
SocketGroup=integrador
SocketMode=0660
RemoveOnStop=yes
[Install]
WantedBy=sockets.target
''',
 'meshcraft-analisador-manutencao.service': '''[Unit]
Description=Consulta e pedidos de manutencao do analisador
Requires=meshcraft-analisador-manutencao.socket
After=meshcraft-analisador-manutencao.socket
[Service]
ExecStart=/usr/bin/python3 /usr/local/lib/meshcraft-analisador/analisador_manutencao.py servir
User=root
Group=root
UMask=0077
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/var/lib/meshcraft-analisador
Restart=on-failure
''',
 'meshcraft-analisador-operacao.service': '''[Unit]
Description=Diagnostico ou recuperacao da versao preservada do analisador
[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /usr/local/lib/meshcraft-analisador/analisador_manutencao.py executar
User=root
Group=root
UMask=0077
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/var/lib/meshcraft-analisador /opt/plataforma/analise-pratica /opt/plataforma/backups-de-codigo /opt/plataforma/encomendas-arquivos /var/spool/cron
TimeoutStartSec=1800
TimeoutStopSec=30
'''
}


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def run(args, timeout=60, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=timeout, **kwargs)


def probe_site():
    req = urllib.request.Request('https://meshcraft.top/', headers={'User-Agent': 'meshcraft-manutencao-analisador/1'})
    with urllib.request.urlopen(req, timeout=30) as response:
        if response.status != 200:
            raise RuntimeError('site_indisponivel')


def anchors():
    current = Path('/usr/local/lib/meshcraft-publicador/atual').resolve(strict=True)
    fixed = Path('/usr/local/lib/meshcraft-publicador/v1-20261006T184415Z')
    paths = [ROOT/'traefik/dynamic/plataforma.yml', ROOT/'docker-compose.yml', ROOT/'bin/plataforma',
             Path('/home/robo/.ssh/authorized_keys'), Path('/home/deploy/.ssh/authorized_keys')]
    for base in (current, fixed):
        for rel in ('mercadopago/politica.json', 'infra/mercadopago_congelado.py',
                    'docs/politica.json', 'infra/docs_somente_admin.py', 'infra/publicar.py'):
            paths.append(base/rel)
    paths += list((ROOT/'env').glob('*.env'))
    return {str(p):sha(p) for p in paths}


def broker_request(action):
    code = ("import socket,json; s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM); s.settimeout(150); "
            "s.connect('/run/meshcraft-robo.sock'); s.sendall(json.dumps(['analisador','"+action+"']).encode()+b'\\n'); "
            "s.shutdown(socket.SHUT_WR); chunks=[]; "
            "exec('while True:\\n b=s.recv(65536)\\n if not b: break\\n chunks.append(b)'); print(b''.join(chunks).decode())")
    response = json.loads(run(['/usr/sbin/runuser', '-u', 'robo', '--', '/usr/bin/python3', '-c', code], timeout=160).stdout)
    if response.get('codigo') != 0:
        raise RuntimeError('canal_nao_confirmado')
    return json.loads(response['saida'])


def main():
    if os.geteuid() != 0:
        raise RuntimeError('console_administrativo_obrigatorio')
    os.umask(0o077)
    if BASE.exists():
        raise RuntimeError('instalacao_ja_existe_confira_o_resultado')
    for name, digest in EXPECTED.items():
        if sha(ACCESS/name) != digest:
            raise RuntimeError('versao_canal_divergente')
    if sha(EXEC) != EXPECTED_EXEC:
        raise RuntimeError('executor_divergente')
    if run(['/usr/bin/docker','image','inspect',IMAGE,'--format','{{.Id}}']).stdout.strip() != EXPECTED_IMAGE:
        raise RuntimeError('imagem_divergente')
    for name in UNITS:
        if (Path('/etc/systemd/system')/name).exists():
            raise RuntimeError('unidade_ja_existe')
    probe_site()
    before = anchors()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = ROOT/'backups-de-codigo'/('canal-analisador-'+stamp)
    backup.mkdir(mode=0o700)
    source_state = json.loads((ROOT/'publicacoes/aplicacao.json').read_text())
    live = Path(source_state['atual_versao']['codigo'])
    models = live/'modules/cursos/static/praticas-3d/modelos/espada-aurora/v3'
    for n in ('base.glb','fonte.blend'):
        if not (models/n).is_file():
            raise RuntimeError('amostra_ausente')
    (backup/'referencias-antes.json').write_text(json.dumps(before))
    for n in EXPECTED:
        shutil.copy2(ACCESS/n, backup/n)
    with tarfile.open(backup/'codigo-configuracoes.tar.gz','w:gz') as tar:
        for p in [ACCESS, EXEC.parent, ROOT/'env', ROOT/'publicacoes/aplicacao.json',
                  Path('/etc/systemd/system/meshcraft-robo.service'), Path('/etc/systemd/system/meshcraft-robo.socket')]:
            tar.add(p, arcname=str(p).lstrip('/'))
    with tarfile.open(backup/'codigo-configuracoes.tar.gz') as tar:
        tar.getmembers()
    with (backup/'backup-bancos.log').open('w') as log:
        r = subprocess.run([str(ROOT/'bin/plataforma'),'backup'], stdout=log, stderr=subprocess.STDOUT, timeout=900)
    if r.returncode:
        raise RuntimeError('backup_bancos_falhou')
    print('BACKUP_BANCOS_E_CODIGO_OK', str(backup), flush=True)
    BASE.mkdir(mode=0o755)
    STATE.mkdir(mode=0o700)
    ref = BASE/'referencia'
    ref.mkdir(mode=0o700)
    shutil.copy2(EXEC, ref/'executor_host.py')
    for n in ('base.glb','fonte.blend'):
        shutil.copyfile(models/n,ref/n)
        (ref/n).chmod(0o444)
    (ref/'invalido.glb').write_bytes(b'TESTE CONTROLADO. Texto sem geometria 3D.')
    (ref/'invalido.glb').chmod(0o444)
    # Salvar por ID deixa a copia independente do nome mutavel usado pela fila.
    run(['/usr/bin/docker','save','-o',str(ref/'imagem.tar'),EXPECTED_IMAGE],timeout=900)
    with tarfile.open(ref/'imagem.tar') as tar:
        manifest = json.load(tar.extractfile('manifest.json'))
        if any(x.get('RepoTags') for x in manifest):
            raise RuntimeError('copia_de_imagem_nao_isolada_do_nome')
    approved = {'imagem':IMAGE,'imagem_id':EXPECTED_IMAGE,
                'arquivos':{n:sha(ref/n) for n in ('base.glb','fonte.blend','invalido.glb','executor_host.py')},
                'imagem_tar_sha256':sha(ref/'imagem.tar'),'backup_instalacao':str(backup)}
    (BASE/'manifesto.json').write_text(json.dumps(approved))
    (backup/'imagem-preservada.json').write_text(json.dumps(approved))
    shutil.copyfile(SOURCES/'analisador_manutencao.py',BASE/'analisador_manutencao.py')
    (BASE/'analisador_manutencao.py').chmod(0o644)
    spec = importlib.util.spec_from_file_location('analisador',BASE/'analisador_manutencao.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    print('IMAGEM_PRESERVADA',EXPECTED_IMAGE,flush=True)
    before_change_proofs = mod.provar(EXPECTED_IMAGE, STATE/'prova-instalacao')
    print('PROVA_ANTES_DA_TROCA_OK',flush=True)
    changed = False
    try:
        for name, body in UNITS.items():
            p = Path('/etc/systemd/system')/name
            p.write_text(body)
            p.chmod(0o644)
        run(['/usr/bin/systemd-analyze','verify',*[str(Path('/etc/systemd/system')/n) for n in UNITS]])
        run(['/usr/bin/systemctl','daemon-reload'])
        run(['/usr/bin/systemctl','enable','--now','meshcraft-analisador-manutencao.socket'])
        changed = True
        for n in EXPECTED:
            temp = ACCESS/(n+'.analisador-novo')
            shutil.copyfile(SOURCES/n,temp)
            temp.chmod(0o755)
            os.replace(temp,ACCESS/n)
        run(['/usr/bin/systemctl','restart','meshcraft-robo.service'])
        result = broker_request('consultar')
        if result['estado'] != 'disponivel':
            raise RuntimeError('consulta_falhou')
        result_start = broker_request('diagnosticar')
        operation_id = result_start['operacao']['id']
        for _ in range(180):
            result = broker_request('consultar')
            op = result['ultima_operacao']
            if op['id'] != operation_id:
                raise RuntimeError('operacao_divergente')
            if op['estado'] in ('concluida','falhou','interrompida'):
                break
            time.sleep(2)
        if op['estado'] != 'concluida':
            raise RuntimeError('diagnostico_pelo_canal_falhou')
        if anchors() != before:
            raise RuntimeError('referencias_protegidas_divergiram')
        probe_site()
        evidence = {'estado':'instalado','backup':str(backup),'provas':before_change_proofs,
                    'consulta':result,'preservacoes_conferidas':len(before),'em':datetime.now(timezone.utc).isoformat()}
        (STATE/'instalacao.json').write_text(json.dumps(evidence,ensure_ascii=False))
        (backup/'CONCLUIDO').write_text('canal instalado, provas e site conferidos\n')
        print('INSTALADO_E_CONFERIDO',json.dumps(evidence,ensure_ascii=False),flush=True)
    except BaseException:
        if changed:
            for n in EXPECTED:
                shutil.copy2(backup/n, ACCESS/n)
            run(['/usr/bin/systemctl','restart','meshcraft-robo.service'])
        subprocess.run(['/usr/bin/systemctl','stop','meshcraft-analisador-operacao.service','meshcraft-analisador-manutencao.service'])
        subprocess.run(['/usr/bin/systemctl','disable','--now','meshcraft-analisador-manutencao.socket'])
        (backup/'CODIGO_RECUPERADO').write_text('broker anterior recuperado; nenhum banco restaurado\n')
        raise


if __name__ == '__main__':
    main()
