"""O funil da página de venda na tela (`/admin/placar/funil/`, frente F7).

O que cada grupo de guardas protege, e por que ele existe:

1. **Três respostas que parecem iguais de longe e não são.** Memória fora do
   ar, memória sem nenhuma visita medida na janela, e memória medindo com zero
   pessoas num degrau. Só a terceira mostra o número zero; as outras duas dizem
   o que aconteceu com palavras, porque um zero ali seria mentira.
2. **A taxa é entre degraus vizinhos, e degrau anterior vazio não vira 0%.**
   Dividir por zero não é "ninguém passou": é "não havia de onde passar".
3. **A janela é escolhida pela pessoa, e a pedida é a perguntada.** Pedido
   inválido cai na janela padrão e a tela diz isso.
4. **Por dia, sem inventar dia antes do primeiro fato.** Antes dele a memória
   pode não estar escutando; depois dele o buraco é zero honesto.
5. **Só a equipe entra.** Sem sessão, login; sessão fora da lista, 404.
"""

from __future__ import annotations

import datetime as dt

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.core import funil as fu
from apps.core.clients import MedicaoClient

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
METRICAS = "http://metricas:8000/api/metricas"
FUNIL = f"{METRICAS}/funil"
CATALOGO = "http://catalogo:8000/api/catalogo"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"

HOJE = dt.date(2026, 9, 26)

PASSOS = (
    "pagina_vista",
    "secao_vista",
    "cta_checkout",
    "lead_capturado",
    "pedido_atribuido",
    "pedido_pago",
)


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    monkeypatch.setenv("METRICAS_API_URL", METRICAS)
    monkeypatch.setenv("METRICAS_API_TOKEN", "token-do-par-admin-metricas")
    monkeypatch.delenv("CATALOGO_API_URL", raising=False)
    monkeypatch.delenv("TOKEN_CATALOGO", raising=False)
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"
    monkeypatch.setattr(fu.timezone, "localdate", lambda: HOJE)


def _pessoa(email: str) -> dict:
    return {
        "autenticado": True,
        "id": "id-opaco-123",
        "nome_exibido": "Fulano",
        "papel": None,
        "email": email,
    }


def _dentro(email: str = DONO) -> Client:
    respx.get(SESSAO).mock(return_value=httpx.Response(200, json=_pessoa(email)))
    c = Client()
    c.defaults["HTTP_COOKIE"] = COOKIE
    return c


def _passos(*visitantes: int) -> list[dict]:
    return [{"passo": p, "visitantes": v} for p, v in zip(PASSOS, visitantes)]


def _resposta(
    passos: list[dict],
    por_dia: list[tuple[str, tuple[int, ...]]] = (),
    coleta: tuple[str | None, str | None] = (
        "2026-09-20T13:02:00-03:00",
        "2026-09-26T09:40:00-03:00",
    ),
) -> dict:
    return {
        "site_id": "",
        "experimento_id": "",
        "de": "2026-08-28",
        "ate": "2026-09-26",
        "coleta": {"primeiro": coleta[0], "ultimo": coleta[1]},
        "passos": passos,
        "por_dia": [{"dia": dia, "passos": _passos(*v)} for dia, v in por_dia],
        "variantes": None,
        "visitantes_com_bracos_trocados": None,
    }


def _a_memoria_responde(corpo: dict):
    return respx.get(FUNIL).mock(return_value=httpx.Response(200, json=corpo))


def _degrau(tela: dict, passo: str) -> dict:
    return next(d for d in tela["escada"] if d["passo"] == passo)


# ---------------------------------------------------------------------------
# 1. Fora do ar, sem coleta e zero verdadeiro são três telas diferentes
# ---------------------------------------------------------------------------


def test_memoria_fora_do_ar_nao_vira_escada_de_zeros():
    tela = fu.montar(MedicaoClient.NAO_RESPONDEU, None, HOJE)

    assert tela["veredito"] == "nao-respondeu"
    assert tela["escada"] == []


