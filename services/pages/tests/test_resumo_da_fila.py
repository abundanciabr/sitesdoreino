from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from apps.portfolio import conferencia
from apps.portfolio.models import EstadoDoPedido, PedidoDeConferencia


class FilaFalsa:
    def __init__(self, quantidade, primeira):
        self.quantidade, self.primeira = quantidade, primeira

    def aggregate(self, **kwargs):
        return {"quantidade": self.quantidade, "primeira": self.primeira}


@pytest.mark.parametrize("quantidade,idade", [(0, None), (3, 4)])
def test_resumo_autenticado_sem_dados_pessoais(settings, monkeypatch, quantidade, idade):
    settings.TOKENS_ACEITOS = {"par-admin"}
    chamados = []
    primeira = timezone.now() - timedelta(days=idade) if idade is not None else None
    monkeypatch.setattr(conferencia, "fila_da_equipe", lambda site: chamados.append(site) or FilaFalsa(quantidade, primeira))
    url = "/interno/pendencias/escola-a"
    assert Client().get(url).status_code == 401
    assert Client().get(url, HTTP_AUTHORIZATION="Bearer errado").status_code == 401
    resposta = Client().get(url, HTTP_AUTHORIZATION="Bearer par-admin")
    assert resposta.status_code == 200
    esperado = (timezone.localdate() - timezone.localtime(primeira).date()).days if primeira else None
    assert resposta.json() == {"quantidade": quantidade, "espera_ha_dias": esperado}
    assert chamados == ["escola-a"]


@pytest.mark.django_db
def test_resumo_conta_so_pedidos_abertos_do_site(criar_portfolio, settings):
    settings.TOKENS_ACEITOS = {"par-admin"}
    assert Client().get("/interno/pendencias/escola-a", HTTP_AUTHORIZATION="Bearer par-admin").json() == {
        "quantidade": 0, "espera_ha_dias": None
    }
    prazo = conferencia.prazo_de()
    aberto = PedidoDeConferencia.objects.create(
        portfolio=criar_portfolio("aluno-1", site_id="escola-a"), prazo_ate=prazo
    )
    respondido = PedidoDeConferencia.objects.create(
        portfolio=criar_portfolio("aluno-2", site_id="escola-a"), prazo_ate=prazo
    )
    PedidoDeConferencia.objects.filter(pk=respondido.pk).update(
        estado=EstadoDoPedido.ACEITO, respondido_em=timezone.now(), respondido_por="equipe"
    )
    PedidoDeConferencia.objects.create(
        portfolio=criar_portfolio("aluno-3", site_id="escola-b"), prazo_ate=prazo
    )
    resposta = Client().get("/interno/pendencias/escola-a", HTTP_AUTHORIZATION="Bearer par-admin")
    assert resposta.status_code == 200
    assert resposta.json() == {
        "quantidade": 1,
        "espera_ha_dias": (timezone.localdate() - timezone.localtime(aberto.criado_em).date()).days,
    }
