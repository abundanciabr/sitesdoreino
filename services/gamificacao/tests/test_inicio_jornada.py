"""A primeira escolha, o plano e as versões são privados e revisáveis."""

import json
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.test import Client
from django.urls import reverse
from PIL import Image

from apps.core.trilha_api import _projecao
from apps.gamificacao.jornada import situacao
from apps.gamificacao.models import AnexoDaJornada, JornadaPessoal, PerfilJogador, RegistroDaJornada


pytestmark = pytest.mark.django_db
SITE, P = "site-inicio", "aluna-inicio"
URL = "/inventario/"


@pytest.fixture(autouse=True)
def conta(monkeypatch):
    monkeypatch.setenv("SITE_ID", SITE)
    monkeypatch.setattr("apps.core.inventario._sessao", lambda cookie: {"autenticado": True, "id": P})


def abrir(client):
    return client.get(URL, HTTP_COOKIE="meshcraft_sessao=A")


def guardar(client, acao, **dados):
    atual = abrir(client).json()
    if acao == 'inicio-motivo':
        dados.setdefault('concluir', 'sim')
    return client.post(
        URL,
        {"acao": acao, "revisao": atual["revisao"], **dados},
        HTTP_COOKIE="meshcraft_sessao=A",
    )


def imagem(nome="tentativa.png", cor="red"):
    fluxo = BytesIO()
    Image.new("RGB", (40, 20), cor).save(fluxo, format="PNG")
    return SimpleUploadedFile(nome, fluxo.getvalue(), content_type="image/png")


def liberar_envio(client):
    assert guardar(client, "inicio-motivo", motivo="ugc").status_code == 200
    assert guardar(client, "inicio-plano", objetivo="Minha peça", compromisso="Praticarei", assumir="sim").status_code == 200
    assert guardar(client, "inicio-item").status_code == 200


def test_rascunho_parcial_salva_e_retomada_na_mesma_conta(client):
    assert not JornadaPessoal.objects.exists()
    r = guardar(client, "inicio-motivo", motivo="ugc", motivo_pessoal="Quero criar algo meu")
    assert r.status_code == 200
    assert r.json()["inicio"]["motivo"] == "ugc"
    assert r.json()["inicio"]["motivo_pessoal"] == "Quero criar algo meu"
    r = guardar(client, "inicio-plano", sonho="Meu mundo 3D", objetivo="Um chapéu", apoio="autonomo")
    assert r.status_code == 200
    assert r.json()["inicio"]["sonho"] == "Meu mundo 3D"
    assert r.json()["inicio"]["confirmado_em"] is None
    assert r.json()["inicio"]["apoio"] == "autonomo"
    retomada = abrir(Client()).json()
    assert retomada["inicio"]["objetivo"] == "Um chapéu"
    assert retomada["inicio"]["motivo"] == "ugc"
    assert retomada["atual_ordem"] == 1
    assert situacao(P, SITE)["atual"]["ordem"] == 1
    assert PerfilJogador.objects.get(pessoa_id=P, site_id=SITE).xp_total == 100
    assert not RegistroDaJornada.objects.exists()


def test_edicao_do_compromisso_pede_nova_confirmacao(client):
    assert guardar(client, "inicio-motivo", motivo="descobrir").status_code == 200
    dados = {"objetivo": "Minha primeira peça", "compromisso": "Praticar sábado"}
    assert guardar(client, "inicio-plano", assumir="sim", **dados).json()["inicio"]["confirmado_em"]
    r = guardar(client, "inicio-plano", assumir="nao", **{**dados, "compromisso": "Praticar domingo"})
    assert r.status_code == 200 and r.json()["inicio"]["confirmado_em"] is None
    assert guardar(client, "inicio-plano", assumir="sim", **{**dados, "compromisso": "Praticar domingo"}).json()["inicio"]["confirmado_em"]


def test_conflito_de_revisao_e_contexto_nao_substituem_resposta(client):
    revisao = abrir(client).json()["revisao"]
    assert guardar(client, "inicio-motivo", motivo="jogo").status_code == 200
    for extras, status in (
        ({"revisao": revisao}, 400),
        ({"contexto_pessoa": "outra-pessoa"}, 403),
        ({"contexto_site": "outra-escola"}, 403),
    ):
        r = client.post(URL, {"acao": "inicio-motivo", "motivo": "ugc", **extras}, HTTP_COOKIE="meshcraft_sessao=A")
        assert r.status_code == status
    assert abrir(client).json()["inicio"]["motivo"] == "jogo"


