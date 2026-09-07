"""O povoado do simulador: cem alunos, trinta projetos e um relógio de mentira.

Este arquivo MONTA o mundo. Ele não julga nada, não decide quem recebe oferta, não
decide quem enxerga o Mural e não sabe o que é justiça: quem julga é
`test_simulador_de_justica.py`, e quem decide é o motor, o Mural e a negociação. É
a mesma separação do `tests/conftest.py` da célula, e ela importa mais ainda aqui:
uma fábrica que soubesse a regra faria o simulador medir a própria resposta.

TUDO É SEMEADO, E A SEMENTE É FIXA
-----------------------------------
`SEMENTE` é o número que faz este mundo ser sempre o mesmo mundo. Cem alunos com
títulos, entregas, datas de entrada e temperamentos diferentes saem de um
`random.Random(SEMENTE)`, e trocar a semente troca o cenário inteiro. Sem
semente, um simulador que acusasse uma injustiça uma vez em cada vinte rodadas
seria pior do que não existir: ninguém conseguiria reproduzir o vermelho.

O RELÓGIO COMEÇA ÀS 8h DE SÃO PAULO, E ISSO NÃO É DETALHE
----------------------------------------------------------
`t_zero` é a abertura da janela ([INV-ENC-J8]) do dia seguinte ao de hoje. As
duas metades da escolha têm motivo:

- **A HORA é fixa** (a abertura da janela), porque a janela 8h-22h muda o
  resultado da simulação. Começar num instante qualquer faria o placar mudar
  conforme a hora em que a suíte rodasse, e um placar que muda sozinho não pode
  ser conferido contra o piloto de papel.
- **O DIA é o de amanhã**, e não uma data escrita à mão, porque uma data fixa no
  futuro fica vermelha sozinha no dia em que o calendário a alcança
  (`armadilhas/323`, medida nesta célula).

E O RELÓGIO DA MÁQUINA PASSA A SER O RELÓGIO SIMULADO
------------------------------------------------------
`relogio_da_maquina` congela `django.utils.timezone.now` no instante simulado, e
sem ele o degrau 2.13 não seria mensurável. A razão cabe numa frase: **as duas
pistas contam o tempo de espera a partir de `MudancaDeStatus.em`, que é
`auto_now_add`.** Enquanto o simulador só encenava a fila, isso não aparecia: as
idas e vindas internas (`na_fila` para `oferecida` e de volta) não geram marco, e
o marco inicial cai em `criada_em`, que a fábrica escreve com o instante simulado.

Com a negociação, um projeto VOLTA à pista vindo de `em_negociacao`, e essa volta
é um marco de verdade. Com o relógio da máquina correndo por fora, esse marco
nasceria um a nove dias no passado do mundo simulado, e todo projeto devolvido
viraria chamada aberta (ou iria ao plantão) no primeiro tique seguinte, sem
ninguém ter tido a chance de vê-lo. O mundo inteiro degeneraria em plantão, e o
[INV-ENC-J9] e o [INV-ENC-M5] ficariam verdes medindo um artefato.

Congelar o relógio é o que faz `Oferta.oferecida_em`, `ReservaDoMural.pegada_em`,
`Proposta.criada_em` e `MudancaDeStatus.em` contarem a mesma história que o laço
da simulação. Nenhum gesto de produção lê `timezone.now()`: todos recebem `agora`
por argumento, e é por isso que congelar o relógio muda só as colunas de
carimbo, e nunca uma decisão.

AS DUAS PISTAS NASCEM PELA PORTA DE VERDADE
--------------------------------------------
Os projetos nascem por `mural.nascer`, que é a única porta de nascimento da
célula e a que a Fase 3 vai chamar. É ela que põe o Iniciante na fila e o
Intermediário e o Avançado no Mural (`PLANO-AREA-DE-NEGOCIACAO.md` §3.1), e é por
isso que o simulador não informa pista nenhuma: **ninguém escolhe pista**, nem o
cliente, nem o aluno, nem este arquivo.

TODO MUNDO COMEÇA DISPONÍVEL, DE PROPÓSITO
-------------------------------------------
Nenhum perfil nasce `pausado` aqui. Quem pausa, pausa durante a simulação pelo
gesto de verdade (`gestos.pausar`), e quem volta volta por `gestos.religar` — que
é o único caminho que grava `modo_da_pausa` do jeito certo e o único que prova
que o lugar na fila foi mantido ([INV-ENC-J4]). Um perfil pausado escrito à mão
teria `modo_da_pausa` vazio e nunca mais conseguiria religar.
"""

