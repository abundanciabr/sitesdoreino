"""API interna das conversas, para o coordenador dos agentes e o painel.

Toda consulta leva `site_id`: conversa de outro site é 404. Leitura aceita os
dois graus de token; enviar, abrir, assumir, devolver e encerrar exigem o grau
de publicação, como as demais escritas desta porta.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from django.db.models import F, Q
from django.utils import timezone
from ninja import Router, Schema
from ninja.errors import HttpError

from apps.core.auth import tokens_de_publicacao

from . import descadastro as descadastros
from . import enderecos, envio
from .models import CANAIS, ESTADOS, LIGACOES, Conversa, Descadastro, MensagemDaConversa, OrientacaoDoSite

router = Router()
POR_PAGINA_MAXIMO = 100


def _escrita(request):
    if request.auth not in tokens_de_publicacao():
        raise HttpError(403, "acesso de escrita negado")


def _site(site_id: str) -> str:
    site_id = (site_id or "").strip()
    if not site_id or len(site_id) > 100:
        raise HttpError(422, "site_id obrigatorio")
    return site_id


def _conversa(conversa_id: str, site_id: str) -> Conversa:
    try:
        chave = uuid.UUID(str(conversa_id))
    except ValueError:
        raise HttpError(404, "conversa inexistente")
    conversa = Conversa.objects.filter(pk=chave, site_id=_site(site_id)).first()
    if conversa is None:
        raise HttpError(404, "conversa inexistente")
    return conversa


def _data(valor: datetime | None) -> str | None:
    return valor.isoformat() if valor else None


def _descadastrados(conversas) -> set[tuple[str, str, str]]:
    """(site, canal, endereço) de quem pediu para parar, buscado de uma vez para o lote."""
    chaves = {(c.site_id, c.canal, c.endereco) for c in conversas}
    if not chaves:
        return set()
    achados = Descadastro.objects.filter(
        site_id__in={c[0] for c in chaves}, canal__in={c[1] for c in chaves},
        endereco__in={c[2] for c in chaves},
    ).values_list("site_id", "canal", "endereco")
    return set(achados) & chaves


def conversa_json(conversa: Conversa, descadastrados: set | None = None) -> dict:
    """`descadastrados` (de `_descadastrados`) evita uma consulta por conversa nas listas."""
    agora = timezone.now()
    if descadastrados is None:
        parou = descadastros.ativo(conversa) is not None
    else:
        parou = (conversa.site_id, conversa.canal, conversa.endereco) in descadastrados
    return {
        "id": str(conversa.id),
        "site_id": conversa.site_id,
        "canal": conversa.canal,
        "endereco_mascarado": enderecos.mascarar(conversa.canal, conversa.endereco),
        # Ambígua ou desconhecida nunca carrega dado de lead nenhum.
        "lead_id": conversa.lead_id if conversa.ligacao == "ligada" else None,
        "ligacao": conversa.ligacao,
        "ambigua": conversa.ambigua,
        "estado": conversa.estado,
        "assumida_por": conversa.assumida_por or None,
        "assumida_em": _data(conversa.assumida_em),
        "janela_aberta_ate": _data(conversa.janela_aberta_ate),
        "janela_aberta": envio.janela_aberta(conversa, agora),
        "descadastrado": parou,
        # Por que não há oportunidade ligada (sem_origem_quiz, telefone_ambiguo, equipe_confirma) e
        # a orientação fixa que já saiu. Nunca carrega dado de lead.
        "etiqueta": conversa.etiqueta or None,
        "orientacao": ({"tipo": conversa.orientacao_tipo, "enviada_em": _data(conversa.orientacao_enviada_em)}
                       if conversa.orientacao_enviada_em else None),
        "ultima_entrada_em": _data(conversa.ultima_entrada_em),
        "ultima_mensagem_em": _data(conversa.ultima_mensagem_em),
        "criada_em": _data(conversa.criada_em),
    }


def mensagem_json(mensagem: MensagemDaConversa) -> dict:
    return {
        "id": str(mensagem.id),
        "conversa_id": str(mensagem.conversa_id),
        "direcao": mensagem.direcao,
        "autor": mensagem.autor,
        "autor_id": mensagem.autor_id or None,
        "texto": mensagem.texto,
        "assunto": mensagem.assunto or None,
        "midia": ({"tipo": mensagem.midia_tipo, "referencia": mensagem.midia_referencia,
                   "mime": mensagem.midia_mime} if mensagem.midia_tipo else None),
        "transcricao": mensagem.transcricao or None,
        "estado_envio": mensagem.estado_envio,
        "erro": mensagem.erro or None,
        "id_externo": mensagem.id_externo or None,
        "em_resposta_a": mensagem.em_resposta_a or None,
        "chave_idempotencia": mensagem.chave_idempotencia or None,
        "descadastro": mensagem.descadastro,
        "ocorrida_em": _data(mensagem.ocorrida_em),
    }


@router.get("/conversas")
def listar_conversas(request, site_id: str, lead_id: str = "", estado: str = "", canal: str = "",
                     ligacao: str = "", pagina: int = 1, por_pagina: int = 50):
    """Sem `lead_id` nem `ligacao`, só conversas ligadas a um lead (lista comercial)."""
    consulta = Conversa.objects.filter(site_id=_site(site_id))
    if estado:
        if estado not in ESTADOS:
            raise HttpError(422, "estado deve ser agente, pessoa ou encerrada")
        consulta = consulta.filter(estado=estado)
    if canal:
        if canal not in CANAIS:
            raise HttpError(422, "canal deve ser whatsapp ou email")
        consulta = consulta.filter(canal=canal)
    if lead_id:
        consulta = consulta.filter(lead_id=lead_id.strip(), ligacao="ligada")
    elif ligacao == "todas":
        pass
    elif ligacao:
        if ligacao not in LIGACOES:
            raise HttpError(422, "ligacao deve ser ligada, ambigua, desconhecida, pendente ou todas")
        consulta = consulta.filter(ligacao=ligacao)
    else:
        consulta = consulta.filter(ligacao="ligada")
    if pagina < 1 or not 1 <= por_pagina <= POR_PAGINA_MAXIMO:
        raise HttpError(422, f"pagina comeca em 1; por_pagina vai de 1 a {POR_PAGINA_MAXIMO}")
    total = consulta.count()
    inicio = (pagina - 1) * por_pagina
    itens = list(consulta.order_by(F("ultima_mensagem_em").desc(nulls_last=True), "-criada_em")
                 [inicio:inicio + por_pagina])
    parados = _descadastrados(itens)
    return {"itens": [conversa_json(c, parados) for c in itens], "total": total, "pagina": pagina,
            "por_pagina": por_pagina, "tem_mais": inicio + por_pagina < total}


class AbrirEntrada(Schema):
    site_id: str
    canal: str
    lead_id: str
    endereco: str


@router.post("/conversas")
def abrir_conversa(request, dados: AbrirEntrada):
    """Abre (ou devolve) a conversa de um lead para o primeiro contato proativo."""
    _escrita(request)
    site_id = _site(dados.site_id)
    if dados.canal not in CANAIS:
        raise HttpError(422, "canal deve ser whatsapp ou email")
    endereco = enderecos.endereco_do_canal(dados.canal, dados.endereco)
    if not endereco:
        raise HttpError(422, "telefone ou e-mail invalido")
    if not dados.lead_id.strip():
        raise HttpError(422, "lead_id obrigatorio")
    conversa, _ = Conversa.objects.get_or_create(
        site_id=site_id, canal=dados.canal, endereco=endereco,
        defaults={"lead_id": dados.lead_id.strip()[:64], "ligacao": "ligada"},
    )
    if conversa.ambigua:
        # Mais de um contato usa este endereco: quem escolhe e a equipe, nao o primeiro que pedir.
        raise HttpError(409, "este endereco pertence a mais de um contato; a equipe precisa escolher")
    if conversa.ligacao != "ligada":
        conversa.lead_id, conversa.ligacao = dados.lead_id.strip()[:64], "ligada"
        conversa.save(update_fields=["lead_id", "ligacao", "atualizada_em"])
    elif conversa.lead_id != dados.lead_id.strip():
        raise HttpError(409, "este endereco ja conversa como outro lead")
    return conversa_json(conversa)


@router.get("/conversas/{conversa_id}")
def ver_conversa(request, conversa_id: str, site_id: str):
    return conversa_json(_conversa(conversa_id, site_id))


def _antes_de(conversa: Conversa, valor: str) -> Q:
    """`antes_de` é o id de uma mensagem (preciso) ou uma data ISO (só mensagens estritamente antes)."""
    try:
        ancora = conversa.mensagens.filter(pk=uuid.UUID(valor.strip())).first()
    except ValueError:
        ancora = None
        try:
            return Q(ocorrida_em__lt=datetime.fromisoformat(valor))
        except ValueError:
            raise HttpError(422, "antes_de deve ser id de mensagem ou data ISO")
    if ancora is None:
        raise HttpError(422, "antes_de: mensagem inexistente nesta conversa")
    return (Q(ocorrida_em__lt=ancora.ocorrida_em)
            | Q(ocorrida_em=ancora.ocorrida_em, criada_em__lt=ancora.criada_em)
            | Q(ocorrida_em=ancora.ocorrida_em, criada_em=ancora.criada_em, id__lt=ancora.id))


@router.get("/conversas/{conversa_id}/mensagens")
def listar_mensagens(request, conversa_id: str, site_id: str, limite: int = 50, antes_de: str = ""):
    conversa = _conversa(conversa_id, site_id)
    if not 1 <= limite <= 200:
        raise HttpError(422, "limite vai de 1 a 200")
    consulta = conversa.mensagens.select_related("mensagem_whatsapp")
    if antes_de:
        consulta = consulta.filter(_antes_de(conversa, antes_de))
    recentes = list(consulta.order_by("-ocorrida_em", "-criada_em", "-id")[:limite])
    recentes.reverse()
    return {"conversa": conversa_json(conversa),
            "mensagens": [mensagem_json(envio._sincronizar(m)) for m in recentes],
            # Cursor da página anterior: id da mais antiga devolvida (desempata mensagens do mesmo instante).
            "proxima_antes_de": str(recentes[0].id) if recentes else None}


class ModeloEntrada(Schema):
    nome: str
    idioma: str = "pt_BR"
    componentes: list = []


class EnviarEntrada(Schema):
    site_id: str
    texto: str = ""
    chave_idempotencia: str
    autor: str = "agente"
    autor_id: str = ""
    assunto: str = ""
    modelo: ModeloEntrada | None = None


@router.post("/conversas/{conversa_id}/mensagens")
def enviar_mensagem(request, conversa_id: str, dados: EnviarEntrada):
    """`resultado`: enviada, repetida, falhou, fora_da_janela, sem_consentimento, descadastrado,
    conversa_com_pessoa, fora_do_horario ou limite_diario (estas duas só para o agente, com `reagendar_para`).
    Horário e teto do dia valem para a iniciativa do agente; resposta a quem falou por último (uma por fala,
    com a janela de 24h aberta) não passa por eles."""
    _escrita(request)
    conversa = _conversa(conversa_id, dados.site_id)
    chave = dados.chave_idempotencia.strip()
    if not chave or len(chave) > 100:
        raise HttpError(422, "chave_idempotencia obrigatoria (ate 100 caracteres)")
    if dados.autor not in ("agente", "pessoa"):
        raise HttpError(422, "autor deve ser agente ou pessoa")
    if not dados.texto.strip() and not dados.modelo:
        raise HttpError(422, "texto obrigatorio")
    if dados.modelo and conversa.canal != "whatsapp":
        raise HttpError(422, "modelo aprovado so existe no WhatsApp")
    resultado = envio.enviar(
        conversa=conversa, texto=dados.texto, chave_idempotencia=chave, autor=dados.autor,
        autor_id=dados.autor_id, assunto=dados.assunto,
        modelo=dados.modelo.dict() if dados.modelo else None,
    )
    conversa.refresh_from_db()
    return {"resultado": resultado.resultado, "detalhe": resultado.detalhe or None,
            "reagendar_para": _data(resultado.reagendar_para),
            "mensagem": mensagem_json(resultado.mensagem) if resultado.mensagem else None,
            "conversa": conversa_json(conversa)}


class AssumirEntrada(Schema):
    site_id: str
    pessoa_id: str


class SiteEntrada(Schema):
    site_id: str


@router.post("/conversas/{conversa_id}/assumir")
def assumir(request, conversa_id: str, dados: AssumirEntrada):
    """Uma pessoa da equipe assume: o agente para de responder nesta conversa."""
    _escrita(request)
    conversa = _conversa(conversa_id, dados.site_id)
    if not dados.pessoa_id.strip():
        raise HttpError(422, "pessoa_id obrigatorio")
    conversa.estado, conversa.assumida_por, conversa.assumida_em = "pessoa", dados.pessoa_id.strip()[:100], timezone.now()
    conversa.save(update_fields=["estado", "assumida_por", "assumida_em", "atualizada_em"])
    return conversa_json(conversa)


@router.post("/conversas/{conversa_id}/devolver")
def devolver(request, conversa_id: str, dados: SiteEntrada):
    """Devolve o atendimento ao agente."""
    _escrita(request)
    conversa = _conversa(conversa_id, dados.site_id)
    conversa.estado, conversa.assumida_por, conversa.assumida_em = "agente", "", None
    conversa.save(update_fields=["estado", "assumida_por", "assumida_em", "atualizada_em"])
    return conversa_json(conversa)


@router.post("/conversas/{conversa_id}/encerrar")
def encerrar(request, conversa_id: str, dados: SiteEntrada):
    """Encerra; uma nova mensagem do contato reabre com o agente."""
    _escrita(request)
    conversa = _conversa(conversa_id, dados.site_id)
    conversa.estado = "encerrada"
    conversa.save(update_fields=["estado", "atualizada_em"])
    return conversa_json(conversa)


class TranscricaoEntrada(Schema):
    site_id: str
    transcricao: str


@router.post("/conversas/{conversa_id}/mensagens/{mensagem_id}/transcricao")
def transcrever(request, conversa_id: str, mensagem_id: str, dados: TranscricaoEntrada):
    """Guarda a transcrição de um áudio recebido, ligada à mídia original."""
    _escrita(request)
    conversa = _conversa(conversa_id, dados.site_id)
    try:
        chave = uuid.UUID(str(mensagem_id))
    except ValueError:
        raise HttpError(404, "mensagem inexistente")
    mensagem = conversa.mensagens.filter(pk=chave).first()
    if mensagem is None:
        raise HttpError(404, "mensagem inexistente")
    mensagem.transcricao = dados.transcricao
    mensagem.save(update_fields=["transcricao"])
    return mensagem_json(mensagem)


class OrientacaoEntrada(Schema):
    endereco_quiz: str = ""
    atendimento_geral: str = ""


def _orientacao_json(site_id: str, config: OrientacaoDoSite | None) -> dict:
    return {"site_id": site_id,
            "endereco_quiz": config.endereco_quiz if config else "",
            "atendimento_geral": config.atendimento_geral if config else ""}


@router.get("/orientacoes/{site_id}")
def ver_orientacao(request, site_id: str):
    """Endereços que a orientação fixa cita neste site (vazio = o texto vai sem o link)."""
    site_id = _site(site_id)
    return _orientacao_json(site_id, OrientacaoDoSite.objects.filter(site_id=site_id).first())


@router.put("/orientacoes/{site_id}")
def definir_orientacao(request, site_id: str, dados: OrientacaoEntrada):
    """Define o endereço do quiz e o caminho de atendimento geral do site."""
    _escrita(request)
    site_id = _site(site_id)
    quiz, geral = dados.endereco_quiz.strip(), dados.atendimento_geral.strip()
    if quiz and not quiz.lower().startswith(("https://", "http://")):
        raise HttpError(422, "endereco_quiz deve ser um endereco completo (https://...)")
    if len(quiz) > 300 or len(geral) > 300:
        raise HttpError(422, "endereco_quiz e atendimento_geral aceitam ate 300 caracteres")
    config, _ = OrientacaoDoSite.objects.update_or_create(
        site_id=site_id, defaults={"endereco_quiz": quiz, "atendimento_geral": geral})
    return _orientacao_json(site_id, config)
