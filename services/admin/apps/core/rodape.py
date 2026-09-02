# apps/core/rodape.py
"""O rodapé do site nas páginas PÚBLICAS desta célula (`/docs/`).

**Cópia do PADRÃO das outras células, com a regra INVERTIDA — e a inversão é a
única coisa importante deste arquivo.** Na `funil`, no `forum`, na `sugestoes` e
na `gamificacao` o padrão é "toda página mostra o rodapé", e a exceção se
declara. Aqui é o contrário: o padrão é NÃO mostrar, e a exceção é a lista de
rotas públicas.

## Por que invertido

Esta célula é bastidor com duas janelas para a rua. Das ~60 rotas nomeadas dela,
duas servem página a quem não é o mantenedor: a biblioteca de documentos e um
documento. O resto é a área de administração, que tem molde próprio
(`admin/base.html`), navegação própria e não é do site — pôr ali a assinatura
pública seria dizer ao mantenedor "você está no site", quando ele está na sala
de máquinas.

Se o padrão fosse "mostra", cada tela nova do bastidor nasceria com o rodapé do
site e alguém teria de lembrar de tirá-lo — a `armadilhas/242` ao contrário,
com o mesmo defeito de raiz (a peça dependendo de alguém lembrar).

## E o que impede ESTA lista de envelhecer

`ROTAS_PUBLICAS` é escrita à mão, e lista escrita à mão apodrece. O guarda em
`tests/test_rodape_publico.py` a compara com as rotas que
`painel/mapa-do-site.json` declara públicas nesta célula — o mesmo mapa que já
tem varredor provando que ele não mente sobre o roteamento. Página pública nova
na `admin` reprova o PR até entrar aqui.

## As páginas de erro NÃO entram, e é medição, não esquecimento

`admin/404.html` e `admin/503.html` estendem `admin/base.html`, o molde do
bastidor — não o `base_publico.html`. Elas já têm a forma daquela área, e
mudá-las é outro assunto, com outra decisão. Conferido no disco em 02/09/2026.
"""

from django.utils import timezone

BLOCOS = frozenset({"assinatura", "links", "direitos"})

VARIANTES = {
    "completo": frozenset({"assinatura", "links", "direitos"}),
    "enxuto": frozenset({"direitos"}),
}

# As DUAS janelas para a rua desta célula, por nome de rota. Quem confere que
# esta lista é exatamente a que o mapa do site declara pública é
# `tests/test_rodape_publico.py`.
ROTAS_PUBLICAS = {
    "docs_publicos": "completo",
    "doc_publico": "completo",
}

# Os endereços das OUTRAS partes do site. Crus, porque cada célula é dona do
# próprio prefixo e esta não monta endereço de ninguém.
URL_DO_SITE = "/"
URL_DA_BIBLIOTECA = "/docs/"


def variante_da_rota(nome_da_rota: "str | None") -> "str | None":
    """Qual rodapé esta rota mostra — `None` para toda página do bastidor."""
    return ROTAS_PUBLICAS.get(nome_da_rota)


def enderecos_de_outras_celulas() -> set:
    """Os links que este rodapé traz para FORA desta célula.

    Existe pelo mesmo motivo da irmã em `sugestoes`: os guardas de prefixo
    (`armadilhas/029`/`081`) precisam saber distinguir um endereço desta célula
    escrito à mão de um endereço que é de outra por natureza. A lista sai daqui,
    que é quem os declara, e não de uma cópia dentro dos testes.
    """
    return {URL_DO_SITE, URL_DA_BIBLIOTECA}


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
        "url_da_biblioteca": URL_DA_BIBLIOTECA,
    }


def rodape_do_contexto(request) -> dict:
    """Processador de contexto: põe `rodape` nas páginas públicas desta célula.

    É processador, e não uma inclusão escrita em cada template, porque "em todas
    as páginas públicas" não pode depender de alguém lembrar da peça
    (`armadilhas/242`). Quem desenha é `admin/base_publico.html`.
    """
    resolvida = getattr(request, "resolver_match", None)
    variante = variante_da_rota(resolvida.url_name if resolvida else None)
    if variante is None:
        return {}
    return {"rodape": montar(variante, ano=timezone.localdate().year)}
