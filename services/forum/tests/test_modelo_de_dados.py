"""Guardas do modelo de dados do fórum — as três condições que a lei §4 impõe.

Não são testes de "o Django salva um objeto". Cada um trava uma decisão que,
se for desfeita sem querer, só aparece em produção e cara:

1. A marca de leitura é marca-d'água (§4.3) — o achado mais afiado da rodada.
2. A busca é coluna materializada e indexada (§4.4) — o item caro de instalar
   depois.
3. A forma é área → tópico → mensagem (§4.2) — o que mantém aberta a porta de
   migrar para o Discourse.
"""

from datetime import timedelta

import pytest
from django.db import IntegrityError, connection
from django.utils import timezone

from apps.forum.models import (
    Area,
    MarcaDeLeitura,
    Mensagem,
    Pessoa,
    Topico,
    TopicoLido,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def area():
    return Area.objects.create(slug="duvidas", nome="Dúvidas")


@pytest.fixture
def aluno():
    return Pessoa.objects.create(
        id_da_plataforma="p_aluno", email="aluno@exemplo.com", nome_exibido="Aluno"
    )


# --------------------------------------------------------------------------
# §4.3 — a marca de leitura NÃO cresce com o número de mensagens
# --------------------------------------------------------------------------


def test_ler_uma_area_inteira_cria_UMA_linha_e_nao_uma_por_mensagem(area, aluno):
    """O guarda que impede a forma ingênua de voltar.

    Consultor 1, na rodada de 28/08: guardar uma linha por pessoa por mensagem
    lida faz, com 200 alunos e 20 mil mensagens, milhões de linhas para
    responder "tem coisa nova?". Aqui a asserção é literal — 30 mensagens
    lidas, UMA linha de leitura.
    """
    topico = Topico.objects.create(area=area, autor=aluno, titulo="Uma dúvida")
    for i in range(30):
        Mensagem.objects.create(topico=topico, autor=aluno, texto=f"resposta {i}")

    # A pessoa leu tudo o que existia até agora: uma marca-d'água só.
    MarcaDeLeitura.objects.create(pessoa=aluno, area=area, lido_ate=timezone.now())

    assert Mensagem.objects.count() == 30
    assert MarcaDeLeitura.objects.filter(pessoa=aluno).count() == 1
    # E nenhuma exceção: nada foi lido DEPOIS da marca.
    assert TopicoLido.objects.filter(pessoa=aluno).count() == 0


def test_a_excecao_existe_para_o_que_foi_lido_depois_da_marca(area, aluno):
    """A tabela de exceções é o que deixa a marca ser uma linha só sem mentir."""
    # A marca nasce UM SEGUNDO no passado de propósito, e não em `timezone.now()`:
    # o relógio do Windows anda de 15,625 ms em 15,625 ms
    # (`time.get_clock_info("time").resolution`), então esta chamada e a que o
    # `auto_now_add` de `Topico.ultima_atividade_em` faz logo abaixo caem no
    # MESMO tique com frequência — e a comparação estrita vira `==`. Medido em
    # 29/08/2026 nesta máquina: 10 falhas em 30 execuções, com os dois
    # timestamps idênticos até o microssegundo; verde no Linux da CI, onde a
    # resolução é ~1 ns. Um segundo é 64 tiques de folga, e a propriedade
    # provada continua a mesma. Afrouxar para `>=` seria apagar exatamente o
    # que este teste existe para provar (`armadilhas/189`).
    marca = timezone.now() - timedelta(seconds=1)
    MarcaDeLeitura.objects.create(pessoa=aluno, area=area, lido_ate=marca)

    novo = Topico.objects.create(area=area, autor=aluno, titulo="Chegou depois")
    assert novo.ultima_atividade_em > marca, "o tópico nasceu depois da marca"

    TopicoLido.objects.create(pessoa=aluno, topico=novo, lido_em=timezone.now())
    assert TopicoLido.objects.filter(pessoa=aluno).count() == 1


def test_nao_existem_duas_marcas_para_a_mesma_pessoa_na_mesma_area(area, aluno):
    """Duas marcas seriam duas respostas para "li até quando?" — o banco recusa."""
    MarcaDeLeitura.objects.create(pessoa=aluno, area=area, lido_ate=timezone.now())
    with pytest.raises(IntegrityError):
        MarcaDeLeitura.objects.create(pessoa=aluno, area=area, lido_ate=timezone.now())


# --------------------------------------------------------------------------
# §4.4 — a busca é coluna materializada e indexada, não conta na consulta
# --------------------------------------------------------------------------


def test_a_busca_e_uma_coluna_de_verdade_com_indice_gin(area, aluno):
    """O guarda de `armadilhas`-em-potencial: busca calculada no WHERE.

    Funciona lindamente com 500 mensagens e trava com 50 mil — e só se
    descobre em produção. Aqui a prova é ir ao catálogo do PostgreSQL: a
    coluna existe, é `tsvector`, e tem índice GIN em cima.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT data_type FROM information_schema.columns
             WHERE table_name = %s AND column_name = 'busca'
            """,
            [Mensagem._meta.db_table],
        )
        tipo = cursor.fetchone()
    assert tipo is not None, "a coluna `busca` não existe — a busca virou consulta"
    assert tipo[0] == "tsvector", f"`busca` deveria ser tsvector, é {tipo[0]}"

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT indexdef FROM pg_indexes WHERE indexname = %s",
            ["forum_mensagem_busca_gin"],
        )
        indice = cursor.fetchone()
    assert indice is not None, "o índice GIN da busca sumiu"
    assert "gin" in indice[0].lower()


