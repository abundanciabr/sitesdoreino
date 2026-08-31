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
    EMBARCADO,
    GRACA_EM_MINUTOS,
    INICIO_DA_COBRANCA,
    ISENTO,
    SEM_CITACAO,
    SEM_REGISTRO,
    como_pagar,
    divida,
    numeros_citados,
    pagamentos_em_voo,
    registro_embarcado,
    so_toca_o_livro,
)

AGORA = INICIO_DA_COBRANCA + timedelta(days=1)


def merge(numero: int, quando: datetime, arquivos: list[str], titulo="trabalho"):
    return {
        "number": numero,
        "title": titulo,
        "mergedAt": quando.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
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
    assert [
        p["number"] for p in divida(livro, AGORA, [merge(100, esquecido, ["a.py"])])
    ] == [100]


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
    assert [
        p["number"] for p in divida(livro, agora, [merge(100, novo, ["a.py"])])
    ] == [100]


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


def test_so_escriturar_isenta_mesmo_misturando_livro_e_fila():
    """O gesto NORMAL de quem termina um trabalho escreve nos dois: o registro
    para o dono e o fechamento da tarefa no balcão.

    Enquanto a isenção era só `painel/`, esse PR virava dívida — uma dívida sem
    dono real, que trava a fila de pouso de TODOS os robôs até alguém escrever
    um registro sobre um PR que não tinha o que registrar. Custou dois PRs de
    rodeio em 30/08 (`armadilhas/214`) e três rodadas em 31/08, a última
    segurando um passo que o mantenedor esperava no terminal.
    """
    assert so_toca_o_livro(
        [
            "painel/registros/20260831-001-alguma-coisa.js",
            "fila/tarefas/099-alguma-tarefa.json",
            "fila/eventos/20260831-120000-TAR-099-concluida.json",
        ]
    )
    assert so_toca_o_livro(["fila/eventos/20260831-120000-TAR-099-concluida.json"])


def test_quem_entrega_codigo_continua_devendo_registro():
    """A outra metade da mesma regra, e a que não pode afrouxar: a isenção é
    para quem SÓ escritura. Um PR que fecha a tarefa E mexe no código continua
    tendo o que contar ao dono — é justamente o trabalho dele que interessa."""
    assert not so_toca_o_livro(
        [
            "fila/eventos/20260831-120000-TAR-099-concluida.json",
            "services/funil/apps/core/views.py",
        ]
    )
    assert not so_toca_o_livro(
        ["painel/registros/20260831-001-x.js", "infra/docker-compose.yml"]
    )


def test_pasta_com_nome_parecido_nao_pega_carona():
    """`startswith` sobre prefixo de PASTA, nunca sobre o nome solto: um
    arquivo chamado `fila-de-espera.py` na raiz não é escrituração."""
    assert not so_toca_o_livro(["fila-de-espera.py"])
    assert not so_toca_o_livro(["painelzinho/coisa.js"])


def test_so_toca_o_livro_recusa_lista_vazia():
    """PR sem arquivo nenhum não é 'PR de livro' — é medição estranha.

    Tratar lista vazia como isenta abriria a porta larga: qualquer falha que
    devolvesse `files: []` viraria isenção silenciosa para todo mundo.
    """
    assert so_toca_o_livro([]) is False


# --------------------------------------- o embarque (a porta, desde 31/08/2026)
#
# A dívida nascia do caminho NORMAL: o rito manda pedir pouso e ir embora, e
# depois do pouso não há mais ninguém para registrar. A cura junta o fato e o
# recibo no mesmo átomo — o PR embarca o próprio registro, citando o próprio
# número, e o portão confere ANTES do pouso (`armadilhas/248`).


def remessa(caminho: str, patch: str) -> dict:
    """Um item de `gh api .../pulls/N/files`, como o GitHub devolve."""
    return {"filename": caminho, "patch": patch}


def test_pr_de_escrituracao_e_isento_de_embarque():
    """O PR que É o registro não deve registro sobre si mesmo — circular."""
    arquivos = ["painel/registros/20260831-001-x.js", "fila/eventos/e.json"]
    assert registro_embarcado(500, arquivos, []) == ISENTO


def test_pr_sem_registro_a_bordo_reprova():
    assert registro_embarcado(500, ["services/x/a.py"], []) == SEM_REGISTRO


def test_registro_a_bordo_citando_o_proprio_numero_embarca():
    """As duas formas de citar valem — URL e forma curta, como no livro."""
    arquivos = ["services/x/a.py", "painel/registros/20260831-001-x.js"]
    por_url = [
        remessa(
            "painel/registros/20260831-001-x.js",
            '+  evidencia: "https://github.com/o/r/pull/500",',
        )
    ]
    por_forma_curta = [
        remessa("painel/registros/20260831-001-x.js", '+  detalhe: "o PR #500",')
    ]
    assert registro_embarcado(500, arquivos, por_url) == EMBARCADO
    assert registro_embarcado(500, arquivos, por_forma_curta) == EMBARCADO


def test_registro_a_bordo_sem_o_proprio_numero_reprova():
    """`armadilhas/185`, agora com guarda: registro a bordo que cita OUTRO
    número (ou nenhum) não é o recibo DESTE trabalho — a dívida seria real e
    cairia no colo da sessão seguinte."""
    arquivos = ["services/x/a.py", "painel/registros/20260831-001-x.js"]
    outro_numero = [
        remessa(
            "painel/registros/20260831-001-x.js",
            '+  evidencia: "https://github.com/o/r/pull/499",',
        )
    ]
    assert registro_embarcado(500, arquivos, outro_numero) == SEM_CITACAO


def test_citacao_em_linha_removida_nao_conta():
    """Linha removida seria registro SAINDO do livro — e registro não se
    apaga. Só o que o PR ACRESCENTA é recibo."""
    arquivos = ["services/x/a.py", "painel/registros/20260831-001-x.js"]
    remessas = [
        remessa("painel/registros/20260831-001-x.js", '-  detalhe: "o PR #500",')
    ]
    assert registro_embarcado(500, arquivos, remessas) == SEM_CITACAO


def test_citacao_fora_do_livro_nao_conta():
    """Citar o próprio número num comentário de código não é registrar."""
    arquivos = ["services/x/a.py", "painel/registros/20260831-001-x.js"]
    remessas = [remessa("services/x/a.py", "+# nascido no PR #500")]
    assert registro_embarcado(500, arquivos, remessas) == SEM_CITACAO


def test_a_porta_cobra_o_embarque_sem_precisar_de_rede(livro):
    """O caso comum (nenhum registro a bordo) reprova ANTES de qualquer
    chamada ao GitHub — guarda lento é guarda que alguém desliga."""
    import mergear
    from _nucleo import Estado

    pr = {"number": 500, "files": [{"path": "services/x/a.py"}]}
    resultado = mergear.checar_registro_embarcado(livro, pr)
    assert resultado.estado is Estado.FAIL
    assert "reservar.py numero registro" in (resultado.detalhe or "")


def test_a_porta_libera_o_embarque_completo(livro, monkeypatch):
    import json as json_

    import mergear
    from _nucleo import Estado

    diff = [
        remessa(
            "painel/registros/20260831-001-x.js",
            '+  evidencia: "https://github.com/o/r/pull/500",',
        )
    ]
    monkeypatch.setattr(mergear, "_gh", lambda *a, **kw: json_.dumps(diff))
    pr = {
        "number": 500,
        "files": [
            {"path": "services/x/a.py"},
            {"path": "painel/registros/20260831-001-x.js"},
        ],
    }
    assert mergear.checar_registro_embarcado(livro, pr).estado is Estado.PASS


def test_falha_na_leitura_do_diff_vira_ERROR_e_nunca_PASS(livro, monkeypatch):
    """INV-CI01: 'não consegui ler o diff' não é 'está a bordo'."""
    import mergear
    from _nucleo import Estado

    monkeypatch.setattr(mergear, "_gh", lambda *a, **kw: "isto não é JSON")
    pr = {
        "number": 500,
        "files": [
            {"path": "services/x/a.py"},
            {"path": "painel/registros/20260831-001-x.js"},
        ],
    }
    assert mergear.checar_registro_embarcado(livro, pr).estado is Estado.ERROR


# ------------------------------------------------------- pagamentos em voo


def test_pagamentos_em_voo_filtra_so_escrituracao():
    """Só o PR que É pagamento entra na lista — um PR de código que leva
    registro de carona não paga dívida de ninguém."""
    abertos = [
        {"number": 1, "title": "livro: paga", "files": [{"path": "painel/registros/a.js"}]},
        {"number": 2, "title": "feat: entrega", "files": [{"path": "services/x/a.py"}]},
        {
            "number": 3,
            "title": "feat com recibo",
            "files": [{"path": "services/x/a.py"}, {"path": "painel/registros/b.js"}],
        },
    ]
    assert [p["number"] for p in pagamentos_em_voo(abertos)] == [1]


def test_como_pagar_lista_o_pagamento_em_voo():
    """A recusa que mata a corrida de cobradores: antes de escrever, olhe o
    que já voa (4 PRs pagaram as mesmas duas dívidas em 31/08/2026)."""
    devedores = [merge(100, AGORA - timedelta(hours=5), ["a.py"])]
    em_voo = [{"number": 744, "title": "livro: os comprovantes que faltavam"}]
    texto = como_pagar(devedores, em_voo)
    assert "EM VOO" in texto
    assert "#744" in texto
    assert "NÃO crie outro" in texto


def test_como_pagar_fica_de_pe_sem_a_lista_dos_abertos():
    """`None` = 'não consegui olhar os abertos' — a recusa base não pode
    depender do enriquecimento."""
    devedores = [merge(100, AGORA - timedelta(hours=5), ["a.py"])]
    texto = como_pagar(devedores, None)
    assert "#100" in texto
    assert "EM VOO" not in texto
