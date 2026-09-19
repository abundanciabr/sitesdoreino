"""`/admin/escola/cursos/` — a lista dos cursos da escola, e o gesto Novo curso.

Até 7 de setembro de 2026 a sala de aula servia UM curso: o editor entrava por
uma constante escrita no código (`CURSO_PADRAO = "profissional"`), e criar o
segundo curso exigiria um bloco de colar no servidor. O mantenedor decidiu o
contrário, com estas palavras: *"quero criar uma estrutura que sirva para vários
cursos e não apenas para um único curso, de modo que seja fácil de criar outros
cursos depois"* (`docs/decisoes/DECISAO-a-sala-serve-varios-cursos.md`).

Esta tela é o lugar onde isso acontece. Ela faz três coisas, e nenhuma a mais:

1. **Lista** os cursos deste site, cada um com a regra de avanço escrita em
   português, o produto do catálogo a que aponta, quantas aulas já estão
   publicadas e o link para escrever as aulas.
2. **Cria** um curso: nome, apelido, produto (um do catálogo, ou um novo com o
   nome do curso) e a regra de avanço.
3. **Troca** o produto ou a regra de um curso que já existe.

## Nada aqui é desta célula

Curso é dado da `cursos`, produto é dado do `catalogo`, e os dois entram e saem
pelas portas de máquina dos contratos congelados. Esta célula não guarda cópia
de nenhum dos dois: ela pergunta a cada abertura de tela. Duas listas
divergiriam no primeiro curso novo, e a que ninguém olha é a que fica errada.

## "Não sei" e "não tem" são telas diferentes

A lição do painel da escola (`LICOES.md`, 28/08/2026) vale inteira aqui, e em
três lugares:

- curso com `produto_id` vazio: **ninguém entra ainda**, e a sala está fechada
  de propósito;
- curso cujo produto não está na lista de ativos do catálogo: o produto
  **existe e não é ativo** (ou foi aposentado), e a tela mostra o apelido dele
  em vez de dizer que não há produto;
- catálogo fora do ar: **não deu para ler o nome**, e nenhuma das duas frases
  acima cabe.

Trocar qualquer uma pelas outras manda o mantenedor para o lado errado: uma
pede que ele aponte um produto, a outra pede que ele olhe o catálogo.

## Criar um produto e criar o curso são DUAS portas, e a metade é o caso caro

Quando o produto é novo, o gesto atravessa `createProduct` (catálogo) e depois
`createCourse` (sala de aula). Se a segunda falhar, o produto já existe — e a
tela diz exatamente isso, em vez de fingir que nada aconteceu. `createProduct` é
idempotente pelo apelido (mesmo apelido e mesmo nome respondem 200 com o que já
existe), então reenviar o formulário é seguro e não duplica nada. A ordem é essa
e não a inversa: um curso apontando para um produto que não nasceu fecharia a
sala para todo mundo, sem nada na tela dizendo por quê.

## Formulário normal, POST por gesto, sem uma linha de script

A política de segurança desta área exige um hash na CSP para cada script
embutido (`armadilhas/199`), e um POST por gesto deixa a tela mostrando sempre o
que está de fato gravado. Os gestos redesenham a lista lendo as portas de novo,
como o importador do sumário faz: o resultado que a pessoa lê é o estado real,
nunca o que esta tela achou que tinha acontecido.
"""

from __future__ import annotations

import unicodedata

from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from apps.auditoria.models import Registro

from .aulas import CursosClient, _falha, _site_desta_requisicao
from .clients import CatalogoClient
from .views import _auditar

TELA = "admin/escola_cursos.html"

#: As duas regras de avanço do contrato (`Progressao`), com a frase que o
#: mantenedor lê. A palavra de máquina nunca chega à tela: ele escolhe pela
#: frase, e é a frase que diz o que muda para o aluno.
PROGRESSAO = {
    "por_laudo": "A próxima aula abre com o laudo da professora",
    "livre": "A próxima aula abre quando o aluno conclui a anterior",
}

