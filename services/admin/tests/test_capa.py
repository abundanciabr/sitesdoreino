"""A capa do painel de gestão tem teto de nove blocos e se recusa a crescer.

Plano §3: "a capa tem teto de nove blocos; realidade nova entra como cartão,
não como bloco". É a mesma disciplina da capa do painel do dono, que quebra
visivelmente em vez de crescer. Aqui o guarda mede o TEMPLATE: cada
`titulo-de-bloco` em `placar.html` é um bloco, e o teto é
`placar.TETO_DE_BLOCOS`. Quem precisar de um décimo bloco discute no plano,
não no template.

E o degrau 4 (parte 2): o placar de doze e as estrelas-guia aparecem na capa
e na pauta da reunião, cada número com o seu cartão, sem nota composta.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.core import placar, reuniao

TEMPLATE = Path(placar.__file__).parent / "templates" / "admin" / "placar.html"

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"
ALUNOS = "http://alunos:8000/api/alunos"
FILA = f"{ALUNOS}/pre-matriculas"
ALUNOS_LISTA = f"{ALUNOS}/matriculas"
HOJE = dt.date(2026, 9, 21)


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    monkeypatch.setenv("ALUNOS_API_URL", ALUNOS)
    monkeypatch.setenv("ALUNOS_API_TOKEN", "token-do-par-admin-alunos")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"
    monkeypatch.setattr(placar.timezone, "localdate", lambda: HOJE)
    monkeypatch.setattr(reuniao.timezone, "localdate", lambda: HOJE)


def _dentro() -> Client:
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "id-opaco-123",
                "nome_exibido": "Fulano",
                "papel": None,
                "email": DONO,
            },
        )
    )
    c = Client()
    c.defaults["HTTP_COOKIE"] = COOKIE
    return c


def _a_escola_responde():
    respx.get(FILA, params={"status": "aguardando"}).mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(FILA, params={"status": "recusada"}).mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(ALUNOS_LISTA).mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "status": "ativa",
                    "origem": "liberado",
                    "criada_em": "2026-09-10T12:00:00-03:00",
                    "virou_aluno_em": "2026-09-11T12:00:00-03:00",
                },
                {
                    "status": "ativa",
                    "origem": "liberado",
                    "criada_em": "2026-09-12T12:00:00-03:00",
                    "virou_aluno_em": "2026-09-13T12:00:00-03:00",
                },
            ],
        )
    )


def test_a_capa_tem_no_maximo_nove_blocos_e_o_plano_os_nomeia():
    blocos = re.findall(r'class="titulo-de-bloco', TEMPLATE.read_text(encoding="utf-8"))
    assert len(placar.BLOCOS_DA_CAPA) == placar.TETO_DE_BLOCOS == 9
    assert len(blocos) <= placar.TETO_DE_BLOCOS, (
        f"a capa tem {len(blocos)} blocos e o teto é {placar.TETO_DE_BLOCOS}: "
        "realidade nova entra como cartão, não como bloco (plano §3)"
    )


@respx.mock
def test_a_capa_mostra_os_doze_e_as_estrelas_sem_nota_composta():
    _a_escola_responde()
    html = _dentro().get(reverse("placar")).content.decode()
    assert "O placar de doze" in html
    assert "As estrelas-guia" in html
    assert "de 12 chegaram medidos" in html
    assert "100% (2 de 2 em 28 dias)" in html, "a conversão da fila, medida"
    assert "Quanto sobra por mês" in html and "Sem dados até o site vender" in html
    assert "/100" not in html, "nada de nota composta"


@respx.mock
def test_a_pauta_le_os_mesmos_doze():
    _a_escola_responde()
    html = _dentro().get(reverse("reuniao")).content.decode()
    assert "de 12 medidos hoje" in html
    assert "Quantas alunas chegaram a um resultado profissional?" in html
