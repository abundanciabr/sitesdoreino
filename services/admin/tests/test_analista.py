"""O robô analista (degrau 16 do plano do painel de gestão).

O que estes guardas protegem, e por que cada um existe:

1. **A chave é lida NO PONTO DE USO.** Trocar o env depois do import muda o
   comportamento na chamada seguinte. Chave lida no import seria env ausente
   virando HTTP 500 em toda página, com o deploy verde (`armadilhas/097`).
2. **Chave vazia é estado honesto.** A tela abre, explica em português que o
   robô está desligado e por quê, e nada quebra.
3. **Cada motivo de recusa tem a frase dele** (`armadilhas/297`). Cada caminho
   triste é coberto um a um, e um guarda extra prova que as frases são
   DIFERENTES entre si: duas falhas com a mesma frase mandam esperar por algo
   que nunca vem.
3b. **Nenhuma falha sobe crua até a tela.** HTTP 200 com o corpo cortado no
   meio, com a forma errada, sem `usage` ou com a página de um proxy dentro
   virava a página de erro do Django, e o formulário inteiro da reunião se
   perdia junto. Os quatro cenários foram medidos contra o SDK de verdade e
   cada um tem o guarda dele aqui.
4. **O contrato de saída é imposto, não pedido.** Resposta sem evidência, sem
   confiança declarada ou sem alternativa é recusada inteira, com a frase do
   formato. Meia análise num painel de gestão tem a mesma cara de certeza e não
   traz a prova.
5. **Ausência de dado nunca vira zero no dossiê** (`armadilhas/271`). Porta que
   não respondeu vira "não consegui medir", nunca 0.
6. **As duas telas não escrevem nada**, nem no banco nem no livro: o que sai é
   o bloco para colar numa sessão.

A rede é cortada em dois lugares, porque são duas bibliotecas. O `respx` dubla
aqui o `httpx` com que a `admin` fala com as células vizinhas. O `httpx2` (o
pacote que vem com o SDK da Anthropic) é cortado em `tests/conftest.py`, para a
suíte INTEIRA e nos dois transportes: proteção que depende de o próximo autor
lembrar de copiar o corte para o arquivo dele não é proteção, e a chave da
Anthropic está na máquina do mantenedor desde 02/09/2026 (`armadilhas/288`).
Aqui ficou só o dublê de cada teste, que troca a mesma função por uma resposta
de mentira.
"""

from __future__ import annotations

from dataclasses import replace
import datetime as dt
import json
import os

import anthropic
import httpx
import httpx2
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.core import analista, fechamento as fechamento_, placar, reuniao

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"
ALUNOS = "http://alunos:8000/api/alunos"
FILA = f"{ALUNOS}/pre-matriculas"
ALUNOS_LISTA = f"{ALUNOS}/matriculas"
HOJE = dt.date(2026, 9, 21)

RESPOSTA_INTEIRA = """\
TÍTULO: Ninguém cobrou o compromisso da semana passada
AFIRMAÇÃO: O compromisso de ligar para a fila venceu e não houve registro de \
resposta. A meta do ciclo continua parada no mesmo número.
EVIDÊNCIA: 1 de 1000 pessoas até 2026-12-15, e o compromisso aparece como não \
cumprido.
CONFIANÇA: média
ALTERNATIVAS:
- As pessoas foram chamadas e ninguém registrou, e aí o problema é o registro.
- A fila estava vazia na semana, e aí não havia o que cobrar.
PRÓXIMO PASSO: Abrir a fila de entrada e ligar para quem espera há mais de dois dias.
PRECISA DO DONO: não
"""


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    monkeypatch.setenv("ALUNOS_API_URL", ALUNOS)
    monkeypatch.setenv("ALUNOS_API_TOKEN", "token-do-par-admin-alunos")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"
    monkeypatch.setattr(placar.timezone, "localdate", lambda: HOJE)
    monkeypatch.setattr(reuniao.timezone, "localdate", lambda: HOJE)
    monkeypatch.setattr(fechamento_.timezone, "localdate", lambda: HOJE)


