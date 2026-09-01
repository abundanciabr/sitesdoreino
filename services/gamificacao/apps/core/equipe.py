"""Quem é da EQUIPE da escola, e por que a resposta mora aqui dentro.

**"Reconhecer não é autorizar"** é a segunda metade do §5 da
`DECISAO-gamificacao.md`, e ela é o motivo deste arquivo existir. A `identidade`
devolve um `papel` junto com o id de quem está logado, e usá-lo para abrir a
fila de validação seria confortável e errado: aquele campo é de EXIBIÇÃO, e quem
decide o que alguém pode fazer aqui é esta célula, fail-CLOSED.

A diferença não é filosófica. O `papel` da identidade responde "esta pessoa é
professora **na plataforma**?"; a pergunta desta fila é "esta pessoa pode
declarar que o primeiro cliente de alguém aconteceu?". No dia em que a
plataforma tiver um segundo produto com outros professores, a primeira resposta
continuaria "sim" e a segunda passaria a ser "não" — e ninguém perceberia,
porque nada quebraria.

**A LISTA VAZIA É NINGUÉM**, e é o mesmo desenho de `TOKENS_ACEITOS` logo ao
lado: env ausente não derruba o boot, não quebra tela nenhuma do aluno, e fecha
a porta da equipe. Fail-closed sem fail-hard. A célula sobe, `/conquistas`
continua respondendo, e só a fila fica inacessível até o env existir.

**Por que id de plataforma e não e-mail:** e-mail muda de dono e não é o que
esta célula recebe. `quem_e()` devolve o id opaco, e é ele que a lista compara —
sem conversão, sem chamada de rede, sem cache para envelhecer.

Quem escreve o env é `infra/provisionar-equipe-da-gamificacao.sh`, na VPS, pelo
mantenedor: um id de pessoa é dado da produção, e nenhum agente o inventa.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

# O nome da variável, num lugar só: a mensagem de recusa cita a mesma palavra
# que o script de provisionamento escreve, e o teste compara as duas.
VARIAVEL = "IDS_DA_EQUIPE"

_ja_avisei_que_a_lista_esta_vazia = False


def ids_da_equipe() -> frozenset[str]:
    """Os ids de plataforma que podem decidir um pedido de validação.

    Lida **no ponto de uso**, nunca no import (`armadilhas/097`): env lido no
    carregamento do módulo transforma variável ausente em erro de boot, e uma
    célula inteira sairia do ar por causa de uma lista de nomes.

    Separador é vírgula, espaços são ignorados, e valor vazio some. Formato
    frouxo de propósito na LEITURA e rígido na escrita: quem digita é um humano
    numa VPS, às duas da manhã, e um espaço a mais não pode trancar a equipe
    para fora.
    """
    global _ja_avisei_que_a_lista_esta_vazia
    cru = os.environ.get(VARIAVEL, "")
    ids = frozenset(pedaco.strip() for pedaco in cru.split(",") if pedaco.strip())
    if not ids and not _ja_avisei_que_a_lista_esta_vazia:
        # UMA vez por processo. O log existe para o dia em que a fila estiver
        # "quebrada" para todo mundo: sem esta linha, a causa (env ausente) é
        # indistinguível de "ninguém tem permissão", que é o que a tela diz.
        logger.warning(
            "%s está vazia ou ausente: NINGUÉM abre a fila de validação. "
            "Quem a escreve é infra/provisionar-equipe-da-gamificacao.sh, na VPS.",
            VARIAVEL,
        )
        _ja_avisei_que_a_lista_esta_vazia = True
    return ids


def e_da_equipe(pessoa_id: str | None) -> bool:
    """Esta pessoa pode julgar pedido dos outros?

    `None` (visitante) devolve `False` sem consultar nada. É a ordem que
    importa: perguntar a lista primeiro faria um id vazio casar com um item
    vazio no dia em que alguém escrevesse `IDS_DA_EQUIPE=,,` no env.
    """
    if not pessoa_id:
        return False
    return pessoa_id in ids_da_equipe()
