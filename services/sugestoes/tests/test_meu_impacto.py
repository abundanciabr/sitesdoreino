"""O painel "MEU IMPACTO" (V1.2, spec §10), medido pela borda HTTP.

O que ele conta é **o que a participação da própria pessoa produziu**: as ideias
que ela escreveu, os votos que ela deu, quantas das ideias em que ela pôs a mão
saíram da análise, e quantos votos as ideias dela receberam. Tudo isso ela já
alcança clicando pela Caixa; o painel só junta num lugar.

**O que ele NÃO é — e é a metade mais importante deste arquivo.** A célula tem
uma avaliação interna (`impacto_educacional`, `impacto_comercial`,
`esforco_tecnico`, `notas`, `decisao_produto`) que é invisível ao aluno por
desenho, em três degraus, desde o EVO-11 (spec §8). A palavra "impacto" aparecer
nos dois assuntos é herança do protótipo: um é o que a PESSOA fez, o outro é o
que a EQUIPE achou. `test_nenhuma_nota_interna_da_equipe_chega_ao_painel` mede a
fronteira aqui também, com a mesma marca inconfundível do guarda antigo — que
continua percorrendo esta página, agora nas três abas
(`test_inv_avaliacao_interna_fora_do_alcance.py`).

Toda asserção olha o HTML que o navegador receberia. As duas exceções são as de
sempre e estão marcadas: a que conta consultas (não há como medir N+1 pelo corpo
da resposta) e a que precisa carimbar data no passado.
"""

import re

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.core.participacao import IDEIAS_NO_IMPACTO
from apps.sugestoes.models import AvaliacaoInterna, Categoria, Sugestao

pytestmark = pytest.mark.django_db

# Os quatro números, na ordem em que a página os desenha. Classe própria e não
# `.votos`: essa é a que `test_o_rosto.py` lê por regex para medir o botão de
# voto da grade, e reaproveitá-la aqui faria aquele guarda somar este painel.
NUMERO = re.compile(r'<b class="impacto-numero">(\d+)</b>')
IDEIA_LISTADA = re.compile(r'<a class="impacto-titulo" href="[^"]*">([^<]+)</a>')

MARCA = "DECISAO-INTERNA-QUE-O-ALUNO-NUNCA-PODE-VER"


def _corpo(pessoa, **query) -> str:
    endereco = reverse("quadro")
    if query:
        endereco += "?" + "&".join(f"{c}={v}" for c, v in query.items())
    resposta = pessoa.client.get(endereco)
    assert resposta.status_code == 200, resposta.status_code
    return resposta.content.decode()


def _painel(corpo: str) -> str:
    """Só a seção do painel — o resto da página também tem números soltos."""
    assert 'id="meu-impacto"' in corpo, "o painel 'Meu impacto' não foi desenhado"
    return corpo.split('<section id="meu-impacto"', 1)[1].split("</section>", 1)[0]


def _numeros(corpo: str) -> list[int]:
    return [int(n) for n in NUMERO.findall(_painel(corpo))]


# ---------------------------------------------------------------------------
# Os quatro números
# ---------------------------------------------------------------------------


def test_o_painel_conta_a_participacao_de_quem_esta_olhando(caixa, entrar_como):
    """Ideias escritas · ideias apoiadas · saíram da análise · votos recebidos."""
    minha = caixa.publicar("Legendas nas aulas")
    outra = caixa.publicar("Modo escuro no player")
    de_terceiro = entrar_como("terceiro@exemplo.test", "Terceiro")
    alheia = Sugestao.objects.create(
        quadro=minha.quadro,
        categoria=minha.categoria,
        autor=de_terceiro.identidade,
        titulo="Ideia de outra pessoa",
        problema="Doi assim.",
    )

    # Eu apoio a ideia alheia; duas outras pessoas apoiam a minha.
    assert caixa.votar(alheia).status_code == 302
    for numero in range(2):
        fa = entrar_como(f"fa{numero}@exemplo.test", f"Fã {numero}")
        assert caixa.votar(minha, quem=fa).status_code == 302
    # E a equipe move uma das minhas para fora da análise.
    assert caixa.mudar_status(outra, Sugestao.Status.PLANEJADO).status_code == 200

    assert _numeros(_corpo(caixa.aluno)) == [2, 1, 1, 2]


