"""A escada do cartão não deixa o robô escolher o passo nem encerrar cedo.

O plano em prosa foi abandonado com a tela ainda no Mercado Pago. Estes
testes cobram a ordem e a parada: o primeiro incompleto é o único passo, a
tela não abre antes do motor, e o gancho só empurra a bancada armada até a
auditoria.
"""

from __future__ import annotations

import io
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

CI = Path(__file__).resolve().parents[1]
if str(CI) not in sys.path:
    sys.path.insert(0, str(CI))

import escada_do_cartao as escada  # noqa: E402
import fila  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]


def _aberta() -> dict[str, dict]:
    return {tar: {"estado": fila.NA_FILA, "espera": fila.ESPERA_A_FILA} for tar, *_ in escada.PASSOS}


def _concluir_ate(estados: dict[str, dict], tar: str) -> None:
    for atual, *_ in escada.PASSOS:
        estados[atual] = {"estado": fila.CONCLUIDA}
        if atual == tar:
            return


def test_o_primeiro_passo_e_o_estorno_e_nao_a_tela():
    # guarda: ci/escada_do_cartao.py:122
    decisao = escada.decidir(_aberta())
    assert decisao.tipo == "pegar"
    assert decisao.tar == escada.PASSOS[0][0]
    assert decisao.tar == "TAR-614"
    tela = next(tar for tar, celula, *_ in escada.PASSOS if celula == "checkout")
    assert tela not in decisao.texto.split("único passo legal agora é ", 1)[-1].split(" ", 1)[0]


def test_a_tela_continua_fechada_enquanto_o_motor_nao_existe():
    estados = _aberta()
    _concluir_ate(estados, "TAR-557")
    decisao = escada.decidir(estados)
    assert decisao.tar == "TAR-593"
    assert decisao.tar != "TAR-555"


def test_auditoria_concluida_encerra_sem_abrir_compra_real():
    estados = _aberta()
    _concluir_ate(estados, "TAR-564")
    estados["TAR-565"] = {"estado": fila.NA_FILA}
    decisao = escada.decidir(estados)
    assert decisao.tipo == "fim"
    assert decisao.tar == "TAR-564"
    assert "TAR-565" in decisao.texto


def test_bloqueio_do_dono_nao_e_fim():
    estados = _aberta()
    _concluir_ate(estados, "TAR-560")
    estados["TAR-561"] = {
        "estado": fila.BLOQUEADA,
        "espera": fila.ESPERA_O_MANTENEDOR,
        "motivo": "cartão oficial ausente",
    }
    decisao = escada.decidir(estados)
    assert decisao.tipo == "bloqueio"
    assert decisao.tar == "TAR-561"


def test_entrega_submetida_nao_abre_a_proxima():
    estados = _aberta()
    estados[escada.PASSOS[0][0]] = {"estado": fila.EM_EXECUCAO}
    decisao = escada.decidir(estados)
    assert decisao.tipo == "aguardar"
    assert decisao.tar == "TAR-614"


def test_a_fila_real_prende_a_tela_e_o_webhook():
    erros: list[str] = []
    tarefas = fila.carregar_tarefas(RAIZ, erros)
    assert not erros
    assert escada.correntes_falsas(tarefas) == []


def test_gancho_calado_sem_arme_e_em_aborto():
    decisao = escada.decidir(_aberta())
    assert escada.resposta_do_gancho(
        status="completed", armada_aqui=False, decisao=decisao,
        repeticoes=1, hora_de_nova_caixa=False,
    ) == {}
    assert escada.resposta_do_gancho(
        status="aborted", armada_aqui=True, decisao=decisao,
        repeticoes=1, hora_de_nova_caixa=False,
    ) == {}


def test_gancho_armado_devolve_o_unico_passo():
    decisao = escada.decidir(_aberta())
    resposta = escada.resposta_do_gancho(
        status="completed", armada_aqui=True, decisao=decisao,
        repeticoes=1, hora_de_nova_caixa=False,
    )
    assert "TAR-614" in resposta["followup_message"]
    assert "TAR-564" in resposta["followup_message"]


def test_gancho_para_no_fim_no_bloqueio_e_depois_de_seis_voltas_iguais():
    fim = escada.decidir({tar: {"estado": fila.CONCLUIDA} for tar, *_ in escada.PASSOS})
    assert escada.resposta_do_gancho(
        status="completed", armada_aqui=True, decisao=fim,
        repeticoes=1, hora_de_nova_caixa=False,
    ) == {}
    bloqueio = escada.Decisao("bloqueio", "TAR-561", fila.BLOQUEADA, "parado")
    assert escada.resposta_do_gancho(
        status="completed", armada_aqui=True, decisao=bloqueio,
        repeticoes=1, hora_de_nova_caixa=False,
    ) == {}
    aberto = escada.decidir(_aberta())
    assert escada.resposta_do_gancho(
        status="completed", armada_aqui=True, decisao=aberto,
        repeticoes=escada.LIMITE_SEM_AVANCO, hora_de_nova_caixa=False,
    ) == {}


def test_depois_das_21h30_nao_abre_caixa_nova():
    aberto = escada.decidir(_aberta())
    assert aberto.estado == fila.NA_FILA
    assert escada.resposta_do_gancho(
        status="completed", armada_aqui=True, decisao=aberto,
        repeticoes=1, hora_de_nova_caixa=True,
    ) == {}
    assert escada.hora_de_nao_abrir_caixa(
        datetime(2026, 9, 22, 21, 30, tzinfo=ZoneInfo("America/Sao_Paulo"))
    )
    assert not escada.hora_de_nao_abrir_caixa(
        datetime(2026, 9, 22, 11, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))
    )


def test_gancho_na_linha_de_comando_sem_arme_nao_forca(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ESCADA_ARQUIVO_DE_ARME", str(tmp_path / "ausente.json"))
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"status": "completed"})))
    assert escada.main(["--gancho-parar", "--raiz", str(RAIZ)]) == 0
    assert json.loads(capsys.readouterr().out) == {}
