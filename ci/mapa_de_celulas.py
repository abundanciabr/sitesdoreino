"""O MAPA DAS CÉLULAS — uma fonte só, e um varredor que a impede de mentir.

Onda 5 do `docs/decisoes/PLANO-MESTRE-ROBOS-SEM-COLISAO.md` (o Cartógrafo).
Carrega `celulas.yml` e responde às três perguntas que o resto do CI faz:

    celulas()            quais existem
    celula_do_caminho()  este arquivo pertence a quem?
    consumo_declarado()  quem lê a API de quem

E, sobretudo, `verificar()`: o varredor que compara o que está ESCRITO com o
que o código FAZ. Sem ele, este arquivo seria só mais um mapa envelhecendo em
silêncio — a Classe 8, que é a doença que este plano existe para curar e a
única que já cobrou dentro do próprio trabalho de curá-la (`armadilhas/148`).

O QUE ELE ELIMINA
-----------------
O mapa caminho→célula existia em DOIS lugares, e eles já discordavam:
`ci/ci.py::celulas_tocadas` contava `painel/` como a célula `admin`;
`ci/cerca-de-celula.sh` casava só `services/*` e ignorava `painel/`. A
divergência estava documentada num comentário — isto é, conhecida e tolerada.
Fato do projeto não mora em dois lugares (CLAUDE.md); agora mora aqui, e os
dois passam a ler daqui.

AS TRÊS CONSISTÊNCIAS QUE ELE COBRA (todas fail-closed)
-------------------------------------------------------
1. **Com o manifesto de contratos:** célula declarada num e ausente do outro é
   FAIL nos dois sentidos. Duas listas de células que discordam é o mesmo
   defeito que o painel curou no livro.
2. **Consumo escondido:** o código lê `OUTRA_API_URL` e o mapa não declara ->
   FAIL. É a dependência que ninguém vê até o dia em que a ordem de publicação
   está errada.
3. **Declaração órfã:** o mapa declara e o código não usa -> FAIL. Um mapa que
   promete a mais é tão mentiroso quanto um que promete a menos, e envelhece
   exatamente assim: alguém remove o consumo e esquece a linha.

Uso:

    python ci/mapa_de_celulas.py --verificar    # o varredor (muralha)
    python ci/mapa_de_celulas.py --mostrar      # o mapa, legível

Exit codes: 0 PASS · 1 FAIL · 2 ERROR (não consegui medir).
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _nucleo import (  # noqa: E402
    ErroDeInstrumentacao,
    Estado,
    Relatorio,
    Resultado,
    configurar_saida,
    raiz_do_repo,
)

ARQUIVO = "celulas.yml"

# A convenção que as 13 células seguem: quem consome a `alunos` lê
# ALUNOS_API_URL. O varredor mede isto — se a convenção mudar sem ele saber,
# `test_o_varredor_enxerga_o_consumo_real` fica vermelho.
CONSUMO = re.compile(r"\b([A-Z][A-Z0-9_]*)_API_URL\b")

# Onde procurar consumo. Nunca em testes: uma célula que MOCKA outra num teste
# não depende dela em produção, e tratar isso como dependência inventaria uma
# ordem de publicação que o mundo real não pede.
EXTENSOES = (".py", ".yml", ".yaml", ".html", ".txt", ".example")
PASTAS_IGNORADAS = {"tests", "test", "__pycache__", "node_modules", "migrations"}


@dataclass(frozen=True)
class Celula:
    nome: str
    caminhos: tuple[str, ...]
    consome: tuple[str, ...]


def _yaml():
    try:
        import yaml  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - ambiente sem pyyaml
        raise ErroDeInstrumentacao(
            "PyYAML não está instalado",
            "O mapa das células é YAML. Sem o leitor, este portão NÃO mediu "
            "nada — e isso não é um OK.\n\n  python -m pip install pyyaml",
        ) from exc
    return yaml


def carregar(raiz: Path | None = None) -> dict[str, Celula]:
    """Lê `celulas.yml`. Qualquer defeito de forma é ERROR, nunca mapa vazio."""
    raiz = raiz or raiz_do_repo()
    caminho = raiz / ARQUIVO
    try:
        bruto = _yaml().safe_load(caminho.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ErroDeInstrumentacao(
            f"{ARQUIVO} ilegível",
            f"Caminho:\n  {caminho}\n\n{exc}\n\nSem o mapa, ninguém sabe a quem "
            "pertence um arquivo — e 'não sei' não pode virar 'não pertence a "
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
        if not isinstance(caminhos, list) or not caminhos:
            raise ErroDeInstrumentacao(
                f"{ARQUIVO}: a célula '{nome}' não declara 'caminhos'",
                "Célula sem caminho é célula que nenhum diff alcança — ela "
                "nunca seria testada nem publicada, e ninguém notaria.",
            )
        if consome is None:
            consome = []
        if not isinstance(consome, list):
            raise ErroDeInstrumentacao(
                f"{ARQUIVO}: 'consome' da célula '{nome}' não é uma lista",
                "Use [] para 'não consome ninguém' — a lista vazia é uma "
                "declaração, a ausência é um esquecimento.",
            )
        mapa[nome] = Celula(
            nome=nome,
            caminhos=tuple(str(c).strip().strip("/") for c in caminhos),
            consome=tuple(sorted(str(c).strip() for c in consome)),
        )
    return mapa


def celula_do_caminho(caminho: str, mapa: dict[str, Celula]) -> str | None:
    """A célula dona deste arquivo — ou None se ele não é de célula nenhuma.

    Casa por prefixo de SEGMENTO, nunca por prefixo de texto: `services/quiz`
    não pode capturar `services/quizzes`, e um dia isso vai existir.
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
    return sorted({c for c in (celula_do_caminho(a, mapa) for a in arquivos) if c})


