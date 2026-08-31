"""O envio do aviso para a tela do aparelho — o único lugar desta célula que
fala com um servidor de fora.

**A promessa deste arquivo, e ela é modesta de propósito: a carta gravada é a
verdade durável; o push é o espelho dela.** Se o envio falhar, a pessoa continua
com o aviso na caixa e o vê no sininho da próxima vez que abrir o site. É por
isso que TODA falha aqui é falha ABERTA: um servidor de push fora do ar, uma
chave ausente ou um aparelho que sumiu não podem derrubar o consumidor do fio
nem impedir a carta seguinte de ser gravada.

**Sem chave VAPID, esta célula não envia e DIZ isso no log.** Ela não finge que
enviou. A chave é segredo do servidor (`VAPID_PRIVATE_KEY`), e enquanto o
mantenedor não a instalar, o canal simplesmente não existe: o resto da caixa
funciona igual, e o log conta a verdade uma vez por processo, não uma vez por
carta (um aviso por carta viraria ruído que ninguém lê).

**O conteúdo vai CIFRADO de ponta a ponta**, com as chaves do próprio aparelho:
o fabricante (Google, Apple, Mozilla) entrega a mensagem sem conseguir lê-la.
E o que viaja é DADO, nunca frase pronta (`DECISAO-notificacoes` §5.1): assunto
e parâmetros. A frase nasce no aparelho, no idioma de quem lê.
"""

import json
import logging

from django.conf import settings

logger = logging.getLogger("notificacoes.push")

# Um aviso por processo, não um por carta: sem esta memória, uma plataforma sem
# chave configurada encheria o log com a mesma linha a cada carta que chegasse,
# e a linha que importa se perderia no meio das outras.
_ja_avisei_que_falta_chave = False

# O que o servidor de push responde quando o aparelho não existe mais: a pessoa
# desinstalou o app, limpou os dados do navegador, ou o fabricante expirou a
# inscrição. As duas respostas são definitivas — repetir o envio nunca vai
# funcionar, e a linha tem de sair do banco.
STATUS_DE_APARELHO_MORTO = (404, 410)

# Teto curto de propósito: este envio acontece dentro do consumidor do fio, e um
# servidor de push lento não pode segurar a fila de cartas de todo mundo. Cinco
# segundos é folgado para uma chamada que normalmente leva menos de um.
SEGUNDOS_DE_ESPERA = 5


class AparelhoMorto(Exception):
    """O servidor de push disse que este aparelho não existe mais.

    Exceção própria, e não um `bool` de retorno: quem chama PRECISA apagar a
    linha, e um valor de retorno que o chamador pode ignorar em silêncio é
    exatamente como um banco acumula lixo eterno.
    """


def esta_configurado() -> bool:
    return bool(settings.VAPID_PRIVATE_KEY and settings.VAPID_SUBJECT)


def enviar(inscricao, *, assunto: str, parametros: dict) -> bool:
    """Manda um aviso para UM aparelho. Devolve se ele saiu.

    **O conteúdo não diz para onde o toque leva, e isso é de propósito.** O
    endereço público de uma página é conhecimento do site, não desta célula;
    quem recebe o aviso é o service worker do `funil`, que sabe onde mora a
    página de avisos e em que idioma a pessoa está. Mandar um caminho daqui
    seria a segunda casa do mesmo endereço, e a primeira a envelhecer.

    Levanta `AparelhoMorto` quando a inscrição precisa ser apagada. Qualquer
    outra falha vira `False` com um log: o servidor de push pode estar fora do
    ar, e isso não é problema desta pessoa nem desta carta.
    """
    global _ja_avisei_que_falta_chave
    if not esta_configurado():
        if not _ja_avisei_que_falta_chave:
            logger.warning(
                "[push] VAPID_PRIVATE_KEY/VAPID_SUBJECT ausentes — nenhum aviso "
                "sai desta célula até o segredo ser instalado no servidor. As "
                "cartas continuam sendo gravadas normalmente."
            )
            _ja_avisei_que_falta_chave = True
        return False

    conteudo = json.dumps({"assunto": assunto, "parametros": parametros})
    try:
        # O import mora aqui DENTRO do try, e não no topo do arquivo: uma
        # dependência que só é necessária para enviar não pode impedir a célula
        # de subir, e um `ImportError` tem de cair na mesma rede de segurança
        # que uma falha de rede. Importado fora do try, ele subiria por cima de
        # todo o cuidado abaixo.
        from pywebpush import WebPushException, webpush

        webpush(
            subscription_info={
                "endpoint": inscricao.endpoint,
                "keys": {"p256dh": inscricao.p256dh, "auth": inscricao.auth},
            },
            data=conteudo,
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={"sub": settings.VAPID_SUBJECT},
            timeout=SEGUNDOS_DE_ESPERA,
        )
        return True
    except AparelhoMorto:
        raise
    except Exception as erro:  # noqa: BLE001 — falha ABERTA, sem exceção
        # `WebPushException` não pode ser nomeada num `except` próprio: ela vem
        # da biblioteca que este mesmo bloco importa, e nomeá-la aqui exigiria
        # o import lá em cima — o que reabriria o buraco que o comentário
        # acima fechou. O status da resposta é lido por atributo, que é o que
        # a exceção dela carrega.
        status = getattr(getattr(erro, "response", None), "status_code", None)
        if status in STATUS_DE_APARELHO_MORTO:
            raise AparelhoMorto(str(status)) from erro
        if status is not None:
            logger.warning(
                "[push] o servidor de push recusou (status %s) — o aviso "
                "continua na caixa da pessoa: %s",
                status,
                erro,
            )
            return False
        # Rede caída, DNS, timeout, biblioteca ausente: nada disto pode
        # derrubar o consumidor do fio. A carta já está gravada, que é a
        # promessa que esta plataforma faz.
        logger.warning("[push] falha ao enviar, e a caixa segue intacta: %s", erro)
        return False
