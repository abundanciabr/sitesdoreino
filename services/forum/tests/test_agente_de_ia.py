"""Guardas do RASCUNHO DA IA — a máquina escreve, a pessoa publica.

Mandato do mantenedor em 02/09/2026: *"o Admin clica na dúvida que quer
responder em um botão 'gerar resposta', e com um form opcional de campo único
para enviar mais detalhes de como o agente deverá responder"*.

As seis coisas que esta suíte existe para travar, em ordem do que dói mais:

1. **A IA nunca publica.** Depois de gerar, a contagem de mensagens do banco é a
   mesma. Se um dia alguém "adiantar" o gesto e fizer a view salvar, é aqui que
   o vermelho aparece.
2. **A porta é só da escola, e a recusa é 404.** Aluno e visitante não devem
   nem descobrir que ela existe. É a mesma regra das outras quatro rotas de
   moderação, e vale o mesmo teste.
3. **Nome de aluno não sai do fórum.** A conversa viaja rotulada `[Aluno]` e
   `[Escola]`. O corpo REAL da requisição é lido e conferido letra por letra:
   quem escreveu não precisa ir junto para a dúvida ser respondida.
4. **Falha de fora nunca vira tela quebrada nem publicação.** Chave ausente,
   chave recusada, limite, queda: cada uma vira uma frase diferente em
   português, com a conversa inteira de volta e a caixa de responder no lugar.
5. **O travessão que voltar é apontado.** A lei do projeto proíbe risca longa em
   texto publicado, e o portão `ci/travessao.py` não enxerga o que já está no
   banco. Aqui a máquina avisa e a pessoa reescreve.
6. **O modelo é o que a casa escolheu.** Trocar por um mais barato é decisão do
   mantenedor, nunca uma economia silenciosa dentro de um diff.

**A rede da Anthropic é dublada NO TRANSPORTE, nunca com `patch.object` no
método do `agente`** (`armadilhas/061`): assim o SDK monta o request de verdade
e lê a resposta de verdade, e um erro no jeito de chamar aparece aqui em vez de
aparecer só na primeira conta paga.
"""

from __future__ import annotations

import json

import httpx
import httpx2
import pytest
from django.test import Client
from django.urls import reverse

from apps.core import agente
from apps.forum.models import Area, Mensagem, Pessoa, Topico

pytestmark = pytest.mark.django_db

COOKIE = "meshcraft_sessao=um-cookie-opaco-qualquer"
CAIXA_DA_IA = "Rascunhar com a IA"
BOTAO = "Gerar resposta"

SESSAO_DO_DONO = {
    "autenticado": True,
    "id": "p_dono",
    "email": "dono@exemplo.com",
    "nome_exibido": "Davi",
}
SESSAO_DA_ANA = {
    "autenticado": True,
    "id": "p_ana",
    "email": "ana@exemplo.com",
    "nome_exibido": "Ana",
}


@pytest.fixture
def env(monkeypatch):
    """O env mínimo da célula, COM a chave da Anthropic.

    Quem quiser provar o mundo sem chave apaga a variável no próprio teste
    (`monkeypatch.delenv`), e isso deixa a intenção visível na linha.
    """
    for nome, valor in [
        ("IDENTIDADE_API_URL", "http://identidade:8000/interno"),
        ("IDENTIDADE_API_TOKEN", "tok-id"),
        ("ALUNOS_API_URL", "http://alunos:8000/api/alunos"),
        ("ALUNOS_API_TOKEN", "tok-al"),
        ("FORUM_PROFESSORES", ""),
        ("ADMIN_EMAILS", "dono@exemplo.com"),
        (agente.VARIAVEL_DA_CHAVE, "sk-ant-de-mentira"),
    ]:
        monkeypatch.setenv(nome, valor)


def dublar_as_celulas(monkeypatch, *, sessao=None, categoria=None):
    """A `identidade` e a `alunos`, dubladas por URL. Molde de test_moderacao."""

    def falso_get(self, url, **kwargs):
        endereco = str(url)
        if "identidade" in endereco:
            if sessao is None:
                raise AssertionError(f"chamada inesperada à identidade: {endereco}")
            return httpx.Response(200, json=sessao)
        if categoria is None:
            raise AssertionError(f"chamada inesperada à alunos: {endereco}")
        return httpx.Response(200, json={"categoria": categoria})

    monkeypatch.setattr(httpx.Client, "get", falso_get)


