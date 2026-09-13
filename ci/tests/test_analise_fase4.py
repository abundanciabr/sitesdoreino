"""Guardas da medição confirmatória da Fase 4."""

from datetime import datetime, timedelta, timezone
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import analise_fase4 as analise  # noqa: E402
import telemetria  # noqa: E402


def tarefa(
    condicao,
    numero,
    *,
    piloto="fase3",
    estado="concluida",
    minutos=30,
    par=True,
    metricas=None,
    fonte="registro-operacional-autorizado",
):
    inicio = datetime(2026, 9, 1, tzinfo=timezone.utc) + timedelta(days=numero)
    fim = inicio + timedelta(minutes=minutos) if minutos is not None else None
    tarefa_id = f"TAR-{piloto}-{numero}-{condicao}"
    commit = "a" * 40
    pr = numero + 1
    dados = {
        "evento": "tarefa_medida",
        "tarefa": tarefa_id,
        "tentativa": f"tentativa-{numero}-{condicao}",
        "branch": f"agent/ci/medicao-{numero}-{condicao}",
        "commit": commit,
        "pr": pr,
        "piloto": piloto,
        "condicao": condicao,
        "par_id": f"par-{numero}" if par else None,
        "tipo": "correcao-transversal",
        "complexidade": "media",
        "natureza": "codigo",
        "componentes": "ci",
        "fronteiras_integracao": "uma",
        "migracao": "nao",
        "risco": "medio",
        "escopo_publicacao": "publicacao-verificada",
        "revisao_instrumento": "b" * 64,
        "inicio": inicio.isoformat(),
        "fim": fim.isoformat() if fim else None,
        "estado": estado,
        "fonte": fonte,
        "metricas": (
            metricas
            if metricas is not None
            else {
                "chamadas_modelo": 1,
                "chamadas_ferramenta": 2,
                "runner_minutos": 3,
                "retentativas": 0,
                "correcoes_revisao": 0,
                "reaberturas": 0,
                "minutos_adocao": 0,
                "minutos_manutencao": 0,
                "defeitos_escapados": 0,
                "violacoes_seguranca": 0,
                "contexto_bytes": None,
            }
        ),
        "schema_medicao": 2,
        "tarefa_sha256": "c" * 64,
        "classificacao_sha256": "d" * 64,
        "classificada_em": (inicio - timedelta(minutes=1)).isoformat(),
        "autorizada_por": "maestro-fase4",
        "observado_em": (fim or inicio).isoformat(),
        "evidencia": (
            None
            if estado == "pendente"
            else {
                "resultado": f"{tarefa_id} {estado}: PR #{pr} no commit {commit}",
                "fonte": (
                    "https://github.com/abundanciabr/sitesdoreino/pull/"
                    f"{pr}/commits/{commit}"
                ),
                "verificado_em": (fim or inicio).isoformat(),
            }
        ),
    }
    dados["id"] = telemetria.identidade_tarefa(dados)
    return dados


def vinculo_para(evento):
    vinculo = {
        "classificacao": {
            campo: evento[campo]
            for campo in (
                "piloto",
                "condicao",
                "par_id",
                "tipo",
                "complexidade",
                "natureza",
                "componentes",
                "fronteiras_integracao",
                "migracao",
                "risco",
                "escopo_publicacao",
                "revisao_instrumento",
            )
        },
        "tarefa_sha256": evento["tarefa_sha256"],
        "classificacao_sha256": evento["classificacao_sha256"],
        "classificada_em": evento["classificada_em"],
        "autorizada_por": evento["autorizada_por"],
        "commits_descendentes": [evento["commit"]],
        "resultados_verificados": [],
    }
    if evento["estado"] != "pendente":
        vinculo["resultados_verificados"].append(
            [evento["pr"], evento["commit"], evento["estado"]]
        )
    return vinculo


