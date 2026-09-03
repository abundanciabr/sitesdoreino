"""O placar, `/admin/placar/` (03/09/2026): o andar zero do painel de gestão.

O que estes guardas protegem (plano: `docs/decisoes/PLANO-PAINEL-DE-GESTAO.md`):

1. **Número sem cartão não aparece.** Cartão ausente ou inválido ⇒ a página
   abre, diz o que faltou, e o número da meta NÃO está no HTML. É a regra
   fail-closed do §2, e o caso que DEVE reprovar está aqui.
2. **Os cartões do repositório são válidos.** Quem escrever um cartão torto
   descobre no PR, não na tela do mantenedor.
3. **"Não sei" nunca vira zero.** A `alunos` fora do ar ⇒ "não consigo contar",
   e nenhum "0 alunos" na tela.
4. **A conta do veredito é a que o plano descreve**, e não outra: linha reta
   da partida ao alvo, sem índice.
5. **O par sem fonte se declara**, em vez de mostrar número inventado.
6. **A porta continua sendo a porta**, e a visão geral leva até aqui.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.core import placar

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"

ALUNOS = "http://alunos:8000/api/alunos"
FILA = f"{ALUNOS}/pre-matriculas"
ALUNOS_LISTA = f"{ALUNOS}/matriculas"


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


def _a_escola_responde(ativos: int, pausados: int = 0):
    """A `alunos` respondendo: `ativos` matrículas ativas e `pausados` suspensas."""
    matriculas = [{"status": "ativa"} for _ in range(ativos)] + [
        {"status": "suspensa"} for _ in range(pausados)
    ]
    respx.get(FILA, params={"status": "aguardando"}).mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(FILA, params={"status": "recusada"}).mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(ALUNOS_LISTA).mock(return_value=httpx.Response(200, json=matriculas))


def _a_escola_caiu():
    respx.get(FILA).mock(side_effect=httpx.ConnectError("recusou"))
    respx.get(ALUNOS_LISTA).mock(side_effect=httpx.ConnectError("recusou"))


# ---------------------------------------------------------------- os cartões


def test_os_cartoes_do_repositorio_sao_validos():
    """Cartão torto reprova aqui, não na tela do mantenedor."""
    pasta = placar.diretorio_dos_cartoes()
    assert pasta is not None, (
        "a pasta painel/cartoes/ não foi encontrada — em produção ela vem em "
        "painel_embutido/, num checkout em painel/. Sem ela o placar abre sem número."
    )
    for arquivo in sorted(pasta.glob("*.json")):
        cartao, problemas = placar.ler_cartao(arquivo.stem, pasta)
        assert cartao is not None, f"{arquivo.name}: {problemas}"


def test_a_meta_e_o_par_apontam_um_para_o_outro():
    pasta = placar.diretorio_dos_cartoes()
    meta, _ = placar.ler_cartao(placar.CARTAO_DA_META, pasta)
    par, _ = placar.ler_cartao(placar.CARTAO_DO_PAR, pasta)
    assert meta["par"] == placar.CARTAO_DO_PAR
    assert par["par"] == placar.CARTAO_DA_META
    assert meta["andar"] == 0 and par["andar"] == 0


@pytest.mark.parametrize(
    "defeito, trecho",
    [
        ({"par": None}, "par"),
        ({"tipo": "composto"}, "tipo"),
        ({"andar": "0"}, "andar"),
        ({"componentes": ["a", "b"]}, "composto"),
        ({"fonte": None}, "sem_fonte_porque"),
        ({"versao": "1"}, "versao"),
        ({"alvo": 200}, "os quatro juntos"),
        (
            {
                "alvo": 200,
                "ate": "2026-01-01",
                "partida": 10,
                "partida_em": "2026-06-01",
            },
            "depois",
        ),
    ],
)
def test_o_validador_reprova_cada_defeito(defeito, trecho):
    """O caso que DEVE reprovar, um por regra do plano (§2)."""
    base = json.loads(
        (
            Path(placar.diretorio_dos_cartoes()) / f"{placar.CARTAO_DA_META}.json"
        ).read_text(encoding="utf-8")
    )
    assert not placar.validar(base)
    torto = {**base, **defeito}
    problemas = placar.validar(torto)
    assert problemas, f"o validador engoliu {defeito}"
    assert any(trecho in p for p in problemas), problemas


# ------------------------------------------------------------------- a conta


HOJE = dt.date(2026, 10, 1)
META = {
    "alvo": 200,
    "ate": "2026-11-30",
    "partida": 100,
    "partida_em": "2026-10-01",
}


def test_sem_alvo_o_veredito_e_aguardar_o_mantenedor():
    r = placar.calcular_placar({"alvo": None}, 42, HOJE)
    assert r["veredito"] == "sem-alvo"
    assert r["x"] == 42


def test_sem_contagem_o_veredito_e_nao_consigo_contar():
    r = placar.calcular_placar(META, None, HOJE)
    assert r["veredito"] == "nao-consigo-contar"
    assert r["x"] is None


def test_a_linha_reta_decide_ganhando_e_perdendo():
    # 30 dos 60 dias passaram: esperado = 100 + 100 * 30/60 = 150.
    meio = dt.date(2026, 10, 31)
    assert placar.calcular_placar(META, 150, meio)["veredito"] == "ganhando"
    assert placar.calcular_placar(META, 149, meio)["veredito"] == "perdendo"
    r = placar.calcular_placar(META, 120, meio)
    assert r["esperado_hoje"] == 150
    assert r["distancia"] == 80
    assert r["dias_restantes"] == 30
    assert r["ritmo_por_semana"] == pytest.approx(80 / (30 / 7), abs=0.1)


def test_no_dia_da_partida_qualquer_x_igual_a_partida_esta_ganhando():
    assert placar.calcular_placar(META, 100, HOJE)["veredito"] == "ganhando"


def test_meta_cumprida_e_prazo_vencido():
    assert placar.calcular_placar(META, 200, HOJE)["veredito"] == "cumprida"
    depois = dt.date(2026, 12, 15)
    assert placar.calcular_placar(META, 199, depois)["veredito"] == "vencida"
    assert placar.calcular_placar(META, 250, depois)["veredito"] == "cumprida"


# -------------------------------------------------------------------- a tela


@respx.mock
def test_a_pagina_mostra_o_numero_medido_e_pede_o_alvo():
    _a_escola_responde(ativos=37, pausados=2)
    resposta = _dentro().get(reverse("placar"))
    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert 'class="hero-numero">37<' in html
    assert "aguardando você" in html
    assert "Sem dados ainda" in html, "o par sem fonte precisa se declarar"


@respx.mock
def test_a_escola_fora_do_ar_nao_vira_zero():
    _a_escola_caiu()
    html = _dentro().get(reverse("placar")).content.decode()
    assert "Não consigo contar agora" in html
    assert 'class="hero-numero">0<' not in html


@respx.mock
def test_sem_cartao_valido_o_numero_nao_aparece(tmp_path, monkeypatch):
    """A regra fail-closed do plano (§2), medida: cartão inválido, número ausente."""
    pasta = tmp_path / "cartoes"
    pasta.mkdir()
    torto = {"nome": placar.CARTAO_DA_META, "tipo": "resultado"}
    (pasta / f"{placar.CARTAO_DA_META}.json").write_text(
        json.dumps(torto), encoding="utf-8"
    )
    monkeypatch.setattr(placar, "diretorio_dos_cartoes", lambda: pasta)
    _a_escola_responde(ativos=37)
    resposta = _dentro().get(reverse("placar"))
    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert "falta o cartão" in html
    assert 'class="hero-numero"' not in html, "número desenhado sem cartão válido"
    assert not respx.calls.call_count or all(
        "alunos:8000" not in str(c.request.url) for c in respx.calls
    ), "sem cartão válido a tela nem pergunta à alunos: número que não vai aparecer não se busca"


@respx.mock
def test_a_visao_geral_leva_ate_o_placar():
    _a_escola_responde(ativos=1)
    html = _dentro().get(reverse("visao_geral")).content.decode()
    assert reverse("placar") in html


@respx.mock
def test_sem_cracha_a_pagina_nao_abre():
    respx.get(SESSAO).mock(
        return_value=httpx.Response(200, json={"autenticado": False})
    )
    assert Client().get(reverse("placar")).status_code != 200
