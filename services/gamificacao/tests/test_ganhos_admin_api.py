import hashlib
from datetime import date
from types import SimpleNamespace

import pytest
from django.http import HttpResponse
from ninja.errors import HttpError

from apps.core import ganhos_admin_api as ganhos
from apps.gamificacao.models import Pessoa, RecebimentoDeclarado

pytestmark = pytest.mark.django_db


@pytest.fixture
def ambiente(monkeypatch):
    monkeypatch.setenv('TOKENS_ACEITOS_ADMIN', 'somente-admin')
    monkeypatch.setattr(ganhos, 'site_atual', lambda: 'meshcraft')
    return SimpleNamespace(auth='somente-admin')


def criar(**campos):
    pessoa, _ = Pessoa.objects.get_or_create(id_da_plataforma='pessoa', defaults={
        'email': 'privado@example.invalid', 'nome_exibido': 'Maria Silva',
    })
    defaults = dict(pessoa=pessoa, site_id='meshcraft', valor_cents=80000,
                    valor_original_cents=80000, moeda_original='BRL', origem='proprio',
                    referencia_trabalho='Modelo 3D', estado='confirmado',
                    print_bytes=b'print-reservado', print_sha256=hashlib.sha256(b'print-reservado').hexdigest(),
                    recebido_em=date(2026,10,12), leitura={'status': 'recebido', 'segredo': 'nao-projetar'})
    defaults.update(campos)
    return RecebimentoDeclarado.objects.create(**defaults)


def test_somente_token_admin_e_site_correto(ambiente):
    criar()
    for request, site in [(SimpleNamespace(auth='outro-token'), 'meshcraft'), (ambiente, 'outro-site')]:
        with pytest.raises(HttpError):
            ganhos.listar(request, HttpResponse(), site)


def test_sem_configuracao_nao_abre(ambiente, monkeypatch):
    monkeypatch.delenv('TOKENS_ACEITOS_ADMIN')
    with pytest.raises(HttpError):
        ganhos.imagem(ambiente, 'meshcraft', 1)


def test_lista_preserva_privacidade_e_nao_muda_registros(ambiente):
    r = criar()
    criar(estado='pendente'); criar(estado='anulado'); criar(fora_da_progressao=True)
    criar(site_id='outro'); criar(print_bytes=None); criar(print_sha256='')
    response = HttpResponse()
    resultado = ganhos.listar(ambiente, response, 'meshcraft')
    assert resultado['total'] == 1 and resultado['itens'][0]['id'] == r.pk
    assert resultado['itens'][0]['nome'] == 'Maria'
    assert 'privado@example' not in str(resultado)
    assert 'print-reservado' not in str(resultado) and 'nao-projetar' not in str(resultado)
    assert response['Cache-Control'] == 'private, no-store'
    assert RecebimentoDeclarado.objects.count() == 7


def test_periodo_e_paginacao(ambiente):
    for _ in range(13): criar()
    assert len(ganhos.listar(ambiente,HttpResponse(),'meshcraft')['itens']) == 12
    assert len(ganhos.listar(ambiente,HttpResponse(),'meshcraft',pagina=2)['itens']) == 1
    assert ganhos.listar(ambiente,HttpResponse(),'meshcraft',de='2026-10-13')['total'] == 0
    for campos in ({'de':'2026-99-01'}, {'de':'2026-11-01','ate':'2026-10-01'}, {'pagina':0}):
        with pytest.raises(HttpError): ganhos.listar(ambiente,HttpResponse(),'meshcraft',**campos)


def test_print_confere_hash_e_recusa_outro_site(ambiente):
    r = criar()
    response = ganhos.imagem(ambiente,'meshcraft',r.pk)
    assert response.content == b'print-reservado'
    assert response['Cache-Control'] == 'private, no-store'
    r.print_sha256 = 'hash-incorreto'; r.save(update_fields=['print_sha256'])
    with pytest.raises(HttpError): ganhos.imagem(ambiente,'meshcraft',r.pk)
    outro = criar(site_id='outro')
    with pytest.raises(HttpError): ganhos.imagem(ambiente,'meshcraft',outro.pk)


def test_rotas_da_api_exigem_par_admin(client, settings, ambiente):
    settings.TOKENS_ACEITOS = {'somente-admin', 'par-forum'}
    r = criar()
    for caminho in ('/api/gamificacao/ganhos-admin/meshcraft',
                    f'/api/gamificacao/ganhos-admin/meshcraft/{r.pk}',
                    f'/api/gamificacao/ganhos-admin/meshcraft/{r.pk}/print'):
        assert client.get(caminho).status_code == 401
        assert client.get(caminho, HTTP_AUTHORIZATION='Bearer par-forum').status_code == 403
        assert client.get(caminho, HTTP_AUTHORIZATION='Bearer somente-admin').status_code == 200
