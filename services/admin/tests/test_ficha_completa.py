"""A ficha completa do contato (`/admin/contatos/<id>/`, 03/10/2026).

O que cada grupo protege:

1. **Tudo numa tela.** Quiz com respostas legíveis, perfil com as provas
   (hipótese marcada como hipótese), oferta de interesse, próximo passo e
   prazo, quem atende, conversa, links de compra e pagamentos.
2. **Cada parte cai sozinha.** Uma célula fora do ar ou sem a capacidade
   publicada vira "ainda indisponível" naquela parte; a ficha abre.
3. **Assumir e devolver** passam pela `mensageria`, só para conversa deste
   contato, e ficam registrados.
4. **Nada de um contato na ficha de outro.**
"""

from __future__ import annotations

import json
import uuid

import httpx
import pytest
import respx
from django.test import Client
from django.urls import NoReverseMatch, reverse

from apps.auditoria.models import Registro
from apps.core import ficha_do_contato as ficha

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
LEADS = "http://leads:8000/api/leads"
MENSAGERIA = "http://mensageria:8000/api/mensageria"
CHECKOUT = "http://checkout:8000/api/checkout"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"

ANA = "24e45be2-77bb-4a32-a388-78d2ce9adcad"
OUTRO = "5b1d7c0e-2f4a-4e8b-9c3d-1a2b3c4d5e6f"
OPORTUNIDADE = "9f8e7d6c-5b4a-4c3d-8e2f-1a0b9c8d7e6f"
CONVERSA = "0d1c2b3a-4f5e-4d6c-8b7a-9e8d7c6b5a40"
CONVERSA_DE_OUTRO = "1e2d3c4b-5a6f-4e7d-8c9b-0a1f2e3d4c50"
SITE = "principal"


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    monkeypatch.setenv("LEADS_API_URL", LEADS)
    monkeypatch.setenv("LEADS_API_TOKEN", "token-do-par-admin-leads")
    monkeypatch.setenv("MENSAGERIA_API_URL", MENSAGERIA)
    monkeypatch.setenv("MENSAGERIA_API_TOKEN", "token-admin-mensageria")
    monkeypatch.setenv("CHECKOUT_API_URL", CHECKOUT)
    monkeypatch.setenv("CHECKOUT_API_TOKEN", "token-admin-checkout")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


def _dentro() -> Client:
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={"autenticado": True, "id": "id-opaco-123", "nome_exibido": "Fulano",
                  "papel": None, "email": DONO},
        )
    )
    c = Client()
    c.defaults["HTTP_COOKIE"] = COOKIE
    return c


def _ficha(**mudancas) -> dict:
    corpo = {
        "id": ANA, "nome": "Ana Souza", "email": "ana@exemplo.com",
        "telefone": "11999990000", "origem": "quiz:prosperidade", "site_id": SITE,
        "tags": ["quiz"], "consentimento": {"whatsapp": True},
        "criado_em": "2026-10-03T13:00:00Z", "atualizado_em": "2026-10-03T15:00:00Z",
        "linha_do_tempo_total": 1,
        "linha_do_tempo": [
            {"evento": "quiz.completado", "ocorrido_em": "2026-10-03T13:00:00Z", "payload": {}},
        ],
        "quizzes": [{
            "id": "q1", "quiz_slug": "prosperidade", "situacao": "completo",
            "resultado": "mentoria", "completado_em": "2026-10-03T13:00:00Z",
            "respostas": [
                {"pergunta_id": "p1", "pergunta": "Qual é o seu maior objetivo?",
                 "respostas": [{"id": "a", "texto": "Organizar as finanças"}], "valor_livre": None},
                {"pergunta_id": "p2", "pergunta": "Quanto tempo por semana você tem?",
                 "respostas": [], "valor_livre": "Umas 3 horas"},
            ],
        }],
        "perfil": {
            "versao": 2, "resumo": "Quer organizar as finanças da família.",
            "objetivo_declarado": {
                "texto": "Organizar as finanças", "hipotese": False,
                "evidencias": [{"tipo": "resposta", "id": "p1", "trecho": "Organizar as finanças"}],
            },
            "experiencia": None, "disponibilidade": None, "duvidas": [], "objecoes": [],
            "hipoteses": [{"texto": "Pode ter pouco tempo livre", "evidencias": [], "hipotese": True}],
            "informacoes_ausentes": ["Renda mensal"], "perguntas_uteis": ["Já fez algum curso?"],
            "prioridade": {"nivel": "alta", "explicacao": "Respondeu tudo e pediu contato"},
            "oferta_indicada": {"oferta_ref": "mentoria", "nome": "Mentoria Prosperar",
                                "motivo": "Resultado do quiz", "evidencias": []},
            "analisado_em": "2026-10-03T14:00:00Z", "fatos_novos_desde_a_analise": 1,
        },
    }
    corpo.update(mudancas)
    return corpo


