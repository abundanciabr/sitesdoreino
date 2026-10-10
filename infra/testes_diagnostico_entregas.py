"""Falhas reais de fronteira reproduzidas sem VPS, banco ou credenciais."""
import importlib.util
import io
import json
from pathlib import Path
import socket
import struct
import subprocess
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import diagnostico_entregas as diag
import ponte_entregas as ponte
import publicar
from mercadopago_congelado import IntegridadeMercadoPagoErro

ID = "a" * 12
SHA = "b" * 40


def test_catalogo_reconstroi_texto_e_nao_vaza_segredos():
    entrada = diag.criar_diagnostico("mercadopago_rotas_divergentes", "mercadopago", "funil")
    entrada.update(motivo="token=MARCADOR senha=MARCADOR CPF=000.000.000-00 email@exemplo.test",
                   acao="cat /privado/MARCADOR", celula="/privado/MARCADOR", em="MARCADOR")
    saida = json.dumps(diag.diagnostico_publico(entrada))
    assert "MARCADOR" not in saida and "CPF" not in saida
    assert "mercadopago_rotas_divergentes" in saida
    assert diag.diagnostico_publico({"codigo": "cat /etc/passwd"}) is None
    antigo = diag.diagnostico_publico({"codigo": "prova_divergente", "em": "MARCADOR"})
    assert "em" not in antigo and "MARCADOR" not in json.dumps(antigo)
    assert "em" not in diag.diagnostico_publico({"codigo": "prova_divergente"})


def test_classificacao_nunca_devolve_texto_da_excecao():
    for erro in (RuntimeError("Rotas protegidas alteradas: /privado/MARCADOR senha=MARCADOR"),
                 RuntimeError("MARCADOR"),
                 IntegridadeMercadoPagoErro("configuracao MARCADOR")):
        assert "MARCADOR" not in json.dumps(diag.classificar_erro(erro))


def test_destino_funil_invalido_classifica_integridade_mp_sem_texto_bruto():
    erro = RuntimeError("IntegridadeMercadoPagoErro: Destino funil inválido em /privado/MARCADOR")
    publico = diag.classificar_erro(erro, "publicador", "funil")
    assert publico["codigo"] == "mercadopago_destino_funil_invalido"
    assert publico["celula"] == "funil"
    assert "MARCADOR" not in json.dumps(publico)


def preparar_publicador(monkeypatch, tmp_path):
    monkeypatch.setattr(publicar, "RAIZ", tmp_path)
    monkeypatch.setattr(publicar, "PUBLICACOES", tmp_path / "publicacoes")
    monkeypatch.setenv("ENTREGA_CANDIDATA", SHA)
    monkeypatch.setattr(publicar, "_diagnostico_entrega", None)


def test_falha_antes_da_intencao_persiste_causa_e_etapa(monkeypatch, tmp_path, capsys):
    preparar_publicador(monkeypatch, tmp_path)
    def antes_da_ativacao(*_):
        publicar.etapa_entrega("mercadopago")
        raise IntegridadeMercadoPagoErro("Rotas protegidas alteradas: /privado/MARCADOR")
    monkeypatch.setattr(publicar, "_publicar_entrega", antes_da_ativacao)
    with pytest.raises(IntegridadeMercadoPagoErro):
        publicar.publicar_entrega(ID, "funil")
    arquivo = tmp_path / "publicacoes/diagnosticos" / (ID + "-funil.json")
    salvo = json.loads(arquivo.read_text())
    assert salvo["estado"] == "falhou"
    assert salvo["diagnostico"]["codigo"] == "mercadopago_rotas_divergentes"
    assert salvo["diagnostico"]["etapa"] == "mercadopago"
    assert salvo["diagnostico"]["em"]
    assert not (tmp_path / "publicacoes/operacoes").exists()
    assert "MARCADOR" not in arquivo.read_text()
    assert "MARCADOR" not in capsys.readouterr().out


