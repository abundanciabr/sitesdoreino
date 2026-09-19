"""A lista do painel em pedaços: `GET /matriculas/pagina`.

Por que esta porta existe: `/matriculas` devolve a escola inteira numa resposta
só, e a tela do painel precisa de uma página por vez mais os contadores de cada
estado. O desenho está no brief 58 do Plano mestre: envelope `itens`,
`proximo_cursor`, `total` e `contagens`, com `/matriculas` intocada.

**O teste que carrega este arquivo** é
`test_paginar_nao_pula_nem_repete_quando_a_ordem_de_compra_diverge_da_de_insercao`.
Em 16/09/2026 duas sessões construíram esta porta em paralelo, sem saber uma da
outra, e uma delas paginou por `pk__lt`. `alunos_do_painel` ordena por
`-enrolled_at`, que não acompanha a ordem de `pk`: a escola real, onde a data
de compra não segue a ordem de inserção, veria alunos sumindo de uma página e
aparecendo em outra. Este teste reprova essa implementação e aprova a que
pagina por deslocamento.

Os outros três que vale nomear:

- `test_os_contadores_nao_zeram_quando_o_mantenedor_filtra_por_um_estado`. A
  outra implementação contava sobre a consulta já filtrada, então filtrar por
  "ativa" zerava os outros três contadores da tela. A tela diria que não há
  aluno pausado numa escola que tem.
- `test_estado_inventado_cai_em_todos_como_na_porta_irma`. `/matriculas` já
  decidiu isso, com o motivo escrito: esconder alunos faria o painel dizer
  "não há ninguém" para quem tem gente. Duas portas do mesmo recurso com
  regras diferentes é como uma tela começa a mentir.
- `test_a_escola_sem_ninguem_devolve_pagina_vazia_sem_erro`. Primeiro uso é um
  estado, não um acidente.
"""

import itertools
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.matriculas.models import Matricula

PAGINA = "/api/alunos/matriculas/pagina"

_sequencia = itertools.count(1)


@pytest.fixture
def token_valido(settings):
    settings.TOKENS_ACEITOS = {"token-de-teste"}
    return "token-de-teste"


@pytest.fixture
def auth(token_valido):
    return {"HTTP_AUTHORIZATION": f"Bearer {token_valido}"}


def criar(**campos) -> Matricula:
    corpo = {
        "site_id": "escola-a",
        "order_id": f"pedido-{next(_sequencia)}",
        "email": f"aluno-{next(_sequencia)}@example.com",
        "name": "Fulano de Tal",
        "status": Matricula.STATUS_ATIVA,
    }
    corpo.update(campos)
    return Matricula.objects.create(**corpo)


def comprou_em(linha: Matricula, dias_atras: int) -> None:
    """`enrolled_at` é `auto_now_add`, então só `update` a coloca onde se quer."""
    Matricula.objects.filter(pk=linha.pk).update(
        enrolled_at=timezone.now() - timedelta(days=dias_atras)
    )


def pedir(client, auth, **query):
    url = PAGINA
    if query:
        url += "?" + "&".join(f"{k}={v}" for k, v in query.items())
    return client.get(url, **auth)


# ------------------------------------------------------------- a paginação


@pytest.mark.django_db
def test_paginar_nao_pula_nem_repete_quando_a_ordem_de_compra_diverge_da_de_insercao(
    client, auth
):
    """O caso real: a ordem de compra não é a ordem em que as linhas nasceram.

    Cinco alunos inseridos na ordem 1..5, com as datas de compra embaralhadas de
    propósito. Paginando de dois em dois, a soma das páginas tem de ser a lista
    inteira, na ordem da lista inteira, sem repetir e sem pular ninguém.
    """
    linhas = [criar(email=f"pessoa-{i}@example.com") for i in range(5)]
    for linha, dias in zip(linhas, [3, 30, 1, 20, 10]):
        comprou_em(linha, dias)

    esperado = [
        linha["email"] for linha in pedir(client, auth, limite=100).json()["itens"]
    ]
    assert len(esperado) == 5

    colhidos, cursor, paginas = [], None, 0
    while True:
        corpo = pedir(client, auth, limite=2, **({"cursor": cursor} if cursor else {}))
        assert corpo.status_code == 200
        corpo = corpo.json()
        colhidos += [linha["email"] for linha in corpo["itens"]]
        paginas += 1
        cursor = corpo["proximo_cursor"]
        if cursor is None:
            break
        assert paginas < 10, "paginação não terminou; o cursor não está andando"

    assert colhidos == esperado
    assert len(colhidos) == len(set(colhidos)), "alguém apareceu em duas páginas"


