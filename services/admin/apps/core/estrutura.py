"""`/admin/escola/<curso>/estrutura/` — colar os módulos e as aulas de um curso.

Um curso novo nasce sem uma aula sequer: `createCourse` cria a sala vazia de
propósito, e sem esta tela encher o esqueleto exigiria um bloco de colar no
servidor. O mantenedor pediu o contrário, com estas palavras: *"quero criar uma
estrutura que sirva para vários cursos e não apenas para um único curso"*
(`docs/decisoes/DECISAO-a-sala-serve-varios-cursos.md` §4). É por aqui que ele
vai criar as aulas do "Primeiros Dólares com Roblox" para os alunos que já
estão matriculados.

## O que esta tela NÃO é

Ela não é o editor. Aqui entram o esqueleto e o nome de cada aula; o texto de
cada uma continua entrando pelo editor, uma a uma, e por outra porta. A
fronteira é a do próprio contrato: `putCourseStructure` mexe em bloco, ordem,
parte, Boss e Banca, e **nunca toca obra** (pedido, cliente, peças, pausas,
quiz, vídeo, estado e versão ficam como estão).

## Dois botões, e o primeiro não escreve nada

PREVER lê o texto colado, lê a estrutura que existe hoje (`listLessons`) e
mostra, aula por aula, o que seria criado, o que ficaria intacto e o que
sumiria. Nenhuma escrita acontece. IMPORTAR faz a mesma leitura e manda tudo
numa ida só a `putCourseStructure`, que reconcilia dentro de UMA transação: ou
a estrutura inteira entra, ou nada entra.

É um formulário com dois botões de enviar, e por isso não há uma linha de
script: a política de segurança desta área exige um hash na CSP para cada
script embutido (`armadilhas/199`), e um POST por gesto deixa a tela mostrando
sempre o que está de fato gravado.

## O texto colado não fica guardado em lugar nenhum

Mesma regra do sumário do livro: o que fica é o resultado, na `cursos`. O texto
volta para a caixa dentro da própria página, e o arquivo continua sendo dele.

## O título que ele já escreveu não se sobrescreve, e a prévia diz isso

O contrato promete: o título da aula só entra onde está VAZIO. Uma aula que já
tem título mantém o dele mesmo que o texto colado traga outro, e a prévia
mostra os dois lado a lado, dizendo qual fica. Um importador que apaga o que o
mantenedor escreveu é a forma mais rápida de perder trabalho que só existe
naquele banco.

## Por que a Banca viaja de volta, mesmo sem ninguém a ter digitado

A estrutura é a FONTE da Banca, por contrato ("corrige bloco, ordem, parte,
Boss e Banca do que já existe"). Esta tela não tem campo de Banca, e mandar a
estrutura sem ela zeraria o nível de Banca de toda aula que já o tivesse, em
silêncio e sem nada na tela dizendo. Por isso a leitura que a prévia já faz
serve a duas coisas: comparar, e devolver a Banca de cada aula que existe
exatamente como está hoje. Aula nova nasce sem Banca, que é o que ela seria de
qualquer jeito.

## As letras são POSICIONAIS, e é por isso que o nome do módulo sempre viaja

O bloco casa pela letra, e a letra é a posição: nascendo um módulo na frente, o
que era o B vira o C. Se o nome não viajasse junto, o nome antigo ficaria
grudado na letra e o módulo inteiro trocaria de nome sozinho. Por isso `nome`
vai SEMPRE preenchido a partir do texto colado. Já `boss_titulo` só viaja
quando a linha do módulo o traz: sem ele o campo vai NULO, que no contrato quer
dizer "não mexa no que está gravado".
"""

from __future__ import annotations

import re
import string

from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from apps.auditoria.models import Registro

from .aulas import CursosClient, _endereco, _falha, _site_desta_requisicao
from .cursos import _frase
from .views import _auditar

TELA = "admin/escola_estrutura.html"

