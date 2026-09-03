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
    """Trocar de modelo é decisão do mantenedor, nunca economia silenciosa.

    Este caso ficou vermelho na troca do Opus 5 para o Haiku 4.5 (02/09/2026), e
    é assim que ele deve se comportar: mudar de modelo muda o custo, a qualidade
    e a velocidade do que o aluno lê, e não pode passar dentro de um diff sem
    alguém encostar no guarda.

    **O id COM DATA é parte da asserção.** O apelido `claude-haiku-4-5` segue o
    modelo quando a Anthropic o move; a data prende. Numa tela paga que fala com
    aluno, mudar de modelo é decisão, nunca surpresa de terça-feira.
    """
    como_dono(monkeypatch)
    capturado: dict = {}
    dublar_a_anthropic(monkeypatch, corpo=corpo_de_resposta("ok"), capturado=capturado)

    gerar(Client(), conversa, orientacao="")

    assert capturado["corpo"]["model"] == "claude-haiku-4-5-20251001"
    assert capturado["url"].endswith("/v1/messages")
    assert capturado["headers"]["x-api-key"] == "sk-ant-de-mentira"


def test_o_ajuste_de_capricho_NAO_viaja_com_o_haiku(env, monkeypatch, conversa):
    """`effort` é controle da geração nova, e o Haiku 4.5 pode recusá-lo.

    A referência diz que o nível `max` dá erro nele, o Haiku não está entre os
    modelos de pensamento adaptativo, e o resto só a API de capacidades ao vivo
    responde — que exige chave, e a chave desta casa não passa por agente.

    Omitir é seguro nos dois mundos: se ele aceitasse, não mandar apenas usa o
    padrão; se não aceita, mandar derrubaria TODA geração com HTTP 400. Este
    caso trava o lado que não quebra, e reprova quem devolver a chave ao corpo
    sem trocar o modelo junto.
    """
    como_dono(monkeypatch)
    capturado: dict = {}
    dublar_a_anthropic(monkeypatch, corpo=corpo_de_resposta("ok"), capturado=capturado)

    gerar(Client(), conversa, orientacao="")

    assert agente.ESFORCO is None, (
        "há um valor de esforço configurado: então confirme, na API de "
        "capacidades, que o modelo em uso o aceita — e troque este caso."
    )
    assert "output_config" not in capturado["corpo"]


def test_esforco_nulo_nunca_vira_effort_null_no_corpo(env, monkeypatch, conversa):
    """`None` mandado é diferente de não mandado.

    Um `{"effort": null}` no corpo faria a API recusar um pedido que, sem a
    chave, estaria perfeito. A guarda é o `if` do `_pedido`, e é isto que o
    prova: nem a chave, nem um nulo dentro dela.
    """
    como_dono(monkeypatch)
    capturado: dict = {}
    dublar_a_anthropic(monkeypatch, corpo=corpo_de_resposta("ok"), capturado=capturado)

    gerar(Client(), conversa, orientacao="")

    inteiro = json.dumps(capturado["corpo"])
    assert "effort" not in inteiro
    assert "null" not in inteiro


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
# 9. O RASCUNHO PRECISA APARECER PARA QUEM O PEDIU
# ---------------------------------------------------------------------------
# Medido em 02/09/2026, na primeira vez que o botão funcionou: a IA respondeu
# três vezes, o texto foi escrito na caixa, e o mantenedor disse "não apareceu
# nada". Ele estava certo. A caixa de escrever fica no FIM da página e o POST
# recarrega no topo, então o rascunho nascia fora da vista — três chamadas pagas
# que ninguém viu.


