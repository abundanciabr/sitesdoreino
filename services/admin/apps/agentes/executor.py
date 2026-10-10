"""O executor dos robôs: o laço do servidor que pega as execuções da fila.

Roda numa thread do processo do site: na aplicação unificada, ao lado dos
outros trabalhadores (`services/aplicacao/workers.py`); na célula sozinha,
pelo `lifespan` do ASGI (`config/asgi.py`). Fechar o navegador não para nada:
o navegador só criou a linha.

## Posse com prazo

Pegar uma execução é gravar nela quem pegou e até quando (`ocupada_ate`),
com a linha travada (`FOR UPDATE SKIP LOCKED`): dois trabalhadores nunca
pegam a mesma. Enquanto trabalha, o executor renova o prazo a cada passo
(`batimento`). Processo que morre deixa o prazo vencer, e outro trabalhador
retoma do ponto guardado em `estado`. Toda gravação do executor confere que a
posse ainda é dele; se não for, ele larga sem gravar por cima.
"""

from __future__ import annotations

import contextvars
import logging
import os
import socket
import threading
from datetime import timedelta

from django.db import close_old_connections, transaction
from django.db.models import Q
from django.utils import timezone

from . import modelo
from .models import Conexao, Execucao, Mensagem
from .trabalhos import registrar, retomar_os_que_esperam

log = logging.getLogger(__name__)

POSSE = timedelta(minutes=5)
MAX_TENTATIVAS = 4
INTERVALO_SEM_TRABALHO = 2.0
INTERVALO_DE_REACORDAR = timedelta(minutes=5)
# Lead que mandou áudio espera resposta: a fila de áudio é olhada mais vezes.
INTERVALO_DO_AUDIO = timedelta(seconds=20)
INTERVALO_DO_MAPA = timedelta(minutes=30)

S = Execucao.Situacao


class PerdeuAPosse(Exception):
    """Outro trabalhador pegou a execução (a posse venceu)."""


class Cancelada(Exception):
    """A pessoa pediu para interromper."""


def nome_do_trabalhador() -> str:
    return f"{socket.gethostname()}:{os.getpid()}:{threading.get_ident()}"[:120]


def pegar_uma(trabalhador: str) -> Execucao | None:
    agora = timezone.now()
    with transaction.atomic():
        execucao = (
            Execucao.objects.select_for_update(skip_locked=True)
            .filter(
                (Q(situacao=S.NA_FILA) & (Q(nao_antes_de__isnull=True) | Q(nao_antes_de__lte=agora)))
                | Q(situacao=S.EXECUTANDO, ocupada_ate__lt=agora)
            )
            .order_by("criada_em", "id")
            .first()
        )
        if execucao is None:
            return None
        retomada = execucao.situacao == S.EXECUTANDO
        execucao.situacao = S.EXECUTANDO
        execucao.trabalhador = trabalhador
        execucao.ocupada_ate = agora + POSSE
        execucao.batimento_em = agora
        execucao.tentativas += 1
        execucao.nao_antes_de = None
        execucao.motivo = ""
        if execucao.iniciada_em is None:
            execucao.iniciada_em = agora
        execucao.save()
        registrar(
            execucao,
            "Retomada no servidor: o trabalhador anterior parou no meio."
            if retomada
            else "Começou no servidor.",
        )
        return execucao


def _minha(execucao: Execucao):
    return Execucao.objects.filter(
        pk=execucao.pk, trabalhador=execucao.trabalhador, situacao=S.EXECUTANDO
    )


def batimento(execucao: Execucao, etapa: str | None = None, progresso: int | None = None) -> None:
    """Renova a posse, anota a etapa e confere se pediram para interromper."""
    agora = timezone.now()
    campos = {"ocupada_ate": agora + POSSE, "batimento_em": agora, "atualizada_em": agora}
    if etapa is not None:
        campos["etapa_atual"] = etapa[:200]
        execucao.etapa_atual = etapa[:200]
    if progresso is not None:
        campos["progresso"] = max(0, min(100, progresso))
        execucao.progresso = campos["progresso"]
    if not _minha(execucao).update(**campos):
        raise PerdeuAPosse()
    if Execucao.objects.filter(pk=execucao.pk, cancelar_pedido_em__isnull=False).exists():
        raise Cancelada()
    if etapa:
        registrar(execucao, etapa)


