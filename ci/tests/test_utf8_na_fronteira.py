"""A fronteira entre pai e filho fala UTF-8 — e decisão não anda em prosa.

O caso, medido em 04/09/2026. No Windows, um `python` filho escreve no cano
pela codepage do console (cp1252); todo leitor desta casa decodifica utf-8. O
`í` de "assíncrona" viaja como `\\xed` e chega como `\\ufffd`. Nada explode:
uma comparação de texto simplesmente passa a dizer "não" para sempre.

Foi assim que a remedição do ERROR do portão (`ci/esperar.py`, construída em
03/09/2026 porque os PRs #954 e #956 morreram sem ela) nasceu inerte na única
máquina onde roda. Verde na CI (Linux), morta em casa, por um dia inteiro.

Não foi a primeira vez, e é isso que estes guardas existem para encerrar:

    armadilhas/003 (PR #15) ..... acento em cp1252 vira lixo. Só documentado.
    armadilhas/138 (27/08/2026) . a MESMA classe, e já com a previsão escrita:
                                  "o required check `muralhas` roda em
                                  ubuntu-latest, não Windows". Só documentado.
    04/09/2026 .................. terceira vez, agora numa DECISÃO.

Catálogo cura o caso; só mecanismo cura a classe (RETROSPECTIVA-FASE-D §2,
"garantia sem mecanismo"). Estes são o mecanismo.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

RAIZ_DO_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ_DO_REPO / "ci"))

import esperar  # noqa: E402
import mergear  # noqa: E402
from _nucleo import configurar_saida  # noqa: E402
from mergear import MOTIVO_GITHUB_AINDA_CALCULANDO  # noqa: E402

FERRAMENTAS = sorted((RAIZ_DO_REPO / "ci").glob("*.py"))
CHAMADAS_DE_SUBPROCESSO = {
    "subprocess.run",
    "subprocess.Popen",
    "subprocess.check_output",
}
# Passar qualquer um destes é dizer "me devolva texto, não bytes" — e é só aí
# que a codepage do filho vira uma decisão do pai.
DECODIFICA_TEXTO = {"text", "encoding", "universal_newlines"}


def test_a_porta_da_casa_poe_utf8_no_ambiente_do_filho():
    """`configurar_saida()` cuida da minha saída E da do meu filho.

    Uma linha só, na porta por onde as 33 ferramentas de `ci/` já passam, cobre
    as 90 fronteiras que decodificam texto — 89 delas não declaravam ambiente
    nenhum em 04/09/2026. Remendar chamada a chamada seria a esteira infinita:
    a de número 91 recomeçaria a doença.
    """
    os.environ.pop("PYTHONUTF8", None)
    configurar_saida()
    assert os.environ.get("PYTHONUTF8") == "1", (
        "configurar_saida() parou de pôr PYTHONUTF8 no ambiente. Todo filho "
        "Python desta casa volta a escrever na codepage do console, e no "
        "Windows as comparações de texto do pai passam a falhar em silêncio."
    )


def test_quem_ja_escolheu_o_proprio_ambiente_continua_mandando_nele():
    """`setdefault`, não atribuição: a porta ajuda, nunca atropela."""
    os.environ["PYTHONUTF8"] = "0"
    try:
        configurar_saida()
        assert os.environ["PYTHONUTF8"] == "0"
    finally:
        os.environ["PYTHONUTF8"] = "1"


def test_o_utf8_chega_de_verdade_ao_filho_python():
    """A prova de fora: não basta a variável estar posta, o `í` tem de chegar.

    Os dois testes acima medem a intenção. Este mede o efeito, atravessando um
    processo de verdade — que é onde a garantia morreu da última vez.
    """
    os.environ.pop("PYTHONUTF8", None)
    configurar_saida()
    filho = subprocess.run(
        [sys.executable, "-c", "print('assíncrona')"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=60,
    )
    assert "assíncrona" in filho.stdout, (
        "o acento não sobreviveu à travessia pai→filho: " + repr(filho.stdout)
    )


def test_toda_ferramenta_que_cria_filho_python_passa_pela_porta():
    """O guarda que pega a ferramenta de número 91 antes de ela sangrar.

    A régua é estreita de propósito, e cada limite é para não medir a coisa
    errada com precisão (que é como um portão morre):

      - só quem DECODIFICA TEXTO (quem lê bytes escolhe a codificação depois);
      - só quem cria filho PYTHON (`PYTHONUTF8` é chave do interpretador: num
        `git`, `gh` ou `docker` ela não faz nada, e exigi-la ali seria teatro);
      - só quem é PONTO DE ENTRADA (biblioteca não configura saída global —
        quem a chama já passou pela porta).

    Em 04/09/2026 a lista cabia em dois nomes, `ci.py` e `esperar.py`, e os
    dois já passavam. O guarda não existe para hoje: existe para o terceiro.
    """
    faltando = []
    for caminho in FERRAMENTAS:
        fonte = caminho.read_text(encoding="utf-8")
        if "__main__" not in fonte:
            continue
        arvore = ast.parse(fonte, str(caminho))
        cria_filho_python = False
        for no in ast.walk(arvore):
            if not (isinstance(no, ast.Call)
                    and ast.unparse(no.func) in CHAMADAS_DE_SUBPROCESSO):
                continue
            if not ({k.arg for k in no.keywords if k.arg} & DECODIFICA_TEXTO):
                continue
            comando = ast.unparse(no.args[0]) if no.args else ""
            if "sys.executable" in comando or "_mergear()" in comando:
                cria_filho_python = True
        if not cria_filho_python:
            continue
        if "configurar_saida" not in fonte and "PYTHONUTF8" not in fonte:
            faltando.append(caminho.name)
    assert not faltando, (
        "estas ferramentas criam um filho Python e leem o texto dele sem passar "
        f"pela porta que põe UTF-8 no ambiente: {faltando}\n"
        "Conserto: chame `configurar_saida()` (de `_nucleo`) no início do main.\n"
        "Por que importa: no Windows o filho escreve em cp1252 e o pai lê "
        "utf-8; o acento vira `\\ufffd` e qualquer comparação de texto do pai "
        "passa a ser falsa, sem erro nenhum na tela. Já custou a remedição "
        "inteira do portão de pouso (04/09/2026)."
    )


def test_a_decisao_de_remedir_anda_em_marca_ascii_e_numa_fonte_so():
    """Prosa é para gente ler; decisão de máquina anda em marca de máquina.

    Duas garantias num teste porque são a mesma: a marca é ASCII (atravessa
    qualquer codepage intacta) e existe UMA vez (o `esperar.py` importa a do
    `mergear.py`). Antes de 04/09/2026 ela era uma frase em português copiada
    em três arquivos — e reescrever a mensagem para o humano entender melhor
    mataria a remedição com todos os testes verdes.
    """
    assert (
        esperar.MOTIVO_GITHUB_AINDA_CALCULANDO is mergear.MOTIVO_GITHUB_AINDA_CALCULANDO
    ), (
        "`ci/esperar.py` voltou a ter uma CÓPIA da marca em vez de importá-la "
        "de `ci/mergear.py`. Duas cópias divergem em silêncio."
    )
    assert MOTIVO_GITHUB_AINDA_CALCULANDO.isascii(), (
        "a marca ganhou um caractere não-ASCII: "
        f"{MOTIVO_GITHUB_AINDA_CALCULANDO!r}\n"
        "Ela atravessa um cano entre dois processos e é comparada do outro "
        "lado. Acento ali é uma decisão que depende da codepage da máquina."
    )


def test_o_portao_realmente_imprime_a_marca_quando_nao_consegue_medir():
    """A ponta solta que fecha o circuito: a marca existe na saída REAL.

    Sem isto, os outros guardas provariam um acordo entre duas constantes que
    poderia não aparecer no texto que o portão de fato imprime.
    """
    resultado = mergear.checar_mergeabilidade(
        {"mergeable": "UNKNOWN", "mergeStateStatus": "UNKNOWN"}
    )
    assert resultado.estado.value == "ERROR"
    assert MOTIVO_GITHUB_AINDA_CALCULANDO in resultado.detalhe
