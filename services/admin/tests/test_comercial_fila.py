"""A fila comercial: quem espera resposta passa na frente, trabalhadores em
paralelo e os dois tempos da página dos agentes. Tudo simulado."""

from __future__ import annotations

import threading
import uuid
from datetime import timedelta

import pytest
import respx
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.agentes import executor
from apps.comercial import coordenador
from apps.comercial.models import TrabalhoComercial

from tests.test_comercial import DONO, IDENTIDADE, E, T, ambiente, _trabalho  # noqa: F401


def _conversa(n: int) -> dict:
    return {"chave_da_conversa": f"conversa:c{n}", "conversa_id": f"c{n}"}


def test_atendimento_passa_na_frente_das_analises_mais_antigas():
    antigas = [_trabalho(T.ANALISAR_LEAD, chave_da_conversa=f"lead:s:{i}") for i in range(3)]
    atender = _trabalho(T.ATENDER_MENSAGEM, **_conversa(1))
    assert coordenador.pegar_um("t1").pk == atender.pk
    # Sem atendimento esperando, as análises seguem a ordem de chegada.
    assert coordenador.pegar_um("t1").pk == antigas[0].pk


def test_ordem_de_prioridade_entre_os_tipos():
    resultados = _trabalho(T.ANALISAR_RESULTADOS, chave_da_conversa="resultados")
    analise = _trabalho(T.ANALISAR_LEAD, chave_da_conversa="lead:s:1")
    abordar = _trabalho(T.ABORDAR, chave_da_conversa="lead:s:2")
    pagamento = _trabalho(T.ACOMPANHAR_PAGAMENTO, chave_da_conversa="lead:s:3")
    atender = _trabalho(T.ATENDER_MENSAGEM, **_conversa(2))
    ordem = [coordenador.pegar_um("t").pk for _ in range(5)]
    assert ordem == [atender.pk, pagamento.pk, abordar.pk, analise.pk, resultados.pk]


def test_dois_atendimentos_da_mesma_conversa_nao_correm_juntos():
    primeiro = _trabalho(T.ATENDER_MENSAGEM, **_conversa(1))
    segundo = _trabalho(T.ATENDER_MENSAGEM, **_conversa(1))
    outra = _trabalho(T.ATENDER_MENSAGEM, **_conversa(2))
    a = coordenador.pegar_um("trabalhador-1")
    b = coordenador.pegar_um("trabalhador-2")
    assert {a.pk, b.pk} == {primeiro.pk, outra.pk}
    assert coordenador.pegar_um("trabalhador-3") is None  # o segundo da conversa 1 espera
    assert TrabalhoComercial.objects.get(pk=segundo.pk).estado == E.NA_FILA


@pytest.mark.parametrize("valor,esperado", [
    (None, 2), ("", 2), ("3", 3), ("1", 1), ("9", 4), ("0", 1), ("abc", 2),
])
def test_quantidade_de_trabalhadores_comerciais(monkeypatch, valor, esperado):
    if valor is None:
        monkeypatch.delenv("COMERCIAL_TRABALHADORES", raising=False)
    else:
        monkeypatch.setenv("COMERCIAL_TRABALHADORES", valor)
    assert executor.trabalhadores_comerciais() == esperado


def test_threads_comerciais_tem_nomes_distintos(monkeypatch):
    monkeypatch.setenv("COMERCIAL_TRABALHADORES", "3")
    indices = []
    parar = threading.Event()
    monkeypatch.setattr(executor, "rodar_comercial_para_sempre",
                        lambda parar_, indice=1: indices.append(indice))
    threads = executor._ligar_trabalhadores_comerciais(parar)
    for t in threads:
        t.join(timeout=5)
    assert sorted(indices) == [1, 2, 3]
    assert len({t.name for t in threads}) == 3


def _entrar():
    cliente = Client()
    cliente.defaults["HTTP_COOKIE"] = "meshcraft_sessao=qualquer-coisa-assinada"
    return cliente


