"""Todo workflow que alcanca a VPS confere alguma coisa antes de abrir a conexao.

O ACHADO QUE ORIGINA ESTE GUARDA (TAR-461, medido em 18/09/2026)
----------------------------------------------------------------
A CONSTITUICAO, Lei 5, diz que agentes nao possuem chave SSH da VPS, e que
isso nao e proibicao, e inexistencia. Isso e verdade para a SESSAO do agente e
era falso para o CAMINHO do codigo: 16 dos 25 workflows carregam
`DEPLOY_SSH_KEY` e abrem shell na VPS como o usuario `deploy`, e apenas tres
conferiam qualquer coisa antes (`deploy-celula` e `deploy-infra` pelo
`ci/portao_de_deploy.py`, `rollback` pelo `ci/rollback.py`).

Os treze restantes, todos `workflow_dispatch`, classificados pelo efeito que
cada um PRETENDE ter na producao:

  apaga    esvaziar-caixa            apagar_definitivamente, sem volta
  apaga    limpar-avisos-orfaos      retirar_cartas, `.delete()` nas cartas
  apaga    semear-demo-caixa         semear_demo --remover tira do quadro
  escreve  backfill-mensagens-do-forum, backfill-pontos-do-forum,
           canario-fase-3-outbox (cunha sessao e matricula), ligar-os-degraus,
           semear-areas-do-forum, semear-boas-vindas, semear-caixa,
           semear-demo-caixa, semear-duvidas-do-forum, semear-economia
  le       conferir-as-fichas        reconciliar_perfis so compara numeros

POR QUE A CLASSIFICACAO NAO GRADUA O PORTAO
-------------------------------------------
Ela descreve o efeito PRETENDIDO, nao o efeito ALCANCAVEL. Num disparo por
`workflow_dispatch` o GitHub roda o YAML e o `script_path` da ref escolhida, e
nao os da main. Quem consegue empurrar um ramo escolhe o que o `infra/*.sh`
manda para a VPS, e o efeito alcancavel dos dezesseis e o mesmo: shell
arbitrario como `deploy`. Por isso o degrau minimo e identico para os treze,
e e o que o `canario-fase-3-outbox` ja praticava sozinho: recusar ref que nao
seja main, antes de qualquer passo que toque na chave.

O SEGUNDO DEGRAU, DECIDIDO PELO MANTENEDOR EM 19/09/2026
---------------------------------------------------------
O passo de recusa mora no proprio ramo, entao quem empurra um ramo tambem
consegue apaga-lo no mesmo empurrao. So o GitHub fecha isso, e so o mantenedor
configura o GitHub. Ele decidiu a ordem, e ela e esta:

  1. todo job que usa a chave declara `environment: vps` (este guarda cobra)
  2. ele cria o Environment `vps` com a trava de branch em `main` e a chave
     dentro
  3. depois de um deploy real terminar verde, ele apaga o segredo antigo do
     repositorio

Entre o passo 1 e o 2 nada quebra, e isso foi medido, nao suposto: o
Environment `vps` ainda nao existe (`gh api repos/.../environments` devolveu
`total_count: 0`), e a documentacao do GitHub diz que rodar um workflow que
cita um environment inexistente cria esse environment, e que o environment
assim criado nasce sem regra de protecao e sem segredo proprio. Sem segredo
proprio, `secrets.DEPLOY_SSH_KEY` continua vindo do segredo do repositorio,
porque o segredo do environment so vence quando existe. Sem regra de protecao,
nenhum job fica pendurado esperando aprovacao humana.

Declarar `environment:` nao exige `deployments: write` no GITHUB_TOKEN: os
proprios workflows-modelo do GitHub (`actions/starter-workflows`, pasta
`deployments/`) declaram o job de deploy com `permissions: contents: none` e
`environment:`. Os dezessete jobs desta casa tem `contents: read`, que e mais.

A LISTA E DERIVADA, NUNCA COLADA: lista fixa envelhece em silencio (Classe 8).
"""

import json
from pathlib import Path

import pytest
import yaml


RAIZ = Path(__file__).resolve().parents[2]
WORKFLOWS = RAIZ / ".github" / "workflows"

CHAVE = "DEPLOY_SSH_KEY"
RECUSA_DE_REF = "github.ref != 'refs/heads/main'"
PORTAO_DE_DEPLOY = "ci/portao_de_deploy.py"
AMBIENTE = "vps"


def _achatar(no) -> str:
    """O no inteiro como uma linha so, para procurar texto sem quebra."""
    return json.dumps(no, ensure_ascii=False, default=str)


