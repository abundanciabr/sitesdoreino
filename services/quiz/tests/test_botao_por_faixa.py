"""A tela de resultado deixa de ser um beco sem saída.

Quem termina o Crivo recebia um diagnóstico e mais nada: nenhum link, nenhum
passo seguinte. O lead entrava no funil e parava ali. O botão é da FAIXA porque
o passo de quem está começando não é o de quem está pronto para escalar.

O destino é OPACO para esta célula, de propósito: o Crivo não sabe o que é um
checkout (AGENTS.quiz.md, "Consome: nada"). Ele guarda e mostra o endereço que o
operador plantou pelo `seed_quiz` — por isso não há aqui nenhuma constante
`/checkout/...` e nenhum teste que a exija.
"""

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction

from apps.quiz.models import (
    Option,
    Question,
    Quiz,
    QuizVersion,
    ResultBand,
    Site,
    Submission,
)

HOST = "quiz-botao.exemplo.com"
DESTINO = "/checkout/curso-teste/"

pytestmark = pytest.mark.django_db


@pytest.fixture
def quiz_a(db):
    site = Site.objects.create(id="site-botao", host=HOST, name="Site do Botão")
    quiz = Quiz.objects.create(site=site, slug="crivo", title="Crivo")
    versao = QuizVersion.objects.create(
        quiz=quiz, key="original", weight=100, active=True
    )
    pergunta = Question.objects.create(version=versao, order=1, text="Pergunta 1")
    Option.objects.create(question=pergunta, order=1, text="Zero", points=0)
    Option.objects.create(question=pergunta, order=2, text="Dez", points=10)
    return quiz


def _submeter(client, quiz, pontos):
    pergunta = quiz.versions.get().questions.get(order=1)
    envio = client.post(
        f"/{quiz.slug}/",
        {
            f"pergunta_{pergunta.id}": pergunta.options.get(points=pontos).id,
            "email": "lead@exemplo.com",
        },
        HTTP_HOST=HOST,
    )
    assert envio.status_code == 302
    return client.get(envio["Location"], HTTP_HOST=HOST)


# ---------------------------------------------------------------------------
# A tela
# ---------------------------------------------------------------------------


def test_o_resultado_mostra_o_botao_da_faixa_que_a_pessoa_caiu(client, quiz_a):
    ResultBand.objects.create(
        version=quiz_a.versions.get(),
        key="baixo",
        title="Baixo",
        min_score=0,
        max_score=4,
        botao_destino="/comece-aqui/",
        botao_rotulo="Começar pelo básico",
    )
    ResultBand.objects.create(
        version=quiz_a.versions.get(),
        key="alto",
        title="Alto",
        min_score=5,
        max_score=10,
        botao_destino=DESTINO,
        botao_rotulo="Quero escalar agora",
    )

    pagina = _submeter(client, quiz_a, pontos=10).content.decode()

    assert f'href="{DESTINO}"' in pagina
    assert "Quero escalar agora" in pagina
    # O botão da OUTRA faixa não pode aparecer: é isso que "por faixa" quer dizer.
    assert "Começar pelo básico" not in pagina
    assert "/comece-aqui/" not in pagina


def test_faixa_sem_botao_mostra_o_diagnostico_e_nenhum_link(client, quiz_a):
    """O estado vazio. Um botão sem destino seria pior que nenhum botão: a
    pessoa clica e não sai do lugar."""
    ResultBand.objects.create(
        version=quiz_a.versions.get(),
        key="alto",
        title="Alto",
        min_score=0,
        max_score=10,
    )

    pagina = _submeter(client, quiz_a, pontos=10).content.decode()

    assert "Alto" in pagina
    assert 'class="botao"' not in pagina
    assert "<a " not in pagina


def test_destino_sem_rotulo_e_recusado_pelo_banco(quiz_a):
    """A regra mora no banco, não no template: tela não é lugar de descobrir
    que o dado está pela metade."""
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ResultBand.objects.create(
                version=quiz_a.versions.get(),
                key="torto",
                title="Torto",
                min_score=0,
                max_score=10,
                botao_destino=DESTINO,
            )


# ---------------------------------------------------------------------------
# O seed
# ---------------------------------------------------------------------------


def _semear(**extra):
    call_command(
        "seed_quiz",
        host=HOST,
        site_id="site-semeado",
        site_name="Site Semeado",
        destino_do_botao=DESTINO,
        **extra,
    )
    return Quiz.objects.get(slug="crivo", site_id="site-semeado")


def test_o_seed_planta_as_tres_faixas_com_botao(db):
    quiz = _semear()

    versao = quiz.versions.get(key="original")
    faixas = list(versao.bands.all())
    assert [f.key for f in faixas] == ["iniciante", "intermediario", "avancado"]
    assert {f.botao_destino for f in faixas} == {DESTINO}
    # Rótulos distintos: é o que faz o botão ser diferente por faixa.
    assert len({f.botao_rotulo for f in faixas}) == 3
    assert all(f.botao_rotulo for f in faixas)


def test_o_seed_poe_botao_em_faixa_que_ja_existia_sem_ele(db):
    """A regressão que o `get_or_create` deixaria passar em silêncio.

    Todo banco semeado antes deste PR tem as três faixas SEM botão. Um seed que
    só criasse o que falta encontraria as linhas, não escreveria nada, sairia
    com "✅" e deixaria a tela no beco sem saída — sem erro nenhum para avisar.
    """
    site = Site.objects.create(id="site-semeado", host=HOST, name="Site Semeado")
    quiz = Quiz.objects.create(site=site, slug="crivo", title="Crivo")
    versao = QuizVersion.objects.create(
        quiz=quiz, key="original", weight=100, active=True
    )
    ResultBand.objects.create(
        version=versao, key="iniciante", title="Antigo", min_score=0, max_score=9
    )

    _semear()

    faixa = versao.bands.get(key="iniciante")
    assert faixa.botao_destino == DESTINO
    assert faixa.botao_rotulo


def test_o_seed_continua_idempotente(db):
    _semear()
    _semear()

    quiz = Quiz.objects.get(slug="crivo", site_id="site-semeado")
    versao = quiz.versions.get(key="original")
    assert Quiz.objects.count() == 1
    assert versao.bands.count() == 3
    assert versao.questions.count() == 3
    assert Option.objects.filter(question__version=versao).count() == 9
    assert Submission.objects.count() == 0


def test_o_seed_exige_o_destino_em_vez_de_inventar_um(db):
    """Sem destino não há botão, e sem botão a tela volta a ser beco. O comando
    tem de recusar NA LINHA DE COMANDO, antes de escrever qualquer coisa.

    `CommandError` e não `Exception`: com o argumento opcional o seed chega a
    gravar e morre lá adiante na restrição do banco, cujo nome por acaso contém
    a palavra "destino". Um teste frouxo aqui ficava verde com o argumento
    opcional — foi a prova por mutação que mostrou isso.
    """
    with pytest.raises(CommandError) as erro:
        call_command(
            "seed_quiz",
            host=HOST,
            site_id="site-semeado",
            site_name="Site Semeado",
        )

    assert "--destino-do-botao" in str(erro.value)
    assert not Quiz.objects.exists()
    assert not ResultBand.objects.exists()
