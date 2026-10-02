"""O que mudou desde a semana passada (degrau 6 do plano do painel de gestão).

O que estes guardas protegem:

1. **A foto é do que a tela mostra**: `valores_atuais` lê a montagem do
   placar, só o que foi medido, e a linha `nome=valor; ...` sai ordenada.
2. **A linha da foto tem forma fixa** (decimal e sinal passam), e torta não
   vira número.
3. **A comparação é com a foto ANTERIOR a hoje**, a mais recente.
4. **Ruído não é movimento; a direção quem pinta é o cartão; foto velha é
   dita; número mensal não compara entre meses.**
5. **Sem foto se diz "sem foto"**, com o caminho para tirar a primeira; sem
   livro, "não medi".
6. **Os campos novos do cartão** (`frescor_maximo`, `dimensoes`, `ruido`)
   passam quando certos e reprovam quando tortos.
"""

from __future__ import annotations

import datetime as dt

import pytest

from apps.core import mudancas

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
    }


def test_a_foto_e_do_que_a_tela_mostra_e_sai_ordenada():
    atuais = mudancas.valores_atuais(_contexto())
    assert atuais == {
        "alunos-na-plataforma": 12,
        "compras-no-ciclo": 7,
        "compras-no-mes": 3,
        "liberacoes-em-48h": 100,
        "pedidos-de-entrada-por-semana": 4,
    }, "cartão sem fonte fica de fora"
    linha = mudancas.foto_em_texto(atuais)
    assert linha == (
        "alunos-na-plataforma=12; compras-no-ciclo=7; compras-no-mes=3; "
        "liberacoes-em-48h=100; pedidos-de-entrada-por-semana=4"
    )
    assert mudancas.ler_foto(linha) == atuais, "a linha volta ao dicionário sem perda"


def test_a_linha_da_foto_guarda_decimal_e_sinal():
    atuais = {"crescimento-mes-a-mes": -12, "margem-mensal": 1234.5}
    linha = mudancas.foto_em_texto(atuais)
    assert linha == "crescimento-mes-a-mes=-12; margem-mensal=1234.5"
    assert mudancas.ler_foto(linha) == atuais


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
        "restricao-da-semana": _cartao("restricao-da-semana", direcao="descer"),
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
            "restricao-da-semana": 1,
            "liberacoes-em-48h": 100,
            "compras-no-mes": 9,
            "aprendizados-validados-no-ciclo": 1,
        },
    }
    atuais = {
        "compras-no-ciclo": 7,  # +1 = ruído, parado
        "restricao-da-semana": 3,  # subiu com direção descer: piorou
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
        "restricao-da-semana",
        "liberacoes-em-48h",
        "aprendizados-validados-no-ciclo",
    }
    assert por_nome["restricao-da-semana"]["sentido"] == "piorou"
    assert (
        por_nome["restricao-da-semana"]["foto_velha"] is True
    ), "21 dias > frescor padrão de 10"
    assert por_nome["liberacoes-em-48h"]["sentido"] == "piorou"
    assert por_nome["liberacoes-em-48h"]["foto_velha"] is True
    assert por_nome["liberacoes-em-48h"]["acao"] == "abra a fila"
    assert por_nome["aprendizados-validados-no-ciclo"]["sentido"] == "mudou"
    assert por_nome["aprendizados-validados-no-ciclo"]["acao"] is None


def test_o_movimento_vem_com_sinal_e_com_modulo():
    """A tela diz "3 a mais" e "14 a menos", nunca "+3" nem "-14".

    `delta` guarda o sinal (quem calcula precisa dele); `variacao` guarda o
    tamanho, que é o que a frase em português usa. Sem os dois, o template
    teria de fazer conta, e template não faz conta nesta casa.
    """
    cartoes = {"x": _cartao("x"), "y": _cartao("y", direcao="descer")}
    foto = {
        "quando": HOJE - dt.timedelta(days=7),
        "arquivo": "f",
        "valores": {"x": 5, "y": 3},
    }
    r = mudancas.comparar({"x": 7, "y": 1.5}, foto, cartoes, HOJE)
    por_nome = {m["nome"]: m for m in r["movidos"]}
    assert por_nome["x"]["delta"] == 2 and por_nome["x"]["variacao"] == 2
    assert por_nome["y"]["delta"] == -1.5 and por_nome["y"]["variacao"] == 1.5
    assert por_nome["y"]["sentido"] == "melhorou", "descer e caiu"


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
    assert r["veredito"] == "sem-foto" and r["quantos_atuais"] == 5
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
    assert r["sem_par"] == 3
