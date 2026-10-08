from copy import deepcopy
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.core.nps_painel import preparar_painel
from tests.test_crm_satisfacao import entrar, ambiente, QUIZ


def avaliacao():
    return {"id": "pesquisa-1", "aluno_id": "aluno-1", "status": "concluida",
        "aluno": {"nome": "Aluno da prova", "email": "aluno@example.test"}, "curso": {"nome": "Modelagem 3D"},
        "concluida_em": "2026-10-08T15:00:00Z", "config_documento": {"roteiro": "revisado"},
        "respostas": {"R12": 10, "R13": "Gostei das aulas práticas."},
        "respostas_legiveis": [
            {"pergunta_id": "R12", "pergunta": "Quanto recomenda?", "valor": 10, "resposta": "10"},
            {"pergunta_id": "A1", "pergunta": "Quando viu aulas?", "resposta": "Viu aula no último mês"},
            {"pergunta_id": "R2", "pergunta": "Está satisfeito?", "resposta": "Satisfeito"},
            {"pergunta_id": "A3", "pergunta": "Quais problemas?", "resposta": "Nenhum"},
            {"pergunta_id": "A8", "pergunta": "Quer continuar?", "resposta": "Quero continuar"},
            {"pergunta_id": "R11", "pergunta": "O que falou?", "resposta": "Não recomendou nem falou contra"},
            {"pergunta_id": "R13", "pergunta": "Comentário?", "resposta": "Gostei das aulas práticas."},
        ],
        "resultado": {"retrato": "Promotor em potencial", "nps": 10, "pessoa_respondente": "aluno_pagante",
                      "motivos": ["Declarou satisfação, ainda sem recomendação a favor."],
                      "leituras": {"satisfacao": {"valor": "Satisfeito", "estado": "declarada"},
                                   "boca_a_boca": {"valor": "Nenhum", "estado": "declarada"},
                                   "continuidade": {"valor": "Fica", "estado": "declarada"},
                                   "reclamacao": {"valor": "Nenhuma", "estado": "declarada"}}}}


def fontes(item=None):
    item = item or avaliacao()
    lista = respx.get(QUIZ + "/interno/nps/respondentes").mock(return_value=httpx.Response(200, json={
        "alunos": 1, "total": 1, "pagina": 1, "paginas": 1, "itens": [{
            "id": item["id"], "aluno_id": item["aluno_id"], "nome": item["aluno"]["nome"],
            "curso": item["curso"]["nome"], "retrato": item["resultado"]["retrato"], "motivo": item["resultado"]["motivos"][0]}]}))
    historico = respx.get(QUIZ + "/interno/nps/historico").mock(return_value=httpx.Response(200, json={
        "avaliacoes": [item], "atendimentos": []}))
    return lista, historico


@respx.mock
def test_painel_mostra_respostas_abertas_motivos_e_nota_independente():
    fontes()
    resposta = entrar().get(reverse("crm_satisfacao"), {"site_id": "escola", "aluno_id": "aluno-1"})
    assert resposta.status_code == 200
    texto = resposta.content.decode()
    for esperado in ("Aluno da prova", "Promotor em potencial", "10/10", "O que ele respondeu", "Por que este retrato",
                     "Declarou satisfação, ainda sem recomendação a favor.", "Ainda não recomendou", "Quer continuar",
                     "Gostei das aulas práticas.", "08/10/2026 12:00", "A nota é independente", "Sem atendimento registrado"):
        assert esperado in texto
    assert 'name="pergunta__' not in texto and 'name="responsavel"' not in texto
    assert len(resposta.context["painel"]["respostas"]) == 7
    assert 'class="valor"' in texto
    assert reverse("crm_satisfacao_gestao") in texto
    assert "Lucas Ferreira" not in texto and "Exemplo fictício" not in texto
    assert "sha256-" in resposta.headers["Content-Security-Policy"]


@respx.mock
def test_sem_selecao_abre_primeira_resposta_e_busca_preserva_site():
    lista, historico = fontes()
    resposta = entrar().get(reverse("crm_satisfacao"), {"site_id": "escola", "q": "Aluno"})
    assert resposta.context["painel"]["id"] == "pesquisa-1"
    assert historico.calls.last.request.url.params["aluno_id"] == "aluno-1"
    assert lista.calls.last.request.url.params["q"] == "Aluno"
    assert lista.calls.last.request.url.params["site_id"] == "escola"
    item = resposta.context["itens"][0]
    assert item["ativo"]
    params = parse_qs(urlsplit(item["url"]).query)
    assert params["avaliacao"] == ["pesquisa-1"] and params["site_id"] == ["escola"]


