"""Quem é da EQUIPE da escola nesta casa, e por que a resposta mora aqui dentro.

**Cópia do PADRÃO de `services/gamificacao/apps/core/equipe.py`, nunca do
arquivo dela** (Lei 3). Lá esta lista abre a fila dos marcos; aqui ela abre a
fila da conferência do portfólio (critério AC-11). O desenho é o mesmo porque o
problema é o mesmo, e um segundo jeito de responder "esta pessoa é da equipe?"
seria uma segunda resposta livre para discordar da primeira.

**"Reconhecer não é autorizar."** A `identidade` devolve um `papel` junto com o
id de quem está logado, e usá-lo para abrir a fila seria confortável e errado:
aquele campo é de EXIBIÇÃO (`apps/core/menu.py` já diz isso de si mesmo), e quem
decide o que alguém pode fazer nesta casa é esta célula, fail-CLOSED.

**A LISTA VAZIA É NINGUÉM.** Env ausente não derruba o boot, não quebra tela
nenhuma do aluno e fecha a porta da equipe. Fail-closed sem fail-hard: a célula
sobe, a Prancheta e a estante continuam respondendo, e só a fila fica
inacessível até o env existir. É o mesmo desenho de `TOKENS_ACEITOS` em
`config/settings.py`.

**Por que id de plataforma e não e-mail:** e-mail muda de dono, e o id opaco é o
que a porta já tem na mão depois de perguntar à `identidade`. Comparar e-mail
custaria uma segunda pergunta de rede e uma segunda forma de a mesma pessoa
existir.

**QUEM ESCREVE O ENV É O MANTENEDOR, NA VPS**, e hoje ninguém escreveu: a
variável não está em `infra/provisionar-pages.sh`, que é caminho CODEOWNERS, e
o PR deste degrau não tem mandato para tocá-lo. Enquanto a linha faltar, a fila
abre e diz, em português, que a pessoa não está na lista. Nada quebra, e o aluno
continua podendo pedir a conferência: o pedido espera na fila até alguém poder
olhar. A dívida está no balcão, nascida bloqueada, com o caminho de volta
escrito nela.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger("pages.equipe")

# O nome da variável, num lugar só: a mensagem de recusa e o roteiro de
# provisionamento citam a MESMA palavra, e o teste compara as duas.
VARIAVEL = "IDS_DA_EQUIPE"

_ja_avisei_que_a_lista_esta_vazia = False


def ids_da_equipe() -> frozenset[str]:
    """Os ids de plataforma que podem conferir o portfólio dos outros.

    Lido **no ponto de uso, nunca no import** (`armadilhas/097`): env lido no
    carregamento do módulo transforma variável ausente em erro de boot, e uma
    célula inteira sairia do ar por causa de uma lista de nomes.

    Separador é vírgula, espaços são ignorados, e valor vazio some. Formato
    frouxo de propósito na LEITURA e rígido na escrita: quem digita é um humano
    numa VPS, e um espaço a mais não pode trancar a equipe para fora.
    """
    global _ja_avisei_que_a_lista_esta_vazia
    cru = os.environ.get(VARIAVEL, "")
    ids = frozenset(pedaco.strip() for pedaco in cru.split(",") if pedaco.strip())
    if not ids and not _ja_avisei_que_a_lista_esta_vazia:
        # UMA vez por processo. O log existe para o dia em que a fila estiver
        # "quebrada" para todo mundo: sem esta linha, a causa (env ausente) é
        # indistinguível de "ninguém tem permissão", que é o que a tela diz.
        logger.warning(
            "%s está vazia ou ausente: NINGUÉM abre a fila da conferência do "
            "portfólio. A linha mora no env desta célula, escrito na VPS.",
            VARIAVEL,
        )
        _ja_avisei_que_a_lista_esta_vazia = True
    return ids


def e_da_equipe(pessoa_id: str | None) -> bool:
    """Esta pessoa pode conferir o portfólio de outra?

    `None` (visitante) devolve `False` sem consultar nada, e a ordem importa:
    perguntar a lista primeiro faria um id vazio casar com um item vazio no dia
    em que alguém escrevesse `IDS_DA_EQUIPE=,,` no env.
    """
    if not pessoa_id:
        return False
    return pessoa_id in ids_da_equipe()
