#!/usr/bin/env python3
"""Entrada comum de Codex e Claude: cópia própria, entrega Git e consulta remota."""
import argparse
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path


def executar(argv, *, cwd=None):
    r = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode:
        raise RuntimeError((r.stderr or r.stdout).strip() or 'operação recusada')
    return r.stdout.strip()


def git(repo, *args):
    return executar(['git', '-C', str(repo), *args])


def remoto(servidor, argumentos):
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._-]*', servidor):
        raise ValueError('alias SSH inválido')
    return executar(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15', servidor, shlex.join(argumentos)])


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
    comando = ['entregar', '--ramo', ramo, '--commit', commit, '--base', base, '--origem', ramo.split('/')[0]]
    for dep in dependencias:
        comando += ['--depende-de', dep]
    return remoto(servidor, comando)


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
    except (RuntimeError, ValueError, OSError) as ex:
        print(json.dumps({'erro': str(ex)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