def como_dono(monkeypatch):
    """O administrador, e de propósito SEM matrícula."""
    dublar_as_celulas(monkeypatch, sessao=SESSAO_DO_DONO, categoria="cadastrado")


def como_aluna(monkeypatch):
    dublar_as_celulas(monkeypatch, sessao=SESSAO_DA_ANA, categoria="aluno")


def sem_login(monkeypatch):
    dublar_as_celulas(monkeypatch, sessao={"autenticado": False})


def corpo_de_resposta(texto: str, *, stop_reason: str = "end_turn") -> dict:
    """O JSON que a API da Anthropic devolve. Forma real, não inventada."""
    return {
        "id": "msg_de_teste",
        "type": "message",
        "role": "assistant",
        "model": agente.MODELO,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "content": [{"type": "text", "text": texto}],
        "usage": {"input_tokens": 120, "output_tokens": 340},
    }


def dublar_a_anthropic(monkeypatch, *, status=200, corpo=None, capturado=None):
    """Troca o TRANSPORTE do httpx2, que é por onde o SDK sai para a rede.

    O `sem_rede` do `conftest.py` já cortou esta mesma função; aqui ela é
    trocada de novo, por uma que responde. O SDK continua montando o request e
    lendo a resposta como monta e lê em produção.
    """

    def falso(self, request):
        if capturado is not None:
            capturado["url"] = str(request.url)
            capturado["headers"] = dict(request.headers)
            capturado["corpo"] = json.loads(request.content)
        return httpx2.Response(status, json=corpo or {}, request=request)

    monkeypatch.setattr(httpx2.HTTPTransport, "handle_request", falso)


@pytest.fixture
def sala():
    return Area.objects.create(
        slug="duvidas",
        nome="Dúvidas gerais",
        visibilidade=Area.Visibilidade.ALUNOS,
        quem_escreve=Area.QuemEscreve.ALUNO,
    )


@pytest.fixture
def conversa(sala):
    """A dúvida da Ana, com o nome dela no banco de propósito.

    O nome existir aqui é o que dá sentido ao teste que prova que ele NÃO viaja.
    """
    ana = Pessoa.objects.create(
        id_da_plataforma="p_ana", email="ana@exemplo.com", nome_exibido="Ana"
    )
    topico = Topico.objects.create(
        area=sala, autor=ana, titulo="A textura estica no braço"
    )
    Mensagem.objects.create(
        topico=topico, autor=ana, texto="Travei no Studio e a malha deforma."
    )
    return topico


def gerar(client, topico, **campos):
    return client.post(
        reverse("gerar_resposta", args=[topico.pk]),
        campos,
        headers={"cookie": COOKIE},
    )


def abrir(client, topico):
    return client.get(reverse("topico", args=[topico.pk]), headers={"cookie": COOKIE})


# ---------------------------------------------------------------------------
# 1. A PORTA — só a escola, e 404 para o resto
# ---------------------------------------------------------------------------


def test_a_aluna_nao_ve_a_caixa_e_a_porta_nao_existe_para_ela(
    env, monkeypatch, conversa
):
    como_aluna(monkeypatch)
    cliente = Client()

    tela = abrir(cliente, conversa)
    assert CAIXA_DA_IA not in tela.content.decode()

    # E esconder o botão não é a proteção: a porta responde 404, não 403.
    assert gerar(cliente, conversa, orientacao="").status_code == 404


def test_visitante_leva_404(env, monkeypatch, conversa):
    sem_login(monkeypatch)
    assert gerar(Client(), conversa, orientacao="").status_code == 404


def test_por_get_a_porta_recusa(env, monkeypatch, conversa):
    """Gerar por GET seria uma chamada PAGA que o robô do Google dispara."""
    como_dono(monkeypatch)
    resposta = Client().get(
        reverse("gerar_resposta", args=[conversa.pk]), headers={"cookie": COOKIE}
    )
    assert resposta.status_code == 405