def _oportunidade(**mudancas) -> dict:
    item = {
        "id": OPORTUNIDADE, "lead_id": ANA, "etapa": "proposta", "situacao": "aberta",
        "titular": {"id": "comercial", "funcao": "comercial"},
        "fonte": {"tipo": "quiz", "referencia_id": "oferta:mentoria"},
        "proximo_passo": {"descricao": "Mandar o link da mentoria",
                          "executar_ate": "2026-10-05T12:00:00Z", "evidencia_esperada": ""},
        "atendido_por": {"tipo": "agente", "nome": "Assistente"},
        "prazo": "2099-10-05T12:00:00Z", "aguardando_resposta": True,
        "objecao_principal": "Preço", "ultimo_contato_em": None,
        "receita": {
            "oportunidade_id": OPORTUNIDADE, "moeda": "BRL", "aprovado_centavos": 49700,
            "estornos_centavos": 0, "liquido_centavos": 49700,
            "compras": [{"pedido_id": "ped-1", "situacao": "aprovada", "oferta_ref": "mentoria",
                         "produtos": ["mentoria"], "valor_pedido_centavos": 49700,
                         "aprovado_centavos": 49700, "estornos_centavos": 0,
                         "aprovado_em": "2026-10-03T16:00:00Z", "revertida_em": None}],
        },
    }
    item.update(mudancas)
    return item


def _quadro(*itens) -> dict:
    return {"itens": list(itens), "resumo": {}, "total": len(itens), "pagina": 1, "tem_mais": False}


def _conversa(**mudancas) -> dict:
    conversa = {
        "id": CONVERSA, "site_id": SITE, "canal": "whatsapp", "lead_id": ANA,
        "ligacao": "ligada", "ambigua": False, "estado": "agente", "assumida_por": None,
        "janela_aberta": True, "descadastrado": False,
        "ultima_mensagem_em": "2026-10-03T15:30:00Z",
    }
    conversa.update(mudancas)
    return conversa


def _mensagens() -> dict:
    return {
        "conversa": _conversa(),
        "mensagens": [
            {"id": "m1", "direcao": "entrada", "autor": "contato", "texto": "Oi, quero saber da mentoria <script>alert(1)</script>",
             "ocorrida_em": "2026-10-03T15:00:00Z", "estado_envio": "recebida"},
            {"id": "m2", "direcao": "saida", "autor": "agente", "texto": "Olá! Sou o assistente da equipe.",
             "ocorrida_em": "2026-10-03T15:30:00Z", "estado_envio": "entregue"},
        ],
    }


def _pedidos() -> dict:
    return {
        "oportunidade_ref": OPORTUNIDADE,
        "pedidos": [{
            "pedido_id": "ped-2", "existe": False, "status": "aguardando_dados",
            "confirmado": False, "valor_cents": 49700, "oportunidade_ref": OPORTUNIDADE,
            "oferta_ref": "mentoria", "criado_em": "2026-10-03T15:40:00Z", "pago_em": None,
            "url": "https://meshcraft.top/checkout/mentoria/?link=ped-2",
        }],
        "resumo": {"aprovado_cents": 0, "estornado_cents": 0, "liquido_cents": 0, "moeda": "BRL"},
    }


def _tudo_no_ar(*, conversas=None, ficha_do_lead=None, oportunidades=None):
    respx.get(f"{LEADS}/leads/{ANA}").mock(
        return_value=httpx.Response(200, json=ficha_do_lead or _ficha())
    )
    respx.get(f"{LEADS}/crm").mock(
        return_value=httpx.Response(200, json=_quadro(*(oportunidades if oportunidades is not None else [_oportunidade()])))
    )
    respx.get(f"{MENSAGERIA}/conversas").mock(
        return_value=httpx.Response(200, json={"itens": conversas if conversas is not None else [_conversa()],
                                               "total": 1, "pagina": 1, "por_pagina": 50, "tem_mais": False})
    )
    respx.get(f"{MENSAGERIA}/conversas/{CONVERSA}/mensagens").mock(
        return_value=httpx.Response(200, json=_mensagens())
    )
    return respx.get(f"{CHECKOUT}/interno/pedidos").mock(
        return_value=httpx.Response(200, json=_pedidos())
    )


