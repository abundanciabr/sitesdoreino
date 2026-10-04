"""Funil por etapa, qualidade do atendimento e desempenho técnico dos agentes.

Três medidas da seção "Como medir resultado e custo" do plano do CRM com
agentes, para a tela de resultados:

* funil: oportunidades abertas, com resposta do lead, com link enviado, com
  pedido, ganhas e receita, por versão de estratégia e por atendente. Quem
  guarda é a `metricas` (`countCrmFunnel`); aqui só se pergunta;
* qualidade do atendimento: descadastros, passagens para pessoa (e por quê),
  trabalhos que falharam ou ficaram em envio incerto, mensagens que o canal
  recusou. Só leitura do registro dos agentes desta célula e da mensageria;
* desempenho técnico: tempo de resposta ao lead, espera na fila e tentativas.

Trabalho de teste fica fora de tudo. Nada aqui carrega texto de lead, nome,
e-mail ou telefone: só contagens e tempos. Fonte que não respondeu aparece
como "ainda indisponível", nunca como zero.
"""

from __future__ import annotations

import datetime as dt
import logging
from collections import Counter

from django.db import DatabaseError
from django.db.models import Count, Min, Q
from django.utils import timezone

from .clients import CatalogoClient, FunilCrmClient

logger = logging.getLogger("admin.crm_resultados")

LIMITE_DE_TRABALHOS = 20000
INDISPONIVEL = "ainda indisponível"

#: O que o canal responde quando recusa um envio, na linguagem da tela.
RECUSAS = (
    ("janela", "WhatsApp fora da janela de 24 horas", ("fora_da_janela",)),
    ("horario", "Fora do horário permitido", ("fora_do_horario",)),
    ("teto", "Teto diário de mensagens por pessoa", ("limite_diario", "limite_do_dia")),
    ("descadastrado", "Pessoa pediu para não receber", ("descadastrado",)),
    ("sem_consentimento", "Pessoa não autorizou o canal", ("sem_consentimento",)),
    ("pessoa_atendendo", "Uma pessoa da equipe já atendia", ("conversa_com_pessoa",)),
    ("canal_falhou", "O canal não conseguiu entregar", ("falhou",)),
)

#: Motivos de passar para uma pessoa, por palavra. A frase do agente é livre e
#: pode citar a conversa: a tela mostra só o grupo, nunca o texto.
MOTIVOS_DA_PASSAGEM = (
    ("pediu_pessoa", "Pediu para falar com uma pessoa", ("pessoa", "humano", "atendente", "equipe", "responsável")),
    ("preco", "Preço, desconto ou condição de pagamento", ("preço", "preco", "desconto", "parcel", "pix", "valor", "negoci", "pagamento")),
    ("reclamacao", "Reclamação, reembolso ou problema", ("reclam", "reembols", "estorno", "problema", "cancel", "insatisf")),
    ("fora_do_conhecimento", "Dúvida que o agente não soube responder", ("dúvida", "duvida", "não sei", "nao sei", "fora do", "conhecimento", "complex")),
)


def _inicio_e_fim(desde: dt.date, ate: dt.date):
    zona = timezone.get_current_timezone()
    inicio = timezone.make_aware(dt.datetime.combine(desde, dt.time.min), zona)
    fim = timezone.make_aware(dt.datetime.combine(ate + dt.timedelta(days=1), dt.time.min), zona)
    return inicio, fim


def _modelos():
    from .crm_resultados import _modelos_comerciais

    return _modelos_comerciais()


def duracao(segundos) -> str:
    """"2 min 05 s", "45 s", "1 h 10 min": tempo curto em português simples."""
    if segundos is None:
        return INDISPONIVEL
    total = max(0, int(round(segundos)))
    horas, resto = divmod(total, 3600)
    minutos, seg = divmod(resto, 60)
    if horas:
        return f"{horas} h {minutos:02d} min"
    if minutos:
        return f"{minutos} min {seg:02d} s"
    return f"{seg} s"


def _numero(valor, casas=1) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


# ---------------------------------------------------------------------------
# Funil
# ---------------------------------------------------------------------------
def site_do_funil(request, filtro: str, Trabalho=None) -> "str | None":
    """O site do funil: o escolhido na tela; senão o do domínio; senão o único
    site que tem trabalho dos agentes. `None` quando não dá para saber."""
    if filtro:
        return filtro
    try:
        site = CatalogoClient().site_por_host(request.get_host().split(":")[0].lower())
    except Exception:  # noqa: BLE001 - a tela não cai porque o catálogo falhou
        site = None
    if isinstance(site, dict) and site.get("id"):
        return str(site["id"])
    if Trabalho is not None:
        try:
            sites = list(Trabalho.objects.filter(teste=False).exclude(site_id="").values_list("site_id", flat=True).distinct()[:2])
        except DatabaseError:
            return None
        if len(sites) == 1:
            return sites[0]
    return None


def _rotulo_do_atendente(valor) -> str:
    return {"agente": "Agente", "pessoa": "Pessoa"}.get(valor, "Não informado" if not valor else str(valor)[:20])


