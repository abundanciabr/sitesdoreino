"""A compra fecha só a oportunidade certa, e uma compra é uma receita."""

import uuid

import pytest

from apps.core.handlers import (
    ao_pagamento_aprovado,
    ao_pagamento_recusado,
    ao_pedido_criado,
    ao_pix_expirado,
    ao_quiz_completado,
    ao_reversao_confirmada,
    processar_envelope,
)
from apps.core.models import CompraDaOportunidade, Oportunidade


pytestmark = pytest.mark.django_db

SITE = "site-a"
EMAIL = "maria@gmail.com"


@pytest.fixture
def admin(settings, monkeypatch):
    settings.TOKENS_ACEITOS.add("admin-compra")
    monkeypatch.setenv("TOKENS_ACEITOS_ADMIN", "admin-compra")
    return {"HTTP_AUTHORIZATION": "Bearer admin-compra"}


def _entregar(handler, dados, event_id=None):
    return processar_envelope(
        {"event_id": event_id or str(uuid.uuid4()), "data": dados}, handler
    )


def quiz(slug, email=EMAIL, site=SITE, **extra):
    _entregar(ao_quiz_completado, {
        "site_id": site, "quiz_slug": slug, "result_key": "iniciante",
        "lead": {"email": email, "name": "Maria"}, **extra,
    })
    return Oportunidade.objects.get(
        lead__email=email, lead__site_id=site, fonte_referencia_id=f"oferta:{slug}"
    )


def pedido(pedido_id, email=EMAIL, site=SITE, produto="prod-1", **extra):
    _entregar(ao_pedido_criado, {
        "site_id": site, "order_id": pedido_id, "checkout_session_id": "s-1",
        "items": [{"product_id": produto, "name": "Curso", "price_cents": 990,
                   "kind": "principal"}],
        "total_cents": 990, "customer": {"email": email, "name": "Maria"}, **extra,
    })


def aprovado(pedido_id, email=EMAIL, site=SITE, referencia=None, valor=990, **extra):
    return _entregar(ao_pagamento_aprovado, {
        "platform_site_id": site, "payment_id": f"pay-{pedido_id}",
        "order_id": pedido_id, "amount_cents": valor, "method": "card",
        "provider": "appmax", "provider_reference_id": referencia or f"ap-{pedido_id}",
        "customer": {"email": email, "name": "Maria"}, **extra,
    })


def recusado(pedido_id, email=EMAIL, site=SITE, tentativa="1"):
    return _entregar(ao_pagamento_recusado, {
        "platform_site_id": site, "payment_id": f"op-{pedido_id}-{tentativa}",
        "order_id": pedido_id, "amount_cents": 990, "method": "card",
        "provider": "appmax", "provider_reference_id": f"ap-r-{tentativa}",
        "reason_code": "saldo", "customer": {"email": email, "name": "Maria"},
    })


def pix_vencido(pedido_id, email=EMAIL, site=SITE):
    return _entregar(ao_pix_expirado, {
        "site_id": site, "payment_id": f"pix-{pedido_id}", "order_id": pedido_id,
        "amount_cents": 990, "method": "pix", "customer": {"email": email},
    })


def estorno(pedido_id, site=SITE, motivo="estorno"):
    return _entregar(ao_reversao_confirmada, {
        "platform_site_id": site, "order_id": pedido_id, "provider": "appmax",
        "provider_reference_id": f"ap-{pedido_id}", "motivo": motivo,
    })


def _recarregar(*oportunidades):
    for oportunidade in oportunidades:
        oportunidade.refresh_from_db()