def atualizar_identidade_e_evidencia(evento):
    if evento["estado"] != "pendente":
        evento["evidencia"] = {
            "resultado": (
                f"{evento['tarefa']} {evento['estado']}: PR #{evento['pr']} "
                f"no commit {evento['commit']}"
            ),
            "fonte": (
                "https://github.com/abundanciabr/sitesdoreino/pull/"
                f"{evento['pr']}/commits/{evento['commit']}"
            ),
            "verificado_em": evento["fim"],
        }
    evento["id"] = telemetria.identidade_tarefa(evento)


def alinhar_ao_vinculo(evento, origem):
    for campo in (
        "piloto",
        "condicao",
        "par_id",
        "tipo",
        "complexidade",
        "natureza",
        "componentes",
        "fronteiras_integracao",
        "migracao",
        "risco",
        "escopo_publicacao",
        "revisao_instrumento",
        "tarefa_sha256",
        "classificacao_sha256",
        "classificada_em",
        "autorizada_por",
    ):
        evento[campo] = origem[campo]
    atualizar_identidade_e_evidencia(evento)


_analisar_sem_fila = analise.analisar


def analisar_com_fila(eventos, vinculos=None):
    if vinculos is None:
        vinculos = {}
        for evento in eventos:
            if isinstance(evento, dict) and evento.get("schema_medicao") == 2:
                vinculo = vinculos.setdefault(
                    evento.get("tarefa"), vinculo_para(evento)
                )
                if evento.get("commit") not in vinculo["commits_descendentes"]:
                    vinculo["commits_descendentes"].append(evento["commit"])
                resultado = [
                    evento.get("pr"), evento.get("commit"), evento.get("estado")
                ]
                if (
                    evento.get("estado") != "pendente"
                    and resultado not in vinculo["resultados_verificados"]
                ):
                    vinculo["resultados_verificados"].append(resultado)
    return _analisar_sem_fila(eventos, vinculos)


def test_sem_tarefas_medidas_nao_declara_ganho():
    resultado = analisar_com_fila([])
    assert resultado["instrumentacao"] == "implementada"
    assert resultado["amostra_disponivel"] == "ausente"
    assert resultado["avaliacao"] == "em coleta"
    assert all(p["resultado"] == "não avaliável" for p in resultado["pilotos"].values())


def test_sintetico_e_excluido_e_fica_explicado_no_diagnostico():
    resultado = analisar_com_fila([tarefa("depois", 1, fonte="telemetria-de-teste")])

    assert resultado["observacoes"]["tarefas_validas"] == 0
    diagnostico = resultado["diagnostico_da_entrada"]
    assert diagnostico["registros_encontrados"] == 1
    assert diagnostico["registros_tarefa_medida"] == 1
    assert diagnostico["registros_sinteticos_excluidos"] == 1
    assert diagnostico["registros_reais_reconhecidos"] == 0
    assert diagnostico["motivos_de_rejeicao"] == {"sintetico": 1}


def test_sintetico_invalido_tambem_e_excluido_sem_virar_erro_real():
    sintetico = tarefa("depois", 1, fonte="telemetria-de-teste")
    sintetico["id"] = "0" * 64

    resultado = analisar_com_fila([sintetico])

    assert resultado["observacoes"]["eventos_invalidos"] == 0
    assert resultado["diagnostico_da_entrada"]["registros_sinteticos_excluidos"] == 1
    assert resultado["diagnostico_da_entrada"]["motivos_de_rejeicao"] == {"sintetico": 1}


def test_diagnostico_separa_incompleto_de_erro_de_correlacao():
    incompleto = tarefa("depois", 1)
    del incompleto["fim"]
    erro = tarefa("depois", 2)
    erro["id"] = "0" * 64

    diagnostico = analisar_com_fila([incompleto, erro])["diagnostico_da_entrada"]

    assert diagnostico["registros_reais_incompletos"] == 1
    assert diagnostico["registros_com_erro_de_validacao_ou_correlacao"] == 1
    assert diagnostico["registros_reais_inelegiveis"] == 2
    assert diagnostico["motivos_de_rejeicao"] == {
        "erro_de_validacao_ou_correlacao": 1,
        "real_incompleto": 1,
    }


