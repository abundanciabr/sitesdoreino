"""Suíte adversarial do portão de deploy — cada linha da tabela de estados.

A tabela vem de docs/decisoes/PROJETO-PORTAO-DEPLOY.md: para cada situação, o
exit code exato (0 PASS/SKIP · 1 FAIL · 2 ERROR). O `gh` de verdade é trocado
por um executável de mentira (costura PORTAO_GH) que devolve JSON roteirizado —
o portão REAL roda inteiro contra respostas controladas, no mesmo espírito do
exportador falso do conftest.

O último teste (`test_workflow_de_deploy_exige_o_portao`) é a mitigação do
vetor de burla "editar o YAML e remover o job portao": ele afirma a FORMA dos
dois workflows de deploy e roda no `muralhas` (PR).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

CI = Path(__file__).resolve().parents[1]
if str(CI) not in sys.path:
    sys.path.insert(0, str(CI))

RAIZ = CI.parent
PORTAO = CI / "portao_de_deploy.py"

REPO = "abundanciabr/sitesdoreino"
SHA_MERGE = "a" * 40
SHA_PR = "b" * 40
RUN_ID_SELF = "999999"

CI_CELULA = ".github/workflows/ci-celula.yml"
ALARME = ".github/workflows/alarme-main.yml"
MURALHAS = ".github/workflows/muralhas.yml"
DEPLOY_CELULA = ".github/workflows/deploy-celula.yml"
VIGIA = ".github/workflows/vigia-do-cadeado.yml"

GH_FALSO = """\
import json, os, sys
with open(os.environ["GH_FALSO_ROTEIRO"], encoding="utf-8") as f:
    roteiro = json.load(f)
caminho = ""
for arg in sys.argv[1:]:
    if arg != "api" and not arg.startswith("-"):
        caminho = arg
        break
for chave, resposta in roteiro.get("respostas", {}).items():
    if chave in caminho:
        if isinstance(resposta, dict) and "__cru__" in resposta:
            sys.stdout.write(resposta["__cru__"])
        else:
            sys.stdout.write(json.dumps(resposta))
        sys.exit(0)
