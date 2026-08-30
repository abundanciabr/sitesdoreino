"""A FAIXA DE ROADMAP (EVO-31), medida pela borda HTTP — nunca pelo contexto.

O que este arquivo prova é o que o aluno passa a CONSEGUIR VER: por onde as
ideias do quadro andaram, em quatro zonas na ordem do caminho, com as sugestões
de verdade em cada uma — e, logo abaixo, "Fora do trilho", com as que viraram
outra ideia (`mesclado`). `nao_planejado` não mora mais aqui (decisão do
mantenedor, 29/08/2026): a ideia recusada continua abrindo pelo link direto,
com a justificativa escrita nela, mas parou de aparecer nas listas do quadro.

Quase toda asserção olha o HTML que o navegador receberia. As duas exceções são
deliberadas e estão marcadas: a que conta consultas (não há como medir N+1 pelo
corpo da resposta) e a que povoa DOIS quadros no banco — `quadro_atual()` é
fail-closed com mais de um quadro (404), então o vazamento entre quadros só pode
ser medido chamando a consulta direto.

**A ordem das quatro zonas está escrita à mão aqui, e não derivada de `ETAPAS`.**
Derivá-la faria o teste seguir qualquer reordenação do código em silêncio — que
é justamente o erro que ele existe para pegar.
"""

import re

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.core.participacao import (
    MARCOS_POR_ZONA,
    faixa_de_roadmap,
    fora_do_trilho,
    numeros_do_quadro,
)
from apps.sugestoes.models import Quadro, Sugestao

pytestmark = pytest.mark.django_db

# O caminho, na ordem em que uma ideia o percorre. Escrito à mão de propósito.
ZONAS_NA_ORDEM = ["em_analise", "planejado", "em_desenvolvimento", "implementado"]
ROTULOS_NA_ORDEM = ["Em análise", "Planejado", "Em desenvolvimento", "Implementado"]

# O marco, como ele chega ao navegador: o `title` é o nome da ideia (um losango
# sozinho não é rótulo para quem usa leitor de tela) e `.marco-votos` é a
# contagem. `.marco-votos` e NÃO `.votos`: a segunda classe é a que o guarda do
# EVO-30 lê para medir o botão de voto da grade.
MARCO = re.compile(r'<a class="marco" href="([^"]+)"\s+title="([^"]+)"')


def _corpo(pessoa, **query) -> str:
    endereco = reverse("quadro")
    if query:
        endereco += "?" + "&".join(f"{c}={v}" for c, v in query.items())
    resposta = pessoa.client.get(endereco)
    assert resposta.status_code == 200, resposta.status_code
    return resposta.content.decode()


def _zonas(corpo: str) -> list[tuple[str, str]]:
    """As zonas da faixa, na ordem em que a PÁGINA as desenhou.

    Recorta pelo HTML entregue, e não pelo contexto: um template que parasse de
    desenhar uma zona continuaria com o contexto certo e este guarda cairia.
    """
    faixa = corpo.split('<div class="faixa">', 1)[1].split("</section>", 1)[0]
    faixa = faixa.split('<div class="fora-do-trilho">', 1)[0]
    pedacos = faixa.split('data-zona="')[1:]
    return [(pedaco.split('"', 1)[0], pedaco.split('"', 1)[1]) for pedaco in pedacos]


def _titulos_da_zona(corpo: str, chave: str) -> list[str]:
    for zona, html in _zonas(corpo):
        if zona == chave:
            return [titulo for _, titulo in MARCO.findall(html)]
    raise AssertionError(f"a faixa não desenhou a zona {chave!r}")


def _saidas(corpo: str) -> str:
    partes = corpo.split('<div class="fora-do-trilho">', 1)
    return partes[1].split("</section>", 1)[0] if len(partes) > 1 else ""