import random
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.conf import settings
from django.utils import timezone as relogio_do_django

from apps.encomendas import mural
from apps.encomendas.models import Encomenda, Oferta, PerfilProfissional

# A semente. Trocar este número troca o mundo inteiro; ele existe para que o
# vermelho de amanhã seja o mesmo vermelho de hoje.
SEMENTE = 20260907

QUANTOS_ALUNOS = 100
QUANTOS_PROJETOS = 40

# Os cem alunos, por faixa. A pirâmide é a da escola de verdade: quase todo mundo
# acabou de sair do Nível 1, e Nível 3 é raro. `SEM_TITULO` são os perfis que
# existem mas nunca passaram pelo professor (lei §3.6) — eles ficam abaixo de
# tudo, e o simulador os carrega para provar que ninguém recebe oferta por
# descuido.
SEM_TITULO = 8
NIVEL_1 = 56
NIVEL_2 = 27
NIVEL_3 = 9

# Os quarenta projetos, por nível, em cada uma das quatro ondas de chegada.
# Avançado é o nível que quase ninguém alcança nos primeiros meses, e as duas
# pistas precisam mostrar o que fazem com ele.
#
# **Eram trinta em três ondas enquanto só a fila existia**, e cresceram junto com
# o mundo: com a emenda, metade dos projetos passou a nascer no Mural, e a fila
# ficou com metade do movimento que tinha. Vinte Iniciantes é o mínimo que ainda
# faz a fila produzir passes suficientes para o mesmo aluno dizer duas vezes
# "ainda não me sinto pronto", que é o gatilho da reclassificação (plano §6.11);
# com quinze, o mecanismo simplesmente não acontecia, e o placar ficava com um
# zero que ninguém saberia ler.
POR_ONDA = {
    Encomenda.Nivel.INICIANTE: 5,
    Encomenda.Nivel.INTERMEDIARIO: 3,
    Encomenda.Nivel.AVANCADO: 2,
}
ONDAS = 4

# O cartão de cada nível, DERIVADO da tabela do modelo em vez de escrito de novo.
# O cartão decide o nível, e o banco recusa o par incoerente
# (`o_cartao_decide_o_nivel`); uma segunda tabela aqui divergiria da primeira no
# dia em que um cartão novo entrasse, e o vermelho apareceria no lugar errado.
CARTAO_DO_NIVEL = {nivel: cartao for cartao, nivel in Encomenda.NIVEL_DO_CARTAO.items()}

# A lista FECHADA de entregáveis que o briefing de cada projeto declara, e da
# qual toda proposta marca um subconjunto (`PLANO-AREA-DE-NEGOCIACAO.md` §4.1).
# Uma proposta que saísse desta lista seria recusada por
# `entregavel_fora_do_briefing`, e o simulador ficaria vermelho por motivo errado.
ENTREGAVEIS_DO_BRIEFING = ("modelo_3d", "texturas", "arquivo_fonte")

# O PREÇO DE REFERÊNCIA de cada nível, em centavos. **Não é parâmetro da lei**
# (não há chave para ele no vocabulário do banco, e o mantenedor não o edita numa
# tela): é a régua do experimento, como o passo e a duração. Ele existe para as
# propostas terem números plausíveis e para a contraproposta poder cortar sem
# chegar a zero, que o banco recusaria (`proposta_tem_valor`).
VALOR_DE_REFERENCIA = {
    Encomenda.Nivel.INICIANTE: 12_000,
    Encomenda.Nivel.INTERMEDIARIO: 35_000,
    Encomenda.Nivel.AVANCADO: 90_000,
}