# ---------------------------------------------------------------------------
# 2. A TELA — o botão aparece quando a view aceita, e explica quando não
# ---------------------------------------------------------------------------


def test_o_dono_ve_a_caixa_com_o_botao_e_o_campo_opcional(env, monkeypatch, conversa):
    como_dono(monkeypatch)
    tela = abrir(Client(), conversa).content.decode()
    assert CAIXA_DA_IA in tela
    assert BOTAO in tela
    assert 'name="orientacao"' in tela


def test_sem_chave_a_caixa_explica_em_vez_de_oferecer_o_botao(
    env, monkeypatch, conversa
):
    """Chave ausente não some com a caixa: some com o BOTÃO, e diz por quê.

    Sumir com a caixa inteira esconderia justamente a explicação de que falta a
    chave, e o mantenedor ficaria procurando um botão que ninguém contou que
    não existe.
    """
    monkeypatch.delenv(agente.VARIAVEL_DA_CHAVE)
    como_dono(monkeypatch)
    tela = abrir(Client(), conversa).content.decode()
    assert CAIXA_DA_IA in tela
    assert BOTAO not in tela
    assert "ainda não está ligada" in tela


def test_conversa_trancada_nao_gera_e_diz_o_motivo(env, monkeypatch, conversa):
    conversa.trancado = True
    conversa.save()
    como_dono(monkeypatch)

    resposta = gerar(Client(), conversa, orientacao="")
    assert resposta.status_code == 400
    assert "trancada" in resposta.content.decode()


# ---------------------------------------------------------------------------
# 3. O CAMINHO FELIZ — o rascunho cai na caixa de responder, e só lá
# ---------------------------------------------------------------------------


def test_o_rascunho_cai_na_caixa_de_resposta_e_nada_e_publicado(
    env, monkeypatch, conversa
):
    como_dono(monkeypatch)
    dublar_a_anthropic(
        monkeypatch, corpo=corpo_de_resposta("Escale o UV antes de pintar.")
    )
    antes = Mensagem.objects.count()

    resposta = gerar(Client(), conversa, orientacao="")
    tela = resposta.content.decode()

    assert resposta.status_code == 200
    assert "Escale o UV antes de pintar." in tela
    # O aviso vem junto: quem publica precisa saber o que a IA não sabe.
    assert "Leia inteiro antes de publicar" in tela
    # A PROVA QUE MAIS IMPORTA DESTE ARQUIVO: gerar não é publicar.
    assert Mensagem.objects.count() == antes


def test_o_modelo_e_o_que_a_casa_escolheu(env, monkeypatch, conversa):
    """Trocar de modelo é decisão do mantenedor, nunca economia silenciosa."""
    como_dono(monkeypatch)
    capturado: dict = {}
    dublar_a_anthropic(monkeypatch, corpo=corpo_de_resposta("ok"), capturado=capturado)

    gerar(Client(), conversa, orientacao="")

    assert capturado["corpo"]["model"] == "claude-opus-5"
    assert capturado["url"].endswith("/v1/messages")
    assert capturado["headers"]["x-api-key"] == "sk-ant-de-mentira"


def test_a_orientacao_de_quem_publica_chega_ao_modelo(env, monkeypatch, conversa):
    como_dono(monkeypatch)
    capturado: dict = {}
    dublar_a_anthropic(monkeypatch, corpo=corpo_de_resposta("ok"), capturado=capturado)

    gerar(Client(), conversa, orientacao="responda curto e cita a aula 3")

    pergunta = capturado["corpo"]["messages"][0]["content"]
    assert "responda curto e cita a aula 3" in pergunta
    assert "ORIENTAÇÃO DE QUEM VAI PUBLICAR" in pergunta


def test_sem_orientacao_o_pedido_nao_finge_que_teve_uma(env, monkeypatch, conversa):
    como_dono(monkeypatch)
    capturado: dict = {}
    dublar_a_anthropic(monkeypatch, corpo=corpo_de_resposta("ok"), capturado=capturado)

    gerar(Client(), conversa, orientacao="   ")

    assert (
        "ORIENTAÇÃO DE QUEM VAI PUBLICAR"
        not in capturado["corpo"]["messages"][0]["content"]
    )


