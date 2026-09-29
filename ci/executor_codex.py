"""Liga a bancada da fila ao Codex CLI, com supervisão explícita e retomada."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

import fila
import reservar
import sessao
from _nucleo import ErroDeInstrumentacao, configurar_saida
from telemetria import redigir

MODELOS = ("gpt-6-sol", "gpt-6-luna")
ESFORCOS = ("low", "medium", "high", "xhigh", "max")
INTERVALO_POSSE = 15
PRAZO = 3600
LIMITE_RUNTIME = "O CLI atesta a seleção local; o modelo usado pelo backend não é verificável por este adaptador."


def agora():
    return datetime.now(timezone.utc).isoformat()


def recusar(motivo):
    raise ErroDeInstrumentacao(motivo, "Preserve a bancada e consulte o checkpoint antes de retomar; nenhum resultado foi aceito.")


def gravar(caminho, dados):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(".tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporario.replace(caminho)


def ler(caminho):
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError) as erro:
        recusar(f"Estado da tentativa ilegível: {erro}")
    if not isinstance(dados, dict):
        recusar("Estado da tentativa precisa ser um objeto JSON")
    return dados


def carregar_bancada(bancada):
    registro = sessao.arquivo_de_sessao_atual(bancada)
    if not registro.exists():
        registro = sessao.arquivo_de_estado_inicial(bancada)
    snapshot = ler(registro)
    identidade = sessao.identidade_duravel_da_bancada(bancada)
    if snapshot.get("identidade") != identidade:
        recusar("Registro inicial pertence a outra bancada")
    dados = snapshot.get("plano", {})
    if not isinstance(dados, dict) or Path(dados.get("worktree", "")).resolve() != bancada:
        recusar("Plano não identifica esta bancada")
    if not (bancada / ".git").is_file() or dados.get("raiz") == str(bancada):
        recusar("Codex só executa em worktree isolado; abra ci/sessao.py primeiro")
    branch = sessao.correr_de_verdade(["git", "symbolic-ref", "--short", "HEAD"], cwd=bancada)
    if branch.exit_code or branch.stdout.strip() != dados.get("branch"):
        recusar("Ramo da bancada diverge do registro inicial")
    tid = dados.get("tarefa_da_fila", "")
    if not tid or sessao.normalizar_tarefa_da_fila(tid) != tid:
        recusar("Bancada sem tarefa da fila; reabra a sessão com --tar TAR-NNN")
    return dados


def conferir_posse(bancada, tid, versao=None):
    atual = reservar.ler_reserva(bancada, f"tarefa-{tid}")
    if atual is None:
        recusar("A tarefa perdeu a reserva remota")
    sha, corpo = atual
    try:
        expira = datetime.fromisoformat(corpo.get("expira_em", ""))
    except (ValueError, TypeError):
        recusar("Reserva sem expiração válida")
    if (corpo.get("tipo") != "intencao" or corpo.get("chave") != f"tarefa-{tid}"
            or corpo.get("dono") != reservar.identidade_da_bancada(bancada)
            or expira.tzinfo is None or expira <= datetime.now(timezone.utc)
            or (versao is not None and sha != versao)):
        recusar("Posse vencida, transferida ou substituída; esta tentativa não pode produzir efeitos")
    return sha


def adquirir_tarefa(bancada, dados):
    tid, quem = dados["tarefa_da_fila"], dados["quem_no_balcao"]
    if not fila.bancada_contem_main_publicada(bancada):
        recusar("A fila publicada mudou; incorpore origin/main antes de iniciar")
    erros = []
    tarefas = fila.carregar_tarefas(bancada, erros)
    eventos = fila.carregar_eventos(bancada, tarefas, erros)
    if erros or tid not in tarefas:
        recusar("Fila inválida ou tarefa ausente; confira o brief antes de iniciar")
    dependencia = fila.recusa_por_dependencia_nao_concluida(tarefas, eventos, tid)
    if dependencia:
        recusar("; ".join(dependencia))
    estados, reservas, _ = fila.estado_ao_vivo(bancada, tarefas, eventos)
    atual = estados[tid]
    if atual["estado"] in {fila.NA_FILA, fila.REIVINDICADA}:
        chamada_fila(fila.cmd_pegar, bancada, argparse.Namespace(tarefa=tid, quem=quem))
        return conferir_posse(bancada, tid)
    if atual["estado"] != fila.EM_EXECUCAO:
        recusar(f"A tarefa está {atual['estado']}; preserve a bancada e confira a fila")
    ultimo = next((ev for ev in reversed(eventos) if ev.get("tarefa") == tid
                   and ev.get("evento") in fila.EVENTOS_DE_CICLO), None)
    if (tid not in reservas or not ultimo or ultimo["evento"] != "reivindicada" or ultimo.get("quem") != quem
            or atual.get("quem") not in {quem, dados["branch"]}):
        recusar("Tarefa ativa não tem reivindicação própria compatível; nenhuma execução foi iniciada")
    registro = sessao.arquivo_de_sessao_atual(bancada)
    if not registro.exists():
        recusar("Tarefa ativa sem abertura operacional concluída; reabra a sessão antes de iniciar")
    preparado = ler(registro).get("preparada_em")
    try:
        instante = datetime.fromisoformat(preparado)
    except (ValueError, TypeError):
        recusar("Abertura operacional sem data válida; confira o registro antes de iniciar")
    if (instante.tzinfo is None or instante > datetime.now(timezone.utc)
            or instante < ultimo["_quando"]):
        recusar("Abertura operacional não comprova a reivindicação vigente; reabra a sessão antes de iniciar")
    reserva = conferir_posse(bancada, tid)
    return conferir_posse(bancada, tid, reserva)


def ambiente_da_bancada(bancada, dados):
    env = dict(os.environ)
    env.pop("PYTHONHOME", None)
    env.pop("PYTHONPATH", None)
    if dados.get("sobe_ambiente"):
        configuracao = sessao.carregar_env_de_sessao(Path(dados["arquivo_env"]))
        if Path(configuracao.get("SESSAO_WORKTREE", "")).resolve() != bancada:
            recusar("Configuração de teste pertence a outra bancada")
        venv = Path(configuracao.get("SESSAO_VENV", ""))
        binario = venv / ("Scripts" if os.name == "nt" else "bin")
        python = binario / ("python.exe" if os.name == "nt" else "python")
        chave = sessao.identidade_do_venv(bancada / "services" / dados["celula"] / "requirements.txt", raiz_do_worktree=bancada)
        if (venv.name != chave or not python.is_file()
                or (venv / ".instalado").read_text(encoding="utf-8") != chave):
            recusar("Dependências ou Python mudaram; reabra a sessão para preparar o ambiente compatível")
        sonda = sessao.correr_de_verdade([str(python), "-c", "import json,sys; print(json.dumps({'prefix':sys.prefix,'version':sys.version}))"],
                                        cwd=bancada, env=env, timeout=30)
        try:
            info = json.loads(sonda.stdout)
        except ValueError:
            recusar("Python preparado não respondeu à sondagem; reabra a sessão")
        if sonda.exit_code or Path(info.get("prefix", "")).resolve() != venv.resolve() or info.get("version") != sys.version:
            recusar("Interpretador preparado diverge do Python da abertura; reabra a sessão")
        env.update(configuracao)
        env["VIRTUAL_ENV"] = str(venv)
        env["PATH"] = str(binario) + os.pathsep + env.get("PATH", "")
    env["PYTHONUTF8"] = "1"
    return env


def chamada_fila(funcao, bancada, argumentos):
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        codigo = funcao(bancada, argumentos)
    if codigo:
        recusar(redigir(buffer.getvalue()))


def checkpoint(bancada, estado):
    conferir_posse(bancada, estado["tarefa"], estado["reserva"])
    chamada_fila(fila.cmd_checkpoint, bancada, argparse.Namespace(
        tarefa=estado["tarefa"], quem=estado["quem"], plano="PME04 / execução supervisionada",
        ultimo_avanco=f"Tentativa {estado['tentativa']}: {estado['estado']}; sessão {estado.get('thread_id') or 'ainda não emitida'}",
        proxima_acao="Conferir o resultado e a jornada antes do aceite" if estado["estado"] == "resultado_recebido" else "Reconciliar os processos e retomar a mesma tentativa",
        verificacao=[f"Seleção local {estado['modelo']} / {estado['esforco']}. {LIMITE_RUNTIME}"], contexto=""))


def comando_codex(executavel, bancada, estado, prompt):
    comando = [executavel, "exec", "-m", estado["modelo"], "-c",
               f'model_reasoning_effort="{estado["esforco"]}"', "-c", 'model_provider="openai"', "--sandbox", "workspace-write",
               "-C", str(bancada), "--json"]
    if estado.get("thread_id"):
        comando.extend(["resume", estado["thread_id"]])
    comando.append(prompt)
    if os.name == "nt" and len(subprocess.list2cmdline(comando)) > 30000:
        recusar("Contexto excede o limite do processo Windows; reduza o brief aos caminhos necessários")
    return comando


def contexto(bancada, dados, pedido):
    erros = []
    tarefas = fila.carregar_tarefas(bancada, erros)
    tarefa = tarefas.get(dados["tarefa_da_fila"])
    if erros or tarefa is None:
        recusar("A tarefa da bancada não tem um brief válido na fila")
    pacote = sessao.contexto_direcionado(bancada, objetivo=tarefa["titulo"],
        caminhos=sessao.caminhos_da_tarefa(tarefa, sessao.celulas_declaradas(bancada)),
        aceite=[tarefa["evidencia_exigida"]], restricoes=[tarefa["despacho"]])
    return (pacote + "\n\n" + pedido + "\n\nBancada gravável desta tarefa: " + str(bancada) +
            ". Este é o worktree isolado autorizado; não o confunda com o clone principal " + dados["raiz"] +
            ", que é somente leitura. O escopo de escrita dentro da bancada continua sendo apenas o do pedido. "
            "TEMP/TMP/TMPDIR são scratch da tentativa e serão descartados; nunca grave artefatos finais ali. "
            "Se uma escrita na bancada for recusada, informe o erro concreto e pare sem redirecionar a entrega para TEMP. "
            "Execução supervisionada. Não crie subagentes nem altere modelo ou esforço. "
            "A publicação e o aceite dependem do canal oficial. "
            "Se interrompido, preserve arquivos e registre o próximo comando concreto.\n")


def aplicar_eventos(estado, texto, *, completo=False):
    linhas = texto.splitlines(keepends=True)
    if linhas and not linhas[-1].endswith("\n") and not completo:
        linhas.pop()
    eventos = []
    for linha in linhas:
        try:
            evento = json.loads(linha)
        except ValueError:
            recusar("Codex devolveu uma linha que não é JSON; confira o log da tentativa")
        if not isinstance(evento, dict) or not isinstance(evento.get("type"), str):
            recusar("Evento Codex incompatível; confira a versão do CLI")
        eventos.append(evento)
    for evento in eventos:
        if evento["type"] == "thread.started":
            try:
                tid = str(uuid.UUID(evento.get("thread_id", "")))
            except (ValueError, TypeError, AttributeError):
                recusar("Identidade da sessão Codex inválida")
            if estado.get("thread_id") and estado["thread_id"] != tid:
                recusar("Codex tentou retomar outra sessão")
            estado["thread_id"] = tid
    if completo:
        terminal = [ev for ev in eventos if ev["type"] in ("turn.started", "turn.completed", "turn.failed")]
        estado["turno_concluido"] = bool(terminal and terminal[-1]["type"] == "turn.completed"
                                         and any(ev["type"] == "turn.started" for ev in terminal))
        estado["usage"] = terminal[-1].get("usage") if terminal else None
    return eventos


def selecao_registrada(estado, bancada, codex_home=None):
    tid = estado.get("thread_id")
    if not tid:
        recusar("Codex não emitiu a identidade da sessão")
    base = codex_home or Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    arquivos = list((base / "sessions").glob(f"*/*/*/rollout-*-{tid}.jsonl"))
    if len(arquivos) != 1:
        recusar("Rollout exato da sessão não foi encontrado; seleção real não foi medida")
    selecoes = []
    provider = None
    for linha in arquivos[0].read_text(encoding="utf-8").splitlines():
        try:
            evento = json.loads(linha)
        except ValueError:
            recusar("Rollout contém uma linha inválida; a seleção local não foi comprovada")
        if not isinstance(evento, dict):
            recusar("Evento do rollout não é um objeto; a seleção local não foi comprovada")
        if evento.get("type") not in {"session_meta", "turn_context"}:
            continue
        payload = evento.get("payload")
        if not isinstance(payload, dict):
            recusar("Payload do rollout não é um objeto; a seleção local não foi comprovada")
        if evento["type"] == "session_meta":
            if payload.get("id") == tid:
                provider = payload.get("model_provider")
            continue
        try:
            timestamp = datetime.fromisoformat(evento["timestamp"].replace("Z", "+00:00"))
            iniciada = datetime.fromisoformat(estado["iniciada_em"])
        except (ValueError, TypeError, KeyError, AttributeError):
            recusar("Timestamp do rollout inválido; a seleção local não foi comprovada")
        if timestamp.tzinfo is None or iniciada.tzinfo is None:
            recusar("Timestamp do rollout sem fuso; a seleção local não foi comprovada")
        if timestamp < iniciada:
            continue
        if (payload.get("model") != estado["modelo"] or payload.get("effort") != estado["esforco"]
                or not isinstance(payload.get("cwd"), str) or Path(payload["cwd"]).resolve() != bancada):
            recusar("Seleção local do runtime diverge do modelo, esforço ou bancada autorizados")
        selecoes.append({"modelo": payload["model"], "esforco": payload["effort"]})
    if provider != "openai":
        recusar("Provider registrado não é OpenAI; não há prova da seleção autorizada")
    if not selecoes:
        recusar("Rollout não tem seleção local deste turno; não há prova do modelo")
    return {"provider": provider, "turnos": selecoes, "limite": LIMITE_RUNTIME}


def criar_grupo():
    if os.name == "nt":
        from pr_processos_windows import GrupoWindows
        return GrupoWindows()
    from pr_processos_linux import GrupoLinux
    return GrupoLinux()


def confirmar_limpeza(estado):
    if estado.get("processos_encerrados"):
        return True
    if estado.get("grupo_windows"):
        from pr_processos_windows import confirmar_encerramento
        return confirmar_encerramento(estado["grupo_windows"])
    selo = Path(estado["selo_limpeza"])
    if not selo.exists():
        return False
    prova = ler(selo)
    return prova.get("encerrado") is True and prova.get("selo") == selo.name



def remover_transitorio_da_tentativa(pasta, estado):
    tentativa = estado.get("tentativa")
    caminho = estado.get("transitorio")
    if (not isinstance(tentativa, str) or not re.fullmatch(r"[0-9a-f]{32}", tentativa)
            or not isinstance(caminho, str)):
        recusar("Identidade do transitório inválida; limpeza recusada")
    transitorio = Path(caminho)
    if (not transitorio.is_absolute() or ".." in transitorio.parts
            or not re.fullmatch(r"[0-9a-f]{12}", transitorio.name)):
        recusar("Nome ou caminho do transitório inválido; limpeza recusada")
    raiz_tentativa = pasta.resolve() / tentativa[:16]
    alvo = transitorio.resolve()
    if alvo.parent != raiz_tentativa or alvo.name != transitorio.name or not alvo.is_relative_to(raiz_tentativa):
        recusar("Transitório não pertence à pasta exata desta tentativa; limpeza recusada")
    if not alvo.exists():
        return []
    pendentes = [alvo]
    arquivos = []
    while pendentes:
        atual = pendentes.pop()
        try:
            entradas = list(atual.iterdir())
        except OSError as erro:
            return [f"conteúdo não inspecionável: {redigir(str(erro))}"]
        for entrada in entradas:
            try:
                if entrada.is_symlink() or (hasattr(entrada, "is_junction") and entrada.is_junction()):
                    arquivos.append(entrada.relative_to(alvo).as_posix())
                elif entrada.is_dir():
                    pendentes.append(entrada)
                else:
                    arquivos.append(entrada.relative_to(alvo).as_posix())
            except OSError as erro:
                return [f"conteúdo não inspecionável: {redigir(str(erro))}"]
            if len(arquivos) >= 32:
                return arquivos + ["mais caminhos preservados; confira a pasta"]
    if arquivos:
        return arquivos
    shutil.rmtree(alvo)
    return []


def registrar_transitorio_preservado(estado, caminho, arquivos):
    registros = estado.setdefault("transitorios_preservados", [])
    registro = {"caminho": caminho, "arquivos": arquivos}
    registros[:] = [item for item in registros if item.get("caminho") != caminho] + [registro]
    estado["estado"] = "incerto"
    estado["erro"] = ("O transitório contém dados preservados fora da bancada. Confira " + caminho +
                     ", transfira os artefatos necessários à bancada autorizada e rode reconciliar. "
                     "A nova tarefa permanece bloqueada; nenhum resultado foi aceito.")


def conferir_devolucao(bancada):
    pasta = sessao.caminho_da_trava_da_bancada(bancada).parent.parent / "codex" / sessao.identidade_duravel_da_bancada(bancada)[:32]
    for arquivo in pasta.glob("TAR-*.json"):
        estado = ler(arquivo)
        if not confirmar_limpeza(estado):
            recusar("Uma tentativa anterior desta bancada ainda não tem limpeza comprovada")
        caminhos = [estado.get("transitorio")] + [item.get("caminho") for item in estado.get("transitorios_preservados", [])]
        if any(caminho and Path(caminho).exists() for caminho in caminhos):
            recusar("Uma tentativa anterior reteve dados no transitório; reconcilie e transfira os artefatos antes de outra tarefa")


def executar_processo(comando, bancada, estado, arquivo_estado, ambiente=None, *, intervalo=INTERVALO_POSSE, prazo=PRAZO):
    grupo = None
    estado["processos_encerrados"] = False
    estado["estado"] = "executando"
    gravar(arquivo_estado, estado)
    processo = None
    stdout = stderr = ""
    ultimo_posse = time.monotonic()
    limite = ultimo_posse + prazo
    env = {**(ambiente or os.environ), "TMP": estado["transitorio"], "TEMP": estado["transitorio"], "TMPDIR": estado["transitorio"],
           "PYTHONUTF8": "1"}
    try:
        grupo = criar_grupo()
        estado["grupo_windows"] = getattr(grupo, "identidade", None)
        gravar(arquivo_estado, estado)
        conferir_posse(bancada, estado["tarefa"], estado["reserva"])
        if os.name == "nt":
            processo = grupo.iniciar(comando, bancada, env)
        else:
            processo = grupo.iniciar(comando, bancada, env, encerramento=estado["selo_limpeza"])
        while True:
            try:
                stdout, stderr = processo.communicate(timeout=min(1, prazo))
                break
            except subprocess.TimeoutExpired as erro:
                stdout = erro.output or ""
                stderr = erro.stderr or ""
                if isinstance(stdout, bytes):
                    stdout = stdout.decode("utf-8", errors="replace")
                if isinstance(stderr, bytes):
                    stderr = stderr.decode("utf-8", errors="replace")
                aplicar_eventos(estado, stdout)
                Path(estado["log"]).write_text(redigir(stdout), encoding="utf-8", newline="\n")
                gravar(arquivo_estado, estado)
            if time.monotonic() - ultimo_posse >= intervalo:
                conferir_posse(bancada, estado["tarefa"], estado["reserva"])
                ultimo_posse = time.monotonic()
            if time.monotonic() >= limite:
                recusar(f"Prazo de {prazo}s excedido; a tentativa será interrompida")
        aplicar_eventos(estado, stdout, completo=True)
        estado["exit_code"] = processo.returncode
        estado["estado"] = "validando_resultado" if processo.returncode == 0 and estado["turno_concluido"] else "incerto"
    except KeyboardInterrupt:
        estado["estado"] = "interrompida"
        estado["erro"] = "Interrompida pelo supervisor; retome a mesma tentativa após reconciliar."
    except (ErroDeInstrumentacao, OSError, ValueError) as erro:
        estado["estado"] = "incerto"
        estado["erro"] = redigir(str(erro))
    finally:
        try:
            if grupo is not None:
                grupo.encerrar()
            estado["processos_encerrados"] = True
            if processo is not None:
                stdout, stderr = processo.communicate(timeout=5)
                aplicar_eventos(estado, stdout, completo=True)
        except (OSError, ValueError, subprocess.TimeoutExpired, ErroDeInstrumentacao) as erro:
            estado["estado"] = "incerto"
            estado["erro"] = "Limpeza não comprovada: " + redigir(str(erro))
        Path(estado["log"]).write_text(redigir(stdout), encoding="utf-8", newline="\n")
        if stderr:
            estado["diagnostico"] = redigir(stderr[-2000:])
        estado["terminada_em"] = agora()
        gravar(arquivo_estado, estado)
    return estado


def executar(acao, bancada, *, modelo=None, esforco=None, pedido=""):
    bancada = bancada.resolve()
    pasta = sessao.caminho_da_trava_da_bancada(bancada).parent.parent / "codex" / sessao.identidade_duravel_da_bancada(bancada)[:32]
    with sessao.trava_da_bancada(bancada, passo="executor Codex", esperar=False):
        dados = carregar_bancada(bancada)
        arquivo_estado = pasta / f"{dados['tarefa_da_fila']}.json"
        if acao == "iniciar":
            if arquivo_estado.exists():
                recusar("Esta bancada já tem uma tentativa; use reconciliar ou retomar")
            if modelo not in MODELOS or esforco not in ESFORCOS or not pedido.strip():
                recusar("Informe modelo permitido, esforço explícito e um pedido não vazio")
            conferir_devolucao(bancada)
            quem = dados["quem_no_balcao"]
            reserva = adquirir_tarefa(bancada, dados)
            estado = {"schema_version": 1, "tentativa": uuid.uuid4().hex, "bancada": str(bancada),
                      "identidade": sessao.identidade_duravel_da_bancada(bancada), "tarefa": dados["tarefa_da_fila"],
                      "quem": quem, "reserva": reserva, "modelo": modelo, "esforco": esforco,
                      "provider": "openai", "processos_encerrados": True,
                      "supervisao": "supervisionada", "limite_runtime": LIMITE_RUNTIME, "estado": "adquirida"}
        else:
            estado = ler(arquivo_estado)
            if (estado.get("identidade") != sessao.identidade_duravel_da_bancada(bancada)
                    or estado.get("tarefa") != dados["tarefa_da_fila"] or estado.get("modelo") not in MODELOS
                    or estado.get("esforco") not in ESFORCOS):
                recusar("Tentativa não pertence à tarefa e bancada atuais")
            if (modelo is not None and modelo != estado["modelo"]) or (esforco is not None and esforco != estado["esforco"]):
                recusar("Retomada não pode trocar modelo ou esforço da tentativa")
            conferir_posse(bancada, estado["tarefa"], estado["reserva"])
            if not confirmar_limpeza(estado):
                recusar("Os processos antigos não foram comprovadamente encerrados; a retomada está bloqueada")
            estado["processos_encerrados"] = True
            if acao == "reconciliar":
                if estado["estado"] in {"executando", "preparando", "validando_resultado"}:
                    estado["estado"] = "incerto"
                try:
                    if estado.get("log") and Path(estado["log"]).exists():
                        aplicar_eventos(estado, Path(estado["log"]).read_text(encoding="utf-8"), completo=True)
                    if estado["estado"] == "resultado_recebido":
                        if estado.get("exit_code") != 0 or not estado.get("turno_concluido"):
                            recusar("Resultado sem protocolo terminal comprovado; preserve a tentativa")
                        estado["selecao_local"] = selecao_registrada(estado, bancada)
                except (ErroDeInstrumentacao, OSError, ValueError) as erro:
                    estado["estado"] = "incerto"
                    estado.pop("selecao_local", None)
                    estado["erro"] = redigir(str(erro))
                caminhos = {item["caminho"] for item in estado.get("transitorios_preservados", [])}
                if estado.get("transitorio"):
                    caminhos.add(estado["transitorio"])
                retidos = []
                for caminho in caminhos:
                    arquivos = remover_transitorio_da_tentativa(pasta, {"tentativa": estado["tentativa"], "transitorio": caminho})
                    if arquivos:
                        retidos.append({"caminho": caminho, "arquivos": arquivos})
                estado["transitorios_preservados"] = retidos
                if retidos:
                    registrar_transitorio_preservado(estado, retidos[-1]["caminho"], retidos[-1]["arquivos"])
                elif estado.get("erro", "").startswith(("O transitório contém dados preservados",
                                                          "Há dados de um turno anterior preservados")):
                    estado["erro"] = "Dados transitórios reconciliados; retome a mesma tentativa para obter novo resultado."
                gravar(arquivo_estado, estado)
                checkpoint(bancada, estado)
                return estado
            if not pedido.strip() or (not estado.get("thread_id") and estado["estado"] != "preparacao_falhou"):
                recusar("Retomada exige pedido não vazio e sessão conhecida ou falha comprovada antes do dispatch")
        for campo in ("selecao_local", "erro", "diagnostico", "exit_code", "turno_concluido", "usage"):
            estado.pop(campo, None)
        estado["estado"] = "preparando"
        gravar(arquivo_estado, estado)
        transitorio = None
        try:
            executavel = shutil.which("codex")
            if not executavel:
                recusar("Codex CLI ausente do PATH; instale o runtime autorizado e retome")
            ambiente = ambiente_da_bancada(bancada, dados)
            prompt = contexto(bancada, dados, pedido)
            comando = comando_codex(executavel, bancada, estado, prompt)
            transitorio = pasta / estado["tentativa"][:16] / uuid.uuid4().hex[:12]
            transitorio.mkdir(parents=True)
            estado.update({"iniciada_em": agora(), "log": str(transitorio.parent / (transitorio.name + ".jsonl")),
                           "selo_limpeza": str(transitorio.parent / (transitorio.name + ".limpo.json")),
                           "transitorio": str(transitorio), "contexto_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                           "contexto_bytes": len(prompt.encode())})
            executar_processo(comando, bancada, estado, arquivo_estado, ambiente)
            conferir_posse(bancada, estado["tarefa"], estado["reserva"])
            validando = estado["estado"] == "validando_resultado"
            if validando:
                estado["selecao_local"] = selecao_registrada(estado, bancada)
            checkpoint(bancada, estado)
            if validando:
                estado["estado"] = "resultado_recebido"
        except (ErroDeInstrumentacao, OSError, ValueError) as erro:
            estado["estado"] = "preparacao_falhou" if estado["estado"] == "preparando" else "incerto"
            estado["erro"] = redigir(str(erro))
        finally:
            arquivos = []
            if transitorio is not None and estado.get("processos_encerrados"):
                arquivos = remover_transitorio_da_tentativa(pasta, estado)
                if arquivos:
                    registrar_transitorio_preservado(estado, str(transitorio), arquivos)
                elif any(Path(item["caminho"]).exists() for item in estado.get("transitorios_preservados", [])):
                    estado["estado"] = "incerto"
                    estado["erro"] = "Há dados de um turno anterior preservados no transitório; confira o registro e reconcilie."
            gravar(arquivo_estado, estado)
            if arquivos:
                checkpoint(bancada, estado)
        return estado


def main(argv=None):
    configurar_saida()
    parser = argparse.ArgumentParser(description="Execução Codex supervisionada numa bancada já preparada.")
    parser.add_argument("acao", choices=("iniciar", "retomar", "reconciliar"))
    parser.add_argument("--modelo", choices=MODELOS)
    parser.add_argument("--esforco", choices=ESFORCOS)
    parser.add_argument("--pedido", type=Path, help="Arquivo UTF-8 com o pedido autorizado; obrigatório para iniciar ou retomar.")
    args = parser.parse_args(argv)
    try:
        pedido = args.pedido.read_text(encoding="utf-8") if args.pedido else ""
        estado = executar(args.acao, Path.cwd(), modelo=args.modelo, esforco=args.esforco, pedido=pedido)
        print(json.dumps(estado, ensure_ascii=False, indent=2))
        return 0 if estado["estado"] == "resultado_recebido" else 2
    except (ErroDeInstrumentacao, sessao.ErroDeSessao, OSError, ValueError) as erro:
        print(f"PAROU: {redigir(str(erro))}\nPreserve os arquivos e confira a posse e o checkpoint antes de repetir.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
