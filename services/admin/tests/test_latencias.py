"""As três latências da gestão (degrau 5 do plano do painel de gestão).

O que estes guardas protegem:

1. **Sinal → decisão** conta do livro: pedido com `precisa_do_dono` até o
   primeiro registro que responde; os abertos contam à parte, com a idade.
2. **Decisão → execução** conta da fila: `criada_em` até o primeiro
   `reivindicada`; parada é a que ninguém pegou em 7 dias, fora bloqueadas e
   terminadas.
3. **Experimento → aprendizado** conta do livro: medição que responde a um
   experimento até o registro que responde à medição; sem experimento
   fechado é dito, nunca zero dias.
4. **"Não medi" se declara** quando o livro ou a fila não vieram.
5. **Os três cartões existem, são de confiança e estão no andar 0**; a capa
   mostra os três, e o livro e a fila reais são lidos por inteiro.
"""

from __future__ import annotations

import datetime as dt
import json

from apps.core import direcao, latencias, placar

HOJE = dt.date(2026, 9, 21)


def _reg(arquivo, tipo="nota", quando="2026-09-10", responde_a=None, precisa=False):
    return {
        "arquivo": arquivo,
        "tipo": tipo,
        "quando": quando,
        "titulo": arquivo,
        "responde_a": responde_a,
        "vence_em_dias": None,
        "precisa_do_dono": precisa,
    }


def test_sinal_para_decisao_mede_os_respondidos_e_conta_os_abertos():
    registros = [
        _reg("p1", "pendencia", "2026-09-01", precisa=True),
        _reg("r1", "resposta", "2026-09-04", responde_a="p1"),
        _reg(
            "r1b", "nota", "2026-09-06", responde_a="p1"
        ),  # a segunda resposta não conta
        _reg("p2", "pendencia", "2026-09-10", precisa=True),
        _reg("r2", "decisao", "2026-09-11", responde_a="p2"),
        _reg("p3", "pendencia", "2026-09-05", precisa=True),  # aberto há 16 dias
        _reg("n1", "nota", "2026-09-12"),
    ]
    r = latencias.latencia_de_decisao(registros, HOJE)
    assert r["veredito"] == "medido"
    assert r["mediana_dias"] == 2 and r["respondidos_28"] == 2  # 3 e 1 dias
    assert r["abertos"] == 1 and r["mais_velho_dias"] == 16


def test_sem_pedido_nenhum_e_sem_dados_ainda_e_sem_livro_e_nao_medi():
    assert (
        latencias.latencia_de_decisao([_reg("n1")], HOJE)["veredito"]
        == "sem-dados-ainda"
    )
    assert latencias.latencia_de_decisao(None, HOJE)["veredito"] == "nao-consigo-medir"


def _fila(tmp_path, tarefas, eventos):
    (tmp_path / "tarefas").mkdir()
    (tmp_path / "eventos").mkdir()
    for i, (id_, criada) in enumerate(tarefas):
        (tmp_path / "tarefas" / f"{i}.json").write_text(
            json.dumps({"id": id_, "criada_em": criada}), encoding="utf-8"
        )
    for i, (id_, evento, quando) in enumerate(eventos):
        (tmp_path / "eventos" / f"{i}.json").write_text(
            json.dumps({"tarefa": id_, "evento": evento, "quando": quando}),
            encoding="utf-8",
        )
    return tmp_path


def test_decisao_para_execucao_mede_da_fila(tmp_path):
    pasta = _fila(
        tmp_path,
        [
            ("TAR-1", "2026-09-01"),
            ("TAR-2", "2026-09-10"),
            ("TAR-3", "2026-09-05"),
            ("TAR-4", "2026-09-02"),
            ("TAR-5", "2026-09-20"),
        ],
        [
            ("TAR-1", "reivindicada", "2026-09-03T12:00:00+00:00"),
            (
                "TAR-1",
                "reivindicada",
                "2026-09-08T12:00:00+00:00",
            ),  # a segunda não conta
            (
                "TAR-2",
                "reivindicada",
                "2026-09-11T02:00:00Z",
            ),  # 23h de 10/09 em SP: 0 dias
            ("TAR-4", "bloqueada", "2026-09-02T13:00:00+00:00"),
        ],
    )
    fila = latencias.ler_a_fila(pasta)
    r = latencias.latencia_de_execucao(fila, HOJE)
    assert r["veredito"] == "medido"
    assert r["pegas_28"] == 2 and r["mediana_dias"] == 1  # 2 e 0 dias
    assert (
        r["paradas"] == 1
    ), "TAR-3 parada há 16 dias; TAR-4 bloqueada e TAR-5 nova não contam"


def test_fila_ausente_e_nao_medi(tmp_path):
    assert (
        latencias.ler_a_fila(tmp_path) is not None
    ), "pasta sem tarefas/ e eventos/ ainda é lida vazia"
    assert latencias.latencia_de_execucao(None, HOJE)["veredito"] == "nao-consigo-medir"


def test_experimento_para_aprendizado():
    registros = [
        _reg("exp", "nota", "2026-09-01"),
        _reg("med", "medicao", "2026-09-10", responde_a="exp"),
        _reg("apr", "decisao", "2026-09-13", responde_a="med"),
        _reg("med2", "medicao", "2026-09-15", responde_a="exp"),
    ]
    r = latencias.latencia_de_aprendizado(registros, HOJE)
    assert r["veredito"] == "medido"
    assert r["mediana_dias"] == 3 and r["com_aprendizado_28"] == 1
    assert r["sem_aprendizado"] == 1
    assert (
        latencias.latencia_de_aprendizado([_reg("n1")], HOJE)["veredito"]
        == "sem-dados-ainda"
    )
    assert (
        latencias.latencia_de_aprendizado(None, HOJE)["veredito"] == "nao-consigo-medir"
    )


def test_os_tres_cartoes_existem_e_sao_de_confianca():
    for nome in (
        "latencia-de-decisao",
        "latencia-de-execucao",
        "latencia-de-aprendizado",
    ):
        cartao, problemas = placar.ler_cartao(nome)
        assert cartao is not None, problemas
        assert cartao["tipo"] == "confianca" and cartao["andar"] == 0
        assert cartao["fonte"]


def test_o_livro_e_a_fila_reais_sao_lidos_por_inteiro():
    registros = direcao.ler_registros()
    assert registros is not None
    assert (
        sum(1 for r in registros if r["precisa_do_dono"]) > 30
    ), "o leitor lê o booleano"
    fila = latencias.ler_a_fila()
    assert (
        fila is not None
        and len(fila["tarefas"]) > 50
        and len(fila["reivindicadas"]) > 20
    )
    r = latencias.medir_as_latencias(registros, fila, dt.date(2026, 9, 4))
    assert r["decisao"]["veredito"] == "medido"
    assert r["execucao"]["veredito"] == "medido"
