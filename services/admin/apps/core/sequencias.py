"""`/admin/escola/jornadas/` — onde o mantenedor vê e edita as sequências de
mensagens da escola, sozinho, sem robô e sem publicação de código.

Degrau 7 do `docs/decisoes/PLANO-SEQUENCIAS-DE-MENSAGENS.md` (§8.3), e ele parou
em 03/09/2026 antes da primeira linha de código porque entre esta célula e o
`mensageria_db` não existia caminho nenhum (`armadilhas/311`). Hoje existe: a
porta de máquina da `mensageria` está no ar e o contrato foi congelado no Rito
de 04/09/2026, com o mantenedor presente (registro `20260904-070`).

## A metade que faz esta tela valer, e é a mais fácil de cortar por engano

O que foi **BARRADO, e POR QUÊ**. Sem isso, "por que o aluno X não recebeu?"
fica sem resposta e ele olha para o silêncio. A tabela `Entrega` do outro lado
guarda também o que NÃO saiu, e a operação `listDeliveries` a devolve com o
`resultado` e o `motivo` que a régua escreveu. Uma linha por passo E POR CANAL,
porque sino entregue, e-mail devolvido e WhatsApp barrado são três resultados
independentes.

## Como esta tela traduz, e onde ela deliberadamente NÃO traduz

O `resultado`, a `classe`, o `canal`, o `estado` e a `condicao_slug` são
**vocabulários fechados do contrato**, e as frases em português para cada um
moram aqui (mesma regra de `apps/core/economia.py`: a porta manda slug, nunca
frase pronta, porque o site serve três idiomas e esta área é só português).

O `motivo` é **texto livre que a régua escreveu**, e ele sai VERBATIM, com o
rótulo "o que a régua anotou". A tentação é reescrevê-lo em português mais
bonito casando o começo da frase ("ja recebeu", "fora da janela"), e isso seria
amarrar esta tela à REDAÇÃO de uma mensagem da outra célula: no dia em que ela
mudasse uma palavra, a tradução cairia para o caso genérico sem nada ficar
vermelho. O que traduz é o vocabulário fechado; o texto livre acompanha como
detalhe. "Barrada pela régua" (daqui) mais "ja recebeu 1 hoje (teto de 1 por
dia)" (de lá) é exatamente a frase que o plano pede, e nenhuma metade dela
depende de adivinhar a outra.

## As duas decisões que o mantenedor tomou no Rito, e que esta tela honra

1. **A tela liga e desliga.** Até o Rito, ligar uma sequência só acontecia por
   um comando de terminal, que ele não roda. `setJourneyActive` descreve o
   ESTADO desejado, e a resposta traz `mudou` e `inscricoes_andando`, que viram
   frase na tela. **Desligar significa que ninguém NOVO entra**, e quem já está
   no meio termina; a tela diz isso com o número, em vez de sugerir que tudo
   parou. Ligar sem versão publicada é 409, e a tela explica o porquê em
   português em vez de mostrar um erro cru.
2. **Quem já entrou termina com o texto antigo.** Salvar uma frase PUBLICA UMA
   VERSÃO NOVA (versão publicada é imutável por gatilho no Postgres), e a porta
   devolve o número da que nasceu. A tela diz isso na hora, com o número: sem
   essa frase ele acharia que a correção não pegou.

## Onde o dado mora, e por que não aqui

Na célula `mensageria`. Esta tela **não guarda nada**: lê tudo pela porta de
máquina e mostra. Guardar uma cópia (de um texto, de um contador, de uma lista
de sequências) seria o mesmo fato em dois lugares, a lei anti-duplicação do
`CLAUDE.md`, e no dia em que os dois discordassem esta tela mostraria um texto
e o aluno receberia outro.

## Quem autoriza é ESTA célula

A `mensageria` não assina sessão: ela não serve página nenhuma, não tem rota no
Traefik e só é alcançável de dentro da rede do Docker. O crachá que vale é o
desta área, que a porta do `/admin/` já exige; o Bearer do par prova só QUEM
CHAMA. Mesmo desenho de `/admin/economia/` e `/admin/menu/`.

## Por que é formulário simples, sem script

Cada gesto é um POST que recarrega a página, como em `/admin/economia/`, pelas
mesmas três razões: o que se vê é o que está gravado; a política de segurança
desta área exige um hash na CSP para cada script embutido (`armadilhas/199`), e
um formulário não precisa de nenhum; e o mantenedor é leigo, então um botão por
gesto, com o nome do gesto escrito nele, não tem como ser mal entendido.
"""

