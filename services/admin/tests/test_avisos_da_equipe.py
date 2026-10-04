"""Avisos para a equipe: um aviso por fato, no painel e por e-mail."""
import json
import threading
import time
import uuid
from datetime import timedelta

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.agentes.models import Execucao, RoboPessoal
from apps.comercial.models import TrabalhoComercial
from apps.core import avisos_equipe
from apps.core.models import Administrador, AvisoDaEquipe, MembroDaEquipe

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
LEADS = "http://leads:8000/api/leads"
MENSAGERIA = "http://mensageria:8000/api/mensageria"
DONO = "dono@exemplo.com"
LIVIA = "livia-avisos@exemplo.com"
SITE = "site-a"
OUTRO_SITE = "site-b"
OPORTUNIDADE = "24e45be2-77bb-4a32-a388-78d2ce9adcad"
LEAD = "92f0c4e1-25f4-480f-a64a-1b68d259c563"
CONVERSA = "5d1c8a51-6f73-4f0e-9c38-0f0a6d0f3e11"


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    monkeypatch.setenv("LEADS_API_URL", LEADS)
    monkeypatch.setenv("LEADS_API_TOKEN", "token-leads")
    monkeypatch.setenv("MENSAGERIA_API_URL", MENSAGERIA)
    monkeypatch.setenv("MENSAGERIA_API_TOKEN", "token-mensageria")
    monkeypatch.delenv("AVISOS_EQUIPE_SITES", raising=False)
    settings.ADMIN_EMAILS = DONO
    # O teste roda dentro de uma transação que nunca confirma: o e-mail que
    # sairia depois da gravação sai na hora.
    monkeypatch.setattr("django.db.transaction.on_commit", lambda funcao, *a, **k: funcao())
    # As memórias da varredura são do processo, não do teste.
    avisos_equipe._RECEITAS.clear()
    avisos_equipe._CONVERSAS_LIDAS.clear()


def _livia() -> MembroDaEquipe:
    pessoa = MembroDaEquipe.objects.get(nome="Lívia")
    pessoa.email = LIVIA
    pessoa.save()
    return pessoa


def _cliente(email=DONO, nome="Dono") -> Client:
    respx.get(SESSAO).mock(return_value=httpx.Response(200, json={
        "autenticado": True, "id": "id-opaco", "nome_exibido": nome, "papel": None, "email": email,
    }))
    cliente = Client()
    cliente.defaults["HTTP_COOKIE"] = "meshcraft_sessao=teste"
    return cliente


def _correio():
    return respx.post(MENSAGERIA + "/avisos-equipe").mock(
        return_value=httpx.Response(200, json={"envio_id": 1, "criado": True, "status": "pendente"})
    )


def _quadro(itens):
    return {"itens": itens, "resumo": {}, "pagina": 1, "total": len(itens), "tem_mais": False}


def _venda(**mudancas):
    return {
        "id": OPORTUNIDADE, "lead_id": LEAD, "etapa": "ganha", "situacao": "encerrada",
        "titular": {"id": LIVIA}, "atendido_por": {"tipo": "agente", "nome": "Agente"},
        "contato": {"id": LEAD, "nome": "Ana", "email": "ana@exemplo.com", "site_id": SITE},
        "registro_de_teste": False, **mudancas,
    }


def _sem_conversas():
    respx.get(MENSAGERIA + "/conversas").mock(return_value=httpx.Response(200, json={"itens": []}))


# ------------------------------------------------------------- o aviso em si


