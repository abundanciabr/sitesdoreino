"""Reuso conserva identidade, isolamento das cópias e conferência por célula."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import ensaio_entregas as e
import protecao_publicacao as p
import armazenamento_codigo as armazenamento
from testes_integrador_servico import servico, entrega, I1, C1, PonteFalsa


def origem(tmp_path, monkeypatch):
    codigo = tmp_path / 'origem/codigo'
    codigo.mkdir(parents=True)
    (codigo / 'programa.py').write_text('valor = 1')
    xml = codigo.parent / 'comercial.xml'
    xml.write_text('<testsuite><testcase name="executado"/></testsuite>')
    cobertura = {'estado': 'comprovado', 'casos': 1, 'relatorio_sha256': e._hash(xml)}
    prova = {'imagem': 'imagem', 'configuracao_base': 'config', 'executor': 'executor',
             'ensaio': 'ensaio', 'identidade': 'identidade', 'codigo': p.arvore(codigo),
             'artefato': {'codigo': str(codigo), 'comercial_xml': str(xml)}, 'cobertura': cobertura}
    arquivo = tmp_path / 'entregas/provas' / (C1 + '.json')
    arquivo.parent.mkdir(parents=True)
    arquivo.write_text(json.dumps(prova))
    monkeypatch.setattr(e, '_ferramentas', lambda *_: ('executor', 'ensaio'))
    monkeypatch.setattr(e, '_configuracao', lambda *_: 'config')
    monkeypatch.setattr(e, 'verificar_prova', lambda *_: prova)
    monkeypatch.setattr(p, 'conferir_relatorio', lambda f, **_: {
        'estado': 'comprovado', 'casos': 1, 'relatorio_sha256': e._hash(f)})
    return codigo, xml, arquivo, prova


def test_mesmos_insumos_reutilizam_e_copia_nao_altera_origem(tmp_path, monkeypatch):
    codigo, xml, _, prova = origem(tmp_path, monkeypatch)
    destino = tmp_path / 'novo/bundle'
    evidencias = destino.parent / 'evidencias'
    reuso = e.reaproveitar_celula(tmp_path, C1, tmp_path, 'funil', 'imagem', destino, evidencias)
    assert reuso['identidade'] == prova['identidade']
    assert p.arvore(destino) == p.arvore(codigo)
    assert (evidencias / 'comercial.xml').read_bytes() == xml.read_bytes()
    (destino / 'programa.py').write_text('valor = 2')
    assert (codigo / 'programa.py').read_text() == 'valor = 1'


@pytest.mark.parametrize('campo', ['imagem', 'configuracao_base', 'executor', 'ensaio'])
def test_insumo_diferente_nao_reaproveita(tmp_path, monkeypatch, campo):
    _, _, arquivo, prova = origem(tmp_path, monkeypatch)
    prova[campo] = 'diferente'
    arquivo.write_text(json.dumps(prova))
    destino = tmp_path / 'novo'
    assert e.reaproveitar_celula(tmp_path, C1, tmp_path, 'funil', 'imagem', destino,
                                tmp_path / 'evidencias') is None
    assert not destino.exists()


def test_corrupcao_da_prova_nao_vira_aprovacao(tmp_path, monkeypatch):
    origem(tmp_path, monkeypatch)
    def recusar(*_):
        raise e.RecusaEnsaio('bytes mudaram')
    monkeypatch.setattr(e, 'verificar_prova', recusar)
    with pytest.raises(e.RecusaEnsaio, match='bytes mudaram'):
        e.reaproveitar_celula(tmp_path, C1, tmp_path, 'funil', 'imagem', tmp_path / 'novo', tmp_path / 'evidencias')


def test_pacote_corrompido_recusado_antes_de_copiar(tmp_path, monkeypatch):
    codigo, _, _, _ = origem(tmp_path, monkeypatch)
    (codigo / 'programa.py').write_text('mudou')
    with pytest.raises(e.RecusaEnsaio, match='pacote de origem mudou'):
        e.reaproveitar_celula(tmp_path, C1, tmp_path, 'funil', 'imagem', tmp_path / 'novo', tmp_path / 'evidencias')


def test_celula_sem_prova_tem_ensaio_proprio(tmp_path):
    assert e.reaproveitar_celula(tmp_path, C1, tmp_path, 'funil', 'imagem', tmp_path / 'novo', tmp_path / 'evidencias') is None


def test_executor_funil_reusa_montagem_mas_executa_prova_especifica(tmp_path, monkeypatch):
    codigo_origem, _, _, prova = origem(tmp_path, monkeypatch)
    fonte = tmp_path / 'ensaios/entrada' / C1 / 'fonte'
    (fonte / 'services/funil').mkdir(parents=True)
    (fonte.parent / '.origem-ensaio.json').write_text(json.dumps({
        'candidata': C1, 'imagem_base': 'sha256:' + '1' * 64, 'arvore': p.arvore(fonte)}))
    prova['imagem'] = 'sha256:' + '1' * 64
    (tmp_path / 'entregas/provas' / (C1 + '.json')).write_text(json.dumps(prova))
    chamadas = []
    def nao_repetir(*_, **__):
        pytest.fail('montagem, estáticos ou teste comercial foram repetidos')
    monkeypatch.setattr(p, 'montar', nao_repetir)
    monkeypatch.setattr(p, 'ensaiar', nao_repetir)
    monkeypatch.setattr(e, '_coletar_estaticos', nao_repetir)
    monkeypatch.setattr(e, '_conferir_lancador', lambda: None)
    monkeypatch.setattr(p, 'imagem_id', lambda _: prova['imagem'])
    monkeypatch.setattr(e.subprocess, 'run', lambda *_a, **_k: SimpleNamespace(returncode=0))
    monkeypatch.setattr(e, '_snapshot_rota', lambda *_: None)
    monkeypatch.setattr(e, 'identidade_atual', lambda *_: {'configuracao_base': 'config', 'imagem': prova['imagem']})
    class Funil:
        def projetar(self, bundle, codigo, _):
            e.shutil.copytree(bundle, codigo)
        def conferir_projecao(self, *args):
            chamadas.append('projecao')
        def ensaiar_funil(self, *args):
            chamadas.append('teste_funil')
            return {'estado': 'comprovado', 'casos': 856}
    monkeypatch.setattr(e, '_modulo_funil', lambda _: Funil())
    monkeypatch.setattr(armazenamento, 'image_archive', lambda *_: {'reused': True})
    monkeypatch.setattr(armazenamento, 'snapshot', lambda *_: {'new_bytes': 0})
    r = e.executar(tmp_path, C1, tmp_path, 'funil')
    assert r['reaproveitamento']['celula'] == 'aplicacao'
    assert r['funil']['casos'] == 856
    assert chamadas == ['projecao', 'teste_funil']
    assert 'testes_comerciais' not in r['tempos']
    assert 'testes_funil' in r['tempos']
    assert p.arvore(codigo_origem) == prova['codigo']


def test_acompanhamento_grava_operacao_em_curso_e_tempos_sem_repetir(tmp_path):
    class Ponte(PonteFalsa):
        def preparar(self, id_, candidata, celula):
            atual = worker.estados.ler(id_)
            assert atual['operacao_atual']['nome'] == 'ensaio'
            assert atual['operacao_atual']['celula'] == celula
            super().preparar(id_, candidata, celula)
            return {'tempos': {'montagem': 2, 'testes_comerciais': 3}, 'reaproveitado': False}
    worker, _, ponte = servico(tmp_path, [entrega(I1, C1)], ponte=Ponte())
    assert worker.rodada()[0]['fase'] == 'ativa'
    r = worker.estados.ler(I1)
    assert r['tempos']['ensaio_aplicacao'] >= 0
    assert r['ensaios']['aplicacao']['tempos']['montagem'] == 2
    assert 'operacao_atual' not in r
    assert 'concluida_em' in r