class RelogioDaMaquina:
    """O `timezone.now()` do Django, preso ao instante simulado.

    Um objeto com um atributo, e não uma variável de módulo, porque o laço da
    simulação precisa MOVER o relógio a cada passo e o `monkeypatch` precisa
    apontar para algo que continue existindo depois de instalado.
    """

    def __init__(self, agora: datetime):
        self.agora = agora


@dataclass(frozen=True)
class Temperamento:
    """Como ESTE aluno se comporta nas duas pistas, sorteado uma vez só.

    Sortear o temperamento por aluno, e não a cada gesto, é o que faz a simulação
    ter gente dentro dela: existe quem aceita quase sempre, quem passa quase
    sempre, e quem some. É de gente que some que nascem os três silêncios da
    pausa automática, as reservas que vencem e as propostas que caducam; é de
    gente que passa que nasce a reclassificação.
    """

    # A FILA
    p_aceita: float
    p_passa: float
    motivo_preferido: str
    p_pausa: float
    p_religa: float
    horas_de_trabalho: int
    # O MURAL E A NEGOCIAÇÃO
    p_pega_no_mural: float
    p_propoe: float
    p_aceita_a_contraproposta: float
    p_contrapropoe: float
    p_desiste: float
    prazo_pedido: int


@dataclass(frozen=True)
class Cliente:
    """Como o cliente DESTE projeto responde a uma proposta do aluno.

    O cliente é sempre a escola enquanto a origem for `escola` (§1, terceira
    resposta do mantenedor), mas cada projeto tem uma pessoa diferente do outro
    lado, e é isso que faz os quatro desfechos da §4.2 aparecerem no mesmo mundo:
    o que aceita, o que contrapropõe até esgotar as rodadas, o que desiste e o
    que simplesmente some. É do que some que nasce o [INV-ENC-N7].
    """

    p_aceita: float
    p_contrapropoe: float
    p_desiste: float


@dataclass
class Povoado:
    """O mundo montado, e as três coisas que o simulador precisa lembrar dele.

    `chegada` guarda o instante SIMULADO em que cada projeto nasceu,
    `lugar_na_fila` guarda a `data_entrada_fila` de cada perfil no minuto zero, e
    `entregas_no_comeco` guarda quantas entregas cada um tinha antes de qualquer
    coisa acontecer. As três existem porque o guarda precisa de uma medida
    INDEPENDENTE do banco: o [INV-ENC-J4] se mede contra o lugar original, e a
    promessa do primeiro dólar se mede contra quem começou em zero.
    """

    site_id: str
    t_zero: datetime
    relogio: RelogioDaMaquina
    sorteio: random.Random
    perfis: list
    temperamentos: dict
    projetos: list
    clientes: dict
    chegada: dict
    lugar_na_fila: dict
    entregas_no_comeco: dict
    # A letra miúda do briefing e o preço de referência viajam DENTRO do povoado,
    # e não como constantes que o guarda importaria deste arquivo. O motivo é de
    # oficina e vale escrever: `tests/conftest.py` e este arquivo têm o mesmo
    # nome de módulo, e um `import conftest` no guarda pegaria o primeiro que o
    # pytest tivesse carregado. O mundo entrega o que o mundo montou.
    entregaveis: tuple
    referencia: dict


@pytest.fixture
def t_zero():
    """A abertura da janela de amanhã, no fuso da célula, devolvida em UTC."""
    fuso = ZoneInfo(settings.TIME_ZONE)
    amanha = datetime.now(tz=fuso).date() + timedelta(days=1)
    janela_abre = time(8, 0)
    return datetime.combine(amanha, janela_abre, tzinfo=fuso)