def _url(lead=ANA):
    return reverse("contato", args=[lead])


# ---------------------------------------------------------------------------
# 1. Tudo numa tela
# ---------------------------------------------------------------------------


@respx.mock
def test_ficha_mostra_quiz_perfil_interesse_passo_conversa_links_e_pagamentos():
    checkout = _tudo_no_ar()
    resposta = _dentro().get(_url(), HTTP_HOST="meshcraft.top")
    assert resposta.status_code == 200
    html = resposta.content.decode()
    # Quiz com respostas legíveis.
    assert "Qual é o seu maior objetivo?" in html and "Organizar as finanças" in html
    assert "Umas 3 horas" in html and "Concluído" in html
    # Perfil: afirmação com a prova; hipótese marcada.
    assert "Quer organizar as finanças da família." in html
    assert "Resposta do quiz: “Organizar as finanças”" in html
    assert "Pode ter pouco tempo livre" in html and "hipótese" in html
    assert "Prioridade: <b>Alta</b>" in html and "Renda mensal" in html
    # Produto ou oferta de interesse.
    assert "Mentoria Prosperar" in html and "Indicada no perfil" in html
    # Próximo passo e prazo.
    assert "Mandar o link da mentoria" in html and "Objeção principal: Preço" in html
    assert "Aguardando resposta do contato." in html
    # Quem atende e o botão de assumir.
    assert "Assistente da equipe (agente)" in html and "Assumir a conversa" in html
    assert reverse("contato_atendimento", args=[ANA]) in html
    # Conversa (o botão da caixa de conversas tem teste próprio, abaixo).
    assert "Olá! Sou o assistente da equipe." in html and "janela de 24h aberta" in html
    # Links de compra enviados.
    assert "Link enviado, ainda não aberto" in html
    assert "https://meshcraft.top/checkout/mentoria/?link=ped-2" in html
    # Pagamentos confirmados pelo provedor.
    assert "Pago (confirmado pelo provedor)" in html and "R$ 497,00" in html
    # O checkout foi perguntado pela oportunidade deste contato, com o host.
    pedido = checkout.calls.last.request
    assert pedido.url.params["oportunidade_ref"] == OPORTUNIDADE
    assert pedido.headers["host"] == "meshcraft.top"


@respx.mock
def test_mensagem_do_contato_e_texto_e_nao_vira_html():
    _tudo_no_ar()
    html = _dentro().get(_url()).content.decode()
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


@respx.mock
def test_conversa_assumida_mostra_a_pessoa_e_o_botao_de_devolver():
    _tudo_no_ar(conversas=[_conversa(estado="pessoa", assumida_por="carla@exemplo.com")])
    html = _dentro().get(_url()).content.decode()
    assert "Pessoa da equipe: carla@exemplo.com" in html
    assert "Devolver ao assistente" in html and "Assumir a conversa" not in html


@respx.mock
def test_sem_conversa_quem_atende_vem_do_crm():
    _tudo_no_ar(conversas=[], oportunidades=[_oportunidade(atendido_por={"tipo": "pessoa", "nome": "Carla"})])
    html = _dentro().get(_url()).content.decode()
    assert "Pessoa da equipe: Carla" in html
    assert "Nenhuma conversa com este contato ainda." in html
    assert "Sem conversa aberta para assumir." in html


@respx.mock
def test_contato_ainda_nao_analisado_e_sem_quiz_diz_isso():
    _tudo_no_ar(ficha_do_lead=_ficha(perfil=None, quizzes=[]), oportunidades=[])
    html = _dentro().get(_url()).content.decode()
    assert "Este contato ainda não foi analisado." in html
    assert "Nenhum quiz registrado para este contato." in html
    assert "Nenhuma oportunidade aberta." in html
    assert "Nenhum link de compra enviado para este contato." in html
    assert "Nenhum pagamento registrado para este contato." in html


# ---------------------------------------------------------------------------
# 2. Cada parte cai sozinha
# ---------------------------------------------------------------------------


