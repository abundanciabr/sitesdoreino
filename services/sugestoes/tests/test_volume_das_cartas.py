# tests/test_volume_das_cartas.py
"""As CARTAS custam o mesmo com 2 e com 20 destinatários (Rito de 26/08/2026).

Irmão do `test_volume_dos_avisos.py`, e pelo mesmo motivo: o que se prova aqui
não é correção, é **desenho**. Um laço de `create()` por pessoa publica as
mesmas cartas, para as mesmas pessoas, na mesma transação, e passa em todo
guarda de conteúdo. O que ele não faz é continuar barato quando uma ideia dá
certo — e é justamente na ideia mais votada que a trava `SELECT … FOR UPDATE`
da moderação estaria aberta.

**Por que este guarda importa MAIS que o dos avisos.** A §5.2 da
`DECISAO-notificacoes` exigia fan-out em lote *dentro da célula que recebe*. O
mantenedor escolheu "uma carta por pessoa" (`DECISAO-fase-2-do-sininho` §1), e
com isso a exigência **mudou de endereço**: o lote acontece aqui, na origem.
Uma exigência que muda de lugar é uma exigência que fica órfã — a lei velha
aponta para um lugar onde não há mais nada a medir, e a nova depende de alguém
ter escrito este arquivo. Está escrito.

Dois degraus, falsificáveis separadamente:

1. o **emissor** — `emitir_cartas_de_notificacao()`, um `INSERT` para a plateia
   inteira;
2. a **jornada** — o POST da moderação, onde alguém poderia reintroduzir um laço
   por fora (percorrendo votantes na view) sem o degrau 1 notar.

Comparar dois números medidos, nunca cravar um: cravar transformaria qualquer
`select_related` novo em vermelho falso, e a pergunta nunca foi "quantas
consultas" — foi "o número depende da plateia?".
"""

import pytest
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.core.avisos import ids_de_plataforma, interessados_em
from apps.sugestoes import eventos
from apps.sugestoes.models import OutboxEvent, Sugestao

pytestmark = pytest.mark.django_db

PEQUENA = 2
GRANDE = 20


def _contar(fazer) -> int:
    with CaptureQueriesContext(connection) as consultas:
        fazer()
    return len(consultas)


def _autor_na_plataforma(autor):
    """O autor da fixture nasce sem o id que atravessa a plataforma.

    Aqui ele ganha um, e a linha não é detalhe: sem ela o autor some das cartas
    (o pulo funcionando, e corretamente) e a contagem deste guarda passaria a
    medir "interessados menos um" sem ninguém perceber. Quem prova o PULO é
    `test_inv_carta_endereca_pelo_id_da_plataforma.py`; aqui a pergunta é outra,
    e é a de volume.
    """
    autor.id_da_plataforma = "idt-autor-na-plataforma"
    autor.save(update_fields=["id_da_plataforma"])
    return autor


def _uma_sugestao(quadro, categoria, autor, titulo):
    return Sugestao.objects.create(
        quadro=quadro,
        categoria=categoria,
        autor=autor,
        titulo=titulo,
        problema="Assisto no ônibus e não dá para ouvir.",
    )


def _publicar_cartas(sugestao):
    def _fazer():
        with transaction.atomic():
            na_plataforma = ids_de_plataforma(interessados_em(sugestao))
            eventos.emitir_cartas_de_notificacao(
                sugestao=sugestao,
                destinatarios=list(na_plataforma.values()),
                status_anterior=Sugestao.Status.EM_ANALISE,
                status_novo=Sugestao.Status.PLANEJADO,
                nota="anda",
                ator_id="idt-quem-moderou",
                origem_event_id="00000000-0000-4000-8000-000000000000",
            )

    return _fazer


def test_as_cartas_custam_o_mesmo_com_2_e_com_20_destinatarios(
    quadro, categoria, aluno, plateia
):
    """Degrau 1 — o emissor, isolado da moderação em volta."""
    autor = _autor_na_plataforma(aluno)
    pequena = _uma_sugestao(quadro, categoria, autor, "Plateia pequena")
    grande = _uma_sugestao(quadro, categoria, autor, "Plateia grande")
    plateia(pequena, votantes=PEQUENA, comentaristas=PEQUENA, marca="peq")
    plateia(grande, votantes=GRANDE, comentaristas=GRANDE, marca="gra")

    poucas = _contar(_publicar_cartas(pequena))
    muitas = _contar(_publicar_cartas(grande))

    # A prova de que a medição mediu algo: as plateias são MESMO diferentes.
    # Sem isto, um emissor quebrado que não escrevesse nada passaria liso.
    assert (
        OutboxEvent.objects.filter(
            event=eventos.NOTIFICACAO_DEVIDA,
            payload__suggestion_id=str(pequena.pk),
        ).count()
        == 0
    ), "as cartas guardam suggestion_id em `parametros`, não no topo"
    escritas = OutboxEvent.objects.filter(event=eventos.NOTIFICACAO_DEVIDA).count()
    assert escritas == (2 * PEQUENA + 1) + (2 * GRANDE + 1), (
        "o número de cartas não bate com o número de interessados — "
        f"escritas {escritas}"
    )

    assert poucas == muitas, (
        f"o custo de publicar as cartas CRESCEU com a plateia: {poucas} consultas "
        f"para {2 * PEQUENA + 1} pessoas e {muitas} para {2 * GRANDE + 1}. "
        "Um `create()` por carta dentro de um laço é o desenho errado — "
        "`bulk_create` escreve a plateia inteira num INSERT só."
    )


def test_a_jornada_inteira_da_moderacao_nao_cresce_com_a_plateia(
    equipe, quadro, categoria, aluno, plateia
):
    """Degrau 2 — o POST de verdade, que é onde um laço reapareceria por fora.

    Mede a requisição inteira: resolver os ids da plataforma, escrever os avisos
    locais, o fato e as cartas. Se qualquer uma dessas etapas voltar a ser "uma
    por pessoa", este número cresce com a plateia e o guarda acusa.
    """
    pequena = _uma_sugestao(quadro, categoria, aluno, "Plateia pequena")
    grande = _uma_sugestao(quadro, categoria, aluno, "Plateia grande")
    plateia(pequena, votantes=PEQUENA, comentaristas=PEQUENA, marca="peq")
    plateia(grande, votantes=GRANDE, comentaristas=GRANDE, marca="gra")

    def _moderar(sugestao):
        def _fazer():
            resposta = equipe.client.post(
                reverse("mudar_status", args=[sugestao.id]),
                {"status": Sugestao.Status.PLANEJADO, "nota": "Entra no ciclo."},
            )
            assert resposta.status_code == 302, resposta.status_code

        return _fazer

    poucas = _contar(_moderar(pequena))
    muitas = _contar(_moderar(grande))

    assert poucas == muitas, (
        f"a moderação inteira ficou mais cara com a plateia: {poucas} consultas "
        f"para {2 * PEQUENA + 1} interessados e {muitas} para {2 * GRANDE + 1}. "
        "Alguém reintroduziu um laço por pessoa — provavelmente fora do emissor, "
        "que o outro teste deste arquivo continua aprovando."
    )