# ---------------------------------------------------------------------------
# 4. O QUE VIAJA — a dúvida sim, quem perguntou não
# ---------------------------------------------------------------------------


def test_a_conversa_viaja_sem_nome_e_sem_email_de_ninguem(env, monkeypatch, conversa):
    """O nome do aluno não muda a resposta técnica, e por isso não sai daqui."""
    como_dono(monkeypatch)
    capturado: dict = {}
    dublar_a_anthropic(monkeypatch, corpo=corpo_de_resposta("ok"), capturado=capturado)

    gerar(Client(), conversa, orientacao="")

    inteiro = json.dumps(capturado["corpo"], ensure_ascii=False)
    assert "Travei no Studio" in inteiro  # a dúvida precisa ir
    assert "[Aluno]" in inteiro  # rotulada
    assert "Ana" not in inteiro
    assert "ana@exemplo.com" not in inteiro
    assert "p_ana" not in inteiro


def test_a_fala_da_escola_chega_rotulada_como_escola(env, monkeypatch, conversa):
    """A resposta que o próprio dono já deu não pode chegar como dúvida de aluno.

    Sem isto a IA repetiria o que a escola acabou de dizer, ou a contradiria.
    """
    dono = Pessoa.objects.create(
        id_da_plataforma="p_dono", email="dono@exemplo.com", nome_exibido="Davi"
    )
    Mensagem.objects.create(
        topico=conversa, autor=dono, texto="Confere a escala do objeto pai."
    )
    como_dono(monkeypatch)
    capturado: dict = {}
    dublar_a_anthropic(monkeypatch, corpo=corpo_de_resposta("ok"), capturado=capturado)

    gerar(Client(), conversa, orientacao="")

    pergunta = capturado["corpo"]["messages"][0]["content"]
    assert "[Escola] Confere a escala do objeto pai." in pergunta
    assert "[Aluno] Travei no Studio e a malha deforma." in pergunta


def test_mensagem_fora_do_ar_nao_viaja(env, monkeypatch, conversa):
    """O que a moderação tirou do ar está tirado do ar, inclusive para a máquina."""
    from django.utils import timezone

    Mensagem.objects.create(
        topico=conversa,
        autor=conversa.autor,
        texto="xingamento que a escola removeu",
        removida_em=timezone.now(),
    )
    como_dono(monkeypatch)
    capturado: dict = {}
    dublar_a_anthropic(monkeypatch, corpo=corpo_de_resposta("ok"), capturado=capturado)

    gerar(Client(), conversa, orientacao="")

    assert "xingamento" not in json.dumps(capturado["corpo"], ensure_ascii=False)


# ---------------------------------------------------------------------------
# 5. O TRAVESSÃO — a lei do projeto não alcança o banco, então a tela avisa
# ---------------------------------------------------------------------------


def test_travessao_na_resposta_vira_aviso_na_tela(env, monkeypatch, conversa):
    como_dono(monkeypatch)
    dublar_a_anthropic(
        monkeypatch,
        corpo=corpo_de_resposta("O UV — aquele mapa — precisa ser escalado."),
    )

    tela = gerar(Client(), conversa, orientacao="").content.decode()

    assert "risca longa" in tela
    # E o texto continua chegando inteiro: o conserto é da pessoa, não daqui.
    # Trocar o caractere aqui deixaria a frase torta com o portão satisfeito.
    assert "aquele mapa" in tela


def test_resposta_limpa_nao_recebe_o_aviso_de_travessao(env, monkeypatch, conversa):
    como_dono(monkeypatch)
    dublar_a_anthropic(
        monkeypatch, corpo=corpo_de_resposta("O UV (aquele mapa) precisa de escala.")
    )

    tela = gerar(Client(), conversa, orientacao="").content.decode()

    assert "risca longa" not in tela


def test_o_hifen_nao_e_travessao():
    """Guarda de português: `guarda-chuva` não pode acusar."""
    assert agente.travessoes_em("um guarda-chuva bem feito") == []
    assert agente.travessoes_em("um travessão — assim") == ["—"]
    assert agente.travessoes_em("meia risca – assim") == ["–"]