def dublar_a_anthropic(monkeypatch, *, status=200, corpo=None, capturado=None):
    """Troca o TRANSPORTE do `httpx2`, que é por onde o SDK sai para a rede.

    O SDK continua montando o request e lendo a resposta como faz em produção:
    o dublê é a rede, não o cliente.
    """

    def falso(self, request):
        if capturado is not None:
            capturado["url"] = str(request.url)
            capturado["headers"] = dict(request.headers)
            capturado["corpo"] = json.loads(request.content)
        return httpx2.Response(status, json=corpo or {}, request=request)

    monkeypatch.setattr(httpx2.HTTPTransport, "handle_request", falso)


def dublar_um_corpo_cru(monkeypatch, conteudo: bytes, *, tipo="application/json"):
    """Um HTTP 200 com o corpo EXATO, byte a byte, e o `content-type` dito.

    É o único jeito de encenar o que um proxy no caminho faz: cortar o JSON no
    meio, ou trocar a resposta inteira por uma página de manutenção em HTML.
    `dublar_a_anthropic` não serve, porque ele sempre serializa um dicionário e
    o que se quer aqui é justamente um corpo que não é um dicionário válido.
    """

    def falso(self, request):
        return httpx2.Response(
            200, content=conteudo, headers={"content-type": tipo}, request=request
        )

    monkeypatch.setattr(httpx2.HTTPTransport, "handle_request", falso)


def corpo_de_resposta(texto: str, *, stop_reason: str = "end_turn") -> dict:
    """O JSON que a API da Anthropic devolve. Forma real, não inventada."""
    return {
        "id": "msg_de_teste",
        "type": "message",
        "role": "assistant",
        "model": analista.MODELO,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "content": [{"type": "text", "text": texto}],
        "usage": {"input_tokens": 900, "output_tokens": 210},
    }


def corpo_vazio() -> dict:
    corpo = corpo_de_resposta("")
    corpo["content"] = []
    return corpo


def _dentro() -> Client:
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "id-opaco-123",
                "nome_exibido": "Fulano",
                "papel": None,
                "email": DONO,
            },
        )
    )
    c = Client()
    c.defaults["HTTP_COOKIE"] = COOKIE
    return c


def _a_escola_responde():
    respx.get(FILA, params={"status": "aguardando"}).mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "status": "aguardando",
                    "criada_em": "2026-09-16T12:00:00-03:00",
                    "esperando_ha_dias": 5,
                }
            ],
        )
    )
    respx.get(FILA, params={"status": "recusada"}).mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(ALUNOS_LISTA).mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "status": "ativa",
                    "origem": "liberado",
                    "criada_em": "2026-09-10T12:00:00-03:00",
                    "virou_aluno_em": "2026-09-11T12:00:00-03:00",
                }
            ],
        )
    )


# ---------------------------------------------------------------------------
# 0. A REDE CORTADA PARA A SUÍTE INTEIRA, NOS DOIS TRANSPORTES
# ---------------------------------------------------------------------------


def test_a_suite_inteira_esta_sem_a_rede_do_sdk_nos_dois_transportes():
    """O corte mora no `conftest.py` e alcança quem nunca dublou nada.

    Este teste não dubla o transporte de propósito: ele é o único da suíte que
    mede o corte de rede em si. Se o corte voltar para dentro deste arquivo, o
    próximo teste da célula que chamar a API paga não terá proteção nenhuma, e
    ninguém vai perceber, porque a suíte fica verde e a conta é que cresce
    (`armadilhas/288`).

    Os DOIS transportes, e não só o síncrono: no dia em que o analista ganhar
    `AsyncAnthropic` ou streaming, como o fórum já tem, o caminho assíncrono não
    pode ser uma porta aberta para a rede.
    """
    pedido = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    recado = "a suíte da admin não fala com a rede"

    with pytest.raises(httpx2.ConnectError, match=recado):
        httpx2.HTTPTransport().handle_request(pedido)
    with pytest.raises(httpx2.ConnectError, match=recado):
        httpx2.AsyncHTTPTransport().handle_async_request(pedido)


def test_a_suite_inteira_comeca_sem_a_chave_da_anthropic():
    """Nenhum teste da célula sai para a API paga por herdar a chave da máquina.

    A chave da Anthropic está na máquina do mantenedor desde 02/09/2026, então
    "não tenho chave aqui" não é mais proteção nenhuma.
    """
    assert analista.VARIAVEL_DA_CHAVE not in os.environ
    assert analista.VARIAVEL_DO_WORKSPACE not in os.environ
    assert analista.ligado() is False