#: `slug` é `^[a-z0-9-]{1,64}$` no contrato de `createCourse` e no de
#: `createProduct`. Todo apelido, gerado do nome ou digitado, passa por
#: `apelido_de` antes de chegar às portas: vira minúsculo, sem acento, com
#: hífens e no máximo este tamanho. Ninguém é recusado por ter digitado
#: "Modelagem 3D": o que a tela recusa, com frase própria, é só o apelido que
#: fica vazio depois da limpeza, porque esse a porta recusaria com 422 genérico.
TETO_DO_APELIDO = 64


def apelido_de(nome: str) -> str:
    """O apelido do endereço, gerado do nome: minúsculo, sem acento, com hífens.

    Existe para que o mantenedor não precise inventar um apelido de endereço
    toda vez: ele escreve "Modelagem 3D Avançada" e o curso mora em
    `/cursos/modelagem-3d-avancada/`. Devolve texto vazio quando o nome não tem
    nenhuma letra nem dígito aproveitável, e aí a tela pede o apelido em vez de
    mandar à porta um `slug` que ela recusaria.
    """
    sem_acento = unicodedata.normalize("NFKD", nome)
    sem_acento = "".join(
        letra for letra in sem_acento if not unicodedata.combining(letra)
    )
    pedacos: list[str] = []
    atual = ""
    for letra in sem_acento.lower():
        if letra.isascii() and letra.isalnum():
            atual += letra
        elif atual:
            pedacos.append(atual)
            atual = ""
    if atual:
        pedacos.append(atual)
    return "-".join(pedacos)[:TETO_DO_APELIDO].strip("-")


def _produto_do_curso(produto_id: str, produtos: "dict | None") -> dict:
    """Como a tela mostra o produto de um curso — as quatro situações.

    `produtos` é o mapa id -> nome dos ATIVOS do catálogo, ou `None` quando não
    deu para perguntar. As quatro saídas são telas diferentes de propósito.
    """
    if not produto_id:
        return {"frase": "sem produto: ninguém entra ainda", "alerta": True}
    if produtos is None:
        return {"frase": "não consegui ler o nome do produto agora", "alerta": False}
    nome = produtos.get(produto_id)
    if nome:
        return {"frase": nome, "alerta": False}
    return {
        "frase": f"o produto {produto_id} não está na lista de ativos do catálogo",
        "alerta": True,
    }


def _linha(curso: dict, produtos: "dict | None") -> dict:
    progressao = str(curso.get("progressao") or "")
    return {
        "slug": str(curso.get("slug") or ""),
        "nome": str(curso.get("nome") or ""),
        "estado": str(curso.get("estado") or ""),
        "progressao": progressao,
        # Regra que a porta mandar fora do vocabulário do contrato não vira uma
        # das duas frases: a tela mostra o que veio, e alguém olha do lado de lá.
        "progressao_frase": PROGRESSAO.get(progressao, progressao),
        "produto": _produto_do_curso(str(curso.get("produto_id") or ""), produtos),
        "total_de_aulas": int(curso.get("total_de_aulas") or 0),
        "aulas_publicadas": int(curso.get("aulas_publicadas") or 0),
    }


def _sem_site(request):
    """O catálogo não respondeu, então não sei de qual escola são os cursos.

    Sem `site_id` a porta responde 422 (Lei 9), e chutar um site seria pior que
    não abrir: mostraria os cursos de outro domínio.
    """
    return render(request, TELA, {"admin": request.admin, "sem_site": True}, status=503)


