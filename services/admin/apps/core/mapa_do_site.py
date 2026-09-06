"""`/admin/mapa/` — o mapa do site inteiro, em árvore, numa página só.

Pedido do mantenedor em 30/08/2026: *"crie um mapa completo do site no painel do
admin"*. A plataforma cresceu por partes — o site, o login, o fórum, a Caixa de
Sugestões, a compra, a área administrativa — e não havia nenhum lugar que
respondesse a pergunta mais simples de todas: **que endereços este site tem?**

## De onde vêm os dados — e por que esta célula NÃO os inventa

| O quê | De onde | Quem escreveu |
|---|---|---|
| O texto de cada endereço | `painel/mapa-do-site.json` | gente, uma entrada por rota |
| O endereço real, o alcance | o mesmo arquivo, **conferido** | `ci/mapa_do_site.py`, na muralha de todo PR |

A pasta `painel/` já viaja para dentro desta imagem (o `deploy-celula` copia a
pasta inteira — é o mesmo caminho por onde o painel do dono e o mapa para IA
chegam aqui), então este arquivo não precisa de passo de build próprio.

**Nada aqui é recalculado.** O endereço, o alcance e a existência de cada rota
são medidos pelo cartógrafo do CI a partir do roteamento do Traefik e dos
`urls.py` das 13 células — e o PR reprova se o mapa e o código discordarem, nos
dois sentidos. Recalcular aqui dentro seria a segunda definição do mesmo fato,
que é exatamente a lei anti-duplicação do `CLAUDE.md`: no dia em que as duas
divergissem, ninguém saberia qual está certa.

**Se o arquivo não vier, a página DIZ isso** (500 e uma frase clara), nunca um
mapa vazio. "Este site não tem endereço nenhum" seria a mentira mais convincente
que esta tela poderia contar — é o falso-verde do padrão 1 da
`RETROSPECTIVA-FASE-D`, na forma de uma tela em branco.

## Sem `{% static %}`, sem script, sem rota nova de arquivo

O estilo é o da própria área (`admin/base.html`), embutido. Célula sob
`SCRIPT_NAME` que serve estático por tag monta endereço da célula ERRADA
(`armadilhas/102`) — e uma página que é só texto e links não precisa de nada
disso.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import unicodedata
from pathlib import Path

from django.shortcuts import render
from django.views.decorators.http import require_GET

from .painel import diretorio_do_painel
from .robos import diretorio_da_fila, onde_isso_mexe

NOME_DO_ARQUIVO = "mapa-do-site.json"

_EMBUTIDO = {
    "script-src": re.compile(
        rb"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.DOTALL | re.IGNORECASE
    ),
    "style-src": re.compile(rb"<style[^>]*>(.*?)</style>", re.DOTALL | re.IGNORECASE),
}

# Os quatro públicos. O vocabulário é o mesmo de `ci/mapa_do_site.py` (que o
# exige fechado), e desde 06/09/2026 ele DEIXOU DE SER O EIXO da tela: a página
# passou a se organizar pela árvore de endereços, e o público virou um selo em
# cada linha, com esta legenda em cima.
#
# Por que o eixo mudou: agrupar por público partia a mesma área do site em
# quatro lugares distantes — a lista de alunos ficava a oitenta linhas da sala
# de aula —, e era isso que tornava as 222 linhas impossíveis de auditar.
#
# `curto` é o que cabe no selo; `titulo` e `explicacao` são a legenda. Público
# que não estiver aqui aparece cru no selo, em vez de sumir: nome estranho o
# dono pergunta, ausência ele nunca percebe.
GRUPOS = (
    (
        "visitante",
        "qualquer um",
        "Para quem só visita",
        "Qualquer pessoa do mundo abre, sem entrar em nada.",
    ),
    (
        "aluno",
        "aluno",
        "Para quem é aluno",
        "Precisa entrar com a conta, e em algumas ter o acesso liberado por você.",
    ),
    (
        "equipe",
        "só você",
        "Para você",
        "A área administrativa. Quem não está na sua lista de administradores "
        "recebe “não existe”, e não “você não pode”.",
    ),
    (
        "maquina",
        "máquina",
        "Só para as máquinas",
        "Ninguém abre à mão: são as portas por onde as partes do site conversam "
        "entre si, e os sinais de vida que o servidor consulta sozinho.",
    ),
)

SELO_DO_PUBLICO = {chave: curto for chave, curto, _, _ in GRUPOS}

# ------------------------------------------------------------------ as áreas
#
# AS CATEGORIAS PRINCIPAIS DO SITE, na ordem em que a página as desenha: o
# caminho de quem chega (vitrine, quiz, compra), o que o aluno recebe (sala de
# aula, portfólio, medalhas, fórum, Caixa, avisos), a sua área, e por último o
# que só as máquinas usam.
#
# Pedido do mantenedor em 06/09/2026: *"crie uma hierarquia das páginas... que
# as páginas fiquem em grupos como em uma árvore... categorias principais e
# abaixo delas as sub-categorias, e páginas e sub-páginas"*. Até aqui a tela
# eram QUATRO listas planas por público, e a maior tinha 106 linhas seguidas:
# ninguém audita um site assim.
#
# O QUE MORA AQUI E O QUE NÃO MORA. Aqui mora só o que uma máquina não sabe: o
# NOME de cada área, em português, e por onde ela começa. A hierarquia de
# dentro (sub-categoria, página, sub-página) é CALCULADA do próprio endereço em
# `_arvore` — `/admin/escola/alunos/recusados` é filho de `/admin/escola/alunos/`
# porque o endereço diz isso, e não porque alguém digitou. Uma segunda lista de
# quem-é-filho-de-quem envelheceria em silêncio na primeira rota nova.
#
# CADA CAMPO:
#   chave       o nome curto, usado no HTML e nos testes
#   titulo      como o dono chamaria a área
#   explicacao  uma linha, sem jargão: o que se faz aqui
#   prefixos    por onde os endereços dela começam. O prefixo MAIS LONGO vence,
#               então `/admin` e `/admin/escola` poderiam coexistir se um dia
#               fizesse sentido separá-los
#
# **Endereço que nenhuma área cobre NÃO some: ele aparece na tela, em voz alta,
# e reprova o teste-guarda** (`services/admin/tests/test_mapa_do_site.py`).
# Isso é o que impede esta lista de envelhecer: rota nova exige entrada em
# `painel/mapa-do-site.json`, o arquivo é da célula `admin`, e a suíte dela roda
# em todo PR que o toca. Cair num grupo mudo é como um mapa morre.
AREA_INTERNA = "por-dentro"

AREAS = (
    (
        "vitrine",
        "A vitrine e a porta de entrada",
        "As páginas que qualquer pessoa do mundo abre, e por onde se entra na conta.",
        ("/", "/cadastro", "/login", "/leads", "/ver-como", "/entrar"),
    ),
    (
        "quiz",
        "O quiz",
        "O teste que a pessoa responde antes de comprar, e a página do resultado.",
        ("/quiz",),
    ),
    (
        "compra",
        "A compra",
        "A tela de pagar, o Pix, o cartão, e as portas por onde o dinheiro é confirmado.",
        ("/checkout", "/api/checkout", "/api/pagamentos"),
    ),
    (
        "sala",
        "A sala de aula",
        "Onde o aluno assiste, entrega a tarefa e recebe o laudo do que fez.",
        ("/cursos",),
    ),
    (
        "portfolio",
        "O portfólio do aluno",
        "A página que o aluno monta para mostrar o trabalho dele ao mundo.",
        ("/pages",),
    ),
    (
        "conquistas",
        "Os pontos e as medalhas",
        "A gamificação da escola: o que o aluno ganha, e o que ele já conquistou.",
        ("/conquistas",),
    ),
    (
        "forum",
        "O fórum",
        "As conversas da turma: as áreas, os assuntos e as respostas.",
        ("/forum",),
    ),
    (
        "caixa",
        "A Caixa de Sugestões",
        "Onde o aluno pede o que quer no site, vota, e acompanha o que virou obra.",
        ("/forms/sugestoes",),
    ),
    (
        "avisos",
        "Os avisos no celular",
        "Ligar e desligar o aviso que chega no telefone do aluno. Não tem tela "
        "própria: são os dois botões da área do aluno.",
        ("/avisos",),
    ),
    (
        "administracao",
        "A sua área de administração",
        "Tudo o que só você abre: a gestão da escola, a Caixa, o livro, os "
        "documentos, o placar e o seu painel.",
        ("/admin",),
    ),
    (
        "documentos",
        "Os documentos publicados",
        "Os textos que você escreve no editor e ficam no ar para quem tem o link.",
        ("/docs",),
    ),
    (
        "mapa-ia",
        "O mapa para uma IA de fora ler",
        "As páginas sem porta que existem para outra inteligência artificial "
        "auditar este sistema quando você pedir uma segunda opinião.",
        ("/mapa-ia",),
    ),
    (
        "sinais",
        "Os arquivos e os sinais do site",
        "Ninguém abre à mão: as imagens e o estilo, o app instalável, o mapa "
        "para o Google, e os sinais de vida que o servidor consulta sozinho.",
        (
            "/static",
            "/sw.js",
            "/manifest.webmanifest",
            "/sitemap.xml",
            "/healthz",
            "/google0e78b54775677e95.html",
            "/alunos",
        ),
    ),
    (
        AREA_INTERNA,
        "As partes que trabalham por dentro",
        "Pedaços do site que a internet não alcança: eles só conversam com as "
        "outras partes, pela rede de dentro do servidor.",
        (),
    ),
)


def _cobre(prefixo: str, endereco: str) -> bool:
    """`/admin` cobre `/admin/escola/`, e `/` cobre só ele mesmo.

    A comparação é por PEDAÇO de caminho, nunca por texto: sem isso `/forum`
    engoliria um futuro `/forumzinho`, e a raiz `/` engoliria o site inteiro.
    """
    if prefixo == "/":
        return endereco == "/"
    return endereco == prefixo or endereco.startswith(prefixo + "/")


def area_de(endereco: str) -> str | None:
    """A área de um endereço, pelo prefixo mais longo. `None` quando nenhuma cobre.

    Devolver `None` é de propósito: a tela mostra o que sobrou numa faixa em voz
    alta e o teste-guarda reprova o PR. Enfiar o desconhecido numa área qualquer
    faria a linha sumir de vista sem nada ficar vermelho.
    """
    if endereco == "-":
        return AREA_INTERNA
    escolhida, tamanho = None, -1
    for chave, _, _, prefixos in AREAS:
        for prefixo in prefixos:
            if _cobre(prefixo, endereco) and len(prefixo) > tamanho:
                escolhida, tamanho = chave, len(prefixo)
    return escolhida


def _degraus(endereco: str) -> tuple[str, ...]:
    """Os pedaços do caminho, que é o que decide quem é filho de quem.

    O `$` do fim de uma rota escrita como expressão regular é sinal de "acaba
    aqui", não pedaço de endereço. Sem tirá-lo, `/admin/documentos/<nome>$` e
    `/admin/documentos/<nome>/editar$` viram irmãos em vez de mãe e filha, e a
    árvore desmonta justamente onde ela mais ajuda.
    """
    return tuple(pedaco for pedaco in endereco.rstrip("$").split("/") if pedaco)


def _arvore(itens: list[dict]) -> list[dict]:
    """As linhas de uma área, achatadas, cada uma sabendo seu `nivel`.

    **A hierarquia sai do endereço, e de nada mais.** A mãe de uma linha é a
    PÁGINA cujo caminho é o maior começo do caminho dela. Assim
    `/admin/escola/alunos/recusados/apagar` acha `/admin/escola/alunos/recusados`
    sozinho, e uma rota nova entra no lugar certo sem ninguém mexer aqui.

    **Botão não vira galho.** Os gestos (o que acontece ao apertar algo) viram
    uma fileira de etiquetas dentro da página a que pertencem. Eles são 96 dos
    222 endereços: como galhos, dobrariam a altura da árvore para responder uma
    pergunta que ninguém faz olhando o mapa.

    Achatar aqui, em vez de aninhar no HTML, é o que dispensa um template que se
    inclui a si mesmo: cada linha leva o próprio `nivel`, e o desenho recua.
    """
    paginas = [i for i in itens if not i["gesto"]]
    por_degrau: dict[tuple[str, ...], dict] = {}
    for pagina in paginas:
        por_degrau.setdefault(_degraus(pagina["endereco"]), pagina)

    def mae(item: dict) -> dict | None:
        degraus = _degraus(item["endereco"])
        for corte in range(len(degraus) - 1, 0, -1):
            candidata = por_degrau.get(degraus[:corte])
            if candidata is not None and candidata is not item:
                return candidata
        return None

    filhas: dict[int, list[dict]] = {}
    raizes: list[dict] = []
    for item in itens:
        item["gestos"] = []
        senhora = mae(item)
        if senhora is None:
            raizes.append(item)
        elif item["gesto"]:
            senhora["gestos"].append(item)
        else:
            filhas.setdefault(id(senhora), []).append(item)

    def ordem(item: dict) -> tuple:
        return (bool(item["gesto"]), item["endereco"])

    linhas: list[dict] = []

    def descer(item: dict, nivel: int) -> None:
        item["nivel"] = nivel
        # O recuo do desenho para no quarto degrau. Mais que isso, num celular,
        # sobra coluna de branco e falta coluna de texto — a linha continua na
        # árvore, só deixa de recuar mais.
        item["recuo"] = min(nivel, 4)
        item["gestos"].sort(key=ordem)
        linhas.append(item)
        for filha in sorted(filhas.get(id(item), []), key=ordem):
            descer(filha, nivel + 1)

    for raiz in sorted(raizes, key=ordem):
        descer(raiz, 0)
    return linhas


def _aninhar(linhas: list[dict]) -> list[dict]:
    """As raízes, com `filhas` dentro de `filhas`, a partir das linhas achatadas.

    **Por que a tela precisa do aninhamento de verdade, e o recuo não bastou.**
    A primeira versão desenhava uma lista achatada e recuava o texto por nível.
    O mantenedor abriu e disse, com todas as letras, o que faltava: *"quero
    poder ver onde começa e onde termina cada parte do site, quais são os pais
    e quais são os filhos"*. Recuo não responde nada disso — ele sugere. Uma
    caixa com borda responde onde começa e onde termina; um trilho ligando a
    mãe às filhas responde de quem é filha.

    Marcação aninhada é o que permite as duas coisas: o `<details>` que abre e
    fecha um galho inteiro, e o trilho que o CSS desenha ao lado das filhas.
    Nenhuma das duas se faz com uma lista plana e uma classe de recuo.

    A entrada continua sendo a lista achatada de `_arvore` (já peneirada pela
    busca, quando há busca), então nada aqui recalcula parentesco: as linhas
    vêm em ordem de descida, e o nível de cada uma diz onde ela entra. Uma
    segunda leitura dos endereços seria a segunda definição do mesmo fato.
    """
    raizes: list[dict] = []
    pilha: list[dict] = []
    for linha in linhas:
        no = {**linha, "filhas": []}
        while pilha and pilha[-1]["nivel"] >= no["nivel"]:
            pilha.pop()
        (pilha[-1]["filhas"] if pilha else raizes).append(no)
        pilha.append(no)

    def contar(no: dict) -> int:
        """Quantas páginas moram dentro deste galho, em todos os degraus.

        É o número que a tela mostra como "N dentro". Ele responde a pergunta
        que o triângulo de abrir e fechar levanta — "o que some se eu fechar
        isto?" — e é o que dá tamanho a um galho fechado.
        """
        no["dentro"] = sum(1 + contar(filha) for filha in no["filhas"])
        return no["dentro"]

    for raiz in raizes:
        contar(raiz)
    return raizes


# ------------------------------------------------------------- o que está em obra
#
# A segunda metade do pedido de 06/09/2026: *"quero poder verificar tudo o que
# existe E o que ainda está sendo construído"*. O que existe é a árvore acima;
# o que está sendo construído é a FILA DE TRABALHO, e ela já viaja nesta imagem
# (a aba "Os robôs" da gestão da Caixa lê a mesma pasta).
#
# **Nada é recalculado aqui.** Os estados saem de `fila_embutida/estados.json`,
# materializado no build por `ci/fila.py listar --json`, e a tradução do `toca`
# para lugares que o dono reconhece é a de `robos.py`. Uma segunda régua de "em
# que pé está" seria a duplicação que o `CLAUDE.md` proíbe.
#
# **O limite, dito na cara:** a fila sabe em que CÉLULA a tarefa mexe, e não em
# que endereço ela vai nascer. Por isso esta seção fica ao lado da árvore, e não
# dentro dela: pendurar a tarefa num galho exigiria adivinhar qual, e um mapa
# que adivinha é pior que um mapa que declara o que não sabe.
EM_ABERTO = ("bloqueada", "reivindicada", "em execução", "na fila")


def em_obra() -> dict | None:
    """As tarefas ainda não terminadas, agrupadas por lugar. `None` sem a fila.

    Fila ausente devolve `None` e a tela diz isso numa linha, em vez de mostrar
    "nada em obra" — que seria a mentira mais convincente desta seção. O mapa em
    si continua de pé: a fila é o segundo assunto da página, não o primeiro.
    """
    pasta = diretorio_da_fila()
    if pasta is None:
        return None
    try:
        estados = json.loads((pasta / "estados.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(estados, dict):
        return None

    por_lugar: dict[str, list[dict]] = {}
    total = 0
    for identificador, tarefa in sorted(estados.items()):
        if not isinstance(tarefa, dict) or tarefa.get("estado") not in EM_ABERTO:
            continue
        total += 1
        cartao = {
            "id": identificador,
            "titulo": tarefa.get("titulo", ""),
            "estado": tarefa.get("estado", ""),
        }
        # Uma tarefa que mexe em dois lugares aparece nos dois. A conta do topo
        # é a de TAREFAS (contadas uma vez), e a de cada lugar é a de tarefas
        # daquele lugar: as duas respondem perguntas diferentes, e somar as
        # segundas não dá a primeira de propósito.
        for lugar in onde_isso_mexe(tarefa.get("toca")) or ["sem lugar declarado"]:
            por_lugar.setdefault(lugar, []).append(cartao)

    return {
        "total": total,
        "lugares": [
            {"nome": nome, "tarefas": tarefas, "quantas": len(tarefas)}
            for nome, tarefas in sorted(
                por_lugar.items(), key=lambda par: (-len(par[1]), par[0])
            )
        ],
    }


def arquivo_do_mapa() -> Path | None:
    """`painel/mapa-do-site.json`, na mesma pasta (embutida ou de checkout)."""
    pasta = diretorio_do_painel()
    if pasta is None:
        return None
    candidato = pasta / NOME_DO_ARQUIVO
    return candidato if candidato.is_file() else None


def _e_molde(endereco: str) -> bool:
    """Endereço com `<pedaço>` ou expressão regular vale para MUITOS endereços.

    `/forum/t/<int:topico_id>` não é um lugar: é a forma de todos os assuntos do
    fórum. A tela precisa saber disso para não oferecer um link que devolve 404.
    """
    return "<" in endereco or "(?P" in endereco


def _preparar(entrada: dict) -> dict:
    """Uma linha da tela, a partir de uma entrada do arquivo.

    O link só existe quando há para onde ir de verdade: endereço concreto, que a
    internet alcança, e que não é um gesto de botão. Um link que devolve 404 (ou
    que dispara uma ação!) é pior que nenhum link — o dono conclui que o site
    quebrou.
    """
    endereco = str(entrada.get("endereco", ""))
    exemplo = entrada.get("exemplo")
    gesto = bool(entrada.get("gesto"))
    publico = entrada.get("alcance") == "publico"
    molde = _e_molde(endereco)
    link = None
    if publico and not gesto:
        if isinstance(exemplo, str) and exemplo:
            link = exemplo
        elif not molde:
            link = endereco
    return {
        "titulo": entrada.get("titulo", ""),
        "descricao": entrada.get("descricao", ""),
        "observacao": entrada.get("observacao"),
        "endereco": endereco,
        "exemplo": exemplo,
        "link": link,
        "molde": molde,
        "gesto": gesto,
        "interno": not publico,
        "celula": entrada.get("celula", ""),
        "para_quem": entrada.get("para_quem", ""),
        "selo": SELO_DO_PUBLICO.get(
            entrada.get("para_quem", ""), entrada.get("para_quem", "")
        ),
        # A luz de "está no ar?". Quem a acende é o NAVEGADOR do dono, pedindo
        # o endereço público de verdade — a prova de fora, do jeito que ele
        # veria. O que pode ser sondado é cercado em `ci/mapa_do_site.py`:
        # gesto, endereço interno e molde sem exemplo são recusados no portão.
        "sonda": (entrada.get("exemplo") or endereco) if entrada.get("sonda") else None,
    }


def _sem_acento(texto: str) -> str:
    """`Sugestões` e `sugestoes` acham a mesma linha.

    O dono digita sem acento no celular tanto quanto com — e uma busca que
    exige o acento certo é uma busca que não encontra.
    """
    sem = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in sem if not unicodedata.combining(c)).casefold()


def _casa(item: dict, procurado: str) -> bool:
    """A busca varre o que a pessoa leria: nome, explicação, endereço e nota."""
    campos = (
        item["titulo"],
        item["descricao"],
        item["endereco"],
        item["observacao"] or "",
        item["exemplo"] or "",
    )
    return any(procurado in _sem_acento(c) for c in campos)


def _politica(html: bytes) -> str:
    """O CSP desta página, com o hash do que ela traz embutido.

    Esta tela manda a própria política porque tem uma ILHA DE SCRIPT (a luz de
    "está no ar?"), e a política da porta diz `script-src 'self'` — sob ela a
    ilha não roda. O caminho é o hash, o mesmo de `painel.py` e `robos.py`:
    `'unsafe-inline'` liberaria QUALQUER script injetado, e nunca entra aqui.

    O `style-src` leva o hash pelo mesmo motivo, e não pode ser esquecido: como
    esta resposta traz a política pronta, a da porta não se aplica (`setdefault`)
    — e sem o hash do estilo a página voltaria a chegar sem desenho nenhum, que
    é exatamente o defeito medido em 30/08/2026 (`armadilhas/199`).

    `connect-src 'self'`: a luz só pergunta a este mesmo site, nunca a terceiro.
    """
    partes = []
    for diretiva, padrao in _EMBUTIDO.items():
        hashes = sorted(
            "'sha256-" + base64.b64encode(hashlib.sha256(m).digest()).decode() + "'"
            for m in set(padrao.findall(html))
        )
        partes.append(f"{diretiva} 'self'" + "".join(f" {h}" for h in hashes))
    return (
        "default-src 'self'; "
        + "; ".join(partes)
        + "; img-src 'self' data:; object-src 'none'; base-uri 'none'; "
        "form-action 'self'; frame-ancestors 'self'; connect-src 'self'"
    )


def _peneirar(linhas: list[dict], procurado: str) -> list[dict]:
    """A busca, sem quebrar a árvore: quem casa fica, e as mães dele também.

    Uma peneira que jogasse fora as mães devolveria galhos soltos no ar —
    `apagar` sem `A lista dos recusados` em cima não diz o que apaga. Como as
    linhas vêm achatadas em ordem de descida, as descendentes de uma linha são
    exatamente as seguintes com nível maior que o dela, até a próxima irmã.
    """
    manter = [
        _casa(linha, procurado) or any(_casa(g, procurado) for g in linha["gestos"])
        for linha in linhas
    ]
    for i in range(len(linhas) - 1, -1, -1):
        nivel = linhas[i]["nivel"]
        j = i + 1
        while j < len(linhas) and linhas[j]["nivel"] > nivel:
            if manter[j]:
                manter[i] = True
                break
            j += 1

    peneiradas = []
    for linha, ficou in zip(linhas, manter):
        if not ficou:
            continue
        if not _casa(linha, procurado):
            # A página entrou pelo que está DENTRO dela — ou por um botão dela,
            # ou por uma sub-página lá embaixo. Nos dois casos ela mostra só os
            # botões que casaram: senão `/admin/escola/` entra como caminho para
            # `recusados` e leva junto "Dar poder de administrador a alguém",
            # que não tem nada a ver com o que foi procurado (medido em
            # 06/09/2026, dois botões de ruído numa busca de cinco linhas).
            linha = {
                **linha,
                "gestos": [g for g in linha["gestos"] if _casa(g, procurado)],
            }
        peneiradas.append(linha)
    return peneiradas


@require_GET
def mapa_do_site(request):
    """A página: uma árvore por área do site, e o que ainda está em obra."""
    caminho = arquivo_do_mapa()
    if caminho is None:
        return render(
            request,
            "admin/mapa_do_site.html",
            {"admin": request.admin, "mapa_ausente": True},
            status=500,
        )
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        entradas = [_preparar(e) for e in dados["enderecos"]]
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        # Mesma lei da pasta ausente: um arquivo torto vira uma tela que diz
        # "não consegui ler o mapa", nunca um mapa pela metade.
        return render(
            request,
            "admin/mapa_do_site.html",
            {"admin": request.admin, "mapa_ausente": True},
            status=500,
        )

    # A BUSCA, e ela é do SERVIDOR de propósito: um formulário que recarrega a
    # página, o mesmo gesto da peneira da lista de alunos. Uma busca em script
    # exigiria abrir a política de segurança para mais uma ilha, e deixaria de
    # funcionar exatamente para quem tem script bloqueado. Aqui o endereço
    # `?q=forum` também é COMPARTILHÁVEL e guardável nos favoritos.
    procurado = _sem_acento(request.GET.get("q", "").strip())

    por_area: dict[str, list[dict]] = {}
    orfas = []
    for entrada in entradas:
        chave = area_de(entrada["endereco"])
        if chave is None:
            orfas.append(entrada)
        else:
            por_area.setdefault(chave, []).append(entrada)

    areas = []
    achados = 0
    for chave, titulo, explicacao, _ in AREAS:
        do_grupo = por_area.get(chave, [])
        if not do_grupo:
            continue
        linhas = _arvore(do_grupo)
        if procurado:
            linhas = _peneirar(linhas, procurado)
        if procurado:
            # A conta é dos endereços que CASAM, nunca das linhas desenhadas.
            # Buscar "recusado" mostrava 9 linhas e a capa dizia "9 de 222 com
            # recusado" — cinco delas eram só o caminho até lá. Número que não
            # responde a própria frase é número errado (medido em 06/09/2026).
            achados += sum(
                (1 if _casa(linha, procurado) else 0) + len(linha["gestos"])
                for linha in linhas
            )
        if not linhas:
            continue
        raizes = _aninhar(linhas)
        areas.append(
            {
                "chave": chave,
                "titulo": titulo,
                "explicacao": explicacao,
                "linhas": linhas,
                # A árvore que a tela desenha. `linhas` continua ao lado dela
                # porque é dela que saem as contas e é ela que os guardas leem:
                # contar percorrendo a árvore daria o mesmo número por um
                # caminho mais longo.
                "raizes": raizes,
                # Por onde esta parte do site COMEÇA, quando começa num lugar
                # só. É metade da pergunta que ele fez ("onde começa e onde
                # termina cada parte"); a outra metade é a borda da caixa.
                "comeca_em": raizes[0]["endereco"] if len(raizes) == 1 else None,
                # As três contas de uma área são disjuntas e somam o que ela
                # mostra — é isso que faz o cabeçalho ser conferível de cabeça.
                "telas": sum(
                    1
                    for linha in linhas
                    if not linha["gesto"] and linha["para_quem"] != "maquina"
                ),
                "botoes": sum(len(linha["gestos"]) for linha in linhas)
                + sum(1 for linha in linhas if linha["gesto"]),
                "maquina": sum(
                    1
                    for linha in linhas
                    if not linha["gesto"] and linha["para_quem"] == "maquina"
                ),
                "visiveis": sum(1 + len(linha["gestos"]) for linha in linhas),
            }
        )

    # Sem busca, "achados" é o mapa inteiro: a contagem por casamento só existe
    # enquanto há palavra procurada, e somar 222 comparações com string vazia
    # daria o mesmo número por um caminho mais caro e menos óbvio.
    if not procurado:
        achados = len(entradas)

    obra = em_obra()
    resposta = render(
        request,
        "admin/mapa_do_site.html",
        {
            "admin": request.admin,
            "areas": areas,
            # O que a pessoa digitou volta para o campo (senão a busca "some" e
            # ela não sabe o que está vendo), e a conta diz de quantos.
            "procurado": request.GET.get("q", "").strip(),
            "achados": achados,
            "total": len(entradas),
            # As três contas são DISJUNTAS e somam o total — é isso que faz a
            # capa desta página ser conferível de cabeça. A primeira versão
            # dizia "71 páginas para abrir" contando as 33 portas de máquina
            # junto: número certo, resposta errada para a pergunta que o dono
            # faz olhando o cartão ("quantas telas eu tenho?").
            "total_telas": sum(
                1 for e in entradas if not e["gesto"] and e["para_quem"] != "maquina"
            ),
            "total_gestos": sum(1 for e in entradas if e["gesto"]),
            "total_maquina": sum(
                1 for e in entradas if not e["gesto"] and e["para_quem"] == "maquina"
            ),
            "total_internos": sum(1 for e in entradas if e["interno"]),
            "obra": obra,
            "legenda": GRUPOS,
            # As entradas que nenhuma área acolheu. Zero hoje, e a tela as
            # mostra em voz alta se um dia não for: linha que some sem erro é a
            # pior forma de perder um fato, e é justamente o que este mapa
            # existe para impedir.
            "orfas": orfas,
        },
    )
    resposta["Content-Security-Policy"] = _politica(resposta.content)
    return resposta
