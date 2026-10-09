"""Porta administrativa da Central WhatsApp."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta

from django.db import transaction
from django.db.models import Exists, Max, Min, OuterRef, Q, Subquery
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Router, Schema
from ninja.errors import HttpError

from apps.conversas.models import Conversa, MensagemDaConversa
from apps.core.auth import tokens_de_publicacao

from . import central, condicoes
from .models import Entrega, Inscricao, Jornada, JornadaVersao, Passo, TextoDoPasso

router = Router()


class CriarEntrada(Schema):
    site_id: str
    nome: str
    objetivo: str = ""
    modelo: str | None = None


class SalvarEntrada(Schema):
    site_id: str
    versao_base: int
    nome: str
    objetivo: str = ""
    gatilho: str
    publico: str = "todos"
    resposta: str = "pausar"
    roteiro: str = ""
    passos: list[dict]


class AcaoEntrada(Schema):
    site_id: str
    acao: str
    versao: int | None = None


class TesteEntrada(Schema):
    site_id: str
    conversa_id: str
    versao: int | None = None
    chave_idempotencia: str


class ParticipantesEntrada(Schema):
    site_id: str
    pessoas: list[dict]
    chave_idempotencia: str
    agendado_em: datetime | None = None


def _site(site_id: str) -> str:
    site_id = (site_id or "").strip()
    if not site_id:
        raise HttpError(422, "site_id obrigatório")
    return site_id


def _escrever(request):
    if request.auth not in tokens_de_publicacao():
        raise HttpError(403, "grau de publicação necessário")


def _jornada(site_id, slug):
    jornada = get_object_or_404(Jornada, site_id=_site(site_id), slug=slug)
    if not jornada.versoes.filter(central_config__central=True).exists():
        raise HttpError(404, "automação inexistente")
    return jornada


def _versao(jornada, numero=None):
    q = jornada.versoes.filter(central_config__central=True)
    return q.filter(numero=numero).first() if numero is not None else q.order_by("-numero").first()


def _iso(valor):
    return valor.isoformat() if valor else None


def _resultado_exibido(entrega: Entrega) -> str:
    """O banco guarda a intenção pendente; a tela distingue espera pela régua."""
    if entrega.resultado == "pendente" and (
        entrega.motivo.startswith("o agente ja mandou ")
        or entrega.motivo.startswith("o agente so envia entre ")
    ):
        return "barrada_pela_regua"
    return entrega.resultado


def _resumo(jornada):
    atual = _versao(jornada)
    config = central.configuracao(atual) if atual else {}
    pub = jornada.versoes.filter(central_config__central=True, publicada_em__isnull=False).order_by("-numero").first()
    intencoes = Entrega.objects.filter(inscricao__jornada=jornada, canal="whatsapp",
        whatsapp_intencao=True, resultado="pendente", inscricao__central_suspensa=False
    ).exclude(inscricao__estado__in=("cancelada", "saiu"))
    proximo_passo = Passo.objects.filter(jornada_versao_id=OuterRef("jornada_versao_id"),
        ordem__gt=OuterRef("passo_atual")).order_by("ordem").values("pk")[:1]
    mesma_intencao = Entrega.objects.filter(inscricao_id=OuterRef("pk"),
        passo_id=OuterRef("proximo_passo_id"), canal="whatsapp",
        whatsapp_intencao=True, resultado="pendente")
    agendadas = (Inscricao.objects.filter(jornada=jornada, estado="andando", central_suspensa=False,
        proximo_em__isnull=False).annotate(proximo_passo_id=Subquery(proximo_passo))
        .annotate(ja_tem_intencao=Exists(mesma_intencao)).filter(ja_tem_intencao=False))
    numero_intencoes = intencoes.count()
    quantidade = numero_intencoes + agendadas.count()
    proximo = agendadas.aggregate(primeiro=Min("proximo_em"))["primeiro"]
    if numero_intencoes:
        agora = timezone.now()
        proximo = min(proximo, agora) if proximo else agora
    return {"slug": jornada.slug, "nome": config.get("nome") or jornada.central_nome,
            "objetivo": config.get("objetivo") or jornada.central_objetivo,
            "gatilho": config.get("gatilho") or jornada.gatilho,
            "publico": config.get("publico", "todos"), "resposta": config.get("resposta", "pausar"),
            "roteiro": config.get("roteiro", ""), "ativa": jornada.ativa,
            "entrada_aberta": jornada.central_entrada_aberta, "pausada": jornada.central_pausada,
            "versao_atual": atual.numero if atual else None,
            "versao_publicada": pub.numero if pub else None,
            "proximos_envios": quantidade,
            "proximo_envio_em": _iso(proximo),
            "criada_em": _iso(jornada.criada_em)}


def _catalogos():
    try:
        from .acontecimentos import GATILHOS
        gatilhos = list(GATILHOS)
    except ImportError:
        gatilhos = [{"slug": slug, "nome": slug} for slug in (
            "identidade.pessoa-cadastrada", "aula.concluida", "checkpoint.devolvido")]
    gatilhos = [({**g, "nome": "Mensagem recebida no WhatsApp"}
                 if g.get("slug") == "mensagem.recebida" else g) for g in gatilhos]
    gatilhos += [{"slug": "manual", "nome": "Seleção manual de contatos"},
                 {"slug": "aluno.inatividade-detectada", "nome": "Aluno sem atividade há cinco dias"}]
    try:
        from apps.whatsapp_modelos import cloud
        from apps.whatsapp_modelos.models import ModeloWhatsApp
        conta = cloud.credenciais()["conta"]
        modelos_whatsapp = list(ModeloWhatsApp.objects.filter(
            conta=conta, estado="aprovado", presente_no_provedor=True, suportado=True
        ).values("nome", "idioma", "corpo")[:100])
    except Exception:  # noqa: BLE001 - catálogo vazio quando canal oficial não está ligado
        modelos_whatsapp = []
    return {"modelos": [{"slug": a, "nome": b} for a, b in central.MODELOS],
            "modelos_whatsapp": modelos_whatsapp,
            "gatilhos": gatilhos,
            "condicoes": [{"slug": "", "nome": "Sempre"}] +
                [{"slug": slug, "nome": slug.replace("-", " ")} for slug in condicoes.CONDICOES],
            "campos": [{"slug": c, "nome": c.capitalize()} for c in central.CAMPOS]}


@router.get("/automacoes")
def listar(request, site_id: str):
    site = _site(site_id)
    jornadas = Jornada.objects.filter(site_id=site, versoes__central_config__central=True).distinct().order_by("slug")
    return {"automacoes": [_resumo(j) for j in jornadas], **_catalogos()}


@router.post("/automacoes")
def criar(request, dados: CriarEntrada):
    _escrever(request)
    site = _site(dados.site_id)
    nome = dados.nome.strip()
    if not nome:
        raise HttpError(422, "nome obrigatório")
    modelo = dados.modelo or ""
    if modelo and modelo not in dict(central.MODELOS):
        raise HttpError(422, "modelo desconhecido")
    with transaction.atomic():
        base = re.sub(r"[^a-z0-9]+", "-", nome.lower()).strip("-")[:60] or "automacao"
        slug = base
        numero = 2
        while Jornada.objects.filter(site_id=site, slug=slug).exists():
            slug = f"{base[:70]}-{numero}"
            numero += 1
        jornada = Jornada.objects.create(site_id=site, slug=slug, gatilho="rascunho.central",
                                          central_nome=nome, central_objetivo=dados.objetivo)
        versao = JornadaVersao.objects.create(jornada=jornada, numero=1,
            central_config={"central": True, "nome": nome, "objetivo": dados.objetivo,
                            "modelo": modelo, "gatilho": central.MODELO_GATILHOS.get(modelo, ""),
                            "publico": "todos", "resposta": "pausar",
                            "roteiro": central.MODELO_ROTEIROS.get(modelo, "")})
        if modelo:
            passo = Passo.objects.create(jornada_versao=versao, ordem=1,
                atraso=timedelta(0), classe=central.classe_do_gatilho(central.MODELO_GATILHOS[modelo]),
                canais=["whatsapp"])
            TextoDoPasso.objects.create(passo=passo, idioma="pt-br", assunto_visivel=nome[:200],
                                        corpo=central.MODELO_CORPOS[modelo])
    return _resumo(jornada)


@router.get("/automacoes/{slug}")
def detalhe(request, slug: str, site_id: str, versao: int | None = None):
    jornada = _jornada(site_id, slug)
    versoes = list(jornada.versoes.filter(central_config__central=True).order_by("-numero"))
    atual = next((v for v in versoes if v.numero == versao), None) if versao is not None else versoes[0]
    if atual is None:
        raise HttpError(404, "versão inexistente")
    passos = []
    for passo in atual.passos.prefetch_related("textos").order_by("ordem"):
        texto = next((t for t in passo.textos.all() if t.idioma == "pt-br"), None)
        passos.append({"id": str(passo.id), "ordem": passo.ordem,
                       "atraso_segundos": int(passo.atraso.total_seconds()),
                       "corpo": texto.corpo if texto else "", "condicao_slug": passo.condicao_slug,
                       "interacao": passo.central_interacao,
                       "modelo_whatsapp": passo.central_modelo_whatsapp})
    participantes = list(Inscricao.objects.filter(jornada=jornada).order_by("-criada_em")[:100])
    ids = [p.id for p in participantes]
    entregas = list(Entrega.objects.filter(inscricao_id__in=ids).select_related("passo").order_by("-decidida_em")[:200])
    respostas = list(MensagemDaConversa.objects.filter(
        conversa_id__in=[p.central_conversa_id for p in participantes if p.central_conversa_id],
        direcao="entrada").order_by("-ocorrida_em")[:100])
    testes = list(MensagemDaConversa.objects.filter(conversa__site_id=jornada.site_id,
        autor_id=f"central:teste:{jornada.slug}", direcao="saida").order_by("-ocorrida_em")[:100])
    config_exibida = central.configuracao(atual)
    automacao_exibida = _resumo(jornada)
    automacao_exibida.update({k: config_exibida.get(k, automacao_exibida.get(k)) for k in
                             ("nome", "objetivo", "gatilho", "publico", "resposta", "roteiro")})
    return {"automacao": automacao_exibida, "versao_exibida": atual.numero,
            "config_exibida": config_exibida,
            "versoes": [{"numero": v.numero, "publicada_em": _iso(v.publicada_em),
                         "central_config": central.configuracao(v)} for v in versoes],
            "passos": passos,
            "participantes": [{"id": str(p.id), "destinatario_id": p.destinatario_id,
                               "estado": p.estado, "passo_atual": p.passo_atual,
                               "versao": p.jornada_versao.numero, "suspensa": p.central_suspensa,
                               "ancora_em": _iso(p.ancora_em), "proximo_em": _iso(p.proximo_em)}
                              for p in participantes],
            "entregas": [{"id": e.pk, "participante_id": str(e.inscricao_id),
                          "passo": e.passo.ordem, "resultado": _resultado_exibido(e),
                          "resultado_registrado": e.resultado, "motivo": e.motivo,
                          "previsto_para": _iso(e.previsto_para), "enviado_em": _iso(e.enviado_em)}
                         for e in entregas],
            "testes": [{"id": str(m.id), "conversa_id": str(m.conversa_id),
                        "estado": m.estado_envio, "erro": m.erro[:200],
                        "ocorrida_em": _iso(m.ocorrida_em)} for m in testes],
            "respostas": [{"id": str(m.id), "conversa_id": str(m.conversa_id),
                           "participante_id": str(p.id), "texto": m.texto[:500],
                           "ocorrida_em": _iso(m.ocorrida_em), "descadastro": m.descadastro}
                          for m in respostas for p in participantes
                          if p.central_conversa_id == m.conversa_id and m.ocorrida_em > p.ancora_em]}


@router.post("/automacoes/{slug}")
def salvar(request, slug: str, dados: SalvarEntrada):
    _escrever(request)
    with transaction.atomic():
        jornada = Jornada.objects.select_for_update().get(pk=_jornada(dados.site_id, slug).pk)
        ultima = jornada.versoes.order_by("-numero").first()
        if not ultima or dados.versao_base != ultima.numero:
            raise HttpError(409, "versão base mudou; recarregue")
        if not dados.nome.strip() or not dados.gatilho.strip() or not dados.passos:
            raise HttpError(422, "nome, gatilho e passos obrigatórios")
        publico_valido = (dados.publico in central.PUBLICOS or
                          any(dados.publico.startswith(prefix) and dados.publico[len(prefix):]
                              for prefix in ("curso:", "turma:")))
        if not publico_valido or dados.resposta not in central.RESPOSTAS:
            raise HttpError(422, "público ou ação de resposta desconhecidos")
        gatilhos = {g["slug"] for g in _catalogos()["gatilhos"]}
        if dados.gatilho not in gatilhos:
            raise HttpError(422, "gatilho não conectado")
        if not all(isinstance(p, dict) for p in dados.passos):
            raise HttpError(422, "passos inválidos")
        ordens = [p.get("ordem") for p in dados.passos]
        if ordens != list(range(1, len(ordens) + 1)):
            raise HttpError(422, "ordens dos passos devem ser 1, 2, 3...")
        versao = JornadaVersao.objects.create(jornada=jornada, numero=ultima.numero + 1,
            central_config={"central": True, "nome": dados.nome.strip(), "objetivo": dados.objetivo,
                            "gatilho": dados.gatilho, "publico": dados.publico,
                            "resposta": dados.resposta, "roteiro": dados.roteiro,
                            "modelo": central.configuracao(ultima).get("modelo", "")})
        for item in dados.passos:
            try:
                atraso = int(item.get("atraso_segundos", 0))
                corpo = str(item.get("corpo") or "").strip()
                condicao = str(item.get("condicao_slug") or "")
                interacao = str(item.get("interacao") or "")
                modelo = item.get("modelo_whatsapp") or {}
            except (TypeError, ValueError):
                raise HttpError(422, "passo inválido")
            if atraso < 0 or atraso > 31536000 or not corpo or len(corpo) > 4096:
                raise HttpError(422, "atraso ou texto inválido")
            if condicao and condicao not in condicoes.CONDICOES:
                raise HttpError(422, "condição desconhecida")
            if interacao not in central.INTERACOES or not isinstance(modelo, dict):
                raise HttpError(422, "interação ou modelo WhatsApp inválido")
            passo = Passo.objects.create(jornada_versao=versao, ordem=item["ordem"],
                atraso=timedelta(seconds=atraso), classe=central.classe_do_gatilho(dados.gatilho),
                canais=["whatsapp"],
                condicao_slug=condicao, central_interacao=interacao,
                central_modelo_whatsapp=modelo)
            TextoDoPasso.objects.create(passo=passo, idioma="pt-br",
                                        assunto_visivel=dados.nome[:200], corpo=corpo)
        jornada.central_nome = dados.nome.strip()
        jornada.central_objetivo = dados.objetivo
        jornada.save(update_fields=["central_nome", "central_objetivo"])
    return _resumo(jornada)


@router.post("/automacoes/{slug}/acao")
def acao(request, slug: str, dados: AcaoEntrada):
    _escrever(request)
    with transaction.atomic():
        jornada = Jornada.objects.select_for_update().get(pk=_jornada(dados.site_id, slug).pk)
        acao = dados.acao
        if acao == "ativar":
            versao = _versao(jornada, dados.versao)
            if versao is None or not versao.passos.exists():
                raise HttpError(422, "versão sem passos")
            gatilho = central.configuracao(versao).get("gatilho", "")
            if gatilho not in {g["slug"] for g in _catalogos()["gatilhos"]}:
                raise HttpError(422, "escolha um gatilho conectado antes de ativar")
            if any(not p.textos.filter(idioma="pt-br").exists() for p in versao.passos.all()):
                raise HttpError(422, "todos os passos precisam de texto")
            publicada = jornada.versoes.filter(central_config__central=True,
                                               publicada_em__isnull=False).aggregate(Max("numero"))["numero__max"] or 0
            if versao.numero < publicada:
                raise HttpError(409, "há uma versão publicada mais recente")
            if not versao.publicada_em:
                JornadaVersao.objects.filter(pk=versao.pk, publicada_em__isnull=True).update(publicada_em=timezone.now())
            jornada.gatilho = gatilho
            jornada.ativa, jornada.central_entrada_aberta, jornada.central_pausada = True, True, False
        elif acao == "fechar_entrada":
            jornada.central_entrada_aberta = False
        elif acao == "pausar":
            jornada.central_pausada = True
        elif acao == "retomar":
            jornada.central_pausada = False
            jornada.ativa = True
            Inscricao.objects.filter(jornada=jornada, central_suspensa=True, estado="andando").update(central_suspensa=False)
        elif acao == "encerrar":
            jornada.ativa, jornada.central_entrada_aberta, jornada.central_pausada = False, False, True
            Inscricao.objects.filter(jornada=jornada, estado="andando").update(
                estado="cancelada", proximo_em=None, motivo_de_saida="automação encerrada")
        elif acao == "retomar_falhas":
            pass
        else:
            raise HttpError(422, "ação desconhecida")
        jornada.save(update_fields=["gatilho", "ativa", "central_entrada_aberta", "central_pausada"])
    if dados.acao == "retomar_falhas":
        for entrega in Entrega.objects.filter(inscricao__jornada=jornada, resultado="falhou",
                                              canal="whatsapp").select_related("inscricao", "passo")[:100]:
            central.processar_entrega(entrega, permitir_falha=True)
    return _resumo(jornada)


@router.post("/automacoes/{slug}/teste")
def teste(request, slug: str, dados: TesteEntrada):
    _escrever(request)
    jornada = _jornada(dados.site_id, slug)
    versao = _versao(jornada, dados.versao)
    if versao is None or not dados.chave_idempotencia.strip():
        raise HttpError(422, "versão e chave de teste obrigatórias")
    try:
        chave_conversa = uuid.UUID(dados.conversa_id)
    except (ValueError, TypeError):
        raise HttpError(404, "conversa WhatsApp inexistente")
    conversa = Conversa.objects.filter(pk=chave_conversa, site_id=jornada.site_id,
                                       canal="whatsapp").first()
    if conversa is None:
        raise HttpError(404, "conversa WhatsApp inexistente")
    try:
        return central.testar(jornada=jornada, conversa=conversa, versao=versao,
                              chave_idempotencia=dados.chave_idempotencia)
    except ValueError as erro:
        raise HttpError(422, str(erro)) from erro


@router.post("/automacoes/{slug}/participantes")
def inscrever_participantes(request, slug: str, dados: ParticipantesEntrada):
    """Inscrição manual de contatos selecionados, com idempotência por seleção."""
    _escrever(request)
    jornada = _jornada(dados.site_id, slug)
    versao = jornada.versoes.filter(publicada_em__isnull=False,
                                    central_config__central=True).order_by("-numero").first()
    if (not jornada.ativa or not jornada.central_entrada_aberta or jornada.central_pausada
            or jornada.gatilho != "manual" or versao is None):
        raise HttpError(409, "automação manual não está recebendo participantes")
    if not dados.chave_idempotencia.strip() or not dados.pessoas or len(dados.pessoas) > 200:
        raise HttpError(422, "chave e 1 a 200 pessoas obrigatórias")
    momento = dados.agendado_em or timezone.now()
    if timezone.is_naive(momento) or momento < timezone.now() - timedelta(minutes=5):
        raise HttpError(422, "agendamento deve ter fuso horário e ser futuro")
    inscritos, recusados = [], []
    for item in dados.pessoas:
        pessoa = str(item.get("destinatario_id") or "")[:64]
        contexto = item.get("contexto") or {}
        if not pessoa or not isinstance(contexto, dict):
            recusados.append({"destinatario_id": pessoa, "motivo": "pessoa ou contexto inválido"})
            continue
        conversa = None
        if item.get("conversa_id"):
            try:
                conversa = Conversa.objects.filter(pk=uuid.UUID(str(item["conversa_id"])),
                                                   site_id=jornada.site_id, canal="whatsapp").first()
            except (ValueError, TypeError):
                conversa = None
            if conversa is None:
                recusados.append({"destinatario_id": pessoa, "motivo": "conversa inexistente neste site"})
                continue
        fato = uuid.uuid5(uuid.NAMESPACE_URL,
                          f"central-manual:{jornada.site_id}:{jornada.slug}:{dados.chave_idempotencia}:{pessoa}")
        episodios = central.inscrever_evento(gatilho="manual", site_id=jornada.site_id,
            destinatario_id=pessoa, event_id=fato, contexto=contexto, conversa=conversa, momento=momento,
            jornada_slug=jornada.slug)
        episodio = next((i for i in episodios if i.jornada_id == jornada.id), None)
        if episodio and episodio.central_conversa_id:
            inscritos.append({"destinatario_id": pessoa, "inscricao_id": str(episodio.id),
                              "conversa_id": str(episodio.central_conversa_id), "estado": episodio.estado,
                              "proximo_em": _iso(episodio.proximo_em)})
        else:
            recusados.append({"destinatario_id": pessoa, "motivo": "contato WhatsApp ou público não confirmado"})
    return {"inscritos": inscritos, "recusados": recusados}


@router.get("/automacoes/contexto/{conversa_id}")
def contexto_da_conversa(request, conversa_id: str, site_id: str):
    """Roteiros vigentes para o agente; não executa instruções nem envia mensagens."""
    try:
        chave_conversa = uuid.UUID(conversa_id)
    except (ValueError, TypeError):
        raise HttpError(404, "conversa inexistente")
    conversa = Conversa.objects.filter(pk=chave_conversa, site_id=_site(site_id), canal="whatsapp").first()
    if conversa is None:
        raise HttpError(404, "conversa inexistente")
    recentes = timezone.now() - timedelta(days=30)
    inscricoes = (Inscricao.objects.filter(site_id=site_id, central_conversa_id=conversa.pk,
        jornada__ativa=True).filter(Q(estado="andando") | Q(estado="concluida", criada_em__gte=recentes))
        .select_related("jornada", "jornada_versao").order_by("-criada_em")[:100])
    automacoes, vistas = [], set()
    for i in inscricoes:
        if i.jornada_id in vistas or not central.e_central(i.jornada_versao):
            continue
        vistas.add(i.jornada_id)
        config = central.configuracao(i.jornada_versao)
        automacoes.append({"slug": i.jornada.slug, "nome": config.get("nome", ""),
            "objetivo": config.get("objetivo", ""), "roteiro": config.get("roteiro", ""),
            "resposta": config.get("resposta", "pausar"), "passo_atual": i.passo_atual,
            "proximo_em": _iso(i.proximo_em), "suspensa": i.central_suspensa,
            "estado": i.estado, "inscricao_id": str(i.id)})
        if len(automacoes) >= 30:
            break
    return {"conversa_id": str(conversa.pk), "automacoes": automacoes}