def test_par_nao_ligado_tem_veredito_proprio():
    tela = fu.montar(MedicaoClient.SEM_CONFIGURACAO, None, HOJE)

    assert tela["veredito"] == "sem-configuracao"
    assert tela["escada"] == []


@respx.mock
def test_sem_coleta_e_um_estado_proprio_e_nao_uma_escada_de_zeros():
    _a_memoria_responde(_resposta(_passos(0, 0, 0, 0, 0, 0), coleta=(None, None)))
    desfecho, resposta = MedicaoClient().funil(
        dt.date(2026, 8, 28), dt.date(2026, 9, 26)
    )

    tela = fu.montar(desfecho, resposta, HOJE)

    assert tela["veredito"] == "sem-coleta"
    assert tela["escada"] == []


@respx.mock
def test_coleta_nula_inteira_tambem_e_sem_coleta_e_nao_memoria_fora_do_ar():
    corpo = _resposta(_passos(0, 0, 0, 0, 0, 0))
    corpo["coleta"] = None
    _a_memoria_responde(corpo)

    tela = fu.montar(*MedicaoClient().funil(HOJE, HOJE), HOJE)

    assert tela["veredito"] == "sem-coleta"


@respx.mock
def test_resposta_sem_o_campo_coleta_e_fora_do_contrato_e_nao_sem_coleta():
    corpo = _resposta(_passos(0, 0, 0, 0, 0, 0))
    del corpo["coleta"]
    _a_memoria_responde(corpo)

    desfecho, _ = MedicaoClient().funil(HOJE, HOJE)

    assert desfecho == MedicaoClient.NAO_RESPONDEU


@respx.mock
def test_zero_com_coleta_e_zero_de_verdade_e_aparece_como_numero():
    _a_memoria_responde(_resposta(_passos(3, 2, 0, 0, 0, 0)))
    desfecho, resposta = MedicaoClient().funil(
        dt.date(2026, 8, 28), dt.date(2026, 9, 26)
    )

    tela = fu.montar(desfecho, resposta, HOJE)

    assert tela["veredito"] == "medindo"
    assert _degrau(tela, "cta_checkout")["visitantes"] == 0
    assert _degrau(tela, "pedido_pago")["visitantes"] == 0


@respx.mock
def test_a_tela_com_a_memoria_fora_do_ar_diz_o_que_houve_e_o_que_fazer():
    cliente = _dentro()
    respx.get(FUNIL).mock(side_effect=httpx.ConnectError("recusou"))

    r = cliente.get(reverse("funil"))
    corpo = r.content.decode()

    assert r.status_code == 200
    assert "não respondeu" in corpo
    assert "não quer dizer que ninguém" in corpo
    assert "Recarregue" in corpo
    assert "<table" not in corpo


@respx.mock
def test_a_tela_sem_coleta_diz_que_nenhuma_visita_chegou():
    cliente = _dentro()
    _a_memoria_responde(_resposta(_passos(0, 0, 0, 0, 0, 0), coleta=(None, None)))

    corpo = cliente.get(reverse("funil")).content.decode()

    assert "ainda não chegou nenhuma visita medida" in corpo
    assert "<table" not in corpo


@respx.mock
def test_a_tela_com_zero_verdadeiro_mostra_a_escada_com_o_zero():
    cliente = _dentro()
    _a_memoria_responde(_resposta(_passos(3, 2, 0, 0, 0, 0)))

    corpo = cliente.get(reverse("funil")).content.decode()

    assert "<table" in corpo
    assert "ainda não chegou nenhuma visita medida" not in corpo
    assert '<td class="numero"><b>0</b></td>' in corpo


@respx.mock
def test_corpo_fora_do_contrato_vira_nao_respondeu_e_nunca_escada_vazia():
    _a_memoria_responde(_resposta(_passos(3, 2, 1)))  # faltam três degraus

    desfecho, resposta = MedicaoClient().funil(
        dt.date(2026, 8, 28), dt.date(2026, 9, 26)
    )

    assert desfecho == MedicaoClient.NAO_RESPONDEU
    assert resposta is None


