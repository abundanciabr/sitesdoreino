"""As 13 faixas: critérios, limites, idempotência, aviso, estorno e isolamento."""

import uuid

import pytest
from django.test import Client

from apps.eventos.management.commands.consume_eventos import STREAMS, processar_envelope
from apps.gamificacao.faixas import FAIXAS, situacao_das_faixas, total_real_cents
from apps.gamificacao.handlers import HANDLERS
from apps.gamificacao.models import (
    FaixaDoAluno,
    HistoricoDaFaixa,
    OutboxEvent,
    PerfilJogador,
    Pessoa,
    RendimentoRealLivro,
)
from apps.eventos.models import EventoProcessado

pytestmark = pytest.mark.django_db

SITE = "escola"
P = "aluno-1"
AGORA = "2026-10-08T12:00:00+00:00"


def env(event, pessoa=P, site=SITE, historico=False, event_id=None, **extra):
    data = {"site_id": site, "pessoa_id": pessoa, "ocorrido_em": AGORA, "historico": historico, **extra}
    return {
        "event_id": event_id or str(uuid.uuid4()),
        "event": event,
        "version": 1,
        "occurred_at": AGORA,
        "ator_id": pessoa,
        "data": data,
    }


def entregar(envelope):
    processar_envelope(envelope, HANDLERS)


def paga(valor, rid=None, **kw):
    entregar(env("encomendas.rendimento-real-confirmado", rendimento_id=rid or str(uuid.uuid4()),
                 valor_cents=valor, **kw))


def estorna(valor, rid, **kw):
    entregar(env("encomendas.rendimento-real-revertido", rendimento_id=rid, valor_cents=valor, **kw))


def atual(pessoa=P, site=SITE):
    return situacao_das_faixas(pessoa, site)["atual"]["ordem"]


@pytest.fixture(autouse=True)
def _aviso_ligado(monkeypatch):
    monkeypatch.setattr("apps.gamificacao.faixas.AVISAR_O_ALUNO", True)


def test_aluno_nao_e_avisado_enquanto_faixas_sao_so_do_admin(monkeypatch):
    monkeypatch.setattr("apps.gamificacao.faixas.AVISAR_O_ALUNO", False)
    paga(6000)
    assert atual() == 7
    assert cartas().count() == 0
    assert not PerfilJogador.objects.filter(pessoa_id=P).exists()


def cartas():
    return OutboxEvent.objects.filter(event="notificacao.devida")


def test_sem_fatos_e_branca_e_nada_gravado():
    s = situacao_das_faixas(P, SITE)
    assert s["atual"]["ordem"] == 1 and s["atual"]["nome"] == "Branca"
    assert len(s["faixas"]) == 13 and s["total_real_cents"] == 0
    assert s["proxima"]["ordem"] == 2 and s["proxima"]["dinheiro"] is None
    assert FaixaDoAluno.objects.count() == 0


def test_contrato_das_13_faixas():
    assert [f["ordem"] for f in FAIXAS] == list(range(1, 14))
    assert [f["nome"] for f in FAIXAS][:4] == ["Branca", "Branca e amarela", "Amarela", "Laranja"]
    assert [f["meta_cents"] for f in FAIXAS][4:] == [1, 2500, 5000, 10000, 20000, 50000, 75000, 100000, 200000]


@pytest.mark.parametrize("event,campo,ordem", [
    ("cursos.item-criado", "item_id", 2),
    ("encomendas.sandbox-trabalho-criado", "trabalho_id", 3),
    ("encomendas.fila-trabalho-aceito", "pedido_id", 4),
])
def test_cada_fato_de_origem(event, campo, ordem):
    entregar(env(event, **{campo: "x1"}))
    s = situacao_das_faixas(P, SITE)
    assert s["atual"]["ordem"] == ordem
    assert FaixaDoAluno.objects.filter(pessoa_id=P, ordem=1).exists()  # Branca gravada
    assert s["faixas"][ordem - 1]["alcancada"] and s["atual"]["origem"]
    # segundo fato do mesmo tipo não muda nada
    n = HistoricoDaFaixa.objects.count()
    entregar(env(event, **{campo: "x2"}))
    assert HistoricoDaFaixa.objects.count() == n


LIMITES = [(5, 1), (6, 2500), (7, 5000), (8, 10000), (9, 20000), (10, 50000),
           (11, 75000), (12, 100000), (13, 200000)]


@pytest.mark.parametrize("ordem,meta", LIMITES)
def test_limites_um_centavo_abaixo_e_no_limite(ordem, meta):
    if meta > 1:
        paga(meta - 1)
        assert atual() == ordem - 1
        paga(1)
    else:
        paga(meta)
    assert atual() == ordem
    assert total_real_cents(P, SITE) == meta


