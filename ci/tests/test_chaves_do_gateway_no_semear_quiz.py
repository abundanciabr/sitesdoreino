"""O semeador do quiz EXECUTADO contra uma plataforma de mentira, com o gateway.

O incidente que este guarda existe para impedir, medido em 20/09/2026:

Em 15/09/2026 o commit `67ccf0ed` tornou `ALUNOS_API_TOKEN` e `TOKEN_CATALOGO`
obrigatórias no serviço `traefik` (`infra/docker-compose.yml`, na forma
`${VAR:?mensagem}`). A interpolação do Compose acontece antes de qualquer
subcomando e sobre o arquivo inteiro: sem as duas no ambiente, TODO `docker
compose` naquela pasta reprova, inclusive um `ps` que não tem nada a ver com o
Traefik.

`infra/deploy-celula-na-vps.sh` aprendeu isso em 17/09 (depois de seis deploys
vermelhos) e `infra/reverter-celula-na-vps.sh` em 19/09 (depois de quatro
smokes). O semeador do quiz não aprendeu, e foi o primeiro a tentar semear
depois de 15/09: os runs 35479761568 e 35479784690 morreram em três segundos,
com `meshcraft.top` e `meshcraft.top/quiz/healthz` respondendo 200.

E a mensagem MENTIA por omissão. O guarda era
`docker compose ps >/dev/null 2>&1 || parar "não consegui falar com o Docker
Compose aqui."`: o `2>&1` jogava no lixo justamente a linha do Docker que dizia
qual variável faltava. Quem lia o log não tinha como distinguir daemon parado,
pasta errada e chave ausente.

POR QUE ESTE GUARDA EXECUTA O SCRIPT, E NÃO LÊ O TEXTO DELE
-----------------------------------------------------------
Um guarda que procurasse a palavra `export` no arquivo passaria com o export
colocado DEPOIS do primeiro `docker compose`, que é exatamente a versão que não
funciona. O que decide o desfecho é o ambiente que o processo `docker compose`
recebe, então o único jeito honesto de medir é rodar o script e olhar até onde
ele chega. Mesmo padrão de `ci/tests/test_chaves_do_gateway_no_deploy.py`.

O QUE ESTA SUÍTE NÃO PROVA, declarado em vez de fingido ([INV-CI01])
--------------------------------------------------------------------
Nada aqui toca a VPS, nem o Docker de verdade, nem o Traefik, nem o banco do
quiz. A fronteira medida é uma só: o script ATRAVESSA o portão do Compose e
chega ao passo 1/6. Que o quiz nasça certo no banco é o que a execução real do
`semear-quiz` prova, depois do merge.

Sem `bash` nesta máquina o guarda não tem o que medir, e isso é ERRO, nunca um
OK silencioso.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from conftest import BASH

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "infra" / "semear-quiz.sh"

# Tokens de mentira com a forma dos reais. São o que este guarda procura em cada
# byte de saída: segredo na tela do Actions é incidente (`armadilhas/090`).
TOKEN_DOS_ALUNOS = "alunos-t0k3n-de-mentira-nunca-na-tela"
TOKEN_DO_CATALOGO = "catalogo-t0k3n-de-mentira-nunca-na-tela"

# O compose de mentira, com as DUAS obrigatórias na forma exata do real.
COMPOSE = """services:
  traefik:
    image: traefik:v3.4
    environment:
      ALUNOS_API_TOKEN: ${ALUNOS_API_TOKEN:?defina ALUNOS_API_TOKEN em env/admin.env}
      TOKEN_CATALOGO: ${TOKEN_CATALOGO:?defina TOKEN_CATALOGO em env/admin.env}
  catalogo:
    image: catalogo
  quiz:
    image: quiz
  quiz-relay:
    image: quiz
  postgres:
    image: postgres:17
"""

DOCKER_DE_MENTIRA = r"""#!/usr/bin/env bash
# `docker` de mentira. Imita a única coisa do docker real que decide este
# incidente: a interpolação do compose reprova, em QUALQUER subcomando, quando
# falta no ambiente uma variável escrita na forma ${VAR:?mensagem}.
[ "${1:-}" = "compose" ] || exit 0
shift

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

if [ "${1:-}" = "ps" ]; then
  shift
  # `ps --status running --services`: a lista sai do próprio compose, como no real.
  case "${*:-}" in
    *--services*) grep -E '^  [a-z][a-z0-9-]*:$' docker-compose.yml | tr -d ' :' ;;
  esac
