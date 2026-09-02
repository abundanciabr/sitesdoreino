# apps/core/api.py  # [RECEITA:R1 v1]
"""A superfície de máquina desta célula: "quem é o dono desta sessão?".

Lei do assunto: `docs/decisoes/DECISAO-celula-de-identidade.md`, que herda o
desenho da `DECISAO-onde-mora-a-sessao` trocando QUEM responde — exatamente a
troca que aquela decisão previu. O `funil` (e qualquer célula) pergunta; esta
célula responde.

**Duas perguntas se cruzam nestes endpoints, e elas têm respostas diferentes:**

| Pergunta | Prova | Falha vira |
|---|---|---|
| quem está CHAMANDO? | Bearer do par (`apps/core/auth.py`) | **401** |
| quem é a PESSOA? | cookie de sessão repassado pelo chamador | **200 com `autenticado: false`** |

Confundir as duas é o erro caro: um 401 para visitante anônimo faria o
consumidor tratar "ninguém entrou ainda" como "recusaram minha credencial", e
a primeira coisa que alguém faria para "consertar" seria afrouxar o token.

**O e-mail tem DOIS regimes, e a diferença é o endpoint:**

- `/sessao` NUNCA o devolve — é a resposta de EXIBIÇÃO, para quem só precisa
  de um nome no canto da página (o `funil`). Guarda mecânico:
  `tests/test_inv_sessao_nao_vaza_email.py`.
- `/sessao/completa` o devolve, e SÓ a par que esteja também em
  `TOKENS_COMPLETOS_*` (403 para os demais) — é a resposta de AUTORIZAÇÃO
  local, para a célula que precisa do e-mail para conferir as listas DELA
  (a Caixa: matrícula e staff). O 403 protege o dado pessoal que a EVO-01 §3
  concentrou numa linha só.

**O papel é DERIVADO na hora** (`apps/core/sessao.py`), da lista de e-mails do
env a cada requisição. E vale o INVARIANTE da DECISAO-onde-mora-a-sessao §4:
**reconhecer não é autorizar** — quem usar este `papel` para liberar rota está
usando a ferramenta errada; a autorização mora, fail-closed, na célula dona do
recurso, sobre as listas e regras DELA.
"""

from django.conf import settings
from django.contrib.auth.hashers import make_password
from ninja import Router, Schema
from ninja.errors import HttpError

from apps.core import sessao as ses
from apps.core import tokens_de_entrada as tokens
from apps.identidade.models import Identidade

router = Router()


# A DOCSTRING desta classe vai INTEIRA para dentro do contrato congelado
# (`description` do schema, via export_openapi) — por isso ela é uma linha só.
#
# **O nome desta classe é o nome do schema NO CONTRATO CONGELADO** — o
# `$ref: '#/components/schemas/Session'`. É o MESMO nome (e a mesma forma) que
# o contrato da Caixa congelou em `contracts/sugestoes.openapi.yaml`: o
# consumidor troca o endereço, não o vocabulário.
#
# **CUIDADO ao editar este arquivo** (`armadilhas/020`): `Session` é um nome
# comum no Django. Um `ninja.Schema` com o mesmo nome de algo importado aqui
# sombreia o import em SILÊNCIO. Hoje é seguro: `django.contrib.sessions` nem
# está em INSTALLED_APPS, e o módulo de sessão entra como `ses`.
#
# **Os três campos de identificação são opcionais** porque visitante é uma
# resposta legítima: sem sessão só `autenticado: false` viaja (`exclude_none`).
class Session(Schema):
    """Quem é o dono da sessão; sem sessão, só `autenticado: false`."""

    autenticado: bool
    id: "str | None" = None
    nome_exibido: "str | None" = None
    papel: "str | None" = None


# A resposta COMPLETA: os mesmos campos, mais o e-mail. Schema separado (e não
# um parâmetro em /sessao) porque a fronteira precisa ser visível no contrato:
# qual operação expõe dado pessoal não pode depender de flag em query string.
class SessionFull(Schema):
    """Como Session, com o e-mail — só para par autorizado em TOKENS_COMPLETOS."""

    autenticado: bool
    id: "str | None" = None
    nome_exibido: "str | None" = None
    papel: "str | None" = None
    email: "str | None" = None


