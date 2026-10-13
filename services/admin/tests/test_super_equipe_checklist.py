from decimal import Decimal
import pytest
from apps.core.models import Documento
from apps.agentes.models import Execucao, Consumo, RotinaSuperEquipe
from apps.agentes.super_equipe_checklist import sincronizar, NOME, INICIO

@pytest.mark.django_db
def test_sincroniza_estado_preserva_texto_custos_e_historico():
    d=Documento.objects.create(nome=NOME,titulo="Checklist privado",corpo="TEXTO DO ADMIN")
    RotinaSuperEquipe.objects.create(host="meshcraft.top",ativa=False)
    e=Execucao.objects.create(tipo=Execucao.Tipo.SUPER_EQUIPE,estado={"host":"meshcraft.top","especialidades":["jez_humble"],"resultados":{}})
    Consumo.objects.create(execucao=e,modelo="ensaio",desconhecido=True,custo_estimado_usd=Decimal("0.228772"))
    assert sincronizar()
    d.refresh_from_db()
    assert "TEXTO DO ADMIN" in d.corpo and "0/1" in d.corpo and "0.228772" in d.corpo
    assert not d.publico and not d.publicacao_manual and "Rotina antiga: pausada" in d.corpo
    assert d.versoes.count()==2
    assert not sincronizar() and d.versoes.count()==2
    d.corpo += "\nEDIÇÃO NOVA DO ADMIN";d.save()
    e.situacao=Execucao.Situacao.FALHOU;e.save()
    assert sincronizar()
    d.refresh_from_db()
    assert "EDIÇÃO NOVA DO ADMIN" in d.corpo and d.corpo.count(INICIO)==1
    assert "Falhou" in d.corpo and d.versoes.count()==3
    assert e.consumos.get().desconhecido

@pytest.mark.django_db
def test_nao_cria_nem_desarquiva_documento():
    assert not sincronizar() and not Documento.objects.filter(nome=NOME).exists()
    d=Documento.objects.create(nome=NOME,titulo="Arquivado",corpo="PRESERVADO",arquivado=True)
    assert not sincronizar()
    d.refresh_from_db();assert d.corpo=="PRESERVADO" and d.arquivado and not d.versoes.exists()
