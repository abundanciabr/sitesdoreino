"""O rodapé da Caixa: em toda tela, e com a mesma assinatura do site.

Cópia do PADRÃO da `funil`, do `forum` e da `gamificacao` (Lei 7), inclusive nos
guardas — e os guardas são a metade que mais importa copiar. Cada um corresponde
a uma forma diferente de esta peça se perder:

1. **A frase "em todas as páginas" envelhecendo em silêncio.** A varredura do
   urlconf real é o que impede isso: tela nova da Caixa herda o rodapé, e tela
   que alguém quis SEM rodapé precisa estar dita por nome.
2. **A tabela certa e o molde ignorando a decisão.** Por isso toda asserção é
   sobre o CORPO RENDERIZADO, nunca sobre a tabela de regras (`armadilhas/087`:
   vazamento não escolhe a tag que você previu).
3. **O estilo que não chega ao navegador.** Esta célula serve o CSS por rota
   própria (`armadilhas/083`), então uma classe nova no HTML sem a regra no
   arquivo é um rodapé sem forma, e nada fica vermelho.

E um quarto, que é próprio daqui: **a Caixa é a única área ESCURA do site.**
Copiar o arquivo de estilo do fórum em vez do desenho traria um `#e4e4e7` de
tema claro para cima de um fundo `#15161c` — uma linha branca atravessando o pé
da página, sem nenhum teste ficando vermelho. Por isso há um guarda sobre as
cores saírem das variáveis desta folha.

## O pé que saiu, e por decisão de quem

Até 02/09/2026 esta célula tinha um pé próprio, de duas frases: "Caixa de
Sugestões" e "o que você pedir, a equipe lê". O mantenedor escolheu trocá-lo
pelo rodapé do site — uma assinatura só no fim de toda página, em vez de uma por
área. `test_o_pe_antigo_nao_voltou` existe para que a troca não seja desfeita por
engano num merge, e a mensagem dele diz de quem foi a decisão.
"""

from pathlib import Path

import pytest
from django.urls import get_resolver, reverse

from apps.core import rodape as regras

pytestmark = pytest.mark.django_db

FOLHA = Path(__file__).resolve().parents[1] / "static" / "sugestoes" / "caixa.css"


def _corpo(pessoa, endereco: str) -> str:
    resposta = pessoa.client.get(endereco)
    assert resposta.status_code == 200, resposta.status_code
    return resposta.content.decode()


def _css(client) -> str:
    """A folha, pedida ao SERVIDOR e não ao disco.

    A rota devolve um `FileResponse`, que NÃO tem `.content` — pedir por ele
    levanta `AttributeError` e o teste fica vermelho por instrumento, não por
    defeito (INV-CI01: não medir não é estar certo).
    """
    resposta = client.get(
        reverse("estatico", kwargs={"caminho": "sugestoes/caixa.css"})
    )
    assert resposta.status_code == 200, resposta.status_code
    if resposta.streaming:
        return b"".join(resposta.streaming_content).decode("utf-8")
    return resposta.content.decode("utf-8")


# ---------------------------------------------------------------------------
# 1. Em TODAS as telas
# ---------------------------------------------------------------------------
def test_o_quadro_tem_rodape(dentro, sugestao):
    corpo = _corpo(dentro, reverse("quadro"))
    assert '<footer class="rodape rodape-completo">' in corpo


def test_a_pagina_de_uma_ideia_tem_rodape(dentro, sugestao):
    corpo = _corpo(dentro, reverse("sugestao", args=[sugestao.id]))
    assert '<footer class="rodape' in corpo


def test_a_tela_de_escrever_uma_ideia_tem_rodape(dentro, categoria):
    assert '<footer class="rodape' in _corpo(dentro, reverse("nova_sugestao"))


def test_o_sininho_tem_rodape(dentro, quadro):
    assert '<footer class="rodape' in _corpo(dentro, reverse("avisos"))


def test_nenhuma_rota_de_pagina_fica_sem_decisao_de_rodape():
    """A varredura que impede a frase "em todas as páginas" de envelhecer.

    Mede o urlconf REAL, não uma lista escrita à mão: rota nova que ninguém
    decidiu cai no padrão, e rota sem rodapé precisa estar dita. O silêncio
    nunca significa "sem rodapé".

    A comparação é contra `rotas_declaradas_sem_rodape()`, que junta as DUAS
    listas — a de rotas de máquina e a das páginas que alguém decidiu deixar sem
    rodapé. Comparar só com a primeira ficaria vermelho por causa de uma decisão
    perfeitamente escrita (a porta da Caixa), e isso ensinaria a próxima pessoa
    a afrouxar a asserção, que é como um guarda morre.
    """
    nomes = {
        padrao.name
        for padrao in get_resolver().url_patterns
        if getattr(padrao, "name", None)
    }
    assert "quadro" in nomes, "a varredura não encontrou o urlconf da célula"
    sem_rodape = {nome for nome in nomes if regras.variante_da_rota(nome) is None}
    assert sem_rodape == regras.rotas_declaradas_sem_rodape() & nomes
    # Desde 02/09/2026 a única rota sem rodapé nesta célula é o servidor de
    # estáticos: a porta passou a mostrar o enxuto. Se esta linha ficar
    # vermelha, alguém declarou uma PÁGINA sem rodapé — e isso precisa de
    # motivo escrito, não de um `None` solto na tabela.
    assert sem_rodape == {"estatico"}
    for nome in nomes - sem_rodape:
        assert regras.variante_da_rota(nome) in regras.VARIANTES


