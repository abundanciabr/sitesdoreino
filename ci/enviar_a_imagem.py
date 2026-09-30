#!/usr/bin/env python3
"""Envia imagens ao registro com até três tentativas para falhas transitórias.

Não constrói nem aprova imagens. Falhas de autenticação encerram o envio.
Uso: python ci/enviar_a_imagem.py ghcr.io/x/y:sha"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time

TENTATIVAS = 3

PAUSAS = (10, 30)

RESPOSTAS_DEFINITIVAS = (
    "denied",
    "unauthorized",
    "authentication required",
    "manifest unknown",
    "name unknown",
    "no space left on device",
    "invalid reference format",
)

ENGASGOS_CONHECIDOS = (
    "unknown blob",
    "blob upload unknown",
    "blob upload invalid",
    "i/o timeout",
    "tls handshake timeout",
    "connection reset by peer",
    "connection refused",
    "unexpected eof",
    "eof",
    "500 internal server error",
    "502 bad gateway",
    "503 service unavailable",
    "504 gateway",
    "received unexpected http status: 5",
    "temporarily unavailable",
    "too many requests",
)

DEFINITIVO = "definitivo"
ENGASGO = "engasgo"
DESCONHECIDO = "desconhecido"


def classificar(saida: str) -> str:
    """Distingue resposta definitiva, falha transitória e erro desconhecido."""
    baixa = (saida or "").lower()
    if any(marca in baixa for marca in RESPOSTAS_DEFINITIVAS):
        return DEFINITIVO
    if any(marca in baixa for marca in ENGASGOS_CONHECIDOS):
        return ENGASGO
    return DESCONHECIDO


def _empurrar(tag: str) -> tuple[int, str]:
    """Executa uma tentativa e captura o código e a saída do Docker."""
    processo = subprocess.run(
        ["docker", "push", tag],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8", errors="replace",
    )
    return processo.returncode, processo.stdout or ""


def enviar(tag: str, *, empurrar=_empurrar, dormir=time.sleep) -> bool:
    """Envia a mesma tag até três vezes, preservando cada falha no log."""
    for tentativa in range(1, TENTATIVAS + 1):
        print(f"→ enviando {tag} (tentativa {tentativa} de {TENTATIVAS})", flush=True)
        codigo, saida = empurrar(tag)
        if codigo == 0:
            if tentativa > 1:
                print(
                    f"✅ {tag} subiu na tentativa {tentativa}. As anteriores "
                    f"falharam por engasgo do registro, e ficam no log acima — "
                    f"o run fecha verde SEM apagar que isto aconteceu.",
                    flush=True,
                )
            return True

        print(saida.rstrip(), flush=True)
        veredito = classificar(saida)

        if veredito == DEFINITIVO:
            print(
                f"🧱 PAROU POR SEGURANÇA: o registro RESPONDEU um 'não' sobre "
                f"{tag}, e isso não é engasgo de rede — é diagnóstico. "
                f"Repetir gastaria tentativa numa falha que nenhuma repetição "
                f"conserta. A mensagem do registro está logo acima.",
                flush=True,
            )
            return False

        if tentativa == TENTATIVAS:
            print(
                f"🧱 {tag} falhou nas {TENTATIVAS} tentativas. O deploy fica "
                f"VERMELHO: não foi confirmado o envio da candidata ao registro.",
                flush=True,
            )
            return False

        if veredito == DESCONHECIDO:
            print(
                "⚠ assinatura NÃO reconhecida por ci/enviar_a_imagem.py. Vou "
                "repetir mesmo assim, porque desistir do que eu não reconheço "
                "não distingue uma falha transitória de uma falha definitiva. Se "
                "esta falha se repetir, acrescente a linha dela a "
                "ENGASGOS_CONHECIDOS ou a RESPOSTAS_DEFINITIVAS.",
                flush=True,
            )

        pausa = PAUSAS[min(tentativa - 1, len(PAUSAS) - 1)]
        print(f"… esperando {pausa}s antes da próxima tentativa", flush=True)
        dormir(pausa)

    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Envia tags de imagem ao registro, repetindo engasgo de rede."
    )
    parser.add_argument("tags", nargs="+", help="as tags completas a enviar")
    args = parser.parse_args(argv)

    for tag in args.tags:
        if not enviar(tag):
            return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
