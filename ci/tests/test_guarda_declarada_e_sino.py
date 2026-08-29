"""Guardas da coluna `Guarda` do índice e do sino das armadilhas.

O que estes testes protegem, e por quê:

1. **Uma armadilha declara QUEM a faz valer.** Sem isso, o catálogo não sabe
   distinguir "lição imposta por mecanismo" de "lição que só vale se você a
   tiver lido" — e essa confusão é o padrão 2 da RETROSPECTIVA-FASE-D em pessoa.
   A coluna existe para que o buraco APAREÇA; os testes existem para que ela não
   possa mentir (guarda apontando arquivo morto, número que discorda do nome,
   'nenhum' sem motivo declarado).

2. **O sino cala quando deve.** Um conselho automático que toca à toa é pior que
   silêncio: ensina a ignorar o canal. Por isso o gerador REPROVA assinatura
   genérica (corpus feliz), e o sino é fail-open em toda borda.

3. **O aninhamento do JSON do hook.** `additionalContext` fora de
   `hookSpecificOutput` é ignorado EM SILÊNCIO pelo harness — o sino pareceria
   funcionar e nunca falaria com ninguém. É falso-verde puro, então é asserção.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

CI = Path(__file__).resolve().parents[1]
if str(CI) not in sys.path:
    sys.path.insert(0, str(CI))

import indice_de_armadilhas as indice  # noqa: E402
import muralha_das_armadilhas as muralha  # noqa: E402
import sino_das_armadilhas as sino  # noqa: E402
from _nucleo import raiz_do_repo  # noqa: E402

RAIZ = raiz_do_repo()
SINO = CI / "sino_das_armadilhas.py"
FIACAO = RAIZ / ".claude" / "settings.json"

FRONTMATTER_BOM = """---
schema_version: 2
armadilha: 1
estado: guardada
degrau: 3
confianca: alta
custo_por_queda: alto
guarda:
  tipo: muralha
  detector: um_detector
  dono: ci/indice_de_armadilhas.py
sinal:
  - `ErroBemEspecifico: coisa \\d+ nao encontrada`
---

# Uma entrada de teste