def test_inicio_isolado_por_pessoa_e_site(client, monkeypatch):
    assert guardar(client, "inicio-motivo", motivo="ugc").status_code == 200
    assert guardar(client, "inicio-plano", sonho="Privado A", compromisso="Meu plano").status_code == 200
    monkeypatch.setattr("apps.core.inventario._sessao", lambda cookie: {"autenticado": True, "id": "aluna-b"})
    assert "Privado A" not in str(abrir(client).json())
    monkeypatch.setattr("apps.core.inventario._sessao", lambda cookie: {"autenticado": True, "id": P})
    monkeypatch.setenv("SITE_ID", "outra-escola")
    assert "Privado A" not in str(abrir(client).json())
    assert JornadaPessoal.objects.filter(pessoa_id=P, site_id=SITE).get().inicio["sonho"] == "Privado A"


def test_sessao_csrf_e_identidade_do_corpo(client, monkeypatch):
    assert client.get(URL).status_code == 403
    c = Client(enforce_csrf_checks=True)
    r = c.get(URL, HTTP_COOKIE="meshcraft_sessao=A")
    assert r.status_code == 200
    assert c.post(URL, {"acao": "inicio-motivo", "motivo": "ugc"}, HTTP_COOKIE="meshcraft_sessao=A").status_code == 403
    r = c.post(URL, {"acao": "inicio-motivo", "motivo": "ugc", "revisao": 0,
                     "pessoa_id": "aluna-b", "site_id": "outra-escola"},
               HTTP_X_CSRFTOKEN=r.json()["csrf"])
    assert r.status_code == 200
    assert JornadaPessoal.objects.get().pessoa_id == P
    assert JornadaPessoal.objects.get().site_id == SITE


def test_versoes_notas_previa_privada_e_projecao_sem_sonho(client, monkeypatch):
    assert guardar(client, "inicio-motivo", motivo="ugc").status_code == 200
    assert guardar(client, "inicio-plano", sonho="Segredo no sonho", objetivo="Criar item",
                   compromisso="Praticar").status_code == 200
    assert guardar(client, "inicio-plano", sonho="Segredo no sonho", objetivo="Criar item",
                   compromisso="Praticar", assumir="sim").status_code == 200
    assert guardar(client, "inicio-item").status_code == 200
    for cor, nota in (("red", "Aprendi a forma"), ("blue", "Ajustei a forma")):
        r = guardar(client, "anexo", passo="2", arquivo=imagem(cor=cor), aprendi=nota, duvida="Como melhorar?")
        assert r.status_code == 200
    anexos = abrir(client).json()["anexos"]
    assert len(anexos) == 2
    assert {a["aprendi"] for a in anexos} == {"Aprendi a forma", "Ajustei a forma"}
    assert all(a["duvida"] == "Como melhorar?" and a["previa"] for a in anexos)
    assert AnexoDaJornada.objects.filter(pessoa_id=P, site_id=SITE).count() == 2
    previa_url = reverse("arquivo-inventario", args=[anexos[0]["id"]]) + "?previa=1"
    previa = client.get(previa_url, HTTP_COOKIE="meshcraft_sessao=A")
    assert previa.status_code == 200 and previa["Content-Type"] == "image/png"
    assert previa.content.startswith(b"\x89PNG")
    assert previa["Cache-Control"] == "private, no-store"
    monkeypatch.setattr("apps.core.inventario._sessao", lambda cookie: {"autenticado": True, "id": "aluna-b"})
    assert client.get(previa_url, HTTP_COOKIE="meshcraft_sessao=B").status_code == 404
    resposta = HttpResponse()
    assert "Segredo no sonho" not in _projecao(resposta, P, SITE).model_dump_json()


def test_reenvio_da_mesma_versao_atualiza_notas_sem_apagar_ou_duplicar(client):
    liberar_envio(client)
    r = guardar(client, "anexo", passo="2", arquivo=imagem(), aprendi="Primeira reflexão",
                duvida="Como arredondar?")
    assert r.status_code == 200
    anexo_id = r.json()["anexos"][0]["id"]
    r = guardar(client, "anexo", passo="2", arquivo=imagem(), aprendi="Aprendi a arredondar",
                duvida="")
    assert r.status_code == 200
    assert len(r.json()["anexos"]) == 1
    assert r.json()["anexos"][0]["id"] == anexo_id
    assert r.json()["anexos"][0]["aprendi"] == "Aprendi a arredondar"
    assert r.json()["anexos"][0]["duvida"] == "Como arredondar?"
    assert AnexoDaJornada.objects.count() == 1
    assert PerfilJogador.objects.get(pessoa_id=P, site_id=SITE).xp_total == 300


