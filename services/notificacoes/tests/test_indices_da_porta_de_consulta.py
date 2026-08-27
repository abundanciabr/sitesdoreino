# tests/test_indices_da_porta_de_consulta.py  # [RECEITA:R1 v1]
"""Os índices de `models.py` casam com a query que a Fase 4 realmente faz —
MEDIDO com `EXPLAIN ANALYZE`, não suposto (CONSTITUICAO.md Lei 6: "qualquer
alegação arquitetural vem com o comando que a falsificaria").

**Por que este arquivo existe.** A migração `0002_indices_da_porta_de_consulta`
apostou que a leitura filtraria só por `destinatario_id` — apostou ANTES da
emenda de 27/08/2026 que tornou `site_id` obrigatório também (decisão do
mantenedor, CONSTITUICAO.md Lei 9: "cada site mostra só os avisos que vieram
dele"). A aposta perdeu, e não dava para ver isso sem medir: com poucas
linhas (o caso comum de dev/CI), o Postgres nem usa índice — SEMPRE faz
sentido escolher um plano ruim quando ele é rápido de qualquer jeito. O
sintoma só aparece com uma pessoa que tenha linhas espalhadas por vários
sites, e é exatamente esse cenário que este arquivo semeia.

**A medição, em prosa** (a `0003_indices_corrigidos_para_site_id_obrigatorio`
tem os números exatos no comentário de topo): com uma pessoa em 5 sites
(1.500 linhas, 300 no site pedido) e 500 pessoas de ruído no site pedido, o
índice ANTIGO (`destinatario_id` sozinho) lia as 1.500 linhas da pessoa em
QUALQUER site e só depois descartava 1.200 com um `Filter` pós-índice. O
índice NOVO (`site_id` + `destinatario_id` liderando juntos) usa `Index Cond`
para as duas colunas e não descarta nenhuma linha.

Este teste NÃO cravou o custo em consultas (`assertNumQueries`, que já mora
em `tests/test_api.py` — seção CUSTO): uma consulta ENGANOSAMENTE eficiente
em contagem pode ainda estar lendo dez vezes mais linhas do que precisa. Este
arquivo mede a outra metade: o formato do PLANO.
"""

import uuid

import pytest
from django.utils import timezone

from apps.notificacoes.models import ContadorDeNaoLidos, Notificacao

pytestmark = pytest.mark.django_db

ALVO_DEST = "idt-pessoa-alvo"
ALVO_SITE = "site-alvo"
OUTROS_SITES = ["site-b", "site-c", "site-d", "site-e"]
LINHAS_POR_SITE_DO_ALVO = 60
PESSOAS_DE_RUIDO = 80
LINHAS_POR_PESSOA_DE_RUIDO = 10


def _semear_avisos_espalhados_por_varios_sites() -> None:
    """A pessoa-alvo tem linhas em 5 sites — só assim um índice que ignora
    `site_id` fica visivelmente pior que um que não ignora: com a pessoa
    inteira num site só, os dois índices leriam o mesmo tanto por acidente.
    """
    agora = timezone.now()
    lote = []
    for site in [ALVO_SITE, *OUTROS_SITES]:
        for i in range(LINHAS_POR_SITE_DO_ALVO):
            lote.append(
                Notificacao(
                    site_id=site,
                    destinatario_id=ALVO_DEST,
                    ator_id=None,
                    assunto="sugestao.status-alterado",
                    parametros={"i": i},
                    origem_event_id=uuid.uuid4(),
                    criado_em=agora - timezone.timedelta(minutes=i),
                )
            )
    for p in range(PESSOAS_DE_RUIDO):
        for i in range(LINHAS_POR_PESSOA_DE_RUIDO):
            lote.append(
                Notificacao(
                    site_id=ALVO_SITE,
                    destinatario_id=f"idt-ruido-{p}",
                    ator_id=None,
                    assunto="sugestao.status-alterado",
                    parametros={"i": i},
                    origem_event_id=uuid.uuid4(),
                    criado_em=agora - timezone.timedelta(minutes=i),
                )
            )
    Notificacao.objects.bulk_create(lote)
    # Estatísticas frescas: sem isto o planejador decide com o "achismo" de
    # tabela vazia que o Postgres assume por padrão, e escolheria um plano
    # tão ruim quanto bom por falta de informação — não é o que este teste
    # quer medir (quer medir a ESCOLHA do planejador informado, não um chute).
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("ANALYZE notificacoes_notificacao")


