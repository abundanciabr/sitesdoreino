"""CONTRATO ADITIVO — o que ele deixa passar e o que ele trava (Onda 5).

A propriedade central: **acrescentar é livre, remover exige autorização**. Ela
precisa de guarda pelos dois lados, e por motivos opostos:

- se ele travar adição, o rito vira burocracia e alguém vai contorná-lo;
- se ele deixar passar remoção, o consumidor quebra em produção — e o
  contrato, que existe para impedir exatamente isso, vira decoração.

Cada cenário é um par de documentos OpenAPI (antes/depois) que a função de
comparação recebe direto. Montar o repositório Git inteiro para cada caso
tornaria a suíte lenta o bastante para alguém querer pular — e um portão
testado devagar demais é um portão que envelhece.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "ci"))

import contrato_aditivo as ca  # noqa: E402
from _nucleo import ErroDeInstrumentacao, Estado  # noqa: E402


def _doc(paths=None, schemas=None):
    doc = {"openapi": "3.1.0", "info": {"title": "t", "version": "1"}, "paths": paths or {}}
    if schemas is not None:
        doc["components"] = {"schemas": schemas}
    return doc


UMA_ROTA = {"/leads": {"post": {"responses": {"201": {}, "422": {}}}}}


# --------------------------------------------------------------------------
# O que PASSA — adição, em todas as formas
# --------------------------------------------------------------------------


def test_caminho_novo_passa():
    depois = {**UMA_ROTA, "/leads/{id}": {"get": {"responses": {"200": {}}}}}
    assert ca.quebras(_doc(UMA_ROTA), _doc(depois), "c.yaml") == []


def test_operacao_nova_no_mesmo_caminho_passa():
    depois = {"/leads": {**UMA_ROTA["/leads"], "get": {"responses": {"200": {}}}}}
    assert ca.quebras(_doc(UMA_ROTA), _doc(depois), "c.yaml") == []


def test_resposta_nova_passa():
    """Foi exatamente o caso real do 502 do provedor (PRs #417 e #420)."""
    depois = {"/leads": {"post": {"responses": {"201": {}, "422": {}, "502": {}}}}}
    assert ca.quebras(_doc(UMA_ROTA), _doc(depois), "c.yaml") == []


def test_propriedade_nova_e_OPCIONAL_passa():
    antes = _doc(UMA_ROTA, {"Lead": {"properties": {"email": {}}}})
    depois = _doc(UMA_ROTA, {"Lead": {"properties": {"email": {}, "nome": {}}}})
    assert ca.quebras(antes, depois, "c.yaml") == []


def test_parametro_novo_e_OPCIONAL_passa():
    antes = _doc({"/leads": {"get": {"responses": {"200": {}}, "parameters": []}}})
    depois = _doc(
        {
            "/leads": {
                "get": {
                    "responses": {"200": {}},
                    "parameters": [{"name": "pagina", "required": False}],
                }
            }
        }
    )
    assert ca.quebras(antes, depois, "c.yaml") == []


# --------------------------------------------------------------------------
# O que TRAVA — a lista fechada de quebras
# --------------------------------------------------------------------------


def test_caminho_removido_trava():
    achados = ca.quebras(_doc(UMA_ROTA), _doc({}), "c.yaml")
    assert achados and "REMOVIDO" in achados[0] and "/leads" in achados[0]


def test_operacao_removida_trava():
    antes = _doc({"/leads": {"post": {"responses": {"201": {}}}, "get": {"responses": {"200": {}}}}})
    depois = _doc({"/leads": {"post": {"responses": {"201": {}}}}})
    achados = ca.quebras(antes, depois, "c.yaml")
    assert any("GET /leads" in a for a in achados), achados


def test_resposta_removida_trava():
    depois = {"/leads": {"post": {"responses": {"201": {}}}}}
    achados = ca.quebras(_doc(UMA_ROTA), _doc(depois), "c.yaml")
    assert any("422" in a for a in achados), achados


def test_propriedade_removida_do_schema_trava():
    antes = _doc(UMA_ROTA, {"Lead": {"properties": {"email": {}, "nome": {}}}})
    depois = _doc(UMA_ROTA, {"Lead": {"properties": {"email": {}}}})
    achados = ca.quebras(antes, depois, "c.yaml")
    assert any("Lead.nome" in a for a in achados), achados


def test_componente_removido_trava():
    antes = _doc(UMA_ROTA, {"Lead": {}, "Erro": {}})
    depois = _doc(UMA_ROTA, {"Lead": {}})
    achados = ca.quebras(antes, depois, "c.yaml")
    assert any("schemas/Erro" in a for a in achados), achados


def test_propriedade_que_VIRA_obrigatoria_trava():
    """O caso que passa despercebido: 'só acrescentei um required'.

    Não removeu nada, e mesmo assim quebra TODO cliente que já envia sem o
    campo. É a quebra mais fácil de fazer sem perceber.
    """
    antes = _doc(UMA_ROTA, {"Lead": {"properties": {"email": {}, "nome": {}}}})
    depois = _doc(
        UMA_ROTA,
        {"Lead": {"properties": {"email": {}, "nome": {}}, "required": ["nome"]}},
    )
    achados = ca.quebras(antes, depois, "c.yaml")
    assert any("OBRIGATÓRIO" in a and "Lead.nome" in a for a in achados), achados


def test_parametro_novo_JA_obrigatorio_trava():
    antes = _doc({"/leads": {"get": {"responses": {"200": {}}}}})
    depois = _doc(
        {
            "/leads": {
                "get": {
                    "responses": {"200": {}},
                    "parameters": [{"name": "conta", "required": True}],
                }
            }
        }
    )
    achados = ca.quebras(antes, depois, "c.yaml")
    assert any("OBRIGATÓRIO" in a and "conta" in a for a in achados), achados


# --------------------------------------------------------------------------
# O documento que não dá para comparar
# --------------------------------------------------------------------------


@pytest.mark.parametrize("texto", ["", "isto: não é openapi", "[1, 2, 3]", "::: torto"])
def test_documento_sem_forma_de_openapi_e_ERROR_nunca_nada_removido(texto: str):
    """Comparar dois documentos sem forma conhecida diria "nada removido".

    E "nada removido" sobre um arquivo que o portão não entendeu é a pior
    resposta possível: parece um veredito e é uma ausência de medição.
    """
    with pytest.raises(ErroDeInstrumentacao):
        ca._doc(texto, "c.yaml")


# --------------------------------------------------------------------------
# O portão inteiro, contra um repositório Git de verdade
# --------------------------------------------------------------------------


def _repo(tmp_path: Path) -> Path:
    raiz = tmp_path / "repo"
    (raiz / "contracts").mkdir(parents=True)
    (raiz / "ci").mkdir()
    for marca in ("CONSTITUICAO.md", "INVARIANTES.md"):
        (raiz / marca).write_text("cenario", encoding="utf-8")
    (raiz / "services").mkdir()
    (raiz / "contracts" / "x.openapi.yaml").write_text(
        "openapi: 3.1.0\npaths:\n  /a:\n    get:\n      responses:\n"
        "        '200': {}\n        '404': {}\n",
        encoding="utf-8",
    )
    for comando in (
        ["git", "init", "-q", "-b", "main"],
        ["git", "config", "user.email", "t@e"],
        ["git", "config", "user.name", "t"],
        ["git", "add", "-A"],
        ["git", "commit", "-qm", "base"],
    ):
        subprocess.run(comando, cwd=str(raiz), check=True, capture_output=True, timeout=120)
    return raiz


def _commitar(raiz: Path, conteudo: str) -> None:
    (raiz / "contracts" / "x.openapi.yaml").write_text(conteudo, encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=str(raiz), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-qm", "mudanca"], cwd=str(raiz), check=True, capture_output=True
    )


def test_o_portao_reprova_remocao_de_verdade(tmp_path: Path, monkeypatch):
    raiz = _repo(tmp_path)
    _commitar(
        raiz, "openapi: 3.1.0\npaths:\n  /a:\n    get:\n      responses:\n        '200': {}\n"
    )
    monkeypatch.setenv("BASE_REF", "HEAD~1")
    monkeypatch.delenv("PR_LABELS", raising=False)
    relatorio = ca.rodar(raiz)
    assert relatorio.estado is Estado.FAIL, relatorio.render()
    assert "404" in relatorio.render()


def test_a_etiqueta_autoriza_e_o_achado_continua_no_log(
    tmp_path: Path, monkeypatch, capsys
):
    """Autorizar não é apagar: a quebra fica escrita, com nome e sobrenome.

    E ela precisa aparecer no LOG, não só no objeto: o `render()` mostra
    detalhe apenas de quem reprova, então uma quebra autorizada guardada só no
    detalhe seria invisível para quem lê o run — quebra silenciosa com carimbo.
    """
    raiz = _repo(tmp_path)
    _commitar(
        raiz, "openapi: 3.1.0\npaths:\n  /a:\n    get:\n      responses:\n        '200': {}\n"
    )
    monkeypatch.setenv("BASE_REF", "HEAD~1")
    monkeypatch.setenv("PR_LABELS", f"contrato,{ca.ETIQUETA_DE_QUEBRA}")
    relatorio = ca.rodar(raiz)
    impresso = capsys.readouterr().out
    assert relatorio.estado is Estado.PASS, relatorio.render()
    assert "404" in impresso, "a quebra autorizada tem de continuar visível no log"


def test_contrato_novo_e_adicao_pura(tmp_path: Path, monkeypatch):
    raiz = _repo(tmp_path)
    (raiz / "contracts" / "y.openapi.yaml").write_text(
        "openapi: 3.1.0\npaths:\n  /b:\n    get:\n      responses:\n        '200': {}\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=str(raiz), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-qm", "novo"], cwd=str(raiz), check=True, capture_output=True
    )
    monkeypatch.setenv("BASE_REF", "HEAD~1")
    monkeypatch.delenv("PR_LABELS", raising=False)
    relatorio = ca.rodar(raiz)
    assert relatorio.estado is Estado.PASS, relatorio.render()


