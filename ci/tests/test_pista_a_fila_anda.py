import json
from pathlib import Path

import mergear
from _nucleo import Estado, ErroDeInstrumentacao, Resultado


def configurar(monkeypatch, prs, bloqueados=()):
    chamadas = []
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
