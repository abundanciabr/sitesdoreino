from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.encomendas import sandbox
from apps.encomendas.models import (
    ArquivoSandbox, MovimentoMeshcoin, ParticipacaoSandbox, ProjetoSandbox,
)


def projeto_configurado(site="escola-a", **mudancas):
    projeto = sandbox.semear_projetos(site_id=site)[0]
    projeto.prazo_dias = 2
    projeto.ajustes_previstos = 1
    projeto.recompensa = Decimal("12.50")
    for chave, valor in mudancas.items():
        setattr(projeto, chave, valor)
    projeto.save()
    return projeto


@pytest.mark.django_db
def test_catalogo_configuracao_aceite_snapshot_e_isolamento():
    projetos = sandbox.semear_projetos(site_id="escola-a")
    assert len(projetos) == 11
    assert len(sandbox.semear_projetos(site_id="escola-a")) == 11
    assert ProjetoSandbox.objects.filter(site_id="escola-a").count() == 11
    with pytest.raises(sandbox.ErroSandbox):
        sandbox.aceitar(site_id="escola-a", pessoa_id="ana", projeto_id=projetos[0].pk)
    projeto = projeto_configurado(recompensa=Decimal("0.00"))
    with pytest.raises(sandbox.ErroSandbox):
        sandbox.aceitar(site_id="escola-b", pessoa_id="ana", projeto_id=projeto.pk)
    p = sandbox.aceitar(site_id="escola-a", pessoa_id="ana", projeto_id=projeto.pk)
    assert p.termos["recompensa"] == "0.00"
    assert p.prazo_ate - p.aceite_em == timedelta(days=2)
    projeto.recompensa = Decimal("99.00")
    projeto.save(update_fields=["recompensa"])
    p.refresh_from_db()
    assert p.termos["recompensa"] == "0.00"
    with pytest.raises(sandbox.ErroSandbox):
        sandbox.aceitar(site_id="escola-a", pessoa_id="ana", projeto_id=projeto.pk)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ParticipacaoSandbox.objects.create(site_id="escola-a", pessoa_id="ana", projeto=projeto,
                termos=p.termos, aceite_em=timezone.now(), prazo_ate=timezone.now() + timedelta(days=2))


@pytest.mark.django_db
def test_rascunho_ajuste_aprovacao_idempotente_e_saldo():
    projeto = projeto_configurado()
    p = sandbox.aceitar(site_id="escola-a", pessoa_id="ana", projeto_id=projeto.pk)
    with pytest.raises(sandbox.ErroSandbox):
        sandbox.entregar(site_id="escola-a", participacao_id=p.pk, pessoa_id="ana", arquivos=[])
    arquivo = ArquivoSandbox.objects.create(site_id="escola-a", participacao=p, nome="modelo.blend", chave="sb/ana/modelo.blend",
        sha256="a" * 64, tamanho=150, mime="application/octet-stream")
    with pytest.raises(sandbox.ErroSandbox):
        sandbox.entregar(site_id="escola-a", participacao_id=p.pk, pessoa_id="outra", arquivos=[arquivo.pk])
    primeira = sandbox.entregar(site_id="escola-a", participacao_id=p.pk, pessoa_id="ana", arquivos=[arquivo.pk])
    assert primeira.versao == 1
    arquivo.refresh_from_db()
    assert arquivo.entrega_id == primeira.pk
    with pytest.raises(sandbox.ErroSandbox):
        sandbox.mensagem(site_id="escola-b", participacao_id=p.pk, ator_id="ana", papel="aluno", texto="Olá")
    with pytest.raises(sandbox.ErroSandbox):
        sandbox.mensagem(site_id="escola-a", participacao_id=p.pk, ator_id="outra", papel="aluno", texto="Olá")
    assert sandbox.mensagem(site_id="escola-a", participacao_id=p.pk, ator_id="ana", papel="aluno", texto="Olá").texto == "Olá"
    sandbox.pedir_ajuste(site_id="escola-a", participacao_id=p.pk, autor_id="equipe", texto="Melhore a luz")
    with pytest.raises(sandbox.ErroSandbox):
        sandbox.aprovar(site_id="escola-a", participacao_id=p.pk, aprovador_id="equipe")
    segunda = sandbox.entregar(site_id="escola-a", participacao_id=p.pk, pessoa_id="ana", arquivos=[dict(
        nome="render.png", chave="sb/ana/render.png", sha256="b" * 64, tamanho=200, mime="image/png")])
    assert segunda.versao == 2
    with pytest.raises(sandbox.ErroSandbox):
        sandbox.pedir_ajuste(site_id="escola-a", participacao_id=p.pk, autor_id="equipe", texto="Mais um")
    assert sandbox.aprovar(site_id="escola-a", participacao_id=p.pk, aprovador_id="equipe").status == "aprovado"
    sandbox.aprovar(site_id="escola-a", participacao_id=p.pk, aprovador_id="equipe")
    from apps.encomendas.models import OutboxMarketplace
    assert OutboxMarketplace.objects.filter(event="encomendas.sandbox-trabalho-concluido").count() == 1
    assert MovimentoMeshcoin.objects.filter(participacao=p).count() == 0
    assert sandbox.saldo(site_id="escola-a", pessoa_id="ana") == 0
    assert sandbox.saldo(site_id="escola-b", pessoa_id="ana") == 0
    assert not sandbox.historico(site_id="escola-a", pessoa_id="ana").exists()


@pytest.mark.django_db
def test_atraso_na_entrega_mas_nao_durante_revisao_e_recompensa_unica():
    projeto = projeto_configurado()
    p = sandbox.aceitar(site_id="escola-a", pessoa_id="ana", projeto_id=projeto.pk)
    ParticipacaoSandbox.objects.filter(pk=p.pk).update(prazo_ate=timezone.now() - timedelta(days=1))
    assert sandbox.registrar_atrasos(site_id="escola-a") == 1
    p.refresh_from_db()
    assert p.atraso_em is not None
    entrega = sandbox.entregar(site_id="escola-a", participacao_id=p.pk, pessoa_id="ana", arquivos=[dict(
        nome="a.png", chave="sb/a.png", sha256="a" * 64, tamanho=1, mime="image/png")])
    ParticipacaoSandbox.objects.filter(pk=p.pk).update(atraso_em=None)
    assert sandbox.registrar_atrasos(site_id="escola-a") == 0
    with transaction.atomic():
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                MovimentoMeshcoin.objects.create(participacao=p, pessoa_id="ana", site_id="escola-a", valor=1, aprovador_id="equipe")
                MovimentoMeshcoin.objects.create(participacao=p, pessoa_id="ana", site_id="escola-a", valor=1, aprovador_id="equipe")
    assert entrega.arquivos.count() == 1
