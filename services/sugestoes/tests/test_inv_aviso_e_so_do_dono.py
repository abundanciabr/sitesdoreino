# tests/test_inv_aviso_e_so_do_dono.py  # [RECEITA:R5 v1]
"""INV-SUG09 — ninguém vê, conta nem marca o aviso de outra pessoa.

**O guarda mais importante do EVO-21.** Um aviso carrega o título da sugestão de
alguém e a nota que a equipe escreveu sobre ela — inclusive o "não vamos fazer, e
por quê", que existe para UMA pessoa ler. Vazar isso não é bug de listagem: é a
Caixa entregando a conversa privada de um aluno a outro.

As três metades, e por que nenhuma dispensa as outras:

* **ler** — a lista de A não pode conter nada de B (nem o título, nem a nota);
* **contar** — o número do sino de A não pode somar o de B, senão o vazamento
  vira um contador que ninguém sabe explicar;
* **escrever** — A não pode marcar como lido o aviso de B, nem por chute de id.

E a resposta ao chute é **404, nunca 403**: 403 diria "existe, mas não é seu", que
é confirmar a existência do aviso alheio a quem estava enumerando. O recorte por
dono mora no próprio `get` (`apps/core/avisos.py::_meus`), de modo que não há
nenhum instante em que a linha de outra pessoa esteja carregada nesta requisição.

Aqui também mora o INVARIANTE 3 (marcar como lido é idempotente) e a metade do
INVARIANTE 4 que se prova por comportamento — a varredura do urlconf que garante
que rota nova nasce com porteiro é a de `test_inv_sem_sessao_nada.py`, e as duas
rotas do sininho já caem nela por derivação, sem ninguém cadastrá-las.
"""

import pytest
from django.urls import URLPattern, reverse

from apps.core.avisos import contar_nao_lidos
from apps.sugestoes.models import Aviso

pytestmark = pytest.mark.django_db


@pytest.fixture
def outra_pessoa(entrar_como):
    """Alguém que entrou pela porta de verdade e não tem aviso nenhum."""
    return entrar_como(email="bianca@exemplo.test", nome="Bianca")


# ---------------------------------------------------------------------------
# Ler
# ---------------------------------------------------------------------------


def test_a_lista_mostra_o_meu_aviso(dentro, aviso):
    corpo = dentro.client.get(reverse("avisos")).content.decode()

    assert aviso.sugestao.titulo in corpo
    assert aviso.nota in corpo


def test_a_data_do_aviso_sai_no_fuso_e_no_formato_de_quem_le(dentro, aviso):
    """A primeira data que a Caixa mostra a um aluno — e ela saía errada duas vezes.

    Nenhuma página desta célula renderizava data até o EVO-21, então dois defaults
    de fábrica passaram despercebidos: o `TIME_ZONE` do Django é
    `America/Chicago` (o aviso aparecia cinco horas antes do que aconteceu) e o
    formato padrão sai no locale `en-us` ("Aug. 24, 2026, 9 a.m."). O guarda
    mede as duas coisas juntas, comparando com o que o próprio Django converte
    para o fuso da Caixa — nunca com uma string escrita à mão, que envelheceria
    no dia seguinte.
    """
    from django.utils import timezone

    corpo = dentro.client.get(reverse("avisos")).content.decode()
    esperado = timezone.localtime(aviso.criado_em).strftime("%d/%m/%Y %H:%M")

    assert esperado in corpo, f"a data não saiu como {esperado}: {corpo[-1200:]}"


def test_a_lista_de_outra_pessoa_nao_mostra_o_meu_aviso(outra_pessoa, aviso):
    resposta = outra_pessoa.client.get(reverse("avisos"))
    corpo = resposta.content.decode()

    assert resposta.status_code == 200
    assert aviso.sugestao.titulo not in corpo, "a lista vazou o aviso de outra pessoa"
    assert aviso.nota not in corpo, "a lista vazou a nota escrita para outra pessoa"


# ---------------------------------------------------------------------------
# Contar
# ---------------------------------------------------------------------------


def ator_de(pessoa):
    """O `Ator` de uma sessão aberta — o mesmo objeto que a view recebe."""
    from apps.core.sessao import Ator, papel_de

    identidade = pessoa.identidade
    return Ator(identidade=identidade, papel=papel_de(identidade.email))