def test_arquivo_de_contrato_apagado_inteiro_trava(tmp_path: Path, monkeypatch):
    raiz = _repo(tmp_path)
    (raiz / "contracts" / "x.openapi.yaml").unlink()
    subprocess.run(["git", "add", "-A"], cwd=str(raiz), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-qm", "apagou"], cwd=str(raiz), check=True, capture_output=True
    )
    monkeypatch.setenv("BASE_REF", "HEAD~1")
    monkeypatch.delenv("PR_LABELS", raising=False)
    relatorio = ca.rodar(raiz)
    assert relatorio.estado is Estado.FAIL, relatorio.render()
    assert "INTEIRO" in relatorio.render()


def test_pr_que_nao_toca_contratos_e_SKIP(tmp_path: Path, monkeypatch):
    raiz = _repo(tmp_path)
    (raiz / "leia.md").write_text("nada de contrato", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=str(raiz), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-qm", "outro"], cwd=str(raiz), check=True, capture_output=True
    )
    monkeypatch.setenv("BASE_REF", "HEAD~1")
    relatorio = ca.rodar(raiz)
    assert relatorio.estado is Estado.SKIP, relatorio.render()


# --------------------------------------------------------------------------
# CONTRATOS DE EVENTO (29/08/2026)
#
# Até esta data o portão pegava `contracts/eventos/*.json` no diff — são `.json`
# dentro de `contracts/` — e ERRAVA com *"não tem forma de OpenAPI"*.
# Fail-closed, o que está certo; mas o efeito prático era que **editar um evento
# existente era impossível**. Ninguém tinha notado porque todo evento novo, até
# então, nasceu como arquivo NOVO (`*.v2.json`), que é adição pura e nem chega à
# comparação. A lei "acrescentar é livre" só valia para OpenAPI, por acidente —
# e o dia em que ela precisou valer para um evento foi o dia em que o buraco
# apareceu.
#
# O que se mede aqui é a mesma propriedade dos testes de cima, no vocabulário
# de JSON Schema: acrescentar passa, tirar trava.
# --------------------------------------------------------------------------


