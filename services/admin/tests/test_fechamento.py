"""O fechamento do ciclo, `/admin/placar/fechamento/` (degrau 13 do plano).

O que cada grupo de guardas protege, e por que ele existe:

1. **O ciclo NÃO fecha sem "o que a escola para de fazer".** É a alma do
   degrau: um fechamento que só acrescenta é uma lista que cresce para sempre.
   Sem o campo, `montar_o_pedido` devolve `None`, e não existe pedido nenhum
   para o robô.
2. **A meta seguinte é parte do fechamento.** É o robô que grava o alvo e a
   data no cartão. Alvo em branco, alvo que não é número ou data no passado
   virariam a régua de TODO o painel no dia seguinte.
3. **Ausência de dado nunca vira conclusão** (`armadilhas/271`). Nas semanas de
   aprender a meta semanal é zero: bater zero e ver o ciclo "ganhando" não
   prova que uma coisa previu a outra. A resposta é "ainda não dá para saber",
   e o livro que não chegou não é "nenhum portão provado".
4. **A fase da escola é calculada, nunca digitada**, e declarar um portão não é
   prová-lo: sem `evidencia` e `verificado_em`, ele não conta.
5. **O estado "correndo" é o principal.** A tela nasce sem nenhum ciclo fechado
   e fica assim até 15/12/2026. Ela abre, diz quantas semanas faltam e mostra a
   prévia, em vez de esconder tudo atrás de um "ainda não".
6. **A porta continua sendo a porta.**
"""

from __future__ import annotations

import datetime as dt

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.core import direcao, fechamento

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"
ALUNOS = "http://alunos:8000/api/alunos"
ALUNOS_LISTA = f"{ALUNOS}/matriculas"
HOJE = dt.date(2026, 9, 7)

META = {
    "alvo": 1000,
    "partida": 0,
    "partida_em": "2026-09-03",
    "ate": "2026-12-15",
    "pergunta": "Quantas pessoas viraram alunas desde o começo do ciclo?",
}


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    monkeypatch.setenv("ALUNOS_API_URL", ALUNOS)
    monkeypatch.setenv("ALUNOS_API_TOKEN", "token-do-par-admin-alunos")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


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
    c = Client()
    c.defaults["HTTP_COOKIE"] = COOKIE
    return c


def _registro(arquivo: str, **extra) -> dict:
    base = {
        "arquivo": arquivo,
        "tipo": "medicao",
        "quando": "2026-09-05",
        "titulo": f"Registro {arquivo}",
        "responde_a": None,
        "vence_em_dias": None,
        "precisa_do_dono": False,
        "foto": None,
        "problema": None,
        "hipotese": None,
        "metrica": None,
        "guarda": None,
        "veredito": None,
        "portao": None,
        "evidencia": None,
        "verificado_em": None,
    }
    base.update(extra)
    return base


def _prova(portao: str, arquivo: str = "20260905-001-prova") -> dict:
    return _registro(
        arquivo,
        portao=portao,
        evidencia="https://github.com/abundanciabr/sitesdoreino/pull/999",
        verificado_em="2026-09-05",
    )


def _dados(**sobre) -> dict:
    base = {
        "meta": META,
        "resultado": {
            "veredito": "perdendo",
            "alvo": 1000,
            "x": 4,
            "ate": "2026-12-15",
        },
        "direcao_da_semana": None,
        "registros": [],
        "hoje": HOJE,
    }
    base.update(sobre)
    return fechamento.montar(**base)


CAMPOS_COMPLETOS = {
    "paramos_de_fazer": "parar de vender por mensagem uma a uma",
    "proximo_alvo": "2000",
    "proxima_ate": "2027-03-09",
}


# --------------------- 1. o ciclo não fecha sem a recusa


