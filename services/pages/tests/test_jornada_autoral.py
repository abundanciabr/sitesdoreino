"""Percurso do aluno: explorar, escolher e mostrar apenas o trabalho desejado."""

from io import BytesIO
import uuid

import httpx
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.core.jornada import CAMINHOS
from apps.portfolio.models import ImagemDoPortfolio, Peca, Portfolio, ProjetoAutoral
from conftest import ANA, COOKIE, SITE, URL_DA_SESSAO, dublar_matricula


def como():
    return {"HTTP_COOKIE": COOKIE}


class QuizFalso:
    """Guarda tentativas como o serviço de quiz, inclusive a opção de retomar."""

    def __init__(self):
        self.tentativas = {}
        self.atual = None
        self.chamadas = []

    def chamar(self, caminho, *, site_id, aluno_id=None, dados=None):
        self.chamadas.append((caminho, site_id, aluno_id, dados))
        if caminho == "catalogo":
            return {"familias": [], "projetos": []}
        if caminho == "exploracoes/atual":
            return self.tentativas.get(self.atual)
        if caminho == "exploracoes":
            if self.atual and not dados["nova"]:
                return self.tentativas[self.atual]
            identificador = str(uuid.uuid4())
            entrada = dados["entrada"]
            tentativa = {
                "id": identificador, "entrada": entrada,
                "etapa": CAMINHOS[entrada][0], "respostas": {},
                "propostas": [{
                    "chave": "cafe", "titulo": "Móveis para cafeteria",
                    "descricao": "Cadeiras e balcão", "servico": "Objetos para Roblox",
                }],
            }
            self.tentativas[identificador] = tentativa
            self.atual = identificador
            return tentativa
        if caminho.startswith("exploracoes/"):
            partes = caminho.split("/")
            tentativa = self.tentativas.get(partes[1])
            if tentativa is None:
                return None
            if len(partes) == 3 and partes[2] == "respostas":
                tentativa["respostas"].update(dados["respostas"])
                tentativa["etapa"] = dados["etapa"]
            return tentativa
        raise AssertionError(f"Chamada inesperada ao quiz: {caminho}")


@pytest.fixture
def quiz_falso(monkeypatch):
    falso = QuizFalso()
    monkeypatch.setattr("apps.core.jornada.quiz.chamar", falso.chamar)
    return falso


@pytest.mark.parametrize("entrada", ["descobrir", "ideia", "prontos"])
def test_tres_entradas_salvar_sair_e_retomar_a_mesma_tentativa(
    entrada, aluna, site_declarado, quiz_falso
):
    cliente = Client()
    inicio = cliente.post(reverse("iniciar_quiz"), {"entrada": entrada}, **como())
    tentativa_id = quiz_falso.atual
    assert inicio.status_code == 302
    assert tentativa_id in inicio["Location"]
    assert CAMINHOS[entrada][0] in inicio["Location"]

    etapa = CAMINHOS[entrada][0]
    resposta = cliente.post(
        reverse("quiz_etapa", kwargs={"exploracao_id": tentativa_id, "etapa": etapa}),
        {"acao": "salvar_sair", "interesses": ["objetos"], "experiencia": "comecando"},
        **como(),
    )
    assert resposta.status_code == 302
    assert resposta["Location"] == reverse("prancheta")
    assert quiz_falso.tentativas[tentativa_id]["etapa"] == CAMINHOS[entrada][1]

    home = cliente.get(reverse("prancheta"), **como())
    assert home.status_code == 200
    assert home.context["exploracao"]["id"] == tentativa_id
    retomada = cliente.post(reverse("iniciar_quiz"), {"entrada": entrada}, **como())
    assert tentativa_id in retomada["Location"]
    assert len(quiz_falso.tentativas) == 1
    assert all(site == SITE and aluno == ANA["id"] for _, site, aluno, _ in quiz_falso.chamadas if aluno)


def test_aceitar_proposta_editada_e_idempotente_mas_nova_exploracao_preserva_anterior(
    aluna, site_declarado, quiz_falso
):
    cliente = Client()
    cliente.post(reverse("iniciar_quiz"), {"entrada": "ideia"}, **como())
    primeira_tentativa = quiz_falso.atual
    quiz_falso.tentativas[primeira_tentativa]["respostas"]["projeto_chave"] = "cafe"
    url = reverse("comecar_projeto", kwargs={"exploracao_id": primeira_tentativa})
    dados = {"titulo": "Minha cafeteria", "intencao": "Quero criar móveis autorais"}
    primeira = cliente.post(url, dados, **como())
    repetida = cliente.post(url, dados, **como())
    assert primeira.status_code == repetida.status_code == 302
    assert primeira["Location"] == repetida["Location"]
    projeto = ProjetoAutoral.objects.do_aluno(site_id=SITE, aluno_id=ANA["id"]).get()
    assert projeto.titulo == "Minha cafeteria"
    assert projeto.origem_proposta["intencao"] == "Quero criar móveis autorais"

    cliente.post(reverse("iniciar_quiz"), {"entrada": "prontos", "nova": "1"}, **como())
    segunda_tentativa = quiz_falso.atual
    assert segunda_tentativa != primeira_tentativa
    assert ProjetoAutoral.objects.do_aluno(site_id=SITE, aluno_id=ANA["id"]).get().pk == projeto.pk
    assert len(quiz_falso.tentativas) == 2


