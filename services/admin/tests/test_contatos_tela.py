"""As telas de contatos de ponta a ponta (`/admin/contatos/`, 03/10/2026).

O `test_contatos.py` prova as funções da tela com a `leads` trocada por um
dublê. Este prova o que o dublê não alcança: o caminho inteiro, da porta
(`porta.py`) até o HTML, com a `leads` respondendo pela rede de mentira.

O que cada grupo protege:

1. **Lista e ficha em português.** Nome de evento técnico nunca chega à tela.
2. **A procura e a página chegam à `leads`.** O que a pessoa digitou é o que é
   perguntado, e o link da página seguinte carrega a procura.
3. **Não perguntei não é não há ninguém.** `leads` fora do ar ou sem o par de
   senhas: a tela diz isso e nenhuma lista aparece.
4. **Só o dono e os administradores entram.** Sem sessão, login; sessão fora da
   lista e crachá só de equipe recebem 404, e o menu acende "Contatos".
"""

from __future__ import annotations

import uuid

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
LEADS = "http://leads:8000/api/leads"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"

ANA = "24e45be2-77bb-4a32-a388-78d2ce9adcad"
INEXISTENTE = "7c9d2f55-0b1e-4a4c-9d0a-3f1c6a2b8e10"


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    monkeypatch.setenv("LEADS_API_URL", LEADS)
    monkeypatch.setenv("LEADS_API_TOKEN", "token-do-par-admin-leads")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


def _dentro(email: str = DONO) -> Client:
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "id-opaco-123",
                "nome_exibido": "Fulano",
                "papel": None,
                "email": email,
            },
        )
    )
    # A ficha completa também pergunta pelas oportunidades do contato
    # (`tests/test_ficha_completa.py` cobre essa parte); aqui, nenhuma.
    respx.get(f"{LEADS}/crm").mock(
        return_value=httpx.Response(
            200, json={"itens": [], "resumo": {}, "total": 0, "pagina": 1, "tem_mais": False}
        )
    )
    c = Client()
    c.defaults["HTTP_COOKIE"] = COOKIE
    return c


def _pagina(itens, *, total=None, pagina=1, tem_mais=False) -> dict:
    return {
        "itens": itens,
        "pagina": pagina,
        "por_pagina": 50,
        "total": len(itens) if total is None else total,
        "tem_mais": tem_mais,
    }


def _ana(**mudancas) -> dict:
    contato = {
        "id": ANA,
        "nome": "Ana Souza",
        "email": "ana@exemplo.com",
        "telefone": "11999990000",
        "origem": "pagina-de-venda",
        "site_id": "principal",
        "tags": ["quente"],
        "criado_em": "2026-10-03T13:00:00Z",
        "ultimo_evento": "pix.expirado",
        "ultimo_evento_em": "2026-10-03T14:00:00Z",
    }
    contato.update(mudancas)
    return contato


def _ficha(**mudancas) -> dict:
    ficha = {
        "id": ANA,
        "nome": "Ana Souza",
        "email": "ana@exemplo.com",
        "telefone": "11999990000",
        "origem": "pagina-de-venda",
        "site_id": "principal",
        "tags": ["quente", "quiz"],
        "consentimento": {"email_marketing": True, "whatsapp": False},
        "utm": {"utm_source": "instagram"},
        "criado_em": "2026-10-03T13:00:00Z",
        "atualizado_em": "2026-10-03T15:00:00Z",
        "linha_do_tempo_total": 6,
        "linha_do_tempo": [
            {
                "evento": "pix.expirado",
                "ocorrido_em": "2026-10-03T14:30:00Z",
                "payload": {"total_cents": 49700, "method": "pix"},
            },
            {
                "evento": "pedido.criado",
                "ocorrido_em": "2026-10-03T14:00:00Z",
                "payload": {
                    "total_cents": 49700,
                    "items": [{"name": "Curso Abundância"}],
                },
            },
            {
                "evento": "pagamento.aprovado",
                "ocorrido_em": "2026-10-03T14:10:00Z",
                "payload": {"amount_cents": 49700, "method": "card"},
            },
            {
                "evento": "pagamento.recusado",
                "ocorrido_em": "2026-10-03T13:50:00Z",
                "payload": {"amount_cents": 49700, "method": "card"},
            },
            {
                "evento": "quiz.completado",
                "ocorrido_em": "2026-10-03T13:30:00Z",
                "payload": {},
            },
            {
                "evento": "lead.upsert",
                "ocorrido_em": "2026-10-03T13:00:00Z",
                "payload": {},
            },
        ],
    }
    ficha.update(mudancas)
    return ficha


