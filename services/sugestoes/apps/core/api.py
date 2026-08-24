# apps/core/api.py  # [RECEITA:R1 v1]
"""A única superfície de máquina desta célula: "quem é o dono desta sessão?".

Lei do assunto: `docs/decisoes/DECISAO-onde-mora-a-sessao.md`. A Caixa continua
sendo dona da identidade e da sessão; o que nasce aqui é a **pergunta** que
torna a sessão útil ao site inteiro — o `funil` pergunta, esta célula responde,
e no dia em que a identidade mudar de casa muda **quem responde**, não quem
pergunta.

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
# **Sufixo `Resposta` de propósito** (`armadilhas/020`): um `ninja.Schema` com o
# mesmo nome de algo importado no arquivo sombreia o import em silêncio, e o
# erro só aparece rodando os testes, nunca no lint. Aqui não há model nem módulo
# chamado `SessaoResposta`.
#
# **Os três campos de identificação são opcionais** porque visitante é uma
# resposta legítima: sem sessão só `autenticado: false` viaja (`exclude_none`),
# e o consumidor lê um corpo curto em vez de três `null` para saber ignorar.
class SessaoResposta(Schema):
    """Quem é o dono da sessão; sem sessão, só `autenticado: false`."""

    autenticado: bool
    id: "str | None" = None
    nome_exibido: "str | None" = None
    papel: "str | None" = None


@router.get(
    "/sessao",
    response=SessaoResposta,
    exclude_none=True,
    summary="Quem é o dono da sessão desta requisição",
    description=(
        "Resolve o cookie de sessão repassado pelo chamador. Responde 200 "
        "sempre que o chamador estiver autorizado: `autenticado: false` "
        "significa que não há sessão (visitante), e NÃO é um erro. O e-mail "
        "nunca é devolvido."
    ),
)
def sessao_atual(request):
    ator = ses.ator_atual(request)
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
