import uuid

from django.test import Client
from django.urls import resolve

from apps.core import galeria_comunidade as galeria
from apps.core.galeria_aula1 import BASE, IMAGENS
from apps.core.galeria_models import ComentarioDaGaleria, VotoDaGaleria


def test_previa_publica_tem_seis_cenas_em_ordem_e_enderecos_do_curso(client, monkeypatch):
    monkeypatch.setattr(galeria, "aluno", lambda request: None)
    VotoDaGaleria.objects.create(pessoa_id="teste", imagem=IMAGENS[-1][0])
    resposta = client.get("/previa-aula-1")
    texto = resposta.content.decode()
    assert resposta.status_code == 200
    assert texto.count('class="modelo"') == 6
    assert [texto.index('data-slug="' + i[0] + '"') for i in IMAGENS] == sorted(
        texto.index('data-slug="' + i[0] + '"') for i in IMAGENS
    )
    assert BASE + "/galeria.js" in texto and BASE + "/imagens/aula1-abertura" in texto
    assert "/comunidade/aula-1" not in texto
    assert resolve("/galeria-publica/aula-1").func is galeria.recurso


def test_voto_da_previa_nao_se_mistura_com_comunidade_nem_reordena_cenas(client, monkeypatch):
    monkeypatch.setattr(galeria, "aluno", lambda request: {"id": "teste", "nome": "Teste", "email": "teste@example.invalid"})
    for _ in range(2):
        resposta = client.post("/previa-aula-1/voto", {"imagem": IMAGENS[-1][0], "acao": "votar"})
        assert resposta.status_code == 200
    assert [i["slug"] for i in resposta.json()["imagens"]] == [i[0] for i in IMAGENS]
    assert VotoDaGaleria.objects.count() == 1
    assert client.post("/previa-aula-1/voto", {"imagem": "apple", "acao": "votar"}).status_code == 400
    assert client.post("/galeria-publica/voto", {"imagem": IMAGENS[-1][0], "acao": "votar"}).status_code == 400
    assert all(i["votos"] == 0 for i in galeria.classificacao())


def test_comentario_da_cena_identificado_sem_publicar_dados(client, monkeypatch):
    pessoa = {"id": "teste", "nome": "Nome da sessão", "email": "teste@example.invalid"}
    monkeypatch.setattr(galeria, "aluno", lambda request: pessoa)
    campos = {"imagem": IMAGENS[0][0], "texto": "Comentário de teste", "chave": str(uuid.uuid4()), "nome": "Nome falso"}
    for _ in range(2):
        assert client.post("/previa-aula-1/comentario", campos).status_code == 200
    comentario = ComentarioDaGaleria.objects.get()
    assert comentario.nome == pessoa["nome"]
    assert comentario.imagem == IMAGENS[0][0]
    texto = client.get("/previa-aula-1").content.decode()
    assert campos["texto"] not in texto and pessoa["email"] not in texto


def test_csrf_da_previa_no_curso_e_imagem_com_nome_permitido(monkeypatch, tmp_path):
    monkeypatch.setattr(galeria, "aluno", lambda request: None)
    cliente = Client(enforce_csrf_checks=True)
    pagina = cliente.get("/previa-aula-1")
    assert pagina.cookies["admin_csrf"]["path"] == BASE
    assert cliente.post("/previa-aula-1/voto", {"imagem": IMAGENS[0][0], "acao": "votar"}).status_code == 403
    monkeypatch.setenv("COMUNIDADE_GALERIA_DIR", str(tmp_path))
    (tmp_path / (IMAGENS[0][0] + ".png")).write_bytes(b"imagem-de-teste")
    assert cliente.get("/previa-aula-1/imagens/" + IMAGENS[0][0]).status_code == 200
    assert cliente.get("/previa-aula-1/imagens/apple").status_code == 404
