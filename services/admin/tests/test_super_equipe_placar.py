from decimal import Decimal

import pytest

from apps.agentes.models import Consumo, Execucao, RoboPessoal
from apps.core.super_equipe_placar import resumo_da_super_equipe
from apps.core.models import MembroDaEquipe
from apps.agentes import views
from django.test import RequestFactory
from unittest.mock import patch


@pytest.mark.django_db
def test_resumo_apenas_trabalhos_tecnicos_do_site():
    membro = MembroDaEquipe.objects.create(nome="Responsável")
    robo = RoboPessoal.objects.create(membro=membro, nome="Suporte da fila")
    trabalho = Execucao.objects.create(robo=robo, tipo=Execucao.Tipo.SUPER_EQUIPE,
        situacao=Execucao.Situacao.CONCLUIDA, estado={"site_id": "site-1"})
    Execucao.objects.create(robo=robo, tipo=Execucao.Tipo.SUPER_EQUIPE,
        estado={"site_id": "outro-site"})
    Execucao.objects.create(robo=robo, tipo=Execucao.Tipo.CONVERSA,
        estado={"site_id": "site-1"})
    Consumo.objects.create(execucao=trabalho, modelo="modelo-real",
                           custo_estimado_usd=Decimal("0.002"))
    resumo = resumo_da_super_equipe("site-1")
    assert resumo["total"] == resumo["concluidos"] == 1
    assert resumo["em_andamento"] == 0
    assert resumo["custo"] == Decimal("0.002")
    assert resumo["recentes"] == [trabalho]


@pytest.mark.django_db
def test_trabalho_tecnico_nao_vira_trabalho_pessoal_ou_acesso_do_dono():
    membro = MembroDaEquipe.objects.create(nome="Responsável")
    robo = RoboPessoal.objects.create(membro=membro, nome="Pessoal")
    tecnico = Execucao.objects.create(robo=robo, tipo=Execucao.Tipo.SUPER_EQUIPE)
    pessoal = Execucao.objects.create(robo=robo, tipo=Execucao.Tipo.PANORAMA)
    pedido = RequestFactory().get("/equipe/robo/")
    pedido.admin = {"equipe_apenas": True}
    with patch.object(views, "_membro_da_sessao", return_value=membro):
        assert views._execucao_visivel(pedido, tecnico.pk) is None
        assert views._execucao_visivel(pedido, pessoal.pk) == pessoal
    assert list(robo.execucoes.exclude(tipo__in=[Execucao.Tipo.CONVERSA,
                                                Execucao.Tipo.SUPER_EQUIPE])) == [pessoal]
