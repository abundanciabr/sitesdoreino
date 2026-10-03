# tests/test_leads_consulta.py
# A consulta de contatos (somente leitura) que alimenta a tela /admin/contatos/:
# `GET /api/leads/leads` (lista) e `GET /api/leads/leads/{id}` (ficha).
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from apps.core.models import Lead, TimelineEvent

pytestmark = pytest.mark.django_db

BASE = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def token(settings):
    settings.TOKENS_ACEITOS = {"token-de-teste"}
    return "token-de-teste"


def _get(client, caminho, token="token-de-teste", **parametros):
    return client.get(
        caminho, parametros, HTTP_AUTHORIZATION=f"Bearer {token}"
    )


def _lead(email, *, site_id="site-a", dias=0, **campos):
    """Cria o lead e fixa o `created_at` (auto_now_add não aceita valor direto)."""
    lead = Lead.objects.create(site_id=site_id, email=email, **campos)
    Lead.objects.filter(pk=lead.pk).update(created_at=BASE + timedelta(days=dias))
    lead.refresh_from_db()
    return lead


def _evento(lead, nome, *, horas=0, payload=None, event_id=None):
    evento = TimelineEvent.objects.create(
        lead=lead, event=nome, payload=payload or {}, event_id=event_id
    )
    TimelineEvent.objects.filter(pk=evento.pk).update(
        occurred_at=BASE + timedelta(hours=horas)
    )
    return evento


# ------------------------------------------------------------------ a lista


def test_lista_exige_o_token(client, token):
    _lead("ana@example.com")
    assert client.get("/api/leads/leads").status_code == 401
    assert _get(client, "/api/leads/leads", token="token-errado").status_code == 401


def test_lista_vem_do_mais_novo_para_o_mais_antigo(client, token):
    _lead("velha@example.com", dias=0)
    _lead("nova@example.com", dias=2)
    _lead("meio@example.com", dias=1)

    corpo = _get(client, "/api/leads/leads").json()

    assert [i["email"] for i in corpo["itens"]] == [
        "nova@example.com",
        "meio@example.com",
        "velha@example.com",
    ]
    assert corpo["total"] == 3
    assert corpo["pagina"] == 1
    assert corpo["tem_mais"] is False


def test_item_da_lista_traz_os_campos_e_o_ultimo_evento(client, token):
    lead = _lead(
        "ana@example.com",
        name="Ana Souza",
        phone="11999990000",
        source="quiz-crivo",
        tags=["quiz", "quente"],
    )
    _evento(lead, "lead.upsert", horas=1)
    _evento(lead, "quiz.completado", horas=5)
    _evento(lead, "pedido.criado", horas=3)

    (item,) = _get(client, "/api/leads/leads").json()["itens"]

    assert item["id"] == str(lead.id)
    assert item["site_id"] == "site-a"
    assert item["nome"] == "Ana Souza"
    assert item["email"] == "ana@example.com"
    assert item["telefone"] == "11999990000"
    assert item["origem"] == "quiz-crivo"
    assert item["tags"] == ["quiz", "quente"]
    assert item["criado_em"].startswith("2026-10-01")
    # O último é o MAIS RECENTE pela data do evento, e não o último gravado.
    assert item["ultimo_evento"] == "quiz.completado"
    assert item["ultimo_evento_em"].startswith("2026-10-01T17:00")


def test_contato_sem_historico_tem_ultimo_evento_nulo(client, token):
    _lead("ana@example.com")

    (item,) = _get(client, "/api/leads/leads").json()["itens"]

    assert item["ultimo_evento"] is None
    assert item["ultimo_evento_em"] is None