def test_sem_o_que_paramos_de_fazer_nao_existe_pedido_nenhum():
    campos = {**CAMPOS_COMPLETOS, "paramos_de_fazer": ""}
    pedido, faltando = fechamento.montar_o_pedido(campos, _dados(), HOJE)

    assert (
        pedido is None
    ), "o ciclo fechou sem ninguém dizer o que a escola para de fazer"
    assert [f["campo"] for f in faltando] == ["paramos_de_fazer"]
    assert (
        faltando[0]["lei"] is True
    ), "a recusa é a LEI do degrau, e a tela precisa saber disso"


def test_espaco_em_branco_nao_e_uma_decisao():
    campos = {**CAMPOS_COMPLETOS, "paramos_de_fazer": "   \n  "}
    pedido, faltando = fechamento.montar_o_pedido(campos, _dados(), HOJE)
    assert pedido is None and faltando[0]["campo"] == "paramos_de_fazer"


def test_com_a_recusa_e_a_meta_seguinte_o_pedido_nasce_inteiro():
    pedido, faltando = fechamento.montar_o_pedido(CAMPOS_COMPLETOS, _dados(), HOJE)

    assert faltando == []
    assert pedido is not None
    assert "parar de vender por mensagem uma a uma" in pedido
    assert "tipo `decisao`" in pedido, "a recusa vira registro de decisão no livro"
    assert fechamento.CARTAO_DA_META_NO_REPOSITORIO in pedido
    assert "2027-03-09" in pedido and "2000" in pedido


def test_o_pedido_avisa_quando_o_ciclo_ainda_nao_terminou():
    """Fechar antes do prazo encerra o ciclo cedo, e o robô tem de saber disso.

    Sem este aviso, um ensaio de fechamento produziria um texto idêntico ao de
    um fechamento de verdade, e o robô viraria o cartão três meses antes.
    """
    correndo, _ = fechamento.montar_o_pedido(CAMPOS_COMPLETOS, _dados(), HOJE)
    assert "AINDA NÃO" in correndo

    depois = dt.date(2026, 12, 16)
    terminado, _ = fechamento.montar_o_pedido(
        CAMPOS_COMPLETOS, _dados(hoje=depois), depois
    )
    assert "AINDA NÃO" not in terminado


# ------------------------------ 2. a meta seguinte é parte do fechamento


def test_alvo_que_nao_e_numero_nao_vira_regua_do_painel():
    campos = {**CAMPOS_COMPLETOS, "proximo_alvo": "umas duas mil"}
    pedido, faltando = fechamento.montar_o_pedido(campos, _dados(), HOJE)
    assert pedido is None
    assert [f["campo"] for f in faltando] == ["proximo_alvo"]
    assert faltando[0]["lei"] is False


def test_alvo_zero_ou_negativo_e_recusado():
    for valor in ("0", "-5"):
        pedido, faltando = fechamento.montar_o_pedido(
            {**CAMPOS_COMPLETOS, "proximo_alvo": valor}, _dados(), HOJE
        )
        assert pedido is None, f"alvo {valor} passou"


def test_data_do_proximo_ciclo_no_passado_e_recusada():
    campos = {**CAMPOS_COMPLETOS, "proxima_ate": "2026-01-01"}
    pedido, faltando = fechamento.montar_o_pedido(campos, _dados(), HOJE)
    assert pedido is None
    assert [f["campo"] for f in faltando] == ["proxima_ate"]


def test_data_escrita_errada_e_recusada_com_o_formato_dito():
    campos = {**CAMPOS_COMPLETOS, "proxima_ate": "09/03/2027"}
    pedido, faltando = fechamento.montar_o_pedido(campos, _dados(), HOJE)
    assert pedido is None
    assert (
        "2027-03-09" in faltando[0]["porque"]
    ), "a mensagem tem de mostrar o formato certo"


# ------------------- 3. ausência de dado nunca vira conclusão


