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

O TERCEIRO BURACO, FECHADO PELA AUDITORIA DE 29/08/2026
-------------------------------------------------------
A catraca nasceu declarando dois furos (abaixo). A auditoria interna das Ondas
3 a 6 achou um TERCEIRO, e este não era teórico — era uma porta aberta:

    git mv ci/tests/test_reversao.py ci/tests/reversao_helpers.py

17 testes coletados viraram 0, a suíte inteira continuou verde, e a catraca
imprimiu `PASS — nenhum teste apagado, reduzido ou desligado neste PR`, com
`0 antes · 0 depois`. O motivo: `git diff --name-only` devolve só o DESTINO de
um rename, e o destino não é nome de teste — então o arquivo de origem, com os
17 testes dentro, simplesmente não entrava na conta.

Pior que os dois furos declarados: naqueles o teste continua sendo COLETADO
(fraco, mas presente). Aqui ele sai da suíte inteira, em silêncio, e sem a
etiqueta que autoriza. A cura é ler o diff com `--name-status -M`, que nomeia
as DUAS pontas do rename, e julgar o par:

    teste  ->  teste       conta antes e depois; cair é perda
    teste  ->  não-teste   saiu da vista da catraca = perda do arquivo inteiro
    -M também traz `D` (apagado), que já era pego, e agora sem depender de o
    nome do destino ser de teste

E a mesma auditoria achou um QUARTO caminho, fechado junto: `conftest.py` e
`pytest.ini` não são "arquivos de teste" (não começam com `test_`), então um
`collect_ignore = ["test_reversao.py", ...]` acrescentado ao `conftest.py`
desligava arquivos inteiros com a catraca em PASS e `0 antes · 0 depois`.
Desligar por configuração é desligar. Ver DESLIGADORES_DE_CONFIG.

O QUE ELE CONTINUA NÃO PEGANDO, dito na cara
--------------------------------------------
Teste que continua existindo e passa a não afirmar nada (`assert True`), teste
movido de um arquivo para outro dentro do mesmo PR (a contagem cai aqui e sobe
lá — o total do PR é que conta), e teste fraco desde o nascimento. Quem cobra a
MORDIDA dos guardas de invariante é o `ci/guarda_dos_guardas.py`.

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

# Desligar por CONFIGURAÇÃO é desligar. `conftest.py` e `pytest.ini` não são
# arquivos de teste (não contêm `def test_`), então nunca entraram na conta —
# e é exatamente por isso que davam um caminho limpo para sumir com arquivos
# inteiros:  collect_ignore = ["test_reversao.py"]  deixava a catraca em PASS
# com `0 antes · 0 depois`. Medido pela auditoria de 29/08/2026.
#
# Aqui não se conta teste: conta-se APARIÇÃO NOVA de um desligador. Uma linha
# que já existia na base continua valendo; uma linha nova precisa da etiqueta.
CONFIGS_DE_COLETA = ("conftest.py", "pytest.ini", "pyproject.toml", "tox.ini")

DESLIGADORES_DE_CONFIG = re.compile(
    r"^\s*collect_ignore(?:_glob)?\s*=|--ignore[=\s]|^\s*norecursedirs\s*=|"
    r"^\s*addopts\s*=.*(?:--ignore|-k\s|-m\s|--deselect)",
    re.M,
)


def e_config_de_coleta(caminho: str) -> bool:
    """`conftest.py`/`pytest.ini` decidem o que a suíte SEQUER coleta."""
    return Path(caminho.replace("\\", "/")).name in CONFIGS_DE_COLETA


def conta_testes(texto: str) -> int:
    return sum(len(padrao.findall(texto)) for padrao in CONTADORES)


def conta_desligados(texto: str) -> int:
    return len(DESLIGADORES.findall(texto))


