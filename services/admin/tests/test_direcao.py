"""A direção da semana (degrau 2 do plano do painel de gestão).

O que estes guardas protegem:

1. **As duas medidas são medidas pela data certa**, no fuso certo, nas janelas
   certas (7 dias por semana, 4 semanas para trás; 28 dias para as liberações).
2. **A meta da semana deriva da régua do ciclo** quando o mantenedor não fixou
   uma, e a fixada vence a derivada. Desde 04/09/2026 essa régua é a CURVA de
   `semanas` do cartão quando ela existe, e a linha reta quando não existe (os
   testes de unidade daqui usam um `META` sem curva, e por isso continuam
   medindo a linha reta: é o caminho de quem não declara semanas).
3. **"Não medi" se declara**: lista que não chegou ⇒ `nao-consigo-medir`.
4. **O compromisso é registro, e o veredito é calculado**: com resposta é
   cumprido; vencido sem resposta é não cumprido; o resto está em aberto. O
   leitor mínimo do livro lê o que a `logica.js` validou, e nada mais.
5. **A tela mostra as duas medidas e os compromissos**, e o vocabulário do
   livro aceita `compromisso` só com prazo (o teste em `painel/testes/`).
"""

from __future__ import annotations

import datetime as dt

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.core import direcao, placar

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"
ALUNOS = "http://alunos:8000/api/alunos"
FILA = f"{ALUNOS}/pre-matriculas"
ALUNOS_LISTA = f"{ALUNOS}/matriculas"

HOJE = dt.date(2026, 10, 9)
META = {"alvo": 500, "ate": "2026-12-15", "partida": 0, "partida_em": "2026-09-03"}


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    monkeypatch.setenv("ALUNOS_API_URL", ALUNOS)
    monkeypatch.setenv("ALUNOS_API_TOKEN", "token-do-par-admin-alunos")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"
    monkeypatch.setattr(placar.timezone, "localdate", lambda: HOJE)


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


def _em(dia: str) -> str:
    return f"{dia}T12:00:00-03:00"


def _pedido(dia: str, esperando: int) -> dict:
    return {
        "status": "aguardando",
        "criada_em": _em(dia),
        "esperando_ha_dias": esperando,
    }


def _liberada(pediu: str, liberou: str, status: str = "ativa") -> dict:
    return {
        "status": status,
        "origem": "liberado",
        "criada_em": _em(pediu),
        "virou_aluno_em": _em(liberou),
    }


# ---------------------------------------------------------------- os pedidos


def test_pedidos_por_semana_da_atual_para_tras():
    aguardando = [_pedido("2026-10-09", 0), _pedido("2026-10-03", 6)]  # semana 0 e 0
    recusados = [{"status": "recusada", "criada_em": _em("2026-10-01")}]  # semana 1
    alunos = [
        _liberada("2026-09-20", "2026-09-21"),  # semana 2
        _liberada("2026-09-05", "2026-09-06"),  # fora (5 semanas)
        {
            "status": "ativa",
            "origem": "comprou",
            "criada_em": _em("2026-10-08"),
            "virou_aluno_em": _em("2026-10-08"),
        },
    ]
    assert direcao.medir_pedidos(aguardando, recusados, alunos, HOJE) == [2, 1, 1, 0]


def test_pedidos_sem_lista_nao_e_zero():
    assert direcao.medir_pedidos(None, [], [], HOJE) is None


def test_a_meta_da_semana_deriva_da_linha_reta_e_a_fixada_vence():
    # esperado(09/10) - esperado(02/10) = round(500*36/103) - round(500*29/103) = 175 - 141 = 34.
    meta, derivada = direcao.meta_semanal_de_pedidos({"meta_semanal": None}, META, HOJE)
    assert (meta, derivada) == (34, True)
    assert direcao.meta_semanal_de_pedidos({"meta_semanal": 50}, META, HOJE) == (
        50,
        False,
    )
    assert direcao.meta_semanal_de_pedidos(
        {"meta_semanal": None}, {"alvo": None}, HOJE
    ) == (None, False)


def test_a_sequencia_conta_semanas_anteriores_na_meta():
    r = direcao.calcular_direcao(
        {"meta_semanal": 2}, {}, META, [1, 3, 2, 1], None, HOJE
    )
    assert r["pedidos"]["veredito"] == "abaixo"
    assert r["pedidos"]["sequencia"] == 2, "3 e 2 cumprem; 1 quebra"
    r = direcao.calcular_direcao(
        {"meta_semanal": 2}, {}, META, [2, 3, 2, 5], None, HOJE
    )
    assert r["pedidos"]["veredito"] == "cumprida" and r["pedidos"]["sequencia"] == 3


# ------------------------------------------------------------- as 48 horas