def test_o_rascunho_pronto_leva_o_cursor_ate_a_caixa(env, monkeypatch, conversa):
    """`autofocus` faz o navegador rolar até a caixa e pôr o cursor nela."""
    como_dono(monkeypatch)
    dublar_a_anthropic(monkeypatch, corpo=corpo_de_resposta("Escale o UV."))

    tela = gerar(Client(), conversa, orientacao="").content.decode()

    # O `autofocus` tem de estar na caixa de RESPONDER, e não em qualquer uma.
    # `name="texto"` sozinho NÃO serve de âncora: cada mensagem da conversa tem
    # a sua caixa de edição da moderação, com esse mesmo nome, e a primeira
    # ocorrência é uma delas. A caixa de responder é a única com `id="texto"`
    # exato (as da moderação são `texto12`, `texto13`...). Foi este teste
    # falhando que mostrou isso.
    marca = 'id="texto" name="texto"'
    assert marca in tela, "não achei a caixa de responder na tela"
    caixa = tela[tela.index(marca) : tela.index("</textarea>", tela.index(marca))]
    assert "autofocus" in caixa


def test_so_abrir_a_conversa_NAO_rouba_o_foco(env, monkeypatch, conversa):
    """Fixo, o autofocus jogaria a página para o fim de quem só quer ler."""
    como_dono(monkeypatch)

    tela = abrir(Client(), conversa).content.decode()

    assert "autofocus" not in tela


def test_o_sucesso_deixa_no_log_o_que_foi_gasto(env, monkeypatch, conversa):
    """O que deu certo também precisa aparecer, e com os tokens.

    O silêncio do sucesso custou uma rodada: sem linha nenhuma no log, "não
    rodou" e "rodou e deu certo" ficam idênticos vistos de fora — e a segunda
    era a verdadeira.
    """
    import logging

    recolhidas = []

    class Pega(logging.Handler):
        def emit(self, registro):
            recolhidas.append(registro.getMessage())

    dono_do_log = logging.getLogger("apps")
    pega = Pega()
    dono_do_log.addHandler(pega)
    nivel_antes = dono_do_log.level
    dono_do_log.setLevel(logging.INFO)
    try:
        como_dono(monkeypatch)
        dublar_a_anthropic(monkeypatch, corpo=corpo_de_resposta("Escale o UV."))
        gerar(Client(), conversa, orientacao="")
    finally:
        dono_do_log.removeHandler(pega)
        dono_do_log.setLevel(nivel_antes)

    linha = [m for m in recolhidas if "rascunho de" in m]
    assert linha, "o sucesso não deixou linha nenhuma no log"
    # Os números que interessam depois de uma chamada PAGA.
    assert "120" in linha[0] and "340" in linha[0]


def test_o_env_da_celula_deixa_o_log_de_apps_sair(settings):
    """A configuração sem a qual a linha acima existe e nunca aparece.

    Sem `LOGGING`, o Django não põe handler na raiz e vale o `lastResort` da
    biblioteca padrão, que só emite WARNING para cima: a falha aparecia, o
    sucesso não.
    """
    dos_apps = settings.LOGGING["loggers"]["apps"]
    assert dos_apps["level"] == "INFO"
    assert dos_apps["handlers"], "o logger de apps não tem para onde escrever"


# ---------------------------------------------------------------------------
# 10. O RASCUNHO AO VIVO — pedaco por pedaco, enquanto ela escreve
# ---------------------------------------------------------------------------
# Pedido do mantenedor em 02/09/2026, depois do susto de achar que o botão
# estava quebrado: alguns segundos sem sinal nenhum são indistinguíveis de uma
# tela travada.
#
# O dublê aqui devolve um corpo `text/event-stream` de verdade, com a sequência
# real de eventos da API. Assim o SDK faz o parsing que faz em produção, e um
# erro no jeito de consumir o fluxo aparece no teste em vez de aparecer na
# primeira chamada paga (`armadilhas/061`).

EVENTOS_DO_INICIO = (
    'event: message_start\ndata: {"type":"message_start","message":{"id":"msg_1",'
    '"type":"message","role":"assistant","model":"claude-opus-5","content":[],'
    '"stop_reason":null,"stop_sequence":null,'
    '"usage":{"input_tokens":120,"output_tokens":0}}}\n\n'
    'event: content_block_start\ndata: {"type":"content_block_start","index":0,'
    '"content_block":{"type":"text","text":""}}\n\n'
)


