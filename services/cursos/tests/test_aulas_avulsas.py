import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock

import pytest
from django.db import close_old_connections
from django.db import IntegrityError
from django.test import Client
from django.urls import clear_script_prefix, reverse, set_script_prefix

from apps.core import api
from apps.cursos.models import AulaAvulsa
from tests.conftest import ANA, COOKIE, SITE, dublar_matricula, dublar_sessao

pytestmark = pytest.mark.django_db

TOKEN = "token-do-admin"
BASE = "/api/cursos"


@pytest.fixture(autouse=True)
def par_autorizado(settings):
    settings.TOKENS_ACEITOS = {TOKEN}


def criar(**mudancas):
    corpo = {
        "titulo": "Os pilares do Roblox",
        "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "descricao": "# Comece aqui\n\nUma resposta **direta**.",
    }
    corpo.update(mudancas)
    return Client().post(
        f"{BASE}/aulas-avulsas?site_id={SITE}",
        data=json.dumps(corpo),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {TOKEN}",
    )


def editar(endereco, **mudancas):
    corpo = {
        "titulo": "Os três pilares atualizados",
        "video_url": "https://youtu.be/dQw4w9WgXcQ",
        "descricao": "Uma explicação corrigida.",
    }
    corpo.update(mudancas)
    return Client().put(
        f"{BASE}/aulas-avulsas/{endereco}?site_id={SITE}",
        data=json.dumps(corpo),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {TOKEN}",
    )


def test_cria_publicada_com_slug_gerado_e_lista_por_site():
    resposta = criar()
    assert resposta.status_code == 201
    aula = resposta.json()
    assert aula["slug"] == "os-pilares-do-roblox"
    assert aula["estado"] == "publicada"
    assert aula["publicada_em"]
    assert Client().get(
        f"{BASE}/aulas-avulsas?site_id={SITE}",
        HTTP_AUTHORIZATION=f"Bearer {TOKEN}",
    ).json() == [aula]


def test_titulo_igual_ganha_sufixo_e_slug_nao_muda():
    primeira = criar().json()
    segunda = criar().json()
    assert (primeira["slug"], segunda["slug"]) == (
        "os-pilares-do-roblox",
        "os-pilares-do-roblox-2",
    )
    primeira_do_banco = AulaAvulsa.objects.get(slug=primeira["slug"])
    primeira_do_banco.titulo = "Outro título"
    primeira_do_banco.save(update_fields=["titulo"])
    assert primeira_do_banco.slug == "os-pilares-do-roblox"


def test_edita_os_tres_campos_sem_slug_preserva_endereco_e_publicacao():
    criada = criar().json()
    publicada_em_antes = AulaAvulsa.objects.get(slug=criada["slug"]).publicada_em
    resposta = editar(criada["slug"])
    assert resposta.status_code == 200
    atualizada = resposta.json()
    assert atualizada == {
        **criada,
        "titulo": "Os três pilares atualizados",
        "video_url": "https://youtu.be/dQw4w9WgXcQ",
        "descricao": "Uma explicação corrigida.",
    }
    aula_no_banco = AulaAvulsa.objects.get(slug=criada["slug"])
    assert aula_no_banco.slug == criada["slug"]
    assert aula_no_banco.publicada_em == publicada_em_antes


def test_edita_slug_nulo_devolve_422_como_corpo_invalido():
    criada = criar().json()

    resposta = editar(criada["slug"], slug=None)

    assert resposta.status_code == 422
    assert resposta.json() == {
        "erro": "corpo_invalido",
        "o_que_fazer": "Revise os campos da aula e envie somente título, URL do vídeo, descrição e slug.",
    }


def test_edita_slug_normaliza_unicode_antes_de_reservar_o_endereco():
    criada = criar().json()
    aula_id = AulaAvulsa.objects.get(slug=criada["slug"]).pk
    resposta = editar(criada["slug"], slug="Ação & Testes")
    assert resposta.status_code == 200
    assert resposta.json()["slug"] == "acao-testes"
    assert AulaAvulsa.objects.get(pk=aula_id).slug == "acao-testes"


