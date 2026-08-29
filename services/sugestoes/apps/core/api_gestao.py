# apps/core/api_gestao.py — a superfície de MÁQUINA da gestão da Caixa
"""O que a Caixa responde ao Admin sobre as ideias, e o que ela aceita dele.

Lei do assunto: `docs/decisoes/DECISAO-a-gestao-da-caixa-mora-no-admin.md`
(28/08/2026, decisão do mantenedor). A gestão das ideias deixa de morar na
Caixa e passa a morar em `/admin/caixa/` — porta única, decisão dele: *"não
vamos espalhar painéis ou gestão por aí, tudo será em /admin"*.

**Por que isto existe em vez de o Admin ler o banco:** Lei 3 — nenhuma célula lê
o banco de outra. O Admin pergunta, a Caixa responde. É o mesmo desenho que a
tela de alunos do Admin já usa com a célula `alunos`.

O que esta superfície é, e o que ela não é:

* **É de DOMÍNIO, não de tela.** Ela devolve os fatos de cada ideia — votos,
  plateia, estado, datas, se tem avaliação, se tem ChangeSpec — e **não** as
  colunas, os baldes ou a ordem. Quem agrupa é o Admin. Um contrato com forma de
  tela precisaria de um Rito de Contrato (uma conversa com o mantenedor) a cada
  ajuste de layout; um contrato com forma de domínio deixa a tela evoluir de
  graça. A conta que NÃO sai daqui é a plateia: ela é definição desta célula
  ([INV-SUG13]) e viaja pronta, porque é a mesma gente que o sininho vai avisar.
* **Ela não afrouxa trava nenhuma.** As três escritas passam pelos MESMOS
  caminhos que as telas usavam (`moderacao.registrar_mudanca_de_status`,
  `changespecs.registrar`) — histórico na mesma transação, avisos para a plateia
  inteira, justificativa obrigatória no "não vamos fazer", e o corredor do
  ChangeSpec nos três degraus. Reimplementar aqui seria abrir uma segunda porta
  para o mesmo cofre.

**Os dois papéis, e por que só um mudou de dono** (as duas decisões do
mantenedor em 28/08/2026, e a primeira foi tomada contra a recomendação desta
sessão, sabendo do custo — ver a lei):

| Papel | Quem decide, depois desta mudança |
|---|---|
| **moderar** (mudar fase, escrever avaliação) | o Admin. Quem entra em `ADMIN_EMAILS` modera — lista ÚNICA, e a `sugestoes` confia no Bearer do par. `SUGESTOES_STAFF_EMAILS` deixa de governar estas rotas. |
| **assinar** (autorizar obra) | continua a `sugestoes`, por `SUGESTOES_APROVADORES`, fail-closed. Não mudou, e mudar de casa a tela não muda isto. |

A consequência aceita da lista única está escrita na lei, por extenso, para
nenhuma sessão futura "consertar" isto achando que foi descuido: **dar acesso ao
Admin a alguém passa a dar, no mesmo gesto, o poder de mexer nas ideias dos
alunos.**

**O e-mail do aluno não sai daqui** (decisão do mantenedor no mesmo dia,
mantendo a `DECISAO-EVO-01` §3): a resposta carrega o nome exibido de quem
sugeriu, nunca o endereço. O único e-mail que ATRAVESSA é o de quem AGE — vindo
do Admin, que já o resolveu pela `identidade` para abrir a própria porta.
"""

from datetime import date

from django.db.models import Exists, Max, OuterRef
from django.db.models.functions import Coalesce
from django.http import Http404
from django.utils import timezone
from ninja import Router, Schema

from apps.sugestoes.eventos import AtorSemIdDaPlataforma
from apps.sugestoes.models import (
    AvaliacaoInterna,
    ChangeSpecAprovado,
    Comentario,
    CorredorAusente,
    HistoricoStatus,
    Sugestao,
    Voto,
)

from . import sessao as ses
from .changespecs import ChangeSpecInvalido, e_aprovador
from .changespecs import registrar as registrar_changespec
from .gestao import (
    DIAS_DE_SILENCIO_DEMAIS,
    JA_RESPONDIDAS,
    plateia_de,
    silencio_por_pessoa,
)

