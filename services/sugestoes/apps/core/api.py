# apps/core/api.py  # [RECEITA:R1 v1]
"""A única superfície de máquina desta célula — DEPRECADA E INERTE desde 25/08/2026.

O dia que a `DECISAO-onde-mora-a-sessao` previu chegou: a identidade mudou de
casa (`DECISAO-celula-de-identidade`), e quem responde "quem é o dono desta
sessão?" ao site inteiro é a célula `identidade` — pelo MESMO vocabulário
(`getSession`/`Session`) que nasceu aqui. Esta operação continua existindo
porque o contrato dela está CONGELADO e contrato só muda pelo Rito §3 (a
remoção é dívida registrada); mas ela responde pela sessão LEGADA — o cookie
que esta célula assinava — e nenhum cookie novo é assinado por ela desde a
virada. Na prática, a resposta real é sempre `autenticado: false`.

**Duas perguntas se cruzam neste endpoint, e elas têm respostas diferentes:**

| Pergunta | Prova | Falha vira |
|---|---|---|
| quem está CHAMANDO? | Bearer do par (`apps/core/auth.py`) | **401** |
| quem é a PESSOA? | cookie de sessão repassado pelo chamador | **200 com `autenticado: false`** |

Confundir as duas é o erro caro: um 401 para visitante anônimo faria o `funil`
tratar "ninguém entrou ainda" como "a Caixa recusou a minha credencial", e a
primeira coisa que alguém faria para "consertar" seria afrouxar o token. Por
isso visitante anônimo é uma resposta **de sucesso** que diz "ninguém".

**O e-mail NUNCA sai daqui.** `Identidade.email` é o dado pessoal que a
EVO-01 §3 concentrou numa linha só; devolvê-lo ao `funil` o espalharia para uma
célula que não precisa dele para nada — ela quer um nome para escrever no canto
da página. Há guarda mecânico (`tests/test_inv_sessao_nao_vaza_email.py`).

**O papel é DERIVADO na hora**, como em toda leitura de sessão desta célula
(`apps/core/sessao.py`): sai da lista de e-mails do env a cada requisição.
Papel gravado no cookie ou na linha da `Identidade` quebraria a promessa da
EVO-01 §4 — tirar alguém da lista não tiraria o crachá de quem já estava
dentro. E vale o INVARIANTE da decisão §4: **reconhecer não é autorizar** —
quem usar este `papel` para liberar rota está usando a ferramenta errada; a
autorização mora, fail-closed, na célula dona do recurso.
"""

from ninja import Router, Schema

from apps.core import sessao as ses

router = Router()


# A DOCSTRING desta classe vai INTEIRA para dentro do contrato congelado
# (`description` do schema, via export_openapi) — por isso ela é uma linha só, e
# o porquê mora aqui em comentário, que o exportador não enxerga. Docstring
# longa aqui vira ruído permanente num arquivo que é lei e que se compara byte a
# byte no freeze.
#
# **Tipada, e não `dict` solto:** um contrato que diz apenas "um objeto" não é
# contrato — é permissão para o formato mudar sem ninguém reprovar.
#
# **O nome desta classe é o nome do schema NO CONTRATO CONGELADO** — o
# `$ref: '#/components/schemas/Session'`. Por isso ele segue o vocabulário dos
# contratos da casa (`Site`, `Product`, `Offer`, `Order`, `Intent`: inglês,
# singular), e não o do código, que é português. Renomear depois custa um Rito
# de Contrato inteiro (RITOS §3), então nasce certo.
#
# **CUIDADO ao editar este arquivo** (`armadilhas/020`): `Session` é um nome
# comum no Django. Um `ninja.Schema` com o mesmo nome de algo importado aqui
# sombreia o import em SILÊNCIO — sem erro de import, sem aviso do lint, e o
# estouro só aparece rodando os testes, vindo de dentro do pydantic. Hoje é
# seguro: `django.contrib.sessions` nem está em INSTALLED_APPS (a sessão desta
# célula é cookie assinado, sem model), e o módulo de sessão entra como `ses`.
# Se um dia alguém precisar do model `Session` aqui, importe com alias.
#
# **Os três campos de identificação são opcionais** porque visitante é uma
# resposta legítima: sem sessão só `autenticado: false` viaja (`exclude_none`),
# e o consumidor lê um corpo curto em vez de três `null` para saber ignorar.
class Session(Schema):
    """Quem é o dono da sessão; sem sessão, só `autenticado: false`."""

    autenticado: bool
    id: "str | None" = None
    nome_exibido: "str | None" = None
    papel: "str | None" = None


@router.get(
    "/sessao",
    response=Session,
    exclude_none=True,
    # Sem isto o django-ninja deriva o `operationId` do caminho do MÓDULO
    # (`apps_core_api_sessao_atual`) — estrutura interna do código vazando para
    # dentro de um arquivo congelado, que é a fronteira pública desta célula.
    # O nome segue a convenção dos contratos da casa: `getOrder`, `getOffer`,
    # `getIntent`, `listEnrollments` — camelCase, verbo em inglês.
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
    # O leitor LEGADO, de propósito — nunca `ator_atual`, que hoje resolve
    # pela célula `identidade`: encaminhar a pergunta de volta para quem já é
    # o dono dela seria um ricochete de rede fingindo ser resposta. Este
    # endpoint responde SÓ pelo cookie que esta célula assinava (ver o
    # docstring do módulo e `sessao.ator_da_sessao_legada`).
    ator = ses.ator_da_sessao_legada(request)
    if ator is None:
        # Visitante. Nada de 401/404: "não entrou ainda" é o estado normal da
        # maioria das requisições do site, e o chamador precisa distinguí-lo de
        # "não consegui perguntar" (que para ele é exceção de rede, não uma
        # resposta desta função).
        return {"autenticado": False}
    return {
        "autenticado": True,
        # Id opaco, o mesmo que sugestões, votos e comentários já apontam.
        "id": ator.identidade.id,
        # Pode ser vazio: `nome_exibido` é editável pela pessoa e só é gravado
        # na cunhagem. Quem exibe decide o que fazer com vazio — não é papel
        # desta célula inventar um apelido para o site mostrar.
        "nome_exibido": ator.identidade.nome_exibido,
        "papel": ator.papel,
    }
