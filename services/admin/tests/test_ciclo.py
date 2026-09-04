"""O calendário do ciclo, `/admin/placar/ciclo/` (04/09/2026).

O que estes guardas protegem:

1. **A curva e a meta grande nunca discordam.** A soma dos alvos semanais tem
   de dar `alvo` menos `partida`, e o validador reprova o cartão quando não dá.
   Sem isso, o placar diria um número e o calendário outro, os dois com ar de
   certeza, e ninguém saberia qual está certo.
2. **O placar SEGUE a curva.** `esperado_em` deixa de ser a linha reta quando o
   cartão declara `semanas` — e é essa função que decide ganhando/perdendo, a
   meta do mês e a meta da semana. Um guarda que só olhasse a tela nova não
   veria se o resto do painel continuou julgando pela régua velha.
3. **A régua antiga continua valendo para quem não declara curva.** Cartão sem
   `semanas` mede em linha reta, como sempre.
4. **"Não sei" nunca vira zero.** Sem a `alunos`, as colunas do que aconteceu
   ficam em branco: um zero ali afirmaria que ninguém comprou naquela semana.
5. **Semana que não fechou não recebe veredito.** Julgar uma semana pela metade
   é o "ontem contra hoje engana" dos documentos.
6. **A porta continua sendo a porta.**
"""

from __future__ import annotations

import datetime as dt

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.core import ciclo, placar

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"
ALUNOS = "http://alunos:8000/api/alunos"
ALUNOS_LISTA = f"{ALUNOS}/matriculas"

#: Um cartão de meta com curva, pequeno o bastante para a conta ser óbvia:
#: duas semanas de 5 dias, alvo 30, partida 0.
CARTAO = {
    "alvo": 30,
    "partida": 0,
    "ate": "2026-09-30",
    "partida_em": "2026-09-01",
    "semanas": [
        {"n": 1, "de": "2026-09-07", "ate": "2026-09-11", "alvo": 10},
        {"n": 2, "de": "2026-09-14", "ate": "2026-09-18", "alvo": 20},
    ],
}


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    monkeypatch.setenv("ALUNOS_API_URL", ALUNOS)
    monkeypatch.setenv("ALUNOS_API_TOKEN", "token-do-par-admin-alunos")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


def _dentro() -> Client:
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "id-opaco-123",
                "nome_exibido": "Fulano",
                "papel": None,
                "email": DONO,
            },
        )
    )
    c = Client()
    c.defaults["HTTP_COOKIE"] = COOKIE
    return c


# --------------------------------------------------------------- a régua


def test_a_soma_das_semanas_e_a_meta_grande_no_cartao_de_verdade():
    """O cartão que está no repositório, medido: a curva soma a meta.

    Este é o guarda que vale mais que os outros juntos. Ele mede o arquivo
    REAL, e não um exemplo: no dia em que alguém ajustar a meta de uma semana
    sem ajustar as outras, é aqui que o PR fica vermelho.
    """
    cartao, recusas = placar.ler_cartao(
        placar.CARTAO_DA_META, placar.diretorio_dos_cartoes()
    )
    assert cartao is not None, f"o cartão da meta não abriu: {recusas}"
    semanas = cartao.get("semanas")
    assert semanas, "o cartão da meta perdeu a curva de semanas"
    soma = sum(s["alvo"] for s in semanas)
    assert (
        soma == cartao["alvo"] - cartao["partida"]
    ), f"a curva soma {soma} e a meta pede {cartao['alvo'] - cartao['partida']}"


def test_o_validador_reprova_curva_que_nao_fecha_com_a_meta():
    torto = {
        **CARTAO,
        "semanas": [{"n": 1, "de": "2026-09-07", "ate": "2026-09-11", "alvo": 7}],
    }
    problemas = placar._validar_as_semanas(torto)
    assert problemas and "não pode discordar" in problemas[0]


def test_o_validador_reprova_semanas_fora_de_ordem():
    torto = {
        **CARTAO,
        "semanas": [
            {"n": 1, "de": "2026-09-14", "ate": "2026-09-18", "alvo": 20},
            {"n": 2, "de": "2026-09-07", "ate": "2026-09-11", "alvo": 10},
        ],
    }
    problemas = placar._validar_as_semanas(torto)
    assert any("sobrepor" in p for p in problemas)


def test_cartao_sem_curva_nao_e_cobrado():
    assert placar._validar_as_semanas({"alvo": 30, "partida": 0}) == []


# ------------------------------------------------- o esperado segue a curva


@pytest.mark.parametrize(
    "dia,esperado",
    [
        ("2026-09-01", 0),  # antes da primeira semana: a partida
        ("2026-09-06", 0),  # véspera
        ("2026-09-07", 2),  # 1º dos 5 dias da semana de 10: 10 * 1/5
        ("2026-09-09", 6),  # 3º dia: 10 * 3/5
        ("2026-09-11", 10),  # fecha a semana 1
        ("2026-09-12", 10),  # sábado: fica no que a semana fechou
        ("2026-09-13", 10),  # domingo, idem
        ("2026-09-14", 14),  # 1º dos 5 dias da semana de 20: 10 + 20/5
        ("2026-09-18", 30),  # fecha a semana 2
        ("2026-09-30", 30),  # depois da última: o alvo
    ],
)
def test_o_esperado_anda_pela_curva_e_para_no_fim_de_semana(dia, esperado):
    assert placar.esperado_em(CARTAO, dt.date.fromisoformat(dia)) == esperado


