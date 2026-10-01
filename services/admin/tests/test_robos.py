"""Os robôs pessoais da equipe (`apps/agentes`), plano-mestre dos robôs.

**Tudo que aqui fala com a OpenAI é SIMULAÇÃO**: as respostas do modelo são
de mentira, montadas com `respx` no formato da Responses API. Estes testes
provam o caminho do sistema (fila, posse, ações no painel, entrega, teto,
retomada), não que o modelo de verdade responde. A prova com a conta real é
feita à parte, no site, e registrada como tal.
"""

from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.agentes import executor, ferramentas, modelo, segredo, trabalhos
from apps.agentes.models import (
    AutorizacaoDeGasto,
    ChamadaDeFerramenta,
    Conexao,
    Consumo,
    Entrega,
    Execucao,
    Mensagem,
    RoboPessoal,
)
from apps.core import equipe_operacoes as operacoes
from apps.core.models import Comentario, MembroDaEquipe, Tarefa

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"
LIVIA = "livia-conta-de-teste@exemplo.com"
RYAN = "ryan-conta-de-teste@exemplo.com"
RESPOSTAS = f"{modelo.URL}/responses"
MODELOS = f"{modelo.URL}/models"
CHAVE = "sk-teste-0000000000000000wxyz"

S = Execucao.Situacao


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


def _cliente(email: str, nome: str = "Fulano") -> Client:
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "id-opaco-123",
                "nome_exibido": nome,
                "papel": None,
                "email": email,
            },
        )
    )
    cliente = Client()
    cliente.defaults["HTTP_COOKIE"] = COOKIE
    return cliente


def _pessoa(nome: str, email: str) -> MembroDaEquipe:
    pessoa = MembroDaEquipe.objects.get(nome=nome)
    pessoa.email = email
    pessoa.save()
    return pessoa


def _guardar_chave(conferida: bool = True) -> Conexao:
    conexao = modelo.conexao()
    conexao.segredo_cifrado = segredo.cifrar(CHAVE)
    conexao.final_da_chave = CHAVE[-4:]
    conexao.situacao = Conexao.Situacao.CONFERIDA if conferida else Conexao.Situacao.A_CONFERIR
    conexao.save()
    return conexao


def _uso(entrada=1000, saida=100):
    return {"input_tokens": entrada, "input_tokens_details": {"cached_tokens": 0}, "output_tokens": saida}


def _texto_do_modelo(texto: str, rid: str = "resp_texto") -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": rid,
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "id": "msg_" + rid,
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": texto}],
                }
            ],
            "usage": _uso(),
        },
    )


def _pedido_de_acao(nome: str, argumentos: dict, call_id: str = "call_1") -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "resp_" + call_id,
            "status": "completed",
            "output": [
                {
                    "type": "function_call",
                    "id": "fc_" + call_id,
                    "call_id": call_id,
                    "name": nome,
                    "arguments": json.dumps(argumentos),
                    "status": "completed",
                }
            ],
            "usage": _uso(),
        },
    )


# ---------------------------------------------------------------- identidade e porta


@respx.mock
def test_a_pessoa_da_equipe_abre_o_proprio_robo_e_ele_persiste():
    livia = _pessoa("Lívia", LIVIA)
    cliente = _cliente(LIVIA, "Lívia")
    resposta = cliente.get(reverse("robo_da_pessoa"))
    assert resposta.status_code == 200
    robo = RoboPessoal.objects.get(membro=livia)
    assert robo.nome == "Robô de Lívia"
    assert "ainda não tem a chave da OpenAI" in resposta.content.decode()
    # Segunda visita: o mesmo robô, não outro.
    cliente.get(reverse("robo_da_pessoa"))
    assert RoboPessoal.objects.filter(membro=livia).count() == 1
    # Trocar o modelo não cria robô novo: o modelo mora na conexão.
    conexao = modelo.conexao()
    conexao.modelo_rapido = "gpt-6-luna-outro"
    conexao.save()
    cliente.get(reverse("robo_da_pessoa"))
    assert RoboPessoal.objects.get(membro=livia).pk == robo.pk


