"""O congelamento também protege recuperação e troca de infraestrutura."""

from __future__ import annotations

import importlib.util
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


class RecuperacaoMercadoPagoCongeladoTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name) / "plataforma"
        self.raiz.mkdir()
        self.imagem = "sha256:" + "a" * 64
        self.sha_atual = "1" * 40
        self.sha_alvo = "2" * 40
        self.codigo_atual = self.raiz / "versoes" / "aplicacao" / self.sha_atual
        self.codigo_alvo = self.raiz / "versoes" / "aplicacao" / self.sha_alvo
        self._arquivo(self.codigo_atual / "checkout" / "cartao.py", b"aprovada")
        self._arquivo(self.codigo_alvo / "checkout" / "cartao.py", b"aprovada")
        self._arquivo(self.raiz / "config.env", b"configuracao aprovada")
        self.politica = {
            "pacote": {"prefixos": ["checkout"], "arquivos": [],
                       "hashes": capturar_arvore(self.codigo_atual, ["checkout"], [])},
            "ambiente": {"prefixos": [], "arquivos": ["config.env"],
                         "hashes": capturar_arvore(self.raiz, [], ["config.env"])},
            "imagem": self.imagem,
        }
        self.journal = self.raiz / "publicacoes" / "aplicacao.json"
        self.estado = {
            "celula": "aplicacao", "atual": self.sha_atual,
            "atual_versao": {"imagem": self.imagem, "codigo": str(self.codigo_atual)},
            "aprovada": {"sha": self.sha_alvo, "imagem": self.imagem,
                         "codigo": str(self.codigo_alvo)},
            "anterior_aprovada": None, "servicos": ["aplicacao"],
            "endereco": "https://meshcraft.top/",
        }
        self._arquivo(self.journal, json.dumps(self.estado).encode())
        with patch.dict(os.environ, {"PLATAFORMA_DIR": str(self.raiz), "CELULA": "aplicacao"}):
            self.local = carregar("publicacao_local_mp_recuperacao_teste", "publicacao-local.py")

    @staticmethod
    def _arquivo(caminho: Path, dados: bytes) -> None:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_bytes(dados)

    def _ambiente(self):
        return patch.dict(os.environ, {"TAG": self.sha_alvo, "ATUAL_ESPERADA": self.sha_atual})

    def test_alvo_antigo_divergente_recusado_antes_de_alterar_journal_ou_rota(self):
        self._arquivo(self.codigo_alvo / "checkout" / "cartao.py", b"versao antiga")
        anterior = self.journal.read_bytes()
        pin = Mock(side_effect=AssertionError("nao pode trocar rota"))
        imagem = Mock(side_effect=AssertionError("nao pode tocar imagem"))
        with self._ambiente(), patch.object(self.local, "politica_mercadopago", return_value=self.politica), \
             patch.object(self.local, "conferir_codigo_docs"), \
             patch.object(self.local, "pin", pin), patch.object(self.local, "garantir_imagem", imagem):
            with self.assertRaises(IntegridadeMercadoPagoErro):
                self.local.executar("recuperar")
        self.assertEqual(self.journal.read_bytes(), anterior)
        pin.assert_not_called()
        imagem.assert_not_called()

    def test_alvo_integro_recupera_e_registra_aprovacao(self):
        pin = Mock()
        compose = Mock()
        provar = Mock()
        with self._ambiente(), patch.object(self.local, "politica_mercadopago", return_value=self.politica), \
             patch.object(self.local, "conferir_codigo_docs"), \
             patch.object(self.local, "garantir_imagem"), patch.object(self.local, "pin", pin), \
             patch.object(self.local, "conferir_execucao_para_recuperar"), \
             patch.object(self.local, "compose", compose), patch.object(self.local, "provar", provar), \
             patch.object(self.local, "medir"):
            self.local.executar("recuperar")
        pin.assert_called_once()
        compose.assert_called_once()
        provar.assert_called_once()
        depois = json.loads(self.journal.read_text(encoding="utf-8"))
        self.assertEqual(depois["atual"], self.sha_alvo)
        self.assertEqual(depois["recuperacao"]["estado"], "concluida")


class InfraMercadoPagoCongeladoTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name) / "plataforma"
        self.fonte = Path(self.tmp.name) / "fonte"
        self.raiz.mkdir()
        self.fonte.mkdir()
        self._arquivo(self.raiz / "docker-compose.yml", b"composicao aprovada")
        self._arquivo(self.fonte / "docker-compose.yml", b"composicao alterada")
        self._arquivo(self.raiz / "traefik" / "dynamic" / "plataforma.yml", b"rota aprovada")
        self._arquivo(self.fonte / "traefik" / "dynamic" / "plataforma.yml", b"rota aprovada")
        self._arquivo(self.raiz / "publicacoes" / "aplicacao.json", json.dumps({
            "atual_versao": {"imagem": "sha256:" + "a" * 64, "codigo": "/versao/aprovada"},
        }).encode())
        self.politica = {
            "infra": {"prefixos": [], "arquivos": ["docker-compose.yml"],
                      "hashes": capturar_arvore(self.raiz, [], ["docker-compose.yml"])},
        }
        with patch.dict(os.environ, {"PLATAFORMA_DIR": str(self.raiz)}):
            self.ativar = carregar("ativar_mp_infra_teste", "ativar-aplicacao.py")

    @staticmethod
    def _arquivo(caminho: Path, dados: bytes) -> None:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_bytes(dados)

    def test_compose_candidato_alterado_recusado_antes_de_snapshot_ou_troca(self):
        compose = Mock(side_effect=AssertionError("nao pode chamar Docker Compose"))
        copiar = Mock(side_effect=AssertionError("nao pode copiar a candidata"))
        with patch.dict(os.environ, {"FONTE_INFRA": str(self.fonte)}), \
             patch.object(self.ativar, "politica_mercadopago", return_value=self.politica), \
             patch.object(self.ativar, "conferir_ambiente"), \
             patch.object(self.ativar, "conferir_rotas"), \
             patch.object(self.ativar, "conferir_mp_pacote"), \
             patch.object(self.ativar, "compose", compose), \
             patch.object(self.ativar.shutil, "copy2", copiar):
            with self.assertRaises(IntegridadeMercadoPagoErro):
                self.ativar.sincronizar_infra("3" * 40)
        compose.assert_not_called()
        copiar.assert_not_called()
        self.assertEqual((self.raiz / "docker-compose.yml").read_bytes(), b"composicao aprovada")

    def test_falha_da_aplicacao_no_lote_impede_sincronizar_infra(self):
        with patch.dict(os.environ, {"PLATAFORMA_DIR": str(self.raiz)}):
            publicar = carregar("publicar_mp_lote_teste", "publicar.py")
        publicar.RAIZ = self.raiz
        publicar.PUBLICACOES = self.raiz / "publicacoes"
        publicar.LOTES = publicar.PUBLICACOES / "lotes"
        publicar.LOGS = publicar.PUBLICACOES / "logs"
        publicar.LOTES.mkdir(parents=True, exist_ok=True)
        head = "4" * 40
        celulas = Mock()
        celulas.topologia.return_value = {"celulas": {}}
        sincronizar = Mock(side_effect=AssertionError("nao pode sincronizar infra"))
        with patch.object(publicar, "git", side_effect=lambda *args: head if args[:1] == ("rev-parse",) else "2026-10-07T12:00:00Z"), \
             patch.object(publicar, "carregar_celulas", return_value=celulas), \
             patch.object(publicar, "arquivos_do_lote", return_value=["services/aplicacao/config.py", "infra/docker-compose.yml"]), \
             patch.object(publicar, "journal", return_value={"atual": "1" * 40}), \
             patch.object(publicar, "sincronizar_infra_aplicacao", sincronizar), \
             patch.object(publicar.subprocess, "run", return_value=Mock(returncode=1)), \
             patch.object(publicar, "dizer"):
            resultado = publicar.lote_travado("1" * 40, head)
        self.assertEqual(resultado, 1)
        sincronizar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