def test_repeticao_nao_inflama_a_amostra_e_fase_antiga_e_ignorada():
    evento = tarefa("antes", 1)
    fase_antiga = {"evento": "fase_operacional", "tarefa": "TAR-1"}
    resultado = analisar_com_fila([evento, evento, fase_antiga])
    assert resultado["observacoes"]["tarefas_validas"] == 1
    assert resultado["observacoes"]["eventos_antigos_ou_de_outras_fases"] == 1
    assert resultado["pilotos"]["fase3"]["amostra"]["antes"] == 1


def test_tentativas_da_mesma_tarefa_nao_formam_tarefas_novas():
    primeira = tarefa("antes", 1, minutos=20)
    retomada = tarefa("antes", 2, minutos=30)
    retomada["tarefa"] = primeira["tarefa"]
    retomada["tentativa"] = "retomada-1"
    retomada["par_id"] = primeira["par_id"]
    alinhar_ao_vinculo(retomada, primeira)
    resultado = analisar_com_fila([primeira, retomada])
    assert resultado["observacoes"]["tarefas_validas"] == 1
    assert resultado["observacoes"]["tentativas_validas"] == 2
    assert resultado["pilotos"]["fase3"]["amostra"]["tentativas_observadas"] == 2


def test_abertura_pendente_e_fechamento_da_mesma_tentativa_preservam_metricas():
    pendente = tarefa(
        "depois",
        1,
        estado="pendente",
        minutos=None,
        metricas={campo: None for campo in telemetria.METRICAS_DA_TAREFA},
    )
    concluida = tarefa("depois", 2, minutos=30)
    concluida["tarefa"] = pendente["tarefa"]
    concluida["tentativa"] = pendente["tentativa"]
    concluida["branch"] = pendente["branch"]
    concluida["inicio"] = pendente["inicio"]
    concluida["classificada_em"] = pendente["classificada_em"]
    concluida["fim"] = (
        datetime.fromisoformat(concluida["inicio"]) + timedelta(minutes=30)
    ).isoformat()
    concluida["observado_em"] = concluida["fim"]
    alinhar_ao_vinculo(concluida, pendente)

    piloto = analisar_com_fila([pendente, concluida])["pilotos"]["fase3"]

    assert piloto["amostra"]["tentativas_observadas"] == 1
    assert piloto["amostra"]["registros_incompletos"] == 0
    assert piloto["metrica_principal_minutos"]["depois"] == 30
    assert piloto["metricas_secundarias"]["chamadas_modelo"]["depois"]["total"] == 1

    inicio_divergente = dict(concluida)
    inicio_divergente["inicio"] = (
        datetime.fromisoformat(concluida["inicio"]) + timedelta(minutes=1)
    ).isoformat()
    atualizar_identidade_e_evidencia(inicio_divergente)
    resultado_divergente = analisar_com_fila(
        [pendente, concluida, inicio_divergente]
    )

    assert resultado_divergente["observacoes"]["tarefas_validas"] == 0
    assert resultado_divergente["observacoes"]["tentativas_validas"] == 0


def test_registrar_tarefa_grava_no_caderno_privado_da_telemetria(tmp_path, monkeypatch):
    evento = tarefa("antes", 1)
    campos = {chave: valor for chave, valor in evento.items()
              if chave not in {"evento", "id"}}
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    monkeypatch.setattr(telemetria, "dir_git_comum", lambda _: git_dir)
    caminho = telemetria.registrar_tarefa(cwd=tmp_path, **campos)
    assert caminho is not None
    eventos = telemetria.ler_tudo(git_dir)
    assert len(eventos) == 1
    assert eventos[0]["evento"] == "tarefa_medida"
    assert eventos[0]["id"] == telemetria.identidade_tarefa(eventos[0])