def mudancas_no_diff(raiz: Path, base: str) -> list[tuple[str | None, str | None]]:
    """Os pares (caminho NA BASE, caminho AGORA) que interessam à catraca.

    `--name-status -M` em vez de `--name-only` porque `--name-only` devolve
    APENAS o destino de um rename — e foi por essa fresta que 17 testes saíram
    da suíte com a catraca em PASS (auditoria de 29/08/2026, ver o cabeçalho).
    Com `-M`, um rename chega como `R100<TAB>origem<TAB>destino`, e as duas
    pontas ficam visíveis.

    `None` na primeira posição = nasceu neste PR. `None` na segunda = sumiu da
    vista da catraca (apagado, ou renomeado para um nome que não é de teste).
    """
    saida = executar(
        ["git", "diff", "--name-status", "-M", f"{base}...HEAD"],
        cwd=raiz,
        descricao=f"listar os arquivos tocados contra '{base}'",
        exigir_stdout=False,
    ).stdout

    pares: list[tuple[str | None, str | None]] = []
    for linha in saida.splitlines():
        if not linha.strip():
            continue
        campos = linha.rstrip("\n").split("\t")
        marca = campos[0].strip()
        caminhos = [c.strip().replace("\\", "/") for c in campos[1:] if c.strip()]
        if not caminhos:
            # Marca sem caminho é diff que não dá para interpretar — e "não
            # entendi esta linha" nunca pode virar "nada mudou aqui".
            raise ErroDeInstrumentacao(
                "linha de diff sem caminho",
                f"Linha recebida:\n  {linha!r}\n\nA catraca não sabe o que foi "
                "tocado, e sem isso não há como afirmar que nenhum teste sumiu.",
            )
        if marca.startswith(("R", "C")) and len(caminhos) >= 2:
            # Rename/copy: origem e destino. Numa CÓPIA a origem continua lá, e
            # `versao_da_base` + o arquivo em disco contam a verdade sozinhos.
            pares.append((caminhos[0], caminhos[1]))
        elif marca.startswith("A"):
            pares.append((None, caminhos[0]))
        elif marca.startswith("D"):
            pares.append((caminhos[0], None))
        else:  # M, T, U...
            pares.append((caminhos[0], caminhos[0]))

    interessam = [
        (origem, destino)
        for origem, destino in pares
        if (origem and (e_arquivo_de_teste(origem) or e_config_de_coleta(origem)))
        or (destino and (e_arquivo_de_teste(destino) or e_config_de_coleta(destino)))
    ]
    return sorted(interessam, key=lambda par: (par[0] or "", par[1] or ""))


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

    def _no_disco(caminho: str) -> str | None:
        alvo = raiz / caminho
        return alvo.read_text(encoding="utf-8") if alvo.is_file() else None

    for origem, destino in mudancas_no_diff(raiz, base):
        # ---- config de coleta: aparição NOVA de desligador ---------------
        if (origem and e_config_de_coleta(origem)) or (
            destino and e_config_de_coleta(destino)
        ):
            antes_txt = versao_da_base(raiz, base, origem) if origem else None
            depois_txt = _no_disco(destino) if destino else None
            n_antes_cfg = len(DESLIGADORES_DE_CONFIG.findall(antes_txt or ""))
            n_depois_cfg = len(DESLIGADORES_DE_CONFIG.findall(depois_txt or ""))
            if n_depois_cfg > n_antes_cfg:
                achados.append(
                    f"{destino or origem}: {n_depois_cfg - n_antes_cfg} "
                    "desligador(es) de COLETA novo(s) "
                    "(collect_ignore/--ignore/norecursedirs/addopts) — "
                    "arquivo de teste desligado por configuração continua "
                    "desligado"
                )
            continue

        # ---- arquivo de teste --------------------------------------------
        if origem is None:
            # Nasceu neste PR: só soma. Não há como perder o que não existia.
            if destino and e_arquivo_de_teste(destino):
                texto = _no_disco(destino)
                if texto is not None:
                    total_depois += conta_testes(texto)
            continue

        if not e_arquivo_de_teste(origem):
            # Não era teste na base; virou teste agora. Só soma.
            if destino and e_arquivo_de_teste(destino):
                texto = _no_disco(destino)
                if texto is not None:
                    total_depois += conta_testes(texto)
            continue

        antes = versao_da_base(raiz, base, origem)
        if antes is None:
            # O git disse que existia na base e o git diz que não existe. Isso
            # é instrumento discordando de si mesmo, nunca "não havia teste".
            raise ErroDeInstrumentacao(
                f"{origem}: o diff diz que o arquivo existia em {base}, e ele "
                "não está lá",
                "Duas leituras do mesmo Git discordando é instrumento quebrado "
                "— e um instrumento quebrado não pode dizer que nada sumiu.",
            )

        n_antes = conta_testes(antes)
        total_antes += n_antes

        # O destino só conta como "o mesmo teste, noutro lugar" se ele TAMBÉM
        # for um arquivo de teste. Renomear para um nome que a suíte não coleta
        # é tirar o teste da suíte — mesmo efeito de apagar.
        texto_atual = (
            _no_disco(destino) if destino and e_arquivo_de_teste(destino) else None
        )

        if texto_atual is None:
            if destino is None:
                achados.append(
                    f"{origem}: arquivo de teste APAGADO ({n_antes} teste(s))"
                )
            else:
                achados.append(
                    f"{origem}: RENOMEADO para '{destino}', que a suíte não "
                    f"coleta — {n_antes} teste(s) saíram da suíte"
                )
            continue

        n_depois = conta_testes(texto_atual)
        total_depois += n_depois
        rotulo = origem if origem == destino else f"{origem} → {destino}"
        if n_depois < n_antes:
            achados.append(
                f"{rotulo}: {n_antes} → {n_depois} teste(s) — "
                f"{n_antes - n_depois} sumiu(ram)"
            )

        desligados_antes = conta_desligados(antes)
        desligados_depois = conta_desligados(texto_atual)
        if desligados_depois > desligados_antes:
            achados.append(
                f"{rotulo}: {desligados_depois - desligados_antes} teste(s) "
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
