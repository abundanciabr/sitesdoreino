"""Leitura fechada da entrega solicitada; nunca devolve mensagens ou logs brutos."""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import time
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

ENTREGA = 'ed31b0c03f97'
ACCESS = Path('/usr/local/lib/meshcraft-acessos')
CACHE = ACCESS / 'leituras-sanitizadas'
PHASE = Path('/entrada/fases') / (ENTREGA + '.json')
SELECTORS = Path('/entrada/selecionadas')
RUNS = Path('/entrada/execucoes')
LEGACY = Path('/entrada/saida')
TESTS = Path('/referencia/provas-funil/tests')
SHA = re.compile(r'[0-9a-f]{40}\Z')
ATTEMPT = re.compile(r'[0-9a-f]{32}\Z')
EXCEPTIONS = {'AssertionError', 'AttributeError', 'CalledProcessError', 'FileNotFoundError',
              'ImportError', 'KeyError', 'ModuleNotFoundError', 'OSError', 'PermissionError',
              'RecusaEnsaio', 'RuntimeError', 'SyntaxError', 'TimeoutExpired', 'TypeError',
              'ValueError', 'MemoryError', 'ParseError', 'pytest.xfail', 'pytest.skip'}
CAUSES = {
    'provas das páginas de entrada falharam; relatório preservado': 'testes_funil_reprovados',
    'prova da célula interrompida': 'executor_interrompido',
    'prova da célula excedeu o prazo': 'prazo_do_executor_excedido',
    'No space left on device': 'espaco_insuficiente',
    'Permission denied': 'permissao_recusada',
    'Cannot connect to the Docker daemon': 'docker_indisponivel',
}


def read_regular(path, root, limit):
    """Recusa links em todos os componentes; limites também valem após abrir."""
    path, root = Path(path), Path(root)
    relative = path.relative_to(root)
    if root.is_symlink():
        raise ValueError('origem_invalida')
    parent = root
    for piece in relative.parts:
        if piece in ('.', '..'):
            raise ValueError('origem_invalida')
        parent = parent / piece
        if parent.is_symlink():
            raise ValueError('origem_invalida')
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise ValueError('arquivo_fora_do_limite')
        data = stream.read(limit + 1)
        if len(data) > limit:
            raise ValueError('arquivo_fora_do_limite')
        return data


def safe_json(path, root):
    value = json.loads(read_regular(path, root, 65536))
    if not isinstance(value, dict):
        raise ValueError('registro_invalido')
    return value


def catalog(tests=TESTS):
    """Só nomes realmente declarados na suíte externa fixada podem sair."""
    names = set()
    for index, source in enumerate(tests.rglob('test_*.py')):
        if index >= 2000:
            raise ValueError('catalogo_excessivo')
        tree = ast.parse(read_regular(source, tests, 262144))
        module = '.'.join(source.relative_to(tests.parent).with_suffix('').parts)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith('test_'):
                names.add((module, node.name))
    return names


def summarize_xml(data, allowed):
    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise ValueError('xml_invalido')
    root = ET.fromstring(data)
    cases = list(root.iter('testcase'))
    if len(cases) > 20000:
        raise ValueError('relatorio_excessivo')
    counts = {'casos': len(cases), 'aprovados': 0, 'falhas': 0, 'erros': 0, 'ignorados': 0}
    problems = []
    for case in cases:
        kind = next((tag for tag in ('failure', 'error', 'skipped') if case.find(tag) is not None), None)
        counts[{None: 'aprovados', 'failure': 'falhas', 'error': 'erros', 'skipped': 'ignorados'}[kind]] += 1
        if kind:
            module = case.get('classname', '')
            name = case.get('name', '').split('[', 1)[0]
            item = {'resultado': {'failure': 'falhou', 'error': 'erro', 'skipped': 'ignorado'}[kind]}
            if (module, name) in allowed:
                item.update(modulo=module, teste=name)
            else:
                item['identificacao'] = 'nome_nao_consta_no_catalogo_fixado'
            exception = case.find(kind).get('type', '').rsplit('.', 1)[-1]
            if exception in EXCEPTIONS:
                item['tipo'] = exception
            problems.append(item)
    return counts | {'problemas': problems[:300], 'lista_limitada': len(problems) > 300,
                     'sha256': hashlib.sha256(data).hexdigest()}


