"""Exercise route recovery with temporary files; never contact a provider."""
import hashlib
import importlib
import json
from pathlib import Path
import sys
import types

import pytest

if sys.platform == 'win32':
    sys.modules.setdefault('fcntl', types.SimpleNamespace(LOCK_EX=2, flock=lambda *_: None))

reference = importlib.import_module('aplicar_referencia_rota_root')
publisher = importlib.import_module('publicar_rota_autorizada')


def digest(data):
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def route_state(tmp_path, monkeypatch):
    root = tmp_path / 'platform'
    task = root / 'appmax-clones/checkout-roblox-20261009'
    backup = task / 'backup-antes-publicar-rota-fixture'
    routes = root / 'traefik/dynamic/plataforma.yml'
    policy = root / 'policy.json'
    (backup / 'candidata/traefik/dynamic').mkdir(parents=True)
    routes.parent.mkdir(parents=True)
    (root / 'publicacoes').mkdir()
    old_routes = b'http:\n  routers: {}\n'
    new_routes = b'http:\n  routers: {checkout-appmax-roblox-teste: {}}\n'
    old_policy = json.dumps({'rotas_sha256': digest(old_routes), 'imagem': 'unchanged'}).encode()
    new_policy = json.dumps({'rotas_sha256': digest(new_routes), 'imagem': 'unchanged'}).encode()
    prepared = {'backup_privado': str(backup), 'imagem': 'fixture-image',
                'rotas_normalizadas_antes': digest(old_routes),
                'rotas_normalizadas_depois': digest(new_routes),
                'autorizacao': {'resposta_do_mantenedor': 'Autorizar somente essa rota em modo de teste'}}
    for name, data, key in (
        ('rotas-anteriores.yml', old_routes, 'rota_anterior_arquivo_sha256'),
        ('candidata/traefik/dynamic/plataforma.yml', new_routes, 'rota_candidata_arquivo_sha256'),
        ('politica-anterior.json', old_policy, 'politica_anterior_sha256'),
        ('politica-candidata.json', new_policy, 'politica_candidata_sha256'),
    ):
        (backup / name).write_bytes(data)
        prepared[key] = digest(data)
    (task / 'publicacao-rota-preparada.json').write_text(json.dumps(prepared))
    (root / 'publicacoes/aplicacao.json').write_text(json.dumps({'aprovada': {'codigo': 'fixture', 'imagem': 'unchanged'}}))
    routes.write_bytes(old_routes)
    policy.write_bytes(old_policy)
    monkeypatch.setattr(reference, 'ROOT', root)
    monkeypatch.setattr(reference, 'TASK', task)
    monkeypatch.setattr(reference, 'ROUTES', routes)
    monkeypatch.setattr(reference, 'POLICY', policy)
    monkeypatch.setattr(reference.os, 'geteuid', lambda: 0, raising=False)
    monkeypatch.setattr(reference.os, 'chown', lambda *_: None, raising=False)
    frozen = types.SimpleNamespace(
        conferir_ambiente=lambda *_: None,
        conferir_pacote=lambda *_: None,
        conferir_rotas=lambda *_: None,
    )
    def check_routes(folder, data):
        assert digest((Path(folder) / 'traefik/dynamic/plataforma.yml').read_bytes()) == data['rotas_sha256']
    frozen.conferir_rotas = check_routes
    monkeypatch.setattr(reference, 'load_checker', lambda: frozen)
    return types.SimpleNamespace(root=root, task=task, backup=backup, routes=routes, policy=policy,
                                 old_routes=old_routes, old_policy=old_policy, prepared=prepared, frozen=frozen)


def test_only_route_reference_changes_and_restores(route_state):
    state = route_state
    reference.perform_locked('apply')
    assert json.loads(state.policy.read_bytes())['imagem'] == 'unchanged'
    assert state.routes.read_bytes() != state.old_routes
    reference.perform_locked('rollback')
    assert state.routes.read_bytes() == state.old_routes
    assert state.policy.read_bytes() == state.old_policy


def test_failure_after_swap_restores_both_files(route_state):
    state = route_state
    def reject_new_reference(_, data):
        if data['rotas_sha256'] == state.prepared['rotas_normalizadas_depois']:
            raise RuntimeError('simulated independent check failure')
    state.frozen.conferir_ambiente = reject_new_reference
    with pytest.raises(RuntimeError):
        reference.perform_locked('apply')
    assert state.routes.read_bytes() == state.old_routes
    assert state.policy.read_bytes() == state.old_policy


def test_publisher_recovers_if_apply_confirmation_fails(route_state, monkeypatch):
    state = route_state
    monkeypatch.setattr(publisher, 'ROOT', state.root)
    monkeypatch.setattr(publisher, 'TASK', state.task)
    monkeypatch.setattr(publisher.preparation, 'main', lambda: None)
    monkeypatch.setattr(publisher, 'assert_test_copy', lambda *_: None)
    operations = []
    def run(args, data=None):
        operations.append(args)
        return json.dumps([{'Image': 'fixture-image', 'NetworkSettings': {'Networks': {}}}])
    monkeypatch.setattr(publisher, 'run', run)
    def apply_then_lose_confirmation(action):
        result = reference.perform_locked(action)
        if action == 'apply':
            raise RuntimeError('simulated missing confirmation')
        return result
    monkeypatch.setattr(publisher, 'switch', apply_then_lose_confirmation)
    with pytest.raises(RuntimeError):
        publisher.activate_locked()
    assert state.routes.read_bytes() == state.old_routes
    assert state.policy.read_bytes() == state.old_policy
    assert any(args[:3] == ['docker', 'network', 'disconnect'] for args in operations)


def test_changed_backup_is_refused_before_mutating(route_state):
    state = route_state
    (state.backup / 'politica-candidata.json').write_text('{}')
    with pytest.raises(RuntimeError, match='Prepared bytes changed'):
        reference.perform_locked('apply')
    assert state.routes.read_bytes() == state.old_routes
    assert state.policy.read_bytes() == state.old_policy