def guardar_estado(execucao: Execucao) -> None:
    """O ponto de retomada. Gravado só se a posse ainda é deste trabalhador."""
    if not _minha(execucao).update(estado=execucao.estado, atualizada_em=timezone.now()):
        raise PerdeuAPosse()


FINAIS = (S.CONCLUIDA, S.FALHOU, S.CANCELADA)


def terminar(execucao: Execucao, situacao: str, motivo: str = "", resultado: str = "") -> None:
    agora = timezone.now()
    campos = {
        "situacao": situacao,
        "motivo": motivo[:4000],
        "trabalhador": "",
        "ocupada_ate": None,
        "atualizada_em": agora,
        "estado": execucao.estado,
    }
    if resultado:
        campos["resultado"] = resultado[:4000]
    if situacao in FINAIS:
        campos["terminada_em"] = agora
        if situacao == S.CONCLUIDA:
            campos["progresso"] = 100
    if situacao == S.NA_FILA:
        campos["nao_antes_de"] = agora + timedelta(seconds=30 * max(execucao.tentativas, 1))
    if situacao in Execucao.ESPERANDO:
        # Esperando, a etapa em que parou não está acontecendo: o motivo diz o porquê.
        campos["etapa_atual"] = ""
    if not _minha(execucao).update(**campos):
        raise PerdeuAPosse()
    for chave, valor in campos.items():
        setattr(execucao, chave, valor)
    registrar(execucao, motivo or dict(S.choices).get(situacao, situacao), situacao)


def _avisar_na_conversa(execucao: Execucao, texto: str) -> None:
    if execucao.conversa_id:
        Mensagem.objects.create(
            conversa_id=execucao.conversa_id,
            papel=Mensagem.Papel.AVISO,
            texto=texto,
            execucao=execucao,
        )


def _executar(execucao: Execucao) -> None:
    from . import conhecimento, conversa, panorama, quiz, super_equipe
    from .models import RoboPessoal

    if execucao.tipo not in (Execucao.Tipo.SUPER_EQUIPE, Execucao.Tipo.SATISFACAO) and execucao.robo.situacao != RoboPessoal.Situacao.ATIVO:
        terminar(execucao, S.PAUSADA, "O robô está pausado. Volta quando for reativado.")
        return
    if execucao.tipo == Execucao.Tipo.CONVERSA:
        conversa.executar(execucao)
    elif execucao.tipo == Execucao.Tipo.PANORAMA:
        panorama.executar(execucao)
    elif execucao.tipo == Execucao.Tipo.CONFERENCIA_QUIZ:
        quiz.executar_conferencia(execucao)
    elif execucao.tipo == Execucao.Tipo.LEITURA_QUIZ:
        quiz.executar_leitura(execucao)
    elif execucao.tipo == Execucao.Tipo.CONHECIMENTO:
        conhecimento.executar(execucao)
    elif execucao.tipo == Execucao.Tipo.SATISFACAO:
        from . import satisfacao
        satisfacao.executar(execucao)
    elif execucao.tipo == Execucao.Tipo.SUPER_EQUIPE:
        super_equipe.executar(execucao)
    else:  # pragma: no cover - tipo novo sem executor
        terminar(execucao, S.FALHOU, "Este tipo de trabalho ainda não tem executor.")


def rodar_uma(trabalhador: str | None = None) -> Execucao | None:
    """Pega UMA execução e trabalha nela até ela terminar ou esperar."""
    execucao = pegar_uma(trabalhador or nome_do_trabalhador())
    if execucao is None:
        return None
    try:
        if execucao.tentativas > MAX_TENTATIVAS:
            terminar(
                execucao,
                S.FALHOU,
                f"Parou no meio {execucao.tentativas - 1} vezes; o robô desistiu "
                "para não repetir sem fim. Dá para retomar pela página do robô.",
            )
            _avisar_na_conversa(execucao, "Não consegui terminar este pedido.")
            return execucao
        _executar(execucao)
    except Cancelada:
        terminar(execucao, S.CANCELADA, "Interrompida a pedido da pessoa.")
    except PerdeuAPosse:
        log.warning("Execução %s: a posse passou para outro trabalhador", execucao.pk)
    except modelo.Temporario as problema:
        terminar(execucao, S.NA_FILA, problema.frase)
    except modelo.ProblemaDoModelo as problema:
        terminar(execucao, problema.situacao, problema.frase)
        if problema.situacao in Execucao.ESPERANDO:
            _avisar_na_conversa(
                execucao,
                "Sua mensagem ficou guardada. " + problema.frase,
            )
        else:
            _avisar_na_conversa(execucao, "Não consegui responder: " + problema.frase)
    except Exception as erro:  # noqa: BLE001 - a execução registra e segue
        log.exception("Execução %s falhou", execucao.pk)
        try:
            terminar(
                execucao,
                S.FALHOU,
                f"Erro interno ({type(erro).__name__}). Dá para retomar pela página do robô.",
            )
            _avisar_na_conversa(execucao, "Não consegui responder: deu um erro interno.")
        except PerdeuAPosse:
            pass
    return execucao


