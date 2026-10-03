"""Criação conversacional, escolhas persistidas e isolamento dos rascunhos."""

import copy
import json

import httpx
import pytest
import respx
from django.http import QueryDict
from django.urls import reverse

from apps.agentes import conversa, executor, ferramentas, trabalhos
from apps.agentes.models import ChamadaDeFerramenta, Execucao, Mensagem
from apps.agentes.quiz_guiado import montar_pergunta, responder_pergunta
from test_robo_no_quiz import (
    QUIZ, RESPOSTAS, S, _admin, _cliente, _conferencia, _guardar_chave,
    _pedido_de_acao, _quiz_da_pagina, _site, _texto_do_modelo, ambiente,
)

pytestmark = pytest.mark.django_db


def _pedido(guiado=True):
    membro = _admin()
    robo = trabalhos.robo_de(membro)
    _, execucao = trabalhos.pedir_resposta(
        robo, membro, "Criar quiz", chave="inicio", autor=membro.nome,
        contexto={"host": "testserver", "quiz": "encontre", "pagina": "campanhas", "guiado": guiado},
    )
    return ferramentas.Contexto(robo, membro, execucao)


def _pergunta(tipo="radio"):
    return {"pergunta": "Qual nome você prefere?", "tipo": tipo,
            "opcoes": ["Meu próximo passo", "Caminho para crescer", "Comece pelo 3D"],
            "ajuda": "Pode escolher um ou escrever outro.", "aceita_outro": True,
            "outro_rotulo": "Prefiro informar outro nome"}


def _documento():
    return {
        "formato": "quiz-low-ticket/2", "quiz": {"slug": "novo-quiz", "title": "Meu próximo passo"},
        "ofertas": [{"id": "base", "nome": "Primeiros passos", "checkout_url": None},
                    {"id": "avanco", "nome": "Avançar", "checkout_url": None}],
        "versoes": [{"key": "A", "default_format": "text", "formats": {
            "text": {"headline": "Descubra seu próximo passo", "subheadline": "Uma pergunta rápida."}},
            "segments": {}, "perguntas": [{"id": "momento", "texto": "Em que momento você está?", "opcoes": [
                {"id": "inicio", "texto": "Estou começando", "pontos": 0},
                {"id": "pratica", "texto": "Já tenho prática", "pontos": 1}]}],
            "faixas": [{"key": "inicio", "title": "Comece pela base", "description": "Seu primeiro passo.",
                "min_score": 0, "max_score": 0, "oferta_id": "base", "botao_rotulo": "Ver primeiros passos"},
                {"key": "avanco", "title": "Avance", "description": "Seu próximo passo.",
                "min_score": 1, "max_score": 1, "oferta_id": "avanco", "botao_rotulo": "Ver como avançar"}]}],
    }


@respx.mock
def test_a_pergunta_encerra_a_rodada_e_a_escolha_vira_memoria_da_conversa():
    _guardar_chave()
    _site()
    ctx = _pedido()
    respx.get(QUIZ + "/conferencia").mock(return_value=httpx.Response(200, json=_conferencia()))
    rota = respx.post(RESPOSTAS).mock(return_value=_pedido_de_acao("perguntar_com_opcoes", _pergunta()))
    executor.rodar_uma("teste")
    ctx.execucao.refresh_from_db()
    assert ctx.execucao.situacao == S.CONCLUIDA
    assert rota.call_count == 1  # Pergunta exibida sem gastar outra rodada de IA.
    mensagem = Mensagem.objects.get(execucao=ctx.execucao, papel="robo")
    assert ctx.execucao.estado["pergunta_guiada"]["opcoes"][0]["rotulo"] == "Meu próximo passo"
    cliente = _cliente()
    _quiz_da_pagina()
    pagina = cliente.get(reverse("quiz_campanhas", args=["encontre"]))
    assert b'data-pergunta-robo' in pagina.content and b'type="radio"' in pagina.content
    assert "Prefiro informar outro nome" in pagina.content.decode()
    resposta = cliente.post(reverse("quiz_campanhas_robo", args=["encontre"]), {
        "acao": "responder_opcoes", "pergunta_id": mensagem.id, "resposta": "outro",
        "resposta_livre": "Meu nome personalizado", "chave": "resposta-1",
    })
    assert resposta.status_code == 302
    nova = Execucao.objects.latest("id")
    assert "Meu nome personalizado" in nova.pedido and nova.estado["contexto"]["resposta_guiada"]
    historico = conversa._historico(nova)
    assert "Meu próximo passo" in historico[-2]["content"]
    assert "Meu nome personalizado" in historico[-1]["content"]
    anterior = Execucao.objects.count()
    cliente.post(reverse("quiz_campanhas_robo", args=["encontre"]), {
        "acao": "responder_opcoes", "pergunta_id": mensagem.id, "resposta": "0", "chave": "fora-de-ordem",
    })
    assert Execucao.objects.count() == anterior


