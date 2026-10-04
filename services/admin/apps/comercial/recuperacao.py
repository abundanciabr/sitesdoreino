"""Recusa, Pix vencido e estorno chamam o agente certo.

Dois trabalhos, ambos do papel de atendimento (a versão no ar, sem mexer nela:
a instrução do trabalho vai no pedido):

* `recuperar_compra` — nasce de `pagamento.recusado` (cartão recusado) ou de
  `pix.expirado`, 10 minutos depois, para a pessoa ter tempo de reabrir o link
  sozinha. ANTES de qualquer mensagem o trabalho confere, sem o modelo, se o
  provedor já confirmou o pagamento (deste pedido ou de outro da mesma
  oportunidade), se uma pessoa assumiu a conversa, se o lead pediu para parar,
  se a jornada da mensageria já falou com ele nas últimas 24 horas e se há
  condição de compra liberada. Passando disso, o agente escolhe só entre as
  condições liberadas, prepara o link novo (mesma oportunidade e oferta) e manda
  UMA mensagem. Sem condição liberada, ou com o canal barrado, passa para uma
  pessoa e a equipe recebe um aviso;
* `registrar_estorno` — nasce de `pagamento.reversao_confirmada`. Não chama o
  modelo, não cria venda e não reabre a oferta: anota na oportunidade e avisa a
  equipe. O agente não conversa com o lead sobre estorno.

Contato de teste: o trabalho é de teste, fica fora dos totais e não vira aviso.
"""

from __future__ import annotations

import json
import logging
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from . import coordenador, ferramentas, servicos
from .models import DecisaoComercial, TrabalhoComercial

log = logging.getLogger(__name__)

E = TrabalhoComercial.Estado
T = TrabalhoComercial.Tipo
R = DecisaoComercial.Resultado

JANELA_DA_JORNADA = timedelta(hours=24)
# Quem já falou com o lead nas últimas 24 horas, sem ser ele: a jornada da
# mensageria (`sistema`) ou uma pessoa da equipe.
AUTORES_QUE_JA_FALARAM = ("sistema", "pessoa")

FALHAS = {
    "pagamento.recusado": "o cartão foi recusado",
    "pix.expirado": "o Pix venceu sem pagamento",
}


def executar(trabalho: TrabalhoComercial) -> None:
    if trabalho.tipo == T.REGISTRAR_ESTORNO:
        _registrar_estorno(trabalho)
    else:
        _recuperar(trabalho)


# ---------------------------------------------------------------- recuperar a compra


def _pago_na_oportunidade(trabalho: TrabalhoComercial) -> bool:
    """O checkout (que só marca pago pelo aviso do provedor) diz que algum pedido
    desta oportunidade foi pago e não reembolsado."""
    if not trabalho.oportunidade_id:
        return False
    lista = servicos.pedir("pedidos_da_oportunidade", params={"oportunidade_ref": trabalho.oportunidade_id},
                           site_id=trabalho.site_id, host=servicos.host_do_trabalho(trabalho))
    if not lista.ok:
        return False
    itens = [p for p in lista.dados.get("pedidos") or [] if isinstance(p, dict)]
    itens += [p for p in lista.dados.get("links") or [] if isinstance(p, dict)]
    return any(p.get("confirmado") and not p.get("reembolsado") for p in itens)


def _ja_pago(trabalho: TrabalhoComercial) -> bool:
    return bool(ferramentas.pagamento_aprovado(trabalho) or coordenador._pago_no_checkout(trabalho)
                or _pago_na_oportunidade(trabalho))