# ---------------------------------------------------------------------------
# 1. Lista e ficha em português
# ---------------------------------------------------------------------------


@respx.mock
def test_lista_mostra_quem_deixou_o_contato_e_o_ultimo_passo():
    cliente = _dentro()
    rota = respx.get(f"{LEADS}/leads").mock(
        return_value=httpx.Response(200, json=_pagina([_ana()]))
    )

    r = cliente.get(reverse("contatos"))

    corpo = r.content.decode()
    assert r.status_code == 200
    assert "Ana Souza" in corpo
    assert "ana@exemplo.com" in corpo
    assert f"/contatos/{ANA}/" in corpo
    assert "Pix venceu sem pagar" in corpo
    assert "pix.expirado" not in corpo
    assert rota.calls.last.request.headers["authorization"] == (
        "Bearer token-do-par-admin-leads"
    )


@respx.mock
def test_lista_verdadeiramente_vazia_diz_que_o_zero_foi_medido():
    cliente = _dentro()
    respx.get(f"{LEADS}/leads").mock(
        return_value=httpx.Response(200, json=_pagina([]))
    )

    r = cliente.get(reverse("contatos"))

    assert r.status_code == 200
    assert "Ainda não há contatos vindos dos quizzes" in r.content.decode()


@respx.mock
def test_ficha_traz_dados_origem_tags_e_a_linha_do_tempo_em_portugues():
    cliente = _dentro()
    respx.get(f"{LEADS}/leads/{ANA}").mock(
        return_value=httpx.Response(200, json=_ficha())
    )

    r = cliente.get(reverse("contato", args=[uuid.UUID(ANA)]))

    corpo = r.content.decode()
    assert r.status_code == 200
    assert "Ana Souza" in corpo
    assert "ana@exemplo.com" in corpo
    assert "11999990000" in corpo
    assert "pagina-de-venda" in corpo
    assert "quente" in corpo and "quiz" in corpo
    for rotulo in (
        "Fez pedido",
        "Pagou",
        "Pagamento recusado",
        "Pix venceu sem pagar",
        "Respondeu o quiz",
        "Deixou o contato",
    ):
        assert rotulo in corpo
    for tecnico in ("pix.expirado", "pedido.criado", "pagamento.aprovado", "lead.upsert"):
        assert tecnico not in corpo
    assert "R$ 497,00" in corpo
    assert "Curso Abundância" in corpo
    # A leads entrega os 6 mais recentes de 6: nada a avisar sobre corte.
    assert "Mostrando" not in corpo


@respx.mock
def test_ficha_com_evento_desconhecido_nao_mostra_o_codigo_interno():
    cliente = _dentro()
    ficha = _ficha(
        linha_do_tempo=[
            {
                "evento": "robo.inventou_isto",
                "ocorrido_em": "2026-10-03T14:00:00Z",
                "payload": {"token": "segredo-do-payload"},
            }
        ],
        linha_do_tempo_total=1,
    )
    respx.get(f"{LEADS}/leads/{ANA}").mock(return_value=httpx.Response(200, json=ficha))

    corpo = cliente.get(reverse("contato", args=[uuid.UUID(ANA)])).content.decode()

    assert "Outra atividade" in corpo
    assert "robo.inventou_isto" not in corpo
    assert "segredo-do-payload" not in corpo


