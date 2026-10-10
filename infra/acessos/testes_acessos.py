"""Ensaios isolados da fronteira robô -> integrador; nenhuma conta é criada."""
import importlib.util
import base64
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest
from unittest import mock

if sys.platform == "win32":
    pwd_fake = types.ModuleType("pwd")
    pwd_fake.getpwnam = lambda _: types.SimpleNamespace(pw_uid=1001)
    sys.modules.setdefault("pwd", pwd_fake)

ORIGEM = Path(__file__).with_name("robo_broker.py")
ESPECIFICACAO = importlib.util.spec_from_file_location("robo_broker", ORIGEM)
BROKER = importlib.util.module_from_spec(ESPECIFICACAO)
ESPECIFICACAO.loader.exec_module(BROKER)
if sys.platform == "win32":
    BROKER.socket.SO_PEERCRED = 17


def carregar(nome, arquivo):
    spec = importlib.util.spec_from_file_location(nome, Path(__file__).with_name(arquivo))
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


COMANDO = carregar("robo_comando", "robo_comando.py")
D1 = carregar("d1_ruleset", "D1-ruleset.py")
D2 = carregar("d2_chaves", "D2-trocar-chave.py")


class Conexao:
    def __init__(self, pedido, uid=1001):
        self.pedido = json.dumps(pedido).encode() + b"\n"
        self.uid = uid

    def getsockopt(self, *_):
        return struct.pack("3i", 123, self.uid, 1001)

    def recv(self, _):
        bloco, self.pedido = self.pedido, b""
        return bloco


