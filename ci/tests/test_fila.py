"""Testes-guarda da FILA DE TRABALHO (ci/fila.py).

O que não pode deixar de morder, na ordem do que mais dói:

1. A corrida: duas sessões pegando a mesma tarefa → a segunda é RECUSADA, e
   nenhum evento é escrito para ela (a trava que os três consultores pediram).
2. Concluir sem evidência não existe — a lei do verde do livro, na fila.
3. Estado é sempre uma conta: ninguém escreve "status" em lugar nenhum.
4. A validação fail-closed que a muralha roda (`ci/muralha-da-fila.sh`).
5. Onde o comprovante NASCE (armadilhas/192, desde 30/08/2026): no espelho os
   gestos que escrevem RECUSAM, e `validar` diz em voz alta — em SOMBRA — o
   comprovante que o Git não conhece. Estes encenam a falha de verdade
   (armadilhas/132): repositório descartável real, com worktree ligado.

Nenhum teste toca a rede: o almoxarife é fingido, como em test_reservar.py —
a prova VIVA da trava (servidor de verdade recusando a segunda reserva) foi
feita à mão e está colada no PR que fez a fila nascer.
"""

from __future__ import annotations

import argparse
import json
import subprocess
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


# ---------------------------------------------------------------------------
# O elo com o placar: `move` (degrau 19, o grafo causal)
#
# A pergunta do quinto documento do Scale OS: "que resultado estratégico esta
# tarefa move?". O campo tem TRÊS estados de propósito, e os testes abaixo
# guardam a diferença entre eles — ausente (ninguém declarou) não é o mesmo
# que manutenção (declarou que não move número), e nenhum dos dois é um nome
# de cartão errado, que é o modo silencioso de a coisa apodrecer.
# ---------------------------------------------------------------------------


def com_cartoes(tmp_path, *nomes):
    """O placar de mentira: um arquivo por cartão, como em `painel/cartoes/`."""
    pasta = tmp_path / "painel" / "cartoes"
    pasta.mkdir(parents=True, exist_ok=True)
    for nome in nomes:
        (pasta / f"{nome}.json").write_text("{}", encoding="utf-8")
    return tmp_path


def test_move_ausente_passa(tmp_path):
    """As 123 tarefas anteriores a 04/09/2026 não declararam, e continuam válidas."""
    montar(tmp_path, [tarefa()])
    assert "move" not in tarefa()
    assert fila.cmd_validar(tmp_path) == 0


def test_move_manutencao_passa_sem_precisar_do_placar(tmp_path):
    montar(tmp_path, [tarefa(move=["manutencao"])])
    assert not (tmp_path / "painel" / "cartoes").exists()
    assert fila.cmd_validar(tmp_path) == 0


def test_move_com_cartao_que_existe_passa(tmp_path):
    montar(tmp_path, [tarefa(move=["compras-no-mes", "liberacoes-em-48h"])])
    com_cartoes(tmp_path, "compras-no-mes", "liberacoes-em-48h")
    assert fila.cmd_validar(tmp_path) == 0


def test_move_com_cartao_que_nao_existe_reprova(tmp_path):
    """O guarda que importa: nome de número inventado não entra na fila."""
    montar(tmp_path, [tarefa(move=["compras-no-mez"])])
    com_cartoes(tmp_path, "compras-no-mes")
    _, _, erros = carregar(tmp_path)
    assert any("compras-no-mez" in e and "não é cartão" in e for e in erros)
    assert fila.cmd_validar(tmp_path) == 1


def test_move_vazio_reprova_porque_ausencia_nao_e_manutencao(tmp_path):
    montar(tmp_path, [tarefa(move=[])])
    _, _, erros = carregar(tmp_path)
    assert any("'move' vazio" in e for e in erros)


def test_move_manutencao_nao_se_mistura_com_numero(tmp_path):
    montar(tmp_path, [tarefa(move=["manutencao", "compras-no-mes"])])
    com_cartoes(tmp_path, "compras-no-mes")
    _, _, erros = carregar(tmp_path)
    assert any("não se mistura" in e for e in erros)


def test_move_sem_pasta_de_cartoes_reprova_em_vez_de_deixar_passar(tmp_path):
    """Fail-closed: sem a lista de cartões o nome não pode ser conferido."""
    montar(tmp_path, [tarefa(move=["compras-no-mes"])])
    _, _, erros = carregar(tmp_path)
    assert any("não pode ser conferido" in e for e in erros)


def test_criar_recusa_move_invalido_ANTES_de_gastar_numero(tmp_path, monkeypatch, capsys):
    """Um erro de digitação não pode queimar um número do almoxarife."""
    montar(tmp_path, [])
    com_cartoes(tmp_path, "compras-no-mes")
    monkeypatch.setattr(fila, "_parar_se_for_o_espelho", lambda *a: None)

    def nunca(*a, **k):
        raise AssertionError("não deveria ter pedido número para um `move` inválido")

    monkeypatch.setattr(fila.reservar, "alocar_numero", nunca)
    args = argparse.Namespace(
        titulo="uma tarefa",
        toca=["ci"],
        depende_de=[],
        cria=[],
        move=["compras-no-mez"],
        evidencia_exigida="um PR",
        despacho="faça",
        despacho_arquivo="",
        origem="teste",
    )
    assert fila.cmd_criar(tmp_path, args) == 1
    saida = capsys.readouterr().out
    assert "RECUSADO" in saida
    assert "compras-no-mes" in saida  # a lista de cartões ajuda quem errou o nome
    assert not list((tmp_path / "fila" / "tarefas").glob("*.json"))


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
    e = estados_de(
        tmp_path,
        [tarefa()],
        [evento(tipo="bloqueada", detalhe="falta decisão do dono", espera="mantenedor")],
    )
    assert e["TAR-001"] == {
        "estado": fila.BLOQUEADA,
        "motivo": "falta decisão do dono",
        "quem": "sessao-a",
        "espera": "mantenedor",
    }