def test_rota_que_ninguem_decidiu_herda_o_padrao():
    assert regras.variante_da_rota("uma-tela-que-nascer-amanha") == "completo"


def test_a_porta_da_caixa_tem_o_rodape_enxuto(client, porta):
    """A tela que eu tinha deixado de fora, e a correção de rumo.

    `entrar.html` não tem CSS externo, nem script, nem fonte remota, porque uma
    dependência de rede numa página de LOGIN quebra exatamente quando não
    deveria. No PR #871 eu li essa restrição e declarei a tela "sem rodapé" —
    aceitei o limite em vez de resolvê-lo.

    O PR #734, aberto em 31/08/2026 e nunca pousado, já tinha a solução: o
    rodapé vira PEÇA incluída pelos dois moldes, e o estilo dela entra embutido,
    com as cores do sistema. Este guarda é o que impede a volta atrás.

    Enxuto, e não completo: quem chega numa tela de entrar veio fazer UMA coisa,
    e uma lista de links ali é atrito (mesma escolha da `funil`).
    """
    assert regras.REGRA_POR_ROTA["entrar"] == "enxuto"
    corpo = client.get(reverse("entrar")).content.decode()
    assert '<footer class="rodape rodape-enxuto">' in corpo
    assert "Todos os direitos reservados" in corpo
    assert 'class="links"' not in corpo


def test_o_estilo_do_rodape_da_porta_e_embutido(client, porta):
    """Marcação sem regra é rodapé sem forma, e nada ficaria vermelho.

    Esta tela NÃO carrega o `caixa.css` — de propósito. Se as regras `.rodape`
    só existissem lá, a porta mostraria um rodapé sem borda, sem espaçamento e
    com o tamanho de fonte do corpo, e todo guarda de renderização passaria.
    """
    corpo = client.get(reverse("entrar")).content.decode()
    # A MARCAÇÃO, e não o nome do arquivo: `caixa.css` aparece nesta página
    # dentro de um COMENTÁRIO de CSS, que explica justamente por que a folha não
    # é carregada aqui. Procurar a string solta é a `armadilhas/247` — o guarda
    # ficaria vermelho por ler a explicação como se fosse a coisa explicada.
    assert '<link rel="stylesheet"' not in corpo, (
        "a porta passou a carregar folha de estilo externa — se isso foi de "
        "propósito, este guarda precisa mudar junto; se não, é a dependência de "
        "rede que a tela recusa por desenho."
    )
    assert ".rodape {" in corpo
    assert ".rodape .direitos" in corpo or ".rodape p {" in corpo


def test_todo_molde_de_pagina_inteira_inclui_a_peca_do_rodape():
    """O guarda que mede ARQUIVOS, e não telas — desenho do PR #734.

    Esta célula tem DOIS moldes de página inteira: a moldura comum e a porta.
    Um teste de tela por molde cobre os que existem hoje; molde standalone NOVO
    é justamente o caso em que ninguém lembra de escrever o teste dele, e a peça
    some de uma página sem nada ficar vermelho (`armadilhas/242`).

    A marca é o `<!doctype`, e não a tag de abertura de HTML: a própria peça
    CITA essa tag num comentário e seria acusada de não incluir a si mesma.
    """
    pasta = Path(__file__).resolve().parents[1] / "apps/core/templates/sugestoes"
    moldes = [
        arquivo
        for arquivo in sorted(pasta.glob("*.html"))
        if "<!doctype" in arquivo.read_text(encoding="utf-8").lower()
    ]
    assert len(moldes) >= 2, (
        f"esperava pelo menos os DOIS moldes de página inteira desta célula e "
        f"achei {[m.name for m in moldes]} — isto é falha de medição, não "
        f"notícia boa ([INV-CI01])."
    )
    sem_a_peca = [
        molde.name
        for molde in moldes
        if "sugestoes/_rodape.html" not in molde.read_text(encoding="utf-8")
    ]
    assert not sem_a_peca, (
        f"estes moldes de página inteira não incluem a peça do rodapé: "
        f"{sem_a_peca}.\nTodo molde desta célula inclui "
        f'`{{% include "sugestoes/_rodape.html" %}}` dentro de `{{% if rodape %}}` '
        f"— é a peça que faz o rodapé aparecer em TODAS as telas, e não só nas "
        f"que alguém lembrou."
    )


