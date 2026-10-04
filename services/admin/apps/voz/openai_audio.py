"""Transcrição e síntese de voz pela OpenAI, com o mesmo teto de gasto dos robôs.

- Transcrição: POST /v1/audio/transcriptions (multipart), modelo
  `gpt-4o-mini-transcribe` por padrão, com `logprobs` para achar o que o
  modelo ouviu com pouca certeza.
- Síntese: POST /v1/audio/speech, modelo `gpt-4o-mini-tts`, voz pronta da
  OpenAI (não é clone de ninguém), saída opus — o formato da nota de voz do
  WhatsApp.

A chave é a do executor (`apps.agentes.modelo.chave()`): nunca vai para log,
prompt ou mensagem de erro. Toda chamada paga reserva o pior caso no teto
(`agentes.Consumo`, origem "audio") ANTES de sair e acerta na volta.

Preços em dólar por minuto, conferidos na documentação da OpenAI; modelo
desconhecido é cobrado pelo mais caro, para o teto errar para o lado seguro.
"""
from __future__ import annotations

import logging
import math
import os
from dataclasses import dataclass, field
from decimal import Decimal

import httpx
from django.db import transaction

from apps.agentes import modelo as executor_modelo
from apps.agentes.models import AutorizacaoDeGasto, Conexao, Consumo

log = logging.getLogger(__name__)

PRECO_POR_MINUTO = {
    "gpt-4o-mini-transcribe": Decimal("0.003"),
    "gpt-4o-transcribe": Decimal("0.006"),
    "whisper-1": Decimal("0.006"),
    "gpt-4o-mini-tts": Decimal("0.015"),
    "tts-1": Decimal("0.015"),
}
PRECO_DESCONHECIDO = Decimal("0.030")
# Português falado: perto de 14 caracteres por segundo. Para reservar, conta
# como se a fala fosse mais lenta (pior caso).
CARACTERES_POR_SEGUNDO = 14
CARACTERES_POR_SEGUNDO_PIOR_CASO = 8
# Nota de voz em opus: ~1,5 KB por segundo. Sem a duração, o pior caso conta
# 1 KB por segundo.
BYTES_POR_SEGUNDO_PIOR_CASO = 1000
ESPERA_SEGUNDOS = 120


def modelo_de_transcricao() -> str:
    return (os.environ.get("OPENAI_MODELO_TRANSCRICAO") or "gpt-4o-mini-transcribe").strip()


def modelo_de_voz() -> str:
    return (os.environ.get("OPENAI_MODELO_VOZ") or "gpt-4o-mini-tts").strip()


def voz_padrao() -> str:
    return (os.environ.get("OPENAI_VOZ") or "coral").strip()


def preco_por_minuto(nome: str) -> Decimal:
    for chave, valor in PRECO_POR_MINUTO.items():
        if nome == chave or nome.startswith(chave + "-"):
            return valor
    return PRECO_DESCONHECIDO


def custo_por_segundos(nome: str, segundos: float) -> Decimal:
    minutos = Decimal(str(max(segundos, 1.0))) / Decimal(60)
    return (minutos * preco_por_minuto(nome)).quantize(Decimal("0.000001"))


def _reservar(nome: str, pior_caso: Decimal, autorizacao_id=None) -> Consumo:
    with transaction.atomic():
        autorizacoes = AutorizacaoDeGasto.objects.select_for_update().filter(ativa=True)
        autorizacao = (
            autorizacoes.filter(pk=autorizacao_id).first()
            if autorizacao_id is not None
            else autorizacoes.filter(destino="equipe").first()
        )
        if autorizacao is None:
            raise executor_modelo.SemAutorizacao()
        if executor_modelo.gasto_do_mes(autorizacao.pk) + pior_caso > autorizacao.teto_mensal_usd:
            raise executor_modelo.TetoDeGasto()
        return Consumo.objects.create(
            autorizacao=autorizacao, modelo=nome, origem="audio",
            custo_estimado_usd=pior_caso, desconhecido=True,
        )


def _problema(resposta: httpx.Response, nome: str) -> executor_modelo.ProblemaDoModelo:
    codigo, mensagem = executor_modelo._erro_da_api(resposta)
    if resposta.status_code == 429 and codigo != "insufficient_quota":
        return executor_modelo.Temporario()
    if resposta.status_code >= 500:
        return executor_modelo.Temporario()
    if resposta.status_code == 401:
        problema = executor_modelo.ChaveRecusada()
    elif resposta.status_code == 429:
        problema = executor_modelo.SemSaldo()
    elif resposta.status_code in (403, 404) or codigo == "model_not_found":
        problema = executor_modelo.ModeloIndisponivel(f"O modelo {nome} não está disponível nesta conta da OpenAI.")
    else:
        return executor_modelo.PedidoRecusado(f"A OpenAI recusou o pedido: {mensagem or codigo}")
    Conexao.objects.filter(provedor="openai").update(
        situacao=Conexao.Situacao.RECUSADA if isinstance(problema, executor_modelo.ChaveRecusada)
        else Conexao.Situacao.FALHOU,
        detalhe=problema.frase,
    )
    return problema