from __future__ import annotations

from datetime import datetime

from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.auditoria.models import Registro

from .clients import CatalogoClient, MensageriaClient
from .views import _auditar

LISTA = "admin/escola_sequencias.html"
DENTRO = "admin/escola_sequencia.html"

# ---------------------------------------------------------------------------
# O DICIONÁRIO DA TELA — os vocabulários fechados do contrato, em português
# ---------------------------------------------------------------------------
# Slug que aparecer aqui sem tradução mostra o PRÓPRIO SLUG, que é feio mas
# honesto: esconder uma linha da tela dele seria pior. Mesma escolha de
# `apps/core/economia.py::TRADUCAO`.

NOME_DA_SEQUENCIA = {
    "boas-vindas": "Boas-vindas",
}

GATILHO = {
    "identidade.pessoa-cadastrada": "quando alguém termina o cadastro no site",
    "aluno.inatividade-detectada": "quando alguém fica dias sem aparecer",
}

# A classe decide, ANTES de tudo, se a régua anti-chateação se aplica (§6 do
# plano). É a informação que explica por que um aviso de senha nunca é barrado e
# uma mensagem de incentivo pode ser.
CLASSE = {
    "critica": (
        "Crítica",
        "Passa por fora da régua inteira. Um aviso de senha não espera vaga no "
        "dia nem horário de janela.",
    ),
    "transacional": (
        "De serviço",
        "Passa por fora da régua inteira: matrícula liberada, pagamento, acesso.",
    ),
    "relacional": (
        "De relacionamento",
        "A régua se aplica: entra na conta de quantas a pessoa já recebeu hoje.",
    ),
    "engajamento": (
        "De incentivo",
        "A régua se aplica: entra na conta de quantas a pessoa já recebeu hoje.",
    ),
}

# DOIS MAPAS PARA O MESMO VOCABULÁRIO, e não é desleixo: é português.
#
# A tela usa o canal em duas posições gramaticais diferentes, e a preposição
# contrai com o artigo numa delas. Com um mapa só, a linha da entrega saía como
# *"Mensagem 2, por o sininho dentro do site"* — apanhado na prévia renderizada
# com dados reais, que é exatamente para isso que a prévia existe.
CANAL = {
    "sino": "o sininho dentro do site",
    "email": "e-mail",
    "whatsapp": "WhatsApp",
}

# A mesma coisa, na posição em que vem depois de "por".
CANAL_POR = {
    "sino": "pelo sininho dentro do site",
    "email": "por e-mail",
    "whatsapp": "pelo WhatsApp",
}

IDIOMA = {
    "pt-br": "Português",
    "en": "Inglês",
    "es": "Espanhol",
}

CONDICAO = {
    "": "Sai para todo mundo que chegar neste passo.",
    "ainda-nao-entrou-em-aula": "Só sai para quem ainda não entrou em nenhuma aula.",
    "ainda-nao-postou-no-forum": "Só sai para quem ainda não escreveu no fórum.",
    "sem-atividade-ha-5-dias": "Só sai para quem está sem aparecer há cinco dias.",
}

ESTADO_DA_INSCRICAO = {
    "andando": (
        "Está recebendo",
        "A pessoa está no meio da sequência e ainda tem passos pela frente.",
    ),
    "concluida": ("Terminou", "A pessoa chegou ao fim da sequência."),
    "saiu": ("Saiu no meio", "A sequência parou para esta pessoa antes do fim."),
    "cancelada": ("Cancelada", "A sequência foi interrompida para esta pessoa."),
}

