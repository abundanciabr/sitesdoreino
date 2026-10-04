"""A análise de resultados: os números por versão de estratégia e o otimizador.

Roda de hora em hora (`coordenador.manutencao`). Os números saem dos
registros desta célula — trabalhos, decisões e os eventos de pagamento
aprovado — e deixam de fora os registros de teste.

* Com pouca amostra (menos de `MIN_AMOSTRA` abordagens na versão) o resultado
  é **inconclusivo** e o modelo nem é chamado: uma venda num grupo pequeno não
  demonstra que uma abordagem ganhou.
* Sem novidade desde a última análise, o modelo também não é chamado.
* Com amostra, o modelo forte lê os números e pode PROPOR uma versão nova das
  instruções de um papel. A proposta fica guardada; quem põe no ar é a página
  dos agentes (`ativar`) — e `voltar_a_anterior` desfaz.
* Duas versões com amostra e a ativa pior de forma clara (teste de duas
  proporções, z < -1,96 nas vendas por abordagem): a anterior volta sozinha.
"""

from __future__ import annotations

import json
import math
from decimal import Decimal

from django.db.models import Sum

from . import papeis
from .models import DecisaoComercial, EstrategiaComercial, EventoComercial, TrabalhoComercial

MIN_AMOSTRA = 30
Z_CRITICO = -1.96

E = TrabalhoComercial.Estado
T = TrabalhoComercial.Tipo
P = EstrategiaComercial.Papel


def numeros() -> dict:
    """Abordagens, respostas, vendas e custo por versão da estratégia de
    abordagem. Só oportunidades reais (sem teste)."""
    envios = (
        DecisaoComercial.objects.filter(
            ferramenta="enviar_mensagem",
            resultado=DecisaoComercial.Resultado.FEITO,
            trabalho__tipo=T.ABORDAR,
            trabalho__teste=False,
        )
        .filter(saida__ja_feito__isnull=True)  # a repetição ("ja_feito") não conta como abordagem
        .select_related("trabalho")
        .order_by("criada_em")
    )
    vendidas = set(
        EventoComercial.objects.filter(nome="pagamento.aprovado").exclude(oportunidade_ref="")
        .values_list("oportunidade_ref", flat=True)
    )
    por_versao: dict[int, dict] = {}
    vistas: set[tuple[int, str]] = set()
    for envio in envios:
        trabalho = envio.trabalho
        chave = trabalho.oportunidade_id or trabalho.chave_da_conversa
        versao = envio.versao_estrategia or 0
        if (versao, chave) in vistas:
            continue
        vistas.add((versao, chave))
        linha = por_versao.setdefault(versao, {
            "versao": versao, "abordagens": 0, "respostas": 0, "vendas": 0, "custo_usd": Decimal("0")})
        linha["abordagens"] += 1
        respondeu = TrabalhoComercial.objects.filter(
            tipo=T.ATENDER_MENSAGEM, teste=False, criado_em__gt=envio.criada_em,
        ).filter(
            **({"contato_id": trabalho.contato_id} if trabalho.contato_id else {"conversa_id": trabalho.conversa_id or "-"})
        ).exists()
        if respondeu:
            linha["respostas"] += 1
        if trabalho.oportunidade_id and trabalho.oportunidade_id in vendidas:
            linha["vendas"] += 1
        linha["custo_usd"] += trabalho.custo_usd or 0
    custo_total = TrabalhoComercial.objects.filter(teste=False).aggregate(s=Sum("custo_usd"))["s"] or 0
    return {
        "papel": P.ABORDAGEM,
        "versoes": [
            {**linha, "custo_usd": str(linha["custo_usd"])}
            for _, linha in sorted(por_versao.items())
        ],
        "custo_total_usd": str(custo_total),
        "min_amostra": MIN_AMOSTRA,
    }


def z_de_duas_proporcoes(sucessos_a: int, n_a: int, sucessos_b: int, n_b: int) -> float | None:
    """z de (a - b). None quando não há como comparar."""
    if not n_a or not n_b:
        return None
    total = (sucessos_a + sucessos_b) / (n_a + n_b)
    erro = math.sqrt(total * (1 - total) * (1 / n_a + 1 / n_b))
    if erro == 0:
        return None
    return (sucessos_a / n_a - sucessos_b / n_b) / erro