# [POR-EMAIL] O corpo e a resposta de `POST /pessoas/por-email` (29/08/2026,
# `DECISAO-cadastrar-alguem-a-mao` não; a lei aqui é o Rito de Contrato do
# aviso de liberação). Schemas próprios, e não reuso de `Session`: a pergunta é
# outra — não há sessão nenhuma envolvida —, e um schema compartilhado faria o
# contrato sugerir um parentesco que não existe.
class EmailPedido(Schema):
    """O e-mail de quem se procura. Comparado em minúsculas, sem espaços."""

    email: str


class PessoaPorEmail(Schema):
    """O id opaco de quem tem aquele e-mail, ou `null` — nunca o e-mail de volta."""

    id: "str | None" = None


# [POR-ID] O corpo e a resposta de `POST /pessoas/por-id` (Rito de Contrato de
# 02/09/2026, degrau 1 do e-mail de verdade). A INVERSA da de cima, e existe
# pelo motivo oposto: uma célula que conhece as pessoas por ID precisa entregar
# uma carta FORA do site, e correio eletrônico se endereça por e-mail.
class IdPedido(Schema):
    """O id de plataforma de quem se procura — o mesmo `id` que getSession devolve."""

    id: str


class PessoaParaEnvio(Schema):
    """O necessário e suficiente para endereçar uma carta: para onde ela vai e em que língua é escrita. Nunca o nome, nunca o papel — quem manda um aviso automático não precisa deles, e cada campo a mais aqui é um campo a mais vazando por um par de tokens."""

    email: "str | None" = None
    idioma: "str | None" = None


# [LOGIN-POR-SENHA] Os schemas de `DECISAO-login-por-senha.md` (31/08/2026).
class TokenDeEntrada(Schema):
    """O token efêmero a embutir no POST de /entrar/senha. Opaco para quem o recebe."""

    token: str


class DefinirSenhaPedido(Schema):
    """O e-mail e a senha em texto puro (transporte é HTTPS interno, nunca fica em log — o hash nasce do lado da identidade, nunca do lado de quem chama). nome/site_id/idioma só valem na primeira vez (cunhagem); numa Identidade que já existe, são ignorados.
    `idioma` é a língua em que a pessoa se cadastrou, e é a ÚNICA vez que a plataforma tem essa informação de graça: ela vem do endereço que a pessoa estava navegando (`/es/cadastro`) e some quando a página fecha. Quem não o envia deixa a pessoa sem língua declarada, e findPersonById devolverá `idioma: null` para ela — resposta legítima, não erro.
    """

    email: str
    senha: str
    nome: "str | None" = None
    site_id: "str | None" = None
    idioma: "str | None" = None


class PessoaComSenha(Schema):
    """Confirma que a senha foi gravada. Nunca ecoa a senha nem o hash."""

    id: str
    criada: bool


class PessoaComSenhaNova(Schema):
    """A senha nova, em texto puro, para o mantenedor repassar por fora (WhatsApp). Sai UMA vez nesta resposta; a célula não a grava em lugar nenhum além do hash."""

    id: str
    senha_nova: str


def _quem_e(request) -> "tuple[dict, object | None]":
    """A resposta de exibição E o ator que a produziu.

    Devolve o PAR de propósito: `/sessao/completa` precisa do e-mail, que
    mora no `Ator`. Antes esta função descartava o objeto e o handler
    chamava `ator_atual` de novo — dois SELECT por resposta completa, no
    caminho de TODA página da Caixa (auditoria de 25/08/2026).
    """
    ator = ses.ator_atual(request)
    if ator is None:
        # Visitante. Nada de 401/404: "não entrou ainda" é o estado normal da
        # maioria das requisições do site, e o chamador precisa distinguí-lo
        # de "não consegui perguntar" (que para ele é exceção de rede).
        return {"autenticado": False}, None
    return {
        "autenticado": True,
        # Id opaco — é ELE que as células guardam em snapshot, nunca o e-mail.
        "id": ator.identidade.id,
        # Pode ser vazio: `nome_exibido` só é gravado na cunhagem. Quem exibe
        # decide o que fazer com vazio.
        "nome_exibido": ator.identidade.nome_exibido,
        "papel": ator.papel,
    }, ator


