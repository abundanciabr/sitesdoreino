"""A leitura das faixas é contígua; fatos antigos ficam guardados."""

from datetime import date
from uuid import uuid4

import pytest
from django.http import HttpResponse

from apps.core.perfil import perfil_de
from apps.core.trilha_api import _projecao
from apps.gamificacao.jornada import registrar_conclusao, salvar, situacao
from apps.gamificacao.models import AnexoDaJornada, JornadaPessoal, RecebimentoDeclarado, RegistroDaJornada


pytestmark = pytest.mark.django_db
SITE, P = "site-sequencial", "aluna-sequencial"
INICIO = {
    "motivo": "ugc", "objetivo": "Criar uma peça", "compromisso": "Praticar esta semana",
    "confirmado_em": "2026-10-10T10:00:00-03:00", "sonho": "SONHO-PRIVADO-ALFA",
}


@pytest.fixture(autouse=True)
def site(monkeypatch):
    monkeypatch.setenv("SITE_ID", SITE)


def registro_legado(*, declaracoes=None, com_anexo=True, total=0, inicio=None):
    perfil_de(P, SITE)
    jornada = JornadaPessoal.objects.create(
        pessoa_id=P, site_id=SITE, meta_cents=10000,
        declaracoes=declaracoes or {"2": "antiga", "3": "antiga", "4": "antiga"},
        inicio=INICIO.copy() if inicio is None else inicio,
    )
    if com_anexo:
        AnexoDaJornada.objects.create(
            pessoa_id=P, site_id=SITE, passo=2, nome="obra.obj",
            conteudo=b"v 0 0 0\n", tamanho=8, sha256="legado",
            aprendi="NOTA-PRIVADA-ALFA",
        )
    if total:
        RecebimentoDeclarado.objects.create(
            pessoa_id=P, site_id=SITE, chave=uuid4(), origem="fora",
            estado="confirmado", valor_cents=total, valor_original_cents=total,
            recebido_em=date(2026, 10, 1),
        )
    return jornada


def declarar(ordem, estado="feito"):
    return salvar(P, SITE, {
        "acao": "declaracao", "passo": str(ordem), "estado": estado,
        "revisao": situacao(P, SITE)["revisao"],
    })


def ordem():
    return situacao(P, SITE)["atual"]["ordem"]


def test_legado_com_todos_os_fatos_e_renda_recomeca_branca_sem_perder_registros():
    from apps.gamificacao.faixas import situacao_das_faixas

    jornada = registro_legado(total=10000)
    anexo_id = AnexoDaJornada.objects.get().pk
    recebimento_id = RecebimentoDeclarado.objects.get().pk
    assert jornada.confirmacoes_sequenciais == {}
    assert ordem() == 1
    assert situacao_das_faixas(P, SITE)["atual"]["ordem"] == 1
    assert [p["alcancada"] for p in situacao(P, SITE)["lista"]] == [True] + [False] * 12
    jornada.refresh_from_db()
    assert set(jornada.declaracoes) == {"2", "3", "4"}
    assert jornada.inicio["sonho"] == "SONHO-PRIVADO-ALFA"
    assert AnexoDaJornada.objects.get(pk=anexo_id).aprendi == "NOTA-PRIVADA-ALFA"
    assert RecebimentoDeclarado.objects.get(pk=recebimento_id).valor_cents == 10000

    for passo in (2, 3, 4):
        declarar(passo)
        assert ordem() == passo if passo < 4 else ordem() == 13
        assert situacao_das_faixas(P, SITE)["atual"]["ordem"] == ordem()
    jornada.refresh_from_db()
    assert set(jornada.confirmacoes_sequenciais) == {"2", "3", "4"}
    assert AnexoDaJornada.objects.count() == RecebimentoDeclarado.objects.count() == 1


def test_sem_predecessora_ninguem_confirma_passo_3_ou_4():
    jornada = registro_legado(declaracoes={"3": "antiga", "4": "antiga"})
    for passo in (3, 4):
        with pytest.raises(ValueError):
            declarar(passo)
    jornada.refresh_from_db()
    assert jornada.confirmacoes_sequenciais == {}
    assert ordem() == 1

    declarar(2)
    assert ordem() == 2
    with pytest.raises(ValueError):
        declarar(4)
    assert ordem() == 2
    declarar(3)
    assert ordem() == 3
    declarar(4)
    assert ordem() == 4


def test_conclusao_automatica_preserva_fato_sem_confirmar_faixa_superior():
    jornada = registro_legado(declaracoes={"2": "antiga"}, total=10000)
    registrar_conclusao(P, SITE, 3)
    registrar_conclusao(P, SITE, 4)
    jornada.refresh_from_db()
    assert jornada.declaracoes.get("3") and jornada.declaracoes.get("4")
    assert jornada.confirmacoes_sequenciais == {}
    assert ordem() == 1
    declarar(2)
    assert ordem() == 2
    assert RegistroDaJornada.objects.filter(acao="conclusao").count() == 2
    registrar_conclusao(P, SITE, 3)
    registrar_conclusao(P, SITE, 4)
    assert ordem() == 2
    declarar(3)
    assert ordem() == 3
    declarar(4)
    assert ordem() == 13


def test_conclusao_automatica_nova_avanca_quando_predecessora_ja_vale():
    registro_legado(declaracoes={"2": "antiga"}, total=10000)
    declarar(2)
    registrar_conclusao(P, SITE, 3)
    assert ordem() == 3
    registrar_conclusao(P, SITE, 4)
    assert ordem() == 13
    assert set(JornadaPessoal.objects.get().confirmacoes_sequenciais) == {"2", "3", "4"}


