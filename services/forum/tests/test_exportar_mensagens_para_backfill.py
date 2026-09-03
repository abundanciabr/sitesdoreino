"""O export de histórico para o acerto de contas retroativo do fórum.

Pedido do mantenedor em 03/09/2026: nenhuma mensagem escrita antes de a regra
`forum-mensagem` ser ligada deixou rastro na gamificação (ela não tem
tabela-espelho de mensagem, ao contrário de tópico e resposta aceita). Este
comando é a metade do fórum: só LÊ a própria tabela e imprime JSON — nunca
credita nada, nunca chama outra célula.

O que este arquivo trava:

1. Só mensagens ANTES do corte (`--antes-de`) saem.
2. Mensagem da ESCOLA (autor nulo) não sai — a escola não ganha ponto de si.
3. Mensagem REMOVIDA não sai — o mesmo motivo que já vale no lado da
   gamificação (`NAO_CREDITAM["forum.mensagem-removida"]`).
4. `pessoa_id` no JSON é o id de PLATAFORMA (a PK de `Pessoa` nesta célula),
   nunca outra coisa.
"""

from __future__ import annotations

import json
from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.forum.models import Area, Mensagem, Pessoa, Topico

pytestmark = pytest.mark.django_db


def _pessoa(id_da_plataforma: str) -> Pessoa:
    return Pessoa.objects.create(
        id_da_plataforma=id_da_plataforma,
        email=f"{id_da_plataforma}@exemplo.test",
        nome_exibido="Quem Fala",
    )


def _area() -> Area:
    return Area.objects.create(
        slug="duvidas",
        nome="Dúvidas",
        visibilidade=Area.Visibilidade.ALUNOS,
        quem_escreve=Area.QuemEscreve.ALUNO,
    )


def _mensagem(area, pessoa, *, quando=None, **campos) -> Mensagem:
    topico = Topico.objects.create(area=area, autor=pessoa, titulo="Dúvida")
    base = {"topico": topico, "autor": pessoa, "texto": "opa"}
    base.update(campos)
    mensagem = Mensagem.objects.create(**base)
    if quando is not None:
        Mensagem.objects.filter(pk=mensagem.pk).update(criado_em=quando)
        mensagem.refresh_from_db()
    return mensagem


def _rodar(antes_de) -> list[dict]:
    saida = StringIO()
    call_command(
        "exportar_mensagens_para_backfill",
        "--antes-de",
        antes_de.isoformat(),
        stdout=saida,
    )
    return json.loads(saida.getvalue())


def test_exporta_mensagem_antes_do_corte():
    agora = timezone.now()
    area = _area()
    pessoa = _pessoa("p1")
    msg = _mensagem(area, pessoa, quando=agora - timedelta(days=3))

    (linha,) = _rodar(agora)

    assert linha["pessoa_id"] == "p1"
    assert linha["mensagem_id"] == str(msg.pk)
    assert linha["occurred_at"] == (agora - timedelta(days=3)).isoformat()


def test_nao_exporta_mensagem_depois_do_corte():
    agora = timezone.now()
    area = _area()
    pessoa = _pessoa("p1")
    _mensagem(area, pessoa, quando=agora - timedelta(hours=1))

    linhas = _rodar(agora - timedelta(days=1))

    assert linhas == []


def test_nao_exporta_mensagem_da_escola():
    agora = timezone.now()
    area = _area()
    pessoa = _pessoa("p1")
    topico = Topico.objects.create(area=area, autor=pessoa, titulo="Aviso")
    Mensagem.objects.create(
        topico=topico, autor=None, publicado_pela_escola=True, texto="aviso oficial"
    )
    Mensagem.objects.filter(topico=topico).update(criado_em=agora - timedelta(days=3))

    linhas = _rodar(agora)

    assert linhas == []


def test_nao_exporta_mensagem_removida():
    agora = timezone.now()
    area = _area()
    pessoa = _pessoa("p1")
    msg = _mensagem(area, pessoa, quando=agora - timedelta(days=3))
    Mensagem.objects.filter(pk=msg.pk).update(removida_em=agora - timedelta(days=2))

    linhas = _rodar(agora)

    assert linhas == []


def test_exporta_em_ordem_cronologica():
    agora = timezone.now()
    area = _area()
    pessoa = _pessoa("p1")
    _mensagem(area, pessoa, quando=agora - timedelta(days=2))
    _mensagem(area, pessoa, quando=agora - timedelta(days=4))
    _mensagem(area, pessoa, quando=agora - timedelta(days=3))

    linhas = _rodar(agora)

    momentos = [linha["occurred_at"] for linha in linhas]
    assert momentos == sorted(momentos)
