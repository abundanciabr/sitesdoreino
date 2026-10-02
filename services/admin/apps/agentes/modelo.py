"""A chamada ao modelo da OpenAI (Responses API), com o teto de gasto na frente.

Plano-mestre §12.1: GPT-6 Luna nas etapas curtas (a conversa), GPT-6 Sol no
que pede planejamento e várias fontes (o panorama). Os nomes ficam na
`Conexao`, conferidos na conta por `conferir_conexao()` — que usa a lista de
modelos, chamada que não cobra.

## O teto antes da chamada

Toda chamada paga RESERVA o pior caso antes de sair (`Consumo` marcado
`desconhecido`, com o máximo de saída cobrado) e, na volta, acerta a reserva
pelo uso real. A reserva é feita com a linha da autorização travada, então
dois trabalhadores ao mesmo tempo não passam juntos do teto. Se o processo cai
no meio, a reserva fica: gasto que talvez tenha acontecido continua contando.

## A chave

Lida na hora da chamada: `OPENAI_API_KEY` do ambiente, ou a da `Conexao`
(cifrada, `segredo.py`). Nunca entra no prompt, no log nem na mensagem de erro.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, time
from decimal import Decimal

import httpx
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from . import segredo
from .models import AutorizacaoDeGasto, Conexao, Consumo

log = logging.getLogger(__name__)

URL = "https://api.openai.com/v1"
ESPERA_SEGUNDOS = 120

# Dólar por milhão de tokens: entrada, entrada em cache, saída. Conferido na
# documentação da OpenAI em 01/10/2026. Modelo desconhecido é cobrado como o
# mais caro, para o teto errar para o lado seguro.
PRECOS = {
    "gpt-6-luna": (Decimal("0.10"), Decimal("0.01"), Decimal("0.50")),
    "gpt-6-sol": (Decimal("2.00"), Decimal("0.20"), Decimal("10.00")),
}
PRECO_DESCONHECIDO = PRECOS["gpt-6-sol"]
MILHAO = Decimal(1_000_000)


class ProblemaDoModelo(Exception):
    """Algo impediu a chamada. `situacao` é para onde a execução vai."""

    situacao = "falhou"
    frase = "O modelo não respondeu."

    def __init__(self, frase: str = ""):
        super().__init__(frase or self.frase)
        self.frase = frase or self.frase


class SemChave(ProblemaDoModelo):
    situacao = "aguardando_dependencia"
    frase = (
        "O robô ainda não tem a chave da OpenAI. Quando o administrador "
        "guardar a chave em Robôs > Conexão, este trabalho continua sozinho."
    )


class ChaveRecusada(ProblemaDoModelo):
    situacao = "aguardando_dependencia"
    frase = (
        "A OpenAI recusou a chave guardada. Quando o administrador guardar "
        "uma chave válida, este trabalho continua sozinho."
    )


class SemSaldo(ProblemaDoModelo):
    situacao = "aguardando_dependencia"
    frase = (
        "A conta da OpenAI recusou por saldo ou limite da própria conta. "
        "Quando houver saldo, o administrador confere a conexão e este "
        "trabalho continua."
    )


class ModeloIndisponivel(ProblemaDoModelo):
    situacao = "aguardando_dependencia"
    frase = "O modelo pedido não está disponível nesta conta da OpenAI."


class SemAutorizacao(ProblemaDoModelo):
    situacao = "aguardando_autorizacao"
    frase = "Não há autorização de gasto com modelos ativa. Nada pago foi chamado."


class TetoDeGasto(ProblemaDoModelo):
    situacao = "aguardando_autorizacao"
    frase = (
        "O gasto do mês com modelos chegou ao teto autorizado. O robô parou "
        "antes de gastar mais; volta no mês que vem ou com um teto novo."
    )


class Temporario(ProblemaDoModelo):
    situacao = "na_fila"
    frase = "A OpenAI não respondeu agora. O robô tenta de novo em instantes."


class PedidoRecusado(ProblemaDoModelo):
    situacao = "falhou"
    frase = "A OpenAI recusou o pedido."


def conexao() -> Conexao:
    return Conexao.objects.get_or_create(provedor="openai")[0]


def chave() -> str | None:
    do_ambiente = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if do_ambiente:
        return do_ambiente
    return segredo.decifrar(conexao().segredo_cifrado)


def tem_chave() -> bool:
    return bool(chave())


def precos(modelo: str):
    for nome, valores in PRECOS.items():
        if modelo == nome or modelo.startswith(nome + "-"):
            return valores
    return PRECO_DESCONHECIDO


def custo(modelo: str, entrada: int, em_cache: int, saida: int) -> Decimal:
    p_entrada, p_cache, p_saida = precos(modelo)
    cheia = max(entrada - em_cache, 0)
    valor = (cheia * p_entrada + em_cache * p_cache + saida * p_saida) / MILHAO
    return valor.quantize(Decimal("0.000001"))


def inicio_do_mes() -> datetime:
    hoje = timezone.localdate()
    return timezone.make_aware(datetime.combine(hoje.replace(day=1), time.min))


def gasto_do_mes() -> Decimal:
    total = Consumo.objects.filter(criado_em__gte=inicio_do_mes()).aggregate(
        s=Sum("custo_estimado_usd")
    )["s"]
    return total or Decimal("0")


def autorizacao_ativa() -> AutorizacaoDeGasto | None:
    return AutorizacaoDeGasto.objects.filter(ativa=True).first()


@dataclass
class Resposta:
    id: str
    itens: list
    texto: str
    chamadas: list
    completa: bool
    consumo: Consumo


def _reservar(modelo: str, corpo: dict, max_saida: int, *, execucao, robo) -> Consumo:
    entrada_estimada = len(json.dumps(corpo, ensure_ascii=False)) // 3 + 500
    pior_caso = custo(modelo, entrada_estimada, 0, max_saida)
    with transaction.atomic():
        autorizacao = (
            AutorizacaoDeGasto.objects.select_for_update().filter(ativa=True).first()
        )
        if autorizacao is None:
            raise SemAutorizacao()
        if gasto_do_mes() + pior_caso > autorizacao.teto_mensal_usd:
            raise TetoDeGasto()
        return Consumo.objects.create(
            execucao=execucao,
            robo=robo,
            autorizacao=autorizacao,
            modelo=modelo,
            tokens_entrada=entrada_estimada,
            tokens_saida=max_saida,
            custo_estimado_usd=pior_caso,
            desconhecido=True,
        )


def _erro_da_api(resposta: httpx.Response) -> tuple[str, str]:
    try:
        erro = resposta.json().get("error") or {}
    except ValueError:
        erro = {}
    return str(erro.get("code") or erro.get("type") or ""), str(erro.get("message") or "")[:300]


# Modelos que recusaram a escolha do esforço de raciocínio: o processo
# lembra e não manda mais para eles.
_SEM_ESFORCO: set[str] = set()


def _recusou_o_esforco(mensagem: str) -> bool:
    mensagem = mensagem.lower()
    return "reasoning" in mensagem or "effort" in mensagem


def responder(
    *,
    modelo: str,
    instrucoes: str,
    itens: list,
    ferramentas: list | None = None,
    max_saida: int = 2000,
    esforco: str | None = None,
    execucao=None,
    robo=None,
) -> Resposta:
    """Uma rodada da Responses API. Não guarda nada na OpenAI (`store`
    falso): o histórico mora aqui, e a retomada reenvia os itens."""
    segredo_da_conta = chave()
    if not segredo_da_conta:
        raise SemChave()
    corpo = {
        "model": modelo,
        "instructions": instrucoes,
        "input": itens,
        "store": False,
        "include": ["reasoning.encrypted_content"],
        "max_output_tokens": max_saida,
    }
    if ferramentas:
        corpo["tools"] = ferramentas
        corpo["parallel_tool_calls"] = False
    if esforco and modelo not in _SEM_ESFORCO:
        corpo["reasoning"] = {"effort": esforco}
    reserva = _reservar(modelo, corpo, max_saida, execucao=execucao, robo=robo)
    try:
        resposta = httpx.post(
            f"{URL}/responses",
            json=corpo,
            headers={"Authorization": f"Bearer {segredo_da_conta}"},
            timeout=ESPERA_SEGUNDOS,
        )
    except httpx.ConnectError:
        # Não conectou: o pedido não saiu, não houve cobrança.
        reserva.delete()
        raise Temporario()
    except httpx.HTTPError:
        # Saiu e não voltou: resultado desconhecido. A reserva fica como está.
        log.warning("Chamada ao modelo %s sem resposta; reserva mantida", modelo)
        raise Temporario(
            "A OpenAI não respondeu a tempo. O gasto possível ficou anotado e o "
            "robô tenta de novo."
        )

    if resposta.status_code >= 400:
        reserva.delete()
        codigo, mensagem = _erro_da_api(resposta)
        if resposta.status_code == 400 and "reasoning" in corpo and _recusou_o_esforco(mensagem):
            # O modelo não deixa escolher o esforço: pede de novo sem ele.
            _SEM_ESFORCO.add(modelo)
            return responder(
                modelo=modelo,
                instrucoes=instrucoes,
                itens=itens,
                ferramentas=ferramentas,
                max_saida=max_saida,
                execucao=execucao,
                robo=robo,
            )
        if resposta.status_code == 429 and codigo != "insufficient_quota":
            raise Temporario()
        if resposta.status_code >= 500:
            raise Temporario()
        if resposta.status_code == 401:
            problema = ChaveRecusada()
        elif resposta.status_code == 429:
            problema = SemSaldo()
        elif resposta.status_code in (403, 404) or codigo == "model_not_found":
            problema = ModeloIndisponivel(
                f"O modelo {modelo} não está disponível nesta conta da OpenAI."
            )
        else:
            raise PedidoRecusado(f"A OpenAI recusou o pedido: {mensagem or codigo}")
        # A conexão deixa de valer até o administrador conferir de novo: é o
        # que impede o servidor de retomar e bater na mesma recusa sem fim.
        Conexao.objects.filter(provedor="openai").update(
            situacao=(
                Conexao.Situacao.RECUSADA
                if isinstance(problema, ChaveRecusada)
                else Conexao.Situacao.FALHOU
            ),
            detalhe=problema.frase,
        )
        raise problema

    dados = resposta.json()
    uso = dados.get("usage") or {}
    entrada = int(uso.get("input_tokens") or 0)
    em_cache = int((uso.get("input_tokens_details") or {}).get("cached_tokens") or 0)
    saida = int(uso.get("output_tokens") or 0)
    reserva.tokens_entrada = entrada
    reserva.tokens_entrada_em_cache = em_cache
    reserva.tokens_saida = saida
    reserva.custo_estimado_usd = custo(modelo, entrada, em_cache, saida)
    reserva.resposta_id = str(dados.get("id") or "")[:120]
    reserva.desconhecido = False
    reserva.save()

    itens_de_saida = list(dados.get("output") or [])
    textos, chamadas = [], []
    for item in itens_de_saida:
        if item.get("type") == "message":
            for parte in item.get("content") or []:
                if parte.get("type") == "output_text":
                    textos.append(parte.get("text") or "")
        elif item.get("type") == "function_call":
            chamadas.append(item)
    return Resposta(
        id=reserva.resposta_id,
        itens=itens_de_saida,
        texto="\n".join(t for t in textos if t).strip(),
        chamadas=chamadas,
        completa=dados.get("status", "completed") == "completed",
        consumo=reserva,
    )


def conferir_conexao(quem: str = "") -> Conexao:
    """Confere a chave na conta pela lista de modelos (não cobra) e guarda o
    que a conta tem de GPT-6."""
    atual = conexao()
    segredo_da_conta = chave()
    if not segredo_da_conta:
        atual.situacao = Conexao.Situacao.SEM_CHAVE
        atual.detalhe = "Nenhuma chave guardada."
        atual.save()
        return atual
    try:
        resposta = httpx.get(
            f"{URL}/models",
            headers={"Authorization": f"Bearer {segredo_da_conta}"},
            timeout=30,
        )
    except httpx.HTTPError:
        atual.situacao = Conexao.Situacao.FALHOU
        atual.detalhe = "A OpenAI não respondeu agora. Tente conferir de novo."
        atual.save()
        return atual
    if resposta.status_code == 401:
        atual.situacao = Conexao.Situacao.RECUSADA
        atual.detalhe = "A OpenAI recusou esta chave."
        atual.save()
        return atual
    if resposta.status_code >= 400:
        _, mensagem = _erro_da_api(resposta)
        atual.situacao = Conexao.Situacao.FALHOU
        atual.detalhe = f"A OpenAI respondeu {resposta.status_code}. {mensagem}".strip()
        atual.save()
        return atual
    nomes = sorted(
        str(m.get("id")) for m in (resposta.json().get("data") or []) if m.get("id")
    )
    gpt6 = [n for n in nomes if n.startswith("gpt-6")]
    atual.modelos_disponiveis = gpt6[:60]
    faltando = [m for m in (atual.modelo_rapido, atual.modelo_forte) if m not in nomes]
    if faltando:
        atual.situacao = Conexao.Situacao.FALHOU
        atual.detalhe = (
            "A chave funciona, mas esta conta não tem: " + ", ".join(faltando) + "."
        )
    else:
        atual.situacao = Conexao.Situacao.CONFERIDA
        atual.detalhe = (
            f"Chave aceita. {atual.modelo_rapido} e {atual.modelo_forte} "
            "disponíveis nesta conta."
        )
    atual.conferida_em = timezone.now()
    if quem:
        atual.alterada_por = quem[:200]
    atual.save()
    return atual
