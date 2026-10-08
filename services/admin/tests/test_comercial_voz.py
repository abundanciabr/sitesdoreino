"""O atendente envia voz pelo caminho pago, com retomada sem gerar outra voz."""
import json
from decimal import Decimal

import httpx
import pytest
import respx
from django.db import connection

from apps.agentes import modelo
from apps.agentes.models import AutorizacaoDeGasto, Consumo
from apps.assistente.models import IdentidadeAssistente
from apps.comercial import ferramentas
from apps.comercial.models import TrabalhoComercial
from apps.voz.models import ProcessamentoDeVoz

pytestmark = pytest.mark.django_db
MSG = "http://mensageria:8000/api/mensageria"
FALA = f"{modelo.URL}/audio/speech"


@pytest.fixture
def ambiente(monkeypatch):
    monkeypatch.setenv("MENSAGERIA_API_URL", MSG)
    monkeypatch.setenv("MENSAGERIA_API_TOKEN", "teste")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-teste-voz")
    AutorizacaoDeGasto.objects.create(destino="equipe", teto_mensal_usd=Decimal("10"), ativa=True)
    IdentidadeAssistente.objects.create(site_id="site-a", resposta_em_voz="espelhar")
    return TrabalhoComercial.objects.create(
        tipo="atender_mensagem", site_id="site-a", contato_id="lead-a", conversa_id="conv-a",
        chave_idempotencia="trabalho-voz", chave_da_conversa="conversa:conv-a",
        entrada={"canal": "whatsapp", "contato": {"telefone": "5511988887777"}},
    )


def enviar(trabalho, call_id="voz-1"):
    return json.loads(ferramentas.executar(
        ferramentas.Contexto(trabalho=trabalho, papel="atendimento"), call_id, "enviar_mensagem",
        json.dumps({"texto": "O curso começa segunda.", "canal": None, "assunto": None,
                    "razao": "resposta", "fonte": None}),
    ))


def rotas(rede, *, motivo="lead_mandou_audio", preferencia="espelhar", canal="whatsapp",
          janela=True, estado="agente", site="site-a"):
    rede.get(f"{MSG}/conversas/conv-a").respond(200, json={
        "site_id": site, "canal": canal, "estado": estado, "janela_aberta": janela})
    formato = rede.post(f"{MSG}/audio/site-a/formato").respond(200, json={
        "formato": "audio" if motivo in ("lead_mandou_audio", "lead_prefere_audio") else "texto",
        "motivo": motivo, "preferencia": preferencia, "canal_aceita_audio": True,
        "ja_respondeu_em_voz": False})
    profundidade = len(connection.atomic_blocks)
    def falar(request):
        assert len(connection.atomic_blocks) == profundidade
        return httpx.Response(200, content=b"OggS-voz")
    fala = rede.post(FALA).mock(side_effect=falar)
    voz = rede.post(f"{MSG}/audio/site-a/responder-em-voz").respond(200, json={
        "resultado": "enviada", "status": "aceito", "mensagem_ref": "msg-voz"})
    texto = rede.post(f"{MSG}/conversas/conv-a/mensagens").respond(200, json={
        "resultado": "enviada", "mensagem": {"id": "msg-texto"}, "conversa": {"canal": canal}})
    return formato, fala, voz, texto


def test_atendente_envia_audio_guarda_custo_e_nao_envia_texto(ambiente):
    with respx.mock as rede:
        _, fala, voz, texto = rotas(rede)
        saida = enviar(ambiente)
        repetida = enviar(ambiente, "outro-pedido-do-modelo")
    assert saida["mensagem_id"] == "msg-voz" and repetida["ja_feito"]
    assert fala.call_count == voz.call_count == 1 and not texto.called
    assert Consumo.objects.filter(origem="audio").count() == 1
    assert ProcessamentoDeVoz.objects.get().resultado["pedido"]["audio_base64"]


@pytest.mark.parametrize("motivo,preferencia", [("lead_mandou_texto", "espelhar"),
                                               ("lead_prefere_texto", "texto")])
