"""A DÍVIDA DO LIVRO — o guarda que transforma "registre ao terminar" em mecanismo.

Cada teste aqui é uma linha da regra de `ci/divida_do_livro.py`, e todos rodam
**sem rede**: as histórias de merge são montadas à mão. Um guarda cuja única
prova fosse o GitHub de verdade não conseguiria exercitar justamente os casos
que decidem se ele é justo — a folga do lote, a isenção do PR de livro, a
virada do marco zero — porque esses estados não se produzem sob encomenda.

O que NÃO se testa aqui, de propósito: se o `gh` responde. Isso é
instrumentação, e o resultado dela já é `ERROR` por construção (INV-CI01) —
"não consegui medir" nunca vira "está em dia".
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "ci"))

from divida_do_livro import (  # noqa: E402
    GRACA_EM_MINUTOS,
    INICIO_DA_COBRANCA,
    divida,
    numeros_citados,
    so_toca_o_livro,
)

AGORA = INICIO_DA_COBRANCA + timedelta(days=1)


def merge(numero: int, quando: datetime, arquivos: list[str], titulo="trabalho"):
    return {
        "number": numero,
        "title": titulo,
        "mergedAt": quando.astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "files": [{"path": caminho} for caminho in arquivos],
    }


@pytest.fixture
def livro(tmp_path):
    """Um repositório de mentira com um livro vazio."""
    (tmp_path / "painel" / "registros").mkdir(parents=True)
    return tmp_path


def registrar(raiz: Path, nome: str, texto: str):
    (raiz / "painel" / "registros" / f"{nome}.js").write_text(texto, encoding="utf-8")


# ------------------------------------------------------------------ a citação


def test_a_leitura_funciona_no_livro_de_verdade():
    """Sanidade contra o repositório real, e não só contra fixtures.

    Um parser que só funciona no formato que o próprio teste inventou não prova
    nada sobre o livro que existe. Se esta asserção cair, a citação mudou de
    forma e a regra deixou de enxergar registro honesto.
    """
    assert len(numeros_citados(RAIZ)) >= 3


def test_as_duas_formas_de_citar_valem(livro):
    """URL e forma curta. Cobrar uma só reprovaria registro honesto por estilo."""
    registrar(livro, "a", 'evidencia: "https://github.com/o/r/pull/100 — MERGED"')
    registrar(livro, "b", 'detalhe: "fechado no #101, junto com o #102"')
    assert numeros_citados(livro) == {100, 101, 102}


def test_um_registro_pode_contar_varios_prs(livro):
    """O fechamento de um LOTE é um acontecimento só, com vários PRs.

    Caso levantado por outra sessão em 26/08/2026, que escreve assim: o registro
    036 dela cita #248 e #252 na mesma evidência. Se a regra exigisse um
    registro POR PR, o jeito honesto de fechar um lote colidiria com a catraca
    na primeira janela — e o incentivo passaria a ser picotar o livro para
    agradar o guarda, em vez de contar o que aconteceu.
    """
    registrar(
        livro,
        "fechamento-do-lote",
        'evidencia: "https://github.com/o/r/pull/248 e '
        'https://github.com/o/r/pull/252 — os dois MERGED"',
    )
    velho = AGORA - timedelta(hours=5)
    prs = [merge(248, velho, ["services/x/a.py"]), merge(252, velho, ["infra/y.yml"])]
    assert divida(livro, AGORA, prs) == []


def test_pr_citado_nao_e_divida(livro):
    registrar(livro, "a", 'evidencia: "https://github.com/o/r/pull/100 — MERGED"')
    velho = AGORA - timedelta(hours=5)
    assert divida(livro, AGORA, [merge(100, velho, ["services/x/a.py"])]) == []


# ------------------------------------------------------------ isenção 1: livro


def test_pr_que_so_toca_o_painel_e_isento(livro):
    """Sem esta isenção o sistema trava: para registrar é preciso mergear."""
    velho = AGORA - timedelta(hours=5)
    prs = [merge(100, velho, ["painel/registros/x.js", "painel/manifesto.js"])]
    assert divida(livro, AGORA, prs) == []


def test_pr_que_toca_painel_E_outra_coisa_nao_e_isento(livro):
    """A isenção é para o PR que É o registro — não para o que leva um de carona."""
    velho = AGORA - timedelta(hours=5)
    prs = [merge(100, velho, ["painel/registros/x.js", "services/x/a.py"])]
    assert [p["number"] for p in divida(livro, AGORA, prs)] == [100]


# -------------------------------------------------------------- isenção 2: folga


def test_dentro_da_folga_nao_cobra(livro):
    """O `RUNBOOK-LOTES.md` mergeia vários em série e registra no fechamento."""
    recente = AGORA - timedelta(minutes=GRACA_EM_MINUTOS - 5)
    assert divida(livro, AGORA, [merge(100, recente, ["services/x/a.py"])]) == []


def test_depois_da_folga_cobra(livro):
    esquecido = AGORA - timedelta(minutes=GRACA_EM_MINUTOS + 5)
    assert [p["number"] for p in divida(livro, AGORA, [merge(100, esquecido, ["a.py"])])] == [100]


# --------------------------------------------------- isenção 3: o marco zero


def test_merge_anterior_ao_marco_zero_nao_e_divida(livro):
    """Cobrar o passado inventaria 17 devedores ja contados em prosa.

    Uma divida impagavel nao e um guarda severo — e um guarda que alguem
    desliga. A medicao que motivou este limite esta no comentario de
    `INICIO_DA_COBRANCA`.
    """
    antigo = INICIO_DA_COBRANCA - timedelta(hours=1)
    assert divida(livro, AGORA, [merge(100, antigo, ["services/x/a.py"])]) == []


def test_merge_logo_depois_do_marco_zero_e_divida(livro):
    novo = INICIO_DA_COBRANCA + timedelta(minutes=1)
    agora = INICIO_DA_COBRANCA + timedelta(minutes=GRACA_EM_MINUTOS + 10)
    assert [p["number"] for p in divida(livro, agora, [merge(100, novo, ["a.py"])])] == [100]


# ------------------------------------------------------------------ a ordem


def test_o_mais_recente_aparece_primeiro(livro):
    velho = AGORA - timedelta(hours=10)
    menos_velho = AGORA - timedelta(hours=3)
    prs = [merge(1, velho, ["a.py"]), merge(2, menos_velho, ["b.py"])]
    assert [p["number"] for p in divida(livro, AGORA, prs)] == [2, 1]


# ------------------------------------------------- a catraca de fato reprova


def test_a_porta_do_merge_reprova_com_divida(livro, monkeypatch):
    """O teste que mede o que importa: a catraca DIZ NÃO.

    Sem isto, a regra poderia estar perfeita e desligada — que é exatamente o
    estado anterior a este guarda (o lembrete impresso no fim do merge).
    """
    import mergear
    from _nucleo import Estado

    esquecido = AGORA - timedelta(hours=5)
    monkeypatch.setattr(
        mergear, "divida", lambda raiz: [merge(100, esquecido, ["services/x/a.py"])]
    )
    resultado = mergear.checar_divida_do_livro(livro, {"files": [{"path": "a.py"}]})
    assert resultado.estado is Estado.FAIL
    assert "#100" in (resultado.detalhe or "")


def test_a_porta_do_merge_libera_o_pr_de_livro(livro, monkeypatch):
    import mergear
    from _nucleo import Estado

    esquecido = AGORA - timedelta(hours=5)
    monkeypatch.setattr(
        mergear, "divida", lambda raiz: [merge(100, esquecido, ["services/x/a.py"])]
    )
    pr = {"files": [{"path": "painel/registros/novo.js"}]}
    assert mergear.checar_divida_do_livro(livro, pr).estado is Estado.PASS


def test_falha_de_medicao_vira_ERROR_e_nunca_PASS(livro, monkeypatch):
    """INV-CI01: 'não consegui medir' é resultado, não silêncio."""
    import mergear
    from _nucleo import Estado

    def explode(raiz):
        raise RuntimeError("gh fora do ar")

    monkeypatch.setattr(mergear, "divida", explode)
    resultado = mergear.checar_divida_do_livro(livro, {"files": [{"path": "a.py"}]})
    assert resultado.estado is Estado.ERROR


# ------------------------------------------------------------------- ajudante


def test_so_toca_o_livro_recusa_lista_vazia():
    """PR sem arquivo nenhum não é 'PR de livro' — é medição estranha.

    Tratar lista vazia como isenta abriria a porta larga: qualquer falha que
    devolvesse `files: []` viraria isenção silenciosa para todo mundo.
    """
    assert so_toca_o_livro([]) is False
