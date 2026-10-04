"""Recusa, Pix vencido e estorno chamam o agente certo (`apps/comercial/recuperacao.py`).

Tudo é SIMULAÇÃO: o modelo e as APIs das outras células respondem com `respx`;
nenhuma mensagem sai de verdade. Os testes provam o caminho do sistema (o gatilho,
as conferências antes de falar com o lead, o link ligado à mesma oportunidade, uma
só mensagem e o estorno sem conversa), não que o modelo escreve bem.
"""

from __future__ import annotations

import json
from datetime import timedelta

import pytest
import respx
from django.utils import timezone

from apps.comercial import coordenador, eventos
from apps.comercial.models import DecisaoComercial, EventoComercial, TrabalhoComercial
from apps.core.models import AvisoDaEquipe
from tests.test_comercial import (  # noqa: F401  (ambiente é fixture automática)
    CHECKOUT,
    EMAIL,
    LEADS,
    MENSAGERIA,
    RESPOSTAS,
    _chamada,
    _corpo,
    _envelope,
    _final,
    _guardar_chave,
    _resto_404,
    ambiente,
)

E = TrabalhoComercial.Estado
T = TrabalhoComercial.Tipo
R = DecisaoComercial.Resultado

TESTE = "ciclo-1@example.com"


def _falha(nome="pagamento.recusado", *, email=EMAIL, pedido="ped-9", tentativa="pay-1", event_id=None, **extra):
    data = {"platform_site_id": "site-1", "payment_id": tentativa, "order_id": pedido, "method": "card",
            "provider": "mercadopago", "provider_reference_id": "ref-1", "reason_code": "cc_rejected",
            "customer": {"email": email, "name": "Ana Souza"}, "oportunidade_ref": "opp-1",
            "oferta_ref": "curso-3d", "context": {"host": "meshcraft.top"}}
    if nome == "pix.expirado":
        data = {"site_id": "site-1", "payment_id": tentativa, "order_id": pedido,
                "customer": {"email": email, "name": "Ana Souza"}, "recovery_url": "https://x/y",
                "oportunidade_ref": "opp-1", "oferta_ref": "curso-3d", "context": {"host": "meshcraft.top"}}
    data.update(extra)
    return _envelope(nome, data, event_id)


def _reversao(event_id=None, **extra):
    data = {"platform_site_id": "site-1", "provider": "appmax", "provider_reference_id": "ref-7",
            "motivo": "estorno", "order_id": "ped-9", "oportunidade_ref": "opp-1",
            "context": {"host": "meshcraft.top"}}
    data.update(extra)
    return _envelope("pagamento.reversao_confirmada", data, event_id)


def _recuperacoes():
    return TrabalhoComercial.objects.filter(tipo=T.RECUPERAR_COMPRA)


def _pronto_para_rodar(trabalho):
    TrabalhoComercial.objects.filter(pk=trabalho.pk).update(nao_antes_de=None)


def _checkout_sem_pagamento(pedido="ped-9"):
    respx.get(f"{CHECKOUT}/interno/pedidos/{pedido}/pagamento").respond(200, json={
        "pedido_id": pedido, "status": "aguardando_dados", "confirmado": False, "reembolsado": False})
    respx.get(f"{CHECKOUT}/interno/pedidos").respond(200, json={"pedidos": [], "links": []})


def _conversa(estado="agente", descadastrado=False, mensagens=()):
    respx.get(f"{MENSAGERIA}/conversas").respond(200, json={"itens": [
        {"id": "conv-1", "site_id": "site-1", "lead_id": "lead-1", "canal": "email", "estado": estado,
         "descadastrado": descadastrado}]})
    respx.get(f"{MENSAGERIA}/conversas/conv-1/mensagens").respond(200, json={
        "conversa": {"id": "conv-1", "site_id": "site-1", "canal": "email", "estado": estado},
        "mensagens": list(mensagens)})


