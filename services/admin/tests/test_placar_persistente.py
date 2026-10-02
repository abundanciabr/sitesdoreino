"""Os dados antigos entram inteiros; edições e encerramentos sobrevivem à página."""

import datetime as dt
import importlib
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

import pytest
from django.apps import apps
from django.db import connection
from django.test import RequestFactory

from apps.core.fechamento import fechamento
from apps.core.gestao_do_placar import gestao_do_placar
from apps.core.models import CartaoDoPlacar, FechamentoDoCiclo, RegistroDoPlacar, VersaoDoCartaoDoPlacar


pytestmark = pytest.mark.django_db


def test_importacao_preserva_todos_e_repetir_nao_sobrescreve():
    raiz = Path(__file__).resolve().parents[1] / "apps" / "core"
    assert CartaoDoPlacar.objects.count() == len(list((raiz / "cartoes").glob("*.json")))
    assert RegistroDoPlacar.objects.count() == len(list((raiz / "registros").glob("*.js")))
    assert VersaoDoCartaoDoPlacar.objects.count() == CartaoDoPlacar.objects.count()
    meta = CartaoDoPlacar.objects.get(nome="compras-no-ciclo")
    meta.dados = {**meta.dados, "alvo": 12345}
    meta.save()
    importador = importlib.import_module("apps.core.migrations.0041_placar_persistente")
    importador.importar(apps, SimpleNamespace(connection=connection))
    assert CartaoDoPlacar.objects.count() == len(list((raiz / "cartoes").glob("*.json")))
    assert RegistroDoPlacar.objects.count() == len(list((raiz / "registros").glob("*.js")))
    assert CartaoDoPlacar.objects.get(nome="compras-no-ciclo").dados["alvo"] == 12345


def test_meta_e_registro_sao_editados_no_painel():
    rf = RequestFactory()
    pagina = rf.get("/admin/placar/editar/")
    pagina.admin = {"email": "dono@example.com"}
    assert gestao_do_placar(pagina).status_code == 200
    meta = CartaoDoPlacar.objects.get(nome="compras-no-ciclo")
    invalido = rf.post("/admin/placar/editar/", {
        "acao": "cartao", "nome": meta.nome, "alvo": "duas mil",
        "partida": "0", "ate": meta.dados["ate"],
        "partida_em": meta.dados["partida_em"],
    })
    invalido.admin = pagina.admin
    resposta_invalida = gestao_do_placar(invalido)
    assert resposta_invalida.status_code == 200
    assert b'duas mil' in resposta_invalida.content
    assert CartaoDoPlacar.objects.get(nome=meta.nome).dados["alvo"] == meta.dados["alvo"]
    pedido = rf.post("/admin/placar/editar/", {
        "acao": "cartao", "nome": meta.nome, "pergunta": "Nova pergunta",
        "alvo": str(meta.dados["alvo"]), "partida": str(meta.dados["partida"]),
        "ate": meta.dados["ate"], "partida_em": meta.dados["partida_em"],
        "orientacao": meta.dados["acao"],
    })
    pedido.admin = {"email": "dono@example.com"}
    assert gestao_do_placar(pedido).status_code == 302
    assert CartaoDoPlacar.objects.get(nome=meta.nome).dados["pergunta"] == "Nova pergunta"
    assert CartaoDoPlacar.objects.get(nome=meta.nome).dados["atualizado_por"] == "dono@example.com"
    assert meta.versoes.count() == 2
    novo = rf.post("/admin/placar/editar/", {
        "acao": "registro", "tipo": "compromisso", "quando": "2026-10-02",
        "titulo": "Telefonar para as alunas", "vence_em_dias": "7",
    })
    novo.admin = pedido.admin
    assert gestao_do_placar(novo).status_code == 302
    assert RegistroDoPlacar.objects.get(dados__titulo="Telefonar para as alunas").dados["vence_em_dias"] == 7
    assert RegistroDoPlacar.objects.get(dados__titulo="Telefonar para as alunas").dados["responsavel"] == "dono@example.com"


def test_fechamento_grava_campos_opcionais_e_nova_meta():
    rf = RequestFactory()
    pedido = rf.post("/admin/placar/fechamento/", {
        "paramos_de_fazer": "", "por_que": "Resultado observado",
        "proximo_alvo": "2000", "proxima_ate": "2027-03-09",
    })
    pedido.admin = {"email": "dono@example.com"}
    meta = CartaoDoPlacar.objects.get(nome="compras-no-ciclo").dados
    resultado = {"x": 5, "alvo": meta["alvo"], "ate": meta["ate"], "partida_em": meta["partida_em"]}
    contexto = {"meta": meta, "placar": resultado, "direcao": None, "recusas": []}
    dados = {
        "estado": "correndo", "partida_em": dt.date(2026, 9, 3),
        "resultado": resultado, "veredito": "perdendo",
        "previsao": {"veredito": "ainda-nao-da", "porque": "teste"},
        "fase": {"fase": "provando"},
    }
    with patch("apps.core.fechamento.montar_o_placar", return_value=contexto), \
         patch("apps.core.fechamento.montar", return_value=dados), \
         patch("apps.core.fechamento.site_de", return_value=None), \
         patch("apps.core.fechamento.timezone.localdate", return_value=dt.date(2026, 10, 2)):
        assert fechamento(pedido).status_code == 200
    encerrado = FechamentoDoCiclo.objects.get(partida_em="2026-09-03")
    assert encerrado.dados["paramos_de_fazer"] == ""
    assert encerrado.dados["por_que"] == "Resultado observado"
    assert encerrado.dados["responsavel"] == "dono@example.com"
    atual = CartaoDoPlacar.objects.get(nome="compras-no-ciclo").dados
    assert (atual["alvo"], atual["partida"], atual["ate"]) == (2000, 5, "2027-03-09")
    assert "semanas" not in atual
    assert VersaoDoCartaoDoPlacar.objects.get(cartao__nome="compras-no-ciclo", revisao=2).dados["alvo"] == 2000
