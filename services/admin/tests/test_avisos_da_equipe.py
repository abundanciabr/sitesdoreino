"""Avisos para a equipe: um aviso por fato, no painel e por e-mail."""
import json
from datetime import timedelta

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.agentes.models import Execucao, RoboPessoal
from apps.core import avisos_equipe
from apps.core.models import AvisoDaEquipe, MembroDaEquipe

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
    assert "https://meshcraft.top/admin/crm/" in corpo["corpo"]
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
        "ambigua": False, "estado": "pessoa", "assumida_por": LIVIA, "assumida_em": agora.isoformat(),
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
    assert pedida.site_id == SITE and pedida.responsavel.email == LIVIA
    assert pedida.link == f"/admin/contatos/{LEAD}/"
    assert AvisoDaEquipe.objects.get(tipo="conversa_ambigua").responsavel is None
    incerto = AvisoDaEquipe.objects.get(tipo="envio_incerto")
    assert incerto.fato == "mensagem:m-velha"
    assert "não entra no aviso" not in incerto.texto
    assert AvisoDaEquipe.objects.count() == 3


@respx.mock
def test_passar_de_novo_depois_de_devolver_e_outro_aviso():
    _correio()
    primeira = {"id": CONVERSA, "site_id": SITE, "estado": "pessoa", "assumida_em": "2026-10-03T10:00:00+00:00"}
    segunda = dict(primeira, assumida_em="2026-10-03T12:00:00+00:00")
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
    assert not avisos.filter(fato__startswith=f"execucao:{recente.pk}:").exists()


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
