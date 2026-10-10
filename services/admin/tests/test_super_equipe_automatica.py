import copy
import json
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.test import RequestFactory
from django.utils import timezone

from apps.agentes import super_equipe, super_equipe_automatica as auto
from apps.agentes.models import (Consumo, Entrega, EventoSuperEquipe, Execucao,
                                 MelhoriaSuperEquipe, RotinaSuperEquipe)
from apps.agentes.views_super_equipe import super_equipe_acao, super_equipe_fila, super_equipe as painel
from apps.core.models import MembroDaEquipe


@pytest.fixture
def fontes():
    return {"consultado_em": "2026-10-10T15:00:00Z", "negocio": {
        "financeiro": {"estado": "medido"}, "alunos": {"estado": "medido"},
        "cursos": {"estado": "medido"}}, "experimentos": {"estado": "medido"},
        "robos_ia": {"estado": "medido"}, "paginas_publicas": {"itens": [
            {"estado": "medido", "http": 200, "url": "https://meshcraft.top/"}]}}


@pytest.fixture
def rotina():
    membro = MembroDaEquipe.objects.create(nome="Responsável")
    from apps.agentes.trabalhos import robo_de
    robo_de(membro)
    return RotinaSuperEquipe.objects.create(host="meshcraft.top", site_id="site-1")


def rodar(fontes):
    with patch.object(super_equipe, "coletar_fontes", return_value=copy.deepcopy(fontes)):
        return auto.ciclo()


def adiantar(rotina, **campos):
    RotinaSuperEquipe.objects.filter(pk=rotina.pk).update(proxima_em=timezone.now() - timedelta(seconds=1), **campos)


def chamada(id_, dados, equipe=False):
    request = RequestFactory().post("/admin/super-equipe/melhorias/1/", data=json.dumps(dados), content_type="application/json")
    request.admin = {"equipe_apenas": equipe, "robo": True}
    return super_equipe_acao(request, id_)


@pytest.fixture
def melhoria(rotina):
    return auto._ocorrencia(rotina, "fonte:teste", "Uma fonte falhou", {"operacao": "fonte"})


def test_ciclo_duravel_nao_duplica_analise_nem_ocorrencia(rotina, fontes):
    fontes["paginas_publicas"]["itens"][0]["http"] = 404
    assert rodar(fontes)
    assert not rodar(fontes)
    rotina.refresh_from_db()
    assert rotina.observada_em and rotina.proxima_em
    assert rotina.ultimo_trabalho.origem == "super_equipe_automatica"
    assert rotina.ultimo_trabalho.estado["fontes"] == fontes
    assert MelhoriaSuperEquipe.objects.count() == 1
    adiantar(rotina)
    assert rodar(fontes)
    assert Execucao.objects.count() == 1
    assert MelhoriaSuperEquipe.objects.count() == 1
    assert Consumo.objects.count() == 0  # observação e agendamento não chamam IA


def test_posse_ativa_impede_segundo_observador_e_vencida_retoma(rotina, fontes):
    adiantar(rotina, posse="anterior", ocupada_ate=timezone.now() + timedelta(minutes=2))
    assert not rodar(fontes)
    adiantar(rotina, ocupada_ate=timezone.now() - timedelta(seconds=1))
    assert rodar(fontes)
    rotina.refresh_from_db()
    assert not rotina.posse and rotina.ocupada_ate is None


def test_pausa_persistente_impede_observacao(rotina, fontes):
    adiantar(rotina, ativa=False)
    with patch.object(super_equipe, "coletar_fontes") as coletar:
        assert not auto.ciclo()
        coletar.assert_not_called()


def test_falha_de_coleta_nao_apaga_pendencia_nem_conclui(rotina, melhoria):
    with patch.object(super_equipe, "coletar_fontes", side_effect=RuntimeError("segredo-nao-publicavel")):
        assert not auto.ciclo()
    rotina.refresh_from_db()
    melhoria.refresh_from_db()
    assert "RuntimeError" in rotina.ultimo_erro
    assert "segredo" not in rotina.ultimo_erro
    assert melhoria.situacao == "pendente"
    assert not rotina.posse