# `registrar_mudanca_de_status` carrega consigo as regras que esta superfície
# NÃO reimplementa: a justificativa obrigatória do "não vamos fazer"
# (`EXIGEM_JUSTIFICATIVA`), o histórico na mesma transação e o leque de avisos.
from .moderacao import (
    JustificativaObrigatoria,
    STATUS_QUE_A_EQUIPE_ESCOLHE,
    registrar_mudanca_de_status,
)
from .participacao import quadro_atual, sugestoes_ordenadas

router = Router()


# ---------------------------------------------------------------------------
# O que a Caixa conta
# ---------------------------------------------------------------------------
#
# [armadilhas/020] Os nomes daqui NÃO repetem nomes de model: `Sugestao` e
# `AvaliacaoInterna` estão importados neste módulo, e um `ninja.Schema` com o
# mesmo nome sombrearia o import em SILÊNCIO — sem erro de import, sem aviso do
# lint, estourando só dentro do pydantic na hora do teste. Daí o sufixo.


class AvaliacaoDaEquipe(Schema):
    """As notas internas. Só o Admin as vê; o aluno nunca (spec §8)."""

    impacto_educacional: int
    impacto_comercial: int
    esforco_tecnico: int
    notas: str
    decisao_produto: str


class IdeiaEmGestao(Schema):
    """Os FATOS de uma ideia. Nenhuma coluna, nenhum balde, nenhuma ordem."""

    id: int
    titulo: str
    problema: str
    solucao_proposta: str
    categoria: str
    status: str
    votos: int
    comentarios: int
    # A plateia: quantas pessoas DISTINTAS estão atrás desta ideia — autor, quem
    # votou e quem comentou, cada uma contada uma vez. Viaja pronta porque é a
    # mesma gente que receberá o aviso quando a ideia andar ([INV-SUG13]); uma
    # segunda contagem do outro lado seria uma segunda verdade.
    pessoas: int
    autor: str
    criada_em: str
    # Quando a ideia entrou no estado em que está AGORA — a última linha do
    # histórico, ou a criação quando ela nunca mudou de fase. Não é a idade dela.
    parada_desde: str
    # `false` = ninguém que interagiu recebeu aviso nenhum ainda. É diferente de
    # "recebeu há muito tempo", e quem mostra precisa poder dizer as duas coisas.
    ja_ouviram: bool
    tem_avaliacao: bool
    tem_changespec: bool
    # A última nota do histórico, quando a ideia saiu do trilho (recusada ou
    # juntada a outra). É a MESMA frase que foi entregue a quem esperava — duas
    # redações para o aluno e para a equipe seriam duas verdades sobre a recusa.
    motivo_da_saida: str
    avaliacao: "AvaliacaoDaEquipe | None" = None
    # O arquivamento (`DECISAO-arquivar-ideia.md`, 29/08/2026). NÃO é status: uma
    # ideia arquivada pode estar em qualquer fase do trilho — arquivar é a
    # equipe tirando algo de vista (spam, duplicata, engano), não uma decisão de
    # produto sobre ela. `arquivada_em` vazio é "nunca foi".
    arquivada: bool = False
    arquivada_em: str = ""
    motivo_do_arquivamento: str = ""
    # O apagamento definitivo (`DECISAO-apagar-ideia.md`, 29/08/2026). Uma
    # ideia apagada também é `arquivada` (mesmo carimbo) — `apagada` é o
    # campo que diz à tela que não há mais nada para restaurar: o botão
    # "Restaurar" não aparece, e o conteúdo que viaja aqui já está vazio.
    apagada: bool = False


class LinhaDoHistorico(Schema):
    """Uma mudança de fase, como ela ficou registrada — append-only na origem.

    `por` é o nome exibido de quem moderou, nunca o e-mail: a regra do e-mail
    vale para QUALQUER pessoa que apareça na resposta, não só para o aluno que
    sugeriu.
    """

    quando: str
    de: str
    para: str
    nota: str
    por: str


class IdeiaComHistorico(IdeiaEmGestao):
    """A ideia inteira, com a história dela.

    Existe separada de `IdeiaEmGestao` porque o histórico só faz sentido quando
    se olha UMA ideia: carregá-lo na lista multiplicaria a resposta por algo que
    nenhuma tela de lista mostra — e cresceria com o uso, que é o pior tipo de
    custo, o que só aparece quando a Caixa dá certo.

    Ela nasce agora porque a gestão saiu da Caixa: sem esta operação, a história
    de cada ideia ficaria inalcançável no dia em que as telas antigas forem
    aposentadas. Descobrir isso ANTES de aposentá-las é a razão de esta emenda
    existir.
    """

    historico: "list[LinhaDoHistorico]"


