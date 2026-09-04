"""O placar, `/admin/placar/`: o andar zero do painel de gestão.

Reformulado em 03/09/2026 à noite (registro `20260903-036`): a meta virou
"quantas pessoas compraram neste mês", com a meta grande por cima (de 0 para
500 somadas de 03/09 a 15/12/2026), contadas pela data em que cada pessoa
virou aluna (`virou_aluno_em`, o campo do Rito de Contrato do PR #933).

O que estes guardas protegem (plano: `docs/decisoes/PLANO-PAINEL-DE-GESTAO.md`):

1. **Número sem cartão não aparece.** Cartão ausente ou inválido ⇒ a página
   abre, diz o que faltou, e o número da meta NÃO está no HTML. É a regra
   fail-closed do §2, e o caso que DEVE reprovar está aqui.
2. **Os cartões do repositório são válidos.** Quem escrever um cartão torto
   descobre no PR, não na tela do mantenedor.
3. **"Não sei" nunca vira zero.** A `alunos` fora do ar ⇒ "não consigo contar";
   lista sem o campo novo ⇒ "ainda não traz a data"; ficha sem data ⇒ contada
   à parte e dita na tela. Nenhum "0" inventado.
4. **A contagem é pela data certa**: `virou_aluno_em` em America/Sao_Paulo,
   nunca `comprou_em`; antes da partida não conta; reembolsada não conta.
5. **A conta do veredito é a que o plano descreve**, e não outra: linha reta
   da partida ao alvo, sem índice. E a barra do mês deriva a meta do mês da
   mesma linha, quando o mantenedor não fixou uma.
6. **O par sem fonte se declara**, em vez de mostrar número inventado.
7. **A porta continua sendo a porta**, e a visão geral leva até aqui.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.core import placar

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"

ALUNOS = "http://alunos:8000/api/alunos"
FILA = f"{ALUNOS}/pre-matriculas"
ALUNOS_LISTA = f"{ALUNOS}/matriculas"


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


def _ficha(status="ativa", virou_aluno_em="omitido", **extra):
    ficha = {"status": status, **extra}
    if virou_aluno_em != "omitido":
        ficha["virou_aluno_em"] = virou_aluno_em
    return ficha


def _a_escola_responde(fichas: list[dict]):
    respx.get(FILA, params={"status": "aguardando"}).mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(FILA, params={"status": "recusada"}).mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(ALUNOS_LISTA).mock(return_value=httpx.Response(200, json=fichas))


def _a_escola_caiu():
    respx.get(FILA).mock(side_effect=httpx.ConnectError("recusou"))
    respx.get(ALUNOS_LISTA).mock(side_effect=httpx.ConnectError("recusou"))


# ---------------------------------------------------------------- os cartões


def test_os_cartoes_do_repositorio_sao_validos():
    """Cartão torto reprova aqui, não na tela do mantenedor."""
    pasta = placar.diretorio_dos_cartoes()
    assert pasta is not None, (
        "a pasta painel/cartoes/ não foi encontrada — em produção ela vem em "
        "painel_embutido/, num checkout em painel/. Sem ela o placar abre sem número."
    )
    for arquivo in sorted(pasta.glob("*.json")):
        cartao, problemas = placar.ler_cartao(arquivo.stem, pasta)
        assert cartao is not None, f"{arquivo.name}: {problemas}"


def test_a_meta_e_o_par_apontam_um_para_o_outro():
    pasta = placar.diretorio_dos_cartoes()
    meta, _ = placar.ler_cartao(placar.CARTAO_DA_META, pasta)
    mes, _ = placar.ler_cartao(placar.CARTAO_DO_MES, pasta)
    par, _ = placar.ler_cartao(placar.CARTAO_DO_PAR, pasta)
    assert meta["par"] == placar.CARTAO_DO_PAR
    assert mes["par"] == placar.CARTAO_DO_PAR
    assert par["par"] == placar.CARTAO_DA_META
    assert meta["andar"] == 0 and mes["andar"] == 0 and par["andar"] == 0


def test_a_meta_1_e_a_que_o_mantenedor_decidiu():
    """1000 somadas, de 03/09 a 15/12/2026, partindo de 0.

    O número fica CRAVADO aqui de propósito, e este é o único lugar do
    repositório onde ele deve estar duas vezes: o papel deste guarda é afirmar
    que o cartão diz o que o mantenedor decidiu. Um teste que perguntasse o
    alvo ao próprio cartão passaria com qualquer alvo, inclusive um trocado por
    engano num rebase.

    A meta nasceu 500 em 03/09/2026 (registro `20260903-036`) e foi dobrada
    para 1000 por ele em 04/09/2026, junto com a curva de crescimento semanal
    (`DECISAO-o-calendario-do-ciclo.md`).
    """
    meta, _ = placar.ler_cartao(placar.CARTAO_DA_META)
    assert (meta["partida"], meta["alvo"]) == (0, 1000)
    assert (meta["partida_em"], meta["ate"]) == ("2026-09-03", "2026-12-15")
    assert meta["acao"], "número de resultado no andar 0 diz o que fazer"


@pytest.mark.parametrize(
    "defeito, trecho",
    [
        ({"par": None}, "par"),
        ({"tipo": "composto"}, "tipo"),
        ({"andar": "0"}, "andar"),
        ({"componentes": ["a", "b"]}, "composto"),
        ({"fonte": None}, "sem_fonte_porque"),
        ({"versao": "1"}, "versao"),
        ({"acao": None}, "acao"),
        ({"direcao": "para-cima"}, "direcao"),
        ({"alvo_do_mes": "50"}, "alvo_do_mes"),
        ({"alvo": None}, "os quatro juntos"),
        (
            {
                "alvo": 200,
                "ate": "2026-01-01",
                "partida": 10,
                "partida_em": "2026-06-01",
            },
            "depois",
        ),
    ],
)
def test_o_validador_reprova_cada_defeito(defeito, trecho):
    """O caso que DEVE reprovar, um por regra do plano (§2)."""
    base = json.loads(
        (
            Path(placar.diretorio_dos_cartoes()) / f"{placar.CARTAO_DA_META}.json"
        ).read_text(encoding="utf-8")
    )
    assert not placar.validar(base)
    torto = {**base, **defeito}
    problemas = placar.validar(torto)
    assert problemas, f"o validador engoliu {defeito}"
    assert any(trecho in p for p in problemas), problemas


# ------------------------------------------------------------------ a contagem


PARTIDA = dt.date(2026, 9, 3)
HOJE = dt.date(2026, 9, 20)


def test_conta_pela_data_em_que_virou_aluna_e_nunca_pela_data_digitada():
    fichas = [
        _ficha(virou_aluno_em="2026-09-10T15:00:00-03:00", comprou_em="2026-07-01"),
        _ficha(virou_aluno_em="2026-09-15T15:00:00-03:00"),
        _ficha(status="suspensa", virou_aluno_em="2026-09-16T15:00:00-03:00"),
        _ficha(status="encerrada", virou_aluno_em="2026-09-17T15:00:00-03:00"),
    ]
    r = placar.contar_compras(fichas, PARTIDA, HOJE)
    assert r["ciclo"] == 4 and r["mes"] == 4
    assert r["sem_data"] == 0 and r["reembolsadas"] == 0
    assert r["total_de_alunos"] == 2


def test_quem_virou_aluna_antes_da_partida_nao_conta():
    """A turma liberada em lote em 02/09 é venda de outros meses."""
    fichas = [
        _ficha(virou_aluno_em="2026-09-02T23:59:00-03:00"),
        _ficha(virou_aluno_em="2026-09-03T00:01:00-03:00"),
    ]
    r = placar.contar_compras(fichas, PARTIDA, HOJE)
    assert r["ciclo"] == 1 and r["mes"] == 1
    assert r["total_de_alunos"] == 2, "no total da escola as duas contam"


def test_o_dia_e_o_de_sao_paulo_e_nao_o_de_utc():
    """23h de 02/09 em UTC ainda é 02/09 às 20h em São Paulo; 02:00Z de 03/09 é 23h de 02/09."""
    assert placar.dia_em_sao_paulo("2026-09-03T02:00:00Z") == dt.date(2026, 9, 2)
    assert placar.dia_em_sao_paulo("2026-09-03T03:00:00Z") == dt.date(2026, 9, 3)
    assert (
        placar.dia_em_sao_paulo("2026-09-03T10:00:00") is None
    ), "sem fuso não se adivinha"
    assert placar.dia_em_sao_paulo(None) is None
    assert placar.dia_em_sao_paulo("isso não é data") is None


def test_o_mes_zera_no_dia_1_e_o_ciclo_soma():
    hoje = dt.date(2026, 10, 5)
    fichas = [
        _ficha(virou_aluno_em="2026-09-20T12:00:00-03:00"),
        _ficha(virou_aluno_em="2026-10-02T12:00:00-03:00"),
    ]
    r = placar.contar_compras(fichas, PARTIDA, hoje)
    assert r["ciclo"] == 2 and r["mes"] == 1


def test_reembolsada_nao_e_compra_e_ficha_sem_data_e_dita_a_parte():
    fichas = [
        _ficha(virou_aluno_em="2026-09-10T12:00:00-03:00"),
        _ficha(status="reembolsada", virou_aluno_em="2026-09-11T12:00:00-03:00"),
        _ficha(virou_aluno_em=None),
    ]
    r = placar.contar_compras(fichas, PARTIDA, HOJE)
    assert r["ciclo"] == 1
    assert r["reembolsadas"] == 1
    assert r["sem_data"] == 1


def test_lista_sem_o_campo_novo_nao_vira_zero():
    """A `alunos` ainda sem o PR do rito: a tela diz que a data não chegou."""
    fichas = [_ficha(), _ficha(status="suspensa")]
    r = placar.contar_compras(fichas, PARTIDA, HOJE)
    assert r["ciclo"] is None and r["mes"] is None
    assert r["campo_ausente"] is True
    assert r["total_de_alunos"] == 1, "o total de alunos continua contável"


def test_lista_ausente_nao_vira_zero():
    r = placar.contar_compras(None, PARTIDA, HOJE)
    assert r["ciclo"] is None and r["total_de_alunos"] is None
    assert r["campo_ausente"] is False


def test_lista_vazia_e_zero_de_verdade():
    r = placar.contar_compras([], PARTIDA, HOJE)
    assert r["ciclo"] == 0 and r["mes"] == 0 and r["campo_ausente"] is False


# ------------------------------------------------------------------- a conta


META = {
    "alvo": 500,
    "ate": "2026-12-15",
    "partida": 0,
    "partida_em": "2026-09-03",
}


def test_sem_alvo_o_veredito_e_aguardar_o_mantenedor():
    r = placar.calcular_placar({"alvo": None}, 42, HOJE)
    assert r["veredito"] == "sem-alvo"
    assert r["x"] == 42


def test_sem_contagem_o_veredito_e_nao_consigo_contar():
    r = placar.calcular_placar(META, None, HOJE)
    assert r["veredito"] == "nao-consigo-contar"
    assert r["x"] is None


def test_a_linha_reta_decide_ganhando_e_perdendo():
    # 103 dias de ciclo; em 09/10 passaram 36: esperado = round(500 * 36/103) = 175.
    dia = dt.date(2026, 10, 9)
    assert placar.esperado_em(META, dia) == 175
    assert placar.calcular_placar(META, 175, dia)["veredito"] == "ganhando"
    assert placar.calcular_placar(META, 174, dia)["veredito"] == "perdendo"
    r = placar.calcular_placar(META, 100, dia)
    assert r["distancia"] == 400
    assert r["dias_restantes"] == 67
    assert r["ritmo_por_semana"] == pytest.approx(400 / (67 / 7), abs=0.1)


def test_no_dia_da_partida_zero_esta_ganhando():
    assert placar.calcular_placar(META, 0, PARTIDA)["veredito"] == "ganhando"


def test_meta_cumprida_e_prazo_vencido():
    assert placar.calcular_placar(META, 500, HOJE)["veredito"] == "cumprida"
    depois = dt.date(2026, 12, 20)
    assert placar.calcular_placar(META, 499, depois)["veredito"] == "vencida"
    assert placar.calcular_placar(META, 600, depois)["veredito"] == "cumprida"


def test_a_meta_do_mes_e_a_fatia_da_linha_reta_quando_nao_ha_alvo_fixo():
    # Outubro inteiro: esperado(31/10) - esperado(30/09) = round(500*58/103) - round(500*27/103) = 282 - 131 = 151.
    hoje = dt.date(2026, 10, 10)
    r = placar.calcular_o_mes({"alvo_do_mes": None}, META, 40, hoje)
    assert r["alvo"] == 151 and r["alvo_derivado"] is True
    assert r["mes"] == "10/2026"
    # 10 de 31 dias: esperado = round(151 * 10/31) = 49; 40 < 49 ⇒ perdendo.
    assert r["esperado_hoje"] == 49
    assert r["veredito"] == "perdendo"
    assert (
        placar.calcular_o_mes({"alvo_do_mes": None}, META, 49, hoje)["veredito"]
        == "ganhando"
    )


def test_a_meta_do_mes_fixada_pelo_mantenedor_vence_a_derivada():
    r = placar.calcular_o_mes({"alvo_do_mes": 30}, META, 30, dt.date(2026, 10, 10))
    assert r["alvo"] == 30 and r["alvo_derivado"] is False
    assert r["veredito"] == "cumprida"


def test_a_barra_sem_contagem_diz_que_nao_consegue_contar():
    r = placar.calcular_o_mes({"alvo_do_mes": None}, META, None, HOJE)
    assert r["veredito"] == "nao-consigo-contar"


# -------------------------------------------------------------------- a tela


@respx.mock
def test_a_pagina_mostra_a_barra_do_mes_e_a_meta_do_ciclo(monkeypatch):
    monkeypatch.setattr(placar.timezone, "localdate", lambda: dt.date(2026, 9, 20))
    _a_escola_responde(
        [
            _ficha(virou_aluno_em="2026-09-10T12:00:00-03:00"),
            _ficha(virou_aluno_em="2026-09-02T12:00:00-03:00"),
            _ficha(virou_aluno_em=None),
            _ficha(status="reembolsada", virou_aluno_em="2026-09-12T12:00:00-03:00"),
        ]
    )
    resposta = _dentro().get(reverse("placar"))
    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert 'class="hero-numero">1<' in html, "só a que virou aluna depois da partida"
    assert "meta do mês" in html
    # PERGUNTA o alvo ao cartão em vez de cravá-lo: este teste mede se o número
    # CHEGA à tela, e não qual é o número. Quem guarda qual é o número é
    # `test_a_meta_1_e_a_que_o_mantenedor_decidiu`, um só, de propósito.
    meta_do_ciclo, _ = placar.ler_cartao(placar.CARTAO_DA_META)
    assert f"para <b>{meta_do_ciclo['alvo']}</b>" in html
    assert "1 ficha sem data" in html
    assert "1 reembolsada" in html
    assert "Sem dados ainda" in html, "o par sem fonte precisa se declarar"
    assert "aguardando você" not in html


@respx.mock
def test_a_escola_fora_do_ar_nao_vira_zero():
    _a_escola_caiu()
    html = _dentro().get(reverse("placar")).content.decode()
    assert "Não consigo contar agora" in html
    assert 'class="hero-numero">0<' not in html


@respx.mock
def test_a_lista_sem_o_campo_novo_diz_isso_em_vez_de_zero():
    _a_escola_responde([_ficha(), _ficha()])
    html = _dentro().get(reverse("placar")).content.decode()
    assert "ainda não traz a data" in html
    assert 'class="hero-numero"' not in html


@respx.mock
def test_sem_cartao_valido_o_numero_nao_aparece(tmp_path, monkeypatch):
    """A regra fail-closed do plano (§2), medida: cartão inválido, número ausente."""
    pasta = tmp_path / "cartoes"
    pasta.mkdir()
    torto = {"nome": placar.CARTAO_DA_META, "tipo": "resultado"}
    (pasta / f"{placar.CARTAO_DA_META}.json").write_text(
        json.dumps(torto), encoding="utf-8"
    )
    monkeypatch.setattr(placar, "diretorio_dos_cartoes", lambda: pasta)
    _a_escola_responde([_ficha(virou_aluno_em="2026-09-10T12:00:00-03:00")])
    resposta = _dentro().get(reverse("placar"))
    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert "falta o cartão" in html
    assert 'class="hero-numero"' not in html, "número desenhado sem cartão válido"
    assert not respx.calls.call_count or all(
        "alunos:8000" not in str(c.request.url) for c in respx.calls
    ), "sem cartão válido a tela nem pergunta à alunos: número que não vai aparecer não se busca"


@respx.mock
def test_a_visao_geral_leva_ate_o_placar():
    _a_escola_responde([_ficha()])
    html = _dentro().get(reverse("visao_geral")).content.decode()
    assert reverse("placar") in html


@respx.mock
def test_sem_cracha_a_pagina_nao_abre():
    respx.get(SESSAO).mock(
        return_value=httpx.Response(200, json={"autenticado": False})
    )
    assert Client().get(reverse("placar")).status_code != 200
