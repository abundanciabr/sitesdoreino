"""O placar, `/admin/placar/`: o andar zero do painel de gestão.

Reformulado em 03/09/2026 à noite (registro `20260903-036`): a meta virou
"quantas pessoas compraram neste mês", com a meta grande por cima (de 0 para
500 somadas de 03/09 a 15/12/2026), contadas pela data em que cada pessoa
virou aluna.

O que estes guardas protegem:

1. **Número sem cartão não aparece.** Cartão ausente ⇒ a página abre, diz o
   que faltou, e o número da meta NÃO está no HTML. Cartão com defeito de
   formato ⇒ o número aparece e o defeito vem como aviso.
2. **"Não sei" nunca vira zero.** A `alunos` fora do ar ⇒ "não consigo contar";
   lista sem o campo novo ⇒ "ainda não traz a data"; ficha sem data ⇒ contada
   à parte e dita na tela. Nenhum "0" inventado.
3. **A contagem é pela data certa**: `virou_aluno_em` em America/Sao_Paulo,
   nunca `comprou_em`; antes da partida não conta; reembolsada não conta.
   E **só a venda do nosso site conta** (02/10/2026): quem foi liberado pela
   sala de espera comprou em outro site e fica de fora.
4. **A conta do veredito é a que o plano descreve**, e não outra: linha reta
   da partida ao alvo, sem índice. E a barra do mês deriva a meta do mês da
   mesma linha, quando o mantenedor não fixou uma.
5. **O par sem fonte se declara**, em vez de mostrar número inventado.
6. **A porta continua sendo a porta**, e a visão geral leva até aqui.
7. **Todo link da capa aponta para uma rota que existe**, inclusive nos ramos
   que nenhum teste abre.
"""

from __future__ import annotations

import datetime as dt
import json
import re
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


def _ficha(status="ativa", virou_aluno_em="omitido", origem="comprou", **extra):
    ficha = {"status": status, "origem": origem, **extra}
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


def test_so_conta_venda_feita_pelo_nosso_site():
    """Correção do mantenedor em 02/10/2026: o placar mostrava 69 alunas num
    site que nunca vendeu nada. Eram as liberadas pela sala de espera, que
    compraram em OUTRO site. Liberada e administrativa não são venda do site,
    nem no ciclo, nem no mês, nem nas reembolsadas, nem nas sem data."""
    fichas = [
        _ficha(virou_aluno_em="2026-09-10T12:00:00-03:00"),
        _ficha(origem="liberado", virou_aluno_em="2026-09-10T12:00:00-03:00"),
        _ficha(origem="liberado", virou_aluno_em="2026-10-01T12:00:00-03:00"),
        _ficha(origem="administrativo", virou_aluno_em="2026-09-11T12:00:00-03:00"),
        _ficha(origem="liberado", status="reembolsada", virou_aluno_em="2026-09-12T12:00:00-03:00"),
        _ficha(origem="liberado", virou_aluno_em=None),
        _ficha(origem="origem-que-ainda-nao-existe", virou_aluno_em="2026-09-13T12:00:00-03:00"),
    ]
    r = placar.contar_compras(fichas, PARTIDA, HOJE)
    assert r["ciclo"] == 1
    assert r["reembolsadas"] == 0 and r["sem_data"] == 0
    assert r["total_de_alunos"] == 6, "o total da escola continua sendo todo mundo ativo"


def test_so_liberadas_no_ciclo_e_zero_de_verdade():
    """É o retrato de hoje: ninguém comprou pelo site, então é zero, e não 69."""
    fichas = [
        _ficha(origem="liberado", virou_aluno_em="2026-09-10T12:00:00-03:00")
        for _ in range(69)
    ]
    r = placar.contar_compras(fichas, PARTIDA, HOJE)
    assert r["ciclo"] == 0 and r["mes"] == 0 and r["campo_ausente"] is False


