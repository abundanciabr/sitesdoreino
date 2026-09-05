"""Os interruptores da economia — ligar, desligar, e o "nunca retroativo".

A lei §10.5 diz que ajustar a economia é *"UPDATE + versão, anunciado e nunca
retroativo"*, e que exigir PR de código para isso é **critério de morte**. Até
31/08/2026 as três palavras tinham pesos muito diferentes: `ativa` e `versao`
eram colunas, e o "nunca retroativo" era só uma frase no topo do `motor.py`. Este
arquivo mede as três como MECANISMO.

O teste que mais importa aqui é `test_ligar_hoje_nao_paga_o_que_aconteceu_ontem`:
sem ele, ligar uma regra num dia movimentado pagaria toda a fila represada e todo
evento reentregue, e o aluno veria um número saltar sem ter feito nada.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.gamificacao.interruptores import (
    CRISTAIS_SEM_EFEITO,
    SEM_CREDITO,
    SEM_FATO_QUE_ALIMENTA,
    SEM_PRODUTOR,
    SO_POR_CONCESSAO_MANUAL,
    ConquistaDesconhecida,
    RegraDesconhecida,
    impedimentos_da_conquista,
    impedimentos_de,
    listar,
    listar_conquistas,
    mudar,
    mudar_conquista,
)
from apps.gamificacao.models import (
    ConquistaDefinicao,
    LancamentoDeXP,
    PerfilJogador,
    RegraDePontuacao,
)
from apps.gamificacao.motor import aplicar

SITE = "site-de-teste"
AUTOR = "pes-autor"


def _regra(**campos) -> RegraDePontuacao:
    base = {
        "slug": "sugestao-criada",
        "site_id": SITE,
        "evento_gatilho": "sugestao.criada.v1",
        "beneficiario": RegraDePontuacao.Beneficiario.ATOR,
        "pontos": 10,
        "cristais": 0,
        "acoes_cheias_por_dia": 0,
        "quarentena_horas": 0,
        "ativa": False,
    }
    base.update(campos)
    return RegraDePontuacao.objects.create(**base)


def _envelope(quando=None, **campos) -> dict:
    envelope = {
        "event": "sugestao.criada",
        "version": 1,
        "event_id": str(uuid.uuid4()),
        "occurred_at": (quando or timezone.now()).isoformat(),
        "ator_id": AUTOR,
        "data": {"site_id": SITE, "suggestion_id": 1, "autor_id": "id-local-da-caixa"},
    }
    envelope.update(campos)
    return envelope


# --------------------------------------------------- ligar, desligar, versionar


@pytest.mark.django_db
def test_ligar_carimba_a_data_e_sobe_a_versao():
    """As três coisas que a lei manda acontecerem juntas."""
    _regra()

    regra = mudar(
        site_id=SITE, slug="sugestao-criada", ativa=True, agora=timezone.now()
    )

    assert regra.ativa is True
    assert regra.versao == 2, "a lei manda UPDATE + versão"
    assert regra.vigente_desde is not None, "sem data não há 'nunca retroativo'"


@pytest.mark.django_db
def test_ligar_duas_vezes_nao_gasta_versao():
    """Dois cliques no mesmo botão não são duas mudanças de economia.

    Sem isto a versão inflaria sozinha, e o histórico contaria mudanças que
    ninguém fez — inclusive por um navegador reenviando o POST.
    """
    _regra()
    agora = timezone.now()
    primeira = mudar(site_id=SITE, slug="sugestao-criada", ativa=True, agora=agora)
    segunda = mudar(
        site_id=SITE,
        slug="sugestao-criada",
        ativa=True,
        agora=agora + timedelta(hours=1),
    )

    assert primeira.versao == segunda.versao == 2
    assert primeira.vigente_desde == segunda.vigente_desde


@pytest.mark.django_db
def test_desligar_e_religar_redefine_a_data():
    """A janela desligada não se paga depois — seria retroatividade pelos fundos."""
    _regra()
    ontem = timezone.now() - timedelta(days=1)
    mudar(site_id=SITE, slug="sugestao-criada", ativa=True, agora=ontem)
    mudar(site_id=SITE, slug="sugestao-criada", ativa=False, agora=ontem)

    hoje = timezone.now()
    regra = mudar(site_id=SITE, slug="sugestao-criada", ativa=True, agora=hoje)

    assert regra.vigente_desde == hoje
    assert regra.versao == 4, "três mudanças de estado, três versões"


@pytest.mark.django_db
def test_slug_desconhecido_recusa_em_vez_de_inventar():
    """Aqui a falha é FECHADA, ao contrário das leituras desta célula.

    Inventar em silêncio qual regra o mantenedor quis ligar é pior que recusar:
    ele clicaria em "ligar" e outra coisa passaria a valer.
    """
    with pytest.raises(RegraDesconhecida):
        mudar(
            site_id=SITE, slug="regra-que-nao-existe", ativa=True, agora=timezone.now()
        )


@pytest.mark.django_db
def test_o_banco_recusa_regra_ligada_sem_data():
    """O invariante é do BANCO, não da disciplina de quem escreve o próximo UPDATE.

    Este é o estado exato em que o motor voltaria a pagar retroativo em silêncio,
    e é por isso que ele não pode existir nem por um `update()` direto.
    """
    _regra()
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            RegraDePontuacao.objects.filter(slug="sugestao-criada").update(
                ativa=True, vigente_desde=None
            )


# ------------------------------------------------------- o "nunca retroativo"


@pytest.mark.django_db
def test_ligar_hoje_nao_paga_o_que_aconteceu_ontem():
    """O CORAÇÃO desta entrega, e o que não tinha mecanismo nenhum até aqui.

    Cenário real: a fila de eventos represa (ou um evento é reentregue pelo lote
    de reentrega), o mantenedor liga a regra, e semanas de passado viram XP no
    segundo do clique. O aluno vê o número saltar sem ter feito nada, e ninguém
    descobre olhando a tela.
    """
    _regra()
    mudar(site_id=SITE, slug="sugestao-criada", ativa=True, agora=timezone.now())

    ontem = timezone.now() - timedelta(days=1)
    assert aplicar(_envelope(quando=ontem), SITE) == []
    assert LancamentoDeXP.objects.count() == 0


@pytest.mark.django_db
def test_o_que_acontece_depois_de_ligar_paga_normalmente():
    """A outra metade: a trava do retroativo não pode virar trava de tudo."""
    _regra()
    mudar(
        site_id=SITE,
        slug="sugestao-criada",
        ativa=True,
        agora=timezone.now() - timedelta(minutes=1),
    )

    assert len(aplicar(_envelope(), SITE)) == 1
    assert PerfilJogador.objects.get(pessoa_id=AUTOR).xp_total == 10


@pytest.mark.django_db
def test_regra_desligada_continua_sem_pagar_mesmo_com_data():
    """A data não substitui o interruptor; ela o acompanha."""
    _regra(ativa=True, vigente_desde=timezone.now() - timedelta(days=1))
    mudar(site_id=SITE, slug="sugestao-criada", ativa=False, agora=timezone.now())

    assert aplicar(_envelope(), SITE) == []


# ------------------------------------------------------------- os impedimentos


@pytest.mark.django_db
def test_regra_sem_quem_publique_o_assunto_avisa_antes_do_clique():
    """`banca.decidida` ainda não existe: é a Fase 5 da sala de aula, e ninguém
    o publica hoje. Uma regra para ele ligaria sem número nenhum mexer, e a tela
    precisa dizer isso ANTES do clique — um zero sem explicação parece defeito
    da tela.

    Até 05/09/2026 o exemplo aqui era `aula.concluida`; ele deixou esta lista
    no dia em que a sala de aula passou a publicá-lo (teste abaixo).
    """
    regra = _regra(slug="banca-decidida", evento_gatilho="banca.decidida.v1")

    assert impedimentos_de(regra) == [SEM_PRODUTOR]


@pytest.mark.django_db
def test_a_aula_concluida_tem_quem_a_publique_e_nada_a_impede():
    """A tomada da sala de aula está ligada nas duas pontas: o consumidor assina
    o assunto e o handler credita. A tela do mantenedor não pode continuar
    dizendo "ninguém avisa isto" depois de a célula `cursos` passar a avisar."""
    regra = _regra(slug="aula-concluida", evento_gatilho="aula.concluida.v1")

    assert impedimentos_de(regra) == []


@pytest.mark.django_db
def test_o_quiz_avisa_que_chega_mas_nao_credita():
    """O assunto É entregue, e mesmo assim ninguém recebe ponto.

    O contrato do quiz identifica a pessoa por e-mail, e esta célula só credita
    id de plataforma. O motivo está declarado ao lado do handler que não credita.
    """
    regra = _regra(slug="quiz-aprovado", evento_gatilho="quiz.completado.v1")

    assert impedimentos_de(regra) == [SEM_CREDITO]


@pytest.mark.django_db
def test_regra_que_promete_cristais_avisa_que_eles_nao_saem():
    """O XP sai; os Cristais não. E a tela diz isso antes, não depois.

    `MovimentoDeCristais.Origem` é vocabulário FECHADO e nenhuma das cinco
    origens é "regra de pontuação" — mexer nele é mexer no que o [INV-GAM1]
    protege, e é decisão do mantenedor.
    """
    regra = _regra(slug="sugestao-implementada", cristais=5)

    assert impedimentos_de(regra) == [CRISTAIS_SEM_EFEITO]


@pytest.mark.django_db
def test_regra_boa_nao_inventa_impedimento():
    """Lista vazia significa: ligar vai funcionar de verdade."""
    assert impedimentos_de(_regra()) == []


@pytest.mark.django_db
def test_listar_devolve_ligadas_e_desligadas():
    """A tela mostra o que ele PODE ligar, não só o que já vale."""
    _regra(slug="a-desligada", ativa=False)
    _regra(slug="b-ligada", ativa=True, vigente_desde=timezone.now())

    assert [r.slug for r in listar(SITE)] == ["a-desligada", "b-ligada"]


# ------------------------------- o crachá: nada de crédito a pessoa fantasma


@pytest.mark.django_db
def test_evento_sem_o_cracha_da_plataforma_nao_credita_ninguem():
    """FAIL-CLOSED, e é o conserto do defeito que quase ligou uma economia falsa.

    Até 31/08/2026 o motor caía em `data.autor_id` quando o envelope não trazia
    `ator_id` — e aquele campo é o id LOCAL da célula `sugestoes`, cunhado
    separadamente do id da plataforma ([INV-SUG11]). Como `Pessoa` é chaveada por
    `id_da_plataforma`, o XP ia para uma pessoa que a tela do aluno nunca acharia:
    ledger enchendo, tela em zero, nada dando erro.

    Não pagar é recuperável (o motivo fica no log e o evento pode ser
    reprocessado). Pagar ao fantasma não é: ninguém descobre olhando.
    """
    _regra()
    mudar(
        site_id=SITE,
        slug="sugestao-criada",
        ativa=True,
        agora=timezone.now() - timedelta(minutes=1),
    )

    envelope = _envelope()
    del envelope["ator_id"]  # a forma EXATA que `sugestao.criada.v1` permitia

    assert aplicar(envelope, SITE) == []
    assert LancamentoDeXP.objects.count() == 0
    assert not PerfilJogador.objects.exists(), "nenhuma Pessoa fantasma nasceu"


# ---------------------------------------------------------------------------
# O SEGUNDO INTERRUPTOR: as conquistas
# ---------------------------------------------------------------------------
# A diferença que estes testes existem para travar é UMA, e foi decidida pelo
# mantenedor em 01/09/2026: ligar uma conquista NÃO carimba data, porque
# reconhecer quem já cumpriu o critério é o comportamento que ele escolheu. Numa
# regra de pontuação, a mesma ausência seria o bug mais caro desta célula.


def _conquista(**campos) -> ConquistaDefinicao:
    base = {
        "slug": "primeira-obra",
        "site_id": SITE,
        "nome": "Primeira obra",
        "descricao": "A primeira peça terminada.",
        "classe": ConquistaDefinicao.Classe.MEDALHA,
        "familia": ConquistaDefinicao.Familia.OFICIO,
        "criterio": {"tipo": "primeira_vez", "assunto": "obra"},
        "pontos": 50,
        "cristais": 5,
        "ativa": False,
    }
    base.update(campos)
    return ConquistaDefinicao.objects.create(**base)


@pytest.mark.django_db
def test_ligar_uma_conquista_nao_carimba_data_nenhuma():
    """A decisão do mantenedor virando ausência de campo.

    Numa regra de pontuação, ligar carimba `vigente_desde` e é isso que impede
    pagar o passado. Aqui esse carimbo seria o mecanismo de negar a "Primeira
    obra" a quem já fez a primeira obra — e ninguém faz duas estreias. Este teste
    existe para que ninguém "conserte" a ausência daqui a seis meses achando que
    foi esquecimento.
    """
    conquista = _conquista()

    depois = mudar_conquista(site_id=SITE, slug="primeira-obra", ativa=True)

    assert depois.ativa is True
    assert depois.versao == conquista.versao + 1
    assert not hasattr(depois, "vigente_desde")


@pytest.mark.django_db
def test_dois_cliques_no_mesmo_botao_nao_inflam_a_versao():
    _conquista()

    primeira = mudar_conquista(site_id=SITE, slug="primeira-obra", ativa=True)
    segunda = mudar_conquista(site_id=SITE, slug="primeira-obra", ativa=True)

    assert primeira.versao == segunda.versao


@pytest.mark.django_db
def test_conquista_desconhecida_recusa_em_vez_de_inventar():
    with pytest.raises(ConquistaDesconhecida):
        mudar_conquista(site_id=SITE, slug="nao-existe", ativa=True)


@pytest.mark.django_db
def test_os_marcos_vem_primeiro_na_lista():
    """A hierarquia da lei virando ordem de tela.

    Realidade > Criação > Maestria > Comunidade > XP. Uma tela que lista o
    andaime acima da espinha ensina a ordem errada a quem a lê todo dia.
    """
    # Os slugs são escolhidos CONTRA a ordem alfabética de propósito: com
    # "aaa-marco" e "zzz-medalha", ordenar só por slug daria o mesmo resultado, e
    # o teste passaria sabotado — provando nada. Medido: com a chave de classe
    # removida, a asserção abaixo fica vermelha.
    _conquista(slug="aaa-medalha", nome="Medalha")
    _conquista(
        slug="zzz-marco",
        nome="Marco",
        classe=ConquistaDefinicao.Classe.MARCO,
        familia=ConquistaDefinicao.Familia.CARREIRA,
        criterio={"tipo": "manual"},
        pontos=0,
        cristais=0,
    )

    ordem = [c.slug for c in listar_conquistas(SITE)]

    assert ordem == ["zzz-marco", "aaa-medalha"]


@pytest.mark.django_db
def test_o_marco_nunca_tem_impedimento():
    """Ele não depende de conta automática: depende de alguém mandar a prova."""
    marco = _conquista(
        slug="primeiro-cliente",
        classe=ConquistaDefinicao.Classe.MARCO,
        familia=ConquistaDefinicao.Familia.CARREIRA,
        criterio={"tipo": "manual"},
        pontos=0,
        cristais=0,
    )

    assert impedimentos_da_conquista(marco) == []


@pytest.mark.django_db
def test_a_medalha_com_conta_de_verdade_nao_tem_impedimento_nenhum():
    """Desde 01/09/2026 o motor existe, e o aviso de que ele faltava SAIU.

    Um aviso que mente é pior que nenhum: a tela seguiria dizendo "isto não vai
    conceder nada" sobre uma medalha que cai na hora. Este guarda é o que impede
    aquele aviso de sobreviver ao motivo dele.
    """
    medalha = _conquista(criterio={"tipo": "xp_acumulado", "alvo": 300})

    assert impedimentos_da_conquista(medalha) == []


@pytest.mark.django_db
def test_criterio_que_nada_alimenta_continua_avisando():
    """`primeira_vez` espera a plataforma saber dizer que uma obra ficou pronta
    (degrau 19); a sequência semanal e as missões esperam os degraus 10 e 11.

    A lista encolhe sozinha à medida que a escada sobe — e é por isso que ela é
    medida contra o que EXISTE, não contra o que alguém se lembrou de escrever.
    """
    obra = _conquista(
        slug="primeira-obra-2", criterio={"tipo": "primeira_vez", "assunto": "obra"}
    )
    sequencia = _conquista(
        slug="quatro-semanas", criterio={"tipo": "semanas_de_sequencia", "alvo": 4}
    )

    assert impedimentos_da_conquista(obra) == [SEM_FATO_QUE_ALIMENTA]
    assert impedimentos_da_conquista(sequencia) == [SEM_FATO_QUE_ALIMENTA]


@pytest.mark.django_db
def test_a_medalha_das_dez_forjas_parou_de_dizer_que_falta_o_fato():
    """A Forja nasceu em 01/09/2026 (degrau 14), e o aviso saiu junto.

    Este guarda é o que impede o aviso de sobreviver ao motivo dele. Um aviso
    que mente é pior que nenhum: a tela do mantenedor seguiria dizendo "ligar
    isto não vai conceder nada" sobre a única medalha que celebra insistência,
    e ele não a ligaria nunca.
    """
    forjas = _conquista(
        slug="dez-forjas", criterio={"tipo": "forjas_seladas", "alvo": 10}
    )

    assert impedimentos_da_conquista(forjas) == []


@pytest.mark.django_db
def test_a_medalha_manual_diz_que_so_sai_pela_mao_da_equipe():
    medalha = _conquista(
        slug="fundador",
        familia=ConquistaDefinicao.Familia.EPOCA,
        criterio={"tipo": "manual"},
    )

    assert impedimentos_da_conquista(medalha) == [SO_POR_CONCESSAO_MANUAL]