sys.stderr.write("gh falso: sem resposta para " + caminho + chr(10))
sys.exit(1)
"""


def run_(id_, path, *, conclusao="success", status="completed", evento="push"):
    return {
        "id": id_,
        "path": path,
        "status": status,
        "conclusion": conclusao,
        "event": evento,
        "html_url": f"https://example.invalid/run/{id_}",
    }


def jobs_(*pares):
    return {
        "jobs": [
            {"name": nome, "status": "completed", "conclusion": conclusao}
            for nome, conclusao in pares
        ]
    }


def cenario_verde() -> dict:
    """O caminho feliz completo — os outros cenários mutam este."""
    return {
        "respostas": {
            f"runs?head_sha={SHA_MERGE}": {
                "workflow_runs": [
                    # O run do PRÓPRIO deploy (em andamento) — precisa ser
                    # ignorado; sem isso o portão se esperaria para sempre.
                    run_(
                        int(RUN_ID_SELF),
                        DEPLOY_CELULA,
                        status="in_progress",
                        conclusao=None,
                    ),
                    run_(11, CI_CELULA),
                    run_(12, ALARME),
                ]
            },
            "runs/11/jobs": jobs_(
                ("detectar", "success"),
                ("ci-celula", "success"),
                ("ci-celula-gate", "success"),
            ),
            "runs/12/jobs": jobs_(
                ("guardas do repositório", "success"), ("alarme", "skipped")
            ),
            f"commits/{SHA_MERGE}/pulls": [
                {
                    "number": 7,
                    "merge_commit_sha": SHA_MERGE,
                    "head": {"sha": SHA_PR},
                }
            ],
            f"runs?head_sha={SHA_PR}": {
                "workflow_runs": [run_(21, MURALHAS, evento="pull_request")]
            },
            "runs/21/jobs": jobs_(("muralhas", "success")),
        }
    }


def rodar_portao(tmp_path: Path, roteiro: dict, **env_extra: str):
    gh_py = tmp_path / "gh_falso.py"
    gh_py.write_text(GH_FALSO, encoding="utf-8")
    (tmp_path / "roteiro.json").write_text(
        json.dumps(roteiro, ensure_ascii=False), encoding="utf-8"
    )
    env = dict(os.environ)
    env.update(
        {
            "PORTAO_GH": json.dumps([sys.executable, str(gh_py)]),
            "GH_FALSO_ROTEIRO": str(tmp_path / "roteiro.json"),
            "REPO": REPO,
            "SHA": SHA_MERGE,
            "RUN_ID": RUN_ID_SELF,
            "EVENTO": "push",
            "CELULAS": '["quiz"]',
            "PORTAO_MODO": "celula",
            "PORTAO_INTERVALO": "0",
            "PORTAO_GRACA": "0",
            "PORTAO_TIMEOUT": "0",
            "PYTHONUTF8": "1",
        }
    )
    env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(PORTAO)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=180,
    )


# ---------------------------------------------------------------------------
# A tabela de estados, caso a caso
# ---------------------------------------------------------------------------


def test_tudo_verde_passa(tmp_path):
    proc = rodar_portao(tmp_path, cenario_verde())
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "RESULTADO  PASS" in proc.stdout


def test_teste_da_celula_quebrou_reprova(tmp_path):
    cen = cenario_verde()
    cen["respostas"][f"runs?head_sha={SHA_MERGE}"]["workflow_runs"][1][
        "conclusion"
    ] = "failure"
    proc = rodar_portao(tmp_path, cen)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "RESULTADO  FAIL" in proc.stdout


def test_pr_de_docs_e_skip_declarado_sem_tocar_a_api(tmp_path):
    # Roteiro VAZIO de propósito: se o portão chamar a API neste caso, o gh
    # falso devolve erro e o teste reprova — SKIP não precisa de rede.
    proc = rodar_portao(tmp_path, {"respostas": {}}, CELULAS="[]")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "SKIP" in proc.stdout
    assert "nenhuma célula" in proc.stdout


def test_ci_celula_pulado_com_celula_tocada_e_error(tmp_path):
    cen = cenario_verde()
    cen["respostas"]["runs/11/jobs"] = jobs_(
        ("detectar", "success"),
        ("ci-celula", "skipped"),
        ("ci-celula-gate", "success"),
    )
    proc = rodar_portao(tmp_path, cen)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "instrumentação quebrada" in proc.stdout


def test_workflow_exigido_ausente_e_error_apos_graca(tmp_path):
    cen = cenario_verde()
    cen["respostas"][f"runs?head_sha={SHA_MERGE}"]["workflow_runs"] = [
        run_(12, ALARME)  # ci-celula sumiu (deletado/desabilitado)
    ]
    proc = rodar_portao(tmp_path, cen)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "ci-celula" in proc.stdout


def test_checks_pendentes_apos_timeout_e_error(tmp_path):
    cen = cenario_verde()
    cen["respostas"][f"runs?head_sha={SHA_MERGE}"]["workflow_runs"][1] = run_(
        11, CI_CELULA, status="in_progress", conclusao=None
    )
    proc = rodar_portao(tmp_path, cen)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "re-run" in proc.stdout


def test_gh_fora_do_ar_5x_e_error(tmp_path):
    proc = rodar_portao(tmp_path, {"respostas": {}}, PORTAO_TIMEOUT="30")
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "5 vezes seguidas" in proc.stdout


def test_resposta_nao_json_e_error(tmp_path):
    cen = {"respostas": {f"runs?head_sha={SHA_MERGE}": {"__cru__": "<html>quebrou"}}}
    proc = rodar_portao(tmp_path, cen, PORTAO_TIMEOUT="30")
    assert proc.returncode == 2, proc.stdout + proc.stderr


def test_job_exigido_cancelled_e_error(tmp_path):
    cen = cenario_verde()
    cen["respostas"]["runs/11/jobs"] = jobs_(
        ("ci-celula", "success"), ("ci-celula-gate", "cancelled")
    )
    proc = rodar_portao(tmp_path, cen)
    assert proc.returncode == 2, proc.stdout + proc.stderr


def test_run_cancelled_e_error_nao_fail(tmp_path):
    cen = cenario_verde()
    cen["respostas"][f"runs?head_sha={SHA_MERGE}"]["workflow_runs"][1][
        "conclusion"
    ] = "cancelled"
    proc = rodar_portao(tmp_path, cen)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "não é uma medição" in proc.stdout


def test_job_de_matriz_conta_pelo_nome_com_sufixo(tmp_path):
    """`ci-celula (admin)` É o job `ci-celula` — com a matriz da Onda 5.

    O portão procurava o nome EXATO e ficou cego no primeiro deploy depois de o
    escopo passar a ser derivado do diff: disse ERROR e não publicou (o certo),
    mas o motivo era o nome do job, não a evidência. `armadilhas/160`.
    """
    cen = cenario_verde()
    cen["respostas"]["runs/11/jobs"] = jobs_(
        ("ci-celula (admin)", "success"),
        ("ci-celula (quiz)", "success"),
        ("ci-celula-gate", "success"),
    )
    proc = rodar_portao(tmp_path, cen)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_uma_celula_verde_nao_fala_pelas_outras(tmp_path):
    """Com matriz, TODAS as instâncias precisam ter passado.

    Se o portão aceitasse a primeira `success` e parasse, um deploy sairia com
    uma célula reprovada — e o `--fail-fast: false` do CI existe justamente para
    a segunda ser medida.
    """
    cen = cenario_verde()
    cen["respostas"]["runs/11/jobs"] = jobs_(
        ("ci-celula (admin)", "success"),
        ("ci-celula (quiz)", "failure"),
        ("ci-celula-gate", "success"),
    )
    proc = rodar_portao(tmp_path, cen)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "quiz" in proc.stdout


def test_job_exigido_ausente_e_error_com_lista_dos_vistos(tmp_path):
    cen = cenario_verde()
    cen["respostas"]["runs/11/jobs"] = jobs_(("outro-nome", "success"))
    proc = rodar_portao(tmp_path, cen)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "outro-nome" in proc.stdout


def test_push_direto_na_main_sem_pr_e_error(tmp_path):
    cen = cenario_verde()
    cen["respostas"][f"commits/{SHA_MERGE}/pulls"] = []
    proc = rodar_portao(tmp_path, cen)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "push direto" in proc.stdout


def test_pr_de_origem_ambiguo_e_error(tmp_path):
    cen = cenario_verde()
    cen["respostas"][f"commits/{SHA_MERGE}/pulls"] = [
        {"number": 7, "merge_commit_sha": "c" * 40, "head": {"sha": SHA_PR}},
        {"number": 8, "merge_commit_sha": "d" * 40, "head": {"sha": "e" * 40}},
    ]
    proc = rodar_portao(tmp_path, cen)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "ambíguo" in proc.stdout


def test_dois_prs_mas_um_exato_passa(tmp_path):
    cen = cenario_verde()
    cen["respostas"][f"commits/{SHA_MERGE}/pulls"] = [
        {"number": 6, "merge_commit_sha": "c" * 40, "head": {"sha": "e" * 40}},
        {"number": 7, "merge_commit_sha": SHA_MERGE, "head": {"sha": SHA_PR}},
    ]
    proc = rodar_portao(tmp_path, cen)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_muralhas_vermelha_no_pr_mergeado_pelo_botao_reprova(tmp_path):
    cen = cenario_verde()
    cen["respostas"][f"runs?head_sha={SHA_PR}"]["workflow_runs"][0][
        "conclusion"
    ] = "failure"
    proc = rodar_portao(tmp_path, cen)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "muralhas" in proc.stdout


def test_check_homonimo_de_outro_workflow_nao_engana(tmp_path):
    # Um workflow impostor verde com jobs de nomes idênticos NÃO salva o
    # ci-celula verdadeiro vermelho: o chaveamento é por PATH (F2).
    cen = cenario_verde()
    cen["respostas"][f"runs?head_sha={SHA_MERGE}"]["workflow_runs"] += [
        run_(31, ".github/workflows/impostor.yml")
    ]
    cen["respostas"]["runs/31/jobs"] = jobs_(
        ("ci-celula", "success"), ("ci-celula-gate", "success")
    )
    cen["respostas"][f"runs?head_sha={SHA_MERGE}"]["workflow_runs"][1][
        "conclusion"
    ] = "failure"
    proc = rodar_portao(tmp_path, cen)
    assert proc.returncode == 1, proc.stdout + proc.stderr


def test_workflow_novo_e_vermelho_no_mesmo_sha_barra(tmp_path):
    cen = cenario_verde()
    cen["respostas"][f"runs?head_sha={SHA_MERGE}"]["workflow_runs"] += [
        run_(41, ".github/workflows/novo.yml", conclusao="failure")
    ]
    proc = rodar_portao(tmp_path, cen)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "vermelhos-nao-previstos" in proc.stdout
    assert "novo.yml" in proc.stdout


def test_o_proprio_run_e_excluido_da_medicao(tmp_path):
    # O ÚNICO run de ci-celula carrega o id do próprio portão: excluído,
    # o workflow exigido fica ausente => ERROR (e não um falso verde/espera).
    cen = cenario_verde()
    cen["respostas"][f"runs?head_sha={SHA_MERGE}"]["workflow_runs"] = [
        run_(int(RUN_ID_SELF), CI_CELULA),
        run_(12, ALARME),
    ]
    proc = rodar_portao(tmp_path, cen)
    assert proc.returncode == 2, proc.stdout + proc.stderr


def test_duas_celulas_num_push_PASSAM_desde_que_ambas_tenham_evidencia(tmp_path):
    """A cerca de largura caiu na Onda 5 — o portão acompanhou.

    Até 29/08/2026 duas células num push reprovavam aqui, porque o CI só
    testava uma. Agora o CI roda a suíte de CADA uma (matriz), e o que o portão
    exige é EVIDÊNCIA VERDE de todas — que é o que ele confere instância por
    instância. Recusar por largura passou a proibir sem medir.
    """
    cen = cenario_verde()
    cen["respostas"]["runs/11/jobs"] = jobs_(
        ("ci-celula (quiz)", "success"),
        ("ci-celula (leads)", "success"),
        ("ci-celula-gate", "success"),
    )
    proc = rodar_portao(tmp_path, cen, CELULAS='["quiz", "leads"]')
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_duas_celulas_com_UMA_sem_evidencia_reprova(tmp_path):
    """O que substituiu a proibição: prova. Faltando prova de uma, reprova."""
    cen = cenario_verde()
    cen["respostas"]["runs/11/jobs"] = jobs_(
        ("ci-celula (quiz)", "success"),
        ("ci-celula (leads)", "failure"),
        ("ci-celula-gate", "success"),
    )
    proc = rodar_portao(tmp_path, cen, CELULAS='["quiz", "leads"]')
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "leads" in proc.stdout


def test_evento_que_nao_e_push_e_error(tmp_path):
    proc = rodar_portao(tmp_path, cenario_verde(), EVENTO="workflow_dispatch")
    assert proc.returncode == 2, proc.stdout + proc.stderr


def test_celulas_com_json_quebrado_e_error(tmp_path):
    proc = rodar_portao(tmp_path, cenario_verde(), CELULAS="nao-e-json")
    assert proc.returncode == 2, proc.stdout + proc.stderr


def test_modo_infra_aceita_rodar_pulado_mas_exige_o_gate(tmp_path):
    cen = cenario_verde()
    cen["respostas"]["runs/11/jobs"] = jobs_(
        ("detectar", "success"),
        ("ci-celula", "skipped"),  # sem célula, o rodar pula LEGITIMAMENTE
        ("ci-celula-gate", "success"),
    )
    proc = rodar_portao(tmp_path, cen, PORTAO_MODO="infra", CELULAS="[]")
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_modo_infra_gate_pulado_e_error(tmp_path):
    cen = cenario_verde()
    cen["respostas"]["runs/11/jobs"] = jobs_(
        ("detectar", "success"),
        ("ci-celula", "skipped"),
        ("ci-celula-gate", "skipped"),
    )
    proc = rodar_portao(tmp_path, cen, PORTAO_MODO="infra", CELULAS="[]")
    assert proc.returncode == 2, proc.stdout + proc.stderr


def test_bug_dentro_do_portao_vira_2_nunca_1():
    import portao_de_deploy as modulo

    def explode():
        raise TypeError("bug nosso, não do código sob deploy")

    assert modulo._blindar("teste", explode)() == 2


# ---------------------------------------------------------------------------
# Forma dos workflows — a mitigação do vetor "remover o job portao no YAML"
# ---------------------------------------------------------------------------


def _carregar(nome: str) -> dict:
    doc = yaml.safe_load(
        (RAIZ / ".github" / "workflows" / nome).read_text(encoding="utf-8")
    )
    # YAML 1.1 lê `on:` como a chave booleana True.
    doc["on"] = doc.get("on", doc.get(True))
    return doc


def test_workflow_de_deploy_exige_o_portao():
    celula = _carregar("deploy-celula.yml")
    assert "workflow_dispatch" not in celula["on"]
    jobs = celula["jobs"]
    assert "portao" in jobs, "o job portao sumiu do deploy-celula"
    assert "ci/portao_de_deploy.py" in json.dumps(jobs["portao"]["steps"])
    assert "PORTAO_GH" not in jobs["portao"].get("env", {}), (
        "PORTAO_GH é costura de teste; no workflow real ela substituiria o gh "
        "verdadeiro — o portão mediria um dublê"
    )
    assert "packages" not in jobs["portao"].get("permissions", {})
    assert set(jobs["deploy"]["needs"]) == {"detectar", "portao"}
    cond = jobs["deploy"]["if"]
    for trecho in (
        "needs.portao.result == 'success'",
        "needs.detectar.result == 'success'",
        "needs.detectar.outputs.deteccao == 'ok'",
        "needs.detectar.outputs.celulas != '[]'",
    ):
        assert trecho in cond, f"condição do deploy perdeu: {trecho}"

    infra = _carregar("deploy-infra.yml")
    assert "workflow_dispatch" not in infra["on"]
    jobs_i = infra["jobs"]
    assert "portao" in jobs_i, "o job portao sumiu do deploy-infra"
    assert jobs_i["portao"]["env"].get("PORTAO_MODO") == "infra"
    assert "PORTAO_GH" not in jobs_i["portao"]["env"]
    needs = jobs_i["sincronizar"]["needs"]
    assert needs == "portao" or "portao" in needs
    assert "needs.portao.result == 'success'" in jobs_i["sincronizar"]["if"]


# ---------------------------------------------------------------------------
# O VIGIA DO CADEADO é ALARME, não portão: vermelho nele não pode travar
# entrega. A declaração dele vive em `conhecidos` (nunca em `exigidos`) e o
# raciocínio está por escrito ao lado da constante em ci/portao_de_deploy.py.
#
# Estes dois testes são um par: o primeiro prova que a isenção EXISTE, o
# segundo prova que ela é ESTREITA. Sozinho, o primeiro passaria também se
# alguém tivesse desligado a regra inteira — que é o modo clássico de uma
# isenção legítima virar buraco.
# ---------------------------------------------------------------------------
def test_vigia_do_cadeado_vermelho_nao_barra_o_deploy():
    # O conserto de um cadeado vermelho É uma publicação (armadilhas/018): se
    # o vigia barrasse deploys, ele trancaria a porta por dentro.
    import portao_de_deploy as pd

    runs = [run_(1, VIGIA, conclusao="failure")]
    conhecidos = {CI_CELULA, ALARME, MURALHAS, pd.VIGIA_DO_CADEADO}
    assert pd.vermelhos_nao_previstos(runs, conhecidos).estado is not pd.Estado.FAIL


def test_workflow_desconhecido_vermelho_continua_barrando_o_deploy():
    import portao_de_deploy as pd

    runs = [run_(1, ".github/workflows/inventado.yml", conclusao="failure")]
    conhecidos = {CI_CELULA, ALARME, MURALHAS, pd.VIGIA_DO_CADEADO}
    resultado = pd.vermelhos_nao_previstos(runs, conhecidos)
    assert resultado.estado is pd.Estado.FAIL
    assert "inventado.yml" in resultado.detalhe


def _linha_dos_conhecidos() -> str:
    """A FIAÇÃO, e não a função: é ela que os outros dois testes não veem.

    Os dois testes acima montam `conhecidos` à mão e provam o COMPORTAMENTO de
    `vermelhos_nao_previstos`. Nenhum dos dois ficaria vermelho se alguém
    apagasse a declaração da fonte — foi medido em 29/08/2026 (armadilhas/180):
    só o teste estrutural pegou. Este lê a linha de verdade.

    Ler a LINHA (e não `"NOME}" in fonte`) porque a lista cresce: em
    30/08/2026 a vacina do deploy entrou nela, e a asserção literal do vigia
    quebrou por ordem de membros — o teste reprovou sem nenhum buraco existir,
    que é como um guarda ensina a gente a ignorá-lo.
    """
    fonte = (RAIZ / "ci" / "portao_de_deploy.py").read_text(encoding="utf-8")
    linhas = [ln for ln in fonte.splitlines() if "conhecidos = set(exigidos)" in ln]
    assert len(linhas) == 1, (
        f"esperava UMA linha montando `conhecidos`, achei {len(linhas)} — a "
        "fiação mudou de forma e este guarda precisa ser refeito, não removido"
    )
    return linhas[0]


def test_o_vigia_esta_em_conhecidos_e_NAO_em_exigidos():
    # Se alguém um dia o promover a exigido, todo deploy passaria a esperar um
    # run que, na maioria dos SHAs, nem existe — o vigia roda no relógio.
    fonte = (RAIZ / "ci" / "portao_de_deploy.py").read_text(encoding="utf-8")
    assert "VIGIA_DO_CADEADO" in _linha_dos_conhecidos()
    assert "VIGIA_DO_CADEADO: (" not in fonte


# ---------------------------------------------------------------------------
# A VACINA DO DEPLOY é o caso mais literal da armadilhas/180 que este
# repositório tem (TAR-029, 30/08/2026): ela acorda por `workflow_run` quando um
# deploy termina `cancelled`, roda NO MESMO `head_sha` do deploy doente, e a
# cura que ela pede é um rerun DAQUELE deploy — que passa por este portão.
#
# Vermelha e fora de `conhecidos`, ela reprovaria o rerun que ela mesma pediu,
# exatamente no caso em que já tinha falhado. O mesmo trio de testes que o vigia
# exige: a isenção existe · a isenção é estreita · a declaração está na fonte.
# ---------------------------------------------------------------------------
VACINA = ".github/workflows/vacina-do-deploy.yml"


def test_vacina_do_deploy_vermelha_nao_barra_o_deploy():
    import portao_de_deploy as pd

    runs = [run_(1, VACINA, conclusao="failure")]
    conhecidos = {CI_CELULA, ALARME, MURALHAS, pd.VACINA_DO_DEPLOY}
    assert pd.vermelhos_nao_previstos(runs, conhecidos).estado is not pd.Estado.FAIL


def test_a_isencao_da_vacina_e_estreita_e_nao_um_buraco():
    """Sozinha, a prova de cima passaria com a regra inteira desligada."""
    import portao_de_deploy as pd

    runs = [
        run_(1, VACINA, conclusao="failure"),
        run_(2, ".github/workflows/inventado.yml", conclusao="failure"),
    ]
    conhecidos = {CI_CELULA, ALARME, MURALHAS, pd.VACINA_DO_DEPLOY}
    resultado = pd.vermelhos_nao_previstos(runs, conhecidos)
    assert resultado.estado is pd.Estado.FAIL
    assert "inventado.yml" in resultado.detalhe
    assert "vacina-do-deploy" not in resultado.detalhe


def test_a_vacina_esta_em_conhecidos_e_NAO_em_exigidos():
    fonte = (RAIZ / "ci" / "portao_de_deploy.py").read_text(encoding="utf-8")
    assert "VACINA_DO_DEPLOY" in _linha_dos_conhecidos(), (
        "sem esta declaração, uma vacina vermelha tranca a porta por dentro "
        "(armadilhas/180) — e só no dia em que ela falhar é que se descobre"
    )
    assert "VACINA_DO_DEPLOY: (" not in fonte, (
        "exigi-la faria TODO deploy esperar por um run que só nasce quando "
        "houve cancelamento — trocaria um bloqueio raro por um bloqueio diário"
    )


# ---------------------------------------------------------------------------
# UMA ESTEIRA DE DEPLOY NÃO TRANCA A OUTRA — TAR-041 (30/08/2026).
#
# `deploy-celula` e `deploy-infra` nascem no MESMO SHA sempre que um PR de
# infraestrutura entra, porque todo PR deste projeto carrega um registro em
# `painel/**`. Fora de `conhecidos`, um soluço de rede em uma REPROVAVA a outra
# — e o merge ficava fora do ar duas vezes em vez de uma, com o mantenedor
# lendo "deploy-infra vermelho" sobre um problema que era de rede na célula.
#
# MEDIDO nos 30 dias até 30/08/2026: `vermelhos_nao_previstos` reprovou 4 vezes,
# e as QUATRO foram esta cascata, nas duas direções. Zero vezes ela pegou o que
# existe para pegar (um check novo fora do portão) — por isso a isenção é
# estreita e o teste do "inventado.yml" continua sendo o par obrigatório.
#
# Medição crua do antes/depois, com estas mesmas histórias:
#
#   deploy-celula vermelho   ANTES=FAIL   DEPOIS=PASS
#   deploy-infra vermelho    ANTES=FAIL   DEPOIS=PASS
#   inventado.yml vermelho   ANTES=FAIL   DEPOIS=FAIL
# ---------------------------------------------------------------------------
DEPLOY_INFRA = ".github/workflows/deploy-infra.yml"


def _conhecidos_de_verdade() -> set:
    """A lista REAL da fonte, não uma cópia — senão o teste prova outra coisa."""
    import portao_de_deploy as pd

    return {CI_CELULA, ALARME, MURALHAS, pd.VIGIA_DO_CADEADO,
            pd.VACINA_DO_DEPLOY, pd.DEPLOY_CELULA, pd.DEPLOY_INFRA}


def _a_irma_vermelha_nao_barra(esteira: str) -> None:
    import portao_de_deploy as pd

    runs = [run_(1, esteira, conclusao="failure")]
    resultado = pd.vermelhos_nao_previstos(runs, _conhecidos_de_verdade())
    assert resultado.estado is not pd.Estado.FAIL, (
        f"um soluço de rede em `{esteira}` não pode trancar a outra esteira: "
        "elas publicam coisas diferentes (imagem de célula × compose/traefik) e "
        "o compose referencia a imagem por tag MÓVEL, então uma imagem atrasada "
        "é o estado normal entre dois deploys"
    )


def test_deploy_celula_vermelho_nao_barra_o_deploy_de_infra():
    """A direção medida no PR #622: o run 33328262912 morreu por isto."""
    _a_irma_vermelha_nao_barra(DEPLOY_CELULA)


