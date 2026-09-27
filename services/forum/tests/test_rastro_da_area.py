"""Guardas do RASTRO DOS GESTOS SOBRE A ÁREA INTEIRA (TAR-867, 27/09/2026).

O registro da moderação anotava o que a escola fazia numa conversa,
numa mensagem ou num grupo, mas esquecia os gestos sobre a área inteira:
arquivar, reabrir, trocar o nome e mudar quem enxerga ou quem escreve. Deixar
aberta ao mundo uma área que era fechada é o mais sério deles.

Agora cada um deixa uma linha, na mesma transação do gesto, com o antes e o
depois. Arquivar, reabrir e mudar quem enxerga ou escreve pedem motivo, e quem
recusa a linha sem ele é o PostgreSQL. Vale para toda área, seja grupo de
prática ou não.
"""

from __future__ import annotations

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.urls import reverse
from django.utils import timezone

from apps.core import moderacao
from apps.forum.models import AcaoDeModeracao, Area, RegistroDeModeracao

from test_grupo_de_pratica import (  # noqa: F401 (fixtures)
    COOKIE,
    como,
    env,
    grupo,
    professora,
)

pytestmark = pytest.mark.django_db

Acao = AcaoDeModeracao
MOTIVO = "turma de setembro encerrada"

ANTES_DO_RASTRO_DA_AREA = ("forum", "0010_registro_de_moderacao")


@pytest.fixture
def duvidas():
    """Uma área que NÃO é grupo: o rastro vale para ela também."""
    return Area.objects.create(
        slug="duvidas",
        nome="Dúvidas",
        visibilidade=Area.Visibilidade.ALUNOS,
        quem_escreve=Area.QuemEscreve.EQUIPE,
    )


def na_area(client, area, **dados):
    return client.post(
        reverse("moderar_area", args=[area.slug]), dados, headers={"cookie": COOKIE}
    )


def editar(client, area, **dados):
    campos = {
        "acao": "salvar",
        "nome": area.nome,
        "descricao": area.descricao,
        "visibilidade": area.visibilidade,
        "quem_escreve": area.quem_escreve,
        "curso_id": area.curso_id,
        "responsavel": area.responsavel_id or "",
        "vagas": str(area.vagas),
    }
    campos.update(dados)
    return na_area(client, area, **campos)


def linhas():
    return list(RegistroDeModeracao.objects.order_by("pk"))


def unica_linha():
    """A única linha do registro. Duas linhas para um gesto é defeito."""
    todas = linhas()
    assert len(todas) == 1, [(l.acao, l.detalhe) for l in todas]
    return todas[0]


# ------------------------------------------------------------ arquivar e reabrir


@pytest.mark.parametrize("qual", ["grupo", "duvidas"])
def test_arquivar_e_reabrir_gravam_uma_linha_com_quem_quando_e_por_que(
    request, client, env, monkeypatch, professora, qual
):
    area = request.getfixturevalue(qual)
    como(monkeypatch, professora, categoria="cadastrado")

    antes = timezone.now()
    assert na_area(client, area, acao="arquivar", motivo=MOTIVO).status_code == 302
    area.refresh_from_db()
    assert area.ativa is False
    linha = unica_linha()
    assert (linha.acao, linha.ator, linha.area, linha.motivo) == (
        Acao.ARQUIVAR_AREA,
        professora,
        area,
        MOTIVO,
    )
    assert antes <= linha.quando <= timezone.now()
    assert area.nome in linha.detalhe

    assert (
        na_area(client, area, acao="reabrir", motivo="pedido da turma").status_code
        == 302
    )
    area.refresh_from_db()
    assert area.ativa is True
    reabriu = linhas()[-1]
    assert (reabriu.acao, reabriu.motivo) == (Acao.REABRIR_AREA, "pedido da turma")


@pytest.mark.parametrize("acao", ["arquivar", "reabrir"])
def test_arquivar_ou_reabrir_sem_motivo_e_recusado_e_nada_muda(
    client, env, monkeypatch, duvidas, professora, acao
):
    duvidas.ativa = acao == "arquivar"
    duvidas.save()
    como(monkeypatch, professora, categoria="cadastrado")

    resposta = na_area(client, duvidas, acao=acao, motivo="   ")

    assert resposta.status_code == 400
    assert moderacao.ERRO_MOTIVO_DA_ACAO in resposta.content.decode()
    assert Area.objects.get(pk=duvidas.pk).ativa == (acao == "arquivar")
    assert not RegistroDeModeracao.objects.exists()


# ------------------------------------------------------------ editar a área


def test_renomear_guarda_o_nome_de_antes_e_o_de_depois_sem_pedir_motivo(
    client, env, monkeypatch, duvidas, professora
):
    como(monkeypatch, professora, categoria="cadastrado")
    assert editar(client, duvidas, nome="Dúvidas de textura").status_code == 302

    linha = unica_linha()
    assert linha.acao == Acao.RENOMEAR_AREA
    assert linha.detalhe == 'de "Dúvidas" para "Dúvidas de textura"'
    assert linha.motivo == ""