def test_liberacoes_em_48h_na_janela_de_28_dias():
    aguardando = [_pedido("2026-10-08", 1), _pedido("2026-10-05", 4)]
    alunos = [
        _liberada("2026-10-01", "2026-10-02"),  # 1 dia: no prazo
        _liberada("2026-09-25", "2026-09-30"),  # 5 dias: fora do prazo
        _liberada("2026-08-01", "2026-08-02"),  # fora da janela
        _liberada("2026-10-03", "2026-10-04", status="reembolsada"),  # não conta
    ]
    r = direcao.medir_liberacoes_em_48h(aguardando, alunos, HOJE)
    assert r == {"no_prazo": 1, "total": 2, "por_cento": 50, "esperando_ha_muito": 1}
    d = direcao.calcular_direcao(
        {"meta_semanal": None}, {}, META, [0, 0, 0, 0], r, HOJE
    )
    assert d["liberacoes"]["veredito"] == "abaixo"


def test_tudo_no_prazo_e_ninguem_esperando_e_na_meta():
    r = {"no_prazo": 3, "total": 3, "por_cento": 100, "esperando_ha_muito": 0}
    d = direcao.calcular_direcao(
        {"meta_semanal": None}, {}, META, [0, 0, 0, 0], r, HOJE
    )
    assert d["liberacoes"]["veredito"] == "cumprida"


def test_sem_liberacoes_e_sem_fila_nao_e_meta_cumprida_nem_falha():
    r = {"no_prazo": 0, "total": 0, "por_cento": None, "esperando_ha_muito": 0}
    d = direcao.calcular_direcao(
        {"meta_semanal": None}, {}, META, [0, 0, 0, 0], r, HOJE
    )
    assert d["liberacoes"]["veredito"] == "sem-liberacoes"


def test_lista_ausente_e_nao_consigo_medir():
    d = direcao.calcular_direcao({"meta_semanal": None}, {}, META, None, None, HOJE)
    assert d["pedidos"]["veredito"] == "nao-consigo-medir"
    assert d["liberacoes"]["veredito"] == "nao-consigo-medir"


# ------------------------------------------------------------ compromissos


def _registro(pasta, arquivo, **campos):
    linhas = [f'  arquivo: "{arquivo}",']
    for chave, valor in campos.items():
        if valor is None:
            linhas.append(f"  {chave}: null,")
        elif isinstance(valor, int):
            linhas.append(f"  {chave}: {valor},")
        else:
            linhas.append(f'  {chave}: "{valor}",')
    corpo = "(function(){ (window.REGISTROS = window.REGISTROS || []).push({\n"
    corpo += "\n".join(linhas) + '\n  detalhe: "x "\n    + "y",\n});})();\n'
    (pasta / f"{arquivo}.js").write_text(corpo, encoding="utf-8")


def test_o_leitor_minimo_le_o_cabecalho_e_o_veredito_e_calculado(tmp_path):
    _registro(
        tmp_path,
        "20261001-001-a",
        tipo="compromisso",
        quando="2026-10-01",
        titulo="Ligar para os 5 da fila",
        responde_a=None,
        vence_em_dias=7,
    )
    _registro(
        tmp_path,
        "20261005-002-b",
        tipo="resposta",
        quando="2026-10-05",
        titulo="Liguei",
        responde_a="20261001-001-a",
        vence_em_dias=None,
    )
    _registro(
        tmp_path,
        "20260928-003-c",
        tipo="compromisso",
        quando="2026-09-28",
        titulo="Publicar o convite",
        responde_a=None,
        vence_em_dias=7,
    )
    _registro(
        tmp_path,
        "20261008-004-d",
        tipo="compromisso",
        quando="2026-10-08",
        titulo="Revisar a fila",
        responde_a=None,
        vence_em_dias=7,
    )
    _registro(
        tmp_path,
        "20260801-005-e",
        tipo="compromisso",
        quando="2026-08-01",
        titulo="Velho demais",
        responde_a=None,
        vence_em_dias=7,
    )
    _registro(
        tmp_path,
        "20261008-006-f",
        tipo="nota",
        quando="2026-10-08",
        titulo="Não é compromisso",
        responde_a=None,
        vence_em_dias=None,
    )
    registros = direcao.ler_registros(tmp_path)
    assert len(registros) == 6
    c = direcao.compromissos(registros, HOJE)
    por_arquivo = {x["arquivo"]: x["veredito"] for x in c}
    assert por_arquivo == {
        "20261001-001-a": "cumprido",
        "20260928-003-c": "nao-cumprido",
        "20261008-004-d": "em-aberto",
    }
    assert c[0]["arquivo"] == "20261008-004-d", "do mais recente para o mais antigo"
    assert c[0]["vence"] == dt.date(2026, 10, 15)


def test_o_livro_do_repositorio_e_lido_por_inteiro():
    registros = direcao.ler_registros()
    assert registros is not None and len(registros) > 300
    assert all(r["tipo"] for r in registros), "todo registro tem tipo"


def test_sem_livro_e_none_e_nao_lista_vazia():
    assert direcao.compromissos(None, HOJE) is None


