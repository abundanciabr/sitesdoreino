import json
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import date
from pathlib import Path

import pytest

import regencia_claude
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


@pytest.mark.parametrize('nome', ['Task', 'Workflow', 'NotebookEdit', 'mcp__shell__exec'])
def test_execucao_e_agentes_sao_recusados(ambiente, nome):
    projeto, casa, dados = ambiente
    dados.update(tool_name=nome, tool_input={'subagent_type': 'Explore'})
    codigo, motivo = decidir(dados, projeto, casa)
    assert codigo == 2
    assert 'Codex' in motivo


@pytest.mark.parametrize('tipo,codigo', [
    ('revisor', 0), ('Explore', 0), ('despacho', 2), ('escrivao', 2),
    ('general-purpose', 2), ('explore', 2), ('', 2), (None, 2),
])
def test_agent_somente_de_leitura(ambiente, tipo, codigo):
    projeto, casa, dados = ambiente
    dados.update(tool_name='Agent', tool_input={'subagent_type': tipo})
    assert decidir(dados, projeto, casa)[0] == codigo


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


@pytest.mark.parametrize('ferramenta', ['Bash', 'PowerShell'])
@pytest.mark.parametrize('sufixo,codigo', [
    ('', 0), (' --saida mapa-ia/planos/ROADMAP-SESSAO.md', 2),
    (' --escrever', 2), (' --output=ci/a.py', 2), (' --json', 2),
    (' > ci/a.py', 2), ('; git commit -am teste', 2),
])
def test_resumo_maestro_somente_sem_argumentos(ambiente, ferramenta, sufixo, codigo):
    projeto, casa, dados = ambiente
    dados.update(tool_name=ferramenta, tool_input={'command': 'python ci/resumo_maestro.py' + sufixo})
    assert decidir(dados, projeto, casa)[0] == codigo


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


@pytest.mark.parametrize('ferramenta', ['Write', 'Edit'])
@pytest.mark.parametrize('principal', [True, False])
@pytest.mark.parametrize('caminho,codigo', [
    ('mapa-ia/planos/ROADMAP-SESSAO.md', 0),
    ('mapa-ia/planos/RETOMADA-DO-MAESTRO.md', 2),
    ('mapa-ia/ROADMAP-SESSAO.md', 2),
    ('mapa-ia/planos/ROADMAP-SESSAO.md.py', 2),
    ('mapa-ia/planos/../RETOMADA-DO-MAESTRO.md', 2),
])
def test_roadmap_e_o_unico_caminho_adicional(ambiente, ferramenta, principal, caminho, codigo):
    projeto, casa, dados = ambiente
    if principal:
        dados['cwd'] = str(projeto)
    dados.update(tool_name=ferramenta, tool_input={'file_path': caminho})
    assert decidir(dados, projeto, casa)[0] == codigo


