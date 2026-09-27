import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import mergear
from _nucleo import Estado, ErroDeInstrumentacao, Resultado


VERDE = [
    dict(name="muralhas", status="COMPLETED", conclusion="SUCCESS"),
    dict(name="ci-celula-gate", status="COMPLETED", conclusion="SUCCESS"),
]
VERMELHO = [
    dict(name="muralhas", status="COMPLETED", conclusion="FAILURE"),
    dict(name="ci-celula-gate", status="COMPLETED", conclusion="SUCCESS"),
]


def configurar(monkeypatch, prs, bloqueados=(), rollup=None, abertos=()):
    """`abertos` é o que a consulta da fome devolve sobre TODOS os PRs abertos."""
    chamadas = []
    monkeypatch.setattr(mergear.time, "sleep", lambda segundos: None)

    def gh(args, *a, **k):
        if args[:2] == ["pr", "list"]:
            return json.dumps(prs)
        if args[:2] == ["api", "graphql"]:
            return json.dumps(
                {"data": {"repository": {"pullRequests": {"nodes": list(abertos)}}}}
            )
        return chamadas.append(args) or ""

    monkeypatch.setattr(mergear, "_gh", gh)
    monkeypatch.setattr(
        mergear,
        "carregar_pr",
        lambda raiz, numero: dict(
            number=numero,
            headRefOid="a" * 40,
            mergeable="MERGEABLE",
            mergeStateStatus="BEHIND" if numero in bloqueados else "CLEAN",
            statusCheckRollup=list(VERDE if rollup is None else rollup),
        ),
    )
    monkeypatch.setattr(
        mergear,
        "checar_mandato",
        lambda *a: Resultado("mandato", Estado.PASS, "autorizado"),
    )
    monkeypatch.setattr(mergear, "integrar", lambda n, r: chamadas.append(n) or 0)
    return chamadas


def pr(numero, **campos):
    return dict(
        number=numero,
        isDraft=False,
        isCrossRepository=False,
        createdAt=str(numero),
        **campos
    )


def test_atende_prs_em_ordem_sem_etiqueta_e_sem_repeticao(monkeypatch, tmp_path):
    chamadas = configurar(monkeypatch, [pr(2), pr(1)])
    assert mergear.integrar_abertos(tmp_path) == 0
    assert chamadas == [1, 2]


def test_rascunho_e_fork_nao_integram(monkeypatch, tmp_path):
    itens = [dict(pr(1), isDraft=True), dict(pr(2), isCrossRepository=True), pr(3)]
    chamadas = configurar(monkeypatch, itens)
    assert mergear.integrar_abertos(tmp_path) == 0
    assert chamadas == [3]


def test_atualiza_base_com_sha_e_segue_sem_esperar(monkeypatch, tmp_path):
    chamadas = configurar(monkeypatch, [pr(1), pr(2)], bloqueados=(1,))
    assert mergear.integrar_abertos(tmp_path) == 0
    assert chamadas[0] == [
        "api",
        "--method",
        "PUT",
        "repos/{owner}/{repo}/pulls/1/update-branch",
        "-f",
        "expected_head_sha=" + "a" * 40,
    ]
    assert chamadas[1] == 2


# guarda: ci/mergear.py:1650
def test_sem_mandato_nao_atualiza_nem_mergeia(monkeypatch, tmp_path, capsys):
    chamadas = configurar(monkeypatch, [pr(1)], bloqueados=(1,))
    monkeypatch.setattr(
        mergear,
        "checar_mandato",
        lambda *a: Resultado("mandato", Estado.FAIL, "ausente"),
    )
    assert mergear.integrar_abertos(tmp_path) == 0
    assert chamadas == []
    assert "PR #1 não foi integrado" in capsys.readouterr().out


def test_falha_de_um_pr_nao_prende_o_seguinte(monkeypatch, tmp_path):
    chamadas = configurar(monkeypatch, [pr(1), pr(2)])

    def integrar(numero, raiz):
        chamadas.append(numero)
        if numero == 1:
            raise ErroDeInstrumentacao("consulta falhou")
        return 0

    monkeypatch.setattr(mergear, "integrar", integrar)
    assert mergear.integrar_abertos(tmp_path) == 2
    assert chamadas == [1, 2]