def test_ausencia_de_tempo_ou_custo_nao_vira_zero():
    sem_tempo = tarefa("antes", 1, minutos=None)
    sem_custo = tarefa("depois", 2, metricas={campo: None for campo in telemetria.METRICAS_DA_TAREFA})
    resultado = analisar_com_fila([sem_tempo, sem_custo])
    piloto = resultado["pilotos"]["fase3"]
    assert piloto["metrica_principal_minutos"]["antes"] is None
    assert piloto["custo_completo"]["depois"]["runner_minutos"]["total"] is None
    assert piloto["metricas_secundarias"]["contexto_bytes"]["antes"]["total"] is None
    assert piloto["resultado"] == "inconclusivo"


def test_par_incompleto_nao_forma_par_completo():
    eventos = []
    for numero in range(20):
        eventos += [tarefa("antes", numero, minutos=None if numero == 0 else 60),
                    tarefa("depois", numero, minutos=30)]
    resultado = analisar_com_fila(eventos)
    amostra = resultado["pilotos"]["fase3"]["amostra"]
    assert amostra["pares"] == 19
    assert amostra["pares_incompletos"] == 1


def test_falha_com_tempo_nao_forma_par_de_tarefa_concluida():
    antes = tarefa("antes", 1, estado="falhou")
    depois = tarefa("depois", 1)
    resultado = analisar_com_fila([antes, depois])
    assert resultado["pilotos"]["fase3"]["amostra"]["pares"] == 0
    assert resultado["pilotos"]["fase3"]["amostra"]["pares_incompletos"] == 1


def test_atributo_diferente_exclui_par_e_fica_visivel():
    antes = tarefa("antes", 1)
    depois = tarefa("depois", 1)
    depois["risco"] = "alto"
    depois["id"] = telemetria.identidade_tarefa(depois)
    resultado = analisar_com_fila([antes, depois])
    piloto = resultado["pilotos"]["fase3"]
    assert piloto["amostra"]["pares"] == 0
    assert piloto["amostra"]["exclusoes"] == 1
    assert piloto["comparabilidade"]["pares_incompativeis"] == 1


def test_revisoes_diferentes_do_instrumento_impedem_aprovacao():
    eventos = []
    for numero in range(20):
        antes = tarefa("antes", numero, minutos=60)
        depois = tarefa("depois", numero, minutos=30)
        if numero == 0:
            depois["revisao_instrumento"] = "c" * 64
            depois["id"] = telemetria.identidade_tarefa(depois)
        eventos += [antes, depois]
    resultado = analisar_com_fila(eventos)
    assert resultado["pilotos"]["fase3"]["resultado"] == "inconclusivo"
    assert (
        len(resultado["pilotos"]["fase3"]["comparabilidade"]["revisoes_do_instrumento"])
        == 2
    )


def test_retomada_que_troca_revisao_sem_nova_classificacao_e_excluida():
    primeira = tarefa("antes", 1)
    retomada = tarefa("antes", 2)
    retomada["tarefa"] = primeira["tarefa"]
    retomada["tentativa"] = "retomada-1"
    retomada["revisao_instrumento"] = "c" * 64
    atualizar_identidade_e_evidencia(retomada)

    piloto = analisar_com_fila([primeira, retomada])["pilotos"]["fase3"]

    assert piloto["resultado"] == "inconclusivo"
    assert piloto["revisoes_do_instrumento"] == ["b" * 64]


def test_colisao_de_par_id_nao_fabrica_pareamento():
    antes_1 = tarefa("antes", 1)
    antes_2 = tarefa("antes", 2)
    depois = tarefa("depois", 1)
    antes_2["par_id"] = antes_1["par_id"]
    antes_2["id"] = telemetria.identidade_tarefa(antes_2)

    piloto = analisar_com_fila([antes_1, antes_2, depois])["pilotos"]["fase3"]

    assert piloto["amostra"]["pares"] == 0
    assert piloto["amostra"]["colisoes_de_pareamento"] == 1


