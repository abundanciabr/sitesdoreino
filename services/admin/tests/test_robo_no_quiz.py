"""O robô na página de links e números do quiz (`apps/agentes/quiz.py`).

**Tudo que aqui fala com a OpenAI, com o quiz e com as páginas do site é
SIMULAÇÃO** (`respx`): estes testes provam o caminho do sistema (fila,
conferência sem formulário, relatório, tarefa de correção, leitura em esquema
fixo, propostas filtradas pelo código, ações da conversa e os botões da
página), não que o site ou o modelo de verdade respondem assim. A prova com o
site e a conta reais é feita à parte, no site.
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

from apps.agentes import executor, ferramentas, modelo, quiz, segredo, trabalhos
from apps.agentes.models import ChamadaDeFerramenta, Conexao, Consumo, Entrega, Execucao, Mensagem
from apps.core.conteudos import _nome_de_campanha_sugerido
from apps.core.models import Comentario, MembroDaEquipe, Tarefa

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
CATALOGO = "http://catalogo:8000/api/catalogo/sites/by-host/testserver"
QUIZ = "http://quiz:8000/interno/editor/quizzes/encontre"
DONO = "dono@exemplo.com"
RYAN = "ryan-conta-de-teste@exemplo.com"
RESPOSTAS = f"{modelo.URL}/responses"
CHAVE = "sk-teste-0000000000000000wxyz"
TEXTO = "https://testserver/quiz/encontre/?v=B2&fmt=text&seg=frio&src=teste&cpg=teste_robo"
VIDEO = "https://testserver/quiz/encontre/?v=B2&fmt=video&seg=frio&src=teste&cpg=teste_robo"

S = Execucao.Situacao


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    monkeypatch.setenv("CATALOGO_API_URL", "http://catalogo:8000/api/catalogo")
    monkeypatch.setenv("TOKEN_CATALOGO", "catalogo-teste")
    monkeypatch.setenv("QUIZ_API_URL", "http://quiz:8000")
    monkeypatch.setenv("QUIZ_API_TOKEN", "quiz-teste")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


def _site():
    respx.get(CATALOGO).mock(
        return_value=httpx.Response(200, json={"id": "site-teste", "host": "testserver", "menu": {}})
    )


def _cliente(email: str = DONO, nome: str = "Dono") -> Client:
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
    _site()
    cliente = Client()
    cliente.defaults["HTTP_COOKIE"] = "meshcraft_sessao=qualquer-coisa-assinada"
    return cliente


def _admin() -> MembroDaEquipe:
    """A Lívia, com o e-mail de quem administra o site."""
    pessoa = MembroDaEquipe.objects.get(nome="Lívia")
    pessoa.email = DONO
    pessoa.save()
    return pessoa


def _guardar_chave() -> None:
    conexao = modelo.conexao()
    conexao.segredo_cifrado = segredo.cifrar(CHAVE)
    conexao.final_da_chave = CHAVE[-4:]
    conexao.situacao = Conexao.Situacao.CONFERIDA
    conexao.save()


def _uso():
    return {"input_tokens": 1000, "input_tokens_details": {"cached_tokens": 0}, "output_tokens": 100}


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


def _faixa(key, minimo, maximo, oferta, destino, soma):
    return {
        "key": key,
        "titulo": key,
        "min": minimo,
        "max": maximo,
        "alcancavel": True,
        "oferta_id": key,
        "oferta": oferta,
        "demonstracao": False,
        "destino": destino,
        "prova_origem": {
            "url_final": f"{destino}?v=B2&fmt=text&seg=frio&src=meta&utm_source=facebook&utm_term=prova_utm_term",
            "faltam": [],
        },
        "rotulo": "Quero",
        "exemplos": [{"pontuacao": soma, "respostas": [{"pergunta": 1, "opcao": "Nunca", "pontos": 1}]}],
    }


def _link(ctv: str, problemas=()) -> dict:
    url = (
        "https://testserver/quiz/encontre/?v=B2&fmt=text&seg=frio&src=meta&med=cpc"
        f"&cpg=qz_frio_oct26&ctv={ctv}"
    )
    return {
        "version_key": "B2",
        "fmt": "text",
        "seg": "frio",
        "ctv": ctv,
        "url": url,
        "experiencia": "B2|text|frio",
        "saidas": [
            {
                "faixa": "desafio",
                "oferta": "Desafio",
                "demonstracao": False,
                "url_final": f"https://pay.exemplo.com/desafio?src=meta&cpg=qz_frio_oct26&ctv={ctv}",
                "faltam": [],
            },
            {
                "faixa": "curso",
                "oferta": "Curso",
                "demonstracao": False,
                "url_final": f"https://pay.exemplo.com/curso?src=meta&cpg=qz_frio_oct26&ctv={ctv}",
                "faltam": [],
            },
        ],
        "problemas": list(problemas),
    }


def _conferencia(problema_na_saida: str = "") -> dict:
    """O formato de `GET .../conferencia` do quiz (`apps/quiz/conferencia.py`)."""
    problemas = [problema_na_saida] if problema_na_saida else []
    return {
        "site_id": "site-teste",
        "quiz_slug": "encontre",
        "quiz_titulo": "Encontre sua solução",
        "host": "testserver",
        "ia_ligada": False,
        "versoes": [
            {
                "key": "B2",
                "perguntas": 3,
                "pontuacao": {"min": 3, "max": 9, "possiveis": [3, 4, 5, 6, 7, 8, 9]},
                "faixas": [
                    _faixa("desafio", 0, 5, "Desafio R$ 147", "https://pay.exemplo.com/desafio", 3),
                    _faixa("curso", 6, 9, "Curso R$ 1.579", "https://pay.exemplo.com/curso", 6),
                ],
                "ofertas": [],
                "problemas": [],
                "avisos": [],
            }
        ],
        "experiencias": [
            {
                "chave": "B2|text|frio",
                "version_key": "B2",
                "fmt": "text",
                "seg": "frio",
                "headline": "Seu próximo passo",
                "teste_url": TEXTO,
                "marcas": ['data-versao="B2"', "<h1>Seu próximo passo</h1>"],
                "problemas": [],
                "avisos": [],
            },
            {
                "chave": "B2|video|frio",
                "version_key": "B2",
                "fmt": "video",
                "seg": "frio",
                "headline": "Seu próximo passo",
                "teste_url": VIDEO,
                "marcas": ['data-versao="B2"', "<h1>Seu próximo passo</h1>", 'class="video-pendente"'],
                "problemas": [],
                "avisos": ["Vídeo em produção: a página abre com um aviso no lugar do vídeo."],
            },
        ],
        "links": [_link("a1", problemas), _link("a2", problemas)],
        "resumo": {"links": 2, "experiencias": 2, "versoes": 1, "problemas": 0, "avisos": 1},
    }


def _paginas(video_com_aviso: bool = True):
    """As páginas públicas do quiz, como o site as devolve."""

    def responder(request):
        aviso = '<div class="video-pendente">Vídeo em produção</div>'
        corpo = '<main data-versao="B2"><h1>Seu próximo passo</h1>'
        if request.url.params.get("fmt") == "video" and video_com_aviso:
            corpo += aviso
        return httpx.Response(200, html=corpo + "</main>")

    return respx.route(host="testserver").mock(side_effect=responder)


# ---------------------------------------------------------------- conferência


@respx.mock
def test_conferencia_abre_as_paginas_so_com_get_e_entrega_o_veredito_sem_custo():
    livia = _admin()
    robo = trabalhos.robo_de(livia)
    execucao, nova = trabalhos.delegar_conferencia(
        robo, livia, pedido_por="Lívia", origem="teste", host="testserver", slug="encontre", params={"v": "B2"}
    )
    assert nova
    _site()
    pedido = respx.get(QUIZ + "/conferencia").mock(return_value=httpx.Response(200, json=_conferencia()))
    paginas = _paginas()
    modelo_pago = respx.post(RESPOSTAS)

    executor.rodar_uma("teste")

    execucao.refresh_from_db()
    assert execucao.situacao == S.CONCLUIDA, execucao.motivo
    assert dict(pedido.calls.last.request.url.params) == {"site_id": "site-teste", "v": "B2"}
    # Abriu cada página uma vez, só para ler: nenhum formulário saiu daqui.
    assert len(paginas.calls) == 2
    assert {c.request.method for c in paginas.calls} == {"GET"}
    assert all(c.request.url.params["src"] == "teste" for c in paginas.calls)
    assert all("MeshcraftRobo" in c.request.headers["User-Agent"] for c in paginas.calls)
    # Sem IA e sem gasto.
    assert not modelo_pago.called and not Consumo.objects.exists() and execucao.modelo == ""
    entrega = Entrega.objects.get(execucao=execucao)
    assert entrega.tipo == "conferencia_quiz"
    assert "PODE SUBIR OS ANÚNCIOS, com avisos para saber" in entrega.conteudo
    assert "Páginas abertas no site: **2 de 2** abriram certas" in entrega.conteudo
    # Sem campanha na escolha, a prova da saída é o anúncio de origem completa.
    assert "Anúncio com a origem completa (os 12 parâmetros" in entrega.conteudo
    assert "**2 de 2** saídas levam tudo até a página da oferta" in entrega.conteudo
    assert "Links desta escolha" not in entrega.conteudo
    assert "Exemplo de um anúncio com a origem completa na versão **B2**" in entrega.conteudo
    assert "- **desafio**: `https://pay.exemplo.com/desafio?v=B2&fmt=text&seg=frio&src=meta" in entrega.conteudo
    assert "| B2 | 0 a 5 | desafio | «Quero» | `https://pay.exemplo.com/desafio` |" in entrega.conteudo
    assert "Vídeo em produção" in entrega.conteudo
    assert "Não enviou nenhum formulário" in entrega.conteudo
    assert "Não abriu a página da oferta nem o checkout" in entrega.conteudo
    assert execucao.resultado == f"PODE SUBIR OS ANÚNCIOS, com avisos para saber. Entrega nº {entrega.id}."
    assert not Tarefa.objects.filter(titulo__startswith="Corrigir os links").exists()


@respx.mock
def test_conferencia_com_problema_cria_uma_tarefa_de_correcao_e_depois_so_comenta():
    livia = _admin()
    robo = trabalhos.robo_de(livia)
    _site()
    respx.get(QUIZ + "/conferencia").mock(
        return_value=httpx.Response(200, json=_conferencia("A saída da faixa curso perde utm_term."))
    )
    _paginas(video_com_aviso=False)

    primeira, _ = trabalhos.delegar_conferencia(
        robo, livia, pedido_por="Lívia", origem="teste", host="testserver", slug="encontre", params={}
    )
    executor.rodar_uma("teste")
    primeira.refresh_from_db()
    assert primeira.situacao == S.CONCLUIDA, primeira.motivo
    assert primeira.resultado.startswith("NÃO SUBA OS ANÚNCIOS AINDA: 2 problema(s) para corrigir")
    entrega = Entrega.objects.get(execucao=primeira)
    assert "B2 · Vídeo no topo (VSL) · frio: a página abriu, mas sem o aviso de vídeo em produção." in entrega.conteudo
    # O mesmo problema de saída em dois links aparece uma vez, com a conta.
    assert "A saída da faixa curso perde utm_term. (2 links)" in entrega.conteudo
    tarefa = Tarefa.objects.get(titulo="Corrigir os links do quiz encontre antes de anunciar")
    assert tarefa.responsavel == livia
    assert tarefa.executor == Tarefa.Executor.PESSOA
    assert tarefa.situacao == Tarefa.Situacao.A_FAZER
    assert entrega.tarefa_id == tarefa.id

    segunda, nova = trabalhos.delegar_conferencia(
        robo, livia, pedido_por="Lívia", origem="teste", host="testserver", slug="encontre", params={}
    )
    assert nova
    executor.rodar_uma("teste")
    assert Tarefa.objects.filter(titulo__startswith="Corrigir os links").count() == 1
    comentario = Comentario.objects.get(tarefa=tarefa, texto__startswith="Nova conferência")
    assert "2 problema(s)" in comentario.texto


def test_a_conferencia_so_abre_paginas_do_quiz_no_proprio_site():
    def nao_devia_abrir(request):  # pragma: no cover - só falha se abrir
        pytest.fail(f"abriu {request.url}")

    with httpx.Client(transport=httpx.MockTransport(nao_devia_abrir)) as cliente:
        for url in (
            "https://outro.site/quiz/encontre/?v=B2",
            "http://testserver/quiz/encontre/?v=B2",
            "https://testserver/admin/quiz/encontre/",
            "https://usuario:senha@testserver/quiz/encontre/",
            "",
        ):
            pagina = quiz.abrir_pagina(cliente, {"teste_url": url, "marcas": []}, "testserver", "encontre")
            assert pagina["erro"] == "endereço fora do site do quiz", url


def test_relatorio_com_campanha_na_escolha_mostra_a_saida_dos_proprios_links():
    estado = {
        "conferencia": _conferencia(),
        "paginas": {
            "B2|text|frio": {"status": 200, "ms": 40, "faltam": [], "erro": ""},
            "B2|video|frio": {"status": 200, "ms": 50, "faltam": [], "erro": ""},
        },
        "params": {"v": "B2", "src": "meta", "med": "cpc", "cpg": "qz_frio_oct26", "ctv": "a1,a2"},
    }
    conteudo, veredito, problemas = quiz.relatorio_da_conferencia(estado, "Robô de Lívia", "")
    assert veredito == "PODE SUBIR OS ANÚNCIOS, com avisos para saber" and problemas == []
    assert "Links desta escolha: **2 de 2** levam a origem da campanha inteira" in conteudo
    assert "Exemplo do link **B2 · Texto · frio · anúncio a1**" in conteudo
    assert "`https://pay.exemplo.com/curso?src=meta&cpg=qz_frio_oct26&ctv=a1`" in conteudo
    # A prova de origem completa continua no resumo.
    assert "**2 de 2** saídas levam tudo até a página da oferta" in conteudo
    assert "Exemplo de um anúncio com a origem completa" not in conteudo


def test_gasto_em_dolar_escrito_como_no_brasil():
    from decimal import Decimal

    assert quiz._dolares(Decimal("0.018818"), 4) == "0,0188"
    assert quiz._dolares(Decimal("10")) == "10,00"
    assert quiz._dolares(Decimal("1234.5")) == "1.234,50"


# ---------------------------------------------------------------- leitura


EVOLUCAO = {
    "periodo": {"inicio": "2026-09-26", "fim": "2026-10-02"},
    "amostra_minima": 30,
    "visitas_elegiveis": 41,
    "teste": {"visitas": 12},
    "funil": [
        {
            "version_key": "B2",
            "ativa": True,
            "visitas_elegiveis": 41,
            "conclusoes": 20,
            "saidas": 9,
            "saidas_reais": 0,
            "saidas_demonstracao": 9,
            "taxa_conclusao": {"valor": 0.49, "numerador": 20, "denominador": 41, "inconclusiva": False},
            "taxa_saida_total": {"valor": 0.45, "numerador": 9, "denominador": 20, "inconclusiva": True},
            "etapas": [{"rotulo": "Pergunta 2", "viram": 35, "avancaram": 22, "perda": 13, "medida": True}],
        }
    ],
    "gargalos": [
        {
            "id": "etapa:B2:2",
            "tipo": "etapa",
            "escopo": {"nome": "geral"},
            "version_key": "B2",
            "prioridade": 1,
            "evidencia": {"texto": "13 de 35 saem na pergunta 2"},
            "inconclusivo": False,
        },
        {
            "id": "saida:B2",
            "tipo": "saida",
            "escopo": {"nome": "geral"},
            "version_key": "B2",
            "prioridade": 2,
            "evidencia": {"texto": "11 de 20 não clicam na oferta"},
            "inconclusivo": True,
        },
    ],
    "por_campanha": [
        {
            "nome": "qz_frio_oct26",
            "sessoes": 30,
            "versoes": [
                {
                    "version_key": "B2",
                    "visitas_elegiveis": 30,
                    "conclusoes": 15,
                    "saidas_reais": 0,
                    "saidas_demonstracao": 7,
                }
            ],
            "gargalos": [],
        }
    ],
    "por_dimensao": [{"tipo": "src", "escopos": [{"nome": "meta", "sessoes": 30}]}],
    "por_dia": [{"nome": "2026-10-01", "sessoes": 20, "versoes": [{"conclusoes": 10}]}],
    "dados_faltantes": [{"texto": "Sem dados de compra: o checkout ainda não avisa as vendas."}],
    "comercial": {"estado": "sem dados de compra"},
    "avisos": [],
}
RASCUNHO = {
    "publicadas": ["A", "B1", "B2"],
    "content": {"versions": [{"key": "A"}, {"key": "B1"}, {"key": "B2"}, {"key": "B3"}]},
}
LEITURA = {
    "leitura": "A B2 teve 41 visitas de verdade; metade chegou ao resultado.",
    "acoes": [
        {
            "titulo": "Encurtar a pergunta 2",
            "porque": "É onde mais gente sai.",
            "evidencia": "13 de 35 saem na pergunta 2",
            "tipo": "testar_versao",
        }
    ],
    "propostas": [
        {
            "gargalo_id": "etapa:B2:2",
            "versao_base": "B2",
            "hipotese": "A pergunta 2 é longa demais para o celular.",
            "mudanca": "Dividir a pergunta 2 em duas perguntas curtas.",
            "prioridade": "alta",
        },
        {
            "gargalo_id": "saida:B2",
            "versao_base": "B2",
            "hipotese": "O botão da oferta aparece tarde.",
            "mudanca": "Subir o botão.",
            "prioridade": "media",
        },
        {
            "gargalo_id": "inventado",
            "versao_base": "A",
            "hipotese": "x",
            "mudanca": "y",
            "prioridade": "baixa",
        },
    ],
}


def _quiz_dos_numeros(propostas=None):
    _site()
    respx.get(QUIZ + "/evolucao").mock(return_value=httpx.Response(200, json=EVOLUCAO))
    respx.get(QUIZ + "/propostas").mock(
        return_value=httpx.Response(200, json={"propostas": propostas or []})
    )
    respx.get(QUIZ + "/rascunho").mock(return_value=httpx.Response(200, json=RASCUNHO))
    return respx.post(QUIZ + "/propostas").mock(
        return_value=httpx.Response(
            201,
            json={
                "id": 7,
                "versao_base": "B2",
                "key_sugerida": "B4",
                "estado": "proposta",
                "prioridade": "alta",
                "gargalo": "etapa:B2:2",
                "hipotese": LEITURA["propostas"][0]["hipotese"],
                "mudanca": LEITURA["propostas"][0]["mudanca"],
            },
        )
    )


@respx.mock
def test_simulacao_leitura_com_o_modelo_forte_registra_so_a_proposta_com_amostra():
    livia = _admin()
    _guardar_chave()
    robo = trabalhos.robo_de(livia)
    execucao, nova = trabalhos.delegar_leitura(
        robo,
        livia,
        pedido_por="Lívia",
        origem="teste",
        host="testserver",
        slug="encontre",
        inicio="2026-09-26",
        fim="2026-10-02",
        observacao="Por que a pergunta 2 perde gente?",
    )
    assert nova
    tarefa = Tarefa.objects.get(pk=execucao.tarefa_id)
    assert tarefa.executor == Tarefa.Executor.ROBO and tarefa.situacao == Tarefa.Situacao.EM_ANDAMENTO
    criar = _quiz_dos_numeros()
    rota = respx.post(RESPOSTAS).mock(return_value=_texto_do_modelo(json.dumps(LEITURA)))

    executor.rodar_uma("teste")

    execucao.refresh_from_db()
    assert execucao.situacao == S.CONCLUIDA, execucao.motivo
    corpo = json.loads(rota.calls[0].request.content)
    assert corpo["model"] == "gpt-6-sol"
    assert corpo["text"]["format"]["name"] == "leitura_do_quiz"
    enviado = json.loads(corpo["input"][0]["content"])
    assert enviado["visitas_elegiveis"] == 41 and enviado["pedido_da_pessoa"] == "Por que a pergunta 2 perde gente?"
    # Só o gargalo com amostra vira proposta; o inconclusivo e o inventado ficam de fora.
    assert len(criar.calls) == 1
    proposta = json.loads(criar.calls[0].request.content)
    assert proposta["gargalo"] == "etapa:B2:2" and proposta["versao_base"] == "B2"
    # B3 já está no rascunho: a proposta pede a B4, sem tocar em versão nenhuma.
    assert proposta["key_sugerida"] == "B4"
    entrega = Entrega.objects.get(execucao=execucao)
    assert entrega.tipo == "leitura_quiz" and entrega.parcial is False and entrega.tarefa_id == tarefa.id
    assert "| B2 | 41 | 20 (49%) | 9 (45%) | sim |" in entrega.conteudo
    assert "1. **Encurtar a pergunta 2**" in entrega.conteudo
    assert "Proposta nº 7: criar a **B4** a partir da **B2**" in entrega.conteudo
    assert execucao.resultado == (
        "Leitura pronta: 41 visita(s) de verdade. 1ª ação: Encurtar a pergunta 2. "
        f"Entrega nº {entrega.id}; 1 proposta(s) de nova versão registrada(s)."
    )
    tarefa.refresh_from_db()
    assert tarefa.situacao == Tarefa.Situacao.CONCLUIDA
    assert Comentario.objects.filter(tarefa=tarefa, texto__startswith="Entrega pronta").exists()


def test_proposta_so_sai_de_gargalo_conclusivo_publicado_e_livre():
    dados = quiz.resumo_dos_numeros(EVOLUCAO, {"propostas": []}, RASCUNHO)
    assert [p["gargalo_id"] for p in quiz.propostas_aceitaveis(LEITURA, dados)] == ["etapa:B2:2"]
    ocupado = {**dados, "propostas": [{"gargalo": "etapa:B2:2", "estado": "aceita"}]}
    assert quiz.propostas_aceitaveis(LEITURA, ocupado) == []
    sem_amostra = {**dados, "gargalos": [{**g, "inconclusivo": True} for g in dados["gargalos"]]}
    assert quiz.propostas_aceitaveis(LEITURA, sem_amostra) == []


@respx.mock
def test_simulacao_leitura_sem_formato_combinado_sai_parcial_com_os_numeros():
    livia = _admin()
    _guardar_chave()
    robo = trabalhos.robo_de(livia)
    execucao, _ = trabalhos.delegar_leitura(
        robo, livia, pedido_por="Lívia", origem="teste", host="testserver", slug="encontre"
    )
    criar = _quiz_dos_numeros()
    respx.post(RESPOSTAS).mock(return_value=_texto_do_modelo("isto não é JSON"))
    executor.rodar_uma("teste")
    execucao.refresh_from_db()
    assert execucao.situacao != S.CONCLUIDA
    entrega = Entrega.objects.get(execucao=execucao)
    assert entrega.parcial is True
    assert "| B2 | 41 |" in entrega.conteudo and "não veio no formato combinado" in entrega.conteudo
    assert not criar.called


# ---------------------------------------------------------------- conversa


@respx.mock
def test_simulacao_pedido_na_pagina_do_quiz_monta_os_links_pelo_quiz():
    livia = _admin()
    _guardar_chave()
    cliente = _cliente()
    resposta = cliente.post(
        reverse("quiz_campanhas_robo", args=["encontre"]),
        {
            "acao": "pedir",
            "texto": "Monte os links da B2 para o TikTok, público frio, anúncios a1 e a2",
            "chave": "p1",
            "volta": "gerar=1&v=B2&fmt=text&seg=frio",
        },
    )
    assert resposta.status_code == 302
    assert resposta["Location"].endswith("?gerar=1&v=B2&fmt=text&seg=frio&robo=pedido#robo")
    execucao = Execucao.objects.get(tipo=Execucao.Tipo.CONVERSA)
    contexto = execucao.estado["contexto"]
    assert contexto["host"] == "testserver" and contexto["quiz"] == "encontre"
    assert contexto["selecao"]["v"] == "B2" and contexto["selecao"]["seg"] == "frio"

    retrato = respx.get(QUIZ + "/conferencia").mock(return_value=httpx.Response(200, json=_conferencia()))
    links = respx.get(QUIZ + "/links").mock(
        return_value=httpx.Response(
            200,
            json={
                "links": [
                    {"version_key": "B2", "fmt": "text", "seg": "frio", "ctv": "a1", "url": TEXTO + "&ctv=a1"},
                    {"version_key": "B2", "fmt": "text", "seg": "frio", "ctv": "a2", "url": TEXTO + "&ctv=a2"},
                ]
            },
        )
    )
    rota = respx.post(RESPOSTAS).mock(
        side_effect=[
            _pedido_de_acao(
                "montar_links_do_quiz",
                {
                    "slug": None,
                    "versoes": ["B2"],
                    "formatos": ["text"],
                    "publicos": ["frio"],
                    "origem": "tiktok",
                    "meio": "cpc",
                    "campanha": None,
                    "anuncios": ["a1", "a2"],
                    "utm_term": None,
                },
            ),
            _texto_do_modelo("Montei 2 links. Abra a página para copiar e testar."),
        ]
    )

    executor.rodar_uma("teste")

    execucao.refresh_from_db()
    assert execucao.situacao == S.CONCLUIDA, execucao.motivo
    assert retrato.called
    primeiro = json.loads(rota.calls[0].request.content)
    assert primeiro["model"] == "gpt-6-luna"
    assert {"montar_links_do_quiz", "delegar_conferencia_dos_links"} <= {f["name"] for f in primeiro["tools"]}
    assert "página de links e números do quiz encontre" in primeiro["instructions"]
    assert "Na tela estava escolhido: versões B2 · formatos Texto · públicos frio" in primeiro["instructions"]
    assert '"versao":"B2"' in primeiro["instructions"]
    pedido = dict(links.calls.last.request.url.params)
    assert pedido == {
        "site_id": "site-teste",
        "v": "B2",
        "fmt": "text",
        "seg": "frio",
        "src": "tiktok",
        "med": "cpc",
        "cpg": _nome_de_campanha_sugerido(["frio"]),
        "ctv": "a1,a2",
    }
    chamada = ChamadaDeFerramenta.objects.get(execucao=execucao)
    assert chamada.situacao == "feita" and chamada.resultado["total"] == 2
    assert reverse("quiz_campanhas", args=["encontre"]) in chamada.resultado["pagina_com_os_links"]
    kit = Entrega.objects.get(pk=chamada.resultado["entrega_id"])
    assert kit.tipo == "kit_de_links" and TEXTO + "&ctv=a2" in kit.conteudo
    assert Mensagem.objects.get(execucao=execucao, papel="robo").texto.startswith("Montei 2 links")

    # A página mostra a conversa sobre este quiz e a última entrega.
    _quiz_da_pagina()
    pagina = cliente.get(reverse("quiz_campanhas", args=["encontre"])).content.decode()
    assert "Conversa sobre este quiz" in pagina and "Montei 2 links" in pagina
    assert "Última entrega: Kit de links do quiz encontre" in pagina


@respx.mock
def test_quem_nao_administra_o_site_nao_recebe_nem_usa_as_acoes_do_quiz():
    ryan = MembroDaEquipe.objects.get(nome="Ryan")
    ryan.email = RYAN
    ryan.save()
    _guardar_chave()
    assert not ferramentas.pode_usar_o_quiz(ryan)
    assert ferramentas.definicoes_para(ryan) == ferramentas.DEFINICOES
    robo = trabalhos.robo_de(ryan)
    _, execucao = trabalhos.pedir_resposta(
        robo,
        ryan,
        "monte os links do quiz",
        chave="k",
        autor="Ryan",
        contexto={"host": "testserver", "quiz": "encontre"},
    )
    rota = respx.post(RESPOSTAS).mock(
        side_effect=[
            _pedido_de_acao("montar_links_do_quiz", {"slug": "encontre", "versoes": ["B2"]}),
            _texto_do_modelo("Isso fica com quem administra o site."),
        ]
    )
    executor.rodar_uma("teste")
    execucao.refresh_from_db()
    assert execucao.situacao == S.CONCLUIDA, execucao.motivo
    primeiro = json.loads(rota.calls[0].request.content)
    assert not ferramentas.NOMES_DO_QUIZ & {f["name"] for f in primeiro["tools"]}
    assert "Quizzes do site" not in primeiro["instructions"]
    chamada = ChamadaDeFerramenta.objects.get(execucao=execucao)
    assert chamada.situacao == "recusada"
    assert chamada.resultado == {"erro": "Os quizzes ficam com quem administra o site."}
    assert not Entrega.objects.exists()


# ---------------------------------------------------------------- a página


def _quiz_da_pagina():
    respx.get(QUIZ + "/campanhas").mock(
        return_value=httpx.Response(200, json={"campanhas": [], "aviso": "Clique não é compra."})
    )
    respx.get(QUIZ + "/links").mock(
        return_value=httpx.Response(
            200,
            json={"links": [{"version_key": "B2", "fmt": "text", "seg": "frio", "url": TEXTO}]},
        )
    )


@respx.mock
def test_a_pagina_de_links_mostra_o_robo_os_tres_pedidos_e_a_ultima_entrega():
    livia = _admin()
    cliente = _cliente()
    _quiz_da_pagina()
    url = reverse("quiz_campanhas", args=["encontre"])

    pagina = cliente.get(url)
    texto = pagina.content.decode()
    assert pagina.status_code == 200
    assert 'id="robo"' in texto and "Seu robô nesta página: Robô de Lívia" in texto
    assert texto.count(f'action="{reverse("quiz_campanhas_robo", args=["encontre"])}"') == 4
    assert "Conferir os links escolhidos" in texto and "Pedir a leitura dos números" in texto
    assert "A IA do robô não está pronta agora" in texto and "IA ainda não pronta" in texto
    assert "Conversa: gpt-6-luna · Leitura: gpt-6-sol" in texto
    assert "unsafe-inline" not in pagina["Content-Security-Policy"]
    # Nada rodando: a página não fica perguntando.
    assert 'data-acompanhar-quiz="' not in texto

    robo = trabalhos.robo_de(livia)
    execucao, _ = trabalhos.delegar_conferencia(
        robo, livia, pedido_por="Lívia", origem="teste", host="testserver", slug="encontre", params={}
    )
    rodando = cliente.get(url).content.decode()
    assert reverse("quiz_campanhas_robo_andamento", args=["encontre"]) in rodando
    assert "Conferência dos links do quiz" in rodando and "Na fila" in rodando
    # Com trabalho rodando, a lista de trabalhos fica aberta para mostrar o andamento.
    assert '<details class="trabalhos-quiz" open>' in rodando

    Execucao.objects.filter(pk=execucao.pk).update(
        situacao=S.CONCLUIDA, resultado="PODE SUBIR OS ANÚNCIOS: tudo conferido. Entrega nº 1."
    )
    Entrega.objects.create(
        robo=robo,
        execucao=execucao,
        tipo="conferencia_quiz",
        titulo="Conferência dos links do quiz encontre",
        conteudo="# Conferência\n\n**Veredito: PODE SUBIR OS ANÚNCIOS: tudo conferido.**\n",
    )
    pronta = cliente.get(url + "?robo=conferencia").content.decode()
    assert quiz.RESULTADOS["conferencia"] in pronta
    assert "Última entrega: Conferência dos links do quiz encontre" in pronta
    assert "<strong>Veredito: PODE SUBIR OS ANÚNCIOS: tudo conferido.</strong>" in pronta
    assert 'class="veredito bom">PODE SUBIR OS ANÚNCIOS: tudo conferido.' in pronta
    # Em outro quiz, nada disso aparece.
    respx.get("http://quiz:8000/interno/editor/quizzes/outro/campanhas").mock(
        return_value=httpx.Response(200, json={"campanhas": []})
    )
    respx.get("http://quiz:8000/interno/editor/quizzes/outro/links").mock(
        return_value=httpx.Response(200, json={"links": []})
    )
    outro = cliente.get(reverse("quiz_campanhas", args=["outro"])).content.decode()
    assert "Última entrega" not in outro


@respx.mock
def test_o_topo_do_robo_diz_o_que_ele_ja_sabe_e_o_proximo_passo():
    livia = _admin()
    cliente = _cliente()
    _quiz_da_pagina()
    url = reverse("quiz_campanhas", args=["encontre"])
    robo = trabalhos.robo_de(livia)
    agora = timezone.now()

    vazio = cliente.get(url).content.decode()
    assert "O que o robô já sabe deste quiz" in vazio and "Ainda não conferidos." in vazio
    assert "Antes de subir os anúncios, peça a conferência dos links" in vazio

    tarefa = Tarefa.objects.create(titulo="Corrigir os links do quiz encontre antes de anunciar", responsavel=livia)
    Execucao.objects.create(
        robo=robo,
        tipo=Execucao.Tipo.CONFERENCIA_QUIZ,
        situacao=S.CONCLUIDA,
        terminada_em=agora - timedelta(hours=2),
        resultado="NÃO SUBA OS ANÚNCIOS AINDA: 2 problema(s) para corrigir. Entrega nº 9.",
        estado={"quiz": "encontre", "paginas": {"a": {}, "b": {}, "c": {}}, "tarefa_de_correcao": tarefa.id},
    )
    ruim = cliente.get(url).content.decode()
    assert 'class="veredito ruim">NÃO SUBA OS ANÚNCIOS AINDA: 2 problema(s) para corrigir</div>' in ruim
    assert "3 página(s) abertas como visitante" in ruim
    assert f'{reverse("tarefa_ver", args=[tarefa.id])}">tarefa de correção nº {tarefa.id}</a>' in ruim
    assert f"Corrija o que a conferência apontou (tarefa nº {tarefa.id}) e peça outra conferência" in ruim
    # Nada rodando: a lista de trabalhos fica recolhida.
    assert '<details class="trabalhos-quiz">' in ruim

    tarefa.situacao = Tarefa.Situacao.CONCLUIDA
    tarefa.save()
    Execucao.objects.create(
        robo=robo,
        tipo=Execucao.Tipo.CONFERENCIA_QUIZ,
        situacao=S.CONCLUIDA,
        terminada_em=agora - timedelta(hours=1),
        resultado="PODE SUBIR OS ANÚNCIOS: tudo conferido. Entrega nº 10.",
        estado={"quiz": "encontre", "paginas": {"a": {}}},
    )
    leitura = Execucao.objects.create(
        robo=robo,
        tipo=Execucao.Tipo.LEITURA_QUIZ,
        situacao=S.CONCLUIDA,
        terminada_em=agora,
        modelo="gpt-6-sol",
        resultado="Leitura pronta: 11 visita(s) de verdade (pouca gente para decidir). Entrega nº 11.",
        estado={
            "quiz": "encontre",
            "dados": {"visitas_elegiveis": 11, "amostra_minima": 30},
            "leitura": {
                "leitura": "Pouca gente ainda.",
                "acoes": [
                    {"titulo": "Medir a pergunta 1.", "porque": "2 de 8 saem nela.", "evidencia": "-", "tipo": "medir"},
                    {"titulo": "Marcar a origem dos links", "porque": "9 sem campanha.", "evidencia": "-", "tipo": "campanha"},
                ],
            },
        },
    )
    Consumo.objects.create(execucao=leitura, robo=robo, modelo="gpt-6-sol", custo_estimado_usd=Decimal("0.011722"))
    entrega = Entrega.objects.create(
        robo=robo, execucao=leitura, tipo="leitura_quiz", titulo="Leitura dos números", conteudo="# Leitura\n"
    )
    pronta = cliente.get(url).content.decode()
    assert 'class="veredito bom">PODE SUBIR OS ANÚNCIOS: tudo conferido</div>' in pronta
    assert "tarefa de correção nº" not in pronta
    assert "<b>11</b> visita(s) de verdade: pouca gente para decidir (o robô decide a partir de 30)." in pronta
    assert "<li><b>Medir a pergunta 1</b> <span class=\"meta\">— 2 de 8 saem nela.</span></li>" in pronta
    assert "modelo gpt-6-sol · custou US$ 0,0117" in pronta
    assert f'{reverse("entrega_do_robo", args=[entrega.id])}">relatório</a>' in pronta
    assert (
        "Ainda é pouca gente: 11 de 30 visitas de verdade para decidir. Enquanto isso: "
        "Medir a pergunta 1. Peça outra leitura quando chegar a 30." in pronta
    )
    assert "Conferência de" in pronta and "todos os links do quiz · 1 página(s)" in pronta

    # A última conferência foi só dos links escolhidos: o quadro diz o que ela
    # cobriu e mostra também a do quiz todo.
    Execucao.objects.create(
        robo=robo,
        tipo=Execucao.Tipo.CONFERENCIA_QUIZ,
        situacao=S.CONCLUIDA,
        terminada_em=agora + timedelta(minutes=5),
        resultado="PODE SUBIR OS ANÚNCIOS, com avisos para saber. Entrega nº 12.",
        estado={
            "quiz": "encontre",
            "params": {"v": "B2", "fmt": "video", "seg": "escalando", "cpg": "qz_x"},
            "paginas": {"a": {}},
        },
    )
    parcial = cliente.get(url).content.decode()
    assert 'class="veredito bom">PODE SUBIR OS ANÚNCIOS, com avisos para saber</div>' in parcial
    assert "links escolhidos: B2 · Vídeo no topo (VSL) · escalando · qz_x" in parcial
    assert 'Todos os links do quiz: <b class="tom-bom">PODE SUBIR OS ANÚNCIOS: tudo conferido</b>' in parcial


@respx.mock
def test_os_botoes_da_pagina_poem_o_trabalho_na_fila_e_voltam_com_a_mesma_escolha():
    livia = _admin()
    cliente = _cliente()
    url = reverse("quiz_campanhas_robo", args=["encontre"])
    volta = "gerar=1&v=B2&fmt=text&seg=frio&robo=pedido"
    pagina = reverse("quiz_campanhas", args=["encontre"])

    resposta = cliente.post(url, {"acao": "conferir", "escopo": "tela", "chave": "c1", "volta": volta})
    assert resposta["Location"] == f"{pagina}?gerar=1&v=B2&fmt=text&seg=frio&robo=conferencia#robo"
    conferencia = Execucao.objects.get(tipo=Execucao.Tipo.CONFERENCIA_QUIZ)
    assert conferencia.pedido_por_membro_id == livia.id
    assert conferencia.estado == {
        "host": "testserver",
        "quiz": "encontre",
        "params": {"v": "B2", "fmt": "text", "seg": "frio", "cpg": _nome_de_campanha_sugerido(["frio"])},
    }
    # O mesmo clique repetido e um segundo pedido enquanto roda não criam outra.
    cliente.post(url, {"acao": "conferir", "escopo": "tela", "chave": "c1", "volta": volta})
    repetida = cliente.post(url, {"acao": "conferir", "escopo": "tudo", "chave": "c2", "volta": volta})
    assert repetida["Location"].endswith("robo=conferencia_rodando#robo")
    assert Execucao.objects.filter(tipo=Execucao.Tipo.CONFERENCIA_QUIZ).count() == 1

    datas = cliente.post(url, {"acao": "ler", "inicio": "01/10/2026", "chave": "l0", "volta": ""})
    assert datas["Location"] == f"{pagina}?robo=datas#robo"
    lida = cliente.post(
        url, {"acao": "ler", "inicio": "2026-09-26", "fim": "2026-10-02", "chave": "l1", "volta": volta}
    )
    assert lida["Location"].endswith("robo=leitura#robo")
    leitura = Execucao.objects.get(tipo=Execucao.Tipo.LEITURA_QUIZ)
    assert leitura.estado["inicio"] == "2026-09-26" and leitura.tarefa_id

    vazia = cliente.post(url, {"acao": "pedir", "texto": "   ", "chave": "m0", "volta": volta})
    assert vazia["Location"].endswith("robo=vazia#robo")
    assert not Execucao.objects.filter(tipo=Execucao.Tipo.CONVERSA).exists()

    andamento = cliente.get(reverse("quiz_campanhas_robo_andamento", args=["encontre"])).json()
    Execucao.objects.filter(pk=conferencia.pk).update(situacao=S.CONCLUIDA)
    depois = cliente.get(reverse("quiz_campanhas_robo_andamento", args=["encontre"])).json()
    assert andamento["marca"] and depois["marca"] != andamento["marca"]


@respx.mock
def test_sem_pessoa_da_equipe_a_pagina_explica_e_o_botao_nao_cria_nada():
    cliente = _cliente()
    _quiz_da_pagina()
    texto = cliente.get(reverse("quiz_campanhas", args=["encontre"])).content.decode()
    assert "Seu acesso não está ligado a uma pessoa da equipe" in texto
    resposta = cliente.post(
        reverse("quiz_campanhas_robo", args=["encontre"]), {"acao": "conferir", "chave": "x", "volta": ""}
    )
    assert resposta["Location"].endswith("?robo=sem_robo#robo")
    assert not Execucao.objects.exists()
