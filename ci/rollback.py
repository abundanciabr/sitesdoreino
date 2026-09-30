"""Recuperação manual e pelo vigia; não depende de congelamento nem reservas."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _nucleo import ErroDeInstrumentacao, configurar_saida
from reversao import celulas_declaradas, main as recuperar, publicar_saidas


def main(argv=None):
    configurar_saida()
    argv = sys.argv[1:] if argv is None else argv
    celula = os.environ.get("ROLLBACK_CELULA", "").strip()
    modo = os.environ.get("ROLLBACK_MODO", "recuperar").strip()
    try:
        if not os.environ.get("ROLLBACK_MOTIVO", "").strip() or modo not in ("recuperar", "recuperar-auto"):
            raise ValueError("informe motivo e modo recuperar ou recuperar-auto")
        if modo == "recuperar" and celula not in celulas_declaradas():
            raise ValueError("célula não declarada")
        if modo == "recuperar-auto" and celula:
            raise ValueError("recuperar-auto seleciona a célula pela última publicação; não informe célula")
        if argv == ["validar-celula"]:
            publicar_saidas({"celula": celula, "modo": modo})
            return 0
        if argv:
            raise ValueError("comando desconhecido")
        os.environ["REVERSAO_CELULA"] = celula
        return recuperar()
    except ErroDeInstrumentacao as exc:
        print(f"PAROU SEM MEDIÇÃO: {exc.resumo}")
        return 2
    except ValueError as exc:
        print(f"PAROU: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
