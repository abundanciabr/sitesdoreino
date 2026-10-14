import uuid
import pytest
from apps.atendimento import jornada_acesso as j
from apps.atendimento.models import Conversa, Mensagem

def test_encaminhamento_unico_sem_robo_e_decisao_remove_da_fila(monkeypatch):
    evento=str(uuid.uuid4())
    monkeypatch.setattr(j.IdentidadeClient,"_configuracao",lambda self:None)
    monkeypatch.setattr(j,"_alunos",lambda *a,**k:dict(site_id="meshcraft",matricula_id="1",nome="Aluno",email="aluno@example.test",motivo="Conferir compra",resolvido=False))
    envelope={"event_id":evento,"data":{"site_id":"meshcraft","matricula_id":"1"}}
    c=j.encaminhar(envelope);j.encaminhar(envelope)
    assert Conversa.objects.count()==1 and Mensagem.objects.count()==1
    assert c.estado=="aguardando" and not c.processar
    monkeypatch.setattr(j,"_alunos",lambda *a,**k:dict(resolvido=True))
    j.resolver(c,decisao="recusar",quem="equipe",nome="Equipe",motivo="Seu pedido precisa de correção.")
    c.refresh_from_db();assert c.arquivada_em and c.estado=="encerrado"
    assert Mensagem.objects.filter(conversa=c,texto="Seu pedido precisa de correção.").exists()

def test_suporte_nao_arquiva_quando_escola_nao_confirmou(monkeypatch):
    evento=str(uuid.uuid4())
    monkeypatch.setattr(j.IdentidadeClient,"_configuracao",lambda self:None)
    monkeypatch.setattr(j,"_alunos",lambda *a,**k:dict(site_id="meshcraft",matricula_id="1",nome="Aluno",email="aluno@example.test",motivo="Conferir compra",resolvido=False))
    c=j.encaminhar({"event_id":evento,"data":{"site_id":"meshcraft","matricula_id":"1"}})
    monkeypatch.setattr(j,"_alunos",lambda *a,**k:None)
    with pytest.raises(ValueError): j.resolver(c,decisao="liberar",quem="equipe",nome="Equipe",product_id="curso")
    c.refresh_from_db();assert not c.arquivada_em
