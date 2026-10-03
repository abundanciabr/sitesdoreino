import json
from io import BytesIO

import httpx
import pytest
from PIL import Image
from django.test import Client
from django.urls import reverse

from apps.portfolio import comercial, robo
from apps.portfolio.models import Portfolio, Peca, ImagemDoPortfolio
from conftest import ANA, SITE, ADMIN
from test_jornada_autoral import como, quiz_falso

pytestmark = pytest.mark.django_db


def conteudo(peca):
    valor = comercial.normalizar_conteudo({})
    valor["pagina"].update(titulo="Espadas para o universo do seu jogo", apresentacao="Crio espadas de fantasia.",
        oferta="Uma espada e texturas.", trabalho_destaque=str(peca.pk),
        legendas=[{"peca_id": str(peca.pk), "titulo": "Espada autoral", "texto": "Render e detalhes da minha peça."}])
    valor["kit"]["abordagem"] = "PROSPECT_PRIVADO"
    valor["kit"]["bio_curta"] = "Espadas de fantasia para Roblox."
    return valor


def test_salvar_reabrir_e_publicar_sem_kit_nem_destinatario(aluna, site_declarado, rede, quiz_falso):
    portfolio = Portfolio.objects.create(site_id=SITE, aluno_id=ANA["id"])
    peca = Peca.objects.create(portfolio=portfolio, ordem=1, link="https://exemplo.test/espada.png")
    estrangeiro = Portfolio.objects.create(site_id=SITE, aluno_id="outro")
    outra = Peca.objects.create(portfolio=estrangeiro, ordem=1, link="https://exemplo.test/segredo.png")
    valor = conteudo(peca)
    valor["pagina"]["legendas"].append({"peca_id": str(outra.pk), "titulo": "SEGREDO_DE_OUTRO", "texto": ""})
    dados = {"conteudo_json": json.dumps(valor), "oferta_formulario": "1", "oferta_encomenda": "Uma espada",
        "oferta_preco": "250", "oferta_moeda": "BRL", "oferta_contato": "https://discord.com/users/exemplo",
        "prospeccao_nome": "DESTINATARIO_PRIVADO", "selecao_trabalhos": "1", "trabalhos_ids": [str(peca.pk), str(outra.pk)],
        "provas_" + str(peca.pk): "wireframe | https://exemplo.test/malha.png | A malha"}
    cliente = Client()
    assert cliente.post(reverse("apresentacao_publica"), dados, **como()).status_code == 302
    portfolio.refresh_from_db(); peca.refresh_from_db(); outra.refresh_from_db()
    assert portfolio.apresentacao_publica == "Crio espadas de fantasia."
    assert portfolio.kit_vendas["abordagem"] == "PROSPECT_PRIVADO"
    assert not portfolio.vitrine_publicada and not outra.mostrar_na_pagina_publica
    assert peca.mostrar_na_pagina_publica and len(peca.provas_comerciais) == 1
    assert len(portfolio.apresentacao_comercial["pagina"]["legendas"]) == 1
    assert "PROSPECT_PRIVADO" in cliente.get(reverse("apresentacao_publica"), **como()).content.decode()
    assert cliente.post(reverse("publicar_vitrine"), {"apelido": "ana-3d"}, **como()).status_code == 302
    publico = Client().get(reverse("vitrine", kwargs={"apelido": "ana-3d"})).content.decode()
    assert "Espadas para o universo" in publico and "malha.png" in publico
    assert all(segredo not in publico for segredo in ("PROSPECT_PRIVADO", "DESTINATARIO_PRIVADO", "SEGREDO_DE_OUTRO", "250"))


def test_geracao_recebe_so_imagens_e_dados_do_dono_sem_salvar(aluna, site_declarado, rede, quiz_falso):
    portfolio = Portfolio.objects.create(site_id=SITE, aluno_id=ANA["id"], apresentacao_publica="Texto anterior")
    peca = Peca.objects.create(portfolio=portfolio, ordem=1, link="https://exemplo.test/modelo.png")
    saida = BytesIO(); Image.new("RGB", (30, 30), "red").save(saida, format="WEBP")
    ImagemDoPortfolio.objects.create(peca=peca, bytes=saida.getvalue(), tamanho=len(saida.getvalue()), largura=30, altura=30)
    api = rede.post(ADMIN + "/robo-dos-alunos/gerar").mock(return_value=httpx.Response(200, json={"conteudo": conteudo(peca)}))
    resposta = Client().post(reverse("gerar_exemplo"), {"campo": "completo", "selecao_trabalhos": "1",
        "trabalhos_ids": [str(peca.pk)], "oferta_encomenda": "Uma espada", "conteudo_json": json.dumps(conteudo(peca))}, **como())
    assert resposta.status_code == 200
    contexto = json.loads(api.calls[0].request.content)["contexto"]
    assert contexto["oferta"]["encomenda"] == "Uma espada"
    assert contexto["imagens"][0]["data_url"].startswith("data:image/webp;base64,")
    assert contexto["imagens"][0]["peca_id"] == str(peca.pk)
    portfolio.refresh_from_db()
    assert portfolio.apresentacao_publica == "Texto anterior" and not portfolio.apresentacao_comercial


def test_payload_invalido_preserva_e_preco_pode_ser_desmarcado(aluna, site_declarado, rede, quiz_falso):
    portfolio = Portfolio.objects.create(site_id=SITE, aluno_id=ANA["id"], apresentacao_publica="Anterior", oferta_comercial={"exibir_preco": True})
    resposta = Client().post(reverse("apresentacao_publica"), {"conteudo_json": "{malformado"}, **como())
    assert resposta.status_code == 422
    portfolio.refresh_from_db(); assert portfolio.apresentacao_publica == "Anterior"
    assert comercial.oferta_de(portfolio, dados={"oferta_formulario": "1"})["exibir_preco"] is False
    for url in ("javascript:alert(1)", "https://localhost/", "https://127.0.0.1/", "https://pessoa:segredo@exemplo.com/"):
        assert comercial.url_publica(url) == ""
