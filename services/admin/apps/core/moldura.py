# apps/core/moldura.py
"""A MOLDURA das telas de administração: o menu do topo e o rodapé de `/admin`.

Pedido do mantenedor em 02/09/2026: *"crie uma forma de todas as páginas da
parte do admin terem o menu e o rodapé de admin, não é o mesmo menu do site, é
um menu e um rodapé exclusivo da parte de /admin"*.

## O que existia antes, e por que doía

Cada tela desta área desenhava À MÃO a mesma faixa de quatro linhas no topo
(`<div class="barra">` com "Meshcraft · Administração" e o nome de quem entrou),
copiada em 22 templates. Ela não levava a lugar nenhum: para sair de
`/admin/economia/` e chegar em `/admin/caixa/` o mantenedor tinha de passar pela
visão geral, por um link `← Visão geral` que cada tela também escrevia à mão. E
rodapé não havia em nenhuma.

Vinte e duas cópias da mesma peça é a Classe 8 do
`docs/decisoes/PLANO-MESTRE-ROBOS-SEM-COLISAO.md` em forma de marcação: a
vigésima terceira tela nasce sem a faixa no dia em que alguém esquecer de
copiá-la, e ninguém percebe.

## Por que isto é processador de contexto, e não uma inclusão por template

Porque "TODAS as páginas" não pode depender de alguém lembrar da peça
(`armadilhas/242`). É a mesma razão de `apps/core/rodape.py` e de
`apps/core/barra_do_site.py`, e o desenho aqui é o mesmo dos dois: o processador
DECIDE o que vai na moldura, e `admin/base.html` só DESENHA. Tela nova que
estenda o molde nasce com menu e rodapé sem escrever uma linha.

## A moldura só aparece para quem já entrou, e isso é fail-closed

`admin/404.html` estende `admin/base.html`, e é ele que a porta devolve a quem
NÃO está na lista de administradores (`porta.py::_nao_existe`). A porta responde
"não existe" em vez de "você não pode" de propósito. Um menu com os nove
endereços desta área desenhado nessa página entregaria a um estranho o mapa
inteiro do bastidor e desfaria a escolha da porta em uma linha de template.

Por isso a primeira coisa que este processador faz é olhar `request.admin`: sem
crachá, ele devolve `{}` e a moldura não existe. `admin/503.html` sai por
`render_to_string` sem `request` e nunca chega aqui, o que fecha o caso pelo
outro lado.

## Por que o menu NÃO é o menu do site, e nunca vai ser

O menu do site (`/admin/menu/`) é DADO, mora no catálogo, muda quando o
mantenedor quiser e tem versões por página. Este aqui é ESTRUTURA: ele é a
lista das seções que a área administrativa tem, e ela só muda quando uma seção
nasce ou morre, o que é mudança de código. Ligar os dois faria o mantenedor
conseguir apagar a própria navegação do bastidor pelo bastidor.

## `SECOES` é escrita à mão, e o guarda é quem a impede de apodrecer

Mesma escolha de `ROTAS_PUBLICAS` em `apps/core/rodape.py`, pelo mesmo motivo:
o rótulo curto ("Pontos", "Menu do site") é uma decisão de linguagem para um
leigo, e não sai por regra de nenhum arquivo. O que sai por regra é a LISTA, e
`tests/test_moldura_do_admin.py` a compara com as seções que
`painel/mapa-do-site.json` declara — o mesmo mapa que já tem varredor no CI
provando que ele não mente sobre o roteamento. Seção nova na área reprova o PR
até ganhar nome aqui.

**O `href` sai de `reverse()`, nunca do endereço escrito no mapa.** O mapa diz
`/admin/escola/`, que é o endereço PÚBLICO; esta célula roda sob `SCRIPT_NAME` e
quem sabe montar o prefixo certo em toda máquina é o Django (`armadilhas/197`,
que é exatamente sobre somar prefixo com rota à mão). É também a regra escrita
no alto de `config/urls.py`: toda rota tem `name=`, e nenhum template escreve
caminho à mão.
"""