def _completar_pela_oportunidade(trabalho: TrabalhoComercial) -> None:
    """O aviso do pagamento traz a oportunidade e a oferta quando o checkout as
    pôs no pedido; o que faltar vem do CRM. O contato e a marca de teste também."""
    from . import eventos

    entrada = dict(trabalho.entrada or {})
    if trabalho.oportunidade_id and (not entrada.get("oferta_ref") or not trabalho.contato_id):
        resposta = servicos.pedir("oportunidade", trabalho.oportunidade_id)
        if resposta.ok:
            dados = resposta.dados or {}
            contato = dados.get("contato") if isinstance(dados.get("contato"), dict) else {}
            lead_id = str(dados.get("lead_id") or contato.get("id") or "")[:80]
            if lead_id and trabalho.contato_id and lead_id != str(trabalho.contato_id):
                # A oportunidade não é deste lead: não se usa (nada de um lead entra no trabalho de outro).
                log.warning("comercial: a oportunidade %s não é do contato do trabalho %s",
                            trabalho.oportunidade_id, trabalho.pk)
                trabalho.oportunidade_id = ""
            else:
                if lead_id and not trabalho.contato_id:
                    trabalho.contato_id = lead_id
                oferta = coordenador._oferta_da_oportunidade(dados)
                if oferta and not entrada.get("oferta_ref"):
                    entrada["oferta_ref"] = oferta
                if dados.get("registro_de_teste") or eventos.de_teste(
                        {"nome": str(contato.get("nome") or ""), "email": str(contato.get("email") or "").lower()},
                        {}):
                    trabalho.teste = True
    if not entrada.get("oferta_ref") and trabalho.contato_id:
        # A recuperação nasce sem oferta: a oferta é a que o CRM liga a outra oportunidade aberta do lead.
        resposta = servicos.pedir("oportunidades", params={
            "lead_id": trabalho.contato_id, "situacao": "aberta", "testes": "mostrar"})
        if resposta.ok:
            for item in resposta.dados.get("itens") or []:
                oferta = coordenador._oferta_da_oportunidade(item) if isinstance(item, dict) else ""
                if oferta:
                    entrada["oferta_ref"] = oferta
                    break
    trabalho.entrada = entrada
    coordenador.guardar(trabalho)


def _conversas_do_lead(trabalho: TrabalhoComercial) -> list[dict]:
    resposta = servicos.pedir("conversas", params={"site_id": trabalho.site_id, "lead_id": trabalho.contato_id},
                              site_id=trabalho.site_id)
    if not resposta.ok:
        return []
    return [c for c in resposta.dados.get("itens") or [] if isinstance(c, dict)
            and str(c.get("lead_id") or "") == str(trabalho.contato_id)
            and str(c.get("site_id") or trabalho.site_id) == str(trabalho.site_id)]


def _ja_recuperou(trabalho: TrabalhoComercial) -> bool:
    """Outra recuperação já mandou a mensagem a este lead nas últimas 24 horas."""
    quem = Q(chave_da_conversa=trabalho.chave_da_conversa) if trabalho.chave_da_conversa else Q(pk=None)
    if trabalho.contato_id:
        quem |= Q(contato_id=trabalho.contato_id, site_id=trabalho.site_id)
    if trabalho.oportunidade_id:
        quem |= Q(oportunidade_id=trabalho.oportunidade_id)
    return TrabalhoComercial.objects.filter(
        quem, tipo=T.RECUPERAR_COMPRA, criado_em__gte=timezone.now() - JANELA_DA_JORNADA,
        decisoes__ferramenta="enviar_mensagem", decisoes__resultado=R.FEITO,
    ).exclude(pk=trabalho.pk).exists()


def _motivo_para_nao_enviar(trabalho: TrabalhoComercial) -> str:
    """O que, olhando só os fatos (sem o modelo), manda NÃO falar com o lead agora."""
    if _ja_recuperou(trabalho):
        return "O agente já mandou a mensagem de recuperação a este lead nas últimas 24 horas."
    conversas = _conversas_do_lead(trabalho)
    if any(c.get("estado") == "pessoa" for c in conversas):
        return "Uma pessoa da equipe está atendendo este lead: o agente não envia a recuperação."
    if conversas and all(c.get("descadastrado") for c in conversas):
        return "O lead pediu para parar de receber mensagens: o agente não envia a recuperação."
    desde = timezone.now() - JANELA_DA_JORNADA
    for conversa in conversas[:3]:
        resposta = servicos.pedir("mensagens", str(conversa.get("id") or ""),
                                  params={"site_id": trabalho.site_id, "limite": 30}, site_id=trabalho.site_id)
        if not resposta.ok:
            continue
        for mensagem in resposta.dados.get("mensagens") or []:
            if not isinstance(mensagem, dict) or mensagem.get("direcao") != "saida":
                continue
            quando = parse_datetime(str(mensagem.get("ocorrida_em") or "")) if mensagem.get("ocorrida_em") else None
            if mensagem.get("autor") in AUTORES_QUE_JA_FALARAM and quando is not None and quando >= desde:
                return ("A jornada de recuperação da mensageria (ou uma pessoa) já falou com este lead nas "
                        "últimas 24 horas: o agente não repete.")
    return ""


