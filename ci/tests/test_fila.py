"""Testes-guarda da FILA DE TRABALHO (ci/fila.py).

O que não pode deixar de morder, na ordem do que mais dói:

1. A corrida: duas sessões pegando a mesma tarefa → a segunda é RECUSADA, e
   nenhum evento é escrito para ela (a trava que os três consultores pediram).
2. Concluir sem evidência não existe — a lei do verde do livro, na fila.
3. Estado é sempre uma conta: ninguém escreve "status" em lugar nenhum.
4. A validação fail-closed que a muralha roda (`ci/muralha-da-fila.sh`).

Nenhum teste toca a rede: o almoxarife é fingido, como em test_reservar.py —
a prova VIVA da trava (servidor de verdade recusando a segunda reserva) foi
feita à mão e está colada no PR que fez a fila nascer.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

import fila
from _nucleo import ErroDeInstrumentacao


def tarefa(numero="001", slug="exemplo", deps=(), **sobrescreve):
    dados = {
        "arquivo": f"{numero}-{slug}",
        "id": f"TAR-{numero}",
        "titulo": "Uma tarefa de exemplo",
        "toca": ["admin"],
        "depende_de": list(deps),
        "evidencia_exigida": "um PR mergeado",
        "despacho": "faça a coisa, com calma",
        "origem": "teste",
        "criada_em": "2026-08-29",
    }
    dados.update(sobrescreve)
    return dados


def evento(tid="TAR-001", tipo="reivindicada", hora="10:00:00", quem="sessao-a", **extra):
    stem = f"20260829-{hora.replace(':', '')}-{tid}-{tipo}"
    dados = {
        "arquivo": stem,
        "tarefa": tid,
        "evento": tipo,
        "quando": f"2026-08-29T{hora}+00:00",
        "quem": quem,
    }
    dados.update(extra)
    return dados


def montar(tmp_path, tarefas=(), eventos=(), com_pasta_de_eventos=True):
    (tmp_path / "fila" / "tarefas").mkdir(parents=True)
    if com_pasta_de_eventos:
        (tmp_path / "fila" / "eventos").mkdir(parents=True)
    for t in tarefas:
        caminho = tmp_path / "fila" / "tarefas" / f"{t['arquivo']}.json"
        caminho.write_text(json.dumps(t, ensure_ascii=False), encoding="utf-8")
    for e in eventos:
        caminho = tmp_path / "fila" / "eventos" / f"{e['arquivo']}.json"
        caminho.write_text(json.dumps(e, ensure_ascii=False), encoding="utf-8")
    return tmp_path


def carregar(raiz):
    erros: list[str] = []
    tarefas = fila.carregar_tarefas(raiz, erros)
    eventos = fila.carregar_eventos(raiz, tarefas, erros)
    return tarefas, eventos, erros


# ---------------------------------------------------------------------------
# A validação que a muralha roda
# ---------------------------------------------------------------------------


def test_fila_valida_passa(tmp_path):
    montar(tmp_path, [tarefa()], [evento()])
    assert fila.cmd_validar(tmp_path) == 0


def test_fila_vazia_e_valida(tmp_path):
    montar(tmp_path, com_pasta_de_eventos=False)
    assert fila.cmd_validar(tmp_path) == 0


def test_sem_pasta_fila_reprova(tmp_path):
    assert fila.cmd_validar(tmp_path) == 1


def test_campo_faltando_reprova(tmp_path):
    t = tarefa()
    del t["evidencia_exigida"]
    montar(tmp_path, [t])
    assert fila.cmd_validar(tmp_path) == 1


def test_campo_desconhecido_reprova(tmp_path):
    montar(tmp_path, [tarefa(status="done")])
    _, _, erros = carregar(tmp_path)
    assert any("desconhecido 'status'" in e for e in erros)


def test_numero_repetido_reprova(tmp_path):
    montar(tmp_path, [tarefa("003", "a"), tarefa("003", "b")])
    _, _, erros = carregar(tmp_path)
    assert any("repetido" in e for e in erros)


def test_dependencia_fantasma_reprova(tmp_path):
    montar(tmp_path, [tarefa(deps=["TAR-099"])])
    _, _, erros = carregar(tmp_path)
    assert any("TAR-099" in e for e in erros)


def test_ciclo_de_dependencias_reprova(tmp_path):
    montar(tmp_path, [tarefa("001", "a", deps=["TAR-002"]), tarefa("002", "b", deps=["TAR-001"])])
    _, _, erros = carregar(tmp_path)
    assert any("ciclo" in e for e in erros)


def test_concluida_sem_evidencia_reprova(tmp_path):
    montar(tmp_path, [tarefa()], [evento(tipo="concluida", quem="sessao-a")])
    _, _, erros = carregar(tmp_path)
    assert any("SEM evidência" in e for e in erros)


def test_evento_depois_do_fim_reprova(tmp_path):
    montar(
        tmp_path,
        [tarefa()],
        [
            evento(tipo="concluida", hora="10:00:00", evidencia="PR #1", verificado_em="2026-08-29"),
            evento(tipo="reivindicada", hora="11:00:00"),
        ],
    )
    _, _, erros = carregar(tmp_path)
    assert any("depois do fim" in e for e in erros)


# ---------------------------------------------------------------------------
# Estado é uma conta, nunca um campo
# ---------------------------------------------------------------------------


def estados_de(tmp_path, tarefas, eventos=(), reservas=None, prs=None):
    montar(tmp_path, tarefas, eventos)
    ts, evs, erros = carregar(tmp_path)
    assert not erros, erros
    return fila.calcular_estados(ts, evs, reservas, prs)


def test_sem_eventos_esta_na_fila(tmp_path):
    assert estados_de(tmp_path, [tarefa()])["TAR-001"]["estado"] == fila.NA_FILA


def test_reivindicada_pelo_evento(tmp_path):
    e = estados_de(tmp_path, [tarefa()], [evento()])["TAR-001"]
    assert (e["estado"], e["quem"]) == (fila.REIVINDICADA, "sessao-a")


def test_devolvida_volta_para_a_fila(tmp_path):
    eventos = [evento(hora="10:00:00"), evento(tipo="devolvida", hora="11:00:00")]
    assert estados_de(tmp_path, [tarefa()], eventos)["TAR-001"]["estado"] == fila.NA_FILA


def test_bloqueada_pelo_evento_carrega_o_motivo(tmp_path):
    e = estados_de(tmp_path, [tarefa()], [evento(tipo="bloqueada", detalhe="falta decisão do dono")])
    assert e["TAR-001"] == {"estado": fila.BLOQUEADA, "motivo": "falta decisão do dono", "quem": "sessao-a"}


def test_concluida_e_terminal(tmp_path):
    eventos = [evento(tipo="concluida", evidencia="PR #9", verificado_em="2026-08-29")]
    assert estados_de(tmp_path, [tarefa()], eventos)["TAR-001"]["estado"] == fila.CONCLUIDA


def test_dependencia_aberta_bloqueia_por_conta(tmp_path):
    e = estados_de(tmp_path, [tarefa("001", "a"), tarefa("002", "b", deps=["TAR-001"])])
    assert e["TAR-002"] == {"estado": fila.BLOQUEADA, "motivo": "esperando TAR-001", "quem": None}


def test_dependencia_concluida_libera(tmp_path):
    eventos = [evento(tipo="concluida", evidencia="PR #9", verificado_em="2026-08-29")]
    e = estados_de(tmp_path, [tarefa("001", "a"), tarefa("002", "b", deps=["TAR-001"])], eventos)
    assert e["TAR-002"]["estado"] == fila.NA_FILA


def test_reserva_viva_no_servidor_conta_como_reivindicada(tmp_path):
    e = estados_de(tmp_path, [tarefa()], reservas={"TAR-001"})
    assert e["TAR-001"]["estado"] == fila.REIVINDICADA


def test_pr_aberto_conta_como_em_execucao(tmp_path):
    e = estados_de(tmp_path, [tarefa()], [evento()], prs={"TAR-001": "PR #77"})
    assert e["TAR-001"] == {"estado": fila.EM_EXECUCAO, "motivo": "PR #77", "quem": "sessao-a"}


# ---------------------------------------------------------------------------
# A corrida — o motivo de a fila existir
# ---------------------------------------------------------------------------


def sem_rede(monkeypatch, reservas=frozenset(), prs=None):
    monkeypatch.setattr(fila, "reservas_no_servidor", lambda raiz: set(reservas))
    monkeypatch.setattr(fila, "prs_citando_tarefas", lambda raiz: dict(prs or {}))


def test_pegar_ganha_escreve_o_evento_e_mostra_o_despacho(tmp_path, monkeypatch, capsys):
    montar(tmp_path, [tarefa()])
    sem_rede(monkeypatch)
    monkeypatch.setattr(fila.reservar, "reservar_intencao", lambda *a, **k: (True, "é sua"))
    args = argparse.Namespace(tarefa="TAR-001", quem="sessao-b")
    assert fila.cmd_pegar(tmp_path, args) == 0
    eventos = list((tmp_path / "fila" / "eventos").glob("*-TAR-001-reivindicada.json"))
    assert len(eventos) == 1
    assert "faça a coisa" in capsys.readouterr().out


def test_pegar_perde_a_corrida_e_recusado_e_NAO_escreve_evento(tmp_path, monkeypatch, capsys):
    """A segunda sessão recebe a recusa DO SERVIDOR — e não deixa rastro falso."""
    montar(tmp_path, [tarefa()])
    sem_rede(monkeypatch)
    monkeypatch.setattr(
        fila.reservar, "reservar_intencao", lambda *a, **k: (False, "JÁ ESTÁ RESERVADA")
    )
    args = argparse.Namespace(tarefa="TAR-001", quem="sessao-b")
    assert fila.cmd_pegar(tmp_path, args) == 1
    assert not list((tmp_path / "fila" / "eventos").glob("*.json"))
    assert "RECUSADO PELO SERVIDOR" in capsys.readouterr().out


def test_pegar_tarefa_bloqueada_recusa_ANTES_de_ir_ao_servidor(tmp_path, monkeypatch):
    montar(tmp_path, [tarefa("001", "a"), tarefa("002", "b", deps=["TAR-001"])])
    sem_rede(monkeypatch)

    def nunca(*a, **k):
        raise AssertionError("não deveria ter chamado o servidor para tarefa bloqueada")

    monkeypatch.setattr(fila.reservar, "reservar_intencao", nunca)
    args = argparse.Namespace(tarefa="TAR-002", quem="sessao-b")
    assert fila.cmd_pegar(tmp_path, args) == 1


def test_pegar_tarefa_ja_reivindicada_no_servidor_recusa(tmp_path, monkeypatch):
    montar(tmp_path, [tarefa()])
    sem_rede(monkeypatch, reservas={"TAR-001"})

    def nunca(*a, **k):
        raise AssertionError("a reserva viva já dizia que é de outro")

    monkeypatch.setattr(fila.reservar, "reservar_intencao", nunca)
    args = argparse.Namespace(tarefa="TAR-001", quem="sessao-b")
    assert fila.cmd_pegar(tmp_path, args) == 1


def test_fila_invalida_para_qualquer_gesto(tmp_path, monkeypatch):
    """Fail-closed: com a fila quebrada, nem pegar, nem concluir — conserte antes."""
    t = tarefa()
    del t["despacho"]
    montar(tmp_path, [t])
    with pytest.raises(ErroDeInstrumentacao):
        fila._carregar_ou_parar(tmp_path)


# ---------------------------------------------------------------------------
# Concluir exige evidência
# ---------------------------------------------------------------------------


def test_concluir_sem_evidencia_recusa(tmp_path, monkeypatch, capsys):
    montar(tmp_path, [tarefa()], [evento()])
    monkeypatch.setattr(fila, "_soltar_reserva_se_houver", lambda *a: None)
    args = argparse.Namespace(tarefa="TAR-001", quem="sessao-a", evidencia="  ", verificado_em="")
    assert fila.cmd_concluir(tmp_path, args) == 1
    assert not list((tmp_path / "fila" / "eventos").glob("*concluida*"))
    assert "sem evidência" in capsys.readouterr().out


def test_concluir_com_evidencia_escreve_o_evento(tmp_path, monkeypatch):
    montar(tmp_path, [tarefa()], [evento()])
    monkeypatch.setattr(fila, "_soltar_reserva_se_houver", lambda *a: None)
    args = argparse.Namespace(
        tarefa="TAR-001", quem="sessao-a",
        evidencia="https://github.com/x/y/pull/9", verificado_em="2026-08-29",
    )
    assert fila.cmd_concluir(tmp_path, args) == 0
    escrito = list((tmp_path / "fila" / "eventos").glob("*-TAR-001-concluida.json"))
    assert len(escrito) == 1
    dados = json.loads(escrito[0].read_text(encoding="utf-8"))
    assert dados["evidencia"].endswith("/pull/9")
    assert dados["verificado_em"] == "2026-08-29"


def test_concluir_duas_vezes_recusa(tmp_path, monkeypatch):
    eventos = [evento(tipo="concluida", evidencia="PR #9", verificado_em="2026-08-29")]
    montar(tmp_path, [tarefa()], eventos)
    monkeypatch.setattr(fila, "_soltar_reserva_se_houver", lambda *a: None)
    args = argparse.Namespace(tarefa="TAR-001", quem="sessao-a", evidencia="PR #10", verificado_em="")
    assert fila.cmd_concluir(tmp_path, args) == 1
