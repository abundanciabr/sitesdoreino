"""Os guardas dos três avisos do acompanhamento comercial humano.

O que está em jogo: até aqui, o fato de um comercial ter assumido uma pessoa da
casa vivia só dentro do banco da célula `leads`. Nenhuma outra célula tinha como
saber disso, e por isso nenhuma outra célula tinha como parar a automação que
fala com essa pessoa. Estes três esquemas são o que faz esse fato viajar.

Três leis governam os três, e cada uma tem aqui um teste que reprova quando ela
é afrouxada:

1. **Só identificador opaco viaja.** Nome, e-mail, telefone e texto escrito por
   humano ficam na `leads`. O evento é imutável: dado pessoal que entra nele não
   sai mais, e texto de histórico apodrece dentro do livro.
2. **O `site_id` viaja em todos.** É ele que impede uma célula consumidora de
   cruzar pessoas de sites diferentes.
3. **Envelope canônico** `{event, version, event_id, occurred_at, data}`
   (`contracts/README.md` pontos 4 e 5), com o exemplo válido morando dentro do
   próprio esquema, em `examples`, para que quem lê o contrato veja a carta.

Rode assim, da raiz do repositório:

    python -m pytest contracts/test_eventos_do_acompanhamento_humano.py -q
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker


AQUI = Path(__file__).parent
EVENTOS = AQUI / "eventos"

#: Os três fatos, e só eles. A lista está escrita aqui em vez de varrida do
#: disco de propósito: um quarto arquivo do mesmo assunto aparecendo sem passar
#: por este rito tem de reprovar, e não ser adotado em silêncio.
NOMES = (
    "oportunidade.assumida.v1",
    "oportunidade.transferencia-decidida.v1",
    "oportunidade.encerrada.v1",
)

#: O que cada evento carrega, inteiro. Pinar o conjunto (e não só conferir
#: presença) é o que faz um campo novo precisar passar por aqui: acrescentar um
#: `motivo` de texto livre a qualquer um deles reprova nesta linha antes de
#: reprovar na lei 1.
CAMPOS = {
    "oportunidade.assumida.v1": {
        "site_id",
        "oportunidade_id",
        "lead_id",
        "titular_id",
        "tipo",
    },
    "oportunidade.transferencia-decidida.v1": {
        "site_id",
        "oportunidade_id",
        "lead_id",
        "transferencia_id",
        "de_titular_id",
        "para_titular_id",
        "decisao",
    },
    "oportunidade.encerrada.v1": {
        "site_id",
        "oportunidade_id",
        "lead_id",
        "titular_id",
        "resultado",
    },
}

#: Nome de campo que denuncia dado pessoal ou texto escrito por humano. Os três
#: primeiros são campos que existem HOJE no contrato vivo da `leads`
#: (`motivo`, `motivo_recusa`, `evidencia`, `descricao`) e que a tentação manda
#: copiar para cá junto com o resto.
PROIBIDOS = (
    "motivo",
    "evidencia",
    "descricao",
    "nota",
    "historico",
    "nome",
    "email",
    "e_mail",
    "telefone",
    "whatsapp",
)


def evento(nome: str) -> dict:
    return json.loads((EVENTOS / f"{nome}.json").read_text(encoding="utf-8"))


def exemplo(nome: str) -> dict:
    """A única carta de exemplo do esquema, copiada para quem for sujá-la."""
    exemplos = evento(nome)["examples"]
    assert len(exemplos) == 1, f"{nome}: um exemplo por esquema, nem zero nem dois"
    return copy.deepcopy(exemplos[0])


def erros(nome: str, carta: dict) -> list:
    validador = Draft202012Validator(evento(nome), format_checker=FormatChecker())
    return list(validador.iter_errors(carta))


def nomes_de_campo(schema: dict) -> list[str]:
    achados: list[str] = []
    for chave, valor in (schema.get("properties") or {}).items():
        achados.append(chave)
        if isinstance(valor, dict):
            achados.extend(nomes_de_campo(valor))
    return achados


# ---------------------------------------------------------------------------
# O instrumento, antes das medições que dependem dele
# ---------------------------------------------------------------------------


def test_o_validador_confere_uuid_de_verdade() -> None:
    """Formato que o `jsonschema` não conhece CONFORMA em silêncio.

    `FormatChecker().conforms(qualquer_coisa, "date-time")` devolve `True` nesta
    instalação, porque `date-time` não está entre os conferidores instalados.
    Sem esta linha, o teste do `event_id` inválido lá embaixo seria verde por não
    medir nada, e ninguém descobriria até a primeira carta torta no fio.
    """
    assert not FormatChecker().conforms("nao-e-uuid", "uuid")


# ---------------------------------------------------------------------------
# O envelope e a carta de exemplo
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("nome", NOMES)
def test_o_exemplo_do_proprio_esquema_passa_no_proprio_esquema(nome: str) -> None:
    assert erros(nome, exemplo(nome)) == []


@pytest.mark.parametrize("nome", NOMES)
def test_o_envelope_e_o_canonico_da_casa(nome: str) -> None:
    schema = evento(nome)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["required"] == [
        "event",
        "version",
        "event_id",
        "occurred_at",
        "data",
    ]
    assert schema["additionalProperties"] is False
    assert schema["properties"]["event"]["const"] == nome.removesuffix(".v1")
    assert schema["properties"]["version"]["const"] == 1
    assert schema["properties"]["event_id"]["format"] == "uuid"
    assert schema["properties"]["occurred_at"]["format"] == "date-time"


@pytest.mark.parametrize("nome", NOMES)
def test_o_evento_nao_aceita_campo_que_ele_nao_declarou(nome: str) -> None:
    carta = exemplo(nome)
    carta["data"]["observacao"] = "qualquer coisa"
    assert erros(nome, carta), f"{nome} aceitou um campo que não declarou"


@pytest.mark.parametrize("nome", NOMES)
def test_o_event_id_precisa_ser_um_uuid(nome: str) -> None:
    carta = exemplo(nome)
    carta["event_id"] = "isto-nao-e-um-uuid"
    assert erros(nome, carta), f"{nome} aceitou um event_id que não é uuid"


# ---------------------------------------------------------------------------
# Lei 1 — só identificador opaco viaja
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("nome", NOMES)
def test_nenhum_campo_carrega_dado_pessoal_nem_texto_de_humano(nome: str) -> None:
    """O evento é imutável: o que entra aqui não sai mais.

    O contrato vivo da `leads` tem `motivo`, `motivo_recusa`, `evidencia` e
    `descricao`, todos escritos por gente. Nenhum deles atravessa a fronteira:
    quem precisar do detalhe pergunta à `leads` pelo `oportunidade_id`.
    """
    for campo in nomes_de_campo(evento(nome)):
        assert campo not in PROIBIDOS, f"{nome} carrega o campo {campo}"


@pytest.mark.parametrize("nome", NOMES)
def test_o_evento_carrega_exatamente_os_campos_desta_lista(nome: str) -> None:
    dados = evento(nome)["properties"]["data"]
    assert set(dados["properties"]) == CAMPOS[nome]
    assert set(dados["required"]) == CAMPOS[nome]
    assert dados["additionalProperties"] is False


@pytest.mark.parametrize("nome", NOMES)
def test_nenhum_identificador_pode_chegar_vazio(nome: str) -> None:
    """`required` aceita string vazia, e vazio aqui é pior que ausente.

    Duas oportunidades com `oportunidade_id` vazio dividiriam a mesma chave do
    lado de quem consome, e a segunda sumiria em silêncio. Quem recusa é o
    `minLength`.
    """
    dados = evento(nome)["properties"]["data"]["properties"]
    for campo, schema in dados.items():
        if "enum" in schema:
            continue
        assert schema["minLength"] == 1, f"{nome}.{campo} aceita string vazia"

    carta = exemplo(nome)
    carta["data"]["site_id"] = ""
    assert erros(nome, carta), f"{nome} aceitou um site_id vazio"


# ---------------------------------------------------------------------------
# Lei 2 — o site viaja em todos
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("nome", NOMES)
def test_o_site_viaja_em_todos_os_tres(nome: str) -> None:
    """Sem ele, uma célula consumidora cruza pessoas de sites diferentes."""
    carta = exemplo(nome)
    del carta["data"]["site_id"]
    assert erros(nome, carta), f"{nome} aceitou uma carta sem site_id"


# ---------------------------------------------------------------------------
# Os três fatos, um a um
# ---------------------------------------------------------------------------


def test_assumida_distingue_a_abertura_da_reabertura() -> None:
    """A automação para nas DUAS, e é por isso que as duas são o mesmo fato.

    Reabrir é assumir de novo. Se a reabertura não publicasse este evento, quem
    tivesse voltado a automatizar depois do encerramento nunca saberia que
    precisa parar outra vez, e a pessoa receberia robô e comercial ao mesmo
    tempo.
    """
    dados = evento("oportunidade.assumida.v1")["properties"]["data"]["properties"]
    assert dados["tipo"]["enum"] == ["abertura", "reabertura"]

    carta = exemplo("oportunidade.assumida.v1")
    carta["data"]["tipo"] = "transferencia"
    assert erros("oportunidade.assumida.v1", carta), (
        "assumida aceitou um tipo fora dos dois que existem"
    )


def test_a_transferencia_diz_a_decisao_e_os_dois_titulares() -> None:
    """Recusada é um fato, e um fato que diz que nada mudou.

    Os dois titulares viajam nas duas decisões, e é o par que responde quem
    responde pela pessoa agora: em `aceita` é o `para_titular_id`, em `recusada`
    continua sendo o `de_titular_id`. Nenhum campo derivado é publicado, porque
    um campo derivado dentro de evento imutável envelhece contra o próprio
    evento.
    """
    nome = "oportunidade.transferencia-decidida.v1"
    dados = evento(nome)["properties"]["data"]["properties"]
    assert dados["decisao"]["enum"] == ["aceita", "recusada"]
    assert "titular_id" not in dados

    carta = exemplo(nome)
    carta["data"]["decisao"] = "pendente"
    assert erros(nome, carta), "a transferência publicou uma decisão que não existe"


def test_o_encerramento_traz_o_titular_porque_ele_e_a_autorizacao() -> None:
    """Quem encerra é o titular, e o provedor recusa qualquer outro.

    (`services/leads/apps/core/oportunidades.py::_oportunidade_da_conta`.) Por
    isso este evento é a própria autorização para a automação voltar, e por isso
    nenhuma célula consumidora precisa de um segundo modelo de responsabilidade.
    """
    nome = "oportunidade.encerrada.v1"
    dados = evento(nome)["properties"]["data"]["properties"]
    assert dados["resultado"]["enum"] == ["ganha", "perdida", "desqualificada"]
    assert "titular_id" in evento(nome)["properties"]["data"]["required"]

    carta = exemplo(nome)
    carta["data"]["resultado"] = "aberta"
    assert erros(nome, carta), "o encerramento aceitou um resultado que não encerra"


def test_o_resultado_do_encerramento_e_o_do_contrato_vivo_da_leads() -> None:
    """O vocabulário não se reinventa na fronteira.

    `DesfechoOportunidade.resultado` e `EtapaEncerradaOportunidade` já dizem
    estas três palavras em `contracts/leads.openapi.yaml`. Um quarto valor aqui,
    ou um sinônimo, obrigaria cada consumidor a manter uma tabela de tradução.
    """
    import yaml  # noqa: PLC0415

    leads = yaml.safe_load((AQUI / "leads.openapi.yaml").read_text(encoding="utf-8"))
    do_contrato = leads["components"]["schemas"]["DesfechoOportunidade"]["properties"]
    do_evento = evento("oportunidade.encerrada.v1")["properties"]["data"]["properties"]
    assert do_evento["resultado"]["enum"] == do_contrato["resultado"]["enum"]
