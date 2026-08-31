"""O rodapé do site: em toda página, no idioma da pessoa, e diferente onde
o mantenedor pediu que fosse diferente.

Pedido dele em 31/08/2026, em três exigências. Cada uma tem guarda aqui, e cada
guarda corresponde a uma forma diferente de a entrega dar errado:

1. **"em todas as páginas"** — o guarda que varre o urlconf inteiro. Sem ele, a
   frase valeria no dia da entrega e deixaria de valer na primeira página nova,
   em silêncio: é a Classe do mapa velho, e é o modo de falha mais provável
   desta parte do site.
2. **"em algumas não tenha, em outras seja diferente"** — os guardas de
   variante. Eles afirmam sobre o CORPO RENDERIZADO, e não sobre a tabela de
   regras: uma tabela certa com um template que ignora a decisão passaria num
   teste que só lê a tabela (`armadilhas/087`).
3. **os domínios monolíngues seguem intocados** — o rodapé nasce do catálogo de
   tradução, que eles não têm. O golden byte a byte da fase 1 do i18n guarda a
   saída deles; aqui guardamos o motivo, dizendo em voz alta que não há rodapé.
"""

import pytest
from django.urls import get_resolver

from apps.core import rodape as regras
from tests.conftest import HOST_A, HOST_MESH, caminho_mesh

IDIOMAS = ("en", "pt-br", "es")

# As páginas desta célula, e o que cada uma deve mostrar. Escrita à mão de
# propósito: é a decisão do mantenedor, e o guarda de varredura logo abaixo é
# que impede a lista de envelhecer sem ninguém ver.
PAGINAS = {
    "/": "completo",
    "/cadastro": "enxuto",
    "/login": "enxuto",
}


def _corpo(resposta) -> str:
    return resposta.content.decode("utf-8")


# ---------------------------------------------------------------------------
# 1. Em TODAS as páginas
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("caminho", sorted(PAGINAS))
@pytest.mark.parametrize("idioma", IDIOMAS)
def test_toda_pagina_do_site_tem_rodape(client, rede, caminho, idioma):
    resposta = client.get(caminho_mesh(idioma, caminho), HTTP_HOST=HOST_MESH)
    assert resposta.status_code == 200
    assert '<footer class="rodape' in _corpo(resposta)


def test_nenhuma_rota_de_pagina_fica_sem_decisao_de_rodape():
    """A varredura que impede a frase "em todas as páginas" de envelhecer.

    Ela mede o urlconf REAL, não uma lista: rota nova que ninguém decidiu cai no
    padrão (`completo`), e rota que alguém quis sem rodapé precisa estar dita em
    `ROTAS_SEM_PAGINA` — o silêncio nunca significa "sem rodapé".
    """
    nomes = {
        padrao.name
        for padrao in get_resolver().url_patterns
        if getattr(padrao, "name", None)
    }
    assert "landing" in nomes, "a varredura não encontrou o urlconf da célula"
    sem_rodape = {nome for nome in nomes if regras.variante_da_rota(nome) is None}
    assert sem_rodape == set(regras.ROTAS_SEM_PAGINA) & nomes
    for nome in nomes - sem_rodape:
        assert regras.variante_da_rota(nome) in regras.VARIANTES


def test_rota_que_ninguem_decidiu_herda_o_padrao():
    assert regras.variante_da_rota("uma-pagina-que-nascer-amanha") == "completo"


def test_o_sitemap_nao_ganha_rodape(client, rede):
    """Rota de MÁQUINA: um rodapé dentro de um XML é lixo no arquivo."""
    resposta = client.get("/sitemap.xml", HTTP_HOST=HOST_MESH)
    assert resposta.status_code == 200
    assert "rodape" not in _corpo(resposta)


# ---------------------------------------------------------------------------
# 2. Variantes: a mesma casa, rodapés diferentes
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("caminho,variante", sorted(PAGINAS.items()))
def test_cada_pagina_mostra_a_variante_que_o_mantenedor_escolheu(
    client, rede, caminho, variante
):
    resposta = client.get(caminho_mesh("pt-br", caminho), HTTP_HOST=HOST_MESH)
    assert f'class="rodape rodape-{variante}"' in _corpo(resposta)


