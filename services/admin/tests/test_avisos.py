"""A tela `/admin/avisos/` — o botão que prova se os avisos na tela do
celular estão funcionando.

O que estes guardas protegem:

1. **Esta tela não guarda nada.** Ela pede o teste à `notificacoes` e mostra o
   que voltou. Um contador aqui seria o mesmo fato em dois lugares.
2. **Quem recebe é sempre quem pediu.** O formulário não tem campo de
   destinatário: `destinatario_id` é sempre `request.admin["id"]`. Um clique
   nunca pode tocar o celular de outra pessoa.
3. **`aparelhos: 0` é resultado, não erro.** É o diagnóstico mais útil desta
   tela, e a frase que a acompanha não pode soar como falha do site.
4. **O gesto vira linha de auditoria**, com o número de aparelhos no detalhe.
5. **A `notificacoes` fora do ar diz isso claramente**, nunca finge que
   enviou — mentir aqui seria pior que recusar.
6. **A porta continua sendo a porta**: sem crachá, nada disto responde.
"""

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.auditoria.models import Registro

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
CATALOGO = "http://catalogo:8000/api/catalogo"
NOTIFICACOES = "http://notificacoes:8000/api/notificacoes"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"
DONO_ID = "id-opaco-123"
SITE_ID = "site-mesh"


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    monkeypatch.setenv("CATALOGO_API_URL", CATALOGO)
    monkeypatch.setenv("TOKEN_CATALOGO", "token-do-par-admin-catalogo")
    monkeypatch.setenv("NOTIFICACOES_API_URL", NOTIFICACOES)
    monkeypatch.setenv("NOTIFICACOES_API_TOKEN", "token-do-par-admin-notificacoes")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


def _dentro() -> Client:
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": DONO_ID,
                "nome_exibido": "Fulano",
                "papel": None,
                "email": DONO,
            },
        )
    )
    c = Client()
    c.defaults["HTTP_COOKIE"] = COOKIE
    return c


def _mock_site():
    return respx.get(f"{CATALOGO}/sites/by-host/testserver").mock(
        return_value=httpx.Response(200, json={"id": SITE_ID, "host": "testserver"})
    )


# ---------------------------------------------------------------------------
# A tela abre
# ---------------------------------------------------------------------------
@pytest.mark.django_db
@respx.mock
def test_a_tela_abre_sem_resultado_nenhum():
    resposta = _dentro().get(reverse("avisos"))

    assert resposta.status_code == 200
    conteudo = resposta.content.decode()
    assert "Mandar um aviso de teste para mim" in conteudo


@pytest.mark.django_db
@respx.mock
def test_sem_credenciais_a_tela_abre_mesmo_assim():
    """Fail-OPEN: uma tela de operação que não abre é inútil justamente
    quando você precisa dela — mesma disciplina de `economia`/`menu`."""
    resposta = _dentro().get(reverse("avisos"))

    assert resposta.status_code == 200


# ---------------------------------------------------------------------------
# O clique — o número que a porta devolve
# ---------------------------------------------------------------------------
@pytest.mark.django_db
@respx.mock
def test_com_aparelho_o_clique_diz_chegou(settings, monkeypatch):
    _mock_site()
    rota = respx.post(f"{NOTIFICACOES}/aviso-de-teste").mock(
        return_value=httpx.Response(200, json={"aparelhos": 2})
    )

    resposta = _dentro().post(reverse("avisos_testar"), follow=True)

    assert resposta.status_code == 200
    assert "Chegou em 2 aparelho(s)" in resposta.content.decode()
    corpo = rota.calls[0].request.content
    import json as _json

    assert _json.loads(corpo) == {"site_id": SITE_ID, "destinatario_id": DONO_ID}