# ---------------------------------------------------------------------------
# 1. A CHAVE — lida no ponto de uso, e vazia é estado honesto
# ---------------------------------------------------------------------------


def test_sem_chave_o_robo_esta_desligado_e_diz_por_que(monkeypatch):
    monkeypatch.delenv(analista.VARIAVEL_DA_CHAVE, raising=False)
    assert analista.ligado() is False
    with pytest.raises(analista.AnalistaIndisponivel) as caiu:
        analista.analisar(momento="reuniao", dossie="qualquer coisa")
    assert str(caiu.value) == analista.SEM_CHAVE
    assert "desligado" in analista.SEM_CHAVE and "VPS" in analista.SEM_CHAVE


def test_a_chave_e_lida_no_ponto_de_uso_e_nao_no_import(monkeypatch):
    """Pôr a chave depois do import já vale na chamada seguinte."""
    assert analista.ligado() is False
    monkeypatch.setenv(analista.VARIAVEL_DA_CHAVE, "sk-de-mentira")
    assert analista.ligado() is True


def test_o_workspace_so_viaja_quando_a_variavel_existe(monkeypatch):
    monkeypatch.setenv(analista.VARIAVEL_DA_CHAVE, "sk-de-mentira")
    capturado: dict = {}
    dublar_a_anthropic(
        monkeypatch, corpo=corpo_de_resposta(RESPOSTA_INTEIRA), capturado=capturado
    )
    analista.analisar(momento="reuniao", dossie="x")
    assert analista.CABECALHO_DO_WORKSPACE not in capturado["headers"]

    monkeypatch.setenv(analista.VARIAVEL_DO_WORKSPACE, "wrkspc_123")
    analista.analisar(momento="reuniao", dossie="x")
    assert capturado["headers"][analista.CABECALHO_DO_WORKSPACE] == "wrkspc_123"


def test_o_modelo_e_o_haiku_que_o_mantenedor_escolheu(monkeypatch):
    monkeypatch.setenv(analista.VARIAVEL_DA_CHAVE, "sk-de-mentira")
    capturado: dict = {}
    dublar_a_anthropic(
        monkeypatch, corpo=corpo_de_resposta(RESPOSTA_INTEIRA), capturado=capturado
    )
    analista.analisar(momento="reuniao", dossie="o dossie")
    assert capturado["corpo"]["model"] == "claude-haiku-4-5-20251001"
    assert "o dossie" in capturado["corpo"]["messages"][0]["content"]


# ---------------------------------------------------------------------------
# 2. OS CINCO CAMINHOS TRISTES — um a um, cada um com a frase dele
# ---------------------------------------------------------------------------


def _recusa(monkeypatch, *, status=200, corpo=None) -> str:
    monkeypatch.setenv(analista.VARIAVEL_DA_CHAVE, "sk-de-mentira")
    dublar_a_anthropic(monkeypatch, status=status, corpo=corpo)
    with pytest.raises(analista.AnalistaIndisponivel) as caiu:
        analista.analisar(momento="reuniao", dossie="x")
    return str(caiu.value)


def test_chave_recusada_tem_a_frase_dela(monkeypatch):
    frase = _recusa(
        monkeypatch,
        status=401,
        corpo={"type": "error", "error": {"type": "authentication_error"}},
    )
    assert frase == analista.CHAVE_RECUSADA


def test_conta_no_limite_tem_a_frase_dela(monkeypatch):
    frase = _recusa(
        monkeypatch,
        status=429,
        corpo={"type": "error", "error": {"type": "rate_limit_error"}},
    )
    assert frase == analista.SEM_SALDO_OU_LIMITE


def test_demora_tem_a_frase_dela(monkeypatch):
    monkeypatch.setenv(analista.VARIAVEL_DA_CHAVE, "sk-de-mentira")

    def estourou(self, request):
        raise httpx2.ReadTimeout("passou do tempo", request=request)

    monkeypatch.setattr(httpx2.HTTPTransport, "handle_request", estourou)
    with pytest.raises(analista.AnalistaIndisponivel) as caiu:
        analista.analisar(momento="reuniao", dossie="x")
    assert str(caiu.value) == analista.DEMOROU_DEMAIS


def test_resposta_vazia_tem_a_frase_dela(monkeypatch):
    assert _recusa(monkeypatch, corpo=corpo_vazio()) == analista.VEIO_VAZIA