def reacordar() -> int:
    """Devolve à fila o que esperava a chave ou o teto, quando voltaram."""
    n = 0
    conexao = modelo.conexao()
    if modelo.tem_chave() and conexao.situacao == Conexao.Situacao.CONFERIDA:
        n += retomar_os_que_esperam([S.AGUARDANDO_DEPENDENCIA], "a conexão voltou")
    autorizacao = modelo.autorizacao_ativa()
    if autorizacao and modelo.gasto_do_mes(autorizacao.pk) < autorizacao.teto_mensal_usd:
        n += retomar_os_que_esperam([S.AGUARDANDO_AUTORIZACAO], "há teto de gasto")
    _manter_o_mapa_em_dia()
    return n


def _avisar_a_equipe() -> None:
    """Pergunta às células o que pede alguém da equipe e avisa uma vez.

    Só no laço de fundo, nunca na tela: a varredura faz dezenas de chamadas a
    outras células, e `reacordar()` também roda dentro do clique de
    /admin/robos/."""
    from apps.core import avisos_equipe

    try:
        avisos_equipe.varrer()
    except Exception:  # noqa: BLE001 - os avisos não podem derrubar o laço
        log.exception("Avisos da equipe: varredura falhou")


def _transcrever_audios() -> None:
    """Notas de voz que os leads mandaram no WhatsApp viram texto para o
    atendente (`apps.voz`), com a mesma chave e o mesmo teto."""
    try:
        from apps.voz.servico import processar_audios_pendentes

        processar_audios_pendentes()
    except Exception:  # noqa: BLE001 - o áudio não pode derrubar o laço
        log.exception("Áudio: transcrição dos pendentes falhou")


def _manter_o_mapa_em_dia() -> None:
    """Depois da primeira leitura pedida na tela, documento novo ou mudado
    entra no mapa sozinho, pelo mesmo robô que pediu da última vez."""
    from . import conhecimento

    try:
        ultima = Execucao.objects.filter(tipo=Execucao.Tipo.CONHECIMENTO).first()
        if ultima is None or ultima.situacao in Execucao.ABERTAS:
            return
        if timezone.now() - ultima.criada_em < INTERVALO_DO_MAPA:
            return
        if conhecimento.documentos_a_ler() or conhecimento.esquecer_os_que_sairam():
            conhecimento.pedir_leitura(ultima.robo, "Leitura automática dos documentos mudados")
    except Exception:  # noqa: BLE001 - o mapa não pode derrubar o laço
        log.exception("Mapa de conhecimento: conferência automática falhou")


def _comercial(funcao: str, *args):
    try:
        from apps.comercial import coordenador
    except ImportError:  # pragma: no cover - célula sem a equipe comercial
        return None
    try:
        return getattr(coordenador, funcao)(*args)
    except Exception:  # noqa: BLE001 - a equipe comercial não derruba o laço
        log.exception("Equipe comercial: %s falhou", funcao)
        return None


_acordar = threading.Event()
_acordar_comercial = threading.Event()


def acordar() -> None:
    """Entrou trabalho na fila: o laço deste processo vai buscar agora, sem
    esperar a próxima volta. Outros processos acham pela volta normal."""
    _acordar.set()
    _acordar_comercial.set()


MAX_TRABALHADORES_COMERCIAIS = 4
PADRAO_TRABALHADORES_COMERCIAIS = 2


def trabalhadores_comerciais() -> int:
    """`COMERCIAL_TRABALHADORES`: quantas threads da equipe comercial por processo
    (padrão 2, teto 4). Valor estranho volta ao padrão."""
    bruto = os.environ.get("COMERCIAL_TRABALHADORES", "").strip()
    try:
        n = int(bruto) if bruto else PADRAO_TRABALHADORES_COMERCIAIS
    except ValueError:
        n = PADRAO_TRABALHADORES_COMERCIAIS
    return max(1, min(MAX_TRABALHADORES_COMERCIAIS, n))


