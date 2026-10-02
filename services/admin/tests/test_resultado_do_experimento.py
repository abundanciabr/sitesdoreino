"""O resultado do experimento (frente F9a do sistema de experimentos).

O que cada grupo de guardas protege:

1. **A conta confere com a mão.** Cada caso aprovado traz o cálculo escrito no
   próprio teste: o caso clássico, o A/A, o SRM em alarme e o zero de
   conversões. Se a fórmula mudar, o número escrito aqui denuncia.
2. **Horizonte fixo, sem espiar** (Emenda 1 do desenho comum). Antes do fim
   planejado a conta de p e do intervalo nem existe; depois dele, braço abaixo
   da amostra planejada dá `inconclusivo (amostra insuficiente)`.
3. **Divisão torta bloqueia a promoção.** SRM sobre atribuídos, SRM sobre
   expostos e visitante com braço trocado acima do limite: qualquer um impede
   `candidato à promoção`.
4. **Divisão por zero e N pequeno não levantam exceção.**
5. **"Não perguntei" nunca vira zero** na tela, e o cliente fala o contrato.
"""

from __future__ import annotations

import datetime as dt
import re

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.core import resultado_do_experimento as re_
from apps.core.clients import MedicaoClient
from apps.core.paginas import SLUG_DA_PAGINA
from apps.core.resultado_do_experimento import Braco

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
METRICAS = "http://metricas:8000/api/metricas"
CAMINHO_DO_FUNIL = "/funil"
FUNIL = f"{METRICAS}{CAMINHO_DO_FUNIL}"
CATALOGO = "http://catalogo:8000/api/catalogo"
SITE = "5d1c0f4e-2a7b-4f11-9c3e-8b6a1d2e3f40"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"

EXPERIMENTO = "0b8f7a52-3c1e-4c7b-9a51-6f2d0c1e9a10"
LER_EXPERIMENTO = (
    f"{CATALOGO}/sites/{SITE}/paginas/{SLUG_DA_PAGINA}/experimentos/{EXPERIMENTO}"
)
SITE_DO_HOST = f"{CATALOGO}/sites/by-host/testserver"
INICIO = dt.date(2026, 9, 1)
# 14 dias planejados: o fim planejado é 15/09 e a janela é [01/09, 15/09].
DIAS = 14
FIM = dt.date(2026, 9, 15)
DEPOIS_DO_FIM = dt.date(2026, 9, 16)
NO_MEIO = dt.date(2026, 9, 8)


def _par(a: tuple, b: tuple, pesos=(5000, 5000)) -> list[Braco]:
    """(atribuidos, expostos, convertidos) de cada braço."""
    return [
        Braco("a", pesos[0], *a),
        Braco("b", pesos[1], *b),
    ]


def _avaliar(bracos, hoje=DEPOIS_DO_FIM, n=1000, trocados=0, encerrado_em=None):
    return re_.avaliar(
        bracos,
        iniciado_em=INICIO,
        dias_planejados=DIAS,
        n_por_braco_planejado=n,
        hoje=hoje,
        trocados=trocados,
        encerrado_em=encerrado_em,
    )


# ---------------------------------------------------------------------------
# 1. A conta confere com a mão
# ---------------------------------------------------------------------------


