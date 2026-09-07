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
roteiro do fórum.

O roteiro roda contra um DOCKER DE MENTIRA, e essa é a diferença que faz esta
suíte medir a metade que importa. Até 07/09/2026 a plataforma de mentira não
tinha o serviço `admin` no compose, então todos os casos saíam pela porta do
"não há o que recarregar": recarregar a célula, conferir a chave dentro do
container e o próprio `PRONTO` nunca eram executados por teste nenhum. Medido:
apagando as 84 linhas finais do roteiro, a suíte continuava verde. É a metade
que roda na VPS do mantenedor, e era a metade sem guarda.

Ele mede oito promessas:

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
7. **Só existe PRONTO com a chave dentro do container.** Recarregar que falhou,
   container que não renasceu, chave que não chegou, chave do mesmo tamanho e
   outro conteúdo, e pergunta sem resposta: os cinco terminam em
   `PAROU POR SEGURANÇA` e código diferente de zero. Uma tela nunca diz PRONTO
   e PAROU ao mesmo tempo.
8. **O que ele escreve, o `provisionar-admin.sh` sabe preservar.** Esta é a
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
# Do MESMO tamanho da `CHAVE` e com outro conteúdo. Duas chaves da Anthropic
# criadas na mesma conta têm o mesmo comprimento, e é por isso que o tamanho
# não serve de prova de que a chave certa chegou ao container.
CHAVE_DO_MESMO_TAMANHO = "sk-ant-api03-" + "0utr4Ch4v3X" * 6
WORKSPACE = "wrkspc_de_teste"

# As duas variáveis que ESTE roteiro escreve, e nenhuma outra.
VARIAVEIS_DO_ROTEIRO = {"ANTHROPIC_API_KEY", "ANTHROPIC_WORKSPACE_ID"}

# O `admin.env` como o `provisionar-admin.sh` o escreve HOJE — as onze linhas,
# com as duas da IA nascendo VAZIAS. Uma máquina recém-provisionada é assim
# desde o PR #1332, e um fixture com as nove linhas antigas mediria um mundo
# que não existe mais: nele as duas variáveis apareceriam como "novas" e a
# asserção de que o roteiro não escreve mais nada passaria por sorte.
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
    "ANTHROPIC_API_KEY=\n"
    "ANTHROPIC_WORKSPACE_ID=\n"
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


# O docker de mentira. Sem ele, `docker compose config --services` responderia
# o que a máquina de quem roda a suíte tiver a dizer: com docker instalado, uma
# coisa; sem docker, outra; e a metade do roteiro que recarrega a célula e
# confere a chave DENTRO do container nunca rodaria em teste nenhum. É essa
# metade que roda na VPS do mantenedor.
#
# Ele guarda estado em arquivos, e é isso que o faz medir em vez de afirmar: o
# `up` só troca o id do container e só recarrega a chave quando de fato dá
# certo. Um `up` que falha deixa o container ANTIGO de pé, com a chave antiga —
# que é exatamente o desfecho que o roteiro precisa recusar.
DOCKER_DE_MENTIRA = r"""#!/usr/bin/env bash
[ "${1:-}" = "compose" ] || exit 0
shift
case "${1:-}" in
  config)
    printf '%s\n' ${DOCKER_FALSO_SERVICOS:-admin}
    exit "${DOCKER_FALSO_CONFIG:-0}"
    ;;
  ps)
    case " $* " in
      *" -q "*) cat "$DOCKER_FALSO_ESTADO/id" ;;
      *) printf 'NAME    IMAGE   STATUS\nadmin   admin   %s\n' "$(cat "$DOCKER_FALSO_ESTADO/estado")" ;;
    esac
    exit 0
    ;;
  up)
    if [ "${DOCKER_FALSO_UP:-0}" -ne 0 ]; then
      printf 'dependency failed to start: container plataforma-admin-1 is unhealthy\n' >&2
      exit "${DOCKER_FALSO_UP}"
    fi
    if [ "${DOCKER_FALSO_RECRIA:-1}" -eq 1 ]; then
      printf 'id-depois-%s\n' "$$" > "$DOCKER_FALSO_ESTADO/id"
      if [ "${DOCKER_FALSO_CHAVE_FIXA+definida}" = "definida" ]; then
        printf '%s' "$DOCKER_FALSO_CHAVE_FIXA" > "$DOCKER_FALSO_ESTADO/chave"
      else
        grep '^ANTHROPIC_API_KEY=' "$DOCKER_FALSO_ENV" | head -1 | cut -d= -f2- \
          | tr -d '\r\n' > "$DOCKER_FALSO_ESTADO/chave"
      fi
    fi
    printf 'Container plataforma-admin-1  Started\n'
    exit 0
    ;;
  exec)
    if [ "${DOCKER_FALSO_EXEC:-0}" -ne 0 ]; then
      printf 'service "admin" is not running\n' >&2
      exit "${DOCKER_FALSO_EXEC}"
    fi
    ANTHROPIC_API_KEY="$(cat "$DOCKER_FALSO_ESTADO/chave")" sh -c "${!#}"
    exit $?
    ;;
esac
exit 0
"""


