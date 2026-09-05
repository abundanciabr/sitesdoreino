"""A tela da confiança (degrau 11 do plano do painel de gestão, §6.6).

O que cada grupo de guardas protege, e por que ele existe:

1. **"Não perguntei" nunca vira "não há nada".** É a razão de o degrau existir.
   Uma tela de qualidade de dados que mostrasse "0 assuntos parados" e "nenhum
   evento quebrado" quando a medição está fora do ar seria pior que tela
   nenhuma: ela diria, com ar de precisão, que está tudo limpo. Os guardas do
   grupo 1 exigem a frase da ausência e PROÍBEM a frase do "tudo certo" na
   mesma resposta.
2. **A decisão dos cinco desfechos é uma só.** `medicao.a_cobertura` é a única
   função que a toma; a linha do placar e esta tela leem dela. O guarda compara
   os dois vereditos na mesma resposta da rede.
3. **Frescor é medido, nunca decorado.** O prazo sai do `frescor_maximo` do
   cartão e a idade sai da última foto do livro. Cartão que nunca foi anotado
   não é "velho" (é "nunca anotado"), e cartão sem fonte não é nem uma coisa
   nem outra.
4. **Todo bloco termina num gesto** (régua 5 do §2 do plano). Os três gestos
   desta tela são links para telas que já existem, e o guarda exige os três.
5. **O corpo cru só sai por inspeção deliberada.** A lista de quebrados não o
   traz (o contrato o esconde em lote de propósito); a página de um evento
   traz. Id que não existe é dito, e não uma página vazia que parece resposta.
"""

from __future__ import annotations

import datetime as dt
import json

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.core import confianca as conf
from apps.core.clients import MedicaoClient

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
CATALOGO = "http://catalogo:8000/api/catalogo"
ALUNOS = "http://alunos:8000/api/alunos"
METRICAS = "http://metricas:8000/api/metricas"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"
SITE_ID = "site-mesh"

HOJE = dt.date(2026, 9, 5)
AGORA = dt.datetime(2026, 9, 5, 15, 0, tzinfo=dt.timezone.utc)


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    monkeypatch.setenv("CATALOGO_API_URL", CATALOGO)
    monkeypatch.setenv("TOKEN_CATALOGO", "token-do-par-admin-catalogo")
    monkeypatch.setenv("ALUNOS_API_URL", ALUNOS)
    monkeypatch.setenv("ALUNOS_API_TOKEN", "token-do-par-admin-alunos")
    monkeypatch.setenv("METRICAS_API_URL", METRICAS)
    monkeypatch.setenv("METRICAS_API_TOKEN", "token-do-par-admin-metricas")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"
    monkeypatch.setattr(conf.timezone, "localdate", lambda: HOJE)
    monkeypatch.setattr(conf.timezone, "now", lambda: AGORA)


def _dentro() -> Client:
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "id-opaco-123",
                "nome_exibido": "Fulano",
                "papel": None,
                "email": DONO,
            },
        )
    )
    respx.get(f"{CATALOGO}/sites/by-host/testserver").mock(
        return_value=httpx.Response(200, json={"id": SITE_ID, "host": "testserver"})
    )
    c = Client()
    c.defaults["HTTP_COOKIE"] = COOKIE
    return c


def _tipo(nome, quantidade=1, dias=0, recebido="2026-09-05T14:58:00+00:00"):
    return {
        "tipo": nome,
        "celula": nome.split(".")[0],
        "quantidade": quantidade,
        "ultimo_ocorrido_em": recebido,
        "ultimo_recebido_em": recebido,
        "dias_desde_o_ultimo": dias,
    }


def _a_cobertura_responde(tipos):
    respx.get(f"{METRICAS}/cobertura").mock(
        return_value=httpx.Response(
            200,
            json={
                "site_id": SITE_ID,
                "medido_em": "2026-09-05T15:00:00+00:00",
                "tipos": tipos,
            },
        )
    )


def _morto(identificador=7, motivo="envelope sem `site_id`"):
    return {
        "id": identificador,
        "recebido_em": "2026-09-04T10:00:00+00:00",
        "estado": "novo",
        "motivo": motivo,
        "tipo_declarado": "quiz.completado",
        "event_id_declarado": "ev-123",
    }


