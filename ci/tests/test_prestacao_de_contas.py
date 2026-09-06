"""Guardas da prestação de contas (ci/prestacao_de_contas.py).

Contrato do hook: exit 0 permite e CALA · exit 2 RECUSA o fim do turno com o
molde no stderr · exit 1 é "não consegui medir", barulhento e sem bloquear.

Tudo aqui roda o hook como PROCESSO, com JSON no stdin — nunca chamando as
funções por dentro. É a exigência da `armadilhas/176`: um hook fail-open que
quebra ao FALAR fica silencioso, e silêncio é o que um hook correto produz na
maior parte do tempo. Os dois estados só se distinguem de fora, e só assim se
pega a `armadilhas/003` (emoji e acento num console cp1252).

O par de cada prova está aqui de propósito: um portão que RECUSASSE sempre
passaria em todos os testes vermelhos e seria arrancado na primeira urgência.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

RAIZ_DO_REPO = Path(__file__).resolve().parents[2]
PORTAO = RAIZ_DO_REPO / "ci" / "prestacao_de_contas.py"
FIACAO = RAIZ_DO_REPO / ".claude" / "settings.json"

sys.path.insert(0, str(RAIZ_DO_REPO / "ci"))
import telemetria  # noqa: E402

CONTAS_COMPLETAS = """Terminei.

- [x] achar o evento repetido no webhook
- [x] ignorá-lo, com teste vermelho→verde
Onde estou: passo 2 de 2, acabou.

**O que mudou** — o webhook do Pix passou a ignorar evento repetido.

**O que foi verificado e como** — `pytest services/pagamentos` → 41 passed.

**O que foi cortado e por quê** — nada.

**O que eu preciso decidir** — nada depende de ninguém, ~8 min até o ar.

**Auditoria de qualidade** — Definição de Pronto 7/7. O crítico atacaria o
retry do provedor, que não tem teste de ponta a ponta.