def test_meta_semanal_em_zero_nao_vira_as_medidas_previram():
    """As cinco primeiras semanas do ciclo valem 0 de propósito.

    Bater uma meta de zero e ver o ciclo "ganhando" é a tela parabenizando quem
    ainda não foi cobrado de nada (`armadilhas/271`).
    """
    direcao_de_semana_zero = {
        "pedidos": {"veredito": "cumprida", "meta": 0, "esta_semana": 0},
        "liberacoes": {"veredito": "cumprida", "por_cento": 100},
    }
    previsao = fechamento.medidas_previram(
        direcao_de_semana_zero, {"veredito": "ganhando"}
    )
    assert previsao["veredito"] == "ainda-nao-da-para-saber"
    assert "zero" in previsao["porque"]


def test_sem_contagem_de_compras_nao_ha_o_que_prever():
    previsao = fechamento.medidas_previram(
        {
            "pedidos": {"veredito": "cumprida", "meta": 20},
            "liberacoes": {"veredito": "cumprida"},
        },
        {"veredito": "nao-consigo-contar"},
    )
    assert previsao["veredito"] == "ainda-nao-da-para-saber"


def test_as_medidas_em_dia_com_o_resultado_em_dia_previram():
    previsao = fechamento.medidas_previram(
        {
            "pedidos": {"veredito": "cumprida", "meta": 20},
            "liberacoes": {"veredito": "cumprida"},
        },
        {"veredito": "ganhando"},
    )
    assert previsao["veredito"] == "previram"


def test_as_medidas_em_dia_com_o_resultado_abaixo_nao_previram():
    previsao = fechamento.medidas_previram(
        {
            "pedidos": {"veredito": "cumprida", "meta": 20},
            "liberacoes": {"veredito": "cumprida"},
        },
        {"veredito": "perdendo"},
    )
    assert previsao["veredito"] == "nao-previram"
    assert "coisa errada" in previsao["porque"]


def test_zero_esperado_com_zero_feito_nao_e_ganhando():
    """A tela não elogia quem ainda não foi cobrado de nada (`armadilhas/271`).

    Nas cinco primeiras semanas do ciclo a curva espera 0. O placar, pela régua
    dele, chama isso de "ganhando" (x >= esperado), e está certo dentro da
    régua. Repetir a palavra na tela do FECHAMENTO seria dizer ao mantenedor
    que a escola vai bem com 0 de 1000.
    """
    parado = {"veredito": "ganhando", "esperado_hoje": 0, "x": 0, "alvo": 1000}
    assert fechamento.veredito_do_ciclo(parado, "correndo") == "ainda-nao-cobra"


def test_zero_esperado_com_venda_acontecida_e_ganhando_de_verdade():
    """Quem compra antes de ser pedido ganhou, e a tela diz isso."""
    adiantado = {"veredito": "ganhando", "esperado_hoje": 0, "x": 3, "alvo": 1000}
    assert fechamento.veredito_do_ciclo(adiantado, "correndo") == "ganhando"


def test_o_veredito_do_placar_passa_inteiro_quando_a_curva_ja_cobra():
    cobrando = {"veredito": "perdendo", "esperado_hoje": 20, "x": 4, "alvo": 1000}
    assert fechamento.veredito_do_ciclo(cobrando, "correndo") == "perdendo"
    vencida = {"veredito": "vencida", "esperado_hoje": 0, "x": 0, "alvo": 1000}
    assert (
        fechamento.veredito_do_ciclo(vencida, "terminou") == "vencida"
    ), "ciclo terminado sem venda nenhuma é meta não cumprida, e a tela diz isso"


def test_sem_resultado_nao_ha_veredito():
    assert fechamento.veredito_do_ciclo(None, "correndo") is None


def test_livro_ausente_nunca_vira_nenhum_portao_provado():
    """`None` é "não consegui olhar"; lista vazia é "olhei e não há".

    Dizer "achando" a partir de um livro que não chegou seria afirmar a fase da
    escola inteira com base numa leitura que não aconteceu.
    """
    sem_livro = fechamento.portoes(None)
    assert sem_livro["livro"] is False
    assert sem_livro["provados"] is None
    assert sem_livro["fase"] is None

    livro_vazio = fechamento.portoes([])
    assert livro_vazio["livro"] is True
    assert livro_vazio["provados"] == 0
    assert livro_vazio["fase"] == fechamento.FASE_SEM_NENHUM