def test_a_busca_em_portugues_encontra_a_duvida_ja_respondida(area, aluno):
    """A razão de existir da busca num fórum de escola: não repetir pergunta.

    Em português, e não no padrão inglês do PostgreSQL. Com a configuração
    errada "texturas" e "textura" viram palavras diferentes e a pessoa não acha
    o que já foi respondido — que é o fórum falhando na única coisa que o torna
    patrimônio em vez de arquivo morto.
    """
    from django.contrib.postgres.search import SearchQuery, SearchVector

    topico = Topico.objects.create(area=area, autor=aluno, titulo="Texturas")
    Mensagem.objects.create(
        topico=topico, autor=aluno, texto="Como aplico texturas no meu modelo?"
    )
    Mensagem.objects.create(topico=topico, autor=aluno, texto="Nada a ver com isso.")

    Mensagem.objects.update(busca=SearchVector("texto", config="portuguese"))

    # Singular na busca, plural no texto: é o caso comum, e o que prova que a
    # configuração é `portuguese` e não o padrão inglês.
    achadas = Mensagem.objects.filter(busca=SearchQuery("textura", config="portuguese"))
    assert achadas.count() == 1, "a busca em português não uniu textura/texturas"
    assert "texturas" in achadas.first().texto


def test_o_buraco_do_plural_em_ens_continua_aberto(area, aluno):
    """MEDIDO em 28/08/2026 contra PostgreSQL 17 — e documentado, não escondido.

    O radicalizador português do PostgreSQL não é mágico: `modelagem` vira o
    radical `modelag`, mas `modelagens` fica inteiro. Numa escola de modelagem
    3D, essa é justamente uma das palavras mais buscadas.

    **Este teste vira vermelho no dia em que a cura chegar** (uma lista de
    sinônimos ou um dicionário ispell/hunspell sobre a mesma configuração) — e
    aí ele é atualizado para exigir o contrário, que é exatamente o sinal que se
    quer. Foi assim que o buraco do ACENTO deixou esta função: ele foi curado em
    30/08/2026 e virou o teste logo abaixo.
    """
    from django.contrib.postgres.search import SearchQuery, SearchVector

    topico = Topico.objects.create(area=area, autor=aluno, titulo="t")
    Mensagem.objects.create(topico=topico, autor=aluno, texto="Fiz a modelagem")
    Mensagem.objects.update(busca=SearchVector("texto", config="portuguese"))

    def acha(termo: str) -> int:
        return Mensagem.objects.filter(
            busca=SearchQuery(termo, config="portuguese")
        ).count()

    assert acha("modelagem") == 1, "o singular tem de achar — isto é o básico"
    assert acha("modelagens") == 0, "buraco: plural em -ens não é unido (ainda)"