def corpo_ao_vivo(pedacos, *, stop_reason="end_turn"):
    """A resposta em fluxo, na forma que a API realmente manda."""
    corpo = EVENTOS_DO_INICIO
    for pedaco in pedacos:
        corpo += (
            'event: content_block_delta\ndata: {"type":"content_block_delta",'
            '"index":0,"delta":{"type":"text_delta","text":%s}}\n\n'
            % json.dumps(pedaco)
        )
    corpo += (
        'event: content_block_stop\ndata: {"type":"content_block_stop","index":0}\n\n'
    )
    corpo += (
        'event: message_delta\ndata: {"type":"message_delta","delta":'
        '{"stop_reason":"%s","stop_sequence":null},"usage":{"output_tokens":340}}\n\n'
        % stop_reason
    )
    corpo += 'event: message_stop\ndata: {"type":"message_stop"}\n\n'
    return corpo


def dublar_ao_vivo(monkeypatch, pedacos, *, stop_reason="end_turn", capturado=None):
    def falso(self, request):
        if capturado is not None:
            capturado["corpo"] = json.loads(request.content)
        return httpx2.Response(
            200,
            content=corpo_ao_vivo(pedacos, stop_reason=stop_reason).encode("utf-8"),
            headers={"content-type": "text/event-stream"},
            request=request,
        )

    monkeypatch.setattr(httpx2.HTTPTransport, "handle_request", falso)


def gerar_ao_vivo(client, topico, **campos):
    return client.post(
        reverse("gerar_resposta_ao_vivo", args=[topico.pk]),
        campos,
        headers={"cookie": COOKIE},
    )


def quadros(resposta):
    """As linhas JSON do fluxo, já interpretadas."""
    inteiro = b"".join(resposta.streaming_content).decode("utf-8")
    return [json.loads(linha) for linha in inteiro.splitlines() if linha.strip()]


def test_ao_vivo_manda_o_texto_em_pedacos_separados(env, monkeypatch, conversa):
    """Se viesse tudo num quadro só, o ao vivo seria uma espera com passos extras."""
    como_dono(monkeypatch)
    dublar_ao_vivo(monkeypatch, ["Escale ", "o UV ", "antes de pintar."])

    resposta = gerar_ao_vivo(Client(), conversa, orientacao="")
    lidos = quadros(resposta)

    assert resposta.status_code == 200
    textos = [q["t"] for q in lidos if "t" in q]
    assert textos == ["Escale ", "o UV ", "antes de pintar."]
    assert "".join(textos) == "Escale o UV antes de pintar."


def test_ao_vivo_termina_avisando_quem_vai_publicar(env, monkeypatch, conversa):
    como_dono(monkeypatch)
    dublar_ao_vivo(monkeypatch, ["Escale o UV."])

    lidos = quadros(gerar_ao_vivo(Client(), conversa, orientacao=""))

    fim = [q["fim"] for q in lidos if "fim" in q]
    assert fim, "o fluxo acabou sem dizer que acabou"
    assert "Leia inteiro antes de publicar" in fim[0]


def test_ao_vivo_aponta_o_travessao_no_fim(env, monkeypatch, conversa):
    """A mesma lei do modo de uma vez: a máquina aponta, a pessoa reescreve."""
    como_dono(monkeypatch)
    dublar_ao_vivo(monkeypatch, ["O UV ", "— aquele mapa — ", "precisa de escala."])

    lidos = quadros(gerar_ao_vivo(Client(), conversa, orientacao=""))

    fim = [q["fim"] for q in lidos if "fim" in q][0]
    assert "risca longa" in fim


def test_ao_vivo_avisa_quando_a_resposta_veio_cortada(env, monkeypatch, conversa):
    como_dono(monkeypatch)
    dublar_ao_vivo(monkeypatch, ["Primeiro escale o"], stop_reason="max_tokens")

    lidos = quadros(gerar_ao_vivo(Client(), conversa, orientacao=""))

    assert "terminou no meio" in [q["fim"] for q in lidos if "fim" in q][0]


