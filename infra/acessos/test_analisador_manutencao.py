import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

if sys.platform == 'win32':
    sys.modules.setdefault('fcntl', types.SimpleNamespace(LOCK_EX=2, LOCK_NB=4, LOCK_UN=8, flock=lambda *a: None))
    sys.modules.setdefault('pwd', types.SimpleNamespace(getpwnam=lambda _: types.SimpleNamespace(pw_uid=1001, pw_gid=1001)))

spec = importlib.util.spec_from_file_location('manutencao', Path(__file__).with_name('analisador_manutencao.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
if sys.platform == 'win32':
    m.socket.SO_PEERCRED = 17
import robo_broker as broker
import robo_comando as comando


class Conn:
    def __init__(self, value, uid=1001):
        self.raw = json.dumps(value).encode() + b'\n'
        self.uid = uid

    def getsockopt(self, *_):
        return m.struct.pack('3i', 1, self.uid, 1)

    def recv(self, size):
        result, self.raw = self.raw[:size], self.raw[size:]
        return result


class TestCanal(unittest.TestCase):
    def setUp(self):
        p = patch.object(m.pwd, 'getpwnam', return_value=types.SimpleNamespace(pw_uid=1001, pw_gid=1001))
        p.start()
        self.addCleanup(p.stop)

    def test_recusa_comando_caminho_ou_imagem_do_cliente(self):
        for args in [['analisador'], ['analisador', 'shell'], ['analisador', 'recuperar', '/tmp/x'],
                     ['analisador', 'recuperar; id'], ['analisador', '--imagem=x']]:
            self.assertFalse(broker.validar_args(args))
        for action in m.ACOES:
            self.assertTrue(broker.validar_args(['analisador', action]))

    def test_comando_forcado_recusa_antes_do_socket(self):
        for raw in ['analisador recuperar /etc/passwd', 'analisador recuperar;id', 'analisador shell']:
            with patch.dict(os.environ, SSH_ORIGINAL_COMMAND=raw), patch.object(comando.socket, 'socket') as s:
                with self.assertRaises(comando.ComandoRecusado):
                    comando.principal()
                s.assert_not_called()

    def test_ponte_so_aceita_uid_integrador(self):
        with patch.object(m.pwd, 'getpwnam', return_value=types.SimpleNamespace(pw_uid=1001)):
            with self.assertRaises(m.Falha):
                m.atender(Conn(['consultar'], uid=1002))

    def test_ponte_recusa_argumentos_sem_efeito(self):
        with patch.object(m, 'iniciar') as start, patch.object(m, 'consultar') as read:
            for args in [[], ['shell'], ['recuperar', '/tmp/a'], {'acao': 'recuperar'}, ['x' * 400]]:
                with self.assertRaises(m.Falha):
                    m.atender(Conn(args))
            start.assert_not_called()
            read.assert_not_called()

    def test_registro_com_tipo_invalido_nao_e_aceito(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'estado.json'
            for value in ([], None, 'texto', 7):
                p.write_text(json.dumps(value))
                with self.assertRaises(m.Falha):
                    m.ler(p)

    def test_fila_com_registro_invalido_continua_consultavel(self):
        with tempfile.TemporaryDirectory() as d, patch.object(m, 'QUEUE', Path(d)):
            job = Path(d) / ('a' * 64)
            job.mkdir()
            (job / 'pedido.json').write_text('{}')
            (job / 'estado.json').write_text('[]')
            self.assertEqual(m.contagens()['ilegivel'], 1)

    def test_consulta_nao_inicia_manutencao(self):
        with patch.object(m, 'consultar', return_value={'estado': 'disponivel'}), patch.object(m, 'iniciar') as start:
            self.assertEqual(m.atender(Conn(['consultar'])), {'estado': 'disponivel'})
            start.assert_not_called()

    def test_repeticao_em_execucao_reutiliza_id(self):
        with tempfile.TemporaryDirectory() as d, patch.object(m, 'STATE', Path(d)):
            current = {'id': 'a' * 32, 'estado': 'executando', 'acao': 'recuperar'}
            with patch.object(m, 'consultar', return_value={'ultima_operacao': current}), patch.object(m, 'run') as run:
                result = m.iniciar('recuperar')
                self.assertTrue(result['reutilizado'])
                self.assertEqual(result['operacao']['id'], current['id'])
                run.assert_not_called()

    def test_estado_persistido_antes_da_execucao(self):
        with tempfile.TemporaryDirectory() as d, patch.object(m, 'STATE', Path(d)):
            def running(args, **kw):
                self.assertEqual(m.ler(Path(d) / 'operacao.json')['estado'], 'recebida')
                self.assertEqual(args, ['/usr/bin/systemctl', 'start', '--no-block', m.UNIT])
                return types.SimpleNamespace(returncode=0)
            with patch.object(m, 'consultar', return_value={'ultima_operacao': None}), patch.object(m, 'run', side_effect=running):
                result = m.iniciar('diagnosticar')
                self.assertTrue(m.HEX.fullmatch(result['operacao']['id']))

    def test_falha_de_inicio_fica_visivel(self):
        with tempfile.TemporaryDirectory() as d, patch.object(m, 'STATE', Path(d)):
            with patch.object(m, 'consultar', return_value={'ultima_operacao': None}), patch.object(m, 'run', side_effect=m.Falha('comando_fixo_falhou')):
                with self.assertRaises(m.Falha):
                    m.iniciar('recuperar')
            self.assertEqual(m.ler(Path(d) / 'operacao.json')['codigo'], 'nao_iniciada')

    def test_reabertura_preserva_historico_e_ignora_invalido(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            q = root / 'analises-v1'
            backup = root / 'backup'
            backup.mkdir()
            src = root / ('c' * 32)
            src.write_bytes(b'arquivo de teste')
            for num, reason in enumerate(['Analisador indisponível ou limite de recursos atingido.', 'Cabeçalho GLB ilegível ou incompleto.']):
                path = q / (str(num) * 64)
                path.mkdir(parents=True)
                m.gravar(path / 'pedido.json', {'chave': src.name, 'sha256': m.sha(src)})
                m.gravar(path / 'estado.json', {'estado': 'falha', 'falha': reason})
            with patch.object(m, 'QUEUE', q):
                self.assertEqual(m.reabrir_falhas(backup), 1)
            self.assertFalse((q / ('0' * 64) / 'estado.json').exists())
            self.assertTrue((q / ('0' * 64) / 'estado-antes-backup.json').exists())
            self.assertTrue((q / ('1' * 64) / 'estado.json').exists())
            self.assertEqual(src.read_bytes(), b'arquivo de teste')

    def test_conteudo_divergente_nao_e_reaberto(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            q = root / 'analises-v1'
            p = q / ('a' * 64)
            p.mkdir(parents=True)
            (root / ('b' * 32)).write_bytes(b'alterado')
            m.gravar(p / 'pedido.json', {'chave': 'b' * 32, 'sha256': '0' * 64})
            m.gravar(p / 'estado.json', {'estado': 'falha', 'falha': 'Analisador indisponível ou limite de recursos atingido.'})
            with patch.object(m, 'QUEUE', q):
                self.assertEqual(m.reabrir_falhas(root), 0)
            self.assertTrue((p / 'estado.json').exists())

    def test_prova_falha_antes_de_alterar_executor_e_agenda(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            executor = root / 'executor.py'
            executor.write_bytes(b'original')
            m.gravar(root / 'operacao.json', {'id': 'a' * 32, 'acao': 'recuperar'})
            with patch.object(m, 'STATE', root), patch.object(m, 'EXECUTOR', executor), patch.object(m, 'EXEC_LOCK', root / 'lock'), \
                 patch.object(m, 'manifesto', return_value={'imagem_id': 'sha256:' + 'a' * 64}), \
                 patch.object(m, 'imagem_id', return_value='sha256:' + 'a' * 64), \
                 patch.object(m, 'backup_operacao', return_value=(root, 'agenda original')), \
                 patch.object(m, 'provar', side_effect=m.Falha('prova_do_leitor_falhou')), patch.object(m, 'run') as run:
                m.executar_operacao()
            self.assertEqual(executor.read_bytes(), b'original')
            self.assertEqual(m.ler(root / 'operacao.json')['estado'], 'falhou')
            self.assertFalse(any('crontab' in str(x) for x in run.call_args_list))

    def test_imagem_diferente_nao_e_sobrescrita(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            ex = root / 'executor.py'
            ex.write_bytes(b'original')
            m.gravar(root / 'operacao.json', {'id': 'a' * 32, 'acao': 'recuperar'})
            with patch.object(m, 'STATE', root), patch.object(m, 'EXECUTOR', ex), patch.object(m, 'EXEC_LOCK', root / 'lock'), \
                 patch.object(m, 'manifesto', return_value={'imagem_id': 'sha256:' + 'a' * 64}), \
                 patch.object(m, 'imagem_id', return_value='sha256:' + 'b' * 64), \
                 patch.object(m, 'backup_operacao', return_value=(root, '')), patch.object(m, 'provar') as prove, patch.object(m, 'run'):
                m.executar_operacao()
            prove.assert_not_called()
            self.assertEqual(m.ler(root / 'operacao.json')['codigo'], 'imagem_divergente_exige_conferencia')

    def test_interno_nao_expoe_erro_privado(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            m.gravar(root / 'operacao.json', {'id': 'a' * 32, 'acao': 'diagnosticar'})
            with patch.object(m, 'STATE', root), patch.object(m, 'manifesto', side_effect=ValueError('SEGREDO')):
                m.executar_operacao()
            raw = (root / 'operacao.json').read_text()
            self.assertNotIn('SEGREDO', raw)
            self.assertIn('falha_interna', raw)

    def test_imagem_ausente_so_recebe_nome_ativo_apos_prova(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            ex = root / 'executor.py'
            ex.write_bytes(b'executor aprovado')
            m.gravar(root / 'operacao.json', {'id': 'a' * 32, 'acao': 'recuperar'})
            ref = {'imagem_id': 'sha256:' + 'a' * 64, 'arquivos': {'executor_host.py': m.sha(ex)}}
            calls = []
            proved = []
            def fake_run(args, **kw):
                calls.append(args)
                if args[:3] == ['/usr/bin/docker', 'tag', ref['imagem_id']]:
                    self.assertTrue(proved, 'Não ativar antes de abrir os modelos e recusar o falso.')
                return types.SimpleNamespace(stdout=ref['imagem_id'], returncode=0)
            def proof(*args):
                self.assertTrue(any(c[:2] == ['/usr/bin/docker', 'load'] for c in calls))
                proved.append(True)
                return [{'estado': 'examinado'}]
            with patch.object(m, 'STATE', root), patch.object(m, 'EXECUTOR', ex), patch.object(m, 'EXEC_LOCK', root / 'lock'), \
                 patch.object(m, 'manifesto', return_value=ref), patch.object(m, 'imagem_id', return_value=None), \
                 patch.object(m, 'backup_operacao', return_value=(root, m.CRON)), patch.object(m, 'provar', side_effect=proof), \
                 patch.object(m, 'run', side_effect=fake_run), patch.object(m, 'consultar', return_value={'estado': 'disponivel'}), \
                 patch.object(m, 'reabrir_falhas', return_value=0):
                m.executar_operacao()
            result = m.ler(root / 'operacao.json')
            self.assertEqual(result['estado'], 'concluida')
            self.assertTrue(result['imagem_restaurada'])

    def test_retorna_executor_anterior_se_comprovacao_final_falha(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            ex = root / 'executor.py'
            ex.write_bytes(b'anterior preservado')
            (root / 'referencia').mkdir()
            saved = root / 'referencia/executor_host.py'
            saved.write_bytes(b'aprovado')
            ref = {'imagem_id': 'sha256:' + 'a' * 64, 'arquivos': {'executor_host.py': m.sha(saved)}}
            m.gravar(root / 'operacao.json', {'id': 'a' * 32, 'acao': 'recuperar'})
            with patch.object(m, 'STATE', root), patch.object(m, 'BASE', root), patch.object(m, 'EXECUTOR', ex), \
                 patch.object(m, 'EXEC_LOCK', root / 'lock'), patch.object(m, 'manifesto', return_value=ref), \
                 patch.object(m, 'imagem_id', return_value=ref['imagem_id']), \
                 patch.object(m, 'backup_operacao', return_value=(root, m.CRON)), patch.object(m, 'provar', return_value=[]), \
                 patch.object(m, 'run'), patch.object(m, 'consultar', return_value={'estado': 'precisa_recuperacao'}), \
                 patch.object(m, 'reabrir_falhas') as requeue:
                m.executar_operacao()
            self.assertEqual(ex.read_bytes(), b'anterior preservado')
            requeue.assert_not_called()
            self.assertEqual(m.ler(root / 'operacao.json')['codigo'], 'recuperacao_nao_confirmada')


if __name__ == '__main__':
    unittest.main()
