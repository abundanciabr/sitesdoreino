import pytest
from django.conf import settings
from apps.gamificacao.models import Pessoa, JornadaPessoal, AvaliacaoDaJornada, RegistroDaJornada, LancamentoDeXP
from apps.gamificacao.jornada import situacao, registrar_avaliacao
from apps.gamificacao.gestao_trilha import remover
from apps.gamificacao.bonus_faixas import configurar
pytestmark = pytest.mark.django_db

@pytest.fixture
def aluna():
    p = Pessoa.objects.create(id_da_plataforma="teste-gestao", email="teste@example.test")
    j = JornadaPessoal.objects.create(pessoa=p, site_id="teste", inicio={"motivo":"aprender"})
    configurar("teste")
    for ordem in range(2,8):
        registrar_avaliacao(p.pk,"teste",ordem,"reconhecida","Atividade conferida",{"chave":str(ordem)})
    return p,j

def test_remocao_preserva_historico_xp_e_repeticao_nao_reconquista(aluna):
    p,j=aluna
    xp=list(LancamentoDeXP.objects.values())
    quantidade=AvaliacaoDaJornada.objects.count()
    remover(p.pk,"teste",3,"etapa","admin",j.revisao)
    assert situacao(p.pk,"teste")["atual"]["ordem"] == 2
    assert AvaliacaoDaJornada.objects.count() == quantidade
    assert list(LancamentoDeXP.objects.values()) == xp
    registrar_avaliacao(p.pk,"teste",3,"reconhecida","Atividade conferida",{"chave":"3"})
    assert situacao(p.pk,"teste")["atual"]["ordem"] == 2
    registrar_avaliacao(p.pk,"teste",3,"reconhecida","Nova atividade conferida",{"chave":"nova"})
    assert situacao(p.pk,"teste")["atual"]["ordem"] == 7
    assert list(LancamentoDeXP.objects.values()) == xp
    assert RegistroDaJornada.objects.filter(acao="admin_remover").count() == 1

def test_isolamento_revisao_e_branca(aluna):
    p,j=aluna
    for site,ordem,revisao in [("outro",3,0),("teste",1,0),("teste",3,99)]:
        with pytest.raises(ValueError): remover(p.pk,site,ordem,"etapa","admin",revisao)
    assert situacao(p.pk,"teste")["atual"]["ordem"] == 7

def test_api_reservada_ao_admin(client,monkeypatch,aluna):
    p,j=aluna
    monkeypatch.setenv("SITE_ID","teste")
    monkeypatch.setenv("TOKENS_ACEITOS_ADMIN","admin-token")
    monkeypatch.setattr(settings,"TOKENS_ACEITOS",["admin-token","outro-token"])
    url=f"/api/gamificacao/gestao-trilha/teste/{p.pk}"
    assert client.get(url).status_code == 401
    assert client.get(url,HTTP_AUTHORIZATION="Bearer outro-token").status_code == 403
    assert client.get(url,HTTP_AUTHORIZATION="Bearer admin-token").status_code == 200
    assert client.post(url,data={"ordem":3,"tipo":"etapa","ator":"admin","revisao":0},content_type="application/json",HTTP_AUTHORIZATION="Bearer admin-token").status_code == 200
    assert situacao(p.pk,"teste")["atual"]["ordem"] == 2

def test_faixa_preta_retira_todos_graus_e_isola_outro_aluno(aluna):
    from apps.gamificacao.gestao_trilha import cortes
    p,j=aluna
    remover(p.pk,"teste",7,"faixa","admin",0)
    assert set(cortes(p.pk,"teste","aprender")) == set(range(7,14))
    assert situacao(p.pk,"teste")["atual"]["ordem"] == 6
    assert cortes("outra-pessoa","teste","aprender") == {}
    assert cortes(p.pk,"outro-site","aprender") == {}