# ------------------------ 4. a fase é calculada, e declarar não é provar


def test_portao_declarado_sem_prova_conferida_nao_conta():
    so_declarado = _registro("20260905-002-so-declarado", portao="demanda")
    saida = fechamento.portoes([so_declarado])

    assert (
        saida["provados"] == 0
    ), "portão sem evidência conferida mudou a fase da escola"
    assert saida["fase"] == fechamento.FASE_SEM_NENHUM
    assert [f["arquivo"] for f in saida["declarados_sem_prova"]] == [
        so_declarado["arquivo"]
    ]


def test_portao_com_evidencia_mas_sem_data_de_conferencia_nao_conta():
    sem_data = _registro(
        "20260905-003-sem-data",
        portao="demanda",
        evidencia="https://github.com/abundanciabr/sitesdoreino/pull/999",
    )
    saida = fechamento.portoes([sem_data])
    assert saida["provados"] == 0
    assert saida["declarados_sem_prova"]


def test_portao_com_nome_inventado_e_dito_pelo_nome_nunca_ignorado():
    torto = _prova("converssao", "20260905-004-torto")
    saida = fechamento.portoes([torto])

    assert saida["provados"] == 0
    assert saida["desconhecidos"] == [
        {"arquivo": torto["arquivo"], "portao": "converssao", "titulo": torto["titulo"]}
    ]


def test_a_fase_sai_da_contagem_dos_portoes_provados():
    assert fechamento.portoes([])["fase"] == "achando"

    um = fechamento.portoes([_prova("demanda")])
    assert um["provados"] == 1 and um["fase"] == "provando"

    quase = fechamento.portoes(
        [
            _prova(chave, f"20260905-1{i:02d}-prova")
            for i, (chave, _, _) in enumerate(fechamento.PORTOES[:-1])
        ]
    )
    assert quase["provados"] == 7, "sete de oito"
    assert quase["fase"] == "provando", (
        "enquanto faltar um portão a escola está provando; promovê-la com portão "
        "em aberto seria a tela decidindo o que só a prova decide"
    )

    todos = fechamento.portoes(
        [
            _prova(chave, f"20260905-2{i:02d}-prova")
            for i, (chave, _, _) in enumerate(fechamento.PORTOES)
        ]
    )
    assert todos["provados"] == 8 and todos["fase"] == "escalando"


def test_o_mesmo_portao_provado_duas_vezes_conta_uma():
    duas = fechamento.portoes(
        [_prova("demanda", "20260905-005-um"), _prova("demanda", "20260905-006-outro")]
    )
    assert duas["provados"] == 1


def test_o_leitor_do_livro_enxerga_o_campo_portao(tmp_path):
    """O campo novo tem de chegar do arquivo até a conta, e não só do dicionário.

    Um `portao` que a tela lê em teste mas o leitor do livro não extrai do
    arquivo daria fase certa no teste e fase errada na tela do mantenedor.
    """
    (tmp_path / "20260905-007-portao.js").write_text(
        "(function(){ (window.REGISTROS = window.REGISTROS || []).push({\n"
        '  arquivo: "20260905-007-portao",\n'
        '  tipo: "medicao",\n'
        '  quando: "2026-09-05",\n'
        '  titulo: "A demanda existe",\n'
        '  portao: "demanda",\n'
        '  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/999",\n'
        '  verificado_em: "2026-09-05"\n'
        "});})();\n",
        encoding="utf-8",
    )
    lidos = direcao.ler_registros(tmp_path)
    assert lidos[0]["portao"] == "demanda"
    assert fechamento.portoes(lidos)["provados"] == 1


# ----------------------------- 5. o estado "correndo" é o principal