def _gatilhos(doc: dict) -> dict:
    """PyYAML le a chave `on:` do YAML 1.1 como o booleano True."""
    return dict(doc.get(True) or doc.get("on") or {})


def _exigidos(jobs: dict, nome: str) -> list:
    """`nome` e todo job que ele exige, transitivamente, em ordem de execucao."""
    vistos: list = []
    fila = [nome]
    while fila:
        atual = fila.pop(0)
        if atual in vistos or atual not in jobs:
            continue
        vistos.append(atual)
        precisa = (jobs[atual] or {}).get("needs") or []
        if isinstance(precisa, str):
            precisa = [precisa]
        fila.extend(precisa)
    vistos.remove(nome)
    return vistos


def _passos_antes_da_chave(jobs: dict, nome: str) -> list | None:
    """Passos que rodam antes do primeiro que usa a chave, ou None se nenhum usa."""
    passos = (jobs[nome] or {}).get("steps") or []
    for i, passo in enumerate(passos):
        if CHAVE in _achatar(passo):
            antes = list(passos[:i])
            for anterior in _exigidos(jobs, nome):
                antes.extend((jobs[anterior] or {}).get("steps") or [])
            return antes
    return None


def alcanca_a_vps(caminho: Path) -> bool:
    return CHAVE in caminho.read_text(encoding="utf-8")


def workflows_que_alcancam_a_vps() -> list[Path]:
    """Derivada do repositorio a cada execucao, nunca escrita a mao."""
    return [c for c in sorted(WORKFLOWS.glob("*.yml")) if alcanca_a_vps(c)]


def _ambiente_do_job(job: dict) -> str:
    """`environment: vps` e `environment: {name: vps}` sao a mesma declaracao."""
    valor = (job or {}).get("environment")
    if isinstance(valor, dict):
        return str(valor.get("name") or "")
    return str(valor or "")


def faltas_de_conferencia(nome: str, doc: dict) -> list[str]:
    """As frestas de um workflow que alcanca a VPS. Lista vazia significa fechado."""
    jobs = doc.get("jobs") or {}
    disparavel = "workflow_dispatch" in _gatilhos(doc)
    exigido = RECUSA_DE_REF if disparavel else PORTAO_DE_DEPLOY
    faltas = []
    for job in jobs:
        antes = _passos_antes_da_chave(jobs, job)
        if antes is None:
            continue
        if not any(exigido in _achatar(passo) for passo in antes):
            faltas.append(
                f"{nome}: o job `{job}` abre conexao com a VPS sem que "
                f"`{exigido}` tenha rodado antes"
            )
        if _ambiente_do_job(jobs[job]) != AMBIENTE:
            faltas.append(
                f"{nome}: o job `{job}` abre conexao com a VPS sem declarar "
                f"`environment: {AMBIENTE}`, e fica fora da trava de branch do GitHub"
            )
    return faltas


@pytest.mark.parametrize(
    "caminho", workflows_que_alcancam_a_vps(), ids=lambda c: c.stem
)
def test_workflow_que_alcanca_a_vps_confere_antes_de_abrir_a_conexao(caminho: Path):
    doc = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    assert faltas_de_conferencia(caminho.stem, doc) == []


def test_a_lista_dos_workflows_com_chave_vem_do_repositorio():
    """Derivacao quebrada em qualquer das duas pontas deixaria o guarda cego.

    Vazia, ele aprovaria sem olhar nada; larga demais, ele cobraria portao de
    workflow que nem chega perto da VPS e a casa aprenderia a ignora-lo.
    """
    com_chave = workflows_que_alcancam_a_vps()
    sem_chave = [c for c in sorted(WORKFLOWS.glob("*.yml")) if not alcanca_a_vps(c)]

    assert com_chave, "nenhum workflow com a chave: a derivacao quebrou"
    assert sem_chave, "todos os workflows tem a chave: a derivacao quebrou"
    assert WORKFLOWS / "deploy-celula.yml" in com_chave
    assert WORKFLOWS / "muralhas.yml" in sem_chave


def test_o_guarda_reprova_workflow_disparavel_que_nasce_sem_recusa_de_ref():
    """O proximo workflow de semeadura nao entra na VPS sem o degrau."""
    recem_nascido = yaml.safe_load(
        """
        name: semear-qualquer-coisa
        on:
          workflow_dispatch:
        jobs:
          semear:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/checkout@v4
              - uses: appleboy/ssh-action@v1
                with:
                  key: ${{ secrets.DEPLOY_SSH_KEY }}
                  script_path: infra/semear-qualquer-coisa.sh
        """
    )
    faltas = faltas_de_conferencia("semear-qualquer-coisa", recem_nascido)
    assert len(faltas) == 2
    assert RECUSA_DE_REF in faltas[0]
    assert f"environment: {AMBIENTE}" in faltas[1]


