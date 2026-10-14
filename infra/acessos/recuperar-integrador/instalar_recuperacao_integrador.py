"""Atualiza a extensão já instalada; não modifica chaves, unidades ou pagamentos."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
SERVICE = Path('/usr/local/lib/meshcraft-servicos/servicos_manutencao.py')
CONTEXT = Path('/usr/local/lib/meshcraft-acessos/operacao_contexto.py')
MODULE = SERVICE.parent / 'recuperacao_integrador.py'
UNIT = 'meshcraft-servicos.service'
BACKUPS = Path('/opt/plataforma/backups-de-codigo')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise RuntimeError('fonte_instalada_divergente')
    return text.replace(old, new)


def service_source(source):
    source = replace_once(source, 'import uuid\n', 'import uuid\nimport recuperacao_integrador\n')
    source = replace_once(source, 'def valid(args):\n',
                          'def valid(args):\n    if recuperacao_integrador.valid(args):\n        return True\n')
    source = replace_once(source, 'def dispatch(args):\n',
                          'def dispatch(args):\n    if recuperacao_integrador.valid(args):\n'
                          '        return recuperacao_integrador.dispatch(args, health, run, Refused, STATE)\n')
    source = replace_once(source, "'reiniciaveis': sorted(RESTART),",
                          "'reiniciaveis': sorted(RESTART), 'recuperaveis': ['integrador'],")
    source = replace_once(source, "'servicos logs SERVICO MINUTOS LINHAS', 'servicos reiniciar SERVICO']",
                          "'servicos logs SERVICO MINUTOS LINHAS', 'servicos reiniciar SERVICO',\n"
                          "                             'servicos recuperar integrador', 'servicos consultar ID']")
    compile(source, str(SERVICE), 'exec')
    return source


def context_source(source):
    marker = "            'servicos reiniciar robo|analisador': 'Reinício existente, quando autorizado na tarefa.',\n"
    source = replace_once(source, marker, marker +
                          "            'servicos recuperar integrador': 'Inicia somente o integrador parado; não interrompe o ativo.',\n"
                          "            'servicos consultar ID': 'Consulta a recuperação registrada sem repetir o início.',\n")
    compile(source, str(CONTEXT), 'exec')
    return source


def run(args, timeout=60):
    return subprocess.run(args, capture_output=True, text=True, check=True, timeout=timeout)


def request(args):
    environment = dict(os.environ, SSH_ORIGINAL_COMMAND=' '.join(args))
    result = subprocess.run(['/usr/sbin/runuser', '-u', 'robo', '--', '/usr/bin/python3',
                             '/usr/local/lib/meshcraft-acessos/robo_comando.py'],
                            capture_output=True, text=True, env=environment, timeout=30)
    return result.returncode, json.loads(result.stdout)


def write(path, data, mode=0o644):
    temporary = path.with_suffix('.recuperacao-candidate')
    temporary.write_bytes(data)
    temporary.chmod(mode)
    os.replace(temporary, path)


def main():
    if not hasattr(os, 'geteuid') or os.geteuid() != 0:
        raise RuntimeError('acesso_administrativo_necessario')
    os.umask(0o077)
    if MODULE.exists():
        raise RuntimeError('extensao_ja_existe_consultar_catalogo')
    original = SERVICE.read_bytes()
    original_context = CONTEXT.read_bytes()
    expected = (HERE / 'servicos_manutencao.py').read_text(encoding='utf-8')
    if SERVICE.read_text(encoding='utf-8') != expected:
        raise RuntimeError('fonte_instalada_divergente')
    updated = service_source(SERVICE.read_text(encoding='utf-8')).encode('utf-8')
    updated_context = context_source(CONTEXT.read_text(encoding='utf-8')).encode('utf-8')
    module = (HERE / 'recuperacao_integrador.py').read_bytes()
    compile(module, str(MODULE), 'exec')
    run(['/usr/bin/python3', '-m', 'unittest', 'test_servicos_manutencao.py',
         'test_recuperacao_integrador.py', 'test_instalar_recuperacao_integrador.py'])
    if sys.argv[1:] != ['--instalar']:
        print(json.dumps({'estado': 'preparado', 'operacao': 'servicos recuperar integrador',
                          'codigo_anterior_sha256': digest(original), 'codigo_novo_sha256': digest(updated)}))
        return
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = BACKUPS / ('ssh-recuperar-integrador-' + stamp)
    backup.mkdir(mode=0o700)
    shutil.copy2(SERVICE, backup / SERVICE.name)
    shutil.copy2(CONTEXT, backup / CONTEXT.name)
    if (backup / SERVICE.name).read_bytes() != original or (backup / CONTEXT.name).read_bytes() != original_context:
        raise RuntimeError('backup_nao_conferido')
    try:
        write(MODULE, module)
        write(SERVICE, updated)
        write(CONTEXT, updated_context)
        # Apenas o pequeno servidor de metadados é reiniciado, nunca o integrador ativo.
        run(['/usr/bin/systemctl', 'restart', UNIT])
        code, catalog = request(['servicos', 'listar'])
        if code or catalog.get('recuperaveis') != ['integrador']:
            raise RuntimeError('catalogo_nao_confirmado')
        code, context = request(['contexto'])
        if code or 'servicos recuperar integrador' not in context.get('acesso', {}).get('comandos', {}):
            raise RuntimeError('contexto_nao_confirmado')
        for args in (['servicos', 'recuperar', 'postgres'], ['servicos', 'reiniciar', 'integrador'],
                     ['servicos', 'consultar', '../etc/shadow']):
            code, result = request(args)
            if code != 2 or not result.get('recusado'):
                raise RuntimeError('limites_nao_preservados')
        evidence = {'estado': 'instalado', 'backup': str(backup), 'catalogo_comprovado': True,
                    'limites_preservados': True, 'recuperacao_ainda_nao_executada': True,
                    'observado_em': datetime.now(timezone.utc).isoformat()}
        (backup / 'resultado.json').write_text(json.dumps(evidence), encoding='utf-8')
        print(json.dumps(evidence))
    except Exception:
        shutil.copy2(backup / SERVICE.name, SERVICE)
        shutil.copy2(backup / CONTEXT.name, CONTEXT)
        run(['/usr/bin/systemctl', 'restart', UNIT])
        # O módulo novo não é apagado; o código anterior não o importa.
        print(json.dumps({'estado': 'codigo_anterior_restaurado', 'backup': str(backup)}))
        raise


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(json.dumps({'estado': 'nao_instalado', 'erro': type(exc).__name__}))
        sys.exit(1)