def _sem_condicao_liberada(trabalho: TrabalhoComercial) -> str:
    """Sem oferta ligada ou sem condição liberada pelo mantenedor, não há o que oferecer."""
    oferta = (trabalho.entrada or {}).get("oferta_ref")
    if not oferta:
        return "Não há oferta ligada a esta oportunidade, então não há condição de compra para oferecer."
    resposta = servicos.pedir("condicoes", oferta, site_id=trabalho.site_id,
                              host=servicos.host_do_trabalho(trabalho))
    if not resposta.ok:
        return ""  # o checkout não respondeu: a ferramenta diz isso ao agente e ele decide
    condicoes = resposta.dados.get("condicoes")
    if isinstance(condicoes, list) and not condicoes:
        return "Nenhuma condição de compra está liberada para esta oferta."
    return ""


def _pedido_do_trabalho(trabalho: TrabalhoComercial) -> str:
    entrada = trabalho.entrada or {}
    falha = FALHAS.get(entrada.get("motivo_da_falha"), "o pagamento não foi concluído")
    return (
        f"Trabalho: recuperar a compra deste lead. No pedido {entrada.get('pedido_recusado') or '—'} {falha}.\n"
        + coordenador._sobre_o_lead(trabalho)
        + "\nFaça nesta ordem (ninguém precisa de mais de uma mensagem):\n"
        "1. consultar_pagamento: se o provedor já confirmou o pagamento deste pedido ou de outro da mesma "
        "oportunidade, não envie nada e decida sem_resposta.\n"
        "2. consultar_oportunidade e consultar_conversa: se uma pessoa da equipe assumiu a conversa, se o lead "
        "pediu para parar ou se já saiu mensagem de recuperação nas últimas 24 horas, não envie nada e decida "
        "sem_resposta. A jornada automática da mensageria pode ter mandado um lembrete: não repita o texto dela.\n"
        "3. consultar_condicoes_compra: escolha SÓ entre as condições liberadas, pelo id exato. Nenhum desconto, "
        "parcela, cupom ou prazo fora delas. Se o Pix venceu, prefira a condição Pix; se o cartão foi recusado, "
        "ofereça o Pix se estiver liberado, ou outra condição liberada. Se não houver condição liberada, use "
        "passar_para_responsavel.\n"
        "4. preparar_link_compra com a MESMA oferta e oportunidade (oferta_ref nulo) e a condição escolhida; "
        "explique o valor e o vencimento que voltarem.\n"
        "5. enviar_mensagem: UMA mensagem curta e acolhedora com o link novo, sem culpar a pessoa, sem prazo, "
        "desconto ou escassez inventados e sem citar código do provedor. Apresente-se como assistente da equipe.\n"
        "Se o envio voltar recusado (WhatsApp fora da janela, descadastro, horário, limite) e outro canal "
        "também não servir, não insista: passar_para_responsavel com o resumo.\n"
        "Termine com a decisão: respondeu (mensagem enviada), sem_resposta (não era para enviar) ou "
        "passou_para_pessoa."
    )


def _descricao(trabalho: TrabalhoComercial) -> str:
    entrada = trabalho.entrada or {}
    falha = FALHAS.get(entrada.get("motivo_da_falha"), "o pagamento não foi concluído")
    return f"No pedido {entrada.get('pedido_recusado') or trabalho.pedido_id or '—'} {falha}."


