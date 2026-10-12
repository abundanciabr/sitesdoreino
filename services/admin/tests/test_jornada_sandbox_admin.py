from unittest.mock import Mock, patch

import httpx
import pytest
from django.test import RequestFactory
from django.template.loader import render_to_string

from apps.atendimento import contexto, views
from apps.atendimento.models import Assunto, Conversa
from apps.core.acompanhamento_fontes import consultar_fontes
from apps.core.clients import GamificacaoClient


SITE = "escola-sandbox"
PESSOA = "aluna-1"
AVALIACAO = {
    "trabalho_id": "trabalho-1", "entrega_id": "entrega-1", "analise_id": "analise-1",
    "atualizado_em": "2026-10-11T12:00:00Z", "versao": 2, "estado": "concluida",
    "resultado": "precisa_ajustes", "explicacao": "Faltam texturas <script>alert(1)</script>",
    "justificativa": "A malha foi examinada.", "proxima_acao": "Enviar nova versão.",
    "url": "/encomendas/sandbox/trabalhos/trabalho-1/",
    "reconhecimento": {"estado": "nao_reconhecido", "texto": "Faixa ainda não concedida."},
}
CORPO = {"fonte": "gamificacao", "site_id": SITE, "pessoa_id": PESSOA,
         "avaliacoes": [AVALIACAO]}
RESUMO = {"fonte": "gamificacao", "site_id": SITE, "pessoa_id": PESSOA,
    "perfil": {"pessoa_id": PESSOA, "xp": 40, "nivel": 3,
               "ultima_atividade_em": "2026-10-11T12:00:00Z", "conquistas": []},
    "faixa": {"alcancadas": 1, "atual": {"ordem": 1, "nome": "Branca",
        "cores": ["#ffffff"], "conquista": "Primeira análise", "alcancada_em": None}},
    "sandbox": {**CORPO, "avaliacoes": [{**AVALIACAO, "reconhecimento": {
        **AVALIACAO["reconhecimento"], "origem": {"tipo": "avaliacao_sandbox_anterior",
            "versao": 2, "entrega_id": "entrega-1", "analise_id": "analise-1",
            "reconhecida_em": "2026-10-11T12:00:00Z"}}}]}}


def test_cliente_consulta_so_a_pessoa_e_site_pedidos(monkeypatch):
    monkeypatch.setenv("GAMIFICACAO_API_URL", "http://gam/api/gamificacao/")
    monkeypatch.setenv("TOKEN_GAMIFICACAO", "par-admin")
    with patch("apps.core.clients.http") as http:
        http.return_value.get.return_value = Mock(status_code=200, json=lambda: CORPO)
        dados = GamificacaoClient().jornada_sandbox(SITE, PESSOA)
        assert dados["avaliacoes"][0]["explicacao"] == AVALIACAO["explicacao"]
        assert dados["avaliacoes"][0]["entrega_id"] == "entrega-1"
        assert dados["avaliacoes"][0]["analise_id"] == "analise-1"
        args, kwargs = http.return_value.get.call_args
        assert args[0] == f"http://gam/api/gamificacao/jornada-sandbox/{SITE}/{PESSOA}"
        assert kwargs["headers"] == {"Authorization": "Bearer par-admin"}
        http.return_value.get.return_value = Mock(status_code=200,
            json=lambda: {**CORPO, "pessoa_id": "outro-aluno"})
        assert GamificacaoClient().jornada_sandbox(SITE, PESSOA) is None
        http.return_value.get.side_effect = httpx.ConnectError("indisponível")
        assert GamificacaoClient().jornada_sandbox(SITE, PESSOA) is None


def test_cliente_nao_aceita_url_externa(monkeypatch):
    monkeypatch.setenv("GAMIFICACAO_API_URL", "http://gam/api/gamificacao/")
    monkeypatch.setenv("TOKEN_GAMIFICACAO", "par-admin")
    with patch("apps.core.clients.http") as http:
        http.return_value.get.return_value = Mock(status_code=200,
            json=lambda: {**CORPO, "avaliacoes": [{**AVALIACAO, "url": "javascript:alert(1)"}]})
        assert GamificacaoClient().jornada_sandbox(SITE, PESSOA)["avaliacoes"][0]["url"] == ""