def test_duas_ofertas_da_mesma_pessoa_e_uma_compra_fecham_so_a_certa(client, admin):
    crivo = quiz("crivo")
    cura = quiz("cura")

    pedido("ped-1", oportunidade_ref=str(cura.id), oferta_ref="oferta-cura")
    _recarregar(crivo, cura)
    assert cura.etapa == "negociacao" and "ped-1" in cura.passo_descricao
    assert crivo.etapa == "nova"

    aprovado("ped-1")
    _recarregar(crivo, cura)
    assert cura.etapa == "ganha" and cura.encerrada
    assert crivo.etapa == "nova" and not crivo.encerrada
    compra = CompraDaOportunidade.objects.get()
    assert compra.oportunidade_id == cura.id and compra.pedido_id == "ped-1"

    receita = client.get(f"/api/leads/crm/{cura.id}/receita", **admin).json()
    assert receita["aprovado_centavos"] == 990
    assert receita["liquido_centavos"] == 990
    assert [c["pedido_id"] for c in receita["compras"]] == ["ped-1"]
    assert client.get(f"/api/leads/crm/{crivo.id}/receita", **admin).json()[
        "aprovado_centavos"] == 0

    fechada = client.get(f"/api/leads/crm/{cura.id}/acompanhamento", **admin).json()
    assert fechada["pode_insistir"] is False
    assert fechada["motivo"] == "compra_aprovada"
    assert fechada["pedido_id"] == "ped-1"
    aberta = client.get(f"/api/leads/crm/{crivo.id}/acompanhamento", **admin).json()
    assert aberta["pode_insistir"] is True
    assert aberta["outras_compras_aprovadas_da_pessoa"] == 1

    quadro = client.get("/api/leads/crm", **admin).json()
    por_id = {item["id"]: item for item in quadro["itens"]}
    assert por_id[str(cura.id)]["acompanhamento"]["pode_insistir"] is False
    assert por_id[str(cura.id)]["receita"]["liquido_centavos"] == 990
    assert por_id[str(crivo.id)]["acompanhamento"]["pode_insistir"] is True


def test_sem_referencia_e_com_duas_ofertas_a_compra_nao_fecha_nenhuma():
    crivo = quiz("crivo")
    cura = quiz("cura")
    pedido("ped-1")
    aprovado("ped-1")
    _recarregar(crivo, cura)
    assert crivo.etapa == "nova" and cura.etapa == "nova"
    compra = CompraDaOportunidade.objects.get()
    assert compra.oportunidade_id is None and compra.aprovado_em is not None


def test_oferta_indicada_pelo_quiz_liga_o_pedido_pela_oferta():
    crivo = quiz("crivo", context={"oferta_ref": "oferta-crivo"})
    cura = quiz("cura", context={"oferta_ref": "oferta-cura"})
    pedido("ped-1", oferta_ref="oferta-crivo")
    aprovado("ped-1")
    _recarregar(crivo, cura)
    assert crivo.etapa == "ganha"
    assert cura.etapa == "nova"


def test_pedido_ligado_guia_compras_seguintes_do_mesmo_produto():
    crivo = quiz("crivo")
    cura = quiz("cura")
    pedido("ped-1", oportunidade_ref=str(crivo.id), produto="prod-crivo")
    recusado("ped-1")
    # Novo pedido do mesmo produto, sem referência: vai para a mesma oferta.
    pedido("ped-2", produto="prod-crivo")
    aprovado("ped-2")
    _recarregar(crivo, cura)
    assert crivo.etapa == "ganha"
    assert cura.etapa == "nova"
    assert CompraDaOportunidade.objects.get(pedido_id="ped-2").oportunidade_id == crivo.id


def test_evento_duplicado_e_aprovacao_repetida_nao_geram_nova_venda(client, admin):
    oferta = quiz("crivo")
    pedido("ped-1", oportunidade_ref=str(oferta.id))
    mesmo_evento = str(uuid.uuid4())
    assert aprovado("ped-1") is True
    # reentrega do mesmo envelope
    dados = {
        "platform_site_id": SITE, "payment_id": "pay-ped-1", "order_id": "ped-1",
        "amount_cents": 990, "method": "card", "provider": "appmax",
        "provider_reference_id": "ap-ped-1", "customer": {"email": EMAIL},
    }
    _entregar(ao_pagamento_aprovado, dados, mesmo_evento)
    assert _entregar(ao_pagamento_aprovado, dados, mesmo_evento) is False
    # mesmo pedido aprovado de novo por outra cobrança (aprovação tardia)
    aprovado("ped-1", referencia="ap-tardia", valor=990)

    assert CompraDaOportunidade.objects.count() == 1
    oferta.refresh_from_db()
    assert oferta.etapa == "ganha"
    assert oferta.historico.filter(tipo="encerramento").count() == 1
    receita = client.get(f"/api/leads/crm/{oferta.id}/receita", **admin).json()
    assert receita["aprovado_centavos"] == 990
    fatos = client.get("/api/leads/receita/fatos", **admin).json()
    assert fatos["totais"]["compras_aprovadas"] == 1
    assert fatos["totais"]["aprovado_centavos"] == 990


