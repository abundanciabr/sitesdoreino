"""Suíte adversarial do guarda-dos-guardas — ele REPROVA quando deve?

Um portão que nunca fica vermelho é indistinguível de um portão desligado, e a
única forma de saber a diferença é obrigá-lo a reprovar de propósito. Por isso
quase todo teste aqui monta um repositório de mentira (com git de verdade,
porque o varredor pergunta ao git) e o sabota de um jeito específico.

O par verde de cada prova vermelha também está aqui: um guarda que reprovasse
SEMPRE passaria em todos os testes vermelhos e seria desligado na primeira
urgência.

E há dois testes contra o repositório REAL — é por eles que este portão chega
aos workflows `muralhas` e `alarme-main`, que já rodam
`python ci/ci.py --apenas testador` (= `pytest ci/tests`). Nenhuma linha de
YAML foi necessária.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

CI = Path(__file__).resolve().parents[1]
if str(CI) not in sys.path:
    sys.path.insert(0, str(CI))

import guarda_dos_guardas as gg  # noqa: E402
from _nucleo import ErroDeInstrumentacao, Estado, raiz_do_repo  # noqa: E402

RAIZ = raiz_do_repo()

GUARDA_QUE_MORDE = '''\
"""Guarda de mentira que morde de verdade."""


def test_o_invariante_vale():
    assert 1 + 1 == 2
'''

IMPORTLINTER = """\
[importlinter]
root_package = falso

[importlinter:contract:independencia]
name = pix e card não se enxergam
type = independence
modules =
    falso.pix
    falso.card
