import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from PIL import Image

from apps.core import comunidade_entrada as comunidade
from apps.core.comunidade_modelos import PerfilDaComunidade
from apps.core.galeria_models import VotoDaGaleria


@pytest.fixture
def admin(monkeypatch, settings):
    settings.ADMIN_EMAILS = "admin@example.test"
    monkeypatch.setattr(
        "apps.core.clients.IdentidadeClient.sessao_completa",
        lambda self, cookie: {
            "autenticado": True,
            "id": "admin-real",
            "email": "admin@example.test",
            "nome_exibido": "Ana Admin",
        },
    )
    monkeypatch.setattr(
        comunidade,
        "_alunos",
        lambda request: [
            {"nome": "Bruno", "inicial": "B", "usuario": "", "perfil": None}
        ],
    )
    monkeypatch.setattr(
        comunidade,
        "_forum",
        lambda request: {"ranking": [], "conversas": [], "grupos": []},
    )
    return Client(HTTP_COOKIE="meshcraft_sessao=teste", HTTP_HOST="meshcraft.top")


def cadastrar(client, **campos):
    return client.post(
        "/galeria-publica/perfil", {"usuario": "@Ana.3D", "avatar": "azul", **campos}
    )


def test_admin_primeiro_acesso_pede_foto_e_handle_sem_criar_perfil(admin):
    pagina = admin.get("/galeria-publica")
    assert pagina.status_code == 200
    assert "Seu primeiro acesso" in pagina.content.decode()
    assert "Seu nome de usuário" in pagina.content.decode()
    assert not PerfilDaComunidade.objects.exists()
    assert (
        PerfilDaComunidade._meta.original_attrs["db_table"] == "core_perfildacomunidade"
    )
    assert "no-store" in pagina["Cache-Control"]
    assert "noindex" in pagina["X-Robots-Tag"]
    assert pagina.cookies["admin_csrf"]["path"] == "/comunidade"


def test_cadastro_persistido_entra_com_apple_e_nao_mexe_na_votacao(admin):
    VotoDaGaleria.objects.create(pessoa_id="aluno-real", imagem="premium")
    resposta = cadastrar(admin, pessoa_id="outro", email="falso@example.test")
    assert resposta.status_code == 302 and resposta.url == "/comunidade"
    perfil = PerfilDaComunidade.objects.get()
    assert (perfil.identidade_id, perfil.email, perfil.usuario, perfil.tema) == (
        "admin-real",
        "admin@example.test",
        "ana.3d",
        "apple",
    )
    assert VotoDaGaleria.objects.filter(ativo=True).count() == 1
    pagina = admin.get("/galeria-publica")
    assert pagina.status_code == 200
    corpo = pagina.content.decode()
    assert 'data-tema="apple"' in corpo
    assert "Fórum da comunidade" in corpo and "Bruno" in corpo
    assert "admin@example.test" not in corpo
    assert "Simulação com dados fictícios" not in corpo
    assert "O ranking ainda não tem alunos" in corpo
    assert admin.get("/galeria-publica?perfil=editar").status_code == 200


def test_tema_e_persistente_e_pertence_so_ao_perfil_atual(admin):
    cadastrar(admin)
    outro = PerfilDaComunidade.objects.create(
        site_host="meshcraft.top",
        identidade_id="outro",
        email="outro@example.test",
        nome="Outro",
        usuario="outro",
        avatar="verde",
    )
    assert (
        admin.post(
            "/galeria-publica/tema", {"tema": "premium", "perfil_id": outro.pk}
        ).status_code
        == 302
    )
    assert PerfilDaComunidade.objects.get(identidade_id="admin-real").tema == "premium"
    outro.refresh_from_db()
    assert outro.tema == "apple"
    assert 'data-tema="premium"' in admin.get("/galeria-publica").content.decode()
    assert admin.post("/galeria-publica/tema", {"tema": "inventado"}).status_code == 404


def test_nome_repetido_e_normalizacao_nao_trocam_o_dono(admin):
    outro = PerfilDaComunidade.objects.create(
        site_host="meshcraft.top",
        identidade_id="outro",
        email="outro@example.test",
        nome="Outro",
        usuario="ana.3d",
        avatar="verde",
    )
    assert cadastrar(admin).status_code == 409
    assert PerfilDaComunidade.objects.count() == 1
    outro.refresh_from_db()
    assert outro.identidade_id == "outro"