#: `maxLength: 120` no contrato, para o título da aula, o nome do bloco e o
#: título do Boss. O que passa disso a porta recusaria com um 422 sobre a
#: estrutura INTEIRA, e nada entraria: é melhor a tela nomear a linha.
TETO = 120

#: `^[A-Z0-9]{1,3}$` em `AulaDaEstruturaSchema`. O que o mantenedor digitar em
#: minúsculo vira maiúsculo aqui: `e01` e `E01` são a mesma aula para ele.
NUMERO = re.compile(r"^[A-Z0-9]{1,3}$")

#: `^[A-Z]$` em `BlocoDaEstruturaSchema`: as letras acabam no vigésimo sexto
#: módulo, e o vigésimo sétimo não tem letra para receber.
LETRAS = string.ascii_uppercase

#: `## Parte 2` abre a Parte seguinte do livro. `ParteDoCurso` é 1, 2 ou 3.
PARTE = re.compile(r"^Parte\s+(\d+)$", re.IGNORECASE)
PARTES = (1, 2, 3)

#: ` | Boss: O Diorama` no fim da linha do módulo. Sem isso o título do Boss vai
#: NULO, e o que está gravado fica como está.
BOSS_DO_MODULO = re.compile(r"^(?P<nome>.*?)\s*\|\s*Boss:\s*(?P<titulo>.*)$")

#: `[boss]` no fim da linha da aula marca o Boss do módulo.
BOSS_DA_AULA = re.compile(r"^(?P<titulo>.*?)\s*\[boss\]$", re.IGNORECASE)

#: O que a prévia diz de cada aula. Três destinos diferentes, e confundi-los
#: mandaria o mantenedor para o lado errado: um pede que ele confira o nome que
#: colou, outro avisa que o nome colado não vai valer.
CRIAR = "criar"
PREENCHER = "preencher"
PRESERVAR = "preservar"


# ---------------------------------------------------------------------------
# O INTERPRETADOR — texto colado para dentro, estrutura para fora
# ---------------------------------------------------------------------------
def interpretar(texto: str) -> "tuple[list, list]":
    """O texto colado, em blocos e aulas. Sem rede, sem banco, sem Django.

    Devolve `(blocos, erros)`. Cada bloco traz `letra` (A, B, C... pela ordem),
    `parte`, `nome`, `boss_titulo` (`None` quando a linha não o trouxe) e
    `aulas`, cada uma com `numero`, `titulo` e `e_boss`.

    Os erros são TODOS os que o texto tem, cada um com o número da linha e o
    que corrigir. Um de cada vez obrigaria o mantenedor a colar, corrigir e
    colar de novo, uma linha por vez, num texto de trinta módulos. Havendo
    qualquer erro, nada é gravado: a lista de erros é a resposta inteira.
    """
    blocos: list[dict] = []
    erros: list[dict] = []
    parte = 1
    onde_apareceu: dict[str, int] = {}
    #: Os modulos que TENTARAM ter aula, mesmo que a linha tenha dado erro. Sem
    #: isto, uma unica linha de aula torta acusa DOIS erros: o dela, e um
    #: "modulo sem nenhuma aula" que so existe porque a primeira falhou. O
    #: mantenedor consertaria a linha e o segundo erro sumiria sozinho, que e a
    #: forma mais rapida de ele parar de confiar na lista de erros.
    com_linha_de_aula: set[int] = set()

    for n, bruta in enumerate(texto.replace("\r\n", "\n").split("\n"), start=1):
        linha = bruta.strip()
        if not linha:
            continue

        if linha.startswith("##"):
            lida, erro = _parte_da_linha(linha[2:].strip())
            if erro:
                erros.append({"linha": n, "frase": erro})
                continue
            parte = lida
            continue

        if linha.startswith("#"):
            bloco, erro = _modulo_da_linha(linha[1:].strip(), parte, n)
            if erro:
                erros.append({"linha": n, "frase": erro})
                continue
            blocos.append(bloco)
            continue

        aula, erro = _aula_da_linha(linha)
        com_linha_de_aula.add(len(blocos) - 1)
        if erro:
            erros.append({"linha": n, "frase": erro})
            continue
        if not blocos:
            erros.append(
                {
                    "linha": n,
                    "frase": f'A aula "{aula["numero"]}" está antes do primeiro '
                    "módulo, e toda aula mora dentro de um. Ponha uma linha de "
                    "módulo acima dela, começando com #.",
                }
            )
            continue
        antes = onde_apareceu.get(aula["numero"])
        if antes:
            erros.append(
                {
                    "linha": n,
                    "frase": f'O número "{aula["numero"]}" já foi usado na linha '
                    f"{antes}. Cada aula do curso tem um número só dela: troque "
                    "um dos dois.",
                }
            )
            continue
        onde_apareceu[aula["numero"]] = n
        blocos[-1]["aulas"].append(aula)

    erros.extend(_erros_do_conjunto(blocos, com_linha_de_aula))
    for i, bloco in enumerate(blocos):
        bloco["letra"] = LETRAS[i] if i < len(LETRAS) else ""
    return blocos, sorted(erros, key=lambda erro: erro["linha"])


