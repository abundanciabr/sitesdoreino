"""O admin real da prévia pratica no banco isolado sem matrícula fictícia."""

import pytest
from django.test import RequestFactory

from apps.core import telas_sandbox
from apps.encomendas import catalogo_curso, sandbox
from apps.encomendas.models import MensagemSandbox, ParticipacaoSandbox


@pytest.mark.django_db
def test_admin_da_previa_inicia_pratica_sem_se_passar_por_aluno(monkeypatch):
    site, pessoa = "escola-previa", "admin-real"
    projeto = catalogo_curso.preparar_projetos(site_id=site, ativar=True)[0]
    monkeypatch.setattr(telas_sandbox, "_entrada", lambda request: (site, pessoa))
    monkeypatch.setattr(telas_sandbox, "_aluno_atual",
                        lambda *args: pytest.fail("a prévia não deve fingir matrícula"))
    fabrica = RequestFactory()

    def privado(pedido):
        pedido.previa_trilha_url = "/trilha/previa/"
        pedido.previa_trilha_admin = True
        return pedido

    confirmar = privado(fabrica.get("/trilha/previa/encomendas/sandbox/"))
    assert telas_sandbox.catalogo(confirmar).status_code == 200
    pagina = telas_sandbox.confirmar_projeto(confirmar, projeto.pk)
    assert pagina.status_code == 200
    assert b'name="aceito_termos"' in pagina.content
    assert b'name="prazo_horas"' in pagina.content

    aceitar = privado(fabrica.post("/trilha/previa/encomendas/sandbox/",
                                  {"aceito_termos": "sim", "prazo_horas": "24"}))
    resposta = telas_sandbox.aceitar(aceitar, projeto.pk)
    assert resposta.status_code == 302
    trabalho = ParticipacaoSandbox.objects.get(site_id=site, pessoa_id=pessoa)
    assert trabalho.termos["sem_pagamento"] is True
    assert trabalho.termos["recompensa_tipo"] == "xp"
    assert telas_sandbox._trabalho(privado(fabrica.get("/trilha/previa/")), trabalho.pk)[2] == "admin_previa"
    assert telas_sandbox._pode_testar(privado(fabrica.get("/trilha/previa/"))) is True
    tela = telas_sandbox.trabalho(privado(fabrica.get("/trilha/previa/")), trabalho.pk)
    assert tela.status_code == 200
    assert b'name="destino"' in tela.content
    assert b'name="teste_mantenedor"' in tela.content
    respostas = []
    from apps.core import ia_sandbox
    monkeypatch.setattr(ia_sandbox, "enfileirar",
                        lambda participacao, origem, interlocutor: respostas.append(interlocutor))
    mensagem = privado(fabrica.post("/trilha/previa/encomendas/sandbox/",
                                   {"texto": "Como organizar minha entrega?", "destino": "ambos"}))
    assert telas_sandbox.mensagem(mensagem, trabalho.pk).status_code == 302
    assert list(MensagemSandbox.objects.filter(participacao=trabalho).values_list("papel", flat=True)) == ["equipe"]
    assert respostas == ["ia", "cliente"]

    entregas = []
    monkeypatch.setattr(sandbox, "entregar", lambda **kwargs: entregas.append(kwargs))
    for dados, teste in (({}, False), ({"teste_mantenedor": "sim"}, True)):
        pedido = privado(fabrica.post("/trilha/previa/encomendas/sandbox/", dados))
        assert telas_sandbox.entregar(pedido, trabalho.pk).status_code == 302
        assert entregas[-1]["teste_mantenedor"] is teste

    fora = fabrica.get("/sandbox/")
    assert telas_sandbox._admin_previa(fora) is False
    fora.previa_trilha_url = "/trilha/previa/"
    assert telas_sandbox._admin_previa(fora) is False
