"""Ficha individual de leitura para o bastidor administrativo."""

from django.db.models import Max

from .jornada import situacao
from .models import (
    AvaliacaoDaJornada, AvaliacaoSandboxProjetada, Concessao,
    LancamentoDeXP, PerfilJogador,
)
from .recursos import disponiveis


def _iso(valor):
    return valor.isoformat() if valor else None


def _origens_sandbox(pessoa_id, site_id, avaliacoes):
    """Liga reconhecimento imutável à entrega sem inferir a versão ausente."""
    if not avaliacoes:
        return
    projetadas = list(AvaliacaoSandboxProjetada.objects.filter(
        pessoa_id=pessoa_id, site_id=site_id,
    ).only(
        "trabalho_id", "entrega_id", "analise_id", "versao", "reconhecida_em",
        "reconhecida_versao", "reconhecida_entrega_id", "reconhecida_analise_id",
    ))
    por_trabalho = {linha.trabalho_id: linha for linha in projetadas}
    origens = {}
    for avaliacao in AvaliacaoDaJornada.objects.filter(
        pessoa_id=pessoa_id, site_id=site_id, ordem=5,
        caminho="freelancer", resultado="reconhecida",
    ).order_by("criada_em", "pk").only("evidencia", "criada_em"):
        evidencia = avaliacao.evidencia or {}
        trabalho_id = str(evidencia.get("trabalho_id") or "")
        entrega_id = str(evidencia.get("entrega_id") or "")
        analise_id = str(evidencia.get("analise_id") or "")
        if not all((trabalho_id, entrega_id, analise_id)) or trabalho_id in origens:
            continue
        projetada = por_trabalho.get(trabalho_id)
        versao = None
        if projetada:
            if (projetada.entrega_id, projetada.analise_id) == (entrega_id, analise_id):
                versao = projetada.versao
            elif (projetada.reconhecida_entrega_id, projetada.reconhecida_analise_id) == (entrega_id, analise_id):
                versao = projetada.reconhecida_versao
        origens[trabalho_id] = {
            "tipo": "avaliacao_jornada", "entrega_id": entrega_id,
            "analise_id": analise_id, "versao": versao,
            "reconhecida_em": _iso(avaliacao.criada_em),
        }
    for item in avaliacoes:
        trabalho_id = item["trabalho_id"]
        origem = origens.get(trabalho_id)
        projetada = por_trabalho.get(trabalho_id)
        if origem is None and projetada and projetada.reconhecida_em:
            origem = {
                "tipo": "avaliacao_sandbox_anterior",
                "entrega_id": projetada.reconhecida_entrega_id,
                "analise_id": projetada.reconhecida_analise_id,
                "versao": projetada.reconhecida_versao,
                "reconhecida_em": _iso(projetada.reconhecida_em),
            }
        item["reconhecimento"] = {**item["reconhecimento"], "origem": origem}


def _origem_da_faixa(pessoa_id, site_id, atual, caminho):
    if atual["ordem"] == 1:
        return {"tipo": "faixa_inicial"}
    quando = atual["alcancada_em"]
    avaliacao = AvaliacaoDaJornada.objects.filter(
        pessoa_id=pessoa_id, site_id=site_id, ordem=atual["ordem"],
        resultado="reconhecida", criada_em=quando,
        caminho__in=["comum", caminho] if caminho else ["comum"],
    ).only("caminho", "criada_em", "evidencia").first()
    if avaliacao is None:
        return {"tipo": "historico_preservado"}
    evidencia = avaliacao.evidencia or {}
    return {
        "tipo": "avaliacao_jornada", "caminho": avaliacao.caminho,
        "avaliada_em": _iso(avaliacao.criada_em),
        "entrega_id": str(evidencia.get("entrega_id")) if evidencia.get("entrega_id") else None,
        "analise_id": str(evidencia.get("analise_id")) if evidencia.get("analise_id") else None,
    }


def resumir_aluno(pessoa_id, site_id):
    """Só consultas da pessoa e do site solicitados; nenhuma escrita."""
    perfil = PerfilJogador.objects.filter(
        pessoa_id=pessoa_id, site_id=site_id,
    ).only("pessoa_id", "xp_total", "nivel").first()
    if perfil is None:
        dados_perfil = None
    else:
        ultima = LancamentoDeXP.objects.filter(
            pessoa_id=pessoa_id, site_id=site_id,
            status=LancamentoDeXP.Status.DEFINITIVO,
        ).aggregate(ultima=Max("occurred_at"))["ultima"]
        concessoes = disponiveis(Concessao.objects.filter(
            pessoa_id=pessoa_id, site_id=site_id, conquista__site_id=site_id,
        ), "conquista__").exclude(estado=Concessao.Estado.REVOGADA).select_related(
            "conquista",
        ).order_by("-concedida_em")
        dados_perfil = {
            "pessoa_id": pessoa_id, "xp": perfil.xp_total, "nivel": perfil.nivel,
            "ultima_atividade_em": _iso(ultima),
            "conquistas": [{
                "slug": linha.conquista.slug, "nome": linha.conquista.nome,
                "concedida_em": _iso(linha.concedida_em),
            } for linha in concessoes],
        }

    jornada = situacao(pessoa_id, site_id)
    atual = jornada["atual"]
    avaliacoes = jornada["sandbox_avaliacoes"]
    _origens_sandbox(pessoa_id, site_id, avaliacoes)
    return {
        "fonte": "gamificacao", "site_id": site_id, "pessoa_id": pessoa_id,
        "perfil": dados_perfil,
        "faixa": {
            "atual": {
                "ordem": atual["ordem"], "nome": atual["nome"],
                "cores": atual["cores"], "conquista": atual["conquista"],
                "alcancada_em": _iso(atual["alcancada_em"]),
            },
            "alcancadas": sum(1 for passo in jornada["lista"] if passo["alcancada"]),
            "origem": _origem_da_faixa(pessoa_id, site_id, atual, jornada["caminho"]),
        },
        "sandbox": {
            "fonte": "gamificacao", "site_id": site_id,
            "pessoa_id": pessoa_id, "avaliacoes": avaliacoes,
        },
    }
