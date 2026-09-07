"""O povoado do simulador: cem alunos, trinta encomendas e um relógio de mentira.

Este arquivo MONTA o mundo. Ele não julga nada, não decide quem recebe oferta e
não sabe o que é justiça: quem julga é `test_simulador_de_justica.py`, e quem
decide é o motor. É a mesma separação do `tests/conftest.py` da célula, e ela
importa mais ainda aqui: uma fábrica que soubesse a regra faria o simulador
medir a própria resposta.

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
- **O DIA é o de amanhã**, e não uma data escrita à mão, por duas razões que se
  somam. `Oferta.oferecida_em` é `auto_now_add`, e a restrição
  `oferta_expira_depois_de_oferecida` compara os dois: com um `t_zero` no
  passado, toda oferta do simulador nasceria já vencida para o banco. E uma data
  fixa no futuro fica vermelha sozinha no dia em que o calendário a alcança
  (`armadilhas/323`, medida nesta célula).

`Encomenda.criada_em` também é `auto_now_add`, e é dele que sai o relógio das 24h
do [INV-ENC-J9]. Por isso a fábrica de encomendas escreve a coluna com o instante
SIMULADO da chegada, por `update()`: sem isso, uma encomenda da terceira onda
nasceria com dois dias de fila e viraria chamada aberta no primeiro tique, sem
nenhum aluno ter tido a chance de vê-la.

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

from apps.encomendas.models import Encomenda, Oferta, PerfilProfissional

# A semente. Trocar este número troca o mundo inteiro; ele existe para que o
# vermelho de amanhã seja o mesmo vermelho de hoje.
SEMENTE = 20260907

QUANTOS_ALUNOS = 100
QUANTAS_ENCOMENDAS = 30

# Os cem alunos, por faixa. A pirâmide é a da escola de verdade: quase todo mundo
# acabou de sair do Nível 1, e Nível 3 é raro. `SEM_TITULO` são os perfis que
# existem mas nunca passaram pelo professor (lei §3.6) — eles ficam abaixo de
# tudo, e o simulador os carrega para provar que ninguém recebe oferta por
# descuido.
SEM_TITULO = 8
NIVEL_1 = 56
NIVEL_2 = 27
NIVEL_3 = 9

# As trinta encomendas, por nível, em cada uma das três ondas de chegada.
# Avançado é o nível que quase ninguém alcança nos primeiros meses, e a fila
# precisa mostrar o que faz com ele.
POR_ONDA = {
    Encomenda.Nivel.INICIANTE: 5,
    Encomenda.Nivel.INTERMEDIARIO: 3,
    Encomenda.Nivel.AVANCADO: 2,
}
ONDAS = 3


@dataclass(frozen=True)
class Temperamento:
    """Como ESTE aluno se comporta diante de uma oferta, sorteado uma vez só.

    Sortear o temperamento por aluno, e não a cada oferta, é o que faz a
    simulação ter gente dentro dela: existe quem aceita quase sempre, quem passa
    quase sempre, e quem some. É de gente que some que nascem os três silêncios
    da pausa automática, e é de gente que passa que nasce a reclassificação.
    """

    p_aceita: float
    p_passa: float
    motivo_preferido: str
    p_pausa: float
    p_religa: float
    horas_de_trabalho: int


@dataclass
class Povoado:
    """O mundo montado, e as duas coisas que o simulador precisa lembrar dele.

    `chegada` guarda o instante SIMULADO em que cada encomenda entrou na fila, e
    `lugar_na_fila` guarda a `data_entrada_fila` de cada perfil no minuto zero. As
    duas existem porque o guarda precisa de uma medida INDEPENDENTE do banco: o
    [INV-ENC-J9] se mede contra a chegada, e o [INV-ENC-J4] se mede contra o
    lugar original.
    """

    site_id: str
    t_zero: datetime
    sorteio: random.Random
    perfis: list
    temperamentos: dict
    encomendas: list
    chegada: dict
    lugar_na_fila: dict


@pytest.fixture
def t_zero():
    """A abertura da janela de amanhã, no fuso da célula, devolvida em UTC."""
    fuso = ZoneInfo(settings.TIME_ZONE)
    amanha = datetime.now(tz=fuso).date() + timedelta(days=1)
    janela_abre = time(8, 0)
    return datetime.combine(amanha, janela_abre, tzinfo=fuso)


@pytest.fixture
def povoado(semeado, criar_perfil, criar_encomenda, t_zero):
    """Cem alunos e trinta encomendas em três ondas, sempre os mesmos.

    Os perfis nascem antes de qualquer encomenda porque é assim que a escola
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

    encomendas = []
    chegada = {}
    for onda in range(ONDAS):
        for minuto, nivel in enumerate(_niveis_da_onda()):
            # UM MINUTO ENTRE UMA E OUTRA, e o minuto é o que torna esta
            # simulação reproduzível. O motor varre `na_fila` ordenando só por
            # `criada_em` (plano §7.4); com dez encomendas no mesmo instante, a
            # ordem da varredura seria a que o banco devolvesse, e o placar
            # mudaria a cada rodada mesmo com a semente fixa.
            quando = t_zero + timedelta(days=onda, minutes=minuto)
            encomenda = criar_encomenda(nivel=nivel)
            # A coluna é `auto_now_add`, e é dela que sai o relógio das 24h do
            # [INV-ENC-J9]. Sem esta linha a onda de amanhã nasceria vencida.
            Encomenda.objects.filter(pk=encomenda.pk).update(criada_em=quando)
            encomenda.criada_em = quando
            encomendas.append(encomenda)
            chegada[encomenda.pk] = quando
    assert len(encomendas) == QUANTAS_ENCOMENDAS

    return Povoado(
        site_id=semeado,
        t_zero=t_zero,
        sorteio=sorteio,
        perfis=perfis,
        temperamentos=temperamentos,
        encomendas=encomendas,
        chegada=chegada,
        lugar_na_fila={p.id: p.data_entrada_fila for p in perfis},
    )


def _niveis_da_onda():
    """Os dez níveis de uma onda, na mesma ordem sempre.

    Intercalados, e não em blocos: dez iniciantes seguidas fariam a fila resolver
    tudo o que é fácil antes de encostar no que é difícil, e o cenário perderia
    justamente o embate que interessa.
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
    """Um aluno de verdade: aceita, passa ou some, com pesos próprios.

    Os pesos são POR HORA SIMULADA, e por isso parecem baixos: quem aceita com
    0,20 por hora decide em menos das três horas úteis da oferta na maioria das
    vezes. **O terceiro caminho é o mais provável de todos, e é de propósito** —
    silêncio é o desfecho comum de qualquer fila de oportunidade, e é dele que
    saem as coisas que este simulador precisa ver acontecer: a oferta que vence,
    a pausa automática dos três silêncios e a encomenda que ninguém pegou em 24h
    e vira chamada aberta.
    """
    return Temperamento(
        p_aceita=sorteio.uniform(0.015, 0.12),
        p_passa=sorteio.uniform(0.015, 0.12),
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
    )