def test_cada_motivo_de_recusa_tem_uma_frase_so_dele():
    """`armadilhas/297`: a mesma frase para duas falhas manda esperar em vão."""
    frases = [
        analista.SEM_CHAVE,
        analista.CHAVE_RECUSADA,
        analista.SEM_SALDO_OU_LIMITE,
        analista.DEMOROU_DEMAIS,
        analista.VEIO_VAZIA,
        analista.FORA_DO_FORMATO,
        analista.NAO_SAIU_DAQUI,
        analista.FALTA_O_WORKSPACE,
        analista.SEM_CREDITO,
        analista.PROBLEMA_DELES,
        analista.RECUSOU_O_PEDIDO.format(codigo=404),
        analista.RECUSOU,
        analista.VEIO_CORROMPIDA,
    ]
    assert len(set(frases)) == len(frases)
    for frase in frases:
        assert frase.strip() and frase[-1] in ".!"


def test_a_conta_sem_credito_nao_vira_a_frase_do_limite(monkeypatch):
    """400 com "credit balance" no corpo tem conserto próprio: pôr crédito."""
    frase = _recusa(
        monkeypatch,
        status=400,
        corpo={
            "type": "error",
            "error": {
                "type": "invalid_request_error",
                "message": "Your credit balance is too low",
            },
        },
    )
    assert frase == analista.SEM_CREDITO


def test_a_chave_de_identidade_sem_workspace_diz_o_que_rodar(monkeypatch):
    frase = _recusa(
        monkeypatch,
        status=400,
        corpo={
            "type": "error",
            "error": {
                "type": "invalid_request_error",
                "message": "anthropic-workspace-id is required",
            },
        },
    )
    assert frase == analista.FALTA_O_WORKSPACE


def test_a_rede_do_servidor_e_a_recusa_deles_sao_frases_diferentes(monkeypatch):
    monkeypatch.setenv(analista.VARIAVEL_DA_CHAVE, "sk-de-mentira")

    def nao_saiu(self, request):
        raise httpx2.ConnectError("sem rota")

    monkeypatch.setattr(httpx2.HTTPTransport, "handle_request", nao_saiu)
    with pytest.raises(analista.AnalistaIndisponivel) as caiu:
        analista.analisar(momento="reuniao", dossie="x")
    assert str(caiu.value) == analista.NAO_SAIU_DAQUI
    assert analista.NAO_SAIU_DAQUI != analista.PROBLEMA_DELES


def test_o_provedor_fora_do_ar_tem_a_frase_dele(monkeypatch):
    """Qualquer 5xx é problema do lado deles, e a frase diz isso na lata.

    Sem este guarda, trocar a linha do 5xx pela frase genérica do código HTTP
    deixa a suíte inteira verde, e o mantenedor passa a ler "me avise com o
    horário" quando a resposta certa é "espere alguns minutos".
    """
    frase = _recusa(
        monkeypatch,
        status=503,
        corpo={"type": "error", "error": {"type": "overloaded_error"}},
    )
    assert frase == analista.PROBLEMA_DELES


def test_uma_recusa_http_sem_motivo_conhecido_carrega_o_codigo(monkeypatch):
    """404 não é workspace, não é crédito e não é 5xx: sobra a frase geral."""
    frase = _recusa(
        monkeypatch,
        status=404,
        corpo={"type": "error", "error": {"type": "not_found_error"}},
    )
    assert frase == analista.RECUSOU_O_PEDIDO.format(codigo=404)
    assert "404" in frase, "sem o código, ninguém consegue procurar no log"


def test_a_recusa_do_proprio_modelo_tem_a_frase_dela(monkeypatch):
    """`stop_reason: refusal` é a trava de segurança do modelo, não uma falha."""
    frase = _recusa(
        monkeypatch,
        corpo=corpo_de_resposta(RESPOSTA_INTEIRA, stop_reason="refusal"),
    )
    assert frase == analista.RECUSOU


# ---------------------------------------------------------------------------
# 2b. O CORPO QUEBRADO — HTTP 200 que não é uma resposta da Anthropic
# ---------------------------------------------------------------------------
# Os quatro cenários abaixo foram MEDIDOS contra o SDK de verdade, em
# 07/09/2026: antes deste conserto, cada um subia um erro cru até a view e
# virava a página de erro do Django na cara do mantenedor, com o formulário
# inteiro da reunião perdido junto.


