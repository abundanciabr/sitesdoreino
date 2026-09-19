"""A porta de máquina da Fila do Primeiro Dólar: a Parte A do anexo do contrato.

Fonte: `docs/decisoes/CONTRATO-encomendas-v1-rascunho.md`, Parte A. O contrato
congelado nasce do EXPORT deste arquivo, no degrau 2.8, e não o contrário
(`armadilhas/243`).

O QUE ATRAVESSA AS SEIS OPERAÇÕES
---------------------------------
1. **O Bearer prova QUEM CHAMA, nunca quem é a pessoa.** Cookie não chega aqui.
   Por isso nenhuma operação desta superfície aceita, passa, entrega ou aprova
   nada em nome de um aluno ou de um cliente: esses gestos são das TELAS, onde a
   pessoa está atrás do login e `apps/core/sessao.py` a reconhece.
2. **Dois graus de crachá, e o segundo não é enfeite** (`armadilhas/318`). Ler a
   fila de alguém e MUDAR a régua da fila inteira não podem ser o mesmo poder.
   `setParameter`, `confirmPayment` e `reportAudit` exigem
   `TOKENS_ESCRITA_<PAR>`; o resto se contenta com `TOKENS_ACEITOS_<PAR>`. A
   recusa é 403, e a razão está em `apps/core/auth.py`.
3. **Nada de dado de contato do aluno sai daqui** ([INV-ENC-S3]): id opaco,
   número, data e slug. E peça só sai com a autorização do cliente registrada
   ([INV-ENC-S4]).
4. **`/interno` NAO é fechado pela topologia nesta célula.** Ela roda sob
   `SCRIPT_NAME=/encomendas`, e o corte do prefixo é do Django, não do Traefik:
   `meshcraft.top/encomendas/api/encomendas/interno/...` é alcançável pela
   internet. Quem fecha a porta é o Bearer, e só ele (`armadilhas/186`; guardas
   em `tests/test_porta_de_maquina.py`).
5. **`SITE_ID` ausente é 503, e não uma lista vazia.** Responder "nenhum
   parâmetro" e "esta pessoa não está na fila" com 200 seria a porta mentindo
   sobre uma instalação mal configurada.

Guardas: `tests/test_porta_de_maquina.py`.
"""

from __future__ import annotations

import re
from datetime import datetime

from django.utils import timezone
from ninja import Router, Schema
from ninja.errors import HttpError

from apps.core.auth import exigir_grau_de_escrita
from apps.core.sessao import ConfiguracaoAusente, site_desta_instalacao
from apps.encomendas import espera, mural
from apps.encomendas.models import CHAVES_DE_PARAMETRO, TAMANHO_MINIMO_DO_MOTIVO
from apps.encomendas.models import Encomenda as EncomendaModel
from apps.encomendas.models import MudancaDeStatus as MudancaDeStatusModel
from apps.encomendas.models import Parametro as ParametroModel
from apps.encomendas.models import PerfilProfissional as PerfilModel
from apps.encomendas.models import Proposta as PropostaModel
from apps.encomendas.models import ReservaDoMural as ReservaModel

router = Router()

# Os estados em que uma peça já é obra pronta desta pessoa. `concluida` entra
# junto com `aprovada` porque o repasse feito não desfaz a aprovação.
ESTADOS_DE_PECA_PRONTA = (
    EncomendaModel.Status.APROVADA,
    EncomendaModel.Status.CONCLUIDA,
)

HORA_DO_DIA = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
IDENTIFICADOR = re.compile(r"^[a-z][a-z0-9_.]*$")


class Erro(Schema):
    """O corpo de toda recusa desta porta. É a forma que o django-ninja já emite
    em `HttpError`, declarada aqui para que ela entre no contrato congelado em
    vez de existir só na prática."""

    detail: str


class LinhaDeParametro(Schema):
    valor: str
    desde: datetime
    motivo: str
    quem: str