def _a_fila_responde(itens, total=None):
    respx.get(f"{METRICAS}/eventos-mortos").mock(
        return_value=httpx.Response(
            200,
            json={
                "total": len(itens) if total is None else total,
                "itens": itens,
                "proximo_cursor": None,
            },
        )
    )


# ---------------------------------------------------------------------------
# 1. "Não perguntei" nunca vira "não há nada" — a razão do degrau
# ---------------------------------------------------------------------------


@respx.mock
def test_medicao_fora_do_ar_diz_que_nao_perguntou_e_nao_que_esta_tudo_limpo():
    cliente = _dentro()
    respx.get(f"{METRICAS}/cobertura").mock(side_effect=httpx.ConnectError("recusou"))
    respx.get(f"{METRICAS}/eventos-mortos").mock(
        side_effect=httpx.ConnectError("recusou")
    )

    resposta = cliente.get(reverse("confianca"))
    corpo = resposta.content.decode()

    assert resposta.status_code == 200, "a tela da confiança é fail-open, como o placar"
    assert "Não consegui perguntar à memória agora." in corpo
    assert "Não consegui ver a fila do que chegou quebrado." in corpo
    assert "Tudo que a plataforma conta continua chegando." not in corpo, (
        "a tela afirmou que está tudo em dia sem ter conseguido perguntar: "
        "é exatamente o falso-verde que este degrau existe para impedir"
    )
    assert (
        "Nada chegou quebrado." not in corpo
    ), "a tela afirmou que nada quebrou sem ter visto a fila"


@respx.mock
def test_o_par_nao_provisionado_diz_que_falta_a_senha_em_vez_de_zero(monkeypatch):
    """Sem o par na VPS a tela abre, e diz o que falta em vez de mostrar zero."""
    cliente = _dentro()
    monkeypatch.delenv("METRICAS_API_TOKEN")

    corpo = cliente.get(reverse("confianca")).content.decode()

    assert "ainda não tem a senha para perguntar a ela" in corpo
    assert "ainda não tem a senha para ver a fila" in corpo
    assert "Tudo que a plataforma conta continua chegando." not in corpo
    assert "Nada chegou quebrado." not in corpo


@respx.mock
def test_memoria_ligada_e_vazia_e_diferente_de_memoria_muda():
    cliente = _dentro()
    _a_cobertura_responde([])
    _a_fila_responde([])

    corpo = cliente.get(reverse("confianca")).content.decode()

    assert "ainda não guardou nenhum fato" in corpo
    assert "Não consegui perguntar à memória agora." not in corpo


# ---------------------------------------------------------------------------
# 2. A decisão dos cinco desfechos é UMA só
# ---------------------------------------------------------------------------


@respx.mock
def test_a_tela_e_o_placar_leem_o_mesmo_veredito():
    """Duas cópias da decisão divergiriam no primeiro desfecho novo."""
    from apps.core import medicao

    class ClienteMudo:
        def cobertura(self, site_id):
            return MedicaoClient.NAO_RESPONDEU, None

        def quebrados(self):
            return MedicaoClient.NAO_RESPONDEU, None

    mudo = ClienteMudo()

    assert medicao.a_cobertura(SITE_ID, AGORA, mudo)["veredito"] == "nao-respondeu"
    assert medicao.a_memoria(SITE_ID, AGORA, mudo)["veredito"] == "nao-respondeu"


# ---------------------------------------------------------------------------
# 3. Cobertura: o que parou de chegar aparece com nome e com quantos dias
# ---------------------------------------------------------------------------


@respx.mock
def test_o_assunto_calado_aparece_com_o_nome_e_os_dias():
    cliente = _dentro()
    _a_cobertura_responde(
        [
            _tipo("identidade.pessoa-cadastrada", 12, dias=0),
            _tipo("forum.topico-criado", 4, dias=19),
        ]
    )
    _a_fila_responde([])

    corpo = cliente.get(reverse("confianca")).content.decode()

    assert "pergunta no fórum" in corpo
    assert "19 dias" in corpo
    assert "gente se cadastrando" in corpo


@respx.mock
def test_assunto_sem_traducao_aparece_com_o_nome_cru_em_vez_de_sumir():
    cliente = _dentro()
    _a_cobertura_responde([_tipo("celula-nova.coisa-nova", 3, dias=40)])
    _a_fila_responde([])

    corpo = cliente.get(reverse("confianca")).content.decode()

    assert "celula-nova.coisa-nova" in corpo


