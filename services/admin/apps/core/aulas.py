"""`/admin/escola/<curso>/parte-N/aulas/` — o editor de encomendas do curso,
onde o mantenedor e a professora escrevem as 34 aulas: as 16 peças, o roteiro e
a ficha do Guia do Mentor, as pausas, o instrumento cabível, o "Aceito quando",
o quiz, o vídeo por link, e o botão de publicar.

Degrau 1.5 do `docs/decisoes/PLANO-CELULA-CURSOS.md` (§6, o editor).

## O curso e a Parte moram no ENDEREÇO (05/09/2026, TAR-211)

Pedido do mantenedor: *"quero que ao compartilhar uma aula o link da mesma seja
útil para o aluno entender exatamente em qual parte do curso ele está"*, e
*"precisamos ajustar o curso ao livro porque o aluno terá o livro em mãos
durante o curso"*. Daí as duas metades desta tela:

1. **O endereço leva o curso e a Parte.** O curso é o SLUG, e a porta o resolve
   pelo par site+slug, nunca mais como "o primeiro curso do site" (que serviria
   o curso errado, calado, no dia do segundo). A Parte é opcional:
   `/admin/escola/<curso>/aulas/` mostra o curso inteiro. Na lista ela é filtro;
   no editor é GUARDA, e parte que não casa com o bloco da encomenda é recusa,
   traduzida aqui no endereço certo pronto para clicar.
2. **A lista é agrupada como o livro**: as três Partes como seções, e dentro de
   cada uma os blocos por letra, na ordem. É assim que se acha a encomenda com
   o livro aberto ao lado da tela.

Das operações da porta, esta tela chama SEMPRE as que sabem de curso
(`listLessons`, `getLesson`, `putLesson`, `publishLesson`) e nunca as irmãs que
varrem o site inteiro. O guarda disso é
`tests/test_editor_de_aulas.py::test_a_tela_nunca_chama_as_operacoes_que_nao_sabem_de_curso`.

## Onde o dado mora, e por que não aqui

Na célula `cursos`, e SÓ lá. Esta tela **não guarda nada**: lê tudo pela porta
de máquina (`contracts/cursos.openapi.yaml`, as sete operações do editor) e
grava pela mesma porta. Guardar uma cópia aqui seria o mesmo fato em dois
lugares (a lei anti-duplicação do `CLAUDE.md`), e o peso aqui é maior do que na
economia ou nas sequências: o texto das aulas é obra NÃO LANÇADA do mantenedor,
o repositório é público, e o único caminho do texto para dentro do sistema é
esta tela ([INV-CUR-C2], `armadilhas/331`). Nenhuma frase de aula existe em
arquivo; nenhuma entra por migração.

## O travessão AVISA, e não recusa

Decisão do mantenedor em 04/09/2026, para a Biblioteca do Livro, e o plano da
`cursos` (§6) a estende a este editor: a obra se guarda como ele escreveu. A lei
do travessão vale na tela do ALUNO, e quem vai cobrá-la antes de publicar é o
verificador de coerência do degrau 3.1, que ainda não existe. O que esta tela
faz é o mecanismo de `apps/core/livro.py`: conta as riscas em todas as peças,
lista as frases com o nome da peça e a linha, e salva mesmo assim. A contagem
sai na LEITURA (toda vez que o editor abre), e por isso aparece logo depois de
salvar sem que a tela precise guardar nada entre o POST e o GET.

## O 422 da porta vira frase ao lado do campo, nunca 500

A `cursos` recusa com 422 e devolve a lista de erros do contrato, com o `loc`
de cada um (`["body", "payload", "pausas", 1, "segundo"]`). Esta tela traduz o
vocabulário fechado do pydantic para português e pendura a frase no campo certo
(a peça, a pergunta do quiz, a linha da pausa). A validação mora num lugar só,
que é a dona do dado; aqui só se traduz. O que a porta escreve como texto livre
(`value_error`: "o instrumento 'x' não existe; os slugs são: ...") sai
verbatim, pela mesma razão de `apps/core/sequencias.py`: reescrevê-lo amarraria
esta tela à redação de uma mensagem da outra célula.

**A recusa devolve o rascunho INTEIRO.** Perder o texto de alguém por causa de
uma regra é o caminho mais curto para essa pessoa odiar a regra, e aqui o que
se perderia é uma aula que não existe em outro lugar.

## Quem autoriza é ESTA célula

A `cursos` não assina sessão. O crachá que vale é o desta área, que a porta do
`/admin/` já exige; o Bearer do par (`CURSOS_API_URL`/`CURSOS_API_TOKEN`, lido
no ponto de uso, `armadilhas/097`) prova só QUEM CHAMA. Mesmo desenho de
`/admin/economia/` e `/admin/escola/jornadas/`.

## Por que é formulário simples, sem script

Cada gesto é um POST que recarrega a página, pelas três razões de sempre: o
que se vê é o que está gravado; a política de segurança desta área exige um
hash na CSP para cada script embutido (`armadilhas/199`), e um formulário não
precisa de nenhum; e o mantenedor é leigo, então um botão por gesto, com o
nome do gesto escrito nele, não tem como ser mal entendido.
"""

from __future__ import annotations

import json
from datetime import datetime

from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.auditoria.models import Registro

from . import travessao
from .clients import CatalogoClient, CursosClient
from .views import _auditar

LISTA = "admin/escola_aulas.html"
EDITOR = "admin/escola_aula.html"
INSTRUMENTO = "admin/escola_instrumento.html"

# ---------------------------------------------------------------------------
# O DICIONÁRIO DA TELA — os vocabulários fechados do contrato, em português
# ---------------------------------------------------------------------------
# As 18 peças NA ORDEM CANÔNICA do contrato (`TipoDePeca`): as 16 da anatomia e
# as duas internas, que o aluno nunca vê. A tela desenha as peças na ordem em
# que a porta as devolve (promessa do contrato), e este mapa dá o nome de cada
# uma; o formulário as devolve nesta mesma ordem. Um tipo que a porta mandar e
# este mapa não conhecer aparece com o slug cru, que é feio mas honesto.
# `tests/test_editor_de_aulas.py` confere que esta ordem é a do contrato.
PECAS = (
    ("pedido", "O pedido", False),
    ("em_jogo", "O que está em jogo", False),
    ("voce_vai_conseguir", "Você vai conseguir", False),
    ("recall", "Recall", False),
    ("par_de_comparacao", "Par de comparação", False),
    ("erro_produtivo", "Erro produtivo", False),
    ("eu_faco", "Eu faço", False),
    ("nos_fazemos", "Nós fazemos", False),
    ("voce_faz", "Você faz", False),
    ("drills", "Drills", False),
    ("erros_classicos", "Erros clássicos", False),
    ("regra_do_padrao", "Regra do Padrão", False),
    ("critica_de_atelier", "Crítica de ateliê", False),
    ("checkpoint", "Checkpoint", False),
    ("pagina_do_portfolio", "Página do portfólio", False),
    ("dicionario_cartao_respostas", "Dicionário, cartão e respostas", False),
    ("roteiro", "Roteiro da aula", True),
    ("guia_do_mentor", "Ficha do Guia do Mentor", True),
)
NOME_DA_PECA = {tipo: nome for tipo, nome, _ in PECAS}
PECAS_INTERNAS = frozenset(tipo for tipo, _, interna in PECAS if interna)

