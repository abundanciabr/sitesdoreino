from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
import json
from datetime import timedelta
from django.utils import timezone

import pytest
from django.test import RequestFactory

from apps.agentes import executor, super_equipe
from apps.agentes.models import Consumo, Entrega, Execucao
from apps.agentes.super_equipe_perfis import (
    PERFIS, VERSAO_PERFIL, contexto_do_perfil, instrucoes, rotulo,
)
from apps.agentes.views_super_equipe import super_equipe as pagina, super_equipe_trabalho
from apps.core.models import MembroDaEquipe


@pytest.mark.django_db
@pytest.mark.parametrize("mudanca", ["valor", "versao", "janela", "acesso"])
def test_retomada_reconsulta_fontes_sem_reutilizar_contexto_antigo(mudanca):
    membro = MembroDaEquipe.objects.create(nome="Ensaio de retomada")
    trabalho, _ = super_equipe.pedir_trabalho(
        membro, site_id="ensaio", host="meshcraft.top", pedido="Conferir retomada",
        especialidades=["jez_humble", "shreya_shankar"], chave="retomada-" + mudanca)
    anterior = {"consultado_em": "2026-10-12T10:00:00Z", "integridade": {
        "valor": 1, "versao": "v1", "janela": "15min", "acesso": "admin"}}
    trabalho.estado["fontes"] = anterior
    trabalho.estado["fontes_tentativa"] = 1
    trabalho.estado["resultados"] = {"jez_humble": {"texto": "CONTEXTO_ANTIGO",
        "concluido_em": "2026-10-12T10:01:00Z"}}
    trabalho.situacao = Execucao.Situacao.EXECUTANDO
    trabalho.tentativas = 1
    trabalho.trabalhador = "interrompido"
    trabalho.ocupada_ate = timezone.now() - timedelta(seconds=1)
    trabalho.save()
    Consumo.objects.create(execucao=trabalho, modelo="gpt-6-sol",
                           custo_estimado_usd=Decimal("0.001"))
    nova = json.loads(json.dumps(anterior))
    nova["integridade"][mudanca] = "alterado"
    if mudanca == "acesso":
        nova["integridade"] = {"estado": "indisponivel", "acesso": "revogado"}
    vistos = []

    def responder(**kwargs):
        vistos.append(json.loads(kwargs["itens"][0]["content"]))
        consumo = Consumo.objects.create(execucao=kwargs["execucao"], modelo="gpt-6-sol",
            custo_estimado_usd=Decimal("0.001"))
        return SimpleNamespace(completa=True, texto="Nova análise", id="ensaio", consumo=consumo)

    with patch.object(super_equipe, "coletar_fontes", return_value=nova) as coleta, \
         patch.object(super_equipe.modelo, "conexao", return_value=SimpleNamespace(modelo_forte="gpt-6-sol")), \
         patch.object(super_equipe.modelo, "responder", side_effect=responder):
        executor.rodar_uma("retomou")
    trabalho.refresh_from_db()
    assert coleta.call_count == 1 and len(vistos) == 1
    assert "CONTEXTO_ANTIGO" not in json.dumps(vistos)
    assert trabalho.estado["fontes_anteriores"] == [anterior]
    assert trabalho.estado["fontes"] == nova
    assert trabalho.estado["resultados"]["jez_humble"]["texto"] == "CONTEXTO_ANTIGO"
    assert trabalho.consumos.count() == 2
    assert any("outra fotografia" in p for p in trabalho.entregas.get().pendencias)


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


def test_cinco_perfis_tem_contratos_distintos_sem_alterar_rotulos_historicos():
    assert len(PERFIS) == 5
    assert len({p["missao"] for p in PERFIS.values()}) == 5
    assert len({tuple(p["fontes"]) for p in PERFIS.values()}) == 5
    assert len({instrucoes(codigo, super_equipe.ESPECIALIDADES) for codigo in PERFIS}) == 5
    assert rotulo("arquitetura", super_equipe.ESPECIALIDADES) == "Arquitetura e ligação entre as partes do site"
    assert all("não participa, assina nem endossa" in instrucoes(codigo, super_equipe.ESPECIALIDADES)
               for codigo in PERFIS)


def test_contexto_de_cada_perfil_separa_fontes_e_reserva_revisao_para_shreya():
    fontes = {"consultado_em": "2026-10-12T12:00:00-03:00",
              **{nome: {"estado": "medido", "seguro": nome} for nome in (
                  "fluxo_entregas", "negocio", "experimentos", "entregas", "servidor",
                  "integridade", "fontes", "execucao_operacional", "robos_ia")}}
    anteriores = {"nicole_forsgren": {"texto": "resposta conferível"}}
    contextos = {codigo: contexto_do_perfil(codigo, "pedido", fontes, anteriores)
                 for codigo in PERFIS}
    assert set(contextos["nicole_forsgren"]["fontes"]) == {"fluxo_entregas", "negocio", "experimentos", "percurso_comercial"}
    assert "resultados_anteriores" not in contextos["nicole_forsgren"]
    assert set(contextos["jez_humble"]["fontes"]) == {"entregas", "fluxo_entregas", "servidor"}
    assert set(contextos["martin_kleppmann"]["fontes"]) == {"integridade", "entregas", "fontes", "percurso_comercial"}
    assert set(contextos["liz_fong_jones"]["fontes"]) == {"execucao_operacional", "servidor", "fluxo_entregas", "percurso_comercial"}
    assert contextos["shreya_shankar"]["fontes"]["resultados_anteriores"] == anteriores
    assert all(c["versao_perfil"] == VERSAO_PERFIL for c in contextos.values())


@pytest.mark.django_db
def test_pedido_salva_perfis_na_ordem_versionada_e_deixa_historico_antigo_legivel():
    membro = MembroDaEquipe.objects.create(nome="Responsável")
    recebidos = list(reversed(PERFIS))
    trabalho, criado = super_equipe.pedir_trabalho(
        membro, site_id="site-1", host="meshcraft.top", pedido="Avaliação dos cinco perfis",
        especialidades=recebidos, chave="cinco-perfis")
    assert criado
    assert trabalho.estado["especialidades"] == list(PERFIS)
    assert trabalho.estado["versoes_perfil"] == {codigo: VERSAO_PERFIL for codigo in PERFIS}
    legado, _ = super_equipe.pedir_trabalho(
        membro, site_id="site-1", host="meshcraft.top", pedido="Consulta histórica",
        especialidades=["desempenho"], chave="perfil-legado")
    assert legado.estado["especialidades"] == ["desempenho"]
    assert legado.estado["versoes_perfil"] == {}


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