@respx.mock
def test_todas_as_outras_fontes_fora_do_ar_a_ficha_abre_e_diz_o_que_faltou():
    corpo = _ficha()
    del corpo["quizzes"], corpo["perfil"]
    respx.get(f"{LEADS}/leads/{ANA}").mock(return_value=httpx.Response(200, json=corpo))
    respx.get(f"{LEADS}/crm").mock(return_value=httpx.Response(500))
    respx.get(f"{MENSAGERIA}/conversas").mock(side_effect=httpx.ConnectError("fora"))
    checkout = respx.get(f"{CHECKOUT}/interno/pedidos").mock(return_value=httpx.Response(500))
    resposta = _dentro().get(_url())
    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert "Ana" in html and "Ana Souza" not in html and "Respondeu o quiz" in html
    assert "Respostas do quiz: ainda indisponível." in html
    assert "Perfil: ainda indisponível." in html
    assert "Ainda indisponível: o CRM não respondeu." in html
    assert "As conversas não responderam agora." in html
    assert "Pagamentos confirmados: ainda indisponível." in html
    assert "Links de compra: ainda indisponível." in html
    assert not checkout.called


@respx.mock
def test_capacidades_ainda_nao_publicadas_aparecem_como_indisponiveis():
    oportunidade = _oportunidade()
    del oportunidade["receita"]
    _tudo_no_ar(oportunidades=[oportunidade])
    respx.get(f"{MENSAGERIA}/conversas").mock(return_value=httpx.Response(404))
    respx.get(f"{CHECKOUT}/interno/pedidos").mock(return_value=httpx.Response(404))
    resposta = _dentro().get(_url())
    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert "Conversas: ainda indisponível." in html
    assert "Assumir ou devolver: ainda indisponível." in html
    assert "Links de compra: ainda indisponível." in html
    assert "Pagamentos confirmados: ainda indisponível." in html


@respx.mock
def test_sem_os_pares_de_mensageria_e_checkout_a_ficha_nao_pergunta_e_avisa(monkeypatch):
    monkeypatch.delenv("MENSAGERIA_API_URL")
    monkeypatch.delenv("CHECKOUT_API_TOKEN")
    respx.get(f"{LEADS}/leads/{ANA}").mock(return_value=httpx.Response(200, json=_ficha()))
    respx.get(f"{LEADS}/crm").mock(return_value=httpx.Response(200, json=_quadro(_oportunidade())))
    html = _dentro().get(_url()).content.decode()
    assert "A administração ainda não está ligada às conversas." in html
    assert "Links de compra: ainda indisponível." in html


@respx.mock
def test_mensagens_fora_do_ar_mostram_a_conversa_e_avisam():
    _tudo_no_ar()
    respx.get(f"{MENSAGERIA}/conversas/{CONVERSA}/mensagens").mock(return_value=httpx.Response(502))
    html = _dentro().get(_url()).content.decode()
    assert "As mensagens não puderam ser lidas agora." in html
    assert "Assumir a conversa" in html


# ---------------------------------------------------------------------------
# 3. Assumir e devolver
# ---------------------------------------------------------------------------


@respx.mock
@pytest.mark.django_db
def test_assumir_passa_pela_mensageria_marca_o_crm_e_registra():
    _tudo_no_ar()
    assumir = respx.post(f"{MENSAGERIA}/conversas/{CONVERSA}/assumir").mock(
        return_value=httpx.Response(200, json=_conversa(estado="pessoa", assumida_por=DONO))
    )
    crm = respx.patch(f"{LEADS}/crm/{OPORTUNIDADE}/acompanhamento").mock(
        return_value=httpx.Response(200, json={"id": OPORTUNIDADE, "historico": []})
    )
    resposta = _dentro().post(
        reverse("contato_atendimento", args=[ANA]), {"gesto": "assumir", "conversa_id": CONVERSA}
    )
    assert resposta.status_code == 302
    assert resposta["Location"].endswith("?atendimento=assumida")
    assert json.loads(assumir.calls.last.request.content) == {"site_id": SITE, "pessoa_id": DONO}
    assert json.loads(crm.calls.last.request.content)["atendido_por"] == {"tipo": "pessoa", "nome": DONO}
    registro = Registro.objects.get(alvo=ANA)
    assert registro.desfecho == Registro.OK and "assumir" in registro.detalhe


@respx.mock
@pytest.mark.django_db
def test_devolver_passa_pela_mensageria_e_a_ficha_confirma():
    _tudo_no_ar(conversas=[_conversa(estado="pessoa", assumida_por=DONO)])
    devolver = respx.post(f"{MENSAGERIA}/conversas/{CONVERSA}/devolver").mock(
        return_value=httpx.Response(200, json=_conversa())
    )
    respx.patch(f"{LEADS}/crm/{OPORTUNIDADE}/acompanhamento").mock(return_value=httpx.Response(500))
    cliente = _dentro()
    resposta = cliente.post(
        reverse("contato_atendimento", args=[ANA]), {"gesto": "devolver", "conversa_id": CONVERSA}
    )
    # O CRM recusou o espelho: a conversa já voltou, e a ficha avisa isso.
    assert resposta.status_code == 302
    assert resposta["Location"].endswith("?atendimento=devolvida&espelho=falhou")
    assert json.loads(devolver.calls.last.request.content) == {"site_id": SITE}
    html = cliente.get(resposta["Location"]).content.decode()
    assert "Conversa devolvida ao assistente da equipe." in html
    assert "o CRM não registrou quem atende agora." in html