def test_o_rodape_completo_tem_marca_links_e_direitos(client, rede):
    corpo = _corpo(client.get("/pt-br/", HTTP_HOST=HOST_MESH))
    assert "Meshcraft Academy" in corpo
    assert "Todos os direitos reservados" in corpo
    for rotulo in ("Início", "Cadastro", "Fórum", "Documentos"):
        assert f">{rotulo}</a>" in corpo


def test_o_rodape_enxuto_perde_os_links_e_guarda_os_direitos(client, rede):
    """A prova é sobre o CORPO, não sobre a tabela: é o corpo que vaza."""
    corpo = _corpo(client.get("/pt-br/cadastro", HTTP_HOST=HOST_MESH))
    assert "Todos os direitos reservados" in corpo
    assert 'class="links"' not in corpo
    assert ">Fórum</a>" not in corpo


def test_pagina_sem_rodape_nao_desenha_footer_nenhum(client, rede, monkeypatch):
    """A terceira exigência: página que o dono não quer com rodapé.

    Nenhuma página nasce assim hoje (a decisão é dele, e ele ainda não a tomou
    página a página), então o guarda exercita o MECANISMO: com a home declarada
    sem rodapé, o rodapé some da home e continua nas outras.
    """
    monkeypatch.setitem(regras.REGRA_POR_ROTA, "landing", None)
    assert "<footer" not in _corpo(client.get("/pt-br/", HTTP_HOST=HOST_MESH))
    assert "<footer" in _corpo(client.get("/pt-br/login", HTTP_HOST=HOST_MESH))


def test_variante_none_na_tabela_significa_sem_rodape():
    assert regras.variante_da_rota("sitemap_xml") is None


# ---------------------------------------------------------------------------
# 3. Idioma e endereços
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("idioma", IDIOMAS)
def test_o_rodape_fala_o_idioma_da_pagina(client, rede, idioma):
    corpo = _corpo(client.get(caminho_mesh(idioma, "/"), HTTP_HOST=HOST_MESH))
    esperado = {
        "en": "All rights reserved",
        "pt-br": "Todos os direitos reservados",
        "es": "Todos los derechos reservados",
    }[idioma]
    assert esperado in corpo


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_link_de_dentro_leva_o_idioma_e_link_de_fora_nao(client, rede, idioma):
    """O erro mais traiçoeiro desta casa desde o D1 revisto: o link cru FUNCIONA
    no idioma padrão (a versão que se abre para conferir) e joga quem está em
    `/pt-br/` de volta para o inglês, sem erro nenhum na tela."""
    corpo = _corpo(client.get(caminho_mesh(idioma, "/"), HTTP_HOST=HOST_MESH))
    assert f'href="{caminho_mesh(idioma, "/cadastro")}"' in corpo
    # As outras células são monolíngues: prefixá-las morre 404 no gateway.
    assert 'href="/forum/"' in corpo
    assert 'href="/docs/"' in corpo


def test_o_ano_dos_direitos_vem_do_servidor(client, rede):
    from django.utils import timezone

    corpo = _corpo(client.get("/pt-br/", HTTP_HOST=HOST_MESH))
    assert f"© {timezone.localdate().year} Meshcraft Academy" in corpo


# ---------------------------------------------------------------------------
# 4. Os domínios monolíngues seguem sem rodapé, e é de propósito
# ---------------------------------------------------------------------------
def test_site_sem_idioma_nao_ganha_rodape(client, rede):
    """O texto do rodapé mora no catálogo de tradução, que estes sites não têm.
    O golden byte a byte da fase 1 prova que a saída deles não mudou; este
    guarda diz em voz alta POR QUE ela não mudou."""
    corpo = _corpo(client.get("/", HTTP_HOST=HOST_A))
    assert "<footer" not in corpo
    assert ".rodape {" not in corpo