TIPOS_DE_PAUSA = (
    ("erro_produtivo", "Erro produtivo"),
    ("faca_agora", "Faça agora"),
    ("cerimonia", "Cerimônia"),
)
TIPO_DE_PAUSA_CONHECIDO = frozenset(valor for valor, _ in TIPOS_DE_PAUSA)

ESTADO = {"rascunho": "Rascunho", "publicada": "Publicada"}

#: O quiz da encomenda tem cinco pares pergunta/resposta-modelo (plano §3.5).
#: A tela oferece sempre cinco linhas; as vazias não viajam.
PERGUNTAS_DO_QUIZ = 5

#: Quantas linhas vazias de pausa a tela oferece além das que já existem. Três
#: cabem numa aula normal sem virar uma tabela de vinte linhas em branco.
LINHAS_DE_PAUSA_A_MAIS = 3

#: O curso por onde se ENTRA no editor, vindo do painel da escola.
#:
#: O slug viaja no endereço de toda tela daqui, e é o par site+slug que resolve
#: o curso do outro lado. Este valor existe só porque a porta não tem operação
#: que LISTE os cursos de um site: para desenhar o primeiro link é preciso um
#: slug, e hoje há um curso só. No dia do segundo, esta constante vira um
#: seletor no painel da escola, e nenhuma outra linha desta tela muda, porque o
#: slug já é dado do endereço em todas elas.
CURSO_PADRAO = "profissional"

#: As três Partes do livro, com o número que viaja no endereço e o algarismo
#: romano com que o livro as chama. O mantenedor e a professora leem a tela com
#: o livro aberto ao lado: o endereço usa `parte-1` (o vocabulário do contrato,
#: `ParteDoCurso`) e a tela escreve "Parte I", que é o que está impresso.
PARTES = ((1, "I"), (2, "II"), (3, "III"))
ROMANO = dict(PARTES)

# Os campos do corpo de `putLesson` e de `putInstrument`, com o nome que a
# recusa cita. O `loc` de um erro da porta começa por um destes.
ROTULO_DO_CAMPO = {
    "pedido": "O pedido",
    "cliente": "O cliente",
    "instrumento": "O instrumento",
    "minimo": "O mínimo",
    "aceito_quando": 'O "Aceito quando"',
    "quiz": "O quiz",
    "video_url": "O vídeo",
    "e_boss": "A marca de Boss",
    "banca_nivel": "O nível de Banca",
    "pecas": "As peças",
    "pausas": "As pausas",
    "escala": "A escala",
    "minimo_exercicio": "O mínimo do exercício",
    "minimo_contrato": "O mínimo do contrato",
    "secao_do_padrao": "A seção do Padrão",
    "descritores": "Os descritores",
}

# O que aparece DENTRO de uma linha do quiz, de uma peça ou de uma pausa.
ROTULO_DO_SUBCAMPO = {
    "texto": "o texto",
    "tipo": "o tipo",
    "pergunta": "a pergunta",
    "resposta_modelo": "a resposta-modelo",
    "ordem": "a ordem",
    "segundo": "o segundo",
    "pede": "o que ela pede",
    "campos": "os campos",
}

# O vocabulário fechado do pydantic, em português. O que não estiver aqui sai
# com a frase que a porta escreveu (é o caso de `value_error`, que é texto
# livre da `cursos`, e sai verbatim de propósito: ver o cabeçalho).
O_QUE_DEU_ERRADO = {
    "string_too_short": "não pode ficar vazio",
    "missing": "não veio no formulário",
    "int_parsing": "precisa ser um número inteiro",
    "int_type": "precisa ser um número inteiro",
    "int_from_float": "precisa ser um número inteiro, sem vírgula",
    "greater_than_equal": "não pode ser negativo",
    "less_than_equal": "passou do maior valor que a sala de aula aceita",
    "enum": "não está no vocabulário da sala de aula",
    "literal_error": "só pode ser 1, 2 ou 3",
    "extra_forbidden": "é uma chave que a sala de aula não conhece",
    "bool_parsing": "precisa ser sim ou não",
    "bool_type": "precisa ser sim ou não",
    "list_type": "precisa ser uma lista",
    "dict_type": "precisa ser um objeto",
    "string_type": "precisa ser texto",
}


# ---------------------------------------------------------------------------
# PEQUENOS AJUDANTES
# ---------------------------------------------------------------------------
def _texto(bruto) -> str:
    """Um texto do formulário, com o fim de linha do Windows desfeito.

    A ÚNICA troca feita no que a pessoa escreveu, pela mesma razão de
    `livro.py`: o navegador manda `\\r\\n` em todo formulário, e o texto
    voltaria com uma marca invisível por linha. Nenhum aparo: a obra se guarda
    como ela escreveu.
    """
    return (bruto or "").replace("\r\n", "\n")


def _numero_ou_cru(bruto: str):
    """Um campo numérico do formulário, do jeito que a porta vai julgá-lo.

    Dígitos viram inteiro; vazio vira `None`; qualquer outra coisa segue CRUA.
    Não se corrige aqui: quem decide se "abc" serve é a `cursos`, que responde
    422 com o `loc` certo, e a tela põe a frase ao lado do campo. Uma segunda
    validação aqui seria a mesma regra em dois lugares.
    """
    bruto = (bruto or "").strip()
    if not bruto:
        return None
    return int(bruto) if bruto.isdigit() else bruto


def _momento(bruto) -> str:
    """Um instante da porta em português, no fuso de quem lê esta tela.

    O contrato manda data como texto ISO em UTC; sem o `localtime`, uma
    publicação das 21h de sábado apareceria como meia-noite de domingo. Texto
    que não for data sai CRU em vez de sumir.
    """
    if not bruto:
        return ""
    try:
        quando = datetime.fromisoformat(str(bruto))
    except (TypeError, ValueError):
        return str(bruto)
    if timezone.is_aware(quando):
        quando = timezone.localtime(quando)
    return quando.strftime("%d/%m/%Y às %H:%M")


