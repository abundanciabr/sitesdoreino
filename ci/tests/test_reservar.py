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


def test_soltar_nao_apaga_reserva_que_mudou_de_dono_antes_da_leitura(tmp_path, monkeypatch):
    sha = "a" * 40
    ref = "refs/reservas/tarefa-TAR-001"

    class Exec:
        def __init__(self, stdout):
            self.stdout = stdout

    def ler(comando, **kwargs):
        if comando[1] == "ls-remote":
            return Exec(f"{sha}\t{ref}\n")
        if comando[1] == "show":
            return Exec(json.dumps({"tipo": "intencao", "chave": "tarefa-TAR-001", "dono": "outra"}))
        return Exec("")

    monkeypatch.setattr(reservar, "executar", ler)
    monkeypatch.setattr(
        reservar,
        "_git",
        lambda *a, **k: pytest.fail("a reserva de outra bancada nunca é apagada"),
    )
    assert reservar.soltar(tmp_path, "tarefa-TAR-001", dono="minha-bancada") is False


def test_soltar_usa_lease_e_preserva_se_o_dono_mudar_depois_da_leitura(tmp_path, monkeypatch):
    sha = "b" * 40
    ref = "refs/reservas/tarefa-TAR-001"

    class Exec:
        def __init__(self, stdout):
            self.stdout = stdout

    def ler(comando, **kwargs):
        if comando[1] == "ls-remote":
            return Exec(f"{sha}\t{ref}\n")
        if comando[1] == "show":
            return Exec(json.dumps({"tipo": "intencao", "chave": "tarefa-TAR-001", "dono": "minha-bancada"}))
        return Exec("")

    vistos = []
    monkeypatch.setattr(reservar, "executar", ler)
    monkeypatch.setattr(
        reservar,
        "_git",
        lambda raiz, comando: (vistos.append(comando), Saida(1, stderr="[rejected] (stale info)"))[1],
    )
    assert reservar.soltar(tmp_path, "tarefa-TAR-001", dono="minha-bancada") is False
    assert any(f"--force-with-lease={ref}:{sha}" in parte for parte in vistos[0])

def test_reserva_com_chave_recupera_numero_sem_alocar(tmp_path, monkeypatch):
    monkeypatch.setattr(reservar, 'numero_da_chave', lambda *a: {'numero': '008', 'dia': '20260828'})
    monkeypatch.setattr(reservar, 'numeros_em_uso', lambda *a: pytest.fail('não deve alocar de novo'))
    assert reservar.alocar_numero(tmp_path, 'registro', AGORA, chave='a'*64) == '008'


def test_reserva_com_chave_e_numero_sao_atomicos(tmp_path, monkeypatch):
    monkeypatch.setattr(reservar, 'numero_da_chave', lambda *a: None)
    monkeypatch.setattr(reservar, 'numeros_em_uso', lambda *a: set())
    vistos = []
    monkeypatch.setattr(reservar, 'criar_ref_atomica', lambda *a, **kw: vistos.append((a,kw)) or True)
    assert reservar.alocar_numero(tmp_path, 'registro', AGORA, chave='a'*64, com_dia=True) == '20260828-001'
    assert vistos[0][1]['ref_chave'] == 'refs/chaves-numero/registro/' + 'a'*64
    assert vistos[0][0][2]['chave'] == 'a'*64

def test_push_atomico_perdido_recupera_numero_real_sem_rede(tmp_path, monkeypatch):
    remoto = tmp_path / 'servidor.git'
    raiz = tmp_path / 'bancada'
    subprocess.run(['git', 'init', '--bare', str(remoto)], check=True, capture_output=True)
    subprocess.run(['git', 'init', str(raiz)], check=True, capture_output=True)
    def git(*args):
        return subprocess.run(['git', *args], cwd=raiz, check=True, capture_output=True, text=True).stdout
    git('config', 'user.name', 'Teste')
    git('config', 'user.email', 'teste@example.com')
    (raiz/'painel/registros').mkdir(parents=True)
    (raiz/'inicial').write_text('base',encoding='utf-8')
    git('add','inicial')
    git('commit','-m','base')
    git('remote','add','origin',str(remoto))
    original = reservar._git
    def perdeu_resposta(raiz, args):
        resultado = original(raiz, args)
        assert resultado.returncode == 0
        assert '--atomic' in args
        return Saida(1, stderr='conexão interrompida após envio')
    monkeypatch.setattr(reservar, '_git', perdeu_resposta)
    with pytest.raises(ErroDeInstrumentacao):
        reservar.alocar_numero(raiz, 'registro', AGORA, chave='d'*64)
    monkeypatch.setattr(reservar, '_git', original)
    amanha = AGORA.replace(day=29)
    assert reservar.alocar_numero(raiz, 'registro', amanha, chave='d'*64, com_dia=True) == '20260828-001'
    assert reservar.alocar_numero(raiz, 'registro', amanha, chave='d'*64) == '001'
    refs = git('ls-remote','origin').splitlines()
    assert len(refs) == 2
    assert sum('refs/numeros/registro/' in linha for linha in refs) == 1


