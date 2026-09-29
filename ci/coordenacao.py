"""Cliente da coordenação. Envie um JSON com chave estável; repetir preserva a operação."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from _nucleo import ErroDeInstrumentacao, configurar_saida


def chamar(pedido):
    url = os.environ.get("COORDENACAO_API_URL", "")
    endereco = urlparse(url)
    if endereco.scheme != "https" and not (
        endereco.scheme == "http" and endereco.hostname in ("localhost", "127.0.0.1")
    ):
        raise ErroDeInstrumentacao(
            "COORDENACAO_API_URL precisa usar HTTPS ou loopback local. Configure o endpoint oficial."
        )
    publicador = pedido.get("operacao") in (
        "adquirir_publicador",
        "autorizar_publicacao",
        "conferir_publicacao",
        "confirmar_publicacao",
    )
    token = os.environ.get(
        "COORDENACAO_PUBLICADOR_TOKEN" if publicador else "COORDENACAO_TOKEN", ""
    )
    if not token:
        raise ErroDeInstrumentacao(
            "Credencial da coordenação ausente. Provisione a identidade técnica pelo canal oficial."
        )
    if pedido.get("operacao") == "autorizar_publicacao":
        try:
            from candidato import carregar
        except ImportError as erro:
            raise ErroDeInstrumentacao(
                "Verificador de candidato ausente. Instale o incremento PME06 antes de autorizar publicação."
            ) from erro
        if not isinstance(pedido.get("candidato"), str) or not pedido["candidato"]:
            raise ErroDeInstrumentacao(
                "Candidato ausente. Envie o identificador da aceitação assinada."
            )
        aceito = carregar(Path(__file__).resolve().parents[1], pedido["candidato"])
        if pedido.get("manifesto") != aceito:
            raise ErroDeInstrumentacao(
                "Manifesto diverge da aceitação assinada. Recarregue o candidato antes de publicar."
            )
    requisicao = Request(
        url,
        data=json.dumps(pedido, allow_nan=False).encode(),
        method="POST",
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(requisicao, timeout=60) as resposta:
            dados = json.load(resposta)
    except HTTPError as erro:
        raise ErroDeInstrumentacao(
            f"Coordenação recusou a operação (HTTP {erro.code}). Consulte o estado, função e coorte antes de repetir a mesma chave."
        ) from None
    except (URLError, TimeoutError, OSError, ValueError) as erro:
        raise ErroDeInstrumentacao(
            "Resposta da coordenação não comprovada. Consulte o efeito antes de repetir o JSON com a mesma chave."
        ) from None
    if (
        not isinstance(dados, dict)
        or dados.get("estado") != "PASS"
        or not isinstance(dados.get("resultado"), dict)
    ):
        raise ErroDeInstrumentacao(
            "Resposta incompatível da coordenação. Preserve a chave e confira o endpoint oficial."
        )
    return dados["resultado"]


def main(argv=None):
    configurar_saida()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "pedido", type=Path, help="arquivo JSON da operação, sem credenciais"
    )
    args = parser.parse_args(argv)
    try:
        pedido = json.loads(args.pedido.read_text(encoding="utf-8-sig"))
        if not isinstance(pedido, dict):
            raise ValueError("corpo não é objeto")
        resultado = chamar(pedido)
    except (ErroDeInstrumentacao, OSError, ValueError) as erro:
        print(json.dumps({"estado": "ERROR", "erro": str(erro)}, ensure_ascii=False))
        return 2
    print(json.dumps({"estado": "PASS", "resultado": resultado}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