def _ficha_do_lead():
    respx.get(f"{LEADS}/leads").respond(200, json={"itens": [
        {"id": "lead-1", "site_id": "site-1", "email": EMAIL, "nome": "Ana Souza"}]})


def _condicoes(liberadas):
    respx.get(f"{CHECKOUT}/interno/ofertas/curso-3d/condicoes-agente").respond(200, json={
        "site_id": "site-1", "oferta": {"oferta_ref": "curso-3d", "preco": "R$ 497,00"},
        "preco_vigente": {"cents": 49700, "texto": "R$ 497,00", "moeda": "BRL"}, "condicoes": liberadas})


PIX = {"id": "pix", "metodo": "pix", "total_cents": 49700}


# ---------------------------------------------------------------- gatilhos


def test_recusa_de_lead_real_cria_um_trabalho_que_espera_o_lead_reabrir_o_link():
    antes = timezone.now()
    trabalho = eventos.tratar("eventos.pagamento.recusado", _falha(event_id="ev-1"))
    assert _recuperacoes().count() == 1
    assert trabalho.tipo == T.RECUPERAR_COMPRA and trabalho.papel == "atendimento"
    assert trabalho.pedido_id == "ped-9" and trabalho.oportunidade_id == "opp-1"
    assert trabalho.chave_idempotencia == "recuperar:site-1:ped-9:pay-1"
    assert trabalho.entrada["oferta_ref"] == "curso-3d" and trabalho.entrada["pedido_recusado"] == "ped-9"
    assert trabalho.entrada["motivo_da_falha"] == "pagamento.recusado"
    assert not trabalho.teste
    assert timedelta(minutes=9) < trabalho.nao_antes_de - antes < timedelta(minutes=11)
    assert EventoComercial.objects.get(event_id="ev-1").pedido_id == "ped-9"
    # Ainda não é hora: o executor não pega.
    assert coordenador.pegar_um("t1") is None


def test_pix_vencido_tambem_abre_a_recuperacao_e_a_reentrega_nao_duplica():
    envelope = _falha("pix.expirado", tentativa="pay-2", event_id="ev-pix")
    eventos.tratar("eventos.pix.expirado", envelope)
    eventos.tratar("eventos.pix.expirado", envelope)
    trabalho = _recuperacoes().get()
    assert trabalho.entrada["motivo_da_falha"] == "pix.expirado"
    assert EventoComercial.objects.filter(event_id="ev-pix").count() == 1


def test_mesmo_event_id_duas_vezes_cria_um_e_a_mesma_tentativa_com_outro_evento_tambem():
    eventos.tratar("eventos.pagamento.recusado", _falha(event_id="ev-1"))
    eventos.tratar("eventos.pagamento.recusado", _falha(event_id="ev-1"))
    assert _recuperacoes().count() == 1
    eventos.tratar("eventos.pagamento.recusado", _falha(event_id="ev-2"))  # mesma tentativa, outro envelope
    assert _recuperacoes().count() == 1
    eventos.tratar("eventos.pagamento.recusado", _falha(event_id="ev-3", tentativa="pay-2"))  # outra tentativa
    assert _recuperacoes().count() == 2


def test_recusa_de_contato_de_teste_vira_trabalho_de_teste_e_sem_pedido_nao_cria_nada():
    eventos.tratar("eventos.pagamento.recusado", _falha(email=TESTE))
    assert _recuperacoes().get().teste is True
    eventos.tratar("eventos.pagamento.recusado", _falha(pedido="ped-2", tentativa="p2", ambiente="sandbox"))
    assert _recuperacoes().get(pedido_id="ped-2").teste is True
    eventos.tratar("eventos.pagamento.recusado", _falha(order_id=""))
    assert _recuperacoes().count() == 2


def test_desligado_no_ambiente_a_recusa_nao_cria_trabalho(monkeypatch):
    monkeypatch.setenv("COMERCIAL_AGENTES", "desligado")
    eventos.tratar("eventos.pagamento.recusado", _falha())
    assert not TrabalhoComercial.objects.exists()