def _docker(tmp_path: Path, raiz: Path, **ajustes: str) -> dict:
    """Instala o docker de mentira e devolve o ambiente que o roteiro vê.

    Sem ajuste nenhum ele é um docker que FUNCIONA: tem o serviço `admin`,
    recria o container, e o container passa a ler o `admin.env` recém-escrito.
    """
    pasta = tmp_path / "docker-de-mentira"
    pasta.mkdir(exist_ok=True)
    executavel = pasta / "docker"
    # Bytes, e não `write_text`: num Windows o modo texto trocaria cada quebra
    # de linha por CRLF e o `bash` recusaria o roteiro com "\r: command not
    # found", que é um erro que não se parece nada com a sua causa.
    executavel.write_bytes(DOCKER_DE_MENTIRA.encode("utf-8"))
    executavel.chmod(0o755)

    estado = tmp_path / "estado-do-container"
    estado.mkdir(exist_ok=True)
    (estado / "id").write_text("id-antes\n", encoding="utf-8")
    (estado / "estado").write_text("Up 3 minutes\n", encoding="utf-8")
    # O container começa SEM a chave: é o mundo antes deste roteiro rodar.
    (estado / "chave").write_text("", encoding="utf-8")

    ambiente = dict(
        os.environ,
        PATH=str(pasta) + os.pathsep + os.environ.get("PATH", ""),
        PLATAFORMA_DIR=str(raiz),
        DOCKER_FALSO_ESTADO=str(estado),
        DOCKER_FALSO_ENV=str(raiz / "env" / "admin.env"),
    )
    ambiente.update(ajustes)
    return ambiente


def _rodar(raiz: Path, ambiente: dict | None = None) -> subprocess.CompletedProcess:
    """Roda o roteiro SEM ARGUMENTO e com a entrada de teclado FECHADA.

    A entrada vazia não é detalhe do teste: é a asserção de que ele não pergunta
    nada. Um `read` que aparecesse aqui receberia fim-de-arquivo, e o roteiro
    gravaria valor vazio ou travaria — os dois desfechos reprovam.

    Sem ambiente dito, ele roda contra um docker de mentira que FUNCIONA, e
    assim cada caso desta suíte atravessa o roteiro inteiro, até a conferência
    feita dentro do container.
    """
    if ambiente is None:
        ambiente = _docker(raiz.parent, raiz)
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
        # Sem acento nenhum, de propósito. Um caso escrito como "chave com
        # espaço" reprovava pelo `ç` e não pelo espaço, e nesse disfarce a
        # conferência podia acontecer DEPOIS de o roteiro apagar os espaços
        # sozinho: aí ele gravava `sk-ant-api03-AAABBB` e dizia que estava tudo
        # certo. O que se mede aqui é o valor CRU do arquivo.
        ("sk-ant-api03-AAA BBB", "colada junto com outra coisa, com espaço no meio"),
        (
            "sk-ant-api03-AAA#comentario",
            "o que parece comentário é parte do valor, e o resto seria truncado",
        ),
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
    assert _valor(raiz, "ANTHROPIC_API_KEY") == "", "recusou e mesmo assim gravou."


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
# 4. A METADE QUE RODA NA VPS: RECARREGAR E CONFERIR DENTRO DO CONTAINER
# ---------------------------------------------------------------------------
# Escrever o arquivo é o passo fácil. O que decide se o robô analista fala ou
# fica mudo é o container renascer e LER a chave, e é essa metade que o
# mantenedor vê na tela. Cada caso aqui mede o CÓDIGO DE SAÍDA de verdade: um
# roteiro que termina em zero é um roteiro que disse "deu certo".