def test_busca_acha_por_nome_email_e_telefone(client, token):
    _lead("ana@example.com", name="Ana Souza", phone="11999990000", dias=0)
    _lead("bruno@example.com", name="Bruno Lima", phone="21988887777", dias=1)

    def emails(q):
        itens = _get(client, "/api/leads/leads", q=q).json()["itens"]
        return [i["email"] for i in itens]

    assert emails("souza") == ["ana@example.com"]  # nome, sem diferenciar caixa
    assert emails("BRUNO@") == ["bruno@example.com"]  # e-mail
    assert emails("8888") == ["bruno@example.com"]  # telefone
    assert emails("ninguem") == []
    assert len(emails("")) == 2  # busca vazia não filtra
    assert len(emails("   ")) == 2


def test_filtro_por_site_e_por_tag(client, token):
    _lead("ana@example.com", site_id="site-a", tags=["quiz"], dias=0)
    _lead("ana@example.com", site_id="site-b", tags=["quiz", "pagou"], dias=1)
    _lead("bia@example.com", site_id="site-a", tags=["pagou"], dias=2)

    def achados(**filtros):
        itens = _get(client, "/api/leads/leads", **filtros).json()["itens"]
        return [(i["site_id"], i["email"]) for i in itens]

    assert achados(site_id="site-b") == [("site-b", "ana@example.com")]
    assert achados(tag="pagou") == [
        ("site-a", "bia@example.com"),
        ("site-b", "ana@example.com"),
    ]
    assert achados(site_id="site-a", tag="pagou") == [("site-a", "bia@example.com")]
    assert achados(tag="nao-existe") == []
    # A tag é inteira, não pedaço: "pag" não acha "pagou".
    assert achados(tag="pag") == []


def test_paginacao_corta_na_pagina_e_diz_se_ha_mais(client, token):
    for n in range(5):
        _lead(f"p{n}@example.com", dias=n)

    primeira = _get(client, "/api/leads/leads", por_pagina=2).json()
    segunda = _get(client, "/api/leads/leads", por_pagina=2, pagina=2).json()
    ultima = _get(client, "/api/leads/leads", por_pagina=2, pagina=3).json()
    alem = _get(client, "/api/leads/leads", por_pagina=2, pagina=4).json()

    assert [i["email"] for i in primeira["itens"]] == ["p4@example.com", "p3@example.com"]
    assert [i["email"] for i in segunda["itens"]] == ["p2@example.com", "p1@example.com"]
    assert [i["email"] for i in ultima["itens"]] == ["p0@example.com"]
    assert (primeira["total"], segunda["total"], ultima["total"]) == (5, 5, 5)
    assert (primeira["tem_mais"], segunda["tem_mais"], ultima["tem_mais"]) == (
        True,
        True,
        False,
    )
    assert alem["itens"] == []
    assert alem["tem_mais"] is False


def test_pagina_padrao_tem_cinquenta(client, token):
    for n in range(51):
        _lead(f"p{n}@example.com", dias=n)

    corpo = _get(client, "/api/leads/leads").json()

    assert len(corpo["itens"]) == 50
    assert corpo["por_pagina"] == 50
    assert corpo["total"] == 51
    assert corpo["tem_mais"] is True


@pytest.mark.parametrize(
    "parametros",
    [
        {"pagina": 0},
        {"pagina": -1},
        {"por_pagina": 0},
        {"por_pagina": 101},
        {"pagina": "abc"},
    ],
)
def test_pagina_invalida_e_422(client, token, parametros):
    assert _get(client, "/api/leads/leads", **parametros).status_code == 422


# ------------------------------------------------------------------ a ficha


def test_ficha_exige_o_token(client, token):
    lead = _lead("ana@example.com")
    assert client.get(f"/api/leads/leads/{lead.id}").status_code == 401


