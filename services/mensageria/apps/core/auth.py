# apps/core/auth.py  # [RECEITA:R1 v1]
from django.conf import settings
from ninja.security import HttpBearer


def tokens_de_leitura() -> set[str]:
    """Quem pode LER pela porta de máquina, e nada além de ler.

    Lido no ponto de uso, nunca guardado num módulo: `settings` é sobrescrito
    por teste e a leitura antecipada congelaria o conjunto do primeiro import.
    """
    return set(getattr(settings, "TOKENS_SOMENTE_LEITURA", set()) or set())


def tokens_de_publicacao() -> set[str]:
    """Quem pode PUBLICAR uma versão nova, o grau a mais."""
    return set(getattr(settings, "TOKENS_PUBLICACAO", set()) or set())


class bearerAuth(HttpBearer):
    """Aceita os tokens estáticos do PAR consumidor, nos dois graus desta porta.

    Cópia do PADRÃO de `identidade`/`forum`/`gamificacao` (Lei 3: copia-se o
    padrão entre células, nunca se importa código de uma na outra). Nome da
    classe em minúsculas de propósito: o freeze de contrato exige que a chave de
    `components.securitySchemes` seja `bearerAuth`, e o django-ninja usa o nome
    da classe do callback de auth como chave do security scheme.

    **Este token responde "QUEM CHAMA", e nada além disso.** Ele prova que o
    chamador é uma célula da casa. Esta porta não tem sessão de pessoa e não
    resolve visitante nenhum: quem fala com ela é máquina, sempre.

    POR QUE SÃO DOIS CONJUNTOS, E NÃO UM
    ------------------------------------
    Um conjunto só (`TOKENS_ACEITOS_*`, como fazem as células que só leem) é
    plano: quem entra, entra inteiro. E esta porta tem uma operação que
    PUBLICA VERSÃO NOVA de uma sequência que vai escrever para alunos de
    verdade. Conjunto plano concederia essa escrita a qualquer par que só
    precisasse desenhar uma tela de consulta.

    A `identidade` já resolveu isto antes, com `TOKENS_SENHA_*`: gravar a senha
    de alguém é mais que perguntar quem alguém é, então é um grau PRÓPRIO. Aqui
    a divisão é a mesma, com um detalhe diferente e deliberado:

    - `TOKENS_SOMENTE_LEITURA_<PAR>` faz o que o nome diz. Quem está só nele
      lê as cinco leituras e leva **403** ao tentar publicar.
    - `TOKENS_PUBLICACAO_<PAR>` é o grau a mais, e **já contém a leitura**. Não
      é preciso pôr o mesmo par nos dois envs, e essa é a diferença em relação
      à `identidade`: lá o par precisa estar nos dois. O modo de falha que isto
      mata é chato e silencioso — o mantenedor põe o token de publicação no env,
      a tela lê tudo certo, e a primeira tentativa de salvar uma frase devolve
      403 sem que nada esteja errado no código.

    Os DOIS nascem VAZIOS quando o env falta, e conjunto vazio recusa todo
    mundo com 401. Fail-closed por construção, e sem derrubar o boot: a célula
    sobe, o `/healthz` responde, o motor das jornadas segue rodando, e só a
    porta de máquina fica fechada até o token existir no env.
    """

    def authenticate(self, request, token: str):
        if token in tokens_de_leitura() or token in tokens_de_publicacao():
            return token
        return None
