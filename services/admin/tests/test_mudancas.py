"""O que mudou desde a semana passada (degrau 6 do plano do painel de gestão).

O que estes guardas protegem:

1. **A foto é do que a tela mostra**: `valores_atuais` lê a montagem do
   placar, só o que foi medido, e a linha `nome=valor; ...` sai ordenada.
2. **A linha da foto tem forma fixa**, e torta não vira número.
3. **A comparação é com a foto ANTERIOR a hoje**, a mais recente.
4. **Ruído não é movimento; a direção quem pinta é o cartão; foto velha é
   dita; número mensal não compara entre meses.**
5. **Sem foto se diz "sem foto"**, com o caminho para tirar a primeira; sem
   livro, "não medi".
6. **Os campos novos do cartão** (`frescor_maximo`, `dimensoes`, `ruido`)
   passam quando certos e reprovam quando tortos.
7. **A reunião põe a foto no pedido** quando a caixa está marcada, e só então.
"""

from __future__ import annotations

import datetime as dt

import pytest

from apps.core import mudancas, placar, reuniao

HOJE = dt.date(2026, 9, 21)


def _cartao(nome, direcao="subir", **extra):
    return {
        "nome": nome,
        "pergunta": f"pergunta de {nome}",
        "direcao": direcao,
        **extra,
    }


def _contexto():
    return {
        "contagem": {"ciclo": 7, "total_de_alunos": 12},
        "direcao": {
            "pedidos": {"veredito": "abaixo", "esta_semana": 4},
            "liberacoes": {"veredito": "cumprida", "por_cento": 100},
        },
        "doze": [
            {
                "nome": "compras-no-mes",
                "veredito": "medido",
                "valor": 3,
                "cartao": _cartao("compras-no-mes"),
            },
            {
                "nome": "margem-mensal",
                "veredito": "sem-fonte",
                "valor": None,
                "cartao": _cartao("margem-mensal"),
            },
        ],
        "latencias": {
            "decisao": {"veredito": "medido", "mediana_dias": 1.5},
            "execucao": {"veredito": "sem-dados-ainda"},
            "aprendizado": {"veredito": "medido", "mediana_dias": None},
        },
    }


def test_a_foto_e_do_que_a_tela_mostra_e_sai_ordenada():
    atuais = mudancas.valores_atuais(_contexto())
    assert atuais == {
        "alunos-na-plataforma": 12,
        "compras-no-ciclo": 7,
        "compras-no-mes": 3,
        "latencia-de-decisao": 1.5,
        "liberacoes-em-48h": 100,
        "pedidos-de-entrada-por-semana": 4,
    }, "sem-fonte, sem-dados-ainda e mediana nula ficam de fora"
    linha = mudancas.foto_em_texto(atuais)
    assert linha == (
        "alunos-na-plataforma=12; compras-no-ciclo=7; compras-no-mes=3; "
        "latencia-de-decisao=1.5; liberacoes-em-48h=100; pedidos-de-entrada-por-semana=4"
    )
    assert mudancas.ler_foto(linha) == atuais, "a linha volta ao dicionário sem perda"


@pytest.mark.parametrize(
    "torta",
    ["compras no mês: três", "compras-no-mes=3;liberacoes=1", "Compras=3", "", None, 3],
)
def test_foto_torta_nao_vira_numero(torta):
    assert mudancas.ler_foto(torta) is None


def _reg(arquivo, quando, foto, tipo="medicao"):
    return {"arquivo": arquivo, "tipo": tipo, "quando": quando, "foto": foto}


def test_a_comparacao_e_com_a_foto_anterior_mais_recente():
    registros = [
        _reg("f1", "2026-09-07", "compras-no-mes=1"),
        _reg("f2", "2026-09-14", "compras-no-mes=2"),
        _reg("f3", "2026-09-21", "compras-no-mes=9"),  # a de hoje não serve
        _reg("n1", "2026-09-15", "compras-no-mes=8", tipo="nota"),  # não é foto
        _reg("f4", "2026-09-16", "torta"),  # ilegível, ignorada
    ]
    foto = mudancas.ultima_foto(registros, HOJE)
    assert foto["arquivo"] == "f2" and foto["valores"] == {"compras-no-mes": 2}
    assert mudancas.ultima_foto([], HOJE) is None


