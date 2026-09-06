# tests/test_lista_de_produtos.py
"""`listProducts` — a lista que a tela de liberar precisa para poder oferecer.

O contrato tinha `getProduct` **por id** e nenhuma forma de descobrir ids. Quem
precisa MOSTRAR uma lista para alguém escolher não tinha por onde começar, e a
`DECISAO-cursos-matriculas-e-alunos.md` §7 proíbe o consumidor de guardar uma
cópia própria da lista. Esta operação é o que fecha os dois lados.

O que estes testes protegem, e por que cada um existe:

- **só os ativos**: a escolha existe para LIBERAR acesso, e ninguém deve ser
  liberado num produto aposentado. Se este filtro cair, um produto morto volta
  a aparecer para ser escolhido, e o erro só apareceria quando o aluno abrisse
  a sala;
- **ordem por nome**: quem escolhe é uma pessoa lendo uma lista. Ordem de
  criação é ordem de ninguém;
- **a credencial**: o catálogo é API interna, e a `security` global do contrato
  vale para esta operação como para todas.
"""

import pytest

from apps.produtos.models import Product

pytestmark = pytest.mark.django_db

CAMINHO = "/api/catalogo/produtos"


@pytest.fixture
def token_valido(settings):
    settings.TOKENS_ACEITOS = {"token-de-teste"}
    return "token-de-teste"


def _listar(client, token):
    return client.get(CAMINHO, HTTP_AUTHORIZATION=f"Bearer {token}")


def test_lista_os_produtos_ativos_com_os_campos_do_contrato(client, token_valido):
    Product.objects.create(
        slug="primeiros-dolares", name="Primeiros Dólares com Roblox", price_cents=19700
    )

    resposta = _listar(client, token_valido)

    assert resposta.status_code == 200
    (produto,) = resposta.json()
    assert produto["name"] == "Primeiros Dólares com Roblox"
    assert produto["price_cents"] == 19700
    assert produto["active"] is True
    assert produto["id"]  # o id é o que a matrícula guarda


def test_produto_aposentado_nao_aparece_para_ser_escolhido(client, token_valido):
    Product.objects.create(slug="vivo", name="Curso Vivo", price_cents=1000)
    Product.objects.create(
        slug="aposentado", name="Curso Aposentado", price_cents=1000, active=False
    )

    nomes = [p["name"] for p in _listar(client, token_valido).json()]

    assert nomes == ["Curso Vivo"]


def test_a_ordem_e_a_do_nome_e_nao_a_da_criacao(client, token_valido):
    """Os ids são escolhidos à mão, e essa é a metade que faz o teste valer.

    Com `id` sorteado (UUID4), ordenar por id devolve os três em ordem
    aleatória, e uma em cada seis rodadas ela sai alfabética por acaso: a
    sabotagem "trocar `name` por `id`" passava. Com os ids abaixo, a ordem por
    id e a ordem de criação são as DUAS o inverso da alfabética, então qualquer
    ordenação que não seja por nome reprova sempre.
    """
    Product.objects.create(
        id="00000000-0000-4000-8000-000000000001",
        slug="z",
        name="Zebra",
        price_cents=1000,
    )
    Product.objects.create(
        id="00000000-0000-4000-8000-000000000002",
        slug="m",
        name="Macaco",
        price_cents=1000,
    )
    Product.objects.create(
        id="00000000-0000-4000-8000-000000000003",
        slug="a",
        name="Abelha",
        price_cents=1000,
    )

    nomes = [p["name"] for p in _listar(client, token_valido).json()]

    assert nomes == ["Abelha", "Macaco", "Zebra"]


def test_catalogo_sem_nenhum_produto_devolve_lista_vazia_e_nao_erro(
    client, token_valido
):
    """Primeiro uso: quem abre a tela antes de cadastrar qualquer produto vê uma
    lista vazia, que é um estado normal, e não uma tela quebrada."""
    resposta = _listar(client, token_valido)

    assert resposta.status_code == 200
    assert resposta.json() == []


def test_sem_credencial_a_lista_nao_sai(client, token_valido):
    Product.objects.create(slug="segredo", name="Curso Secreto", price_cents=1000)

    resposta = client.get(CAMINHO)

    assert resposta.status_code == 401