def _parte_da_linha(resto: str) -> "tuple[int, str]":
    """`## Parte 2` abre a Parte seguinte. Devolve `(parte, erro)`."""
    casou = PARTE.match(resto)
    if not casou:
        return 0, (
            "Esta linha começa com ## e aí eu só entendo Parte 1, Parte 2 ou "
            "Parte 3. Se você queria abrir um módulo, use um # só."
        )
    parte = int(casou.group(1))
    if parte not in PARTES:
        return 0, (
            f"O livro tem três Partes, e esta linha pede a Parte {parte}. "
            "Escreva Parte 1, Parte 2 ou Parte 3."
        )
    return parte, ""


def _modulo_da_linha(resto: str, parte: int, linha: int) -> "tuple[dict, str]":
    """`# Módulo 1: Começando | Boss: A Cadeira` vira um bloco. `(bloco, erro)`.

    `boss_titulo` sai `None` quando a linha não traz o Boss, e é de propósito:
    nulo, no contrato, quer dizer não mexer no que está gravado. Vazio APAGARIA
    o título que alguém escreveu por outra tela.
    """
    boss_titulo = None
    casou = BOSS_DO_MODULO.match(resto)
    if casou:
        resto = casou.group("nome").strip()
        boss_titulo = casou.group("titulo").strip()
        if len(boss_titulo) > TETO:
            return {}, (
                f"O título do Boss deste módulo tem {len(boss_titulo)} letras, e "
                f"cabem no máximo {TETO}. Encurte-o."
            )
    if not resto:
        return {}, (
            "Esta linha abre um módulo sem nome. Escreva o nome depois do #, "
            "assim: # Módulo 1: Comece por aqui"
        )
    if len(resto) > TETO:
        return {}, (
            f"O nome deste módulo tem {len(resto)} letras, e cabem no máximo "
            f"{TETO}. Encurte-o."
        )
    return {
        "letra": "",
        "parte": parte,
        "nome": resto,
        "boss_titulo": boss_titulo,
        "aulas": [],
        "linha": linha,
    }, ""