@router.get(
    "/sessao",
    response=Session,
    exclude_none=True,
    # Sem isto o django-ninja deriva o `operationId` do caminho do MÓDULO —
    # estrutura interna do código vazando para dentro de um arquivo congelado.
    # O nome segue a convenção dos contratos da casa: camelCase, verbo inglês.
    operation_id="getSession",
    summary="Quem é o dono da sessão desta requisição",
    description=(
        "Resolve o cookie de sessão repassado pelo chamador. Responde 200 "
        "sempre que o chamador estiver autorizado: `autenticado: false` "
        "significa que não há sessão (visitante), e NÃO é um erro. O e-mail "
        "nunca é devolvido."
    ),
)
def sessao_atual(request):
    resposta, _ = _quem_e(request)
    return resposta


@router.get(
    "/sessao/completa",
    response=SessionFull,
    exclude_none=True,
    operation_id="getSessionFull",
    summary="Quem é o dono da sessão, com e-mail — par autorizado apenas",
    description=(
        "Como getSession, acrescentando o e-mail — o dado que uma célula dona "
        "de recurso precisa para conferir as PRÓPRIAS listas (matrícula, "
        "staff). Exige que o token do par esteja também em TOKENS_COMPLETOS_*; "
        "sem esse degrau a resposta é 403, mesmo com Bearer válido."
    ),
)
def sessao_completa(request):
    # O degrau a mais é conferido AQUI, no handler, contra request.auth (o
    # token que o bearerAuth validou): dois security schemes no contrato
    # dobrariam a superfície congelada por algo que um 403 nomeado diz melhor.
    # Conjunto vazio ⇒ 403 para todo mundo — fail-closed por construção.
    if request.auth not in settings.TOKENS_COMPLETOS:
        raise HttpError(403, "este par não está autorizado à resposta completa")
    resposta, ator = _quem_e(request)
    if ator is not None:
        # O MESMO objeto que `_quem_e` já resolveu — nunca um SELECT novo.
        resposta["email"] = ator.identidade.email
    return resposta


@router.post(
    "/pessoas/por-email",
    response=PessoaPorEmail,
    operation_id="findPersonByEmail",
    summary="Qual o id de plataforma de quem tem este e-mail",
    description=(
        "Traduz um e-mail no id OPACO da pessoa — o mesmo `id` que getSession "
        "devolve. Existe por uma razão só: uma célula que conhece as pessoas "
        "por E-MAIL precisa endereçar uma carta para a caixa de avisos, que "
        "entrega por ID DE PLATAFORMA. POST e não GET com o e-mail no caminho: "
        "caminho de URL entra em log de servidor, em histórico de proxy e em "
        "rastro de erro; corpo, não. Entra e-mail, sai id — esta porta nunca "
        "devolve e-mail nem nome. Exige TOKENS_COMPLETOS_*, o mesmo degrau de "
        "getSessionFull, porque quem manda um e-mail para ela descobre se ele "
        "existe. `id: null` é RESPOSTA, não erro."
    ),
)
def pessoa_por_email(request, corpo: EmailPedido):
    """O id de quem tem este e-mail, ou `None` — a tradução que faltava.

    **O mesmo degrau de `/sessao/completa`, e pelo mesmo motivo.** Aquele
    DEVOLVE um e-mail; este RECEBE um e diz se ele existe. As duas coisas são
    informação sobre uma pessoa, e a segunda permite enumerar: um par com
    Bearer válido, mas sem o degrau, poderia varrer endereços e descobrir quem
    tem conta. Conjunto vazio ⇒ 403 para todo mundo — fail-closed por
    construção, igual ao vizinho.

    **A normalização mora AQUI, e não em quem chama.** O e-mail é gravado como
    o Google o entrega, e cada célula que precisasse procurar por ele teria de
    repetir a mesma regra — a primeira que esquecesse devolveria `null` para
    uma pessoa que existe, e o efeito seria um aviso que nunca chega, sem erro
    nenhum no caminho. Quem é dono do dado é dono da forma canônica dele.

    **Nunca 404.** "Não conheço esta pessoa" é uma resposta legítima e comum —
    quem foi cadastrado à mão pelo painel e ainda não entrou com o Google não
    tem identidade nenhuma aqui. Um 404 obrigaria quem chama a traduzir uma
    exceção de rede em "não existe", que é exatamente onde um erro de verdade
    passaria despercebido.
    """
    if request.auth not in settings.TOKENS_COMPLETOS:
        raise HttpError(403, "este par não está autorizado a procurar por e-mail")

    email = (corpo.email or "").strip().lower()
    if not email:
        # 422 e não `id: null`: pedido sem e-mail é desacordo de quem chama com
        # o contrato, e responder "não conheço" a uma pergunta que não foi feita
        # esconderia o defeito de quem escreveu o código.
        raise HttpError(422, "email é obrigatório")

    achada = Identidade.objects.filter(email=email).values_list("id", flat=True).first()
    return {"id": achada}