def test_abrir_ao_mundo_uma_area_fechada_exige_motivo_e_guarda_o_antes_e_o_depois(
    client, env, monkeypatch, duvidas, professora
):
    como(monkeypatch, professora, categoria="cadastrado")

    recusa = editar(client, duvidas, visibilidade="publica")
    assert recusa.status_code == 400
    assert moderacao.ERRO_MOTIVO_DA_ACAO in recusa.content.decode()
    assert Area.objects.get(pk=duvidas.pk).visibilidade == Area.Visibilidade.ALUNOS
    assert not RegistroDeModeracao.objects.exists()

    resposta = editar(client, duvidas, visibilidade="publica", motivo=MOTIVO)
    assert resposta.status_code == 302
    assert Area.objects.get(pk=duvidas.pk).visibilidade == Area.Visibilidade.PUBLICA

    linha = unica_linha()
    assert linha.acao == Acao.MUDAR_ACESSO_DA_AREA
    assert linha.motivo == MOTIVO
    assert linha.detalhe == (
        f'quem enxerga de "{Area.Visibilidade.ALUNOS.label}" '
        f'para "{Area.Visibilidade.PUBLICA.label}"'
    )


def test_mudar_quem_escreve_exige_motivo(client, env, monkeypatch, duvidas, professora):
    como(monkeypatch, professora, categoria="cadastrado")

    recusa = editar(client, duvidas, quem_escreve="aluno")
    assert recusa.status_code == 400
    assert Area.objects.get(pk=duvidas.pk).quem_escreve == Area.QuemEscreve.EQUIPE
    assert not RegistroDeModeracao.objects.exists()

    assert (
        editar(client, duvidas, quem_escreve="aluno", motivo=MOTIVO).status_code == 302
    )
    linha = unica_linha()
    assert linha.acao == Acao.MUDAR_ACESSO_DA_AREA
    assert linha.detalhe == (
        f'quem escreve de "{Area.QuemEscreve.EQUIPE.label}" '
        f'para "{Area.QuemEscreve.ALUNO.label}"'
    )


def test_renomear_e_mudar_o_acesso_juntos_viram_duas_linhas_com_o_mesmo_motivo(
    client, env, monkeypatch, duvidas, professora
):
    como(monkeypatch, professora, categoria="cadastrado")
    resposta = editar(
        client,
        duvidas,
        nome="Perguntas abertas",
        visibilidade="publica",
        motivo=MOTIVO,
    )
    assert resposta.status_code == 302
    assert [(l.acao, l.motivo) for l in linhas()] == [
        (Acao.RENOMEAR_AREA, MOTIVO),
        (Acao.MUDAR_ACESSO_DA_AREA, MOTIVO),
    ]


def test_salvar_a_area_sem_mudar_nada_nao_inventa_linha(
    client, env, monkeypatch, grupo, duvidas, professora
):
    como(monkeypatch, professora, categoria="cadastrado")
    assert editar(client, duvidas, descricao="Pergunte aqui").status_code == 302
    assert editar(client, grupo).status_code == 302
    assert not RegistroDeModeracao.objects.exists()


# ------------------------------------------------------------ a rede do banco


@pytest.mark.parametrize(
    "acao", [Acao.ARQUIVAR_AREA, Acao.REABRIR_AREA, Acao.MUDAR_ACESSO_DA_AREA]
)
def test_o_banco_recusa_o_gesto_na_area_sem_motivo(duvidas, professora, acao):
    with pytest.raises(IntegrityError), transaction.atomic():
        RegistroDeModeracao.objects.create(ator=professora, acao=acao, area=duvidas)


def test_o_gesto_na_area_nasce_na_mesma_transacao_da_linha(
    client, env, monkeypatch, duvidas, professora
):
    """Se a linha não pode ser gravada, a área também não muda."""

    def banco_recusa(self, *args, **kwargs):
        raise IntegrityError("simulado")

    monkeypatch.setattr(RegistroDeModeracao, "save", banco_recusa)
    como(monkeypatch, professora, categoria="cadastrado")

    assert na_area(client, duvidas, acao="arquivar", motivo=MOTIVO).status_code == 400
    assert (
        editar(client, duvidas, visibilidade="publica", motivo=MOTIVO).status_code
        == 400
    )
    depois = Area.objects.get(pk=duvidas.pk)
    assert (depois.ativa, depois.visibilidade) == (True, Area.Visibilidade.ALUNOS)


# ------------------------------------------------------------ a migração


def _migrar_para(alvo=None):
    """Sem alvo, volta à última migração do fórum, seja ela qual for."""
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate([alvo] if alvo else executor.loader.graph.leaf_nodes("forum"))


@pytest.mark.django_db(transaction=True)
def test_a_migracao_troca_as_restricoes_sem_perder_linha(duvidas, professora):
    _migrar_para(ANTES_DO_RASTRO_DA_AREA)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO forum_registrodemoderacao"
                " (ator_id, acao, area_id, detalhe, motivo, quando)"
                " VALUES (%s, 'trancar', %s, '', '', now())",
                [professora.pk, duvidas.pk],
            )
            with pytest.raises(IntegrityError), transaction.atomic():
                cursor.execute(
                    "INSERT INTO forum_registrodemoderacao"
                    " (ator_id, acao, area_id, detalhe, motivo, quando)"
                    " VALUES (%s, 'arquivar_area', %s, '', 'x', now())",
                    [professora.pk, duvidas.pk],
                )
    finally:
        _migrar_para()

    assert [l.acao for l in linhas()] == [Acao.TRANCAR]
    RegistroDeModeracao.objects.create(
        ator=professora, acao=Acao.ARQUIVAR_AREA, area=duvidas, motivo=MOTIVO
    )
    assert len(linhas()) == 2
