"""O portão que cobra a constituição de cada célula — nos DOIS sentidos.

`RITOS.md` §1 manda toda sessão abrir declarando *"Li `CONSTITUICAO.md` e
`constituicoes/AGENTS.<celula>.md`"*. Até 25/08/2026 isso era **garantia sem
mecanismo** (o padrão da `docs/decisoes/RETROSPECTIVA-FASE-D.md`): a célula
`identidade` — justamente a que prova quem é a pessoa em toda a plataforma —
nasceu sem a dela, e todo despacho da célula abriu por semanas citando um
arquivo que não existia. Nada ficou vermelho, porque nada olhava.

Este arquivo é o que olha. Duas afirmações, e a segunda importa tanto quanto a
primeira:

1. **Célula sem constituição reprova.** Célula nova nasce declarada ou não
   nasce.
2. **Constituição órfã reprova.** `AGENTS.<x>.md` de uma célula que não existe
   mais é o mesmo defeito que o manifesto de contratos já vigia dos dois lados
   (`ci/contract_freeze.py::auditar_manifesto`): declaração e realidade
   discordando em silêncio. Aqui o custo é o agente que lê a lei de uma célula
   morta e trabalha pela regra errada.

**A árvore vem do git, nunca do disco** (`armadilhas/106`): `Path.rglob` entra
em `.claude/worktrees/`, onde o harness guarda o clone de OUTRAS sessões — e
mediria as células delas junto com as suas. O runner do GitHub não tem essa
pasta, então o furo seria mudo na CI e barulhento em quem trabalha, que é como
um guarda perde a credibilidade. O varredor mora em
`ci/guarda_dos_guardas.py::arquivos_versionados`, um só para todos os portões.

Consequência aceita: constituição criada e ainda **não** adicionada ao índice é
invisível aqui. O rito da casa manda `git add` por arquivo antes de qualquer
coisa, e na CI tudo está commitado.

Rodam com `pytest ci/tests` — ou seja, dentro de `python ci/ci.py --apenas
testador`, que os workflows `muralhas` e `alarme-main` já chamam. Nenhuma linha
de YAML foi necessária.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

CI = Path(__file__).resolve().parents[1]
if str(CI) not in sys.path:
    sys.path.insert(0, str(CI))

from _nucleo import ErroDeInstrumentacao, raiz_do_repo  # noqa: E402
from guarda_dos_guardas import arquivos_versionados  # noqa: E402

RAIZ = raiz_do_repo()

PASTA = "constituicoes"
PREFIXO = "AGENTS."
SUFIXO = ".md"
SERVICES = "services/"


# ------------------------------------------------------------- o que existe


def celulas_no_repositorio(versionados: list[str]) -> set[str]:
    """Os nomes das células — o primeiro nível de `services/` que tem arquivo.

    Uma pasta só existe para o git se algo dentro dela é rastreado, então
    "célula de verdade" aqui é exatamente isso: aparece no repositório. NÃO se
    exige `Makefile` nem nenhuma outra marca, pela mesma razão que
    `auditar_manifesto` não exige: uma célula recém-criada ficaria invisível
    para a auditoria, e "não vi" viraria "não existe" — que é o defeito que
    este portão inteiro existe para fechar.
    """
    achadas = set()
    for caminho in versionados:
        if not caminho.startswith(SERVICES):
            continue
        partes = caminho.split("/")
        # `services/<celula>/<arquivo>` — três partes no mínimo. Um arquivo
        # solto em `services/` (um README da pasta) não é célula.
        if len(partes) >= 3 and partes[1]:
            achadas.add(partes[1])
    return achadas


def constituicoes_no_repositorio(versionados: list[str]) -> dict[str, str]:
    """`{celula: caminho}` para cada `constituicoes/AGENTS.<celula>.md`."""
    achadas = {}
    for caminho in versionados:
        nome = caminho.removeprefix(f"{PASTA}/")
        if caminho == nome or "/" in nome:
            continue
        if not (nome.startswith(PREFIXO) and nome.endswith(SUFIXO)):
            continue
        achadas[nome[len(PREFIXO) : -len(SUFIXO)]] = caminho
    return achadas


# ------------------------------------------------------------------ o portão


def _defeito_do_conteudo(raiz: Path, celula: str, relativo: str) -> str | None:
    """O que desqualifica um arquivo que EXISTE. `None` = está de pé.

    Duas checagens, e as duas foram medidas contra as 10 constituições que já
    existiam antes deste portão (todas passam):

    - **vazio** — arquivo de 0 byte satisfaz "existe" e não diz nada. Sem esta
      linha, o jeito mais rápido de calar o portão seria `touch`, e o portão
      viraria cerimônia.
    - **não menciona a própria célula** — pega a constituição copiada de outra
      célula e renomeada, que é o segundo jeito mais rápido de calá-lo. As 10
      abrem com `# Constituição da Célula: <nome>` e citam o nome de 4 a 11
      vezes; nenhuma regra nova de forma foi inventada aqui, só se exige que o
      documento fale da célula que ele governa.
    """
    caminho = raiz / relativo
    if not caminho.is_file():
        return "está versionado mas não existe em disco"
    texto = caminho.read_text(encoding="utf-8")
    if not texto.strip():
        return "está vazio"
    if celula not in texto:
        return f"não menciona '{celula}' em lugar nenhum — é a lei de outra célula?"
    return None


def problemas(raiz: Path) -> list[str]:
    """Toda divergência entre `services/` e `constituicoes/`, em texto de gente.

    Zero células é `ErroDeInstrumentacao`, nunca "tudo certo": um portão que
    aprova sem medir é pior que portão nenhum (INV-CI01).
    """
    versionados = arquivos_versionados(raiz)
    celulas = celulas_no_repositorio(versionados)
    if not celulas:
        raise ErroDeInstrumentacao(
            "nenhuma célula encontrada em services/",
            f"A raiz medida foi {raiz}. Zero células não é 'nada a conferir': é "
            "sinal de que a medição não aconteceu.",
        )
    declaradas = constituicoes_no_repositorio(versionados)

    achados: list[str] = []
    for celula in sorted(celulas - set(declaradas)):
        achados.append(
            f"a célula '{celula}' existe em services/ mas não tem "
            f"{PASTA}/{PREFIXO}{celula}{SUFIXO} — RITOS.md §1 manda toda sessão "
            f"dela abrir citando esse arquivo, e hoje ela citaria o vazio"
        )
    for celula in sorted(set(declaradas) - celulas):
        achados.append(
            f"{declaradas[celula]} é declaração órfã: não há services/{celula}/ "
            f"no repositório — ou a célula foi removida/renomeada sem levar a "
            f"lei junto, ou o nome do arquivo está errado"
        )
    for celula in sorted(set(declaradas) & celulas):
        defeito = _defeito_do_conteudo(raiz, celula, declaradas[celula])
        if defeito:
            achados.append(f"{declaradas[celula]} {defeito}")
    return achados


# ------------------------------------------------- contra o repositório REAL


def test_toda_celula_tem_constituicao_e_nenhuma_e_orfa() -> None:
    achados = problemas(RAIZ)
    assert not achados, (
        "constituição de célula fora do lugar:\n  - "
        + "\n  - ".join(achados)
        + "\n\nCélula nova nasce com a lei dela no mesmo PR: copie a forma de "
        f"{PASTA}/{PREFIXO}admin{SUFIXO} (missão, fronteiras, comunicação, "
        "invariantes com o teste-guarda de cada um, DoD, ritos) e escreva a "
        "partir do CÓDIGO da célula, não do plano dela."
    )


def test_o_varredor_enxerga_o_repositorio_e_ignora_worktree_de_agente() -> None:
    """Duas afirmações, porque uma sem a outra é armadilha (`armadilhas/106`).

    (a) nada de `.claude/worktrees/` entra — nem por `git add -A` acidental;
    (b) o que importa continua entrando — um varredor que devolvesse lista
    vazia também passaria em (a), e este portão aprovaria o repositório
    inteiro sem medir nada.

    Ele mede o VARREDOR, não o estado do repositório: a divergência entre as
    duas listas é assunto do teste acima, e dois vermelhos pelo mesmo defeito
    só ensinariam a ler menos.

    Até 26/08/2026 o (a) barrava `.claude/` inteiro, porque nada ali era
    rastreado. A muralha da pasta compartilhada versionou de propósito o
    `.claude/settings.json` (armadilhas/135), e ele DEVE ser visto pelo
    varredor: é repositório, não lixo de máquina — a asserção nova fixa isso.
    """
    versionados = arquivos_versionados(RAIZ)
    assert not [p for p in versionados if p.startswith(".claude/worktrees/")]
    assert ".claude/settings.json" in versionados
    celulas = celulas_no_repositorio(versionados)
    assert "identidade" in celulas
    assert len(celulas) >= 10
    leis = constituicoes_no_repositorio(versionados)
    assert "admin" in leis
    assert all(c == f"{PASTA}/{PREFIXO}{n}{SUFIXO}" for n, c in leis.items())


# ------------------------------------------------ o repositório de MENTIRA
#
# Com git de verdade: o varredor pergunta ao git, e testar contra um dublê do
# git testaria o dublê.


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


def _lei(celula: str) -> str:
    return (
        f"# Constituição da Célula: {celula}\n"
        f"> **Jurisdição:** governa apenas `services/{celula}/`.\n"
    )


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """Repositório de mentira NO ESTADO CORRETO: duas células, duas leis.

    Duas, e não uma: com uma só, apagá-la cairia no ramo "zero células ⇒
    ERROR" e o teste mediria outra coisa.
    """
    raiz = tmp_path / "repo-falso"
    raiz.mkdir()
    _git(raiz, "init", "-q")
    _git(raiz, "config", "user.email", "falso@exemplo.invalid")
    _git(raiz, "config", "user.name", "Falso")

    for celula in ("falsa", "outra"):
        _escrever(raiz, f"services/{celula}/Makefile", "ci:\n\t@echo falso\n")
        _escrever(raiz, f"{PASTA}/{PREFIXO}{celula}{SUFIXO}", _lei(celula))
    _git(raiz, "add", "-A")
    return raiz


def test_o_repo_falso_intacto_passa(repo: Path) -> None:
    """Sem este par verde, um portão que reprovasse SEMPRE passaria em tudo
    abaixo — e seria desligado na primeira urgência."""
    assert problemas(repo) == []


def test_celula_sem_constituicao_reprova(repo: Path) -> None:
    (repo / PASTA / f"{PREFIXO}outra{SUFIXO}").unlink()
    _git(repo, "add", "-A")  # `-A` também tira do índice o que sumiu do disco
    achados = problemas(repo)
    assert len(achados) == 1
    assert "'outra'" in achados[0] and "não tem" in achados[0]


def test_celula_nova_sem_lei_nenhuma_reprova(repo: Path) -> None:
    """O caso real de 25/08/2026: a célula nasceu, a constituição não."""
    _escrever(repo, "services/identidade/Makefile", "ci:\n\t@echo falso\n")
    _git(repo, "add", "-A")
    achados = problemas(repo)
    assert len(achados) == 1
    assert "'identidade'" in achados[0]


def test_constituicao_orfa_reprova(repo: Path) -> None:
    _escrever(repo, f"{PASTA}/{PREFIXO}fantasma{SUFIXO}", _lei("fantasma"))
    _git(repo, "add", "-A")
    achados = problemas(repo)
    assert len(achados) == 1
    assert "órfã" in achados[0]


def test_constituicao_vazia_reprova(repo: Path) -> None:
    """`touch` não é declarar — só espaços em branco também não."""
    _escrever(repo, f"{PASTA}/{PREFIXO}outra{SUFIXO}", "   \n\n\t\n")
    _git(repo, "add", "-A")
    achados = problemas(repo)
    assert len(achados) == 1
    assert "está vazio" in achados[0]


def test_constituicao_copiada_de_outra_celula_reprova(repo: Path) -> None:
    """Renomear a lei da vizinha é o segundo jeito de calar o portão."""
    _escrever(repo, f"{PASTA}/{PREFIXO}outra{SUFIXO}", _lei("falsa"))
    _git(repo, "add", "-A")
    achados = problemas(repo)
    assert len(achados) == 1
    assert "não menciona 'outra'" in achados[0]


def test_repositorio_sem_celula_nenhuma_e_ERROR(tmp_path: Path) -> None:
    """Zero células é falha de instrumentação, nunca aprovação silenciosa."""
    raiz = tmp_path / "vazio"
    raiz.mkdir()
    _git(raiz, "init", "-q")
    _git(raiz, "config", "user.email", "falso@exemplo.invalid")
    _git(raiz, "config", "user.name", "Falso")
    _escrever(raiz, "README.md", "# só isto\n")
    _git(raiz, "add", "-A")
    with pytest.raises(ErroDeInstrumentacao):
        problemas(raiz)


def test_fora_de_um_repositorio_git_e_ERROR(tmp_path: Path) -> None:
    """Git que não responde vira ERROR, nunca lista vazia de arquivos."""
    with pytest.raises(ErroDeInstrumentacao):
        problemas(tmp_path)
