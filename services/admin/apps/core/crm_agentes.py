"""A área dos agentes do CRM: o que a equipe comercial de agentes está
fazendo, o que decidiu, quanto gastou e com que estratégia.

Plano do CRM com agentes (03/10/2026), "Como o painel ficará": trabalhos em
andamento, última decisão, ação realizada, versão da estratégia e consumo; e as
estratégias por papel, em versões, com a possibilidade de ativar uma versão ou
voltar à anterior.

Os registros moram no app `apps.comercial` (coordenador). Enquanto ele não
estiver instalado ou não responder, a tela diz que a capacidade ainda não está
disponível — nunca erro 500. Esta é a única página dos agentes comerciais: o
que a primeira página do coordenador fazia (ver um trabalho com todas as
decisões, retomar um trabalho parado, pôr no ar a proposta do otimizador) mora
aqui.
"""
from __future__ import annotations

import logging
import uuid
from decimal import Decimal

from django.apps import apps as django_apps
from django.db import DatabaseError
from django.db.models import Count, Sum
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.auditoria.models import Registro

logger = logging.getLogger(__name__)

LIMITE_POR_GRUPO = 50
LIMITE_CONCLUIDOS = 20

# Os grupos da tela, na ordem em que o mantenedor lê.
GRUPOS = (
    ("andamento", "Em andamento", ("executando", "aguardando_dependencia", "aguardando_autorizacao")),
    ("fila", "Na fila", ("na_fila",)),
    ("incerto", "Envio sem confirmação", ("envio_incerto",)),
    ("falha", "Com falha", ("falhou",)),
    ("concluidos", "Concluídos recentes", ("concluido", "encerrado", "cancelado")),
)
LIMITE_DO_GRUPO = {"concluidos": LIMITE_CONCLUIDOS}
EXPLICA_GRUPO = {
    "andamento": "Trabalhos que um agente está fazendo agora ou que esperam um serviço ou o teto de gasto.",
    "fila": "Trabalhos esperando a vez.",
    "incerto": "A mensagem ou o link pode ter saído, mas o serviço não confirmou. O agente não repete o envio sozinho.",
    "falha": "Trabalhos que pararam com erro. O motivo aparece em cada um.",
    "concluidos": "Os últimos trabalhos que terminaram, inclusive os que pararam porque o pagamento foi aprovado. "
    "A análise de resultados que o relógio pede a cada hora não entra aqui. Abra um para ver cada decisão do agente.",
}

RECADOS = {
    "ativada": "Versão posta no ar. As próximas decisões usam esta versão.",
    "voltou": "A versão anterior voltou ao ar.",
    "sem_anterior": "Este papel não tem versão anterior para voltar.",
    "nova": "Nova versão guardada.",
    "nova_ativa": "Nova versão guardada e posta no ar.",
    "vazia": "Escreva as instruções da nova versão antes de guardar.",
    "nao_encontrada": "Essa versão não foi encontrada.",
    "indisponivel": "A equipe comercial de agentes ainda não está disponível.",
    "papel": "Esse papel não existe.",
    "mudou": "A versão no ar já mudou desde que esta tela abriu. Confira a versão atual antes de voltar de novo.",
    "retomado": "O trabalho voltou para a fila.",
    "nao_retomado": "Este trabalho não pode ser retomado no estado em que está.",
    "analise_pedida": "Análise de resultados pedida. Ela entra na fila e aparece em Trabalhos.",
    "analise_ja_pedida": "A análise de hoje já foi pedida; ela está em Trabalhos. Uma nova só amanhã.",
    "analise_desligada": "Os agentes comerciais estão desligados neste ambiente: a análise não foi pedida.",
    "comparacao_mudou": "Grupo de comparação atualizado. Vale só para os leads que chegarem daqui para a frente: quem já foi marcado continua no mesmo grupo.",
    "comparacao_igual": "O percentual já era esse; nada mudou.",
    "comparacao_sem_confirmacao": "Nada foi mudado: marque a confirmação para alterar o grupo de comparação.",
    "comparacao_invalida": "Nada foi mudado: informe um número inteiro de 0 a 50.",
}

# Estados em que o botão "Retomar" aparece (`coordenador.retomar`).
RETOMAVEIS = ("falhou", "aguardando_dependencia", "aguardando_autorizacao", "envio_incerto")


def comercial_disponivel() -> bool:
    return django_apps.is_installed("apps.comercial")