def test_hash_da_entrada_muda_com_registro_invalido():
    valido = tarefa("depois", 1)
    invalido = dict(valido, id="0" * 64)

    sem_invalido = analisar_com_fila([valido])["reprodutibilidade"]["entrada_sha256"]
    com_invalido = analisar_com_fila([valido, invalido])["reprodutibilidade"]["entrada_sha256"]

    assert sem_invalido != com_invalido


def test_vinte_pares_com_qualidade_preservada_podem_demonstrar_beneficio():
    eventos = []
    for numero in range(20):
        eventos += [tarefa("antes", numero, minutos=60), tarefa("depois", numero, minutos=30)]
    resultado = analisar_com_fila(eventos)
    piloto = resultado["pilotos"]["fase3"]
    assert piloto["amostra"]["antes"] == 20
    assert piloto["amostra"]["depois"] == 20
    assert piloto["amostra"]["pares"] == 20
    assert piloto["metrica_principal_minutos"]["reducao_relativa"] == 0.5
    assert piloto["incerteza_intervalo_pareado_minutos"] == [-30.0, -30.0]
    assert piloto["resultado"] == "benefício demonstrado no escopo"


def test_defeito_historico_antes_e_zero_depois_nao_e_regressao_nova():
    eventos = []
    for numero in range(20):
        antes = tarefa("antes", numero, minutos=60)
        depois = tarefa("depois", numero, minutos=30)
        if numero == 0:
            antes["metricas"]["defeitos_escapados"] = 1
            antes["id"] = telemetria.identidade_tarefa(antes)
        eventos += [antes, depois]

    piloto = analisar_com_fila(eventos)["pilotos"]["fase3"]

    assert piloto["qualidade"]["historico"]["antes_com_defeito_escapado"] == 1
    assert piloto["qualidade"]["depois"]["defeitos_escapados"] == 0
    assert piloto["resultado"] == "benefício demonstrado no escopo"
    assert piloto["decisao_expansao"] == "não liberada"


def test_falha_atual_depois_bloqueia_expansao_mesmo_sem_amostra_completa():
    evento = tarefa("depois", 1)
    evento["metricas"]["violacoes_seguranca"] = 1
    evento["id"] = telemetria.identidade_tarefa(evento)

    resultado = analisar_com_fila([evento])
    piloto = resultado["pilotos"]["fase3"]

    assert piloto["resultado"] == "regressão"
    assert piloto["decisao_expansao"] == "bloqueada por falha atual"
    assert resultado["decisao_expansao"] == "bloqueada por falha atual"


def test_intervalo_compatível_com_melhora_e_piora_fica_inconclusivo():
    eventos = []
    for numero in range(20):
        eventos.append(tarefa("antes", numero, minutos=60))
        eventos.append(tarefa("depois", numero, minutos=30 if numero % 2 == 0 else 90))

    piloto = analisar_com_fila(eventos)["pilotos"]["fase3"]

    assert piloto["incerteza_intervalo_pareado_minutos"] == [-30.0, 30.0]
    assert piloto["resultado"] == "inconclusivo"


def test_beneficio_sustentado_em_todos_os_pilotos_nao_aprova_auditoria_ou_expansao():
    eventos = []
    for piloto in analise.PILOTOS:
        for numero in range(20):
            eventos += [
                tarefa("antes", numero, piloto=piloto, minutos=60),
                tarefa("depois", numero, piloto=piloto, minutos=30),
            ]

    resultado = analisar_com_fila(eventos)

    assert resultado["avaliacao"] == "concluída"
    assert resultado["auditoria_independente"] == "pendente"
    assert resultado["decisao_expansao"] == "não liberada"
    assert all(p["resultado"] == "benefício demonstrado no escopo"
               for p in resultado["pilotos"].values())