def test_a_cura_do_acento_chegou_e_esta_travada(area, aluno):
    """O buraco 2 de 28/08 CURADO, e o guarda invertido — 30/08/2026.

    A configuração `portugues_sem_acento` (criada pelo provisionamento, com
    `unaccent`) faz `chapeu` achar `chapéu`. Isso importa mais do que parece: no
    Brasil quase ninguém acentua ao buscar, então a versão sensível a acento
    errava a maioria das buscas reais **em silêncio** — a pessoa concluía que a
    resposta não existia e perguntava de novo, que é o oposto do que um fórum
    existe para fazer.

    O guarda exige as DUAS direções: com acento e sem acento acham a mesma
    mensagem. Um teste que só provasse `chapeu` passaria com uma configuração
    que tivesse simplesmente parado de indexar o acento.
    """
    from django.contrib.postgres.search import SearchQuery, SearchVector

    from apps.forum.config_de_busca import CONFIG_SEM_ACENTO

    topico = Topico.objects.create(area=area, autor=aluno, titulo="t")
    Mensagem.objects.create(topico=topico, autor=aluno, texto="Meu chapéu ficou torto")
    Mensagem.objects.update(busca=SearchVector("texto", config=CONFIG_SEM_ACENTO))

    def acha(termo: str) -> int:
        return Mensagem.objects.filter(
            busca=SearchQuery(termo, config=CONFIG_SEM_ACENTO)
        ).count()

    assert acha("chapeu") == 1, "a cura do acento não está no banco de teste"
    assert acha("chapéu") == 1, "quem escreve certo também tem de achar"


# --------------------------------------------------------------------------
# §4.2 — a forma comum, que mantém a porta do Discourse aberta
# --------------------------------------------------------------------------


def test_a_forma_e_area_topico_mensagem(area, aluno):
    """Mensagem pertence a tópico, que pertence a área. Nada de atalho.

    Se um dia alguém pendurar mensagem direto na área — ou inventar um nível a
    mais —, migrar para o Discourse deixa de ser caminho batido e vira projeto.
    """
    topico = Topico.objects.create(area=area, autor=aluno, titulo="t")
    mensagem = Mensagem.objects.create(topico=topico, autor=aluno, texto="m")

    assert mensagem.topico.area == area
    campos = {f.name for f in Mensagem._meta.get_fields()}
    assert "area" not in campos, "mensagem não pode pendurar direto na área"


def test_area_de_turma_sem_curso_e_recusada_pelo_banco(aluno):
    """Fail-closed por construção, e no banco — não numa view.

    Uma área de turma sem curso é uma área que ninguém consegue avaliar; a
    tentação, na hora do bug, é liberar. O banco recusa antes disso.
    """
    with pytest.raises(IntegrityError):
        Area.objects.create(
            slug="turma-x",
            nome="Turma X",
            visibilidade=Area.Visibilidade.TURMA,
            curso_id="",
        )


def test_area_de_turma_com_curso_e_aceita():
    """O outro lado: a trava não pode barrar o caso legítimo."""
    a = Area.objects.create(
        slug="turma-y",
        nome="Turma Y",
        visibilidade=Area.Visibilidade.TURMA,
        curso_id="curso_esqueleto",
    )
    assert a.pk


def test_o_padrao_de_uma_area_nova_e_fechado(area):
    """Área nasce para ALUNOS e com escrita só da EQUIPE — nunca aberta por descuido.

    O mantenedor decidiu áreas mistas (lei §5), e o público é majoritariamente
    menor de idade. O padrão seguro é o fechado: abrir uma área é um ato
    explícito, escrito no dado, e não o que acontece quando alguém esquece.

    **O default de `quem_escreve` apertou em 30/08/2026**: era `aluno`, virou
    `equipe`. Uma área que nascia sem o campo preenchido já vinha com a porta
    mais aberta do que a intenção de quem a criou — e "mais aberto do que se
    quis" é exatamente o erro que um default fail-closed existe para evitar.
    """
    assert area.visibilidade == Area.Visibilidade.ALUNOS
    assert area.quem_escreve == Area.QuemEscreve.EQUIPE


def test_remover_mensagem_nao_apaga_o_historico(area, aluno):
    """Remoção é suave: some da tela, a linha fica.

    Apagar de verdade destruiria o contexto de uma denúncia justamente quando
    ele importa — e o público desta escola é majoritariamente menor de idade.
    """
    topico = Topico.objects.create(area=area, autor=aluno, titulo="t")
    m = Mensagem.objects.create(topico=topico, autor=aluno, texto="algo")

    m.removida_em = timezone.now()
    m.save(update_fields=["removida_em"])

    m.refresh_from_db()
    assert m.texto == "algo", "o texto tem de sobreviver à remoção"
    assert Mensagem.objects.filter(pk=m.pk).exists()