@respx.mock
def test_ficha_diz_quando_a_linha_do_tempo_foi_cortada():
    cliente = _dentro()
    ficha = _ficha(linha_do_tempo_total=80)
    respx.get(f"{LEADS}/leads/{ANA}").mock(return_value=httpx.Response(200, json=ficha))

    corpo = cliente.get(reverse("contato", args=[uuid.UUID(ANA)])).content.decode()

    assert "Mostrando 6 das 80 atividades" in corpo


@respx.mock
def test_ficha_de_quem_nunca_fez_nada_diz_que_nao_ha_atividade():
    cliente = _dentro()
    ficha = _ficha(linha_do_tempo=[], linha_do_tempo_total=0)
    respx.get(f"{LEADS}/leads/{ANA}").mock(return_value=httpx.Response(200, json=ficha))

    r = cliente.get(reverse("contato", args=[uuid.UUID(ANA)]))

    assert r.status_code == 200
    assert "Ainda não há atividades registradas" in r.content.decode()


# ---------------------------------------------------------------------------
# 2. A procura e a página chegam à leads
# ---------------------------------------------------------------------------


@respx.mock
def test_a_procura_e_os_filtros_vao_na_pergunta_e_voltam_no_link_da_pagina():
    cliente = _dentro()
    rota = respx.get(f"{LEADS}/leads").mock(
        return_value=httpx.Response(
            200, json=_pagina([_ana()], total=120, tem_mais=True)
        )
    )

    r = cliente.get(
        reverse("contatos"), {"q": " ana ", "tag": "quente", "site_id": "principal"}
    )

    params = dict(rota.calls.last.request.url.params)
    assert params["q"] == "ana"
    assert params["tag"] == "quente"
    assert params["site_id"] == "principal"
    assert params["pagina"] == "1"
    assert params["origem"] == "quiz"
    corpo = r.content.decode()
    assert "Contatos 1 a 1, de 120" in corpo
    assert "pagina=2" in corpo
    assert "q=ana" in corpo and "tag=quente" in corpo


@respx.mock
def test_pagina_do_endereco_chega_a_leads_e_lixo_vira_a_primeira():
    cliente = _dentro()
    rota = respx.get(f"{LEADS}/leads").mock(
        return_value=httpx.Response(
            200, json=_pagina([_ana()], total=120, pagina=3, tem_mais=True)
        )
    )

    corpo = cliente.get(reverse("contatos"), {"pagina": "3"}).content.decode()

    assert rota.calls.last.request.url.params["pagina"] == "3"
    assert "Mais novos" in corpo and "Mais antigos" in corpo

    cliente.get(reverse("contatos"), {"pagina": "abc"})
    assert rota.calls.last.request.url.params["pagina"] == "1"


@respx.mock
def test_procura_sem_resultado_nao_diz_que_a_casa_esta_vazia():
    cliente = _dentro()
    respx.get(f"{LEADS}/leads").mock(
        return_value=httpx.Response(200, json=_pagina([]))
    )

    corpo = cliente.get(reverse("contatos"), {"q": "ninguem"}).content.decode()

    assert "Nenhum contato casou com a sua procura" in corpo
    assert "Ainda não há contatos vindos dos quizzes" not in corpo


# ---------------------------------------------------------------------------
# 3. Não perguntei não é não há ninguém
# ---------------------------------------------------------------------------


@respx.mock
@pytest.mark.parametrize(
    "falha",
    [
        httpx.ConnectError("recusou"),
        httpx.ReadTimeout("demorou"),
        httpx.Response(500, json={"detail": "caiu"}),
        httpx.Response(401, json={"detail": "Unauthorized"}),
        httpx.Response(200, content=b"isto nao e json"),
    ],
)
def test_leads_fora_do_ar_a_lista_diz_isso_e_nao_mostra_lista_vazia(falha):
    cliente = _dentro()
    if isinstance(falha, Exception):
        respx.get(f"{LEADS}/leads").mock(side_effect=falha)
    else:
        respx.get(f"{LEADS}/leads").mock(return_value=falha)

    r = cliente.get(reverse("contatos"))

    corpo = r.content.decode()
    assert r.status_code == 503
    assert "não respondeu agora" in corpo
    assert "Ainda não há contatos vindos dos quizzes" not in corpo
    assert "Nenhum contato casou" not in corpo