**Veredito:** PRONTO — o guarda nasceu vermelho e ficou verde com o fix.
"""


# ------------------------------------------------------------- montagem ----


def _humano(texto: str) -> dict:
    return {"type": "user", "origin": {"kind": "human"},
            "message": {"role": "user", "content": texto}}


def _notificacao(evento: str) -> dict:
    return {"type": "user", "origin": {"kind": "task-notification"},
            "message": {"role": "user",
                        "content": f"<task-notification>\n<event>{evento}</event>\n</task-notification>"}}


def _fala(texto: str) -> dict:
    return {"type": "assistant",
            "message": {"role": "assistant", "content": [{"type": "text", "text": texto}]}}


def _ferramenta(nome: str, entrada: dict) -> dict:
    return {"type": "assistant",
            "message": {"role": "assistant",
                        "content": [{"type": "tool_use", "name": nome, "input": entrada}]}}


def _decidir(tmp_path: Path, entradas: list[dict], **extra) -> subprocess.CompletedProcess:
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in entradas),
        encoding="utf-8",
    )
    carga = {"transcript_path": str(transcript), "stop_hook_active": False, **extra}
    return _rodar(["--contas"], carga)


def _rodar(argumentos: list[str], carga: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(PORTAO), *argumentos],
        input=json.dumps(carga, ensure_ascii=False),
        capture_output=True, text=True, timeout=60,
        encoding="utf-8", errors="replace",
    )


def _recusa_que_ensina(proc: subprocess.CompletedProcess) -> None:
    assert proc.returncode == 2, (proc.returncode, proc.stdout, proc.stderr)
    # A recusa tem de ENTREGAR o molde: recusa que não ensina só trava o robô
    # de outro jeito. E o emoji/acento provam que a fala não morreu no cp1252.
    assert "🧾 PRESTAÇÃO DE CONTAS" in proc.stderr
    for titulo, _ in (("**O que mudou**", 0), ("**O que foi verificado e como**", 0),
                      ("**O que foi cortado e por quê**", 0),
                      ("**O que eu preciso decidir**", 0),
                      ("**Auditoria de qualidade**", 0)):
        assert titulo in proc.stderr, f"o molde não trouxe {titulo}"
    assert "PRONTO" in proc.stderr
    # E o roteiro que ele pediu em 05/09/2026: a recusa tem de ensinar a caixinha.
    assert "- [x]" in proc.stderr and "Onde estou" in proc.stderr


def _silencio(proc: subprocess.CompletedProcess) -> None:
    assert proc.returncode == 0, (proc.returncode, proc.stdout, proc.stderr)
    assert proc.stderr.strip() == "", proc.stderr


# ------------------------------------------- o caso que motivou o portão ----


def test_turno_que_editou_arquivo_e_calou_e_recusado(tmp_path):
    proc = _decidir(tmp_path, [
        _humano("conserte o webhook"),
        _ferramenta("Edit", {"file_path": "services/pagamentos/webhook.py"}),
        _fala("Pronto."),
    ])
    _recusa_que_ensina(proc)
    assert "webhook.py" in proc.stderr, "a recusa não diz o que mudou o mundo"


def test_o_mesmo_turno_com_as_contas_passa_calado(tmp_path):
    _silencio(_decidir(tmp_path, [
        _humano("conserte o webhook"),
        _ferramenta("Edit", {"file_path": "services/pagamentos/webhook.py"}),
        _fala(CONTAS_COMPLETAS),
    ]))


def test_turno_que_so_leu_passa_calado(tmp_path):
    _silencio(_decidir(tmp_path, [
        _humano("como está o deploy?"),
        _ferramenta("Bash", {"command": "gh run view 42 --json status,conclusion"}),
        _fala("Verde, concluído às 14h02."),
    ]))


# ----------------------------- as 225 esperas: o portão não pode gritar ----


def test_acordar_de_espera_sem_mudanca_nao_cobra_relatorio(tmp_path):
    """225 de 232 mensagens de uma sessão real eram estas. Cobrar em cada uma
    seria pior do que não cobrar nenhuma: o mantenedor aprenderia a ignorar."""
    entradas = [_humano("suba o relay")]
    for i in range(30):
        entradas += [_notificacao(f"aguardando a pista: 1072=OPEN ({i}min de 30)"),
                     _fala("Aguardando.")]
    _silencio(_decidir(tmp_path, entradas))


def test_espera_depois_de_mudanca_ja_prestada_continua_calada(tmp_path):
    entradas = [
        _humano("suba o relay"),
        _ferramenta("Edit", {"file_path": "infra/docker-compose.yml"}),
        _fala(CONTAS_COMPLETAS),
    ]
    for i in range(10):
        entradas += [_notificacao(f"deploy {i}"), _fala("Aguardando.")]
    _silencio(_decidir(tmp_path, entradas))


def test_mudanca_depois_das_contas_cobra_de_novo(tmp_path):
    proc = _decidir(tmp_path, [
        _humano("suba o relay"),
        _ferramenta("Edit", {"file_path": "infra/docker-compose.yml"}),
        _fala(CONTAS_COMPLETAS),
        _notificacao("a pista devolveu o PR"),
        _ferramenta("Edit", {"file_path": "infra/docker-compose.yml"}),
        _fala("Consertei."),
    ])
    _recusa_que_ensina(proc)


def test_contas_antes_da_mudanca_nao_valem(tmp_path):
    """A ordem importa: relatório escrito antes de mexer não relata o que mexeu."""
    _recusa_que_ensina(_decidir(tmp_path, [
        _humano("conserte"),
        _fala(CONTAS_COMPLETAS),
        _ferramenta("Write", {"file_path": "services/forum/models.py"}),
        _fala("Feito."),
    ]))


def test_a_divida_sobrevive_a_ele_falar_outra_coisa(tmp_path):
    """ESTE TESTE JÁ AFIRMOU O CONTRÁRIO, e o contrário era o defeito.

    Ele mandou a tela: a sessão abriu o PR #1092, mergeou, e ficou esperando o
    deploy; no meio ele respondeu uma pergunta ("deixe assim: só admin pode
    ver, ler"); e daí em diante nada mais mudou no mundo. Como o portão só
    media a janela aberta pela última fala dele, a dívida do trabalho já feito
    tinha sido apagada por ELE ter digitado uma frase.

    Dívida se paga com o relatório, nunca com o devedor falando outra coisa.
    """
    _recusa_que_ensina(_decidir(tmp_path, [
        _humano("conserte o webhook"),
        _ferramenta("Edit", {"file_path": "services/pagamentos/webhook.py"}),
        _fala("Feito."),
        _humano("deixe assim: só admin pode ver, ler"),
        _fala("Combinado."),
    ]))


def test_divida_paga_nao_assombra_pergunta_nova(tmp_path):
    """O par verde: com o relatório entregue, a pergunta seguinte é livre."""
    _silencio(_decidir(tmp_path, [
        _humano("conserte o webhook"),
        _ferramenta("Edit", {"file_path": "services/pagamentos/webhook.py"}),
        _fala(CONTAS_COMPLETAS),
        _humano("e o que é uma célula?"),
        _fala("É um serviço isolado, com banco e deploy próprios."),
    ]))


# ------------------------------------------------ o que conta como mudar ----


def test_heredoc_de_bash_que_escreve_arquivo_conta(tmp_path):
    """O modo automático deste harness manda escrever arquivo por Bash. Sem
    esta regra o portão seria cego justamente no caminho mais usado."""
    _recusa_que_ensina(_decidir(tmp_path, [
        _humano("crie o script"),
        _ferramenta("Bash", {"command": "cat > ci/novo.py <<'PY'\nprint(1)\nPY"}),
        _fala("Criado."),
    ]))


def test_redirecionamento_de_ruido_de_shell_nao_conta(tmp_path):
    for comando in ("pytest ci/tests 2>&1 | tail -5",
                    "python ci/indice_de_armadilhas.py >/dev/null 2>&1",
                    "git status > $null"):
        _silencio(_decidir(tmp_path, [
            _humano("rode os testes"),
            _ferramenta("Bash", {"command": comando}),
            _fala("Verde."),
        ]))


def test_commit_e_pr_contam(tmp_path):
    for comando in ("git commit -m 'fix'", "gh pr create --base main --title x --body y",
                    "python ci/mergear.py 1072 --pousar"):
        _recusa_que_ensina(_decidir(tmp_path, [
            _humano("entregue"),
            _ferramenta("Bash", {"command": comando}),
            _fala("Feito."),
        ]))


def test_rascunho_no_scratchpad_nao_e_entrega(tmp_path):
    _silencio(_decidir(tmp_path, [
        _humano("analise os dados"),
        _ferramenta("Write", {"file_path":
                              r"C:\Users\davia\AppData\Local\Temp\claude\x\scratchpad\notas.md"}),
        _fala("A mediana é 8,4 min."),
    ]))


def test_anotar_na_propria_memoria_nao_e_tarefa(tmp_path):
    """Achado da medição contra 40 sessões reais (05/09/2026): sem esta regra,
    "lembre-se disso" virava tarefa com seis blocos de relatório."""
    memoria = r"C:\Users\davia\.claude\projects\C--Users-davia-x\memory\MEMORY.md"
    _silencio(_decidir(tmp_path, [
        _humano("lembre que a escola é 18+"),
        _ferramenta("Edit", {"file_path": memoria}),
        _fala("Anotado."),
    ]))
    _silencio(_decidir(tmp_path, [
        _humano("lembre que a escola é 18+"),
        _ferramenta("Bash", {"command": f'cat > "{memoria}" <<EOF\nx\nEOF'}),
        _fala("Anotado."),
    ]))


def test_seta_dentro_de_frase_nao_e_arquivo(tmp_path):
    """O outro falso positivo da mesma medição: um `>` no meio de um texto
    entre aspas virava "escreveu em cala'". Alvo de redirecionamento tem de
    PARECER arquivo — ponto ou separador de caminho."""
    _silencio(_decidir(tmp_path, [
        _humano("me explique"),
        _ferramenta("Bash", {"command": "echo 'o portao recusa -> e cala'"}),
        _fala("É isso."),
    ]))


def test_subagente_de_leitura_nao_conta_mas_despacho_conta(tmp_path):
    _silencio(_decidir(tmp_path, [
        _humano("onde mora o login?"),
        _ferramenta("Agent", {"subagent_type": "Explore", "prompt": "ache o login"}),
        _fala("Em services/identidade/."),
    ]))
    _recusa_que_ensina(_decidir(tmp_path, [
        _humano("faça o login"),
        _ferramenta("Agent", {"subagent_type": "despacho", "prompt": "brief"}),
        _fala("Despachado."),
    ]))


# --------------------------------------- o relatório tem de estar inteiro ----


def test_relatorio_sem_um_dos_blocos_e_recusado(tmp_path):
    for titulo in ("**O que mudou**", "**Auditoria de qualidade**",
                   "**O que eu preciso decidir**"):
        mutilado = CONTAS_COMPLETAS.replace(titulo, "**Alguma coisa**")
        _recusa_que_ensina(_decidir(tmp_path, [
            _humano("conserte"),
            _ferramenta("Edit", {"file_path": "a.py"}),
            _fala(mutilado),
        ]))


def test_relatorio_sem_veredito_e_recusado(tmp_path):
    sem_veredito = CONTAS_COMPLETAS.replace("**Veredito:** PRONTO", "Acabei")
    _recusa_que_ensina(_decidir(tmp_path, [
        _humano("conserte"),
        _ferramenta("Edit", {"file_path": "a.py"}),
        _fala(sem_veredito),
    ]))


def test_pontuacao_natural_do_relatorio_nao_barra_o_robo(tmp_path):
    """O portão reconhece o BLOCO, não decora a pontuação. Barrar
    `**O que mudou:**` por causa de dois-pontos só faria o mantenedor ler o
    mesmo relatório duas vezes na tela."""
    for variante in (
        CONTAS_COMPLETAS.replace("**O que mudou**", "**O que mudou:**"),
        CONTAS_COMPLETAS.replace("**Veredito:** PRONTO", "**Veredito** — PRONTO"),
        CONTAS_COMPLETAS.replace("**Veredito:** PRONTO", "Veredito: **PRONTO**"),
        CONTAS_COMPLETAS.replace("**Auditoria de qualidade**", "**AUDITORIA DE QUALIDADE**"),
    ):
        _silencio(_decidir(tmp_path, [
            _humano("conserte"),
            _ferramenta("Edit", {"file_path": "a.py"}),
            _fala(variante),
        ]))


def test_os_mesmos_titulos_soltos_na_prosa_nao_valem(tmp_path):
    """O par vermelho do teste acima: frouxo na pontuação, firme no bloco.
    Sem os asteriscos, um parágrafo corrido satisfaria o portão sem entregar
    relatório nenhum."""
    prosa = ("Fiz o conserto. O que mudou foi o webhook, o que foi verificado e como "
             "está nos testes, o que foi cortado e por quê: nada, o que eu preciso "
             "decidir: nada, auditoria de qualidade ok. Veredito: PRONTO.")
    _recusa_que_ensina(_decidir(tmp_path, [
        _humano("conserte"),
        _ferramenta("Edit", {"file_path": "a.py"}),
        _fala(prosa),
    ]))


def test_relatorio_sem_o_checklist_e_recusado(tmp_path):
    """Pedido dele em 05/09/2026: "toda e cada tarefa mostre um checklist e um
    roadmap claro de onde está e o que ainda precisa ser feito". Os seis blocos
    sem a caixinha eram o relatório de antes, e ele não dizia onde a tarefa
    parou. Este teste nasceu VERMELHO contra o portão anterior."""
    sem_checklist = "\n".join(
        linha for linha in CONTAS_COMPLETAS.splitlines()
        if not linha.startswith("- [") and not linha.startswith("Onde estou")
    )
    assert "- [x]" not in sem_checklist
    _recusa_que_ensina(_decidir(tmp_path, [
        _humano("conserte"),
        _ferramenta("Edit", {"file_path": "a.py"}),
        _fala(sem_checklist),
    ]))


def test_caixinha_solta_na_prosa_nao_e_checklist(tmp_path):
    """O par vermelho: `[x]` no meio de uma frase não é linha de checklist."""
    prosa = (CONTAS_COMPLETAS
             .replace("- [x] achar o evento repetido no webhook", "achei [x] o evento")
             .replace("- [x] ignorá-lo, com teste vermelho→verde", "e ignorei [x] com teste"))
    assert not any(l.startswith("- [") for l in prosa.splitlines())
    _recusa_que_ensina(_decidir(tmp_path, [
        _humano("conserte"),
        _ferramenta("Edit", {"file_path": "a.py"}),
        _fala(prosa),
    ]))


def test_checklist_com_caixa_aberta_e_aceito(tmp_path):
    """NÃO PRONTO honesto deixa `- [ ]` na tela. Um portão que só aceitasse
    `[x]` ensinaria a marcar o que não foi feito — o contrário do roteiro."""
    honesto = CONTAS_COMPLETAS.replace(
        "- [x] achar o evento repetido no webhook",
        "- [ ] achar o evento repetido no webhook (o log de produção não chega aqui)",
    ).replace(
        "- [x] ignorá-lo, com teste vermelho→verde",
        "- [ ] ignorá-lo, com teste vermelho→verde (o teste de ponta a ponta não roda aqui)",
    ).replace("**Veredito:** PRONTO", "**Veredito:** NÃO PRONTO")
    assert "- [x]" not in honesto  # senão o teste não prova que `- [ ]` basta
    _silencio(_decidir(tmp_path, [
        _humano("conserte"),
        _ferramenta("Edit", {"file_path": "a.py"}),
        _fala(honesto),
    ]))


def test_pronto_com_caixa_aberta_e_contradicao_e_e_recusado(tmp_path):
    """O plano de abertura colado no fim, intocado, com PRONTO embaixo, satisfazia
    o portão sem o robô ter marcado nada (achado do revisor do PR #1126). Ou a
    tarefa acabou, ou sobrou passo: as duas coisas juntas não existem."""
    contraditorio = CONTAS_COMPLETAS.replace(
        "- [x] ignorá-lo, com teste vermelho→verde",
        "- [ ] ignorá-lo, com teste vermelho→verde",
    )
    assert "**Veredito:** PRONTO" in contraditorio
    _recusa_que_ensina(_decidir(tmp_path, [
        _humano("conserte"),
        _ferramenta("Edit", {"file_path": "a.py"}),
        _fala(contraditorio),
    ]))


def test_caixinha_quebrada_em_duas_linhas_nao_e_checklist(tmp_path):
    """`\\s` com re.M atravessava linha: `-` numa linha e `[x]` na outra casavam."""
    quebrado = CONTAS_COMPLETAS.replace("- [x] achar", "-\n[x] achar") \
                               .replace("- [x] ignorá-lo", "- [x]\nignorá-lo")
    _recusa_que_ensina(_decidir(tmp_path, [
        _humano("conserte"),
        _ferramenta("Edit", {"file_path": "a.py"}),
        _fala(quebrado),
    ]))


def test_veredito_nao_pronto_e_resposta_aceita(tmp_path):
    """NÃO PRONTO é honestidade, não falha. Um portão que só aceitasse PRONTO
    ensinaria o robô a mentir — que é a doença que ele existe para curar."""
    honesto = CONTAS_COMPLETAS.replace(
        "**Veredito:** PRONTO — o guarda nasceu vermelho e ficou verde com o fix.",
        "**Veredito:** NÃO PRONTO — o teste de ponta a ponta não roda nesta máquina.",
    )
    _silencio(_decidir(tmp_path, [
        _humano("conserte"),
        _ferramenta("Edit", {"file_path": "a.py"}),
        _fala(honesto),
    ]))


# ------------------------------------- nunca prender, nunca ficar mudo ----


def test_segunda_recusa_no_mesmo_fim_de_turno_nao_prende_a_sessao(tmp_path):
    proc = _rodar(["--contas"], {"transcript_path": "qualquer", "stop_hook_active": True})
    assert proc.returncode == 1, proc
    assert "cobrado e terminou assim mesmo" in proc.stderr


def test_transcript_ausente_grita_e_nao_bloqueia():
    proc = _rodar(["--contas"], {"stop_hook_active": False})
    assert proc.returncode == 1, proc
    assert "NÃO é 'está tudo certo'" in proc.stderr


def test_transcript_inexistente_grita_e_nao_bloqueia():
    proc = _rodar(["--contas"], {"transcript_path": "/caminho/que/nao/existe.jsonl"})
    assert proc.returncode == 1, proc
    assert "não encontrado" in proc.stderr


def test_json_quebrado_grita_e_nao_bloqueia():
    proc = subprocess.run(
        [sys.executable, str(PORTAO), "--contas"],
        input="{isto nao e json", capture_output=True, text=True, timeout=60,
        encoding="utf-8", errors="replace",
    )
    assert proc.returncode == 1, proc
    assert "não entendi o JSON" in proc.stderr


def test_linha_meio_escrita_no_transcript_nao_derruba_o_portao(tmp_path):
    transcript = tmp_path / "t.jsonl"
    transcript.write_text(
        json.dumps(_humano("conserte"), ensure_ascii=False) + "\n"
        + json.dumps(_ferramenta("Edit", {"file_path": "a.py"}), ensure_ascii=False) + "\n"
        + '{"type": "assist',  # o harness escrevendo enquanto o hook lê
        encoding="utf-8",
    )
    proc = _rodar(["--contas"], {"transcript_path": str(transcript)})
    assert proc.returncode == 2, proc  # a mudança continua visível; ele cobra


# ------------------------------------------------------ o plano, na entrada ----


def test_o_aviso_do_plano_sai_para_pedido_do_mantenedor():
    proc = _rodar(["--plano"], {"prompt": "conserte o login do site"})
    assert proc.returncode == 0, proc
    assert "PLANO PRIMEIRO" in proc.stdout
    assert "- [ ]" in proc.stdout
    assert "Veredito" in proc.stdout
    # A ponta do meio (05/09/2026) só tem o aviso como mecanismo: ele tem de dizê-la.
    assert "FIM DE CADA ETAPA" in proc.stdout and "Onde estou" in proc.stdout


def test_o_aviso_do_plano_cala_no_acordar_da_maquina():
    proc = _rodar(["--plano"], {"prompt": "<task-notification>\n<event>x</event>\n</task-notification>"})
    assert proc.returncode == 0, proc
    assert proc.stdout.strip() == "", proc.stdout


# ------------------------------------------------------------- a fiação ----


def _comando_da_fiacao(gancho: str, bandeira: str) -> str:
    fiacao = json.loads(FIACAO.read_text(encoding="utf-8"))
    for entrada in fiacao.get("hooks", {}).get(gancho, []):
        for h in entrada.get("hooks", []):
            comando = h.get("command", "")
            if "prestacao_de_contas" in comando and bandeira in comando:
                return comando
    raise AssertionError(f"a prestação de contas não está ligada no gancho {gancho}")


def test_o_portao_esta_ligado_nos_dois_ganchos():
    """Portão que existe em disco e não está na fiação é decoração."""
    assert _comando_da_fiacao("Stop", "--contas")
    assert _comando_da_fiacao("UserPromptSubmit", "--plano")


def _pelo_shell(comando: str, projeto: Path, carga: dict) -> subprocess.CompletedProcess:
    """Do jeito EXATO que o harness invoca: pelo shell, com CLAUDE_PROJECT_DIR."""
    import os
    ambiente = {**os.environ, "CLAUDE_PROJECT_DIR": str(projeto)}
    return subprocess.run(
        comando, shell=True, env=ambiente,
        input=json.dumps(carga, ensure_ascii=False),
        capture_output=True, text=True, timeout=60,
        encoding="utf-8", errors="replace",
    )


def test_clone_sem_o_portao_nao_prende_a_sessao(tmp_path):
    """O guarda mais importante desta suíte.

    `python arquivo_que_nao_existe.py` sai com código **2** — e 2 num gancho
    Stop é RECUSA. Um clone desatualizado (o do mantenedor estava 746 commits
    atrás quando este portão nasceu, sem sequer o `padrao_de_trabalho.py`)
    ficaria preso num laço de recusa com a mensagem "can't open file", sem
    saída e sem sentido. É por isso que a fiação não chama o script direto: ela
    passa por um `python -c` que confere o arquivo antes.

    Um portão que trava a máquina do dono é pior que o silêncio que ele veio
    curar.
    """
    vazio = tmp_path / "clone-velho"
    (vazio / "ci").mkdir(parents=True)
    for gancho, bandeira in (("Stop", "--contas"), ("UserPromptSubmit", "--plano")):
        proc = _pelo_shell(_comando_da_fiacao(gancho, bandeira), vazio, {})
        assert proc.returncode == 0, (gancho, proc.returncode, proc.stdout, proc.stderr)


def test_a_fiacao_literal_recusa_de_ponta_a_ponta(tmp_path):
    """O par verde do teste acima: com o script no lugar, a recusa acontece
    pelo caminho REAL — shell, variável de ambiente, JSON no stdin."""
    transcript = tmp_path / "t.jsonl"
    transcript.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in [
        _humano("conserte o webhook"),
        _ferramenta("Edit", {"file_path": "services/pagamentos/webhook.py"}),
        _fala("Pronto."),
    ]), encoding="utf-8")
    proc = _pelo_shell(
        _comando_da_fiacao("Stop", "--contas"), RAIZ_DO_REPO,
        {"transcript_path": str(transcript), "stop_hook_active": False},
    )
    assert proc.returncode == 2, (proc.returncode, proc.stdout, proc.stderr)
    assert "PRESTAÇÃO DE CONTAS" in proc.stderr


# ------------------------------------------------------------------------
# A tela que ele mandou, reconstruída (05/09/2026).
# A sessão abriu PR, mergeou e ficou em turnos de espera. O relatório do
# trabalho nunca saiu, e a conversa ia ser arquivada com "Aguardando." como
# última palavra.
# ------------------------------------------------------------------------

def _batimento(evento: str) -> dict:
    return {"type": "user", "origin": {"kind": "task-notification"},
            "message": {"role": "user", "content":
                        f"<task-notification><task-id>bdeploy1</task-id>"
                        f"<event>{evento}</event></task-notification>"}}


def _a_tela_que_ele_mandou() -> list[dict]:
    entradas = [
        _humano("faça o relatório de apresentação do projeto"),
        _ferramenta("Bash", {"command": "gh pr create --base main --title x --body y"}),
        _fala("PR #1092 aberto."),
    ]
    for evento in ("Sonda do merge, 18 min", "a pista atualizou o PR",
                   "Deploy em andamento", "Deploy na fila do GitHub"):
        entradas += [_batimento(evento), _fala("Aguardando.")]
    return entradas


def test_a_sessao_da_captura_dele_nao_termina_calada(tmp_path):
    proc = _decidir(tmp_path, _a_tela_que_ele_mandou())
    _recusa_que_ensina(proc)
    assert "trabalho feito nesta sessão" in proc.stderr, proc.stderr


def test_a_mesma_sessao_com_o_relatorio_passa(tmp_path):
    entradas = _a_tela_que_ele_mandou()
    entradas[-1] = _fala(CONTAS_COMPLETAS)
    _silencio(_decidir(tmp_path, entradas))


def test_a_fala_dele_no_meio_da_espera_nao_perdoa_a_divida(tmp_path):
    """O detalhe exato da tela: ele respondeu algo no meio das esperas."""
    entradas = _a_tela_que_ele_mandou()
    entradas += [_humano("deixe assim: só admin pode ver, ler"), _fala("Combinado.")]
    entradas += [_batimento("Deploy na fila"), _fala("Aguardando.")]
    _recusa_que_ensina(_decidir(tmp_path, entradas))


# ------------------------------------------- Alavanca 3: série sem despacho ----
#
# documentos/alavancas-10x-da-fabrica.md mediu que, das 60 sessões mais
# recentes, só 4 dispararam o robô `despacho` (16 vezes); as demais fizeram os
# PRs de um pedido em série, na mesma sessão. Esta contagem nasce em SOMBRA
# (Sistema Imunológico): só telemetria, nada visível, nada bloqueado — o exit
# code continua sendo só o que `decidir()` já calculava (provado no fim desta
# seção pelo caso que já tinha teste próprio, com 2 PRs sem despacho).


def _repo_encenado(tmp_path: Path) -> Path:
    casa = tmp_path / "casa"
    (casa / ".git").mkdir(parents=True)
    return casa


def _pr_criado(ferramenta: str = "Bash") -> dict:
    return _ferramenta(ferramenta, {"command": "gh pr create --base main --title x --body y"})


def _despacho() -> dict:
    return _ferramenta("Agent", {"subagent_type": "despacho", "prompt": "brief"})


def test_dois_prs_sem_despacho_gravam_a_sombra(tmp_path):
    casa = _repo_encenado(tmp_path)
    _decidir(tmp_path, [
        _humano("faça os dois PRs"),
        _pr_criado("Bash"),
        _fala("PR #1 aberto."),
        _pr_criado("PowerShell"),
        _fala(CONTAS_COMPLETAS),
    ], cwd=str(casa), session_id="sessao-serie")
    eventos = telemetria.ler_tudo(casa / ".git")
    achados = [e for e in eventos if e.get("evento") == "serie_sem_despacho"]
    assert len(achados) == 1, "a série de PRs sem despacho deveria ter sido medida"
    assert achados[0]["prs_criados"] == 2
    assert achados[0]["despachos"] == 0


def test_prs_com_despacho_nao_conta_como_serie(tmp_path):
    """O turno despachou: não é a série que a Alavanca 3 quer enxergar."""
    casa = _repo_encenado(tmp_path)
    _decidir(tmp_path, [
        _humano("faça os dois PRs"),
        _despacho(),
        _pr_criado("Bash"),
        _pr_criado("PowerShell"),
        _fala(CONTAS_COMPLETAS),
    ], cwd=str(casa), session_id="sessao-com-despacho")
    eventos = telemetria.ler_tudo(casa / ".git")
    assert not any(e.get("evento") == "serie_sem_despacho" for e in eventos)


def test_um_pr_so_nao_dispara_a_medicao(tmp_path):
    """O limiar é 2 ou mais: um PR sozinho não é série."""
    casa = _repo_encenado(tmp_path)
    _decidir(tmp_path, [
        _humano("faça o PR"),
        _pr_criado("Bash"),
        _fala(CONTAS_COMPLETAS),
    ], cwd=str(casa), session_id="sessao-um-pr")
    eventos = telemetria.ler_tudo(casa / ".git")
    assert not any(e.get("evento") == "serie_sem_despacho" for e in eventos)


def test_sombra_nao_muda_o_exit_code(tmp_path):
    """A sombra é SOMBRA: mesmo com 2 PRs sem despacho, uma sessão que já
    prestou contas corretamente continua saindo calada (exit 0). Quem decide o
    exit code continua sendo só `decidir()`."""
    casa = _repo_encenado(tmp_path)
    proc = _decidir(tmp_path, [
        _humano("faça os dois PRs"),
        _pr_criado("Bash"),
        _pr_criado("PowerShell"),
        _fala(CONTAS_COMPLETAS),
    ], cwd=str(casa), session_id="sessao-exit-code")
    _silencio(proc)
    eventos = telemetria.ler_tudo(casa / ".git")
    assert any(e.get("evento") == "serie_sem_despacho" for e in eventos), (
        "a sombra tem de ter gravado mesmo com o turno calado"
    )