fi
exit 0
"""


def _bash() -> str:
    assert BASH, (
        "não achei `bash` nesta máquina. Este guarda EXECUTA o semeador do quiz; "
        "sem interpretador ele não tem o que medir, e isso não é um OK "
        "([INV-CI01])."
    )
    return BASH


def _plataforma(
    tmp_path: Path,
    *,
    alunos: str | None = TOKEN_DOS_ALUNOS,
    catalogo: str | None = TOKEN_DO_CATALOGO,
) -> Path:
    """Uma /opt/plataforma de mentira, com o compose que exige os dois tokens."""
    raiz = tmp_path / "plataforma"
    (raiz / "env").mkdir(parents=True)
    (raiz / "docker-compose.yml").write_text(COMPOSE, encoding="utf-8")
    linhas = ["DJANGO_SECRET_KEY=x\n", "SCRIPT_NAME=/admin\n"]
    if alunos is not None:
        linhas.append(f"ALUNOS_API_TOKEN={alunos}\n")
    if catalogo is not None:
        linhas.append(f"TOKEN_CATALOGO={catalogo}\n")
    (raiz / "env" / "admin.env").write_text("".join(linhas), encoding="utf-8")
    return raiz


def _sem_o_export(texto: str) -> str:
    """A MUTAÇÃO: o script lê as chaves e não as entrega ao ambiente.

    É o defeito com roupa nova, e a versão que um guarda de leitura de texto
    deixaria passar, porque a palavra `export` continua no arquivo dentro dos
    comentários.
    """
    linhas = [
        linha
        for linha in texto.splitlines()
        if not linha.lstrip().startswith('export "$CHAVE_DO_GATEWAY=')
    ]
    return "\n".join(linhas) + "\n"


def _rodar(
    tmp_path: Path,
    raiz: Path,
    *,
    roteiro: str | None = None,
) -> subprocess.CompletedProcess:
    """Roda o semeador contra a plataforma de mentira.

    `roteiro` permite rodar uma versão MUTADA do script; sem ele, roda o
    arquivo que vai para a VPS.
    """
    pasta = tmp_path / "docker-de-mentira"
    pasta.mkdir(exist_ok=True)
    executavel = pasta / "docker"
    # Bytes, e não `write_text`: num Windows o modo texto trocaria cada quebra de
    # linha por CRLF e o `bash` recusaria o roteiro com "\r: command not found",
    # um erro que não se parece nada com a sua causa.
    executavel.write_bytes(DOCKER_DE_MENTIRA.encode("utf-8"))
    executavel.chmod(0o755)

    alvo = SCRIPT
    if roteiro is not None:
        alvo = tmp_path / "semear-quiz-mutado.sh"
        alvo.write_bytes(roteiro.encode("utf-8"))

    ambiente = dict(
        os.environ,
        PATH=str(pasta) + os.pathsep + os.environ.get("PATH", ""),
        PLATAFORMA_DIR=str(raiz).replace("\\", "/"),
        HOST_QUIZ="meshcraft.top",
    )
    # Herdadas do ambiente de quem roda a suíte, elas fariam o teste passar sem
    # o script ter exportado nada. O que se mede aqui é o que o SCRIPT entrega
    # ao compose, então o ponto de partida é sem as duas.
    ambiente.pop("ALUNOS_API_TOKEN", None)
    ambiente.pop("TOKEN_CATALOGO", None)

    return subprocess.run(
        [_bash(), str(alvo)],
        input="",
        capture_output=True,
        text=True,
        # O script fala PORTUGUÊS, com acento. Sem dizer o encoding aqui, o
        # Python de uma máquina Windows tenta cp1252 e a leitura da tela estoura
        # antes de qualquer asserção.
        encoding="utf-8",
        errors="replace",
        timeout=120,
        env=ambiente,
    )


def _tela(processo: subprocess.CompletedProcess) -> str:
    return (processo.stdout or "") + (processo.stderr or "")


PORTAO = "não consegui falar com o Docker Compose"


# ---------------------------------------------------------------------------
# (a) O CASO QUE ESTAVA QUEBRADO EM PRODUÇÃO
# ---------------------------------------------------------------------------
def test_o_semeador_atravessa_o_portao_do_compose(tmp_path: Path) -> None:
    """As duas chaves estão em `env/admin.env`: o semeador tem de passar.

    É o mundo da VPS desde 15/09/2026. Sem o preâmbulo, a interpolação reprova
    no primeiro `docker compose` e nenhum quiz é publicado.
    """
    # guarda: infra/semear-quiz.sh:111
    tela = _tela(_rodar(tmp_path, _plataforma(tmp_path)))
    assert PORTAO not in tela, (
        "o semeador parou no portão do Compose com as duas chaves presentes em "
        f"env/admin.env. Tela:\n{tela}"
    )
    assert "== 1/6" in tela, (
        f"o semeador não chegou ao primeiro passo. Tela:\n{tela}"
    )


def test_nenhum_dos_dois_tokens_aparece_na_tela(tmp_path: Path) -> None:
    """O log do run é lido por gente, e um segredo nele é incidente."""
    tela = _tela(_rodar(tmp_path, _plataforma(tmp_path)))
    for token in (TOKEN_DOS_ALUNOS, TOKEN_DO_CATALOGO):
        assert token not in tela, (
            f"o semeador imprimiu um token na tela. Tela:\n{tela}"
        )


# ---------------------------------------------------------------------------
# (b) A MUTAÇÃO: ler sem exportar precisa reprovar
# ---------------------------------------------------------------------------
def test_sem_o_export_o_semeador_para_no_portao_do_compose(tmp_path: Path) -> None:
    """Tirar o export do script real tem de derrubar a execução.

    Se este teste ficar verde com a mutação aplicada, o guarda não está medindo
    nada: seria possível apagar o preâmbulo e a suíte continuaria dizendo que
    está tudo bem.
    """
    mutado = _sem_o_export(SCRIPT.read_text(encoding="utf-8"))
    assert mutado != SCRIPT.read_text(encoding="utf-8"), (
        "a mutação não encontrou a linha do export; o guarda está apontando "
        "para um script que mudou de forma."
    )
    processo = _rodar(tmp_path, _plataforma(tmp_path), roteiro=mutado)
    tela = _tela(processo)
    assert processo.returncode != 0, (
        f"o semeador seguiu adiante sem exportar as chaves. Tela:\n{tela}"
    )
    assert PORTAO in tela, (
        f"esperava a parada no portão do Compose. Tela:\n{tela}"
    )


# ---------------------------------------------------------------------------
# (c) O RECADO DO DOCKER, que a versão antiga jogava no lixo
# ---------------------------------------------------------------------------
def test_a_parada_no_portao_mostra_o_que_o_docker_disse(tmp_path: Path) -> None:
    """Sem a linha do Docker, a mensagem não distingue daemon parado de chave
    faltando, e foi isso que custou a investigação de 20/09/2026."""
    # guarda: infra/semear-quiz.sh:100
    mutado = _sem_o_export(SCRIPT.read_text(encoding="utf-8"))
    tela = _tela(_rodar(tmp_path, _plataforma(tmp_path), roteiro=mutado))
    assert "required variable ALUNOS_API_TOKEN is missing a value" in tela, (
        "a tela não trouxe o recado do próprio Docker, que é o que diz QUAL "
        f"variável falta. Tela:\n{tela}"
    )
    assert "O QUE FAZER" in tela, (
        f"a parada não diz o que fazer em seguida. Tela:\n{tela}"
    )


# ---------------------------------------------------------------------------
# (d) A chave ausente no arquivo para ANTES de qualquer compose
# ---------------------------------------------------------------------------
def test_chave_ausente_no_arquivo_para_com_recado_proprio(tmp_path: Path) -> None:
    """Falha fechada: sem a chave no `env/admin.env`, nada é tentado."""
    # guarda: infra/semear-quiz.sh:109
    raiz = _plataforma(tmp_path, alunos=None)
    processo = _rodar(tmp_path, raiz)
    tela = _tela(processo)
    assert processo.returncode != 0, f"seguiu sem a chave. Tela:\n{tela}"
    assert "ALUNOS_API_TOKEN está ausente ou vazia" in tela, tela
    assert "NADA foi alterado" in tela, tela
    # PARA AQUI, e não adiante. Sem esta linha o guarda não morde a sabotagem
    # que apaga o `exit 1`: o script reclamaria da chave, seguiria com ela
    # vazia e morreria no portão do Compose — outro erro, outra investigação,
    # e um teste verde por cima. Medido com `ci/provar_guardas.py`.
    assert PORTAO not in tela, (
        "o script passou da conferência da chave e só parou no portão do "
        f"Compose. A parada tem de ser aqui, com este recado. Tela:\n{tela}"
    )
    assert TOKEN_DO_CATALOGO not in tela, (
        "o script imprimiu o valor da outra chave ao reclamar da que falta."
    )