def test_evento_consulta_apenas_o_ramo_que_terminou(monkeypatch, tmp_path):
    consultas = []
    monkeypatch.setattr(
        mergear, "_gh", lambda args, *a, **k: consultas.append(args) or "[]"
    )
    assert mergear.integrar_abertos(tmp_path, ramo="agent/admin/entrega") == 0
    assert consultas[0][-2:] == ["--head", "agent/admin/entrega"]


def test_workflow_nao_descarta_eventos_de_outros_prs():
    import yaml

    fluxo = yaml.safe_load(
        (Path(__file__).resolve().parents[2] / ".github/workflows/pouso.yml").read_text(
            encoding="utf-8"
        )
    )
    grupo = fluxo["concurrency"]["group"]
    assert "pull_request.head.ref" in grupo
    assert "workflow_run.head_branch" in grupo
    passos = fluxo["jobs"]["pousar"]["steps"]
    assert "RAMO_DO_EVENTO" in passos[-1]["env"]


def leitor_que_esfria(monkeypatch, mergeaveis):
    """Simula o GitHub calculando a mergeabilidade depois da primeira consulta.

    `mergeaveis` é a resposta de cada leitura, na ordem; a última se repete.
    Devolve a lista de leituras e a das pausas realmente pedidas.
    """
    leituras, pausas = [], []

    def carregar(raiz, numero):
        leituras.append(numero)
        posicao = min(len(leituras), len(mergeaveis)) - 1
        return dict(
            number=numero,
            headRefOid="a" * 40,
            mergeable=mergeaveis[posicao],
            mergeStateStatus="BEHIND",
            statusCheckRollup=list(VERDE),
        )

    monkeypatch.setattr(mergear, "carregar_pr", carregar)
    monkeypatch.setattr(mergear.time, "sleep", pausas.append)
    return leituras, pausas


def test_reconsulta_quando_o_github_ainda_nao_calculou(monkeypatch, tmp_path):
    chamadas = configurar(monkeypatch, [pr(1)], bloqueados=(1,))
    leituras, pausas = leitor_que_esfria(monkeypatch, ["UNKNOWN", "MERGEABLE"])
    assert mergear.integrar_abertos(tmp_path) == 0
    assert leituras == [1, 1]
    # Sem a espera, as três leituras saem no mesmo segundo e o GitHub devolve
    # UNKNOWN nas três: reler sem pausar é não reler.
    assert pausas == [mergear.PAUSA_ENTRE_AS_LEITURAS]
    assert chamadas[0][3] == "repos/{owner}/{repo}/pulls/1/update-branch"


def test_desiste_de_reconsultar_e_entrega_o_pr_ao_relatorio(
    monkeypatch, tmp_path, capsys
):
    chamadas = configurar(monkeypatch, [pr(1)], bloqueados=(1,))
    leituras, pausas = leitor_que_esfria(monkeypatch, ["UNKNOWN"])
    assert mergear.integrar_abertos(tmp_path) == 0
    assert len(leituras) == mergear.TENTATIVAS_ATE_O_GITHUB_DECIDIR
    assert len(pausas) == mergear.TENTATIVAS_ATE_O_GITHUB_DECIDIR - 1
    assert chamadas == [1]
    assert "LEITURA FRIA" in capsys.readouterr().out


def test_atualizacao_da_base_fica_no_log(monkeypatch, tmp_path, capsys):
    configurar(monkeypatch, [pr(1)], bloqueados=(1,))
    assert mergear.integrar_abertos(tmp_path) == 0
    assert "BASE ATUALIZADA" in capsys.readouterr().out


def test_nao_atualiza_a_base_de_pr_com_check_obrigatorio_vermelho(
    monkeypatch, tmp_path
):
    chamadas = configurar(monkeypatch, [pr(1)], bloqueados=(1,), rollup=VERMELHO)
    assert mergear.integrar_abertos(tmp_path) == 0
    # Nenhum `update-branch`: o PR desce inteiro para o relatório, que mostra
    # o check reprovado. Atualizar a base aqui é CI gasto em laço.
    assert chamadas == [1]


# ---------------------------------------------------------------------------
# A FOME (medida em 27/09/2026): o PR 2229 teve quatro ciclos verdes seguidos
# sem integrar. A cada ciclo de 8 minutos um PR de checks de 2 minutos entrava
# na main antes, e o lento voltava a BEHIND. Os PRs abaixo são o lento (#1) e o
# rápido (#2); `aberto` fala a língua da consulta GraphQL da pista.
# ---------------------------------------------------------------------------

