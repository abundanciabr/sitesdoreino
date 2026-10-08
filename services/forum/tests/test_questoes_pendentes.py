import pytest
from django.test import Client
from django.utils import timezone

from apps.forum.models import Area, Mensagem, Pessoa, Topico

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def tokens(settings):
    settings.TOKENS_ACEITOS = {"admin-teste", "outro-par"}
    settings.TOKEN_DO_EDITOR_FORUM = "admin-teste"


def pedir(token="admin-teste", **params):
    return Client().get("/interno/questoes/pendentes", params, HTTP_AUTHORIZATION=f"Bearer {token}" if token else "")


@pytest.fixture
def cenario():
    a = Pessoa.objects.create(id_da_plataforma="aluno-fila", nome_exibido="Aluno da fila", email="aluno@invalid.example")
    b = Pessoa.objects.create(id_da_plataforma="outra-fila", nome_exibido="Outra pessoa", email="outra@invalid.example")
    regiao = Area.objects.create(slug="duvidas-fila", nome="Dúvidas da fila", visibilidade="alunos")
    def criar(titulo, **kwargs):
        t = Topico.objects.create(area=regiao, autor=a, titulo=titulo, **kwargs)
        Mensagem.objects.create(topico=t, autor=a, texto="Pergunta original")
        return t
    return a, b, regiao, criar


def test_apenas_o_par_admin_pode_ler():
    assert pedir(token="").status_code == 401
    assert pedir(token="outro-par").status_code == 403
    assert pedir().status_code == 200


def test_sem_resposta_nao_conta_a_pergunta_atualizacoes_ou_falas_removidas(cenario):
    a, b, regiao, criar = cenario
    sem = criar("Ainda esperando")
    Mensagem.objects.create(topico=sem, autor=a, texto="Atualização do aluno")
    Mensagem.objects.create(topico=sem, autor=b, texto="Removida", removida_em=timezone.now())
    respondida = criar("Resposta de colega")
    Mensagem.objects.create(topico=respondida, autor=b, texto="Ajuda")
    escola = criar("Resposta da escola")
    Mensagem.objects.create(topico=escola, autor=None, publicado_pela_escola=True, texto="Ajuda da escola")
    dados = pedir().json()
    assert (dados["abertas"], dados["sem_resposta"], dados["respondidas"]) == (3, 1, 2)
    assert [i["id"] for i in pedir(filtro="sem-resposta").json()["itens"]] == [sem.pk]
    assert {i["id"] for i in pedir(filtro="respondidas").json()["itens"]} == {respondida.pk, escola.pk}


def test_resolvidas_removidas_e_publicacoes_da_escola_ficam_fora(cenario):
    a, b, regiao, criar = cenario
    resolvida = criar("Resolvida")
    resposta = Mensagem.objects.create(topico=resolvida, autor=b, texto="Resolvido")
    Topico.objects.filter(pk=resolvida.pk).update(resposta_aceita=resposta)
    criar("Removida", estado="removido")
    criar("Aguardando aprovação", estado="esperando")
    Topico.objects.create(area=regiao, publicado_pela_escola=True, titulo="Aviso da escola")
    assert pedir().json()["total"] == 0


def test_todas_as_areas_inclui_grupo_privado_arquivado_e_trancado(cenario):
    a, b, regiao, criar = cenario
    normal = criar("Área normal")
    grupo = Area.objects.create(slug="grupo-fila", nome="Grupo privado", visibilidade="turma", curso_id="curso-teste", ativa=False)
    antiga = Topico.objects.create(area=grupo, autor=a, titulo="Grupo arquivado", trancado=True)
    dados = pedir().json()
    assert {i["id"] for i in dados["itens"]} == {normal.pk, antiga.pk}
    item = next(i for i in dados["itens"] if i["id"] == antiga.pk)
    assert item["area_arquivada"] and item["trancada"]
    assert pedir(area="grupo-fila").json()["total"] == 1
    assert pedir(q="arquivado").json()["total"] == 1
    assert pedir(q="Aluno da fila").json()["total"] == 2


def test_paginacao_mantem_as_mais_antigas_primeiro(cenario):
    a, b, regiao, criar = cenario
    linhas = [Topico(area=regiao, autor=a, titulo=f"Questão {n}") for n in range(55)]
    Topico.objects.bulk_create(linhas)
    primeira = pedir().json()
    segunda = pedir(pagina=2).json()
    assert primeira["total"] == 55 and primeira["paginas"] == 2
    assert len(primeira["itens"]) == 50 and len(segunda["itens"]) == 5
    assert primeira["itens"][0]["id"] == linhas[0].pk
    assert not ({i["id"] for i in primeira["itens"]} & {i["id"] for i in segunda["itens"]})
