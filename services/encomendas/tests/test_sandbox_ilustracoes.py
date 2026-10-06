import pytest
from django.urls import reverse
from apps.core import telas_sandbox, sessao
from apps.encomendas import sandbox

@pytest.mark.django_db
@pytest.mark.parametrize('categoria', ['espadas_objetos', 'pets', 'cabelos', 'chapeus', 'personagens'])
def test_referencias_acompanham_categoria(client, monkeypatch, categoria):
    sandbox.semear_projetos(site_id='escola-imagens')
    monkeypatch.setattr(sessao, 'quem_e', lambda req: 'aluno')
    monkeypatch.setattr(sessao, 'site_desta_instalacao', lambda: 'escola-imagens')
    monkeypatch.setattr(telas_sandbox, '_aluno_atual', lambda *args: True)
    monkeypatch.setenv('IDS_DO_PLANTAO', 'equipe')
    r = client.get(reverse('sandbox_catalogo'), {'categoria': categoria})
    assert r.status_code == 200
    html = r.content.decode()
    projetos = r.context['projetos']
    assert html.count('class="project-illustration"') == len(projetos)
    assert html.count('class="reference-figure"') == len(projetos)
    for projeto in projetos:
        assert reverse('sandbox_ilustracao', args=[projeto.slug]) in html
    for slug, _, outra_categoria, *_ in sandbox._PROJETOS:
        if outra_categoria != categoria:
            assert reverse('sandbox_ilustracao', args=[slug]) not in html

@pytest.mark.django_db
def test_imagens_publicas_apenas_arquivos_ilustrativos(client):
    for slug in telas_sandbox.ILUSTRACOES:
        r = client.get(reverse('sandbox_ilustracao', args=[slug]))
        assert r.status_code == 200 and r['Content-Type'] == 'image/png'
        r.close()
    assert client.get(reverse('sandbox_ilustracao', args=['segredo'])).status_code == 404
