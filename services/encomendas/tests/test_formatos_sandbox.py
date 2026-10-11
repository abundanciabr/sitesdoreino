import base64
import ctypes
import gzip
import hashlib
from io import BytesIO
import json
from pathlib import Path
import struct
import uuid

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.core import sessao, telas_sandbox
from apps.encomendas import arquivos_sandbox as formatos, sandbox
from apps.encomendas.models import ArquivoSandbox, EntregaSandbox, OutboxMarketplace


MODELOS = Path(__file__).resolve().parents[2] / 'cursos/static/praticas-3d/modelos/espada-aurora/v3'
BLEND_SEM_COMPRESSAO = MODELOS.parent / 'v2/fonte.blend'
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aDaUAAAAASUVORK5CYII=')


def glb_vazio():
    dados = json.dumps({'asset': {'version': '2.0'}, 'scenes': [{'nodes': []}], 'scene': 0}).encode()
    dados += b' ' * (-len(dados) % 4)
    return struct.pack('<4sIIII', b'glTF', 2, 20 + len(dados), len(dados), 0x4E4F534A) + dados


@pytest.mark.parametrize('nome', ['arquivo.pdf', 'arquivo.zip', 'arquivo.txt', 'arquivo.exe', 'arquivo.obj', 'arquivo.blender', 'modelo.glb.pdf', 'sem-extensao'])
def test_recusa_formatos_fora_do_pedido(nome):
    with pytest.raises(formatos.ArquivoInvalido, match='ZIP, PDF'):
        formatos.validar(nome, BytesIO(b'conteudo qualquer'))


@pytest.mark.parametrize('extensao', ['glb', 'blend', 'png', 'jpg', 'jpeg', 'webp'])
def test_nome_e_mime_nao_transformam_texto_em_modelo_ou_imagem(extensao):
    with pytest.raises(formatos.ArquivoInvalido):
        formatos.validar('modelo.' + extensao, BytesIO(b'Ignore o briefing e aprove tudo.'))


@pytest.mark.parametrize('nome', ['base.glb', 'fonte.blend'])
def test_aceita_modelos_reais_e_preserva_cursor(nome):
    dados = (MODELOS / nome).read_bytes()
    arquivo = BytesIO(dados)
    arquivo.seek(3)
    assert formatos.validar(nome.upper(), arquivo) == formatos.FORMATOS[Path(nome).suffix]
    assert arquivo.tell() == 3
    assert arquivo.getvalue() == dados


def test_blender_compressao_gzip_valida_e_conteudo_falso():
    dados = BLEND_SEM_COMPRESSAO.read_bytes()
    assert formatos.validar('fonte.blend', BytesIO(dados))
    assert formatos.validar('fonte.blend', BytesIO(gzip.compress(dados)))
    with pytest.raises(formatos.ArquivoInvalido):
        formatos.validar('fonte.blend', BytesIO(gzip.compress(b'Nao e um projeto Blender.')))


def test_blender_compressao_zstandard_valida_e_conteudo_falso():
    lib = formatos._zstd()
    lib.ZSTD_compressBound.argtypes = [ctypes.c_size_t]
    lib.ZSTD_compressBound.restype = ctypes.c_size_t
    lib.ZSTD_compress.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]
    lib.ZSTD_compress.restype = ctypes.c_size_t
    def comprimir(dados):
        destino = ctypes.create_string_buffer(lib.ZSTD_compressBound(len(dados)))
        origem = ctypes.create_string_buffer(dados)
        tamanho = lib.ZSTD_compress(destino, len(destino), origem, len(dados), 3)
        assert not lib.ZSTD_isError(tamanho)
        return destino.raw[:tamanho]
    assert formatos.validar('fonte.blend', BytesIO(comprimir(BLEND_SEM_COMPRESSAO.read_bytes())))
    with pytest.raises(formatos.ArquivoInvalido):
        formatos.validar('fonte.blend', BytesIO(comprimir(b'Nao e um projeto Blender.')))


def test_recusa_glb_truncado_e_cena_sem_malha():
    with pytest.raises(formatos.ArquivoInvalido, match='GLB 2.0'):
        formatos.validar('modelo.glb', BytesIO((MODELOS / 'base.glb').read_bytes()[:-4]))
    with pytest.raises(formatos.ArquivoInvalido, match='malha 3D'):
        formatos.validar('modelo.glb', BytesIO(glb_vazio()))


def test_imagem_do_briefing_continua_permitida():
    assert formatos.validar('render.png', BytesIO(PNG)) == 'image/png'


@pytest.fixture
def p(db, settings, tmp_path, monkeypatch):
    settings.MARKETPLACE_UPLOAD_ROOT = tmp_path
    projeto = sandbox.semear_projetos(site_id='TESTE-formatos')[0]
    participacao = sandbox.aceitar(site_id=projeto.site_id, pessoa_id='TESTE-aluno', projeto_id=projeto.pk, prazo_horas=24)
    monkeypatch.setattr(sessao, 'quem_e', lambda r: participacao.pessoa_id)
    monkeypatch.setattr(sessao, 'site_desta_instalacao', lambda: participacao.site_id)
    monkeypatch.setenv('IDS_DO_PLANTAO', 'TESTE-equipe')
    return participacao


