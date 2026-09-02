"""Guarda de armadilhas/081, quinta temporada: a faixa de roadmap sob prefixo.

`reverse()` **não lê** `settings.FORCE_SCRIPT_NAME`. Ele lê um prefixo guardado
numa variável de THREAD que o servidor de verdade preenche
(`ASGIHandler.__call__` chama `set_script_prefix`) e que os handlers de teste do
Django **não** preenchem. Cada tela nova desta célula paga isso de novo: a porta
no EVO-12a, a participação no EVO-12b, o sininho no EVO-21, o rosto no EVO-30 —
e agora a faixa, que estreia DOIS endereços de gente na tela:

1. o **botão do trilho**, que é uma âncora para a seção (`{% url 'quadro' %}` +
   `#roadmap`) e aparece em TODA página da Caixa;
2. o **link de cada marco**, que leva à sugestão daquele losango.

Escrito à mão, qualquer um dos dois renderiza `/#roadmap` ou `/sugestoes/7` — o
navegador pede `meshcraft.top/sugestoes/7`, endereço que em produção pertence ao
`funil` (catch-all na raiz), não à Caixa. Em dev os dois regimes coincidem, então
isto quebra **só em produção** e só depois do deploy.

O prefixo é de thread e o Django **não** o limpa entre testes: sem o
`clear_script_prefix()` na saída da fixture, ele vaza para quem rodar depois.
"""

import re

import pytest

from apps.core.rodape import enderecos_de_outras_celulas
from django.urls import clear_script_prefix, reverse, set_script_prefix

from apps.sugestoes.models import Sugestao

pytestmark = pytest.mark.django_db

PREFIXO = "/forms/sugestoes"

# Escrito à mão: é o endereço que o Traefik serve (DECISAO-EVO-01 §2). Um teste
# que o montasse com o mesmo `reverse()` do código passaria com o prefixo errado.
LINK_INTERNO = re.compile(r'(?:href|action)="(/[^"]*)"')
MARCO = re.compile(r'<a class="marco" href="([^"]+)"')


@pytest.fixture
def sob_prefixo(settings):
    """O env da VPS mais o que o SERVIDOR faz e o client de teste não faz."""
    settings.FORCE_SCRIPT_NAME = PREFIXO
    set_script_prefix(PREFIXO)
    yield
    clear_script_prefix()


@pytest.fixture
def quadro_com_marco(caixa):
    """Uma ideia no trilho — sem marco nenhum não há link de marco para medir.

    A ORDEM importa: entrar e publicar primeiro, ligar o prefixo depois. Ligado
    antes, o client síncrono trataria o prefixo como parte do `path_info` e as
    requisições da jornada bateriam em 404 (LICOES.md, EVO-21).
    """
    sugestao = caixa.publicar("Legendas nas aulas")
    assert caixa.mudar_status(sugestao, Sugestao.Status.PLANEJADO).status_code == 200
    return caixa.aluno, sugestao


def test_todo_link_do_quadro_com_a_faixa_leva_o_prefixo(quadro_com_marco, sob_prefixo):
    """A varredura inteira da página: nenhum endereço interno sem o prefixo.

    Vale mais que uma asserção nominal por link — o dia em que a faixa ganhar um
    endereço novo, ele entra nesta medição sem ninguém lembrar de atualizar o
    teste.
    """
    pessoa, _ = quadro_com_marco
    corpo = pessoa.client.get("/").content.decode()

    assert 'id="roadmap"' in corpo, "a faixa não foi desenhada — nada foi medido"
    internos = LINK_INTERNO.findall(corpo)
    assert internos, "o quadro não tem link interno — nada foi medido"

    de_fora = enderecos_de_outras_celulas()
    sem_prefixo = [
        link
        for link in internos
        if not link.startswith(f"{PREFIXO}/") and link not in de_fora
    ]
    assert sem_prefixo == [], (
        f"links sem o prefixo público no quadro: {sem_prefixo}. Todo endereço "
        "interno sai de {% url %}, nunca escrito à mão."
    )


def test_o_botao_do_roadmap_no_trilho_leva_o_prefixo_e_a_ancora(
    quadro_com_marco, sob_prefixo
):
    """O botão aparece em TODA página (ele vive na moldura): sem prefixo, quebra
    em todas de uma vez — como o link do sino quebraria."""
    pessoa, _ = quadro_com_marco

    for endereco in ("/", "/avisos", "/sugestoes/nova"):
        corpo = pessoa.client.get(endereco).content.decode()
        assert (
            f'href="{PREFIXO}/#roadmap"' in corpo
        ), f"o botão do roadmap saiu sem o prefixo em {endereco}"


def test_o_marco_da_faixa_leva_para_a_sugestao_com_o_prefixo(
    quadro_com_marco, sob_prefixo
):
    pessoa, sugestao = quadro_com_marco
    corpo = pessoa.client.get("/").content.decode()

    assert MARCO.findall(corpo) == [f"{PREFIXO}/sugestoes/{sugestao.id}"]


def test_o_urlconf_continua_sem_conhecer_o_prefixo(client):
    """Sem `SCRIPT_NAME`, o caminho prefixado não existe: a faixa não trouxe
    endereço novo para o urlconf — ela vive dentro do quadro, por âncora."""
    assert client.get(f"{PREFIXO}/").status_code == 404
    assert reverse("quadro") == "/"
