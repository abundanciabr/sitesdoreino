import pytest
from django.http import Http404
from django.test import RequestFactory
from apps.core import medalhas


def pedido(metodo="get", **dados):
    r = getattr(RequestFactory(), metodo)("/escola/alunos/medalhas/", {
        "email": "aluna@example.test", "site_id": "escola", **dados,
    })
    r.admin = {"id": "admin-1", "nome": "Admin", "email": "admin@example.test"}
    return r


@pytest.fixture
def ambiente(monkeypatch):
    monkeypatch.setattr(medalhas.AlunosClient, "prontuario", lambda self, email: {
        "nome_completo": "Aluna", "passagens": [{"site_id": "escola"}],
    })
    monkeypatch.setattr(medalhas, "_identidade", lambda email: "pessoa-real")
    monkeypatch.setattr(medalhas, "_medalhas", lambda *args: {"medalhas": []})


def test_get_prepara_formulario_sem_conceder(ambiente, monkeypatch):
    chamadas = []
    monkeypatch.setattr(medalhas, "_medalhas", lambda *args: chamadas.append(args) or {"medalhas": []})
    resposta = medalhas.painel(pedido())
    assert resposta.status_code == 200
    assert all(len(a) == 2 for a in chamadas)
    assert "Dar medalha ao aluno" in resposta.content.decode()


def test_nota_10_verificada_sugere_mensagem_sem_conceder(ambiente, monkeypatch):
    monkeypatch.setattr(medalhas.NPSClient, "historico", lambda self, *args, **kwargs: ("ok", {
        "avaliacoes": [{"id": "aval-1", "aluno": {"email": "aluna@example.test"}}],
    }))
    monkeypatch.setattr(medalhas, "preparar_painel", lambda a: {"nota": 10})
    html = medalhas.painel(pedido(avaliacao="aval-1")).content.decode()
    assert "Nota 10 na Pesquisa" in html and medalhas.MENSAGEM_EMBAIXADOR in html


def test_nao_confia_em_avaliacao_de_outro_email(ambiente, monkeypatch):
    monkeypatch.setattr(medalhas.NPSClient, "historico", lambda self, *args, **kwargs: ("ok", {
        "avaliacoes": [{"id": "aval-1", "aluno": {"email": "outra@example.test"}}],
    }))
    chamadas = []
    monkeypatch.setattr(medalhas, "_medalhas", lambda *args: chamadas.append(args))
    html = medalhas.painel(pedido("post", avaliacao="aval-1", nome="Embaixador", mensagem="Parabéns")).content.decode()
    assert "Não foi possível conferir esta avaliação" in html and not chamadas


def test_post_usa_identidade_resolvida_e_autor_autenticado(ambiente, monkeypatch):
    chamadas = []
    monkeypatch.setattr(medalhas, "_medalhas", lambda *args: chamadas.append(args) or {"medalha": {"id": 7}, "nova": True})
    resposta = medalhas.painel(pedido("post", pessoa_id="forjado", quem_id="forjado",
                                    nome="Embaixador", mensagem="Parabéns!"))
    assert resposta.status_code == 302 and "concedida=7" in resposta["Location"]
    assert chamadas[0][:2] == ("escola", "pessoa-real")
    assert chamadas[0][2]["quem_id"] == "admin-1"


def test_falha_de_envio_nao_finge_sucesso(ambiente, monkeypatch):
    monkeypatch.setattr(medalhas, "_medalhas", lambda *args: None)
    r = medalhas.painel(pedido("post", nome="Embaixador", mensagem="Parabéns"))
    assert r.status_code == 200 and "Não foi possível confirmar a concessão" in r.content.decode()


def test_equipe_e_robo_nao_concedem(ambiente):
    for papel in ("equipe_apenas", "robo"):
        r = pedido("post", nome="Embaixador", mensagem="Parabéns")
        r.admin[papel] = True
        assert medalhas.painel(r).status_code == 403


def test_outro_site_nao_concede(ambiente):
    with pytest.raises(Http404):
        medalhas.painel(pedido("post", site_id="outra", nome="Embaixador", mensagem="Parabéns"))


def test_previa_sem_efeitos_e_texto_escapado(ambiente, monkeypatch):
    def nao_chamar(*args):
        raise AssertionError("Prévia não consulta nem concede")
    monkeypatch.setattr(medalhas, "_medalhas", nao_chamar)
    r = medalhas.previa(pedido(nome="</script><script>alert(1)</script>"))
    html = r.content.decode()
    assert r.status_code == 200 and "</script><script>alert" not in html
    assert '"previa": true' in html