class BrokerTests(unittest.TestCase):
    def test_estado_roda_somente_o_integrador(self):
        processo = types.SimpleNamespace(returncode=0, stdout='{"estado":"ok"}\n')
        with mock.patch.object(BROKER.pwd, "getpwnam", return_value=types.SimpleNamespace(pw_uid=1001)):
            with mock.patch.object(BROKER.subprocess, "run", return_value=processo) as run:
                resposta = BROKER.atender(Conexao(["estado"]))
        self.assertEqual(resposta['codigo'], 0)
        self.assertEqual(json.loads(resposta['saida']), {'estado': 'ok'})
        chamada = run.call_args
        self.assertEqual(chamada.args[0], ["/usr/bin/python3", BROKER.INTEGRADOR, "estado"])
        self.assertEqual(chamada.kwargs["env"]["PLATAFORMA_DIR"], "/var/lib/meshcraft-integrador")
        self.assertEqual(chamada.kwargs["cwd"], "/var/lib/meshcraft-integrador")
        self.assertEqual(chamada.kwargs["env"]["HOME"], "/home/integrador")
        self.assertFalse({"DOCKER_HOST", "GITHUB_TOKEN", "GH_TOKEN"} & set(chamada.kwargs["env"]))

    def test_resposta_excessiva_gera_json_seguro(self):
        processo = types.SimpleNamespace(returncode=0, stdout='{"dado":"' + 'x' * 200001 + '"}\n')
        with mock.patch.object(BROKER.pwd, "getpwnam", return_value=types.SimpleNamespace(pw_uid=1001)):
            with mock.patch.object(BROKER.subprocess, "run", return_value=processo):
                resposta = BROKER.atender(Conexao(["estado"]))
        self.assertEqual(resposta["codigo"], 3)
        self.assertEqual(json.loads(resposta["saida"])["motivo"], "resposta excessiva")
        self.assertNotIn('x' * 100, resposta["saida"])


    def test_consulta_distingue_main_de_ativacao_e_omite_dados_privados(self):
        id_ = "a" * 12
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(BROKER, "FASES", Path(temp)):
            fase = {"id": id_, "fase": "ativação pendente", "candidata": "b" * 40,
                    "celulas": ["aplicacao", "funil"], "ativadas": ["aplicacao"],
                    "atualizada_em": datetime.now(timezone.utc).isoformat(),
                    "diagnostico": {"codigo": "resposta_perdida", "motivo": "/privado/segredo"},
                    "motivo": "/privado/marcador-inofensivo", "credencial": "marcador"}
            (Path(temp) / (id_ + ".json")).write_text(json.dumps(fase), encoding="utf-8")
            entrada = {"id": id_, "estado": "integrada na main", "candidata": "b" * 40}
            saida = json.loads(BROKER.acrescentar_operacao(json.dumps(entrada)))
            self.assertEqual(saida["estado"], "integrada na main")
            self.assertEqual(saida["operacao"]["fase"], "ativação pendente")
            self.assertEqual(saida["operacao"]["ativadas"], ["aplicacao"])
            self.assertEqual(saida["operacao"]["diagnostico"]["codigo"], "resposta_perdida")
            self.assertNotIn("marcador", json.dumps(saida))
            lista = json.loads(BROKER.acrescentar_operacao(json.dumps([entrada])))
            self.assertEqual(lista[0], saida)

    def test_consulta_com_fase_corrompida_preserva_estado_da_entrega(self):
        id_ = "a" * 12
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(BROKER, "FASES", Path(temp)):
            (Path(temp) / (id_ + ".json")).write_text("{", encoding="utf-8")
            entrada = {"id": id_, "estado": "integrada na main"}
            saida = json.loads(BROKER.acrescentar_operacao(json.dumps(entrada)))
            self.assertEqual(saida["estado"], entrada["estado"])
            self.assertEqual(saida["operacao"]["estado"], "acompanhamento indisponível")

    def test_fase_de_outra_candidata_nao_confirma_ativacao(self):
        id_ = "a" * 12
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(BROKER, "FASES", Path(temp)):
            (Path(temp) / (id_ + ".json")).write_text(json.dumps({
                "id": id_, "fase": "ativa", "candidata": "b" * 40,
                "atualizada_em": datetime.now(timezone.utc).isoformat()}), encoding="utf-8")
            saida = json.loads(BROKER.acrescentar_operacao(json.dumps({
                "id": id_, "candidata12": "c" * 12})))
            self.assertEqual(saida["operacao"]["estado"], "acompanhamento incompleto")

    def test_heartbeat_antigo_nao_afirma_worker_ativo(self):
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(BROKER, "FASES", Path(temp)):
            antigo = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
            (Path(temp) / "canal.json").write_text(json.dumps({
                "em": antigo, "estado": "em andamento", "segredo": "nao devolver"}), encoding="utf-8")
            canal = BROKER._canal_publico()
            self.assertEqual(canal["estado"], "acompanhamento desatualizado")
            self.assertEqual(canal["ultimo_estado_registrado"], "em andamento")

    def test_fase_final_antiga_preserva_diagnostico_historico(self):
        id_ = "a" * 12
        antigo = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(BROKER, "FASES", Path(temp)):
            (Path(temp) / (id_ + ".json")).write_text(json.dumps({
                "id": id_, "fase": "falha no ensaio", "candidata": "b" * 40,
                "atualizada_em": antigo, "ultima_falha": {"codigo": "ensaio_reprovado",
                    "motivo": "SEGREDO_TESTE"}}), encoding="utf-8")
            saida = json.loads(BROKER.acrescentar_operacao(json.dumps({
                "id": id_, "candidata": "b" * 40})))
            self.assertEqual(saida["operacao"]["fase"], "falha no ensaio")
            self.assertEqual(saida["operacao"]["estado"], "registro histórico")
            self.assertEqual(saida["operacao"]["atualizada_em"], antigo)
            self.assertEqual(saida["operacao"]["ultima_falha"]["codigo"], "ensaio_reprovado")
            self.assertNotIn("SEGREDO_TESTE", json.dumps(saida))

    def test_sem_horario_preserva_fase_e_marca_incompleto(self):
        id_ = "a" * 12
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(BROKER, "FASES", Path(temp)):
            (Path(temp) / (id_ + ".json")).write_text(json.dumps({
                "id": id_, "fase": "ativa", "candidata": "b" * 40,
                "diagnostico": {"codigo": "ativacao_nao_confirmada"}}), encoding="utf-8")
            saida = json.loads(BROKER.acrescentar_operacao(json.dumps({
                "id": id_, "candidata": "b" * 40})))
            self.assertEqual(saida["operacao"]["estado"], "acompanhamento incompleto")
            self.assertEqual(saida["operacao"]["fase"], "ativa")
            self.assertEqual(saida["operacao"]["diagnostico"]["codigo"], "ativacao_nao_confirmada")

    def test_tentativa_em_andamento_sem_heartbeat_nao_confirma_execucao(self):
        id_ = "a" * 12
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(BROKER, "FASES", Path(temp)):
            (Path(temp) / (id_ + ".json")).write_text(json.dumps({
                "id": id_, "fase": "ensaiando", "candidata": "b" * 40,
                "atualizada_em": datetime.now(timezone.utc).isoformat(),
                "em_andamento": True}), encoding="utf-8")
            saida = json.loads(BROKER.acrescentar_operacao(json.dumps({
                "id": id_, "candidata": "b" * 40})))
            self.assertEqual(saida["canal"]["estado"], "acompanhamento indisponível")
            self.assertTrue(saida["operacao"]["em_andamento_registrado"])
            self.assertEqual(saida["operacao"]["execucao"], "não confirmada nesta consulta")

    def test_pid_reutilizado_encerrado_ou_antigo_nao_confirma_execucao(self):
        fase = {"fase": "ensaiando", "candidata": "b" * 40,
                "em_andamento": True, "execucao_processo": {"pid": 123, "inicio": 777}}
        with mock.patch.object(BROKER.sys, "platform", "linux"):
            with mock.patch.object(BROKER.os, "geteuid", return_value=1001, create=True):
                with mock.patch.object(BROKER, "_proc_identidade", return_value=(1001, 777)):
                    self.assertTrue(BROKER._fase_publica(fase)["em_andamento"])
                for observado in ((1001, 778), None, (1002, 777)):
                    with mock.patch.object(BROKER, "_proc_identidade", return_value=observado):
                        publico = BROKER._fase_publica(fase)
                        self.assertNotIn("em_andamento", publico)
                        self.assertEqual(publico["execucao"], "não confirmada nesta consulta")
                antigo = dict(fase)
                antigo.pop("execucao_processo")
                self.assertNotIn("em_andamento", BROKER._fase_publica(antigo))

    def test_comando_privilegiado_e_outro_uid_sao_recusados_sem_execucao(self):
        with mock.patch.object(BROKER.pwd, "getpwnam", return_value=types.SimpleNamespace(pw_uid=1001)):
            with mock.patch.object(BROKER.subprocess, "run") as run:
                for pedido in (["integrar"], ["promover", "abc"], ["sh", "-c", "id"]):
                    with self.assertRaises(ValueError):
                        BROKER.atender(Conexao(pedido))
                with self.assertRaises(ValueError):
                    BROKER.atender(Conexao(["estado"], uid=1002))
                run.assert_not_called()

    def test_paths_e_argumentos_invalidos_nao_atingem_o_git(self):
        sha = "a" * 40
        pedidos = [
            ["estado", "/etc/passwd"],
            ["consultar", "../../etc/passwd"],
            ["entregar", "--ramo", "../../etc/passwd", "--commit", sha, "--base", sha],
            ["entregar", "--ramo", "/etc/passwd", "--commit", sha, "--base", sha],
            ["entregar", "--ramo", "codex/entrega/a", "--commit", sha, "--base", sha,
             "--remoto", "integrador"],
            ["entregar", "--ramo", "codex/entrega/a", "--commit", sha, "--base", sha,
             "--origem", "$(id)"],
        ]
        with mock.patch.object(BROKER.pwd, "getpwnam", return_value=types.SimpleNamespace(pw_uid=1001)):
            with mock.patch.object(BROKER.subprocess, "run") as run:
                for pedido in pedidos:
                    with self.subTest(pedido=pedido), self.assertRaises(ValueError):
                        BROKER.atender(Conexao(pedido))
                run.assert_not_called()


