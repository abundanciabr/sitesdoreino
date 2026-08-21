from tests.conftest import HOST_A, HOST_B, HOST_DESCONHECIDO, OFERTA_A, SLUG


def test_landing_mostra_a_oferta_padrao_do_site(client, rede):
    resp = client.get("/", HTTP_HOST=HOST_A)
    assert resp.status_code == 200
    assert OFERTA_A["product"]["name"].encode() in resp.content
    assert b"99,00" in resp.content  # price_cents 9900 -> R$ 99,00


def test_host_desconhecido_e_404_nunca_um_site_padrao(client, rede):
    resp = client.get("/", HTTP_HOST=HOST_DESCONHECIDO)
    assert resp.status_code == 404


def test_site_sem_oferta_padrao_e_404(client, rede):
    resp = client.get("/", HTTP_HOST=HOST_B)
    assert resp.status_code == 404


def test_botao_de_compra_aponta_pro_checkout_da_oferta_padrao(client, rede):
    resp = client.get("/", HTTP_HOST=HOST_A)
    assert f'href="/checkout/{SLUG}/"'.encode() in resp.content


def test_utm_chega_intacta_ao_link_do_checkout(client, rede):
    resp = client.get(
        "/",
        {
            "utm_source": "instagram",
            "utm_medium": "cpc",
            "utm_campaign": "lancamento-esqueleto",
        },
        HTTP_HOST=HOST_A,
    )
    # o Django autoescapa `&` em atributo HTML — o browser decodifica normalmente
    esperado = (
        f'href="/checkout/{SLUG}/?utm_source=instagram&amp;utm_medium=cpc'
        f'&amp;utm_campaign=lancamento-esqueleto"'
    ).encode()
    assert esperado in resp.content


def test_sem_utm_o_link_do_checkout_nao_leva_query_string(client, rede):
    resp = client.get("/", HTTP_HOST=HOST_A)
    assert f'href="/checkout/{SLUG}/"'.encode() in resp.content
    assert b"?utm" not in resp.content