@pytest.fixture
def relogio_da_maquina(t_zero, monkeypatch):
    """Prende `timezone.now()` ao instante simulado durante a rodada inteira.

    O porquê está no cabeçalho deste arquivo, e ele é o de sempre nesta casa: um
    relógio que corre por fora faz duas partes do mesmo sistema discordarem sobre
    quando as coisas aconteceram. O que muda com isto são só as colunas de
    carimbo (`auto_now_add` e `auto_now`); nenhuma decisão de produção lê o
    relógio da máquina, porque todas recebem `agora` por argumento.
    """
    relogio = RelogioDaMaquina(t_zero)
    monkeypatch.setattr(relogio_do_django, "now", lambda: relogio.agora)
    return relogio


@pytest.fixture
def povoado(semeado, criar_perfil, relogio_da_maquina, t_zero):
    """Cem alunos e trinta projetos em três ondas, sempre os mesmos.

    Os perfis nascem antes de qualquer projeto porque é assim que a escola
    funciona: a turma existe, e o cliente chega depois.
    """
    sorteio = random.Random(SEMENTE)

    titulos = (
        [""] * SEM_TITULO
        + [PerfilProfissional.Titulo.NIVEL_1] * NIVEL_1
        + [PerfilProfissional.Titulo.NIVEL_2] * NIVEL_2
        + [PerfilProfissional.Titulo.NIVEL_3] * NIVEL_3
    )
    assert len(titulos) == QUANTOS_ALUNOS
    sorteio.shuffle(titulos)

    perfis = []
    temperamentos = {}
    for numero, titulo in enumerate(titulos):
        # Sem título é o perfil que nunca ativou a fila: `data_entrada_fila`
        # nulo, que é ausência e não penalidade (o motor chama isso de
        # `fora_da_fila`). O banco também exige título, autor e data juntos ou
        # os três vazios.
        na_fila = bool(titulo)
        entrada = t_zero - timedelta(days=sorteio.randint(1, 240)) if na_fila else None
        perfil = criar_perfil(
            f"pes-{numero:03d}",
            entrada=entrada,
            titulo=titulo,
            entregas=_entregas_do_titulo(titulo, sorteio),
            abandonos=_abandonos(titulo, sorteio, t_zero),
        )
        perfis.append(perfil)
        temperamentos[perfil.id] = _temperamento(sorteio)

    projetos = []
    clientes = {}
    chegada = {}
    for onda in range(ONDAS):
        for minuto, nivel in enumerate(_niveis_da_onda()):
            # UM MINUTO ENTRE UM E OUTRO, e o minuto é o que torna esta simulação
            # reproduzível. O motor varre `na_fila` ordenando só por `criada_em`
            # (plano §7.4) e o Mural lista por `criada_em` (§3.3); com dez
            # projetos no mesmo instante, a ordem seria a que o banco devolvesse,
            # e o placar mudaria a cada rodada mesmo com a semente fixa. É também
            # o que mantém este arquivo longe do empate por UUID que a TAR-255
            # registrou.
            quando = t_zero + timedelta(days=onda, minutes=minuto)
            projeto = mural.nascer(
                site_id=semeado,
                origem=Encomenda.Origem.ESCOLA,
                cliente_id=f"cli-{len(projetos):03d}",
                cartao=CARTAO_DO_NIVEL[nivel],
                briefing={"entregaveis": list(ENTREGAVEIS_DO_BRIEFING)},
            )
            # A coluna é `auto_now_add`, e é dela que sai o marco das 24h do
            # [INV-ENC-J9] e do [INV-ENC-M5]. Sem esta linha a onda de amanhã
            # nasceria com dois dias de espera nas costas.
            Encomenda.objects.filter(pk=projeto.pk).update(criada_em=quando)
            projeto.criada_em = quando
            projetos.append(projeto)
            clientes[projeto.pk] = _cliente(sorteio)
            chegada[projeto.pk] = quando
    assert len(projetos) == QUANTOS_PROJETOS

    return Povoado(
        site_id=semeado,
        t_zero=t_zero,
        relogio=relogio_da_maquina,
        sorteio=sorteio,
        perfis=perfis,
        temperamentos=temperamentos,
        projetos=projetos,
        clientes=clientes,
        chegada=chegada,
        lugar_na_fila={p.id: p.data_entrada_fila for p in perfis},
        entregas_no_comeco={p.id: p.entregas_aprovadas for p in perfis},
        entregaveis=ENTREGAVEIS_DO_BRIEFING,
        referencia=dict(VALOR_DE_REFERENCIA),
    )


