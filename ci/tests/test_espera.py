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
           gh_exit: int = 0) -> subprocess.CompletedProcess:
    """Roda a CLI com gh de mentira (ESPERAR_GH) e HOME em tmp."""
    env = dict(os.environ)
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
