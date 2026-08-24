# tests/test_inv_voto_pelo_endpoint.py  # [RECEITA:R5 v1]
"""INV-SUG01, a metade HTTP — o que o banco já recusa, a API não pode estourar.

`test_inv_voto_unico_por_ator.py` (EVO-11) prova o invariante no BANCO: a
segunda linha do mesmo par levanta `IntegrityError`, e desvotar apaga a linha.
Isso continua verdade — e é justamente por isso que este arquivo existe.

Uma `unique` que o endpoint não trata vira **500 na cara da pessoa** no clique
duplo mais banal do mundo (spec §9: "corrida entre dois cliques de votar do
mesmo ator"). O invariante inteiro tem duas metades:

1. o banco garante que existe **no máximo uma linha** (EVO-11);
2. o endpoint garante que a segunda tentativa é um **não-evento** — mesma
   contagem, resposta normal, nenhum rastro de erro (aqui).

E a terceira asserção, a que o despacho chamou de invariante 3: **desvotar
apaga a linha**. Não "marca inativa", não "zera um contador": depois de
desvotar, `Voto.objects.filter(...)` não acha NADA. A diferença aparece no dia
em que alguém contar votos sem lembrar do filtro.
"""

import pytest
from django.urls import reverse

from apps.sugestoes.models import Voto

pytestmark = pytest.mark.django_db


def _votar(cliente, sugestao, **extra):
    return cliente.post(reverse("votar", args=[sugestao.id]), extra)


def _desvotar(cliente, sugestao, **extra):
    return cliente.post(reverse("desvotar", args=[sugestao.id]), extra)


def test_votar_duas_vezes_nao_devolve_500_e_nao_duplica(dentro, sugestao):
    primeira = _votar(dentro.client, sugestao)
    segunda = _votar(dentro.client, sugestao)

    assert primeira.status_code == 302, primeira.content
    assert segunda.status_code == 302, segunda.content
    assert Voto.objects.filter(sugestao=sugestao, autor=dentro.identidade).count() == 1


def test_dez_cliques_no_botao_de_votar_continuam_valendo_um_voto(dentro, sugestao):
    """O clique nervoso é o caso comum, não o exótico."""
    for _ in range(10):
        assert _votar(dentro.client, sugestao).status_code == 302

    assert Voto.objects.filter(sugestao=sugestao).count() == 1


def test_desvotar_apaga_a_linha_e_nao_marca_nada(dentro, sugestao):
    _votar(dentro.client, sugestao)
    assert Voto.objects.filter(sugestao=sugestao, autor=dentro.identidade).exists()

    resposta = _desvotar(dentro.client, sugestao)

    assert resposta.status_code == 302, resposta.content
    # Sem filtro nenhum: a linha não existe mais em lugar algum da tabela.
    assert Voto.objects.filter(sugestao=sugestao, autor=dentro.identidade).count() == 0
    assert Voto.objects.count() == 0


def test_desvotar_duas_vezes_tambem_nao_estoura(dentro, sugestao):
    _votar(dentro.client, sugestao)
    _desvotar(dentro.client, sugestao)

    resposta = _desvotar(dentro.client, sugestao)

    assert resposta.status_code == 302, resposta.content
    assert Voto.objects.count() == 0


def test_desvotar_sem_nunca_ter_votado_nao_estoura(dentro, sugestao):
    resposta = _desvotar(dentro.client, sugestao)

    assert resposta.status_code == 302, resposta.content
    assert Voto.objects.count() == 0


def test_votar_de_novo_depois_de_desvotar_funciona(dentro, sugestao):
    _votar(dentro.client, sugestao)
    _desvotar(dentro.client, sugestao)
    _votar(dentro.client, sugestao)

    assert Voto.objects.filter(sugestao=sugestao, autor=dentro.identidade).count() == 1


def test_o_voto_e_do_ator_da_sessao_e_de_mais_ninguem(entrar_como, sugestao):
    """Dois alunos, dois votos — e desvotar de um não derruba o do outro."""
    joao = entrar_como("joao@exemplo.test", "João")
    maria = entrar_como("maria@exemplo.test", "Maria")

    _votar(joao.client, sugestao)
    _votar(maria.client, sugestao)
    assert Voto.objects.filter(sugestao=sugestao).count() == 2

    _desvotar(joao.client, sugestao)

    restantes = list(Voto.objects.filter(sugestao=sugestao))
    assert [voto.autor_id for voto in restantes] == [maria.identidade.id]


def test_o_botao_do_quadro_volta_para_o_quadro(dentro, sugestao):
    """`de=quadro` é a ÚNICA coisa que o formulário decide sobre o destino.

    O par de destinos é fixo no código (`_de_volta`). Um campo com a URL
    dentro seria redirecionamento aberto: a Caixa mandando a pessoa para onde
    o atacante escrevesse.
    """
    do_quadro = _votar(dentro.client, sugestao, de="quadro")
    da_pagina = _desvotar(dentro.client, sugestao)

    assert do_quadro["Location"] == reverse("quadro")
    assert da_pagina["Location"] == reverse("sugestao", args=[sugestao.id])


def test_um_destino_inventado_no_formulario_e_ignorado(dentro, sugestao):
    resposta = _votar(dentro.client, sugestao, de="https://site-do-atacante.test")

    assert resposta["Location"] == reverse("sugestao", args=[sugestao.id])