def rodar_comercial_para_sempre(parar: threading.Event, indice: int = 1) -> None:
    """O laço de UM trabalhador da equipe comercial. Só pega trabalho comercial:
    a manutenção, os avisos, o áudio e os robôs pessoais ficam no laço principal."""
    trabalhador = f"{nome_do_trabalhador()}:comercial-{indice}"[:120]
    log.info("Trabalhador comercial ligado: %s", trabalhador)
    while not parar.is_set():
        _acordar_comercial.clear()
        close_old_connections()
        trabalhou = False
        try:
            trabalhou = _comercial("rodar_um", trabalhador) is not None
        except Exception:  # noqa: BLE001 - o laço não pode morrer
            log.exception("Trabalhador comercial: volta falhou")
        if not trabalhou:
            _acordar_comercial.wait(INTERVALO_SEM_TRABALHO)
    close_old_connections()


def _ligar_trabalhadores_comerciais(parar: threading.Event) -> list[threading.Thread]:
    threads = []
    for indice in range(1, trabalhadores_comerciais() + 1):
        # Uma thread nova não herda o contexto do serviço (na aplicação unificada ele
        # diz em qual banco o admin lê e grava): cada trabalhador leva a sua cópia.
        contexto = contextvars.copy_context()
        thread = threading.Thread(
            target=contexto.run,
            args=(rodar_comercial_para_sempre, parar, indice),
            name=f"comercial-admin-{indice}",
            daemon=True,
        )
        thread.start()
        threads.append(thread)
    return threads


def rodar_para_sempre(parar: threading.Event) -> None:
    """O laço da thread. Cada volta usa uma conexão de banco saudável.

    Este laço cuida dos robôs pessoais e da manutenção; a equipe comercial
    roda em threads próprias (`COMERCIAL_TRABALHADORES`), ligadas aqui."""
    trabalhador = nome_do_trabalhador()
    _ligar_trabalhadores_comerciais(parar)
    from apps.atendimento.service import ligar as ligar_suporte
    ligar_suporte(parar)
    from .super_equipe_automatica import ligar as ligar_super_equipe
    ligar_super_equipe(parar)
    ultimo_reacordar = timezone.now() - INTERVALO_DE_REACORDAR
    ultimo_audio = timezone.now() - INTERVALO_DO_AUDIO
    log.info("Executor dos robôs ligado: %s", trabalhador)
    while not parar.is_set():
        # Limpa antes de buscar: um aviso que chegar durante a busca faz a
        # espera abaixo voltar na hora.
        _acordar.clear()
        close_old_connections()
        trabalhou = False
        try:
            if timezone.now() - ultimo_reacordar >= INTERVALO_DE_REACORDAR:
                ultimo_reacordar = timezone.now()
                reacordar()
                # Só no laço, nunca na tela: a varredura dos avisos fala com
                # outras células, e não derruba a volta se uma delas demorar.
                _avisar_a_equipe()
                # Só no laço, nunca na tela: o catálogo mudou, o índice comercial muda junto.
                from .conhecimento_comercial import manter_em_dia

                manter_em_dia()
                _comercial("manutencao")
            if timezone.now() - ultimo_audio >= INTERVALO_DO_AUDIO:
                ultimo_audio = timezone.now()
                _transcrever_audios()
            trabalhou = rodar_uma(trabalhador) is not None
        except Exception:  # noqa: BLE001 - o laço não pode morrer
            log.exception("Executor dos robôs: volta falhou")
        if not trabalhou:
            _acordar.wait(INTERVALO_SEM_TRABALHO)
    close_old_connections()


_parar = threading.Event()
_thread: threading.Thread | None = None


def ligar_em_segundo_plano() -> bool:
    """Liga a thread do executor uma vez por processo (célula sozinha).

    `ROBOS_EXECUTOR=desligado` no ambiente deixa o processo sem executor."""
    global _thread
    if os.environ.get("ROBOS_EXECUTOR", "").strip().lower() == "desligado":
        return False
    if _thread is not None and _thread.is_alive():
        return False
    _parar.clear()
    _thread = threading.Thread(
        target=rodar_para_sempre, args=(_parar,), name="robos-admin", daemon=True
    )
    _thread.start()
    return True


def desligar() -> None:
    _parar.set()
    _acordar.set()
    _acordar_comercial.set()
    if _thread is not None:
        _thread.join(timeout=5)
