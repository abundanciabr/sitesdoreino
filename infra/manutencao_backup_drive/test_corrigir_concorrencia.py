import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('correcao', Path(__file__).with_name('corrigir_concorrencia.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
FIXTURE = (Path(__file__).parent / 'fixtures' / 'enviar_20261013.txt').read_bytes().replace(b'\r\n', b'\n')
FIXED = FIXTURE.replace(m.OLD, m.NEW)
PROOF = {'estado': 'copia conferida por leitura integral', 'bases': 19, 'arquivos': 23}


class CorrectionTests(unittest.TestCase):
    def test_exact_known_source_and_only_two_lock_changes(self):
        self.assertEqual(m.sha(FIXTURE), m.BEFORE)
        self.assertEqual(m.sha(FIXED), m.AFTER)
        self.assertEqual(m.candidate(FIXTURE), FIXED)
        self.assertEqual(FIXTURE.count(m.OLD), 2)
        self.assertIn(b'fcntl.flock(own,fcntl.LOCK_EX|fcntl.LOCK_NB)', FIXED)

    def test_unknown_program_is_not_modified(self):
        with self.assertRaisesRegex(RuntimeError, 'divergente'):
            m.candidate(FIXTURE + b'\n')

    def test_already_corrected_is_idempotent(self):
        self.assertEqual(m.candidate(FIXED), FIXED)

    def test_proof_uses_separate_state_and_restores_arguments(self):
        source = b'''import json,sys\nfrom pathlib import Path\nSTATE=Path('/nao_usar')\ndef rc(*args):\n assert '-conferencia-' in args[1]\n return b''\ndef main():\n assert len(sys.argv)==1\n rc('copy','meshcraft_crypt:2026-10-13/20261013-000000Z-teste')\n STATE.mkdir()\n (STATE/'ultimo-resultado.json').write_text(json.dumps({'estado':'copia conferida por leitura integral','bases':19,'arquivos':23}))\n'''
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(m.prove(source, Path(folder))['bases'], 19)

    def test_competing_source_change_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'enviar.py'; target.write_bytes(b'outro trabalho')
            with self.assertRaisesRegex(RuntimeError, 'outra_operacao'):
                m.replace_preserving(target, FIXED, m.BEFORE)
            self.assertEqual(target.read_bytes(), b'outro trabalho')

    def test_symlink_target_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            real=Path(folder)/'real.py'; real.write_bytes(FIXTURE)
            target=Path(folder)/'enviar.py'; target.symlink_to(real)
            with self.assertRaises(RuntimeError):
                m.replace_preserving(target, FIXED, m.BEFORE)
            self.assertEqual(real.read_bytes(), FIXTURE)

    def run_apply(self, fail=False):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); state=root/'estado'; state.mkdir()
            program=root/'enviar.py'; program.write_bytes(FIXTURE); program.chmod(0o750)
            old=state/'historico'; old.write_bytes(b'comprovante anterior')
            def proof(code, destination):
                self.assertEqual(code, FIXED)
                self.assertEqual((destination/'enviar-anterior.py').read_bytes(), FIXTURE)
                self.assertEqual(program.stat().st_mode & 0o777, 0o750)
                if fail: raise RuntimeError('teste_falhou')
                return PROOF
            with patch.object(m,'PROGRAM',program), patch.object(m,'STATE',state), \
                 patch.object(m,'site_status',return_value=200), patch.object(m,'prove',side_effect=proof), \
                 patch.object(m.subprocess,'run',return_value=subprocess.CompletedProcess([],0)) as start:
                if fail:
                    with self.assertRaisesRegex(RuntimeError,'teste_falhou'): m.apply()
                    self.assertEqual(program.read_bytes(),FIXTURE)
                    start.assert_not_called()
                else:
                    result=m.apply(); self.assertTrue(result['corrigido'])
                    self.assertEqual(program.read_bytes(),FIXED)
                    self.assertEqual(start.call_args.args[0],['systemctl','start','--no-block','meshcraft-backup-drive.service'])
            self.assertEqual(old.read_bytes(),b'comprovante anterior')
            backups=list(state.glob('correcao-*/enviar-anterior.py'))
            self.assertEqual(len(backups),1)
            self.assertEqual(backups[0].read_bytes(),FIXTURE)

    def test_apply_backs_up_then_verifies_without_deleting_history(self):
        self.run_apply()

    def test_failure_restores_only_program_and_preserves_backup(self):
        self.run_apply(fail=True)


if __name__=='__main__': unittest.main()