def test_cliente_preserva_explicacao_de_ate_quatro_mil_caracteres(monkeypatch):
    monkeypatch.setenv("GAMIFICACAO_API_URL", "http://gam/api/gamificacao/")
    monkeypatch.setenv("TOKEN_GAMIFICACAO", "par-admin")
    explicacao = "A" * 4000
    with patch("apps.core.clients.http") as http:
        http.return_value.get.return_value = Mock(status_code=200,
            json=lambda: {**CORPO, "avaliacoes": [{**AVALIACAO, "explicacao": explicacao}]})
        dados = GamificacaoClient().jornada_sandbox(SITE, PESSOA)
    assert dados["avaliacoes"][0]["explicacao"] == explicacao


def test_cliente_resumo_individual_valida_site_pessoa_e_faz_uma_chamada(monkeypatch):
    monkeypatch.setenv("GAMIFICACAO_API_URL", "http://gam/api/gamificacao/")
    monkeypatch.setenv("TOKEN_GAMIFICACAO", "par-admin")
    with patch("apps.core.clients.http") as http:
        http.return_value.get.return_value = Mock(status_code=200, json=lambda: RESUMO)
        dados = GamificacaoClient().resumo_aluno(SITE, PESSOA)
        assert dados["perfil"]["xp"] == 40
        assert dados["sandbox"]["avaliacoes"][0]["explicacao"] == AVALIACAO["explicacao"]
        assert http.return_value.get.call_count == 1
        args, kwargs = http.return_value.get.call_args
        assert args[0] == f"http://gam/api/gamificacao/resumo-aluno/{SITE}/{PESSOA}"
        assert kwargs["headers"] == {"Authorization": "Bearer par-admin"}
        http.return_value.get.return_value = Mock(status_code=200,
            json=lambda: {**RESUMO, "pessoa_id": "outra-pessoa"})
        assert GamificacaoClient().resumo_aluno(SITE, PESSOA) is None
        http.return_value.get.return_value = Mock(status_code=200,
            json=lambda: {**RESUMO, "sandbox": {**CORPO, "site_id": "outra-escola"}})
        assert GamificacaoClient().resumo_aluno(SITE, PESSOA) is None
        http.return_value.get.return_value = Mock(status_code=200,
            json=lambda: {**RESUMO, "perfil": {**RESUMO["perfil"], "pessoa_id": "outra-pessoa"}})
        assert GamificacaoClient().resumo_aluno(SITE, PESSOA) is None
        http.return_value.get.side_effect = httpx.ConnectError("fora do ar")
        assert GamificacaoClient().resumo_aluno(SITE, PESSOA) is None


@pytest.mark.django_db
def test_contexto_privado_mostra_mesma_explicacao_ao_abrir_conversa(monkeypatch):
    assunto = Assunto.objects.create(site_id=SITE, nome="Cursos")
    conversa = Conversa.objects.create(site_id=SITE, pessoa_id=PESSOA, nome="Aluna",
        assunto=assunto, estado="aguardando")
    monkeypatch.setattr(contexto.GamificacaoClient, "jornada_sandbox",
                        lambda self, site, pessoa: CORPO if (site, pessoa) == (SITE, PESSOA) else None)
    jornada = contexto._jornada_sandbox(conversa)
    assert jornada["avaliacoes"][0]["explicacao"] == AVALIACAO["explicacao"]
    html = render_to_string("admin/atendimento_jornada_sandbox.html", {"jornada_sandbox": jornada})
    assert "Faltam texturas" in html and "Faixa ainda não concedida" in html
    assert "entrega-1" in html and "analise-1" in html
    assert "<script>" not in html and "&lt;script&gt;" in html


@pytest.mark.django_db
def test_contexto_privado_explicita_falha_da_fonte(monkeypatch):
    assunto = Assunto.objects.create(site_id=SITE, nome="Cursos")
    conversa = Conversa.objects.create(site_id=SITE, pessoa_id=PESSOA, assunto=assunto)
    monkeypatch.setattr(contexto.GamificacaoClient, "jornada_sandbox", lambda *args: None)
    jornada = contexto._jornada_sandbox(conversa)
    html = render_to_string("admin/atendimento_jornada_sandbox.html", {"jornada_sandbox": jornada})
    assert "indisponível" in html and "não presuma conclusão" in html
    assert "concluida" not in html


