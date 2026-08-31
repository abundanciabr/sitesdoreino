"""O MASCOTE da caixa de escrever, medido pela borda HTTP.

Pedido do mantenedor em 30/08/2026: um ícone animado, com cara de 3D/Blender/
Roblox, no formulário de CRIAR — aqui e na Caixa de Sugestões. Em 31/08 ele
escolheu, entre quatro desenhos animados lado a lado, **o tijolo que gira**: uma
peça de montar numa mesa giratória. A marcação mora em
`templates/forum/_mascote.html` e a animação inteira em `static/forum.css`.

Três coisas podem apagar isto sem ninguém perceber, e cada uma tem um guarda
abaixo:

1. o `{% include %}` sumir de uma das duas caixas (abrir conversa · responder)
   numa edição futura — o mascote é enfeite, e enfeite é o que cai primeiro
   quando alguém reescreve o bloco do formulário;
2. o desenho ESCAPAR do `{% if pode_escrever %}` e ficar boiando na tela de
   quem não pode escrever, ao lado do recado que explica a recusa — é o modo de
   falha típico de mover um bloco de lugar;
3. a folha de estilo perder a volta, a profundidade ou o
   `prefers-reduced-motion` que desliga tudo, e o mascote virar um quadrado
   parado, sem que teste nenhum caia.

O guarda 3 é o que mais importa deste arquivo, e ele mede TRÊS coisas porque são
três as maneiras de o tijolo deixar de ser um tijolo: sem `@keyframes` ele não
gira; sem `preserve-3d` as seis faces empilham chapadas e a volta vira origami;
sem `perspective` ele gira sem nada se aproximar do olho. Qualquer uma das três
sozinha já devolve um quadrado — e um quadrado passa em qualquer teste que só
procure a marcação.
"""

from __future__ import annotations

import httpx
import pytest
from django.urls import reverse

from apps.forum.models import Area, Mensagem, Pessoa, Topico

pytestmark = pytest.mark.django_db

COOKIE = "meshcraft_sessao=um-cookie-opaco-qualquer"

SESSAO_DA_ANA = {
    "autenticado": True,
    "id": "p_ana",
    "email": "ana@exemplo.com",
    "nome_exibido": "Ana",
}

# O que prova que o mascote CHEGOU: a moldura do desenho e uma peça de dentro
# dele. Só `class="mascote"` ficaria verde com um `<svg>` vazio.
MOLDURA = 'class="mascote"'
PECA = 'class="mascote-cubo"'


@pytest.fixture
def env(monkeypatch):
    """O env mínimo dos dois clientes. Sem ele, tudo fecha — e isso é correto."""
    for nome, valor in [
        ("IDENTIDADE_API_URL", "http://identidade:8000/interno"),
        ("IDENTIDADE_API_TOKEN", "tok-id"),
        ("ALUNOS_API_URL", "http://alunos:8000/api/alunos"),
        ("ALUNOS_API_TOKEN", "tok-al"),
        ("FORUM_PROFESSORES", ""),
        ("ADMIN_EMAILS", ""),
    ]:
        monkeypatch.setenv(nome, valor)


def dublar(monkeypatch, *, sessao, categoria=None):
    """A rede das duas células vizinhas, dublada por URL — o padrão de
    `test_escrever.py`. A suíte desta célula não fala com ninguém."""

    def falso_get(self, url, **kwargs):
        endereco = str(url)
        if "identidade" in endereco:
            return httpx.Response(200, json=sessao)
        if categoria is None:
            raise AssertionError(f"chamada inesperada à alunos: {endereco}")
        return httpx.Response(200, json={"categoria": categoria})

    monkeypatch.setattr(httpx.Client, "get", falso_get)


@pytest.fixture
def sala():
    """A área onde o aluno escreve: trancada para o mundo, aberta para a turma."""
    return Area.objects.create(
        slug="duvidas",
        nome="Dúvidas gerais",
        visibilidade=Area.Visibilidade.ALUNOS,
        quem_escreve=Area.QuemEscreve.ALUNO,
    )


@pytest.fixture
def avisos():
    """A única forma legal de área pública: quem publica é a escola."""
    return Area.objects.create(
        slug="avisos",
        nome="Avisos da escola",
        visibilidade=Area.Visibilidade.PUBLICA,
        quem_escreve=Area.QuemEscreve.EQUIPE,
    )