def _modelos():
    from apps.comercial.models import DecisaoComercial, EstrategiaComercial, TrabalhoComercial

    return TrabalhoComercial, DecisaoComercial, EstrategiaComercial


def _quem(request) -> str:
    admin = getattr(request, "admin", None) or {}
    return str(admin.get("email") or admin.get("id") or "mantenedor")


def _auditar(request, alvo: str, detalhe: str, ok: bool = True) -> None:
    admin = getattr(request, "admin", None) or {}
    Registro.objects.create(
        quem_email=admin.get("email", ""),
        quem_id=str(admin.get("id") or admin.get("email") or "mantenedor")[:64],
        acao=Registro.EDITAR,
        alvo=alvo[:64],
        desfecho=Registro.OK if ok else Registro.RECUSADO_PELA_CELULA,
        detalhe=detalhe[:500],
    )


def _curto(valor, limite: int = 90) -> str:
    if isinstance(valor, (dict, list)):
        texto = ", ".join(str(v) for v in (valor.values() if isinstance(valor, dict) else valor))
    else:
        texto = "" if valor is None else str(valor)
    texto = " ".join(texto.split())
    return texto if len(texto) <= limite else texto[: limite - 1] + "…"


def contexto_resumido(contexto) -> list[tuple[str, str]]:
    """Até cinco pares chave → valor curto do contexto que o agente usou."""
    if not isinstance(contexto, dict):
        return [("contexto", _curto(contexto))] if contexto else []
    return [(str(chave).replace("_", " "), _curto(valor)) for chave, valor in list(contexto.items())[:5] if valor not in (None, "", [], {})]


def _oportunidade_uuid(valor: str) -> str:
    try:
        return str(uuid.UUID(str(valor)))
    except (ValueError, TypeError, AttributeError):
        return ""


def _inicio_do_mes():
    from apps.agentes import modelo

    return modelo.inicio_do_mes()


def _limite_do_mes(gasto_comercial: Decimal) -> dict:
    """O teto já autorizado: o MESMO que o gasto usa de verdade
    (`modelo.autorizacao_ativa()`, a dos robôs da equipe, que o comercial
    divide). A tela nunca mostra um teto diferente do que trava a chamada."""
    from apps.agentes import modelo

    autorizacao = modelo.autorizacao_ativa()
    if autorizacao is None:
        return {"autorizacao": None, "gasto_comercial": gasto_comercial}
    gasto_da_autorizacao = modelo.gasto_do_mes(autorizacao.pk)
    teto = autorizacao.teto_mensal_usd or Decimal("0")
    usado = max(gasto_da_autorizacao, gasto_comercial)
    return {
        "autorizacao": autorizacao,
        "compartilhado": True,
        "teto": teto,
        "gasto_comercial": gasto_comercial,
        "gasto_da_autorizacao": gasto_da_autorizacao,
        "disponivel": max(teto - usado, Decimal("0")),
        "percentual": int(min(100, (usado * 100 / teto))) if teto > 0 else 100,
    }


def _preparar_trabalho(trabalho, decisoes) -> dict:
    ultima = decisoes[-1] if decisoes else None
    custo_decisoes = sum((d.custo_usd or Decimal("0")) for d in decisoes)
    tokens = 0
    for d in decisoes:
        consumo = d.consumo
        if consumo is not None:
            tokens += (consumo.tokens_entrada or 0) + (consumo.tokens_saida or 0)
    versao = None
    for d in reversed(decisoes):
        if d.versao_estrategia:
            versao = d.versao_estrategia
            break
    if versao is None and isinstance(trabalho.entrada, dict):
        versao = trabalho.entrada.get("estrategia_versao") or trabalho.entrada.get("versao_estrategia")
    return {
        "obj": trabalho,
        "tipo": trabalho.get_tipo_display(),
        "estado": trabalho.get_estado_display(),
        "papel": trabalho.papel,
        "oportunidade": _oportunidade_uuid(trabalho.oportunidade_id),
        "custo": trabalho.custo_usd if trabalho.custo_usd else custo_decisoes,
        "tokens": tokens,
        "versao": versao,
        "decisoes": len(decisoes),
        "retomavel": trabalho.estado in RETOMAVEIS,
        "ultima": None
        if ultima is None
        else {
            "acao": ultima.acao or "—",
            "ferramenta": ultima.ferramenta or "—",
            "resultado": ultima.get_resultado_display(),
            "resultado_chave": ultima.resultado,
            "contexto": contexto_resumido(ultima.contexto_usado),
            "saida": _curto(ultima.saida, 160) if ultima.saida else "",
            "quando": ultima.terminada_em or ultima.criada_em,
            "versao": ultima.versao_estrategia,
        },
    }


