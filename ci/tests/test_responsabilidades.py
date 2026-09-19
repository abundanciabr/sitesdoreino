import json
import os
from pathlib import Path
import subprocess

import pytest

import responsabilidades
import medir_esforco
import fila


def observacao_real(**sobrescritas):
    observacao = {
        "id": "real",
        "natureza": "operacao",
        "rotina": "triagem",
        "casos": 1,
        "minutos_referencia": 100,
        "minutos_humanos": 40,
        "minutos_revisao": 0,
        "minutos_retrabalho": 0,
        "minutos_excecoes": 0,
        "minutos_manutencao": 0,
        "excecoes": 0,
        "qualidade": "avaliada",
        "reaberturas": 0,
        "prazo": "cumprido",
        "periodo": "2026-09-01/2026-09-07",
        "condicoes": "comparável",
        "situacao_dado": "real",
    }
    observacao.update(sobrescritas)
    return observacao


def escrever_registro(tmp_path: Path, registro: dict) -> Path:
    (tmp_path / "painel").mkdir()
    (tmp_path / "painel" / "responsabilidades.json").write_text(
        json.dumps(registro), encoding="utf-8"
    )
    (tmp_path / "painel" / "fonte.txt").write_text("fonte", encoding="utf-8")
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
                "tipo": "processo",
                "prepara": "Pessoa",
                "executa": "Pessoa",
                "aprova": "Ensino e Comunidade",
                "excecoes": "nenhuma",
                "autoridade": "Decide: define a entrega. Escala para: mantenedor.",
                "acompanhamento": "revisar",
                "fonte": "painel/fonte.txt",
                "evidencia": "prova",
            },
            {
                "id": "aula",
                "herda_de": "curso",
                "finalidade": "entregar",
                "acompanhamento": "revisar",
                "fonte": "painel/fonte.txt",
                "evidencia": "prova",
            },
        ],
    }


def test_entrega_com_responsabilidade_herdada_e_pessoas_definidas(tmp_path):
    raiz = escrever_registro(tmp_path, registro_completo())
    assert responsabilidades.validar_entrega(raiz, "aula") == []
    assert responsabilidades.auditar(raiz) == []
    registro = registro_completo()
    registro["unidades"][1]["aprova"] = "IA"
    (tmp_path / "painel" / "responsabilidades.json").write_text(
        json.dumps(registro), encoding="utf-8"
    )
    assert any(
        "IA não pode ocupar o campo aprova" in erro
        for erro in responsabilidades.validar_entrega(tmp_path, "aula")
    )
    assert any(
        "IA não pode ocupar o campo aprova" in erro
        for erro in responsabilidades.auditar(tmp_path)
    )


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
    assert any(
        "curso: função ensino-comunidade não tem pessoa ocupante" in erro
        for erro in erros
    )


