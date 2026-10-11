import pytest
from django.test import Client
from django.urls import reverse

from apps.core import sessao, telas_sandbox
from apps.encomendas import sandbox
from apps.encomendas.models import EntregaSandbox, MensagemSandbox, OutboxMarketplace
from apps.encomendas.sandbox_models import AnaliseEntregaSandbox


@pytest.fixture
def conversa(db, monkeypatch):
    contexto = {"id": "equipe-sandbox", "site": "escola-a"}
    monkeypatch.setattr(sessao, "quem_e", lambda request: contexto["id"])
    monkeypatch.setattr(sessao, "site_desta_instalacao", lambda: contexto["site"])
    monkeypatch.setenv("IDS_DO_PLANTAO", "equipe-sandbox")
    projeto = sandbox.semear_projetos(site_id="escola-a")[0]
    trabalho = sandbox.aceitar(site_id="escola-a", pessoa_id="aluno", projeto_id=projeto.pk, prazo_horas=48)
    for papel in ("aluno", "ia", "cliente", "equipe"):
        MensagemSandbox.objects.create(site_id=trabalho.site_id, participacao=trabalho,
            ator_id=papel, papel=papel, texto=f"Mensagem anterior de {papel}.")
    return trabalho, contexto


def test_limpeza_preserva_mensagens_entregas_avaliacoes_e_eventos(client, conversa):
    trabalho, _ = conversa
    outro = sandbox.aceitar(site_id=trabalho.site_id, pessoa_id="outro-aluno", projeto_id=trabalho.projeto_id, prazo_horas=48)
    MensagemSandbox.objects.create(site_id=outro.site_id, participacao=outro,
        ator_id="outro-aluno", papel="aluno", texto="Outro trabalho.")
    entrega = EntregaSandbox.objects.create(site_id=trabalho.site_id, participacao=trabalho,
        versao=1, teste_mantenedor=True, comentario="Amostra do mantenedor.")
    AnaliseEntregaSandbox.objects.create(site_id=trabalho.site_id, entrega=entrega,
        estado="concluida", resultado={"resultado": "ajustes"}, historico=[{"versao": 1}])
    mensagens = list(MensagemSandbox.objects.order_by("id").values())
    entregas = list(EntregaSandbox.objects.values())
    analises = list(AnaliseEntregaSandbox.objects.values())
    eventos = list(OutboxMarketplace.objects.values())
    antes = client.get(reverse("sandbox_trabalho", args=[trabalho.pk]))
    assert len(antes.context["mensagens"]) == 4
    assert not antes.context["mensagens_anteriores"]
    resposta = client.post(reverse("sandbox_limpar_conversa", args=[trabalho.pk]), follow=True)
    assert resposta.status_code == 200
    assert not resposta.context["mensagens"]
    assert len(resposta.context["mensagens_anteriores"]) == 4
    html = resposta.content.decode()
    assert '<details><summary>Mensagens anteriores (4)</summary>' in html
    assert 'Conversa limpa para o próximo teste.' in html
    assert list(MensagemSandbox.objects.order_by("id").values()) == mensagens
    assert list(EntregaSandbox.objects.values()) == entregas
    assert list(AnaliseEntregaSandbox.objects.values()) == analises
    assert list(OutboxMarketplace.objects.values()) == eventos
    outro.refresh_from_db()
    assert outro.mensagens_recolhidas_ate is None
    assert len(client.get(reverse("sandbox_trabalho", args=[outro.pk])).context["mensagens"]) == 1


def test_novas_respostas_aparecem_apos_limpeza_e_recarga(client, conversa):
    trabalho, _ = conversa
    limpar = reverse("sandbox_limpar_conversa", args=[trabalho.pk])
    assert client.post(limpar).status_code == 302
    nova = MensagemSandbox.objects.create(site_id=trabalho.site_id, participacao=trabalho,
        ator_id="analise-automatica", papel="ia", texto="Resultado do novo teste.")
    pagina = reverse("sandbox_trabalho", args=[trabalho.pk])
    for _ in range(2):
        resposta = client.get(pagina)
        assert list(resposta.context["mensagens"]) == [nova]
        assert len(resposta.context["mensagens_anteriores"]) == 4
        assert 'Análise automática' in resposta.content.decode()
    assert client.post(limpar).status_code == 302
    resposta = client.get(pagina)
    assert not resposta.context["mensagens"]
    assert len(resposta.context["mensagens_anteriores"]) == 5
    assert trabalho.mensagens.count() == 5


@pytest.mark.parametrize("pessoa,site,status", [
    (None, "escola-a", 302),
    ("aluno", "escola-a", 404),
    ("outro-aluno", "escola-a", 404),
    ("equipe-sandbox", "escola-b", 404),
])
def test_apenas_equipe_autorizada_limpa_o_trabalho(client, conversa, pessoa, site, status):
    trabalho, contexto = conversa
    contexto.update(id=pessoa, site=site)
    resposta = client.post(reverse("sandbox_limpar_conversa", args=[trabalho.pk]))
    assert resposta.status_code == status
    trabalho.refresh_from_db()
    assert trabalho.mensagens_recolhidas_ate is None
    assert trabalho.mensagens.count() == 4


def test_limpeza_exige_post_e_csrf(client, conversa):
    trabalho, _ = conversa
    caminho = reverse("sandbox_limpar_conversa", args=[trabalho.pk])
    assert client.get(caminho).status_code == 405
    assert Client(enforce_csrf_checks=True).post(caminho).status_code == 403
    trabalho.refresh_from_db()
    assert trabalho.mensagens_recolhidas_ate is None
