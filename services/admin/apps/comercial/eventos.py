"""Os gatilhos da equipe comercial: eventos da plataforma viram trabalhos.

* `quiz.completado` e `quiz.captura_parcial` → `analisar_lead` (que, se o
  analista indicar, põe `abordar` na fila; na captura parcial a abordagem
  espera 30 minutos, e o quiz concluído nesse meio cancela o que era parcial);
* `mensagem.recebida` → `atender_mensagem`; se for áudio sem texto, o atendimento
  espera a transcrição por até 3 minutos e `mensagem.transcrita` o libera já com
  o texto do que o lead falou (sem a transcrição, segue como antes);
* `pagamento.aprovado` → fecha os acompanhamentos daquela oportunidade ou
  daquele pedido, sem chamar o modelo;
* `pagamento.recusado` e `pix.expirado` → `recuperar_compra` (o atendimento
  vê se a pessoa já pagou e, se não, manda UMA mensagem com as condições
  liberadas); espera 10 minutos para a pessoa reabrir o link sozinha;
* `pagamento.reversao_confirmada` → `registrar_estorno` (nota na oportunidade
  e aviso para a equipe; o agente não conversa sobre estorno).

Reentrega do mesmo `event_id` não cria nada de novo (`EventoComercial` e a
chave de idempotência do trabalho). Nada aqui chama outra célula: o trabalho
acha a ficha quando roda.
"""

from __future__ import annotations

import logging
import re
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from . import comparacao, coordenador, interruptor, otimizador, servicos
from .models import EventoComercial, TrabalhoComercial

log = logging.getLogger(__name__)

ESPERA_DA_CAPTURA_PARCIAL = timedelta(minutes=30)
# Dá tempo de a pessoa reabrir o link e pagar sozinha antes de o agente falar.
ESPERA_DA_RECUPERACAO = timedelta(minutes=10)
# Quanto o atendimento de um áudio espera a transcrição antes de seguir sem ela.
ESPERA_DA_TRANSCRICAO = timedelta(minutes=3)

E = TrabalhoComercial.Estado
T = TrabalhoComercial.Tipo

_TESTE = re.compile(r"\b(teste|test|sandbox)\b", re.I)


def _texto(valor, limite: int = 200) -> str:
    return str(valor or "").strip()[:limite]


def _site(data: dict) -> str:
    return _texto(data.get("site_id") or data.get("site") or data.get("platform_site_id"), 80)


def _contato(data: dict) -> dict:
    bruto = data.get("lead") or data.get("contato") or data.get("customer") or {}
    if not isinstance(bruto, dict):
        bruto = {}
    return {
        "nome": _texto(bruto.get("nome") or bruto.get("name")),
        "email": _texto(bruto.get("email")).lower(),
        "telefone": _texto(bruto.get("telefone") or bruto.get("phone"), 40),
    }


def de_teste(contato: dict, data: dict) -> bool:
    email = contato.get("email") or ""
    return bool(
        email.endswith(("@example.com", "@exemplo.test"))
        or _TESTE.search(contato.get("nome") or "")
        # O quiz marca a visita de teste em `utm` (`source`, `campaign`, com ou sem
        # o prefixo `utm_`) e em `context` (`src`, `cpg`).
        or otimizador.marcado_como_teste(data.get("utm"), data.get("context"))
        or data.get("sandbox") is True
        or data.get("teste") is True
    )


# O que do `context` do quiz fica no trabalho: só as marcas de origem (a campanha
# do relatório e a marca de teste), nunca a página ou o endereço do visitante.
_CAMPOS_DO_CONTEXTO = ("src", "med", "cpg", "seg", "fmt", "ctv")


def _origem_do_contexto(data: dict) -> dict:
    contexto = data.get("context") if isinstance(data.get("context"), dict) else {}
    return {campo: _texto(contexto.get(campo), 120) for campo in _CAMPOS_DO_CONTEXTO if contexto.get(campo)}


def _host(data: dict) -> str:
    contexto = data.get("context") if isinstance(data.get("context"), dict) else {}
    host = contexto.get("host") or data.get("host") or ""
    if not host:
        for chave in ("url", "pagina", "page_url", "referrer"):
            achado = re.match(r"https?://([^/:?#]+)", str(contexto.get(chave) or ""))
            if achado:
                host = achado.group(1)
                break
    return _texto(host, 255).lower()


