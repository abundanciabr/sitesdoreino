"""Onda 1 do CRM com agentes, frente "comercial-fila": o PARAR tira o lead da fila, a tela diz o que o código
faz no envio incerto, a passagem para a equipe avisa na hora, o perfil guarda a prova mais recente e a primeira
mensagem de um lead sem marca já cai no grupo certo. Tudo simulado (respx)."""

from __future__ import annotations

import json

import pytest
import respx
from django.utils import timezone

from apps.comercial import comparacao, coordenador, eventos, ferramentas
from apps.comercial.models import DecisaoComercial, TrabalhoComercial
from apps.core import avisos_equipe, crm_agentes
from apps.core.models import AvisoDaEquipe

from tests.test_comercial import (  # noqa: F401
    EMAIL, LEADS, MENSAGERIA, RESPOSTAS, E, R, T, ambiente, _chamada, _contato, _envelope, _final,
    _guardar_chave, _reanalise_pronta, _resto_404, _rotas_da_reanalise, _trabalho, DISPONIBILIDADE, _corpo,
)


def _mensagem(texto="oi", *, parar=False, lead="lead-1", conversa="conv-1", event_id=None):
    return _envelope("mensagem.recebida", {
        "conversa_id": conversa, "mensagem_id": f"m-{conversa}-{parar}", "canal": "whatsapp", "site_id": "site-1",
        "lead": lead, "lead_ligacao": "ligada", "texto": texto, "estado_conversa": "agente",
        "descadastro": parar}, event_id)


# ---------------------------------------------------------------- D2: PARAR


def test_parar_cancela_o_que_esta_na_fila_para_falar_com_o_lead_e_so_dele():
    abordar = _trabalho(T.ABORDAR, chave_da_conversa="lead:site-1:a@x.test")
    acompanhar = _trabalho(T.ACOMPANHAR_PAGAMENTO, chave_da_conversa="lead:site-1:a@x.test")
    recuperar = _trabalho(T.RECUPERAR_COMPRA, chave_da_conversa="lead:site-1:a@x.test")
    atender = _trabalho(T.ATENDER_MENSAGEM, conversa_id="conv-1", chave_da_conversa="conversa:conv-1")
    analise = _trabalho(T.ANALISAR_LEAD, chave_da_conversa="lead:site-1:a@x.test")
    de_outro = _trabalho(T.ABORDAR, contato_id="lead-2", chave_da_conversa="lead:site-1:b@x.test")
    rodando = _trabalho(T.ABORDAR, chave_da_conversa="lead:site-1:c@x.test")
    TrabalhoComercial.objects.filter(pk=rodando.pk).update(estado=E.EXECUTANDO)
    rodando.refresh_from_db()

    parar = eventos.tratar("eventos.mensagem.recebida", _mensagem("PARAR", parar=True))

    for trabalho in (abordar, acompanhar, recuperar, atender):
        trabalho.refresh_from_db()
        assert trabalho.estado == E.CANCELADO and "parar" in trabalho.motivo and trabalho.terminado_em
    for intacto in (analise, de_outro, rodando):
        estado = intacto.estado
        intacto.refresh_from_db()
        assert intacto.estado == estado  # análise não fala com o lead; outro lead e o que já roda ficam
    # O trabalho desta própria mensagem nasce depois e segue a regra de sempre (encerra sem chamar o modelo).
    assert parar is not None and parar.estado == E.NA_FILA


@respx.mock
@pytest.mark.parametrize("tipo", [T.ABORDAR, T.ACOMPANHAR_PAGAMENTO])
def test_trabalho_de_lead_que_pediu_para_parar_nao_chama_o_modelo(tipo):
    _guardar_chave()
    trabalho = _trabalho(tipo)
    respx.get(f"{MENSAGERIA}/conversas").respond(200, json={"itens": [
        {"id": "conv-1", "site_id": "site-1", "lead_id": "lead-1", "descadastrado": True}]})
    openai = respx.post(RESPOSTAS)
    _resto_404()
    coordenador.rodar_um("t1")
    trabalho.refresh_from_db()
    assert trabalho.estado == E.ENCERRADO and "parar" in trabalho.motivo
    assert not openai.called and not DecisaoComercial.objects.exists()


@respx.mock
def test_lead_com_outra_conversa_que_aceita_mensagem_segue_para_o_agente():
    _guardar_chave()
    trabalho = _trabalho(T.ABORDAR)
    respx.get(f"{MENSAGERIA}/conversas").respond(200, json={"itens": [
        {"id": "conv-1", "site_id": "site-1", "lead_id": "lead-1", "descadastrado": True},
        {"id": "conv-2", "site_id": "site-1", "lead_id": "lead-1", "descadastrado": False}]})
    openai = respx.post(RESPOSTAS).mock(side_effect=[_final({
        "acao": "sem_mensagem", "razao": "r", "alternativas": []})])
    _resto_404()
    coordenador.rodar_um("t1")
    trabalho.refresh_from_db()
    assert openai.called and trabalho.estado == E.CONCLUIDO


# ---------------------------------------------------------------- D3: envio incerto