@respx.mock
def test_a_aba_do_robo_aparece_no_painel():
    _pessoa("Lívia", LIVIA)
    resposta = _cliente(LIVIA, "Lívia").get(reverse("painel_da_equipe"))
    assert reverse("robo_da_pessoa") in resposta.content.decode()


@respx.mock
def test_conta_sem_pessoa_ve_explicacao_e_nao_um_robo():
    resposta = _cliente(DONO, "Dono").get(reverse("robo_da_pessoa"))
    assert resposta.status_code == 200
    assert "não está ligada a ninguém" in resposta.content.decode()
    assert not RoboPessoal.objects.exists()


@respx.mock
def test_a_conexao_e_so_do_administrador():
    _pessoa("Lívia", LIVIA)
    assert _cliente(LIVIA, "Lívia").get(reverse("robos_admin")).status_code == 404
    assert _cliente(DONO, "Dono").get(reverse("robos_admin")).status_code == 200


@respx.mock
def test_quem_entra_pelo_aparelho_usa_o_proprio_robo_e_nao_a_conexao():
    """A equipe entra por link no aparelho, sem e-mail: o crachá vale em
    `/equipe/`, e o robô mora lá dentro. A conexão com a OpenAI não."""
    import re

    ryan = MembroDaEquipe.objects.get(nome="Ryan")
    gerou = _cliente(DONO, "Dono").post(reverse("ficha_gerar_link", args=[ryan.id]))
    codigo = re.search(r"/equipe/magic-link\?client=desktop_app#([0-9a-f]{32}):", gerou.content.decode())
    aparelho = Client()
    assert aparelho.post(reverse("magic_link") + "?client=desktop_app", {"codigo": codigo.group(1)}).status_code == 302
    assert aparelho.get(reverse("robo_da_pessoa")).status_code == 200
    assert RoboPessoal.objects.get(membro=ryan).nome == "Robô de Ryan"
    aparelho.post(reverse("delegar_ao_robo"), {"chave": "a1"})
    execucao = Execucao.objects.get(robo__membro=ryan)
    assert execucao.pedido_por_membro_id == ryan.id
    executor.rodar_uma("teste")
    entrega = Entrega.objects.get(execucao=execucao)
    assert aparelho.get(reverse("entrega_do_robo", args=[entrega.id])).status_code == 200
    # Fora de `/equipe/` o aparelho não vale nada: sem sessão, vai ao login.
    respx.get(SESSAO).mock(return_value=httpx.Response(200, json={"autenticado": False}))
    assert aparelho.get(reverse("robos_admin"))["Location"].startswith("/entrar/google")


@respx.mock
def test_a_pagina_do_robo_libera_o_script_por_hash_e_nunca_por_unsafe_inline():
    livia = _pessoa("Lívia", LIVIA)
    robo = trabalhos.robo_de(livia)
    trabalhos.pedir_resposta(robo, livia, "oi", chave="k1", autor="Lívia")
    resposta = _cliente(LIVIA, "Lívia").get(reverse("robo_da_pessoa"))
    politica = resposta["Content-Security-Policy"]
    assert "'sha256-" in politica.split("script-src", 1)[1].split(";", 1)[0]
    assert "unsafe-inline" not in politica
    assert "data-acompanhar" in resposta.content.decode()


# ---------------------------------------------------------------- conversa