def _sem_analise_do_relogio(consulta):
    """A análise de resultados que o relógio pede a cada hora conclui quase
    sempre sem novidade: se entrasse na lista, empurraria para fora os trabalhos
    de verdade. A que a pessoa pede pelo botão (origem "painel") continua."""
    return consulta.exclude(tipo="analisar_resultados", origem="relogio")


def _grupos(mostrar_testes: bool) -> list[dict]:
    TrabalhoComercial, DecisaoComercial, _ = _modelos()
    base = TrabalhoComercial.objects.all()
    if not mostrar_testes:
        base = base.filter(teste=False)
    grupos = []
    for chave, nome, estados in GRUPOS:
        consulta = base.filter(estado__in=estados)
        if chave == "concluidos":
            consulta = _sem_analise_do_relogio(consulta)
        consulta = consulta.order_by("-atualizado_em", "-id")
        total = consulta.count()
        trabalhos = list(consulta[: LIMITE_DO_GRUPO.get(chave, LIMITE_POR_GRUPO)])
        por_trabalho: dict[int, list] = {t.pk: [] for t in trabalhos}
        if trabalhos:
            for decisao in (
                DecisaoComercial.objects.filter(trabalho_id__in=por_trabalho.keys())
                .select_related("consumo")
                .order_by("criada_em", "id")
            ):
                por_trabalho[decisao.trabalho_id].append(decisao)
        grupos.append(
            {
                "chave": chave,
                "nome": nome,
                "explica": EXPLICA_GRUPO[chave],
                "total": total,
                "itens": [_preparar_trabalho(t, por_trabalho[t.pk]) for t in trabalhos],
            }
        )
    return grupos


def _estrategias() -> list[dict]:
    _, DecisaoComercial, EstrategiaComercial = _modelos()
    from apps.comercial import papeis

    usos = dict(
        DecisaoComercial.objects.filter(estrategia__isnull=False)
        .values_list("estrategia_id")
        .annotate(n=Count("id"))
    )
    lista = []
    for papel, nome in EstrategiaComercial.Papel.choices:
        ativa = papeis.estrategia_ativa(papel)
        versoes = list(EstrategiaComercial.objects.filter(papel=papel).order_by("-versao"))
        for v in versoes:
            v.usos = usos.get(v.pk, 0)
            v.marcas = list(reversed(v.historico or []))
        anterior = ativa.anterior if ativa.anterior_id and ativa.anterior_id != ativa.pk else None
        lista.append(
            {
                "papel": papel,
                "nome": nome,
                "ativa": ativa,
                "anterior": anterior,
                "versoes": versoes,
                "propostas": [v for v in versoes if v.situacao == "proposta"],
                "ferramentas": papeis.FERRAMENTAS_DO_PAPEL.get(papel, ()),
            }
        )
    return lista


def _numero_do_trabalho(bruto) -> int | None:
    """O `?trabalho=` da tela: só dígitos ASCII, até 12. Qualquer outra coisa
    (letras, sinal, dígitos de outro alfabeto, texto enorme) é ignorada."""
    s = bruto if isinstance(bruto, str) else ""
    if s.isascii() and s.isdigit() and len(s) <= 12:
        return int(s)
    return None


def _detalhe(trabalho_id: str):
    """Um trabalho com todas as decisões, na ordem em que aconteceram."""
    numero = _numero_do_trabalho(trabalho_id)
    if numero is None:
        return None
    TrabalhoComercial, DecisaoComercial, _ = _modelos()
    trabalho = TrabalhoComercial.objects.filter(pk=numero).first()
    if trabalho is None:
        return None
    decisoes = list(
        DecisaoComercial.objects.filter(trabalho=trabalho).select_related("consumo").order_by("criada_em", "id")
    )
    preparado = _preparar_trabalho(trabalho, decisoes)
    preparado["todas"] = [
        {
            "obj": d,
            "resultado": d.get_resultado_display(),
            "contexto": contexto_resumido(d.contexto_usado),
            "entrada": contexto_resumido(d.entrada),
            "saida": _curto(d.saida, 600) if d.saida else "",
        }
        for d in decisoes
    ]
    return preparado


