"""A candidata alterada não passa da montagem nem chega à ativação."""

from __future__ import annotations

import importlib.util
from contextlib import ExitStack
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


INFRA = Path(__file__).resolve().parents[1]
if str(INFRA) not in sys.path:
    sys.path.insert(0, str(INFRA))

from mercadopago_congelado import IntegridadeMercadoPagoErro, capturar_arvore


def carregar(nome: str, arquivo: str):
    spec = importlib.util.spec_from_file_location(nome, INFRA / arquivo)
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class PublicacaoMercadoPagoCongeladoTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name) / "plataforma"
        self.raiz.mkdir()
        self.aprovada = Path(self.tmp.name) / "aprovada"
        self._arquivo(self.aprovada / "payments" / "gateway.py", b"versao aprovada")
        self._arquivo(self.raiz / "config.env", b"configuracao privada")
        self.imagem = "sha256:" + "a" * 64
        self.sha = "1" * 40
        self.politica = {
            "fontes": {"prefixos": ["payments"], "arquivos": [], "hashes": capturar_arvore(self.aprovada, ["payments"], [])},
            "pacote": {"prefixos": ["payments"], "arquivos": [], "hashes": capturar_arvore(self.aprovada, ["payments"], [])},
            "ambiente": {"arquivos": ["config.env"], "hashes": capturar_arvore(self.raiz, [], ["config.env"])},
            "imagem": self.imagem,
        }

    @staticmethod
    def _arquivo(caminho: Path, dados: bytes) -> None:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_bytes(dados)

    def _publicador(self):
        modulo = carregar("publicar_mp_teste", "publicar.py")
        modulo.RAIZ = self.raiz
        modulo.PUBLICACOES = self.raiz / "publicacoes"
        modulo.TRABALHO = modulo.PUBLICACOES / "trabalho"
        modulo.LOGS = modulo.PUBLICACOES / "logs"
        return modulo

    def test_fonte_alterada_impede_preparar_codigo(self):
        publicador = self._publicador()
        preparar = Mock(side_effect=AssertionError("não deve montar código"))
        ativar = Mock(side_effect=AssertionError("não deve ativar"))

        def extrair_alterada(_sha, destino):
            self._arquivo(destino / "payments" / "gateway.py", b"versao alterada")

        with patch.object(publicador, "git", return_value=""), \
             patch.object(publicador, "ordem", return_value="nova"), \
             patch.object(publicador, "extrair", side_effect=extrair_alterada), \
             patch.object(publicador, "politica_mercadopago", return_value=self.politica), \
             patch.object(publicador, "preparar_codigo", preparar), \
             patch.object(publicador, "executar_roteiro", ativar), \
             patch.object(publicador, "dizer"):
            resultado = publicador.publicar("aplicacao", self.sha, pedido_em="2026-10-07T12:00:00Z")
        self.assertEqual(resultado, 1)
        preparar.assert_not_called()
        ativar.assert_not_called()

    def test_pacote_alterado_durante_ensaio_impede_roteiro_de_ativacao(self):
        publicador = self._publicador()
        codigo = self.raiz / "versoes" / "aplicacao" / self.sha
        self._arquivo(codigo / "payments" / "gateway.py", b"versao aprovada")
        ativar = Mock(side_effect=AssertionError("não deve ativar"))

        def extrair_aprovada(_sha, destino):
            self._arquivo(destino / "payments" / "gateway.py", b"versao aprovada")

        def ensaiar_e_alterar(*_args):
            (codigo / "payments" / "gateway.py").write_bytes(b"alterada depois do primeiro exame")
            return {"estado": "comprovado"}

        with patch.object(publicador, "git", return_value=""), \
             patch.object(publicador, "ordem", return_value="nova"), \
             patch.object(publicador, "extrair", side_effect=extrair_aprovada), \
             patch.object(publicador, "politica_mercadopago", return_value=self.politica), \
             patch.object(publicador, "preparar_codigo", return_value=(codigo, self.imagem, False, 0.0)), \
             patch.object(publicador, "imagem_id", side_effect=lambda imagem: imagem), \
             patch.object(publicador, "identificar", return_value={"id": "pacote1"}), \
             patch.object(publicador, "ensaiar", side_effect=ensaiar_e_alterar), \
             patch.object(publicador, "executar_roteiro", ativar), \
             patch.object(publicador, "dizer"):
            resultado = publicador.publicar("aplicacao", self.sha, pedido_em="2026-10-07T12:00:00Z")
        self.assertEqual(resultado, 1)
        ativar.assert_not_called()

    def test_pacote_alterado_apos_preparar_impede_pin_e_preserva_atual(self):
        with patch.dict(os.environ, {"PLATAFORMA_DIR": str(self.raiz), "CELULA": "aplicacao", "TAG": self.sha}):
            local = carregar("publicacao_local_mp_teste", "publicacao-local.py")
        provas = self.raiz / "publicacoes" / "provas" / "pacote1"
        provas.mkdir(parents=True)
        codigo = self.raiz / "versoes" / "aplicacao" / self.sha
        self._arquivo(codigo / "payments" / "gateway.py", b"versao aprovada")
        resultado_prova = {"estado": "comprovado"}
        pacote = {"id": "pacote1"}
        self._arquivo(provas / "pacote.json", json.dumps({"sha": self.sha, "resultado": resultado_prova, "pacote": pacote}).encode())
        estado = {
            "celula": "aplicacao", "atual": "2" * 40,
            "servicos": ["aplicacao"],
        }
        journal = self.raiz / "publicacoes" / "aplicacao.json"
        self._arquivo(journal, json.dumps(estado).encode())
        pin = Mock(side_effect=AssertionError("não deve fixar imagem"))
        with ExitStack() as pilha:
            pilha.enter_context(patch.dict(os.environ, {"TAG": self.sha, "PACOTE_ENSAIADO": str(provas / "pacote.json")}))
            pilha.enter_context(patch.object(local, "conferir_ultima"))
            pilha.enter_context(patch.object(local, "conferir_relatorio", return_value=resultado_prova))
            pilha.enter_context(patch.object(local, "identificar", return_value=pacote))
            pilha.enter_context(patch.object(local, "versao_pedida", return_value={"codigo": str(codigo), "imagem": self.imagem}))
            pilha.enter_context(patch.object(local, "compose", return_value="aplicacao"))
            pilha.enter_context(patch.object(local, "pin", pin))
            pilha.enter_context(patch.object(local, "politica_mercadopago", return_value=self.politica))
            local.executar("preparar")
            self.assertEqual(json.loads(journal.read_text(encoding="utf-8"))["candidata"], self.sha)
            (codigo / "payments" / "gateway.py").write_bytes(b"alterada depois de preparar")
            with self.assertRaises(IntegridadeMercadoPagoErro):
                local.executar("aplicar")
        pin.assert_not_called()
        self.assertEqual(json.loads(journal.read_text(encoding="utf-8"))["atual"], "2" * 40)


if __name__ == "__main__":
    unittest.main()