def _aula_da_linha(linha: str) -> "tuple[dict, str]":
    """`01 Boas-vindas ao curso [boss]` vira uma aula. `(aula, erro)`."""
    numero, _, titulo = linha.partition(" ")
    numero = numero.upper()
    if not NUMERO.match(numero):
        return {}, (
            "Não reconheci esta linha. Uma aula começa pelo número dela e um "
            "espaço, assim: 01 Boas-vindas ao curso. Um módulo começa com #. O "
            "número tem no máximo três letras ou algarismos."
        )
    e_boss = False
    casou = BOSS_DA_AULA.match(titulo.strip())
    if casou:
        titulo, e_boss = casou.group("titulo"), True
    titulo = titulo.strip()
    if not titulo:
        return {}, (
            f'A aula "{numero}" está sem nome. Escreva o nome dela depois do '
            "número, assim: 01 Boas-vindas ao curso"
        )
    if len(titulo) > TETO:
        return {}, (
            f'O nome da aula "{numero}" tem {len(titulo)} letras, e cabem no '
            f"máximo {TETO}. Encurte-o."
        )
    return {"numero": numero, "titulo": titulo, "e_boss": e_boss}, ""


def _erros_do_conjunto(blocos: list, com_linha_de_aula: set) -> list:
    """Os erros que só se enxergam com o texto inteiro lido.

    A linha citada é a do módulo, e não a última do arquivo: é lá que o
    mantenedor precisa ir mexer. Módulo cuja única linha de aula deu erro NÃO
    aparece aqui: o erro dele é o da linha, e acusar os dois faria um sumir
    sozinho quando o outro fosse corrigido.
    """
    erros = [
        {
            "linha": bloco["linha"],
            "frase": f'O módulo "{bloco["nome"]}" ficou sem nenhuma aula. Todo '
            "módulo tem pelo menos uma: escreva as aulas dele abaixo da linha "
            "do #, ou apague o módulo.",
        }
        for i, bloco in enumerate(blocos)
        if not bloco["aulas"] and i not in com_linha_de_aula
    ]
    if len(blocos) > len(LETRAS):
        erros.append(
            {
                "linha": blocos[len(LETRAS)]["linha"],
                "frase": f"Este texto tem {len(blocos)} módulos, e um curso cabe "
                f"em {len(LETRAS)}: cada módulo é uma letra, de A a Z. Junte "
                "módulos, ou divida o curso em dois.",
            }
        )
    return erros


# ---------------------------------------------------------------------------
# O CASAMENTO — o que a importação faria, sem fazer nada
# ---------------------------------------------------------------------------
def casar(blocos: list, existentes: list) -> "tuple[list, list]":
    """O que aconteceria com cada aula, e quais sumiriam. Nada é gravado.

    Devolve `(modulos, a_apagar)`. Cada aula ganha `acao` (criar, preencher ou
    preservar) e `titulo_que_fica`, que é o nome com que ela vai FICAR: o do
    texto colado quando ela nasce ou está sem nome, e o que já está gravado
    quando o mantenedor já escreveu um.
    """
    hoje = {
        str(aula.get("numero") or ""): aula
        for aula in existentes
        if isinstance(aula, dict)
    }
    na_estrutura = {aula["numero"] for bloco in blocos for aula in bloco["aulas"]}

    modulos = []
    for bloco in blocos:
        aulas = []
        for aula in bloco["aulas"]:
            ja = hoje.get(aula["numero"])
            gravado = str((ja or {}).get("titulo_exibido") or "").strip()
            if ja is None:
                acao, fica = CRIAR, aula["titulo"]
            elif gravado:
                acao, fica = PRESERVAR, gravado
            else:
                acao, fica = PREENCHER, aula["titulo"]
            aulas.append(aula | {"acao": acao, "titulo_que_fica": fica})
        modulos.append(bloco | {"aulas": aulas})

    a_apagar = [
        {
            "numero": numero,
            "titulo": str(aula.get("titulo_exibido") or ""),
            "publicada": str(aula.get("estado") or "") == "publicada",
        }
        for numero, aula in hoje.items()
        if numero not in na_estrutura
    ]
    return modulos, a_apagar