def summarize_log(data):
    text = data.decode('utf-8', 'replace')
    # Não retorna trechos, argumentos, valores de asserções, URLs nem caminhos.
    found = set(re.findall(r'(?m)^([A-Za-z][A-Za-z0-9_]{0,50})(?::|\s*$)', text))
    return {'tipos': sorted(found & EXCEPTIONS),
            'causas_reconhecidas': sorted({code for message, code in CAUSES.items() if message in text}),
            'sha256': hashlib.sha256(data).hexdigest()}


def collect(phase=PHASE, selectors=SELECTORS, runs=RUNS, legacy=LEGACY, tests=TESTS):
    record = safe_json(phase, phase.parent)
    candidate = record.get('candidata')
    if record.get('id') != ENTREGA or not isinstance(candidate, str) or not SHA.fullmatch(candidate):
        raise ValueError('identidade_invalida')
    key = candidate + '-funil'
    selector = selectors / (key + '.json')
    attempt = None
    if selector.exists() or selector.is_symlink():
        attempt = safe_json(selector, selectors).get('tentativa')
        if not isinstance(attempt, str) or not ATTEMPT.fullmatch(attempt):
            raise ValueError('tentativa_invalida')
        base, source_root = runs / key / attempt, runs
    else:
        base, source_root = legacy / key, legacy
    result = {'id': ENTREGA, 'candidata': candidate, 'tentativa': attempt,
              'observado_em': datetime.now(timezone.utc).isoformat(), 'celula': 'funil'}
    result['referencias_sha256'] = {}
    for name in ('test_categorias_na_home.py', 'test_quadrinho_de_progresso.py', 'test_sessao_no_site.py'):
        try:
            result['referencias_sha256'][name] = hashlib.sha256(read_regular(tests / name, tests, 262144)).hexdigest()
        except OSError:
            pass
    for label, relative, limit in [('testes', 'evidencias/funil.xml', 4194304),
                                    ('execucao', 'execucao.log', 2097152)]:
        try:
            data = read_regular(base / relative, source_root, limit)
            result[label] = summarize_xml(data, catalog(tests)) if label == 'testes' else summarize_log(data)
        except FileNotFoundError:
            result[label] = {'estado': 'arquivo_ausente'}
        except (OSError, ValueError, SyntaxError, ET.ParseError):
            result[label] = {'estado': 'leitura_recusada'}
    if safe_json(phase, phase.parent).get('candidata') != candidate:
        raise ValueError('candidata_mudou_durante_leitura')
    if attempt and safe_json(selector, selectors).get('tentativa') != attempt:
        raise ValueError('tentativa_mudou_durante_leitura')
    return result


def atomic(path, data, mode=0o644):
    temporary = path.with_name(path.name + '.novo')
    if path.is_symlink() or temporary.is_symlink():
        raise ValueError('destino_invalido')
    with temporary.open('wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.chmod(mode)
    os.replace(temporary, path)


def atender_leitura(args, cache=CACHE):
    if not args or args[0] != 'diagnostico':
        return None
    if args != ['diagnostico', ENTREGA]:
        print('{"recusado":true,"motivo":"somente_entrega_autorizada"}')
        return 2
    try:
        data = safe_json(cache / (ENTREGA + '.json'), cache)
        if data.get('id') != ENTREGA:
            raise ValueError('identidade_invalida')
        age = time.time() - datetime.fromisoformat(data['observado_em']).timestamp()
        data['leitura_atual'] = 0 <= age <= 120
        print(json.dumps(data, ensure_ascii=True))
        return 0 if data['leitura_atual'] else 3
    except (OSError, ValueError, KeyError, TypeError):
        print('{"indisponivel":true,"motivo":"leitura_ainda_indisponivel"}')
        return 3


def watch():
    while True:
        try:
            data = collect()
        except (OSError, ValueError, TypeError, KeyError) as error:
            data = {'id': ENTREGA, 'estado': 'leitura_indisponivel',
                    'observado_em': datetime.now(timezone.utc).isoformat(),
                    'tipo': type(error).__name__ if type(error).__name__ in EXCEPTIONS else 'erro_de_formato'}
            try:
                info = PHASE.stat()
                data['permissoes_fase'] = {'uid': info.st_uid, 'gid': info.st_gid,
                                          'modo': stat.S_IMODE(info.st_mode)}
            except OSError:
                pass
        atomic(CACHE / (ENTREGA + '.json'), json.dumps(data, ensure_ascii=True).encode())
        time.sleep(30)


if __name__ == '__main__':
    watch()