def _volta_se_piorou(dados: dict) -> dict | None:
    ativa = papeis.estrategia_ativa(P.ABORDAGEM)
    anterior = ativa.anterior
    if anterior is None:
        return None
    linhas = {linha["versao"]: linha for linha in dados["versoes"]}
    a, b = linhas.get(ativa.versao), linhas.get(anterior.versao)
    if not a or not b or a["abordagens"] < MIN_AMOSTRA or b["abordagens"] < MIN_AMOSTRA:
        return None
    z = z_de_duas_proporcoes(a["vendas"], a["abordagens"], b["vendas"], b["abordagens"])
    if z is None or z >= Z_CRITICO:
        return None
    papeis.voltar_a_anterior(
        P.ABORDAGEM, "otimizador",
        f"A v{ativa.versao} vendeu menos que a v{anterior.versao} com amostra suficiente (z={z:.2f}).",
    )
    return {"voltou_de": ativa.versao, "voltou_para": anterior.versao, "z": round(z, 3)}


def executar(trabalho: TrabalhoComercial) -> None:
    from .coordenador import conversar, terminar

    dados = numeros()
    maior = max((linha["abordagens"] for linha in dados["versoes"]), default=0)
    trabalho.resultado = {**(trabalho.resultado or {}), "numeros": dados}
    if maior < MIN_AMOSTRA:
        trabalho.resultado["conclusao"] = "inconclusivo"
        terminar(trabalho, E.CONCLUIDO, resumo=(
            f"Inconclusivo: a maior amostra tem {maior} abordagem(ns); são precisas {MIN_AMOSTRA}. "
            "O modelo não foi chamado."))
        return
    volta = _volta_se_piorou(dados)
    if volta:
        trabalho.resultado["voltou"] = volta
    ultima = (
        TrabalhoComercial.objects.filter(tipo=T.ANALISAR_RESULTADOS, estado=E.CONCLUIDO)
        .exclude(pk=trabalho.pk).order_by("-terminado_em").first()
    )
    if ultima is not None and (ultima.resultado or {}).get("numeros") == dados and not volta:
        trabalho.resultado["conclusao"] = "sem_novidade"
        terminar(trabalho, E.CONCLUIDO, resumo="Sem novidade desde a última análise; o modelo não foi chamado.")
        return
    ativas = {
        papel: papeis.estrategia_ativa(papel).versao for papel in (P.ANALISTA, P.ABORDAGEM, P.ATENDIMENTO)
    }
    final = conversar(trabalho, (
        "Números consolidados por versão da estratégia de abordagem (só vendas confirmadas pelo provedor; "
        "registros de teste fora):\n" + json.dumps(dados, ensure_ascii=False)
        + f"\nVersões ativas: {json.dumps(ativas)}.\nInstruções atuais da abordagem:\n"
        + papeis.estrategia_ativa(P.ABORDAGEM).instrucoes
    ), forte=True)
    trabalho.resultado["decisao"] = final
    trabalho.resultado["conclusao"] = final.get("conclusao") or "manter"
    proposta = None
    if final.get("conclusao") == "proposta" and final.get("papel") and (final.get("instrucoes_propostas") or "").strip():
        proposta = papeis.propor_versao(
            final["papel"], final["instrucoes_propostas"],
            criada_por="agente:resultados", origem="otimizador",
            motivo=str(final.get("motivo") or "")[:4000],
            evidencias={"numeros": dados, "evidencias": final.get("evidencias") or []},
        )
        trabalho.resultado["proposta"] = {"papel": proposta.papel, "versao": proposta.versao, "id": proposta.pk}
    terminar(trabalho, E.CONCLUIDO, resumo=(
        f"Proposta a v{proposta.versao} de {proposta.get_papel_display()}." if proposta
        else f"Conclusão: {trabalho.resultado['conclusao']}."))