def test_requisito_anterior_invalido_regrede_sem_apagar_fatos_ou_confirmacoes():
    jornada = registro_legado(total=10000)
    for passo in (2, 3, 4):
        declarar(passo)
    assert ordem() == 13
    inicio = dict(jornada.inicio)
    inicio["confirmado_em"] = None
    jornada.inicio = inicio
    jornada.save(update_fields=["inicio"])
    assert ordem() == 1
    jornada.refresh_from_db()
    assert set(jornada.confirmacoes_sequenciais) == {"2", "3", "4"}
    assert set(jornada.declaracoes) == {"2", "3", "4"}
    assert RecebimentoDeclarado.objects.count() == AnexoDaJornada.objects.count() == 1
    inicio["confirmado_em"] = "2026-10-10T11:00:00-03:00"
    jornada.inicio = inicio
    jornada.save(update_fields=["inicio"])
    assert ordem() == 13


def test_correcao_e_estorno_baixam_a_primeira_etapa_incompleta():
    jornada = registro_legado(total=10000)
    for passo in (2, 3, 4):
        declarar(passo)
    assert ordem() == 13
    recebimento = RecebimentoDeclarado.objects.get()
    recebimento.estado = "anulado"
    recebimento.save(update_fields=["estado"])
    assert ordem() == 4
    assert jornada.declaracoes == {"2": "antiga", "3": "antiga", "4": "antiga"}
    recebimento.estado = "confirmado"
    recebimento.save(update_fields=["estado"])
    assert ordem() == 13
    declarar(2, "corrigir")
    assert ordem() == 1
    jornada.refresh_from_db()
    assert "2" not in jornada.confirmacoes_sequenciais
    assert set(jornada.confirmacoes_sequenciais) == {"3", "4"}
    assert jornada.declaracoes.get("3") and jornada.declaracoes.get("4")
    assert RecebimentoDeclarado.objects.count() == AnexoDaJornada.objects.count() == 1


def test_api_do_aluno_reflete_mesma_ordem_sem_vazar_dados_privados():
    registro_legado(total=10000)
    resposta = _projecao(HttpResponse(), P, SITE)
    assert resposta.atual_ordem == ordem() == 1
    for privado in ("SONHO-PRIVADO-ALFA", "NOTA-PRIVADA-ALFA"):
        assert privado not in resposta.model_dump_json()
    declarar(2)
    resposta = _projecao(HttpResponse(), P, SITE)
    assert resposta.atual_ordem == ordem() == 2
    assert [p.alcancada for p in resposta.etapas[:4]] == [True, True, False, False]


def test_post_declaracao_reconfirma_legado_na_ordem(client, monkeypatch):
    monkeypatch.setattr("apps.core.inventario._sessao", lambda cookie: {"autenticado": True, "id": P})
    jornada = registro_legado()
    url = "/inventario/"

    def postar(passo):
        revisao = client.get(url, HTTP_COOKIE="meshcraft_sessao=A").json()["revisao"]
        return client.post(url, {"acao": "declaracao", "passo": str(passo),
                                 "estado": "feito", "revisao": revisao},
                           HTTP_COOKIE="meshcraft_sessao=A")

    assert client.get(url, HTTP_COOKIE="meshcraft_sessao=A").json()["atual_ordem"] == 1
    assert postar(2).status_code == 200
    assert ordem() == 2
    assert postar(4).status_code == 400
    assert ordem() == 2
    assert postar(3).status_code == 200
    assert ordem() == 3
    assert postar(4).status_code == 200
    assert ordem() == 4
    jornada.refresh_from_db()
    assert set(jornada.confirmacoes_sequenciais) == {"2", "3", "4"}
    assert set(jornada.declaracoes) == {"2", "3", "4"}
    assert AnexoDaJornada.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_migracao_recomeca_branca_sem_perder_legado_e_defaults_servem_codigo_antigo():
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor

    anterior = [("gamificacao", "0016_inicio_da_jornada")]
    atual = [("gamificacao", "0017_confirmacoes_sequenciais")]
    executor = MigrationExecutor(connection)
    try:
        executor.migrate(anterior)
        antigo = executor.loader.project_state(anterior).apps
        PessoaAntiga = antigo.get_model("gamificacao", "Pessoa")
        JornadaAntiga = antigo.get_model("gamificacao", "JornadaPessoal")
        pessoa = PessoaAntiga.objects.create(id_da_plataforma="aluna-migracao", email="aluna-migracao@example.test")
        jornada = JornadaAntiga.objects.create(
            pessoa=pessoa, site_id="site-migracao", meta_cents=10000,
            declaracoes={"2": "legado", "3": "legado", "4": "legado"},
            inicio={"motivo": "ugc", "objetivo": "Obra antiga", "sonho": "SONHO-ANTIGO"},
        )
        executor = MigrationExecutor(connection)
        executor.migrate(atual)
        nova = JornadaPessoal.objects.get(pk=jornada.pk)
        assert nova.confirmacoes_sequenciais == {}
        assert nova.declaracoes == {"2": "legado", "3": "legado", "4": "legado"}
        assert nova.inicio["sonho"] == "SONHO-ANTIGO"
        assert situacao("aluna-migracao", "site-migracao")["atual"]["ordem"] == 1

        # Modelo 0016 não conhece o novo campo; o banco fornece o default.
        outra = PessoaAntiga.objects.create(id_da_plataforma="aluna-rollback", email="aluna-rollback@example.test")
        criado = JornadaAntiga.objects.create(pessoa=outra, site_id="site-migracao", declaracoes={"3": "legado"})
        assert JornadaPessoal.objects.get(pk=criado.pk).confirmacoes_sequenciais == {}
    finally:
        MigrationExecutor(connection).migrate(atual)