def _registrar(envelope: dict, nome: str, **campos) -> bool:
    """Grava o evento. Falso quando ele já tinha sido tratado (reentrega)."""
    event_id = _texto(envelope.get("event_id"), 120)
    if not event_id:
        return True
    try:
        with transaction.atomic():
            EventoComercial.objects.create(event_id=event_id, nome=nome, **campos)
    except IntegrityError:
        return False
    return True


def _chave_do_lead(site_id: str, contato: dict) -> str:
    quem = contato.get("email") or re.sub(r"\D", "", contato.get("telefone") or "")
    return f"lead:{site_id}:{quem}" if quem else ""


def _do_quiz(nome: str, envelope: dict, *, parcial: bool) -> TrabalhoComercial | None:
    data = envelope.get("data") or {}
    site_id = _site(data)
    contato = _contato(data)
    chave_do_lead = _chave_do_lead(site_id, contato)
    if not site_id or not chave_do_lead:
        return None  # sem endereço não há com quem falar
    if not _registrar(envelope, nome, site_id=site_id):
        return None
    if not coordenador.ligado():
        return None
    quiz = _texto(data.get("quiz_slug") or data.get("quiz"), 120)
    if not interruptor.quiz_no_escopo(quiz):
        return None  # a equipe atua só nos quizzes escolhidos na tela
    sessao = _texto(data.get("sessao") or data.get("session_id"), 120)
    teste = de_teste(contato, data)
    # O grupo de comparação fica sem o agente: o lead não vira trabalho nenhum e segue só
    # com o que já existia (jornadas fixas e caixa de conversas). Com o percentual em 0,
    # que é o padrão, todo lead cai em `agente` e nada muda.
    grupo = comparacao.decidir(
        site_id, comparacao.quem_e(contato.get("email"), contato.get("telefone")), sessao=sessao, teste=teste)
    if grupo == comparacao.GRUPO_COMPARACAO:
        return None
    entrada = {
        "contato": contato,
        "quiz": quiz,
        "versao": _texto(data.get("version_key") or data.get("versao"), 80),
        "resultado": _texto(data.get("result_key") or data.get("resultado"), 120),
        "respostas": data.get("respostas") if isinstance(data.get("respostas"), list) else [],
        "utm": data.get("utm") if isinstance(data.get("utm"), dict) else {},
        "context": _origem_do_contexto(data),
        "campanha": data.get("campanha") or data.get("origem"),
        "submissao_id": _texto(data.get("submissao_id"), 80),
        "captura_id": _texto(data.get("captura_id") or data.get("captura_parcial_id"), 80),
        "sessao": sessao,
        "host": _host(data) or servicos.host_do_site(site_id),
        "parcial": parcial,
        "grupo": grupo,
    }
    comum = {
        "origem": nome,
        "evento_id": _texto(envelope.get("event_id"), 120),
        "site_id": site_id,
        "chave_da_conversa": chave_do_lead,
        "teste": teste,
    }
    if parcial:
        if TrabalhoComercial.objects.filter(
            chave_da_conversa=chave_do_lead, origem="quiz.completado", entrada__quiz=quiz
        ).exists():
            return None  # o quiz já foi concluído: a captura parcial chegou atrasada
        entrada["abordar_apos"] = (timezone.now() + ESPERA_DA_CAPTURA_PARCIAL).isoformat()
        chave = f"analisar_lead:parcial:{site_id}:{quiz}:{sessao or chave_do_lead}"
        trabalho, criado = coordenador.criar(T.ANALISAR_LEAD, chave, entrada=entrada, **comum)
        if not criado and trabalho.estado == E.NA_FILA:
            # A mesma sessão respondeu mais: o trabalho na fila lê o mais novo.
            TrabalhoComercial.objects.filter(pk=trabalho.pk, estado=E.NA_FILA).update(
                entrada={**(trabalho.entrada or {}), "respostas": entrada["respostas"], "contato": contato},
                atualizado_em=timezone.now(),
            )
        return trabalho
    # Concluiu: o que era da captura parcial deste quiz e ainda não rodou sai da fila.
    TrabalhoComercial.objects.filter(
        chave_da_conversa=chave_do_lead,
        entrada__parcial=True,
        entrada__quiz=quiz,
        estado__in=[E.NA_FILA, E.AGUARDANDO_DEPENDENCIA, E.AGUARDANDO_AUTORIZACAO],
    ).update(estado=E.CANCELADO, motivo="O lead concluiu o quiz; vale a análise do quiz completo.",
             terminado_em=timezone.now(), atualizado_em=timezone.now())
    chave = f"analisar_lead:{site_id}:{data.get('submissao_id') or envelope.get('event_id')}"
    trabalho, _ = coordenador.criar(T.ANALISAR_LEAD, chave, entrada=entrada, **comum)
    return trabalho