def test_a_tela_e_o_aviso_dizem_o_que_o_coordenador_faz_no_envio_incerto():
    # O coordenador repete o pedido em 1 minuto com a MESMA chave e a mensageria devolve "repetida" sem mandar
    # de novo (ver test_envio_sem_confirmacao_fica_incerto_e_reconcilia_com_a_mesma_chave). Nada diz o contrário.
    assert coordenador.ESPERA_ENVIO_INCERTO.total_seconds() == 60
    explicacao = crm_agentes.EXPLICA_GRUPO["incerto"]
    assert "não repete" not in explicacao and "mesma chave" in explicacao and "em dobro" in explicacao


# ---------------------------------------------------------------- D5: aviso na hora


def _assumir(trabalho, assumida_em="2026-10-04T12:00:00+00:00"):
    return respx.post(f"{MENSAGERIA}/conversas/conv-1/assumir").respond(200, json={
        "id": "conv-1", "site_id": "site-1", "canal": "whatsapp", "estado": "pessoa", "assumida_por": "equipe",
        "assumida_em": assumida_em})


@pytest.mark.django_db
@respx.mock
def test_passar_para_responsavel_avisa_a_equipe_na_hora_e_a_varredura_nao_repete():
    trabalho = _trabalho(T.ATENDER_MENSAGEM, conversa_id="conv-1", chave_da_conversa="conversa:conv-1")
    _assumir(trabalho)
    respx.patch(f"{LEADS}/crm/opp-1/acompanhamento").respond(200, json={})
    ctx = ferramentas.Contexto(trabalho=trabalho, papel="atendimento")
    saida = ferramentas.passar_para_responsavel(ctx, {"motivo": "quer falar com gente", "resumo": "r"})
    assert saida["passado"] is True
    aviso = AvisoDaEquipe.objects.get()
    assert aviso.tipo == AvisoDaEquipe.Tipo.PESSOA_PEDIDA and aviso.site_id == "site-1"
    # É o mesmo fato que a varredura usa: ela cai no aviso que já existe.
    outro, criado = avisos_equipe.avisar(
        AvisoDaEquipe.Tipo.PESSOA_PEDIDA, site_id="site-1", fato="conversa:conv-1:2026-10-04T12:00:00+00:00",
        titulo="x")
    assert criado is False and outro.pk == aviso.pk


@pytest.mark.django_db
@respx.mock
def test_passar_para_responsavel_de_teste_nao_avisa_e_o_aviso_nao_derruba_o_trabalho(monkeypatch):
    teste = _trabalho(T.ATENDER_MENSAGEM, conversa_id="conv-1", chave_da_conversa="conversa:conv-1", teste=True)
    _assumir(teste)
    respx.patch(f"{LEADS}/crm/opp-1/acompanhamento").respond(200, json={})
    ferramentas.passar_para_responsavel(ferramentas.Contexto(trabalho=teste, papel="atendimento"),
                                        {"motivo": "m", "resumo": "r"})
    assert not AvisoDaEquipe.objects.exists()

    real = _trabalho(T.ATENDER_MENSAGEM, conversa_id="conv-1", chave_da_conversa="conversa:conv-1")
    monkeypatch.setattr(avisos_equipe, "avisar", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("fora")))
    saida = ferramentas.passar_para_responsavel(ferramentas.Contexto(trabalho=real, papel="atendimento"),
                                                {"motivo": "m", "resumo": "r"})
    assert saida["passado"] is True


# ---------------------------------------------------------------- D20: prova mais recente


def test_perfil_mostra_ao_modelo_a_prova_mais_recente():
    afirmacao = {"texto": "Acha caro", "hipotese": False, "evidencias": [
        {"tipo": "mensagem", "id": "m-antiga", "trecho": "caro"},
        {"tipo": "mensagem", "id": "m-nova", "trecho": "continua caro"}]}
    visto = coordenador._afirmacao_para_o_modelo(afirmacao)
    assert visto["fonte_id"] == "m-nova" and visto["trecho"] == "continua caro"


@respx.mock
def test_reanalise_com_prova_nova_para_a_mesma_afirmacao_grava_versao_e_guarda_as_provas_antigas():
    _guardar_chave()
    _reanalise_pronta()
    _rotas_da_reanalise()
    perfil = respx.put(f"{LEADS}/leads/lead-1/perfil").respond(200, json={"versao": 2})
    respx.patch(f"{LEADS}/crm/opp-1/acompanhamento").respond(200, json={"id": "opp-1"})
    _resto_404()
    # Mesma afirmação do perfil vigente, agora sustentada por uma mensagem: antes isto era ignorado.
    reforco = {**DISPONIBILIDADE, "fonte": "mensagem", "fonte_id": "msg-1", "trecho": "continuo com 3 horas"}
    respx.post(RESPOSTAS).mock(side_effect=[
        _chamada("salvar_perfil", {
            "resumo": "Iniciante com pouco tempo.", "objetivo_declarado": None, "experiencia": None,
            "disponibilidade": reforco, "duvidas": [], "objecoes": [], "hipoteses": [],
            "informacoes_ausentes": ["experiência"], "perguntas_uteis": ["Já usou Blender?"],
            "prioridade": "media", "razao_prioridade": "Interesse.", "oferta_motivo": None,
            "oferta_indicada": "curso-3d"}, "c1"),
        _final({"mudou": "sim", "resumo": "Reforçou a disponibilidade.", "o_que_mudou": "Mesma disponibilidade.",
                "objecao_principal": None, "proximo_passo": None}),
    ])
    rodado = coordenador.rodar_um("t1")
    rodado.refresh_from_db()
    assert rodado.estado == E.CONCLUIDO, rodado.motivo
    salvo = _corpo(perfil.calls.last)
    assert [p["id"] for p in salvo["disponibilidade"]["evidencias"]] == ["q1", "msg-1"]  # a antiga fica, a nova entra
    assert rodado.resultado["versao_do_perfil"] == 2 and rodado.resultado["perfil_mudou"] is True


