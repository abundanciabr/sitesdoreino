# tests/test_backfill_cartas_dos_avisos_existentes.py  # [RECEITA:R5 v1]
"""A migration `0008` reemite os `Aviso` já existentes como cartas
`notificacao.devida.v1` — a segunda metade da FASE 3 do
`docs/notificacoes/PLANO-MESTRE.md` (`DECISAO-fase-2-do-sininho.md` §3).

Chama a função do `RunPython` DIRETO (não `python manage.py migrate`): é o
padrão que o próprio despacho pediu, para poder falsificar idempotência e
volume sem precisar desfazer e refazer uma migration de verdade a cada teste.
`django.apps.apps` (o registro AO VIVO) serve tão bem quanto o histórico que o
Django injeta em produção — a função só chama `.get_model(...)`, e é
exatamente o padrão que o próprio Django recomenda para testar RunPython
isoladamente.

Cinco guardas, cada um falsificando uma decisão do despacho:

1. **idempotência** — rodar duas vezes não duplica carta nenhuma;
2. **o filtro** — destinatário sem `id_da_plataforma` fica de fora, sem
   estourar (o mesmo pulo que `ids_de_plataforma()` já faz no caminho ao
   vivo);
3. **volume** — o custo em consultas não cresce com o número de avisos;
4. **`occurred_at`** — preserva o `criado_em` do `Aviso`, não a hora do
   backfill (a pegadinha do `auto_now_add` com `bulk_create`, já vivida
   nesta célula para `Voto.criado_em` — `LICOES.md`);
5. **a forma da carta** — `ator_id` nulo, `origem_event_id` sintético e
   PRÓPRIO de cada `Aviso`, e o envelope inteiro validando contra o
   contrato congelado quando passa pelo relay de verdade.
"""

from __future__ import annotations

import importlib
import json
from datetime import timedelta
from pathlib import Path

import pytest
from django.apps import apps as registro_ao_vivo
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from jsonschema import Draft202012Validator, FormatChecker

from apps.sugestoes.models import Aviso, Identidade, OutboxEvent, Sugestao
from apps.sugestoes.tasks import relay_outbox

pytestmark = pytest.mark.django_db

migracao = importlib.import_module(
    "apps.sugestoes.migrations.0008_backfill_cartas_dos_avisos_existentes"
)

CONTRATOS = Path(__file__).resolve().parents[3] / "contracts" / "eventos"

PEQUENA = 2
GRANDE = 200


def _rodar_backfill() -> None:
    migracao.publicar_cartas_retroativas(registro_ao_vivo, None)


def _cartas():
    return list(
        OutboxEvent.objects.filter(event=migracao.NOTIFICACAO_DEVIDA).order_by("id")
    )


def _uma_pessoa(email: str, *, com_id_da_plataforma: bool = True) -> Identidade:
    return Identidade.objects.create(
        email=email,
        id_da_plataforma=f"idt-{email}" if com_id_da_plataforma else None,
    )


def _um_aviso(quadro, categoria, destinatario, *, autor=None, nota: str = "") -> Aviso:
    sugestao = Sugestao.objects.create(
        quadro=quadro,
        categoria=categoria,
        autor=autor or destinatario,
        titulo=f"Sugestão de {destinatario.email}",
        problema="Assisto no ônibus e não dá para ouvir.",
    )
    return Aviso.objects.create(
        destinatario=destinatario,
        sugestao=sugestao,
        status_anterior=Sugestao.Status.EM_ANALISE,
        status_novo=Sugestao.Status.PLANEJADO,
        nota=nota,
    )


def _preparar_avisos(quadro, categoria, quantidade: int, marca: str) -> None:
    """`quantidade` avisos, cada um de uma pessoa DISTINTA — pelo ORM em lote,
    como a fixture `plateia` já faz, para a preparação do cenário não pesar na
    medição de consultas do teste de volume."""
    pessoas = Identidade.objects.bulk_create(
        [
            Identidade(
                email=f"{marca}-{n}@exemplo.test", id_da_plataforma=f"idt-{marca}-{n}"
            )
            for n in range(quantidade)
        ]
    )
    sugestoes = Sugestao.objects.bulk_create(
        [
            Sugestao(
                quadro=quadro,
                categoria=categoria,
                autor=pessoa,
                titulo=f"Sugestão {marca}-{n}",
                problema="Assisto no ônibus e não dá para ouvir.",
            )
            for n, pessoa in enumerate(pessoas)
        ]
    )
    Aviso.objects.bulk_create(
        [
            Aviso(
                destinatario=pessoa,
                sugestao=sugestao,
                status_anterior=Sugestao.Status.EM_ANALISE,
                status_novo=Sugestao.Status.PLANEJADO,
            )
            for pessoa, sugestao in zip(pessoas, sugestoes)
        ]
    )


