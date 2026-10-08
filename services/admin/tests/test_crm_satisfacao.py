"""Satisfação no CRM: acesso, leitura honesta e escritas protegidas."""

import httpx
import json
import pytest
import respx
from unittest.mock import MagicMock
from django.test import Client
from django.urls import reverse

from apps.core.nps import anexar_progresso_manual, preparar_avaliacoes


IDENTIDADE = "http://identidade:8000/interno"
QUIZ = "http://quiz:8000"


@pytest.fixture(autouse=True)
def ambiente(monkeypatch, settings):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-identidade")
    monkeypatch.setenv("QUIZ_API_URL", QUIZ)
    monkeypatch.setenv("QUIZ_API_TOKEN", "token-quiz")
    settings.ADMIN_EMAILS = "dono@exemplo.com"
    settings.URL_DE_ENTRADA = "/entrar/google"


def entrar(email="dono@exemplo.com", *, csrf=False):
    respx.get(IDENTIDADE + "/sessao/completa").mock(return_value=httpx.Response(200, json={
        "autenticado": True, "id": "id-dono", "nome_exibido": "Dono", "papel": None, "email": email,
    }))
    cliente = Client(enforce_csrf_checks=csrf)
    cliente.defaults["HTTP_COOKIE"] = "meshcraft_sessao=assinada"
    return cliente


@respx.mock
def test_consulta_mostra_nps_respostas_e_atendimento_sem_uuid_no_titulo():
    cliente = entrar()
    respx.get(QUIZ + "/interno/nps/config").mock(return_value=httpx.Response(200, json={
        "site_id": "principal", "versao": 2, "documento": {"perguntas": {}, "caminhos": {}},
    }))
    respx.get(QUIZ + "/interno/nps/historico").mock(return_value=httpx.Response(200, json={
        "site_id": "principal", "aluno_id": "aluno-1",
        "avaliacoes": [{
            "id": "avaliacao-uuid", "aluno_id": "aluno-1", "curso": {"nome": "Curso de desenho"},
            "resultado": {"nps": 9, "classificacao": "promotor", "motivos": ["Indicou três pessoas"],
                          "repercussao_pontos": 2, "participacao_externa": "não disponível"},
            "respostas_legiveis": [{"pergunta": "O que gostou?", "resposta": "Aulas práticas"}],
            "qualidade": {"estado": "conclusiva", "evidencias": {
                "observacao": "Registros somente deste site.",
                "registros_locais": {"aulas_concluidas": 3, "entregas": 1, "comentarios": 0, "ultima_entrega": None},
            }},
            "config_versao": 2, "calculo_versao": 1,
        }],
        "atendimentos": [{"id": "atendimento-uuid", "status": "aberto", "responsavel": "Ana",
                          "proximo_passo": "Ligar amanhã", "historico": []}],
    }))
    resposta = cliente.get(reverse("crm_satisfacao_gestao"), {"site_id": "principal", "email": "aluna@exemplo.com"})
    assert resposta.status_code == 200
    texto = resposta.content.decode()
    for trecho in ("Curso de desenho", "NPS original:", "Indicou três pessoas", "O que gostou?", "Aulas práticas", "Ligar amanhã", "Aulas concluídas neste site", "Registros somente deste site."):
        assert trecho in texto
    assert "Avaliação avaliacao-uuid" not in texto
    assert "{'aulas_concluidas':" not in texto


@respx.mock
def test_servico_fora_do_ar_nao_vira_historico_vazio():
    cliente = entrar()
    respx.get(QUIZ + "/interno/nps/config").mock(side_effect=httpx.ConnectError("offline"))
    respx.get(QUIZ + "/interno/nps/historico").mock(side_effect=httpx.ConnectError("offline"))
    resposta = cliente.get(reverse("crm_satisfacao_gestao"), {"site_id": "principal", "email": "aluna@exemplo.com"})
    assert resposta.status_code == 200
    texto = resposta.content.decode()
    assert "não significa que não houve avaliações" in texto
    assert "Nenhuma avaliação registrada" not in texto


@respx.mock
def test_somente_admin_e_post_exige_csrf():
    cliente = entrar("estranho@exemplo.com")
    assert cliente.get(reverse("crm_satisfacao_gestao"), {"site_id": "principal"}).status_code == 404
    cliente = entrar(csrf=True)
    resposta = cliente.post(reverse("crm_satisfacao_config_salvar"), {"site_id": "principal", "documento": "{}"})
    assert resposta.status_code == 403