def _niveis_da_onda():
    """Os dez níveis de uma onda, na mesma ordem sempre.

    Intercalados, e não em blocos: dez Iniciantes seguidos fariam a fila resolver
    tudo o que é fácil antes de encostar no que é difícil, e as duas pistas nunca
    ficariam cheias ao mesmo tempo, que é justamente o embate que interessa.
    """
    restam = dict(POR_ONDA)
    fila = []
    while any(restam.values()):
        for nivel in POR_ONDA:
            if restam[nivel]:
                restam[nivel] -= 1
                fila.append(nivel)
    return fila


def _entregas_do_titulo(titulo, sorteio):
    """Quantas entregas aprovadas este aluno já tem. É a escola nos PRIMEIROS MESES.

    O plano diz a frase que este mundo encena: *"nos primeiros meses NINGUÉM tem
    entrega aprovada"* (§6.4, sobre a chamada aberta). Um mundo em que metade da
    turma já entregou seria uma fila fácil, e a fila fácil não prova nada: a
    dificuldade inteira da Fila do Primeiro Dólar é justamente que ninguém
    contrata quem nunca entregou.

    Então **cinco em cada seis Nível 1 têm zero**, e é isso que faz o desempate da
    lei §6.2 ser a data de entrada para dezenas de pessoas ao mesmo tempo. Uns
    três Nível 3 chegaram de fora com caminhada feita: sem eles, o nível avançado
    não teria NINGUÉM elegível, e a janela de abandono do plano §6.1 nunca
    decidiria nada.

    **É esta função que faz o Mural existir neste mundo.** O Mural só mostra a
    quem já entregou (`PLANO-AREA-DE-NEGOCIACAO.md` §3.1), então uma turma
    inteira em zero deixaria os quinze projetos Intermediário e Avançado sem
    ninguém para olhá-los, e os cinco guardas do Mural ficariam verdes numa
    prateleira vazia. Os que já entregaram são poucos de propósito: é a escassez
    que faz a memória do Mural (ninguém pega o mesmo projeto duas vezes) esgotar
    o conjunto de elegíveis, e é aí que o [INV-ENC-M5] tem de decidir alguma
    coisa.

    O SEXTO DE CADA FAIXA É O QUE FAZ O TÍTULO DECIDIR ALGUMA COISA
    ----------------------------------------------------------------
    Um em cada seis tem entrega de sobra para o nível de CIMA e título de menos:
    o Nível 1 com uma entrega (o mínimo do intermediário), o Nível 2 com cinco a
    sete (o mínimo do avançado). São pessoas reais da escola, as que já
    entregaram e ainda não passaram pela banca seguinte.

    **Sem elas a regra do título seria decorativa neste mundo**, porque a
    contagem de entregas já barraria exatamente quem o título barra, e o guarda
    do [INV-ENC-J5] ficaria verde com a regra APAGADA do motor. Foi assim que ele
    ficou na primeira prova por mutação, em 07/09/2026: com todo Nível 1 em zero,
    a sabotagem do título atravessou a simulação inteira sem um vermelho.
    """
    if titulo == PerfilProfissional.Titulo.NIVEL_3:
        veterano = sorteio.random() < 0.34
        return sorteio.randint(5, 9) if veterano else sorteio.randint(0, 4)
    if titulo == PerfilProfissional.Titulo.NIVEL_2:
        return sorteio.choice([0, 0, 0, 1, 2, sorteio.randint(5, 7)])
    return sorteio.choice([0, 0, 0, 0, 0, 1])