def test_caso_classico_duas_proporcoes():
    """A: 200 de 1000 (20%). B: 250 de 1000 (25%).

    Efeito absoluto 0,25 - 0,20 = 0,05; relativo 0,05 / 0,20 = 0,25.
    Teste z com variância agrupada: p = 450 / 2000 = 0,225;
    ep = raiz(0,225 x 0,775 x (1/1000 + 1/1000)) = raiz(0,00034875) = 0,0186748;
    z = 0,05 / 0,0186748 = 2,67740; p bicaudal = erfc(2,67740 / raiz 2) = 0,0074196.
    IC 95% sem agrupar: ep = raiz(0,2x0,8/1000 + 0,25x0,75/1000) = raiz(0,0003475)
    = 0,0186414; 1,959964 x 0,0186414 = 0,0365364; IC = [0,0134636; 0,0865364].
    """
    c = re_.comparar(
        Braco("a", 5000, 1000, 1000, 200), Braco("b", 5000, 1000, 1000, 250)
    )

    assert c.efeito_absoluto == pytest.approx(0.05)
    assert c.efeito_relativo == pytest.approx(0.25)
    assert c.p == pytest.approx(0.0074196, abs=1e-6)
    assert c.ic95[0] == pytest.approx(0.0134636, abs=1e-6)
    assert c.ic95[1] == pytest.approx(0.0865364, abs=1e-6)


def test_aa_nao_tem_efeito_e_p_e_um():
    """A: 100 de 1000. B: 100 de 1000.

    Efeito 0; z = 0; p = erfc(0) = 1. IC: ep = raiz(2 x 0,1 x 0,9 / 1000)
    = raiz(0,00018) = 0,0134164; 1,959964 x 0,0134164 = 0,0262957; IC simétrico.
    """
    c = re_.comparar(
        Braco("a", 5000, 1000, 1000, 100), Braco("b", 5000, 1000, 1000, 100)
    )

    assert c.efeito_absoluto == 0
    assert c.efeito_relativo == 0
    assert c.p == 1.0
    assert c.ic95[0] == pytest.approx(-0.0262957, abs=1e-6)
    assert c.ic95[1] == pytest.approx(0.0262957, abs=1e-6)

    r = _avaliar(_par((1000, 1000, 100), (1000, 1000, 100)))
    assert r.veredito == re_.INCONCLUSIVO


def test_srm_em_alarme_pelo_qui_quadrado():
    """5500 contra 4500 num 50/50: esperado 5000 em cada.

    qui2 = 500^2/5000 + 500^2/5000 = 50 + 50 = 100; com 1 grau de liberdade,
    p = erfc(raiz(100/2)) = erfc(7,0711) = 1,524e-23, abaixo de 0,001: alarme.
    """
    s = re_.srm(
        [Braco("a", 5000, 5500, 0, 0), Braco("b", 5000, 4500, 0, 0)], "atribuidos"
    )

    assert s.qui_quadrado == pytest.approx(100.0)
    assert s.p == pytest.approx(1.524e-23, rel=1e-3)
    assert s.alarme is True


def test_srm_sem_alarme_no_valor_tabelado():
    """5050 contra 4950: qui2 = 2 x 50^2/5000 = 1,0; p = erfc(raiz(0,5)) = 0,3173
    (o valor de tabela da qui-quadrado com 1 grau de liberdade em 1,0)."""
    s = re_.srm(
        [Braco("a", 5000, 5050, 0, 0), Braco("b", 5000, 4950, 0, 0)], "atribuidos"
    )

    assert s.qui_quadrado == pytest.approx(1.0)
    assert s.p == pytest.approx(0.3173105, abs=1e-6)
    assert s.alarme is False


def test_srm_respeita_pesos_desiguais():
    """Pesos 7000/3000 e 700 contra 300: é exatamente o planejado, qui2 = 0."""
    s = re_.srm(
        [Braco("a", 7000, 700, 0, 0), Braco("b", 3000, 300, 0, 0)], "atribuidos"
    )

    assert s.qui_quadrado == pytest.approx(0.0)
    assert s.p == pytest.approx(1.0)
    assert s.alarme is False


def test_zero_conversoes_nos_dois_bracos():
    """0 de 500 contra 0 de 500: taxa agrupada 0, erro padrão 0. Não há diferença
    nenhuma a testar: efeito 0, p = 1, IC [0; 0], e o relativo não existe
    (dividiria por uma taxa de controle zero)."""
    c = re_.comparar(Braco("a", 5000, 500, 500, 0), Braco("b", 5000, 500, 500, 0))

    assert c.efeito_absoluto == 0
    assert c.efeito_relativo is None
    assert c.p == 1.0
    assert c.ic95 == (0.0, 0.0)


