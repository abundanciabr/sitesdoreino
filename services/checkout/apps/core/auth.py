# apps/core/auth.py  # [RECEITA:R1 v1]
from django.conf import settings
from ninja.errors import HttpError
from ninja.security import HttpBearer

# O que um token PÚBLICO alcança, escrito por extenso e em lugar nenhum mais,
# com os operation_id do contrato congelado. São exatamente as três coisas que
# a página já faz em nome do visitante anônimo: abrir a sessão, fechar o pedido
# e ler o status dele. Operação fora desta lista responde 403 ao token público,
# inclusive a que ainda não existe — quem acrescentar uma rota nova à API
# acrescenta alcance por decisão escrita, nunca por descuido
# (docs/consultorias/equipe-especialista/DIAGNOSTICO-TAR-458-bearer-do-checkout.md).
ALCANCE_DO_TOKEN_PUBLICO = frozenset({"createSession", "placeOrder", "getOrder"})


def _operacao_pedida(request) -> str | None:
    """O operation_id da rota que vai atender esta requisição.

    Sai do casamento de URL que o Django já fez antes de chamar a view
    (`resolver_match`): a view de uma rota django-ninja é um método da
    `PathView` daquele caminho, que guarda as operações dele. Devolve None
    quando não dá para saber, e quem chama trata None como negativa.
    """
    casamento = getattr(request, "resolver_match", None)
    caminho = getattr(getattr(casamento, "func", None), "__self__", None)
    for operacao in getattr(caminho, "operations", ()):
        if request.method in operacao.methods:
            return operacao.operation_id
    return None


class bearerAuth(HttpBearer):
    """Aceita os tokens estáticos de TOKENS_ACEITOS_* — um por par consumidor.

    Nome da classe em minúsculas de propósito: o freeze de contrato exige que a
    chave de components.securitySchemes exportada seja "bearerAuth" (django-ninja
    usa o nome da classe do callback de auth como chave do security scheme).

    **Dois graus**, no padrão que `identidade` já usa (copia-se o PADRÃO, nunca
    o arquivo por import cruzado): `TOKENS_ACEITOS_*` responde QUEM CHAMA, e
    `TOKENS_PUBLICOS` diz qual desses chamadores é um segredo que a própria
    célula publica no HTML das páginas. Esse segundo grau é conferido AQUI, e
    não no handler como em `identidade`, porque o modo de falha que ele existe
    para fechar é a ROTA NOVA: um degrau que dependesse de o autor da rota nova
    lembrar de escrevê-lo deixaria essa rota nascer alcançável por qualquer
    visitante, sem ninguém errar. Nenhum securityScheme novo entra no contrato
    congelado por causa disto (um 403 nomeado diz melhor), e as três operações
    de hoje continuam respondendo o mesmo ao comprador.

    Dúvida é negativa: se não dá para identificar a operação pedida, o token
    público é recusado.
    """

    def authenticate(self, request, token: str):
        if token not in settings.TOKENS_ACEITOS:
            return None
        if (
            token in settings.TOKENS_PUBLICOS
            and _operacao_pedida(request) not in ALCANCE_DO_TOKEN_PUBLICO
        ):
            raise HttpError(
                403,
                "este token é público (a própria página o publica no HTML) e "
                "não alcança esta operação; use o token servidor a servidor do "
                "par consumidor que chama esta rota",
            )
        return token