@respx.mock
@pytest.mark.django_db
def test_devolver_diz_quando_o_robo_volta_a_responder():
    _tudo_no_ar(conversas=[_conversa(estado="pessoa", assumida_por=DONO)])
    respx.post(f"{MENSAGERIA}/conversas/{CONVERSA}/devolver").mock(
        return_value=httpx.Response(200, json=_conversa())
    )
    respx.patch(f"{LEADS}/crm/{OPORTUNIDADE}/acompanhamento").mock(
        return_value=httpx.Response(200, json={"id": OPORTUNIDADE, "historico": []})
    )
    cliente = _dentro()
    resposta = cliente.post(
        reverse("contato_atendimento", args=[ANA]), {"gesto": "devolver", "conversa_id": CONVERSA}
    )
    assert resposta["Location"].endswith("?atendimento=devolvida")
    html = cliente.get(resposta["Location"]).content.decode()
    assert "O robô responde a partir da próxima mensagem da pessoa." in html
    # Com o espelho no CRM certo, não há aviso nenhum.
    assert "o CRM não registrou quem atende agora." not in html
    # Assumir não promete nada sobre o robô.
    assert "O robô responde a partir" not in cliente.get(_url() + "?atendimento=assumida").content.decode()


@respx.mock
@pytest.mark.django_db
def test_crm_fora_do_ar_ao_trocar_atendimento_avisa_na_ficha():
    _tudo_no_ar()
    respx.post(f"{MENSAGERIA}/conversas/{CONVERSA}/assumir").mock(
        return_value=httpx.Response(200, json=_conversa(estado="pessoa", assumida_por=DONO))
    )
    respx.get(f"{LEADS}/crm").mock(side_effect=httpx.ConnectError("fora"))
    cliente = _dentro()
    resposta = cliente.post(
        reverse("contato_atendimento", args=[ANA]), {"gesto": "assumir", "conversa_id": CONVERSA}
    )
    assert resposta["Location"].endswith("?atendimento=assumida&espelho=falhou")
    html = cliente.get(resposta["Location"]).content.decode()
    assert "Você assumiu a conversa." in html
    assert "o CRM não registrou quem atende agora." in html


@respx.mock
def test_autor_do_espelho_no_crm_e_cortado_em_100_caracteres():
    crm = respx.patch(f"{LEADS}/crm/{OPORTUNIDADE}/acompanhamento").mock(
        return_value=httpx.Response(200, json={"id": OPORTUNIDADE, "historico": []})
    )
    autor = ("a" * 150) + "@exemplo.com"
    ok = ficha.marcar_atendimento_no_crm(
        [ficha.montar_oportunidade(_oportunidade())], tipo="pessoa", nome=autor, autor=autor
    )
    assert ok is True
    enviado = json.loads(crm.calls.last.request.content)
    assert enviado["autor_id"] == autor[:100] and len(enviado["autor_id"]) == 100


@respx.mock
def test_espelho_no_crm_devolve_falso_se_alguma_oportunidade_falhou():
    respx.patch(f"{LEADS}/crm/{OPORTUNIDADE}/acompanhamento").mock(return_value=httpx.Response(500))
    ok = ficha.marcar_atendimento_no_crm(
        [ficha.montar_oportunidade(_oportunidade())], tipo="agente", nome="Assistente da equipe", autor="x"
    )
    assert ok is False
    # Sem oportunidade aberta não há o que marcar, e isso não é falha.
    assert ficha.marcar_atendimento_no_crm([], tipo="agente", nome="x", autor="x") is True


@respx.mock
@pytest.mark.django_db
def test_nao_assume_conversa_de_outro_contato():
    _tudo_no_ar()
    assumir = respx.post(url__regex=rf"{MENSAGERIA}/conversas/.*/assumir")
    resposta = _dentro().post(
        reverse("contato_atendimento", args=[ANA]),
        {"gesto": "assumir", "conversa_id": CONVERSA_DE_OUTRO},
    )
    assert resposta["Location"].endswith("?erro=conversa")
    assert not assumir.called