def test_controle_zerado_e_tratamento_com_conversao():
    """0 de 500 contra 5 de 500. Efeito 0,01; relativo não existe (controle 0).
    Agrupada 5/1000 = 0,005; ep = raiz(0,005 x 0,995 x 2/500) = 0,0044609;
    z = 2,24168; p = erfc(2,24168 / raiz 2) = 0,0249821."""
    c = re_.comparar(Braco("a", 5000, 500, 500, 0), Braco("b", 5000, 500, 500, 5))

    assert c.efeito_absoluto == pytest.approx(0.01)
    assert c.efeito_relativo is None
    assert c.p == pytest.approx(0.0249821, abs=1e-6)


# ---------------------------------------------------------------------------
# 2. Horizonte fixo, sem espiar
# ---------------------------------------------------------------------------


def test_coletando_nao_calcula_p_nem_intervalo():
    r = _avaliar(_par((1000, 1000, 200), (1000, 1000, 250)), hoje=NO_MEIO)

    assert r.veredito == re_.COLETANDO
    assert r.comparacao is None
    assert r.dias_corridos == 7
    assert r.fim_planejado == FIM


def test_no_ultimo_dia_da_janela_ainda_e_coletando():
    """O dia 15 ainda está acontecendo: a janela só fecha quando ele acaba."""
    r = _avaliar(_par((1000, 1000, 200), (1000, 1000, 250)), hoje=FIM)

    assert r.veredito == re_.COLETANDO
    assert r.comparacao is None


def test_no_horizonte_braco_abaixo_do_planejado_e_amostra_insuficiente():
    r = _avaliar(_par((1000, 999, 200), (1000, 1000, 250)), n=1000)

    assert r.veredito == re_.AMOSTRA_INSUFICIENTE
    assert r.veredito == "inconclusivo (amostra insuficiente)"


def test_no_horizonte_b_melhor_com_significancia_e_candidato():
    # guarda: services/admin/apps/core/resultado_do_experimento.py:170
    r = _avaliar(_par((1000, 1000, 200), (1000, 1000, 250)))

    assert r.veredito == re_.CANDIDATO
    assert r.veredito == "candidato à promoção"
    assert r.comparacao.p < 0.05


def test_b_pior_com_significancia_nao_e_candidato():
    r = _avaliar(_par((1000, 1000, 250), (1000, 1000, 200)))

    assert r.veredito == re_.INCONCLUSIVO
    assert "menos" in r.motivo


def test_encerrado_antes_do_horizonte_nao_calcula_p():
    """Parar no meio porque o número pareceu bom é exatamente o espiar que o
    horizonte fixo proíbe: a conta não é feita."""
    r = _avaliar(
        _par((1000, 1000, 200), (1000, 1000, 250)),
        hoje=DEPOIS_DO_FIM,
        encerrado_em=NO_MEIO,
    )

    assert r.veredito == re_.INCONCLUSIVO
    assert r.comparacao is None
    assert "antes" in r.motivo


# ---------------------------------------------------------------------------
# 3. Divisão torta bloqueia a promoção
# ---------------------------------------------------------------------------


def test_srm_nos_atribuidos_bloqueia_candidato():
    # guarda: services/admin/apps/core/resultado_do_experimento.py:190
    r = _avaliar(_par((1150, 1000, 200), (850, 1000, 250)))

    assert r.srm_atribuidos.alarme is True
    assert r.comparacao.p < 0.05
    assert r.veredito == re_.INCONCLUSIVO
    assert "divisão" in r.motivo


def test_srm_nos_expostos_bloqueia_candidato():
    # guarda: services/admin/apps/core/resultado_do_experimento.py:190
    r = _avaliar(_par((1000, 1000, 200), (1000, 1200, 300)))

    assert r.srm_atribuidos.alarme is False
    assert r.srm_expostos.alarme is True
    assert r.veredito == re_.INCONCLUSIVO