@pytest.mark.parametrize(
    "campos",
    [{"usuario": ""}, {"usuario": "a b"}, {"avatar": ""}, {"avatar": "../../segredo"}],
)
def test_perfil_incompleto_ou_invalido_nao_e_gravado(admin, campos):
    assert cadastrar(admin, **campos).status_code == 400
    assert not PerfilDaComunidade.objects.exists()


def test_foto_e_lida_pelos_bytes_e_convertida_sem_metadados(admin):
    saida = io.BytesIO()
    Image.new("RGB", (700, 450), "red").save(saida, "PNG")
    arquivo = SimpleUploadedFile(
        "qualquer-nome.png", saida.getvalue(), content_type="image/png"
    )
    assert cadastrar(admin, foto=arquivo, avatar="").status_code == 302
    perfil = PerfilDaComunidade.objects.get()
    assert perfil.foto and not perfil.avatar
    foto = admin.get(f"/galeria-publica/foto/{perfil.pk}")
    assert foto.status_code == 200 and foto["Content-Type"] == "image/jpeg"
    with Image.open(io.BytesIO(foto.content)) as imagem:
        assert imagem.size == (320, 320)
        assert not imagem.getexif()


def test_html_disfarcado_de_foto_nao_entra(admin):
    foto = SimpleUploadedFile(
        "foto.png", b"<script>roubar()</script>", content_type="image/png"
    )
    assert cadastrar(admin, foto=foto).status_code == 400
    assert not PerfilDaComunidade.objects.exists()


def test_aluno_permanece_na_galeria_e_nao_acessa_perfis_privados(monkeypatch, settings):
    settings.ADMIN_EMAILS = "admin@example.test"
    monkeypatch.setattr(
        "apps.core.clients.IdentidadeClient.sessao_completa",
        lambda self, cookie: {
            "autenticado": True,
            "id": "aluno",
            "email": "aluno@example.test",
            "nome_exibido": "Aluno",
            "papel": "admin",
        },
    )
    monkeypatch.setattr(
        "apps.core.galeria_comunidade.aluno",
        lambda request: {"id": "aluno", "nome": "Aluno", "email": "aluno@example.test"},
    )
    cliente = Client(HTTP_COOKIE="meshcraft_sessao=teste")
    corpo = cliente.get("/galeria-publica").content.decode()
    assert corpo.count('class="modelo"') == 9
    assert "Vamos nos conhecer?" not in corpo
    for caminho in (
        "/galeria-publica/avatar/azul",
        "/galeria-publica/assets/comunidade.css",
        "/galeria-publica/disponivel?usuario=ana",
        "/galeria-publica/foto/1",
    ):
        assert cliente.get(caminho).status_code == 404
    assert cadastrar(cliente).status_code == 404
    assert not PerfilDaComunidade.objects.exists()


def test_csrf_do_cadastro_atravessa_a_porta_real(admin):
    seguro = Client(enforce_csrf_checks=True, HTTP_HOST="meshcraft.top")
    seguro.cookies["meshcraft_sessao"] = "teste"
    assert cadastrar(seguro).status_code == 403
    pagina = seguro.get("/galeria-publica", secure=True)
    token = pagina.cookies["admin_csrf"].value
    seguro.cookies["admin_csrf"] = token
    assert (
        seguro.post(
            "/galeria-publica/perfil",
            {"usuario": "ana", "avatar": "azul"},
            HTTP_X_CSRFTOKEN=token,
            secure=True,
            HTTP_REFERER="https://meshcraft.top/comunidade",
        ).status_code
        == 302
    )


