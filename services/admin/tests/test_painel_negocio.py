"""A tela distingue fatos reais de ausência e de testes."""

import datetime as dt

import pytest
from django.template.loader import get_template

from apps.core.models import Tarefa
from apps.core.painel_negocio import _alunos, _funil, _pagamentos, _trabalho, atualizar_explicacoes


HOJE = dt.date(2026, 10, 6)


class Compras:
    def __init__(self, paginas):
        self.paginas = paginas
        self.pedidas = []

    def compras_pagina(self, site_id, pagina):
        self.pedidas.append(pagina)
        return self.paginas.get(pagina)


def _compra(**campos):
    return {**{"estado": "approved", "data": "2026-10-04T10:00:00-03:00",
               "valor_centavos": 10000, "estorno": ""}, **campos}


def test_receita_sem_ambiente_nao_inventa_valor():
    cliente = Compras({1: {"pagina": 1, "paginas": 1, "mais": False,
                           "total": 1, "compras": [_compra()]}})
    resultado = _pagamentos("site", HOJE, cliente)
    assert resultado["estado"] == "indisponivel"
    assert resultado["valor"] is None
    assert "ambiente" in resultado["motivo"]


def test_receita_paginada_exclui_sandbox_e_estorno():
    p1 = {"pagina": 1, "paginas": 2, "mais": True, "total": 4,
          "compras": [_compra(ambiente="sandbox"), _compra(ambiente="producao")]}
    p2 = {"pagina": 2, "paginas": 2, "mais": False, "total": 4,
          "compras": [_compra(ambiente="producao", estorno="confirmado"),
                       _compra(ambiente="producao", valor_centavos=2500)]}
    cliente = Compras({1: p1, 2: p2})
    resultado = _pagamentos("site", HOJE, cliente)
    assert cliente.pedidas == [1, 2]
    assert resultado["valor"] == 12500
    assert resultado["reais"] == "R$ 125,00"


def test_pagina_que_falha_nao_vira_total_parcial():
    cliente = Compras({1: {"pagina": 1, "paginas": 2, "mais": True,
                           "total": 2, "compras": [_compra(ambiente="producao")]}})
    assert _pagamentos("site", HOJE, cliente)["estado"] == "indisponivel"


def test_zero_sem_compras_e_distinto_de_falha():
    cliente = Compras({1: {"pagina": 1, "paginas": 1, "mais": False,
                           "total": 0, "compras": []}})
    assert _pagamentos("site", HOJE, cliente)["estado"] == "zero"
    assert _pagamentos("site", HOJE, Compras({}))["estado"] == "indisponivel"


class Medicao:
    OK = "ok"

    def __init__(self, coleta):
        self.coleta = coleta

    def funil(self, desde, ate, site_id):
        return "ok", {"coleta": {"primeiro": self.coleta},
                      "passos": {"pagina_vista": 0, "cta_checkout": 0, "pedido_pago": 0}}


def test_funil_distingue_sem_evento_de_zero_medido():
    assert _funil("site", HOJE, 7, Medicao(None))["estado"] == "sem_dados"
    assert _funil("site", HOJE, 7, Medicao("2026-10-01"))["estado"] == "medido"


def test_alunos_inclui_externos_sem_chamar_receita():
    class Alunos:
        def alunos(self):
            return [{"status": "ativa", "origem": "liberado"},
                    {"status": "ativa", "origem": "comprou"}]
    resultado = _alunos(Alunos())
    assert resultado["valor"] == 2
    assert "externas" in resultado["limite"]


def test_alunos_do_site_sem_somar_outras_escolas():
    class Alunos:
        def alunos(self):
            return [{"status": "ativa", "site_id": "site-a"},
                    {"status": "ativa", "site_id": "site-b"}]
    resultado = _alunos(Alunos(), site_id="site-a")
    assert resultado["estado"] == "medido"
    assert resultado["valor"] == 1
    assert resultado["escopo"] == "site"


def test_alunos_parcialmente_sem_site_nao_inventa_recorte():
    class Alunos:
        def alunos(self):
            return [{"status": "ativa", "site_id": "site-a"}, {"status": "ativa"}]
    assert _alunos(Alunos(), site_id="site-a")["estado"] == "indisponivel"


@pytest.mark.django_db
def test_tarefa_sem_objetivo_aparece_nas_prioridades():
    Tarefa.objects.create(titulo="Resolver matrícula", situacao=Tarefa.Situacao.BLOQUEADA)
    grupos = _trabalho(HOJE)
    sem_objetivo = next(g for g in grupos if g["id"] is None)
    assert sem_objetivo["abertas"] == 1
    assert sem_objetivo["prioridade"] == "Atenção agora"
    assert sem_objetivo["tarefas"][0]["titulo"] == "Resolver matrícula"


def test_explicacao_e_projecao_sem_mudar_cartao():
    cartao = {"nome": "margem-mensal", "sem_fonte_porque": "checkout congelado"}
    par = {"fonte": None, "sem_fonte_porque": "não guarda acesso"}
    contexto = {"doze": [{"nome": "margem-mensal", "veredito": "sem-fonte", "cartao": cartao}],
                "caminho_da_venda": [], "par": par}
    novo = atualizar_explicacoes(contexto)
    assert "Hotmart" in novo["doze"][0]["cartao"]["sem_fonte_porque"]
    assert cartao["sem_fonte_porque"] == "checkout congelado"
    assert "Hotmart" in novo["par"]["sem_fonte_porque"]
    assert par["sem_fonte_porque"] == "não guarda acesso"


def test_fragmento_compila():
    assert get_template("admin/_painel_negocio.html")
