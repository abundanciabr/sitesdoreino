import json
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.links.models import LinkIndividual
from apps.conversas import entrada, envio, interacoes
from apps.conversas.models import Conversa
from apps.whatsapp import service
from apps.whatsapp.models import ConfiguracaoWhatsApp, MensagemWhatsApp


@pytest.mark.parametrize("conteudo", [
    {"buttonsResponseMessage": {"selectedButtonId": "meshcraft:cursos", "contextInfo": {"stanzaId": "ENVIADA"}}},
    {"templateButtonReplyMessage": {"selectedId": "meshcraft:cursos", "contextInfo": {"stanzaId": "ENVIADA"}}},
    {"listResponseMessage": {"singleSelectReply": {"selectedRowId": "meshcraft:cursos"}, "contextInfo": {"stanzaId": "ENVIADA"}}},
    {"interactiveResponseMessage": {"nativeFlowResponseMessage": {"paramsJson": '{"id":"meshcraft:cursos"}'}, "contextInfo": {"stanzaId": "ENVIADA"}}},
])
def test_clique_vira_fala_e_preserva_citacao(conteudo):
    item = {"key": {"remoteJid": "5511971815639@s.whatsapp.net", "id": "CLIQUE"},
            "message": {"ephemeralMessage": {"message": conteudo}}}
    recebida = entrada.de_evolution(site_id="site", instancia="inst", item=item)
    assert recebida.texto == "Conhecer cursos"
    assert recebida.em_resposta_a == "ENVIADA"
    assert recebida.id_externo == "CLIQUE"
    item["key"]["fromMe"] = True
    assert entrada.de_evolution(site_id="site", instancia="inst", item=item) is None


def test_native_flow_invalido_ainda_recebe_resposta():
    assert interacoes.resposta({"interactiveResponseMessage": {
        "body": {"text": "Escolhi outra opção"}, "nativeFlowResponseMessage": {"paramsJson": "{errado"}}})[0] == "Escolhi outra opção"


def test_cloud_entende_id_e_contexto():
    msg = entrada.de_cloud(site_id="site", numero_id="inst", item={"from": "5511971815639", "id": "CLIQUE",
        "type": "interactive", "interactive": {"list_reply": {"id": "meshcraft:acesso"}}, "context": {"id": "ENVIADA"}})
    assert msg.texto == "Acesso às aulas" and msg.em_resposta_a == "ENVIADA"


@pytest.mark.parametrize("tipo,endpoint", [("botoes", "sendButtons"), ("lista", "sendList"), ("links", "sendButtons")])
@pytest.mark.django_db(transaction=True)
def test_texto_e_componente_tem_chaves_duraveis_e_nao_repetem(monkeypatch, tipo, endpoint):
    ConfiguracaoWhatsApp.objects.create(site_id="site", instancia="inst", ativo=True)
    conversa = Conversa.objects.create(site_id="site", canal="whatsapp", endereco="5511971815639",
                                      janela_aberta_ate=timezone.now() + timedelta(hours=24))
    chamadas = []
    def gateway(method, caminho, dados=None):
        chamadas.append((caminho, dados))
        return {"key": {"id": f"WA-{len(chamadas)}"}}
    monkeypatch.setattr(service, "estado_da_conexao", lambda site: {"estado": "open"})
    monkeypatch.setattr(service, "_gateway", gateway)
    kwargs = dict(conversa=conversa, texto="Vamos conversar: https://meshcraft.top/cursos/", autor="pessoa",
                  chave_idempotencia="menu-1", interacao=tipo)
    saida = envio.enviar(**kwargs)
    assert saida.resultado == "enviada"
    assert chamadas[0][0] == "message/sendText/inst"
    assert chamadas[1][0] == f"message/{endpoint}/inst"
    if tipo == "lista":
        assert all(row["description"].strip() for row in chamadas[1][1]["sections"][0]["rows"])
    # O link do WhatsApp sai como /r/<token>; o destino guardado é o original.
    assert "https://meshcraft.top/r/" in saida.mensagem.texto
    assert LinkIndividual.objects.get().url_original == "https://meshcraft.top/cursos/"
    if tipo != "links":
        assert "1. Conhecer cursos" in saida.mensagem.texto
    assert envio.enviar(**kwargs).resultado == "repetida"
    assert len(chamadas) == 2
    assert MensagemWhatsApp.objects.count() == 2


@pytest.mark.django_db(transaction=True)
def test_componente_falha_sem_perder_a_resposta_em_texto(monkeypatch):
    ConfiguracaoWhatsApp.objects.create(site_id="site", instancia="inst", ativo=True)
    conversa = Conversa.objects.create(site_id="site", canal="whatsapp", endereco="5511971815639",
                                      janela_aberta_ate=timezone.now() + timedelta(hours=24))
    def gateway(method, caminho, dados=None):
        if "sendButtons" in caminho:
            raise service.GatewayIndisponivel("gateway respondeu HTTP 400")
        return {"key": {"id": "TEXTO"}}
    monkeypatch.setattr(service, "estado_da_conexao", lambda site: {"estado": "open"})
    monkeypatch.setattr(service, "_gateway", gateway)
    saida = envio.enviar(conversa=conversa, texto="Olá", chave_idempotencia="menu", autor="pessoa", interacao="botoes")
    assert saida.resultado == "enviada" and saida.mensagem.id_externo == "TEXTO"
    assert "3. Já sou aluno" in saida.mensagem.texto
    assert MensagemWhatsApp.objects.get(origem="conversa-interativa").status == "desconhecido"


@pytest.mark.django_db(transaction=True)
def test_reentrega_do_clique_emite_um_so_evento(monkeypatch):
    from apps.conversas import leads, orientacao
    from apps.jornadas.models import OutboxEvent
    monkeypatch.setattr(leads, "procurar", lambda **kw: leads.Ligacao("desconhecida"))
    monkeypatch.setattr(orientacao, "apos_receber", lambda *a, **kw: "desligada")
    recebida = entrada.de_evolution(site_id="site", instancia="inst", item={
        "key": {"remoteJid": "5511971815639@s.whatsapp.net", "id": "CLIQUE"},
        "message": {"buttonsResponseMessage": {"selectedButtonId": "meshcraft:duvidas"}}})
    assert entrada.receber(recebida)[1] is True
    assert entrada.receber(recebida)[1] is False
    assert OutboxEvent.objects.filter(event="mensagem.recebida").count() == 1