def test_bracos_trocados_acima_do_limite_bloqueiam_candidato():
    """2000 atribuídos: o limite de 1% são 20 visitantes."""
    # guarda: services/admin/apps/core/resultado_do_experimento.py:212
    bracos = _par((1000, 1000, 200), (1000, 1000, 250))

    assert _avaliar(bracos, trocados=20).veredito == re_.CANDIDATO
    r = _avaliar(bracos, trocados=21)
    assert r.trocados_em_alarme is True
    assert r.veredito == re_.INCONCLUSIVO


# ---------------------------------------------------------------------------
# 4. Divisão por zero e N pequeno
# ---------------------------------------------------------------------------


def test_braco_sem_ninguem_nao_levanta_excecao():
    a = Braco("a", 5000, 0, 0, 0)
    b = Braco("b", 5000, 3, 2, 1)

    assert a.taxa is None
    c = re_.comparar(a, b)
    assert c.p is None and c.ic95 is None and c.efeito_absoluto is None
    s = re_.srm([a, Braco("b", 5000, 0, 0, 0)], "atribuidos")
    assert s.p is None and s.alarme is False
    r = _avaliar([a, b], n=1)
    assert r.veredito == re_.AMOSTRA_INSUFICIENTE


def test_peso_zero_com_gente_dentro_e_alarme():
    s = re_.srm([Braco("a", 10000, 10, 0, 0), Braco("b", 0, 1, 0, 0)], "atribuidos")

    assert s.alarme is True


# ---------------------------------------------------------------------------
# A amostra planejada (DECISAO-a-pagina-real-antes-do-experimento, §3)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "base,mde,esperado",
    [
        # As seis linhas da tabela publicada na DECISAO §3 (lift relativo
        # convertido em efeito absoluto: base x lift).
        (0.02, 0.004, 21109),
        (0.02, 0.010, 3826),
        (0.10, 0.020, 3841),
        (0.10, 0.050, 686),
        (0.30, 0.060, 963),
        (0.30, 0.150, 163),
    ],
)
def test_n_por_braco_bate_com_a_tabela_da_decisao(base, mde, esperado):
    # guarda: services/admin/apps/core/resultado_do_experimento.py:151
    assert re_.n_por_braco_planejado(base, mde) == esperado


@pytest.mark.parametrize(
    "base,mde", [(0, 0.01), (1, 0.01), (0.1, 0), (0.1, -0.01), (0.95, 0.05)]
)
def test_n_por_braco_recusa_entrada_impossivel_com_frase(base, mde):
    with pytest.raises(ValueError, match="taxa|efeito"):
        re_.n_por_braco_planejado(base, mde)


# ---------------------------------------------------------------------------
# 5. A tela
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    monkeypatch.setenv("METRICAS_API_URL", METRICAS)
    monkeypatch.setenv("METRICAS_API_TOKEN", "token-do-par-admin-metricas")
    monkeypatch.setenv("CATALOGO_API_URL", CATALOGO)
    monkeypatch.setenv("TOKEN_CATALOGO", "token-do-par-admin-catalogo")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"
    monkeypatch.setattr(re_.timezone, "localdate", lambda: DEPOIS_DO_FIM)


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


def _experimento(**troca) -> dict:
    corpo = {
        "id": EXPERIMENTO,
        "site_id": SITE,
        "slug": SLUG_DA_PAGINA,
        "estado": "ativo",
        "decisao": None,
        "vencedora": None,
        "secao": "cubo",
        "slot": "titulo",
        "hipotese": "Um título mais direto faz mais gente entrar no checkout",
        "metrica_principal": "entrada no checkout por visitante",
        "taxa_base": 0.2,
        "mde": 0.05,
        "n_por_braco_planejado": 1000,
        "dias_planejados": DIAS,
        "criado_em": "2026-08-31T10:00:00-03:00",
        "iniciado_em": "2026-09-01T13:00:00-03:00",
        "fim_planejado": "2026-09-15T13:00:00-03:00",
        "encerrado_em": None,
        "variantes": [
            {"variante_id": "b", "peso": 5000, "valor": "Texto B"},
            {"variante_id": "a", "peso": 5000, "valor": "Texto A"},
        ],
    }
    corpo.update(troca)
    return corpo