def _evento(propriedades=None, exigidos=None, extra=None):
    doc = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "carta.v1",
        "type": "object",
        "properties": propriedades if propriedades is not None else {"event": {}},
    }
    if exigidos is not None:
        doc["required"] = exigidos
    if extra:
        doc.update(extra)
    return doc


def test_evento_e_reconhecido_pelo_caminho_e_nao_pelo_conteudo():
    """Farejar o conteúdo acertaria hoje e erraria no primeiro documento de
    forma inesperada — e "não sei que forma é esta" tem de virar ERROR."""
    assert ca.e_evento("contracts/eventos/carta.v1.json")
    assert ca.e_evento("contracts\\eventos\\carta.v1.json")
    assert not ca.e_evento("contracts/identidade.openapi.yaml")


def test_evento_sem_forma_conhecida_e_ERROR_e_nunca_PASS():
    """O falso-verde que este portão inteiro existe para não cometer."""
    with pytest.raises(ErroDeInstrumentacao):
        ca._doc("titulo: sem properties\n", "e.json", evento=True)


def test_assunto_novo_no_enum_do_evento_PASSA():
    """O caso real que descobriu o buraco: `matricula.situacao-alterada`
    entrando no enum de `assunto` de `notificacao.devida.v1`."""
    antes = _evento({"assunto": {"enum": ["sugestao.status-alterado"]}})
    depois = _evento(
        {"assunto": {"enum": ["sugestao.status-alterado", "matricula.situacao-alterada"]}}
    )
    assert ca.quebras_de_evento(antes, depois, "e.json") == []


