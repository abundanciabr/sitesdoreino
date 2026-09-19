"""`/admin/escola/<curso>/sumario/` — colar o sumário do livro e o curso ganhar
a mesma estrutura.

Sem esta tela as 34 encomendas do curso ficam com número e mais nada, e todo
verificador que vier depois não tem o que verificar. Ela é o degrau que enche o
esqueleto que `semear_esqueleto` deixa de propósito vazio.

## Por que uma TELA, e não um arquivo no repositório

O sumário é obra NÃO LANÇADA do mantenedor e este repositório é PÚBLICO
([INV-CUR-C2], `armadilhas/331`). Ele não entra aqui: nem como arquivo, nem
como semente, nem dentro de um teste. Entra por esta área de colar, e o que
fica guardado é o resultado (as encomendas, na `cursos`), nunca o texto colado.
**Esta tela não guarda nada**, nem entre o PREVER e o IMPORTAR: o texto volta
para a área de colar dentro da própria página, e o arquivo continua sendo dele.
O teste desta tela usa um sumário de MENTIRA, com a mesma forma e conteúdo
inventado.

## A regra que não se negocia: campo escrito nunca é sobrescrito

Campo vazio o importador preenche; campo que já tem texto ele preserva, **e diz
na prévia que preservou**. Um importador que apaga o que o mantenedor escreveu
é a forma mais rápida de perder meses de trabalho que só existem naquele banco.
Por isso a leitura vem sempre antes da escrita, encomenda por encomenda, e a
encomenda em que nada mudaria não é gravada: sem isso, importar duas vezes
subiria a versão das 34 sem trocar uma letra.

## Dois botões, e o primeiro não escreve nada

PREVER lê o texto colado, lê o que está gravado e mostra, encomenda por
encomenda, **o que vai ser preenchido** e **o que vai ficar como está**. Nada
vai para a porta. IMPORTAR faz a mesma leitura e grava pela porta de máquina
(`putLesson` do contrato congelado), nunca no banco direto.

É um formulário simples com dois botões de enviar, e por isso não há uma linha
de script: a política de segurança desta área exige um hash na CSP para cada
script embutido (`armadilhas/199`), e um POST por gesto deixa a tela mostrando
sempre o que está de fato gravado.

## As peças se casam pelo NÚMERO, não pelo nome

No livro a peça 13 muda de nome por Parte ("Crítica de atelier" nas Partes I e
II, "Revisão de estúdio" na III), a peça 12 é ora "Regra" ora "Nota sobre o
Padrão", e a 15 é "Página 0", "Página 1" ou "Página B". O NOME é decoração; o
número de 1 a 16 é a ordem canônica das peças, que é a mesma do contrato
(`TipoDePeca`) e a mesma que o próprio sumário declara no cabeçalho dele. Casar
pelo número resolve as três variações de uma vez, sem um mapa de apelidos que
envelheceria na primeira edição do livro. O nome lido continua aparecendo na
prévia, ao lado do campo em que ele caiu: é assim que se confere.

## Duas linhas do sumário NÃO TÊM PORTA, e a prévia diz isso na cara

O título entre aspas de cada encomenda e o título de cada Boss são lidos daqui
e **não podem ser gravados**: `titulo_exibido` está fora do corpo de
`putLesson` por contrato ("Número, ordem, título, bloco, estado, versão e data
de publicação não entram, e mandá-los é 422"), e `boss_titulo` não aparece em
nenhuma das onze operações de `contracts/cursos.openapi.yaml`. O contrato é
congelado e é de outra célula: abrir porta para eles é trabalho da `cursos`,
não desta tela. Em vez de gravar em silêncio num campo que ninguém pediu, a
prévia lista os dois e diz por que ficaram de fora.
"""

from __future__ import annotations

import re

from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from apps.auditoria.models import Registro

from .aulas import (
    NOME_DA_PECA,
    PECAS,
    SEQUENCIA,
    CursosClient,
    _endereco,
    _falha,
    _sem_site,
    _site_desta_requisicao,
)
from .views import _auditar