def test_texto_corrigido_pelo_cliente_leva_so_a_prova_nova():
    vigente = {"disponibilidade": {"texto": "Tem 3 horas por semana", "hipotese": False,
                                   "evidencias": [{"tipo": "resposta_quiz", "id": "q1", "trecho": "3 horas"}]}}
    novo = {"disponibilidade": {"texto": "Agora tem 10 horas por semana", "hipotese": False,
                                "evidencias": [{"tipo": "mensagem", "id": "m1", "trecho": "agora tenho 10"}]}}
    ferramentas._guardar_historico_de_provas(novo, vigente)
    assert [p["id"] for p in novo["disponibilidade"]["evidencias"]] == ["m1"]
    assert not ferramentas.perfil_igual(vigente, novo)


# ---------------------------------------------------------------- D21: marca antes do agente


def _do_grupo(grupo, percentual=50):
    for i in range(10000):
        email = f"sorteio{i}@meshcraft.test"
        if comparacao.grupo_do_contato("site-1", email, percentual) == grupo:
            return email
    raise AssertionError("não achou")


@pytest.mark.django_db
@respx.mock
def test_primeira_mensagem_de_lead_sem_marca_e_sorteada_antes_do_agente():
    comparacao.definir_percentual(50, "dono")
    sem = _do_grupo(comparacao.GRUPO_COMPARACAO)
    com = _do_grupo(comparacao.GRUPO_AGENTE)
    respx.get(f"{LEADS}/leads/lead-1").respond(200, json={"id": "lead-1", "email": sem, "nome": "Ana"})
    respx.get(f"{LEADS}/leads/lead-2").respond(200, json={"id": "lead-2", "email": com, "nome": "Bia"})
    respx.route(url__startswith="http://").respond(404, json={"detail": "sem esta rota"})
    assert not comparacao.MarcaDeComparacao.objects.exists()  # nenhum dos dois passou pelo quiz
    eventos.tratar("eventos.mensagem.recebida", _mensagem(lead="lead-1", conversa="conv-1"))
    eventos.tratar("eventos.mensagem.recebida", _mensagem(lead="lead-2", conversa="conv-2"))

    primeiro = coordenador.rodar_um("t1")
    primeiro.refresh_from_db()
    assert primeiro.estado == E.ENCERRADO and "grupo de comparação" in primeiro.motivo
    assert comparacao.grupo_do_contato_id("site-1", "lead-1") == comparacao.GRUPO_COMPARACAO
    assert comparacao.grupo_do_contato_id("site-1", "lead-2") is None  # o segundo ainda não rodou
    assert not DecisaoComercial.objects.exists()
    # O lead sorteado para o agente fica marcado e segue atendido.
    assert coordenador._do_grupo_de_comparacao(TrabalhoComercial.objects.get(contato_id="lead-2")) is False
    assert comparacao.grupo_do_contato_id("site-1", "lead-2") == comparacao.GRUPO_AGENTE


@pytest.mark.django_db
def test_evento_com_o_lead_completo_sorteia_antes_de_criar_o_trabalho():
    comparacao.definir_percentual(50, "dono")
    sem = _do_grupo(comparacao.GRUPO_COMPARACAO)
    envelope = _mensagem()
    envelope["data"]["lead"] = {"id": "lead-1", "email": sem, "nome": "Ana"}
    assert eventos.tratar("eventos.mensagem.recebida", envelope) is None  # nem virou trabalho
    assert not TrabalhoComercial.objects.exists()
    assert comparacao.grupo_do_contato_id("site-1", "lead-1") == comparacao.GRUPO_COMPARACAO


@pytest.mark.django_db
def test_lead_que_o_agente_ja_atendeu_antes_do_recurso_nao_e_sorteado():
    comparacao.definir_percentual(50, "dono")
    sem = _do_grupo(comparacao.GRUPO_COMPARACAO)
    antigo = _trabalho(T.ABORDAR)
    TrabalhoComercial.objects.filter(pk=antigo.pk).update(estado=E.CONCLUIDO)
    assert coordenador.sortear_se_ainda_sem_marca("site-1", sem, "lead-1") is None
    assert not comparacao.MarcaDeComparacao.objects.exists()