def ao_quiz_completado(envelope: dict):
    return _do_quiz("quiz.completado", envelope, parcial=False)


def ao_quiz_captura_parcial(envelope: dict):
    return _do_quiz("quiz.captura_parcial", envelope, parcial=True)


def ao_mensagem_recebida(envelope: dict):
    data = envelope.get("data") or {}
    site_id = _site(data)
    conversa_id = _texto(data.get("conversa_id"), 120)
    if not site_id or not conversa_id:
        return None
    if data.get("direcao") in ("saida", "enviada") or data.get("autor") in ("agente", "pessoa"):
        return None  # o que a equipe mandou não pede resposta
    if not _registrar(envelope, "mensagem.recebida", site_id=site_id):
        return None
    if data.get("lead_ligacao") in ("desconhecida", "ambigua") and data.get("canal") == "whatsapp":
        # A mensageria orienta quem não é do quiz; aqui só se garante o endereço do site no texto.
        servicos.garantir_endereco_do_quiz_na_orientacao(site_id)
    if not coordenador.ligado():
        return None
    lead = data.get("lead")
    contato_id = _texto(lead.get("id") if isinstance(lead, dict) else lead, 80)
    if data.get("lead_ligacao") != "ligada" or not contato_id:
        return None  # o robô só atende contato do quiz; o resto fica na caixa para a equipe
    contato = _contato(data) if isinstance(lead, dict) else {"nome": "", "email": "", "telefone": ""}
    if data.get("estado_conversa") == "pessoa":
        return None  # uma pessoa da equipe está atendendo
    if comparacao.grupo_do_contato_id(site_id, contato_id) == comparacao.GRUPO_COMPARACAO:
        return None  # grupo de comparação: a mensagem fica na caixa para a equipe responder
    escopo = interruptor.escopo()
    if escopo and not TrabalhoComercial.objects.filter(contato_id=contato_id, entrada__quiz__in=escopo).exists():
        return None  # a equipe atua só em alguns quizzes e este contato não veio deles
    midia = data.get("midia") if isinstance(data.get("midia"), dict) else None
    texto = str(data.get("texto") or "")[:4000]
    # Áudio sem texto: espera a transcrição (`mensagem.transcrita`), que libera o trabalho.
    aguarda_transcricao = bool(midia and midia.get("tipo") == "audio" and not texto.strip())
    trabalho, _ = coordenador.criar(
        T.ATENDER_MENSAGEM,
        f"atender:{envelope.get('event_id') or data.get('mensagem_id')}",
        origem="mensagem.recebida",
        evento_id=_texto(envelope.get("event_id"), 120),
        site_id=site_id,
        contato_id=contato_id,
        conversa_id=conversa_id,
        chave_da_conversa=f"conversa:{conversa_id}",
        teste=de_teste(contato, data),
        nao_antes_de=timezone.now() + ESPERA_DA_TRANSCRICAO if aguarda_transcricao else None,
        entrada={
            "canal": _texto(data.get("canal"), 20),
            "aguarda_transcricao": aguarda_transcricao,
            # O domínio do site: o checkout e o quiz acham o site por ele.
            "host": _host(data) or servicos.host_do_site(site_id),
            "texto": texto,
            "assunto": _texto(data.get("assunto"), 300),
            "midia": midia,
            "descadastro": bool(data.get("descadastro")),
            "contato": contato,
            "mensagem_id": _texto(data.get("mensagem_id"), 80),
            "mensagens": [{"texto": texto, "midia": midia,
                           "descadastro": bool(data.get("descadastro")),
                           "evento_id": _texto(envelope.get("event_id"), 120),
                           "mensagem_id": _texto(data.get("mensagem_id"), 80)}],
        },
    )
    return trabalho