def test_retomada_preserva_ultima_falha_e_conclui_mesma_identidade(monkeypatch, tmp_path):
    preparar_publicador(monkeypatch, tmp_path)
    def falhar(*_):
        raise IntegridadeMercadoPagoErro("Rotas protegidas alteradas: caminho")
    monkeypatch.setattr(publicar, "_publicar_entrega", falhar)
    with pytest.raises(IntegridadeMercadoPagoErro):
        publicar.publicar_entrega(ID, "funil")
    monkeypatch.setattr(publicar, "_publicar_entrega", lambda *_: 0)
    assert publicar.publicar_entrega(ID, "funil") == 0
    registros = list((tmp_path / "publicacoes/diagnosticos").glob("*.json"))
    assert len(registros) == 1
    salvo = json.loads(registros[0].read_text())
    assert salvo["estado"] == "concluida" and salvo["diagnostico"] is None
    assert salvo["ultima_falha"]["codigo"] == "mercadopago_rotas_divergentes"


def autoridade(tmp_path, monkeypatch):
    a = ponte.Autoridade(plataforma=tmp_path)
    monkeypatch.setattr(a, "_conferir_espelho", lambda *_: {"estado": "integrada na main",
            "promovida_candidata": SHA, "promocao": {"estado": "remota"}})
    return a


def test_origem_ate_ponte_preserva_diagnostico_pre_ativacao(monkeypatch, tmp_path):
    preparar_publicador(monkeypatch, tmp_path)
    a = autoridade(tmp_path, monkeypatch)
    def falhar(*_):
        publicar.etapa_entrega("mercadopago")
        raise IntegridadeMercadoPagoErro("Rotas protegidas alteradas: MARCADOR")
    monkeypatch.setattr(publicar, "_publicar_entrega", falhar)
    def executar(*_, **__):
        try:
            publicar.publicar_entrega(ID, "funil")
        except IntegridadeMercadoPagoErro:
            return SimpleNamespace(returncode=1, stdout=b"", stderr=b"MARCADOR")
    monkeypatch.setattr(ponte.subprocess, "run", executar)
    with pytest.raises(ponte.ErroPonte) as erro:
        a.publicar(ID, SHA, "funil")
    assert erro.value.diagnostico["codigo"] == "mercadopago_rotas_divergentes"
    assert erro.value.diagnostico["etapa"] == "mercadopago"
    assert "MARCADOR" not in str(erro.value)


def test_ponte_antiga_saida_bruta_e_somente_classificada(monkeypatch, tmp_path):
    a = autoridade(tmp_path, monkeypatch)
    monkeypatch.setattr(ponte.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=1,
        stdout=b"", stderr=b"IntegridadeMercadoPagoErro: Rotas protegidas alteradas: MARCADOR"))
    with pytest.raises(ponte.ErroPonte) as erro:
        a.publicar(ID, SHA, "funil")
    assert erro.value.diagnostico["codigo"] == "mercadopago_rotas_divergentes"
    assert "MARCADOR" not in str(erro.value)


def test_timeout_nao_afirma_que_ativacao_falhou(monkeypatch, tmp_path):
    a = autoridade(tmp_path, monkeypatch)
    def executar(*_, **__):
        raise subprocess.TimeoutExpired("privado MARCADOR", 3600, stderr=b"MARCADOR")
    monkeypatch.setattr(ponte.subprocess, "run", executar)
    with pytest.raises(ponte.ErroPonte) as erro:
        a.publicar(ID, SHA, "funil")
    assert erro.value.diagnostico["codigo"] == "resposta_perdida"
    assert "desconhecido" in str(erro.value)
    assert "MARCADOR" not in str(erro.value)


def test_sucesso_do_processo_sem_journal_atual_nao_confirma_ativacao(monkeypatch, tmp_path):
    a = autoridade(tmp_path, monkeypatch)
    (tmp_path / "publicacoes").mkdir()
    (tmp_path / "publicacoes/funil.json").write_text(json.dumps({"atual": "c" * 40, "aprovada": {"sha": SHA}}))
    monkeypatch.setattr(ponte.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0))
    with pytest.raises(ponte.ErroPonte) as erro:
        a.publicar(ID, SHA, "funil")
    assert erro.value.diagnostico["codigo"] == "ativacao_nao_confirmada"