@respx.mock
def test_selecao_de_outra_avaliacao_nao_mistura_curso_nem_atendimento():
    _, historico = fontes()
    outra = deepcopy(avaliacao())
    outra.update(id="pesquisa-2", curso={"nome": "Outro curso"})
    outra["resultado"].update(retrato="Detrator", nps=0, motivos=["Falou contra e não declarou satisfação."])
    historico.mock(return_value=httpx.Response(200, json={"avaliacoes": [avaliacao(), outra], "atendimentos": [
        {"tentativa_id": "pesquisa-1", "status": "aberto", "proximo_passo": "Não pertence à selecionada"},
        {"tentativa_id": "pesquisa-2", "status": "em_andamento", "responsavel": "Equipe", "proximo_passo": "Contato referente ao outro curso"}]}))
    resposta = entrar().get(reverse("crm_satisfacao"), {"site_id": "escola", "aluno_id": "aluno-1", "avaliacao": "pesquisa-2"})
    texto = resposta.content.decode()
    assert resposta.context["painel"]["curso"] == "Outro curso"
    assert "0/10" in texto and "Contato referente ao outro curso" in texto
    assert "Não pertence à selecionada" not in texto
    invalida = entrar().get(reverse("crm_satisfacao"), {"site_id": "escola", "aluno_id": "aluno-1", "avaliacao": "pesquisa-de-outro-aluno"})
    assert invalida.context["painel"] is None and "Esta avaliação não foi encontrada" in invalida.content.decode()


def test_revisao_e_conflito_mantem_original_visivel_sem_reclassificar():
    original = avaliacao()
    original["revisoes"] = [{"tipo": "fato"}]
    original["resultado_atual"] = {"retrato": "A conferir", "nps": 0, "suspenso": True,
        "motivos": ["Pergunta precisa de esclarecimento."], "sinais": [{"motivo": "Continuidade não esclarecida"}],
        "leituras": {"continuidade": {"valor": "Sai", "valor_declarado": "Fica", "estado": "em_conflito",
                         "fonte": {"fonte": "Atendimento", "referencia": "Registro 123"}}}}
    respostas = deepcopy(original["respostas"])
    painel = preparar_painel(original)
    assert painel["retrato"] == "A conferir" and painel["suspenso"] and painel["nota"] == 0
    assert original["respostas"] == respostas
    assert painel["original"] == "Promotor em potencial" and painel["revisoes"]
    assert painel["evidencias"][0]["origem"] == "Em conflito com o registro"
    assert painel["evidencias"][0]["referencia"] == "Registro 123"
    assert painel["pendencias"] == ["Continuidade não esclarecida"]


@respx.mock
def test_indisponibilidade_nao_vira_aluno_sem_resposta():
    _, historico = fontes()
    historico.mock(return_value=httpx.Response(503))
    texto = entrar().get(reverse("crm_satisfacao"), {"site_id": "escola", "aluno_id": "aluno-1"}).content.decode()
    assert "Não foi possível consultar as respostas" in texto and "Nenhuma avaliação registrada" not in texto
    historico.mock(return_value=httpx.Response(200, json={}))
    texto = entrar().get(reverse("crm_satisfacao"), {"site_id": "escola", "aluno_id": "aluno-1"}).content.decode()
    assert "Não foi possível consultar as respostas" in texto


@respx.mock
def test_configuracao_e_atendimento_sao_telas_separadas_do_painel():
    fontes()
    respx.get(QUIZ + "/interno/nps/config").mock(return_value=httpx.Response(200, json={"documento": {"perguntas": {}, "caminhos": {}}, "versao": 1}))
    cliente = entrar()
    url = reverse("crm_satisfacao_gestao")
    config = cliente.get(url, {"site_id": "escola", "secao": "configuracao"}).content.decode()
    assert "Perguntas e caminhos" in config and "Histórico de satisfação</h2>" not in config
    atendimento = cliente.get(url, {"site_id": "escola", "aluno_id": "aluno-1", "secao": "atendimento"}).content.decode()
    assert 'name="responsavel"' in atendimento and "Perguntas e caminhos" not in atendimento
    hist = cliente.get(url, {"site_id": "escola", "aluno_id": "aluno-1", "secao": "historico"}).content.decode()
    assert "Histórico de satisfação" in hist and "Perguntas e caminhos" not in hist


@respx.mock
def test_painel_exige_admin_e_nao_responde_post():
    for nome in ("crm_satisfacao", "crm_satisfacao_respondentes", "crm_satisfacao_gestao"):
        assert Client().get(reverse(nome)).status_code in (302, 404)
        assert entrar("aluno@example.test").get(reverse(nome)).status_code == 404
    assert entrar().post(reverse("crm_satisfacao")).status_code == 405


def test_detalhe_livre_da_reclamacao_aparece_sem_perder_a_resposta():
    item = avaliacao()
    item["respostas_legiveis"][3].update(resposta="Outro problema", complemento="Não consigo abrir os arquivos de exercício.")
    linha = next(r for r in preparar_painel(item)["respostas"] if r["chave"] == "A3")
    assert linha["resposta"] == "Outro problema"
    assert linha["complemento"] == "Não consigo abrir os arquivos de exercício."
