# tests/test_create_product.py
"""`createProduct`: cadastrar um produto pela porta, com as regras do comando.

Até 07/09/2026 um produto só nascia por `manage.py criar_curso`, rodado na VPS
pelo mantenedor a partir de um bloco de colar. A decisão de 07/09/2026
(`DECISAO-a-sala-serve-varios-cursos.md`) diz que criar um curso tem de ser
fácil e pelo Admin, e a tela do Admin precisa de uma porta para chamar.

O que cada teste protege, e por que existe:

- **o produto nasce com preço zero e ativo**: quem cobra é a oferta, que é por
  site. Zero aqui significa "não está à venda por este produto", nunca "de
  graça". Se este valor virar outra coisa, um curso passa a ter preço próprio
  fora da oferta, e a plataforma cobra por um caminho que ninguém desenhou;
- **a resposta tem exatamente os quatro campos do contrato**: o apelido é chave
  interna e não faz parte do contrato de hoje. O caminho do 201 devolve o corpo
  cru, sem o Schema filtrar nada, então esta é a única guarda contra vazar
  campo novo por ali;
- **repetir o mesmo cadastro não cria duplicata**: a tela pode ser reenviada
  (dois cliques, recarregar a página) sem que nasçam dois cursos com o mesmo
  apelido;
- **apelido usado com outro nome recusa e não altera nada**: o nome sai na
  lista de escolher, e trocá-lo é gesto de quem opera a máquina, pelo comando
  com `--renomear`. Renomear em silêncio por um POST reenviado seria perder o
  nome antigo sem ninguém pedir;
- **apelido fora da forma e nome vazio param na porta**: o apelido é chave, e
  chave com espaço ou maiúscula quebra a repetibilidade do cadastro;
- **a credencial**: o catálogo é API interna, e a `security` global do contrato
  vale para esta escrita como vale para o `putSiteMenu`.
"""

import pytest

from apps.produtos.models import Product

pytestmark = pytest.mark.django_db

CAMINHO = "/api/catalogo/produtos"


@pytest.fixture
def token_valido(settings):
    settings.TOKENS_ACEITOS = {"token-de-teste"}
    return "token-de-teste"


def _cadastrar(client, token, **corpo):
    return client.post(
        CAMINHO,
        data=corpo,
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )


def test_cadastra_o_produto_e_devolve_201_com_os_campos_do_contrato(
    client, token_valido
):
    resposta = _cadastrar(
        client, token_valido, slug="profissional", name="Profissional"
    )

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert set(corpo) == {"id", "name", "price_cents", "active"}
    assert corpo["name"] == "Profissional"
    assert corpo["price_cents"] == 0
    assert corpo["active"] is True

    produto = Product.objects.get(slug="profissional")
    assert str(produto.id) == corpo["id"]
    assert produto.price_cents == 0
    assert produto.active is True


def test_cadastrar_de_novo_o_mesmo_devolve_200_e_nao_cria_duplicata(
    client, token_valido
):
    primeira = _cadastrar(
        client, token_valido, slug="profissional", name="Profissional"
    )
    segunda = _cadastrar(client, token_valido, slug="profissional", name="Profissional")

    assert primeira.status_code == 201
    assert segunda.status_code == 200
    assert segunda.json()["id"] == primeira.json()["id"]
    assert Product.objects.filter(slug="profissional").count() == 1


def test_apelido_usado_com_outro_nome_recusa_e_nao_altera_nada(client, token_valido):
    _cadastrar(client, token_valido, slug="profissional", name="Profissional")

    resposta = _cadastrar(
        client, token_valido, slug="profissional", name="Profissional 2026"
    )

    assert resposta.status_code == 409
    recado = resposta.json()["detail"]
    assert "Profissional" in recado
    assert "--renomear" in recado
    assert Product.objects.get(slug="profissional").name == "Profissional"


def test_apelido_fora_da_forma_para_na_porta(client, token_valido):
    """Maiúscula e espaço quebrariam a chave que torna o cadastro repetível."""
    resposta = _cadastrar(client, token_valido, slug="Curso Novo", name="Curso Novo")

    assert resposta.status_code == 422
    assert Product.objects.count() == 0


def test_nome_so_de_espacos_para_na_porta(client, token_valido):
    """Nome em branco nasceria como uma linha em branco na lista de escolher."""
    resposta = _cadastrar(client, token_valido, slug="sem-nome", name="   ")

    assert resposta.status_code == 422
    assert Product.objects.count() == 0


def test_o_nome_entra_sem_os_espacos_das_pontas(client, token_valido):
    """Mesma regra do comando: o nome guardado é o aparado, e é ele que decide
    se um cadastro repetido é o mesmo cadastro."""
    criado = _cadastrar(client, token_valido, slug="aparado", name="  Profissional  ")
    repetido = _cadastrar(client, token_valido, slug="aparado", name="Profissional")

    assert criado.status_code == 201
    assert repetido.status_code == 200
    assert criado.json()["name"] == "Profissional"


def test_sem_credencial_nenhum_produto_nasce(client, token_valido):
    resposta = client.post(
        CAMINHO,
        data={"slug": "invasor", "name": "Curso do Invasor"},
        content_type="application/json",
    )

    assert resposta.status_code == 401
    assert Product.objects.count() == 0


def test_com_credencial_errada_nenhum_produto_nasce(client, token_valido):
    """Chave presente mas desconhecida é o mesmo 401 de chave ausente: a porta
    não distingue os dois para fora, e nada nasce em nenhum dos casos."""
    resposta = _cadastrar(
        client, "token-que-ninguem-cadastrou", slug="invasor", name="Curso do Invasor"
    )

    assert resposta.status_code == 401
    assert Product.objects.count() == 0