def _site_desta_requisicao(request) -> "dict | None":
    """O site vem do HOST desta própria requisição, sem seletor.

    Mesmo padrão de `apps/core/sequencias.py` e `apps/core/avisos.py`: toda
    operação de aula da porta é escopada por `site_id` (CONSTITUICAO Lei 9), e
    sem ele a porta responde 422 em vez de uma lista vazia que pareceria
    resposta.
    """
    return CatalogoClient().site_por_host(request.get_host().split(":")[0].lower())


def _parte_do_bloco(bloco) -> int:
    """A Parte em que a encomenda está, pelo `bloco` do contrato.

    Zero quando a porta manda algo fora do vocabulário: a tela mostra "Parte ?"
    em vez de escolher uma Parte por conta própria.
    """
    parte = (bloco or {}).get("parte")
    return parte if parte in ROMANO else 0


def _bloco(bloco) -> str:
    bloco = bloco or {}
    romano = ROMANO.get(_parte_do_bloco(bloco), "?")
    return f"Parte {romano}, bloco {bloco.get('letra', '?')}"


def _endereco(nome: str, curso: str, parte: "int | None", numero: str = "") -> str:
    """O endereço de uma tela deste editor, com o curso e (quando há) a Parte.

    Um lugar só monta endereço aqui, e é `reverse`: o prefixo `/admin` desta
    célula mora no env (`armadilhas/029`), e endereço escrito à mão o perderia.
    """
    argumentos: dict = {"curso": curso}
    if parte:
        argumentos["parte"] = str(parte)
    if numero:
        argumentos["numero"] = numero
    return reverse(nome, kwargs=argumentos)


def _cabecalho(aula: dict) -> dict:
    """O que a tela mostra e NÃO edita: número, título, bloco, estado, versão."""
    estado = str(aula.get("estado") or "")
    return {
        "numero": str(aula.get("numero") or ""),
        "titulo_exibido": str(aula.get("titulo_exibido") or ""),
        "bloco": _bloco(aula.get("bloco")),
        "estado": estado,
        "estado_rotulo": ESTADO.get(estado, estado),
        "publicada": estado == "publicada",
        "versao": int(aula.get("versao") or 0),
        "publicada_em": _momento(aula.get("publicada_em")),
    }


# ---------------------------------------------------------------------------
# O RASCUNHO — o que o formulário desenha, e de onde sai o corpo da porta
# ---------------------------------------------------------------------------
# Duas origens, uma forma. Da PORTA, quando o editor abre; do FORMULÁRIO, quando
# a porta recusa e a tela devolve o que a pessoa escreveu. Ter uma forma só é o
# que deixa o template ser um, e o que deixa `_corpo` ser uma função só.
def _linha_do_quiz(n: int, item: dict | None) -> dict:
    item = item or {}
    return {
        "n": n,
        "pergunta": str(item.get("pergunta") or ""),
        "resposta_modelo": str(item.get("resposta_modelo") or ""),
        "erro": "",
    }


def _linha_de_pausa(n: int, pausa: dict | None) -> dict:
    pausa = pausa or {}
    campos = pausa.get("campos")
    if isinstance(campos, list):
        campos = ", ".join(str(c) for c in campos)
    tipo = str(pausa.get("tipo") or "")
    return {
        "n": n,
        "ordem": "" if pausa.get("ordem") is None else str(pausa.get("ordem")),
        "segundo": "" if pausa.get("segundo") is None else str(pausa.get("segundo")),
        "tipo": tipo,
        # Um tipo que a porta mandar e esta tela não conhecer continua
        # selecionado, cru: sumir com ele em silêncio gravaria a pausa sem tipo.
        "tipo_conhecido": tipo in TIPO_DE_PAUSA_CONHECIDO,
        "pede": str(pausa.get("pede") or ""),
        "campos": str(campos or ""),
        "erro": "",
    }


def _linha_de_peca(tipo: str, texto: str) -> dict:
    return {
        "tipo": tipo,
        "nome": NOME_DA_PECA.get(tipo, tipo),
        "interna": tipo in PECAS_INTERNAS,
        "texto": texto,
        "erro": "",
    }


def _rascunho_da_aula(aula: dict) -> dict:
    """O rascunho como a porta o devolveu: o texto que ESTÁ gravado."""
    quiz = [q for q in (aula.get("quiz") or []) if isinstance(q, dict)]
    pausas = [p for p in (aula.get("pausas") or []) if isinstance(p, dict)]
    pecas = [p for p in (aula.get("pecas") or []) if isinstance(p, dict)]
    banca = aula.get("banca_nivel")
    return {
        "pedido": str(aula.get("pedido") or ""),
        "cliente": str(aula.get("cliente") or ""),
        "instrumento": str(aula.get("instrumento") or ""),
        "minimo": str(aula.get("minimo") or ""),
        "aceito_quando": "\n".join(str(c) for c in (aula.get("aceito_quando") or [])),
        "video_url": str(aula.get("video_url") or ""),
        "e_boss": bool(aula.get("e_boss")),
        "banca_nivel": "" if banca is None else str(banca),
        "quiz": [
            _linha_do_quiz(n + 1, quiz[n] if n < len(quiz) else None)
            for n in range(max(PERGUNTAS_DO_QUIZ, len(quiz)))
        ],
        "pecas": [
            _linha_de_peca(str(p.get("tipo") or ""), str(p.get("texto") or ""))
            for p in pecas
        ],
        "pausas": [
            _linha_de_pausa(n + 1, pausas[n] if n < len(pausas) else None)
            for n in range(len(pausas) + LINHAS_DE_PAUSA_A_MAIS)
        ],
        "erros": {},
    }


def _rascunho_do_formulario(request) -> dict:
    """O rascunho como a pessoa o mandou, letra por letra, para voltar à tela
    se a porta recusar. As peças vêm na ordem canônica de `PECAS`."""
    dados = request.POST
    quiz = []
    n = 1
    while n <= PERGUNTAS_DO_QUIZ or f"quiz_{n}_pergunta" in dados:
        quiz.append(
            _linha_do_quiz(
                n,
                {
                    "pergunta": dados.get(f"quiz_{n}_pergunta", ""),
                    "resposta_modelo": dados.get(f"quiz_{n}_resposta_modelo", ""),
                },
            )
        )
        n += 1
    pausas = []
    n = 1
    while f"pausa_{n}_tipo" in dados or f"pausa_{n}_pede" in dados:
        pausas.append(
            _linha_de_pausa(
                n,
                {
                    "ordem": dados.get(f"pausa_{n}_ordem", ""),
                    "segundo": dados.get(f"pausa_{n}_segundo", ""),
                    "tipo": dados.get(f"pausa_{n}_tipo", ""),
                    "pede": dados.get(f"pausa_{n}_pede", ""),
                    "campos": dados.get(f"pausa_{n}_campos", ""),
                },
            )
        )
        n += 1
    return {
        "pedido": _texto(dados.get("pedido")),
        "cliente": (dados.get("cliente") or "").strip(),
        "instrumento": (dados.get("instrumento") or "").strip(),
        "minimo": (dados.get("minimo") or "").strip(),
        "aceito_quando": _texto(dados.get("aceito_quando")),
        "video_url": (dados.get("video_url") or "").strip(),
        "e_boss": dados.get("e_boss") == "1",
        "banca_nivel": (dados.get("banca_nivel") or "").strip(),
        "quiz": quiz,
        "pecas": [
            _linha_de_peca(tipo, _texto(dados.get(f"peca_{tipo}")))
            for tipo, _, _ in PECAS
        ],
        "pausas": pausas,
        "erros": {},
    }


