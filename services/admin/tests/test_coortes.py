"""As coortes (degrau 10 do plano do painel de gestão, §6.4).

O que cada grupo de guardas protege, e por que ele existe:

1. **"Não perguntei" nunca vira "ninguém entrou".** É a mesma razão da tela da
   confiança, no lugar onde ela mais dói: uma tabela de coortes com zeros em
   toda linha, com a memória fora do ar, diria que a escola não recebeu
   ninguém no ano. Zero é afirmação sobre o mundo; ausência de resposta não é.
2. **Os dois vocabulários de identidade nunca se somam.** Matrícula e pessoa
   são coisas diferentes (contrato da `metricas`, regra 7), e cruzá-las com o
   olho é o erro que esta tela existe para tornar impossível.
3. **O mês sai do dia que a memória já devolveu, sem reconverter fuso.** Ela
   grava o dia de São Paulo na recepção (`armadilhas/099`); aplicar fuso de
   novo deslocaria o dia uma segunda vez e trocaria o grupo de quem entrou na
   virada do mês.
4. **A tabela não inventa mês antes do primeiro fato, e não engole buraco
   depois dele.** Antes do primeiro fato, zero seria mentira; depois dele, o
   buraco é informação.
5. **Nada some.** Conquista com dia ilegível vira contagem própria, e tipo que
   esta tela ainda não sabe nomear vira nota, nunca silêncio.
6. **As três dimensões sem fonte aparecem escritas, com o motivo.** Turma,
   canal e a foto ao longo do tempo. Um zero mudo no lugar delas seria pior
   que a ausência, porque pareceria medição.
7. **A janela cabe na porta.** A memória recusa intervalo maior que 366 dias;
   uma janela que estourasse viraria "não respondeu" em algum dia do calendário
   e em nenhum outro.
"""

from __future__ import annotations

import datetime as dt

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.core import coortes as co
from apps.core.clients import MedicaoClient

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
METRICAS = "http://metricas:8000/api/metricas"
CONTAGENS = f"{METRICAS}/marcos/contagens"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"

HOJE = dt.date(2026, 9, 20)


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    monkeypatch.setenv("METRICAS_API_URL", METRICAS)
    monkeypatch.setenv("METRICAS_API_TOKEN", "token-do-par-admin-metricas")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"
    monkeypatch.setattr(co.timezone, "localdate", lambda: HOJE)


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


def _conquista(sujeito: str, tipo: str, dias: list[tuple[str, int]]) -> dict:
    return {
        "sujeito_tipo": sujeito,
        "tipo": tipo,
        "total": sum(q for _, q in dias),
        "por_dia": [{"dia": dia, "quantidade": q} for dia, q in dias],
    }


def _a_memoria_responde(conquistas: list) -> None:
    respx.get(CONTAGENS).mock(
        return_value=httpx.Response(
            200,
            json={
                "sujeito_tipo": "",
                "tipo": "",
                "de": "2025-10-01",
                "ate": "2026-09-20",
                "conquistas": conquistas,
            },
        )
    )


def _linha(tela: dict, chave: str) -> dict:
    return next(m for m in tela["meses"] if m["chave"] == chave)


# ---------------------------------------------------------------------------
# 1. "Não perguntei" nunca vira "ninguém entrou"
# ---------------------------------------------------------------------------


def test_memoria_fora_do_ar_nao_vira_tabela_de_zeros():
    tela = co.montar(MedicaoClient.NAO_RESPONDEU, None, HOJE)

    assert tela["veredito"] == "nao-respondeu"
    assert tela["meses"] == []


def test_par_nao_ligado_tem_veredito_proprio_e_nao_se_confunde_com_vazio():
    tela = co.montar(MedicaoClient.SEM_CONFIGURACAO, None, HOJE)

    assert tela["veredito"] == "sem-configuracao"
    assert tela["veredito"] != "vazia"


def test_memoria_respondeu_e_nao_ha_nada_e_um_terceiro_estado():
    tela = co.montar(MedicaoClient.OK, [], HOJE)

    assert tela["veredito"] == "vazia"
    assert tela["meses"] == []


@respx.mock
def test_a_tela_diz_que_nao_perguntou_em_vez_de_mostrar_a_escola_vazia():
    cliente = _dentro()
    respx.get(CONTAGENS).mock(side_effect=httpx.ConnectError("recusou"))

    corpo = cliente.get(reverse("coortes")).content.decode()

    assert "não consegui perguntar" in corpo
    assert "Ninguém entrou" not in corpo


# ---------------------------------------------------------------------------
# 2. Os dois vocabulários de identidade nunca se somam
# ---------------------------------------------------------------------------