def test_fonte_recuperada_e_recidiva_tem_historico(rotina, fontes):
    fontes["robos_ia"]["estado"] = "indisponivel"
    rodar(fontes)
    item = MelhoriaSuperEquipe.objects.get()
    fontes["robos_ia"]["estado"] = "medido"
    adiantar(rotina)
    rodar(fontes)
    item.refresh_from_db()
    assert item.situacao == "resolvida"
    fontes["robos_ia"]["estado"] = "indisponivel"
    adiantar(rotina)
    rodar(fontes)
    item.refresh_from_db()
    assert item.situacao == "pendente" and item.resolvida_em is None
    assert item.eventos.count() == 3


def test_repara_ressalva_antiga_preservando_parecer_e_consumo(rotina, fontes):
    trabalho, _ = super_equipe.pedir_trabalho(None, site_id="site-1", host="meshcraft.top",
        pedido="Análise anterior", especialidades=["seguranca"], chave="antiga")
    fontes["robos_ia"]["estado"] = "indisponivel"
    trabalho.estado.update(fontes=copy.deepcopy(fontes), resultados={"seguranca": {"texto": "Parecer original"}})
    trabalho.situacao = Execucao.Situacao.CONCLUIDA
    trabalho.save()
    entrega = super_equipe._entrega(trabalho, parcial=False, pendencias=[])
    Consumo.objects.create(execucao=trabalho, modelo="teste", custo_estimado_usd="0.01")
    fontes["robos_ia"]["estado"] = "medido"  # a fonte atual não reescreve o passado
    rodar(fontes)
    trabalho.refresh_from_db()
    entrega.refresh_from_db()
    assert trabalho.situacao == Execucao.Situacao.AGUARDANDO_INFORMACAO
    assert entrega.parcial and "IA" in entrega.pendencias[0]
    assert "Parecer original" in entrega.conteudo
    assert trabalho.estado["fontes"]["robos_ia"]["estado"] == "indisponivel"
    assert trabalho.consumos.count() == 1
    versao = entrega.versao
    adiantar(rotina)
    rodar(fontes)
    entrega.refresh_from_db()
    assert entrega.versao == versao
    assert MelhoriaSuperEquipe.objects.filter(situacao="resolvida", evidencia__operacao="ressalvas").count() == 1


def test_parecer_concluido_chega_a_fila_uma_vez(rotina, fontes):
    rodar(fontes)
    rotina.refresh_from_db()
    Execucao.objects.filter(pk=rotina.ultimo_trabalho_id).update(situacao=Execucao.Situacao.CONCLUIDA)
    adiantar(rotina)
    rodar(fontes)
    adiantar(rotina)
    rodar(fontes)
    assert MelhoriaSuperEquipe.objects.filter(evidencia__operacao="desenvolvimento").count() == 1
    assert Execucao.objects.count() == 1


def test_nova_analise_nao_duplica_desenvolvimento_pendente(rotina, fontes):
    rodar(fontes)
    rotina.refresh_from_db()
    Execucao.objects.filter(pk=rotina.ultimo_trabalho_id).update(
        situacao=Execucao.Situacao.CONCLUIDA, criada_em=timezone.now() - timedelta(days=2))
    adiantar(rotina)
    futuro = timezone.now() + timedelta(days=2)
    with patch.object(auto.timezone, "now", return_value=futuro):
        rodar(fontes)
    rotina.refresh_from_db()
    Execucao.objects.filter(pk=rotina.ultimo_trabalho_id).update(situacao=Execucao.Situacao.CONCLUIDA)
    adiantar(rotina)
    rodar(fontes)
    assert Execucao.objects.count() == 2
    assert MelhoriaSuperEquipe.objects.filter(evidencia__operacao="desenvolvimento").count() == 1