def _corpo(rascunho: dict) -> "tuple[dict, dict]":
    """O corpo de `putLesson` a partir do rascunho, e QUAIS linhas viajaram.

    Linha vazia do quiz e da pausa não viaja: a tela oferece linhas em branco
    para preencher, e mandá-las faria a porta recusar a aula inteira por causa
    de um espaço em branco. O segundo item diz, para cada lista, o índice da
    linha do rascunho que virou cada item do corpo: é por ele que um erro da
    porta ("quiz, item 2") volta para a linha certa da tela.
    """
    quiz, quiz_enviado = [], []
    for i, item in enumerate(rascunho["quiz"]):
        pergunta = item["pergunta"].strip()
        resposta = item["resposta_modelo"].strip()
        if pergunta or resposta:
            quiz.append({"pergunta": pergunta, "resposta_modelo": resposta})
            quiz_enviado.append(i)

    pausas, pausas_enviadas = [], []
    for i, linha in enumerate(rascunho["pausas"]):
        if not any(
            linha[c].strip() for c in ("ordem", "segundo", "tipo", "pede", "campos")
        ):
            continue
        ordem = _numero_ou_cru(linha["ordem"])
        pausas.append(
            {
                # Sem ordem escrita, a ordem é a posição na tabela: é o que a
                # pessoa vê, e é o que ela quis dizer.
                "ordem": len(pausas) + 1 if ordem is None else ordem,
                "segundo": _numero_ou_cru(linha["segundo"]),
                "tipo": linha["tipo"].strip(),
                "pede": linha["pede"].strip(),
                "campos": [c.strip() for c in linha["campos"].split(",") if c.strip()],
            }
        )
        pausas_enviadas.append(i)

    banca = rascunho["banca_nivel"].strip()
    corpo = {
        "pedido": rascunho["pedido"],
        "cliente": rascunho["cliente"],
        "instrumento": rascunho["instrumento"] or None,
        "minimo": rascunho["minimo"],
        "aceito_quando": [
            linha.strip()
            for linha in rascunho["aceito_quando"].splitlines()
            if linha.strip()
        ],
        "quiz": quiz,
        "video_url": rascunho["video_url"],
        "e_boss": bool(rascunho["e_boss"]),
        "banca_nivel": (
            None if not banca else (int(banca) if banca in ("1", "2", "3") else banca)
        ),
        "pecas": [{"tipo": p["tipo"], "texto": p["texto"]} for p in rascunho["pecas"]],
        "pausas": pausas,
    }
    enviados = {
        "quiz": quiz_enviado,
        "pausas": pausas_enviadas,
        "pecas": list(range(len(rascunho["pecas"]))),
    }
    return corpo, enviados


# ---------------------------------------------------------------------------
# O TRAVESSÃO: conta e lista, nunca recusa
# ---------------------------------------------------------------------------
def _riscas(rascunho: dict) -> list:
    """As frases com risca comprida em todas as peças e nos campos de texto,
    cada uma dizendo ONDE está. O mesmo instrumento que recusa no editor de
    documentos, aqui só avisa (ver o cabeçalho)."""
    achados = []
    for peca in rascunho["pecas"]:
        for achado in travessao.problemas(peca["texto"]):
            achado["onde"] = f"peça \"{peca['nome']}\", linha {achado['linha']}"
            achados.append(achado)
    for campo in ("pedido", "cliente", "minimo", "aceito_quando"):
        for achado in travessao.problemas(rascunho[campo]):
            achado["onde"] = f"{ROTULO_DO_CAMPO[campo]}, linha {achado['linha']}"
            achados.append(achado)
    for item in rascunho["quiz"]:
        for achado in travessao.problemas(
            item["pergunta"] + "\n" + item["resposta_modelo"]
        ):
            achado["onde"] = f"quiz, pergunta {item['n']}"
            achados.append(achado)
    return achados


# ---------------------------------------------------------------------------
# O 422 DA PORTA, TRADUZIDO PARA O CAMPO CERTO
# ---------------------------------------------------------------------------
def _frase_do_erro(erro: dict) -> str:
    tipo = str(erro.get("type") or "")
    if tipo == "string_too_long":
        teto = (erro.get("ctx") or {}).get("max_length")
        if teto:
            return f"passa do tamanho que a sala de aula aceita ({teto} letras)"
        return "passa do tamanho que a sala de aula aceita"
    if tipo in O_QUE_DEU_ERRADO:
        return O_QUE_DEU_ERRADO[tipo]
    msg = str(erro.get("msg") or "")
    if msg.startswith("Value error, "):
        msg = msg[len("Value error, ") :]
    return msg or "a sala de aula recusou este valor, sem dizer por quê"


