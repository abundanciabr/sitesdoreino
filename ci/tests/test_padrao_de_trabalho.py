"""Prova que compactar expressão não apaga obrigações, portas ou tetos."""

from __future__ import annotations

import shutil
import subprocess
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
    arquivos = [padrao.FONTE, "CLAUDE.md", "AGENTS.md", *padrao.PORTAS]
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


def test_indice_historico_nao_e_porta_mas_entradas_diretas_continuam_guardadas(tmp_path):
    assert "RITOS.md" not in padrao.PORTAS
    raiz = _cenario(tmp_path, **{"AGENTS.md": ("CAMINHO-DOURADO.md", "RITOS.md")})
    _falha(padrao.conferir(raiz), "entrada direta AGENTS.md")


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
        _cenario(tmp_path, **{padrao.FONTE: ("#### 7. Faça o passe de remoção", "#### 7. Limpeza")})
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
                padrao.FONTE: (
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
            **{padrao.FONTE: (padrao.TITULO, "## Um aviso qualquer\n\nTexto.\n\n" + padrao.TITULO)},
        )
    )
    _falha(relatorio, "é a primeira seção")


def test_costura_apagada_reprova(tmp_path):
    """Sem a costura 2, a regra 4 vira desculpa para não abrir a caixa de pergunta."""
    relatorio = padrao.conferir(
        _cenario(
            tmp_path,
            **{padrao.FONTE: ("A regra 4 distingue decisões do agente das decisões exclusivas do mantenedor.", "O agente decide sempre.")},
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

    As entradas dos agentes são carregadas antes da consulta da receita. Nenhuma regra some
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
    (raiz / padrao.FONTE).write_text("# CLAUDE.md\n\n## Outra coisa\n\nTexto.\n", encoding="utf-8")
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
    (raiz / padrao.FONTE).write_text("# CLAUDE.md\n", encoding="utf-8")
    assert padrao.aviso(raiz) == 0
    assert "PADRÃO DE TRABALHO" in capsys.readouterr().out


@pytest.mark.parametrize("nome,teto", padrao.TETOS_EM_BYTES.items())
def test_teto_mede_bytes_utf8_e_nao_caracteres(tmp_path, nome, teto):
    raiz = _cenario(tmp_path)
    p = raiz / nome
    conteudo = p.read_bytes()
    # A conta parte do que o portão MEDE (o blob, com CRLF normalizado), não do
    # que está no disco: numa checkout Windows os dois diferem em centenas de
    # bytes e o "á" a mais deixaria de estourar o teto justamente aqui.
    medido = len(conteudo.replace(b"\r\n", b"\n"))
    p.write_bytes(conteudo + ("á" * ((teto - medido) // 2 + 1)).encode())
    _falha(padrao.conferir(raiz), f"teto de {nome}")


@pytest.mark.parametrize("nome,teto", padrao.TETOS_EM_BYTES.items())
def test_teto_mede_o_blob_e_nao_o_fim_de_linha_do_disco(tmp_path, nome, teto):
    """O mesmo arquivo com CRLF e com LF tem de dar a MESMA medida.

    Com `core.autocrlf=true` o Windows guarda CRLF e o Git guarda LF: medir o
    disco reprovava em toda máquina do mantenedor e passava na CI pelos mesmos
    bytes. Portão que mente localmente é portão que se aprende a ignorar, e
    este nasceu VERMELHO contra a versão que lia `read_bytes()` cru.
    """
    raiz = _cenario(tmp_path)
    p = raiz / nome
    lf = p.read_bytes().replace(b"\r\n", b"\n")
    p.write_bytes(lf)
    com_lf = next(r for r in padrao.conferir(raiz).resultados if r.nome == f"teto de {nome}")
    p.write_bytes(lf.replace(b"\n", b"\r\n"))
    com_crlf = next(r for r in padrao.conferir(raiz).resultados if r.nome == f"teto de {nome}")
    assert com_lf.resumo == com_crlf.resumo, (com_lf.resumo, com_crlf.resumo)
    assert com_lf.estado == com_crlf.estado


@pytest.mark.parametrize("obrigacao", padrao.PEDRAS_ANGULARES)
def test_obrigacao_removida_reprova(tmp_path, obrigacao):
    import re
    raiz = _cenario(tmp_path)
    p = raiz / padrao.FONTE
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
    raiz = _cenario(tmp_path, **{"AGENTS.md": ("CAMINHO-DOURADO.md", "Leia o resumo")})
    _falha(padrao.conferir(raiz), "entrada direta AGENTS.md")


def test_entrada_que_restaura_a_ponte_claude_reprova(tmp_path):
    raiz = _cenario(tmp_path)
    caminho = raiz / "AGENTS.md"
    caminho.write_text(caminho.read_text(encoding="utf-8") + "\nLeia `CLAUDE.md` antes de agir\n", encoding="utf-8")
    _falha(padrao.conferir(raiz), "entrada direta AGENTS.md")


def test_adaptador_com_regua_duplicada_reprova(tmp_path):
    raiz = _cenario(tmp_path)
    caminho = raiz / "CLAUDE.md"
    caminho.write_text(caminho.read_text(encoding="utf-8") + "\n" + padrao.TITULO, encoding="utf-8")
    _falha(padrao.conferir(raiz), "entrada direta CLAUDE.md")


def _executar_verificador_externo(tmp_path: Path, candidato: Path):
    base = tmp_path / "origem-base" / "ci"
    base.mkdir(parents=True)
    for nome in ("padrao_de_trabalho.py", "_nucleo.py"):
        shutil.copyfile(RAIZ / "ci" / nome, base / nome)
    return subprocess.run(
        [sys.executable, "-I", str(base / "padrao_de_trabalho.py"), "--candidato", str(candidato)],
        cwd=tmp_path, capture_output=True, text=True, encoding="utf-8", timeout=30,
    )


def test_origem_base_nao_executa_o_verificador_candidato(tmp_path):
    raiz = _cenario(tmp_path)
    candidato = raiz / "ci" / "padrao_de_trabalho.py"
    candidato.write_text("raise RuntimeError('a versão candidata não deve ser executada')\n", encoding="utf-8")
    resultado = _executar_verificador_externo(tmp_path, raiz)
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr


def test_origem_base_recusa_regressao_mesmo_com_verificador_candidato_autoaprovador(tmp_path):
    raiz = _cenario(tmp_path, **{padrao.FONTE: ('Rodou de verdade, com comando e saída real, ou escreva "NÃO RODEI".', "Sempre teste antes de entregar.")})
    candidato = raiz / "ci" / "padrao_de_trabalho.py"
    candidato.write_text("print('PASS')\n", encoding="utf-8")
    resultado = _executar_verificador_externo(tmp_path, raiz)
    assert resultado.returncode == 1, resultado.stdout + resultado.stderr
    assert "as exigências literais" in resultado.stdout


def test_modo_origem_base_recusa_executar_de_dentro_do_proprio_candidato():
    resultado = subprocess.run(
        [sys.executable, "-I", str(RAIZ / "ci" / "padrao_de_trabalho.py"), "--candidato", str(RAIZ)],
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert resultado.returncode == 2, resultado.stdout + resultado.stderr
    assert "dentro da árvore candidata" in resultado.stdout