@respx.mock
def test_o_mesmo_fato_avisa_uma_vez_so_e_manda_o_email_ao_responsavel():
    _livia()
    correio = _correio()
    primeiro, criado = avisos_equipe.avisar(
        "pessoa_pedida", site_id=SITE, fato="conversa:1:t", responsavel=LIVIA,
        titulo="Conversa", link="/admin/crm/",
    )
    segundo, de_novo = avisos_equipe.avisar(
        "pessoa_pedida", site_id=SITE, fato="conversa:1:t", responsavel=LIVIA, titulo="Conversa",
    )
    assert criado is True and de_novo is False and primeiro.pk == segundo.pk
    assert AvisoDaEquipe.objects.count() == 1
    assert correio.call_count == 1
    corpo = json.loads(correio.calls.last.request.content)
    assert corpo["destinatario"] == LIVIA
    assert corpo["chave"].startswith(f"aviso-equipe-{primeiro.pk}-")
    # Lívia entra só com o crachá de equipe: o e-mail leva à lista de avisos
    # dela, e não a uma página do painel do dono (que para ela não existe).
    assert "/admin/crm/" not in corpo["corpo"]
    assert "https://meshcraft.top/admin/equipe/avisos/" in corpo["corpo"]
    primeiro.refresh_from_db()
    assert primeiro.responsavel.email == LIVIA
    assert primeiro.email_situacao == AvisoDaEquipe.Email.PEDIDO


@respx.mock
def test_sem_responsavel_o_email_vai_para_quem_administra():
    correio = _correio()
    aviso, _ = avisos_equipe.avisar("conversa_ambigua", site_id=SITE, fato="conversa:2", titulo="Ambígua")
    assert aviso.responsavel is None
    assert json.loads(correio.calls.last.request.content)["destinatario"] == DONO


@respx.mock
def test_mensageria_fora_do_ar_tenta_de_novo_na_volta_seguinte():
    rota = respx.post(MENSAGERIA + "/avisos-equipe").mock(return_value=httpx.Response(503))
    aviso, _ = avisos_equipe.avisar("envio_incerto", site_id=SITE, fato="mensagem:9", titulo="Incerto")
    aviso.refresh_from_db()
    assert aviso.email_situacao == AvisoDaEquipe.Email.PENDENTE
    assert aviso.email_tentativas == 1
    rota.mock(return_value=httpx.Response(200, json={"envio_id": 1, "criado": True, "status": "pendente"}))
    avisos_equipe.enviar_emails_pendentes()
    aviso.refresh_from_db()
    assert aviso.email_situacao == AvisoDaEquipe.Email.PEDIDO


def test_tipo_desconhecido_nao_vira_aviso():
    with pytest.raises(ValueError):
        avisos_equipe.avisar("qualquer", fato="x", titulo="x")


# ---------------------------------------------------------------- a varredura


@respx.mock
def test_venda_aprovada_com_agente_avisa_uma_vez_com_link_da_ficha():
    _livia()
    correio = _correio()
    respx.get(LEADS + "/crm").mock(return_value=httpx.Response(200, json=_quadro([_venda()])))
    respx.get(LEADS + f"/crm/{OPORTUNIDADE}/receita").mock(return_value=httpx.Response(200, json={
        "oportunidade_id": OPORTUNIDADE, "aprovado_centavos": 19700, "estornos_centavos": 0, "liquido_centavos": 19700,
    }))
    _sem_conversas()
    avisos_equipe.varrer()
    avisos_equipe.varrer()
    aviso = AvisoDaEquipe.objects.get(tipo="venda_assistida")
    assert aviso.link == f"/admin/crm/{OPORTUNIDADE}/"
    assert "R$ 197,00" in aviso.texto
    assert aviso.responsavel.email == LIVIA
    assert AvisoDaEquipe.objects.filter(tipo="venda_assistida").count() == 1
    assert correio.call_count == 1


@respx.mock
def test_sem_pagamento_aprovado_ou_venda_de_pessoa_nao_avisa():
    respx.get(LEADS + "/crm").mock(return_value=httpx.Response(200, json=_quadro([
        _venda(), _venda(id="11111111-1111-1111-1111-111111111111", atendido_por={"tipo": "pessoa", "nome": "Lívia"}),
        _venda(id="22222222-2222-2222-2222-222222222222", registro_de_teste=True),
    ])))
    respx.get(LEADS + f"/crm/{OPORTUNIDADE}/receita").mock(return_value=httpx.Response(200, json={
        "aprovado_centavos": 0, "estornos_centavos": 0, "liquido_centavos": 0,
    }))
    _sem_conversas()
    avisos_equipe.varrer()
    assert not AvisoDaEquipe.objects.filter(tipo="venda_assistida").exists()


