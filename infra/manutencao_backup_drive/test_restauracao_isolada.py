import json
import os
from pathlib import Path
import tempfile
import time
import unittest
import uuid

import testar_restauracao_isolada as restore


class FilesAndCounts(unittest.TestCase):
    def manifest(self):
        names = [f'base_{i}-{restore.TAG}.dump' for i in range(19)]
        names += [restore.TAG + '.contagens.tsv', 'papeis.sql', 'redis.rdb', 'sessao.tar.gz']
        return {'carimbo_utc': restore.TAG, 'bases': 19,
                'arquivos': {name: {'bytes': 1, 'sha256': restore.sha(b'a')} for name in names}}

    def test_complete_manifest_and_missing_database(self):
        doc = self.manifest()
        self.assertEqual(len(restore.manifest_entries(json.dumps(doc))[1]), 19)
        doc['arquivos']['outro.bin'] = doc['arquivos'].pop(f'base_0-{restore.TAG}.dump')
        with self.assertRaisesRegex(RuntimeError, 'incompleto'):
            restore.manifest_entries(json.dumps(doc))

    def test_manifest_refuses_directory_escape(self):
        doc = self.manifest()
        doc['arquivos']['../exterior'] = doc['arquivos'].pop('papeis.sql')
        with self.assertRaisesRegex(RuntimeError, 'nome_de_arquivo'):
            restore.manifest_entries(json.dumps(doc))

    def test_corrupt_download_is_refused(self):
        # Somente dados ficticios criados pelo proprio teste.
        root = Path(tempfile.mkdtemp(prefix='meshcraft-ensaio-hash-'))
        (root / 'x').write_bytes(b'a')
        restore.verify_files(root, {'x': {'bytes': 1, 'sha256': restore.sha(b'a')}})
        (root / 'x').write_bytes(b'b')
        with self.assertRaisesRegex(RuntimeError, 'divergente'):
            restore.verify_files(root, {'x': {'bytes': 1, 'sha256': restore.sha(b'a')}})

    def test_count_file_preserves_all_databases_and_rejects_duplicates(self):
        self.assertEqual(restore.expected_counts(b'a\tpublic.t\t2\n', ['a','b']),
                         {'a': {'public.t': 2}, 'b': {}})
        with self.assertRaisesRegex(RuntimeError, 'duplicada'):
            restore.expected_counts(b'a\tpublic.t\t2\na\tpublic.t\t3\n', ['a'])

    def test_inventory_distinguishes_schema_from_data_and_ignores_owner(self):
        source = b'1; 1 1 TABLE public.t dono\n2; 1 2 TABLE DATA public.t dono\n3; 1 3 SEQUENCE SET public.s dono\n4; 1 4 SEQUENCE public.s dono\n'
        other = b'5; 1 5 TABLE public.t postgres\n6; 1 6 SEQUENCE public.s postgres\n'
        self.assertEqual(restore.inventory(source), restore.inventory(other))
        self.assertEqual(sum(restore.inventory(source).values()), 2)


@unittest.skipUnless(os.environ.get('TESTAR_POSTGRES_ISOLADO') == '1', 'PostgreSQL real opcional')
class PostgreSQLRoundtrip(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = Path(tempfile.mkdtemp(prefix='meshcraft-teste-restore-'))
        restore.LOGS = cls.folder / 'logs'
        restore.LOGS.mkdir()
        cls.container = 'meshcraft-teste-restore-' + uuid.uuid4().hex[:12]
        restore.run(['docker', 'run', '-d', '--pull', 'never', '--name', cls.container,
                     '--network', 'none', '--memory', '512m', '--cpus', '1',
                     '-e', 'POSTGRES_HOST_AUTH_METHOD=trust', 'postgres:17',
                     '-c', 'listen_addresses='])
        for _ in range(60):
            if restore.run(['docker', 'exec', cls.container, 'pg_isready', '-U', 'postgres'], check=False).returncode == 0:
                break
            time.sleep(1)
        else:
            restore.run(['docker', 'stop', cls.container], check=False)
            raise RuntimeError('postgres_teste_nao_iniciou')
        restore.sql(cls.container, 'postgres', 'CREATE DATABASE origem TEMPLATE template0')
        restore.sql(cls.container, 'origem', '''
            CREATE ROLE dono_ficticio NOLOGIN;
            CREATE TABLE public.pai (id bigserial PRIMARY KEY, nome text NOT NULL UNIQUE);
            CREATE TABLE public.filho (id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                pai_id bigint REFERENCES public.pai(id), valor integer CHECK (valor > 0));
            INSERT INTO public.pai(nome) VALUES ('ficticio um'), ('ficticio dois');
            INSERT INTO public.filho(pai_id,valor) VALUES (1,2),(2,3),(1,5);
            CREATE INDEX filho_valor ON public.filho(valor);
            CREATE VIEW public.total AS SELECT sum(valor) FROM public.filho;
            CREATE FUNCTION public.dobro(integer) RETURNS integer LANGUAGE sql AS 'SELECT $1 * 2';
            ALTER TABLE public.pai OWNER TO dono_ficticio;
        ''')
        cls.dump = cls.folder / 'origem.dump'
        cls.dump.write_bytes(restore.run(['docker', 'exec', cls.container, 'pg_dump', '-U', 'postgres', '-d', 'origem', '-Fc']).stdout)

    @classmethod
    def tearDownClass(cls):
        # Nao remove nem o conteiner, nem o volume, nem os relatórios.
        restore.run(['docker', 'stop', '--time', '30', cls.container])
        print(json.dumps({'teste_postgresql': cls.container, 'dados_e_relatorios_preservados': str(cls.folder)}))

    def test_actual_restore_tables_constraints_functions_and_sequences(self):
        report = restore.restore_database(self.container, 'destino', self.dump, {'public.pai': 2, 'public.filho': 3})
        self.assertEqual(report['tabelas_com_contagem_diferente'], 0)
        self.assertEqual(report['divergencias_esquema'], 0)
        self.assertEqual(report['indices_invalidos'], 0)
        self.assertEqual(report['linhas'], 5)
        self.assertEqual(report['sequencias_restauradas'], 2)
        self.assertEqual(restore.sql(self.container, 'destino', "SELECT nextval('public.pai_id_seq')").strip(), b'3')
        self.assertEqual(restore.sql(self.container, 'destino', "SELECT public.dobro(4)").strip(), b'8')

    def test_count_difference_is_reported(self):
        report = restore.restore_database(self.container, 'divergente', self.dump, {'public.pai': 99, 'public.filho': 3})
        self.assertEqual(report['tabelas_com_contagem_diferente'], 1)
        self.assertEqual(report['divergencias_esquema'], 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)