def _duas_bancadas_git(tmp_path):
    remoto = tmp_path / "servidor.git"
    origem = tmp_path / "origem"
    subprocess.run(["git", "init", "--bare", str(remoto)], check=True, capture_output=True)
    subprocess.run(["git", "init", "-b", "main", str(origem)], check=True, capture_output=True)

    def git(raiz, *args):
        return subprocess.run(
            ["git", *args], cwd=raiz, check=True, capture_output=True, text=True
        ).stdout.strip()

    git(origem, "config", "user.name", "Teste")
    git(origem, "config", "user.email", "teste@example.com")
    (origem / "base").write_text("base", encoding="utf-8")
    git(origem, "add", "base")
    git(origem, "commit", "-m", "base")
    git(origem, "remote", "add", "origin", str(remoto))
    git(origem, "push", "-u", "origin", "main")
    bancadas = []
    for nome in ("claim", "pausa"):
        bancada = tmp_path / nome
        git(tmp_path, "clone", "-b", "main", str(remoto), str(bancada))
        git(bancada, "config", "user.name", "Teste")
        git(bancada, "config", "user.email", "teste@example.com")
        bancadas.append(bancada)
    return remoto, bancadas, git


@pytest.mark.parametrize("primeiro", ["claim", "pausa"])
def test_claim_e_pausa_disputam_mesma_ref_cas_em_bare_git(tmp_path, primeiro):
    remoto, (claim, pausa), git = _duas_bancadas_git(tmp_path)
    barreira = "refs/coordenacao/barreira/piloto"
    reserva = "refs/reservas/tarefa-TAR-001"
    assert reservar.criar_ref_atomica(claim, barreira, {"barreira": "git"})
    esperado = git(claim, "ls-remote", "origin", barreira).split()[0]

    def reivindicar():
        return reservar.criar_ref_atomica(
            claim, barreira, {"barreira": "git", "chave": "tarefa-TAR-001"},
            ref_chave=reserva, lease=esperado,
        )

    def pausar():
        return reservar.criar_ref_atomica(
            pausa, barreira, {"barreira": "pausada"}, lease=esperado,
        )

    operacoes = {"claim": reivindicar, "pausa": pausar}
    assert operacoes[primeiro]() is True
    assert operacoes["pausa" if primeiro == "claim" else "claim"]() is False
    refs = dict(
        linha.split("\t")[::-1]
        for linha in git(claim, "ls-remote", "origin", barreira, reserva).splitlines()
    )
    assert (reserva in refs) is (primeiro == "claim")
    if primeiro == "claim":
        assert refs[barreira] == refs[reserva]
    assert remoto.is_dir()


def test_cliente_antigo_ignora_barreira_e_ainda_grava_reserva(tmp_path):
    _, (claim, pausa), git = _duas_bancadas_git(tmp_path)
    barreira = "refs/coordenacao/barreira/piloto"
    assert reservar.criar_ref_atomica(pausa, barreira, {"barreira": "pausada"})
    ganhou, _ = reservar.reservar_intencao(
        claim, "tarefa-TAR-001", "cliente antigo", agora=AGORA
    )
    assert ganhou is True
    assert git(claim, "ls-remote", "origin", barreira).split()[0] != git(
        claim, "ls-remote", "origin", "refs/reservas/tarefa-TAR-001"
    ).split()[0]


