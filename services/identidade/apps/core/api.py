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
from ninja import Router, Schema
from ninja.errors import HttpError

from apps.core import sessao as ses

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


def _quem_e(request) -> dict:
    ator = ses.ator_atual(request)
    if ator is None:
        # Visitante. Nada de 401/404: "não entrou ainda" é o estado normal da
        # maioria das requisições do site, e o chamador precisa distinguí-lo
        # de "não consegui perguntar" (que para ele é exceção de rede).
        return {"autenticado": False}
    return {
        "autenticado": True,
        # Id opaco — é ELE que as células guardam em snapshot, nunca o e-mail.
        "id": ator.identidade.id,
        # Pode ser vazio: `nome_exibido` só é gravado na cunhagem. Quem exibe
        # decide o que fazer com vazio.
        "nome_exibido": ator.identidade.nome_exibido,
        "papel": ator.papel,
    }


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
    return _quem_e(request)


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
    resposta = _quem_e(request)
    if resposta["autenticado"]:
        ator = ses.ator_atual(request)
        resposta["email"] = ator.identidade.email
    return resposta
