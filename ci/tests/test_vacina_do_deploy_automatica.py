"""A FIAÇÃO da vacina automática do deploy — TAR-029 (30/08/2026).

`ci/tests/test_rerun_de_deploy.py` prova a DECISÃO (repetir? parar? não medi?)
com histórias montadas à mão, sem rede. Este arquivo prova a outra metade, que
nenhum teste de decisão enxerga: **que existe um gatilho, e que ele está ligado
no lugar certo**.

A distinção é a Classe 2 da `RETROSPECTIVA-FASE-D` (garantia sem mecanismo), e
foi ela que criou esta tarefa: a cura do deploy cancelado existia desde a
TAR-017, escrita e testada, e mesmo assim três deploys ficaram fora do ar em
dois dias — porque a cura era um COMANDO que alguém precisava lembrar de rodar.
Um teste que só provasse a decisão continuaria verde nesse mundo.

Por que a fiação se testa lendo o YAML: um workflow não roda em pytest. O que
dá para afirmar sem rede é o que está escrito nele — e cada asserção aqui
corresponde a um jeito MEDIDO de esta mecânica se desligar sozinha, não a uma
transcrição do arquivo.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

CI = Path(__file__).resolve().parents[1]
if str(CI) not in sys.path:
    sys.path.insert(0, str(CI))

yaml = pytest.importorskip("yaml")

RAIZ = CI.parent
ARQUIVO = RAIZ / ".github" / "workflows" / "vacina-do-deploy.yml"


@pytest.fixture(scope="module")
def wf() -> dict:
    assert ARQUIVO.exists(), (
        "sem este arquivo não há gatilho nenhum: a vacina volta a ser um "
        "comando que alguém precisa lembrar de rodar (Classe 2 da retrospectiva)"
    )
    return yaml.safe_load(ARQUIVO.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def gatilho(wf: dict) -> dict:
    # `on:` sem aspas é o booleano True em YAML 1.1 — a pegadinha clássica.
    return wf.get("on") or wf.get(True)


@pytest.fixture(scope="module")
def job(wf: dict) -> dict:
    jobs = wf["jobs"]
    assert len(jobs) == 1, f"esperava um job só; achei {sorted(jobs)}"
    return next(iter(jobs.values()))


def test_acorda_com_o_FIM_das_DUAS_esteiras_de_deploy(gatilho):
    """As duas brigam pela mesma vaga, então as duas podem ser a expulsa.

    Medido: 2 cancelados no `deploy-infra` (PRs 602 e 605) e mais dois no
    `deploy-celula` (armadilhas/183 e /188). Cobrir só uma deixaria metade da
    doença sem cura, e seria invisível — o desfecho é silêncio nos dois casos.
    """
    assert "workflow_run" in gatilho, (
        "um `schedule` teria de varrer o histórico atrás de cinzas e ainda "
        "erraria a janela; o Actions sabe a hora exata"
    )
    esteiras = set(gatilho["workflow_run"]["workflows"])
    assert esteiras == {"deploy-celula", "deploy-infra"}, f"veio: {esteiras}"
    assert gatilho["workflow_run"]["types"] == ["completed"]


def test_acorda_no_CANCELADO_e_no_VERMELHO_da_main(job):
    """As DUAS conclusões doentes desde a TAR-041 — e `success` fora.

    Até 30/08/2026 era só o `cancelled`, com a justificativa escrita de que
    *"`failure` na `main` já tem dono: o agente que mergeou, avisado pelo
    vermelho"*. A medição do dia derrubou a justificativa: 14 dos 41 deploys
    vermelhos dos últimos 30 dias morreram no timeout da porta 22
    (`armadilhas/127`), TRÊS num único dia, e a escada de 3 tentativas de
    dentro do deploy salvou 1 de 18. O "dono" existia — e o trabalho dele era
    apertar um botão que uma máquina aperta.

    A asserção do `success` não é enfeite: é ela que impede alguém de "abrir um
    pouco mais" a condição até a vacina acordar em todo deploy saudável do
    repositório, que são ~100 por dia.
    """
    condicao = " ".join(job["if"].split())
    assert "github.event.workflow_run.conclusion == 'cancelled'" in condicao
    assert "github.event.workflow_run.conclusion == 'failure'" in condicao
    assert "'success'" not in condicao, (
        "deploy verde não tem doença; acordar nele seria gastar um runner por "
        "merge para responder 'nada a fazer'"
    )
    assert "github.event.workflow_run.head_branch == 'main'" in condicao


def test_NAO_entra_no_grupo_deploy_senao_a_vacina_morre_da_doenca(wf, job):
    """O erro mais fácil deste arquivo, e ele já aconteceu uma vez (173).

    O grupo `deploy` guarda UM pendente e é a fila mais disputada do projeto.
    Uma vacina posta ali seria expulsa e morreria em `cancelled` sem uma linha
    de log — a cura contra o cancelamento morrendo de cancelamento.
    """
    grupo = str(wf["concurrency"]["group"])
    assert grupo != "deploy"
    assert "workflow_run.id" in grupo, (
        "a chave precisa ser o RUN DOENTE: assim duas curas do mesmo run se "
        "enfileiram e curas de runs diferentes correm juntas, porque não "
        f"disputam recurso nenhum (veio: {grupo})"
    )
    assert wf["concurrency"]["cancel-in-progress"] is False, (
        "cancelar a cura em andamento para começar outra do mesmo run é "
        "trocar uma cura pela metade por outra pela metade"
    )
    assert "concurrency" not in job, "grupo por job aqui só confundiria o de cima"


def test_chama_a_vacina_que_ja_sabe_decidir_em_vez_de_decidir_de_novo(job):
    """A lei anti-duplicação aplicada a uma DECISÃO (CLAUDE.md).

    Se o YAML medisse ancestralidade por conta própria, existiriam duas regras
    para a mesma pergunta — e bastaria afinar uma para elas discordarem sobre
    republicar ou não, que é a diferença entre curar e fazer rollback.
    """
    passos = "\n".join(str(p.get("run", "")) for p in job["steps"])
    # O PASSO DA CURA, e não o arquivo inteiro: o corpo da issue cita
    # `--so-diagnosticar` de propósito, ensinando o humano a olhar sem mexer.
    curar = next(p for p in job["steps"] if p.get("id") == "vacina")["run"]
    assert "ci/rerun_de_deploy.py" in curar
    assert "--run" in curar
    assert "--so-diagnosticar" not in curar, (
        "diagnosticar sem repetir devolveria o problema para o humano, que é "
        "exatamente o que esta tarefa veio tirar do caminho"
    )
    assert "merge-base" not in passos, (
        "a ancestralidade se mede num lugar só: dentro da vacina, onde ela "
        "tem teste sem rede"
    )


def test_o_veredito_da_vacina_e_CAPTURADO_e_nao_perdido_num_pipe(job):
    """O modo de falha nº 1 desta casa (RETROSPECTIVA-FASE-D §1).

    `vacina | tee` sai 0 sempre, porque o exit de um pipeline é o do ÚLTIMO
    comando: ler dali faria toda vacina parecer bem-sucedida, e a issue — que é
    o sinal inteiro — nunca nasceria.

    E a captura é `|| CODIGO=$?`, nunca `set +e`/`|| true`: a diferença é entre
    a falha virar um VALOR que alguém lê e a falha virar silêncio. Os dois
    últimos são proibidos em workflow por
    `test_contract_freeze.py::test_workflows_nao_escondem_erro`.
    """
    curar = next(p for p in job["steps"] if p.get("id") == "vacina")["run"]
    # Só o que EXECUTA: o comentário do passo explica os padrões proibidos e
    # naturalmente os cita — é o mesmo cuidado que o guarda de
    # `test_contract_freeze.py` toma ao pular linhas iniciadas por `#`.
    codigo = "\n".join(
        ln for ln in curar.splitlines() if not ln.lstrip().startswith("#")
    )
    assert "|| CODIGO=$?" in codigo
    assert "| tee" not in codigo, "o `$?` seria o do tee, que sai 0 sempre"
    assert "set +e" not in codigo and "|| true" not in codigo


def test_a_falta_de_cura_vira_ISSUE_no_desenho_do_alarme_main(job):
    """Reusar o alarme que existe, não inventar o segundo (pedido do despacho).

    E a issue nasce SÓ quando não houve cura: uma issue por cadeira musical,
    num repositório com ~100 entregas por dia, é o alarme que se aprende a
    ignorar — e aí ele para de servir para o caso em que importa.
    """
    passo = next(p for p in job["steps"] if "issue" in str(p.get("name", "")).lower())
    assert passo["if"] == "steps.vacina.outputs.alarmar == 'true'", (
        "a issue precisa nascer da resposta a 'isto acorda alguém?', que é uma "
        "pergunta DIFERENTE do veredito desde a TAR-041 — com o `failure` no "
        "gatilho, `codigo != 0` passou a incluir o defeito de código, que já "
        f"está vermelho e já tem dono (veio: {passo.get('if')})"
    )
    corpo = str(passo["run"])
    assert "gh issue list" in corpo and "--state open" in corpo, (
        "empilhar uma issue por cancelamento é o alarme que se aprende a "
        "ignorar; o `alarme-main` comenta na que já está aberta"
    )
    assert "gh issue create" in corpo and "gh issue comment" in corpo
    assert "gh label create" in corpo, "issue sem label não se acha depois"


def test_o_job_NAO_reprova_quando_nao_conseguiu_curar(job):
    """armadilhas/180 com o alvo trocado: aqui o conserto É o deploy.

    A vacina roda no MESMO `head_sha` do deploy doente e pede um rerun DAQUELE
    deploy. Vermelha, ela seria barrada por `vermelhos_nao_previstos` — o único
    caso em que isso aconteceria é justamente aquele em que ela já falhou.
    """
    curar = next(p for p in job["steps"] if p.get("id") == "vacina")["run"]
    assert "|| CODIGO=$?" in curar, (
        "o `run:` do GitHub roda com `bash -e`: sem TRATAR a falha, a saída 1 "
        "da vacina (PAROU por regra, que é um veredito legítimo) derrubaria o "
        "passo — e o job vermelho barraria o rerun que a própria vacina pediu"
    )
    assert "continue-on-error" not in str(job), (
        "`continue-on-error` esconderia também a falha que NÃO é veredito — "
        "é o falso-verde da armadilhas/211; aqui o exit é lido, não ignorado"
    )


def test_tem_as_permissoes_que_a_cura_e_o_sinal_exigem(job):
    """Permissão que falta não avisa: ela vira 403 no meio, uma vez só.

    O `alarme-main` viveu meses com a cura automática quebrada por exatamente
    isto — `contents: read` onde precisava de `write` —, e ninguém sabia.
    """
    permissoes = job["permissions"]
    assert permissoes.get("actions") == "write", "sem isto, `gh run rerun` é 403"
    assert permissoes.get("issues") == "write", "sem isto, o sinal não nasce"
    assert permissoes.get("contents") == "read"


def test_o_checkout_e_FUNDO_porque_a_decisao_e_ancestralidade(job):
    """Clone raso faz `git merge-base` responder 128 — "não consegui medir".

    A vacina então devolve ERROR (correto e fail-closed) e a cura vira uma
    issue inútil sobre um caso que era decidível (armadilhas/159).
    """
    checkout = next(p for p in job["steps"] if "checkout" in str(p.get("uses", "")))
    assert checkout["with"]["fetch-depth"] == 0


def test_o_portao_de_deploy_conhece_esta_vacina():
    """A ponta solta que faria tudo isto se voltar contra si (armadilhas/180).

    O par de testes de comportamento vive em `test_portao_de_deploy.py`; este
    aqui é o que amarra os dois arquivos, para que apagar a declaração lá
    reprove também de quem depende dela.
    """
    import portao_de_deploy as pd

    assert pd.VACINA_DO_DEPLOY == ".github/workflows/vacina-do-deploy.yml"
    assert ARQUIVO.exists()


# ---------------------------------------------------------------------------
# O CANAL DO `alarmar` — TAR-041. Três testes, e cada um fecha um jeito medido
# de esta separação virar decoração.
# ---------------------------------------------------------------------------
def test_quem_escreve_o_alarmar_e_a_TABELA_e_nao_o_YAML(job):
    """A lei anti-duplicação aplicada de novo, agora à pergunta do alarme.

    Se o YAML decidisse por conta própria quando alarmar — por `grep` na saída,
    por lista de códigos, por qualquer coisa —, existiriam DUAS regras sobre o
    mesmo assunto e um dia elas discordariam, sem que nada acusasse. Quem
    responde é `Decisao.precisa_de_alarme`, onde o motivo mora colado ao
    desfecho e é testável sem rede.
    """
    import rerun_de_deploy as vacina

    assert hasattr(vacina.Decisao("nada", 0, "x"), "precisa_de_alarme")
    assert vacina.Decisao("parar", 1, "x").precisa_de_alarme is True, (
        "o padrão tem de ser ALARMAR: ramo novo nasce barulhento, e o silêncio "
        "se escreve à mão com o motivo do lado"
    )
    codigo = next(
        str(p["run"]) for p in job["steps"] if p.get("id") == "vacina"
    )
    assert "grep -q '^codigo='" in codigo, (
        "a rede que cobre o script morrendo antes de escrever a saída dele"
    )


def test_ha_uma_REDE_para_o_caso_de_a_vacina_morrer_sem_escrever(job):
    """Se o processo morrer antes do `$GITHUB_OUTPUT`, o passo do sinal ficaria
    sem `alarmar` — e um `if` sobre variável ausente é sempre falso. Ou seja: a
    vacina morrer viraria SILÊNCIO, que é o desfecho que este arquivo inteiro
    existe para impedir."""
    codigo = next(str(p["run"]) for p in job["steps"] if p.get("id") == "vacina")
    assert "alarmar=" in codigo
    assert "codigo do processo" in codigo or "código do processo" in codigo


def test_a_issue_DIZ_qual_das_duas_doencas_foi(job):
    """Chamar de "cancelado" um run que RODOU e morreu no SSH manda quem abre a
    issue procurar a cadeira musical em vez do timeout de rede (TAR-041)."""
    passo = next(p for p in job["steps"] if "issue" in str(p.get("name", "")).lower())
    corpo = str(passo["run"])
    assert "CONCLUSAO" in str(passo.get("env", {})) or "CONCLUSAO" in corpo
    assert "CANCELADO" in corpo and "FALHOU" in corpo, (
        "as duas manchetes precisam existir; uma só serviria para os dois "
        "casos — e serviu, com o merge fora do ar como consequência (188)"
    )
    assert "armadilhas/127" in corpo, (
        "o vermelho por timeout precisa apontar a entrada que o explica"
    )


def test_o_SEGUNDO_BRACO_viaja_ate_o_script(job):
    """A escada no Python não vale nada se o YAML entregar um degrau só.

    Em 30/08/2026, às 23:20, a vacina decidiu REPETIR certo e não alcançou
    nada: `GH_TOKEN: ${{ secrets.PISTA_TOKEN || github.token }}` faz o PAT
    sombrear o `github.token`, e o PAT é o único dos dois que não pode
    redisparar run — coisa que o `pouso.yml` já declarava desde o dia anterior.
    O `actions: write` do job estava concedido o tempo todo.

    Medido em 02/09/2026, três casos isolados, veredito lido do `run_attempt`
    por fora: PAT+write recusa · github.token+write redispara · github.token+read
    recusa. Sem esta linha no YAML, `pedir_o_rerun` vê um braço só e a TAR-051
    volta a ser um comentário bonito (Classe 2 da retrospectiva).
    """
    passo = next(p for p in job["steps"] if p.get("id") == "vacina")
    reserva = str(passo["env"].get("GH_TOKEN_RESERVA", ""))
    assert "github.token" in reserva, (
        "o segundo braço tem de ser o `github.token` do próprio job — é o "
        f"único medido capaz de `gh run rerun` aqui; veio: {reserva!r}"
    )
    assert "PISTA_TOKEN" not in reserva, (
        "a reserva não pode ser o mesmo PAT do principal: seria repetir a "
        "tentativa que já foi recusada em produção e chamar isso de plano B"
    )


def test_a_escada_de_bracos_EXISTE_do_lado_de_ca(job):
    """O YAML entrega dois tokens; alguém tem de descer a escada com eles.

    Guarda em par com a de cima: um `GH_TOKEN_RESERVA` que nenhum código lê é
    exatamente a garantia sem mecanismo que esta casa mede há semanas.
    """
    import rerun_de_deploy as vacina

    assert hasattr(vacina, "pedir_o_rerun"), (
        "sumiu `pedir_o_rerun`: o rerun voltou a ser uma tentativa única, e a "
        "reserva no YAML virou enfeite"
    )
    bracos = vacina.bracos_do_rerun(
        {"GH_TOKEN": "pat", "GH_TOKEN_RESERVA": "do-job"}
    )
    assert [t for _, t in bracos] == ["pat", "do-job"]