def test_aprovacao_depois_de_recusa_e_a_mesma_compra_recuperada(client, admin):
    oferta = quiz("crivo")
    outra = quiz("cura")
    pedido("ped-1", oportunidade_ref=str(oferta.id))
    recusado("ped-1", tentativa="1")
    pix_vencido("ped-1")
    oferta.refresh_from_db()
    assert oferta.etapa == "negociacao"
    assert "Recuperar" in oferta.passo_descricao and "ped-1" in oferta.passo_descricao
    # a recuperação é a da própria oferta: nenhuma oportunidade nova
    assert not Oportunidade.objects.filter(fonte_tipo="pagamento").exists()
    estado = client.get(f"/api/leads/crm/{oferta.id}/acompanhamento", **admin).json()
    assert estado["motivo"] == "recuperar_pagamento"

    aprovado("ped-1")
    _recarregar(oferta, outra)
    assert oferta.etapa == "ganha"
    assert outra.etapa == "nova"
    compra = CompraDaOportunidade.objects.get()
    assert compra.recuperada and len(compra.falhas) == 2
    fatos = client.get("/api/leads/receita/fatos", **admin).json()
    assert fatos["totais"]["compras_recuperadas"] == 1
    assert fatos["totais"]["compras_aprovadas"] == 1
    assert fatos["por_origem"] == [{
        "origem": "quiz:crivo", "compras_aprovadas": 1, "compras_revertidas": 0,
        "compras_recuperadas": 1, "compradores": 1, "aprovado_centavos": 990,
        "estornos_centavos": 0, "liquido_centavos": 990,
    }]


def test_oferta_inicial_e_recuperacao_do_mesmo_pedido_sao_uma_receita(client, admin):
    oferta = quiz("crivo")
    quiz("cura")
    # a recusa chega antes do pedido: sem saber a oferta, abre recuperação
    recusado("ped-1")
    recuperacao = Oportunidade.objects.get(fonte_tipo="pagamento")
    pedido("ped-1", oportunidade_ref=str(oferta.id))
    aprovado("ped-1")
    _recarregar(oferta, recuperacao)
    assert oferta.etapa == "ganha" and recuperacao.etapa == "ganha"
    for item in (oferta, recuperacao):
        receita = client.get(f"/api/leads/crm/{item.id}/receita", **admin).json()
        assert [c["pedido_id"] for c in receita["compras"]] == ["ped-1"]
    fatos = client.get("/api/leads/receita/fatos", **admin).json()
    assert fatos["totais"]["compras_aprovadas"] == 1
    assert fatos["totais"]["liquido_centavos"] == 990


def test_estorno_atualiza_resultado_liquido_e_para_o_acompanhamento(client, admin):
    oferta = quiz("crivo")
    outra = quiz("cura")
    pedido("ped-1", oportunidade_ref=str(oferta.id))
    aprovado("ped-1")
    estorno("ped-1", motivo="contestacao")
    estorno("ped-1", motivo="contestacao")  # reentrega
    _recarregar(oferta, outra)
    assert oferta.etapa == "desqualificada"
    assert oferta.desfecho_motivo == "Pagamento revertido"
    assert outra.etapa == "nova"
    receita = client.get(f"/api/leads/crm/{oferta.id}/receita", **admin).json()
    assert receita["aprovado_centavos"] == 990
    assert receita["estornos_centavos"] == 990
    assert receita["liquido_centavos"] == 0
    assert receita["compras"][0]["motivo_reversao"] == "contestacao"
    estado = client.get(f"/api/leads/crm/{oferta.id}/acompanhamento", **admin).json()
    assert estado["pode_insistir"] is False
    assert estado["motivo"] == "pagamento_revertido"
    fatos = client.get("/api/leads/receita/fatos", **admin).json()["totais"]
    assert fatos["compras_revertidas"] == 1 and fatos["liquido_centavos"] == 0


def test_eventos_fora_de_ordem_nao_criam_venda_nem_recuperacao_falsa():
    oferta = quiz("crivo")
    outra = quiz("cura")
    # pagamento chega antes do pedido: com duas ofertas, ainda não há a quem ligar
    aprovado("ped-1")
    _recarregar(oferta, outra)
    assert oferta.etapa == "nova" and outra.etapa == "nova"
    # recusa velha chega depois da aprovação: nada muda
    recusado("ped-1")
    assert not Oportunidade.objects.filter(fonte_tipo="pagamento").exists()
    # o pedido chega com a referência: liga e fecha só a oferta dele
    pedido("ped-1", oportunidade_ref=str(oferta.id))
    _recarregar(oferta, outra)
    assert oferta.etapa == "ganha"
    assert outra.etapa == "nova"
    compra = CompraDaOportunidade.objects.get()
    assert compra.oportunidade_id == oferta.id
    assert compra.falhas == [] and compra.aprovado_centavos == 990


