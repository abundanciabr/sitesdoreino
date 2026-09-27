"""Guardas da TROCA DE GRUPO (TAR-847, 27/09/2026).

Antes, mudar um aluno de grupo eram dois gestos: tirar de um e pôr no outro. No
meio do caminho ele ficava sem grupo nenhum, e se o segundo gesto falhasse (sem
vaga, por exemplo) ele ficava de fora sem ninguém perceber. Agora é um gesto só,
numa transação: fecha o vínculo no grupo de origem e abre no de destino, ou não
muda nada. A leitura, a busca e a página Comunidade seguem o vínculo no mesmo
instante, e o que o aluno escreveu no grupo antigo continua com o nome dele.

O mundo e a rede das células vizinhas são montados pelas mesmas peças de
`test_grupo_de_pratica.py`.
"""

from __future__ import annotations

import pytest
from django.test import Client
from django.urls import reverse

from apps.core import moderacao
from apps.forum.models import (
    AcaoDeModeracao,
    Area,
    MembroDoGrupo,
    RegistroDeModeracao,
    Topico,
)

from test_grupo_de_pratica import (  # noqa: F401 (fixtures)
    ana,
    bia,
    como,
    dublar,
    duvida,
    env,
    gerir,
    grupo,
    novo_grupo,
    outro_grupo,
    pedir,
    professora,
    vincular,
)

pytestmark = pytest.mark.django_db

MOTIVO = "mudou para o turno da tarde"


def trocar(client, origem, vinculo, destino, motivo=MOTIVO):
    return gerir(
        client,
        origem,
        acao="trocar",
        vinculo_id=vinculo.pk,
        destino=destino.pk,
        motivo=motivo,
    )


def ativos(grupo):
    return MembroDoGrupo.objects.filter(grupo=grupo, ate__isnull=True)


def test_a_troca_fecha_a_origem_e_abre_o_destino_de_uma_vez(
    client, env, monkeypatch, grupo, outro_grupo, ana, professora
):
    vinculo = vincular(grupo, ana, professora)
    como(monkeypatch, professora, categoria="cadastrado")

    resposta = trocar(client, grupo, vinculo, outro_grupo)
    assert resposta.status_code == 302

    vinculo.refresh_from_db()
    novo = ativos(outro_grupo).get(pessoa=ana)
    assert vinculo.removido_por == professora
    assert novo.adicionado_por == professora
    assert novo.motivo == MOTIVO
    # O mesmo instante: não existe janela em que ela esteja em grupo nenhum.
    assert vinculo.ate == novo.desde
    assert not ativos(grupo).filter(pessoa=ana).exists()

    linha = RegistroDeModeracao.objects.get()
    assert linha.acao == AcaoDeModeracao.TROCAR_DE_GRUPO
    assert (linha.area, linha.area_destino, linha.vinculo) == (grupo, outro_grupo, novo)
    assert linha.ator == professora
    assert linha.motivo == MOTIVO


def test_sem_vaga_no_destino_nada_muda_na_origem(
    client, env, monkeypatch, grupo, ana, bia, professora
):
    cheio = novo_grupo("grupo-cheio", professora, vagas=1)
    vincular(cheio, bia, professora)
    vinculo = vincular(grupo, ana, professora)
    como(monkeypatch, professora, categoria="cadastrado")

    resposta = trocar(client, grupo, vinculo, cheio)
    assert resposta.status_code == 400
    assert moderacao.ERRO_DESTINO_SEM_VAGA in resposta.content.decode()
    vinculo.refresh_from_db()
    assert vinculo.ate is None
    assert not ativos(cheio).filter(pessoa=ana).exists()
    assert not RegistroDeModeracao.objects.exists()


def test_sem_motivo_a_troca_e_recusada(
    client, env, monkeypatch, grupo, outro_grupo, ana, professora
):
    vinculo = vincular(grupo, ana, professora)
    como(monkeypatch, professora, categoria="cadastrado")
    resposta = trocar(client, grupo, vinculo, outro_grupo, motivo="  ")
    assert resposta.status_code == 400
    assert moderacao.ERRO_MOTIVO_DA_ACAO in resposta.content.decode()
    vinculo.refresh_from_db()
    assert vinculo.ate is None
    assert not ativos(outro_grupo).exists()


