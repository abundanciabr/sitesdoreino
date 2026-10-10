import json
import uuid
from datetime import timedelta

import pytest
from django.http import Http404, HttpResponse
from django.test import RequestFactory
from django.utils import timezone

from apps.atendimento import contexto, gestao, indicadores, service, views
from apps.atendimento.models import Assunto, Conversa, Mensagem


pytestmark = pytest.mark.django_db
SID = "site-suporte-a"
OUTRO_SID = "site-suporte-b"


class RenderCapturado(HttpResponse):
    def __init__(self, template, context, status=200):
        super().__init__(status=status)
        self.template_name = template
        self.context_data = context


def _capturar_render(monkeypatch, modulo):
    capturas = []

    def render(_request, template, context=None, status=200, **_kwargs):
        resposta = RenderCapturado(template, context or {}, status)
        capturas.append(resposta)
        return resposta

    monkeypatch.setattr(modulo, "render", render)
    return capturas


def _requisicao(metodo, caminho, dados=None, admin=True):
    fabrica = RequestFactory()
    request = getattr(fabrica, metodo)(caminho, data=dados or {})
    if admin:
        request.admin = {"id": "admin-a", "nome": "Equipe A"}
    return request


@pytest.fixture
def suporte(monkeypatch):
    monkeypatch.setattr(views.CatalogoClient, "site_por_host", lambda *_args: {"id": SID})
    service.config(SID)
    service.config(OUTRO_SID)
    assunto = Assunto.objects.get(site_id=SID, nome="Cursos")
    assunto_outro = Assunto.objects.get(site_id=OUTRO_SID, nome="Cursos")
    return assunto, assunto_outro


def _conversa(assunto, *, site_id=SID, pessoa="aluno-a", estado="aguardando",
              prioridade="normal", atendente_id="", atendente_nome="", curso="curso-a"):
    return Conversa.objects.create(
        site_id=site_id, pessoa_id=pessoa, nome="Aluno Exemplo", assunto=assunto,
        estado=estado, prioridade=prioridade, atendente_id=atendente_id,
        atendente_nome=atendente_nome, curso=curso,
    )


def test_renderiza_as_seis_telas_com_dados_reais_e_ausentes(suporte,monkeypatch):
    assunto,_=suporte
    c=_conversa(assunto)
    Mensagem.objects.create(conversa=c,autor='aluno',referencia='render-123',texto='Uma demanda real de teste')
    monkeypatch.setattr(contexto,'consultar',lambda c:{'crm':{'estado':'Cadastro indisponível'},'nps':{'estado':'Sem avaliações'},'faixa':{'estado':'Sem faixa'}})
    for func,caminho,args in [
        (views.fila,'/equipe/atendimento/',()),
        (gestao.triagem,'/equipe/atendimento/triagem/',()),
        (gestao.alunos,'/equipe/atendimento/alunos/',()),
        (views.conversa_admin,f'/equipe/atendimento/{c.pk}/',(c.pk,)),
        (gestao.aluno,f'/equipe/atendimento/{c.pk}/aluno/',(c.pk,)),
        (indicadores.desempenho,'/equipe/atendimento/desempenho/',()),
        (indicadores.supervisor,'/equipe/atendimento/supervisor/',()),
    ]:
        resposta=func(_requisicao('get',caminho),*args)
        assert resposta.status_code==200
        assert b'gerenciamento.css' in resposta.content


