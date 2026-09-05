"""O checkpoint: quem entrega, quando, o que a fila devolve, e o estouro do prazo.

Lei: `docs/decisoes/PLANO-CELULA-CURSOS.md` §3.12 (o checkpoint é por link),
§4 (`Envio`; "a fila de revisão não é tabela"), §5 (os dois eventos) e §9
([INV-CUR-L3]). Degrau 2.1 (TAR-155). Este arquivo é o único lugar onde um
`Envio` nasce e onde um estouro se registra, como `progresso.py` é o único
lugar onde uma porta muda de estado.

AS TRÊS FUNÇÕES, E O QUE CADA UMA NÃO FAZ
-----------------------------------------
- `entregar` exige a porta em `em_producao` (o primeiro envio) ou `devolvida`
  (o reenvio, `numero` = último + 1), exige TODAS as pausas registradas
  ([INV-CUR-P3], perguntado a `progresso.pausas_registradas` e nunca
  reescrito), valida os links, o README e a autoavaliação, e grava o `Envio`,
  a porta em `enviada` e o `envio.recebido.v1` na MESMA transação. Não tem
  parâmetro de prazo, de hora nem de estado: o prazo é o modelo quem calcula,
  e a hora é a do relógio.
- `fila_de_revisao` é uma CONSULTA: os envios em `recebido` ou `em_revisao`
  por `prazo_em`, os vencidos primeiro. Não há tabela de fila, e o plantão
  (degrau 2.2) lê daqui.
- `registrar_estouros(agora)` grava `estourado_em` em todo envio da fila cujo
  prazo passou e emite `revisao.prazo-estourado.v1` UMA vez por envio: o
  filtro `estourado_em IS NULL` é o que faz a segunda passada não emitir de
  novo. Registra; nunca alonga ([INV-CUR-L3]). Quem a chama de minuto em
  minuto é o tique de `tasks.py`.

O LAUDO NÃO MORA AQUI
---------------------
Nenhuma função deste arquivo grava `aberto`, `aberto_com_ajuste` ou
`devolvido`: isso é o laudo, degrau 2.2. Aqui o envio nasce e espera.

Molde de forma: `apps/cursos/progresso.py` (as regras fora da view, a recusa
como exceção com frase para gente) e `services/encomendas/apps/encomendas/tique.py`
(a varredura por `agora`, a trava por linha, a idempotência pelo filtro).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urlsplit

from django.db import transaction
from django.db.models import Max

from . import eventos
from . import progresso as portas
from .models import Aula, Envio, Instrumento, Progresso

# Os dois estados de porta em que a pessoa PODE entregar: em produção (o
# primeiro envio) e devolvida (o reenvio, depois de um laudo devolvido).
ESTADOS_QUE_ENTREGAM = frozenset(
    {Progresso.Estado.EM_PRODUCAO, Progresso.Estado.DEVOLVIDA}
)

# Os dois estados de envio que estão NA FILA de revisão (lei §4).
ESTADOS_NA_FILA = (Envio.Estado.RECEBIDO, Envio.Estado.EM_REVISAO)

# O rótulo do link obrigatório. A tela o escreve por ela, e o serviço o exige:
# é ele que a professora abre para revisar.
ROTULO_DO_ARQUIVO = "Arquivo"

# O teto de uma URL, o mesmo do `video_url` da aula.
TAMANHO_MAXIMO_DA_URL = 500

# As frases que a tela mostra quando a porta não entrega, por estado. Escritas
# para o aluno: o que aconteceu e o que fazer.
POR_QUE_NAO_ENTREGA = {
    Progresso.Estado.TRANCADA: (
        "Essa porta ainda está trancada: conclua a aula anterior antes."
    ),
    Progresso.Estado.DISPONIVEL: ("Abra a aula e assista ao vídeo antes de entregar."),
    Progresso.Estado.ENVIADA: (
        "Seu envio já está na fila de revisão. Espere o laudo antes de entregar "
        "de novo."
    ),
    Progresso.Estado.CONCLUIDA: (
        "Esta aula já está concluída: não há mais nada a entregar aqui."
    ),
}

A_FRASE_DAS_PAUSAS = (
    "O checkpoint fica fechado até todas as pausas desta aula terem registro."
)


class EnvioRecusado(Exception):
    """A entrega não acontece. A mensagem é escrita para quem lê a tela."""


@dataclass(frozen=True)
class Criterio:
    """Um critério da escala do instrumento, com os dois limites da nota."""

    nome: str
    minimo: int
    maximo: int


def criterios_de(instrumento: Instrumento | None) -> list[Criterio]:
    """A escala do instrumento como a sala a lê: `{criterio: {minimo, maximo}}`.

    A escala é JSON livre, editado como texto no Admin (degrau 1.5): "os
    critérios, com o mínimo e o máximo de cada um, um objeto entre chaves".
    Esta função é o ÚNICO lugar que a interpreta para o aluno, e ela é
    tolerante por desenho: critério sem `minimo` e `maximo` inteiros, ou com
    mínimo que não é menor que o máximo, não conta. Sem instrumento, ou sem
    critério legível, a lista é vazia e a autoavaliação é texto livre. Um
    `bool` é `int` em Python, e por isso é recusado à parte.

    **A lista sai em ordem alfabética do nome, nunca "a ordem em que o JSON foi
    escrito".** `escala` é `JSONField` sobre `jsonb`: o Postgres reordena as
    chaves de um objeto ao gravar, e o mesmo dicionário volta do banco numa
    ordem diferente da que o Admin digitou (medido: `{"Proporção",
    "Acabamento"}` volta `{"Acabamento", "Proporção"}`). A tela (GET) e o
    serviço (POST) leem o instrumento em requisições separadas, cada uma com a
    própria consulta; se a ordem dependesse do jsonb, ambas ainda casariam
    entre si (a mesma linha reordena sempre igual), mas nem a tela nem quem lê
    o código teriam como prever qual índice é qual critério. Alfabético é
    determinístico e olhável no código, sem depender de um detalhe interno do
    Postgres.
    """
    if instrumento is None or not isinstance(instrumento.escala, dict):
        return []
    criterios = []
    for nome, limites in instrumento.escala.items():
        if not isinstance(limites, dict):
            continue
        minimo, maximo = limites.get("minimo"), limites.get("maximo")
        if isinstance(minimo, bool) or isinstance(maximo, bool):
            continue
        if isinstance(minimo, int) and isinstance(maximo, int) and minimo < maximo:
            criterios.append(Criterio(str(nome), minimo, maximo))
    criterios.sort(key=lambda criterio: criterio.nome)
    return criterios


def _url_valida(url: str) -> bool:
    partes = urlsplit(url)
    return (
        partes.scheme in ("http", "https")
        and bool(partes.netloc)
        and len(url) <= TAMANHO_MAXIMO_DA_URL
    )


def _validar_links(links) -> list[dict]:
    """`[{rotulo, url}]` limpo: rótulo e URL http(s) em cada um, e o do arquivo
    presente. Linha sem URL é pulada: o formulário manda as prévias com o
    rótulo sugerido e o link vazio, e prévia é opcional."""
    limpos = []
    for item in links or []:
        rotulo = str(item.get("rotulo") or "").strip()
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        if not rotulo:
            raise EnvioRecusado(
                "Cada link precisa de um rótulo que diga o que ele é: sólido, "
                "wireframe, silhueta, ou o que a encomenda pedir."
            )
        if not _url_valida(url):
            raise EnvioRecusado(
                f"O link de {rotulo} precisa ser um endereço completo, começando "
                "com http:// ou https://."
            )
        limpos.append({"rotulo": rotulo, "url": url})
    if not any(link["rotulo"] == ROTULO_DO_ARQUIVO for link in limpos):
        raise EnvioRecusado(
            "Falta o link do arquivo: é ele que a professora abre para revisar."
        )
    return limpos


def _validar_laudo(aula: Aula, laudo) -> dict:
    """A autoavaliação: uma nota dentro da escala e uma frase por critério, ou o
    texto livre quando a aula não tem instrumento com escala."""
    laudo = laudo if isinstance(laudo, dict) else {}
    criterios = criterios_de(aula.instrumento)
    if not criterios:
        texto = str(laudo.get("texto") or "").strip()
        if not texto:
            raise EnvioRecusado("Escreva sua autoavaliação antes de entregar.")
        return {"texto": texto}
    dadas = laudo.get("notas") if isinstance(laudo.get("notas"), dict) else {}
    notas = {}
    for criterio in criterios:
        item = dadas.get(criterio.nome)
        item = item if isinstance(item, dict) else {}
        nota, frase = item.get("nota"), str(item.get("frase") or "").strip()
        if (
            isinstance(nota, bool)
            or not isinstance(nota, int)
            or not (criterio.minimo <= nota <= criterio.maximo)
        ):
            raise EnvioRecusado(
                f"Dê uma nota de {criterio.minimo} a {criterio.maximo} em "
                f"{criterio.nome}."
            )
        if not frase:
            raise EnvioRecusado(
                f"Escreva uma frase para a nota de {criterio.nome}: nota sem "
                "frase não diz nada."
            )
        notas[criterio.nome] = {"nota": nota, "frase": frase}
    # A versão do instrumento em que a avaliação COMEÇOU (P04): o laudo da
    # professora vai comparar com a mesma régua.
    return {
        "instrumento": aula.instrumento.slug,
        "versao": aula.instrumento.versao,
        "notas": notas,
    }


def entregar(progresso: Progresso, *, links, readme: str, laudo_do_aluno) -> Envio:
    """O aluno entrega o checkpoint: nasce o `Envio`, a porta vira `enviada`,
    e o `envio.recebido.v1` entra na outbox, tudo numa transação.

    A trava é na porta (`select_for_update`): dois cliques no mesmo segundo
    serializam aqui, e o segundo encontra a porta já `enviada` e é recusado
    com a frase certa, em vez de nascer um envio duplicado. O `numero` é o
    último desta pessoa nesta aula mais um: 1 no primeiro envio, 2 no reenvio.
    """
    readme = (readme or "").strip()
    if not readme:
        raise EnvioRecusado(
            "Escreva o README do pacote antes de entregar: é o que a professora "
            "lê primeiro."
        )
    links_limpos = _validar_links(links)
    laudo = _validar_laudo(progresso.aula, laudo_do_aluno)

    with transaction.atomic():
        porta = Progresso.objects.select_for_update().get(pk=progresso.pk)
        if porta.estado not in ESTADOS_QUE_ENTREGAM:
            raise EnvioRecusado(POR_QUE_NAO_ENTREGA[Progresso.Estado(porta.estado)])
        if not portas.pausas_registradas(porta):
            raise EnvioRecusado(A_FRASE_DAS_PAUSAS)
        ultimo = Envio.objects.filter(pessoa=porta.pessoa, aula=porta.aula).aggregate(
            ultimo=Max("numero")
        )["ultimo"]
        envio = Envio.objects.create(
            pessoa=porta.pessoa,
            aula=porta.aula,
            numero=(ultimo or 0) + 1,
            links=links_limpos,
            readme=readme,
            laudo_do_aluno=laudo,
        )
        porta.estado = Progresso.Estado.ENVIADA
        porta.save(update_fields=["estado"])
        eventos.emitir_envio_recebido(envio)
    progresso.estado = porta.estado
    return envio


def ultimo_envio(progresso: Progresso) -> Envio | None:
    """O envio mais recente desta pessoa nesta aula, ou `None` antes do primeiro."""
    return (
        Envio.objects.filter(pessoa=progresso.pessoa, aula=progresso.aula)
        .order_by("-numero")
        .first()
    )


def fila_de_revisao(site_id: str):
    """A fila de revisão de um site: os envios que esperam laudo, por prazo,
    os vencidos primeiro. Uma consulta, não uma tabela (lei §4)."""
    return (
        Envio.objects.filter(aula__curso__site_id=site_id, estado__in=ESTADOS_NA_FILA)
        .select_related("aula", "pessoa")
        .order_by("prazo_em", "id")
    )


def registrar_estouros(agora: datetime) -> tuple[int, ...]:
    """Registra `estourado_em = agora` em todo envio da fila cujo prazo passou,
    e emite `revisao.prazo-estourado.v1` uma vez por envio.

    Idempotente pelo FILTRO: envio com `estourado_em` preenchido não volta na
    lista, então a passada seguinte não registra nem emite de novo. A trava por
    linha (`select_for_update`) serializa duas passadas no mesmo minuto (deploy
    com dois workers de pé); o `continue` de dentro é para a corrida entre
    elas, que nenhum teste sequencial encena.

    `horas_de_atraso` são as horas COMPLETAS além das 24, no mínimo 1: é o que
    o contrato pede, e um estouro de dez minutos conta como uma hora.
    """
    vencidos = list(
        Envio.objects.filter(
            estado__in=ESTADOS_NA_FILA, prazo_em__lt=agora, estourado_em__isnull=True
        )
        .order_by("prazo_em", "id")
        .values_list("pk", flat=True)
    )
    registrados: list[int] = []
    for envio_id in vencidos:
        with transaction.atomic():
            envio = (
                Envio.objects.select_for_update()
                .select_related("aula__curso")
                .get(pk=envio_id)
            )
            if envio.estourado_em is not None or envio.estado not in ESTADOS_NA_FILA:
                continue
            envio.estourado_em = agora
            envio.save(update_fields=["estourado_em"])
            horas = max(1, (agora - envio.prazo_em) // timedelta(hours=1))
            eventos.emitir_prazo_estourado(envio, horas_de_atraso=horas)
            registrados.append(envio_id)
    return tuple(registrados)