def consumo_no_codigo(raiz: Path, mapa: dict[str, Celula]) -> dict[str, set[str]]:
    """O que o CÓDIGO diz — a régua contra a qual o mapa é medido."""
    conhecidas = {nome.upper(): nome for nome in mapa}
    medido: dict[str, set[str]] = {nome: set() for nome in mapa}
    for nome, celula in mapa.items():
        for base in celula.caminhos:
            pasta = raiz / base
            if not pasta.is_dir():
                continue
            for arquivo in pasta.rglob("*"):
                if not arquivo.is_file() or arquivo.suffix not in EXTENSOES:
                    continue
                if PASTAS_IGNORADAS & {p.name for p in arquivo.parents}:
                    continue
                try:
                    texto = arquivo.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                for achado in CONSUMO.findall(texto):
                    outra = conhecidas.get(achado)
                    if outra and outra != nome:
                        medido[nome].add(outra)
    return medido


def _celulas_do_manifesto(raiz: Path) -> set[str]:
    caminho = raiz / "ci" / "manifesto-de-contratos.json"
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ErroDeInstrumentacao(
            "manifesto de contratos ilegível", f"Caminho:\n  {caminho}\n\n{exc}"
        ) from exc
    celulas = dados.get("celulas")
    if not isinstance(celulas, dict) or not celulas:
        raise ErroDeInstrumentacao("manifesto de contratos sem 'celulas'", "")
    return set(celulas)