def _pendurar(rascunho: dict, enviados: dict, detalhe) -> list[str]:
    """Pendura cada erro do 422 no campo certo do rascunho. Devolve os erros
    que não têm campo (os gerais), para a tela mostrar no alto.

    O `detail` do contrato é uma lista de `{type, loc, msg}`; se vier outra
    coisa (uma frase solta), ela vira erro geral, verbatim.
    """
    if not isinstance(detalhe, list):
        return (
            [str(detalhe)]
            if detalhe
            else ["a sala de aula recusou, sem dizer o motivo"]
        )

    gerais: list[str] = []
    campos: dict = rascunho["erros"]
    for erro in detalhe:
        if not isinstance(erro, dict):
            gerais.append(str(erro))
            continue
        frase = _frase_do_erro(erro)
        loc = [p for p in (erro.get("loc") or [])]
        if loc and loc[0] == "body":
            loc = loc[1:]
        if loc and loc[0] == "payload":
            loc = loc[1:]

        if not loc:
            gerais.append(frase)
            continue
        campo = str(loc[0])
        rotulo = ROTULO_DO_CAMPO.get(campo, campo)

        # Um item de lista: a peça, a pergunta do quiz, a linha da pausa.
        if (
            campo in ("pecas", "quiz", "pausas")
            and len(loc) >= 2
            and isinstance(loc[1], int)
        ):
            indice = loc[1]
            subcampo = (
                ROTULO_DO_SUBCAMPO.get(str(loc[2]), str(loc[2]))
                if len(loc) >= 3
                else ""
            )
            frase_da_linha = f"{subcampo} {frase}".strip() if subcampo else frase
            linhas = enviados.get(campo) or []
            if indice < len(linhas):
                linha = rascunho[campo][linhas[indice]]
                linha["erro"] = "; ".join(filter(None, [linha["erro"], frase_da_linha]))
                continue
            gerais.append(f"{rotulo}, item {indice + 1}: {frase_da_linha}")
            continue

        if campo == "aceito_quando" and len(loc) >= 2 and isinstance(loc[1], int):
            frase = f"linha {loc[1] + 1} {frase}"
        if campo in ROTULO_DO_CAMPO:
            campos[campo] = "; ".join(filter(None, [campos.get(campo, ""), frase]))
        else:
            gerais.append(f"{rotulo}: {frase}")
    return gerais


def _nomes_dos_campos_recusados(rascunho: dict, gerais: list[str]) -> str:
    """Para a auditoria: QUAIS campos a porta recusou, nunca os valores."""
    nomes = list(rascunho["erros"])
    for lista in ("pecas", "quiz", "pausas"):
        if any(linha["erro"] for linha in rascunho[lista]):
            nomes.append(lista)
    if gerais:
        nomes.append("geral")
    return ", ".join(nomes) or "sem campo"


# ---------------------------------------------------------------------------
# AS TELAS, DESENHADAS SEMPRE DO QUE A PORTA RESPONDEU
# ---------------------------------------------------------------------------
# A `cursos` fora do ar tem três caras, e cada uma vira uma frase diferente,
# porque o conserto de cada uma é diferente (ver `CursosClient`).
FALHA_DA_SALA = {
    CursosClient.SEM_CONFIGURACAO: (
        "Ainda não consigo falar com a sala de aula.",
        "Falta criar a ligação entre esta área e o lugar onde as aulas ficam "
        "guardadas: as duas chaves do par (CURSOS_API_URL e CURSOS_API_TOKEN) "
        "ainda não estão no ambiente desta área. É um passo de máquina, dentro "
        "do servidor. Nada do que está guardado mudou por causa disso.",
    ),
    CursosClient.RECUSOU: (
        "A sala de aula recusou a admin: confira o par.",
        "A ligação existe deste lado, mas a sala de aula não aceitou a senha de "
        "par desta área. É um passo de máquina, dentro do servidor. Nada do que "
        "está guardado mudou por causa disso.",
    ),
    CursosClient.NAO_RESPONDEU: (
        "A sala de aula não respondeu.",
        "Recarregue a página em um minuto. Nada do que está guardado mudou por "
        "causa disso.",
    ),
}


def _falha(desfecho: str) -> dict:
    titulo, explicacao = FALHA_DA_SALA.get(
        desfecho, FALHA_DA_SALA[CursosClient.NAO_RESPONDEU]
    )
    return {"titulo": titulo, "explicacao": explicacao}


def _sem_site(request, status: int = 503):
    """O catálogo não respondeu, então não sei de qual escola são as aulas.

    Sem `site_id` a porta responde 422 (Lei 9), e chutar um site seria pior que
    não abrir: mostraria as aulas de outro domínio.
    """
    return render(
        request, LISTA, {"admin": request.admin, "sem_site": True}, status=status
    )


def _linha_da_lista(aula: dict, curso: str) -> dict:
    """Uma linha da lista, com o endereço dela já montado.

    O endereço leva SEMPRE a Parte da própria encomenda, mesmo quando a lista
    aberta é a do curso inteiro: é o link que a professora copia, e ele tem de
    dizer a quem o abrir em que ponto do livro aquilo está.
    """
    bloco = aula.get("bloco") or {}
    parte = _parte_do_bloco(bloco)
    cabecalho = _cabecalho(aula)
    return cabecalho | {
        "ordem": int(aula.get("ordem") or 0),
        "e_boss": bool(aula.get("e_boss")),
        "banca_nivel": aula.get("banca_nivel"),
        # As três que agrupam: a Parte e a letra dizem em que seção a linha
        # entra, e a ordem do bloco é a do livro (A a L), não a alfabética.
        "parte": parte,
        "letra": str(bloco.get("letra") or "?"),
        "ordem_do_bloco": int(bloco.get("ordem") or 0),
        "endereco": _endereco("escola_aula", curso, parte, cabecalho["numero"]),
    }


def _agrupar(linhas: list, curso: str) -> list:
    """As encomendas nas três Partes do livro, e dentro de cada uma nos blocos.

    A ordem é a do livro: Parte I, II, III; dentro de cada Parte os blocos pela
    ordem deles (que é a letra, de A a L); dentro de cada bloco a ordem da
    encomenda. Uma lista corrida de 34 linhas obriga quem está com o livro
    aberto ao lado a contar de cabeça em que Parte cada uma cai.
    """
    partes = []
    for parte, romano in PARTES:
        da_parte = sorted(
            (linha for linha in linhas if linha["parte"] == parte),
            key=lambda linha: (linha["ordem_do_bloco"], linha["ordem"]),
        )
        if not da_parte:
            continue
        blocos: list = []
        for linha in da_parte:
            if not blocos or blocos[-1]["letra"] != linha["letra"]:
                blocos.append({"letra": linha["letra"], "aulas": []})
            blocos[-1]["aulas"].append(linha)
        partes.append(
            {
                "romano": romano,
                "blocos": blocos,
                "endereco": _endereco("escola_aulas", curso, parte),
            }
        )
    return partes


