"""Guardas do índice das armadilhas — e das referências que apontam para ele.

Duas famílias de teste, com motivos diferentes:

1. **O índice está em dia.** Ele é gerado; gerado que ninguém confere volta a
   divergir na primeira entrada nova, e uma armadilha fora do índice é uma
   armadilha que ninguém acha — o mesmo efeito de ela não existir.
2. **Toda referência `§X.Y` ainda resolve.** O repositório cita armadilhas por
   número em mais de 200 lugares, 20 deles dentro de `services/**` — que a cerca
   (1 PR = 1 célula) proíbe reescrever num PR só. Por isso a âncora `§X.Y`
   continua sendo a forma canônica de citar, e a garantia de que ela aponta para
   algum lugar precisa ser MECÂNICA, não uma promessa do agente que particionou
   o arquivo.

Estes testes rodam dentro de `python ci/ci.py` (portão `testar-o-testador`) —
nenhum portão novo foi inventado para eles.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

CI = Path(__file__).resolve().parents[1]
if str(CI) not in sys.path:
    sys.path.insert(0, str(CI))

import indice_de_armadilhas as indice  # noqa: E402
from _nucleo import raiz_do_repo  # noqa: E402
from guarda_dos_guardas import arquivos_versionados  # noqa: E402

RAIZ = raiz_do_repo()

# Este próprio arquivo cita `§X.Y` em exemplos e mensagens; varrê-lo tornaria o
# guarda um teste sobre si mesmo.
ARQUIVO_DESTE_TESTE = Path(__file__).resolve()


def _entrada(pasta: Path, nome: str, titulo: str, sintoma: str = "") -> Path:
    corpo = f"# {titulo}\n"
    if sintoma:
        corpo += f"\n**Sintoma:** {sintoma}\n"
    caminho = pasta / nome
    caminho.write_text(corpo, encoding="utf-8", newline="\n")
    return caminho


@pytest.fixture()
def repo_falso(tmp_path: Path) -> Path:
    pasta = tmp_path / indice.PASTA
    pasta.mkdir()
    _entrada(pasta, "001-primeira.md", "3.1 `Erro: coisa` explodindo", "o comando morre.")
    _entrada(pasta, "002-segunda.md", "Entrada nova sem § histórico", "outro erro cru.")
    return tmp_path


# --------------------------------------------------------------- geração


def test_regenerar_cria_o_indice_e_e_idempotente(repo_falso: Path) -> None:
    """Rodar duas vezes não pode produzir um byte diferente.

    Gerador não-idempotente vira diff em todo PR e, pior, ensina o agente a
    ignorar a mudança do índice — que é justamente onde a entrada nova aparece.
    """
    assert indice.rodar(repo_falso, conferir=False) == 0
    destino = repo_falso / indice.PASTA / indice.NOME_DO_INDICE
    primeira = destino.read_bytes()

    assert indice.rodar(repo_falso, conferir=False) == 0
    assert destino.read_bytes() == primeira


def test_toda_entrada_vira_uma_linha_do_indice(repo_falso: Path) -> None:
    indice.rodar(repo_falso, conferir=False)
    texto = (repo_falso / indice.PASTA / indice.NOME_DO_INDICE).read_text(
        encoding="utf-8"
    )
    assert "001-primeira.md" in texto
    assert "002-segunda.md" in texto
    assert "**2 entradas**" in texto


def test_o_indice_nao_indexa_a_si_mesmo(repo_falso: Path) -> None:
    indice.rodar(repo_falso, conferir=False)
    indice.rodar(repo_falso, conferir=False)
    texto = (repo_falso / indice.PASTA / indice.NOME_DO_INDICE).read_text(
        encoding="utf-8"
    )
    assert "**2 entradas**" in texto


def test_o_id_historico_do_titulo_vira_a_coluna_de_de_para(repo_falso: Path) -> None:
    indice.rodar(repo_falso, conferir=False)
    linhas = (repo_falso / indice.PASTA / indice.NOME_DO_INDICE).read_text(
        encoding="utf-8"
    ).splitlines()
    da_primeira = next(ln for ln in linhas if "001-primeira.md" in ln)
    assert da_primeira.endswith("| §3.1 |")
    da_segunda = next(ln for ln in linhas if "002-segunda.md" in ln)
    assert da_segunda.endswith("| — |")


# --------------------------------------------------------------- conferência


def test_conferir_reprova_quando_uma_entrada_nova_nao_foi_indexada(
    repo_falso: Path,
) -> None:
    """FAIL (1), não ERROR: o instrumento mediu, o conteúdo é que está velho."""
    assert indice.rodar(repo_falso, conferir=False) == 0
    assert indice.rodar(repo_falso, conferir=True) == 0

    _entrada(repo_falso / indice.PASTA, "003-terceira.md", "Armadilha recém-nascida")
    assert indice.rodar(repo_falso, conferir=True) == 1


def test_conferir_nao_escreve_nada(repo_falso: Path) -> None:
    """`--conferir` é read-only: um portão que conserta esconde a violação."""
    indice.rodar(repo_falso, conferir=False)
    destino = repo_falso / indice.PASTA / indice.NOME_DO_INDICE
    destino.write_text("índice sabotado\n", encoding="utf-8", newline="\n")

    assert indice.rodar(repo_falso, conferir=True) == 1
    assert destino.read_text(encoding="utf-8") == "índice sabotado\n"


# --------------------------------------------------- ERROR nunca vira PASS


def test_pasta_ausente_e_ERROR_e_nao_indice_vazio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """[INV-CI01] 'não achei a pasta' é indistinguível de 'não há entradas'.

    Se isto virasse um índice vazio bem-sucedido, apagar `armadilhas/` deixaria
    a CI verde — a mesma família de falso-verde que este repositório inteiro
    combate. Medimos pelo `main`, que é o que produz o exit code de verdade.
    """
    monkeypatch.setattr(indice, "raiz_do_repo", lambda: tmp_path)
    assert indice.main([]) == 2


def test_pasta_vazia_e_ERROR(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / indice.PASTA).mkdir()
    monkeypatch.setattr(indice, "raiz_do_repo", lambda: tmp_path)
    assert indice.main([]) == 2


def test_entrada_sem_titulo_e_ERROR(
    repo_falso: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (repo_falso / indice.PASTA / "004-muda.md").write_text(
        "sem heading nenhum\n", encoding="utf-8", newline="\n"
    )
    monkeypatch.setattr(indice, "raiz_do_repo", lambda: repo_falso)
    assert indice.main(["--conferir"]) == 2


def test_conferir_do_repositorio_real_pela_linha_de_comando() -> None:
    """O caminho oficial (`python ci/indice_de_armadilhas.py --conferir`) roda.

    Testar só a função deixaria passar um script que estoura no argparse ou no
    import — portão que não consegue ser invocado não é portão.
    """
    proc = subprocess.run(
        [sys.executable, str(CI / "indice_de_armadilhas.py"), "--conferir"],
        cwd=str(RAIZ),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


# ------------------------------------- dois arquivos com o MESMO NNN (EVO-11)
#
# 24/08/2026: um ramo criou `armadilhas/078-guarda-de-imutabilidade...md`
# enquanto outra sessão mergeava `armadilhas/078-script-injetado...md` na main.
# `git rebase origin/main` juntou os dois SEM conflito — nomes diferentes,
# hunks diferentes, nada para o git reclamar — e a pasta ficou com dois `078-`.
# Só foi pego porque um humano-agente olhou a pasta com `ls` na mão. O índice
# era gerado em silêncio, com as duas linhas, como se estivesse tudo em ordem.


def test_dois_arquivos_com_o_mesmo_numero_sao_ERROR(
    repo_falso: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """ERROR (2), não FAIL (1): o índice não é medível enquanto o NNN for ambíguo.

    Um índice com duas linhas `078` não é "conteúdo desatualizado" — é uma
    numeração que deixou de identificar entrada, e toda citação
    `armadilhas/078` passa a apontar para dois lugares.
    """
    _entrada(repo_falso / indice.PASTA, "002-outra-coisa.md", "Colidiu com a 002")
    monkeypatch.setattr(indice, "raiz_do_repo", lambda: repo_falso)

    assert indice.main([]) == 2

    erro = capsys.readouterr().err
    assert "ERROR" in erro
    assert "002-segunda.md" in erro and "002-outra-coisa.md" in erro


def test_a_colisao_manda_pedir_o_numero_ao_almoxarife(
    repo_falso: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Dois guardas não podem se contradizer sobre o mesmo número.

    Até 30/08/2026 esta mensagem mandava escolher o número À MÃO ("renomeando a
    SUA entrada para o primeiro número acima de todos, hoje NNN" + um `git mv`)
    — e quem obedecia era reprovado pela `muralha-das-reservas` com "número
    escolhido à mão". Custou uma rodada de CI a TRÊS robôs no mesmo dia, e
    nenhum deles estava errado: a INSTRUÇÃO estava.

    Este teste é o que impede a contradição de voltar: a mensagem de colisão
    ensina o almoxarife (`python ci/reservar.py numero armadilha`), e NÃO ensina
    escolha manual.
    """
    _entrada(repo_falso / indice.PASTA, "002-outra-coisa.md", "Colidiu com a 002")
    monkeypatch.setattr(indice, "raiz_do_repo", lambda: repo_falso)

    assert indice.main([]) == 2
    erro = capsys.readouterr().err

    # (a) ensina o almoxarife — o MESMO conserto que a muralha-das-reservas exige
    assert "ci/reservar.py numero armadilha" in erro
    # (b) e continua dizendo o que fazer com o arquivo já escrito: renomear o
    #     arquivo E o campo do frontmatter, que precisam bater
    assert "armadilha:" in erro
    assert "python ci/indice_de_armadilhas.py" in erro

    # (c) e NÃO escolhe número por você. O veneno não é o `git mv` — renomear
    #     continua sendo o que se faz com o arquivo já escrito; o veneno é o
    #     gerador NOMEAR um número. Aqui o "primeiro livre" seria 003: ele não
    #     pode aparecer em lugar nenhum da mensagem, nem no destino do `git mv`.
    assert "003" not in erro, (
        "a mensagem de colisão voltou a escolher o número por conta própria — "
        "a `muralha-das-reservas` reprova quem obedecer, com 'número escolhido "
        "à mão'. O destino do `git mv` é o NNN que o almoxarife devolver."
    )
    assert "primeiro número acima de todos" not in erro