def test_o_corpo_cortado_no_meio_nao_sobe_erro_cru(monkeypatch):
    """200 com JSON truncado: a conexão morreu depois do cabeçalho."""
    monkeypatch.setenv(analista.VARIAVEL_DA_CHAVE, "sk-de-mentira")
    dublar_um_corpo_cru(monkeypatch, b'{"id": "msg_de_teste", "content": [{"ty')
    with pytest.raises(analista.AnalistaIndisponivel) as caiu:
        analista.analisar(momento="reuniao", dossie="x")
    assert str(caiu.value) == analista.VEIO_CORROMPIDA


def test_o_corpo_com_a_forma_errada_nao_sobe_erro_cru(monkeypatch):
    """200 que é um JSON válido e não é uma mensagem: contrato mudado."""
    frase = _recusa(
        monkeypatch,
        corpo={
            "id": "msg_de_teste",
            "type": "message",
            "role": "assistant",
            "model": analista.MODELO,
            "stop_reason": "end_turn",
            "content": None,
            "usage": None,
        },
    )
    assert frase == analista.VEIO_CORROMPIDA


def test_a_pagina_de_um_proxy_no_caminho_nao_sobe_erro_cru(monkeypatch):
    """200 com HTML: um portal cativo ou uma página de manutenção respondeu."""
    monkeypatch.setenv(analista.VARIAVEL_DA_CHAVE, "sk-de-mentira")
    dublar_um_corpo_cru(
        monkeypatch,
        b"<html><body><h1>502 Bad Gateway</h1></body></html>",
        tipo="text/html",
    )
    with pytest.raises(analista.AnalistaIndisponivel) as caiu:
        analista.analisar(momento="reuniao", dossie="x")
    assert str(caiu.value) == analista.VEIO_CORROMPIDA


def test_um_erro_do_sdk_que_nao_e_status_nem_conexao_nao_sobe_cru(monkeypatch):
    """A escada precisa de um degrau final, e este teste é a prova de que precisa.

    `anthropic.APIResponseValidationError` NÃO herda de `APIStatusError` nem de
    `APIConnectionError`: o `mro` dela é `APIError`, `AnthropicError`,
    `Exception`. Sem o `except anthropic.APIError` no fim, ela atravessa os seis
    degraus anteriores e vira a página de erro do Django.

    O dublê aqui é a fronteira do SDK, e não a rede, porque este erro nasce
    DENTRO do SDK, depois de a resposta ter chegado.
    """
    monkeypatch.setenv(analista.VARIAVEL_DA_CHAVE, "sk-de-mentira")
    assert not issubclass(
        anthropic.APIResponseValidationError,
        (anthropic.APIStatusError, anthropic.APIConnectionError),
    )

    pedido = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")

    def o_sdk_recusa(self, *args, **kwargs):
        raise anthropic.APIResponseValidationError(
            response=httpx2.Response(200, request=pedido), body=None
        )

    monkeypatch.setattr(anthropic.resources.Messages, "create", o_sdk_recusa)
    with pytest.raises(analista.AnalistaIndisponivel) as caiu:
        analista.analisar(momento="reuniao", dossie="x")
    assert str(caiu.value) == analista.VEIO_CORROMPIDA


def test_uma_analise_boa_nao_se_perde_por_causa_de_uma_linha_de_registro(monkeypatch):
    """O pior defeito é o que joga fora trabalho que já deu certo.

    A resposta chegou inteira e no formato. Faltar a contagem de tokens é um
    detalhe do LOG, e log nenhum pode custar ao mantenedor a análise que ele
    esperou noventa segundos para ler.
    """
    monkeypatch.setenv(analista.VARIAVEL_DA_CHAVE, "sk-de-mentira")
    corpo = corpo_de_resposta(RESPOSTA_INTEIRA)
    corpo["usage"] = None
    dublar_a_anthropic(monkeypatch, corpo=corpo)
    analise = analista.analisar(momento="reuniao", dossie="x")
    assert analise.titulo.startswith("Ninguém cobrou")
    assert analise.confianca == "média"