def test_bloqueada_por_evento_antigo_nao_inventa_quem_destrava(tmp_path):
    """Sem `espera` declarado, o estado sai com None — nunca com 'fila'.

    "Ninguém declarou" e "a fila resolve" são respostas diferentes, e fundi-las
    esconderia do dono uma parada que talvez fosse dele. Quem cobra a declaração
    é `cmd_validar`, em todo bloqueio vivo.
    """
    e = estados_de(tmp_path, [tarefa()], [evento(tipo="bloqueada", detalhe="travou")])
    assert e["TAR-001"]["espera"] is None


def test_concluida_e_terminal(tmp_path):
    eventos = [evento(tipo="concluida", evidencia="PR #9", verificado_em="2026-08-29")]
    assert estados_de(tmp_path, [tarefa()], eventos)["TAR-001"]["estado"] == fila.CONCLUIDA


def test_dependencia_aberta_bloqueia_por_conta(tmp_path):
    e = estados_de(tmp_path, [tarefa("001", "a"), tarefa("002", "b", deps=["TAR-001"])])
    # `espera` sai calculado como `fila`: esta trava se desfaz sozinha quando a
    # de cima terminar, e por isso nunca é assunto do mantenedor.
    assert e["TAR-002"] == {
        "estado": fila.BLOQUEADA,
        "motivo": "esperando TAR-001",
        "quem": None,
        "espera": fila.ESPERA_A_FILA,
    }


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
# Bloquear exige motivo — o verbo que faltava (04/09/2026)
# ---------------------------------------------------------------------------


def test_bloquear_sem_motivo_recusa_e_NAO_escreve_evento(tmp_path, monkeypatch, capsys):
    """A mesma lei do `concluir`: `validar` reprova `bloqueada` sem `detalhe`,
    então o balcão não pode deixar nascer um evento que a muralha vai recusar.
    Sem este guarda, o verbo novo seria uma fábrica de fila inválida."""
    montar(tmp_path, [tarefa()])
    monkeypatch.setattr(fila, "_soltar_reserva_se_houver", lambda *a: None)
    monkeypatch.setattr(fila, "_parar_se_for_o_espelho", lambda *a: None)
    args = argparse.Namespace(tarefa="TAR-001", quem="sessao-a", motivo="   ")
    assert fila.cmd_bloquear(tmp_path, args) == 1
    assert not list((tmp_path / "fila" / "eventos").glob("*bloqueada*"))
    assert "sem motivo" in capsys.readouterr().out


def test_bloquear_com_motivo_escreve_o_evento_e_o_estado_calculado_muda(tmp_path, monkeypatch):
    """A prova de ponta a ponta: o verbo escreve, e a CONTA do estado enxerga.

    Mede as duas coisas de propósito. Um evento escrito com o nome errado, ou
    com o motivo no campo errado, ainda produziria arquivo — e um teste que só
    olhasse a pasta passaria enquanto o quadro continuasse dizendo `na fila`.
    """
    montar(tmp_path, [tarefa()], [evento()])
    monkeypatch.setattr(fila, "_soltar_reserva_se_houver", lambda *a: None)
    monkeypatch.setattr(fila, "_parar_se_for_o_espelho", lambda *a: None)
    args = argparse.Namespace(
        tarefa="TAR-001", quem="sessao-a",
        motivo="espera o passo do mantenedor na VPS",
        espera=fila.ESPERA_O_MANTENEDOR,
    )
    assert fila.cmd_bloquear(tmp_path, args) == 0
    escrito = list((tmp_path / "fila" / "eventos").glob("*-TAR-001-bloqueada.json"))
    assert len(escrito) == 1
    dados = json.loads(escrito[0].read_text(encoding="utf-8"))
    assert dados["detalhe"] == "espera o passo do mantenedor na VPS"
    tarefas, eventos, erros = carregar(tmp_path)
    assert erros == [], erros
    estado = fila.calcular_estados(tarefas, eventos)["TAR-001"]
    assert estado["estado"] == fila.BLOQUEADA
    assert "VPS" in estado["motivo"]


def test_bloquear_tarefa_que_ja_terminou_recusa(tmp_path, monkeypatch, capsys):
    """Depois do fim, silêncio: evento após o fim reprova na muralha, e o
    balcão não escreve o que ele mesmo sabe que vai ser recusado."""
    montar(
        tmp_path,
        [tarefa()],
        [evento(), evento(tipo="concluida", hora="11:00:00",
                evidencia="https://github.com/x/y/pull/9", verificado_em="2026-08-29")],
    )
    monkeypatch.setattr(fila, "_soltar_reserva_se_houver", lambda *a: None)
    monkeypatch.setattr(fila, "_parar_se_for_o_espelho", lambda *a: None)
    args = argparse.Namespace(
        tarefa="TAR-001", quem="sessao-a", motivo="tarde demais",
        espera=fila.ESPERA_A_FILA,
    )
    assert fila.cmd_bloquear(tmp_path, args) == 1
    assert not list((tmp_path / "fila" / "eventos").glob("*bloqueada*"))
    assert "já terminou" in capsys.readouterr().out