def test_os_tres_fluxos_novos_estao_assinados():
    for stream in ("eventos.pagamento.recusado", "eventos.pix.expirado", "eventos.pagamento.reversao_confirmada"):
        assert stream in eventos.STREAMS


# ---------------------------------------------------------------- pago antes de falar


@respx.mock
def test_pago_depois_do_recusado_nao_envia_nada_nem_chama_o_modelo():
    _guardar_chave()
    na_fila = eventos.tratar("eventos.pagamento.recusado", _falha())
    eventos.tratar("eventos.pagamento.aprovado", _envelope("pagamento.aprovado", {
        "site_id": "site-1", "order_id": "ped-9", "oportunidade_ref": "opp-1", "customer": {"email": EMAIL}}))
    na_fila.refresh_from_db()
    assert na_fila.estado == E.ENCERRADO
    openai = respx.post(RESPOSTAS)
    envio = respx.post(f"{MENSAGERIA}/conversas/conv-1/mensagens")
    _resto_404()
    assert coordenador.rodar_um("t1") is None
    assert not openai.called and not envio.called

    # Recusa que chega DEPOIS do pagamento (fora de ordem): o trabalho nasce e se encerra sozinho.
    eventos.tratar("eventos.pagamento.recusado", _falha(tentativa="pay-tardia"))
    tardio = _recuperacoes().get(chave_idempotencia="recuperar:site-1:ped-9:pay-tardia")
    _pronto_para_rodar(tardio)
    coordenador.rodar_um("t1")
    tardio.refresh_from_db()
    assert tardio.estado == E.ENCERRADO and "aprovado" in tardio.motivo
    assert not openai.called and not envio.called


@respx.mock
def test_outro_pedido_da_mesma_oportunidade_ja_pago_encerra_sem_enviar():
    _guardar_chave()
    trabalho = eventos.tratar("eventos.pagamento.recusado", _falha())
    _pronto_para_rodar(trabalho)
    respx.get(f"{CHECKOUT}/interno/pedidos/ped-9/pagamento").respond(200, json={
        "pedido_id": "ped-9", "status": "recusado", "confirmado": False})
    respx.get(f"{CHECKOUT}/interno/pedidos").respond(200, json={"pedidos": [
        {"pedido_id": "ped-8", "status": "pago", "confirmado": True, "reembolsado": False}]})
    openai = respx.post(RESPOSTAS)
    _resto_404()
    coordenador.rodar_um("t1")
    trabalho.refresh_from_db()
    assert trabalho.estado == E.ENCERRADO
    assert not openai.called


# ---------------------------------------------------------------- a recuperação