TELA = "admin/escola_sumario.html"

#: As 16 peças da anatomia na ordem em que o sumário as numera, que é a ordem
#: canônica do contrato. São as da categoria `SEQUENCIA`, e só elas: as duas
#: internas (`roteiro`, `guia_do_mentor`) e a vídeo-aula em texto ficam de fora,
#: o sumário não as tem, e o importador nunca as toca. Numerar por exclusão ("as
#: que não são internas") daria 17 no dia em que uma peça não interna nascesse
#: fora da anatomia, e foi exatamente o que aconteceu.
PECAS_NUMERADAS = tuple(t for t, _, categoria in PECAS if categoria == SEQUENCIA)

#: A peça 1 ("O pedido") traz, no sumário, o NOME DO CLIENTE e nada mais ("o
#: Mentor", "Téo", "o cliente sem nome"). Ela é a única cujo texto próprio não
#: vai para a peça: vai para o campo `cliente` da encomenda, que é onde esse
#: fato mora no modelo. Escrever nos dois seria o mesmo fato em dois lugares.
PECA_DO_CLIENTE = 1

#: `cliente` é `maxLength: 120` no contrato. O que passar disso não viaja: a
#: porta recusaria a encomenda INTEIRA por causa de uma linha, e é melhor a
#: prévia dizer que aquela ficou de fora do que perder as outras quinze.
TETO_DO_CLIENTE = 120


# ---------------------------------------------------------------------------
# O INTERPRETADOR — texto colado para dentro, estrutura para fora
# ---------------------------------------------------------------------------
# As cinco formas de linha que importam, medidas no sumário em 06/09/2026. As
# demais (a abertura, o aparato, os Marcos, as Bancas, as molduras) não casam
# com nenhuma e são ignoradas, que é o certo: elas não têm campo para onde ir.
BLOCO = re.compile(r"^═+ BLOCO ([A-L]) ")
BOSS = re.compile(r"^\s*── BOSS ([A-L]) — (.+?)\s*─*\s*$")
ENCOMENDA = re.compile(r'^(E\d{2}) · "(.*?)"')
BONUS = re.compile(r'^ENCOMENDA BÔNUS · "(.*?)"')

#: A linha de peça: o número alinhado à direita numa faixa de três colunas, dois
#: espaços, e o resto (`  1  O pedido — o Mentor`, ` 16  Dicionário · Cartão`).
#: A faixa de três é o que separa uma peça de uma linha de continuação.
PECA = re.compile(r"^(?P<recuo> *)(?P<n>\d{1,2})  (?P<resto>\S.*)$")
LARGURA_DO_NUMERO = 3

#: Onde começa o texto de uma peça, e portanto a coluna das linhas de
#: continuação dela: as sub-linhas do "Eu faço" e as figuras a mais do "Par de
#: comparação" recuam além dela, e esse recuo a mais é preservado.
COLUNA_DO_TEXTO = 5

#: O que separa o NOME da peça do que é próprio dela naquela encomenda.
SEPARADOR = " — "


def _peca_do_numero(n: int) -> str:
    """O tipo do contrato para o número de 1 a 16 do sumário, ou vazio."""
    return PECAS_NUMERADAS[n - 1] if 1 <= n <= len(PECAS_NUMERADAS) else ""


def _partir_a_peca(resto: str) -> "tuple[str, str]":
    """`O pedido — o Mentor` vira `("O pedido", "o Mentor")`.

    Peça sem travessão (`13  Crítica de atelier`) é nome sem texto próprio: no
    sumário ela existe, e naquela encomenda não tem nada de particular.
    """
    nome, _, proprio = resto.partition(SEPARADOR)
    return nome.strip(), proprio.strip()