def test_bloquear_solta_a_reserva_no_servidor(tmp_path, monkeypatch):
    """Quem bloqueia larga a tarefa. A reserva viva conta como `reivindicada`
    na vista ao vivo, e sozinha ela faria o quadro mostrar duas verdades
    diferentes sobre a mesma tarefa até a trava expirar sozinha em 3 horas."""
    montar(tmp_path, [tarefa()])
    monkeypatch.setattr(fila, "_parar_se_for_o_espelho", lambda *a: None)
    soltas = []
    monkeypatch.setattr(fila, "_soltar_reserva_se_houver", lambda raiz, tid: soltas.append(tid))
    args = argparse.Namespace(
        tarefa="TAR-001", quem="sessao-a", motivo="a porta não existe",
        espera=fila.ESPERA_A_FILA,
    )
    assert fila.cmd_bloquear(tmp_path, args) == 0
    assert soltas == ["TAR-001"]


def test_bloquear_recusa_no_espelho(tmp_path, monkeypatch, capsys):
    """Como `concluir`: o comprovante nasce na bancada, para embarcar no PR
    (armadilhas/192). `soltar` continua livre, porque é gesto de emergência."""
    montar(tmp_path, [tarefa()])
    monkeypatch.setattr(fila, "_soltar_reserva_se_houver", lambda *a: None)
    monkeypatch.setattr(
        fila, "_parar_se_for_o_espelho",
        lambda acao, raiz: f"🧱 RECUSADO: {acao} no clone principal",
    )
    args = argparse.Namespace(
        tarefa="TAR-001", quem="sessao-a", motivo="qualquer um",
        espera=fila.ESPERA_A_FILA,
    )
    assert fila.cmd_bloquear(tmp_path, args) == 1
    assert not list((tmp_path / "fila" / "eventos").glob("*bloqueada*"))
    assert "clone principal" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# QUEM DESTRAVA UMA PARADA — o campo `espera` (06/09/2026)
#
# O que estes guardam: que nenhuma tarefa PARADA fique sem dizer quem a tira
# dali. Sem isso o painel do dono volta a empilhar, no mesmo bloco de urgência,
# o que espera uma decisão dele e o que espera só a fila andar — que foi
# exatamente o estado medido em 06/09/2026 (27 paradas, 6 dele).
# ---------------------------------------------------------------------------


def test_parada_sem_dizer_quem_destrava_reprova(tmp_path, capsys):
    montar(tmp_path, [tarefa()], [evento(tipo="bloqueada", detalhe="travou")])
    assert fila.cmd_validar(tmp_path) == 1
    assert "quem destrava" in capsys.readouterr().out


def test_parada_que_declarou_quem_destrava_passa(tmp_path):
    montar(
        tmp_path,
        [tarefa()],
        [evento(tipo="bloqueada", detalhe="travou", espera="mantenedor")],
    )
    assert fila.cmd_validar(tmp_path) == 0


def test_bloqueio_ja_superado_nao_e_cobrado(tmp_path):
    """A régua é o estado de HOJE, não uma data de corte no código.

    Os 22 eventos `bloqueada` que a fila já tinha em tarefas que seguiram
    adiante são história encerrada, e cobrar deles exigiria reescrever evento —
    que esta fila não faz. O que não pode existir é tarefa PARADA sem dono.
    """
    montar(
        tmp_path,
        [tarefa()],
        [
            evento(tipo="bloqueada", hora="10:00:00", detalhe="travou"),
            evento(tipo="devolvida", hora="11:00:00"),
        ],
    )
    assert fila.cmd_validar(tmp_path) == 0


def test_dependencia_aberta_nao_precisa_declarar_nada(tmp_path):
    """Ela já sai calculada como `fila`: ninguém escreveu, ninguém precisa."""
    montar(tmp_path, [tarefa("001", "a"), tarefa("002", "b", deps=["TAR-001"])])
    assert fila.cmd_validar(tmp_path) == 0


def test_espera_com_valor_inventado_reprova(tmp_path):
    montar(
        tmp_path,
        [tarefa()],
        [evento(tipo="bloqueada", detalhe="travou", espera="talvez")],
    )
    _, _, erros = carregar(tmp_path)
    assert any("'talvez'" in e for e in erros)


def test_espera_fora_de_um_bloqueio_reprova(tmp_path):
    """Quem destrava só faz sentido para quem está travado."""
    montar(tmp_path, [tarefa()], [evento(espera="mantenedor")])
    _, _, erros = carregar(tmp_path)
    assert any("só existe em evento 'bloqueada'" in e for e in erros)


# ---------------------------------------------------------------------------
# Cancelar: o segundo estado que não tinha verbo (06/09/2026)
# ---------------------------------------------------------------------------


def test_cancelar_escreve_o_evento_e_o_estado_calculado_muda(tmp_path, monkeypatch):
    montar(tmp_path, [tarefa()], [evento()])
    monkeypatch.setattr(fila, "_soltar_reserva_se_houver", lambda *a: None)
    monkeypatch.setattr(fila, "_parar_se_for_o_espelho", lambda *a: None)
    args = argparse.Namespace(
        tarefa="TAR-001", quem="sessao-a", motivo="o plano mudou, substituta já criada"
    )
    assert fila.cmd_cancelar(tmp_path, args) == 0
    escrito = list((tmp_path / "fila" / "eventos").glob("*-TAR-001-cancelada.json"))
    assert len(escrito) == 1
    assert json.loads(escrito[0].read_text(encoding="utf-8"))["detalhe"].startswith("o plano")
    tarefas, eventos, erros = carregar(tmp_path)
    assert erros == [], erros
    assert fila.calcular_estados(tarefas, eventos)["TAR-001"]["estado"] == fila.CANCELADA


