"""Provas de medição sem transformar ausência em custo zero."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import medir_coordenacao as medidor
from _nucleo import ErroDeInstrumentacao


def test_erro_de_instrumento_nao_vira_amostra_zero():
    def quebrado():
        raise ErroDeInstrumentacao("servidor indisponível")

    resultado = medidor.medir_chamada("consulta", quebrado)
    assert resultado["estado"] == "ERROR"
    assert "resultado" not in resultado
    assert resultado["acao"]


def test_resumo_separa_falhas_e_nao_inventa_cauda():
    # guarda: ci/medir_coordenacao.py:52
    resumo = medidor.resumir(
        [
            {"estado": "PASS", "parede_s": 2},
            {"estado": "ERROR", "parede_s": 100},
            {"estado": "PASS", "parede_s": 4},
        ]
    )
    assert resumo == {
        "amostras_validas": 2,
        "erros": 1,
        "valores_s": [2, 4],
        "p50_s": 3.0,
        "p90_s": None,
    }
    assert medidor.resumir([])["p50_s"] is None


def test_pr_administrativo_exige_todos_os_caminhos_e_nao_confunde_espera():
    dados = {
        "data": {
            "repository": {
                "pullRequests": {
                    "nodes": [
                        {
                            "number": 1,
                            "createdAt": "2026-09-29T10:00:00Z",
                            "mergedAt": "2026-09-29T10:03:00Z",
                            "files": {
                                "totalCount": 1,
                                "nodes": [{"path": "fila/eventos/1.json"}],
                                "pageInfo": {"hasNextPage": False},
                            },
                        },
                        {
                            "number": 2,
                            "createdAt": "2026-09-29T10:00:00Z",
                            "mergedAt": "2026-09-29T10:02:00Z",
                            "files": {
                                "totalCount": 2,
                                "nodes": [
                                    {"path": "fila/eventos/2.json"},
                                    {"path": "ci/alguma.py"},
                                ],
                                "pageInfo": {"hasNextPage": False},
                            },
                        },
                        {
                            "number": 3,
                            "createdAt": "2026-09-29T10:00:00Z",
                            "mergedAt": "2026-09-29T10:01:00Z",
                            "files": {
                                "totalCount": 101,
                                "nodes": [{"path": "fila/eventos/3.json"}],
                                "pageInfo": {"hasNextPage": True},
                            },
                        },
                    ]
                }
            }
        }
    }
    resumo = medidor.resumir_prs(dados)
    assert resumo["administrativos"] == 1
    assert resumo["descartados_incompletos"] == [3]
    assert resumo["prs"][0]["abertura_ate_merge_s"] == 180
    assert "espera_executor_s" not in resumo["prs"][0]


@pytest.mark.parametrize(
    "dados", [{}, {"data": None}, {"errors": [{"message": "negado"}]}]
)
def test_graphql_invalido_nao_vira_zero_prs(dados):
    with pytest.raises(ErroDeInstrumentacao):
        medidor.resumir_prs(dados)


def test_limpeza_exige_dono_e_sha(monkeypatch, tmp_path):
    monkeypatch.setattr(
        medidor.reservar,
        "ler_reserva",
        lambda raiz, chave: ("a" * 40, {"dono": "outro"}),
    )
    monkeypatch.setattr(
        medidor.reservar, "soltar", lambda *a, **k: pytest.fail("soltou reserva alheia")
    )
    with pytest.raises(ErroDeInstrumentacao):
        medidor.limpar_ensaio(tmp_path, "pme05-ensaio-teste", "meu")


def test_cli_exibe_error_e_instrucao(monkeypatch, capsys):
    monkeypatch.setattr(
        medidor,
        "medir",
        lambda *a, **k: {"estado": "ERROR", "acao": "Confira o servidor e repita."},
    )
    assert medidor.main([]) == 2
    assert json.loads(capsys.readouterr().out)["estado"] == "ERROR"


def test_ensaio_limpa_somente_a_versao_conferida(monkeypatch, tmp_path):
    monkeypatch.setattr(
        medidor.reservar, "ler_reserva", lambda raiz, chave: ("a" * 40, {"dono": "meu"})
    )
    chamadas = []

    def soltar(raiz, chave, **opcoes):
        chamadas.append(opcoes)
        return True

    monkeypatch.setattr(medidor.reservar, "soltar", soltar)
    assert (
        medidor.limpar_ensaio(tmp_path, "pme05-ensaio-teste", "meu")["estado"] == "PASS"
    )
    assert chamadas == [{"esperado": "a" * 40, "dono": "meu"}]


def test_limpeza_inconclusiva_impede_ensaio_pass(monkeypatch, tmp_path):
    resultados = iter([True, False])
    monkeypatch.setattr(medidor.reservar, "identidade_da_bancada", lambda _: "meu")
    monkeypatch.setattr(
        medidor.reservar, "reservar_intencao", lambda *a: (next(resultados), "recado")
    )
    monkeypatch.setattr(medidor.reservar, "confirmar_intencao", lambda *a: True)

    def falha(*args):
        raise ErroDeInstrumentacao("SHA mudou")

    monkeypatch.setattr(medidor, "limpar_ensaio", falha)
    resultado = medidor.ensaiar_reservas(tmp_path)
    assert resultado["estado"] == "ERROR"
    assert resultado["limpeza"]["estado"] == "ERROR"


def test_amostra_vazia_de_prs_e_explicita():
    dados = {"data": {"repository": {"pullRequests": {"nodes": []}}}}
    resultado = medidor.resumir_prs(dados)
    assert resultado["amostra_completa"] == 0
    assert resultado["administrativos"] == 0