def test_deploy_infra_vermelho_nao_barra_o_deploy_de_celula():
    """A direção oposta, medida nos PRs #106 e #502 — a cascata vai nos dois
    sentidos, e cobrir só uma deixaria metade da doença de pé."""
    _a_irma_vermelha_nao_barra(DEPLOY_INFRA)


def test_a_isencao_das_esteiras_e_estreita_e_nao_um_buraco():
    """Sozinha, a prova de cima passaria com a regra inteira desligada.

    É o mesmo par que o vigia e a vacina já exigem — e é o teste que impede
    alguém de "resolver" a cascata apagando `vermelhos_nao_previstos`.
    """
    import portao_de_deploy as pd

    runs = [
        run_(1, DEPLOY_CELULA, conclusao="failure"),
        run_(2, DEPLOY_INFRA, conclusao="failure"),
        run_(3, ".github/workflows/inventado.yml", conclusao="failure"),
    ]
    resultado = pd.vermelhos_nao_previstos(runs, _conhecidos_de_verdade())
    assert resultado.estado is pd.Estado.FAIL
    assert "inventado.yml" in resultado.detalhe
    assert "deploy-celula" not in resultado.detalhe
    assert "deploy-infra" not in resultado.detalhe


def test_as_esteiras_estao_em_conhecidos_e_NAO_em_exigidos():
    """A FIAÇÃO — o que os dois testes de cima não enxergam (armadilhas/180)."""
    fonte = (RAIZ / "ci" / "portao_de_deploy.py").read_text(encoding="utf-8")
    linha = _linha_dos_conhecidos()
    for nome in ("DEPLOY_CELULA", "DEPLOY_INFRA"):
        assert nome in linha, (
            f"sem `{nome}` em `conhecidos`, a esteira irmã vermelha volta a "
            "reprovar este deploy — a cascata medida 4 vezes em 30 dias"
        )
        assert f"{nome}: (" not in fonte, (
            f"exigir `{nome}` faria todo deploy esperar por um run da outra "
            "esteira que, na maioria dos SHAs, nem nasce (26 contra 417 em 30 "
            "dias) — trocaria um bloqueio raro por um bloqueio diário"
        )


