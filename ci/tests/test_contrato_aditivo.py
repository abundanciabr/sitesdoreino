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


def test_o_portao_esta_na_muralha():
    fonte = (RAIZ / "ci" / "ci.py").read_text(encoding="utf-8")
    assert "ci/contrato-aditivo.sh" in fonte