def test_falha_de_qualidade_e_dado_ausente_impedem_aprovacao():
    eventos = []
    for numero in range(20):
        eventos += [tarefa("antes", numero), tarefa("depois", numero)]
    eventos[-1]["metricas"]["violacoes_seguranca"] = None
    eventos[-1]["id"] = telemetria.identidade_tarefa(eventos[-1])
    eventos[-2]["metricas"]["defeitos_escapados"] = 1
    eventos[-2]["id"] = telemetria.identidade_tarefa(eventos[-2])
    resultado = analisar_com_fila(eventos)
    piloto = resultado["pilotos"]["fase3"]
    assert piloto["qualidade"]["depois"]["violacoes_seguranca"] is None
    assert piloto["qualidade"]["antes"]["defeitos_escapados"] == 1
    assert piloto["resultado"] == "inconclusivo"


def test_evento_adulterado_fica_fora_da_analise():
    evento = tarefa("antes", 1)
    evento["tipo"] = "outro-tipo"
    resultado = analisar_com_fila([evento])
    assert resultado["observacoes"]["eventos_invalidos"] == 1
    assert resultado["observacoes"]["tarefas_validas"] == 0
    assert "outro-tipo" not in json.dumps(resultado, ensure_ascii=False)
def test_estado_da_tentativa_e_o_mais_recente_e_nao_um_verde_antigo():
    concluida = tarefa("depois", 1, estado="concluida")
    concluida.update(
        inicio="2026-09-08T10:00:00+00:00",
        fim="2026-09-08T10:30:00+00:00",
        observado_em="2026-09-08T10:30:00+00:00",
        quando="2026-09-08T10:30:00+00:00",
    )
    atualizar_identidade_e_evidencia(concluida)
    reaberta = tarefa("depois", 2, estado="falhou")
    reaberta.update(
        tarefa=concluida["tarefa"],
        tentativa=concluida["tentativa"],
        branch=concluida["branch"],
        inicio=concluida["inicio"],
        classificada_em=concluida["classificada_em"],
        fim="2026-09-08T08:40:00-03:00",
        quando="2026-09-08T08:40:00-03:00",
        observado_em="2026-09-08T08:40:00-03:00",
    )
    alinhar_ao_vinculo(reaberta, concluida)

    piloto = analisar_com_fila([concluida, reaberta])["pilotos"]["fase3"]

    assert piloto["amostra"]["falhas_ou_abandonadas"] == 1
    assert piloto["amostra"]["tarefas_com_tempo_observado"]["depois"] == 0


def test_classificacao_divergente_da_fila_nao_entra_na_unidade_de_analise():
    antes = tarefa("antes", 1)
    depois = tarefa("depois", 2)
    depois["tarefa"] = antes["tarefa"]
    atualizar_identidade_e_evidencia(depois)

    resultado = analisar_com_fila([antes, depois])

    assert resultado["observacoes"]["tarefas_validas"] == 1
    assert (
        resultado["diagnostico_da_entrada"]["tarefas_com_classificacao_conflitante"]
        == 0
    )
    assert resultado["observacoes"]["eventos_estruturais_sem_confirmacao"] == 1


def test_revisao_do_instrumento_entra_na_compatibilidade_do_par():
    antes = tarefa("antes", 1)
    depois = tarefa("depois", 1)
    depois["revisao_instrumento"] = "c" * 64
    depois["id"] = telemetria.identidade_tarefa(depois)

    piloto = analisar_com_fila([antes, depois])["pilotos"]["fase3"]

    assert piloto["amostra"]["pares"] == 0
    assert piloto["comparabilidade"]["pares_incompativeis"] == 1