def _avisar_a_equipe(trabalho: TrabalhoComercial, *, titulo: str, texto: str, fato: str) -> None:
    """Abre o aviso do painel (um por fato). Registro de teste não avisa ninguém."""
    if trabalho.teste:
        return
    try:
        from apps.core import avisos_equipe

        avisos_equipe.avisar(
            avisos_equipe.Tipo.PESSOA_PEDIDA,
            site_id=trabalho.site_id,
            fato=fato,
            titulo=titulo,
            texto=texto,
            link=(avisos_equipe.link_da_oportunidade(trabalho.oportunidade_id)
                  if trabalho.oportunidade_id else "/admin/crm/"),
            enviar_agora=False,
        )
    except Exception:  # noqa: BLE001 - o aviso não derruba o trabalho
        log.exception("comercial: o aviso do trabalho %s não foi aberto", trabalho.pk)


def _passar_para_pessoa(trabalho: TrabalhoComercial, motivo: str) -> None:
    """Sem o modelo: a decisão é gravada com a versão da estratégia, a oportunidade (e a
    conversa, se houver) vão para a equipe e o painel recebe o aviso."""
    ctx = ferramentas.Contexto(trabalho=trabalho, papel=trabalho.papel, estrategia=coordenador._estrategia(trabalho))
    resumo = f"{_descricao(trabalho)} {motivo}"
    ferramentas.executar(ctx, "recuperacao-passar", "passar_para_responsavel",
                         json.dumps({"motivo": motivo, "resumo": resumo}))
    trabalho.resultado = {**(trabalho.resultado or {}),
                          "decisao": {"acao": "passou_para_pessoa", "resumo": resumo},
                          "mensagem_enviada": False, "passou_para_pessoa": True}
    _avisar_a_equipe(
        trabalho, titulo="Compra para recuperar: precisa de uma pessoa",
        texto=f"{resumo} O agente não mandou mensagem; vale um contato da equipe.",
        fato=f"recuperacao:{trabalho.site_id}:{(trabalho.entrada or {}).get('pedido_recusado') or trabalho.pedido_id}",
    )
    coordenador.terminar(trabalho, E.CONCLUIDO, resumo=f"Passou para uma pessoa da equipe: {motivo}")


def _encerrar(trabalho: TrabalhoComercial, motivo: str) -> None:
    coordenador.terminar(trabalho, E.ENCERRADO, motivo)


def _recuperar(trabalho: TrabalhoComercial) -> None:
    if _ja_pago(trabalho):
        _encerrar(trabalho, "O pagamento já foi aprovado pelo provedor: nada a recuperar, o modelo não foi chamado.")
        return
    coordenador._achar_a_ficha(trabalho)
    _completar_pela_oportunidade(trabalho)
    if not trabalho.contato_id:
        _encerrar(trabalho, "Quem comprou não é contato de quiz do CRM: o agente só recupera a compra de um lead.")
        return
    if _ja_pago(trabalho):
        _encerrar(trabalho, "O pagamento já foi aprovado pelo provedor: nada a recuperar, o modelo não foi chamado.")
        return
    if "itens" not in (trabalho.retomada or {}):  # depois do primeiro passo, estas conferências já foram feitas
        motivo = _motivo_para_nao_enviar(trabalho)
        if motivo:
            _encerrar(trabalho, motivo)
            return
        sem = _sem_condicao_liberada(trabalho)
        if sem:
            _passar_para_pessoa(trabalho, sem)
            return
    final = coordenador.conversar(trabalho, _pedido_do_trabalho(trabalho))
    feitas = trabalho.decisoes.filter(resultado=R.FEITO)
    enviada = feitas.filter(ferramenta="enviar_mensagem").exists()
    passou = feitas.filter(ferramenta="passar_para_responsavel").exists() or final.get("acao") == "passou_para_pessoa"
    trabalho.resultado = {**(trabalho.resultado or {}), "decisao": final, "mensagem_enviada": enviada,
                          "link_preparado": feitas.filter(ferramenta="preparar_link_compra").exists(),
                          "passou_para_pessoa": passou}
    if not enviada and not passou and final.get("acao") != "sem_resposta":
        _passar_para_pessoa(trabalho, "O canal não aceitou a mensagem ou o agente não conseguiu preparar a oferta.")
        return
    if passou and not enviada:
        _avisar_a_equipe(
            trabalho, titulo="Compra para recuperar: precisa de uma pessoa",
            texto=f"{_descricao(trabalho)} O agente passou o caso para a equipe.",
            fato=f"recuperacao:{trabalho.site_id}:{(trabalho.entrada or {}).get('pedido_recusado') or trabalho.pedido_id}",
        )
    resumo = ("Recuperação: mensagem com o link novo enviada." if enviada
              else "Passou para uma pessoa da equipe." if passou
              else f"Sem mensagem: {final.get('resumo') or final.get('acao') or '—'}.")
    coordenador.terminar(trabalho, E.CONCLUIDO, resumo=resumo)


