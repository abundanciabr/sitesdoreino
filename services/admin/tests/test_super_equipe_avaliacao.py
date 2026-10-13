import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.test import RequestFactory

from apps.agentes import executor, super_equipe as equipe
from apps.agentes import super_equipe_avaliacao as avaliacao
from apps.agentes.models import Consumo, Execucao
from apps.agentes.super_equipe_perfis import PERFIS
from apps.agentes.views_super_equipe import super_equipe_trabalho
from apps.core.models import MembroDaEquipe


def fotografia():
    return {"consultado_em": "2026-10-13T12:00:00Z", "robos_ia": {"estado": "medido"},
            "experimentos": {"estado": "medido", "itens": []},
            "fluxo_entregas": {"processamento_ativo": None, "espera": 113},
            "paginas_publicas": {"itens": [{"estado": "medido", "http": 200}]}}


def test_material_explicita_truncamento_e_exclui_contexto_revogado():
    estado = {"fontes": fotografia(), "fontes_anteriores": [{"SEGREDO_REVOGADO": True}],
              "resultados": {"jez_humble": {"texto": "x" * 13000, "fontes_digest": "atual"},
                             "liz_fong_jones": {"texto": "SEGREDO_REVOGADO", "fontes_digest": "antigo"}}}
    dados = avaliacao.material(estado, "atual", equipe._sem_dados_pessoais)
    assert dados["pares_do_proprio_trabalho"][0]["truncado"] is True
    assert len(dados["pares_do_proprio_trabalho"][0]["texto"]) == 12000
    assert dados["perfis_excluidos_por_fotografia"] == ["liz_fong_jones"]
    assert "SEGREDO_REVOGADO" not in json.dumps(dados)
    assert dados["fontes_para_confronto"]["fluxo_entregas"]["processamento_ativo"] is None


def test_contexto_compacto_preserva_fatos_e_nao_muda_fotografia_salva():
    fonte = {"estado": "medido", "serie": list(range(1000)), "ausente": None, "zero": 0}
    contexto = {"fontes": {"servidor": fonte, "outra": {"estado": "indisponivel"},
                           "resultados_anteriores": {"jez_humble": "Alegação"}},
                "confronto": {"fontes_para_confronto": {"servidor": fonte},
                              "pares_do_proprio_trabalho": [
                                  {"perfil": "jez_humble", "texto": "Alegação com evidência"}]}}
    original = json.dumps(contexto, ensure_ascii=False)
    compacto, medicao = avaliacao.compactar_contexto(contexto)
    assert json.dumps(contexto, ensure_ascii=False) == original
    assert "servidor" not in compacto["fontes"]
    assert "resultados_anteriores" not in compacto["fontes"]
    assert compacto["confronto"] == contexto["confronto"]
    assert compacto["fontes"]["outra"] == contexto["fontes"]["outra"]
    assert compacto["fontes_reutilizadas_nesta_entrada"]["servidor"] == "confronto.fontes_para_confronto.servidor"
    assert medicao["bytes_antes"] == len(original.encode())
    assert medicao["bytes_enviados"] == len(json.dumps(compacto, ensure_ascii=False).encode())
    assert medicao["bytes_repetidos_evitados"] > 4000


def test_nao_reutiliza_fonte_divergente_ou_parecer_truncado_incompativel():
    contexto = {"fontes": {"servidor": {"versao": "nova"},
                           "resultados_anteriores": {"jez_humble": "Parecer completo"}},
                "confronto": {"fontes_para_confronto": {"servidor": {"versao": "antiga"}},
                              "pares_do_proprio_trabalho": [{"perfil": "jez_humble", "texto": "Parecer"}]}}
    compacto, medicao = avaliacao.compactar_contexto(contexto)
    assert compacto == contexto
    assert medicao["bytes_repetidos_evitados"] == 0


def test_perfil_individual_sem_confronto_conserva_contexto_integral():
    contexto = {"pedido": "Diagnóstico", "fontes": fotografia()}
    compacto, medicao = avaliacao.compactar_contexto(contexto)
    assert compacto == contexto
    assert medicao["bytes_repetidos_evitados"] == 0