def _titulo_do_boss(resto: str) -> str:
    """O título do Boss: o que está entre aspas, ou a frase antes da medalha.

    Metade dos Bosses do livro tem título entre aspas (`"O Diorama" · Medalha:
    Piloto de Viewport`) e a outra metade é uma frase (`a Encomenda da Semana
    real · Título: Modelador Nível 1`). Nos dois casos, o que vem depois do
    ponto do meio é a medalha ou o título de nível, e não o nome do Boss.
    """
    entre_aspas = re.match(r'^"(.*?)"', resto)
    if entre_aspas:
        return entre_aspas.group(1).strip()
    return resto.split(" · ")[0].strip()


def interpretar(texto: str) -> dict:
    """O sumário colado, em estrutura. Sem rede, sem banco, sem Django.

    Devolve `{"encomendas": [...], "bosses": [(letra, titulo), ...]}`. Cada
    encomenda traz `numero` (`E00`..`E32`, `EB`), `titulo` (o que está entre
    aspas), `pecas` (tipo do contrato para o texto próprio daquela peça),
    `nomes` (o nome com que o sumário chamou cada peça, para a prévia conferir),
    `cliente` (o texto próprio da peça 1) e `fora_da_anatomia` (peça numerada
    além da 16, que não tem campo para onde ir).

    Linha que não casa com nenhuma das formas é ignorada: a abertura, o
    aparato, os Marcos e as Bancas não têm campo. Texto que não é um sumário
    devolve nenhuma encomenda, e a tela diz isso em vez de gravar no escuro.
    """
    encomendas: list[dict] = []
    bosses: list[tuple[str, str]] = []
    atual: dict | None = None
    aberta = ""
    linhas_da_peca: list[str] = []

    def fechar() -> None:
        nonlocal aberta, linhas_da_peca
        if atual is not None and aberta:
            texto_da_peca = _sem_a_margem(linhas_da_peca)
            if texto_da_peca:
                atual["pecas"][aberta] = texto_da_peca
        aberta, linhas_da_peca = "", []

    for linha in texto.replace("\r\n", "\n").split("\n"):
        casou = ENCOMENDA.match(linha)
        if casou:
            fechar()
            atual = _nova_encomenda(casou.group(1), casou.group(2))
            encomendas.append(atual)
            continue

        casou = BONUS.match(linha)
        if casou:
            fechar()
            atual = _nova_encomenda("EB", casou.group(1))
            encomendas.append(atual)
            continue

        casou = BOSS.match(linha)
        if casou:
            fechar()
            atual = None
            bosses.append((casou.group(1), _titulo_do_boss(casou.group(2))))
            continue

        if BLOCO.match(linha):
            fechar()
            atual = None
            continue

        if atual is None:
            continue

        casou = PECA.match(linha)
        recuo_do_numero = (
            len(casou.group("recuo")) + len(casou.group("n")) if casou else -1
        )
        if recuo_do_numero == LARGURA_DO_NUMERO:
            fechar()
            aberta, primeira = _guardar_a_peca(
                atual, int(casou.group("n")), casou.group("resto")
            )
            linhas_da_peca = [" " * COLUNA_DO_TEXTO + primeira] if primeira else []
            continue

        recuo = len(linha) - len(linha.lstrip(" "))
        if linha.strip() and recuo >= COLUNA_DO_TEXTO:
            if aberta:
                linhas_da_peca.append(" " * recuo + linha.strip())
            continue

        # Linha em branco, moldura, ou texto sem recuo: a peça aberta acaba aqui.
        fechar()

    fechar()
    return {"encomendas": encomendas, "bosses": bosses}


def _sem_a_margem(linhas: list) -> str:
    """As linhas de uma peça sem a margem comum a todas, e com o resto do recuo.

    O sumário desenha um contorno: o texto próprio da peça começa numa coluna,
    e as sub-linhas dela (as seções numeradas do "Eu faço", as figuras a mais
    do "Par de comparação") recuam além. Tirar SÓ a margem que todas dividem
    preserva esse contorno e não deixa recuo morto na frente do texto quando a
    peça começa direto nas sub-linhas, que é o caso do "Eu faço".
    """
    if not linhas:
        return ""
    margem = min(len(linha) - len(linha.lstrip(" ")) for linha in linhas)
    return "\n".join(linha[margem:] for linha in linhas).strip()