PENDENTE = [
    dict(name="muralhas", status="COMPLETED", conclusion="SUCCESS"),
    dict(name="ci-celula-gate", status="IN_PROGRESS", conclusion=None),
]


def aberto(numero, bases=2, minutos=5, rollup=PENDENTE, **campos):
    """Um PR aberto cuja cauda tem `bases` merges da main, o último há `minutos`."""
    topo = datetime.now(timezone.utc) - timedelta(minutes=minutos)
    cauda = ["Merge branch 'main' into agent/lento"] * bases
    cauda = (["pagamentos: conserto"] + cauda)[-mergear.BASES_NOVAS_ATE_A_PRIORIDADE :]
    commits = [
        dict(messageHeadline=titulo, committedDate=topo.isoformat())
        for titulo in cauda
    ]
    commits[-1]["statusCheckRollup"] = {"contexts": {"nodes": list(rollup)}}
    no = dict(
        number=numero,
        isDraft=False,
        isCrossRepository=False,
        commits={"nodes": [{"commit": c} for c in commits]},
    )
    no.update(campos)
    return no


def test_rapido_espera_enquanto_o_lento_mede_a_base_nova(
    monkeypatch, tmp_path, capsys
):
    # guarda: ci/mergear.py:1690
    chamadas = configurar(monkeypatch, [pr(2)], abertos=[aberto(1)])
    assert mergear.integrar_abertos(tmp_path, ramo="agent/rapido") == 0
    assert chamadas == []
    saida = capsys.readouterr().out
    assert "PRIORIDADE — PR #1 espera os checks da base nova" in saida
    assert "PR #2 aguarda" in saida


def test_lento_recebe_a_base_e_o_rapido_espera(monkeypatch, tmp_path):
    chamadas = configurar(
        monkeypatch, [pr(1), pr(2)], bloqueados=(1,), abertos=[aberto(1)]
    )
    assert mergear.integrar_abertos(tmp_path) == 0
    assert [c[3] for c in chamadas] == ["repos/{owner}/{repo}/pulls/1/update-branch"]


def test_o_proprio_prioritario_integra(monkeypatch, tmp_path):
    chamadas = configurar(monkeypatch, [pr(1)], abertos=[aberto(1)])
    assert mergear.integrar_abertos(tmp_path) == 0
    assert chamadas == [1]


def test_pr_vermelho_segue_ao_relatorio_mesmo_com_prioridade(monkeypatch, tmp_path):
    chamadas = configurar(monkeypatch, [pr(2)], rollup=VERMELHO, abertos=[aberto(1)])
    assert mergear.integrar_abertos(tmp_path) == 0
    assert chamadas == [2]


def _rapido_integra_com(monkeypatch, tmp_path, lento):
    chamadas = configurar(monkeypatch, [pr(2)], abertos=[lento])
    assert mergear.integrar_abertos(tmp_path) == 0
    assert chamadas == [2]


def test_trava_solta_quando_os_checks_do_lento_reprovam(monkeypatch, tmp_path):
    # guarda: ci/mergear.py:1613
    _rapido_integra_com(monkeypatch, tmp_path, aberto(1, rollup=VERMELHO))


def test_trava_solta_quando_os_checks_do_lento_terminam_verdes(monkeypatch, tmp_path):
    # guarda: ci/mergear.py:1613
    _rapido_integra_com(monkeypatch, tmp_path, aberto(1, rollup=VERDE))


def test_trava_solta_quando_o_lento_vira_rascunho(monkeypatch, tmp_path):
    # guarda: ci/mergear.py:1595
    _rapido_integra_com(monkeypatch, tmp_path, aberto(1, isDraft=True))


def test_trava_ignora_pr_de_fork(monkeypatch, tmp_path):
    # guarda: ci/mergear.py:1595
    _rapido_integra_com(monkeypatch, tmp_path, aberto(1, isCrossRepository=True))


def test_trava_solta_depois_do_teto_de_tempo(monkeypatch, tmp_path):
    # guarda: ci/mergear.py:1603
    passou_do_teto = mergear.TETO_DA_PRIORIDADE // timedelta(minutes=1) + 1
    _rapido_integra_com(monkeypatch, tmp_path, aberto(1, minutos=passou_do_teto))


def test_uma_base_nova_so_ainda_nao_e_fome(monkeypatch, tmp_path):
    # guarda: ci/mergear.py:1600
    _rapido_integra_com(monkeypatch, tmp_path, aberto(1, bases=1))