def test_ao_vivo_manda_a_recusa_dentro_do_proprio_fluxo(env, monkeypatch, conversa):
    """No meio do fluxo o status já foi 200: a recusa tem de viajar no corpo."""
    como_dono(monkeypatch)
    dublar_a_anthropic(
        monkeypatch,
        status=400,
        corpo=erro_da_anthropic("Your credit balance is too low."),
    )

    lidos = quadros(gerar_ao_vivo(Client(), conversa, orientacao=""))

    erros = [q["erro"] for q in lidos if "erro" in q]
    assert erros and "sem crédito" in erros[0]


def test_ao_vivo_com_a_conversa_trancada_recusa_no_mesmo_formato(
    env, monkeypatch, conversa
):
    """Devolver HTML aqui obrigaria o navegador a ter dois jeitos de ler."""
    conversa.trancado = True
    conversa.save()
    como_dono(monkeypatch)

    resposta = gerar_ao_vivo(Client(), conversa, orientacao="")
    lidos = quadros(resposta)

    assert resposta.status_code == 400
    assert "trancada" in [q["erro"] for q in lidos if "erro" in q][0]


def test_ao_vivo_e_a_mesma_porta_fechada_para_quem_nao_modera(
    env, monkeypatch, conversa
):
    como_aluna(monkeypatch)
    assert gerar_ao_vivo(Client(), conversa, orientacao="").status_code == 404


def test_ao_vivo_por_get_recusa(env, monkeypatch, conversa):
    como_dono(monkeypatch)
    resposta = Client().get(
        reverse("gerar_resposta_ao_vivo", args=[conversa.pk]),
        headers={"cookie": COOKIE},
    )
    assert resposta.status_code == 405


def test_ao_vivo_pede_a_mesma_coisa_que_o_modo_de_uma_vez(env, monkeypatch, conversa):
    """As duas formas de pedir não podem passar a responder coisas diferentes.

    `_pedido` existe para isso, e este caso é o que o prova: o corpo enviado
    carrega o mesmo modelo, o mesmo esforço e a mesma transcrição sem nomes.
    """
    como_dono(monkeypatch)
    capturado: dict = {}
    dublar_ao_vivo(monkeypatch, ["ok"], capturado=capturado)

    # A RESPOSTA EM FLUXO E PREGUICOSA: o gerador so roda quando alguem le os
    # pedacos, entao a chamada a Anthropic ainda NAO aconteceu aqui. Conferir o
    # `capturado` sem consumir o fluxo devolve um dicionario vazio, e foi
    # exatamente assim que este teste falhou na primeira escrita.
    quadros(gerar_ao_vivo(Client(), conversa, orientacao="responda curto"))

    corpo = capturado["corpo"]
    assert corpo["model"] == agente.MODELO
    # O ao vivo pede EXATAMENTE o mesmo que o modo de uma vez, inclusive na
    # ausência do ajuste de capricho: se um dos dois voltasse a mandá-lo, as
    # duas formas passariam a responder coisas diferentes sem ninguém notar.
    assert ("output_config" in corpo) is (agente.ESFORCO is not None)
    assert corpo["stream"] is True
    pergunta = corpo["messages"][0]["content"]
    assert "responda curto" in pergunta
    assert "[Aluno] Travei no Studio e a malha deforma." in pergunta
    assert "Ana" not in json.dumps(corpo, ensure_ascii=False)


def test_a_tela_oferece_o_ao_vivo_sem_depender_dele(env, monkeypatch, conversa):
    """O `action` continua sendo a rota de sempre; o ao vivo viaja como dado.

    É essa ordem que faz o script ser melhoria e não dependência: sem ele, o
    formulário posta no `action` e o rascunho chega inteiro.
    """
    como_dono(monkeypatch)

    tela = abrir(Client(), conversa).content.decode()

    assert 'action="' + reverse("gerar_resposta", args=[conversa.pk]) + '"' in tela
    assert (
        'data-ao-vivo="' + reverse("gerar_resposta_ao_vivo", args=[conversa.pk]) + '"'
        in tela
    )
    assert 'id="ia-recado"' in tela


# ---------------------------------------------------------------------------
# 11. A TESOURA DA CONVERSA — o começo e o fim, nunca o silêncio
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