class ComandoTests(unittest.TestCase):
    def test_comando_forcado_recusa_shell_antes_de_abrir_socket(self):
        with mock.patch.dict(os.environ, {"SSH_ORIGINAL_COMMAND": "estado; /bin/sh"}):
            with mock.patch.object(COMANDO.socket, "socket") as socket_ctor:
                with self.assertRaises(ValueError):
                    COMANDO.principal()
                socket_ctor.assert_not_called()

    def test_comando_distingue_recusa_de_canal_indisponivel(self):
        with mock.patch.dict(os.environ, {"SSH_ORIGINAL_COMMAND": "sh -c id"}):
            with self.assertRaises(COMANDO.ComandoRecusado):
                COMANDO.principal()
        with mock.patch.dict(os.environ, {"SSH_ORIGINAL_COMMAND": "estado"}):
            with mock.patch.object(COMANDO.socket, "AF_UNIX", 1, create=True):
                with mock.patch.object(COMANDO.socket, "socket", side_effect=OSError("sem socket")):
                    with self.assertRaises(OSError):
                        COMANDO.principal()


class ChavesTests(unittest.TestCase):
    def test_retirada_e_restauracao_preservam_chave_adicionada_depois(self):
        linha_antiga = "ssh-ed25519 " + base64.b64encode(b"chave antiga de teste").decode() + " antiga\n"
        linha_nova = "ssh-ed25519 " + base64.b64encode(b"chave nova de teste").decode() + " nova\n"
        alvo = D2.fingerprint(linha_antiga)
        with tempfile.TemporaryDirectory() as temp:
            chaves = Path(temp) / "authorized_keys"
            backups = Path(temp) / "backups"
            chaves.write_text(linha_antiga, encoding="utf-8")
            with (
                mock.patch.object(D2, "CHAVES", chaves),
                mock.patch.object(D2, "BACKUPS", backups),
                mock.patch.object(D2.os, "geteuid", return_value=0, create=True),
                mock.patch.object(D2.os, "fchown", create=True),
                mock.patch.object(D2.os, "fchmod", create=True),
            ):
                with mock.patch.object(sys, "argv", ["d2", "retirar", alvo, "--aplicar"]):
                    D2.principal()
                copia = next(backups.iterdir())
                self.assertEqual(chaves.read_text(encoding="utf-8"), "")
                chaves.write_text(linha_nova, encoding="utf-8")
                with mock.patch.object(
                    sys, "argv", ["d2", "restaurar", alvo, "--backup", str(copia), "--aplicar"]
                ):
                    D2.principal()
                self.assertEqual(chaves.read_text(encoding="utf-8"), linha_nova + linha_antiga)


