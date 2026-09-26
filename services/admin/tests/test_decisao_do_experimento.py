"""A decisão de um experimento da página: promover, reverter ou encerrar.

O que estes guardas protegem:

1. **Promover publica pela publicação que já existe**: rascunho gravado a partir
   da versão publicada, com um espaço trocado, e rascunho publicado. Só depois
   o experimento é encerrado com `promover` e a variante vencedora.
2. **Promover só com veredito `candidato à promoção` ou com confirmação.**
3. **Reverter e Encerrar não publicam nada.**
4. **Duplo clique não duplica nada**: o segundo encontra o experimento encerrado
   com a mesma decisão e não publica nem encerra de novo; a trava por
   experimento é pedida ao Postgres.
5. **Texto salvo e não publicado não vai ao ar escondido.**
6. **A metade que parou se completa sem publicar de novo.**
7. **Toda escrita deixa linha de auditoria**, e sem crachá nada escreve.
"""

from __future__ import annotations

import json
import sys

import httpx
import pytest
import respx
from django.db import DatabaseError, connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.auditoria.models import Registro
from apps.core import decisao_do_experimento

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
CATALOGO = "http://catalogo:8000/api/catalogo"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"
SITE_ID = "site-mesh"
EXP_ID = "6f1c2b1e-0000-4000-8000-000000000001"
EXPERIMENTO = f"{CATALOGO}/sites/{SITE_ID}/experimentos/{EXP_ID}"
ENCERRAR = f"{EXPERIMENTO}/encerrar"
PAGINA = f"{CATALOGO}/sites/{SITE_ID}/paginas/oferta"
RASCUNHO = f"{PAGINA}/rascunho"
PUBLICAR = f"{PAGINA}/publicar"

TEXTO_A = "Modele peças que funcionam"
TEXTO_B = "Da primeira peça ao primeiro cliente"


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    monkeypatch.setenv("CATALOGO_API_URL", CATALOGO)
    monkeypatch.setenv("TOKEN_CATALOGO", "token-do-par-admin-catalogo")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


@pytest.fixture
def veredito(monkeypatch):
    """O veredito da F9a, fixado pelo teste."""
    atual = {"valor": decisao_do_experimento.CANDIDATO}
    monkeypatch.setattr(
        decisao_do_experimento, "_veredito", lambda site_id, exp: atual["valor"]
    )
    return atual


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
        return_value=httpx.Response(
            200,
            json={
                "id": SITE_ID,
                "host": "testserver",
                "name": "Meshcraft",
                "active": True,
            },
        )
    )
    c = Client()
    c.defaults["HTTP_COOKIE"] = COOKIE
    return c


def _experimento(estado="ativo", decisao=None, vencedora=None) -> dict:
    return {
        "id": EXP_ID,
        "pagina": "oferta",
        "secao": "cubo",
        "slot": "headline",
        "estado": estado,
        "decisao": decisao,
        "variante_vencedora": vencedora,
        "variantes": [
            {"variante_id": "a", "peso": 5000, "valor": TEXTO_A},
            {"variante_id": "b", "peso": 5000, "valor": TEXTO_B},
        ],
    }


def _secoes(headline: str) -> list:
    return [
        {
            "nome": "cubo",
            "ordem": 0,
            "slots": {"headline": headline, "cta_texto": "Quero"},
        },
        {"nome": "carta", "ordem": 9, "slots": {"texto": "Olá"}},
    ]


def _publicada(headline=TEXTO_A, version=7) -> dict:
    return {
        "id": "11111111-1111-1111-1111-111111111111",
        "site_id": SITE_ID,
        "slug": "oferta",
        "version": version,
        "published_at": "2026-09-26T12:00:00Z",
        "secoes": _secoes(headline),
    }


def _rascunho(headline=TEXTO_A) -> dict:
    return {
        "site_id": SITE_ID,
        "slug": "oferta",
        "base_version": 7,
        "secoes": _secoes(headline),
        "atualizado_em": "2026-09-26T12:00:00Z",
    }


