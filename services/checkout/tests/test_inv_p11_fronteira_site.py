# tests/test_inv_p11_fronteira_site.py  # [RECEITA:R5 v1]
# [INV-P11] O site vem do Host (CONV-SITE), nunca do payload. Host desconhecido
# é 404 — nunca "cai" num site padrão. Sessão, pedido e oferta de um site jamais
# aparecem em outro.
import json

import pytest

from apps.pedidos.models import Order
from tests.conftest import (
    BUMP_A,
    HOST_A,
    HOST_B,
    HOST_DESCONHECIDO,
    OFERTA_A,
    OFERTA_B,
    SITE_A,
    SITE_B,
    SLUG,
)

pytestmark = pytest.mark.django_db


def test_host_desconhecido_e_404_nunca_um_site_padrao(api, rede):
    resp = api.post(
        "/api/checkout/sessoes", {"offer_slug": SLUG}, host=HOST_DESCONHECIDO
    )
    assert resp.status_code == 404


def test_a_mesma_slug_em_dois_sites_devolve_o_preco_de_cada_um(api, rede):
    do_a = api.post("/api/checkout/sessoes", {"offer_slug": SLUG})
    do_b = api.post("/api/checkout/sessoes", {"offer_slug": SLUG}, host=HOST_B)

    assert do_a.json()["offer"]["price_cents"] == OFERTA_A["price_cents"]
    assert do_b.json()["offer"]["price_cents"] == OFERTA_B["price_cents"]
    assert do_a.json()["site_id"] == SITE_A["id"]
    assert do_a.json()["site_id"] != do_b.json()["site_id"]


def test_sessao_do_site_a_nao_fecha_pedido_pelo_host_do_site_b(api, rede, sessao_a):
    resp = api.post(
        f"/api/checkout/sessoes/{sessao_a['id']}/pedido",
        {
            "customer": {"email": "cliente@exemplo.com", "name": "Cliente"},
            "method": "pix",
        },
        host=HOST_B,
    )
    assert resp.status_code == 404
    assert Order.objects.count() == 0


def test_pedido_do_site_a_nao_e_visivel_pelo_host_do_site_b(api, rede, sessao_a):
    criado = api.post(
        f"/api/checkout/sessoes/{sessao_a['id']}/pedido",
        {
            "customer": {"email": "cliente@exemplo.com", "name": "Cliente"},
            "bump_ids": [BUMP_A["id"]],
            "method": "pix",
        },
    )
    order_id = criado.json()["order_id"]

    assert api.get(f"/api/checkout/pedidos/{order_id}").status_code == 200
    assert api.get(f"/api/checkout/pedidos/{order_id}", host=HOST_B).status_code == 404
    assert (
        api.get(f"/api/checkout/pedidos/{order_id}", host=HOST_DESCONHECIDO).status_code
        == 404
    )


def test_oferta_inexistente_neste_site_e_404(api, rede):
    resp = api.post("/api/checkout/sessoes", {"offer_slug": "oferta-que-nao-existe"})
    assert resp.status_code == 404


def _post_com_cabecalhos(client, token, path, corpo, host, **cabecalhos):
    """O fixture `api` só sabe mandar Host; aqui o atacante manda mais."""
    return client.post(
        path,
        data=json.dumps(corpo),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_HOST=host,
        **cabecalhos,
    )


def test_cabecalho_de_proxy_forjado_nao_troca_o_site_do_host(client, token_valido, rede):
    # O site vem do Host, e SÓ do Host. Nenhum cabeçalho que o cliente consiga
    # escrever redireciona a resolução, e X-Forwarded-Host é o clássico: quem
    # ler `(request.headers.get("X-Forwarded-Host") or request.get_host())`
    # entrega a oferta do site A a quem bateu no host do site B.
    resp = _post_com_cabecalhos(
        client,
        token_valido,
        "/api/checkout/sessoes",
        {"offer_slug": SLUG},
        host=HOST_B,
        HTTP_X_FORWARDED_HOST=HOST_A,
    )
    assert resp.status_code == 201, resp.content
    assert resp.json()["site_id"] == SITE_B["id"]
    assert resp.json()["offer"]["price_cents"] == OFERTA_B["price_cents"]


def test_host_desconhecido_continua_404_mesmo_com_cabecalho_de_proxy_valido(
    client, token_valido, rede
):
    # A outra ponta: o cabeçalho forjado também não pode RESGATAR um host que
    # não existe, senão qualquer domínio apontado para cá vira loja aberta.
    resp = _post_com_cabecalhos(
        client,
        token_valido,
        "/api/checkout/sessoes",
        {"offer_slug": SLUG},
        host=HOST_DESCONHECIDO,
        HTTP_X_FORWARDED_HOST=HOST_A,
    )
    assert resp.status_code == 404
