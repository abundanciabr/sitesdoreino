"""Marcadores locais; nunca conecta à VPS nem abre credenciais reais."""
import importlib.util
import base64
import io
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

ARQUIVO = Path(__file__).with_name("cofre_dispatcher.py")
spec = importlib.util.spec_from_file_location("cofre_dispatcher_teste", ARQUIVO)
cofre = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cofre)


class CofreRestrito(unittest.TestCase):
    def test_operacoes_exatas(self):
        self.assertEqual(cofre.pedido("cofre fetch admin-midia"), ("fetch", "admin-midia"))
        self.assertEqual(cofre.pedido("cofre secrets"), ("secrets", None))
        self.assertEqual(cofre.pedido("cofre guide"), ("guide", None))
        for pedido in ("sh", "cofre fetch /etc", "cofre fetch ../env", "cofre guide; id",
                       "cofre archive env", "cofre list admin-dados", "cofre fetch admin-midia extra"):
            with self.subTest(pedido=pedido), self.assertRaises(cofre.Recusa):
                cofre.pedido(pedido)

    def test_nomes_e_symlink_nao_vazam(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporario:
            raiz = Path(temporario)
            (raiz / "sub").mkdir()
            (raiz / "sub" / "marcador.txt").write_bytes(b"MARCADOR-FICTICIO")
            (raiz / "sub" / "outro.parcial").write_bytes(b"INCOMPLETO")
            fora = raiz.parent / (raiz.name + "-fora.txt")
            fora.write_bytes(b"FORA-DO-ESCOPO")
            try:
                try:
                    (raiz / "atalho").symlink_to(fora)
                except (OSError, NotImplementedError):
                    pass
                self.assertEqual(list(cofre.nomes_regulares(raiz)), ["sub/marcador.txt"])
                cod = cofre.nome_codificado("sub/marcador.txt").encode()
                self.assertEqual(cofre.decodificar_nome(cod), "sub/marcador.txt")
                for nome in ("/etc/passwd", "../fora", "sub/../fora", "sub\\fora", "sub//x", "x\nY"):
                    with self.subTest(nome=nome), self.assertRaises(cofre.Recusa):
                        cofre.caminho_relativo(nome)
                for linha in (b"!!", base64.b64encode(b"../fora"), base64.b64encode(b"sub\\fora")):
                    with self.subTest(linha=linha), self.assertRaises(cofre.Recusa):
                        cofre.decodificar_nome(linha)
            finally:
                fora.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
