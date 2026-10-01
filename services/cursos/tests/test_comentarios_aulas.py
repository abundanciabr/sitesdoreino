import json
import pytest
from django.test import Client
from django.urls import reverse
from apps.cursos.models import ComentarioDeAula, Pessoa, Curso, Progresso
from tests.conftest import (
    ANA,
    BETO,
    COOKIE,
    SITE,
    dublar_sessao,
    dublar_matricula,
    publicar,
)

pytestmark = pytest.mark.django_db
ADMIN = "token-especifico-admin"
BASE = "/api/cursos/comentarios"


def endereco(aula, gesto=False, parte=None):
    return reverse(
        "enviar-comentario" if gesto else "aula-do-curso",
        args=[aula.curso.slug, parte or aula.bloco.parte, aula.numero],
    )


@pytest.fixture
def cenario(aluna, aula_publicada, rede, client, monkeypatch):
    monkeypatch.setenv("TOKENS_ACEITOS_ADMIN", ADMIN)
    client.defaults["HTTP_COOKIE"] = COOKIE
    assert client.get(endereco(aula_publicada)).status_code == 200
    ana = Pessoa.objects.get(pk=ANA["id"])
    beto = Pessoa.objects.create(id_da_plataforma=BETO["id"], nome_exibido="Beto")
    return client, aula_publicada, ana, beto


def comentario(aula, autor, corpo="Dúvida privada", publico=False):
    return ComentarioDeAula.objects.create(
        aula=aula, autor=autor, corpo=corpo, publico=publico
    )


def api(client, aula, item=None, publico=True, site=SITE, token=ADMIN, extra=None):
    headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
    if item is None:
        return client.get(BASE, {"site_id": site}, **headers)
    payload = {"publico": publico, "moderador_id": "admin-opaco"}
    payload.update(extra or {})
    return client.put(
        f"{BASE}/{item.pk}/visibilidade?site_id={site}",
        json.dumps(payload),
        content_type="application/json",
        **headers,
    )


def test_novo_comentario_e_privado_e_autor_vem_da_sessao(cenario):
    client, aula, ana, beto = cenario
    estado = Progresso.objects.get(pessoa=ana, aula=aula).estado
    r = client.post(
        endereco(aula, True),
        {"corpo": "Minha dúvida", "autor": beto.pk, "publico": "true", "aula": "outra"},
    )
    assert r.status_code == 302 and r.url.endswith("#comentarios")
    item = ComentarioDeAula.objects.get()
    assert item.autor == ana and item.aula == aula and not item.publico
    assert Progresso.objects.get(pessoa=ana, aula=aula).estado == estado
    assert "Minha dúvida" in client.get(endereco(aula)).content.decode()


def test_so_proprios_e_publicos_desta_aula(cenario):
    client, aula, ana, beto = cenario
    comentario(aula, ana, "privado de Ana")
    comentario(aula, beto, "segredo de Beto")
    comentario(aula, beto, "aprovado para todos", True)
    outra = publicar(aula.curso.aulas.exclude(pk=aula.pk).first())
    comentario(outra, ana, "de outra aula")
    comentario(outra, beto, "publico de outra aula", True)
    corpo = client.get(endereco(aula)).content.decode()
    assert "privado de Ana" in corpo and "aprovado para todos" in corpo
    assert "segredo de Beto" not in corpo and "de outra aula" not in corpo


def test_outro_aluno_nao_le_privado_mesmo_sabendo_id(cenario, rede):
    client, aula, ana, beto = cenario
    item = comentario(aula, ana, "segredo de Ana")
    comentario(aula, beto, "privado de Beto")
    dublar_sessao(rede, BETO)
    dublar_matricula(rede, BETO["email"])
    corpo = client.get(
        endereco(aula), {"comentario_id": item.pk, "autor": ana.pk, "publico": "true"}
    ).content.decode()
    assert "privado de Beto" in corpo and "segredo de Ana" not in corpo


@pytest.mark.parametrize("corpo", ["", "   ", "a" * 4001])
def test_recusa_vazio_e_longo_sem_gravar(cenario, corpo):
    client, aula, _, _ = cenario
    r = client.post(endereco(aula, True), {"corpo": corpo})
    assert r.status_code == 302 and "erro=" in r.url
    assert not ComentarioDeAula.objects.exists()