@respx.mock
def test_mensagem_repetida_vira_uma_execucao_so():
    livia = _pessoa("Lívia", LIVIA)
    cliente = _cliente(LIVIA, "Lívia")
    for _ in range(2):
        resposta = cliente.post(reverse("mensagem_ao_robo"), {"texto": "minhas tarefas?", "chave": "abc"})
        assert resposta.status_code == 302
    robo = RoboPessoal.objects.get(membro=livia)
    assert Mensagem.objects.filter(conversa__robo=robo, papel="membro").count() == 1
    execucao = Execucao.objects.get(robo=robo)
    assert execucao.situacao == S.NA_FILA
    assert execucao.pedido_por_membro_id == livia.id


def test_sem_chave_a_mensagem_espera_sem_chamar_nada_pago():
    livia = _pessoa("Lívia", LIVIA)
    robo = trabalhos.robo_de(livia)
    _, execucao = trabalhos.pedir_resposta(robo, livia, "oi", chave="k", autor="Lívia")
    with respx.mock(assert_all_called=False) as rede:
        rota = rede.post(RESPOSTAS)
        executor.rodar_uma("teste")
        assert not rota.called
    execucao.refresh_from_db()
    assert execucao.situacao == S.AGUARDANDO_DEPENDENCIA
    assert "chave da OpenAI" in execucao.motivo
    assert Mensagem.objects.filter(execucao=execucao, papel="aviso").exists()
    assert not Consumo.objects.exists()
    # A chave chega e é conferida: o servidor devolve o trabalho à fila sozinho.
    _guardar_chave()
    assert executor.reacordar() == 1
    execucao.refresh_from_db()
    assert execucao.situacao == S.NA_FILA


def test_simulacao_conversa_cria_tarefa_pelas_operacoes_do_painel():
    livia = _pessoa("Lívia", LIVIA)
    ryan = MembroDaEquipe.objects.get(nome="Ryan")
    _guardar_chave()
    robo = trabalhos.robo_de(livia)
    _, execucao = trabalhos.pedir_resposta(
        robo, livia, "cria uma tarefa para o Ryan revisar a aula 3", chave="k", autor="Lívia"
    )
    with respx.mock as rede:
        rota = rede.post(RESPOSTAS).mock(
            side_effect=[
                _pedido_de_acao(
                    "criar_tarefa",
                    {
                        "titulo": "Revisar a aula 3",
                        "descricao": None,
                        "responsavel_id": ryan.id,
                        "objetivo_id": None,
                        "prazo": "2026-10-09",
                        "situacao": None,
                        "impedimento": None,
                    },
                ),
                _texto_do_modelo("Criei a tarefa **Revisar a aula 3** para o Ryan, prazo 09/10."),
            ]
        )
        executor.rodar_uma("teste")
    execucao.refresh_from_db()
    assert execucao.situacao == S.CONCLUIDA, execucao.motivo
    tarefa = Tarefa.objects.get(titulo="Revisar a aula 3")
    assert tarefa.responsavel == ryan
    assert tarefa.criada_por == "Robô de Lívia (a pedido de Lívia)"
    assert ChamadaDeFerramenta.objects.get(execucao=execucao).situacao == "feita"
    resposta = Mensagem.objects.get(execucao=execucao, papel="robo")
    assert "Revisar a aula 3" in resposta.texto
    # O pedido saiu com o modelo rápido, sem guardar nada na OpenAI, com as
    # ações do painel, e a chave só no cabeçalho.
    corpo = json.loads(rota.calls[0].request.content)
    assert corpo["model"] == "gpt-6-luna"
    assert corpo["store"] is False
    assert {f["name"] for f in corpo["tools"]} >= {"criar_tarefa", "consultar_tarefas"}
    assert CHAVE not in rota.calls[0].request.content.decode()
    assert rota.calls[0].request.headers["Authorization"] == f"Bearer {CHAVE}"
    # A segunda rodada devolve o resultado da ação ao modelo.
    segundo = json.loads(rota.calls[1].request.content)
    assert any(i.get("type") == "function_call_output" for i in segundo["input"])
    consumos = Consumo.objects.filter(execucao=execucao)
    assert consumos.count() == 2
    assert all(not c.desconhecido for c in consumos)
    assert consumos.first().custo_estimado_usd == modelo.custo("gpt-6-luna", 1000, 0, 100)


