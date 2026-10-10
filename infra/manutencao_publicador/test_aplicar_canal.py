"""Ensaios isolados: nenhum systemctl, Docker ou caminho de produção é usado."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import tarfile
import types
import unittest
from unittest.mock import patch

sys.modules.setdefault('fcntl', types.SimpleNamespace(LOCK_EX=2, LOCK_NB=4, LOCK_UN=8,
                                                       flock=lambda *_: None))
SPEC = importlib.util.spec_from_file_location('canal', Path(__file__).with_name('aplicar_canal.py'))
canal = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(canal)


def sha(content):
    return hashlib.sha256(content).hexdigest()


class AplicarCanalTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.pub = base / 'publicador'
        self.pub.mkdir()
        self.original = self.pub / 'v6-original'
        (self.original / 'infra').mkdir(parents=True)
        (self.original / 'mercadopago').mkdir()
        (self.original / 'infra/publicar.py').write_bytes(b'publicador')
        (self.original / 'infra/mercadopago_congelado.py').write_bytes(b'verificador')
        (self.original / 'mercadopago/politica.json').write_bytes(b'politica')
        self.integrador = base / 'integrador'
        self.integrador.mkdir()
        self.queue = base / 'fila'
        self.queue.mkdir()
        self.target = self.integrador / 'integrador_servico.py'
        self.target.write_bytes(b'antigo')
        self.acessos = base / 'acessos'
        self.acessos.mkdir()
        (self.acessos / 'robo_broker.py').write_bytes(b'broker')
        self.root = base / 'plataforma'
        (self.root / 'bin').mkdir(parents=True)
        (self.root / 'bin/plataforma').write_text(
            'PUBLICADOR=/usr/local/lib/meshcraft-publicador/atual/infra/publicar.py')
        self.package = base / 'pacote'
        source = self.package / 'fontes/integrador/integrador_servico.py'
        source.parent.mkdir(parents=True)
        source.write_bytes(b'novo')
        (self.package / 'manifest.json').write_text(json.dumps({'prova_id': '481e4c9fc2bb', 'arquivos': [{
            'alvo': 'integrador/integrador_servico.py', 'antes': sha(b'antigo'),
            'depois': sha(b'novo'), 'origem': 'fontes/integrador/integrador_servico.py'}]}))
        self.pointer = {'current': self.original}
        self.events = []
        self.original_replace = canal.os.replace
        self.original_resolve = Path.resolve
        self.original_symlink_to = Path.symlink_to

    def fake_replace(self, source, target):
        if Path(target) == self.pub / 'atual':
            self.pointer['current'] = self.pub / Path(source).read_text()
            Path(source).unlink()
        else:
            self.original_replace(source, target)

    def fake_resolve(self, path, *args, **kwargs):
        if path == self.pub / 'atual':
            return self.pointer['current']
        return self.original_resolve(path, *args, **kwargs)

    def fake_run(self, *args, **kwargs):
        if args[0] == 'runuser':
            return types.SimpleNamespace(stdout=self.broker_answer)
        if args[:2] == ('systemctl', 'is-active'):
            return types.SimpleNamespace(stdout='active\n')
        return types.SimpleNamespace(stdout='')

    def fake_resume(self, active, *, restart=False):
        self.events.append(('resume', active))
        if restart:
            self.events.append('restart')
        if getattr(self, 'fail_start_worker', False):
            self.fail_start_worker = False
            raise RuntimeError('worker não iniciou')

    def fake_inventory(self):
        return {'arquivos': {str(self.original / 'infra/publicar.py'): sha(b'publicador')},
                'rotas_sha256': sha(b'rota'), 'politica_rotas_sha256': sha(b'outra-rota'),
                'units': {
                    'meshcraft-integrador.service': {'active': 'active', 'exec_script':
                        '/usr/local/lib/meshcraft-integrador/integrador_servico.py'},
                    'meshcraft-entregas-publicador.service': {'active': 'inactive', 'exec_script':
                        '/usr/local/lib/meshcraft-publicador/atual/infra/ponte_entregas.py'},
                    'meshcraft-robo.service': {'active': 'inactive', 'exec_script':
                        '/usr/local/lib/meshcraft-acessos/robo_broker.py'},
                    'meshcraft-robo.socket': {'active': 'active'},
                    'meshcraft-entregas-publicador.socket': {'active': 'active'},
                }}

    def patches(self):
        return [patch.object(canal, name, value) for name, value in {
            'PUB': self.pub, 'ATUAL': self.pub / 'atual', 'INT': self.integrador,
            'ACESSOS': self.acessos, 'ROOT': self.root,
            'release_atual': lambda: self.pointer['current'],
            'inventory': self.fake_inventory,
            'backup': lambda *_: self.root / 'backup',
            'acquire_locks': lambda: self.events.append('lock'),
            'release_locks': lambda: self.events.append('unlock'),
            'stop_units': lambda: self.events.append('stop'),
            'resume_units': self.fake_resume,
            'run': self.fake_run,
        }.items()] + [
            patch.object(canal.os, 'geteuid', lambda: 0, create=True),
            patch.object(canal.os, 'chown', lambda *_: None, create=True),
            patch.object(canal.sys, 'platform', 'linux'),
            patch.object(canal.os, 'replace', self.fake_replace),
            patch.object(Path, 'resolve', lambda path, *args, **kwargs: self.fake_resolve(path, *args, **kwargs)),
            patch.object(Path, 'symlink_to', lambda path, target: path.write_text(str(target))),
        ]

    def run_apply(self):
        patches = self.patches()
        for item in patches:
            item.start()
        try:
            canal.apply(self.package)
        finally:
            for item in reversed(patches):
                item.stop()

    def test_aplica_e_retorna_servicos_anteriores(self):
        self.broker_answer = json.dumps({'id': '481e4c9fc2bb', 'canal': {'estado': 'acompanhamento recente'},
                                         'operacao': {'estado': 'registro histórico'}})
        self.run_apply()
        self.assertEqual(self.target.read_bytes(), b'novo')
        self.assertNotEqual(self.pointer['current'], self.original)
        self.assertIn('stop', self.events)
        self.assertIn(('resume', {'meshcraft-integrador.service', 'meshcraft-robo.socket',
                                   'meshcraft-entregas-publicador.socket'}), self.events)

    def test_falha_broker_volta_codigo_e_servicos(self):
        self.broker_answer = 'invalido'
        with self.assertRaises(json.JSONDecodeError):
            self.run_apply()
        self.assertEqual(self.target.read_bytes(), b'antigo')
        self.assertEqual(self.pointer['current'], self.original)
        self.assertTrue(any(isinstance(item, tuple) and item[0] == 'resume' for item in self.events))

    def test_falha_ao_retomar_worker_tambem_volta(self):
        self.broker_answer = json.dumps({'id': '481e4c9fc2bb', 'canal': {'estado': 'acompanhamento recente'},
                                         'operacao': {'estado': 'registro histórico'}})
        self.fail_start_worker = True
        with self.assertRaisesRegex(RuntimeError, 'worker não iniciou'):
            self.run_apply()
        self.assertEqual(self.target.read_bytes(), b'antigo')
        self.assertEqual(self.pointer['current'], self.original)
        self.assertGreaterEqual(self.events.count('stop'), 2)

    def test_falha_parada_no_retorno_nao_interrompe_restauracao(self):
        self.broker_answer = 'invalido'
        calls = []

        def stopping():
            calls.append('stop')
            if len(calls) == 2:
                raise RuntimeError('parada indisponivel')

        patches = self.patches()
        for item in patches:
            item.start()
        try:
            with patch.object(canal, 'stop_units', stopping):
                with self.assertRaises(json.JSONDecodeError):
                    canal.apply(self.package)
        finally:
            for item in reversed(patches):
                item.stop()
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.target.read_bytes(), b'antigo')
        self.assertEqual(self.pointer['current'], self.original)
        self.assertIn('restart', self.events)
        self.assertLess(self.events.index('restart'), self.events.index('unlock'))
        self.assertTrue(any(isinstance(e, tuple) and e[0] == 'resume' for e in self.events))

    def test_consulta_e_retomada_mantem_exclusao_ate_concluir(self):
        self.broker_answer = json.dumps({'id': '481e4c9fc2bb', 'canal': {'estado': 'recente'},
                                        'operacao': {'estado': 'registro histórico'}})
        held = {'value': False}
        observations = []

        def run(*args, **kwargs):
            if args[0] == 'runuser':
                observations.append(('consulta', held['value']))
            return self.fake_run(*args, **kwargs)

        def resume(active, *, restart=False):
            observations.append(('retomada', held['value']))

        patches = self.patches()
        for item in patches:
            item.start()
        try:
            with patch.object(canal, 'run', run), \
                    patch.object(canal, 'resume_units', resume), \
                    patch.object(canal, 'acquire_locks', lambda: held.update(value=True)), \
                    patch.object(canal, 'release_locks', lambda: held.update(value=False)):
                canal.apply(self.package)
        finally:
            for item in reversed(patches):
                item.stop()
        self.assertEqual(observations, [('consulta', True), ('retomada', True)])
        self.assertFalse(held['value'])

    def test_exclusao_indisponivel_nao_sobrescreve_outra_operacao(self):
        self.target.write_bytes(b'novo')
        with patch.object(canal, 'locks', []), \
                patch.object(canal, 'acquire_locks', side_effect=RuntimeError('ocupado')), \
                patch.object(canal, 'release_locks') as release, \
                patch.object(canal, 'resume_units') as resume:
            with self.assertRaisesRegex(RuntimeError, 'recuperação incompleta: exclusão não obtida'):
                canal.recover(self.original, self.pub / 'nova',
                    [(self.target, b'antigo', 0o644, sha(b'novo'))], set(),
                    stopped=True, switched=False)
        self.assertEqual(self.target.read_bytes(), b'novo')
        release.assert_called_once()
        resume.assert_not_called()

    def test_parada_tenta_todas_unidades_apos_falha(self):
        calls = []

        def run(*args, **kwargs):
            calls.append(args)
            if args[:2] == ('systemctl', 'stop') and args[2] == 'meshcraft-robo.socket':
                raise canal.subprocess.CalledProcessError(1, args)
            return types.SimpleNamespace(stdout='inactive\n')

        with patch.object(canal, 'run', run):
            with self.assertRaisesRegex(RuntimeError, 'parada não comprovada'):
                canal.stop_units()
        self.assertEqual({c[2] for c in calls if c[1] == 'stop'}, set(canal.UNITS))
        self.assertEqual(len([c for c in calls if c[1] == 'is-active']), len(canal.UNITS))

    def test_retomada_reinicia_processos_e_para_os_antes_inativos(self):
        active = {'meshcraft-robo.socket', 'meshcraft-integrador.service'}
        calls = []

        def run(*args, **kwargs):
            calls.append(args)
            return types.SimpleNamespace(stdout='active\n' if args[2] in active else 'inactive\n')

        with patch.object(canal, 'run', run):
            canal.resume_units(active, restart=True)
        self.assertIn(('systemctl', 'restart', 'meshcraft-integrador.service'), calls)
        self.assertIn(('systemctl', 'start', 'meshcraft-robo.socket'), calls)
        self.assertIn(('systemctl', 'stop', 'meshcraft-robo.service'), calls)

    def test_retomada_tenta_outros_servicos_e_informa_falha_persistente(self):
        calls = []

        def run(*args, **kwargs):
            calls.append(args)
            if args[:2] == ('systemctl', 'restart') and args[2] == 'meshcraft-robo.service':
                raise canal.subprocess.TimeoutExpired(args, 180)
            return types.SimpleNamespace(stdout='active\n')

        with patch.object(canal, 'run', run):
            with self.assertRaisesRegex(RuntimeError, 'retomada não comprovada'):
                canal.resume_units(set(canal.UNITS), restart=True)
        self.assertIn(('systemctl', 'restart', 'meshcraft-integrador.service'), calls)

    def test_recuperacao_preserva_arquivo_alterado_por_outra_operacao(self):
        self.target.write_bytes(b'posterior')
        with patch.object(canal, 'release_locks', lambda: None):
            with self.assertRaisesRegex(RuntimeError, 'arquivo alterado por outra operação'):
                canal.recover(self.original, self.pub / 'nova',
                    [(self.target, b'antigo', 0o644, sha(b'novo'))], set(),
                    stopped=False, switched=False)
        self.assertEqual(self.target.read_bytes(), b'posterior')

    def test_falha_em_um_arquivo_nao_impede_outro_retorno_e_servicos(self):
        first = self.integrador / 'primeiro.py'
        first.write_bytes(b'novo')
        self.target.write_bytes(b'novo')

        def replace(source, target):
            if Path(target) == self.target:
                raise OSError('erro de escrita simulado')
            self.original_replace(source, target)

        with patch.object(canal, 'acquire_locks', lambda: None), \
                patch.object(canal, 'release_locks', lambda: self.events.append('unlock')), \
                patch.object(canal, 'stop_units', lambda: None), \
                patch.object(canal, 'resume_units', self.fake_resume), \
                patch.object(canal.os, 'replace', replace):
            with self.assertRaisesRegex(RuntimeError, 'recuperação incompleta'):
                canal.recover(self.original, self.pub / 'nova',
                    [(first, b'antigo1', 0o644, sha(b'novo')),
                     (self.target, b'antigo', 0o644, sha(b'novo'))], set(),
                    stopped=True, switched=False)
        self.assertEqual(first.read_bytes(), b'antigo1')
        self.assertEqual(self.target.read_bytes(), b'novo')
        self.assertIn('restart', self.events)

    def test_base_divergente_recusa_antes_de_trocar(self):
        self.target.write_bytes(b'diferente')
        with self.assertRaises(RuntimeError):
            canal.manifest(self.package, self.original)
        self.assertEqual(self.pointer['current'], self.original)

    def test_hash_rotas_preserva_bytes_mesmo_se_normalizacao_recusa(self):
        route = self.root / 'traefik/dynamic/plataforma.yml'
        route.parent.mkdir(parents=True)
        route.write_bytes(b'http://meshcraft-funil-af3c21fc4d40-ensaio:8000\r\n')
        with patch.object(canal, 'ROOT', self.root):
            before = canal.rotas_hash()
            self.assertEqual(before, sha(route.read_bytes()))
            route.write_bytes(route.read_bytes().replace(b'\r\n', b'\n'))
            self.assertNotEqual(canal.rotas_hash(), before)

    def test_diagnostico_recusa_rota_sem_alterar_verificador(self):
        verifier = self.root / 'verificador.py'
        verifier.write_text('class IntegridadeMercadoPagoErro(RuntimeError): pass\n'
                            'def capturar_rotas(root):\n'
                            '    raise IntegridadeMercadoPagoErro("detalhe privado")\n')
        with patch.object(canal, 'VER', verifier):
            result = canal.rotas_diagnostico()
        self.assertIsNone(result['sha256'])
        self.assertEqual(result['estado'], 'rota recusada pelo verificador congelado')
        self.assertNotIn('privado', str(result))

    def test_backup_inclui_codigo_montado_bases_e_imagem_aprovada(self):
        image = 'sha256:' + sha(b'{}')
        app_code = self.root / 'versoes/aplicacao/abc'
        fun_code = self.root / 'ensaios/saida/funil/codigo'
        app_code.mkdir(parents=True)
        fun_code.mkdir(parents=True)
        (app_code / 'app.py').write_text('app')
        (fun_code / 'funil.py').write_text('funil')
        (self.root / 'publicacoes').mkdir()
        (self.root / 'protecao-celulas').mkdir()
        (self.root / 'traefik').mkdir()
        (self.root / '.env').write_text('privado')
        (self.root / 'docker-compose.yml').write_text('compose')
        (self.root / 'publicacoes/aplicacao.json').write_text(json.dumps({
            'aprovada': {'codigo': str(app_code), 'imagem': image}}))
        (self.root / 'publicacoes/funil.json').write_text('{}')
        (self.root / 'protecao-celulas/topologia.json').write_text(json.dumps({
            'celulas': {'funil': {'codigo': str(fun_code), 'pacote': {'imagem_id': image}}}}))
        def fake_backup_run(*args, **kwargs):
            if args[0] == 'bash':
                database_dir = Path(kwargs['env']['PASTA_DOS_BACKUPS'])
                (database_dir / 'site-canal.dump').write_bytes(b'dump')
                (database_dir / 'canal.contagens.tsv').write_bytes(b'1\n')
                (database_dir / 'papeis-canal.sql').write_bytes(b'roles')
                return types.SimpleNamespace(stdout='BACKUP-CONCLUIDO: canal 1 bases')
            if args[:3] == ('docker', 'image', 'inspect'):
                return types.SimpleNamespace(stdout=image + '\n')
            if args[:2] == ('docker', 'save'):
                output = Path(args[args.index('-o') + 1])
                with tarfile.open(output, 'w') as archive:
                    for name, content in (('config.json', b'{}'),
                                          ('manifest.json', b'[{"Config":"config.json"}]')):
                        info = tarfile.TarInfo(name)
                        info.size = len(content)
                        archive.addfile(info, io.BytesIO(content))
            return types.SimpleNamespace(stdout='')
        with patch.multiple(canal, ROOT=self.root, BACKUP_ROOT=self.root / 'backups-de-codigo',
                            INT=self.integrador, ACESSOS=self.acessos, QUEUE=self.queue,
                            POL=self.original / 'mercadopago/politica.json', UNITS=()), \
                patch.object(canal, 'run', fake_backup_run), \
                patch.object(Path, 'resolve', lambda path, *_, **__: path.absolute()):
            destination = canal.backup(self.original, {'teste': True})
        self.assertTrue((destination / 'bancos/site-canal.dump').is_file())
        self.assertTrue((destination / 'prova.json').is_file())
        with tarfile.open(destination / 'estado-antes.tar.gz') as archive:
            names = archive.getnames()
        self.assertIn('codigo-montado/aplicacao/app.py', names)
        self.assertIn('codigo-montado/funil/funil.py', names)
        self.assertIn('config/topologia.json', names)


if __name__ == '__main__':
    unittest.main()
