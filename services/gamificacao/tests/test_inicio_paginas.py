"""O começo ocupa quatro páginas privadas; a Base aponta a primeira pendência."""

import pytest
from django.test import Client, override_settings
from django.urls import get_script_prefix, reverse, set_script_prefix

from apps.gamificacao.models import JornadaPessoal


pytestmark = pytest.mark.django_db
SITE, P = "site-paginas", "aluna-paginas"
ETAPAS = ("inicio-motivo", "inicio-objetivo", "inicio-item", "inicio-envio")


@pytest.fixture(autouse=True)
def conta(monkeypatch):
    monkeypatch.setenv("SITE_ID", SITE)
    monkeypatch.setattr("apps.core.views.quem_e", lambda request: P)
    monkeypatch.setattr("apps.core.inventario._sessao", lambda cookie: {"autenticado": True, "id": P})
    monkeypatch.setattr("apps.gamificacao.avaliacao_inicio.avaliar", lambda *args, **kwargs: {
        "resultado": "reconhecida", "feedback": "A realização foi examinada.", "evidencia": {"teste": True}})


def guardar(client, acao, **dados):
    url = reverse("inventario")
    if acao == 'inicio-motivo':
        dados.setdefault('concluir', 'sim')
    revisao = client.get(url, HTTP_COOKIE="meshcraft_sessao=A").json()["revisao"]
    return client.post(url, {"acao": acao, "revisao": revisao, **dados}, HTTP_COOKIE="meshcraft_sessao=A")


def test_tarefa_exibe_apenas_seu_xp_e_entrega_faixa_para_cerimonia_separada(client):
    from apps.gamificacao.bonus_faixas import configurar
    configurar(SITE)
    guardar(client, 'inicio-motivo', motivo='ugc')
    premio = guardar(client, 'inicio-compromisso', assumir='sim', proximo_passo='criar_item').json()
    resposta = client.get(premio['conquista_url'])
    corpo = resposta.content.decode()
    assert 'data-xp="100"' in corpo
    assert 'data-xp="5100"' not in corpo
    assert 'XP DA TAREFA' in corpo and 'Ver minha conquista' in corpo
    assert '100 XP da tarefa + 5000' not in corpo
    assert resposta.context['cerimonia_faixa']['celebracao']['bonus_xp'] == 5000


@pytest.mark.parametrize("ordem,nome", enumerate(ETAPAS, start=1))
def test_cada_etapa_tem_rota_pagina_e_formulario_proprios(client, ordem, nome):
    if ordem > 1:
        assert guardar(client, "inicio-motivo", motivo="ugc").status_code == 200
    if ordem > 2:
        assert guardar(client, "inicio-compromisso", assumir="sim", proximo_passo="criar_item").status_code == 200
    if ordem > 3:
        assert guardar(client, "inicio-item", item_nome="Minha peça", item_acao="Modelei a forma").status_code == 200
    url = reverse(nome)
    assert url == ("/trilha/inicio/motivo/", "/trilha/inicio/objetivo/", "/trilha/inicio/item/", "/trilha/inicio/envio/")[ordem - 1]
    r = client.get(url)
    assert r.status_code == 200
    assert r.context["entrou"] is True and r.context["inicio_etapa"] == ordem
    assert r.context["inicio_titulo"]
    assert r.context["faixas"]
    assert "gamificacao/inicio_pagina.html" in [t.name for t in r.templates]
    corpo = r.content.decode()
    assert 'id="inicio-jornada"' in corpo
    assert corpo.count("<form") == 1
    assert "private" in r["Cache-Control"] and "no-store" in r["Cache-Control"]
    assert r["X-Robots-Tag"] == "noindex, nofollow"
    assert 'name="sonho"' not in corpo
    assert ('id="inicio-form-compromisso"' in corpo) is (ordem == 2)
    assert ("id=\"inicio-pedir-ajuda\"" in corpo) is (ordem == 3)


def test_compromisso_embutido_tem_duas_acoes_e_confirmacao_privada(client):
    assert guardar(client, 'inicio-motivo', motivo='jogo').status_code == 200
    resposta = client.get(reverse('inicio-objetivo') + '?embutido=1')
    assert resposta.status_code == 200
    assert 'gamificacao/inicio_embutido.html' in [t.name for t in resposta.templates]
    corpo = resposta.content.decode()
    for texto in ('Eu sei por que comecei.', 'Eu vou até o fim.', 'Meu compromisso está assumido.', 'Eu assumo. Vou até o fim.'):
        assert texto in corpo
    assert 'name="objetivo"' not in corpo and 'name="obstaculo"' not in corpo
    assert 'inicio-proximo-passo' not in corpo
    assert 'Vamos conferir seu motivo' not in corpo
    assert 'Meu compromisso é com a minha decisão.' not in corpo
    assert 'private' in resposta['Cache-Control'] and 'no-store' in resposta['Cache-Control']
    assert not JornadaPessoal.objects.get().inicio.get('compromisso_curso_em')