def test_simulacao_retomada_nao_repete_a_acao_ja_feita():
    """O processo caiu DEPOIS de criar a tarefa e ANTES de guardar o fim:
    a retomada acha o pedido já feito pelo `call_id` e não cria outra."""
    livia = _pessoa("Lívia", LIVIA)
    _guardar_chave()
    robo = trabalhos.robo_de(livia)
    _, execucao = trabalhos.pedir_resposta(robo, livia, "cria a tarefa X", chave="k", autor="Lívia")
    chamada = {
        "type": "function_call",
        "id": "fc_1",
        "call_id": "call_1",
        "name": "criar_tarefa",
        "arguments": json.dumps(
            {
                "titulo": "Tarefa X",
                "descricao": None,
                "responsavel_id": None,
                "objetivo_id": None,
                "prazo": None,
                "situacao": None,
                "impedimento": None,
            }
        ),
    }
    # Primeira vida: pegou, guardou o pedido do modelo, fez a ação e "morreu".
    execucao = executor.pegar_uma("trabalhador-que-morreu")
    execucao.estado = {"itens": [{"role": "user", "content": "cria a tarefa X"}, chamada], "rodadas": 1}
    executor.guardar_estado(execucao)
    ctx = ferramentas.Contexto(robo=robo, membro=livia, execucao=execucao)
    ferramentas.executar(ctx, "call_1", "criar_tarefa", chamada["arguments"])
    assert Tarefa.objects.filter(titulo="Tarefa X").count() == 1
    Execucao.objects.filter(pk=execucao.pk).update(ocupada_ate=timezone.now() - timedelta(seconds=1))

    with respx.mock as rede:
        rede.post(RESPOSTAS).mock(return_value=_texto_do_modelo("Criei a Tarefa X."))
        executor.rodar_uma("outro-trabalhador")
    execucao.refresh_from_db()
    assert execucao.situacao == S.CONCLUIDA
    assert Tarefa.objects.filter(titulo="Tarefa X").count() == 1
    assert execucao.registros.filter(texto__startswith="Retomada no servidor").exists()


def test_simulacao_alteracao_com_versao_velha_e_recusada():
    livia = _pessoa("Lívia", LIVIA)
    robo = trabalhos.robo_de(livia)
    tarefa, _ = operacoes.criar_tarefa({"titulo": "Original"}, "Lívia")
    versao_lida = operacoes.versao_de(tarefa)
    # Outra pessoa altera pelo painel depois da leitura do robô.
    operacoes.alterar_tarefa(tarefa.id, {"titulo": "Mudada por outra pessoa"}, "Ryan")
    execucao = Execucao.objects.create(robo=robo, tipo=Execucao.Tipo.CONVERSA, pedido_por_membro_id=livia.id)
    ctx = ferramentas.Contexto(robo=robo, membro=livia, execucao=execucao)
    saida = json.loads(
        ferramentas.executar(
            ctx,
            "call_v",
            "alterar_tarefa",
            json.dumps(
                {
                    "tarefa_id": tarefa.id,
                    "versao": versao_lida,
                    "titulo": "Por cima",
                    "descricao": None,
                    "responsavel_id": None,
                    "objetivo_id": None,
                    "prazo": None,
                    "situacao": None,
                    "impedimento": None,
                }
            ),
        )
    )
    assert "mudou desde que você a leu" in saida["erro"]
    tarefa.refresh_from_db()
    assert tarefa.titulo == "Mudada por outra pessoa"


