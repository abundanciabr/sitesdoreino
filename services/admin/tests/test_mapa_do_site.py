"""A tela `/admin/mapa/` — o mapa do site (30/08/2026).

O que estes guardas protegem:

1. **A tela serve o arquivo do repositório** (`painel/mapa-do-site.json`), e não
   uma lista própria. Uma segunda lista aqui dentro seria a duplicação que o
   `CLAUDE.md` proíbe — e o dia em que as duas divergissem, o dono estaria
   olhando a planta errada da casa.
2. **Nenhum endereço some no caminho**: todo título do arquivo chega ao HTML.
   Uma linha que some não deixa rastro — é a pior forma de perder um fato.
3. **Molde não vira link.** `/forum/t/<int:topico_id>` não é um lugar; oferecê-lo
   como link manda o dono para um 404 e ele conclui que o site quebrou.
4. **Mapa ausente se DECLARA** (500 + explicação), nunca vira página vazia — a
   mesma lei do painel ausente. "Este site não tem endereço nenhum" seria a
   mentira mais convincente que esta tela poderia contar.
5. **A porta continua sendo a porta**: sem crachá, esta página não abre.
"""

import json

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.core import mapa_do_site

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


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


def _arquivo() -> dict:
    caminho = mapa_do_site.arquivo_do_mapa()
    assert caminho is not None, (
        "o mapa do site não foi encontrado — em produção ele vem em "
        "`painel_embutido/`, num checkout em `painel/`. Se este assert falhou, "
        "a tela do dono abriria em 500."
    )
    return json.loads(caminho.read_text(encoding="utf-8"))


@respx.mock
def test_a_pagina_abre_e_agrupa_por_quem_consegue_ver():
    resposta = _dentro().get(reverse("mapa_do_site"))
    assert resposta.status_code == 200
    html = resposta.content.decode()
    for titulo in ("Para quem só visita", "Para quem é aluno", "Para você"):
        assert titulo in html
    assert "Só para as máquinas" in html


@respx.mock
def test_nenhum_endereco_do_arquivo_some_da_tela():
    """Todo título declarado chega ao HTML — inclusive os gestos, dentro do
    `<details>`. Uma entrada que some não deixa rastro nenhum."""
    html = _dentro().get(reverse("mapa_do_site")).content.decode()
    sumidos = [e["titulo"] for e in _arquivo()["enderecos"] if e["titulo"] not in html]
    assert not sumidos, f"sumiram da tela: {sumidos}"


@respx.mock
def test_a_conta_da_tela_e_a_do_arquivo():
    """O número grande da capa é contado do arquivo, nunca digitado."""
    resposta = _dentro().get(reverse("mapa_do_site"))
    assert resposta.context["total"] == len(_arquivo()["enderecos"])
    # As três contas da capa são DISJUNTAS e somam o total. Se um dia deixarem
    # de somar, é porque uma entrada caiu em duas — e o dono estaria contando
    # a mesma página duas vezes na tela.
    assert (
        resposta.context["total_telas"]
        + resposta.context["total_gestos"]
        + resposta.context["total_maquina"]
        == resposta.context["total"]
    )
    assert not resposta.context["orfas"], (
        "entrada com um público que a tela não desenha: ela apareceria na "
        "seção 'sem grupo' em vez de sumir, mas o lugar de consertar é o mapa"
    )


@respx.mock
def test_molde_nao_vira_link_e_exemplo_vira():
    html = _dentro().get(reverse("mapa_do_site")).content.decode()
    assert 'href="/forum/t/' not in html, "molde oferecido como link dá 404"
    assert 'href="/forum/a/avisos"' in html, "o exemplo concreto é clicável"
    assert 'href="/forum/"' in html, "o endereço concreto é clicável"


@respx.mock
def test_gesto_nao_vira_link():
    """Clicar num gesto não pode ser possível: alguns MUDAM a vida de alguém."""
    html = _dentro().get(reverse("mapa_do_site")).content.decode()
    assert 'href="/admin/escola/alunos/decidir"' not in html
    assert "/admin/escola/alunos/decidir" in html, "mas ele está no mapa"


@respx.mock
def test_mapa_ausente_diz_isso_em_voz_alta(monkeypatch):
    monkeypatch.setattr(mapa_do_site, "diretorio_do_painel", lambda: None)
    resposta = _dentro().get(reverse("mapa_do_site"))
    assert resposta.status_code == 500
    assert "não veio nesta versão" in resposta.content.decode()


@respx.mock
def test_arquivo_torto_nao_vira_mapa_pela_metade(monkeypatch, tmp_path):
    torto = tmp_path / "mapa-do-site.json"
    torto.write_text('{"enderecos": ', encoding="utf-8")
    monkeypatch.setattr(mapa_do_site, "arquivo_do_mapa", lambda: torto)
    resposta = _dentro().get(reverse("mapa_do_site"))
    assert resposta.status_code == 500


@respx.mock
def test_sem_cracha_a_pagina_nao_abre():
    """Quem não passou pela porta não vê a planta da casa."""
    respx.get(SESSAO).mock(
        return_value=httpx.Response(200, json={"autenticado": False})
    )
    resposta = Client().get(reverse("mapa_do_site"))
    assert resposta.status_code != 200