class QuadroEmGestao(Schema):

    quadro: str
    ideias: "list[IdeiaEmGestao]"
    # Quem AGE não é quem lê: este campo responde "a pessoa que o Admin informou
    # pode assinar?" — e é só um espelho de `SUGESTOES_APROVADORES`. Serve para o
    # Admin não desenhar um botão que a Caixa vai recusar; a recusa de verdade
    # continua acontecendo aqui, na escrita.
    pode_assinar: bool
    # Os três números que SÓ esta célula consegue produzir, e por isso viajam
    # prontos: eles contam PESSOAS DISTINTAS entre várias ideias, e quem tem
    # apenas a contagem por ideia não consegue deduplicar quem está atrás de
    # duas — contaria a mesma pessoa duas vezes.
    #
    # São fatos do domínio ("quantas pessoas aguardam resposta"), não recortes de
    # tela: nenhum deles muda se o layout do consumidor mudar. A alternativa
    # honesta seria mandar a lista de ids de cada plateia para o consumidor
    # deduplicar — dezenas de milhares de ids atravessando a rede para produzir
    # três inteiros.
    pessoas_esperando: int
    # `None` quando não há ninguém esperando — e é diferente de zero, que se
    # leria como "todo mundo ouviu hoje".
    silencio_medio_em_dias: "int | None" = None
    pessoas_em_silencio_demais: int = 0


# ---------------------------------------------------------------------------
# O que a Caixa aceita
# ---------------------------------------------------------------------------


class QuemAge(Schema):
    """Quem está agindo, vindo do Admin.

    O e-mail é o de quem abriu o Admin — resolvido lá pela `identidade`, que é
    quem tem esse direito. A Caixa o usa para duas coisas e nada mais: achar (ou
    cunhar) a linha local que o histórico exige como autor da mudança, e conferir
    a lista de aprovadores. Não é o e-mail de nenhum ALUNO: esse continua sem
    sair daqui.

    **`por_id_da_plataforma` não é enfeite, e não é opcional na prática.** Toda
    mudança de status vira uma carta endereçada, e [INV-SUG12] exige que quem
    moderou tenha o id que atravessa a plataforma — sem ele o fato não pode ser
    afirmado e a escrita é recusada com instrução (não com erro 500). O Admin já
    tem esse id: é o mesmo `SessionFull.id` que ele leu da `identidade` para
    abrir a própria porta. Ele entra como texto vazio-permitido só porque o
    contrato da `identidade` declara o campo nulável — e é justamente esse caso
    que a recusa legível existe para cobrir.
    """

    por_email: str
    por_nome: str = ""
    por_id_da_plataforma: str = ""


class MudancaDeStatus(QuemAge):
    status: str
    nota: str = ""


class AvaliacaoEscrita(QuemAge):
    impacto_educacional: int = 0
    impacto_comercial: int = 0
    esforco_tecnico: int = 0
    notas: str = ""
    decisao_produto: str = ""


class ChangeSpecEscrito(QuemAge):
    change_id: str
    documento: str
    aprovado_por: str
    aprovado_em: date


class ArquivamentoEscrito(QuemAge):
    motivo: str = ""


class Recusa(Schema):
    """Uma recusa que ENSINA o caminho — a frase é a mesma que a tela dizia."""

    erro: str


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------


def _ideias_do_quadro(quadro):
    """Sempre COM as arquivadas — `incluir_arquivadas=True` de propósito.

    Quem decide se elas aparecem é `listar_ideias`, olhando o parâmetro do
    Admin; e `uma_ideia`/as escritas de arquivar precisam achar a ideia
    independente do estado dela, ou desarquivar ficaria impossível.
    """
    return (
        sugestoes_ordenadas(quadro, incluir_arquivadas=True)
        .annotate(
            parada_desde=Coalesce(Max("historico__criado_em"), "criado_em"),
            tem_avaliacao=Exists(
                AvaliacaoInterna.objects.filter(sugestao_id=OuterRef("pk"))
            ),
            tem_changespec=Exists(
                ChangeSpecAprovado.objects.filter(sugestao_id=OuterRef("pk"))
            ),
            ja_ouviram=Exists(
                HistoricoStatus.objects.filter(sugestao_id=OuterRef("pk"))
            ),
        )
        .prefetch_related("historico__alterado_por", "avaliacao")
    )


