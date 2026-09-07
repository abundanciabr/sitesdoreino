"""A rede de talentos, `/admin/placar/talentos/` (degrau 17 do plano do painel).

O que cada grupo de guardas protege, e por que ele existe:

1. **Ausência de contagem nunca vira zero** (`armadilhas/271`). São quatro
   estados diferentes na tela, e o teste separa os quatro: "nunca contado" (a
   escola não contou), "não consigo olhar" (o livro não chegou), "não consigo
   contar" (a célula `alunos` não respondeu) e "sem dados" (o cartão não tem
   fonte nenhuma). Uma escola sem estúdio parceiro nenhum tem de ver a
   pergunta sem resposta, e nunca um zero que parece medição.
2. **A contagem digitada é registro do livro, não tabela.** O pedido que a
   tela monta pede uma `medicao` com o campo `foto`, e a linha que ele escreve
   passa no MESMO formato que `painel/logica.js` impõe ao livro. Um pedido que
   produzisse uma linha torta só seria descoberto pelo robô, horas depois.
3. **A foto que vai ao livro nasce completa.** O bloco "o que mudou" da capa
   compara a foto mais recente do livro com o que o placar mostra agora. Uma
   foto só com as três contagens da rede seria a mais recente sem ter os
   outros números, e o placar inteiro apareceria como "sem par" na segunda
   seguinte. O guarda mede que o placar de hoje viaja junto.
4. **Campo vazio não é zero.** Contar uma etapa hoje e outra na semana que vem
   é o uso normal desta tela; gravar zero pelo campo em branco apagaria uma
   contagem verdadeira na foto seguinte.
5. **Entrada inválida diz o que aconteceu e o que fazer**, e não grava nada.
6. **A tela não escreve em lugar nenhum**: o POST devolve texto, e todas as
   chamadas que saem daqui são leituras.
7. **O laço tem os seis passos do documento, na ordem** (Scale OS 2 §45), e a
   última contagem de cada etapa vence a anterior, com a idade dita.
"""

from __future__ import annotations

import datetime as dt

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.core import placar, talentos
from apps.core.mudancas import ler_foto

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"
ALUNOS = "http://alunos:8000/api/alunos"
FILA = f"{ALUNOS}/pre-matriculas"
ALUNOS_LISTA = f"{ALUNOS}/matriculas"
HOJE = dt.date(2026, 9, 21)

TALENTOS = "alunos-selecionados-para-a-rede"
ESTUDIOS = "estudios-parceiros"
ENCAIXES = "encaixes-com-estudio"


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    monkeypatch.setenv("ALUNOS_API_URL", ALUNOS)
    monkeypatch.setenv("ALUNOS_API_TOKEN", "token-do-par-admin-alunos")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"
    monkeypatch.setattr(placar.timezone, "localdate", lambda: HOJE)
    monkeypatch.setattr(talentos.timezone, "localdate", lambda: HOJE)


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


def _a_escola_responde():
    respx.get(FILA, params={"status": "aguardando"}).mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(FILA, params={"status": "recusada"}).mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(ALUNOS_LISTA).mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "status": "ativa",
                    "origem": "liberado",
                    "criada_em": "2026-09-10T12:00:00-03:00",
                    "virou_aluno_em": "2026-09-11T12:00:00-03:00",
                }
            ],
        )
    )


def _medicao(quando: str, foto: str, arquivo: str = "um-registro") -> dict:
    return {"arquivo": arquivo, "tipo": "medicao", "quando": quando, "foto": foto}


def _passo(laco: dict, chave: str) -> dict:
    return next(p for p in laco["passos"] if p["chave"] == chave)


# ---------------------------------------------------------------------------
# 1. Ausência de contagem nunca vira zero
# ---------------------------------------------------------------------------


def test_nunca_contado_nao_e_zero():
    laco = talentos.montar([], 133, HOJE)

    for chave in ("talentos", "estudios", "encaixes"):
        assert _passo(laco, chave)["estado"] == "nunca-contado"
        assert _passo(laco, chave)["valor"] is None
    assert laco["nunca_contadas"] == 3


