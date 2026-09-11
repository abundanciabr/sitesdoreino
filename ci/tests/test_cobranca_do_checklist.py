"""Guardas da cobrança do checklist em sombra (ci/cobranca_do_checklist.py).

Contrato do gancho: exit 0 SEMPRE. Silêncio quase sempre; quando a contagem
bate no teto, uma linha no `hookSpecificOutput.additionalContext`.

Tudo aqui roda o gancho como PROCESSO, com JSON no stdin, nunca chamando as
funções por dentro. É a exigência da `armadilhas/176`: um gancho fail-open que
quebra ao FALAR fica silencioso, e silêncio é o que este gancho produz na maior
parte do tempo. Os dois estados só se distinguem de fora, e só assim se pega a
`armadilhas/003` (emoji e acento num console cp1252).

Cada prova tem o par: um gancho que falasse SEMPRE passaria em todos os testes
de disparo e seria arrancado no primeiro dia de ruído.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

RAIZ_DO_REPO = Path(__file__).resolve().parents[2]
GANCHO = RAIZ_DO_REPO / "ci" / "cobranca_do_checklist.py"
FIACAO = RAIZ_DO_REPO / ".claude" / "settings.json"

sys.path.insert(0, str(RAIZ_DO_REPO / "ci"))
import telemetria  # noqa: E402

TETO = 8  # o mesmo número do gancho; se ele mudar, estes testes têm de mudar junto

ROTEIRO = """Fechei a primeira etapa.