class Parametro(Schema):
    """Uma chave do vocabulário fechado, com o valor de agora e o histórico.

    `vigente` é nulo quando ainda não há linha valendo, e isso não é falha: o
    piso de preço por nível nasceu de propósito sem número (lei §7), porque ele
    sai do piloto de papel. Uma chave sem valor precisa aparecer na tela do dono,
    ou ele não tem por onde gravar o primeiro.
    """

    chave: str
    tipo: str
    descricao: str
    vigente: LinhaDeParametro | None
    historico: list[LinhaDeParametro]


class MudancaDeParametro(Schema):
    """`desde` não é campo, e a ausência é decisão: esta porta grava a linha
    valendo agora. Mudança marcada para o futuro é poder que ninguém pediu, e
    quem o quisesse teria de explicar o que acontece com a oferta feita no
    meio."""

    valor: str
    motivo: str
    quem: str


class ReservaNoMural(Schema):
    encomenda_id: str
    expira_em: datetime


class PropostaDePe(Schema):
    encomenda_id: str
    de_quem: str
    rodada: int
    valida_ate: datetime


class FilaDeUmaPessoa(Schema):
    """Em que pé está a fila de uma pessoa, para a home e para o Estúdio.

    **Os campos vêm sempre, nulos quando `existe` é falso**, e não ausentes como
    o rascunho em papel previa: uma resposta que muda de forma obriga quem
    consome a escrever dois desenhos de tela para o mesmo lugar.

    OS TRES ULTIMOS CAMPOS SAO A EMENDA DE 04/09/2026, e são a razão de esta
    tarefa ter esperado a negociação existir. O contrato congela no degrau
    seguinte; congelá-lo antes do Mural faria a porta nascer cega justamente
    para o estado que o aluno mais consulta (`PLANO-AREA-DE-NEGOCIACAO.md` §3
    e §4).
    """

    existe: bool
    titulo_banca: str | None
    disponibilidade: str | None
    na_fila_desde: datetime | None
    entregas_aprovadas: int | None
    espera_estimada_dias: int | None
    encomenda_ativa_id: str | None
    ve_o_mural: bool | None
    reserva_no_mural: ReservaNoMural | None
    proposta_de_pe: PropostaDePe | None


class PecaAprovada(Schema):
    """`no_prazo` é nulo quando não houve prazo prometido para medir contra.
    O rascunho em papel pedia um booleano, e um booleano aqui teria de escolher
    entre chamar de atrasado quem nunca teve prazo e chamar de pontual quem
    ninguém mediu. As duas seriam invenção."""

    encomenda_id: str
    nome_da_peca: str
    cartao: str
    origem: str
    aprovada_em: datetime | None
    no_prazo: bool | None
    previa_url: str | None


class PecasAprovadas(Schema):
    entregas: int
    no_prazo: int
    pecas: list[PecaAprovada]


class PagamentoConfirmado(Schema):
    encomenda_id: str
    pagamento_id: str
    valor_pago_cents: int
    confirmado_em: datetime
    chave_idempotencia: str


class ItemDaAuditoria(Schema):
    codigo: str
    mensagem: str
    medido: str | None = None
    limite: str | None = None


class ResultadoDaAuditoria(Schema):
    entrega_id: str
    versao: int
    resultado: str
    itens: list[ItemDaAuditoria] = []


class EstadoDaEncomenda(Schema):
    encomenda_id: str
    status: str


def _site() -> str:
    """O site desta instalação, ou 503 com o nome da variável que falta."""
    try:
        return site_desta_instalacao()
    except ConfiguracaoAusente as erro:
        raise HttpError(503, str(erro)) from erro


