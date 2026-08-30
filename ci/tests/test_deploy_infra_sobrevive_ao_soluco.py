"""Guardas da vacina da `armadilhas/127` DENTRO do `deploy-infra` (TAR-024).

Contra a `main` de 30/08/2026 — antes desta entrega — o job `sincronizar` tinha
**3 passos**: um SCP, um SSH e o checkout. Medido, e não estimado: 0 passos
medindo a porta 22, 0 passos lendo o veredito da sonda, 0 pausas, 1 tentativa
de rede. O soluço de rede que a `armadilhas/127` descreve (seis quedas em três
dias, com a VPS viva e o site em 200) matava a publicação da infraestrutura no
primeiro engasgo, sem chance nenhuma de recuperação.

O que estes guardas protegem, e por que cada um existe:

- **A medição é UMA só no repositório.** A pergunta "a VPS está alcançável
  daqui?" é respondida por `ci/sonda_da_vps.py`, importada e não reescrita.
  Duas implementações poderiam discordar sobre o mesmo fato, e aí nenhuma das
  duas serviria para decidir nada.
- **A unidade de repetição é o PAR (SCP + SSH), nunca o SSH sozinho.** O
  script na VPS consome a área de staging (`rmdir infra.new`); um segundo SSH
  sem um SCP antes morreria no primeiro `ls infra.new`.
- **Repetir o par só é seguro porque o staging é limpo** — `rm: true` num
  `target` que é a área de staging, nunca um caminho em uso. Se alguém tirar o
  `rm`, restos de uma tentativa interrompida passam a contaminar a seguinte; se
  alguém apontar o `target` para `/opt/plataforma`, o `rm` apaga a produção.
- **E a repetição só acontece quando a VPS não executou UMA LINHA.** É a
  diferença de desenho em relação ao `deploy-celula`, e a razão de ela existir
  é que o script daqui troca arquivos em uso e data um backup: repetir depois
  de ele ter começado dataria um backup do estado meio-trocado. A marca
  `SINCRONIZACAO-INICIADA:` é quem separa os dois mundos.
- **Verde sem ter trocado nada continua sendo o pior verde.** As duas
  primeiras tentativas são `continue-on-error` (senão não haveria repetição), e
  sem um portão de conclusão um script que reprovou na 1ª deixaria o job verde.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

CI = Path(__file__).resolve().parents[1]
RAIZ = CI.parent
if str(CI) not in sys.path:
    sys.path.insert(0, str(CI))

DEPLOY = RAIZ / ".github" / "workflows" / "deploy-infra.yml"
SCRIPT_DA_VPS = RAIZ / "infra" / "sincronizar-infra-na-vps.sh"

# As duas marcas, com a grafia literal. Elas moram aqui, e não em módulo de
# produção, porque o único lugar que precisa saber que as três cópias batem é
# este guarda — e um guarda que lesse a régua do próprio objeto medido não
# mediria nada (`armadilhas/129`).
MARCA_DE_PARTIDA = "SINCRONIZACAO-INICIADA:"
MARCA_DE_CONCLUSAO = "SINCRONIZACAO-CONCLUIDA:"

# A sonda mora num arquivo só. Qualquer outra forma de perguntar "a porta 22
# responde?" dentro deste workflow é uma segunda implementação.
A_UNICA_SONDA = "ci/sonda_da_vps.py --sondar-porta"
OUTRAS_FORMAS_DE_MEDIR = ("/dev/tcp/", "nc -z", "nmap", "ssh -o ConnectTimeout")


def _passos() -> list[dict]:
    fluxo = yaml.safe_load(DEPLOY.read_text(encoding="utf-8"))
    return fluxo["jobs"]["sincronizar"]["steps"]


def _por_acao(fragmento: str) -> list[dict]:
    return [p for p in _passos() if fragmento in str(p.get("uses", ""))]


def _envios() -> list[dict]:
    return _por_acao("scp-action")


def _aplicacoes() -> list[dict]:
    return _por_acao("ssh-action")


def _sondas() -> list[dict]:
    return [p for p in _passos() if A_UNICA_SONDA in str(p.get("run", ""))]


# ------------------------------------------------------- medir a porta 22 --


def test_o_deploy_infra_mede_a_porta_22_sozinho():
    """A primeira ordem da `armadilhas/127`, que aqui não existia.

    Sem estes passos o retry repetiria às cegas: trataria a `armadilhas/017`
    (falha PERMANENTE de alcance) como se fosse o soluço intermitente da 127,
    gastaria 105 s de pausa e seis conexões, e terminaria sem saber qual das
    duas doenças mordeu.
    """
    sondas = _sondas()
    assert len(sondas) >= 3, (
        f"o deploy-infra mede a porta 22 em {len(sondas)} passos — esperava a "
        "medição de partida e uma depois de cada recusa"
    )


def test_a_medicao_e_a_MESMA_do_deploy_celula_e_nao_uma_segunda():
    """Lei anti-duplicação: "a VPS está alcançável?" tem UMA resposta.

    Foi este o cuidado que a TAR-013 tomou ao fazer o `ci/rerun_de_deploy.py`
    importar `ci/sonda_da_vps.py` em vez de copiá-la. Duas medições que possam
    discordar sobre o mesmo fato não servem para decidir nada — e a que decide
    aqui é a que interrompe uma entrega.
    """
    corpo = DEPLOY.read_text(encoding="utf-8")
    for forma in OUTRAS_FORMAS_DE_MEDIR:
        assert forma not in corpo, (
            f"o workflow passou a medir a porta 22 por conta própria ({forma!r}) "
            "— a medição é de ci/sonda_da_vps.py, e só dela"
        )


def test_a_sonda_nunca_pode_derrubar_a_sincronizacao():
    """Vacina, não arma: ela mede e informa; quem reprova são as tentativas."""
    for passo in _sondas():
        assert passo.get("continue-on-error") is True, (
            f"{passo.get('name')}: sem continue-on-error, um defeito da própria "
            "sonda passa a reprovar sincronizações que iriam dar certo"
        )


def test_a_sonda_recebe_o_host_por_env_e_nunca_por_argumento():
    """`VPS_HOST` é segredo: argumento aparece na tabela de processos."""
    for passo in _sondas():
        assert "VPS_HOST" in (passo.get("env") or {}), (
            f"{passo.get('name')}: o host precisa chegar por env"
        )
        assert "secrets.VPS_HOST" not in str(passo.get("run", "")), (
            f"{passo.get('name')}: o host não pode viajar na linha de comando"
        )


def test_so_a_medicao_de_partida_se_declara_partida():
    """As medições de recusa NÃO podem herdar o texto neutro da partida.

    Marcar todas como `MOMENTO: partida` faria o run parar de dizer "repetir é
    exatamente o certo" no único momento em que essa frase é a conclusão.
    """
    partidas = [p for p in _sondas() if (p.get("env") or {}).get("MOMENTO") == "partida"]
    assert len(partidas) == 1, (
        f"esperava exatamente uma medição de linha de base, achei {len(partidas)}"
    )
    assert not partidas[0].get("if"), (
        "a medição de partida é a única que roda SEMPRE — condicioná-la faria a "
        "sincronização saudável deixar de registrar qualquer medição"
    )


# ----------------------------------------------------- repetir com pausa --


def test_a_sincronizacao_e_tentada_tres_vezes():
    """A segunda ordem da `armadilhas/127`. Antes desta entrega era UMA."""
    assert len(_envios()) == 3, f"envios (SCP) para a VPS: {len(_envios())}, esperava 3"
    assert len(_aplicacoes()) == 3, (
        f"aplicações (SSH) na VPS: {len(_aplicacoes())}, esperava 3"
    )


def test_a_unidade_de_repeticao_e_o_par_scp_mais_ssh():
    """Repetir o SSH sozinho é impossível, e o guarda precisa saber disso.

    O script na VPS consome a área de staging (termina o bloco 0 com
    `rmdir infra.new`). Um SSH repetido sem um SCP antes morreria no primeiro
    `ls infra.new` — por isso cada aplicação é condicionada ao envio da SUA
    tentativa, e não à aplicação anterior.
    """
    passos = _passos()
    ordem = [
        p.get("id")
        for p in passos
        if "scp-action" in str(p.get("uses", "")) or "ssh-action" in str(p.get("uses", ""))
    ]
    assert ordem == ["enviar1", "aplicar1", "enviar2", "aplicar2", "enviar3", "aplicar3"], (
        f"a ordem dos passos de rede mudou: {ordem} — cada tentativa é um PAR "
        "envio→aplicação, nessa ordem"
    )
    for indice, aplicacao in enumerate(_aplicacoes(), start=1):
        condicao = str(aplicacao.get("if", ""))
        assert f"steps.enviar{indice}.outcome == 'success'" in condicao, (
            f"a {indice}ª aplicação não espera o envio da própria tentativa — "
            f"if={condicao!r}. Sem o envio, o staging não existe."
        )


def test_o_staging_e_limpo_a_cada_tentativa_e_nunca_e_um_caminho_em_uso():
    """A razão pela qual repetir o par é seguro — e ela é frágil de propósito.

    `rm: true` na `appleboy/scp-action` é, na documentação da própria ação,
    "Remove target directory before upload": toda tentativa recomeça de um
    staging vazio. Isso só é inofensivo enquanto o `target` for a área de
    staging. Apontá-lo para `/opt/plataforma` com o `rm` ligado apagaria a
    produção — e tirá-lo faria restos de uma tentativa interrompida
    contaminarem a seguinte.
    """
    for envio in _envios():
        com = envio.get("with") or {}
        alvo = str(com.get("target", ""))
        assert alvo.endswith("infra.new"), (
            f"{envio.get('name')}: o destino do SCP é {alvo!r}. Com `rm: true`, "
            "ele PRECISA ser a área de staging — nunca um caminho em uso."
        )
        assert com.get("rm") is True, (
            f"{envio.get('name')}: sem `rm: true` o staging acumula restos de "
            "uma tentativa interrompida, e a repetição deixa de ser segura"
        )


def test_nenhuma_copia_para_a_vps_menciona_env():
    """INV-P8: os .env reais são segredos escritos à mão pelo mantenedor."""
    for envio in _envios():
        origem = str((envio.get("with") or {}).get("source", ""))
        assert "env/" not in origem, (
            f"{envio.get('name')}: `env/` entrou na lista de cópia — {origem!r}"
        )


def test_ha_pausa_entre_as_tentativas():
    """Conselho medido, não superstição: em 26/08/2026 duas tentativas
    emendadas falharam e a terceira, depois de ~1 minuto, passou."""
    pausas = [
        str(p.get("run", ""))
        for p in _passos()
        if "sleep" in str(p.get("run", "")) and "SINCRONIZACAO" not in str(p.get("run", ""))
    ]
    assert len(pausas) == 2, f"pausas entre tentativas: {len(pausas)}, esperava 2"
    assert any("sleep 45" in p for p in pausas), "a pausa de 45s sumiu"
    assert any("sleep 60" in p for p in pausas), "a pausa de 60s sumiu"


def test_a_repeticao_so_acontece_quando_a_VPS_NAO_EXECUTOU_NADA():
    """O guarda mais importante deste arquivo — a diferença para o deploy-celula.

    Lá o script é trivialmente idempotente (`pull` + `up -d`), e por isso ele
    repete diante de qualquer falha. Aqui o script troca arquivos EM USO e data
    um backup: uma repetição cega depois de ele ter começado dataria um backup
    novo do estado já meio-trocado, e o caminho de volta impresso no bloco 4
    passaria a apontar para um estado misto.

    Quem fecha essa porta é a marca de partida: sem ela na saída capturada,
    está PROVADO que a VPS não executou uma linha, e repetir é tão seguro
    quanto o primeiro envio. Se alguém trocar esta condição por
    `outcome == 'failure'`, a segurança vira argumento outra vez.
    """
    repeticoes = [
        p
        for p in _passos()
        if p.get("id") in {"sonda1", "enviar2", "sonda2", "enviar3"}
        or "Esperar" in str(p.get("name", ""))
    ]
    assert repeticoes, "não achei os passos que decidem repetir"
    for passo in repeticoes:
        condicao = str(passo.get("if", ""))
        assert MARCA_DE_PARTIDA in condicao, (
            f"{passo.get('name')}: repete sem provar que a VPS não executou "
            f"nada — if={condicao!r}"
        )
        assert "outcome == 'failure'" not in condicao, (
            f"{passo.get('name')}: voltou a repetir por 'falhou', que inclui o "
            "script que rodou e reprovou"
        )


def test_a_saida_da_aplicacao_e_capturada_senao_nada_disso_e_mensuravel():
    """Toda a regra acima se lê da saída capturada. Sem ela, o `if` fica cego —
    e cego, ele repetiria SEMPRE (a marca nunca apareceria)."""
    for aplicacao in _aplicacoes():
        assert (aplicacao.get("with") or {}).get("capture_stdout") is True, (
            f"{aplicacao.get('name')}: sem `capture_stdout`, a marca de partida "
            "nunca chega ao workflow e a repetição volta a ser cega"
        )


def test_as_duas_primeiras_tentativas_nao_derrubam_o_job_e_a_ultima_derruba():
    """Sem `continue-on-error` nas duas primeiras não existe repetição; com ele
    na última, um vermelho real viraria verde."""
    aplicacoes = _aplicacoes()
    for indice, aplicacao in enumerate(aplicacoes[:2], start=1):
        assert aplicacao.get("continue-on-error") is True, (
            f"a {indice}ª aplicação derruba o job — não haveria 2ª nem 3ª tentativa"
        )
    assert not aplicacoes[2].get("continue-on-error"), (
        "a 3ª aplicação é a que decide: com continue-on-error ela deixaria de decidir"
    )
    assert not _envios()[2].get("continue-on-error"), (
        "o 3º envio é a última chance de o material chegar; ele precisa reprovar"
    )


# --------------------------------------------------- a parada antecipada --


def _passo_de_parada() -> dict:
    parada = [p for p in _passos() if "outputs.veredito" in str(p.get("if", ""))]
    assert parada, (
        "nenhum passo do deploy-infra lê o veredito da sonda — a medição "
        "existiria sem decidir nada, que é o mesmo que não medir"
    )
    return parada[0]


def test_a_parada_antecipada_exige_DUAS_medicoes():
    """Uma medição isolada pode ser defeito da sonda; duas são evidência."""
    condicao = str(_passo_de_parada().get("if", ""))
    assert condicao.count("== 'permanente'") >= 2, (
        "a parada antecipada passou a se contentar com UMA medição de porta morta"
    )
    assert "sonda1" in condicao and "sonda2" in condicao


def test_a_parada_le_o_veredito_e_nunca_o_outcome():
    """[INV-CI01] em uma linha de YAML: `outcome` juntaria "a porta está morta"
    com "não consegui medir", e a segunda passaria a abortar entregas sãs."""
    condicao = str(_passo_de_parada().get("if", ""))
    assert "outputs.veredito" in condicao
    for id_da_sonda in ("sonda1", "sonda2"):
        assert f"steps.{id_da_sonda}.outcome" not in condicao


def test_a_parada_antecipada_reprova_de_verdade():
    """Ela existe para PARAR, não para avisar."""
    parada = _passo_de_parada()
    assert "exit 1" in str(parada.get("run", ""))
    assert not parada.get("continue-on-error")


# ------------------------------------------- verde só com trabalho feito --


def _portao_de_conclusao() -> dict:
    portoes = [
        p
        for p in _passos()
        if MARCA_DE_CONCLUSAO in str(p.get("run", "")) and "exit 1" in str(p.get("run", ""))
    ]
    assert portoes, (
        "nada exige a marca de conclusão: com as duas primeiras tentativas em "
        "continue-on-error, um script que reprovou na 1ª deixaria o job VERDE"
    )
    return portoes[0]


def test_conectar_sem_trocar_nada_nao_e_sucesso():
    """A trava que o deploy-celula ganhou a custo em 28/08/2026, aqui.

    Lá o parâmetro estava com o nome errado: a ação avisou "Unexpected input",
    ignorou o script, abriu a conexão, não executou nada e saiu com sucesso.
    Aqui o risco é outro e maior, porque a repetição exigiu `continue-on-error`
    nas duas primeiras tentativas.
    """
    portao = _portao_de_conclusao()
    assert "cancelled()" in str(portao.get("if", "")), (
        "o portão de conclusão precisa rodar também quando a entrega falhou — e "
        "NÃO quando o run foi cancelado sem rodar nada (armadilhas/173 e /188)"
    )
    assert not portao.get("continue-on-error")


def test_o_portao_separa_nao_comecou_de_comecou_e_parou_no_meio():
    """Duas falhas diferentes, dois encaminhamentos diferentes.

    "A VPS não atendeu" manda para a medição da porta 22; "o script começou e
    parou" manda para o log e para o backup datado. Dar a mesma mensagem às
    duas faria o leitor procurar rede quando o problema era o compose.
    """
    corpo = str(_portao_de_conclusao().get("run", ""))
    assert MARCA_DE_PARTIDA in corpo, (
        "o portão não distingue 'não começou' de 'começou e parou no meio'"
    )


def test_as_sentinelas_sao_as_mesmas_no_script_e_no_workflow():
    """O script imprime, o workflow exige. Duas grafias fariam o portão contar
    uma história e o script outra sobre a MESMA sincronização."""
    do_script = SCRIPT_DA_VPS.read_text(encoding="utf-8")
    do_workflow = DEPLOY.read_text(encoding="utf-8")
    for marca in (MARCA_DE_PARTIDA, MARCA_DE_CONCLUSAO):
        assert marca in do_script, f"{marca} não é impressa pelo script da VPS"
        assert marca in do_workflow, f"{marca} não é exigida pelo workflow"


def test_o_script_da_vps_mora_num_arquivo_e_nao_dentro_do_yaml():
    """Três tentativas com o script embutido seriam três cópias de ~120 linhas
    de shell — a duplicação que esta casa proíbe, e a mesma razão que tirou o
    script da célula do YAML em 28/08/2026."""
    assert SCRIPT_DA_VPS.exists(), f"{SCRIPT_DA_VPS} não existe"
    for aplicacao in _aplicacoes():
        com = aplicacao.get("with") or {}
        assert "script" not in com, (
            f"{aplicacao.get('name')}: script embutido no YAML voltou — com três "
            "tentativas isso são três cópias que podem divergir"
        )
        assert com.get("script_path") == "infra/sincronizar-infra-na-vps.sh", (
            f"{aplicacao.get('name')}: script_path={com.get('script_path')!r}. O "
            "nome errado do parâmetro já deixou um deploy verde sem fazer nada "
            "(28/08/2026) — aqui ele é conferido."
        )


def test_o_workflow_dispara_quando_o_script_da_vps_muda():
    """O script agora É o que a produção executa. Se ele mudasse sem disparar o
    deploy, a mudança ficaria só no Git — que é o H11 voltando."""
    fluxo = yaml.safe_load(DEPLOY.read_text(encoding="utf-8"))
    # `on` vira True no YAML 1.1 (é a palavra reservada de booleano).
    gatilhos = fluxo.get("on") or fluxo.get(True)
    caminhos = gatilhos["push"]["paths"]
    assert "infra/sincronizar-infra-na-vps.sh" in caminhos, (
        f"o script da VPS não dispara o deploy-infra — paths={caminhos}"
    )


def test_o_deploy_infra_registra_no_resumo_do_run_o_que_fez():
    """A terceira ordem da `armadilhas/127`: registrar.

    Sem isto, uma sincronização salva na 2ª tentativa é indistinguível de uma
    que passou de primeira para quem abre a execução — e o padrão da VPS
    recusando fica invisível justamente nos dias em que ela mais mordeu.
    """
    narradores = [
        p for p in _passos() if "GITHUB_STEP_SUMMARY" in str(p.get("run", ""))
    ]
    assert narradores, "o deploy-infra não registra o que fez"
    narrador = narradores[0]
    assert "cancelled()" in str(narrador.get("if", "")), (
        "o narrador precisa rodar também quando a entrega falhou — é aí que a "
        "história importa"
    )
    for variavel in ("E1", "E2", "E3", "A1", "A2", "A3"):
        assert variavel in (narrador.get("env") or {}), (
            f"sem {variavel} o resumo não sabe contar quantas tentativas foram precisas"
        )
    assert "exit 1" not in str(narrador.get("run", "")), (
        "o narrador não é portão: se ele pudesse reprovar, 'não consegui contar "
        "a história' viraria 'a entrega falhou'"
    )