def test_resposta_cortada_no_meio_avisa(env, monkeypatch, conversa):
    como_dono(monkeypatch)
    dublar_a_anthropic(
        monkeypatch,
        corpo=corpo_de_resposta("Primeiro escale o", stop_reason="max_tokens"),
    )

    tela = gerar(Client(), conversa, orientacao="").content.decode()

    assert "terminou no meio" in tela


# ---------------------------------------------------------------------------
# 6. QUANDO NÃO DÁ — cada falha com a frase dela, e a conversa inteira de volta
# ---------------------------------------------------------------------------


def test_sem_chave_o_post_recusa_em_portugues_sem_tocar_a_rede(
    env, monkeypatch, conversa
):
    """A rede continua CORTADA pelo conftest: se este caminho tentar sair, estoura."""
    monkeypatch.delenv(agente.VARIAVEL_DA_CHAVE)
    como_dono(monkeypatch)

    resposta = gerar(Client(), conversa, orientacao="")
    tela = resposta.content.decode()

    assert resposta.status_code == 503
    assert "ainda não está ligada" in tela
    # A conversa volta INTEIRA: a caixa de responder continua no lugar.
    assert "Travei no Studio" in tela
    assert 'name="texto"' in tela


def test_chave_recusada_manda_o_mantenedor_para_a_chave(env, monkeypatch, conversa):
    como_dono(monkeypatch)
    dublar_a_anthropic(
        monkeypatch,
        status=401,
        corpo={
            "type": "error",
            "error": {"type": "authentication_error", "message": "x"},
        },
    )

    resposta = gerar(Client(), conversa, orientacao="")

    assert resposta.status_code == 503
    assert "chave de acesso da Anthropic foi recusada" in resposta.content.decode()


def test_limite_da_conta_tem_frase_propria(env, monkeypatch, conversa):
    """ "Sem crédito" e "a chave está errada" mandam a pessoa para lugares opostos."""
    como_dono(monkeypatch)
    dublar_a_anthropic(
        monkeypatch,
        status=429,
        corpo={"type": "error", "error": {"type": "rate_limit_error", "message": "x"}},
    )

    tela = gerar(Client(), conversa, orientacao="").content.decode()

    assert "recusou por limite" in tela


def test_a_orientacao_digitada_volta_na_caixinha_quando_da_errado(
    env, monkeypatch, conversa
):
    """Perder o que a pessoa digitou é a pior forma de recusar.

    A falha aqui é a de fora (a Anthropic recusou), e não a chave ausente: com
    a chave ausente a caixinha nem chega a existir na tela, então não há o que
    devolver. Esta é a situação real, a que acontece com o texto já digitado.
    """
    como_dono(monkeypatch)
    dublar_a_anthropic(
        monkeypatch,
        status=429,
        corpo={"type": "error", "error": {"type": "rate_limit_error", "message": "x"}},
    )

    tela = gerar(Client(), conversa, orientacao="fala da aula 3").content.decode()

    assert "fala da aula 3" in tela


def test_recusa_do_modelo_nao_vira_rascunho_vazio(env, monkeypatch, conversa):
    """Resposta sem texto apagaria a caixa em vez de dizer que não deu."""
    como_dono(monkeypatch)
    vazia = corpo_de_resposta("", stop_reason="end_turn")
    vazia["content"] = []
    dublar_a_anthropic(monkeypatch, corpo=vazia)

    resposta = gerar(Client(), conversa, orientacao="")

    assert resposta.status_code == 503
    assert "veio sem texto" in resposta.content.decode()


# ---------------------------------------------------------------------------
# 7. O PERCURSO INTEIRO, COM CSRF LIGADO — o caminho que o mantenedor usa
# ---------------------------------------------------------------------------