def test_medicao_de_esforco_distingue_teste_de_trabalho_real(tmp_path):
    (tmp_path / "painel" / "medicoes").mkdir(parents=True)
    (tmp_path / "painel" / "medicoes" / "esforco.json").write_text(
        json.dumps(
            {
                "coleta_iniciada_em": "2026-09-09",
                "situacao_linha_de_base": "iniciada, insuficiente para comparação",
                "observacoes": [
                    {
                        "id": "fixture",
                        "natureza": "teste",
                        "rotina": "x",
                        "casos": 1,
                        "minutos_referencia": 1,
                        "minutos_humanos": 1,
                        "minutos_revisao": 0,
                        "minutos_retrabalho": 0,
                        "minutos_excecoes": 0,
                        "minutos_manutencao": 0,
                        "excecoes": 0,
                        "qualidade": "não avaliada; dado de teste",
                        "reaberturas": None,
                        "prazo": "teste",
                        "periodo": "hoje",
                        "condicoes": "fixture",
                        "situacao_dado": "teste",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    assert medir_esforco.validar(tmp_path) == []
    assert medir_esforco.resumo(tmp_path)["produtividade_comprovada"] is False


def test_tarefa_nova_sem_responsabilidade_e_reconhecida_como_invalida():
    assert (
        fila.tarefa_exige_responsabilidade(
            {"criada_em": "2026-09-09", "responsabilidade_obrigatoria": True}
        )
        is True
    )
    assert fila.tarefa_exige_responsabilidade({"criada_em": "2026-09-08"}) is False
    assert (
        fila.normalizar_responsabilidade("  ensino-comunidade  ") == "ensino-comunidade"
    )
    assert (
        fila.tarefa_exige_responsabilidade(
            {"criada_em": "2026-09-09", "responsabilidade": "x"}
        )
        is False
    )


def test_unidade_sem_id_e_recusada_sem_traceback(tmp_path):
    registro = registro_completo()
    registro["unidades"].append({"finalidade": "sem id"})
    raiz = escrever_registro(tmp_path, registro)
    assert "unidade sem id válido" in responsabilidades.auditar(raiz)


def test_medicao_recusa_booleano_e_numero_infinito(tmp_path):
    (tmp_path / "painel" / "medicoes").mkdir(parents=True)
    observacao = {
        "id": "real",
        "natureza": "operacao",
        "rotina": "x",
        "casos": 1,
        "minutos_referencia": True,
        "minutos_humanos": float("inf"),
        "minutos_revisao": 0,
        "minutos_retrabalho": 0,
        "minutos_excecoes": 0,
        "minutos_manutencao": 0,
        "excecoes": 0,
        "qualidade": "confirmada",
        "reaberturas": 0,
        "prazo": "cumprido",
        "periodo": "hoje",
        "condicoes": "fixture",
        "situacao_dado": "real",
    }
    (tmp_path / "painel" / "medicoes" / "esforco.json").write_text(
        json.dumps({"observacoes": [observacao]}), encoding="utf-8"
    )
    erros = medir_esforco.validar(tmp_path)
    assert any("minutos_referencia precisa ser número" in erro for erro in erros)
    assert any("minutos_humanos precisa ser número" in erro for erro in erros)


def test_medicao_real_incompleta_e_recusada(tmp_path):
    (tmp_path / "painel" / "medicoes").mkdir(parents=True)
    (tmp_path / "painel" / "medicoes" / "esforco.json").write_text(
        json.dumps(
            {
                "observacoes": [
                    {
                        "id": "real-invalido",
                        "natureza": "operacao",
                        "situacao_dado": "real",
                        "casos": "muitos",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    erros = medir_esforco.validar(tmp_path)
    assert any("real-invalido: casos precisa ser inteiro" in erro for erro in erros)


def test_resumo_de_esforco_pesa_casos_pelo_tempo_de_referencia(tmp_path):
    (tmp_path / "painel" / "medicoes").mkdir(parents=True)
    observacao = observacao_real(casos=2, minutos_humanos=50, minutos_excecoes=10)
    segunda = {
        **observacao,
        "id": "real-2",
        "casos": 20,
        "minutos_referencia": 20,
        "minutos_humanos": 0,
        "minutos_excecoes": 0,
    }
    (tmp_path / "painel" / "medicoes" / "esforco.json").write_text(
        json.dumps(
            {"produtividade_comprovada": True, "observacoes": [observacao, segunda]}
        ),
        encoding="utf-8",
    )
    assert medir_esforco.resumo(tmp_path)["economia_media_percentual"] == 80.0


def test_medicao_inconclusiva_e_valida_sem_comprovar_produtividade(tmp_path):
    (tmp_path / "painel" / "medicoes").mkdir(parents=True)
    observacao = observacao_real(casos=2, minutos_humanos=10)
    conclusoes = {
        chave: {
            "estado": "inconclusivo",
            "evidencia": "prova",
            "consequencia": "continuar medindo",
        }
        for chave in medir_esforco.CONCLUSOES
    }
    (tmp_path / "painel" / "medicoes" / "esforco.json").write_text(
        json.dumps(
            {
                "observacoes": [observacao, {**observacao, "id": "real-2"}],
                "conclusoes": conclusoes,
            }
        ),
        encoding="utf-8",
    )
    assert medir_esforco.validar(tmp_path) == []
    assert medir_esforco.resumo(tmp_path)["produtividade_comprovada"] is False


def test_medicao_recusa_identificador_duplicado_rotina_vazia_e_periodo_invalido(
    tmp_path,
):
    (tmp_path / "painel" / "medicoes").mkdir(parents=True)
    observacao = observacao_real(rotina="", periodo="hoje")
    (tmp_path / "painel" / "medicoes" / "esforco.json").write_text(
        json.dumps({"observacoes": [observacao, {**observacao}]}),
        encoding="utf-8",
    )

    erros = medir_esforco.validar(tmp_path)

    assert "real: identificador duplicado" in erros
    assert "real: rotina precisa ser texto preenchido" in erros
    assert "real: periodo precisa usar AAAA-MM-DD/AAAA-MM-DD" in erros


def test_dado_sintetico_e_melhoria_nao_criam_maturidade(tmp_path):
    (tmp_path / "painel" / "medicoes").mkdir(parents=True)
    teste = {
        **observacao_real(
            id="teste",
            natureza="teste",
            situacao_dado="teste",
            qualidade="não avaliada; dado de teste",
        ),
        "reaberturas": None,
    }
    melhoria = observacao_real(id="melhoria", natureza="melhoria")
    (tmp_path / "painel" / "medicoes" / "esforco.json").write_text(
        json.dumps({"observacoes": [teste, melhoria]}),
        encoding="utf-8",
    )

    resumo = medir_esforco.resumo(tmp_path)

    assert resumo["observacoes_reais_coletadas"] == 1
    assert resumo["observacoes_reais"] == 0
    assert resumo["economia_comprovada"] is False
    assert resumo["meta_atingida"] is False


def test_economia_comprovada_fica_separada_da_meta_de_oitenta_por_cento(tmp_path):
    (tmp_path / "painel" / "medicoes").mkdir(parents=True)
    observacao = observacao_real(id="real-1", casos=1, minutos_humanos=50)
    segunda = observacao_real(id="real-2", casos=1, minutos_humanos=50)
    conclusoes = {
        chave: {
            "estado": "comprovado",
            "evidencia": "prova",
            "consequencia": "seguir medindo",
        }
        for chave in medir_esforco.CONCLUSOES
    }
    (tmp_path / "painel" / "medicoes" / "esforco.json").write_text(
        json.dumps({"observacoes": [observacao, segunda], "conclusoes": conclusoes}),
        encoding="utf-8",
    )

    resumo = medir_esforco.resumo(tmp_path)

    assert resumo["economia_media_percentual"] == 50.0
    assert resumo["economia_comprovada"] is True
    assert resumo["meta_atingida"] is False
    assert resumo["vereditos"]["economia"] == "comprovado"
    assert resumo["vereditos"]["meta_atingida"] == "inconclusivo"
    assert resumo["produtividade_comprovada"] is True


def test_ia_nao_pode_ser_titular_ou_substituta(tmp_path):
    registro = registro_completo()
    registro["funcoes"]["ensino-comunidade"]["pessoa"] = "agente de IA"
    registro["funcoes"]["ensino-comunidade"]["substituto"] = "IA"
    raiz = escrever_registro(tmp_path, registro)
    erros = responsabilidades.validar_entrega(raiz, "curso")
    assert any("não pode ter IA como pessoa ocupante" in erro for erro in erros)
    assert any("não pode ter IA como substituto" in erro for erro in erros)


def escrever_inventario_de_recursos(raiz: Path) -> None:
    (raiz / "celulas.yml").write_text(
        "celulas:\n  admin:\n    caminhos: [painel]\n    consome: []\n  funil:\n    caminhos: [services/funil]\n    consome: []\n",
        encoding="utf-8",
    )
    (raiz / "painel" / "mapa-do-site.json").write_text(
        json.dumps(
            {
                "enderecos": [
                    {
                        "celula": "admin",
                        "rota": "",
                        "endereco": "/admin/",
                        "alcance": "publico",
                        "para_quem": "equipe",
                        "titulo": "Admin",
                        "descricao": "Painel",
                    },
                    {
                        "celula": "funil",
                        "rota": "",
                        "endereco": "/",
                        "alcance": "publico",
                        "para_quem": "visitante",
                        "titulo": "Entrada",
                        "descricao": "Site",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def test_auditoria_recusa_recurso_sem_vinculo_e_vinculo_ambiguo(tmp_path):
    registro = registro_completo()
    registro["unidades"][0]["recursos"] = {"celulas": ["admin"]}
    raiz = escrever_registro(tmp_path, registro)
    escrever_inventario_de_recursos(raiz)

    assert (
        "recurso conhecido sem responsabilidade: celula:funil"
        in responsabilidades.auditar(raiz)
    )

    registro["unidades"].append(
        {
            **registro["unidades"][0],
            "id": "outra-responsabilidade",
        }
    )
    (raiz / "painel" / "responsabilidades.json").write_text(
        json.dumps(registro), encoding="utf-8"
    )
    assert (
        "recurso conhecido com vínculo ambíguo: celula:admin"
        in responsabilidades.auditar(raiz)
    )


def test_auditoria_recusa_fonte_e_alcada_sem_referencia_concreta(tmp_path):
    registro = registro_completo()
    registro["unidades"][0]["fonte"] = "fonte genérica"
    registro["unidades"][0]["aprova"] = "alguém aprova"
    registro["unidades"][0]["autoridade"] = "conforme necessário"
    raiz = escrever_registro(tmp_path, registro)

    erros = responsabilidades.auditar(raiz)
    assert "curso: fonte precisa listar referências concretas" in erros
    assert "curso: aprova precisa identificar funções responsáveis" in erros
    assert "curso: autoridade precisa declarar decisão e escalonamento" in erros


def test_auditoria_recusa_heranca_por_id_duplicado(tmp_path):
    registro = registro_completo()
    registro["unidades"].append({**registro["unidades"][0], "finalidade": "outra"})
    raiz = escrever_registro(tmp_path, registro)

    assert (
        "identificador de responsabilidade duplicado: curso"
        in responsabilidades.auditar(raiz)
    )


@pytest.mark.parametrize(
    "fonte",
    [
        "services/inexistente.py",
        "painel",
        "texto services/inexistente.py",
    ],
)
def test_auditoria_recusa_fonte_que_nao_resolve_para_arquivo(tmp_path, fonte):
    registro = registro_completo()
    registro["unidades"][0]["fonte"] = fonte
    raiz = escrever_registro(tmp_path, registro)

    assert (
        "curso: fonte precisa listar referências concretas"
        in responsabilidades.auditar(raiz)
    )


def test_auditoria_recusa_decisao_ou_escalonamento_vazio(tmp_path):
    registro = registro_completo()
    raiz = escrever_registro(tmp_path, registro)
    assert responsabilidades.auditar(raiz) == []

    registro["unidades"][0]["autoridade"] = "Decide:   Escala para: mantenedor."
    (raiz / "painel" / "responsabilidades.json").write_text(
        json.dumps(registro), encoding="utf-8"
    )
    assert (
        "curso: autoridade precisa declarar decisão e escalonamento"
        in responsabilidades.auditar(raiz)
    )


def test_auditoria_recusa_fonte_simbolica_fora_da_bancada(tmp_path):
    registro = registro_completo()
    registro["unidades"][0]["fonte"] = "painel/fonte/link.txt"
    raiz = escrever_registro(tmp_path, registro)
    fonte = raiz / "painel" / "fonte"
    fonte.mkdir()
    (fonte / "link.txt").write_text("dentro", encoding="utf-8")
    assert responsabilidades.auditar(raiz) == []

    externa = tmp_path.parent / f"{tmp_path.name}-fonte-externa"
    externa.mkdir()
    (externa / "link.txt").write_text("fora", encoding="utf-8")
    (fonte / "link.txt").unlink()
    fonte.rmdir()
    try:
        fonte.symlink_to(externa, target_is_directory=True)
    except OSError:
        if os.name != "nt":
            raise
        resultado = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(fonte), str(externa)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert resultado.returncode == 0, resultado.stderr

    assert (
        "curso: fonte precisa listar referências concretas"
        in responsabilidades.auditar(raiz)
    )

    registro["unidades"][0]["autoridade"] = "Decide: aprova a entrega. Escala para:   "
    (raiz / "painel" / "responsabilidades.json").write_text(
        json.dumps(registro), encoding="utf-8"
    )
    assert (
        "curso: autoridade precisa declarar decisão e escalonamento"
        in responsabilidades.auditar(raiz)
    )