def _valor_fora_do_tipo(chave: str, valor: str) -> str:
    """A frase que explica por que este valor não serve, ou vazio se ele serve.

    A régua é o TIPO declarado no vocabulário fechado, e não uma segunda tabela:
    `CHAVES_DE_PARAMETRO` é quem diz que `janela_inicio` é hora do dia e que
    `relogio_da_oferta` é um número de horas.
    """
    tipo = CHAVES_DE_PARAMETRO[chave][0]
    if tipo in ("inteiro", "horas", "dias", "centavos"):
        if not valor.isdigit():
            return f"{chave} e do tipo {tipo}: escreva um numero inteiro, sem sinal"
        return ""
    if tipo == "hora_do_dia":
        if not HORA_DO_DIA.match(valor):
            return (
                f"{chave} e uma hora do dia: escreva no formato HH:MM, de 00:00 a 23:59"
            )
        return ""
    # O único `enum` de hoje é `repasse_apos_aprovacao`, e a lei §6 fixou UM
    # valor para ele sem listar os outros possíveis. Fechar o vocabulário aqui
    # seria inventar produto; deixá-lo livre seria aceitar uma frase inteira numa
    # coluna de 60. A régua que sobra, e é honesta, é a FORMA: um identificador.
    if not IDENTIFICADOR.match(valor):
        return (
            f"{chave} e uma escolha nomeada: use letras minusculas, numeros, "
            "ponto e sublinhado, como proximo_dia_util"
        )
    return ""


@router.get(
    "/parametros",
    response={200: list[Parametro], 401: Erro, 503: Erro},
    operation_id="getParameters",
    summary="Os parametros vigentes da fila, com o historico de cada um",
)
def listar_parametros(request):
    """O vocabulário fechado INTEIRO, e não só as chaves já semeadas.

    A tela do dono precisa mostrar a linha do piso de preço que ainda não tem
    número, ou ele não descobre que pode gravá-lo. Chave sem linha vem com
    `vigente: null` e histórico vazio.

    O valor de agora sai de `Parametro.vigente_em`, a mesma função que o motor
    usa. Uma segunda expressão da mesma conta divergiria algum dia, e divergir
    aqui significa a tela do dono mostrar um número e o motor obedecer a outro.
    """
    site = _site()
    agora = timezone.now()
    linhas: dict[str, list] = {}
    for linha in ParametroModel.objects.filter(site_id=site).order_by(
        "chave", "-desde"
    ):
        linhas.setdefault(linha.chave, []).append(linha)
    return 200, [
        {
            "chave": chave,
            "tipo": tipo,
            "descricao": descricao,
            "vigente": ParametroModel.vigente_em(chave, agora, site_id=site),
            "historico": linhas.get(chave, []),
        }
        for chave, (tipo, descricao) in sorted(CHAVES_DE_PARAMETRO.items())
    ]


@router.put(
    "/parametros/{chave}",
    response={
        200: LinhaDeParametro,
        400: Erro,
        401: Erro,
        403: Erro,
        404: Erro,
        503: Erro,
    },
    operation_id="setParameter",
    summary="Muda um parametro acrescentando uma linha nova com motivo",
)
def mudar_parametro(request, chave: str, dados: MudancaDeParametro):
    """Acrescenta uma linha. **Nunca reescreve a que está valendo.**

    O `UPDATE` é recusado pelo PostgreSQL, por gatilho, então "nunca reescreve"
    não é uma promessa deste arquivo. O que este arquivo garante é o resto: o
    motivo escrito, o autor nomeado e o valor dentro do tipo da chave.

    Chave desconhecida é 404: o vocabulário é fechado e nasce no código da
    célula, nunca pela porta.
    """
    exigir_grau_de_escrita(request)
    site = _site()
    if chave not in CHAVES_DE_PARAMETRO:
        raise HttpError(404, f"nao existe parametro chamado {chave!r} nesta celula")
    motivo = dados.motivo.strip()
    if len(motivo) < TAMANHO_MINIMO_DO_MOTIVO:
        raise HttpError(
            400,
            f"escreva o motivo da mudanca com pelo menos {TAMANHO_MINIMO_DO_MOTIVO} "
            "caracteres: e o rastro que a proxima pessoa vai ler daqui a seis meses",
        )
    quem = dados.quem.strip()
    if not quem:
        raise HttpError(400, "diga quem esta mudando: mudanca de parametro tem autor")
    valor = dados.valor.strip()
    recusa = _valor_fora_do_tipo(chave, valor)
    if recusa:
        raise HttpError(400, recusa)
    linha = ParametroModel.objects.create(
        site_id=site,
        chave=chave,
        valor=valor,
        desde=timezone.now(),
        motivo=motivo,
        quem=quem,
    )
    return 200, linha


