"""Mesmos bytes reaproveitam; alterações e histórico inválido voltam ao ensaio."""
import json
from pathlib import Path
import shutil
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import ensaio_entregas as e
import protecao_publicacao as p
from testes_ensaio_entregas import A, B, _tar_imagem, _imagem_de_teste


@pytest.fixture
def contexto(tmp_path, monkeypatch):
    base = tmp_path / 'ensaios/saida' / A
    codigo = base / 'codigo'
    codigo.mkdir(parents=True)
    (codigo / 'programa.py').write_text('valor = 1')
    (codigo / 'Dockerfile').write_text('FROM imagem-aprovada')
    xml = base / 'evidencias/comercial.xml'
    xml.parent.mkdir()
    casos = {f'test_executado_{n}' for n in range(30)}
    xml.write_text('<testsuite>' + ''.join(f'<testcase name="{n}"/>' for n in sorted(casos)) + '</testsuite>')
    tar = base / 'imagem.tar'
    membros, imagem = _imagem_de_teste('docker')
    _tar_imagem(tar, membros)
    monkeypatch.setattr(p, 'casos_esperados', lambda: casos)
    monkeypatch.setattr(e, '_ferramentas', lambda *_: ('executor', 'ensaio'))
    monkeypatch.setattr(e, '_configuracao', lambda *_: 'config')
    monkeypatch.setattr(e, '_git', lambda *_: 'arvore-git')
    pacote = {'codigo_sha256': p.arvore(codigo), 'imagem_id': imagem, 'configuracao_sha256': 'config'}
    import hashlib
    pacote['id'] = hashlib.sha256(json.dumps(pacote, sort_keys=True).encode()).hexdigest()
    identidade = {'candidata': A, 'celula': 'aplicacao', 'codigo_git': 'arvore-git',
                  'codigo': p.arvore(codigo), 'imagem': imagem, 'imagem_tar_sha256': e._hash(tar),
                  'configuracao': 'config', 'configuracao_base': 'config',
                  'executor': 'executor', 'ensaio': 'ensaio', 'pacote_publicador': pacote,
                  'artefato': {'codigo': str(codigo), 'imagem_tar': str(tar), 'comercial_xml': str(xml)},
                  'relatorios': {'comercial_xml': e._hash(xml)}}
    prova = {'versao': 2, **identidade, 'identidade': e._json_hash(identidade),
             'resultado': 'aprovado', 'cobertura': p.conferir_relatorio(xml, registrar_falha_conhecida=True)}
    arquivo = tmp_path / 'entregas/provas' / (A + '.json')
    arquivo.parent.mkdir(parents=True)
    arquivo.write_text(json.dumps(prova))
    destino = tmp_path / 'novo/codigo'
    shutil.copytree(codigo, destino)
    return tmp_path, destino, imagem, arquivo, prova


def reaproveitar(contexto):
    raiz, bundle, imagem, _, _ = contexto
    return e.reaproveitar_ensaio(raiz, B, raiz, imagem, bundle, bundle.parent / 'evidencias')


def test_outra_entrega_mesmos_bytes_com_prova_historica_real(contexto):
    raiz, bundle, _, _, prova = contexto
    resultado = reaproveitar(contexto)
    assert resultado['candidata'] == A and resultado['tipo'] == 'entre_entregas'
    copia = bundle.parent / 'evidencias/comercial.xml'
    original = Path(prova['artefato']['comercial_xml'])
    assert copia.read_bytes() == original.read_bytes()
    copia.write_text('alterado apenas na copia')
    assert 'test_executado' in original.read_text()


@pytest.mark.parametrize('campo', ['imagem', 'configuracao_base', 'executor', 'ensaio', 'codigo'])
def test_insumo_diferente_exige_ensaio(contexto, campo):
    _, bundle, _, arquivo, prova = contexto
    prova[campo] = 'mudou'
    arquivo.write_text(json.dumps(prova))
    assert reaproveitar(contexto) is None
    assert not (bundle.parent / 'evidencias').exists()