def ao_mensagem_transcrita(envelope: dict):
    """O áudio do lead virou texto: o atendimento que esperava por ele ganha o
    texto e sai da espera. Se o atendimento já começou (a espera acabou) ou já
    terminou, não há o que fazer: ele seguiu sem a transcrição."""
    data = envelope.get("data") or {}
    site_id = _site(data)
    conversa_id = _texto(data.get("conversa_id"), 120)
    mensagem_id = _texto(data.get("mensagem_id"), 80)
    if not site_id or not conversa_id or not mensagem_id:
        return None
    if not _registrar(envelope, "mensagem.transcrita", site_id=site_id):
        return None
    texto = str(data.get("transcricao") or "").strip()[:4000]
    esclarecer = _texto(data.get("pergunta_de_esclarecimento"), 300) if data.get("pedir_esclarecimento") else ""
    trabalho = (
        TrabalhoComercial.objects.select_for_update()
        .filter(tipo=T.ATENDER_MENSAGEM, site_id=site_id, conversa_id=conversa_id,
                entrada__mensagem_id=mensagem_id,
                estado__in=[E.NA_FILA, E.AGUARDANDO_DEPENDENCIA, E.AGUARDANDO_AUTORIZACAO])
        .first()
    )
    if trabalho is None:
        return None
    entrada = dict(trabalho.entrada or {})
    if texto:
        entrada["texto"] = texto
    entrada["aguarda_transcricao"] = False
    mensagens = []
    for mensagem in entrada.get("mensagens") or []:
        if texto and mensagem.get("mensagem_id") == mensagem_id and not str(mensagem.get("texto") or "").strip():
            mensagem = {**mensagem, "texto": texto, **({"esclarecer": esclarecer} if esclarecer else {})}
        mensagens.append(mensagem)
    if mensagens:
        entrada["mensagens"] = mensagens
    campos = {"entrada": entrada, "atualizado_em": timezone.now()}
    if trabalho.estado == E.NA_FILA:
        campos["nao_antes_de"] = None  # pode atender agora
    TrabalhoComercial.objects.filter(pk=trabalho.pk).update(**campos)
    transaction.on_commit(coordenador._acordar_o_executor)
    return trabalho


def ao_pagamento_aprovado(envelope: dict):
    data = envelope.get("data") or {}
    site_id = _site(data)
    pedido = _texto(data.get("order_id") or data.get("pedido_id"), 120)
    oportunidade = _texto(data.get("oportunidade_ref"), 80)
    event_id = _texto(envelope.get("event_id"), 120) or f"pagamento:{pedido}"
    try:
        with transaction.atomic():
            evento = EventoComercial.objects.create(
                event_id=event_id, nome="pagamento.aprovado", site_id=site_id,
                oportunidade_ref=oportunidade, pedido_id=pedido,
            )
    except IntegrityError:
        return 0
    if not oportunidade and pedido:
        # O link preparado pelo agente guardou o pedido no trabalho.
        ligado = TrabalhoComercial.objects.filter(pedido_id=pedido).exclude(oportunidade_id="").first()
        if ligado is not None:
            evento.oportunidade_ref = ligado.oportunidade_id
            evento.save(update_fields=["oportunidade_ref"])
    email = _contato(data).get("email") or ""
    return coordenador._fechar_por_pagamento(evento, email=email, site_id=site_id)


def _blocos(data: dict):
    yield data
    for chave in ("metadata", "contexto", "context"):
        bloco = data.get(chave)
        if isinstance(bloco, dict):
            yield bloco


def _referencia(data: dict, campo: str, limite: int = 120) -> str:
    """`oportunidade_ref` e `oferta_ref` que o checkout ecoa no aviso do pagamento
    (no topo ou em `metadata`/`contexto`)."""
    for bloco in _blocos(data):
        valor = _texto(bloco.get(campo), limite)
        if valor:
            return valor
    return ""


def _sandbox(data: dict) -> bool:
    return any(
        bloco.get("sandbox") is True or _texto(bloco.get("ambiente")).lower() == "sandbox"
        for bloco in _blocos(data)
    )


def _pedido_do_evento(data: dict) -> str:
    return _texto(data.get("order_id") or data.get("pedido_id"), 120)


def _oportunidade_do_pedido(pedido: str, site_id: str) -> str:
    """O link preparado pelo agente guardou o pedido no trabalho."""
    ligado = TrabalhoComercial.objects.filter(pedido_id=pedido, site_id=site_id).exclude(
        oportunidade_id="").first()
    return ligado.oportunidade_id if ligado is not None else ""


