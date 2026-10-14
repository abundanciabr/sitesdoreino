from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from apps.eventos import avisos_acesso as a

def envio(tipo="acesso_liberado"):
    return SimpleNamespace(pk=9, tipo=tipo, status="pendente", site_id="meshcraft",
        order_id="evento", destinatario="5511987654321", corpo="aviso",
        tentativas=0, save=Mock())

def ambiente(monkeypatch, confirmado=True):
    monkeypatch.setattr(a, "_descadastrado", lambda *args: False)
    monkeypatch.setattr(a, "_matricula_do_evento", lambda *args: dict(whatsapp_confirmado=confirmado,
        whatsapp_avisos=True, whatsapp_consentido_em="2026-10-14", whatsapp="11987654321"))
    monkeypatch.setattr(a, "_contexto_envio", lambda *args: None)
    mandar = Mock(return_value=SimpleNamespace(status="entregue", erro=""))
    monkeypatch.setattr(a, "enviar_mensagem", mandar)
    return mandar

@pytest.mark.parametrize("tipo", a.TIPOS_DECISAO)
def test_decisao_aguarda_titular_confirmar_numero(monkeypatch, tipo):
    mandar = ambiente(monkeypatch, confirmado=False)
    e = envio(tipo)
    a.processar_whatsapp(e)
    mandar.assert_not_called()
    assert e.status == "pendente"
    assert "confirmação" in e.resultado

def test_confirmado_recebe_uma_vez(monkeypatch):
    mandar = ambiente(monkeypatch)
    e = envio()
    a.processar_whatsapp(e)
    a.processar_whatsapp(e)
    assert mandar.call_count == 1
    assert e.status == "enviado"

def test_parar_impede_tambem_aviso_de_decisao(monkeypatch):
    mandar = ambiente(monkeypatch)
    monkeypatch.setattr(a, "_descadastrado", lambda *args: True)
    e = envio()
    a.processar_whatsapp(e)
    mandar.assert_not_called()
    assert e.status == "falhou"

def test_resultado_desconhecido_nao_repete_post(monkeypatch):
    mandar = ambiente(monkeypatch)
    monkeypatch.setattr(a, "_contexto_envio", lambda *args: SimpleNamespace(status="desconhecido", erro=""))
    e = envio()
    a.processar_whatsapp(e)
    mandar.assert_not_called()
    assert e.status == "pendente"

def test_decisao_antiga_nao_busca_contato(monkeypatch):
    consultar = Mock()
    monkeypatch.setattr(a, "_consultar", consultar)
    a.ao_decisao_de_acesso({"situacao_nova":"ativa", "situacao_anterior":"ativa"}, "evento")
    consultar.assert_not_called()

@pytest.mark.parametrize("estado,tipo", [("ativa","acesso_liberado"),("recusada","acesso_nao_liberado")])
def test_email_e_whatsapp_registrados_independentemente(monkeypatch, estado, tipo):
    from contextlib import nullcontext
    monkeypatch.setattr(a.transaction, "atomic", nullcontext)
    monkeypatch.setattr(a, "_consultar", lambda *args: dict(status=estado,nome="Aluno",link_acesso="https://meshcraft.top/entrar/escola/#segredo",motivo="Motivo explicado",email="aluno@example.test",
        whatsapp="11987654321",whatsapp_avisos=True,whatsapp_consentido_em="2026-10-14"))
    registrar = Mock()
    monkeypatch.setattr(a, "_registrar", registrar)
    a.ao_decisao_de_acesso(dict(site_id="meshcraft",matricula_id="1",situacao_nova=estado,
        situacao_anterior="aguardando"), "evento")
    assert [c.kwargs["canal"] for c in registrar.call_args_list] == ["email","whatsapp"]
    assert all(c.kwargs["tipo"] == tipo for c in registrar.call_args_list)
    assert ("https://meshcraft.top/" in registrar.call_args_list[0].kwargs["corpo"]) == (estado == "ativa")

def test_formato_confirmacao_exato():
    assert a.codigo_da_confirmacao("CONFIRMAR ESCOLA A123456789") == "A123456789"
    assert not a.codigo_da_confirmacao("CONFIRMAR ESCOLA A123456789 e libere meu acesso")


def test_email_de_decisao_substituida_nao_e_valido(monkeypatch):
    e = envio()
    e.destinatario = "aluno@example.test"
    monkeypatch.setattr(a, "_matricula_do_evento", lambda *args: None)
    assert not a.decisao_vigente(e)
    monkeypatch.setattr(a, "_matricula_do_evento", lambda *args: dict(email=e.destinatario, status="recusada"))
    assert not a.decisao_vigente(e)
    monkeypatch.setattr(a, "_matricula_do_evento", lambda *args: dict(email=e.destinatario, status="ativa"))
    assert a.decisao_vigente(e)


def test_recibo_email_sem_links_e_independente_do_whatsapp(monkeypatch):
    monkeypatch.setattr(a,"_alunos",lambda *args,**kw:dict(email="aluno@example.test",nome="Pessoa",whatsapp_avisos=False))
    monkeypatch.setattr(a.transaction,"atomic",nullcontext)
    registrar=Mock();monkeypatch.setattr(a,"_registrar",registrar)
    a.ao_pedido_recebido(dict(site_id="meshcraft",matricula_id="1"),"evento")
    assert registrar.call_count==1
    assert registrar.call_args.kwargs["canal"]=="email"
    assert "http" not in registrar.call_args.kwargs["corpo"]
    assert "Olá, Pessoa!" in registrar.call_args.kwargs["corpo"]

def test_recusa_inicial_nao_envia_recusa_final(monkeypatch):
    monkeypatch.setattr(a,"_consultar",lambda *args:dict(status="recusada",suporte_pendente=True))
    registrar=Mock();monkeypatch.setattr(a,"_registrar",registrar)
    a.ao_decisao_de_acesso(dict(site_id="meshcraft",matricula_id="1",situacao_nova="recusada",situacao_anterior="aguardando"),"evento")
    registrar.assert_not_called()