@respx.mock
def test_conversa_passada_ambigua_e_envio_incerto_viram_avisos_por_site():
    _livia()
    _correio()
    respx.get(LEADS + "/crm").mock(return_value=httpx.Response(200, json=_quadro([_venda(etapa="nova", situacao="aberta")])))
    respx.get(LEADS + f"/crm/{OPORTUNIDADE}/receita").mock(return_value=httpx.Response(404))
    agora = timezone.now()
    passada = {
        "id": CONVERSA, "site_id": SITE, "canal": "whatsapp", "lead_id": LEAD, "ligacao": "ligada",
        "ambigua": False, "estado": "pessoa", "assumida_por": "equipe", "assumida_em": agora.isoformat(),
        "ultima_mensagem_em": agora.isoformat(),
    }
    ambigua = dict(passada, id="6d1c8a51-6f73-4f0e-9c38-0f0a6d0f3e12", estado="agente", ligacao="ambigua",
                   ambigua=True, lead_id=None, assumida_por=None)

    def conversas(request):
        params = request.url.params
        assert params["site_id"] == SITE
        if params.get("estado") == "pessoa":
            return httpx.Response(200, json={"itens": [passada]})
        if params.get("ligacao") == "ambigua":
            return httpx.Response(200, json={"itens": [ambigua]})
        return httpx.Response(200, json={"itens": [passada]})

    respx.get(MENSAGERIA + "/conversas").mock(side_effect=conversas)
    respx.get(MENSAGERIA + f"/conversas/{CONVERSA}/mensagens").mock(return_value=httpx.Response(200, json={
        "conversa": passada,
        "mensagens": [
            {"id": "m-velha", "direcao": "saida", "estado_envio": "desconhecido",
             "ocorrida_em": (agora - timedelta(minutes=30)).isoformat(), "texto": "não entra no aviso"},
            {"id": "m-nova", "direcao": "saida", "estado_envio": "desconhecido",
             "ocorrida_em": agora.isoformat()},
            {"id": "m-ok", "direcao": "saida", "estado_envio": "entregue",
             "ocorrida_em": (agora - timedelta(minutes=30)).isoformat()},
        ],
    }))
    avisos_equipe.varrer(agora)
    avisos_equipe.varrer(agora)

    pedida = AvisoDaEquipe.objects.get(tipo="pessoa_pedida")
    # Passada pelo agente: é aviso da equipe (e vai para quem administra).
    assert pedida.site_id == SITE and pedida.responsavel is None
    assert pedida.link == f"/admin/crm/conversas/{CONVERSA}/?site_id={SITE}"
    assert AvisoDaEquipe.objects.get(tipo="conversa_ambigua").responsavel is None
    incerto = AvisoDaEquipe.objects.get(tipo="envio_incerto")
    assert incerto.fato == f"conversa:{CONVERSA}:envio_incerto"
    assert "não entra no aviso" not in incerto.texto
    assert AvisoDaEquipe.objects.count() == 3


@respx.mock
def test_passar_de_novo_depois_de_devolver_e_outro_aviso():
    _correio()
    agora = timezone.now()
    primeira = {
        "id": CONVERSA, "site_id": SITE, "estado": "pessoa", "assumida_por": "equipe",
        "assumida_em": (agora - timedelta(hours=3)).isoformat(),
    }
    segunda = dict(primeira, assumida_em=(agora - timedelta(hours=1)).isoformat())
    rota = respx.get(MENSAGERIA + "/conversas").mock(return_value=httpx.Response(200, json={"itens": [primeira]}))
    avisos_equipe.varrer_conversas(SITE)
    avisos_equipe.varrer_conversas(SITE)
    rota.mock(return_value=httpx.Response(200, json={"itens": [segunda]}))
    avisos_equipe.varrer_conversas(SITE)
    assert AvisoDaEquipe.objects.filter(tipo="pessoa_pedida").count() == 2


