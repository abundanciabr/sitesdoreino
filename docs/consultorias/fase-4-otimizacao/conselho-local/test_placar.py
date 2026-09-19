import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import placar


PARTICIPANTES = ("codex", "claude", "antigravity")
PEERS = {
    "codex": ("claude", "antigravity"),
    "claude": ("codex", "antigravity"),
    "antigravity": ("codex", "claude"),
}
T1 = "2026-09-12T10:00:00-03:00"
T2 = "2026-09-12T10:01:00-03:00"
T3 = "2026-09-12T10:02:00-03:00"
T4 = "2026-09-12T10:03:00-03:00"
T5 = "2026-09-12T10:04:00-03:00"
T6 = "2026-09-12T10:05:00-03:00"


def proposta(
    identificador="CODEX-001",
    autor="codex",
    problema="coleta-real",
    registrado_em=T1,
):
    return {
        "tipo": "proposta",
        "id": identificador,
        "autor": autor,
        "problema": problema,
        "titulo": "Medir antes de decidir",
        "baseline": "evidencia antes",
        "aceite": "resultado completo",
        "registrado_em": registrado_em,
    }


def voto(
    item,
    autor,
    decisao="aprovar",
    importancia=2,
    registrado_em=T2,
):
    return {
        "tipo": "voto",
        "proposta": item["id"],
        "autor": autor,
        "proposta_sha256": placar.assinatura(item),
        "decisao": decisao,
        "importancia": importancia,
        "justificativa": "A prova fecha o problema.",
        "registrado_em": registrado_em,
    }


def implementacao(
    item,
    autor=None,
    minutos_totais=10.0,
    custo_reais=None,
    fonte_custo="",
    registrado_em=T4,
):
    return {
        "tipo": "implementacao",
        "proposta": item["id"],
        "autor": autor or item["autor"],
        "proposta_sha256": placar.assinatura(item),
        "prova": "caminho/saida.txt",
        "resultado": "resultado observado",
        "minutos_totais": minutos_totais,
        "custo_reais": custo_reais,
        "fonte_custo": fonte_custo,
        "registrado_em": registrado_em,
    }


def verificacao(
    item,
    execucao,
    autor,
    decisao="confirmar",
    registrado_em=T5,
):
    return {
        "tipo": "verificacao",
        "proposta": item["id"],
        "autor": autor,
        "implementacao_sha256": placar.assinatura(execucao),
        "decisao": decisao,
        "justificativa": "A evidencia confirma o aceite.",
        "prova": "caminho/saida.txt",
        "registrado_em": registrado_em,
    }


def registros_completos(
    identificador="CODEX-001",
    autor="codex",
    problema="coleta-real",
    importancias=(3, 2),
    custo_reais=4.5,
):
    item = proposta(identificador, autor, problema)
    peer_1, peer_2 = PEERS[autor]
    voto_1 = voto(item, peer_1, importancia=importancias[0], registrado_em=T2)
    voto_2 = voto(item, peer_2, importancia=importancias[1], registrado_em=T3)
    execucao = implementacao(
        item,
        custo_reais=custo_reais,
        fonte_custo="medicao local" if custo_reais is not None else "",
    )
    verificacao_1 = verificacao(item, execucao, peer_1, registrado_em=T5)
    verificacao_2 = verificacao(item, execucao, peer_2, registrado_em=T6)
    return [item, voto_1, voto_2, execucao, verificacao_1, verificacao_2]


