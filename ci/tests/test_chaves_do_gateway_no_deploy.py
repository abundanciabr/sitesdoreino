"""O deploy de célula EXECUTADO contra uma plataforma de mentira, com o gateway.

O incidente que este guarda existe para impedir, medido em 17/09/2026:

Em 15/09/2026 o commit `67ccf0ed` tornou `ALUNOS_API_TOKEN` e `TOKEN_CATALOGO`
obrigatórias no serviço `traefik` (`infra/docker-compose.yml`, na forma
`${VAR:?mensagem}`). A interpolação do Compose acontece antes de qualquer
subcomando, e não só no serviço que usa a variável: sem as duas no ambiente,
TODO `docker compose` naquela pasta reprova, inclusive um `config --services`
que não tem nada a ver com o Traefik.

`infra/sincronizar-infra-na-vps.sh` exporta as duas (bloco 0.1) e por isso
continuou funcionando. `infra/deploy-celula-na-vps.sh` não exportava nenhuma, e
a plataforma ficou dois dias sem receber entrega, com seis execuções seguidas do
`deploy-celula` vermelhas (PRs #1676, #1677, #1678, #1682, #1683 e #1684).

E ficou dois dias porque o erro MENTIA. O `|| true` do `SERVICOS=$(docker
compose config --services | grep ...)` engolia a falha da leitura do compose,
`SERVICOS` saía vazio e o script acusava a célula de não ter serviço algum. Quem
lia o log ia procurar um defeito no compose que não existia.

POR QUE ESTE GUARDA EXECUTA O SCRIPT, E NÃO LÊ O TEXTO DELE
-----------------------------------------------------------
Um guarda que procurasse a palavra `export` no arquivo passaria com o export
colocado DEPOIS do primeiro `docker compose`, que é justamente a versão que não
funciona. O que decide o desfecho é o ambiente que o processo `docker compose`
recebe, então o único jeito honesto de medir é rodar o script inteiro e olhar o
que ele consegue fazer. Foi assim que `ci/tests/test_por_a_chave_da_ia_do_admin.py`
resolveu o mesmo problema, e este arquivo segue aquele padrão.

O `docker` de mentira abaixo imita UMA coisa do docker real, a que importa
aqui: a interpolação do compose reprova quando falta uma variável obrigatória.
É por isso que o primeiro teste nasce vermelho no código de hoje.

O QUE ESTA SUÍTE NÃO PROVA, declarado em vez de fingido ([INV-CI01])
--------------------------------------------------------------------
Nada aqui toca a VPS, nem o Docker de verdade, nem o Traefik. A prova de que o
gateway sobe com os tokens certos é a próxima execução do `deploy-celula`
depois do merge.

Sem `bash` nesta máquina o guarda não tem o que medir, e isso é ERRO, nunca um
OK silencioso.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from conftest import BASH

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "infra" / "deploy-celula-na-vps.sh"

# Tokens de mentira com a forma dos reais. São o que este guarda procura em cada
# byte de saída: um segredo que aparece na tela do Actions é incidente
# (`armadilhas/090`), e o log de um deploy é público para quem tem o repositório.
TOKEN_DOS_ALUNOS = "alunos-t0k3n-de-mentira-nunca-na-tela"
TOKEN_DO_CATALOGO = "catalogo-t0k3n-de-mentira-nunca-na-tela"

# O compose de mentira, com as DUAS obrigatórias na forma exata do real e com
# uma célula que tem serviço auxiliar (`admin-huey`), porque a lista de serviços
# sai do compose e não de uma lista fixa no script.
COMPOSE = """services:
  traefik:
    image: traefik:v3.4
    environment:
      ALUNOS_API_TOKEN: ${ALUNOS_API_TOKEN:?defina ALUNOS_API_TOKEN em env/admin.env}
      TOKEN_CATALOGO: ${TOKEN_CATALOGO:?defina TOKEN_CATALOGO em env/admin.env}
  admin:
    image: admin
  admin-huey:
    image: admin
  postgres:
    image: postgres:17
"""

DOCKER_DE_MENTIRA = r"""#!/usr/bin/env bash
# `docker` de mentira. Imita a única coisa do docker real que decide este
# incidente: a interpolação do compose reprova, em QUALQUER subcomando, quando
# falta no ambiente uma variável escrita na forma ${VAR:?mensagem}.
[ "${1:-}" = "compose" ] || exit 0
shift
printf '%s\n' "$*" >> "$DOCKER_FALSO_DIARIO"