def _linha_do_funil(grupo: dict, nome: str) -> dict:
    from .crm_resultados import reais

    return dict(grupo, nome=nome, receita_texto=reais(grupo["receita_centavos"]))


def _com_mensagem_do_agente(desde, ate, site_id) -> "int | None":
    modelos = _modelos()
    if modelos is None:
        return None
    Trabalho, Decisao = modelos
    inicio, fim = _inicio_e_fim(desde, ate)
    decisoes = Decisao.objects.filter(
        ferramenta="enviar_mensagem", resultado="feito", criada_em__gte=inicio, criada_em__lt=fim,
        trabalho__teste=False,
    ).exclude(trabalho__oportunidade_id="")
    if site_id:
        decisoes = decisoes.filter(trabalho__site_id=site_id)
    try:
        return decisoes.values("trabalho__oportunidade_id").distinct().count()
    except DatabaseError:
        return None


def funil(request, desde, ate, site_filtro: str) -> dict:
    modelos = _modelos()
    site_id = site_do_funil(request, site_filtro, modelos[0] if modelos else None)
    if not site_id:
        return {"disponivel": False, "aviso": "O funil ainda está indisponível: não deu para saber de qual site perguntar."}
    estado, dados = FunilCrmClient().funil_crm(site_id, desde, ate)
    if estado != FunilCrmClient.OK:
        return {
            "disponivel": False,
            "aviso": (
                "O funil ainda está indisponível: o painel aguarda a conexão com a medição."
                if estado == FunilCrmClient.SEM_CONFIGURACAO
                else "O funil ainda está indisponível: a medição não respondeu. Tente de novo em instantes."
            ),
        }
    por_estrategia = [
        _linha_do_funil(g, "Sem versão" if g["estrategia_versao"] is None else f"Versão {g['estrategia_versao']}")
        for g in dados["por_estrategia"]
    ]
    por_atendente = [_linha_do_funil(g, _rotulo_do_atendente(g["atendente"])) for g in dados["por_atendente"]]
    soma = {c: sum(g[c] for g in dados["por_estrategia"]) for c in FunilCrmClient.CAMPOS_DO_GRUPO}
    soma["amostra_insuficiente"] = bool(dados["amostra_minima"]) and soma["abertas"] < dados["amostra_minima"]
    return {
        "disponivel": True,
        "site_id": site_id,
        "oportunidades": dados["oportunidades"],
        "mensagens_recebidas": dados["mensagens_recebidas"],
        "amostra_minima": dados["amostra_minima"],
        "total": _linha_do_funil(soma, "Todas"),
        "por_estrategia": por_estrategia,
        "por_atendente": por_atendente,
        "com_mensagem_do_agente": _com_mensagem_do_agente(desde, ate, site_id),
    }


# ---------------------------------------------------------------------------
# Qualidade do atendimento
# ---------------------------------------------------------------------------
def _grupo_do_motivo(texto) -> str:
    texto = str(texto or "").lower()
    for chave, _nome, palavras in MOTIVOS_DA_PASSAGEM:
        if any(p in texto for p in palavras):
            return chave
    return "outro"


def _descadastros_da_mensageria(desde, ate, site_id) -> "int | None":
    if not site_id:
        return None
    from .crm_resultados import ConversasClient

    resumo = ConversasClient().resumo(site_id, desde.isoformat(), ate.isoformat())
    if not resumo:
        return None
    return sum(
        int(l.get("descadastros") or 0) for l in resumo["por_canal"] if isinstance(l, dict)
    )


