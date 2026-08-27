"""A dívida do livro na TELA do dono — o segundo remédio, medido de fora.

O primeiro remédio (`ci/divida_do_livro.py`) impede o esquecimento na porta do
merge. Este arquivo guarda o outro: **fazer o esquecimento aparecer** quando o
primeiro falhar, for contornado, ou ainda não tiver mordido (existe uma folga de
90 minutos, e uma sessão pode terminar dentro dela).

As três coisas que este arquivo existe para impedir, e todas já aconteceram em
algum sistema deste repositório:

1. **A faixa dizer "está tudo contado" quando não sabe.** Falha de rede virando
   zero é a mentira mais cara possível aqui — o painel afirmando completude
   justamente quando perdeu a capacidade de verificar.
2. **A medição derrubar o painel.** Uma medição auxiliar não pode transformar o
   painel inteiro em erro; ela responde 200 com `erro` dentro.
3. **A faixa se desligar em silêncio.** Se o HTML parar de pedir a medição,
   nenhum teste de servidor notaria: a rota continuaria verde, respondendo para
   ninguém. Por isso há um guarda sobre o próprio HTML.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
import respx
from django.test import Client

from apps.core import divida as modulo_divida

BASE = "http://identidade:8000/interno"
SESSAO = f"{BASE}/sessao/completa"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"
API = "https://api.github.com"

PAINEL_NO_REPO = Path(__file__).resolve().parents[3] / "painel"


@pytest.fixture(autouse=True)
def env_e_cache_limpo(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", BASE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"
    # O cache é de módulo: sem limpar, o primeiro teste decidiria o resultado
    # de todos os outros — e a suíte passaria medindo uma coisa só.
    modulo_divida._cache["quando"] = 0.0
    modulo_divida._cache["resposta"] = None


def _dentro() -> Client:
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "id-opaco-123",
                "nome_exibido": "Dono",
                "email": DONO,
            },
        )
    )
    cliente = Client()
    cliente.defaults["HTTP_COOKIE"] = COOKIE
    return cliente


def _ha_horas(horas: int) -> str:
    """Um instante do passado, ancorado no relógio de AGORA.

    Datas cravadas em string não servem aqui: a regra compara com o relógio
    real (folga de 90 min) e com um marco zero fixo. Um teste com data cravada
    ou passa por acaso hoje e falha amanhã, ou — pior — fica verde por vacuidade
    porque a data escolhida caiu fora da janela e nada foi medido.
    """
    return (
        (datetime.now(timezone.utc) - timedelta(hours=horas))
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


@pytest.fixture
def cobranca_ja_valia(monkeypatch):
    """Puxa o marco zero para trás, para o passado do teste ser cobrável.

    Em produção o marco existe para não inventar 17 devedores no histórico
    (ver `INICIO_DA_COBRANCA`). Aqui ele só atrapalharia a medição do
    comportamento — o que se quer provar é a regra, não a data de estreia dela.
    """
    import divida_do_livro

    monkeypatch.setattr(
        divida_do_livro,
        "INICIO_DA_COBRANCA",
        datetime(2020, 1, 1, tzinfo=timezone.utc),
    )


def _pr(numero: int, quando: str, titulo="trabalho"):
    return {
        "number": numero,
        "title": titulo,
        "merged_at": quando,
        "state": "closed",
    }


# ------------------------------------------------------------------- a porta


def test_a_medicao_esta_atras_da_porta():
    """Ela conta o que aconteceu no projeto — não é rota pública."""
    resposta = Client().get("/painel/divida.json")
    assert resposta.status_code == 302
    assert "/entrar/google" in resposta["Location"]


# --------------------------------------------------------------- a medição


@respx.mock
def test_merge_sem_registro_aparece_na_medicao(cobranca_ja_valia):
    """O caso que dói: trabalho concluído que o livro não conhece."""
    respx.get(f"{API}/repos/abundanciabr/sitesdoreino/pulls").mock(
        return_value=httpx.Response(
            200, json=[_pr(9001, _ha_horas(5), "fix: algo importante")]
        )
    )
    respx.get(f"{API}/repos/abundanciabr/sitesdoreino/pulls/9001/files").mock(
        return_value=httpx.Response(200, json=[{"filename": "services/x/a.py"}])
    )

    dados = json.loads(_dentro().get("/painel/divida.json").content)
    assert "erro" not in dados, dados
    assert [d["numero"] for d in dados["devedores"]] == [9001]


@respx.mock
def test_pr_que_so_toca_o_livro_nao_aparece(cobranca_ja_valia):
    """A isenção da regra compartilhada vale aqui também — é a MESMA regra."""
    respx.get(f"{API}/repos/abundanciabr/sitesdoreino/pulls").mock(
        return_value=httpx.Response(
            200, json=[_pr(9002, _ha_horas(5), "livro: registro novo")]
        )
    )
    respx.get(f"{API}/repos/abundanciabr/sitesdoreino/pulls/9002/files").mock(
        return_value=httpx.Response(200, json=[{"filename": "painel/registros/x.js"}])
    )

    dados = json.loads(_dentro().get("/painel/divida.json").content)
    assert dados["devedores"] == []


# ------------------------------------------------- falha aparece, não vira 0


@respx.mock
def test_github_fora_do_ar_vira_ERRO_e_nunca_lista_vazia():
    """A asserção mais importante do arquivo.

    Uma medição que falha e devolve `devedores: []` faria a faixa sumir, e o
    dono leria a AUSÊNCIA como "está tudo contado". Aqui a falha precisa chegar
    à tela como falha.
    """
    respx.get(f"{API}/repos/abundanciabr/sitesdoreino/pulls").mock(
        side_effect=httpx.ConnectError("sem rede")
    )

    resposta = _dentro().get("/painel/divida.json")
    dados = json.loads(resposta.content)
    assert resposta.status_code == 200, "medição auxiliar não derruba o painel"
    assert "erro" in dados
    assert "devedores" not in dados


@respx.mock
def test_limite_da_api_tambem_vira_erro():
    respx.get(f"{API}/repos/abundanciabr/sitesdoreino/pulls").mock(
        return_value=httpx.Response(403, json={"message": "rate limit exceeded"})
    )
    dados = json.loads(_dentro().get("/painel/divida.json").content)
    assert "erro" in dados


# ------------------------------------------------------------------- cache


@respx.mock
def test_a_segunda_visita_nao_gasta_cota():
    """Limite anônimo é 60/h por IP; recarregar a página não pode queimá-lo."""
    rota = respx.get(f"{API}/repos/abundanciabr/sitesdoreino/pulls").mock(
        return_value=httpx.Response(200, json=[])
    )
    cliente = _dentro()
    cliente.get("/painel/divida.json")
    cliente.get("/painel/divida.json")
    assert rota.call_count == 1


# ------------------------------------------------------ a faixa está ligada


def test_o_painel_realmente_pede_a_medicao():
    """Guarda contra a faixa se desligar em silêncio.

    Sem isto, alguém poderia remover o `fetch` do HTML e todos os testes de
    servidor continuariam verdes — a rota responderia certinho, para ninguém.
    """
    html = (PAINEL_NO_REPO / "painel.html").read_text(encoding="utf-8")
    assert 'fetch("divida.json"' in html
    assert 'id="divida"' in html


def test_a_faixa_diz_quando_nao_consegue_medir():
    """O texto do caminho cego existe — é ele que impede o silêncio mentiroso."""
    html = (PAINEL_NO_REPO / "painel.html").read_text(encoding="utf-8")
    assert "Não consigo conferir" in html