def _nova_encomenda(numero: str, titulo: str) -> dict:
    return {
        "numero": numero,
        "titulo": titulo.strip(),
        "cliente": "",
        "pecas": {},
        "nomes": {},
        "fora_da_anatomia": [],
    }


def _guardar_a_peca(encomenda: dict, n: int, resto: str) -> "tuple[str, str]":
    """Guarda o nome lido da peça e devolve `(tipo aberto, primeira linha)`.

    A peça 1 não abre nada: o texto próprio dela é o cliente, e vai para o
    campo `cliente` da encomenda. Número além da 16 não tem campo, e é contado
    em voz alta em vez de sumir.
    """
    nome, proprio = _partir_a_peca(resto)
    tipo = _peca_do_numero(n)
    if not tipo:
        encomenda["fora_da_anatomia"].append(f"{n} {nome}".strip())
        return "", ""
    encomenda["nomes"][tipo] = nome
    if n == PECA_DO_CLIENTE:
        encomenda["cliente"] = proprio
        return "", ""
    return tipo, proprio


# ---------------------------------------------------------------------------
# O CASAMENTO — o que seria preenchido, e o que ficaria como está
# ---------------------------------------------------------------------------
def _escrito(valor) -> bool:
    """Um campo conta como ESCRITO quando tem qualquer coisa além de espaço.

    Espaço solto não é obra: para quem olha a tela aquele campo está vazio, e
    recusar preenchê-lo obrigaria o mantenedor a caçar o espaço em 34 telas.
    """
    return bool(str(valor or "").strip())


def _rotulo_da_peca(encomenda: dict, tipo: str) -> str:
    """ "Peça 7: Eu faço" — e, quando difere, o nome que o sumário usou.

    O sumário chama a mesma peça de nomes diferentes conforme a Parte, e é
    justamente aí que alguém precisa ver as duas palavras lado a lado para
    confiar que a linha caiu no lugar certo.
    """
    do_contrato = NOME_DA_PECA.get(tipo, tipo)
    do_sumario = encomenda["nomes"].get(tipo, "")
    if do_sumario and do_sumario.casefold() != do_contrato.casefold():
        do_contrato = f"{do_contrato} (no sumário: {do_sumario})"
    if tipo in PECAS_NUMERADAS:
        return f"Peça {PECAS_NUMERADAS.index(tipo) + 1}: {do_contrato}"
    return do_contrato


