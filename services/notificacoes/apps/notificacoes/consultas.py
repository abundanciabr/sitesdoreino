# apps/notificacoes/consultas.py  # [RECEITA:R1 v1]
"""As duas perguntas de LEITURA que a Fase 4 do sininho abriu: quantos avisos
faltam ler, e quais são. Ficam à parte de `services.py` (que só teve ESCRITAS
até esta fase) porque leitura não carrega o mesmo risco de invariante
transacional — não há `F()`, não há `atomic()`, só consulta.

Lei do desenho: `contracts/notificacoes.openapi.yaml` (congelado, Rito de
Contrato de 27/08/2026) e `docs/decisoes/DECISAO-fase-4-do-sininho.md`. A
tradução HTTP mora em `apps/core/api.py` — aqui é só a pergunta ao banco.

**Por que `pagina_de_avisos` lê DUAS tabelas.** O arquivamento
(`DECISAO-notificacoes` §5.2) move o lido-e-velho para fora do caminho quente
— mas o motivo de existir uma tabela separada, em vez de apagar a linha, é que
"nada se perde: o histórico continua consultável" (docstring de
`NotificacaoArquivada` em `models.py`). Esta é a ÚNICA porta de consulta que a
Fase 4 abriu; se ela lesse só a tabela quente, um aviso lido sumiria da vida da
pessoa 30 dias depois de ela o ter lido — a promessa do arquivamento
funcionando ao contrário. As duas consultas por página custam o mesmo,
independente de quantas linhas existirem em qualquer uma das tabelas (LIMIT
fixo + os índices de `models.py`): é a mesma exigência de O(1) do `/resumo`,
aplicada à lista.

**Por que nenhuma consulta aqui filtra por `site_id`.** O contrato congelado
não tem parâmetro `site_id` em rota nenhuma — só `destinatario_id`, sempre
descrito como "Id da PLATAFORMA da pessoa" (nunca "do site"). Ver a nota no
índice de `Notificacao.Meta` em `models.py` e `LICOES.md` desta célula.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime

from django.db.models import Sum

from .models import ContadorDeNaoLidos, Notificacao, NotificacaoArquivada

LIMITE_MINIMO = 1
LIMITE_MAXIMO = 100
LIMITE_PADRAO = 20

# As duas fontes que uma carta pode vir de, codificadas no cursor e no `id` que
# a API devolve — nunca o dígito puro da chave primária. `Notificacao.pk` e
# `NotificacaoArquivada.pk` são sequências INDEPENDENTES: sem o prefixo, duas
# linhas de tabelas diferentes poderiam chegar na mesma página com o mesmo
# "id", e qualquer lista no front (React, ou o que for) que use `id` como
# chave colidiria em silêncio.
_FONTE_ATIVA = "n"
_FONTE_ARQUIVADA = "a"


class CursorInvalido(Exception):
    """O cursor recebido não é um que esta célula tenha devolvido."""


def resumo_de_nao_lidos(*, destinatario_id: str) -> int:
    """Quantos avisos não lidos — soma do `ContadorDeNaoLidos` (O(1) desde a gênese).

    Não existe `COUNT(*)` aqui: o contador já é mantido, por carta, na mesma
    transação de `apps/notificacoes/services.py::guardar`. `Sum` (e não um
    laço somando em Python) porque `destinatario_id` sozinho pode um dia casar
    com mais de uma linha — uma por `site_id` que a pessoa já tiver tocado
    (ver o porquê no docstring do módulo) — e a soma continua sendo UMA
    consulta, independente de quantos sites ou quantos avisos existirem.
    """
    total = ContadorDeNaoLidos.objects.filter(
        destinatario_id=destinatario_id
    ).aggregate(total=Sum("nao_lidos"))["total"]
    return total or 0


def _codificar_cursor(*, criado_em: datetime, fonte: str, pk: int) -> str:
    """Opaco de propósito — o contrato só promete "devolvido pela página
    anterior", nunca um formato. Base64 de um JSON pequeno: sobra espaço para
    crescer (um dia a chave pode precisar de mais um campo) sem quebrar cursor
    já distribuído por aí, porque ninguém além desta função o decodifica.
    """
    bruto = json.dumps([criado_em.isoformat(), fonte, pk])
    return base64.urlsafe_b64encode(bruto.encode("utf-8")).decode("ascii")


def _decodificar_cursor(cursor: str) -> tuple[datetime, str, int]:
    try:
        bruto = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        criado_em_iso, fonte, pk = json.loads(bruto)
        if fonte not in (_FONTE_ATIVA, _FONTE_ARQUIVADA):
            raise ValueError(f"fonte desconhecida: {fonte!r}")
        if not isinstance(pk, int):
            raise ValueError(f"pk não é inteiro: {pk!r}")
        criado_em = datetime.fromisoformat(criado_em_iso)
    except CursorInvalido:
        raise
    except Exception as exc:  # noqa: BLE001 - qualquer forma estranha é 422, nunca 500
        raise CursorInvalido(f"cursor ilegível: {exc}") from exc
    return criado_em, fonte, pk


def _candidatos(queryset, *, fonte: str, cursor_dt: datetime | None, limite: int):
    """Até `limite + 1` linhas de UMA tabela, mais novas primeiro.

    O `+1` é o que permite responder "existe próxima página?" sem uma segunda
    consulta: se sobrar mais que `limite` depois do merge das duas fontes, a
    (limite+1)-ésima prova que há mais.

    `criado_em__lte` (inclusive) e não `<`: a exclusão exata do que já foi
    visto acontece depois, em Python, comparando a chave composta
    `(criado_em, fonte, pk)` inteira contra o cursor — nunca só `criado_em`.
    Se dependesse só de `<` no banco, duas cartas com o MESMO `criado_em` (o
    relógio tem resolução de microssegundos, mas duas escritas na mesma
    transação de teste podem colidir) perderiam uma delas para sempre: a
    primeira página devolve só uma das duas como cursor, e um `<` estrito no
    banco excluiria a outra na página seguinte por engano.
    """
    if cursor_dt is not None:
        queryset = queryset.filter(criado_em__lte=cursor_dt)
    linhas = list(queryset.order_by("-criado_em", "-id")[: limite + 1])
    return [((linha.criado_em, fonte, linha.pk), fonte, linha) for linha in linhas]


def pagina_de_avisos(
    *, destinatario_id: str, cursor: str | None, limite: int
) -> tuple[list[dict], str | None]:
    """Uma página de avisos desta pessoa, mais novo primeiro.

    Busca até `limite + 1` linhas de CADA tabela (Notificacao +
    NotificacaoArquivada — sempre as duas, nunca uma sozinha: ver o porquê no
    docstring do módulo), junta as duas listas (já ordenadas) num merge em
    Python, corta no `limite` e decide o próximo cursor pelo item que sobrou.
    Sempre EXATAMENTE duas consultas SQL, com `LIMIT` fixo — o custo não
    cresce com o total de avisos que existirem em qualquer uma das tabelas
    (`tests/test_volume_da_api.py` mede).

    `limite` já chega validado e dentro de [`LIMITE_MINIMO`, `LIMITE_MAXIMO`]
    — quem valida é `apps/core/api.py`, que também é quem transforma
    `CursorInvalido` em 422. Esta função confia no que recebe.
    """
    cursor_dt: datetime | None = None
    chave_cursor: tuple[datetime, str, int] | None = None
    if cursor:
        cursor_dt, cursor_fonte, cursor_pk = _decodificar_cursor(cursor)
        chave_cursor = (cursor_dt, cursor_fonte, cursor_pk)

    candidatos = _candidatos(
        Notificacao.objects.filter(destinatario_id=destinatario_id),
        fonte=_FONTE_ATIVA,
        cursor_dt=cursor_dt,
        limite=limite,
    )
    candidatos += _candidatos(
        NotificacaoArquivada.objects.filter(destinatario_id=destinatario_id),
        fonte=_FONTE_ARQUIVADA,
        cursor_dt=cursor_dt,
        limite=limite,
    )
    candidatos.sort(key=lambda candidato: candidato[0], reverse=True)

    if chave_cursor is not None:
        candidatos = [c for c in candidatos if c[0] < chave_cursor]

    pagina = candidatos[:limite]
    tem_mais = len(candidatos) > limite

    itens = [
        {
            "id": f"{fonte}{linha.pk}",
            "assunto": linha.assunto,
            "parametros": linha.parametros,
            "ator_id": linha.ator_id,
            "lido_em": linha.lido_em,
            "criado_em": linha.criado_em,
        }
        for _, fonte, linha in pagina
    ]

    proximo_cursor = None
    if pagina and tem_mais:
        _, ultima_fonte, ultima_linha = pagina[-1]
        proximo_cursor = _codificar_cursor(
            criado_em=ultima_linha.criado_em, fonte=ultima_fonte, pk=ultima_linha.pk
        )
    return itens, proximo_cursor
