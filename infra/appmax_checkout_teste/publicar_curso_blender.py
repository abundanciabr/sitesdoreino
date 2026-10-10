#!/usr/bin/env python3
"""Publish the renamed Appmax sandbox checkout from a reviewed source tree.

Run as root in the hosting console: python3 publicar_curso_blender.py RAIZ_REVISAO
Only the private clone, its existing router rule, and the route hash change.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import signal
import stat
import subprocess
import tarfile
import time
import urllib.request
from urllib.parse import unquote, urlparse


ROOT = Path('/opt/plataforma')
TASK = ROOT / 'appmax-clones/checkout-roblox-20261009'
DEST = TASK / 'servico'
TOOLS = Path('/usr/local/lib/meshcraft-publicador/v1-20261006T184415Z')
POLICY = TOOLS / 'mercadopago/politica.json'
ROUTES = ROOT / 'traefik/dynamic/plataforma.yml'
WEB = 'meshcraft-checkout-appmax-roblox-20261009'
OLD = '/checkout/comprar-desafio-como-ganhar-em-dolar-com-roblox'
NEW = '/checkout/curso-primeiros-passos-no-blender'
URL = 'https://meshcraft.top' + NEW
MP_URL = 'https://meshcraft.top/checkout/desafio-como-ganhar-em-dolar-com-roblox/'
FILES = ('wrapper.py', 'assets/checkout.css', 'assets/checkout.js', 'assets/checkout.html')
OFFER = 'services/checkout_appmax/oferta_blender.py'
EXPECTED = {'slug': 'curso-primeiros-passos-no-blender',
            'name': 'Curso Primeiros Passos com 3d no Blender', 'price_cents': 2700}
SANDBOX_SCRIPT = 'https://scripts.sandboxappmax.com.br/appmax.min.js'


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(part)
    return digest.hexdigest()


def checked(args: list[str], data: bytes | None = None, timeout: int = 300) -> bytes:
    result = subprocess.run(args, input=data, capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError('Administrative operation failed: ' + args[0])
    return result.stdout


def frozen_checker():
    spec = importlib.util.spec_from_file_location('frozen', TOOLS / 'infra/mercadopago_congelado.py')
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    return checker


def prove_frozen(checker, policy: dict) -> dict:
    approved = json.loads((ROOT / 'publicacoes/aplicacao.json').read_text())['aprovada']
    checker.conferir_ambiente(ROOT, policy)
    checker.conferir_rotas(ROOT, policy)
    checker.conferir_pacote(approved['codigo'], approved['imagem'], policy)
    checker.conferir_pacote(TASK / 'codigo-aprovado-copia', approved['imagem'], policy)
    return approved


def regular(path: Path) -> os.stat_result:
    if path.is_symlink():
        raise RuntimeError('Symbolic file refused')
    result = path.stat(follow_symlinks=False)
    if not stat.S_ISREG(result.st_mode):
        raise RuntimeError('Regular file required')
    return result


def sync_dir(folder: Path) -> None:
    fd = os.open(folder, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic(path: Path, data: bytes, owner: os.stat_result) -> None:
    temporary = path.with_name('.' + path.name + '.blender-' + secrets.token_hex(8))
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chown(temporary, owner.st_uid, owner.st_gid)
        os.chmod(temporary, stat.S_IMODE(owner.st_mode))
        regular(path)
        os.replace(temporary, path)
        sync_dir(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def env_values(path: Path) -> dict:
    values = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('export '):
            line = line[7:].lstrip()
        key, sep, value = line.partition('=')
        if sep:
            value = value.strip()
            if value[:1] in ('"', "'") and value[-1:] == value[:1]:
                value = value[1:-1]
            elif ' #' in value:
                value = value.split(' #', 1)[0].rstrip()
            values[key.strip()] = value
    return values


def backup_database(path: Path, container: str, output: Path, *, clone: bool) -> dict:
    url = urlparse(env_values(path)['DATABASE_URL'])
    if clone and (url.hostname != 'postgres' or url.username != 'appmax_clone'):
        raise RuntimeError('Clone database is not isolated')
    fields = [unquote(value) for value in (url.username or '', url.password or '', url.path.lstrip('/'))]
    if any('\n' in field or '\r' in field or not field for field in fields):
        raise RuntimeError('Invalid database connection')
    command = ('IFS= read -r PGUSER; IFS= read -r PGPASSWORD; IFS= read -r PGDATABASE; '
               'export PGUSER PGPASSWORD PGDATABASE; '
               'exec pg_dump --format=custom --no-owner --no-privileges')
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'wb') as stream:
            result = subprocess.run(['docker', 'exec', '-i', container, 'sh', '-c', command],
                                    input=('\n'.join(fields) + '\n').encode(), stdout=stream,
                                    stderr=subprocess.DEVNULL, timeout=300)
            stream.flush()
            os.fsync(stream.fileno())
        if result.returncode:
            raise RuntimeError('Private database backup failed')
        content = output.read_bytes()
        listing = checked(['docker', 'exec', '-i', container, 'pg_restore', '--list'], content, 120)
        if len(listing.splitlines()) < 20:
            raise RuntimeError('Database backup could not be read')
        return {'sha256': sha(content), 'bytes': len(content), 'verified': True}
    finally:
        del fields


def complete_backup(backup: Path, approved: dict, originals: dict[str, bytes]) -> dict:
    backup.mkdir(mode=0o700, parents=True)
    for name, content in originals.items():
        target = backup / ('before-' + name.replace('/', '-'))
        with target.open('xb') as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if target.read_bytes() != content:
            raise RuntimeError('Source backup differs')
    archive_path = backup / 'codigo-configuracao.tar.gz'
    fd = os.open(archive_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        with tarfile.open(fileobj=stream, mode='w:gz') as archive:
            for source, name in ((Path(approved['codigo']), 'codigo-original'),
                                 (ROOT / '.env', 'configuracao/.env'),
                                 (ROOT / 'docker-compose.yml', 'configuracao/docker-compose.yml'),
                                 (ROOT / 'traefik', 'configuracao/traefik'),
                                 (ROOT / 'publicacoes/aplicacao.json', 'configuracao/aplicacao.json'),
                                 (POLICY, 'configuracao/politica.json'),
                                 (TASK / 'servico', 'servico-clone'),
                                 (TASK / 'codigo-aprovado-copia', 'codigo-aprovado-clone')):
                archive.add(source, arcname=name)
            for source in (ROOT / 'env').glob('*.env'):
                archive.add(source, arcname='configuracao/env/' + source.name)
            for source in (TASK / 'env-privado').glob('*.env'):
                archive.add(source, arcname='configuracao-clone/' + source.name)
        stream.flush()
        os.fsync(stream.fileno())
    with tarfile.open(archive_path, 'r:gz') as archive:
        if len(archive.getmembers()) < 50:
            raise RuntimeError('Code and configuration backup incomplete')
    print(json.dumps({'etapa': 'backup_codigo_configuracoes_conferido'}), flush=True)
    image = backup / 'imagem-aprovada.tar'
    fd = os.open(image, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        result = subprocess.run(['docker', 'image', 'save', approved['imagem']], stdout=stream,
                                stderr=subprocess.DEVNULL, timeout=300)
        stream.flush()
        os.fsync(stream.fileno())
    if result.returncode:
        raise RuntimeError('Approved image backup failed')
    with tarfile.open(image) as archive:
        manifest = json.loads(archive.extractfile('manifest.json').read())
        config = archive.extractfile(manifest[0]['Config']).read()
        blob = 'blobs/sha256/' + approved['imagem'].split(':', 1)[1]
        if ('sha256:' + sha(config) != approved['imagem'] and
                (blob not in archive.getnames() or 'sha256:' + sha(archive.extractfile(blob).read()) != approved['imagem'])):
            raise RuntimeError('Approved image backup differs')
    print(json.dumps({'etapa': 'backup_imagem_conferido'}), flush=True)
    databases = {}
    for service in ('checkout', 'pagamentos'):
        databases['original-' + service] = backup_database(
            ROOT / 'env' / (service + '.env'), 'plataforma-postgres-1', backup / ('original-' + service + '.dump'), clone=False)
    clone_env = sorted((TASK / 'env-privado').glob('*.env'))
    for path in clone_env:
        if 'DATABASE_URL' in env_values(path):
            databases['clone-' + path.stem] = backup_database(
                path, 'meshcraft-appmax-roblox-sandbox-postgres-20261009',
                backup / ('clone-' + path.stem + '.dump'), clone=True)
    if not all('clone-' + name in databases for name in ('catalogo', 'checkout', 'pagamentos')):
        raise RuntimeError('Related clone database backups incomplete')
    print(json.dumps({'etapa': 'backup_bancos_conferido', 'bancos': len(databases)}), flush=True)
    return {'code_config_sha256': sha_file(archive_path),
            'image_sha256': sha_file(image), 'databases': databases}


def route_candidate(before: bytes, checker, backup: Path, policy: dict, policy_bytes: bytes) -> tuple[bytes, bytes]:
    old_rule = (f'Host(`meshcraft.top`) && (Path(`{OLD}`) || PathPrefix(`{OLD}/`))').encode()
    new_rule = (f'Host(`meshcraft.top`) && (Path(`{NEW}`) || PathPrefix(`{NEW}/`) || '
                f'Path(`{OLD}`) || PathPrefix(`{OLD}/`))').encode()
    routers_marker = b'  routers:\n'
    services_marker = b'  services:\n'
    if before.count(routers_marker) != 1 or before.count(services_marker) != 1:
        raise RuntimeError('Traefik router or service section differs')
    routers_start = before.index(routers_marker) + len(routers_marker)
    routers_end = before.index(services_marker)
    if routers_start >= routers_end:
        raise RuntimeError('Traefik sections are out of order')
    section = before[routers_start:routers_end]
    matches = list(re.finditer(rb'(?m)^    checkout-appmax-roblox-teste:[ \t]*\r?$', section))
    if len(matches) != 1:
        raise RuntimeError('Dedicated Appmax router is absent or repeated')
    match = matches[0]
    next_router = re.search(rb'(?m)^    [A-Za-z][A-Za-z0-9_-]*:[ \t]*\r?$', section[match.end():])
    start = routers_start + match.start()
    stop = routers_start + match.end() + next_router.start() if next_router else routers_end
    block = before[start:stop]
    if block.count(old_rule) != 1 or b'rule: "' + old_rule + b'"' not in block:
        raise RuntimeError('Existing route does not match the expected Appmax rule')
    updated = block.replace(old_rule, new_rule, 1)
    candidate = before[:start] + updated + before[stop:]
    if candidate.replace(new_rule, old_rule, 1) != before:
        raise RuntimeError('Route change exceeds the dedicated rule')
    candidate_root = backup / 'candidata'
    folder = candidate_root / 'traefik/dynamic'
    folder.mkdir(parents=True, mode=0o700)
    (folder / 'plataforma.yml').write_bytes(candidate)
    os.chmod(folder / 'plataforma.yml', 0o600)
    next_hash = checker.capturar_rotas(candidate_root)
    next_policy = dict(policy)
    next_policy['rotas_sha256'] = next_hash
    checker.conferir_rotas(candidate_root, next_policy)
    pattern = rb'("rotas_sha256"\s*:\s*")' + policy['rotas_sha256'].encode() + rb'(")'
    if len(re.findall(pattern, policy_bytes)) != 1:
        raise RuntimeError('Route policy representation changed')
    candidate_policy = re.sub(pattern, lambda m: m.group(1) + next_hash.encode() + m.group(2), policy_bytes)
    if json.loads(candidate_policy) != next_policy:
        raise RuntimeError('Policy change exceeds route hash')
    return candidate, candidate_policy


def fetch(url: str, host: str | None = None) -> tuple[int, bytes, str]:
    headers = {'Host': host} if host else {}
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20) as response:
        return response.status, response.read(), response.geturl()


def config(page: bytes) -> dict:
    match = re.search(rb'<script id="checkout-config" type="application/json">(.*?)</script>', page, re.S)
    if not match or b'mercadopago.com' in page.lower() or b'MP_DEVICE_SESSION_ID' in page:
        raise RuntimeError('Expected Appmax-only checkout not found')
    result = json.loads(match.group(1))
    if (result.get('environment') != 'sandbox' or result.get('scriptURL') != SANDBOX_SCRIPT or
            result.get('offerSlug') != EXPECTED['slug'] or result.get('apiBase') != NEW + '/api'):
        raise RuntimeError('Sandbox checkout configuration differs')
    return result


def clone_running(approved: dict) -> None:
    current = json.loads(checked(['docker', 'inspect', WEB]))[0]
    if not current['State']['Running'] or current['Image'] != approved['imagem']:
        raise RuntimeError('Approved clone is unavailable')
    if 'meshcraft-appmax-roblox-sandbox-20261009' not in current['NetworkSettings']['Networks']:
        raise RuntimeError('Exclusive sandbox network is absent')
    mounts = {item['Destination']: item for item in current.get('Mounts', [])}
    for destination, folder in (('/clone', DEST), ('/approved', TASK / 'codigo-aprovado-copia'),
                                ('/run/plataforma-env', TASK / 'env-privado')):
        mount = mounts.get(destination, {})
        if mount.get('Source') != str(folder) or mount.get('RW') is not False:
            raise RuntimeError('Read-only clone mount differs')
    for service in ('checkout', 'pagamentos'):
        values = env_values(TASK / 'env-privado' / (service + '.env'))
        if values.get('APPMAX_API_URL') != 'https://api.sandboxappmax.com.br':
            raise RuntimeError('Clone provider is not sandbox')
        url = urlparse(values['DATABASE_URL'])
        if url.hostname != 'postgres' or url.username != 'appmax_clone':
            raise RuntimeError('Clone payment database is not isolated')
        if any(value for key, value in values.items() if key.startswith('MP_')):
            raise RuntimeError('Mercado Pago credential found in clone')


def offer_command(source: bytes, verify: bool) -> dict:
    args = ['docker', 'exec', '-i', WEB, 'python', '-']
    if verify:
        args.append('--verificar')
    raw = checked(args, source, 120)
    try:
        result = json.loads(raw.decode().strip().splitlines()[-1])
    except (ValueError, IndexError) as error:
        raise RuntimeError('Offer helper did not return JSON') from error
    if not all(result.get(key) == value for key, value in EXPECTED.items()):
        raise RuntimeError('Private offer name, slug or price differs')
    return {key: result[key] for key in EXPECTED}


def prove_page(source: dict[str, bytes], *, public: bool) -> dict:
    base = URL if public else 'http://127.0.0.1:18049' + NEW
    host = None if public else 'meshcraft.top'
    statuses = {}
    for path in ('', '/', '/assets/checkout.css', '/assets/checkout.js'):
        code, body, final = fetch(base + path, host)
        if code != 200:
            raise RuntimeError('Checkout page or asset unavailable')
        statuses[path or 'canonical'] = code
        if path in ('', '/'):
            config(body)
            if urlparse(final).path != NEW:
                raise RuntimeError('Canonical redirect differs')
            if EXPECTED['name'].encode() not in body:
                raise RuntimeError('Checkout product title differs')
        else:
            name = 'assets/' + path.rsplit('/', 1)[-1]
            if body != source[name]:
                raise RuntimeError('Published asset differs')
    return statuses


def proof_public(source: dict[str, bytes]) -> dict:
    status = prove_page(source, public=True)
    _, old_page, old_final = fetch('https://meshcraft.top' + OLD)
    if urlparse(old_final).path != NEW or EXPECTED['name'].encode() not in old_page:
        raise RuntimeError('Old checkout URL did not reach the renamed page')
    for url in ('https://meshcraft.top/', MP_URL):
        code, body, _ = fetch(url)
        if code != 200:
            raise RuntimeError('Original site health proof failed')
        if url == MP_URL and (b'mercadopago.com' not in body.lower() or b'checkout-config' in body):
            raise RuntimeError('Original Mercado Pago checkout differs')
    status['old_url_redirect'] = 200
    status['home'] = 200
    status['mercado_pago'] = 200
    return status


def run(source_root: Path) -> None:
    if os.geteuid() != 0:
        raise RuntimeError('Administrative hosting console required')
    source_dir = source_root / 'services/checkout_appmax'
    source = {}
    for name in FILES:
        regular(source_dir / name)
        source[name] = (source_dir / name).read_bytes()
        if not source[name]:
            raise RuntimeError('Reviewed source file is empty')
    offer_path = source_root / OFFER
    regular(offer_path)
    offer_source = offer_path.read_bytes()
    if not offer_source:
        raise RuntimeError('Reviewed offer helper is empty')
    if source['assets/checkout.html'].count(b'__CHECKOUT_CONFIG__') != 1:
        raise RuntimeError('Checkout configuration placeholder differs')
    with (ROOT / 'publicacoes/.receber.lock').open('a') as receiving, \
            (ROOT / 'publicacoes/.ativacao.lock').open('a') as activation:
        fcntl.flock(receiving, fcntl.LOCK_EX)
        fcntl.flock(activation, fcntl.LOCK_EX)
        checker = frozen_checker()
        policy_bytes = POLICY.read_bytes()
        policy = json.loads(policy_bytes)
        approved = prove_frozen(checker, policy)
        clone_running(approved)
        owners = {name: regular(DEST / name) for name in FILES}
        originals = {name: (DEST / name).read_bytes() for name in FILES}
        route_before = ROUTES.read_bytes()
        stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        backup = TASK / 'backups-curso-blender' / (stamp + '-' + str(os.getpid()))
        originals_with_route = dict(originals, **{'rotas.yml': route_before, 'politica.json': policy_bytes})
        details = complete_backup(backup, approved, originals_with_route)
        request_record = backup / 'pedido.json'
        with request_record.open('x', encoding='utf-8') as stream:
            os.fchmod(stream.fileno(), 0o600)
            json.dump({'pedido': EXPECTED, 'url': URL, 'ambiente': 'sandbox'}, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        manifest = backup / 'manifesto-backup.json'
        with manifest.open('x', encoding='utf-8') as stream:
            os.fchmod(stream.fileno(), 0o600)
            json.dump(details, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        candidate, candidate_policy = route_candidate(route_before, checker, backup, policy, policy_bytes)
        if ROUTES.read_bytes() != route_before or POLICY.read_bytes() != policy_bytes:
            raise RuntimeError('Protected route reference changed during backup')
        prove_frozen(checker, policy)
        changed = []
        restarted = False
        route_changed = False
        try:
            offer_command(offer_source, verify=False)
            offer_command(offer_source, verify=True)
            for name in FILES:
                if originals[name] != source[name]:
                    changed.append(name)
                    atomic(DEST / name, source[name], owners[name])
            checked(['docker', 'restart', WEB], timeout=120)
            restarted = True
            clone_running(approved)
            for attempt in range(15):
                try:
                    prove_page(source, public=False)
                    break
                except Exception:
                    if attempt == 14:
                        raise
                    time.sleep(1)
            offer_command(offer_source, verify=True)
            if ROUTES.read_bytes() != route_before or POLICY.read_bytes() != policy_bytes:
                raise RuntimeError('Protected route reference changed during preparation')
            route_changed = True
            atomic(POLICY, candidate_policy, regular(POLICY))
            atomic(ROUTES, candidate, regular(ROUTES))
            prove_frozen(checker, json.loads(candidate_policy))
            for attempt in range(15):
                try:
                    status = proof_public(source)
                    break
                except Exception:
                    if attempt == 14:
                        raise
                    time.sleep(1)
            if ROUTES.read_bytes() != candidate or POLICY.read_bytes() != candidate_policy:
                raise RuntimeError('Protected route reference changed after proof')
            prove_frozen(checker, json.loads(candidate_policy))
            print(json.dumps({'published': True, 'url': URL, 'environment': 'sandbox',
                              'offer': EXPECTED, 'http': status, 'backup': str(backup),
                              'backup_verified': True,
                              'database_restored': False}, ensure_ascii=False))
        except BaseException:
            restored = True
            if route_changed:
                try:
                    atomic(ROUTES, route_before, regular(ROUTES))
                    atomic(POLICY, policy_bytes, regular(POLICY))
                except Exception:
                    restored = False
            for name in reversed(changed):
                try:
                    atomic(DEST / name, originals[name], regular(DEST / name))
                except Exception:
                    restored = False
            if restarted or changed:
                try:
                    checked(['docker', 'restart', WEB], timeout=120)
                except Exception:
                    restored = False
            if restored:
                try:
                    prove_frozen(checker, policy)
                except Exception:
                    restored = False
            print(json.dumps({'published': False, 'code_route_policy_restored': restored,
                              'backup': str(backup), 'database_restored': False}, ensure_ascii=False))
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source_root', type=Path)
    args = parser.parse_args()
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(InterruptedError('Interrupted')))
    run(args.source_root.resolve(strict=True))


if __name__ == '__main__':
    try:
        main()
    except BaseException as error:
        print(json.dumps({'published': False, 'error_type': type(error).__name__}))
        raise SystemExit(1)
