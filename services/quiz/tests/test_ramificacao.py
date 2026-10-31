"""Caminhos reais, preservação do fluxo antigo e rejeição de estado adulterado."""
from unittest.mock import patch

import pytest
from django.core import signing
from apps.quiz.conteudo import conferir_documento, importar_documento
from apps.quiz.models import Submission
from apps.quiz.previa import _pontuar
from apps.quiz.ramificacao import FIM, conferir_caminhos
from apps.quiz.views import COOKIE_SESSAO, SALT_SESSAO
from tests.test_importar_quiz import documento, site  # noqa: F401
from tests.test_conversa import ClienteDuble, abrir, enviar, concluir

pytestmark = pytest.mark.django_db


@pytest.fixture
def ramificado(documento, site):
    v = documento["versoes"][0]
    v["perguntas"][0]["opcoes"][1]["proxima"] = FIM
    v["formats"]["ai"] = {"headline": "Converse", "subheadline": "Teste", "instructions": "Interprete a resposta."}
    return importar_documento(documento, site)


def entrada(client, quiz):
    cookie = signing.loads(client.cookies[COOKIE_SESSAO].value, salt=SALT_SESSAO)
    return cookie["quizzes"][quiz.slug]


def responder(client, quiz, tela, **dados):
    return client.post(f"/{quiz.slug}/", {"quiz_attempt": entrada(client, quiz)["session_id"], "estado_ramo": tela.context["estado_ramo"], **dados}, HTTP_HOST=quiz.site.host)


def test_pontuacao_considera_somente_caminho(documento):
    v = documento["versoes"][0]
    v["perguntas"][0]["opcoes"][1]["proxima"] = FIM
    assert conferir_caminhos(v) == {0, 2, 3}
    assert _pontuar(v, {"momento": "avanco", "ritmo": "rapido"}) == 2
    conferir_documento(documento)


def test_salto_para_pergunta_posterior_e_conferencia(documento, site):
    from apps.quiz.conferencia import _conferir_versao
    from apps.quiz.ramificacao import preparar, percurso
    v = documento["versoes"][0]
    v["perguntas"].insert(1, {"id": "pulada", "texto": "Pergunta de outro caminho", "opcoes": [{"id": "a", "texto": "A", "pontos": 100}, {"id": "b", "texto": "B", "pontos": 200}]})
    for o in v["perguntas"][0]["opcoes"]:
        o["proxima"] = "ritmo"
    q = importar_documento(documento, site)
    perguntas = preparar(q.versions.get())
    caminho, atual = percurso(perguntas, {str(perguntas[0].id): perguntas[0].options.first().id})
    assert atual.id == perguntas[2].id
    assert [p.id for p in caminho] == [perguntas[0].id, perguntas[2].id]
    assert _pontuar(v, {"momento": "inicio", "ritmo": "rapido", "pulada": "b"}) == 3
    from apps.quiz.conferencia import _somas_possiveis
    assert set(_somas_possiveis(perguntas)) == {0, 2, 3, 5}


def test_metricas_nao_inventam_visita_ao_ramo_pulado():
    from apps.quiz.campanhas import funil_de_versao
    s = {"id": "um", "teste": False, "viu": {"1", "3"}, "clicou": {"1", "3"}, "abandonou": set(), "concluiu": True, "respondidas": {"1", "3"}, "saida": False, "saida_real": False}
    resultado = funil_de_versao("B2", [s], [("1", "Início"), ("2", "Outro caminho"), ("3", "Final")], ramificado=True)
    linhas = resultado["etapas"]
    assert next(e for e in linhas if e["etapa"] == "2")["viram"] == 0
    assert next(e for e in linhas if e["etapa"] == "1")["perda"] == 0


@pytest.mark.parametrize("destino", ["inexistente", "momento", 123, True])
def test_destino_invalido_nao_publica(documento, destino):
    documento["versoes"][0]["perguntas"][0]["opcoes"][0]["proxima"] = destino
    with pytest.raises(ValueError, match="proxima"):
        conferir_documento(documento)


def test_faixas_precisam_cobrir_pontuacao_do_encerramento(documento):
    v = documento["versoes"][0]
    v["perguntas"][0]["opcoes"][1].update(proxima=FIM, pontos=-5)
    with pytest.raises(ValueError, match="cobrem"):
        conferir_documento(documento)


def test_caminho_curto_grava_apenas_pergunta_respondida(client, ramificado):
    q = ramificado
    tela = client.get(f"/{q.slug}/?v=B2&src=teste", HTTP_HOST=q.site.host)
    assert tela.context["atual"].order == 1
    alternativa = q.versions.get().questions.get(order=1).options.get(order=2)
    tela = responder(client, q, tela, opcao=alternativa.id)
    assert tela.context["atual"] is None
    assert "Qual ritmo?" not in tela.content.decode()
    final = responder(client, q, tela, acao="concluir", email="ramo@example.invalid", pergunta_999="999")
    assert final.status_code == 302
    s = Submission.objects.get()
    assert s.score == 2 and s.result_key == "baixo"
    assert s.answers == {str(alternativa.question_id): alternativa.id}


def test_voltar_troca_caminho_e_rejeita_estado_de_outra_tentativa(client, ramificado):
    q = ramificado
    tela = client.get(f"/{q.slug}/?v=B2", HTTP_HOST=q.site.host)
    primeira = q.versions.get().questions.get(order=1)
    tela = responder(client, q, tela, opcao=primeira.options.get(order=2).id)
    tela = responder(client, q, tela, acao="voltar")
    assert tela.context["atual"].id == primeira.id
    tela = responder(client, q, tela, opcao=primeira.options.get(order=1).id)
    assert tela.context["atual"].order == 2
    adulterada = responder(client, q, tela, estado_ramo="falso", opcao="1")
    assert adulterada.status_code == 422
    assert not Submission.objects.exists()


def test_ia_encerra_no_ramo_sem_perguntar_etapa_pulada(client, ramificado, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "chave-de-teste")
    q = ramificado
    tela, ent = abrir(client, q)
    alternativa = q.versions.get().questions.get(order=1).options.get(order=2)
    with patch("apps.quiz.conversa._cliente", return_value=ClienteDuble([("Pergunta errada inventada", alternativa.id)])):
        tela = enviar(client, q, tela, ent, "Já estou avançando")
    assert tela.context["completo"]
    assert "Pergunta errada inventada" not in tela.content.decode()
    final = concluir(client, q, tela, ent)
    assert final.status_code == 302
    assert Submission.objects.get().score == 2


def test_ia_indisponivel_mantem_ramificacao(client, ramificado, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    q = ramificado
    tela, ent = abrir(client, q)
    assert tela.context["fallback"] and tela.context["ramificado"]
    assert "Qual ritmo?" not in tela.content.decode()
    alternativa = q.versions.get().questions.get(order=1).options.get(order=2)
    tela = client.post(f"/{q.slug}/conversa", {"quiz_attempt": ent["session_id"], "estado": tela.context["estado_token"], "acao": "opcao", "opcao": alternativa.id}, HTTP_HOST=q.site.host)
    assert tela.context["completo"]
    assert concluir(client, q, tela, ent).status_code == 302
