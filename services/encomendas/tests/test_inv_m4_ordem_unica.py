"""A ordem do Mural é só a antiguidade do projeto.

Produto: `PLANO-AREA-DE-NEGOCIACAO.md` §3.3 e §8. Lei:
`docs/decisoes/DECISAO-fila-do-primeiro-dolar.md` §9, critério de morte 2.

A ORDEM É DELIBERADAMENTE BURRA
--------------------------------
*"Os mais antigos primeiro. É a única ordem que existe, e ela é deliberadamente
burra: qualquer ordem inteligente (destaque, peso, relevância) é a segunda regra
de ordem que o critério de morte 2 proíbe."*

A tentação é óbvia e chega sempre pela porta da frente, com um bom motivo: pôr
os projetos que pagam mais em cima "para o aluno ganhar mais", pôr os de prazo
curto em cima "para o cliente não esperar", pôr os do nível do aluno em cima
"porque é mais relevante". Cada uma dessas é uma régua nova, e a segunda régua é
a que ninguém consegue explicar depois quando um aluno pergunta por que o
projeto dele nunca aparece em cima.

O `id` NÃO É UMA SEGUNDA REGRA
-------------------------------
Ele só é consultado quando dois projetos nasceram no mesmo microssegundo, e
existe para a lista ser uma função de verdade: sem ele, dois cartões empatados
trocariam de lugar entre dois carregamentos, conforme a ordem em que o banco
devolvesse as linhas. É o mesmo desempate, pela mesma razão, do terceiro termo
do `motor.CHAVE_DA_ORDEM`. A diferença entre desempate e regra é que o
desempate nunca decide nada que os termos da lei já não tenham decidido.
"""

from datetime import datetime, timedelta, timezone as fuso

from apps.encomendas import mural
from apps.encomendas.models import Encomenda

SITE = "escola-a"
AGORA = datetime.now(tz=fuso.utc)


def _envelhecer(projeto, *, dias):
    """Recua `criada_em` no banco. É `auto_now_add`, então não se escolhe no create."""
    Encomenda.objects.filter(pk=projeto.pk).update(
        criada_em=projeto.criada_em - timedelta(days=dias)
    )
    projeto.refresh_from_db()
    return projeto


# ---------------------------------------------------------------------------
# 1. O MAIS ANTIGO PRIMEIRO
# ---------------------------------------------------------------------------


def test_o_mural_lista_do_mais_antigo_para_o_mais_novo(
    dois_no_mural, criar_projeto_no_mural
):
    """A regra inteira numa asserção, com os projetos criados fora de ordem.

    O `bru` é quem olha porque ele é Nível 3 com cinco entregas: é elegível aos
    três, e por isso a lista dele mede a ORDEM, e não a peneira.
    """
    _, bru = dois_no_mural
    novo = criar_projeto_no_mural(cliente="cli-novo")
    velho = _envelhecer(criar_projeto_no_mural(cliente="cli-velho"), dias=10)
    meio = _envelhecer(criar_projeto_no_mural(cliente="cli-meio"), dias=5)

    lista = mural.listar(bru.id, AGORA, site_id=SITE)

    assert [p.pk for p in lista] == [velho.pk, meio.pk, novo.pk]


def test_o_nivel_nao_reordena_nada(dois_no_mural, criar_projeto_no_mural):
    """O Avançado mais novo continua embaixo do Intermediário mais velho.

    É a ordenação "inteligente" mais tentadora de todas, porque o projeto
    Avançado costuma valer mais. A lista não sabe disso, e é assim que ela deve
    ficar.
    """
    _, bru = dois_no_mural
    intermediario = _envelhecer(
        criar_projeto_no_mural(nivel=Encomenda.Nivel.INTERMEDIARIO), dias=3
    )
    avancado = criar_projeto_no_mural(nivel=Encomenda.Nivel.AVANCADO, cliente="cli-2")

    lista = mural.listar(bru.id, AGORA, site_id=SITE)

    assert [p.pk for p in lista] == [intermediario.pk, avancado.pk]


def test_o_preco_de_referencia_nao_reordena_nada(dois_no_mural, criar_projeto_no_mural):
    """Preço alto não sobe na lista, e é isso que separa o Mural de um leilão."""
    _, bru = dois_no_mural
    barato_e_velho = _envelhecer(criar_projeto_no_mural(cliente="cli-1"), dias=2)
    caro_e_novo = criar_projeto_no_mural(cliente="cli-2")
    Encomenda.objects.filter(pk=caro_e_novo.pk).update(preco_cents=900_00)
    Encomenda.objects.filter(pk=barato_e_velho.pk).update(preco_cents=1_00)

    lista = mural.listar(bru.id, AGORA, site_id=SITE)

    assert [p.pk for p in lista] == [barato_e_velho.pk, caro_e_novo.pk]


def test_a_chamada_aberta_entra_na_mesma_ordem_e_nao_na_frente(
    semeado, criar_perfil, criar_projeto_no_mural, criar_encomenda
):
    """O projeto que veio da fila não fura a fila do Mural.

    A tentação aqui tem um motivo bom ("ele já esperou 24 horas"), e é
    exatamente por isso que ela precisa de um guarda: dar prioridade a quem
    esperou é a segunda regra de ordem com outro nome.
    """
    from apps.encomendas import tique

    bru = criar_perfil(
        "pes-bru",
        entrada=AGORA - timedelta(days=20),
        titulo="nivel_3",
        entregas=5,
    )
    velho_do_mural = _envelhecer(criar_projeto_no_mural(cliente="cli-1"), dias=10)
    da_fila = criar_encomenda(cliente="cli-2")
    depois = da_fila.criada_em + timedelta(days=2)
    tique.rodar(depois, site_id=SITE)
    da_fila.refresh_from_db()
    assert da_fila.status == Encomenda.Status.ABERTA

    lista = mural.listar(bru.id, depois, site_id=SITE)

    assert [p.pk for p in lista] == [velho_do_mural.pk, da_fila.pk]


def test_a_lista_e_estavel_entre_duas_leituras(dois_no_mural, criar_projeto_no_mural):
    """O desempate por `id` fazendo o trabalho dele.

    Dois projetos criados no mesmo instante têm de sair na MESMA ordem sempre.
    Sem o desempate, a ordem viria do planejador do PostgreSQL e mudaria sem
    aviso, entre dois carregamentos da mesma tela.
    """
    _, bru = dois_no_mural
    primeiro = criar_projeto_no_mural(cliente="cli-1")
    segundo = criar_projeto_no_mural(cliente="cli-2")
    Encomenda.objects.filter(pk__in=[primeiro.pk, segundo.pk]).update(
        criada_em=primeiro.criada_em
    )

    leituras = {
        tuple(p.pk for p in mural.listar(bru.id, AGORA, site_id=SITE)) for _ in range(5)
    }

    assert len(leituras) == 1
    assert len(next(iter(leituras))) == 2