def test_visitante_encontra_convite_sem_dados_privados(client, monkeypatch):
    assert guardar(client, "inicio-motivo", motivo="ugc").status_code == 200
    assert guardar(client, "inicio-plano", sonho="SONHO-PRIVADO-ALFA", objetivo="OBJETIVO-PRIVADO-ALFA").status_code == 200
    monkeypatch.setattr("apps.core.views.quem_e", lambda request: None)
    antiga = client.get(reverse("base"))
    assert antiga.status_code == 302 and antiga["Location"] == "/trilha/"
    for nome in ETAPAS:
        r = client.get(reverse(nome))
        corpo = r.content.decode()
        assert r.status_code == 200 and "Entrar na escola" in corpo
        assert "SONHO-PRIVADO-ALFA" not in corpo and "OBJETIVO-PRIVADO-ALFA" not in corpo
        assert 'id="inicio-jornada"' not in corpo


def test_cartao_retoma_primeiro_passo_pendente_sem_expor_plano(client):
    base = reverse("base")
    corpo = client.get(base).content.decode()
    assert 'id="inicio-cartao"' not in corpo
    assert client.get(reverse("inicio-motivo")).status_code == 200

    assert guardar(client, "inicio-motivo", motivo="ugc", motivo_pessoal="MOTIVO-PRIVADO-ALFA").status_code == 200
    assert client.get(reverse("inicio-objetivo")).status_code == 200
    assert client.get(reverse("inicio-item")).url == reverse("inicio-objetivo")
    assert guardar(client, "inicio-plano", sonho="SONHO-PRIVADO-ALFA", objetivo="OBJETIVO-PRIVADO-ALFA",
                   compromisso="COMPROMISSO-PRIVADO-ALFA", assumir="sim").status_code == 200
    assert guardar(client, "inicio-compromisso", assumir="sim", proximo_passo="criar_item").status_code == 200
    corpo = client.get(base).content.decode()
    assert client.get(reverse("inicio-item")).status_code == 200
    for segredo in ("SONHO-PRIVADO-ALFA", "OBJETIVO-PRIVADO-ALFA", "COMPROMISSO-PRIVADO-ALFA", "MOTIVO-PRIVADO-ALFA"):
        assert segredo not in corpo

    # Concluir a entrega mantém as páginas acessíveis para releitura e edição.
    from django.core.files.uploadedfile import SimpleUploadedFile
    arquivo = SimpleUploadedFile("item.obj", b"v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n")
    assert guardar(client, "inicio-item", item_nome="Minha peça", item_acao="Modelei a forma").status_code == 200
    assert client.get(reverse("inicio-envio")).status_code == 200
    assert guardar(client, "inicio-envio", arquivo=arquivo).status_code == 200
    corpo = client.get(base).content.decode()
    assert 'id="inicio-cartao"' not in corpo
    assert client.get(reverse("inicio-motivo")).status_code == 200
    assert client.get(reverse("inicio-item")).status_code == 200
    assert guardar(client, "inicio-motivo", motivo="jogo").status_code == 200


def test_paginas_nao_perdem_registro_e_respeitam_pessoa_e_site(client, monkeypatch):
    assert guardar(client, "inicio-motivo", motivo="aprender", motivo_pessoal="Minha razão").status_code == 200
    assert guardar(client, "inicio-plano", sonho="Sonho reservado", objetivo="Minha peça").status_code == 200
    salvo = JornadaPessoal.objects.get(pessoa_id=P, site_id=SITE)
    for nome in ETAPAS[:2]:
        assert client.get(reverse(nome)).status_code == 200
    for nome in ETAPAS[2:]:
        assert client.get(reverse(nome)).url == reverse("inicio-objetivo")
    salvo.refresh_from_db()
    assert salvo.inicio["sonho"] == "Sonho reservado" and salvo.inicio["motivo"] == "aprender"
    assert client.get(reverse("inventario"), HTTP_COOKIE="meshcraft_sessao=A").json()["inicio"]["objetivo"] == "Minha peça"

    monkeypatch.setattr("apps.core.views.quem_e", lambda request: "outro-aluno")
    antiga = client.get(reverse("base"))
    assert antiga.status_code == 302 and antiga["Location"] == "/trilha/"
    for nome in ETAPAS:
        assert "Sonho reservado" not in client.get(reverse(nome)).content.decode()
    monkeypatch.setattr("apps.core.views.quem_e", lambda request: P)
    monkeypatch.setenv("SITE_ID", "outro-site")
    antiga = client.get(reverse("base"))
    assert antiga.status_code == 302 and antiga["Location"] == "/trilha/"
    for nome in ETAPAS:
        assert "Sonho reservado" not in client.get(reverse(nome)).content.decode()
    assert JornadaPessoal.objects.filter(pessoa_id=P, site_id=SITE).count() == 1


