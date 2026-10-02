"""O rosto da Caixa, medido pela borda HTTP: o HTML recebido e o efeito no banco.
O voto sai do `action` da página e o CSS é medido sob `SCRIPT_NAME`."""

import re

import pytest
from asgiref.sync import async_to_sync
from django.test import AsyncClient
from django.urls import clear_script_prefix, reverse, set_script_prefix

from apps.sugestoes.models import Sugestao, Voto

pytestmark = pytest.mark.django_db

PREFIXO = "/forms/sugestoes"

# Como o voto chega ao navegador: dois padrões, pois a página tem outros formulários.
ACAO_DO_VOTO = re.compile(r'action="([^"]*/(?:des)?votar)"')
ROTULO_DO_VOTO = re.compile(r'class="voto[^"]*"\s+title="([^"]*)"')
CONTAGEM = re.compile(r'<span class="votos">(\d+)</span>')
TITULO_DE_PECA = re.compile(r'<h3 class="peca-titulo"><a href="[^"]*">([^<]+)</a>')

# A aba como chega ao navegador: a chave na URL, se está acesa e o rótulo.
ABA = re.compile(r'\?ordem=([a-z-]+)"\s+class="([^"]*)">([^<]+)</a>')


def _abas(corpo: str) -> str:
    """Só a fila de abas — o `.ativo` dos filtros de categoria mora ao lado."""
    return corpo.split('<div class="abas">', 1)[1].split("</div>", 1)[0]


def _quadro(pessoa, **query) -> str:
    endereco = reverse("quadro")
    if query:
        endereco += "?" + "&".join(f"{c}={v}" for c, v in query.items())
    resposta = pessoa.client.get(endereco)
    assert resposta.status_code == 200, resposta.status_code
    return resposta.content.decode()


# O quadro: a grade, as abas e o que não está aqui


def test_o_quadro_abre_para_o_aluno_logado_e_desenha_a_grade(caixa):
    caixa.publicar("Legendas nas aulas")

    corpo = _quadro(caixa.aluno)

    assert 'class="grade"' in corpo, "o quadro não desenhou a grade de peças"
    assert TITULO_DE_PECA.findall(corpo) == ["Legendas nas aulas"]
    # A folha de estilo é do rosto: sem ela a grade vira uma lista de texto.
    assert 'rel="stylesheet"' in corpo


def test_as_abas_sao_quatro_e_a_acesa_continua_sendo_mais_votadas(caixa):
    """As quatro abas, na ordem do protótipo, com "Mais votadas" acesa por padrão."""
    corpo = _quadro(caixa.aluno)

    assert ABA.findall(_abas(corpo)) == [
        ("em-alta", "", "Em alta"),
        ("mais-votadas", "ativo", "Mais votadas"),
        ("novas", "", "Novas"),
        ("implementadas", "", "Implementadas"),
    ]


def test_a_aba_novas_ordena_pela_chegada_e_a_padrao_pelos_votos(caixa, entrar_como):
    """As duas abas mostram as MESMAS sugestões em ordens diferentes."""
    primeira = caixa.publicar("Chegou primeiro")
    caixa.publicar("Chegou depois")
    quem_vota = entrar_como("votante@exemplo.test", "Votante")
    assert caixa.votar(primeira, quem=quem_vota).status_code == 302

    mais_votadas = TITULO_DE_PECA.findall(_quadro(caixa.aluno))
    novas = TITULO_DE_PECA.findall(_quadro(caixa.aluno, ordem="novas"))

    assert mais_votadas == ["Chegou primeiro", "Chegou depois"]
    assert novas == ["Chegou depois", "Chegou primeiro"]


def test_uma_aba_inventada_para_a_pagina_em_vez_de_escolher_por_conta(caixa):
    """Aba inexistente dá 404: servir a ordem padrão faria a aba mentir."""
    assert (
        caixa.aluno.client.get(f"{reverse('quadro')}?ordem=quentinhas").status_code
        == 404
    )


def test_a_aba_carrega_o_filtro_e_o_filtro_carrega_a_aba(caixa):
    """Trocar de aba não pode apagar a categoria escolhida, nem o contrário —
    senão cada clique desfaz metade da escolha anterior."""
    caixa.publicar("Legendas nas aulas")

    corpo = _quadro(caixa.aluno, ordem="novas", categoria="curso")

    assert f'href="{reverse("quadro")}?ordem=novas&amp;categoria=curso"' in corpo
    assert f'href="{reverse("quadro")}?ordem=mais-votadas&amp;categoria=curso"' in corpo


# O voto, clicando no que está na tela


def _clicar_no_voto(pessoa, corpo: str):
    """Segue o `action` do formulário que a página realmente entregou."""
    enderecos = ACAO_DO_VOTO.findall(corpo)
    rotulos = ROTULO_DO_VOTO.findall(corpo)
    assert enderecos and rotulos, "a página não trouxe nenhum botão de voto"
    endereco, rotulo = enderecos[0], rotulos[0]
    resposta = pessoa.client.post(endereco, {"de": "quadro"})
    assert resposta.status_code == 302, resposta.status_code
    return rotulo


def test_votar_e_desvotar_pela_tela_mudam_a_contagem_que_a_pessoa_ve(caixa):
    sugestao = caixa.publicar("Legendas nas aulas")

    antes = _quadro(caixa.aluno)
    assert CONTAGEM.findall(antes) == ["0"]
    assert _clicar_no_voto(caixa.aluno, antes) == "Votar"

    depois = _quadro(caixa.aluno)
    assert CONTAGEM.findall(depois) == ["1"]
    assert Voto.objects.filter(sugestao=sugestao).count() == 1
    assert _clicar_no_voto(caixa.aluno, depois) == "Tirar meu voto"

    de_volta = _quadro(caixa.aluno)
    assert CONTAGEM.findall(de_volta) == ["0"]
    assert Voto.objects.filter(sugestao=sugestao).count() == 0