PESSOAS_DE_RUIDO_DO_CONTADOR = 600


def _semear_contador_espalhado_por_varios_sites() -> None:
    """`ContadorDeNaoLidos` é uma linha por (pessoa, site) — bem menor que
    `Notificacao` na mesma plateia. Com poucas centenas de linhas o Postgres
    prefere corretamente um `Seq Scan` (não é bug: para tabela pequena, ler
    tudo sequencialmente É mais barato que ir e voltar num índice). Este
    teste precisa de gente de ruído suficiente para que o índice realmente
    compense — é o mesmo tamanho (~500) que a investigação manual usou para
    medir a decisão do PR que corrigiu os índices.
    """
    ContadorDeNaoLidos.objects.bulk_create(
        [
            ContadorDeNaoLidos(site_id=site, destinatario_id=ALVO_DEST, nao_lidos=7)
            for site in [ALVO_SITE, *OUTROS_SITES]
        ]
        + [
            ContadorDeNaoLidos(
                site_id=ALVO_SITE, destinatario_id=f"idt-ruido-{p}", nao_lidos=3
            )
            for p in range(PESSOAS_DE_RUIDO_DO_CONTADOR)
        ]
    )
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("ANALYZE notificacoes_contadordenaolidos")


def _plano_de_texto(queryset) -> str:
    return "\n".join(queryset.explain(analyze=True, buffers=True).splitlines())


def test_a_pagina_de_avisos_usa_indice_nas_duas_colunas_sem_descartar_linhas():
    """A consulta real de `pagina_de_avisos` (site_id + destinatario_id,
    ordenado por -criado_em, com LIMIT) não pode ler linha de OUTRO site."""
    _semear_avisos_espalhados_por_varios_sites()

    queryset = Notificacao.objects.filter(
        site_id=ALVO_SITE, destinatario_id=ALVO_DEST
    ).order_by("-criado_em", "-id")[:21]
    plano = _plano_de_texto(queryset)

    assert (
        "notif_caixa_da_pessoa" in plano
    ), f"a consulta não usou o índice esperado — plano:\n{plano}"
    assert "Rows Removed by Filter" not in plano, (
        "o índice não está cobrindo site_id: o Postgres leu linhas de OUTROS "
        f"sites da mesma pessoa e descartou depois. Plano:\n{plano}"
    )


def test_o_resumo_usa_indice_nas_duas_colunas_sem_descartar_linhas():
    """`resumo_de_nao_lidos` — mesma pergunta, para `ContadorDeNaoLidos`.

    Aqui não existe (nem precisa existir) um índice PRÓPRIO desta rota: o
    `UniqueConstraint contador_um_por_pessoa` (`site_id`, `destinatario_id`)
    já É o índice ideal. Este teste é o que prova que ele continua sendo
    escolhido — se algum dia sumir ou for substituído por um pior, é aqui
    que quebra.
    """
    _semear_contador_espalhado_por_varios_sites()

    queryset = ContadorDeNaoLidos.objects.filter(
        site_id=ALVO_SITE, destinatario_id=ALVO_DEST
    ).values_list("nao_lidos", flat=True)
    plano = _plano_de_texto(queryset)

    assert (
        "contador_um_por_pessoa" in plano
    ), f"a consulta não usou o índice único esperado — plano:\n{plano}"
    assert (
        "Rows Removed by Filter" not in plano
    ), f"o índice não está cobrindo as duas colunas. Plano:\n{plano}"
