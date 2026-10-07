"""Provas locais para o conferidor do manifesto externo do Mercado Pago."""

import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULO = Path(__file__).resolve().parents[1] / "mercadopago_congelado.py"
spec = importlib.util.spec_from_file_location("mercadopago_congelado", MODULO)
assert spec and spec.loader
mp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mp)


class ConferenciaCongeladaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)
        (self.raiz / "payments" / "sub").mkdir(parents=True)
        (self.raiz / "payments" / "gateway.py").write_bytes(b"codigo aprovado")
        (self.raiz / "config.env").write_bytes(b"valor-privado-original")
        (self.raiz / "fora.py").write_bytes(b"livre")
        self.politica = {
            "fontes": {"prefixos": ["payments"], "arquivos": [], "hashes": mp.capturar_arvore(self.raiz, ["payments"], [])},
            "ambiente": {"arquivos": ["config.env"], "hashes": mp.capturar_arvore(self.raiz, [], ["config.env"])},
            "pacote": {"prefixos": ["payments"], "arquivos": [], "hashes": mp.capturar_arvore(self.raiz, ["payments"], [])},
            "imagem": "sha256:" + "a" * 64,
        }

    def test_base_aprovada_e_arquivo_fora_do_escopo(self):
        mp.conferir_fontes(self.raiz, self.politica)
        mp.conferir_ambiente(self.raiz, self.politica)
        mp.conferir_pacote(self.raiz, "sha256:" + "a" * 64, self.politica)
        (self.raiz / "fora.py").write_bytes(b"alteracao permitida")
        mp.conferir_fontes(self.raiz, self.politica)

    def test_detecta_alteracao_sem_expor_conteudo_ou_hash(self):
        (self.raiz / "payments" / "gateway.py").write_bytes(b"SEGREDO_NOVO")
        with self.assertRaises(mp.IntegridadeMercadoPagoErro) as contexto:
            mp.conferir_fontes(self.raiz, self.politica)
        mensagem = str(contexto.exception)
        self.assertIn("payments/gateway.py", mensagem)
        self.assertNotIn("SEGREDO_NOVO", mensagem)
        self.assertNotIn(self.politica["fontes"]["hashes"]["payments/gateway.py"], mensagem)

    def test_detecta_remocao_adicao_e_diretorio_vazio(self):
        (self.raiz / "payments" / "gateway.py").unlink()
        (self.raiz / "payments" / "extra.py").write_bytes(b"novo")
        (self.raiz / "payments" / "vazio").mkdir()
        with self.assertRaises(mp.IntegridadeMercadoPagoErro) as contexto:
            mp.conferir_fontes(self.raiz, self.politica)
        mensagem = str(contexto.exception)
        self.assertIn("removidos: payments/gateway.py", mensagem)
        self.assertIn("payments/extra.py", mensagem)
        self.assertIn("payments/vazio/", mensagem)

    def test_link_simbolico_na_arvore(self):
        link = self.raiz / "payments" / "link.py"
        try:
            link.symlink_to(self.raiz / "fora.py")
        except (OSError, NotImplementedError) as erro:
            self.skipTest(f"Link simbólico indisponível: {type(erro).__name__}")
        with self.assertRaises(mp.IntegridadeMercadoPagoErro) as contexto:
            mp.conferir_fontes(self.raiz, self.politica)
        self.assertIn("payments/link.py", str(contexto.exception))

    def test_imagem_divergente_e_ambiente_ausente(self):
        with self.assertRaisesRegex(mp.IntegridadeMercadoPagoErro, "Imagem do pacote divergente"):
            mp.conferir_pacote(self.raiz, "sha256:" + "b" * 64, self.politica)
        (self.raiz / "config.env").unlink()
        with self.assertRaises(mp.IntegridadeMercadoPagoErro) as contexto:
            mp.conferir_ambiente(self.raiz, self.politica)
        self.assertIn("config.env", str(contexto.exception))
        self.assertNotIn("valor-privado-original", str(contexto.exception))

    def test_recusa_manifesto_vazio_ou_sem_baseline_do_prefixo(self):
        self.politica["fontes"]["hashes"] = {}
        with self.assertRaises(mp.IntegridadeMercadoPagoErro):
            mp.conferir_fontes(self.raiz, self.politica)
        self.politica["fontes"]["hashes"] = {"payments/gateway.py": "a" * 64}
        with self.assertRaises(mp.IntegridadeMercadoPagoErro):
            mp.conferir_fontes(self.raiz, self.politica)

    def test_recusa_caminho_fora_da_raiz_e_escopo(self):
        for nome in ["../fora.py", "/fora.py", "C:/fora.py", "payments//gateway.py", "payments/./gateway.py", "payments/../fora.py", "payments\\gateway.py"]:
            with self.subTest(nome=nome):
                self.politica["fontes"]["arquivos"] = [nome]
                with self.assertRaises(mp.IntegridadeMercadoPagoErro):
                    mp.conferir_fontes(self.raiz, self.politica)
        self.politica["fontes"]["arquivos"] = []
        self.politica["fontes"]["hashes"]["fora.py"] = "a" * 64
        with self.assertRaises(mp.IntegridadeMercadoPagoErro):
            mp.conferir_fontes(self.raiz, self.politica)

    @staticmethod
    def _texto_rotas(funil="http://aplicacao:8000", checkout="http://aplicacao:8000"):
        return (
            "http:\n  routers:\n    checkout:\n      rule: 'PathPrefix(`/checkout`)'\n"
            "      service: checkout\n  services:\n    funil:\n      loadBalancer:\n"
            f'        servers: [ {{ url: "{funil}" }} ]\n'
            "    checkout:\n      loadBalancer:\n"
            f'        servers: [ {{ url: "{checkout}" }} ]\n'
        ).encode()

    def _escrever_rotas(self, texto):
        rota = self.raiz / "traefik" / "dynamic" / "plataforma.yml"
        rota.parent.mkdir(parents=True, exist_ok=True)
        rota.write_bytes(texto)
        return rota

    def test_troca_valida_do_funil_preserva_hash_e_ambiente(self):
        self._escrever_rotas(self._texto_rotas())
        digest = mp.capturar_rotas(self.raiz)
        self.politica["rotas_sha256"] = digest
        self._escrever_rotas(self._texto_rotas(funil="http://meshcraft-funil-abcdef123456-deadbeef:8000"))
        self.assertEqual(mp.capturar_rotas(self.raiz), digest)
        mp.conferir_rotas(self.raiz, self.politica)
        mp.conferir_ambiente(self.raiz, self.politica)

    def test_checkout_e_outro_texto_alterados_sao_barrados(self):
        original = self._texto_rotas()
        self._escrever_rotas(original)
        self.politica["rotas_sha256"] = mp.capturar_rotas(self.raiz)
        for texto in [
            self._texto_rotas(checkout="http://outro-servico:8000"),
            original.replace(b"service: checkout", b"service: funil"),
        ]:
            with self.subTest(texto=texto[:20]):
                self._escrever_rotas(texto)
                with self.assertRaises(mp.IntegridadeMercadoPagoErro):
                    mp.conferir_ambiente(self.raiz, self.politica)

    def test_rota_funil_ausente_duplicada_ou_destino_invalido(self):
        original = self._texto_rotas()
        for texto in [
            original.replace(b"    funil:", b"    outro:"),
            original.replace(b"    checkout:\n      loadBalancer:", b"    funil:\n      loadBalancer:\n        servers: [ { url: \"http://aplicacao:8000\" } ]\n    checkout:\n      loadBalancer:"),
            self._texto_rotas(funil="http://servico-qualquer:8000"),
        ]:
            with self.subTest(texto=texto[:20]):
                self._escrever_rotas(texto)
                with self.assertRaises(mp.IntegridadeMercadoPagoErro):
                    mp.capturar_rotas(self.raiz)

    def test_rota_simbolica_rejeitada(self):
        rota = self.raiz / "traefik" / "dynamic" / "plataforma.yml"
        rota.parent.mkdir(parents=True, exist_ok=True)
        destino = self.raiz / "fora.yml"
        destino.write_bytes(self._texto_rotas())
        try:
            rota.symlink_to(destino)
        except (OSError, NotImplementedError) as erro:
            self.skipTest(f"Link simbólico indisponível: {type(erro).__name__}")
        with self.assertRaises(mp.IntegridadeMercadoPagoErro):
            mp.capturar_rotas(self.raiz)


if __name__ == "__main__":
    unittest.main()
