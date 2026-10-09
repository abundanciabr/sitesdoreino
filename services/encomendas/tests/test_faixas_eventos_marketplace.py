"""Fatos das faixas: emissão na origem, idempotência, estorno e carga histórica."""

import uuid
from datetime import timedelta

import pytest
from django.apps import apps as django_apps
from django.utils import timezone

from apps.encomendas import faixas_eventos as fe
from apps.encomendas import fila_real, sandbox
from apps.encomendas.faixas_carga import carregar
from apps.encomendas.models import (
    AcordoMarketplace, EventoMarketplace, OutboxMarketplace, ParticipacaoSandbox,
    PedidoMarketplace, ProjetoSandbox, RecebivelMarketplace,
)
from tests.test_fila_real_marketplace import SITE, _dados, _deposito_confirmado, cenario  # noqa: F401

pytestmark = pytest.mark.django_db


def saidas(evento):
    return list(OutboxMarketplace.objects.filter(event=evento).order_by("occurred_at", "pk"))


def _aprovado(real=True, valor="50,00", pessoa_id="aluno-autorizado"):
    pedido = fila_real.criar_pedido(site_id=SITE, slug="tilon", pessoa_id="cliente-tilon", dados=_dados(valor))
    if real:
        _deposito_confirmado(pedido)
    fila_real.aceitar(site_id=SITE, pessoa_id=pessoa_id, pedido_id=pedido.pk)
    arq = fila_real.adicionar_arquivo(site_id=SITE, pessoa_id=pessoa_id, pedido_id=pedido.pk,
                                      nome="a.blend", chave=f"t/{uuid.uuid4()}.blend")
    ent = fila_real.entregar(site_id=SITE, pessoa_id=pessoa_id, pedido_id=pedido.pk, arquivos_ids=[arq.pk])
    fila_real.aprovar(site_id=SITE, pessoa_id="cliente-tilon", pedido_id=pedido.pk, entrega_id=ent.pk)
    pedido.refresh_from_db()
    return pedido


def test_aceite_na_fila_emite_fato_do_aluno_e_nao_do_cliente(cenario):
    pedido = fila_real.criar_pedido(site_id=SITE, slug="tilon", pessoa_id="cliente-tilon", dados=_dados())
    assert saidas(fe.EV_FILA) == []  # o pedido do cliente não é fato do aluno
    fila_real.aceitar(site_id=SITE, pessoa_id="aluno-autorizado", pedido_id=pedido.pk)
    fila_real.aceitar(site_id=SITE, pessoa_id="aluno-autorizado", pedido_id=pedido.pk)  # repetição
    [o] = saidas(fe.EV_FILA)
    acordo = AcordoMarketplace.objects.get(pedido=pedido)
    assert o.event_id == uuid.uuid5(uuid.NAMESPACE_URL, f"meshcraft-faixas:{fe.EV_FILA}:{acordo.pk}")
    assert o.payload["pessoa_id"] == "aluno-autorizado" and o.payload["site_id"] == SITE
    assert o.payload["pedido_id"] == str(pedido.pk) and o.payload["historico"] is False
    assert o.payload["ocorrido_em"]


def test_sandbox_emite_ao_criar_participacao(db):
    projeto = ProjetoSandbox.objects.create(site_id="escola-a", slug="arte", titulo="Arte", briefing="b",
                                            referencias=[], entregaveis=[], criterios="c",
                                            recompensa=5, prazo_dias=3, categoria="pets", ativo=True)
    p = sandbox.aceitar(site_id="escola-a", pessoa_id="aluno-1", projeto_id=projeto.pk)
    [o] = saidas(fe.EV_SANDBOX)
    assert o.payload == {"site_id": "escola-a", "pessoa_id": "aluno-1", "trabalho_id": str(p.pk),
                         "ocorrido_em": p.aceite_em.isoformat(), "historico": False}
    assert o.event_id == fe.event_id(fe.EV_SANDBOX, p.pk)
    fe.sandbox_trabalho_criado(p)  # idempotente
    assert len(saidas(fe.EV_SANDBOX)) == 1


def test_rendimento_real_confirma_uma_vez_com_valor_liquido(cenario):
    pedido = _aprovado()
    r = RecebivelMarketplace.objects.get(pedido=pedido)
    [o] = saidas(fe.EV_CONFIRMADO)
    assert o.payload["valor_cents"] == 5000 and o.payload["rendimento_id"] == str(r.pk)
    assert o.payload["pessoa_id"] == "aluno-autorizado" and o.payload["historico"] is False
    assert o.event_id == fe.event_id(fe.EV_CONFIRMADO, f"{r.pk}:1")
    assert fe.sincronizar_rendimento(r) == []
    assert fe.reconciliar() == 0
    assert len(saidas(fe.EV_CONFIRMADO)) == 1 and saidas(fe.EV_REVERTIDO) == []


def test_sem_sinal_de_pagamento_real_nao_conta(cenario):
    _aprovado(real=False)  # só créditos internos do ClienteFila
    assert saidas(fe.EV_CONFIRMADO) == []


