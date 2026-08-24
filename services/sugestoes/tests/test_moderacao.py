"""A superfície da equipe (EVO-13): a fila, a página de moderação e a avaliação.

Os invariantes moram nos `test_inv_*` deste diretório — 403 para quem não é
staff, histórico na mesma transação, justificativa obrigatória, append-only,
situação de matrícula. Aqui ficam os comportamentos que fazem a moderação ser
utilizável: a fila mostra o que precisa mostrar, a avaliação interna é UMA por
sugestão e revisitável, e a equipe tem como chegar até a fila sem decorar URL.
"""

import pytest
from django.urls import reverse

from apps.sugestoes.models import AvaliacaoInterna, Sugestao, Voto

pytestmark = pytest.mark.django_db


@pytest.fixture
def duas_sugestoes(quadro, categoria, aluno, outro_aluno):
    """Uma com voto, outra sem — o suficiente para a ordem significar algo."""
    campeã = Sugestao.objects.create(
        quadro=quadro,
        categoria=categoria,
        autor=aluno,
        titulo="Exportar o projeto para o Roblox",
        problema="Termino a aula e não sei como publicar.",
    )
    quieta = Sugestao.objects.create(
        quadro=quadro,
        categoria=categoria,
        autor=outro_aluno,
        titulo="Aula sobre iluminação",
        problema="Meus mapas ficam escuros.",
    )
    Voto.objects.create(sugestao=campeã, autor=outro_aluno)
    return campeã, quieta


# ---------------------------------------------------------------------------
# A fila
# ---------------------------------------------------------------------------


def test_a_fila_mostra_as_sugestoes_do_mais_votado_para_o_menos(equipe, duas_sugestoes):
    campeã, quieta = duas_sugestoes

    corpo = equipe.client.get(reverse("fila")).content.decode()

    assert corpo.index(campeã.titulo) < corpo.index(quieta.titulo)


def test_a_fila_mostra_o_status_e_se_ja_foi_avaliada(equipe, duas_sugestoes, aluno):
    campeã, _ = duas_sugestoes
    AvaliacaoInterna.objects.create(
        sugestao=campeã, notas="já olhamos", avaliado_por=aluno
    )

    corpo = equipe.client.get(reverse("fila")).content.decode()

    assert "Em análise" in corpo
    assert "sem avaliação interna" in corpo
    assert "avaliada" in corpo


def test_a_fila_filtra_por_status(equipe, duas_sugestoes):
    campeã, quieta = duas_sugestoes
    Sugestao.objects.filter(pk=quieta.pk).update(status=Sugestao.Status.PLANEJADO)

    corpo = equipe.client.get(
        reverse("fila"), {"status": Sugestao.Status.PLANEJADO}
    ).content.decode()

    assert quieta.titulo in corpo
    assert campeã.titulo not in corpo


def test_um_filtro_de_status_inventado_e_ignorado_e_nao_quebra_a_fila(
    equipe, duas_sugestoes
):
    """Filtro desconhecido cai para "todos" — e não para uma lista vazia que
    faria a equipe achar que a fila esvaziou."""
    resposta = equipe.client.get(reverse("fila"), {"status": "virou_unicornio"})

    assert resposta.status_code == 200
    for sugestao in duas_sugestoes:
        assert sugestao.titulo in resposta.content.decode()


# ---------------------------------------------------------------------------
# A página de uma sugestão, do lado da equipe
# ---------------------------------------------------------------------------


def test_a_pagina_de_moderacao_mostra_o_historico_com_a_nota(equipe, sugestao):
    equipe.client.post(
        reverse("mudar_status", args=[sugestao.id]),
        {"status": Sugestao.Status.PLANEJADO, "nota": "entra na trilha de agosto"},
    )

    corpo = equipe.client.get(reverse("moderar", args=[sugestao.id])).content.decode()

    assert "Em análise" in corpo and "Planejado" in corpo
    assert "entra na trilha de agosto" in corpo
    assert "Equipe" in corpo  # quem mudou


def test_a_pagina_de_moderacao_nao_oferece_apagar_o_historico(equipe, sugestao):
    """O histórico é append-only nos três degraus do EVO-11: um botão de apagar
    seria uma promessa que o banco recusa — erro 500 em vez de tela útil."""
    corpo = equipe.client.get(reverse("moderar", args=[sugestao.id])).content.decode()

    assert "Apagar" not in corpo
    assert "Excluir" not in corpo


