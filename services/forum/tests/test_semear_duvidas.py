"""Guardas da semeadura das dúvidas da escola, e da autoria INSTITUCIONAL.

O que se protege aqui não é "o Django salvou dez tópicos". É a regra dura que o
mantenedor escolheu com todas as letras em 30/08/2026 (registro
`20260830-021`, tarefa TAR-020):

    as mensagens semeadas são publicadas EM NOME DA ESCOLA, e nenhuma delas
    pode fingir ser de aluno, nem com nome inventado, nem com conta de mentira,
    nem com um rótulo genérico que sugira uma pessoa.

Um fórum recém-aberto é a tentação clássica de inventar movimento: criar cinco
contas com nome de gente e encher o salão. O modelo de dados desta célula não
sabia dizer "quem publicou isto foi a instituição" (todo tópico e toda mensagem
EXIGIAM uma `Pessoa`), então a saída fácil era exatamente a proibida. É por isso
que a capacidade nasce junto com o conteúdo, e com restrição no BANCO.

O CENÁRIO FRACO QUE ESTES TESTES EVITAM (`armadilhas/183`): uma suíte que só
provasse "nenhuma mensagem tem autor pessoa" ficaria verde num fórum onde nada
foi semeado. Por isso toda proibição aqui vem acompanhada da prova positiva de
que o conteúdo existe e chega à tela.
"""

from __future__ import annotations

import re
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import Client

from apps.core.sessao import Ator
from apps.forum.models import Area, Mensagem, Pessoa, Topico

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# As formas de risca longa que não podem aparecer em texto publicado.
#
# A lista é a mesma de `ci/travessao.py`, e a repetição aqui NÃO é uma segunda
# verdade: o portão do repositório já varre este comando (a superfície dele
# inclui `management/commands/*.py`), e quem manda continua sendo ele. Este
# teste é o alarme que toca na hora, dentro da célula, para quem estiver
# escrevendo dúvida nova não descobrir só no CI.
# ---------------------------------------------------------------------------
RISCAS_LONGAS = ("—", "–", "―", "&mdash;", "&ndash;", "&#8212;")


@pytest.fixture
def semeado():
    """As áreas primeiro, as dúvidas depois. A ordem é a do mundo real."""
    call_command("semear_areas", stdout=StringIO())
    saida = StringIO()
    call_command("semear_duvidas", stdout=saida)
    return saida.getvalue()


def aluno_qualquer() -> Ator:
    pessoa = Pessoa.objects.create(
        id_da_plataforma="p_aluno", email="aluno@exemplo.com", nome_exibido="Aluno"
    )
    return Ator(pessoa=pessoa, eh_aluno=True, eh_professor=False)


# ===========================================================================
# 1. A CAPACIDADE: o fórum precisa SABER publicar em nome da instituição
# ===========================================================================
# Estes três testes reprovam na ASSERÇÃO no código anterior à TAR-020
# (`armadilhas/195`): eles perguntam ao modelo, no vocabulário que ele já
# tinha, se a escola consegue assinar sem inventar gente.


def test_o_autor_pessoa_deixou_de_ser_obrigatorio():
    """Enquanto `autor` for obrigatório, publicar como escola exige um aluno falso."""
    for modelo in (Topico, Mensagem):
        assert modelo._meta.get_field("autor").null, (
            f"{modelo.__name__}.autor continua obrigatório: para a escola "
            "publicar, alguém teria de criar uma Pessoa de mentira, que é "
            "exatamente o que o mantenedor proibiu em 30/08/2026"
        )


def test_existe_a_declaracao_explicita_de_que_quem_fala_e_a_escola():
    """Ausência de autor NÃO é a declaração: silêncio não pode virar a voz da escola."""
    for modelo in (Topico, Mensagem):
        campos = {f.name for f in modelo._meta.get_fields()}
        assert "publicado_pela_escola" in campos, (
            f"{modelo.__name__} não sabe declarar autoria institucional. Sem um "
            "campo explícito, a única leitura possível seria 'sem autor logo é "
            "da escola', e aí um bug que esquecesse o autor publicaria em nome "
            "da instituição por acidente"
        )


def test_a_tela_tem_uma_assinatura_para_mostrar():
    for modelo in (Topico, Mensagem):
        assert hasattr(modelo, "assinatura"), (
            f"{modelo.__name__} não expõe `assinatura`. Sem ela cada template "
            "resolveria a autoria por conta própria, e o primeiro que "
            "esquecesse mostraria o rótulo genérico de pessoa"
        )