def _ligado() -> bool:
    from apps.comercial import coordenador

    return coordenador.ligado()


def _min_amostra() -> int:
    from apps.comercial import resultados

    return resultados.MIN_AMOSTRA


def _comparacao_na_tela() -> dict:
    from apps.comercial import comparacao

    marcas = comparacao.MarcaDeComparacao.objects.filter(teste=False)
    return {
        "percentual": comparacao.percentual(),
        "maximo": comparacao.PERCENTUAL_MAXIMO,
        "sem_agente": marcas.filter(grupo=comparacao.GRUPO_COMPARACAO).count(),
        "com_agente": marcas.filter(grupo=comparacao.GRUPO_AGENTE).count(),
    }


@require_GET
def crm_agentes(request):
    mostrar_testes = request.GET.get("testes") == "mostrar"
    contexto = {
        "admin": getattr(request, "admin", None),
        "disponivel": False,
        "mostrar_testes": mostrar_testes,
        "recado": RECADOS.get(request.GET.get("recado", ""), ""),
    }
    if not comercial_disponivel():
        return render(request, "admin/crm_agentes.html", contexto)
    try:
        TrabalhoComercial, _, _ = _modelos()
        inicio = _inicio_do_mes()
        gasto_comercial = (
            TrabalhoComercial.objects.filter(criado_em__gte=inicio).aggregate(s=Sum("custo_usd"))["s"]
            or Decimal("0")
        )
        contexto.update(
            disponivel=True,
            grupos=_grupos(mostrar_testes),
            gasto=_limite_do_mes(gasto_comercial),
            concluidos_no_mes=_sem_analise_do_relogio(
                TrabalhoComercial.objects.filter(criado_em__gte=inicio, estado="concluido", teste=False)
            ).count(),
            testes_ocultos=0 if mostrar_testes else TrabalhoComercial.objects.filter(teste=True).count(),
            estrategias=_estrategias(),
            comparacao=_comparacao_na_tela(),
            detalhe=_detalhe(request.GET.get("trabalho", "")),
            ligado=_ligado(),
            min_amostra=_min_amostra(),
        )
    except (DatabaseError, ImportError, LookupError):
        logger.exception("Não foi possível ler os registros dos agentes do CRM")
        contexto["disponivel"] = False
        contexto["falha_de_leitura"] = True
    return render(request, "admin/crm_agentes.html", contexto)


def _volta(recado: str, ancora: str = "estrategias"):
    return HttpResponseRedirect(f"{reverse('crm_agentes')}?recado={recado}#{ancora}")


@require_POST
def crm_agentes_ativar(request, estrategia_id: int):
    if not comercial_disponivel():
        return _volta("indisponivel")
    _, _, EstrategiaComercial = _modelos()
    from apps.comercial import papeis

    estrategia = EstrategiaComercial.objects.filter(pk=estrategia_id).first()
    if estrategia is None:
        return _volta("nao_encontrada")
    motivo = (request.POST.get("motivo") or "").strip()[:1000]
    papeis.ativar(estrategia, _quem(request), motivo or f"ativada no painel (v{estrategia.versao})")
    _auditar(request, f"estrategia:{estrategia.papel}:v{estrategia.versao}", "CRM agentes: ativar versão")
    return _volta("ativada", f"papel-{estrategia.papel}")


@require_POST
def crm_agentes_voltar(request, papel: str):
    if not comercial_disponivel():
        return _volta("indisponivel")
    _, _, EstrategiaComercial = _modelos()
    from apps.comercial import papeis

    if papel not in EstrategiaComercial.Papel.values:
        return _volta("papel")
    motivo = (request.POST.get("motivo") or "").strip()[:1000]
    esperada = request.POST.get("versao_no_ar", "")
    try:
        voltou = papeis.voltar_a_anterior(
            papel,
            _quem(request),
            motivo,
            versao_esperada=int(esperada) if esperada.isascii() and esperada.isdigit() and len(esperada) <= 9 else None,
        )
    except papeis.VersaoMudou:
        return _volta("mudou", f"papel-{papel}")
    if voltou is None:
        return _volta("sem_anterior", f"papel-{papel}")
    _auditar(request, f"estrategia:{papel}:v{voltou.versao}", "CRM agentes: voltar à versão anterior")
    return _volta("voltou", f"papel-{papel}")


