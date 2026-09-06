"""O PADRÃO DE TRABALHO — provas de que o portão pega cada jeito de perdê-lo.

O mantenedor mandou o Padrão valer INTEGRALMENTE e ficar onde nenhum robô
consiga ignorá-lo (04/09/2026). Um portão que só conferisse "a seção existe"
daria PASS num texto reduzido a três bullets — e é exatamente assim que ela
morreria: ninguém apaga uma lei, alguém a *resume* numa sessão apertada de
contexto, com a melhor das intenções.

Por isso cada teste aqui mutila o texto de um jeito DIFERENTE e exige vermelho:

    regra apagada          — some um dos 11 títulos
    exigência parafraseada — os títulos ficam, a frase que obriga some
    seção rebaixada        — continua no arquivo, mas deixa de ser a primeira
    costura apagada        — a conciliação com as leis da casa some
    porta muda             — o texto está lá, mas nenhum caminho leva até ele
    arquivo engordado      — a lei está inteira, e a história voltou para dentro

E um teste garante o contrário: o aviso de abertura de sessão é DERIVADO do
`CLAUDE.md`, não uma segunda cópia da lei. Duas cópias divergem, e a sessão
passa a ler a errada.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "ci"))

import padrao_de_trabalho as padrao  # noqa: E402
from _nucleo import ErroDeInstrumentacao, Estado  # noqa: E402


def _cenario(tmp_path: Path, **trocas: tuple[str, str]) -> Path:
    """Uma cópia do repositório real reduzida ao que este portão lê, com trocas.

    Cada troca é `arquivo=(velho, novo)`; a substituição é exigida acontecer,
    porque um teste que "mutila" sem mutilar dá verde e não prova nada.
    """
    raiz = tmp_path / "repo"
    arquivos = ["CLAUDE.md", *padrao.PORTAS]
    for nome in arquivos:
        destino = raiz / nome
        destino.parent.mkdir(parents=True, exist_ok=True)
        texto = (RAIZ / nome).read_text(encoding="utf-8").replace("\r\n", "\n")
        if nome in trocas:
            velho, novo = trocas[nome]
            assert velho in texto, f"a mutilação de {nome} não encontrou: {velho!r}"
            texto = texto.replace(velho, novo, 1)
        destino.write_text(texto, encoding="utf-8")
    return raiz


def _falha(relatorio, nome: str) -> None:
    resultado = next(r for r in relatorio.resultados if r.nome == nome)
    assert resultado.estado is Estado.FAIL, relatorio.render()
    assert relatorio.estado is Estado.FAIL, relatorio.render()


# ---------------------------------------------------------------------------
# O repositório de verdade
# ---------------------------------------------------------------------------


def test_o_padrao_esta_integro_no_repositorio_de_verdade():
    relatorio = padrao.conferir(RAIZ)
    assert relatorio.estado is Estado.PASS, relatorio.render()


def test_toda_porta_declarada_existe_em_disco():
    """Porta citada para um arquivo que sumiu é pior que porta nenhuma.

    Ela parece garantia: o portão continua verde, medindo um caminho que já
    não faz parte do caminho de ninguém.
    """
    sumidas = [nome for nome in padrao.PORTAS if not (RAIZ / nome).exists()]
    assert not sumidas, f"portas declaradas que não existem: {sumidas}"


def test_o_aviso_de_sessao_lista_as_onze_regras(capsys):
    padrao.aviso(RAIZ)
    saida = capsys.readouterr().out
    for regra in padrao.REGRAS:
        assert regra in saida, f"o aviso de abertura não cita a regra: {regra}"


# ---------------------------------------------------------------------------
# As cinco mutilações — cada uma tem de dar vermelho
# ---------------------------------------------------------------------------


def test_regra_apagada_reprova(tmp_path):
    relatorio = padrao.conferir(
        _cenario(tmp_path, **{"CLAUDE.md": ("#### 7. O passe de remoção", "#### 7. Limpeza")})
    )
    _falha(relatorio, "as 11 regras, íntegras")


def test_exigencia_parafraseada_reprova(tmp_path):
    """Os 11 títulos intactos, e a lei esvaziada mesmo assim.

    Este é o modo de falha que o portão existe para pegar: "sempre teste antes
    de entregar" diz a mesma coisa em espírito e não obriga a nada. O que
    obriga é a frase literal.
    """
    relatorio = padrao.conferir(
        _cenario(
            tmp_path,
            **{
                "CLAUDE.md": (
                    'Você nunca diz "deve funcionar". Ou rodou, ou escreve "NÃO RODEI".',
                    "Sempre teste antes de entregar.",
                )
            },
        )
    )
    _falha(relatorio, "as exigências literais")


def test_seção_rebaixada_reprova(tmp_path):
    """Continua no arquivo, deixou de ser a primeira — e vira rodapé."""
    relatorio = padrao.conferir(
        _cenario(
            tmp_path,
            **{"CLAUDE.md": (padrao.TITULO, "## Um aviso qualquer\n\nTexto.\n\n" + padrao.TITULO)},
        )
    )
    _falha(relatorio, "é a primeira seção")


def test_costura_apagada_reprova(tmp_path):
    """Sem a costura 2, a regra 4 vira desculpa para não abrir a caixa de pergunta."""
    relatorio = padrao.conferir(
        _cenario(
            tmp_path,
            **{"CLAUDE.md": ("vale para as decisões que são\nSUAS", "vale sempre")},
        )
    )
    _falha(relatorio, "as 3 costuras conciliadas")


def test_porta_muda_reprova(tmp_path):
    """O texto continua inteiro; nenhum caminho leva até ele pela Constituição."""
    relatorio = padrao.conferir(
        _cenario(
            tmp_path,
            **{"CONSTITUICAO.md": ("## Lei 10 — O Padrão de Trabalho", "## Lei 10 — Outra coisa")},
        )
    )
    _falha(relatorio, "as portas apontam para cá")


def test_arquivo_acima_do_teto_reprova(tmp_path):
    """A história voltando para dentro da lei.

    O CLAUDE.md inteiro entra em cada chamada de cada robô. Nenhuma regra some
    neste cenário — o arquivo só engorda — e é exatamente assim que ele voltou
    a 60 mil caracteres uma vez: cada lei nova trazendo o próprio porquê.
    """
    raiz = _cenario(tmp_path)
    caminho = raiz / "CLAUDE.md"
    caminho.write_text(
        caminho.read_text(encoding="utf-8") + "\n" + "história " * (padrao.TETO_DE_CARACTERES // 8),
        encoding="utf-8",
    )
    _falha(padrao.conferir(raiz), "cabe no teto de contexto")


# ---------------------------------------------------------------------------
# Falha de instrumentação: não medir NUNCA é "está tudo certo"
# ---------------------------------------------------------------------------


def test_secao_inteira_ausente_e_erro_de_instrumentacao(tmp_path):
    raiz = _cenario(tmp_path)
    (raiz / "CLAUDE.md").write_text("# CLAUDE.md\n\n## Outra coisa\n\nTexto.\n", encoding="utf-8")
    with pytest.raises(ErroDeInstrumentacao) as erro:
        padrao.conferir(raiz)
    assert "SUMIU" in erro.value.resumo


def test_o_aviso_nao_derruba_a_sessao_quando_nao_acha_o_texto(tmp_path, capsys):
    """O aviso é hook de abertura: ele avisa alto, mas não impede ninguém de trabalhar.

    Um hook de sessão que sai diferente de zero por causa de um texto fora do
    lugar transformaria uma lei em travamento — e a resposta a um travamento é
    desligar o hook, que é como um guarda morre.
    """
    raiz = _cenario(tmp_path)
    (raiz / "CLAUDE.md").write_text("# CLAUDE.md\n", encoding="utf-8")
    assert padrao.aviso(raiz) == 0
    assert "PADRÃO DE TRABALHO" in capsys.readouterr().out