def test_numero_repetido_nao_deixa_o_indice_ser_escrito(
    repo_falso: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gerar o índice apesar da colisão é justamente o silêncio que se combate."""
    monkeypatch.setattr(indice, "raiz_do_repo", lambda: repo_falso)
    assert indice.main([]) == 0
    destino = repo_falso / indice.PASTA / indice.NOME_DO_INDICE
    antes = destino.read_bytes()

    _entrada(repo_falso / indice.PASTA, "002-outra-coisa.md", "Colidiu com a 002")
    assert indice.main([]) == 2
    assert destino.read_bytes() == antes


def test_conferir_tambem_reprova_o_numero_repetido(
    repo_falso: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """É por `--conferir` que a CI passa — se ele não vir, o portão não existe."""
    _entrada(repo_falso / indice.PASTA, "002-outra-coisa.md", "Colidiu com a 002")
    monkeypatch.setattr(indice, "raiz_do_repo", lambda: repo_falso)
    assert indice.main(["--conferir"]) == 2


def test_zero_a_esquerda_nao_esconde_a_colisao(
    repo_falso: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`2-` e `002-` são a mesma gaveta: a comparação é numérica, não textual."""
    _entrada(repo_falso / indice.PASTA, "2-sem-zeros.md", "Mesmo número, outra grafia")
    monkeypatch.setattr(indice, "raiz_do_repo", lambda: repo_falso)
    assert indice.main([]) == 2


def test_numeracao_sem_repeticao_continua_passando(
    repo_falso: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O verde do par: entrada nova com número livre não pode ser reprovada.

    Sem este, um guarda que reprovasse SEMPRE também passaria no teste vermelho
    — e portão que reprova tudo é desligado na primeira urgência.
    """
    _entrada(repo_falso / indice.PASTA, "003-terceira.md", "Número livre, sem colisão")
    monkeypatch.setattr(indice, "raiz_do_repo", lambda: repo_falso)
    assert indice.main([]) == 0
    assert indice.main(["--conferir"]) == 0


def test_a_pasta_real_nao_tem_dois_arquivos_com_o_mesmo_numero() -> None:
    """O guarda medindo a pasta de verdade — é aqui que a colisão do PR aparece.

    Roda dentro de `python ci/ci.py --apenas testador`, que o workflow
    `muralhas` executa em TODO PR: um `NNN` duplicado deixa o PR vermelho antes
    do merge, sem depender de alguém lembrar de listar a pasta.
    """
    por_numero: dict[int, list[str]] = {}
    for caminho in (RAIZ / indice.PASTA).glob("*.md"):
        if caminho.name == indice.NOME_DO_INDICE:
            continue
        numero = indice.Entrada.numero_de(caminho.name)
        if numero is not None:
            por_numero.setdefault(numero, []).append(caminho.name)
    colisoes = {n: sorted(v) for n, v in por_numero.items() if len(v) > 1}
    assert not colisoes, (
        "dois arquivos com o mesmo NNN em armadilhas/:\n  "
        + "\n  ".join(f"{n:03d}: {', '.join(v)}" for n, v in sorted(colisoes.items()))
        + "\n\nPeça um número novo — `python ci/reservar.py numero armadilha` — e "
        "renomeie com ele a entrada mais nova (o arquivo E o campo `armadilha:` "
        "do frontmatter), depois regenere o índice. Escolher o número à mão é "
        "reprovado pela `muralha-das-reservas`."
    )


# ------------------------------------------------- o repositório de verdade


def test_o_indice_do_repositorio_esta_em_dia() -> None:
    """O guarda que impede o inchaço de voltar por esquecimento."""
    assert indice.rodar(RAIZ, conferir=True) == 0


def test_nenhuma_entrada_ficou_fora_do_indice_real() -> None:
    pasta = RAIZ / indice.PASTA
    arquivos = {p.name for p in pasta.glob("*.md") if p.name != indice.NOME_DO_INDICE}
    texto = (pasta / indice.NOME_DO_INDICE).read_text(encoding="utf-8")
    faltando = sorted(n for n in arquivos if n not in texto)
    assert not faltando, f"entradas fora do índice: {faltando}"


# ------------------------------------------------- referências §X.Y resolvem

RE_CITACAO = re.compile(
    r"(?:ARMADILHAS[A-Z\-]*(?:\.md)?|RESOLVIDAS\.md)`?,?\s*"
    r"§([0-9]+(?:\.[0-9]+)*)"
)
RE_ID_DE_ENTRADA = re.compile(r"ID historico: §([0-9]+(?:\.[0-9]+)*)")
RE_H1_COM_ID = re.compile(r"^#\s+([0-9]+(?:\.[0-9]+)+)\s")
RE_H_COM_ID = re.compile(r"^#{2,3}\s+§?([0-9]+(?:\.[0-9]+)*)\s")

EXTENSOES_VARRIDAS = {".md", ".py", ".sh", ".yml", ".yaml", ".txt", ".exemplo", ".json"}


def _ids_conhecidos() -> set[str]:
    """Todo § que hoje resolve para algum lugar de verdade."""
    conhecidos: set[str] = set()

    for arquivo in (RAIZ / indice.PASTA).glob("*.md"):
        if arquivo.name == indice.NOME_DO_INDICE:
            continue
        texto = arquivo.read_text(encoding="utf-8")
        for achado in RE_ID_DE_ENTRADA.finditer(texto):
            conhecidos.add(achado.group(1))
        for linha in texto.splitlines():
            achado = RE_H1_COM_ID.match(linha)
            if achado:
                conhecidos.add(achado.group(1))

    for arquivo in (
        RAIZ / "ARMADILHAS.md",
        RAIZ / "ARMADILHAS-OPERACAO.md",
        RAIZ / "docs" / "historico" / "RESOLVIDAS.md",
    ):
        for linha in arquivo.read_text(encoding="utf-8").splitlines():
            achado = RE_H_COM_ID.match(linha)
            if achado:
                conhecidos.add(achado.group(1))

    # a seção-mãe de cada entrada continua sendo citável ("ARMADILHAS §4")
    conhecidos |= {ident.split(".")[0] for ident in conhecidos}
    return conhecidos


def _arquivos_do_repo() -> list[Path]:
    """Os arquivos do REPOSITÓRIO — perguntados ao git, não andados no disco.

    Antes daqui saía um `RAIZ.rglob("*")` com uma lista de pastas a pular. Ele
    entrava em `.claude/worktrees/`, onde o harness do agente guarda worktrees
    de OUTRAS sessões: na máquina do agente este teste acusava três vezes a
    sentinela `§99.99` do fixture logo abaixo, copiada dentro de worktrees
    velhos. No runner do GitHub essas pastas não existem — ou seja, o furo era
    mudo na CI e barulhento em quem trabalha, que é exatamente como um guarda
    morre: todo mundo aprende a ignorar o vermelho dele.

    Acrescentar `.claude` à lista de pastas ignoradas curaria o caso e não a
    classe. `git ls-files` cura a classe: o que o git rastreia é o repositório;
    o resto é lixo de máquina. O varredor mora em `ci/guarda_dos_guardas.py`
    para que o guarda-dos-guardas e este teste NÃO tenham dois varredores com
    dois bugs diferentes.
    """
    saida: list[Path] = []
    for relativo in arquivos_versionados(RAIZ):
        caminho = RAIZ / relativo
        if not caminho.is_file():
            continue
        if caminho.resolve() == ARQUIVO_DESTE_TESTE:
            continue
        if caminho.suffix not in EXTENSOES_VARRIDAS and caminho.name != "Makefile":
            continue
        saida.append(caminho)
    return saida


def test_o_varredor_enxerga_o_repositorio_e_ignora_worktree_de_agente() -> None:
    """Prova de que o conserto acima é o conserto — e continua varrendo de verdade.

    Duas afirmações, porque uma sem a outra é armadilha: (a) nada de
    `.claude/worktrees/` entra — nem por `git add -A` acidental; (b) os
    arquivos que importam continuam entrando — um varredor que devolvesse
    lista vazia também passaria em (a).

    Até 26/08/2026 o (a) barrava `.claude/` inteiro, porque nada ali era
    rastreado. A muralha da pasta compartilhada versionou de propósito o
    `.claude/settings.json` (armadilhas/135), e ele DEVE entrar no varredor:
    é repositório, não lixo de máquina — a terceira asserção fixa isso.
    """
    varridos = {p.relative_to(RAIZ).as_posix() for p in _arquivos_do_repo()}
    assert not [p for p in varridos if p.startswith(".claude/worktrees/")]
    assert ".claude/settings.json" in varridos
    assert "CLAUDE.md" in varridos
    assert "INVARIANTES.md" in varridos
    assert any(p.startswith("services/") for p in varridos)
    assert len(varridos) > 100


def test_toda_referencia_a_uma_armadilha_resolve() -> None:
    """Referência pendurada custa a próxima sessão inteira.

    O agente lê "ARMADILHAS §5.3", não acha nada, e ou refaz a investigação do
    zero ou conclui que o documento mente. Este teste varre o repositório todo
    (inclusive `services/**`, que a cerca proíbe EDITAR mas não proíbe LER) e
    exige que cada número citado exista em `armadilhas/`, em
    `ARMADILHAS-OPERACAO.md`, no `ARMADILHAS.md` ou no histórico.
    """
    conhecidos = _ids_conhecidos()
    penduradas: list[str] = []
    for caminho in _arquivos_do_repo():
        try:
            texto = caminho.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if "ARMADILHAS" not in texto and "RESOLVIDAS" not in texto:
            continue
        for numero, linha in enumerate(texto.splitlines(), start=1):
            for achado in RE_CITACAO.finditer(linha):
                if achado.group(1) not in conhecidos:
                    rel = caminho.relative_to(RAIZ).as_posix()
                    penduradas.append(f"{rel}:{numero} -> §{achado.group(1)}")
    assert not penduradas, (
        "referência(s) a armadilha que não existe mais:\n  "
        + "\n  ".join(penduradas)
        + "\n\nOu a entrada foi renomeada sem atualizar quem a cita, ou o número "
        "está errado. Conserte a referência — nunca a ignore."
    )


def test_o_guarda_de_referencias_reprova_de_verdade() -> None:
    """Prova falsificável: um § inventado NÃO pode estar no conjunto conhecido."""
    conhecidos = _ids_conhecidos()
    assert "3.3" in conhecidos, "o §3.3 real sumiu — o guarda mediu a coisa errada"
    assert "1" in conhecidos, "o §1 (ARMADILHAS-OPERACAO) deveria resolver"
    assert "99.99" not in conhecidos
    achado = RE_CITACAO.search("ver ARMADILHAS §99.99 para detalhes")
    assert achado is not None and achado.group(1) == "99.99"