def casar(encomenda: dict, aula: dict) -> dict:
    """O que o importador FARIA nesta encomenda, sem fazer nada.

    Devolve `preencher` (o que entra), `preservar` (o que já tem texto e fica
    intacto), `nao_coube` (o que o contrato não aceita do jeito que está) e
    `corpo` (o corpo de `putLesson`, montado do que está gravado com só os
    vazios trocados). `corpo` é `None` quando nada mudaria, e é assim que a
    encomenda sem novidade não é gravada nem sobe de versão.
    """
    preencher: list[dict] = []
    preservar: list[dict] = []
    nao_coube: list[str] = []

    cliente = str(aula.get("cliente") or "")
    if encomenda["cliente"]:
        if _escrito(cliente):
            preservar.append({"campo": "Cliente", "atual": cliente})
        elif len(encomenda["cliente"]) > TETO_DO_CLIENTE:
            nao_coube.append(
                f"O cliente da peça 1 tem {len(encomenda['cliente'])} letras, e a "
                f"sala de aula aceita no máximo {TETO_DO_CLIENTE} nesse campo."
            )
        else:
            preencher.append({"campo": "Cliente", "novo": encomenda["cliente"]})
            cliente = encomenda["cliente"]

    # As peças vêm sempre as 18, na ordem canônica (promessa do contrato). O
    # casamento percorre o que a PORTA mandou, e não a lista daqui: peça que a
    # porta não mandar não é inventada, e peça a mais dela viaja de volta
    # intacta em vez de desaparecer na gravação.
    pecas = []
    for peca in aula.get("pecas") or []:
        if not isinstance(peca, dict):
            continue
        tipo = str(peca.get("tipo") or "")
        texto = str(peca.get("texto") or "")
        do_sumario = encomenda["pecas"].get(tipo, "")
        if do_sumario:
            rotulo = _rotulo_da_peca(encomenda, tipo)
            if _escrito(texto):
                preservar.append({"campo": rotulo, "atual": texto})
            else:
                preencher.append({"campo": rotulo, "novo": do_sumario})
                texto = do_sumario
        pecas.append({"tipo": tipo, "texto": texto})

    if not preencher:
        return {
            "preencher": [],
            "preservar": preservar,
            "nao_coube": nao_coube,
            "corpo": None,
        }

    return {
        "preencher": preencher,
        "preservar": preservar,
        "nao_coube": nao_coube,
        # O corpo INTEIRO de `putLesson`, montado do que está gravado: a porta
        # substitui a encomenda toda, então o que não vem no corpo se perde.
        "corpo": {
            "pedido": str(aula.get("pedido") or ""),
            "cliente": cliente,
            "instrumento": aula.get("instrumento") or None,
            "minimo": str(aula.get("minimo") or ""),
            "aceito_quando": [str(c) for c in (aula.get("aceito_quando") or [])],
            "quiz": [q for q in (aula.get("quiz") or []) if isinstance(q, dict)],
            "video_url": str(aula.get("video_url") or ""),
            "e_boss": bool(aula.get("e_boss")),
            "banca_nivel": aula.get("banca_nivel"),
            "pecas": pecas,
            "pausas": [p for p in (aula.get("pausas") or []) if isinstance(p, dict)],
        },
    }


# ---------------------------------------------------------------------------
# A TELA
# ---------------------------------------------------------------------------
def _ler_o_curso(cliente, site_id: str, curso: str, encomendas: list):
    """O que está gravado hoje em cada encomenda que o sumário menciona.

    Devolve `(linhas, falha)`. Encomenda que a porta não souber ler entra na
    lista dizendo isso e NÃO é gravada: gravar sem ter lido o que já estava lá
    é exatamente o que apagaria obra.
    """
    desfecho, lista = cliente.aulas(site_id, curso)
    if desfecho != CursosClient.OK:
        return [], desfecho
    existem = {str(a.get("numero") or "") for a in (lista or []) if isinstance(a, dict)}

    linhas = []
    for encomenda in encomendas:
        numero = encomenda["numero"]
        linha = {
            "encomenda": encomenda,
            "numero": numero,
            "titulo": encomenda["titulo"],
        }
        if numero not in existem:
            linhas.append(linha | {"ausente": True})
            continue
        desfecho, aula = cliente.aula(site_id, curso, numero)
        if desfecho != CursosClient.OK:
            linhas.append(linha | {"nao_li": _falha(desfecho)["titulo"]})
            continue
        linhas.append(linha | casar(encomenda, aula or {}))
    return linhas, ""


def _desenhar(request, curso: str, colado: str, contexto: dict, status: int = 200):
    return render(
        request,
        TELA,
        {
            "admin": request.admin,
            "curso": curso,
            "colado": colado,
            "url_da_lista": _endereco("escola_aulas", curso, None),
            "url_de_prever": _endereco("escola_sumario_prever", curso, None),
            "url_de_importar": _endereco("escola_sumario_importar", curso, None),
        }
        | contexto,
        status=status,
    )


