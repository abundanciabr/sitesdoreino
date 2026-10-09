import pytest

from apps.links import servico
from apps.links.models import Destino, LinkIndividual


@pytest.mark.django_db
def test_link_de_recuperacao_nao_entra_em_relatorio_de_destinos():
    texto = 'Recupere em https://meshcraft.top/entrar/recuperar/#segredo-de-teste'
    corpo, links = servico.reescrever(texto, site_id='site-teste', origem='conversa', referencia='teste-privado')
    assert corpo == texto
    assert links == []
    assert not Destino.objects.exists()
    assert not LinkIndividual.objects.exists()


@pytest.mark.django_db
def test_link_comum_continua_individual_e_repeticao_reusa_a_mesma_intencao():
    texto = 'Conheça https://meshcraft.top/cursos/'
    argumentos = dict(site_id='site-teste', origem='conversa', referencia='teste-publico')
    primeiro, links = servico.reescrever(texto, **argumentos)
    segundo, repetidos = servico.reescrever(texto, **argumentos)
    assert primeiro == segundo
    assert links[0].id == repetidos[0].id
    assert LinkIndividual.objects.count() == 1