@respx.mock
@pytest.mark.django_db
def test_sem_permissao_de_escrita_a_ficha_diz_isso():
    _tudo_no_ar()
    respx.post(f"{MENSAGERIA}/conversas/{CONVERSA}/assumir").mock(return_value=httpx.Response(403))
    cliente = _dentro()
    resposta = cliente.post(
        reverse("contato_atendimento", args=[ANA]), {"gesto": "assumir", "conversa_id": CONVERSA}
    )
    assert resposta["Location"].endswith("?erro=sem-grau")
    html = cliente.get(resposta["Location"]).content.decode()
    assert "ainda não tem permissão para mudar o atendimento" in html
    assert Registro.objects.get(alvo=ANA).desfecho == Registro.RECUSADO_PELA_CELULA


@respx.mock
@pytest.mark.django_db
def test_conversas_fora_do_ar_ao_assumir_nao_quebra():
    respx.get(f"{LEADS}/leads/{ANA}").mock(return_value=httpx.Response(200, json=_ficha()))
    respx.get(f"{MENSAGERIA}/conversas").mock(side_effect=httpx.ConnectError("fora"))
    resposta = _dentro().post(
        reverse("contato_atendimento", args=[ANA]), {"gesto": "assumir", "conversa_id": CONVERSA}
    )
    assert resposta.status_code == 302 and resposta["Location"].endswith("?erro=nao-respondeu")


@respx.mock
def test_assumir_so_aceita_post():
    respx.get(f"{LEADS}/leads/{ANA}").mock(return_value=httpx.Response(200, json=_ficha()))
    resposta = _dentro().get(reverse("contato_atendimento", args=[ANA]))
    assert resposta.status_code == 405


# ---------------------------------------------------------------------------
# 4. Nada de um contato na ficha de outro
# ---------------------------------------------------------------------------


@respx.mock
def test_conversa_e_oportunidade_de_outro_contato_nao_entram_na_ficha():
    _tudo_no_ar(
        conversas=[_conversa(id=CONVERSA_DE_OUTRO, lead_id=OUTRO)],
        oportunidades=[_oportunidade(id="op-outro", lead_id=OUTRO,
                                     proximo_passo={"descricao": "Passo de outra pessoa",
                                                    "executar_ate": "2026-10-05T12:00:00Z"})],
    )
    html = _dentro().get(_url()).content.decode()
    assert "Passo de outra pessoa" not in html
    assert CONVERSA_DE_OUTRO not in html
    assert "Nenhuma conversa com este contato ainda." in html


@respx.mock
def test_conversas_sao_pedidas_pelo_site_e_pelo_contato_da_ficha():
    _tudo_no_ar()
    _dentro().get(_url())
    chamadas = [c.request for c in respx.calls if c.request.url.path.endswith("/conversas")]
    assert chamadas and chamadas[0].url.params["site_id"] == SITE
    assert chamadas[0].url.params["lead_id"] == ANA


# ---------------------------------------------------------------------------
# Funções puras
# ---------------------------------------------------------------------------


def test_afirmacao_sem_prova_e_hipotese_mesmo_que_a_fonte_diga_o_contrario():
    perfil = ficha.montar_perfil({"perfil": {
        "resumo": "x", "objetivo_declarado": {"texto": "Crescer", "hipotese": False, "evidencias": []},
    }})
    assert perfil["afirmacoes"][0]["hipotese"] is True


def test_mesma_compra_em_duas_oportunidades_aparece_uma_vez():
    compra = {"pedido_id": "ped-1", "situacao": "aprovada", "aprovado_centavos": 100}
    oportunidades = [
        ficha.montar_oportunidade(_oportunidade(receita={"compras": [compra]})),
        ficha.montar_oportunidade(_oportunidade(id="op-2", receita={"compras": [compra]})),
    ]
    assert len(ficha.pagamentos_das_oportunidades(oportunidades)) == 1


def test_link_que_nao_e_https_nao_vira_link():
    link = ficha._link({"url": "javascript:alert(1)", "status": "pago"}, {"oferta": ""})
    assert link["url"] == ""


# ---------------------------------------------------------------------------
# 5. Ajustes da revisão (03/10/2026)
# ---------------------------------------------------------------------------

CONVERSA_ENCERRADA = "2f3e4d5c-6b7a-4f8e-9d0c-1b2a3f4e5d60"


def _sem_a_caixa(monkeypatch):
    def sem_rota(nome, *args, **kwargs):
        raise NoReverseMatch(nome)

    monkeypatch.setattr(ficha, "reverse", sem_rota)


