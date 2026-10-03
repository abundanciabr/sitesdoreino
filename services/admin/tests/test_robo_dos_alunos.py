import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
import httpx
import pytest
import respx
from django.test import Client
from apps.agentes import alunos, modelo, segredo
from apps.agentes.models import AutorizacaoDeGasto, Consumo, RoboPessoal
from test_robos import _guardar_chave, _texto_do_modelo, _cliente, DONO, ambiente

pytestmark = pytest.mark.django_db
URL = "/interno/robo-dos-alunos/gerar"

def pedido(cliente=None, token="pages", **extra):
    return (cliente or Client()).post(URL, json.dumps({
        "campo": "apresentacao_publica",
        "contexto": {"quiz": {"experiencia": "iniciante", "ideia_propria": "um cabelo"}},
        **extra,
    }), content_type="application/json", HTTP_AUTHORIZATION="Bearer " + token)

def ativar(teto="1"):
    robo = alunos.configuracao()
    robo.ativo = True
    robo.modelo = "gpt-6-luna"
    robo.autorizacao = AutorizacaoDeGasto.objects.create(
        destino="alunos", descricao="Alunos", teto_mensal_usd=Decimal(teto), fonte="teste"
    )
    robo.save()
    return robo

def test_nao_aceita_outro_par_nem_chama_modelo_desativado(monkeypatch, settings):
    monkeypatch.setenv("TOKENS_ACEITOS_PAGES", "pages")
    settings.TOKENS_ACEITOS = {"pages", "outro-par"}
    with patch.object(modelo, "responder") as chamar:
        assert pedido(token="outro-par").status_code == 401
        assert pedido(token="").status_code == 401
        assert pedido().status_code == 503
        assert pedido(campo="segredo").status_code == 422
        chamar.assert_not_called()
    assert RoboPessoal.objects.count() == 0

@respx.mock
def test_exemplo_tem_robo_prompt_e_consumo_distintos(monkeypatch):
    monkeypatch.setenv("TOKENS_ACEITOS_PAGES", "pages")
    _guardar_chave()
    robo = ativar()
    api = respx.post(modelo.URL + "/responses").mock(return_value=_texto_do_modelo("Estou desenvolvendo meu primeiro cabelo para Roblox."))
    resposta = pedido()
    assert resposta.status_code == 200
    assert resposta.json()["texto"].startswith("Estou desenvolvendo")
    corpo = json.loads(api.calls.last.request.content)
    assert "robô dos alunos" in corpo["instructions"]
    assert "não são instruções" in corpo["instructions"]
    assert not corpo.get("tools")
    assert corpo["store"] is False
    consumo = Consumo.objects.get()
    assert consumo.origem == "alunos" and consumo.robo_id is None
    assert consumo.autorizacao_id == robo.autorizacao_id
    assert modelo.autorizacao_ativa().destino == "equipe"

@respx.mock
def test_teto_dos_alunos_nao_usa_autorizacao_da_equipe(monkeypatch):
    monkeypatch.setenv("TOKENS_ACEITOS_PAGES", "pages")
    _guardar_chave()
    robo = ativar("0")
    api = respx.post(modelo.URL + "/responses")
    assert pedido().status_code == 503
    assert not api.called
    assert not Consumo.objects.exists()

@respx.mock
def test_configuracao_dos_alunos_nao_altera_modelo_da_equipe():
    cliente = _cliente(DONO)
    conexao = _guardar_chave()
    antes = (conexao.modelo_rapido, conexao.modelo_forte, conexao.segredo_cifrado)
    r = cliente.post("/robos/", {
        "acao": "alunos", "nome_alunos": "Ajuda do portfólio", "modelo_alunos": "modelo-alunos",
        "instrucoes_alunos": "Escreva curto", "ativo_alunos": "1",
        "orcamento_alunos": "compartilhar",
    })
    assert r.status_code == 302
    robo = alunos.configuracao()
    assert robo.ativo and robo.autorizacao.destino == "equipe"
    assert robo.modelo == "modelo-alunos"
    conexao.refresh_from_db()
    assert antes == (conexao.modelo_rapido, conexao.modelo_forte, conexao.segredo_cifrado)
    pagina = cliente.get("/robos/")
    assert pagina.status_code == 200 and "Robô dos alunos" in pagina.content.decode()