def conversa(area) -> Topico:
    autor = Pessoa.objects.create(
        id_da_plataforma="p_prof", email="prof@exemplo.com", nome_exibido="Professor"
    )
    topico = Topico.objects.create(area=area, autor=autor, titulo="Uma conversa")
    Mensagem.objects.create(topico=topico, autor=autor, texto="a primeira fala")
    return topico


def pagina(client, endereco: str) -> str:
    resposta = client.get(endereco, headers={"cookie": COOKIE})
    assert resposta.status_code == 200, resposta.status_code
    return resposta.content.decode()


# ---------------------------------------------------------------------------
# 1. Ele está nas DUAS caixas em que o aluno cria alguma coisa
# ---------------------------------------------------------------------------


def test_a_caixa_de_abrir_conversa_chega_com_o_mascote(client, env, monkeypatch, sala):
    dublar(monkeypatch, sessao=SESSAO_DA_ANA, categoria="aluno")

    corpo = pagina(client, reverse("area", args=[sala.slug]))

    assert "Abrir uma conversa" in corpo
    assert MOLDURA in corpo, "o formulário de abrir conversa veio sem o mascote"
    assert PECA in corpo, "a caixa do mascote chegou vazia"


def test_a_caixa_de_responder_tambem_chega_com_o_mascote(
    client, env, monkeypatch, sala
):
    """As duas caixas usam o MESMO pedaço; este guarda é o que impede que uma
    delas fique para trás no dia em que o desenho mudar."""
    dublar(monkeypatch, sessao=SESSAO_DA_ANA, categoria="aluno")
    topico = conversa(sala)

    corpo = pagina(client, reverse("topico", args=[topico.pk]))

    assert "Responder" in corpo
    assert MOLDURA in corpo, "a caixa de responder veio sem o mascote"
    assert PECA in corpo


# ---------------------------------------------------------------------------
# 2. Sem formulário, sem mascote
# ---------------------------------------------------------------------------


def test_quem_nao_pode_escrever_nao_ve_o_mascote(client, env, monkeypatch, avisos):
    """O desenho pertence ao formulário, não à página.

    Numa área em que quem publica é a escola, o visitante lê o recado que
    explica a recusa — e um bloquinho animado ao lado dele seria um convite
    para clicar em nada.
    """
    dublar(monkeypatch, sessao={"autenticado": False})

    corpo = pagina(client, reverse("area", args=[avisos.slug]))

    assert "Entre para escrever aqui." in corpo, "o recado de recusa sumiu"
    assert MOLDURA not in corpo, "o mascote escapou do `{% if pode_escrever %}`"


# ---------------------------------------------------------------------------
# 3. O que faz dele ANIMADO chega junto
# ---------------------------------------------------------------------------


def test_a_folha_traz_a_volta_a_profundidade_e_o_botao_de_desligar(client):
    """As três pernas do tijolo, e o botão de desligar.

    Sem estas regras o mascote é um quadrado parado — e o pedido era um ícone
    ANIMADO e 3D. O `prefers-reduced-motion` entra no mesmo guarda de
    propósito: movimento que não se pode desligar é acessibilidade quebrada, e
    some tão silenciosamente quanto a animação.
    """
    resposta = client.get(reverse("estatico", args=["forum.css"]))
    assert resposta.status_code == 200
    if resposta.streaming:
        folha = b"".join(resposta.streaming_content).decode()
    else:
        folha = resposta.content.decode()

    assert "@keyframes mascote-gira" in folha, "a volta do tijolo sumiu da folha"
    assert "preserve-3d" in folha, (
        "sem `transform-style: preserve-3d` as seis faces empilham chapadas: o "
        "cubo deixa de ser cubo e a volta vira origami"
    )
    assert "perspective" in folha, (
        "sem `perspective` o tijolo gira sem nada se aproximar do olho — é a "
        "diferença entre girar e escorregar"
    )
    assert "prefers-reduced-motion" in folha, (
        "a folha perdeu o desligamento de movimento — quem sente enjoo com "
        "animação na tela pede isso ao sistema uma vez, e o site tem de obedecer"
    )
    assert ".escrever:focus-within .mascote-cubo { animation-duration" in folha, (
        "sumiu a regra que faz o tijolo ACELERAR quando a pessoa põe o cursor "
        "num campo. A asserção carrega o `animation-duration` de propósito: o "
        "mesmo seletor reaparece no bloco de `prefers-reduced-motion`, e sem "
        "esta metade o guarda ficaria verde com a aceleração apagada"
    )
    assert ".escrever:focus-within .mascote { filter" in folha, (
        "sumiu a regra que faz o tijolo ACENDER — a borda de luz do objeto "
        "selecionado"
    )