@router.post(
    "/pessoas/por-id",
    response=PessoaParaEnvio,
    operation_id="findPersonById",
    summary="Para onde escrever a esta pessoa, e em que lingua",
    description=(
        "A INVERSA de findPersonByEmail, e existe pelo motivo oposto: uma "
        "celula que conhece as pessoas por ID DE PLATAFORMA precisa entregar "
        "uma carta FORA do site, e correio eletronico se enderecca por e-mail. "
        "A `mensageria` a chama NO INSTANTE DO ENVIO, nunca no da inscricao — "
        "guardar o e-mail do outro lado criaria uma segunda casa do dado que "
        "ninguem mantem quando a pessoa o troca, e gravar o idioma na inscricao "
        "congelaria a lingua de quem se inscreveu "
        "(PLANO-SEQUENCIAS-DE-MENSAGENS §4.3). POST e nao GET pelo mesmo motivo "
        "da irma: caminho de URL entra em log de servidor e em rastro de erro; "
        "corpo, nao. Exige TOKENS_COMPLETOS_*, o degrau alto, porque esta porta "
        "DEVOLVE dado pessoal — e por isso ela devolve o minimo que uma carta "
        "precisa: para onde ir e em que lingua ser escrita, nunca o nome nem o "
        "papel. `email: null` e RESPOSTA (id que nao existe), nao erro. "
        '`idioma: null` tambem e resposta, e quer dizer "esta pessoa nunca '
        'declarou lingua" — quem escreve a carta decide o padrao, porque so '
        "ele sabe em que linguas sabe escrever."
    ),
)
def pessoa_por_id(request, corpo: IdPedido):
    """Para onde escrever a esta pessoa, e em que língua — nada além disso.

    **O degrau alto, e por um motivo mais forte que o da irmã.** Aquela RECEBE
    um e-mail e diz se existe; esta DEVOLVE o e-mail. Um par com Bearer válido
    mas sem `TOKENS_COMPLETOS_*` poderia varrer ids e colher a caixa de entrada
    de toda a escola. Conjunto vazio ⇒ 403 para todo mundo — fail-closed por
    construção, igual aos vizinhos.

    **Nunca 404, e nunca `{}` mudo.** "Não conheço este id" é resposta legítima:
    a `mensageria` guarda o id numa inscrição que pode sobreviver à pessoa que a
    apagou. `email: None` diz isso sem obrigar quem chama a traduzir uma exceção
    de rede em "não existe" — que é exatamente onde um erro de verdade passaria
    despercebido.

    **`idioma` vazio vira `None` na resposta, e a diferença é do contrato.** No
    banco a ausência é string vazia (convenção do Django para texto); no fio ela
    é `null`, porque `""` é um idioma que não existe e quem lesse sem cuidado
    tentaria renderizar nele. Traduzir na borda é o lugar certo: o modelo guarda
    do jeito do Django, o contrato fala do jeito do contrato.
    """
    if request.auth not in settings.TOKENS_COMPLETOS:
        raise HttpError(403, "este par não está autorizado a procurar por id")

    id_pedido = (corpo.id or "").strip()
    if not id_pedido:
        # 422 e não `email: null`, pelo mesmo motivo da irmã: pedido sem id é
        # desacordo de quem chama com o contrato, e responder "não conheço" a
        # uma pergunta que não foi feita esconderia o defeito de quem o escreveu.
        raise HttpError(422, "id é obrigatório")

    achada = Identidade.objects.filter(id=id_pedido).values("email", "idioma").first()
    if achada is None:
        return {"email": None, "idioma": None}
    return {"email": achada["email"], "idioma": achada["idioma"] or None}