@respx.mock
def test_trabalho_parado_alem_da_tolerancia_avisa_quem_pediu():
    _correio()
    livia = _livia()
    robo = RoboPessoal.objects.create(membro=livia, nome="Robô da Lívia")
    parada = Execucao.objects.create(
        robo=robo, tipo=Execucao.Tipo.LEITURA_QUIZ, situacao=Execucao.Situacao.AGUARDANDO_DEPENDENCIA,
        pedido_por_membro_id=livia.pk, motivo="o provedor do modelo não respondeu",
    )
    recente = Execucao.objects.create(
        robo=robo, tipo=Execucao.Tipo.LEITURA_QUIZ, situacao=Execucao.Situacao.AGUARDANDO_DEPENDENCIA,
    )
    antigo = timezone.now() - timedelta(minutes=30)
    Execucao.objects.filter(pk=parada.pk).update(atualizada_em=antigo)
    avisos_equipe.varrer_trabalhos_parados()
    avisos_equipe.varrer_trabalhos_parados()
    avisos = AvisoDaEquipe.objects.filter(tipo="trabalho_parado")
    assert avisos.count() == 1
    assert avisos[0].responsavel == livia
    assert avisos[0].link.endswith(f"/execucoes/{parada.pk}")
    assert avisos[0].fato == f"execucao:{parada.pk}"
    assert not avisos.filter(fato=f"execucao:{recente.pk}").exists()


@respx.mock
def test_celulas_fora_do_ar_nao_derrubam_a_varredura():
    respx.get(LEADS + "/crm").mock(return_value=httpx.Response(503))
    respx.get(MENSAGERIA + "/conversas").mock(side_effect=httpx.ConnectError("fora"))
    avisos_equipe.varrer()
    assert AvisoDaEquipe.objects.count() == 0


# ---------------------------------------------------------------- as telas


@respx.mock
def test_o_painel_mostra_os_avisos_e_marcar_visto_abre_o_link():
    _correio()
    aviso, _ = avisos_equipe.avisar(
        "venda_assistida", site_id=SITE, fato="oportunidade:x", titulo="Venda aprovada: Ana",
        link=f"/admin/crm/{OPORTUNIDADE}/",
    )
    cliente = _cliente()
    resposta = cliente.get(reverse("avisos_da_equipe"))
    assert resposta.status_code == 200
    assert "Venda aprovada: Ana" in resposta.content.decode()
    resposta = cliente.post(reverse("aviso_visto", args=[aviso.pk]), {"abrir": "1"})
    assert resposta.status_code == 302 and resposta["Location"] == f"/admin/crm/{OPORTUNIDADE}/"
    aviso.refresh_from_db()
    assert aviso.visto_em is not None and aviso.visto_por == "Dono"
    assert "Venda aprovada: Ana" not in cliente.get(reverse("avisos_da_equipe")).content.decode()


@respx.mock
def test_a_pessoa_da_equipe_ve_os_dela_e_os_da_equipe_nao_os_de_outra_pessoa():
    _correio()
    livia = _livia()
    outra = MembroDaEquipe.objects.exclude(pk=livia.pk).first()
    avisos_equipe.avisar("pessoa_pedida", fato="a", titulo="Para Lívia", responsavel=LIVIA)
    avisos_equipe.avisar("conversa_ambigua", fato="b", titulo="Para a equipe")
    de_outra, _ = avisos_equipe.avisar("pessoa_pedida", fato="c", titulo="Para outra pessoa", responsavel=str(outra.pk))
    cliente = _cliente(LIVIA, nome="Lívia")
    texto = cliente.get(reverse("avisos_da_equipe")).content.decode()
    assert "Para Lívia" in texto and "Para a equipe" in texto
    assert "Para outra pessoa" not in texto
    assert cliente.post(reverse("aviso_visto", args=[de_outra.pk])).status_code == 404


# ------------------------------------------- o que a revisão de 04/10 pediu


def _conversas(*itens):
    respx.get(MENSAGERIA + "/conversas").mock(return_value=httpx.Response(200, json={"itens": list(itens)}))


def _conversa_passada(agora, **mudancas):
    return {
        "id": str(uuid.uuid4()), "site_id": SITE, "canal": "whatsapp", "estado": "pessoa",
        "assumida_por": "equipe", "assumida_em": agora.isoformat(), **mudancas,
    }


