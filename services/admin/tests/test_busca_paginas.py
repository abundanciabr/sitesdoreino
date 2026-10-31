import httpx
import pytest
import respx
from django.test import Client
from django.urls import get_script_prefix, reverse, set_script_prefix

from apps.core import busca_paginas as busca


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv('IDENTIDADE_API_URL', 'http://identidade:8000/interno')
    monkeypatch.setenv('IDENTIDADE_API_TOKEN', 'token-de-teste')
    settings.ADMIN_EMAILS = 'admin@exemplo.com'


def cliente():
    respx.get('http://identidade:8000/interno/sessao/completa').mock(
        return_value=httpx.Response(200, json={
            'autenticado': True, 'id': 'teste', 'nome_exibido': 'Admin',
            'email': 'admin@exemplo.com', 'papel': None,
        }))
    c = Client()
    c.defaults['HTTP_COOKIE'] = 'meshcraft_sessao=teste'
    return c


@respx.mock
def test_enter_e_botao_levam_a_resultados_proprios_sob_prefixo():
    anterior = get_script_prefix()
    set_script_prefix('/admin/')
    try:
        r = cliente().get('/busca/', {'q': 'escola'}, SCRIPT_NAME='/admin')
        assert r.status_code == 200
        html = r.content.decode()
        assert 'action="/admin/busca/"' in html
        assert 'data-sugestoes="/admin/busca/sugestoes/"' in html
        assert 'src="/admin/busca/script.js"' in html
        assert 'Resultados para “escola”' in html
        assert 'class="busca-resultado"' in html
        assert '<h1>O mapa do site</h1>' not in html
    finally:
        set_script_prefix(anterior)


@respx.mock
def test_sugestoes_sao_paginas_com_enderecos_clicaveis():
    r = cliente().get(reverse('busca_sugestoes'), {'q': 'forum'})
    assert r.status_code == 200
    dados = r.json()
    assert 0 < len(dados['resultados']) <= 7
    assert any(p['endereco'] == '/forum/' for p in dados['resultados'])
    assert all(set(p) == {'titulo', 'descricao', 'endereco'} for p in dados['resultados'])
    assert all('<' not in p['endereco'] for p in dados['resultados'])
    assert 'no-store' in r['Cache-Control']


def test_nomes_do_menu_tem_prioridade_e_acentos_nao_atrapalham():
    assert busca.pesquisar('escola')[0]['titulo'] == 'Escola'
    assert busca.pesquisar('FÓRUM') == busca.pesquisar('forum')
    assert busca.pesquisar('pagina venda')


def test_nao_oferece_acoes_apis_ou_moldes_como_paginas():
    paginas = busca.paginas()
    assert not any(p['endereco'].endswith('/decidir') for p in paginas)
    assert not any('/healthz' in p['endereco'] for p in paginas)
    assert not any('/api/' in p['endereco'] for p in paginas)
    assert not any('<' in p['endereco'] for p in paginas)


@respx.mock
def test_consulta_vazia_sem_resultados_e_texto_escapado():
    c = cliente()
    assert c.get(reverse('busca_sugestoes')).json()['resultados'] == []
    r = c.get(reverse('busca_paginas'), {'q': '<script>alert(1)</script>'})
    assert r.status_code == 200
    html = r.content.decode()
    assert 'Nenhuma página corresponde' in html
    assert '<script>alert(1)</script>' not in html
    assert '&lt;script&gt;' in html


@respx.mock
def test_falha_no_indice_nao_finge_resultado_vazio(monkeypatch):
    monkeypatch.setattr(busca.mapa_do_site, 'arquivo_do_mapa', lambda: None)
    c = cliente()
    assert c.get(reverse('busca_sugestoes'), {'q': 'escola'}).status_code == 503
    r = c.get(reverse('busca_paginas'), {'q': 'escola'})
    assert r.status_code == 503
    assert 'Não foi possível carregar' in r.content.decode()


@respx.mock
def test_paginacao_preserva_consulta(monkeypatch):
    monkeypatch.setattr(busca, 'pesquisar', lambda q: [
        {'titulo': f'Página {i}', 'descricao': 'Teste', 'endereco': f'/pagina-{i}/'}
        for i in range(25)])
    r = cliente().get(reverse('busca_paginas'), {'q': 'escola & cursos', 'pagina': 2})
    assert r.status_code == 200
    assert len(r.context['resultados']) == 5
    assert 'q=escola%20%26%20cursos&amp;pagina=1' in r.content.decode()


@respx.mock
@pytest.mark.parametrize('nome', ['busca_paginas', 'busca_sugestoes', 'busca_script'])
def test_busca_exige_administrador(nome):
    respx.get('http://identidade:8000/interno/sessao/completa').mock(
        return_value=httpx.Response(200, json={'autenticado': False}))
    r = Client().get(reverse(nome), {'q': 'escola'})
    assert r.status_code in (302, 404)


@respx.mock
def test_script_servido_sem_afrouxar_csp_e_busca_so_le():
    c = cliente()
    r = c.get(reverse('busca_script'))
    assert r.status_code == 200
    assert r['Content-Type'].startswith('text/javascript')
    assert 'unsafe-inline' not in r['Content-Security-Policy']
    assert c.post(reverse('busca_sugestoes')).status_code == 405


@pytest.mark.parametrize('url', ['//outro.site/', '/\\outro.site/', 'javascript:alert(1)', '/pagina/<id>', '/a\nb'])
def test_enderecos_perigosos_ou_incompletos_nao_viram_links(url):
    assert not busca._endereco_seguro(url)