def mensagem(tokens, ident='m1', sessao='s1'):
    return {'type': 'assistant', 'sessionId': sessao, 'message': {'id': ident, 'usage': {
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


@pytest.fixture
def dia_local(monkeypatch):
    calendario = {'hoje': date(2026, 9, 14)}

    class DataLocal(date):
        @classmethod
        def today(cls):
            return calendario['hoje']

    monkeypatch.setattr(regencia_claude, 'date', DataLocal, raising=False)
    return calendario


def test_teto_diario_soma_sessoes_e_impede_nova_sessao(ambiente, dia_local):
    projeto, casa, dados = ambiente
    transcript = Path(dados['transcript_path'])
    transcript.write_text(json.dumps(mensagem(1_000_000 - 60)))
    assert decidir(dados, projeto, casa) == (0, '')
    dados['session_id'] = 's2'
    transcript.write_text(json.dumps(mensagem(600_001 - 60, sessao='s2')))
    codigo, motivo = decidir(dados, projeto, casa)
    assert codigo == 3
    assert '1600001' in motivo and '1600000' in motivo
    assert 'dia' in motivo and 'Codex' in motivo
    dados.update(session_id='s3', tool_name='Agent', tool_input={'subagent_type': 'revisor'})
    transcript.write_text('')
    assert decidir(dados, projeto, casa)[0] == 3


def test_virada_do_dia_libera_sem_recontar_transcript(ambiente, dia_local):
    projeto, casa, dados = ambiente
    transcript = Path(dados['transcript_path'])
    estado = casa / '.claude/hooks/sitesdoreino-regencia/consumo.sqlite3'
    transcript.write_text(json.dumps(mensagem(1_600_000 - 60)))
    assert decidir(dados, projeto, casa)[0] == 3
    dia_local['hoje'] = date(2026, 9, 15)
    assert decidir(dados, projeto, casa) == (0, '')
    assert consumo(transcript, 's1', estado) == 0
    transcript.write_text(json.dumps(mensagem(1_600_050 - 60)))
    assert consumo(transcript, 's1', estado) == 50
    assert consumo(transcript, 's1', estado) == 50
    transcript.write_text(json.dumps(mensagem(100 - 60, 'm2')))
    assert consumo(transcript, 's1', estado) == 150


def test_migracao_preserva_consumo_legado_no_dia_local(ambiente, dia_local):
    projeto, casa, dados = ambiente
    estado = casa / '.claude/hooks/sitesdoreino-regencia/consumo.sqlite3'
    estado.parent.mkdir(parents=True)
    with closing(sqlite3.connect(estado)) as banco, banco:
        banco.execute('CREATE TABLE consumo (sessao TEXT, resposta TEXT, tokens INTEGER, PRIMARY KEY (sessao, resposta))')
        banco.executemany('INSERT INTO consumo VALUES (?, ?, ?)', [('s1', 'm1', 500_000), ('s2', 'm1', 1_100_001)])
    assert decidir(dados, projeto, casa)[0] == 3
    assert consumo(Path(dados['transcript_path']), 's1', estado) == 1_600_001
    instalar(projeto, casa)
    assert decidir(dados, projeto, casa)[0] == 3
    with closing(sqlite3.connect(estado)) as banco:
        assert banco.execute('SELECT sessao, resposta, tokens FROM consumo ORDER BY sessao').fetchall() == [
            ('s1', 'm1', 500_000), ('s2', 'm1', 1_100_001)]
    dia_local['hoje'] = date(2026, 9, 15)
    assert decidir(dados, projeto, casa) == (0, '')
    Path(dados['transcript_path']).write_text(json.dumps(mensagem(500_100 - 60)))
    assert consumo(Path(dados['transcript_path']), 's1', estado) == 100


def test_sessoes_concorrentes_compartilham_teto_diario(tmp_path, dia_local):
    estado = tmp_path / 'consumo.sqlite3'
    arquivos = []
    for numero in range(4):
        sessao = f's{numero}'
        arquivo = tmp_path / f'{sessao}.jsonl'
        arquivo.write_text(json.dumps(mensagem(400_000 - 60, sessao=sessao)))
        arquivos.append((arquivo, sessao))
    with ThreadPoolExecutor(max_workers=4) as executor:
        futuros = [executor.submit(consumo, arquivo, sessao, estado) for arquivo, sessao in arquivos]
        totais = [futuro.result() for futuro in futuros]
    assert sorted(totais) == [400_000, 800_000, 1_200_000, 1_600_000]


def test_teto_para_a_sessao_antes_da_proxima_ferramenta(ambiente):
    # guarda: ci/regencia_claude.py:162
    projeto, casa, dados = ambiente
    Path(dados['transcript_path']).write_text(json.dumps(mensagem(1_600_000)))
    codigo, motivo = decidir(dados, projeto, casa)
    assert codigo == 3
    assert '1600060' in motivo


@pytest.mark.parametrize('total,codigo', [(800_000, 0), (800_001, 0), (1_599_999, 0), (1_600_000, 3), (1_600_001, 3)])
def test_teto_de_1600_mil_inclui_cache(ambiente, total, codigo):
    projeto, casa, dados = ambiente
    Path(dados['transcript_path']).write_text(json.dumps(mensagem(total - 60)))
    resultado, motivo = decidir(dados, projeto, casa)
    assert resultado == codigo
    if codigo == 3:
        assert '1600000, incluindo cache' in motivo


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
    # guarda: ci/regencia_claude.py:231
    projeto, casa, dados = ambiente
    instalar(projeto, casa)
    script = casa / '.claude/hooks/sitesdoreino-regencia/regencia_claude.py'
    dados.update(tool_name='Workflow')
    recusa = subprocess.run([sys.executable, str(script)], input=json.dumps(dados),
                            capture_output=True, text=True, encoding='utf-8')
    assert recusa.returncode == 2
    Path(dados['transcript_path']).write_text(json.dumps(mensagem(1_600_000)))
    parada = subprocess.run([sys.executable, str(script)], input=json.dumps(dados),
                            capture_output=True, text=True, encoding='utf-8')
    assert parada.returncode == 0
    assert json.loads(parada.stdout)['continue'] is False
