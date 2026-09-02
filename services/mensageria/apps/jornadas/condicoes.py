"""As condições que um passo pode consultar — funções Python num dicionário.

Lei: `docs/decisoes/PLANO-SEQUENCIAS-DE-MENSAGENS.md` §4.2 e §10.1.

**Isto não é, e nunca pode virar, uma linguagem de fórmulas dentro do banco.**
Condição nova é um PR pequeno que acrescenta uma função aqui; o `Passo` guarda só
o SLUG dela. Uma DSL neste ponto é o critério de morte §10.1 do plano, e é como
este motor viraria um monstro em seis meses.

A diferença entre as duas coisas é exatamente esta lista: um punhado de nomes que
um humano lê inteiro em cinco segundos, contra uma linguagem que ninguém audita.

DE ONDE ELAS LEEM, E POR QUE NÃO É DA OUTRA CÉLULA
---------------------------------------------------
Toda condição lê a projeção `EstadoDoAluno`, e SÓ ela. Nenhuma faz chamada
síncrona a outra célula, e a razão está medida no §5: 10 mil pessoas x 4
condições seriam 40 mil idas à rede numa passada da varredura, e o `consome:` da
célula cresceria a cada condição nova.

A projeção é superfície **calculada**, não fonte da verdade — a autoridade sobre
"esta pessoa entrou em aula" continua sendo de quem publica o fato. A Lei 7
(nenhum fato mora em dois lugares) continua respeitada, e é esta distinção que a
salva. Está escrito aqui porque, sem isso escrito, a próxima sessão lê como
duplicação e tem razão.

QUANDO A CONDIÇÃO É AVALIADA
----------------------------
**No instante do envio, nunca no da inscrição.** É a diferença entre uma
sequência que sabe desistir e uma que manda "sentimos sua falta" para quem voltou
ontem — e essa é a falha que faz o aluno desligar tudo (§9).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable

from .models import EstadoDoAluno

# Uma condição recebe a projeção da pessoa (ou `None`, quando ela ainda não tem
# projeção nenhuma) e o instante da avaliação. Devolve "este passo ainda faz
# sentido?".
Condicao = Callable[["EstadoDoAluno | None", datetime], bool]

CONDICOES: dict[str, Condicao] = {}

# Quantos dias de silêncio contam como "sumiu". Constante, e não parâmetro do
# passo: parâmetro no banco é o primeiro degrau da DSL que o §10.1 proíbe. Se um
# dia forem precisos dois prazos, nascem duas condições com nomes próprios, e o
# diff que as cria é visível.
DIAS_PARA_SUMIR = 5


class CondicaoDesconhecida(KeyError):
    """O `condicao_slug` de um passo não existe neste dicionário.

    Existe como classe própria para que o motor possa tratá-la como o que ela é:
    motivo para PULAR o passo, nunca para mandá-lo assim mesmo. Um erro de
    digitação num slug não pode virar mensagem enviada a quem não devia recebê-la.
    """


def condicao(slug: str):
    """Registra uma condição. O slug é o que o `Passo` guarda."""

    def registrar(funcao: Condicao) -> Condicao:
        if slug in CONDICOES:
            raise ValueError(f"condicao duplicada: {slug}")
        CONDICOES[slug] = funcao
        return funcao

    return registrar


@condicao("ainda-nao-entrou-em-aula")
def _ainda_nao_entrou_em_aula(estado, momento) -> bool:
    """O empurrãozinho só faz sentido para quem ainda não começou."""
    return estado is None or estado.ultima_aula_em is None


@condicao("ainda-nao-postou-no-forum")
def _ainda_nao_postou_no_forum(estado, momento) -> bool:
    """O convite para a comunidade só faz sentido para quem ainda não falou lá."""
    return estado is None or estado.ultimo_post_em is None


@condicao("sem-atividade-ha-5-dias")
def _sem_atividade_ha_5_dias(estado, momento) -> bool:
    """ "Sumiu" continua valendo? Quem voltou ontem NÃO recebe "senti sua falta".

    Sem projeção nenhuma a resposta é NÃO: pessoa sem nenhuma atividade
    registrada é pessoa sobre quem não se sabe nada, e mandar "senti sua falta"
    para quem talvez nunca tenha entrado é a mensagem errada. Fail-closed.
    """
    if estado is None or estado.ultima_atividade_em is None:
        return False
    return momento - estado.ultima_atividade_em >= timedelta(days=DIAS_PARA_SUMIR)


def avaliar(slug: str, estado, momento: datetime) -> bool:
    """A condição de um passo. Slug vazio é "sem condição": o passo sempre vale.

    Slug DESCONHECIDO levanta, e quem chama trata isso como "pula o passo" —
    nunca como "manda assim mesmo". A diferença aparece no dia de um erro de
    digitação, e nesse dia ela é a diferença entre uma mensagem não enviada e uma
    mensagem enviada para a pessoa errada.
    """
    if not slug:
        return True
    try:
        funcao = CONDICOES[slug]
    except KeyError as erro:
        raise CondicaoDesconhecida(slug) from erro
    return funcao(estado, momento)
