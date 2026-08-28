"""O ARAUTO — provas de que ele prefere calar a mentir.

Todos rodam **sem rede**: as respostas do GitHub são montadas à mão. Um guarda
cuja única prova dependesse do GitHub de verdade não conseguiria exercitar
justamente o caso que decide se ele presta — o da consulta que falha — porque
esse estado não se produz sob encomenda.

A propriedade central sob teste é uma só, e é o motivo de o arquivo existir:
**boletim parcial nunca sai**. Um boletim que perde uma seção em silêncio tem a
mesma cara de um boletim inteiro, e recria a Classe 8 (mapa velho) escondida
atrás de uma falsa sensação de segurança. Se alguém trocar o fail-closed por um
`try/except: pass`, os testes `recusa_*` e `sem_meia_verdade` ficam vermelhos.
"""

import sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "ci"))

from _nucleo import ErroDeInstrumentacao  # noqa: E402
from boletim import (  # noqa: E402
    JANELA_HORAS,
    Dados,
    area_do_ramo,
    coletar,
    montar,
    proximo_numero_livre,
)

AGORA = datetime(2026, 8, 28, 18, 0, tzinfo=timezone.utc)


def dados(**mudancas) -> Dados:
    base = Dados(
        atraso_do_espelho=0,
        prs_abertos=[],
        pousos=[],
        leis_mudadas=[],
        reservas=[],
        proximo_registro="001",
        proxima_armadilha="001",
    )
    return replace(base, **mudancas)


# --------------------------------------------------------------------------
# A propriedade central: nada parcial chega à tela
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "campo",
    [
        "atraso_do_espelho",
        "prs_abertos",
        "pousos",
        "leis_mudadas",
        "reservas",
        "proximo_registro",
        "proxima_armadilha",
    ],
)
def test_sem_meia_verdade_montar_recusa_campo_ausente(campo):
    """Campo faltando ⇒ nada impresso. Vale para TODO campo, não só o lembrado."""
    with pytest.raises(ErroDeInstrumentacao) as erro:
        montar(dados(**{campo: None}))
    assert campo in erro.value.detalhe


def test_recusa_quando_o_git_nao_responde(tmp_path, monkeypatch):
    """Instrumento quebrado ⇒ ErroDeInstrumentacao, nunca um boletim otimista."""
    import boletim

    def git_quebrado(comando, **kwargs):
        raise ErroDeInstrumentacao("git não respondeu", "simulado pelo teste")

    monkeypatch.setattr(boletim, "executar", git_quebrado)
    with pytest.raises(ErroDeInstrumentacao):
        coletar(tmp_path, agora=AGORA)


def test_recusa_quando_o_atraso_nao_e_numero(tmp_path, monkeypatch):
    """`rev-list` devolvendo lixo não pode virar 'em dia com origin/main'.

    Este é o caso sutil: exit 0 com stdout inesperado. Sem esta checagem, um
    `int()` estouraria — ou pior, um `or 0` diria que a árvore está fresca.
    """
    import boletim

    class Falsa:
        stdout = "sei lá"

    monkeypatch.setattr(boletim, "executar", lambda *a, **k: Falsa())
    with pytest.raises(ErroDeInstrumentacao) as erro:
        coletar(tmp_path, agora=AGORA)
    assert "atraso" in erro.value.resumo


def test_recusa_quando_o_github_responde_algo_que_nao_e_json(tmp_path, monkeypatch):
    import boletim

    class Falsa:
        stdout = "<html>login</html>"

    monkeypatch.setattr(boletim, "executar", lambda *a, **k: Falsa())
    with pytest.raises(ErroDeInstrumentacao):
        boletim._gh_json(["pr", "list"], tmp_path, "listar PRs")


def test_pastas_ausentes_param_o_boletim(tmp_path, monkeypatch):
    """Sem `painel/registros/` não dá para dizer qual número está livre — então cala."""
    import boletim

    class Falsa:
        stdout = "0"

    monkeypatch.setattr(boletim, "executar", lambda *a, **k: Falsa())
    monkeypatch.setattr(boletim, "_gh_json", lambda *a, **k: [])
    monkeypatch.setattr(boletim, "refs_existentes", lambda *a, **k: [])
    with pytest.raises(ErroDeInstrumentacao) as erro:
        coletar(tmp_path, agora=AGORA)
    assert "registros" in erro.value.resumo


# --------------------------------------------------------------------------
# O que o boletim precisa GRITAR
# --------------------------------------------------------------------------


def test_arvore_atrasada_avisa_que_os_fatos_sao_suspeitos():
    """75 não parece diferente de 0 em tela nenhuma — então tem de estar escrito."""
    texto = montar(dados(atraso_do_espelho=75))
    assert "ATRASADA em 75" in texto
    assert "SUSPEITO" in texto
    assert "git show origin/main:" in texto


def test_arvore_em_dia_nao_grita_a_toa():
    texto = montar(dados(atraso_do_espelho=0))
    assert "em dia com origin/main" in texto
    assert "SUSPEITO" not in texto