def test_estorno_antes_da_aprovacao_e_aplicado_quando_ela_chega(client, admin):
    oferta = quiz("crivo")
    pedido("ped-1", oportunidade_ref=str(oferta.id))
    estorno("ped-1")
    oferta.refresh_from_db()
    assert oferta.etapa == "negociacao"
    aprovado("ped-1")
    oferta.refresh_from_db()
    assert oferta.etapa == "desqualificada"
    receita = client.get(f"/api/leads/crm/{oferta.id}/receita", **admin).json()
    assert receita["liquido_centavos"] == 0


def test_referencia_de_outro_site_nao_liga_a_compra():
    oferta_b = quiz("crivo", site="site-b")
    oferta_a = quiz("crivo")
    quiz("cura")
    pedido("ped-1", oportunidade_ref=str(oferta_b.id))
    aprovado("ped-1")
    _recarregar(oferta_a, oferta_b)
    assert oferta_b.etapa == "nova"
    assert oferta_a.etapa == "nova"


def test_compra_com_outro_email_liga_pela_referencia_no_mesmo_site():
    oferta = quiz("crivo")
    pedido("ped-1", email="maria.trabalho@gmail.com", oportunidade_ref=str(oferta.id))
    aprovado("ped-1", email="maria.trabalho@gmail.com")
    oferta.refresh_from_db()
    assert oferta.etapa == "ganha"


def test_fatos_de_receita_deixam_testes_e_sandbox_fora(client, admin):
    real = quiz("crivo")
    teste = quiz("crivo", email="teste@example.com")
    sandbox = quiz("crivo", email="joao@gmail.com")
    pedido("ped-1", oportunidade_ref=str(real.id))
    aprovado("ped-1")
    pedido("ped-2", email="teste@example.com", oportunidade_ref=str(teste.id))
    aprovado("ped-2", email="teste@example.com")
    pedido("ped-3", email="joao@gmail.com", oportunidade_ref=str(sandbox.id),
           metadata={"sandbox": True})
    aprovado("ped-3", email="joao@gmail.com")
    # compra de quem não veio do quiz (aluno) não entra no CRM
    pedido("ped-4", email="aluno@gmail.com")
    aprovado("ped-4", email="aluno@gmail.com")

    fatos = client.get("/api/leads/receita/fatos", **admin).json()
    assert fatos["totais"]["compras_aprovadas"] == 1
    assert fatos["totais"]["aprovado_centavos"] == 990
    assert fatos["testes_fora"] == 2
    assert fatos["por_oferta"][0]["oferta"] == "prod-1"
    filtrado = client.get(
        "/api/leads/receita/fatos", {"desde": "2000-01-01", "ate": "2000-01-02"}, **admin
    ).json()
    assert filtrado["totais"]["compras_aprovadas"] == 0
    assert client.get("/api/leads/receita/fatos", {"desde": "ontem"}, **admin).status_code == 422
    assert client.get("/api/leads/receita/fatos",
                      HTTP_AUTHORIZATION="Bearer outro").status_code in (401, 403)


def test_backfill_de_compras_reconstroi_sem_duplicar(capsys):
    from django.core.management import call_command

    from apps.core.models import Lead, TimelineEvent

    oferta = quiz("crivo")
    quiz("cura")
    lead = Lead.objects.get(email=EMAIL)
    TimelineEvent.objects.create(lead=lead, event="pedido.criado", payload={
        "site_id": SITE, "order_id": "ped-9", "oportunidade_ref": str(oferta.id),
        "total_cents": 500, "customer": {"email": EMAIL},
    })
    TimelineEvent.objects.create(lead=lead, event="pagamento.aprovado", payload={
        "site_id": SITE, "order_id": "ped-9", "amount_cents": 500,
    })
    call_command("backfill_compras")
    call_command("backfill_compras")
    oferta.refresh_from_db()
    assert oferta.etapa == "ganha"
    compra = CompraDaOportunidade.objects.get()
    assert compra.aprovado_centavos == 500 and compra.oportunidade_id == oferta.id
    assert "Compras: 1; aprovadas: 1" in capsys.readouterr().out


