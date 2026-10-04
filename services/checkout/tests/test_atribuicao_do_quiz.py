"""Compra depois do quiz: a atribuição (v, fmt, seg, src, med, cpg, ctv, qa, qz)
vem na URL da página de dados, entra na Session, é copiada ao Order e dá a
leitura de pedidos pagos por versão/campanha/dia sem contar reenvio duas vezes."""

import pytest

from apps.pedidos.atribuicao import separar_atribuicao
from apps.pedidos.management.commands.consume_eventos import aplicar
from apps.pedidos.models import FatoAplicado, Order, Session
from apps.pedidos.relatorio import pagos_do_quiz
from conftest import HOST_A, SLUG, aprovado_v1

QA = "7b0c2f9e-3f0a-4c1e-9d52-0a1b2c3d4e5f"
ATRIB = {
    "v": "v2",
    "fmt": "direto",
    "seg": "iniciante",
    "src": "tiktok",
    "med": "video",
    "cpg": "maio-roblox",
    "ctv": "criativo-3",
    "qa": QA,
    "qz": "low-ticket",
}


def _sessao(api, utm):
    resp = api.post("/api/checkout/sessoes", {"offer_slug": SLUG, "utm": utm})
    assert resp.status_code == 201, resp.content
    return resp.json()


def _pedido(api, sessao):
    resp = api.post(
        f"/api/checkout/sessoes/{sessao['id']}/pedido",
        {"customer": {"email": "c@exemplo.com", "name": "C Teste", "phone": "11999999999", "cpf": "40827365144"}, "method": "pix"},
    )
    assert resp.status_code == 201, resp.content
    return Order.objects.get(pk=resp.json()["order_id"])


@pytest.mark.django_db
def test_pagina_de_dados_embute_as_utms_e_os_nove_parametros(client, rede):
    consulta = {**ATRIB, "utm_source": "tiktok", "lixo": "x", "cpg<": "y"}
    resp = client.get(f"/{SLUG}/", consulta, HTTP_HOST=HOST_A)
    assert resp.status_code == 200
    html = resp.content.decode()
    assert 'id="atribuicao"' in html
    for chave, valor in ATRIB.items():
        assert f'"{chave}": "{valor}"' in html
    assert '"utm_source": "tiktok"' in html
    assert "lixo" not in html


@pytest.mark.django_db
def test_sessao_e_pedido_guardam_a_atribuicao(api, rede):
    sessao = _sessao(api, {**ATRIB, "utm_campaign": "maio", "x": "ignorado?"})
    s = Session.objects.get(pk=sessao["id"])
    assert s.contexto == ATRIB
    assert s.utm["utm_campaign"] == "maio"
    assert not (set(ATRIB) & set(s.utm))
    pedido = _pedido(api, sessao)
    assert pedido.contexto == ATRIB


@pytest.mark.django_db
def test_valor_fora_do_limite_ou_do_charset_e_descartado(api, rede):
    sessao = _sessao(
        api,
        {"v": "v1", "cpg": "a" * 101, "ctv": "<script>", "qa": ["x"], "seg": "ação 1"},
    )
    s = Session.objects.get(pk=sessao["id"])
    assert s.contexto == {"v": "v1", "seg": "ação 1"}


@pytest.mark.django_db
def test_sem_atribuicao_nada_muda(api, rede):
    sessao = _sessao(api, {})
    assert Session.objects.get(pk=sessao["id"]).contexto == {}
    assert _pedido(api, sessao).contexto == {}


def _pago(api, **atrib):
    pedido = _pedido(api, _sessao(api, {**ATRIB, **atrib}))
    return pedido


@pytest.mark.django_db
def test_agrupamento_de_pagos_nao_duplica_reenvio(api, rede):
    p1 = _pago(api)
    p2 = _pago(api)
    p3 = _pago(api, cpg="junho-roblox")
    outro_quiz = _pago(api, qz="outro-quiz")  # pago, mas de outro quiz
    for p in (p1, p2, p3, outro_quiz):
        assert aplicar(aprovado_v1(p, mp_payment_id=f"mp-{p.id}")) is True
    # reenvio do mesmo webhook (mesma identidade lógica): não aplica de novo
    assert aplicar(aprovado_v1(p1, mp_payment_id=f"mp-{p1.id}")) is False
    assert aplicar(aprovado_v1(p1, mp_payment_id=f"mp-{p1.id}")) is False
    assert FatoAplicado.objects.count() == 4
    # Aguardando, fora da conta (aberto depois: um pedido já aberto do mesmo
    # cliente e oferta seria encerrado quando outro é pago).
    pendente = _pago(api)
    pendente.refresh_from_db()
    assert pendente.status == "aguardando_pagamento"

    linhas = pagos_do_quiz("low-ticket")
    por_cpg = {l["cpg"]: l for l in linhas}
    assert set(por_cpg) == {"maio-roblox", "junho-roblox"}
    assert por_cpg["maio-roblox"]["pedidos"] == 2
    assert por_cpg["maio-roblox"]["receita_cents"] == 2 * p1.total_cents
    assert por_cpg["junho-roblox"]["pedidos"] == 1
    assert por_cpg["maio-roblox"]["v"] == "v2"
    assert por_cpg["maio-roblox"]["ctv"] == "criativo-3"
    assert por_cpg["maio-roblox"]["seg"] == "iniciante"
    assert por_cpg["maio-roblox"]["fmt"] == "direto"
    assert por_cpg["maio-roblox"]["dia"] is not None
    assert pagos_do_quiz("low-ticket", site_id="outro-site") == []
    assert sum(l["pedidos"] for l in pagos_do_quiz("outro-quiz")) == 1


@pytest.mark.django_db
def test_pedido_de_teste_nao_entra_nas_vendas_do_quiz(api, rede):
    real = _pago(api)
    teste = _pago(api)
    reembolsado_de_teste = _pago(api)
    for p in (real, teste, reembolsado_de_teste):
        assert aplicar(aprovado_v1(p, mp_payment_id=f"mp-{p.id}")) is True
    # Pedido que nasceu contra o sandbox do provedor: dinheiro de mentira.
    Order.objects.filter(pk__in=[teste.pk, reembolsado_de_teste.pk]).update(em_teste=True)
    Order.objects.filter(pk=reembolsado_de_teste.pk).update(status="reembolsado")

    linhas = pagos_do_quiz("low-ticket")

    assert sum(l["pedidos"] for l in linhas) == 1
    assert sum(l["receita_cents"] for l in linhas) == real.total_cents
    assert sum(l["reembolsos"] for l in linhas) == 0
    assert sum(l["reembolsado_cents"] for l in linhas) == 0


def test_op_e_est_do_atendimento_entram_na_atribuicao_e_nao_nas_utms():
    utm, contexto = separar_atribuicao(
        {"op": "op-1", "est": "retomada-quiz", "utm_source": "x", "lixo": "y"}
    )
    assert contexto == {"op": "op-1", "est": "retomada-quiz"}
    assert utm == {"utm_source": "x", "lixo": "y"}
