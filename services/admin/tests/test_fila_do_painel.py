"""`painel/fila.json` (07/09/2026) — a fila dos robôs chegando ao painel do dono.

O que estes guardas protegem:

1. **A rota SERVE o que o build materializou** (`fila_embutida/estados.json`)
   e traduz com as MESMAS funções de `apps.core.robos` — nunca uma segunda
   definição de situação, selo ou lugar (`armadilhas/379`).
2. **Só as tarefas ABERTAS aparecem.** `concluída` e `cancelada` já têm
   desfecho; a aba "Prioridades" não é história.
3. **`para_o_dono` distingue as duas paradas.** `espera: mantenedor` é dele;
   `espera: fila` se destrava sozinha.
4. **`area` falha ABERTO.** `toca` sem célula reconhecida em
   `painel/areas.json`, ou `areas.json` ausente, nunca faz a tarefa sumir —
   vira `area: null` e um `aviso`, nunca 500 (`armadilhas/289`).
5. **Sempre 200, como `divida.json`** — fila ausente é `erro` no corpo, nunca
   um painel inteiro quebrado.
6. **A porta protege esta rota como qualquer outra** desta célula.
"""

import json

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.core import fila_do_painel as modulo
from apps.core import painel as painel_modulo
from apps.core import robos

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


def fila_de_mentira(tmp_path, monkeypatch, estados: dict):
    """Uma fila embutida como o deploy a deixaria — só `estados.json` importa
    aqui, o resto (`eventos/`, `regua.json`...) é assunto da aba "Os robôs"."""
    pasta = tmp_path / "fila_embutida"
    pasta.mkdir()
    (pasta / "estados.json").write_text(
        json.dumps(estados, ensure_ascii=False), encoding="utf-8"
    )
    monkeypatch.setattr(robos, "CANDIDATOS", (pasta,))
    return pasta


def painel_de_mentira(tmp_path, monkeypatch, areas=None):
    """Uma pasta de painel como `diretorio_do_painel()` reconheceria."""
    pasta = tmp_path / "painel_de_mentira"
    pasta.mkdir()
    (pasta / "painel.html").write_text("<html></html>", encoding="utf-8")
    if areas is not None:
        (pasta / "areas.json").write_text(
            json.dumps(areas, ensure_ascii=False), encoding="utf-8"
        )
    monkeypatch.setattr(painel_modulo, "CANDIDATOS", (pasta,))
    return pasta


AREAS_DE_MENTIRA = {
    "areas": [
        {
            "id": "vendas",
            "nome": "Vendas",
            "diz": "o que traz gente e dinheiro",
            "celulas": ["encomendas", "checkout"],
        },
        {
            "id": "site",
            "nome": "O site",
            "diz": "as páginas que todo mundo vê",
            "celulas": ["funil", "identidade"],
        },
    ]
}

ESTADOS_DE_MENTIRA = {
    "TAR-001": {
        "estado": "concluída",
        "motivo": "https://github.com/x/y/pull/500",
        "titulo": "Já terminou",
        "toca": ["admin"],
    },
    "TAR-002": {
        "estado": "cancelada",
        "motivo": "não faz mais sentido",
        "titulo": "Foi cancelada",
        "toca": ["admin"],
    },
    "TAR-003": {
        "estado": "na fila",
        "titulo": "Esperando um robô",
        "importancia": 85,
        "toca": ["encomendas"],
        "o_que_muda": "o mural fica mais rápido",
    },
    "TAR-004": {
        "estado": "bloqueada",
        "espera": "mantenedor",
        "motivo": "aguardando despacho do mantenedor",
        "titulo": "Só ele destrava",
        "toca": ["infra"],
    },
    "TAR-005": {
        "estado": "bloqueada",
        "espera": "fila",
        "motivo": "esperando TAR-003",
        "titulo": "A corrente destrava sozinha",
        "toca": ["admin"],
    },
}


# ────────────────────────────────────────────── 1. forma, filtro, para_o_dono


@respx.mock
def test_so_as_tarefas_abertas_aparecem_na_forma_do_contrato(tmp_path, monkeypatch):
    fila_de_mentira(tmp_path, monkeypatch, ESTADOS_DE_MENTIRA)
    painel_de_mentira(tmp_path, monkeypatch, AREAS_DE_MENTIRA)

    resposta = _dentro().get(reverse("painel_fila"))
    assert resposta.status_code == 200
    assert resposta["Content-Type"] == "application/json"
    dados = json.loads(resposta.content)

    assert dados["erro"] is None
    assert dados["aviso"] is None
    ids = [t["id"] for t in dados["tarefas"]]
    assert ids == [
        "TAR-003",
        "TAR-004",
        "TAR-005",
    ], "concluída/cancelada vazaram, ou a ordem não é por id"

    por_id = {t["id"]: t for t in dados["tarefas"]}

    dele = por_id["TAR-004"]
    assert dele["para_o_dono"] is True
    assert dele["situacao"] == "Esperando uma decisão sua"
    assert dele["motivo"] == "aguardando despacho do mantenedor"

    corrente = por_id["TAR-005"]
    assert corrente["para_o_dono"] is False
    assert corrente["situacao"] == "Esperando outra tarefa terminar"

    na_fila = por_id["TAR-003"]
    assert na_fila["situacao"] == "Esperando um robô pegar"
    assert na_fila["para_o_dono"] is False
    assert na_fila["o_que_muda"] == "o mural fica mais rápido"
    assert na_fila["motivo"] is None


