"""A batida na rede que diz se o endereço colado pelo aluno abre.

Este módulo é a mitigação que o plano §6.2 prometeu quando o mantenedor
escolheu, em 01/09/2026, que a foto entra por LINK COLADO e nunca hospedada por
nós. O preço dessa escolha está escrito lá com todas as letras: link de aluno
quebra, e quando quebra a escola não consegue consertar do lado de lá. O que
esta casa pode fazer é OLHAR, e é isto.

AS TRÊS RESPOSTAS, E A TERCEIRA É A QUE COSTUMA SER ESQUECIDA
--------------------------------------------------------------
- **`RESPONDEU`** — o outro lado atendeu com um status de sucesso.
- **`NAO_RESPONDEU`** — o outro lado atendeu e disse NÃO (403, 404, 500). É a
  única resposta que a escola pode afirmar sobre o link do aluno, porque ela
  veio do servidor dele.
- **`NAO_DEU_PARA_CONFERIR`** — ninguém atendeu: estourou o tempo, o nome não
  resolveu, a conexão morreu. **Isto não é "o link está quebrado"**, é "a
  escola não sabe", e as duas frases levam a coisas diferentes acontecerem.
  Daqui de dentro é impossível separar "o site dele caiu" de "a nossa rede
  caiu", e chutar uma das duas seria acusar a obra do aluno por causa de um
  problema que pode ser nosso.

QUEM DECIDE O QUE FAZER COM CADA UMA É QUEM CHAMA, E A ASSIMETRIA É O DESENHO
-----------------------------------------------------------------------------
Na hora de COLAR (critério AC-08) existe um aluno esperando na frente da tela,
e um "quebrado" errado o impede de guardar uma obra que está perfeita: por isso
só `NAO_RESPONDEU` recusa, e `NAO_DEU_PARA_CONFERIR` guarda a peça marcada como
ainda não conferida, dizendo isso na tela.

Na VARREDURA periódica (critério AC-09) não há ninguém esperando, a marca é
reversível (volta a `respondendo` no minuto em que o endereço abrir de novo) e
**nada é apagado nunca**: por isso as duas contam como não abriu. Um endereço
cujo domínio morreu de vez nunca mais devolve status nenhum, e é justamente ele
o buraco que o §6.2 pediu para vigiar.

O TETO DE TEMPO NÃO É ENFEITE
------------------------------
O endereço é de um servidor de terceiro que esta casa não controla: sem teto,
um servidor lento pendura a requisição do aluno até o navegador dele desistir.
Cinco segundos é o mesmo teto que `apps/core/clients.py` já usa para os saltos
que ficam no caminho de uma tela.

O CLIENTE É UM SÓ POR PROCESSO, e não `httpx.get()` a cada chamada: cada
chamada construiria um `ssl.SSLContext` novo (`armadilhas/082`). Ele é próprio,
e não o de `apps/core/clients.py`, porque as duas conversas são diferentes: lá
é a plataforma falando com as células dela, com Bearer e contrato; aqui é a
internet aberta, sem credencial nenhuma e com redirecionamento seguido.
"""

from __future__ import annotations

import ipaddress
import logging
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

logger = logging.getLogger("pages.conferencia_do_link")

# Teto explícito, como o dos clientes desta casa. Um servidor de terceiro que
# demora mais que isto não vai encaixar na tela de ninguém.
TIMEOUT = 5.0

RESPONDEU = "respondeu"
NAO_RESPONDEU = "nao_respondeu"
NAO_DEU_PARA_CONFERIR = "nao_deu_para_conferir"

_cliente: httpx.Client | None = None


@dataclass(frozen=True)
class Veredito:
    """O que a batida na rede achou, e a frase que o aluno lê se der ruim.

    `motivo` é escrito PARA O ALUNO: diz o que aconteceu e o que fazer, sem
    jargão e sem travessão. Vazio quando o endereço abriu, porque aí não há o
    que explicar.
    """

    resultado: str
    motivo: str = ""

    @property
    def abriu(self) -> bool:
        return self.resultado == RESPONDEU


def http() -> httpx.Client:
    """Um `httpx.Client` por processo para a internet aberta."""
    global _cliente
    if _cliente is None:
        _cliente = httpx.Client(timeout=TIMEOUT, follow_redirects=True)
    return _cliente


