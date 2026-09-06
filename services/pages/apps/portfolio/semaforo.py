"""O semáforo de uma peça: a cor, e a lista do que ainda falta nela.

ci:texto-publicado

A MARCA ACIMA LIGA O PORTÃO DO TRAVESSÃO neste arquivo inteiro
(`ci/travessao.py`, terceira regra de alcance no `CLAUDE.md`). Ela é obrigatória
pelo mesmo motivo do `roteiro_da_escola.py`: as frases daqui são lidas pelo
ALUNO, e não estão numa `templates/` nem num rótulo de `TextChoices`, que são as
duas regras que pegam sozinhas.

Lei: `docs/changespecs/CS-PAGES-0001.md`, critério AC-10, e
`docs/decisoes/PLANO-PORTFOLIO-DO-ALUNO.md` §5 (degrau 10) e §7. Este módulo é o
degrau 10 inteiro, tirando a tela.

O QUE ESTE SEMÁFORO É, E O QUE ELE NUNCA SERÁ
---------------------------------------------
Ele diz **o que falta marcar**. Ele não diz **quanto a peça vale**.

Nota, estrela, ranking e voto popular em portfólio de aluno são proibidos por
escrito (plano §7), e detectar "isto foi feito por IA" também. Nada aqui olha a
obra: o módulo não abre a imagem, não a mede, não a compara com nada e não tem
opinião sobre ela. Ele lê as respostas que a própria pessoa deu a perguntas de
sim ou não, confere quais ficaram em branco, e devolve a lista.

**A LISTA É O PRODUTO. A COR É SÓ O RESUMO DELA.** Um semáforo amarelo que não
diz o que falta é um enfeite, e é por isso que `Semaforo.pendencias` nunca vem
vazia num amarelo ou num vermelho: a cor sai da lista, e não o contrário.

O TEXTO DAS REGRAS NÃO MORA AQUI, E ISSO É LEI DESTA CASA
----------------------------------------------------------
Quem escreveu as quatro regras foi a professora do curso, e elas estão no banco,
plantadas pelo degrau 07 a partir de `apps/portfolio/roteiro_da_escola.py`. Este
módulo recebe o texto delas de fora, em `regras`, e apenas o repassa. Copiá-lo
para cá criaria a segunda verdade que esta casa recusa desde o degrau 02: no dia
em que a escola corrigisse uma palavra, o aluno leria a antiga na Prancheta e a
nova aqui, ou o contrário, sem nada acusar.

O que este módulo guarda é o LIGAMENTO (qual resposta serve a qual regra) e o
que fazer para responder. Isso não é a regra, e não existe em lugar nenhum além
daqui.

POR QUE A REGRA 2 DA PROFESSORA NÃO TEM PERGUNTA PRÓPRIA NESTA TELA
--------------------------------------------------------------------
Ela é "pelo menos 3 peças de cada tipo escolhido", e é uma conta sobre o
portfólio INTEIRO, não um fato de uma peça: nenhuma peça sozinha cumpre ou
descumpre essa regra. A resposta de que ela precisa é o `tipo`, que a pergunta
da regra 1 já colhe, e quem marca o resultado é o próprio aluno na Prancheta,
onde essa caixa vive desde o degrau 07. Contá-la aqui poria a mesma marcação em
dois lugares, livres para discordar um do outro.

POR QUE O LINK QUEBRADO ENTRA, E O NÃO CONFERIDO NÃO
-----------------------------------------------------
O critério AC-10 diz "calculado só das respostas objetivas do aluno", e o
endereço colado É uma resposta objetiva dele. Que esse endereço parou de abrir é
um fato medido sobre a resposta dele, nunca uma opinião sobre a obra, e esconder
isso deixaria verde justamente a peça que ninguém consegue ver.

Já `nao_conferido` é a nossa própria ignorância, e ela não é falta do aluno.
Daqui não dá para separar "o site dele caiu" de "a nossa rede caiu"
(`apps/portfolio/conferencia_do_link.py` explica a assimetria por extenso), e
acusar a peça dele por causa de uma tosse da nossa rede seria a mesma injustiça
que aquele módulo recusou no degrau 08.
"""

from __future__ import annotations

from dataclasses import dataclass

from apps.portfolio.models import EstadoDoLink, ParecidaComAAula, Peca

VERDE = "verde"
AMARELO = "amarelo"
VERMELHO = "vermelho"