@respx.mock
def test_o_corpo_quebrado_nao_apaga_a_tela_da_reuniao(monkeypatch):
    """O caminho inteiro, da cadeira dele: a pauta continua na tela."""
    _a_escola_responde()
    monkeypatch.setenv(analista.VARIAVEL_DA_CHAVE, "sk-de-mentira")
    dublar_um_corpo_cru(monkeypatch, b'{"id": "msg_de_teste", "content": [{"ty')
    resposta = _dentro().post(
        reverse("reuniao"), {"acao": "analista", "compromisso1": "Ligar para a fila"}
    )
    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert analista.VEIO_CORROMPIDA[:40] in html
    assert "8. Os compromissos novos" in html, "a pauta continua inteira"
    assert "Ligar para a fila" in html, "o que ele digitou continua na tela"


# ---------------------------------------------------------------------------
# 3. O CONTRATO DE SAÍDA — imposto campo a campo, nunca meia análise
# ---------------------------------------------------------------------------


def test_a_resposta_inteira_vira_os_cinco_campos_do_contrato():
    a = analista.ler_a_resposta(RESPOSTA_INTEIRA)
    assert a.titulo.startswith("Ninguém cobrou")
    assert "não houve registro de resposta" in a.afirmacao
    assert "1 de 1000" in a.evidencia
    assert a.confianca == "média"
    assert len(a.alternativas) == 2
    assert a.alternativas[0].startswith("As pessoas foram chamadas")
    assert a.proximo_passo.startswith("Abrir a fila")
    assert a.precisa_do_dono is False
    assert a.tipo_de_registro == "nota"


def test_quando_pede_decisao_dele_o_registro_nasce_pendencia():
    texto = RESPOSTA_INTEIRA.replace("PRECISA DO DONO: não", "PRECISA DO DONO: sim")
    a = analista.ler_a_resposta(texto)
    assert a.precisa_do_dono is True
    assert a.tipo_de_registro == "pendencia"


def test_o_rotulo_sem_acento_continua_sendo_lido():
    texto = RESPOSTA_INTEIRA.replace("AFIRMAÇÃO:", "AFIRMACAO:").replace(
        "CONFIANÇA: média", "CONFIANCA: media"
    )
    assert analista.ler_a_resposta(texto).confianca == "média"


@pytest.mark.parametrize(
    "sem",
    ["EVIDÊNCIA:", "CONFIANÇA:", "ALTERNATIVAS:", "PRÓXIMO PASSO:", "AFIRMAÇÃO:"],
)
def test_faltando_um_campo_do_contrato_a_analise_inteira_e_recusada(sem):
    texto = "\n".join(
        linha for linha in RESPOSTA_INTEIRA.splitlines() if not linha.startswith(sem)
    )
    with pytest.raises(analista.AnalistaIndisponivel) as caiu:
        analista.ler_a_resposta(texto)
    assert str(caiu.value) == analista.FORA_DO_FORMATO


def test_confianca_fora_das_tres_palavras_e_recusada():
    texto = RESPOSTA_INTEIRA.replace("CONFIANÇA: média", "CONFIANÇA: mais ou menos")
    with pytest.raises(analista.AnalistaIndisponivel) as caiu:
        analista.ler_a_resposta(texto)
    assert str(caiu.value) == analista.FORA_DO_FORMATO


def test_alternativa_que_e_so_um_hifen_nao_conta_como_alternativa():
    """O campo veio preenchido, e mesmo assim não há leitura nenhuma dentro."""
    texto = RESPOSTA_INTEIRA.replace(
        "- As pessoas foram chamadas e ninguém registrou, e aí o problema é o registro.\n"
        "- A fila estava vazia na semana, e aí não havia o que cobrar.\n",
        "-\n",
    )
    with pytest.raises(analista.AnalistaIndisponivel) as caiu:
        analista.ler_a_resposta(texto)
    assert str(caiu.value) == analista.FORA_DO_FORMATO


def test_precisa_do_dono_fora_de_sim_e_nao_e_recusado():
    texto = RESPOSTA_INTEIRA.replace("PRECISA DO DONO: não", "PRECISA DO DONO: talvez")
    with pytest.raises(analista.AnalistaIndisponivel) as caiu:
        analista.ler_a_resposta(texto)
    assert str(caiu.value) == analista.FORA_DO_FORMATO


# ---------------------------------------------------------------------------
# 4. O DOSSIÊ — ausência de dado nunca vira zero
# ---------------------------------------------------------------------------


