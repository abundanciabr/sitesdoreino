# apps/core/auth.py
"""Quem CHAMA esta porta, e com que grau. Duas perguntas, não uma.

O molde é `services/gamificacao/apps/core/auth.py` (Lei 3: copia-se o padrão
entre células, nunca se importa código de uma na outra). O que NÃO foi copiado
de lá é a premissa, e a diferença é a razão deste arquivo ter duas funções em
vez de uma.

**A porta da gamificação só LÊ.** Nela, "ter o crachá" e "poder tudo" são a
mesma coisa, porque tudo o que há para fazer é ler nível e título. Um conjunto
plano de tokens está certo lá.

**Esta porta ESCREVE.** `setParameter` grava um parâmetro do dono (o relógio da
oferta, o prazo de produção, o piso de preço) e `confirmPayment` declara que uma
encomenda foi paga. Com um conjunto plano, o par que pediu o token para desenhar
"em que pé está a minha fila" na home ganharia, junto e de graça, o poder de
mudar a régua da fila inteira e de confirmar dinheiro. Ninguém perceberia: o
teste de 401 fica verde, o contrato fica verde, e o modo de falha só aparece no
dia em que alguém usar o poder que ganhou sem pedir (`armadilhas/318`).

Por isso são DOIS conjuntos, os dois fail-closed, declarados em
`config/settings.py`:

    TOKENS_ACEITOS_<PAR>   quem pode LER
    TOKENS_ESCRITA_<PAR>   quem pode GRAVAR

**O grau alto CONTÉM o baixo**, e essa é a única diferença deliberada em relação
ao desenho da `identidade` (`TOKENS_SENHA_*` exige estar TAMBÉM em
`TOKENS_ACEITOS_*`). Lá isso produz um dia perdido: o mantenedor põe no env só a
variável de escrita, a leitura devolve 401, nada falha e nada explica. Aqui uma
linha apaga esse dia.

**A recusa de escrita é 403, e nunca 401.** São frases diferentes: 401 diz *"não
sei quem você é"* e manda o par conferir um token que está certo; 403 diz *"sei
quem você é, e este par não tem esse grau"*, que é a verdade e é acionável.

Guardas: `tests/test_porta_de_maquina.py` — 401 em todas as operações, 401 com o
env ausente, e 403 do par que só lê em cada uma das três operações que gravam.
"""

from __future__ import annotations

from django.conf import settings
from ninja.errors import HttpError
from ninja.security import HttpBearer


class bearerAuth(HttpBearer):
    """Aceita os tokens dos DOIS graus. Nome em minúsculas de propósito.

    O django-ninja usa o nome da classe do callback de auth como chave de
    `components.securitySchemes`, e o freeze de contrato desta casa exige que ela
    seja `bearerAuth` — como nas dez portas que já congelaram.

    **Este token responde "quem chama", e nada além disso.** Ele não diz quem é a
    pessoa do outro lado do navegador, e nesta porta nem existe pessoa: nenhum
    cookie chega aqui. Quem responde "quem é a pessoa" é `apps/core/sessao.py`,
    no caminho das TELAS, repassando o cookie à `identidade` sem nunca assiná-lo.
    """

    def authenticate(self, request, token: str):
        if token in settings.TOKENS_ACEITOS or token in settings.TOKENS_ESCRITA:
            return token
        return None


def exigir_grau_de_escrita(request) -> None:
    """Recusa com 403 o par que tem crachá de leitura e pediu para gravar.

    Chamada na PRIMEIRA linha de toda operação que muda alguma coisa, antes de
    qualquer leitura de banco e antes do 501 das portas que ainda não operam: um
    par que não pode escrever não deve nem descobrir se a encomenda existe.
    """
    if request.auth not in settings.TOKENS_ESCRITA:
        raise HttpError(
            403,
            "este par tem o grau de leitura desta celula, e nao o de escrita. "
            "Quem grava parametro, confirma pagamento ou registra auditoria "
            "precisa estar em TOKENS_ESCRITA_<PAR> no env da encomendas.",
        )
