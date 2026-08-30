"""Guardas da porta de MÁQUINA (`/interno`) — e o que ela NUNCA pode responder.

A invariante desta porta é curta e é dura: **ela só fala de área PÚBLICA.**

Por que ela precisa de guarda próprio, e forte: a porta interna é a superfície
mais fácil de vazar do sistema, porque ninguém olha para ela. Não tem tela, não
tem link, não aparece no navegador de ninguém. Um `filter()` que alguém tire
numa refatoração não quebra página nenhuma — só passa a devolver, para quem
tiver o token, o conteúdo das áreas trancadas de uma escola de menores de idade.

Por isso o teste central aqui **sabota de verdade**: monta uma área de alunos e
uma de turma, com tópico e mensagem dentro, e exige que NADA delas apareça em
NENHUMA das três operações — nem título, nem contagem, nem existência.
"""

from __future__ import annotations

import json

import pytest
from django.test import Client
from django.utils import timezone

from apps.forum.models import Area, Mensagem, Pessoa, Topico

pytestmark = pytest.mark.django_db

TOKEN = "token-de-teste-do-par"


@pytest.fixture(autouse=True)
def par_autorizado(settings):
    settings.TOKENS_ACEITOS = {TOKEN}


@pytest.fixture
def autor():
    return Pessoa.objects.create(
        id_da_plataforma="p_ana", email="ana@exemplo.com", nome_exibido="Ana"
    )


def pedir(caminho: str, token: str | None = TOKEN):
    cabecalhos = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
    return Client().get(f"/interno{caminho}", **cabecalhos)


def corpo(resposta):
    return json.loads(resposta.content)


def montar_o_cenario(autor):
    """Uma área pública COM conteúdo, e duas trancadas TAMBÉM com conteúdo.

    As trancadas precisam ter conteúdo de verdade: uma área trancada vazia
    passaria no teste mesmo se o filtro sumisse — o teste ficaria verde
    provando nada. É a mesma armadilha do cenário fraco.
    """
    publica = Area.objects.create(
        slug="aberta", nome="Dúvidas gerais", visibilidade=Area.Visibilidade.PUBLICA
    )
    de_aluno = Area.objects.create(
        slug="trancada", nome="Só alunos", visibilidade=Area.Visibilidade.ALUNOS
    )
    de_turma = Area.objects.create(
        slug="turma-1",
        nome="Turma de janeiro",
        visibilidade=Area.Visibilidade.TURMA,
        curso_id="curso_x",
    )
    for area, titulo in [
        (publica, "Como faço um cubo"),
        (de_aluno, "SEGREDO DE ALUNO"),
        (de_turma, "SEGREDO DE TURMA"),
    ]:
        topico = Topico.objects.create(area=area, autor=autor, titulo=titulo)
        Mensagem.objects.create(topico=topico, autor=autor, texto=f"corpo de {titulo}")
    return publica, de_aluno, de_turma


# ---------------------------------------------------------------------------
# A INVARIANTE — a sabotagem
# ---------------------------------------------------------------------------
def test_area_trancada_NAO_vaza_por_nenhuma_das_tres_operacoes(autor):
    """**O guarda que justifica este arquivo existir.**

    Se este teste ficar verde com o conteúdo trancado aparecendo, a porta
    interna virou um buraco em volta de `permissoes.py`.
    """
    montar_o_cenario(autor)

    tudo = " ".join(
        pedir(c).content.decode() for c in ["/areas", "/topicos/recentes", "/resumo"]
    )

    for proibido in [
        "trancada",
        "Só alunos",
        "SEGREDO DE ALUNO",
        "turma-1",
        "Turma de janeiro",
        "SEGREDO DE TURMA",
    ]:
        assert proibido not in tudo, f"VAZOU conteúdo de área trancada: {proibido!r}"