# ===========================================================================
# 2. O BANCO RECUSA AS DUAS MENTIRAS POSSÍVEIS
# ===========================================================================
# A regra que protege criança não pode morar só em código de aplicação. Uma
# tela de administração futura, ou uma linha editada à mão no `psql` numa
# madrugada de incidente, faria a combinação proibida existir sem ninguém
# saber. É a `RETROSPECTIVA-FASE-D` §2 aplicada de novo nesta célula.


def _area_de_teste() -> Area:
    return Area.objects.create(
        slug="teste", nome="Teste", visibilidade=Area.Visibilidade.ALUNOS
    )


def test_o_banco_recusa_mensagem_orfa_sem_declarar_a_escola():
    """Esquecer o autor não pode virar, em silêncio, uma fala da instituição."""
    area = _area_de_teste()
    topico = Topico.objects.create(area=area, titulo="t", publicado_pela_escola=True)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Mensagem.objects.create(
                topico=topico, autor=None, publicado_pela_escola=False, texto="x"
            )


def test_o_banco_recusa_uma_pessoa_publicando_como_se_fosse_a_escola():
    """O outro lado: ninguém empresta a voz da instituição para a própria fala."""
    area = _area_de_teste()
    pessoa = aluno_qualquer().pessoa
    topico = Topico.objects.create(area=area, autor=pessoa, titulo="t")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Mensagem.objects.create(
                topico=topico, autor=pessoa, publicado_pela_escola=True, texto="x"
            )


# ===========================================================================
# 3. O CONTEÚDO SEMEADO: existe, é da escola, e NENHUM aluno foi inventado
# ===========================================================================


def test_a_semeadura_enche_o_forum(semeado):
    """A prova POSITIVA. Sem ela, tudo abaixo ficaria verde num fórum vazio."""
    assert Topico.objects.count() >= 8, "o fórum continuou praticamente deserto"
    assert Mensagem.objects.count() >= Topico.objects.count() * 2


def test_nenhuma_pessoa_foi_inventada_pela_semeadura(semeado):
    """**O guarda do mandato.** Semear não cria gente, nem com nome bonito."""
    assert Pessoa.objects.count() == 0, (
        "a semeadura criou pessoas no banco: alguma mensagem está fingindo ser "
        "de aluno, e foi exatamente isso que o mantenedor proibiu"
    )


def test_toda_mensagem_semeada_e_da_escola(semeado):
    for mensagem in Mensagem.objects.all():
        assert (
            mensagem.autor_id is None and mensagem.publicado_pela_escola
        ), f"a mensagem {mensagem.pk} não está assinada pela escola"
    for topico in Topico.objects.all():
        assert topico.autor_id is None and topico.publicado_pela_escola


def test_a_assinatura_na_tela_e_o_nome_da_escola_e_nunca_alguem(
    semeado, client: Client
):
    """Medido pelo HTML que chega ao navegador, não pelo objeto em memória.

    O rótulo genérico de pessoa (`alguém`) é o default do template quando o
    nome de exibição está vazio. Se a assinatura institucional falhasse, é ele
    que apareceria, e ele sugere uma pessoa: é o avatar genérico que o
    mantenedor recusou, escrito em palavra.
    """
    topico = Topico.objects.filter(area__slug="avisos").first()
    assert topico is not None, "nada foi semeado na área que o visitante lê"

    pagina = client.get(f"/t/{topico.pk}")
    assert pagina.status_code == 200
    html = pagina.content.decode("utf-8")
    # O nome da escola já aparece no cabeçalho de toda página, então medir só a
    # presença dele não provaria nada. A régua é a assinatura NO LUGAR do autor.
    assert '<span class="autor">Meshcraft Academy</span>' in html, (
        "a mensagem não saiu assinada pela escola no lugar onde o nome de quem "
        "escreveu aparece"
    )
    assert "alguém" not in html, (
        "a tela mostrou o rótulo genérico de pessoa numa página em que quem "
        "fala é a instituição"
    )


def test_o_visitante_encontra_conteudo_na_porta_do_forum(semeado, client: Client):
    """O salão vazio (lei §6.1) medido de fora, sem sessão nenhuma."""
    home = client.get("/")
    assert home.status_code == 200
    assert "Avisos da escola" in home.content.decode("utf-8")

    area = client.get("/a/avisos")
    assert area.status_code == 200
    corpo = area.content.decode("utf-8")
    assert "Nenhuma conversa por aqui ainda" not in corpo


def test_o_aluno_encontra_duvidas_ja_respondidas(semeado):
    """A razão de existir da tarefa: quem chega vê pergunta com resposta."""
    duvidas = Topico.objects.filter(area__slug="duvidas")
    assert duvidas.count() >= 5, "a área de dúvidas continuou quase vazia"
    for topico in duvidas:
        assert topico.resposta_aceita_id, (
            f"o tópico `{topico.titulo}` foi semeado sem resposta aceita: um "
            "fórum semeado com perguntas sem resposta é pior que um vazio"
        )