def test_ruido_direcao_frescor_e_mes():
    cartoes = {
        "compras-no-ciclo": _cartao("compras-no-ciclo", ruido=1, unidade="pessoas"),
        "latencia-de-decisao": _cartao("latencia-de-decisao", direcao="descer"),
        "liberacoes-em-48h": _cartao(
            "liberacoes-em-48h", frescor_maximo=3, acao="abra a fila"
        ),
        "compras-no-mes": _cartao("compras-no-mes"),
        "aprendizados-validados-no-ciclo": _cartao(
            "aprendizados-validados-no-ciclo", direcao="faixa"
        ),
    }
    foto = {
        "quando": dt.date(2026, 8, 31),  # 21 dias, e mês diferente
        "arquivo": "f",
        "valores": {
            "compras-no-ciclo": 6,
            "latencia-de-decisao": 1,
            "liberacoes-em-48h": 100,
            "compras-no-mes": 9,
            "aprendizados-validados-no-ciclo": 1,
        },
    }
    atuais = {
        "compras-no-ciclo": 7,  # +1 = ruído, parado
        "latencia-de-decisao": 3,  # subiu com direção descer: piorou
        "liberacoes-em-48h": 50,  # caiu com direção subir: piorou, foto velha, com ação
        "compras-no-mes": 2,  # mês diferente: nem entra
        "aprendizados-validados-no-ciclo": 2,  # faixa: mudou
        "alunos-na-plataforma": 12,  # sem par na foto
    }
    r = mudancas.comparar(atuais, foto, cartoes, HOJE)
    assert r["veredito"] == "comparado" and r["idade_dias"] == 21
    assert r["parados"] == 1 and r["sem_par"] == 1
    por_nome = {m["nome"]: m for m in r["movidos"]}
    assert set(por_nome) == {
        "latencia-de-decisao",
        "liberacoes-em-48h",
        "aprendizados-validados-no-ciclo",
    }
    assert por_nome["latencia-de-decisao"]["sentido"] == "piorou"
    assert (
        por_nome["latencia-de-decisao"]["foto_velha"] is True
    ), "21 dias > frescor padrão de 10"
    assert por_nome["liberacoes-em-48h"]["sentido"] == "piorou"
    assert por_nome["liberacoes-em-48h"]["foto_velha"] is True
    assert por_nome["liberacoes-em-48h"]["acao"] == "abra a fila"
    assert por_nome["aprendizados-validados-no-ciclo"]["sentido"] == "mudou"
    assert por_nome["aprendizados-validados-no-ciclo"]["acao"] is None


def test_frescor_padrao_e_dez_dias():
    cartoes = {"x": _cartao("x")}
    foto = {"quando": HOJE - dt.timedelta(days=11), "arquivo": "f", "valores": {"x": 1}}
    r = mudancas.comparar({"x": 2}, foto, cartoes, HOJE)
    assert r["movidos"][0]["foto_velha"] is True
    foto["quando"] = HOJE - dt.timedelta(days=10)
    r = mudancas.comparar({"x": 2}, foto, cartoes, HOJE)
    assert r["movidos"][0]["foto_velha"] is False


def test_sem_foto_e_dito_e_sem_livro_e_nao_medi():
    r = mudancas.o_que_mudou(_contexto(), [], HOJE)
    assert r["veredito"] == "sem-foto" and r["quantos_atuais"] == 6
    assert r["foto_de_hoje"].startswith("alunos-na-plataforma=12; ")
    assert mudancas.o_que_mudou(_contexto(), None, HOJE) == {
        "veredito": "nao-consigo-medir"
    }


def test_a_montagem_inteira_compara_e_pinta_pelo_cartao():
    registros = [
        _reg("f", "2026-09-14", "compras-no-ciclo=5; pedidos-de-entrada-por-semana=6")
    ]
    contexto = {
        **_contexto(),
        "meta": _cartao("compras-no-ciclo"),
        "cartao_pedidos": _cartao("pedidos-de-entrada-por-semana"),
    }
    r = mudancas.o_que_mudou(contexto, registros, HOJE)
    por_nome = {m["nome"]: m for m in r["movidos"]}
    assert por_nome["compras-no-ciclo"]["sentido"] == "melhorou"
    assert por_nome["pedidos-de-entrada-por-semana"]["sentido"] == "piorou"
    assert r["sem_par"] == 4


# ------------------------------------------------------- os campos do cartão


def _cartao_valido(**sobre):
    base = {
        "nome": "x",
        "tipo": "confianca",
        "andar": 1,
        "pergunta": "?",
        "definicao": "d",
        "formula": "f",
        "fonte": "f",
        "autoridade": "alunos",
        "dono": "mantenedor",
        "frequencia": "f",
        "versao": 1,
        "desde": "2026-09-04",
    }
    base.update(sobre)
    return base


def test_os_campos_novos_do_cartao_passam_quando_certos():
    problemas = placar.validar(
        _cartao_valido(frescor_maximo=7, dimensoes=["site", "turma"], ruido=0.5)
    )
    assert not [
        p for p in problemas if "frescor" in p or "dimensoes" in p or "ruido" in p
    ]


@pytest.mark.parametrize(
    "torto, trecho",
    [
        ({"frescor_maximo": 0}, "frescor_maximo"),
        ({"frescor_maximo": "7"}, "frescor_maximo"),
        ({"dimensoes": ["cor"]}, "dimensoes"),
        ({"dimensoes": "site"}, "dimensoes"),
        ({"ruido": -1}, "ruido"),
        ({"ruido": True}, "ruido"),
    ],
)
def test_os_campos_novos_do_cartao_reprovam_quando_tortos(torto, trecho):
    problemas = placar.validar(_cartao_valido(**torto))
    assert any(trecho in p for p in problemas), problemas


# --------------------------------------------------------------- a reunião


def test_a_reuniao_poe_a_foto_no_pedido_so_com_a_caixa_marcada():
    foto = "compras-no-mes=3; liberacoes-em-48h=100"
    texto = reuniao.montar_o_pedido({"tirar_foto": "sim"}, HOJE, foto)
    assert "FOTO DA SEMANA" in texto and f'foto: "{foto}"' in texto
    assert "tipo `medicao`" in texto and "2026-09-21" in texto
    assert reuniao.montar_o_pedido({}, HOJE, foto) is None, "sem a caixa, sem pedido"
    assert (
        reuniao.montar_o_pedido({"tirar_foto": "sim"}, HOJE, None) is None
    ), "sem número com fonte não há o que fotografar"
    com_compromisso = reuniao.montar_o_pedido({"compromisso1": "ligar"}, HOJE, foto)
    assert "FOTO DA SEMANA" not in com_compromisso