def test_pessoa_retirada_da_equipe_nao_age_pelo_robo():
    livia = _pessoa("Lívia", LIVIA)
    robo = trabalhos.robo_de(livia)
    execucao = Execucao.objects.create(robo=robo, tipo=Execucao.Tipo.CONVERSA, pedido_por_membro_id=livia.id)
    ctx = ferramentas.Contexto(robo=robo, membro=livia, execucao=execucao)
    MembroDaEquipe.objects.filter(pk=livia.pk).update(ativo=False)
    saida = json.loads(
        ferramentas.executar(ctx, "c", "comentar_tarefa", json.dumps({"tarefa_id": 1, "texto": "oi"}))
    )
    assert "não está mais ativa" in saida["erro"]


# ---------------------------------------------------------------- teto de gasto


def test_o_teto_para_antes_de_chamar():
    livia = _pessoa("Lívia", LIVIA)
    _guardar_chave()
    AutorizacaoDeGasto.objects.update(teto_mensal_usd=Decimal("0.0001"))
    robo = trabalhos.robo_de(livia)
    _, execucao = trabalhos.pedir_resposta(robo, livia, "oi", chave="k", autor="Lívia")
    with respx.mock(assert_all_called=False) as rede:
        rota = rede.post(RESPOSTAS)
        executor.rodar_uma("teste")
        assert not rota.called
    execucao.refresh_from_db()
    assert execucao.situacao == S.AGUARDANDO_AUTORIZACAO


def test_a_autorizacao_do_mantenedor_esta_semeada():
    autorizacao = AutorizacaoDeGasto.objects.get(ativa=True)
    assert autorizacao.teto_mensal_usd == Decimal("10.00")
    assert "Até US$ 10/mês" in autorizacao.fonte


def test_simulacao_resposta_perdida_conta_o_pior_caso():
    livia = _pessoa("Lívia", LIVIA)
    _guardar_chave()
    robo = trabalhos.robo_de(livia)
    _, execucao = trabalhos.pedir_resposta(robo, livia, "oi", chave="k", autor="Lívia")
    with respx.mock as rede:
        rede.post(RESPOSTAS).mock(side_effect=httpx.ReadTimeout("caiu"))
        executor.rodar_uma("teste")
    execucao.refresh_from_db()
    assert execucao.situacao == S.NA_FILA
    assert execucao.nao_antes_de is not None
    reserva = Consumo.objects.get(execucao=execucao)
    assert reserva.desconhecido is True
    assert reserva.custo_estimado_usd > 0


# ---------------------------------------------------------------- panorama


def _tarefas_da_livia(livia):
    hoje = operacoes.hoje()
    operacoes.criar_tarefa(
        {"titulo": "Gravar aula 5", "responsavel": str(livia.id), "prazo": (hoje - timedelta(days=2)).isoformat()},
        "Lívia",
    )
    operacoes.criar_tarefa(
        {
            "titulo": "Esperando render",
            "responsavel": str(livia.id),
            "situacao": "bloqueada",
            "impedimento": "render da cena 2",
        },
        "Lívia",
    )


