"""A VÁLVULA DE EMERGÊNCIA INTEIRA — forma medida do `.github/workflows/rollback.yml`.

Este arquivo não testa Python: lê o YAML do workflow e afirma o que ele precisa
ter para funcionar no dia em que for usado. É a única prova possível aqui, e é
mecânica: ninguém dispara um rollback de verdade para conferir, e um rollback
que só falha na hora do incêndio não é descoberto por ninguém antes.

DOIS FATOS MEDIDOS EM 19/09/2026, ANTES DE UMA LINHA SER ESCRITA:

1. O job `aplicar` NÃO faz checkout, e manda o `appleboy/ssh-action` rodar
   `script_path: infra/reverter-celula-na-vps.sh` — um arquivo que, sem
   checkout, não existe no runner. Todos os outros jobs da casa que usam
   `script_path` (deploy-celula, deploy-infra) começam por `actions/checkout`.
   O `script_path` entrou neste workflow em 28/08/2026 (c6f90bfe) e o job
   `aplicar-na-vps` não roda desde 24/08/2026: a válvula de emergência está
   quebrada há três semanas, e nenhum run vermelho existe para acusá-la,
   porque ninguém a dispara sem emergência.

2. Nada no workflow congelava a célula. O PR #1739 deu à casa o congelamento
   (`refs/congelamentos/<celula>`), mas quem voltava uma imagem tinha de
   digitar `python ci/rollback.py congelar` à mão — e às 2h da manhã o que
   depende de alguém lembrar não acontece.

O congelamento roda com `always()` DE PROPÓSITO, e isso merece defesa porque o
workflow proíbe `always()` no `if:` do JOB: lá ele apagaria a prova de que o
alvo é seguro. Aqui é outra coisa. O job só começa com o alvo já provado, e
quando este passo roda a produção JÁ FOI TOCADA. SSH que falha pela metade,
script que não imprime a marca de conclusão, run cancelado no meio: em todos
esses a célula está num estado que ninguém garante, e integrar por cima é pior
que congelar sem precisar. Congelar de menos custa um rollback desfeito em
silêncio; congelar de mais custa um comando de seis palavras.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

CI = Path(__file__).resolve().parents[1]
if str(CI) not in sys.path:
    sys.path.insert(0, str(CI))

RAIZ = Path(__file__).resolve().parents[2]
WORKFLOWS = RAIZ / ".github" / "workflows"
ROLLBACK = WORKFLOWS / "rollback.yml"

# Medido em 19/09/2026 em todo `.github/workflows/`: os jobs que JÁ escreviam
# no repositório antes desta tarefa. A lista é fechada para que uma permissão
# nova em qualquer workflow precise passar por aqui e ser explicada.
ESCRITA_ANTES = {
    ("alarme-main.yml", "reverter"),
    ("vacina-do-deploy.yml", "medir"),
}
ESCRITA_NOVA = ("rollback.yml", "aplicar")


def _workflow(nome: str = "rollback.yml") -> dict:
    return yaml.safe_load((WORKFLOWS / nome).read_text(encoding="utf-8"))


def _passos(job: str) -> list[dict]:
    return _workflow()["jobs"][job]["steps"]


def _passo_do_congelamento() -> dict:
    achados = [
        p
        for p in _passos("aplicar")
        if "rollback.py" in (p.get("run") or "") and "congelar" in (p.get("run") or "")
    ]
    assert achados, (
        "o job que aplica o rollback não congela a célula. Sem isso, a "
        "integração automática devolve a célula a :main em até 15 minutos, "
        "com o run verde."
    )
    assert len(achados) == 1, "congelar duas vezes no mesmo job esconde qual valeu"
    return achados[0]


# ---------------------------------------------------------------------------
# A válvula inteira, não só o passo novo
# ---------------------------------------------------------------------------


def test_todo_script_remoto_tem_checkout_antes_dele() -> None:
    """`script_path` lê um arquivo DO RUNNER; sem checkout ele não existe.

    Este é o defeito que quebrou a válvula em 28/08/2026 sem deixar rastro.
    """
    for nome in sorted(p.name for p in WORKFLOWS.glob("*.yml")):
        for job, corpo in (_workflow(nome).get("jobs") or {}).items():
            vistos_checkout = False
            for passo in corpo.get("steps") or []:
                if (passo.get("uses") or "").startswith("actions/checkout"):
                    vistos_checkout = True
                if (passo.get("with") or {}).get("script_path"):
                    assert vistos_checkout, (
                        f"{nome}::{job} manda rodar "
                        f"{passo['with']['script_path']} sem ter feito checkout. "
                        "O arquivo não existe no runner, e o passo falha no "
                        "instante em que alguém mais precisa dele."
                    )


def test_o_job_que_aplica_confere_a_marca_de_conclusao_e_reprova_sem_ela() -> None:
    """Em 28/08/2026 o SSH conectou, ignorou o script e saiu com sucesso."""
    corpo = "\n".join(p.get("run") or "" for p in _passos("aplicar"))
    assert "REVERSAO-CONCLUIDA:" in corpo, "a marca de conclusão sumiu do workflow"
    assert "exit 1" in corpo, (
        "a ausência da marca precisa REPROVAR o job; sem isso, 'a porta abriu' "
        "volta a ser lido como 'o trabalho foi feito'."
    )


def test_o_job_que_aplica_so_roda_com_o_alvo_provado() -> None:
    """A guarda que impede `workflow_dispatch` de virar caminho para produção."""
    condicao = _workflow()["jobs"]["aplicar"]["if"]
    for exigencia in (
        "needs.validar.result == 'success'",
        "needs.validar.outputs.celula != ''",
        "needs.validar.outputs.tag != ''",
        "needs.validar.outputs.var_tag != ''",
    ):
        assert exigencia in condicao, f"o job que aplica perdeu a guarda: {exigencia}"
    assert "always()" not in condicao, (
        "always() no JOB apagaria a prova de que o alvo é seguro; ele vale "
        "só no passo do congelamento, depois de a produção já ter sido tocada."
    )


# ---------------------------------------------------------------------------
# O congelamento, ligado onde a imagem volta
# ---------------------------------------------------------------------------


def test_o_congelamento_roda_no_job_que_aplica() -> None:
    _passo_do_congelamento()


def test_o_congelamento_roda_mesmo_se_o_passo_anterior_falhar() -> None:
    """SSH pela metade, marca ausente ou run cancelado deixam a célula incerta."""
    condicao = _passo_do_congelamento().get("if") or ""
    assert "always()" in condicao, (
        "sem always(), um SSH que falha pela metade deixa a célula num estado "
        "que ninguém garante E destravada para a integração automática."
    )


def test_o_congelamento_nao_dispara_ao_voltar_para_a_linha_principal() -> None:
    """`alvo=main` é o DESFAZER do RITOS §4: congelar ali travaria a casa à toa."""
    condicao = _passo_do_congelamento().get("if") or ""
    assert "'main'" in condicao and "needs.validar.outputs.tag" in condicao, (
        "o passo precisa excluir o alvo `main`: aquele disparo desfaz o pin, e "
        "congelar a célula nele pararia a fábrica sem nenhum incidente de pé."
    )


def test_o_congelamento_recebe_celula_e_motivo_como_dados_nunca_costurados() -> None:
    """Motivo é texto LIVRE: interpolado no `run:`, aspas e `;` viram comando."""
    passo = _passo_do_congelamento()
    assert "${{" not in (passo.get("run") or ""), (
        "nada de `${{ }}` dentro do run: passe por env, onde o shell recebe o "
        "valor como dado e não como código."
    )
    assert passo.get("env"), "o passo precisa receber célula e motivo por env"


# ---------------------------------------------------------------------------
# A permissão, medida e não afirmada
# ---------------------------------------------------------------------------


def test_so_o_job_que_aplica_ganhou_escrita_em_toda_a_casa() -> None:
    medido = set()
    for arquivo in sorted(WORKFLOWS.glob("*.yml")):
        dados = _workflow(arquivo.name)
        topo = dados.get("permissions") or {}
        assert not (isinstance(topo, dict) and topo.get("contents") == "write"), (
            f"{arquivo.name} dá escrita no nível do WORKFLOW inteiro; a "
            "permissão é do job que precisa dela, nunca de todos."
        )
        for job, corpo in (dados.get("jobs") or {}).items():
            permissoes = corpo.get("permissions") or {}
            if isinstance(permissoes, dict) and permissoes.get("contents") == "write":
                medido.add((arquivo.name, job))
    assert medido == ESCRITA_ANTES | {ESCRITA_NOVA}, (
        f"os jobs com escrita mudaram.\n  medido:   {sorted(medido)}\n"
        f"  esperado: {sorted(ESCRITA_ANTES | {ESCRITA_NOVA})}"
    )


def test_o_job_que_valida_o_alvo_continua_sem_escrita() -> None:
    """Quem lê o registry e julga o alvo nunca precisou escrever no repositório."""
    permissoes = _workflow()["jobs"]["validar"]["permissions"]
    assert permissoes.get("contents") == "read", permissoes
    assert permissoes.get("packages") == "read", permissoes


def test_o_checkout_que_congela_guarda_a_credencial() -> None:
    """`persist-credentials: false` aqui deixaria o `git push` do congelamento
    sem token, e o congelamento falharia calado no meio de uma emergência."""
    for passo in _passos("aplicar"):
        if (passo.get("uses") or "").startswith("actions/checkout"):
            com = passo.get("with") or {}
            assert com.get("persist-credentials") is not False, com
            return
    raise AssertionError("o job que aplica não faz checkout")
