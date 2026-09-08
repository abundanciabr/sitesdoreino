import argparse
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import reservar
import sessao
from test_fila import evento, montar, sem_rede, tarefa
from test_sessao import MundoFalso, plano_de_teste

import fila


def test_branch_vazia_nao_autoriza_reusar_bancada():
    plano = plano_de_teste()
    mundo = MundoFalso(
        plano, worktree_list=f"worktree {plano.worktree.as_posix()}\n", branch_atual=""
    )
    mundo.existentes.add(str(plano.worktree / ".git").lower())
    with pytest.raises(sessao.ErroDeSessao):
        mundo.sessao().preparar_worktree("git")


def test_reserva_propria_valida_dono_expiracao_e_tipo(tmp_path, monkeypatch):
    dono = reservar.identidade_da_bancada(tmp_path)
    corpo = {
        "tipo": "intencao",
        "chave": "tarefa-TAR-001",
        "dono": dono,
        "expira_em": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    }
    monkeypatch.setattr(
        reservar,
        "executar",
        lambda *a, **k: SimpleNamespace(
            stdout="a" * 40 + "\trefs/reservas/tarefa-TAR-001\n"
            if a[0][1] == "ls-remote"
            else json.dumps(corpo)
        ),
    )
    assert reservar.confirmar_intencao(tmp_path, "tarefa-TAR-001")
    corpo["tipo"] = "numero"
    assert not reservar.confirmar_intencao(tmp_path, "tarefa-TAR-001")
    corpo["tipo"] = "intencao"
    corpo["chave"] = "outra"
    assert not reservar.confirmar_intencao(tmp_path, "tarefa-TAR-001")
    corpo["chave"] = "tarefa-TAR-001"
    corpo.pop("dono")
    assert not reservar.confirmar_intencao(tmp_path, "tarefa-TAR-001")
    corpo["dono"] = "outra"
    assert not reservar.confirmar_intencao(tmp_path, "tarefa-TAR-001")
    corpo["dono"] = dono
    corpo["expira_em"] = "2020-01-01T00:00:00+00:00"
    assert not reservar.confirmar_intencao(tmp_path, "tarefa-TAR-001")


def test_repetir_pegar_preserva_evento_e_retoma_sem_reservar(tmp_path, monkeypatch):
    montar(tmp_path, [tarefa()], [evento(quem="sessao-a")])
    sem_rede(monkeypatch, reservas={"TAR-001"})
    monkeypatch.setattr(reservar, "confirmar_intencao", lambda *a: True)
    monkeypatch.setattr(
        reservar, "reservar_intencao", lambda *a, **k: pytest.fail("duplicou reserva")
    )
    antes = {p: p.read_bytes() for p in (tmp_path / "fila/eventos").glob("*")}
    assert (
        fila.cmd_pegar(tmp_path, argparse.Namespace(tarefa="TAR-001", quem="sessao-a"))
        == 0
    )
    assert antes == {p: p.read_bytes() for p in (tmp_path / "fila/eventos").glob("*")}


def test_interrupcao_apos_reserva_reconstitui_evento_uma_vez(tmp_path, monkeypatch):
    montar(tmp_path, [tarefa()])
    sem_rede(monkeypatch, reservas={"TAR-001"})
    monkeypatch.setattr(reservar, "confirmar_intencao", lambda *a: True)
    monkeypatch.setattr(
        reservar, "reservar_intencao", lambda *a, **k: pytest.fail("duplicou reserva")
    )
    args = argparse.Namespace(tarefa="TAR-001", quem="sessao-a")
    assert fila.cmd_pegar(tmp_path, args) == 0
    assert fila.cmd_pegar(tmp_path, args) == 0
    assert len(list((tmp_path / "fila/eventos").glob("*reivindicada.json"))) == 1


@pytest.mark.parametrize(
    "dono,quem,tipo",
    [
        (False, "sessao-a", "reivindicada"),
        (True, "outra", "reivindicada"),
        (True, "sessao-a", "bloqueada"),
        (True, "sessao-a", "concluida"),
    ],
)
def test_retomada_nao_contorna_dono_nem_estado(tmp_path, monkeypatch, dono, quem, tipo):
    montar(
        tmp_path,
        [tarefa()],
        [
            evento(
                tipo=tipo,
                quem=quem,
                **(
                    {"detalhe": "bloqueio", "espera": "mantenedor"}
                    if tipo == "bloqueada"
                    else {"evidencia": "PR #1", "verificado_em": "2026-08-29"}
                    if tipo == "concluida"
                    else {}
                ),
            )
        ],
    )
    sem_rede(monkeypatch, reservas={"TAR-001"})
    monkeypatch.setattr(reservar, "confirmar_intencao", lambda *a: dono)
    assert (
        fila.cmd_pegar(tmp_path, argparse.Namespace(tarefa="TAR-001", quem="sessao-a"))
        == 1
    )


def test_comprovante_da_propria_tarefa_nao_impede_abertura(tmp_path):
    plano = plano_de_teste(
        raiz=tmp_path / "repo", sobe_ambiente=False, tarefa_da_fila="TAR-001"
    )
    caminho = plano.worktree / "fila/eventos/20260908-120000-TAR-001-reivindicada.json"
    caminho.parent.mkdir(parents=True)
    caminho.write_text(
        json.dumps(
            {
                "tarefa": "TAR-001",
                "quem": plano.quem_no_balcao,
                "evento": "reivindicada",
            }
        ),
        encoding="utf-8",
    )
    mundo = MundoFalso(
        plano, porcelain="?? " + caminho.relative_to(plano.worktree).as_posix()
    )
    texto = mundo.sessao().rodar()
    assert "comprovante" in texto
    assert "git status: limpo" not in texto
    assert caminho.is_file()


def test_rede_indisponivel_na_retomada_nao_e_sucesso(tmp_path, monkeypatch):
    from _nucleo import ErroDeInstrumentacao

    def falhar(*a, **k):
        raise ErroDeInstrumentacao(
            "rede indisponível", "repita após restaurar o acesso"
        )

    monkeypatch.setattr(reservar, "executar", falhar)
    with pytest.raises(ErroDeInstrumentacao):
        reservar.confirmar_intencao(tmp_path, "tarefa-TAR-001")


def test_comprovante_alheio_ou_modificado_nao_e_ignorado(tmp_path):
    plano = plano_de_teste(
        raiz=tmp_path / "repo", sobe_ambiente=False, tarefa_da_fila="TAR-001"
    )
    caminho = plano.worktree / "fila/eventos/teste.json"
    caminho.parent.mkdir(parents=True)
    caminho.write_text(
        json.dumps(
            {
                "tarefa": "TAR-002",
                "quem": plano.quem_no_balcao,
                "evento": "reivindicada",
            }
        ),
        encoding="utf-8",
    )
    original = caminho.read_bytes()
    mundo = MundoFalso(plano, porcelain="?? fila/eventos/teste.json")
    with pytest.raises(sessao.ErroDeSessao):
        mundo.sessao().rodar()
    assert caminho.read_bytes() == original