def test_leitor_da_barreira_confronta_digest_e_referencia_remota(tmp_path):
    _, (claim, _), _ = _duas_bancadas_git(tmp_path)
    ids = ["TAR-001", "TAR-002"]
    digest = reservar.digest_da_coorte_piloto(ids)
    corpo = {"barreira": {"coorte": "piloto", "estado": "git",
                          "ids_sha256": digest, "sequencia": 0}}
    assert reservar.criar_ref_atomica(claim, reservar.REF_BARREIRA_PILOTO, corpo)
    sha, leitura = reservar.ler_barreira_piloto(claim)
    assert len(sha) == 40
    assert leitura == corpo["barreira"]
    assert reservar.digest_da_coorte_piloto(ids[::-1]) == digest
    assert reservar.digest_da_coorte_piloto(["TAR-001", "TAR-003"]) != digest


@pytest.mark.parametrize("ids", [[], ["TAR-001", "TAR-001"], ["TAR-1"], [{}]])
def test_manifesto_piloto_invalido_para_antes_da_rede(ids):
    with pytest.raises(ErroDeInstrumentacao, match="manifesto"):
        reservar.digest_da_coorte_piloto(ids)


def test_segundo_lease_troca_apenas_reserva_expirada_lida(tmp_path):
    _, (claim, pausa), git = _duas_bancadas_git(tmp_path)
    barreira = reservar.REF_BARREIRA_PILOTO
    reserva = "refs/reservas/tarefa-TAR-001"
    assert reservar.criar_ref_atomica(claim, barreira, {"barreira": "git"})
    assert reservar.criar_ref_atomica(pausa, reserva, {"expira_em": "2020-01-01T00:00:00+00:00"})
    sha_barreira = git(claim, "ls-remote", "origin", barreira).split()[0]
    sha_antiga = git(claim, "ls-remote", "origin", reserva).split()[0]
    assert reservar.criar_ref_atomica(
        claim, barreira, {"barreira": "git", "chave": "tarefa-TAR-001"},
        ref_chave=reserva, lease=sha_barreira, lease_chave=sha_antiga,
    )
    assert git(claim, "ls-remote", "origin", barreira).split()[0] == git(
        claim, "ls-remote", "origin", reserva
    ).split()[0]
    assert reservar.criar_ref_atomica(
        pausa, barreira, {"barreira": "git"}, ref_chave=reserva,
        lease=sha_barreira, lease_chave=sha_antiga,
    ) is False


def _iniciar_barreira_piloto(raiz, ids):
    assert reservar.criar_ref_atomica(
        raiz, reservar.REF_BARREIRA_PILOTO,
        {"barreira": {"coorte": "piloto", "estado": "git",
                      "ids_sha256": reservar.digest_da_coorte_piloto(ids), "sequencia": 0}},
    )


def test_claim_piloto_e_pausa_real_preservam_reserva_ativa(tmp_path):
    _, (claim, pausa), git = _duas_bancadas_git(tmp_path)
    ids = ["TAR-001", "TAR-002"]
    _iniciar_barreira_piloto(claim, ids)
    ganhou, _ = reservar.reservar_intencao_piloto(
        claim, "tarefa-TAR-001", "ensaio", ids, agora=AGORA
    )
    assert ganhou is True
    sha, barreira = reservar.ler_barreira_piloto(pausa)
    assert barreira["sequencia"] == 1
    assert sha == git(claim, "ls-remote", "origin", "refs/reservas/tarefa-TAR-001").split()[0]
    assert reservar.pausar_barreira_piloto(pausa, ids, agora=AGORA) is False
    assert reservar.pausar_barreira_piloto(
        pausa, ids, agora=AGORA.replace(hour=19)
    ) is False
    assert reservar.pausar_barreira_piloto(
        pausa, ids, agora=AGORA.replace(month=9)
    ) is True
    assert reservar.ler_barreira_piloto(claim)[1]["estado"] == "pausada"
    assert reservar.reservar_intencao_piloto(
        claim, "tarefa-TAR-002", "ensaio", ids, agora=AGORA.replace(month=9)
    )[0] is False