@respx.mock
def test_pix_vencido_com_condicao_pix_liberada_prepara_o_link_da_mesma_oportunidade_e_manda_uma_mensagem():
    _guardar_chave()
    trabalho = eventos.tratar("eventos.pix.expirado", _falha("pix.expirado", event_id="ev-pix"))
    _pronto_para_rodar(trabalho)
    _ficha_do_lead()
    _checkout_sem_pagamento()
    _conversa()
    _condicoes([PIX])
    link = respx.post(f"{CHECKOUT}/interno/links-de-compra").respond(201, json={
        "url": "https://meshcraft.top/checkout/curso-3d/?link=2", "pedido_id": "ped-10", "valor": "R$ 497,00",
        "vencimento": None, "vencimento_pix_minutos": 30})
    envio = respx.post(f"{MENSAGERIA}/conversas/conv-1/mensagens").respond(200, json={
        "resultado": "enviada", "mensagem": {"id": "msg-1"}, "conversa": {"canal": "email"}})
    respx.patch(f"{LEADS}/crm/opp-1/acompanhamento").respond(200, json={})
    _resto_404()
    texto = {"texto": "Oi Ana, o Pix venceu. Aqui está um link novo: https://meshcraft.top/checkout/curso-3d/?link=2",
             "canal": None, "assunto": "Seu link novo", "razao": "Pix venceu", "fonte": "condições liberadas"}
    openai = respx.post(RESPOSTAS).mock(side_effect=[
        _chamada("consultar_pagamento", {"pedido_id": None}, "c1"),
        _chamada("consultar_condicoes_compra", {"oferta_ref": None}, "c2"),
        _chamada("preparar_link_compra", {"oferta_ref": None, "condicao_id": "pix"}, "c3"),
        _chamada("enviar_mensagem", texto, "c4"),
        _chamada("enviar_mensagem", texto, "c5"),  # o modelo pede de novo: a segunda não sai
        _final({"acao": "respondeu", "resumo": "link novo enviado", "objecao_principal": None,
                "proximo_passo": "pagar o Pix"}),
    ])
    coordenador.rodar_um("t1")
    trabalho.refresh_from_db()
    assert trabalho.estado == E.CONCLUIDO, trabalho.motivo
    corpo = _corpo(link.calls[0])
    assert corpo["oportunidade_ref"] == "opp-1" and corpo["oferta"] == "curso-3d" and corpo["condicao"] == "pix"
    assert link.call_count == 1
    assert envio.call_count == 1
    assert "link=2" in _corpo(envio.calls[0])["texto"]
    assert trabalho.pedido_id == "ped-10" and trabalho.entrada["pedido_recusado"] == "ped-9"
    assert trabalho.resultado["mensagem_enviada"] is True and trabalho.resultado["link_preparado"] is True
    assert trabalho.decisoes.get(call_id="c5").saida["ja_feito"] is True
    assert trabalho.decisoes.filter(ferramenta="preparar_link_compra", resultado=R.FEITO).exists()
    assert {d.versao_estrategia for d in trabalho.decisoes.all()} == {1}
    # O pedido ao modelo diz o que aconteceu e não leva e-mail nem telefone.
    primeiro = openai.calls[0].request.content.decode()
    assert "Pix venceu" in primeiro and "ped-9" in primeiro
    assert EMAIL not in primeiro and "11999990000" not in primeiro
    assert not AvisoDaEquipe.objects.exists()  # mandou a mensagem: ninguém precisa agir


@respx.mock
def test_sem_condicao_liberada_passa_para_uma_pessoa_sem_chamar_o_modelo_e_abre_aviso():
    _guardar_chave()
    trabalho = eventos.tratar("eventos.pagamento.recusado", _falha())
    _pronto_para_rodar(trabalho)
    _ficha_do_lead()
    _checkout_sem_pagamento()
    _conversa()
    _condicoes([])  # o mantenedor não liberou nenhuma condição
    assumir = respx.post(f"{MENSAGERIA}/conversas/conv-1/assumir").respond(200, json={})
    nota = respx.patch(f"{LEADS}/crm/opp-1/acompanhamento").respond(200, json={})
    envio = respx.post(f"{MENSAGERIA}/conversas/conv-1/mensagens")
    openai = respx.post(RESPOSTAS)
    _resto_404()
    coordenador.rodar_um("t1")
    trabalho.refresh_from_db()
    assert trabalho.estado == E.CONCLUIDO, trabalho.motivo
    assert not openai.called and not envio.called
    assert assumir.called and nota.called
    decisao = trabalho.decisoes.get(ferramenta="passar_para_responsavel")
    assert decisao.resultado == R.FEITO and decisao.versao_estrategia == 1
    assert "Nenhuma condição" in decisao.entrada["motivo"]
    assert trabalho.resultado["passou_para_pessoa"] is True and trabalho.resultado["mensagem_enviada"] is False
    aviso = AvisoDaEquipe.objects.get()
    assert aviso.site_id == "site-1" and "ped-9" in aviso.texto
    assert EMAIL not in aviso.texto and "Ana" not in aviso.texto
    # Rodar de novo (a mesma decisão guardada) não abre outro aviso.
    from apps.comercial import recuperacao
    recuperacao._avisar_a_equipe(trabalho, titulo="x", texto="y", fato="recuperacao:site-1:ped-9")
    assert AvisoDaEquipe.objects.count() == 1


