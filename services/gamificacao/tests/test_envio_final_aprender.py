"""O envio final compara o par escolhido ou a imagem do começo da jornada."""
import hashlib
import io

import pytest
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.gamificacao.bonus_faixas import configurar
from apps.gamificacao.jornada import registrar_avaliacao, situacao
from apps.gamificacao.models import AnexoDaJornada, JornadaPessoal, LancamentoDeXP

pytestmark = pytest.mark.django_db
P, SITE = 'teste-par-final', 'teste-par-final-site'
URL = '/trilha/inventario/api/'


def imagem(cor):
    corpo = io.BytesIO()
    Image.new('RGB', (64, 64), cor).save(corpo, format='PNG')
    return corpo.getvalue()


def guardar(cor, passo=2, pessoa=P, site=SITE):
    corpo = imagem(cor)
    return AnexoDaJornada.objects.create(pessoa_id=pessoa, site_id=site, passo=passo,
        nome='espada.png', conteudo=corpo, tamanho=len(corpo), sha256=hashlib.sha256(corpo).hexdigest())


def enviar(client, **arquivos):
    return client.post(URL, {'acao': 'ciclo-avaliar', 'ordem': 7,
        'revisao': situacao(P, SITE)['revisao'], 'item_nome': 'Espada Aurora',
        'explicacao': 'Mudei a cor dos detalhes.',
        **{campo: SimpleUploadedFile(campo + '.png', corpo, content_type='image/png')
           for campo, corpo in arquivos.items()}}, HTTP_COOKIE='meshcraft_sessao=teste')


@pytest.fixture(autouse=True)
def jornada(monkeypatch):
    monkeypatch.setenv('SITE_ID', SITE)
    monkeypatch.setattr('apps.core.inventario._sessao', lambda _: {'autenticado': True, 'id': P})
    configurar(SITE)
    JornadaPessoal.objects.create(pessoa_id=P, site_id=SITE,
        inicio={'motivo': 'aprender', 'item_nome': 'Espada Aurora'})
    for ordem in range(2, 7):
        registrar_avaliacao(P, SITE, ordem, 'reconhecida', 'Etapa anterior conferida.', {'chave': str(ordem)})


@pytest.fixture
def pares(monkeypatch):
    pares = []

    def avaliar(pessoa, site, ordem, dados, anexos):
        par = [next(a for a in anexos if a.id == dados[chave])
               for chave in ('anexo_anterior_id', 'anexo_final_id')]
        pares.append(par)
        return {'resultado': 'reconhecida', 'feedback': 'Par examinado no teste.', 'evidencia': {}}

    monkeypatch.setattr('apps.gamificacao.avaliacao_inicio.avaliar', avaliar)
    return pares


def test_par_explicito_tem_prioridade_e_reenvio_nao_duplica_bonus(client, pares):
    guardar('green')
    guardar('red', passo=6)
    for _ in range(2):
        resposta = enviar(client, arquivo_anterior=imagem('blue'), arquivo=imagem('red'))
        assert resposta.status_code == 200
        assert resposta.json()['atual_ordem'] == 7
        assert [a.sha256 for a in pares[-1]] == [hashlib.sha256(imagem(c)).hexdigest() for c in ('blue', 'red')]
    assert sum(LancamentoDeXP.objects.filter(pessoa_id=P, site_id=SITE).values_list('pontos', flat=True)) == 105000


def test_so_final_usa_primeira_imagem_do_comeco_e_respeita_conta_e_site(client, pares):
    guardar('yellow', pessoa='outra-pessoa')
    guardar('yellow', site='outro-site')
    inicial = guardar('blue')
    guardar('green')
    guardar('red', passo=6)
    assert enviar(client, arquivo=imagem('red')).status_code == 200
    assert pares[-1][0].id == inicial.id
    assert pares[-1][1].passo == 7


@pytest.mark.parametrize('explicito', [True, False])
def test_imagens_iguais_continuam_incompletas_sem_bonus(client, explicito):
    guardar('red')
    arquivos = {'arquivo': imagem('red')}
    if explicito:
        arquivos['arquivo_anterior'] = imagem('red')
    resposta = enviar(client, **arquivos)
    assert resposta.status_code == 200
    assert resposta.json()['avaliacao_atual']['resultado'] == 'incompleta'
    assert situacao(P, SITE)['atual']['ordem'] == 6
    assert not LancamentoDeXP.objects.filter(pessoa_id=P, site_id=SITE, regra_slug='bonus-faixa-preta').exists()


def test_apenas_imagem_anterior_nao_e_tratada_como_final(client):
    antes = JornadaPessoal.objects.get(pessoa_id=P, site_id=SITE).revisao
    resposta = enviar(client, arquivo_anterior=imagem('blue'))
    assert resposta.status_code == 400
    assert not AnexoDaJornada.objects.exists()
    assert JornadaPessoal.objects.get(pessoa_id=P, site_id=SITE).revisao == antes


def test_imagem_de_outra_pessoa_ou_marrom_nao_substitui_inicio_ausente(client):
    guardar('blue', pessoa='outra-pessoa')
    guardar('blue', site='outro-site')
    guardar('green', passo=6)
    resposta = enviar(client, arquivo=imagem('red'))
    assert resposta.status_code == 200
    assert resposta.json()['avaliacao_atual']['resultado'] == 'incompleta'
    assert situacao(P, SITE)['atual']['ordem'] == 6