def test_o_botao_atravessa_o_csrf_de_verdade(env, monkeypatch, conversa):
    """Todos os testes acima entram pela porta com o cabeçalho `cookie` na mão,
    e `armadilhas/204` diz o que isso custa: `headers={"cookie": ...}` substitui
    o cabeçalho INTEIRO e leva junto o `forum_csrf` que a página tinha posto lá.
    Com o CSRF desligado na suíte, nenhum deles prova que o formulário funciona.

    Este prova. Ele abre a página como o navegador abre, lê o token que a tela
    imprimiu, e devolve o formulário como o botão devolve. Se o `{% csrf_token %}`
    sumir do template, é aqui que aparece o vermelho.
    """
    import re

    como_dono(monkeypatch)
    dublar_a_anthropic(
        monkeypatch, corpo=corpo_de_resposta("Escale o UV antes de pintar.")
    )

    navegador = Client(enforce_csrf_checks=True)
    navegador.cookies["meshcraft_sessao"] = "um-cookie-opaco-qualquer"

    tela = navegador.get(reverse("topico", args=[conversa.pk]))
    assert tela.status_code == 200

    # O TOKEN TEM DE SAIR DE DENTRO DESTE FORMULÁRIO, e não de qualquer um da
    # página. A tela de uma conversa tem meia dúzia de formulários de moderação,
    # todos com `{% csrf_token %}`: uma busca solta acharia o token de um deles,
    # o POST passaria, e o teste ficaria verde com o `{% csrf_token %}` ARRANCADO
    # do formulário da IA. Foi o que aconteceu na primeira versão deste teste, e
    # é a família de falso-verde que esta casa cataloga (`armadilhas/266`):
    # asserção com mais de uma causa suficiente.
    pagina = tela.content.decode()
    marca = 'action="' + reverse("gerar_resposta", args=[conversa.pk]) + '"'
    assert marca in pagina, "a tela não trouxe o formulário do botão de IA"
    formulario = pagina[
        pagina.index(marca) : pagina.index("</form>", pagina.index(marca))
    ]
    achado = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', formulario)
    assert achado, (
        "o formulário do botão de IA não imprimiu o token de CSRF. Sem ele o "
        "botão responde 403 no navegador do mantenedor, e só lá."
    )

    resposta = navegador.post(
        reverse("gerar_resposta", args=[conversa.pk]),
        {
            "orientacao": "responda curto",
            "csrfmiddlewaretoken": achado.group(1),
        },
    )

    assert resposta.status_code == 200, resposta.content[:400]
    assert "Escale o UV antes de pintar." in resposta.content.decode()


# ---------------------------------------------------------------------------
# 8. O WORKSPACE, E CADA RECUSA COM A FRASE DELA
# ---------------------------------------------------------------------------
# Isto tudo nasceu do PRIMEIRO clique real do mantenedor, em 02/09/2026. A chave
# dele é do tipo ligado à identidade, a Anthropic recusou com HTTP 400 pedindo o
# `anthropic-workspace-id`, e a tela disse a ele que "pode ser a internet do
# servidor". Duas coisas erradas de uma vez: faltava o cabeçalho, e a frase
# mandava para o lugar errado.


def erro_da_anthropic(mensagem: str) -> dict:
    """O corpo de recusa da API, na forma real."""
    return {
        "type": "error",
        "error": {"type": "invalid_request_error", "message": mensagem},
    }


def test_o_cabecalho_do_workspace_viaja_quando_a_variavel_existe(
    env, monkeypatch, conversa
):
    """O SDK NÃO lê esta variável sozinho quando a chave é passada no código.

    Medido em 02/09/2026 com o transporte dublado: `Anthropic(api_key=...)`
    ignora `ANTHROPIC_WORKSPACE_ID` do ambiente. Quem manda o cabeçalho é o
    nosso código, e é isto que este caso trava.
    """
    monkeypatch.setenv(agente.VARIAVEL_DO_WORKSPACE, "wrkspc_de_teste")
    como_dono(monkeypatch)
    capturado: dict = {}
    dublar_a_anthropic(monkeypatch, corpo=corpo_de_resposta("ok"), capturado=capturado)

    gerar(Client(), conversa, orientacao="")

    assert capturado["headers"][agente.CABECALHO_DO_WORKSPACE] == "wrkspc_de_teste"


def test_sem_a_variavel_o_cabecalho_NAO_viaja(env, monkeypatch, conversa):
    """Chave de workspace não precisa dele, e mandar vazio seria pior que não mandar."""
    monkeypatch.delenv(agente.VARIAVEL_DO_WORKSPACE, raising=False)
    como_dono(monkeypatch)
    capturado: dict = {}
    dublar_a_anthropic(monkeypatch, corpo=corpo_de_resposta("ok"), capturado=capturado)

    gerar(Client(), conversa, orientacao="")

    assert agente.CABECALHO_DO_WORKSPACE not in capturado["headers"]