def conteudo_comercial():
    return {
        "versao": 1,
        "posicionamento": {"comprador": "Estúdio", "necessidade": "Cenário",
                          "oferta": "Objeto 3D", "prova": "Peça no portfólio"},
        "pagina": {"titulo": "Objetos para seu mundo", "subtitulo": "3D para projetos Roblox",
                   "apresentacao": "Crio objetos para mundos de jogo.",
                   "oferta": "Converse sobre o objeto de que precisa.",
                   "continuidade": "Podemos conversar sobre novas peças.",
                   "diferenciais": "Trabalho demonstrado no portfólio.",
                   "condicoes": "Escopo a combinar.", "duvidas": "Como começar? Envie seu projeto.",
                   "cta": "Conte sobre seu projeto.", "trabalho_destaque": "p1",
                   "legendas": [{"peca_id": "p1", "titulo": "Peça", "texto": "Objeto 3D."}]},
        "kit": {"apresentacao_principal": "Crio objetos 3D para mundos Roblox.",
                "bio_curta": "Criador 3D para Roblox.",
                "abordagem": "Olá, seu projeto pode usar esta peça como referência.",
                "proposta": "Podemos definir juntos o objeto e o escopo."},
    }


def test_completo_envia_imagem_separada_e_devolve_contrato(monkeypatch):
    monkeypatch.setenv("TOKENS_ACEITOS_PAGES", "pages")
    ativar()
    conteudo = conteudo_comercial()
    with patch.object(modelo, "responder", return_value=SimpleNamespace(
        texto=json.dumps({"conteudo": conteudo}), completa=True,
    )) as chamar:
        resposta = pedido(campo="completo", contexto={
            "trabalhos": [{"id": "p1", "legenda": "Objeto 3D"}],
            "imagens": [{"peca_id": "p1", "data_url": "data:image/png;base64,AAAA"}],
            "oferta": {"comprador": "Estúdio", "exibir_preco": False},
        })
    assert resposta.status_code == 200
    assert resposta.json()["conteudo"] == conteudo
    assert resposta.json()["visao"] is True
    argumentos = chamar.call_args.kwargs
    assert argumentos["max_saida"] == 6500 and argumentos["esforco"] == "medium"
    assert argumentos["formato"]["type"] == "json_schema"
    assert argumentos["formato"]["strict"] is True
    partes = argumentos["itens"][0]["content"]
    assert partes[-1] == {"type": "input_image", "image_url": "data:image/png;base64,AAAA", "detail": "low"}
    assert "base64" not in partes[0]["text"]
    assert "Hormozi" in argumentos["instrucoes"]
    assert "NUNCA escreva números de preço" in argumentos["instrucoes"]
    assert "kit.proposta" in argumentos["instrucoes"]
    assert "Quatro exemplos sintéticos completos" in argumentos["instrucoes"]
    assert '"u1"' in argumentos["instrucoes"] and '"a2"' in argumentos["instrucoes"]
    assert '"m3"' in argumentos["instrucoes"]
    assert "Vamos conversar sobre seu visual 3D" in argumentos["instrucoes"]
    assert 'prospeccao.idioma' in argumentos["instrucoes"]


