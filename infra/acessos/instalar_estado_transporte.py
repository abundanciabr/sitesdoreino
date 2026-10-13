"""Atualiza só o transporte do canal existente, com backup e retorno em falha."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
import instalar_servicos as base

ACCESS = base.ACCESS
HISTORY = Path('/var/lib/meshcraft-integrador/entregas')


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise RuntimeError('fonte_atual_divergente')
    return text.replace(old, new)


def candidates():
    command = (ACCESS/'robo_comando.py').read_text()
    command = replace_once(command, 'import sys\n', 'import sys\nfrom estado_transporte import receber\n')
    start = command.index('        resposta = bytearray()')
    end = command.index('\n\n\nif __name__', start)
    command = command[:start] + '        return receber(canal)\n' + command[end:]
    broker = (ACCESS/'robo_broker.py').read_text()
    broker = replace_once(broker, 'import sys\n', 'import sys\nfrom estado_transporte import enviar\n')
    broker = replace_once(broker, '    if len(saida.encode("utf-8")) > 200000:',
                          '    if args[0] != "estado" and len(saida.encode("utf-8")) > 200000:')
    broker = replace_once(broker, '        "saida": saida,\n',
                          '        "saida": saida,\n        "_blocos": args[0] == "estado",\n')
    broker = replace_once(broker, 'conexao.sendall(json.dumps(resposta, ensure_ascii=True).encode())',
                          'enviar(conexao, resposta)')
    for name, text in (('robo_comando.py', command), ('robo_broker.py', broker)):
        compile(text, name, 'exec')
    return {'robo_comando.py': command, 'robo_broker.py': broker,
            'estado_transporte.py': (Path(__file__).parent/'estado_transporte.py').read_text()}


def idle():
    for attempt in range(20):
        fields = [l.split() for l in Path('/proc/net/unix').read_text().splitlines()]
        if not any(len(f) >= 8 and f[5] == '03' and f[7] == '/run/meshcraft-robo.sock' for f in fields):
            return
        time.sleep(1)
    raise RuntimeError('canal_ocupado')


def main():
    if os.geteuid() != 0:
        raise RuntimeError('console_root_necessario')
    os.umask(0o077)
    prepared = candidates()
    base.run(['/usr/bin/python3', '-m', 'unittest', '-v', 'test_estado_transporte.py'])
    base.site()
    anchors = base.anchors()
    ids = {p.stem for p in HISTORY.glob('*.json') if re.fullmatch('[0-9a-f]{12}', p.stem)}
    backup = Path('/opt/plataforma/backups-de-codigo') / ('estado-transporte-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    backup.mkdir(mode=0o700)
    (backup/'referencias.json').write_text(json.dumps(anchors))
    (backup/'ids-antes.json').write_text(json.dumps(sorted(ids)))
    for name in prepared:
        if (ACCESS/name).exists():
            shutil.copy2(ACCESS/name, backup/name)
    try:
        for name, text in prepared.items():
            temporary = ACCESS/(name + '.candidate')
            temporary.write_text(text)
            temporary.chmod(0o755 if name != 'estado_transporte.py' else 0o644)
            os.replace(temporary, ACCESS/name)
        idle()
        base.run(['/usr/bin/systemctl', 'restart', 'meshcraft-robo.service'])
        code, result = base.request(['estado'])
        if code or not isinstance(result, list):
            raise RuntimeError('estado_falhou')
        received = [r['id'] for r in result]
        if len(received) != len(set(received)) or not ids <= set(received):
            raise RuntimeError('historico_incompleto')
        tests = {}
        for name, args in (
            ('consultar', ['consultar', next(iter(ids))]),
            ('analisador', ['analisador', 'consultar']),
            ('servicos', ['servicos', 'listar']),
            ('saude', ['servicos', 'saude', 'aplicacao']),
            ('logs', ['servicos', 'logs', 'aplicacao', '60', '5']),
        ):
            rc, data = base.request(args)
            if rc:
                raise RuntimeError('comando_existente_falhou')
            tests[name] = True
        base.site()
        if base.anchors() != anchors:
            raise RuntimeError('referencias_alteradas')
        evidence = {'estado': 'instalado', 'backup': str(backup), 'registros_antes': len(ids),
                    'registros_recebidos': len(received), 'sem_perda_ou_duplicacao': True,
                    'bytes_json': len(json.dumps(result, ensure_ascii=False).encode()),
                    'comandos_preservados': tests, 'referencias_preservadas': len(anchors),
                    'site_http': 200, 'testes': 7, 'em': datetime.now(timezone.utc).isoformat()}
        (backup/'comprovacao.json').write_text(json.dumps(evidence, indent=2))
        print(json.dumps(evidence))
    except Exception:
        for name in ('robo_comando.py', 'robo_broker.py'):
            shutil.copy2(backup/name, ACCESS/name)
        base.run(['/usr/bin/systemctl', 'restart', 'meshcraft-robo.service'])
        print(json.dumps({'estado': 'canal_anterior_restaurado', 'backup': str(backup)}))
        raise


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        message = str(exc)
        print(json.dumps({'erro': message if re.fullmatch('[a-z_]{1,100}', message) else type(exc).__name__}))
        raise SystemExit(1)
