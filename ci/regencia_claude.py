"""Instala e aplica a guarda local da regência, mesmo com o espelho antigo."""
from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import sqlite3
import sys
from contextlib import closing
from datetime import date
from pathlib import Path

TETO_CONSUMO = 1_600_000
LEITURA = {'Read', 'Grep', 'Glob', 'WebSearch', 'WebFetch'}
CONVERSA = {'AskUserQuestion', 'TodoWrite', 'TaskCreate', 'TaskUpdate', 'TaskList', 'TaskGet', 'TaskStop', 'EnterPlanMode'}
ENCAMINHAR = (
    'RECUSADO: Claude rege; Codex executa. Escreva o brief em docs/despachos/ '
    'numa bancada e encaminhe por python ci/fila.py criar --despacho-arquivo <brief>. '
    'Agent aceita somente revisor ou Explore; construção e Workflow continuam recusados.'
)


def repositorio(caminho: Path) -> tuple[Path, Path] | None:
    caminho = caminho.resolve()
    for pasta in (caminho, *caminho.parents):
        git = pasta / '.git'
        if git.is_dir():
            return pasta, git.resolve()
        if git.is_file():
            texto = git.read_text(encoding='utf-8').strip()
            if not texto.startswith('gitdir: '):
                raise ValueError('arquivo .git ilegível')
            gitdir = (pasta / texto[8:]).resolve()
            comum = gitdir / 'commondir'
            destino = (gitdir / comum.read_text().strip()).resolve() if comum.exists() else gitdir.parents[1]
            return pasta, destino
    return None


def consumo(caminho: Path, sessao: str, estado: Path) -> int:
    respostas: dict[str, int] = {}
    with caminho.open(encoding='utf-8-sig') as arquivo:
        for linha in arquivo:
            if not linha.strip():
                continue
            item = json.loads(linha)
            if not isinstance(item, dict):
                raise ValueError('entrada do consumo não é objeto')
            if item.get('type') != 'assistant':
                continue
            if item.get('sessionId') != sessao:
                raise ValueError('consumo pertence a outra sessão')
            mensagem = item['message']
            uso = mensagem['usage']
            valores = [uso[chave] for chave in (
                'input_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens', 'output_tokens')]
            if any(type(valor) is not int or valor < 0 for valor in valores):
                raise ValueError('contador de tokens inválido')
            ident = mensagem['id']
            if not isinstance(ident, str) or not ident:
                raise ValueError('resposta sem identidade')
            respostas[ident] = max(respostas.get(ident, 0), sum(valores))
    estado.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(estado, timeout=5)) as banco, banco:
        banco.execute('BEGIN IMMEDIATE')
        hoje = date.today().isoformat()
        banco.execute('CREATE TABLE IF NOT EXISTS consumo (sessao TEXT, resposta TEXT, tokens INTEGER, PRIMARY KEY (sessao, resposta))')
        if 'dia' not in {coluna[1] for coluna in banco.execute('PRAGMA table_info(consumo)')}:
            banco.execute('ALTER TABLE consumo ADD COLUMN dia TEXT')
            banco.execute('ALTER TABLE consumo ADD COLUMN tokens_dia INTEGER')
            # O legado não tem data: preservar o débito no dia da migração evita zerar o teto.
            banco.execute('UPDATE consumo SET dia = ?, tokens_dia = tokens', (hoje,))
        banco.executemany(
            'INSERT INTO consumo (sessao, resposta, tokens, dia, tokens_dia) VALUES (?, ?, ?, ?, ?) '
            'ON CONFLICT(sessao, resposta) DO UPDATE SET '
            'tokens_dia = CASE WHEN consumo.dia = excluded.dia THEN consumo.tokens_dia ELSE 0 END '
            '+ excluded.tokens - consumo.tokens, dia = excluded.dia, tokens = excluded.tokens '
            'WHERE excluded.tokens > consumo.tokens',
            [(sessao, ident, tokens, hoje, tokens) for ident, tokens in respostas.items()],
        )
        return banco.execute('SELECT COALESCE(SUM(tokens_dia), 0) FROM consumo WHERE dia = ?', (hoje,)).fetchone()[0]


