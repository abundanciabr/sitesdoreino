import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse
from apps.core import ganhos_previa as ganhos

SESSAO = 'http://identidade:8000/interno/sessao/completa'


@pytest.fixture(autouse=True)
def ambiente(monkeypatch, settings):
    monkeypatch.setenv('IDENTIDADE_API_URL', 'http://identidade:8000/interno')
    monkeypatch.setenv('IDENTIDADE_API_TOKEN', 'token-teste')
    settings.ADMIN_EMAILS = 'admin@example.invalid'
    monkeypatch.setattr(ganhos, 'site_de', lambda request: 'meshcraft')


def cliente(email='admin@example.invalid'):
    respx.get(SESSAO).mock(return_value=httpx.Response(200,json={
        'autenticado': True, 'id': 'teste', 'email':email,'nome_exibido':'Admin',
    }))
    c = Client(); c.defaults['HTTP_COOKIE'] = 'meshcraft_sessao=teste'
    return c


@respx.mock
def test_telas_e_print_fechados_para_aluno_e_anonimo(monkeypatch):
    def nao_consultar(*args, **kwargs): raise AssertionError('Nao consultar dados privados')
    monkeypatch.setattr(ganhos, '_consultar', nao_consultar)
    for nome, args in [('ganhos_previa',[]),('ganhos_previa_detalhe',[1]),('ganhos_previa_print',[1])]:
        url = reverse(nome,args=args)
        assert Client().get(url).status_code == 302
        assert cliente('aluno@example.invalid').get(url).status_code == 403


@respx.mock
def test_fonte_vazia_e_indisponivel_sao_diferentes(monkeypatch):
    monkeypatch.setattr(ganhos,'_consultar',lambda *a,**kw: None)
    assert 'fonte está indisponível' in cliente().get(reverse('ganhos_previa')).content.decode()
    monkeypatch.setattr(ganhos,'_consultar',lambda *a,**kw: {'itens': [],'total':0,'mais':False})
    r=cliente().get(reverse('ganhos_previa'))
    assert 'Ainda não há resultados' in r.content.decode()
    assert 'no-store' in r['Cache-Control']


@respx.mock
def test_valor_original_e_texto_escapado(monkeypatch):
    item=dict(id=1,nome='Ana',trabalho='<script>segredo</script>',valor_cents=50000,
              valor_original_cents=10000,moeda_original='USD',recebido_em='2026-10-12',revisao=1)
    monkeypatch.setattr(ganhos,'_consultar',lambda *a,**kw: {'itens':[item], 'item':item,'total':1,'mais':False})
    r=cliente().get(reverse('ganhos_previa')); texto=r.content.decode()
    assert 'USD 100,00' in texto and '<script>segredo' not in texto
    assert '<img' not in texto
    d=cliente().get(reverse('ganhos_previa_detalhe',args=[1]))
    assert 'não autentica o documento junto ao banco' in d.content.decode()


@respx.mock
def test_print_privado_e_periodo_invalido(monkeypatch):
    monkeypatch.setattr(ganhos,'_consultar',lambda *a,**kw: b'print-reservado')
    r=cliente().get(reverse('ganhos_previa_print',args=[1]))
    assert r.content == b'print-reservado' and 'no-store' in r['Cache-Control']
    assert r['Referrer-Policy'] == 'no-referrer'
    assert cliente().get(reverse('ganhos_previa'),{'de':'2026-99-99'}).status_code == 400


@respx.mock
def test_historico_excluido_aparece_na_lista_mas_nao_no_bloco(monkeypatch):
    item = dict(id=1, nome='Ana', trabalho='Modelo histórico', valor_cents=80000,
                moeda_original='BRL', recebido_em='2026-10-10', historico=True,
                estado_texto='Confirmado', elegivel=False, print_disponivel=False,
                motivos_exclusao=['Sem imagem do print armazenada.'])
    monkeypatch.setattr(ganhos, '_consultar', lambda *a, **kw: {
        'itens': [item], 'item': item, 'total': 1, 'mais': False})
    texto = cliente().get(reverse('ganhos_previa')).content.decode()
    assert 'Modelo histórico' in texto and 'Sem imagem do print armazenada.' in texto
    assert 'Modelo histórico' not in texto.split('<aside')[1]
    detalhe = cliente().get(reverse('ganhos_previa_detalhe', args=[1])).content.decode()
    assert 'Recebimento histórico' in detalhe and '<img' not in detalhe
    item.update(elegivel=True, print_disponivel=True, motivos_exclusao=[])
    texto = cliente().get(reverse('ganhos_previa')).content.decode()
    assert 'Modelo histórico' in texto.split('<aside')[1]
    detalhe = cliente().get(reverse('ganhos_previa_detalhe', args=[1])).content.decode()
    assert 'Ver imagem do print privado' in detalhe
