"""O robô analista (degrau 16 do plano do painel de gestão).

O que estes guardas protegem, e por que cada um existe:

1. **A chave é lida NO PONTO DE USO.** Trocar o env depois do import muda o
   comportamento na chamada seguinte. Chave lida no import seria env ausente
   virando HTTP 500 em toda página, com o deploy verde (`armadilhas/097`).
2. **Chave vazia é estado honesto.** A tela abre, explica em português que o
   robô está desligado e por quê, e nada quebra.
3. **Cada motivo de recusa tem a frase dele** (`armadilhas/297`). Os cinco
   caminhos tristes exigidos pela tarefa (chave ausente, chave recusada, conta
   no limite, demora, resposta vazia) são cobertos um a um, e um guarda extra
   prova que as cinco frases são DIFERENTES entre si: duas falhas com a mesma
   frase mandam esperar por algo que nunca vem.
4. **O contrato de saída é imposto, não pedido.** Resposta sem evidência, sem
   confiança declarada ou sem alternativa é recusada inteira, com a frase do
   formato. Meia análise num painel de gestão tem a mesma cara de certeza e não
   traz a prova.
5. **Ausência de dado nunca vira zero no dossiê** (`armadilhas/271`). Porta que
   não respondeu vira "não consegui medir", nunca 0.
6. **As duas telas não escrevem nada**, nem no banco nem no livro: o que sai é
   o bloco para colar numa sessão.

A rede é cortada aqui de dois jeitos, porque são duas bibliotecas: `respx`
dubla o `httpx` com que a `admin` fala com as células vizinhas, e o transporte
do `httpx2` (o pacote que vem com o SDK da Anthropic) é trocado à mão. Sem o
segundo, a suíte diria não falar com a rede e poderia chamar a API paga de
verdade, com a chave da máquina de quem rodasse os testes (`armadilhas/288`).
"""

from __future__ import annotations

import datetime as dt
import json

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
    monkeypatch.delenv(analista.VARIAVEL_DA_CHAVE, raising=False)
    monkeypatch.delenv(analista.VARIAVEL_DO_WORKSPACE, raising=False)
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"
    monkeypatch.setattr(placar.timezone, "localdate", lambda: HOJE)
    monkeypatch.setattr(reuniao.timezone, "localdate", lambda: HOJE)
    monkeypatch.setattr(fechamento_.timezone, "localdate", lambda: HOJE)


@pytest.fixture(autouse=True)
def sem_a_rede_do_sdk(monkeypatch):
    """O `httpx2` não fala com ninguém a menos que o teste dubla o transporte.

    Fail-closed: quem esquecer de dublar recebe uma recusa de conexão, nunca uma
    chamada de verdade à API paga.
    """

    def recusa(*args, **kwargs):
        raise httpx2.ConnectError("a suíte da admin não fala com a rede")

    monkeypatch.setattr(httpx2.HTTPTransport, "handle_request", recusa)


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


def test_as_cinco_frases_dos_caminhos_tristes_sao_diferentes():
    """`armadilhas/297`: a mesma frase para duas falhas manda esperar em vão."""
    cinco = [
        analista.SEM_CHAVE,
        analista.CHAVE_RECUSADA,
        analista.SEM_SALDO_OU_LIMITE,
        analista.DEMOROU_DEMAIS,
        analista.VEIO_VAZIA,
    ]
    assert len(set(cinco)) == 5
    for frase in cinco:
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


def test_o_pedido_que_pede_decisao_dele_manda_preencher_os_quatro():
    texto = RESPOSTA_INTEIRA.replace("PRECISA DO DONO: não", "PRECISA DO DONO: sim")
    pedido = analista.montar_o_pedido(
        analista.ler_a_resposta(texto), "fechamento", HOJE
    )
    assert "tipo: pendencia" in pedido
    assert "precisa_do_dono: true" in pedido
    assert "se_eu_nao_decidir" in pedido and "Central de Pendências" in pedido


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
