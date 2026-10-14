"""Owner-authorized network/HBA step. Runs on the VPS; never prints credentials."""
import datetime
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import subprocess
import time


def run(args, data=None):
    p = subprocess.run(args, input=data, capture_output=True, text=True, timeout=45)
    if p.returncode:
        raise RuntimeError('operation failed: ' + args[0])
    return p.stdout


PG = ['docker', 'exec', '-i', 'plataforma-postgres-1']
SQL = PG + ['psql', '-U', 'postgres', '-d', 'postgres', '-XAt', '-v', 'ON_ERROR_STOP=1', '-c']
ROOT = Path('/opt/plataforma')
HBA = '/var/lib/postgresql/data/pg_hba.conf'
BLOCK = '''# BEGIN REVISOR OWNER AUTHORIZED 20261014
host revisor revisor 172.16.2.250/32 scram-sha-256
host all all 172.16.2.250/32 reject
host replication all 172.16.2.250/32 reject
host revisor revisor 127.0.0.1/32 scram-sha-256
host revisor revisor ::1/128 scram-sha-256
local all revisor reject
local replication revisor reject
host all revisor 0.0.0.0/0 reject
host all revisor ::/0 reject
host replication revisor 0.0.0.0/0 reject
host replication revisor ::/0 reject
# END REVISOR OWNER AUTHORIZED 20261014
'''


def main():
    os.umask(0o077)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = ROOT / 'backups-de-codigo' / ('revisor-rede-' + stamp)
    backup.mkdir(mode=0o700)
    original = run(PG + ['cat', HBA])
    assert 'BEGIN REVISOR' not in original, 'already applied; inspect existing result'
    (backup / 'pg_hba.conf').write_text(original)
    routes = json.loads(run(['ip', '-j', 'route']))
    nets = json.loads(run(['docker', 'network', 'inspect'] + run(['docker', 'network', 'ls', '-q']).split()))
    (backup / 'networks.json').write_text(json.dumps(nets))
    (backup / 'routes.json').write_text(json.dumps(routes))
    target = ipaddress.ip_network('172.16.20.0/24')
    assert not any(target.overlaps(ipaddress.ip_network(r['dst'])) for r in routes if r.get('dst') not in ('default', None))
    assert not any(target.overlaps(ipaddress.ip_network(c['Subnet'])) for n in nets for c in (n['IPAM'].get('Config') or []) if c.get('Subnet'))
    protected = ['docker-compose.yml', '.env', 'env/checkout.env', 'env/pagamentos.env', 'traefik/dynamic/plataforma.yml']
    hashes = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in protected}
    (backup / 'protected-hashes.json').write_text(json.dumps(hashes))
    # Backup is complete and checksum recorded before mutation.
    (backup / 'hba.sha256').write_text(hashlib.sha256(original.encode()).hexdigest())
    candidate = BLOCK + original
    run(PG + ['sh', '-c', 'cat > "$1"', 'sh', HBA], candidate)
    if run(SQL + ['SELECT count(*) FROM pg_hba_file_rules WHERE error IS NOT NULL']).strip() != '0':
        run(PG + ['sh', '-c', 'cat > "$1"', 'sh', HBA], original)
        raise RuntimeError('invalid HBA; original restored before reload')
    assert run(SQL + ['SELECT pg_reload_conf()']).strip() == 't'
    run(SQL + ["SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE usename='revisor' AND pid<>pg_backend_pid()"])
    time.sleep(1)
    secret = json.loads((ROOT / 'revisor-private/database.json').read_text())['password']
    def login(database, password, host='127.0.0.1'):
        args = PG + ['sh', '-c', 'IFS= read -r PGPASSWORD; export PGPASSWORD; exec psql -h "$1" -U revisor -d "$2" -XAtc "SELECT current_user,current_database()"', 'sh', host, database]
        p = subprocess.run(args, input=password + '\n', capture_output=True, text=True, timeout=15)
        return p.returncode, p.stdout.strip(), p.stderr
    good = login('revisor', secret)
    bad = login('revisor', 'deliberately-incorrect-revisor-proof')
    denied = login('test_praticas_3d_20261006', secret)
    outside = login('revisor', secret, '172.16.2.4')
    proofs = {'own_database_password_ok': good[:2] == (0, 'revisor|revisor'),
              'wrong_password_rejected': bad[0] != 0 and 'password authentication failed' in bad[2],
              'other_database_rejected_before_session': denied[0] != 0 and 'pg_hba.conf rejects connection' in denied[2],
              'outside_relay_rejected': outside[0] != 0 and 'pg_hba.conf rejects connection' in outside[2]}
    if not all(proofs.values()):
        run(SQL + ['ALTER ROLE revisor NOLOGIN'])
        (backup / 'failure.json').write_text(json.dumps(proofs))
        raise RuntimeError('proof failed: revisor login disabled; HBA retained')
    run(['docker', 'network', 'create', '--internal', '--subnet', str(target), '--opt', 'com.docker.network.bridge.name=br-revisor', '--label', 'meshcraft.owner=revisor', 'meshcraft-revisor'])
    network = json.loads(run(['docker', 'network', 'inspect', 'meshcraft-revisor']))[0]
    proofs['network_internal'] = network['Internal'] is True
    proofs['protected_files_unchanged'] = all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest() == h for p,h in hashes.items())
    result = {'backup': str(backup), 'proofs': proofs, 'http_pairs': 'pending', 'ai_egress': 'closed', 'public_route': 'not_created', 'disclosure': 'pending'}
    (backup / 'result.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