# O CORAÇÃO DESTA TELA. Sem estas quatro linhas, "por que o aluno X não
# recebeu?" fica sem resposta e o mantenedor olha para o silêncio.
RESULTADO = {
    "enviada": ("Enviada", "Saiu daqui para a pessoa."),
    # A explicação cobre as DUAS causas reais de um pulo, e não só a bonita. A
    # primeira versão dizia apenas "ela já tinha feito o que a mensagem ia
    # pedir" — e hoje, em produção, a causa MAIS COMUM é a outra: o e-mail
    # ainda é um esboço, e o motor grava `pulada` com "a plataforma ainda nao
    # entrega pelo canal email". Dizer só a primeira faria o mantenedor
    # concluir que o aluno estava adiantado, quando na verdade a escola é que
    # ainda não sabe mandar. A anotação ao lado separa os dois casos.
    "pulada": (
        "Pulada",
        "Não foi enviada e não foi barrada. Ou a condição do passo deixou de "
        "valer para esta pessoa (ela já tinha feito o que a mensagem ia "
        "pedir), ou a escola ainda não sabe entregar por esse canal. A "
        "anotação ao lado diz qual dos dois foi.",
    ),
    "barrada_pela_regua": (
        "Barrada pela régua",
        "A régua anti-chateação segurou esta mensagem. Ela guarda duas coisas: "
        "quantas a pessoa já recebeu hoje, e o horário em que é educado "
        "escrever. Nada se perdeu: o que foi barrado é remarcado.",
    ),
    "barrada_por_preferencia": (
        "Barrada por escolha da pessoa",
        "Ela pediu para não receber este tipo de mensagem neste canal, e a "
        "escola respeita.",
    ),
}


def _traduzir(dicionario: dict, chave: str) -> tuple:
    """A tradução, ou o slug cru quando não houver uma. Nunca esconde a linha."""
    return dicionario.get(chave, (chave, ""))


def _numero(bruto) -> "int | None":
    """Um texto de formulário como inteiro, ou `None`. Lixo vira `None`."""
    bruto = (bruto or "").strip()
    return int(bruto) if bruto.isdigit() else None