def test_sem_curva_o_esperado_volta_a_ser_a_linha_reta():
    """A regra antiga, intacta: metade do prazo, metade da meta."""
    sem_curva = {k: v for k, v in CARTAO.items() if k != "semanas"}
    # 01/09 a 30/09 são 29 dias; no 15º dia a linha reta passa em 30 * 15/29.
    assert placar.esperado_em(sem_curva, dt.date(2026, 9, 16)) == round(30 * 15 / 29)


def test_o_veredito_do_placar_usa_a_curva():
    """O MESMO dia e o MESMO número, julgados pelas duas réguas, discordam.

    É este teste que prova que a curva não é enfeite de uma tela: ela muda o
    veredito do placar. Em 09/09 com 6 vendas, a curva diz ganhando (ela
    esperava 6) e a linha reta diz perdendo (ela esperava 8). Se um dia alguém
    fizer `esperado_em` voltar a ignorar `semanas`, é aqui que fica vermelho.
    """
    hoje = dt.date(2026, 9, 9)
    sem_curva_cartao = {k: v for k, v in CARTAO.items() if k != "semanas"}
    com_curva = placar.calcular_placar(CARTAO, 6, hoje)
    sem_curva = placar.calcular_placar(sem_curva_cartao, 6, hoje)
    assert com_curva["esperado_hoje"] == 6
    assert com_curva["veredito"] == "ganhando"
    assert sem_curva["esperado_hoje"] == 8
    assert sem_curva["veredito"] == "perdendo"


# ------------------------------------------------------------- a contagem


def test_nao_consegui_perguntar_nunca_vira_zero():
    faixas = placar.semanas_do_ciclo(CARTAO)
    assert ciclo.contar_por_semana(None, faixas) is None
    linhas = ciclo.montar_as_semanas(faixas, None, dt.date(2026, 9, 20))
    assert [l["real"] for l in linhas] == [None, None]
    assert [l["acumulado_real"] for l in linhas] == [None, None]
    assert all(l["cumpriu"] is None for l in linhas)


def test_cada_compra_cai_na_semana_dela():
    faixas = placar.semanas_do_ciclo(CARTAO)
    alunos = [
        {"status": "ativa", "virou_aluno_em": "2026-09-08T10:00:00-03:00"},
        {"status": "ativa", "virou_aluno_em": "2026-09-08T11:00:00-03:00"},
        {"status": "suspensa", "virou_aluno_em": "2026-09-15T09:00:00-03:00"},
        # Fora de qualquer semana (um sábado): não some, só não entra em nenhuma.
        {"status": "ativa", "virou_aluno_em": "2026-09-12T09:00:00-03:00"},
        # Reembolsada não conta: a compra foi desfeita.
        {"status": "reembolsada", "virou_aluno_em": "2026-09-08T09:00:00-03:00"},
    ]
    assert ciclo.contar_por_semana(alunos, faixas) == [2, 1]


def test_semana_que_nao_fechou_nao_recebe_veredito():
    faixas = placar.semanas_do_ciclo(CARTAO)
    # Hoje é uma quarta da semana 2: a 1 fechou, a 2 está andando.
    linhas = ciclo.montar_as_semanas(faixas, [3, 1], dt.date(2026, 9, 16))
    assert linhas[0]["estado"] == "fechada" and linhas[0]["cumpriu"] is False
    assert linhas[1]["estado"] == "andando" and linhas[1]["cumpriu"] is None


def test_semana_futura_e_marcada_como_futura():
    faixas = placar.semanas_do_ciclo(CARTAO)
    linhas = ciclo.montar_as_semanas(faixas, [0, 0], dt.date(2026, 9, 1))
    assert [l["estado"] for l in linhas] == ["futura", "futura"]
    assert all(l["cumpriu"] is None for l in linhas)


# ------------------------------------------------------------------ a tela


@respx.mock
def test_a_tela_abre_com_as_quatorze_semanas():
    respx.get(ALUNOS_LISTA).mock(return_value=httpx.Response(200, json=[]))
    resposta = _dentro().get(reverse("ciclo"))
    assert resposta.status_code == 200
    assert len(resposta.context["semanas"]) == 14
    html = resposta.content.decode()
    assert "O calendário do ciclo" in html
    assert "Preparação" in html and "Recuperação" in html


@respx.mock
def test_a_tela_abre_mesmo_sem_a_alunos_e_diz_isso():
    respx.get(ALUNOS_LISTA).mock(return_value=httpx.Response(503))
    resposta = _dentro().get(reverse("ciclo"))
    assert resposta.status_code == 200
    assert resposta.context["nao_consigo_contar"]
    assert "Não consegui perguntar" in resposta.content.decode()


@respx.mock
def test_o_placar_leva_ate_o_calendario():
    respx.get(ALUNOS_LISTA).mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{ALUNOS}/pre-matriculas").mock(
        return_value=httpx.Response(200, json=[])
    )
    html = _dentro().get(reverse("placar")).content.decode()
    assert f'href="{reverse("ciclo")}"' in html


@respx.mock
def test_o_placar_nao_fala_mais_em_linha_reta():
    """A tela mudou de régua, e o texto dela tinha de mudar junto.

    Um número julgado pela curva e explicado como linha reta é a tela mentindo
    com todas as letras certas.
    """
    from pathlib import Path

    caminho = Path(placar.__file__).parent / "templates" / "admin" / "placar.html"
    assert "linha reta" not in caminho.read_text(encoding="utf-8")


@respx.mock
def test_sem_cracha_a_tela_nao_abre():
    respx.get(SESSAO).mock(
        return_value=httpx.Response(200, json={"autenticado": False})
    )
    assert Client().get(reverse("ciclo")).status_code != 200
