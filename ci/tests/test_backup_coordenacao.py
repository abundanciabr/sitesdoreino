import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

import pytest


RAIZ = Path(__file__).resolve().parents[2]


def carregar(caminho):
    spec = importlib.util.spec_from_file_location(caminho.stem.replace('-', '_'), caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_pacote_cms_autenticado_e_transporte(tmp_path):
    backup = carregar(RAIZ / 'infra' / 'backup-coordenacao.py')
    verificador = carregar(RAIZ / 'ci' / 'backup_coordenacao.py')
    cert = tmp_path / 'destinatario.pem'
    cert.write_text(backup.CERTIFICADO)
    pacote = tmp_path / '123.p7m'
    subprocess.run(
        ['openssl', 'cms', '-encrypt', '-binary', '-outform', 'DER',
         '-aes-256-gcm', '-recip', str(cert), '-keyopt', 'rsa_padding_mode:oaep',
         '-keyopt', 'rsa_oaep_md:sha256', '-out', str(pacote)],
        input=b'pacote de ensaio', check=True,
    )
    resumo = tmp_path / 'resumo.json'
    resumo.write_text(json.dumps({
        'arquivo': pacote.name, 'bytes': pacote.stat().st_size,
        'sha256': hashlib.sha256(pacote.read_bytes()).hexdigest(),
        'capturado_em_utc': '2026-09-29T00:00:00Z',
    }))
    verificador.verificar(resumo, pacote)
    dados = bytearray(pacote.read_bytes())
    dados[-1] ^= 1
    pacote.write_bytes(dados)
    with pytest.raises(ValueError, match='SHA-256 divergiu'):
        verificador.verificar(resumo, pacote)

    fraco = tmp_path / '124.p7m'
    subprocess.run(
        ['openssl', 'cms', '-encrypt', '-binary', '-outform', 'DER',
         '-aes-256-gcm', '-recip', str(cert), '-keyopt', 'rsa_padding_mode:oaep',
         '-out', str(fraco)], input=b'pacote com OAEP SHA-1', check=True,
    )
    resumo.write_text(json.dumps({
        'arquivo': fraco.name, 'bytes': fraco.stat().st_size,
        'sha256': hashlib.sha256(fraco.read_bytes()).hexdigest(),
        'capturado_em_utc': '2026-09-29T00:00:00Z',
    }))
    with pytest.raises(ValueError, match='MGF1'):
        verificador.verificar(resumo, fraco)

    dois = tmp_path / '125.p7m'
    subprocess.run(
        ['openssl', 'cms', '-encrypt', '-binary', '-outform', 'DER',
         '-aes-256-gcm', '-recip', str(cert), '-keyopt', 'rsa_padding_mode:oaep',
         '-keyopt', 'rsa_oaep_md:sha256', '-recip', str(cert),
         '-keyopt', 'rsa_padding_mode:oaep', '-keyopt', 'rsa_oaep_md:sha256',
         '-out', str(dois)], input=b'dois destinatarios', check=True,
    )
    resumo.write_text(json.dumps({
        'arquivo': dois.name, 'bytes': dois.stat().st_size,
        'sha256': hashlib.sha256(dois.read_bytes()).hexdigest(),
        'capturado_em_utc': '2026-09-29T00:00:00Z',
    }))
    with pytest.raises(ValueError, match='MGF1'):
        verificador.verificar(resumo, dois)

    cifra_fraca = tmp_path / '126.p7m'
    subprocess.run(
        ['openssl', 'cms', '-encrypt', '-binary', '-outform', 'DER',
         '-aes-128-gcm', '-recip', str(cert), '-keyopt', 'rsa_padding_mode:oaep',
         '-keyopt', 'rsa_oaep_md:sha256', '-out', str(cifra_fraca)],
        input=b'AES com chave curta', check=True,
    )
    resumo.write_text(json.dumps({
        'arquivo': cifra_fraca.name, 'bytes': cifra_fraca.stat().st_size,
        'sha256': hashlib.sha256(cifra_fraca.read_bytes()).hexdigest(),
        'capturado_em_utc': '2026-09-29T00:00:00Z',
    }))
    with pytest.raises(ValueError, match='AES-256-GCM'):
        verificador.verificar(resumo, cifra_fraca)


def test_restauro_recusa_banco_oficial_antes_de_ler_chave(tmp_path):
    restaurador = carregar(RAIZ / 'infra' / 'restaurar-coordenacao.py')
    with pytest.raises(ValueError, match='Destino recusado'):
        restaurador.executar(tmp_path / 'pacote', tmp_path / 'cert',
                             tmp_path / 'chave', 'coordenacao_db', '0' * 64)


def test_restaurador_confere_nove_hashes_e_bloqueia_retomada(tmp_path, monkeypatch, capsys):
    restaurador = carregar(RAIZ / 'infra' / 'restaurar-coordenacao.py')
    linhas = {nome: [] for nome in restaurador.TABELAS}
    manifesto = {
        'capturado_em_utc': datetime.now(timezone.utc).isoformat(),
        'tabelas': {nome: {
            'linhas': 0, 'sha256': hashlib.sha256(b'[]').hexdigest(),
        } for nome in linhas},
    }
    cabecalho = json.dumps(manifesto).encode()
    pacote = tmp_path / '123.p7m'
    pacote.write_bytes(b'SDRCOORD1' + len(cabecalho).to_bytes(4, 'big') +
                        cabecalho + b'PGDMP-978')
    cert = tmp_path / 'cert.pem'
    chave = tmp_path / 'chave.pem'
    cert.touch()
    chave.touch()
    chamadas = []

    def executar_falso(argumentos, entrada=None):
        chamadas.append(argumentos)
        if argumentos[0] == 'openssl':
            assert argumentos[argumentos.index('-passin') + 1] == 'stdin'
            Path(argumentos[-1]).write_bytes(pacote.read_bytes())
            return b''
        if argumentos[:2] in (['docker', 'image'], ['docker', 'run']):
            return b''
        if 'pg_restore' in argumentos:
            assert entrada == b'PGDMP-978'
            return b''
        if 'createdb' in argumentos:
            return b''
        sql = argumentos[-1]
        for nome in linhas:
            if f'FROM coordenacao.{nome} t' in sql:
                return (b'' if '-q' in argumentos else b'SET\n') + json.dumps(linhas[nome]).encode()
        raise AssertionError(argumentos)

    monkeypatch.setattr(restaurador, 'comando', executar_falso)
    monkeypatch.setattr(restaurador.shutil, 'which', lambda _: '/usr/bin/tool')
    monkeypatch.setattr(restaurador.subprocess, 'run',
                        lambda *args, **kwargs: subprocess.CompletedProcess(args, 0))
    restaurador.executar(pacote, cert, chave, 'coordenacao_ensaio_978',
                         hashlib.sha256(pacote.read_bytes()).hexdigest())
    resultado = json.loads(capsys.readouterr().out)
    assert resultado['tabelas_conferidas'] == 9
    assert resultado['retomada'].startswith('BLOQUEADA')
    assert any('pg_restore' in chamada for chamada in chamadas)
    with pytest.raises(ValueError, match='Pacote divergiu'):
        restaurador.executar(pacote, cert, chave, 'coordenacao_ensaio_979', '0' * 64)


def test_wrapper_cifra_com_snapshot_vivo_ate_pg_dump(tmp_path, monkeypatch, capsys):
    import ast

    backup = carregar(RAIZ / 'infra' / 'backup-coordenacao.py')
    verificador = carregar(RAIZ / 'ci' / 'backup_coordenacao.py')
    ast.parse(backup.CAPTURA)
    modulo = tmp_path / 'apps' / 'core'
    modulo.mkdir(parents=True)
    (tmp_path / 'apps' / '__init__.py').write_text('')
    (modulo / '__init__.py').write_text('')
    (tmp_path / 'django.py').write_text('def setup(): pass\n')
    (modulo / 'coordenacao.py').write_text(
        'from contextlib import contextmanager\n'
        '@contextmanager\n'
        'def banco():\n'
        '    yield\n'
        '@contextmanager\n'
        'def capturar_snapshot():\n'
        "    yield {'snapshot_id': 'snapshot-978', 'autoridades': [], "
        "'tabelas': {nome: {'linhas': 0, 'sha256': '0'*64} for nome in "
        "('autoridade','tarefa','historico','operacao','evento','outbox',"
        "'candidato','publicador','publicacao')}}\n"
    )
    monkeypatch.setenv('PYTHONPATH', str(tmp_path))
    monkeypatch.setattr(backup, 'RAIZ', tmp_path)
    monkeypatch.setattr(backup, 'DESTINO', tmp_path / 'backups-coordenacao')
    monkeypatch.setattr(backup.select, 'select', lambda readable, *_: (readable, [], []))
    popen_real = subprocess.Popen
    captura = []

    def iniciar(argumentos, **kwargs):
        if argumentos[:4] == ['docker', 'compose', 'exec', '-T']:
            if argumentos[4] == 'admin':
                processo = popen_real([sys.executable, '-c', argumentos[-1]], **kwargs)
                captura.append(processo)
                return processo
            assert argumentos[4] == 'postgres'
            assert '--snapshot' in argumentos
            assert argumentos[argumentos.index('--snapshot') + 1] == 'snapshot-978'
            assert captura[0].poll() is None
            return popen_real([sys.executable, '-c',
                               "import sys;sys.stdout.buffer.write(b'PGDMP-978')"], **kwargs)
        return popen_real(argumentos, **kwargs)

    monkeypatch.setattr(backup.subprocess, 'Popen', iniciar)
    anterior = Path.cwd()
    try:
        backup.executar('978')
    finally:
        os.chdir(anterior)
    resumo = json.loads(capsys.readouterr().out)
    assert captura[0].returncode == 0
    assert resumo['bytes'] > 0
    resumo_path = tmp_path / 'resumo.json'
    resumo_path.write_text(json.dumps(resumo))
    verificador.verificar(resumo_path, backup.DESTINO / '978.p7m')


def test_captura_importa_coordenacao_com_django_real(tmp_path):
    pytest.importorskip('django')
    backup = carregar(RAIZ / 'infra' / 'backup-coordenacao.py')
    codigo = (backup.CAPTURA.split("    fase = 'conexao'", 1)[0]
              + "    print('IMPORTOU')\nexcept Exception:\n    raise\n")
    configuracao = tmp_path / 'config'
    configuracao.mkdir()
    (configuracao / '__init__.py').write_text('')
    (configuracao / 'settings.py').write_text(
        "SECRET_KEY = 'teste'\n"
        "INSTALLED_APPS = []\n"
        "DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}\n"
    )
    ambiente = os.environ.copy()
    ambiente.pop('DJANGO_SETTINGS_MODULE', None)
    ambiente['PYTHONPATH'] = os.pathsep.join((str(tmp_path), str(RAIZ / 'services' / 'admin')))
    resultado = subprocess.run(
        [sys.executable, '-c', codigo], cwd=tmp_path,
        env=ambiente, capture_output=True, text=True, encoding='utf-8', timeout=30,
    )
    assert resultado.returncode == 0, resultado.stderr
    assert resultado.stdout.strip() == 'IMPORTOU'


@pytest.mark.parametrize(
    'fase,acao',
    [
        ('inicializacao', 'inicialização da captura'),
        ('conexao', 'conexão com o banco'),
        ('captura', 'captura do esquema'),
    ],
)
def test_backup_classifica_falha_antes_do_manifesto_sem_vazar_segredo(
    tmp_path, monkeypatch, fase, acao
):
    backup = carregar(RAIZ / 'infra' / 'backup-coordenacao.py')
    segredo = 'SENHA_SINTETICA_NAO_PUBLICAR_1028'
    (tmp_path / 'django.py').write_text(
        "def setup():\n"
        + (
            f"    raise RuntimeError('{segredo}')\n"
            if fase == 'inicializacao'
            else "    pass\n"
        ),
        encoding='utf-8',
    )
    modulo = tmp_path / 'apps' / 'core'
    modulo.mkdir(parents=True)
    (tmp_path / 'apps' / '__init__.py').write_text('', encoding='utf-8')
    (modulo / '__init__.py').write_text('', encoding='utf-8')
    (modulo / 'coordenacao.py').write_text(
        'from contextlib import contextmanager\n'
        '@contextmanager\n'
        'def banco():\n'
        + (
            f"    raise RuntimeError('{segredo}')\n"
            if fase == 'conexao'
            else "    yield\n"
        )
        + '@contextmanager\n'
        + 'def capturar_snapshot():\n'
        + (
            f"    raise RuntimeError('{segredo}')\n"
            if fase == 'captura'
            else "    yield {'snapshot_id':'ok','autoridades':[],'tabelas':{}}\n"
        ),
        encoding='utf-8',
    )
    monkeypatch.setenv('PYTHONPATH', str(tmp_path))
    monkeypatch.setattr(backup, 'RAIZ', tmp_path)
    monkeypatch.setattr(backup, 'DESTINO', tmp_path / 'backups-coordenacao')
    monkeypatch.setattr(backup.select, 'select', lambda readable, *_: (readable, [], []))
    popen_real = subprocess.Popen

    def iniciar(argumentos, **kwargs):
        if argumentos[:5] == ['docker', 'compose', 'exec', '-T', 'admin']:
            return popen_real([sys.executable, '-c', argumentos[-1]], **kwargs)
        pytest.fail('Não pode iniciar pg_dump nem cifra sem manifesto.')

    monkeypatch.setattr(backup.subprocess, 'Popen', iniciar)
    anterior = Path.cwd()
    try:
        with pytest.raises(RuntimeError, match=acao) as falha:
            backup.executar('1028')
    finally:
        os.chdir(anterior)
    assert segredo not in str(falha.value)
    assert not (backup.DESTINO / '1028.p7m').exists()