def _motivo_da_saida(sugestao) -> str:
    """A última nota do histórico — só faz sentido para quem saiu do trilho."""
    if sugestao.status not in (
        Sugestao.Status.NAO_PLANEJADO,
        Sugestao.Status.MESCLADO,
    ):
        return ""
    ultima = max(
        sugestao.historico.all(), key=lambda linha: linha.criado_em, default=None
    )
    return ultima.nota if ultima else ""


def _como_fato(ideia, plateias) -> dict:
    """Uma ideia, na forma que atravessa a fronteira."""
    return {
        "id": ideia.id,
        "titulo": ideia.titulo,
        "problema": ideia.problema,
        "solucao_proposta": ideia.solucao_proposta,
        "categoria": ideia.categoria.nome,
        "status": ideia.status,
        "votos": ideia.total_votos,
        "comentarios": ideia.total_comentarios,
        "pessoas": plateias.get(ideia.id, 1),
        # Nome exibido, nunca o e-mail — e vazio é resposta legítima: quem exibe
        # decide o que escrever no lugar, como já faz o `getSession`. Inventar um
        # apelido aqui seria esta célula decidindo o texto de uma tela que não é
        # dela.
        "autor": ideia.autor.nome_exibido,
        "criada_em": ideia.criado_em.isoformat(),
        "parada_desde": ideia.parada_desde.isoformat(),
        "ja_ouviram": ideia.ja_ouviram,
        "tem_avaliacao": ideia.tem_avaliacao,
        "tem_changespec": ideia.tem_changespec,
        "motivo_da_saida": _motivo_da_saida(ideia),
        "arquivada": ideia.arquivada_em is not None,
        "arquivada_em": ideia.arquivada_em.isoformat() if ideia.arquivada_em else "",
        "motivo_do_arquivamento": ideia.motivo_do_arquivamento,
        "apagada": ideia.apagada_em is not None,
        "avaliacao": (
            {
                "impacto_educacional": ideia.avaliacao.impacto_educacional,
                "impacto_comercial": ideia.avaliacao.impacto_comercial,
                "esforco_tecnico": ideia.avaliacao.esforco_tecnico,
                "notas": ideia.avaliacao.notas,
                "decisao_produto": ideia.avaliacao.decisao_produto,
            }
            if ideia.tem_avaliacao
            else None
        ),
    }


@router.get(
    "/gestao/ideias",
    response=QuadroEmGestao,
    operation_id="listManagementIdeas",
    summary="Os fatos de cada ideia do quadro, para quem conduz",
    description=(
        "Devolve o quadro inteiro com os fatos de cada ideia — votos, plateia, "
        "estado, datas, se tem avaliação interna e se tem ChangeSpec aprovado. "
        "NÃO devolve colunas, baldes nem ordenação: agrupar é do consumidor. O "
        "e-mail de quem sugeriu nunca viaja. Por padrão as arquivadas ficam de "
        "fora — `incluir_arquivadas=true` as traz de volta, para quem precisa "
        "achar uma ideia arquivada para desarquivar."
    ),
)
def listar_ideias(request, por_email: str = "", incluir_arquivadas: bool = False):
    quadro = quadro_atual()
    agora = timezone.now()
    todas = list(_ideias_do_quadro(quadro))
    # Apagada nunca reaparece, nem com `incluir_arquivadas=True`: não sobrou
    # nada nela para alguém "achar de novo" — é diferente de arquivada, que
    # `incluir_arquivadas` existe justamente para reencontrar.
    todas = [i for i in todas if not i.apagada_em]
    ideias = todas if incluir_arquivadas else [i for i in todas if not i.arquivada_em]
    plateias = plateia_de(ideias)

    # Quem ainda espera: as ideias que NÃO receberam resposta. Recusada com
    # justificativa e juntada a outra contam como respondidas — o aviso saiu, e
    # cobrar para sempre uma dívida paga ensinaria a equipe a evitar recusar.
    em_aberto = [ideia for ideia in ideias if ideia.status not in JA_RESPONDIDAS]
    silencio = silencio_por_pessoa(em_aberto, agora)
    caladas = [dias for dias in silencio.values() if dias > DIAS_DE_SILENCIO_DEMAIS]

    return {
        "quadro": quadro.nome,
        "pode_assinar": bool(por_email) and e_aprovador(por_email),
        "pessoas_esperando": len(silencio),
        "silencio_medio_em_dias": (
            round(sum(silencio.values()) / len(silencio)) if silencio else None
        ),
        "pessoas_em_silencio_demais": len(caladas),
        "ideias": [_como_fato(ideia, plateias) for ideia in ideias],
    }


