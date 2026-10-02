# tests/test_inv_aviso_e_so_do_dono.py  # [RECEITA:R5 v1]
"""O aviso é do dono: só quem interagiu recebe, e só o seu.
Mede a escrita: a linha `Aviso` local e a carta da outbox."""

import pytest

from apps.sugestoes import eventos
from apps.sugestoes.models import Aviso, OutboxEvent, Sugestao, Voto

pytestmark = pytest.mark.django_db


@pytest.fixture
def outra_pessoa(entrar_como):
    """Alguém que entrou pela porta de verdade e não interagiu com a ideia."""
    return entrar_como(email="bianca@exemplo.test", nome="Bianca")


def _mudar(equipe, sugestao, nota):
    resposta = equipe.gestao.mudar_status(
        equipe, sugestao, Sugestao.Status.PLANEJADO, nota=nota
    )
    assert resposta.status_code == 200, resposta.content


def test_so_quem_interagiu_recebe_o_aviso_e_so_o_dele(
    equipe, dentro, outra_pessoa, sugestao
):
    Voto.objects.create(sugestao=sugestao, autor=dentro.identidade)

    _mudar(equipe, sugestao, "Entra no próximo ciclo.")

    meu = Aviso.objects.get(destinatario=dentro.identidade)
    assert meu.sugestao_id == sugestao.id
    assert meu.vinculo == Aviso.Vinculo.VOTO
    assert meu.nota == "Entra no próximo ciclo."
    assert meu.lido_em is None
    assert not Aviso.objects.filter(destinatario=outra_pessoa.identidade).exists()
    assert set(Aviso.objects.values_list("destinatario_id", flat=True)) == {
        sugestao.autor_id,
        dentro.identidade.id,
    }


def test_a_carta_vai_so_para_o_id_da_plataforma_de_quem_interagiu(
    equipe, dentro, outra_pessoa, sugestao
):
    Voto.objects.create(sugestao=sugestao, autor=dentro.identidade)

    _mudar(equipe, sugestao, "Entra no próximo ciclo.")

    enderecados = {
        carta.payload["destinatario_id"]
        for carta in OutboxEvent.objects.filter(event=eventos.NOTIFICACAO_DEVIDA)
    }
    assert enderecados == {dentro.identidade.id_da_plataforma}
    assert outra_pessoa.identidade.id_da_plataforma not in enderecados


def test_ninguem_recebe_o_aviso_de_uma_ideia_em_que_nao_interagiu(
    equipe, outra_pessoa, sugestao
):
    _mudar(equipe, sugestao, "Só o autor sabe.")

    assert Aviso.objects.count() == 1
    assert not Aviso.objects.filter(destinatario=outra_pessoa.identidade).exists()