def _desenhar_lista(request, site: dict, curso: str, parte: "int | None"):
    cliente = CursosClient()
    desfecho, aulas = cliente.aulas(site["id"], curso, parte)
    if desfecho == CursosClient.NAO_EXISTE:
        return render(
            request,
            LISTA,
            {"admin": request.admin, "curso_nao_existe": True, "curso": curso},
            status=404,
        )
    if desfecho != CursosClient.OK:
        return render(
            request,
            LISTA,
            {"admin": request.admin, "falha_da_sala": _falha(desfecho)},
            status=503,
        )
    linhas = [_linha_da_lista(a, curso) for a in aulas if isinstance(a, dict)]
    lidos, instrumentos = cliente.instrumentos()
    return render(
        request,
        LISTA,
        {
            "admin": request.admin,
            "curso": curso,
            "parte": parte,
            "parte_romano": ROMANO.get(parte or 0, ""),
            "url_do_curso_inteiro": _endereco("escola_aulas", curso, None),
            "partes": _agrupar(linhas, curso),
            # O que a porta mandar com Parte fora do vocabulário do contrato
            # (`ParteDoCurso` é 1, 2 ou 3) não cabe em nenhuma seção e SUMIRIA
            # da tela em silêncio, com a contagem do topo dizendo outro número.
            # A tela conta em voz alta em vez de esconder.
            "fora_das_partes": [linha for linha in linhas if not linha["parte"]],
            "aulas": linhas,
            "publicadas": sum(1 for linha in linhas if linha["publicada"]),
            "instrumentos": [
                {
                    "slug": str(i.get("slug") or ""),
                    "nome_canonico": str(i.get("nome_canonico") or ""),
                    "cartao": i.get("cartao"),
                    "versao": int(i.get("versao") or 0),
                }
                for i in (instrumentos or [])
                if isinstance(i, dict)
            ],
            "instrumentos_lidos": lidos == CursosClient.OK,
        },
    )


def _endereco_certo(cliente, site: dict, curso: str, numero: str) -> "int | None":
    """A encomenda existe, mas em outra Parte? Devolve a Parte de verdade dela.

    A porta recusa a parte que não casa com um 404 cujo texto diz onde a
    encomenda está. Ler esse texto seria a tela decorando a frase de outra
    célula; em vez disso ela pergunta de novo SEM a parte e lê o `bloco.parte`
    do contrato, que é dado, não prosa. Custa uma ida à porta, e só no caminho
    do erro, para devolver um endereço certo pronto para clicar em vez de um
    "não existe" que mandaria a professora procurar sozinha.

    `None` quando a encomenda não existe mesmo, ou quando a porta não respondeu
    a segunda vez: nos dois casos a tela diz que não achou, e nunca inventa
    uma Parte.
    """
    desfecho, aula = cliente.aula(site["id"], curso, numero)
    if desfecho != CursosClient.OK:
        return None
    return _parte_do_bloco((aula or {}).get("bloco")) or None


def _desenhar_aula(
    request,
    site: dict,
    curso: str,
    numero: str,
    parte: "int | None" = None,
    *,
    rascunho: "dict | None" = None,
    gerais: "list[str] | None" = None,
    erro: str = "",
    recado: str = "",
    versao: int = 0,
    status: int = 200,
):
    """O editor de UMA encomenda.

    Sem `rascunho`, a tela desenha o que a porta devolveu (o texto gravado).
    Com `rascunho`, desenha o que a pessoa mandou e a porta recusou, com os
    erros já pendurados nos campos; o cabeçalho (título, estado, versão)
    continua vindo da porta, porque só ela sabe.

    `parte` é a do ENDEREÇO, e ela é guarda dos dois lados: a porta recusa a
    que não casa com o bloco da encomenda, e esta tela transforma a recusa no
    endereço certo.
    """
    cliente = CursosClient()
    desfecho, aula = cliente.aula(site["id"], curso, numero, parte)
    if desfecho == CursosClient.NAO_EXISTE:
        certa = _endereco_certo(cliente, site, curso, numero) if parte else None
        return render(
            request,
            EDITOR,
            {
                "admin": request.admin,
                "nao_existe": True,
                "numero": numero,
                "curso": curso,
                "url_da_lista": _endereco("escola_aulas", curso, parte),
                "parte_pedida": ROMANO.get(parte or 0, ""),
                "parte_certa": ROMANO.get(certa or 0, ""),
                "url_da_parte_certa": (
                    _endereco("escola_aula", curso, certa, numero) if certa else ""
                ),
            },
            status=404,
        )
    contexto_do_lugar = {
        "curso": curso,
        "parte": parte,
        "url_da_lista": _endereco("escola_aulas", curso, parte),
        "url_de_salvar": _endereco("escola_aula_salvar", curso, parte, numero),
        "url_de_publicar": _endereco("escola_aula_publicar", curso, parte, numero),
        "url_do_capitulo": _endereco("escola_capitulo", curso, parte, numero),
    }
    if desfecho != CursosClient.OK:
        contexto = {
            "admin": request.admin,
            "falha_da_sala": _falha(desfecho),
            "numero": numero,
        } | contexto_do_lugar
        if rascunho is not None:
            # A porta caiu no meio da edição: o texto NÃO se perde. Ele volta
            # para a tela, sem cabeçalho, e o botão de salvar continua lá. As
            # listas fechadas (tipos de pausa) vêm desta tela e não da porta,
            # então continuam inteiras; a de instrumentos vem da porta, e o que
            # estava escolhido segue selecionado, cru.
            contexto |= {
                "rascunho": rascunho,
                "sem_cabecalho": True,
                "erro": erro,
                "tipos_de_pausa": TIPOS_DE_PAUSA,
                "instrumentos": [],
                "instrumentos_lidos": False,
            }
        return render(request, EDITOR, contexto, status=503)

    if rascunho is None:
        rascunho = _rascunho_da_aula(aula)
    lidos, instrumentos = cliente.instrumentos()
    return render(
        request,
        EDITOR,
        {
            "admin": request.admin,
            "numero": numero,
            "aula": _cabecalho(aula),
            "rascunho": rascunho,
            "gerais": gerais or [],
            "riscas": _riscas(rascunho),
            "instrumentos": [
                {
                    "slug": str(i.get("slug") or ""),
                    "nome_canonico": str(i.get("nome_canonico") or ""),
                }
                for i in (instrumentos or [])
                if isinstance(i, dict)
            ],
            "instrumentos_lidos": lidos == CursosClient.OK,
            "tipos_de_pausa": TIPOS_DE_PAUSA,
            "erro": erro,
            "recado": recado,
            "versao_nova": versao,
        }
        | contexto_do_lugar,
        status=status,
    )


def _rascunho_do_instrumento(instrumento: dict) -> dict:
    return {
        "slug": str(instrumento.get("slug") or ""),
        "nome_canonico": str(instrumento.get("nome_canonico") or ""),
        "cartao": instrumento.get("cartao"),
        "versao": int(instrumento.get("versao") or 0),
        "escala": json.dumps(
            instrumento.get("escala") or {}, ensure_ascii=False, indent=2
        ),
        "minimo_exercicio": str(instrumento.get("minimo_exercicio") or ""),
        "minimo_contrato": str(instrumento.get("minimo_contrato") or ""),
        "secao_do_padrao": str(instrumento.get("secao_do_padrao") or ""),
        "descritores": json.dumps(
            instrumento.get("descritores") or {}, ensure_ascii=False, indent=2
        ),
        "erros": {},
    }