@router.get(
    "/gestao/ideias/{sugestao_id}",
    response=IdeiaComHistorico,
    operation_id="getManagementIdea",
    summary="Uma ideia, com a história dela",
    description=(
        "A mesma ideia da lista, mais o histórico de mudanças de fase — cada "
        "linha com quando, de onde para onde, a nota escrita e o nome de quem "
        "moderou. O histórico é append-only na origem: uma correção é uma linha "
        "nova, nunca uma linha reescrita. Nenhum e-mail viaja."
    ),
)
def uma_ideia(request, sugestao_id: int):
    ideia = _ideias_do_quadro(quadro_atual()).filter(pk=sugestao_id).first()
    if ideia is None:
        raise Http404("ideia inexistente")
    corpo = _como_fato(ideia, plateia_de([ideia]))
    corpo["historico"] = [
        {
            "quando": linha.criado_em.isoformat(),
            "de": linha.status_anterior,
            "para": linha.status_novo,
            "nota": linha.nota,
            # Nome exibido, nunca o e-mail — a regra vale para quem moderou
            # tanto quanto para quem sugeriu.
            "por": linha.alterado_por.nome_exibido,
        }
        for linha in sorted(ideia.historico.all(), key=lambda l: l.criado_em)
    ]
    return corpo


# ---------------------------------------------------------------------------
# Escrita — pelos MESMOS caminhos das telas, nunca por uma porta nova
# ---------------------------------------------------------------------------


def _ideia(sugestao_id: int) -> Sugestao:
    sugestao = Sugestao.objects.filter(pk=sugestao_id).first()
    if sugestao is None:
        raise Http404("ideia inexistente")
    return sugestao


def _quem(payload: QuemAge):
    """A linha local de quem está agindo — o histórico a exige como autor.

    `cunhar_ou_recuperar` e não `get`: quem entra no Admin pode nunca ter aberto
    a Caixa, e recusar a moderação por isso seria uma porta fechada por um
    detalhe de cadastro. A cunhagem é a mesma de sempre — uma linha por pessoa,
    casada por e-mail.
    """
    return ses.cunhar_ou_recuperar(
        email=payload.por_email,
        nome=payload.por_nome or payload.por_email,
        id_da_plataforma=payload.por_id_da_plataforma or None,
    )


@router.post(
    "/gestao/ideias/{sugestao_id}/status",
    response={200: IdeiaEmGestao, 422: Recusa},
    operation_id="setIdeaStatus",
    summary="Move a ideia de fase, com histórico e avisos",
    description=(
        "Passa pelo mesmo caminho da tela antiga: o histórico nasce na MESMA "
        "transação, a plateia inteira recebe aviso, 'não planejado' exige "
        "justificativa e 'planejado → em desenvolvimento' exige ChangeSpec "
        "aprovado registrado. Recusa 422 com a frase que ensina o caminho."
    ),
)
def mudar_status(request, sugestao_id: int, payload: MudancaDeStatus):
    sugestao = _ideia(sugestao_id)
    if payload.status not in {status.value for status in STATUS_QUE_A_EQUIPE_ESCOLHE}:
        return 422, {"erro": "Esta fase não é uma das que a equipe escolhe."}
    try:
        registrar_mudanca_de_status(
            sugestao=sugestao,
            status_novo=payload.status,
            nota=payload.nota,
            por=_quem(payload),
        )
    except JustificativaObrigatoria:
        return 422, {
            "erro": (
                "Para dizer que a ideia não será feita, escreva o porquê: quem "
                "sugeriu vai ler essa frase."
            )
        }
    except CorredorAusente as recusa:
        return 422, {"erro": str(recusa)}
    except AtorSemIdDaPlataforma:
        # [INV-SUG12] O fato não pode ser afirmado sem quem o afirmou. Recusa
        # legível em vez de 500: o caminho existe e é curto — a pessoa entra uma
        # vez pelo site e a porta grava o id na reentrada.
        return 422, {
            "erro": (
                "Não consegui registrar quem fez esta mudança: falta o "
                "identificador que atravessa a plataforma. Entre uma vez em "
                "meshcraft.top com a sua conta e tente de novo — a porta grava "
                "esse dado na entrada."
            )
        }
    return _uma_ideia(sugestao_id)


