"""Guardas da medição confirmatória da Fase 4."""

from datetime import datetime, timedelta, timezone
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import analise_fase4 as analise  # noqa: E402
import telemetria  # noqa: E402


def tarefa(condicao, numero, *, piloto="fase3", estado="concluida", minutos=30,
           par=True, metricas=None):
    inicio = datetime(2026, 9, 1, tzinfo=timezone.utc) + timedelta(days=numero)
    fim = inicio + timedelta(minutes=minutos) if minutos is not None else None
    dados = {
        "evento": "tarefa_medida", "tarefa": f"TAR-{piloto}-{numero}-{condicao}",
        "tentativa": f"tentativa-{numero}-{condicao}",
        "branch": f"agent/ci/medicao-{numero}-{condicao}", "commit": "a" * 40,
        "pr": numero + 1, "piloto": piloto, "condicao": condicao,
        "par_id": f"par-{numero}" if par else None, "tipo": "correcao-transversal",
        "complexidade": "media", "natureza": "codigo", "componentes": "ci",
        "fronteiras_integracao": "uma", "migracao": "nao",
        "risco": "medio", "escopo_publicacao": "publicacao-verificada",
        "revisao_instrumento": "b" * 40,
        "inicio": inicio.isoformat(), "fim": fim.isoformat() if fim else None,
        "estado": estado, "fonte": "telemetria-de-teste",
        "metricas": metricas if metricas is not None else {
            "chamadas_modelo": 1, "chamadas_ferramenta": 2, "runner_minutos": 3,
            "retentativas": 0, "correcoes_revisao": 0, "reaberturas": 0,
            "minutos_adocao": 0, "minutos_manutencao": 0,
            "defeitos_escapados": 0, "violacoes_seguranca": 0,
        },
    }
    dados["id"] = telemetria.identidade_tarefa(dados)
    return dados


def test_sem_tarefas_medidas_nao_declara_ganho():
    resultado = analise.analisar([])
    assert resultado["instrumentacao"] == "parcial"
    assert resultado["avaliacao"] == "em coleta"
    assert all(p["resultado"] == "não avaliável" for p in resultado["pilotos"].values())


def test_repeticao_nao_inflama_a_amostra_e_fase_antiga_e_ignorada():
    evento = tarefa("antes", 1)
    fase_antiga = {"evento": "fase_operacional", "tarefa": "TAR-1"}
    resultado = analise.analisar([evento, evento, fase_antiga])
    assert resultado["observacoes"]["tarefas_validas"] == 1
    assert resultado["observacoes"]["eventos_antigos_ou_de_outras_fases"] == 1
    assert resultado["pilotos"]["fase3"]["amostra"]["antes"] == 1


def test_tentativas_da_mesma_tarefa_nao_formam_tarefas_novas():
    primeira = tarefa("antes", 1, minutos=20)
    retomada = tarefa("antes", 2, minutos=30)
    retomada["tarefa"] = primeira["tarefa"]
    retomada["tentativa"] = "retomada-1"
    retomada["par_id"] = primeira["par_id"]
    retomada["id"] = telemetria.identidade_tarefa(retomada)
    resultado = analise.analisar([primeira, retomada])
    assert resultado["observacoes"]["tarefas_validas"] == 1
    assert resultado["observacoes"]["tentativas_validas"] == 2
    assert resultado["pilotos"]["fase3"]["amostra"]["tentativas_observadas"] == 2


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
    sem_custo = tarefa("depois", 2, metricas={campo: None for campo in analise.METRICAS_DE_CUSTO})
    resultado = analise.analisar([sem_tempo, sem_custo])
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
    resultado = analise.analisar(eventos)
    amostra = resultado["pilotos"]["fase3"]["amostra"]
    assert amostra["pares"] == 19
    assert amostra["pares_incompletos"] == 1


def test_falha_com_tempo_nao_forma_par_de_tarefa_concluida():
    antes = tarefa("antes", 1, estado="falhou")
    depois = tarefa("depois", 1)
    resultado = analise.analisar([antes, depois])
    assert resultado["pilotos"]["fase3"]["amostra"]["pares"] == 0
    assert resultado["pilotos"]["fase3"]["amostra"]["pares_incompletos"] == 1


def test_atributo_diferente_exclui_par_e_fica_visivel():
    antes = tarefa("antes", 1)
    depois = tarefa("depois", 1)
    depois["risco"] = "alto"
    depois["id"] = telemetria.identidade_tarefa(depois)
    resultado = analise.analisar([antes, depois])
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
            depois["revisao_instrumento"] = "c" * 40
            depois["id"] = telemetria.identidade_tarefa(depois)
        eventos += [antes, depois]
    resultado = analise.analisar(eventos)
    assert resultado["pilotos"]["fase3"]["resultado"] == "inconclusivo"
    assert len(resultado["pilotos"]["fase3"]["comparabilidade"]["revisoes_do_instrumento"]) == 2


def test_vinte_pares_com_qualidade_preservada_podem_demonstrar_beneficio():
    eventos = []
    for numero in range(20):
        eventos += [tarefa("antes", numero, minutos=60), tarefa("depois", numero, minutos=30)]
    resultado = analise.analisar(eventos)
    piloto = resultado["pilotos"]["fase3"]
    assert piloto["amostra"]["antes"] == 20
    assert piloto["amostra"]["depois"] == 20
    assert piloto["amostra"]["pares"] == 20
    assert piloto["metrica_principal_minutos"]["reducao_relativa"] == 0.5
    assert piloto["incerteza_intervalo_pareado_minutos"] == [-30.0, -30.0]
    assert piloto["resultado"] == "benefício demonstrado no escopo"


def test_falha_de_qualidade_e_dado_ausente_impedem_aprovacao():
    eventos = []
    for numero in range(20):
        eventos += [tarefa("antes", numero), tarefa("depois", numero)]
    eventos[-1]["metricas"]["violacoes_seguranca"] = None
    eventos[-1]["id"] = telemetria.identidade_tarefa(eventos[-1])
    eventos[-2]["metricas"]["defeitos_escapados"] = 1
    eventos[-2]["id"] = telemetria.identidade_tarefa(eventos[-2])
    resultado = analise.analisar(eventos)
    piloto = resultado["pilotos"]["fase3"]
    assert piloto["qualidade"]["violacoes_seguranca"] is None
    assert piloto["qualidade"]["defeitos_escapados"] == 1
    assert piloto["resultado"] == "inconclusivo"


def test_evento_adulterado_fica_fora_da_analise():
    evento = tarefa("antes", 1)
    evento["tipo"] = "outro-tipo"
    resultado = analise.analisar([evento])
    assert resultado["observacoes"]["eventos_invalidos"] == 1
    assert resultado["observacoes"]["tarefas_validas"] == 0
    assert "outro-tipo" not in json.dumps(resultado, ensure_ascii=False)