def _abandonos(titulo, sorteio, t_zero):
    """A lista de abandonos, que só o nível avançado consulta (plano §6.1).

    Só os Nível 3 a recebem porque só neles ela muda alguma coisa, e um dado que
    não muda nada é ruído no cenário. Metade dos sorteados abandonou dentro da
    janela de 90 dias e metade muito antes: as duas metades precisam existir para
    o guarda distinguir "a janela funciona" de "a lista derruba todo mundo".
    """
    if titulo != PerfilProfissional.Titulo.NIVEL_3 or sorteio.random() >= 0.4:
        return []
    dias = sorteio.choice([10, 40, 200, 300])
    return [(t_zero - timedelta(days=dias)).isoformat()]


def _temperamento(sorteio):
    """Um aluno de verdade: aceita, passa, pega, propõe, cede ou some.

    Os pesos são POR HORA SIMULADA, e por isso parecem baixos: quem aceita com
    0,20 por hora decide em menos das três horas úteis da oferta na maioria das
    vezes. **O caminho do silêncio é o mais provável de todos, e é de propósito**,
    porque silêncio é o desfecho comum de qualquer fila de oportunidade, e é dele
    que saem as coisas que este simulador precisa ver acontecer: a oferta que
    vence, a pausa automática dos três silêncios, o projeto que ninguém pegou em
    24h e vira chamada aberta, a reserva do Mural que caduca e a proposta que
    morre sem resposta.
    """
    return Temperamento(
        p_aceita=sorteio.uniform(0.015, 0.12),
        # PASSAR É MAIS PROVÁVEL DO QUE ACEITAR, e a diferença tem razão de
        # experimento: a reclassificação da lei §6.11 exige DOIS "ainda não me
        # sinto pronto" na MESMA encomenda, e é o único mecanismo do livro de
        # regras que só aparece quando a mesma peça passa por várias mãos. Com as
        # duas chances iguais, o mundo produzia cinco passes desse motivo
        # espalhados por vinte encomendas, e a reclassificação nunca acontecia.
        p_passa=sorteio.uniform(0.03, 0.22),
        # "Ainda não me sinto pronto" entra duas vezes de propósito: é o único
        # dos quatro com consequência mecânica (a reclassificação do plano
        # §6.11), e um cenário em que ele quase nunca sai nunca a produziria.
        motivo_preferido=sorteio.choice(
            [
                Oferta.MotivoDoPasse.SEM_TEMPO,
                Oferta.MotivoDoPasse.VALOR_BAIXO,
                Oferta.MotivoDoPasse.NAO_CURTO,
                Oferta.MotivoDoPasse.NAO_ME_SINTO_PRONTO,
                Oferta.MotivoDoPasse.NAO_ME_SINTO_PRONTO,
            ]
        ),
        # A MÃO NO INTERRUPTOR É RARA, e a raridade é regra do experimento,
        # não estética. `gestos.religar` ZERA o contador de silêncios
        # consecutivos, então uma turma que pausa e volta o tempo todo
        # apaga sozinha a pausa automática dos três silêncios (plano §6.3)
        # antes de ela poder acontecer — e o simulador ficaria verde sem
        # nunca ter visto esse mecanismo funcionar.
        p_pausa=sorteio.uniform(0.0, 0.0015),
        p_religa=sorteio.uniform(0.05, 0.30),
        # Dias, não horas: o prazo de produção da lei §6 é de 3, 7 ou 14
        # dias. Um aluno que ficasse livre em seis horas devolveria a vaga
        # rápido demais, e a fila nunca ficaria apertada — que é exatamente
        # o estado em que os invariantes de justiça correm risco.
        horas_de_trabalho=sorteio.randint(36, 110),
        # O MURAL. A chance é alta porque o Mural é ATIVO: o projeto fica na
        # prateleira e é o aluno que vai lá pegar. Com uma chance baixa, os
        # quinze projetos das duas pistas de cima ficariam parados a simulação
        # inteira e o relógio da reserva nunca decidiria nada.
        p_pega_no_mural=sorteio.uniform(0.05, 0.35),
        # O prazo que este aluno pede, em dias. O banco exige pelo menos um
        # (`proposta_tem_prazo`), e o teto é o do cartão mais caro da lei §6.6.
        prazo_pedido=sorteio.randint(2, 14),
        **_jeito_de_negociar(sorteio, NA_MESA_DO_ALUNO),
    )