def _catalogo(*, experimentos, publicada=None, rascunho=None, encerrar=200):
    """O catálogo falso. `experimentos` é a sequência de leituras do experimento;
    depois da última, ele continua respondendo a última (a tela relê)."""
    fila = list(experimentos)

    def ler(request):
        return httpx.Response(200, json=fila.pop(0) if len(fila) > 1 else fila[0])

    respx.get(EXPERIMENTO).mock(side_effect=ler)
    rotas = {
        "publicada": respx.get(PAGINA).mock(
            return_value=httpx.Response(200, json=publicada or _publicada())
        ),
        "rascunho": respx.get(RASCUNHO).mock(
            return_value=httpx.Response(200, json=rascunho or _rascunho())
        ),
        "gravar": respx.put(RASCUNHO).mock(
            return_value=httpx.Response(200, json=_rascunho(TEXTO_B))
        ),
        "publicar": respx.post(PUBLICAR).mock(
            return_value=httpx.Response(200, json=_publicada(TEXTO_B, 8))
        ),
        "encerrar": respx.post(ENCERRAR).mock(
            return_value=httpx.Response(encerrar, json={"detail": "fora do ar"})
        ),
    }
    return rotas


def _decidir(cliente, **dados):
    return cliente.post(reverse("decidir_experimento", args=[EXP_ID]), dados)


# ---------------------------------------------------------------------------
# 1. Promover publica pela publicação que já existe, e só então encerra
# ---------------------------------------------------------------------------
@respx.mock
@pytest.mark.django_db
def test_promover_publica_a_variante_pelo_rascunho_e_encerra_com_a_vencedora(veredito):
    rotas = _catalogo(experimentos=[_experimento()])
    r = _decidir(_dentro(), decisao="promover", variante="b")

    assert r.status_code == 302
    assert r["Location"].endswith("?recado=promover")
    gravado = json.loads(rotas["gravar"].calls.last.request.content)
    assert gravado["secoes"] == _secoes(TEXTO_B)
    assert rotas["publicar"].call_count == 1
    assert json.loads(rotas["encerrar"].calls.last.request.content) == {
        "decisao": "promover",
        "variante_vencedora": "b",
    }
    ordem = [c.request.url for c in respx.calls]
    assert ordem.index(PUBLICAR) < ordem.index(ENCERRAR)


@respx.mock
@pytest.mark.django_db
def test_promover_deixa_auditoria_da_publicacao_e_da_decisao(veredito):
    _catalogo(experimentos=[_experimento()])
    _decidir(_dentro(), decisao="promover", variante="b")
    publicou = Registro.objects.get(acao=Registro.PUBLICAR_PAGINA)
    decidiu = Registro.objects.get(acao=Registro.DECIDIR_EXPERIMENTO)
    assert "versão 8" in publicou.detalhe and EXP_ID in publicou.detalhe
    assert decidiu.alvo == EXP_ID
    assert decidiu.desfecho == Registro.OK
    assert decidiu.detalhe == "promover b"


# ---------------------------------------------------------------------------
# 2. Promover só com candidato à promoção, ou com a palavra dele
# ---------------------------------------------------------------------------
@respx.mock
@pytest.mark.django_db
def test_promover_inconclusivo_sem_confirmacao_nao_publica_nem_encerra(veredito):
    veredito["valor"] = "inconclusivo"
    rotas = _catalogo(experimentos=[_experimento()])
    r = _decidir(_dentro(), decisao="promover", variante="b")

    assert r.status_code == 422
    assert "não é conclusivo" in r.content.decode()
    assert not rotas["gravar"].called
    assert not rotas["publicar"].called
    assert not rotas["encerrar"].called


@respx.mock
@pytest.mark.django_db
def test_promover_inconclusivo_com_confirmacao_publica_e_registra_a_confirmacao(
    veredito,
):
    veredito["valor"] = "inconclusivo"
    rotas = _catalogo(experimentos=[_experimento()])
    r = _decidir(
        _dentro(), decisao="promover", variante="b", confirmo_inconclusivo="sim"
    )

    assert r.status_code == 302
    assert rotas["publicar"].call_count == 1
    assert (
        Registro.objects.get(acao=Registro.DECIDIR_EXPERIMENTO).detalhe
        == "promover b com resultado não conclusivo"
    )


