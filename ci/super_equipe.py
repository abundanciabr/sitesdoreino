"""Cliente da fila técnica privada. A credencial vem somente de ROBO_ADMIN.

O desenvolvimento usa as mesmas ferramentas da tarefa, a cópia isolada e a
entrada infra/robo.py. Este cliente apenas assume, acompanha e registra o
resultado na fila do site. Não executa comandos recebidos em respostas.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request

BASE = "https://meshcraft.top/admin/super-equipe/"


class SemRedirecionar(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def pedir(caminho, dados=None):
    credencial = os.environ.get("ROBO_ADMIN", "")
    if not credencial:
        raise ValueError("Credencial do robô indisponível; use o cofre existente.")
    cabecalhos = {"Authorization": "Robo " + credencial, "Accept": "application/json",
                  "User-Agent": "Meshcraft-Super-Equipe/1"}
    corpo = None
    if dados is not None:
        corpo = json.dumps(dados, ensure_ascii=False).encode()
        cabecalhos["Content-Type"] = "application/json"
    request = urllib.request.Request(BASE + caminho, data=corpo, headers=cabecalhos)
    try:
        with urllib.request.build_opener(SemRedirecionar()).open(request, timeout=40) as resposta:
            return json.load(resposta)
    except urllib.error.HTTPError as erro:
        # Não imprime corpo HTML, cabeçalhos ou credenciais de uma falha.
        raise ValueError(f"Fila indisponível ou ação recusada: HTTP {erro.code}.") from None
    except (urllib.error.URLError, TimeoutError):
        raise ValueError("Resposta indisponível; consulte o mesmo trabalho antes de repetir a ação.") from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    comandos = parser.add_subparsers(dest="comando", required=True)
    comandos.add_parser("fila")
    assumir = comandos.add_parser("assumir")
    assumir.add_argument("id", type=int)
    batimento = comandos.add_parser("batimento")
    batimento.add_argument("id", type=int)
    batimento.add_argument("posse")
    resultado = comandos.add_parser("resultado")
    resultado.add_argument("id", type=int)
    resultado.add_argument("arquivo", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.comando == "fila":
            resposta = pedir("fila/")
        else:
            if args.id <= 0:
                raise ValueError("Número de melhoria inválido.")
            dados = {"acao": args.comando}
            if args.comando == "batimento":
                dados["posse"] = args.posse
            elif args.comando == "resultado":
                dados = json.loads(args.arquivo.read_text(encoding="utf-8-sig"))
                if not isinstance(dados, dict):
                    raise ValueError("Resultado precisa ser um objeto JSON.")
                dados["acao"] = "resultado"
            resposta = pedir(f"melhorias/{args.id}/", dados)
        print(json.dumps(resposta, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError):
        # Não propaga conteúdo de JSON inválido, caminho privado ou segredo.
        print(json.dumps({"erro": "Não foi possível concluir a operação. Confira a fila e o acesso do robô."}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