def test_resposta_perdida_nao_derruba_servidor_da_ponte(monkeypatch):
    class Conexao:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def getsockopt(self, *_): return struct.pack("3i", 0, 1234, 0)
        def makefile(self, *_): return io.BytesIO(json.dumps({"acao": "espelhar", "id": ID, "candidata": SHA, "celula": "funil"}).encode() + b"\n")
        def sendall(self, *_): raise BrokenPipeError()
    atendidas = []
    def aceitar():
        if len(atendidas) == 2: raise StopIteration()
        atendidas.append(1)
        return Conexao(), None
    servidor = SimpleNamespace(getsockname=lambda: "/run/teste.sock", accept=aceitar)
    monkeypatch.setattr(ponte.sys, "platform", "linux")
    monkeypatch.setattr(ponte.socket, "fromfd", lambda *_: servidor, raising=False)
    monkeypatch.setattr(ponte.socket, "SO_PEERCRED", 17, raising=False)
    monkeypatch.setitem(sys.modules, "pwd", SimpleNamespace(getpwnam=lambda _: SimpleNamespace(pw_uid=1234)))
    monkeypatch.setenv("LISTEN_FDS", "1")
    import os
    monkeypatch.setenv("LISTEN_PID", str(os.getpid()))
    with pytest.raises(StopIteration):
        ponte.servir(SimpleNamespace(atender=lambda _: {"ok": True}), esperado="/run/teste.sock")
    assert len(atendidas) == 2


@pytest.mark.skipif(sys.platform != "linux", reason="SO_PEERCRED e socket systemd exigem Linux")
def test_primeira_prova_ausente_passa_pelo_fio_e_ensaia_uma_vez(monkeypatch, tmp_path):
    """Usa a resposta serializada por servir e recebida por ClientePonte."""
    import os
    from unittest.mock import Mock
    from testes_integrador_servico import IntegradorFalso
    from integrador_servico import Estados, Servico

    a = autoridade(tmp_path, monkeypatch)
    a.espelhar = lambda *_: {"ok": True}
    a.conferir_preservacao = lambda *_: {"ok": True, "situacao": "publicavel"}
    preparar_chamadas = []
    def preparar(id_, candidata, celula):
        preparar_chamadas.append((id_, candidata, celula))
        arquivo = tmp_path / "ensaios/saida" / candidata / "resultado.json"
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_text("{}", encoding="utf-8")
        return {"ok": True}
    a.preparar = preparar
    a.publicar = lambda *_: {"ok": True, "estado": "ativa"}
    ensaio = Mock()
    ensaio.RecusaEnsaio = RuntimeError
    ensaio._caminhos.side_effect = lambda raiz, candidata, celula: (
        raiz / "ensaios/saida" / candidata, None, None)
    def registrar_prova(*_):
        arquivo = tmp_path / "entregas/provas" / (SHA + ".json")
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_text("{}", encoding="utf-8")
    ensaio.registrar_prova.side_effect = registrar_prova
    ensaio.verificar_prova.return_value = {"candidata": SHA, "celula": "aplicacao",
        "resultado": "aprovado", "identidade": "d" * 64,
        "pacote_publicador": {"id": "e" * 64}}
    a._ensaio = lambda: ensaio

    class Entrada:
        def __init__(self, pedido): self.pedido, self.resposta = pedido, b""
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def getsockopt(self, *_): return struct.pack("3i", 0, 1234, 0)
        def makefile(self, *_): return io.BytesIO(self.pedido)
        def sendall(self, dado): self.resposta = dado

    def resposta_servidor(pedido):
        entrada = Entrada(json.dumps(pedido).encode() + b"\n")
        chamadas = []
        def aceitar():
            if chamadas: raise StopIteration()
            chamadas.append(1)
            return entrada, None
        servidor = SimpleNamespace(getsockname=lambda: "/run/teste.sock", accept=aceitar)
        with monkeypatch.context() as mp:
            mp.setattr(ponte.sys, "platform", "linux")
            mp.setattr(ponte.socket, "fromfd", lambda *_: servidor)
            mp.setattr(ponte.socket, "SO_PEERCRED", 17, raising=False)
            mp.setitem(sys.modules, "pwd", SimpleNamespace(getpwnam=lambda _: SimpleNamespace(pw_uid=1234)))
            mp.setenv("LISTEN_FDS", "1")
            mp.setenv("LISTEN_PID", str(os.getpid()))
            with pytest.raises(StopIteration):
                ponte.servir(a, esperado="/run/teste.sock")
        return entrada.resposta

    class Saida:
        def __init__(self, resposta): self.resposta = resposta
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def settimeout(self, *_): pass
        def connect(self, *_): pass
        def sendall(self, *_): pass
        def makefile(self, *_): return io.BytesIO(self.resposta)

    class TransporteFio(ponte.ClientePonte):
        def pedir(self, acao, id_, candidata, celula="aplicacao"):
            pedido = {"acao": acao, "id": id_, "candidata": candidata, "celula": celula}
            resposta = resposta_servidor(pedido)
            with monkeypatch.context() as mp:
                mp.setattr(ponte.socket, "socket", lambda *_: Saida(resposta))
                return super().pedir(acao, id_, candidata, celula)

    reg = {"id": ID, "estado": "pronta", "candidata": SHA,
           "base_da_candidata": "c" * 40, "depende_de": []}
    worker = Servico(IntegradorFalso([reg], diff="services/aplicacao/teste.py"),
                     TransporteFio(), Estados(tmp_path / "fases"))
    assert worker.rodada()[0]["fase"] == "ativa"
    assert preparar_chamadas == [(ID, SHA, "aplicacao")]