def test_os_cartoes_da_direcao_sao_validos():
    for nome in (placar.CARTAO_DOS_PEDIDOS, placar.CARTAO_DAS_48H):
        cartao, problemas = placar.ler_cartao(nome)
        assert cartao is not None, problemas
        assert cartao["tipo"] == "direcao" and cartao["par"] == placar.CARTAO_DA_META


def test_as_duas_medidas_acesas_dizem_que_a_compra_aconteceu_fora_do_site():
    """A correção do mantenedor de 05/09/2026, presa nos dois cartões.

    Ninguém pede entrada na escola: quem está na fila JÁ COMPROU, fora do site,
    e espera confirmação. O texto que envelheceu era o nome, não a medida, e é
    justamente por a conta continuar exata que a volta ao texto antigo passaria
    despercebida por qualquer suíte verde. Este guarda é o que impede a volta.
    """
    for nome in (placar.CARTAO_DOS_PEDIDOS, placar.CARTAO_DAS_48H):
        cartao, problemas = placar.ler_cartao(nome)
        assert cartao is not None, problemas
        texto = f"{cartao['pergunta']} {cartao['definicao']} {cartao['acao']}".lower()
        assert "sala de espera" in texto, f"{nome} não nomeia a sala de espera"
        assert "fora do site" in texto, f"{nome} não diz que a compra foi feita fora"
        for mentira in (
            "pediram para entrar",
            "pediu para entrar",
            "pedir para entrar",
        ):
            assert (
                mentira not in texto
            ), f"{nome} ainda trata a fila como pedido de entrada"


def test_o_caminho_da_venda_nasce_apagado_e_diz_por_que():
    """Os dois cartões novos, e a trava que os mantém sem número.

    Acender um número de venda contraria a decisão do mantenedor de 22/08/2026
    (o checkout está congelado). O guarda é fail-closed pelo lado certo: quem
    ligar uma fonte aqui sem ele mandar abre vermelho.
    """
    assert len(placar.CARTOES_DO_CAMINHO_DA_VENDA) == 2
    for nome in placar.CARTOES_DO_CAMINHO_DA_VENDA:
        cartao, problemas = placar.ler_cartao(nome)
        assert cartao is not None, problemas
        assert cartao["tipo"] == "direcao" and cartao["andar"] == 0
        assert cartao["fonte"] is None, f"{nome} acendeu venda sem ordem do mantenedor"
        assert "22/08/2026" in cartao["sem_fonte_porque"], "diga por que está apagado"


# -------------------------------------------------------------------- a tela


@respx.mock
def test_a_tela_mostra_as_duas_medidas_e_os_compromissos():
    respx.get(FILA, params={"status": "aguardando"}).mock(
        return_value=httpx.Response(200, json=[_pedido("2026-10-08", 1)])
    )
    respx.get(FILA, params={"status": "recusada"}).mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(ALUNOS_LISTA).mock(
        return_value=httpx.Response(200, json=[_liberada("2026-10-01", "2026-10-02")])
    )
    html = _dentro().get(reverse("placar")).content.decode()
    assert "A direção da semana" in html
    assert "nesta semana" in html
    # A meta da semana é PERGUNTADA à régua, e não cravada aqui. Até 04/09/2026
    # ela era o mesmo 34 toda semana, porque a meta se repartia em linha reta;
    # com a curva do ciclo ela muda de semana para semana, e um número cravado
    # neste teste ficaria vermelho sozinho na virada de uma segunda-feira.
    # Este teste mede a TELA (o bloco aparece, com o número que a régua deu);
    # quem mede se a régua está certa é `tests/test_ciclo.py`.
    meta_do_ciclo, _recusas = placar.ler_cartao(placar.CARTAO_DA_META)
    hoje = timezone.localdate()
    alvo_da_semana = placar.esperado_em(meta_do_ciclo, hoje) - placar.esperado_em(
        meta_do_ciclo, hoje - dt.timedelta(days=7)
    )
    assert f"meta da semana: {alvo_da_semana}" in html
    assert "100%" in html and "na meta" in html
    assert "Os compromissos da semana" in html


@respx.mock
def test_a_tela_mostra_o_caminho_da_venda_apagado():
    """Os dois cartões sem fonte aparecem na tela, com a frase que os explica."""
    respx.get(FILA, params={"status": "aguardando"}).mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(FILA, params={"status": "recusada"}).mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(ALUNOS_LISTA).mock(return_value=httpx.Response(200, json=[]))
    html = _dentro().get(reverse("placar")).content.decode()
    assert "O caminho da venda" in html
    for nome in placar.CARTOES_DO_CAMINHO_DA_VENDA:
        cartao, _recusas = placar.ler_cartao(nome)
        assert cartao["pergunta"] in html, f"{nome} não aparece na tela"
        assert (
            cartao["sem_fonte_porque"] in html
        ), f"{nome} não diz por que está apagado"