def _funil(variantes, coleta=True, trocados=0) -> dict:
    return {
        "site_id": SITE,
        "experimento_id": EXPERIMENTO,
        "de": "2026-09-01",
        "ate": "2026-09-15",
        "coleta": (
            {"primeiro": "2026-09-01T16:00:00Z", "ultimo": "2026-09-15T22:00:00Z"}
            if coleta
            else {"primeiro": None, "ultimo": None}
        ),
        "passos": [
            {"passo": passo, "visitantes": 0} for passo in MedicaoClient.PASSOS_DO_FUNIL
        ],
        "por_dia": [],
        "variantes": [
            {
                "variante_id": v,
                "atribuidos": at,
                "expostos": ex,
                "convertidos": co,
                "passos": [],
            }
            for v, at, ex, co in variantes
        ],
        "visitantes_com_bracos_trocados": trocados,
    }


def _catalogo_responde(corpo, status=200):
    respx.get(SITE_DO_HOST).mock(
        return_value=httpx.Response(200, json={"id": SITE, "host": "testserver"})
    )
    return respx.get(LER_EXPERIMENTO).mock(
        return_value=httpx.Response(status, json=corpo)
    )


def _abrir(c: Client) -> str:
    r = c.get(reverse("resultado_do_experimento", args=[EXPERIMENTO]))
    assert r.status_code == 200
    return r.content.decode()


@respx.mock
def test_tela_madura_mostra_a_conta_e_o_veredito():
    _catalogo_responde(_experimento())
    rota = respx.get(FUNIL).mock(
        return_value=httpx.Response(
            200, json=_funil([("a", 1000, 1000, 200), ("b", 1000, 1000, 250)])
        )
    )

    html = _abrir(_dentro())

    assert "candidato à promoção" in html
    assert "0,0074" in html  # o p do caso clássico
    assert "+5,00 pontos" in html
    pedido = rota.calls.last.request.url.params
    assert pedido["experimento_id"] == EXPERIMENTO
    assert pedido["secao"] == "cubo"
    assert pedido["site_id"] == SITE
    assert pedido["de"] == "2026-09-01"
    assert pedido["ate"] == "2026-09-15"


@respx.mock
def test_tela_coletando_nao_mostra_p_nem_intervalo_nem_conversoes(monkeypatch):
    # guarda: services/admin/apps/core/resultado_do_experimento.py:413
    monkeypatch.setattr(re_.timezone, "localdate", lambda: NO_MEIO)
    _catalogo_responde(_experimento())
    rota = respx.get(FUNIL).mock(
        return_value=httpx.Response(
            200, json=_funil([("a", 400, 380, 77), ("b", 410, 390, 99)])
        )
    )

    html = _abrir(_dentro())

    assert "coletando" in html
    assert "Intervalo de 95%" not in html
    assert "Valor p" not in html
    assert ">77<" not in html and ">99<" not in html
    assert ">380<" in html and ">390<" in html
    assert "Faltam para a amostra" in html and ">620<" in html
    # A janela perguntada vai só até hoje, e nunca além do fim planejado.
    assert rota.calls.last.request.url.params["ate"] == NO_MEIO.isoformat()