def test_prova_divergente_nao_autoriza_novo_ensaio(monkeypatch, tmp_path):
    from integrador_servico import Servico
    a = autoridade(tmp_path, monkeypatch)
    a.espelhar = lambda *_: {"ok": True}
    arquivo = tmp_path / "entregas/provas" / (SHA + ".json")
    arquivo.parent.mkdir(parents=True)
    arquivo.write_text("{", encoding="utf-8")
    falso = SimpleNamespace(RecusaEnsaio=RuntimeError,
                            verificar_prova=lambda *_: (_ for _ in ()).throw(RuntimeError("prova corrompida")))
    a._ensaio = lambda: falso
    with pytest.raises(ponte.ErroPonte) as erro:
        a.verificar_prova(ID, SHA, "aplicacao")
    assert erro.value.diagnostico["codigo"] == "prova_divergente"
    assert not Servico._ausencia_esperada(erro.value)


def test_resultado_ausente_e_ilegivel_sao_distintos(monkeypatch, tmp_path):
    from integrador_servico import Servico
    a = autoridade(tmp_path, monkeypatch)
    arquivo = tmp_path / "ensaios/saida" / SHA / "resultado.json"
    with pytest.raises(ponte.ErroPonte) as ausente:
        a.registrar(ID, SHA, "aplicacao")
    assert ausente.value.diagnostico["codigo"] == "resultado_ensaio_ausente"
    assert Servico._ausencia_esperada(ausente.value)
    arquivo.parent.mkdir(parents=True)
    arquivo.write_text("{", encoding="utf-8")
    with pytest.raises(ponte.ErroPonte) as ilegivel:
        a.registrar(ID, SHA, "aplicacao")
    assert not Servico._ausencia_esperada(ilegivel.value)