@respx.mock
def test_atendimento_envia_prazo_com_fuso():
    cliente = entrar()
    chamada = respx.post(QUIZ + "/interno/nps/atendimentos").mock(return_value=httpx.Response(201, json={
        "atendimento": {"id": "1"},
    }))
    resposta = cliente.post(reverse("crm_satisfacao_atendimento_salvar"), {
        "site_id": "principal", "aluno_id": "aluno-1", "responsavel": "Ana",
        "proximo_passo": "Ligar", "prazo": "2026-10-07T15:30", "status": "aberto",
    })
    assert resposta.status_code == 302
    assert chamada.called
    assert chamada.calls[0].request.read().decode().find('2026-10-07T15:30:00-03:00') >= 0


@respx.mock
def test_editor_simples_preserva_identificadores_valores_e_calculo():
    cliente = entrar()
    documento = {"perguntas": {
        "gargalo": {"texto": "Gargalo antigo", "tipo": "escolha", "opcoes": [
            {"valor": "pedagogico", "texto": "Pedagógico"}, {"valor": "tecnologico", "texto": "Tecnológico"}], "obrigatoria": True},
        "concorrente": {"texto": "Concorrente antigo", "tipo": "texto", "opcoes": [], "obrigatoria": True},
        "comentario": {"texto": "Comentário antigo", "tipo": "texto", "opcoes": [], "obrigatoria": False},
    }, "caminhos": {"7-8": ["gargalo", "concorrente", "comentario"]},
        "calculo": {"evangelismo": {"mais_3": 2, "1_2": 1, "nenhuma": 0}}}
    respx.get(QUIZ + "/interno/nps/config").mock(return_value=httpx.Response(200, json={
        "site_id": "principal", "versao": 4, "documento": documento,
    }))
    chamada = respx.post(QUIZ + "/interno/nps/config").mock(return_value=httpx.Response(200, json={
        "site_id": "principal", "versao": 5, "documento": documento,
    }))
    resposta = cliente.post(reverse("crm_satisfacao_config_salvar"), {
        "site_id": "principal", "modo": "perguntas",
        "pergunta__gargalo": "Qual gargalo novo?", "opcao__gargalo__pedagogico": "Ensino",
        "opcao__gargalo__tecnologico": "Tecnologia", "pergunta__concorrente": "Concorrente novo?",
        "pergunta__comentario": "Comentário novo?", "caminho__7-8__0": "concorrente",
        "caminho__7-8__1": "gargalo", "caminho__7-8__2": "comentario",
    })
    assert resposta.status_code == 302
    assert chamada.called
    enviado = json.loads(chamada.calls[0].request.read())["documento"]
    assert enviado["perguntas"]["gargalo"]["texto"] == "Qual gargalo novo?"
    assert enviado["perguntas"]["gargalo"]["tipo"] == "escolha"
    assert [opcao["valor"] for opcao in enviado["perguntas"]["gargalo"]["opcoes"]] == ["pedagogico", "tecnologico"]
    assert [opcao["texto"] for opcao in enviado["perguntas"]["gargalo"]["opcoes"]] == ["Ensino", "Tecnologia"]
    assert enviado["caminhos"]["7-8"] == ["concorrente", "gargalo", "comentario"]
    assert enviado["calculo"] == documento["calculo"]
    assert documento["perguntas"]["gargalo"]["texto"] == "Gargalo antigo"


@respx.mock
def test_editar_atendimento_preenche_formulario_sem_expor_id():
    cliente = entrar()
    respx.get(QUIZ + "/interno/nps/config").mock(return_value=httpx.Response(200, json={
        "site_id": "principal", "versao": 1, "documento": {"perguntas": {}, "caminhos": {}},
    }))
    respx.get(QUIZ + "/interno/nps/historico").mock(return_value=httpx.Response(200, json={
        "site_id": "principal", "aluno_id": "aluno-1",
        "avaliacoes": [{"id": "tentativa-1", "aluno_id": "aluno-1", "curso": {"nome": "Desenho"}}],
        "atendimentos": [{"id": "atendimento-1", "aluno_id": "aluno-1", "tentativa_id": "tentativa-1",
                          "responsavel": "Ana", "proximo_passo": "Ligar amanhã", "prazo": "2026-10-07T18:30:00+00:00",
                          "solucao": "Aguardando", "status": "em_andamento"}],
    }))
    resposta = cliente.get(reverse("crm_satisfacao_gestao"), {
        "site_id": "principal", "email": "aluna@exemplo.com", "atendimento": "atendimento-1",
    })
    assert resposta.status_code == 200
    texto = resposta.content.decode()
    assert 'name="responsavel" value="Ana"' in texto
    assert 'name="prazo" type="datetime-local" value="2026-10-07T15:30"' in texto
    assert '<textarea name="proximo_passo" required maxlength="2000">Ligar amanhã</textarea>' in texto
    assert '<input type="hidden" name="atendimento_id" value="atendimento-1">' in texto
    assert 'name="site_id" value="principal" required' not in texto