def verificar(raiz: Path | None = None) -> Relatorio:
    """O varredor. Compara o que está escrito com o que o código faz."""
    raiz = raiz or raiz_do_repo()
    relatorio = Relatorio(titulo="MAPA DAS CÉLULAS — o escrito contra o medido")
    mapa = carregar(raiz)

    # 1. As duas listas de células precisam ser a MESMA lista.
    do_manifesto = _celulas_do_manifesto(raiz)
    do_mapa = set(mapa)
    faltando = sorted(do_manifesto - do_mapa)
    sobrando = sorted(do_mapa - do_manifesto)
    if faltando or sobrando:
        detalhe = []
        if faltando:
            detalhe.append("no manifesto e ausentes do mapa: " + ", ".join(faltando))
        if sobrando:
            detalhe.append("no mapa e ausentes do manifesto: " + ", ".join(sobrando))
        relatorio.registrar(
            Resultado(
                "lista de células",
                Estado.FAIL,
                "o mapa e o manifesto de contratos discordam",
                "\n".join(detalhe)
                + "\n\nDuas listas da mesma coisa que discordam é o defeito que "
                "esta casa proíbe. Declare a célula nova nos dois, no mesmo PR.",
            )
        )
    else:
        relatorio.registrar(
            Resultado(
                "lista de células",
                Estado.PASS,
                f"{len(do_mapa)} células, iguais no mapa e no manifesto",
            )
        )

    # 2. Todo caminho declarado precisa existir. Caminho morto faz o mapa
    #    prometer cobertura que ele não tem.
    inexistentes = [
        f"{celula.nome}: {base}"
        for celula in mapa.values()
        for base in celula.caminhos
        if not (raiz / base).exists()
    ]
    relatorio.registrar(
        Resultado(
            "caminhos",
            Estado.FAIL if inexistentes else Estado.PASS,
            (
                "caminho declarado que não existe no disco"
                if inexistentes
                else "todos os caminhos declarados existem"
            ),
            "\n".join(f"  - {i}" for i in inexistentes),
        )
    )

    # 3. O consumo: os dois sentidos.
    medido = consumo_no_codigo(raiz, mapa)
    escondidos: list[str] = []
    orfas: list[str] = []
    for nome, celula in mapa.items():
        declarado = set(celula.consome)
        real = medido.get(nome, set())
        for outra in sorted(real - declarado):
            escondidos.append(f"{nome} lê {outra.upper()}_API_URL e não declara")
        for outra in sorted(declarado - real):
            orfas.append(f"{nome} declara consumir {outra} e não há sinal disso")
    if escondidos or orfas:
        relatorio.registrar(
            Resultado(
                "consumo entre células",
                Estado.FAIL,
                "o mapa e o código discordam sobre quem consome quem",
                "\n".join(
                    [*(f"  - {e}" for e in escondidos), *(f"  - {o}" for o in orfas)]
                )
                + "\n\nDependência escondida quebra a ordem de publicação (o "
                "consumidor sobe antes do provedor, e o site responde errado "
                "sem nada ficar vermelho). Declaração órfã envelhece o mapa até "
                "ele não valer nada.",
            )
        )
    else:
        total = sum(len(v) for v in medido.values())
        relatorio.registrar(
            Resultado(
                "consumo entre células",
                Estado.PASS,
                f"{total} consumo(s) declarado(s) e medido(s) no código",
            )
        )
    return relatorio


def main(argv: list[str] | None = None) -> int:
    configurar_saida()
    argumentos = list(sys.argv[1:] if argv is None else argv)
    try:
        raiz = raiz_do_repo()
        if "--mostrar" in argumentos:
            mapa = carregar(raiz)
            print(f"MAPA DAS CÉLULAS ({len(mapa)})")
            for celula in mapa.values():
                consome = ", ".join(celula.consome) or "ninguém"
                print(f"  {celula.nome:<13} caminhos: {', '.join(celula.caminhos)}")
                print(f"  {'':<13} consome : {consome}")
            return 0
        relatorio = verificar(raiz)
    except ErroDeInstrumentacao as erro:
        print(f"\n❌ ERROR mapa_de_celulas: {erro.resumo}")
        if erro.detalhe:
            print(erro.detalhe)
        print("   O mapa NÃO foi verificado. Este resultado NÃO é um OK.")
        return 2
    print(relatorio.render())
    if relatorio.estado is Estado.PASS:
        print("\n✅ O mapa diz a verdade sobre o código.")
    else:
        print(
            "\n❌ Conserte `celulas.yml` (ou o código) e rode de novo. Um mapa "
            "que mente é pior que mapa nenhum: ele é consultado com confiança."
        )
    return relatorio.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
