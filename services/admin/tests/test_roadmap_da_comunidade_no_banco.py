"""A foto da Comunidade nasce privada e visual, inclusive no banco já existente."""

import re
from importlib import import_module
from pathlib import Path

import httpx
import pytest
import respx
from django.apps import apps
from django.test import Client

from apps.core import documentos
from apps.core.models import Documento, VersaoDoDocumento

pytestmark = pytest.mark.django_db
NOME = "roadmap-da-comunidade"
MIGRACAO = import_module("apps.core.migrations.0032_semear_roadmap_da_comunidade")
SEMENTE = Path(__file__).resolve().parents[3] / "documentos" / f"{NOME}.md"


def test_instalacao_nova_ja_tem_o_roadmap_privado_em_formato_pagina():
    documento = Documento.objects.get(nome=NOME)

    assert documento.publico is False
    assert documento.formato == "pagina"
    assert documento.corpo.startswith("<!doctype html>")


def test_migracao_semeia_o_roadmap_no_banco_que_ja_existia():
    Documento.objects.filter(nome=NOME).delete()

    MIGRACAO.semear_roadmap_da_comunidade(apps, None)

    documento = Documento.objects.get(nome=NOME)
    assert documento.publico is False
    assert documento.formato == "pagina"
    assert "As peças principais estão no ar" in documento.corpo


def test_migracao_formata_a_semente_intacta_que_a_0003_ja_importou():
    Documento.objects.filter(nome=NOME).delete()
    assert documentos.semear_documento(Documento, NOME) is True
    assert Documento.objects.get(nome=NOME).formato == "texto"

    MIGRACAO.semear_roadmap_da_comunidade(apps, None)

    assert Documento.objects.get(nome=NOME).formato == "pagina"


def test_migracao_nao_altera_edicao_do_mantenedor():
    Documento.objects.filter(nome=NOME).update(
        titulo="Minha versão", corpo="Meu texto", formato="texto", ordem=77
    )

    MIGRACAO.semear_roadmap_da_comunidade(apps, None)

    documento = Documento.objects.get(nome=NOME)
    assert (documento.titulo, documento.corpo, documento.formato, documento.ordem) == (
        "Minha versão",
        "Meu texto",
        "texto",
        77,
    )


def test_migracao_preserva_gesto_do_editor_mesmo_com_corpo_igual_a_semente():
    documento = Documento.objects.get(nome=NOME)
    documento.formato = "texto"
    documento.save(update_fields=["formato"])
    VersaoDoDocumento.objects.create(
        documento=documento,
        titulo=documento.titulo,
        publico=documento.publico,
        ordem=documento.ordem,
        corpo=documento.corpo,
        salvo_por="mantenedor",
        gesto="escolheu texto pela tela",
    )

    MIGRACAO.semear_roadmap_da_comunidade(apps, None)

    documento.refresh_from_db()
    assert documento.formato == "texto"
    assert documento.versoes.count() == 1


def test_roadmap_e_moldura_nao_existem_para_visitante():
    for endereco in (f"/docs/{NOME}", f"/docs/{NOME}/moldura"):
        resposta = Client().get(endereco)
        assert resposta.status_code == 404
        assert b"<svg" not in resposta.content
    resposta = Client().get(f"/documentos/{NOME}")
    assert resposta.status_code == 302
    assert "entrar" in resposta["Location"]


@respx.mock
def test_administrador_le_a_pagina_na_moldura_com_sandbox(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", "http://identidade:8000/interno")
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-teste")
    settings.ADMIN_EMAILS = "dono@exemplo.com"
    respx.get("http://identidade:8000/interno/sessao/completa").mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "id-do-teste",
                "nome_exibido": "Mantenedor",
                "papel": None,
                "email": settings.ADMIN_EMAILS,
            },
        )
    )
    cliente = Client(HTTP_COOKIE="meshcraft_sessao=sessao-do-teste")
    resposta = cliente.get(f"/documentos/{NOME}")
    assert resposta.status_code == 200
    moldura = re.search(r"<iframe\b[^>]*>", resposta.content.decode())
    assert moldura is not None
    assert 'sandbox="allow-scripts allow-popups allow-forms"' in moldura.group()
    assert "allow-same-origin" not in moldura.group()
    resposta = cliente.get(f"/documentos/{NOME}/moldura")
    assert resposta.status_code == 200
    assert resposta.content.decode().startswith(Documento.objects.get(nome=NOME).corpo)
    assert "frame-ancestors 'self'" in resposta["Content-Security-Policy"]


def test_html_embutido_sem_script_e_figuras_com_descricao_acessivel():
    corpo = documentos.de_texto(NOME, SEMENTE.read_text(encoding="utf-8")).corpo
    assert '<html lang="pt-BR">' in corpo
    assert 'name="viewport"' in corpo
    assert "<script" not in corpo.lower()
    assert "<link" not in corpo.lower()
    assert "@import" not in corpo.lower()
    figuras = re.findall(r"<svg\b.*?</svg>", corpo, re.DOTALL)
    assert figuras
    for figura in figuras:
        assert 'role="img"' in figura
        assert "aria-labelledby=" in figura
        assert "<title " in figura and "<desc " in figura
    assert len(re.findall(r'class="card bloco"', corpo)) == 10
    assert len(re.findall(r'class="linha-grafico"', corpo)) == 10
