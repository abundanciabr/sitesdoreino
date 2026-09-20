# apps/core/telemetria.py
"""Os fatos que saem desta célula para o Redis Streams, e a lei deles.

POR QUE NÃO HÁ OUTBOX AQUI, e a ausência é decisão, não esquecimento
--------------------------------------------------------------------
Toda outra célula da casa publica assim: grava o fato numa tabela `outbox` na
MESMA transação do fato, e um relay empurra a linha ao Redis depois do commit.
A outbox existe para uma coisa só: impedir que o evento e o fato divirjam
quando um dos dois falha. O `funil` não tem transação nenhuma para proteger,
porque não tem banco (`config/settings.py`: `DATABASES = {}`, e a constituição
da célula diz "sem banco próprio"). O fato aqui é uma página que foi servida,
não uma linha que foi escrita.

Sem fato durável do outro lado, uma outbox seria um banco inteiro criado para
guardar a cópia de um evento que ninguém pode reconciliar depois. Então o
trilho é o MESMO (o stream `eventos.<nome>`, o mesmo envelope, o mesmo
`event_id` que deduplica do lado de quem consome) e a garantia é a que cabe a
uma célula sem estado: **no máximo uma vez**. Visita perdida por Redis fora do
ar é medição perdida, e a lei da casa diz que medição pode falhar; a página,
não.

O ENVELOPE É O DO RELAY DAS OUTRAS, copiado e não importado
-----------------------------------------------------------
Código de outra célula não atravessa a fronteira (CONSTITUICAO.md). O que
atravessa é a FORMA: `{event, version, event_id, occurred_at, data}` dentro de
um campo `json`, no stream `eventos.<nome-do-evento>` **sem versão no nome** —
a versão viaja no envelope, e pôr `v1` no nome do stream faria de toda evolução
de contrato uma migração de infraestrutura.

`REDIS_STREAMS_URL` É LIDA NO PONTO DE USO
-------------------------------------------
Nunca no import (`armadilhas/INDICE.md` → §5.3): o processo web importa este
módulo pela view e não pode morrer no boot por causa de uma variável que só a
telemetria usa. Faltando a variável, ninguém tenta a rede e a página abre igual
— que é exatamente o estado da VPS hoje, onde o serviço `funil` depende do
`redis` no compose mas ainda não recebeu o endereço dele.

O RELÓGIO DA PÁGINA NÃO ESPERA O FIO
-------------------------------------
Os tempos-limite abaixo são o teto do atraso que a telemetria pode custar a
quem está olhando a tela, e `publicar` engole toda exceção por desenho. Um
Redis pendurado atrasa a página em frações de segundo e nada mais; um Redis
ausente não a atrasa em nada.
"""

import json
import logging
import os
import uuid

import redis
from django.utils import timezone

logger = logging.getLogger("funil.telemetria")

#: Teto do que a telemetria pode custar à página, em segundos, para conectar e
#: para escrever. Curto de propósito: o Redis mora na mesma rede do container,
#: então o caminho saudável leva milissegundos, e o que este número corta é o
#: caminho doente.
TEMPO_LIMITE = 0.3

#: Um cliente por endereço, pelo mesmo motivo do `http()` de `clients.py`
#: (`armadilhas/082`): construir um cliente por requisição paga a montagem da
#: conexão em toda página servida.
_clientes: dict[str, "redis.Redis"] = {}


def _conectar(url: str) -> "redis.Redis":
    """O cliente deste endereço. Ponto de costura dos testes, que o trocam."""
    cliente = _clientes.get(url)
    if cliente is None:
        cliente = redis.from_url(
            url,
            socket_connect_timeout=TEMPO_LIMITE,
            socket_timeout=TEMPO_LIMITE,
        )
        _clientes[url] = cliente
    return cliente


def publicar(nome: str, versao: int, dados: dict) -> bool:
    """Empurra um fato ao stream `eventos.<nome>`. Devolve se ele saiu.

    Devolver `False` nunca é motivo para quem chama fazer alguma coisa: o
    retorno existe para o teste, e para o log dizer o que não saiu.

    `data.site_id` vazio é recusado AQUI, e não na recepção: a
    `services/metricas/apps/fatos/recepcao.py` manda para a fila de mortos, em
    silêncio, todo envelope sem ele. Uma medição que some sem avisar é pior do
    que uma que nunca foi tentada, então o erro nasce do lado de quem emite,
    com nome e linha.
    """
    if not dados.get("site_id"):
        logger.error(
            "%s: `data.site_id` ausente — a recepção da metricas o mataria em "
            "silêncio. O evento NÃO foi publicado.",
            nome,
        )
        return False

    url = os.environ.get("REDIS_STREAMS_URL")
    if not url:
        logger.error(
            "%s: REDIS_STREAMS_URL ausente no env desta célula — a página abre "
            "normalmente e o fato não é medido. Ponha o endereço do Redis no "
            "serviço `funil` do compose para a medição começar.",
            nome,
        )
        return False

    envelope = {
        "event": nome,
        "version": versao,
        "event_id": str(uuid.uuid4()),
        "occurred_at": timezone.now().isoformat(),
        "data": dados,
    }
    try:
        _conectar(url).xadd(
            f"eventos.{nome}",
            {"json": json.dumps(envelope, ensure_ascii=False)},
        )
    except Exception:  # noqa: BLE001 - defensivo por desenho, ver a docstring
        logger.exception("%s: não deu para publicar; a visita não foi medida", nome)
        return False
    return True


def dispositivo_do_agente(user_agent: str) -> str:
    """`celular`, `tablet`, `computador` — ou `""` quando não dá para decidir.

    O vocabulário é FECHADO aqui porque quem publica é quem o valida (o
    contrato do evento deixa o campo aberto de propósito, para que um formato
    novo não custe um Rito de Contrato).

    A ordem das perguntas é a regra: **tablet antes de celular**, porque o iPad
    também se anuncia como `Safari` móvel e o Android de tela grande manda
    `Android` sem `Mobile`. Perguntar por celular primeiro chamaria todo tablet
    de celular.
    """
    agente = (user_agent or "").lower()
    if not agente:
        return ""
    if "ipad" in agente or "tablet" in agente:
        return "tablet"
    if "android" in agente and "mobile" not in agente:
        return "tablet"
    if any(marca in agente for marca in ("mobi", "iphone", "ipod")):
        return "celular"
    return "computador"


def utm_sem_prefixo(parametros) -> dict:
    """`utm_source=x` na URL vira `{"source": "x"}` no evento.

    O prefixo sai porque o contrato do evento assim o declara, e ele fica na
    query string do checkout porque é lá que a Meta CAPI o lê. São dois
    formatos do mesmo dado, e cada um tem o seu lugar.
    """
    return {
        chave.removeprefix("utm_"): valor
        for chave, valor in parametros.items()
        if chave.startswith("utm_") and valor
    }