def _desenhar(request, site: dict, contexto: dict, status: int = 200):
    """A tela inteira, lida das duas portas a cada vez.

    Os gestos passam por aqui depois de gravar: o que a pessoa lê é o estado
    real das outras células, e não o que esta tela achou que aconteceu. O site
    chega pronto porque quem grava já precisou dele: perguntar de novo ao
    catálogo seria uma segunda ida à rede pela mesma resposta.
    """
    desfecho, cursos = CursosClient().cursos(site["id"])
    if desfecho != CursosClient.OK:
        return render(
            request,
            TELA,
            {"admin": request.admin, "falha_da_sala": _falha(desfecho)} | contexto,
            status=503,
        )

    lidos = CatalogoClient().listar_produtos()
    produtos = (
        None
        if lidos is None
        else {
            str(p.get("id") or ""): str(p.get("name") or "")
            for p in lidos
            if isinstance(p, dict)
        }
    )
    return render(
        request,
        TELA,
        {
            "admin": request.admin,
            "cursos": [
                _linha(c, produtos) for c in cursos or [] if isinstance(c, dict)
            ],
            "progressoes": list(PROGRESSAO.items()),
            # A lista para ESCOLHER (só os ativos, em ordem de nome, como o
            # catálogo manda) e o aviso de quando ela não pôde ser lida são
            # coisas separadas: sem a segunda, catálogo fora do ar viraria uma
            # tela dizendo que não há produto nenhum.
            "produtos": [] if produtos is None else list(produtos.items()),
            "catalogo_calado": produtos is None,
        }
        | contexto,
        status=status,
    )


@require_GET
def escola_cursos(request):
    """A lista dos cursos da escola, e o formulário de criar um."""
    site = _site_desta_requisicao(request)
    if site is None:
        return _sem_site(request)
    return _desenhar(request, site, {})


@require_POST
def escola_curso_criar(request):
    """Novo curso: o produto primeiro (se for novo), o curso depois.

    A ordem importa e não é simétrica. O produto é a chave de quem entra no
    curso; criar o curso antes dele deixaria a sala fechada com o formulário já
    limpo, sem nada na tela dizendo por quê. Do jeito certo, a metade que pode
    sobrar é um produto sem curso — e essa a tela sabe explicar e reaproveitar.
    """
    site = _site_desta_requisicao(request)
    if site is None:
        return _sem_site(request)

    nome = (request.POST.get("nome") or "").strip()
    apelido = (request.POST.get("apelido") or "").strip()
    escolha = (request.POST.get("produto") or "").strip()
    progressao = (request.POST.get("progressao") or "").strip()

    rascunho = {
        "nome": nome,
        "apelido": apelido,
        "produto": escolha,
        "progressao": progressao,
    }

    if not nome:
        return _desenhar(
            request,
            site,
            {"rascunho": rascunho, "erro": "Escreva o nome do curso. Nada foi criado."},
            status=400,
        )
    if not progressao:
        return _desenhar(
            request,
            site,
            {
                "rascunho": rascunho,
                "erro": "Escolha como a próxima aula abre para o aluno. Nada foi "
                "criado: essa regra não tem valor padrão de propósito, porque "
                "trocá-la depois muda a vida de todos os alunos do curso.",
            },
            status=400,
        )
    if progressao not in PROGRESSAO:
        return _desenhar(
            request,
            site,
            {
                "rascunho": rascunho,
                "erro": "Essa regra de avanço não existe. Escolha uma das duas da "
                "lista. Nada foi criado.",
            },
            status=400,
        )
    if not escolha:
        return _desenhar(
            request,
            site,
            {
                "rascunho": rascunho,
                "erro": "Escolha o produto do curso, ou peça para criar um produto "
                "novo com o nome dele. Sem produto ninguém entra na sala, e "
                "nada foi criado.",
            },
            status=400,
        )

    apelido = apelido_de(apelido or nome)
    if not apelido:
        return _desenhar(
            request,
            site,
            {
                "rascunho": rascunho,
                "erro": "Não consegui montar o apelido do endereço com esse nome: "
                "escreva o apelido você mesmo, com letras minúsculas, números "
                "e hífens. Nada foi criado.",
            },
            status=400,
        )

    produto_id = escolha
    if escolha == "novo":
        desfecho, corpo = CatalogoClient().criar_produto(apelido, nome)
        if desfecho == CatalogoClient.JA_EXISTE:
            return _desenhar(
                request,
                site,
                {
                    "rascunho": rascunho,
                    "erro": f"O catálogo recusou o produto novo: {corpo} Escolha "
                    "outro apelido para o curso, ou escolha na lista o produto "
                    "que já existe. Nada foi criado.",
                },
                status=409,
            )
        if desfecho == CatalogoClient.RECUSADO:
            return _desenhar(
                request,
                site,
                {
                    "rascunho": rascunho,
                    "erro": f"O catálogo não aceitou o produto novo: {corpo} "
                    "Corrija e envie de novo. Nada foi criado.",
                },
                status=400,
            )
        if desfecho != CatalogoClient.OK:
            return _desenhar(
                request,
                site,
                {
                    "rascunho": rascunho,
                    "erro": "O catálogo não respondeu, e sem produto o curso não "
                    "nasce. Nada foi criado. Espere um minuto e envie de novo.",
                },
                status=503,
            )
        produto_id = str((corpo or {}).get("id") or "")

    desfecho, criado = CursosClient().criar_curso(
        site["id"],
        {
            "slug": apelido,
            "nome": nome,
            "progressao": progressao,
            "produto_id": produto_id,
        },
    )
    return _depois_de_criar(
        request, site, desfecho, criado, rascunho, apelido, nome, escolha, produto_id
    )


