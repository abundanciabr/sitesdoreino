"""Guardas da muralha das armadilhas (ci/muralha_das_armadilhas.py).

Contrato do hook (o mesmo das duas irmãs): exit 0 = permite; exit 2 = recusa
com o motivo no stderr; erro de instrumento TAMBÉM é exit 2 (fail-closed,
INV-CI01). Recusa que não ENSINA o caminho certo só produz robô travado de
outro jeito, então isso é asserção, não estilo.

O que este arquivo prova, além do de sempre:

- O CORPUS DOURADO (`corpus_armadilhas.jsonl`) — cada caso perigoso e, ao lado,
  os sósias legítimos que NÃO podem ser recusados. Todo falso positivo real que
  aparecer vira linha nova ali e nunca mais volta: é o sistema aprendendo com as
  próprias cicatrizes. A relação é deliberada — mais benignos que perigosos.
- A SOMBRA — uma regra em sombra observa e deixa passar, mas ela precisa GRAVAR;
  sombra que não registra nada não amadurece nunca e a promoção viraria palpite.
- A FIAÇÃO derivada da tabela: o matcher do settings.json tem de cobrir a união
  de `Regra.ferramentas`. Assim, uma regra futura de Write sem a fiação
  correspondente reprova sozinha — muralha sem fiação é decoração
  (RETROSPECTIVA-FASE-D §2).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ_DO_REPO = Path(__file__).resolve().parents[2]
MURALHA = RAIZ_DO_REPO / "ci" / "muralha_das_armadilhas.py"
FIACAO = RAIZ_DO_REPO / ".claude" / "settings.json"
CORPUS = Path(__file__).resolve().parent / "corpus_armadilhas.jsonl"

sys.path.insert(0, str(RAIZ_DO_REPO / "ci"))
import muralha_das_armadilhas as muralha  # noqa: E402
import telemetria  # noqa: E402


def _decidir(tool_name: str, tool_input: dict, **extra) -> subprocess.CompletedProcess:
    corpo = {"tool_name": tool_name, "tool_input": tool_input}
    corpo.update(extra)
    return subprocess.run(
        [sys.executable, str(MURALHA)],
        input=json.dumps(corpo),
        capture_output=True, text=True, timeout=60,
        encoding="utf-8", errors="replace",
    )


def _casos_do_corpus() -> list[dict]:
    linhas = CORPUS.read_text(encoding="utf-8").splitlines()
    return [json.loads(linha) for linha in linhas if linha.strip()]


def _ident(caso: dict) -> str:
    return f"{caso['armadilha']}-{caso['esperado']}-{caso['porque'][:40]}"


# ------------------------------------------------------ o corpus dourado ----


@pytest.mark.parametrize("caso", _casos_do_corpus(), ids=_ident)
def test_corpus_dourado(caso: dict):
    """Cada linha do corpus é um veredito da muralha — perigoso e sósia."""
    achado = muralha.avaliar(
        {"tool_name": caso["ferramenta"], "tool_input": {"command": caso["comando"]}}
    )
    if caso["esperado"] == "detecta":
        assert achado is not None, f"deixou passar: {caso['porque']}"
        assert achado.regra.armadilha == caso["armadilha"]
    else:
        assert achado is None, (
            f"FALSO POSITIVO ({caso['porque']}): "
            f"{achado.motivo if achado else ''}"
        )


# ------------------------------------ a sombra observa, registra e permite ----


def _repo_encenado(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    return tmp_path


def test_sombra_deixa_passar_mas_grava_no_caderninho(tmp_path: Path):
    casa = _repo_encenado(tmp_path)
    proc = _decidir(
        "Bash",
        {"command": 'git commit -m "corrige o `ci/mergear.py`"'},
        cwd=str(casa), session_id="sessao-de-teste",
    )
    assert proc.returncode == 0, "regra em sombra não pode impedir nada"
    eventos = telemetria.ler_tudo(casa / ".git")
    assert len(eventos) == 1, "sombra que não registra nunca amadurece"
    assert eventos[0]["armadilha"] == "136"
    assert eventos[0]["modo"] == "sombra"
    assert eventos[0]["evento"] == "regra_disparou"


def test_um_arquivo_por_sessao(tmp_path: Path):
    """Padrão 7: duas sessões paralelas nunca disputam a mesma linha."""
    casa = _repo_encenado(tmp_path)
    perigoso = {"command": 'git commit -m "toca o `painel/logica.js`"'}
    _decidir("Bash", perigoso, cwd=str(casa), session_id="sessao-A")
    _decidir("Bash", perigoso, cwd=str(casa), session_id="sessao-B")
    arquivos = sorted(p.name for p in (casa / ".git" / "telemetria-dos-robos").glob("*.jsonl"))
    assert arquivos == ["sessao-A.jsonl", "sessao-B.jsonl"]


def test_comando_limpo_nao_gera_evento(tmp_path: Path):
    casa = _repo_encenado(tmp_path)
    proc = _decidir("Bash", {"command": "git status --short"}, cwd=str(casa))
    assert proc.returncode == 0
    assert telemetria.ler_tudo(casa / ".git") == []


def test_segredo_no_comando_medido_e_redigido(tmp_path: Path):
    """Medir não pode virar vazamento: o detector da 090 vira redator."""
    casa = _repo_encenado(tmp_path)
    segredo = "ghp_" + "A" * 36
    _decidir(
        "Bash",
        {"command": f'git commit -m "usa a `chave {segredo}` aqui"'},
        cwd=str(casa), session_id="s",
    )
    eventos = telemetria.ler_tudo(casa / ".git")
    assert eventos, "o evento deveria ter sido gravado"
    assert segredo not in json.dumps(eventos, ensure_ascii=False)
    assert "<REDIGIDO>" in eventos[0]["comando"]


def test_telemetria_impossivel_nao_derruba_a_muralha(tmp_path: Path):
    """Fail-open do caderninho: sem .git não há onde gravar, e tudo bem."""
    proc = _decidir(
        "Bash",
        {"command": 'git commit -m "toca o `ci/x.py`"'},
        cwd=str(tmp_path), session_id="s",
    )
    assert proc.returncode == 0, proc.stderr


# --------------------------------------------- o caminho do bloqueio real ----


def test_bloqueio_recusa_e_ensina(monkeypatch):
    """A regra promovida recusa com ponteiro e alternativa executável.

    A R136 nasce em sombra; este teste encena a promoção para provar que o
    caminho de bloqueio funciona ANTES de alguém depender dele.
    """
    promovida = tuple(
        muralha.Regra(
            armadilha=r.armadilha, detector_nome=r.detector_nome,
            ferramentas=r.ferramentas, detectar=r.detectar,
            confianca=r.confianca, autoridade="bloqueia",
            caminho_certo=r.caminho_certo,
        )
        for r in muralha.REGRAS
    )
    monkeypatch.setattr(muralha, "REGRAS", promovida)
    # Sem isto, o teste grava um disparo "em bloqueia" no caderninho da CASA —
    # e é do caderninho que sai a decisão de promover a regra de sombra para
    # bloqueio. Medição envenenada pelo próprio teste é pior que medição
    # nenhuma: ela faria a promoção parecer justificada por disparos que nunca
    # existiram fora da suíte.
    monkeypatch.setattr(muralha.telemetria, "registrar", lambda *a, **k: None)
    monkeypatch.setattr(
        sys, "stdin",
        type("F", (), {"buffer": type("B", (), {"read": staticmethod(
            lambda: json.dumps({
                "tool_name": "Bash",
                "tool_input": {"command": 'git commit -m "toca o `ci/x.py`"'},
            }).encode("utf-8"))})()})(),
    )
    saida = []
    monkeypatch.setattr(muralha, "_recusar", lambda m, c, a="": saida.append((m, c, a)) or 2)
    assert muralha.main() == 2
    motivo, caminho, armadilha = saida[0]
    assert armadilha == "136"
    assert "commit -F" in caminho, "recusa sem ensinar o caminho certo"


def test_formato_da_recusa_ensina(capsys):
    muralha._recusar("um motivo", "faça assim", "136")
    erro = capsys.readouterr().err
    assert "MURALHA DAS ARMADILHAS" in erro
    assert "armadilhas/136" in erro
    assert "falso positivo" in erro, "toda recusa oferece a saída de reporte"


# ----------------------------------------------- contrato do hook e bordas ----


def test_json_quebrado_recusa_fail_closed():
    proc = subprocess.run(
        [sys.executable, str(MURALHA)], input="isto não é json",
        capture_output=True, text=True, timeout=60,
        encoding="utf-8", errors="replace",
    )
    assert proc.returncode == 2
    assert "INV-CI01" in proc.stderr


def test_bom_utf8_no_stdin_nao_vira_recusa():
    """armadilhas/138: o PowerShell 5.1 injeta BOM ao canalizar."""
    corpo = json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls"}})
    proc = subprocess.run(
        [sys.executable, str(MURALHA)],
        input=b"\xef\xbb\xbf" + corpo.encode("utf-8"),
        capture_output=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")


def test_ferramenta_alheia_passa_direto():
    assert _decidir("Read", {"file_path": "x.md"}).returncode == 0


def test_erro_interno_recusa(monkeypatch):
    """Fail-closed: 'não consegui medir' nunca vira permissão."""
    def explode(_entrada):
        raise RuntimeError("instrumento quebrado")
    monkeypatch.setattr(muralha, "avaliar", explode)
    monkeypatch.setattr(
        sys, "stdin",
        type("F", (), {"buffer": type("B", (), {"read": staticmethod(
            lambda: b'{"tool_name":"Bash","tool_input":{"command":"ls"}}')})()})(),
    )
    assert muralha.main() == 2


# ------------------------------------------------------------- a fiação ----


def test_settings_do_projeto_liga_a_muralha():
    """Muralha sem fiação é decoração (RETROSPECTIVA-FASE-D §2)."""
    fiacao = json.loads(FIACAO.read_text(encoding="utf-8"))
    entradas = fiacao.get("hooks", {}).get("PreToolUse", [])
    minhas = [
        e for e in entradas
        if any("muralha_das_armadilhas.py" in h.get("command", "")
               for h in e.get("hooks", []))
    ]
    assert minhas, "a muralha não está ligada em .claude/settings.json"
    matcher = minhas[0].get("matcher", "")
    for ferramenta in muralha.FERRAMENTAS_COBERTAS:
        assert ferramenta in matcher, (
            f"a tabela tem regra para {ferramenta} e o matcher não o cobre — "
            "a regra nunca rodaria"
        )


def test_toda_regra_aponta_uma_entrada_que_existe():
    """Recusa apontando entrada apagada é pior que recusa nenhuma."""
    for regra in muralha.REGRAS:
        achados = list((RAIZ_DO_REPO / "armadilhas").glob(f"{regra.armadilha}-*.md"))
        assert achados, f"a regra cita armadilhas/{regra.armadilha}, que não existe"


def test_toda_regra_declara_autoridade_e_confianca_conhecidas():
    for regra in muralha.REGRAS:
        assert regra.autoridade in ("sombra", "bloqueia")
        assert regra.confianca in ("estrutural", "alta")
        if regra.confianca == "alta":
            assert regra.autoridade == "sombra" or regra.armadilha in PROMOVIDAS, (
                "confiança 'alta' nasce em sombra; a promoção passa pelo "
                "relatório do termômetro (lei da autoridade proporcional à certeza)"
            )


# Armadilhas já promovidas a bloqueio, com o relatório de falsos positivos como
# prova. Crescer esta lista é um PR deliberado, nunca um efeito colateral.
PROMOVIDAS: frozenset = frozenset()


def test_o_custo_por_chamada_e_baixo():
    """A muralha roda em TODA chamada de shell: a tabela não pode ficar cara."""
    import time
    entrada = {"tool_name": "Bash", "tool_input": {"command": "make ci && git status"}}
    inicio = time.perf_counter()
    for _ in range(200):
        muralha.avaliar(entrada)
    assert time.perf_counter() - inicio < 1.0