def test_as_seis_telas_mostram_apenas_conversas_do_site_da_sessao(suporte, monkeypatch):
    assunto, assunto_outro = suporte
    antiga = _conversa(assunto, estado="aguardando_aluno", atendente_id="membro-1",
                       atendente_nome="Ana", prioridade="alta")
    atual = _conversa(assunto, estado="andamento", atendente_id="membro-1",
                      atendente_nome="Ana", prioridade="alta")
    Conversa.objects.filter(pk=antiga.pk).update(criada_em=timezone.now() - timedelta(days=1))
    _conversa(assunto_outro, site_id=OUTRO_SID, estado="andamento", prioridade="alta",
              atendente_id="membro-2", atendente_nome="Outro site", curso="curso-b")
    Mensagem.objects.create(conversa=atual, autor="aluno", nome="Aluno Exemplo",
                            referencia="pergunta-1", texto="Preciso de ajuda com a aula.")

    renders_views = _capturar_render(monkeypatch, views)
    r = views.fila(_requisicao("get", "/atendimento/?estado=todos"))
    assert r.status_code == 200
    assert {c.site_id for c in renders_views[-1].context_data["conversas"]} == {SID}
    entrada = views.fila(_requisicao("get", "/atendimento/conversas/"))
    assert entrada.status_code == 302
    assert any(entrada.url.endswith(str(c.pk) + '/') for c in (atual, antiga))

    renders_gestao = _capturar_render(monkeypatch, gestao)
    r = gestao.triagem(_requisicao("get", "/admin/atendimento/triagem/"))
    assert r.status_code == 200
    assert set(renders_gestao[-1].context_data["consulta"].values_list("site_id", flat=True)) == {SID}

    r = gestao.alunos(_requisicao("get", "/admin/atendimento/alunos/"))
    assert r.status_code == 200
    fichas = renders_gestao[-1].context_data["conversas"]
    assert [c.pk for c in fichas] == [atual.pk]

    monkeypatch.setattr(contexto, "consultar", lambda c: {"privado": c.pessoa_id})
    r = gestao.aluno(_requisicao("get", f"/admin/atendimento/{atual.pk}/aluno/"), atual.pk)
    assert r.status_code == 200
    ficha = renders_gestao[-1].context_data
    assert ficha["conversa"].pk == atual.pk
    assert ficha["ficha"] == {"privado": "aluno-a"}
    assert [c.site_id for c in ficha["historico"]] == [SID]

    renders_indicadores = _capturar_render(monkeypatch, indicadores)
    r = indicadores.desempenho(_requisicao("get", "/admin/atendimento/desempenho/"))
    assert r.status_code == 200
    desempenho = renders_indicadores[-1].context_data
    assert desempenho["metricas"]["recebidos"] == 2
    assert "curso-b" not in desempenho["cursos"]

    r = indicadores.supervisor(_requisicao("get", "/admin/atendimento/supervisor/"))
    assert r.status_code == 200
    supervisor = renders_indicadores[-1].context_data
    assert supervisor["resumo"]["andamento"] == 1
    assert supervisor["resumo"]["aguardando_aluno"] == 1
    assert {i["atendente_id"] for i in supervisor["carga"]} == {"membro-1"}


@pytest.mark.parametrize(
    ("modulo", "nome", "argumentos"),
    [
        (views, "fila", ()),
        (gestao, "triagem", ()),
        (gestao, "alunos", ()),
        (gestao, "aluno", (uuid.uuid4(),)),
        (indicadores, "desempenho", ()),
        (indicadores, "supervisor", ()),
    ],
)
def test_aluno_sem_sessao_admin_nao_acessa_nenhuma_tela_privada(
    suporte, modulo, nome, argumentos
):
    caminho = "/admin/atendimento/"
    request = _requisicao("get", caminho, admin=False)
    with pytest.raises(Http404):
        getattr(modulo, nome)(request, *argumentos)


def test_ficha_privada_e_contexto_json_nao_abrem_para_aluno(suporte):
    assunto, _ = suporte
    conversa = _conversa(assunto)
    request = _requisicao("get", f"/admin/atendimento/{conversa.pk}/aluno/", admin=False)
    with pytest.raises(Http404):
        gestao.aluno(request, conversa.pk)

    request = _requisicao("get", f"/admin/atendimento/{conversa.pk}/?formato=json", admin=False)
    with pytest.raises(Http404):
        views.conversa_admin(request, conversa.pk)


def test_conversa_de_outro_site_nao_pode_ser_aberta_nem_organizada(suporte, monkeypatch):
    assunto, assunto_outro = suporte
    alheia = _conversa(assunto_outro, site_id=OUTRO_SID, atendente_id="membro-2")
    monkeypatch.setattr(gestao, "identidade_atendente", lambda _request: ("admin-a", "Equipe A"))
    monkeypatch.setattr(gestao, "responsaveis", lambda *_args: [{"id": "admin-a", "nome": "Equipe A"}])

    get = _requisicao("get", f"/admin/atendimento/{alheia.pk}/")
    with pytest.raises(Http404):
        views.conversa_admin(get, alheia.pk)
    post = _requisicao("post", f"/admin/atendimento/{alheia.pk}/", {
        "acao": "organizar", "estado": "encerrado", "prioridade": "alta", "responsavel": "admin-a",
    })
    with pytest.raises(Http404):
        views.conversa_admin(post, alheia.pk)
    alheia.refresh_from_db()
    assert alheia.estado == "aguardando"
    assert alheia.prioridade == "normal"