def _trabalho(minutos=30, **campos):
    base = dict(
        tipo="atender_mensagem", site_id=SITE, estado="aguardando_dependencia",
        chave_idempotencia=uuid.uuid4().hex, motivo="o provedor do modelo não respondeu",
    )
    base.update(campos)
    trabalho = TrabalhoComercial.objects.create(**base)
    TrabalhoComercial.objects.filter(pk=trabalho.pk).update(atualizado_em=timezone.now() - timedelta(minutes=minutos))
    return trabalho


@respx.mock
def test_trabalho_comercial_parado_avisa_mesmo_com_o_rotulo_de_app_do_site(monkeypatch):
    """No site o app se chama admin_comercial: `get_model("comercial", ...)` não acha."""
    _correio()
    original = avisos_equipe.django_apps.get_model

    def como_no_site(rotulo, modelo=None, *args, **kwargs):
        if rotulo == "comercial":
            raise LookupError(f"No installed app with label '{rotulo}'.")
        return original(rotulo, modelo, *args, **kwargs)

    monkeypatch.setattr(avisos_equipe.django_apps, "get_model", como_no_site)
    parado = _trabalho()
    incerto = _trabalho(estado="envio_incerto", chave_da_conversa="")
    avisos_equipe.varrer_trabalhos_parados()
    assert AvisoDaEquipe.objects.get(tipo="trabalho_parado").fato == f"trabalho_comercial:{parado.pk}:aguardando_dependencia"
    assert AvisoDaEquipe.objects.get(tipo="envio_incerto").fato == f"trabalho_comercial:{incerto.pk}:envio_incerto"


@respx.mock
def test_trabalho_comercial_avisa_uma_vez_por_trabalho_e_nao_por_tentativa_nem_pela_analise_da_hora():
    correio = _correio()
    parado = _trabalho()
    analise = _trabalho(tipo="analisar_resultados", estado="aguardando_dependencia")
    velho = _trabalho(minutos=60 * 24 * 3)
    for tentativa in range(3):
        TrabalhoComercial.objects.filter(pk=parado.pk).update(tentativas=tentativa)
        avisos_equipe.varrer_trabalhos_parados()
    avisos = AvisoDaEquipe.objects.filter(tipo="trabalho_parado")
    assert [a.fato for a in avisos] == [f"trabalho_comercial:{parado.pk}:aguardando_dependencia"]
    assert not avisos.filter(fato__contains=f":{analise.pk}:").exists()
    assert not avisos.filter(fato__contains=f":{velho.pk}:").exists()
    # A varredura não manda e-mail por conta própria: quem manda é o fim da volta.
    assert correio.call_count == 0
    avisos_equipe.enviar_emails_pendentes()
    assert correio.call_count == 1


@respx.mock
def test_uma_volta_cria_no_maximo_dez_avisos_de_trabalho_parado_e_o_resto_vem_na_seguinte():
    _correio()
    for _ in range(15):
        _trabalho()
    avisos_equipe.varrer_trabalhos_parados()
    assert AvisoDaEquipe.objects.filter(tipo="trabalho_parado").count() == avisos_equipe.AVISOS_DE_TRABALHO_POR_VOLTA == 10
    avisos_equipe.varrer_trabalhos_parados()
    assert AvisoDaEquipe.objects.filter(tipo="trabalho_parado").count() == 15
    avisos_equipe.varrer_trabalhos_parados()
    assert AvisoDaEquipe.objects.filter(tipo="trabalho_parado").count() == 15


@respx.mock
def test_quem_assumiu_pelo_painel_nao_recebe_aviso_de_conversa_passada():
    _correio()
    agora = timezone.now()
    assumida = _conversa_passada(agora, assumida_por=LIVIA)
    _conversas(assumida)
    avisos_equipe.varrer_conversas(SITE, agora)
    avisos_equipe.varrer_conversas(SITE, agora)
    assert not AvisoDaEquipe.objects.filter(tipo="pessoa_pedida").exists()
    _conversas(dict(assumida, assumida_por="equipe"))
    avisos_equipe.varrer_conversas(SITE, agora)
    assert AvisoDaEquipe.objects.filter(tipo="pessoa_pedida").count() == 1


