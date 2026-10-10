#!/usr/bin/env python3
"""Inventário por padrão; aplicação local pontual, somente por root --aplicar PACOTE.

PACOTE/manifest.json: {"arquivos":[{"alvo":"publicador/infra/...",
"antes":"sha256 ou null", "depois":"sha256", "origem":"fontes/..."}]}.
Sem SSH, credenciais, alteração da política Mercado Pago, banco ou fila.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import time
from datetime import datetime, timezone

PUB = Path('/usr/local/lib/meshcraft-publicador')
ATUAL = PUB / 'atual'
INT = Path('/usr/local/lib/meshcraft-integrador')
ACESSOS = Path('/usr/local/lib/meshcraft-acessos')
ROOT = Path('/opt/plataforma')
BACKUP_ROOT = ROOT / 'backups-de-codigo'
QUEUE = Path('/var/lib/meshcraft-integrador/entregas')
POL = PUB / 'v1-20261006T184415Z/mercadopago/politica.json'
VER = PUB / 'v1-20261006T184415Z/infra/mercadopago_congelado.py'
UNITS = ('meshcraft-integrador.service', 'meshcraft-entregas-publicador.service',
         'meshcraft-entregas-publicador.socket', 'meshcraft-robo.service', 'meshcraft-robo.socket')
SHA = re.compile(r'[0-9a-f]{64}\Z')
ALVOS = {
    'wrapper',
    'publicador/infra/publicar.py', 'publicador/infra/ponte_entregas.py',
    'publicador/infra/diagnostico_entregas.py', 'publicador/infra/ensaio_entregas.py',
    'integrador/integrador_servico.py', 'integrador/ponte_entregas.py',
    'integrador/diagnostico_entregas.py',
    'acessos/robo_broker.py', 'acessos/robo_comando.py',
}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def run(*args: str, timeout: int = 120, check: bool = True, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(args, text=True, capture_output=True, timeout=timeout, check=check, env=env)


def regular(path: Path) -> bool:
    try:
        mode = path.lstat().st_mode
        return stat.S_ISREG(mode)
    except FileNotFoundError:
        return False


def required_hash(path: Path) -> str:
    if not regular(path):
        raise RuntimeError(f'arquivo ausente ou especial: {path}')
    return digest(path)


def anchor_hash(path: Path) -> str | None:
    if not path.exists() and not path.is_symlink():
        return None
    return required_hash(path)


def alvo_path(key: str, release: Path) -> Path:
    if key not in ALVOS:
        raise RuntimeError(f'alvo não permitido: {key}')
    if key == 'wrapper':
        return ROOT / 'bin/plataforma'
    part, rel = key.split('/', 1)
    return {'publicador': release, 'integrador': INT, 'acessos': ACESSOS}[part] / rel


def anchors(release: Path) -> list[Path]:
    fixed = POL.parents[1]
    return ([release / 'infra/publicar.py', release / 'infra/ponte_entregas.py',
             release / 'infra/diagnostico_entregas.py', release / 'infra/ensaio_entregas.py',
             release / 'infra/docs_somente_admin.py', release / 'docs/politica.json',
             release / 'infra/backup-do-banco.sh',
             release / 'infra/mercadopago_congelado.py',
             release / 'mercadopago/politica.json',
             INT / 'integrador_servico.py', INT / 'entregas.py',
             INT / 'ponte_entregas.py', INT / 'diagnostico_entregas.py',
             ACESSOS / 'robo_broker.py', ACESSOS / 'robo_comando.py',
             ROOT / 'bin/plataforma', POL, VER,
             fixed / 'infra/docs_somente_admin.py', fixed / 'docs/politica.json']
            + [Path('/etc/systemd/system') / unit for unit in UNITS])


def release_atual() -> Path:
    if not ATUAL.is_symlink():
        raise RuntimeError('ponteiro atual não é link simbólico')
    release = ATUAL.resolve(strict=True)
    if release.parent != PUB or not release.is_dir():
        raise RuntimeError('release atual fora da pasta esperada')
    return release


def rotas_hash() -> str:
    # A instalação do canal preserva os bytes da rota mesmo se ela já é recusada.
    # Não altera nem aprova a rota: o publicador continua usando o verificador fixado.
    return required_hash(ROOT / 'traefik/dynamic/plataforma.yml')


def rotas_diagnostico() -> dict:
    # Chama o verificador independente fixado no servidor; nunca imprime a rota.
    import importlib.util
    spec = importlib.util.spec_from_file_location('mp_congelado', VER)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    try:
        return {'estado': 'normalizacao concluida', 'sha256': mod.capturar_rotas(ROOT)}
    except mod.IntegridadeMercadoPagoErro:
        return {'estado': 'rota recusada pelo verificador congelado', 'sha256': None}


def inventory() -> dict:
    release = release_atual()
    policy = json.loads(POL.read_text(encoding='utf-8'))
    current_policy = release / 'mercadopago/politica.json'
    current_policy_data = json.loads(current_policy.read_text(encoding='utf-8'))
    units = {}
    for unit in UNITS:
        result = run('systemctl', 'show', unit, '--property=ActiveState,SubState,MainPID,ExecStart,User,Group',
                     check=False)
        # ExecStart pode conter caminhos; jamais inclui Environment ou credenciais.
        fields = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
        pid = fields.get('MainPID', '0')
        identity = None
        if pid.isdigit() and int(pid) > 0:
            try:
                status = (Path('/proc') / pid / 'status').read_text()
                identity = {key: re.search(rf'^{key}:\s*(.+)$', status, re.M).group(1)
                            for key in ('Name', 'Uid', 'Gid')}
            except (OSError, AttributeError):
                identity = {'indisponivel': True}
        exec_raw = fields.get('ExecStart', '')
        exec_script = next((p for p in ('/usr/local/lib/meshcraft-publicador/atual/infra/ponte_entregas.py',
                                        '/usr/local/lib/meshcraft-integrador/integrador_servico.py',
                                        '/usr/local/lib/meshcraft-acessos/robo_broker.py') if p in exec_raw), None)
        units[unit] = {'active': fields.get('ActiveState'), 'sub': fields.get('SubState'),
                       'exec_script': exec_script, 'user': fields.get('User'),
                       'group': fields.get('Group'), 'processo': identity}
    return {'release': str(release), 'arquivos': {str(p): anchor_hash(p) for p in anchors(release)},
            'rotas_sha256': rotas_hash(), 'rotas_hash_tipo': 'bytes integrais do arquivo',
            'rotas_diagnostico': rotas_diagnostico(),
            'politica_rotas_sha256': policy.get('rotas_sha256'),
            'politica_atual_rotas_sha256': current_policy_data.get('rotas_sha256'),
            'politica_atual_sha256': required_hash(current_policy),
            'units': units}


def manifest(path: Path, release: Path) -> list[dict]:
    data = json.loads((path / 'manifest.json').read_text(encoding='utf-8'))
    files = data.get('arquivos')
    if not isinstance(data.get('prova_id'), str) or not re.fullmatch(r'[0-9a-f]{12}', data['prova_id']):
        raise RuntimeError('prova_id de entrega conhecida ausente ou inválido')
    if not isinstance(files, list) or not files or any(not isinstance(i, dict) for i in files):
        raise RuntimeError('manifesto incompleto')
    if len({item.get('alvo') for item in files}) != len(files):
        raise RuntimeError('alvos duplicados')
    for item in files:
        key, before, after, source = (item.get(k) for k in ('alvo', 'antes', 'depois', 'origem'))
        current = alvo_path(key, release)
        if before is not None and not (isinstance(before, str) and SHA.fullmatch(before)):
            raise RuntimeError('hash anterior inválido')
        if not (isinstance(after, str) and SHA.fullmatch(after)):
            raise RuntimeError('hash novo inválido')
        if source != 'fontes/' + key or not regular(path / source):
            raise RuntimeError(f'fonte ausente ou caminho irregular: {key}')
        if digest(path / source) != after:
            raise RuntimeError(f'fonte difere do manifesto: {key}')
        if before is None:
            if current.exists() or current.is_symlink():
                raise RuntimeError(f'arquivo novo já existe: {key}')
        elif required_hash(current) != before:
            raise RuntimeError(f'base instalada difere: {key}')
    return files


def lock(path: Path, timeout: float = 1800):
    if not regular(path):
        raise RuntimeError(f'trava inválida: {path}')
    f = path.open('rb')
    deadline = time.monotonic() + timeout
    while True:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return f
        except BlockingIOError:
            if time.monotonic() >= deadline:
                f.close()
                raise RuntimeError(f'tarefa ainda em andamento: {path}')
            time.sleep(1)


def acquire_locks() -> None:
    for path in (QUEUE / 'fases/.worker.lock', QUEUE / '.integrador.lock',
                 ROOT / 'publicacoes/.ativacao.lock', ROOT / 'publicacoes/lotes/.lote.lock'):
        locks.append(lock(path))
    # O bit em_andamento pode sobreviver a uma falha; as travas são a prova de ociosidade.


def release_locks() -> None:
    while locks:
        fd = locks.pop()
        fcntl.flock(fd, fcntl.LOCK_UN)
        fd.close()


def stop_units() -> None:
    # As travas asseguram que worker e publicador não estão em operação.
    errors = []
    for unit in ('meshcraft-robo.socket', 'meshcraft-entregas-publicador.socket',
                 'meshcraft-integrador.service', 'meshcraft-robo.service',
                 'meshcraft-entregas-publicador.service'):
        try:
            run('systemctl', 'stop', unit, timeout=180)
        except (OSError, subprocess.SubprocessError):
            errors.append(unit)
    for unit in UNITS:
        try:
            state = run('systemctl', 'is-active', unit, check=False).stdout.strip()
            if state not in {'inactive', 'failed'}:
                errors.append(unit)
        except (OSError, subprocess.SubprocessError):
            errors.append(unit)
    if errors:
        raise RuntimeError('parada não comprovada: ' + ', '.join(dict.fromkeys(errors)))


def resume_units(active: set[str], *, restart: bool = False) -> None:
    errors = []
    for unit in ('meshcraft-entregas-publicador.socket', 'meshcraft-robo.socket',
                 'meshcraft-entregas-publicador.service', 'meshcraft-robo.service',
                 'meshcraft-integrador.service'):
        if unit in active:
            action = 'restart' if restart and unit.endswith('.service') else 'start'
        elif restart:
            action = 'stop'
        else:
            continue
        try:
            run('systemctl', action, unit, timeout=180)
        except (OSError, subprocess.SubprocessError):
            errors.append(unit)
    if restart:
        for unit in UNITS:
            try:
                state = run('systemctl', 'is-active', unit, check=False).stdout.strip()
                expected = {'active'} if unit in active else {'inactive', 'failed'}
                if state not in expected:
                    errors.append(unit)
            except (OSError, subprocess.SubprocessError):
                errors.append(unit)
    if errors:
        raise RuntimeError('retomada não comprovada: ' + ', '.join(dict.fromkeys(errors)))


def recover(original, new, changed_flat, initially_active, *, stopped, switched):
    """Tenta cada restauração independente; nunca restaura bancos ou fila."""
    errors = []
    if stopped and not locks:
        # Sem exclusão, não é seguro sobrescrever uma operação concorrente.
        try:
            acquire_locks()
        except Exception:
            release_locks()
            raise RuntimeError('recuperação incompleta: exclusão não obtida; '
                               'nenhum arquivo foi sobrescrito nem serviço retomado') from None
    try:
        if stopped:
            try:
                stop_units()
            except Exception:
                # As travas retidas impedem mutações. Ainda é possível restaurar
                # os arquivos e reiniciar os processos com o código anterior.
                print('RECUPERACAO: parada incompleta; prosseguindo sob as travas', file=sys.stderr)
        if switched:
            try:
                current = ATUAL.resolve()
                if current == new:
                    pointer = PUB / '.atual-canal-volta'
                    pointer.symlink_to(original.name)
                    os.replace(pointer, ATUAL)
                elif current != original:
                    errors.append('ponteiro alterado por outra operação')
            except Exception:
                errors.append('ponteiro não restaurado')
        for target, old, mode, installed_hash in reversed(changed_flat):
            try:
                if ((old is None and not target.exists() and not target.is_symlink())
                        or (old is not None and regular(target) and target.read_bytes() == old)):
                    continue
                if not regular(target) or digest(target) != installed_hash:
                    errors.append('arquivo alterado por outra operação: ' + target.name)
                    continue  # não sobrescrever trabalho posterior
                if old is None:
                    target.unlink()
                else:
                    temp = target.with_name(target.name + '.canal-volta')
                    temp.write_bytes(old)
                    os.chmod(temp, mode)
                    os.replace(temp, target)
            except Exception:
                errors.append('arquivo não restaurado: ' + target.name)
    finally:
        if stopped:
            try:
                # start seria inócuo se stop falhou e o processo novo segue vivo.
                # Ele também não pode iniciar outra rodada antes do restart.
                resume_units(initially_active, restart=True)
            except Exception:
                errors.append('serviços não retomados integralmente')
        try:
            release_locks()
        except Exception:
            errors.append('travas não liberadas integralmente')
    if errors:
        raise RuntimeError('recuperação incompleta: ' + '; '.join(errors))


def backup(release: Path, inv: dict) -> Path:
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    dest = BACKUP_ROOT / ('publicacao-estrutural-' + stamp)
    dest.mkdir(mode=0o700, parents=True, exist_ok=False)
    os.chmod(dest, 0o700)
    # O comando existente faz dump consistente das bases; nenhum banco é restaurado aqui.
    database_dir = dest / 'bancos'
    database_dir.mkdir(mode=0o700)
    backup_env = {**os.environ, 'PLATAFORMA_DIR': str(ROOT), 'PRESERVAR_COPIAS': '1',
                  'PASTA_DOS_BACKUPS': str(database_dir)}
    backup_env.pop('BASES', None)
    result = run('bash', str(release / 'infra/backup-do-banco.sh'), 'canal',
                 timeout=3600, env=backup_env)
    if 'BACKUP-CONCLUIDO:' not in result.stdout:
        raise RuntimeError('comando de backup não comprovou conclusão')
    dumps = sorted(database_dir.glob('*.dump'))
    if not dumps or any(not regular(p) or p.stat().st_size == 0 for p in dumps):
        raise RuntimeError('dump das bases ausente ou vazio')
    if not any(p.is_file() and p.stat().st_size > 0 for p in database_dir.glob('*.contagens.tsv')):
        raise RuntimeError('contagens das bases ausentes')
    if not any(p.is_file() and p.stat().st_size > 0 for p in database_dir.glob('papeis-*.sql')):
        raise RuntimeError('papéis das bases ausentes')
    paths = [(release, 'publicador-atual'), (INT, 'integrador'), (ACESSOS, 'acessos'),
             (ROOT / 'bin/plataforma', 'wrapper'),
             (QUEUE, 'fila-registros'),
             (ROOT / '.env', 'config/.env'), (ROOT / 'docker-compose.yml', 'config/docker-compose.yml'),
             (ROOT / 'traefik', 'config/traefik'), (POL, 'politica-mp'),
             (ROOT / 'protecao-celulas/topologia.json', 'config/topologia.json'),
             (ROOT / 'publicacoes/aplicacao.json', 'journals/aplicacao.json'),
             (ROOT / 'publicacoes/funil.json', 'journals/funil.json')]
    paths += [(Path('/etc/systemd/system') / unit, 'units/' + unit) for unit in UNITS]
    for name in ('config', 'configuracoes', 'env', 'env-celulas', 'protecao-celulas',
                 'secrets', 'segredos', 'privado', 'credenciais'):
        private_dir = ROOT / name
        if private_dir.is_dir() and not private_dir.is_symlink():
            paths.append((private_dir, 'config-privada/' + name))
    images = set()
    app_journal = json.loads((ROOT / 'publicacoes/aplicacao.json').read_text(encoding='utf-8'))
    topology = json.loads((ROOT / 'protecao-celulas/topologia.json').read_text(encoding='utf-8'))
    app_approved = app_journal.get('aprovada')
    funnel_approved = (topology.get('celulas') or {}).get('funil')
    for cell, approved in (('aplicacao', app_approved), ('funil', funnel_approved)):
        if not isinstance(approved, dict):
            raise RuntimeError(f'versão aprovada inválida: {cell}')
        code = approved.get('codigo')
        if not code:
            raise RuntimeError(f'código aprovado ausente: {cell}')
        if code:
            if not isinstance(code, str):
                raise RuntimeError(f'código aprovado inválido: {cell}')
            source = Path(code).resolve(strict=True)
            allowed = [ROOT / 'versoes', ROOT / 'ensaios']
            if not source.is_dir() or not any(source.is_relative_to(base.resolve()) for base in allowed):
                raise RuntimeError(f'código aprovado fora da plataforma: {cell}')
            paths.append((source, f'codigo-montado/{cell}'))
        package = approved.get('pacote') or {}
        cell_images = set()
        image = approved.get('imagem') or (package.get('imagem_id') if isinstance(package, dict) else None)
        if isinstance(image, str) and (re.fullmatch(r'sha256:[0-9a-f]{64}', image) or
                                       re.fullmatch(r'[a-zA-Z0-9_.-]+:[a-zA-Z0-9_.-]+', image)):
            cell_images.add(image)
        if not cell_images:
            raise RuntimeError(f'imagem aprovada inválida ou ausente: {cell}')
        images.update(cell_images)
    with tarfile.open(dest / 'estado-antes.tar.gz', 'w:gz') as tar:
        for source, name in paths:
            if not source.exists() and not source.is_symlink():
                if source in (ROOT / 'publicacoes/funil.json',):
                    continue
                raise RuntimeError(f'backup incompleto: {source}')
            tar.add(source, arcname=name, recursive=True)
    os.chmod(dest / 'estado-antes.tar.gz', 0o600)
    with tarfile.open(dest / 'estado-antes.tar.gz') as tar:
        if not tar.getmembers():
            raise RuntimeError('arquivo de backup vazio')
    (dest / 'inventario.json').write_text(json.dumps(inv, ensure_ascii=False, indent=2), encoding='utf-8')
    os.chmod(dest / 'inventario.json', 0o600)
    if not images:
        raise RuntimeError('journals não indicam imagem para backup')
    image_proof = {}
    for number, image in enumerate(sorted(images), 1):
        identity = run('docker', 'image', 'inspect', '--format', '{{.Id}}', image, timeout=120).stdout.strip()
        if not re.fullmatch(r'sha256:[0-9a-f]{64}', identity):
            raise RuntimeError('identidade Docker da imagem aprovada inválida')
        if image.startswith('sha256:') and identity != image:
            raise RuntimeError('imagem aprovada não corresponde ao Docker')
        image_path = dest / f'imagem-{number}.tar'
        run('docker', 'save', '-o', str(image_path), image, timeout=3600)
        os.chmod(image_path, 0o600)
        if not tarfile.is_tarfile(image_path):
            raise RuntimeError('imagem de backup inválida')
        with tarfile.open(image_path) as archive:
            if not archive.getmembers():
                raise RuntimeError('imagem de backup vazia')
            if image.startswith('sha256:'):
                try:
                    manifest_image = json.load(archive.extractfile('manifest.json'))
                    config = archive.extractfile(manifest_image[0]['Config']).read()
                    matches = 'sha256:' + hashlib.sha256(config).hexdigest() == image
                except (KeyError, IndexError, TypeError, json.JSONDecodeError, AttributeError):
                    matches = False
                if not matches:
                    blob = archive.extractfile('blobs/sha256/' + image.split(':', 1)[1])
                    matches = blob is not None and 'sha256:' + hashlib.sha256(blob.read()).hexdigest() == image
                if not matches:
                    raise RuntimeError('identidade da imagem salva diverge')
        image_proof[image] = digest(image_path)
    proof = {'arquivo_sha256': digest(dest / 'estado-antes.tar.gz'), 'imagens': image_proof,
             'dumps': {p.name: digest(p) for p in dumps}}
    (dest / 'prova.json').write_text(json.dumps(proof, sort_keys=True), encoding='utf-8')
    os.chmod(dest / 'prova.json', 0o600)
    return dest


def apply(package: Path) -> None:
    if os.geteuid() != 0 or sys.platform != 'linux':
        raise RuntimeError('aplicação exige administrador na VPS Linux')
    original = release_atual()
    before = inventory()
    wrapper = (ROOT / 'bin/plataforma').read_text(encoding='utf-8')
    for unit, script in (
        ('meshcraft-integrador.service', '/usr/local/lib/meshcraft-integrador/integrador_servico.py'),
        ('meshcraft-entregas-publicador.service', '/usr/local/lib/meshcraft-publicador/atual/infra/ponte_entregas.py'),
        ('meshcraft-robo.service', '/usr/local/lib/meshcraft-acessos/robo_broker.py'),
    ):
        if before['units'][unit]['exec_script'] != script:
            raise RuntimeError(f'ExecStart inesperado: {unit}')
    files = manifest(package, original)  # bytes dos alvos antes de qualquer escrita ativa
    proof_id = json.loads((package / 'manifest.json').read_text(encoding='utf-8'))['prova_id']
    if '/usr/local/lib/meshcraft-publicador/atual/infra/publicar.py' not in wrapper:
        replacements = [item for item in files if item['alvo'] == 'wrapper']
        old_literal = str(original / 'infra/publicar.py')
        if len(replacements) != 1 or old_literal not in wrapper or (
                package / replacements[0]['origem']).read_text(encoding='utf-8') != wrapper.replace(
                    old_literal, '/usr/local/lib/meshcraft-publicador/atual/infra/publicar.py'):
            raise RuntimeError('wrapper fixo exige substituição declarada apontando ao ponteiro atual')
    initially_active = {unit for unit in UNITS if before['units'][unit]['active'] == 'active'}
    new = PUB / ('v8-publicacao-estrutural-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    if new.exists() or new.is_symlink():
        raise RuntimeError('nome de release já existe')
    changed_flat = []
    switched = False
    stopped = False
    backup_dir = None
    try:
        print('ETAPA: aguardando termino da rodada atual', flush=True)
        acquire_locks()  # worker, integrador e publicador terminam a rodada em curso
        stopped = True
        stop_units()    # nenhuma tarefa é interrompida: travas já estão livres e retidas
        print('ETAPA: backup privado de codigo, configuracoes, bancos e imagens', flush=True)
        backup_dir = backup(original, before)
        print('BACKUP CONFERIDO: ' + str(backup_dir), flush=True)
        if release_atual() != original:
            raise RuntimeError('release atual mudou durante o backup')
        manifest(package, original)
        now = inventory()
        if now['arquivos'] != before['arquivos'] or now['rotas_sha256'] != before['rotas_sha256']:
            raise RuntimeError('arquivos ou rotas mudaram durante o backup')
        shutil.copytree(original, new, symlinks=True)
        print('ETAPA: instalando somente os arquivos declarados do canal', flush=True)
        for item in files:
            key = item['alvo']
            target = alvo_path(key, new if key.startswith('publicador/') else original)
            if target.is_symlink() or target.parent.is_symlink():
                raise RuntimeError(f'alvo simbólico inesperado: {key}')
            target.parent.mkdir(parents=True, exist_ok=True)
            if not key.startswith('publicador/'):
                changed_flat.append((target, target.read_bytes() if regular(target) else None,
                                     target.stat().st_mode & 0o777 if regular(target) else None,
                                     item['depois']))
            source = package / item['origem']
            temp = target.with_name(target.name + '.canal-novo')
            shutil.copy2(source, temp)
            os.chown(temp, 0, 0)
            os.chmod(temp, changed_flat[-1][2] if not key.startswith('publicador/')
                     and changed_flat[-1][2] is not None else 0o644)
            os.replace(temp, target)
            if digest(target) != item['depois']:
                raise RuntimeError(f'cópia divergente: {key}')
        # O manifesto jamais pode alterar política/verificador, mesmo dentro do clone.
        for rel in ('mercadopago/politica.json', 'infra/mercadopago_congelado.py'):
            if required_hash(new / rel) != required_hash(original / rel):
                raise RuntimeError(f'arquivo congelado mudou: {rel}')
        pointer = PUB / '.atual-canal-novo'
        pointer.symlink_to(new.name)
        os.replace(pointer, ATUAL)
        switched = True
        after = inventory()
        if after['rotas_sha256'] != before['rotas_sha256']:
            raise RuntimeError('rota protegida mudou')
        changed_keys = {str(alvo_path(item['alvo'], original)) for item in files}
        for old_path, expected_hash in before['arquivos'].items():
            if old_path in changed_keys:
                continue
            path = Path(old_path)
            if path.is_relative_to(original):
                path = new / path.relative_to(original)
            if anchor_hash(path) != expected_hash:
                raise RuntimeError(f'âncora não alterada divergiu: {old_path}')
        for item in files:
            target = alvo_path(item['alvo'], new)
            if required_hash(target) != item['depois']:
                raise RuntimeError(f'prova de instalação falhou: {item["alvo"]}')
        # consultar só lê registros. Manter as travas até terminar a prova e a
        # retomada evita disputar a exclusão com outra operação durante retorno.
        print('ETAPA: comprovando consulta como usuario robo', flush=True)
        run('systemctl', 'start', 'meshcraft-robo.socket')
        result = run('runuser', '-u', 'robo', '--', 'env', 'SSH_ORIGINAL_COMMAND=consultar ' + proof_id,
                     '/usr/bin/python3', str(ACESSOS / 'robo_comando.py'), timeout=180)
        answer = json.loads(result.stdout)
        if (not isinstance(answer, dict) or answer.get('id') != proof_id
                or not isinstance(answer.get('canal'), dict)
                or not isinstance(answer['canal'].get('estado'), str)
                or not isinstance(answer.get('operacao'), dict)):
            raise RuntimeError('consulta não comprovou canal e operação da entrega conhecida')
        if 'meshcraft-robo.service' not in initially_active:
            run('systemctl', 'stop', 'meshcraft-robo.service')
        resume_units(initially_active)
        if 'meshcraft-robo.socket' not in initially_active:
            run('systemctl', 'stop', 'meshcraft-robo.socket')
        print(json.dumps({'aplicado': True, 'backup_privado': str(backup_dir),
                          'release': str(new), 'rotas_sha256': after['rotas_sha256'],
                          'broker_sha256': required_hash(ACESSOS / 'robo_broker.py'),
                          'prova_id': proof_id, 'canal_estado': answer['canal']['estado'],
                          'operacao_estado': answer['operacao'].get('estado'),
                          'integrador_ativo': run('systemctl', 'is-active', 'meshcraft-integrador.service',
                                                  check=False).stdout.strip()},
                         ensure_ascii=False))
        release_locks()
    except Exception:
        recover(original, new, changed_flat, initially_active, stopped=stopped, switched=switched)
        raise


locks = []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--aplicar', type=Path, metavar='PACOTE')
    args = parser.parse_args()
    try:
        if args.aplicar:
            apply(args.aplicar.resolve())
        else:
            print(json.dumps(inventory(), ensure_ascii=False, indent=2))
        return 0
    except (RuntimeError, OSError, ValueError, KeyError, subprocess.CalledProcessError,
            subprocess.TimeoutExpired, json.JSONDecodeError) as error:
        print(json.dumps({'aplicado': False, 'erro': str(error)[:300]}, ensure_ascii=False), file=sys.stderr)
        return 2
    finally:
        release_locks()


if __name__ == '__main__':
    raise SystemExit(main())
