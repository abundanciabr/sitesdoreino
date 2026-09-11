"""A promessa entre Admin e Cursos para o endereço de aulas avulsas."""

from pathlib import Path

import yaml


RAIZ = Path(__file__).resolve().parents[2]
CONTRATO = RAIZ / "contracts" / "cursos.openapi.yaml"


def contrato() -> dict:
    return yaml.safe_load(CONTRATO.read_text(encoding="utf-8"))


def test_edicao_de_aula_avulsa_aceita_slug_opcional_e_retorna_o_final_salvo() -> None:
    documento = contrato()
    criacao = documento["paths"]["/aulas-avulsas"]["post"]
    operacao = documento["paths"]["/aulas-avulsas/{slug}"]["put"]
    requisicao = operacao["requestBody"]["content"]["application/json"]
    corpo = requisicao["schema"]
    esquema = documento["components"]["schemas"][
        corpo["$ref"].removeprefix("#/components/schemas/")
    ]
    respostas = operacao["responses"]
    exemplos = respostas["200"]["content"]["application/json"]["examples"]
    corpo_404 = respostas["404"]["content"]["application/json"]
    corpo_422 = respostas["422"]["content"]["application/json"]
    exemplos_404 = corpo_404["examples"]
    exemplos_422 = corpo_422["examples"]

    assert corpo["$ref"] == "#/components/schemas/AulaAvulsaParaEditarSchema"
    assert "somente quando o corpo do PUT omite `slug`" in criacao["description"]
    assert esquema["additionalProperties"] is False
    assert esquema["properties"]["slug"] == {"maxLength": 140, "type": "string"}
    assert "slug" not in esquema["required"]
    assert "slug" not in requisicao["examples"]["preservar_endereco"]["value"]
    assert (
        requisicao["examples"]["slug_normalizado"]["value"]["slug"] == "Ação & Testes"
    )
    assert operacao["x-normalizacao-de-slug"] == {
        "campo": "slug",
        "algoritmo": "unicode_para_ascii_minusculo_com_hifens",
        "exemplo": {"entrada": "Ação & Testes", "saida": "acao-testes"},
    }
    assert operacao["x-reserva-de-slug"] == {
        "chave": ["site_id", "slug"],
        "atomica": True,
        "exclui_aula_editada": True,
        "em_colisao": "menor_sufixo_numerico_livre",
        "repete_ate_reservar": True,
    }
    assert respostas["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/AulaAvulsaSchema"
    }
    assert exemplos["slug_identico"]["value"]["slug"] == "aula-de-testes"
    assert exemplos["slug_ocupado"]["value"]["slug"] == "aula-de-testes-2"
    assert exemplos["menor_sufixo_livre"]["value"]["slug"] == "aula-de-testes-3"
    assert exemplos["slug_normalizado"]["value"]["slug"] == "acao-testes"
    assert corpo_404["schema"]["properties"]["erro"] == {
        "const": "aula_avulsa_nao_encontrada",
        "type": "string",
    }
    assert corpo_404["schema"]["properties"]["o_que_fazer"]["minLength"] == 1
    assert "o_que_fazer" in corpo_404["schema"]["required"]
    assert corpo_422["schema"]["properties"]["erro"]["enum"] == [
        "corpo_invalido",
        "slug_invalido",
    ]
    assert corpo_422["schema"]["properties"]["o_que_fazer"]["minLength"] == 1
    assert "o_que_fazer" in corpo_422["schema"]["required"]
    assert exemplos_404["aula_nao_encontrada"]["value"] == {
        "erro": "aula_avulsa_nao_encontrada",
        "o_que_fazer": "Confira o endereço da aula ou escolha outra aula publicada.",
    }
    assert exemplos_422["slug_invalido"]["value"] == {
        "erro": "slug_invalido",
        "o_que_fazer": "Informe um endereço com ao menos uma letra ou número.",
    }
    assert (
        respostas["404"]["description"]
        == "Aula avulsa inexistente para este site e slug do caminho"
    )
    assert (
        respostas["422"]["description"]
        == "Corpo invalido, inclusive slug que nao gera letras ou numeros"
    )
