"""Consultas compostas: executa somente leituras já permitidas ao usuário robo."""
import json
import os
import re
import shlex
import subprocess
from datetime import datetime, timezone

VERSION = 1
ID = re.compile(r'[0-9a-f]{12}\Z')
COMMANDS = {'ajuda', 'contexto', 'operacoes', 'retomar'}


def catalogo():
    return {
        'versao': VERSION,
        'comandos': {
            'contexto': 'Saúde, últimas entregas e operação atual do analisador; somente leitura.',
            'operacoes [1..50]': 'Últimas entregas resumidas, em ordem de criação; padrão 10.',
            'retomar ID': 'Consulta a entrega existente. Não reenvia, reinicia ou republica.',
            'consultar ID': 'Registro completo da entrega e evidências disponíveis.',
            'estado': 'Histórico completo, potencialmente grande.',
            'entregar --ramo RAMO --commit SHA --base SHA --origem ORIGEM':
                'Canal de entrega existente. Mesmo ramo e commit mantêm o mesmo ID.',
            'servicos listar': 'Serviços e ações disponíveis.',
            'servicos saude [SERVICO]': 'Estado observado agora.',
            'servicos logs SERVICO MINUTOS LINHAS': 'Classes de eventos, sem texto privado.',
            'servicos reiniciar robo|analisador': 'Reinício existente, quando autorizado na tarefa.',
            'analisador consultar': 'Estado e última operação persistente.',
            'analisador diagnosticar|recuperar': 'Operação existente assíncrona; usar somente no escopo autorizado.',
        },
        'execucao': {
            'identidade': 'Mesmo usuário robo, mesmas operações e permissões existentes.',
            'entregas': 'Integração, ensaio e ativação continuam na VPS após o recebimento.',
            'resposta_perdida': 'Consultar ID; não interpretar desconexão como falha da tarefa.',
            'id_entrega': 'Primeiros 12 caracteres do SHA256 de ramo + quebra de linha + commit.',
            'retomada': 'Retomar acompanha. Não repete efeitos nem reabre falhas.',
            'limite': 'Não oferece shell, SQL, arquivos privados, uploads arbitrários ou edição de prévias.',
        },
        'referencias': {
            'site': 'https://meshcraft.top/',
            'codigo': 'https://github.com/abundanciabr/sitesdoreino',
            'console': 'https://hpanel.hostinger.com/vps/1893584/overview',
            'backup': 'O publicador existente preserva código e configurações antes de ativar; banco não é restaurado automaticamente.',
            'restricoes': 'Mantidas as autorizações por tarefa, Mercado Pago congelado e publicação de conteúdo.',
        },
    }


def compacto(reg):
    op = reg.get('operacao') or {}
    result = {k: reg[k] for k in ('id', 'ramo', 'estado', 'commit12', 'candidata12') if k in reg}
    result['operacao'] = {k: op[k] for k in (
        'fase', 'execucao', 'em_andamento', 'atualizada_em', 'progresso_em',
        'proxima_tentativa_em', 'diagnostico', 'operacao_atual',
        'tempos_segundos') if k in op}
    evidence = op.get('evidencia_publicador')
    if isinstance(evidence, dict):
        result['operacao']['evidencia_publicador'] = {k: evidence[k] for k in (
            'estado', 'commit', 'candidata', 'versao', 'backup') if k in evidence}
    result['canal'] = reg.get('canal', {})
    result['consulta'] = 'consultar ' + reg['id']
    return result


def resumir(registros, limite=10):
    if not isinstance(registros, list) or not all(
        isinstance(r, dict) and ID.fullmatch(str(r.get('id', ''))) for r in registros
    ):
        raise ValueError('resposta_invalida')
    # `estado` já ordena por criação. Não promove histórico antigo a execução atual.
    return {'total': len(registros), 'exibidas': min(len(registros), limite),
            'ordem': 'últimas criadas; não é lista de versões ativas',
            'operacoes': [compacto(r) for r in registros[-limite:]]}


def consultar_existente(args, command):
    if not (args in (['estado'], ['servicos', 'saude'], ['analisador', 'consultar'])
            or (len(args) == 2 and args[0] == 'consultar' and ID.fullmatch(args[1]))):
        raise ValueError('consulta_nao_permitida')
    env = dict(os.environ, SSH_ORIGINAL_COMMAND=shlex.join(args))
    p = subprocess.run(['/usr/bin/python3', str(command)], env=env,
                       capture_output=True, text=True, encoding='utf-8',
                       timeout=175, check=False)
    if p.returncode not in (0, 2, 3):
        return 3, {'indisponivel': True, 'motivo': 'consulta_indisponivel'}
    try:
        result = json.loads(p.stdout)
    except ValueError:
        return 3, {'indisponivel': True, 'motivo': 'resposta_invalida'}
    return p.returncode, result


def dispatch(args, query):
    if args == ['ajuda']:
        return 0, catalogo()
    if args == ['contexto']:
        result = {'versao': VERSION, 'observado_em': datetime.now(timezone.utc).isoformat(),
                  'acesso': catalogo()}
        code = 0
        for name, command in [('entregas', ['estado']), ('saude', ['servicos', 'saude']),
                              ('analisador', ['analisador', 'consultar'])]:
            rc, data = query(command)
            result[name] = resumir(data, 5) if name == 'entregas' and rc == 0 else data
            if rc:
                code = 3
        result['completo'] = code == 0
        return code, result
    if args and args[0] == 'operacoes' and (len(args) == 1 or
            (len(args) == 2 and re.fullmatch(r'[0-9]{1,2}', args[1]) and 1 <= int(args[1]) <= 50)):
        rc, data = query(['estado'])
        return (rc, data) if rc else (0, resumir(data, int(args[1]) if len(args) == 2 else 10))
    if len(args) == 2 and args[0] == 'retomar' and ID.fullmatch(args[1]):
        rc, data = query(['consultar', args[1]])
        if rc:
            return rc, data
        if not isinstance(data, dict) or data.get('id') != args[1]:
            raise ValueError('resposta_invalida')
        return 0, {'retomada': 'consulta sem repetir efeitos', 'entrega': compacto(data)}
    return 2, {'recusado': True, 'motivo': 'comando não permitido'}


def atender(args, command):
    if not args or args[0] not in COMMANDS:
        return None
    try:
        rc, data = dispatch(args, lambda cmd: consultar_existente(cmd, command))
    except (OSError, ValueError, TypeError, subprocess.TimeoutExpired):
        rc, data = 3, {'indisponivel': True, 'motivo': 'consulta_indisponivel'}
    print(json.dumps(data, ensure_ascii=True))
    return rc