def _com_a_caixa(monkeypatch):
    def com_rota(nome, *args, **kwargs):
        if nome == "crm_conversas":
            return "/crm/conversas/"
        return reverse(nome, *args, **kwargs)

    monkeypatch.setattr(ficha, "reverse", com_rota)


@respx.mock
def test_botao_da_caixa_de_conversas_usa_a_rota_resolvida_e_nao_inventa_endereco(monkeypatch):
    _tudo_no_ar()
    _com_a_caixa(monkeypatch)
    html = _dentro().get(_url()).content.decode()
    assert 'href="/crm/conversas/"' in html and "Abrir a caixa de conversas" in html
    # A caixa não filtra por contato: nada de parâmetro que ela ignora.
    assert "conversas/?lead_id" not in html


@respx.mock
def test_sem_a_rota_da_caixa_de_conversas_nao_ha_botao(monkeypatch):
    _tudo_no_ar()
    _sem_a_caixa(monkeypatch)
    resposta = _dentro().get(_url())
    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert "Abrir a caixa de conversas" not in html
    assert "/crm/conversas" not in html
    # O resto da conversa continua na ficha.
    assert "Olá! Sou o assistente da equipe." in html


@respx.mock
def test_conversa_encerrada_mais_nova_nao_esconde_a_aberta_mais_antiga():
    """A conversa atual é escolhida uma vez e vale para tudo na ficha."""
    _tudo_no_ar(conversas=[
        _conversa(id=CONVERSA_ENCERRADA, estado="encerrada", canal="email", janela_aberta=False,
                  ultima_mensagem_em="2026-10-03T18:00:00Z"),
        _conversa(estado="pessoa", assumida_por="carla@exemplo.com",
                  ultima_mensagem_em="2026-10-02T10:00:00Z"),
    ])
    encerrada = respx.get(f"{MENSAGERIA}/conversas/{CONVERSA_ENCERRADA}/mensagens").mock(
        return_value=httpx.Response(200, json={"conversa": {}, "mensagens": []})
    )
    html = _dentro().get(_url()).content.decode()
    # Crachá, botão e bloco da conversa falam da mesma conversa: a aberta.
    assert "Pessoa da equipe: carla@exemplo.com" in html
    assert "Devolver ao assistente" in html and "Assumir a conversa" not in html
    assert f'name="conversa_id" value="{CONVERSA}"' in html
    assert CONVERSA_ENCERRADA not in html
    assert "WhatsApp · Pessoa da equipe (carla@exemplo.com)" in html
    assert "Olá! Sou o assistente da equipe." in html
    assert not encerrada.called
    assert "Este contato tem 2 conversas" in html


@respx.mock
def test_todas_encerradas_a_atual_e_a_mais_recente_e_nao_ha_botao():
    _tudo_no_ar(conversas=[
        _conversa(estado="encerrada", ultima_mensagem_em="2026-10-01T10:00:00Z"),
        _conversa(id=CONVERSA_ENCERRADA, estado="encerrada", canal="email", janela_aberta=False,
                  ultima_mensagem_em="2026-10-03T18:00:00Z"),
    ])
    mais_recente = respx.get(f"{MENSAGERIA}/conversas/{CONVERSA_ENCERRADA}/mensagens").mock(
        return_value=httpx.Response(200, json={"conversa": {}, "mensagens": [
            {"id": "m9", "direcao": "entrada", "autor": "contato", "texto": "Obrigada, resolvido",
             "ocorrida_em": "2026-10-03T18:00:00Z"}]})
    )
    html = _dentro().get(_url()).content.decode()
    assert mais_recente.called and "Obrigada, resolvido" in html
    assert "E-mail · Conversa encerrada" in html
    assert "Sem conversa aberta para assumir." in html
    assert "Assumir a conversa" not in html and "Devolver ao assistente" not in html


def test_escolher_conversa_atual():
    nova_encerrada = {"id": "a", "estado": "encerrada"}
    antiga_aberta = {"id": "b", "estado": "agente"}
    outra_aberta = {"id": "c", "estado": "pessoa"}
    assert ficha.escolher_conversa_atual([nova_encerrada, antiga_aberta, outra_aberta]) is antiga_aberta
    assert ficha.escolher_conversa_atual([nova_encerrada, {"id": "d", "estado": "encerrada"}]) is nova_encerrada
    assert ficha.escolher_conversa_atual([]) is None