def test_ficha_traz_dados_origem_consentimento_e_linha_do_tempo(client, token):
    lead = _lead(
        "ana@example.com",
        name="Ana Souza",
        phone="11999990000",
        source="lp-certificacao",
        utm={"utm_source": "instagram", "utm_campaign": "outubro"},
        tags=["quiz"],
        consent={"email_marketing": True, "whatsapp": False},
    )
    id_do_evento = uuid.uuid4()
    _evento(lead, "lead.upsert", horas=1, payload={"email": "ana@example.com"})
    _evento(
        lead,
        "pagamento.aprovado",
        horas=9,
        payload={"valor": 497, "produto": "Escola"},
        event_id=id_do_evento,
    )
    _evento(lead, "pedido.criado", horas=4, payload={"valor": 497})

    resposta = _get(client, f"/api/leads/leads/{lead.id}")

    assert resposta.status_code == 200
    ficha = resposta.json()
    assert ficha["id"] == str(lead.id)
    assert ficha["site_id"] == "site-a"
    assert ficha["nome"] == "Ana Souza"
    assert ficha["email"] == "ana@example.com"
    assert ficha["telefone"] == "11999990000"
    assert ficha["origem"] == "lp-certificacao"
    assert ficha["utm"] == {"utm_source": "instagram", "utm_campaign": "outubro"}
    assert ficha["tags"] == ["quiz"]
    assert ficha["consentimento"] == {"email_marketing": True, "whatsapp": False}
    assert ficha["criado_em"].startswith("2026-10-01")
    assert ficha["atualizado_em"]
    # Linha do tempo: mais novo primeiro, com o payload inteiro.
    assert [e["evento"] for e in ficha["linha_do_tempo"]] == [
        "pagamento.aprovado",
        "pedido.criado",
        "lead.upsert",
    ]
    assert ficha["linha_do_tempo_total"] == 3
    pago = ficha["linha_do_tempo"][0]
    assert pago["payload"] == {"valor": 497, "produto": "Escola"}
    assert pago["event_id"] == str(id_do_evento)
    assert pago["ocorrido_em"].startswith("2026-10-01T21:00")
    assert ficha["linha_do_tempo"][2]["event_id"] is None


def test_ficha_so_mostra_a_linha_do_tempo_da_propria_pessoa(client, token):
    ana = _lead("ana@example.com")
    bia = _lead("bia@example.com")
    _evento(ana, "quiz.completado")
    _evento(bia, "pedido.criado")

    ficha = _get(client, f"/api/leads/leads/{ana.id}").json()

    assert [e["evento"] for e in ficha["linha_do_tempo"]] == ["quiz.completado"]


def test_ficha_sem_historico_devolve_linha_do_tempo_vazia(client, token):
    lead = _lead("ana@example.com")

    ficha = _get(client, f"/api/leads/leads/{lead.id}").json()

    assert ficha["linha_do_tempo"] == []
    assert ficha["linha_do_tempo_total"] == 0


def test_ficha_corta_a_linha_do_tempo_mas_diz_o_total(client, token, monkeypatch):
    from apps.core import api

    monkeypatch.setattr(api, "LIMITE_DA_LINHA_DO_TEMPO", 2)
    lead = _lead("ana@example.com")
    _evento(lead, "lead.upsert", horas=1)
    _evento(lead, "pedido.criado", horas=2)
    _evento(lead, "pagamento.aprovado", horas=3)

    ficha = _get(client, f"/api/leads/leads/{lead.id}").json()

    assert [e["evento"] for e in ficha["linha_do_tempo"]] == [
        "pagamento.aprovado",
        "pedido.criado",
    ]
    assert ficha["linha_do_tempo_total"] == 3


def test_ficha_de_contato_inexistente_e_404(client, token):
    assert _get(client, f"/api/leads/leads/{uuid.uuid4()}").status_code == 404


def test_ficha_com_identificador_que_nao_e_uuid_e_404(client, token):
    assert _get(client, "/api/leads/leads/nao-e-uuid").status_code == 404


def test_consulta_nao_grava_nada(client, token):
    lead = _lead("ana@example.com")
    _evento(lead, "lead.upsert")

    _get(client, "/api/leads/leads")
    _get(client, f"/api/leads/leads/{lead.id}")

    assert Lead.objects.count() == 1
    assert TimelineEvent.objects.count() == 1
