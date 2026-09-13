import json
import subprocess
import sys
from pathlib import Path

import pytest

from regencia_claude import consumo, decidir, instalar


@pytest.fixture
def ambiente(tmp_path):
    projeto = tmp_path / 'projeto'
    projeto.mkdir()
    (projeto / '.git').mkdir()
    bancada = tmp_path / 'bancada'
    bancada.mkdir()
    (bancada / '.git').write_text(f'gitdir: {projeto}/.git/worktrees/bancada')
    casa = tmp_path / 'casa'
    transcript = tmp_path / 'sessao.jsonl'
    transcript.write_text('')
    dados = dict(cwd=str(bancada), session_id='s1', transcript_path=str(transcript),
                 hook_event_name='PreToolUse', tool_use_id='t1', tool_name='Read', tool_input={})
    return projeto, casa, dados


@pytest.mark.parametrize('nome', ['Agent', 'Task', 'Workflow', 'NotebookEdit', 'mcp__shell__exec'])
def test_execucao_e_agentes_sao_recusados(ambiente, nome):
    projeto, casa, dados = ambiente
    dados.update(tool_name=nome, tool_input={'subagent_type': 'Explore'})
    codigo, motivo = decidir(dados, projeto, casa)
    assert codigo == 2
    assert 'Codex' in motivo


@pytest.mark.parametrize('comando', [
    'python -c "print(1)"', 'claude -p executar', 'powershell -EncodedCommand AAA',
    'git status; python tarefa.py', 'python ci/fila.py listar > services/a.py',
    'python ci/fila.py listar $(calc)', 'python ci/fila.py listar `calc`',
    'python ci/fila.py criar --raiz ../outro', 'python ci/economia_da_fabrica.py brief --saida ci/a.py',
    'python ci/pr.py --titulo teste', 'git -c alias.x=!calc x', 'npm test',
    'python ci/economia_da_fabrica.py brief --sa ci/a.py',
    'python ci/fila.py criar --ra ../outro',
])
def test_shell_nao_vira_executor(ambiente, comando):
    projeto, casa, dados = ambiente
    dados.update(tool_name='Bash', tool_input={'command': comando})
    assert decidir(dados, projeto, casa)[0] == 2


@pytest.mark.parametrize('comando', [
    'python ci/fila.py listar --json',
    'python ci/fila.py criar --titulo "Planejar admin" --toca ci --move manutencao '
    '--responsabilidade continuidade-operacional --evidencia-exigida "Plano validado" '
    '--o-que-e "Pedido de plano" --o-que-muda "Delegar ao Codex" --exemplo "Plano do admin" '
    '--importancia 95 --despacho-arquivo docs/despachos/admin.md',
    'python ci/economia_da_fabrica.py brief --tipo arquitetura --objetivo plano --alvo services/admin',
    'python ci/mergear.py 1606 --pousar', 'gh pr view 1606 --json state,headRefOid',
    'gh pr comment 1606 --body-file docs/despachos/atestado-1606.md',
])
def test_regencia_pode_encaminhar_e_conferir(ambiente, comando):
    projeto, casa, dados = ambiente
    dados.update(tool_name='Bash', tool_input={'command': comando})
    assert decidir(dados, projeto, casa) == (0, '')
    if comando.startswith('python ci/fila.py'):
        import shlex
        from fila import construir_parser
        construir_parser().parse_args(shlex.split(comando)[2:])


@pytest.mark.parametrize('alvo', ['services/admin/a.py', '.claude/settings.json', '../projeto/CLAUDE.md'])
def test_escrita_fora_do_brief_e_recusada(ambiente, alvo):
    projeto, casa, dados = ambiente
    dados.update(tool_name='Write', tool_input={'file_path': str(Path(dados['cwd']) / alvo)})
    assert decidir(dados, projeto, casa)[0] == 2


def test_brief_na_bancada_e_permitido_mas_no_espelho_nao(ambiente):
    projeto, casa, dados = ambiente
    dados.update(tool_name='Write', tool_input={'file_path': str(Path(dados['cwd']) / 'docs/despachos/plano.md')})
    assert decidir(dados, projeto, casa) == (0, '')
    dados['tool_input']['file_path'] = str(projeto / 'docs/despachos/plano.md')
    assert decidir(dados, projeto, casa)[0] == 2