@pytest.mark.parametrize("primeiro", ["pouso", "pausa"])
def test_pouso_e_pausa_disputam_a_mesma_barreira_bare(tmp_path, primeiro):
    _, (pouso, pausa), _ = _duas_bancadas_git(tmp_path)
    ids = ["TAR-001"]
    head = "a" * 40
    _iniciar_barreira_piloto(pouso, ids)
    if primeiro == "pausa":
        assert reservar.pausar_barreira_piloto(pausa, ids, agora=AGORA)
        assert reservar.adquirir_efeito_piloto(pouso, ids, 99, head) is None
        return
    operacao = reservar.adquirir_efeito_piloto(pouso, ids, 99, head)
    assert operacao and len(operacao) == 32
    assert reservar.pausar_barreira_piloto(pausa, ids, agora=AGORA) is False
    assert reservar.pausar_barreira_piloto(
        pausa, ids, agora=AGORA.replace(year=AGORA.year + 1)
    ) is False
    assert reservar.adquirir_efeito_piloto(pausa, ids, 100, "b" * 40) is None
    assert reservar.concluir_efeito_piloto(pouso, ids, 99, head, "0" * 32) is False
    assert reservar.concluir_efeito_piloto(pouso, ids, 99, head, operacao)
    assert reservar.pausar_barreira_piloto(pausa, ids, agora=AGORA)


def test_pouso_recupera_resposta_perdida_sem_soltar_efeito_incerto(tmp_path, monkeypatch):
    _, (pouso, pausa), _ = _duas_bancadas_git(tmp_path)
    ids = ["TAR-001"]
    head = "a" * 40
    _iniciar_barreira_piloto(pouso, ids)
    original = reservar._git

    def perder_resposta(raiz, args):
        resposta = original(raiz, args)
        assert resposta.returncode == 0
        return Saida(128, stderr="resposta perdida após push")

    monkeypatch.setattr(reservar, "_git", perder_resposta)
    operacao = reservar.adquirir_efeito_piloto(pouso, ids, 99, head)
    assert operacao
    assert reservar.pausar_barreira_piloto(pausa, ids, agora=AGORA) is False
    assert reservar.concluir_efeito_piloto(pouso, ids, 99, head, operacao)
    assert reservar.pausar_barreira_piloto(pausa, ids, agora=AGORA)


def test_claim_piloto_recupera_resposta_perdida_e_reserva_expirada(tmp_path, monkeypatch):
    _, (claim, _), git = _duas_bancadas_git(tmp_path)
    ids = ["TAR-001"]
    _iniciar_barreira_piloto(claim, ids)
    assert reservar.criar_ref_atomica(
        claim, "refs/reservas/tarefa-TAR-001",
        {"tipo": "intencao", "expira_em": "2020-01-01T00:00:00+00:00"},
    )
    original = reservar._git

    def perder_resposta(raiz, args):
        resultado = original(raiz, args)
        assert resultado.returncode == 0
        return Saida(128, stderr="resposta perdida após push atômico")

    monkeypatch.setattr(reservar, "_git", perder_resposta)
    assert reservar.reservar_intencao_piloto(
        claim, "tarefa-TAR-001", "ensaio", ids, agora=AGORA
    )[0] is True
    assert git(claim, "ls-remote", "origin", reservar.REF_BARREIRA_PILOTO).split()[0] == git(
        claim, "ls-remote", "origin", "refs/reservas/tarefa-TAR-001"
    ).split()[0]


def test_claim_piloto_recusa_manifesto_divergente_sem_escrever(tmp_path):
    _, (claim, _), git = _duas_bancadas_git(tmp_path)
    _iniciar_barreira_piloto(claim, ["TAR-001"])
    antes = git(claim, "ls-remote", "origin", reservar.REF_BARREIRA_PILOTO)
    with pytest.raises(ErroDeInstrumentacao, match="manifesto piloto diverge"):
        reservar.reservar_intencao_piloto(
            claim, "tarefa-TAR-001", "ensaio", ["TAR-001", "TAR-002"], agora=AGORA
        )
    assert git(claim, "ls-remote", "origin", reservar.REF_BARREIRA_PILOTO) == antes
    assert not git(claim, "ls-remote", "origin", "refs/reservas/tarefa-TAR-001")


def test_pausa_piloto_recupera_resposta_perdida_sem_reabrir_git(tmp_path, monkeypatch):
    _, (claim, _), _ = _duas_bancadas_git(tmp_path)
    ids = ["TAR-001"]
    _iniciar_barreira_piloto(claim, ids)
    original = reservar._git

    def perder_resposta(raiz, args):
        resultado = original(raiz, args)
        assert resultado.returncode == 0
        return Saida(128, stderr="resposta perdida após pausa")

    monkeypatch.setattr(reservar, "_git", perder_resposta)
    assert reservar.pausar_barreira_piloto(claim, ids, agora=AGORA) is True
    assert reservar.ler_barreira_piloto(claim)[1]["estado"] == "pausada"
