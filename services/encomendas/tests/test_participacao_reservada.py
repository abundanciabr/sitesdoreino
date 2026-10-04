"""A preparação fecha também as entradas antigas e preserva seus registros."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.encomendas import marketplace, motor, mural, tique
from apps.encomendas.models import Oferta


@pytest.mark.django_db
def test_selecao_individual_nao_abre_motor_antigo_na_preparacao(semeado, criar_perfil, criar_encomenda):
    agora = timezone.now()
    perfil = criar_perfil("aluno-reservado", entrada=agora - timedelta(days=30))
    pedido = criar_encomenda()
    marketplace.autorizar_aluno(site_id=semeado, pessoa_id=perfil.pessoa_id, ativa=True, quem="equipe")
    assert motor.candidatos_do_banco(semeado) == ()
    motor.rodar(agora, site_id=semeado)
    tique.rodar(agora, site_id=semeado)
    assert not Oferta.objects.filter(encomenda=pedido).exists()
    assert not mural.listar(perfil.pk, agora, site_id=semeado)
    pedido.refresh_from_db()
    assert pedido.status == "na_fila"


@pytest.mark.django_db
def test_api_antiga_nao_revela_fila_ou_pecas_antes_da_liberacao(client, settings, monkeypatch, criar_perfil):
    settings.TOKENS_ACEITOS = {"token-do-teste"}
    monkeypatch.setenv("SITE_ID", "escola-a")
    perfil = criar_perfil("aluno-reservado", entrada=timezone.now() - timedelta(days=2), entregas=7)
    marketplace.autorizar_aluno(site_id="escola-a", pessoa_id=perfil.pessoa_id, ativa=True, quem="equipe")
    headers = {"HTTP_AUTHORIZATION": "Bearer token-do-teste"}
    fila = client.get(f"/api/encomendas/perfis/{perfil.pessoa_id}/fila", **headers)
    pecas = client.get(f"/api/encomendas/perfis/{perfil.pessoa_id}/pecas-aprovadas", **headers)
    assert fila.status_code == 200 and fila.json()["existe"] is False
    assert pecas.status_code == 200 and pecas.json() == {"entregas": 0, "no_prazo": 0, "pecas": []}
    perfil.refresh_from_db()
    assert perfil.entregas_aprovadas == 7


@pytest.mark.django_db
def test_fase_aberta_nao_seleciona_aluno_e_cliente_nao_da_permissao_aluno(semeado, criar_perfil):
    perfil = criar_perfil("aluno-reservado", entrada=timezone.now() - timedelta(days=2))
    marketplace.configurar_fase(site_id=semeado, quem="equipe", alunos_liberados=True, clientes_liberados=True)
    marketplace.autorizar_cliente(site_id=semeado, cliente_id=perfil.pessoa_id, ativa=True, quem="equipe")
    assert marketplace.acesso_cliente(site_id=semeado, cliente_id=perfil.pessoa_id)
    assert motor.candidatos_do_banco(semeado) == ()
    assert not marketplace.acesso_aluno(site_id=semeado, pessoa_id=perfil.pessoa_id)