def test_cancelar_sem_motivo_recusa(tmp_path, monkeypatch, capsys):
    montar(tmp_path, [tarefa()])
    monkeypatch.setattr(fila, "_soltar_reserva_se_houver", lambda *a: None)
    monkeypatch.setattr(fila, "_parar_se_for_o_espelho", lambda *a: None)
    args = argparse.Namespace(tarefa="TAR-001", quem="sessao-a", motivo="   ")
    assert fila.cmd_cancelar(tmp_path, args) == 1
    assert not list((tmp_path / "fila" / "eventos").glob("*cancelada*"))
    assert "sem motivo" in capsys.readouterr().out


def test_cancelar_avisa_quem_vai_ficar_preso_para_sempre(tmp_path, monkeypatch, capsys):
    """Dependência só se destrava CONCLUÍDA: quem dependia da cancelada trava
    para sempre. Dizer isso antes é o que separa uma decisão de uma surpresa —
    foi assim que a TAR-060 caiu, em 31/08/2026."""
    montar(tmp_path, [tarefa("001", "a"), tarefa("002", "b", deps=["TAR-001"])])
    monkeypatch.setattr(fila, "_soltar_reserva_se_houver", lambda *a: None)
    monkeypatch.setattr(fila, "_parar_se_for_o_espelho", lambda *a: None)
    args = argparse.Namespace(tarefa="TAR-001", quem="sessao-a", motivo="não vai mais ser feita")
    assert fila.cmd_cancelar(tmp_path, args) == 0
    assert "TAR-002" in capsys.readouterr().out


def test_cancelar_tarefa_que_ja_terminou_recusa(tmp_path, monkeypatch, capsys):
    montar(
        tmp_path,
        [tarefa()],
        [evento(tipo="concluida", evidencia="https://github.com/x/y/pull/9",
                verificado_em="2026-08-29")],
    )
    monkeypatch.setattr(fila, "_soltar_reserva_se_houver", lambda *a: None)
    monkeypatch.setattr(fila, "_parar_se_for_o_espelho", lambda *a: None)
    args = argparse.Namespace(tarefa="TAR-001", quem="sessao-a", motivo="tarde demais")
    assert fila.cmd_cancelar(tmp_path, args) == 1
    assert not list((tmp_path / "fila" / "eventos").glob("*cancelada*"))
    assert "já terminou" in capsys.readouterr().out


def test_cancelar_recusa_no_espelho(tmp_path, monkeypatch, capsys):
    """Como `concluir` e `bloquear`: o comprovante nasce na bancada
    (armadilhas/192), senão o PR viaja sem ele."""
    montar(tmp_path, [tarefa()])
    monkeypatch.setattr(fila, "_soltar_reserva_se_houver", lambda *a: None)
    monkeypatch.setattr(
        fila, "_parar_se_for_o_espelho",
        lambda acao, raiz: f"🧱 RECUSADO: {acao} no clone principal",
    )
    args = argparse.Namespace(tarefa="TAR-001", quem="sessao-a", motivo="qualquer um")
    assert fila.cmd_cancelar(tmp_path, args) == 1
    assert not list((tmp_path / "fila" / "eventos").glob("*cancelada*"))
    assert "clone principal" in capsys.readouterr().out


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


# ---------------------------------------------------------------------------
# Onde o comprovante nasce — armadilhas/192 (TAR-018)
#
# Encenação de verdade: um clone principal (.git PASTA) e um worktree irmão
# (.git ARQUIVO), a mesma topologia que a muralha da pasta compartilhada
# distingue. Sem isso o teste seria sobre um mock, não sobre a decisão.
# ---------------------------------------------------------------------------


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", *args],
        cwd=cwd, check=True, capture_output=True,
    )


@pytest.fixture()
def espelho_e_bancada(tmp_path):
    """(clone principal, worktree irmão) — os dois com a fila montada."""
    principal = tmp_path / "principal"
    principal.mkdir()
    _git("init", "-b", "main", cwd=principal)
    _git("config", "user.email", "teste@teste", cwd=principal)
    _git("config", "user.name", "teste", cwd=principal)
    (principal / "leia.txt").write_text("oi", encoding="utf-8")
    _git("add", "leia.txt", cwd=principal)
    _git("commit", "-m", "genese", cwd=principal)
    bancada = tmp_path / "wt-fila-tarefa"
    _git("worktree", "add", str(bancada), "-b", "agent/fila/tarefa", cwd=principal)
    montar(principal, [tarefa()])
    montar(bancada, [tarefa()])
    return principal, bancada


def _args_pegar():
    return argparse.Namespace(tarefa="TAR-001", quem="sessao-b")


def test_pegar_NO_ESPELHO_recusa_e_NAO_escreve_o_comprovante(
    espelho_e_bancada, monkeypatch, capsys
):
    """O caso da armadilhas/192: o evento nascia no clone principal, numa pasta
    onde ninguém pode commitar, e nada acusava."""
    principal, _ = espelho_e_bancada
    sem_rede(monkeypatch)

    def nunca(*a, **k):
        raise AssertionError("nem devia ter chegado ao servidor: a pasta já estava errada")

    monkeypatch.setattr(fila.reservar, "reservar_intencao", nunca)
    assert fila.cmd_pegar(principal, _args_pegar()) == 1
    assert not list((principal / "fila" / "eventos").glob("*.json"))


