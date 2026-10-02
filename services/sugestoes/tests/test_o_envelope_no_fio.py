# tests/test_o_envelope_no_fio.py  # [RECEITA:R5 v1]
"""O envelope que sai no fio: o nome do stream, a versão dentro, o `data` de cada
fato e nenhum dado pessoal.

É a decisão de privacidade do mantenedor (`DECISAO-EVO-01` §3: o e-mail vive
numa linha só, dentro da Caixa): o fio leva ids opacos, contagem e status.
"""

import json

import pytest

from apps.sugestoes import eventos
from apps.sugestoes.models import Sugestao
from apps.sugestoes.tasks import relay_outbox

pytestmark = pytest.mark.django_db


# Os quatro fatos + a CARTA do autor. Desde o Rito de Contrato de 26/08/2026 a
# mudança de status publica também um `notificacao.devida` por interessado, e
# nesta fixture o único interessado é o próprio autor (ele vota e desvota, então
# não sobra voto de mais ninguém). O número está escrito, e não calculado, de
# propósito: se um dia sair evento a mais ou a menos, este é o primeiro guarda
# que acusa.
FATOS_E_CARTAS_DA_FIXTURE = 5


@pytest.fixture
def no_fio(caixa, fio):
    """Provoca os quatro fatos e devolve o que o relay REALMENTE publicou."""
    caixa.os_quatro_fatos()
    assert relay_outbox() == FATOS_E_CARTAS_DA_FIXTURE
    return fio


# ---------------------------------------------------------------------------
# Os quatro envelopes, como saíram no fio
# ---------------------------------------------------------------------------


def test_o_nome_do_stream_e_eventos_ponto_evento_e_a_versao_vai_no_envelope(no_fio):
    """`eventos.<nome>`, sem `v1` no nome — a versão viaja DENTRO.

    Pôr a versão no nome do stream faria de toda evolução de contrato uma
    migração de infraestrutura: o `v1` continua sendo emitido até o último
    consumidor migrar (RITOS §3), e seriam dois streams para o mesmo fato.
    """
    assert sorted(no_fio.streams) == [
        "eventos.notificacao.devida",
        "eventos.sugestao.criada",
        "eventos.sugestao.status-alterado",
        "eventos.sugestao.voto-adicionado",
        "eventos.sugestao.voto-removido",
    ]
    # E a prova de que a versão viaja DENTRO: o `status-alterado` foi para o v2
    # no Rito de Contrato de 26/08/2026 e continua no MESMO stream, sem `v2` no
    # nome. Se a versão morasse no nome, esta migração teria sido uma mudança de
    # infraestrutura.
    versoes = {(evento["event"], evento["version"]) for _, evento in no_fio.mensagens}
    assert versoes == {
        ("sugestao.criada", 1),
        ("sugestao.voto-adicionado", 1),
        ("sugestao.voto-removido", 1),
        ("sugestao.status-alterado", 2),
        ("notificacao.devida", 1),
    }


def test_o_data_da_sugestao_criada_e_o_que_o_contrato_descreve(caixa, fio):
    sugestao = caixa.publicar()
    relay_outbox()

    dados = fio.um_envelope(eventos.CRIADA)["data"]

    assert dados == {
        "site_id": "site-de-teste",
        "suggestion_id": str(sugestao.pk),
        "quadro_id": str(sugestao.quadro_id),
        "categoria_id": str(sugestao.categoria_id),
        "autor_id": caixa.aluno.identidade.id,
    }


def test_os_votos_levam_quem_votou_e_o_total_depois_do_fato(caixa, fio, entrar_como):
    """`autor_id` é quem VOTOU, não quem sugeriu — e `total_votos` é o de
    depois. Dois atores diferentes deixam a confusão impossível de passar."""
    sugestao = caixa.publicar()
    outra_pessoa = entrar_como("maria@exemplo.test", "Maria")
    caixa.votar(sugestao)
    caixa.votar(sugestao, quem=outra_pessoa)
    caixa.desvotar(sugestao, quem=outra_pessoa)
    relay_outbox()

    adicionados = fio.envelopes(eventos.VOTO_ADICIONADO)
    removido = fio.um_envelope(eventos.VOTO_REMOVIDO)

    assert [e["data"]["autor_id"] for e in adicionados] == [
        caixa.aluno.identidade.id,
        outra_pessoa.identidade.id,
    ]
    assert [e["data"]["total_votos"] for e in adicionados] == [1, 2]
    assert removido["data"]["autor_id"] == outra_pessoa.identidade.id
    assert removido["data"]["total_votos"] == 1  # DEPOIS da remoção


def test_o_status_alterado_leva_o_autor_da_sugestao_e_a_justificativa(caixa, fio):
    """Quem SUGERIU, não quem moderou: é a esse que o EVO-21 vai avisar.

    Quem moderou fica no `HistoricoStatus`, dentro da Caixa — é auditoria
    interna e não interessa a nenhum consumidor.
    """
    sugestao = caixa.publicar()
    caixa.mudar_status(
        sugestao, Sugestao.Status.NAO_PLANEJADO, nota="Já existe no menu de aulas."
    )
    relay_outbox()

    dados = fio.um_envelope(eventos.STATUS_ALTERADO)["data"]

    assert dados["autor_da_sugestao_id"] == caixa.aluno.identidade.id
    assert dados["status_anterior"] == "em_analise"
    assert dados["status_novo"] == "nao_planejado"
    assert dados["nota"] == "Já existe no menu de aulas."


def test_sem_justificativa_o_campo_nota_nem_aparece(caixa, fio):
    """Opcional no contrato quer dizer AUSENTE, não string vazia — senão todo
    consumidor teria de distinguir "sem justificativa" de "justificativa
    vazia", que são dois nomes para a mesma coisa."""
    sugestao = caixa.publicar()
    caixa.mudar_status(sugestao, Sugestao.Status.PLANEJADO)
    relay_outbox()

    assert "nota" not in fio.um_envelope(eventos.STATUS_ALTERADO)["data"]


# ---------------------------------------------------------------------------
# A privacidade
# ---------------------------------------------------------------------------


def test_nenhum_envelope_carrega_dado_pessoal_nem_texto_do_aluno(no_fio):
    """Ids opacos, contagem e status. Mais nada.

    A `DECISAO-EVO-01` §3 põe o e-mail numa linha só, dentro da Caixa. Um
    evento que o levasse junto espalharia dado pessoal por todo consumidor que
    assinasse o stream — e não haveria como recolher depois. Título e texto do
    problema ficam de fora pelo mesmo motivo: são o que a pessoa escreveu.
    """
    for _, envelope in no_fio.mensagens:
        cru = json.dumps(envelope, ensure_ascii=False)
        for vazamento in ("@", "Legendas nas aulas", "ônibus", "João", "Equipe"):
            assert vazamento not in cru, f"{vazamento!r} vazou em {envelope['event']}"