@respx.mock
@pytest.mark.django_db
def test_a_tela_so_pede_confirmacao_quando_o_resultado_nao_e_candidato(veredito):
    _catalogo(experimentos=[_experimento(), _experimento()])
    cliente = _dentro()
    url = reverse("decisao_do_experimento", args=[EXP_ID])

    candidato = cliente.get(url).content.decode()
    assert "Promover b" in candidato
    assert 'name="confirmo_inconclusivo"' not in candidato

    veredito["valor"] = "coletando"
    coletando = cliente.get(url).content.decode()
    assert "Promover b" in coletando
    assert 'name="confirmo_inconclusivo" value="sim" required' in coletando


@respx.mock
@pytest.mark.django_db
def test_a_variante_de_controle_nao_se_promove(veredito):
    rotas = _catalogo(experimentos=[_experimento()])
    r = _decidir(_dentro(), decisao="promover", variante="a")
    assert r.status_code == 422
    assert "use Reverter" in r.content.decode()
    assert not rotas["publicar"].called


# ---------------------------------------------------------------------------
# 3. Reverter e Encerrar não publicam nada
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("decisao", ["reverter", "encerrar"])
@respx.mock
@pytest.mark.django_db
def test_reverter_e_encerrar_encerram_sem_publicar(veredito, decisao):
    rotas = _catalogo(experimentos=[_experimento()])
    r = _decidir(_dentro(), decisao=decisao)

    assert r.status_code == 302
    assert r["Location"].endswith(f"?recado={decisao}")
    assert not rotas["gravar"].called
    assert not rotas["publicar"].called
    assert json.loads(rotas["encerrar"].calls.last.request.content) == {
        "decisao": decisao,
        "variante_vencedora": None,
    }


# ---------------------------------------------------------------------------
# 4. Duplo clique não duplica nada
# ---------------------------------------------------------------------------
@respx.mock
@pytest.mark.django_db
def test_o_segundo_clique_nao_publica_nem_encerra_de_novo(veredito):
    rotas = _catalogo(
        experimentos=[
            _experimento(),
            _experimento("encerrado", "promover", "b"),
        ]
    )
    cliente = _dentro()
    primeiro = _decidir(cliente, decisao="promover", variante="b")
    segundo = _decidir(cliente, decisao="promover", variante="b")

    assert primeiro["Location"].endswith("?recado=promover")
    assert segundo.status_code == 302
    assert segundo["Location"].endswith("?recado=repetido")
    assert rotas["publicar"].call_count == 1
    assert rotas["encerrar"].call_count == 1


@respx.mock
@pytest.mark.django_db
def test_decisao_gravada_nao_muda_com_outro_botao(veredito):
    rotas = _catalogo(experimentos=[_experimento("encerrado", "reverter")])
    r = _decidir(_dentro(), decisao="promover", variante="b")
    assert r.status_code == 422
    assert "já foi encerrado com a decisão Reverter" in r.content.decode()
    assert not rotas["publicar"].called
    assert not rotas["encerrar"].called


@pytest.mark.django_db(transaction=True)
def test_a_decisao_pede_a_trava_do_experimento_ao_postgres(monkeypatch):
    monkeypatch.setattr(connection, "vendor", "postgresql")
    with CaptureQueriesContext(connection) as consultas:
        try:
            with decisao_do_experimento._um_de_cada_vez(EXP_ID):
                pass
        except DatabaseError:
            pass  # o SQLite local não conhece a função; o Postgres do CI conhece
    assert any("pg_advisory_xact_lock" in c["sql"] for c in consultas.captured_queries)


# ---------------------------------------------------------------------------
# 5. Texto salvo e não publicado não vai ao ar escondido
# ---------------------------------------------------------------------------
@respx.mock
@pytest.mark.django_db
def test_rascunho_com_texto_nao_publicado_recusa_promover(veredito):
    pendente = _rascunho()
    pendente["secoes"][1]["slots"]["texto"] = "Carta nova, ainda não publicada"
    rotas = _catalogo(experimentos=[_experimento()], rascunho=pendente)
    r = _decidir(_dentro(), decisao="promover", variante="b")

    assert r.status_code == 422
    assert "ainda não foi ao ar" in r.content.decode()
    assert not rotas["gravar"].called
    assert not rotas["publicar"].called
    assert not rotas["encerrar"].called