def test_duas_abas_com_revisao_antiga_nao_sobrescrevem_nota_nem_criam_arquivo(client):
    liberar_envio(client)
    outra_aba = Client()
    revisao_aberta = abrir(outra_aba).json()["revisao"]
    primeiro = client.post(URL, {"acao": "anexo", "passo": "2", "revisao": revisao_aberta,
                                "arquivo": imagem(), "aprendi": "Primeira nota"},
                           HTTP_COOKIE="meshcraft_sessao=A")
    assert primeiro.status_code == 200
    anexo_id = primeiro.json()["anexos"][0]["id"]
    revisao_nova = primeiro.json()["revisao"]
    assert revisao_nova == revisao_aberta + 1

    atrasada = outra_aba.post(URL, {"acao": "anexo", "passo": "2", "revisao": revisao_aberta,
                                    "arquivo": imagem(cor="blue"), "aprendi": "Nota atrasada"},
                               HTTP_COOKIE="meshcraft_sessao=A")
    assert atrasada.status_code == 400
    assert AnexoDaJornada.objects.count() == 1

    atualizada = client.post(URL, {"acao": "anexo", "passo": "2", "revisao": revisao_nova,
                                   "arquivo": imagem(), "aprendi": "Nota da primeira aba"},
                              HTTP_COOKIE="meshcraft_sessao=A")
    assert atualizada.status_code == 200
    assert atualizada.json()["revisao"] == revisao_nova + 1
    atrasada = outra_aba.post(URL, {"acao": "anexo", "passo": "2", "revisao": revisao_nova,
                                    "arquivo": imagem(), "aprendi": "Sobrescrever pela segunda aba"},
                               HTTP_COOKIE="meshcraft_sessao=A")
    assert atrasada.status_code == 400
    anexo = AnexoDaJornada.objects.get()
    assert anexo.id == anexo_id and anexo.aprendi == "Nota da primeira aba"
    assert abrir(outra_aba).json()["anexos"][0]["aprendi"] == "Nota da primeira aba"


def test_inicio_continua_editavel_depois_da_faixa_branca(client, monkeypatch):
    monkeypatch.setattr("apps.core.views.quem_e", lambda request: P)
    antes = client.get(reverse("base")).content.decode()
    assert 'id="inicio-cartao"' in antes
    assert 'id="inicio-retomar"' in antes
    assert guardar(client, "inicio-motivo", motivo="ugc").status_code == 200
    assert guardar(client, "inicio-plano", objetivo="Criar meu item",
                   compromisso="Praticar esta semana", assumir="sim").status_code == 200
    assert guardar(client, "inicio-item").status_code == 200
    assert guardar(client, "anexo", passo="2", arquivo=imagem()).status_code == 200
    assert guardar(client, "declaracao", passo="2", estado="feito").status_code == 200
    depois = client.get(reverse("base")).content.decode()
    assert 'id="inicio-cartao"' in depois
    assert 'id="inicio-retomar"' in depois


def test_outro_motivo_e_etapa_sao_privados_retomaveis_sem_credito_no_rascunho(client, monkeypatch):
    r = guardar(client, 'inicio-motivo', motivo='outro', motivo_outro='Meu motivo privado',
                motivo_pessoal='', motivo_etapa='2', concluir='nao')
    assert r.status_code == 200
    assert 'conquista_xp' not in r.json()
    assert r.json()['inicio']['etapas'][1]['bloqueada'] is True
    retomada = abrir(Client()).json()['inicio']
    assert retomada['motivo_outro'] == 'Meu motivo privado'
    assert retomada['motivo_etapa'] == 2
    concluida = guardar(client, 'inicio-motivo', motivo='outro', motivo_pessoal='', concluir='sim')
    assert concluida.json()['conquista_xp'] == 100
    assert concluida.json()['inicio']['motivo_outro'] == 'Meu motivo privado'
    assert guardar(client, 'inicio-motivo', motivo='outro', concluir='sim').json()['conquista_xp'] == 0
    monkeypatch.setattr('apps.core.inventario._sessao', lambda cookie: {'autenticado': True, 'id': 'outra-conta'})
    assert 'Meu motivo privado' not in str(abrir(client).json())


@pytest.mark.parametrize("etapa", (1, 2, 3))
@pytest.mark.parametrize("faixa_completa", (False, True))
def test_revisar_motivo_e_voltar_preserva_conclusao_pontos_e_faixa(client, etapa, faixa_completa):
    assert guardar(client, "inicio-motivo", motivo="ugc").status_code == 200
    if faixa_completa:
        liberar_envio(client)
        assert guardar(client, "anexo", passo="2", arquivo=imagem()).status_code == 200
        assert guardar(client, "declaracao", passo="2", estado="feito").status_code == 200
    antes = abrir(client).json()
    xp_antes = PerfilJogador.objects.get(pessoa_id=P, site_id=SITE).xp_total
    resposta = guardar(client, "inicio-motivo", motivo="jogo", motivo_pessoal="Meu novo motivo",
                       motivo_etapa=str(etapa), concluir="nao")
    assert resposta.status_code == 200
    dados = resposta.json()
    assert dados["inicio"]["motivo"] == "jogo"
    assert dados["inicio"]["motivo_pessoal"] == "Meu novo motivo"
    assert dados["inicio"]["etapas"][0]["concluida"] is True
    assert dados["inicio"]["etapas"][1]["liberada"] is True
    assert dados["atual_ordem"] == antes["atual_ordem"]
    assert "conquista_url" not in dados
    assert PerfilJogador.objects.get(pessoa_id=P, site_id=SITE).xp_total == xp_antes
    assert abrir(Client()).json()["inicio"]["etapas"][0]["concluida"] is True


