"""TESTAR O TESTADOR — o merge guardado.

[INV-CI01] Este portão é o único que fica entre um PR vermelho e a `main`,
porque o GitHub não oferece required checks em repositório privado de conta
pessoal. Se ele errar para o lado do verde, não há segunda barreira.

Todos os testes aqui são offline: alimentam as funções com a resposta que o
`gh` devolveria, e conferem o veredito. O que se valida é a SEMÂNTICA, não o
formato das mensagens.

O caso que mais importa é `test_sem_checks_e_error`: um PR sem check algum é
indistinguível de um PR cujos workflows nem dispararam. Ler isso como "não vi
nada errado, então pode" é o falso positivo original em outra roupa.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import mergear
from _nucleo import Estado

RAIZ = Path(__file__).resolve().parents[2]
NL = chr(10)


def _check(nome: str, conclusao: str = "SUCCESS", status: str = "COMPLETED") -> dict:
    return {
        "__typename": "CheckRun",
        "name": nome,
        "status": status,
        "conclusion": conclusao,
    }


def _pr(**alteracoes: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "number": 99,
        "title": "um PR de mentira",
        "state": "OPEN",
        "isDraft": False,
        "mergeable": "MERGEABLE",
        "mergeStateStatus": "CLEAN",
        "baseRefName": "main",
        "headRefName": "agent/falso",
        "url": "https://example.invalid/pr/99",
        "author": {"login": "ninguem"},
        "labels": [],
        "files": [{"path": "ci/algo.py"}],
        "commits": [{"oid": "abc"}],
        "statusCheckRollup": [
            _check("muralhas"),
            _check("ci-celula-gate"),
            _check("detectar"),
        ],
    }
    base.update(alteracoes)
    return base


def _pior(resultados) -> Estado:
    return max((r.estado for r in resultados), key=lambda e: e.gravidade)


# ---------------------------------------------------------------------------
# Checks — o coração do portão
# ---------------------------------------------------------------------------


def test_tudo_verde_passa() -> None:
    assert _pior(mergear.checar_checks(_pr())) is Estado.PASS


def test_sem_checks_e_error() -> None:
    """Nenhum check reportado NÃO é sinal verde.

    Um PR sem check é indistinguível de um PR cujos workflows não chegaram a
    rodar. Aprovar isso seria mergear sem que nada tenha sido medido.
    """
    resultados = mergear.checar_checks(_pr(statusCheckRollup=[]))
    assert _pior(resultados) is Estado.ERROR


def test_check_vermelho_reprova() -> None:
    pr = _pr(
        statusCheckRollup=[
            _check("muralhas", "FAILURE"),
            _check("ci-celula-gate"),
        ]
    )
    assert _pior(mergear.checar_checks(pr)) is Estado.FAIL


@pytest.mark.parametrize(
    "conclusao", ["FAILURE", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED", "STALE", ""]
)
def test_qualquer_conclusao_que_nao_seja_sucesso_reprova(conclusao: str) -> None:
    pr = _pr(
        statusCheckRollup=[_check("muralhas", conclusao), _check("ci-celula-gate")]
    )
    assert _pior(mergear.checar_checks(pr)) is not Estado.PASS


def test_check_ainda_rodando_e_error() -> None:
    """Mergear com check em andamento é aprovar antes da medição terminar."""
    pr = _pr(
        statusCheckRollup=[
            _check("muralhas", "", "IN_PROGRESS"),
            _check("ci-celula-gate"),
        ]
    )
    assert _pior(mergear.checar_checks(pr)) is Estado.ERROR


def test_status_context_pendente_e_error() -> None:
    """StatusContext (API legada) não tem `status`; PENDING marca em andamento.

    Sem o `state` mapeado para "ainda rodando", um check nesse formato caía no
    `else: FAIL` — reportando "não passou" para um check que só não tinha
    terminado ainda.
    """
    pr = _pr(
        statusCheckRollup=[
            {"context": "servico-externo", "state": "PENDING"},
            _check("muralhas"),
            _check("ci-celula-gate"),
        ]
    )
    assert _pior(mergear.checar_checks(pr)) is Estado.ERROR


def test_skip_declarado_e_permitido() -> None:
    pr = _pr(
        statusCheckRollup=[
            _check("muralhas"),
            _check("ci-celula-gate"),
            _check("ci-celula", "SKIPPED"),
        ]
    )
    assert _pior(mergear.checar_checks(pr)) is Estado.PASS


def test_skip_nao_declarado_reprova() -> None:
    """Pulo sem declaração é pulo inferido — o buraco que o INV-CI01 fecha."""
    pr = _pr(
        statusCheckRollup=[
            _check("muralhas"),
            _check("ci-celula-gate"),
            _check("algum-check-novo", "SKIPPED"),
        ]
    )
    assert _pior(mergear.checar_checks(pr)) is Estado.FAIL


@pytest.mark.parametrize("ausente", list(mergear.CHECKS_OBRIGATORIOS))
def test_check_obrigatorio_ausente_e_error(ausente: str) -> None:
    """Workflow renomeado, desabilitado ou que não disparou não é aprovação."""
    rollup = [_check(n) for n in mergear.CHECKS_OBRIGATORIOS if n != ausente]
    assert _pior(mergear.checar_checks(_pr(statusCheckRollup=rollup))) is Estado.ERROR


# ---------------------------------------------------------------------------
# Estado do PR e mergeabilidade
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("estado", ["MERGED", "CLOSED"])
def test_pr_que_nao_esta_aberto_reprova(estado: str) -> None:
    assert mergear.checar_estado(_pr(state=estado)).estado is Estado.FAIL


def test_rascunho_reprova() -> None:
    assert mergear.checar_estado(_pr(isDraft=True)).estado is Estado.FAIL


def test_conflito_reprova() -> None:
    assert (
        mergear.checar_mergeabilidade(_pr(mergeable="CONFLICTING")).estado
        is Estado.FAIL
    )


def test_base_velha_reprova_em_vez_de_dizer_verde() -> None:
    """BEHIND é recusa do GitHub, não detalhe — o portão não pode dizer PASS.

    Medido no PR #414: o portão dizia `PASS sem conflitos (BEHIND)` e o
    `gh pr merge` seguinte falhava com "the head branch is not up to date".
    A trava estrita entrou em 28/08 (Onda 0) e o portão não sabia dela.
    Verde na tela e recusa na hora de agir é o pior par possível.
    """
    resultado = mergear.checar_mergeabilidade(_pr(mergeStateStatus="BEHIND"))
    assert resultado.estado is Estado.FAIL
    assert "update-branch" in resultado.detalhe


def test_base_velha_avisa_do_painel_gerado() -> None:
    """Quem atualiza precisa saber que o gerado do painel fica para trás.

    Também medido no PR #414: o `update-branch` mistura a main sem regerar, e o
    check do painel reprova por artefato velho. Custou uma rodada inteira.
    """
    detalhe = mergear.checar_mergeabilidade(_pr(mergeStateStatus="BEHIND")).detalhe
    assert "gerar_manifesto" in detalhe


@pytest.mark.parametrize("status", ["CLEAN", "UNSTABLE", "BLOCKED"])
def test_base_em_dia_continua_passando(status: str) -> None:
    """A recusa é SÓ do BEHIND — não pode virar um portão que trava tudo."""
    assert (
        mergear.checar_mergeabilidade(_pr(mergeStateStatus=status)).estado
        is Estado.PASS
    )


def test_mergeabilidade_desconhecida_e_error() -> None:
    """O GitHub calcula isso de forma assíncrona; 'não sei' não é 'pode'."""
    assert (
        mergear.checar_mergeabilidade(_pr(mergeable="UNKNOWN")).estado is Estado.ERROR
    )


# ---------------------------------------------------------------------------
# Labels — as mesmas regras das muralhas, conferidas antes do clique
# ---------------------------------------------------------------------------


def test_orcamento_estourado_sem_label_reprova() -> None:
    arquivos = [{"path": f"ci/f{i}.py"} for i in range(mergear.LIMITE_DE_ARQUIVOS + 1)]
    assert _pior(mergear.checar_labels(_pr(files=arquivos))) is Estado.FAIL


def test_orcamento_estourado_com_label_passa() -> None:
    arquivos = [{"path": f"ci/f{i}.py"} for i in range(mergear.LIMITE_DE_ARQUIVOS + 1)]
    pr = _pr(files=arquivos, labels=[{"name": "arquitetural"}])
    assert _pior(mergear.checar_labels(pr)) is Estado.PASS


def test_contrato_sem_label_reprova() -> None:
    pr = _pr(files=[{"path": "contracts/catalogo.openapi.yaml"}])
    assert _pior(mergear.checar_labels(pr)) is Estado.FAIL


def test_contrato_com_label_passa() -> None:
    pr = _pr(
        files=[{"path": "contracts/catalogo.openapi.yaml"}],
        labels=[{"name": "contrato"}],
    )
    assert _pior(mergear.checar_labels(pr)) is Estado.PASS


# ---------------------------------------------------------------------------
# Lane 'traducoes' — a mesma válvula que as muralhas abrem (PLANO-I18N.md, D9)
#
# Sem estes testes o modo de falha é mecânico e já estava previsto
# (docs/historico/RESOLVIDAS.md §5.11): um lote de tradução legítimo passa nas muralhas e é
# recusado NA CATRACA, porque as duas cópias da regra divergiram.
# ---------------------------------------------------------------------------


def _traducoes(quantidade: int, celula: str = "meshcraft") -> list[dict[str, str]]:
    return [
        {"path": f"services/{celula}/traducoes/en/pagina{i}.json"}
        for i in range(quantidade)
    ]


def test_lane_traducoes_aceita_lote_grande_de_traducao() -> None:
    """>15 arquivos, todos dados de tradução, label 'traducoes': passa."""
    pr = _pr(
        files=_traducoes(mergear.LIMITE_DE_ARQUIVOS + 10),
        labels=[{"name": "traducoes"}],
    )
    assert _pior(mergear.checar_labels(pr)) is Estado.PASS


def test_lane_traducoes_reprova_arquivo_fora_e_o_nomeia() -> None:
    """Um arquivo fora da árvore de traduções fecha a lane inteira — e a
    mensagem NOMEIA o intruso: "algo está fora" manda procurar entre dezenas."""
    arquivos = _traducoes(mergear.LIMITE_DE_ARQUIVOS + 10)
    arquivos.insert(7, {"path": "services/meshcraft/views.py"})
    resultados = mergear.checar_labels(
        _pr(files=arquivos, labels=[{"name": "traducoes"}])
    )
    assert _pior(resultados) is Estado.FAIL
    reprovado = [r for r in resultados if r.estado is Estado.FAIL]
    assert any("services/meshcraft/views.py" in r.resumo for r in reprovado)


@pytest.mark.parametrize(
    "caminho",
    [
        "services/traducoes/pt.json",  # sem célula no meio
        "services/meshcraft/traducoes",  # a própria pasta, sem arquivo dentro
        "services/meshcraft/traducoes/",  # idem, com barra
        "docs/traducoes/pt.json",  # fora de services/
        "services/meshcraft/a/traducoes/pt.json",  # traducoes aninhada
        "outro/services/meshcraft/traducoes/pt.json",  # prefixo colado
    ],
)
def test_lane_traducoes_nao_cobre_caminho_parecido(caminho: str) -> None:
    """A lane cobre services/<celula>/traducoes/<algo> — nada que só se pareça."""
    arquivos = _traducoes(mergear.LIMITE_DE_ARQUIVOS) + [{"path": caminho}]
    pr = _pr(files=arquivos, labels=[{"name": "traducoes"}])
    assert _pior(mergear.checar_labels(pr)) is Estado.FAIL


def test_lane_traducoes_nao_aperta_dentro_do_teto() -> None:
    """Label NUNCA aperta o portão: ≤15 arquivos passa com ou sem 'traducoes',
    estejam eles na árvore de traduções ou não (mesma regra do .sh, onde o
    bloco da lane nem chega a rodar com N ≤ 15)."""
    arquivos = [{"path": f"ci/f{i}.py"} for i in range(mergear.LIMITE_DE_ARQUIVOS)]
    assert _pior(mergear.checar_labels(_pr(files=arquivos))) is Estado.PASS
    pr_com_label = _pr(files=arquivos, labels=[{"name": "traducoes"}])
    assert _pior(mergear.checar_labels(pr_com_label)) is Estado.PASS


def test_arquitetural_passa_na_frente_da_lane() -> None:
    """As duas labels juntas: 'arquitetural' continua valendo como sempre valeu
    — inclusive para arquivos que a lane jamais aceitaria."""
    arquivos = [{"path": f"ci/f{i}.py"} for i in range(mergear.LIMITE_DE_ARQUIVOS + 1)]
    pr = _pr(
        files=arquivos,
        labels=[{"name": "arquitetural"}, {"name": "traducoes"}],
    )
    assert _pior(mergear.checar_labels(pr)) is Estado.PASS


def test_lote_grande_de_traducao_sem_label_reprova() -> None:
    """A lane é uma DECLARAÇÃO por label, não uma inferência pelo caminho."""
    pr = _pr(files=_traducoes(mergear.LIMITE_DE_ARQUIVOS + 10))
    assert _pior(mergear.checar_labels(pr)) is Estado.FAIL


def test_padrao_da_lane_bate_com_orcamento_de_mudanca() -> None:
    """Como o LIMITE_DE_ARQUIVOS: o padrão de caminho da lane é cópia solta do
    que as muralhas aplicam. Duas fontes para a mesma regra só ficam honestas
    se algo mecânico denuncia a divergência — foi a divergência entre portão e
    catraca que abriu a docs/historico/RESOLVIDAS.md §5.11."""
    import re

    script = (mergear.raiz_do_repo() / "ci" / "orcamento-de-mudanca.sh").read_text(
        encoding="utf-8"
    )
    match = re.search(r'"\$CAMINHO"\s*=~\s*(\S+)\s*\]\]', script)
    assert match, (
        "não encontrei o padrão da lane em ci/orcamento-de-mudanca.sh — "
        "script mudou de formato?"
    )
    assert mergear.PADRAO_DA_LANE_TRADUCOES.pattern == match.group(1)


def test_lane_depende_do_modo_conferido_pelas_muralhas() -> None:
    """A catraca confere só o CAMINHO; o MODO (executável/symlink/submódulo)
    fica com as muralhas, porque `gh pr view --json files` não devolve modo
    (ver a decisão comentada em checar_labels). Esta assimetria só é segura
    enquanto o .sh continuar medindo modo — se ele parar, este teste acusa
    antes de a lane virar porta aberta."""
    script = (mergear.raiz_do_repo() / "ci" / "orcamento-de-mudanca.sh").read_text(
        encoding="utf-8"
    )
    assert "git diff --raw --no-renames" in script
    for modo_proibido in ("100755", "120000", "160000"):
        assert modo_proibido in script
    assert "muralhas" in mergear.CHECKS_OBRIGATORIOS


# ---------------------------------------------------------------------------
# Fronteira
# ---------------------------------------------------------------------------


def test_excecao_inesperada_vira_error() -> None:
    def estoura() -> int:
        raise RuntimeError("bug dentro do próprio portão")

    assert mergear._blindar("mergear", estoura)() == 2


def test_limite_de_arquivos_bate_com_orcamento_de_mudanca() -> None:
    """LIMITE_DE_ARQUIVOS é uma cópia solta do limite em orcamento-de-mudanca.sh.

    Duas fontes independentes para o mesmo número só ficam honestas se algo
    mecânico denuncia quando elas divergirem — do contrário é exatamente o
    tipo de deriva silenciosa que o INV-CI01 existe para eliminar.
    """
    import re

    script = (mergear.raiz_do_repo() / "ci" / "orcamento-de-mudanca.sh").read_text(
        encoding="utf-8"
    )
    match = re.search(r"\(\(\s*N\s*>\s*(\d+)\s*\)\)", script)
    assert (
        match
    ), "não encontrei o limite em ci/orcamento-de-mudanca.sh — script mudou de formato?"
    assert mergear.LIMITE_DE_ARQUIVOS == int(match.group(1))


def test_skips_permitidos_tem_motivo_escrito() -> None:
    """SKIP sem motivo declarado é SKIP inferido, e SKIP inferido é proibido."""
    assert mergear.SKIPS_PERMITIDOS
    for nome, motivo in mergear.SKIPS_PERMITIDOS.items():
        assert motivo.strip(), f"'{nome}' está na lista de skips sem justificativa"


# ---------------------------------------------------------------------------
# O merge em si (desde 22/08/2026 é o agente quem o executa — Lei 4)
# ---------------------------------------------------------------------------


def test_comando_de_merge_nao_usa_yes() -> None:
    """H6: o `gh` 2.97.0 não tem `--yes` em `pr merge` — o portão conferia tudo
    verde e quebrava exatamente na hora de agir. Se a flag voltar, este teste
    acusa antes de o próximo merge real quebrar (docs/historico/RESOLVIDAS.md §5.9.1).
    """
    for metodo in ("merge", "squash", "rebase"):
        cmd = mergear.comando_de_merge(99, metodo)
        assert "--yes" not in cmd
        assert "-y" not in cmd
        assert f"--{metodo}" in cmd
        assert "99" in cmd


def _relatorio_verde() -> "mergear.Relatorio":
    relatorio = mergear.Relatorio("teste")
    relatorio.registrar(mergear.Resultado("tudo", Estado.PASS, "verde"))
    return relatorio


def _relatorio_vermelho() -> "mergear.Relatorio":
    relatorio = mergear.Relatorio("teste")
    relatorio.registrar(mergear.Resultado("tudo", Estado.FAIL, "vermelho"))
    return relatorio


def _gh_de_mentira(
    chamadas: list, estado_apos_merge: str = "MERGED", remessas: list | None = None
):
    import json as _json

    def falso(argumentos, raiz, descricao, **kwargs):
        chamadas.append(list(argumentos))
        if argumentos and argumentos[0] == "api":
            return _json.dumps(remessas or [])
        if argumentos[:2] == ["pr", "view"]:
            return _json.dumps(
                {
                    "state": estado_apos_merge,
                    "mergedBy": {"login": "robo"},
                    "mergeCommit": {"oid": "a" * 40},
                }
            )
        return ""

    return falso


def test_confirmo_errado_recusa_sem_chamar_o_gh(monkeypatch) -> None:
    """A defesa de identidade sobrevive no caminho não-interativo: --confirmo
    com número diferente do PR conferido cancela ANTES de qualquer merge —
    o erro que já aconteceu (PR #21 no lugar do #20) era de identidade."""
    chamadas: list = []
    monkeypatch.setattr(mergear, "conferir", lambda n: (_relatorio_verde(), _pr()))
    monkeypatch.setattr(mergear, "_gh", _gh_de_mentira(chamadas))
    assert mergear.main(["99", "--confirmo", "98"]) == 1
    assert chamadas == []


def test_confirmo_certo_mergeia_e_confere_o_estado(monkeypatch) -> None:
    """O caminho DA PISTA: --confirmo com o número certo mergeia E confere no
    GitHub que o PR virou MERGED — o veredito nunca é o exit do disparo.

    Desde 29/08/2026 este caminho é da pista, não do agente: por isso a
    variável de identificação entra aqui. Sem ela o portão recusa (teste
    abaixo), e é essa recusa que faz o agente ir pedir pouso.
    """
    chamadas: list = []
    monkeypatch.setenv(mergear.VARIAVEL_DA_PISTA, "sim")
    monkeypatch.setattr(mergear, "conferir", lambda n: (_relatorio_verde(), _pr()))
    monkeypatch.setattr(mergear, "_gh", _gh_de_mentira(chamadas))
    assert mergear.main(["99", "--confirmo", "99"]) == 0
    assert ["pr", "merge", "99", "--merge"] in chamadas
    assert any(c[:2] == ["pr", "view"] for c in chamadas)


def test_merge_que_nao_vira_merged_reprova(monkeypatch) -> None:
    """Se o gh não recusar mas o PR não constar como MERGED, o resultado é
    FAIL — 'o comando não reclamou' não é evidência de merge (Lei 6)."""
    chamadas: list = []
    monkeypatch.setenv(mergear.VARIAVEL_DA_PISTA, "sim")
    monkeypatch.setattr(mergear, "conferir", lambda n: (_relatorio_verde(), _pr()))
    monkeypatch.setattr(mergear, "_gh", _gh_de_mentira(chamadas, "OPEN"))
    assert mergear.main(["99", "--confirmo", "99"]) == 1


# ---------------------------------------------------------------------------
# O MERGE SAIU DA MÃO DO ROBÔ — Onda 4, fatia 3 (decisão do mantenedor,
# registro 20260829-006). O agente pede pouso; quem mergeia é a pista.
#
# O que estes testes guardam não é "o robô não merge": é que a recusa
# ENSINA. Uma recusa que só diga "não" faria a próxima sessão procurar um
# contorno — e contorno existe, porque isto é disciplina, não muralha.
# ---------------------------------------------------------------------------


def test_o_agente_nao_mergeia_mais_e_a_recusa_ensina_o_caminho(monkeypatch, capsys):
    chamadas: list = []
    monkeypatch.delenv(mergear.VARIAVEL_DA_PISTA, raising=False)
    monkeypatch.setattr(mergear, "conferir", lambda n: (_relatorio_verde(), _pr()))
    monkeypatch.setattr(mergear, "_gh", _gh_de_mentira(chamadas))
    assert mergear.main(["99", "--confirmo", "99"]) == 1
    assert chamadas == [], "com tudo verde, o robô AINDA assim não pode mergear"
    saida = capsys.readouterr().out
    assert "--pousar" in saida, "a recusa precisa dizer o que fazer em seguida"
    assert "20260829-006" in saida, "e de onde veio a decisão"


def test_pousar_poe_a_etiqueta_e_nao_mergeia(monkeypatch, capsys):
    chamadas: list = []
    monkeypatch.delenv(mergear.VARIAVEL_DA_PISTA, raising=False)
    monkeypatch.setattr(mergear, "conferir", lambda n: (_relatorio_verde(), _pr()))
    monkeypatch.setattr(mergear, "_gh", _gh_de_mentira(chamadas))
    monkeypatch.setattr(mergear, "raiz_do_repo", lambda: RAIZ)
    assert mergear.main(["99", "--pousar"]) == 0
    assert ["pr", "edit", "99", "--add-label", "pousar"] in chamadas
    assert not any(c[:2] == ["pr", "merge"] for c in chamadas)
    assert "não precisa esperar" in capsys.readouterr().out.lower()


def test_pousar_so_acontece_com_o_portao_verde(monkeypatch):
    """Pedir pouso de um PR reprovado entupiria a fila com trabalho quebrado."""
    chamadas: list = []
    monkeypatch.delenv(mergear.VARIAVEL_DA_PISTA, raising=False)
    monkeypatch.setattr(
        mergear, "conferir", lambda n: (_relatorio_vermelho(), _pr())
    )
    monkeypatch.setattr(mergear, "_gh", _gh_de_mentira(chamadas))
    assert mergear.main(["99", "--pousar"]) == 1
    assert chamadas == []


def test_so_a_pista_declara_a_variavel_de_identificacao():
    """A identificação existe num lugar só: o workflow da pista.

    Se ela aparecer em outro workflow, a recusa vira decoração — e o motivo de
    a Lei 4 ter mudado (o agente perdendo a corrida contra o relógio dos
    checks) volta em silêncio.
    """
    import yaml

    fluxos = sorted((RAIZ / ".github" / "workflows").glob("*.yml"))
    com_a_variavel = [
        f.name
        for f in fluxos
        if mergear.VARIAVEL_DA_PISTA in f.read_text(encoding="utf-8")
    ]
    assert com_a_variavel == ["pouso.yml"], (
        "a identificação da pista tem de existir só no pouso.yml; encontrada em: "
        + ", ".join(com_a_variavel)
    )


def test_a_pista_continua_usando_o_MESMO_portao():
    """A pista não pode ser mais permissiva que a catraca do agente."""
    texto = (RAIZ / ".github" / "workflows" / "pouso.yml").read_text(encoding="utf-8")
    assert "ci/mergear.py" in texto and "--confirmo" in texto


# ---------------------------------------------------------------------------
# Execução repetida do MESMO check no MESMO commit (medido em 25/08/2026)
#
# O `muralhas.yml` dispara em `labeled`. Aplicar a label `arquitetural` para
# abrir a válvula do orçamento roda o workflow de novo no mesmo SHA — e o
# GitHub mantém as DUAS execuções penduradas nele. O portão emitia um veredito
# por entrada e reprovava para sempre, com o check verde na cara do GitHub.
# ---------------------------------------------------------------------------
def _check_datado(nome, conclusao, inicio, status="COMPLETED"):
    return {
        "__typename": "CheckRun",
        "name": nome,
        "status": status,
        "conclusion": conclusao,
        "startedAt": inicio,
    }


def test_rerun_verde_depois_de_vermelho_no_mesmo_sha_passa() -> None:
    """O caso real do PR #187: label aplicada, workflow re-rodou, ficou verde."""
    pr = _pr(
        statusCheckRollup=[
            _check_datado("muralhas", "FAILURE", "2026-08-25T19:35:07Z"),
            _check_datado("detectar", "SUCCESS", "2026-08-25T19:35:08Z"),
            _check_datado("muralhas", "SUCCESS", "2026-08-25T19:39:33Z"),
            _check_datado("ci-celula-gate", "SUCCESS", "2026-08-25T19:36:04Z"),
        ]
    )
    resultados = mergear.checar_checks(pr)
    assert _pior(resultados) is Estado.PASS
    # E o veredito de `muralhas` aparece UMA vez só — não dois, contraditórios.
    assert [r for r in resultados if r.nome == "check/muralhas"].__len__() == 1


def test_rerun_VERMELHO_depois_de_verde_no_mesmo_sha_reprova() -> None:
    """A direção que importa mais: a mais recente vale mesmo quando é a pior.

    Sem esta asserção, alguém poderia "consertar" o dedup pegando a melhor das
    duas — que passaria o teste de cima e transformaria o portão em decoração.
    """
    pr = _pr(
        statusCheckRollup=[
            _check_datado("muralhas", "SUCCESS", "2026-08-25T19:35:07Z"),
            _check_datado("muralhas", "FAILURE", "2026-08-25T19:39:33Z"),
            _check_datado("detectar", "SUCCESS", "2026-08-25T19:35:08Z"),
            _check_datado("ci-celula-gate", "SUCCESS", "2026-08-25T19:36:04Z"),
        ]
    )
    assert _pior(mergear.checar_checks(pr)) is Estado.FAIL


def test_sem_hora_o_desempate_fica_com_a_PIOR() -> None:
    """[INV-CI01] "não sei qual é a atual" nunca vira "considero a verde"."""
    pr = _pr(
        statusCheckRollup=[
            _check("muralhas", "SUCCESS"),
            _check("muralhas", "FAILURE"),
            _check("detectar"),
            _check("ci-celula-gate"),
        ]
    )
    assert _pior(mergear.checar_checks(pr)) is Estado.FAIL


def test_hora_IGUAL_o_desempate_fica_com_a_PIOR() -> None:
    pr = _pr(
        statusCheckRollup=[
            _check_datado("muralhas", "SUCCESS", "2026-08-25T19:35:07Z"),
            _check_datado("muralhas", "FAILURE", "2026-08-25T19:35:07Z"),
            _check_datado("detectar", "SUCCESS", "2026-08-25T19:35:08Z"),
            _check_datado("ci-celula-gate", "SUCCESS", "2026-08-25T19:36:04Z"),
        ]
    )
    assert _pior(mergear.checar_checks(pr)) is Estado.FAIL


def test_rerun_que_ainda_roda_nao_e_aprovado_pela_execucao_velha() -> None:
    """Re-rodar deixa o check EM ANDAMENTO; o verde velho não vale por ele."""
    pr = _pr(
        statusCheckRollup=[
            _check_datado("muralhas", "SUCCESS", "2026-08-25T19:35:07Z"),
            _check_datado(
                "muralhas", None, "2026-08-25T19:39:33Z", status="IN_PROGRESS"
            ),
            _check_datado("detectar", "SUCCESS", "2026-08-25T19:35:08Z"),
            _check_datado("ci-celula-gate", "SUCCESS", "2026-08-25T19:36:04Z"),
        ]
    )
    assert _pior(mergear.checar_checks(pr)) is Estado.ERROR


def test_check_obrigatorio_duplicado_nao_some_da_lista_de_vistos() -> None:
    """Desduplicar não pode fazer um check obrigatório parecer ausente."""
    pr = _pr(
        statusCheckRollup=[
            _check_datado("muralhas", "FAILURE", "2026-08-25T19:35:07Z"),
            _check_datado("muralhas", "SUCCESS", "2026-08-25T19:39:33Z"),
            _check_datado("detectar", "SUCCESS", "2026-08-25T19:35:08Z"),
            _check_datado("ci-celula-gate", "SUCCESS", "2026-08-25T19:36:04Z"),
        ]
    )
    resultados = mergear.checar_checks(pr)
    assert not [r for r in resultados if r.nome == "checks obrigatórios"]


def test_a_ordem_da_lista_nao_decide_nada_a_hora_decide() -> None:
    """A entrada MAIS NOVA vem PRIMEIRO — quem só guarda "a última vista" erra.

    Este teste nasceu de uma mutação que passou: trocar a comparação de hora por
    `if True` (= fica sempre com a última entrada percorrida) deixava a suíte
    inteira verde, porque todas as fixtures tinham o rerun no fim da lista. O
    `statusCheckRollup` não promete ordem nenhuma, então depender dela seria um
    guarda que funciona por acidente do dado.
    """
    pr = _pr(
        statusCheckRollup=[
            # o rerun VERDE vem primeiro; a execução velha VERMELHA vem depois
            _check_datado("muralhas", "SUCCESS", "2026-08-25T19:39:33Z"),
            _check_datado("muralhas", "FAILURE", "2026-08-25T19:35:07Z"),
            _check_datado("detectar", "SUCCESS", "2026-08-25T19:35:08Z"),
            _check_datado("ci-celula-gate", "SUCCESS", "2026-08-25T19:36:04Z"),
        ]
    )
    assert _pior(mergear.checar_checks(pr)) is Estado.PASS


def test_a_ordem_da_lista_nao_salva_um_vermelho_recente() -> None:
    """O espelho do de cima: velho-verde primeiro, novo-VERMELHO depois na lista
    já é coberto acima; aqui o novo-VERMELHO vem PRIMEIRO e ainda tem de valer."""
    pr = _pr(
        statusCheckRollup=[
            _check_datado("muralhas", "FAILURE", "2026-08-25T19:39:33Z"),
            _check_datado("muralhas", "SUCCESS", "2026-08-25T19:35:07Z"),
            _check_datado("detectar", "SUCCESS", "2026-08-25T19:35:08Z"),
            _check_datado("ci-celula-gate", "SUCCESS", "2026-08-25T19:36:04Z"),
        ]
    )
    assert _pior(mergear.checar_checks(pr)) is Estado.FAIL


def test_skip_do_job_de_matriz_e_lido_pelo_prefixo(monkeypatch):
    """`ci-celula (admin)` é o MESMO check que `ci-celula`, com a matriz.

    Sem isto, o primeiro PR que pulasse uma célula reprovaria com "pulo não
    declarado" — e o motivo verdadeiro (o nome do job ganhou um sufixo) não
    apareceria em lugar nenhum.
    """
    pr = _pr()
    pr["statusCheckRollup"] = [
        {
            "__typename": "CheckRun",
            "name": "ci-celula (admin)",
            "status": "COMPLETED",
            "conclusion": "SKIPPED",
        },
        {
            "__typename": "CheckRun",
            "name": "muralhas",
            "status": "COMPLETED",
            "conclusion": "SUCCESS",
        },
        {
            "__typename": "CheckRun",
            "name": "ci-celula-gate",
            "status": "COMPLETED",
            "conclusion": "SUCCESS",
        },
    ]
    resultados = mergear.checar_checks(pr)
    do_skip = [r for r in resultados if "ci-celula (admin)" in r.nome]
    assert do_skip and do_skip[0].estado is Estado.SKIP, [
        (r.nome, r.estado) for r in resultados
    ]


def test_skip_de_check_desconhecido_continua_reprovando(monkeypatch):
    """A lista de skips permitidos continua FECHADA — o prefixo não a abre."""
    pr = _pr()
    pr["statusCheckRollup"] = [
        {
            "__typename": "CheckRun",
            "name": "inventado (algo)",
            "status": "COMPLETED",
            "conclusion": "SKIPPED",
        }
    ]
    resultados = mergear.checar_checks(pr)
    assert any(r.estado is Estado.FAIL for r in resultados)


# ---------------------------------------------------------------------------
# `Depende-de: #N` — a ordem entre PRs, cobrada por máquina (Onda 5)
#
# Com a cerca derrubada, trabalho grande sai em PRs encadeados. A pista de
# pouso atende por ANTIGUIDADE e não conhece essa ordem — sem esta checagem,
# dois PRs dependentes podem pousar trocados e a `main` fica com o consumidor
# falando com uma API que ainda não existe.
# ---------------------------------------------------------------------------


def _pr_com_corpo(corpo: str) -> dict:
    pr = _pr()
    pr["body"] = corpo
    return pr


@pytest.mark.parametrize(
    "corpo,esperado",
    [
        ("Depende-de: #12", [12]),
        ("depende de: #12 e #34", [12, 34]),
        (NL.join(["bla", "", "Depende-De:  #7", "", "mais texto"]), [7]),
        ("nada aqui", []),
        ("uma menção solta a #99 no meio do texto", []),
    ],
)
def test_le_a_declaracao_de_dependencia(corpo: str, esperado: list) -> None:
    assert mergear.dependencias_declaradas(_pr_com_corpo(corpo)) == esperado


def test_dependencia_ainda_aberta_reprova(monkeypatch) -> None:
    import json as _json

    def gh(argumentos, raiz, descricao, **kwargs):
        if argumentos[:2] == ["pr", "view"]:
            return _json.dumps({"state": "OPEN", "title": "o provedor"})
        return ""

    monkeypatch.setattr(mergear, "_gh", gh)
    resultados = mergear.checar_dependencias(RAIZ, _pr_com_corpo("Depende-de: #12"))
    assert resultados and resultados[0].estado is Estado.FAIL
    assert "ainda não entrou" in resultados[0].resumo


def test_dependencia_ja_mergeada_passa(monkeypatch) -> None:
    import json as _json

    monkeypatch.setattr(
        mergear,
        "_gh",
        lambda *a, **k: _json.dumps({"state": "MERGED", "title": "o provedor"}),
    )
    resultados = mergear.checar_dependencias(RAIZ, _pr_com_corpo("Depende-de: #12"))
    assert resultados and resultados[0].estado is Estado.PASS


def test_dependencia_que_nao_da_para_conferir_e_ERROR(monkeypatch) -> None:
    """"Não sei se a dependência entrou" nunca vira "pode entrar"."""

    def gh_quebrado(*a, **k):
        raise mergear.ErroDeInstrumentacao("gh fora do ar", "")

    monkeypatch.setattr(mergear, "_gh", gh_quebrado)
    resultados = mergear.checar_dependencias(RAIZ, _pr_com_corpo("Depende-de: #12"))
    assert resultados and resultados[0].estado is Estado.ERROR


def test_pr_que_depende_de_si_mesmo_reprova(monkeypatch) -> None:
    monkeypatch.setattr(mergear, "_gh", lambda *a, **k: "{}")
    resultados = mergear.checar_dependencias(RAIZ, _pr_com_corpo("Depende-de: #99"))
    assert resultados and resultados[0].estado is Estado.FAIL
    assert "si mesmo" in resultados[0].resumo


def test_sem_declaracao_nao_ha_checagem(monkeypatch) -> None:
    """Declarar é opcional. Declarado, é cobrado — mas o silêncio não custa."""

    def nunca(*a, **k):
        raise AssertionError("não pode consultar o GitHub sem declaração")

    monkeypatch.setattr(mergear, "_gh", nunca)
    assert mergear.checar_dependencias(RAIZ, _pr_com_corpo("")) == []


# ---------------------------------------------------------------------------
# A PISTA NÃO DEPENDE DE PERMISSÃO QUE ELA NÃO TEM (conserto de 29/08/2026)
#
# A pista terminava chamando a si mesma (`gh workflow run pouso.yml`) para
# atender o próximo da fila. Isso exige `actions: write` no token, e a
# `PISTA_TOKEN` não tem: o merge acontecia e o run terminava VERMELHO, toda vez
# — `HTTP 403: Resource not accessible by personal access token`.
#
# Quem viu foi o mantenedor, olhando a lista de execuções e perguntando "o pouso
# vai ficar assim?". Um vermelho permanente é pior que um defeito visível: ele
# ensina a ignorar vermelho, e esta casa inteira depende de vermelho significar
# alguma coisa.
# ---------------------------------------------------------------------------


def _pouso_yml() -> str:
    return (RAIZ / ".github" / "workflows" / "pouso.yml").read_text(encoding="utf-8")


def test_a_pista_nao_chama_a_si_mesma_por_dispatch():
    """`gh workflow run` aqui volta a exigir uma permissão que o token não tem."""
    import yaml as _yaml

    fluxo = _yaml.safe_load(_pouso_yml())
    script = "".join(
        str(passo.get("run", "")) for passo in fluxo["jobs"]["pousar"]["steps"]
    )
    linhas = [
        ln
        for ln in script.splitlines()
        if "gh workflow run" in ln and not ln.strip().startswith("#")
    ]
    assert not linhas, (
        "a pista voltou a se auto-chamar: isso exige `actions: write`, que a "
        "PISTA_TOKEN não tem, e faz TODA passagem que mergeia terminar "
        "vermelha: " + ", ".join(linhas)
    )


def test_a_fila_anda_dentro_da_mesma_execucao():
    """Sem o laço, cada passagem atenderia UM PR e o resto esperaria 15 min."""
    script = _pouso_yml()
    assert "MAX_POUSOS" in script, "sumiu o laço que faz a fila andar"
    assert "for volta in" in script


def test_a_pista_continua_com_um_pouso_por_vez():
    """Ordem serial é o ponto da pista: `concurrency` sem cancelamento."""
    import yaml as _yaml

    fluxo = _yaml.safe_load(_pouso_yml())
    assert fluxo["concurrency"]["group"] == "pouso"
    assert fluxo["concurrency"]["cancel-in-progress"] is False


def test_a_pista_continua_atendendo_o_mais_antigo_primeiro():
    assert "sort_by(.createdAt)" in _pouso_yml(), (
        "quem pediu antes pousa antes — sem isso a fila vira sorteio"
    )


def test_a_pista_nao_atende_o_mesmo_PR_duas_vezes_na_mesma_passagem():
    """O GitHub lista um PR como aberto por alguns segundos DEPOIS do merge.

    Medido em 29/08/2026, na primeira passagem do laço novo: a volta seguinte
    pegou o mesmo PR que acabara de pousar. Naquele run o portão respondeu ERROR
    e a pista saiu quieta — mas com FAIL ela teria tirado a etiqueta e comentado
    "não pousei" num PR que ENTROU. Comentário mentiroso no PR é pior que volta
    perdida: ele vira a memória do projeto.
    """
    script = _pouso_yml()
    assert "ja_vistos" in script, (
        "sumiu a lista de PRs já atendidos na passagem — a pista pode voltar a "
        "comentar 'não pousei' num PR que pousou"
    )


def test_a_pista_acorda_quando_os_checks_concluem():
    """O agendamento é rede, não despertador único.

    Pergunta do mantenedor em 29/08/2026: "esse agendamento resolve algum
    problema concreto ou causa mais demora desnecessária?". Medido: as duas
    coisas — sem o gatilho de evento, um PR cujos checks terminam em ~2 min
    esperava até ~13 min parado, e a espera cheia caía justamente em quem
    seguia a regra da casa ("peça pouso e vá embora"). Se este gatilho sumir,
    a demora desnecessária volta em silêncio.
    """
    import yaml as _yaml

    fluxo = _yaml.safe_load(_pouso_yml())
    gatilhos = fluxo.get(True) or fluxo.get("on")
    assert "workflow_run" in gatilhos, "a pista voltou a acordar só pelo relógio"
    vigiados = gatilhos["workflow_run"]["workflows"]
    assert "ci-celula" in vigiados and "muralhas" in vigiados
    assert "schedule" in gatilhos, (
        "a rede de segurança saiu — o evento perde acordadas (workflow "
        "renomeado, etiqueta posta num PR já verde), e aí alguém espera para sempre"
    )


def test_a_pista_acorda_quando_a_etiqueta_e_posta():
    """O buraco que o `workflow_run` não cobre é o fluxo PADRÃO da casa.

    `mergear.py --pousar` etiqueta DEPOIS dos checks verdes — nenhum
    `workflow_run` vem depois disso, e quem seguia a regra ("peça pouso e vá
    embora") esperava a rede de 15 min. O gatilho tem de ser
    `pull_request_target` (roda a definição da MAIN — decisão 2: um PR não
    altera o juiz que o julga), nunca `pull_request`.
    """
    import yaml as _yaml

    fluxo = _yaml.safe_load(_pouso_yml())
    gatilhos = fluxo.get(True) or fluxo.get("on")
    assert "pull_request_target" in gatilhos, (
        "a etiqueta parou de acordar a pista — o fluxo padrão do --pousar "
        "volta a esperar até 15 min parado"
    )
    assert "labeled" in gatilhos["pull_request_target"]["types"]
    assert "pull_request" not in gatilhos, (
        "pull_request (sem _target) roda a definição DO PR — o PR passa a "
        "poder alterar o juiz que vai julgá-lo (decisão 2 do cabeçalho)"
    )
    # A decisão 2 só sobrevive se o job continuar julgando com o código da main.
    passos = fluxo["jobs"]["pousar"]["steps"]
    checkouts = [p for p in passos if "checkout" in str(p.get("uses", ""))]
    assert checkouts and all(
        p.get("with", {}).get("ref") == "main" for p in checkouts
    ), "o checkout da pista deixou de ser ref: main — o juiz virou o réu"


# --------------------------------------------------------------------------
# PEDIR POUSO COM A BASE ENVELHECIDA — a contradição que a auditoria achou
#
# `RITOS.md` §2 peça 4 dizia "o --pousar só age com o portão verde"; a peça 5
# dizia "Quando usar: o PR ficou BEHIND mais de uma vez". Um PR BEHIND não está
# verde, então o comando recusava exatamente o caso que a lei manda mandar para
# a pista — e empurrava o agente de volta para o laço de oito voltas
# (`armadilhas/156`) que a pista existe para abolir.
#
# Pedir pouso NÃO mergeia: põe na fila. A pista atualiza a base, roda ESTE
# MESMO portão contra o mundo novo e só então mergeia. Por isso aceitar aqui
# não afrouxa nada — e por isso vermelho de verdade e ERROR continuam recusando.
# --------------------------------------------------------------------------


def _relatorio(*resultados):
    r = mergear.Relatorio("teste")
    for x in resultados:
        r.registrar(x)
    return r


_BEHIND = mergear.Resultado(
    "conflitos", Estado.FAIL, "a base envelheceu — este PR está ATRÁS da main (BEHIND)"
)
_VERDE = mergear.Resultado("check/x", Estado.PASS, "verde")
_PULADO = mergear.Resultado("check/y", Estado.SKIP, "pulo declarado como permitido")
_VERMELHO = mergear.Resultado("check/z", Estado.FAIL, "não passou (conclusão: FAILURE)")
_ERRO = mergear.Resultado("checks", Estado.ERROR, "nenhum check reportado neste PR")


def test_so_a_base_velha_pode_pedir_pouso():
    """O caso que a peça 5 nomeia: só falta atualizar, e a pista faz isso."""
    assert mergear.so_falta_atualizar_a_base(
        _relatorio(_VERDE, _BEHIND, _PULADO)
    ) is True


def test_base_velha_MAIS_check_vermelho_continua_recusando():
    """A pista não é lugar de despejar PR quebrado — ela é a catraca com paciência."""
    assert mergear.so_falta_atualizar_a_base(
        _relatorio(_BEHIND, _VERMELHO)
    ) is False


def test_base_velha_MAIS_erro_continua_recusando():
    """ERROR é 'não consegui medir'. Enfileirar o que não se mediu é adivinhar."""
    assert mergear.so_falta_atualizar_a_base(_relatorio(_BEHIND, _ERRO)) is False


def test_check_vermelho_sozinho_nao_vira_pouso():
    assert mergear.so_falta_atualizar_a_base(_relatorio(_VERDE, _VERMELHO)) is False


def test_erro_sozinho_nao_vira_pouso():
    assert mergear.so_falta_atualizar_a_base(_relatorio(_ERRO)) is False


def test_relatorio_verde_nao_passa_por_esta_porta():
    """Verde segue o caminho normal; esta função é só para a exceção."""
    assert mergear.so_falta_atualizar_a_base(_relatorio(_VERDE)) is False


def test_a_lei_e_o_codigo_dizem_a_mesma_coisa_sobre_pousar_com_base_velha():
    """A contradição era entre DUAS metades do RITOS — o texto viaja junto.

    Sem este guarda, o conserto do código deixaria a peça 4 dizendo o oposto do
    que o comando faz, e a próxima sessão acreditaria no documento.
    """
    ritos = (RAIZ / "RITOS.md").read_text(encoding="utf-8")
    assert "o `--pousar` só age com o portão verde" not in ritos, (
        "a peça 4 do RITOS ainda afirma que o --pousar exige portão verde, e o "
        "código já aceita a base envelhecida. Documento e mecanismo discordando "
        "é a doença que este projeto mais paga caro."
    )
    assert "base envelhecida" in ritos or "base velha" in ritos, (
        "o RITOS precisa dizer, em algum lugar, o que acontece ao pedir pouso "
        "com a base envelhecida"
    )


# --------------------------------------------------------------------------
# O MOTIVO EM CÓDIGO — quem roteia não pode depender de prosa
#
# A pista decidia o destino de um PR procurando a frase em português
# "ATRÁS da main (BEHIND)" no relatório do portão. Achado por acidente na
# auditoria das Ondas 3 a 6: um dublê de teste escreveu a frase sem acento e o
# roteamento errou — tratou "só precisa atualizar" como "reprovou", que na
# pista significa TIRAR a etiqueta e comentar "não pousei" num PR são.
#
# Agora o portão imprime `MOTIVO-DA-RECUSA: BASE-VELHA` e a pista lê isso. Os
# testes abaixo existem para que as duas pontas não possam se soltar em
# silêncio: se o token mudar num arquivo e não no outro, aqui fica vermelho.
# --------------------------------------------------------------------------


def test_a_base_velha_vira_codigo_de_motivo():
    relatorio = mergear.Relatorio("teste")
    relatorio.registrar(mergear.Resultado("check/x", Estado.PASS, "verde"))
    relatorio.registrar(_BEHIND)
    assert mergear.motivos_da_recusa(relatorio) == [mergear.MOTIVO_BASE_VELHA]


def test_relatorio_sem_base_velha_nao_inventa_motivo():
    """Código emitido à toa faria a pista atualizar um PR que não precisa."""
    relatorio = mergear.Relatorio("teste")
    relatorio.registrar(_VERMELHO)
    relatorio.registrar(_ERRO)
    assert mergear.motivos_da_recusa(relatorio) == []


def test_a_linha_do_motivo_e_ASCII_PURO():
    """O ponto inteiro do conserto: nada de acento no que atravessa shell/YAML.

    A frase em português continua no relatório, para gente ler. O que ROTEIA
    tem de sobreviver a locale, codificação e a um `grep` de shell.
    """
    linha = f"{mergear.MARCA_DE_MOTIVO} {mergear.MOTIVO_BASE_VELHA}"
    assert linha.isascii(), f"o motivo saiu com caractere não-ASCII: {linha!r}"


def test_a_pista_procura_EXATAMENTE_o_codigo_que_o_portao_imprime():
    """As duas pontas, amarradas. Sem isto, elas se soltam sem nada avisar."""
    pouso = (RAIZ / ".github" / "workflows" / "pouso.yml").read_text(
        encoding="utf-8"
    )
    assert mergear.MARCA_DE_MOTIVO in pouso, (
        f"a pista não procura mais a marca '{mergear.MARCA_DE_MOTIVO}' que "
        "ci/mergear.py imprime — o roteamento do pouso está solto"
    )
    assert mergear.MOTIVO_BASE_VELHA in pouso, (
        f"a pista não procura mais o código '{mergear.MOTIVO_BASE_VELHA}'"
    )


def test_a_pista_NAO_roteia_mais_pela_frase_em_portugues():
    """A frase pode voltar ao relatório; ela não pode voltar a DECIDIR."""
    pouso = (RAIZ / ".github" / "workflows" / "pouso.yml").read_text(
        encoding="utf-8"
    )
    for linha in pouso.splitlines():
        alvo = linha.strip()
        if not alvo.startswith("if grep") and not alvo.startswith("grep"):
            continue
        assert "ATRÁS da main" not in alvo, (
            "a pista voltou a decidir pela frase em português:\n  "
            + alvo
            + "\nRotear por prosa é o defeito que o MOTIVO-DA-RECUSA fechou."
        )


# ---------------------------------------------------------------------------
# A SOMBRA DO EVENTO DA FILA (06/09/2026) — a porta vê o que gravaria.
#
# O buraco de desenho: o rito manda pedir pouso e ir embora, então o evento
# "concluída" da fila depende de o robô ainda estar vivo na hora do merge.
# Aqui a porta passa a saber escrevê-lo. Nasce em SOMBRA (a lei do Sistema
# Imunológico), e o teste que mais importa é o que prova que ela NÃO GRAVA.
# ---------------------------------------------------------------------------


def _fila_com_tarefa_reivindicada(raiz: Path, quem: str = "despacho-ci-0609") -> Path:
    import json as _json

    (raiz / "fila" / "tarefas").mkdir(parents=True, exist_ok=True)
    (raiz / "fila" / "eventos").mkdir(parents=True, exist_ok=True)
    (raiz / "fila" / "tarefas" / "001-exemplo.json").write_text(
        _json.dumps(
            {
                "arquivo": "001-exemplo",
                "id": "TAR-001",
                "titulo": "Uma tarefa de exemplo",
                "toca": ["ci"],
                "evidencia_exigida": "um PR mergeado",
                "despacho": "faça a coisa",
                "origem": "teste",
                "criada_em": "2026-09-06",
            }
        ),
        encoding="utf-8",
    )
    (raiz / "fila" / "eventos" / "20260906-100000-TAR-001-reivindicada.json").write_text(
        _json.dumps(
            {
                "arquivo": "20260906-100000-TAR-001-reivindicada",
                "tarefa": "TAR-001",
                "evento": "reivindicada",
                "quando": "2026-09-06T10:00:00+00:00",
                "quem": quem,
            }
        ),
        encoding="utf-8",
    )
    return raiz


def _pr_que_cita_a_tarefa() -> dict:
    return _pr(title="ci: o evento pela porta (TAR-001)", body="atende a TAR-001")


def _eventos_no_disco(raiz: Path) -> list[str]:
    return sorted(p.name for p in (raiz / "fila" / "eventos").glob("*.json"))


def test_a_porta_diz_em_sombra_o_evento_que_gravaria(monkeypatch, tmp_path, capsys):
    raiz = _fila_com_tarefa_reivindicada(tmp_path)
    antes = _eventos_no_disco(raiz)
    chamadas: list = []
    monkeypatch.setenv(mergear.VARIAVEL_DA_PISTA, "sim")
    monkeypatch.setattr(mergear, "raiz_do_repo", lambda: raiz)
    monkeypatch.setattr(
        mergear, "conferir", lambda n: (_relatorio_verde(), _pr_que_cita_a_tarefa())
    )
    monkeypatch.setattr(mergear, "_gh", _gh_de_mentira(chamadas))
    assert mergear.main(["99", "--confirmo", "99"]) == 0
    saida = capsys.readouterr().out
    assert "sombra: eu teria gravado fila/eventos/" in saida
    assert '"evento": "concluida"' in saida
    assert '"quem": "despacho-ci-0609"' in saida
    assert _eventos_no_disco(raiz) == antes, "sombra que grava deixou de ser sombra"


def test_a_sombra_nao_roda_se_o_merge_nao_aconteceu(monkeypatch, tmp_path, capsys):
    """Evento de conclusão sem merge seria mentira escrita no livro da fila."""
    raiz = _fila_com_tarefa_reivindicada(tmp_path)
    chamadas: list = []
    monkeypatch.setenv(mergear.VARIAVEL_DA_PISTA, "sim")
    monkeypatch.setattr(mergear, "raiz_do_repo", lambda: raiz)
    monkeypatch.setattr(
        mergear, "conferir", lambda n: (_relatorio_verde(), _pr_que_cita_a_tarefa())
    )
    monkeypatch.setattr(mergear, "_gh", _gh_de_mentira(chamadas, "OPEN"))
    assert mergear.main(["99", "--confirmo", "99"]) == 1
    assert "SOMBRA" not in capsys.readouterr().out


def test_confirmo_de_quem_nao_e_a_pista_continua_recusando_e_sem_sombra(
    monkeypatch, tmp_path, capsys
):
    """(e) O guarda que já existia não pode afrouxar por causa da sombra."""
    raiz = _fila_com_tarefa_reivindicada(tmp_path)
    chamadas: list = []
    monkeypatch.delenv(mergear.VARIAVEL_DA_PISTA, raising=False)
    monkeypatch.setattr(mergear, "raiz_do_repo", lambda: raiz)
    monkeypatch.setattr(
        mergear, "conferir", lambda n: (_relatorio_verde(), _pr_que_cita_a_tarefa())
    )
    monkeypatch.setattr(mergear, "_gh", _gh_de_mentira(chamadas))
    assert mergear.main(["99", "--confirmo", "99"]) == 1
    assert chamadas == []
    assert "SOMBRA" not in capsys.readouterr().out


def test_pr_sem_tarefa_citada_nao_consulta_o_diff(monkeypatch, tmp_path, capsys):
    """A maioria dos PRs não atende tarefa nenhuma: nem a chamada extra."""
    raiz = _fila_com_tarefa_reivindicada(tmp_path)
    chamadas: list = []
    monkeypatch.setenv(mergear.VARIAVEL_DA_PISTA, "sim")
    monkeypatch.setattr(mergear, "raiz_do_repo", lambda: raiz)
    monkeypatch.setattr(mergear, "conferir", lambda n: (_relatorio_verde(), _pr()))
    monkeypatch.setattr(mergear, "_gh", _gh_de_mentira(chamadas))
    assert mergear.main(["99", "--confirmo", "99"]) == 0
    assert not any(c and c[0] == "api" for c in chamadas)
    assert "SOMBRA" not in capsys.readouterr().out


def test_diff_ilegivel_nao_derruba_o_pouso_ja_consumado(monkeypatch, tmp_path, capsys):
    """Sombra é fail-open: ela roda DEPOIS do merge, e uma exceção aqui viraria
    um pouso bem-sucedido em ERROR. Muralha na dúvida recusa; sombra cala."""
    raiz = _fila_com_tarefa_reivindicada(tmp_path)
    chamadas: list = []

    def _gh_que_quebra_no_diff(argumentos, raiz_, descricao, **kwargs):
        if argumentos and argumentos[0] == "api":
            raise mergear.ErroDeInstrumentacao("o gh caiu", "sem rede")
        return _gh_de_mentira(chamadas)(argumentos, raiz_, descricao, **kwargs)

    monkeypatch.setenv(mergear.VARIAVEL_DA_PISTA, "sim")
    monkeypatch.setattr(mergear, "raiz_do_repo", lambda: raiz)
    monkeypatch.setattr(
        mergear, "conferir", lambda n: (_relatorio_verde(), _pr_que_cita_a_tarefa())
    )
    monkeypatch.setattr(mergear, "_gh", _gh_que_quebra_no_diff)
    assert mergear.main(["99", "--confirmo", "99"]) == 0
    saida = capsys.readouterr().out
    assert "sombra: eu teria gravado" not in saida
    assert "não consegui ler o diff" in saida


def test_a_sombra_nao_mergeia_nem_muda_o_veredito(monkeypatch, tmp_path):
    """A sombra é observação pura: nenhum comando novo que ESCREVA no GitHub."""
    raiz = _fila_com_tarefa_reivindicada(tmp_path)
    chamadas: list = []
    monkeypatch.setenv(mergear.VARIAVEL_DA_PISTA, "sim")
    monkeypatch.setattr(mergear, "raiz_do_repo", lambda: raiz)
    monkeypatch.setattr(
        mergear, "conferir", lambda n: (_relatorio_verde(), _pr_que_cita_a_tarefa())
    )
    monkeypatch.setattr(mergear, "_gh", _gh_de_mentira(chamadas))
    assert mergear.main(["99", "--confirmo", "99"]) == 0
    escritas = [c for c in chamadas if c[:2] == ["pr", "merge"]]
    assert len(escritas) == 1, "a sombra não pode disparar nada além do merge"