@respx.mock
def test_pagina_dos_agentes_sem_trabalhos_diz_sem_dados():
    respx.get(f"{IDENTIDADE}/sessao/completa").respond(200, json={
        "autenticado": True, "id": "id-1", "nome_exibido": "Dono", "papel": None, "email": DONO})
    resposta = _entrar().get(reverse("crm_agentes"))
    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert "Espera média na fila (últimas 24h)" in html
    assert "Tempo até a resposta ao lead (últimas 24h)" in html
    assert html.count("ainda sem dados") == 2


@respx.mock
def test_pagina_dos_agentes_mostra_os_tempos_das_ultimas_24h():
    respx.get(f"{IDENTIDADE}/sessao/completa").respond(200, json={
        "autenticado": True, "id": "id-1", "nome_exibido": "Dono", "papel": None, "email": DONO})
    agora = timezone.now()
    trabalho = _trabalho(T.ATENDER_MENSAGEM, **_conversa(1))
    TrabalhoComercial.objects.filter(pk=trabalho.pk).update(
        criado_em=agora - timedelta(minutes=10), iniciado_em=agora - timedelta(minutes=8),
        terminado_em=agora - timedelta(minutes=5), estado=E.CONCLUIDO)
    antigo = _trabalho(T.ANALISAR_LEAD, chave_da_conversa=f"lead:antigo:{uuid.uuid4().hex}")
    TrabalhoComercial.objects.filter(pk=antigo.pk).update(
        criado_em=agora - timedelta(days=3), iniciado_em=agora - timedelta(days=3) + timedelta(hours=2))
    resposta = _entrar().get(reverse("crm_agentes"))
    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert "2 min" in html and "5 min" in html
    assert "ainda sem dados" not in html


def test_vinte_atendimentos_de_conversa_ocupada_nao_escondem_o_resto():
    agora = timezone.now()
    for n in range(20):
        _trabalho(T.ATENDER_MENSAGEM, **_conversa(n))
        ocupado = _trabalho(T.ATENDER_MENSAGEM, **_conversa(n))
        TrabalhoComercial.objects.filter(pk=ocupado.pk).update(
            estado=E.ENVIO_INCERTO, nao_antes_de=agora + timedelta(hours=1))
    # Os 20 atendimentos esperam as conversas, que estao com envio incerto.
    analise = _trabalho(T.ANALISAR_LEAD, chave_da_conversa="lead:s:livre")
    pegou = coordenador.pegar_um("t")
    assert pegou is not None and pegou.pk == analise.pk


@respx.mock
def test_espera_na_fila_nao_conta_pagamento_nem_resultados():
    respx.get(f"{IDENTIDADE}/sessao/completa").respond(200, json={
        "autenticado": True, "id": "id-1", "nome_exibido": "Dono", "papel": None, "email": DONO})
    agora = timezone.now()
    pagamento = _trabalho(T.ACOMPANHAR_PAGAMENTO, chave_da_conversa="lead:s:pg")
    TrabalhoComercial.objects.filter(pk=pagamento.pk).update(
        criado_em=agora - timedelta(hours=23), iniciado_em=agora - timedelta(minutes=1))
    analise = _trabalho(T.ANALISAR_LEAD, chave_da_conversa="lead:s:an")
    TrabalhoComercial.objects.filter(pk=analise.pk).update(
        criado_em=agora - timedelta(minutes=10), iniciado_em=agora - timedelta(minutes=7))
    html = _entrar().get(reverse("crm_agentes")).content.decode()
    assert "3 min" in html and "22 h" not in html and "23 h" not in html


def test_threads_comerciais_herdam_o_contexto_do_servico(monkeypatch):
    import contextvars

    marca = contextvars.ContextVar("marca_do_servico", default="nenhuma")
    visto = []
    monkeypatch.setenv("COMERCIAL_TRABALHADORES", "2")
    monkeypatch.setattr(executor, "rodar_comercial_para_sempre",
                        lambda parar_, indice=1: visto.append(marca.get()))
    token = marca.set("admin")
    try:
        threads = executor._ligar_trabalhadores_comerciais(threading.Event())
        for t in threads:
            t.join(timeout=5)
    finally:
        marca.reset(token)
    assert visto == ["admin", "admin"]

