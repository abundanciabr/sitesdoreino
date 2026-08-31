# apps/core/rodape.py
"""O rodapé do site: quem mostra, qual dos rodapés, e o que cada um leva.

Pedido do mantenedor em 31/08/2026, com três exigências na mesma frase: rodapé
em TODAS as páginas, textos que ele possa trocar sozinho, e páginas que mostram
um rodapé diferente (ou nenhum). Este arquivo é a peça que decide; o desenho
dela responde às três.

**Por que a decisão mora aqui, e não dentro do template.** Um `{% if %}` por
página espalhado pelos templates seria a regra escrita em quatro lugares, e
página nova nasceria sem rodapé sem ninguém perceber. Aqui a regra é UMA tabela,
o padrão vale para toda rota que não aparece nela, e o teste-guarda
(`tests/test_rodape.py`) varre o urlconf inteiro: rota nova sem decisão explícita
herda o padrão, e isso é visível.

**Por que os textos ainda saem do catálogo de tradução, e não de um banco.** A
`funil` é a única célula sem banco (é vitrine pura), então "o mantenedor edita o
texto no painel" não é uma coluna nova aqui: é a etapa 2, que precisa de um dono
do dado com API própria e passa pelo Rito de Contrato (RITOS §3). O que esta
etapa entrega é a costura pronta para ela: quem constrói o rodapé é ESTA função,
que devolve um dicionário; no dia em que o painel mandar, o dicionário vem de lá
e o template não muda uma linha. É de propósito que o template não saiba de onde
o texto veio.

**Site monolíngue não ganha rodapé nesta etapa**, e isso também é desenho: os
domínios antigos (`basileiatoutheou.org`) são comparados byte a byte pelo golden
da fase 1 do i18n, e o texto do rodapé deles não existe em catálogo nenhum. O
rodapé aparece onde há idioma resolvido, que hoje é o site da escola.
"""

from django.utils import timezone

from apps.core import enderecos

# ---------------------------------------------------------------------------
# OS RODAPÉS QUE EXISTEM
# ---------------------------------------------------------------------------
# Cada variante é o conjunto de BLOCOS que ela mostra. Bloco é a unidade que o
# mantenedor enxerga na tela: a assinatura da escola, a lista de links, a linha
# de direitos. Guardar o conjunto (e não um template por variante) é o que faz
# uma variante nova custar uma linha aqui, e não um arquivo novo.
BLOCOS = frozenset({"assinatura", "links", "direitos"})

VARIANTES = {
    # O rodapé cheio: quem é a escola, para onde ir, e a linha de direitos.
    # Vale nas páginas de leitura, onde a pessoa está passeando pelo site.
    "completo": frozenset({"assinatura", "links", "direitos"}),
    # O rodapé curto: só a linha de direitos. Vale nas páginas em que a pessoa
    # veio fazer UMA coisa (entrar, se cadastrar) — ali uma lista de links é
    # convite para sair no meio do caminho.
    "enxuto": frozenset({"direitos"}),
}

VARIANTE_PADRAO = "completo"

# A tabela de exceções: nome da rota (o `name=` do `config/urls.py`) → a
# variante que ela mostra, ou `None` para "esta página não tem rodapé".
# Rota que não está aqui usa o VARIANTE_PADRAO — inclusive rota que nascer
# amanhã, que é o que faz "em todas as páginas" continuar verdade sozinho.
REGRA_POR_ROTA = {
    "cadastro": "enxuto",
    "entrar": "enxuto",
}

# Rotas de MÁQUINA: não são páginas, e um rodapé nelas seria lixo dentro de um
# XML ou de um arquivo estático. Ficam de fora por nome, não por adivinhação.
ROTAS_SEM_PAGINA = frozenset({"sitemap_xml", "static"})


def variante_da_rota(nome_da_rota: "str | None") -> "str | None":
    """Qual rodapé esta rota mostra — `None` quando não mostra nenhum.

    `nome_da_rota` vem de `request.resolver_match.url_name`. Rota sem nome
    (nenhuma nesta célula, mas o Django permite) cai no padrão, como qualquer
    página que ninguém decidiu diferente.
    """
    if nome_da_rota in ROTAS_SEM_PAGINA:
        return None
    if nome_da_rota in REGRA_POR_ROTA:
        return REGRA_POR_ROTA[nome_da_rota]
    return VARIANTE_PADRAO


def montar(variante: str, *, ano: int) -> dict:
    """O dicionário que o template consome — a costura da etapa 2.

    Hoje ele carrega só a estrutura (que blocos aparecem) e os dados que não são
    texto: o ano e os endereços das outras células. Os textos saem do catálogo,
    no próprio template. Quando o painel entrar, é esta função que passa a
    receber o que o dono escreveu, e o template segue igual.
    """
    blocos = VARIANTES[variante]
    return {
        "variante": variante,
        "mostra_assinatura": "assinatura" in blocos,
        "mostra_links": "links" in blocos,
        "mostra_direitos": "direitos" in blocos,
        "ano": ano,
        # Endereços de OUTRAS células: crus e monolíngues de propósito — o
        # prefixo de idioma é desta célula, e prefixá-los morre 404 no gateway
        # (guarda 3 do D6). Mesma regra que `request.url_da_caixa` já segue.
        "url_do_forum": enderecos.url_do_forum(),
        "url_dos_documentos": enderecos.url_dos_documentos(),
    }


def rodape_do_contexto(request) -> dict:
    """Processador de contexto: põe `rodape` em TODA página desta célula.

    É processador, e não `{% include %}` avulso em cada template, porque a
    exigência do mantenedor foi "em todas as páginas" — e um mecanismo que
    depende de alguém lembrar de incluir a peça não cumpre essa frase. O
    `base_mobile.html` desenha; este processador decide.

    Devolve `{}` (e o `{% if rodape %}` do template cala) quando o site não tem
    idioma resolvido: ali não há catálogo de onde tirar o texto, e a saída dos
    domínios monolíngues continua byte a byte a de sempre.
    """
    if getattr(request, "i18n_seo", None) is None:
        return {}
    resolvida = getattr(request, "resolver_match", None)
    variante = variante_da_rota(resolvida.url_name if resolvida else None)
    if variante is None:
        return {}
    return {"rodape": montar(variante, ano=timezone.localdate().year)}