@router.post(
    "/gestao/ideias/{sugestao_id}/avaliacao",
    response=IdeiaEmGestao,
    operation_id="setIdeaReview",
    summary="Escreve a avaliação interna da equipe",
    description=(
        "Impacto educacional, impacto comercial, esforço técnico, anotações e a "
        "decisão de produto. Nada disto é visível ao aluno (spec §8)."
    ),
)
def avaliar(request, sugestao_id: int, payload: AvaliacaoEscrita):
    sugestao = _ideia(sugestao_id)
    AvaliacaoInterna.objects.update_or_create(
        sugestao=sugestao,
        defaults={
            "impacto_educacional": payload.impacto_educacional,
            "impacto_comercial": payload.impacto_comercial,
            "esforco_tecnico": payload.esforco_tecnico,
            "notas": payload.notas,
            "decisao_produto": payload.decisao_produto,
            "avaliado_por": _quem(payload),
        },
    )
    return _uma_ideia(sugestao_id)


@router.post(
    "/gestao/ideias/{sugestao_id}/changespec",
    response={200: IdeiaEmGestao, 403: Recusa, 422: Recusa},
    operation_id="registerApprovedChangeSpec",
    summary="Registra o ChangeSpec aprovado que destrava a obra",
    description=(
        "O SEGUNDO portão da Caixa, e ele NÃO mudou de dono: só quem está em "
        "SUGESTOES_APROVADORES registra, e a lista vazia recusa todo mundo. "
        "Estar autorizado no Admin não basta — moderar e autorizar "
        "desenvolvimento são papéis diferentes."
    ),
)
def registrar_o_changespec(request, sugestao_id: int, payload: ChangeSpecEscrito):
    if not e_aprovador(payload.por_email):
        return 403, {
            "erro": (
                "Só quem está na lista de aprovadores da Caixa autoriza uma "
                "ideia a entrar em desenvolvimento. Estar no Admin dá o direito "
                "de moderar, não o de assinar obra."
            )
        }
    sugestao = _ideia(sugestao_id)
    try:
        registrar_changespec(
            sugestao=sugestao,
            por=_quem(payload),
            change_id=payload.change_id,
            documento=payload.documento,
            aprovado_por=payload.aprovado_por,
            aprovado_em=payload.aprovado_em.isoformat(),
        )
    except ChangeSpecInvalido as recusa:
        return 422, {"erro": " ".join(recusa.args[0])}
    return _uma_ideia(sugestao_id)


@router.post(
    "/gestao/ideias/{sugestao_id}/arquivar",
    response={200: IdeiaEmGestao, 422: Recusa},
    operation_id="archiveIdea",
    summary="Arquiva a ideia — some do quadro do aluno, nada se perde",
    description=(
        "`DECISAO-arquivar-ideia.md` (29/08/2026): não é um apagar de vez. A "
        "ideia, os votos, os comentários e o histórico continuam intactos no "
        "banco; ela só deixa de aparecer no quadro, na busca de duplicatas e em "
        "qualquer página que o aluno alcance. Desarquivar traz tudo de volta "
        "exatamente como estava. Recusa 422 se já estiver arquivada."
    ),
)
def arquivar(request, sugestao_id: int, payload: ArquivamentoEscrito):
    sugestao = _ideia(sugestao_id)
    if sugestao.apagada_em is not None:
        return 422, {"erro": "Esta ideia foi apagada definitivamente."}
    if sugestao.arquivada_em is not None:
        return 422, {"erro": "Esta ideia já está arquivada."}
    sugestao.arquivada_em = timezone.now()
    sugestao.arquivada_por = _quem(payload)
    sugestao.motivo_do_arquivamento = payload.motivo
    sugestao.save(
        update_fields=["arquivada_em", "arquivada_por", "motivo_do_arquivamento"]
    )
    return _uma_ideia(sugestao_id)


