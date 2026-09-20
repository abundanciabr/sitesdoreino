"""`/admin/paginas/` — onde o mantenedor escreve o texto da página de venda.

Sem esta tela, o único jeito de preencher os espaços da página seria linha de
comando, e a estrutura construída na célula `catalogo` não serviria para nada.
Ela é a tela em que ELE faz: escreve o texto e publica.

## Onde o dado mora, e por que não aqui

Na `catalogo`, que é o registro canônico do multissítio, pelas operações
`getPageDraft`, `putPageDraft` e `publishPage` do contrato congelado
(`contracts/catalogo.openapi.yaml`). Esta célula não guarda cópia: a página
seria o mesmo fato em dois lugares, e no dia em que discordassem o site
mostraria uma coisa e esta tela outra.

Qual site? O do domínio pelo qual a requisição chegou, como na tela do menu
([INV-P11]). Nada de lista para escolher.

## Por que a tela é um formulário simples, sem script

Pelas três razões escritas em `apps/core/menu.py`, que valem inteiras aqui: o
que se vê é o que está gravado, a política de segurança desta área proíbe
script embutido (`armadilhas/199`), e um botão por gesto não tem como ser mal
entendido por quem não é programador.

## As palavras da tela são as do despacho, e isso é mecanismo

Cada espaço traz ao lado a frase que o explica, e essa frase é transcrita de
`docs/despachos/DESPACHO-COPY-DA-PAGINA-DE-OFERTA.md`, que é o documento em que
a casa perguntou a ele, espaço por espaço, o que escrever. Duas redações para a
mesma pergunta fariam ele responder uma coisa no documento e ler outra na tela.

A transcrição não é promessa: `tests/test_pagina_de_venda.py` lê o documento,
extrai as onze seções, os espaços e a frase de cada um, e compara com o que
está aqui, caractere por caractere. Corrigir o documento e esquecer a tela fica
vermelho no PR.

## Espaço vazio não é erro

É seção que não aparece na página. O provedor já trata assim
(`services/catalogo/apps/paginas/vocabulario.py`), o despacho diz a ele que
"espaço em branco é resposta legítima", e a tela precisa dizer o mesmo: senão
o primeiro uso, com trinta e nove campos vazios, parece defeito.

## A sentinela da ferramenta 74 avisa; quem decide é ele

Em 05/09/2026 o mantenedor escreveu a lista do que a página nunca pode ter
(`documentos/ferramentas-do-projeto-meshcraft.md:971`): contagem regressiva,
"últimas vagas", valor riscado, promessa de renda ou de prazo, e superlativo.
A tela aponta o que encontrou, com o espaço e o trecho, e deixa publicar assim
mesmo. Bloquear poria a máquina decidindo o que ele pode dizer no próprio site;
calar deixaria a regra dele existir só no papel.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.auditoria.models import Registro

from .clients import CatalogoClient
from .views import _auditar

# A página que esta tela escreve. A casa tem UMA, e o despacho inteiro é sobre
# ela; um seletor para escolher entre uma opção seria cerimônia. Quando a
# segunda nascer, `paginas/` vira a lista e `paginas/<slug>/` o editor, sem que
# o endereço desta mude.
SLUG_DA_PAGINA = "oferta"


@dataclass(frozen=True)
class Espaco:
    """Um espaço de texto da página, com a frase que o explica para um leigo."""

    nome: str
    explicacao: str


@dataclass(frozen=True)
class Secao:
    """Uma das onze seções, com o que ela é em uma linha e os espaços dela."""

    nome: str
    e: str
    espacos_do_formulario: tuple[Espaco, ...]

    def espacos(self) -> tuple[str, ...]:
        return tuple(espaco.nome for espaco in self.espacos_do_formulario)


# Os espaços que cabem numa linha. Todo o resto é caixa de texto: quem vai
# escrever três frases num campo de uma linha desiste na segunda.
DE_UMA_LINHA = frozenset(
    {
        "headline",
        "subheadline",
        "cta_texto",
        "cta_destino",
        "imagem",
        "preco_texto",
        "parcelamento",
        "assinatura",
    }
)


def _espacos(*pares: tuple[str, str]) -> tuple[Espaco, ...]:
    return tuple(Espaco(nome, explicacao) for nome, explicacao in pares)


#: As ONZE seções, na ordem dele, com as palavras do despacho. Não mexa aqui
#: sem mexer no despacho: o guarda compara os dois.
SECOES: tuple[Secao, ...] = (
    Secao(
        "cubo",
        "a abertura da página",
        _espacos(
            (
                "headline",
                "A frase maior da página, a primeira coisa que a pessoa lê. Diz o "
                "que ela sai sabendo ou conseguindo.",
            ),
            (
                "subheadline",
                "Uma frase abaixo do título, que explica a de cima sem repetir as "
                "mesmas palavras. Costuma dizer para quem a coisa é, ou por qual "
                "caminho ela acontece.",
            ),
            ("cta_texto", "O que está escrito dentro do botão."),
            ("cta_destino", "Para onde o botão leva."),
            ("imagem", "A imagem do topo."),
        ),
    ),
    Secao(
        "viloes",
        "os três vilões",
        _espacos(
            (
                "headline",
                "O título da seção que descreve a situação em que a pessoa está "
                "hoje, antes de comprar.",
            ),
            (
                "vilao_1",
                "O primeiro vilão: o que atrapalha a pessoa, descrito com as "
                'palavras que ela mesma usaria. Serve para ela pensar "é '
                'exatamente isso".',
            ),
            ("vilao_2", "O segundo vilão, na mesma forma."),
            ("vilao_3", "O terceiro vilão, na mesma forma."),
            (
                "prova",
                "O que mostra que esses três vilões são reais, e não invenção de "
                "quem vende.",
            ),
        ),
    ),
    Secao(
        "metodo",
        "o método",
        _espacos(
            (
                "headline",
                "O título da seção que explica como o seu método resolve aquilo.",
            ),
            (
                "texto",
                "A explicação de por que o método funciona. É o princípio, não a "
                "lista de aulas: a lista fica em `percurso`.",
            ),
            ("imagem", "Uma imagem ou desenho que mostre o método."),
            ("prova", "O que mostra que o método funciona."),
        ),
    ),
    Secao(
        "instrumentos",
        "os instrumentos, com o índice de estúdios como prova",
        _espacos(
            (
                "headline",
                "O título da seção sobre as ferramentas de conferência que o aluno "
                "recebe.",
            ),
            (
                "texto",
                "O que são os instrumentos e para que servem, do ponto de vista de "
                "quem vai usar.",
            ),
            (
                "indice_de_estudios",
                "O texto que apresenta o índice de estúdios, que é a prova que você "
                "escolheu para esta seção.",
            ),
            ("prova", "O que mostra que os instrumentos funcionam fora da sua sala."),
        ),
    ),
    Secao(
        "percurso",
        "o percurso",
        _espacos(
            ("headline", "O título da seção que mostra o caminho do começo ao fim."),
            (
                "texto",
                "O caminho em passos, para a pessoa ver onde entra e onde chega.",
            ),
            ("prova", "O que mostra que alguém percorreu esse caminho até o fim."),
        ),
    ),
    Secao(
        "tempo",
        "quanto tempo leva, admitindo que os números ainda não existem",
        _espacos(
            ("headline", "O título da seção."),
            ("texto", 'A resposta honesta para "em quanto tempo eu chego lá".'),
            ("prova", "O que sustenta o que o texto diz sobre tempo."),
        ),
    ),
    Secao(
        "para_quem_nao_serve",
        "para quem não serve, no meio da página, com seis recusas",
        _espacos(
            ("headline", "O título da seção."),
            *(
                (
                    f"recusa_{numero}",
                    "Cada uma é um tipo de pessoa, ou uma expectativa, que este "
                    "curso não atende. Uma frase por recusa, dita sem rodeio.",
                )
                for numero in range(1, 7)
            ),
        ),
    ),
    Secao(
        "se_eu_parar",
        "o que acontece se eu parar",
        _espacos(
            ("headline", "O título da seção."),
            (
                "texto",
                "O que acontece com quem comprou e parou no meio: o que ela perde, "
                "o que ela mantém, e se dá para voltar.",
            ),
        ),
    ),
    Secao(
        "oferta",
        "o que recebe e o preço, uma vez e sem ancoragem",
        _espacos(
            ("headline", "O título da seção onde o preço aparece."),
            (
                "o_que_recebe",
                "A lista do que entra na compra, escrita do ponto de vista de quem "
                "paga.",
            ),
            ("preco_texto", "O preço à vista, escrito como a pessoa lê na tela."),
            ("parcelamento", "Em quantas vezes e de quanto fica cada parcela."),
            ("cta_texto", "O que está escrito no botão desta seção."),
        ),
    ),
    Secao(
        "carta",
        "a carta do autor, por inteiro",
        _espacos(
            ("headline", "O título da seção."),
            (
                "texto",
                "A carta inteira, na sua voz. É onde a pessoa decide se confia em "
                "você.",
            ),
            ("assinatura", "Como a carta termina: o nome, e o que vem junto do nome."),
        ),
    ),
    Secao(
        "perguntas",
        "as perguntas",
        _espacos(
            ("headline", "O título da seção."),
            (
                "perguntas",
                "A lista de perguntas com as respostas. Vale a pena responder aqui o "
                "que faz a pessoa desistir na hora de pagar.",
            ),
        ),
    ),
)

TOTAL_DE_ESPACOS = sum(len(secao.espacos()) for secao in SECOES)


# ---------------------------------------------------------------------------
# A sentinela da ferramenta 74
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PadraoProibido:
    """Um dos cinco padrões que ele proibiu, e as formas de escrevê-lo."""

    nome: str
    formas: tuple[re.Pattern, ...]


def _formas(*expressoes: str) -> tuple[re.Pattern, ...]:
    return tuple(re.compile(e) for e in expressoes)


#: SÃO CINCO, e são os dele. A lista sai de `documentos/ferramentas-do-projeto-
#: meshcraft.md:971`, ferramenta 74, escrita em 05/09/2026. Padrão inventado por
#: quem programa não entra aqui: a régua é dele, e um alarme que ele não
#: reconhece é um alarme que ele aprende a ignorar.
#:
#: As formas casam num texto SEM ACENTO e em minúsculas (ver `_dobrar`), para
#: que "últimas vagas" e "ULTIMAS VAGAS" sejam a mesma coisa.
PADROES_PROIBIDOS: tuple[PadraoProibido, ...] = (
    PadraoProibido(
        "contagem regressiva",
        _formas(
            r"\bcontagem regressiva\b",
            r"\bfaltam?\s+(?:apenas\s+|so\s+)?\d+\s*(?:segundos?|minutos?|horas?|dias?)\b",
            r"\b(?:termina|acaba|encerra|expira|fecha)\s+(?:em\s+\d|hoje|amanha|a meia-noite|as\s+\d)",
            r"\bso ate\s+(?:hoje|amanha|meia-noite|domingo|\d)",
            r"\bultim[ao]s?\s+\d+\s*(?:horas?|dias?)\b",
        ),
    ),
    PadraoProibido(
        "últimas vagas",
        _formas(
            r"\bultim[ao]s?\s+vagas?\b",
            r"\bvagas?\s+(?:limitad[ao]s?|restantes?)\b",
            r"\brestam?\s+(?:apenas\s+|so\s+)?\d+\s+vagas?\b",
            r"\bpoucas vagas\b",
            r"\bultim[ao]s?\s+unidades\b",
            r"\bturma quase (?:cheia|lotada)\b",
        ),
    ),
    PadraoProibido(
        "valor riscado",
        _formas(
            r"~~\s*(?:de\s*)?r\$",
            r"r\$\s*[\d.,]+\s*~~",
            r"</?(?:s|del|strike)\b[^>]*>",
            r"\bde\s*:?\s*r\$\s*[\d.,]+\s*(?:por|para)\s*(?:apenas\s*)?r\$",
            r"\bem vez de\s*r\$",
            r"\bpreco\s+(?:antigo|cheio|normal)\b",
        ),
    ),
    PadraoProibido(
        "promessa de renda ou de prazo",
        _formas(
            # Renda: dinheiro ao lado de um verbo de ganhar. O parcelamento
            # legítimo ("12x de R$ 49 por mês") não tem verbo nenhum, e por isso
            # não acende alarme.
            r"\b(?:ganh\w+|fatur\w+|lucr\w+|renda|rendimento|receita)\b[^.!?]{0,60}\br\$",
            r"\br\$\s*[\d.,]+[^.!?]{0,60}\b(?:ganh\w+|fatur\w+|lucr\w+|de renda)\b",
            r"\bprimeir[ao]s?\s+r\$",
            # Prazo: um número de tempo ao lado de uma promessa. "34 encomendas
            # em 3 partes" não casa porque parte não é unidade de tempo, e "em
            # 12 meses o curso inteiro" não casa porque não promete nada.
            r"\bem\s+(?:apenas\s+|so\s+)?\d+\s*(?:dias?|semanas?|mes|meses|horas?)\b"
            r"[^.!?]{0,60}\b(?:voce|vai|ja|estara|consegue|conseguira|domina|dominara|"
            r"pront[ao]|garantid\w+)\b",
            r"\bem\s+(?:apenas\s+|so\s+)?\d+\s*(?:dias?|semanas?|mes|meses)\b"
            r"[^.!?]{0,30}\b(?:resultado|resultados)\b",
        ),
    ),
    PadraoProibido(
        "superlativo",
        _formas(
            r"\b[oa]s?\s+(?:melhor(?:es)?|maior(?:es)?|unic[ao]s?|pior(?:es)?)\b",
            r"\b[oa]s?\s+mais\s+\w+\s+d[oa]s?\s+(?:mundo|brasil|mercado|pais|planeta)\b",
            r"\b[oa]s?\s+mais\s+(?:complet[ao]|avancad[ao]|poderos[ao]|eficaz|"
            r"eficiente|rapid[ao]|barat[ao])\b",
            r"\b(?:definitiv[ao]|imbativel|insuperavel|revolucionari[ao]|"
            r"extraordinari[ao]|espetacular|sensacional)\b",
            r"\bnumero\s+1\b",
        ),
    ),
)


def _dobrar(texto: str) -> tuple[str, list[int]]:
    """O texto sem acento e em minúsculas, com o caminho de volta ao original.

    Casar acento a acento faria a sentinela perder "ÚLTIMAS VAGAS"; casar no
    texto dobrado e não saber voltar faria ela mostrar um trecho torto. A lista
    devolvida diz, para cada letra do texto dobrado, de que letra do original
    ela veio, e é ela que permite citar o trecho como ele foi escrito.
    """
    plano: list[str] = []
    volta: list[int] = []
    for posicao, letra in enumerate(texto):
        for parte in unicodedata.normalize("NFD", letra):
            if unicodedata.combining(parte):
                continue
            plano.append(parte.lower())
            volta.append(posicao)
    volta.append(len(texto))
    return "".join(plano), volta


def _trecho(texto: str, comeco: int, fim: int) -> str:
    """O pedaço citado: o que casou, com um pouco de folga dos dois lados."""
    inicio = max(0, comeco - 25)
    final = min(len(texto), fim + 25)
    citado = texto[inicio:final].strip()
    return ("…" if inicio > 0 else "") + citado + ("…" if final < len(texto) else "")


def sentinela(escritos: dict[str, dict[str, str]]) -> list[dict]:
    """O que a lista da ferramenta 74 encontrou no texto, ou lista vazia.

    Devolve um achado por padrão e por espaço, na ordem em que a página se lê,
    com o trecho citado como ele foi escrito. Nunca recusa nada: quem decide
    publicar é o dono do site.
    """
    achados = []
    for secao in SECOES:
        textos = escritos.get(secao.nome) or {}
        for espaco in secao.espacos_do_formulario:
            texto = (textos.get(espaco.nome) or "").strip()
            if not texto:
                continue
            plano, volta = _dobrar(texto)
            for padrao in PADROES_PROIBIDOS:
                for forma in padrao.formas:
                    casou = forma.search(plano)
                    if casou is None:
                        continue
                    achados.append(
                        {
                            "padrao": padrao.nome,
                            "onde": f"{secao.nome}.{espaco.nome}",
                            "trecho": _trecho(
                                texto, volta[casou.start()], volta[casou.end()]
                            ),
                        }
                    )
                    break  # um achado por padrão e por espaço já diz o que fazer
    return achados


# ---------------------------------------------------------------------------
# A tela
# ---------------------------------------------------------------------------
def _escritos_do_rascunho(rascunho: dict) -> dict[str, dict[str, str]]:
    """O rascunho do catálogo virado em `{seção: {espaço: texto}}`."""
    escritos: dict[str, dict[str, str]] = {}
    for secao in rascunho.get("secoes") or []:
        nome = secao.get("nome")
        slots = secao.get("slots") or {}
        if isinstance(nome, str) and isinstance(slots, dict):
            escritos[nome] = {c: v for c, v in slots.items() if isinstance(v, str)}
    return escritos


def _escritos_do_formulario(post) -> dict[str, dict[str, str]]:
    """O que ele acabou de digitar, lido campo a campo do formulário."""
    escritos: dict[str, dict[str, str]] = {}
    for secao in SECOES:
        preenchidos = {}
        for espaco in secao.espacos_do_formulario:
            texto = (post.get(f"{secao.nome}.{espaco.nome}") or "").strip()
            if texto:
                preenchidos[espaco.nome] = texto
        if preenchidos:
            escritos[secao.nome] = preenchidos
    return escritos


def _para_o_catalogo(escritos: dict[str, dict[str, str]]) -> list[dict]:
    """As seções na forma que o contrato pede, na ordem canônica.

    Só o que tem texto viaja: espaço vazio é seção que não aparece, e mandar
    uma chave vazia faria o provedor guardar um silêncio com aparência de
    resposta.
    """
    return [
        {
            "nome": secao.nome,
            "ordem": ordem,
            "slots": escritos[secao.nome],
        }
        for ordem, secao in enumerate(SECOES)
        if escritos.get(secao.nome)
    ]


def _contexto(request, escritos, *, base_version, motivo="", erro="", recado=""):
    secoes = []
    preenchidos = 0
    invisiveis = []
    for secao in SECOES:
        textos = escritos.get(secao.nome) or {}
        campos = []
        for espaco in secao.espacos_do_formulario:
            valor = textos.get(espaco.nome) or ""
            if valor.strip():
                preenchidos += 1
            campos.append(
                {
                    "campo": f"{secao.nome}.{espaco.nome}",
                    "nome": espaco.nome,
                    "explicacao": espaco.explicacao,
                    "valor": valor,
                    "de_uma_linha": espaco.nome in DE_UMA_LINHA,
                }
            )
        if not textos:
            invisiveis.append(secao.e)
        secoes.append(
            {
                "nome": secao.nome,
                "e": secao.e,
                "campos": campos,
                "vazia": not textos,
                # A conta por seção vai na aba da gaveta: com onze gavetas
                # fechadas, ela é a única forma de ele ver onde parou sem abrir
                # uma por uma.
                "preenchidos": sum(1 for c in campos if c["valor"].strip()),
                "total": len(campos),
            }
        )
    return {
        "admin": request.admin,
        "secoes": secoes,
        "preenchidos": preenchidos,
        "total": TOTAL_DE_ESPACOS,
        "invisiveis": invisiveis,
        "achados": sentinela(escritos),
        # Três estados, e o template não sabe distinguir `None` de zero: quem
        # decide é aqui. `None` é "não perguntei agora" (a tela que voltou de
        # uma gravação recusada), zero é "nunca esteve no ar".
        "sabe_do_ar": base_version is not None,
        "nunca_publicada": base_version == 0,
        "versao_no_ar": base_version,
        "motivo": motivo,
        "erro": erro,
        "recado": recado,
    }


def _site(request) -> "dict | None":
    return CatalogoClient().site_por_host(request.get_host().split(":")[0].lower())


def _sem_catalogo(request, status: int = 200):
    """Fail-OPEN, como a tela do menu: aviso honesto, nunca 500.

    E sem formulário: um formulário que não tem onde salvar é uma armadilha de
    trabalho perdido.
    """
    return render(
        request,
        "admin/pagina_de_venda.html",
        {"admin": request.admin, "sem_catalogo": True},
        status=status,
    )


def _carregar(request, site):
    """O rascunho de hoje: `(escritos, base_version)` ou `None` se não deu.

    `None` é "não consegui perguntar", e ele é diferente de folha em branco. A
    diferença não é acadêmica: oferecer campos vazios porque a leitura falhou
    faria o primeiro `Salvar` apagar tudo o que ele já tinha escrito.
    """
    situacao, corpo = CatalogoClient().rascunho_da_pagina(site["id"], SLUG_DA_PAGINA)
    if situacao == CatalogoClient.SEM_RASCUNHO:
        return {}, 0
    if situacao != CatalogoClient.OK:
        return None
    return _escritos_do_rascunho(corpo), corpo.get("base_version") or 0


@require_GET
def pagina_de_venda(request):
    """A tela: um campo por espaço, agrupado por seção, na ordem da página."""
    site = _site(request)
    if site is None:
        return _sem_catalogo(request)

    lido = _carregar(request, site)
    if lido is None:
        return render(
            request,
            "admin/pagina_de_venda.html",
            {"admin": request.admin, "sem_leitura": True},
        )

    escritos, base_version = lido
    return render(
        request,
        "admin/pagina_de_venda.html",
        _contexto(
            request,
            escritos,
            base_version=base_version,
            recado=request.GET.get("recado", ""),
        ),
    )


def _motivo_de_nao_salvar(situacao: str) -> str:
    """Qual das três recusas a tela precisa explicar, e elas não se parecem.

    `recusado` é regra do catálogo sobre o texto; `sem_pagina` é a página não
    existir lá, e o conserto é de quem cuida do catálogo; `nao_salvou` é rede
    ou configuração, e o conserto é tentar de novo.
    """
    if situacao == CatalogoClient.RECUSADO:
        return "recusado"
    if situacao == CatalogoClient.SEM_PAGINA:
        return "sem_pagina"
    return "nao_salvou"


@require_POST
def pagina_de_venda_salvar(request):
    """Grava o rascunho inteiro. Não muda nada do que está no ar."""
    site = _site(request)
    if site is None:
        return _sem_catalogo(request, status=503)

    escritos = _escritos_do_formulario(request.POST)
    situacao, resposta = CatalogoClient().gravar_rascunho_da_pagina(
        site["id"], SLUG_DA_PAGINA, _para_o_catalogo(escritos)
    )
    detalhe = f"{SLUG_DA_PAGINA}: {sum(len(v) for v in escritos.values())} espaço(s)"

    if situacao == CatalogoClient.OK:
        _auditar(
            request,
            Registro.SALVAR_RASCUNHO_DA_PAGINA,
            SLUG_DA_PAGINA,
            Registro.OK,
            detalhe,
        )
        # POST-redirect-GET: sem ele, um F5 depois de salvar repetiria a
        # gravação inteira.
        return HttpResponseRedirect(f"{reverse('pagina_de_venda')}?recado=salvo")

    recusado = situacao in (CatalogoClient.RECUSADO, CatalogoClient.SEM_PAGINA)
    _auditar(
        request,
        Registro.SALVAR_RASCUNHO_DA_PAGINA,
        SLUG_DA_PAGINA,
        Registro.RECUSADO_PELA_CELULA if recusado else Registro.NAO_RESPONDEU,
        detalhe,
    )
    # A tela volta com O QUE ELE DIGITOU, e não com o que está gravado. É o
    # contrário da tela do menu, e de propósito: lá o conteúdo é a configuração
    # do site, aqui o conteúdo é o trabalho dele, e perdê-lo por uma falha de
    # rede seria a máquina apagando trabalho de gente.
    return render(
        request,
        "admin/pagina_de_venda.html",
        _contexto(
            request,
            escritos,
            base_version=None,
            motivo=_motivo_de_nao_salvar(situacao),
            erro=resposta,
        ),
        status=422 if recusado else 503,
    )


@require_POST
def pagina_de_venda_publicar(request):
    """Põe no ar o rascunho salvo, criando a versão seguinte da página."""
    site = _site(request)
    if site is None:
        return _sem_catalogo(request, status=503)

    situacao, resposta = CatalogoClient().publicar_pagina(site["id"], SLUG_DA_PAGINA)
    if situacao == CatalogoClient.OK:
        versao = resposta.get("version")
        _auditar(
            request,
            Registro.PUBLICAR_PAGINA,
            SLUG_DA_PAGINA,
            Registro.OK,
            f"{SLUG_DA_PAGINA}: publicou a versão {versao}",
        )
        return HttpResponseRedirect(f"{reverse('pagina_de_venda')}?recado=publicado")

    vazio = situacao == CatalogoClient.VAZIO
    sem_pagina = situacao == CatalogoClient.SEM_PAGINA
    _auditar(
        request,
        Registro.PUBLICAR_PAGINA,
        SLUG_DA_PAGINA,
        (
            Registro.RECUSADO_PELA_CELULA
            if vazio or sem_pagina
            else Registro.NAO_RESPONDEU
        ),
        f"{SLUG_DA_PAGINA}: {resposta}",
    )

    lido = _carregar(request, site)
    escritos, base_version = ({}, 0) if lido is None else lido
    return render(
        request,
        "admin/pagina_de_venda.html",
        _contexto(
            request,
            escritos,
            base_version=base_version,
            motivo=(
                "vazio" if vazio else "sem_pagina" if sem_pagina else "nao_publicou"
            ),
            erro=resposta,
        ),
        status=409 if vazio else 503,
    )