# ---------------------------------------------------------------------------
# 1. Idempotência
# ---------------------------------------------------------------------------


def test_a_segunda_passada_nao_duplica_cartas(quadro, categoria):
    destinatario = _uma_pessoa("aluno-antigo@exemplo.test")
    _um_aviso(quadro, categoria, destinatario, nota="Entra no ciclo.")

    _rodar_backfill()
    primeira = OutboxEvent.objects.filter(event=migracao.NOTIFICACAO_DEVIDA).count()
    assert primeira == 1, "a primeira passada devia publicar exatamente uma carta"

    _rodar_backfill()
    segunda = OutboxEvent.objects.filter(event=migracao.NOTIFICACAO_DEVIDA).count()

    assert segunda == primeira, (
        f"a segunda passada duplicou cartas: {primeira} -> {segunda}. "
        "É exatamente o cenário anômalo (rollback + reapply) que o event_id "
        "determinístico existe para impedir."
    )


def test_rodar_duas_vezes_sem_avisos_novos_nao_estoura(quadro, categoria):
    """Nada a fazer na segunda passada não é erro — é o caso comum."""
    _um_aviso(quadro, categoria, _uma_pessoa("sozinho@exemplo.test"))
    _rodar_backfill()

    _rodar_backfill()  # não deve estourar mesmo sem nada de novo para publicar

    assert OutboxEvent.objects.filter(event=migracao.NOTIFICACAO_DEVIDA).count() == 1


# ---------------------------------------------------------------------------
# 2. O filtro — mesma assimetria do caminho ao vivo
# ---------------------------------------------------------------------------


def test_aviso_sem_id_da_plataforma_fica_de_fora_sem_estourar(quadro, categoria):
    sem_id = _uma_pessoa("nunca-voltou@exemplo.test", com_id_da_plataforma=False)
    aviso_sem_id = _um_aviso(quadro, categoria, sem_id)
    com_id = _uma_pessoa("voltou-ontem@exemplo.test")
    _um_aviso(quadro, categoria, com_id)

    _rodar_backfill()  # não deve estourar por causa do destinatário sem id

    (carta,) = _cartas()
    assert carta.payload["destinatario_id"] == "idt-voltou-ontem@exemplo.test"
    # O aviso sem id da plataforma NÃO virou carta — mas continua existindo
    # localmente, exatamente como o caminho ao vivo também preserva o Aviso.
    assert Aviso.objects.filter(pk=aviso_sem_id.pk).exists()


# ---------------------------------------------------------------------------
# 3. Volume — o custo em consultas não cresce com o número de avisos
# ---------------------------------------------------------------------------


def _contar(fazer) -> int:
    with CaptureQueriesContext(connection) as consultas:
        fazer()
    return len(consultas)


def test_o_backfill_custa_o_mesmo_com_poucos_e_com_muitos_avisos(quadro, categoria):
    """Duas medições no MESMO teste, como `test_volume_das_cartas.py` já faz.

    A função não é parametrizada por sugestão — ela sempre processa TODOS os
    avisos pendentes de carta — então a segunda medição inevitavelmente
    reprocessa a tabela inteira (os `PEQUENA` de antes, já publicados e
    portanto pulados pela idempotência, MAIS os `GRANDE` novos). Isso não
    invalida a medição: o que se prova é que o número de CONSULTAS não cresce
    com o tamanho da lista de candidatos — 2 candidatos ou 202, mesmo total de
    idas ao banco, contanto que caibam no mesmo lote (`TAMANHO_DO_LOTE`, hoje
    500, folga de sobra para os dois números deste teste).
    """
    _preparar_avisos(quadro, categoria, PEQUENA, "peq")
    poucas = _contar(_rodar_backfill)

    _preparar_avisos(quadro, categoria, GRANDE, "gra")
    muitas = _contar(_rodar_backfill)

    assert (
        OutboxEvent.objects.filter(event=migracao.NOTIFICACAO_DEVIDA).count()
        == PEQUENA + GRANDE
    )
    assert poucas == muitas, (
        f"o custo do backfill CRESCEU com o número de avisos: {poucas} consultas "
        f"para {PEQUENA} candidatos e {muitas} para {PEQUENA + GRANDE}. Um laço "
        "por aviso é o desenho errado — o lote inteiro tem de caber em consultas "
        "fixas (bulk_create + bulk_update), como test_volume_das_cartas.py exige "
        "para o caminho ao vivo."
    )


