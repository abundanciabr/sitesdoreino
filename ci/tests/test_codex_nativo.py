"""Eventos nativos do Codex: guardas exercitados pela borda pública."""
import json
import sys
from pathlib import Path

import pytest
import muralha_pasta_compartilhada as pasta
import muralha_do_travessao_na_escrita as texto
import economia_da_fabrica as economia

RAIZ = Path(__file__).resolve().parents[2]

@pytest.fixture
def bancada(tmp_path):
    (tmp_path / ".git").write_text("gitdir: outro")
    (tmp_path / "ci").mkdir()
    (tmp_path / "ci/texto-publico-bastidor.txt").write_text("")
    return tmp_path

def evento(raiz, corpo):
    return {"hook_event_name": "PreToolUse", "tool_name": "apply_patch",
            "tool_input": {"command": "*** Begin Patch\n" + corpo + "*** End Patch\n"},
            "cwd": str(raiz), "session_id": "teste-codex"}

@pytest.mark.parametrize("operacao", ["Add", "Update", "Delete"])
def test_principal_recusa_todas_as_operacoes(tmp_path, operacao):
    (tmp_path / ".git").mkdir()
    (tmp_path / "a.txt").write_text("antes\n")
    corpo = f"*** {operacao} File: a.txt\n"
    corpo += {"Add": "+novo\n", "Update": "@@\n-antes\n+novo\n", "Delete": ""}[operacao]
    assert pasta.decidir(evento(tmp_path, corpo))

def test_multipatch_confere_tambem_destino_do_move(bancada, tmp_path):
    principal = bancada / "principal"
    (principal / ".git").mkdir(parents=True)
    (bancada / "a.txt").write_text("antes\n")
    e = evento(bancada, "*** Add File: permitido.txt\n+ok\n*** Update File: a.txt\n*** Move to: principal/a.txt\n@@\n-antes\n+novo\n")
    assert pasta.decidir(e)

@pytest.mark.parametrize("corpo", ["", "lixo\n", "*** Add File: ../fora.txt\n+x\n", "*** Add File: ..\\fora.txt\n+x\n", "*** Add File: a.txt\nsem-prefixo\n", "*** Update File: a.txt\n*** Move to: ../fora.txt\n@@\n-a\n+b\n"])
def test_patch_invalido_ou_traversal_fecha_as_duas_guardas(bancada, corpo):
    e = evento(bancada, corpo)
    assert pasta.decidir(e)
    assert texto.decidir(e) == 2

def test_patch_legitimo_permitido_na_bancada(bancada):
    e = evento(bancada, "*** Add File: services/a/templates/a.html\n+<p>Olá, mundo.</p>\n")
    assert pasta.decidir(e) is None
    assert texto.decidir(e) == 0

def test_travessao_no_segundo_arquivo_recusa_patch_inteiro(bancada):
    e = evento(bancada, "*** Add File: interno.txt\n+ok\n*** Add File: services/a/templates/a.html\n+<p>Olá — mundo.</p>\n")
    assert texto.decidir(e) == 2
    assert not (bancada / "interno.txt").exists()

def test_update_reconstroi_contexto_para_detectar_travessao(bancada):
    destino = bancada / "services/a/templates/a.html"
    destino.parent.mkdir(parents=True)
    destino.write_text("<p>\nOlá, mundo.\n</p>\n", encoding="utf-8")
    e = evento(bancada, "*** Update File: services/a/templates/a.html\n@@\n <p>\n-Olá, mundo.\n+Olá — mundo.\n </p>\n")
    assert texto.decidir(e) == 2
    assert "—" not in destino.read_text(encoding="utf-8")

def test_move_de_privado_para_publico_mede_destino(bancada):
    (bancada / "interno.txt").write_text("Olá — mundo.\n", encoding="utf-8")
    e = evento(bancada, "*** Update File: interno.txt\n*** Move to: services/a/templates/a.html\n@@\n Olá — mundo.\n")
    assert texto.decidir(e) == 2

def test_contexto_ausente_recusa_medicao(bancada):
    (bancada / "a.txt").write_text("diferente\n")
    e = evento(bancada, "*** Update File: a.txt\n@@\n-ausente\n+novo\n")
    assert texto.decidir(e) == 2

def test_modelos_codex_sao_explicitos(monkeypatch, bancada):
    monkeypatch.setenv("CODEX_THREAD_ID", "teste")
    brief = economia.compilar_brief(bancada, objetivo="registrar", tipo="escrita", celula="ci", alvos=["ci/a.py"], armadilhas=[])
    assert "modelo_recomendado: gpt-5.6-sol" in brief
    assert economia.perfil_por_tipo("arquitetura").modelo == "gpt-6-astra"