def _um_veredito_so(r) -> str:
    """A tela nunca pode dizer duas coisas opostas para um leigo.

    O roteiro tem TRÊS desfechos, e nenhum deles se mistura com outro:
    `== PRONTO ==` com código 0, `(aviso: ...)` com código 0, e
    `PAROU POR SEGURANÇA` com código 1.
    """
    tela = r.stdout + r.stderr
    assert not ("== PRONTO ==" in tela and "PAROU POR SEGURANÇA" in tela), (
        "a mesma tela disse PRONTO e PAROU POR SEGURANÇA. O mantenedor é leigo "
        "em terminal: duas frases com veredito oposto na mesma tela fazem ele "
        "escolher a que preferir ler."
    )
    if r.returncode == 0:
        assert "PAROU POR SEGURANÇA" not in tela, "parou e mesmo assim saiu com 0."
    else:
        assert "== PRONTO ==" not in tela, "disse PRONTO e saiu com erro."
        assert "PAROU POR SEGURANÇA" in tela, (
            "saiu com erro sem dizer ao mantenedor o que houve e o que fazer."
        )
    return tela


def test_o_caminho_bom_leva_a_chave_ate_dentro_do_container(tmp_path):
    """O único desfecho verde: o container renasceu e leu a chave certa."""
    raiz = _plataforma(tmp_path, workspace=WORKSPACE)

    r = _rodar(raiz)

    tela = _um_veredito_so(r)
    assert r.returncode == 0, tela
    assert "== PRONTO ==" in tela
    assert CHAVE not in tela


def test_recarregar_que_falhou_nunca_vira_pronto(tmp_path):
    """`docker compose up` recusando deixa o container ANTIGO de pé, e o `ps`
    continua dizendo "Up". Ler só o `ps` é ler o container errado.

    O container de mentira já está com a chave CERTA dentro, de propósito: sem
    isso, quem recusaria seria a conferência da chave, e o código de saída do
    `up` poderia ser jogado fora sem nenhum teste perceber. Aqui só ele pode
    recusar, e recusar é o certo: o docker acabou de dizer que a célula não
    subiu, e a área administrativa pode estar fora do ar neste momento.
    """
    raiz = _plataforma(tmp_path)
    ambiente = _docker(tmp_path, raiz, DOCKER_FALSO_UP="1")
    (tmp_path / "estado-do-container" / "estado").write_text(
        "Up 4 minutes (unhealthy)\n", encoding="utf-8"
    )
    (tmp_path / "estado-do-container" / "chave").write_text(CHAVE, encoding="utf-8")

    r = _rodar(raiz, ambiente)

    tela = _um_veredito_so(r)
    assert r.returncode != 0, tela
    assert "dependency failed to start" in tela, (
        "o que o docker respondeu tem de aparecer na tela: é a única pista do "
        "que houve, e o mantenedor manda essa tela ao agente."
    )


def test_container_que_nao_foi_recriado_diz_isso_ao_mantenedor(tmp_path):
    """`up` pode devolver zero sem tocar em nada. Aí a chave está no arquivo e
    fora do processo, e comparar o id antes e depois é a única medição que
    distingue "recriado" de "nunca foi tocado" — que são dois problemas
    diferentes, com conserto diferente, e chegariam ao agente com a mesma cara.
    """
    raiz = _plataforma(tmp_path)
    ambiente = _docker(tmp_path, raiz, DOCKER_FALSO_RECRIA="0")

    r = _rodar(raiz, ambiente)

    tela = _um_veredito_so(r)
    assert r.returncode != 0, tela
    assert "renasceu quando eu recarreguei? NAO" in tela, (
        "a tela não disse a causa que o roteiro tinha medido."
    )


