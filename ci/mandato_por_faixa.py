"""MANDATO POR FAIXA: o agente descobre ANTES de construir se precisa da palavra dele.

`docs/decisoes/MANDATO-POR-FAIXA.md` é a lei; este arquivo é a tradução dela em
comando. A exigência de mandato não é o custo. O custo é descobrir que ela
existe depois de o trabalho estar pronto.

    python ci/mandato_por_faixa.py --arquivos infra/deploy-celula-na-vps.sh
    python ci/mandato_por_faixa.py --arquivos painel/x.json --faixa admin --corpo-arquivo corpo.md

Sem `--corpo-arquivo` ele só classifica, porque no minuto zero ainda não existe
corpo de PR: sai 0 em Lista B e 1 em Lista A. Com o corpo, julga também a linha.

A LISTA A SÃO TRÊS NOMES, NÃO UMA LISTA DE CAMINHOS
---------------------------------------------------
O mantenedor fechou três nomes em 20/09/2026: pagamento e cobrança, servidor e
infraestrutura, senhas e chaves. Os nomes são a autoridade e estão escritos
aqui. Os CAMINHOS de cada nome são derivados de `celulas.yml` e do disco a cada
chamada, nunca colados.

Colar os caminhos seria a Classe 8 do plano dos robôs sem colisão (mapa velho):
no dia em que a célula `pagamentos` mudasse de pasta, a lista continuaria
apontando para a pasta antiga, e um caminho de dinheiro sem dono passaria batido
justamente no lugar onde a casa menos pode errar. `test_mandato_por_faixa.py`
reprova se algum caminho da Lista A voltar a ser constante.

Os segredos saem do DISCO, não de `git ls-files`, de propósito: um `.env` de
verdade é ignorado pelo Git e ainda assim é senha na bancada. Achar demais aqui
custa uma pergunta a mais; achar de menos custa uma chave vazando.

O QUE ESTE ARQUIVO NÃO FAZ
--------------------------
Não é portão de pouso. Quem recusa merge continua sendo `ci/mergear.py` pelo
`.github/CODEOWNERS`, e nada aqui afrouxa aquela conferência.

Por isso a Lista B cobra os mesmos tokens que o pouso vai cobrar, com o mesmo
regex e a mesma leitura de CODEOWNERS: um pré-voo que aprovasse o que o pouso
recusa seria pior que pré-voo nenhum, porque o agente descobriria a recusa no
mesmo lugar de sempre, no fim. A única conferência do pouso que este comando não
tem como fazer é a da conta que abre o PR, e a aprovação diz isso em voz alta.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import os
from pathlib import Path
import re
import sys

from _nucleo import ErroDeInstrumentacao, configurar_saida, raiz_do_repo
from mapa_de_celulas import carregar

DOCUMENTO = "docs/decisoes/MANDATO-POR-FAIXA.md"
# O MESMO regex de `ci/mergear.py`: um mais frouxo aprovaria linha que lá não casa.
LINHA = re.compile(r"^Mandato-do-mantenedor: (.{20,})$", re.MULTILINE)
GLOB = "*?!["

PAGAMENTO = "pagamento e cobrança"
SERVIDOR = "servidor e infraestrutura"
SEGREDOS = "senhas e chaves"

# Nomes de CÉLULA, não caminhos: quem responde onde elas moram é `celulas.yml`.
CELULAS_DO_DINHEIRO = ("checkout", "pagamentos")
PASTA_DA_INFRA = "infra"
COFRE = "secrets."
PASTAS_QUE_A_VARREDURA_PULA = {".git", "__pycache__", "node_modules", ".venv", "venv"}


@dataclass(frozen=True)
class Veredito:
    aprovado: bool
    lista: str
    resumo: str
    como_prosseguir: str = ""
    motivos: dict[str, str] = field(default_factory=dict)


def _normalizar(caminho: str) -> str:
    """`infra\\x.sh`, `./infra/x.sh` e `/infra/x.sh` são o mesmo arquivo."""
    return caminho.replace("\\", "/").removeprefix("./").strip("/")


def _casa(caminho: str, alvo: str) -> bool:
    """Alvo com barra é pasta e casa por segmento; sem barra é o arquivo exato."""
    caminho, alvo = _normalizar(caminho), alvo.replace("\\", "/").lstrip("/")
    return caminho.startswith(alvo) if alvo.endswith("/") else caminho == alvo


def _pasta(raiz: Path, caminho: str) -> str:
    """Só vira prefixo de pasta o que É pasta; arquivo continua arquivo."""
    caminho = _normalizar(caminho)
    return caminho + "/" if (raiz / caminho).is_dir() else caminho


def _guarda_segredo(raiz: Path, arquivo: Path) -> bool:
    """Nome de arquivo de ambiente, ou receita que saca do cofre do GitHub."""
    if "env" in arquivo.name.split(".")[1:] or arquivo.name == ".env":
        return True
    if arquivo.suffix not in (".yml", ".yaml"):
        return False
    if not arquivo.is_relative_to(raiz / ".github"):
        return False
    return COFRE in arquivo.read_text(encoding="utf-8", errors="replace")


def _segredos_no_disco(raiz: Path) -> tuple[str, ...]:
    achados = []
    for pasta, subpastas, arquivos in os.walk(raiz):
        subpastas[:] = [s for s in subpastas if s not in PASTAS_QUE_A_VARREDURA_PULA]
        for arquivo in arquivos:
            caminho = Path(pasta, arquivo)
            if _guarda_segredo(raiz, caminho):
                achados.append(caminho.relative_to(raiz).as_posix())
    return tuple(sorted(achados))


def lista_a(raiz: Path | None = None) -> dict[str, tuple[str, ...]]:
    """Os três nomes da Lista A traduzidos em caminhos, derivados a cada chamada."""
    raiz = raiz or raiz_do_repo()
    mapa = carregar(raiz)

    ausentes = [nome for nome in CELULAS_DO_DINHEIRO if nome not in mapa]
    if ausentes:
        raise ErroDeInstrumentacao(
            "célula de dinheiro fora de celulas.yml: " + ", ".join(ausentes),
            "A Lista A traduz os nomes do mantenedor pelo mapa das células. "
            "Sem a célula no mapa, eu não sei onde o dinheiro mora, e responder "
            "'Lista B' aqui seria liberar justamente o que nunca se libera.",
        )
    dinheiro = tuple(
        sorted(
            _pasta(raiz, caminho)
            for nome in CELULAS_DO_DINHEIRO
            for caminho in mapa[nome].caminhos
        )
    )

    if not (raiz / PASTA_DA_INFRA).is_dir():
        raise ErroDeInstrumentacao(
            f"a pasta {PASTA_DA_INFRA}/ não existe em {raiz}",
            "É dela que sai o item 'servidor e infraestrutura'. Sem a pasta, "
            "eu não tenho como dizer o que é servidor, e calar seria dizer "
            "'não há servidor nenhum'.",
        )

    return {
        PAGAMENTO: dinheiro,
        SERVIDOR: (PASTA_DA_INFRA + "/",),
        SEGREDOS: _segredos_no_disco(raiz),
    }


def classificar(arquivos: list[str], raiz: Path | None = None) -> dict[str, str]:
    """Caminho tocado que é Lista A, e por qual dos três nomes. Vazio é Lista B."""
    faixas = lista_a(raiz)
    return {
        caminho: item
        for caminho in arquivos
        for item, alvos in faixas.items()
        if any(_casa(caminho, alvo) for alvo in alvos)
    }


def _cercas_de_codeowners(arquivos: list[str], raiz: Path | None = None) -> tuple[str, ...]:
    """Os padrões de CODEOWNERS que estes arquivos cruzam, como `ci/mergear.py` os lê."""
    raiz = raiz or raiz_do_repo()
    try:
        linhas = (raiz / ".github/CODEOWNERS").read_text(encoding="utf-8").splitlines()
    except OSError as erro:
        raise ErroDeInstrumentacao(
            "não consegui ler .github/CODEOWNERS",
            f"{erro}\n\nSem as cercas, este pré-voo aprovaria o que o pouso "
            "recusa, que é exatamente o erro que ele existe para evitar.",
        ) from erro
    padroes = [
        linha.split()[0]
        for linha in linhas
        if linha.strip() and not linha.lstrip().startswith("#")
    ]
    if any(caractere in padrao for padrao in padroes for caractere in GLOB):
        raise ErroDeInstrumentacao(
            "padrão CODEOWNERS com curinga",
            "`ci/mergear.py` recusa o PR inteiro nesse caso. Enquanto os dois "
            "leitores não souberem ler curinga, este pré-voo mentiria.",
        )
    return tuple(
        sorted(
            {
                padrao.lstrip("/")
                for padrao in padroes
                for caminho in arquivos
                if _casa(caminho, padrao)
            }
        )
    )


def _cita(tokens: list[str], cerca: str, arquivos: list[str]) -> bool:
    """`ci/mergear.py` aceita a cerca OU o caminho exato de dentro dela."""
    dentro = [caminho for caminho in arquivos if _casa(caminho, cerca)]
    return cerca in tokens or any(caminho in tokens for caminho in dentro)


def conferir(
    arquivos: list[str],
    corpo: str = "",
    faixa: str = "",
    raiz: Path | None = None,
) -> Veredito:
    motivos = classificar(arquivos, raiz)
    achada = LINHA.search(corpo)
    tokens = achada.group(1).split() if achada else []

    if motivos:
        caminho, item = sorted(motivos.items())[0]
        if not achada:
            return Veredito(
                False,
                "A",
                f"falta o mandato nominal para {caminho} ({item})",
                "Pare antes de editar. Peça a ele, na própria sessão, a "
                f"autorização para {item} e transcreva a resposta numa linha só: "
                "Mandato-do-mantenedor: <o pedido dele> <os caminhos> ; origem: "
                "sessão de DD/MM/AAAA. Enquanto não houver resposta, escreva o "
                "bloqueio no balcão e devolva à maestro; não espere de ramo aberto.",
                motivos,
            )
        fora = sorted(alvo for alvo in motivos if alvo not in tokens)
        if fora:
            return Veredito(
                False,
                "A",
                f"o mandato não alcança {fora[0]}",
                f"Acrescente {fora[0]} à linha Mandato-do-mantenedor: como token "
                "separado por espaço, na MESMA linha, se a autorização dele cobre "
                "esse caminho. Se não cobre, pergunte a ele.",
                motivos,
            )
        return Veredito(
            True,
            "A",
            "mandato nominal presente e alcançando os caminhos",
            "O pouso ainda confere que o PR saiu da conta do dono, e isto aqui "
            "não mede isso.",
            motivos,
        )

    if any(_casa(caminho, "contracts/") for caminho in arquivos):
        return Veredito(
            False,
            "B",
            "contrato congelado sem a etiqueta",
            "`ci/mergear.py` recusa PR que toca contracts/ sem a etiqueta "
            "`contrato`. Preserve o rito de contrato antes de seguir.",
        )
    if not achada:
        return Veredito(
            False,
            "B",
            "falta a linha Mandato-do-mantenedor:",
            "O mandato por faixa não dispensa a linha, muda o que ela cita. "
            f"Escreva: Mandato-do-mantenedor: mandato prévio por faixa "
            f"{faixa or '<faixa>'} ; {DOCUMENTO} ; sessão de 20/09/2026.",
        )
    if DOCUMENTO not in tokens:
        return Veredito(
            False,
            "B",
            f"a linha não cita {DOCUMENTO}",
            "É esse documento que concede o mandato prévio. Acrescente "
            f"{DOCUMENTO} à linha como token separado por espaço.",
        )
    faltam = [
        cerca
        for cerca in _cercas_de_codeowners(arquivos, raiz)
        if not _cita(tokens, cerca, arquivos)
    ]
    if faltam:
        return Veredito(
            False,
            "B",
            f"a linha não cita a cerca {faltam[0]} de CODEOWNERS",
            "Mandato prévio por faixa não dispensa a cerca: `ci/mergear.py` vai "
            f"exigir {faltam[0]} nesta mesma linha, como token separado por "
            "espaço, na hora do pouso. Acrescente agora e o pouso não recusa.",
        )
    if faixa and faixa not in tokens and faixa.rstrip("/") + "/" not in tokens:
        return Veredito(
            False,
            "B",
            f"a linha não cita a faixa {faixa}",
            f"Acrescente {faixa} à linha Mandato-do-mantenedor:. O mandato "
            "prévio é por faixa, e uma linha que não diz qual faixa não diz o "
            "que foi autorizado.",
        )
    return Veredito(
        True,
        "B",
        f"mandato prévio por faixa, concedido por {DOCUMENTO}",
        "O pouso ainda confere que o PR saiu da conta do dono, e isto aqui não "
        "mede isso.",
    )


def main(argv: list[str] | None = None) -> int:
    configurar_saida()
    analisador = argparse.ArgumentParser(
        description="Diz se o que você vai tocar é Lista A (mandato nominal) ou "
        "Lista B (mandato prévio por faixa). Rode ANTES de editar."
    )
    analisador.add_argument("--arquivos", nargs="+", required=True)
    analisador.add_argument("--faixa", default="", help="a área da tarefa, por exemplo ci")
    analisador.add_argument(
        "--corpo-arquivo", type=Path, help="o corpo do PR; sem ele, só classifica"
    )
    argumentos = analisador.parse_args(argv)

    try:
        if argumentos.corpo_arquivo:
            corpo = argumentos.corpo_arquivo.read_text(encoding="utf-8")
            veredito = conferir(argumentos.arquivos, corpo, argumentos.faixa)
        else:
            motivos = classificar(argumentos.arquivos)
            veredito = Veredito(
                not motivos,
                "A" if motivos else "B",
                "exige mandato nominal antes de editar"
                if motivos
                else f"mandato prévio por faixa, concedido por {DOCUMENTO}",
                "Só siga se o brief já trouxer a linha Mandato-do-mantenedor: "
                "com esses caminhos. Se não trouxer, escreva o bloqueio no balcão "
                "e devolva à maestro, agora, antes de editar."
                if motivos
                else "",
                motivos,
            )
    except OSError as erro:
        print(f"ERROR mandato_por_faixa: não consegui ler o corpo: {erro}", file=sys.stderr)
        return 2
    except ErroDeInstrumentacao as erro:
        print(f"ERROR mandato_por_faixa: {erro.resumo}", file=sys.stderr)
        if erro.detalhe:
            print(erro.detalhe, file=sys.stderr)
        print("A lista NÃO foi calculada. Trate como Lista A até saber.", file=sys.stderr)
        return 2

    print(f"LISTA {veredito.lista}: {veredito.resumo}")
    for caminho, item in sorted(veredito.motivos.items()):
        print(f"  {caminho} é {item}")
    if veredito.como_prosseguir:
        print()
        print(veredito.como_prosseguir)
    return 0 if veredito.aprovado else 1


if __name__ == "__main__":
    raise SystemExit(main())