def test_auditoria_codex_nao_aprova_so_as_fichas_claude(monkeypatch, bancada):
    monkeypatch.setenv("CODEX_THREAD_ID", "teste")
    fichas = bancada / ".claude/agents"
    fichas.mkdir(parents=True)
    (fichas / "revisor.md").write_text("---\nname: revisor\nmodel: sonnet\n---\ntexto")
    with pytest.raises(economia.ErroDeInstrumentacao):
        economia.auditar_fichas(bancada)

def test_transcript_codex_cobra_relatorio_depois_de_filechange(bancada):
    import prestacao_de_contas as contas
    registros = [
        {"type": "response_item", "payload": {"type": "message", "role": "user",
         "content": [{"type": "input_text", "text": "Corrija a página."}]}},
        {"type": "event_msg", "payload": {"type": "item_completed", "item": {
         "type": "FileChange", "id": "f1", "status": "completed",
         "changes": {"a.html": {"type": "add", "content": "texto"}}}}},
    ]
    arquivo = bancada / "transcript.jsonl"
    arquivo.write_text("\n".join(json.dumps(r) for r in registros), encoding="utf-8")
    assert contas.decidir(contas.ler_transcript(arquivo))[0] is True

def test_fichas_nativas_declaradas_e_revisor_sem_escrita(monkeypatch):
    monkeypatch.setenv("CODEX_THREAD_ID", "teste")
    assert economia.auditar_fichas(RAIZ) == []



@pytest.mark.parametrize("entrada", ["{}", "JSON quebrado"])
def test_dispatcher_fecha_entrada_nao_medida(entrada):
    import subprocess
    resultado = subprocess.run([sys.executable, str(RAIZ / "ci/hook_codex.py"), "PreToolUse"],
                               input=entrada, capture_output=True, text=True, encoding="utf-8")
    assert resultado.returncode == 2
    assert "PAROU POR SEGURANÇA" in resultado.stderr

@pytest.mark.parametrize("nome", ["apply_patch", "Edit", "Write", "Bash", "PowerShell"])
@pytest.mark.parametrize("evento_hook", ["PreToolUse", "PostToolUse"])
def test_acao_comum_nao_executa_scripts_nem_le_transcript(monkeypatch, nome, evento_hook):
    # guarda: ci/hook_codex.py:44
    import hook_codex
    def proibido(*args, **kwargs):
        pytest.fail("ação comum disparou processamento de hook")
    monkeypatch.setattr(hook_codex, "executar", proibido)
    assert hook_codex.decidir({"hook_event_name": evento_hook, "tool_name": nome}) == 0


def test_monitor_preserva_guarda_da_espera(monkeypatch):
    # guarda: ci/hook_codex.py:43
    import hook_codex
    chamadas = []
    def executar(script, dados):
        chamadas.append(script)
        return 2
    monkeypatch.setattr(hook_codex, "executar", executar)
    assert hook_codex.decidir({"hook_event_name": "PreToolUse", "tool_name": "Monitor"}) == 2
    assert chamadas == ["muralha_da_espera.py"]


@pytest.mark.parametrize("config", [".codex/hooks.json", ".claude/settings.json"])
def test_config_apenas_monitor_por_acao_e_checkpoints_preservados(config):
    hooks = json.loads((RAIZ / config).read_text(encoding="utf-8"))["hooks"]
    esperado = ["Monitor", "Agent|Workflow"] if config == ".claude/settings.json" else ["Monitor"]
    assert [h["matcher"] for h in hooks["PreToolUse"]] == esperado
    assert hooks["PostToolUse"] == []
    for evento_hook in ["SessionStart", "UserPromptSubmit", "Stop"]:
        assert hooks[evento_hook]


def test_launcher_codex_nativo_preservado():
    hooks = json.loads((RAIZ / ".codex/hooks.json").read_text(encoding="utf-8"))["hooks"]
    for evento_hook in ["SessionStart", "UserPromptSubmit", "Stop", "PreToolUse"]:
        comando = hooks[evento_hook][0]["hooks"][0]
        assert "hook_codex.cmd" in comando["commandWindows"]
        assert "CLAUDE_PROJECT_DIR" not in str(comando)
        assert evento_hook in comando["commandWindows"]


def test_travessao_permanece_no_checkpoint_de_commit():
    gancho = (RAIZ / ".githooks/pre-commit").read_text(encoding="utf-8")
    assert "python ci/travessao.py --verificar-staged || exit 1" in gancho
    assert "python ci/registro_no_commit.py" in gancho


