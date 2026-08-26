"""A aba "EM ALTA" (V1.2, spec §10) — o ranking com peso de recência.

A fórmula, na mesma frase que o `participacao.py` carrega: **o calor de uma
ideia é a soma dos votos dela com peso de recência — voto dos últimos 7 dias
vale 3, voto do último mês vale 1, voto mais velho que um mês não conta.**

**Nenhuma asserção deste arquivo depende do relógio da máquina.** O guarda da
fórmula chama `sugestoes_ordenadas(..., agora=INSTANTE)` com um instante escrito
à mão e votos carimbados à mão: o mesmo código medido hoje, amanhã ou num
domingo de madrugada dá o mesmo resultado. Foi por isso que `agora` virou
parâmetro em vez de um `timezone.now()` lá dentro — ranking que só se mede
contra o relógio é ranking que apodrece sozinho.

Os guardas de BORDA (os que abrem a página de verdade) usam deslocamentos a
partir de um instante lido UMA vez pelo teste, sempre longe das fronteiras de 7
e 30 dias: eles medem a fiação (a aba existe, ordena a grade, custa o mesmo),
não a aritmética.

**Detalhe que decide se o arquivo mede alguma coisa:** `Voto.criado_em` é
`auto_now_add`, então a data só se escreve por `update()` DEPOIS do fato. Passar
`criado_em=` no `create()`/`bulk_create()` é ignorado em silêncio — todo voto
nasceria "de hoje" e o guarda ficaria verde sem nunca ter medido um degrau.
"""

import re
from datetime import datetime, timedelta
from datetime import timezone as tz

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.core.participacao import ORDEM_EM_ALTA, sugestoes_ordenadas
from apps.sugestoes.models import Categoria, Comentario, Identidade, Sugestao, Voto

pytestmark = pytest.mark.django_db

TITULO_DE_PECA = re.compile(r'<h3 class="peca-titulo"><a href="[^"]*">([^<]+)</a>')

# O instante contra o qual a fórmula é medida. Escrito à mão, e não derivado de
# `timezone.now()`: é ele que faz este arquivo dizer a mesma coisa para sempre.
INSTANTE = datetime(2026, 8, 25, 12, 0, tzinfo=tz.utc)

# Longe das fronteiras, de propósito. Um voto marcado exatamente em -7 dias
# mediria o `>=` do degrau, não a fórmula — e teste que mora em cima da
# fronteira fica vermelho por arredondamento no dia em que alguém mexer no fuso.
ONTEM = INSTANTE - timedelta(days=1)
HA_VINTE_DIAS = INSTANTE - timedelta(days=20)
HA_DUZENTOS_DIAS = INSTANTE - timedelta(days=200)

PEQUENO = 2
GRANDE = 20


def _corpo(pessoa, **query) -> str:
    endereco = reverse("quadro")
    if query:
        endereco += "?" + "&".join(f"{c}={v}" for c, v in query.items())
    resposta = pessoa.client.get(endereco)
    assert resposta.status_code == 200, resposta.status_code
    return resposta.content.decode()


@pytest.fixture
def votar_em(db):
    """N votos numa ideia, todos carimbados num instante escolhido pelo teste.

    **Cada voto vem de uma pessoa nova** porque a unicidade é do banco (um ator
    vota no máximo uma vez por sugestão, spec §8): dez votos do mesmo aluno
    seriam um voto só, e o guarda mediria a constraint achando que media o peso.

    **Escrito pelo ORM, como a fixture `plateia` do EVO-42, e pelo mesmo
    motivo.** O que se mede aqui é a ORDENAÇÃO; vinte logins dublados custariam
    segundos de suíte sem acrescentar nada à medição. Que o clique de verdade
    grava a linha que este ranking lê está provado à parte, pela jornada, em
    `test_inv_voto_pelo_endpoint.py` e em `test_o_rosto.py`.
    """
    proximo = iter(range(100_000))

    def _votar(sugestao: Sugestao, quantos: int, quando) -> None:
        marca = next(proximo)
        gente = Identidade.objects.bulk_create(
            [
                Identidade(email=f"votante-{marca}-{n}@exemplo.test")
                for n in range(quantos)
            ]
        )
        Voto.objects.bulk_create(
            [Voto(sugestao=sugestao, autor=pessoa) for pessoa in gente]
        )
        # O carimbo vem DEPOIS: `auto_now_add` sobrescreve qualquer `criado_em`
        # passado ao construtor, inclusive no `bulk_create`.
        Voto.objects.filter(sugestao=sugestao, autor__in=gente).update(criado_em=quando)

    return _votar


def _titulos_em_alta(quadro, **extra) -> list[str]:
    return [
        s.titulo
        for s in sugestoes_ordenadas(
            quadro, ordem=ORDEM_EM_ALTA, agora=INSTANTE, **extra
        )
    ]


# ---------------------------------------------------------------------------
# A fórmula, com datas fixas
# ---------------------------------------------------------------------------