@pytest.mark.django_db
def test_get_conversa_le_jornada_sem_gerar_resposta(monkeypatch):
    from apps.atendimento import gestao
    assunto = Assunto.objects.create(site_id=SITE, nome="Cursos")
    conversa = Conversa.objects.create(site_id=SITE, pessoa_id=PESSOA, nome="Aluna",
        assunto=assunto, estado="aguardando")
    requisicao = RequestFactory().get(f"/admin/atendimento/{conversa.pk}/")
    requisicao.admin = {"id": "admin-1", "nome": "Admin"}
    monkeypatch.setattr(views, "admin", lambda request: None)
    monkeypatch.setattr(views, "site", lambda request: SITE)
    monkeypatch.setattr(views, "contexto", lambda request, site: {"admin": requisicao.admin})
    monkeypatch.setattr(gestao, "contexto_conversa", lambda *args: None)
    monkeypatch.setattr(gestao, "identidade_atendente", lambda request: ("admin-1", "Admin"))
    monkeypatch.setattr(contexto, "catalogo", lambda: [])
    monkeypatch.setattr(contexto, "_jornada_sandbox", lambda c: {
        "estado": "Jornada do Sandbox consultada.", "avaliacoes": [AVALIACAO]})
    monkeypatch.setattr(views.escala, "token_tempo", lambda *args: "tempo")
    with patch.object(contexto, "preparar") as preparar:
        resposta = views.conversa_admin(requisicao, conversa.pk)
    pagina = resposta.content.decode()
    assert resposta.status_code == 200
    assert pagina.index("Faltam texturas") < pagina.index('id="resposta"')
    assert "&lt;script&gt;" in pagina and "<script>alert(1)</script>" not in pagina
    preparar.assert_not_called()


def test_ficha_indica_fonte_indisponivel_sem_inventar_conclusao(monkeypatch):
    with patch("apps.core.acompanhamento_fontes.IdentidadeClient") as identidade, \
            patch("apps.core.nps_client.NPSClient") as nps, \
            patch("apps.core.acompanhamento_fontes.GamificacaoClient") as gamificacao, \
            patch("apps.core.acompanhamento_fontes._pedir", return_value=("ok", {"id": PESSOA})), \
            patch("apps.core.acompanhamento_fontes._fonte", return_value=("sem_registro", None)):
        identidade.return_value._configuracao.return_value = ("http://identidade", "token")
        nps.return_value.historico.return_value = ("sem_registro", None)
        gamificacao.return_value.resumo_aluno.return_value = None
        fontes = consultar_fontes(SITE, "aluna@example.test")
    assert fontes["jornada_sandbox"]["estado"] == "indisponivel"
    html = render_to_string("admin/acompanhamento_fontes.html", {"fontes": fontes})
    assert "nenhuma conclusão foi presumida" in html


def test_ficha_mostra_explicacao_escapada(monkeypatch):
    with patch("apps.core.acompanhamento_fontes.IdentidadeClient") as identidade, \
            patch("apps.core.nps_client.NPSClient") as nps, \
            patch("apps.core.acompanhamento_fontes.GamificacaoClient") as gamificacao, \
            patch("apps.core.acompanhamento_fontes._pedir", return_value=("ok", {"id": PESSOA})), \
            patch("apps.core.acompanhamento_fontes._fonte", return_value=("sem_registro", None)):
        identidade.return_value._configuracao.return_value = ("http://identidade", "token")
        nps.return_value.historico.return_value = ("sem_registro", None)
        gamificacao.return_value.resumo_aluno.return_value = RESUMO
        fontes = consultar_fontes(SITE, "aluna@example.test")
    html = render_to_string("admin/acompanhamento_fontes.html", {"fontes": fontes})
    assert "Faltam texturas" in html and "Faixa ainda não concedida" in html
    assert "análise anterior do Sandbox" in html
    assert "<script>" not in html and "&lt;script&gt;" in html