# COMO CADA LADO SE PORTA NA MESA, EM TRÊS FEITIOS, e não numa faixa contínua.
# A primeira versão sorteava cada chance numa faixa, e o mundo saiu sem os
# desfechos que interessam: com todo mundo respondendo um pouco a cada hora,
# NENHUMA proposta chegou a vencer em oito dias e NENHUMA negociação esgotou as
# rodadas — os dois caminhos que o [INV-ENC-N7] e o [INV-ENC-N2] existem para
# medir. Três feitios com pesos garantem que os quatro desfechos da emenda §4.2
# aconteçam no mesmo mundo:
#
#   `fecha`     responde rápido e aceita: é de onde saem os acordos;
#   `regateia`  quase nunca aceita e quase sempre contrapõe: é de onde saem as
#               rodadas esgotadas, que mandam o projeto ao plantão;
#   `some`      quase não responde: é de onde saem a reserva que caduca, a
#               proposta que vence e o projeto que volta para o próximo.
#
# As chances são POR HORA SIMULADA. A validade da proposta é de 24 horas úteis,
# que numa janela de 14 horas por dia dá cerca de quarenta passos: uma chance de
# 0,03 por passo responde em 70% das vezes, e é essa fatia que sobra calada.
NA_MESA_DO_ALUNO = {
    "fecha": (0.25, 0.30, 0.03, 0.005),
    "regateia": (0.25, 0.02, 0.30, 0.010),
    "some": (0.04, 0.01, 0.01, 0.000),
}
NA_MESA_DO_CLIENTE = {
    "fecha": (0.20, 0.05, 0.005),
    "regateia": (0.02, 0.25, 0.010),
    "some": (0.01, 0.01, 0.000),
}

# Quatro em dez somem, e é o feitio mais comum de propósito: silêncio é o
# desfecho mais frequente de qualquer negociação de valor baixo, e é dele que
# saem as três coisas que este simulador precisa ver.
FEITIOS = ["fecha"] * 3 + ["regateia"] * 3 + ["some"] * 4


def _jeito_de_negociar(sorteio, mesa):
    """As quatro chances do aluno na mesa, pelo feitio sorteado."""
    p_propoe, p_aceita, p_contrapropoe, p_desiste = mesa[sorteio.choice(FEITIOS)]
    return {
        "p_propoe": p_propoe,
        "p_aceita_a_contraproposta": p_aceita,
        "p_contrapropoe": p_contrapropoe,
        "p_desiste": p_desiste,
    }


def _cliente(sorteio):
    """O outro lado da mesa, sorteado por projeto.

    Os três feitios são os mesmos do aluno, e pela mesma razão. O que mais
    importa aqui é o `some`: o cliente calado é quem manda o projeto ao plantão
    em vez de ao próximo aluno, que é o [INV-ENC-N7], e é o único jeito de esse
    caminho acontecer sem alguém escrevê-lo à mão.
    """
    p_aceita, p_contrapropoe, p_desiste = NA_MESA_DO_CLIENTE[sorteio.choice(FEITIOS)]
    return Cliente(
        p_aceita=p_aceita,
        p_contrapropoe=p_contrapropoe,
        p_desiste=p_desiste,
    )