def test_trabalho_aguardando_orcamento_nao_gera_nova_cobranca(rotina, fontes):
    rodar(fontes)
    rotina.refresh_from_db()
    Execucao.objects.filter(pk=rotina.ultimo_trabalho_id).update(
        situacao=Execucao.Situacao.AGUARDANDO_AUTORIZACAO, criada_em=timezone.now() - timedelta(days=2))
    adiantar(rotina)
    rodar(fontes)
    assert Execucao.objects.count() == 1


def test_sem_robo_monitora_e_mostra_dependencia(fontes):
    rotina = RotinaSuperEquipe.objects.create(host="meshcraft.top", site_id="site-1")
    assert rodar(fontes)
    rotina.refresh_from_db()
    assert "robô disponível" in rotina.ultimo_erro


def test_assumir_duplicado_recusado_e_posse_vencida_retoma(melhoria):
    primeira = chamada(melhoria.pk, {"acao": "assumir"})
    assert primeira.status_code == 200
    assert chamada(melhoria.pk, {"acao": "assumir"}).status_code == 409
    posse = json.loads(primeira.content)["posse"]
    MelhoriaSuperEquipe.objects.filter(pk=melhoria.pk).update(ocupada_ate=timezone.now() - timedelta(seconds=1))
    assert chamada(melhoria.pk, {"acao": "batimento", "posse": posse}).status_code == 409
    nova = json.loads(chamada(melhoria.pk, {"acao": "assumir"}).content)
    assert nova["posse"] != posse
    assert chamada(melhoria.pk, {"acao": "resultado", "posse": posse, "situacao": "resolvida", "resultado": "velho"}).status_code == 409


def test_publicacao_nao_vira_resolvida_e_conclusao_nao_duplica(melhoria):
    posse = json.loads(chamada(melhoria.pk, {"acao": "assumir"}).content)["posse"]
    dados = {"acao": "resultado", "posse": posse, "situacao": "publicando",
             "resultado": "Testes passaram. Entrega recebida, aguardando ativação.", "entrega": "123456abcdef"}
    assert chamada(melhoria.pk, dados).status_code == 200
    melhoria.refresh_from_db()
    assert melhoria.situacao == "publicando" and melhoria.resolvida_em is None
    dados.update(situacao="resolvida", resultado="Publicador confirmou ativa; página conferida.", custo_externo_usd="0.03")
    assert chamada(melhoria.pk, dados).status_code == 200
    eventos = EventoSuperEquipe.objects.count()
    assert chamada(melhoria.pk, dados).status_code == 200
    assert EventoSuperEquipe.objects.count() == eventos
    melhoria.refresh_from_db()
    assert melhoria.resolvida_em and str(melhoria.custo_externo_usd) == "0.030000"


@pytest.mark.parametrize("dados", [[], {}, {"acao": "shell"}, {"acao": "resultado", "posse": "errada"}])
def test_acao_invalida_nao_muda_trabalho(melhoria, dados):
    assert chamada(melhoria.pk, dados).status_code in (400, 409)
    melhoria.refresh_from_db()
    assert melhoria.situacao == "pendente"


def test_equipe_sem_admin_nao_pode_assumir(melhoria):
    assert chamada(melhoria.pk, {"acao": "assumir"}, equipe=True).status_code == 403


def test_painel_mostra_pendencia_historico_e_custo_desconhecido(melhoria):
    request = RequestFactory().get("/admin/super-equipe/")
    request.admin = {"equipe_apenas": False}
    resposta = painel(request)
    assert resposta.status_code == 200
    assert "Uma fonte falhou" in resposta.content.decode()
    assert "não informado" in resposta.content.decode()
    assert "ainda não conectado" in resposta.content.decode()
    assert super_equipe_fila(request).status_code == 200
