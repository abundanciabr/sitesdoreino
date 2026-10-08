from datetime import timedelta

import pytest
from django.utils import timezone

from apps.core import participacao, views
from apps.core.sessao import Ator, VISITANTE
from apps.forum.models import Area, Mensagem, Pessoa, Topico


@pytest.fixture
def cenario(monkeypatch):
    pessoas = [Pessoa.objects.create(id_da_plataforma=i, email=i + "@example.test", nome_exibido=i) for i in ("autor", "colega", "admin", "professor")]
    area = Area.objects.create(slug="alunos", nome="Alunos", visibilidade="alunos", quem_escreve="aluno")
    topico = Topico.objects.create(area=area, autor=pessoas[0], titulo="Uma dúvida concreta")
    mensagem = Mensagem.objects.create(topico=topico, autor=pessoas[0], texto="Conteúdo que precisa ficar restrito")
    estados = {i: {"segmento": "detrator" if i == "autor" else "promotor", "embaixador": True, "conquistas_privadas_ate": "2026-10-08T00:00:00Z" if i == "autor" else None} for i in ("autor", "colega", "admin", "professor")}
    monkeypatch.setattr(participacao, "consultar", lambda ids: {str(i): estados[str(i)] for i in ids if i})
    return pessoas, area, topico, mensagem, estados


@pytest.mark.django_db
def test_detrator_so_e_visivel_para_o_proprio_autor_e_admin(cenario):
    pessoas, area, topico, mensagem, estados = cenario
    atores = [Ator(pessoa=pessoas[0], eh_aluno=True), Ator(pessoa=pessoas[1], eh_aluno=True), Ator(pessoa=pessoas[2], eh_admin=True), Ator(pessoa=pessoas[3], eh_professor=True), VISITANTE]
    for ator, esperado in zip(atores, [True, False, True, False, False]):
        assert participacao.topicos_visiveis(Topico.objects.all(), ator).exists() == esperado
        assert participacao.mensagens_visiveis(Mensagem.objects.all(), ator).exists() == esperado
    estados["autor"]["segmento"] = "promotor"
    assert participacao.topicos_visiveis(Topico.objects.all(), atores[1]).exists()
    assert participacao.mensagens_visiveis(Mensagem.objects.all(), atores[1]).exists()


@pytest.mark.django_db
def test_link_direto_nao_entrega_conteudo_restrito(client, cenario, monkeypatch):
    pessoas, area, topico, mensagem, estados = cenario
    monkeypatch.setattr(views, "quem_e", lambda request: Ator(pessoa=pessoas[1], eh_aluno=True))
    resposta = client.get(f"/t/{topico.pk}")
    assert resposta.status_code == 404
    assert mensagem.texto.encode() not in resposta.content


@pytest.mark.django_db
def test_professor_nao_contorna_visibilidade_por_rota_de_moderacao(client, cenario, monkeypatch):
    from apps.core import moderacao
    pessoas, area, topico, mensagem, estados = cenario
    ator = Ator(pessoa=pessoas[3], eh_professor=True)
    monkeypatch.setattr(moderacao, "quem_e", lambda request: ator)
    resposta = client.post(f"/t/{topico.pk}/moderar", {"acao": "salvar", "titulo": ""})
    assert resposta.status_code == 404
    assert topico.titulo.encode() not in resposta.content
    assert mensagem.texto.encode() not in resposta.content


@pytest.mark.django_db
def test_publicar_pela_moderacao_nao_retira_a_restricao_da_avaliacao(cenario):
    pessoas, area, topico, mensagem, estados = cenario
    topico.estado = Topico.Estado.PUBLICADO
    topico.save()
    assert not participacao.topicos_visiveis(Topico.objects.all(), Ator(pessoa=pessoas[1], eh_aluno=True)).exists()


@pytest.mark.django_db
def test_selo_historico_fica_apenas_com_o_autor_mesmo_apos_recuperacao(cenario):
    pessoas, area, topico, mensagem, estados = cenario
    estados["autor"]["segmento"] = "promotor"
    assert participacao.decorar([mensagem], Ator(pessoa=pessoas[0], eh_aluno=True))[0].embaixador
    assert not participacao.decorar([mensagem], Ator(pessoa=pessoas[1], eh_aluno=True))[0].embaixador
    assert not participacao.decorar([mensagem], Ator(pessoa=pessoas[2], eh_admin=True))[0].embaixador


@pytest.mark.django_db
def test_comentario_restrito_nao_vaza_em_topico_de_outro_aluno(cenario):
    pessoas, area, topico, mensagem, estados = cenario
    aberto = Topico.objects.create(area=area, autor=pessoas[1], titulo="Uma conversa aberta")
    escondida = Mensagem.objects.create(topico=aberto, autor=pessoas[0], texto="Comentário restrito")
    consulta = Mensagem.objects.filter(topico=aberto)
    assert not participacao.mensagens_visiveis(consulta, Ator(pessoa=pessoas[1], eh_aluno=True)).exists()
    assert participacao.mensagens_visiveis(consulta, Ator(pessoa=pessoas[0], eh_aluno=True)).get() == escondida


@pytest.mark.django_db
def test_indisponibilidade_nao_abre_conteudo(cenario, monkeypatch):
    pessoas, area, topico, mensagem, estados = cenario
    def falhar(ids):
        raise participacao.AvaliacaoIndisponivel()
    monkeypatch.setattr(participacao, "consultar", falhar)
    assert not participacao.topicos_visiveis(Topico.objects.all(), Ator(pessoa=pessoas[1], eh_aluno=True)).exists()
    assert participacao.topicos_visiveis(Topico.objects.all(), Ator(pessoa=pessoas[0], eh_aluno=True)).exists()


@pytest.mark.django_db
def test_post_do_detrator_preserva_a_atividade_visivel(client, cenario, monkeypatch):
    pessoas, area, topico, mensagem, estados = cenario
    aberto = Topico.objects.create(area=area, autor=pessoas[1], titulo="Uma conversa aberta", ultima_atividade_em=timezone.now() - timedelta(days=1))
    antes = aberto.ultima_atividade_em
    monkeypatch.setattr(views, "quem_e", lambda request: Ator(pessoa=pessoas[0], eh_aluno=True))
    monkeypatch.setattr(views, "site_id_do_host", lambda host: "escola")
    monkeypatch.setattr(views, "relay_apos_commit", lambda: None)
    resposta = client.post(f"/t/{aberto.pk}/responder", {"texto": "Esta mensagem continua aparecendo para mim."})
    assert resposta.status_code == 302
    aberto.refresh_from_db()
    assert aberto.ultima_atividade_em == antes
    assert Mensagem.objects.filter(topico=aberto, autor=pessoas[0]).exists()