def _da_falha_de_pagamento(nome: str, envelope: dict):
    """Cartão recusado ou Pix vencido: abre `recuperar_compra`. Uma por (site,
    pedido, tentativa); a reentrega do mesmo evento não cria outra."""
    data = envelope.get("data") or {}
    site_id = _site(data)
    pedido = _pedido_do_evento(data)
    if not site_id or not pedido:
        return None
    oportunidade = _referencia(data, "oportunidade_ref", 80)
    if not _registrar(envelope, nome, site_id=site_id, oportunidade_ref=oportunidade, pedido_id=pedido):
        return None
    if not coordenador.ligado():
        return None
    contato = _contato(data)
    tentativa = _texto(data.get("payment_id") or envelope.get("event_id"), 120)
    quem = _chave_do_lead(site_id, contato)
    trabalho, _ = coordenador.criar(
        T.RECUPERAR_COMPRA,
        f"recuperar:{site_id}:{pedido}:{tentativa}",
        origem=nome,
        evento_id=_texto(envelope.get("event_id"), 120),
        site_id=site_id,
        oportunidade_id=oportunidade or _oportunidade_do_pedido(pedido, site_id),
        pedido_id=pedido,
        chave_da_conversa=quem or f"pedido:{site_id}:{pedido}",
        teste=de_teste(contato, data) or _sandbox(data),
        nao_antes_de=timezone.now() + ESPERA_DA_RECUPERACAO,
        entrada={
            "contato": contato,
            "motivo_da_falha": nome,  # pagamento.recusado (cartão) ou pix.expirado
            "metodo": _texto(data.get("method"), 20),
            "codigo_do_provedor": _texto(data.get("reason_code"), 120),
            "pedido_recusado": pedido,
            "tentativa": tentativa,
            "oferta_ref": _referencia(data, "oferta_ref"),
            "host": _host(data) or servicos.host_do_site(site_id),
        },
    )
    return trabalho


def ao_pagamento_recusado(envelope: dict):
    return _da_falha_de_pagamento("pagamento.recusado", envelope)


def ao_pix_expirado(envelope: dict):
    return _da_falha_de_pagamento("pix.expirado", envelope)


def ao_reversao_confirmada(envelope: dict):
    """Estorno ou contestação confirmada pelo provedor: não cria venda, não
    reabre oferta e o agente não conversa sobre isso. Abre `registrar_estorno`,
    que anota na oportunidade e avisa a equipe."""
    data = envelope.get("data") or {}
    site_id = _site(data)
    pedido = _pedido_do_evento(data)
    if not site_id or not pedido:
        return None
    oportunidade = _referencia(data, "oportunidade_ref", 80)
    if not _registrar(envelope, "pagamento.reversao_confirmada", site_id=site_id,
                      oportunidade_ref=oportunidade, pedido_id=pedido):
        return None
    if not coordenador.ligado():
        return None
    referencia = _texto(data.get("provider_reference_id"), 120) or _texto(envelope.get("event_id"), 120)
    trabalho, _ = coordenador.criar(
        T.REGISTRAR_ESTORNO,
        f"estorno:{site_id}:{pedido}:{referencia}",
        origem="pagamento.reversao_confirmada",
        evento_id=_texto(envelope.get("event_id"), 120),
        site_id=site_id,
        oportunidade_id=oportunidade or _oportunidade_do_pedido(pedido, site_id),
        pedido_id=pedido,
        chave_da_conversa=f"pedido:{site_id}:{pedido}",
        teste=_sandbox(data),
        entrada={
            "motivo": "contestacao" if _texto(data.get("motivo")) == "contestacao" else "estorno",
            "provedor": _texto(data.get("provider"), 40),
            "oferta_ref": _referencia(data, "oferta_ref"),
            "host": _host(data) or servicos.host_do_site(site_id),
        },
    )
    return trabalho


STREAMS = {
    "eventos.quiz.completado": ao_quiz_completado,
    "eventos.quiz.captura_parcial": ao_quiz_captura_parcial,
    "eventos.mensagem.recebida": ao_mensagem_recebida,
    "eventos.mensagem.transcrita": ao_mensagem_transcrita,
    "eventos.pagamento.aprovado": ao_pagamento_aprovado,
    "eventos.pagamento.recusado": ao_pagamento_recusado,
    "eventos.pix.expirado": ao_pix_expirado,
    "eventos.pagamento.reversao_confirmada": ao_reversao_confirmada,
}


def tratar(stream: str, envelope: dict):
    """Um evento, numa transação: se falhar, nada fica pela metade e a
    reentrega trata de novo."""
    handler = STREAMS[stream]
    with transaction.atomic():
        return handler(envelope)
