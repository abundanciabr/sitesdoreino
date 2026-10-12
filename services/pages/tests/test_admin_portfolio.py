from django.test import Client
from django.urls import reverse

from conftest import ANA, BIA, COOKIE
from test_portfolio_visual_fluxo import imagem, montagem_dados, preparo_url


def test_admin_sem_matricula_prepara_salva_previa_e_pdf_do_proprio_portfolio(
    da_equipe, site_declarado, criar_portfolio, criar_peca
):
    cliente = Client(HTTP_COOKIE=COOKIE)
    assert cliente.get(reverse("apresentacao_publica")).status_code == 200
    portfolio = criar_portfolio(BIA["id"])
    peca = criar_peca(portfolio, legenda="Trabalho próprio")
    alheio = criar_peca(criar_portfolio(ANA["id"]), legenda="Privado da Ana")
    assert cliente.get(preparo_url(alheio)).status_code == 404
    url = preparo_url(peca)
    assert cliente.post(url, {"acao": "enviar", "categoria": "render",
        "arquivos": [imagem("render.png", "blue")], "principal": "1"}).status_code == 302
    material = peca.materiais.get()
    assert cliente.get(reverse("imagem_portfolio", kwargs={"imagem_id": material.pk})).status_code == 200
    assert cliente.post(url, {"acao": "salvar", "titulo": "Meu modelo",
        "descricao": "Descrição do trabalho", "checklist": ["nome_descricao"]}).status_code == 302
    peca.refresh_from_db()
    assert any(i["chave"] == "nome_descricao" and i["marcado"] for i in peca.checklist_preparacao)
    salvo = cliente.post(reverse("apresentacao_publica"),
        montagem_dados(peca, [material], "Portfólio de teste"),
        HTTP_X_REQUESTED_WITH="XMLHttpRequest")
    assert salvo.status_code == 200 and salvo.json()["salvo"]
    assert "Portfólio de teste" in cliente.get(reverse("apresentacao_previa")).content.decode()
    pdf = cliente.get(reverse("dossie"))
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    portfolio.refresh_from_db()
    assert not portfolio.vitrine_publicada
    assert portfolio.pecas.count() == 1
    alheio.refresh_from_db()
    assert alheio.legenda == "Privado da Ana"
