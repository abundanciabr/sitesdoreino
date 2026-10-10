"""Local checks for the one authorized Appmax sandbox route change."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import types

import pytest


# The administrative helper runs on Linux; these tests also run on Windows.
if sys.platform == 'win32' and 'fcntl' not in sys.modules:
    fcntl = types.ModuleType('fcntl')
    fcntl.LOCK_EX = 2
    fcntl.flock = lambda *_: None
    sys.modules['fcntl'] = fcntl

SPEC = importlib.util.spec_from_file_location('publicar_curso_blender', Path(__file__).with_name('publicar_curso_blender.py'))
helper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helper)


class RouteChecker:
    @staticmethod
    def capturar_rotas(root):
        content = (Path(root) / 'traefik/dynamic/plataforma.yml').read_bytes()
        return hashlib.sha256(content).hexdigest()

    def conferir_rotas(self, root, policy):
        assert self.capturar_rotas(root) == policy['rotas_sha256']


def route_yaml(*, router_before: bool) -> bytes:
    target = (
        f'    checkout-appmax-roblox-teste:\n'
        f'      rule: "Host(`meshcraft.top`) && (Path(`{helper.OLD}`) || PathPrefix(`{helper.OLD}/`))"\n'
        '      service: "checkout-appmax-roblox-teste"\n'
        '      entryPoints: ["websecure"]\n'
        '      priority: 30\n'
        '      middlewares: ["seguranca"]\n'
        '      tls: {}\n'
    )
    other = (
        '    checkout:\n'
        '      rule: "Host(`meshcraft.top`) && PathPrefix(`/checkout`)"\n'
        '      service: "checkout"\n'
        '      priority: 10\n'
    )
    routers = target + other if router_before else other + target
    return (
        'http:\n  routers:\n' + routers +
        '  services:\n'
        '    checkout-appmax-roblox-teste:\n'
        '      loadBalancer:\n'
        '        servers: [{ url: "http://meshcraft-checkout-appmax-roblox-20261009:8000" }]\n'
        '    checkout:\n'
        '      loadBalancer: {}\n'
    ).encode()


@pytest.mark.parametrize('router_before', [True, False])
def test_route_candidate_changes_only_dedicated_rule_and_policy_hash(tmp_path, router_before):
    before = route_yaml(router_before=router_before)
    policy = {'imagem': 'unchanged', 'rotas_sha256': hashlib.sha256(before).hexdigest(),
              'ambiente': {'unchanged': True}}
    policy_bytes = json.dumps(policy, sort_keys=True).encode()

    candidate, policy_after = helper.route_candidate(
        before, RouteChecker(), tmp_path / 'backup', policy, policy_bytes)

    old_rule = (f'Host(`meshcraft.top`) && (Path(`{helper.OLD}`) || '
                f'PathPrefix(`{helper.OLD}/`))').encode()
    new_rule = (f'Host(`meshcraft.top`) && (Path(`{helper.NEW}`) || PathPrefix(`{helper.NEW}/`) || '
                f'Path(`{helper.OLD}`) || PathPrefix(`{helper.OLD}/`))').encode()
    assert before.count(old_rule) == 1
    assert candidate == before.replace(old_rule, new_rule, 1)
    assert candidate.count(b'    checkout-appmax-roblox-teste:') == 2  # router and service
    assert candidate.split(b'  services:\n', 1)[1] == before.split(b'  services:\n', 1)[1]
    expected_policy = dict(policy, rotas_sha256=hashlib.sha256(candidate).hexdigest())
    assert json.loads(policy_after) == expected_policy
    assert policy_after.replace(expected_policy['rotas_sha256'].encode(),
                                policy['rotas_sha256'].encode(), 1) == policy_bytes


def test_public_proof_failure_restores_only_clone_files_route_and_policy(tmp_path, monkeypatch):
    source_root = tmp_path / 'reviewed'
    source_dir = source_root / 'services/checkout_appmax'
    clone = tmp_path / 'clone'
    destination = clone / 'servico'
    source_dir.joinpath('assets').mkdir(parents=True)
    destination.joinpath('assets').mkdir(parents=True)
    originals = {}
    for name in helper.FILES:
        before = ('previous ' + name).encode()
        after = ('reviewed ' + name).encode()
        if name.endswith('checkout.html'):
            after += b' __CHECKOUT_CONFIG__'
        (destination / name).write_bytes(before)
        (source_dir / name).write_bytes(after)
        originals[name] = before
    (source_dir / 'oferta_blender.py').write_text('print("offer helper")')

    route = tmp_path / 'plataforma.yml'
    route_before = route_yaml(router_before=True)
    route.write_bytes(route_before)
    policy = tmp_path / 'politica.json'
    policy_before = json.dumps({'rotas_sha256': hashlib.sha256(route_before).hexdigest(),
                                'imagem': 'unchanged'}, sort_keys=True).encode()
    policy.write_bytes(policy_before)
    publicacoes = tmp_path / 'publicacoes'
    publicacoes.mkdir()

    monkeypatch.setattr(helper, 'TASK', clone)
    monkeypatch.setattr(helper, 'DEST', destination)
    monkeypatch.setattr(helper, 'ROOT', tmp_path)
    monkeypatch.setattr(helper, 'ROUTES', route)
    monkeypatch.setattr(helper, 'POLICY', policy)
    monkeypatch.setattr(helper.os, 'geteuid', lambda: 0, raising=False)
    if sys.platform == 'win32':
        monkeypatch.setattr(helper.os, 'fchmod', lambda *_: None, raising=False)
    monkeypatch.setattr(helper, 'frozen_checker', RouteChecker)

    def assert_frozen(checker, current_policy):
        assert current_policy['rotas_sha256'] == hashlib.sha256(route.read_bytes()).hexdigest()
        return {'imagem': 'approved-image'}

    monkeypatch.setattr(helper, 'prove_frozen', assert_frozen)
    monkeypatch.setattr(helper, 'clone_running', lambda *_: None)
    monkeypatch.setattr(helper, 'offer_command', lambda *_args, **_kwargs: helper.EXPECTED)
    monkeypatch.setattr(helper, 'prove_page', lambda *_args, **_kwargs: {})
    observed_swapped = []

    def failed_public_proof(_source):
        observed_swapped.append(route.read_bytes() != route_before and policy.read_bytes() != policy_before)
        assert all((destination / name).read_bytes() != originals[name] for name in helper.FILES)
        raise RuntimeError('public proof failed')

    monkeypatch.setattr(helper, 'proof_public', failed_public_proof)
    monkeypatch.setattr(helper.time, 'sleep', lambda *_: None)
    monkeypatch.setattr(helper, 'atomic', lambda path, data, _owner: path.write_bytes(data))

    def backup(folder, _approved, original_bytes):
        folder.mkdir(parents=True)
        assert original_bytes['rotas.yml'] == route_before
        assert original_bytes['politica.json'] == policy_before
        return {'verified': True}

    monkeypatch.setattr(helper, 'complete_backup', backup)
    commands = []

    def command(args, *_a, **_k):
        commands.append(tuple(args))
        return b''

    monkeypatch.setattr(helper, 'checked', command)
    with pytest.raises(RuntimeError, match='public proof failed'):
        helper.run(source_root)

    assert route.read_bytes() == route_before
    assert policy.read_bytes() == policy_before
    assert observed_swapped and all(observed_swapped)
    assert all((destination / name).read_bytes() == previous for name, previous in originals.items())
    assert commands == [('docker', 'restart', helper.WEB), ('docker', 'restart', helper.WEB)]
    assert not any('pg_restore' in part or 'psql' in part for command_parts in commands for part in command_parts)
