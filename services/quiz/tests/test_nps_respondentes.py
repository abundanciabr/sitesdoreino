from datetime import timedelta

import pytest
from django.utils import timezone

from apps.quiz.models import NPSTentativa


@pytest.mark.django_db
def test_lista_somente_concluidas_do_site_com_busca_contagem_e_paginacao(client, settings):
    settings.TOKEN_EDITOR_ADMIN = "editor-token"
    auth = {"HTTP_AUTHORIZATION": "Bearer editor-token"}
    url = "/interno/nps/respondentes"
    assert client.get(url, {"site_id": "escola"}).status_code == 401
    assert client.get(url, **auth).status_code == 400
    assert client.post(url, **auth).status_code == 405

    def criar(aluno_id, *, site_id="escola", status="concluida", nome="Ana", dias=0, nota=0):
        return NPSTentativa.objects.create(
            site_id=site_id, aluno_id=aluno_id, status=status,
            aluno={"nome": nome, "email": aluno_id + "@example.test"}, curso={"nome": "Desenho"},
            config_versao=1, config_documento={"perguntas": {}}, respostas={},
            resultado={"nps": nota, "classificacao": "Neutro"},
            concluida_em=timezone.now() - timedelta(days=dias) if status == "concluida" else None,
        )
    criar("ana", dias=2)
    recente = criar("ana", nome="Ana Silva", nota=10)
    criar("outro", site_id="outro-site", nome="Segredo outro site")
    criar("incompleta", status="em_andamento")
    dados = client.get(url, {"site_id": "escola"}, **auth).json()
    assert dados["alunos"] == 1 and dados["total"] == 2
    assert dados["itens"][0]["id"] == str(recente.id)
    assert dados["itens"][1]["nota"] == 0
    assert "respostas" not in dados["itens"][0]
    assert client.get(url, {"site_id": "escola", "q": "SILVA"}, **auth).json()["total"] == 1
    assert client.get(url, {"site_id": "escola", "q": "ana@example.test"}, **auth).json()["total"] == 2
    assert client.get(url, {"site_id": "escola", "q": "desenho"}, **auth).json()["total"] == 2
    assert client.get(url, {"site_id": "escola", "q": "ausente"}, **auth).json()["itens"] == []
    for indice in range(50):
        criar("aluno-" + str(indice))
    primeira = client.get(url, {"site_id": "escola", "pagina": "inválida"}, **auth).json()
    segunda = client.get(url, {"site_id": "escola", "pagina": "2"}, **auth).json()
    assert primeira["alunos"] == 51 and primeira["total"] == 52 and primeira["paginas"] == 2
    assert len(primeira["itens"]) == 50 and len(segunda["itens"]) == 2
    assert not {i["id"] for i in primeira["itens"]} & {i["id"] for i in segunda["itens"]}