from __future__ import annotations

from django.urls import NoReverseMatch, get_script_prefix, reverse
from django.utils import timezone

# As SEÇÕES da área administrativa, na ordem em que o menu as desenha, e o nome
# curto de cada uma. A ordem é a de quem trabalha aqui, não a alfabética: as
# três primeiras são o dia a dia da escola, as três do meio são o que o site
# publica, e as três últimas são as ferramentas de olhar o sistema por dentro.
#
# Os rótulos são para um leigo, e três deles são deliberados:
#
#   · "Pontos", e não "Economia": a tela se chama "Os pontos da escola", e é
#     assim que o mantenedor fala dela.
#   · "Menu do site", e não "Menu": estando DENTRO do menu do admin, um item
#     chamado "Menu" seria a pergunta "menu de quê?" em toda visita.
#   · "Painel do sistema", e não "Painel": esta casa tem dois painéis, e chamar
#     um deles pelo nome curto já custou uma confusão ao mantenedor, contada no
#     comentário de `visao_geral.html`.
SECOES = (
    ("visao_geral", "Visão geral"),
    ("escola", "Escola"),
    ("caixa", "Caixa"),
    ("economia", "Pontos"),
    ("documentos_admin", "Documentos"),
    # "Livro", e não "Biblioteca": a tela guarda o livro que ele está
    # escrevendo, e é assim que ele fala dela. "Biblioteca" ao lado de
    # "Documentos" faria as duas parecerem a mesma coisa vista de dois ângulos
    # (04/09/2026).
    ("livro", "Livro"),
    ("menu_do_topo", "Menu do site"),
    ("perpetuo", "Lançamento"),
    # "Placar", e não "Metas": é UMA meta por vez (4DX), e o que a tela mostra
    # é o número contra o alvo, não uma lista (03/09/2026).
    ("placar", "Placar"),
    # A pauta de segunda-feira do painel de gestão (degrau 3, 03/09/2026): lê o
    # placar e termina no pedido para o robô. "Reunião", curto, porque é o que
    # o mantenedor abre toda segunda.
    ("reuniao", "Reunião"),
    ("avisos", "Avisos"),
    ("mapa_do_site", "Mapa do site"),
    ("painel", "Painel do sistema"),
)

# A CASA é a visão geral, e ela é o único item que casa por igualdade em vez de
# por prefixo: o endereço dela é prefixo de todos os outros. Ver
# `secoes_do_menu`.
#
# Está escrita pelo NOME, e não como `SECOES[0][0]`, desde 02/09/2026 — no dia
# em que a saída para o site passou a vir na frente dela, "o primeiro item" e
# "a capa" deixaram de ser a mesma coisa. Amarrar a regra à POSIÇÃO faria a
# capa parar de acender sozinha na próxima vez que alguém reordenasse o menu, e
# em silêncio.
CASA = "visao_geral"

# O endereço do site, cru, porque cada célula é dona do próprio prefixo e esta
# não monta endereço de ninguém. Mesma razão (e mesma forma) de
# `apps/core/rodape.py`: os guardas de prefixo (`armadilhas/029` e `/081`)
# precisam distinguir um endereço desta célula escrito à mão de um que é de
# outra por natureza, e a lista sai de quem o declara.
URL_DO_SITE = "/"

# O PRIMEIRO item do menu, e ele não é uma seção da administração: é a porta de
# SAÍDA. Escolha do mantenedor em 02/09/2026, no dia seguinte ao menu nascer:
# *"coloque o primeiro link do Menu do Admin para ser o link para a / home,
# acho que antes de Visão Geral"*.
#
# Duas coisas o separam do resto da lista, e as duas são o motivo de ele morar
# aqui fora em vez de dentro de `SECOES`:
#
# 1. **Ele não passa por `reverse()`, e não pode.** `/` é endereço de OUTRA
#    célula (a `funil`), que esta não conhece e não monta. Enfiá-lo em `SECOES`
#    estouraria em `NoReverseMatch` e o item sumiria da tela em silêncio, que é
#    exatamente o pulo que `secoes_do_menu` faz para link quebrado.
# 2. **O guarda mede `SECOES` contra o mapa desta área.** Um item de outra
#    célula ali dentro faria a conta não fechar, e a saída para o guarda seria
#    afrouxá-lo — que é como um portão morre.
#
# Ele nunca acende: você não está NO site enquanto está aqui dentro.
SAIDA_PARA_O_SITE = {"href": URL_DO_SITE, "rotulo": "Ver o site", "aqui": False}


