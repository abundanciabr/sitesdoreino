import os
from pathlib import Path
import unittest


class Isolation(unittest.TestCase):
    def test_unprivileged_without_secrets(self):
        self.assertEqual(os.getuid(),65534)
        self.assertFalse(Path('/run/docker.sock').exists())
        self.assertFalse(Path('/opt/plataforma/env').exists())
        self.assertFalse(Path('/run/previa-env').exists())
        with self.assertRaises(OSError):
            Path('/work/index.html').write_text('changed')
        self.assertIn('Prévia isolada funcionando',Path('index.html').read_text())