@pytest.mark.parametrize("destino", ["o_mesmo", "area_de_alunos", "inexistente"])
def test_destino_que_nao_e_outro_grupo_e_recusado(
    client, env, monkeypatch, grupo, ana, professora, destino
):
    vinculo = vincular(grupo, ana, professora)
    alunos = Area.objects.create(
        slug="duvidas",
        nome="Dúvidas",
        visibilidade=Area.Visibilidade.ALUNOS,
        quem_escreve=Area.QuemEscreve.ALUNO,
    )
    destino_id = {"o_mesmo": grupo.pk, "area_de_alunos": alunos.pk}.get(destino, 99999)
    como(monkeypatch, professora, categoria="cadastrado")
    resposta = gerir(
        client,
        grupo,
        acao="trocar",
        vinculo_id=vinculo.pk,
        destino=destino_id,
        motivo=MOTIVO,
    )
    assert resposta.status_code == 400
    assert moderacao.ERRO_DESTINO_INVALIDO in resposta.content.decode()
    vinculo.refresh_from_db()
    assert vinculo.ate is None


def test_quem_ja_esta_no_destino_nao_ganha_segundo_vinculo(
    client, env, monkeypatch, grupo, outro_grupo, ana, professora
):
    vinculo = vincular(grupo, ana, professora)
    vincular(outro_grupo, ana, professora)
    como(monkeypatch, professora, categoria="cadastrado")
    resposta = trocar(client, grupo, vinculo, outro_grupo)
    assert resposta.status_code == 400
    assert moderacao.ERRO_JA_NO_DESTINO in resposta.content.decode()
    vinculo.refresh_from_db()
    assert vinculo.ate is None


def test_leitura_busca_e_comunidade_seguem_a_troca_e_a_autoria_fica(
    client, env, monkeypatch, grupo, outro_grupo, ana, bia, professora
):
    vinculo = vincular(grupo, ana, professora)
    vincular(grupo, bia, professora)
    vincular(outro_grupo, bia, professora)
    dela = duvida(grupo, ana, "Meu rig do dragão", "o rig do dragão quebra")
    da_bia_em_a = duvida(grupo, bia, "Pergunta da Bia no azul", "a")
    da_bia_em_b = duvida(outro_grupo, bia, "Pergunta da Bia no verde", "b")

    como(monkeypatch, ana)
    assert "Pergunta da Bia no azul" in pedir(client, "comunidade").content.decode()

    como(monkeypatch, professora, categoria="cadastrado")
    assert trocar(client, grupo, vinculo, outro_grupo).status_code == 302

    como(monkeypatch, ana)
    assert pedir(client, "area", grupo.slug).status_code == 404
    assert pedir(client, "topico", dela.pk).status_code == 404
    assert pedir(client, "topico", da_bia_em_a.pk).status_code == 404
    assert (
        "Meu rig do dragão" not in pedir(client, "buscar", q="dragão").content.decode()
    )
    assert pedir(client, "area", outro_grupo.slug).status_code == 200
    assert pedir(client, "topico", da_bia_em_b.pk).status_code == 200
    comunidade = pedir(client, "comunidade").content.decode()
    assert "Pergunta da Bia no verde" in comunidade
    assert "Pergunta da Bia no azul" not in comunidade

    dela = Topico.objects.get(pk=dela.pk)
    assert dela.autor == ana
    assert dela.area == grupo
    assert dela.mensagens.get().autor == ana


def test_quem_nao_e_equipe_recebe_404_na_troca(
    client, env, monkeypatch, grupo, outro_grupo, ana, professora
):
    vinculo = vincular(grupo, ana, professora)
    como(monkeypatch, ana)
    assert trocar(client, grupo, vinculo, outro_grupo).status_code == 404
    dublar(monkeypatch, sessao={"autenticado": False})
    assert trocar(client, grupo, vinculo, outro_grupo).status_code == 404
    vinculo.refresh_from_db()
    assert vinculo.ate is None
    assert not RegistroDeModeracao.objects.exists()


def test_a_tela_oferece_a_troca_e_ela_atravessa_o_csrf(
    env, monkeypatch, grupo, outro_grupo, ana, professora
):
    vinculo = vincular(grupo, ana, professora)
    como(monkeypatch, professora, categoria="cadastrado")
    navegador = Client(enforce_csrf_checks=True)
    navegador.cookies["meshcraft_sessao"] = "um-cookie-opaco-qualquer"
    endereco = reverse("membros_do_grupo", args=[grupo.slug])
    dados = {
        "acao": "trocar",
        "vinculo_id": vinculo.pk,
        "destino": outro_grupo.pk,
        "motivo": MOTIVO,
    }

    assert navegador.post(endereco, dados).status_code == 403

    corpo = navegador.get(endereco).content.decode()
    assert 'value="trocar"' in corpo
    assert f'<option value="{outro_grupo.pk}"' in corpo
    token = corpo.split('name="csrfmiddlewaretoken" value="', 1)[1].split('"', 1)[0]
    resposta = navegador.post(endereco, {**dados, "csrfmiddlewaretoken": token})
    assert resposta.status_code == 302, resposta.content[:400]
    assert ativos(outro_grupo).filter(pessoa=ana).exists()