def test_dispatcher_stop_cobra_e_aceita_relatorio(bancada):
    import subprocess
    import prestacao_de_contas as contas
    arquivo = bancada / "transcript.jsonl"
    registros = [
        {"type": "response_item", "payload": {"type": "message", "role": "user",
         "content": [{"type": "input_text", "text": "Corrija."}]}},
        {"type": "response_item", "payload": {"type": "custom_tool_call", "name": "apply_patch",
         "call_id": "c1", "input": "*** Begin Patch"}}]
    def rodar():
        arquivo.write_text("\n".join(json.dumps(r) for r in registros), encoding="utf-8")
        return subprocess.run([sys.executable, str(RAIZ / "ci/hook_codex.py"), "Stop"],
            input=json.dumps({"hook_event_name": "Stop", "transcript_path": str(arquivo), "cwd": str(bancada)}),
            capture_output=True, text=True, encoding="utf-8")
    assert rodar().returncode == 2
    relatorio = "\n".join(titulo + " Alteração conferida com teste real." for titulo, _ in contas.BLOCOS)
    relatorio += "\n- [x] Correção verificada.\n**Veredito:** PRONTO, os testes passaram."
    registros.append({"type": "response_item", "payload": {"type": "message", "role": "assistant",
        "content": [{"type": "output_text", "text": relatorio}]}})
    assert rodar().returncode == 0

@pytest.mark.parametrize("alterar", ["model", "sandbox_mode", "model_reasoning_effort", "name"])
def test_auditoria_nativa_recusa_modelo_herdado_e_revisor_com_escrita(bancada, monkeypatch, alterar):
    import shutil
    monkeypatch.setenv("CODEX_THREAD_ID", "teste")
    shutil.copytree(RAIZ / ".codex/agents", bancada / ".codex/agents")
    p = bancada / ".codex/agents/revisor.toml"
    linhas = p.read_text(encoding="utf-8").splitlines()
    linhas = [linha for linha in linhas if not linha.startswith(alterar + " =")]
    p.write_text("\n".join(linhas), encoding="utf-8")
    assert economia.auditar_fichas(bancada)

def test_add_update_multihunk_e_delete_na_bancada(bancada):
    from patch_codex import ler_patch, texto_proposto
    (bancada / "a.txt").write_text("primeira\nmeio\nultima\n", encoding="utf-8")
    dados = evento(bancada, "*** Update File: a.txt\n@@\n-primeira\n+início\n@@ meio\n-ultima\n+fim\n*** End of File\n*** Delete File: lixo.txt\n")
    alteracoes = ler_patch(dados)
    assert texto_proposto(alteracoes[0]) == "início\nmeio\nfim\n"
    assert texto_proposto(alteracoes[1]) is None

@pytest.mark.parametrize("corpo", [
    "*** Update File: a.txt\n", "*** Delete File: a.txt\n+texto\n",
    "*** Add File: a.txt\n+x\n*** Add File: a.txt\n+y\n",
    "*** Update File: a.txt\n@@\n-x\n+y\n*** End of File\n+lixo\n",
])
def test_gramatica_invalida_fecha_patch(bancada, corpo):
    assert pasta.decidir(evento(bancada, corpo))
    assert texto.decidir(evento(bancada, corpo)) == 2

def test_session_start_emite_um_json_valido(bancada):
    import subprocess
    resultado = subprocess.run([sys.executable, str(RAIZ / "ci/hook_codex.py"), "SessionStart"],
        input=json.dumps({"hook_event_name": "SessionStart", "cwd": str(bancada)}),
        capture_output=True, text=True, encoding="utf-8")
    assert resultado.returncode == 0, resultado.stderr
    contexto = json.loads(resultado.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "fichas nativas conferidas" in contexto
    assert "ainda não mede transcripts Codex" in contexto



def test_dispatcher_preserva_acentos_e_emoji_em_console_cp1252(bancada):
    import os
    import subprocess
    ambiente = dict(os.environ)
    ambiente.pop("PYTHONUTF8", None)
    ambiente["PYTHONIOENCODING"] = "cp1252"
    r = subprocess.run([sys.executable, str(RAIZ / "ci/hook_codex.py"), "UserPromptSubmit"],
        input=json.dumps({"hook_event_name": "UserPromptSubmit", "prompt": "Corrija a página.", "cwd": str(bancada)}),
        env=ambiente, capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stderr
    contexto = json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "📋" in contexto and "não" in contexto
    assert "\ufffd" not in contexto


def test_revisor_confere_mutacoes_do_despacho_sem_ordens_de_escrita():
    import re
    import tomllib
    ficha = tomllib.loads((RAIZ / ".codex/agents/revisor.toml").read_text(encoding="utf-8"))
    instrucoes = ficha["developer_instructions"]
    prova = instrucoes.split("4. **A prova.**", 1)[1].split("5. **Todo estado tratado.**", 1)[0]
    assert "fornecidas pelo despacho" in prova
    assert "mutação" in prova
    assert not re.search(r"\b(sabote|comente|rode|execute|desfaça)\b|git\s+checkout", prova, re.I)