@respx.mock
def test_visitantes_que_nao_sao_numero_viram_nao_respondeu():
    passos = _passos(3, 2, 1, 0, 0, 0)
    passos[0]["visitantes"] = "3"
    _a_memoria_responde(_resposta(passos))

    desfecho, _ = MedicaoClient().funil(dt.date(2026, 8, 28), dt.date(2026, 9, 26))

    assert desfecho == MedicaoClient.NAO_RESPONDEU


# ---------------------------------------------------------------------------
# 2. A taxa entre degraus
# ---------------------------------------------------------------------------


@respx.mock
def test_a_taxa_e_do_degrau_anterior_e_o_primeiro_nao_tem_taxa():
    _a_memoria_responde(_resposta(_passos(200, 50, 10, 4, 2, 1)))
    tela = fu.montar(*MedicaoClient().funil(HOJE, HOJE), HOJE)

    assert _degrau(tela, "pagina_vista")["taxa"] is None
    assert _degrau(tela, "secao_vista")["taxa"] == "25,0%"
    assert _degrau(tela, "cta_checkout")["taxa"] == "20,0%"
    assert _degrau(tela, "pedido_pago")["taxa"] == "50,0%"


@respx.mock
def test_degrau_anterior_vazio_nao_vira_zero_por_cento():
    _a_memoria_responde(_resposta(_passos(5, 0, 0, 0, 0, 0)))
    tela = fu.montar(*MedicaoClient().funil(HOJE, HOJE), HOJE)

    assert _degrau(tela, "secao_vista")["taxa"] == "0,0%"
    assert _degrau(tela, "cta_checkout")["taxa"] is None


@respx.mock
def test_a_tela_mostra_a_taxa_e_diz_sem_base_quando_nao_ha_de_onde_passar():
    cliente = _dentro()
    _a_memoria_responde(_resposta(_passos(8, 4, 0, 0, 0, 0)))

    corpo = cliente.get(reverse("funil")).content.decode()

    assert "50,0%" in corpo
    assert "sem base" in corpo


# ---------------------------------------------------------------------------
# 3. A janela escolhida é a perguntada
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "pedida, dias, desde",
    [("7", 7, "2026-09-20"), ("30", 30, "2026-08-28"), ("90", 90, "2026-06-29")],
)
@respx.mock
def test_a_janela_escolhida_vai_para_a_pergunta(pedida, dias, desde):
    cliente = _dentro()
    rota = _a_memoria_responde(_resposta(_passos(1, 1, 1, 0, 0, 0)))

    corpo = cliente.get(reverse("funil"), {"janela": pedida}).content.decode()

    url = str(rota.calls.last.request.url)
    assert f"?de={desde}&" in url
    assert "ate=2026-09-26" in url
    assert f'aria-current="page">{dias} dias</a>' in corpo


@respx.mock
def test_sem_escolha_a_janela_e_a_padrao():
    cliente = _dentro()
    rota = _a_memoria_responde(_resposta(_passos(1, 1, 1, 0, 0, 0)))

    cliente.get(reverse("funil"))

    assert "?de=2026-08-28&" in str(rota.calls.last.request.url)


@respx.mock
def test_janela_invalida_cai_na_padrao_e_a_tela_avisa():
    cliente = _dentro()
    rota = _a_memoria_responde(_resposta(_passos(1, 1, 1, 0, 0, 0)))

    corpo = cliente.get(reverse("funil"), {"janela": "365"}).content.decode()

    assert "?de=2026-08-28&" in str(rota.calls.last.request.url)
    assert "não existe" in corpo


# ---------------------------------------------------------------------------
# 4. Por dia
# ---------------------------------------------------------------------------