@respx.mock
def test_a_tela_diz_que_assunto_que_nunca_chegou_nao_aparece_aqui():
    """O contrato da medição não conhece a lista do que DEVERIA chegar.

    Calar sobre esse limite faria a tela parecer uma auditoria completa quando
    ela é a lista do que já chegou alguma vez.
    """
    cliente = _dentro()
    _a_cobertura_responde([_tipo("quiz.completado", 9, dias=1)])
    _a_fila_responde([])

    corpo = cliente.get(reverse("confianca")).content.decode()

    assert "nunca chegou" in corpo


# ---------------------------------------------------------------------------
# 4. Frescor: medido do cartão e da última foto do livro
# ---------------------------------------------------------------------------


def _cartao(pasta, nome, **campos):
    base = {
        "nome": nome,
        "tipo": "resultado",
        "andar": 1,
        "pergunta": f"Pergunta de {nome}?",
        "definicao": "o que conta",
        "formula": "a conta",
        "fonte": "a célula dona",
        "autoridade": "alunos",
        "dono": "mantenedor",
        "frequencia": "diária",
        "par": "outro-cartao",
        "versao": 1,
        "desde": "2026-09-01",
    }
    base.update(campos)
    (pasta / f"{nome}.json").write_text(
        json.dumps(base, ensure_ascii=False), encoding="utf-8"
    )


def _registro_com_foto(quando: str, foto: str) -> dict:
    return {"tipo": "medicao", "quando": quando, "foto": foto, "arquivo": quando}


def test_numero_dentro_do_prazo_e_numero_que_envelheceu(tmp_path):
    _cartao(tmp_path, "no-prazo", frescor_maximo=10)
    _cartao(tmp_path, "envelheceu", frescor_maximo=3)
    registros = [_registro_com_foto("2026-08-30", "envelheceu=4; no-prazo=7")]

    frescor = conf.o_frescor(tmp_path, registros, HOJE)

    por_nome = {linha["nome"]: linha for linha in frescor["linhas"]}
    assert por_nome["no-prazo"]["estado"] == "no-prazo"
    assert por_nome["envelheceu"]["estado"] == "velho"
    assert por_nome["envelheceu"]["idade"] == 6
    assert por_nome["envelheceu"]["atraso"] == 3
    assert frescor["velhos"] == 1
    assert frescor["no_prazo"] == 1


def test_cartao_nunca_anotado_nao_e_chamado_de_velho(tmp_path):
    _cartao(tmp_path, "nunca-anotado", frescor_maximo=2)

    frescor = conf.o_frescor(tmp_path, [], HOJE)

    linha = frescor["linhas"][0]
    assert linha["estado"] == "nunca-anotado"
    assert linha.get("atraso") is None
    assert frescor["velhos"] == 0


def test_cartao_sem_fonte_diz_por_que_e_fica_fora_da_conta(tmp_path):
    _cartao(
        tmp_path,
        "sem-fonte",
        fonte=None,
        sem_fonte_porque="a célula de cursos ainda não nasceu",
    )

    frescor = conf.o_frescor(tmp_path, [], HOJE)

    linha = frescor["linhas"][0]
    assert linha["estado"] == "sem-fonte"
    assert linha["porque"] == "a célula de cursos ainda não nasceu"
    assert frescor["velhos"] == 0 and frescor["nunca_anotados"] == 0


def test_cartao_torto_e_dito_em_vez_de_sumir(tmp_path):
    (tmp_path / "torto.json").write_text('{"nome": "torto"}', encoding="utf-8")

    frescor = conf.o_frescor(tmp_path, [], HOJE)

    linha = frescor["linhas"][0]
    assert linha["estado"] == "cartao-torto"
    assert linha["porque"]


def test_livro_ausente_nao_vira_tudo_velho(tmp_path):
    """`None` é "não consegui olhar o livro", e isso não é uma medição."""
    _cartao(tmp_path, "qualquer", frescor_maximo=1)

    frescor = conf.o_frescor(tmp_path, None, HOJE)

    assert frescor["veredito"] == "sem-livro"
    assert frescor["linhas"] == []


def test_a_foto_mais_recente_de_um_cartao_e_a_que_vale(tmp_path):
    _cartao(tmp_path, "numero", frescor_maximo=5)
    registros = [
        _registro_com_foto("2026-08-01", "numero=1"),
        _registro_com_foto("2026-09-03", "numero=9"),
        _registro_com_foto("2026-08-20", "numero=4"),
    ]

    frescor = conf.o_frescor(tmp_path, registros, HOJE)

    assert frescor["linhas"][0]["idade"] == 2
    assert frescor["linhas"][0]["estado"] == "no-prazo"


