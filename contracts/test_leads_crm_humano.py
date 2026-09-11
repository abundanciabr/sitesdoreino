from pathlib import Path

import yaml


CONTRATO = Path(__file__).with_name("leads.openapi.yaml")


def carregar() -> dict:
    return yaml.safe_load(CONTRATO.read_text(encoding="utf-8"))


def operacao(documento: dict, caminho: str, metodo: str) -> dict:
    return documento["paths"][caminho][metodo]


def resposta(documento: dict, caminho: str, metodo: str, codigo: str) -> str:
    schema = operacao(documento, caminho, metodo)["responses"][codigo]["content"]
    return schema["application/json"]["schema"]["$ref"]


def test_listagem_separa_oportunidades_do_historico_do_lead():
    documento = carregar()
    listagem = operacao(documento, "/opportunities", "get")
    parametros = {item["name"]: item for item in listagem["parameters"]}

    assert list(parametros).count("lead_id") == 1
    assert parametros["lead_id"]["in"] == "query"
    assert parametros["situacao"]["schema"] == {
        "$ref": "#/components/schemas/SituacaoOportunidade"
    }
    assert resposta(documento, "/opportunities", "get", "200") == (
        "#/components/schemas/PaginaDeOportunidades"
    )
    assert documento["components"]["schemas"]["PaginaDeOportunidades"]["properties"][
        "itens"
    ]["items"] == {"$ref": "#/components/schemas/Oportunidade"}


def test_atrasadas_sao_restritas_as_oportunidades_abertas():
    documento = carregar()
    parametros = operacao(documento, "/opportunities", "get")["parameters"]
    atrasada = next(item for item in parametros if item["name"] == "atrasada")

    assert atrasada["description"] == (
        "Quando verdadeiro, retorna somente oportunidades com etapa aberta e próximo passo vencido."
    )


def test_titular_e_permissoes_sao_comerciais_e_explicitos_por_recurso():
    documento = carregar()
    schemas = documento["components"]["schemas"]
    assert schemas["TitularOportunidade"]["properties"]["funcao"]["enum"] == ["comercial"]

    esperadas = {
        ("/opportunities", "get"): ("oportunidade", "listar", "titular"),
        ("/opportunities", "post"): ("oportunidade", "criar", "titular_autorizado"),
        ("/opportunities/{opportunity_id}", "get"): ("oportunidade", "consultar", "titular"),
        ("/opportunities/{opportunity_id}", "patch"): ("oportunidade", "atualizar", "titular"),
        ("/opportunities/{opportunity_id}/history", "post"): ("oportunidade", "registrar_historico", "titular"),
        ("/opportunities/{opportunity_id}/transfers", "post"): ("oportunidade", "transferir", "titular"),
        ("/opportunities/{opportunity_id}/transfers/{transfer_id}/accept", "post"): ("transferencia", "aceitar", "novo_titular"),
        ("/opportunities/{opportunity_id}/transfers/{transfer_id}/refuse", "post"): ("transferencia", "recusar", "novo_titular"),
        ("/opportunities/{opportunity_id}/close", "post"): ("oportunidade", "encerrar", "titular"),
        ("/opportunities/{opportunity_id}/reopen", "post"): ("oportunidade", "reabrir", "titular"),
    }
    for (caminho, metodo), (recurso, acao, escopo) in esperadas.items():
        operacao_da_rota = operacao(documento, caminho, metodo)
        assert operacao_da_rota["x-autorizacao"] == {
            "recurso": recurso,
            "acao": acao,
            "permitido_para": ["comercial"],
            "escopo": escopo,
        }
        assert operacao_da_rota["responses"]["403"] == {
            "$ref": "#/components/responses/AcaoNaoAutorizada"
        }


def test_encerramento_exige_evidencia_nao_vazia():
    documento = carregar()
    encerramento = documento["components"]["schemas"]["EncerrarOportunidade"]

    assert encerramento["required"] == ["resultado", "motivo", "evidencia"]
    assert encerramento["properties"]["evidencia"]["minLength"] == 1


def test_mutacoes_retornao_evento_imutavel():
    documento = carregar()
    caminhos_de_oportunidade = [
        ("/opportunities/{opportunity_id}", "patch", "200"),
        ("/opportunities/{opportunity_id}/transfers/{transfer_id}/accept", "post", "200"),
        ("/opportunities/{opportunity_id}/close", "post", "200"),
        ("/opportunities/{opportunity_id}/reopen", "post", "200"),
    ]
    for caminho, metodo, codigo in caminhos_de_oportunidade:
        assert resposta(documento, caminho, metodo, codigo) == (
            "#/components/schemas/ResultadoDaMutacaoDaOportunidade"
        )

    for caminho, metodo, codigo in [
        ("/opportunities/{opportunity_id}/transfers", "post", "201"),
        ("/opportunities/{opportunity_id}/transfers/{transfer_id}/refuse", "post", "200"),
    ]:
        assert resposta(documento, caminho, metodo, codigo) == (
            "#/components/schemas/TransferenciaComEvento"
        )

    schemas = documento["components"]["schemas"]
    assert schemas["ResultadoDaMutacaoDaOportunidade"]["required"] == [
        "oportunidade",
        "evento",
    ]
    assert schemas["TransferenciaComEvento"]["required"] == ["transferencia", "evento"]
    assert set(schemas["RegistroHistoricoOportunidade"]["properties"]["tipo"]["enum"]) >= {
        "etapa_alterada",
        "transferencia_solicitada",
        "transferencia_aceita",
        "transferencia_recusada",
        "encerramento",
        "reabertura",
    }
    assert schemas["RegistroHistoricoOportunidade"]["description"] == (
        "Evento imutável da oportunidade; a API não expõe alteração nem remoção."
    )