if [ -f docker-compose.yml ]; then
  while IFS= read -r exigida; do
    [ -n "$exigida" ] || continue
    nome="${exigida%%:*}"
    recado="${exigida#*:}"
    if [ -z "${!nome-}" ]; then
      printf 'validating %s/docker-compose.yml: services.traefik.environment.%s: required variable %s is missing a value: %s\n' \
        "$PWD" "$nome" "$nome" "$recado" >&2
      exit 1
    fi
  done <<FIM
$(grep -oE '\$\{[A-Za-z_][A-Za-z0-9_]*:\?[^}]*\}' docker-compose.yml | sed 's/^\${//; s/}$//; s/:?/:/')
FIM
fi

case "${1:-}" in
  config)
    if [ "${DOCKER_FALSO_CONFIG:-0}" -ne 0 ]; then
      printf 'yaml: line 9: could not find expected key\n' >&2
      exit "$DOCKER_FALSO_CONFIG"
    fi
    grep -E '^  [a-z][a-z0-9-]*:$' docker-compose.yml | tr -d ' :'
    exit 0
    ;;
  exec)
    # A pergunta ao Postgres sobre a base da célula. Resposta VAZIA com estado
    # zero é "esta célula não tem banco", o ramo legítimo em que a cópia de
    # segurança é dispensada e o resto do script segue.
    exit 0
    ;;
