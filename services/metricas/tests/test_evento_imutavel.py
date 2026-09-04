"""Teste-guarda: o livro de fatos é append-only, e a duplicata se recusa.

O que estes guardas protegem (degrau 7.2, `AGENTS.metricas.md`):

1. **Um evento gravado não se altera nem se apaga**, pelos quatro caminhos que
   o ORM oferece: `save()` numa instância existente, `delete()` na instância,
   `update()` de conjunto e `delete()` de conjunto.
2. **A trava existe também no banco**, para o `UPDATE` que não passa pelo ORM.
   Medida só em Postgres, que é o banco do CI e o de produção.
3. **Duplicata se recusa pelo `event_id`**, nunca por conteúdo: dois cadastros
   legítimos no mesmo segundo têm o mesmo corpo e são dois fatos.
4. **O `dia` é o de São Paulo**, calculado na recepção, e é ele que decide em
   qual mês o fato entra.
5. **A célula sai do tipo**, sem ninguém digitar.

Por que isso merece guarda, e não um combinado escrito: um número derivado de
fatos que alguém pode reescrever não é medição, é opinião com casas decimais.
E a reescrita nunca chega anunciada — ela chega como "só ajustar esta linha".
"""

from __future__ import annotations

import datetime as dt
import uuid

import pytest
from django.db import connection, transaction

from apps.fatos.models import Evento, EventoMorto, FatoImutavel, dia_em_sao_paulo

pytestmark = pytest.mark.django_db

# 01h de UTC do dia 1º: ainda é dia 30 em São Paulo, e é este o caso que põe
# uma pessoa no mês errado quando alguém conta por UTC.
NA_VIRADA = dt.datetime(2026, 10, 1, 1, 0, tzinfo=dt.timezone.utc)


def cria(**sobre) -> Evento:
    campos = {
        "event_id": uuid.uuid4(),
        "tipo": "identidade.pessoa-cadastrada",
        "versao": 1,
        "site_id": "meshcraft",
        "ocorrido_em": NA_VIRADA,
        "dados": {"site_id": "meshcraft", "pessoa_id": "id-opaco-1"},
    }
    campos.update(sobre)
    evento = Evento(**campos)
    evento.save()
    return evento


def test_o_dia_e_o_de_sao_paulo_e_a_celula_sai_do_tipo():
    evento = cria()
    assert evento.dia == dt.date(2026, 9, 30), "01h UTC ainda é o dia anterior aqui"
    assert evento.ocorrido_em.date() == dt.date(2026, 10, 1), "em UTC seria outubro"
    assert evento.celula == "identidade"


def test_instante_sem_fuso_e_recusado():
    """Todo evento traz `occurred_at` com fuso; sem ele o dia é um chute."""
    with pytest.raises(ValueError):
        dia_em_sao_paulo(dt.datetime(2026, 10, 1, 1, 0))


def test_salvar_de_novo_e_recusado():
    evento = cria()
    evento.dados = {"outra": "coisa"}
    with pytest.raises(FatoImutavel):
        evento.save()
    assert Evento.objects.get(pk=evento.pk).dados["pessoa_id"] == "id-opaco-1"


def test_apagar_e_recusado_na_instancia_e_no_conjunto():
    evento = cria()
    with pytest.raises(FatoImutavel):
        evento.delete()
    with pytest.raises(FatoImutavel):
        Evento.objects.all().delete()
    assert Evento.objects.count() == 1


def test_update_de_conjunto_e_recusado():
    """O caminho que o `save()` sobrescrito NÃO cobre, e por isso engana."""
    cria()
    with pytest.raises(FatoImutavel):
        Evento.objects.filter(tipo="identidade.pessoa-cadastrada").update(versao=2)
    assert Evento.objects.get().versao == 1


@pytest.mark.skipif(
    connection.vendor != "postgresql",
    reason="a trava de banco é gatilho de Postgres; em SQLite vale a do ORM",
)
def test_a_trava_existe_tambem_no_banco():
    """O `UPDATE` que não passa pelo ORM: console, psql, script de migração.

    Sem este guarda, a imutabilidade seria uma convenção do código Python — e
    o caminho mais provável de quebrá-la é justamente o que não passa por ele.
    """
    from django.db.utils import InternalError, ProgrammingError

    evento = cria()
    with pytest.raises((InternalError, ProgrammingError)):
        with transaction.atomic(), connection.cursor() as c:
            c.execute("UPDATE fatos_evento SET versao = 99 WHERE id = %s", [evento.pk])
    with pytest.raises((InternalError, ProgrammingError)):
        with transaction.atomic(), connection.cursor() as c:
            c.execute("DELETE FROM fatos_evento WHERE id = %s", [evento.pk])


def test_duplicata_se_recusa_pelo_event_id():
    """Reentrega é o normal de qualquer fila; contar duas vezes é a mentira."""
    from django.db.utils import IntegrityError

    mesmo = uuid.uuid4()
    cria(event_id=mesmo)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            cria(event_id=mesmo)
    assert Evento.objects.count() == 1


def test_dois_fatos_iguais_com_ids_diferentes_sao_dois_fatos():
    """O outro lado: a recusa é pelo id, nunca por conteúdo.

    Duas pessoas que se cadastram no mesmo segundo produzem eventos de corpo
    parecido. Recusar por conteúdo perderia uma delas, e o número ficaria
    menor sem ninguém ver.
    """
    cria(dados={"site_id": "meshcraft", "pessoa_id": "a"})
    cria(dados={"site_id": "meshcraft", "pessoa_id": "a"})
    assert Evento.objects.count() == 2


def test_evento_morto_guarda_o_corpo_cru_e_muda_de_estado():
    """A fila de mortos É mutável, e a diferença é o desenho.

    Ela guarda o ESTADO de um problema em aberto (inspecionar, tentar de novo,
    descartar com motivo). O que não muda é o corpo cru, que é a prova do que
    chegou.
    """
    morto = EventoMorto.objects.create(
        corpo='{"event": "identidade.pessoa-cadastrada", "occurred_at": "ontem"}',
        motivo="`occurred_at` não é uma data com fuso",
        tipo_declarado="identidade.pessoa-cadastrada",
    )
    assert morto.estado == EventoMorto.Estado.NOVO
    morto.estado = EventoMorto.Estado.DESCARTADO
    morto.decidido_por = "id-opaco-do-dono"
    morto.motivo_da_decisao = "veio de um teste de carga, não é fato da escola"
    morto.save()
    assert EventoMorto.objects.get(pk=morto.pk).estado == "descartado"
    assert "occurred_at" in EventoMorto.objects.get(pk=morto.pk).corpo


def test_evento_morto_nao_conta_como_fato():
    """A separação que faz a fila de mortos valer a pena."""
    EventoMorto.objects.create(corpo="{}", motivo="vazio")
    assert Evento.objects.count() == 0
