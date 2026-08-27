"""O middleware `BarraNoFinal` no funil — e, principalmente, o que ele NÃO toca.

O sintoma foi medido em produção pelo mantenedor em 27/08/2026, na Caixa: o
mesmo endereço responde sem a barra no fim e devolve `Not Found` com ela. O
conserto entrou primeiro na `sugestoes` (PR #284); aqui ele chega à célula que
serve as páginas públicas do site.

**Esta célula tem uma complicação que a `sugestoes` não tinha: o idioma.** O
`SiteResolutionMiddleware` decapa o prefixo (`/pt-br`, `/es`) de `path_info`
antes do urlconf, e o D1 revisto (25/08/2026) pôs o idioma PADRÃO na raiz nua —
não existe `/<padrão>/`. Metade deste arquivo existe para provar que a regra da
barra não encosta na matriz do `PLANO-I18N`.

Os caminhos com idioma saem de `caminho_mesh()`, nunca escritos à mão: escrever
`f"/{idioma}{caminho}"` faria o caso do idioma padrão bater num 404 e o teste
"passaria" medindo outra coisa (é o aviso que o próprio `conftest.py` dá).
"""

# Sem  em lugar nenhum, e isso é da célula: o funil tem
#  (ele não guarda nada — manda os leads para a célula ).
# Pedir banco aqui faz o teardown do pytest-django estourar com
# "settings.DATABASES is improperly configured", num erro que parece de ambiente
# e é de marcador.
import pytest
from django.test import Client

from tests.conftest import HOST_MESH, SITE_MESH, caminho_mesh

PADRAO = SITE_MESH["default_language"]
PREFIXADOS = [
    idioma["code"] for idioma in SITE_MESH["languages"] if idioma["code"] != PADRAO
]


@pytest.fixture
def cliente():
    return Client()


def pegar(cliente, caminho, **extra):
    return cliente.get(caminho, HTTP_HOST=HOST_MESH, **extra)


# ---------------------------------------------------------------------------
# O que ele conserta
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("nu", ["/cadastro", "/login"])
def test_barra_no_final_leva_a_rota_nua(cliente, rede, nu):
    resposta = pegar(cliente, f"{nu}/")
    assert resposta.status_code == 302, f"{nu}/ devia redirecionar"
    assert resposta["Location"] == nu


def test_a_query_sobrevive_ao_redirecionamento(cliente, rede):
    """Perder o `?utm_source=…` aqui não é detalhe: esta é a célula de
    AQUISIÇÃO, e a origem da visita é o dado que paga o anúncio."""
    resposta = pegar(cliente, "/cadastro/?utm_source=instagram&utm_campaign=agosto")
    assert resposta.status_code == 302
    destino, _, query = resposta["Location"].partition("?")
    assert destino == "/cadastro"
    assert "utm_source=instagram" in query and "utm_campaign=agosto" in query


def test_e_302_e_nunca_301(cliente, rede):
    """301 fica cacheado no navegador quase para sempre: se `/cadastro/` ganhar
    rota própria amanhã, quem já visitou nunca mais a alcança."""
    assert pegar(cliente, "/cadastro/").status_code == 302


def test_barra_dupla_no_final_tambem_resolve(cliente, rede):
    """`//` no fim vem de concatenação de link mal feita e é indistinguível de
    uma barra para quem digitou."""
    resposta = pegar(cliente, "/cadastro//")
    assert resposta.status_code == 302
    assert resposta["Location"] == "/cadastro"


# ---------------------------------------------------------------------------
# O idioma — a metade que a `sugestoes` não precisou provar
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("idioma", PREFIXADOS)
def test_o_conserto_preserva_o_prefixo_de_idioma(cliente, rede, idioma):
    """`/es/cadastro/` tem de cair em `/es/cadastro`, e não em `/cadastro`.

    É o caso que justifica a ordem do middleware na lista: ele resolve contra
    `path_info` (já sem o idioma, que é o que o urlconf entende) e redireciona
    para `request.path` (com o idioma, que é o que o navegador precisa).
    """
    nu = caminho_mesh(idioma, "/cadastro")
    resposta = pegar(cliente, f"{nu}/")

    assert resposta.status_code == 302
    assert resposta["Location"] == nu
    assert resposta["Location"].startswith(f"/{idioma}/"), (
        "o redirecionamento perdeu o idioma — a pessoa foi jogada para outra "
        "língua sem pedir"
    )