def corpo_para_gravar(blocos: list, existentes: list) -> dict:
    """O corpo de `putCourseStructure`, montado dos blocos lidos.

    A Banca de cada aula que já existe viaja de volta como está: a estrutura é
    a fonte dela por contrato, e mandá-la sem esse campo zeraria o nível de
    Banca de toda aula que o tivesse, sem nada na tela dizendo.
    """
    banca = {
        str(aula.get("numero") or ""): aula.get("banca_nivel")
        for aula in existentes
        if isinstance(aula, dict)
    }
    return {
        "blocos": [
            {
                "letra": bloco["letra"],
                "parte": bloco["parte"],
                "nome": bloco["nome"],
                "boss_titulo": bloco["boss_titulo"],
                "aulas": [
                    {
                        "numero": aula["numero"],
                        "titulo": aula["titulo"],
                        "e_boss": aula["e_boss"],
                        "banca_nivel": banca.get(aula["numero"]),
                    }
                    for aula in bloco["aulas"]
                ],
            }
            for bloco in blocos
        ]
    }


# ---------------------------------------------------------------------------
# A TELA
# ---------------------------------------------------------------------------
def _desenhar(request, curso: str, colado: str, contexto: dict, status: int = 200):
    return render(
        request,
        TELA,
        {
            "admin": request.admin,
            "curso": curso,
            "colado": colado,
            "url_das_aulas": _endereco("escola_aulas", curso, None),
            "url_de_prever": _endereco("escola_estrutura_prever", curso, None),
            "url_de_importar": _endereco("escola_estrutura_importar", curso, None),
        }
        | contexto,
        status=status,
    )


def _sem_site(request, curso: str, colado: str):
    """O catálogo não respondeu, então não sei de qual escola é este curso.

    Sem `site_id` a porta responde 422 (Lei 9), e chutar um site seria pior que
    não abrir: mexeria na estrutura do curso de outro domínio.
    """
    return _desenhar(request, curso, colado, {"sem_site": True}, status=503)


def _preparar(request, curso: str, colado: str):
    """A leitura que PREVER e IMPORTAR fazem igual.

    Devolve `(preparado, resposta)`: exatamente um dos dois é `None`. A resposta
    pronta é a própria tela, e existe quando não há o que fazer: sem site, sem
    texto, texto com erro, curso que não existe, ou a sala de aula fora do ar.
    """
    site = _site_desta_requisicao(request)
    if site is None:
        return None, _sem_site(request, curso, colado)

    if not colado.strip():
        return None, _desenhar(
            request,
            curso,
            colado,
            {
                "erro": "Cole a lista dos módulos e das aulas na caixa antes de "
                "apertar o botão. Nada foi lido e nada foi gravado."
            },
            status=400,
        )

    blocos, erros = interpretar(colado)
    if erros:
        return None, _desenhar(request, curso, colado, {"erros": erros}, status=400)

    desfecho, existentes = CursosClient().aulas(site["id"], curso)
    if desfecho == CursosClient.NAO_EXISTE:
        return None, _desenhar(
            request,
            curso,
            colado,
            {
                "erro": f"Não existe nenhum curso {curso} nesta escola. Volte à "
                "lista de cursos e entre pelo curso certo. Nada foi gravado."
            },
            status=404,
        )
    if desfecho != CursosClient.OK:
        return None, _desenhar(
            request,
            curso,
            colado,
            {"falha_da_sala": _falha(desfecho)},
            status=503,
        )
    return (site, blocos, existentes or []), None


def _resumo(modulos: list, a_apagar: list) -> dict:
    """Os números do alto da tela, contados das linhas. Nunca guardados."""
    aulas = [aula for modulo in modulos for aula in modulo["aulas"]]
    return {
        "modulos": modulos,
        "a_apagar": a_apagar,
        "total_de_modulos": len(modulos),
        "total_de_aulas": len(aulas),
        "a_criar": sum(1 for aula in aulas if aula["acao"] == CRIAR),
        "a_preservar": sum(1 for aula in aulas if aula["acao"] == PRESERVAR),
    }


@require_GET
def estrutura(request, curso: str):
    """A área de colar, vazia. Nenhuma ida à porta: aqui ainda não há texto."""
    return _desenhar(request, curso, "", {})