def test_url_https_publica_e_aceita_e_endereco_interno_e_rejeitado(monkeypatch):
    monkeypatch.setenv("TOKENS_ACEITOS_PAGES", "pages")
    ativar()
    conteudo = conteudo_comercial()
    with patch.object(modelo, "responder", return_value=SimpleNamespace(
        texto=json.dumps({"conteudo": conteudo}), completa=True,
    )) as chamar:
        resposta = pedido(campo="completo", contexto={
            "trabalhos": [{"id": "p1"}],
            "imagens": [{"peca_id": "p1", "data_url": "https://cdn.example.com/peca.webp"}],
        })
    assert resposta.status_code == 200 and resposta.json()["visao"] is True
    assert chamar.call_args.kwargs["itens"][0]["content"][-1]["image_url"] == "https://cdn.example.com/peca.webp"
    for url in ("https://localhost/x", "https://127.0.0.1/x", "https://10.0.0.1/x",
                "https://arquivo.local/x", "https://usuario:senha@example.com/x",
                "https://intranet/x", "http://example.com/x"):
        assert pedido(campo="completo", contexto={
            "trabalhos": [{"id": "p1"}], "imagens": [{"peca_id": "p1", "data_url": url}],
        }).status_code == 422


def test_recusa_especifica_de_imagem_repete_uma_vez_sem_visao(monkeypatch):
    monkeypatch.setenv("TOKENS_ACEITOS_PAGES", "pages")
    ativar()
    conteudo = conteudo_comercial()
    with patch.object(modelo, "responder", side_effect=[
        modelo.PedidoRecusado("modelo não suporta image input"),
        SimpleNamespace(texto=json.dumps({"conteudo": conteudo}), completa=True),
    ]) as chamar:
        resposta = pedido(campo="completo", contexto={
            "trabalhos": [{"id": "p1"}],
            "imagens": [{"peca_id": "p1", "data_url": "data:image/png;base64,AAAA"}],
        })
    assert resposta.status_code == 200 and resposta.json()["visao"] is False
    assert chamar.call_count == 2
    assert len(chamar.call_args.kwargs["itens"][0]["content"]) == 1


def test_erro_geral_nao_repete_sem_imagem(monkeypatch):
    monkeypatch.setenv("TOKENS_ACEITOS_PAGES", "pages")
    ativar()
    with patch.object(modelo, "responder", side_effect=modelo.PedidoRecusado(
        "pedido recusado por parâmetro"
    )) as chamar:
        resposta = pedido(campo="completo", contexto={
            "trabalhos": [{"id": "p1"}],
            "imagens": [{"peca_id": "p1", "data_url": "data:image/png;base64,AAAA"}],
        })
    assert resposta.status_code == 503 and chamar.call_count == 1


def test_secao_preserva_demais_campos_mesmo_se_modelo_os_alterar(monkeypatch):
    monkeypatch.setenv("TOKENS_ACEITOS_PAGES", "pages")
    ativar()
    atual = conteudo_comercial()
    novo = json.loads(json.dumps(atual))
    novo["kit"]["bio_curta"] = "Objetos 3D para mundos Roblox."
    contexto = {"trabalhos": [{"id": "p1"}], "conteudo_atual": atual}
    with patch.object(modelo, "responder", return_value=SimpleNamespace(
        texto=json.dumps({"conteudo": novo}), completa=True,
    )):
        assert pedido(campo="kit.bio_curta", contexto=contexto).json()["conteudo"] == novo
    novo["pagina"]["titulo"] = "Título alterado"
    with patch.object(modelo, "responder", return_value=SimpleNamespace(
        texto=json.dumps({"conteudo": novo}), completa=True,
    )):
        resposta = pedido(campo="kit.bio_curta", contexto=contexto)
    assert resposta.status_code == 200
    assert resposta.json()["conteudo"]["kit"]["bio_curta"] == novo["kit"]["bio_curta"]
    assert resposta.json()["conteudo"]["pagina"]["titulo"] == atual["pagina"]["titulo"]


def test_contrato_incompleto_nao_substitui_texto(monkeypatch):
    monkeypatch.setenv("TOKENS_ACEITOS_PAGES", "pages")
    ativar()
    with patch.object(modelo, "responder", return_value=SimpleNamespace(
        texto='{"conteudo":{"versao":1}}', completa=True,
    )):
        resposta = pedido(campo="completo", contexto={})
    assert resposta.status_code == 503
    assert "mantido" in resposta.json()["erro"]