@respx.mock
def test_por_dia_comeca_no_primeiro_dia_medido_e_o_buraco_depois_e_zero():
    # guarda: services/admin/apps/core/funil.py:96
    _a_memoria_responde(
        _resposta(
            _passos(4, 3, 1, 0, 0, 0),
            por_dia=[
                ("2026-09-26", (1, 1, 0, 0, 0, 0)),
                ("2026-09-23", (3, 2, 1, 0, 0, 0)),
            ],
        )
    )
    desfecho, resposta = MedicaoClient().funil(
        dt.date(2026, 8, 28), dt.date(2026, 9, 26)
    )

    tela = fu.montar(desfecho, resposta, HOJE)

    assert [d["dia"] for d in tela["dias"]] == [
        dt.date(2026, 9, 26),
        dt.date(2026, 9, 25),
        dt.date(2026, 9, 24),
        dt.date(2026, 9, 23),
    ]
    assert tela["dias"][1]["visitantes"] == [0, 0, 0, 0, 0, 0]
    assert tela["dias"][3]["visitantes"] == [3, 2, 1, 0, 0, 0]


@respx.mock
def test_a_prova_da_visita_de_teste_aparece_inteira_na_tela():
    """A visita de teste do ensaio: uma pessoa abre, lê a oferta e clica."""
    cliente = _dentro()
    _a_memoria_responde(
        _resposta(
            _passos(1, 1, 1, 0, 0, 0),
            por_dia=[("2026-09-26", (1, 1, 1, 0, 0, 0))],
            coleta=("2026-09-26T19:10:00-03:00", "2026-09-26T19:11:30-03:00"),
        )
    )

    r = cliente.get(reverse("funil"), {"janela": "7"})
    corpo = r.content.decode()

    assert r.status_code == 200
    assert "<title>Placar | O funil · Meshcraft</title>" in corpo
    for _, nome in fu.PASSOS:
        assert nome in corpo
    assert corpo.count("100,0%") == 2
    assert "26/09/2026" in corpo
    # O texto desta tela, sem o CSS e os comentários do `base.html`.
    tela = corpo[corpo.index('class="envolucro"') : corpo.index("<footer")]
    for traco in ("—", "–", "―"):
        assert traco not in tela


# ---------------------------------------------------------------------------
# 5. O site e a porta
# ---------------------------------------------------------------------------


@respx.mock
def test_o_site_do_endereco_vai_na_pergunta(monkeypatch):
    monkeypatch.setenv("CATALOGO_API_URL", CATALOGO)
    monkeypatch.setenv("TOKEN_CATALOGO", "token-do-par-admin-catalogo")
    respx.get(f"{CATALOGO}/sites/by-host/testserver").mock(
        return_value=httpx.Response(200, json={"id": "meshcraft"})
    )
    cliente = _dentro()
    rota = _a_memoria_responde(_resposta(_passos(1, 1, 1, 0, 0, 0)))

    cliente.get(reverse("funil"))

    assert "site_id=meshcraft" in str(rota.calls.last.request.url)


@respx.mock
def test_sem_saber_o_site_a_tela_diz_que_conta_todos():
    cliente = _dentro()
    rota = _a_memoria_responde(_resposta(_passos(1, 1, 1, 0, 0, 0)))

    corpo = cliente.get(reverse("funil")).content.decode()

    assert "site_id" not in str(rota.calls.last.request.url)
    assert "todos os sites" in corpo


def test_sem_sessao_vai_para_o_login():
    r = Client().get(reverse("funil"))

    assert r.status_code == 302


@respx.mock
def test_sessao_fora_da_equipe_recebe_404():
    cliente = _dentro("estranho@exemplo.com")

    assert cliente.get(reverse("funil")).status_code == 404


@respx.mock
def test_o_placar_leva_ate_o_funil_em_um_clique():
    cliente = _dentro()
    respx.get(url__regex=rf"{METRICAS}/.*").mock(
        side_effect=httpx.ConnectError("recusou")
    )

    corpo = cliente.get(reverse("placar")).content.decode()

    assert reverse("funil") in corpo