@pytest.mark.django_db
def test_a_ultima_pagina_nao_promete_uma_proxima(client, auth):
    criar()
    criar()
    corpo = pedir(client, auth, limite=2).json()
    assert len(corpo["itens"]) == 2
    assert corpo["proximo_cursor"] is None


@pytest.mark.django_db
def test_o_total_conta_a_escola_inteira_e_nao_a_pagina(client, auth):
    for _ in range(5):
        criar()
    corpo = pedir(client, auth, limite=2).json()
    assert len(corpo["itens"]) == 2
    assert corpo["total"] == 5


# ------------------------------------------------------------- os contadores


@pytest.mark.django_db
def test_os_contadores_nao_zeram_quando_o_mantenedor_filtra_por_um_estado(client, auth):
    criar(status=Matricula.STATUS_ATIVA)
    criar(status=Matricula.STATUS_ATIVA)
    criar(status=Matricula.STATUS_SUSPENSA)
    criar(status=Matricula.STATUS_ENCERRADA)

    corpo = pedir(client, auth, status=Matricula.STATUS_ATIVA).json()

    assert [linha["status"] for linha in corpo["itens"]] == ["ativa", "ativa"]
    assert corpo["total"] == 2
    assert corpo["contagens"] == {
        "ativa": 2,
        "suspensa": 1,
        "encerrada": 1,
        "reembolsada": 0,
    }


@pytest.mark.django_db
def test_os_contadores_respeitam_a_escola_pedida(client, auth):
    criar(site_id="escola-a")
    criar(site_id="escola-b")
    criar(site_id="escola-b")

    corpo = pedir(client, auth, site_id="escola-b").json()

    assert corpo["total"] == 2
    assert corpo["contagens"]["ativa"] == 2


# ------------------------------------------------------------- os limites


@pytest.mark.django_db
@pytest.mark.parametrize("limite", [0, -1, 101])
def test_limite_fora_da_faixa_recusa_com_422(client, auth, limite):
    criar()
    resposta = pedir(client, auth, limite=limite)
    assert resposta.status_code == 422


@pytest.mark.django_db
def test_cursor_inventado_recusa_com_422_dizendo_o_que_fazer(client, auth):
    criar()
    resposta = pedir(client, auth, cursor="isto-nao-e-um-cursor")
    assert resposta.status_code == 422
    assert "pagina anterior" in resposta.json()["detail"]


@pytest.mark.django_db
def test_o_cursor_que_esta_porta_emite_e_aceito_por_ela_mesma(client, auth):
    """O `rstrip("=")` do emissor já quebrou um decode que não repõe o padding."""
    for _ in range(3):
        criar()
    cursor = pedir(client, auth, limite=1).json()["proximo_cursor"]
    assert cursor is not None
    assert pedir(client, auth, limite=1, cursor=cursor).status_code == 200


# ------------------------------------------------------------- quem entra


@pytest.mark.django_db
def test_a_pagina_nao_traz_quem_ainda_esta_na_fila(client, auth):
    criar(email="aluno@example.com")
    criar(
        email="espera@example.com",
        order_id="pre:1",
        status=Matricula.STATUS_AGUARDANDO,
    )
    corpo = pedir(client, auth).json()
    assert [linha["email"] for linha in corpo["itens"]] == ["aluno@example.com"]
    assert corpo["total"] == 1


@pytest.mark.django_db
def test_estado_inventado_cai_em_todos_como_na_porta_irma(client, auth):
    criar(status=Matricula.STATUS_ATIVA)
    criar(status=Matricula.STATUS_SUSPENSA)
    corpo = pedir(client, auth, status="estado-que-nao-existe").json()
    assert corpo["total"] == 2


@pytest.mark.django_db
def test_a_escola_sem_ninguem_devolve_pagina_vazia_sem_erro(client, auth):
    corpo = pedir(client, auth).json()
    assert corpo["itens"] == []
    assert corpo["total"] == 0
    assert corpo["proximo_cursor"] is None
    assert corpo["contagens"] == {
        "ativa": 0,
        "suspensa": 0,
        "encerrada": 0,
        "reembolsada": 0,
    }