@respx.mock
def test_coletando_nem_leva_as_conversoes_ate_a_tela():
    """O número escondido não viaja: o template não tem como vazá-lo."""
    _catalogo_responde(_experimento())
    respx.get(FUNIL).mock(
        return_value=httpx.Response(
            200, json=_funil([("a", 400, 380, 77), ("b", 410, 390, 99)])
        )
    )

    tela = re_.montar({"id": SITE}, EXPERIMENTO, NO_MEIO)

    assert tela["veredito"] == re_.COLETANDO
    assert tela["conta"] is None
    assert all(
        linha["convertidos"] is None and linha["taxa"] is None
        for linha in tela["linhas"]
    )


@respx.mock
def test_medicao_fora_do_ar_vira_aviso_e_nunca_zero():
    _catalogo_responde(_experimento())
    respx.get(FUNIL).mock(side_effect=httpx.ConnectError("sem rede"))

    html = _abrir(_dentro())

    assert "não respondeu" in html
    assert "coletando" not in html
    assert "candidato" not in html
    assert not re.search(r"<td[^>]*>\s*0\s*</td>", html)


@respx.mock
def test_catalogo_fora_do_ar_vira_aviso():
    respx.get(SITE_DO_HOST).mock(side_effect=httpx.ConnectError("sem rede"))

    html = _abrir(_dentro())

    assert "catálogo não respondeu" in html


@respx.mock
def test_experimento_que_nao_existe_diz_isso():
    _catalogo_responde({"detail": "não existe"}, status=404)

    html = _abrir(_dentro())

    assert "não existe" in html


@respx.mock
def test_rascunho_ainda_nao_comecou_e_nao_pergunta_a_medicao():
    _catalogo_responde(_experimento(estado="rascunho", iniciado_em=None))
    rota = respx.get(FUNIL)

    html = _abrir(_dentro())

    assert "ainda não começou" in html
    assert not rota.called


@respx.mock
def test_encerrado_sem_ter_comecado_diz_isso_e_nao_e_defeito():
    _catalogo_responde(_experimento(estado="encerrado", iniciado_em=None))

    html = _abrir(_dentro())

    assert "encerrado sem nunca ter começado" in html
    assert "fora do combinado" not in html


@respx.mock
def test_sem_coleta_nao_e_zero():
    _catalogo_responde(_experimento())
    respx.get(FUNIL).mock(
        return_value=httpx.Response(200, json=_funil([], coleta=False))
    )

    html = _abrir(_dentro())

    assert "nenhum evento" in html
    assert "candidato" not in html


@respx.mock
def test_braco_que_a_medicao_nao_conhece_e_fora_do_contrato():
    _catalogo_responde(_experimento())
    respx.get(FUNIL).mock(
        return_value=httpx.Response(
            200, json=_funil([("a", 10, 10, 1), ("z", 10, 10, 1)])
        )
    )

    html = _abrir(_dentro())

    assert "fora do combinado" in html
    assert "candidato" not in html


@respx.mock
def test_braco_ainda_sem_visitante_conta_como_zero_quando_ha_coleta():
    _catalogo_responde(_experimento())
    respx.get(FUNIL).mock(
        return_value=httpx.Response(200, json=_funil([("a", 1000, 1000, 200)]))
    )

    html = _abrir(_dentro())

    assert "inconclusivo (amostra insuficiente)" in html


# ---------------------------------------------------------------------------
# As duas portas que as frentes irmãs usam
# ---------------------------------------------------------------------------


@respx.mock
def test_veredito_do_experimento_para_a_decisao():
    respx.get(FUNIL).mock(
        return_value=httpx.Response(
            200, json=_funil([("a", 1000, 1000, 200), ("b", 1000, 1000, 250)])
        )
    )

    assert re_.veredito_do_experimento(SITE, _experimento()) == re_.CANDIDATO


@respx.mock
def test_veredito_sem_medicao_e_none_e_nunca_um_veredito_inventado():
    respx.get(FUNIL).mock(side_effect=httpx.ConnectError("sem rede"))

    assert re_.veredito_do_experimento(SITE, _experimento()) is None