def test_ambiente_sandbox_nao_conta(cenario):
    pedido = _aprovado()
    assert len(saidas(fe.EV_CONFIRMADO)) == 1
    PedidoMarketplace.objects.filter(pk=pedido.pk).update(ambiente="sandbox")
    assert fe.valor_que_vale(RecebivelMarketplace.objects.get(pedido=pedido)) is None
    assert fe.reconciliar() == 1  # vira reversão
    assert len(saidas(fe.EV_REVERTIDO)) == 1


def test_excecao_reverte_e_volta_a_confirmar_com_ids_novos(cenario):
    pedido = _aprovado()
    r = RecebivelMarketplace.objects.get(pedido=pedido)
    r.status = "excecao"
    r.save(update_fields=["status"])  # gancho do post_save
    [rev] = saidas(fe.EV_REVERTIDO)
    assert rev.payload["valor_cents"] == 5000 and rev.payload["rendimento_id"] == str(r.pk)
    assert rev.event_id == fe.event_id(fe.EV_REVERTIDO, f"{r.pk}:1")
    r.status = "pendente"
    r.save(update_fields=["status"])
    conf = saidas(fe.EV_CONFIRMADO)
    assert len(conf) == 2 and conf[1].event_id == fe.event_id(fe.EV_CONFIRMADO, f"{r.pk}:2")
    assert len({o.event_id for o in conf}) == 2


def test_pedido_cancelado_e_sinal_desfeito_revertem(cenario):
    pedido = _aprovado()
    PedidoMarketplace.objects.filter(pk=pedido.pk).update(status="cancelado")  # sem gancho
    assert fe.reconciliar() == 1  # o batimento pega
    assert len(saidas(fe.EV_REVERTIDO)) == 1
    PedidoMarketplace.objects.filter(pk=pedido.pk).update(status="aprovado")
    assert fe.reconciliar() == 1  # voltou: confirma de novo, ciclo 2
    vinculo = pedido.fila_cliente
    vinculo.pagamento_real_confirmado_em = None
    vinculo.save(update_fields=["pagamento_real_confirmado_em"])  # gancho do vinculo
    assert len(saidas(fe.EV_CONFIRMADO)) == 2 and len(saidas(fe.EV_REVERTIDO)) == 2


def test_valor_que_muda_reverte_o_antigo_e_confirma_o_novo(cenario):
    pedido = _aprovado()
    r = RecebivelMarketplace.objects.get(pedido=pedido)
    r.valor_liquido_cents = 4500
    r.save(update_fields=["valor_liquido_cents"])
    assert [o.payload["valor_cents"] for o in saidas(fe.EV_REVERTIDO)] == [5000]
    assert [o.payload["valor_cents"] for o in saidas(fe.EV_CONFIRMADO)] == [5000, 4500]


def test_criterio_da_carga_bate_com_o_da_funcao_existente(cenario):
    ok = _aprovado()
    # Dois pedidos pertencem a dois alunos; cada aluno participa uma única vez.
    from apps.encomendas.models import Pessoa, PerfilProfissional, AutorizacaoMarketplaceAluno
    outra = Pessoa.objects.create(id_da_plataforma="aluno-do-segundo-pedido")
    PerfilProfissional.objects.create(pessoa=outra, site_id=SITE)
    AutorizacaoMarketplaceAluno.objects.create(site_id=SITE, pessoa=outra, ativa=True, autorizada_por="admin-teste")
    sem_sinal = _aprovado(real=False, pessoa_id=outra.pk)
    ids = set(fe.recebiveis_validos(RecebivelMarketplace).values_list("pedido_id", flat=True))
    assert ids == {ok.pk}
    for p in (ok, sem_sinal):
        assert bool(fila_real._depositado(p)) == (p.pk in ids)


def test_carga_historica_idempotente_e_so_o_primeiro(cenario):
    pedido = _aprovado()
    projeto = ProjetoSandbox.objects.create(site_id=SITE, slug="a", titulo="A", briefing="b", referencias=[],
                                            entregaveis=[], criterios="c")
    agora = timezone.now()
    for i in range(2):
        ParticipacaoSandbox.objects.create(site_id=SITE, pessoa_id="aluno-autorizado", projeto=projeto,
                                           status="aprovado", aceite_em=agora - timedelta(days=5 - i),
                                           prazo_ate=agora)
    OutboxMarketplace.objects.all().delete()
    EventoMarketplace.objects.filter(chave__startswith="faixas:").delete()
    m = django_apps.get_model
    args = [m("encomendas", n) for n in ("ParticipacaoSandbox", "AcordoMarketplace", "RecebivelMarketplace",
                                         "EventoMarketplace", "OutboxMarketplace")]
    assert carregar(*args) == {"sandbox": 1, "fila": 1, "rendimento": 1}
    assert carregar(*args) == {"sandbox": 0, "fila": 0, "rendimento": 0}
    for ev in (fe.EV_SANDBOX, fe.EV_FILA, fe.EV_CONFIRMADO):
        [o] = saidas(ev)
        assert o.payload["historico"] is True
    r = RecebivelMarketplace.objects.get(pedido=pedido)
    assert saidas(fe.EV_CONFIRMADO)[0].event_id == fe.event_id(fe.EV_CONFIRMADO, f"{r.pk}:1")
    assert fe.sincronizar_rendimento(r) == []  # o ao vivo reconhece o que a carga publicou