def test_texto_nao_gasta_com_sintese(ambiente, motivo, preferencia):
    with respx.mock as rede:
        _, fala, voz, texto = rotas(rede, motivo=motivo, preferencia=preferencia)
        assert enviar(ambiente)["mensagem_id"] == "msg-texto"
    assert texto.called and not voz.called and not fala.called and not Consumo.objects.exists()


def test_pedido_de_voz_recebe_audio(ambiente):
    with respx.mock as rede:
        _, fala, voz, texto = rotas(rede, motivo="lead_prefere_audio", preferencia="audio")
        enviar(ambiente)
    assert fala.called and voz.called and not texto.called


def test_painel_sempre_fala_mas_respeita_preferencia_por_texto(ambiente):
    IdentidadeAssistente.objects.update(resposta_em_voz="sempre")
    with respx.mock as rede:
        _, fala, voz, texto = rotas(rede, motivo="lead_mandou_texto")
        enviar(ambiente)
    assert fala.called and voz.called and not texto.called


def test_painel_sempre_respeita_pedido_de_texto(ambiente):
    IdentidadeAssistente.objects.update(resposta_em_voz="sempre")
    with respx.mock as rede:
        _, fala, voz, texto = rotas(rede, motivo="lead_prefere_texto", preferencia="texto")
        enviar(ambiente)
    assert texto.called and not fala.called and not voz.called


@pytest.mark.parametrize("opcoes", [{"canal": "email"}, {"janela": False}, {"estado": "pessoa"}])
def test_voz_nao_sai_fora_da_conversa_permitida(ambiente, opcoes):
    with respx.mock as rede:
        _, fala, voz, texto = rotas(rede, **opcoes)
        enviar(ambiente)
    assert not fala.called and not voz.called and texto.called


def test_site_diferente_recusa_sem_enviar(ambiente):
    with respx.mock as rede:
        _, fala, voz, texto = rotas(rede, site="outro-site")
        assert "não é deste site" in enviar(ambiente)["erro"]
    assert not fala.called and not voz.called and not texto.called


def test_voz_desligada_no_painel_nao_chama_audio(ambiente):
    IdentidadeAssistente.objects.update(resposta_em_voz="texto")
    with respx.mock as rede:
        formato, fala, voz, texto = rotas(rede)
        enviar(ambiente)
    assert texto.called and not formato.called and not fala.called and not voz.called


def test_confirmacao_perdida_retoma_mesmo_audio_sem_novo_gasto(ambiente):
    with respx.mock as rede:
        _, fala, voz, texto = rotas(rede)
        voz.mock(side_effect=[httpx.ReadTimeout("sem confirmacao"), httpx.Response(200, json={
            "resultado": "enviada", "status": "aceito", "mensagem_ref": "msg-voz"})])
        with pytest.raises(ferramentas.EnvioIncerto):
            enviar(ambiente)
        assert ambiente.decisoes.get().resultado == "incerto"
        assert ProcessamentoDeVoz.objects.get().resultado["pedido"]
        assert enviar(ambiente)["mensagem_id"] == "msg-voz"
    assert fala.call_count == 1 and voz.call_count == 2 and not texto.called
    assert json.loads(voz.calls[0].request.content) == json.loads(voz.calls[1].request.content)
    assert Consumo.objects.filter(origem="audio").count() == 1


def test_falha_confirmada_de_voz_volta_para_texto(ambiente):
    with respx.mock as rede:
        _, _, voz, texto = rotas(rede)
        voz.respond(200, json={"status": "falhou", "resultado": "falhou"})
        assert enviar(ambiente)["mensagem_id"] == "msg-texto"
    assert texto.called


def test_sem_autorizacao_de_gasto_responde_em_texto(ambiente):
    AutorizacaoDeGasto.objects.update(ativa=False)
    with respx.mock as rede:
        _, fala, voz, texto = rotas(rede)
        enviar(ambiente)
    assert texto.called and not voz.called and not fala.called