- [x] achar o evento repetido
- [ ] ignorá-lo, com teste
Onde estou: passo 1 de 2. Próximo: escrever o guarda.
"""


# ------------------------------------------------------------- montagem ----


def _fala(texto: str) -> dict:
    return {"type": "assistant",
            "message": {"role": "assistant", "content": [{"type": "text", "text": texto}]}}


def _ferramenta(nome: str, entrada: dict) -> dict:
    return {"type": "assistant",
            "message": {"role": "assistant",
                        "content": [{"type": "tool_use", "name": nome, "input": entrada}]}}


def _editou(quantas: int, comeco: int = 0) -> list[dict]:
    return [_ferramenta("Edit", {"file_path": f"services/loja/a{i}.py"})
            for i in range(comeco, comeco + quantas)]


def _leu(quantas: int) -> list[dict]:
    """Leitura pura: `Read`, `ls`, `cat`. Nada disto muda o mundo."""
    entradas: list[dict] = []
    for i in range(quantas):
        entradas.append(_ferramenta("Read", {"file_path": f"services/loja/a{i}.py"}))
        entradas.append(_ferramenta("Bash", {"command": f"ls ci/tests && cat ci/a{i}.py"}))
    return entradas


def _rodar(carga: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GANCHO)],
        input=json.dumps(carga, ensure_ascii=False),
        capture_output=True, text=True, timeout=60,
        encoding="utf-8", errors="replace",
    )


def _chamar(tmp_path: Path, entradas: list[dict], **extra) -> subprocess.CompletedProcess:
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in entradas),
        encoding="utf-8",
    )
    # `cwd` dentro do tmp de propósito: sem ele, a telemetria destes testes
    # cairia no caderninho DE VERDADE da casa, e a medição em sombra (que é o
    # produto deste gancho) começaria a vida contaminada por disparo de teste.
    carga = {"transcript_path": str(transcript), "tool_name": "Edit",
             "cwd": str(tmp_path), **extra}
    return _rodar(carga)


def _aviso(proc: subprocess.CompletedProcess) -> str:
    """O texto que o gancho entregou ao robô, pelo canal que o harness lê."""
    assert proc.returncode == 0, (proc.returncode, proc.stdout, proc.stderr)
    assert proc.stdout.strip(), "o gancho não falou nada"
    corpo = json.loads(proc.stdout)
    # O aninhamento é obrigatório: `additionalContext` no TOPO do JSON é
    # ignorado EM SILÊNCIO pelo harness, e o gancho pareceria funcionar sem
    # nunca falar com ninguém.
    especifico = corpo["hookSpecificOutput"]
    assert especifico["hookEventName"] == "PostToolUse"
    return especifico["additionalContext"]


def _silencio(proc: subprocess.CompletedProcess) -> None:
    assert proc.returncode == 0, (proc.returncode, proc.stdout, proc.stderr)
    assert proc.stdout.strip() == "", proc.stdout
    assert proc.stderr.strip() == "", proc.stderr


# --------------------------------------------------- (a) o disparo ----


def test_oito_mudancas_sem_caixinha_disparam_a_sombra(tmp_path):
    aviso = _aviso(_chamar(tmp_path, _editou(TETO)))
    assert "sombra: eu teria cobrado o checklist" in aviso
    assert f"{TETO} mudanças" in aviso  # acento vivo: cp1252 não comeu a fala
    assert "Onde estou" in aviso  # a linha ensina o que fazer, não só reclama


def test_a_sombra_nao_impede_nada(tmp_path):
    """Sombra é sobre autoridade: ela fala e deixa passar, sempre exit 0."""
    proc = _chamar(tmp_path, _editou(TETO))
    assert proc.returncode == 0
    assert proc.stderr.strip() == "", proc.stderr


def test_o_disparo_vai_para_o_caderninho(tmp_path):
    """Em sombra, a medição é o efeito que sobrevive à sessão."""
    casa = tmp_path / "casa"
    (casa / ".git").mkdir(parents=True)
    _chamar(tmp_path, _editou(TETO), cwd=str(casa), session_id="sessao-de-teste")
    eventos = [e for e in telemetria.ler_tudo(casa / ".git")
               if e.get("evento") == "checklist_em_sombra"]
    assert len(eventos) == 1, eventos
    assert eventos[0]["mudancas"] == TETO
    assert eventos[0]["modo"] == "sombra"


# --------------------------------------------------- (b) a caixinha zera ----


def test_caixinha_no_meio_zera_a_contagem(tmp_path):
    """As duas metades somam TETO: sem o zeramento, isto cobraria."""
    entradas = _editou(1) + [_fala(ROTEIRO)] + _editou(TETO - 1, comeco=100)
    _silencio(_chamar(tmp_path, entradas))


def test_depois_da_caixinha_a_contagem_recomeca_e_cobra_de_novo(tmp_path):
    entradas = _editou(30) + [_fala(ROTEIRO)] + _editou(TETO, comeco=100)
    assert f"{TETO} mudanças" in _aviso(_chamar(tmp_path, entradas))


def test_caixinha_sem_onde_estou_nao_zera(tmp_path):
    """Plano de abertura colado de novo não diz onde a tarefa está.

    Esta exigência está guardada DUAS vezes no gancho, e é de propósito: a
    peneira de substring (`nde estou`) nem chega a desserializar a fala, e o
    `ONDE_ESTOU` a reprovaria se chegasse. A prova por mutação de 06/09/2026
    precisou sabotar as duas juntas para pintar este teste de vermelho.
    """
    meio_roteiro = "- [x] achar o evento repetido\n- [ ] ignorá-lo"
    entradas = _editou(4) + [_fala(meio_roteiro)] + _editou(4, comeco=100)
    assert _aviso(_chamar(tmp_path, entradas))


def test_onde_estou_sem_caixinha_nao_zera(tmp_path):
    entradas = _editou(4) + [_fala("Onde estou: no meio.")] + _editou(4, comeco=100)
    assert _aviso(_chamar(tmp_path, entradas))


# --------------------------------------------------- (c) o teto ----


def test_sete_mudancas_calam(tmp_path):
    _silencio(_chamar(tmp_path, _editou(TETO - 1)))


def test_nove_mudancas_calam_porque_ja_foi_cobrado_no_oito(tmp_path):
    """Cobrado uma vez, a contagem zera: só volta a falar depois de mais N."""
    _silencio(_chamar(tmp_path, _editou(TETO + 1)))


def test_dezesseis_mudancas_cobram_de_novo(tmp_path):
    assert f"{TETO * 2} mudanças" in _aviso(_chamar(tmp_path, _editou(TETO * 2)))


def test_transcript_sem_mudanca_nenhuma_cala(tmp_path):
    _silencio(_chamar(tmp_path, [_fala("Oi.")]))


# --------------------------------------------------- (d) ler não conta ----


def test_so_leitura_nunca_dispara(tmp_path):
    """A `armadilhas/350` em uma linha: um portão que grita a cada `ls` morre."""
    _silencio(_chamar(tmp_path, _leu(40)))


def test_rascunho_no_scratchpad_nao_conta(tmp_path):
    entradas = [_ferramenta("Write", {"file_path": f"C:/Temp/claude/scratchpad/n{i}.md"})
                for i in range(TETO)]
    _silencio(_chamar(tmp_path, entradas))


def test_sub_agente_nao_conta_pelo_transcript_dele(tmp_path):
    """Sidechain já conta pelo `Agent` do fio principal; contar duas vezes
    adiantaria a cobrança sem ninguém ter mudado nada a mais."""
    entradas = []
    for e in _editou(TETO):
        e = dict(e)
        e["isSidechain"] = True
        entradas.append(e)
    _silencio(_chamar(tmp_path, entradas))


# --------------------------------------------------- (e) fail-open total ----


def test_transcript_ausente_cala(tmp_path):
    _silencio(_rodar({"transcript_path": str(tmp_path / "nao-existe.jsonl")}))


def test_sem_transcript_path_cala():
    _silencio(_rodar({}))


def test_json_quebrado_cala():
    proc = subprocess.run(
        [sys.executable, str(GANCHO)], input="{isto nao e json",
        capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace",
    )
    _silencio(proc)


def test_linha_corrompida_no_meio_nao_derruba_a_contagem(tmp_path):
    transcript = tmp_path / "transcript.jsonl"
    linhas = [json.dumps(e, ensure_ascii=False) for e in _editou(TETO)]
    linhas.insert(3, '{"type":"assistant","message":{"content":[{"type":"tool_use"')
    transcript.write_text("\n".join(linhas), encoding="utf-8")
    assert _aviso(_rodar({"transcript_path": str(transcript), "cwd": str(tmp_path)}))


def test_linha_partida_entre_dois_blocos_de_leitura_continua_inteira(tmp_path):
    """A leitura vem do FIM do arquivo, em blocos: o corte cai no meio de uma
    linha, e sem costurar o pedaço de volta a contagem perderia mudanças."""
    import cobranca_do_checklist as gancho

    transcript = tmp_path / "grande.jsonl"
    recheio = json.dumps({"type": "user", "message": {"role": "user", "content": "z" * 5000}})
    linhas = ([json.dumps(e, ensure_ascii=False) for e in _editou(TETO)]
              + [recheio] * (gancho.BLOCO * 3 // 5000))
    transcript.write_text("\n".join(linhas), encoding="utf-8")
    assert transcript.stat().st_size > gancho.BLOCO * 2, "o teste precisa de mais de dois blocos"

    lidas = list(gancho.linhas_de_tras_para_frente(transcript))
    assert lidas == list(reversed(linhas)), "a leitura de trás para frente perdeu ou cortou linha"
    assert gancho.decidir(gancho.entradas_de_interesse(transcript)) == TETO


# --------------------------------------------------- (f) o custo ----


def test_transcript_de_tres_mil_linhas_custa_menos_de_300ms(tmp_path):
    """Este gancho roda em TODO comando: caro aqui é caro na sessão inteira."""
    transcript = tmp_path / "grande.jsonl"
    recheio = "x" * 900  # linha de transcript real tem ~1,2 KB
    linhas = []
    for i in range(3000):
        if i % 7 == 0:
            linhas.append(json.dumps(_ferramenta("Edit", {"file_path": f"a{i}.py"})))
        else:
            linhas.append(json.dumps({"type": "user", "message": {
                "role": "user", "content": [{"type": "tool_result", "content": recheio}]}}))
    transcript.write_text("\n".join(linhas), encoding="utf-8")

    comeco = time.perf_counter()
    proc = _rodar({"transcript_path": str(transcript), "cwd": str(tmp_path)})
    gasto = time.perf_counter() - comeco
    assert proc.returncode == 0
    # O processo inteiro, com a partida do Python dentro. A medição da decisão
    # sozinha está no docstring do gancho (116 ms no maior transcript da casa).
    assert gasto < 3.0, f"o gancho levou {gasto:.2f}s só para subir e medir"

    comeco = time.perf_counter()
    import cobranca_do_checklist
    cobranca_do_checklist.decidir(cobranca_do_checklist.entradas_de_interesse(transcript))
    medida = time.perf_counter() - comeco
    # Este é o PIOR caso do gancho: 3.000 linhas sem uma caixinha sequer, quer
    # dizer, nada em que parar. A sessão que reimprime o roteiro custa menos.
    assert medida < 0.300, f"a varredura levou {medida * 1000:.0f} ms em 3.000 linhas"


# --------------------------------------------------- a fiação ----


def _comando_da_fiacao() -> str:
    fiacao = json.loads(FIACAO.read_text(encoding="utf-8"))
    for entrada in fiacao.get("hooks", {}).get("PostToolUse", []):
        for gancho in entrada.get("hooks", []):
            if "cobranca_do_checklist" in gancho.get("command", ""):
                assert entrada.get("matcher") == "Edit|Write|NotebookEdit|Bash|PowerShell", (
                    "o matcher precisa cobrir todas as ferramentas que mudam o mundo; "
                    f"veio {entrada.get('matcher')!r}"
                )
                return gancho["command"]
    raise AssertionError("a cobrança do checklist não está ligada no PostToolUse")


def test_o_gancho_esta_ligado_no_posttooluse():
    """Gancho que existe em disco e não está na fiação é decoração."""
    assert _comando_da_fiacao()


def test_clone_sem_o_gancho_nao_atrapalha_a_sessao(tmp_path):
    """`armadilhas/343`: o clone do mantenedor pode estar atrás do repositório.

    A fiação nova tem de conferir o arquivo antes de chamá-lo: sem isso o
    `python` sai com 2, e 2 num gancho é recusa.
    """
    ambiente = {**os.environ, "CLAUDE_PROJECT_DIR": str(tmp_path)}
    proc = subprocess.run(
        _comando_da_fiacao(), shell=True, env=ambiente,
        input=json.dumps({"transcript_path": ""}),
        capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace",
    )
    assert proc.returncode == 0, (proc.returncode, proc.stdout, proc.stderr)


def test_a_fiacao_de_verdade_dispara(tmp_path):
    """O par verde: o mesmo comando literal, contra o repositório real."""
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in _editou(TETO)),
        encoding="utf-8",
    )
    ambiente = {**os.environ, "CLAUDE_PROJECT_DIR": str(RAIZ_DO_REPO)}
    proc = subprocess.run(
        _comando_da_fiacao(), shell=True, env=ambiente,
        input=json.dumps({"transcript_path": str(transcript)}),
        capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace",
    )
    assert proc.returncode == 0, (proc.returncode, proc.stdout, proc.stderr)
    assert "sombra: eu teria cobrado o checklist" in proc.stdout
