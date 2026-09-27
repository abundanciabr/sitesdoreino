"""Guardas da COMUNIDADE VISTA PELA EQUIPE (TAR-827, 27/09/2026).

A equipe abre uma página só e vê, por grupo de prática, quem responde por ele,
quantas vagas estão ocupadas, as dúvidas que esperam resposta aceita (a mais
antiga primeiro) e quem entrou no grupo e ainda não escreveu. Toda espera
aponta para o responsável do grupo. Para quem não é da escola a página não
existe: 404, nunca 403.

O mundo e a rede das células vizinhas são montados pelas mesmas peças de
`test_grupo_de_pratica.py`, que é o molde destes testes.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core import views
from apps.forum.models import Area, MembroDoGrupo, Mensagem, Topico

from test_grupo_de_pratica import (  # noqa: F401 (fixtures)
    ana,
    bia,
    como,
    dublar,
    duvida,
    env,
    grupo,
    novo_grupo,
    pedir,
    professora,
    vincular,
)

pytestmark = pytest.mark.django_db


def vista(client):
    return pedir(client, "comunidade_da_equipe")


def test_quem_nao_e_da_escola_recebe_404(
    client, env, monkeypatch, grupo, ana, professora
):
    vincular(grupo, ana, professora)

    como(monkeypatch, ana)
    assert vista(client).status_code == 404

    como(monkeypatch, ana, categoria="cadastrado")
    assert vista(client).status_code == 404

    dublar(monkeypatch, sessao={"autenticado": False})
    assert vista(client).status_code == 404


def test_a_equipe_ve_o_grupo_o_responsavel_e_as_vagas_sem_email_na_tela(
    client, env, monkeypatch, grupo, ana, bia, professora
):
    vincular(grupo, ana, professora)
    saiu = vincular(grupo, bia, professora)
    MembroDoGrupo.objects.filter(pk=saiu.pk).update(
        ate=timezone.now(), removido_por=professora
    )

    como(monkeypatch, professora, categoria="cadastrado")
    resposta = vista(client)
    corpo = resposta.content.decode()

    assert resposta.status_code == 200
    assert grupo.nome in corpo
    assert "Responsável: Profa. Lia" in corpo
    assert "1 de 10 vagas" in corpo
    assert reverse("membros_do_grupo", args=[grupo.slug]) in corpo
    assert "@exemplo.com" not in corpo


def test_as_duvidas_abertas_vem_da_mais_antiga_para_a_mais_nova_com_quem_responde(
    client, env, monkeypatch, grupo, ana, bia, professora
):
    vincular(grupo, ana, professora)
    vincular(grupo, bia, professora)
    agora = timezone.now()
    nova = duvida(grupo, bia, "Duvida nova da Bia", "a")
    antiga = duvida(grupo, ana, "Duvida antiga da Ana", "b")
    resolvida = duvida(grupo, bia, "Duvida resolvida da Bia", "c")
    trancada = duvida(grupo, bia, "Duvida trancada da Bia", "d")
    Topico.objects.filter(pk=nova.pk).update(criado_em=agora - timedelta(hours=5))
    Topico.objects.filter(pk=antiga.pk).update(criado_em=agora - timedelta(days=3))
    certa = Mensagem.objects.create(topico=resolvida, autor=ana, texto="ok")
    Topico.objects.filter(pk=resolvida.pk).update(resposta_aceita=certa)
    Topico.objects.filter(pk=trancada.pk).update(trancado=True)

    como(monkeypatch, professora, categoria="cadastrado")
    corpo = vista(client).content.decode()

    assert corpo.index("Duvida antiga da Ana") < corpo.index("Duvida nova da Bia")
    assert "esperando há 3 dias" in corpo
    assert "esperando há 5 horas" in corpo
    assert "Duvida resolvida da Bia" not in corpo
    assert "Duvida trancada da Bia" not in corpo
    assert corpo.count("Quem responde: Profa. Lia") >= 2


def test_quem_entrou_e_nao_escreveu_aparece_no_acolhimento_e_some_quando_escreve(
    client, env, monkeypatch, grupo, ana, bia, professora
):
    vinculo = vincular(grupo, bia, professora)
    MembroDoGrupo.objects.filter(pk=vinculo.pk).update(
        desde=timezone.now() - timedelta(days=2)
    )
    vincular(grupo, ana, professora)
    duvida(grupo, ana, "Oi, sou a Ana", "cheguei")

    como(monkeypatch, professora, categoria="cadastrado")
    resposta = vista(client)
    [visto] = resposta.context["grupos"]
    assert [v.pessoa for v in visto.acolhimento] == [bia]
    assert "Bia entrou há 2 dias" in resposta.content.decode()

    duvida(grupo, bia, "Oi, sou a Bia", "cheguei")
    resposta = vista(client)
    [visto] = resposta.context["grupos"]
    assert visto.acolhimento == []
    assert "Bia entrou" not in resposta.content.decode()


def test_grupo_sem_responsavel_diz_que_a_espera_nao_tem_dono(
    client, env, monkeypatch, ana, professora
):
    orfao = novo_grupo("grupo-orfao", professora)
    Area.objects.filter(pk=orfao.pk).update(responsavel=None)
    vincular(orfao, ana, professora)
    duvida(orfao, ana, "Duvida sem dono", "a")

    como(monkeypatch, professora, categoria="cadastrado")
    corpo = vista(client).content.decode()

    assert "Responsável: ninguém definido" in corpo
    assert "Quem responde: ninguém definido" in corpo


def test_os_tres_estados_vazios_tem_texto(client, env, monkeypatch, professora):
    como(monkeypatch, professora, categoria="cadastrado")
    assert "Ainda não existe nenhum grupo de prática" in (
        vista(client).content.decode()
    )

    novo_grupo("grupo-vazio", professora)
    corpo = vista(client).content.decode()
    assert "Ninguém no grupo ainda" in corpo
    assert "Nenhuma dúvida esperando resposta neste grupo" in corpo


def test_o_grupo_arquivado_nao_entra_e_o_grupo_cheio_e_marcado(
    client, env, monkeypatch, ana, professora
):
    cheio = novo_grupo("grupo-cheio", professora, vagas=1)
    vincular(cheio, ana, professora)
    arquivado = novo_grupo("grupo-arquivado", professora)
    Area.objects.filter(pk=arquivado.pk).update(ativa=False)

    como(monkeypatch, professora, categoria="cadastrado")
    corpo = vista(client).content.decode()

    assert "1 de 1 vaga." in corpo
    assert "sem vaga" in corpo
    assert arquivado.nome not in corpo


def test_as_filas_das_outras_celulas_sao_links_e_nao_numeros(
    client, env, monkeypatch, professora
):
    como(monkeypatch, professora, categoria="cadastrado")
    corpo = vista(client).content.decode()
    assert f'href="{views.PLANTAO_DE_LAUDOS}"' in corpo
    assert f'href="{views.FILA_DE_VALIDACAO}"' in corpo


def test_a_capa_leva_a_equipe_a_vista_e_esconde_o_link_do_aluno(
    client, env, monkeypatch, ana, professora
):
    como(monkeypatch, ana)
    assert reverse("comunidade_da_equipe") not in pedir(client, "home").content.decode()
    como(monkeypatch, professora, categoria="cadastrado")
    assert reverse("comunidade_da_equipe") in pedir(client, "home").content.decode()