def test_as_contagens_do_resumo_contam_so_o_publico(autor):
    """Contagem de área trancada é informação sobre área trancada.

    Este é o vazamento silencioso: nenhum título aparece, mas o número diz
    quantas conversas existem atrás da porta.
    """
    montar_o_cenario(autor)
    dados = corpo(pedir("/resumo"))

    assert dados == {
        "areas_publicas": 1,
        "topicos_publicos": 1,
        "mensagens_publicas": 1,
    }, "o resumo contou algo que não é público"


def test_o_cenario_do_teste_tem_dente(autor):
    """Prova que o cenário acima NÃO é fraco.

    Se as áreas trancadas não tivessem conteúdo, a sabotagem passaria mesmo
    com o filtro removido. Aqui se afirma que há, sim, o que vazar.
    """
    montar_o_cenario(autor)
    assert Area.objects.count() == 3
    assert Topico.objects.count() == 3
    assert Mensagem.objects.count() == 3


# ---------------------------------------------------------------------------
# A porta é fechada por padrão
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("caminho", ["/areas", "/topicos/recentes", "/resumo"])
def test_sem_token_e_401_em_toda_operacao(caminho):
    assert pedir(caminho, token=None).status_code == 401


@pytest.mark.parametrize("caminho", ["/areas", "/topicos/recentes", "/resumo"])
def test_token_errado_e_401_em_toda_operacao(caminho):
    assert pedir(caminho, token="token-de-outra-pessoa").status_code == 401


def test_conjunto_de_tokens_vazio_recusa_todo_mundo(settings):
    """Env ausente ⇒ conjunto vazio ⇒ ninguém entra. Fail-closed por construção.

    O modo de falha que isto mata: a célula sobe sem o token no env e a porta
    fica ABERTA porque "não havia nada com que comparar".
    """
    settings.TOKENS_ACEITOS = set()
    assert pedir("/areas").status_code == 401


# ---------------------------------------------------------------------------
# Nada de dado pessoal
# ---------------------------------------------------------------------------
def test_o_email_do_autor_nunca_sai(autor):
    montar_o_cenario(autor)
    tudo = " ".join(
        pedir(c).content.decode() for c in ["/areas", "/topicos/recentes", "/resumo"]
    )
    assert "ana@exemplo.com" not in tudo, "vazou e-mail"
    assert "p_ana" not in tudo, "vazou o id da plataforma"
    # O nome de exibição PODE sair: é o que já aparece na página pública.
    assert "Ana" in tudo


# ---------------------------------------------------------------------------
# O caminho feliz, e as bordas
# ---------------------------------------------------------------------------
def test_area_publica_desativada_some_da_porta(autor):
    publica, _, _ = montar_o_cenario(autor)
    publica.ativa = False
    publica.save(update_fields=["ativa"])
    assert corpo(pedir("/areas")) == []
    assert corpo(pedir("/resumo"))["areas_publicas"] == 0


def test_topico_nao_publicado_nao_aparece(autor):
    publica, _, _ = montar_o_cenario(autor)
    Topico.objects.filter(area=publica).update(estado=Topico.Estado.REMOVIDO)
    assert corpo(pedir("/topicos/recentes")) == []


def test_mensagem_removida_nao_entra_na_contagem(autor):
    montar_o_cenario(autor)
    Mensagem.objects.update(removida_em=timezone.now())
    assert corpo(pedir("/resumo"))["mensagens_publicas"] == 0


def test_forum_vazio_responde_200_com_lista_vazia_nunca_404():
    """404 obrigaria o consumidor a traduzir erro em "fórum vazio"."""
    assert pedir("/areas").status_code == 200
    assert corpo(pedir("/areas")) == []
    assert corpo(pedir("/resumo")) == {
        "areas_publicas": 0,
        "topicos_publicos": 0,
        "mensagens_publicas": 0,
    }


def test_o_limite_de_recentes_e_cortado_em_vez_de_recusado(autor):
    """Consumidor nenhum deve quebrar por pedir demais."""
    montar_o_cenario(autor)
    assert pedir("/topicos/recentes?limite=9999").status_code == 200
    assert pedir("/topicos/recentes?limite=0").status_code == 200
    assert pedir("/topicos/recentes?limite=-5").status_code == 200