def test_lista_sem_a_origem_nao_vira_zero_nem_soma_tudo():
    """Sem a origem não se separa o site da sala de espera: não sei, e não 0."""
    fichas = [{"status": "ativa", "virou_aluno_em": "2026-09-10T12:00:00-03:00"}]
    r = placar.contar_compras(fichas, PARTIDA, HOJE)
    assert r["ciclo"] is None and r["campo_ausente"] is True


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
    # CHEGA à tela, e não qual é o número.
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


def _pasta_com(tmp_path, cartoes: dict[str, dict]) -> Path:
    pasta = tmp_path / "cartoes"
    pasta.mkdir()
    for nome, dados in cartoes.items():
        (pasta / f"{nome}.json").write_text(json.dumps(dados), encoding="utf-8")
    return pasta


@respx.mock
def test_sem_cartao_o_numero_nao_aparece(tmp_path, monkeypatch):
    """Cartão ausente: a página abre, diz o que faltou, e não desenha número."""
    pasta = _pasta_com(tmp_path, {})
    monkeypatch.setattr(placar, "diretorio_dos_cartoes", lambda: pasta)
    _a_escola_responde([_ficha(virou_aluno_em="2026-09-10T12:00:00-03:00")])
    resposta = _dentro().get(reverse("placar"))
    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert "falta o cartão" in html
    assert 'class="hero-numero"' not in html, "número desenhado sem cartão"
    assert not respx.calls.call_count or all(
        "alunos:8000" not in str(c.request.url) for c in respx.calls
    ), "sem cartão a tela nem pergunta à alunos: número que não vai aparecer não se busca"


@respx.mock
def test_cartao_torto_mostra_o_numero_com_aviso(tmp_path, monkeypatch):
    """Cartão com defeito de formato: o número aparece, e o defeito vem como aviso."""
    monkeypatch.setattr(placar.timezone, "localdate", lambda: dt.date(2026, 9, 20))
    meta, _ = placar.ler_cartao(placar.CARTAO_DA_META)
    mes, _ = placar.ler_cartao(placar.CARTAO_DO_MES)
    pasta = _pasta_com(
        tmp_path,
        {
            placar.CARTAO_DA_META: {**meta, "alvo": "quinhentos"},
            placar.CARTAO_DO_MES: {**mes, "alvo_do_mes": "dez"},
        },
    )
    monkeypatch.setattr(placar, "diretorio_dos_cartoes", lambda: pasta)
    _a_escola_responde([_ficha(virou_aluno_em="2026-09-10T12:00:00-03:00")])
    resposta = _dentro().get(reverse("placar"))
    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert 'class="hero-numero">1<' in html, "o cartão torto sumiu com o número"
    assert "<b>1</b> desde a partida" in html
    assert "falta o cartão" not in html
    assert "defeito de formato" in html
    assert "`alvo` é um inteiro sem aspas" in html
    assert "`alvo_do_mes` é um inteiro sem aspas" in html


@respx.mock
def test_a_visao_geral_leva_ate_o_placar():
    _a_escola_responde([_ficha()])
    html = _dentro().get(reverse("visao_geral")).content.decode()
    assert reverse("placar") in html


def test_todo_link_da_pagina_aponta_para_rota_que_existe():
    """Um `{% url %}` num ramo que nenhum teste abre só quebra em produção, no dia
    em que o ramo abrir. Aqui todos são resolvidos, abertos ou não."""
    tela = Path(placar.__file__).parent / "templates" / "admin" / "placar.html"
    fonte = tela.read_text(encoding="utf-8")
    nomes = set(re.findall(r"\{% url '([\w-]+)' %\}", fonte))
    assert nomes, "a capa tem links, e este guarda não os está achando"
    for nome in sorted(nomes):
        reverse(nome)


@respx.mock
def test_sem_cracha_a_pagina_nao_abre():
    respx.get(SESSAO).mock(
        return_value=httpx.Response(200, json={"autenticado": False})
    )
    assert Client().get(reverse("placar")).status_code != 200