def test_a_contagem_de_nao_lidos_e_de_quem_esta_na_sessao(dentro, outra_pessoa, aviso):
    assert contar_nao_lidos(ator_de(dentro)) == 1
    assert contar_nao_lidos(ator_de(outra_pessoa)) == 0


def test_o_sino_de_toda_pagina_conta_so_os_meus(dentro, outra_pessoa, aviso):
    """A contagem do context processor, medida onde ela aparece: no quadro.

    O sino desenhado é do EVO-31; o que se prova aqui é o DADO — e que ele é por
    pessoa, que é o que impede o vazamento de virar um número inexplicável na
    tela de quem não tem aviso nenhum.
    """
    meu = dentro.client.get(reverse("quadro")).content.decode()
    dela = outra_pessoa.client.get(reverse("quadro")).content.decode()

    assert "avisos (1)" in " ".join(meu.split())
    assert "avisos (1)" not in " ".join(dela.split())


# ---------------------------------------------------------------------------
# Escrever
# ---------------------------------------------------------------------------


def test_marcar_como_lido_zera_a_contagem(dentro, aviso):
    resposta = dentro.client.post(reverse("marcar_aviso_lido", args=[aviso.id]))

    assert resposta.status_code == 302
    assert resposta["Location"] == reverse("avisos")
    aviso.refresh_from_db()
    assert aviso.lido_em is not None
    assert contar_nao_lidos(ator_de(dentro)) == 0


def test_marcar_duas_vezes_nao_mexe_no_carimbo_da_primeira(dentro, aviso):
    """[INVARIANTE 3] Idempotente: o instante da primeira leitura não se move.

    Sem a guarda, um duplo clique — ou o refresh de um POST — reescreveria o
    carimbo, e "quando eu vi isto" viraria "quando eu cliquei pela última vez".
    """
    dentro.client.post(reverse("marcar_aviso_lido", args=[aviso.id]))
    aviso.refresh_from_db()
    primeira = aviso.lido_em

    dentro.client.post(reverse("marcar_aviso_lido", args=[aviso.id]))
    aviso.refresh_from_db()

    assert aviso.lido_em == primeira
    assert Aviso.objects.count() == 1


def test_outra_pessoa_nao_marca_o_meu_aviso_e_nem_descobre_que_ele_existe(
    outra_pessoa, aviso
):
    resposta = outra_pessoa.client.post(reverse("marcar_aviso_lido", args=[aviso.id]))

    assert resposta.status_code == 404, (
        "o aviso de outra pessoa respondeu algo diferente de 404 — 403 já "
        "confirmaria que ele existe a quem chutou o número."
    )
    aviso.refresh_from_db()
    assert aviso.lido_em is None


# ---------------------------------------------------------------------------
# [INVARIANTE 4] Sem sessão, nada — nem a lista, nem a contagem, nem a marca
# ---------------------------------------------------------------------------


def test_anonimo_nao_le_a_lista_nem_marca_nada(client, aviso):
    lista = client.get(reverse("avisos"))
    marca = client.post(reverse("marcar_aviso_lido", args=[aviso.id]))

    assert lista.status_code == 302
    assert lista["Location"] == reverse("entrar")
    assert aviso.sugestao.titulo not in lista.content.decode()
    assert marca.status_code == 302
    aviso.refresh_from_db()
    assert aviso.lido_em is None


def test_as_duas_rotas_do_sininho_carregam_o_porteiro():
    """A varredura completa do urlconf é de `test_inv_sem_sessao_nada.py`; esta
    aqui é a asserção nominal, para que apagar o decorador de UMA delas apareça
    com o nome da rota no relatório de falha."""
    from config.urls import urlpatterns

    porteiros = {
        rota.name: getattr(rota.callback, "exige_sessao", False)
        for rota in urlpatterns
        # `URLPattern` só: desde a DECISAO-onde-mora-a-sessao o urlconf também
        # carrega uma montagem por `include()` (a superfície de máquina), e
        # `URLResolver` não tem `.name` nem `.callback`. Quem guarda a montagem
        # é `test_inv_sem_sessao_nada.py`, que a declara e prova o 401.
        if isinstance(rota, URLPattern) and rota.name in {"avisos", "marcar_aviso_lido"}
    }
    assert porteiros == {"avisos": True, "marcar_aviso_lido": True}
