from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from apps.gamificacao import validacao
from apps.gamificacao.models import PedidoDeValidacao, Pessoa


class FilaFalsa:
    def __init__(self, quantidade, primeira):
        self.quantidade, self.primeira = quantidade, primeira

    def aggregate(self, **kwargs):
        return {"quantidade": self.quantidade, "primeira": self.primeira}


@pytest.mark.parametrize("quantidade,idade", [(0, None), (2, 3)])
def test_resumo_autenticado_sem_dados_pessoais(settings, monkeypatch, quantidade, idade):
    settings.TOKENS_ACEITOS = {"par-admin"}
    chamados = []
    primeira = timezone.now() - timedelta(days=idade) if idade is not None else None
    monkeypatch.setattr(validacao, "fila_da_equipe", lambda site: chamados.append(site) or FilaFalsa(quantidade, primeira))
    url = "/api/gamificacao/pendencias/escola-a"
    assert Client().get(url).status_code == 401
    assert Client().get(url, HTTP_AUTHORIZATION="Bearer errado").status_code == 401
    resposta = Client().get(url, HTTP_AUTHORIZATION="Bearer par-admin")
    assert resposta.status_code == 200
    esperado = (timezone.localdate() - timezone.localtime(primeira).date()).days if primeira else None
    assert resposta.json() == {"quantidade": quantidade, "espera_ha_dias": esperado}
    assert chamados == ["escola-a"]


@pytest.mark.django_db
def test_resumo_conta_so_pedidos_abertos_do_site(settings):
    settings.TOKENS_ACEITOS = {"par-admin"}
    url = "/api/gamificacao/pendencias/escola-a"
    assert Client().get(url, HTTP_AUTHORIZATION="Bearer par-admin").json() == {
        "quantidade": 0, "espera_ha_dias": None
    }
    pessoa = Pessoa.objects.create(id_da_plataforma="pes-1", email="a@exemplo.com", nome_exibido="Ana")
    aberto = PedidoDeValidacao.objects.create(
        pessoa=pessoa, site_id="escola-a", tipo=PedidoDeValidacao.Tipo.MARCO,
        evidencia="prova", prazo_ate=timezone.now() + timedelta(days=5),
    )
    PedidoDeValidacao.objects.create(
        pessoa=pessoa, site_id="escola-a", tipo=PedidoDeValidacao.Tipo.OBRA,
        evidencia="outra", estado=PedidoDeValidacao.Estado.ACEITO,
        prazo_ate=timezone.now() + timedelta(days=5), respondido_em=timezone.now(),
    )
    PedidoDeValidacao.objects.create(
        pessoa=pessoa, site_id="escola-b", tipo=PedidoDeValidacao.Tipo.AJUDA,
        evidencia="terceira", prazo_ate=timezone.now() + timedelta(days=5),
    )
    resposta = Client().get(url, HTTP_AUTHORIZATION="Bearer par-admin")
    assert resposta.status_code == 200
    assert resposta.json() == {
        "quantidade": 1,
        "espera_ha_dias": (timezone.localdate() - timezone.localtime(aberto.criado_em).date()).days,
    }