def _metade_feita(nome: str, escolha: str) -> str:
    """A frase do caso em que o produto nasceu e o curso não.

    Ela só existe quando o produto foi criado NESTE envio: dizer isso quando o
    produto já era escolhido na lista mandaria o mantenedor procurar um problema
    que não houve.
    """
    if escolha != "novo":
        return ""
    return (
        f" O produto {nome} já existe no catálogo, e continua lá. Aperte Criar o "
        "curso de novo: o produto não vai ser duplicado."
    )


def _rastro_do_produto(escolha: str, produto_id: str) -> str:
    """O que a auditoria guarda sobre o produto: o id que ficou ligado ao curso
    (é ele que a matrícula compara), e se nasceu neste envio ou já existia."""
    origem = "criado neste envio" if escolha == "novo" else "escolhido na lista"
    return f"produto_id: {produto_id or 'nenhum'} ({origem})"


def _depois_de_criar(
    request, site, desfecho, criado, rascunho, apelido, nome, escolha, produto_id
):
    rastro = _rastro_do_produto(escolha, produto_id)
    if desfecho == CursosClient.OK:
        _auditar(request, Registro.CRIAR_CURSO, apelido, Registro.OK, rastro)
        criado_nome = str((criado or {}).get("nome") or nome)
        return _desenhar(
            request,
            site,
            {
                "recado": f"O curso {criado_nome} foi criado. Agora escreva as aulas "
                "dele: enquanto nenhuma estiver publicada, o aluno abre a sala "
                "e não encontra nada."
            },
        )

    _auditar(
        request,
        Registro.CRIAR_CURSO,
        apelido,
        (
            Registro.RECUSADO_PELA_CELULA
            if desfecho in (CursosClient.RECUSADO, CursosClient.JA_EXISTE)
            else Registro.NAO_RESPONDEU
        ),
        f"{rastro}; desfecho: {desfecho}",
    )
    metade = _metade_feita(nome, escolha)
    if desfecho == CursosClient.JA_EXISTE:
        return _desenhar(
            request,
            site,
            {
                "rascunho": rascunho,
                "erro": f"A sala de aula recusou: {_frase(criado)} O apelido é a "
                "identidade do curso e não muda depois, então escolha outro." + metade,
            },
            status=409,
        )
    if desfecho == CursosClient.RECUSADO:
        return _desenhar(
            request,
            site,
            {
                "rascunho": rascunho,
                "erro": f"A sala de aula não aceitou o curso: {_frase(criado)} "
                "Corrija e envie de novo." + metade,
            },
            status=400,
        )
    return _desenhar(
        request,
        site,
        {
            "rascunho": rascunho,
            "erro": "A sala de aula não respondeu, e por isso não sei se o curso foi "
            "criado. Recarregue esta página em um minuto: se ele aparecer na "
            "lista, está feito." + metade,
        },
        status=503,
    )


