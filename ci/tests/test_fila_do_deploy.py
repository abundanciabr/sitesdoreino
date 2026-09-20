"""O grupo `deploy` enfileira, e a chave que enfileira precisa estar escrita.

O ACHADO QUE ORIGINA ESTE GUARDA (TAR-529, decidido em 20/09/2026)
-------------------------------------------------------------------
Tres workflows publicam na VPS pelo MESMO `docker compose` e por isso dividem
o grupo de concorrencia `deploy`: `deploy-celula`, `deploy-infra` e
`rollback`. A medicao que recusa separar os grupos, com as linhas exatas dos
dois scripts que rodam dentro da VPS, esta no cabecalho do `concurrency:` de
`.github/workflows/deploy-infra.yml`, e continua valendo.

Ate 20/09/2026 o grupo rodava no padrao `queue: single`, que guarda UMA vaga
de pendente: um merge novo expulsava o deploy que esperava e ele terminava
`cancelled`, sem vermelho e sem alarme (`armadilhas/173`, `/183`, `/188`,
`/245`). Desde 07/05/2026 o `concurrency` aceita `queue: max`, que guarda ate
100 runs pendentes atendidos em ordem de chegada. As fontes e a medicao estao
em `docs/decisoes/PLANO-MESTRE-FILA-DE-DEPLOY.md`, itens 4 e 7.

O QUE ESTE GUARDA COBRA
-----------------------
1. todo workflow cujo `concurrency.group` e `deploy` declara `queue: max` e
   `cancel-in-progress: false`. Sem a chave, a fila volta a ser uma cadeira
   so, e o sintoma e um cinza no historico que ninguem procura;
2. nenhum workflow da pasta combina `queue: max` com
   `cancel-in-progress: true`. Essa combinacao e erro de validacao do proprio
   GitHub: a esteira para de rodar NO AR, nao no PR, que e o pior lugar para
   descobrir.

Workflow cujo grupo NAO e `deploy` fica de fora de proposito: grupo proprio
segue em `queue: single`, e essa e a decisao do item 7.2 do plano mestre.

A LISTA E DERIVADA, NUNCA COLADA: lista fixa envelhece em silencio. O minimo
de tres membros existe para que a derivacao quebrada nao passe vazia,
aprovando sem olhar nada.
"""

from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[2]
WORKFLOWS = RAIZ / ".github" / "workflows"

GRUPO_DO_DEPLOY = "deploy"
FILA = "max"
MINIMO_DE_MEMBROS = 3


def ler(caminho: Path) -> dict:
    return yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}


def _concorrencia(doc: dict) -> dict:
    """O bloco `concurrency` como dicionario. `concurrency: nome` nao e bloco."""
    bloco = (doc or {}).get("concurrency")
    return dict(bloco) if isinstance(bloco, dict) else {}


def _grupo(doc: dict) -> str:
    return str(_concorrencia(doc).get("group") or "").strip()


def workflows_da_pasta() -> list[Path]:
    """Derivada do repositorio a cada execucao, nunca escrita a mao."""
    return sorted(WORKFLOWS.glob("*.yml"))


def workflows_do_grupo_deploy() -> list[Path]:
    """Os que disputam o `docker compose` da VPS, lidos do YAML de hoje."""
    return [c for c in workflows_da_pasta() if _grupo(ler(c)) == GRUPO_DO_DEPLOY]


def faltas_da_fila(nome: str, doc: dict) -> list[str]:
    """As frestas do bloco `concurrency`. Lista vazia significa enfileirado."""
    bloco = _concorrencia(doc)
    faltas = []
    if str(bloco.get("queue") or "") != FILA:
        faltas.append(
            f"{nome}: esta no grupo `{GRUPO_DO_DEPLOY}` sem `queue: {FILA}`, "
            "entao a vaga de pendente e uma so e o run que espera morre "
            f"`cancelled` quando o proximo chega (veio: {bloco.get('queue')!r})"
        )
    if bloco.get("cancel-in-progress") is not False:
        faltas.append(
            f"{nome}: esta no grupo `{GRUPO_DO_DEPLOY}` sem "
            "`cancel-in-progress: false`, e um deploy interrompido no meio do "
            "`docker compose up` e pior que um deploy que espera a vez "
            f"(veio: {bloco.get('cancel-in-progress')!r})"
        )
    return faltas


def combinacao_que_o_github_recusa(nome: str, doc: dict) -> list[str]:
    """`queue: max` com `cancel-in-progress: true` nao e workflow valido."""
    bloco = _concorrencia(doc)
    if str(bloco.get("queue") or "") == FILA and bloco.get("cancel-in-progress") is True:
        return [
            f"{nome}: combina `queue: {FILA}` com `cancel-in-progress: true`, "
            "que e erro de validacao do workflow: a esteira para de rodar no "
            "ar, e nenhum check do PR acusa isso"
        ]
    return []


