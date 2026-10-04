"""A identidade do assistente de cada site: padrão, configuração, tela e uso
pelo coordenador."""

from __future__ import annotations

import json
import uuid

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.agentes import modelo, segredo
from apps.agentes.models import Conexao
from apps.assistente import identidade
from apps.assistente.models import IdentidadeAssistente
from apps.comercial import coordenador, papeis
from apps.comercial.models import TrabalhoComercial

IDENTIDADE = "http://identidade:8000/interno"
CATALOGO = "http://catalogo:8000/api/catalogo"
SESSAO = IDENTIDADE + "/sessao/completa"
RESPOSTAS = f"{modelo.URL}/responses"
CHAVE = "sk-teste-0000000000000000wxyz"


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    settings.ADMIN_EMAILS = "dono@exemplo.com"
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "identidade-test")
    monkeypatch.setenv("CATALOGO_API_URL", CATALOGO)
    monkeypatch.setenv("TOKEN_CATALOGO", "catalogo-test")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


def dentro(site=True):
    respx.get(SESSAO).respond(200, json={"autenticado": True, "id": "dono-1", "email": "dono@exemplo.com",
                                         "nome_exibido": "Dono"})
    if site:
        respx.get(CATALOGO + "/sites/by-host/testserver").respond(200, json={"id": "site-a", "name": "Meshcraft"})
    else:
        respx.get(CATALOGO + "/sites/by-host/testserver").respond(404, json={"detail": "x"})
    client = Client()
    client.defaults["HTTP_COOKIE"] = "meshcraft_sessao=assinado-test"
    return client


# ------------------------------------------------------------------ padrão


def test_sem_configuracao_vale_o_padrao_de_assistente_da_equipe():
    ident = identidade.identidade_do_site("site-a", "Meshcraft")
    assert not ident.configurada
    assert ident.apresentacao == "Assistente da equipe de Meshcraft"
    assert ident.assinatura == "— Assistente da equipe de Meshcraft"
    assert ident.tom == "acolhedor" and ident.resposta_em_voz == "texto"
    assert not IdentidadeAssistente.objects.exists()  # ler não grava


def test_sem_nome_do_site_nao_inventa_um():
    ident = identidade.identidade_do_site("site-desconhecido")
    assert ident.apresentacao == "Assistente da equipe"
    assert " de " not in ident.apresentacao


def test_site_vazio_nunca_levanta():
    assert identidade.identidade_do_site("").apresentacao == "Assistente da equipe"
    assert identidade.trecho_das_instrucoes("") == ""


def test_nome_entra_na_apresentacao_padrao():
    identidade.salvar("site-a", nome_do_site="Meshcraft", nome="Mia")
    ident = identidade.identidade_do_site("site-a")
    assert ident.configurada
    assert ident.apresentacao == "Mia, assistente da equipe de Meshcraft"
    assert ident.assinatura == "— Mia de Meshcraft" or ident.assinatura.startswith("— Mia")


def test_texto_proprio_com_marcadores_e_uma_linha_so():
    identidade.salvar("site-a", nome_do_site="Meshcraft", nome="Mia",
                      apresentacao="Oi, aqui é {nome},\n  assistente da equipe da {site}",
                      assinatura="Equipe {site}")
    ident = identidade.identidade_do_site("site-a")
    assert ident.apresentacao == "Oi, aqui é Mia, assistente da equipe da Meshcraft"
    assert ident.assinatura == "Equipe Meshcraft"


def test_valores_invalidos_voltam_ao_padrao_e_um_site_nao_vaza_no_outro():
    identidade.salvar("site-a", nome="Mia", tom="gritado", resposta_em_voz="radio")
    a = identidade.identidade_do_site("site-a")
    assert a.tom == "acolhedor" and a.resposta_em_voz == "texto"
    b = identidade.identidade_do_site("site-b")
    assert b.nome == "" and not b.configurada


def test_salvar_de_novo_atualiza_a_mesma_linha():
    identidade.salvar("site-a", nome="Mia", quem="dono@exemplo.com")
    identidade.salvar("site-a", nome="Lia", tom="formal")
    assert IdentidadeAssistente.objects.count() == 1
    assert identidade.identidade_do_site("site-a").nome == "Lia"


def test_voz_segue_a_preferencia_do_site():
    assert not identidade.deve_responder_em_voz("site-a", True)  # padrão: texto
    identidade.salvar("site-a", resposta_em_voz="espelhar")
    assert identidade.deve_responder_em_voz("site-a", True)
    assert not identidade.deve_responder_em_voz("site-a", False)
    identidade.salvar("site-a", resposta_em_voz="sempre")
    assert identidade.deve_responder_em_voz("site-a", False)


def test_trecho_das_instrucoes_diz_que_e_assistente_e_nao_o_criador():
    identidade.salvar("site-a", nome_do_site="Meshcraft", nome="Mia", tom="direto", resposta_em_voz="espelhar")
    trecho = identidade.trecho_das_instrucoes("site-a")
    assert "Mia, assistente da equipe de Meshcraft" in trecho
    assert "não o criador do curso" in trecho
    assert "Direto e curto" in trecho and "só quando a pessoa mandar áudio" in trecho


# ---------------------------------------------------------------- instruções