# ===========================================================================
# 4. O TEXTO PUBLICADO OBEDECE À REGRA DE ESCRITA
# ===========================================================================


def test_nenhuma_risca_longa_no_texto_semeado(semeado):
    """Decisão do mantenedor em 30/08/2026: texto publicado sai sem travessão."""
    for mensagem in Mensagem.objects.all():
        for risca in RISCAS_LONGAS:
            assert risca not in mensagem.texto, (
                f"a mensagem {mensagem.pk} publica `{risca}`. A troca é uma "
                "REESCRITA da frase, não um caractere trocado"
            )
    for topico in Topico.objects.all():
        for risca in RISCAS_LONGAS:
            assert risca not in topico.titulo


def test_todo_titulo_semeado_cabe_no_que_a_tela_aceita(semeado):
    """O mesmo teto que a view aplica ao aluno vale para a escola."""
    for topico in Topico.objects.all():
        assert 5 <= len(topico.titulo) <= 180, topico.titulo


# ===========================================================================
# 5. A BUSCA ENCONTRA O QUE FOI SEMEADO
# ===========================================================================


def test_a_coluna_de_busca_foi_preenchida_na_escrita(semeado):
    """Lei §4.4: a busca é calculada na ESCRITA, nunca no `WHERE` da consulta.

    Uma semeadura que esquecesse este passo entregaria dez tópicos invisíveis
    para a busca do site, e o defeito só apareceria quando alguém procurasse.
    """
    assert not Mensagem.objects.filter(busca__isnull=True).exists()


# ===========================================================================
# 6. RODAR DE NOVO NÃO DUPLICA, E NÃO PISA EM EDIÇÃO HUMANA
# ===========================================================================


def test_rodar_de_novo_nao_duplica_nem_desfaz_edicao(semeado):
    quantos = Topico.objects.count()
    alvo = Topico.objects.filter(area__slug="duvidas").first()
    Mensagem.objects.filter(topico=alvo).update(texto="O QUE O DONO ESCREVEU")

    saida = StringIO()
    call_command("semear_duvidas", stdout=saida)

    assert Topico.objects.count() == quantos, "a semeadura duplicou ao rodar de novo"
    assert Mensagem.objects.filter(topico=alvo).first().texto == "O QUE O DONO ESCREVEU"
    assert "ja existia" in saida.getvalue()


def test_semear_sem_as_areas_para_por_seguranca():
    """Fail-closed: este comando publica conteúdo, ele não inventa área nenhuma."""
    with pytest.raises(CommandError) as recusa:
        call_command("semear_duvidas", stdout=StringIO(), stderr=StringIO())
    # A mensagem entra na asserção de propósito: `CommandError` também é o que
    # o Django levanta para comando INEXISTENTE, e um teste que só exigisse a
    # classe ficaria verde antes de o comando nascer (`armadilhas/195`).
    assert "PAROU POR SEGURANCA" in str(recusa.value)
    assert Topico.objects.count() == 0


def test_a_linha_que_o_pipeline_procura_existe(semeado):
    """`armadilhas/114`: o log da ssh-action ecoa o script inteiro.

    A frase que comprova execução não pode ser uma que também apareça no eco do
    shell. Esta vem do Python, do fim do caminho feliz.
    """
    assert "SEMEADURA DAS DUVIDAS OK" in semeado
    assert re.search(r"TOPICOS DA ESCOLA: \d+", semeado)


# ===========================================================================
# 7. A PORTA DE MÁQUINA NÃO QUEBRA COM AUTORIA INSTITUCIONAL
# ===========================================================================


def test_a_porta_de_maquina_devolve_a_escola_como_autor(semeado, settings):
    """`/interno/topicos/recentes` lia `autor.nome_exibido` direto.

    Com autoria institucional isso seria `AttributeError` num `None`, ou seja,
    HTTP 500 na vitrine que o resto do site consome. A porta é a superfície que
    ninguém olha (`tests/test_porta_de_maquina.py`), então ela ganha guarda no
    mesmo PR que muda o modelo.
    """
    settings.TOKENS_ACEITOS = {"token-da-semeadura"}
    resposta = Client().get(
        "/interno/topicos/recentes",
        HTTP_AUTHORIZATION="Bearer token-da-semeadura",
    )
    assert resposta.status_code == 200, resposta.content
    dados = resposta.json()
    assert dados, "a vitrine pública do fórum voltou vazia depois da semeadura"
    assert all(item["autor"] == "Meshcraft Academy" for item in dados)