def test_ciclo_correndo_diz_quantas_semanas_faltam():
    dados = _dados()
    assert dados["estado"] == "correndo"
    assert dados["dias_restantes"] == 99, "de 07/09 a 15/12/2026"
    assert dados["semanas_restantes"] == 15


def test_passado_o_prazo_o_ciclo_terminou():
    dados = _dados(hoje=dt.date(2026, 12, 16))
    assert dados["estado"] == "terminou"
    assert dados["semanas_restantes"] == 0


def test_sem_cartao_nao_ha_ciclo_para_fechar():
    dados = _dados(meta=None, resultado=None)
    assert dados["estado"] == "sem-cartao"
    assert dados["ate"] is None


# ------------------------------------------------------------------ a tela


@respx.mock
def test_a_tela_abre_com_o_ciclo_correndo_e_a_previa():
    respx.get(ALUNOS_LISTA).mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{ALUNOS}/pre-matriculas").mock(
        return_value=httpx.Response(200, json=[])
    )

    resposta = _dentro().get(reverse("fechamento"))
    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert "O fechamento do ciclo" in html
    assert "O ciclo está correndo" in html
    assert "O que a escola PARA de fazer" in html
    assert resposta.context["fechamento"]["estado"] == "correndo"


@respx.mock
def test_a_tela_abre_mesmo_sem_a_alunos_e_nao_chama_ausencia_de_zero():
    respx.get(ALUNOS_LISTA).mock(return_value=httpx.Response(503))
    respx.get(f"{ALUNOS}/pre-matriculas").mock(return_value=httpx.Response(503))

    resposta = _dentro().get(reverse("fechamento"))
    assert resposta.status_code == 200
    assert "Não consigo contar agora" in resposta.content.decode()


@respx.mock
def test_a_tela_nao_diz_ganhando_com_zero_de_mil():
    """O caso REAL de hoje, renderizado: 0 comprado, 0 esperado pela curva."""
    respx.get(ALUNOS_LISTA).mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{ALUNOS}/pre-matriculas").mock(
        return_value=httpx.Response(200, json=[])
    )

    html = _dentro().get(reverse("fechamento")).content.decode()
    assert "Ainda não existe ganhando nem perdendo" in html
    assert (
        "ganhando</span>" not in html
    ), "a tela do fechamento elogiou uma escola que ainda não vendeu nada"


@respx.mock
def test_o_post_sem_a_recusa_devolve_a_lei_em_vez_do_pedido():
    respx.get(ALUNOS_LISTA).mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{ALUNOS}/pre-matriculas").mock(
        return_value=httpx.Response(200, json=[])
    )

    resposta = _dentro().post(
        reverse("fechamento"),
        {"paramos_de_fazer": "", "proximo_alvo": "2000", "proxima_ate": "2027-03-09"},
    )
    assert resposta.status_code == 200
    assert resposta.context["pedido"] is None
    assert "O ciclo não fecha sem" in resposta.content.decode()


@respx.mock
def test_o_post_completo_devolve_o_pedido_para_colar():
    respx.get(ALUNOS_LISTA).mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{ALUNOS}/pre-matriculas").mock(
        return_value=httpx.Response(200, json=[])
    )

    resposta = _dentro().post(reverse("fechamento"), CAMPOS_COMPLETOS)
    assert resposta.status_code == 200
    assert resposta.context["pedido"] is not None
    assert "parar de vender por mensagem uma a uma" in resposta.content.decode()


@respx.mock
def test_o_placar_leva_ate_o_fechamento():
    respx.get(ALUNOS_LISTA).mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{ALUNOS}/pre-matriculas").mock(
        return_value=httpx.Response(200, json=[])
    )
    html = _dentro().get(reverse("placar")).content.decode()
    assert f'href="{reverse("fechamento")}"' in html


def test_sem_cracha_a_tela_nao_abre():
    assert Client().get(reverse("fechamento")).status_code != 200