@router.get(
    "/perfis/{id}/fila",
    response={200: FilaDeUmaPessoa, 401: Erro, 503: Erro},
    operation_id="getQueueStanding",
    summary="Em que pe esta a fila de uma pessoa, para a home e o Estudio",
)
def fila_de_uma_pessoa(request, id: str):
    """200 com `existe: false` para quem não tem perfil profissional. Nunca 404.

    "Não conheço esta pessoa" é a resposta, e não um erro: um 404 obrigaria cada
    consumidor a traduzir "erro" em "ainda não entrou", e o primeiro que tratasse
    404 como falha de rede mostraria a tela errada para todo visitante novo.

    **A ESPERA substitui a posição** (plano §5.4), e vem nula quando não há ritmo
    para medir. Ver `apps/encomendas/espera.py`.

    **Os três campos do Mural e da negociação** respondem o que o aluno mais
    consulta: tem prateleira para mim? peguei alguma coisa? tem proposta parada
    esperando resposta?
    """
    site = _site()
    agora = timezone.now()
    perfil = PerfilModel.objects.filter(pessoa_id=id, site_id=site).first()
    if perfil is None:
        return 200, {
            "existe": False,
            "titulo_banca": None,
            "disponibilidade": None,
            "na_fila_desde": None,
            "entregas_aprovadas": None,
            "espera_estimada_dias": None,
            "encomenda_ativa_id": None,
            "ve_o_mural": None,
            "reserva_no_mural": None,
            "proposta_de_pe": None,
        }

    ativa = (
        EncomendaModel.objects.filter(
            aluno=perfil, site_id=site, status__in=EncomendaModel.ESTADOS_ATIVOS
        )
        .order_by("criada_em")
        .first()
    )
    reserva = (
        ReservaModel.objects.filter(aluno=perfil, resultado__in=ReservaModel.VIVAS)
        .order_by("-pegada_em")
        .first()
    )
    proposta = (
        PropostaModel.objects.filter(
            aluno=perfil, resultado=PropostaModel.Resultado.PENDENTE
        )
        .order_by("-criada_em")
        .first()
    )
    return 200, {
        "existe": True,
        # Título vazio é "o professor ainda não deu", e nulo diz isso melhor que
        # uma string vazia para quem desenha a tela do outro lado.
        "titulo_banca": perfil.titulo_banca or None,
        "disponibilidade": perfil.disponibilidade,
        "na_fila_desde": perfil.data_entrada_fila,
        "entregas_aprovadas": perfil.entregas_aprovadas,
        "espera_estimada_dias": espera.estimar_dias(perfil, agora, site_id=site),
        "encomenda_ativa_id": str(ativa.pk) if ativa else None,
        # A MESMA lista que a tela do Mural desenha, medida pela MESMA régua de
        # elegibilidade do motor. Mural vazio não é erro: quem nunca entregou
        # ainda não alcança projeto nenhum, e é assim que a lei quer.
        "ve_o_mural": bool(mural.listar(perfil.pk, agora, site_id=site)),
        "reserva_no_mural": (
            {
                "encomenda_id": str(reserva.encomenda_id),
                "expira_em": reserva.expira_em,
            }
            if reserva
            else None
        ),
        "proposta_de_pe": (
            {
                "encomenda_id": str(proposta.encomenda_id),
                "de_quem": proposta.de_quem,
                "rodada": proposta.rodada,
                "valida_ate": proposta.valida_ate,
            }
            if proposta
            else None
        ),
    }


