"""O DEGRAU LOCAL DA ARMADILHA 185 — cada teste é uma linha da regra.

O que se testa é a função de decisão pura, sem repositório de verdade: os
estados que decidem se o degrau é justo (o registro que chega sozinho depois
do trabalho, a pendência de carona, o ramo que só escritura) não se produzem
sob encomenda num git real sem cerimônia que ninguém releria.

O que NÃO se testa aqui, de propósito: se o `git` responde. A polaridade do
degrau já é "sem medição, LIBERA" por construção — quem faz valer é a porta
(`ci/mergear.py`), e um degrau local que travasse todo commit porque o git
engasgou seria um degrau que alguém desliga.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "ci"))

from registro_no_commit import (  # noqa: E402
    CITA,
    ESCAPATORIA,
    ESCRITURACAO,
    SEM_NUMERO,
    SEM_REGISTRO_NOVO,
    main,
    recusa,
    veredito,
)

REGISTRO = "painel/registros/20260906-001-alguma-coisa.js"


def conteudos(**por_nome: str):
    """Um leitor de conteúdo estagiado de mentira, chaveado pelo caminho."""

    def conteudo_de(caminho: str) -> str:
        for pedaco, texto in por_nome.items():
            if pedaco in caminho:
                return texto
        raise AssertionError(f"o teste não previu leitura de {caminho}")

    return conteudo_de


# ------------------------------------------------------------------ a régua


def test_commit_sem_registro_novo_nao_e_medido():
    """O caso de todo commit comum — o degrau tem de ser invisível nele."""
    assert (
        veredito(["services/x/a.py"], [], conteudos())
        == SEM_REGISTRO_NOVO
    )


def test_o_erro_da_armadilha_reprova_no_commit_junto():
    """A forma clássica: trabalho e registro no MESMO commit, antes de o PR
    existir — logo, sem número para citar."""
    leitor = conteudos(registros='evidencia: null')
    assert veredito([REGISTRO, "services/x/a.py"], [], leitor) == SEM_NUMERO


def test_o_erro_da_armadilha_reprova_no_commit_so_do_registro():
    """A forma que mais escapa: o trabalho JÁ foi commitado, e este commit é
    só o registro. Sem olhar o diff do ramo, este caso passaria — e é
    exatamente o rito correto interrompido um passo cedo demais."""
    leitor = conteudos(registros="detalhe: 'o PR desta entrega'")
    assert (
        veredito([REGISTRO], ["services/x/a.py"], leitor) == SEM_NUMERO
    )


def test_registro_citando_url_passa():
    leitor = conteudos(
        registros='evidencia: "https://github.com/o/r/pull/1180"'
    )
    assert veredito([REGISTRO, "services/x/a.py"], [], leitor) == CITA


def test_registro_citando_forma_curta_passa():
    """As duas formas valem, como no livro — cobrar uma só reprovaria
    registro honesto por questão de estilo."""
    leitor = conteudos(registros='detalhe: "fechado no #1180"')
    assert veredito([REGISTRO], ["services/x/a.py"], leitor) == CITA


def test_ramo_que_so_escritura_e_isento():
    """O PR de livro é isento na porta; o degrau local espelha a isenção.
    Uma pendência sem PR nenhum é registro honesto num ramo desses."""
    leitor = conteudos(registros="precisa_do_dono: true")
    assert (
        veredito([REGISTRO, "fila/eventos/e.json"], [], leitor)
        == ESCRITURACAO
    )


def test_pendencia_de_carona_passa_junto_do_recibo():
    """Reprovar a carona reprovaria trabalho honesto: basta que ALGUM registro
    estagiado cite — o guarda do commit não sabe qual é o PR; a porta, que
    sabe, cobra o número exato."""
    pendencia = "painel/registros/20260906-002-pendencia.js"
    leitor = conteudos(
        **{
            "20260906-001": 'evidencia: ".../pull/1180"',
            "20260906-002": "precisa_do_dono: true",
        }
    )
    assert (
        veredito([REGISTRO, pendencia], ["services/x/a.py"], leitor) == CITA
    )


def test_caminho_com_barra_invertida_nao_escapa():
    """O degrau roda no Windows — o caminho que o git devolve com `/` pode
    chegar com `\\` de quem o repassa. Normalizar é o que impede a régua de
    valer só no Linux."""
    leitor = conteudos(registros="evidencia: null")
    assert (
        veredito(
            ["painel\\registros\\20260906-001-x.js", "services\\x\\a.py"],
            [],
            leitor,
        )
        == SEM_NUMERO
    )


# ------------------------------------------------------------------ a recusa


def test_a_recusa_ensina_a_ordem_e_a_escapatoria():
    """O que falhou quatro vezes em 06/09/2026 foi a ORDEM, não o
    conhecimento — a recusa tem de reensinar os três passos no instante do
    gesto, citar a armadilha e mostrar a saída deliberada."""
    texto = recusa([REGISTRO])
    assert "armadilhas/185" in texto
    assert "abra o PR" in texto
    assert "MESMO ramo" in texto
    assert f"{ESCAPATORIA}=sim" in texto
    assert REGISTRO in texto


# ------------------------------------------------------- o main, sem git real


def test_instrumentacao_quebrada_libera_o_commit(monkeypatch, capsys):
    """A polaridade OPOSTA da CI, de propósito: aqui "não consegui medir"
    libera, porque quem faz valer é a porta — e um degrau local que prende
    todo commit quando o git engasga é um degrau que alguém desliga."""
    import registro_no_commit

    def explode(*args):
        raise OSError("git fora do ar")

    monkeypatch.setattr(registro_no_commit, "_git", explode)
    assert main() == 0
    assert "porta do pouso confere" in capsys.readouterr().err


def test_a_escapatoria_avisa_e_libera(monkeypatch, capsys):
    import registro_no_commit

    respostas = {
        ("diff", "--cached", "--name-only", "--diff-filter=ACMR"): (
            REGISTRO + "\nservices/x/a.py\n"
        ),
        ("diff", "--name-only", "origin/main...HEAD"): "",
        ("show", f":{REGISTRO}"): "evidencia: null",
    }
    monkeypatch.setattr(
        registro_no_commit, "_git", lambda *a: respostas[tuple(a)]
    )
    monkeypatch.setenv(ESCAPATORIA, "sim")
    assert main() == 0
    assert "permissão explícita" in capsys.readouterr().out


def test_o_main_reprova_com_exit_1_e_imprime_a_recusa(monkeypatch, capsys):
    """O contrato com o gancho bash: recusa deliberada é exit 1 e NADA mais o
    é — é assim que `python` ausente (127) nunca vira commit preso."""
    import registro_no_commit

    respostas = {
        ("diff", "--cached", "--name-only", "--diff-filter=ACMR"): (
            REGISTRO + "\nservices/x/a.py\n"
        ),
        ("diff", "--name-only", "origin/main...HEAD"): "",
        ("show", f":{REGISTRO}"): "evidencia: null",
    }
    monkeypatch.setattr(
        registro_no_commit, "_git", lambda *a: respostas[tuple(a)]
    )
    monkeypatch.delenv(ESCAPATORIA, raising=False)
    assert main() == 1
    assert "armadilhas/185" in capsys.readouterr().out


# ------------------------------------------------------------------ a costura


def test_o_gancho_chama_o_degrau_e_so_prende_no_exit_1():
    """A costura que mantém o degrau ligado: se alguém tirar a chamada do
    `.githooks/pre-commit`, a regra continua perfeita e DESLIGADA — que é o
    estado que esta casa não aceita (garantia sem mecanismo)."""
    gancho = (RAIZ / ".githooks" / "pre-commit").read_text(encoding="utf-8")
    assert "ci/registro_no_commit.py" in gancho
    assert "-eq 1" in gancho
