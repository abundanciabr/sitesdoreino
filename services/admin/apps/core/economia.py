"""`/admin/economia/` — onde o mantenedor liga e desliga cada regra de pontuação.

Pedido dele em 31/08/2026: *"ligar a economia e ver o XP mexer"*. A economia
inteira da escola nasce DESLIGADA (`semear_economia` cria tudo com
`ativa=False`), e ligar a primeira regra é decisão dele, com data e aviso.

## Por que esta tela é obrigatória, e não conveniência

A lei da gamificação (`DECISAO-gamificacao.md` §10.5) tem um **critério de
morte** escrito assim: *"ajustar a economia passar a exigir PR de código"* obriga
a parar e reabrir a decisão com o mantenedor. Enquanto ligar uma regra dependesse
de um agente editar o semeador e esperar uma publicação, a economia era código
com aparência de dado. Esta tela é o que torna a lei verdade.

## Onde o dado mora, e por que não aqui

Na célula `gamificacao`, que é a dona da economia. Esta tela **não guarda nada**:
lê as regras pela porta de máquina, aplica UM gesto, e mostra o que voltou.
Guardar uma cópia aqui seria o mesmo fato em dois lugares — a lei
anti-duplicação do `CLAUDE.md` —, e no dia em que as duas discordassem esta tela
mostraria uma coisa e o motor pagaria outra.

## Quem autoriza é ESTA célula

A `gamificacao` não assina sessão ([INV-P12]) e o `papel` que a `identidade`
devolve **nunca autoriza rota** (*"reconhecer não é autorizar"*,
`DECISAO-onde-mora-a-sessao` §4). O crachá que vale é o desta área, que a porta
do `/admin/` já exige; o Bearer do par prova só QUEM CHAMA. É o mesmo desenho de
`/admin/menu/`, que lê e grava o menu no `catalogo`.

## As frases em português moram AQUI, e isso é regra do contrato

A porta da gamificação manda **slug, nunca frase pronta** (invariante 3 do
contrato dela): o site serve três idiomas, e uma frase que saísse de lá
congelaria o idioma de quem a escreveu. Então `TRADUCAO` e `IMPEDIMENTOS`, mais
abaixo, são desta tela — o bastidor do mantenedor, que é só em português.

## Por que é formulário simples, sem script

Cada gesto é um POST que recarrega a página, como em `/admin/menu/`, pelas mesmas
três razões: o que se vê é o que está gravado; a política de segurança desta área
exige um hash na CSP para cada script embutido (`armadilhas/199`), e um
formulário não precisa de nenhum; e o mantenedor é leigo — um botão por gesto,
com o nome do gesto escrito nele, não tem como ser mal entendido.
"""

from __future__ import annotations

from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.auditoria.models import Registro

from .clients import GamificacaoClient
from .views import _auditar

# O que cada regra semeada significa, em português de gente. A chave é o slug
# que a porta devolve; regra que aparecer aqui sem tradução mostra o próprio
# slug, que é feio mas honesto — melhor que esconder uma regra da tela dele.
TRADUCAO = {
    "quiz-aprovado": (
        "Terminar o quiz",
        "O aluno responde o quiz de entrada e ganha pontos.",
    ),
    "sugestao-criada": (
        "Mandar uma sugestão",
        "Alguém escreve uma sugestão na Caixa de Sugestões.",
    ),
    "voto-dado": (
        "Votar numa sugestão",
        "Quem VOTA ganha um pouco, por participar.",
    ),
    "sugestao-votada": (
        "Ter a própria sugestão votada",
        "Quem ESCREVEU a sugestão ganha quando alguém vota nela.",
    ),
    "sugestao-implementada": (
        "Ter a própria sugestão feita",
        "Você marca a sugestão como pronta, e quem a escreveu ganha.",
    ),
    "aula-concluida": (
        "Terminar uma aula",
        "O aluno conclui uma aula do curso.",
    ),
}

# Os três motivos pelos quais ligar uma regra pode não fazer número nenhum se
# mexer. O vocabulário é fechado e vem do contrato; as frases são daqui.
#
# ISTO EXISTE PARA UMA FRUSTRAÇÃO ESPECÍFICA: sem este aviso, ele ligaria a
# primeira regra para "ver o número mexer", o número ficaria zero, e não haveria
# nada na tela dizendo por quê. Um zero sem explicação parece defeito da tela.
IMPEDIMENTOS = {
    "sem-produtor": (
        "Ligar não vai adiantar ainda: nada no site avisa quando isso acontece."
    ),
    "sem-credito": (
        "Ligar não vai adiantar ainda: o aviso chega, mas sem dizer de quem é o "
        "ponto, e eu não invento dono para ponto de ninguém."
    ),
    "cristais-sem-efeito": (
        "Os pontos vão ser pagos, mas os Cristais NÃO: Cristal só nasce de "
        "medalha, missão, sequência, ajuda validada e correção da equipe. Mudar "
        "essa lista é decisão sua, e mexe na trava que garante que Cristal não "
        "se compra."
    ),
}


