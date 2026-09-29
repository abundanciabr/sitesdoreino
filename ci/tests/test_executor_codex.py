"""Protocolo Codex e contenção com processos reais, sem chamar uma IA."""
import json
import os
import subprocess
import sys
import time
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest
import executor_codex as executor
import sessao
from test_fila import tarefa as tarefa_da_prova, evento as evento_da_prova

PEGAR_REAL = executor.fila.cmd_pegar
ESTADO_AO_VIVO_REAL = executor.fila.estado_ao_vivo
CONTEXTO_REAL = executor.contexto


def git(onde, *args):
    return subprocess.run(["git", "-C", str(onde), *args], check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def bancada(tmp_path, monkeypatch):
    principal = tmp_path / "principal"
    principal.mkdir()
    git(principal, "init", "-b", "main")
    git(principal, "config", "user.name", "Teste")
    git(principal, "config", "user.email", "teste@example.invalid")
    (principal / "README.md").write_text("inicial", encoding="utf-8")
    pasta_fila = principal / "fila/tarefas"
    pasta_fila.mkdir(parents=True)
    tarefa = tarefa_da_prova("1001",toca=["ci"])
    (pasta_fila / (tarefa["arquivo"]+".json")).write_text(json.dumps(tarefa),encoding="utf-8")
    git(principal, "add", "README.md", "fila")
    git(principal, "commit", "-m", "inicial")
    alvo = tmp_path / "bancada"
    git(principal, "worktree", "add", "-b", "agent/ci/piloto", str(alvo))
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex"))
    plano = replace(sessao.derivar_plano("ci", "piloto", raiz=principal, celulas=["ci"], usa_redis=False,
                    sobe_ambiente=False, tarefa_da_fila="TAR-1001"), worktree=alvo, branch="agent/ci/piloto")
    sessao.registrar_estado_inicial(plano, "git")
    corpo = {"tipo": "intencao", "chave": "tarefa-TAR-1001", "dono": executor.reservar.identidade_da_bancada(alvo),
             "expira_em": "2099-01-01T00:00:00+00:00"}
    reserva = ["a" * 40, corpo]
    monkeypatch.setattr(executor.reservar, "ler_reserva", lambda *args: tuple(reserva))
    chamadas = []
    monkeypatch.setattr(executor.fila, "bancada_contem_main_publicada", lambda *args:True)
    monkeypatch.setattr(executor.fila, "estado_ao_vivo",lambda onde,tarefas,eventos:(executor.fila.calcular_estados(tarefas,eventos),set(),{}))
    monkeypatch.setattr(executor.fila, "cmd_pegar", lambda onde, args: chamadas.append(("pegar", onde, args)) or 0)
    monkeypatch.setattr(executor.fila, "cmd_checkpoint", lambda onde, args: chamadas.append(("checkpoint", onde, args)) or 0)
    monkeypatch.setattr(executor, "contexto", lambda *args: "brief mínimo")
    monkeypatch.setattr(executor.shutil, "which", lambda nome: sys.executable)
    return alvo, reserva, chamadas


def protocolo(bancada, monkeypatch, *, esperar=0, terminal=True, thread=None, gravar_temp=False):
    alvo, _, _ = bancada
    thread = thread or str(uuid.uuid4())
    root = Path(os.environ["CODEX_HOME"])
    pasta = root / "sessions/2026/09/29"
    pasta.mkdir(parents=True, exist_ok=True)
    rollout = pasta / f"rollout-2026-09-29T00-00-00-{thread}.jsonl"
    script = (
        "import json,time,sys\nfrom pathlib import Path\nfrom datetime import datetime,timezone\n"
        f"thread={thread!r}\n"
        "print(json.dumps({'type':'thread.started','thread_id':thread}),flush=True)\n"
        "print(json.dumps({'type':'turn.started'}),flush=True)\n"
        f"Path({str(rollout)!r}).write_text(json.dumps({{'type':'session_meta','payload':{{'id':thread,'model_provider':'openai'}}}})+'\\n'+json.dumps({{'timestamp':datetime.now(timezone.utc).isoformat(),"
        f"'type':'turn_context','payload':{{'model':'gpt-6-sol','effort':'high','cwd':{str(alvo)!r}}}}})+'\\n')\n"
        f"time.sleep({esperar})\n"
    )
    if gravar_temp:
        script += ("import os\n"
                   "artefatos=Path(os.environ['TEMP'])/'pme04-piloto'; artefatos.mkdir()\n"
                   "(artefatos/'resultado.json').write_text('{\"soma\":18}',encoding='utf-8')\n")
    if terminal:
        script += "print(json.dumps({'type':'turn.completed','usage':{'input_tokens':1,'output_tokens':1}}),flush=True)\n"
    monkeypatch.setattr(executor, "comando_codex", lambda *args: [sys.executable, "-u", "-c", script])
    return thread, rollout


def iniciar(bancada):
    return executor.executar("iniciar", bancada[0], modelo="gpt-6-sol", esforco="high", pedido="Faça o pedido autorizado")


def test_cli_fixa_modelo_esforco_sandbox_e_retomada_exata(tmp_path):
    estado = {"modelo": "gpt-6-sol", "esforco": "high"}
    comando = executor.comando_codex("codex", tmp_path, estado, "pedido")
    assert comando == ["codex", "exec", "-m", "gpt-6-sol", "-c", 'model_reasoning_effort="high"',
                       "-c", 'model_provider="openai"', "--sandbox", "workspace-write", "-C", str(tmp_path), "--json", "pedido"]
    estado["thread_id"] = str(uuid.uuid4())
    assert executor.comando_codex("codex", tmp_path, estado, "retome")[-3:] == ["resume", estado["thread_id"], "retome"]
    assert not any("ignore" in arg or "bypass" in arg for arg in comando)


def test_resultado_exige_protocolo_e_runtime_e_preserva_tentativa_na_retomada(bancada, monkeypatch):
    thread, _ = protocolo(bancada, monkeypatch)
    estado = iniciar(bancada)
    assert estado["estado"] == "resultado_recebido"
    assert estado["supervisao"] == "supervisionada"
    assert estado["thread_id"] == thread
    assert estado["selecao_local"]["turnos"] == [{"modelo": "gpt-6-sol", "esforco": "high"}]
    assert estado["processos_encerrados"]
    assert not Path(estado["transitorio"]).exists()
    retomada = executor.executar("retomar", bancada[0], pedido="Continue o mesmo pedido")
    assert retomada["tentativa"] == estado["tentativa"]
    assert retomada["thread_id"] == thread
    assert retomada["reserva"] == estado["reserva"]
    assert retomada["estado"] == "resultado_recebido"
    assert [c[0] for c in bancada[2]] == ["pegar", "checkpoint", "checkpoint"]


@pytest.mark.parametrize("modelo,esforco,pedido", [("gpt-6-astra", "high", "x"), ("gpt-6-sol", "ultra", "x"),
                                                   ("gpt-6-sol", "high", "")])
def test_entrada_invalida_nao_adquire_nem_inicia(bancada, modelo, esforco, pedido):
    with pytest.raises(executor.ErroDeInstrumentacao):
        executor.executar("iniciar", bancada[0], modelo=modelo, esforco=esforco, pedido=pedido)
    assert bancada[2] == []


def test_bancada_principal_e_ramo_divergente_recusados(bancada):
    alvo = bancada[0]
    with pytest.raises(executor.ErroDeInstrumentacao):
        executor.carregar_bancada(alvo.parent / "principal")
    git(alvo, "checkout", "-b", "agent/ci/outra")
    with pytest.raises(executor.ErroDeInstrumentacao, match="Ramo"):
        executor.carregar_bancada(alvo)


@pytest.mark.parametrize("defeito", ["vencida", "dono", "chave", "versao", "instrumento"])
def test_perda_posse_recusa_novo_efeito(bancada, defeito, monkeypatch):
    alvo, reserva, _ = bancada
    if defeito == "vencida": reserva[1]["expira_em"] = "2000-01-01T00:00:00+00:00"
    if defeito == "dono": reserva[1]["dono"] = "outra-bancada"
    if defeito == "chave": reserva[1]["chave"] = "tarefa-TAR-1002"
    if defeito == "versao": reserva[0] = "b" * 40
    if defeito == "instrumento":
        monkeypatch.setattr(executor.reservar, "ler_reserva", lambda *args: None)
    with pytest.raises(executor.ErroDeInstrumentacao):
        executor.conferir_posse(alvo, "TAR-1001", "a" * 40)


def test_saida_zero_sem_turno_concluido_nao_e_resultado(bancada, monkeypatch):
    protocolo(bancada, monkeypatch, terminal=False)
    estado = iniciar(bancada)
    assert estado["estado"] == "incerto"
    assert estado["exit_code"] == 0
    assert estado["processos_encerrados"]


def test_runtime_divergente_recusa_resultado(bancada, monkeypatch):
    _, rollout = protocolo(bancada, monkeypatch)
    original = executor.selecao_registrada
    def divergir(estado, alvo):
        texto = rollout.read_text().replace("gpt-6-sol", "gpt-6-astra")
        rollout.write_text(texto)
        return original(estado, alvo)
    monkeypatch.setattr(executor, "selecao_registrada", divergir)
    estado = iniciar(bancada)
    assert estado["estado"] == "incerto"
    assert "diverge" in estado["erro"]


def test_timeout_preserva_thread_e_reconciliacao_nao_chama_ia(bancada, monkeypatch):
    thread, _ = protocolo(bancada, monkeypatch, esperar=60)
    original = executor.executar_processo
    monkeypatch.setattr(executor, "executar_processo", lambda *args: original(*args, prazo=1, intervalo=.05))
    estado = iniciar(bancada)
    assert estado["estado"] == "incerto"
    assert estado["thread_id"] == thread
    assert estado["processos_encerrados"]
    def nunca(*args):
        raise AssertionError("reconciliar iniciou IA")
    monkeypatch.setattr(executor, "executar_processo", nunca)
    reconciliado = executor.executar("reconciliar", bancada[0])
    assert reconciliado["tentativa"] == estado["tentativa"]
    assert reconciliado["estado"] == "incerto"


def test_posse_perdida_durante_execucao_encerra_e_nao_checkpoint(bancada, monkeypatch):
    protocolo(bancada, monkeypatch, esperar=60)
    original = executor.executar_processo
    quantidade = 0
    conferir = executor.conferir_posse
    def perder(*args):
        nonlocal quantidade
        quantidade += 1
        if quantidade >= 3:
            bancada[1][0] = "b" * 40
        return conferir(*args)
    monkeypatch.setattr(executor, "conferir_posse", perder)
    monkeypatch.setattr(executor, "executar_processo", lambda *args: original(*args, prazo=3, intervalo=.05))
    estado = iniciar(bancada)
    assert estado["estado"] == "incerto"
    assert estado["processos_encerrados"]
    assert not any(c[0] == "checkpoint" for c in bancada[2])
    with pytest.raises(executor.ErroDeInstrumentacao):
        executor.executar("retomar", bancada[0], pedido="continue")


def test_estado_ou_evento_corrompido_recusa_sem_falso_sucesso(tmp_path):
    arquivo = tmp_path / "estado.json"
    arquivo.write_text("[]")
    with pytest.raises(executor.ErroDeInstrumentacao): executor.ler(arquivo)
    with pytest.raises(executor.ErroDeInstrumentacao): executor.aplicar_eventos({}, "texto\n", completo=True)
    with pytest.raises(executor.ErroDeInstrumentacao):
        executor.aplicar_eventos({"thread_id": str(uuid.uuid4())}, json.dumps({"type":"thread.started","thread_id":str(uuid.uuid4())})+"\n")


def test_trava_recusa_segunda_execucao_imediatamente(tmp_path):
    script = (
        "import sys,time\nfrom pathlib import Path\nimport sessao\n"
        "with sessao.trava_da_bancada(Path(sys.argv[1]),esperar=False):\n"
        " Path(sys.argv[2]).touch()\n time.sleep(60)\n"
    )
    marcador = tmp_path / "pronto"
    env = {**os.environ, "PYTHONPATH": str(Path(sessao.__file__).parent)}
    filho = subprocess.Popen([sys.executable, "-c", script, str(tmp_path), str(marcador)], env=env)
    try:
        limite = time.monotonic() + 5
        while not marcador.exists():
            assert time.monotonic() < limite
            time.sleep(.01)
        inicio = time.monotonic()
        with pytest.raises(sessao.ErroDeSessao):
            with sessao.trava_da_bancada(tmp_path, esperar=False):
                pytest.fail("segunda execução entrou")
        assert time.monotonic() - inicio < 1
    finally:
        filho.kill()
        filho.wait(timeout=5)


def test_limpeza_nao_confirmada_impede_retomada(bancada, monkeypatch):
    protocolo(bancada, monkeypatch)
    estado = iniciar(bancada)
    pasta = sessao.caminho_da_trava_da_bancada(bancada[0]).parent.parent / "codex" / sessao.identidade_duravel_da_bancada(bancada[0])[:32]
    estado["processos_encerrados"] = False
    estado["grupo_windows"] = None
    Path(estado["selo_limpeza"]).unlink(missing_ok=True)
    executor.gravar(pasta / "TAR-1001.json", estado)
    with pytest.raises(executor.ErroDeInstrumentacao, match="processos antigos"):
        executor.executar("retomar", bancada[0], pedido="continue")


@pytest.mark.parametrize("sistema", ["win32", "linux"])
def test_morte_abrupta_encerra_processos_proprios(tmp_path, sistema):
    if sys.platform != sistema:
        pytest.skip("Prova específica do sistema operacional")
    script = tmp_path / "supervisor.py"
    filho = "import os,time;from pathlib import Path;Path('filho.pid').write_text(str(os.getpid()));time.sleep(60)"
    pai = f"import subprocess,sys,time;subprocess.Popen([sys.executable,'-c',{filho!r}],start_new_session=True);time.sleep(60)"
    script.write_text(
        "import os,sys,time\nfrom pathlib import Path\nfrom executor_codex import criar_grupo\n"
        "grupo=criar_grupo()\n"
        f"comando=[sys.executable,'-c',{pai!r}]\n"
        "kwargs={} if os.name=='nt' else {'encerramento':'limpo.json'}\n"
        "processo=grupo.iniciar(comando,Path.cwd(),os.environ,**kwargs)\n"
        "Path('grupo.json').write_text(str(getattr(grupo,'identidade','linux')))\n"
        "time.sleep(60)\n", encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": str(Path(executor.__file__).parent)}
    proc = subprocess.Popen([sys.executable, str(script)], cwd=tmp_path, env=env)
    try:
        limite = time.monotonic() + 10
        while not (tmp_path / "filho.pid").exists():
            assert time.monotonic() < limite
            time.sleep(.01)
        proc.kill()
        proc.wait(timeout=5)
        limite = time.monotonic() + 8
        if sistema == "linux":
            while not (tmp_path / "limpo.json").exists():
                assert time.monotonic() < limite
                time.sleep(.01)
            pid = int((tmp_path / "filho.pid").read_text())
            assert not Path(f"/proc/{pid}").exists()
        else:
            from pr_processos_windows import confirmar_encerramento
            while not confirmar_encerramento((tmp_path / "grupo.json").read_text()):
                assert time.monotonic() < limite
                time.sleep(.01)
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=5)


def test_duas_tentativas_mantem_bancadas_estado_e_transitorio_separados(bancada, monkeypatch):
    alvo, reserva, chamadas = bancada
    protocolo(bancada, monkeypatch)
    primeira = iniciar(bancada)
    principal = alvo.parent / "principal"
    segunda_bancada = alvo.parent / "segunda"
    git(principal, "worktree", "add", "-b", "agent/ci/segunda", str(segunda_bancada))
    plano = replace(sessao.derivar_plano("ci", "segunda", raiz=principal, celulas=["ci"], usa_redis=False,
                    sobe_ambiente=False, tarefa_da_fila="TAR-1001"), worktree=segunda_bancada, branch="agent/ci/segunda")
    sessao.registrar_estado_inicial(plano, "git")
    reserva[0] = "b" * 40
    reserva[1]["dono"] = executor.reservar.identidade_da_bancada(segunda_bancada)
    protocolo((segunda_bancada, reserva, chamadas), monkeypatch)
    segunda = iniciar((segunda_bancada, reserva, chamadas))
    assert primeira["tentativa"] != segunda["tentativa"]
    assert primeira["thread_id"] != segunda["thread_id"]
    assert primeira["log"] != segunda["log"]
    assert Path(primeira["log"]).exists() and Path(segunda["log"]).exists()
    assert not Path(primeira["transitorio"]).exists() and not Path(segunda["transitorio"]).exists()
    assert primeira["bancada"] != segunda["bancada"]
    with pytest.raises(executor.ErroDeInstrumentacao):
        executor.executar("retomar", alvo, pedido="continue")


def test_retomada_recusa_troca_de_modelo(bancada, monkeypatch):
    protocolo(bancada, monkeypatch)
    iniciar(bancada)
    with pytest.raises(executor.ErroDeInstrumentacao, match="trocar modelo"):
        executor.executar("retomar", bancada[0], modelo="gpt-6-luna", pedido="continue")


def test_env_da_sessao_recusa_duplicacao_e_formato(tmp_path):
    env = tmp_path / "sessao.env"
    env.write_text("SESSAO_VENV='/venv'\nSESSAO_VENV='/outra'\n")
    with pytest.raises(sessao.ErroDeSessao, match="duplicada"):
        sessao.carregar_env_de_sessao(env)
    env.write_text("SESSAO_VENV=sem-aspas")
    with pytest.raises(sessao.ErroDeSessao, match="formato inválido"):
        sessao.carregar_env_de_sessao(env)


def test_ambiente_sem_servico_nao_herda_python_injetado(bancada, monkeypatch):
    monkeypatch.setenv("PYTHONHOME", "outro-python")
    monkeypatch.setenv("PYTHONPATH", "outra-bancada")
    env = executor.ambiente_da_bancada(bancada[0], executor.carregar_bancada(bancada[0]))
    assert "PYTHONHOME" not in env and "PYTHONPATH" not in env
    assert env["PYTHONUTF8"] == "1"


def test_selecao_ausente_nao_aceita_resultado(bancada, monkeypatch):
    _, rollout = protocolo(bancada, monkeypatch)
    original = executor.selecao_registrada
    def apagar(estado, alvo):
        rollout.unlink()
        return original(estado, alvo)
    monkeypatch.setattr(executor, "selecao_registrada", apagar)
    estado = iniciar(bancada)
    assert estado["estado"] == "incerto"
    assert "não foi encontrado" in estado["erro"]


def test_turno_que_reabre_apos_conclusao_continua_incerto():
    estado = {}
    eventos = [json.dumps({'type':tipo}) for tipo in ('turn.started','turn.completed','turn.started')]
    executor.aplicar_eventos(estado,'\n'.join(eventos)+'\n',completo=True)
    assert not estado['turno_concluido']


def plano_existente(alvo, tarefa="TAR-1001"):
    return sessao.derivar_plano("ci", "piloto", raiz=alvo.parent / "principal", celulas=["ci"],
        usa_redis=False, sobe_ambiente=False, tarefa_da_fila=tarefa)


def test_adocao_preserva_checkout_ramo_e_registro_historico(bancada):
    alvo = bancada[0]
    historico = sessao.arquivo_de_estado_inicial(alvo).read_bytes()
    antes = git(alvo, "worktree", "list", "--porcelain")
    plano = sessao.adotar_bancada_existente(plano_existente(alvo), alvo)
    assert plano.worktree == alvo and plano.branch == "agent/ci/piloto"
    assert git(alvo, "worktree", "list", "--porcelain") == antes
    sessao.registrar_sessao_atual(plano)
    assert sessao.arquivo_de_estado_inicial(alvo).read_bytes() == historico
    assert executor.carregar_bancada(alvo)["tarefa_da_fila"] == "TAR-1001"


def test_reuso_exige_reserva_anterior_devolvida_e_trabalho_contabilizado(bancada, monkeypatch):
    alvo = bancada[0]
    plano = plano_existente(alvo, "TAR-1002")
    git(alvo, "checkout", "-b", "codex/ci/segunda")
    with pytest.raises(sessao.ErroDeSessao, match="reserva da tarefa anterior"):
        sessao.adotar_bancada_existente(plano, alvo)
    monkeypatch.setattr(executor.reservar, "ler_reserva", lambda *args: None)
    (alvo / "anterior.txt").write_text("trabalho de outra tarefa")
    with pytest.raises(sessao.ErroDeSessao, match="não contabilizado"):
        sessao.adotar_bancada_existente(plano, alvo)
    (alvo / "anterior.txt").unlink()
    fila = alvo / "fila/tarefas"
    fila.mkdir(parents=True, exist_ok=True)
    (fila / "002-tarefa.json").write_text(json.dumps({"id":"TAR-1002"}))
    plano = sessao.adotar_bancada_existente(plano, alvo)
    sessao.registrar_sessao_atual(plano)
    assert executor.carregar_bancada(alvo)["branch"] == "codex/ci/segunda"
    assert executor.carregar_bancada(alvo)["tarefa_da_fila"] == "TAR-1002"
    assert json.loads(sessao.arquivo_de_estado_inicial(alvo).read_text())["plano"]["tarefa_da_fila"] == "TAR-1001"


def test_adocao_recusa_principal_checkout_alheio_e_detached(bancada):
    alvo = bancada[0]
    plano = plano_existente(alvo)
    with pytest.raises(sessao.ErroDeSessao, match="isolado"):
        sessao.adotar_bancada_existente(plano, alvo.parent / "principal")
    outra = alvo.parent / "outra"
    outra.mkdir()
    (outra / ".git").write_text("gitdir: inexistente")
    with pytest.raises(sessao.ErroDeSessao, match="registrada"):
        sessao.adotar_bancada_existente(plano, outra)
    git(alvo, "checkout", "--detach")
    with pytest.raises(sessao.ErroDeSessao, match="sem ramo"):
        sessao.adotar_bancada_existente(plano, alvo)


def test_adocao_e_novo_inicio_recusam_tentativa_anterior_sem_limpeza(bancada):
    alvo = bancada[0]
    pasta = sessao.caminho_da_trava_da_bancada(alvo).parent.parent / "codex" / sessao.identidade_duravel_da_bancada(alvo)[:32]
    executor.gravar(pasta / "TAR-999.json", {"selo_limpeza":str(pasta / "ausente.json"), "processos_encerrados":False})
    with pytest.raises(executor.ErroDeInstrumentacao, match="limpeza comprovada"):
        sessao.adotar_bancada_existente(plano_existente(alvo), alvo)
    with pytest.raises(executor.ErroDeInstrumentacao, match="limpeza comprovada"):
        iniciar(bancada)
    assert bancada[2] == []


@pytest.mark.parametrize("provider", ["ollama", None])
def test_provider_ausente_ou_diferente_recusa_resultado(bancada, monkeypatch, provider):
    _, rollout = protocolo(bancada, monkeypatch)
    original = executor.selecao_registrada
    def mudar(estado, alvo):
        eventos = [json.loads(linha) for linha in rollout.read_text().splitlines()]
        eventos[0]["payload"]["model_provider"] = provider
        rollout.write_text("\n".join(json.dumps(ev) for ev in eventos)+"\n")
        return original(estado, alvo)
    monkeypatch.setattr(executor, "selecao_registrada", mudar)
    estado = iniciar(bancada)
    assert estado["estado"] == "incerto"
    assert "Provider" in estado["erro"]


def test_falha_antes_dispatch_preserva_tentativa_sem_lixo_e_pode_retomar(bancada, monkeypatch):
    monkeypatch.setattr(executor.shutil, "which", lambda nome: None)
    primeira = iniciar(bancada)
    assert primeira["estado"] == "preparacao_falhou"
    assert primeira["processos_encerrados"] and "transitorio" not in primeira
    assert "thread_id" not in primeira
    reconciliada = executor.executar("reconciliar", bancada[0])
    assert reconciliada["tentativa"] == primeira["tentativa"]
    monkeypatch.setattr(executor.shutil, "which", lambda nome: sys.executable)
    protocolo(bancada, monkeypatch)
    retomada = executor.executar("retomar", bancada[0], pedido="Retome depois de reparar a preparação")
    assert retomada["estado"] == "resultado_recebido"
    assert retomada["tentativa"] == primeira["tentativa"]
    assert sum(c[0] == "pegar" for c in bancada[2]) == 1


def test_falha_de_criacao_do_grupo_sem_filho_nao_inventa_resultado(bancada, monkeypatch):
    protocolo(bancada, monkeypatch)
    def falhar():
        raise OSError("Falha na criação do grupo")
    monkeypatch.setattr(executor, "criar_grupo", falhar)
    estado = iniciar(bancada)
    assert estado["estado"] == "incerto"
    assert estado["processos_encerrados"]
    assert not Path(estado["transitorio"]).exists()
    assert "thread_id" not in estado


def test_boletim_da_adocao_mede_bancada_real_e_declaracao_mostra_tar(bancada, monkeypatch, capsys):
    import boletim
    alvo = bancada[0]
    medidas = []
    def interromper(onde):
        medidas.append(onde)
        raise executor.ErroDeInstrumentacao("fim da sonda sem rede", "nenhuma escrita")
    monkeypatch.setattr(boletim, "coletar", interromper)
    monkeypatch.setattr(sessao, "raiz_declarada", lambda onde: onde)
    monkeypatch.setattr(sessao, "celulas_declaradas", lambda onde: ["ci"])
    monkeypatch.setattr(sessao, "medir_fase", lambda *args, **kwargs: None)
    assert sessao.main(["--raiz",str(alvo.parent / "principal"),"--celula","ci","--tarefa","piloto",
                       "--tar","1001","--sem-container","--worktree",str(alvo)]) == 2
    assert medidas == [alvo]
    assert f"Boletim da bancada: {alvo}" in capsys.readouterr().out
    texto = sessao.declaracao(plano_existente(alvo), resumo="")
    assert "Tarefa: TAR-1001." in texto and "não informada" not in texto


def test_windows_libera_handle_de_processo_apos_colher_saida(tmp_path):
    if os.name != "nt":
        pytest.skip("Handle nativo específico do Windows")
    from pr_processos_windows import GrupoWindows
    grupo = GrupoWindows()
    try:
        processo = grupo.iniciar([sys.executable,"-c","print('concluído')"], tmp_path, os.environ)
        saida, _ = processo.communicate(timeout=10)
        assert "concluído" in saida and processo.wait(timeout=1) == 0
        assert processo.handle is None
    finally:
        grupo.encerrar()


@pytest.mark.parametrize("defeito", ["evento_lista", "payload_lista", "timestamp_sem_fuso", "timestamp_numero"])
def test_rollout_invalido_termina_incerto_e_reconciliacao_nao_devolve_sucesso(bancada, monkeypatch, defeito):
    _, rollout = protocolo(bancada, monkeypatch)
    original = executor.selecao_registrada
    def corromper(estado, alvo):
        eventos = [json.loads(linha) for linha in rollout.read_text().splitlines()]
        if defeito == "evento_lista": eventos[1] = []
        if defeito == "payload_lista": eventos[1]["payload"] = []
        if defeito == "timestamp_sem_fuso": eventos[1]["timestamp"] = "2099-01-01T00:00:00"
        if defeito == "timestamp_numero": eventos[1]["timestamp"] = 123
        rollout.write_text("\n".join(json.dumps(ev) for ev in eventos)+"\n")
        return original(estado, alvo)
    monkeypatch.setattr(executor, "selecao_registrada", corromper)
    estado = iniciar(bancada)
    assert estado["estado"] == "incerto" and "selecao_local" not in estado
    reconciliada = executor.executar("reconciliar", bancada[0])
    assert reconciliada["estado"] == "incerto"


def test_reconciliacao_revalida_resultado_herdado_sem_selecao(bancada, monkeypatch):
    _, rollout = protocolo(bancada, monkeypatch)
    estado = iniciar(bancada)
    pasta = sessao.caminho_da_trava_da_bancada(bancada[0]).parent.parent / "codex" / sessao.identidade_duravel_da_bancada(bancada[0])[:32]
    estado.pop("selecao_local")
    executor.gravar(pasta / "TAR-1001.json", estado)
    assert executor.executar("reconciliar", bancada[0])["selecao_local"]["provider"] == "openai"
    rollout.unlink()
    incerto = executor.executar("reconciliar", bancada[0])
    assert incerto["estado"] == "incerto" and "selecao_local" not in incerto


def test_morte_apos_saida_antes_guardas_deixa_estado_intermediario_e_reconcilia_incerto(bancada, monkeypatch):
    protocolo(bancada, monkeypatch)
    original = executor.selecao_registrada
    def interromper(estado, alvo):
        pasta = sessao.caminho_da_trava_da_bancada(alvo).parent.parent / "codex" / sessao.identidade_duravel_da_bancada(alvo)[:32]
        persistido = executor.ler(pasta / "TAR-1001.json")
        assert persistido["estado"] == "validando_resultado"
        assert persistido["processos_encerrados"]
        raise KeyboardInterrupt()
    monkeypatch.setattr(executor, "selecao_registrada", interromper)
    with pytest.raises(KeyboardInterrupt):
        iniciar(bancada)
    monkeypatch.setattr(executor, "selecao_registrada", original)
    reconciliada = executor.executar("reconciliar", bancada[0])
    assert reconciliada["estado"] == "incerto" and "selecao_local" not in reconciliada
    retomada = executor.executar("retomar", bancada[0], pedido="Continue a mesma tentativa")
    assert retomada["estado"] == "resultado_recebido"
    assert retomada["tentativa"] == reconciliada["tentativa"]


def test_morte_real_antes_guardas_nao_persiste_sucesso_e_reconciliacao_limpa(bancada, tmp_path):
    alvo, reserva, _ = bancada
    script = "\n".join([
        "import os,sys,json",
        "from pathlib import Path",
        f"sys.path.insert(0,{str(Path(executor.__file__).parent)!r})",
        f"sys.path.insert(0,{str(Path(__file__).parent)!r})",
        "import pytest,sessao,executor_codex as executor,test_executor_codex as prova",
        "m=pytest.MonkeyPatch()",
        f"alvo=Path({str(alvo)!r})",
        f"m.setattr(Path,'home',lambda:Path({str(Path.home())!r}))",
        f"reserva=json.loads({json.dumps(reserva)!r})",
        "m.setattr(executor.reservar,'ler_reserva',lambda *args:tuple(reserva))",
        "m.setattr(executor.fila,'bancada_contem_main_publicada',lambda *args:True)",
        "m.setattr(executor.fila,'estado_ao_vivo',lambda onde,tarefas,eventos:(executor.fila.calcular_estados(tarefas,eventos),set(),{}))",
        "m.setattr(executor.fila,'cmd_pegar',lambda *args:0)",
        "m.setattr(executor.fila,'cmd_checkpoint',lambda *args:0)",
        "m.setattr(executor,'contexto',lambda *args:'brief mínimo')",
        "m.setattr(executor.shutil,'which',lambda *args:sys.executable)",
        "prova.protocolo((alvo,reserva,[]),m)",
        "m.setattr(executor,'selecao_registrada',lambda *args:os._exit(73))",
        "executor.executar('iniciar',alvo,modelo='gpt-6-sol',esforco='high',pedido='pedido')",
    ])
    proc = subprocess.run([sys.executable,"-c",script],capture_output=True,text=True,timeout=20)
    assert proc.returncode == 73, proc.stderr
    pasta = sessao.caminho_da_trava_da_bancada(alvo).parent.parent / "codex" / sessao.identidade_duravel_da_bancada(alvo)[:32]
    estado = executor.ler(pasta / "TAR-1001.json")
    assert estado["estado"] == "validando_resultado" and estado["processos_encerrados"]
    assert "selecao_local" not in estado
    assert Path(estado["transitorio"]).exists()
    reconciliada = executor.executar("reconciliar",alvo)
    assert reconciliada["estado"] == "incerto"
    assert reconciliada["tentativa"] == estado["tentativa"]
    assert not Path(estado["transitorio"]).exists()


@pytest.mark.parametrize("tipo", ["pai", "pasta", "tentativa", "nome_invalido", "fora", "relativo"])
def test_limpeza_recusa_caminho_adverso_sem_chamar_exclusao(tmp_path, monkeypatch, tipo):
    pasta = tmp_path / "codex"
    tentativa = "a" * 32
    base = pasta / tentativa[:16]
    caminhos = {"pai":base / "..", "pasta":pasta, "tentativa":base,
                "nome_invalido":base / "lixo", "fora":tmp_path / ("b" * 12), "relativo":Path("a" * 12)}
    removidos = []
    monkeypatch.setattr(executor.shutil, "rmtree", lambda alvo:removidos.append(alvo))
    with pytest.raises(executor.ErroDeInstrumentacao, match="limpeza recusada"):
        executor.remover_transitorio_da_tentativa(pasta,{"tentativa":tentativa,"transitorio":str(caminhos[tipo])})
    assert removidos == []


def test_reconciliacao_recusa_transitorio_pai_sem_excluir_outro_estado(bancada, monkeypatch):
    protocolo(bancada, monkeypatch)
    estado = iniciar(bancada)
    pasta = sessao.caminho_da_trava_da_bancada(bancada[0]).parent.parent / "codex" / sessao.identidade_duravel_da_bancada(bancada[0])[:32]
    estado["transitorio"] = str(pasta / estado["tentativa"][:16] / "..")
    executor.gravar(pasta / "TAR-1001.json",estado)
    outra_tar = pasta / "TAR-1002.json"
    executor.gravar(outra_tar,{"sentinela":"preservada"})
    removidos = []
    monkeypatch.setattr(executor.shutil,"rmtree",lambda alvo:removidos.append(alvo))
    with pytest.raises(executor.ErroDeInstrumentacao,match="limpeza recusada"):
        executor.executar("reconciliar",bancada[0])
    assert removidos == [] and executor.ler(outra_tar) == {"sentinela":"preservada"}


def test_limpeza_so_remove_alvo_absoluto_verificado_da_tentativa(tmp_path, monkeypatch):
    pasta = tmp_path / "codex"
    estado = {"tentativa":"a" * 32}
    alvo = pasta / ("a" * 16) / ("b" * 12)
    alvo.mkdir(parents=True)
    estado["transitorio"] = str(alvo)
    removidos = []
    monkeypatch.setattr(executor.shutil,"rmtree",lambda alvo:removidos.append(alvo))
    executor.remover_transitorio_da_tentativa(pasta,estado)
    assert removidos == [alvo.resolve()]



def abrir_com_fila_real(bancada, monkeypatch):
    alvo, _, _ = bancada
    prs = {}
    monkeypatch.setattr(executor.fila,"cmd_pegar",PEGAR_REAL)
    monkeypatch.setattr(executor.fila,"estado_ao_vivo",ESTADO_AO_VIVO_REAL)
    monkeypatch.setattr(executor.fila,"reservas_no_servidor",lambda onde:{"TAR-1001"})
    monkeypatch.setattr(executor.fila,"prs_citando_tarefas",lambda onde:prs)
    monkeypatch.setattr(executor.fila,"rotular_orfaos",lambda *args:[])
    monkeypatch.setattr(executor.reservar,"confirmar_intencao",lambda *args:True)
    plano = sessao.adotar_bancada_existente(plano_existente(alvo),alvo)
    abertura = sessao.Sessao(plano)
    monkeypatch.setattr(abertura,"conferir_pecas_locais",lambda:{"git":"git","gh":"gh"})
    monkeypatch.setattr(abertura,"conferir",lambda:None)
    monkeypatch.setattr(abertura,"buscar",lambda git:None)
    monkeypatch.setattr(abertura,"gerar_indice",lambda git:None)
    monkeypatch.setattr(abertura,"anunciar_pr",lambda gh:prs.update({"TAR-1001":"PR #7"}))
    assert "Tarefa: TAR-1001." in abertura.rodar()
    assert sessao.arquivo_de_sessao_atual(alvo).exists()
    return plano


def test_abertura_real_e_inicio_adotam_posse_propria_ativa_sem_nova_reivindicacao(bancada, monkeypatch):
    abrir_com_fila_real(bancada,monkeypatch)
    alvo = bancada[0]
    erros = []
    tarefas = executor.fila.carregar_tarefas(alvo,erros)
    eventos = executor.fila.carregar_eventos(alvo,tarefas,erros)
    estados,_,_ = executor.fila.estado_ao_vivo(alvo,tarefas,eventos)
    assert not erros and estados["TAR-1001"]["estado"] == executor.fila.EM_EXECUCAO
    assert len(eventos) == 1 and eventos[0]["evento"] == "reivindicada"
    def nao_reivindicar(*args):
        pytest.fail("iniciar tentou reivindicar de novo a posse já aberta")
    monkeypatch.setattr(executor.fila,"cmd_pegar",nao_reivindicar)
    protocolo(bancada,monkeypatch)
    estado = iniciar(bancada)
    assert estado["estado"] == "resultado_recebido"
    assert estado["reserva"] == bancada[1][0]
    assert len(executor.fila.carregar_eventos(alvo,tarefas,[])) == 1


@pytest.mark.parametrize("defeito", ["dono", "expirada", "historico", "sem_abertura", "abertura_anterior", "main", "terminal", "dependencia"])
def test_adocao_de_ativa_recusa_posse_historico_ou_fila_incompativeis(bancada, monkeypatch, defeito):
    abrir_com_fila_real(bancada,monkeypatch)
    alvo = bancada[0]
    if defeito == "dono": bancada[1][1]["dono"] = "outra-bancada"
    if defeito == "expirada": bancada[1][1]["expira_em"] = "2000-01-01T00:00:00+00:00"
    if defeito == "sem_abertura": sessao.arquivo_de_sessao_atual(alvo).unlink()
    if defeito == "abertura_anterior":
        p=sessao.arquivo_de_sessao_atual(alvo)
        e=executor.ler(p); e["preparada_em"]="2000-01-01T00:00:00+00:00"
        executor.gravar(p,e)
    if defeito == "main": monkeypatch.setattr(executor.fila,"bancada_contem_main_publicada",lambda *args:False)
    if defeito == "historico":
        p=next((alvo / "fila/eventos").glob("*.json"))
        e=json.loads(p.read_text(encoding="utf-8")); e["quem"]="outro-executor"
        p.write_text(json.dumps(e),encoding="utf-8")
    if defeito == "terminal":
        e=evento_da_prova("TAR-1001","cancelada",quem="operador",detalhe="cancelamento da prova",hora="23:59:59")
        (alvo / "fila/eventos" / (e["arquivo"]+".json")).write_text(json.dumps(e),encoding="utf-8")
    if defeito == "dependencia":
        t=tarefa_da_prova("1002",toca=["ci"])
        (alvo / "fila/tarefas" / (t["arquivo"]+".json")).write_text(json.dumps(t),encoding="utf-8")
        p=next((alvo / "fila/tarefas").glob("1001-*.json"))
        t=json.loads(p.read_text(encoding="utf-8")); t["depende_de"]=["TAR-1002"]
        p.write_text(json.dumps(t),encoding="utf-8")
    def nao_executar(*args):
        pytest.fail("uma guarda recusada iniciou processo")
    monkeypatch.setattr(executor,"executar_processo",nao_executar)
    with pytest.raises(executor.ErroDeInstrumentacao):
        iniciar(bancada)


def test_contexto_distingue_worktree_gravavel_principal_e_temp_descartavel(bancada, monkeypatch):
    alvo = bancada[0]
    dados = executor.carregar_bancada(alvo)
    monkeypatch.setattr(sessao, "contexto_direcionado", lambda *args, **kwargs:"CONTEXTO MINIMO")
    monkeypatch.setattr(sessao, "caminhos_da_tarefa", lambda *args:["ci/"])
    monkeypatch.setattr(sessao, "celulas_declaradas", lambda *args:["ci"])
    texto = CONTEXTO_REAL(alvo, dados, "Escreva resultado.json somente no escopo pedido")
    assert f"Bancada gravável desta tarefa: {alvo}" in texto
    assert f"clone principal {dados['raiz']}" in texto
    assert "TEMP/TMP/TMPDIR são scratch" in texto
    assert "pare sem redirecionar a entrega para TEMP" in texto


def test_subprocesso_que_grava_no_temp_preserva_dados_e_permite_retomada_da_mesma_tentativa(bancada, monkeypatch):
    alvo = bancada[0]
    thread, _ = protocolo(bancada, monkeypatch, gravar_temp=True)
    primeira = iniciar(bancada)
    artefato = Path(primeira["transitorio"]) / "pme04-piloto" / "resultado.json"
    assert primeira["estado"] == "incerto" and primeira["processos_encerrados"]
    assert artefato.read_text(encoding="utf-8") == '{"soma":18}'
    assert primeira["transitorios_preservados"] == [{"caminho":primeira["transitorio"],
                                                      "arquivos":["pme04-piloto/resultado.json"]}]
    assert not (alvo / "pme04-piloto").exists()
    with pytest.raises(executor.ErroDeInstrumentacao, match="reteve dados"):
        executor.conferir_devolucao(alvo)
    protocolo(bancada, monkeypatch, thread=thread)
    segunda = executor.executar("retomar",alvo,pedido="Refaça na bancada, preservando os dados do TEMP")
    assert segunda["tentativa"] == primeira["tentativa"] and segunda["thread_id"] == thread
    assert segunda["estado"] == "incerto" and artefato.exists()
    assert segunda["transitorios_preservados"] == primeira["transitorios_preservados"]
    destino = alvo / "pme04-piloto" / "resultado.json"
    destino.parent.mkdir()
    destino.write_bytes(artefato.read_bytes())
    assert destino.read_bytes() == artefato.read_bytes()
    artefato.unlink()
    artefato.parent.rmdir()
    reconciliada = executor.executar("reconciliar",alvo)
    assert reconciliada["transitorios_preservados"] == []
    assert reconciliada["estado"] == "incerto"
    assert reconciliada["erro"].startswith("Dados transitórios reconciliados")
    assert not Path(primeira["transitorio"]).exists()
    assert destino.read_text(encoding="utf-8") == '{"soma":18}'


def test_limpeza_remove_apenas_diretorios_vazios_sem_classificar_por_nome(tmp_path):
    pasta = tmp_path / "codex"
    tentativa = "a" * 32
    alvo = pasta / tentativa[:16] / ("b" * 12)
    (alvo / ".tmpXYZ" / "profundo").mkdir(parents=True)
    (alvo / "outro_diretorio_vazio").mkdir()
    assert executor.remover_transitorio_da_tentativa(pasta,{"tentativa":tentativa,"transitorio":str(alvo)}) == []
    assert not alvo.exists()


def test_inspecao_recusada_preserva_transitorio_inteiro(tmp_path, monkeypatch):
    pasta = tmp_path / "codex"
    estado = {"tentativa":"a" * 32}
    alvo = pasta / ("a" * 16) / ("b" * 12)
    alvo.mkdir(parents=True)
    original = Path.iterdir
    def recusar_inspecao(caminho):
        if caminho == alvo:
            raise PermissionError("leitura recusada no teste")
        return original(caminho)
    monkeypatch.setattr(Path,"iterdir",recusar_inspecao)
    achados = executor.remover_transitorio_da_tentativa(pasta,{**estado,"transitorio":str(alvo)})
    assert "não inspecionável" in achados[0]
    assert alvo.exists()