class RulesetTests(unittest.TestCase):
    def setUp(self):
        self.repo = {"owner": {"type": "User"}, "private": False, "default_branch": "main"}
        self.regra = D1.plano()
        self.atual = None
        self.enviados = []

    def gh(self, endpoint, *args, **kwargs):
        if endpoint == D1.REPO:
            return self.repo
        if endpoint.endswith("/rulesets?includes_parents=false"):
            return [] if self.atual is None else [{"id": self.atual["id"], "name": self.atual["name"]}]
        if self.atual is not None and endpoint == f"{D1.REPO}/rulesets/{self.atual['id']}":
            return self.atual
        if endpoint.endswith("/keys"):
            return [{"title": "integrador-vps", "read_only": False}]
        raise AssertionError(endpoint)

    def enviar(self, metodo, endpoint, dados):
        self.enviados.append((metodo, endpoint))
        self.atual = dict(dados, id=42)
        return self.atual

    def test_aplicar_uma_vez_e_repetir_sem_criar_regra_duplicada(self):
        with (
            mock.patch.object(D1, "gh", side_effect=self.gh),
            mock.patch.object(D1, "enviar", side_effect=self.enviar),
            mock.patch.object(sys, "argv", ["d1", "aplicar"]),
        ):
            D1.principal()
            D1.principal()
        self.assertEqual(self.enviados, [("POST", D1.REPO + "/rulesets")])

    def test_resposta_real_omite_update_false_e_reaplicacao_e_idempotente(self):
        def enviar_com_resposta_da_api(metodo, endpoint, dados):
            self.enviados.append((metodo, endpoint))
            self.atual = json.loads(json.dumps(dados))
            self.atual["id"] = 24822061
            self.atual["rules"][0] = {"type": "update"}
            return self.atual

        with (
            mock.patch.object(D1, "gh", side_effect=self.gh),
            mock.patch.object(D1, "enviar", side_effect=enviar_com_resposta_da_api),
            mock.patch.object(sys, "argv", ["d1", "aplicar"]),
        ):
            D1.principal()
            D1.principal()
        self.assertEqual(self.enviados, [("POST", D1.REPO + "/rulesets")])

    def test_update_true_continua_sendo_divergencia(self):
        self.atual = json.loads(json.dumps(self.regra))
        self.atual["id"] = 24822061
        self.atual["rules"][0]["parameters"]["update_allows_fetch_and_merge"] = True
        with (
            mock.patch.object(D1, "gh", side_effect=self.gh),
            mock.patch.object(D1, "enviar") as enviar,
            mock.patch.object(sys, "argv", ["d1", "aplicar"]),
        ):
            with self.assertRaisesRegex(RuntimeError, "regra existente diverge"):
                D1.principal()
            enviar.assert_not_called()

    def test_resposta_com_update_true_nao_confirma_aplicacao(self):
        def enviar_com_resposta_divergente(metodo, endpoint, dados):
            self.enviados.append((metodo, endpoint))
            self.atual = json.loads(json.dumps(dados))
            self.atual["id"] = 24822061
            self.atual["rules"][0]["parameters"]["update_allows_fetch_and_merge"] = True
            return self.atual

        with (
            mock.patch.object(D1, "gh", side_effect=self.gh),
            mock.patch.object(D1, "enviar", side_effect=enviar_com_resposta_divergente),
            mock.patch.object(sys, "argv", ["d1", "aplicar"]),
        ):
            with self.assertRaisesRegex(RuntimeError, "resposta não confirmou"):
                D1.principal()

    def test_recusa_duas_deploy_keys_com_escrita(self):
        def gh_com_duas(endpoint, *args, **kwargs):
            if endpoint.endswith("/keys"):
                return [
                    {"title": "integrador-vps", "read_only": False},
                    {"title": "outra", "read_only": False},
                ]
            return self.gh(endpoint, *args, **kwargs)

        with (
            mock.patch.object(D1, "gh", side_effect=gh_com_duas),
            mock.patch.object(D1, "enviar") as enviar,
            mock.patch.object(sys, "argv", ["d1", "aplicar"]),
        ):
            with self.assertRaises(RuntimeError):
                D1.principal()
            enviar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
