"""A suíte roda em paralelo quando dá, e roda do mesmo jeito quando não dá.

`armadilhas/332`. A suíte de 1685 testes levava 8min55s no Windows porque abre
outros programas o tempo todo (119 fronteiras de subprocesso), e criar processo
ali custa perto de dez vezes o que custa no Linux. Em série, isso empurrava a
espera de TODO PR desta casa de 1min36s para 14min17s — o preço do job
`windows-a-maquina-dos-robos`, que existe porque nenhum outro job roda no
sistema onde os robôs trabalham (desde 05/09/2026 ele mora em
`.github/workflows/rede-do-windows.yml` e roda na `main`, fora do PR).

`-n auto` derrubou para 3min31s em 4 processos. A velocidade em si não se guarda
por teste (isso mediria a máquina do dia, não o código); o que se guarda é a
DECISÃO: usar o paralelo quando ele está disponível, e continuar rodando quando
não está.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ_DO_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ_DO_REPO / "ci"))

import ci as portao  # noqa: E402


def test_usa_o_paralelo_quando_o_xdist_existe():
    """Sem isto, alguém remove o `-n auto` e ninguém percebe: a suíte continua
    verde, só que três vezes mais devagar — e devagar não deixa nada vermelho."""
    import xdist  # noqa: F401  (se faltar aqui, é o outro teste que responde)

    assert portao._em_paralelo() == ["-n", "auto"], (
        "o portão parou de pedir o paralelo mesmo com o pytest-xdist instalado. "
        "A suíte volta de ~3min para ~9min no Windows, e a espera de todo PR "
        "desta casa vai junto (armadilhas/332)."
    )


def test_sem_o_xdist_a_suite_continua_rodando_em_serie(monkeypatch):
    """A metade que impede a cura de virar armadilha nova.

    Um portão que passa a EXIGIR dependência nova quebra a máquina de quem só
    fez `git pull`, com `pytest: error: unrecognized arguments: -n`. E portão
    que não roda não protege ninguém — o remédio teria virado a doença.
    """
    monkeypatch.setitem(sys.modules, "xdist", None)
    assert portao._em_paralelo() == [], (
        "sem o pytest-xdist o portão continuou pedindo `-n auto`. Quem não "
        "tiver a dependência instalada não consegue mais rodar a suíte."
    )


def test_o_paralelo_entra_no_comando_que_o_portao_de_fato_roda():
    """A ponta solta: os dois testes acima medem a função isolada.

    Este confere que ela está PLUGADA no comando real — uma função certa que
    ninguém chama é a mesma coisa que nenhuma função.
    """
    fonte = (RAIZ_DO_REPO / "ci" / "ci.py").read_text(encoding="utf-8")
    trecho = fonte.split("def rodar_testes_do_testador")[1][:400]
    assert "_em_paralelo()" in trecho, (
        "`rodar_testes_do_testador` parou de chamar `_em_paralelo()` — a suíte "
        "voltou a rodar em fila indiana sem nada ficar vermelho."
    )