@respx.mock
def test_selo_e_importancia_vem_de_robos_py_sem_reimplementar_limiares(
    tmp_path, monkeypatch
):
    fila_de_mentira(
        tmp_path,
        monkeypatch,
        {
            "TAR-100": {
                "estado": "na fila",
                "titulo": "alta",
                "importancia": 85,
                "toca": [],
            },
            # bool é int em Python — o guarda de `importancia_declarada` recusa.
            "TAR-101": {
                "estado": "na fila",
                "titulo": "bool não é nota",
                "importancia": True,
                "toca": [],
            },
        },
    )
    painel_de_mentira(tmp_path, monkeypatch)

    dados = json.loads(_dentro().get(reverse("painel_fila")).content)
    por_id = {t["id"]: t for t in dados["tarefas"]}

    assert por_id["TAR-100"]["importancia"] == 85
    assert por_id["TAR-100"]["selo"] == {"texto": "custa caro hoje", "classe": "alta"}

    assert por_id["TAR-101"]["importancia"] is None
    assert por_id["TAR-101"]["selo"]["classe"] == "sem-nota"


# ──────────────────────────────────────────────────────── 2. resolução de área


@respx.mock
def test_area_resolvida_pela_primeira_celula_do_toca(tmp_path, monkeypatch):
    fila_de_mentira(
        tmp_path,
        monkeypatch,
        {
            "TAR-200": {
                "estado": "na fila",
                "titulo": "vendas",
                "toca": ["encomendas"],
            },
            "TAR-201": {
                "estado": "na fila",
                "titulo": "site",
                "toca": ["services/funil"],
            },
            "TAR-202": {
                "estado": "na fila",
                "titulo": "orfa",
                "toca": ["nome-que-nao-existe"],
            },
            "TAR-203": {"estado": "na fila", "titulo": "sem toca", "toca": []},
        },
    )
    painel_de_mentira(tmp_path, monkeypatch, AREAS_DE_MENTIRA)

    dados = json.loads(_dentro().get(reverse("painel_fila")).content)
    por_id = {t["id"]: t for t in dados["tarefas"]}

    assert por_id["TAR-200"]["area"] == "vendas"
    assert (
        por_id["TAR-201"]["area"] == "site"
    ), "services/funil devia normalizar para funil"
    assert por_id["TAR-202"]["area"] is None, "célula desconhecida some, não quebra"
    assert por_id["TAR-203"]["area"] is None
    assert por_id["TAR-203"]["onde"] == []
    assert dados["aviso"] is None


# ────────────────────────────────────────────── 3. sem areas.json, sem fila


@respx.mock
def test_sem_areas_json_todas_ficam_sem_area_e_o_aviso_aparece(tmp_path, monkeypatch):
    fila_de_mentira(tmp_path, monkeypatch, ESTADOS_DE_MENTIRA)
    painel_de_mentira(tmp_path, monkeypatch, areas=None)  # painel.html sem areas.json

    resposta = _dentro().get(reverse("painel_fila"))
    dados = json.loads(resposta.content)

    assert resposta.status_code == 200
    assert dados["erro"] is None
    assert dados["aviso"] == (
        "painel/areas.json não veio nesta imagem: as tarefas chegam sem área"
    )
    assert all(t["area"] is None for t in dados["tarefas"])


@respx.mock
def test_sem_fila_vira_erro_nunca_500_e_tarefas_vazia(tmp_path, monkeypatch):
    monkeypatch.setattr(robos, "CANDIDATOS", (tmp_path / "nao-existe",))
    painel_de_mentira(tmp_path, monkeypatch, AREAS_DE_MENTIRA)

    resposta = _dentro().get(reverse("painel_fila"))
    dados = json.loads(resposta.content)

    assert resposta.status_code == 200, "fila ausente não pode derrubar o painel"
    assert dados["erro"] == "a fila dos robôs não veio nesta imagem"
    assert dados["tarefas"] == []


@respx.mock
def test_estados_json_ilegivel_tambem_vira_erro_declarado(tmp_path, monkeypatch):
    pasta = tmp_path / "fila_embutida"
    pasta.mkdir()
    (pasta / "estados.json").write_text("isto não é json{{{", encoding="utf-8")
    monkeypatch.setattr(robos, "CANDIDATOS", (pasta,))
    painel_de_mentira(tmp_path, monkeypatch, AREAS_DE_MENTIRA)

    dados = json.loads(_dentro().get(reverse("painel_fila")).content)
    assert dados["erro"] == "a fila dos robôs não veio nesta imagem"
    assert dados["tarefas"] == []


# ───────────────────────────────────────────── 4. cabeçalho e porta


@respx.mock
def test_nunca_e_guardado_em_cache(tmp_path, monkeypatch):
    fila_de_mentira(tmp_path, monkeypatch, ESTADOS_DE_MENTIRA)
    painel_de_mentira(tmp_path, monkeypatch, AREAS_DE_MENTIRA)

    assert _dentro().get(reverse("painel_fila"))["Cache-Control"] == "no-store"


def test_sem_sessao_a_rota_nao_entrega_a_fila():
    """Ela não está em `CAMINHOS_ISENTOS`, e isso é medido de fora."""
    resposta = Client().get("/painel/fila.json")
    assert resposta.status_code == 302
    assert "/entrar/google" in resposta["Location"]


# ─────────────────────────────────────────────────────── a função pura, direto


def test_a_funcao_pura_nao_levanta_com_dados_estranhos_no_meio(tmp_path):
    """Uma tarefa que não é um dicionário (build antigo, campo corrompido)
    desaparece da lista em vez de derrubar a resposta inteira."""
    pasta = tmp_path / "fila_embutida"
    pasta.mkdir()
    (pasta / "estados.json").write_text(
        json.dumps({"TAR-900": "isto deveria ser um objeto"}), encoding="utf-8"
    )
    resultado = modulo.fila_para_o_painel(pasta, None)
    assert resultado["erro"] is None
    assert resultado["tarefas"] == []
