"""Provas sem rede do instalador interativo da loja sandbox."""

from __future__ import annotations

import importlib.util
import io
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

ARQUIVO = Path(__file__).with_name("instalar-appmax-meshcraft-sandbox.py")
SPEC = importlib.util.spec_from_file_location("instalador_appmax", ARQUIVO)
assert SPEC and SPEC.loader
instalador = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(instalador)


class InstalacaoSandboxTest(unittest.TestCase):
    def test_somente_env_sandbox_da_loja_autorizada(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            env = Path(pasta) / "pagamentos.env"
            script = Path(pasta) / "appmax.sh"
            script.touch()
            env.write_text(
                "APPMAX_AUTH_URL=https://auth.sandboxappmax.com.br/oauth2/token\n"
                "APPMAX_API_URL=https://api.sandboxappmax.com.br\n"
                'APPMAX_INSTALACOES={"1888":{"alias":"Meshcraft","sites":["cc06b8c3-043b-4c06-92c5-5ea624e00586"]}}\n'
                "APPMAX_APP_CLIENT_ID=app-id-falso\n"
                "APPMAX_APP_CLIENT_SECRET=app-segredo-falso\n",
                encoding="utf-8",
            )
            with (
                patch.object(instalador, "ENV", env),
                patch.object(instalador, "ROTEIRO_MERCHANT", script),
            ):
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
                with self.assertRaises(instalador.FalhaDeInstalacao):
                    instalador.conferir_ambiente()

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

    def test_credenciais_merchant_seguem_pelo_stdin_sem_sair_na_tela(self) -> None:
        respostas = [
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
        saida = io.StringIO()
        with (
            patch.object(
                instalador,
                "conferir_ambiente",
                return_value=(
                    "app-id-falso",
                    "app-segredo-falso",
                    instalador.SITE_INTERNO,
                ),
            ),
            patch.object(instalador, "conferir_callback"),
            patch.object(instalador, "postar", side_effect=respostas) as postar,
            patch(
                "builtins.input",
                side_effect=["c682b36a-7687-402f-a94d-7e87f31adaba", ""],
            ),
            patch.object(
                instalador.subprocess, "run", return_value=Mock(returncode=0)
            ) as run,
            redirect_stdout(saida),
        ):
            instalador.instalar()
        self.assertEqual(postar.call_count, 3)
        self.assertIn(
            b'"url_callback": "https://meshcraft.top/api/pagamentos/appmax/retorno"',
            postar.call_args_list[1].args[1],
        )
        self.assertEqual(
            run.call_args.kwargs["input"],
            "merchant-id-falso\nmerchant-segredo-falso\n",
        )
        self.assertNotIn("merchant-id-falso", saida.getvalue())
        self.assertNotIn("merchant-segredo-falso", saida.getvalue())
        self.assertIn("INSTALACAO_SANDBOX_OK", saida.getvalue())


if __name__ == "__main__":
    unittest.main()
