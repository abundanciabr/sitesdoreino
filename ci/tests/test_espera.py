"""Guardas da espera que fala (ci/espera.py + ci/esperar.py) — armadilhas/161.

O que se prova aqui, na ordem do que custou caro:

1. O MOTOR (`vigiar`) preserva a semântica do portão: teto, graça, cinco
   falhas seguidas — e o contador de falhas ZERA após observação boa.
2. A VOZ é chamada a cada volta — espera muda é estruturalmente impossível.
3. A CLI fala as três linhas do contrato (partida · batimento · desfecho), e a
   SABOTAGEM (API que falha sempre / alvo que nunca conclui) NUNCA rende verde.
   As asserções são sobre O TEXTO QUE O DONO LÊ, não sobre exit code apenas
   (armadilhas/155: sabotagem que "passa" nem sempre é guarda forte).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ_DO_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ_DO_REPO / "ci"))

from _nucleo import ErroDeInstrumentacao  # noqa: E402
from espera import (  # noqa: E402
    FalhasSeguidas,
    GracaVencida,
    Olhada,
    TetoVencido,
    vigiar,
)
from esperar import ESPERAS_QUE_NAO_DEVIAM_EXISTIR  # noqa: E402
from mergear import MOTIVO_GITHUB_AINDA_CALCULANDO  # noqa: E402

ESPERAR = RAIZ_DO_REPO / "ci" / "esperar.py"


# ------------------------------------------------------------------ o motor --


class Relogio:
    """Relógio de mentira: cada dormir() avança o tempo — teste sem sleep real."""

    def __init__(self) -> None:
        self.agora = 0.0

    def __call__(self) -> float:
        return self.agora

    def dormir(self, segundos: float) -> None:
        self.agora += segundos


def test_sucesso_devolve_a_olhada_e_a_voz_ouviu_cada_volta():
    relogio = Relogio()
    respostas = iter([
        Olhada(pronta=False, resumo="ainda não"),
        Olhada(pronta=False, resumo="quase"),
        Olhada(pronta=True, resumo="pronto", dados={"verde": True}),
    ])
    vozes = []
    final = vigiar(
        lambda: next(respostas),
        teto=100, intervalo=10,
        relogio=relogio, dormir=relogio.dormir,
        ao_observar=vozes.append,
    )
    assert final.resumo == "pronto"
    assert [v.olhada.resumo for v in vozes] == ["ainda não", "quase", "pronto"]


def test_teto_vencido_com_alvo_pendente_carrega_a_ultima_olhada():
    relogio = Relogio()
    with pytest.raises(TetoVencido) as caso:
        vigiar(
            lambda: Olhada(pronta=False, resumo="pendurado"),
            teto=25, intervalo=10,
            relogio=relogio, dormir=relogio.dormir,
        )
    assert caso.value.olhada is not None
    assert caso.value.erro is None
    assert caso.value.decorrido >= 25


def test_cinco_falhas_seguidas_derrubam_a_espera():
    relogio = Relogio()

    def observar():
        raise ErroDeInstrumentacao("a API caiu", "detalhe")

    vozes = []
    with pytest.raises(FalhasSeguidas) as caso:
        vigiar(observar, teto=1000, intervalo=1,
               relogio=relogio, dormir=relogio.dormir, ao_observar=vozes.append)
    assert caso.value.falhas_seguidas == 5
    # a voz ouviu CADA falha — nenhum silêncio entre a 1ª e a 5ª
    assert [v.falhas_seguidas for v in vozes] == [1, 2, 3, 4, 5]


def test_falha_transitoria_nao_derruba_o_contador_zera():
    relogio = Relogio()
    roteiro = iter(["erro", "erro", "erro", "erro", "bom", "erro", "pronto"])

    def observar():
        passo = next(roteiro)
        if passo == "erro":
            raise ErroDeInstrumentacao("tosse passageira")
        return Olhada(pronta=(passo == "pronto"), resumo=passo)

    final = vigiar(observar, teto=1000, intervalo=1,
                   relogio=relogio, dormir=relogio.dormir)
    assert final.resumo == "pronto"  # 4 falhas + boa + 1 falha + pronta: passa


def test_graca_vencida_quando_o_alvo_nem_aparece():
    relogio = Relogio()
    with pytest.raises(GracaVencida):
        vigiar(
            lambda: Olhada(pronta=False, apareceu=False, resumo="cadê?"),
            teto=1000, intervalo=10, graca=25,
            relogio=relogio, dormir=relogio.dormir,
        )


def test_alvo_que_apareceu_nao_sofre_graca_sofre_teto():
    relogio = Relogio()
    with pytest.raises(TetoVencido):
        vigiar(
            lambda: Olhada(pronta=False, apareceu=True, resumo="rodando"),
            teto=50, intervalo=10, graca=25,
            relogio=relogio, dormir=relogio.dormir,
        )


def test_teto_no_meio_de_falhas_carrega_o_erro_nao_a_olhada():
    relogio = Relogio()

    def observar():
        raise ErroDeInstrumentacao("a API caiu")

    with pytest.raises(TetoVencido) as caso:
        vigiar(observar, teto=3, intervalo=1, falhas_max=99,
               relogio=relogio, dormir=relogio.dormir)
    assert caso.value.erro is not None


# ------------------------------------------------------------------- a CLI --


def _rodar(args: list[str], tmp: Path, gh_respostas: list[dict] | None = None,
           gh_exit: int = 0, mergear_exit: int | None = None,
           mergear_roteiro: list[dict] | None = None,
) -> subprocess.CompletedProcess:
    """Roda a CLI com gh de mentira (ESPERAR_GH) e HOME em tmp.

    `mergear_exit` liga um portão de mentira (ESPERAR_MERGEAR) que grava os
    argumentos recebidos em `portao-chamado.txt` e sai com esse código.

    `mergear_roteiro` é o mesmo portão de mentira, com uma resposta DIFERENTE
    por chamada: uma lista de `{"exit": int, "saida": str}`. Serve para medir a
    remedição — o portão que não consegue medir na primeira volta e mede na
    segunda. Cada chamada acrescenta uma linha em `portao-chamadas.txt`.
    """
    env = dict(os.environ)
    if mergear_roteiro is not None:
        fita_do_portao = tmp / "fita-do-portao.json"
        fita_do_portao.write_text(json.dumps(mergear_roteiro), encoding="utf-8")
        portao = tmp / "portao_de_mentira.py"
        chamadas = tmp / "portao-chamadas.txt"
        portao.write_text(
            "import json, sys, pathlib\n"
            f"fita = pathlib.Path(r'{fita_do_portao}')\n"
            f"chamadas = pathlib.Path(r'{chamadas}')\n"
            "roteiro = json.loads(fita.read_text(encoding='utf-8'))\n"
            "atual = roteiro.pop(0) if roteiro else {'exit': 0, 'saida': 'fita vazia'}\n"
            "fita.write_text(json.dumps(roteiro), encoding='utf-8')\n"
            "with chamadas.open('a', encoding='utf-8') as f:\n"
            "    f.write(' '.join(sys.argv[1:]) + chr(10))\n"
            # Escreve BYTES, na codificação que a fita mandar (padrão utf-8).
            # Um `print` comum escreveria na codepage do console, que é
            # justamente a variável do defeito de 04/09/2026 — e um dublê que
            # não consegue reproduzir a travessia não prova nada sobre ela.
            "cp = atual.get('codepage', 'utf-8')\n"
            "sys.stdout.buffer.write(atual['saida'].encode(cp, 'replace') + b'\\n')\n"
            "sys.stdout.buffer.flush()\n"
            "sys.exit(atual['exit'])\n",
            encoding="utf-8",
        )
        env["ESPERAR_MERGEAR"] = json.dumps([sys.executable, str(portao)])
        env["ESPERAR_SEGUNDOS_ENTRE_REMEDICOES"] = "0.05"
    elif mergear_exit is not None:
        portao = tmp / "portao_de_mentira.py"
        marca = tmp / "portao-chamado.txt"
        portao.write_text(
            "import sys, pathlib\n"
            f"pathlib.Path(r'{marca}').write_text(' '.join(sys.argv[1:]))\n"
            f"print('portao de mentira: exit {mergear_exit}')\n"
            f"sys.exit({mergear_exit})\n",
            encoding="utf-8",
        )
        env["ESPERAR_MERGEAR"] = json.dumps([sys.executable, str(portao)])
    env["USERPROFILE"] = str(tmp)      # Windows: Path.home()
    env["HOME"] = str(tmp)             # POSIX (o runner do CI é Linux)
    env["ESPERAR_REPO"] = "dona/loja"
    if gh_respostas is not None:
        fita = tmp / "fita.json"
        fita.write_text(json.dumps(gh_respostas), encoding="utf-8")
        fake = tmp / "gh_de_mentira.py"
        fake.write_text(
            "import json, sys, pathlib\n"
            f"fita = pathlib.Path(r'{fita}')\n"
            "respostas = json.loads(fita.read_text(encoding='utf-8'))\n"
            f"if {gh_exit} != 0 or not respostas:\n"
            "    print('gh de mentira: caiu', file=sys.stderr)\n"
            f"    sys.exit({gh_exit or 1})\n"
            "atual = respostas.pop(0)\n"
            "fita.write_text(json.dumps(respostas), encoding='utf-8')\n"
            "print(json.dumps(atual))\n",
            encoding="utf-8",
        )
        env["ESPERAR_GH"] = json.dumps([sys.executable, str(fake)])
    return subprocess.run(
        [sys.executable, str(ESPERAR), *args],
        capture_output=True, text=True, env=env, timeout=120,
        encoding="utf-8", errors="replace",
    )


def test_autoteste_fala_as_tres_linhas_e_morre_no_teto(tmp_path):
    proc = _rodar(["--autoteste"], tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert "▶ vou esperar" in proc.stdout
    assert "⏳" in proc.stdout
    assert "ESTOUREI o teto" in proc.stdout


def test_sem_teto_a_cli_recusa_e_ensina(tmp_path):
    proc = _rodar(["--run", "123"], tmp_path)
    assert proc.returncode != 0
    assert "teto" in (proc.stderr + proc.stdout)
    assert "armadilhas/161" in (proc.stderr + proc.stdout)


@pytest.mark.parametrize("alvo", sorted(ESPERAS_QUE_NAO_DEVIAM_EXISTIR))
def test_a_espera_que_nao_devia_existir_recusa_e_ensina_o_caminho(alvo, tmp_path):
    """`--pouso`/`--checks` recusam, e a recusa ENSINA (31/08/2026).

    A regra existia desde 29/08 no texto do RITOS e no cabeçalho deste script,
    e apodreceu por não ter mecanismo: os robôs esperavam o pouso porque a
    opção estava listada ao lado das legítimas. Medido nos 40 PRs de 31/08,
    isso era ~8,4 min de robô parado por tarefa, olhando uma fila que anda
    sozinha. Recusa muda não serviria: ela precisa dizer o que fazer no lugar.
    """
    proc = _rodar([f"--{alvo}", "447", "--teto", "15"], tmp_path)
    saida = proc.stdout + proc.stderr
    assert proc.returncode != 0, saida
    assert "--pousar" in saida, "a recusa precisa ENSINAR o caminho certo"
    assert "447" in saida, "a recusa precisa citar o PR de quem a leu"
    assert "RITOS" in saida


@pytest.mark.parametrize("alvo", sorted(ESPERAS_QUE_NAO_DEVIAM_EXISTIR))
def test_a_recusa_nao_falou_a_partida_antes_de_desistir(alvo, tmp_path):
    """Recusar DEPOIS de anunciar "vou esperar" ensinaria o oposto da lei."""
    proc = _rodar([f"--{alvo}", "447", "--teto", "15"], tmp_path)
    assert "▶ vou esperar" not in proc.stdout


def test_o_escape_exige_motivo_escrito_e_entao_espera_de_verdade(tmp_path):
    """`--mesmo-assim` existe para depurar a própria pista — e cobra o motivo."""
    proc = _rodar(
        ["--pouso", "447", "--teto", "1", "--intervalo", "0.05",
         "--mesmo-assim", "depurando a pista"],
        tmp_path,
        gh_respostas=[{"state": "MERGED", "labels": [], "url": "u"}],
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "▶ vou esperar" in proc.stdout
    assert "POUSOU" in proc.stdout


def test_o_veredito_do_deploy_continua_livre(tmp_path):
    """A espera que a LEI MANDA ter nunca pode cair na recusa acima."""
    assert "deploy-celula" not in ESPERAS_QUE_NAO_DEVIAM_EXISTIR
    proc = _rodar(
        ["--run", "9", "--teto", "1", "--intervalo", "0.05"],
        tmp_path,
        gh_respostas=[{"status": "completed", "conclusion": "success",
                       "name": "deploy-celula", "html_url": "u"}],
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_esperar_os_checks_UMA_VEZ_continua_livre(tmp_path):
    """`--checks` NÃO pode ser proibido — é pré-requisito do `--pousar`.

    Este teste existe por um erro que quase pousou (armadilhas/258): a primeira
    versão do PR #801 proibiu `--checks` apoiada na letra do RITOS §2 peça 6
    ("checks de PR não se esperam"). A peça fala do LAÇO da armadilhas/156, não
    da espera única que o portão EXIGE: `ci/mergear.py --pousar` recusa com
    check em andamento (ERROR), e o CLAUDE.md manda esperá-los concluir antes
    de pedir pouso. Proibir aqui tornaria o rito da casa impossível de cumprir.
    """
    assert "checks" not in ESPERAS_QUE_NAO_DEVIAM_EXISTIR, (
        "proibir --checks quebra o passo 1 do rito (CLAUDE.md): o portão recusa "
        "pedido de pouso com check em andamento — ver armadilhas/258"
    )
    proc = _rodar(
        ["--checks", "447", "--teto", "1", "--intervalo", "0.05"],
        tmp_path,
        gh_respostas=[{"state": "OPEN", "statusCheckRollup": [
            {"status": "COMPLETED", "conclusion": "SUCCESS", "name": "muralhas"},
        ]}],
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "verdes" in proc.stdout


def test_run_verde_fala_verde_e_sai_zero(tmp_path):
    proc = _rodar(
        ["--run", "9", "--teto", "1", "--intervalo", "0.05"],
        tmp_path,
        gh_respostas=[{"status": "completed", "conclusion": "success",
                       "name": "deploy-celula", "html_url": "u"}],
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "✅" in proc.stdout
    assert "terminou 'success'" in proc.stdout


def test_run_reprovado_fala_reprovado_e_sai_um(tmp_path):
    proc = _rodar(
        ["--run", "9", "--teto", "1", "--intervalo", "0.05"],
        tmp_path,
        gh_respostas=[{"status": "completed", "conclusion": "failure",
                       "name": "deploy-celula", "html_url": "u"}],
    )
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "REPROVADO" in proc.stdout
    assert "não re-tente às cegas" in proc.stdout


def test_sabotagem_api_que_cai_sempre_nunca_rende_verde(tmp_path):
    """A sabotagem central: gh caindo TODA vez. O dono tem de ler que a medição
    falhou — e nenhum ✅ pode aparecer (não medir nunca é verde)."""
    proc = _rodar(
        ["--run", "9", "--teto", "5", "--intervalo", "0.05"],
        tmp_path,
        gh_respostas=[], gh_exit=1,
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "não consegui medir 5 vezes seguidas" in proc.stdout
    assert "NUNCA é um verde" in proc.stdout
    assert "✅" not in proc.stdout
    # e a voz falou CADA falha antes de morrer — nada de silêncio
    assert proc.stdout.count("não consegui perguntar") >= 4


def test_estouro_fala_a_linha_de_morte_e_sai_dois(tmp_path):
    sempre_rodando = [{"status": "in_progress", "conclusion": None,
                       "name": "deploy-celula", "html_url": "u"}] * 50
    proc = _rodar(
        ["--run", "9", "--teto", "0.02", "--intervalo", "0.05", "--voz", "0"],
        tmp_path,
        gh_respostas=sempre_rodando,
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "ESTOUREI o teto" in proc.stdout
    assert "Parei." in proc.stdout
    assert "✅" not in proc.stdout


def test_toda_espera_concluida_deixa_registro_no_log(tmp_path):
    _rodar(
        ["--run", "9", "--teto", "1", "--intervalo", "0.05"],
        tmp_path,
        gh_respostas=[{"status": "completed", "conclusion": "success",
                       "name": "x", "html_url": "u"}],
    )
    log = tmp_path / ".sitesdoreino" / "esperas.jsonl"
    assert log.exists(), "a espera concluiu e não deixou registro nenhum"
    linha = json.loads(log.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert linha["desfecho"] == "verde"
    assert linha["alvo"] == "run:9"
    assert linha["teto_s"] == 60


def test_regua_ausente_diz_nao_sei_nunca_inventa_numero(tmp_path):
    proc = _rodar(
        ["--sonda", "exit 0", "--teto", "1", "--intervalo", "0.05"],
        tmp_path,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "não sei quanto isto costuma levar" in proc.stdout


# ---------------------------------------------------------------------------
# --e-pousar: o caminho inteiro num comando (03/09/2026)
# ---------------------------------------------------------------------------
VERDE = [{"state": "OPEN", "statusCheckRollup": [
    {"status": "COMPLETED", "conclusion": "SUCCESS", "name": "muralhas"},
]}]
VERMELHO = [{"state": "OPEN", "statusCheckRollup": [
    {"status": "COMPLETED", "conclusion": "FAILURE", "name": "muralhas"},
]}]
RAPIDO = ["--teto", "1", "--intervalo", "0.05"]


def test_e_pousar_sem_checks_recusa_e_ensina(tmp_path):
    proc = _rodar(["--run", "1", *RAPIDO, "--e-pousar"], tmp_path)
    assert proc.returncode == 2
    assert "--e-pousar" in proc.stderr and "--checks" in proc.stderr


def test_checks_verdes_com_e_pousar_chamam_o_portao_e_pedem_pouso(tmp_path):
    """O que o mantenedor pediu em 03/09/2026: verde ⇒ pouso, sem ninguém voltar."""
    proc = _rodar(
        ["--checks", "447", *RAPIDO, "--e-pousar"],
        tmp_path, gh_respostas=VERDE, mergear_exit=0,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    chamado = (tmp_path / "portao-chamado.txt").read_text(encoding="utf-8")
    assert chamado == "447 --pousar", chamado
    assert "pedi pouso do PR 447 pelo portão" in proc.stdout
    assert "Nada mais depende de ninguém" in proc.stdout


def test_checks_reprovados_com_e_pousar_nunca_chamam_o_portao(tmp_path):
    """Vermelho NUNCA vira pedido de pouso — o portão nem é acordado."""
    proc = _rodar(
        ["--checks", "447", *RAPIDO, "--e-pousar"],
        tmp_path, gh_respostas=VERMELHO, mergear_exit=0,
    )
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert not (tmp_path / "portao-chamado.txt").exists(), "chamou o portão no vermelho"
    assert "REPROVADO" in proc.stdout


def test_portao_que_recusa_faz_a_espera_terminar_vermelha(tmp_path):
    """Checks verdes não bastam: o portão continua dono da decisão (base velha,
    dívida do livro, registro ausente), e a recusa dele sai inteira na voz."""
    proc = _rodar(
        ["--checks", "447", *RAPIDO, "--e-pousar"],
        tmp_path, gh_respostas=VERDE, mergear_exit=1,
    )
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "RECUSOU o pouso do PR 447" in proc.stdout
    assert "portao de mentira: exit 1" in proc.stdout, "a recusa do portão tem de sair na voz"


# ---------------------------------------------------------------------------
# O --deploy resolve ou recusa o sha curto (04/09/2026)
# ---------------------------------------------------------------------------
DEPLOY_VERDE = [{"workflow_runs": [
    {"path": ".github/workflows/deploy-celula.yml",
     "status": "completed", "conclusion": "success"},
]}]
SHA_FALSO = "a" * 40


def test_deploy_com_sha_inteiro_passa_direto_sem_resolver(tmp_path):
    """40 caracteres hexadecimais é o que a API espera: nada a resolver, e o
    script não pode depender de um repositório git para o caso normal."""
    proc = _rodar(
        ["--deploy", SHA_FALSO, *RAPIDO],
        tmp_path, gh_respostas=DEPLOY_VERDE,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "resolvi" not in proc.stdout, "sha inteiro não se resolve: " + proc.stdout


def test_deploy_com_referencia_desconhecida_RECUSA_e_ensina(tmp_path):
    """O guarda que impede a espera impossível.

    O `head_sha=` da API casa por IGUALDADE. Um sha curto acha zero runs, e a
    espera repetiria "nenhum run apareceu ainda" até o teto — uma frase
    legítima para uma condição que nunca vai ser satisfeita. Recusar na porta
    é o que transforma vinte minutos perdidos em uma linha de erro.
    """
    proc = _rodar(
        ["--deploy", "isto-nao-e-um-commit-de-jeito-nenhum", *RAPIDO],
        tmp_path, gh_respostas=DEPLOY_VERDE,
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "git rev-parse" in proc.stderr, "a recusa tem de ENSINAR o caminho"
    assert "IGUALDADE" in proc.stderr, "a recusa tem de dizer POR QUE"


def test_deploy_com_sha_curto_de_verdade_resolve_e_diz_que_resolveu(tmp_path):
    """A outra metade: recusar tudo o que é curto seria cura pior que a doença.

    Usa `HEAD` porque ele existe em qualquer checkout e não amarra o teste a um
    commit específico. A asserção é dupla de propósito: resolveu (a espera
    seguiu e terminou) E avisou em voz alta (a linha 'resolvi'), porque uma
    resolução silenciosa esconderia do robô qual sha ele acabou medindo.
    """
    proc = _rodar(
        ["--deploy", "HEAD", *RAPIDO],
        tmp_path, gh_respostas=DEPLOY_VERDE,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "resolvi HEAD para o sha inteiro" in proc.stdout


# ---------------------------------------------------------------------------
# A remedição do ERROR do portão (03/09/2026) — ERROR nunca é FAIL
# ---------------------------------------------------------------------------
# A prosa é decorativa aqui e pode ser reescrita à vontade; a marca IMPORTADA é
# o que o `esperar.py` procura. Antes de 04/09/2026 esta fita copiava a frase
# em português, e a cópia dava um verde falso: reescrever a mensagem no portão
# mataria a remedição sem este teste piscar.
RECALCULANDO = (
    "--- ERROR conflitos ---\n"
    "O GitHub calcula isso de forma assíncrona; se você acabou de dar push,\n"
    "espere alguns segundos e rode de novo.\n"
    f"{MOTIVO_GITHUB_AINDA_CALCULANDO}\n"
    "RESULTADO  ERROR"
)


def test_o_portao_que_nao_conseguiu_medir_e_remedido_e_o_pouso_sai(tmp_path):
    """O caso medido em 03/09/2026: dois PRs seguidos do mesmo lote (#954 e
    #956) morreram aqui porque o GitHub ainda recalculava o conflito no segundo
    em que o último check ficou verde. ERROR é 'não consegui medir', nunca
    'reprovado' — remede-se (RUNBOOK-LOTES §9, Lote 10, lição 3)."""
    proc = _rodar(
        ["--checks", "447", *RAPIDO, "--e-pousar"],
        tmp_path, gh_respostas=VERDE,
        mergear_roteiro=[
            {"exit": 2, "saida": RECALCULANDO},
            {"exit": 0, "saida": "POUSO PEDIDO"},
        ],
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    chamadas = (tmp_path / "portao-chamadas.txt").read_text(encoding="utf-8").split()
    assert chamadas.count("--pousar") == 2, chamadas
    # A remedição é bastidor: desde 06/09/2026 ela fala no stderr sob
    # `--e-pousar`, para não acordar o robô por um fato que ainda não é
    # desfecho. Continua PROIBIDO esperar calada — só mudou o cano.
    assert "remeço em" in proc.stdout + proc.stderr, (
        "a remedição tem de FALAR, nunca esperar calada"
    )
    assert "pedi pouso do PR 447 pelo portão" in proc.stdout


def test_o_portao_que_REPROVA_nao_e_remedido_nenhuma_vez(tmp_path):
    """A contraprova que impede a cura de virar teimosia: FAIL é sobre o PR
    (base velha, dívida do livro, registro ausente) e nunca melhora sozinho.
    Sem este guarda, remedir seis vezes TODA recusa passaria no teste acima."""
    proc = _rodar(
        ["--checks", "447", *RAPIDO, "--e-pousar"],
        tmp_path, gh_respostas=VERDE,
        mergear_roteiro=[
            {"exit": 1, "saida": "FAIL dívida do livro"},
            {"exit": 0, "saida": "POUSO PEDIDO"},
        ],
    )
    assert proc.returncode == 1, proc.stdout + proc.stderr
    chamadas = (tmp_path / "portao-chamadas.txt").read_text(encoding="utf-8").split()
    assert chamadas.count("--pousar") == 1, "FAIL não se remede: " + repr(chamadas)
    assert "RECUSOU o pouso do PR 447" in proc.stdout


def test_o_ERROR_que_nao_para_de_vir_desiste_e_conta_a_recusa_inteira(tmp_path):
    """Teto na remedição: o GitHub que nunca decide não vira espera infinita.
    A última recusa sai inteira na voz, como sempre saiu."""
    proc = _rodar(
        ["--checks", "447", *RAPIDO, "--e-pousar"],
        tmp_path, gh_respostas=VERDE,
        mergear_roteiro=[{"exit": 2, "saida": RECALCULANDO} for _ in range(6)],
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    chamadas = (tmp_path / "portao-chamadas.txt").read_text(encoding="utf-8").split()
    assert chamadas.count("--pousar") == 6, chamadas
    assert "RECUSOU o pouso do PR 447" in proc.stdout
    assert "calcula isso de forma assíncrona" in proc.stdout


def test_a_remedicao_sobrevive_ao_portao_que_escreve_em_cp1252(tmp_path):
    """A prova de fora do defeito de 04/09/2026, e ela roda em QUALQUER sistema.

    O caso real: no Windows um filho Python escreve no cano pela codepage do
    console (cp1252) enquanto o pai decodifica utf-8. O `í` de "assíncrona"
    sai como `\\xed`, chega como `\\ufffd`, e a comparação de texto que decidia
    remedir dizia "não" para sempre. A remedição inteira — construída em
    03/09/2026 porque os PRs #954 e #956 morreram sem ela — nasceu inerte na
    única máquina onde roda, e ficou verde na CI o tempo todo.

    Este teste não espera por um runner Windows para ver isso: ele MANDA o
    dublê escrever cp1252. Assim o perigo, que era de plataforma, virou uma
    linha de fita — reproduzível no Linux da CI, no primeiro segundo.

    Vermelho→verde medido em 04/09/2026: com a marca em prosa acentuada, o pai
    lê `ass\\ufffdncrona`, não remede, e o teste reprova com uma chamada só.
    """
    proc = _rodar(
        ["--checks", "447", *RAPIDO, "--e-pousar"],
        tmp_path, gh_respostas=VERDE,
        mergear_roteiro=[
            {"exit": 2, "saida": RECALCULANDO, "codepage": "cp1252"},
            {"exit": 0, "saida": "POUSO PEDIDO"},
        ],
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    chamadas = (tmp_path / "portao-chamadas.txt").read_text(encoding="utf-8").split()
    assert chamadas.count("--pousar") == 2, (
        "a recusa em cp1252 não foi reconhecida como 'não consegui medir' — "
        "a decisão voltou a depender de bytes: " + repr(chamadas)
    )
    assert "pedi pouso do PR 447 pelo portão" in proc.stdout


def test_sem_e_pousar_o_verde_continua_so_verde(tmp_path):
    """A opção é opt-in: quem não a pediu não pede pouso nenhum."""
    proc = _rodar(
        ["--checks", "447", *RAPIDO],
        tmp_path, gh_respostas=VERDE, mergear_exit=0,
    )
    assert proc.returncode == 0
    assert not (tmp_path / "portao-chamado.txt").exists()


# ---------------------------------------------------------------------------
# --so-desfecho: a espera acorda o robô UMA vez (06/09/2026)
#
# Cada linha em stdout vira uma notificação que reenvia a conversa inteira ao
# modelo. Medido em 06/09/2026: a espera dos checks custava de 18% a 21,8% da
# cota semanal, com o contexto mediano em 372k a 401k no instante da fala.
# Partida, batimento e placar continuam existindo — mudam de cano (stderr) e
# ficam guardados no log da espera, que é onde a auditoria os lê.
# ---------------------------------------------------------------------------
VERDE_COM_RUN = [{"state": "OPEN", "statusCheckRollup": [
    {"status": "COMPLETED", "conclusion": "SUCCESS", "name": "muralhas",
     "detailsUrl": "https://github.com/dona/loja/actions/runs/8899/job/1"},
]}]
PENDENTE = [{"state": "OPEN", "statusCheckRollup": [
    {"status": "IN_PROGRESS", "name": "muralhas"},
]}] * 40


def _linhas(texto: str) -> list[str]:
    return [l for l in texto.splitlines() if l.strip()]


def test_so_desfecho_manda_uma_linha_ao_stdout_e_o_batimento_ao_stderr(tmp_path):
    proc = _rodar(
        ["--checks", "447", *RAPIDO, "--so-desfecho"],
        tmp_path, gh_respostas=list(VERDE_COM_RUN),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert len(_linhas(proc.stdout)) == 1, (
        "stdout precisa acordar o robô UMA vez: " + proc.stdout
    )
    assert "verdes" in proc.stdout
    assert "▶ vou esperar" in proc.stderr, "a partida não pode SUMIR, só mudar de cano"
    assert "⏳" in proc.stderr, "o batimento não pode SUMIR, só mudar de cano"
    assert "▶ vou esperar" not in proc.stdout


def test_sem_a_flag_a_voz_de_hoje_continua_inteira_no_stdout(tmp_path):
    """Quem usa --run/--deploy pelo Monitor não pode perder nada."""
    proc = _rodar(
        ["--run", "9", *RAPIDO],
        tmp_path,
        gh_respostas=[{"status": "completed", "conclusion": "success",
                       "name": "deploy-celula", "html_url": "u"}],
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "▶ vou esperar" in proc.stdout
    assert "⏳" in proc.stdout
    assert "✅" in proc.stdout


def test_e_pousar_liga_o_modo_calado_e_o_pouso_cabe_na_mesma_linha(tmp_path):
    proc = _rodar(
        ["--checks", "447", *RAPIDO, "--e-pousar"],
        tmp_path, gh_respostas=list(VERDE_COM_RUN), mergear_exit=0,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert len(_linhas(proc.stdout)) == 1, (
        "--e-pousar tem de acordar o robô UMA vez: " + proc.stdout
    )
    unica = _linhas(proc.stdout)[0]
    assert "verdes" in unica, "o desfecho da espera some se não vier junto"
    assert "pedi pouso do PR 447" in unica
    assert "Nada mais depende de ninguém" in unica
    assert "passo pelo portão" in proc.stderr


def test_o_portao_que_recusa_conta_o_motivo_no_proprio_desfecho(tmp_path):
    """Calar o bastidor não pode calar a RECUSA: ela é o desfecho."""
    proc = _rodar(
        ["--checks", "447", *RAPIDO, "--e-pousar"],
        tmp_path, gh_respostas=list(VERDE_COM_RUN), mergear_exit=1,
    )
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "RECUSOU o pouso do PR 447" in proc.stdout
    assert "portao de mentira: exit 1" in proc.stdout, (
        "o motivo do portão ficou só no stderr — o robô não teria o que ler"
    )


def test_o_estouro_do_teto_e_desfecho_e_sai_no_stdout_mesmo_calado(tmp_path):
    proc = _rodar(
        ["--checks", "447", "--teto", "0.02", "--intervalo", "0.05", "--so-desfecho"],
        tmp_path, gh_respostas=list(PENDENTE),
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "ESTOUREI o teto" in proc.stdout


def test_a_falha_de_medicao_e_desfecho_e_sai_no_stdout_mesmo_calado(tmp_path):
    proc = _rodar(
        ["--checks", "447", *RAPIDO, "--so-desfecho"],
        tmp_path, gh_respostas=list(VERDE_COM_RUN), gh_exit=3,
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "não consegui medir" in proc.stdout


def test_o_batimento_calado_no_stdout_sobrevive_no_log_da_espera(tmp_path):
    """armadilhas/161: o que sai do stdout NÃO pode sair da auditoria."""
    proc = _rodar(
        ["--checks", "447", *RAPIDO, "--so-desfecho"],
        tmp_path, gh_respostas=list(VERDE_COM_RUN),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    bruto = (tmp_path / ".sitesdoreino" / "esperas.jsonl").read_text(encoding="utf-8")
    linha = json.loads(_linhas(bruto)[0])
    assert any("vou esperar" in l for l in linha["voz"]), linha
    assert any("⏳" in l for l in linha["voz"]), linha
