"""Guardas do RASTRO DA MODERAÇÃO (TAR-847, 27/09/2026).

Cada gesto da escola sobre uma conversa, uma mensagem ou um grupo deixa UMA
linha em `RegistroDeModeracao`: quem fez, o quê, em quê, em que grupo, quando e
por quê. A linha nasce na mesma transação do gesto e ninguém a altera nem apaga
depois, nem pelo `update()` que fura o `save()` (`armadilhas/023`): quem recusa
é o PostgreSQL.

Os gestos que mexem no que outra pessoa vê ou escreveu pedem motivo, e a recusa
diz o que fazer. A vista da equipe mostra, por grupo, as últimas dez linhas.

O mundo e a rede das células vizinhas são montados pelas mesmas peças de
`test_grupo_de_pratica.py`.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.db import DatabaseError, IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from apps.core import moderacao
from apps.forum.models import (
    AcaoDeModeracao,
    MembroDoGrupo,
    Mensagem,
    Pessoa,
    RegistroDeModeracao,
    Topico,
)

from test_grupo_de_pratica import (  # noqa: F401 (fixtures)
    COOKIE,
    ana,
    bia,
    como,
    duvida,
    env,
    gerir,
    grupo,
    outro_grupo,
    pedir,
    professora,
    vincular,
)

pytestmark = pytest.mark.django_db

Acao = AcaoDeModeracao
MOTIVO = "link fora da lista permitida"


@pytest.fixture
def dono():
    return Pessoa.objects.create(
        id_da_plataforma="p_dono", email="dono@exemplo.com", nome_exibido="Davi"
    )


@pytest.fixture
def conversa(grupo, ana, professora):
    vincular(grupo, ana, professora)
    return duvida(grupo, ana, "Minha textura estica", "a textura do escudo estica")


def na_conversa(client, topico, **dados):
    return client.post(
        reverse("moderar_topico", args=[topico.pk]), dados, headers={"cookie": COOKIE}
    )


def na_mensagem(client, mensagem, **dados):
    return client.post(
        reverse("moderar_mensagem", args=[mensagem.pk]),
        dados,
        headers={"cookie": COOKIE},
    )


def no_grupo(client, grupo, **dados):
    campos = {
        "acao": "salvar",
        "nome": grupo.nome,
        "descricao": "",
        "visibilidade": "turma",
        "quem_escreve": "aluno",
        "curso_id": grupo.curso_id,
        "responsavel": grupo.responsavel_id,
        "vagas": str(grupo.vagas),
    }
    campos.update(dados)
    return client.post(
        reverse("moderar_area", args=[grupo.slug]), campos, headers={"cookie": COOKIE}
    )


def unica_linha():
    """A única linha do registro. Duas linhas para um gesto é defeito."""
    linhas = list(RegistroDeModeracao.objects.all())
    assert len(linhas) == 1, [(l.acao, l.detalhe) for l in linhas]
    return linhas[0]


def mensagem_de(topico):
    return Mensagem.objects.filter(topico=topico).first()


# ------------------------------------------------------------ uma linha por gesto


@pytest.mark.parametrize(
    "acao, motivo",
    [
        (Acao.FIXAR, ""),
        (Acao.DESAFIXAR, ""),
        (Acao.TRANCAR, ""),
        (Acao.DESTRANCAR, ""),
        (Acao.TIRAR_DO_AR, MOTIVO),
        (Acao.RESTAURAR, MOTIVO),
    ],
)
def test_cada_gesto_na_conversa_grava_uma_linha_com_quem_quando_e_por_que(
    client, env, monkeypatch, conversa, grupo, professora, acao, motivo
):
    como(monkeypatch, professora, categoria="cadastrado")
    antes = timezone.now()
    resposta = na_conversa(client, conversa, acao=acao, motivo=motivo)
    assert resposta.status_code == 302

    linha = unica_linha()
    assert linha.acao == acao
    assert linha.ator == professora
    assert linha.topico == conversa
    assert linha.area == grupo
    assert linha.motivo == motivo
    assert antes <= linha.quando <= timezone.now()
    assert conversa.titulo in linha.detalhe


def test_mover_grava_a_origem_e_o_destino(
    client, env, monkeypatch, conversa, grupo, outro_grupo, professora
):
    como(monkeypatch, professora, categoria="cadastrado")
    resposta = na_conversa(
        client,
        conversa,
        acao="salvar",
        titulo=conversa.titulo,
        area_id=outro_grupo.pk,
        motivo="é assunto do grupo verde",
    )
    assert resposta.status_code == 302

    linha = unica_linha()
    assert linha.acao == Acao.MOVER
    assert linha.area == grupo
    assert linha.area_destino == outro_grupo
    assert linha.motivo == "é assunto do grupo verde"
    assert grupo.nome in linha.detalhe and outro_grupo.nome in linha.detalhe


def test_editar_o_titulo_alheio_guarda_o_titulo_de_antes(
    client, env, monkeypatch, conversa, professora
):
    como(monkeypatch, professora, categoria="cadastrado")
    resposta = na_conversa(
        client,
        conversa,
        acao="salvar",
        titulo="A textura estica no braço",
        motivo="título mais claro",
    )
    assert resposta.status_code == 302

    linha = unica_linha()
    assert linha.acao == Acao.EDITAR_TOPICO
    assert "Minha textura estica" in linha.detalhe
    assert "A textura estica no braço" in linha.detalhe


def test_salvar_sem_mudar_nada_nao_inventa_linha(
    client, env, monkeypatch, conversa, professora
):
    como(monkeypatch, professora, categoria="cadastrado")
    resposta = na_conversa(client, conversa, acao="salvar", titulo=conversa.titulo)
    assert resposta.status_code == 302
    assert not RegistroDeModeracao.objects.exists()


@pytest.mark.parametrize(
    "acao, esperado",
    [
        ("salvar", Acao.EDITAR_MENSAGEM),
        ("tirar_do_ar", Acao.TIRAR_MENSAGEM_DO_AR),
    ],
)
def test_os_gestos_na_mensagem_gravam_uma_linha(
    client, env, monkeypatch, conversa, grupo, professora, acao, esperado
):
    mensagem = mensagem_de(conversa)
    como(monkeypatch, professora, categoria="cadastrado")
    resposta = na_mensagem(
        client, mensagem, acao=acao, texto="texto corrigido", motivo=MOTIVO
    )
    assert resposta.status_code == 302

    linha = unica_linha()
    assert linha.acao == esperado
    assert linha.mensagem == mensagem
    assert linha.topico == conversa
    assert linha.area == grupo
    assert linha.motivo == MOTIVO


def test_devolver_a_mensagem_ao_ar_tambem_fica_registrado(
    client, env, monkeypatch, conversa, professora
):
    mensagem = mensagem_de(conversa)
    Mensagem.objects.filter(pk=mensagem.pk).update(removida_em=timezone.now())
    como(monkeypatch, professora, categoria="cadastrado")
    resposta = na_mensagem(client, mensagem, acao="restaurar", motivo="foi engano")
    assert resposta.status_code == 302
    assert unica_linha().acao == Acao.RESTAURAR_MENSAGEM


def test_apontar_e_desmarcar_a_resposta_certa_ficam_registrados(
    client, env, monkeypatch, conversa, bia, grupo, professora
):
    vincular(grupo, bia, professora)
    resposta_da_bia = Mensagem.objects.create(topico=conversa, autor=bia, texto="ok")
    como(monkeypatch, professora, categoria="cadastrado")

    assert (
        na_conversa(
            client, conversa, acao="aceitar", mensagem_id=resposta_da_bia.pk
        ).status_code
        == 302
    )
    assert unica_linha().acao == Acao.APONTAR_RESPOSTA
    assert unica_linha().mensagem == resposta_da_bia

    assert na_conversa(client, conversa, acao="desmarcar").status_code == 302
    assert RegistroDeModeracao.objects.filter(acao=Acao.DESMARCAR_RESPOSTA).count() == 1


def test_adicionar_e_tirar_do_grupo_ficam_registrados(
    client, env, monkeypatch, grupo, bia, professora
):
    como(monkeypatch, professora, categoria="cadastrado")
    gerir(client, grupo, acao="adicionar", email=bia.email, motivo="turma 9")
    linha = unica_linha()
    assert linha.acao == Acao.ADICIONAR_MEMBRO
    assert linha.vinculo.pessoa == bia
    assert linha.motivo == "turma 9"

    vinculo = MembroDoGrupo.objects.get(grupo=grupo, pessoa=bia)
    resposta = gerir(
        client, grupo, acao="remover", vinculo_id=vinculo.pk, motivo="pediu para sair"
    )
    assert resposta.status_code == 302
    saida = RegistroDeModeracao.objects.get(acao=Acao.REMOVER_MEMBRO)
    assert saida.vinculo == vinculo
    assert saida.motivo == "pediu para sair"
    assert saida.area == grupo


def test_trocar_o_responsavel_exige_motivo_e_guarda_quem_saiu_e_quem_entrou(
    client, env, monkeypatch, grupo, professora, dono
):
    como(monkeypatch, professora, categoria="cadastrado")
    recusa = no_grupo(client, grupo, responsavel=dono.pk)
    assert recusa.status_code == 400
    assert moderacao.ERRO_MOTIVO_DA_ACAO in recusa.content.decode()
    grupo.refresh_from_db()
    assert grupo.responsavel == professora
    assert not RegistroDeModeracao.objects.exists()

    resposta = no_grupo(client, grupo, responsavel=dono.pk, motivo="Lia de férias")
    assert resposta.status_code == 302
    grupo.refresh_from_db()
    assert grupo.responsavel == dono

    linha = unica_linha()
    assert linha.acao == Acao.TROCAR_RESPONSAVEL
    assert linha.motivo == "Lia de férias"
    assert "Profa. Lia" in linha.detalhe and "Davi" in linha.detalhe


def test_mudar_as_vagas_fica_registrado_com_o_numero_de_antes(
    client, env, monkeypatch, grupo, professora
):
    como(monkeypatch, professora, categoria="cadastrado")
    assert no_grupo(client, grupo, vagas="12").status_code == 302
    linha = unica_linha()
    assert linha.acao == Acao.MUDAR_VAGAS
    assert "10" in linha.detalhe and "12" in linha.detalhe


# ------------------------------------------------------------ o motivo obrigatório


@pytest.mark.parametrize(
    "gesto",
    ["tirar_do_ar", "restaurar", "mover", "editar_titulo_alheio"],
)
def test_gesto_na_conversa_sem_motivo_e_recusado_e_nada_muda(
    client, env, monkeypatch, conversa, outro_grupo, professora, gesto
):
    dados = {
        "tirar_do_ar": {"acao": "tirar_do_ar"},
        "restaurar": {"acao": "restaurar"},
        "mover": {
            "acao": "salvar",
            "titulo": conversa.titulo,
            "area_id": outro_grupo.pk,
        },
        "editar_titulo_alheio": {"acao": "salvar", "titulo": "Outro título bom"},
    }[gesto]
    como(monkeypatch, professora, categoria="cadastrado")
    resposta = na_conversa(client, conversa, motivo="   ", **dados)

    assert resposta.status_code == 400
    assert moderacao.ERRO_MOTIVO_DA_ACAO in resposta.content.decode()
    depois = Topico.objects.get(pk=conversa.pk)
    assert (depois.estado, depois.titulo, depois.area_id) == (
        conversa.estado,
        conversa.titulo,
        conversa.area_id,
    )
    assert not RegistroDeModeracao.objects.exists()


@pytest.mark.parametrize("acao", ["salvar", "tirar_do_ar", "restaurar"])
def test_gesto_na_mensagem_alheia_sem_motivo_e_recusado(
    client, env, monkeypatch, conversa, professora, acao
):
    mensagem = mensagem_de(conversa)
    como(monkeypatch, professora, categoria="cadastrado")
    resposta = na_mensagem(client, mensagem, acao=acao, texto="mudado")

    assert resposta.status_code == 400
    assert moderacao.ERRO_MOTIVO_DA_ACAO in resposta.content.decode()
    depois = Mensagem.objects.get(pk=mensagem.pk)
    assert (depois.texto, depois.removida_em) == (mensagem.texto, None)
    assert not RegistroDeModeracao.objects.exists()


def test_tirar_do_grupo_sem_motivo_e_recusado(
    client, env, monkeypatch, grupo, ana, professora
):
    vinculo = vincular(grupo, ana, professora)
    como(monkeypatch, professora, categoria="cadastrado")
    resposta = gerir(client, grupo, acao="remover", vinculo_id=vinculo.pk)
    assert resposta.status_code == 400
    assert moderacao.ERRO_MOTIVO_DA_ACAO in resposta.content.decode()
    vinculo.refresh_from_db()
    assert vinculo.ate is None


def test_editar_a_propria_mensagem_nao_pede_motivo(
    client, env, monkeypatch, grupo, professora
):
    """Motivo é para o texto de OUTRA pessoa. Corrigir o próprio erro de digitação
    não é moderação de ninguém, e a linha fica registrada do mesmo jeito."""
    topico = duvida(grupo, professora, "Aviso da semana", "Desafio novo na quarta.")
    como(monkeypatch, professora, categoria="cadastrado")
    resposta = na_mensagem(
        client, mensagem_de(topico), acao="salvar", texto="Desafio novo na quinta."
    )
    assert resposta.status_code == 302
    linha = unica_linha()
    assert (linha.acao, linha.motivo) == (Acao.EDITAR_MENSAGEM, "")


# ------------------------------------------------------------ nunca muda, nunca some


def test_a_linha_nao_se_altera_nem_se_apaga_nem_pelo_update(
    client, env, monkeypatch, conversa, professora
):
    como(monkeypatch, professora, categoria="cadastrado")
    na_conversa(client, conversa, acao="tirar_do_ar", motivo=MOTIVO)
    linha = unica_linha()

    linha.motivo = "outro motivo, escrito depois"
    with pytest.raises(DatabaseError), transaction.atomic():
        linha.save()
    with pytest.raises(DatabaseError), transaction.atomic():
        RegistroDeModeracao.objects.filter(pk=linha.pk).update(motivo="")
    with pytest.raises(DatabaseError), transaction.atomic():
        RegistroDeModeracao.objects.filter(pk=linha.pk).delete()

    assert RegistroDeModeracao.objects.get(pk=linha.pk).motivo == MOTIVO


def test_o_vocabulario_e_fechado_e_o_motivo_obrigatorio_vale_no_banco(
    conversa, grupo, professora
):
    with pytest.raises(IntegrityError), transaction.atomic():
        RegistroDeModeracao.objects.create(
            ator=professora, acao="apagar", area=grupo, topico=conversa, motivo="x"
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        RegistroDeModeracao.objects.create(
            ator=professora, acao=Acao.TIRAR_DO_AR, area=grupo, topico=conversa
        )


def test_a_linha_nasce_na_mesma_transacao_do_gesto(
    client, env, monkeypatch, conversa, professora
):
    """Se a linha não pode ser gravada, o gesto também não acontece.

    Uma conversa tirada do ar sem rastro é exatamente o que este registro existe
    para impedir.
    """

    def banco_recusa(self, *args, **kwargs):
        raise IntegrityError("simulado")

    monkeypatch.setattr(RegistroDeModeracao, "save", banco_recusa)
    como(monkeypatch, professora, categoria="cadastrado")
    resposta = na_conversa(client, conversa, acao="tirar_do_ar", motivo=MOTIVO)

    assert resposta.status_code == 400
    assert Topico.objects.get(pk=conversa.pk).estado == Topico.Estado.PUBLICADO


# ------------------------------------------------------------ a vista da equipe


def test_a_vista_da_equipe_mostra_as_ultimas_dez_acoes_de_cada_grupo(
    client, env, monkeypatch, conversa, grupo, outro_grupo, professora
):
    agora = timezone.now()
    for n in range(12):
        RegistroDeModeracao.objects.create(
            ator=professora,
            acao=Acao.TRANCAR,
            area=grupo,
            topico=conversa,
            detalhe=f"conversa numero {n:02d}",
            quando=agora - timedelta(minutes=12 - n),
        )
    RegistroDeModeracao.objects.create(
        ator=professora,
        acao=Acao.TIRAR_DO_AR,
        area=grupo,
        topico=conversa,
        detalhe="a ultima de todas",
        motivo=MOTIVO,
        quando=agora,
    )

    como(monkeypatch, professora, categoria="cadastrado")
    corpo = pedir(client, "comunidade_da_equipe").content.decode()

    assert "Últimas ações da moderação" in corpo
    assert "a ultima de todas" in corpo
    assert f"Motivo: {MOTIVO}" in corpo
    assert "Profa. Lia" in corpo
    assert Acao.TIRAR_DO_AR.label in corpo
    assert "conversa numero 11" in corpo
    assert "conversa numero 03" in corpo
    assert "conversa numero 02" not in corpo
    assert corpo.index("a ultima de todas") < corpo.index("conversa numero 11")
    assert "@exemplo.com" not in corpo
    assert "Nenhuma ação de moderação neste grupo ainda." in corpo


def test_a_troca_aparece_nos_dois_grupos_da_vista(
    client, env, monkeypatch, grupo, outro_grupo, ana, professora
):
    vinculo = vincular(outro_grupo, ana, professora)
    RegistroDeModeracao.objects.create(
        ator=professora,
        acao=Acao.TROCAR_DE_GRUPO,
        area=grupo,
        area_destino=outro_grupo,
        vinculo=vinculo,
        detalhe="Ana, de um para o outro",
        motivo="mudou de turno",
    )
    como(monkeypatch, professora, categoria="cadastrado")
    corpo = pedir(client, "comunidade_da_equipe").content.decode()
    assert corpo.count("Ana, de um para o outro") == 2
    assert "Nenhuma ação de moderação neste grupo ainda." not in corpo