def test_ate_com_data_simples_vale_ate_o_fim_do_dia(client, admin):
    from django.utils import timezone

    oferta = quiz("crivo")
    pedido("ped-1", oportunidade_ref=str(oferta.id))
    aprovado("ped-1")
    hoje = timezone.localdate().isoformat()
    sem_filtro = client.get("/api/leads/receita/fatos", **admin).json()
    assert sem_filtro["totais"]["compras_aprovadas"] == 1
    ate_hoje = client.get("/api/leads/receita/fatos", {"ate": hoje}, **admin).json()
    assert ate_hoje["totais"]["compras_aprovadas"] == 1
    so_hoje = client.get(
        "/api/leads/receita/fatos", {"desde": hoje, "ate": hoje}, **admin
    ).json()
    assert so_hoje["totais"]["compras_aprovadas"] == 1
    assert client.get(
        "/api/leads/receita/fatos", {"ate": "2026-13-45"}, **admin
    ).status_code == 422


def test_pagamento_com_email_de_outra_pessoa_nao_fecha_a_oferta_dela():
    maria_crivo = quiz("crivo")
    maria_cura = quiz("cura")
    joao_crivo = quiz("crivo", email="joao@gmail.com")
    pedido("ped-1")
    aprovado("ped-1", email="joao@gmail.com")
    _recarregar(maria_crivo, maria_cura, joao_crivo)
    assert not joao_crivo.encerrada and joao_crivo.etapa == "nova"
    assert not maria_crivo.encerrada and not maria_cura.encerrada
    compra = CompraDaOportunidade.objects.get()
    assert compra.lead.email == EMAIL and compra.oportunidade_id is None


def test_referencia_inexistente_nao_fecha_a_unica_oferta_aberta():
    crivo = quiz("crivo")
    pedido("ped-1", oportunidade_ref="lixo-qualquer", produto="outro")
    aprovado("ped-1")
    crivo.refresh_from_db()
    assert not crivo.encerrada and crivo.etapa == "nova"
    assert CompraDaOportunidade.objects.get().oportunidade_id is None


def test_aprovacao_antes_do_pedido_corrigida_pela_referencia_reabre_a_oferta_errada():
    from django.utils import timezone

    crivo = quiz("crivo")
    cura = quiz("cura")
    cura.desfecho_resultado = "perdida"
    cura.desfecho_motivo = "Sem interesse"
    cura.desfecho_encerrada_em = timezone.now()
    cura.etapa = "perdida"
    cura.save()

    aprovado("ped-1")  # chega antes do pedido, sem referência
    crivo.refresh_from_db()
    assert crivo.etapa == "ganha"

    pedido("ped-1", oportunidade_ref=str(cura.id))
    _recarregar(crivo, cura)
    assert cura.etapa == "ganha" and cura.encerrada
    assert crivo.etapa != "ganha" and not crivo.encerrada
    assert CompraDaOportunidade.objects.get().oportunidade_id == cura.id


# ---------------------------------------------------------------------------
# Sem oportunidade_ref/oferta_ref: casa por produto
# ---------------------------------------------------------------------------


def test_sem_referencia_o_produto_do_pedido_casa_com_a_oferta_indicada_pelo_quiz():
    crivo = quiz("crivo", context={"oferta_ref": "prod-crivo"})
    cura = quiz("cura", context={"oferta_ref": "prod-cura"})
    pedido("ped-1", produto="prod-cura")
    aprovado("ped-1")
    _recarregar(crivo, cura)
    assert cura.etapa == "ganha" and cura.encerrada
    assert crivo.etapa == "nova" and not crivo.encerrada
    assert CompraDaOportunidade.objects.get().oportunidade_id == cura.id


def test_sem_referencia_o_resultado_do_quiz_casa_com_o_produto_do_pedido():
    from django.utils import timezone

    from apps.core.models import Lead, QuizDoLead

    crivo = quiz("crivo")
    cura = quiz("cura")
    lead = Lead.objects.get(email=EMAIL, site_id=SITE)
    QuizDoLead.objects.create(
        lead=lead, quiz_slug="crivo", situacao="completo", resultado="Prod-Crivo",
        completado_em=timezone.now(),
    )
    QuizDoLead.objects.create(
        lead=lead, quiz_slug="cura", situacao="completo", resultado="prod-cura",
        completado_em=timezone.now(),
    )
    pedido("ped-1", produto="prod-crivo")
    aprovado("ped-1")
    _recarregar(crivo, cura)
    assert crivo.etapa == "ganha"
    assert cura.etapa == "nova"


