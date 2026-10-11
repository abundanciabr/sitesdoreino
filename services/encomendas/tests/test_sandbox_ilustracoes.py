import pytest
from django.urls import reverse
from apps.core import telas_sandbox, sessao
from apps.encomendas import catalogo_curso

@pytest.mark.django_db
@pytest.mark.parametrize('categoria', [chave for chave, *_ in catalogo_curso.CATEGORIAS])
def test_referencias_acompanham_categoria(client, monkeypatch, categoria):
    catalogo_curso.preparar_projetos(site_id='escola-imagens', ativar=True)
    monkeypatch.setattr(sessao, 'quem_e', lambda req: 'aluno')
    monkeypatch.setattr(sessao, 'site_desta_instalacao', lambda: 'escola-imagens')
    monkeypatch.setattr(telas_sandbox, '_aluno_atual', lambda *args: True)
    monkeypatch.setenv('IDS_DO_PLANTAO', 'equipe')
    r = client.get(reverse('sandbox_catalogo'), {'categoria': categoria})
    assert r.status_code == 200
    html = r.content.decode()
    projetos = r.context['projetos']
    assert {p.slug for p in projetos} == {p['slug'] for p in catalogo_curso.PROJETOS if p['categoria'] == categoria}
    assert html.count('class="reference-figure"') == len(projetos)
    for projeto in projetos:
        assert f'data-reference-project="{projeto.slug}"' in html
        arte = catalogo_curso.arte_projeto(projeto.slug)
        if arte:
            assert reverse('sandbox_ilustracao', args=[arte['arquivo']]) in html
        else:
            assert 'class="course-free"' in html
    for projeto in catalogo_curso.PROJETOS:
        if projeto['categoria'] != categoria:
            assert f'data-reference-project="{projeto["slug"]}"' not in html

@pytest.mark.django_db
def test_imagens_publicas_apenas_arquivos_ilustrativos(client):
    for slug in telas_sandbox.ILUSTRACOES:
        r = client.get(reverse('sandbox_ilustracao', args=[slug]))
        assert r.status_code == 200 and r['Content-Type'] == 'image/png'
        r.close()
    assert client.get(reverse('sandbox_ilustracao', args=['segredo'])).status_code == 404