def test_livro_ausente_e_outra_coisa_de_nenhuma_contagem():
    laco = talentos.montar(None, 133, HOJE)

    assert laco["livro_ausente"] is True
    assert _passo(laco, "estudios")["estado"] == "nao-consigo-olhar"
    assert _passo(laco, "estudios")["valor"] is None


def test_a_escola_sem_resposta_nao_vira_escola_vazia():
    laco = talentos.montar([], None, HOJE)

    assert _passo(laco, "alunas")["estado"] == "nao-medi"
    assert _passo(laco, "alunas")["valor"] is None


def test_a_etapa_sem_fonte_diz_o_motivo_escrito_no_cartao():
    laco = talentos.montar([], 133, HOJE)

    resultados = _passo(laco, "resultados")
    assert resultados["estado"] == "sem-fonte"
    assert resultados["cartao_lido"]["sem_fonte_porque"]


def test_zero_contado_e_zero_e_aparece_medido():
    laco = talentos.montar([_medicao("2026-09-20", f"{ESTUDIOS}=0")], 133, HOJE)

    assert _passo(laco, "estudios")["estado"] == "medido"
    assert _passo(laco, "estudios")["valor"] == 0


@respx.mock
def test_a_tela_diz_nunca_contado_em_vez_de_mostrar_zero():
    _a_escola_responde()

    html = _dentro().get(reverse("talentos")).content.decode()

    assert "nunca contado" in html
    assert "Ninguém contou esta etapa ainda" in html
    assert "Primeira vez aqui" in html, "o primeiro uso tem texto próprio"


def test_sem_cartao_a_etapa_nao_mostra_numero_nenhum(tmp_path):
    """A lei do plano (§2): número sem cartão não aparece em tela nenhuma."""
    laco = talentos.montar([], 133, HOJE, pasta=tmp_path)

    for passo in laco["passos"]:
        assert passo["estado"] == "sem-cartao"
        assert passo["valor"] is None
        assert passo["problemas"]


# ---------------------------------------------------------------------------
# 2. A contagem digitada é registro do livro, não tabela
# ---------------------------------------------------------------------------


def test_o_pedido_pede_uma_medicao_com_o_campo_foto():
    texto = talentos.montar_o_pedido({TALENTOS: 4}, HOJE)

    assert "21/09/2026" in texto
    assert "tipo `medicao`" in texto
    assert "autoridade: mantenedor" in texto
    assert f'foto: "{TALENTOS}=4"' in texto
    assert "painel/registros/" in texto


def test_a_linha_da_foto_passa_no_formato_que_o_livro_exige():
    texto = talentos.montar_o_pedido({TALENTOS: 4, ESTUDIOS: 2, ENCAIXES: 1}, HOJE)
    linha = texto.split('foto: "')[1].split('"')[0]

    assert ler_foto(linha) == {TALENTOS: 4, ESTUDIOS: 2, ENCAIXES: 1}


def test_sem_contagem_nenhuma_nao_ha_pedido():
    assert talentos.montar_o_pedido({}, HOJE) is None


# ---------------------------------------------------------------------------
# 3. A foto que vai ao livro nasce completa
# ---------------------------------------------------------------------------


def test_o_pedido_leva_o_placar_junto_para_a_foto_nao_nascer_pela_metade():
    texto = talentos.montar_o_pedido(
        {ESTUDIOS: 2}, HOJE, "compras-no-ciclo=17; compras-no-mes=9"
    )
    linha = texto.split('foto: "')[1].split('"')[0]

    assert ler_foto(linha) == {
        "compras-no-ciclo": 17,
        "compras-no-mes": 9,
        ESTUDIOS: 2,
    }


def test_a_contagem_digitada_vence_o_mesmo_nome_vindo_do_placar():
    texto = talentos.montar_o_pedido({ESTUDIOS: 5}, HOJE, f"{ESTUDIOS}=2")
    linha = texto.split('foto: "')[1].split('"')[0]

    assert ler_foto(linha) == {ESTUDIOS: 5}


# ---------------------------------------------------------------------------
# 4 e 5. Campo vazio não é zero; entrada inválida é recusada em português
# ---------------------------------------------------------------------------


def test_campo_vazio_nao_e_zero():
    contagens, recusas = talentos.ler_as_contagens(
        {"talentos": "4", "estudios": "", "encaixes": "   "}
    )

    assert contagens == {TALENTOS: 4}
    assert recusas == []