@respx.mock
def test_editor_simples_exibe_recusa_da_api_sem_erro_interno():
    cliente = entrar()
    documento = {"perguntas": {"comentario": {"texto": "Conte mais", "tipo": "texto", "opcoes": []}},
                 "caminhos": {"7-8": ["comentario"]}}
    respx.get(QUIZ + "/interno/nps/config").mock(return_value=httpx.Response(200, json={
        "site_id": "principal", "versao": 1, "documento": documento,
    }))
    respx.post(QUIZ + "/interno/nps/config").mock(return_value=httpx.Response(400, json={
        "detail": "Documento NPS inválido.",
    }))
    resposta = cliente.post(reverse("crm_satisfacao_config_salvar"), {
        "site_id": "principal", "modo": "perguntas", "pergunta__comentario": "Conte ainda mais",
        "caminho__7-8__0": "comentario",
    })
    assert resposta.status_code == 400
    assert "Documento NPS inválido." in resposta.content.decode()


@respx.mock
def test_roteiro_revisado_mostra_quatro_leituras_sem_converter_nps_antigo():
    cliente = entrar()
    documento = {"roteiro": "revisado", "settings": {"publico": "adultos", "compra": "unica", "ajuda": "forum"},
                 "textos": {"abertura": "Conte como foi"},
                 "perguntas": {"A3": {"texto": "O que aconteceu?", "tipo": "multipla", "opcoes": []}},
                 "situacoes": {"aluno_pagante": [{"id": "outra", "texto": "Outra situação (escreva)",
                                                        "tipo": "escola", "bloco": "No fim"}]}}
    respx.get(QUIZ + "/interno/nps/config").mock(return_value=httpx.Response(200, json={
        "site_id": "principal", "versao": 3, "documento": documento,
    }))
    respx.get(QUIZ + "/interno/nps/historico").mock(return_value=httpx.Response(200, json={
        "site_id": "principal", "aluno_id": "aluno-1", "atendimentos": [], "avaliacoes": [
            {"id": "revisada-1", "aluno_id": "aluno-1", "curso": {"nome": "Blender"},
             "config_documento": documento, "config_versao": 3, "calculo_versao": 2,
             "respostas": {"A3": {"valor": ["outra"]}},
             "resultado": {"nps": 8, "retrato": "Em risco por problema", "pessoa_respondente": "aluno_pagante",
                           "leituras": {"satisfacao": {"valor": "Morno", "estado": "declarada", "fonte": None},
                                        "reclamacao": {"valor": "Em aberto", "estado": "declarada", "fonte": None},
                                        "continuidade": {"valor": "Fica", "estado": "declarada", "fonte": None},
                                        "boca_a_boca": {"valor": "Nenhum", "estado": "declarada", "fonte": None}},
                           "sinais": [{"codigo": "outra_situacao", "motivo": "Aguardando revisão"}],
                           "provisorio": True, "suspenso": False},
             "qualidade": {"tempos_perguntas": [{"pergunta_id": "A3", "duracao_segundos": 5.2}]},
            },
            {"id": "antiga-1", "aluno_id": "aluno-1", "curso": {"nome": "Outro"},
             "config_documento": {"perguntas": {}}, "resultado": {"nps": 9, "classificacao": "Promotor antigo"}},
        ],
    }))
    respx.get(QUIZ + "/interno/nps/revisao").mock(return_value=httpx.Response(200, json={
        "fatos_disponiveis": {"registros_locais": {"aulas_concluidas": 2}}, "revisoes": [],
        "perguntas_pendentes_revisao": [{"id": "A8", "texto": "Quer continuar?", "tipo": "escolha",
                                         "opcoes": [{"valor": "sim", "texto": "Quero continuar"}]}],
    }))
    resposta = cliente.get(reverse("crm_satisfacao_gestao"), {
        "site_id": "principal", "email": "aluno@exemplo.com", "revisao": "revisada-1",
    })
    assert resposta.status_code == 200
    texto = resposta.content.decode()
    for trecho in ("Aluno que pagou o curso", "Em risco por problema", "Satisfação", "Reclamação",
                   "Continuidade", "Boca a boca", "provisório", "somente medição", "Roteiro anterior",
                   "Promotor antigo", "Conferir retrato, fatos e perguntas", "Classificar “Outra situação”",
                   "Quer continuar?", "Aulas concluídas neste site"):
        assert trecho in texto
    assert "Participação na Hotmart/Herospark não está disponível" in texto


