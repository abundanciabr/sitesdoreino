from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.test import RequestFactory

from apps.agentes import executor, super_equipe
from apps.agentes.models import Consumo, Entrega, Execucao
from apps.agentes.views_super_equipe import super_equipe as pagina, super_equipe_trabalho
from apps.core.models import MembroDaEquipe


@pytest.mark.django_db
def test_pedido_deduplicado_e_analise_compartilhada():
    membro = MembroDaEquipe.objects.create(nome="Responsável")
    primeiro, criado = super_equipe.pedir_trabalho(
        membro, site_id="site-1", host="meshcraft.top", pedido="Avalie desempenho e confiança",
        especialidades=["desempenho", "confiabilidade"], chave="mesmo-envio")
    segundo, recriado = super_equipe.pedir_trabalho(
        membro, site_id="site-1", host="meshcraft.top", pedido="Avalie desempenho e confiança",
        especialidades=["desempenho", "confiabilidade"], chave="mesmo-envio")
    assert criado and not recriado and primeiro.pk == segundo.pk
    assert primeiro.tipo == Execucao.Tipo.SUPER_EQUIPE
    assert primeiro.origem == "super_equipe"

    fontes = {"consultado_em": "2026-10-06T12:00:00-03:00", "negocio": {
        "financeiro": {"estado": "medido", "valor": 1},
        "alunos": {"estado": "zero", "valor": 0}, "cursos": {"estado": "medido", "valor": 2}},
        "robos_ia": {"estado": "medido"},
        "experimentos": {"estado": "medido", "itens": []},
        "paginas_publicas": {"itens": [{"estado": "medido", "http": 200}]}}
    vistos = []

    def responder(**kwargs):
        vistos.append(kwargs)
        consumo = Consumo.objects.create(execucao=kwargs["execucao"], robo=kwargs["robo"],
                                         modelo="gpt-6-sol", origem="super_equipe",
                                         tokens_entrada=100, tokens_saida=50,
                                         custo_estimado_usd=Decimal("0.001"))
        return SimpleNamespace(completa=True, texto=f"Análise {len(vistos)}", id=f"r{len(vistos)}",
                               consumo=consumo)

    with patch.object(super_equipe, "coletar_fontes", return_value=fontes), \
         patch.object(super_equipe.modelo, "conexao", return_value=SimpleNamespace(modelo_forte="gpt-6-sol")), \
         patch.object(super_equipe.modelo, "responder", side_effect=responder):
        executor.rodar_uma("teste-super-equipe")
    primeiro.refresh_from_db()
    assert primeiro.situacao == Execucao.Situacao.CONCLUIDA
    assert primeiro.modelo == "gpt-6-sol"
    assert len(vistos) == 2
    assert "Análise 1" in vistos[1]["itens"][0]["content"]
    assert Entrega.objects.get(execucao=primeiro).parcial is False
    assert primeiro.consumos.count() == 2


@pytest.mark.django_db
def test_fonte_falha_permanece_parcial_e_acesso_da_equipe_recusado():
    membro = MembroDaEquipe.objects.create(nome="Responsável")
    trabalho, _ = super_equipe.pedir_trabalho(
        membro, site_id="site-1", host="meshcraft.top", pedido="Examine a fonte",
        especialidades=["arquitetura"], chave="parcial")
    fontes = {"consultado_em": "2026-10-06", "negocio": {"estado": "indisponivel"},
              "experimentos": {"estado": "indisponivel"}, "paginas_publicas": {"itens": []}}

    def responder(**kwargs):
        consumo = Consumo.objects.create(execucao=kwargs["execucao"], modelo="gpt-6-sol",
                                         custo_estimado_usd=Decimal("0.001"))
        return SimpleNamespace(completa=True, texto="Fonte não respondeu.", id="r1", consumo=consumo)

    with patch.object(super_equipe, "coletar_fontes", return_value=fontes), \
         patch.object(super_equipe.modelo, "conexao", return_value=SimpleNamespace(modelo_forte="gpt-6-sol")), \
         patch.object(super_equipe.modelo, "responder", side_effect=responder):
        executor.rodar_uma("teste-super-equipe-parcial")
    trabalho.refresh_from_db()
    assert trabalho.situacao == Execucao.Situacao.AGUARDANDO_INFORMACAO
    entrega = Entrega.objects.get(execucao=trabalho)
    assert entrega.parcial and entrega.pendencias
    request = RequestFactory().get("/admin/super-equipe/")
    request.admin = {"equipe_apenas": True}
    assert pagina(request).status_code == 403


def test_redacao_e_host():
    assert "123.456.789-09" not in super_equipe._sem_dados_pessoais("123.456.789-09")
    assert "ana@example.com" not in super_equipe._sem_dados_pessoais("ana@example.com")
    with pytest.raises(ValueError):
        super_equipe._host_proprio("example.com")


@pytest.mark.parametrize("status", [301, 302, 403, 404, 500, None])
def test_falha_publica_aponta_pagina_e_status(status):
    fontes = {"experimentos": {"estado": "medido"}, "robos_ia": {"estado": "medido"},
              "paginas_publicas": {"itens": [{"estado": "medido", "http": status,
                                               "url": "https://meshcraft.top/"}]}}
    faltas = super_equipe._pendencias(fontes)
    assert len(faltas) == 1
    assert "https://meshcraft.top/" in faltas[0]
    assert (f"HTTP {status}" if status else "sem resposta") in faltas[0]