def test_a_recusa_no_espelho_ENSINA_o_caminho(espelho_e_bancada, monkeypatch, capsys):
    """Recusa que não ensina vira robô parado. Ela precisa dizer três coisas:
    que a TAREFA não foi recusada, o rito do worktree, e a armadilha."""
    principal, _ = espelho_e_bancada
    sem_rede(monkeypatch)
    monkeypatch.setattr(fila.reservar, "reservar_intencao", lambda *a, **k: (True, "é sua"))
    fila.cmd_pegar(principal, _args_pegar())
    saida = capsys.readouterr().out
    assert "NÃO É RECUSA DA TAREFA" in saida
    assert "git worktree add" in saida
    assert "armadilhas/192" in saida


def test_pegar_NA_BANCADA_passa(espelho_e_bancada, monkeypatch):
    """O certo continua certo: no worktree, o comprovante nasce onde vai ser
    commitado."""
    _, bancada = espelho_e_bancada
    sem_rede(monkeypatch)
    monkeypatch.setattr(fila.reservar, "reservar_intencao", lambda *a, **k: (True, "é sua"))
    assert fila.cmd_pegar(bancada, _args_pegar()) == 0
    assert len(list((bancada / "fila" / "eventos").glob("*-TAR-001-reivindicada.json"))) == 1


def test_pegar_FORA_DE_CHECKOUT_GIT_passa(tmp_path, monkeypatch):
    """Pasta sem `.git` nenhum não é 'não consegui medir': é medição que deu
    'não há repositório aqui' — e sem repositório não há PR a perder."""
    montar(tmp_path, [tarefa()])
    sem_rede(monkeypatch)
    monkeypatch.setattr(fila.reservar, "reservar_intencao", lambda *a, **k: (True, "é sua"))
    assert fila.cmd_pegar(tmp_path, _args_pegar()) == 0


def test_criar_e_concluir_TAMBEM_recusam_no_espelho(espelho_e_bancada, monkeypatch):
    principal, _ = espelho_e_bancada
    monkeypatch.setattr(fila, "_soltar_reserva_se_houver", lambda *a: None)
    monkeypatch.setattr(fila.reservar, "alocar_numero", lambda *a, **k: "099")
    criar = argparse.Namespace(
        titulo="qualquer", toca=["admin"], depende_de=[], evidencia_exigida="PR",
        despacho="faça", despacho_arquivo="", origem="teste",
    )
    assert fila.cmd_criar(principal, criar) == 1
    concluir = argparse.Namespace(
        tarefa="TAR-001", quem="sessao-b", evidencia="PR #1", verificado_em="2026-08-30",
    )
    assert fila.cmd_concluir(principal, concluir) == 1
    assert not list((principal / "fila" / "eventos").glob("*.json"))
    assert len(list((principal / "fila" / "tarefas").glob("*.json"))) == 1


def test_soltar_CONTINUA_LIVRE_no_espelho(espelho_e_bancada, monkeypatch):
    """A fronteira declarada: devolver à fila uma tarefa presa é gesto de
    emergência, e emergência não pode depender de ter worktree."""
    principal, _ = espelho_e_bancada
    monkeypatch.setattr(fila, "_soltar_reserva_se_houver", lambda *a: None)
    args = argparse.Namespace(tarefa="TAR-001", quem="sessao-b", motivo="mudei de ideia")
    assert fila.cmd_soltar(principal, args) == 0


def test_nao_conseguir_medir_a_pasta_vira_ERROR_nunca_PASS(tmp_path, monkeypatch):
    """O terceiro estado: instrumento quebrado não vira permissão de escrever.

    Sem a cura, este mesmo teste falha na ASSERÇÃO (`DID NOT RAISE`) e não no
    monkeypatch — por isso o `raising=False` e a rede fingida: vermelho que
    morre montando o teste não prova decisão nenhuma (armadilhas/195).
    """
    montar(tmp_path, [tarefa()])
    sem_rede(monkeypatch)
    monkeypatch.setattr(fila.reservar, "reservar_intencao", lambda *a, **k: (True, "é sua"))

    def instrumento_quebrado(_caminho):
        raise OSError("o disco sumiu no meio da medição")

    monkeypatch.setattr(fila, "raiz_do_checkout", instrumento_quebrado, raising=False)
    with pytest.raises(ErroDeInstrumentacao):
        fila.cmd_pegar(tmp_path, _args_pegar())


# ---- a peça em SOMBRA: `validar` fala, e não reprova -----------------------


def test_validar_DIZ_o_comprovante_orfao_do_espelho_e_NAO_reprova(
    espelho_e_bancada, capsys
):
    """O falso-verde medido em 30/08/2026: com o comprovante fora, `validar`
    respondia '✅ Fila válida' e mais nada."""
    principal, _ = espelho_e_bancada
    orfao = evento()
    (principal / "fila" / "eventos" / f"{orfao['arquivo']}.json").write_text(
        json.dumps(orfao, ensure_ascii=False), encoding="utf-8"
    )
    assert fila.cmd_validar(principal) == 0  # SOMBRA: avisa, não reprova
    saida = capsys.readouterr().out
    assert "COMPROVANTE ÓRFÃO" in saida
    assert orfao["arquivo"] in saida
    assert "SOMBRA" in saida