def test_diretorio_usa_so_ativos_reais_da_escola_sem_dados_de_contato(
    admin, monkeypatch
):
    monkeypatch.setattr(comunidade, "site_de", lambda request: "escola-a")
    linhas = [
        {
            "site_id": "escola-a",
            "status": "ativa",
            "email": "bruno@example.test",
            "nome_completo": "Bruno Real",
            "origem": "liberado",
        },
        {
            "site_id": "escola-a",
            "status": "ativa",
            "email": "bruno@example.test",
            "nome_completo": "Bruno Real",
            "origem": "liberado",
        },
        {
            "site_id": "escola-b",
            "status": "ativa",
            "email": "fora@example.test",
            "nome_completo": "Fora",
        },
        {
            "site_id": "escola-a",
            "status": "suspensa",
            "email": "pausado@example.test",
            "nome_completo": "Pausado",
        },
        {
            "site_id": "escola-a",
            "status": "ativa",
            "email": "teste@example.test",
            "nome_completo": "Teste",
            "origem": "teste",
        },
        {
            "site_id": "escola-a",
            "status": "ativa",
            "email": "admin@example.test",
            "nome_completo": "Admin",
        },
    ]
    monkeypatch.setattr(comunidade.AlunosClient, "alunos", lambda self, status: linhas)
    from django.test import RequestFactory

    request = RequestFactory().get("/galeria-publica", HTTP_HOST="meshcraft.top")
    request.admin = {"id": "admin-real", "email": "admin@example.test"}
    assert comunidade._alunos(request) == [
        {"nome": "Bruno", "inicial": "B", "perfil": None, "usuario": ""}
    ]


def test_dados_do_forum_mantem_sessao_e_links_da_comunidade(monkeypatch):
    from django.test import RequestFactory

    monkeypatch.setenv("FORUM_API_URL", "http://forum:8000/interno/")
    monkeypatch.setenv("TOKEN_FORUM", "par-interno-de-teste")
    dados = {
        "ranking": [],
        "conversas": [{"url": "/t/11"}, {"url": "/forum/t/12"}],
        "grupos": [{"url": "/a/grupo/"}],
    }

    class Resposta:
        status_code = 200

        def json(self):
            return dados

    class Fonte:
        def get(self, url, headers, timeout):
            assert url == "http://forum:8000/comunidade/quem-ajuda/dados/"
            assert headers == {
                "Cookie": "meshcraft_sessao=teste",
                "Authorization": "Bearer par-interno-de-teste",
            }
            assert timeout == 5
            return Resposta()

    monkeypatch.setattr(comunidade, "http", lambda: Fonte())
    request = RequestFactory().get(
        "/galeria-publica", HTTP_COOKIE="meshcraft_sessao=teste"
    )
    resultado = comunidade._forum(request)
    assert [c["url"] for c in resultado["conversas"]] == ["/forum/t/11", "/forum/t/12"]
    assert resultado["grupos"][0]["url"] == "/forum/a/grupo/"


def test_nome_exibido_editavel_persistido_sem_trocar_outro_perfil(admin):
    cadastrar(admin, nome="Açainite")
    outro = PerfilDaComunidade.objects.create(site_host="meshcraft.top", identidade_id="outro", email="outro@example.test", nome="Outro", usuario="outro", avatar="verde")
    pagina = admin.get("/galeria-publica?perfil=editar")
    assert 'name="nome"' in pagina.content.decode()
    assert 'value="Açainite"' in pagina.content.decode()
    assert cadastrar(admin, nome="  Açaí   Artista  ").status_code == 302
    perfil = PerfilDaComunidade.objects.get(identidade_id="admin-real")
    assert perfil.nome == "Açaí Artista"
    assert perfil.usuario == "ana.3d"
    assert "Açaí Artista" in admin.get("/galeria-publica").content.decode()
    assert cadastrar(admin).status_code == 302
    perfil.refresh_from_db()
    assert perfil.nome == "Açaí Artista"
    outro.refresh_from_db()
    assert outro.nome == "Outro"


def test_nome_invalido_nao_sobrescreve_perfil_e_preserva_formulario(admin):
    cadastrar(admin, nome="Açainite")
    for nome in (" ", "a" * 121):
        resposta = cadastrar(admin, nome=nome)
        assert resposta.status_code == 400
        assert PerfilDaComunidade.objects.get().nome == "Açainite"
    resposta = cadastrar(admin, nome="Nome Editado", usuario="inválido")
    assert resposta.status_code == 400
    assert 'value="Nome Editado"' in resposta.content.decode()