@pytest.fixture
def povoar(caixa, entrar_como):
    """Uma ideia em cada situação pedida, pela jornada de verdade onde ela existe.

    `mudar_status` é o POST da equipe — o mesmo caminho da moderação. `mesclado`
    é a exceção e vai pelo ORM de propósito: ele fica FORA do `<select>` da
    moderação desde o EVO-13 (mesclar é V1.1 e é uma operação transacional
    inteira), e há guarda impedindo que ele entre por lá. A faixa, porém, tem de
    saber desenhá-lo hoje — o dia em que o merge nascer não pode ser o dia em
    que a tela quebra.

    **Cada ideia nasce de uma pessoa nova**, e não é capricho: o limite da §10 é
    de 3 sugestões por autor em 7 dias (INVARIANTE 4 do EVO-12b), e uma zona
    cheia precisa de mais do que três. Publicar tudo pela mesma pessoa daria 429
    na quarta — que é o guarda do limite fazendo o trabalho dele.
    """
    autores = iter(range(1000))

    def _povoar(titulo: str, status: str, nota: str = "Motivo escrito pela equipe."):
        numero = next(autores)
        caixa.aluno = entrar_como(f"autor{numero}@exemplo.test", f"Autor {numero}")
        sugestao = caixa.publicar(titulo)
        if status == Sugestao.Status.MESCLADO:
            Sugestao.objects.filter(pk=sugestao.pk).update(status=status)
            sugestao.refresh_from_db()
        elif status != Sugestao.Status.EM_ANALISE:
            assert caixa.mudar_status(sugestao, status, nota=nota).status_code == 200
            sugestao.refresh_from_db()
        return sugestao

    return _povoar


# ---------------------------------------------------------------------------
# As quatro zonas, na ordem, com as ideias reais
# ---------------------------------------------------------------------------


def test_a_faixa_desenha_as_quatro_zonas_na_ordem_do_caminho(caixa):
    corpo = _corpo(caixa.aluno)

    assert 'id="roadmap"' in corpo, "a faixa de roadmap não foi desenhada"
    assert [chave for chave, _ in _zonas(corpo)] == ZONAS_NA_ORDEM

    # E os rótulos saem na mesma ordem no texto: a ordem das zonas É a
    # informação da faixa — trocada, ela conta a história ao contrário.
    posicoes = [corpo.index(rotulo) for rotulo in ROTULOS_NA_ORDEM]
    assert posicoes == sorted(posicoes), ROTULOS_NA_ORDEM


def test_cada_zona_mostra_as_ideias_que_estao_nela_e_so_elas(povoar, caixa):
    povoar("Ainda sendo analisada", Sugestao.Status.EM_ANALISE)
    povoar("Já entrou no plano", Sugestao.Status.PLANEJADO)
    povoar("Alguém está fazendo", Sugestao.Status.EM_DESENVOLVIMENTO)
    povoar("Entregue no site", Sugestao.Status.IMPLEMENTADO)

    corpo = _corpo(caixa.aluno)

    assert _titulos_da_zona(corpo, "em_analise") == ["Ainda sendo analisada"]
    assert _titulos_da_zona(corpo, "planejado") == ["Já entrou no plano"]
    assert _titulos_da_zona(corpo, "em_desenvolvimento") == ["Alguém está fazendo"]
    assert _titulos_da_zona(corpo, "implementado") == ["Entregue no site"]


def test_o_marco_leva_para_a_ideia_e_diz_quantos_votos_ela_tem(povoar, caixa):
    """Losango que não leva a lugar nenhum é enfeite: a faixa é um caminho de
    entrada para a ideia, e o número ao lado é o que explica a posição dela."""
    sugestao = povoar("Já entrou no plano", Sugestao.Status.PLANEJADO)
    assert caixa.votar(sugestao).status_code == 302

    corpo = _corpo(caixa.aluno)
    enderecos = dict((titulo, href) for href, titulo in MARCO.findall(corpo))

    assert enderecos["Já entrou no plano"] == reverse("sugestao", args=[sugestao.id])
    assert '<span class="marco-votos">1</span>' in corpo


def test_zona_vazia_tem_estado_vazio_e_nao_um_buraco_na_tela(povoar, caixa):
    povoar("Já entrou no plano", Sugestao.Status.PLANEJADO)

    corpo = _corpo(caixa.aluno)

    for chave in ("em_desenvolvimento", "implementado"):
        _, html = next(z for z in _zonas(corpo) if z[0] == chave)
        assert (
            "nenhuma ideia por aqui ainda" in html
        ), f"a zona {chave} ficou um buraco na tela: nem marco, nem recado."
        assert MARCO.findall(html) == []


def test_a_zona_corta_a_lista_mas_nunca_o_numero(povoar, caixa):
    """Zona lotada mostra `+N`, e o total ao lado do rótulo continua inteiro.

    O corte é de DESENHO (uma faixa horizontal não comporta cem losangos); o
    número, não — se ele encolhesse junto, a faixa passaria a mentir sobre o
    tamanho da fila.
    """
    for numero in range(MARCOS_POR_ZONA + 2):
        povoar(f"Ideia {numero}", Sugestao.Status.PLANEJADO)

    corpo = _corpo(caixa.aluno)

    assert len(_titulos_da_zona(corpo, "planejado")) == MARCOS_POR_ZONA
    assert "+2" in corpo
    assert f'<b class="zona-total">{MARCOS_POR_ZONA + 2}</b>' in corpo