def _desenhar_instrumento(
    request,
    slug: str,
    *,
    rascunho: "dict | None" = None,
    gerais: "list[str] | None" = None,
    erro: str = "",
    recado: str = "",
    versao: int = 0,
    status: int = 200,
):
    # Os instrumentos são de plataforma inteira (o contrato não os escopa por
    # curso), então esta tela não tem curso próprio: a volta é para a lista do
    # curso por onde se entra. Ela vai nas TRÊS caras da tela porque o link
    # mora no alto do gabarito, fora de toda condição: faltando numa delas, a
    # volta vira `href=""` e recarrega o próprio erro.
    volta = {"url_da_lista": _endereco("escola_aulas", CURSO_PADRAO, None)}
    desfecho, instrumento = CursosClient().instrumento(slug)
    if desfecho == CursosClient.NAO_EXISTE:
        return render(
            request,
            INSTRUMENTO,
            {"admin": request.admin, "nao_existe": True, "slug": slug} | volta,
            status=404,
        )
    if desfecho != CursosClient.OK:
        contexto = {
            "admin": request.admin,
            "falha_da_sala": _falha(desfecho),
            "slug": slug,
        } | volta
        if rascunho is not None:
            contexto |= {"rascunho": rascunho, "sem_cabecalho": True, "erro": erro}
        return render(request, INSTRUMENTO, contexto, status=503)

    lido = _rascunho_do_instrumento(instrumento)
    if rascunho is not None:
        # O nome e o cartão são da lei, e vêm SEMPRE da porta: o formulário não
        # os manda, então não tem como tê-los errado.
        rascunho = rascunho | {
            "nome_canonico": lido["nome_canonico"],
            "cartao": lido["cartao"],
            "versao": lido["versao"],
        }
    return render(
        request,
        INSTRUMENTO,
        {
            "admin": request.admin,
            "rascunho": rascunho or lido,
            "gerais": gerais or [],
            "erro": erro,
            "recado": recado,
            "versao_nova": versao,
        }
        | volta,
        status=status,
    )


# ---------------------------------------------------------------------------
# AS TRÊS VISTAS
# ---------------------------------------------------------------------------
@require_GET
def aulas(request, curso: str, parte: "str | None" = None):
    """As encomendas de um curso, e quantas estão publicadas.

    Com `parte` no endereço, só aquela Parte do livro; sem ela, o curso
    inteiro, com as três Partes como seções.
    """
    site = _site_desta_requisicao(request)
    if site is None:
        return _sem_site(request)
    return _desenhar_lista(request, site, curso, int(parte) if parte else None)


@require_GET
def aula(request, curso: str, numero: str, parte: "str | None" = None):
    """Uma encomenda por dentro: o editor. O trabalho está em `_desenhar_aula`."""
    site = _site_desta_requisicao(request)
    if site is None:
        return _sem_site(request)
    bruto = (request.GET.get("versao") or "").strip()
    return _desenhar_aula(
        request,
        site,
        curso,
        numero,
        int(parte) if parte else None,
        recado=request.GET.get("recado", ""),
        versao=int(bruto) if bruto.isdigit() else 0,
    )


@require_GET
def instrumento(request, slug: str):
    """Um instrumento por dentro: a escala, os mínimos, a seção e os descritores."""
    bruto = (request.GET.get("versao") or "").strip()
    return _desenhar_instrumento(
        request,
        slug,
        recado=request.GET.get("recado", ""),
        versao=int(bruto) if bruto.isdigit() else 0,
    )


# ---------------------------------------------------------------------------
# OS TRÊS GESTOS
# ---------------------------------------------------------------------------
@require_POST
def aula_salvar(request, curso: str, numero: str, parte: "str | None" = None):
    """Grava a encomenda INTEIRA pela porta; a versão volta incrementada.

    Padrão POST-redirect-GET no sucesso, como toda escrita desta área. Na
    recusa, a tela volta com o rascunho inteiro e a frase ao lado do campo. Se
    a porta não responder, o rascunho também volta: "não sei se gravou" é a
    verdade, e o texto continua na tela para tentar de novo.

    O travessão é contado antes de mandar e vai para a auditoria como NÚMERO;
    ele nunca impede a gravação (ver o cabeçalho).
    """
    site = _site_desta_requisicao(request)
    if site is None:
        return _sem_site(request)

    na_parte = int(parte) if parte else None
    rascunho = _rascunho_do_formulario(request)
    corpo, enviados = _corpo(rascunho)
    riscas = len(_riscas(rascunho))
    desfecho, resposta = CursosClient().gravar_aula(
        site["id"], curso, numero, corpo, na_parte
    )

    if desfecho == CursosClient.OK:
        versao = int((resposta or {}).get("versao") or 0)
        _auditar(
            request,
            Registro.EDITAR_AULA,
            numero,
            Registro.OK,
            f"versao {versao}; {riscas} frase(s) com travessao",
        )
        destino = _endereco("escola_aula", curso, na_parte, numero)
        return HttpResponseRedirect(f"{destino}?recado=salva&versao={versao}")

    if desfecho == CursosClient.RECUSADO:
        gerais = _pendurar(rascunho, enviados, resposta)
        _auditar(
            request,
            Registro.EDITAR_AULA,
            numero,
            Registro.RECUSADO_PELA_CELULA,
            "recusou: " + _nomes_dos_campos_recusados(rascunho, gerais),
        )
        return _desenhar_aula(
            request,
            site,
            curso,
            numero,
            na_parte,
            rascunho=rascunho,
            gerais=gerais,
            erro="A sala de aula não aceitou a encomenda assim. Nada foi gravado; "
            "o que você escreveu continua aqui embaixo, e cada campo recusado diz o "
            "que a sala de aula não aceitou.",
            status=422,
        )

    if desfecho == CursosClient.NAO_EXISTE:
        _auditar(
            request,
            Registro.EDITAR_AULA,
            numero,
            Registro.RECUSADO_PELA_CELULA,
            "nao existe",
        )
        return _desenhar_aula(request, site, curso, numero, na_parte)

    _auditar(request, Registro.EDITAR_AULA, numero, Registro.NAO_RESPONDEU, desfecho)
    return _desenhar_aula(
        request,
        site,
        curso,
        numero,
        na_parte,
        rascunho=rascunho,
        erro=f"{_falha(desfecho)['titulo']} Não sei se a encomenda foi gravada; o que "
        "você escreveu continua aqui embaixo. Espere um minuto e salve de novo.",
        status=503,
    )