def _linha(regra: dict) -> dict:
    """Uma regra como a tela a desenha: já traduzida, já com os avisos."""
    slug = str(regra.get("slug", ""))
    nome, explicacao = TRADUCAO.get(slug, (slug, ""))
    impedimentos = [
        IMPEDIMENTOS[chave]
        for chave in regra.get("impedimentos") or []
        if chave in IMPEDIMENTOS
    ]
    quarentena = int(regra.get("quarentena_horas") or 0)
    return {
        "slug": slug,
        "nome": nome,
        "explicacao": explicacao,
        "pontos": int(regra.get("pontos") or 0),
        "cristais": int(regra.get("cristais") or 0),
        "ativa": bool(regra.get("ativa")),
        "versao": int(regra.get("versao") or 0),
        "vigente_desde": regra.get("vigente_desde") or "",
        "quarentena_horas": quarentena,
        # A espera é a parte que mais confunde quem olha o número: o ponto é
        # creditado na hora, mas só entra no perfil depois da quarentena. Sem
        # esta frase, ele liga, faz a ação, e acha que não funcionou.
        "espera": (
            f"O ponto só aparece no perfil {quarentena} horas depois, de "
            "propósito: é a janela para desfazer se o conteúdo for moderado."
            if quarentena
            else ""
        ),
        "teto": int(regra.get("acoes_cheias_por_dia") or 0),
        "impedimentos": impedimentos,
    }


def _contexto(request, regras, erro="", recado="", conquistas=None):
    """O que a tela desenha. `conquistas=None` significa "não consegui ler".

    A distinção importa e é visível: lista VAZIA quer dizer "esta escola não tem
    nenhuma"; `None` quer dizer "a pergunta falhou agora". Sem essa diferença, uma
    falha de rede apareceria como "a escola não tem medalhas", e ele iria procurar
    o problema no lugar errado.
    """
    linhas = [_linha(r) for r in regras]
    conquistas_lidas = conquistas is not None
    linhas_de_conquista = [_linha_de_conquista(c) for c in (conquistas or [])]
    return {
        "admin": request.admin,
        "regras": linhas,
        "ligadas": sum(1 for linha in linhas if linha["ativa"]),
        "conquistas": linhas_de_conquista,
        "conquistas_lidas": conquistas_lidas,
        "conquistas_ligadas": sum(1 for c in linhas_de_conquista if c["ativa"]),
        "erro": erro,
        "recado": recado,
    }


def _sem_gamificacao(request, status=200):
    """A tela abre mesmo sem o par de tokens, e diz o que falta.

    Fail-OPEN na leitura: uma tela de operação que não abre é inútil justamente
    quando você precisa dela. E o que falta é um passo DELE na VPS
    (`infra/provisionar-par-da-economia.sh`), então a tela nomeia o passo.
    """
    return render(
        request,
        "admin/economia.html",
        {"admin": request.admin, "sem_gamificacao": True},
        status=status,
    )


@require_GET
def economia(request):
    """A tela: uma linha por regra e uma por conquista, com o botão de cada uma.

    As duas listas vêm de duas perguntas separadas, e a segunda pode falhar
    sozinha — foi assim durante alguns minutos em 01/09/2026, entre a publicação
    desta tela e a da porta do outro lado. Nesse caso a metade de cima continua
    inteira e a de baixo diz que não conseguiu ler, em vez de a tela toda cair.
    """
    cliente = GamificacaoClient()
    regras = cliente.regras()
    if regras is None:
        return _sem_gamificacao(request)
    return render(
        request,
        "admin/economia.html",
        _contexto(
            request,
            regras,
            recado=request.GET.get("recado", ""),
            conquistas=cliente.conquistas(),
        ),
    )


@require_POST
def economia_mudar(request):
    """Liga ou desliga UMA regra, e volta para a tela.

    Padrão POST-redirect-GET: sem ele, um F5 depois de ligar repetiria o gesto.
    Aqui repetir é inofensivo (a porta devolve a linha como está, sem gastar
    versão), mas o padrão fica porque o dia em que um gesto NÃO for idempotente
    é tarde demais para lembrar dele.
    """
    slug = (request.POST.get("slug") or "").strip()
    ativa = request.POST.get("ativa") == "1"
    if not slug:
        return _voltar_com_erro(request, "não veio o nome da regra")

    situacao, frase = GamificacaoClient().mudar(slug, ativa)
    verbo = Registro.LIGAR_REGRA if ativa else Registro.DESLIGAR_REGRA
    if situacao == GamificacaoClient.OK:
        _auditar(request, verbo, slug, Registro.OK, "")
        recado = "ligada" if ativa else "desligada"
        return HttpResponseRedirect(f"{reverse('economia')}?recado={recado}")

    desfecho = (
        Registro.RECUSADO_PELA_CELULA
        if situacao == GamificacaoClient.RECUSADO
        else Registro.NAO_RESPONDEU
    )
    _auditar(request, verbo, slug, desfecho, frase)
    return _voltar_com_erro(
        request,
        frase,
        status=422 if situacao == GamificacaoClient.RECUSADO else 503,
    )