# ---------------------------------------------------------------------------
# O ALARME DA MAIN SAIU DE `exigidos` (alavanca 2 das alavancas de 10x da
# fábrica, liberada pelo mantenedor em 05/09/2026). O portão esperava o
# `alarme-main` terminar para publicar, e ele respondia a mesma pergunta que o
# `muralhas` do PR de origem já tinha respondido sobre o MESMO conteúdo: a
# `main` tem política estrita, o PR só mergeia com a base em dia, e o portão
# já exige e confere esse `muralhas`. Medido no deploy-celula de 05/09 20:25:
# o job `portao-de-deploy` levou 1min22s, quase tudo esperando o alarme.
#
# O mesmo trio da armadilhas/180: a isenção existe (ausente, pendente e
# vermelho não seguram o deploy) · a isenção é estreita (o `muralhas` do PR
# de origem CONTINUA exigido) · a declaração está na fonte.
# ---------------------------------------------------------------------------
def test_alarme_main_ausente_nao_segura_o_deploy(tmp_path):
    cen = cenario_verde()
    cen["respostas"][f"runs?head_sha={SHA_MERGE}"]["workflow_runs"] = [
        run_(int(RUN_ID_SELF), DEPLOY_CELULA, status="in_progress", conclusao=None),
        run_(11, CI_CELULA),
    ]
    proc = rodar_portao(tmp_path, cen)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_alarme_main_pendente_nao_segura_o_deploy(tmp_path):
    # Antes da alavanca 2, este cenário era ERROR depois do teto: o portão
    # esperava o alarme terminar. Agora ele não espera por um run que mede o
    # que o `muralhas` do PR de origem já mediu.
    cen = cenario_verde()
    cen["respostas"][f"runs?head_sha={SHA_MERGE}"]["workflow_runs"][2] = run_(
        12, ALARME, status="in_progress", conclusao=None
    )
    proc = rodar_portao(tmp_path, cen)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_alarme_main_vermelho_no_mesmo_sha_nao_e_vermelho_nao_previsto(tmp_path):
    # Quem grita quando o alarme reprova é a issue do próprio alarme, não este
    # portão. Fora de `conhecidos`, o vermelho dele cairia em
    # `vermelhos-nao-previstos` e a isenção não existiria de verdade.
    cen = cenario_verde()
    cen["respostas"][f"runs?head_sha={SHA_MERGE}"]["workflow_runs"][2] = run_(
        12, ALARME, conclusao="failure"
    )
    proc = rodar_portao(tmp_path, cen)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "nenhum workflow vermelho fora da lista" in proc.stdout


def test_o_alarme_esta_em_conhecidos_e_NAO_em_exigidos():
    """A FIAÇÃO, e não a função (armadilhas/180): os testes de cima passam
    contra o gh falso; só este fica vermelho se alguém devolver o alarme a
    `exigidos` ou o tirar de `conhecidos`."""
    fonte = (RAIZ / "ci" / "portao_de_deploy.py").read_text(encoding="utf-8")
    assert "ALARME_MAIN" in _linha_dos_conhecidos(), (
        "sem `ALARME_MAIN` em `conhecidos`, um alarme vermelho no mesmo SHA "
        "volta a reprovar o deploy por `vermelhos-nao-previstos`"
    )
    assert "ALARME_MAIN: (" not in fonte, (
        "exigir o `alarme-main` faz todo deploy esperar 1min18s por uma "
        "medição que o `muralhas` do PR de origem já fez sobre o mesmo conteúdo"
    )