@respx.mock
def test_contato_de_teste_passa_para_pessoa_mas_nao_abre_aviso():
    _guardar_chave()
    trabalho = eventos.tratar("eventos.pagamento.recusado", _falha(email=TESTE))
    _pronto_para_rodar(trabalho)
    respx.get(f"{LEADS}/leads").respond(200, json={"itens": [
        {"id": "lead-1", "site_id": "site-1", "email": TESTE, "nome": "Ciclo"}]})
    _checkout_sem_pagamento()
    _conversa()
    _condicoes([])
    respx.post(f"{MENSAGERIA}/conversas/conv-1/assumir").respond(200, json={})
    respx.patch(f"{LEADS}/crm/opp-1/acompanhamento").respond(200, json={})
    _resto_404()
    coordenador.rodar_um("t1")
    trabalho.refresh_from_db()
    assert trabalho.estado == E.CONCLUIDO and trabalho.teste is True
    assert not AvisoDaEquipe.objects.exists()


@respx.mock
def test_canal_barrado_passa_para_uma_pessoa_em_vez_de_insistir():
    _guardar_chave()
    trabalho = eventos.tratar("eventos.pagamento.recusado", _falha())
    _pronto_para_rodar(trabalho)
    _ficha_do_lead()
    _checkout_sem_pagamento()
    _conversa()
    _condicoes([PIX])
    respx.post(f"{CHECKOUT}/interno/links-de-compra").respond(201, json={
        "url": "https://meshcraft.top/checkout/curso-3d/?link=2", "pedido_id": "ped-10"})
    envio = respx.post(f"{MENSAGERIA}/conversas/conv-1/mensagens").respond(200, json={"resultado": "descadastrado"})
    respx.post(f"{MENSAGERIA}/conversas/conv-1/assumir").respond(200, json={})
    respx.patch(f"{LEADS}/crm/opp-1/acompanhamento").respond(200, json={})
    _resto_404()
    texto = {"texto": "Oi Ana, segue o link novo.", "canal": None, "assunto": None, "razao": "recusa",
             "fonte": "condições"}
    respx.post(RESPOSTAS).mock(side_effect=[
        _chamada("preparar_link_compra", {"oferta_ref": None, "condicao_id": "pix"}, "c1"),
        _chamada("enviar_mensagem", texto, "c2"),
        _final({"acao": "respondeu", "resumo": "tentei", "objecao_principal": None, "proximo_passo": "—"}),
    ])
    coordenador.rodar_um("t1")
    trabalho.refresh_from_db()
    assert trabalho.estado == E.CONCLUIDO, trabalho.motivo
    assert envio.call_count == 1
    assert trabalho.decisoes.get(call_id="c2").resultado == R.RECUSADO
    assert trabalho.resultado["mensagem_enviada"] is False and trabalho.resultado["passou_para_pessoa"] is True
    assert trabalho.decisoes.filter(ferramenta="passar_para_responsavel", resultado=R.FEITO).exists()
    assert AvisoDaEquipe.objects.count() == 1


@pytest.mark.parametrize("cenario", ["pessoa_assumiu", "descadastrado", "jornada_ja_enviou"])
@respx.mock
def test_pessoa_descadastro_ou_jornada_recente_encerram_sem_enviar(cenario):
    _guardar_chave()
    trabalho = eventos.tratar("eventos.pagamento.recusado", _falha())
    _pronto_para_rodar(trabalho)
    _ficha_do_lead()
    _checkout_sem_pagamento()
    recente = (timezone.now() - timedelta(hours=3)).isoformat()
    if cenario == "pessoa_assumiu":
        _conversa(estado="pessoa")
    elif cenario == "descadastrado":
        _conversa(descadastrado=True)
    else:
        _conversa(mensagens=[{"direcao": "saida", "autor": "sistema", "texto": "Seu pagamento não foi aprovado",
                              "ocorrida_em": recente}])
    openai = respx.post(RESPOSTAS)
    envio = respx.post(f"{MENSAGERIA}/conversas/conv-1/mensagens")
    _resto_404()
    coordenador.rodar_um("t1")
    trabalho.refresh_from_db()
    assert trabalho.estado == E.ENCERRADO, trabalho.motivo
    assert not openai.called and not envio.called