**Sintoma:** o comando morre.
"""


def _repo(tmp_path: Path, corpo: str, nome: str = "001-primeira.md") -> Path:
    pasta = tmp_path / indice.PASTA
    pasta.mkdir(exist_ok=True)
    (pasta / nome).write_text(corpo, encoding="utf-8", newline="\n")
    # O dono citado precisa EXISTIR na casa encenada: é justamente isso que o
    # guarda de referência morta confere.
    dono = tmp_path / "ci" / "indice_de_armadilhas.py"
    dono.parent.mkdir(exist_ok=True)
    dono.write_text("# dublê do dono da guarda\n", encoding="utf-8")
    return tmp_path


def _rodar(raiz: Path):
    return indice.rodar(raiz, conferir=False)


# ------------------------------------------------- a coluna diz a verdade ----


def test_entrada_com_frontmatter_declara_a_guarda(tmp_path: Path):
    raiz = _repo(tmp_path, FRONTMATTER_BOM)
    assert _rodar(raiz) == 0
    texto = (raiz / indice.PASTA / indice.NOME_DO_INDICE).read_text(encoding="utf-8")
    assert "| muralha+sino |" in texto
    guardas = json.loads(
        (raiz / indice.PASTA / indice.NOME_DAS_GUARDAS).read_text(encoding="utf-8")
    )
    assert guardas["guardas"][0]["detector"] == "um_detector"
    assert guardas["guardas"][0]["estado"] == "guardada"


def test_entrada_legado_aparece_como_sem_guarda(tmp_path: Path):
    """As 153 antigas seguem válidas — e o buraco delas fica VISÍVEL."""
    raiz = _repo(tmp_path, "# Entrada antiga\n\n**Sintoma:** algo.\n")
    assert _rodar(raiz) == 0
    texto = (raiz / indice.PASTA / indice.NOME_DO_INDICE).read_text(encoding="utf-8")
    assert "— sem guarda" in texto
    assert "0 com guarda declarada, 1 ainda sem" in texto


@pytest.mark.parametrize(
    "troca, esperado",
    [
        ("estado: guardada\n", "estado: inventado\n"),
        ("confianca: alta\n", "confianca: altissima\n"),
        ("  tipo: muralha\n", "  tipo: telepatia\n"),
        ("armadilha: 1\n", "armadilha: 99\n"),
        ("schema_version: 2\n", "schema_version: 7\n"),
        ("degrau: 3\n", "degrau: 3\ninventada: sim\n"),
        ("  dono: ci/indice_de_armadilhas.py\n", "  dono: ci/nao_existe.py\n"),
    ],
    ids=["estado", "confianca", "tipo", "numero", "schema", "chave-extra", "dono-morto"],
)
def test_frontmatter_invalido_e_ERROR(tmp_path: Path, troca: str, esperado: str):
    """ERROR, não FAIL: regenerar não conserta — alguém precisa decidir."""
    raiz = _repo(tmp_path, FRONTMATTER_BOM.replace(troca, esperado))
    with pytest.raises(indice.ErroDeInstrumentacao):
        _rodar(raiz)


def test_guarda_nenhum_sem_motivo_e_ERROR(tmp_path: Path):
    """Buraco assumido é gerenciável; buraco silencioso não."""
    corpo = FRONTMATTER_BOM.replace(
        "  tipo: muralha\n  detector: um_detector\n  dono: ci/indice_de_armadilhas.py\n",
        "  tipo: nenhum\n",
    )
    raiz = _repo(tmp_path, corpo)
    with pytest.raises(indice.ErroDeInstrumentacao):
        _rodar(raiz)


def test_guarda_nenhum_com_motivo_passa(tmp_path: Path):
    corpo = FRONTMATTER_BOM.replace(
        "  tipo: muralha\n  detector: um_detector\n  dono: ci/indice_de_armadilhas.py\n",
        "  tipo: nenhum\n  motivo: `corrompe em silencio, nao da para detectar`\n",
    )
    raiz = _repo(tmp_path, corpo)
    assert _rodar(raiz) == 0
    texto = (raiz / indice.PASTA / indice.NOME_DO_INDICE).read_text(encoding="utf-8")
    assert "nenhum (declarado)" in texto or "sino" in texto


# ------------------------------------------- sinal que tocaria à toa reprova ----


@pytest.mark.parametrize(
    "sinal, motivo_esperado",
    [
        ("`erro`", "curto demais"),
        ("`(ErroGrave)?(Traceback)?`", "casa a string vazia"),
        ("`[nao fecha`", "não compila"),
        ("`PASS indice-de-armadilhas`", "BENIGNA"),
        ("`passed in `", "BENIGNA"),
    ],
    ids=["curto", "casa-vazio", "nao-compila", "corpus-feliz", "pytest-verde"],
)
def test_sinal_ruim_e_ERROR_na_geracao(tmp_path: Path, sinal: str, motivo_esperado: str):
    """A mensagem tem de dizer QUAL guarda pegou.

    Sem isso o teste não distingue os guardas entre si: como todo regex que casa
    a string vazia também casa qualquer saída benigna, desligar a checagem de
    vazio deixava a suíte verde — a prova por mutação apanhou exatamente isso
    (é a armadilhas/155: a sabotagem 'passou' porque o teste media outra coisa).
    """
    corpo = FRONTMATTER_BOM.replace(
        "  - `ErroBemEspecifico: coisa \\d+ nao encontrada`", f"  - {sinal}"
    )
    raiz = _repo(tmp_path, corpo)
    with pytest.raises(indice.ErroDeInstrumentacao) as erro:
        _rodar(raiz)
    tudo = " ".join(str(parte) for parte in erro.value.args)
    assert motivo_esperado in tudo, f"pegou por outro motivo: {tudo[:160]}"


# ------------------------------------------------------------- o sino ----


def _sinais(regex: str = r"ConfigError: Schema for status \d+ is not set") -> list:
    return [{
        "armadilha": "021", "arquivo": "armadilhas/021-x.md",
        "titulo": "ConfigError", "regex": regex,
    }]


def test_o_sino_toca_no_erro_conhecido():
    aviso = sino.decidir({
        "tool_name": "Bash",
        "tool_input": {"command": "make ci"},
        "tool_response": {"stdout": "", "stderr":
                          "ConfigError: Schema for status 201 is not set in response"},
    }, _sinais())
    assert aviso and "armadilhas/021" in aviso
    assert "LEIA" in aviso, "tocar sem dizer o que abrir não resolve nada"


def test_o_sino_cala_em_saida_benigna():
    assert sino.decidir({
        "tool_name": "Bash", "tool_input": {"command": "make ci"},
        "tool_response": {"stdout": "929 passed in 239.63s"},
    }, _sinais()) is None


def test_o_sino_cala_quando_o_comando_le_o_catalogo():
    """O sintoma catalogado CONTÉM a mensagem de erro — ler não pode tocar."""
    assert sino.decidir({
        "tool_name": "Bash",
        "tool_input": {"command": "cat armadilhas/021-configerror.md"},
        "tool_response": {"stdout":
                          "ConfigError: Schema for status 201 is not set in response"},
    }, _sinais()) is None


def test_o_sino_le_a_saida_seja_qual_for_a_forma():
    """A documentação não fixa o formato de tool_response — ser defensivo é lei."""
    erro = "ConfigError: Schema for status 201 is not set"
    for resposta in (erro, {"output": erro}, {"stderr": erro}, [erro],
                     {"content": [erro]}):
        assert sino.decidir({
            "tool_name": "Bash", "tool_input": {"command": "x"},
            "tool_response": resposta,
        }, _sinais()) is not None, f"não enxergou a saída em {type(resposta)}"


def test_o_sino_e_fail_open_em_toda_borda():
    """Conselho que trava a sessão é pior que conselho nenhum."""
    for entrada in ("nao é json", "{}", '{"tool_name":"Bash"}'):
        proc = subprocess.run(
            [sys.executable, str(SINO)], input=entrada,
            capture_output=True, text=True, timeout=60,
            encoding="utf-8", errors="replace",
        )
        assert proc.returncode == 0, f"o sino recusou algo: {entrada!r}"


def test_o_json_do_sino_aninha_additional_context():
    """Fora de hookSpecificOutput o harness IGNORA em silêncio: falso-verde."""
    corpo = json.dumps({
        "tool_name": "Bash", "tool_input": {"command": "make ci"},
        "tool_response": {"stderr":
                          "ConfigError: Schema for status 201 is not set in response"},
    })
    proc = subprocess.run(
        [sys.executable, str(SINO)], input=corpo,
        capture_output=True, text=True, timeout=60,
        encoding="utf-8", errors="replace",
    )
    assert proc.returncode == 0
    saida = json.loads(proc.stdout)
    assert saida["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    assert "armadilhas/021" in saida["hookSpecificOutput"]["additionalContext"]
    assert "additionalContext" not in saida, "no topo, o harness ignora em silêncio"


# ------------------------------------------- coerência entre as duas metades ----


def test_todo_detector_declarado_existe_na_muralha():
    """O índice não importa o hook; um teste é que prova que os dois concordam."""
    declarados = {
        e.guarda.get("detector")
        for e in indice.coletar(RAIZ)
        if e.guarda.get("tipo") == "muralha" and e.guarda.get("detector")
    }
    reais = {r.detector_nome for r in muralha.REGRAS}
    assert declarados <= reais, (
        f"entrada declara detector que a muralha não tem: {declarados - reais}"
    )
    assert reais <= declarados, (
        f"a muralha tem regra que nenhuma entrada declara: {reais - declarados}"
    )


def test_o_sinal_do_repositorio_real_e_lido_pelo_sino():
    """Prova de fora: o SINAIS.json versionado é carregável pelo sino de verdade."""
    sinais = sino.carregar_sinais()
    assert sinais, "nenhum sinal declarado — o sino nunca tocaria"
    for s in sinais:
        assert (RAIZ / s["arquivo"]).is_file(), f"sinal aponta {s['arquivo']}, que sumiu"


def test_settings_do_projeto_liga_o_sino():
    """Sino sem fiação é decoração (RETROSPECTIVA-FASE-D §2)."""
    fiacao = json.loads(FIACAO.read_text(encoding="utf-8"))
    entradas = fiacao.get("hooks", {}).get("PostToolUse", [])
    ligado = [
        e for e in entradas
        if any("sino_das_armadilhas.py" in h.get("command", "")
               for h in e.get("hooks", []))
    ]
    assert ligado, "o sino não está ligado em .claude/settings.json"
    assert "Bash" in ligado[0].get("matcher", "")
