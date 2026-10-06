from decimal import Decimal

import pytest

from apps.agentes.models import Consumo, Execucao, RoboPessoal
from apps.core.super_equipe_placar import resumo_da_super_equipe
from apps.core.models import MembroDaEquipe


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