@respx.mock
def test_panorama_sem_chave_sai_parcial_e_a_pessoa_abre_a_entrega():
    livia = _pessoa("Lívia", LIVIA)
    _tarefas_da_livia(livia)
    cliente = _cliente(LIVIA, "Lívia")
    resposta = cliente.post(reverse("delegar_ao_robo"), {"chave": "d1"})
    assert resposta.status_code == 302
    execucao = Execucao.objects.get(tipo=Execucao.Tipo.PANORAMA)
    tarefa = Tarefa.objects.get(pk=execucao.tarefa_id)
    assert tarefa.executor == Tarefa.Executor.ROBO
    assert tarefa.responsavel == livia
    assert tarefa.situacao == Tarefa.Situacao.EM_ANDAMENTO
    # O mesmo clique repetido não cria outro.
    cliente.post(reverse("delegar_ao_robo"), {"chave": "d1"})
    assert Execucao.objects.filter(tipo=Execucao.Tipo.PANORAMA).count() == 1

    executor.rodar_uma("teste")
    execucao.refresh_from_db()
    assert execucao.situacao == S.AGUARDANDO_DEPENDENCIA
    entrega = Entrega.objects.get(execucao=execucao)
    assert entrega.parcial is True
    assert entrega.tarefa_id == tarefa.id
    assert "Gravar aula 5" in entrega.conteudo
    assert "render da cena 2" in entrega.conteudo
    assert "Esperando render" in entrega.conteudo
    tarefa.refresh_from_db()
    assert tarefa.situacao == Tarefa.Situacao.EM_ANDAMENTO
    assert Comentario.objects.filter(tarefa=tarefa, texto__contains="Entrega parcial").exists()

    pagina = cliente.get(reverse("entrega_do_robo", args=[entrega.id]))
    assert pagina.status_code == 200
    assert "Gravar aula 5" in pagina.content.decode()
    # O painel mostra o executor, o andamento e a entrega no cartão.
    painel = cliente.get(reverse("painel_da_equipe") + "?visao=minhas").content.decode()
    assert "Executor: O robô" in painel
    assert reverse("entrega_do_robo", args=[entrega.id]) in painel
    ficha = cliente.get(reverse("tarefa_editar", args=[tarefa.id])).content.decode()
    assert 'id="robo"' in ficha and entrega.titulo in ficha


@respx.mock
def test_entrega_solta_e_so_do_dono_e_ligada_a_tarefa_e_da_equipe():
    livia = _pessoa("Lívia", LIVIA)
    _pessoa("Ryan", RYAN)
    robo = trabalhos.robo_de(livia)
    solta = Entrega.objects.create(robo=robo, titulo="Rascunho meu", conteudo="texto")
    tarefa, _ = operacoes.criar_tarefa({"titulo": "T"}, "Lívia")
    da_tarefa = Entrega.objects.create(robo=robo, titulo="Da tarefa", conteudo="texto", tarefa_id=tarefa.id)
    ryan = _cliente(RYAN, "Ryan")
    assert ryan.get(reverse("entrega_do_robo", args=[solta.id])).status_code == 404
    assert ryan.get(reverse("entrega_do_robo", args=[da_tarefa.id])).status_code == 200
    assert _cliente(LIVIA, "Lívia").get(reverse("entrega_do_robo", args=[solta.id])).status_code == 200


def test_simulacao_panorama_completo_conclui_a_tarefa():
    livia = _pessoa("Lívia", LIVIA)
    _tarefas_da_livia(livia)
    _guardar_chave()
    robo = trabalhos.robo_de(livia)
    execucao, nova = trabalhos.delegar_panorama(robo, livia, pedido_por="Lívia", origem="teste")
    assert nova
    with respx.mock as rede:
        rota = rede.post(RESPOSTAS).mock(
            return_value=_texto_do_modelo("- Prioridade: destravar **Esperando render** (nº 2).")
        )
        executor.rodar_uma("teste")
    execucao.refresh_from_db()
    assert execucao.situacao == S.CONCLUIDA, execucao.motivo
    assert json.loads(rota.calls[0].request.content)["model"] == "gpt-6-sol"
    entrega = Entrega.objects.get(execucao=execucao)
    assert entrega.parcial is False
    assert "Leitura do robô" in entrega.conteudo and "destravar" in entrega.conteudo
    tarefa = Tarefa.objects.get(pk=execucao.tarefa_id)
    assert tarefa.situacao == Tarefa.Situacao.CONCLUIDA
    assert Comentario.objects.filter(tarefa=tarefa, texto__contains="Entrega pronta").exists()