def test_o_impacto_de_uma_pessoa_nao_e_o_da_outra(caixa, entrar_como):
    """O painel é de quem está olhando — nunca a soma do quadro.

    Sem este guarda, um `filter(autor=...)` esquecido devolveria os números do
    quadro inteiro para todo mundo, e o painel ficaria plausível para sempre:
    números grandes não parecem errados.
    """
    caixa.publicar("Legendas nas aulas")
    recem_chegada = entrar_como("recem@exemplo.test", "Recém-chegada")

    assert _numeros(_corpo(caixa.aluno))[0] == 1
    assert _numeros(_corpo(recem_chegada)) == [0, 0, 0, 0]
    assert "Você ainda não publicou nenhuma ideia" in _painel(_corpo(recem_chegada))


def test_quem_so_votou_tambem_ve_a_ideia_avancar_na_conta(caixa, entrar_como):
    """ "Participou" é ter escrito OU votado — e é o que o painel promete.

    Contar só a autoria transformaria o painel num placar de quem escreve muito,
    e a Caixa é feita para quem vota também: a §10 põe o voto no MVP justamente
    porque ele é a participação mais barata e mais comum.
    """
    ideia = caixa.publicar("Legendas nas aulas")
    apoiadora = entrar_como("apoiadora@exemplo.test", "Apoiadora")
    assert caixa.votar(ideia, quem=apoiadora).status_code == 302

    antes = _numeros(_corpo(apoiadora))
    assert (
        caixa.mudar_status(ideia, Sugestao.Status.EM_DESENVOLVIMENTO).status_code == 200
    )
    depois = _numeros(_corpo(apoiadora))

    assert antes == [0, 1, 0, 0]
    assert depois == [0, 1, 1, 0]


def test_quem_votou_na_propria_ideia_conta_uma_vez_so(caixa):
    """`Q(autor=eu) | Q(votos__autor=eu)` casa nos DOIS lados para quem votou na
    própria ideia; sem o `.distinct()`, a mesma sugestão sairia contada duas
    vezes e o número passaria a premiar quem vota em si mesmo."""
    minha = caixa.publicar("Legendas nas aulas")
    assert caixa.votar(minha).status_code == 302
    assert caixa.mudar_status(minha, Sugestao.Status.PLANEJADO).status_code == 200

    assert _numeros(_corpo(caixa.aluno))[2] == 1


def test_recusada_e_mesclada_nao_contam_como_avanco(caixa):
    """`nao_planejado` não é avanço, e `mesclado` também não: a ideia não andou,
    ela virou outra. Contá-las faria o número subir por um fato que não é
    vitória de ninguém — e a pessoa leria "1 saiu da análise" no mesmo dia em
    que recebeu um "não vamos fazer"."""
    recusada = caixa.publicar("Esta a equipe não vai fazer")
    virou_outra = caixa.publicar("Esta virou outra")
    assert (
        caixa.mudar_status(
            recusada, Sugestao.Status.NAO_PLANEJADO, nota="Sai do escopo do curso."
        ).status_code
        == 200
    )
    # `mesclado` fica FORA do <select> da moderação desde o EVO-13 (há guarda
    # para isso), então só o ORM o escreve — mas a tela tem de saber contá-lo
    # hoje, senão o dia em que o merge nascer é o dia em que o painel mente.
    Sugestao.objects.filter(pk=virou_outra.pk).update(status=Sugestao.Status.MESCLADO)

    assert _numeros(_corpo(caixa.aluno)) == [2, 0, 0, 0]