def test_zero_digitado_entra_como_zero():
    contagens, recusas = talentos.ler_as_contagens({"estudios": "0"})

    assert contagens == {ESTUDIOS: 0}
    assert recusas == []


def test_texto_no_lugar_do_numero_e_recusado_e_nada_entra():
    contagens, recusas = talentos.ler_as_contagens({"estudios": "uns três"})

    assert contagens == {}
    assert len(recusas) == 1
    assert "uns três" in recusas[0] and "número inteiro" in recusas[0]


def test_contagem_negativa_e_recusada():
    contagens, recusas = talentos.ler_as_contagens({"encaixes": "-2"})

    assert contagens == {}
    assert "não pode ser negativa" in recusas[0]


@respx.mock
def test_a_tela_devolve_a_recusa_e_nao_monta_pedido():
    _a_escola_responde()

    html = _dentro().post(reverse("talentos"), {"estudios": "dois"}).content.decode()

    assert "Não gravei nada" in html
    assert "O pedido para o robô" not in html


# ---------------------------------------------------------------------------
# 6. A tela não escreve em lugar nenhum
# ---------------------------------------------------------------------------


@respx.mock
def test_o_post_devolve_o_pedido_e_so_le():
    _a_escola_responde()

    resposta = _dentro().post(reverse("talentos"), {"talentos": "4", "estudios": "2"})

    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert "O pedido para o robô" in html
    assert f"{TALENTOS}=4" in html
    assert all(c.request.method == "GET" for c in respx.calls), "a rede só lê"


@respx.mock
def test_o_post_vazio_diz_que_nao_ha_o_que_pedir():
    _a_escola_responde()

    html = _dentro().post(reverse("talentos"), {}).content.decode()

    assert "Nada para pedir" in html


@respx.mock
def test_sem_cracha_a_pagina_nao_abre():
    respx.get(SESSAO).mock(
        return_value=httpx.Response(200, json={"autenticado": False})
    )

    assert Client().get(reverse("talentos")).status_code != 200


@respx.mock
def test_o_placar_leva_ate_a_rede_de_talentos():
    _a_escola_responde()

    html = _dentro().get(reverse("placar")).content.decode()

    assert reverse("talentos") in html


# ---------------------------------------------------------------------------
# 7. O laço tem os seis passos do documento, e a última contagem vence
# ---------------------------------------------------------------------------


def test_o_laco_tem_os_seis_passos_na_ordem_do_documento():
    laco = talentos.montar([], 133, HOJE)

    assert [p["chave"] for p in laco["passos"]] == [
        "alunas",
        "talentos",
        "estudios",
        "encaixes",
        "resultados",
        "valor",
    ]


def test_a_contagem_mais_recente_vence_a_anterior():
    registros = [
        _medicao("2026-09-01", f"{ESTUDIOS}=1", "antigo"),
        _medicao("2026-09-18", f"{ESTUDIOS}=3", "novo"),
    ]

    laco = talentos.montar(registros, 133, HOJE)

    assert _passo(laco, "estudios")["valor"] == 3
    assert _passo(laco, "estudios")["contado_em"] == dt.date(2026, 9, 18)
    assert _passo(laco, "estudios")["dias"] == 3


def test_a_contagem_velha_e_dita_como_velha():
    laco = talentos.montar([_medicao("2026-07-01", f"{ESTUDIOS}=3")], 133, HOJE)

    assert _passo(laco, "estudios")["velha"] is True


def test_a_contagem_dentro_do_prazo_do_cartao_nao_e_velha():
    laco = talentos.montar([_medicao("2026-09-18", f"{ESTUDIOS}=3")], 133, HOJE)

    assert _passo(laco, "estudios")["velha"] is False


def test_uma_foto_sem_a_rede_nao_apaga_a_contagem_anterior():
    registros = [
        _medicao("2026-09-01", f"{ESTUDIOS}=3", "a-contagem"),
        _medicao("2026-09-20", "compras-no-ciclo=17", "a-foto-da-semana"),
    ]

    laco = talentos.montar(registros, 133, HOJE)

    assert _passo(laco, "estudios")["valor"] == 3