@respx.mock
def test_varias_mensagens_sem_confirmacao_da_mesma_conversa_viram_um_aviso_so():
    _correio()
    agora = timezone.now()
    conversa = {
        "id": CONVERSA, "site_id": SITE, "canal": "whatsapp", "estado": "agente",
        "ultima_mensagem_em": (agora - timedelta(minutes=20)).isoformat(),
    }
    _conversas(conversa)
    incertas = [
        {"id": f"m{i}", "direcao": "saida", "estado_envio": "desconhecido",
         "ocorrida_em": (agora - timedelta(minutes=30 + i)).isoformat()}
        for i in range(3)
    ]
    mensagens = respx.get(MENSAGERIA + f"/conversas/{CONVERSA}/mensagens").mock(
        return_value=httpx.Response(200, json={"mensagens": incertas})
    )
    avisos_equipe.varrer_conversas(SITE, agora)
    avisos = AvisoDaEquipe.objects.filter(tipo="envio_incerto")
    assert avisos.count() == 1 and "3 mensagens" in avisos[0].texto
    # Conversa parada, já lida depois da tolerância: não se lê de novo.
    avisos_equipe.varrer_conversas(SITE, agora + timedelta(minutes=5))
    assert mensagens.call_count == 1 and avisos.count() == 1


@respx.mock
def test_o_que_ja_era_velho_na_primeira_volta_nao_vira_aviso():
    _correio()
    agora = timezone.now()
    velha = (agora - timedelta(days=3)).isoformat()
    antiga = _conversa_passada(agora, assumida_em=velha)
    ambigua_antiga = _conversa_passada(
        agora, estado="agente", ligacao="ambigua", ambigua=True, assumida_por=None, assumida_em=None,
        ultima_mensagem_em=velha,
    )
    _conversas(antiga, ambigua_antiga)
    avisos_equipe.varrer_conversas(SITE, agora)
    assert AvisoDaEquipe.objects.count() == 0
    _conversas(antiga, ambigua_antiga, _conversa_passada(agora))
    avisos_equipe.varrer_conversas(SITE, agora)
    assert AvisoDaEquipe.objects.filter(tipo="pessoa_pedida").count() == 1


@respx.mock
def test_uma_volta_manda_no_maximo_dez_emails_e_o_resto_sai_nas_voltas_seguintes(monkeypatch):
    correio = _correio()
    monkeypatch.setenv("AVISOS_EQUIPE_SITES", SITE)
    respx.get(LEADS + "/crm").mock(return_value=httpx.Response(503))
    agora = timezone.now()
    _conversas(*[_conversa_passada(agora) for _ in range(25)])
    avisos_equipe.varrer(agora)
    assert AvisoDaEquipe.objects.filter(tipo="pessoa_pedida").count() == 25
    assert correio.call_count == 10
    avisos_equipe.varrer(agora)
    assert correio.call_count == 20
    avisos_equipe.varrer(agora)
    assert correio.call_count == 25


@respx.mock
def test_receita_que_vem_no_quadro_nao_gera_pergunta_a_leads():
    _correio()
    item = _venda(receita={
        "aprovado_centavos": 19700, "liquido_centavos": 19700,
        "compras": [{"aprovado_em": timezone.now().isoformat()}],
    })
    respx.get(LEADS + "/crm").mock(return_value=httpx.Response(200, json=_quadro([item])))
    receita = respx.get(LEADS + f"/crm/{OPORTUNIDADE}/receita").mock(return_value=httpx.Response(200, json={}))
    avisos_equipe.varrer_vendas_assistidas()
    avisos_equipe.varrer_vendas_assistidas()
    assert receita.call_count == 0
    aviso = AvisoDaEquipe.objects.get(tipo="venda_assistida")
    assert "R$ 197,00" in aviso.texto


@respx.mock
def test_venda_aprovada_ha_mais_de_um_dia_nao_vira_aviso():
    _correio()
    antiga = _venda(receita={
        "aprovado_centavos": 19700, "liquido_centavos": 19700,
        "compras": [{"aprovado_em": (timezone.now() - timedelta(days=3)).isoformat()}],
    })
    respx.get(LEADS + "/crm").mock(return_value=httpx.Response(200, json=_quadro([antiga])))
    avisos_equipe.varrer_vendas_assistidas()
    assert not AvisoDaEquipe.objects.exists()


