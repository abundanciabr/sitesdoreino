"""CATRACA DE TESTES — a intocabilidade dos testes deixa de ser prosa.

Onda 6 do `docs/decisoes/PLANO-MESTRE-ROBOS-SEM-COLISAO.md` (O11 e B15). O
`RITOS.md` §2.3 e a Lei 6 dizem, desde a fundação: *"proibido deletar,
desativar, comentar ou afrouxar teste para passar"*. Isso era **só texto** — a
única coisa mecanizada era o `ci/guarda_dos_guardas.py`, e só para os testes de
invariante declarados no `INVARIANTES.md`.

O QUE ESTE PORTÃO MEDE
----------------------
O diff, contra a base, em todo arquivo de teste do projeto:

1. **arquivo de teste apagado**
2. **menos testes num arquivo que continua existindo** (contagem de `def test_`
   em Python e de `caso(` nos guardas em JavaScript)
3. **teste desligado**: `@pytest.mark.skip/skipif/xfail` ou `pytestmark` que não
   existia antes

Nenhum desses é proibido — todos são **autorizáveis**, com a etiqueta
`remove-teste` no PR. O que deixa de ser possível é fazer qualquer um deles em
SILÊNCIO, no meio de um diff grande, com a suíte ficando verde por ter menos
gente olhando.

POR QUE CONTAR, E NÃO MEDIR COBERTURA
--------------------------------------
Cobertura por porcentagem exige rodar a suíte com instrumentação em toda célula
— caro, lento, e com um número que oscila por motivos que não são qualidade.
A contagem é grosseira e é honesta: ela não diz que os testes são bons, diz que
**ninguém sumiu com eles**. As duas travas são complementares, e esta é a que
cabe num portão que roda em todo PR. A catraca de cobertura fica declarada como
o que é: ainda não existe.

O QUE ELE NÃO PEGA, dito na cara
--------------------------------
Teste que continua existindo e passa a não afirmar nada (`assert True`), teste
renomeado para outro arquivo (a contagem cai aqui e sobe lá — o total do PR é
que conta), e teste fraco desde o nascimento. Quem cobra a MORDIDA dos guardas
de invariante é o `ci/guarda_dos_guardas.py`.

Uso (o wrapper da muralha passa BASE_REF e PR_LABELS):

    python ci/catraca_de_testes.py

Exit codes: 0 PASS/SKIP · 1 teste sumiu sem autorização · 2 ERROR (não medi).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _nucleo import (  # noqa: E402
    ErroDeInstrumentacao,
    Estado,
    Relatorio,
    Resultado,
    configurar_saida,
    executar,
    raiz_do_repo,
)

ETIQUETA = "remove-teste"

# O que conta como arquivo de teste. Lista fechada: um lugar novo de teste que
# ninguém acrescente aqui fica fora da catraca — e a catraca passaria a
# proteger menos do que aparenta.
def e_arquivo_de_teste(caminho: str) -> bool:
    c = caminho.replace("\\", "/")
    if c.endswith(".py") and ("/tests/" in c or c.startswith("ci/tests/")):
        return Path(c).name.startswith("test_")
    if c.startswith("painel/testes/") and c.endswith(".js"):
        return True
    if c.startswith("e2e/") and c.endswith(".js"):
        return True
    return False


CONTADORES = (
    re.compile(r"^\s*(?:async\s+)?def\s+test_\w+", re.M),  # pytest
    re.compile(r"^\s*caso\(", re.M),  # os guardas em JS deste projeto
)

DESLIGADORES = re.compile(
    r"@pytest\.mark\.(?:skip|skipif|xfail)|^\s*pytestmark\s*=", re.M
)


def conta_testes(texto: str) -> int:
    return sum(len(padrao.findall(texto)) for padrao in CONTADORES)


def conta_desligados(texto: str) -> int:
    return len(DESLIGADORES.findall(texto))


def arquivos_no_diff(raiz: Path, base: str) -> list[str]:
    saida = executar(
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        cwd=raiz,
        descricao=f"listar os arquivos tocados contra '{base}'",
        exigir_stdout=False,
    ).stdout
    return sorted(
        linha.strip().replace("\\", "/")
        for linha in saida.splitlines()
        if linha.strip() and e_arquivo_de_teste(linha.strip())
    )


def versao_da_base(raiz: Path, base: str, caminho: str) -> str | None:
    """O arquivo NA BASE — ou None se ele não existia lá (arquivo novo).

    Não passa por `executar` porque precisa distinguir "não existia" (caso
    legítimo, e o mais comum: teste novo) de "não consegui ler" (ERROR).
    """
    proc = subprocess.run(
        ["git", "show", f"{base}:{caminho}"],
        cwd=str(raiz),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    if proc.returncode == 0:
        return proc.stdout
    erro = (proc.stderr or "").lower()
    if "does not exist" in erro or "exists on disk, but not in" in erro:
        return None
    raise ErroDeInstrumentacao(
        f"não consegui ler {caminho} em {base}",
        f"exit {proc.returncode}\n{proc.stderr.strip()[:600]}\n\n"
        "Sem a versão anterior não dá para dizer se um teste sumiu — e 'não "
        "sei' não pode virar 'não sumiu'.",
    )


def perdas(raiz: Path, base: str) -> tuple[list[str], int, int]:
    """As perdas do diff, mais os totais (antes, depois) — para o log."""
    achados: list[str] = []
    total_antes = total_depois = 0
    for caminho in arquivos_no_diff(raiz, base):
        antes = versao_da_base(raiz, base, caminho)
        atual = raiz / caminho
        texto_atual = atual.read_text(encoding="utf-8") if atual.is_file() else None

        if antes is None:
            # Arquivo novo: só soma. Não há como perder o que não existia.
            if texto_atual is not None:
                total_depois += conta_testes(texto_atual)
            continue

        n_antes = conta_testes(antes)
        total_antes += n_antes

        if texto_atual is None:
            achados.append(f"{caminho}: arquivo de teste APAGADO ({n_antes} teste(s))")
            continue

        n_depois = conta_testes(texto_atual)
        total_depois += n_depois
        if n_depois < n_antes:
            achados.append(
                f"{caminho}: {n_antes} → {n_depois} teste(s) — "
                f"{n_antes - n_depois} sumiu(ram)"
            )

        desligados_antes = conta_desligados(antes)
        desligados_depois = conta_desligados(texto_atual)
        if desligados_depois > desligados_antes:
            achados.append(
                f"{caminho}: {desligados_depois - desligados_antes} teste(s) "
                "DESLIGADO(S) (skip/skipif/xfail/pytestmark)"
            )
    return achados, total_antes, total_depois


def rodar(raiz: Path | None = None) -> Relatorio:
    raiz = raiz or raiz_do_repo()
    base = os.environ.get("BASE_REF", "").strip() or "origin/main"
    etiquetas = {
        e.strip() for e in os.environ.get("PR_LABELS", "").split(",") if e.strip()
    }
    relatorio = Relatorio(titulo="CATRACA DE TESTES — teste não some em silêncio")

    achados, antes, depois = perdas(raiz, base)
    print(f"TESTES nos arquivos tocados: {antes} antes · {depois} depois")

    if not achados:
        relatorio.registrar(
            Resultado(
                "testes",
                Estado.PASS,
                "nenhum teste apagado, reduzido ou desligado neste PR",
            )
        )
        return relatorio

    detalhe = "\n".join(f"  - {a}" for a in achados)
    if ETIQUETA in etiquetas:
        print(f"PERDAS AUTORIZADAS por `{ETIQUETA}`:")
        print(detalhe)
        relatorio.registrar(
            Resultado(
                "testes",
                Estado.PASS,
                f"{len(achados)} perda(s), com a etiqueta `{ETIQUETA}`",
                detalhe
                + "\n\nAutorizado de propósito, e registrado aqui item por item. "
                "Apagar teste que ficou obsoleto é legítimo; apagar em silêncio "
                "é que não.",
            )
        )
    else:
        relatorio.registrar(
            Resultado(
                "testes",
                Estado.FAIL,
                f"{len(achados)} teste(s) apagado(s), reduzido(s) ou desligado(s)",
                detalhe
                + "\n\nRITOS §2.3 e Lei 6: teste não se deleta, desativa nem "
                "afrouxa para passar. Se o teste ficou obsoleto de verdade "
                f"(a regra mudou, o código saiu), ponha a etiqueta `{ETIQUETA}` "
                "no PR e explique na descrição — ela não apaga o achado, "
                "registra a decisão.",
            )
        )
    return relatorio


def main() -> int:
    configurar_saida()
    try:
        relatorio = rodar()
    except ErroDeInstrumentacao as erro:
        print(f"\n❌ ERROR catraca_de_testes: {erro.resumo}")
        if erro.detalhe:
            print(erro.detalhe)
        print("   A catraca NÃO mediu nada. Isto NÃO é um OK.")
        return 2
    print(relatorio.render())
    return relatorio.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