@respx.mock
def test_sem_o_par_de_senhas_a_lista_diz_que_nao_esta_ligada(monkeypatch):
    monkeypatch.delenv("LEADS_API_URL")
    monkeypatch.delenv("LEADS_API_TOKEN")
    cliente = _dentro()
    rota = respx.get(f"{LEADS}/leads").mock(
        return_value=httpx.Response(200, json=_pagina([_ana()]))
    )

    r = cliente.get(reverse("contatos"))

    corpo = r.content.decode()
    assert r.status_code == 503
    assert "ainda não está ligada" in corpo
    assert "Ana Souza" not in corpo
    assert "Ainda não há contatos vindos dos quizzes" not in corpo
    assert not rota.called


@respx.mock
def test_leads_fora_do_ar_a_ficha_diz_isso_e_nao_vira_404():
    cliente = _dentro()
    respx.get(f"{LEADS}/leads/{ANA}").mock(side_effect=httpx.ConnectError("recusou"))

    r = cliente.get(reverse("contato", args=[uuid.UUID(ANA)]))

    assert r.status_code == 503
    assert "Ficha indisponível" in r.content.decode()


@respx.mock
def test_contato_que_nao_existe_e_404():
    cliente = _dentro()
    respx.get(f"{LEADS}/leads/{INEXISTENTE}").mock(
        return_value=httpx.Response(404, json={"detail": "Not Found"})
    )

    r = cliente.get(reverse("contato", args=[uuid.UUID(INEXISTENTE)]))

    assert r.status_code == 404


# ---------------------------------------------------------------------------
# 4. Só o dono e os administradores entram, e o menu acende "Contatos"
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("nome, args", [("contatos", []), ("contato", [uuid.UUID(ANA)])])
def test_sem_sessao_vai_para_o_login(nome, args):
    r = Client().get(reverse(nome, args=args))

    assert r.status_code == 302


@respx.mock
@pytest.mark.parametrize("nome, args", [("contatos", []), ("contato", [uuid.UUID(ANA)])])
def test_sessao_fora_da_lista_recebe_404_e_a_leads_nem_e_perguntada(nome, args):
    cliente = _dentro("estranho@exemplo.com")
    rota = respx.get(url__regex=rf"{LEADS}/.*").mock(
        return_value=httpx.Response(200, json=_pagina([_ana()]))
    )

    r = cliente.get(reverse(nome, args=args))

    assert r.status_code == 404
    assert "Ana Souza" not in r.content.decode()
    assert not rota.called


@respx.mock
def test_o_menu_acende_contatos_na_lista_e_na_ficha():
    cliente = _dentro()
    respx.get(f"{LEADS}/leads").mock(
        return_value=httpx.Response(200, json=_pagina([_ana()]))
    )
    respx.get(f"{LEADS}/leads/{ANA}").mock(
        return_value=httpx.Response(200, json=_ficha())
    )

    for url in (reverse("contatos"), reverse("contato", args=[uuid.UUID(ANA)])):
        menu = cliente.get(url).context["menu_do_admin"]
        acesos = [item["rotulo"] for item in menu if item["aqui"]]
        # O CRM acende junto: a lista de contatos é uma parte dele (a regra
        # está em `moldura.secoes_do_menu`). Nenhuma outra seção acende.
        assert "Contatos" in acesos, url
        assert set(acesos) <= {"CRM", "Contatos"}, url


@respx.mock
def test_a_visao_geral_leva_ate_os_contatos():
    cliente = _dentro()

    corpo = cliente.get(reverse("visao_geral")).content.decode()

    assert reverse("contatos") in corpo
