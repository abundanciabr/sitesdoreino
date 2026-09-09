import json
from pathlib import Path

import responsabilidades
import medir_esforco
import fila


def escrever_registro(tmp_path: Path, registro: dict) -> Path:
    (tmp_path / "painel").mkdir()
    (tmp_path / "painel" / "responsabilidades.json").write_text(
        json.dumps(registro), encoding="utf-8"
    )
    return tmp_path


def registro_completo() -> dict:
    return {
        "funcoes": {
            nome: {"pessoa": "Pessoa", "substituto": "Substituto"}
            for nome in responsabilidades.FUNCOES
        },
        "unidades": [
            {
                "id": "curso",
                "titular_funcao": "ensino-comunidade",
                "pessoa": None,
                "substituto": None,
                "finalidade": "entregar",
                "acompanhamento": "revisar",
                "fonte": "fonte",
                "evidencia": "prova",
            },
            {"id": "aula", "herda_de": "curso", "finalidade": "entregar", "acompanhamento": "revisar", "fonte": "fonte", "evidencia": "prova"},
        ],
    }


def test_entrega_com_responsabilidade_herdada_e_pessoas_definidas(tmp_path):
    raiz = escrever_registro(tmp_path, registro_completo())
    assert responsabilidades.validar_entrega(raiz, "aula") == []


def test_entrega_sem_unidade_e_recusada(tmp_path):
    raiz = escrever_registro(tmp_path, registro_completo())
    assert responsabilidades.validar_entrega(raiz, "inexistente") == [
        "responsabilidade inexistente não foi cadastrada"
    ]


def test_heranca_circular_e_recusada(tmp_path):
    registro = registro_completo()
    registro["unidades"] = [{"id": "a", "herda_de": "b"}, {"id": "b", "herda_de": "a"}]
    raiz = escrever_registro(tmp_path, registro)
    assert responsabilidades.validar_entrega(raiz, "a") == ["herança circular em a"]


def test_auditoria_expõe_pessoas_e_substitutos_ausentes(tmp_path):
    registro = registro_completo()
    registro["funcoes"]["ensino-comunidade"]["pessoa"] = None
    raiz = escrever_registro(tmp_path, registro)
    erros = responsabilidades.auditar(raiz)
    assert "ensino-comunidade: pessoa ocupante ausente" in erros
    assert any("curso: função ensino-comunidade não tem pessoa ocupante" in erro for erro in erros)


def test_medicao_de_esforco_distingue_teste_de_trabalho_real(tmp_path):
    (tmp_path / "painel" / "medicoes").mkdir(parents=True)
    (tmp_path / "painel" / "medicoes" / "esforco.json").write_text(
        json.dumps({
            "coleta_iniciada_em": "2026-09-09",
            "situacao_linha_de_base": "iniciada, insuficiente para comparação",
            "observacoes": [{
                "id": "fixture", "natureza": "teste", "rotina": "x", "casos": 1,
                "minutos_referencia": 1, "minutos_humanos": 1, "minutos_revisao": 0,
                "minutos_retrabalho": 0, "minutos_excecoes": 0, "minutos_manutencao": 0, "excecoes": 0, "qualidade": "não avaliada; dado de teste",
                "reaberturas": None, "prazo": "teste", "periodo": "hoje",
                "condicoes": "fixture", "situacao_dado": "teste",
            }],
        }), encoding="utf-8"
    )
    assert medir_esforco.validar(tmp_path) == []
    assert medir_esforco.resumo(tmp_path)["produtividade_comprovada"] is False


def test_tarefa_nova_sem_responsabilidade_e_reconhecida_como_invalida():
    assert fila.tarefa_exige_responsabilidade({"criada_em": "2026-09-09"}) is True
    assert fila.tarefa_exige_responsabilidade({"criada_em": "2026-09-08"}) is False
    assert fila.normalizar_responsabilidade("  ensino-comunidade  ") == "ensino-comunidade"


def test_medicao_real_incompleta_e_recusada(tmp_path):
    (tmp_path / "painel" / "medicoes").mkdir(parents=True)
    (tmp_path / "painel" / "medicoes" / "esforco.json").write_text(
        json.dumps({"observacoes": [{"id": "real-invalido", "natureza": "operacao", "situacao_dado": "real", "casos": "muitos"}]}),
        encoding="utf-8",
    )
    erros = medir_esforco.validar(tmp_path)
    assert any("real-invalido: casos precisa ser inteiro" in erro for erro in erros)


def test_resumo_de_esforco_pesa_casos_pelo_tempo_de_referencia(tmp_path):
    (tmp_path / "painel" / "medicoes").mkdir(parents=True)
    observacao = {
        "id": "real", "natureza": "operacao", "rotina": "x", "casos": 2,
        "minutos_referencia": 100, "minutos_humanos": 50, "minutos_revisao": 0,
        "minutos_retrabalho": 0, "minutos_excecoes": 10, "minutos_manutencao": 0, "excecoes": 1, "qualidade": "confirmada",
        "reaberturas": 0, "prazo": "cumprido", "periodo": "hoje",
        "condicoes": "fixture", "situacao_dado": "real",
    }
    segunda = {**observacao, "id": "real-2", "casos": 20, "minutos_referencia": 20, "minutos_humanos": 0, "minutos_excecoes": 0}
    (tmp_path / "painel" / "medicoes" / "esforco.json").write_text(
        json.dumps({"produtividade_comprovada": True, "observacoes": [observacao, segunda]}),
        encoding="utf-8",
    )
    assert medir_esforco.resumo(tmp_path)["economia_media_percentual"] == 50.0


def test_ia_nao_pode_ser_titular_ou_substituta(tmp_path):
    registro = registro_completo()
    registro["funcoes"]["ensino-comunidade"]["pessoa"] = "agente de IA"
    registro["funcoes"]["ensino-comunidade"]["substituto"] = "IA"
    raiz = escrever_registro(tmp_path, registro)
    erros = responsabilidades.validar_entrega(raiz, "curso")
    assert any("não pode ter IA como pessoa ocupante" in erro for erro in erros)
    assert any("não pode ter IA como substituto" in erro for erro in erros)
