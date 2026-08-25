"""A saída única do site: POST, com prova de origem — nunca GET.

`/entrar/sair` é `csrf_exempt` por necessidade (os formulários que postam para
cá são renderizados por OUTRAS células, que não têm o token de CSRF desta) e a
defesa equivalente é a de ORIGEM: `Origin`/`Referer` do próprio host, ou 403.
Sem cabeçalho nenhum também fecha — fail-closed, como toda borda da casa.
"""


def test_get_nao_encerra_nada(dentro):
    assert dentro.client.get("/entrar/sair").status_code == 405
    assert dentro.esta_dentro


def test_post_sem_origem_nenhuma_e_403(dentro):
    resposta = dentro.client.post("/entrar/sair")
    assert resposta.status_code == 403
    assert dentro.esta_dentro


def test_post_de_outro_site_e_403(dentro):
    resposta = dentro.client.post(
        "/entrar/sair", HTTP_ORIGIN="https://golpista.example"
    )
    assert resposta.status_code == 403
    assert dentro.esta_dentro


def test_post_da_propria_origem_encerra_e_volta(dentro):
    resposta = dentro.client.post(
        "/entrar/sair", {"next": "/pt-br/"}, HTTP_ORIGIN="http://testserver"
    )
    assert resposta.status_code == 302
    assert resposta["Location"] == "/pt-br/"
    assert not dentro.esta_dentro


def test_referer_da_propria_origem_tambem_vale(dentro):
    """Formulário de página antiga sem `Origin` (Referer só): também é prova."""
    resposta = dentro.client.post(
        "/entrar/sair", HTTP_REFERER="http://testserver/forms/sugestoes/"
    )
    assert resposta.status_code == 302
    assert not dentro.esta_dentro


def test_next_do_sair_tambem_e_saneado(dentro):
    resposta = dentro.client.post(
        "/entrar/sair",
        {"next": "https://golpista.example/"},
        HTTP_ORIGIN="http://testserver",
    )
    assert resposta.status_code == 302
    assert resposta["Location"] == "/"