"""


# --------------------------------------------------------- repositório falso


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=str(repo),
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _escrever(repo: Path, relativo: str, conteudo: str) -> Path:
    destino = repo / relativo
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(conteudo, encoding="utf-8", newline="\n")
    return destino


def _documento(blocos: str) -> str:
    return "# INVARIANTES de mentira\n\n---\n\n" + blocos


def _bloco(codigo: str, guardas: str, celula: str = "falsa") -> str:
    return (
        f"### [{codigo}] Invariante de mentira\n"
        f"- **O quê:** alguma coisa.\n"
        f"- **Por quê:** algum motivo.\n"
        f"- **Teste-Guarda:** {guardas} — descrição do que ele prova.\n"
        f"- **Célula dona:** {celula}\n\n"
    )


def _divida(linhas: list[str]) -> str:
    corpo = "\n".join(linhas)
    return f"# dívida de mentira\n# TOTAL: {len(linhas)}\n{corpo}\n"


# Duas células, dois guardas — de propósito. Com UM guarda só, apagá-lo cairia
# no ramo "zero guardas em disco ⇒ ERROR" e o teste da regra 1 mediria outra
# coisa. O repositório real tem 47; o de mentira precisa de pelo menos dois
# para que remover um continue sendo "faltou um", não "não há o que medir".
BLOCO_F1 = _bloco("INV-F1", "`services/falsa/tests/test_inv_f1.py`")
BLOCO_F2 = _bloco("INV-F2", "`services/outra/tests/test_inv_f2.py`", "outra")


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """Repositório de mentira NO ESTADO CORRETO: dois invariantes, dois guardas.

    Tem git de verdade porque `arquivos_versionados` pergunta ao git — testar
    contra um mock do git testaria o mock.
    """
    raiz = tmp_path / "repo-falso"
    raiz.mkdir()
    _git(raiz, "init", "-q")
    _git(raiz, "config", "user.email", "falso@exemplo.invalid")
    _git(raiz, "config", "user.name", "Falso")

    _escrever(raiz, "INVARIANTES.md", _documento(BLOCO_F1 + BLOCO_F2))
    _escrever(raiz, "services/falsa/tests/test_inv_f1.py", GUARDA_QUE_MORDE)
    _escrever(raiz, "services/outra/tests/test_inv_f2.py", GUARDA_QUE_MORDE)
    _escrever(raiz, gg.DIVIDA, _divida([]))
    _git(raiz, "add", "-A")
    return raiz


def _estado(raiz: Path) -> Estado:
    return gg.rodar(raiz).estado


def _detalhe(raiz: Path) -> str:
    relatorio = gg.rodar(raiz)
    return "\n".join(r.resumo + "\n" + r.detalhe for r in relatorio.resultados)


# ------------------------------------------------------------- o par verde


def test_o_repo_falso_intacto_passa(repo: Path) -> None:
    """Sem isto, um portão que reprova SEMPRE passaria em todo o resto."""
    assert _estado(repo) is Estado.PASS


def test_o_repositorio_real_passa_hoje() -> None:
    """A `main` de hoje tem de ficar VERDE — senão este portão nasce inútil.

    47 guardas de célula em disco contra 12 linhas `Teste-Guarda:` era a
    situação medida em 25/08/2026. É por isso que o item 5 é uma CATRACA com
    linha de base (`ci/guardas-nao-declarados.txt`) em vez de um inverso duro:
    inverso duro nasceria vermelho e levaria a `main` junto.
    """
    relatorio = gg.rodar(RAIZ)
    assert relatorio.estado is Estado.PASS, relatorio.render()


def test_o_repositorio_real_mede_de_verdade() -> None:
    """PASS por não ter medido nada é o falso-verde do INV-CI01.

    Aqui o veredito verde é amarrado aos números que o sustentam: se um dia o
    parse parar de casar, ou o varredor devolver menos guardas do que existem,
    este teste cai antes de o verde virar mentira.
    """
    invariantes = gg.invariantes_declarados(
        (RAIZ / gg.DOCUMENTO).read_text(encoding="utf-8")
    )
    assert len(invariantes) >= 12
    declarados = {alvo for inv in invariantes for alvo in inv.guardas}
    assert "services/pagamentos/.importlinter" in declarados
    assert "ci/guarda-de-segredos.sh" in declarados
    assert "services/checkout/tests/test_inv_p1_snapshot.py" in declarados

    em_disco = [
        a for a in gg.arquivos_versionados(RAIZ) if gg.RE_GUARDA_DE_CELULA.fullmatch(a)
    ]
    assert len(em_disco) >= 47
    divida = gg.ler_divida(RAIZ)
    assert set(em_disco) - declarados <= set(divida.caminhos)


# ------------------------------------- regra 1: o guarda declarado sumiu


def test_guarda_declarado_que_sumiu_do_disco_e_FAIL(repo: Path) -> None:
    (repo / "services/falsa/tests/test_inv_f1.py").unlink()
    assert _estado(repo) is Estado.FAIL
    assert "não existem em disco" in _detalhe(repo)


def test_guarda_declarado_renomeado_sem_atualizar_o_documento_e_FAIL(
    repo: Path,
) -> None:
    _git(
        repo,
        "mv",
        "services/falsa/tests/test_inv_f1.py",
        "services/falsa/tests/test_inv_f1_novo_nome.py",
    )
    # o documento continua citando o nome velho
    assert _estado(repo) is Estado.FAIL
    assert "não existem em disco" in _detalhe(repo)


def test_uma_linha_com_DOIS_caminhos_e_medida_inteira(repo: Path) -> None:
    """INV-P11 cita dois arquivos numa linha só — o segundo não pode escapar."""
    _escrever(
        repo,
        "INVARIANTES.md",
        _documento(
            _bloco(
                "INV-F1",
                "`services/falsa/tests/test_inv_f1.py` + "
                "`services/falsa/tests/test_inv_f9.py`",
            )
            + BLOCO_F2
        ),
    )
    _git(repo, "add", "-A")
    assert _estado(repo) is Estado.FAIL
    assert "test_inv_f9.py" in _detalhe(repo)


# --------------------------------- regra 2 e 3: o guarda existe mas não morde


def test_corpo_do_teste_trocado_por_pass_e_FAIL(repo: Path) -> None:
    _escrever(
        repo,
        "services/falsa/tests/test_inv_f1.py",
        "def test_o_invariante_vale():\n    pass\n",
    )
    assert _estado(repo) is Estado.FAIL
    assert "corpo vazio" in _detalhe(repo)


@pytest.mark.parametrize("corpo", ["    ...\n", "    return\n", '    """só doc."""\n'])
def test_corpo_so_com_reticencias_return_ou_docstring_e_FAIL(
    repo: Path, corpo: str
) -> None:
    _escrever(
        repo,
        "services/falsa/tests/test_inv_f1.py",
        "def test_o_invariante_vale():\n" + corpo,
    )
    assert _estado(repo) is Estado.FAIL


@pytest.mark.parametrize("marca", ["skip", "skipif(True, reason='x')", "xfail"])
def test_marca_que_desliga_o_teste_e_FAIL(repo: Path, marca: str) -> None:
    _escrever(
        repo,
        "services/falsa/tests/test_inv_f1.py",
        "import pytest\n\n\n"
        f"@pytest.mark.{marca}\n"
        "def test_o_invariante_vale():\n    assert 1 + 1 == 2\n",
    )
    assert _estado(repo) is Estado.FAIL
    assert "decorado com" in _detalhe(repo)


def test_pytestmark_de_modulo_tambem_e_FAIL(repo: Path) -> None:
    """Desligar o arquivo inteiro numa linha é o jeito mais silencioso de todos."""
    _escrever(
        repo,
        "services/falsa/tests/test_inv_f1.py",
        "import pytest\n\npytestmark = pytest.mark.skip('depois eu volto')\n\n\n"
        "def test_o_invariante_vale():\n    assert 1 + 1 == 2\n",
    )
    assert _estado(repo) is Estado.FAIL
    assert "pytestmark" in _detalhe(repo)


def test_arquivo_de_guarda_sem_nenhum_def_test_e_FAIL(repo: Path) -> None:
    _escrever(
        repo,
        "services/falsa/tests/test_inv_f1.py",
        "def helper_que_nao_e_teste():\n    assert True\n",
    )
    assert _estado(repo) is Estado.FAIL
    assert "não testa nada" in _detalhe(repo)


def test_guarda_da_divida_tambem_precisa_morder(repo: Path) -> None:
    """A linha de base isenta de DECLARAÇÃO, jamais de MORDER.

    Sem isto a dívida viraria um interruptor: bastava listar o arquivo lá e
    esvaziá-lo. É o teste que separa 'catraca' de 'decoração'.
    """
    _escrever(
        repo, "services/falsa/tests/test_inv_devedor.py", "def test_x():\n    pass\n"
    )
    _escrever(
        repo,
        gg.DIVIDA,
        _divida(
            [
                "services/falsa/tests/test_inv_devedor.py :: "
                "dívida reconhecida no lote de 25/08/2026, invariante ainda não redigido"
            ]
        ),
    )
    _git(repo, "add", "-A")
    assert _estado(repo) is Estado.FAIL
    assert "corpo vazio" in _detalhe(repo)


def test_guarda_da_divida_que_morde_continua_verde(repo: Path) -> None:
    _escrever(repo, "services/falsa/tests/test_inv_devedor.py", GUARDA_QUE_MORDE)
    _escrever(
        repo,
        gg.DIVIDA,
        _divida(
            [
                "services/falsa/tests/test_inv_devedor.py :: "
                "dívida reconhecida no lote de 25/08/2026, invariante ainda não redigido"
            ]
        ),
    )
    _git(repo, "add", "-A")
    assert _estado(repo) is Estado.PASS


# ------------------------------------------- regra 4: o guarda que não é .py


@pytest.fixture()
def repo_com_importlinter(repo: Path) -> Path:
    _escrever(
        repo,
        "INVARIANTES.md",
        _documento(
            BLOCO_F1
            + BLOCO_F2
            + _bloco(
                "INV-F9",
                "`services/falsa/.importlinter` (`lint-imports` no `make ci`)",
            )
        ),
    )
    _escrever(repo, "services/falsa/.importlinter", IMPORTLINTER)
    _escrever(
        repo,
        "services/falsa/Makefile",
        "lint:\n\t@if [ -f .importlinter ]; then lint-imports; fi\n",
    )
    _git(repo, "add", "-A")
    return repo


def test_importlinter_presente_e_invocado_e_PASS(repo_com_importlinter: Path) -> None:
    assert _estado(repo_com_importlinter) is Estado.PASS


def test_apagar_o_importlinter_e_FAIL(repo_com_importlinter: Path) -> None:
    """A prova que dá sentido ao portão inteiro.

    `@if [ -f .importlinter ]; then lint-imports; fi` faz o `make ci` continuar
    VERDE quando o arquivo some — o `if` some junto com ele. Só de fora dá para
    ver que o guarda do INV-P9 evaporou.
    """
    (repo_com_importlinter / "services/falsa/.importlinter").unlink()
    assert _estado(repo_com_importlinter) is Estado.FAIL


def test_importlinter_vazio_e_FAIL(repo_com_importlinter: Path) -> None:
    _escrever(repo_com_importlinter, "services/falsa/.importlinter", "\n\n")
    assert _estado(repo_com_importlinter) is Estado.FAIL
    assert "vazio" in _detalhe(repo_com_importlinter)


def test_importlinter_sem_contrato_declarado_e_FAIL(
    repo_com_importlinter: Path,
) -> None:
    _escrever(
        repo_com_importlinter, "services/falsa/.importlinter", "# um dia eu escrevo\n"
    )
    assert _estado(repo_com_importlinter) is Estado.FAIL
    assert "não declara contrato" in _detalhe(repo_com_importlinter)


def test_importlinter_que_o_Makefile_nao_invoca_e_FAIL(
    repo_com_importlinter: Path,
) -> None:
    """Arquivo presente e ninguém rodando é a mesma coisa que arquivo ausente."""
    _escrever(repo_com_importlinter, "services/falsa/Makefile", "lint:\n\tblack .\n")
    assert _estado(repo_com_importlinter) is Estado.FAIL
    assert "não invoca" in _detalhe(repo_com_importlinter)


def test_guarda_shell_vazio_e_FAIL(repo: Path) -> None:
    _escrever(
        repo,
        "INVARIANTES.md",
        _documento(BLOCO_F1 + BLOCO_F2 + _bloco("INV-F8", "`ci/guarda-de-mentira.sh`")),
    )
    _escrever(repo, "ci/guarda-de-mentira.sh", "   \n")
    _git(repo, "add", "-A")
    assert _estado(repo) is Estado.FAIL


# ------------------------------------------------- regra 5: a catraca (INVERSO)


def test_guarda_novo_nao_declarado_e_FAIL(repo: Path) -> None:
    """A propriedade (ii) do despacho: dívida nova nasce vermelha."""
    _escrever(repo, "services/falsa/tests/test_inv_novo.py", GUARDA_QUE_MORDE)
    _git(repo, "add", "-A")
    assert _estado(repo) is Estado.FAIL
    assert "test_inv_novo.py" in _detalhe(repo)


def test_guarda_novo_declarado_no_documento_e_PASS(repo: Path) -> None:
    """O caminho CERTO de pagar: escrever o invariante."""
    _escrever(repo, "services/falsa/tests/test_inv_novo.py", GUARDA_QUE_MORDE)
    _escrever(
        repo,
        "INVARIANTES.md",
        _documento(
            BLOCO_F1
            + BLOCO_F2
            + _bloco("INV-F3", "`services/falsa/tests/test_inv_novo.py`")
        ),
    )
    _git(repo, "add", "-A")
    assert _estado(repo) is Estado.PASS


def test_divida_que_encolhe_e_sempre_permitida(repo: Path) -> None:
    """Linha que sobrou porque o arquivo sumiu não pode reprovar ninguém."""
    _escrever(
        repo,
        gg.DIVIDA,
        _divida(
            [
                "services/falsa/tests/test_inv_que_ja_sumiu.py :: "
                "dívida antiga; o arquivo foi removido em outro despacho"
            ]
        ),
    )
    _git(repo, "add", "-A")
    relatorio = gg.rodar(repo)
    assert relatorio.estado is Estado.PASS
    assert "quitada" in relatorio.render()


def test_arquivo_nao_versionado_nao_e_enxergado(repo: Path) -> None:
    """O varredor mede o REPOSITÓRIO, não o disco — e isso é documentado.

    Consequência aceita: guarda criado e não adicionado ao índice é invisível
    localmente. Na CI tudo está commitado, e o rito da casa manda `git add` por
    arquivo. Este teste existe para que a consequência seja uma DECISÃO
    registrada, não uma surpresa de alguém em 2027.
    """
    _escrever(repo, "services/falsa/tests/test_inv_fantasma.py", GUARDA_QUE_MORDE)
    assert _estado(repo) is Estado.PASS  # ainda não foi `git add`
    _git(repo, "add", "-A")
    assert _estado(repo) is Estado.FAIL  # agora existe para o repositório


# -------------------------------------- ERROR: não medir nunca vira PASS


def test_documento_ausente_e_ERROR(repo: Path) -> None:
    (repo / "INVARIANTES.md").unlink()
    assert _estado(repo) is Estado.ERROR


def test_documento_sem_nenhuma_linha_teste_guarda_e_ERROR(repo: Path) -> None:
    """Zero blocos parseados não é zero violações — é o instrumento cego."""
    _escrever(repo, "INVARIANTES.md", "# INVARIANTES\n\nprosa e mais nada.\n")
    _git(repo, "add", "-A")
    assert _estado(repo) is Estado.ERROR


def test_bloco_teste_guarda_sem_caminho_e_ERROR(repo: Path) -> None:
    _escrever(
        repo,
        "INVARIANTES.md",
        _documento(_bloco("INV-F1", "revisão manual do time, sem arquivo")),
    )
    _git(repo, "add", "-A")
    assert _estado(repo) is Estado.ERROR


def test_arquivo_de_divida_ausente_e_ERROR_nao_divida_vazia(repo: Path) -> None:
    """Apagar a linha de base não pode ser um caminho para ficar verde."""
    (repo / gg.DIVIDA).unlink()
    assert _estado(repo) is Estado.ERROR


def test_divida_sem_total_e_ERROR(repo: Path) -> None:
    _escrever(repo, gg.DIVIDA, "# sem total\n")
    _git(repo, "add", "-A")
    assert _estado(repo) is Estado.ERROR


def test_total_que_nao_bate_com_as_linhas_e_ERROR(repo: Path) -> None:
    """O anti-recarimbo: acrescentar linha exige mexer no número, e o diff mostra."""
    _escrever(
        repo,
        gg.DIVIDA,
        "# TOTAL: 0\nservices/falsa/tests/test_inv_x.py :: motivo suficientemente longo\n",
    )
    _git(repo, "add", "-A")
    assert _estado(repo) is Estado.ERROR


def test_divida_sem_motivo_escrito_e_ERROR(repo: Path) -> None:
    _escrever(repo, gg.DIVIDA, "# TOTAL: 1\nservices/falsa/tests/test_inv_x.py\n")
    _git(repo, "add", "-A")
    assert _estado(repo) is Estado.ERROR


def test_divida_com_motivo_de_carimbo_e_ERROR(repo: Path) -> None:
    _escrever(
        repo, gg.DIVIDA, "# TOTAL: 1\nservices/falsa/tests/test_inv_x.py :: TODO\n"
    )
    _git(repo, "add", "-A")
    assert _estado(repo) is Estado.ERROR


def test_divida_apontando_para_fora_dos_guardas_e_ERROR(repo: Path) -> None:
    """A lista não pode virar interruptor geral de silenciar arquivo."""
    _escrever(
        repo,
        gg.DIVIDA,
        "# TOTAL: 1\nci/guarda-de-segredos.sh :: quero calar este aqui também\n",
    )
    _git(repo, "add", "-A")
    assert _estado(repo) is Estado.ERROR


def test_divida_com_caminho_repetido_e_ERROR(repo: Path) -> None:
    _escrever(
        repo,
        gg.DIVIDA,
        "# TOTAL: 2\n"
        "services/falsa/tests/test_inv_x.py :: primeiro motivo bem escrito aqui\n"
        "services/falsa/tests/test_inv_x.py :: segundo motivo bem escrito aqui\n",
    )
    _git(repo, "add", "-A")
    assert _estado(repo) is Estado.ERROR


def test_guarda_que_nao_parseia_e_ERROR_nao_FAIL(repo: Path) -> None:
    """Arquivo ilegível é medição impossível (2), não violação medida (1)."""
    _escrever(
        repo,
        "services/falsa/tests/test_inv_f1.py",
        "def test_(:\n  isto nao e python\n",
    )
    assert _estado(repo) is Estado.ERROR


def test_zero_guardas_em_disco_e_ERROR(repo: Path) -> None:
    """Nenhum `test_inv_*` versionado não é 'tudo declarado' — é medir o nada."""
    (repo / "services/falsa/tests/test_inv_f1.py").unlink()
    (repo / "services/outra/tests/test_inv_f2.py").unlink()
    _escrever(repo, "INVARIANTES.md", _documento(_bloco("INV-F1", "`ci/algum.sh`")))
    _escrever(repo, "ci/algum.sh", "echo ok\n")
    _git(repo, "add", "-A")  # `-A` também tira do índice o que sumiu do disco
    assert _estado(repo) is Estado.ERROR


def test_fora_de_um_repositorio_git_e_ERROR(tmp_path: Path) -> None:
    """Git que não responde é ERROR, nunca lista vazia de arquivos."""
    with pytest.raises(ErroDeInstrumentacao):
        gg.arquivos_versionados(tmp_path)


# ------------------------------------------------ o varredor compartilhado


def test_o_varredor_nao_entra_em_worktree_de_agente(repo: Path) -> None:
    """A regressão que motivou o conserto de `test_indice_de_armadilhas.py`.

    `.claude/worktrees/<nome>/` é onde o harness guarda o clone de OUTRA
    sessão. Um varredor de disco (`rglob`) entra lá e passa a acusar o
    conteúdo alheio; o git nunca entra, porque nada daquilo é rastreado — e
    numa pasta que é um repositório à parte ele nem desce.
    """
    intruso = repo / ".claude" / "worktrees" / "sessao-velha" / "ci" / "tests"
    intruso.mkdir(parents=True)
    # A sentinela é montada em tempo de execução de propósito: escrita literal,
    # ela viraria uma citação PENDURADA de verdade neste arquivo — e o
    # `test_toda_referencia_a_uma_armadilha_resolve`, que agora enxerga tudo o
    # que o git rastreia, reprovaria com razão. Foi ele mesmo quem pegou isto.
    secao = "§"
    (intruso / "test_indice_de_armadilhas.py").write_text(
        f"# ver ARMADILHAS {secao}99.99 para detalhes\n", encoding="utf-8"
    )
    (repo / ".claude" / "worktrees" / "sessao-velha" / ".git").write_text(
        "gitdir: ../../../.git/worktrees/sessao-velha\n", encoding="utf-8"
    )

    varridos = gg.arquivos_versionados(repo)
    assert not [p for p in varridos if p.startswith(".claude/")]
    assert "INVARIANTES.md" in varridos

    # e o varredor de disco antigo VERIA — é o contraste que prova o conserto
    do_disco = [
        p.relative_to(repo).as_posix()
        for p in repo.rglob("*")
        if p.is_file() and ".git\\" not in str(p) and "/.git/" not in p.as_posix()
    ]
    assert any(p.startswith(".claude/") for p in do_disco)


def test_o_varredor_devolve_caminhos_posix_relativos(repo: Path) -> None:
    varridos = gg.arquivos_versionados(repo)
    assert "services/falsa/tests/test_inv_f1.py" in varridos
    assert all(not p.startswith("/") and "\\" not in p for p in varridos)


# --------------------------------------------- o parse, isolado do resto


def test_parse_ignora_crase_que_nao_e_caminho() -> None:
    """`make ci`, `lint-imports`, `FAIL`, `pix.js`/`cartao.js` não são arquivos.

    O INV-P7 real escreve ``revisão de `pix.js`/`cartao.js` `` — a barra está
    FORA das crases. Se o parse a lesse como caminho, o portão nasceria
    vermelho por um falso positivo, e ninguém confia num portão assim.
    """
    texto = _documento(
        _bloco(
            "INV-F7",
            "`services/falsa/tests/test_inv_f7.py` + revisão de `pix.js`/`cartao.js`, "
            "`lint-imports` no `make ci`, estado `FAIL`",
        )
    )
    (inv,) = gg.invariantes_declarados(texto)
    assert inv.guardas == ["services/falsa/tests/test_inv_f7.py"]
    assert inv.codigo == "INV-F7"


def test_parse_do_documento_real_casa_os_blocos_de_hoje() -> None:
    """Inventário por igualdade exata dos invariantes declarados hoje.

    Ele não julga se o invariante é bom — julga se o PARSE continua casando o
    documento real. Falhar quando um invariante nasce é o comportamento
    pretendido: obriga quem escreve o próximo a passar por aqui e conferir que
    o parser ainda enxerga todos.

    **Acrescentar o código novo a esta lista é manutenção de inventário, não
    afrouxamento** — mesma distinção de `armadilhas/089`. Trocar o `==` por
    `<=`, ou apagar a asserção, seria afrouxar: mataria o único mecanismo que
    força a revisão.
    """
    invariantes = gg.invariantes_declarados(
        (RAIZ / gg.DOCUMENTO).read_text(encoding="utf-8")
    )
    codigos = [inv.codigo for inv in invariantes]
    assert codigos == [
        "INV-P1",
        "INV-P2",
        "INV-P3",
        "INV-P4",
        "INV-P5",
        "INV-P6",
        "INV-P7",
        "INV-P8",
        "INV-P9",
        "INV-P10",
        "INV-P11",
        # Nasceu na gênese da célula `admin` (25/08/2026): um único assinante
        # do cookie de sessão do site.
        "INV-P12",
        # Reversão do mantenedor em 31/08/2026, célula `sugestoes`: quem foi
        # REEMBOLSADO não entra, e a porta diz por quê. Entrou aqui pagando uma
        # linha da dívida de `ci/guardas-nao-declarados.txt` — a do guarda
        # antigo, que afirmava o CONTRÁRIO e, pior, tinha parado de medir o que
        # dizia medir desde 28/08 (`armadilhas/252`).
        "INV-SUG09",
        # EVO-40 (25/08/2026), célula `sugestoes`: nada sai de `planejado` para
        # `em_desenvolvimento` sem ChangeSpec aprovado registrado. Entrou aqui
        # pagando uma linha da dívida de `ci/guardas-nao-declarados.txt`, que é
        # exatamente o que a catraca existe para provocar.
        "INV-SUG10",
        # Nasceu com a porta da célula `admin` (25/08/2026): autorização falha
        # fechada, e é o único ponto de autorização daquela célula.
        #
        # A ordem desta lista é a de APARIÇÃO no documento, não a numérica —
        # foi o que este teste provou em 25/08, quando duas sessões paralelas
        # inseriram blocos no mesmo arquivo e a lista ficou com um código
        # repetido. O inventário pegou na hora.
        "INV-P13",
        # Pedido do mantenedor (28/08/2026): um link público do mapa técnico
        # do projeto (`painel/ia/`), para mandar a IAs externas sem login.
        "INV-P14",
        # Fecha a metade que faltava do rito de contrato do 502 (29/08/2026):
        # o contrato passou a declarar a falha do provedor nos PRs 417/420, e
        # esta é a regra que aquele status protege — falha do Mercado Pago
        # responde 502, nunca 2xx, e o consumidor repete com a MESMA chave.
        "INV-P15",
        # Fase 1 do plano de notificações (25/08/2026), célula `sugestoes`: a
        # identidade cunhada aqui guarda o id da identidade da PLATAFORMA, que a
        # resposta do contrato já entregava e a porta descartava. Sem ele nenhum
        # evento da Caixa consegue endereçar uma pessoa fora dela.
        "INV-SUG11",
        # Nasceu no Rito de Contrato do sininho (26/08/2026): a carta endereça
        # pelo id da plataforma, quem não tem um é pulado, e quem MODERA sem um
        # reverte a transação inteira.
        "INV-SUG12",
        "INV-SUG13",
        # Nasceram na gênese da célula `notificacoes` (26/08/2026, Fase 3 do
        # plano do sininho): a caixa escreve uma linha por carta com o contador
        # andando junto, e o que ela consome casa com o contrato congelado.
        "INV-NOT1",
        "INV-NOT2",
        # As três leis da economia da célula `gamificacao` (30/08/2026,
        # TAR-042). Os guardas nasceram no PR #636 e reprovavam de verdade,
        # mas viviam fora da lista: a regra 5 só vigia o que está declarado,
        # então apagar um deles não acusaria nada. Aparecem antes do
        # INV-CI01 porque a ordem é a de APARIÇÃO no documento, e eles
        # fecham a seção da plataforma.
        "INV-GAM1",
        "INV-GAM2",
        "INV-GAM3",
        # Os sete de justiça da fila, célula `encomendas` (04/09/2026, TAR-121,
        # degrau 2.3 da escada). Nasceram juntos porque a lei os agrupa no degrau
        # do MOTOR (`DECISAO-fila-do-primeiro-dolar.md` §5): J1 e J2 as duas
        # travas de oferta pendente, J3 a regra de ordem, J4 o lugar na fila, J5
        # o nível mínimo, J6 a memória por encomenda, J7 quem está trabalhando.
        "INV-ENC-J1",
        "INV-ENC-J2",
        "INV-ENC-J3",
        "INV-ENC-J4",
        "INV-ENC-J5",
        "INV-ENC-J6",
        "INV-ENC-J7",
        # Os três dos RELÓGIOS chegaram no degrau 2.4 (04/09/2026, TAR-122), e
        # com eles os dez de justiça estão completos: J8 o relógio da oferta que
        # congela fora da janela 8h–22h, J9 a encomenda que não espera na fila
        # além do prazo sem virar chamada aberta, J10 a reexecução que não cria
        # oferta nova — e, no mesmo invariante, a ausência de timer agendado, que
        # é o que faz a fila sobreviver a reinício, deploy e queda do Redis.
        "INV-ENC-J8",
        "INV-ENC-J9",
        "INV-ENC-J10",
        "INV-CUR-C2",
        # Os três da PORTA da célula `cursos` (05/09/2026, TAR-154, degrau 1.8
        # da escada): P1 nenhuma tela compara alunos, P2 a porta só abre por
        # laudo, P3 o checkpoint fechado até todas as pausas terem registro.
        "INV-CUR-P1",
        "INV-CUR-P2",
        "INV-CUR-P3",
        # O prazo do checkpoint, célula `cursos` (05/09/2026, TAR-155, degrau
        # 2.1 da escada): `prazo_em` = `enviado_em` + 24 h e não muda por API
        # nenhuma; o estouro se registra, nunca alonga.
        "INV-CUR-L3",
        # Os cinco do LAUDO, célula `cursos` (05/09/2026, TAR-156, degrau 2.2
        # da escada): L1 devolvido exige data de retorno de amanhã em diante,
        # L2 "reprovado" não existe em vocabulário nenhum, L5 a rubrica
        # completa (nota+frase) antes de qualquer campo livre, L6 exatamente
        # três forças (nenhuma genérica) e exatamente uma mudança (com aula
        # que existe no curso), L7 a pergunta de amanhã de manhã só aceita
        # `true`. L4 (nada de decisão/data/pergunta vem da IA) fica para o
        # degrau 2.3, quando `RascunhoDaIA` ganhar o corpo real.
        "INV-CUR-L1",
        "INV-CUR-L2",
        "INV-CUR-L5",
        "INV-CUR-L6",
        "INV-CUR-L7",
        "INV-CI01",
    ]


def test_problemas_do_guarda_aprova_um_guarda_de_verdade(tmp_path: Path) -> None:
    alvo = tmp_path / "test_inv_ok.py"
    alvo.write_text(
        textwrap.dedent(
            '''
            """doc do módulo."""
            import pytest


            @pytest.mark.parametrize("n", [1, 2])
            def test_alguma_coisa(n):
                """doc do teste — não é corpo vazio, porque tem assert depois."""
                assert n > 0
            '''
        ),
        encoding="utf-8",
    )
    assert gg.problemas_do_guarda(alvo, "test_inv_ok.py") == []


# ---------------------------------------------- integração com o runner


def test_o_portao_esta_registrado_no_runner() -> None:
    """Portão que o runner não conhece é portão que ninguém roda."""
    import ci as runner

    assert "guardas" in runner.PORTOES
    relatorio = runner.rodar(apenas=["guardas"])
    assert relatorio.estado is Estado.PASS, relatorio.render()


def test_a_linha_de_comando_do_portao_roda_sozinha() -> None:
    """`python ci/guarda_dos_guardas.py` — portão que não se invoca não é portão."""
    proc = subprocess.run(
        [sys.executable, str(CI / "guarda_dos_guardas.py")],
        cwd=str(RAIZ),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "guardas/inverso" in proc.stdout