@respx.mock
def test_jornada_de_mais_de_24_horas_atras_nao_impede():
    _guardar_chave()
    trabalho = eventos.tratar("eventos.pagamento.recusado", _falha())
    _pronto_para_rodar(trabalho)
    _ficha_do_lead()
    _checkout_sem_pagamento()
    _conversa(mensagens=[{"direcao": "saida", "autor": "sistema", "texto": "velha",
                          "ocorrida_em": (timezone.now() - timedelta(hours=30)).isoformat()}])
    _condicoes([PIX])
    respx.post(RESPOSTAS).mock(side_effect=[_final({
        "acao": "sem_resposta", "resumo": "nada a fazer", "objecao_principal": None, "proximo_passo": "—"})])
    _resto_404()
    coordenador.rodar_um("t1")
    trabalho.refresh_from_db()
    assert trabalho.estado == E.CONCLUIDO and trabalho.resultado["mensagem_enviada"] is False
    assert not AvisoDaEquipe.objects.exists()  # o agente decidiu não falar: ninguém precisa agir


@respx.mock
def test_segunda_recusa_do_mesmo_lead_nas_24_horas_nao_manda_outra_mensagem():
    _guardar_chave()
    primeira = eventos.tratar("eventos.pagamento.recusado", _falha(tentativa="pay-1"))
    TrabalhoComercial.objects.filter(pk=primeira.pk).update(
        estado=E.CONCLUIDO, contato_id="lead-1", nao_antes_de=None)
    DecisaoComercial.objects.create(trabalho=primeira, call_id="c9", ferramenta="enviar_mensagem",
                                    resultado=R.FEITO, papel="atendimento")
    segunda = eventos.tratar("eventos.pagamento.recusado", _falha(tentativa="pay-2"))
    _pronto_para_rodar(segunda)
    _ficha_do_lead()
    _checkout_sem_pagamento()
    _conversa()
    openai = respx.post(RESPOSTAS)
    _resto_404()
    coordenador.rodar_um("t1")
    segunda.refresh_from_db()
    assert segunda.estado == E.ENCERRADO and "24 horas" in segunda.motivo
    assert not openai.called


@respx.mock
def test_quem_comprou_sem_ser_contato_de_quiz_nao_recebe_recuperacao_do_agente():
    _guardar_chave()
    trabalho = eventos.tratar("eventos.pagamento.recusado", _falha(oportunidade_ref=""))
    TrabalhoComercial.objects.filter(pk=trabalho.pk).update(
        nao_antes_de=None, criado_em=timezone.now() - timedelta(hours=1))
    _checkout_sem_pagamento()
    respx.get(f"{LEADS}/leads").respond(200, json={"itens": []})
    openai = respx.post(RESPOSTAS)
    _resto_404()
    coordenador.rodar_um("t1")
    trabalho.refresh_from_db()
    assert trabalho.estado == E.ENCERRADO and "contato de quiz" in trabalho.motivo
    assert not openai.called


# ---------------------------------------------------------------- estorno


def test_reversao_cria_um_trabalho_de_estorno_e_a_reentrega_nao_duplica():
    envelope = _reversao(event_id="ev-rev")
    eventos.tratar("eventos.pagamento.reversao_confirmada", envelope)
    eventos.tratar("eventos.pagamento.reversao_confirmada", envelope)
    eventos.tratar("eventos.pagamento.reversao_confirmada", _reversao(event_id="ev-rev-2"))  # mesma reversão
    trabalho = TrabalhoComercial.objects.get(tipo=T.REGISTRAR_ESTORNO)
    assert trabalho.papel == "atendimento" and trabalho.pedido_id == "ped-9"
    assert trabalho.oportunidade_id == "opp-1" and trabalho.entrada["motivo"] == "estorno"
    # Não cria venda nem acompanhamento: o evento de aprovação não existe.
    assert not EventoComercial.objects.filter(nome="pagamento.aprovado").exists()
    assert not TrabalhoComercial.objects.exclude(tipo=T.REGISTRAR_ESTORNO).exists()