@router.post(
    "/tokens-de-entrada",
    response=TokenDeEntrada,
    operation_id="issueLoginToken",
    summary="Um token efêmero para provar, no POST de /entrar/senha, que o pedido veio do site",
    description=(
        "Login por senha (DECISAO-login-por-senha.md) é um POST que CRIA "
        "sessão — ao contrário de /entrar/sair, que só destrói, o padrão de "
        "origem (Origin/Referer) não basta aqui (LICOES.md da célula já "
        "registra isso por escrito). Como quem RENDERIZA o formulário de "
        "senha é o `funil`, não esta célula, e um CSRF token do funil nunca "
        "validaria aqui (segredos diferentes), a prova é este token assinado "
        "(TimestampSigner, expira em minutos) — o mesmo princípio do `state` "
        "que o fluxo do Google já usa, só que emitido para outra célula em "
        "vez de guardado na própria sessão. Qualquer par aceito pode pedir; "
        'o token não carrega e-mail nem senha nenhuma, só prova "isto foi '
        'pedido a este site, agora".'
    ),
)
def emitir_token_de_entrada(request):
    return {"token": tokens.emitir()}


@router.post(
    "/pessoas/definir-senha",
    response=PessoaComSenha,
    operation_id="setPassword",
    summary="Cria ou atualiza a senha de uma pessoa (cadastro sem conta do Google)",
    description=(
        "Upsert por e-mail — mesma forma de cunhar_ou_recuperar (o caminho "
        "do Google): se a Identidade não existir, nasce aqui; se existir, "
        "só a senha é atualizada. `criada: true` só na primeira vez, mesma "
        "semântica do resto da célula. Exige o grau TOKENS_SENHA_* além do "
        'par aceito — gravar senha alheia é mais que "perguntar quem é '
        'alguém", e por isso não reusa TOKENS_COMPLETOS_* (esse grau é '
        "sobre LER e-mail, não sobre ESCREVER senha)."
    ),
)
def definir_senha(request, corpo: DefinirSenhaPedido):
    if request.auth not in settings.TOKENS_SENHA:
        raise HttpError(403, "este par não está autorizado a definir senha")

    email = (corpo.email or "").strip().lower()
    if not email or not corpo.senha:
        raise HttpError(422, "email e senha são obrigatórios")

    identidade, criada = ses.definir_senha(
        email=email,
        senha=corpo.senha,
        nome=corpo.nome or "",
        site_id=corpo.site_id or "",
        idioma=corpo.idioma or "",
    )
    return {"id": identidade.id, "criada": criada}


@router.post(
    "/pessoas/resetar-senha",
    response=PessoaComSenhaNova,
    operation_id="resetPassword",
    summary="Gera uma senha nova para um e-mail que já existe, e a devolve em texto puro UMA vez",
    description=(
        "Para o caminho de recuperação manual (DECISAO-login-por-senha.md "
        "§1): o mantenedor confirma quem é a pessoa pelo WhatsApp que ela "
        "já deixou no cadastro, aciona esta porta pelo admin, e repassa a "
        "senha nova por fora — esta célula nunca manda mensagem nenhuma. A "
        "senha em texto puro sai UMA vez nesta resposta e não é gravada em "
        "lugar nenhum (só o hash fica). 404 se o e-mail não tiver Identidade "
        "nenhuma (nada a resetar). Mesmo grau de setPassword."
    ),
)
def resetar_senha(request, corpo: EmailPedido):
    if request.auth not in settings.TOKENS_SENHA:
        raise HttpError(403, "este par não está autorizado a resetar senha")

    email = (corpo.email or "").strip().lower()
    if not email:
        raise HttpError(422, "email é obrigatório")

    identidade = Identidade.objects.filter(email=email).first()
    if identidade is None:
        raise HttpError(404, "nenhuma identidade com este e-mail")

    senha_nova = ses.gerar_senha_aleatoria()
    identidade.senha_hash = make_password(senha_nova)
    identidade.save(update_fields=["senha_hash"])
    return {"id": identidade.id, "senha_nova": senha_nova}