@respx.mock
def test_editor_revisado_muda_textos_e_preserva_settings_e_tipos():
    cliente = entrar()
    documento = {"roteiro": "revisado", "settings": {"publico": "adultos", "compra": "unica", "ajuda": "forum"},
                 "textos": {"abertura": "Antes"}, "perguntas": {
                     "A3": {"texto": "O que houve?", "tipo": "multipla", "opcoes": [], "obrigatoria": True},
                     "A8": {"texto": "Quer continuar?", "tipo": "escolha", "opcoes": [], "obrigatoria": True,
                            "variantes": {"nenhuma": {"texto": "Quer começar?", "opcoes": [
                                {"valor": "sim", "texto": "Quero começar"}]}}}},
                 "situacoes": {"aluno_pagante": [{"id": "outra", "texto": "Outra situação", "tipo": "escola", "bloco": "No fim"}]}}
    respx.get(QUIZ + "/interno/nps/config").mock(return_value=httpx.Response(200, json={
        "site_id": "principal", "versao": 1, "documento": documento,
    }))
    chamada = respx.post(QUIZ + "/interno/nps/config").mock(return_value=httpx.Response(200, json={
        "site_id": "principal", "versao": 2, "documento": documento,
    }))
    resposta = cliente.post(reverse("crm_satisfacao_config_salvar"), {
        "site_id": "principal", "modo": "perguntas", "pergunta__A3": "Quais situações aconteceram?",
        "pergunta__A8": "Quer seguir?", "pergunta_variante__A8__nenhuma": "Quer iniciar?",
        "opcao_variante__A8__nenhuma__sim": "Sim, quero iniciar",
        "situacao__aluno_pagante__outra": "Outra coisa (escreva)", "ajuste__textos__abertura": "Agora",
    })
    assert resposta.status_code == 302
    enviado = json.loads(chamada.calls[0].request.read())["documento"]
    assert enviado["roteiro"] == "revisado"
    assert enviado["settings"] == documento["settings"]
    assert enviado["perguntas"]["A3"] == {"texto": "Quais situações aconteceram?", "tipo": "multipla", "opcoes": [], "obrigatoria": True}
    assert enviado["situacoes"]["aluno_pagante"][0]["tipo"] == "escola"
    assert enviado["situacoes"]["aluno_pagante"][0]["texto"] == "Outra coisa (escreva)"
    assert enviado["textos"]["abertura"] == "Agora"
    assert enviado["perguntas"]["A8"]["variantes"]["nenhuma"]["texto"] == "Quer iniciar?"
    assert enviado["perguntas"]["A8"]["variantes"]["nenhuma"]["opcoes"] == [
        {"valor": "sim", "texto": "Sim, quero iniciar"}]


@respx.mock
def test_revisao_manual_exige_fonte_e_referencia_juntas():
    cliente = entrar()
    endereco = reverse("crm_satisfacao_revisao_salvar")
    base = {"site_id": "principal", "aluno_id": "aluno-1", "tentativa_id": "tentativa-1",
            "situacao_id": "outra", "tipo": "opiniao", "email": "aluno@exemplo.com"}
    resposta = cliente.post(endereco, {**base, "fonte": "fórum"})
    assert resposta.status_code == 400
    assert "fonte e a referência juntas" in resposta.content.decode()
    chamada = respx.post(QUIZ + "/interno/nps/revisao").mock(return_value=httpx.Response(201, json={
        "revisao": {"id": 1}, "avaliacao": {},
    }))
    resposta = cliente.post(endereco, {**base, "fonte": "fórum", "referencia": "chamado 123"})
    assert resposta.status_code == 302
    enviado = json.loads(chamada.calls[0].request.read())
    assert enviado["tipo"] == "opiniao"
    assert enviado["prova"] == {"fonte": "fórum", "referencia": "chamado 123"}