def test_validade_estrutural_nao_vira_completude_confirmatoria():
    legado_sem_vinculo_ou_evidencia = tarefa("depois", 1)
    for campo in (
        "schema_medicao",
        "tarefa_sha256",
        "classificacao_sha256",
        "classificada_em",
        "autorizada_por",
        "observado_em",
        "evidencia",
    ):
        legado_sem_vinculo_ou_evidencia.pop(campo)
    legado_sem_vinculo_ou_evidencia["revisao_instrumento"] = "b" * 40
    legado_sem_vinculo_ou_evidencia["id"] = telemetria.identidade_tarefa(
        legado_sem_vinculo_ou_evidencia
    )

    resultado = analisar_com_fila([legado_sem_vinculo_ou_evidencia])

    assert resultado["observacoes"]["eventos_estruturalmente_validos"] == 1
    assert resultado["observacoes"]["tarefas_confirmatorias_completas"] == 0
    assert resultado["observacoes"]["eventos_incompletos_excluidos"] == 0
    assert resultado["observacoes"]["eventos_estruturais_sem_confirmacao"] == 1
    assert resultado["amostra_disponivel"] == "ausente"

    pendente = tarefa("depois", 2, estado="pendente", minutos=None)
    resultado_pendente = analisar_com_fila([pendente])

    assert resultado_pendente["observacoes"]["eventos_estruturalmente_validos"] == 1
    assert resultado_pendente["observacoes"]["tarefas_confirmatorias_completas"] == 0
    assert resultado_pendente["amostra_disponivel"] == "ausente"


def test_auditoria_so_vale_para_o_hash_e_a_revisao_exatos():
    evento = tarefa("depois", 1)
    sem_auditoria = analisar_com_fila([evento])
    entrada_sha = sem_auditoria["reprodutibilidade"]["entrada_sha256"]
    auditoria = {
        "evento": "auditoria_fase4",
        "entrada_sha256": entrada_sha,
        "revisao_analise": sem_auditoria["analise"],
        "revisao_instrumento": evento["revisao_instrumento"],
        "auditor": "revisor-independente",
        "estado": "aprovada",
        "verificado_em": "2026-09-08T12:00:00+00:00",
        "evidencia": "https://github.com/abundanciabr/sitesdoreino/pull/1420",
    }
    auditoria["id"] = telemetria.identidade_auditoria(auditoria)

    assert (
        analisar_com_fila([evento, auditoria])["auditoria_independente"] == "concluída"
    )
    auditoria_errada = dict(auditoria, entrada_sha256="0" * 64)
    auditoria_errada["id"] = telemetria.identidade_auditoria(auditoria_errada)
    assert (
        analisar_com_fila([evento, auditoria_errada])["auditoria_independente"]
        == "pendente"
    )
    auditoria_posterior = dict(
        auditoria,
        estado="reprovada",
        verificado_em="2026-09-08T10:00:00-03:00",
    )
    auditoria_posterior["id"] = telemetria.identidade_auditoria(
        auditoria_posterior
    )
    assert (
        analisar_com_fila([evento, auditoria, auditoria_posterior])[
            "auditoria_independente"
        ]
        == "reprovada"
    )


def test_tentativa_e_identificada_sem_multiplicar_mudanca_de_branch():
    primeira = tarefa("depois", 1, estado="pendente", minutos=None)
    segunda = tarefa("depois", 2)
    segunda.update(
        tarefa=primeira["tarefa"],
        tentativa=primeira["tentativa"],
        inicio=primeira["inicio"],
        classificada_em=primeira["classificada_em"],
        branch="agent/ci/ramo-retomado",
    )
    alinhar_ao_vinculo(segunda, primeira)

    resultado = analisar_com_fila([primeira, segunda])

    assert resultado["observacoes"]["tarefas_validas"] == 1
    assert resultado["observacoes"]["tentativas_validas"] == 1


