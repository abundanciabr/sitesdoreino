from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from apps.cursos import envio
from apps.cursos.models import Aula, Bloco, Curso, Envio


class FilaFalsa:
    def __init__(self, quantidade, primeira):
        self.quantidade, self.primeira = quantidade, primeira

    def aggregate(self, **kwargs):
        return {"quantidade": self.quantidade, "primeira": self.primeira}


@pytest.mark.parametrize("quantidade,idade", [(0, None), (4, 2)])
def test_resumo_autenticado_sem_dados_pessoais(settings, monkeypatch, quantidade, idade):
    settings.TOKENS_ACEITOS = {"par-admin"}
    chamados = []
    primeira = timezone.now() - timedelta(days=idade) if idade is not None else None
    monkeypatch.setattr(envio, "fila_de_revisao", lambda site: chamados.append(site) or FilaFalsa(quantidade, primeira))
    url = "/api/cursos/pendencias/escola-a"
    assert Client().get(url).status_code == 401
    assert Client().get(url, HTTP_AUTHORIZATION="Bearer errado").status_code == 401
    resposta = Client().get(url, HTTP_AUTHORIZATION="Bearer par-admin")
    assert resposta.status_code == 200
    esperado = (timezone.localdate() - timezone.localtime(primeira).date()).days if primeira else None
    assert resposta.json() == {"quantidade": quantidade, "espera_ha_dias": esperado}
    assert chamados == ["escola-a"]


@pytest.mark.django_db
def test_resumo_conta_so_envios_aguardando_do_site(settings, ana_pronta):
    settings.TOKENS_ACEITOS = {"par-admin"}
    url = "/api/cursos/pendencias/escola-a"
    assert Client().get(url, HTTP_AUTHORIZATION="Bearer par-admin").json() == {
        "quantidade": 0, "espera_ha_dias": None
    }
    aberto = Envio.objects.create(
        pessoa=ana_pronta.pessoa, aula=ana_pronta.aula, numero=1, links=[]
    )
    Envio.objects.create(
        pessoa=ana_pronta.pessoa, aula=ana_pronta.aula, numero=2, links=[],
        estado=Envio.Estado.ABERTO,
    )
    outro_curso = Curso.objects.create(site_id="escola-b", slug="outro", nome="Outro")
    outro_bloco = Bloco.objects.create(curso=outro_curso, ordem=1, letra="A", parte=1)
    outra_aula = Aula.objects.create(
        curso=outro_curso, bloco=outro_bloco, ordem=1, numero="1", titulo_exibido="Outra"
    )
    Envio.objects.create(
        pessoa=ana_pronta.pessoa, aula=outra_aula, numero=1, links=[]
    )
    resposta = Client().get(url, HTTP_AUTHORIZATION="Bearer par-admin")
    assert resposta.status_code == 200
    assert resposta.json() == {
        "quantidade": 1,
        "espera_ha_dias": (timezone.localdate() - timezone.localtime(aberto.enviado_em).date()).days,
    }