@pytest.mark.django_db
@respx.mock
def test_sem_aparelho_o_clique_diz_zero_e_nao_parece_erro():
    """O desfecho mais importante desta tela: zero é diagnóstico, não falha."""
    _mock_site()
    respx.post(f"{NOTIFICACOES}/aviso-de-teste").mock(
        return_value=httpx.Response(200, json={"aparelhos": 0})
    )

    resposta = _dentro().post(reverse("avisos_testar"), follow=True)

    conteudo = resposta.content.decode()
    assert "Zero aparelhos" in conteudo
    assert "Ligar os avisos" in conteudo


@pytest.mark.django_db
@respx.mock
def test_a_notificacoes_fora_do_ar_diz_isso_claramente():
    _mock_site()
    respx.post(f"{NOTIFICACOES}/aviso-de-teste").mock(return_value=httpx.Response(503))

    resposta = _dentro().post(reverse("avisos_testar"), follow=True)

    assert "Não deu para saber" in resposta.content.decode()


@pytest.mark.django_db
@respx.mock
def test_catalogo_fora_do_ar_nao_chega_a_perguntar_a_notificacoes():
    respx.get(f"{CATALOGO}/sites/by-host/testserver").mock(
        return_value=httpx.Response(503)
    )
    rota = respx.post(f"{NOTIFICACOES}/aviso-de-teste").mock(
        return_value=httpx.Response(200, json={"aparelhos": 1})
    )

    resposta = _dentro().post(reverse("avisos_testar"), follow=True)

    assert "Não consegui saber qual site é este" in resposta.content.decode()
    assert rota.calls.call_count == 0


# ---------------------------------------------------------------------------
# Quem recebe é sempre quem pediu
# ---------------------------------------------------------------------------
@pytest.mark.django_db
@respx.mock
def test_o_formulario_nao_tem_campo_para_escolher_o_destinatario():
    resposta = _dentro().get(reverse("avisos"))

    assert 'name="destinatario' not in resposta.content.decode()
    assert 'name="id"' not in resposta.content.decode()


@pytest.mark.django_db
@respx.mock
def test_um_id_mandado_a_mao_no_post_e_ignorado():
    """A garantia é estrutural: mesmo que alguém poste um campo estranho, a
    view nunca lê destinatário do corpo — só de `request.admin`."""
    _mock_site()
    rota = respx.post(f"{NOTIFICACOES}/aviso-de-teste").mock(
        return_value=httpx.Response(200, json={"aparelhos": 1})
    )

    _dentro().post(reverse("avisos_testar"), {"destinatario_id": "id-de-outra-pessoa"})

    import json as _json

    assert _json.loads(rota.calls[0].request.content)["destinatario_id"] == DONO_ID


# ---------------------------------------------------------------------------
# A auditoria
# ---------------------------------------------------------------------------
@pytest.mark.django_db
@respx.mock
def test_o_clique_vira_linha_de_auditoria_com_o_numero():
    _mock_site()
    respx.post(f"{NOTIFICACOES}/aviso-de-teste").mock(
        return_value=httpx.Response(200, json={"aparelhos": 3})
    )

    _dentro().post(reverse("avisos_testar"))

    linha = Registro.objects.get()
    assert linha.acao == Registro.TESTAR_AVISO
    assert linha.quem_email == DONO
    assert linha.desfecho == Registro.OK
    assert "3" in linha.detalhe


@pytest.mark.django_db
@respx.mock
def test_a_falha_tambem_vira_linha_de_auditoria():
    _mock_site()
    respx.post(f"{NOTIFICACOES}/aviso-de-teste").mock(return_value=httpx.Response(503))

    _dentro().post(reverse("avisos_testar"))

    linha = Registro.objects.get()
    assert linha.acao == Registro.TESTAR_AVISO
    assert linha.desfecho == Registro.NAO_RESPONDEU


# ---------------------------------------------------------------------------
# A porta continua sendo a porta
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_sem_cracha_o_clique_nao_responde():
    resposta = Client().post(reverse("avisos_testar"))

    assert resposta.status_code in (302, 401, 403)
    assert Registro.objects.count() == 0


@pytest.mark.django_db
def test_sem_cracha_a_tela_nao_abre():
    resposta = Client().get(reverse("avisos"))

    assert resposta.status_code == 302