@pytest.mark.parametrize("idioma", PREFIXADOS)
def test_a_raiz_de_um_idioma_nao_e_tocada(cliente, rede, idioma):
    """A forma canônica de um prefixo de idioma é COM barra (`/es/`), e ela
    resolve — então a regra 1 barra o middleware antes de qualquer coisa. Se
    ele agisse aqui, `/es/` viraria `/es`, que é justamente o redirecionamento
    contrário ao da matriz do D1."""
    resposta = pegar(cliente, caminho_mesh(idioma, "/"))
    assert resposta.status_code == 200


def test_o_idioma_padrao_nao_ganha_um_prefixo_inventado(cliente, rede):
    """O D1 revisto pôs o idioma PADRÃO na raiz nua: `/<padrão>/` não existe, e
    o middleware não pode dar existência a ele.

    Sem este guarda, um dia alguém "conserta" o 404 de `/en/cadastro/` e volta a
    servir o mesmo conteúdo em dois endereços — que é exatamente a duplicação
    que o D1 foi revisto para eliminar.
    """
    for caminho in (f"/{PADRAO}", f"/{PADRAO}/", f"/{PADRAO}/cadastro/"):
        assert pegar(cliente, caminho).status_code == 404, (
            f"{caminho} deixou de ser 404: o idioma padrão ganhou um prefixo, e "
            "agora a mesma página vive em dois endereços"
        )


# ---------------------------------------------------------------------------
# As fronteiras deliberadas
# ---------------------------------------------------------------------------


def test_a_raiz_nao_e_tocada(cliente, rede):
    """A raiz é a home e resolve. Um `rstrip("/")` ingênuo a transformaria na
    string vazia e o `Location` sairia inválido."""
    assert pegar(cliente, "/").status_code == 200


def test_caminho_que_nao_existe_nem_com_nem_sem_barra_segue_404(cliente, rede):
    """Sem isto o middleware viraria um 302 universal para qualquer typo."""
    assert pegar(cliente, "/nao-existe/").status_code == 404
    assert pegar(cliente, "/nao-existe").status_code == 404


def test_post_com_barra_nao_e_redirecionado(cliente, rede):
    """O guarda mais importante do arquivo.

    Um 302 num POST vira GET no navegador e o corpo do formulário é descartado
    **em silêncio**. `/leads` é a porta de captura desta célula: um lead
    redirecionado é um lead perdido sem nenhum sinal — nem erro, nem log, nem
    linha no banco. A matriz do `PLANO-I18N` D1 já tinha preservado
    `POST /leads` e `POST /cadastro` pela mesma razão.
    """
    for rota in ("/leads/", "/cadastro/"):
        resposta = cliente.post(rota, HTTP_HOST=HOST_MESH)
        assert resposta.status_code != 302, (
            f"POST {rota} foi redirecionado — o corpo do formulário seria "
            "descartado em silêncio e o lead sumiria"
        )


def test_rota_de_maquina_nao_ganha_uma_gemea(cliente, rede):
    """`/healthz` e `/sitemap.xml` são endereços de MÁQUINA. A `armadilhas/086`
    conta o caso de uma sonda ganhando uma gêmea sem querer. Redirecionar é
    aceitável (não cria resposta de sonda nova); o que não pode é a forma com
    barra passar a RESPONDER como a nua."""
    for rota in ("/healthz", "/sitemap.xml"):
        resposta = pegar(cliente, f"{rota}/")
        if resposta.status_code == 302:
            assert resposta["Location"] == rota
        else:
            assert resposta.status_code == 404
        assert resposta.status_code != 200, (
            f"{rota}/ respondeu como se fosse {rota} — agora a rota de máquina "
            "tem dois endereços canônicos"
        )