@respx.mock
def test_sem_receita_no_quadro_a_pergunta_a_leads_vale_por_um_tempo_e_nao_se_repete_depois_do_aviso():
    _correio()
    respx.get(LEADS + "/crm").mock(return_value=httpx.Response(200, json=_quadro([_venda()])))
    receita = respx.get(LEADS + f"/crm/{OPORTUNIDADE}/receita").mock(
        return_value=httpx.Response(200, json={"aprovado_centavos": 0, "liquido_centavos": 0})
    )
    for _ in range(3):
        avisos_equipe.varrer_vendas_assistidas()
    assert receita.call_count == 1
    receita.mock(return_value=httpx.Response(200, json={"aprovado_centavos": 19700, "liquido_centavos": 19700}))
    avisos_equipe._RECEITAS.clear()
    avisos_equipe.varrer_vendas_assistidas()
    assert receita.call_count == 2
    assert AvisoDaEquipe.objects.filter(tipo="venda_assistida").count() == 1
    avisos_equipe._RECEITAS.clear()
    avisos_equipe.varrer_vendas_assistidas()
    assert receita.call_count == 2


@respx.mock
def test_o_aviso_da_equipe_vai_tambem_para_os_administradores_promovidos_pela_tela():
    Administrador.objects.create(email="Promovida@exemplo.com")
    Administrador.objects.create(email="removida@exemplo.com", ativo=False)
    correio = _correio()
    avisos_equipe.avisar("conversa_ambigua", site_id=SITE, fato="conversa:77", titulo="Ambígua")
    destinos = sorted(json.loads(c.request.content)["destinatario"] for c in correio.calls)
    assert destinos == [DONO, "promovida@exemplo.com"]


@respx.mock
def test_par_sem_grau_de_publicacao_nao_faz_o_email_desistir():
    rota = respx.post(MENSAGERIA + "/avisos-equipe").mock(return_value=httpx.Response(403))
    aviso, _ = avisos_equipe.avisar("envio_incerto", site_id=SITE, fato="x", titulo="Incerto")
    for _ in range(avisos_equipe.MAXIMO_DE_TENTATIVAS + 2):
        avisos_equipe.enviar_emails_pendentes()
    aviso.refresh_from_db()
    assert aviso.email_situacao == AvisoDaEquipe.Email.PENDENTE and aviso.email_tentativas == 0
    assert "grau de publicação" in aviso.email_erro
    rota.mock(return_value=httpx.Response(200, json={"envio_id": 1, "criado": True, "status": "pendente"}))
    avisos_equipe.enviar_emails_pendentes()
    aviso.refresh_from_db()
    assert aviso.email_situacao == AvisoDaEquipe.Email.PEDIDO and aviso.email_erro == ""


@respx.mock
def test_ligacao_com_a_mensageria_sem_configurar_nao_faz_o_email_desistir(monkeypatch):
    monkeypatch.delenv("MENSAGERIA_API_TOKEN")
    aviso, _ = avisos_equipe.avisar("envio_incerto", site_id=SITE, fato="x", titulo="Incerto")
    for _ in range(avisos_equipe.MAXIMO_DE_TENTATIVAS + 2):
        avisos_equipe.enviar_emails_pendentes()
    aviso.refresh_from_db()
    assert aviso.email_situacao == AvisoDaEquipe.Email.PENDENTE and aviso.email_tentativas == 0


@respx.mock
def test_pessoa_de_cracha_recebe_a_venda_sem_nome_valor_nem_link_do_painel_do_dono():
    correio = _correio()
    _livia()
    texto = "O pagamento de Ana foi aprovado (R$ 197,00 líquido), numa oportunidade atendida pelo agente."
    avisos_equipe.avisar(
        "venda_assistida", site_id=SITE, fato="oportunidade:cracha", responsavel=LIVIA,
        titulo="Venda aprovada: Ana", texto=texto, link=f"/admin/crm/{OPORTUNIDADE}/",
    )
    corpo = json.loads(correio.calls.last.request.content)
    assert corpo["destinatario"] == LIVIA
    assert "Ana" not in corpo["corpo"] and "197" not in corpo["corpo"]
    assert "/admin/crm/" not in corpo["corpo"] and "/admin/equipe/avisos/" in corpo["corpo"]
    # A administração recebe o aviso inteiro, com o link.
    avisos_equipe.avisar(
        "venda_assistida", site_id=SITE, fato="oportunidade:dono",
        titulo="Venda aprovada: Ana", texto=texto, link=f"/admin/crm/{OPORTUNIDADE}/",
    )
    corpo = json.loads(correio.calls.last.request.content)
    assert corpo["destinatario"] == DONO
    assert "Ana" in corpo["corpo"] and "R$ 197,00" in corpo["corpo"]
    assert f"https://meshcraft.top/admin/crm/{OPORTUNIDADE}/" in corpo["corpo"]