# ---------------------------------------------------------------- estorno


def _registrar_estorno(trabalho: TrabalhoComercial) -> None:
    """Nota e próximo passo na oportunidade, conversa e oportunidade com a equipe e aviso. Sem o
    modelo: o agente não conversa sobre estorno."""
    from . import eventos

    entrada = dict(trabalho.entrada or {})
    pedido = trabalho.pedido_id
    if not trabalho.oportunidade_id and pedido:
        # A recuperação que a leads abre por pedido leva 'recuperar:<pedido>' na fonte.
        achadas = servicos.pedir("oportunidades", params={"q": pedido, "testes": "mostrar"})
        if achadas.ok:
            for item in achadas.dados.get("itens") or []:
                if isinstance(item, dict) and (item.get("fonte") or {}).get("referencia_id") == f"recuperar:{pedido}":
                    trabalho.oportunidade_id = str(item.get("id") or "")[:80]
                    break
    if trabalho.oportunidade_id:
        resposta = servicos.pedir("oportunidade", trabalho.oportunidade_id)
        if resposta.ok:
            dados = resposta.dados or {}
            contato = dados.get("contato") if isinstance(dados.get("contato"), dict) else {}
            if not trabalho.contato_id:
                trabalho.contato_id = str(dados.get("lead_id") or contato.get("id") or "")[:80]
            if dados.get("registro_de_teste") or eventos.de_teste(
                    {"nome": str(contato.get("nome") or ""), "email": str(contato.get("email") or "").lower()}, {}):
                trabalho.teste = True
    coordenador.guardar(trabalho)

    contestacao = entrada.get("motivo") == "contestacao"
    palavra = "Contestação (chargeback)" if contestacao else "Estorno"
    resumo = (f"{palavra} confirmado pelo provedor no pedido {pedido}. O CRM ajusta o resultado líquido; a oferta "
              "não foi reaberta e o agente não vai conversar com o lead sobre isso.")
    ctx = ferramentas.Contexto(trabalho=trabalho, papel=trabalho.papel, estrategia=coordenador._estrategia(trabalho))
    ferramentas.executar(ctx, "estorno-nota", "registrar_nota_proximo_passo", json.dumps({
        "nota": resumo,
        "proximo_passo": "A equipe confere o caso e decide se fala com o cliente.",
        "prazo": (timezone.localdate() + timedelta(days=1)).isoformat(),
        "objecao_principal": None,
        "aguardando_resposta": False,
    }))
    ferramentas.executar(ctx, "estorno-passar", "passar_para_responsavel", json.dumps({
        "motivo": f"{palavra} confirmado pelo provedor", "resumo": resumo}))
    _avisar_a_equipe(
        trabalho, titulo=f"{palavra} confirmado: veja o caso",
        texto=f"{resumo} Confira a oportunidade e decida o contato com o cliente.",
        fato=f"estorno:{trabalho.site_id}:{pedido}",
    )
    trabalho.resultado = {**(trabalho.resultado or {}), "decisao": {"acao": "passou_para_pessoa", "resumo": resumo},
                          "mensagem_enviada": False, "motivo": entrada.get("motivo") or "estorno"}
    coordenador.terminar(trabalho, E.CONCLUIDO, resumo=f"{palavra} registrado; a equipe foi avisada.")
