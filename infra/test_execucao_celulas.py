import importlib.util
import json
from pathlib import Path
import uuid

import pytest


def carregar(nome):
    spec = importlib.util.spec_from_file_location(nome.replace('-', '_'), Path(__file__).parent / (nome + '.py'))
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_projecao_recusa_codigo_de_outro_modulo_e_troca_de_arquivo(tmp_path):
    modulo = carregar('execucao-celulas')
    bundle = tmp_path / 'bundle'
    (bundle / 'config').mkdir(parents=True)
    (bundle / 'config/settings.py').write_text('configuracao original')
    for nome in ('entrypoint.py', 'workers.py', 'internal.py'):
        (bundle / nome).write_text('codigo original')
    (bundle / 'modules/funil').mkdir(parents=True)
    (bundle / 'modules/admin').mkdir()
    (bundle / 'modules/__init__.py').touch()
    (bundle / 'modules/funil/views.py').write_text('pagina original')
    destino = tmp_path / 'funil'
    modulo.projetar(bundle, destino, 'funil')
    assert not (destino / 'modules/admin').exists()
    modulo.conferir_projecao(bundle, destino, 'funil')
    (destino / 'modules/funil/views.py').write_text('pagina substituida')
    with pytest.raises(ValueError, match='diferente'):
        modulo.conferir_projecao(bundle, destino, 'funil')
    (destino / 'modules/funil/views.py').write_text('pagina original')
    (destino / 'modules/admin').mkdir()
    with pytest.raises(ValueError, match='outra célula'):
        modulo.conferir_projecao(bundle, destino, 'funil')


@pytest.mark.parametrize('alteracao', [
    {'event': 'pagamento.confirmado'}, {'version': True}, {'version': 2},
    {'event_id': 'identificador-invalido'}, {'data': {}},
])
def test_ponte_recusa_evento_incompativel(alteracao):
    ponte = carregar('ponte-celula')
    evento = {'event': 'funil.pagina-vista', 'version': 1, 'event_id': str(uuid.uuid4()),
              'occurred_at': '2026-10-06T00:00:00+00:00', 'data': {'site_id': 'ensaio'}}
    evento.update(alteracao)
    with pytest.raises(ValueError):
        ponte.conferir_evento('eventos.funil.pagina-vista', {'json': json.dumps(evento)})


def test_recuperacao_de_rota_fica_restrita_a_funil(tmp_path):
    modulo = carregar('execucao-celulas')
    arquivo = tmp_path / 'plataforma.yml'
    texto = '\n  services:\n    funil:\n      loadBalancer:\n        servers: [ { url: "http://aplicacao:8000" } ]\n    identidade:\n      loadBalancer:\n        servers: [ { url: "http://aplicacao:8000" } ]\n'
    arquivo.write_text(texto)
    modulo.apontar('candidata', arquivo)
    assert 'http://candidata:8000' in arquivo.read_text()
    assert arquivo.read_text().count('http://aplicacao:8000') == 1
    modulo.apontar('aplicacao', arquivo)
    assert arquivo.read_text() == texto


def test_recuperacao_recusa_codigo_anterior_alterado(tmp_path, monkeypatch):
    modulo = carregar('execucao-celulas')
    codigo = tmp_path / 'codigo'
    codigo.mkdir()
    (codigo / 'entrypoint.py').write_text('alterado')
    anterior = {'codigo': str(codigo), 'pacote': {'codigo_sha256': 'incorreto'}}
    monkeypatch.setattr(modulo, 'topologia', lambda: {'celulas': {'funil': {'anterior': anterior}}})
    chamadas = []
    monkeypatch.setattr(modulo, 'executar', lambda *args: chamadas.append(args))
    with pytest.raises(RuntimeError, match='código anterior'):
        modulo.recuperar_celula('funil')
    assert chamadas == []


def test_vigia_nao_reinicia_celula_saudavel(monkeypatch):
    modulo = carregar('execucao-celulas')
    monkeypatch.setattr(modulo, 'retomar_troca', lambda: None)
    monkeypatch.setattr(modulo, 'topologia', lambda: {'celulas': {'funil': {'container': 'saudavel'}}})
    monkeypatch.setattr(modulo, 'saudavel', lambda nome: True)
    chamadas = []
    monkeypatch.setattr(modulo, 'executar', lambda *args: chamadas.append(args))
    modulo.vigiar_travado()
    assert chamadas == []


def test_vigia_preserva_aplicacao_saudavel_quando_entrada_falha(tmp_path, monkeypatch):
    from types import SimpleNamespace
    modulo = carregar('publicar')
    monkeypatch.setattr(modulo, 'PUBLICACOES', tmp_path)
    monkeypatch.setattr(modulo, 'publicacao_em_andamento', lambda: False)
    monkeypatch.setattr(modulo, 'carregar_celulas', lambda: SimpleNamespace(
        vigiar=lambda: None, topologia=lambda: {'celulas': {'funil': {}}}))
    monkeypatch.setattr(modulo, 'site_abre', lambda: False)
    monkeypatch.setattr(modulo.time, 'sleep', lambda segundos: None)
    monkeypatch.setattr(modulo.subprocess, 'run', lambda *a, **k: SimpleNamespace(returncode=0))
    chamadas = []
    monkeypatch.setattr(modulo, 'religar_aplicacao', lambda: chamadas.append('reiniciar'))
    monkeypatch.setattr(modulo, 'recuperar', lambda celula: chamadas.append('recuperar'))
    assert modulo.vigiar_uma_vez() == 1
    assert chamadas == []
    assert 'principal saudável' in json.loads((tmp_path / 'incidente.json').read_text())['alcance']