def test_matricula_e_pessoa_ficam_em_colunas_separadas_e_nunca_no_mesmo_total():
    tela = co.montar(
        MedicaoClient.OK,
        [
            _conquista("matricula", "virou-aluno-comprando", [("2026-09-10", 3)]),
            _conquista("pessoa", "escreveu-no-forum", [("2026-09-10", 7)]),
        ],
        HOJE,
    )
    setembro = _linha(tela, "2026-09")

    assert setembro["matricula"] == [0, 3, 0], "pediu, comprando, liberado"
    assert setembro["pessoa"] == [0, 7, 0], "chegou, escreveu, ajudou"
    assert setembro["entraram"] == 3, "as 7 do fórum são pessoas, e não entradas"
    assert tela["entraram_no_total"] == 3


def test_pedir_entrada_nao_conta_como_ter_entrado():
    tela = co.montar(
        MedicaoClient.OK,
        [
            _conquista("matricula", "pediu-entrada", [("2026-09-10", 9)]),
            _conquista("matricula", "virou-aluno-liberado", [("2026-09-11", 2)]),
        ],
        HOJE,
    )

    assert _linha(tela, "2026-09")["entraram"] == 2


def test_comprou_e_foi_liberado_somam_a_entrada_e_continuam_visiveis_separados():
    tela = co.montar(
        MedicaoClient.OK,
        [
            _conquista("matricula", "virou-aluno-comprando", [("2026-09-02", 4)]),
            _conquista("matricula", "virou-aluno-liberado", [("2026-09-03", 6)]),
        ],
        HOJE,
    )
    setembro = _linha(tela, "2026-09")

    assert setembro["matricula"] == [0, 4, 6]
    assert setembro["entraram"] == 10


# ---------------------------------------------------------------------------
# 3. O mês sai do dia da memória, sem reconverter fuso
# ---------------------------------------------------------------------------


def test_o_dia_da_virada_do_mes_fica_no_mes_que_a_memoria_gravou():
    # 30/09 é dia de São Paulo, gravado na recepção. Reaplicar fuso o jogaria
    # em outubro, e a pessoa mudaria de grupo sem erro em lugar nenhum (099).
    tela = co.montar(
        MedicaoClient.OK,
        [_conquista("matricula", "virou-aluno-comprando", [("2026-08-31", 1)])],
        HOJE,
    )

    assert _linha(tela, "2026-08")["entraram"] == 1
    assert _linha(tela, "2026-09")["entraram"] == 0


def test_o_mes_corrente_vem_marcado_como_ainda_aberto():
    tela = co.montar(
        MedicaoClient.OK,
        [_conquista("matricula", "virou-aluno-comprando", [("2026-08-10", 1)])],
        HOJE,
    )

    assert _linha(tela, "2026-09")["aberto"] is True
    assert _linha(tela, "2026-08")["aberto"] is False


def test_o_nome_do_mes_sai_em_portugues():
    assert co.nome_do_mes("2026-03") == "março de 2026"
    assert co.nome_do_mes("2026-12") == "dezembro de 2026"


# ---------------------------------------------------------------------------
# 4. Nem mês inventado antes do primeiro fato, nem buraco engolido depois
# ---------------------------------------------------------------------------


def test_a_tabela_comeca_no_primeiro_mes_com_conquista_e_nao_antes():
    tela = co.montar(
        MedicaoClient.OK,
        [_conquista("pessoa", "entrou-no-site", [("2026-07-15", 5)])],
        HOJE,
    )

    assert [m["chave"] for m in tela["meses"]] == ["2026-09", "2026-08", "2026-07"]


def test_mes_sem_nada_no_meio_da_serie_vira_zero_e_nao_desaparece():
    tela = co.montar(
        MedicaoClient.OK,
        [
            _conquista(
                "matricula",
                "virou-aluno-comprando",
                [("2026-07-15", 5), ("2026-09-02", 1)],
            )
        ],
        HOJE,
    )

    assert [m["chave"] for m in tela["meses"]] == ["2026-09", "2026-08", "2026-07"]
    assert _linha(tela, "2026-08")["entraram"] == 0


def test_o_mes_mais_novo_vem_em_cima():
    tela = co.montar(
        MedicaoClient.OK,
        [_conquista("pessoa", "entrou-no-site", [("2026-06-01", 1)])],
        HOJE,
    )

    assert tela["meses"][0]["chave"] == "2026-09"


# ---------------------------------------------------------------------------
# 5. Nada some
# ---------------------------------------------------------------------------


def test_conquista_com_dia_ilegivel_e_contada_a_parte_e_nao_descartada():
    tela = co.montar(
        MedicaoClient.OK,
        [
            _conquista(
                "matricula",
                "virou-aluno-comprando",
                [("2026-09-10", 2), ("dia-torto", 3)],
            )
        ],
        HOJE,
    )

    assert tela["sem_dia"] == 3
    assert _linha(tela, "2026-09")["entraram"] == 2