# ---------------------------------------------------------------------------
# As duas situações que não são zona — e não somem por isso
# ---------------------------------------------------------------------------


def test_a_recusada_some_das_listas_mas_o_link_direto_continua_com_o_motivo(
    povoar, caixa
):
    """Decisão do mantenedor (29/08/2026): `nao_planejado` some da grade e da
    faixa — mas quem tem o link (o autor, por exemplo) ainda abre a página e lê
    o porquê. A garantia de "quem sugeriu vai ler" (EVO-13) segue de pé: quem
    interagiu já recebeu a nota pelo sininho (`avisos.py`), antes desta mudança
    e independente dela — a página deixar de listar a ideia não desfaz isso.
    """
    recusada = povoar(
        "Aula ao vivo todo dia",
        Sugestao.Status.NAO_PLANEJADO,
        nota="Não temos equipe para diário; vamos manter o semanal.",
    )
    mesclada = povoar("Legendas, de novo", Sugestao.Status.MESCLADO)

    corpo = _corpo(caixa.aluno)
    saidas = _saidas(corpo)

    assert recusada.titulo not in corpo
    assert f'href="{reverse("sugestao", args=[mesclada.id])}"' in saidas
    assert 'class="selo selo-mesclado">Mesclado' in saidas
    assert "selo-nao_planejado" not in corpo

    # O link direto continua abrindo, com o motivo escrito por inteiro.
    resposta = caixa.aluno.client.get(reverse("sugestao", args=[recusada.id]))
    assert resposta.status_code == 200
    assert "Não temos equipe para diário" in resposta.content.decode()


def test_nenhuma_ideia_visivel_fica_de_fora_da_conta(povoar):
    """A aritmética honesta: as quatro zonas MAIS as saídas dão o total MOSTRADO.

    É este guarda que impede alguém de "limpar" a faixa escondendo um status
    sem também tirá-lo da conta: a soma passaria a discordar do número que a
    página exibe, e ela estaria mentindo sem nada na tela indicando a diferença.

    Desde 29/08/2026 "o total mostrado" e "o total no banco" podem divergir de
    propósito — `nao_planejado` continua existindo (6 linhas), mas só 5 são
    MOSTRADAS em algum lugar do quadro; a sexta só abre pelo link direto. A
    honestidade agora é sobre `numeros_do_quadro()["sugestoes"]`, que é o
    número que o aluno lê — não sobre `Sugestao.objects.count()`.
    """
    for numero, status in enumerate(
        [
            Sugestao.Status.EM_ANALISE,
            Sugestao.Status.PLANEJADO,
            Sugestao.Status.EM_DESENVOLVIMENTO,
            Sugestao.Status.IMPLEMENTADO,
            Sugestao.Status.NAO_PLANEJADO,
            Sugestao.Status.MESCLADO,
        ]
    ):
        povoar(f"Ideia {numero}", status)

    quadro = Sugestao.objects.first().quadro
    nas_zonas = sum(zona["total"] for zona in faixa_de_roadmap(quadro))

    assert Sugestao.objects.count() == 6, "as seis ideias existem de verdade no banco"
    assert (
        nas_zonas + len(fora_do_trilho(quadro))
        == numeros_do_quadro(quadro)["sugestoes"]
        == 5
    )


# ---------------------------------------------------------------------------
# O que a faixa NÃO pode mostrar
# ---------------------------------------------------------------------------


def test_a_faixa_nao_vaza_sugestao_de_outro_quadro(quadro, categoria, aluno):
    """Medido pela consulta, e não pela página, porque a página não chega lá.

    `quadro_atual()` é fail-closed: com dois quadros no banco ela para com 404,
    porque a célula ainda não resolve Host→Site (CONV-SITE). O vazamento entre
    quadros, então, só aparece chamando a consulta direto — e ele apareceria no
    dia em que o middleware chegasse, com dois sites no ar, que é tarde demais.
    """
    outro = Quadro.objects.create(site_id="outro-site", nome="Quadro do vizinho")
    outra_categoria = outro.categorias.create(slug="curso", nome="Curso e aulas")
    Sugestao.objects.create(
        quadro=quadro,
        categoria=categoria,
        autor=aluno,
        titulo="Ideia daqui",
        problema="dói aqui",
        status=Sugestao.Status.PLANEJADO,
    )
    Sugestao.objects.create(
        quadro=outro,
        categoria=outra_categoria,
        autor=aluno,
        titulo="Ideia do vizinho",
        problema="dói lá",
        status=Sugestao.Status.PLANEJADO,
    )

    titulos = [
        marco["titulo"] for zona in faixa_de_roadmap(quadro) for marco in zona["marcos"]
    ]

    assert titulos == ["Ideia daqui"], (
        "a faixa mostrou sugestão de outro quadro — o INV-P11 diz que toda "
        "sugestão pertence a um quadro, e o quadro a um site."
    )


