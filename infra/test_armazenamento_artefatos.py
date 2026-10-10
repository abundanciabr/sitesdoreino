"""Provas locais de preservação, recuperação e falhas de artefatos novos."""

import hashlib
import io
import json
import os
import stat
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from infra import armazenamento_artefatos as a
except ImportError:
    import armazenamento_artefatos as a


class ArtefatosTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ.get("ARTEFATOS_TEST_TMP"))
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.cache = self.base / "cache"

    def test_arvore_nova_reusa_inode_e_preserva_metadados(self):
        one, two = self.base / "nova1", self.base / "nova2"
        one.mkdir()
        two.mkdir()
        stamp = 1700000000123456789
        for root in (one, two):
            p = root / "arquivo"
            p.write_bytes(b"repetido" * 1024)
            p.chmod(0o640)
            os.utime(p, ns=(stamp, stamp))
        original = (one / "arquivo").read_bytes()
        first = a.consolidar_arvore_nova(one, self.cache)
        second = a.consolidar_arvore_nova(two, self.cache)
        self.assertEqual(first["objetos_criados"], 1)
        self.assertEqual(second["objetos_criados"], 0)
        self.assertGreater(second["bytes_economizados_estimados"], 0)
        self.assertEqual((two / "arquivo").read_bytes(), original)
        self.assertEqual(stat.S_IMODE((two / "arquivo").stat().st_mode), 0o640)
        self.assertEqual((two / "arquivo").stat().st_mtime_ns, stamp)
        self.assertEqual((one / "arquivo").stat().st_ino, (two / "arquivo").stat().st_ino)

    def test_arvore_distingue_modo_e_mtime_e_recusa_link(self):
        one, two = self.base / "um", self.base / "dois"
        one.mkdir()
        two.mkdir()
        (one / "x").write_bytes(b"same")
        (two / "x").write_bytes(b"same")
        (one / "x").chmod(0o600)
        (two / "x").chmod(0o400)
        self.assertEqual(a.consolidar_arvore_nova(one, self.cache)["objetos_criados"], 1)
        self.assertEqual(a.consolidar_arvore_nova(two, self.cache)["objetos_criados"], 1)
        self.assertNotEqual((one / "x").stat().st_ino, (two / "x").stat().st_ino)
        if hasattr(os, "symlink"):
            try:
                (two / "atalho").symlink_to(one / "x")
            except OSError:
                return
            before = (two / "x").stat().st_ino
            with self.assertRaises(ValueError):
                a.consolidar_arvore_nova(two, self.cache)
            self.assertEqual((two / "x").stat().st_ino, before)

    def test_cache_corrompido_recusado_sem_alterar_fonte(self):
        one, two = self.base / "um", self.base / "dois"
        for root in (one, two):
            root.mkdir()
            (root / "x").write_bytes(b"conteudo")
            os.utime(root / "x", ns=(1700000000000000000,) * 2)
        a.consolidar_arvore_nova(one, self.cache)
        obj = next((self.cache / "arvores").iterdir())
        obj.write_bytes(b"corrupto")
        original = (two / "x").read_bytes()
        with self.assertRaises(ValueError):
            a.consolidar_arvore_nova(two, self.cache)
        self.assertEqual((two / "x").read_bytes(), original)

    def test_snapshot_restauracao_independente_cache_e_sem_sobrescrita(self):
        source = self.base / "origem"
        source.mkdir()
        (source / "sub").mkdir()
        file = source / "sub" / "texto"
        file.write_bytes(b"conteudo original")
        file.chmod(0o640)
        stamp = 1700000000000000000
        os.utime(file, ns=(stamp, stamp))
        snap = self.base / "backup-novo"
        a.criar_snapshot([(source, "fonte")], snap, self.cache)
        self.assertTrue((snap / "restaurar.py").is_file())
        self.assertEqual(a.verificar_snapshot(snap)["formato"], 2)
        # Simula perda integral do cache; o backup contém os próprios objetos.
        import shutil
        shutil.rmtree(self.cache)
        restored = self.base / "recuperado"
        a.restaurar_snapshot(snap, restored)
        result = restored / "fonte" / "sub" / "texto"
        self.assertEqual(result.read_bytes(), b"conteudo original")
        self.assertEqual(stat.S_IMODE(result.stat().st_mode), 0o640)
        self.assertEqual(result.stat().st_mtime_ns, stamp)
        self.assertNotEqual(result.stat().st_ino, (snap / "objetos" / hashlib.sha256(b"conteudo original").hexdigest()).stat().st_ino)
        with self.assertRaises(FileExistsError):
            a.restaurar_snapshot(snap, restored)
        self.assertEqual(result.read_bytes(), b"conteudo original")

    def test_snapshot_recusa_percurso_hostil_objeto_ausente_e_destino_existente(self):
        source = self.base / "x"
        source.write_bytes(b"X")
        with self.assertRaises(ValueError):
            a.criar_snapshot([(source, "../escape")], self.base / "bad", self.cache)
        snap = self.base / "backup"
        a.criar_snapshot([(source, "x")], snap, self.cache)
        with self.assertRaises(FileExistsError):
            a.criar_snapshot([(source, "x")], snap, self.cache)
        manifest = json.loads((snap / "manifesto.json").read_text())
        manifest["entradas"][0]["path"] = "../fora"
        (snap / "manifesto.json").chmod(0o600)
        (snap / "manifesto.json").write_text(json.dumps(manifest))
        with self.assertRaises(ValueError):
            a.restaurar_snapshot(snap, self.base / "destino")
        self.assertFalse((self.base / "destino").exists())
        manifest["entradas"][0]["path"] = "x"
        (snap / "manifesto.json").write_text(json.dumps(manifest))
        next((snap / "objetos").iterdir()).unlink()
        with self.assertRaises((ValueError, FileNotFoundError)):
            a.restaurar_snapshot(snap, self.base / "destino")

    def test_exportacao_imagem_repetida_e_configuracao_adulterada(self):
        config = b'{"architecture":"amd64"}'
        digest = hashlib.sha256(config).hexdigest()
        image = "sha256:" + digest
        calls = []

        def save(command, stdout, check):
            calls.append(command)
            with tarfile.open(fileobj=stdout, mode="w") as archive:
                manifest = json.dumps([{"Config": digest + ".json", "Layers": []}]).encode()
                for name, data in (("manifest.json", manifest), (digest + ".json", config)):
                    info = tarfile.TarInfo(name)
                    info.size = len(data)
                    archive.addfile(info, io.BytesIO(data))

        with patch.object(a.subprocess, "run", side_effect=save):
            first = a.exportar_imagem_nova(image, self.base / "um.tar", self.cache)
            second = a.exportar_imagem_nova(image, self.base / "dois.tar", self.cache)
        self.assertEqual(len(calls), 1)
        self.assertTrue(first["exportacao_nova"])
        self.assertFalse(second["exportacao_nova"])
        self.assertEqual((self.base / "um.tar").stat().st_ino, (self.base / "dois.tar").stat().st_ino)
        with self.assertRaises(FileExistsError):
            a.exportar_imagem_nova(image, self.base / "um.tar", self.cache)
        obj = next((self.cache / "imagens").glob("*.tar"))
        obj.chmod(0o600)
        obj.write_bytes(b"adulterado")
        obj.chmod(0o400)
        with self.assertRaises((ValueError, tarfile.TarError)):
            a.exportar_imagem_nova(image, self.base / "tres.tar", self.cache)
        self.assertFalse((self.base / "tres.tar").exists())

    def test_identidade_oci_e_camadas_conferidas(self):
        def encoded(obj):
            return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()

        config = encoded({"architecture": "amd64", "os": "linux"})
        layer = b"camada"
        cfg_sha = hashlib.sha256(config).hexdigest()
        layer_sha = hashlib.sha256(layer).hexdigest()
        manifest = encoded({"schemaVersion": 2,
                            "config": {"mediaType": "application/vnd.oci.image.config.v1+json",
                                       "digest": "sha256:" + cfg_sha, "size": len(config)},
                            "layers": [{"mediaType": "application/vnd.oci.image.layer.v1.tar",
                                        "digest": "sha256:" + layer_sha, "size": len(layer)}]})
        manifest_sha = hashlib.sha256(manifest).hexdigest()
        index = encoded({"schemaVersion": 2, "manifests": [
            {"mediaType": "application/vnd.oci.image.manifest.v1+json",
             "digest": "sha256:" + manifest_sha, "size": len(manifest)}]})
        image = self.base / "oci.tar"

        def archive(layer_bytes):
            with tarfile.open(image, "w") as tar:
                for name, data in (("index.json", index),
                                   ("blobs/sha256/" + manifest_sha, manifest),
                                   ("blobs/sha256/" + cfg_sha, config),
                                   ("blobs/sha256/" + layer_sha, layer_bytes)):
                    info = tarfile.TarInfo(name)
                    info.size = len(data)
                    tar.addfile(info, io.BytesIO(data))

        archive(layer)
        a._verify_image_tar(image, manifest_sha)
        with self.assertRaises(ValueError):
            a._verify_image_tar(image, cfg_sha)
        archive(b"tamper")
        with self.assertRaises(ValueError):
            a._verify_image_tar(image, manifest_sha)


if __name__ == "__main__":
    unittest.main()