def test_projeto_direto_e_isolamento_por_aluno_e_site(
    aluna, site_declarado, quiz_falso, rede, monkeypatch
):
    cliente = Client()
    resposta = cliente.post(
        reverse("novo_projeto"),
        {"titulo": "Meu veículo", "servico": "Modelagem de veículos"}, **como(),
    )
    assert resposta.status_code == 302
    projeto = ProjetoAutoral.objects.do_aluno(site_id=SITE, aluno_id=ANA["id"]).get()
    assert projeto.origem_exploracao is None
    endereco = reverse("projeto", kwargs={"projeto_id": projeto.pk})
    assert cliente.get(endereco, **como()).status_code == 200

    monkeypatch.setenv("SITE_ID", "outra-escola")
    assert cliente.get(endereco, **como()).status_code == 404
    monkeypatch.setenv("SITE_ID", SITE)
    outra_aluna = {**ANA, "id": "p_outra"}
    rede.get(URL_DA_SESSAO).mock(return_value=httpx.Response(200, json=outra_aluna))
    dublar_matricula(rede, outra_aluna["email"])
    assert cliente.get(endereco, **como()).status_code == 404
    assert cliente.post(endereco, {"titulo": "Tentativa de edição"}, **como()).status_code == 404
    projeto.refresh_from_db()
    assert projeto.titulo == "Meu veículo"


def _png_upload(nome):
    dados = BytesIO()
    Image.new("RGB", (24, 24), (20, 80, 150)).save(dados, format="PNG")
    return SimpleUploadedFile(nome, dados.getvalue(), content_type="image/png")


def test_imagens_novas_ficam_privadas_e_aluno_escolhe_uma_para_a_vitrine(
    aluna, site_declarado, quiz_falso
):
    cliente = Client()
    projeto = cliente.post(reverse("novo_projeto"), {"titulo": "Cafeteria"}, **como())
    assert projeto.status_code == 302
    escolhido = ProjetoAutoral.objects.do_aluno(site_id=SITE, aluno_id=ANA["id"]).get()
    for indice in (1, 2):
        resposta = cliente.post(
            reverse("guardar_peca"),
            {"legenda": f"Obra {indice}", "imagem": _png_upload(f"obra-{indice}.png")},
            **como(),
        )
        assert resposta.status_code == 302
    pecas = list(Peca.objects.do_aluno(site_id=SITE, aluno_id=ANA["id"]).order_by("ordem"))
    assert len(pecas) == 2
    assert all(not peca.mostrar_na_pagina_publica for peca in pecas)
    imagens = [ImagemDoPortfolio.objects.get(peca=peca) for peca in pecas]

    portfolio = Portfolio.objects.do_aluno(site_id=SITE, aluno_id=ANA["id"]).get()
    portfolio.apelido = "ana-arte"
    portfolio.vitrine_publicada = True
    portfolio.publicada_em = timezone.now()
    portfolio.save(update_fields=["apelido", "vitrine_publicada", "publicada_em"])
    assert cliente.get(reverse("imagem_portfolio", kwargs={"imagem_id": imagens[0].pk})).status_code == 404

    resposta = cliente.post(
        reverse("trabalho_contexto", kwargs={"peca_id": pecas[0].pk}),
        {"projeto_id": str(escolhido.pk), "legenda": "Obra 1", "uso_pretendido": "Cenário de Roblox", "mostrar_na_pagina_publica": "1"},
        **como(),
    )
    assert resposta.status_code == 302
    pecas[0].refresh_from_db()
    pecas[1].refresh_from_db()
    assert pecas[0].projeto_id == escolhido.pk
    assert pecas[0].mostrar_na_pagina_publica is True
    assert pecas[1].mostrar_na_pagina_publica is False
    assert cliente.get(reverse("imagem_portfolio", kwargs={"imagem_id": imagens[0].pk})).status_code == 200
    assert cliente.get(reverse("imagem_portfolio", kwargs={"imagem_id": imagens[1].pk})).status_code == 404
    vitrine = cliente.get(reverse("vitrine", kwargs={"apelido": "ana-arte"}))
    assert vitrine.status_code == 200
    assert "Obra 1" in vitrine.content.decode()
    assert "Obra 2" not in vitrine.content.decode()