def _preparar(request, curso: str, colado: str):
    """A leitura que PREVER e IMPORTAR fazem igual.

    Devolve `(preparado, resposta)`: exatamente um dos dois é `None`. A
    resposta pronta é a própria tela, e existe quando não há o que fazer — sem
    site, sem texto, texto que não é um sumário, ou a sala de aula fora do ar.
    """
    site = _site_desta_requisicao(request)
    if site is None:
        return None, _sem_site(request)

    if not colado.strip():
        return None, _desenhar(
            request,
            curso,
            colado,
            {
                "erro": "Cole o sumário na caixa antes de apertar o botão. Nada "
                "foi lido e nada foi gravado."
            },
            status=400,
        )

    lido = interpretar(colado)
    if not lido["encomendas"]:
        return None, _desenhar(
            request,
            curso,
            colado,
            {
                "erro": "Não achei nenhuma encomenda neste texto. Cada uma começa "
                'com o número e o título entre aspas, assim: E00 · "Bem-vindo ao '
                'estúdio." Confira se você colou o sumário inteiro. Nada foi '
                "gravado."
            },
            status=400,
        )

    linhas, falha = _ler_o_curso(CursosClient(), site["id"], curso, lido["encomendas"])
    if falha:
        return None, _desenhar(
            request, curso, colado, {"falha_da_sala": _falha(falha)}, status=503
        )
    return (site, linhas, lido), None


def _resumo(linhas: list, lido: dict) -> dict:
    """Os números do alto da tela, contados das linhas — nunca guardados."""
    return {
        "linhas": linhas,
        "bosses": lido["bosses"],
        "encomendas_lidas": len(lido["encomendas"]),
        "a_preencher": sum(len(linha.get("preencher") or []) for linha in linhas),
        "a_preservar": sum(len(linha.get("preservar") or []) for linha in linhas),
        "ausentes": [linha["numero"] for linha in linhas if linha.get("ausente")],
        "nao_lidas": [linha["numero"] for linha in linhas if linha.get("nao_li")],
    }


@require_GET
def sumario(request, curso: str):
    """A área de colar, vazia. Nenhuma ida à porta: aqui ainda não há texto."""
    return _desenhar(request, curso, "", {})


@require_POST
def sumario_prever(request, curso: str):
    """Lê o texto colado e mostra o que aconteceria. NÃO grava nada."""
    colado = (request.POST.get("sumario") or "").replace("\r\n", "\n")
    preparado, resposta = _preparar(request, curso, colado)
    if resposta is not None:
        return resposta
    _, linhas, lido = preparado
    return _desenhar(request, curso, colado, _resumo(linhas, lido) | {"previu": True})


@require_POST
def sumario_importar(request, curso: str):
    """Grava, pela porta, só os campos que estão vazios hoje.

    Encomenda em que nada mudaria não é enviada: sem isso, importar duas vezes
    subiria a versão das 34 sem trocar uma letra. Encomenda que não foi lida
    também não é enviada, e a tela diz quais foram.
    """
    colado = (request.POST.get("sumario") or "").replace("\r\n", "\n")
    preparado, resposta = _preparar(request, curso, colado)
    if resposta is not None:
        return resposta
    site, linhas, lido = preparado

    cliente = CursosClient()
    gravadas, recusadas = 0, []
    for linha in linhas:
        if not linha.get("corpo"):
            continue
        numero = linha["numero"]
        desfecho, corpo = cliente.gravar_aula(site["id"], curso, numero, linha["corpo"])
        if desfecho == CursosClient.OK:
            gravadas += 1
            linha["gravada"] = int((corpo or {}).get("versao") or 0)
            _auditar(
                request,
                Registro.EDITAR_AULA,
                numero,
                Registro.OK,
                f"sumario: {len(linha['preencher'])} campo(s) vazio(s) preenchido(s)",
            )
            continue
        linha["recusada"] = (
            "A sala de aula não aceitou o texto desta encomenda."
            if desfecho == CursosClient.RECUSADO
            else _falha(desfecho)["titulo"]
        )
        recusadas.append(numero)
        _auditar(
            request,
            Registro.EDITAR_AULA,
            numero,
            (
                Registro.RECUSADO_PELA_CELULA
                if desfecho == CursosClient.RECUSADO
                else Registro.NAO_RESPONDEU
            ),
            f"sumario: {desfecho}",
        )

    return _desenhar(
        request,
        curso,
        colado,
        _resumo(linhas, lido)
        | {"importou": True, "gravadas": gravadas, "recusadas": recusadas},
    )
