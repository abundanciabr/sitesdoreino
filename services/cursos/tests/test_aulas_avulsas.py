import json

import pytest
from django.test import Client
from django.urls import clear_script_prefix, reverse, set_script_prefix

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


def test_edita_os_tres_campos_sem_mudar_slug_nem_data_de_publicacao():
    criada = criar().json()
    publicada_em_antes = AulaAvulsa.objects.get(slug=criada["slug"]).publicada_em
    resposta = Client().put(
        f"{BASE}/aulas-avulsas/{criada['slug']}?site_id={SITE}",
        data=json.dumps(
            {
                "titulo": "Os três pilares atualizados",
                "video_url": "https://youtu.be/dQw4w9WgXcQ",
                "descricao": "Uma explicação corrigida.",
            }
        ),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {TOKEN}",
    )
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


def test_editar_recusa_chave_desconhecida_com_campos_validos():
    criada = criar().json()
    resposta = Client().put(
        f"{BASE}/aulas-avulsas/{criada['slug']}?site_id={SITE}",
        data=json.dumps(
            {
                "titulo": "Os três pilares atualizados",
                "video_url": "https://youtu.be/dQw4w9WgXcQ",
                "descricao": "Uma explicação corrigida.",
                "slug": "nao-pode",
            }
        ),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {TOKEN}",
    )
    assert resposta.status_code == 422


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