# As perguntas de sim ou não que o aluno responde SOBRE UMA PEÇA, e a regra da
# professora que cada uma serve. A `chave` é a mesma que viaja no roteiro do
# banco (`ItemDoRoteiro.chave`) e na marcação da Prancheta: ela nunca muda, e é
# por ela que o texto da regra chega até aqui.
#
# A ordem é a das etapas do roteiro, e é ela que a tela mostra: o aluno lê a
# lista do que falta na mesma sequência em que leu as regras.
PERGUNTAS = (
    (
        "tipo",
        "tres-tipos-escolhidos",
        "Diga de que tipo é esta peça, entre os tipos que o curso ensina.",
    ),
    (
        "acabamento",
        "maioria-high-poly",
        "Diga se esta peça é high poly ou uma variação mais simples.",
    ),
    (
        "parecida_com_a_aula",
        "nada-parecido-com-a-aula",
        "Diga se esta peça se parece com o modelo que você fez na aula.",
    ),
)

# O que o aluno faz quando ele mesmo respondeu que a peça se parece com a aula.
# Não é julgamento da obra: é a resposta dele lida contra a regra que a escola
# escreveu, e a frase diz o caminho de saída em vez de dar um veredito.
TROCAR_A_PECA_PARECIDA = (
    "Você respondeu que esta peça se parece com o modelo da aula. Troque a peça "
    "por uma criação sua, ou mude o que ela tem de igual ao da aula."
)

# O endereço parou de abrir. A frase diz o que aconteceu e o que fazer, como
# toda recusa desta casa.
GUARDAR_O_ENDERECO_NOVO = (
    "O endereço desta peça parou de abrir, então quem visitar o seu portfólio "
    "não vai ver a imagem. Guarde a peça de novo com o endereço atual dela."
)

RESUMOS = {
    VERDE: "Você já respondeu tudo o que a escola pergunta sobre esta peça.",
    AMARELO: "Falta responder sobre esta peça:",
    VERMELHO: "Esta peça precisa de um ajuste seu:",
}


@dataclass(frozen=True)
class Pendencia:
    """Uma linha do que falta nesta peça.

    `regra` é o texto da ESCOLA, vindo do banco. Ele chega vazio quando a chave
    ainda não foi plantada (instalação nova, migração do roteiro por rodar), e a
    tela continua útil porque `o_que_fazer` é frase inteira e se explica
    sozinha. Fazer a lista sumir quando o texto falta esconderia a pendência
    exatamente na instalação mais incompleta.
    """

    chave_da_regra: str
    regra: str
    o_que_fazer: str
    precisa_mudar: bool


@dataclass(frozen=True)
class Semaforo:
    cor: str
    resumo: str
    pendencias: tuple[Pendencia, ...]


def calcular(peca: Peca, regras: dict[str, str]) -> Semaforo:
    """A cor e a lista do que falta nesta peça.

    `regras` é `{chave: texto}` lido de `ItemDoRoteiro`. Ele entra por
    parâmetro, e não é buscado aqui dentro, para que a tela leia o roteiro UMA
    vez em vez de uma consulta por peça da estante.

    A cor sai da lista, e nunca de uma contagem própria: vermelho é ter alguma
    pendência que o aluno já sabe que precisa mudar, amarelo é ter só pergunta
    sem resposta, verde é a lista vazia.
    """
    pendencias: list[Pendencia] = []

    # O ajuste mais urgente primeiro: sem endereço que abra, não há peça para
    # ninguém ver, e responder as perguntas não resolve isso.
    if peca.estado_do_link == EstadoDoLink.QUEBRADO:
        pendencias.append(
            Pendencia(
                chave_da_regra="",
                regra="",
                o_que_fazer=GUARDAR_O_ENDERECO_NOVO,
                precisa_mudar=True,
            )
        )

    if peca.parecida_com_a_aula == ParecidaComAAula.SIM:
        chave = "nada-parecido-com-a-aula"
        pendencias.append(
            Pendencia(
                chave_da_regra=chave,
                regra=regras.get(chave, ""),
                o_que_fazer=TROCAR_A_PECA_PARECIDA,
                precisa_mudar=True,
            )
        )

    for campo, chave, o_que_fazer in PERGUNTAS:
        if getattr(peca, campo):
            continue
        pendencias.append(
            Pendencia(
                chave_da_regra=chave,
                regra=regras.get(chave, ""),
                o_que_fazer=o_que_fazer,
                precisa_mudar=False,
            )
        )

    if not pendencias:
        cor = VERDE
    elif any(pendencia.precisa_mudar for pendencia in pendencias):
        cor = VERMELHO
    else:
        cor = AMARELO

    return Semaforo(cor=cor, resumo=RESUMOS[cor], pendencias=tuple(pendencias))