def test_o_guarda_acusa_quando_o_portao_sai_do_deploy_de_celula():
    """Mutacao sobre o workflow de verdade: sem o portao, o guarda reprova."""
    caminho = WORKFLOWS / "deploy-celula.yml"
    doc = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    assert faltas_de_conferencia("deploy-celula", doc) == []

    doc["jobs"]["portao"]["steps"] = [{"run": "echo nao confiro nada"}]
    faltas = faltas_de_conferencia("deploy-celula", doc)

    assert [f.split("`")[1] for f in faltas] == ["publicar-dados-admin", "deploy"]
    assert all(PORTAO_DE_DEPLOY in f for f in faltas)


def test_o_guarda_acusa_quando_a_recusa_de_ref_sai_do_rollback():
    """Mutacao sobre o workflow de verdade: sem a recusa, o guarda reprova."""
    caminho = WORKFLOWS / "rollback.yml"
    doc = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    assert faltas_de_conferencia("rollback", doc) == []

    jobs = doc["jobs"]
    for job in jobs.values():
        job["steps"] = [p for p in job["steps"] if RECUSA_DE_REF not in _achatar(p)]
    faltas = faltas_de_conferencia("rollback", doc)

    assert [f.split("`")[1] for f in faltas] == ["aplicar"]
    assert RECUSA_DE_REF in faltas[0]


def test_o_guarda_acusa_quando_o_ambiente_sai_de_um_job_que_usa_a_chave():
    """Mutacao sobre o workflow de verdade: sem o ambiente, o guarda reprova.

    Sem ele o job fica fora da trava de branch que o mantenedor vai por no
    Environment, e volta a receber a chave vindo de qualquer ramo.
    """
    caminho = WORKFLOWS / "deploy-celula.yml"
    doc = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    assert faltas_de_conferencia("deploy-celula", doc) == []

    del doc["jobs"]["deploy"]["environment"]
    faltas = faltas_de_conferencia("deploy-celula", doc)

    assert [f.split("`")[1] for f in faltas] == ["deploy"]
    assert f"environment: {AMBIENTE}" in faltas[0]


def test_ambiente_de_outro_nome_nao_serve():
    """`environment: teste` passaria por qualquer busca de texto por environment."""
    disfarcado = yaml.safe_load(
        """
        name: semear-disfarcada
        on:
          workflow_dispatch:
        jobs:
          semear:
            runs-on: ubuntu-latest
            environment: teste
            steps:
              - name: Recusar ref que nao seja main
                if: github.ref != 'refs/heads/main'
                run: exit 1
              - uses: appleboy/ssh-action@v1
                with:
                  key: ${{ secrets.DEPLOY_SSH_KEY }}
        """
    )
    faltas = faltas_de_conferencia("semear-disfarcada", disfarcado)
    assert len(faltas) == 1
    assert f"environment: {AMBIENTE}" in faltas[0]


def test_ambiente_na_forma_longa_vale_igual():
    """`environment: {name: vps, url: ...}` e a mesma declaracao, e passa."""
    forma_longa = yaml.safe_load(
        """
        name: semear-forma-longa
        on:
          workflow_dispatch:
        jobs:
          semear:
            runs-on: ubuntu-latest
            environment:
              name: vps
              url: https://meshcraft.top
            steps:
              - name: Recusar ref que nao seja main
                if: github.ref != 'refs/heads/main'
                run: exit 1
              - uses: appleboy/ssh-action@v1
                with:
                  key: ${{ secrets.DEPLOY_SSH_KEY }}
        """
    )
    assert faltas_de_conferencia("semear-forma-longa", forma_longa) == []


def test_a_recusa_de_ref_para_o_job_em_vez_de_apenas_avisar():
    """Um passo que so imprime aviso deixaria a conexao abrir logo depois."""
    for caminho in workflows_que_alcancam_a_vps():
        doc = yaml.safe_load(caminho.read_text(encoding="utf-8"))
        for job in (doc.get("jobs") or {}).values():
            for passo in (job or {}).get("steps") or []:
                if RECUSA_DE_REF not in _achatar(passo):
                    continue
                assert "exit 1" in passo.get("run", ""), (
                    f"{caminho.stem}: a recusa de ref precisa sair com erro"
                )