def test_validar_na_bancada_lembra_de_commitar(espelho_e_bancada, capsys):
    _, bancada = espelho_e_bancada
    solto = evento()
    (bancada / "fila" / "eventos" / f"{solto['arquivo']}.json").write_text(
        json.dumps(solto, ensure_ascii=False), encoding="utf-8"
    )
    assert fila.cmd_validar(bancada) == 0
    saida = capsys.readouterr().out
    assert "fora do Git" in saida and "git add fila/eventos" in saida
    assert "COMPROVANTE ÓRFÃO" not in saida  # na bancada dá para commitar


def test_validar_com_tudo_commitado_fica_calado(espelho_e_bancada, capsys):
    """Aviso que grita sempre vira ruído que ninguém lê."""
    _, bancada = espelho_e_bancada
    ev = evento()
    (bancada / "fila" / "eventos" / f"{ev['arquivo']}.json").write_text(
        json.dumps(ev, ensure_ascii=False), encoding="utf-8"
    )
    _git("add", "fila", cwd=bancada)  # agora o Git conhece o comprovante
    assert fila.cmd_validar(bancada) == 0
    saida = capsys.readouterr().out
    assert "fora do Git" not in saida and "COMPROVANTE ÓRFÃO" not in saida


def test_validar_DIZ_quando_nao_conseguiu_conferir(tmp_path, monkeypatch, capsys):
    """'Não medi' se diz, não se esconde — mesmo em sombra, mesmo sem reprovar."""
    montar(tmp_path, [tarefa()])
    monkeypatch.setattr(
        fila, "comprovantes_que_o_git_nao_conhece", lambda raiz: None, raising=False
    )
    assert fila.cmd_validar(tmp_path) == 0
    assert "NÃO CONSEGUI CONFERIR" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# A imutabilidade do arquivo de tarefa — armadilhas/356 (TAR-206)
#
# "Nada se edita, corrigir é acrescentar" é lei desde 29/08/2026 e ficou sem
# ninguém que a fizesse valer até 05/09/2026. Estes testes são os DIFFS DE
# MENTIRA que o guarda tem de julgar, e eles rodam contra um repositório git de
# verdade, com base e ramo: o que se está medindo é o diff, e um diff fingido
# não provaria nada (armadilhas/132).
#
# A assimetria, que é o miolo do guarda, está aqui inteira:
#   tarefa nova .......... passa (criar não é editar)
#   só o `depende_de` .... passa (o único campo sem conserto append-only)
#   qualquer outro campo . REPROVA
#   tarefa apagada ....... REPROVA (apagar e recriar é editar por outra porta)
# ---------------------------------------------------------------------------


def _commitar(repo: Path, mensagem: str) -> None:
    _git("add", "-A", cwd=repo)
    _git("commit", "-m", mensagem, cwd=repo)


def _reescrever(repo: Path, nome: str, **campos) -> None:
    caminho = repo / "fila" / "tarefas" / f"{nome}.json"
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    dados.update(campos)
    caminho.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")