@respx.mock
def test_reversao_anota_na_oportunidade_avisa_a_equipe_e_nao_manda_mensagem():
    _guardar_chave()
    trabalho = eventos.tratar("eventos.pagamento.reversao_confirmada", _reversao(motivo="contestacao"))
    respx.get(f"{LEADS}/crm/opp-1").respond(200, json={
        "id": "opp-1", "lead_id": "lead-1", "contato": {"id": "lead-1", "nome": "Ana Souza", "email": EMAIL},
        "registro_de_teste": False})
    notas = respx.patch(f"{LEADS}/crm/opp-1/acompanhamento").respond(200, json={})
    _conversa()
    assumir = respx.post(f"{MENSAGERIA}/conversas/conv-1/assumir").respond(200, json={})
    envio = respx.post(f"{MENSAGERIA}/conversas/conv-1/mensagens")
    openai = respx.post(RESPOSTAS)
    _resto_404()
    coordenador.rodar_um("t1")
    trabalho.refresh_from_db()
    assert trabalho.estado == E.CONCLUIDO, trabalho.motivo
    assert not openai.called and not envio.called  # o agente não conversa sobre estorno
    assert trabalho.contato_id == "lead-1"
    assert assumir.called
    corpos = [_corpo(c) for c in notas.calls]
    assert any("Contestação" in c.get("nota", "") and "ped-9" in c["nota"] for c in corpos)
    assert any("equipe" in json.dumps(c) and c.get("aguardando_resposta") is False for c in corpos)
    assert trabalho.decisoes.get(call_id="estorno-nota").resultado == R.FEITO
    assert trabalho.decisoes.get(call_id="estorno-passar").resultado == R.FEITO
    aviso = AvisoDaEquipe.objects.get()
    assert "Contestação" in aviso.titulo and aviso.link == "/admin/crm/opp-1/"
    assert EMAIL not in aviso.texto


@respx.mock
def test_reversao_de_lead_de_teste_anota_mas_nao_avisa():
    _guardar_chave()
    trabalho = eventos.tratar("eventos.pagamento.reversao_confirmada", _reversao())
    respx.get(f"{LEADS}/crm/opp-1").respond(200, json={
        "id": "opp-1", "lead_id": "lead-1", "contato": {"id": "lead-1", "nome": "Ciclo", "email": TESTE},
        "registro_de_teste": True})
    notas = respx.patch(f"{LEADS}/crm/opp-1/acompanhamento").respond(200, json={})
    _conversa()
    respx.post(f"{MENSAGERIA}/conversas/conv-1/assumir").respond(200, json={})
    _resto_404()
    coordenador.rodar_um("t1")
    trabalho.refresh_from_db()
    assert trabalho.estado == E.CONCLUIDO and trabalho.teste is True
    assert notas.called
    assert not AvisoDaEquipe.objects.exists()


@respx.mock
def test_reversao_sem_oportunidade_conhecida_ainda_avisa_a_equipe():
    _guardar_chave()
    trabalho = eventos.tratar("eventos.pagamento.reversao_confirmada", _reversao(oportunidade_ref=""))
    respx.get(f"{LEADS}/crm").respond(200, json={"itens": []})
    _resto_404()
    coordenador.rodar_um("t1")
    trabalho.refresh_from_db()
    assert trabalho.estado == E.CONCLUIDO
    assert trabalho.decisoes.get(call_id="estorno-nota").resultado == R.INDISPONIVEL
    assert AvisoDaEquipe.objects.get().link == "/admin/crm/"

