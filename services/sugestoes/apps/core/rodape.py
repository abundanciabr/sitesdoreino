# apps/core/rodape.py
"""O rodapé da casa, dentro da Caixa: quem mostra, qual dos rodapés, e o que
cada um leva.

**Cópia do PADRÃO das células `funil` e `forum`, nunca do arquivo delas**
(Lei 7). O rodapé da casa nasceu no site em 31/08/2026 (PR #705) e foi para o
fórum no mesmo dia (PR #711); o mantenedor reparou, olhando o site, que a Caixa
tinha ficado de fora. A lição transversal do desenho está em `armadilhas/242`.

**O que este arquivo APOSENTA.** A Caixa já tinha um pé próprio,
`<footer class="pe">`, anterior ao rodapé da casa e diferente dele: duas
colunas em fonte mono dizendo "Caixa de Sugestões" e "o que você pedir, a
equipe lê". Ele sai, e o da casa entra no lugar. Empilhar os dois seria dois
rodapés na mesma tela, e manter só o antigo é justamente o que o mantenedor
apontou como errado: a Caixa é parte do site, e parecia outro lugar.

**A variante `enxuto` vale nas telas em que a pessoa veio fazer UMA coisa** —
entrar e escrever uma ideia. É a mesma régua que o site já usa no cadastro e no
login, aprovada pelo mantenedor em 31/08/2026: ali uma lista de links é convite
para sair no meio do caminho.
"""

from django.utils import timezone

BLOCOS = frozenset({"assinatura", "links", "direitos"})

VARIANTES = {
    "completo": frozenset({"assinatura", "links", "direitos"}),
    "enxuto": frozenset({"direitos"}),
}

VARIANTE_PADRAO = "completo"

# Nome da rota (o `name=` do `config/urls.py`) → a variante que ela mostra, ou
# `None` para "esta tela não tem rodapé". Rota que não está aqui usa o padrão,
# inclusive rota que nascer amanhã.
REGRA_POR_ROTA: "dict[str, str | None]" = {
    "entrar": "enxuto",
    "nova_sugestao": "enxuto",
}

# Rotas de MÁQUINA: não são telas. Um rodapé dentro de um arquivo CSS seria
# lixo no arquivo, e o navegador o serviria como estilo.
ROTAS_SEM_PAGINA = frozenset({"estatico"})

# Os endereços das OUTRAS partes do site. Crus, porque cada célula é dona do
# próprio prefixo e a Caixa não monta endereço de ninguém: se um deles mudar de
# casa, a mudança do lado da Caixa é esta linha.
URL_DO_SITE = "/"
URL_DO_FORUM = "/forum/"
URL_DOS_DOCUMENTOS = "/docs/"


def variante_da_rota(nome_da_rota: "str | None") -> "str | None":
    """Qual rodapé esta rota mostra — `None` quando não mostra nenhum."""
    if nome_da_rota in ROTAS_SEM_PAGINA:
        return None
    if nome_da_rota in REGRA_POR_ROTA:
        return REGRA_POR_ROTA[nome_da_rota]
    return VARIANTE_PADRAO


def montar(variante: str, *, ano: int) -> dict:
    """O dicionário que o molde consome — a costura para a tela do painel."""
    blocos = VARIANTES[variante]
    return {
        "variante": variante,
        "mostra_assinatura": "assinatura" in blocos,
        "mostra_links": "links" in blocos,
        "mostra_direitos": "direitos" in blocos,
        "ano": ano,
        "url_do_site": URL_DO_SITE,
        "url_do_forum": URL_DO_FORUM,
        "url_dos_documentos": URL_DOS_DOCUMENTOS,
    }


def rodape(request) -> dict:
    """Processador de contexto: põe `rodape` em TODA tela desta célula.

    É processador, e não `{% include %}` escrito em cada molde, pelo mesmo
    motivo que o sininho desta mesma célula é (`apps/core/avisos.py`): um
    combinado desses é esquecido pela primeira view escrita depois.
    """
    resolvida = getattr(request, "resolver_match", None)
    variante = variante_da_rota(resolvida.url_name if resolvida else None)
    if variante is None:
        return {}
    return {"rodape": montar(variante, ano=timezone.localdate().year)}