def test_links_entre_paginas_respeitam_prefixo_publico(client):
    prefixo_anterior = get_script_prefix()
    try:
        with override_settings(FORCE_SCRIPT_NAME="/prefixo"):
            set_script_prefix("/prefixo/")
            r = client.get("/trilha/inicio/motivo/", SCRIPT_NAME="/prefixo")
            assert r.status_code == 200
            corpo = r.content.decode()
            assert '/trilha/inicio/objetivo/' not in corpo
            assert '/prefixo/trilha/inventario/api/' in corpo
    finally:
        set_script_prefix(prefixo_anterior)


def test_motivo_embutido_tem_tres_etapas_sem_saida_antiga_e_comprovante_no_mesmo_painel(client):
    resposta = client.get(reverse('inicio-motivo') + '?embutido=1')
    html = resposta.content.decode()
    assert resposta.status_code == 200
    assert 'gamificacao/inicio_embutido.html' in [t.name for t in resposta.templates]
    assert 'data-embutido="sim"' in html
    assert 'id="inicio-motivo-reflexao" hidden' in html
    assert 'id="inicio-motivo-sonhos" hidden' in html
    assert 'Etapa 1 de 3' in html
    assert html.count('>Continuar</button>') == 2
    assert html.count('>Concluir meu motivo</button>') == 1
    assert 'name="motivo_outro"' in html
    assert 'Depois eu faço isso' in html
    assert 'Sair e retomar depois' not in html
    assert 'Salvar para continuar depois' not in html
    assert 'private' in resposta['Cache-Control']
    credito = guardar(client, 'inicio-motivo', motivo='ugc').json()
    comprovante = client.get(credito['conquista_url'] + '&embutido=1')
    assert comprovante.status_code == 200
    assert comprovante.context['conquista_xp'] == 100
    assert 'data-embutido="sim"' in comprovante.content.decode()
    assert client.get(reverse('inicio-conquista', args=[1]) + '?embutido=1').context['conquista_xp'] == 0


@pytest.mark.parametrize("ordem,nome", enumerate(ETAPAS, start=1))
def test_etapas_no_modal_devolvem_so_componente_nativo(client, ordem, nome):
    if ordem > 1:
        guardar(client, "inicio-motivo", motivo="ugc")
    if ordem > 2:
        guardar(client, "inicio-compromisso", assumir="sim", proximo_passo="criar_item")
    if ordem > 3:
        guardar(client, "inicio-item", item_nome="Minha peça", item_acao="Modelei a forma")
    antes = list(JornadaPessoal.objects.values())
    resposta = client.get(reverse(nome), HTTP_X_TRILHA_PAINEL="1")
    assert resposta.status_code == 200
    dados = resposta.json()
    assert dados["componente"] == "trilha" and dados["controlador"] == "inicio"
    assert 'id="inicio-jornada"' in dados["html"]
    for proibido in ("<!doctype", "<html", "<body", "<iframe", "<script"):
        assert proibido not in dados["html"].lower()
    assert "X-Trilha-Painel" in resposta["Vary"]
    assert "no-store" in resposta["Cache-Control"]
    assert list(JornadaPessoal.objects.values()) == antes


@pytest.mark.parametrize("caminho", ("ugc", "jogo", "aprender"))
@pytest.mark.parametrize("ordem", (5, 6, 7))
def test_todas_as_etapas_do_ciclo_sao_componentes(client, monkeypatch, caminho, ordem):
    from apps.gamificacao.models import Pessoa
    Pessoa.objects.get_or_create(id_da_plataforma=P, defaults={"email": "aluna@example.test", "nome_exibido": "Aluna"})
    JornadaPessoal.objects.create(pessoa_id=P, site_id=SITE, inicio={"item_nome": "Minha peça"})
    monkeypatch.setattr("apps.gamificacao.jornada.situacao", lambda *args: {
        "caminho": caminho, "proxima": {"ordem": ordem, "nome": "Próxima faixa"}})
    resposta = client.get(reverse("ciclo"), HTTP_X_TRILHA_PAINEL="1")
    assert resposta.status_code == 200
    dados = resposta.json()
    assert dados["controlador"] == "ciclo"
    assert 'id="ciclo-form"' in dados["html"]
    assert '<iframe' not in dados["html"] and '<html' not in dados["html"]
    assert '<script' not in dados["html"]


def test_modal_nao_entrega_formulario_privado_ao_visitante(client, monkeypatch):
    monkeypatch.setattr("apps.core.views.quem_e", lambda request: None)
    resposta = client.get(reverse("inicio-motivo"), HTTP_X_TRILHA_PAINEL="1")
    assert resposta.status_code == 403 and "html" not in resposta.json()


def test_recebimentos_e_erros_de_meta_permanecem_componentes(client):
    resposta = client.get(reverse("recebimentos"), HTTP_X_TRILHA_PAINEL="1")
    assert resposta.status_code == 200 and resposta.json()["controlador"] == "formularios"
    erro = client.post(reverse("recebimentos"), {"acao": "preview-meta", "meta": "0"}, HTTP_X_TRILHA_PAINEL="1")
    assert erro.status_code == 400
    assert 'role="alert"' in erro.json()["html"]
    assert '<html' not in erro.json()["html"]