# ---------------------------------------------------------------------------
# A avaliação interna
# ---------------------------------------------------------------------------


def test_a_equipe_registra_a_avaliacao_interna(equipe, sugestao):
    resposta = equipe.client.post(
        reverse("avaliar", args=[sugestao.id]),
        {
            "impacto_educacional": 5,
            "impacto_comercial": 3,
            "esforco_tecnico": 2,
            "notas": "dá para reaproveitar o player que já existe",
            "decisao_produto": "entra depois do módulo 3",
        },
    )

    assert resposta.status_code == 302, resposta.content
    avaliacao = AvaliacaoInterna.objects.get()
    assert avaliacao.sugestao_id == sugestao.id
    assert (
        avaliacao.impacto_educacional,
        avaliacao.impacto_comercial,
        avaliacao.esforco_tecnico,
    ) == (5, 3, 2)
    assert avaliacao.decisao_produto == "entra depois do módulo 3"
    assert avaliacao.avaliado_por_id == equipe.identidade.id


def test_avaliar_de_novo_atualiza_a_mesma_linha(equipe, sugestao):
    """A avaliação é UMA por sugestão (`OneToOneField`) e é revisitada. Quem
    guarda linha do tempo é o `HistoricoStatus`, e ele é de status, não de
    opinião interna."""
    endereco = reverse("avaliar", args=[sugestao.id])
    equipe.client.post(endereco, {"esforco_tecnico": 1, "notas": "primeira leitura"})
    equipe.client.post(
        endereco, {"esforco_tecnico": 4, "notas": "é mais caro do que parecia"}
    )

    avaliacao = AvaliacaoInterna.objects.get()
    assert avaliacao.esforco_tecnico == 4
    assert avaliacao.notas == "é mais caro do que parecia"


def test_a_segunda_pessoa_da_equipe_assume_a_avaliacao(
    equipe, entrar_como_staff, sugestao
):
    """`avaliado_por` responde "quem responde por este texto agora", e não
    "quem escreveu primeiro" — senão a coluna aponta para quem já discorda."""
    endereco = reverse("avaliar", args=[sugestao.id])
    equipe.client.post(endereco, {"notas": "primeira leitura"})

    outra = entrar_como_staff(email="outra@meshcraft.test", nome="Outra")
    outra.client.post(endereco, {"notas": "reescrevi"})

    assert AvaliacaoInterna.objects.get().avaliado_por_id == outra.identidade.id


@pytest.mark.parametrize("valor", ["-1", "6", "muitos"])
def test_nota_fora_da_escala_e_recusada_com_frase_em_portugues(equipe, sugestao, valor):
    """A recusa vem como texto, não como `IntegrityError` do check constraint
    do Postgres — que é o que aconteceria com um número negativo passando."""
    resposta = equipe.client.post(
        reverse("avaliar", args=[sugestao.id]), {"impacto_educacional": valor}
    )

    assert resposta.status_code == 400
    assert "vai de 0 a 5" in resposta.content.decode()
    assert AvaliacaoInterna.objects.count() == 0


def test_campo_de_nota_em_branco_vale_zero(equipe, sugestao):
    """Salvar só a decisão de produto, sem tocar nas notas, é caso normal."""
    resposta = equipe.client.post(
        reverse("avaliar", args=[sugestao.id]), {"decisao_produto": "vamos fazer"}
    )

    assert resposta.status_code == 302, resposta.content
    assert AvaliacaoInterna.objects.get().impacto_educacional == 0


# ---------------------------------------------------------------------------
# O caminho até a fila
# ---------------------------------------------------------------------------


def test_a_equipe_tem_link_para_a_fila_no_topo_de_toda_pagina(equipe, sugestao):
    corpo = equipe.client.get(reverse("quadro")).content.decode()

    assert reverse("fila") in corpo


def test_o_aluno_nao_ve_esse_link(dentro, sugestao):
    corpo = dentro.client.get(reverse("quadro")).content.decode()

    assert reverse("fila") not in corpo
    assert "moderação" not in corpo
