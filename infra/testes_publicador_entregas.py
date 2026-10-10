"""Interrupções e concorrência do publicador, sem Docker ou rede."""
import importlib.util
import json
import multiprocessing
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from unittest.mock import Mock

INFRA = Path(__file__).resolve().parent
sys.path.insert(0, str(INFRA))


def carregar(nome, arquivo):
    spec = importlib.util.spec_from_file_location(nome, INFRA / arquivo)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def adquirir_trava_em_processo(pasta, pronta):
    modulo = carregar("publicador_processo", "publicar.py")
    modulo.PUBLICACOES = Path(pasta)
    with modulo.trava_ativacao():
        with modulo.trava_ativacao():
            pronta.set()


class PublicacaoRetomada(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)
        self.mod = carregar("publicacao_local_retoma", "publicacao-local.py")
        self.mod.RAIZ = self.raiz
        self.mod.PASTA = self.raiz / "publicacoes"
        self.mod.PASTA.mkdir()
        self.mod.CELULA = "aplicacao"
        self.antiga, self.nova = "a" * 40, "b" * 40
        self.codigo = self.raiz / "versoes" / "aplicacao" / self.nova
        self.codigo.mkdir(parents=True)
        self.versao = {"imagem": "sha256:" + "b" * 64, "codigo": str(self.codigo)}
        self.prova = str(self.mod.PASTA / "provas" / "teste" / "pacote.json")
        self.estado = {"celula": "aplicacao", "servicos": ["aplicacao"], "endereco": "https://meshcraft.top/",
                       "atual": self.antiga, "atual_versao": {"imagem": "sha256:" + "a" * 64, "codigo": None},
                       "aprovada": {"sha": self.antiga, "imagem": "sha256:" + "a" * 64, "codigo": None},
                       "candidata": self.nova, "candidata_versao": self.versao,
                       "candidata_pacote": {"id": "pacote"},
                       "operacao": {"id": "op", "sha": self.nova, "fase": "configurando", "origem": self.antiga,
                                    "pacote": {"id": "pacote"}, "prova": self.prova}}

    def gravar(self):
        self.mod.salvar(self.mod.PASTA / "aplicacao.json", self.estado)

    def test_C13_retoma_configuracao_aplicada_e_aprova_apos_prova(self):
        self.gravar()
        self.mod.salvar(self.mod.PASTA / "imagens.json", {"services": {"aplicacao": {
            "image": self.versao["imagem"], "volumes": [str(self.codigo) + ":/app:ro"]}}})
        with patch.dict(os.environ, {"TAG": "", "PACOTE_ENSAIADO": ""}), \
             patch.object(self.mod, "conferir_pacote", return_value={"id": "pacote"}), \
             patch.object(self.mod, "provar") as prova, \
             patch.object(self.mod, "medir"):
            self.mod.executar("retomar")
        atual = json.loads((self.mod.PASTA / "aplicacao.json").read_text())
        self.assertEqual(atual["atual"], self.nova)
        self.assertEqual(atual["aprovada"]["sha"], self.nova)
        self.assertEqual(atual["operacao"]["fase"], "concluida")
        prova.assert_called_once()

    def test_C14_abortamento_antigo_nao_altera_nova_versao(self):
        self.estado.update(atual=self.nova, candidata=None)
        self.gravar()
        with patch.dict(os.environ, {"TAG": self.antiga}):
            self.mod.executar("abortar")
        atual = json.loads((self.mod.PASTA / "aplicacao.json").read_text())
        self.assertEqual(atual["atual"], self.nova)
        self.assertEqual(atual["operacao"]["fase"], "configurando")

    def test_recuperacao_interrompida_depois_do_journal_retoma_prova(self):
        self.estado.update(atual=self.antiga, atual_versao={"imagem": "sha256:" + "a" * 64, "codigo": None},
                           candidata=self.nova, recuperacao={"origem": self.nova,
                                                                "alvo": self.antiga, "estado": "tentando"})
        self.gravar()
        with patch.dict(os.environ, {}), \
             patch.object(self.mod, "configuracao_aponta", return_value=True), \
             patch.object(self.mod, "conferir_codigo_docs"), \
             patch.object(self.mod, "politica_mercadopago", return_value={}), \
             patch.object(self.mod, "conferir_ambiente"), \
             patch.object(self.mod, "conferir_mp_pacote"), \
             patch.object(self.mod, "conferir_versao_real") as real, \
             patch.object(self.mod, "provar") as prova:
            self.estado["aprovada"]["codigo"] = str(self.codigo)
            self.estado["atual_versao"]["codigo"] = str(self.codigo)
            self.gravar()
            self.mod.executar("retomar")
        atual = json.loads((self.mod.PASTA / "aplicacao.json").read_text())
        self.assertEqual(atual["recuperacao"]["estado"], "concluida")
        self.assertEqual(atual["operacao"]["fase"], "recuperada")
        real.assert_called_once()
        prova.assert_called_once()

    def test_recuperacao_interrompida_antes_do_journal_repete_mesmo_alvo(self):
        self.estado.update(atual=self.nova, atual_versao=self.versao,
                           recuperacao={"origem": self.nova, "alvo": self.antiga,
                                        "estado": "tentando"})
        self.gravar()
        with patch.dict(os.environ, {}), patch.object(self.mod, "executar") as executar:
            self.mod.retomar(self.mod.PASTA / "aplicacao.json", self.estado)
            executar.assert_called_once_with("recuperar")
            self.assertEqual(os.environ["TAG"], self.antiga)
            self.assertEqual(os.environ["ATUAL_ESPERADA"], self.nova)

    def test_C17_pacote_alterado_impede_configurar(self):
        self.estado["operacao"]["fase"] = "backup_concluido"
        self.gravar()
        with patch.dict(os.environ, {"TAG": self.nova}), \
             patch.object(self.mod, "conferir_pacote", side_effect=ValueError("pacote diferente")), \
             patch.object(self.mod, "pin") as pin:
            with self.assertRaisesRegex(ValueError, "pacote diferente"):
                self.mod.executar("aplicar")
        pin.assert_not_called()
        atual = json.loads((self.mod.PASTA / "aplicacao.json").read_text())
        self.assertEqual(atual["atual"], self.antiga)

    def test_C14_recuperacao_atrasada_nao_chama_roteiro(self):
        publicador = carregar("publicador_retoma", "publicar.py")
        publicador.PUBLICACOES = self.mod.PASTA
        registro = Mock()
        with patch.object(publicador, "journal", return_value={"atual": self.nova}), \
             patch.object(publicador, "executar_roteiro") as roteiro:
            self.assertTrue(publicador.recuperar_versao("aplicacao", registro, "falha antiga", self.antiga))
        roteiro.assert_not_called()

    def test_modo_exclusivo_recusa_sha_avulso(self):
        publicador = carregar("publicador_exclusivo", "publicar.py")
        with patch.dict(os.environ, {"PLATAFORMA_ENTREGAS_EXCLUSIVAS": "1"}), \
             patch.object(publicador, "publicar") as antigo:
            with self.assertRaises(SystemExit):
                publicador.main(["publicar", "aplicacao", self.nova])
        antigo.assert_not_called()

    def test_instalado_recusa_sha_avulso_sem_variavel_ambiente(self):
        publicador = carregar("publicador_instalado", "publicar.py")
        publicador.FERRAMENTAS = Mock()
        publicador.FERRAMENTAS.resolve.return_value = "/usr/local/lib/meshcraft-publicador/v1-teste"
        with patch.dict(os.environ, {"PLATAFORMA_ENTREGAS_EXCLUSIVAS": "0"}), \
             patch.object(publicador, "publicar") as antigo:
            with self.assertRaises(SystemExit):
                publicador.main(["publicar", "aplicacao", self.nova])
        antigo.assert_not_called()

    def test_main_remota_publica_usa_https_sem_remoto_local_nem_credencial(self):
        publicador = carregar("publicador_consulta_publica", "publicar.py")
        consulta = Mock(returncode=0, stdout=self.nova + "\trefs/heads/main\n")
        with patch.object(publicador.subprocess, "run", return_value=consulta) as executar:
            self.assertEqual(publicador.main_remota_publica(), self.nova)
        comando = executar.call_args.args[0]
        ambiente = executar.call_args.kwargs["env"]
        self.assertEqual(comando, ["git", "-c", "credential.helper=", "ls-remote",
                                  "--heads", "https://github.com/abundanciabr/sitesdoreino.git", "main"])
        self.assertNotIn("integrador", comando)
        self.assertEqual(ambiente["GIT_CONFIG_NOSYSTEM"], "1")
        self.assertEqual(ambiente["GIT_CONFIG_GLOBAL"], os.devnull)
        self.assertEqual(ambiente["GIT_TERMINAL_PROMPT"], "0")

    def test_publicacao_recusa_remoto_de_promocao_diferente(self):
        publicador = carregar("publicador_remoto_divergente", "publicar.py")
        publicador.RAIZ = self.raiz
        publicador.PUBLICACOES = self.mod.PASTA
        (self.raiz / "entregas").mkdir()
        (self.raiz / "entregas" / (("a" * 12) + ".json")).write_text(json.dumps({
            "id": "a" * 12, "estado": "integrada na main", "promovida_candidata": self.nova,
            "promocao": {"estado": "remota", "candidata": self.nova, "remoto": "origin"}}))
        with patch.object(publicador, "git", return_value=self.nova), \
             patch.object(publicador, "main_remota_publica") as consultar, \
             patch.object(publicador, "rodar") as docker:
            with self.assertRaisesRegex(ValueError, "remoto da promoção inesperado"):
                publicador.publicar_entrega("a" * 12, "aplicacao")
        consultar.assert_not_called()
        docker.assert_not_called()

    def test_promocao_com_prova_trocada_nao_carrega_imagem(self):
        publicador = carregar("publicador_prova", "publicar.py")
        publicador.RAIZ = self.raiz
        publicador.PUBLICACOES = self.mod.PASTA
        (self.raiz / "entregas").mkdir()
        (self.raiz / "entregas" / (("a" * 12) + ".json")).write_text(json.dumps({
            "id": "a" * 12, "estado": "integrada na main", "promovida_candidata": self.nova,
            "promocao": {"estado": "remota", "candidata": self.nova,
                         "remoto": "integrador", "prova_identidade": "prova-original"}}))
        import ensaio_entregas
        with patch.object(publicador, "git", return_value=self.nova), \
             patch.object(publicador, "main_remota_publica", return_value=self.nova), \
             patch.object(publicador, "journal", return_value=None), \
             patch.object(publicador, "rodar") as docker, \
             patch.object(ensaio_entregas, "verificar_prova", return_value={"identidade": "prova-trocada"}):
            with self.assertRaisesRegex(ValueError, "outra prova"):
                publicador.publicar_entrega("a" * 12, "aplicacao")
        docker.assert_not_called()

    def test_lock_comum_bloqueia_outro_processo_e_aceita_reentrada(self):
        publicador = carregar("publicador_trava", "publicar.py")
        publicador.PUBLICACOES = self.mod.PASTA
        contexto = multiprocessing.get_context("spawn")
        pronta = contexto.Event()
        processo = contexto.Process(target=adquirir_trava_em_processo, args=(str(self.mod.PASTA), pronta))
        try:
            with publicador.trava_ativacao():
                with publicador.trava_ativacao():
                    processo.start()
                    self.assertFalse(pronta.wait(0.5), "outro processo entrou durante a ativação")
            self.assertTrue(pronta.wait(5), "outro processo não retomou após liberar a trava")
            processo.join(5)
            self.assertEqual(processo.exitcode, 0)
        finally:
            if processo.is_alive():
                processo.terminate()
                processo.join(5)

    def test_recuperacao_recusa_container_real_de_outra_versao(self):
        self.estado["atual"] = self.nova
        self.estado["atual_versao"] = self.versao
        alvo = {"imagem": "sha256:" + "a" * 64, "codigo": None}
        def docker(*args):
            if args[:2] == ("docker", "inspect") and "{{.Image}}" in args:
                return "sha256:" + "c" * 64
            if args[:2] == ("docker", "inspect") and "{{json .Mounts}}" in args:
                return "[]"
            if args[:3] == ("docker", "image", "inspect"):
                return args[-1]
            raise AssertionError(args)
        with patch.object(self.mod, "compose", return_value="container-posterior"), \
             patch.object(self.mod, "comando", side_effect=docker):
            with self.assertRaisesRegex(ValueError, "contêiner real difere"):
                self.mod.conferir_execucao_para_recuperar(self.estado, self.nova, alvo)

    def test_prova_nao_aprova_container_com_imagem_diferente(self):
        self.estado["atual"] = self.nova
        def docker(*args):
            if args[:2] == ("docker", "inspect") and "{{json .State}}" in args:
                return json.dumps({"Status": "running", "Running": True})
            if args[:2] == ("docker", "inspect") and "{{.Image}}" in args:
                return "sha256:" + "c" * 64
            if args[:3] == ("docker", "image", "inspect"):
                return self.versao["imagem"]
            raise AssertionError(args)
        with patch.object(self.mod, "compose", return_value="container"), \
             patch.object(self.mod, "comando", side_effect=docker):
            with self.assertRaisesRegex(ValueError, "imagem diferente"):
                self.mod.provar(self.estado, self.nova, self.versao)

    def test_funil_exige_prova_promovida_antes_de_carregar_imagem(self):
        publicador = carregar("publicador_funil", "publicar.py")
        publicador.RAIZ = self.raiz
        publicador.PUBLICACOES = self.mod.PASTA
        (self.raiz / "entregas").mkdir()
        (self.raiz / "entregas" / (("a" * 12) + ".json")).write_text(json.dumps({
            "id": "a" * 12, "estado": "integrada na main", "promovida_candidata": self.nova,
            "promocao": {"estado": "remota", "candidata": self.nova,
                         "remoto": "integrador", "prova_funil_identidade": "original"}}))
        modulo_funil = Mock()
        modulo_funil.topologia.return_value = {"celulas": {}}
        import ensaio_entregas
        with patch.object(publicador, "git", return_value=self.nova), \
             patch.object(publicador, "main_remota_publica", return_value=self.nova), \
             patch.object(publicador, "journal", return_value=None), \
             patch.object(publicador, "carregar_celulas", return_value=modulo_funil), \
             patch.object(publicador, "rodar") as docker, \
             patch.object(ensaio_entregas, "verificar_prova", return_value={"identidade": "trocada"}):
            with self.assertRaisesRegex(ValueError, "outra prova"):
                publicador.publicar_entrega("a" * 12, "funil")
        docker.assert_not_called()

    def test_funil_faz_backup_antes_de_ativar_o_pacote_ensaiado(self):
        publicador = carregar("publicador_funil_ativa", "publicar.py")
        publicador.RAIZ = self.raiz
        publicador.PUBLICACOES = self.mod.PASTA
        publicador.LOGS = self.mod.PASTA / "logs"
        pacote = {"id": "pacote", "imagem_id": "sha256:" + "b" * 64}
        prova = {"identidade": "prova", "nome_funil": "meshcraft-funil-teste-ensaio",
                 "pacote_publicador": pacote,
                 "artefato": {"codigo": str(self.codigo), "bundle": str(self.codigo),
                              "imagem_tar": str(self.raiz / "imagem.tar"),
                              "configuracao_final": str(self.raiz / "config-final")}}
        celulas = Mock()
        celulas.topologia.return_value = {"celulas": {}}
        eventos = []
        celulas.ativar.side_effect = lambda *args, **kwargs: eventos.append(("ativar", args, kwargs))
        def executar_backup(*args, **kwargs):
            eventos.append(("backup", args, kwargs))
            return Mock(returncode=0)
        import ensaio_entregas
        with patch.object(publicador, "carregar_celulas", return_value=celulas), \
             patch.object(publicador, "journal", return_value=None), \
             patch.object(publicador, "rodar", return_value=""), \
             patch.object(publicador, "imagem_id", return_value=pacote["imagem_id"]), \
             patch.object(publicador, "politica_mercadopago", return_value={}), \
             patch.object(publicador, "conferir_ambiente"), \
             patch.object(publicador, "conferir_mp_pacote"), \
             patch.object(publicador, "conferir_codigo_docs"), \
             patch.object(publicador, "identificar", return_value=pacote), \
             patch.object(publicador, "git", return_value=self.nova), \
             patch.object(publicador.subprocess, "run", side_effect=executar_backup), \
             patch.object(ensaio_entregas, "verificar_prova", return_value=prova):
            self.assertEqual(publicador._publicar_funil_entrega("a" * 12, self.nova,
                                                                 {"prova_funil_identidade": "prova"}, {}), 0)
        self.assertEqual([e[0] for e in eventos], ["backup", "ativar"])
        self.assertEqual(eventos[1][1][:4], (self.codigo, pacote["imagem_id"], self.nova, pacote))
        self.assertEqual(eventos[1][2]["nome"], prova["nome_funil"])


if __name__ == "__main__":
    unittest.main()
