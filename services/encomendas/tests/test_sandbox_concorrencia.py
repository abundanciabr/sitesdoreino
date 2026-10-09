"""Disputas reais em conexões PostgreSQL separadas."""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier

import pytest
from django.db import close_old_connections, connection
from django.test import TransactionTestCase

from apps.encomendas import sandbox
from apps.encomendas.models import EntregaSandbox, MovimentoMeshcoin, ParticipacaoSandbox


@pytest.fixture
def limpeza_transacional():
    """O banco de teste exige TRUNCATE; o legado proíbe TRUNCATE por gatilho.

    O gatilho só é suspenso durante a limpeza do teste e restaurado no mesmo
    método, para que os testes seguintes continuem medindo a proteção real.
    """
    original = TransactionTestCase._fixture_teardown

    def limpar(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "ALTER TABLE encomendas_parametro DISABLE TRIGGER encomendas_parametro_sem_truncate"
            )
            cursor.execute(
                "ALTER TABLE encomendas_mudancadestatus DISABLE TRIGGER encomendas_historico_sem_truncate"
            )
        try:
            return original(self)
        finally:
            with connection.cursor() as cursor:
                cursor.execute(
                    "ALTER TABLE encomendas_parametro ENABLE TRIGGER encomendas_parametro_sem_truncate"
                )
                cursor.execute(
                    "ALTER TABLE encomendas_mudancadestatus ENABLE TRIGGER encomendas_historico_sem_truncate"
                )
            TransactionTestCase._fixture_teardown = original

    TransactionTestCase._fixture_teardown = limpar


pytestmark = pytest.mark.usefixtures("limpeza_transacional")

def _disputar(funcoes):
    inicio = Barrier(len(funcoes))

    def executar(funcao):
        close_old_connections()
        try:
            inicio.wait(timeout=10)
            try:
                return ("ok", funcao())
            except sandbox.ErroSandbox as erro:
                return ("recusado", str(erro))
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=len(funcoes)) as pool:
        return list(pool.map(executar, funcoes))


def _projeto(indice=0):
    projeto = sandbox.semear_projetos(site_id="escola-a")[indice]
    projeto.prazo_dias = 2
    projeto.ajustes_previstos = 1
    projeto.recompensa = Decimal("5.00")
    projeto.save(update_fields=["prazo_dias", "ajustes_previstos", "recompensa"])
    return projeto


@pytest.mark.django_db(transaction=True)
def test_aceites_simultaneos_em_projetos_diferentes_nao_duplicam_vaga():
    primeiro, segundo = _projeto(0), _projeto(1)
    resultados = _disputar([
        lambda: sandbox.aceitar(site_id="escola-a", pessoa_id="ana", projeto_id=primeiro.pk),
        lambda: sandbox.aceitar(site_id="escola-a", pessoa_id="ana", projeto_id=segundo.pk),
    ])
    assert sorted(tipo for tipo, _ in resultados) == ["ok", "recusado"]
    assert ParticipacaoSandbox.objects.filter(site_id="escola-a", pessoa_id="ana").count() == 1


@pytest.mark.django_db(transaction=True)
def test_entregas_simultaneas_criam_uma_versao():
    p = sandbox.aceitar(site_id="escola-a", pessoa_id="ana", projeto_id=_projeto().pk)
    resultados = _disputar([
        lambda i=i: sandbox.entregar(site_id="escola-a", participacao_id=p.pk, pessoa_id="ana",
            arquivos=[dict(nome=f"{i}.png", chave=f"sb/{i}.png", sha256=f"{i}" * 64,
                          tamanho=1, mime="image/png")]) for i in ("a", "b")
    ])
    assert sorted(tipo for tipo, _ in resultados) == ["ok", "recusado"]
    assert list(EntregaSandbox.objects.filter(participacao=p).values_list("versao", flat=True)) == [1]


@pytest.mark.django_db(transaction=True)
def test_aprovacoes_simultaneas_creditam_uma_vez():
    p = sandbox.aceitar(site_id="escola-a", pessoa_id="ana", projeto_id=_projeto().pk)
    sandbox.entregar(site_id="escola-a", participacao_id=p.pk, pessoa_id="ana",
        arquivos=[dict(nome="a.png", chave="sb/a.png", sha256="a" * 64, tamanho=1, mime="image/png")])
    resultados = _disputar([
        lambda: sandbox.aprovar(site_id="escola-a", participacao_id=p.pk, aprovador_id="equipe-1"),
        lambda: sandbox.aprovar(site_id="escola-a", participacao_id=p.pk, aprovador_id="equipe-2"),
    ])
    assert [tipo for tipo, _ in resultados] == ["ok", "ok"]
    from apps.encomendas.models import OutboxMarketplace
    assert OutboxMarketplace.objects.filter(event="encomendas.sandbox-trabalho-concluido").count() == 1
    assert MovimentoMeshcoin.objects.filter(participacao=p).count() == 0
    assert sandbox.saldo(site_id="escola-a", pessoa_id="ana") == 0