@pytest.mark.parametrize("caminho", workflows_do_grupo_deploy(), ids=lambda c: c.stem)
def test_workflow_do_grupo_deploy_enfileira_em_vez_de_expulsar(caminho: Path):
    assert faltas_da_fila(caminho.stem, ler(caminho)) == []


@pytest.mark.parametrize("caminho", workflows_da_pasta(), ids=lambda c: c.stem)
def test_nenhum_workflow_combina_fila_cheia_com_cancelamento(caminho: Path):
    assert combinacao_que_o_github_recusa(caminho.stem, ler(caminho)) == []


def test_a_lista_do_grupo_deploy_vem_da_pasta_e_nao_esta_vazia():
    """Derivacao quebrada em qualquer das duas pontas deixaria o guarda cego.

    Vazia, ele aprovaria sem olhar nada; larga demais, ele cobraria fila de
    workflow com grupo proprio, que segue em `queue: single` de proposito.
    """
    do_grupo = workflows_do_grupo_deploy()
    de_fora = [c for c in workflows_da_pasta() if c not in do_grupo]

    assert len(do_grupo) >= MINIMO_DE_MEMBROS, (
        f"o grupo `{GRUPO_DO_DEPLOY}` tem {len(do_grupo)} membro(s), menos que "
        f"os {MINIMO_DE_MEMBROS} que publicam na VPS: a derivacao quebrou"
    )
    assert de_fora, "todo workflow no grupo `deploy`: a derivacao quebrou"
    for esperado in ("deploy-celula.yml", "deploy-infra.yml", "rollback.yml"):
        assert WORKFLOWS / esperado in do_grupo, (
            f"{esperado} publica na VPS pelo mesmo compose e precisa estar no "
            "grupo compartilhado"
        )
    assert WORKFLOWS / "vacina-do-deploy.yml" in de_fora, (
        "a vacina tem grupo proprio por decisao medida (armadilhas/173): posta "
        "no grupo `deploy`, ela esperaria atras dos deploys que vem curar"
    )


def test_o_guarda_acusa_quando_a_fila_sai_de_um_so_dos_tres():
    """Mutacao sobre os workflows de verdade, um arquivo de cada vez."""
    for caminho in workflows_do_grupo_deploy():
        doc = ler(caminho)
        doc.setdefault("concurrency", {})["queue"] = FILA
        assert faltas_da_fila(caminho.stem, doc) == []

        doc["concurrency"].pop("queue")
        faltas = faltas_da_fila(caminho.stem, doc)

        assert len(faltas) == 1, f"{caminho.stem}: {faltas}"
        assert f"queue: {FILA}" in faltas[0]


def test_o_guarda_reprova_o_proximo_workflow_que_entrar_no_grupo_deploy():
    """O proximo que for publicar na VPS nao entra na fila sem a chave."""
    recem_nascido = yaml.safe_load(
        """
        name: deploy-qualquer-coisa
        on:
          workflow_dispatch:
        concurrency:
          group: deploy
          cancel-in-progress: true
        jobs:
          subir:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/checkout@v4
        """
    )
    faltas = faltas_da_fila("deploy-qualquer-coisa", recem_nascido)
    assert len(faltas) == 2
    assert f"queue: {FILA}" in faltas[0]
    assert "cancel-in-progress: false" in faltas[1]


def test_o_guarda_acusa_a_combinacao_que_o_github_recusa():
    """`queue: max` com `cancel-in-progress: true` so falha no ar, e tarde."""
    impossivel = yaml.safe_load(
        """
        name: deploy-impossivel
        on:
          workflow_dispatch:
        concurrency:
          group: deploy
          cancel-in-progress: true
          queue: max
        jobs:
          subir:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/checkout@v4
        """
    )
    acusacoes = combinacao_que_o_github_recusa("deploy-impossivel", impossivel)
    assert len(acusacoes) == 1
    assert f"queue: {FILA}" in acusacoes[0]


def test_fila_de_outro_nome_nao_serve():
    """`queue: single` passaria por qualquer busca de texto por `queue`."""
    disfarcado = yaml.safe_load(
        """
        name: deploy-disfarcado
        on:
          workflow_dispatch:
        concurrency:
          group: deploy
          cancel-in-progress: false
          queue: single
        jobs:
          subir:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/checkout@v4
        """
    )
    faltas = faltas_da_fila("deploy-disfarcado", disfarcado)
    assert len(faltas) == 1
    assert f"queue: {FILA}" in faltas[0]
