"""Provas sem rede do instalador interativo da loja sandbox."""

from __future__ import annotations

import importlib.util
import io
import json
import shutil
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from unittest.mock import Mock, patch

ARQUIVO = Path(__file__).with_name("instalar-appmax-meshcraft-sandbox.py")
SPEC = importlib.util.spec_from_file_location("instalador_appmax", ARQUIVO)
assert SPEC and SPEC.loader
instalador = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(instalador)


class InstalacaoSandboxTest(unittest.TestCase):
    def test_http_403_informa_etapa_sem_expor_credenciais(self) -> None:
        with patch.object(
            instalador.subprocess,
            "run",
            return_value=Mock(returncode=0, stdout=b"{}\n403"),
        ) as executar:
            with self.assertRaisesRegex(
                instalador.FalhaDeInstalacao, "HTTP 403 em OAuth APP"
            ):
                instalador.postar(
                    instalador.AUTH,
                    b"client_secret=segredo-falso",
                    form=True,
                )
        self.assertNotIn("segredo-falso", " ".join(executar.call_args.args[0]))
        self.assertIn(b"segredo-falso", executar.call_args.kwargs["input"])

    def test_erro_producao_nao_indica_painel_sandbox(self) -> None:
        with patch.object(instalador.subprocess, "run", return_value=Mock(returncode=0, stdout=b"{}\n403")):
            with self.assertRaises(instalador.FalhaDeInstalacao) as erro:
                instalador.postar("https://api.appmax.com.br/app/authorize", b"{}")
        self.assertIn("produção", str(erro.exception))
        self.assertNotIn("painel sandbox", str(erro.exception))

    def test_curl_envia_json_e_bearer_sem_segredos_na_linha_de_comando(self) -> None:
        if not shutil.which("curl"):
            self.skipTest("curl indisponível")

        recebido = {}

        class Resposta(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                recebido["body"] = self.rfile.read(int(self.headers["Content-Length"]))
                recebido["authorization"] = self.headers["Authorization"]
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"data":{"token":"ok"}}')

            def log_message(self, *args: object) -> None:
                pass

        servidor = ThreadingHTTPServer(("127.0.0.1", 0), Resposta)
        servidor_thread = Thread(target=servidor.serve_forever, daemon=True)
        servidor_thread.start()
        body = json.dumps({"nome": 'Loja "Meshcraft"'}).encode()
        try:
            resposta = instalador.postar(
                f"http://127.0.0.1:{servidor.server_port}/app/authorize",
                body,
                bearer="token-app-falso",
            )
        finally:
            servidor.shutdown()
            servidor.server_close()
            servidor_thread.join()
        self.assertEqual(resposta, {"data": {"token": "ok"}})
        self.assertEqual(recebido["body"], body)
        self.assertEqual(recebido["authorization"], "Bearer token-app-falso")

    def test_sandbox_e_producao_aceitam_ids_diferentes(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            env = Path(pasta) / "pagamentos.env"
            env.write_text(
                "APPMAX_AUTH_URL=https://auth.sandboxappmax.com.br/oauth2/token\n"
                "APPMAX_API_URL=https://api.sandboxappmax.com.br\n"
                'APPMAX_INSTALACOES={"1888":{"alias":"Meshcraft","sites":["cc06b8c3-043b-4c06-92c5-5ea624e00586"]}}\n'
                "APPMAX_APP_CLIENT_ID=app-id-falso\n"
                "APPMAX_APP_CLIENT_SECRET=app-segredo-falso\n",
                encoding="utf-8",
            )
            with patch.object(instalador, "ENV", env):
                self.assertEqual(
                    instalador.conferir_ambiente(),
                    (
                        "app-id-falso",
                        "app-segredo-falso",
                        "cc06b8c3-043b-4c06-92c5-5ea624e00586",
                    ),
                )
                env.write_text(
                    env.read_text(encoding="utf-8").replace("1888", "1889"),
                    encoding="utf-8",
                )
                self.assertEqual(instalador.conferir_ambiente()[2], instalador.SITE_INTERNO)
                env.write_text(env.read_text(encoding="utf-8").replace("sandboxappmax", "appmax"), encoding="utf-8")
                self.assertEqual(instalador.endpoints()[2], "https://admin.appmax.com.br")
                self.assertEqual(instalador.conferir_ambiente()[2], instalador.SITE_INTERNO)

    def test_retorno_precisa_remover_o_token_da_url(self) -> None:
        resposta = urllib.error.HTTPError(
            instalador.CALLBACK,
            302,
            "Found",
            {"Location": "https://meshcraft.top/"},
            None,
        )
        opener = Mock()
        opener.open.side_effect = resposta
        with patch.object(
            instalador.urllib.request, "build_opener", return_value=opener
        ):
            instalador.conferir_callback()
        resposta.headers["Location"] = "https://meshcraft.top/?token=vazou"
        with patch.object(
            instalador.urllib.request, "build_opener", return_value=opener
        ):
            with self.assertRaises(instalador.FalhaDeInstalacao):
                instalador.conferir_callback()

    RESPOSTAS_ATE_O_PAR = [
        {"access_token": "token-app", "token_type": "Bearer"},
        {"data": {"token": "hashdeusoUnico123"}},
        {
            "data": {
                "client": {
                    "client_id": "merchant-id-falso",
                    "client_secret": "merchant-segredo-falso",
                }
            }
        },
    ]
    VALIDACAO_OK = [
        {"access_token": "token-merchant", "token_type": "Bearer"},
        {"data": {"products": []}},
    ]

    def instalar_em(self, pasta: str, auth: str, api: str, respostas: list, entradas: list):
        env = Path(pasta) / "pagamentos.env"
        env.write_text(
            f"APPMAX_AUTH_URL={auth}\n"
            f"APPMAX_API_URL={api}\n"
            'APPMAX_INSTALACOES={"1888":{"alias":"Meshcraft","sites":["cc06b8c3-043b-4c06-92c5-5ea624e00586"]}}\n'
            "APPMAX_APP_CLIENT_ID=app-id-falso\n"
            "APPMAX_APP_CLIENT_SECRET=app-segredo-falso\n"
            "APPMAX_CARD_ENABLED_SITES=cc06b8c3-043b-4c06-92c5-5ea624e00586\n"
            "APPMAX_MERCHANT_CLIENT_ID=antigo\n"
            "APPMAX_MERCHANT_CLIENT_ID=antigo-repetido\n"
            "OUTRA=fica\n",
            encoding="utf-8",
        )
        saida = io.StringIO()
        with (
            patch.object(instalador, "ENV", env),
            patch.object(instalador, "conferir_callback"),
            patch.object(instalador, "postar", side_effect=respostas) as postar,
            patch(
                "builtins.input",
                side_effect=["c682b36a-7687-402f-a94d-7e87f31adaba", "", *entradas],
            ),
            patch.object(instalador.subprocess, "run") as run,
            redirect_stdout(saida),
        ):
            try:
                instalador.instalar()
                erro = None
            except instalador.FalhaDeInstalacao as exc:
                erro = exc
        run.assert_not_called()
        return env, postar, saida.getvalue(), erro

    def test_producao_com_cartao_ligado_grava_par_merchant_com_copia(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            env, postar, saida, erro = self.instalar_em(
                pasta,
                instalador.AUTH_PRODUCAO,
                instalador.API_PRODUCAO,
                self.RESPOSTAS_ATE_O_PAR + self.VALIDACAO_OK,
                [],
            )
            self.assertIsNone(erro)
            texto = env.read_text(encoding="utf-8")
            copias = list(Path(pasta).glob("pagamentos.env.bak-instalador-*"))
            self.assertEqual(len(copias), 1)
            self.assertIn("APPMAX_MERCHANT_CLIENT_ID=antigo-repetido\n", copias[0].read_text(encoding="utf-8"))
            sobras = [p.name for p in Path(pasta).iterdir() if p.name.startswith(".instalador-")]
        self.assertEqual(sobras, [])
        self.assertIn("APPMAX_MERCHANT_CLIENT_ID=merchant-id-falso\n", texto)
        self.assertIn("APPMAX_MERCHANT_CLIENT_SECRET=merchant-segredo-falso\n", texto)
        self.assertNotIn("antigo", texto)
        self.assertIn("OUTRA=fica\n", texto)
        self.assertIn("APPMAX_CARD_ENABLED_SITES=cc06b8c3", texto)
        self.assertEqual(postar.call_args_list[3].args[0], instalador.AUTH_PRODUCAO)
        self.assertIn(b"merchant-segredo-falso", postar.call_args_list[3].args[1])
        self.assertEqual(postar.call_args_list[4].args[0], f"{instalador.API_PRODUCAO}/v1/products")
        self.assertEqual(postar.call_args_list[4].kwargs["bearer"], "token-merchant")
        self.assertEqual(postar.call_args_list[4].kwargs["metodo"], "GET")
        self.assertIn(
            b'"url_callback": "https://meshcraft.top/api/pagamentos/appmax/retorno"',
            postar.call_args_list[1].args[1],
        )
        self.assertNotIn("merchant-id-falso", saida)
        self.assertNotIn("merchant-segredo-falso", saida)
        self.assertIn("INSTALACAO_OK", saida)
        self.assertIn("produção", saida)

    def test_sandbox_valida_no_sandbox_e_grava(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            env, postar, saida, erro = self.instalar_em(
                pasta,
                instalador.AUTH_SANDBOX,
                instalador.API_SANDBOX,
                self.RESPOSTAS_ATE_O_PAR + self.VALIDACAO_OK,
                [],
            )
            texto = env.read_text(encoding="utf-8")
        self.assertIsNone(erro)
        self.assertEqual(postar.call_args_list[3].args[0], instalador.AUTH_SANDBOX)
        self.assertEqual(postar.call_args_list[4].args[0], f"{instalador.API_SANDBOX}/v1/products")
        self.assertIn("APPMAX_MERCHANT_CLIENT_SECRET=merchant-segredo-falso\n", texto)
        self.assertIn("INSTALACAO_OK", saida)

    def test_validacao_tenta_de_novo_e_desistencia_nao_grava(self) -> None:
        recusa = instalador.FalhaDeInstalacao("HTTP 401 em OAuth MERCHANT")
        with tempfile.TemporaryDirectory() as pasta:
            env, postar, saida, erro = self.instalar_em(
                pasta,
                instalador.AUTH_PRODUCAO,
                instalador.API_PRODUCAO,
                self.RESPOSTAS_ATE_O_PAR + [recusa, recusa],
                ["", "n"],
            )
            env_antes = env.read_text(encoding="utf-8")
            copias = list(Path(pasta).glob("pagamentos.env.bak-instalador-*"))
        self.assertIsNotNone(erro)
        self.assertIn("nada foi gravado", str(erro))
        self.assertNotIn("merchant-segredo-falso", str(erro))
        self.assertEqual(postar.call_count, 5)
        self.assertEqual(copias, [])
        self.assertIn("APPMAX_MERCHANT_CLIENT_ID=antigo\n", env_antes)
        self.assertNotIn("merchant-", env_antes)

    def test_curl_get_sem_corpo_com_bearer(self) -> None:
        if not shutil.which("curl"):
            self.skipTest("curl indisponível")
        recebido = {}

        class Resposta(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                recebido["path"] = self.path
                recebido["authorization"] = self.headers["Authorization"]
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"data":{"products":[]}}')

            def log_message(self, *args: object) -> None:
                pass

        servidor = ThreadingHTTPServer(("127.0.0.1", 0), Resposta)
        servidor_thread = Thread(target=servidor.serve_forever, daemon=True)
        servidor_thread.start()
        try:
            resposta = instalador.postar(
                f"http://127.0.0.1:{servidor.server_port}/v1/products",
                b"",
                bearer="token-merchant-falso",
                etapa="leitura de produtos MERCHANT",
                metodo="GET",
            )
        finally:
            servidor.shutdown()
            servidor.server_close()
            servidor_thread.join()
        self.assertEqual(resposta, {"data": {"products": []}})
        self.assertEqual(recebido["path"], "/v1/products")
        self.assertEqual(recebido["authorization"], "Bearer token-merchant-falso")


if __name__ == "__main__":
    unittest.main()