@require_POST
def crm_agentes_nova(request, papel: str):
    if not comercial_disponivel():
        return _volta("indisponivel")
    _, _, EstrategiaComercial = _modelos()
    from apps.comercial import papeis

    if papel not in EstrategiaComercial.Papel.values:
        return _volta("papel")
    instrucoes = (request.POST.get("instrucoes") or "").strip()
    if not instrucoes:
        return _volta("vazia", f"papel-{papel}")
    motivo = (request.POST.get("motivo") or "").strip()[:4000] or "escrita no painel"
    quem = _quem(request)
    nova = papeis.propor_versao(papel, instrucoes, criada_por=quem, motivo=motivo, origem="painel")
    pos_no_ar = request.POST.get("ativar") == "1"
    if pos_no_ar:
        papeis.ativar(nova, quem, motivo)
    _auditar(request, f"estrategia:{papel}:v{nova.versao}", "CRM agentes: nova versão" + (" ativada" if pos_no_ar else ""))
    return _volta("nova_ativa" if pos_no_ar else "nova", f"papel-{papel}")


@require_POST
def crm_agentes_analisar(request):
    """"Analisar agora": põe na fila UMA análise de resultados por dia.

    Usa o tipo que já existe para isso (`analisar_resultados`, o mesmo que o
    relógio põe a cada hora); a chave é estável por dia, então apertar de
    novo no mesmo dia devolve o mesmo trabalho e não cria outro. Se ainda não
    houver o mínimo de abordagens para comparar, o próprio trabalho conclui
    como inconclusivo sem chamar o modelo (sem gasto)."""
    if not comercial_disponivel():
        return _volta("indisponivel", "trabalhos")
    from apps.comercial import coordenador

    if not coordenador.ligado():
        return _volta("analise_desligada", "trabalhos")
    hoje = timezone.localdate()
    trabalho, criado = coordenador.criar(
        coordenador.T.ANALISAR_RESULTADOS, f"resultados:painel:{hoje:%Y%m%d}", origem="painel"
    )
    _auditar(
        request,
        f"trabalho_comercial:{trabalho.pk}",
        "CRM agentes: analisar agora" + ("" if criado else " (já pedida hoje)"),
    )
    return _volta("analise_pedida" if criado else "analise_ja_pedida", "trabalhos")


@require_POST
def crm_agentes_retomar(request, trabalho_id: int):
    """Devolve à fila um trabalho que falhou ou esperava. Envio sem confirmação
    volta com a mesma chave de idempotência: a mensagem não sai duas vezes."""
    if not comercial_disponivel():
        return _volta("indisponivel", "trabalhos")
    TrabalhoComercial, _, _ = _modelos()
    from apps.comercial import coordenador

    trabalho = TrabalhoComercial.objects.filter(pk=trabalho_id).first()
    if trabalho is None:
        return _volta("nao_retomado", "trabalhos")
    if not coordenador.retomar(trabalho, _quem(request)):
        return _volta("nao_retomado", "trabalhos")
    _auditar(request, f"trabalho_comercial:{trabalho.pk}", f"CRM agentes: retomar ({trabalho.estado})")
    return _volta("retomado", "trabalhos")


@require_POST
def crm_agentes_comparacao(request):
    """Muda o percentual de leads novos que ficam sem o agente (o grupo de comparação).

    Pede confirmação, só vale para leads que chegarem depois (quem já foi marcado não
    muda de grupo) e deixa rastro na auditoria. O padrão é 0: nada muda até a pessoa escolher."""
    if not comercial_disponivel():
        return _volta("indisponivel", "comparacao")
    from apps.comercial import comparacao

    bruto = (request.POST.get("percentual") or "").strip()
    if not (bruto.isascii() and bruto.isdigit() and len(bruto) <= 3) or int(bruto) > comparacao.PERCENTUAL_MAXIMO:
        return _volta("comparacao_invalida", "comparacao")
    if request.POST.get("confirmo") != "1":
        return _volta("comparacao_sem_confirmacao", "comparacao")
    antes, depois = comparacao.definir_percentual(int(bruto), _quem(request))
    if antes == depois:
        return _volta("comparacao_igual", "comparacao")
    _auditar(
        request,
        "grupo-de-comparacao",
        f"CRM agentes: grupo de comparação de {antes}% para {depois}% dos leads novos sem o agente",
    )
    return _volta("comparacao_mudou", "comparacao")