def test_lei_mudada_aparece_em_destaque():
    texto = montar(dados(leis_mudadas=["RITOS.md"]))
    assert "LEI MUDOU" in texto
    assert "RITOS.md" in texto


def test_sem_lei_mudada_a_secao_nao_aparece():
    assert "LEI MUDOU" not in montar(dados())


def test_intencao_reservada_aparece_para_os_outros():
    """Sem leitor, a reserva de intenção não ataca a Classe 5 — só enfeita."""
    texto = montar(dados(reservas=["onda2-reservar"]))
    assert "onda2-reservar" in texto
    assert "INTENÇÕES RESERVADAS" in texto


def test_ninguem_reservou_e_dito_explicitamente():
    assert "ninguém anunciou" in montar(dados(reservas=[]))


def test_o_numero_livre_se_declara_nao_reserva():
    """A honestidade que separa 'encurtar a corrida' de 'fingir que a venceu'."""
    texto = montar(dados(proximo_registro="037"))
    assert "037" in texto
    assert "NÃO é reserva" in texto


def test_pr_aberto_mostra_area_e_tamanho():
    texto = montar(
        dados(
            prs_abertos=[
                {
                    "number": 42,
                    "title": "painel: o tanque à vista",
                    "headRefName": "agent/painel/tanque",
                    "files": [{"path": "a"}, {"path": "b"}],
                }
            ]
        )
    )
    assert "#42" in texto and "painel" in texto and "2 arq." in texto


def test_ninguem_mexendo_e_dito_explicitamente():
    """Seção vazia diz 'ninguém' — silêncio pareceria seção que não carregou."""
    assert "ninguém" in montar(dados(prs_abertos=[]))


# --------------------------------------------------------------------------
# Nada é adivinhado
# --------------------------------------------------------------------------


def test_area_sai_do_ramo_no_padrao():
    assert area_do_ramo("agent/painel/vista-fila") == "painel"


@pytest.mark.parametrize("ramo", ["claude/ecstatic-nash-ee3c08", "main", "tmp", ""])
def test_ramo_fora_do_padrao_e_dito_como_tal_nunca_adivinhado(ramo):
    assert area_do_ramo(ramo) == "(fora do padrão)"


# --------------------------------------------------------------------------
# O número livre
# --------------------------------------------------------------------------


def test_numero_livre_pula_os_ocupados():
    nomes = ["20260828-001-a.js", "20260828-002-b.js", "20260828-003-c.js"]
    assert proximo_numero_livre(nomes, "20260828-", 3) == "004"


def test_numero_livre_preenche_buraco_do_meio_em_registros():
    """Buraco no meio é número livre de verdade em `registros/`, que nasce por dia."""
    nomes = ["20260828-001-a.js", "20260828-003-c.js"]
    assert proximo_numero_livre(nomes, "20260828-", 3) == "002"


def test_armadilha_nunca_reusa_numero_aposentado():
    """A regra dura de `armadilhas/085`: número vago no meio está APOSENTADO.

    Este teste nasceu de um defeito real: rodando o boletim contra o
    repositório de verdade, a política errada anunciou `armadilha 001` — um
    número que nunca existiu — porque a pasta começa em 003. Referências
    antigas ainda apontam para os vagos; reusar um quebraria a citação.
    """
    nomes = ["003-a.md", "004-b.md", "153-z.md"]
    assert proximo_numero_livre(nomes, "", 3, politica="acima_de_todos") == "154"


def test_politica_desconhecida_para_em_vez_de_chutar():
    with pytest.raises(ErroDeInstrumentacao):
        proximo_numero_livre(["003-a.md"], "", 3, politica="sei-la")


def test_numero_livre_comeca_em_um_quando_o_dia_esta_vazio():
    assert proximo_numero_livre([], "20260828-", 3) == "001"


def test_numero_livre_ignora_nome_sem_numero():
    assert proximo_numero_livre(["INDICE.md", "001-a.md"], "", 3) == "002"


# --------------------------------------------------------------------------
# A janela de 24h
# --------------------------------------------------------------------------


def test_pouso_velho_fica_de_fora(tmp_path, monkeypatch):
    import boletim

    class Falsa:
        stdout = "0"

    velho = (
        (AGORA - timedelta(hours=JANELA_HORAS + 2)).isoformat().replace("+00:00", "Z")
    )
    novo = (AGORA - timedelta(hours=1)).isoformat().replace("+00:00", "Z")

    (tmp_path / "painel" / "registros").mkdir(parents=True)
    (tmp_path / "armadilhas").mkdir()

    monkeypatch.setattr(boletim, "executar", lambda *a, **k: Falsa())
    monkeypatch.setattr(boletim, "refs_existentes", lambda *a, **k: [])
    monkeypatch.setattr(
        boletim,
        "_gh_json",
        lambda args, *a, **k: (
            []
            if "open" in args
            else [
                {"number": 1, "title": "velho", "mergedAt": velho},
                {"number": 2, "title": "novo", "mergedAt": novo},
            ]
        ),
    )
    resultado = coletar(tmp_path, agora=AGORA)
    assert [pr["number"] for pr in resultado.pousos] == [2]