# O detalhe: a conversa e a história da ideia


def test_a_pagina_da_sugestao_conta_por_onde_a_ideia_andou(caixa):
    sugestao = caixa.publicar("Legendas nas aulas")
    assert (
        caixa.mudar_status(
            sugestao, Sugestao.Status.PLANEJADO, nota="Entra no ciclo de setembro."
        ).status_code
        == 200
    )

    corpo = caixa.aluno.client.get(
        reverse("sugestao", args=[sugestao.id])
    ).content.decode()

    assert 'class="etapas"' in corpo, "a linha do tempo não foi desenhada"
    assert "Em desenvolvimento" in corpo  # a etapa existe mesmo sem ter chegado nela
    assert "Entra no ciclo de setembro." in corpo


def test_a_historia_mostra_a_decisao_e_nunca_quem_decidiu(caixa):
    """A história mostra a decisão e a nota, nunca a `Identidade` de quem decidiu."""
    sugestao = caixa.publicar("Legendas nas aulas")
    caixa.mudar_status(sugestao, Sugestao.Status.PLANEJADO, nota="Vale a pena.")

    corpo = caixa.aluno.client.get(
        reverse("sugestao", args=[sugestao.id])
    ).content.decode()

    assert "Vale a pena." in corpo
    assert "equipe@meshcraft.test" not in corpo
    assert "meshcraft.test" not in corpo


def test_o_comentario_escrito_aparece_na_conversa(caixa):
    sugestao = caixa.publicar("Legendas nas aulas")
    caixa.aluno.client.post(
        reverse("comentar", args=[sugestao.id]), {"texto": "Assisto no ônibus."}
    )

    corpo = caixa.aluno.client.get(
        reverse("sugestao", args=[sugestao.id])
    ).content.decode()

    assert 'class="conversa"' in corpo
    assert "Assisto no ônibus." in corpo


# Nova ideia: a busca de duplicata na frente


def test_o_formulario_confere_antes_de_publicar_e_a_conferencia_nao_cria_nada(caixa):
    caixa.publicar("Legendas nas aulas gravadas")

    vazio = caixa.aluno.client.get(reverse("nova_sugestao")).content.decode()
    assert "Conferir se já existe" in vazio
    assert "Publicar assim mesmo" not in vazio, (
        "o botão de publicar apareceu antes da conferência — a busca de "
        "duplicata deixou de estar na frente"
    )

    conferencia = caixa.aluno.client.post(
        reverse("nova_sugestao"),
        {
            "titulo": "Legendas nos vídeos",
            "problema": "Não ouço.",
            "categoria": "curso",
        },
    )
    corpo = conferencia.content.decode()

    assert conferencia.status_code == 200
    assert "Isto já foi sugerido?" in corpo
    assert "Legendas nas aulas gravadas" in corpo
    assert "Publicar assim mesmo" in corpo
    assert Sugestao.objects.count() == 1, "a conferência publicou alguma coisa"


def test_a_categoria_escolhida_sobrevive_a_conferencia(caixa):
    """O estado mora no formulário, não em JavaScript: quem volta da
    conferência não reescolhe a categoria do zero."""
    corpo = caixa.aluno.client.post(
        reverse("nova_sugestao"),
        {"titulo": "Ideia nova", "problema": "Doi assim.", "categoria": "curso"},
    ).content.decode()

    assert re.search(r'value="curso"\s+checked', corpo), corpo[-1200:]


# O rosto sob o prefixo público


@pytest.fixture
def sob_prefixo(settings):
    """O env da VPS com `SCRIPT_NAME` ligado, limpo na saída porque o prefixo é de
    thread."""
    settings.FORCE_SCRIPT_NAME = PREFIXO
    set_script_prefix(PREFIXO)
    yield
    clear_script_prefix()


def test_a_folha_de_estilo_sai_com_o_prefixo_publico(dentro, sugestao, sob_prefixo):
    """A folha de estilo sai com o prefixo público (`{% url %}`, não `{% static %}`)."""
    corpo = dentro.client.get("/").content.decode()

    assert f'href="{PREFIXO}/static/sugestoes/caixa.css"' in corpo, (
        "a folha de estilo saiu sem o prefixo público — em meshcraft.top esse "
        "endereço é do funil, não da Caixa."
    )


def test_a_borda_publica_entrega_a_folha_de_estilo(sob_prefixo):
    """O endereço da folha de estilo resolve quando chega com o prefixo, como pelo
    Traefik."""
    resposta = async_to_sync(AsyncClient().get)(
        f"{PREFIXO}/static/sugestoes/caixa.css",
        headers={"x-forwarded-proto": "https"},
    )

    assert resposta.status_code == 200, resposta.status_code
    assert b"--laranja" in b"".join(resposta.streaming_content)


def test_quem_nao_entrou_nao_alcanca_o_rosto(client, sugestao):
    """Sem sessão, nenhuma página do rosto abre: o anônimo é mandado para a porta."""
    for endereco in (
        reverse("quadro"),
        f"{reverse('quadro')}?ordem=novas",
        reverse("nova_sugestao"),
        reverse("sugestao", args=[sugestao.id]),
    ):
        resposta = client.get(endereco)
        assert resposta.status_code == 302, f"{endereco}: {resposta.status_code}"
        assert resposta["Location"] == reverse("entrar")