@respx.mock
def test_checkbox_select_e_texto_e_opcoes_que_nao_foram_oferecidas():
    ctx = _pedido()
    for tipo, entrada, esperado in [
        ("checkbox", "resposta=0&resposta=2", "Meu próximo passo; Comece pelo 3D"),
        ("select", "resposta=1", "Caminho para crescer"),
        ("texto", "resposta_livre=Meu+objetivo", "Meu objetivo"),
    ]:
        ctx.execucao.estado["pergunta_guiada"] = montar_pergunta(_pergunta(tipo))
        ctx.execucao.save(update_fields=["estado"])
        mensagem = Mensagem.objects.create(conversa=ctx.execucao.conversa, execucao=ctx.execucao, papel="robo", texto="Escolha")
        post = QueryDict(entrada + f"&pergunta_id={mensagem.id}")
        texto, _ = responder_pergunta(ctx.robo, "encontre", post)
        assert texto.endswith(esperado)
    ctx.execucao.estado["pergunta_guiada"] = montar_pergunta(_pergunta())
    ctx.execucao.save(update_fields=["estado"])
    with pytest.raises(ValueError, match="opções"):
        responder_pergunta(ctx.robo, "encontre", QueryDict(f"pergunta_id={mensagem.id}&resposta=inventada"))
    from apps.core.models import MembroDaEquipe
    outra_pessoa = trabalhos.robo_de(MembroDaEquipe.objects.get(nome="Ryan"))
    with pytest.raises(ValueError, match="não está disponível"):
        responder_pergunta(outra_pessoa, "encontre", QueryDict(f"pergunta_id={mensagem.id}&resposta=0"))


@respx.mock
def test_inicio_novo_preserva_historico_e_comeca_outra_coleta():
    ctx = _pedido()
    cliente = _cliente()
    cliente.post(reverse("quiz_campanhas_robo", args=["encontre"]), {
        "acao": "iniciar", "fluxo": "campanha", "chave": "nova-campanha",
    })
    nova = Execucao.objects.latest("id")
    assert nova.estado["contexto"]["fluxo"] == "campanha"
    assert "2 a 3 nomes" in nova.pedido
    assert len(conversa._historico(nova)) == 1
    assert Mensagem.objects.filter(execucao=ctx.execucao).exists()


@respx.mock
def test_criar_quiz_nao_sobrescreve_o_que_ja_existe_e_repete_sem_duplicar():
    ctx = _pedido()
    _site()
    lista = respx.get(QUIZ.rsplit("/", 1)[0]).mock(return_value=httpx.Response(200, json={"items": [
        {"slug": "meu-proximo-passo", "title": "Outra campanha"}]}))
    respx.get(QUIZ.rsplit("/", 1)[0] + "/meu-proximo-passo/rascunho").mock(
        return_value=httpx.Response(200, json={"content": {"quiz": {"title": "Existente"}}}))
    rota = respx.put(QUIZ.rsplit("/", 1)[0] + "/meu-proximo-passo-2/rascunho").mock(
        return_value=httpx.Response(200, json={"has_draft": True}))
    args = {"slug": None, "modo": "novo", "usar_ofertas_do_quiz_atual": False,
            "documento_json": json.dumps(_documento())}
    primeiro = json.loads(ferramentas.executar(ctx, "criar-1", "criar_rascunho_do_quiz", json.dumps(args)))
    repetido = json.loads(ferramentas.executar(ctx, "criar-1", "criar_rascunho_do_quiz", json.dumps(args)))
    assert primeiro == repetido and primeiro["salvo"]
    assert primeiro["slug"] == "meu-proximo-passo-2" and primeiro["perguntas"] == 1
    assert rota.call_count == 1 and lista.call_count == 1
    enviado = json.loads(rota.calls[0].request.content)
    assert enviado["quiz"]["slug"] == primeiro["slug"]
    assert enviado["versoes"][0]["perguntas"][0]["texto"] == "Em que momento você está?"
    assert ChamadaDeFerramenta.objects.get(execucao=ctx.execucao).situacao == "feita"


@respx.mock
def test_nova_versao_preserva_ofertas_e_todas_as_perguntas_anteriores():
    ctx = _pedido()
    _site()
    anterior = _documento()
    anterior["quiz"]["slug"] = "encontre"
    anterior["versoes"][0]["key"] = "B2"
    anterior["ofertas"][0]["checkout_url"] = "https://testserver/checkout/base/"
    original = copy.deepcopy(anterior)
    respx.get(QUIZ + "/rascunho").mock(return_value=httpx.Response(200, json={"content": anterior}))
    rota = respx.put(QUIZ + "/rascunho").mock(return_value=httpx.Response(200, json={"has_draft": True}))
    novo = _documento()
    novo["versoes"][0]["key"] = "B2"
    novo["versoes"][0]["perguntas"][0]["texto"] = "Qual seu objetivo?"
    resultado = ferramentas.criar_rascunho_do_quiz(ctx, {"slug": None, "modo": "nova_versao",
        "usar_ofertas_do_quiz_atual": True, "documento_json": json.dumps(novo)})
    enviado = json.loads(rota.calls[0].request.content)
    assert enviado["ofertas"] == original["ofertas"]
    assert enviado["versoes"][0] == original["versoes"][0]
    assert enviado["versoes"][1]["key"] == "B3"
    assert resultado["estudio_url"].endswith("/conteudos/quiz/encontre/")


@respx.mock
def test_andamento_traz_a_pergunta_sem_recarregar_a_pagina():
    ctx = _pedido()
    ctx.execucao.estado["pergunta_guiada"] = montar_pergunta(_pergunta("checkbox"))
    ctx.execucao.situacao = S.CONCLUIDA
    ctx.execucao.save()
    Mensagem.objects.create(conversa=ctx.execucao.conversa, execucao=ctx.execucao, papel="robo", texto="Escolha")
    resposta = _cliente().get(reverse("quiz_campanhas_robo_andamento", args=["encontre"]), {"chat": "1", "marca": "antiga"})
    dados = resposta.json()
    assert 'type="checkbox"' in dados["conversa_html"] and "Continuar" in dados["conversa_html"]
    assert 'csrfmiddlewaretoken' in dados["conversa_html"]
    assert dados["acompanhar"] is False and dados["conversando"] is False