@router.post(
    "/gestao/ideias/{sugestao_id}/desarquivar",
    response={200: IdeiaEmGestao, 422: Recusa},
    operation_id="unarchiveIdea",
    summary="Desarquiva a ideia — volta a aparecer para o aluno",
    description=(
        "O inverso de arquivar, e simétrico: a ideia volta ao quadro exatamente "
        "como estava (mesmo status, mesmos votos, mesmo histórico). Recusa 422 "
        "se ela não estiver arquivada."
    ),
)
def desarquivar(request, sugestao_id: int, payload: QuemAge):
    sugestao = _ideia(sugestao_id)
    if sugestao.apagada_em is not None:
        return 422, {
            "erro": "Esta ideia foi apagada definitivamente e não pode ser restaurada."
        }
    if sugestao.arquivada_em is None:
        return 422, {"erro": "Esta ideia não está arquivada."}
    sugestao.arquivada_em = None
    sugestao.arquivada_por = None
    sugestao.motivo_do_arquivamento = ""
    sugestao.save(
        update_fields=["arquivada_em", "arquivada_por", "motivo_do_arquivamento"]
    )
    return _uma_ideia(sugestao_id)


@router.post(
    "/gestao/ideias/{sugestao_id}/apagar",
    response={200: IdeiaEmGestao, 422: Recusa},
    operation_id="deleteIdeaForever",
    summary="Apaga a ideia definitivamente — sem volta, nem para quem criou",
    description=(
        "`DECISAO-apagar-ideia.md` (29/08/2026). Título, texto e solução ficam "
        "vazios, votos e comentários são removidos — para sempre, de qualquer "
        "pessoa que tenha participado, não só do autor. NINGUÉM alcança este "
        "conteúdo de novo, nem pelo link direto, nem esta API. A LINHA "
        "continua existindo no banco (uma ideia apagada também vira "
        "arquivada), porque `HistoricoStatus`/`ChangeSpecAprovado`/`Aviso` são "
        "append-only e apontam para ela — apagar a linha quebraria essa "
        "trava. Recusa 422 se já tiver sido apagada."
    ),
)
def apagar(request, sugestao_id: int, payload: QuemAge):
    sugestao = _ideia(sugestao_id)
    if sugestao.apagada_em is not None:
        return 422, {"erro": "Esta ideia já foi apagada."}
    agora = timezone.now()
    quem = _quem(payload)
    Voto.objects.filter(sugestao=sugestao).delete()
    Comentario.objects.filter(sugestao=sugestao).delete()
    sugestao.titulo = ""
    sugestao.problema = ""
    sugestao.solucao_proposta = ""
    sugestao.apagada_em = agora
    sugestao.apagada_por = quem
    # Apagada é sempre arquivada: nenhuma superfície do aluno ou da gestão
    # precisa aprender um segundo carimbo para saber que isto sumiu — a
    # exclusiva NOVIDADE que `apagada` acrescenta é "não há mais nada para
    # restaurar".
    sugestao.arquivada_em = sugestao.arquivada_em or agora
    sugestao.arquivada_por = sugestao.arquivada_por or quem
    sugestao.save(
        update_fields=[
            "titulo",
            "problema",
            "solucao_proposta",
            "apagada_em",
            "apagada_por",
            "arquivada_em",
            "arquivada_por",
        ]
    )
    return _uma_ideia(sugestao_id)


def _uma_ideia(sugestao_id: int) -> dict:
    """A ideia recém-escrita, relida pela MESMA consulta da leitura.

    Devolver o objeto que acabou de ser gravado seria devolver o que o
    consumidor já sabia; relê-la pela consulta pública é o que faz a resposta
    valer como confirmação — inclusive dos campos derivados (a plateia, o estado
    do corredor) que a escrita não toca diretamente.
    """
    ideia = _ideias_do_quadro(quadro_atual()).filter(pk=sugestao_id).first()
    if ideia is None:
        raise Http404("ideia inexistente")
    return _como_fato(ideia, plateia_de([ideia]))