def test_container_que_renasceu_e_caiu_nunca_vira_pronto(tmp_path):
    """O `--wait` pode ser satisfeito e o container morrer logo depois. Aí o
    `docker compose ps` não diz "Up", e não dizer "Up" é a área administrativa
    fora do ar neste momento."""
    raiz = _plataforma(tmp_path)
    ambiente = _docker(tmp_path, raiz)
    (tmp_path / "estado-do-container" / "estado").write_text(
        "Exited (1) 2 seconds ago\n", encoding="utf-8"
    )

    r = _rodar(raiz, ambiente)

    tela = _um_veredito_so(r)
    assert r.returncode != 0, tela


def test_sem_o_sha256sum_desta_maquina_ele_nao_finge_que_conferiu(tmp_path):
    """O resumo é a prova. Sem o programa que o calcula não há prova nenhuma, e
    a ausência de prova nunca vira PRONTO."""
    raiz = _plataforma(tmp_path)
    ambiente = _docker(tmp_path, raiz)
    quebrado = tmp_path / "docker-de-mentira" / "sha256sum"
    quebrado.write_bytes(b"#!/usr/bin/env bash\nexit 1\n")
    quebrado.chmod(0o755)

    r = _rodar(raiz, ambiente)

    tela = _um_veredito_so(r)
    assert r.returncode != 0, tela
    assert "sha256sum" in tela, "a mensagem tem de dizer o que faltou."


def test_chave_que_nao_chegou_dentro_do_container_nunca_vira_pronto(tmp_path):
    """O defeito mais caro que este roteiro já teve: o container leu zero
    caracteres, a tela imprimiu um AVISO de rodapé e o roteiro terminou com
    código 0. O mantenedor conclui que o robô analista está ligado."""
    raiz = _plataforma(tmp_path)
    ambiente = _docker(tmp_path, raiz, DOCKER_FALSO_CHAVE_FIXA="")

    r = _rodar(raiz, ambiente)

    tela = _um_veredito_so(r)
    assert r.returncode != 0, tela


def test_chave_do_mesmo_tamanho_e_de_outro_conteudo_nunca_vira_pronto(tmp_path):
    """Rodar de novo para acompanhar uma troca de chave é o caso NORMAL, e é
    justamente nele que as duas chaves têm o mesmo comprimento."""
    assert len(CHAVE_DO_MESMO_TAMANHO) == len(CHAVE), "o caso perdeu o sentido."
    raiz = _plataforma(tmp_path)
    ambiente = _docker(tmp_path, raiz, DOCKER_FALSO_CHAVE_FIXA=CHAVE_DO_MESMO_TAMANHO)

    r = _rodar(raiz, ambiente)

    tela = _um_veredito_so(r)
    assert r.returncode != 0, tela
    assert CHAVE not in tela and CHAVE_DO_MESMO_TAMANHO not in tela, (
        "a conferência por resumo não pode virar um jeito novo de a chave "
        "aparecer na tela (`armadilhas/090`)."
    )
    assert "renasceu quando eu recarreguei? sim" in tela, (
        "aqui o container RENASCEU e mesmo assim leu outra chave. Confundir "
        "isso com 'nem renasceu' manda o agente consertar a coisa errada."
    )


def test_conferencia_que_nao_pode_ser_feita_nunca_vira_pronto(tmp_path):
    """Não conseguir perguntar ao container não é o mesmo que a resposta ser
    boa. Um `exec` que falha é uma pergunta sem resposta."""
    raiz = _plataforma(tmp_path)
    ambiente = _docker(tmp_path, raiz, DOCKER_FALSO_EXEC="1")

    r = _rodar(raiz, ambiente)

    tela = _um_veredito_so(r)
    assert r.returncode != 0, tela


