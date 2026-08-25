"""A porta do site: botão → Google → e-mail VERIFICADO → sessão.

A diferença de produto em relação à porta da Caixa está no que NÃO existe
aqui: nenhuma consulta de matrícula (guarda próprio em
`test_inv_porta_nao_consulta_ninguem.py`). E toda recusa VOLTA para a tela de
login do `funil` com a chave do motivo — esta célula não renderiza página.
"""

from urllib.parse import urlparse

from apps.identidade.models import Identidade
from tests.conftest import perfil_google


def _para_onde(resposta) -> str:
    assert resposta.status_code == 302, resposta.content
    return resposta["Location"]


def test_entrar_abre_sessao_e_volta_para_o_destino(porta):
    resposta = porta.bater(perfil_google(), next="/pt-br/")
    assert _para_onde(resposta) == "/pt-br/"
    assert porta.esta_dentro
    assert porta.identidade.email == "joao.silva@exemplo.test"


def test_sem_next_volta_para_a_raiz(porta):
    resposta = porta.bater(perfil_google())
    assert _para_onde(resposta) == "/"
    assert porta.esta_dentro


def test_email_nao_verificado_e_recusado_sem_criar_nada(porta):
    """[INVARIANTE] Só o booleano True do Google passa — herdado da EVO-01 §2."""
    resposta = porta.bater(perfil_google(verificado=False), next="/pt-br/")
    assert _para_onde(resposta) == "/pt-br/login?erro=email-nao-verificado"
    assert not porta.esta_dentro
    assert Identidade.objects.count() == 0


def test_email_verificado_string_false_tambem_e_recusado(porta):
    """A string "false" é verdadeira em Python — o portão usa `is not True`."""
    perfil = perfil_google()
    perfil["email_verified"] = "false"
    resposta = porta.bater(perfil)
    assert "erro=email-nao-verificado" in _para_onde(resposta)
    assert not porta.esta_dentro


def test_volta_com_error_do_google_e_interrompida(porta):
    resposta = porta.bater(error="access_denied")
    assert "erro=interrompida" in _para_onde(resposta)
    assert not porta.esta_dentro


def test_state_que_nao_confere_e_recusado(porta, client, rede, db):
    """O antifalsificação: `state` inventado nunca abre sessão."""
    inicio = client.get("/entrar/google")
    assert inicio.status_code == 302
    resposta = client.get(
        "/entrar/google/retorno",
        {"code": "codigo-de-teste", "state": "state-inventado"},
    )
    assert "erro=nao-confere" in _para_onde(resposta)
    assert Identidade.objects.count() == 0


def test_retorno_sem_inicio_e_recusado(client, rede, db):
    """Chegar direto no retorno (sessão sem `state` guardado) fecha a porta."""
    resposta = client.get("/entrar/google/retorno", {"code": "x", "state": "y"})
    assert "erro=nao-confere" in _para_onde(resposta)


def test_google_fora_do_ar_fecha_explicando(porta, rede):
    rede.google_fora_do_ar()
    resposta = porta.bater()
    assert "erro=google-indisponivel" in _para_onde(resposta)
    assert not porta.esta_dentro


def test_sem_credenciais_do_google_a_porta_fecha(client, db, monkeypatch, rede):
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    resposta = client.get("/entrar/google", {"next": "/es/algo"})
    # A recusa aterrissa na tela de login DO IDIOMA do destino pedido.
    assert _para_onde(resposta) == "/es/login?erro=nao-configurada"


def test_recusa_fala_o_idioma_do_destino(porta):
    resposta = porta.bater(perfil_google(verificado=False), next="/es/pagina")
    assert _para_onde(resposta) == "/es/login?erro=email-nao-verificado"


def test_o_redirect_uri_e_o_endereco_neutro_cadastrado_no_google(client, rede, db):
    """O retorno é `/entrar/google/retorno` SEM prefixo de célula — o endereço
    que o mantenedor cadastrou no console em 24/08/2026 exatamente para o dia
    desta célula (DECISAO-onde-mora-a-sessao §5.2)."""
    inicio = client.get("/entrar/google")
    destino = urlparse(inicio["Location"])
    from urllib.parse import parse_qs

    redirect_uri = parse_qs(destino.query)["redirect_uri"][0]
    assert urlparse(redirect_uri).path == "/entrar/google/retorno"
