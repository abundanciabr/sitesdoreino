"""A faixa de roadmap sob prefixo público: todo link interno leva o prefixo.
O prefixo é de thread e o Django não o limpa entre testes; a fixture o limpa."""

import re

import pytest

from apps.core.rodape import enderecos_de_outras_celulas
from django.urls import clear_script_prefix, reverse, set_script_prefix

from apps.sugestoes.models import Sugestao

pytestmark = pytest.mark.django_db

PREFIXO = "/forms/sugestoes"

# Escrito à mão: é o endereço que o Traefik serve.
# Montá-lo com `reverse()` passaria com o prefixo errado.
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
    """Uma ideia no trilho, para haver link de marco a medir.
    Entrar e publicar vêm antes de ligar o prefixo, que desviaria o `path_info`."""
    sugestao = caixa.publicar("Legendas nas aulas")
    assert caixa.mudar_status(sugestao, Sugestao.Status.PLANEJADO).status_code == 200
    return caixa.aluno, sugestao


def test_todo_link_do_quadro_com_a_faixa_leva_o_prefixo(quadro_com_marco, sob_prefixo):
    """Varredura da página inteira: nenhum endereço interno sem o prefixo."""
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

    for endereco in ("/", "/sugestoes/nova"):
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