@require_POST
def aula_publicar(request, curso: str, numero: str, parte: "str | None" = None):
    """Abre a encomenda para a sala de aula. Não muda uma letra do texto.

    Exige a confirmação de uma linha (a caixa marcada): publicar é o gesto
    mais pesado desta tela, e um clique escorregado não pode abrir uma aula
    pela metade para os alunos.
    """
    site = _site_desta_requisicao(request)
    if site is None:
        return _sem_site(request)
    na_parte = int(parte) if parte else None
    if request.POST.get("confirmo") != "1":
        return _desenhar_aula(
            request,
            site,
            curso,
            numero,
            na_parte,
            erro="Para publicar, marque a caixa de confirmação ao lado do botão. "
            "Nada foi publicado.",
            status=400,
        )

    desfecho, resposta = CursosClient().publicar_aula(
        site["id"], curso, numero, na_parte
    )
    if desfecho == CursosClient.OK:
        versao = int((resposta or {}).get("versao") or 0)
        _auditar(
            request, Registro.PUBLICAR_AULA, numero, Registro.OK, f"versao {versao}"
        )
        destino = _endereco("escola_aula", curso, na_parte, numero)
        return HttpResponseRedirect(f"{destino}?recado=publicada")

    if desfecho == CursosClient.NAO_EXISTE:
        _auditar(
            request,
            Registro.PUBLICAR_AULA,
            numero,
            Registro.RECUSADO_PELA_CELULA,
            "nao existe",
        )
        return _desenhar_aula(request, site, curso, numero, na_parte)
    if desfecho == CursosClient.RECUSADO:
        gerais = _pendurar(
            {"erros": {}, "pecas": [], "quiz": [], "pausas": []}, {}, resposta
        )
        _auditar(
            request,
            Registro.PUBLICAR_AULA,
            numero,
            Registro.RECUSADO_PELA_CELULA,
            "recusou",
        )
        return _desenhar_aula(
            request,
            site,
            curso,
            numero,
            na_parte,
            gerais=gerais,
            erro="A sala de aula não deixou publicar esta encomenda ainda. Nada mudou.",
            status=422,
        )

    _auditar(request, Registro.PUBLICAR_AULA, numero, Registro.NAO_RESPONDEU, desfecho)
    return _desenhar_aula(
        request,
        site,
        curso,
        numero,
        na_parte,
        erro=f"{_falha(desfecho)['titulo']} Não sei se a encomenda foi publicada. "
        "Recarregue esta página em um minuto e olhe o estado dela.",
        status=503,
    )


def _objeto_json(texto: str) -> "tuple[dict | None, str]":
    """Um campo de JSON do formulário como objeto, ou a frase do que está errado.

    Esta é a ÚNICA validação feita deste lado, e ela existe porque a porta não
    tem como fazê-la: JSON torto nem chega a virar um corpo de pedido. Vazio é
    recusado em vez de virar `{}` por baixo dos panos: limpar o campo sem
    querer e salvar apagaria a escala de um cartão em silêncio.
    """
    texto = (texto or "").strip()
    if not texto:
        return None, "não pode ficar vazio; para deixar sem nada, escreva {}"
    try:
        valor = json.loads(texto)
    except ValueError as erro:
        return None, f"não é um JSON válido ({erro})"
    if not isinstance(valor, dict):
        return None, "precisa ser um objeto JSON, entre chaves"
    return valor, ""


@require_POST
def instrumento_salvar(request, slug: str):
    """Grava a escala, os mínimos, a seção e os descritores de um cartão."""
    dados = request.POST
    rascunho = {
        "slug": slug,
        "escala": _texto(dados.get("escala")),
        "minimo_exercicio": (dados.get("minimo_exercicio") or "").strip(),
        "minimo_contrato": (dados.get("minimo_contrato") or "").strip(),
        "secao_do_padrao": (dados.get("secao_do_padrao") or "").strip(),
        "descritores": _texto(dados.get("descritores")),
        "erros": {},
    }
    escala, erro_da_escala = _objeto_json(rascunho["escala"])
    descritores, erro_dos_descritores = _objeto_json(rascunho["descritores"])
    if erro_da_escala:
        rascunho["erros"]["escala"] = erro_da_escala
    if erro_dos_descritores:
        rascunho["erros"]["descritores"] = erro_dos_descritores
    if rascunho["erros"]:
        return _desenhar_instrumento(
            request,
            slug,
            rascunho=rascunho,
            erro="Não mandei nada para a sala de aula: um dos campos de JSON está "
            "torto, e a frase ao lado dele diz o quê. O que você escreveu continua aqui.",
            status=422,
        )

    corpo = {
        "escala": escala,
        "minimo_exercicio": rascunho["minimo_exercicio"],
        "minimo_contrato": rascunho["minimo_contrato"],
        "secao_do_padrao": rascunho["secao_do_padrao"],
        "descritores": descritores,
    }
    desfecho, resposta = CursosClient().gravar_instrumento(slug, corpo)

    if desfecho == CursosClient.OK:
        versao = int((resposta or {}).get("versao") or 0)
        _auditar(
            request, Registro.EDITAR_INSTRUMENTO, slug, Registro.OK, f"versao {versao}"
        )
        destino = reverse("escola_instrumento", args=[slug])
        return HttpResponseRedirect(f"{destino}?recado=salvo&versao={versao}")

    if desfecho == CursosClient.RECUSADO:
        rascunho_com_listas = rascunho | {"pecas": [], "quiz": [], "pausas": []}
        gerais = _pendurar(rascunho_com_listas, {}, resposta)
        _auditar(
            request,
            Registro.EDITAR_INSTRUMENTO,
            slug,
            Registro.RECUSADO_PELA_CELULA,
            "recusou: " + (", ".join(rascunho["erros"]) or "geral"),
        )
        return _desenhar_instrumento(
            request,
            slug,
            rascunho=rascunho,
            gerais=gerais,
            erro="A sala de aula não aceitou o instrumento assim. Nada foi gravado; "
            "o que você escreveu continua aqui embaixo.",
            status=422,
        )

    if desfecho == CursosClient.NAO_EXISTE:
        _auditar(
            request,
            Registro.EDITAR_INSTRUMENTO,
            slug,
            Registro.RECUSADO_PELA_CELULA,
            "nao existe",
        )
        return _desenhar_instrumento(request, slug)

    _auditar(
        request, Registro.EDITAR_INSTRUMENTO, slug, Registro.NAO_RESPONDEU, desfecho
    )
    return _desenhar_instrumento(
        request,
        slug,
        rascunho=rascunho,
        erro=f"{_falha(desfecho)['titulo']} Não sei se o instrumento foi gravado; o que "
        "você escreveu continua aqui embaixo. Espere um minuto e salve de novo.",
        status=503,
    )