def test_prioridade_status_e_responsavel_sao_persistidos(suporte, monkeypatch):
    assunto, _ = suporte
    conversa = _conversa(assunto)
    monkeypatch.setattr(gestao, "identidade_atendente", lambda _request: ("admin-a", "Equipe A"))
    monkeypatch.setattr(gestao, "responsaveis", lambda *_args: [
        {"id": "admin-a", "nome": "Equipe A"}, {"id": "membro-2", "nome": "Bia"},
    ])
    request = _requisicao("post", f"/admin/atendimento/{conversa.pk}/", {
        "acao": "organizar", "estado": "aguardando_aluno", "prioridade": "alta", "responsavel": "membro-2",
    })

    resposta = views.conversa_admin(request, conversa.pk)

    assert resposta.status_code == 302
    conversa.refresh_from_db()
    assert (conversa.estado, conversa.prioridade, conversa.atendente_id, conversa.atendente_nome) == (
        "aguardando_aluno", "alta", "membro-2", "Bia"
    )


def test_mensagem_do_aluno_retoma_atendimento_que_aguardava_aluno(suporte, monkeypatch):
    assunto, _ = suporte
    conversa = _conversa(assunto, estado="aguardando_aluno", atendente_id="admin-a",
                         atendente_nome="Equipe A")
    monkeypatch.setattr(views.IdentidadeClient, "sessao_completa", lambda *_args: {
        "autenticado": True, "id": conversa.pessoa_id, "nome_exibido": conversa.nome,
    })
    corpo = {"acao": "mensagem", "conversa": str(conversa.pk), "referencia": "resposta-aluno-1",
             "texto": "Ainda preciso de ajuda.", "assunto": assunto.pk}
    request = RequestFactory().post(
        "/interno/atendimento-aluno/", data=json.dumps(corpo), content_type="application/json"
    )

    resposta = views.aluno(request)
    repetida = RequestFactory().post(
        "/interno/atendimento-aluno/", data=json.dumps(corpo), content_type="application/json"
    )
    repetida.COOKIES["meshcraft_sessao"] = "sessao-do-aluno"
    assert views.aluno(repetida).status_code == 200

    assert resposta.status_code == 200
    conversa.refresh_from_db()
    assert conversa.estado == "andamento"
    assert conversa.atendente_id == "admin-a"
    assert conversa.mensagens.filter(autor="aluno", referencia="resposta-aluno-1").count() == 1


def test_assumir_responder_idempotente_e_encerrar_registram_estado_e_horarios(suporte, monkeypatch):
    assunto, _ = suporte
    conversa = _conversa(assunto, estado="aguardando", curso="curso-a")
    monkeypatch.setattr(gestao, "identidade_atendente", lambda _request: ("admin-a", "Equipe A"))
    monkeypatch.setattr(gestao, "responsaveis", lambda *_args: [{"id": "admin-a", "nome": "Equipe A"}])
    monkeypatch.setattr(service, "fontes_atuais", lambda _fontes: True)

    assumir = _requisicao("post", f"/admin/atendimento/{conversa.pk}/", {"acao": "assumir"})
    assert views.conversa_admin(assumir, conversa.pk).status_code == 302
    conversa.refresh_from_db()
    assert conversa.estado == "andamento" and conversa.atendente_id == "admin-a"
    assert conversa.processar is False
    assert conversa.encerrada_em is None

    referencia = "resposta-equipe-001"
    for texto in ("Resposta inicial.", "Texto repetido deve ser ignorado."):
        responder = _requisicao("post", f"/admin/atendimento/{conversa.pk}/", {
            "acao": "responder", "referencia": referencia, "texto": texto,
        })
        assert views.conversa_admin(responder, conversa.pk).status_code == 302
    conversa.refresh_from_db()
    mensagem = conversa.mensagens.get(referencia=referencia)
    assert mensagem.autor == "equipe" and mensagem.texto == "Resposta inicial."
    assert conversa.mensagens.filter(referencia=referencia).count() == 1
    assert conversa.primeira_resposta_em == mensagem.criada_em

    encerrar = _requisicao("post", f"/admin/atendimento/{conversa.pk}/", {"acao": "encerrar"})
    assert views.conversa_admin(encerrar, conversa.pk).status_code == 302
    conversa.refresh_from_db()
    assert conversa.estado == "encerrado"
    assert conversa.encerrada_em is not None
    assert conversa.processar is False
