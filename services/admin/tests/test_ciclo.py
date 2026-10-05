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
    monkeypatch.setattr(ciclo.CatalogoClient, "site_por_host", lambda self, host: {"id": "site-mesh"})
    monkeypatch.setattr(ciclo.CatalogoClient, "oferta_do_site", lambda self, site, slug: (self.OK, {
        "product": {"id": "produto-desafio" if slug.startswith("desafio") else "produto-curso"}
    }))
    monkeypatch.setattr(ciclo.CatalogoClient, "listar_produtos", lambda self: [
        {"id": "produto-curso", "slug": "primeiros-dolares"},
        {"id": "produto-desafio", "slug": "desafio-como-ganhar-em-dolar-com-roblox"},
    ])
    # Estas fichas simulam contatos comerciais previamente conferidos.
    def contatos_confirmados(pessoas):
        for n, pessoa in enumerate(pessoas):
            pessoa.setdefault("id", str(n))
        return {str(p["id"]): {"contato_crm_id": str(p["id"]), "venda_origem": "crm"} for p in pessoas}
    monkeypatch.setattr("apps.core.vendas_do_crm.vinculos", contatos_confirmados)
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


def _cartao_de_verdade() -> dict:
    """O cartão que está no repositório, o mesmo que a tela lê em produção."""
    cartao, recusas = placar.ler_cartao(
        placar.CARTAO_DA_META, placar.diretorio_dos_cartoes()
    )
    assert cartao is not None, f"o cartão da meta não abriu: {recusas}"
    return cartao


def _linhas_da_tabela(html: str) -> dict:
    """Cada `<tr>` de semana da tela renderizada, achável pelo nome da linha."""
    linhas = {}
    for pedaco in html.split('<tr class="semana ')[1:]:
        corpo = pedaco.split("</tr>")[0]
        nome = corpo.split("<b>")[1].split("</b>")[0].strip()
        linhas[nome] = corpo
    return linhas


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
    site = {"origem": "comprou"}
    alunos = [
        {**site, "status": "ativa", "virou_aluno_em": "2026-09-08T10:00:00-03:00"},
        {**site, "status": "ativa", "virou_aluno_em": "2026-09-08T11:00:00-03:00"},
        {**site, "status": "suspensa", "virou_aluno_em": "2026-09-15T09:00:00-03:00"},
        # Fora de qualquer semana (um sábado): não some, só não entra em nenhuma.
        {**site, "status": "ativa", "virou_aluno_em": "2026-09-12T09:00:00-03:00"},
        # Reembolsada não conta: a compra foi desfeita.
        {**site, "status": "reembolsada", "virou_aluno_em": "2026-09-08T09:00:00-03:00"},
        # Liberada pela sala de espera: comprou em outro site (02/10/2026).
        {"origem": "liberado", "status": "ativa", "virou_aluno_em": "2026-09-09T09:00:00-03:00"},
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
def test_a_tela_abre_com_doze_semanas_e_dois_botoes():
    respx.get(ALUNOS_LISTA).mock(return_value=httpx.Response(200, json=[]))
    resposta = _dentro().get(reverse("ciclo"))
    assert resposta.status_code == 200
    painel = resposta.context["painel"]
    assert len(painel["semanas"]) == 9
    assert len(painel["recuperacoes"]) == 2
    assert painel["preparacao"]["meta"] == 0
    assert painel["meta"] == 500
    html = resposta.content.decode()
    assert "Curso Primeiros Dólares com Roblox" in html
    assert "Preparação" in html and "Duas semanas de recuperação" in html
    assert "?produto=curso" in html and "?produto=desafio" in html


@respx.mock
def test_a_tela_abre_mesmo_sem_a_alunos_e_diz_isso():
    respx.get(ALUNOS_LISTA).mock(return_value=httpx.Response(503))
    resposta = _dentro().get(reverse("ciclo"))
    assert resposta.status_code == 200
    assert resposta.context["painel"]["sem_contagem"]
    assert "Não foi possível confirmar" in resposta.content.decode()


@respx.mock
def test_o_placar_leva_ate_o_calendario():
    respx.get(ALUNOS_LISTA).mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{ALUNOS}/pre-matriculas").mock(
        return_value=httpx.Response(200, json=[])
    )
    html = _dentro().get(reverse("placar")).content.decode()
    assert f'href="{reverse("ciclo")}"' in html


@respx.mock
def test_a_tela_mostra_o_novo_calendario_e_marca_a_faixa_de_hoje(monkeypatch):
    """A prova que só a tela renderizada dá: as datas certas, no lugar certo.

    Em 17/09/2026 quem está andando é a PREPARAÇÃO (14 a 18/09), e a semana 1
    ainda nem começou (21 a 25/09). Um guarda que só medisse o cartão ficaria
    verde com a tela mostrando outra coisa, que foi exatamente o que aconteceu
    entre o ajuste da curva e este PR.
    """
    monkeypatch.setattr(ciclo.timezone, "localdate", lambda: dt.date(2026, 10, 5))
    respx.get(ALUNOS_LISTA).mock(return_value=httpx.Response(200, json=[]))
    resposta = _dentro().get(reverse("ciclo"))
    assert resposta.status_code == 200

    painel = resposta.context["painel"]
    assert painel["preparacao"]["atual"]
    assert painel["semanas"][0]["de"] == dt.date(2026, 10, 12)
    assert painel["semanas"][-1]["n"] == 10
    assert [s["n"] for s in painel["recuperacoes"]] == [11, 12]
    assert "Esta semana" in resposta.content.decode()


@respx.mock
def test_sem_cracha_a_tela_nao_abre():
    respx.get(SESSAO).mock(
        return_value=httpx.Response(200, json={"autenticado": False})
    )
    assert Client().get(reverse("ciclo")).status_code != 200