def test_compose_ilegivel_nao_vira_diagnostico_falso(tmp_path):
    """`docker compose config` também falha quando um `env_file` citado no
    compose está faltando. Traduzir isso para "o serviço admin não está no
    docker-compose.yml" é mandar o mantenedor procurar o problema errado."""
    raiz = _plataforma(tmp_path)
    ambiente = _docker(tmp_path, raiz, DOCKER_FALSO_CONFIG="1")

    r = _rodar(raiz, ambiente)

    tela = _um_veredito_so(r)
    assert r.returncode != 0, tela
    assert "nao esta no docker-compose.yml" not in tela, (
        "o roteiro afirmou uma causa que não mediu."
    )


def test_sem_o_servico_admin_no_compose_ele_avisa_e_o_arquivo_fica_certo(tmp_path):
    """O desfecho amarelo, e ele é legítimo: não há o que recarregar, o arquivo
    já está certo, e o próximo deploy relê o env sozinho."""
    raiz = _plataforma(tmp_path)
    ambiente = _docker(tmp_path, raiz, DOCKER_FALSO_SERVICOS="postgres forum")

    r = _rodar(raiz, ambiente)

    tela = _um_veredito_so(r)
    assert r.returncode == 0, tela
    assert "aviso" in tela
    assert "== PRONTO ==" not in tela, (
        "sem recarregar não há como conferir dentro do container, e sem "
        "conferir não há PRONTO."
    )
    assert _valor(raiz, "ANTHROPIC_API_KEY") == CHAVE


def test_o_arquivo_temporario_com_a_chave_nao_sobrevive_a_uma_interrupcao(tmp_path):
    """`armadilhas/090`: entre a escrita e a troca existe um arquivo com a
    chave dentro, em `env/`. Um Ctrl-C ali deixaria o segredo na máquina com um
    nome que nenhuma mensagem cita, e nenhuma execução seguinte o apagaria."""
    fonte = SCRIPT.read_text(encoding="utf-8")
    assert re.search(r"^trap .*rm -f .*NOVO.* EXIT INT TERM", fonte, re.MULTILINE), (
        "o arquivo temporário que carrega a chave não tem `trap`."
    )
    # E medido: o roteiro interrompido não deixa o arquivo para trás.
    raiz = _plataforma(tmp_path)
    ambiente = _docker(tmp_path, raiz, DOCKER_FALSO_EXEC="1")
    _rodar(raiz, ambiente)
    assert not list((raiz / "env").glob("admin.env.novo-*"))


def test_a_prova_de_fora_nao_pergunta_a_producao(tmp_path):
    """Um `curl` fixo para `https://meshcraft.top` mede PRODUÇÃO, rode o
    roteiro onde rodar. Chamar isso de prova do que acabou de ser feito numa
    outra máquina é medir o vizinho e assinar embaixo."""
    fonte = SCRIPT.read_text(encoding="utf-8")
    codigo = "\n".join(
        linha for linha in fonte.splitlines() if not linha.lstrip().startswith("#")
    )
    assert "meshcraft.top" not in codigo, (
        "o roteiro voltou a medir um endereço fixo. O que prova esta mudança é "
        "o container desta máquina, medido por dentro."
    )


# ---------------------------------------------------------------------------
# 5. OS DOIS ROTEIROS DO MESMO ENV, CONFERIDOS UM CONTRA O OUTRO
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
    assert depois == antes, (
        "o roteiro mudou o conjunto de variáveis do env. Ensine os dois lados "
        "na mesma edição, ou o provisionamento vai parar (ou apagar) na "
        "próxima vez."
    )
    # A máquina recém-provisionada nasce com as duas linhas VAZIAS, então o que
    # prova o trabalho não é uma variável nova: é o VALOR delas e o fato de
    # cada uma aparecer uma vez só.
    assert _valor(raiz, "ANTHROPIC_API_KEY") == CHAVE
    assert _valor(raiz, "ANTHROPIC_WORKSPACE_ID") == WORKSPACE
    assert _quantas(raiz, "ANTHROPIC_API_KEY") == 1
    assert _quantas(raiz, "ANTHROPIC_WORKSPACE_ID") == 1

    escritas = VARIAVEIS_DO_ROTEIRO
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