def pode_escrever(caminho: Path, projeto: Path, casa: Path) -> bool:
    caminho = caminho.resolve()
    if caminho.suffix != '.md':
        return False
    if caminho.is_relative_to((casa / '.claude/plans').resolve()):
        return True
    repo = repositorio(caminho.parent)
    return bool(repo and repo[1] == projeto / '.git' and (
        caminho == repo[0] / 'mapa-ia/planos/ROADMAP-SESSAO.md'
        or (repo[0] != projeto and caminho.is_relative_to(repo[0] / 'docs/despachos'))))


def comando_de_regencia(comando: str, cwd: Path, projeto: Path, casa: Path) -> bool:
    if not isinstance(comando, str) or re.search(r'[;&|<>`$\n\r\x00]', comando):
        return False
    args = shlex.split(comando)
    if not args:
        return False
    if any(arg in {'--raiz', '--directory', '-C'} or arg.startswith('--raiz=') for arg in args):
        return False
    if args == ['python', 'ci/resumo_maestro.py']:
        return True
    opcoes = {
        'ci/economia_da_fabrica.py': {'--tipo', '--objetivo', '--celula', '--alvo', '--armadilha', '--saida', '--texto'},
        'ci/fila.py': {'--json', '--ao-vivo', '--titulo', '--toca', '--depende-de', '--tipo',
                       '--evidencia-exigida', '--responsabilidade', '--despacho', '--despacho-arquivo', '--origem',
                       '--move', '--cria', '--o-que-e', '--o-que-muda', '--exemplo', '--importancia'},
        'ci/sessao.py': {'--celula', '--tarefa', '--sem-container'},
    }
    if args[0] == 'python' and len(args) > 1 and args[1] in opcoes:
        if any(arg.startswith('-') and arg.split('=', 1)[0] not in opcoes[args[1]] for arg in args[2:]):
            return False
    if args[:3] == ['python', 'ci/economia_da_fabrica.py', 'brief']:
        for i, arg in enumerate(args):
            if arg == '--saida':
                if i + 1 == len(args) or not pode_escrever(cwd / args[i + 1], projeto, casa):
                    return False
            elif arg.startswith('--saida=') and not pode_escrever(cwd / arg.split('=', 1)[1], projeto, casa):
                return False
        return True
    if args[:2] == ['python', 'ci/fila.py']:
        return len(args) > 2 and args[2] in {'listar', 'criar', 'validar'}
    if args[:2] == ['python', 'ci/mergear.py']:
        return len(args) == 4 and args[2].isdigit() and args[3] in {'--pousar', '--conferir'}
    if args[:2] == ['python', 'ci/economia_da_fabrica.py']:
        return len(args) > 2 and args[2] == 'rotear'
    if args[:2] == ['python', 'ci/sessao.py']:
        return '--sem-container' in args and '--contexto' not in args
    if args[:3] == ['gh', 'pr', 'comment']:
        return (len(args) == 6 and args[3].isdigit() and args[4] == '--body-file'
                and pode_escrever(cwd / args[5], projeto, casa))
    if args[:2] in (['gh', 'pr'], ['gh', 'run']):
        return (len(args) > 2 and args[2] in {'view', 'list', 'diff'}
                and all(re.fullmatch(r'[\w./,:=\-]+', arg) for arg in args)
                and '--web' not in args)
    return args in (['git', 'status', '--short'], ['git', 'fetch', 'origin'])