def test_o_peso_de_recencia_desmancha_o_ranking_por_total_de_votos(
    caixa, quadro, votar_em
):
    """O caso que justifica a aba existir: o mesmo quadro, duas verdades.

    "Mais votadas" premia quem acumulou; "Em alta" premia quem está sendo votado
    agora. Se as duas listas saíssem iguais, a aba nova seria uma cópia com outro
    nome — e é isso que este guarda existe para não deixar acontecer.
    """
    veterana = caixa.publicar("Veterana com dez votos antigos")
    morna = caixa.publicar("Morna, votada no mês passado")
    quente = caixa.publicar("Quente, votada ontem")

    votar_em(veterana, 10, HA_DUZENTOS_DIAS)  # calor 10 × 0 = 0
    votar_em(morna, 5, HA_VINTE_DIAS)  # calor  5 × 1 = 5
    votar_em(quente, 3, ONTEM)  # calor  3 × 3 = 9

    assert _titulos_em_alta(quadro) == [
        "Quente, votada ontem",
        "Morna, votada no mês passado",
        "Veterana com dez votos antigos",
    ]
    # E a aba do lado continua contando cabeças, não datas.
    assert [s.titulo for s in sugestoes_ordenadas(quadro, ordem="mais-votadas")] == [
        "Veterana com dez votos antigos",
        "Morna, votada no mês passado",
        "Quente, votada ontem",
    ]


def test_o_voto_mais_velho_que_um_mes_nao_esquenta_nada(caixa, quadro, votar_em):
    """Um voto de ontem passa na frente de dez de um ano atrás.

    É a metade da fórmula que faz "em alta" significar alguma coisa: sem o zero
    depois de 30 dias, o calor seria o total de votos com outro nome, e a aba
    seria uma segunda cópia da que está do lado dela.
    """
    antiga = caixa.publicar("Dez votos do ano passado")
    nova = caixa.publicar("Um voto de ontem")

    votar_em(antiga, 10, HA_DUZENTOS_DIAS)
    votar_em(nova, 1, ONTEM)

    assert _titulos_em_alta(quadro) == ["Um voto de ontem", "Dez votos do ano passado"]


def test_ideia_sem_voto_nenhum_fica_atras_de_quem_tem_calor(caixa, quadro, votar_em):
    """`Coalesce` para zero, e não `NULL` — e a diferença é a aba inteira.

    No Postgres, `ORDER BY … DESC` põe `NULL` na FRENTE de qualquer número: sem
    o `Coalesce`, "Em alta" abriria mostrando exatamente as ideias em que
    ninguém votou, que é o oposto do que o nome promete.
    """
    caixa.publicar("Ninguém votou nesta")
    falada = caixa.publicar("Esta a turma votou ontem")
    votar_em(falada, 1, ONTEM)

    assert _titulos_em_alta(quadro) == [
        "Esta a turma votou ontem",
        "Ninguém votou nesta",
    ]


def test_o_calor_nao_e_multiplicado_pelos_comentarios(caixa, quadro, votar_em, aluno):
    """A armadilha que a subconsulta existe para fechar.

    A grade junta `votos` E `comentarios` na mesma consulta: com dois `JOIN`, o
    banco devolve o produto cartesiano das duas pernas. Os `Count(distinct=True)`
    que já estavam ali sobrevivem a isso — e é essa sobrevivência que engana,
    porque um `Sum` escrito ao lado deles **não** sobrevive: o calor sairia
    multiplicado pelo número de comentários, e a aba passaria a premiar quem tem
    thread comprido em vez de quem está sendo votado agora.

    Duas ideias com o MESMO voto de ontem, uma delas com três comentários. Com o
    `Sum` na junção, a conversada faria calor 9 contra 3 e passaria na frente; do
    jeito certo elas empatam em 3, e quem decide é o desempate por data.
    """
    conversada = caixa.publicar("Com três comentários")
    calada = caixa.publicar("Sem comentário nenhum")
    votar_em(conversada, 1, ONTEM)
    votar_em(calada, 1, ONTEM)
    for numero in range(3):
        Comentario.objects.create(
            sugestao=conversada, autor=aluno, texto=f"comentário {numero}"
        )

    assert _titulos_em_alta(quadro) == ["Com três comentários", "Sem comentário nenhum"]
    # A prova de que o empate acima não é sorte: com a MAIS NOVA conversada, o
    # desempate por data a manda para trás — e um calor inflado a traria de volta
    # para a frente.
    Sugestao.objects.filter(pk=conversada.pk).update(
        criado_em=calada.criado_em + timedelta(minutes=1)
    )
    assert _titulos_em_alta(quadro) == ["Sem comentário nenhum", "Com três comentários"]