def test_sem_referencia_produto_de_nenhuma_oferta_com_duas_abertas_nao_fecha_nada():
    from django.utils import timezone

    from apps.core.models import Lead, QuizDoLead

    crivo = quiz("crivo")
    cura = quiz("cura")
    lead = Lead.objects.get(email=EMAIL, site_id=SITE)
    for slug in ("crivo", "cura"):
        QuizDoLead.objects.create(
            lead=lead, quiz_slug=slug, situacao="completo",
            resultado=f"prod-{slug}", completado_em=timezone.now(),
        )
    pedido("ped-1", produto="prod-outro")
    aprovado("ped-1")
    _recarregar(crivo, cura)
    assert crivo.etapa == "nova" and cura.etapa == "nova"


def test_perfil_que_indica_o_produto_liga_a_unica_oferta_aberta():
    from django.utils import timezone

    from apps.core.models import Lead, PerfilDoLead

    crivo = quiz("crivo", context={"oferta_ref": "prod-crivo"})
    lead = Lead.objects.get(email=EMAIL, site_id=SITE)
    # sem indicação, um produto diferente do que a oferta conhece não a fecha
    pedido("ped-1", produto="prod-novo")
    aprovado("ped-1")
    crivo.refresh_from_db()
    assert not crivo.encerrada

    PerfilDoLead.objects.create(
        lead=lead, versao=1, analisado_em=timezone.now(),
        oferta_indicada={"oferta_ref": "prod-novo", "nome": "Novo"},
    )
    pedido("ped-2", produto="prod-novo")
    aprovado("ped-2")
    crivo.refresh_from_db()
    assert crivo.etapa == "ganha"
    assert CompraDaOportunidade.objects.get(pedido_id="ped-2").oportunidade_id == crivo.id


def test_recompra_de_produto_de_oferta_ganha_nao_fecha_a_outra_oferta_aberta():
    crivo = quiz("crivo")
    cura = quiz("cura")
    pedido("ped-1", oportunidade_ref=str(crivo.id), produto="prod-crivo")
    aprovado("ped-1")
    _recarregar(crivo, cura)
    assert crivo.etapa == "ganha" and cura.etapa == "nova"

    pedido("ped-2", produto="prod-crivo")
    aprovado("ped-2")
    _recarregar(crivo, cura)
    assert cura.etapa == "nova" and not cura.encerrada
    assert CompraDaOportunidade.objects.get(pedido_id="ped-2").oportunidade_id is None


def test_unica_oferta_aberta_ainda_vale_quando_o_produto_e_novo():
    crivo = quiz("crivo")
    pedido("ped-1", produto="prod-qualquer")
    aprovado("ped-1")
    crivo.refresh_from_db()
    assert crivo.etapa == "ganha"


# ---------------------------------------------------------------------------
# Falha e aprovação no mesmo instante: vale a ordem de gravação
# ---------------------------------------------------------------------------


def _fatos_no_mesmo_instante(*eventos):
    from django.utils import timezone

    from apps.core.models import Lead, TimelineEvent

    lead = Lead.objects.create(site_id=SITE, email=EMAIL)
    instante = timezone.now()
    dados = {"site_id": SITE, "order_id": "ped-7", "amount_cents": 990}
    for nome in eventos:
        evento = TimelineEvent.objects.create(lead=lead, event=nome, payload=dados)
        TimelineEvent.objects.filter(pk=evento.pk).update(occurred_at=instante)


def test_backfill_falha_gravada_antes_da_aprovacao_no_mesmo_instante_abre_recuperacao():
    from django.core.management import call_command

    _fatos_no_mesmo_instante("pagamento.recusado", "pagamento.aprovado")
    call_command("backfill_recuperacao")
    call_command("backfill_recuperacao")
    recuperacao = Oportunidade.objects.get(fonte_tipo="pagamento")
    assert recuperacao.etapa == "ganha"
    assert CompraDaOportunidade.objects.get().recuperada


def test_backfill_aprovacao_gravada_antes_da_falha_no_mesmo_instante_nao_abre_nada():
    from django.core.management import call_command

    _fatos_no_mesmo_instante("pagamento.aprovado", "pagamento.recusado")
    call_command("backfill_recuperacao")
    assert not Oportunidade.objects.filter(fonte_tipo="pagamento").exists()