def test_o_servidor_de_estaticos_nao_ganha_rodape(client, rf):
    """Rota de MÁQUINA: um rodapé dentro do arquivo CSS seria lixo no arquivo, e
    o navegador o serviria como estilo.

    **A prova é um PAR**, e não uma afirmação de ausência sobre um `.css` que
    não teria `<footer>` de jeito nenhum (`armadilhas/266`): a rota de máquina
    devolve `{}`, a rota de página devolve o rodapé. Arranque `ROTAS_SEM_PAGINA`
    e a primeira cai; arranque `rodape_do_contexto` e cai a segunda.
    """

    class Casamento:
        def __init__(self, nome):
            self.url_name = nome

    def requisicao_de(nome):
        pedido = rf.get("/")
        pedido.resolver_match = Casamento(nome)
        return pedido

    assert regras.rodape_do_contexto(requisicao_de("estatico")) == {}
    assert "rodape" in regras.rodape_do_contexto(requisicao_de("quadro"))
    assert "<footer" not in _css(client)


# ---------------------------------------------------------------------------
# 2. O que o rodapé completo mostra, e a variante que o painel vai oferecer
# ---------------------------------------------------------------------------
def test_o_rodape_completo_tem_marca_links_e_direitos(dentro, sugestao):
    corpo = _corpo(dentro, reverse("quadro"))
    assert "Meshcraft Academy" in corpo
    assert "Todos os direitos reservados" in corpo
    for rotulo in ("Início do site", "Caixa de Sugestões", "Documentos"):
        assert f">{rotulo}</a>" in corpo
    assert 'href="/docs/"' in corpo


def test_o_rodape_enxuto_perde_os_links_e_guarda_os_direitos(
    dentro, sugestao, monkeypatch
):
    """A variante que ainda não tem uso, exercitada mesmo assim: é ela que o
    painel vai oferecer, e variante que só nasce no dia do pedido nasce sem
    teste. A prova é sobre o CORPO, não sobre a tabela."""
    monkeypatch.setitem(regras.REGRA_POR_ROTA, "quadro", "enxuto")
    corpo = _corpo(dentro, reverse("quadro"))
    assert '<footer class="rodape rodape-enxuto">' in corpo
    assert "Todos os direitos reservados" in corpo
    assert 'class="links"' not in corpo
    assert "Meshcraft Academy</p>" not in corpo


def test_pagina_declarada_sem_rodape_nao_desenha_footer_nenhum(
    dentro, sugestao, monkeypatch
):
    monkeypatch.setitem(regras.REGRA_POR_ROTA, "quadro", None)
    assert "<footer" not in _corpo(dentro, reverse("quadro"))
    assert "<footer" in _corpo(dentro, reverse("avisos"))


def test_o_ano_dos_direitos_vem_do_servidor(dentro, sugestao):
    from django.utils import timezone

    corpo = _corpo(dentro, reverse("quadro"))
    assert f"© {timezone.localdate().year} Meshcraft Academy" in corpo


# ---------------------------------------------------------------------------
# 3. O estilo chega ao navegador, e com as cores DESTA área
# ---------------------------------------------------------------------------
def test_o_estilo_do_rodape_chega_pela_rota_do_css(client):
    """Classe no HTML sem regra no CSS é rodapé sem forma, e nada fica vermelho.
    Esta célula serve o estilo por rota própria (`armadilhas/083`), então a
    prova pergunta ao SERVIDOR, não ao disco."""
    css = _css(client)
    for regra in (".rodape {", ".rodape .marca", ".rodape .links", ".rodape .direitos"):
        assert regra in css


def test_as_cores_do_rodape_saem_das_variaveis_desta_folha():
    """A Caixa é a única área ESCURA do site.

    Uma cor de tema claro copiada do fórum (`#e4e4e7` na borda, `#52525b` no
    texto) atravessaria o pé da página com uma linha branca sobre fundo
    `#15161c` — e nenhum teste de renderização veria isso. Este guarda lê o
    bloco do rodapé e exige que ele não traga cor crua nenhuma.
    """
    folha = FOLHA.read_text(encoding="utf-8")
    inicio = folha.index(".rodape {")
    bloco = folha[inicio : folha.index(".rodape .direitos", inicio)]
    assert "#" not in bloco, (
        f"o bloco do rodapé traz cor crua: {bloco!r}. Nesta folha a cor sai das "
        f"variáveis (`--linha`, `--texto`, `--texto-tenue`, `--laranja`) — a "
        f"Caixa é escura, e um hexadecimal de tema claro passa despercebido por "
        f"todo guarda de renderização."
    )
    assert "var(--" in bloco


# ---------------------------------------------------------------------------
# 4. O pé antigo não volta por engano
# ---------------------------------------------------------------------------
def test_o_pe_antigo_nao_voltou(dentro, sugestao):
    """A troca foi ESCOLHA do mantenedor em 02/09/2026, não descuido.

    Ele viu as duas opções — trocar pelo rodapé do site, ou manter o pé pequeno
    e pôr o do site embaixo — e escolheu trocar: uma assinatura só no fim de
    toda página, em vez de uma por área. Se este guarda ficar vermelho, alguém
    trouxe o pé antigo de volta num merge, e a pergunta certa é para ele, não
    para o código.
    """
    corpo = _corpo(dentro, reverse("quadro"))
    assert 'class="pe"' not in corpo
    assert "o que você pedir, a equipe lê" not in corpo