esac
exit 0
"""


def _codigo_do_script() -> str:
    """As linhas que o shell EXECUTA: sem comentário e sem linha em branco.

    Despir os comentários não é zelo, é o que separa um guarda de uma decoração.
    O script explica o incidente em prosa, e essa prosa cita as duas chaves pelo
    nome: um guarda que procurasse `TOKEN_CATALOGO` no arquivo inteiro
    continuaria verde com a chave retirada do laço de export, porque o
    comentário não sai junto. Medido por mutação em 17/09/2026.
    """
    return "\n".join(
        linha
        for linha in SCRIPT.read_text(encoding="utf-8").splitlines()
        if linha.strip() and not linha.lstrip().startswith("#")
    )


def _bash() -> str:
    assert BASH, (
        "não achei `bash` nesta máquina. Este guarda EXECUTA o script de deploy; "
        "sem interpretador ele não tem o que medir, e isso não é um OK "
        "([INV-CI01])."
    )
    return BASH


def _plataforma(
    tmp_path: Path,
    *,
    alunos: str | None = TOKEN_DOS_ALUNOS,
    catalogo: str | None = TOKEN_DO_CATALOGO,
    admin_env: bool = True,
) -> Path:
    """Uma /opt/plataforma de mentira, com o compose que exige os dois tokens."""
    raiz = tmp_path / "plataforma"
    (raiz / "env").mkdir(parents=True)
    (raiz / "docker-compose.yml").write_text(COMPOSE, encoding="utf-8")
    if admin_env:
        linhas = ["DJANGO_SECRET_KEY=x\n", "SCRIPT_NAME=/admin\n"]
        if alunos is not None:
            linhas.append(f"ALUNOS_API_TOKEN={alunos}\n")
        if catalogo is not None:
            linhas.append(f"TOKEN_CATALOGO={catalogo}\n")
        (raiz / "env" / "admin.env").write_text("".join(linhas), encoding="utf-8")
    return raiz


def _rodar(
    tmp_path: Path,
    raiz: Path,
    *,
    celula: str = "admin",
    **ajustes: str,
) -> tuple[subprocess.CompletedProcess, Path]:
    """Roda o script de deploy inteiro contra a plataforma de mentira.

    Devolve também o diário do docker de mentira: é nele que se lê se algum
    `up -d` chegou a acontecer depois de uma recusa.
    """
    pasta = tmp_path / "docker-de-mentira"
    pasta.mkdir(exist_ok=True)
    executavel = pasta / "docker"
    # Bytes, e não `write_text`: num Windows o modo texto trocaria cada quebra de
    # linha por CRLF e o `bash` recusaria o roteiro com "\r: command not found",
    # um erro que não se parece nada com a sua causa.
    executavel.write_bytes(DOCKER_DE_MENTIRA.encode("utf-8"))
    executavel.chmod(0o755)

    diario = tmp_path / "comandos-do-docker.txt"
    diario.write_text("", encoding="utf-8")

    ambiente = dict(
        os.environ,
        PATH=str(pasta) + os.pathsep + os.environ.get("PATH", ""),
        PLATAFORMA_DIR=str(raiz),
        CELULA=celula,
        DOCKER_FALSO_DIARIO=str(diario),
    )
    # Herdadas do ambiente de quem roda a suíte, elas fariam o teste passar sem
    # o script ter exportado nada. O que se mede aqui é o que o SCRIPT entrega
    # ao compose, então o ponto de partida é sem as duas.
    ambiente.pop("ALUNOS_API_TOKEN", None)
    ambiente.pop("TOKEN_CATALOGO", None)
    ambiente.update(ajustes)

    processo = subprocess.run(
        [_bash(), str(SCRIPT)],
        input="",
        capture_output=True,
        text=True,
        # O script fala PORTUGUÊS, com acento. Sem dizer o encoding aqui, o
        # Python de uma máquina Windows tenta cp1252 e a leitura da tela estoura
        # antes de qualquer asserção.
        encoding="utf-8",
        errors="replace",
        env=ambiente,
    )
    return processo, diario


def _tela(processo: subprocess.CompletedProcess) -> str:
    return (processo.stdout or "") + (processo.stderr or "")


# ---------------------------------------------------------------------------
# (a) O CASO QUE ESTÁ QUEBRADO EM PRODUÇÃO AGORA
# ---------------------------------------------------------------------------
def test_o_deploy_atravessa_com_o_compose_que_exige_os_tokens(tmp_path: Path):
    """As duas chaves estão em `env/admin.env`: a entrega tem de acontecer.

    É exatamente o mundo da VPS desde 15/09/2026. Sem o export, a interpolação
    reprova no primeiro `docker compose` e nenhuma célula é entregue.
    """
    raiz = _plataforma(tmp_path)
    processo, _ = _rodar(tmp_path, raiz)
    tela = _tela(processo)

    assert processo.returncode == 0, (
        "o deploy da célula 'admin' falhou contra um compose que exige "
        "ALUNOS_API_TOKEN e TOKEN_CATALOGO, com as duas presentes em "
        f"env/admin.env. Tela:\n{tela}"
    )
    assert "Serviços desta célula: admin" in tela, (
        f"o script não listou os serviços da célula. Tela:\n{tela}"
    )
    assert "admin-huey" in tela, (
        "o serviço auxiliar da célula ficou de fora da lista: ele subiria a "
        f"imagem ANTIGA, em silêncio. Tela:\n{tela}"
    )
    assert "ENTREGA-CONCLUIDA: admin" in tela, (
        f"o script não chegou ao fim. Tela:\n{tela}"
    )


def test_nenhum_dos_dois_tokens_aparece_na_tela(tmp_path: Path):
    """O log do run é lido por gente, e um segredo nele é incidente."""
    raiz = _plataforma(tmp_path)
    processo, _ = _rodar(tmp_path, raiz)
    tela = _tela(processo)

    for token in (TOKEN_DOS_ALUNOS, TOKEN_DO_CATALOGO):
        assert token not in tela, (
            "o VALOR de um token do gateway foi impresso na saída do deploy. "
            f"Tela:\n{tela}"
        )


# ---------------------------------------------------------------------------
# (b) O ERRO PARA DE MENTIR
# ---------------------------------------------------------------------------
def test_compose_ilegivel_nao_se_disfarca_de_celula_sem_servico(tmp_path: Path):
    """`docker compose config` falhou: a culpa não é da célula.

    Dois dias de caça ao defeito errado saíram daqui. A mensagem tem de dizer
    que a LEITURA do compose falhou, repetir o que o compose reclamou e apontar
    o lugar certo para consertar.
    """
    raiz = _plataforma(tmp_path)
    processo, diario = _rodar(tmp_path, raiz, DOCKER_FALSO_CONFIG="1")
    tela = _tela(processo)

    assert processo.returncode != 0, (
        f"o deploy seguiu com o compose ilegível. Tela:\n{tela}"
    )
    assert "não tem serviço algum" not in tela, (
        "a leitura do compose falhou e o script acusou a célula de não ter "
        "serviço. É a mentira que fez o incidente durar dois dias, porque manda "
        f"quem lê o log procurar um defeito que não existe. Tela:\n{tela}"
    )
    assert "could not find expected key" in tela, (
        "a reclamação do próprio compose não chegou à tela; sem ela ninguém "
        f"sabe qual variável ou qual linha está em falta. Tela:\n{tela}"
    )
    assert "env/" in tela, (
        "a mensagem não aponta /opt/plataforma/env/, que é onde a causa quase "
        f"sempre está. Tela:\n{tela}"
    )
    assert "up -d" not in diario.read_text(encoding="utf-8"), (
        "o script subiu contêiner depois de não conseguir ler o compose"
    )


def test_celula_sem_servico_continua_dizendo_exatamente_isso(tmp_path: Path):
    """O compose foi lido bem e a célula não existe: aí a mensagem de hoje está certa.

    Sem este caso, separar as duas situações poderia simplesmente apagar a
    recusa que impede um `up -d` sem argumento de subir a plataforma inteira.

    O nome da célula NÃO tem hífen de propósito, e trocá-lo por um que tenha
    cega este guarda. Medido por mutação em 18/09/2026: com hífen, comentar o
    `exit 1` da linha 166 deixa o script seguir e morrer adiante, na conferência
    do nome da base (`fantasma_db` aceita, `celula-que-nao-existe_db` não): o
    processo ainda sai diferente de zero, nenhum `up -d` acontece, e o teste
    continua verde com a recusa apagada. Sem hífen, a mesma sabotagem entrega
    `up -d --wait` sem serviço nenhum e sai 0, que é o estrago de verdade.
    """
    # guarda: infra/deploy-celula-na-vps.sh:166
    raiz = _plataforma(tmp_path)
    processo, diario = _rodar(tmp_path, raiz, celula="celula_inexistente")
    tela = _tela(processo)

    assert processo.returncode != 0, (
        f"o deploy de uma célula sem serviço nenhum seguiu em frente. Tela:\n{tela}"
    )
    assert "não tem serviço algum" in tela, (
        "a célula realmente não tem serviço no compose e o script não disse "
        f"isso. Tela:\n{tela}"
    )
    assert "required variable" not in tela, (
        "o compose reprovou na interpolação neste caso, então esta tela não "
        "está provando o que diz provar: aqui o compose tem de ser lido sem "
        f"erro algum. Tela:\n{tela}"
    )
    assert "up -d" not in diario.read_text(encoding="utf-8"), (
        "o script chamou `up -d` sem serviço nenhum na lista, e isso subiria a "
        "plataforma inteira"
    )


# ---------------------------------------------------------------------------
# (c) FAIL-CLOSED: chave ausente no env para o deploy, e nomeia qual
# ---------------------------------------------------------------------------
def test_token_ausente_no_env_para_o_deploy_e_nomeia_a_chave(tmp_path: Path):
    """Sem a chave, o compose cairia de qualquer jeito. Parar antes é mais honesto."""
    raiz = _plataforma(tmp_path, catalogo=None)
    processo, diario = _rodar(tmp_path, raiz)
    tela = _tela(processo)

    assert processo.returncode != 0, (
        f"o deploy seguiu sem TOKEN_CATALOGO em env/admin.env. Tela:\n{tela}"
    )
    assert "PAROU POR SEGURANÇA" in tela, (
        "quem recusou foi o compose, lá adiante, e não o script: a recusa tem "
        "de vir do próprio deploy, antes de qualquer contato com o Docker, para "
        f"que a tela explique a causa em vez de exibi-la. Tela:\n{tela}"
    )
    assert "TOKEN_CATALOGO" in tela, (
        f"o script não disse QUAL chave falta em env/admin.env. Tela:\n{tela}"
    )
    assert "admin.env" in tela, (
        f"o script não disse em qual arquivo a chave falta. Tela:\n{tela}"
    )
    # O diário VAZIO, e não só a ausência de `up -d`: sem esta recusa o script
    # exportaria a chave vazia, o compose reprovaria adiante na interpolação e a
    # tela teria as mesmas palavras por outra causa. Duas causas suficientes para
    # a mesma asserção é como um guarda morre sem ninguém notar; pego por mutação
    # em 17/09/2026. O que só esta recusa entrega é parar ANTES do Docker.
    assert diario.read_text(encoding="utf-8").strip() == "", (
        "o script chegou a falar com o docker sem a chave do gateway em mãos. "
        "Quem recusou foi o compose, não o deploy, e aí a tela exibe a reclamação "
        "de uma variável vazia em vez de explicar o que o operador tem de escrever"
    )
    assert TOKEN_DOS_ALUNOS not in tela, (
        "o token que EXISTE foi impresso na tela ao reclamar do que falta"
    )


def test_admin_env_ausente_para_o_deploy_sem_estouro_de_shell(tmp_path: Path):
    """Primeiro uso, ou VPS meio provisionada: o arquivo pode não existir.

    O desfecho tem de ser a mesma recusa explicada, e não um `grep: ... No such
    file` solto seguido de um deploy que segue assim mesmo.
    """
    raiz = _plataforma(tmp_path, admin_env=False)
    processo, diario = _rodar(tmp_path, raiz)
    tela = _tela(processo)

    assert processo.returncode != 0, (
        f"o deploy seguiu sem o arquivo env/admin.env existir. Tela:\n{tela}"
    )
    assert "PAROU POR SEGURANÇA" in tela, (
        "sem o arquivo, o `grep` do script falhou e o deploy seguiu até o "
        f"compose recusar: a recusa explicada tem de vir antes. Tela:\n{tela}"
    )
    assert "ALUNOS_API_TOKEN" in tela and "admin.env" in tela, (
        f"a recusa não nomeia a chave nem o arquivo que falta. Tela:\n{tela}"
    )
    assert diario.read_text(encoding="utf-8").strip() == "", (
        "o script falou com o docker sem ter as chaves do gateway em mãos"
    )


# ---------------------------------------------------------------------------
# (d) O MESMO INCIDENTE NÃO ACONTECE DE NOVO COM UMA CHAVE NOVA
# ---------------------------------------------------------------------------
def _obrigatorias_do_traefik() -> set[str]:
    """As variáveis `${VAR:?...}` do serviço `traefik` no compose de verdade.

    Só o `traefik`: as obrigatórias dos outros serviços são interpoladas a partir
    do `/opt/plataforma/.env`, que o Compose lê sozinho, sem ninguém exportar
    nada. As do gateway não têm esse caminho, e é exatamente por isso que elas
    precisam de um bloco de export em cada script que fala com o compose.
    """
    compose = (RAIZ / "infra" / "docker-compose.yml").read_text(encoding="utf-8")
    dentro = False
    trecho: list[str] = []
    for linha in compose.splitlines():
        if linha.startswith("  traefik:"):
            dentro = True
            continue
        if dentro:
            if linha.strip() and not linha.startswith("    "):
                break
            trecho.append(linha)
    assert trecho, (
        "não achei o serviço `traefik` em infra/docker-compose.yml. Se ele mudou "
        "de nome ou de lugar, este guarda parou de medir o que diz medir"
    )
    return set(re.findall(r"\$\{([A-Za-z_][A-Za-z0-9_]*):\?", "\n".join(trecho)))


def test_toda_obrigatoria_do_gateway_e_exportada_pelo_deploy():
    """Uma obrigatória nova no Traefik não pode parar a plataforma outra vez.

    Foi assim que isto começou: alguém acrescentou duas `${VAR:?...}` ao gateway
    e só um dos dois scripts que falam com o compose aprendeu a exportá-las.
    Acrescentar uma terceira agora reprova aqui, em segundos, em vez de reprovar
    na produção, dois dias depois.
    """
    exigidas = _obrigatorias_do_traefik()
    assert exigidas, (
        "o serviço `traefik` não exige mais variável nenhuma no compose. Se isso "
        "foi de propósito, o bloco de export do deploy perdeu a razão de existir "
        "e este guarda também"
    )
    codigo = _codigo_do_script()
    faltando = sorted(nome for nome in exigidas if nome not in codigo)
    assert not faltando, (
        f"o compose exige {faltando} no serviço traefik e "
        "infra/deploy-celula-na-vps.sh não exporta essas variáveis. Todo `docker "
        "compose` na VPS vai reprovar na interpolação, e a plataforma inteira para "
        "de receber entrega, como parou entre 15 e 17/09/2026"
    )


def test_o_deploy_le_o_env_de_forma_nominal_e_nunca_por_source():
    """Abrir um `env/` é privilégio: só as duas chaves, e nunca o arquivo inteiro.

    `source env/admin.env` traria para o ambiente do deploy a DATABASE_URL e tudo
    o mais que estiver ali, e bastaria um `set -x` de alguém depurando para o
    conteúdo virar log público.
    """
    codigo = _codigo_do_script()
    assert not re.search(r"(?:^|\s)(?:source|\.)\s+\S*\.env", codigo), (
        "o script de deploy passou a carregar um arquivo .env inteiro; ele só tem "
        "licença para ler as chaves do gateway, uma a uma, pelo nome"
    )
    assert "env/admin.env" in codigo, (
        "o script não lê mais env/admin.env. Sem ele as chaves do gateway não "
        "chegam ao compose"
    )
    outros_envs = set(re.findall(r"env/([a-z]+)\.env", codigo)) - {"admin"}
    assert not outros_envs, (
        f"o script passou a abrir também {sorted(outros_envs)}. A licença é de um "
        "arquivo só, e das duas chaves do gateway dentro dele"
    )
