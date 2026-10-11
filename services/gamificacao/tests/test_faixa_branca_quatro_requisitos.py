"""A primeira entrega nova exige quatro registros; conquistas antigas permanecem."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.urls import reverse

from apps.core.trilha_api import _projecao
from apps.gamificacao.bonus_faixas import configurar
from apps.gamificacao.checklist_trilha import montar_checklists
from apps.gamificacao.jornada import salvar, situacao
from apps.gamificacao.models import AnexoDaJornada, JornadaPessoal, PerfilJogador, RegistroDaJornada


pytestmark = pytest.mark.django_db
SITE, P = "site-quatro-requisitos", "aluna-quatro-requisitos"
URL = "/inventario/"
CAMINHOS = (
    "/conquistas/inicio/motivo/",
    "/conquistas/inicio/objetivo/",
    "/conquistas/inicio/item/",
    "/conquistas/inicio/item/#inicio-form-item",
)


@pytest.fixture(autouse=True)
def conta(monkeypatch):
    monkeypatch.setenv("SITE_ID", SITE)
    monkeypatch.setattr("apps.core.inventario._sessao", lambda cookie: {"autenticado": True, "id": P})
    monkeypatch.setattr("apps.core.views.quem_e", lambda request: P)


def arquivo():
    return SimpleUploadedFile("primeiro.obj", b"v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n")


def post(client, acao, **dados):
    revisao = client.get(URL, HTTP_COOKIE="meshcraft_sessao=A").json()["revisao"]
    return client.post(URL, {"acao": acao, "revisao": revisao, **dados}, HTTP_COOKIE="meshcraft_sessao=A")


def preparar(client):
    assert post(client, "inicio-motivo", motivo="ugc", motivo_pessoal="MOTIVO-PRIVADO-ALFA").status_code == 200
    assert post(client, "inicio-plano", objetivo="OBJETIVO-PRIVADO-ALFA",
                compromisso="COMPROMISSO-PRIVADO-ALFA", sonho="SONHO-PRIVADO-ALFA",
                assumir="sim").status_code == 200
    assert post(client, "anexo", passo="2", arquivo=arquivo()).status_code == 200


@pytest.mark.parametrize("faltando", ["motivo", "objetivo", "compromisso", "confirmado_em", "arquivo"])
def test_cada_requisito_bloqueia_declaracao_nova_no_nucleo_e_na_rota(client, faltando):
    configurar(SITE)
    preparar(client)
    if faltando == "arquivo":
        AnexoDaJornada.objects.filter(pessoa_id=P, site_id=SITE).delete()
    else:
        jornada = JornadaPessoal.objects.get(pessoa_id=P, site_id=SITE)
        inicio = dict(jornada.inicio)
        inicio[faltando] = None if faltando == "confirmado_em" else ""
        jornada.inicio = inicio
        jornada.save(update_fields=["inicio"])

    dados = {"acao": "declaracao", "passo": "2", "estado": "feito",
             "revisao": situacao(P, SITE)["revisao"]}
    with pytest.raises(ValueError):
        salvar(P, SITE, dados)
    resposta = post(client, "declaracao", passo="2", estado="feito")
    assert resposta.status_code == 400
    assert situacao(P, SITE)["atual"]["ordem"] == 1
    assert not JornadaPessoal.objects.get(pessoa_id=P, site_id=SITE).declaracoes.get("2")
    assert not RegistroDaJornada.objects.filter(pessoa_id=P, site_id=SITE, acao="declaracao").exists()
    assert PerfilJogador.objects.get(pessoa_id=P, site_id=SITE).xp_total == 0


def test_rascunho_e_anexo_sao_permitidos_antes_dos_quatro_requisitos(client):
    assert post(client, "inicio-plano", objetivo="Uma peça", compromisso="Vou tentar",
                assumir="nao").status_code == 200
    assert post(client, "anexo", passo="2", arquivo=arquivo()).status_code == 200
    assert post(client, "declaracao", passo="2", estado="feito").status_code == 400
    assert AnexoDaJornada.objects.count() == 1
    assert JornadaPessoal.objects.get().inicio["confirmado_em"] is None
    assert situacao(P, SITE)["atual"]["ordem"] == 1


def test_quatro_requisitos_concluem_uma_vez_e_edicao_posterior_regride_sem_apagar(client):
    configurar(SITE)
    preparar(client)
    resposta = post(client, "declaracao", passo="2", estado="feito")
    assert resposta.status_code == 200 and resposta.json()["atual_ordem"] == 2
    assert PerfilJogador.objects.get(pessoa_id=P, site_id=SITE).xp_total == 5000
    assert post(client, "declaracao", passo="2", estado="feito").status_code == 200
    assert PerfilJogador.objects.get(pessoa_id=P, site_id=SITE).xp_total == 5000
    assert RegistroDaJornada.objects.filter(pessoa_id=P, site_id=SITE, acao="declaracao").count() == 1

    assert post(client, "inicio-plano", objetivo="Objetivo revisado",
                compromisso="Compromisso revisado", assumir="nao").status_code == 200
    assert JornadaPessoal.objects.get(pessoa_id=P, site_id=SITE).inicio["confirmado_em"] is None
    assert situacao(P, SITE)["atual"]["ordem"] == 1
    assert [i["estado"] for i in montar_checklists(P, SITE, situacao(P, SITE))[2]["itens"]] == [
        "concluido", "pendente", "andamento", "concluido",
    ]
    assert JornadaPessoal.objects.get(pessoa_id=P, site_id=SITE).declaracoes.get("2")
    assert PerfilJogador.objects.get(pessoa_id=P, site_id=SITE).xp_total == 5000


def test_editar_somente_sonho_nao_desfaz_compromisso_ja_confirmado(client):
    preparar(client)
    assert post(client, "declaracao", passo="2", estado="feito").status_code == 200
    confirmado = JornadaPessoal.objects.get(pessoa_id=P, site_id=SITE).inicio["confirmado_em"]
    resposta = post(client, "inicio-plano", objetivo="OBJETIVO-PRIVADO-ALFA",
                   compromisso="COMPROMISSO-PRIVADO-ALFA", sonho="SONHO-REVISTO-ALFA",
                   assumir="nao")
    assert resposta.status_code == 200
    jornada = JornadaPessoal.objects.get(pessoa_id=P, site_id=SITE)
    assert jornada.inicio["confirmado_em"] == confirmado
    assert jornada.inicio["sonho"] == "SONHO-REVISTO-ALFA"
    assert situacao(P, SITE)["atual"]["ordem"] == 2


def test_declaracao_legada_sem_inicio_nem_anexo_recomeca_branca_sem_ser_apagada(client):
    from apps.core.perfil import perfil_de

    perfil_de(P, SITE)
    JornadaPessoal.objects.create(pessoa_id=P, site_id=SITE, declaracoes={"2": "2026-10-01T10:00:00-03:00"})
    assert situacao(P, SITE)["atual"]["ordem"] == 1
    assert [i["estado"] for i in montar_checklists(P, SITE, situacao(P, SITE))[2]["itens"]] == ["pendente"] * 4
    assert post(client, "inicio-motivo", motivo="jogo").status_code == 200
    assert situacao(P, SITE)["atual"]["ordem"] == 1
    assert JornadaPessoal.objects.get(pessoa_id=P, site_id=SITE).declaracoes.get("2")


def test_checklist_tem_quatro_itens_e_nao_exporta_respostas_privadas(client):
    def itens():
        return montar_checklists(P, SITE, situacao(P, SITE))[2]["itens"]

    iniciais = itens()
    assert [i["id"] for i in iniciais] == ["motivo-2", "plano-2", "item-2", "envio-2"]
    assert [i["acao"]["url"] for i in iniciais] == list(CAMINHOS)
    assert [i["estado"] for i in iniciais] == ["pendente"] * 4

    assert post(client, "inicio-motivo", motivo="ugc", motivo_pessoal="MOTIVO-PRIVADO-ALFA").status_code == 200
    assert post(client, "inicio-plano", objetivo="OBJETIVO-PRIVADO-ALFA",
                compromisso="COMPROMISSO-PRIVADO-ALFA", sonho="SONHO-PRIVADO-ALFA",
                assumir="nao").status_code == 200
    assert [i["estado"] for i in itens()] == ["concluido", "pendente", "pendente", "pendente"]
    assert post(client, "inicio-plano", objetivo="OBJETIVO-PRIVADO-ALFA",
                compromisso="COMPROMISSO-PRIVADO-ALFA", sonho="SONHO-PRIVADO-ALFA",
                assumir="sim").status_code == 200
    assert post(client, "anexo", passo="2", arquivo=arquivo()).status_code == 200
    assert [i["estado"] for i in itens()] == ["concluido", "concluido", "andamento", "concluido"]
    projecao = _projecao(HttpResponse(), P, SITE).model_dump_json()
    for segredo in ("MOTIVO-PRIVADO-ALFA", "OBJETIVO-PRIVADO-ALFA",
                    "COMPROMISSO-PRIVADO-ALFA", "SONHO-PRIVADO-ALFA"):
        assert segredo not in projecao and segredo not in str(itens())
    assert post(client, "declaracao", passo="2", estado="feito").status_code == 200
    assert [i["estado"] for i in itens()] == ["concluido"] * 4


def test_consultas_nao_alteram_revisao_xp_ou_declaracao(client):
    assert post(client, "inicio-motivo", motivo="descobrir").status_code == 200
    jornada = JornadaPessoal.objects.get(pessoa_id=P, site_id=SITE)
    revisao = jornada.revisao
    for nome in ("base", "inicio-motivo", "inicio-objetivo", "inicio-item"):
        assert client.get(reverse(nome)).status_code == 200
    assert client.get(URL, HTTP_COOKIE="meshcraft_sessao=A").status_code == 200
    _projecao(HttpResponse(), P, SITE)
    jornada.refresh_from_db()
    assert jornada.revisao == revisao and not jornada.declaracoes
    assert PerfilJogador.objects.get(pessoa_id=P, site_id=SITE).xp_total == 0


def test_revisao_antiga_e_outro_dono_nao_aproveitam_quatro_requisitos(client, monkeypatch):
    preparar(client)
    atual = situacao(P, SITE)["revisao"]
    resposta = client.post(URL, {"acao": "declaracao", "passo": "2", "estado": "feito",
                                  "revisao": atual - 1}, HTTP_COOKIE="meshcraft_sessao=A")
    assert resposta.status_code == 400
    monkeypatch.setattr("apps.core.inventario._sessao", lambda cookie: {"autenticado": True, "id": "outra-aluna"})
    assert post(client, "declaracao", passo="2", estado="feito").status_code == 400
    assert not JornadaPessoal.objects.filter(pessoa_id="outra-aluna", site_id=SITE, declaracoes__has_key="2").exists()
    monkeypatch.setattr("apps.core.inventario._sessao", lambda cookie: {"autenticado": True, "id": P})
    monkeypatch.setenv("SITE_ID", "outro-site")
    assert post(client, "declaracao", passo="2", estado="feito").status_code == 400
    assert situacao(P, SITE)["atual"]["ordem"] == 1
