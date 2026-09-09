"""[INV-ENC-J11] Chamada aberta sem aceite não fica presa para sempre.

Lei: `DECISAO-fila-do-primeiro-dolar.md` §3.8 e §5. A passada seguinte do tique
escala a chamada aberta ao plantão quando o novo prazo histórico vence.
"""

from datetime import timedelta

from apps.encomendas import tique
from apps.encomendas.models import Encomenda, MudancaDeStatus, Parametro

SITE = "escola-a"


def prazo_da_chamada_aberta(agora):
    linha = Parametro.vigente_em(
        "horas_para_escalar_chamada_aberta", agora, site_id=SITE
    )
    return timedelta(hours=int(linha.valor))


def abrir_chamada_aberta(criar_encomenda, monkeypatch):
    encomenda = criar_encomenda()
    agora = encomenda.criada_em + timedelta(days=3)
    monkeypatch.setattr("django.utils.timezone.now", lambda: agora)
    tique.rodar(agora, site_id=SITE)
    encomenda.refresh_from_db()
    assert encomenda.status == Encomenda.Status.ABERTA
    return encomenda, agora


def test_chamada_aberta_sem_aceite_vai_ao_plantao_no_prazo(
    semeado, criar_encomenda, monkeypatch
):
    encomenda, aberta_em = abrir_chamada_aberta(criar_encomenda, monkeypatch)
    antes = aberta_em + prazo_da_chamada_aberta(aberta_em) - timedelta(minutes=1)

    assert tique.rodar(antes, site_id=SITE).projetos_ao_plantao == ()
    encomenda.refresh_from_db()
    assert encomenda.status == Encomenda.Status.ABERTA

    depois = aberta_em + prazo_da_chamada_aberta(aberta_em)
    resultado = tique.rodar(depois, site_id=SITE)

    encomenda.refresh_from_db()
    assert resultado.projetos_ao_plantao == (encomenda.pk,)
    assert encomenda.status == Encomenda.Status.PARA_RECLASSIFICAR
    historico = MudancaDeStatus.objects.get(
        encomenda=encomenda, para=Encomenda.Status.PARA_RECLASSIFICAR
    )
    assert historico.ator_id == ""
    assert historico.motivo == tique.MOTIVO_DA_CHAMADA_ABERTA_SEM_ACEITE


def test_prazo_da_chamada_aberta_e_historico_do_banco(
    semeado, criar_encomenda, monkeypatch
):
    encomenda, aberta_em = abrir_chamada_aberta(criar_encomenda, monkeypatch)
    Parametro.objects.create(
        site_id=SITE,
        chave="horas_para_escalar_chamada_aberta",
        valor="1",
        desde=aberta_em + timedelta(minutes=1),
        motivo="o plantao precisa receber chamadas abertas sem resposta",
        quem="dono",
    )

    resultado = tique.rodar(aberta_em + timedelta(hours=1), site_id=SITE)

    encomenda.refresh_from_db()
    assert resultado.projetos_ao_plantao == (encomenda.pk,)
    assert encomenda.status == Encomenda.Status.PARA_RECLASSIFICAR


def test_chamada_aberta_escalada_nao_volta_ao_plantao(
    semeado, criar_encomenda, monkeypatch
):
    encomenda, aberta_em = abrir_chamada_aberta(criar_encomenda, monkeypatch)
    depois = aberta_em + prazo_da_chamada_aberta(aberta_em)

    primeira = tique.rodar(depois, site_id=SITE)
    segunda = tique.rodar(depois, site_id=SITE)

    assert primeira.projetos_ao_plantao == (encomenda.pk,)
    assert segunda.projetos_ao_plantao == ()