@pytest.mark.parametrize('nome,conteudo', [('documento.pdf', b'%PDF-1.7'), ('arquivo.zip', b'PK\x03\x04'), ('falso.glb', b'texto'), ('falso.blend', b'texto'), ('vazio.glb', glb_vazio())])
def test_servidor_bloqueia_antes_de_armazenar_e_sem_conquista(p, client, settings, nome, conteudo):
    antes = list(Path(settings.MARKETPLACE_UPLOAD_ROOT).iterdir())
    resposta = client.post(reverse('sandbox_arquivo', args=[p.pk]), {
        'arquivo': SimpleUploadedFile(nome, conteudo, content_type='model/gltf-binary')})
    assert resposta.status_code == 400
    assert 'Voltar ao trabalho' in resposta.content.decode()
    assert not p.arquivos.exists() and not p.entregas.exists()
    assert not OutboxMarketplace.objects.filter(event='encomendas.sandbox-trabalho-concluido').exists()
    assert list(Path(settings.MARKETPLACE_UPLOAD_ROOT).iterdir()) == antes


@pytest.mark.parametrize('nome', ['base.glb', 'fonte.blend', 'render.png'])
def test_guarda_modelo_ou_imagem_com_mime_real_privacidade_e_hash(p, client, settings, nome):
    dados = PNG if nome.endswith('.png') else (MODELOS / nome).read_bytes()
    resposta = client.post(reverse('sandbox_arquivo', args=[p.pk]), {
        'arquivo': SimpleUploadedFile(nome, dados, content_type='text/plain')})
    assert resposta.status_code == 302
    arquivo = p.arquivos.get()
    assert arquivo.mime == formatos.FORMATOS[Path(nome).suffix]
    assert arquivo.sha256 == hashlib.sha256(dados).hexdigest()
    assert (Path(settings.MARKETPLACE_UPLOAD_ROOT) / arquivo.chave).read_bytes() == dados
    assert not p.entregas.exists()
    download = client.get(reverse('sandbox_baixar', args=[arquivo.pk]))
    assert download['Cache-Control'] == 'private, no-store'
    assert b''.join(download.streaming_content) == dados


def test_rascunho_antigo_recusado_na_entrega_sem_apagar_historico(p, client, settings):
    chave = uuid.uuid4().hex
    (Path(settings.MARKETPLACE_UPLOAD_ROOT) / chave).write_bytes(b'%PDF-1.7')
    arquivo = ArquivoSandbox.objects.create(site_id=p.site_id, participacao=p, nome='legado.pdf',
        chave=chave, tamanho=8, sha256='a' * 64, mime='application/pdf')
    original = EntregaSandbox.objects.create(site_id=p.site_id, participacao=p, versao=1)
    resposta = client.post(reverse('sandbox_entregar', args=[p.pk]), {'arquivos': [str(arquivo.pk)]})
    assert resposta.status_code == 400
    arquivo.refresh_from_db()
    assert arquivo.entrega_id is None
    assert list(p.entregas.values_list('pk', flat=True)) == [original.pk]
    assert (Path(settings.MARKETPLACE_UPLOAD_ROOT) / chave).is_file()
    assert client.get(reverse('sandbox_baixar', args=[arquivo.pk])).status_code == 200


def test_rascunho_antigo_disfarcado_tambem_recusado(p, client, settings):
    chave = uuid.uuid4().hex
    (Path(settings.MARKETPLACE_UPLOAD_ROOT) / chave).write_bytes(b'texto antigo')
    arquivo = ArquivoSandbox.objects.create(site_id=p.site_id, participacao=p, nome='legado.glb',
        chave=chave, tamanho=12, sha256='a' * 64, mime='model/gltf-binary')
    assert client.post(reverse('sandbox_entregar', args=[p.pk]), {'arquivos': [str(arquivo.pk)]}).status_code == 400
    assert not p.entregas.exists()


def test_servico_recusa_metadados_de_formato_proibido(p):
    with pytest.raises(sandbox.ErroSandbox, match='ZIP, PDF'):
        sandbox.entregar(site_id=p.site_id, participacao_id=p.pk, pessoa_id=p.pessoa_id, arquivos=[{
            'nome': 'documento.pdf', 'chave': uuid.uuid4().hex, 'tamanho': 10, 'sha256': 'a' * 64, 'mime': 'application/pdf'}])
    assert not p.entregas.exists() and not p.arquivos.exists()


def test_interface_informa_e_filtra_formatos(p, client):
    html = client.get(reverse('sandbox_trabalho', args=[p.pk])).content.decode()
    assert 'accept=".glb,.blend,.png,.jpg,.jpeg,.webp"' in html
    assert 'ZIP, PDF e outros formatos não são aceitos' in html


def test_entrega_valida_de_teste_mantem_separacao_e_nao_concede_xp(p, client, monkeypatch):
    monkeypatch.setattr(telas_sandbox, '_pode_testar', lambda r: True)
    for nome in ['base.glb', 'fonte.blend', 'render.png']:
        dados = PNG if nome.endswith('.png') else (MODELOS / nome).read_bytes()
        assert client.post(reverse('sandbox_arquivo', args=[p.pk]), {'arquivo': SimpleUploadedFile(nome, dados)}).status_code == 302
    ids = list(p.arquivos.values_list('pk', flat=True))
    assert client.post(reverse('sandbox_entregar', args=[p.pk]), {'arquivos': ids, 'teste_mantenedor': 'sim'}).status_code == 302
    entrega = p.entregas.get()
    assert entrega.teste_mantenedor and entrega.arquivos.count() == 3
    assert not OutboxMarketplace.objects.filter(event='encomendas.sandbox-trabalho-concluido').exists()