# ---------------------------------------------------------------------------
# A lista: qual ideia andou, e onde ela está
# ---------------------------------------------------------------------------


def test_a_lista_mostra_as_ideias_da_pessoa_com_o_status_de_cada_uma(caixa):
    """Quatro números sozinhos não dizem QUAL ideia andou."""
    andou = caixa.publicar("Esta entrou no roadmap")
    assert caixa.mudar_status(andou, Sugestao.Status.PLANEJADO).status_code == 200
    caixa.publicar("Esta ainda está em análise")

    painel = _painel(_corpo(caixa.aluno))

    assert IDEIA_LISTADA.findall(painel) == [
        "Esta ainda está em análise",  # a mais recente primeiro
        "Esta entrou no roadmap",
    ]
    assert 'class="selo selo-planejado">Planejado' in painel
    assert 'class="selo selo-em_analise">Em análise' in painel


def test_a_lista_corta_no_teto_e_diz_quantas_ficaram_de_fora(caixa, quadro, categoria):
    """O corte é em Python sobre a MESMA consulta — não custa consulta nenhuma —
    e o total continua saindo inteiro no número de cima. Sem a linha do "e mais
    N", a lista mentiria por omissão para quem participa há mais tempo."""
    for numero in range(IDEIAS_NO_IMPACTO + 3):
        # Pelo ORM: o limite da §10 é de 3 sugestões por pessoa em 7 dias, e o
        # que se mede aqui é o corte da lista, não o limite (que tem guarda
        # próprio em `test_inv_rate_limit_sugestoes.py`).
        Sugestao.objects.create(
            quadro=quadro,
            categoria=categoria,
            autor=caixa.aluno.identidade,
            titulo=f"Ideia {numero}",
            problema="Doi assim.",
        )

    painel = _painel(_corpo(caixa.aluno))

    assert len(IDEIA_LISTADA.findall(painel)) == IDEIAS_NO_IMPACTO
    assert _numeros(_corpo(caixa.aluno))[0] == IDEIAS_NO_IMPACTO + 3
    assert "e mais 3 que você escreveu antes destas" in painel


# ---------------------------------------------------------------------------
# O filtro de categoria — a mesma regra da faixa de roadmap
# ---------------------------------------------------------------------------


def test_o_painel_obedece_ao_filtro_de_categoria(caixa, quadro):
    """Quem filtrou por uma categoria não pode receber o resto do quadro de
    volta no rodapé da mesma página — foi um guarda do EVO-12b
    (`test_o_quadro_filtra_por_categoria`) que decidiu isso, vermelho, quando a
    faixa de roadmap tentou mostrar o quadro inteiro no EVO-31.

    E o painel DIZ em que recorte os números estão: sem essa linha, "1 ideia"
    pareceria desmentir as 2 que a pessoa escreveu no quadro.
    """
    Categoria.objects.create(quadro=quadro, slug="blender", nome="Blender")
    caixa.publicar("Coisa de curso")
    caixa.publicar("Coisa de Blender", categoria="blender")

    inteiro = _corpo(caixa.aluno)
    so_curso = _corpo(caixa.aluno, categoria="curso")

    assert _numeros(inteiro)[0] == 2
    assert "neste quadro" in _painel(inteiro)

    assert _numeros(so_curso)[0] == 1
    assert IDEIA_LISTADA.findall(_painel(so_curso)) == ["Coisa de curso"]
    assert "em Curso e aulas" in _painel(so_curso)
    assert "Coisa de Blender" not in so_curso


# ---------------------------------------------------------------------------
# A fronteira que não se move: a avaliação interna continua invisível
# ---------------------------------------------------------------------------