def test_acumulado_em_varias_vendas():
    for _ in range(5):
        paga(1000)
    assert total_real_cents(P, SITE) == 5000
    assert atual() == 7
    s = situacao_das_faixas(P, SITE)
    assert s["proxima"]["ordem"] == 8
    assert s["proxima"]["dinheiro"] == {"total_cents": 5000, "meta_cents": 10000,
                                         "falta_cents": 5000, "fracao_pct": 50}
    assert "R$ 50,00" in s["proxima"]["falta_texto"]


def test_maior_faixa_sem_exigir_as_anteriores():
    paga(200000)
    s = situacao_das_faixas(P, SITE)
    assert s["atual"]["ordem"] == 13 and s["proxima"] is None
    assert [f["alcancada"] for f in s["faixas"]][1:4] == [False, False, False]
    assert all(f["alcancada"] for f in s["faixas"][4:])


def test_atual_e_a_maior_ordem_mesmo_com_laranja_depois():
    paga(100)
    entregar(env("encomendas.fila-trabalho-aceito", pedido_id="p"))
    assert atual() == 5


def test_reentrega_do_mesmo_evento_nao_duplica():
    e = env("encomendas.rendimento-real-confirmado", rendimento_id="r1", valor_cents=3000)
    entregar(e)
    entregar(e)
    assert total_real_cents(P, SITE) == 3000
    assert RendimentoRealLivro.objects.count() == 1


def test_mesmo_event_id_sem_dedupe_do_consumidor_nao_duplica():
    e = env("encomendas.rendimento-real-confirmado", rendimento_id="r1", valor_cents=3000)
    HANDLERS[e["event"]](e)
    HANDLERS[e["event"]](e)  # ignora o EventoProcessado de propósito
    assert RendimentoRealLivro.objects.count() == 1
    assert HistoricoDaFaixa.objects.filter(ordem=6).count() == 1
    assert cartas().count() == 1


def test_historico_true_nao_avisa_e_ao_vivo_avisa():
    paga(3000, historico=True)
    entregar(env("cursos.item-criado", item_id="i", historico=True))
    assert atual() == 6
    assert cartas().count() == 0
    assert not PerfilJogador.objects.filter(pessoa_id=P).exists()
    assert HistoricoDaFaixa.objects.filter(historico=True).count() >= 3

    paga(3000, pessoa="aluno-2")
    carta = cartas().get()
    assert carta.payload["assunto"] == "gamificacao.conquista-concedida"
    assert carta.payload["destinatario_id"] == "aluno-2"
    assert carta.payload["parametros"]["conquista_slug"] == "faixa-verde-e-azul"
    perfil = PerfilJogador.objects.get(pessoa_id="aluno-2")
    assert {"tipo": "conquista-concedida", "referencia": "faixa-verde-e-azul"} in perfil.celebracoes_pendentes


def test_aviso_so_da_faixa_mais_alta_cruzada():
    paga(6000)  # cruza 5, 6 e 7 de uma vez
    assert cartas().count() == 1
    assert cartas().get().payload["parametros"]["conquista_slug"] == "faixa-azul"


def test_estorno_reverte_e_reconfirmacao_restaura_na_mesma_linha():
    paga(3000, rid="r1")
    linha = FaixaDoAluno.objects.get(pessoa_id=P, ordem=6)
    assert linha.estado == "alcancada"
    estorna(3000, "r1")
    linha.refresh_from_db()
    assert linha.estado == "revertida"
    assert atual() == 1
    s = situacao_das_faixas(P, SITE)
    assert s["faixas"][5]["estado"] == "revertida" and not s["faixas"][5]["alcancada"]
    cartas_antes = cartas().count()
    paga(3000, rid="r1")  # reconfirmação com outro event_id
    linha2 = FaixaDoAluno.objects.get(pessoa_id=P, ordem=6)
    assert linha2.pk == linha.pk and linha2.estado == "alcancada"
    assert FaixaDoAluno.objects.filter(pessoa_id=P, ordem=6).count() == 1
    estados = list(HistoricoDaFaixa.objects.filter(pessoa_id=P, ordem=6).values_list("estado_novo", flat=True))
    assert estados == ["alcancada", "revertida", "alcancada"]
    assert cartas().count() == cartas_antes  # restaurar não comemora de novo


def test_estorno_parcial_derruba_so_o_que_cai():
    paga(2000, rid="a")
    paga(500, rid="b")
    assert atual() == 6
    estorna(500, "b")
    assert atual() == 5
    assert FaixaDoAluno.objects.get(pessoa_id=P, ordem=5).estado == "alcancada"