def _frase(detalhe) -> str:
    """A recusa da outra célula, mostrada verbatim, ou uma frase honesta.

    A regra é de lá, e reescrevê-la aqui daria duas redações para o mesmo não —
    e a que ninguém testa é a que fica errada.
    """
    if isinstance(detalhe, str) and detalhe.strip():
        return detalhe.strip()
    if isinstance(detalhe, list) and detalhe:
        return "; ".join(str(item.get("msg", item)) for item in detalhe)
    return "ela não disse o motivo."


@require_POST
def escola_curso_alterar(request):
    """Trocar o produto OU a regra de avanço de um curso que já existe.

    Um gesto por formulário, e o corpo leva só o campo daquele formulário:
    `putCourse` trata campo ausente como NÃO MEXER, então mandar os dois de uma
    vez gravaria de novo o que ninguém pediu para trocar.
    """
    site = _site_desta_requisicao(request)
    if site is None:
        return _sem_site(request)

    curso = (request.POST.get("curso") or "").strip()
    produto_id = request.POST.get("produto_id")
    progressao = request.POST.get("progressao")

    corpo: dict = {}
    campos: list[str] = []
    if produto_id is not None:
        corpo["produto_id"] = produto_id.strip()
        campos.append("produto")
    if progressao is not None:
        if progressao.strip() not in PROGRESSAO:
            return _desenhar(
                request,
                site,
                {
                    "erro": "Essa regra de avanço não existe. Escolha uma das duas "
                    "da lista. Nada foi trocado."
                },
                status=400,
            )
        corpo["progressao"] = progressao.strip()
        campos.append("regra de avanço")

    if not curso or not corpo:
        return _desenhar(
            request,
            site,
            {
                "erro": "Escolha o que trocar antes de enviar. Nada foi trocado.",
            },
            status=400,
        )

    desfecho, resposta = CursosClient().alterar_curso(site["id"], curso, corpo)
    _auditar(
        request,
        Registro.EDITAR_CURSO,
        curso,
        (
            Registro.OK
            if desfecho == CursosClient.OK
            else (
                Registro.RECUSADO_PELA_CELULA
                if desfecho == CursosClient.RECUSADO
                else Registro.NAO_RESPONDEU
            )
        ),
        # QUAIS campos mudaram, nunca os valores (`LICOES.md`, 28/08/2026).
        f"campos: {', '.join(campos)}",
    )

    if desfecho == CursosClient.OK:
        recado = (
            f"O produto do curso {curso} foi trocado. Quem entra nele mudou a partir "
            "de agora; quem já está matriculado continua onde está."
            if "produto" in campos
            else f"A regra de avanço do curso {curso} foi trocada. Ela vale para "
            "todos os alunos dele a partir de agora."
        )
        return _desenhar(request, site, {"recado": recado})
    if desfecho == CursosClient.NAO_EXISTE:
        return _desenhar(
            request,
            site,
            {
                "erro": f"Não existe nenhum curso {curso} nesta escola, e nada foi "
                "trocado. Recarregue esta página: a lista abaixo é a de verdade."
            },
            status=404,
        )
    if desfecho == CursosClient.RECUSADO:
        return _desenhar(
            request,
            site,
            {"erro": f"A sala de aula não aceitou a troca: {_frase(resposta)}"},
            status=400,
        )
    return _desenhar(
        request,
        site,
        {
            "erro": "A sala de aula não respondeu, e por isso não sei se a troca "
            "valeu. Recarregue esta página em um minuto: a lista abaixo mostra "
            "como o curso está de verdade."
        },
        status=503,
    )
