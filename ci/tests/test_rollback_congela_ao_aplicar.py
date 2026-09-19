"""A VÁLVULA DE EMERGÊNCIA INTEIRA — forma medida do `.github/workflows/rollback.yml`.

Este arquivo não testa Python: lê o YAML do workflow e afirma o que ele precisa
ter para funcionar no dia em que for usado. É a única prova CONTÍNUA possível
aqui, e é mecânica: ninguém dispara um rollback de verdade a cada PR, e um
rollback que só falha na hora do incêndio não é descoberto por ninguém antes.

DOIS FATOS MEDIDOS EM 19/09/2026, ANTES DE UMA LINHA SER ESCRITA:

1. O job `aplicar` NÃO fazia checkout, e mandava o `appleboy/ssh-action` rodar
   `script_path: infra/reverter-celula-na-vps.sh` — um arquivo que, sem
   checkout, não existe no runner. Todos os outros jobs da casa que usam
   `script_path` (deploy-celula, deploy-infra) começam por `actions/checkout`.
   O `script_path` entrou neste workflow em 28/08/2026 (c6f90bfe) e o job
   `aplicar-na-vps` não roda desde 24/08/2026: a válvula ficou 22 dias
   quebrada, e nenhum run vermelho existiu para acusá-la, porque ninguém a
   dispara sem emergência.

2. Nada no workflow congelava a célula. O PR #1739 deu à casa o congelamento
   (`refs/congelamentos/<celula>`), mas quem voltava uma imagem tinha de
   digitar `python ci/rollback.py congelar` à mão — e às 2h da manhã o que
   depende de alguém lembrar não acontece.

A SEPARAÇÃO DE PODERES QUE ESTE ARQUIVO GUARDA: quem entra na VPS por SSH não
escreve no repositório, e quem escreve no repositório não entra na VPS. Por
isso o congelamento mora num job próprio. Um único job com a chave de deploy E
a caneta do repositório seria um passo só com os dois poderes.
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

# Medido em 19/09/2026 em todo `.github/workflows/`: os jobs que JÁ escreviam
# no repositório antes desta tarefa. A lista é fechada para que uma permissão
# nova em qualquer workflow precise passar por aqui e ser explicada.
ESCRITA_ANTES = {
    ("alarme-main.yml", "reverter"),
    ("vacina-do-deploy.yml", "medir"),
}
ESCRITA_NOVA = ("rollback.yml", "congelamento")
JOB_DO_SSH = "aplicar"
JOB_QUE_ESCREVE = "congelamento"


def _workflow(nome: str = "rollback.yml") -> dict:
    return yaml.safe_load((WORKFLOWS / nome).read_text(encoding="utf-8"))


def _passos(job: str) -> list[dict]:
    return _workflow()["jobs"][job]["steps"]


def _passo_que_roda(job: str, subcomando: str) -> dict:
    """O passo que roda ESTE subcomando. Casa o comando inteiro de propósito:
    procurar por "congelar" acharia também o "descongelar"."""
    alvo = f"rollback.py {subcomando} "
    achados = [p for p in _passos(job) if alvo in (p.get("run") or "")]
    assert achados, f"nenhum passo de `{job}` roda `{alvo.strip()}`"
    assert len(achados) == 1, f"`{alvo.strip()}` aparece duas vezes em {job}"
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
            viu_checkout = False
            for passo in corpo.get("steps") or []:
                if (passo.get("uses") or "").startswith("actions/checkout"):
                    viu_checkout = True
                if (passo.get("with") or {}).get("script_path"):
                    assert viu_checkout, (
                        f"{nome}::{job} manda rodar "
                        f"{passo['with']['script_path']} sem ter feito checkout. "
                        "O arquivo não existe no runner, e o passo falha no "
                        "instante em que alguém mais precisa dele."
                    )


def test_o_script_que_o_workflow_manda_rodar_existe_no_disco() -> None:
    """Checkout sem o arquivo seria o mesmo buraco com outra roupa."""
    for nome in sorted(p.name for p in WORKFLOWS.glob("*.yml")):
        for job, corpo in (_workflow(nome).get("jobs") or {}).items():
            for passo in corpo.get("steps") or []:
                caminho = (passo.get("with") or {}).get("script_path")
                if caminho:
                    assert (RAIZ / caminho).is_file(), (
                        f"{nome}::{job} aponta para {caminho}, que não existe "
                        "no repositório."
                    )


def test_os_tres_jobs_do_rollback_fixam_a_linha_principal() -> None:
    """`workflow_dispatch` aceita QUALQUER ref; sem `ref: main` quem dispara
    escolheria o roteiro que entra na VPS e o código que decide o congelamento."""
    for job in ("validar", JOB_DO_SSH, JOB_QUE_ESCREVE):
        checkouts = [
            p for p in _passos(job) if (p.get("uses") or "").startswith("actions/checkout")
        ]
        assert checkouts, f"o job `{job}` não faz checkout"
        for passo in checkouts:
            assert (passo.get("with") or {}).get("ref") == "main", (
                f"o checkout de `{job}` não fixa `ref: main`: {passo.get('with')}"
            )


def test_o_job_que_aplica_confere_a_marca_de_conclusao_e_reprova_sem_ela() -> None:
    """Em 28/08/2026 o SSH conectou, ignorou o script e saiu com sucesso."""
    corpo = "\n".join(p.get("run") or "" for p in _passos(JOB_DO_SSH))
    assert "REVERSAO-CONCLUIDA:" in corpo, "a marca de conclusão sumiu do workflow"
    assert "exit 1" in corpo, (
        "a ausência da marca precisa REPROVAR o job; sem isso, 'a porta abriu' "
        "volta a ser lido como 'o trabalho foi feito'."
    )


def test_o_job_que_aplica_so_roda_com_o_alvo_provado() -> None:
    """A guarda que impede `workflow_dispatch` de virar caminho para produção."""
    condicao = _workflow()["jobs"][JOB_DO_SSH]["if"]
    for exigencia in (
        "needs.validar.result == 'success'",
        "needs.validar.outputs.celula != ''",
        "needs.validar.outputs.tag != ''",
        "needs.validar.outputs.var_tag != ''",
    ):
        assert exigencia in condicao, f"o job que aplica perdeu a guarda: {exigencia}"
    assert "always()" not in condicao, (
        "always() no job do SSH apagaria a prova de que o alvo é seguro."
    )


# ---------------------------------------------------------------------------
# O ciclo completo: congelar ao voltar, descongelar ao normalizar
# ---------------------------------------------------------------------------


def test_o_congelamento_roda_mesmo_com_a_aplicacao_incerta() -> None:
    """SSH pela metade, marca ausente ou run cancelado deixam a célula incerta,
    e incerta é exatamente o estado que não pode receber deploy automático."""
    condicao = _workflow()["jobs"][JOB_QUE_ESCREVE]["if"]
    assert "always()" in condicao, condicao
    assert "needs.validar.result == 'success'" in condicao, (
        "sem alvo provado não há o que congelar: o job que aplica nem rodou."
    )
    passo = _passo_que_roda(JOB_QUE_ESCREVE, "congelar")
    assert "needs.aplicar" not in (passo.get("if") or ""), (
        "congelar NÃO pode depender do sucesso da aplicação — é justamente o "
        "desfecho incerto que mais precisa da trava."
    )


def test_o_congelamento_so_vale_para_alvo_antigo() -> None:
    """`alvo=main` é o DESFAZER do RITOS §4: congelar ali travaria a casa à toa."""
    condicao = _passo_que_roda(JOB_QUE_ESCREVE, "congelar").get("if") or ""
    assert "needs.validar.outputs.tag != 'main'" in condicao, condicao


def test_o_descongelamento_exige_a_volta_ao_normal_bem_sucedida() -> None:
    """Soltar a trava depois de uma volta incerta devolveria a integração
    automática a uma célula que ninguém sabe onde está."""
    condicao = _passo_que_roda(JOB_QUE_ESCREVE, "descongelar").get("if") or ""
    assert "needs.validar.outputs.tag == 'main'" in condicao, condicao
    assert "needs.aplicar.result == 'success'" in condicao, condicao


def test_congelar_e_descongelar_nunca_rodam_no_mesmo_disparo() -> None:
    """As duas condições são exclusivas por construção: `tag` é `main` ou não é."""
    congelar = _passo_que_roda(JOB_QUE_ESCREVE, "congelar").get("if") or ""
    soltar = _passo_que_roda(JOB_QUE_ESCREVE, "descongelar").get("if") or ""
    assert "tag != 'main'" in congelar and "tag == 'main'" in soltar, (
        f"congelar={congelar!r} descongelar={soltar!r}"
    )


def test_o_job_que_congela_configura_identidade_antes_de_assinar() -> None:
    """`git commit-tree` EXIGE autor, e o runner do GitHub não tem nenhum.

    Medido no smoke da TAR-486 (run 35417675479): sem esta linha o passo morre
    com `fatal: empty ident name`, exit 128. A bancada de um agente tem
    identidade e o runner não, então este é o defeito que só aparece às 2h da
    manhã — e é por isso que ele tem guarda.
    """
    passos = _passos(JOB_QUE_ESCREVE)
    indice_identidade = next(
        (i for i, p in enumerate(passos) if "git config user.email" in (p.get("run") or "")),
        None,
    )
    assert indice_identidade is not None, (
        "o job que congela não configura identidade de git; `git commit-tree` "
        "falha com `empty ident name` no runner."
    )
    indice_congelar = passos.index(_passo_que_roda(JOB_QUE_ESCREVE, "congelar"))
    assert indice_identidade < indice_congelar, (
        "a identidade precisa ser configurada ANTES do passo que assina."
    )


def test_celula_e_motivo_chegam_como_dados_nunca_costurados_no_shell() -> None:
    """Motivo é texto LIVRE: interpolado no `run:`, aspas e `;` viram comando."""
    for trecho in ("congelar", "descongelar"):
        passo = _passo_que_roda(JOB_QUE_ESCREVE, trecho)
        assert "${{" not in (passo.get("run") or ""), (
            f"o passo de {trecho} costura a interpolacao dentro do run; passe "
            "por env, onde o shell recebe o valor como dado e não como código."
        )
        assert passo.get("env"), f"o passo de {trecho} precisa receber a célula por env"


# ---------------------------------------------------------------------------
# A separação de poderes, medida e não afirmada
# ---------------------------------------------------------------------------


def test_so_um_job_da_casa_inteira_ganhou_escrita() -> None:
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


def test_quem_entra_na_vps_nao_escreve_no_repositorio() -> None:
    """A regra que o job separado existe para cumprir."""
    permissoes = _workflow()["jobs"][JOB_DO_SSH]["permissions"]
    assert permissoes.get("contents") == "read", permissoes
    assert any("ssh-action" in (p.get("uses") or "") for p in _passos(JOB_DO_SSH)), (
        "este teste aponta para o job errado; ele deixou de usar SSH"
    )


def test_quem_escreve_no_repositorio_nao_entra_na_vps() -> None:
    """O outro lado da mesma regra, e o que impede o job novo de crescer."""
    for passo in _passos(JOB_QUE_ESCREVE):
        usa = passo.get("uses") or ""
        assert "ssh-action" not in usa and "scp-action" not in usa, (
            f"o job que escreve no repositório ganhou acesso à VPS: {usa}"
        )
    assert "DEPLOY_SSH_KEY" not in yaml.dump(_workflow()["jobs"][JOB_QUE_ESCREVE]), (
        "o job que escreve no repositório recebeu a chave de deploy"
    )


def test_o_job_que_valida_o_alvo_continua_sem_escrita() -> None:
    """Quem lê o registry e julga o alvo nunca precisou escrever no repositório."""
    permissoes = _workflow()["jobs"]["validar"]["permissions"]
    assert permissoes.get("contents") == "read", permissoes
    assert permissoes.get("packages") == "read", permissoes


def test_o_checkout_que_congela_guarda_a_credencial() -> None:
    """`persist-credentials: false` aqui deixaria o `git push` do congelamento
    sem token, e o congelamento falharia calado no meio de uma emergência."""
    for passo in _passos(JOB_QUE_ESCREVE):
        if (passo.get("uses") or "").startswith("actions/checkout"):
            com = passo.get("with") or {}
            assert com.get("persist-credentials") is not False, com
            return
    raise AssertionError("o job que congela não faz checkout")