def decidir(dados: dict, projeto: Path, casa: Path) -> tuple[int, str]:
    try:
        cwd = Path(dados['cwd']).resolve()
        repo = repositorio(cwd)
        origem = os.environ.get('CLAUDE_PROJECT_DIR')
        repo_origem = repositorio(Path(origem)) if origem else None
        alvo = projeto.resolve() / '.git'
        if not any(item and item[1] == alvo for item in (repo, repo_origem)):
            return 0, ''
        sessao = dados['session_id']
        if not isinstance(sessao, str) or not sessao:
            raise ValueError('sessão sem identidade')
        total = consumo(Path(dados['transcript_path']), sessao,
                        casa / '.claude/hooks/sitesdoreino-regencia/consumo.sqlite3')
        if total >= TETO_CONSUMO:
            limite = (f'PAROU: consumo do dia de {total} tokens atingiu o teto diário '
                      f'de {TETO_CONSUMO}, incluindo cache. Encaminhe o trabalho ao Codex; '
                      'o orçamento renova no próximo dia local; outra sessão usa o mesmo teto.')
            return 3, limite
        nome, entrada = dados['tool_name'], dados['tool_input']
        if not isinstance(entrada, dict):
            raise ValueError('entrada da ferramenta inválida')
        if nome in LEITURA | CONVERSA:
            return 0, ''
        if nome == 'Agent' and entrada.get('subagent_type') in ('revisor', 'Explore'):
            return 0, ''
        if nome in {'Write', 'Edit'}:
            if pode_escrever(cwd / entrada['file_path'], projeto, casa):
                return 0, ''
        if nome in {'Bash', 'PowerShell'} and repo and repo[1] == alvo:
            if not entrada.get('run_in_background') and comando_de_regencia(entrada['command'], cwd, projeto, casa):
                return 0, ''
        return 2, ENCAMINHAR
    except (OSError, ValueError, KeyError, TypeError, AttributeError, sqlite3.Error) as erro:
        return 3, (f'PAROU: não foi possível conferir a regência ({erro}). '
                   'Codex deve corrigir o instrumento antes de retomar; ausência de medição não libera consumo.')


def instalar(projeto: Path, casa: Path) -> Path:
    pasta = casa / '.claude'
    settings = pasta / 'settings.json'
    original = settings.read_text(encoding='utf-8-sig') if settings.exists() else '{}'
    config = json.loads(original)
    destino = pasta / 'hooks/sitesdoreino-regencia'
    script = destino / 'regencia_claude.py'
    comando = f'"{sys.executable}" "{script}"'
    hook = {'matcher': '.*', 'hooks': [{'type': 'command', 'command': comando, 'timeout': 20}]}
    hooks = config.setdefault('hooks', {}).setdefault('PreToolUse', [])
    hooks[:] = [item for item in hooks if not any(
        'sitesdoreino-regencia' in parte.get('command', '') for parte in item.get('hooks', []))]
    hooks.append(hook)
    destino.mkdir(parents=True, exist_ok=True)
    backup = pasta / 'settings.antes-regencia.json'
    if not backup.exists():
        backup.write_text(original, encoding='utf-8')
    shutil.copyfile(__file__, script)
    script.with_suffix('.json').write_text(json.dumps({'projeto': str(projeto.resolve())}), encoding='utf-8')
    temporario = settings.with_suffix('.regencia.tmp')
    temporario.write_text(json.dumps(config, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    if settings.exists() and settings.read_text(encoding='utf-8-sig') != original:
        raise ValueError('settings.json mudou durante a instalação; repita para preservar a alteração')
    temporario.replace(settings)
    return script


def main() -> int:
    for fluxo in (sys.stdout, sys.stderr):
        fluxo.reconfigure(encoding='utf-8')
    try:
        if sys.argv[1:] == ['instalar']:
            repo = repositorio(Path(__file__).resolve().parent)
            if not repo:
                raise ValueError('instale a partir da bancada do projeto')
            script = instalar(repo[1].parent, Path.home())
            print(f'INSTALADO: {script}')
            print('Configuração anterior preservada. Sessão já aberta requer recarregar os hooks no Claude.')
            return 0
        config = json.loads(Path(__file__).with_suffix('.json').read_text(encoding='utf-8'))
        dados = json.loads(sys.stdin.buffer.read().decode('utf-8-sig'))
        codigo, motivo = decidir(dados, Path(config['projeto']), Path(__file__).resolve().parents[3])
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as erro:
        codigo, motivo = 3, f'PAROU: guarda da regência indisponível ({erro}). Peça ao Codex para reinstalar a guarda.'
    if codigo == 3:
        print(json.dumps({'continue': False, 'stopReason': motivo}, ensure_ascii=False))
        return 0
    if codigo:
        print(motivo, file=sys.stderr)
    return codigo


if __name__ == '__main__':
    raise SystemExit(main())