def _quando(atraso_segundos: int) -> str:
    """`atraso_segundos` em português, e ele conta a partir da ENTRADA.

    Nunca a partir do passo anterior: é a escolha do §5 do plano (o cronograma é
    ancorado em `ancora_em`, e atraso da régua não empurra os passos seguintes),
    e uma tela que dissesse "dois dias depois da anterior" mentiria sobre quando
    a mensagem sai.
    """
    if atraso_segundos <= 0:
        return "Na hora em que a pessoa entra na sequência."
    dias, resto = divmod(int(atraso_segundos), 86400)
    horas = resto // 3600
    if dias and horas:
        return f"{dias} dia{'s' if dias > 1 else ''} e {horas}h depois de entrar."
    if dias:
        return f"{dias} dia{'s' if dias > 1 else ''} depois de entrar."
    if horas:
        return f"{horas} hora{'s' if horas > 1 else ''} depois de entrar."
    minutos = max(1, resto // 60)
    return f"{minutos} minuto{'s' if minutos > 1 else ''} depois de entrar."


def _momento(bruto) -> str:
    """Um instante da porta em português, no fuso de quem lê esta tela.

    O contrato manda data como texto ISO (`2026-09-04T18:30:00+00:00`), e o
    filtro `|date` do Django só formata objeto de data: passar a string a ele
    devolve a string crua, e o mantenedor leria um carimbo de máquina no meio de
    uma frase em português. A conversão mora AQUI, e não no molde, porque o
    fuso é `America/Sao_Paulo` e a porta fala UTC: sem o `localtime`, uma
    mensagem das 21h de sábado apareceria como meia-noite de domingo.

    Texto que não for data sai CRU em vez de sumir. Esconder a linha porque um
    campo veio estranho é o tipo de silêncio que faz o mantenedor procurar o
    problema no lugar errado.
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

    Mesmo padrão de `apps/core/avisos.py` e `apps/core/menu.py::_carregar`: quem
    abre esta tela num domínio vê as sequências DAQUELE domínio. Toda operação
    da porta é escopada por `site_id` (CONSTITUICAO Lei 9), e sem ele a porta
    responde 422 em vez de uma lista vazia que pareceria resposta.
    """
    return CatalogoClient().site_por_host(request.get_host().split(":")[0].lower())


# ---------------------------------------------------------------------------
# AS LINHAS QUE A TELA DESENHA
# ---------------------------------------------------------------------------
def _linha_de_sequencia(jornada: dict) -> dict:
    """Uma sequência como a lista a desenha."""
    slug = str(jornada.get("slug", ""))
    gatilho = str(jornada.get("gatilho", ""))
    publicada = jornada.get("versao_publicada") or None
    return {
        "slug": slug,
        "nome": NOME_DA_SEQUENCIA.get(slug, slug),
        "gatilho": GATILHO.get(gatilho, gatilho),
        "ativa": bool(jornada.get("ativa")),
        "versoes": int(jornada.get("versoes") or 0),
        "versao_publicada": (None if publicada is None else publicada.get("numero")),
    }


def _linha_de_passo(passo: dict) -> dict:
    """Um passo como a tela o desenha, com o texto de cada idioma."""
    classe, o_que_a_classe_significa = _traduzir(CLASSE, str(passo.get("classe", "")))
    condicao_slug = str(passo.get("condicao_slug", ""))
    textos = passo.get("textos") or []
    # O TÍTULO DO CARTÃO É O QUE A PESSOA VÊ, e não o `assunto` do passo.
    #
    # `assunto` é vocabulário FECHADO de máquina (`jornada.passo`,
    # `gamificacao.nivel-alcancado`): é o nome do acontecimento no barramento de
    # eventos, não o nome da mensagem. Escrito no cabeçalho, ele saía como
    # "Mensagem 1: jornada.passo", que não diz nada a ninguém — apanhado na
    # prévia renderizada com dados reais. O que serve de título é a frase que o
    # aluno lê, e a de português vem primeiro porque esta área é só em português.
    em_portugues = next((t for t in textos if t.get("idioma") == "pt-br"), None)
    primeiro = em_portugues or (textos[0] if textos else {})
    return {
        "ordem": int(passo.get("ordem") or 0),
        "quando": _quando(int(passo.get("atraso_segundos") or 0)),
        "titulo": str(primeiro.get("assunto_visivel") or ""),
        "classe": classe,
        "classe_explicacao": o_que_a_classe_significa,
        "canais": [CANAL.get(c, c) for c in passo.get("canais") or []],
        "condicao": CONDICAO.get(condicao_slug, condicao_slug),
        "textos": [
            {
                "idioma": str(t.get("idioma") or ""),
                "idioma_nome": IDIOMA.get(
                    str(t.get("idioma") or ""), str(t.get("idioma") or "")
                ),
                "assunto_visivel": str(t.get("assunto_visivel") or ""),
                "corpo": str(t.get("corpo") or ""),
            }
            for t in textos
        ],
    }


def _linha_de_inscricao(inscricao: dict) -> dict:
    """Uma pessoa dentro da sequência, como a tela a desenha.

    O `destinatario_id` é o id OPACO de plataforma, e é tudo que a porta manda:
    nem e-mail, nem nome, nem telefone saem da `mensageria`, que sequer os
    guarda (invariante 1 do contrato). A tela mostra o id como ele é, em vez de
    prometer um nome que não tem de onde vir.
    """
    estado = str(inscricao.get("estado", ""))
    rotulo, explicacao = _traduzir(ESTADO_DA_INSCRICAO, estado)
    return {
        "inscricao_id": str(inscricao.get("inscricao_id") or ""),
        "destinatario_id": str(inscricao.get("destinatario_id") or ""),
        "estado": estado,
        "estado_rotulo": rotulo,
        "estado_explicacao": explicacao,
        "passo_atual": int(inscricao.get("passo_atual") or 0),
        "versao_numero": int(inscricao.get("versao_numero") or 0),
        "proximo_em": _momento(inscricao.get("proximo_em")),
        "motivo_de_saida": str(inscricao.get("motivo_de_saida") or ""),
        "criada_em": _momento(inscricao.get("criada_em")),
    }


def _linha_de_entrega(entrega: dict) -> dict:
    """Uma entrega, ou uma NÃO-entrega, como a tela a desenha.

    `motivo` sai VERBATIM: é texto livre que a régua escreveu, e reescrevê-lo
    aqui casando o começo da frase amarraria esta tela à redação de uma mensagem
    da outra célula (ver o cabeçalho deste arquivo). O que traduz é o
    `resultado`, que é vocabulário fechado do contrato.
    """
    canal = str(entrega.get("canal", ""))
    resultado = str(entrega.get("resultado", ""))
    rotulo, explicacao = _traduzir(RESULTADO, resultado)
    return {
        "ordem": int(entrega.get("ordem") or 0),
        "canal": CANAL_POR.get(canal, f"por {canal}"),
        "resultado": resultado,
        "resultado_rotulo": rotulo,
        "resultado_explicacao": explicacao,
        "barrada": resultado.startswith("barrada"),
        "saiu": resultado == "enviada",
        "motivo": str(entrega.get("motivo") or ""),
        "previsto_para": _momento(entrega.get("previsto_para")),
        "reagendado_para": _momento(entrega.get("reagendado_para")),
        "enviado_em": _momento(entrega.get("enviado_em")),
    }


# ---------------------------------------------------------------------------
# AS DUAS TELAS, DESENHADAS SEMPRE DO QUE ESTÁ GRAVADO
# ---------------------------------------------------------------------------
# As duas funções abaixo são as únicas que renderizam, e as views e os gestos
# passam por elas. É o padrão de `economia.py::_voltar_com_erro`: depois de uma
# recusa, a tela precisa mostrar o que ESTÁ gravado, e nunca o gesto que não
# pegou — uma página que exibisse o texto recusado discordaria do motor, e é
# sobre este texto que os alunos dele vão receber.
def _desenhar_lista(request, *, recado="", erro="", quantas=0, status=200):
    site = _site_desta_requisicao(request)
    if site is None:
        return _sem_site(request, status=status if status != 200 else 200)

    corpo = MensageriaClient().jornadas(site["id"])
    if corpo is None:
        return _sem_mensageria(request, LISTA, status=503 if status == 200 else status)

    linhas = [_linha_de_sequencia(j) for j in corpo.get("jornadas") or []]
    return render(
        request,
        LISTA,
        {
            "admin": request.admin,
            "sequencias": linhas,
            "ligadas": sum(1 for linha in linhas if linha["ativa"]),
            "recado": recado,
            "erro": erro,
            "quantas": quantas,
        },
        status=status,
    )


def _desenhar_sequencia(
    request, slug, *, recado="", erro="", versao=0, quantas=0, status=200
):
    """Uma sequência por dentro: passos, texto editável, gente e entregas.

    ## Por que esta função PERGUNTA A LISTA antes de pedir os passos

    `getJourney` responde 404 em duas situações diferentes: a sequência não
    existe neste site, e a sequência existe mas ainda não tem versão publicada.
    Distinguir as duas pelo TEXTO da resposta amarraria esta tela à redação de
    uma mensagem de erro da outra célula. A lista já traz `versao_publicada`,
    então quem pergunta primeiro sabe qual dos dois casos tem na mão, sem
    adivinhar nada — e a segunda chamada só acontece quando faz sentido.

    ## `?ver_versao=N` existe por causa de quem está no meio

    Quem entrou na v1 termina na v1, mesmo depois de a v2 nascer. Sem poder
    abrir a versão antiga, a tela mostraria a frase NOVA ao lado do nome de
    alguém que vai receber a ANTIGA, e essa é exatamente a confusão que a
    promessa do §5 existe para evitar.
    """
    site = _site_desta_requisicao(request)
    if site is None:
        return _sem_site(request)

    cliente = MensageriaClient()
    lista = cliente.jornadas(site["id"])
    if lista is None:
        return _sem_mensageria(request, DENTRO, status=503 if status == 200 else status)

    resumo = next(
        (j for j in lista.get("jornadas") or [] if j.get("slug") == slug), None
    )
    if resumo is None:
        return render(
            request,
            DENTRO,
            {"admin": request.admin, "nao_existe": True, "slug": slug},
            status=404,
        )

    linha = _linha_de_sequencia(resumo)
    contexto = {
        "admin": request.admin,
        "sequencia": linha,
        "recado": recado,
        "erro": erro,
        "versao_nova": versao,
        "quantas": quantas,
    }

    if linha["versao_publicada"] is None:
        # Estado NORMAL de uma sequência recém-semeada, e a tela diz isso sem
        # alarme: ligar é decisão dele, nunca efeito colateral de um deploy.
        return render(request, DENTRO, contexto, status=status)

    pedida = _numero(request.GET.get("ver_versao", ""))
    detalhe = cliente.jornada(site["id"], slug, versao=pedida)
    if detalhe is None:
        return _sem_mensageria(request, DENTRO, status=503 if status == 200 else status)

    aberta = (detalhe.get("versao") or {}).get("numero")
    contexto["versao_aberta"] = aberta
    contexto["e_a_corrente"] = aberta == linha["versao_publicada"]
    contexto["passos"] = [_linha_de_passo(p) for p in detalhe.get("passos") or []]

    inscritos = cliente.inscricoes(site["id"], slug)
    contexto["inscricoes_lidas"] = inscritos is not None
    contexto["inscricoes"] = [
        _linha_de_inscricao(i) for i in (inscritos or {}).get("inscricoes") or []
    ]
    contexto["total_de_inscricoes"] = (inscritos or {}).get("total") or 0
    contexto["andando"] = sum(
        1 for i in contexto["inscricoes"] if i["estado"] == "andando"
    )

    # A METADE QUE FAZ A TELA VALER: o que saiu e o que NÃO saiu, para UMA
    # pessoa. Só é pedida quando ele clica numa linha da lista de gente. É uma
    # chamada por pessoa, e pedi-la para todas encheria a tela de ruído no dia
    # em que houver duzentas.
    escolhida = (request.GET.get("inscricao") or "").strip()
    if escolhida:
        contexto["inscricao_aberta"] = escolhida
        entregas = cliente.entregas(site["id"], escolhida)
        contexto["entregas_lidas"] = entregas is not None
        contexto["entregas"] = [
            _linha_de_entrega(e) for e in (entregas or {}).get("entregas") or []
        ]
        contexto["barradas"] = sum(1 for e in contexto["entregas"] if e["barrada"])

    return render(request, DENTRO, contexto, status=status)


def _sem_mensageria(request, molde: str, status: int = 200):
    """A tela abre mesmo sem o par de tokens, e diz o que falta.

    Fail-OPEN na leitura, pelo mesmo motivo de `economia.py::_sem_gamificacao`:
    uma tela de operação que não abre é inútil justamente quando você precisa
    dela. E o que falta é um passo DELE na VPS (Lei 5), então a tela nomeia o
    passo em vez de mostrar um erro cru ou, pior, uma lista vazia — que pareceria
    "esta escola não tem sequência nenhuma" e o mandaria procurar no lugar errado.
    """
    return render(
        request, molde, {"admin": request.admin, "sem_mensageria": True}, status=status
    )


def _sem_site(request, status: int = 200):
    """O catálogo não respondeu, então não sei de qual escola são as sequências.

    Sem `site_id` a porta responde 422 (Lei 9), e chutar um site seria pior que
    não abrir: mostraria as sequências de outro domínio.
    """
    return render(
        request, LISTA, {"admin": request.admin, "sem_site": True}, status=status
    )


# ---------------------------------------------------------------------------
# AS DUAS VISTAS
# ---------------------------------------------------------------------------
@require_GET
def sequencias(request):
    """A lista das sequências deste site, com o interruptor de cada uma.

    UMA chamada à porta, e isso é deliberado: mostrar aqui "quantas pessoas
    estão recebendo" exigiria uma chamada de inscrições POR sequência, e o
    número tem casa própria na tela de dentro, que é onde ele vai olhar para
    pessoas. Contador a mais numa lista custa uma ida à rede por linha e não
    responde nenhuma pergunta que a tela de dentro não responda melhor.
    """
    return _desenhar_lista(
        request,
        recado=request.GET.get("recado", ""),
        erro=request.GET.get("erro", ""),
        quantas=_numero(request.GET.get("quantas", "")) or 0,
    )


@require_GET
def sequencia(request, slug: str):
    """Uma sequência por dentro. O trabalho está em `_desenhar_sequencia`."""
    return _desenhar_sequencia(
        request,
        slug,
        recado=request.GET.get("recado", ""),
        erro=request.GET.get("erro", ""),
        versao=_numero(request.GET.get("versao", "")) or 0,
        quantas=_numero(request.GET.get("quantas", "")) or 0,
    )


# ---------------------------------------------------------------------------
# OS DOIS GESTOS
# ---------------------------------------------------------------------------
@require_POST
def sequencia_ligar(request):
    """Liga ou desliga uma sequência, e volta para a lista dizendo o que houve.

    Padrão POST-redirect-GET no sucesso, como toda escrita desta área: sem ele,
    um F5 depois de ligar repetiria o gesto. Aqui repetir é inofensivo (o pedido
    descreve o ESTADO desejado, não um verbo), e o padrão fica pela mesma razão
    de sempre: o dia em que um gesto não for idempotente é tarde demais para
    lembrar dele.

    DESLIGAR NÃO PARA QUEM JÁ ESTÁ ANDANDO, e é por isso que o número viaja: a
    tela precisa dizer "ninguém novo entra, e N pessoas continuam recebendo até
    o fim" em vez de sugerir que tudo parou.
    """
    slug = (request.POST.get("slug") or "").strip()
    ativa = request.POST.get("ativa") == "1"
    if not slug:
        return _desenhar_lista(request, erro="não veio o nome da sequência", status=400)

    site = _site_desta_requisicao(request)
    if site is None:
        return _sem_site(request, status=503)

    situacao, resposta, frase = MensageriaClient().ligar(
        site_id=site["id"], slug=slug, ativa=ativa
    )
    verbo = Registro.LIGAR_SEQUENCIA if ativa else Registro.DESLIGAR_SEQUENCIA

    if situacao == MensageriaClient.OK:
        andando = int(resposta.get("inscricoes_andando") or 0)
        mudou = bool(resposta.get("mudou"))
        _auditar(
            request,
            verbo,
            slug,
            Registro.OK,
            ("mudou" if mudou else "ja estava assim") + f"; {andando} andando",
        )
        if mudou:
            recado = "ligada" if ativa else "desligada"
        else:
            recado = "ja_estava_ligada" if ativa else "ja_estava_desligada"
        destino = f"{reverse('escola_jornadas')}?recado={recado}&quantas={andando}"
        return HttpResponseRedirect(destino)

    if situacao == MensageriaClient.SEM_VERSAO:
        _auditar(
            request, verbo, slug, Registro.RECUSADO_PELA_CELULA, "sem versao publicada"
        )
        return _desenhar_lista(request, recado="sem_versao", status=422)
    if situacao == MensageriaClient.SEM_GRAU:
        _auditar(request, verbo, slug, Registro.RECUSADO_PELA_CELULA, "sem grau")
        return _desenhar_lista(request, recado="sem_grau", status=422)

    desfecho = (
        Registro.RECUSADO_PELA_CELULA
        if situacao == MensageriaClient.RECUSADO
        else Registro.NAO_RESPONDEU
    )
    _auditar(request, verbo, slug, desfecho, frase)
    return _desenhar_lista(
        request,
        erro=frase,
        status=422 if situacao == MensageriaClient.RECUSADO else 503,
    )


@require_POST
def sequencia_publicar(request):
    """Grava a frase de um passo — o que publica uma versão NOVA da sequência.

    A porta devolve o número da versão que nasceu, e ele viaja para a tela
    porque ela precisa dizer, em português e na hora: quem já está no meio da
    sequência termina com o texto ANTIGO, e o novo vale para quem entrar daqui
    em diante. Sem essa frase, ele trocaria o texto, veria um aluno receber o
    antigo, e concluiria que a correção não pegou.

    `versao_base` viaja escondido no formulário e é a trava contra sobrescrever
    em silêncio quem publicou primeiro: se outra publicação aconteceu entre o
    desenho desta tela e o clique, a porta recusa com 409 em vez de aceitar.
    """
    slug = (request.POST.get("slug") or "").strip()
    ordem = (request.POST.get("ordem") or "").strip()
    idioma = (request.POST.get("idioma") or "").strip()
    assunto = (request.POST.get("assunto_visivel") or "").strip()
    corpo = request.POST.get("corpo") or ""

    if not slug:
        return _desenhar_lista(request, erro="não veio o nome da sequência", status=400)
    if not ordem.isdigit() or not idioma:
        return _desenhar_sequencia(
            request, slug, erro="faltou dizer qual passo é este", status=400
        )
    if not assunto or not corpo.strip():
        return _desenhar_sequencia(
            request,
            slug,
            erro="o título e o texto da mensagem não podem ficar vazios",
            status=400,
        )

    site = _site_desta_requisicao(request)
    if site is None:
        return _sem_site(request, status=503)

    alvo = f"{slug}#{ordem}/{idioma}"
    situacao, resposta, frase = MensageriaClient().publicar_texto(
        site_id=site["id"],
        slug=slug,
        ordem=int(ordem),
        idioma=idioma,
        assunto_visivel=assunto,
        corpo=corpo,
        versao_base=_numero(request.POST.get("versao_base", "")),
    )

    if situacao == MensageriaClient.OK:
        nascida = int(resposta.get("versao") or 0)
        _auditar(
            request, Registro.PUBLICAR_TEXTO, alvo, Registro.OK, f"versao {nascida}"
        )
        destino = reverse("escola_jornada_sequencia", args=[slug])
        return HttpResponseRedirect(f"{destino}?recado=publicado&versao={nascida}")

    if situacao == MensageriaClient.DESATUALIZADO:
        _auditar(
            request,
            Registro.PUBLICAR_TEXTO,
            alvo,
            Registro.RECUSADO_PELA_CELULA,
            "versao base desatualizada",
        )
        return _desenhar_sequencia(request, slug, recado="desatualizado", status=409)
    if situacao == MensageriaClient.SEM_GRAU:
        _auditar(
            request,
            Registro.PUBLICAR_TEXTO,
            alvo,
            Registro.RECUSADO_PELA_CELULA,
            "sem grau",
        )
        return _desenhar_sequencia(request, slug, recado="sem_grau", status=422)

    desfecho = (
        Registro.RECUSADO_PELA_CELULA
        if situacao == MensageriaClient.RECUSADO
        else Registro.NAO_RESPONDEU
    )
    _auditar(request, Registro.PUBLICAR_TEXTO, alvo, desfecho, frase)
    return _desenhar_sequencia(
        request,
        slug,
        erro=frase,
        status=422 if situacao == MensageriaClient.RECUSADO else 503,
    )
