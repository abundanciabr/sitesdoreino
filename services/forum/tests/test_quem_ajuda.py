import pytest
from django.urls import reverse
from django.utils import timezone
from apps.core.sessao import Ator
from apps.core.quem_ajuda import ranking_de_ajuda
from apps.forum.models import Area, Mensagem, MembroDoGrupo, Pessoa, Topico

pytestmark = pytest.mark.django_db


def pessoa(i):
    return Pessoa.objects.create(
        id_da_plataforma=f"p{i}", nome_exibido=f"Pessoa {i}", email=f"p{i}@example.test"
    )


def area(slug="duvidas", turma=False, responsavel=None):
    return Area.objects.create(
        slug=slug,
        nome=slug,
        visibilidade="turma" if turma else "alunos",
        quem_escreve="aluno",
        responsavel=responsavel,
        curso_id="curso" if turma else "",
    )


def solucao(grupo, autor, ajudante):
    topico = Topico.objects.create(
        area=grupo, autor=autor, titulo="Como resolver esta dúvida?"
    )
    resposta = Mensagem.objects.create(
        topico=topico, autor=ajudante, texto="Resposta que resolveu"
    )
    topico.resposta_aceita = resposta
    topico.save(update_fields=["resposta_aceita"])
    return topico


@pytest.mark.parametrize("papel", ["visitante", "aluno", "professor"])
def test_previa_fecha_para_quem_nao_e_admin(client, monkeypatch, papel):
    ator = (
        Ator(None)
        if papel == "visitante"
        else Ator(
            pessoa(1), eh_aluno=papel == "aluno", eh_professor=papel == "professor"
        )
    )
    monkeypatch.setattr("apps.core.quem_ajuda.quem_e", lambda request: ator)
    assert client.get(reverse("previa_quem_ajuda")).status_code == 404


def test_top_cinco_conta_aceite_atual_e_nao_respostas(client, monkeypatch):
    admin, autor = pessoa(90), pessoa(91)
    grupo = area()
    ajudantes = [pessoa(i) for i in range(1, 7)]
    for i, ajudante in enumerate(ajudantes, 1):
        for _ in range(i):
            solucao(grupo, autor, ajudante)
    topico = solucao(grupo, autor, ajudantes[-1])
    Mensagem.objects.create(
        topico=topico, autor=ajudantes[0], texto="Resposta sem aceite"
    )
    ator = Ator(admin, eh_admin=True)
    monkeypatch.setattr("apps.core.quem_ajuda.quem_e", lambda request: ator)
    resposta = client.get(reverse("previa_quem_ajuda"))
    assert resposta.status_code == 200
    assert [(p["nome"], p["solucoes"]) for p in resposta.context["ranking"]] == [
        ("Pessoa 6", 7),
        ("Pessoa 5", 5),
        ("Pessoa 4", 4),
        ("Pessoa 3", 3),
        ("Pessoa 2", 2),
    ]
    assert "no-store" in resposta["Cache-Control"]
    assert "noindex" in resposta["X-Robots-Tag"]
    assert "@example.test" not in resposta.content.decode()
    topico.resposta_aceita = None
    topico.save(update_fields=["resposta_aceita"])
    assert ranking_de_ajuda(ator)[0]["solucoes"] == 6


def test_removidos_arquivados_autoresposta_e_escola_nao_contam():
    admin, autor, ajudante = pessoa(90), pessoa(91), pessoa(1)
    grupo = area()
    solucao(grupo, autor, ajudante)
    removido = solucao(grupo, autor, ajudante)
    removido.resposta_aceita.removida_em = timezone.now()
    removido.resposta_aceita.save(update_fields=["removida_em"])
    oculto = solucao(grupo, autor, ajudante)
    oculto.estado = Topico.Estado.REMOVIDO
    oculto.save(update_fields=["estado"])
    solucao(grupo, ajudante, ajudante)
    arquivada = area("arquivada")
    solucao(arquivada, autor, ajudante)
    arquivada.ativa = False
    arquivada.save(update_fields=["ativa"])
    escola = Topico.objects.create(
        area=grupo, autor=autor, titulo="Dúvida respondida pela escola"
    )
    escola.resposta_aceita = Mensagem.objects.create(
        topico=escola, publicado_pela_escola=True, texto="Resposta da escola"
    )
    escola.save(update_fields=["resposta_aceita"])
    assert ranking_de_ajuda(Ator(admin, eh_admin=True))[0]["solucoes"] == 1


def test_grupo_privado_nao_vaza_no_ranking(monkeypatch):
    admin, membro, autor, ajudante = pessoa(90), pessoa(91), pessoa(92), pessoa(1)
    azul = area("azul", True, admin)
    verde = area("verde", True, admin)
    MembroDoGrupo.objects.create(
        grupo=azul, pessoa=membro, adicionado_por=admin, motivo="Teste de acesso"
    )
    solucao(azul, autor, ajudante)
    for _ in range(3):
        solucao(verde, autor, ajudante)
    monkeypatch.setattr(
        "apps.core.participacao.consultar",
        lambda ids: {str(i): {"segmento": "promotor"} for i in ids},
    )
    ator = Ator(membro, eh_aluno=True)
    assert ranking_de_ajuda(ator)[0]["solucoes"] == 1
    assert ranking_de_ajuda(ator, verde) == []
    assert ranking_de_ajuda(Ator(admin, eh_admin=True), verde)[0]["solucoes"] == 3


def test_previa_vazia_e_filtro_inexistente(client, monkeypatch):
    monkeypatch.setattr(
        "apps.core.quem_ajuda.quem_e", lambda request: Ator(pessoa_admin, eh_admin=True)
    )
    pessoa_admin = pessoa(90)
    resposta = client.get(reverse("previa_quem_ajuda"))
    assert resposta.status_code == 200
    assert resposta.context["ranking"] == []
    assert "Ainda não há respostas aceitas" in resposta.content.decode()
    assert (
        client.get(reverse("previa_quem_ajuda"), {"grupo": "inexistente"}).status_code
        == 404
    )