def test_propriedade_nova_e_opcional_no_evento_PASSA():
    antes = _evento({"data": {"properties": {"a": {}}, "required": ["a"]}})
    depois = _evento({"data": {"properties": {"a": {}, "b": {}}, "required": ["a"]}})
    assert ca.quebras_de_evento(antes, depois, "e.json") == []


def test_ramo_condicional_novo_no_evento_PASSA():
    """Assunto novo ganha um `if/then` próprio — é o desenho que a carta
    prometia, e ele não pode ser lido como quebra."""
    antes = _evento(extra={"allOf": [{"if": {}, "then": {}}]})
    depois = _evento(extra={"allOf": [{"if": {}, "then": {}}, {"if": {}, "then": {}}]})
    assert ca.quebras_de_evento(antes, depois, "e.json") == []


def test_propriedade_removida_do_evento_TRAVA():
    antes = _evento({"data": {"properties": {"a": {}, "b": {}}}})
    depois = _evento({"data": {"properties": {"a": {}}}})
    achados = ca.quebras_de_evento(antes, depois, "e.json")
    assert any("data.b" in a and "REMOVIDO" in a for a in achados), achados


def test_valor_de_enum_removido_do_evento_TRAVA():
    """A quebra mais cara das três: ela só aparece em produção, na primeira
    carta do tipo antigo que o publicador ainda emite."""
    antes = _evento({"assunto": {"enum": ["a", "b"]}})
    depois = _evento({"assunto": {"enum": ["a"]}})
    achados = ca.quebras_de_evento(antes, depois, "e.json")
    assert any("`b`" in a for a in achados), achados


def test_const_trocado_no_evento_TRAVA():
    """`const: x` é `enum: [x]` escrito curto. Trocar o `const` de `event` é a
    quebra mais total que uma carta pode sofrer."""
    antes = _evento({"event": {"const": "notificacao.devida"}})
    depois = _evento({"event": {"const": "notificacao.necessaria"}})
    achados = ca.quebras_de_evento(antes, depois, "e.json")
    assert any("notificacao.devida" in a for a in achados), achados


def test_campo_que_VIRA_obrigatorio_no_evento_TRAVA():
    """Quebra quem PUBLICA sem aquele campo — o caso que passa despercebido
    porque soa a "só acrescentei"."""
    antes = _evento({"data": {"properties": {"a": {}, "b": {}}}, "b": {}}, exigidos=["data"])
    depois = _evento(
        {"data": {"properties": {"a": {}, "b": {}}}, "b": {}}, exigidos=["data", "b"]
    )
    achados = ca.quebras_de_evento(antes, depois, "e.json")
    assert any("b" in a and "OBRIGATÓRIO" in a for a in achados), achados


def test_quebra_dentro_de_um_ramo_then_TRAVA():
    """Os ramos condicionais entram na varredura como qualquer outro pedaço —
    é lá que moram os parâmetros de cada assunto."""
    ramo = lambda props: {  # noqa: E731
        "allOf": [{"if": {}, "then": {"properties": {"data": {"properties": props}}}}]
    }
    antes = _evento(extra=ramo({"x": {}, "y": {}}))
    depois = _evento(extra=ramo({"x": {}}))
    achados = ca.quebras_de_evento(antes, depois, "e.json")
    assert any(".y" in a and "REMOVIDO" in a for a in achados), achados


def test_evento_editado_no_repo_passa_pelo_portao_de_ponta_a_ponta(
    tmp_path: Path, monkeypatch
):
    """A prova de que o caminho INTEIRO funciona — e não só o comparador.

    Antes de 29/08/2026 este cenário terminava em ERROR, e era o bloqueio real:
    o portão nem chegava a comparar.
    """
    raiz = _repo(tmp_path)
    eventos = raiz / "contracts" / "eventos"
    eventos.mkdir()
    carta = eventos / "carta.v1.json"
    carta.write_text(
        '{"$schema": "x", "type": "object", "properties": '
        '{"assunto": {"enum": ["um"]}}}',
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=str(raiz), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-qm", "carta"], cwd=str(raiz), check=True, capture_output=True
    )
    carta.write_text(
        '{"$schema": "x", "type": "object", "properties": '
        '{"assunto": {"enum": ["um", "dois"]}}}',
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=str(raiz), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-qm", "assunto novo"],
        cwd=str(raiz),
        check=True,
        capture_output=True,
    )
    monkeypatch.setenv("BASE_REF", "HEAD~1")
    monkeypatch.delenv("PR_LABELS", raising=False)

    relatorio = ca.rodar(raiz)

    assert relatorio.estado is Estado.PASS, relatorio.render()


def test_o_portao_esta_na_muralha():
    fonte = (RAIZ / "ci" / "ci.py").read_text(encoding="utf-8")
    assert "ci/contrato-aditivo.sh" in fonte
