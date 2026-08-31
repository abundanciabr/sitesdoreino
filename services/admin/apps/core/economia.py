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


def _contexto(request, regras, erro="", recado=""):
    linhas = [_linha(r) for r in regras]
    return {
        "admin": request.admin,
        "regras": linhas,
        "ligadas": sum(1 for linha in linhas if linha["ativa"]),
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
    """A tela: uma linha por regra, com o botão de ligar ou desligar."""
    regras = GamificacaoClient().regras()
    if regras is None:
        return _sem_gamificacao(request)
    return render(
        request,
        "admin/economia.html",
        _contexto(request, regras, recado=request.GET.get("recado", "")),
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
        regras = GamificacaoClient().regras()
        if regras is None:
            return _sem_gamificacao(request, status=503)
        return render(
            request,
            "admin/economia.html",
            _contexto(request, regras, erro="não veio o nome da regra"),
            status=400,
        )

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

    # A tela volta com as regras COMO ESTÃO GRAVADAS, nunca com o que foi
    # recusado: mostrar o gesto que não pegou faria a página discordar do motor,
    # e é exatamente sobre este número que ele vai confiar depois.
    regras = GamificacaoClient().regras()
    if regras is None:
        return _sem_gamificacao(request, status=503)
    return render(
        request,
        "admin/economia.html",
        _contexto(request, regras, erro=frase),
        status=422 if situacao == GamificacaoClient.RECUSADO else 503,
    )
