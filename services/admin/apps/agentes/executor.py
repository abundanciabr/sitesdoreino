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
    from . import conversa, panorama
    from .models import RoboPessoal

    if execucao.robo.situacao != RoboPessoal.Situacao.ATIVO:
        terminar(execucao, S.PAUSADA, "O robô está pausado. Volta quando for reativado.")
        return
    if execucao.tipo == Execucao.Tipo.CONVERSA:
        conversa.executar(execucao)
    elif execucao.tipo == Execucao.Tipo.PANORAMA:
        panorama.executar(execucao)
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
    if autorizacao and modelo.gasto_do_mes() < autorizacao.teto_mensal_usd:
        n += retomar_os_que_esperam([S.AGUARDANDO_AUTORIZACAO], "há teto de gasto")
    return n


_acordar = threading.Event()


def acordar() -> None:
    """Entrou trabalho na fila: o laço deste processo vai buscar agora, sem
    esperar a próxima volta. Outros processos acham pela volta normal."""
    _acordar.set()


def rodar_para_sempre(parar: threading.Event) -> None:
    """O laço da thread. Cada volta usa uma conexão de banco saudável."""
    trabalhador = nome_do_trabalhador()
    ultimo_reacordar = timezone.now() - INTERVALO_DE_REACORDAR
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
    if _thread is not None:
        _thread.join(timeout=5)
