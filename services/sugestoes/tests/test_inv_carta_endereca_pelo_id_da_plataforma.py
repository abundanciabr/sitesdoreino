# tests/test_inv_carta_endereca_pelo_id_da_plataforma.py  # [RECEITA:R5 v1]
"""A carta endereça pelo id da PLATAFORMA — e quem não tem um, não recebe carta.

Lei: `docs/decisoes/DECISAO-fase-2-do-sininho.md`, Rito de Contrato de
26/08/2026 com o mantenedor presente.

O que este arquivo protege é o **motivo de existir** de toda a Fase 2. Uma carta
endereçada com o id LOCAL chega a uma caixa central que não faz ideia de quem é
essa pessoa — é exatamente o nó medido no `PLANO-MESTRE` §2, e é um erro que
não faz barulho nenhum: os dois ids são strings opacas parecidas, o contrato
aceita as duas, e a falha só apareceria na Fase 3, com a caixa cheia de cartas
para ninguém.

**As duas ausências são tratadas de formas OPOSTAS, e a assimetria é a decisão:**

- **destinatário sem id ⇒ pula, e a moderação segue.** É alguém que não volta ao
  site desde a Fase 1. A carta é aditiva (ninguém a consome ainda) e a pessoa
  continua recebendo o `Aviso` local, que é o que a tela mostra hoje. Travar a
  moderação de uma ideia popular porque um votante antigo sumiu seria absurdo.
- **ator sem id ⇒ para tudo, e nada é escrito.** Quem modera está autenticado
  NESTA requisição; chegar aqui sem id significa que algo quebrou agora. E o
  contrato v2 exige `ator_id`: sem ele o fato não pode ser afirmado, e INV-P6
  não admite estado sem evento — então recusar os dois juntos é a única saída
  correta.
"""

import json

import pytest

from apps.sugestoes import eventos
from apps.sugestoes.models import Aviso, OutboxEvent, Sugestao
from tests.conftest import id_da_plataforma_de

pytestmark = pytest.mark.django_db


def _cartas():
    return list(
        OutboxEvent.objects.filter(event=eventos.NOTIFICACAO_DEVIDA).order_by("id")
    )


def test_a_carta_leva_o_id_da_plataforma_e_nunca_o_id_local(caixa):
    """O par que torna o erro impossível de passar: os dois ids existem e são
    DIFERENTES, então trocar um pelo outro reprova."""
    sugestao = caixa.publicar()
    local = caixa.aluno.identidade.id
    plataforma = caixa.aluno.identidade.id_da_plataforma
    assert plataforma and plataforma != local, "a fixture não prova nada assim"

    caixa.mudar_status(sugestao, Sugestao.Status.PLANEJADO)

    (carta,) = _cartas()
    assert carta.payload["destinatario_id"] == plataforma
    assert carta.payload["destinatario_id"] != local


def test_quem_nao_tem_id_da_plataforma_nao_recebe_carta_mas_recebe_o_aviso(
    caixa, quadro, categoria, plateia
):
    """O pulo — e a prova de que ele NÃO é perda: o aviso local continua lá."""
    sugestao = caixa.publicar()
    antigos = plateia(sugestao, votantes=3, marca="antigo", na_plataforma=False)

    caixa.mudar_status(sugestao, Sugestao.Status.PLANEJADO)

    enderecados = {carta.payload["destinatario_id"] for carta in _cartas()}
    sem_id = {pessoa.id for pessoa in antigos["votaram"]}

    assert not (enderecados & sem_id), "carta endereçada a um id local"
    assert len(enderecados) == 1, "só o autor tem id de plataforma nesta cena"
    # E a parte que impede a leitura errada de "foi ignorado":
    assert Aviso.objects.filter(destinatario_id__in=sem_id).count() == 3


def test_o_ator_sem_id_da_plataforma_para_tudo_e_nada_e_escrito(
    caixa, entrar_como_staff, gestao
):
    """Fail-closed, e o `nada é escrito` é o ponto — não só o evento.

    Se o rollback falhasse, o status teria mudado sem o fato existir, que é o
    modo de falha que a outbox existe para tornar impossível (INV-P6).

    **A encenação é pela PORTA, e tem de ser.** A primeira versão deste guarda
    zerava a coluna `id_da_plataforma` da equipe e mandava o POST — e passava
    verde sem encenar falha nenhuma: toda requisição atravessa `obter_sessao`,
    que REGRAVA o id na reentrada (INV-SUG11). O único jeito honesto de a
    coluna continuar vazia é o site responder sem `id`, que o contrato declara
    opcional e nulável — e é o que `com_id=False` faz.
    """
    sugestao = caixa.publicar()
    sem_identidade = entrar_como_staff("outro@meshcraft.test", "Outro", com_id=False)
    antes = OutboxEvent.objects.count()

    resposta = gestao.mudar_status(sem_identidade, sugestao, Sugestao.Status.PLANEJADO)

    # 422 e nao mais 409: a jornada de moderacao passou a ser o CONTRATO
    # (30/08/2026), e la a recusa vem como `Recusa` com a frase que ensina o
    # caminho — a mesma que a tela dizia. O que este guarda mede nao mudou:
    # sem quem afirma, NADA e escrito.
    assert resposta.status_code == 422, resposta.content
    assert "entre uma vez em meshcraft.top" in resposta.json()["erro"].lower()
    sugestao.refresh_from_db()
    assert sugestao.status == Sugestao.Status.EM_ANALISE, "o status mudou mesmo assim"
    assert (
        OutboxEvent.objects.count() == antes
    ), "nasceu evento numa transação revertida"
    assert not Aviso.objects.filter(sugestao=sugestao).exists()


def test_a_carta_aponta_para_o_fato_que_a_gerou(caixa, quadro, categoria, plateia):
    """`origem_event_id` é o que torna a promessa nova RASTREÁVEL: de qualquer
    aviso se chega ao acontecimento. E as N cartas de uma mudança compartilham
    o valor — é o que permite reconstruir o leque inteiro depois."""
    sugestao = caixa.publicar()
    plateia(sugestao, votantes=2, marca="turma")

    caixa.mudar_status(sugestao, Sugestao.Status.PLANEJADO)

    fato = OutboxEvent.objects.get(event=eventos.STATUS_ALTERADO)
    origens = {carta.payload["origem_event_id"] for carta in _cartas()}

    assert len(_cartas()) == 3, "autor + dois votantes"
    assert origens == {str(fato.event_id)}


def test_a_carta_nao_leva_titulo_nem_texto_nem_email(caixa):
    """A frase nasce na LEITURA (DECISAO-notificacoes §5.1), e o título fica
    fora por um motivo próprio: ideia renomeada deixaria aviso velho mentindo."""
    sugestao = caixa.publicar()
    caixa.mudar_status(
        sugestao, Sugestao.Status.NAO_PLANEJADO, nota="Já existe no menu."
    )

    (carta,) = _cartas()
    cru = json.dumps(carta.payload, ensure_ascii=False)

    assert "@" not in cru
    assert sugestao.titulo not in cru
    assert sugestao.problema not in cru
    # a `nota` É da carta: é a resposta que a equipe escreveu para quem lê.
    assert carta.payload["parametros"]["nota"] == "Já existe no menu."
    assert carta.payload["parametros"]["suggestion_id"] == str(sugestao.pk)
