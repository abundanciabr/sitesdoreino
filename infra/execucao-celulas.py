"""Execução independente das células já extraídas, com troca reversível."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import uuid

RAIZ = Path(os.environ.get('PLATAFORMA_DIR', '/opt/plataforma'))
FERRAMENTAS = Path(__file__).resolve().parent
TOPOLOGIA = RAIZ / 'protecao-celulas/topologia.json'
PARES_FUNIL = ('catalogo', 'identidade', 'leads', 'alunos', 'notificacoes', 'mensageria', 'quiz')


def executar(*args):
    p = subprocess.run(list(map(str, args)), capture_output=True, text=True)
    if p.returncode:
        # Os parâmetros podem conter caminhos de ambientes; jamais imprimir
        # inspect completo, env, corpos HTTP ou saída de aplicação.
        raise RuntimeError(f'{args[0]} {args[1]} falhou ({p.returncode})')
    return p.stdout.strip()


def salvar(path, valor):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_name('.' + path.name + '-' + uuid.uuid4().hex)
    tmp.write_text(json.dumps(valor, sort_keys=True), 'utf-8')
    tmp.chmod(0o600)
    os.replace(tmp, path)


def topologia():
    return json.loads(TOPOLOGIA.read_text()) if TOPOLOGIA.exists() else {'celulas': {}}


def projetar(bundle, destino, celula):
    if celula != 'funil':
        raise ValueError('extração ainda não instalada para essa célula')
    if destino.exists():
        return
    tmp = destino.with_name('.' + destino.name + '-' + uuid.uuid4().hex)
    tmp.mkdir(parents=True)
    shutil.copytree(bundle / 'config', tmp / 'config')
    for nome in ('entrypoint.py', 'workers.py', 'internal.py'):
        shutil.copy2(bundle / nome, tmp / nome)
    (tmp / 'modules').mkdir()
    shutil.copy2(bundle / 'modules/__init__.py', tmp / 'modules/__init__.py')
    shutil.copytree(bundle / 'modules' / celula, tmp / 'modules' / celula)
    os.rename(tmp, destino)


def conferir_projecao(bundle, codigo, celula):
    from protecao_publicacao import arvore
    if set(p.name for p in (codigo / 'modules').iterdir()) != {'__init__.py', celula}:
        raise ValueError('código de outra célula na execução')
    for p in codigo.rglob('*'):
        if p.is_file():
            original = bundle / p.relative_to(codigo)
            if not original.is_file() or p.read_bytes() != original.read_bytes():
                raise ValueError('projeção diferente do código ensaiado')
    return arvore(codigo)


def rede(nome):
    if subprocess.run(['docker', 'network', 'inspect', nome], capture_output=True).returncode:
        executar('docker', 'network', 'create', '--internal', nome)


def conectar(rede, container, aliases=()):
    nomes = json.loads(executar('docker', 'inspect', '--format', '{{json .NetworkSettings.Networks}}', container))
    if rede not in nomes:
        args = ['docker', 'network', 'connect']
        for alias in aliases:
            args += ['--alias', alias]
        executar(*args, rede, container)


def argumentos(nome, imagem, memoria='128m', cpu='.2', pids='48'):
    return ['docker', 'create', '--name', nome, '--restart', 'unless-stopped',
        '--network', 'meshcraft-funil', '--user', '65532:65532', '--read-only',
        '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
        '--memory', memoria, '--memory-swap', memoria, '--cpus', cpu,
        '--pids-limit', pids, '--tmpfs', '/tmp:rw,nosuid,nodev,size=64m',
        '--label', 'meshcraft.celula=funil', '--label', 'meshcraft.protegida=1']


def garantir_pontes(imagem):
    rede('meshcraft-funil')
    ponte = 'br-' + executar('docker', 'network', 'inspect', '--format', '{{.Id}}', 'meshcraft-funil')[:12]
    if not re.fullmatch(r'br-[0-9a-f]{12}', ponte):
        raise ValueError('interface de isolamento desconhecida')
    # Nenhum acesso do executor aos serviços do host nem a outra rede Docker.
    # Unidade antes do Docker conserva a restrição após reinício da VPS.
    instalacao = '''
import pathlib,subprocess,sys
ponte=sys.argv[1];ferramentas=sys.argv[2]
unit=pathlib.Path('/host/etc/systemd/system/meshcraft-funil-rede.service')
texto='[Unit]\\nDescription=Rede privada da celula funil\\nBefore=docker.service\\nAfter=network-pre.target\\n[Service]\\nType=oneshot\\nRemainAfterExit=yes\\nExecStart=/bin/sh '+ferramentas+'/rede-celulas.sh '+ponte+'\\n[Install]\\nWantedBy=multi-user.target\\n'
unit.write_text(texto)
for comando in (['systemctl','daemon-reload'],['systemctl','enable','meshcraft-funil-rede.service'],['systemctl','restart','meshcraft-funil-rede.service']):
 subprocess.run(['chroot','/host',*comando],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
'''
    executar('docker', 'run', '--rm', '--network', 'host', '--pid', 'host',
        '--privileged', '-v', '/:/host', '--entrypoint', 'python', imagem, '-c',
        instalacao, ponte, str(FERRAMENTAS))
    # A aplicação só acessa a rede privada. Traefik e transportes fixados
    # recebem também os pares necessários, sem abrir porta no host.
    conectar('meshcraft-funil', 'plataforma-traefik-1')
    if subprocess.run(['docker', 'inspect', 'meshcraft-funil-api'], capture_output=True).returncode:
        args = argumentos('meshcraft-funil-api', imagem)
        executar(*args, '-v', f'{FERRAMENTAS / "ponte-celula.py"}:/ponte.py:ro',
                 '--entrypoint', 'python', imagem, '/ponte.py', 'http', '--destino', 'aplicacao')
        conectar('edge', 'meshcraft-funil-api')
        # Aliases são fixados na primeira conexão, feita abaixo após retirar
        # somente o endpoint ainda não iniciado; nenhum dado é apagado.
        executar('docker', 'network', 'disconnect', 'meshcraft-funil', 'meshcraft-funil-api')
        conectar('meshcraft-funil', 'meshcraft-funil-api', PARES_FUNIL)
        executar('docker', 'start', 'meshcraft-funil-api')
    if subprocess.run(['docker', 'inspect', 'meshcraft-funil-redis'], capture_output=True).returncode:
        executar('docker', 'volume', 'create', 'meshcraft-funil-redis')
        executar('docker', 'run', '--rm', '--network', 'none',
                 '-v', 'meshcraft-funil-redis:/data', '--entrypoint', 'chown',
                 'redis:7', '999:999', '/data')
        executar('docker', 'create', '--name', 'meshcraft-funil-redis', '--restart', 'unless-stopped',
            '--network', 'meshcraft-funil', '--memory', '96m', '--memory-swap', '96m',
            '--cpus', '.15', '--pids-limit', '32', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges', '--user', '999:999', '--read-only',
            '--tmpfs', '/tmp:rw,nosuid,nodev,size=16m',
            '-v', 'meshcraft-funil-redis:/data', '--entrypoint', 'redis-server',
            'redis:7', '--dir', '/data', '--appendonly', 'yes', '--maxmemory', '64mb',
            '--maxmemory-policy', 'noeviction', '--save', '')
        executar('docker', 'start', 'meshcraft-funil-redis')
    if subprocess.run(['docker', 'inspect', 'meshcraft-funil-eventos'], capture_output=True).returncode:
        args = argumentos('meshcraft-funil-eventos', imagem)
        executar(*args, '-v', f'{FERRAMENTAS / "ponte-celula.py"}:/ponte.py:ro',
            '--entrypoint', 'python', imagem, '/ponte.py', 'eventos',
            '--origem', 'redis://meshcraft-funil-redis:6379/0',
            '--destino', 'redis://plataforma-redis-1:6379/0')
        conectar('interna', 'meshcraft-funil-eventos')
        executar('docker', 'start', 'meshcraft-funil-eventos')


def ambiente_funil():
    destino = RAIZ / 'env-celulas/funil.env'
    if destino.exists():
        return destino
    destino.parent.mkdir(mode=0o700, exist_ok=True)
    texto = (RAIZ / 'env/funil.env').read_text()
    # Os mesmos signatários/cookies e tokens dos pares são preservados.
    # Esta célula não recebe DATABASE_URL nem ambientes de outras células.
    linhas = [l for l in texto.splitlines() if not l.startswith(
        ('DATABASE_URL=', 'REDIS_STREAMS_URL=', 'SITE_ERRORS_REDIS_URL='))]
    linhas += ['REDIS_STREAMS_URL=redis://meshcraft-funil-redis:6379/0',
               'SITE_ERRORS_REDIS_URL=redis://meshcraft-funil-redis:6379/0']
    destino.write_text('\n'.join(linhas) + '\n')
    destino.chmod(0o644)
    return destino


def iniciar(codigo, imagem, sha, nome=None):
    garantir_pontes(imagem)
    env = ambiente_funil()
    nome = nome or 'meshcraft-funil-' + sha[:12] + '-' + uuid.uuid4().hex[:8]
    args = argumentos(nome, imagem, '384m', '.5', '64')
    executar(*args, '-v', f'{codigo}:/app:ro', '-v', f'{env}:/run/plataforma-env/funil.env:ro',
        '-e', 'CELULA_EXECUCAO=funil', '-e', 'APLICACAO_MIGRAR=0',
        '-e', 'APLICACAO_ENV_DIR=/run/plataforma-env', '-e', 'PYTHONDONTWRITEBYTECODE=1',
        '-w', '/app', '--entrypoint', 'python', imagem, 'entrypoint.py')
    executar('docker', 'start', nome)
    for _ in range(30):
        p = subprocess.run(['docker', 'exec', nome, 'python', '-c',
            "import urllib.request;assert urllib.request.urlopen('http://localhost:8000/healthz',timeout=2).status==200"],
            capture_output=True)
        if p.returncode == 0:
            # A saúde sozinha não confirma os pares de API nem o HTML servido.
            executar('docker', 'exec', nome, 'python', '-c',
                "import urllib.request; r=urllib.request.Request('http://localhost:8000/',headers={'Host':'meshcraft.top','X-Forwarded-Proto':'https'}); "
                "s=urllib.request.urlopen(r,timeout=25); assert s.status==200; assert b'<html' in s.read().lower()")
            return nome
        time.sleep(2)
    executar('docker', 'stop', nome)
    raise RuntimeError('célula não ficou saudável; rota preservada')


def apontar(nome, arquivo=None):
    arquivo = arquivo or RAIZ / 'traefik/dynamic/plataforma.yml'
    texto = arquivo.read_text()
    novo, quantidade = re.subn(
        r'(\n  services:\s*\n    funil:\s*\n      loadBalancer:\s*\n        servers: \[ \{ url: ")[^"]+(" \} \])',
        lambda m: m[1] + 'http://' + nome + ':8000' + m[2], texto)
    if quantidade != 1:
        raise ValueError('rota da célula não identificada de forma única')
    temp = arquivo.with_name('.' + arquivo.name + '.novo')
    temp.write_text(novo)
    os.replace(temp, arquivo)


def provar_site():
    for origem in (False, True):
        args = ['curl', '--silent', '--show-error', '--retry', '4', '--retry-delay', '2',
                '--max-time', '15', '--output', '/dev/null', '--write-out', '%{http_code}']
        if origem:
            args += ['--resolve', 'meshcraft.top:443:127.0.0.1']
        if executar(*args, 'https://meshcraft.top/') != '200':
            raise RuntimeError('prova da origem ou endereço público falhou')


def ativar(codigo, imagem, sha, pacote, nome=None):
    topo = topologia()
    anterior = topo['celulas'].get('funil')
    nome = iniciar(codigo, imagem, sha, nome=nome)
    topo['em_troca'] = {'celula': 'funil', 'container': nome, 'anterior': anterior}
    salvar(TOPOLOGIA, topo)
    try:
        apontar(nome)
        time.sleep(3)
        provar_site()
        from protecao_publicacao import identificar
        if identificar(codigo, imagem, RAIZ / 'docker-compose.yml') != pacote:
            raise ValueError('configuração final diferente da combinação ensaiada')
    except BaseException:
        apontar(anterior['container'] if anterior else 'aplicacao')
        time.sleep(3)
        provar_site()
        executar('docker', 'stop', nome)
        topo.pop('em_troca', None)
        salvar(TOPOLOGIA, topo)
        raise
    entrada = {'sha': sha, 'container': nome, 'codigo': str(codigo),
        'imagem': imagem, 'pacote': pacote, 'aprovada_em': datetime.now(timezone.utc).isoformat(),
        'anterior': anterior}
    topo['celulas']['funil'] = entrada
    topo.pop('em_troca', None)
    salvar(TOPOLOGIA, topo)
    salvar(RAIZ / 'publicacoes/funil.json', {'celula': 'funil', 'atual': sha, 'aprovada': entrada})
    if anterior:
        executar('docker', 'stop', anterior['container'])
    return entrada


def preservar_rotas():
    topo = topologia()
    for celula, estado in topo['celulas'].items():
        if celula == 'funil':
            conectar('meshcraft-funil', 'plataforma-traefik-1')
            apontar(estado['container'])


def vigiar():
    import fcntl
    trava = (RAIZ / 'publicacoes/lotes/.lote.lock').open('a')
    try:
        fcntl.flock(trava, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        trava.close()
        return
    try:
        vigiar_travado()
    finally:
        trava.close()


def vigiar_travado():
    retomar_troca()
    for celula, estado in topologia()['celulas'].items():
        p = subprocess.run(['docker', 'exec', estado['container'], 'python', '-c',
            "import urllib.request;assert urllib.request.urlopen('http://localhost:8000/healthz',timeout=3).status==200"],
            capture_output=True)
        if p.returncode:
            executar('docker', 'restart', estado['container'])
            time.sleep(5)


def retomar_troca():
    topo = topologia()
    troca = topo.get('em_troca')
    if troca:
        anterior = troca.get('anterior')
        if anterior:
            executar('docker', 'start', anterior['container'])
        apontar(anterior['container'] if anterior else 'aplicacao')
        topo.pop('em_troca')
        salvar(TOPOLOGIA, topo)
        executar('docker', 'stop', troca['container'])


def publicar(publicador, sha, registro):
    """Prova a combinação completa e promove só a projeção byte a byte."""
    from protecao_publicacao import identificar, ensaiar, imagem_id
    retomar_troca()
    celula = 'funil'
    fonte = RAIZ / 'publicacoes/trabalho' / ('funil-' + sha + '-' + uuid.uuid4().hex)
    publicador.extrair(sha, fonte)
    bundle, imagem, _, _ = publicador.preparar_codigo('aplicacao', sha, fonte, registro)
    imagem = imagem_id(imagem)
    codigo = RAIZ / 'versoes/funil' / sha
    projetar(bundle, codigo, celula)
    projecao = conferir_projecao(bundle, codigo, celula)
    antes = identificar(codigo, imagem, RAIZ / 'docker-compose.yml')
    nome = 'meshcraft-funil-' + sha[:12] + '-' + uuid.uuid4().hex[:8]
    configuracao = fonte / 'configuracao-final'
    configuracao.mkdir(mode=0o700)
    shutil.copy2(RAIZ / 'docker-compose.yml', configuracao / 'docker-compose.yml')
    shutil.copy2(RAIZ / '.env', configuracao / '.env')
    for pasta in ('env', 'env-celulas', 'traefik'):
        alvo = configuracao / pasta
        alvo.mkdir()
        if pasta == 'traefik':
            shutil.copytree(RAIZ / pasta, alvo, dirs_exist_ok=True)
        else:
            for env in (RAIZ / pasta).glob('*.env'):
                shutil.copy2(env, alvo / env.name)
    (configuracao / 'protecao-celulas').mkdir()
    shutil.copy2(RAIZ / 'protecao-celulas/politica.json', configuracao / 'protecao-celulas/politica.json')
    apontar(nome, arquivo=configuracao / 'traefik/dynamic/plataforma.yml')
    pacote = identificar(codigo, imagem, configuracao / 'docker-compose.yml')
    provas = RAIZ / 'publicacoes/provas' / pacote['id']
    resultado_funil = ensaiar_funil(fonte / 'services/funil', imagem, publicador.FERRAMENTAS, provas)
    resultado = ensaiar(bundle, imagem, publicador.FERRAMENTAS, provas, registro)
    if (identificar(codigo, imagem, RAIZ / 'docker-compose.yml') != antes
            or identificar(codigo, imagem, configuracao / 'docker-compose.yml') != pacote
            or conferir_projecao(bundle, codigo, celula) != projecao):
        raise ValueError('pacote alterado durante a prova')
    if sha != publicador.git('rev-parse', 'refs/heads/main'):
        raise ValueError('publicação superada; prova da combinação nova necessária')
    salvar(provas / 'pacote.json', {'sha': sha, 'celula': celula, 'pacote': pacote,
        'resultado': resultado, 'funil': resultado_funil,
        'bundle': str(bundle), 'projecao_sha256': projecao})
    subprocess.run(['bash', str(FERRAMENTAS / 'backup-do-banco.sh'), 'funil-' + sha[:12]],
        env=publicador.ambiente_base() | {'PRESERVAR_COPIAS': '1'},
        stdout=registro, stderr=subprocess.STDOUT, check=True)
    # A cópia anterior e o banco são preservados; código incompatível não
    # chega a essa extração, que não tem migrações nem banco próprio.
    if identificar(codigo, imagem, RAIZ / 'docker-compose.yml') != antes:
        raise ValueError('configuração mudou antes da troca')
    if sha != publicador.git('rev-parse', 'refs/heads/main'):
        raise ValueError('publicação superada durante a cópia; rota preservada')
    entrada = ativar(codigo, imagem, sha, pacote, nome=nome)
    print('CELULA-NO-AR: funil ' + sha, flush=True)
    return entrada


def ensaiar_funil(fonte, imagem, ferramentas, provas):
    from protecao_publicacao import conferir_relatorio, resumir_relatorio
    provas.mkdir(parents=True, exist_ok=True)
    nome = 'meshcraft-prova-funil-' + uuid.uuid4().hex
    try:
        args = ['docker', 'run', '--name', nome, '--network', 'none',
            '--user', '65532:65532', '--read-only', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges', '--memory', '512m',
            '--cpus', '.75', '--pids-limit', '64', '--tmpfs', '/tmp:rw,nosuid,nodev,size=128m',
            '-v', f'{fonte}:/app:ro', '-v', f'{ferramentas / "provas-funil/tests"}:/app/tests:ro',
            '-v', f'{ferramentas / "provas-funil/pytest.ini"}:/app/pytest.ini:ro',
            '-e', 'DJANGO_SECRET_KEY=chave-sintetica-para-o-ensaio', '-e', 'PYTHONDONTWRITEBYTECODE=1',
            '-e', 'PYTHONPATH=/app', '-e', 'HOME=/tmp', '-w', '/app', '--entrypoint', 'sh', imagem,
            '-c', 'python -m pytest tests -q -p no:cacheprovider --junitxml=/tmp/funil.xml >/tmp/prova.log 2>&1; rc=$?; echo RESULTADO:$rc; sleep 300']
        # O processo permanece vivo só para ler o relatório da área temporária.
        args.insert(2, '-d')
        executar(*args)
        for _ in range(600):
            logs = executar('docker', 'logs', nome)
            if 'RESULTADO:' in logs:
                xml = subprocess.check_output(['docker', 'exec', nome, 'cat', '/tmp/funil.xml'])
                (provas / 'funil.xml').write_bytes(xml)
                resumir_relatorio(provas / 'funil.xml')
                if 'RESULTADO:0' not in logs:
                    raise ValueError('provas das páginas de entrada falharam; relatório preservado')
                return conferir_relatorio(provas / 'funil.xml')
            if executar('docker', 'inspect', '--format', '{{.State.Running}}', nome) != 'true':
                raise ValueError('prova da célula interrompida')
            time.sleep(1)
        raise ValueError('prova da célula excedeu o prazo')
    finally:
        subprocess.run(['docker', 'rm', '-f', nome], capture_output=True)