@pytest.mark.django_db
def test_cinco_pareceres_revisao_com_fontes_e_sintese_posterior_persistidas():
    membro = MembroDaEquipe.objects.create(nome="Ensaio privado")
    trabalho, _ = equipe.pedir_trabalho(membro, site_id="ensaio", host="meshcraft.top",
        pedido="Confronte evidência e resultado", especialidades=list(PERFIS), chave="qualidade")
    vistos = []

    def responder(**kwargs):
        entrada = json.loads(kwargs["itens"][0]["content"])
        salvo = Execucao.objects.get(pk=kwargs["execucao"].pk)
        assert len(salvo.estado["entradas_avaliacao"]) == len(vistos) + 1
        vistos.append(entrada)
        consumo = Consumo.objects.create(execucao=trabalho, modelo="ensaio",
            custo_estimado_usd=Decimal("0.001"), tokens_entrada=10, tokens_saida=20)
        return SimpleNamespace(completa=True, texto="PARECER_" + str(len(vistos)),
                               id="isolado", consumo=consumo)

    with patch.object(equipe, "coletar_fontes", return_value=fotografia()), \
         patch.object(equipe.modelo, "conexao", return_value=SimpleNamespace(modelo_forte="ensaio")), \
         patch.object(equipe.modelo, "responder", side_effect=responder):
        executor.rodar_uma("ensaio-rastreavel")
    trabalho.refresh_from_db()
    assert len(vistos) == 6 and trabalho.consumos.count() == 6
    assert len(vistos[4]["confronto"]["pares_do_proprio_trabalho"]) == 4
    assert vistos[4]["confronto"]["fontes_para_confronto"]["fluxo_entregas"]["espera"] == 113
    assert len(vistos[5]["confronto"]["pares_do_proprio_trabalho"]) == 5
    assert len(trabalho.estado["resultados"]) == 5
    assert trabalho.estado["sintese_final"]["texto"] == "PARECER_6"
    assert "PARECER_6" in trabalho.entregas.get().conteudo
    request = RequestFactory().get("/super-equipe/")
    request.admin = {"equipe_apenas": False}
    resposta = super_equipe_trabalho(request, trabalho.pk)
    assert resposta.status_code == 200
    assert b"Rastreio das entradas" in resposta.content and b"PARECER_6" in resposta.content
    assert b"Contexto desta chamada" in resposta.content
    for entrada in trabalho.estado["entradas_avaliacao"].values():
        assert entrada["economia_contexto"]["bytes_enviados"] == len(json.dumps(
            entrada["contexto"], ensure_ascii=False, default=str).encode())


@pytest.mark.django_db
@pytest.mark.parametrize("perdida", [False, True])
def test_retomada_da_sintese_nao_repete_pareceres_nem_chamada_incerta(perdida):
    membro = MembroDaEquipe.objects.create(nome="Ensaio de continuidade")
    trabalho, _ = equipe.pedir_trabalho(membro, site_id="ensaio", host="meshcraft.top",
        pedido="Sintetizar", especialidades=["nicole_forsgren", "shreya_shankar"], chave=f"sintese-{perdida}")
    trabalho.estado["resultados"] = {c: {"texto": "Já pago", "fontes_digest": "antigo"}
                                    for c in trabalho.estado["especialidades"]}
    trabalho.estado["fontes"] = {"antiga": "CONTEXTO_ANTIGO"}
    trabalho.estado["fontes_tentativa"] = 0
    trabalho.save()
    for _ in range(2 + int(perdida)):
        Consumo.objects.create(execucao=trabalho, modelo="ensaio", custo_estimado_usd=Decimal("0.001"))
    entradas = []

    def responder(**kwargs):
        entradas.append(json.loads(kwargs["itens"][0]["content"]))
        consumo = Consumo.objects.create(execucao=trabalho, modelo="ensaio", custo_estimado_usd=Decimal("0.001"))
        return SimpleNamespace(completa=True, texto="Síntese limitada", id="ensaio", consumo=consumo)

    with patch.object(equipe, "coletar_fontes", return_value=fotografia()), \
         patch.object(equipe.modelo, "conexao", return_value=SimpleNamespace(modelo_forte="ensaio")), \
         patch.object(equipe.modelo, "responder", side_effect=responder):
        executor.rodar_uma("retomada-sintese")
    trabalho.refresh_from_db()
    assert len(entradas) == (0 if perdida else 1)
    assert trabalho.consumos.count() == 3
    assert all(r["texto"] == "Já pago" for r in trabalho.estado["resultados"].values())
    if perdida:
        assert trabalho.situacao == Execucao.Situacao.FALHOU
        assert "sintese_final" not in trabalho.estado
    else:
        assert "CONTEXTO_ANTIGO" not in json.dumps(entradas)
        assert entradas[0]["confronto"]["pares_do_proprio_trabalho"] == []