def test_edita_slug_igual_ao_atual_sem_alterar_o_endereco():
    criada = criar().json()
    resposta = editar(criada["slug"], slug=criada["slug"])
    assert resposta.status_code == 200
    assert resposta.json()["slug"] == criada["slug"]


def test_edita_slug_ocupado_com_menor_sufixo_livre():
    criada = criar(titulo="Aula original").json()
    criar(titulo="Guia")
    criar(titulo="Guia")
    criar(titulo="Guia")
    resposta = editar(criada["slug"], slug="Guia")
    assert resposta.status_code == 200
    assert resposta.json()["slug"] == "guia-4"


def test_edita_slug_longo_ocupado_encontra_menor_sufixo_apos_truncamento():
    base = "a" * 140
    criada = criar(titulo="Aula original").json()
    aula_id = AulaAvulsa.objects.get(slug=criada["slug"]).pk
    for sufixo in range(1, 4):
        AulaAvulsa.objects.create(
            site_id=SITE,
            titulo=f"Aula {sufixo}",
            slug=api._proximo_slug(base, sufixo),
            video_url="https://youtu.be/dQw4w9WgXcQ",
        )

    assert api._proximo_slug_livre(SITE, base, aula_id) == api._proximo_slug(base, 4)
    resposta = editar(criada["slug"], slug=base)

    assert resposta.status_code == 200
    assert resposta.json()["slug"] == api._proximo_slug(base, 4)


def test_edita_slug_concorrente_reexecuta_apos_colisao_no_banco(monkeypatch):
    primeira = AulaAvulsa.objects.create(
        site_id=SITE,
        titulo="Primeira",
        slug="primeira",
        video_url="https://youtu.be/dQw4w9WgXcQ",
    )

    chamadas_save = 0
    original_save = AulaAvulsa.save

    def mock_save(self, *args, **kwargs):
        nonlocal chamadas_save
        chamadas_save += 1
        if chamadas_save == 1 and self.slug == "aula-disputada":
            # Simula a colisão de banco de dados jogando IntegrityError
            # logo ANTES de gravar, mas cria a linha conflitante FORA
            # deste atomic block se fosse possível.
            # Como estamos no mock do save, vamos apenas forçar o erro
            # e criar a linha concorrente direto no banco com uma conexão separada?
            # Não, basta jogar IntegrityError. E para a SEGUNDA tentativa
            # calcular o sufixo correto, precisamos que a linha exista.
            # O problema é que o rollback desfaz tudo.
            # Então nós inserimos a linha conflitante usando _outra_ abordagem ou
            # mockamos o _proximo_slug_livre para também devolver o sufixo na 2a vez.
            raise IntegrityError("simulando colisão concorrente")
        return original_save(self, *args, **kwargs)

    monkeypatch.setattr(AulaAvulsa, "save", mock_save)

    chamadas_proximo = 0
    original_proximo = api._proximo_slug_livre

    def mock_proximo(*args):
        nonlocal chamadas_proximo
        chamadas_proximo += 1
        if chamadas_proximo == 1:
            return "aula-disputada"
        return "aula-disputada-2"

    monkeypatch.setattr(api, "_proximo_slug_livre", mock_proximo)

    payload = api.AulaAvulsaParaEditarSchema(
        titulo="Aula disputada",
        video_url="https://youtu.be/dQw4w9WgXcQ",
        descricao="",
        slug="Aula disputada",
    )

    resultado = api.update_standalone_lesson(None, primeira.slug, SITE, payload)

    assert resultado["slug"] == "aula-disputada-2"
    assert AulaAvulsa.objects.get(pk=primeira.pk).slug == "aula-disputada-2"