def recusa_pela_forma(link: str) -> str:
    """O que está errado no endereço antes mesmo de tocar na rede, ou "".

    **Duas regras, e a segunda é uma trava de segurança, não capricho.**

    1. **`https` e nada mais.** A vitrine que o aluno manda ao cliente é
       servida por `https`, e um endereço `http` dentro dela é bloqueado pelo
       navegador como conteúdo misto: a imagem simplesmente não aparece, sem
       explicação nenhuma para o aluno nem para o cliente dele. Recusar aqui,
       com a frase escrita, é melhor do que entregar um buraco silencioso na
       página que ele usa para vender.
    2. **Endereço de máquina de dentro não passa.** Esta função roda no
       SERVIDOR, então um endereço colado por qualquer aluno vira uma
       requisição saindo de dentro da plataforma. Sem esta trava, colar
       `http://identidade:8000/interno/...` transformaria a conferência de link
       numa sonda das células vizinhas, e o veredito devolvido na tela diria ao
       aluno o que respondeu lá dentro. Nome sem ponto é máquina da rede
       interna; endereço numérico é a mesma coisa escrita de outro jeito.
    """
    partes = urlsplit(link)
    if partes.scheme != "https":
        return (
            "o endereço precisa começar com https, porque a sua página é "
            "segura e o navegador do seu cliente não mostra imagem vinda de um "
            "endereço http. Abra a imagem no navegador e copie o endereço de lá."
        )

    host = partes.hostname or ""
    if not host:
        return (
            "não deu para entender o endereço. Abra a imagem no navegador e "
            "copie o endereço inteiro da barra de cima."
        )

    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return (
            "esse endereço aponta para um número de máquina, e não para um "
            "site na internet. Use o endereço que o Drive, o ArtStation ou o "
            "site onde a imagem está guardada mostra na barra do navegador."
        )

    if "." not in host:
        return (
            "esse endereço não parece ser de um site da internet. Use o "
            "endereço que o Drive, o ArtStation ou o site onde a imagem está "
            "guardada mostra na barra do navegador."
        )

    return ""


def conferir(link: str) -> Veredito:
    """Bate no endereço e diz o que aconteceu. Nunca levanta exceção.

    Nunca levanta porque quem chama são duas coisas que não podem morrer por
    causa de um site de terceiro: a tela em que um aluno está guardando a obra
    dele, e a varredura que passa por todas as peças da escola.
    """
    motivo = recusa_pela_forma(link)
    if motivo:
        return Veredito(NAO_RESPONDEU, motivo)

    try:
        # Só o cabeçalho: o que interessa é o status, e baixar o corpo puxaria
        # a imagem inteira do aluno para dentro do nosso servidor a cada
        # conferência, sem nenhum uso para os bytes.
        status = http().head(link).status_code
        # Servidor que não sabe responder a um HEAD devolve 405 ou 501. Aí a
        # pergunta se refaz em `GET` por streaming, que abre a resposta, lê o
        # status e a fecha sem baixar o corpo. Sem esta segunda tentativa, um
        # site inteiro de hospedagem de imagem seria declarado quebrado por não
        # atender a um verbo, e o aluno não teria o que consertar.
        if status in (405, 501):
            with http().stream("GET", link) as resposta:
                status = resposta.status_code
    except httpx.TimeoutException as erro:
        logger.info("o endereço da peça demorou demais: %s", erro)
        return Veredito(
            NAO_DEU_PARA_CONFERIR,
            "a escola não conseguiu conferir esse endereço agora, porque ele "
            "demorou demais para responder. A peça foi guardada e vamos "
            "conferir de novo mais tarde.",
        )
    except httpx.RequestError as erro:
        logger.info("não deu para chegar no endereço da peça: %s", erro)
        return Veredito(
            NAO_DEU_PARA_CONFERIR,
            "a escola não conseguiu chegar nesse endereço agora. Pode ser o "
            "site onde a imagem está, pode ser a nossa conexão. A peça foi "
            "guardada e vamos conferir de novo mais tarde.",
        )

    if 200 <= status < 300:
        return Veredito(RESPONDEU)

    return Veredito(
        NAO_RESPONDEU,
        f"esse endereço respondeu com o erro {status}, então a imagem não vai "
        "aparecer para quem você mandar o link. O caso mais comum é a imagem "
        "estar privada: abra o compartilhamento e deixe visível para qualquer "
        "pessoa com o link, ou confira se o endereço está completo.",
    )