def test_cadeia_real_pre_ativacao_ate_consulta_retomada_sem_duplicar(monkeypatch, tmp_path):
    from unittest.mock import Mock
    import ensaio_entregas
    from testes_integrador_servico import IntegradorFalso, PonteFalsa
    from integrador_servico import Estados, Servico
    sys.path.insert(0, str(Path(__file__).parent / "acessos"))
    import robo_broker

    preparar_publicador(monkeypatch, tmp_path)
    monkeypatch.setattr(publicar, "LOGS", tmp_path / "publicacoes/logs")
    reg = {"id": ID, "estado": "integrada na main", "candidata": SHA,
           "promovida_candidata": SHA, "base_da_candidata": "c" * 40,
           "promocao": {"estado": "remota", "candidata": SHA, "remoto": "integrador",
                        "prova_funil_identidade": "prova", "main_esperada": "c" * 40}}
    (tmp_path / "entregas").mkdir()
    (tmp_path / "entregas" / (ID + ".json")).write_text(json.dumps(reg))
    pacote = {"id": "d" * 64, "imagem_id": "sha256:" + "e" * 64}
    prova = {"identidade": "prova", "nome_funil": "meshcraft-funil-teste-ensaio",
             "pacote_publicador": pacote, "artefato": {
             "codigo": str(tmp_path / "codigo"), "bundle": str(tmp_path / "bundle"),
             "imagem_tar": str(tmp_path / "imagem.tar"),
             "configuracao_final": str(tmp_path / "config")}}
    celulas = Mock()
    celulas.topologia.return_value = {"celulas": {}}
    monkeypatch.setattr(publicar, "carregar_celulas", lambda: celulas)
    monkeypatch.setattr(publicar, "retomar_pendencia", lambda *_: None)
    monkeypatch.setattr(publicar, "git", lambda *_: SHA)
    monkeypatch.setattr(publicar, "main_remota_publica", lambda: SHA)
    monkeypatch.setattr(publicar, "journal", lambda *_: None)
    monkeypatch.setattr(publicar, "rodar", lambda *_: "")
    monkeypatch.setattr(publicar, "imagem_id", lambda *_: pacote["imagem_id"])
    monkeypatch.setattr(publicar, "politica_mercadopago", lambda: {})
    monkeypatch.setattr(publicar, "conferir_mp_pacote", lambda *_: None)
    monkeypatch.setattr(publicar, "conferir_codigo_docs", lambda *_: None)
    monkeypatch.setattr(publicar, "identificar", lambda *_: pacote)
    monkeypatch.setattr(ensaio_entregas, "verificar_prova", lambda *a, **k: prova)
    bloqueada = [True]
    def conferir(*_):
        if bloqueada[0]:
            raise IntegridadeMercadoPagoErro("Rotas protegidas alteradas: MARCADOR PRIVADO")
    monkeypatch.setattr(publicar, "conferir_ambiente", conferir)
    a = autoridade(tmp_path, monkeypatch)
    chamadas = []
    def executar(cmd, **kwargs):
        if cmd[0] == "bash":
            return SimpleNamespace(returncode=0)
        chamadas.append("publicar")
        try:
            publicar.publicar_entrega(ID, "funil")
            return SimpleNamespace(returncode=0)
        except IntegridadeMercadoPagoErro:
            return SimpleNamespace(returncode=1, stdout=b"", stderr=b"MARCADOR PRIVADO")
    monkeypatch.setattr(ponte.subprocess, "run", executar)
    def ativar(*args, **kwargs):
        (tmp_path / "publicacoes/funil.json").write_text(json.dumps({
            "atual": SHA, "aprovada": {"sha": SHA}}))
    celulas.ativar.side_effect = ativar
    transporte = PonteFalsa()
    transporte.publicar = a.publicar
    estados = Estados(tmp_path / "fases")
    estados.salvar({"id": ID, "candidata": SHA, "fase": "ativação pendente", "tentativas": 0})
    worker = Servico(IntegradorFalso([reg], diff="services/funil/teste.py"), transporte, estados)
    monkeypatch.setattr(robo_broker, "FASES", estados.pasta)
    assert worker.rodada()[0]["fase"] == "ativação pendente"
    assert not (tmp_path / "publicacoes/operacoes").exists()
    consulta = json.loads(robo_broker.acrescentar_operacao(json.dumps(reg)))
    assert consulta["operacao"]["diagnostico"]["codigo"] == "mercadopago_rotas_divergentes"
    assert consulta["operacao"]["diagnostico"]["etapa"] == "mercadopago"
    assert "MARCADOR" not in json.dumps(consulta)
    bloqueada[0] = False
    assert worker.rodada()[0]["fase"] == "ativa"
    assert worker.rodada()[0]["fase"] == "ativa"
    assert chamadas == ["publicar", "publicar"]
    assert celulas.ativar.call_count == 1
    salvo = estados.ler(ID)
    assert salvo["ultima_falha"]["codigo"] == "mercadopago_rotas_divergentes"
    assert salvo["diagnostico"] is None
    assert salvo["progresso_em"]


@pytest.mark.parametrize("resposta", [b"", b"x" * 4097, b"[1]\n", b"{quebrado\n"])
def test_cliente_resposta_vazia_longa_ou_malformada_preserva_desconhecido(monkeypatch, resposta):
    class Conexao:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def settimeout(self, *_): pass
        def connect(self, *_): pass
        def sendall(self, *_): pass
        def makefile(self, *_): return io.BytesIO(resposta)
    monkeypatch.setattr(ponte.socket, "socket", lambda *_: Conexao())
    with pytest.raises(ponte.ErroPonte) as erro:
        ponte.ClientePonte().publicar(ID, SHA, "funil")
    assert erro.value.diagnostico["codigo"] == "resposta_perdida"


def test_catalogo_recusa_tipos_inesperados_sem_quebrar_consulta():
    assert diag.diagnostico_publico({"codigo": []}) is None
    assert diag.diagnostico_publico({"codigo": "falha_operacional", "etapa": []})["etapa"] == "publicador"
