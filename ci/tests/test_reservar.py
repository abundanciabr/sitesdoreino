"""O ALMOXARIFE — provas de que a trava é trava, e não teatro.

Todos rodam **sem rede**: o `git push` é injetado. Um guarda cuja única prova
dependesse do GitHub de verdade não conseguiria exercitar justamente os casos
que decidem se ele presta — a corrida perdida, o "Everything up-to-date" e a
rede caída — porque esses estados não se produzem sob encomenda.

O caso mais importante do arquivo é o `everything_up_to_date`. Ele existe porque
a medição contra o repositório real, ANTES de este módulo ser escrito, mostrou
que empurrar um commit que já é o valor da referência devolve **exit 0** sem
conferir o `--force-with-lease`. Uma trava que devolve sucesso sem conferir nada
é pior que trava nenhuma: ela é acreditada.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

CI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CI))

import reservar  # noqa: E402
from _nucleo import ErroDeInstrumentacao  # noqa: E402

AGORA = datetime(2026, 8, 28, 18, 0, tzinfo=timezone.utc)


class Saida:
    """O que `subprocess.run` devolveria, sem rodar nada."""

    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


def fingir_git(monkeypatch, respostas):
    """Injeta o `git` de escrita e grava os comandos vistos."""
    vistos = []

    def falso(raiz, args):
        vistos.append(args)
        resposta = respostas.pop(0) if isinstance(respostas, list) else respostas
        return resposta

    monkeypatch.setattr(reservar, "_git", falso)
    return vistos


def fingir_leitura(monkeypatch, mensagens):
    """Injeta o `git` de leitura (`executar`) e grava as mensagens de commit."""

    class Exec:
        def __init__(self, stdout):
            self.stdout = stdout

    def falso(comando, **kwargs):
        if comando[1] == "commit-tree":
            mensagens.append(comando[-1])
            return Exec("cafe" * 10)
        return Exec("beef" * 10)

    monkeypatch.setattr(reservar, "executar", falso)


# ---------------------------------------------------------------------------
# A trava que não pode ser teatro
# ---------------------------------------------------------------------------


def test_everything_up_to_date_e_ERRO_nunca_vitoria(tmp_path, monkeypatch):
    """Exit 0 sem o lease ter sido conferido não é vitória — é o falso-verde.

    Medido no repositório real: commit idêntico ⇒ 'Everything up-to-date',
    exit 0, e o --force-with-lease NEM É AVALIADO. Duas sessões sairiam daqui
    achando que ganharam a mesma reserva.
    """
    fingir_leitura(monkeypatch, [])
    fingir_git(monkeypatch, Saida(0, stdout="Everything up-to-date"))
    with pytest.raises(ErroDeInstrumentacao) as erro:
        reservar.criar_ref_atomica(tmp_path, "refs/numeros/registro/x/001", {})
    assert "nonce" in erro.value.detalhe


def test_toda_tentativa_carrega_um_nonce_diferente(tmp_path, monkeypatch):
    """Sem nonce os SHAs coincidem e a trava deixa de ser conferida."""
    mensagens: list[str] = []
    fingir_leitura(monkeypatch, mensagens)
    fingir_git(monkeypatch, Saida(0, stdout="* [new reference]"))

    reservar.criar_ref_atomica(tmp_path, "refs/x/1", {"tipo": "numero"})
    reservar.criar_ref_atomica(tmp_path, "refs/x/1", {"tipo": "numero"})

    assert len(mensagens) == 2
    assert all("nonce" in m for m in mensagens)
    assert mensagens[0] != mensagens[1], "dois commits iguais ⇒ dois vencedores"


def test_recusa_do_servidor_e_derrota_nao_excecao(tmp_path, monkeypatch):
    fingir_leitura(monkeypatch, [])
    fingir_git(monkeypatch, Saida(1, stderr="! [rejected] (stale info)"))
    assert reservar.criar_ref_atomica(tmp_path, "refs/x/1", {}) is False


def test_rede_caida_NAO_vira_ocupado(tmp_path, monkeypatch):
    """A distinção que evita queimar números que ninguém pegou.

    "Não consegui perguntar" tratado como "está ocupado" faria o laço pular
    números livres — e o robô sairia com um número mais alto do que devia,
    sem ninguém perceber.
    """
    fingir_leitura(monkeypatch, [])
    fingir_git(monkeypatch, Saida(128, stderr="fatal: unable to access ... Could not resolve host"))
    with pytest.raises(ErroDeInstrumentacao) as erro:
        reservar.criar_ref_atomica(tmp_path, "refs/x/1", {})
    assert "não saber" in erro.value.detalhe


def test_git_ausente_para_com_mensagem(tmp_path, monkeypatch):
    def sem_git(*a, **k):
        raise FileNotFoundError("git")

    monkeypatch.setattr(subprocess, "run", sem_git)
    with pytest.raises(ErroDeInstrumentacao):
        reservar._git(tmp_path, ["push"])


# ---------------------------------------------------------------------------
# A alocação
# ---------------------------------------------------------------------------


def preparar_pastas(tmp_path, registros=(), armadilhas=()):
    (tmp_path / "painel" / "registros").mkdir(parents=True)
    (tmp_path / "armadilhas").mkdir()
    for nome in registros:
        (tmp_path / "painel" / "registros" / nome).write_text("x", encoding="utf-8")
    for nome in armadilhas:
        (tmp_path / "armadilhas" / nome).write_text("x", encoding="utf-8")


def test_alocar_devolve_o_numero_que_GANHOU_nao_o_que_pediu(tmp_path, monkeypatch):
    """Perdeu a corrida do 002? Então o número é o 003 — e é esse que sai."""
    preparar_pastas(tmp_path, registros=["20260828-001-a.js"])
    monkeypatch.setattr(reservar, "refs_existentes", lambda *a, **k: [])
    tentativas = iter([False, True])
    monkeypatch.setattr(
        reservar, "criar_ref_atomica", lambda *a, **k: next(tentativas)
    )
    assert reservar.alocar_numero(tmp_path, "registro", agora=AGORA) == "003"


def test_armadilha_nunca_reusa_numero_aposentado(tmp_path, monkeypatch):
    """`armadilhas/085`: número vago no meio está aposentado e ainda é citado."""
    preparar_pastas(tmp_path, armadilhas=["003-a.md", "153-z.md", "INDICE.md"])
    monkeypatch.setattr(reservar, "refs_existentes", lambda *a, **k: [])
    monkeypatch.setattr(reservar, "criar_ref_atomica", lambda *a, **k: True)
    assert reservar.alocar_numero(tmp_path, "armadilha", agora=AGORA) == "154"


def test_tarefa_nunca_reusa_numero(tmp_path, monkeypatch):
    """A fila segue a política da armadilha: TAR concluída continua citada."""
    (tmp_path / "fila" / "tarefas").mkdir(parents=True)
    (tmp_path / "fila" / "tarefas" / "002-a.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(reservar, "refs_existentes", lambda *a, **k: [])
    monkeypatch.setattr(reservar, "criar_ref_atomica", lambda *a, **k: True)
    assert reservar.alocar_numero(tmp_path, "tarefa", agora=AGORA) == "003"


def test_tarefa_sem_pasta_ainda_conta_as_reservas_do_servidor(tmp_path, monkeypatch):
    """No dia em que a fila nasce a pasta não existe — e os números já
    reservados por outra sessão continuam valendo (não é erro, é o começo)."""
    monkeypatch.setattr(
        reservar, "refs_existentes", lambda *a, **k: ["refs/numeros/tarefa/001"]
    )
    monkeypatch.setattr(reservar, "criar_ref_atomica", lambda *a, **k: True)
    assert reservar.alocar_numero(tmp_path, "tarefa", agora=AGORA) == "002"


def test_registro_preenche_buraco_do_dia(tmp_path, monkeypatch):
    preparar_pastas(tmp_path, registros=["20260828-001-a.js", "20260828-003-c.js"])
    monkeypatch.setattr(reservar, "refs_existentes", lambda *a, **k: [])
    monkeypatch.setattr(reservar, "criar_ref_atomica", lambda *a, **k: True)
    assert reservar.alocar_numero(tmp_path, "registro", agora=AGORA) == "002"


def test_reserva_ainda_nao_commitada_conta_como_ocupada(tmp_path, monkeypatch):
    """A janela que abriu as colisões: número reservado mas ainda sem arquivo."""
    preparar_pastas(tmp_path, registros=["20260828-001-a.js"])
    monkeypatch.setattr(
        reservar,
        "refs_existentes",
        lambda *a, **k: ["refs/numeros/registro/20260828/002"],
    )
    monkeypatch.setattr(reservar, "criar_ref_atomica", lambda *a, **k: True)
    assert reservar.alocar_numero(tmp_path, "registro", agora=AGORA) == "003"


# ---------------------------------------------------------------------------
# O RECIBO — a prova local de que este número veio do almoxarife
# ---------------------------------------------------------------------------


def ler_caderninho(tmp_path) -> list[dict]:
    linhas = []
    for arquivo in (tmp_path / ".git" / "telemetria-dos-robos").glob("*.jsonl"):
        for linha in arquivo.read_text(encoding="utf-8").splitlines():
            if linha.strip():
                linhas.append(json.loads(linha))
    return linhas


def recibos(tmp_path) -> list[dict]:
    return [l for l in ler_caderninho(tmp_path) if l["evento"] == "numero_reservado"]


def test_alocar_deixa_recibo_no_caderninho(tmp_path, monkeypatch):
    """Sem recibo, o gancho da lição teria de bater na rede a cada Write — e um
    gancho que bate na rede é um gancho que alguém desliga."""
    (tmp_path / ".git").mkdir()
    preparar_pastas(tmp_path, registros=["20260828-001-a.js"])
    monkeypatch.setattr(reservar, "refs_existentes", lambda *a, **k: [])
    monkeypatch.setattr(reservar, "criar_ref_atomica", lambda *a, **k: True)

    assert reservar.alocar_numero(tmp_path, "registro", agora=AGORA) == "002"

    assert len(recibos(tmp_path)) == 1
    recibo = recibos(tmp_path)[0]
    assert recibo["superficie"] == "registro"
    assert recibo["numero"] == "002"
    assert recibo["dia"] == "20260828"
    assert recibo["bancada"] == reservar.bancada(tmp_path)


def test_recibo_leva_o_numero_que_GANHOU_nao_o_que_pediu(tmp_path, monkeypatch):
    """Recibo do número errado é pior que recibo nenhum: ele calaria o gancho
    justamente no arquivo que colide."""
    (tmp_path / ".git").mkdir()
    preparar_pastas(tmp_path, registros=["20260828-001-a.js"])
    monkeypatch.setattr(reservar, "refs_existentes", lambda *a, **k: [])
    tentativas = iter([False, True])
    monkeypatch.setattr(reservar, "criar_ref_atomica", lambda *a, **k: next(tentativas))

    assert reservar.alocar_numero(tmp_path, "registro", agora=AGORA) == "003"
    assert [r["numero"] for r in recibos(tmp_path)] == ["003"]


def test_recusa_do_servidor_nao_deixa_recibo(tmp_path, monkeypatch):
    """Perder a corrida não é ganhar número nenhum, e o caderninho não pode
    dizer o contrário."""
    (tmp_path / ".git").mkdir()
    preparar_pastas(tmp_path)
    monkeypatch.setattr(reservar, "refs_existentes", lambda *a, **k: [])
    monkeypatch.setattr(reservar, "criar_ref_atomica", lambda *a, **k: False)
    with pytest.raises(ErroDeInstrumentacao):
        reservar.alocar_numero(tmp_path, "registro", agora=AGORA)
    assert recibos(tmp_path) == []


def test_superficie_desconhecida_para_em_vez_de_chutar(tmp_path):
    with pytest.raises(ErroDeInstrumentacao):
        reservar.alocar_numero(tmp_path, "sei-la", agora=AGORA)


def test_pasta_ausente_para(tmp_path, monkeypatch):
    monkeypatch.setattr(reservar, "refs_existentes", lambda *a, **k: [])
    with pytest.raises(ErroDeInstrumentacao):
        reservar.alocar_numero(tmp_path, "registro", agora=AGORA)


def test_desiste_depois_de_muitas_recusas_em_vez_de_girar_para_sempre(
    tmp_path, monkeypatch
):
    preparar_pastas(tmp_path)
    monkeypatch.setattr(reservar, "refs_existentes", lambda *a, **k: [])
    monkeypatch.setattr(reservar, "criar_ref_atomica", lambda *a, **k: False)
    with pytest.raises(ErroDeInstrumentacao) as erro:
        reservar.alocar_numero(tmp_path, "registro", agora=AGORA)
    assert "listar" in erro.value.detalhe


# ---------------------------------------------------------------------------
# A intenção (Classe 5)
# ---------------------------------------------------------------------------


def test_intencao_perdida_explica_que_o_mecanismo_funcionou(tmp_path, monkeypatch):
    monkeypatch.setattr(reservar, "criar_ref_atomica", lambda *a, **k: False)
    ganhou, recado = reservar.reservar_intencao(tmp_path, "onda2", "o cofre")
    assert ganhou is False
    assert "não é erro" in recado


def test_intencao_ganha_leva_prazo_dentro(tmp_path, monkeypatch):
    corpos = []
    monkeypatch.setattr(
        reservar,
        "criar_ref_atomica",
        lambda raiz, ref, corpo: (corpos.append(corpo), True)[1],
    )
    ganhou, _ = reservar.reservar_intencao(
        tmp_path, "onda2", "o cofre", horas=3, agora=AGORA
    )
    assert ganhou is True
    assert corpos[0]["expira_em"] > corpos[0]["criado_em"]
