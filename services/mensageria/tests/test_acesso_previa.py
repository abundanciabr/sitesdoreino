from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from apps.eventos import acesso_previa as a

@pytest.fixture
def ambiente(monkeypatch):
    monkeypatch.setenv("TOKENS_PUBLICACAO_ADMIN","admin-test")
    monkeypatch.setattr(a,"_exige_grau_de_publicacao",lambda request:None)
    monkeypatch.setattr(a.transaction,"atomic",nullcontext)
    enviar_email=Mock(); enviar_wa=Mock(return_value=SimpleNamespace(status="entregue"))
    monkeypatch.setattr(a,"enviar_email",enviar_email)
    monkeypatch.setattr(a,"enviar_mensagem",enviar_wa)
    monkeypatch.setattr(a,"reservar_envio",Mock())
    monkeypatch.setattr(a,"registrar_sucesso",Mock())
    envio=SimpleNamespace(assunto="Seu código",save=Mock(),resultado="aceito")
    manager=Mock();manager.get_or_create.return_value=(envio,True)
    monkeypatch.setattr(a,"EnvioRegistrado",SimpleNamespace(objects=manager))
    return envio,manager,enviar_email,enviar_wa

def dados(canal="email"):
    return a.Enviar(site_id="site-1",desafio="11111111-1111-4111-8111-111111111111",canal=canal,destino="admin@example.test" if canal=="email" else "5511900000000",codigo="123456")

@pytest.mark.parametrize("canal",["email","whatsapp"])
def test_envio_real_no_transporte_sem_codigo_no_registro(ambiente,canal):
    envio,manager,email,wa=ambiente
    resultado=a.enviar(SimpleNamespace(auth="admin-test"),dados(canal))
    assert resultado["estado"] in {"aceito","entregue"}
    assert "123456" not in str(manager.get_or_create.call_args)
    assert (email if canal=="email" else wa).call_count==1

def test_repetido_nao_dispara_outro_envio(ambiente):
    envio,manager,email,wa=ambiente
    manager.get_or_create.return_value=(envio,False)
    assert a.enviar(SimpleNamespace(auth="admin-test"),dados())["repetido"]
    email.assert_not_called();wa.assert_not_called()

def test_erro_nao_expoe_codigo_ou_destinatario(ambiente):
    envio,manager,email,wa=ambiente
    email.side_effect=RuntimeError("123456 admin@example.test")
    r=a.enviar(SimpleNamespace(auth="admin-test"),dados())
    assert r["estado"]=="desconhecido"
    assert "123456" not in str(r) and "admin@example.test" not in envio.resultado

def test_outro_par_recusado(ambiente):
    from ninja.errors import HttpError
    with pytest.raises(HttpError) as erro:a.enviar(SimpleNamespace(auth="outro"),dados())
    assert erro.value.status_code==403
    ambiente[1].get_or_create.assert_not_called()