@pytest.mark.parametrize('alvo', ['codigo', 'imagem_tar', 'comercial_xml'])
def test_bytes_historicos_corrompidos_nao_impedem_ensaio_novo(contexto, alvo):
    _, _, _, _, prova = contexto
    caminho = Path(prova['artefato'][alvo])
    if caminho.is_dir():
        caminho /= 'programa.py'
    caminho.write_text('corrompido')
    assert reaproveitar(contexto) is None


@pytest.mark.parametrize('conteudo', ['{incompleto', '[]', '{"celula":"outra"}'])
def test_indice_antigo_ilegivel_apenas_deixa_de_reaproveitar(contexto, conteudo):
    contexto[3].write_text(conteudo)
    assert reaproveitar(contexto) is None


def test_codigo_da_nova_entrega_diferente_exige_ensaio(contexto):
    (contexto[1] / 'programa.py').write_text('valor = 2')
    assert reaproveitar(contexto) is None


def test_imagem_de_apoio_diferente_muda_identidade(tmp_path, monkeypatch):
    (tmp_path / 'infra').mkdir()
    for nome in ['infra/protecao_publicacao.py', 'preparar-aplicacao.py', 'infra/execucao-celulas.py']:
        (tmp_path / nome).write_text('fixo')
    imagens = {'postgres:17': 'postgres-original', 'redis:7': 'redis-original'}
    monkeypatch.setattr(p, 'imagem_id', imagens.__getitem__)
    antes = e._ferramentas(tmp_path)
    imagens['postgres:17'] = 'postgres-diferente'
    assert e._ferramentas(tmp_path) != antes


@pytest.mark.parametrize('alterar_codigo', [False, True])
def test_executor_reaproveita_ou_ensaia_e_sempre_faz_backup(contexto, monkeypatch, alterar_codigo):
    from types import SimpleNamespace
    import armazenamento_codigo as armazenamento
    raiz, bundle, imagem, _, prova = contexto
    fonte = raiz / 'ensaios/entrada' / B / 'fonte'
    shutil.copytree(bundle, fonte / 'services/aplicacao')
    (fonte / 'documentos').mkdir()
    if alterar_codigo:
        (fonte / 'services/aplicacao/programa.py').write_text('valor = 2')
    (fonte.parent / '.origem-ensaio.json').write_text(json.dumps({
        'candidata': B, 'imagem_base': imagem, 'arvore': p.arvore(fonte)}))
    chamadas = []
    def ensaiar(_bundle, _imagem, _ferramentas, evidencias, _registro):
        chamadas.append('ensaio')
        evidencias.mkdir(parents=True, exist_ok=True)
        shutil.copy2(prova['artefato']['comercial_xml'], evidencias / 'comercial.xml')
        return prova['cobertura']
    monkeypatch.setattr(e, '_conferir_lancador', lambda: None)
    monkeypatch.setattr(p, 'montar', lambda *_: None)
    monkeypatch.setattr(p, 'ensaiar', ensaiar)
    monkeypatch.setattr(p, 'imagem_id', lambda _: imagem)
    monkeypatch.setattr(e.subprocess, 'run', lambda *_a, **_k: SimpleNamespace(returncode=0))
    monkeypatch.setattr(e, 'identidade_atual', lambda *_: {'configuracao_base': 'config', 'imagem': imagem})
    monkeypatch.setattr(armazenamento, 'image_archive', lambda *_: {'reused': True})
    monkeypatch.setattr(armazenamento, 'snapshot', lambda *_: chamadas.append('backup'))
    resultado = e.executar(raiz, B, raiz)
    assert chamadas == (['ensaio', 'backup'] if alterar_codigo else ['backup'])
    assert bool(resultado['reaproveitamento']) is not alterar_codigo
    assert ('testes_comerciais' in resultado['tempos']) is alterar_codigo
