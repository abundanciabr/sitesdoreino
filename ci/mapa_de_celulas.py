"""O MAPA DAS CÉLULAS: quem é quem e quem consome quem, lido de `celulas.yml`.

Responde às perguntas que a publicação e a reversão fazem:

    carregar()           o mapa inteiro
    celula_do_caminho()  este arquivo pertence a quem?
    celulas_do_diff()    que células um conjunto de arquivos toca

Uso:

    python ci/mapa_de_celulas.py --mostrar

Exit codes: 0 leu · 2 ERROR (não consegui ler o mapa).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _nucleo import ErroDeInstrumentacao, configurar_saida, raiz_do_repo  # noqa: E402

ARQUIVO = "celulas.yml"


@dataclass(frozen=True)
class Celula:
    nome: str
    caminhos: tuple[str, ...]
    consome: tuple[str, ...]
    compartilhados: tuple[str, ...] = ()


def _yaml():
    try:
        import yaml  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - ambiente sem pyyaml
        raise ErroDeInstrumentacao(
            "PyYAML não está instalado",
            "O mapa das células é YAML. Sem o leitor, nada foi lido.\n\n"
            "  python -m pip install pyyaml",
        ) from exc
    return yaml


def carregar(raiz: Path | None = None) -> dict[str, Celula]:
    """Lê `celulas.yml`. Qualquer defeito de forma é ERROR, nunca mapa vazio."""
    raiz = raiz or raiz_do_repo()
    caminho = raiz / ARQUIVO
    leitor = _yaml()
    try:
        bruto = leitor.safe_load(caminho.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ErroDeInstrumentacao(
            f"{ARQUIVO} ilegível",
            f"Caminho:\n  {caminho}\n\n{exc}\n\nSem o mapa, ninguém sabe a quem "
            "pertence um arquivo, e 'não sei' não pode virar 'não pertence a "
            "ninguém'.",
        ) from exc
    except Exception as exc:  # noqa: BLE001 - erro de parse do yaml
        raise ErroDeInstrumentacao(f"{ARQUIVO} não é YAML válido", str(exc)) from exc

    celulas = (bruto or {}).get("celulas")
    if not isinstance(celulas, dict) or not celulas:
        raise ErroDeInstrumentacao(
            f"{ARQUIVO} sem a chave 'celulas'",
            "Mapa vazio NÃO é 'o projeto não tem células'.",
        )

    mapa: dict[str, Celula] = {}
    for nome, dados in sorted(celulas.items()):
        if not isinstance(dados, dict):
            raise ErroDeInstrumentacao(
                f"{ARQUIVO}: a célula '{nome}' não é um bloco", f"Recebido: {dados!r}"
            )
        caminhos = dados.get("caminhos")
        consome = dados.get("consome")
        compartilhados = dados.get("compartilhados", [])
        if not isinstance(caminhos, list) or not caminhos:
            raise ErroDeInstrumentacao(
                f"{ARQUIVO}: a célula '{nome}' não declara 'caminhos'",
                "Célula sem caminho é célula que nenhum diff alcança: ela "
                "nunca seria testada nem publicada, e ninguém notaria.",
            )
        if consome is None:
            consome = []
        if not isinstance(consome, list):
            raise ErroDeInstrumentacao(
                f"{ARQUIVO}: 'consome' da célula '{nome}' não é uma lista",
                "Use [] para 'não consome ninguém'. A lista vazia é uma "
                "declaração, a ausência é um esquecimento.",
            )
        if not isinstance(compartilhados, list):
            raise ErroDeInstrumentacao(
                f"{ARQUIVO}: 'compartilhados' da célula '{nome}' não é uma lista",
                "Use uma lista de caminhos compartilhados, ou [] quando não houver.",
            )
        mapa[nome] = Celula(
            nome=nome,
            caminhos=tuple(str(c).strip().strip("/") for c in caminhos),
            consome=tuple(sorted(str(c).strip() for c in consome)),
            compartilhados=tuple(str(c).strip().strip("/") for c in compartilhados),
        )
    # Durante o corte, as entradas antigas ficam recuperáveis no arquivo, mas
    # todo código do produto passa a pertencer à única aplicação publicada.
    if "aplicacao" in mapa:
        return {"aplicacao": mapa["aplicacao"]}
    return mapa


def celula_do_caminho(caminho: str, mapa: dict[str, Celula]) -> str | None:
    """A célula dona deste arquivo, ou None se ele não é de célula nenhuma.

    Casa por prefixo de SEGMENTO, nunca por prefixo de texto: `services/quiz`
    não pode capturar `services/quizzes`.
    """
    partes = caminho.strip().replace("\\", "/").strip("/").split("/")
    for celula in mapa.values():
        for base in celula.caminhos:
            segmentos = base.split("/")
            if partes[: len(segmentos)] == segmentos:
                return celula.nome
    return None


def celulas_do_diff(arquivos: list[str], mapa: dict[str, Celula]) -> list[str]:
    """Quais células um conjunto de arquivos toca. Ordenado, para ser estável."""
    tocadas = set()
    for arquivo in arquivos:
        dono = celula_do_caminho(arquivo, mapa)
        if dono:
            tocadas.add(dono)
        partes = arquivo.strip().replace("\\", "/").strip("/").split("/")
        for nome, celula in mapa.items():
            if any(
                partes[: len(base.split("/"))] == base.split("/")
                for base in celula.compartilhados
            ):
                tocadas.add(nome)
    return sorted(tocadas)


def main() -> int:
    configurar_saida()
    try:
        mapa = carregar(raiz_do_repo())
    except ErroDeInstrumentacao as erro:
        print(f"\n❌ ERROR mapa_de_celulas: {erro.resumo}")
        if erro.detalhe:
            print(erro.detalhe)
        return 2
    print(f"MAPA DAS CÉLULAS ({len(mapa)})")
    for celula in mapa.values():
        consome = ", ".join(celula.consome) or "ninguém"
        print(f"  {celula.nome:<13} caminhos: {', '.join(celula.caminhos)}")
        print(f"  {'':<13} consome : {consome}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