# ---------------------------------------------------------------------------
# 5. O que chegou quebrado, e a inspeção de um
# ---------------------------------------------------------------------------


@respx.mock
def test_a_fila_de_quebrados_mostra_o_motivo_de_cada_um_e_nao_o_corpo():
    cliente = _dentro()
    _a_cobertura_responde([_tipo("quiz.completado", 2)])
    _a_fila_responde([_morto(7, "envelope sem `site_id`")])

    corpo = cliente.get(reverse("confianca")).content.decode()

    assert "envelope sem `site_id`" in corpo
    assert reverse("confianca_quebrado", args=[7]) in corpo


@respx.mock
def test_fila_vazia_diz_que_nada_quebrou_porque_ela_respondeu():
    cliente = _dentro()
    _a_cobertura_responde([_tipo("quiz.completado", 2)])
    _a_fila_responde([])

    corpo = cliente.get(reverse("confianca")).content.decode()

    assert "Nada chegou quebrado." in corpo


@respx.mock
def test_inspecionar_um_evento_mostra_o_corpo_cru():
    cliente = _dentro()
    respx.get(f"{METRICAS}/eventos-mortos/7").mock(
        return_value=httpx.Response(
            200, json={**_morto(7), "corpo": '{"assim": "que chegou"}'}
        )
    )

    corpo = cliente.get(reverse("confianca_quebrado", args=[7])).content.decode()

    assert "que chegou" in corpo
    assert "envelope sem `site_id`" in corpo


@respx.mock
def test_evento_que_nao_existe_diz_isso_em_vez_de_pagina_vazia():
    cliente = _dentro()
    respx.get(f"{METRICAS}/eventos-mortos/999").mock(return_value=httpx.Response(404))

    resposta = cliente.get(reverse("confianca_quebrado", args=[999]))

    assert resposta.status_code == 200
    assert "Este evento não existe na fila" in resposta.content.decode()


@respx.mock
def test_medicao_muda_na_inspecao_nao_vira_evento_vazio():
    cliente = _dentro()
    respx.get(f"{METRICAS}/eventos-mortos/7").mock(
        side_effect=httpx.ConnectError("recusou")
    )

    corpo = cliente.get(reverse("confianca_quebrado", args=[7])).content.decode()

    assert "Não consegui perguntar à memória agora." in corpo
    assert "Este evento não existe na fila" not in corpo


# ---------------------------------------------------------------------------
# 6. Todo bloco termina num gesto (régua 5 do §2 do plano)
# ---------------------------------------------------------------------------


@respx.mock
def test_cada_uma_das_tres_perguntas_termina_num_gesto():
    cliente = _dentro()
    _a_cobertura_responde([_tipo("forum.topico-criado", 4, dias=19)])
    _a_fila_responde([_morto(7)])

    corpo = cliente.get(reverse("confianca")).content.decode()

    assert (
        reverse("caixa_robos") in corpo
    ), "o gesto da cobertura: pedir que um robô olhe"
    assert reverse("reuniao") in corpo, "o gesto do frescor: tirar a foto da semana"
    assert reverse("confianca_quebrado", args=[7]) in corpo, "o gesto: inspecionar"


@respx.mock
def test_o_placar_leva_ate_esta_tela():
    cliente = _dentro()
    respx.get(f"{ALUNOS}/pre-matriculas").mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(f"{ALUNOS}/matriculas").mock(return_value=httpx.Response(200, json=[]))
    _a_cobertura_responde([_tipo("quiz.completado", 1)])
    _a_fila_responde([])

    corpo = cliente.get(reverse("placar")).content.decode()

    assert reverse("confianca") in corpo


@respx.mock
def test_quem_a_porta_recusa_nao_ve_a_confianca():
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "id-opaco-999",
                "nome_exibido": "Estranho",
                "papel": None,
                "email": "estranho@exemplo.com",
            },
        )
    )
    c = Client()
    c.defaults["HTTP_COOKIE"] = COOKIE

    assert c.get(reverse("confianca")).status_code == 404
    assert c.get(reverse("confianca_quebrado", args=[7])).status_code == 404