# ---------------------------------------------------------------------------
# 4. occurred_at — a pegadinha do auto_now_add com bulk_create
# ---------------------------------------------------------------------------


def test_occurred_at_preserva_o_criado_em_do_aviso_e_nao_a_hora_do_backfill(
    quadro, categoria
):
    """`OutboxEvent.occurred_at` é `auto_now_add=True`: se a migration só
    atribuísse o valor no construtor do `bulk_create`, o INSERT sobrescreveria
    em silêncio com a hora do backfill (a mesma armadilha documentada em
    `LICOES.md` para `Voto.criado_em`). Este teste força um `Aviso` com uma
    data BEM no passado e prova que a carta herda essa data, não "agora"."""
    destinatario = _uma_pessoa("aviso-de-trinta-dias-atras@exemplo.test")
    aviso = _um_aviso(quadro, categoria, destinatario)
    ha_um_mes = timezone.now() - timedelta(days=30)
    Aviso.objects.filter(pk=aviso.pk).update(criado_em=ha_um_mes)

    antes_do_backfill = timezone.now()
    _rodar_backfill()

    (carta,) = _cartas()
    assert carta.occurred_at == ha_um_mes, (
        f"occurred_at devia preservar o criado_em do Aviso ({ha_um_mes!r}), "
        f"e veio {carta.occurred_at!r} — a hora do backfill vazou por cima "
        "(auto_now_add sobrescrevendo o bulk_create em silêncio)."
    )
    assert carta.occurred_at < antes_do_backfill - timedelta(days=29)


# ---------------------------------------------------------------------------
# 5. A forma da carta — as decisões do despacho, e o contrato de verdade
# ---------------------------------------------------------------------------


def test_ator_id_nulo_e_origem_event_id_sintetico_e_proprio_de_cada_carta(
    quadro, categoria
):
    destinatario = _uma_pessoa("duas-cartas@exemplo.test")
    aviso_1 = _um_aviso(quadro, categoria, destinatario, nota="Primeira.")
    aviso_2 = _um_aviso(quadro, categoria, destinatario, nota="Segunda.")

    _rodar_backfill()

    cartas = {c.payload["parametros"]["nota"]: c for c in _cartas()}
    carta_1, carta_2 = cartas["Primeira."], cartas["Segunda."]

    assert carta_1.envelope_extra == {"ator_id": None}
    assert carta_2.envelope_extra == {"ator_id": None}

    origem_1 = carta_1.payload["origem_event_id"]
    origem_2 = carta_2.payload["origem_event_id"]
    assert origem_1 != origem_2, (
        "cada Aviso deve gerar seu PRÓPRIO origem_event_id sintético — "
        "diferente do caminho ao vivo, o backfill não tem como saber que "
        "dois avisos vieram da mesma mudança de status."
    )
    # E determinístico: recalculável a partir só do pk do Aviso.
    assert origem_1 == str(migracao._origem_event_id_sintetico(aviso_1.pk))
    assert origem_2 == str(migracao._origem_event_id_sintetico(aviso_2.pk))


def _validador(evento: str, versao: int) -> Draft202012Validator:
    schema = json.loads(
        (CONTRATOS / f"{evento}.v{versao}.json").read_text(encoding="utf-8")
    )
    return Draft202012Validator(schema, format_checker=FormatChecker())


def test_a_carta_retroativa_valida_contra_o_contrato_quando_passa_pelo_relay(
    quadro, categoria, fio
):
    """Ponta a ponta: a linha que a migration escreve é a MESMA que o relay
    (`apps/sugestoes/tasks.py`, o código de produção, sem dublê nenhum) lê e
    publica — e o envelope que sai no fio tem de validar contra o contrato
    `notificacao.devida.v1` congelado, com o `FormatChecker` ligado (senão
    `format: uuid` vira anotação decorativa — mesma lição de
    `test_inv_envelope_casa_com_contrato.py`)."""
    destinatario = _uma_pessoa("carta-de-verdade@exemplo.test")
    _um_aviso(quadro, categoria, destinatario, nota="Já existe no menu de aulas.")

    _rodar_backfill()
    assert relay_outbox() == 1

    envelope = fio.um_envelope(migracao.NOTIFICACAO_DEVIDA)
    _validador(envelope["event"], envelope["version"]).validate(envelope)

    assert envelope["ator_id"] is None
    assert envelope["data"]["destinatario_id"] == "idt-carta-de-verdade@exemplo.test"
    assert envelope["data"]["assunto"] == migracao.ASSUNTO_STATUS_ALTERADO
    assert envelope["data"]["parametros"]["nota"] == "Já existe no menu de aulas."