@pytest.mark.parametrize(
    "modo", ["visitante", "sem_matricula", "rascunho", "parte_errada", "trancada"]
)
def test_porta_da_aula_tambem_protege_comentarios(cenario, rede, modo):
    client, aula, ana, beto = cenario
    if modo == "visitante":
        dublar_sessao(rede, {"autenticado": False})
    elif modo == "sem_matricula":
        dublar_matricula(rede, ANA["email"], "cadastrado")
    elif modo == "rascunho":
        aula.estado = "rascunho"
        aula.save(update_fields=["estado"])
    elif modo == "trancada":
        aula = publicar(aula.curso.aulas.exclude(pk=aula.pk).first())
    parte = 3 if modo == "parte_errada" else None
    r = client.post(endereco(aula, True, parte), {"corpo": "não pode gravar"})
    assert r.status_code in (200, 302, 403, 404)
    assert not ComentarioDeAula.objects.exists()
    item = comentario(aula, beto, "texto protegido", True)
    assert (
        "texto protegido"
        not in client.get(endereco(aula, parte=parte)).content.decode()
    )


def test_csrf_obrigatorio(cenario):
    _, aula, _, _ = cenario
    client = Client(enforce_csrf_checks=True, HTTP_COOKIE=COOKIE)
    assert client.post(endereco(aula, True), {"corpo": "injetado"}).status_code == 403
    assert not ComentarioDeAula.objects.exists()


@pytest.mark.parametrize("token", [None, "errado", "token-outro-par"])
def test_api_so_aceita_token_especifico_admin(cenario, settings, token):
    client, aula, ana, _ = cenario
    settings.TOKENS_ACEITOS = {"token-outro-par", ADMIN}
    item = comentario(aula, ana)
    assert api(client, aula, token=token).status_code == 401
    assert api(client, aula, item, token=token).status_code == 401
    item.refresh_from_db()
    assert not item.publico


def test_admin_ausente_falha_fechada(cenario, monkeypatch):
    client, aula, _, _ = cenario
    monkeypatch.delenv("TOKENS_ACEITOS_ADMIN")
    assert api(client, aula).status_code == 401


def test_admin_ve_privados_sem_email_e_publica_reverte(cenario, rede):
    client, aula, ana, beto = cenario
    item = comentario(aula, ana, "Dúvida para compartilhar")
    lista = api(client, aula)
    assert lista.status_code == 200
    assert lista.json()["itens"][0]["corpo"] == item.corpo
    assert "no-store" in lista["Cache-Control"]
    assert "email" not in lista.json()["itens"][0]
    assert api(client, aula, item).status_code == 200
    item.refresh_from_db()
    assert item.publico and item.moderador_id == "admin-opaco" and item.moderado_em
    dublar_sessao(rede, BETO)
    dublar_matricula(rede, BETO["email"])
    assert item.corpo in client.get(endereco(aula)).content.decode()
    assert api(client, aula, item, publico=False).status_code == 200
    assert item.corpo not in client.get(endereco(aula)).content.decode()
    dublar_sessao(rede, ANA)
    assert item.corpo in client.get(endereco(aula)).content.decode()


def test_admin_site_diferente_nao_le_nem_muda(cenario):
    client, aula, ana, _ = cenario
    item = comentario(aula, ana)
    assert api(client, aula, site="outro-site").json()["total"] == 0
    assert api(client, aula, item, site="outro-site").status_code == 404
    item.refresh_from_db()
    assert not item.publico


def test_visibilidade_exige_booleano_real(cenario):
    client, aula, ana, _ = cenario
    item = comentario(aula, ana)
    assert api(client, aula, item, publico="false").status_code == 422
    item.refresh_from_db()
    assert not item.publico


def test_texto_escapado_nome_sem_email_e_sem_cache(cenario):
    client, aula, ana, beto = cenario
    beto.nome_exibido = "beto@exemplo.com"
    beto.save()
    comentario(aula, beto, '<script>alert("segredo")</script>', True)
    r = client.get(endereco(aula))
    assert '<script>alert("segredo")</script>' not in r.content.decode()
    assert "&lt;script&gt;" in r.content.decode()
    assert "beto@exemplo.com" not in r.content.decode()
    assert "no-store" in r["Cache-Control"] and "Cookie" in r["Vary"]


def test_paginacao_so_conta_visiveis(cenario):
    client, aula, ana, beto = cenario
    for n in range(23):
        comentario(aula, ana, f"visivel-{n}")
    for n in range(25):
        comentario(aula, beto, f"oculto-{n}")
    r = client.get(endereco(aula), {"comentarios_pagina": "2"})
    assert r.context["comentarios"].paginator.count == 23
    assert len(r.context["comentarios"]) == 3
    assert "oculto-" not in r.content.decode()
