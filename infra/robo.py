#!/usr/bin/env python3
"""Entrada comum de Codex e Claude: cópia própria, entrega Git e consulta remota."""
import argparse
import hashlib
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path


class RemotoIndisponivel(RuntimeError):
    """A resposta da operação remota é desconhecida; consultar o mesmo ID."""


class RecusaRemota(ValueError):
    """Recusa explícita do integrador, com causa pública de vocabulário fechado."""

    def __init__(self, codigo='operacao_recusada', id_=None):
        self.codigo = codigo
        self.id = id_
        super().__init__(codigo.replace('_', ' '))


def classificar_recusa(resposta):
    motivo = resposta.get('motivo')
    if not isinstance(motivo, str):
        return RecusaRemota()
    encontrada = re.fullmatch(r'entrega ([0-9a-f]{12}) não existe', motivo)
    if encontrada:
        return RecusaRemota('entrega_inexistente', encontrada.group(1))
    encontrada = re.match(r'o registro ([0-9a-f]{12}) está ilegível\b', motivo)
    if encontrada:
        return RecusaRemota('registro_ilegivel', encontrada.group(1))
    if motivo == 'comando não permitido':
        return RecusaRemota('comando_nao_permitido')
    return RecusaRemota()


def executar(argv, *, cwd=None):
    ssh = argv[0] == 'ssh'
    try:
        r = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, encoding='utf-8',
                           errors='replace', timeout=170 if ssh else None)
    except subprocess.TimeoutExpired:
        if ssh:
            raise RemotoIndisponivel('resposta SSH indisponível; resultado da operação desconhecido') from None
        raise RuntimeError('operação local excedeu o tempo disponível') from None
    if r.returncode:
        if ssh:
            if r.returncode == 255 or not r.stdout.strip():
                raise RemotoIndisponivel('canal SSH indisponível; resultado da operação desconhecido')
            try:
                resposta = json.loads(r.stdout)
            except (ValueError, TypeError):
                raise RemotoIndisponivel('resposta SSH inválida; resultado da operação desconhecido') from None
            if isinstance(resposta, dict) and resposta.get('recusado') is True:
                raise classificar_recusa(resposta)
            raise RemotoIndisponivel('resposta SSH não confirmada; resultado da operação desconhecido')
        raise RuntimeError('operação local recusada')
    if ssh:
        try:
            json.loads(r.stdout)
        except (ValueError, TypeError):
            raise RemotoIndisponivel('resposta SSH inválida; resultado da operação desconhecido') from None
    return r.stdout.strip()


def git(repo, *args):
    return executar(['git', '-C', str(repo), *args])


def remoto(servidor, argumentos):
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._-]*', servidor):
        raise ValueError('alias SSH inválido')
    return executar(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15',
                     '-o', 'ConnectionAttempts=1', servidor, shlex.join(argumentos)])


def entregar(repo, servidor, dependencias=()):
    ramo = git(repo, 'symbolic-ref', '--quiet', '--short', 'HEAD')
    if not re.fullmatch(r'(codex|claude)/entrega/[a-z0-9-]+', ramo):
        raise ValueError('a entrega precisa do ramo próprio criado por nova-tarefa')
    commit = git(repo, 'rev-parse', '--verify', 'HEAD^{commit}')
    base = git(repo, 'config', '--get', f'branch.{ramo}.base-observada')
    if not re.fullmatch(r'[0-9a-f]{40}', base) or not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('commit ou base observada inválidos')
    git(repo, 'merge-base', '--is-ancestor', base, commit)
    for dep in dependencias:
        if not re.fullmatch(r'[0-9a-f]{12}', dep):
            raise ValueError('dependência inválida')
    # Publica exatamente o commit observado: alteração posterior de HEAD não muda este envio.
    git(repo, 'push', '--', 'origin', f'{commit}:refs/heads/{ramo}')
    id_ = hashlib.sha256((ramo + '\n' + commit).encode('utf-8')).hexdigest()[:12]
    comando = ['entregar', '--ramo', ramo, '--commit', commit, '--base', base, '--origem', ramo.split('/')[0]]
    for dep in dependencias:
        comando += ['--depende-de', dep]
    try:
        resposta = remoto(servidor, comando)
        reg = json.loads(resposta)
        if not isinstance(reg, dict) or reg.get('id') != id_:
            raise RemotoIndisponivel('confirmação da entrega não corresponde ao ID esperado')
        return resposta
    except RemotoIndisponivel:
        # O envio pode ter sido persistido antes de a conexão cair. Consultar o
        # ID determinístico evita atribuir uma segunda identidade à entrega.
        try:
            resposta = remoto(servidor, ['consultar', id_])
            reg = json.loads(resposta)
            if (isinstance(reg, dict) and reg.get('id') == id_
                    and reg.get('ramo') == ramo and reg.get('commit') == commit):
                return resposta
        except (RemotoIndisponivel, ValueError, TypeError):
            pass
        raise RemotoIndisponivel(
            f'confirmação indisponível para a entrega {id_}; consulte este ID ou reenvie o mesmo commit') from None


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', type=Path, default=Path.cwd())
    p.add_argument('--servidor', default='sitesdoreino-robo')
    s = p.add_subparsers(dest='comando', required=True)
    n = s.add_parser('nova')
    n.add_argument('robo', choices=['codex', 'claude'])
    n.add_argument('nome')
    n.add_argument('--raiz', type=Path, default=Path.home() / 'abundanciabr')
    e = s.add_parser('entregar')
    e.add_argument('--depende-de', action='append', default=[])
    c = s.add_parser('consultar')
    c.add_argument('id', nargs='?')
    s.add_parser('estado')
    a = p.parse_args(argv)
    try:
        if a.comando == 'nova':
            saida = executar([sys.executable, str(Path(__file__).with_name('nova-tarefa.py')), a.robo, a.nome,
                              '--repo', str(a.repo), '--raiz', str(a.raiz)])
        elif a.comando == 'entregar':
            saida = entregar(a.repo, a.servidor, a.depende_de)
        elif a.comando == 'consultar':
            if a.id and not re.fullmatch(r'[0-9a-f]{12}', a.id):
                raise ValueError('id inválido')
            saida = remoto(a.servidor, ['consultar'] + ([a.id] if a.id else []))
        else:
            saida = remoto(a.servidor, ['estado'])
        print(saida)
        return 0
    except RecusaRemota as ex:
        erro = {'erro': 'operação recusada pelo integrador', 'codigo': ex.codigo}
        if ex.id:
            erro['id'] = ex.id
        print(json.dumps(erro, ensure_ascii=False), file=sys.stderr)
        return 2
    except (RuntimeError, ValueError, OSError) as ex:
        print(json.dumps({'erro': str(ex)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
