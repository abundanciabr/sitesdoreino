import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from revisor.sandbox import accepted, analyze, command, MAX_UPLOAD


class ForbiddenRead:
    def read(self, *_):
        raise AssertionError('Rejected input must not be read')


class SandboxTests(unittest.TestCase):
    def test_reject_before_read(self):
        for filename,size in [('model.blend',10),('model.zip',10),('model.glb',MAX_UPLOAD+1)]:
            with self.assertRaises(ValueError): analyze(ForbiddenRead(),filename,size,'game')

    def test_exact_size_limit(self):
        accepted('MODEL.GLB',MAX_UPLOAD)
        with self.assertRaises(ValueError): accepted('model.fbx',MAX_UPLOAD+1)

    def test_no_fallback_on_windows(self):
        with patch('revisor.sandbox.LINUX',False):
            with self.assertRaisesRegex(RuntimeError,'linux_isolation_required'):
                analyze(ForbiddenRead(),'model.glb',3,'game')

    def test_namespace_command_never_mounts_database_or_secrets(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'suffix').write_text('.fbx')
            args = command(root,'game',None)
            self.assertIn('--unshare-all',args)
            self.assertIn('--clearenv',args)
            self.assertIn('--disable-autoexec',args)
            self.assertNotIn('--share-net',args)
            self.assertNotIn('/etc',args)
            self.assertNotIn('/var/run/docker.sock',args)

    @unittest.skipUnless(os.name=='posix','Linux resource limits and process groups are required')
    def test_missing_sandbox_is_unreadable_and_cleans_temporary(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch('revisor.sandbox.subprocess.Popen',side_effect=FileNotFoundError):
                # Explicit runner injection; no untrusted subprocess runs in this test.
                result = analyze(io.BytesIO(b'abc'),'model.glb',3,'game',temporary_root=temporary,
                                 runner=lambda *a,**kw: (_ for _ in ()).throw(FileNotFoundError()))
            self.assertEqual(result['state'],'unreadable')
            self.assertEqual(list(Path(temporary).iterdir()),[])


if __name__ == '__main__':
    unittest.main()