@pytest.mark.parametrize("fonte", [{}, {"estado": "indisponivel"}])
def test_fonte_de_ia_ausente_nao_pode_concluir(fonte):
    fontes = {"experimentos": {"estado": "medido"}, "robos_ia": fonte,
              "paginas_publicas": {"itens": [{"estado": "medido", "http": 200}]}}
    assert super_equipe._pendencias(fontes) == ["Robôs de IA: fonte indisponível ou não consultada."]


@pytest.mark.django_db
def test_fotografia_consulta_fontes_e_preserva_falha():
    class Catalogo:
        OK = "ok"

        def experimentos_da_pagina(self, site_id, slug):
            assert site_id == "site-1"
            return self.OK, [{"id": "exp-1", "estado": "ativo"}]

    painel = {"negocio": {
        "financeiro": {"estado": "indisponivel", "valor": None},
        "funis": [{"estado": "zero", "valor": 0}],
        "alunos": {"estado": "medido", "valor": 2},
        "cursos": {"estado": "medido", "valor": 1},
        "objetivos": [{"id": 1, "abertas": 3, "bloqueadas": 1, "atrasadas": 0,
                       "responsaveis": ["Nome privado"]}],
    }}
    with patch.object(super_equipe, "montar_painel_negocio", return_value=painel), \
         patch.object(super_equipe, "CatalogoClient", return_value=Catalogo()), \
         patch.object(super_equipe, "calcular", return_value={"estado": "resultado", "veredito": "coletando"}), \
         patch.object(super_equipe, "_probes", return_value={"itens": [{"estado": "medido", "http": 200}]}):
        fontes = super_equipe.coletar_fontes("site-1", "meshcraft.top")
    assert fontes["negocio"]["financeiro"]["estado"] == "indisponivel"
    assert fontes["negocio"]["trabalho"]["tarefas_abertas"] == 3
    assert "Nome privado" not in str(fontes)
    assert fontes["experimentos"]["itens"][0]["veredito"] == "coletando"
    assert super_equipe._pendencias(fontes)


@pytest.mark.django_db
def test_paginas_do_admin_mostram_trabalho_e_entrega():
    membro = MembroDaEquipe.objects.create(nome="Responsável")
    trabalho, _ = super_equipe.pedir_trabalho(
        membro, site_id="site-1", host="meshcraft.top", pedido="Verifique o andamento",
        especialidades=["arquitetura"], chave="tela")
    Entrega.objects.create(robo=trabalho.robo, execucao=trabalho, tipo="super_equipe",
                           titulo="Resultado", conteudo="Leitura salva", parcial=True)
    request = RequestFactory().get("/admin/super-equipe/")
    request.admin = {"nome": "Administrador", "equipe_apenas": False}
    lista = pagina(request)
    assert lista.status_code == 200
    assert b"Verifique o andamento" in lista.content
    detalhe = super_equipe_trabalho(request, trabalho.pk)
    assert detalhe.status_code == 200
    assert b"Leitura salva" in detalhe.content
    assert b"Atualizar andamento" in detalhe.content


@pytest.mark.django_db
def test_resposta_paga_incompleta_nao_conclui_nem_repete_custo():
    membro = MembroDaEquipe.objects.create(nome="Responsável")
    trabalho, _ = super_equipe.pedir_trabalho(
        membro, site_id="site-1", host="meshcraft.top", pedido="Confira a fonte",
        especialidades=["seguranca"], chave="resposta-incompleta")
    fontes = {"consultado_em": "2026-10-06", "negocio": {"financeiro": {"estado": "medido"},
              "alunos": {"estado": "medido"}, "cursos": {"estado": "medido"}},
              "experimentos": {"estado": "medido"},
              "paginas_publicas": {"itens": [{"estado": "medido", "http": 200}]}}

    def incompleta(**kwargs):
        consumo = Consumo.objects.create(execucao=kwargs["execucao"], modelo="gpt-6-sol",
                                         custo_estimado_usd=Decimal("0.001"))
        return SimpleNamespace(completa=False, texto="parcial", id="r1", consumo=consumo)

    with patch.object(super_equipe, "coletar_fontes", return_value=fontes), \
         patch.object(super_equipe.modelo, "conexao", return_value=SimpleNamespace(modelo_forte="gpt-6-sol")), \
         patch.object(super_equipe.modelo, "responder", side_effect=incompleta) as chamada:
        executor.rodar_uma("teste-incompleta")
        trabalho.refresh_from_db()
        assert trabalho.situacao == Execucao.Situacao.FALHOU
        assert Entrega.objects.get(execucao=trabalho).parcial
        Execucao.objects.filter(pk=trabalho.pk).update(situacao=Execucao.Situacao.NA_FILA)
        executor.rodar_uma("teste-retomada")
        assert chamada.call_count == 1
    trabalho.refresh_from_db()
    assert trabalho.situacao == Execucao.Situacao.FALHOU
    assert trabalho.consumos.count() == 1