def test_nenhuma_nota_interna_da_equipe_chega_ao_painel(caixa, equipe, gestao):
    """O guarda do despacho: "Meu impacto" não é a avaliação da EQUIPE.

    Dois degraus, sobre a MESMA jornada em que o painel aparece — as três abas e
    o recorte por categoria:

    1. o corpo da resposta não pode conter a marca da avaliação;
    2. nenhuma consulta da página pode encostar na tabela dela — é o degrau que
       pega o `select_related` distraído e o `{{ … }}` que consulta na hora de
       renderizar, que "não escrevi o campo no template" não pega.

    O terceiro degrau (a AST de `participacao.py`, que proíbe o módulo do aluno
    de sequer NOMEAR o model) mora no guarda antigo e continua valendo para o
    código novo, porque ele varre o módulo inteiro.
    """
    minha = caixa.publicar("Legendas nas aulas")
    escrita = gestao.avaliar(
        equipe,
        minha,
        impacto_educacional=5,
        impacto_comercial=4,
        esforco_tecnico=2,
        notas=MARCA,
        decisao_produto=MARCA,
    )
    assert escrita.status_code == 200, escrita.content
    assert AvaliacaoInterna.objects.filter(
        sugestao=minha
    ).exists(), "a avaliação nem chegou a existir — este guarda não mediu nada"

    tabela = AvaliacaoInterna._meta.db_table
    with CaptureQueriesContext(connection) as consultas:
        corpos = [
            _corpo(caixa.aluno),
            _corpo(caixa.aluno, ordem="em-alta"),
            _corpo(caixa.aluno, ordem="novas"),
            _corpo(caixa.aluno, categoria="curso"),
        ]

    for corpo in corpos:
        assert 'id="meu-impacto"' in corpo, "o painel sumiu — nada foi medido"
        assert MARCA not in corpo, "a página do aluno devolveu a avaliação interna"

    culpadas = [c["sql"] for c in consultas.captured_queries if tabela in c["sql"]]
    assert culpadas == [], (
        f"o quadro com o painel 'Meu impacto' consultou {tabela}: {culpadas[:3]}. "
        "A avaliação interna é da equipe (spec §8)."
    )


# ---------------------------------------------------------------------------
# O custo: a mesma página, com um quadro maior, custa o mesmo
# ---------------------------------------------------------------------------


def test_o_painel_nao_paga_consulta_por_ideia(caixa, quadro, categoria):
    """Compara dois números medidos, nunca crava um (a forma do EVO-42).

    O painel são quatro consultas agregadas: o banco conta, e não este processo.
    O jeito ingênuo — puxar as ideias e os votos e somar em Python — entrega
    exatamente os mesmos números e passa em todos os guardas acima; o que ele
    não faz é continuar barato quando a pessoa participa de muita coisa.

    Aquecimento antes da primeira medição, e as duas leituras pela MESMA pessoa:
    sessão e matrícula têm cache de módulo com janela própria (armadilhas/026).
    """
    proximo = iter(range(1000))

    def encher(quantas: int) -> None:
        for _ in range(quantas):
            numero = next(proximo)
            Sugestao.objects.create(
                quadro=quadro,
                categoria=categoria,
                autor=caixa.aluno.identidade,
                titulo=f"Ideia {numero}",
                problema="Doi assim.",
            )

    encher(2)
    _corpo(caixa.aluno)  # aquecimento: sessão e matrícula

    with CaptureQueriesContext(connection) as com_poucas:
        _corpo(caixa.aluno)

    encher(18)
    with CaptureQueriesContext(connection) as com_muitas:
        corpo = _corpo(caixa.aluno)

    assert _numeros(corpo)[0] == 20
    assert len(com_poucas) == len(com_muitas), (
        f"o quadro com o painel pagou {len(com_muitas) - len(com_poucas)} "
        f"consulta(s) a mais com 20 ideias do que com 2 "
        f"({len(com_poucas)} → {len(com_muitas)}). SQL da medição grande:\n"
        + "\n".join(c["sql"][:160] for c in com_muitas.captured_queries)
    )