def qualidade(desde, ate, site_id: str) -> dict:
    modelos = _modelos()
    if modelos is None:
        return {"disponivel": False}
    Trabalho, Decisao = modelos
    inicio, fim = _inicio_e_fim(desde, ate)
    trabalhos = Trabalho.objects.filter(teste=False, criado_em__gte=inicio, criado_em__lt=fim)
    decisoes = Decisao.objects.filter(trabalho__teste=False, criada_em__gte=inicio, criada_em__lt=fim)
    if site_id:
        trabalhos = trabalhos.filter(site_id=site_id)
        decisoes = decisoes.filter(trabalho__site_id=site_id)
    estados = Trabalho.Estado
    try:
        por_estado = dict(trabalhos.values_list("estado").annotate(n=Count("id")))
        descadastros_dos_trabalhos = trabalhos.filter(tipo=Trabalho.Tipo.ATENDER_MENSAGEM, entrada__descadastro=True).count()
        passagens = list(
            decisoes.filter(ferramenta="passar_para_responsavel", resultado="feito")
            .values_list("trabalho_id", "entrada")
        )
        recusas = list(
            decisoes.filter(ferramenta="enviar_mensagem", resultado="recusado").values_list("saida", flat=True)
        )
    except DatabaseError:
        logger.exception("resultados: leitura da qualidade do atendimento falhou")
        return {"disponivel": False}

    descadastros = _descadastros_da_mensageria(desde, ate, site_id)
    fonte_descadastros = "mensageria"
    if descadastros is None:
        descadastros, fonte_descadastros = descadastros_dos_trabalhos, "agentes"

    motivos = Counter()
    pessoas = set()
    for trabalho_id, entrada in passagens:
        if trabalho_id in pessoas:
            continue
        pessoas.add(trabalho_id)
        motivos[_grupo_do_motivo((entrada or {}).get("motivo") if isinstance(entrada, dict) else "")] += 1
    nomes = {c: n for c, n, _ in MOTIVOS_DA_PASSAGEM} | {"outro": "Outro motivo"}
    passagem_por_motivo = [{"nome": nomes[c], "n": n} for c, n in motivos.most_common()]

    contagem_de_recusas = Counter()
    for saida in recusas:
        palavra = (saida or {}).get("resultado") if isinstance(saida, dict) else ""
        for chave, _nome, palavras in RECUSAS:
            if palavra in palavras:
                contagem_de_recusas[chave] += 1
                break
        else:
            contagem_de_recusas["outra"] += 1
    nomes_recusa = {c: n for c, n, _ in RECUSAS} | {"outra": "Outro motivo do canal"}
    recusadas = [{"chave": c, "nome": nomes_recusa[c], "n": contagem_de_recusas[c]} for c, _n, _p in RECUSAS]
    if contagem_de_recusas["outra"]:
        recusadas.append({"chave": "outra", "nome": nomes_recusa["outra"], "n": contagem_de_recusas["outra"]})

    return {
        "disponivel": True,
        "trabalhos": sum(por_estado.values()),
        "descadastros": descadastros,
        "descadastros_fonte": fonte_descadastros,
        "passaram_para_pessoa": len(pessoas),
        "passagem_por_motivo": passagem_por_motivo,
        "falharam": por_estado.get(estados.FALHOU, 0),
        "envio_incerto": por_estado.get(estados.ENVIO_INCERTO, 0),
        "esperando_teto_de_gasto": por_estado.get(estados.AGUARDANDO_AUTORIZACAO, 0),
        "recusadas": recusadas,
        "recusadas_total": sum(r["n"] for r in recusadas),
        "janela": contagem_de_recusas["janela"],
        "horario": contagem_de_recusas["horario"],
        "teto": contagem_de_recusas["teto"],
    }


# ---------------------------------------------------------------------------
# Desempenho técnico
# ---------------------------------------------------------------------------
def desempenho(desde, ate, site_id: str) -> dict:
    modelos = _modelos()
    if modelos is None:
        return {"disponivel": False}
    Trabalho, _Decisao = modelos
    inicio, fim = _inicio_e_fim(desde, ate)
    trabalhos = Trabalho.objects.filter(teste=False, criado_em__gte=inicio, criado_em__lt=fim)
    if site_id:
        trabalhos = trabalhos.filter(site_id=site_id)
    tipos = Trabalho.Tipo
    try:
        respostas = list(
            trabalhos.filter(tipo=tipos.ATENDER_MENSAGEM)
            .annotate(primeira=Min(
                "decisoes__criada_em",
                filter=Q(decisoes__ferramenta="enviar_mensagem", decisoes__resultado="feito"),
            ))
            .exclude(primeira__isnull=True)
            .values_list("criado_em", "primeira")[:LIMITE_DE_TRABALHOS]
        )
        # Só os trabalhos que começam na hora: abordagem e acompanhamento de
        # pagamento têm hora marcada para começar, e esperar por ela não é fila.
        esperas = list(
            trabalhos.filter(tipo__in=[tipos.ATENDER_MENSAGEM, tipos.ANALISAR_LEAD], iniciado_em__isnull=False)
            .values_list("criado_em", "iniciado_em")[:LIMITE_DE_TRABALHOS]
        )
        tentativas = list(trabalhos.filter(tentativas__gt=0).values_list("tentativas", flat=True)[:LIMITE_DE_TRABALHOS])
        total = trabalhos.count()
        falharam = trabalhos.filter(estado=Trabalho.Estado.FALHOU).count()
        incertos = trabalhos.filter(estado=Trabalho.Estado.ENVIO_INCERTO).count()
    except DatabaseError:
        logger.exception("resultados: leitura do desempenho técnico falhou")
        return {"disponivel": False}

    tempos = [max(0.0, (p - c).total_seconds()) for c, p in respostas]
    filas = [max(0.0, (i - c).total_seconds()) for c, i in esperas]
    return {
        "disponivel": True,
        "trabalhos": total,
        "respostas": len(tempos),
        "resposta_media_texto": duracao(sum(tempos) / len(tempos)) if tempos else None,
        "resposta_pior_texto": duracao(max(tempos)) if tempos else None,
        "fila_amostra": len(filas),
        "fila_media_texto": duracao(sum(filas) / len(filas)) if filas else None,
        "fila_pior_texto": duracao(max(filas)) if filas else None,
        "tentativas_amostra": len(tentativas),
        "tentativas_media_texto": _numero(sum(tentativas) / len(tentativas)) if tentativas else None,
        "tentativas_maximo": max(tentativas) if tentativas else None,
        "falharam": falharam,
        "falhas_taxa_texto": (_numero(falharam * 100 / total) + "%") if total else None,
        "envio_incerto": incertos,
    }
