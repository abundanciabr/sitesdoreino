"""A promessa entre Admin e Cursos para o endereço de aulas avulsas."""

from pathlib import Path

import yaml


RAIZ = Path(__file__).resolve().parents[2]
CONTRATO = RAIZ / "contracts" / "cursos.openapi.yaml"
PADRAO_SLUG = "^[a-z0-9]+(?:-[a-z0-9]+)*$"


def contrato() -> dict:
    return yaml.safe_load(CONTRATO.read_text(encoding="utf-8"))


def test_edicao_de_aula_avulsa_aceita_slug_opcional_e_retorna_o_final_salvo() -> None:
    documento = contrato()
    operacao = documento["paths"]["/aulas-avulsas/{slug}"]["put"]
    corpo = operacao["requestBody"]["content"]["application/json"]["schema"]
    esquema = documento["components"]["schemas"][
        corpo["$ref"].removeprefix("#/components/schemas/")
    ]
    respostas = operacao["responses"]
    exemplos = respostas["200"]["content"]["application/json"]["examples"]

    assert corpo["$ref"] == "#/components/schemas/AulaAvulsaParaEditarSchema"
    assert esquema["additionalProperties"] is False
    assert esquema["properties"]["slug"] == {"pattern": PADRAO_SLUG, "type": "string"}
    assert "slug" not in esquema["required"]
    assert respostas["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/AulaAvulsaSchema"
    }
    assert exemplos["slug_identico"]["value"]["slug"] == "aula-de-testes"
    assert exemplos["slug_ocupado"]["value"]["slug"] == "aula-de-testes-2"
    assert exemplos["menor_sufixo_livre"]["value"]["slug"] == "aula-de-testes-3"
    assert (
        respostas["404"]["description"]
        == "Aula avulsa inexistente para este site e slug do caminho"
    )
    assert (
        respostas["422"]["description"]
        == "Corpo invalido, inclusive slug fora do formato permitido"
    )