def enderecos_de_outras_celulas() -> set:
    """Os links desta moldura que apontam para FORA desta célula."""
    return {URL_DO_SITE}


def secoes_do_menu(caminho_interno: str) -> list[dict]:
    """Os itens do menu: a saída para o site na frente, e as seções depois.

    Cada um sabe se é onde a pessoa está agora, e a saída nunca é.

    `caminho_interno` é o `request.path_info`: o caminho SEM o prefixo da
    célula. E a comparação DESCONTA o mesmo prefixo do que `reverse()` devolve,
    em vez de usar `request.path` cru, porque os dois lados precisam medir a
    mesma coisa em toda máquina. Em produção esta área mora sob
    `SCRIPT_NAME=/admin` e `reverse()` devolve `/admin/escola/`; na suíte, sem
    prefixo, ele devolve `/escola/`. Comparar `path` com `reverse()` funciona
    nas duas SÓ enquanto as duas pontas concordarem sobre o prefixo, e é
    exatamente aí que a `armadilhas/081` mora: o prefixo que `reverse()` lê é
    um valor de THREAD que o servidor preenche, não a variável de ambiente.
    Descontá-lo tira o assunto da frente: sobra `escola/` dos dois lados.

    A CASA casa por igualdade, e as outras por prefixo. O endereço dela, sem o
    prefixo da célula, é a string vazia: por prefixo ela ficaria acesa em toda
    página da área, e todo `startswith("")` é verdadeiro.

    Seção que não resolve é PULADA em vez de virar link quebrado: um item de
    menu que devolve 404 faz o mantenedor concluir que o site caiu. Ela não
    passa despercebida por isso: o guarda de `tests/test_moldura_do_admin.py`
    reprova o PR antes, e é lá que a ausência aparece alto.
    """
    prefixo = get_script_prefix()
    atual = caminho_interno.lstrip("/")
    # A saída para o site vem na frente da capa (ver `SAIDA_PARA_O_SITE`). É uma
    # cópia, e não a constante em si: o template recebe esta lista, e devolver o
    # objeto do módulo deixaria qualquer mexida futura vazar entre requisições.
    itens = [dict(SAIDA_PARA_O_SITE)]
    for nome, rotulo in SECOES:
        try:
            href = reverse(nome)
        except NoReverseMatch:
            continue
        rota = href[len(prefixo) :]
        aqui = atual == rota if nome == CASA else atual.startswith(rota)
        itens.append({"href": href, "rotulo": rotulo, "aqui": aqui})
    return itens


def rodape(ano: int) -> dict:
    """O que o rodapé desta área mostra. O texto mora no template; aqui, os dados.

    Ele NÃO traz mais o endereço do site: esse link subiu para a frente do menu
    em 02/09/2026, e mantê-lo aqui embaixo seria a mesma porta duas vezes na
    mesma tela — a repetição que o mantenedor mandou tirar no PR #891, poucas
    horas antes, quando ela era o `← Visão geral`.
    """
    return {"ano": ano}


def moldura_do_contexto(request) -> dict:
    """Processador de contexto: põe a moldura em TODA tela da administração.

    Sem crachá, devolve `{}`: ver "fail-closed" no cabeçalho deste arquivo.
    """
    if not getattr(request, "admin", None):
        return {}
    return {
        "menu_do_admin": secoes_do_menu(request.path_info),
        "rodape_do_admin": rodape(timezone.localdate().year),
    }