@router.get(
    "/perfis/{id}/pecas-aprovadas",
    response={200: PecasAprovadas, 401: Erro, 503: Erro},
    operation_id="getApprovedPieces",
    summary="As pecas aprovadas E autorizadas de uma pessoa, para o Estudio",
)
def pecas_aprovadas(request, id: str):
    """A ÚNICA porta por onde uma peça sai desta célula.

    Só encomendas `aprovada` ou `concluida` **e** com `autorizacao_portfolio`
    registrada pelo cliente ([INV-ENC-S4]). Nada de briefing, nada de cliente,
    nada de contato ([INV-ENC-S3]): sai o nome que o cliente deu à peça, e mais
    nada do que ele escreveu.

    Lista vazia para quem não tem nada, nunca 404.

    `previa_url` é nulo até a Fase 5 decidir onde moram os arquivos da entrega.
    Ele existe desde já porque o Estúdio desenha a moldura da imagem em volta
    dele, e um campo que aparece depois muda a tela de quem já consumia.
    """
    site = _site()
    perfil = PerfilModel.objects.filter(pessoa_id=id, site_id=site).first()
    if perfil is None:
        return 200, {"entregas": 0, "no_prazo": 0, "pecas": []}

    prontas = list(
        EncomendaModel.objects.filter(
            aluno=perfil,
            site_id=site,
            status__in=ESTADOS_DE_PECA_PRONTA,
            autorizacao_portfolio=True,
        ).order_by("-atualizada_em")
    )
    # Quando cada uma foi aprovada, do livro de transições: é o fato registrado,
    # e não `atualizada_em`, que qualquer gravação posterior moveria.
    aprovada_em = {
        mudanca.encomenda_id: mudanca.em
        for mudanca in MudancaDeStatusModel.objects.filter(
            encomenda__in=prontas, para=EncomendaModel.Status.APROVADA
        ).order_by("em")
    }
    pecas = []
    for encomenda in prontas:
        quando = aprovada_em.get(encomenda.pk)
        pecas.append(
            {
                "encomenda_id": str(encomenda.pk),
                "nome_da_peca": encomenda.briefing.get("nome_da_peca", ""),
                "cartao": encomenda.cartao,
                "origem": encomenda.origem,
                "aprovada_em": quando,
                "no_prazo": (
                    quando <= encomenda.prazo_prometido_ate
                    if quando and encomenda.prazo_prometido_ate
                    else None
                ),
                "previa_url": None,
            }
        )
    return 200, {
        "entregas": len(pecas),
        "no_prazo": sum(1 for peca in pecas if peca["no_prazo"]),
        "pecas": pecas,
    }


@router.post(
    "/interno/pagamentos/confirmado",
    response={
        200: EstadoDaEncomenda,
        401: Erro,
        403: Erro,
        404: Erro,
        409: Erro,
        501: Erro,
    },
    operation_id="confirmPayment",
    summary="A celula de pagamentos avisa que a cobranca de uma encomenda foi confirmada",
)
def pagamento_confirmado(request, dados: PagamentoConfirmado):
    """Declarada e fechada: **responde 501 até a Fase 3**.

    Ela existe hoje para que o contrato congelado do degrau 2.8 já a contenha, e
    o dia em que a `pagamentos` entrar não seja um Rito de Contrato inteiro. Não
    opera porque dinheiro é a Fase 3, e a diretiva do mantenedor é clara (lei
    §3.4): até a Fase 3 a única confirmação que existe é a do plantão, na tela,
    com autor.

    **O grau de escrita é conferido ANTES do 501**, e a ordem não é detalhe: um
    par que não pode gravar não deve nem descobrir que esta porta existe e está
    desligada.
    """
    exigir_grau_de_escrita(request)
    raise HttpError(
        501,
        "a confirmacao de pagamento por porta de maquina entra na Fase 3. Ate la, "
        "quem declara pago e o plantao, na tela, com autor (lei 3.4).",
    )


@router.post(
    "/interno/auditoria/resultado",
    response={200: EstadoDaEncomenda, 401: Erro, 403: Erro, 404: Erro, 501: Erro},
    operation_id="reportAudit",
    summary="O worker de auditoria devolve o veredito sobre uma entrega",
)
def resultado_da_auditoria(request, dados: ResultadoDaAuditoria):
    """Declarada e fechada: **responde 501 até a Fase 5**.

    Mesma razão da vizinha de cima. A auditoria automática roda fora desta
    célula, e o que ela vai mover (`entregue` de volta a `em_producao`, com a
    frase que o aluno lê) depende da Entrega, que esta célula ainda não tem.
    """
    exigir_grau_de_escrita(request)
    raise HttpError(
        501,
        "o veredito da auditoria automatica entra na Fase 5, junto com a Entrega. "
        "Ate la esta porta existe e nao opera.",
    )