def test_quem_atende_segue_a_conversa_atual_e_nao_a_primeira_da_lista():
    conversa = {
        "conversas": [{"id": "a", "estado": "encerrada", "assumida_por": ""},
                      {"id": "b", "estado": "pessoa", "assumida_por": "carla"}],
        "atual": {"id": "b", "estado": "pessoa", "assumida_por": "carla"},
    }
    assert ficha.quem_atende(conversa, []) == {"tipo": "pessoa", "texto": "Pessoa da equipe: carla"}


def _oportunidades_com_id(quantas, primeira=OPORTUNIDADE):
    ids = [primeira] + [str(uuid.uuid4()) for _ in range(quantas - 1)]
    return [ficha.montar_oportunidade(_oportunidade(id=i)) for i in ids]


@respx.mock
def test_links_param_na_primeira_falha_de_rede_e_as_restantes_nao_respondem():
    rota = respx.get(f"{CHECKOUT}/interno/pedidos").mock(side_effect=httpx.ConnectTimeout("lento"))
    resultado = ficha.links_das_oportunidades(_oportunidades_com_id(5), "meshcraft.top")
    assert rota.call_count == 1
    assert resultado == {"estado": ficha.NAO_RESPONDEU, "links": []}


@respx.mock
def test_links_ja_lidos_ficam_e_a_falha_depois_deles_avisa_que_e_parcial():
    chamadas = []

    def responder(request):
        chamadas.append(request.url.params["oportunidade_ref"])
        if len(chamadas) == 1:
            return httpx.Response(200, json=_pedidos())
        raise httpx.ReadTimeout("lento")

    respx.get(f"{CHECKOUT}/interno/pedidos").mock(side_effect=responder)
    resultado = ficha.links_das_oportunidades(_oportunidades_com_id(4), "meshcraft.top")
    assert len(chamadas) == 2
    assert resultado["estado"] == ficha.OK and resultado["parcial"] is True
    assert [l["pedido_id"] for l in resultado["links"]] == ["ped-2"]


@respx.mock
def test_pergunta_ao_checkout_espera_no_maximo_2_segundos():
    assert ficha.LinksDeCompraClient.TIMEOUT == 2.0
    rota = respx.get(f"{CHECKOUT}/interno/pedidos").mock(return_value=httpx.Response(200, json=_pedidos()))
    ficha.links_das_oportunidades(_oportunidades_com_id(1), "meshcraft.top")
    assert rota.calls.last.request.extensions["timeout"]["read"] == 2.0


@respx.mock
def test_checkout_fora_do_ar_na_ficha_pergunta_uma_vez_so():
    _tudo_no_ar(oportunidades=[_oportunidade(id=str(uuid.uuid4())) for _ in range(3)])
    rota = respx.get(f"{CHECKOUT}/interno/pedidos").mock(side_effect=httpx.ConnectError("fora"))
    resposta = _dentro().get(_url())
    assert resposta.status_code == 200 and rota.call_count == 1
    assert "Os links de compra não puderam ser lidos agora." in resposta.content.decode()


def test_prova_do_tipo_resposta_quiz_ganha_nome_em_portugues():
    assert ficha._evidencias([{"tipo": "resposta_quiz", "trecho": "Organizar"}]) == [
        {"tipo": "Resposta do quiz", "trecho": "Organizar"}
    ]


def test_prova_de_tipo_desconhecido_mostra_o_proprio_tipo_e_sem_tipo_diz_registro():
    evidencias = ficha._evidencias([
        {"tipo": "ligacao_gravada", "trecho": "Falou do preço"},
        {"trecho": "Sem tipo"},
        {"tipo": "  ", "trecho": ""},
    ])
    assert [e["tipo"] for e in evidencias] == ["ligacao_gravada", "Registro", "Registro"]
    assert evidencias[2]["trecho"] == "(sem trecho)"


@respx.mock
def test_ficha_mostra_prova_resposta_quiz_com_nome_em_portugues():
    corpo = _ficha()
    corpo["perfil"]["objetivo_declarado"]["evidencias"] = [
        {"tipo": "resposta_quiz", "id": "p1", "trecho": "Organizar as finanças"}
    ]
    _tudo_no_ar(ficha_do_lead=corpo)
    html = _dentro().get(_url()).content.decode()
    assert "Resposta do quiz: “Organizar as finanças”" in html
    assert "Registro: “Organizar as finanças”" not in html


def test_evento_mensagem_recebida_nao_tem_rotulo_proprio():
    from apps.core import contatos

    assert "mensagem.recebida" not in contatos.ROTULOS_DOS_EVENTOS
    assert contatos.rotulo_do_evento("mensagem.recebida") == "Outra atividade"