# ---------------------------------------------------------------------------
# A SEGUNDA METADE DA TELA: as medalhas e os marcos
# ---------------------------------------------------------------------------
# Entrou em 01/09/2026, depois de o mantenedor escolher que os dois interruptores
# ficam na MESMA tela, em vez de espalhados por duas. O custo dessa escolha foi um
# Rito de Contrato (a porta da gamificação estava congelada); o ganho é que ele
# abre um lugar só e vê tudo o que a escola paga e reconhece.
#
# AQUI NÃO HÁ TABELA DE TRADUÇÃO, e a diferença em relação às regras é do
# contrato: `nome` e `descricao` de uma conquista VIAJAM pela porta, como exceção
# declarada ao "slug, nunca frase pronta". A razão está escrita lá — o texto de
# uma conquista é dado que o mantenedor edita, não frase de interface que precise
# existir em três idiomas.
IMPEDIMENTOS_DE_CONQUISTA = {
    "sem-motor-de-criterio": (
        "Ligar não vai conceder nada ainda: a conta automática das medalhas é a "
        "próxima peça a construir. Enquanto ela não existe, a medalha fica "
        "disponível e ninguém a recebe."
    ),
    "sem-fato-que-alimenta": (
        "E nada no site produz esse número ainda: o que esta medalha conta "
        "depende de uma parte que não foi construída."
    ),
    "so-por-concessao-manual": (
        "Esta não tem conta automática nenhuma: ela sai pela mão da equipe, uma "
        "pessoa de cada vez. Ligar só a torna disponível para ser concedida."
    ),
}


def _linha_de_conquista(conquista: dict) -> dict:
    """Uma medalha ou marco como a tela a desenha."""
    e_marco = conquista.get("classe") == "marco"
    return {
        "slug": str(conquista.get("slug", "")),
        "nome": str(conquista.get("nome") or conquista.get("slug", "")),
        "descricao": str(conquista.get("descricao") or ""),
        "e_marco": e_marco,
        # Marco vale ZERO ponto por lei, e o banco da gamificação recusa o
        # contrário. A tela não mostra o número dele: um "0 pontos" ao lado de
        # "Primeiro cliente" convidaria à pergunta errada.
        "pontos": 0 if e_marco else int(conquista.get("pontos") or 0),
        "cristais": 0 if e_marco else int(conquista.get("cristais") or 0),
        "ativa": bool(conquista.get("ativa")),
        "envolve_dinheiro": bool(conquista.get("envolve_dinheiro")),
        "impedimentos": [
            IMPEDIMENTOS_DE_CONQUISTA[chave]
            for chave in conquista.get("impedimentos") or []
            if chave in IMPEDIMENTOS_DE_CONQUISTA
        ],
    }


@require_POST
def economia_mudar_conquista(request):
    """Liga ou desliga UMA medalha ou marco, e volta para a tela.

    Gêmea de `economia_mudar`, com dois verbos de auditoria próprios: a pergunta
    que se faz ao histórico é diferente ("quando a escola passou a reconhecer
    isto?" contra "desde quando esta regra paga?").
    """
    slug = (request.POST.get("slug") or "").strip()
    ativa = request.POST.get("ativa") == "1"
    if not slug:
        return _voltar_com_erro(request, "não veio o nome da conquista")

    situacao, frase = GamificacaoClient().mudar_conquista(slug, ativa)
    verbo = Registro.LIGAR_CONQUISTA if ativa else Registro.DESLIGAR_CONQUISTA
    if situacao == GamificacaoClient.OK:
        _auditar(request, verbo, slug, Registro.OK, "")
        recado = "ligada" if ativa else "desligada"
        return HttpResponseRedirect(f"{reverse('economia')}?recado={recado}")

    desfecho = (
        Registro.RECUSADO_PELA_CELULA
        if situacao == GamificacaoClient.RECUSADO
        else Registro.NAO_RESPONDEU
    )
    _auditar(request, verbo, slug, desfecho, frase)
    return _voltar_com_erro(
        request,
        frase,
        status=422 if situacao == GamificacaoClient.RECUSADO else 503,
    )


def _voltar_com_erro(request, frase: str, status: int = 400):
    """A tela de volta, com o que ESTÁ GRAVADO e o erro por cima.

    Nunca com o gesto que não pegou: mostrar o que foi recusado faria a página
    discordar do motor, e é sobre este número que ele vai confiar depois.
    """
    cliente = GamificacaoClient()
    regras = cliente.regras()
    if regras is None:
        return _sem_gamificacao(request, status=503)
    return render(
        request,
        "admin/economia.html",
        _contexto(request, regras, erro=frase, conquistas=cliente.conquistas()),
        status=status,
    )
