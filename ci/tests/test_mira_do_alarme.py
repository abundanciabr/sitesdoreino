"""A mira do socorro, provada com históricos montados à mão — sem rede.

Por que sem rede: a mira decide QUEM tem o trabalho desfeito. Um teste que
pergunta ao GitHub só prova que o GitHub respondeu hoje; ele não consegue
montar a fronteira ambígua (um `cancelled` entre dois vermelhos, a janela
inteira vermelha) que é exatamente onde a mira precisa RECUSAR. Aqui cada
história é um caso escrito à mão, e uma delas é a história real de 30/08/2026,
copiada de `gh run list --workflow=alarme-main.yml`.

O que estes testes protegem, em uma frase: **a automação de reversão nunca
aponta para quem não quebrou** — e, quando não consegue saber, ela diz que não
sabe em vez de escolher alguém.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

CI = Path(__file__).resolve().parents[1]
if str(CI) not in sys.path:
    sys.path.insert(0, str(CI))

import mira_do_alarme  # noqa: E402

# ---------------------------------------------------------------------------
# A HISTÓRIA REAL DE 30/08/2026, mais nova primeiro.
#
# Os SHAs e as conclusões vêm de `gh run list --workflow=alarme-main.yml
# --branch main`; o `run_number` é sintético e monotônico, que é a propriedade
# que o GitHub garante para ele. O vermelho começa em `caaeb2e8` (PR #580, o
# merge que tirou os gerados de `armadilhas/` do Git sem dizer quem os monta) e
# só termina em `c045725e` (PR #591, a fixture do conftest).
# ---------------------------------------------------------------------------
HISTORIA_REAL = [
    ("6cf04603", "failure"),
    ("cde8fd24", "failure"),
    ("e03c64b1", "failure"),
    ("ecaa4742", "failure"),
    ("ce8ee673", "failure"),
    ("8ab661aa", "failure"),
    ("86a5f59e", "failure"),
    ("caaeb2e8", "failure"),
    ("1dfce1a4", "success"),
    ("8458cb7f", "success"),
    ("12d5492d", "success"),
    ("20737b70", "success"),
]

O_CULPADO = "caaeb2e8"
O_INOCENTE_ACUSADO = "86a5f59e"  # PR #585 — a escrita do fórum


def historia(pares, *, primeiro_numero: int = 900) -> list[dict]:
    """Monta a resposta do GitHub a partir de (sha, conclusão), mais nova primeiro."""
    runs = []
    numero = primeiro_numero
    for sha, conclusao in pares:
        runs.append(
            {
                "head_sha": sha,
                "run_number": numero,
                "status": "in_progress" if conclusao == "em-andamento" else "completed",
                "conclusion": None if conclusao == "em-andamento" else conclusao,
                "html_url": f"https://exemplo.invalido/{sha}",
            }
        )
        numero -= 1
    return runs


def ate(sha: str) -> list[tuple[str, str]]:
    """A história real como ela era NO INSTANTE em que `sha` estava rodando."""
    indice = [s for s, _ in HISTORIA_REAL].index(sha)
    return HISTORIA_REAL[indice + 1:]


# ---------------------------------------------------------------------------
# O caso que motivou tudo
# ---------------------------------------------------------------------------


def test_o_caso_real_aponta_o_580_e_nunca_o_inocente_seguinte():
    """A prova de fogo: a execução de 86a5f59e acusa caaeb2e8, não a si mesma.

    O comportamento antigo revertia `github.sha` — e o commit de reversão já
    estava montado na árvore do runner (`15 files changed, 1251 deletions`,
    apagando a escrita do fórum) quando o push bateu no 403. Só a falta de
    permissão evitou o estrago.
    """
    mira = mira_do_alarme.mirar(
        historia(ate(O_INOCENTE_ACUSADO)), O_INOCENTE_ACUSADO
    )
    assert mira.achou
    assert mira.culpado == O_CULPADO
    assert mira.culpado != O_INOCENTE_ACUSADO
    assert mira.fronteira_verde == "1dfce1a4"
    assert not mira.e_a_ponta, "a main já tinha andado por cima do culpado"


@pytest.mark.parametrize("sha_da_execucao", [s for s, c in HISTORIA_REAL if c == "failure"])
def test_as_oito_execucoes_vermelhas_apontam_todas_o_mesmo_culpado(sha_da_execucao):
    """Oito execuções, um único réu — e é por isso que só nasce UM PR.

    O ramo da reversão é nomeado pelo alvo. Com a mira antiga, cada push da
    sequência gerava um nome diferente: oito PRs de reversão, sete contra
    inocentes, todos etiquetados `pousar`. Com a mira medida, os oito calculam
    `caaeb2e8` e a recusa "já existe PR de reversão para este commit" faz o
    resto sozinha.
    """
    mira = mira_do_alarme.mirar(historia(ate(sha_da_execucao)), sha_da_execucao)
    assert mira.culpado == O_CULPADO


def test_no_primeiro_vermelho_o_culpado_e_a_propria_ponta():
    """Quando o fogo acaba de começar, reverter é desfazer a última coisa."""
    mira = mira_do_alarme.mirar(historia(ate(O_CULPADO)), O_CULPADO)
    assert mira.culpado == O_CULPADO
    assert mira.e_a_ponta, (
        "com a sequência vermelha de tamanho 1 o culpado É a ponta da main — é "
        "esta distinção que autoriza o pouso automático"
    )


# ---------------------------------------------------------------------------
# As recusas — cada uma é um jeito de a automação escolher a vítima errada
# ---------------------------------------------------------------------------


def test_main_verde_agora_nao_tem_o_que_curar():
    mira = mira_do_alarme.mirar(historia([("aaa", "success"), ("bbb", "failure")]), "")
    assert not mira.achou
    assert "não há vermelho corrente" in mira.motivo


def test_janela_inteira_vermelha_recusa_em_vez_de_chutar_o_mais_antigo():
    """O commit mais velho que EU enxergo não é o mais velho que existe."""
    mira = mira_do_alarme.mirar(
        historia([(f"sha{i:03d}", "failure") for i in range(12)]), ""
    )
    assert not mira.achou
    assert "não dá para ver onde o vermelho começou" in mira.motivo


def test_cancelado_na_fronteira_recusa():
    """`cancelled` esconde o estado daquele commit — a fronteira some com ele."""
    mira = mira_do_alarme.mirar(
        historia(
            [("novo", "failure"), ("meio", "failure"), ("borda", "cancelled"),
             ("velho", "success")]
        ),
        "",
    )
    assert not mira.achou
    assert "'cancelled'" in mira.motivo


def test_execucao_ainda_rodando_na_fronteira_recusa():
    """Verde por omissão é o falso-verde do padrão 1 — aqui ele não existe."""
    mira = mira_do_alarme.mirar(
        historia([("novo", "failure"), ("borda", "em-andamento"), ("velho", "success")]),
        "",
    )
    assert not mira.achou
    assert "em-andamento" in mira.motivo


def test_historico_vazio_recusa():
    assert not mira_do_alarme.mirar([], "").achou


# ---------------------------------------------------------------------------
# A leitura do histórico — onde um empate troca o réu
# ---------------------------------------------------------------------------


def test_a_execucao_que_pergunta_conta_como_vermelha_mesmo_ausente_do_historico():
    """A API ainda mostra a execução corrente como `in_progress`.

    Esperar por ela seria esperar por si mesmo. O job só existe sob
    `if: failure()`, então o vermelho dela é fato conhecido, não suposição.
    """
    mira = mira_do_alarme.mirar(historia([("velho", "success")]), "novissimo")
    assert mira.culpado == "novissimo"
    assert mira.e_a_ponta


def test_a_execucao_que_pergunta_e_vermelha_mesmo_se_a_api_disser_outra_coisa():
    mira = mira_do_alarme.mirar(
        historia([("eu", "success"), ("velho", "success")]), "eu"
    )
    assert mira.culpado == "eu"


def test_ordena_por_numero_da_execucao_e_nao_pela_ordem_da_lista():
    """Dois merges no mesmo segundo empatam no carimbo de tempo.

    Este repositório recebe ~100 merges por dia. Um empate na fronteira do
    vermelho troca o culpado — e trocar o culpado é o defeito inteiro.
    """
    fora_de_ordem = historia([("velho", "success")], primeiro_numero=10)
    fora_de_ordem += historia([("culpado", "failure")], primeiro_numero=11)
    fora_de_ordem += historia([("depois", "failure")], primeiro_numero=12)
    mira = mira_do_alarme.mirar(fora_de_ordem, "")
    assert mira.culpado == "culpado"


def test_reexecucao_do_mesmo_commit_conta_uma_vez_so():
    """`gh run rerun` devolve o mesmo commit duas vezes; vale a mais recente."""
    runs = historia([("culpado", "failure")], primeiro_numero=50)
    runs += historia([("culpado", "failure")], primeiro_numero=49)
    runs += historia([("velho", "success")], primeiro_numero=48)
    mira = mira_do_alarme.mirar(runs, "")
    assert mira.culpado == "culpado"
    assert mira.sequencia == ("culpado",)
    assert mira.e_a_ponta


def test_a_mira_nunca_aponta_para_fora_da_sequencia_vermelha():
    """Invariante, valendo para toda história desta suíte."""
    for sha, conclusao in HISTORIA_REAL:
        if conclusao != "failure":
            continue
        mira = mira_do_alarme.mirar(historia(ate(sha)), sha)
        assert mira.culpado in mira.sequencia
        assert mira.culpado == mira.sequencia[-1]
        assert mira.fronteira_verde not in mira.sequencia


# ---------------------------------------------------------------------------
# A linha de comando — é ela que o YAML chama
# ---------------------------------------------------------------------------


def _rodar_cli(tmp_path: Path, pares, sha: str) -> subprocess.CompletedProcess:
    arquivo = tmp_path / "historico.json"
    arquivo.write_text(
        json.dumps({"workflow_runs": historia(pares)}, ensure_ascii=False),
        encoding="utf-8",
    )
    return subprocess.run(
        [
            sys.executable,
            str(CI / "mira_do_alarme.py"),
            "--historico",
            str(arquivo),
            "--sha",
            sha,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )


def test_cli_achou_sai_zero_e_imprime_a_mira_na_primeira_linha(tmp_path: Path):
    proc = _rodar_cli(tmp_path, ate(O_INOCENTE_ACUSADO), O_INOCENTE_ACUSADO)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout.splitlines()[0] == f"MIRA={O_CULPADO}"
    assert "PONTA=nao" in proc.stdout


def test_cli_primeiro_vermelho_diz_que_o_culpado_e_a_ponta(tmp_path: Path):
    proc = _rodar_cli(tmp_path, ate(O_CULPADO), O_CULPADO)
    assert proc.returncode == 0
    assert "PONTA=sim" in proc.stdout


def test_cli_recusa_sai_tres_e_nunca_zero(tmp_path: Path):
    """3 é 'medi e não sei'. Zero aqui viraria reversão do commit errado."""
    proc = _rodar_cli(tmp_path, [(f"s{i}", "failure") for i in range(9)], "")
    assert proc.returncode == 3
    assert proc.stdout.startswith("RECUSA=")


def test_cli_sem_conseguir_medir_e_ERROR_dois(tmp_path: Path):
    proc = subprocess.run(
        [
            sys.executable,
            str(CI / "mira_do_alarme.py"),
            "--historico",
            str(tmp_path / "nao-existe.json"),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "ERROR" in proc.stdout
    assert "NÃO é um 'ninguém quebrou'" in proc.stdout


def test_cli_sem_alvo_nenhum_e_ERROR_nunca_silencio():
    proc = subprocess.run(
        [sys.executable, str(CI / "mira_do_alarme.py")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    assert proc.returncode == 2
