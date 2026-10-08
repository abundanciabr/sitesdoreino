import json
from uuid import uuid4
from unittest.mock import patch

import pytest
from django.utils import timezone
from apps.quiz.models import NPSTentativa, NPSAtendimento, NPSRevisao


@pytest.fixture
def avaliacao(db, settings):
    settings.TOKEN_EDITOR_ADMIN = "editor-token"
    return NPSTentativa.objects.create(site_id="escola", aluno_id="aluno", status="concluida",
        config_versao=1, config_documento={"perguntas": {}}, respostas={"nota":0},
        resultado={"nps":0, "classificacao":"Detrator"}, concluida_em=timezone.now())


AUTH = {"HTTP_AUTHORIZATION":"Bearer editor-token"}
URL = "/interno/nps/acoes"


def corpo(item, acao, **extra):
    return {"site_id":item.site_id, "aluno_id":item.aluno_id, "tentativa_id":str(item.id), "acao":acao, **extra}


def post(client, data):
    return client.post(URL, json.dumps(data), content_type="application/json", **AUTH)


def test_arquivo_e_restauracao_preservam_respostas_e_separam_lista(client, avaliacao):
    assert post(client, corpo(avaliacao, "arquivar")).status_code == 200
    avaliacao.refresh_from_db()
    primeiro = avaliacao.arquivada_em
    assert primeiro and avaliacao.status == "concluida" and avaliacao.respostas == {"nota":0}
    assert post(client, corpo(avaliacao, "arquivar")).status_code == 200
    avaliacao.refresh_from_db()
    assert avaliacao.arquivada_em == primeiro
    assert client.get('/interno/nps/respondentes', {"site_id":"escola"}, **AUTH).json()["total"] == 0
    arquivo = client.get('/interno/nps/respondentes', {"site_id":"escola", "arquivadas":"1"}, **AUTH).json()
    assert arquivo["total"] == 1 and arquivo["itens"][0]["arquivada_em"]
    historico = client.get('/interno/nps/historico', {"site_id":"escola", "aluno_id":"aluno"}, **AUTH).json()
    assert historico["avaliacoes"][0]["arquivada_em"]
    assert post(client, corpo(avaliacao, "restaurar")).status_code == 200
    avaliacao.refresh_from_db()
    assert avaliacao.arquivada_em is None
    assert client.get('/interno/nps/respondentes', {"site_id":"escola"}, **AUTH).json()["total"] == 1


def test_excluir_so_com_confirmacao_preserva_atendimento_e_outros_alunos(client, avaliacao):
    caso = NPSAtendimento.objects.create(site_id="escola", aluno_id="aluno", tentativa=avaliacao,
        responsavel="Equipe", historico=[{"solucao":"Contato feito"}])
    revisao = NPSRevisao.objects.create(tentativa=avaliacao, site_id="escola", aluno_id="aluno", situacao_id="R2", tipo="fato")
    outra = NPSTentativa.objects.create(site_id="outro", aluno_id="outro", config_versao=1, config_documento={})
    assert post(client, corpo(avaliacao, "excluir")).status_code == 400
    assert NPSTentativa.objects.filter(pk=avaliacao.pk).exists()
    assert post(client, corpo(avaliacao, "excluir", confirmacao="excluir")).status_code == 200
    assert not NPSTentativa.objects.filter(pk=avaliacao.pk).exists()
    assert not NPSRevisao.objects.filter(pk=revisao.pk).exists()
    assert NPSTentativa.objects.filter(pk=outra.pk).exists()
    caso.refresh_from_db()
    assert caso.tentativa_id is None and caso.historico == [{"solucao":"Contato feito"}]


def test_acoes_nao_atingem_outro_site_aluno_ou_uuid_invalido(client, avaliacao):
    for acao in ("arquivar", "restaurar", "excluir"):
        for extra in ({"site_id":"outro"}, {"aluno_id":"outro"}, {"tentativa_id":str(uuid4())}):
            assert post(client, corpo(avaliacao, acao, confirmacao="excluir", **extra)).status_code == 404
        assert post(client, corpo(avaliacao, acao, tentativa_id="invalido", confirmacao="excluir")).status_code == 400
    avaliacao.refresh_from_db()
    assert avaliacao.arquivada_em is None


def test_autenticacao_metodo_e_acao_invalidos(client, avaliacao):
    assert client.post(URL, corpo(avaliacao, "arquivar")).status_code == 401
    assert client.get(URL, **AUTH).status_code == 405
    assert post(client, corpo(avaliacao, "qualquer")).status_code == 400
    assert post(client, []).status_code == 400


def test_exclusao_falha_sem_deixar_atendimento_desvinculado(client, avaliacao):
    caso = NPSAtendimento.objects.create(site_id="escola", aluno_id="aluno", tentativa=avaliacao)
    with patch.object(NPSTentativa, 'delete', side_effect=RuntimeError('falha simulada')):
        with pytest.raises(RuntimeError):
            post(client, corpo(avaliacao, "excluir", confirmacao="excluir"))
    caso.refresh_from_db()
    assert caso.tentativa_id == avaliacao.pk and NPSTentativa.objects.filter(pk=avaliacao.pk).exists()