# ---------------------------------------------------------------------------
# 6. A metade que parou se completa sem publicar de novo
# ---------------------------------------------------------------------------
@respx.mock
@pytest.mark.django_db
def test_publicou_e_nao_encerrou_diz_a_metade_e_o_clique_seguinte_so_encerra(
    veredito,
):
    rotas = _catalogo(experimentos=[_experimento(), _experimento()], encerrar=503)
    cliente = _dentro()
    metade = _decidir(cliente, decisao="promover", variante="b")

    assert metade.status_code == 503
    assert "já está no ar" in metade.content.decode()
    assert "Apertar Promover de novo é seguro" in metade.content.decode()
    assert rotas["publicar"].call_count == 1

    # O catálogo voltou, e a página no ar já tem o texto da variante.
    respx.get(PAGINA).mock(
        return_value=httpx.Response(200, json=_publicada(TEXTO_B, 8))
    )
    respx.get(RASCUNHO).mock(return_value=httpx.Response(200, json=_rascunho(TEXTO_B)))
    rotas["encerrar"].mock(return_value=httpx.Response(200, json=_experimento()))
    completou = _decidir(cliente, decisao="promover", variante="b")

    assert completou["Location"].endswith("?recado=promover")
    assert rotas["publicar"].call_count == 1
    assert rotas["gravar"].call_count == 1
    assert rotas["encerrar"].call_count == 2


# ---------------------------------------------------------------------------
# 7. A porta e os estados da tela
# ---------------------------------------------------------------------------
@respx.mock
@pytest.mark.django_db
def test_experimento_encerrado_nao_oferece_botao(veredito):
    _catalogo(experimentos=[_experimento("encerrado", "promover", "b")])
    tela = _dentro().get(reverse("decisao_do_experimento", args=[EXP_ID]))
    texto = tela.content.decode()
    assert "Encerrado com a decisão Promover" in texto
    assert "<button" not in texto


@respx.mock
@pytest.mark.django_db
def test_catalogo_mudo_nao_mostra_botao_e_diz_o_que_fazer(veredito):
    _dentro()
    respx.get(EXPERIMENTO).mock(return_value=httpx.Response(503))
    tela = _dentro().get(reverse("decisao_do_experimento", args=[EXP_ID]))
    texto = tela.content.decode()
    assert "Não consegui ler o experimento" in texto
    assert "<button" not in texto


@respx.mock
def test_sem_cracha_nenhum_gesto_escreve():
    respx.get(f"{CATALOGO}/sites/by-host/testserver").mock(
        return_value=httpx.Response(200, json={"id": SITE_ID})
    )
    publicar = respx.post(PUBLICAR).mock(return_value=httpx.Response(200, json={}))
    encerrar = respx.post(ENCERRAR).mock(return_value=httpx.Response(200, json={}))
    r = Client().post(
        reverse("decidir_experimento", args=[EXP_ID]),
        {"decisao": "promover", "variante": "b"},
    )
    assert r.status_code in (302, 404)
    assert not publicar.called
    assert not encerrar.called


@respx.mock
@pytest.mark.django_db
def test_sem_veredito_calculado_promover_exige_a_confirmacao(monkeypatch):
    """Sem a tela de resultado (F9a) ou sem cálculo, o lado seguro vale."""
    monkeypatch.setattr(decisao_do_experimento, "_veredito", lambda s, e: None)
    rotas = _catalogo(experimentos=[_experimento()])
    cliente = _dentro()
    tela = cliente.get(reverse("decisao_do_experimento", args=[EXP_ID]))
    assert "ainda sem cálculo" in tela.content.decode()
    assert 'name="confirmo_inconclusivo" value="sim" required' in tela.content.decode()
    assert _decidir(cliente, decisao="promover", variante="b").status_code == 422
    assert not rotas["publicar"].called


def test_sem_a_tela_de_resultado_o_veredito_e_desconhecido(monkeypatch):
    """Módulo da F9a ausente não derruba a tela: o veredito fica desconhecido."""
    monkeypatch.setitem(sys.modules, "apps.core.resultado_do_experimento", None)
    assert decisao_do_experimento._veredito(SITE_ID, _experimento()) is None
