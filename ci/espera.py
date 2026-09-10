"""O LAÇO DE ESPERA DA CASA — extraído do portão de deploy, agora com voz.

POR QUE ESTE ARQUIVO EXISTE
---------------------------
Em 29/08/2026 o mantenedor descreveu o pior modo de falha do projeto, nas
palavras dele: a janela mostra o robô "trabalhando, executando, fazendo algo",
passam horas, e no fim o robô confessa que estava esperando algo que quebrou.
Espera sem fim é visualmente idêntica a trabalho — e a lição ("esperas em
segundo plano precisam de limite"; custou 2h de silêncio em 28/08) morava só na
memória privada do mantenedor, fora do repositório. Detalhes: armadilhas/161.

A espera CORRETA já existia: `esperar_workflows()` do `ci/portao_de_deploy.py`
— fail-closed em três tempos (graça vencida sem o alvo aparecer · teto vencido
sem concluir · falhas seguidas demais da medição), só que MUDA e presa dentro
do CI. Este módulo extrai o laço para um primitivo compartilhado; o portão
passa a importá-lo. Duas definições de "esperar" divergiriam no primeiro dia em
que alguém mexesse numa só (a mesma lei que `services/admin/apps/core/divida.py`
aplica à regra da dívida).

O CONTRATO, EM QUATRO FRASES
----------------------------
1. `observar()` olha o mundo de fora UMA vez e devolve uma `Olhada` (ou levanta
   `ErroDeInstrumentacao` quando não conseguiu medir).
2. `vigiar()` repete a observação até desfecho, e NUNCA espera calado: a cada
   volta chama `ao_observar` — a voz é efeito colateral da espera, não promessa
   de comportamento do agente.
3. Todo desfecho é barulhento: sucesso devolve a `Olhada` final; graça, teto e
   falhas seguidas levantam exceções TIPADAS que carregam o contexto.
4. Um contador de tempo sem estado observado é o mesmo silêncio com batimento
   bonito — por isso a `Olhada` sempre carrega o `resumo` do que foi VISTO, e a
   volta com falha carrega o erro, nunca um relógio nu.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _nucleo import ErroDeInstrumentacao  # noqa: E402

FALHAS_MAX_PADRAO = 5  # o limite herdado do portão — nunca invente um segundo


@dataclass
class Olhada:
    """Uma observação do mundo externo, com o que foi visto por escrito."""

    pronta: bool          # a condição terminou (o veredito é de quem observa)
    resumo: str           # uma frase do estado OBSERVADO — nunca vazia à toa
    apareceu: bool = True  # False = o alvo ainda nem existe (conta contra a graça)
    dados: Any = None     # payload para o chamador (runs, conclusão, etc.)


@dataclass
class Volta:
    """O que a voz recebe a cada volta do laço."""

    decorrido: float               # segundos desde o início
    olhada: Olhada | None = None   # a observação desta volta (ou None se falhou)
    erro: ErroDeInstrumentacao | None = None
    falhas_seguidas: int = 0


class EsperaFalhou(Exception):
    """Base das saídas ruidosas do laço. Carrega o contexto do momento."""

    def __init__(
        self,
        mensagem: str,
        *,
        decorrido: float,
        olhada: Olhada | None = None,
        erro: ErroDeInstrumentacao | None = None,
        falhas_seguidas: int = 0,
    ) -> None:
        super().__init__(mensagem)
        self.decorrido = decorrido
        self.olhada = olhada
        self.erro = erro
        self.falhas_seguidas = falhas_seguidas


class FalhasSeguidas(EsperaFalhou):
    """A medição falhou vezes demais em sequência — não dá para medir."""


class GracaVencida(EsperaFalhou):
    """O alvo não APARECEU dentro da graça — deletado, renomeado ou nunca disparou."""


class TetoVencido(EsperaFalhou):
    """O teto estourou sem desfecho. `erro` preenchido = estourou no meio de
    uma sequência de falhas de medição; `olhada` preenchida = estourou com o
    alvo ainda pendente."""


class LimiteGitHub(ErroDeInstrumentacao):
    def __init__(self, segundos: float, detalhe: str, *, secundario: bool):
        super().__init__(
            f"GitHub limitou as consultas; aguarde pelo menos {segundos:.0f}s antes de consultar novamente",
            detalhe,
        )
        self.segundos = segundos
        self.secundario = secundario


@dataclass
class ConsultasDaEspera:
    prazo: float
    relogio: Callable[[], float]
    cache: dict[tuple, tuple[str, str]] = field(default_factory=dict)
    intervalo: float = 0
    retomar_em: float = 0


_consultas: ContextVar[ConsultasDaEspera | None] = ContextVar("consultas_da_espera", default=None)


def vigiar(
    observar: Callable[[], Olhada],
    *,
    teto: float,
    intervalo: float,
    graca: float | None = None,
    falhas_max: int = FALHAS_MAX_PADRAO,
    relogio: Callable[[], float] = time.monotonic,
    dormir: Callable[[float], None] = time.sleep,
    ao_observar: Callable[[Volta], None] | None = None,
) -> Olhada:
    """Observa até desfecho com teto compartilhado por consultas e pausas.

    Durante uma sequência de falhas de medição só o teto e o limite de falhas
    valem (graça compara com o alvo, e sem medição não se sabe do alvo). Depois
    de uma observação boa o contador de falhas zera — falha TRANSITÓRIA não
    derruba a espera, só falha PERSISTENTE (INV-CI01: cinco "não sei" seguidos
    não são um "não").
    """
    inicio = relogio()
    consultas = ConsultasDaEspera(inicio + teto, relogio)
    contexto = _consultas.set(consultas)
    falhas_seguidas = 0
    limites_seguidos = 0
    ultima = None
    ultimo_erro = None
    try:
        while True:
            decorrido = relogio() - inicio
            if decorrido >= teto:
                if ultima is None and ultimo_erro is None:
                    ultimo_erro = ErroDeInstrumentacao("prazo insuficiente para iniciar a consulta; informe um teto positivo")
                raise TetoVencido(
                    f"teto de {teto:.0f}s vencido sem concluir a medição",
                    decorrido=decorrido, olhada=ultima, erro=ultimo_erro,
                    falhas_seguidas=falhas_seguidas,
                )
            espera = intervalo
            try:
                olhada = observar()
                falhas_seguidas = 0
                limites_seguidos = 0
                ultima, ultimo_erro = olhada, None
            except ErroDeInstrumentacao as erro:
                falhas_seguidas += 1
                ultima, ultimo_erro = None, erro
                decorrido = relogio() - inicio
                if isinstance(erro, LimiteGitHub):
                    limites_seguidos += 1
                    espera = max(intervalo, erro.segundos)
                    if erro.secundario:
                        espera = max(espera, 60 * 2 ** (limites_seguidos - 1))
                if ao_observar is not None:
                    ao_observar(Volta(decorrido, erro=erro, falhas_seguidas=falhas_seguidas))
                if falhas_seguidas >= falhas_max:
                    raise FalhasSeguidas(
                        f"a medição falhou {falhas_seguidas} vezes seguidas",
                        decorrido=decorrido, erro=erro, falhas_seguidas=falhas_seguidas,
                    ) from erro
            else:
                decorrido = relogio() - inicio
                if ao_observar is not None:
                    ao_observar(Volta(decorrido, olhada=olhada))
                if decorrido >= teto:
                    raise TetoVencido(
                        f"teto de {teto:.0f}s vencido durante a medição",
                        decorrido=decorrido, olhada=olhada,
                    )
                if olhada.pronta:
                    return olhada
                if graca is not None and not olhada.apareceu and decorrido >= graca:
                    raise GracaVencida(
                        f"o alvo não apareceu em {graca:.0f}s de graça",
                        decorrido=decorrido, olhada=olhada,
                    )
                espera = max(intervalo, consultas.intervalo, consultas.retomar_em - relogio())

            retomar = min(relogio() + espera, consultas.prazo)
            while relogio() < retomar:
                dormir(min(60, retomar - relogio()))
                if ao_observar is not None and relogio() < retomar:
                    ao_observar(Volta(relogio() - inicio, ultima, ultimo_erro, falhas_seguidas))
    finally:
        _consultas.reset(contexto)


def _segundos(valor: str | None) -> float:
    try:
        numero = float(valor)
        return numero if math.isfinite(numero) and numero >= 0 else 0
    except (ValueError, TypeError):
        return 0


def _identidade_gh() -> str:
    # Inclui mudanças de token e de conta ativa sem guardar credenciais no cache.
    nomes = ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN",
             "GH_HOST", "GH_CONFIG_DIR", "XDG_CONFIG_HOME", "APPDATA", "HOME", "USERPROFILE")
    dados = [os.environ.get(nome, "") for nome in nomes]
    configuracoes = [Path.home() / ".config" / "gh"]
    for nome in ("GH_CONFIG_DIR", "XDG_CONFIG_HOME", "APPDATA"):
        if os.environ.get(nome):
            base = Path(os.environ[nome])
            configuracoes.append(base if nome == "GH_CONFIG_DIR" else base / (
                "GitHub CLI" if nome == "APPDATA" else "gh"
            ))
    for base in configuracoes:
        arquivo = base / "hosts.yml"
        try:
            estado = arquivo.stat()
            dados.append(f"{arquivo}:{estado.st_mtime_ns}:{estado.st_size}")
        except FileNotFoundError:
            dados.append(str(arquivo))
        except OSError as erro:
            raise ErroDeInstrumentacao(
                "não consegui conferir a conta do gh; restaure o acesso à configuração antes de consultar",
                str(erro),
            ) from erro
    return hashlib.sha256(json.dumps(dados).encode()).hexdigest()


def chamar_gh(gh: list[str], caminho: str) -> Any:
    """GET condicional em cada observação; cache privado dura só esta espera.

    `gh api --include` sai 1 no 304 legítimo. O protocolo HTTP decide esse
    caso; falha de transporte e qualquer outro erro nunca reutilizam o corpo.
    Sem `--paginate`: actions/runs é um objeto, não JSON concatenável.
    """
    consultas = _consultas.get()
    timeout = min(120, consultas.prazo - consultas.relogio()) if consultas else 120
    if timeout <= 0:
        raise ErroDeInstrumentacao("teto da consulta vencido; reinicie a medição quando puder concluí-la")
    chave = (tuple(gh), caminho, str(Path.cwd()), _identidade_gh())
    anterior = consultas.cache.get(chave) if consultas else None
    comando = [*gh, "api", caminho, "--include"]
    if anterior:
        comando.extend(["--header", f"If-None-Match: {anterior[0]}"])
    try:
        proc = subprocess.run(
            comando, cwd=str(Path.cwd()), stdin=subprocess.DEVNULL,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            env={**os.environ, "PYTHONUTF8": os.environ.get("PYTHONUTF8", "1")},
            timeout=timeout, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ErroDeInstrumentacao(
            f"gh api {caminho}: não consegui consultar; confira a conexão e tente novamente",
            str(exc),
        ) from exc
    bruto = proc.stdout.replace("\r\n", "\n")
    cabecalho, separador, corpo = bruto.partition("\n\n")
    linhas = cabecalho.splitlines()
    status = re.fullmatch(r"HTTP/\d(?:\.\d)? (\d{3})(?: .*)?", linhas[0] if linhas else "")
    detalhe = f"exit code {proc.returncode}\n{proc.stderr[:2000]}\n{bruto[:2000]}"
    if not separador or not status:
        raise ErroDeInstrumentacao(
            f"gh api {caminho}: resposta HTTP inválida; confira o GitHub e repita a consulta", detalhe,
        )
    codigo = int(status[1])
    headers = {k.strip().lower(): v.strip() for linha in linhas[1:]
               if ":" in linha for k, v in [linha.split(":", 1)]}
    if codigo in (403, 429) and (
        codigo == 429 or headers.get("x-ratelimit-remaining") == "0"
        or "retry-after" in headers or "rate limit" in (corpo + proc.stderr).lower()
    ):
        segundos = _segundos(headers.get("retry-after"))
        if not segundos and headers.get("retry-after"):
            try:
                segundos = max(0, parsedate_to_datetime(headers["retry-after"]).timestamp() - time.time())
            except (ValueError, TypeError, OverflowError):
                pass
        primario = headers.get("x-ratelimit-remaining") == "0"
        if primario:
            segundos = max(segundos, _segundos(headers.get("x-ratelimit-reset")) - time.time())
        raise LimiteGitHub(max(segundos, 1) if segundos > 0 else 60, detalhe,
                           secundario=not primario and not segundos)
    if codigo == 304:
        if not anterior:
            raise ErroDeInstrumentacao(
                f"gh api {caminho}: HTTP 304 sem cache validado; reinicie a medição", detalhe,
            )
        if proc.returncode not in (0, 1):
            raise ErroDeInstrumentacao(f"gh api {caminho}: falha ao revalidar; repita a medição", detalhe)
        corpo = anterior[1]
    elif codigo != 200 or proc.returncode != 0:
        raise ErroDeInstrumentacao(
            f"gh api {caminho}: HTTP {codigo}, exit code {proc.returncode}; confira acesso e disponibilidade", detalhe,
        )
    try:
        dado = json.loads(corpo)
    except ValueError as exc:
        raise ErroDeInstrumentacao(
            f"gh api {caminho}: resposta não é JSON; repita a medição após conferir o GitHub", detalhe,
        ) from exc
    if consultas:
        consultas.intervalo = max(consultas.intervalo, _segundos(headers.get("x-poll-interval")))
        if headers.get("x-ratelimit-remaining") == "0":
            consultas.retomar_em = consultas.relogio() + max(
                _segundos(headers.get("x-ratelimit-reset")) - time.time(), 60,
            )
        if codigo == 200:
            consultas.cache.pop(chave, None)
            if headers.get("etag"):
                consultas.cache[chave] = (headers["etag"], corpo)
    return dado