@pytest.fixture()
def fila_na_base(tmp_path):
    """Um repo com a TAR-001 já na `main`, e o ramo do agente pronto para mentir."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git("init", "-b", "main", cwd=repo)
    _git("config", "user.email", "teste@teste", cwd=repo)
    _git("config", "user.name", "teste", cwd=repo)
    montar(repo, [tarefa(deps=["TAR-009"])])
    _commitar(repo, "a fila nasce")
    _git("checkout", "-b", "agent/fila/mentira", cwd=repo)
    return repo


def test_mudar_o_titulo_de_tarefa_existente_REPROVA(fila_na_base):
    """O caso que mais dói: a tarefa muda debaixo de quem já a pegou."""
    _reescrever(fila_na_base, "001-exemplo", titulo="Outra coisa completamente")
    _commitar(fila_na_base, "mentira: o titulo virou outro")
    problemas = fila.conferir_imutabilidade(fila_na_base, "main")
    assert len(problemas) == 1
    assert "titulo" in problemas[0]
    assert fila.cmd_imutabilidade(fila_na_base, "main") == 1


def test_mudar_so_o_depende_de_PASSA(fila_na_base):
    """A exceção, e a razão dela: nenhum evento conserta uma corrente errada."""
    _reescrever(fila_na_base, "001-exemplo", depende_de=["TAR-004"])
    _commitar(fila_na_base, "conserta a corrente")
    assert fila.conferir_imutabilidade(fila_na_base, "main") == []
    assert fila.cmd_imutabilidade(fila_na_base, "main") == 0


def test_apagar_o_arquivo_da_tarefa_REPROVA(fila_na_base):
    """Apagar e recriar é editar por outra porta."""
    (fila_na_base / "fila" / "tarefas" / "001-exemplo.json").unlink()
    _commitar(fila_na_base, "mentira: some com a tarefa")
    problemas = fila.conferir_imutabilidade(fila_na_base, "main")
    assert len(problemas) == 1
    assert "APAGADO" in problemas[0]
    assert fila.cmd_imutabilidade(fila_na_base, "main") == 1


def test_tarefa_nova_passa_livre(fila_na_base):
    """Criar não é editar — senão o guarda travaria a fila inteira."""
    caminho = fila_na_base / "fila" / "tarefas" / "002-outra.json"
    caminho.write_text(
        json.dumps(tarefa("002", "outra"), ensure_ascii=False), encoding="utf-8"
    )
    _commitar(fila_na_base, "tarefa nova")
    assert fila.conferir_imutabilidade(fila_na_base, "main") == []


def test_renomear_o_arquivo_da_tarefa_REPROVA(fila_na_base):
    """Renomear é a terceira porta da mesma edição: `--no-renames` a desdobra
    em remoção mais adição, e a remoção reprova."""
    tarefas = fila_na_base / "fila" / "tarefas"
    (tarefas / "001-exemplo.json").rename(tarefas / "001-com-outro-nome.json")
    _commitar(fila_na_base, "mentira: renomeia a tarefa")
    problemas = fila.conferir_imutabilidade(fila_na_base, "main")
    assert any("APAGADO" in p for p in problemas)


def test_a_recusa_ENSINA_o_caminho_certo(fila_na_base, capsys):
    """Recusa que não ensina vira recusa contornada."""
    _reescrever(fila_na_base, "001-exemplo", despacho="outro despacho qualquer")
    _commitar(fila_na_base, "mentira: reescreve o despacho")
    assert fila.cmd_imutabilidade(fila_na_base, "main") == 1
    saida = capsys.readouterr().out
    assert "depende_de" in saida
    assert "fila.py criar" in saida
    assert "armadilhas/356" in saida


def test_sem_repositorio_git_e_ERROR_e_nao_um_OK(tmp_path):
    """Não medir nunca é passar (RETROSPECTIVA-FASE-D §1)."""
    with pytest.raises(ErroDeInstrumentacao):
        fila.cmd_imutabilidade(tmp_path, "main")


def test_base_que_nao_existe_e_ERROR(fila_na_base):
    with pytest.raises(ErroDeInstrumentacao):
        fila.conferir_imutabilidade(fila_na_base, "uma-base-que-nunca-existiu")


_NL = chr(10)


# ---------------------------------------------------------------------------
# O EVENTO "CONCLUÍDA" PELA PORTA DO POUSO, EM SOMBRA (06/09/2026)
#
# O buraco que ela mede: o rito manda pedir pouso e ir embora, então o evento
# de conclusão depende de o robô ainda estar vivo quando o merge acontece.
# Estes testes provam as cinco respostas da sombra e, acima de tudo, que ela
# NÃO GRAVA NADA — é isso que a separa da versão graduada.
# ---------------------------------------------------------------------------


def _sombra(raiz, **muda):
    padrao = dict(
        numero=1200,
        titulo="ci: o evento pela porta (TAR-001)",
        corpo="",
        ramo="agent/ci/evento-pela-porta",
        url="https://github.com/dono/repo/pull/1200",
        sha_do_merge="abcdef1234567890" + "0" * 24,
        arquivos_do_diff=[],
        agora=fila.datetime(2026, 9, 6, 14, 30, 5, tzinfo=fila.timezone.utc),
    )
    padrao.update(muda)
    return fila.evento_de_conclusao_em_sombra(raiz, **padrao)


def _remessa_do_evento(dados):
    corpo = json.dumps(dados, ensure_ascii=False, indent=2)
    return {
        "filename": f"fila/eventos/{dados['arquivo']}.json",
        "patch": "@@ -0,0 +1 @@" + _NL + _NL.join("+" + linha for linha in corpo.splitlines()),
    }


def test_pr_que_cita_tarefa_reivindicada_gera_o_evento_com_os_seis_campos(tmp_path):
    """(a) O caso que a regra existe para cobrir."""
    raiz = montar(tmp_path, [tarefa()], [evento(quem="despacho-ci-0609")])
    achados = _sombra(raiz)
    assert [a["desfecho"] for a in achados] == [fila.SOMBRA_GERARIA]
    gerado = achados[0]["evento"]
    assert gerado["tarefa"] == "TAR-001"
    assert gerado["evento"] == "concluida"
    assert gerado["quando"] == "2026-09-06T14:30:05+00:00"
    assert gerado["quem"] == "despacho-ci-0609"
    assert gerado["evidencia"] == (
        "https://github.com/dono/repo/pull/1200 (merge abcdef123456)"
    )
    assert gerado["verificado_em"] == "2026-09-06"
    assert "PR #1200" in gerado["detalhe"]
    assert "https://github.com/dono/repo/pull/1200" in gerado["detalhe"]
    assert gerado["arquivo"] == "20260906-143005-TAR-001-concluida"


def test_o_evento_gerado_pela_porta_passa_na_validacao_da_propria_fila(tmp_path):
    """De que serve gerar um evento que a fila recusaria? Gravado à mão no
    lugar certo, ele tem de passar por `carregar_eventos` sem um erro."""
    raiz = montar(tmp_path, [tarefa()], [evento(quem="despacho-ci-0609")])
    gerado = _sombra(raiz)[0]["evento"]
    caminho = raiz / "fila" / "eventos" / f"{gerado['arquivo']}.json"
    caminho.write_text(json.dumps(gerado, ensure_ascii=False), encoding="utf-8")
    tarefas, _, erros = carregar(raiz)
    assert erros == []
    assert fila.calcular_estados(tarefas, carregar(raiz)[1])["TAR-001"]["estado"] == (
        fila.CONCLUIDA
    )


def test_a_sombra_nao_grava_nada_no_disco(tmp_path):
    """O que a separa da versão graduada. Se este teste cair, a regra passou a
    escrever no livro da fila sem ter graduado."""
    raiz = montar(tmp_path, [tarefa()], [evento(quem="despacho-ci-0609")])
    antes = sorted(p.name for p in (raiz / "fila" / "eventos").glob("*.json"))
    _sombra(raiz)
    depois = sorted(p.name for p in (raiz / "fila" / "eventos").glob("*.json"))
    assert antes == depois


def test_pr_sem_tarefa_citada_e_silencio_total(tmp_path):
    """(b) Nem medir: a maioria dos PRs não atende tarefa nenhuma."""
    raiz = montar(tmp_path, [tarefa()], [evento()])
    assert _sombra(raiz, titulo="ci: um ajuste qualquer", ramo="agent/ci/ajuste") == []


def test_tarefa_que_ninguem_pegou_nao_vira_evento(tmp_path):
    """(c) Estado é uma conta: sem reivindicação, a porta não conclui nada."""
    raiz = montar(tmp_path, [tarefa()], [])
    achados = _sombra(raiz)
    assert achados[0]["desfecho"] == fila.SOMBRA_SILENCIO
    assert "na fila" in achados[0]["motivo"]


def test_tarefa_ja_concluida_antes_deste_pr_nao_vira_evento(tmp_path):
    """(c) Depois do terminal, silêncio: evento após concluída reescreveria a
    história, e a própria `carregar_eventos` recusaria o arquivo."""
    raiz = montar(
        tmp_path,
        [tarefa()],
        [
            evento(),
            evento(
                tipo="concluida",
                hora="11:00:00",
                evidencia="https://exemplo.invalido/pr/1",
                verificado_em="2026-08-29",
            ),
        ],
    )
    achados = _sombra(raiz)
    assert achados[0]["desfecho"] == fila.SOMBRA_SILENCIO
    assert "conclu" in achados[0]["motivo"]


def test_evento_que_ja_viaja_no_pr_e_ja_existe_nada_a_fazer(tmp_path):
    """(d) O caso comum de hoje: o robô escreveu o evento à mão no ramo. A
    pista não vê o ramo no disco, só o diff da API."""
    raiz = montar(tmp_path, [tarefa()], [evento()])
    a_bordo = evento(
        tipo="concluida",
        hora="12:00:00",
        evidencia="https://github.com/dono/repo/pull/1200",
        verificado_em="2026-09-06",
    )
    achados = _sombra(raiz, arquivos_do_diff=[_remessa_do_evento(a_bordo)])
    assert achados[0]["desfecho"] == fila.SOMBRA_JA_EXISTE
    assert achados[0]["evento"] is None


def test_reivindicacao_que_viaja_no_proprio_pr_conta(tmp_path):
    """O caminho normal: o robô pega a tarefa na bancada, e o evento de
    reivindicação só chega à `main` com este merge. A porta lê o diff."""
    raiz = montar(tmp_path, [tarefa()], [])
    a_bordo = evento(quem="despacho-ci-0609")
    achados = _sombra(raiz, arquivos_do_diff=[_remessa_do_evento(a_bordo)])
    assert achados[0]["desfecho"] == fila.SOMBRA_GERARIA
    assert achados[0]["evento"]["quem"] == "despacho-ci-0609"


def test_tarefa_citada_que_nao_existe_na_fila_e_silencio_com_motivo(tmp_path):
    raiz = montar(tmp_path, [tarefa()], [evento()])
    achados = _sombra(raiz, titulo="ci: algo (TAR-777)")
    assert achados[0]["tarefa"] == "TAR-777"
    assert achados[0]["desfecho"] == fila.SOMBRA_SILENCIO
    assert "não existe na fila" in achados[0]["motivo"]


def test_fila_invalida_no_disco_e_silencio_e_nunca_um_evento(tmp_path):
    """Não medir nunca é permissão (INV-CI01), nem para uma sombra."""
    raiz = montar(tmp_path, [tarefa()], [])
    (raiz / "fila" / "eventos" / "quebrado.json").write_text("{", encoding="utf-8")
    achados = _sombra(raiz)
    assert achados[0]["desfecho"] == fila.SOMBRA_SILENCIO
    assert "inválida" in achados[0]["motivo"]


def test_bloqueada_nao_vira_concluida_pela_porta(tmp_path):
    raiz = montar(
        tmp_path,
        [tarefa()],
        [evento(), evento(tipo="bloqueada", hora="11:00:00", detalhe="falta a chave")],
    )
    achados = _sombra(raiz)
    assert achados[0]["desfecho"] == fila.SOMBRA_SILENCIO
    assert "bloqueada" in achados[0]["motivo"]


def test_diff_que_nao_e_evento_da_fila_e_ignorado():
    """A leitura do diff não pode confundir qualquer JSON com um evento. Cada
    linha aqui é um sósia que já poderia aparecer num PR de verdade."""
    de_verdade = json.dumps(evento(tipo="concluida"), ensure_ascii=False)
    lixo = [
        # formato de evento, PASTA errada: registro do livro não é evento da fila
        {"filename": "painel/registros/20260906-001.json", "patch": "+" + de_verdade},
        # pasta certa, patch que não decodifica (diff truncado pela API)
        {"filename": "fila/eventos/x.json", "patch": "+isto nao e json"},
        # pasta certa, JSON válido que não é evento nenhum
        {"filename": "fila/eventos/y.json", "patch": '+{"tipo": "nota"}'},
        # evento REMOVIDO: linha que sai do diff não é fato que entra
        {"filename": "fila/eventos/z.json", "patch": "-" + de_verdade},
    ]
    assert fila.eventos_no_diff(lixo) == []