@respx.mock
def test_revisao_de_fato_exige_prova_e_preserva_valor_confirmado():
    cliente = entrar()
    chamada = respx.post(QUIZ + "/interno/nps/revisao").mock(return_value=httpx.Response(201, json={
        "revisao": {"id": 2}, "avaliacao": {},
    }))
    base = {"site_id": "principal", "aluno_id": "aluno-1", "tentativa_id": "tentativa-1",
            "situacao_id": "continuidade", "tipo": "fato", "valor": "Concluiu"}
    assert cliente.post(reverse("crm_satisfacao_revisao_salvar"), {**base, "fonte": "fórum"}).status_code == 400
    assert not chamada.called
    resposta = cliente.post(reverse("crm_satisfacao_revisao_salvar"), {
        **base, "fonte": "atendimento da escola", "referencia": "chamado 123",
    })
    assert resposta.status_code == 302
    assert json.loads(chamada.calls[0].request.read())["prova"] == {
        "fonte": "atendimento da escola", "referencia": "chamado 123", "valor": "Concluiu",
    }


@respx.mock
def test_esclarecimento_viva_voz_mantem_multiplas_respostas_e_complemento():
    cliente = entrar()
    chamada = respx.post(QUIZ + "/interno/nps/revisao").mock(return_value=httpx.Response(201, json={
        "revisao": {"id": 3}, "avaliacao": {},
    }))
    resposta = cliente.post(reverse("crm_satisfacao_revisao_salvar"), {
        "site_id": "principal", "aluno_id": "aluno-1", "tentativa_id": "tentativa-1",
        "situacao_id": "A3", "tipo": "esclarecimento", "valor": ["sem_tempo", "outra"],
        "complemento": "Outra dificuldade contada na conversa", "referencia": "ligação de 7/10",
    })
    assert resposta.status_code == 302
    assert json.loads(chamada.calls[0].request.read())["prova"] == {
        "fonte": "entrevista", "referencia": "ligação de 7/10",
        "valor": ["sem_tempo", "outra"], "complemento": "Outra dificuldade contada na conversa",
    }


def test_leituras_revisadas_traduzem_fonte_prova_e_valor_declarado():
    historico = {"avaliacoes": [{"config_documento": {"roteiro": "revisado"}, "resultado": {
        "retrato": "Em risco", "pessoa_respondente": "aluno_pagante"}, "resultado_atual": {
        "retrato": "A conferir", "pessoa_respondente": "aluno_pagante",
        "leituras": {"ponto_curso": {"valor": "recente", "valor_declarado": "nenhuma",
                                    "estado": "em_conflito", "fonte": {"fonte": "atendimento", "referencia": "chamado 123"}}},
    }}]}
    leitura = preparar_avaliacoes(historico)["avaliacoes"][0]["leituras_tela"][0]
    assert leitura == {"nome": "Aulas vistas", "valor": "Viu aula no último mês",
                      "valor_declarado": "Não assistiu a nenhuma aula", "estado": "em_conflito",
                      "fonte": "atendimento · chamado 123"}


def test_progresso_manual_busca_mesmo_site_email_e_produto(monkeypatch):
    from apps.core.acompanhamento_modelo import RegistroAcompanhamentoAluno

    registro = MagicMock(progresso_externo="Aula 2 vista", fonte="anotação do suporte", criado_em="2026-10-07")
    consulta = MagicMock()
    consulta.exclude.return_value = consulta
    consulta.order_by.return_value.__getitem__.return_value = [registro]
    filtro = MagicMock(return_value=consulta)
    monkeypatch.setattr(RegistroAcompanhamentoAluno.objects, "filter", filtro)
    historico = {"avaliacoes": [{"aluno": {"email": "Pessoa@Exemplo.com"}, "produto": {"id": "curso-1"}}]}
    anexar_progresso_manual(historico, "principal")
    filtro.assert_called_once_with(site_id="principal", email__iexact="Pessoa@Exemplo.com", product_id="curso-1")
    assert historico["avaliacoes"][0]["evidencias_externas_tela"][0]["fonte"] == "anotação do suporte"
