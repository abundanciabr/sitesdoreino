import json
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


def configurar(monkeypatch, prs, bloqueados=(), rollup=None):
    chamadas = []
    monkeypatch.setattr(mergear.time, "sleep", lambda segundos: None)
    monkeypatch.setattr(
        mergear,
        "_gh",
        lambda args, *a, **k: (
            json.dumps(prs)
            if args[:2] == ["pr", "list"]
            else chamadas.append(args) or ""
        ),
    )
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


def test_sem_mandato_nao_atualiza_nem_mergeia(monkeypatch, tmp_path):
    chamadas = configurar(monkeypatch, [pr(1)], bloqueados=(1,))
    monkeypatch.setattr(
        mergear,
        "checar_mandato",
        lambda *a: Resultado("mandato", Estado.FAIL, "ausente"),
    )
    assert mergear.integrar_abertos(tmp_path) == 0
    assert chamadas == []


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
