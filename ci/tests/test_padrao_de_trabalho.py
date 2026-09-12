"""Prova que compactar expressão não apaga obrigações, portas ou tetos."""

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
    arquivos = ["CLAUDE.md", "AGENTS.md", *padrao.PORTAS]
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


def test_o_aviso_de_sessao_lista_as_dez_regras(capsys):
    padrao.aviso(RAIZ)
    saida = capsys.readouterr().out
    for regra in padrao.REGRAS:
        assert regra in saida, f"o aviso de abertura não cita a regra: {regra}"


# ---------------------------------------------------------------------------
# As cinco mutilações — cada uma tem de dar vermelho
# ---------------------------------------------------------------------------


def test_regra_apagada_reprova(tmp_path):
    relatorio = padrao.conferir(
        _cenario(tmp_path, **{"CLAUDE.md": ("#### 7. Faça o passe de remoção", "#### 7. Limpeza")})
    )
    _falha(relatorio, "as 10 regras, íntegras")


def test_exigencia_parafraseada_reprova(tmp_path):
    """Os 10 títulos intactos, e a lei esvaziada mesmo assim.

    Este é o modo de falha que o portão existe para pegar: "sempre teste antes
    de entregar" diz a mesma coisa em espírito e não obriga a nada. O que
    obriga é a frase literal.
    """
    relatorio = padrao.conferir(
        _cenario(
            tmp_path,
            **{
                "CLAUDE.md": (
                    'Rodou de verdade, com comando e saída real, ou escreva "NÃO RODEI".',
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
            **{"CLAUDE.md": ("A regra 4 distingue decisões do agente das decisões exclusivas do mantenedor.", "O agente decide sempre.")},
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
        caminho.read_text(encoding="utf-8") + "\n" + "história " * (padrao.TETOS_EM_BYTES["CLAUDE.md"] // 8),
        encoding="utf-8",
    )
    _falha(padrao.conferir(raiz), "teto de CLAUDE.md")


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


@pytest.mark.parametrize("nome,teto", padrao.TETOS_EM_BYTES.items())
def test_teto_mede_bytes_utf8_e_nao_caracteres(tmp_path, nome, teto):
    raiz = _cenario(tmp_path)
    p = raiz / nome
    conteudo = p.read_bytes()
    p.write_bytes(conteudo + ("á" * ((teto - len(conteudo)) // 2 + 1)).encode())
    _falha(padrao.conferir(raiz), f"teto de {nome}")


@pytest.mark.parametrize("obrigacao", padrao.PEDRAS_ANGULARES)
def test_obrigacao_removida_reprova(tmp_path, obrigacao):
    import re
    raiz = _cenario(tmp_path)
    p = raiz / "CLAUDE.md"
    texto = p.read_text(encoding="utf-8")
    padrao_frase = r"\s+".join(re.escape(s) for s in obrigacao.split())
    texto, n = re.subn(padrao_frase, "", texto)
    assert n >= 1
    p.write_text(texto, encoding="utf-8")
    _falha(padrao.conferir(raiz), "as exigências literais")


def test_constituicao_preserva_a_lei_canonica_compacta():
    constituicao = (RAIZ / 'CONSTITUICAO.md').read_text(encoding='utf-8')
    lei = constituicao.split('## Lei 10', 1)[1].split('## Definição de Pronto', 1)[0]
    assert 'forma compacta, sem perda das obrigações' in lei
    assert 'AGENTS.md' in lei
    assert 'escrito por inteiro' not in lei


def test_codex_sem_ponteiro_canonico_reprova(tmp_path):
    raiz = _cenario(tmp_path, **{"AGENTS.md": ("Leia `CLAUDE.md` antes de agir", "Leia o resumo")})
    _falha(padrao.conferir(raiz), "Codex aponta para a lei")