def test_conquista_que_esta_tela_ainda_nao_sabe_nomear_vira_nota():
    tela = co.montar(
        MedicaoClient.OK,
        [
            _conquista("matricula", "virou-aluno-comprando", [("2026-09-10", 1)]),
            _conquista("pessoa", "terminou-o-curso", [("2026-09-11", 4)]),
        ],
        HOJE,
    )

    assert tela["novos"] == [{"tipo": "terminou-o-curso", "total": 4}]
    assert _linha(tela, "2026-09")["entraram"] == 1, "a nova não entra numa coluna"


@respx.mock
def test_a_tela_mostra_a_conquista_que_ainda_nao_tem_coluna():
    cliente = _dentro()
    _a_memoria_responde([_conquista("pessoa", "terminou-o-curso", [("2026-09-11", 4)])])

    corpo = cliente.get(reverse("coortes")).content.decode()

    assert "terminou-o-curso" in corpo


# ---------------------------------------------------------------------------
# 6. As três dimensões sem fonte aparecem escritas, com o motivo
# ---------------------------------------------------------------------------


@respx.mock
def test_turma_canal_e_a_foto_no_tempo_aparecem_com_o_motivo_e_sem_numero():
    cliente = _dentro()
    _a_memoria_responde(
        [_conquista("matricula", "virou-aluno-comprando", [("2026-09-10", 1)])]
    )

    corpo = cliente.get(reverse("coortes")).content.decode()

    assert "Por turma" in corpo
    assert "Por canal" in corpo
    assert "checkout" in corpo, "o motivo do canal é o checkout congelado"
    assert "Rito de Contrato" in corpo, "o motivo da foto é contrato congelado"


@respx.mock
def test_a_tela_diz_que_a_contagem_e_da_plataforma_inteira():
    cliente = _dentro()
    _a_memoria_responde(
        [_conquista("matricula", "virou-aluno-comprando", [("2026-09-10", 1)])]
    )

    corpo = cliente.get(reverse("coortes")).content.decode()

    assert "plataforma inteira" in corpo


@respx.mock
def test_o_estado_vazio_explica_o_que_e_uma_coorte_em_vez_de_uma_tabela_em_branco():
    cliente = _dentro()
    _a_memoria_responde([])

    corpo = cliente.get(reverse("coortes")).content.decode()

    assert "<table" not in corpo
    assert "primeira coorte" in corpo


@respx.mock
def test_o_placar_leva_ate_as_coortes_em_um_clique():
    cliente = _dentro()
    respx.get(CONTAGENS).mock(side_effect=httpx.ConnectError("recusou"))

    corpo = cliente.get(reverse("placar")).content.decode()

    assert reverse("coortes") in corpo


# ---------------------------------------------------------------------------
# 7. A janela cabe na porta da memória
# ---------------------------------------------------------------------------


def test_a_janela_sao_doze_meses_inteiros_terminando_hoje():
    de, ate = co.janela(dt.date(2026, 9, 20))

    assert de == dt.date(2025, 10, 1)
    assert ate == dt.date(2026, 9, 20)


def test_a_janela_nunca_estoura_o_teto_de_366_dias_da_memoria():
    # O teto é `JANELA_MAXIMA_EM_DIAS` da `metricas`. Varrer o calendário é o
    # único jeito honesto de provar isto: o pior caso mora num 29 de fevereiro
    # que ninguém escolheria à mão.
    dia = dt.date(2026, 1, 1)
    while dia < dt.date(2032, 1, 1):
        de, ate = co.janela(dia)
        assert (ate - de).days + 1 <= 366, f"a janela de {dia} estourou o teto"
        dia += dt.timedelta(days=1)


@respx.mock
def test_o_cliente_pede_a_janela_que_a_tela_calculou():
    cliente = _dentro()
    rota = respx.get(CONTAGENS).mock(
        return_value=httpx.Response(
            200,
            json={
                "sujeito_tipo": "",
                "tipo": "",
                "de": "2025-10-01",
                "ate": "2026-09-20",
                "conquistas": [],
            },
        )
    )

    cliente.get(reverse("coortes"))

    pedido = rota.calls.last.request
    assert "de=2025-10-01" in str(pedido.url)
    assert "ate=2026-09-20" in str(pedido.url)


@respx.mock
def test_corpo_fora_do_contrato_vira_nao_respondeu_e_nunca_tabela_vazia():
    respx.get(CONTAGENS).mock(
        return_value=httpx.Response(200, json={"conquistas": "isto não é lista"})
    )

    desfecho, linhas = MedicaoClient().conquistas(
        dt.date(2025, 10, 1), dt.date(2026, 9, 20)
    )

    assert desfecho == MedicaoClient.NAO_RESPONDEU
    assert linhas is None