@pytest.mark.parametrize("slug", ["", "!!!", "   "])
def test_edita_slug_fora_do_formato_do_contrato_devolve_422_como_envelope(slug):
    criada = criar().json()
    resposta = editar(criada["slug"], slug=slug)
    assert resposta.status_code == 422
    assert resposta.json() == {
        "erro": "slug_invalido",
        "o_que_fazer": "Informe um endereço com ao menos uma letra ou número.",
    }


def test_editar_aula_ausente_neste_site_devolve_404():
    criada = criar().json()
    resposta = Client().put(
        f"{BASE}/aulas-avulsas/{criada['slug']}?site_id=outro-site",
        data=json.dumps(
            {
                "titulo": "Outro título",
                "video_url": "https://youtu.be/dQw4w9WgXcQ",
                "descricao": "",
            }
        ),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {TOKEN}",
    )
    assert resposta.status_code == 404
    assert resposta.json() == {
        "erro": "aula_avulsa_nao_encontrada",
        "o_que_fazer": "Confira o endereço da aula ou escolha outra aula publicada.",
    }


def test_editar_recusa_chave_desconhecida_com_campos_validos():
    criada = criar().json()
    resposta = editar(criada["slug"], campo_desconhecido="nao-pode")
    assert resposta.status_code == 422
    assert resposta.json() == {
        "erro": "corpo_invalido",
        "o_que_fazer": "Revise os campos da aula e envie somente título, URL do vídeo, descrição e slug.",
    }


@pytest.mark.parametrize(
    "video_url",
    ["", "http://youtube.com/watch?v=dQw4w9WgXcQ", "https://vimeo.com/123"],
)
def test_url_de_video_invalida_e_422(video_url):
    assert criar(video_url=video_url).status_code == 422


def test_pagina_publica_exige_matricula_deste_site(env_dos_pares, rede, client):
    aula = AulaAvulsa.objects.create(
        site_id=SITE,
        titulo="Os pilares do Roblox",
        slug="os-pilares-do-roblox",
        video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    )
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"], "aluno", site="outra-escola")
    resposta = client.get(reverse("aula-avulsa", args=[aula.slug]), HTTP_COOKIE=COOKIE)
    assert resposta.status_code == 403
    assert (
        "Não encontramos uma matrícula ativa no seu nome" in resposta.content.decode()
    )


def test_pagina_mostra_markdown_video_e_capa_do_youtube(aluna, client):
    aula = AulaAvulsa.objects.create(
        site_id=SITE,
        titulo="Os pilares do Roblox",
        slug="os-pilares-do-roblox",
        video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        descricao="# Comece aqui\n\nUma resposta **direta**.",
    )
    resposta = client.get(reverse("aula-avulsa", args=[aula.slug]), HTTP_COOKIE=COOKIE)
    corpo = resposta.content.decode()
    assert resposta.status_code == 200
    assert "<h1>Comece aqui</h1>" in corpo
    assert "<strong>direta</strong>" in corpo
    assert 'src="https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"' in corpo
    assert 'referrerpolicy="strict-origin-when-cross-origin"' in corpo
    assert "Abrir o vídeo em outra aba" in corpo


def test_pagina_publica_da_aula_avulsa_resolve_sob_o_prefixo_cursos(
    aluna, client, settings
):
    aula = AulaAvulsa.objects.create(
        site_id=SITE,
        titulo="Os pilares do Roblox",
        slug="os-pilares-do-roblox",
        video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    )
    settings.FORCE_SCRIPT_NAME = "/cursos"
    set_script_prefix("/cursos")
    try:
        assert reverse("aula-avulsa", args=[aula.slug]) == (
            "/cursos/aulas/os-pilares-do-roblox"
        )
        resposta = client.get("/aulas/os-pilares-do-roblox", HTTP_COOKIE=COOKIE)
    finally:
        clear_script_prefix()
    assert resposta.status_code == 200


def test_indice_vazio_e_acesso_de_visitante(env_dos_pares, client):
    resposta = client.get(reverse("aulas-avulsas"))
    assert resposta.status_code == 200
    assert "Entre para ver o curso" in resposta.content.decode()