def test_motivo_com_xp_e_marcacao_antiga_de_rascunho_reconhece_conclusao_sem_reescrever_dados(client):
    assert guardar(client, "inicio-motivo", motivo="ugc").status_code == 200
    jornada = JornadaPessoal.objects.get(pessoa_id=P, site_id=SITE)
    jornada.inicio.update(motivo="jogo", motivo_rascunho=True, motivo_etapa=2)
    jornada.save(update_fields=["inicio"])
    inicio_antes, revisao_antes = dict(jornada.inicio), jornada.revisao
    dados = abrir(client).json()
    assert dados["inicio"]["etapas"][0]["concluida"] is True
    assert dados["inicio"]["etapas"][1]["liberada"] is True
    jornada.refresh_from_db()
    assert jornada.inicio == inicio_antes and jornada.revisao == revisao_antes
    assert PerfilJogador.objects.get(pessoa_id=P, site_id=SITE).xp_total == 100


def test_sonhos_multiplos_retomam_em_privado_e_nao_antecipam_xp(client, monkeypatch):
    sonhos = ['pc_gamer', 'ajudar_pais', 'jogo_roblox']
    dados = dict(motivo='ugc', motivo_pessoal='Meu motivo', motivo_sonhos=json.dumps(sonhos), motivo_etapa='3')
    resposta = guardar(client, 'inicio-motivo', concluir='nao', **dados)
    assert resposta.status_code == 200
    assert 'conquista_xp' not in resposta.json()
    assert resposta.json()['inicio']['etapas'][1]['bloqueada'] is True
    inicio = abrir(Client()).json()['inicio']
    assert inicio['motivo_sonhos'] == sonhos and inicio['motivo_etapa'] == 3
    assert len(inicio['sonhos_opcoes']) == 25
    assert 'motivo_sonhos' not in _projecao(HttpResponse(), P, SITE).model_dump_json()
    concluida = guardar(client, 'inicio-motivo', concluir='sim', **dados).json()
    assert concluida['conquista_xp'] == 100
    assert guardar(client, 'inicio-motivo', concluir='sim', **dados).json()['conquista_xp'] == 0
    monkeypatch.setattr('apps.core.inventario._sessao', lambda cookie: {'autenticado': True, 'id': 'outra-conta'})
    assert not abrir(client).json()['inicio'].get('motivo_sonhos')
    monkeypatch.setattr('apps.core.inventario._sessao', lambda cookie: {'autenticado': True, 'id': P})
    monkeypatch.setenv('SITE_ID', 'outra-escola')
    assert not abrir(client).json()['inicio'].get('motivo_sonhos')


def test_sonhos_editaveis_e_cliente_antigo_preserva_escolhas_e_sonho_anterior(client):
    assert guardar(client, 'inicio-motivo', motivo='ugc', motivo_sonhos='["pc_gamer", "pc_gamer", "viagens"]').status_code == 200
    assert guardar(client, 'inicio-plano', sonho='Meu sonho escrito anteriormente').status_code == 200
    assert guardar(client, 'inicio-motivo', motivo='jogo', concluir='nao').status_code == 200
    inicio = abrir(client).json()['inicio']
    assert inicio['motivo_sonhos'] == ['pc_gamer', 'viagens']
    assert inicio['sonho'] == 'Meu sonho escrito anteriormente'
    resposta = guardar(client, 'inicio-motivo', motivo='jogo', motivo_sonhos='[]', motivo_etapa='3', concluir='nao')
    assert resposta.status_code == 200
    assert resposta.json()['inicio']['motivo_sonhos'] == []
    assert resposta.json()['inicio']['etapas'][0]['concluida'] is True
    assert PerfilJogador.objects.get(pessoa_id=P, site_id=SITE).xp_total == 100


@pytest.mark.parametrize('valor', ['{', '{}', '["inexistente"]', '[{}]'])
def test_sonhos_invalidos_nao_sobrescrevem_registro(client, valor):
    assert guardar(client, 'inicio-motivo', motivo='ugc', motivo_sonhos='["pc_gamer"]').status_code == 200
    resposta = guardar(client, 'inicio-motivo', motivo='jogo', motivo_sonhos=valor)
    assert resposta.status_code == 400
    inicio = abrir(client).json()['inicio']
    assert inicio['motivo'] == 'ugc' and inicio['motivo_sonhos'] == ['pc_gamer']