def test_o_dossie_diz_nao_consegui_medir_e_nunca_escreve_zero():
    """`armadilhas/271`: porta que não respondeu não é escola que não vendeu."""
    texto = analista.dossie_da_reuniao(
        {
            "meta": None,
            "placar": None,
            "barra": None,
            "direcao": None,
            "restricao": None,
            "compromissos": None,
            "doze": None,
            "latencias": None,
            "mudancas": None,
        },
        HOJE,
    )
    assert "alvo: não consegui medir pessoas até não consegui medir" in texto
    assert "medido hoje: não consegui medir" in texto
    assert "suspeita: não consegui medir" in texto
    assert "não consegui ler o livro" in texto
    assert " 0" not in texto, "ausência de dado não pode aparecer como zero"
    assert "None" not in texto, "ausência nunca chega à tela como o nome do vazio"


def test_o_dossie_do_fechamento_leva_o_ciclo_e_a_semana():
    dados = {
        "estado": "correndo",
        "ate": dt.date(2026, 12, 15),
        "semanas_restantes": 12,
        "veredito": "ainda-nao-cobra",
        "previsao": {"veredito": "ainda-nao-da-para-saber", "porque": "a meta é zero"},
        "fase": {
            "livro": True,
            "fase": "achando",
            "provados": 0,
            "total": 8,
            "portoes": [
                {"nome": "Demanda", "prova": "gente querendo", "provado": False}
            ],
            "declarados_sem_prova": [],
        },
    }
    texto = analista.dossie_do_fechamento(dados, {"meta": None}, HOJE)
    assert "achando" in texto and "0 de 8" in texto
    assert "[em aberto] Demanda" in texto
    assert "A META DO CICLO" in texto, "o dossiê da semana vem junto"


def test_livro_ausente_no_fechamento_nao_vira_nenhum_portao_provado():
    texto = analista.dossie_do_fechamento(
        {"fase": {"livro": False}}, {"meta": None}, HOJE
    )
    assert "não sei em que fase a escola está" in texto
    assert "achando" not in texto


# ---------------------------------------------------------------------------
# 5. O BLOCO PARA COLAR — o vocabulário do livro, e nada de escrita
# ---------------------------------------------------------------------------


def test_o_pedido_carrega_o_vocabulario_do_livro():
    a = analista.ler_a_resposta(RESPOSTA_INTEIRA)
    texto = analista.montar_o_pedido(a, "reuniao", HOJE)
    assert "21/09/2026" in texto
    assert "tipo: nota" in texto
    assert "PLANO-PAINEL-DE-GESTAO.md, degrau 16" in texto
    assert "painel/registros/" in texto
    assert "precisa_do_dono: false" in texto
    assert "AFIRMAÇÃO:" in texto and "EVIDÊNCIA:" in texto
    assert "CONFIANÇA: média" in texto
    assert "PRÓXIMO PASSO:" in texto


@pytest.mark.parametrize("momento", ["reuniao", "fechamento"])
def test_o_pedido_que_pede_decisao_dele_exige_os_seis_campos(momento):
    texto = RESPOSTA_INTEIRA.replace("PRECISA DO DONO: não", "PRECISA DO DONO: sim")
    pedido = analista.montar_o_pedido(analista.ler_a_resposta(texto), momento, HOJE)
    assert "tipo: pendencia" in pedido
    assert "precisa_do_dono: true" in pedido
    assert "se_eu_nao_decidir" in pedido and "Central de Pendências" in pedido
    assert "seis campos obrigatórios" in pedido
    for campo in (
        "porque_so_voce",
        "proximo_passo",
        "se_eu_nao_decidir",
        "recomendacao",
        "reversivel",
        "impacto",
    ):
        assert f"  {campo}: " in pedido, f"falta instrução para {campo}"
    assert "O robô justifica por que só o mantenedor pode decidir" in pedido
    assert "não peça ao mantenedor para completar esses campos" in pedido


@pytest.mark.parametrize(
    "passo",
    [
        "Autorizar a despesa de R$ 30 ou manter o serviço atual.",
        'Escolher entre "publicar" e "revisar". A evidência está no painel.',
    ],
)
def test_o_pedido_reaproveita_o_proximo_passo_da_analise(passo):
    a = analista.ler_a_resposta(
        RESPOSTA_INTEIRA.replace("PRECISA DO DONO: não", "PRECISA DO DONO: sim")
    )
    a = replace(a, proximo_passo=passo)
    pedido = analista.montar_o_pedido(a, "reuniao", HOJE)
    assert f"  proximo_passo: {passo}" in pedido
    assert f"    PRÓXIMO PASSO: {passo}" in pedido