def test_variavel_so_com_espaco_conta_como_ausente(env, monkeypatch, conversa):
    monkeypatch.setenv(agente.VARIAVEL_DO_WORKSPACE, "   ")
    como_dono(monkeypatch)
    capturado: dict = {}
    dublar_a_anthropic(monkeypatch, corpo=corpo_de_resposta("ok"), capturado=capturado)

    gerar(Client(), conversa, orientacao="")

    assert agente.CABECALHO_DO_WORKSPACE not in capturado["headers"]


def test_falta_o_workspace_manda_rodar_o_comando_de_novo(env, monkeypatch, conversa):
    """A recusa REAL que o mantenedor levou, palavra por palavra."""
    como_dono(monkeypatch)
    dublar_a_anthropic(
        monkeypatch,
        status=400,
        corpo=erro_da_anthropic(
            "anthropic-workspace-id is required when authenticating with an "
            "identity-linked API key; send the id of the workspace this request acts in."
        ),
    )

    tela = gerar(Client(), conversa, orientacao="").content.decode()

    assert "workspace" in tela
    assert "rodar de novo" in tela
    # E o que ela NÃO pode dizer: a rede funcionou perfeitamente aqui.
    assert "nem chegou a sair" not in tela


def test_conta_sem_credito_tem_frase_propria(env, monkeypatch, conversa):
    """Também chega como 400, e não como o 402 que o nome sugere."""
    como_dono(monkeypatch)
    dublar_a_anthropic(
        monkeypatch,
        status=400,
        corpo=erro_da_anthropic(
            "Your credit balance is too low to access the Anthropic API."
        ),
    )

    tela = gerar(Client(), conversa, orientacao="").content.decode()

    assert "sem crédito" in tela
    assert "workspace" not in tela


def test_problema_do_lado_deles_nao_culpa_a_conta(env, monkeypatch, conversa):
    como_dono(monkeypatch)
    dublar_a_anthropic(
        monkeypatch, status=500, corpo=erro_da_anthropic("internal server error")
    )

    tela = gerar(Client(), conversa, orientacao="").content.decode()

    assert "problema do lado dela" in tela


def test_recusa_desconhecida_diz_o_numero_e_nao_chuta_o_motivo(
    env, monkeypatch, conversa
):
    """A rede de segurança da heurística: nunca inventar um motivo."""
    como_dono(monkeypatch)
    dublar_a_anthropic(
        monkeypatch, status=418, corpo=erro_da_anthropic("algo que eu nunca vi")
    )

    tela = gerar(Client(), conversa, orientacao="").content.decode()

    assert "418" in tela
    assert "NÃO é falta de internet" in tela


def test_a_chamada_que_nem_sai_tem_frase_de_rede(env, monkeypatch, conversa):
    """Aqui o dublê NÃO é montado de propósito: vale o corte de rede do conftest.

    É o caso oposto ao das recusas acima, e a frase tem de ser oposta também:
    ali a rede funcionou e eles disseram não; aqui a chamada não chegou a sair.
    """
    como_dono(monkeypatch)

    tela = gerar(Client(), conversa, orientacao="").content.decode()

    assert "nem chegou a sair" in tela
    assert "não é a sua chave nem a sua conta" in tela


# ---------------------------------------------------------------------------
# 9. A TESOURA DA CONVERSA — o começo e o fim, nunca o silêncio
# ---------------------------------------------------------------------------


def test_conversa_grande_e_cortada_pelo_meio_e_o_corte_e_anunciado():
    falas = [("Aluno", "a pergunta original")] + [
        ("Aluno", "x" * 100) for _ in range(50)
    ]
    texto = agente._transcrever(falas, teto=600)

    assert "a pergunta original" in texto  # sem ela a resposta é sobre outra coisa
    assert "ficaram de fora" in texto  # a tesoura não é silenciosa
    assert len(texto) < 1200


def test_conversa_pequena_vai_inteira():
    falas = [("Aluno", "pergunta"), ("Escola", "resposta")]
    texto = agente._transcrever(falas)

    assert texto == "[Aluno] pergunta\n\n[Escola] resposta"