@require_POST
def estrutura_prever(request, curso: str):
    """Lê o texto colado e mostra o que aconteceria. NÃO grava nada."""
    colado = (request.POST.get("estrutura") or "").replace("\r\n", "\n")
    preparado, resposta = _preparar(request, curso, colado)
    if resposta is not None:
        return resposta
    _, blocos, existentes = preparado
    modulos, a_apagar = casar(blocos, existentes)
    return _desenhar(
        request, curso, colado, _resumo(modulos, a_apagar) | {"previu": True}
    )


@require_POST
def estrutura_importar(request, curso: str):
    """Grava a estrutura inteira numa ida só. Ou tudo entra, ou nada entra.

    A porta reconcilia dentro de UMA transação, então não há meia estrutura
    para esta tela explicar: o 422 dela conta o motivo, e nada foi gravado.
    """
    colado = (request.POST.get("estrutura") or "").replace("\r\n", "\n")
    preparado, resposta = _preparar(request, curso, colado)
    if resposta is not None:
        return resposta
    site, blocos, existentes = preparado
    modulos, a_apagar = casar(blocos, existentes)
    resumo = _resumo(modulos, a_apagar)

    desfecho, corpo = CursosClient().gravar_estrutura(
        site["id"], curso, corpo_para_gravar(blocos, existentes)
    )
    # QUAIS campos mudaram e QUANTOS, nunca o que o mantenedor escreveu: os
    # nomes das aulas são obra dele, e a auditoria é append-only (`LICOES.md`,
    # 28/08/2026).
    rastro = (
        f"{resumo['total_de_modulos']} módulo(s), {resumo['total_de_aulas']} aula(s)"
    )
    if desfecho == CursosClient.OK:
        contagens = _contagens(corpo)
        _auditar(
            request,
            Registro.IMPORTAR_ESTRUTURA,
            curso,
            Registro.OK,
            f"{rastro}; {contagens['criadas']} criada(s), "
            f"{contagens['apagadas']} apagada(s)",
        )
        return _desenhar(
            request, curso, colado, resumo | {"importou": True} | contagens
        )

    _auditar(
        request,
        Registro.IMPORTAR_ESTRUTURA,
        curso,
        (
            Registro.RECUSADO_PELA_CELULA
            if desfecho == CursosClient.RECUSADO
            else Registro.NAO_RESPONDEU
        ),
        f"{rastro}; desfecho: {desfecho}",
    )
    if desfecho == CursosClient.RECUSADO:
        return _desenhar(
            request,
            curso,
            colado,
            resumo | {"recusa_da_sala": _frase(corpo)},
            status=400,
        )
    if desfecho == CursosClient.NAO_EXISTE:
        return _desenhar(
            request,
            curso,
            colado,
            {
                "erro": f"Não existe nenhum curso {curso} nesta escola, e nada foi "
                "gravado. Volte à lista de cursos e entre pelo curso certo."
            },
            status=404,
        )
    return _desenhar(
        request,
        curso,
        colado,
        resumo | {"falha_da_sala": _falha(desfecho), "nao_sei_se_gravou": True},
        status=503,
    )


def _contagens(corpo) -> dict:
    """As quatro contagens que a porta devolveu, prontas para a tela.

    Elas vêm de lá, e não são recontadas aqui: quem sabe o que a reconciliação
    fez é quem a fez, e uma segunda conta feita nesta tela discordaria dela no
    primeiro caso de borda.
    """
    corpo = corpo if isinstance(corpo, dict) else {}
    return {
        "blocos_criados": int(corpo.get("blocos_criados") or 0),
        "criadas": int(corpo.get("aulas_criadas") or 0),
        "preservadas": int(corpo.get("aulas_preservadas") or 0),
        "apagadas": int(corpo.get("aulas_apagadas") or 0),
    }
