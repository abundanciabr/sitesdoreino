import hashlib
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.core import sessao, telas_sandbox
from apps.encomendas import sandbox
from apps.encomendas.models import ArquivoSandbox, AutorizacaoMarketplaceAluno, MovimentoMeshcoin, ParticipacaoSandbox


@pytest.fixture
def contexto(monkeypatch):
    atual = {"id": "aluno-sandbox", "site": "escola-a"}
    monkeypatch.setattr(sessao, "quem_e", lambda request: atual["id"])
    monkeypatch.setattr(sessao, "site_desta_instalacao", lambda: atual["site"])
    monkeypatch.setenv("IDS_DO_PLANTAO", "equipe-sandbox")
    monkeypatch.setattr(telas_sandbox, "_aluno_atual", lambda request, pessoa, site: True)
    return atual


def test_visitante_volta_ao_sandbox_apos_login(client, contexto):
    from urllib.parse import parse_qs, urlsplit

    contexto["id"] = None
    caminho = reverse("sandbox_catalogo") + "?categoria=pets"
    resposta = client.get(caminho)
    assert resposta.status_code == 302
    destino = urlsplit(resposta["Location"])
    assert destino.path == "/login"
    assert parse_qs(destino.query)["next"] == [caminho]


@pytest.fixture
def projeto(db):
    projeto = sandbox.semear_projetos(site_id="escola-a")[0]
    projeto.prazo_dias = 2
    projeto.ajustes_previstos = 1
    projeto.recompensa = Decimal("7.50")  # somente cenário de teste
    projeto.save()
    return projeto


@pytest.mark.django_db
def test_percurso_telas_arquivos_versoes_ajuste_aprovacao(client, contexto, projeto, settings, tmp_path, monkeypatch):
    settings.MARKETPLACE_UPLOAD_ROOT = tmp_path
    from apps.core import ia_sandbox
    monkeypatch.setattr(ia_sandbox, "responder", lambda p: sandbox.mensagem(
        site_id=p.site_id, participacao_id=p.pk, ator_id="ia-sandbox", papel="ia", texto="IA: confira os critérios."))
    assert client.get(reverse("sandbox_catalogo")).status_code == 200
    assert client.post(reverse("sandbox_aceitar", args=[projeto.pk]), {"aceito_termos": "sim"}).status_code == 302
    p = ParticipacaoSandbox.objects.get(pessoa_id=contexto["id"])
    assert client.get(reverse("sandbox_trabalho", args=[p.pk])).status_code == 200
    assert client.post(reverse("sandbox_mensagem", args=[p.pk]), {"texto": "Como preparo a entrega?"}).status_code == 302
    assert p.mensagens.filter(papel="ia").count() == 1
    for versao in (1, 2):
        recebido = SimpleUploadedFile(f"fonte-v{versao}.blend", b"BLENDER sandbox privado")
        assert client.post(reverse("sandbox_arquivo", args=[p.pk]), {"arquivo": recebido}).status_code == 302
        arquivo = p.arquivos.get(entrega__isnull=True)
        download = client.get(reverse("sandbox_baixar", args=[arquivo.pk]))
        assert b"".join(download.streaming_content) == b"BLENDER sandbox privado"
        assert arquivo.sha256 == hashlib.sha256(b"BLENDER sandbox privado").hexdigest()
        assert download["Cache-Control"] == "private, no-store"
        contexto["id"] = "outro-aluno"
        assert client.get(reverse("sandbox_baixar", args=[arquivo.pk])).status_code == 404
        assert client.get(reverse("sandbox_trabalho", args=[p.pk])).status_code == 404
        contexto["id"] = p.pessoa_id
        assert client.post(reverse("sandbox_entregar", args=[p.pk]), {"arquivos": [str(arquivo.pk)]}).status_code == 302
        assert client.post(reverse("sandbox_avaliar", args=[p.pk, "aprovar"])).status_code == 404
        contexto["id"] = "equipe-sandbox"
        if versao == 1:
            assert client.post(reverse("sandbox_avaliar", args=[p.pk, "ajuste"]), {"texto": "Ajuste a silhueta."}).status_code == 302
            contexto["id"] = p.pessoa_id
    for _ in range(2):
        assert client.post(reverse("sandbox_avaliar", args=[p.pk, "aprovar"])).status_code == 302
    assert MovimentoMeshcoin.objects.filter(participacao=p).count() == 1
    assert sandbox.saldo(site_id="escola-a", pessoa_id=p.pessoa_id) == Decimal("7.50")
    assert p.entregas.count() == 2 and p.arquivos.count() == 2
    assert not AutorizacaoMarketplaceAluno.objects.exists()
    assert client.get(reverse("sandbox_escola")).status_code == 200


@pytest.mark.django_db
def test_visitante_outro_site_csrf_e_preservacao(client, contexto, projeto, monkeypatch):
    p = sandbox.aceitar(site_id="escola-a", pessoa_id=contexto["id"], projeto_id=projeto.pk)
    contexto["site"] = "escola-b"
    assert client.get(reverse("sandbox_trabalho", args=[p.pk])).status_code == 404
    contexto["site"] = "escola-a"
    monkeypatch.setattr(telas_sandbox, "_aluno_atual", lambda request, pessoa, site: False)
    assert client.get(reverse("sandbox_trabalho", args=[p.pk])).status_code == 200
    assert client.post(reverse("sandbox_aceitar", args=[projeto.pk]), {"aceito_termos": "sim"}).status_code == 404
    contexto["id"] = None
    assert client.get(reverse("sandbox_catalogo")).status_code == 302
    assert client.get(reverse("sandbox_trabalho", args=[p.pk])).status_code == 302
    from django.test import Client
    contexto["id"] = p.pessoa_id
    protegido = Client(enforce_csrf_checks=True)
    assert protegido.post(reverse("sandbox_mensagem", args=[p.pk]), {"texto": "teste"}).status_code == 403


@pytest.mark.parametrize("plataforma", ["Hotmart", "Herospark"])
def test_matricula_externa_legitima_sem_consumo_aulas(monkeypatch, plataforma):
    monkeypatch.setattr(telas_sandbox, "_email_da_conta", lambda request, pessoa: "aluno@escola.test")
    monkeypatch.setattr(sessao, "categoria_na_escola", lambda email: "aluno")
    monkeypatch.setattr(telas_sandbox, "_matriculas_ativas", lambda site: [
        {"site_id": "escola-a", "email": "aluno@escola.test", "status": "ativa", "plataforma": plataforma}])
    assert telas_sandbox._aluno_atual(None, "aluno", "escola-a")
    assert not telas_sandbox._aluno_atual(None, "aluno", "outra-escola")

