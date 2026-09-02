# apps/core/rodape.py
"""O rodapé da Caixa: quem mostra, qual dos rodapés, e o que cada um leva.

**Cópia do PADRÃO das células `funil`, `forum` e `gamificacao`, nunca do arquivo
delas** (Lei 7 do Caminho Dourado). O rodapé do site nasceu na `funil` em
31/08/2026 (PR #705) e chegou ao fórum no mesmo dia; as Conquistas o ganharam em
02/09. A Caixa era a última área do site com um pé só dela.

## A troca, e de quem foi a decisão

Até 02/09/2026 esta célula tinha um pé próprio, de duas frases — "Caixa de
Sugestões" e "o que você pedir, a equipe lê". O mantenedor escolheu, nesse dia,
**trocá-lo pelo rodapé do site**: uma assinatura só no fim de toda página, em vez
de uma por área. A frase que sai foi perguntada e respondida, não perdida por
descuido.

O que muda em relação ao fórum, e por quê:

* **Não há catálogo de tradução.** A Caixa é monolíngue, e o texto visível dela
  mora no template, como o resto desta célula. Quando o painel mandar nos
  textos, é `montar()` que passa a receber o que o dono escreveu.
* **A porta da Caixa (`entrar`) fica SEM rodapé, e isso é decisão escrita.** Ela
  é a única tela desta célula que não veste `base_caixa.html`, de propósito: o
  `entrar.html` não tem CSS externo, nem script, nem fonte remota, porque *"uma
  dependência de rede numa página de LOGIN é o tipo de coisa que quebra
  exatamente quando não deveria"*. Pendurar o rodapé ali obrigaria a folha de
  estilo a entrar naquela página, que é justamente o que ela recusa.

  Ela está em `REGRA_POR_ROTA` com `None`, e não em `ROTAS_SEM_PAGINA`: a
  primeira lista diz *"esta PÁGINA não mostra rodapé"*, a segunda diz *"isto nem
  é página"*. A porta é página, e chamá-la de rota de máquina seria mentir na
  estrutura para caber num teste.
"""

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
REGRA_POR_ROTA: "dict[str, str | None]" = {
    # A porta da Caixa. Ver a razão no cabeçalho deste arquivo: ela é a única
    # tela desta célula sem CSS externo, e o rodapé precisa da folha.
    "entrar": None,
}

# Rotas de MÁQUINA: não são páginas. A API interna e o `/healthz` nem chegam a
# ter nome; o servidor de estáticos tem, e por isso precisa estar dito — um
# rodapé dentro do arquivo CSS seria lixo que o navegador serve como estilo.
#
# Os GESTOS desta célula (votar, comentar, sair, marcar aviso lido…) e os
# redirecionamentos de "mudou de casa" NÃO entram aqui, e a ausência é decisão:
# eles respondem com redirecionamento, que não renderiza template nenhum, então
# o rodapé que este módulo oferece simplesmente não é usado. Declará-los "sem
# rodapé" seria dizer uma coisa que não se mede — e no dia em que um deles
# passasse a renderizar uma tela de recusa, ela nasceria sem rodapé por causa de
# uma linha escrita hoje.
ROTAS_SEM_PAGINA = frozenset({"estatico"})

# Os endereços das OUTRAS partes do site. Crus, porque cada célula é dona do
# próprio prefixo e a Caixa não monta endereço de ninguém: se um deles mudar de
# casa, a mudança do lado da Caixa é esta linha.
URL_DO_SITE = "/"
URL_DOS_DOCUMENTOS = "/docs/"


def enderecos_de_outras_celulas() -> set:
    """Os links que este rodapé traz para FORA da Caixa.

    Existe por causa dos guardas de `armadilhas/029`/`081`
    (`tests/test_*_script_name.py`): eles exigem que todo link interno de uma
    página desta célula comece com `/forms/sugestoes/`, porque a regra é
    "nenhum endereço desta célula escrito à mão", e o prefixo é como ela se
    mede.

    O rodapé do site trouxe dois endereços que são de OUTRAS células por
    natureza — a capa e a biblioteca de documentos. Levar o prefixo daqui seria
    o defeito, não a cura.

    A função mora AQUI, e não numa lista dentro dos testes, porque este arquivo
    é quem declara os dois. Uma segunda lista divergiria da primeira no dia em
    que alguém mexesse num deles — e o guarda passaria a reprovar o link certo,
    ou a deixar passar o errado.
    """
    return {URL_DO_SITE, URL_DOS_DOCUMENTOS}


def variante_da_rota(nome_da_rota: "str | None") -> "str | None":
    """Qual rodapé esta rota mostra — `None` quando não mostra nenhum."""
    if nome_da_rota in ROTAS_SEM_PAGINA:
        return None
    if nome_da_rota in REGRA_POR_ROTA:
        return REGRA_POR_ROTA[nome_da_rota]
    return VARIANTE_PADRAO


def rotas_declaradas_sem_rodape() -> set:
    """As duas listas que dizem "sem rodapé", juntas.

    Existe para o guarda da varredura poder comparar contra UMA coisa. Sem ela o
    teste compararia só com `ROTAS_SEM_PAGINA` e ficaria vermelho por causa de
    uma decisão perfeitamente escrita — o que ensinaria a próxima pessoa a
    afrouxar a asserção, que é como um guarda morre.
    """
    return set(ROTAS_SEM_PAGINA) | {
        nome for nome, variante in REGRA_POR_ROTA.items() if variante is None
    }


def montar(variante: str, *, ano: int) -> dict:
    """O dicionário que o template consome — a costura para o painel."""
    blocos = VARIANTES[variante]
    return {
        "variante": variante,
        "mostra_assinatura": "assinatura" in blocos,
        "mostra_links": "links" in blocos,
        "mostra_direitos": "direitos" in blocos,
        "ano": ano,
        "url_do_site": URL_DO_SITE,
        "url_dos_documentos": URL_DOS_DOCUMENTOS,
    }


def rodape_do_contexto(request) -> dict:
    """Processador de contexto: põe `rodape` em TODA página desta célula.

    É processador, e não uma inclusão escrita em cada template, porque "em todas
    as páginas" não pode depender de alguém lembrar de incluir a peça: tela nova
    da Caixa nasce com rodapé sozinha (`armadilhas/242`).
    """
    resolvida = getattr(request, "resolver_match", None)
    variante = variante_da_rota(resolvida.url_name if resolvida else None)
    if variante is None:
        return {}
    return {"rodape": montar(variante, ano=timezone.localdate().year)}