def test_simulacao_panorama_parcial_ganha_versao_nova_quando_a_chave_chega():
    livia = _pessoa("Lívia", LIVIA)
    robo = trabalhos.robo_de(livia)
    execucao, _ = trabalhos.delegar_panorama(robo, livia, pedido_por="Lívia", origem="teste")
    executor.rodar_uma("teste")
    entrega = Entrega.objects.get(execucao=execucao)
    assert entrega.parcial and entrega.versao == 1
    _guardar_chave()
    executor.reacordar()
    with respx.mock as rede:
        rede.post(RESPOSTAS).mock(return_value=_texto_do_modelo("Semana tranquila."))
        executor.rodar_uma("teste")
    entrega.refresh_from_db()
    execucao.refresh_from_db()
    assert execucao.situacao == S.CONCLUIDA
    assert entrega.parcial is False and entrega.versao == 2
    assert Entrega.objects.filter(execucao=execucao).count() == 1


# ---------------------------------------------------------------- servidor


def test_posse_viva_nao_e_tomada_e_posse_vencida_e_retomada():
    livia = _pessoa("Lívia", LIVIA)
    robo = trabalhos.robo_de(livia)
    viva = Execucao.objects.create(
        robo=robo,
        tipo=Execucao.Tipo.CONVERSA,
        situacao=S.EXECUTANDO,
        trabalhador="outro",
        ocupada_ate=timezone.now() + timedelta(minutes=3),
    )
    assert executor.pegar_uma("eu") is None
    Execucao.objects.filter(pk=viva.pk).update(ocupada_ate=timezone.now() - timedelta(seconds=1))
    pega = executor.pegar_uma("eu")
    assert pega.pk == viva.pk and pega.trabalhador == "eu"


def test_interromper_o_que_esta_na_fila_cancela_na_hora():
    livia = _pessoa("Lívia", LIVIA)
    robo = trabalhos.robo_de(livia)
    execucao, _ = trabalhos.delegar_panorama(robo, livia, pedido_por="Lívia", origem="teste")
    trabalhos.pedir_cancelamento(execucao, "Lívia")
    execucao.refresh_from_db()
    assert execucao.situacao == S.CANCELADA


def test_robo_pausado_nao_trabalha():
    livia = _pessoa("Lívia", LIVIA)
    robo = trabalhos.robo_de(livia)
    execucao, _ = trabalhos.delegar_panorama(robo, livia, pedido_por="Lívia", origem="teste")
    RoboPessoal.objects.filter(pk=robo.pk).update(situacao=RoboPessoal.Situacao.PAUSADO)
    executor.rodar_uma("teste")
    execucao.refresh_from_db()
    assert execucao.situacao == S.PAUSADA
    assert not Entrega.objects.exists()


# ---------------------------------------------------------------- a chave


def test_a_chave_fica_cifrada_e_selada():
    guardado = segredo.cifrar(CHAVE)
    assert CHAVE not in guardado
    assert segredo.decifrar(guardado) == CHAVE
    adulterado = guardado[:-6] + ("A" if guardado[-6] != "A" else "B") + guardado[-5:]
    assert segredo.decifrar(adulterado) is None


@respx.mock
def test_o_administrador_guarda_a_chave_e_a_conta_e_conferida_sem_custo():
    respx.get(MODELOS).mock(
        return_value=httpx.Response(
            200, json={"data": [{"id": "gpt-6-luna"}, {"id": "gpt-6-sol"}, {"id": "gpt-4o"}]}
        )
    )
    cliente = _cliente(DONO, "Dono")
    resposta = cliente.post(reverse("robos_admin"), {"acao": "guardar", "chave": CHAVE})
    assert resposta.status_code == 302
    conexao = Conexao.objects.get(provedor="openai")
    assert conexao.situacao == Conexao.Situacao.CONFERIDA
    assert conexao.final_da_chave == "wxyz"
    assert CHAVE not in conexao.segredo_cifrado
    assert conexao.modelos_disponiveis == ["gpt-6-luna", "gpt-6-sol"]
    pagina = cliente.get(reverse("robos_admin")).content.decode()
    assert CHAVE not in pagina and "wxyz" in pagina
    assert not Consumo.objects.exists()