def test_estorno_nunca_deixa_total_negativo():
    estorna(500, "x")
    assert total_real_cents(P, SITE) == 0
    assert atual() == 1


def test_separacao_entre_pessoas_e_entre_sites():
    paga(5000)
    assert atual("outra") == 1
    assert atual(P, "outra-escola") == 1
    paga(100, site="outra-escola")
    assert atual(P, "outra-escola") == 5
    assert atual() == 7
    assert total_real_cents(P, "outra-escola") == 100


def test_xp_e_cristais_intactos():
    pessoa = Pessoa.objects.create(id_da_plataforma=P, email="a@example.invalid")
    PerfilJogador.objects.create(pessoa=pessoa, site_id=SITE, xp_total=120, nivel=1, cristais_saldo=7)
    paga(200000)
    entregar(env("cursos.item-criado", item_id="i"))
    perfil = PerfilJogador.objects.get(pessoa_id=P, site_id=SITE)
    assert (perfil.xp_total, perfil.nivel, perfil.cristais_saldo) == (120, 1, 7)


def test_envelope_incompleto_nao_quebra_nem_grava():
    entregar({"event_id": str(uuid.uuid4()), "event": "cursos.item-criado", "data": {"pessoa_id": P}})
    entregar(env("encomendas.rendimento-real-confirmado", rendimento_id="r", valor_cents=0))
    assert FaixaDoAluno.objects.count() == 0 and RendimentoRealLivro.objects.count() == 0


def test_streams_e_handlers_registrados():
    for ev in ("cursos.item-criado", "encomendas.sandbox-trabalho-criado", "encomendas.fila-trabalho-aceito",
               "encomendas.rendimento-real-confirmado", "encomendas.rendimento-real-revertido"):
        assert ev in HANDLERS and f"eventos.{ev}" in STREAMS


def test_grupo_nasce_em_zero_para_todos_os_streams():
    import inspect
    from apps.eventos.management.commands import consume_eventos

    assert 'id="0"' in inspect.getsource(consume_eventos.Command.handle)


def test_endpoint_interno_faixa_do_aluno(settings, monkeypatch):
    settings.TOKENS_ACEITOS = {"tok"}
    monkeypatch.setattr("apps.core.api.site_atual", lambda: SITE)
    paga(5000)
    c = Client()
    assert c.get("/api/gamificacao/faixa-do-aluno", {"pessoa_id": P}).status_code == 401
    r = c.get("/api/gamificacao/faixa-do-aluno", {"pessoa_id": P}, HTTP_AUTHORIZATION="Bearer tok")
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["pessoa_id"] == P and corpo["site_id"] == SITE
    assert corpo["atual"]["ordem"] == 7 and corpo["atual"]["nome"] == "Azul"
    assert corpo["alcancadas"] == 4  # Branca + 5, 6, 7
    assert set(corpo["atual"]) == {"ordem", "nome", "cores", "conquista", "alcancada_em"}
    r = c.get("/api/gamificacao/faixa-do-aluno", {"pessoa_id": "ninguem"}, HTTP_AUTHORIZATION="Bearer tok")
    assert r.json()["atual"]["ordem"] == 1 and r.json()["alcancadas"] == 1


def test_eventoprocessado_dedupe_continua():
    e = env("cursos.item-criado", item_id="i")
    entregar(e)
    assert EventoProcessado.objects.filter(event_id=e["event_id"]).count() == 1


def test_reversao_que_chega_antes_da_confirmacao_anula_a_confirmacao():
    estorna(5000, "r9")  # streams separados: a reversão pode ser lida primeiro
    assert RendimentoRealLivro.objects.filter(rendimento_id="r9", valor_cents=-5000).count() == 1
    paga(5000, rid="r9")
    assert total_real_cents(P, SITE) == 0
    assert atual() == 1
    assert not FaixaDoAluno.objects.filter(pessoa_id=P, ordem__gte=5).exists()


def test_reversao_em_excesso_nao_abate_outro_rendimento():
    paga(3000, rid="a")
    estorna(9000, "b")  # b nunca foi confirmado
    assert total_real_cents(P, SITE) == 3000


def test_confirmacao_do_ciclo_novo_antes_da_reversao_velha_nao_avisa_falso():
    paga(2800, rid="base")
    paga(1500, rid="troca", ciclo=1)
    antes = cartas().count()
    paga(2000, rid="troca", ciclo=2)  # chega antes da reversão do ciclo 1
    assert total_real_cents(P, SITE) == 4800
    estorna(1500, "troca", ciclo=1)
    assert total_real_cents(P, SITE) == 4800
    assert cartas().count() == antes
    assert not FaixaDoAluno.objects.filter(pessoa_id=P, ordem__gt=atual()).exists()