def test_o_pedido_tecnico_nao_exige_campos_de_decisao_do_mantenedor():
    a = analista.ler_a_resposta(RESPOSTA_INTEIRA)
    pedido = analista.montar_o_pedido(a, "reuniao", HOJE)
    assert "tipo: nota" in pedido and "precisa_do_dono: false" in pedido
    assert "porque_so_voce:" not in pedido
    assert "  proximo_passo:" not in pedido


# ---------------------------------------------------------------------------
# 6. AS DUAS TELAS
# ---------------------------------------------------------------------------


@respx.mock
def test_a_reuniao_sem_chave_explica_que_o_robo_esta_desligado():
    _a_escola_responde()
    html = _dentro().get(reverse("reuniao")).content.decode()
    assert "robô analista" in html
    assert "desligado neste servidor" in html


@respx.mock
def test_o_fechamento_sem_chave_explica_que_o_robo_esta_desligado():
    _a_escola_responde()
    html = _dentro().get(reverse("fechamento")).content.decode()
    assert "robô analista" in html
    assert "desligado neste servidor" in html


@respx.mock
def test_pedir_a_analise_sem_chave_devolve_a_tela_inteira_com_a_frase():
    _a_escola_responde()
    resposta = _dentro().post(reverse("reuniao"), {"acao": "analista"})
    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert "desligado neste servidor" in html
    assert "8. Os compromissos novos" in html, "a pauta continua inteira"


@respx.mock
def test_a_reuniao_mostra_a_analise_e_o_bloco_para_colar(monkeypatch):
    _a_escola_responde()
    monkeypatch.setenv(analista.VARIAVEL_DA_CHAVE, "sk-de-mentira")
    dublar_a_anthropic(monkeypatch, corpo=corpo_de_resposta(RESPOSTA_INTEIRA))
    resposta = _dentro().post(reverse("reuniao"), {"acao": "analista"})
    html = resposta.content.decode()
    assert "Ninguém cobrou o compromisso" in html
    assert "Confiança" in html and "média" in html
    assert "Outras leituras possíveis" in html
    assert "tipo: nota" in html, "o bloco para colar veio junto"
    assert all(c.request.method == "GET" for c in respx.calls), "a tela só lê"


@respx.mock
def test_o_fechamento_mostra_a_analise_do_ciclo(monkeypatch):
    _a_escola_responde()
    monkeypatch.setenv(analista.VARIAVEL_DA_CHAVE, "sk-de-mentira")
    capturado: dict = {}
    dublar_a_anthropic(
        monkeypatch, corpo=corpo_de_resposta(RESPOSTA_INTEIRA), capturado=capturado
    )
    html = _dentro().post(reverse("fechamento"), {"acao": "analista"}).content.decode()
    assert "Ninguém cobrou o compromisso" in html
    assert "FECHAMENTO DO CICLO" in capturado["corpo"]["messages"][0]["content"]


@respx.mock
def test_a_falha_da_ia_nao_apaga_a_tela_nem_o_que_foi_digitado(monkeypatch):
    _a_escola_responde()
    monkeypatch.setenv(analista.VARIAVEL_DA_CHAVE, "sk-de-mentira")
    dublar_a_anthropic(
        monkeypatch,
        status=429,
        corpo={"type": "error", "error": {"type": "rate_limit_error"}},
    )
    html = (
        _dentro()
        .post(
            reverse("reuniao"),
            {"acao": "analista", "compromisso1": "Ligar para a fila"},
        )
        .content.decode()
    )
    assert analista.SEM_SALDO_OU_LIMITE[:40] in html
    assert "Ligar para a fila" in html, "o que ele digitou continua na tela"


@respx.mock
def test_o_botao_de_montar_o_pedido_continua_fazendo_o_que_fazia():
    """O analista não roubou o POST antigo da reunião."""
    _a_escola_responde()
    html = (
        _dentro()
        .post(reverse("reuniao"), {"compromisso1": "Abrir a fila toda manhã"})
        .content.decode()
    )
    assert "O pedido para o robô" in html
    assert "tipo `compromisso`" in html
