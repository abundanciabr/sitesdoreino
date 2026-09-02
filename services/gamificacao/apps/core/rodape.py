# apps/core/rodape.py
"""O rodapé das Conquistas: quem mostra, qual dos rodapés, e o que cada um leva.

**Cópia do PADRÃO das células `funil` e `forum`, nunca do arquivo delas** (Lei 7
do Caminho Dourado). O rodapé do site nasceu na `funil` em 31/08/2026 (PR #705)
e chegou ao fórum no mesmo dia (PR #711). Esta célula nasceu ANTES dessa peça
existir e por isso ficou de fora — o mantenedor abriu `/conquistas/` em
02/09/2026 e viu uma página sem menu e sem rodapé, sozinha no meio do site.

Isto é a `armadilhas/242` acontecendo pelo lado que ela não previu. Ela avisa
que `{% include %}` por template deixa a peça sumir da PRIMEIRA TELA NOVA; aqui
a peça sumiu da primeira CÉLULA nova, porque nenhum portão do repositório sabia
perguntar "esta célula pública desenha o rodapé?".

O que muda em relação ao fórum, e por quê:

* **Não há catálogo de tradução.** Esta célula é monolíngue, e o texto visível
  dela mora no template, como o resto daqui. Quando o painel mandar nos textos,
  é `montar()` que passa a receber o que o dono escreveu, exatamente como nas
  outras duas.
* **O link do site sai do `settings`, e não de uma constante daqui.** Esta
  célula já lê `URL_DA_CAPA` do env (é ela que o convite ao visitante usa), e
  uma segunda resposta para "onde fica a capa do site" divergiria da primeira
  no dia em que alguém mexesse numa delas.
"""

from django.conf import settings
from django.utils import timezone

BLOCOS = frozenset({"assinatura", "links", "direitos"})

VARIANTES = {
    "completo": frozenset({"assinatura", "links", "direitos"}),
    "enxuto": frozenset({"direitos"}),
}

VARIANTE_PADRAO = "completo"

# Nome da rota (o `name=` do `config/urls.py`) → a variante que ela mostra, ou
# `None` para "esta página não tem rodapé". Rota que não está aqui usa o padrão,
# **inclusive rota que nascer amanhã** — é essa a metade que impede a frase "em
# todas as páginas" de envelhecer em silêncio (`armadilhas/242`).
REGRA_POR_ROTA: "dict[str, str | None]" = {}

# Rotas de MÁQUINA: não são páginas. O `/healthz` e a porta de máquina nem
# chegam a ter nome; o servidor de estáticos tem, e por isso precisa estar dito
# — um rodapé dentro do arquivo CSS seria lixo que o navegador serve como
# estilo.
#
# Os três GESTOS desta célula (`enviar-prova`, `decidir`, `forjar`) NÃO entram
# aqui, e a ausência é decisão: eles respondem com um redirecionamento, que não
# renderiza template nenhum, então o rodapé que este módulo oferece simplesmente
# não é usado. Declará-los "sem rodapé" seria dizer uma coisa que não se mede, e
# no dia em que um deles passasse a renderizar uma tela de recusa, a tela
# nasceria sem rodapé por causa de uma linha escrita hoje.
ROTAS_SEM_PAGINA = frozenset({"estatico"})

# A biblioteca pública é de outra célula (`admin`), e esta aqui não monta
# endereço de ninguém: se ela mudar de casa, a mudança do lado das Conquistas é
# esta linha.
URL_DOS_DOCUMENTOS = "/docs/"


def variante_da_rota(nome_da_rota: "str | None") -> "str | None":
    """Qual rodapé esta rota mostra — `None` quando não mostra nenhum."""
    if nome_da_rota in ROTAS_SEM_PAGINA:
        return None
    if nome_da_rota in REGRA_POR_ROTA:
        return REGRA_POR_ROTA[nome_da_rota]
    return VARIANTE_PADRAO


def montar(variante: str, *, ano: int) -> dict:
    """O dicionário que o template consome — a costura para o painel."""
    blocos = VARIANTES[variante]
    return {
        "variante": variante,
        "mostra_assinatura": "assinatura" in blocos,
        "mostra_links": "links" in blocos,
        "mostra_direitos": "direitos" in blocos,
        "ano": ano,
        "url_do_site": settings.URL_DA_CAPA,
        "url_dos_documentos": URL_DOS_DOCUMENTOS,
    }


def rodape_do_contexto(request) -> dict:
    """Processador de contexto: põe `rodape` em TODA página desta célula.

    É processador, e não `{% include %}` escrito em cada template, porque "em
    todas as páginas" não pode depender de alguém lembrar de incluir a peça:
    tela nova das Conquistas nasce com rodapé sozinha (`armadilhas/242`).
    """
    resolvida = getattr(request, "resolver_match", None)
    variante = variante_da_rota(resolvida.url_name if resolvida else None)
    if variante is None:
        return {}
    return {"rodape": montar(variante, ano=timezone.localdate().year)}