def _chamar(nome: str, pior_caso: Decimal, autorizacao_id, **pedido) -> tuple[httpx.Response, Consumo]:
    segredo = executor_modelo.chave()
    if not segredo:
        raise executor_modelo.SemChave()
    reserva = _reservar(nome, pior_caso, autorizacao_id)
    try:
        resposta = httpx.post(headers={"Authorization": f"Bearer {segredo}"}, timeout=ESPERA_SEGUNDOS, **pedido)
    except httpx.ConnectError:
        reserva.delete()
        raise executor_modelo.Temporario()
    except httpx.HTTPError:
        log.warning("Chamada de áudio %s sem resposta; reserva mantida", nome)
        raise executor_modelo.Temporario(
            "A OpenAI não respondeu a tempo. O gasto possível ficou anotado e o robô tenta de novo."
        )
    if resposta.status_code >= 400:
        reserva.delete()
        raise _problema(resposta, nome)
    return resposta, reserva


def _acertar(reserva: Consumo, custo: Decimal, resposta_id: str = "") -> None:
    reserva.custo_estimado_usd = custo
    reserva.desconhecido = False
    reserva.resposta_id = resposta_id[:120]
    reserva.save(update_fields=["custo_estimado_usd", "desconhecido", "resposta_id"])


@dataclass
class Transcricao:
    texto: str
    idioma: str
    segundos: float
    modelo: str
    custo_usd: Decimal
    consumo_id: int
    logprobs: list = field(default_factory=list)


def _extensao(mime: str) -> str:
    mime = (mime or "").split(";", 1)[0].strip().lower()
    return {"audio/ogg": "ogg", "audio/opus": "ogg", "audio/mpeg": "mp3", "audio/mp4": "m4a",
            "audio/aac": "m4a", "audio/wav": "wav", "audio/webm": "webm"}.get(mime, "ogg")


def transcrever(conteudo: bytes, mime: str, *, segundos: float | None = None, vocabulario: list[str] | None = None,
                autorizacao_id=None) -> Transcricao:
    nome = modelo_de_transcricao()
    duracao_pior = max(segundos or 0, len(conteudo) / BYTES_POR_SEGUNDO_PIOR_CASO, 1)
    pior_caso = custo_por_segundos(nome, math.ceil(duracao_pior) + 5)
    dados = {"model": nome, "language": "pt", "response_format": "json"}
    if "transcribe" in nome:
        dados["include[]"] = "logprobs"
    if vocabulario:
        # Só nomes de produto, para a grafia. Não é instrução.
        dados["prompt"] = "Produtos citados podem ser: " + ", ".join(vocabulario[:30])
    resposta, reserva = _chamar(
        nome, pior_caso, autorizacao_id,
        url=f"{executor_modelo.URL}/audio/transcriptions",
        data=dados,
        files={"file": (f"audio.{_extensao(mime)}", conteudo, (mime or "audio/ogg").split(";")[0])},
    )
    try:
        corpo = resposta.json()
    except ValueError:
        corpo = {}
    uso = corpo.get("usage") if isinstance(corpo.get("usage"), dict) else {}
    duracao = float(uso.get("seconds") or corpo.get("duration") or segundos or len(conteudo) / 1500 or 1)
    custo = custo_por_segundos(nome, duracao)
    _acertar(reserva, custo)
    return Transcricao(
        texto=str(corpo.get("text") or "").strip(),
        idioma=str(corpo.get("language") or "pt")[:20],
        segundos=round(duracao, 1),
        modelo=nome,
        custo_usd=custo,
        consumo_id=reserva.pk,
        logprobs=[p for p in (corpo.get("logprobs") or []) if isinstance(p, dict)],
    )


INSTRUCOES_DE_VOZ = (
    "Fale em português do Brasil, com calma e cordialidade, como o assistente "
    "da equipe que atende pelo WhatsApp. Não imite a voz de nenhuma pessoa real."
)


@dataclass
class Sintese:
    audio: bytes
    mime: str
    modelo: str
    voz: str
    caracteres: int
    custo_usd: Decimal
    consumo_id: int


def sintetizar(texto: str, *, autorizacao_id=None) -> Sintese:
    nome, voz = modelo_de_voz(), voz_padrao()
    texto = texto.strip()
    pior_caso = custo_por_segundos(nome, len(texto) / CARACTERES_POR_SEGUNDO_PIOR_CASO + 5)
    corpo = {"model": nome, "voice": voz, "input": texto, "response_format": "opus"}
    if "tts" in nome and not nome.startswith("tts-"):
        corpo["instructions"] = INSTRUCOES_DE_VOZ
    resposta, reserva = _chamar(nome, pior_caso, autorizacao_id,
                                url=f"{executor_modelo.URL}/audio/speech", json=corpo)
    audio = resposta.content
    if not audio:
        _acertar(reserva, pior_caso)
        raise executor_modelo.PedidoRecusado("A OpenAI devolveu um áudio vazio.")
    custo = custo_por_segundos(nome, len(texto) / CARACTERES_POR_SEGUNDO)
    _acertar(reserva, custo)
    return Sintese(audio=audio, mime="audio/ogg", modelo=nome, voz=voz, caracteres=len(texto),
                   custo_usd=custo, consumo_id=reserva.pk)