class PlacarTest(unittest.TestCase):
    def test_entrega_por_outra_ia_nao_pontua_sem_acordo_de_autoria(self):
        registros = registros_completos()
        registros[3]["autor"] = "claude"
        for parecer in registros[4:]:
            parecer["implementacao_sha256"] = placar.assinatura(registros[3])
        resultado = placar.apurar(registros)
        self.assertEqual(resultado["propostas"][0]["estado"], "autoria_pendente")
        self.assertEqual(resultado["propostas"][0]["pontos"], 0)
        participantes = self.participantes_por_id(resultado)
        self.assertEqual(participantes["codex"]["minutos_totais"], 0)
        self.assertEqual(participantes["claude"]["minutos_totais"], 10)

    def test_custo_parcial_preserva_a_parcela_conhecida_sem_inventar_total(self):
        registros = registros_completos(custo_reais=7)
        registros += registros_completos("CODEX-002", problema="outro", custo_reais=None)
        resultado = placar.apurar(registros)
        codex = self.participantes_por_id(resultado)["codex"]
        self.assertIsNone(codex["custo_reais"])
        self.assertEqual(codex["custo_conhecido_reais"], 7)
        self.assertIn("R$ 7.00 conhecidos; total não medido", placar.renderizar(resultado))

    def participantes_por_id(self, resultado):
        participantes = resultado["participantes"]
        self.assertEqual(set(PARTICIPANTES), {item["id"] for item in participantes})
        for item in participantes:
            self.assertIsInstance(item["contribuicoes"], int)
        return {item["id"]: item for item in participantes}

    def assert_erro_acionavel(self, registros, trecho):
        with self.assertRaises(ValueError) as contexto:
            placar.apurar(registros)
        mensagem = str(contexto.exception)
        self.assertRegex(
            mensagem,
            r"(?i)(consolide|confira|corrija|obtenha|preencha|remova|resolva|solicite|use|informe|ajuste)",
        )
        self.assertIn(trecho.lower(), mensagem.lower())

    def test_assinatura_usa_json_canonico_com_unicode(self):
        registro = {"titulo": "Ação", "autor": "codex", "ordem": 1}
        serializado = json.dumps(
            registro,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        esperado = hashlib.sha256(serializado.encode("utf-8")).hexdigest()

        self.assertEqual(esperado, placar.assinatura(registro))

    def test_vazio_nao_define_ranking_e_mantem_custos_desconhecidos(self):
        resultado = placar.apurar([])

        self.assertEqual([], resultado["propostas"])
        self.assertFalse(resultado["ranking_definido"])
        participantes = self.participantes_por_id(resultado)
        for participante in participantes.values():
            self.assertEqual(0, participante["pontos"])
            self.assertEqual(0, participante["contribuicoes"])
            self.assertEqual(0, participante["minutos_totais"])
            self.assertIsNone(participante["custo_reais"])

    def test_dois_votos_aprovados_aguardam_implementacao(self):
        item = proposta()
        registros = [
            item,
            voto(item, "claude", importancia=3, registrado_em=T2),
            voto(item, "antigravity", importancia=2, registrado_em=T3),
        ]

        resultado = placar.apurar(registros)

        self.assertEqual("aguarda_implementacao", resultado["propostas"][0]["estado"])
        self.assertEqual(0, resultado["propostas"][0]["pontos"])
        self.assertFalse(resultado["ranking_definido"])

    def test_reprovacao_de_peer_reprova_proposta(self):
        item = proposta()
        registros = [
            item,
            voto(item, "claude", registrado_em=T2),
            voto(item, "antigravity", "reprovar", 0, T3),
        ]

        resultado = placar.apurar(registros)

        self.assertEqual("reprovada", resultado["propostas"][0]["estado"])
        self.assertEqual(0, resultado["propostas"][0]["pontos"])

    def test_fluxo_completo_pontua_pela_menor_importancia(self):
        registros = registros_completos(importancias=(3, 2), custo_reais=4.5)

        resultado = placar.apurar(registros)

        proposta_apurada = resultado["propostas"][0]
        self.assertEqual("pontua", proposta_apurada["estado"])
        self.assertEqual(2, proposta_apurada["pontos"])
        self.assertEqual(placar.assinatura(registros[0]), proposta_apurada["sha256"])
        participantes = self.participantes_por_id(resultado)
        self.assertEqual(2, participantes["codex"]["pontos"])
        self.assertEqual(1, participantes["codex"]["contribuicoes"])
        self.assertEqual(10.0, participantes["codex"]["minutos_totais"])
        self.assertEqual(4.5, participantes["codex"]["custo_reais"])
        self.assertFalse(resultado["ranking_definido"])

    def test_implementacao_sem_votos_nao_pontua_mas_contabiliza_trabalho(self):
        item = proposta()
        execucao = implementacao(
            item,
            autor="claude",
            minutos_totais=12.5,
            custo_reais=7.25,
            fonte_custo="fatura",
            registrado_em=T2,
        )

        resultado = placar.apurar([item, execucao])

        self.assertEqual("aguarda_votos", resultado["propostas"][0]["estado"])
        self.assertEqual(0, resultado["propostas"][0]["pontos"])
        participantes = self.participantes_por_id(resultado)
        self.assertEqual(0, participantes["codex"]["minutos_totais"])
        self.assertEqual(12.5, participantes["claude"]["minutos_totais"])
        self.assertEqual(7.25, participantes["claude"]["custo_reais"])

    def test_autovoto_e_dados_basicos_invalidos_sao_recusados(self):
        item = proposta()
        casos = {
            "autovoto": ([item, voto(item, "codex")], "autovoto"),
            "autor": ([proposta(autor="outro")], "autor"),
            "tipo": (
                [{"tipo": "misterio", "autor": "codex", "registrado_em": T1}],
                "tipo",
            ),
            "fuso": ([proposta(registrado_em="2026-09-12T10:00:00")], "fuso"),
        }
        for nome, (registros, trecho) in casos.items():
            with self.subTest(nome=nome):
                self.assert_erro_acionavel(registros, trecho)

    def test_hash_alterado_em_voto_ou_verificacao_e_recusado(self):
        item = proposta()
        voto_alterado = voto(item, "claude")
        voto_alterado["proposta_sha256"] = "0" * 64

        execucao = implementacao(item)
        verificacao_alterada = verificacao(item, execucao, "claude")
        verificacao_alterada["implementacao_sha256"] = "f" * 64

        casos = (
            ([item, voto_alterado], "sha256"),
            ([item, execucao, verificacao_alterada], "sha256"),
        )
        for registros, trecho in casos:
            with self.subTest(tipo=registros[-1]["tipo"]):
                self.assert_erro_acionavel(registros, trecho)

    def test_aprovacao_posterior_a_implementacao_nao_pontua(self):
        item = proposta()
        voto_antes = voto(item, "claude", importancia=3, registrado_em=T2)
        execucao = implementacao(item, registrado_em=T3)
        voto_depois = voto(item, "antigravity", importancia=2, registrado_em=T4)
        confirmacao_1 = verificacao(item, execucao, "claude", registrado_em=T5)
        confirmacao_2 = verificacao(item, execucao, "antigravity", registrado_em=T6)

        resultado = placar.apurar(
            [item, voto_antes, execucao, voto_depois, confirmacao_1, confirmacao_2]
        )

        self.assertNotEqual("pontua", resultado["propostas"][0]["estado"])
        self.assertEqual(0, resultado["propostas"][0]["pontos"])
        self.assertFalse(resultado["ranking_definido"])

    def test_verificacao_faltante_aguarda_e_recusa_de_peer_recusa(self):
        completos = registros_completos()
        sem_uma_verificacao = completos[:-1]

        resultado_incompleto = placar.apurar(sem_uma_verificacao)

        self.assertEqual(
            "aguarda_verificacao", resultado_incompleto["propostas"][0]["estado"]
        )
        self.assertEqual(0, resultado_incompleto["propostas"][0]["pontos"])

        recusados = registros_completos(custo_reais=8.0)
        recusados[-1]["decisao"] = "recusar"
        resultado_recusado = placar.apurar(recusados)

        self.assertEqual("recusada", resultado_recusado["propostas"][0]["estado"])
        self.assertEqual(0, resultado_recusado["propostas"][0]["pontos"])
        autor = self.participantes_por_id(resultado_recusado)["codex"]
        self.assertEqual(10.0, autor["minutos_totais"])
        self.assertEqual(8.0, autor["custo_reais"])

    def test_custo_desconhecido_torna_agregado_do_autor_desconhecido(self):
        conhecidos = registros_completos(
            identificador="CODEX-001",
            problema="problema-um",
            custo_reais=3.0,
        )
        desconhecidos = registros_completos(
            identificador="CODEX-002",
            problema="problema-dois",
            custo_reais=None,
        )

        resultado = placar.apurar(conhecidos + desconhecidos)

        autor = self.participantes_por_id(resultado)["codex"]
        self.assertEqual(20.0, autor["minutos_totais"])
        self.assertIsNone(autor["custo_reais"])

    def test_duplicatas_de_registro_e_de_implementacao_sao_recusadas(self):
        item = proposta()
        primeiro_voto = voto(item, "claude")
        execucao_1 = implementacao(item, autor="codex")
        execucao_2 = implementacao(item, autor="claude")
        casos = (
            ([item, primeiro_voto, dict(primeiro_voto)], "duplic"),
            ([item, execucao_1, execucao_2], "duplic"),
        )
        for registros, trecho in casos:
            with self.subTest(trecho=trecho):
                self.assert_erro_acionavel(registros, trecho)

    def test_campos_numericos_e_fonte_de_custo_invalidos_sao_recusados(self):
        item = proposta()
        casos = (
            (implementacao(item, minutos_totais=-1), "minutos"),
            (implementacao(item, custo_reais=-0.01, fonte_custo="fatura"), "custo"),
            (implementacao(item, custo_reais=None, fonte_custo="fatura"), "fonte"),
            (implementacao(item, custo_reais=1.0, fonte_custo=""), "fonte"),
        )
        for execucao, trecho in casos:
            with self.subTest(trecho=trecho):
                self.assert_erro_acionavel([item, execucao], trecho)

    def test_duas_propostas_pontuando_para_mesmo_problema_sao_recusadas(self):
        primeira = registros_completos(
            identificador="CODEX-001", autor="codex", problema="mesmo-problema"
        )
        segunda = registros_completos(
            identificador="CLAUDE-001", autor="claude", problema="mesmo-problema"
        )

        self.assert_erro_acionavel(primeira + segunda, "problema")

    def test_empate_na_maior_pontuacao_nao_inventa_vencedor(self):
        primeira = registros_completos(
            identificador="CODEX-001",
            autor="codex",
            problema="problema-codex",
            importancias=(2, 2),
        )
        segunda = registros_completos(
            identificador="CLAUDE-001",
            autor="claude",
            problema="problema-claude",
            importancias=(2, 2),
        )

        resultado = placar.apurar(primeira + segunda)

        participantes = self.participantes_por_id(resultado)
        self.assertEqual(2, participantes["codex"]["pontos"])
        self.assertEqual(2, participantes["claude"]["pontos"])
        self.assertFalse(resultado["ranking_definido"])

    def test_tres_pontuacoes_distintas_definem_ranking(self):
        registros = []
        for identificador, autor, problema, importancia in (
            ("CODEX-001", "codex", "problema-codex", 3),
            ("CLAUDE-001", "claude", "problema-claude", 2),
            ("ANTIGRAVITY-001", "antigravity", "problema-antigravity", 1),
        ):
            registros.extend(
                registros_completos(
                    identificador=identificador,
                    autor=autor,
                    problema=problema,
                    importancias=(importancia, importancia),
                )
            )

        resultado = placar.apurar(registros)

        self.assertEqual(
            [3, 2, 1],
            [participante["pontos"] for participante in resultado["participantes"]],
        )
        self.assertTrue(resultado["ranking_definido"])

    def test_carregar_recusa_json_invalido_com_acao_clara(self):
        with tempfile.TemporaryDirectory() as diretorio:
            raiz = Path(diretorio)
            pasta = raiz / "registros"
            pasta.mkdir()
            (pasta / "quebrado.json").write_text("{", encoding="utf-8")

            with mock.patch.object(placar, "RAIZ", raiz):
                with self.assertRaisesRegex(ValueError, r"(?i)json.*corrija"):
                    placar.carregar(pasta)

    def test_carregar_recusa_prova_ausente_vazia_ou_fora_da_raiz(self):
        casos = (
            ("evidencias/ausente.txt", None, r"(?i)prova.*ausente.*salve"),
            ("evidencias/vazia.txt", b"", r"(?i)prova.*vazia.*salve"),
            ("../fora.txt", None, r"(?i)prova.*fora.*guarde"),
        )
        for caminho, conteudo, mensagem in casos:
            with self.subTest(caminho=caminho):
                with tempfile.TemporaryDirectory() as diretorio:
                    raiz = Path(diretorio)
                    pasta = raiz / "registros"
                    pasta.mkdir()
                    prova = (raiz / caminho).resolve()
                    if conteudo is not None:
                        prova.parent.mkdir(parents=True, exist_ok=True)
                        prova.write_bytes(conteudo)
                    registro = {
                        "tipo": "implementacao",
                        "prova": caminho,
                        "prova_sha256": hashlib.sha256(
                            conteudo if conteudo is not None else b""
                        ).hexdigest(),
                    }
                    (pasta / "registro.json").write_text(
                        json.dumps(registro), encoding="utf-8"
                    )

                    with mock.patch.object(placar, "RAIZ", raiz):
                        with self.assertRaisesRegex(ValueError, mensagem):
                            placar.carregar(pasta)

    def test_carregar_exige_hash_da_prova_em_implementacao_e_verificacao(self):
        for tipo in ("implementacao", "verificacao"):
            with self.subTest(tipo=tipo):
                with tempfile.TemporaryDirectory() as diretorio:
                    raiz = Path(diretorio)
                    pasta = raiz / "registros"
                    pasta.mkdir()
                    prova = raiz / "evidencias" / "saida.txt"
                    prova.parent.mkdir()
                    prova.write_bytes(b"saida observada")
                    registro = {"tipo": tipo, "prova": "evidencias/saida.txt"}
                    (pasta / "registro.json").write_text(
                        json.dumps(registro), encoding="utf-8"
                    )

                    with mock.patch.object(placar, "RAIZ", raiz):
                        with self.assertRaisesRegex(
                            ValueError,
                            r"(?i)(prova_sha256|sha256).*(informe|registre|preencha)",
                        ):
                            placar.carregar(pasta)

    def test_carregar_recusa_prova_reescrita_depois_do_registro(self):
        with tempfile.TemporaryDirectory() as diretorio:
            raiz = Path(diretorio)
            pasta = raiz / "registros"
            pasta.mkdir()
            prova = raiz / "evidencias" / "saida.txt"
            prova.parent.mkdir()
            prova.write_bytes(b"saida original")
            registro = {
                "tipo": "implementacao",
                "prova": "evidencias/saida.txt",
                "prova_sha256": hashlib.sha256(prova.read_bytes()).hexdigest(),
            }
            (pasta / "registro.json").write_text(
                json.dumps(registro), encoding="utf-8"
            )
            prova.write_bytes(b"saida alterada")

            with mock.patch.object(placar, "RAIZ", raiz):
                with self.assertRaisesRegex(
                    ValueError, r"(?i)prova.*(mudou|sha256).*(registre|atualize|restaure)"
                ):
                    placar.carregar(pasta)

    def test_carregar_aceita_prova_com_hash_do_conteudo_atual(self):
        with tempfile.TemporaryDirectory() as diretorio:
            raiz = Path(diretorio)
            pasta = raiz / "registros"
            pasta.mkdir()
            prova = raiz / "evidencias" / "saida.txt"
            prova.parent.mkdir()
            prova.write_bytes(b"saida observada\n")
            registro = {
                "tipo": "verificacao",
                "prova": "evidencias/saida.txt",
                "prova_sha256": hashlib.sha256(prova.read_bytes()).hexdigest(),
            }
            (pasta / "registro.json").write_text(
                json.dumps(registro), encoding="utf-8"
            )

            with mock.patch.object(placar, "RAIZ", raiz):
                carregados = placar.carregar(pasta)

            self.assertEqual([registro], carregados)


if __name__ == "__main__":
    unittest.main()