def test_quem_nao_entrou_nao_alcanca_a_faixa(client, povoar):
    """O roadmap é público DENTRO da Caixa: quem tem sessão vê, como no resto da
    participação (`DECISAO-EVO-01` §2). Uma página anônima mudaria essa lei."""
    povoar("Já entrou no plano", Sugestao.Status.PLANEJADO)

    resposta = client.get(reverse("quadro"))
    corpo = resposta.content.decode()

    assert resposta.status_code == 302
    assert resposta["Location"] == reverse("entrar")
    assert 'id="roadmap"' not in corpo
    assert "Já entrou no plano" not in corpo


def test_a_faixa_encolhe_junto_com_o_filtro_de_categoria(povoar, caixa, quadro):
    """Quem filtrou por uma categoria não recebe o resto do quadro de volta na
    parte de baixo da mesma página."""
    quadro.categorias.create(slug="blender", nome="Blender")
    de_curso = povoar("Coisa de curso", Sugestao.Status.PLANEJADO)
    de_blender = caixa.publicar("Coisa de Blender", categoria="blender")
    assert caixa.mudar_status(de_blender, Sugestao.Status.PLANEJADO).status_code == 200

    corpo = _corpo(caixa.aluno, categoria="curso")

    assert _titulos_da_zona(corpo, "planejado") == [de_curso.titulo]
    assert de_blender.titulo not in corpo


# ---------------------------------------------------------------------------
# O custo: a faixa não pode ser um N+1 escondido atrás de losangos
# ---------------------------------------------------------------------------


def test_a_faixa_inteira_e_uma_consulta_so(povoar, django_assert_num_queries):
    """Uma consulta agregada — não uma por zona, nem uma por marco.

    O jeito ingênuo custaria quatro (`filter(status=…)` por zona) mais uma por
    sugestão (`s.votos.count()` no template). Aqui o banco é visitado UMA vez, e
    quem separa por zona é um laço em Python sobre o resultado.
    """
    povoar("Já entrou no plano", Sugestao.Status.PLANEJADO)
    povoar("Alguém está fazendo", Sugestao.Status.EM_DESENVOLVIMENTO)
    quadro = Sugestao.objects.first().quadro

    with django_assert_num_queries(1):
        faixa_de_roadmap(quadro)

    with django_assert_num_queries(1):
        fora_do_trilho(quadro)


def test_o_quadro_nao_paga_mais_consultas_quando_a_faixa_enche(
    povoar, caixa, entrar_como
):
    """O guarda que morde de verdade: a mesma página, com mais ideias, custa o
    MESMO número de consultas.

    Um número fixo (`assertNumQueries(9)`) envelheceria a cada mudança da página
    e seria "corrigido" para o valor novo sem ninguém olhar o motivo. A
    comparação não envelhece: o que ela afirma é que o custo não depende do
    tamanho do quadro, que é a definição de não ser N+1.

    As duas medições são da MESMA pessoa, e há uma leitura de aquecimento antes
    da primeira: sessão e matrícula têm cache de módulo com janela própria
    (`apps/core/sessao.py`), então um leitor novo entre as medições traria
    consultas de estreia e o guarda acusaria N+1 onde não há.
    """
    leitor = entrar_como("leitor@exemplo.test", "Leitor")
    povoar("Primeira", Sugestao.Status.PLANEJADO)
    _corpo(leitor)

    with CaptureQueriesContext(connection) as com_uma:
        _corpo(leitor)

    for numero in range(4):
        povoar(f"Ideia {numero}", Sugestao.Status.IMPLEMENTADO)
    with CaptureQueriesContext(connection) as com_cinco:
        _corpo(leitor)

    assert len(com_cinco) == len(com_uma), (
        f"o quadro passou de {len(com_uma)} para {len(com_cinco)} consultas só "
        "por ter mais sugestões — há um N+1 na página."
    )