def test_instrucoes_dos_papeis_levam_a_identidade_do_site():
    estrategia = papeis.estrategia_ativa("atendimento")
    sem_site = papeis.instrucoes_completas(estrategia)
    assert "Identidade neste site" in sem_site  # site sem id: apresentação padrão, sem nome de site
    assert "Assistente da equipe" in sem_site and "Meshcraft" not in sem_site
    identidade.salvar("site-a", nome_do_site="Meshcraft", nome="Mia")
    com_site = papeis.instrucoes_completas(estrategia, "site-a")
    assert "Mia, assistente da equipe de Meshcraft" in com_site
    assert estrategia.instrucoes in com_site
    # Outro site não herda a identidade do primeiro.
    assert "Mia" not in papeis.instrucoes_completas(estrategia, "site-b")


def test_instrucoes_comuns_nao_fixam_um_site_e_servem_a_site_sem_id():
    assert "Meshcraft" not in papeis.COMUM
    estrategia = papeis.estrategia_ativa("atendimento")
    for vazio in ("", None):
        texto = papeis.instrucoes_completas(estrategia, vazio)
        assert "assistente da equipe" in texto and estrategia.instrucoes in texto
    identidade.salvar("site-b", nome_do_site="Outro Site", nome="Teo")
    texto_b = papeis.instrucoes_completas(estrategia, "site-b")
    assert "Teo, assistente da equipe de Outro Site" in texto_b and "Meshcraft" not in texto_b


@respx.mock
def test_coordenador_manda_ao_modelo_a_identidade_do_site_do_trabalho():
    conexao = modelo.conexao()
    conexao.segredo_cifrado = segredo.cifrar(CHAVE)
    conexao.final_da_chave = CHAVE[-4:]
    conexao.situacao = Conexao.Situacao.CONFERIDA
    conexao.save()
    identidade.salvar("site-a", nome_do_site="Meshcraft", nome="Mia")
    rota = respx.post(RESPOSTAS).mock(return_value=httpx.Response(200, json={
        "id": "resp_1", "status": "completed",
        "usage": {"input_tokens": 10, "input_tokens_details": {"cached_tokens": 0}, "output_tokens": 5},
        "output": [{"type": "message", "id": "m1", "role": "assistant", "content": [
            {"type": "output_text", "text": json.dumps({
                "resumo": "ok", "prioridade": "baixa", "razao_prioridade": "x", "oferta_indicada": None,
                "proximo_trabalho": "nenhum", "motivo": "x"})}]}],
    }))
    trabalho, _ = coordenador.criar(
        TrabalhoComercial.Tipo.ANALISAR_LEAD, f"teste:{uuid.uuid4().hex}", site_id="site-a",
        contato_id="lead-1", oportunidade_id="opp-1", chave_da_conversa="lead:site-a:x@y.test",
        entrada={"contato": {"nome": "Ana", "email": "x@y.test"}},
    )
    trabalho = coordenador.pegar_um("teste")
    assert trabalho is not None
    coordenador.conversar(trabalho, "Analise este lead.")
    instrucoes = json.loads(rota.calls[0].request.content)["instructions"]
    assert "Mia, assistente da equipe de Meshcraft" in instrucoes


# --------------------------------------------------------------------- tela


@respx.mock
def test_tela_exige_sessao_de_administrador():
    respx.get(SESSAO).respond(200, json={"autenticado": False})
    assert Client().get(reverse("assistente_do_site")).status_code == 302


@respx.mock
def test_tela_mostra_o_padrao_quando_nao_ha_configuracao():
    r = dentro().get(reverse("assistente_do_site"))
    assert r.status_code == 200
    html = r.content.decode()
    assert "Assistente da equipe de Meshcraft" in html
    assert "Ainda não configurado" in html


@respx.mock
def test_tela_salva_para_o_site_do_dominio_e_ignora_site_do_formulario():
    client = dentro()
    r = client.post(reverse("assistente_do_site"), {
        "site_id": "site-de-outro", "nome": "Mia", "apresentacao": "", "assinatura": "",
        "tom": "formal", "resposta_em_voz": "espelhar"})
    assert r.status_code == 302 and r["Location"].endswith("?salvo=1")
    linha = IdentidadeAssistente.objects.get()
    assert linha.site_id == "site-a" and linha.nome_do_site == "Meshcraft"
    assert linha.tom == "formal" and linha.resposta_em_voz == "espelhar"
    assert linha.atualizado_por == "dono@exemplo.com"
    html = client.get(reverse("assistente_do_site")).content.decode()
    assert "Mia, assistente da equipe de Meshcraft" in html
    assert "Ainda não configurado" not in html


@respx.mock
def test_tela_sem_site_avisa_e_nao_grava():
    client = dentro(site=False)
    r = client.post(reverse("assistente_do_site"), {"nome": "Mia"})
    assert r.status_code == 503
    assert "Não consegui identificar este site" in r.content.decode()
    assert not IdentidadeAssistente.objects.exists()


@respx.mock
def test_crm_tem_atalho_para_a_tela_do_assistente():
    respx.get("http://leads:8000/api/leads/crm").respond(500)
    r = dentro().get(reverse("crm"))
    assert reverse("assistente_do_site") in r.content.decode()