def test_vinculo_externo_divergente_impede_confirmacao():
    evento = tarefa("depois", 1)
    vinculos = {evento["tarefa"]: vinculo_para(evento)}
    vinculos[evento["tarefa"]]["tarefa_sha256"] = "0" * 64

    sem_fila = _analisar_sem_fila([evento])
    resultado = analisar_com_fila([evento], vinculos)
    evidencia_generica = tarefa("depois", 2)
    evidencia_generica["evidencia"] = {
        "resultado": "resultado conferido",
        "fonte": "https://example.test/prova",
        "verificado_em": evidencia_generica["fim"],
    }
    evidencia_generica["id"] = telemetria.identidade_tarefa(evidencia_generica)
    resultado_generico = _analisar_sem_fila(
        [evidencia_generica],
        {evidencia_generica["tarefa"]: vinculo_para(evidencia_generica)},
    )
    commit_sem_ancestralidade = dict(evento, commit="b" * 40)
    atualizar_identidade_e_evidencia(commit_sem_ancestralidade)
    vinculo_sem_ancestralidade = vinculo_para(evento)
    vinculo_sem_ancestralidade["resultados_verificados"].append(
        [
            commit_sem_ancestralidade["pr"],
            commit_sem_ancestralidade["commit"],
            commit_sem_ancestralidade["estado"],
        ]
    )
    resultado_sem_ancestralidade = _analisar_sem_fila(
        [commit_sem_ancestralidade],
        {evento["tarefa"]: vinculo_sem_ancestralidade},
    )
    pr_sem_relacao = dict(evento, pr=9999)
    atualizar_identidade_e_evidencia(pr_sem_relacao)
    resultado_sem_relacao = _analisar_sem_fila(
        [pr_sem_relacao], {evento["tarefa"]: vinculo_para(evento)}
    )
    estado_sem_relacao = dict(evento, estado="falhou")
    atualizar_identidade_e_evidencia(estado_sem_relacao)
    resultado_com_estado_inventado = _analisar_sem_fila(
        [estado_sem_relacao], {evento["tarefa"]: vinculo_para(evento)}
    )
    fim_antes_do_inicio = dict(evento)
    fim_antes_do_inicio["fim"] = (
        datetime.fromisoformat(evento["inicio"]) - timedelta(minutes=1)
    ).isoformat()
    fim_antes_do_inicio["observado_em"] = evento["inicio"]
    atualizar_identidade_e_evidencia(fim_antes_do_inicio)
    resultado_com_fim_invalido = _analisar_sem_fila(
        [fim_antes_do_inicio],
        {evento["tarefa"]: vinculo_para(fim_antes_do_inicio)},
    )

    assert sem_fila["observacoes"]["tarefas_confirmatorias_completas"] == 0
    assert resultado["observacoes"]["eventos_estruturalmente_validos"] == 1
    assert resultado["observacoes"]["tarefas_confirmatorias_completas"] == 0
    assert resultado_generico["observacoes"]["tarefas_confirmatorias_completas"] == 0
    assert resultado_sem_ancestralidade["observacoes"]["tarefas_confirmatorias_completas"] == 0
    assert resultado_sem_relacao["observacoes"]["tarefas_confirmatorias_completas"] == 0
    assert resultado_com_estado_inventado["observacoes"]["tarefas_confirmatorias_completas"] == 0
    assert resultado_com_fim_invalido["observacoes"]["tarefas_confirmatorias_completas"] == 0


def test_parecer_reprovado_no_hash_atual_nao_aparece_como_aprovado():
    evento = tarefa("depois", 1)
    entrada_sha = analisar_com_fila([evento])["reprodutibilidade"]["entrada_sha256"]
    auditoria = {
        "evento": "auditoria_fase4",
        "entrada_sha256": entrada_sha,
        "revisao_analise": analise.REVISAO_DA_ANALISE,
        "revisao_instrumento": evento["revisao_instrumento"],
        "auditor": "revisor-independente",
        "estado": "reprovada",
        "verificado_em": "2026-09-08T12:00:00+00:00",
        "evidencia": "https://example.test/parecer",
    }
    auditoria["id"] = telemetria.identidade_auditoria(auditoria)

    assert (
        analisar_com_fila([evento, auditoria])["auditoria_independente"] == "reprovada"
    )


def test_revisao_da_analise_e_o_hash_do_codigo_carregado():
    conteudo_normalizado = Path(analise.__file__).read_text(encoding="utf-8").encode(
        "utf-8"
    )
    assert (
        analise.REVISAO_DA_ANALISE
        == __import__("hashlib").sha256(conteudo_normalizado).hexdigest()
    )
