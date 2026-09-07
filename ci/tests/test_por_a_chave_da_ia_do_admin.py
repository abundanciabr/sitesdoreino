"""O cano que leva a chave da IA até a área administrativa, EXECUTADO, não lido.

`infra/por-a-chave-da-ia-do-admin.sh` copia `ANTHROPIC_API_KEY` (e o
`ANTHROPIC_WORKSPACE_ID`, quando existe) de `env/forum.env` para
`env/admin.env` na VPS e recria a célula `admin` para ela reler o arquivo. Sem
esse cano, o robô analista do degrau 16 do `PLANO-PAINEL-DE-GESTAO.md` nasce
desligado em produção: a chave está na máquina desde 02/09/2026, e está no env
da célula errada.

Ele roda **na máquina do mantenedor**, com uma linha, e um erro ali custa o
pior tipo de tempo que este projeto tem: o dele, no terminal, sem saber o que
fazer com a tela. Por isso este guarda **roda o roteiro de verdade**, contra
uma plataforma de mentira em `tmp_path`, em vez de afirmar coisas sobre o texto
dele. É irmão de `ci/tests/test_por_a_chave_da_ia.py`, que faz o mesmo com o
roteiro do fórum, e mede sete promessas:

1. **A chave NUNCA aparece na tela** (`armadilhas/090`). É o print de tela que o
   mantenedor manda ao agente para provar que funcionou que faz um segredo mudar
   de lugar.
2. **Ele não pergunta NADA e não recebe argumento.** O valor já existe na
   máquina; pedir de novo faria o mantenedor colar um segredo à toa, e argumento
   fica no `~/.bash_history` e é lido por qualquer processo pelo `ps aux`.
3. **Recusa fail-closed, e o arquivo fica intacto.** Sem fórum, sem área
   administrativa, sem plataforma, com a chave vazia ou estranha.
4. **Rodar de novo REESCREVE, nunca duplica.** É como se acompanha uma troca de
   chave, e duas linhas `ANTHROPIC_API_KEY=` no mesmo env fazem o valor depender
   da ordem de leitura.
5. **O resto do `admin.env` sobrevive inteiro** (`armadilhas/111`).
6. **Env sem quebra de linha no fim não gruda a chave no último valor.**
7. **O que ele escreve, o `provisionar-admin.sh` sabe preservar.** Esta é a
   promessa que nenhum dos dois arquivos consegue cumprir sozinho: aquele
   roteiro reescreve o `admin.env` INTEIRO e **para** diante de variável que não
   conhece. Ensinado pela metade, ele apagaria a chave e o robô analista ficaria
   mudo com o deploy verde.

[INV-CI01]: sem `bash` nesta máquina o guarda não tem o que medir, e isso é
ERRO, nunca um OK silencioso.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "infra" / "por-a-chave-da-ia-do-admin.sh"
PROVISIONAMENTO = RAIZ / "infra" / "provisionar-admin.sh"

# Uma chave de mentira com a FORMA da real, e um workspace de mentira.
CHAVE = "sk-ant-api03-" + "N0tAr3alK3y" * 6
OUTRA_CHAVE = "sk-ant-api03-" + "S3gundaCh4v3" * 5
WORKSPACE = "wrkspc_de_teste"

# O `admin.env` como o `provisionar-admin.sh` o escreve.
ADMIN_ENV = (
    "DJANGO_SECRET_KEY=x\n"
    "DATABASE_URL=postgres://admin_user:senha@postgres:5432/admin_db\n"
    "DEBUG=0\n"
    "SCRIPT_NAME=/admin\n"
    "IDENTIDADE_API_URL=http://identidade:8000/interno\n"
    "IDENTIDADE_API_TOKEN=abc123\n"
    "ADMIN_EMAILS=dono@exemplo.com\n"
    "TOKENS_ACEITOS_PAGES=def456\n"
    "GITHUB_TOKEN_FILA=github_pat_naoereal\n"
)


def _bash() -> str:
    caminho = shutil.which("bash")
    assert caminho, (
        "não achei `bash` nesta máquina. Este guarda EXECUTA o roteiro; sem "
        "interpretador ele não tem o que medir, e isso não é um OK ([INV-CI01])."
    )
    return caminho


def _plataforma(
    tmp_path: Path,
    *,
    admin_env: str | None = ADMIN_ENV,
    chave: str | None = CHAVE,
    workspace: str | None = None,
) -> Path:
    """Uma /opt/plataforma de mentira.

    `admin_env=None` = área administrativa não provisionada.
    `chave=None` = a linha da chave não existe no fórum.
    """
    raiz = tmp_path / "plataforma"
    (raiz / "env").mkdir(parents=True)
    (raiz / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    # A referência de dono e permissão que o roteiro copia.
    (raiz / "env" / "identidade.env").write_text(
        "DJANGO_SECRET_KEY=y\n", encoding="utf-8"
    )
    forum = "DJANGO_SECRET_KEY=z\nSCRIPT_NAME=/forum\n"
    if chave is not None:
        forum += f"ANTHROPIC_API_KEY={chave}\n"
    if workspace is not None:
        forum += f"ANTHROPIC_WORKSPACE_ID={workspace}\n"
    (raiz / "env" / "forum.env").write_text(forum, encoding="utf-8")
    if admin_env is not None:
        (raiz / "env" / "admin.env").write_text(admin_env, encoding="utf-8")
    return raiz


def _rodar(raiz: Path) -> subprocess.CompletedProcess:
    """Roda o roteiro SEM ARGUMENTO e com a entrada de teclado FECHADA.

    A entrada vazia não é detalhe do teste: é a asserção de que ele não pergunta
    nada. Um `read` que aparecesse aqui receberia fim-de-arquivo, e o roteiro
    gravaria valor vazio ou travaria — os dois desfechos reprovam.

    A plataforma de mentira não tem serviço `admin` no compose, e isso é de
    propósito: o roteiro tem um caminho declarado para quando não há o que
    recarregar (grava o arquivo, avisa que não recarregou, e sai com 0). É o
    mesmo caminho que rodaria numa VPS onde o docker mudou de nome, e ele
    precisa ser o caminho testado. Assim o guarda não depende de haver docker na
    máquina que roda a suíte.
    """
    ambiente = dict(os.environ, PLATAFORMA_DIR=str(raiz))
    return subprocess.run(
        [_bash(), str(SCRIPT)],
        input="",
        capture_output=True,
        text=True,
        # O roteiro fala PORTUGUÊS, com acento e com o "PAROU POR SEGURANÇA".
        # Sem dizer o encoding aqui, o Python de uma máquina Windows tenta
        # cp1252 e a leitura da tela estoura antes de qualquer asserção.
        encoding="utf-8",
        errors="replace",
        env=ambiente,
    )


def _valor(raiz: Path, chave: str, arquivo: str = "admin.env") -> str | None:
    for linha in (raiz / "env" / arquivo).read_text(encoding="utf-8").splitlines():
        if linha.startswith(chave + "="):
            return linha.split("=", 1)[1]
    return None


def _quantas(raiz: Path, chave: str) -> int:
    texto = (raiz / "env" / "admin.env").read_text(encoding="utf-8")
    return sum(1 for x in texto.splitlines() if x.startswith(chave + "="))


# ---------------------------------------------------------------------------
# 1. O CANO LEVA A CHAVE, E SÓ ISSO
# ---------------------------------------------------------------------------


def test_a_chave_vai_do_forum_para_a_area_administrativa(tmp_path):
    raiz = _plataforma(tmp_path, workspace=WORKSPACE)

    r = _rodar(raiz)

    assert r.returncode == 0, r.stdout + r.stderr
    assert _valor(raiz, "ANTHROPIC_API_KEY") == CHAVE
    assert _valor(raiz, "ANTHROPIC_WORKSPACE_ID") == WORKSPACE
    # E o fórum, de onde ela veio, não foi tocado.
    assert _valor(raiz, "ANTHROPIC_API_KEY", "forum.env") == CHAVE


def test_a_chave_nunca_aparece_na_tela(tmp_path):
    raiz = _plataforma(tmp_path, workspace=WORKSPACE)

    r = _rodar(raiz)

    tela = r.stdout + r.stderr
    assert CHAVE not in tela, (
        "a chave apareceu na tela. É exatamente por esse caminho que o segredo "
        "do OAuth vazou em 24/08/2026 (`armadilhas/090`): o mantenedor manda o "
        "print para provar que funcionou."
    )
    # E nem um pedaço dela: metade de uma chave ainda é meia chave vazada.
    assert CHAVE[:20] not in tela
    # Mas o roteiro FALA: silêncio total seria indistinguível de travado.
    assert "caracteres" in tela
    # Id de workspace não é segredo, e ver o que foi copiado evita a cópia pela
    # metade que ninguém percebe. A assimetria é de propósito.
    assert WORKSPACE in tela


def test_ele_nao_pergunta_nada():
    """Um `read` a mais funcionaria perfeitamente numa VPS com alguém digitando,
    e nenhuma asserção sobre o arquivo escrito o pegaria. O defeito é o pedido
    em si: o valor já está na máquina, e pedir de novo faz o mantenedor colar um
    segredo à toa (`armadilhas/090`).
    """
    codigo = "\n".join(
        linha
        for linha in SCRIPT.read_text(encoding="utf-8").splitlines()
        if not linha.lstrip().startswith("#")
    )
    assert not re.search(r"\bread\b", codigo), (
        "o roteiro passou a perguntar alguma coisa, e ele não deve perguntar "
        "nada: a chave já existe nesta máquina desde 02/09/2026."
    )


def test_argumento_de_linha_de_comando_e_ignorado(tmp_path):
    """A outra metade da mesma decisão, e esta se mede executando.

    Argumento aparece no `ps aux` de qualquer processo da máquina, fica no
    `~/.bash_history` e vai junto no print de tela que o mantenedor manda ao
    agente. Um roteiro que ACEITASSE a chave por argumento convidaria a colá-la
    ali, e foi assim que o segredo do OAuth vazou em 24/08/2026
    (`armadilhas/090`). Aqui, o que vier na linha de comando não muda nada.
    """
    raiz = _plataforma(tmp_path)
    intruso = "sk-ant-api03-" + "V3ioP0rArgum3nt0" * 3
    ambiente = dict(os.environ, PLATAFORMA_DIR=str(raiz))
    r = subprocess.run(
        [_bash(), str(SCRIPT), intruso],
        input="",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=ambiente,
    )

    assert r.returncode == 0, r.stdout + r.stderr
    assert _valor(raiz, "ANTHROPIC_API_KEY") == CHAVE, (
        "o roteiro gravou o que veio na linha de comando. A chave tem de sair "
        "do `env/forum.env` desta máquina, e de lugar nenhum mais."
    )
    assert intruso not in (raiz / "env" / "admin.env").read_text(encoding="utf-8")
    assert intruso not in (r.stdout + r.stderr)


# ---------------------------------------------------------------------------
# 2. FAIL-CLOSED, E COM O ARQUIVO INTACTO
# ---------------------------------------------------------------------------


def test_sem_a_plataforma_ele_para(tmp_path):
    r = _rodar(tmp_path / "lugar-nenhum")
    assert r.returncode != 0
    assert "PAROU POR SEGURANÇA" in (r.stdout + r.stderr)


def test_sem_a_area_administrativa_provisionada_ele_para(tmp_path):
    raiz = _plataforma(tmp_path, admin_env=None)

    r = _rodar(raiz)

    assert r.returncode != 0
    assert "PAROU POR SEGURANÇA" in (r.stdout + r.stderr)
    assert "provisionar-admin.sh" in (r.stdout + r.stderr), (
        "a mensagem de erro tem de dizer o que fazer, não só o que houve."
    )
    assert not (raiz / "env" / "admin.env").exists()


@pytest.mark.parametrize(
    "chave,porque",
    [
        (None, "a linha da chave não existe no fórum"),
        ("", "a linha existe e está vazia (o fórum ainda não recebeu a chave)"),
        ("sk-ant chave com espaço", "colada junto com outra coisa"),
        ("sk-ant-'; rm -rf /", "caractere que não é de chave"),
    ],
)
def test_chave_ausente_ou_estranha_para_e_nada_e_escrito(tmp_path, chave, porque):
    raiz = _plataforma(tmp_path, chave=chave)
    antes = (raiz / "env" / "admin.env").read_text(encoding="utf-8")

    r = _rodar(raiz)

    assert r.returncode != 0, porque
    assert "PAROU POR SEGURANÇA" in (r.stdout + r.stderr)
    assert (raiz / "env" / "admin.env").read_text(encoding="utf-8") == antes, (
        "recusou e mesmo assim mexeu no arquivo: " + porque
    )


def test_carregado_com_source_ele_recusa(tmp_path):
    """O modo de falha de 24/08/2026: um `exit` de um arquivo carregado com
    `source` derruba a sessão do mantenedor no meio do trabalho."""
    raiz = _plataforma(tmp_path)
    ambiente = dict(os.environ, PLATAFORMA_DIR=str(raiz))
    r = subprocess.run(
        [_bash(), "-c", f'. "{SCRIPT}"; echo AINDA_VIVO'],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=ambiente,
    )
    assert "PAROU POR SEGURANÇA" in r.stdout
    assert "AINDA_VIVO" in r.stdout, "o `return` não pode derrubar a sessão."
    assert _valor(raiz, "ANTHROPIC_API_KEY") is None


# ---------------------------------------------------------------------------
# 3. RODAR DE NOVO É O CASO NORMAL, NÃO O EXCEPCIONAL
# ---------------------------------------------------------------------------


def test_rodar_de_novo_acompanha_a_troca_e_nao_duplica_a_linha(tmp_path):
    """É assim que a área administrativa acompanha uma chave trocada no fórum.
    Duas linhas fariam o valor depender da ordem em que alguém lê o arquivo."""
    raiz = _plataforma(tmp_path, workspace=WORKSPACE)
    assert _rodar(raiz).returncode == 0

    # O mantenedor troca a chave no fórum, para uma de workspace (sem o número).
    (raiz / "env" / "forum.env").write_text(
        f"DJANGO_SECRET_KEY=z\nANTHROPIC_API_KEY={OUTRA_CHAVE}\n"
        "ANTHROPIC_WORKSPACE_ID=\n",
        encoding="utf-8",
    )
    assert _rodar(raiz).returncode == 0

    assert _valor(raiz, "ANTHROPIC_API_KEY") == OUTRA_CHAVE
    assert _quantas(raiz, "ANTHROPIC_API_KEY") == 1
    assert _quantas(raiz, "ANTHROPIC_WORKSPACE_ID") == 1
    assert _valor(raiz, "ANTHROPIC_WORKSPACE_ID") == "", (
        "herdou o workspace da chave anterior. A chave nova sairia mandando o "
        "cabeçalho da antiga, e a recusa seria por um motivo que ninguém mudou."
    )
    # E o cabeçalho do bloco não empilha a cada execução.
    texto = (raiz / "env" / "admin.env").read_text(encoding="utf-8")
    assert texto.count("# escrito por infra/por-a-chave-da-ia-do-admin.sh") == 1


def test_o_resto_do_env_sobrevive_inteiro(tmp_path):
    """`armadilhas/111`: variável que some do env é falha silenciosa com deploy
    verde. Aqui, perder `IDENTIDADE_API_TOKEN` fecharia a área administrativa
    inteira, e perder `GITHUB_TOKEN_FILA` custaria uma ida do mantenedor ao
    navegador, porque uma chave do GitHub aparece uma vez só."""
    raiz = _plataforma(tmp_path)

    assert _rodar(raiz).returncode == 0

    assert _valor(raiz, "DJANGO_SECRET_KEY") == "x"
    assert _valor(raiz, "SCRIPT_NAME") == "/admin"
    assert _valor(raiz, "ADMIN_EMAILS") == "dono@exemplo.com"
    assert _valor(raiz, "IDENTIDADE_API_TOKEN") == "abc123"
    assert _valor(raiz, "TOKENS_ACEITOS_PAGES") == "def456"
    assert _valor(raiz, "GITHUB_TOKEN_FILA") == "github_pat_naoereal"
    assert _valor(raiz, "DATABASE_URL") == (
        "postgres://admin_user:senha@postgres:5432/admin_db"
    )


def test_env_sem_quebra_de_linha_no_fim_nao_gruda_a_chave_no_ultimo_valor(tmp_path):
    """A última linha de um env é um VALOR, e um `>>` sem a quebra o corromperia
    em silêncio."""
    raiz = _plataforma(tmp_path, admin_env="DJANGO_SECRET_KEY=x\nADMIN_EMAILS=dono@e.com")

    assert _rodar(raiz).returncode == 0

    assert _valor(raiz, "ADMIN_EMAILS") == "dono@e.com"
    assert _valor(raiz, "ANTHROPIC_API_KEY") == CHAVE
    assert _quantas(raiz, "ANTHROPIC_API_KEY") == 1


def test_a_copia_de_seguranca_nasce_antes_de_qualquer_edicao(tmp_path):
    raiz = _plataforma(tmp_path)

    assert _rodar(raiz).returncode == 0

    copias = list((raiz / "env").glob("admin.env.bak-*"))
    assert len(copias) == 1, "sem a cópia, um erro no meio não teria volta."
    assert copias[0].read_text(encoding="utf-8") == ADMIN_ENV
    # E o arquivo temporário da reescrita não fica para trás.
    assert not list((raiz / "env").glob("admin.env.novo-*"))


# ---------------------------------------------------------------------------
# 4. OS DOIS ROTEIROS DO MESMO ENV, CONFERIDOS UM CONTRA O OUTRO
# ---------------------------------------------------------------------------
# Esta é a promessa que nenhum dos dois arquivos cumpre sozinho, e ela é medida
# do que o roteiro REALMENTE escreveu, não do que o texto dele diz escrever.


def test_o_provisionamento_sabe_de_tudo_que_este_roteiro_escreve(tmp_path):
    """`infra/provisionar-admin.sh` reescreve o `admin.env` INTEIRO e **para**
    diante de variável que não conhece. Se este roteiro escrever uma chave que
    aquele não conhece, o mantenedor recebe uma parada nominal na próxima
    reprovisão; e se aquele a conhecer sem RELÊ-LA, o valor some em silêncio com
    o deploy verde (`armadilhas/111`), e o robô analista fica mudo.
    """
    raiz = _plataforma(tmp_path, workspace=WORKSPACE)
    assert _rodar(raiz).returncode == 0

    antes = set(re.findall(r"^([A-Z_][A-Z0-9_]*)=", ADMIN_ENV, re.MULTILINE))
    depois = set(
        re.findall(
            r"^([A-Z_][A-Z0-9_]*)=",
            (raiz / "env" / "admin.env").read_text(encoding="utf-8"),
            re.MULTILINE,
        )
    )
    escritas = depois - antes
    assert escritas == {"ANTHROPIC_API_KEY", "ANTHROPIC_WORKSPACE_ID"}, (
        "o roteiro mudou o que escreve no env. Ensine os dois lados na mesma "
        "edição, ou o provisionamento vai parar (ou apagar) na próxima vez."
    )

    fonte = PROVISIONAMENTO.read_text(encoding="utf-8")
    achado = re.search(r'^CHAVES_QUE_EU_GERO="([^"]*)"', fonte, re.MULTILINE)
    assert achado, "`provisionar-admin.sh` não declara `CHAVES_QUE_EU_GERO`."
    conhecidas = set(achado.group(1).split())
    faltando = escritas - conhecidas
    assert not faltando, (
        f"`infra/provisionar-admin.sh` não conhece {sorted(faltando)}, e ele "
        "reescreve este env inteiro. Rodá-lo pararia com 'variável que eu NÃO "
        "sei gerar'. Acrescente à `CHAVES_QUE_EU_GERO`, ao heredoc, e releia o "
        "valor vivo antes de escrever."
    )
    for chave in sorted(escritas):
        assert re.search(rf'ler_de env/admin\.env {chave}\b', fonte), (
            f"`provisionar-admin.sh` escreve {chave} sem RELÊ-LA do arquivo "
            "vivo. Ele geraria vazio por cima do valor que este roteiro pôs, e "
            "o sintoma seria o robô analista mudo com o deploy verde "
            "(`armadilhas/111`)."
        )