@respx.mock
def test_o_painel_da_pessoa_de_cracha_esconde_o_dado_do_cliente_e_o_link_que_leva_a_404():
    _correio()
    _livia()
    venda, _ = avisos_equipe.avisar(
        "venda_assistida", site_id=SITE, fato="oportunidade:painel", titulo="Venda aprovada: Ana",
        texto="O pagamento de Ana foi aprovado (R$ 197,00 líquido).", link=f"/admin/crm/{OPORTUNIDADE}/",
    )
    parado, _ = avisos_equipe.avisar(
        "trabalho_parado", fato="execucao:9", titulo="Trabalho parado: Leitura",
        link="/admin/equipe/robo/execucoes/9",
    )
    cracha = _cliente(LIVIA, nome="Lívia")
    pagina = cracha.get(reverse("avisos_da_equipe")).content.decode()
    assert "Ana" not in pagina and "197" not in pagina
    assert "Venda aprovada com atendimento do agente" in pagina
    assert pagina.count('name="abrir" value="1"') == 1
    resposta = cracha.post(reverse("aviso_visto", args=[venda.pk]), {"abrir": "1"})
    assert resposta.status_code == 302 and resposta["Location"] == reverse("avisos_da_equipe")
    resposta = cracha.post(reverse("aviso_visto", args=[parado.pk]), {"abrir": "1"})
    assert resposta["Location"] == "/admin/equipe/robo/execucoes/9"
    dono = _cliente().get(reverse("avisos_da_equipe") + "?mostrar=todos").content.decode()
    assert "Venda aprovada: Ana" in dono and "R$ 197,00" in dono
    assert dono.count('name="abrir" value="1"') == 2


# ------------------------------------------------------ onde a varredura roda


def test_a_varredura_dos_avisos_nao_roda_dentro_do_reacordar(monkeypatch):
    """`reacordar()` roda dentro do clique de /admin/robos/: sem rede ali."""
    from apps.agentes import executor

    chamadas = []
    monkeypatch.setattr(avisos_equipe, "varrer", lambda *a, **k: chamadas.append(1))
    executor.reacordar()
    assert chamadas == []
    executor._avisar_a_equipe()
    assert chamadas == [1]


def test_o_laco_de_fundo_roda_a_varredura_dos_avisos(monkeypatch):
    from apps.agentes import executor

    chamadas = []
    monkeypatch.setattr(executor, "_avisar_a_equipe", lambda: chamadas.append(1))
    monkeypatch.setattr(executor, "reacordar", lambda: 0)
    monkeypatch.setattr(executor, "rodar_uma", lambda trabalhador: None)
    monkeypatch.setattr(executor, "_comercial", lambda *a: None)
    monkeypatch.setattr(executor, "_transcrever_audios", lambda: None)
    monkeypatch.setattr(executor, "close_old_connections", lambda: None)
    monkeypatch.setattr(executor, "INTERVALO_SEM_TRABALHO", 30.0)
    monkeypatch.setattr("apps.agentes.conhecimento_comercial.manter_em_dia", lambda **_: None)
    parar = threading.Event()
    laco = threading.Thread(target=executor.rodar_para_sempre, args=(parar,), daemon=True)
    laco.start()
    try:
        limite = time.monotonic() + 5
        while not chamadas and time.monotonic() < limite:
            time.sleep(0.01)
        assert chamadas == [1]
    finally:
        parar.set()
        executor.acordar()
        laco.join(timeout=5)
        executor._acordar.clear()