def test_em_alta_obedece_ao_filtro_de_categoria(caixa, quadro, votar_em):
    """Como a faixa de roadmap, e pelo mesmo motivo medido no EVO-31: quem
    filtrou por uma categoria não pode receber o resto do quadro de volta."""
    Categoria.objects.create(quadro=quadro, slug="blender", nome="Blender")
    de_curso = caixa.publicar("Coisa de curso")
    de_blender = caixa.publicar("Coisa de Blender", categoria="blender")
    votar_em(de_blender, 3, ONTEM)
    votar_em(de_curso, 1, ONTEM)

    assert _titulos_em_alta(quadro) == ["Coisa de Blender", "Coisa de curso"]
    assert _titulos_em_alta(quadro, categoria_slug="curso") == ["Coisa de curso"]


# ---------------------------------------------------------------------------
# A fiação: a aba na tela, pela borda HTTP
# ---------------------------------------------------------------------------


def test_a_aba_em_alta_abre_e_ordena_a_grade_que_a_pessoa_ve(caixa, votar_em):
    """A prova de que a fórmula chegou à TELA, e não só à função.

    Os deslocamentos saem de um instante lido uma vez pelo teste e ficam longe
    das fronteiras de 7 e 30 dias — o resultado não muda com o relógio.
    """
    agora = timezone.now()
    antiga = caixa.publicar("Antiga com muitos votos")
    recente = caixa.publicar("Recente com poucos")
    votar_em(antiga, 6, agora - timedelta(days=200))
    votar_em(recente, 2, agora - timedelta(days=1))

    assert TITULO_DE_PECA.findall(_corpo(caixa.aluno, ordem="em-alta")) == [
        "Recente com poucos",
        "Antiga com muitos votos",
    ]
    # E a aba padrão continua sendo o ranking por total de votos (spec §10).
    assert TITULO_DE_PECA.findall(_corpo(caixa.aluno)) == [
        "Antiga com muitos votos",
        "Recente com poucos",
    ]


def test_a_aba_em_alta_carrega_o_filtro_e_o_filtro_carrega_a_aba(caixa):
    """O link da aba nova preserva a categoria, como as duas antigas já faziam —
    senão cada clique desfaz metade da escolha anterior."""
    caixa.publicar("Legendas nas aulas")

    corpo = _corpo(caixa.aluno, ordem="em-alta", categoria="curso")

    assert f'href="{reverse("quadro")}?ordem=em-alta&amp;categoria=curso"' in corpo


# ---------------------------------------------------------------------------
# O custo: a mesma página, com um quadro maior, custa o mesmo
# ---------------------------------------------------------------------------


def test_a_aba_em_alta_nao_paga_consulta_por_ideia(caixa, quadro, categoria, votar_em):
    """Não crava um número: compara dois medidos (a forma do EVO-42).

    `assertNumQueries(13)` viraria vermelho falso no dia em que alguém
    acrescentasse um `select_related` — e a pergunta nunca foi "quantas
    consultas", foi *"o número depende do tamanho do quadro?"*. A subconsulta do
    calor é correlacionada: se um dia ela virar um laço em Python, é aqui que
    aparece.

    Duas armadilhas para montar isto nesta célula, as duas pagas aqui: as
    medições têm de ser da MESMA pessoa e depois de uma leitura de AQUECIMENTO —
    sessão e matrícula têm cache de módulo com janela própria
    (`apps/core/sessao.py`, armadilhas/026), então um leitor novo entre as
    medições traria as consultas de estreia e o guarda acusaria N+1 onde não há.

    As ideias entram pelo ORM: publicar 20 pela jornada esbarraria no limite de
    3 por 7 dias (§10) e exigiria 20 logins dublados para medir uma LEITURA.
    """
    agora = timezone.now()
    proximo = iter(range(1000))

    def encher(quantas: int) -> None:
        for _ in range(quantas):
            numero = next(proximo)
            ideia = Sugestao.objects.create(
                quadro=quadro,
                categoria=categoria,
                autor=caixa.aluno.identidade,
                titulo=f"Ideia {numero}",
                problema="Assisto no ônibus e não dá para ouvir.",
            )
            votar_em(ideia, 1, agora - timedelta(days=1))

    encher(PEQUENO)
    _corpo(caixa.aluno, ordem="em-alta")  # aquecimento: sessão e matrícula

    with CaptureQueriesContext(connection) as com_poucas:
        _corpo(caixa.aluno, ordem="em-alta")

    encher(GRANDE - PEQUENO)
    with CaptureQueriesContext(connection) as com_muitas:
        _corpo(caixa.aluno, ordem="em-alta")

    assert Sugestao.objects.count() == GRANDE
    assert len(com_poucas) == len(com_muitas), (
        f"a aba 'Em alta' pagou {len(com_muitas) - len(com_poucas)} consulta(s) a "
        f"mais com {GRANDE} ideias do que com {PEQUENO} "
        f"({len(com_poucas)} → {len(com_muitas)}). SQL da medição grande:\n"
        + "\n".join(c["sql"][:160] for c in com_muitas.captured_queries)
    )