def mensagem(tokens, ident='m1'):
    return {'type': 'assistant', 'sessionId': 's1', 'message': {'id': ident, 'usage': {
        'input_tokens': 10, 'cache_creation_input_tokens': 20,
        'cache_read_input_tokens': tokens, 'output_tokens': 30}}}


def test_consumo_conta_cache_sem_duplicar_blocos_da_mesma_resposta(tmp_path):
    arquivo = tmp_path / 'sessao.jsonl'
    arquivo.write_text('\n'.join(json.dumps(x) for x in [mensagem(100), mensagem(150), mensagem(100, 'm2')]))
    assert consumo(arquivo, 's1', tmp_path / 'consumo.sqlite3') == 370


def test_compactacao_nao_renova_orcamento(tmp_path):
    arquivo, estado = tmp_path / 'sessao.jsonl', tmp_path / 'consumo.sqlite3'
    arquivo.write_text(json.dumps(mensagem(100)))
    assert consumo(arquivo, 's1', estado) == 160
    arquivo.write_text(json.dumps(mensagem(200, 'm2')))
    assert consumo(arquivo, 's1', estado) == 420


def test_teto_para_a_sessao_antes_da_proxima_ferramenta(ambiente):
    # guarda: ci/regencia_claude.py:148
    projeto, casa, dados = ambiente
    Path(dados['transcript_path']).write_text(json.dumps(mensagem(180_000)))
    codigo, motivo = decidir(dados, projeto, casa)
    assert codigo == 3
    assert '180060' in motivo


@pytest.mark.parametrize('conteudo', ['{', '[]', json.dumps({'type': 'assistant', 'message': {}})])
def test_medicao_quebrada_nao_libera(ambiente, conteudo):
    projeto, casa, dados = ambiente
    Path(dados['transcript_path']).write_text(conteudo)
    assert decidir(dados, projeto, casa)[0] == 3


def test_transcript_ausente_nao_libera(ambiente):
    projeto, casa, dados = ambiente
    Path(dados['transcript_path']).unlink()
    assert decidir(dados, projeto, casa)[0] == 3


def test_outro_projeto_nao_e_restringido(ambiente, tmp_path):
    projeto, casa, dados = ambiente
    dados.update(cwd=str(tmp_path), tool_name='Agent')
    assert decidir(dados, projeto, casa) == (0, '')


def test_instalacao_preserva_configuracao_e_nao_duplica_hook(ambiente):
    projeto, casa, _ = ambiente
    pasta = casa / '.claude'
    pasta.mkdir(parents=True)
    settings = pasta / 'settings.json'
    original = {'permissions': {'defaultMode': 'auto'}, 'hooks': {'Stop': [{'hooks': []}]}}
    settings.write_text(json.dumps(original))
    instalar(projeto, casa)
    instalar(projeto, casa)
    atual = json.loads(settings.read_text())
    assert atual['permissions'] == original['permissions']
    assert atual['hooks']['Stop'] == original['hooks']['Stop']
    assert len(atual['hooks']['PreToolUse']) == 1
    assert (pasta / 'settings.antes-regencia.json').read_text() == json.dumps(original)


def test_hook_instalado_recusa_workflow_e_para_ao_atingir_teto(ambiente):
    # guarda: ci/regencia_claude.py:215
    projeto, casa, dados = ambiente
    instalar(projeto, casa)
    script = casa / '.claude/hooks/sitesdoreino-regencia/regencia_claude.py'
    dados.update(tool_name='Workflow')
    recusa = subprocess.run([sys.executable, str(script)], input=json.dumps(dados),
                            capture_output=True, text=True, encoding='utf-8')
    assert recusa.returncode == 2
    Path(dados['transcript_path']).write_text(json.dumps(mensagem(180_000)))
    parada = subprocess.run([sys.executable, str(script)], input=json.dumps(dados),
                            capture_output=True, text=True, encoding='utf-8')
    assert parada.returncode == 0
    assert json.loads(parada.stdout)['continue'] is False
