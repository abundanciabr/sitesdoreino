"""A vista Appmax lê o retrato publicado da fila sem criar outro estado."""

import json
import re

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.core import appmax, robos


DONO = "dono@exemplo.com"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
SESSAO = "http://identidade:8000/interno/sessao/completa"


@pytest.fixture
def fila_appmax(tmp_path, monkeypatch):
    pasta = tmp_path / "fila_embutida"
    (pasta / "eventos").mkdir(parents=True)
    dados = {
        "TAR-558": {
            "estado": "concluída",
            "titulo": "Aviso guardado",
            "motivo": "prova oficial da fila",
            "evidencia": "https://github.com/abundanciabr/sitesdoreino/pull/2000",
            "depende_de": ["TAR-557"],
        },
        "TAR-559": {
            "estado": "cancelada",
            "titulo": "Worker antigo",
            "motivo": "substituída pelo reconciliador",
        },
        "TAR-554": {
            "estado": "cancelada",
            "titulo": "Estorno antigo",
            "motivo": "escopo histórico cancelado",
        },
        "TAR-641": {
            "estado": "concluída",
            "titulo": "Estorno medido",
            "motivo": "prova histórica registrada",
        },
        "TAR-555": {
            "estado": "cancelada",
            "titulo": "Tela antiga",
            "motivo": "substituída pela tela atual",
        },
        "TAR-560": {
            "estado": "bloqueada",
            "titulo": "Processo dormente",
            "motivo": "esperando TAR-559",
            "depende_de": ["TAR-559"],
        },
        "TAR-615": {
            "estado": "reivindicada",
            "titulo": "Tela do cartão",
            "motivo": "sessão agent/checkout/cartao",
        },
    }
    (pasta / "estados.json").write_text(
        json.dumps(dados, ensure_ascii=False), encoding="utf-8"
    )
    monkeypatch.setattr(robos, "CANDIDATOS", (pasta,))
    return pasta, dados


@pytest.fixture
def dentro(monkeypatch, settings):
    monkeypatch.setenv("IDENTIDADE_API_URL", "http://identidade:8000/interno")
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    settings.ADMIN_EMAILS = DONO
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={"autenticado": True, "email": DONO, "nome_exibido": "Dono"},
        )
    )
    cliente = Client()
    cliente.defaults["HTTP_COOKIE"] = COOKIE
    return cliente


@respx.mock
def test_vista_appmax_mostra_sequencia_estado_dependencia_prova_e_fontes(
    fila_appmax, dentro
):
    # guarda: services/admin/apps/core/appmax.py:131
    resposta = dentro.get(reverse("appmax"))
    html = resposta.content.decode()

    assert resposta.status_code == 200
    assert "Vista Appmax" in html
    assert "Retrato publicado" in html
    assert "Consulta viva" in html
    assert "TAR-558" in html
    assert "concluída" in html
    assert "TAR-559" in html
    assert "cancelada" in html
    assert "TAR-554" in html
    assert "TAR-641" in html
    assert "TAR-555" in html
    assert "TAR-560" in html
    assert "TAR-711" in html
    assert "TAR-731" in html
    assert "TAR-730" in html
    assert "TAR-732" in html
    assert "TAR-641" in html
    assert "TAR-615" in html
    assert "Substituta" in html
    assert "<dt>Substituta</dt><dd>TAR-641</dd>" in html
    assert "<dt>Substituta</dt><dd>TAR-644</dd>" in html
    assert "<dt>Substituta</dt><dd>TAR-615</dd>" in html
    assert "TAR-557" in html
    assert "prova oficial da fila" in html
    assert "data-consulta-viva" in html
    cartao_560 = html.split('<p class="id-tarefa">TAR-560</p>', 1)[1].split("</li>", 1)[
        0
    ]
    assert "TAR-559" in cartao_560


@respx.mock
def test_vista_appmax_mostra_transicoes_apos_nova_leitura(fila_appmax, dentro):
    pasta, dados = fila_appmax
    primeira = dentro.get(reverse("appmax")).content.decode()
    assert "TAR-615" in primeira and "reivindicada" in primeira

    dados["TAR-615"]["estado"] = "bloqueada"
    dados["TAR-615"]["motivo"] = "aguardando prova"
    (pasta / "estados.json").write_text(
        json.dumps(dados, ensure_ascii=False), encoding="utf-8"
    )
    segunda = dentro.get(reverse("appmax")).content.decode()
    assert "TAR-615" in segunda
    assert "bloqueada" in segunda
    assert "aguardando prova" in segunda

    dados["TAR-615"]["estado"] = "na fila"
    dados["TAR-615"]["motivo"] = "devolvida para a fila após a tentativa"
    (pasta / "estados.json").write_text(
        json.dumps(dados, ensure_ascii=False), encoding="utf-8"
    )
    devolvida = dentro.get(reverse("appmax")).content.decode()
    assert "na fila" in devolvida
    assert "devolvida para a fila" in devolvida

    dados["TAR-615"]["estado"] = "concluída"
    dados["TAR-615"]["motivo"] = "aceite conferido"
    (pasta / "estados.json").write_text(
        json.dumps(dados, ensure_ascii=False), encoding="utf-8"
    )
    terceira = dentro.get(reverse("appmax")).content.decode()
    assert "concluída" in terceira
    assert "aceite conferido" in terceira


@respx.mock
def test_fonte_ausente_vira_nao_medido_com_recarregar(tmp_path, monkeypatch, dentro):
    monkeypatch.setattr(robos, "CANDIDATOS", (tmp_path / "ausente",))
    resposta = dentro.get(reverse("appmax"))
    html = re.sub(r"\s+", " ", resposta.content.decode())

    assert resposta.status_code == 200
    assert "não medido" in html
    assert "Recarregar" in html
    assert "Nenhuma tarefa Appmax encontrada" not in html


@respx.mock
def test_consulta_viva_falha_sem_apagar_retrato(fila_appmax, dentro):
    html = dentro.get(reverse("appmax")).content.decode()

    assert "retrato publicado" in html.lower()
    assert "consulta viva" in html.lower()
    assert "não medido" in html.lower()
    assert "recarregar" in html.lower()
