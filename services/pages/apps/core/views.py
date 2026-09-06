"""As views da célula `pages` (a casa das Páginas do aluno).

Sete: a sonda, a Prancheta (o roteiro das cinco etapas, degrau 07), a marcação
de um item da lista de conferência, as três das peças coladas por link (degrau
08: a estante, o colar de um link novo e a mudança de uma peça que já está lá) e
a resposta das perguntas da escola sobre uma peça (degrau 10). O que falta
continua vindo pela escada do `PLANO-PORTFOLIO-DO-ALUNO.md` §5: o pedido de
conferência e a fila da equipe (11 e 12) e a vitrine em `/estudio/<apelido>`
(13).

**Nenhuma view daqui decide quem entra.** Quem decide é a porta
(`apps/core/porta.py`), fail-CLOSED, e ela vem por último no `MIDDLEWARE`:
quando uma view desta célula roda, a pessoa já foi reconhecida e a matrícula
ativa já foi conferida. Espalhar essa decisão por tela faria o critério AC-05
depender de uma lembrança por arquivo, que é a forma como esse tipo de porta
morre.

**Nenhuma view daqui escreve um `filter()` por aluno.** O isolamento do critério
AC-07 tem UMA porta, o `do_aluno` dos gerenciadores de
`apps/portfolio/models.py`, provado por mutação em
`tests/test_isolamento_por_aluno.py`. Um segundo `filter` aqui seria a mesma
regra em duas expressões, e no dia em que discordassem o vazamento sairia pela
que ninguém está medindo.
"""

from __future__ import annotations

import logging
import os

from django.conf import settings
from django.db import models, transaction
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.portfolio import conferencia_do_link, semaforo
from apps.portfolio.models import (
    Acabamento,
    EstadoDoLink,
    EtapaDoRoteiro,
    ItemDeConferencia,
    ItemDoRoteiro,
    ParecidaComAAula,
    Peca,
    Portfolio,
    TipoDeModelo,
)
from apps.portfolio.roteiro_da_escola import AVISO_DE_RASCUNHO

logger = logging.getLogger("pages.views")


def de_fora() -> dict:
    """Os dois endereços que NÃO são desta célula, e que `{% url %}` ignora.

    A entrada mora na `identidade` e a capa mora no `funil`. Com padrão, de
    propósito: `infra/provisionar-pages.sh` não escreve estas chaves, e a trava
    de deriva dele reprova env com variável que ele não sabe gerar. Molde:
    `services/cursos/apps/core/views.py`.
    """
    return {
        "url_de_entrada": settings.URL_DE_ENTRADA,
        "url_da_capa": settings.URL_DA_CAPA,
    }


def site_atual() -> str | None:
    """De que escola é esta instalação, ou `None` quando o env não diz.

    **Lida no ponto de uso, nunca no import** (`armadilhas/097`): variável lida
    no topo de um módulo transforma env ausente em HTTP 500 em toda página, com
    o deploy verde.

    **`None` é o estado real da VPS hoje**, e não uma hipótese:
    `infra/provisionar-pages.sh` não escreve `SITE_ID`, e não escrever
    configuração que a célula ainda não lia foi decisão consciente da gênese
    (`armadilhas/224`, dito por extenso em `infra/env/pages.env.exemplo`). O
    degrau 07 é a primeira tela desta casa que precisa da variável, e a linha
    que a escreve mora em `infra/`, caminho CODEOWNERS que este PR não tem
    mandato para tocar. A dívida está no balcão.

    Enquanto ela faltar, a Prancheta MOSTRA o roteiro (a lista orienta, nunca
    tranca, plano §7) e RECUSA a marcação, dizendo o que aconteceu. Gravar com
    o site em branco seria pior do que recusar: no dia em que a segunda escola
    chegasse, os alunos das duas estariam do mesmo lado da fronteira e nenhuma
    tela quebraria para avisar.
    """
    valor = (os.environ.get("SITE_ID") or "").strip()
    if not valor:
        logger.error(
            "SITE_ID ausente no env: a Prancheta mostra o roteiro mas não grava "
            "marcação, porque não sabe de que escola esta instalação é"
        )
        return None
    return valor


def sem_escola(request):
    """A recusa de gravar quando o env não diz de que escola esta casa é.

    Fail-closed, no mesmo vocabulário que a porta desta casa já usa: 503 é *a
    parte que responde por isto está incompleta*, e é temporário. Gravar com o
    site em branco seria pior do que recusar, e o porquê está em `site_atual`.

    Escrita uma vez e usada por toda view que GRAVA: a alternativa era repetir
    o bloco em cada uma, e regra repetida é regra que diverge na terceira cópia.
    """
    resposta = render(
        request,
        "pages/porta.html",
        {"motivo": "sem-escola", **de_fora()},
        status=503,
    )
    resposta["Retry-After"] = "30"
    resposta["Cache-Control"] = "no-store"
    return resposta


@require_GET
def healthz(request):
    """A sonda do container. Rota de MÁQUINA.

    Ela responde nas DUAS formas de entrada, porque as duas existem em
    produção: `/pages/healthz` pela internet (o Traefik **não** remove o
    prefixo) e `/healthz` pelo healthcheck do compose (`armadilhas/029`).

    A porta do degrau 06 isenta esta rota comparando `request.path_info`, e
    **nunca** `request.path`, que pela borda pública contém o prefixo
    (`apps/core/porta.py::CAMINHOS_ISENTOS`). Guarda:
    `tests/test_healthz_script_name.py`.
    """
    return JsonResponse({"status": "ok"})


@require_GET
def prancheta(request):
    """O roteiro: as cinco etapas, as listas de conferência e o que já foi marcado.

    **Ler não escreve.** O portfólio do aluno nasce na primeira marcação, e não
    aqui: um `GET` que criasse a linha encheria a tabela com quem só passou pela
    porta, e faria a página depender de uma escrita para responder.

    **As duas consultas são independentes de propósito.** O roteiro é da ESCOLA
    e é o mesmo para todo mundo; as marcações são DO ALUNO e saem pela porta do
    isolamento. Juntá-las numa consulta só amarraria o texto da escola ao dono
    da linha, que é a segunda verdade que o degrau 02 recusou.
    """
    site_id = site_atual()

    marcadas: set[str] = set()
    if site_id:
        marcadas = set(
            ItemDeConferencia.objects.do_aluno(
                site_id=site_id, aluno_id=request.aluno["id"]
            )
            .filter(marcado=True)
            .values_list("chave", flat=True)
        )

    etapas = [
        {
            "numero": etapa.numero,
            "titulo": etapa.titulo,
            "resumo": etapa.resumo,
            "itens": [
                {
                    "chave": item.chave,
                    "texto": item.texto,
                    "marcado": item.chave in marcadas,
                }
                for item in etapa.itens.all()
            ],
        }
        for etapa in EtapaDoRoteiro.objects.prefetch_related("itens")
    ]

    return render(
        request,
        "pages/prancheta.html",
        {
            "aluno": request.aluno,
            "etapas": etapas,
            "pode_marcar": site_id is not None,
            "aviso_de_rascunho": AVISO_DE_RASCUNHO,
            **de_fora(),
        },
    )


@require_POST
def marcar(request):
    """O aluno marca (ou desmarca) um item da lista. A marca vai para o BANCO.

    **Formulário normal, sem script:** a regra desta casa é que nenhum caminho
    exista só com JavaScript, e a resposta é o redirecionamento de volta para a
    Prancheta. O POST-redirect-GET também impede que recarregar a página repita
    a escrita.

    **O estado desejado vem no formulário, e não se calcula aqui.** Um botão que
    invertesse o valor atual gravaria o contrário do que o aluno viu sempre que
    ele tivesse duas abas abertas, ou que a rede repetisse o pedido.

    **Chave de fora do catálogo é 404.** Sem essa recusa, qualquer POST
    escreveria marcação com a chave que quisesse, e a tela do aluno passaria a
    mostrar itens que a escola nunca escreveu.
    """
    site_id = site_atual()
    if site_id is None:
        return sem_escola(request)

    chave = (request.POST.get("chave") or "").strip()
    item = ItemDoRoteiro.objects.filter(chave=chave).select_related("etapa").first()
    if item is None:
        raise Http404(f"o roteiro da escola não tem o item {chave!r}")

    quer_marcar = request.POST.get("marcar") == "1"

    with transaction.atomic():
        portfolio, _ = Portfolio.objects.get_or_create(
            site_id=site_id, aluno_id=request.aluno["id"]
        )
        # A marcação é procurada pela MESMA porta do critério AC-07: é o
        # `do_aluno` que impede o desmarcar de um aluno de alcançar a linha de
        # outro que tenha a mesma chave.
        marcacao = (
            ItemDeConferencia.objects.do_aluno(
                site_id=site_id, aluno_id=request.aluno["id"]
            )
            .filter(chave=chave)
            .first()
        )
        if marcacao is None:
            marcacao = ItemDeConferencia(portfolio=portfolio, chave=chave)

        # A etapa acompanha o catálogo a cada escrita: se a escola mudar um item
        # de etapa, a marcação antiga se corrige na primeira vez que o aluno
        # tocar nela, em vez de apontar para a etapa de ontem para sempre.
        marcacao.etapa = item.etapa.numero
        marcacao.marcado = quer_marcar
        # A data anda junto com a marca, e o banco recusa uma sem a outra.
        marcacao.marcado_em = timezone.now() if quer_marcar else None
        marcacao.save()

    # `redirect` pelo NOME da rota: é `reverse()` que carrega o prefixo público
    # para dentro do endereço, e caminho cravado em string quebra em produção e
    # só lá (`armadilhas/029` e `/081`).
    return redirect("prancheta")


# ===========================================================================
# AS PEÇAS, COLADAS POR LINK (degrau 08, critérios AC-08 e AC-09)
# ===========================================================================
# A foto entra por LINK COLADO e nunca hospedada por nós. Decisão do mantenedor
# de 01/09/2026, informado do preço, e ela não se reabre: não existe envio de
# arquivo aqui, e o degrau que era isso saiu da escada (plano §6.2).
#
# A ESTANTE É TELA PRÓPRIA, e não mais um pedaço da Prancheta. O roteiro das
# cinco etapas é o que o aluno LÊ; a estante é o que ele MEXE, com um formulário
# em cada linha. Numa página só, o botão de subir uma peça ficaria a três telas
# de rolagem do item que ele acabou de marcar.


def estante_de(request, site_id: str) -> list[Peca]:
    """As peças deste aluno, na ordem que ele escolheu.

    Sai pela porta única do isolamento (`do_aluno`), como toda leitura desta
    casa: um `filter` próprio aqui seria a mesma regra numa segunda expressão,
    e no dia em que as duas discordassem o vazamento sairia pela que ninguém
    está medindo (critério AC-07).
    """
    return list(
        Peca.objects.do_aluno(site_id=site_id, aluno_id=request.aluno["id"]).order_by(
            "ordem"
        )
    )


def com_semaforo(pecas: list[Peca]) -> list[Peca]:
    """Cada peça com a cor e a lista do que ainda falta nela (critério AC-10).

    **O roteiro da escola é lido UMA vez**, e não uma consulta por peça: a
    estante de um aluno aplicado tem dezenas de linhas, e o texto das regras é o
    mesmo para todas elas.

    **O semáforo não é guardado em coluna nenhuma**, e é por isso que ele nasce
    aqui a cada abertura de tela. Uma cor gravada envelheceria calada no dia em
    que a escola corrigisse uma regra, e a peça mostraria a conta de ontem.
    """
    if not pecas:
        return pecas
    regras = dict(ItemDoRoteiro.objects.values_list("chave", "texto"))
    for peca in pecas:
        peca.semaforo = semaforo.calcular(peca, regras)
    return pecas


def desenhar_estante(request, site_id, *, recusa="", link="", legenda="", status=200):
    """A tela das peças. `recusa` é a frase que diz por que o link não entrou.

    A recusa é DESENHADA no lugar, e não redirecionada: o aluno acabou de colar
    um endereço longo, e mandá-lo para outra página perderia o que ele digitou
    junto com a explicação.
    """
    return render(
        request,
        "pages/pecas.html",
        {
            "aluno": request.aluno,
            "pecas": com_semaforo(estante_de(request, site_id)) if site_id else [],
            "pode_guardar": site_id is not None,
            "recusa": recusa,
            "link_recusado": link,
            "legenda_recusada": legenda,
            # As respostas que a escola aceita em cada pergunta. Só os VALORES e
            # os rótulos: a pergunta em si é frase que o aluno lê, e ela mora no
            # template, que é superfície medida pelo portão do travessão.
            "tipos": TipoDeModelo.choices,
            "acabamentos": Acabamento.choices,
            "semelhancas": ParecidaComAAula.choices,
            **de_fora(),
        },
        status=status,
    )


@require_GET
def pecas(request):
    """A estante: as obras do aluno, na ordem dele, com o estado de cada link.

    **Ler não escreve.** O portfólio nasce quando o aluno guarda a primeira
    peça, e não quando ele abre a página: um `GET` que criasse a linha encheria
    a tabela com quem só passou por aqui.

    Sem `SITE_ID` no env a estante aparece vazia e o formulário some, com a
    frase que explica o porquê. O motivo é o mesmo da Prancheta e está por
    extenso em `site_atual`.
    """
    return desenhar_estante(request, site_atual())


@require_POST
def guardar_peca(request):
    """O aluno cola o endereço, e a Prancheta CONFERE antes de guardar (AC-08).

    **A conferência acontece no momento em que o link é colado**, e não numa
    varredura de madrugada: o aluno está aqui agora, com o navegador aberto na
    imagem, e é agora que ele consegue corrigir um endereço privado ou pela
    metade. Descobrir isso amanhã custaria uma volta que ele não vai dar.

    **Só o "não" que veio do outro lado recusa.** Endereço que respondeu com
    erro é fato sobre o link dele, e a recusa diz o número e o que fazer.
    Endereço que não respondeu de jeito nenhum (demorou, não resolveu, conexão
    morreu) não é a mesma coisa: daqui não dá para separar "o site dele caiu"
    de "a nossa rede caiu", e recusar seria acusar a obra do aluno por um
    problema que pode ser nosso. Nesse caso a peça É GUARDADA, marcada como
    ainda não conferida, e a varredura diária (`apps/portfolio/tasks.py`)
    resolve depois.

    **A peça nova entra no FIM da estante.** Empurrar as outras para baixo
    mudaria uma ordem que o aluno montou a mão, sem ele ter pedido.
    """
    site_id = site_atual()
    if site_id is None:
        return sem_escola(request)

    link = (request.POST.get("link") or "").strip()
    legenda = (request.POST.get("legenda") or "").strip()[:200]

    if not link:
        return desenhar_estante(
            request,
            site_id,
            recusa=(
                "Cole o endereço da imagem para guardar a peça. Ele é o link "
                "que aparece na barra do navegador quando você abre a imagem."
            ),
            legenda=legenda,
            status=422,
        )

    veredito = conferencia_do_link.conferir(link)
    if veredito.resultado == conferencia_do_link.NAO_RESPONDEU:
        return desenhar_estante(
            request,
            site_id,
            recusa=f"A peça não foi guardada porque {veredito.motivo}",
            link=link,
            legenda=legenda,
            status=422,
        )

    agora = timezone.now()
    with transaction.atomic():
        portfolio, _ = Portfolio.objects.get_or_create(
            site_id=site_id, aluno_id=request.aluno["id"]
        )
        ultima = portfolio.pecas.aggregate(fim=models.Max("ordem"))["fim"] or 0
        Peca.objects.create(
            portfolio=portfolio,
            link=link,
            legenda=legenda,
            ordem=ultima + 1,
            estado_do_link=(
                EstadoDoLink.RESPONDENDO
                if veredito.abriu
                else EstadoDoLink.NAO_CONFERIDO
            ),
            conferido_em=agora,
        )

    return redirect("pecas")


@require_POST
def mudar_peca(request):
    """Subir, descer, destacar ou tirar uma peça. Sempre a mando do aluno.

    **A peça só sai daqui quando ELE mandar** (critério AC-09). Nenhuma
    varredura, nenhuma medição de rede e nenhuma limpeza automática apaga obra
    de aluno: é a falha que não tem volta, e o guarda que prova isso está em
    `tests/test_pecas_por_link.py`. Este botão é o único caminho de saída, e
    ele começa num formulário que a pessoa aperta.

    **A troca de posição é uma TROCA**, e é por isso que a unicidade de `ordem`
    nasceu `DEFERRED` no degrau 02: as duas peças passam pelo mesmo lugar no
    meio do caminho, e uma restrição imediata recusaria esse passo, obrigando
    esta view a inventar uma posição temporária.

    **A peça é encontrada pela porta única do isolamento**, e é isso que impede
    o botão de um aluno de alcançar a peça de outro que tenha o mesmo número.
    """
    site_id = site_atual()
    if site_id is None:
        return sem_escola(request)

    acao = request.POST.get("acao") or ""
    if acao not in ("subir", "descer", "destacar", "tirar-destaque", "remover"):
        raise Http404(f"a estante não sabe fazer {acao!r}")

    with transaction.atomic():
        minhas = Peca.objects.do_aluno(
            site_id=site_id, aluno_id=request.aluno["id"]
        ).select_for_update()
        peca = minhas.filter(pk=request.POST.get("peca") or 0).first()
        if peca is None:
            raise Http404("essa peça não está na sua estante")

        if acao == "remover":
            peca.delete()
        elif acao in ("destacar", "tirar-destaque"):
            peca.destaque = acao == "destacar"
            peca.save(update_fields=["destaque", "atualizada_em"])
        else:
            vizinha = (
                minhas.filter(ordem__lt=peca.ordem).order_by("-ordem").first()
                if acao == "subir"
                else minhas.filter(ordem__gt=peca.ordem).order_by("ordem").first()
            )
            # Já está na ponta: nada a fazer e nada a explicar. A tela não
            # mostra o botão nesse caso, e um POST feito a mão não merece erro.
            if vizinha is not None:
                peca.ordem, vizinha.ordem = vizinha.ordem, peca.ordem
                vizinha.save(update_fields=["ordem", "atualizada_em"])
                peca.save(update_fields=["ordem", "atualizada_em"])

    return redirect("pecas")


# ===========================================================================
# AS RESPOSTAS DO ALUNO SOBRE UMA PEÇA (degrau 10, critério AC-10)
# ===========================================================================
# O semáforo é calculado SÓ das respostas objetivas do aluno, e é este
# formulário que as colhe. Ele pergunta o que a professora perguntou, com as
# palavras dela, e nada além disso.
#
# NÃO EXISTE NOTA, ESTRELA NEM CLASSIFICAÇÃO aqui, e a ausência é lei escrita
# (`PLANO-PORTFOLIO-DO-ALUNO.md` §7). Também não existe nada que tente adivinhar
# de onde a peça veio: a única fonte destas colunas é a resposta que a pessoa
# deu, e a máquina não tem opinião sobre a obra dela.

# Cada campo do formulário e o vocabulário que a escola aceita nele. É por esta
# tabela que a view recusa resposta inventada, e ela é a MESMA lista que o banco
# guarda nas três restrições da `Peca`: a tela recusa cedo e com uma frase, o
# banco recusa por último e sem frase nenhuma.
RESPOSTAS_DA_PECA = {
    "tipo": TipoDeModelo,
    "acabamento": Acabamento,
    "parecida_com_a_aula": ParecidaComAAula,
}


@require_POST
def responder_peca(request):
    """O aluno responde as perguntas da escola sobre uma peça.

    **As três respostas viajam juntas, num formulário só com um botão.** Salvar
    uma de cada vez faria o aluno esperar três recarregamentos de página para
    apagar um amarelo, e a lista do que falta é justamente o que ele está
    tentando zerar.

    **Vazio é resposta legítima**, e significa "ainda não respondi". É assim que
    ele desfaz um clique errado sem precisar de um segundo botão para isso.

    **Resposta que a escola não escreveu é 404**, no mesmo molde da ação
    desconhecida do `mudar_peca`. Sem essa recusa, um POST gravaria na coluna
    qualquer palavra, e a tela passaria a mostrar uma resposta que a professora
    nunca deu como opção.

    **A peça é encontrada pela porta única do isolamento** (`do_aluno`, critério
    AC-07): é ela que impede o formulário de um aluno de alcançar a peça de
    outro.
    """
    site_id = site_atual()
    if site_id is None:
        return sem_escola(request)

    numero = (request.POST.get("peca") or "").strip()
    if not numero.isdigit():
        raise Http404(f"a estante não tem a peça {numero!r}")

    respostas = {}
    for campo, vocabulario in RESPOSTAS_DA_PECA.items():
        valor = (request.POST.get(campo) or "").strip()
        if valor and valor not in vocabulario.values:
            raise Http404(f"a escola não oferece a resposta {valor!r} em {campo!r}")
        respostas[campo] = valor

    peca = (
        Peca.objects.do_aluno(site_id=site_id, aluno_id=request.aluno["id"])
        .filter(pk=numero)
        .first()
    )
    if peca is None:
        raise Http404("essa peça não está na sua estante")

    for campo, valor in respostas.items():
        setattr(peca, campo, valor)
    # `atualizada_em` entra na lista de propósito: com `update_fields`, o Django
    # só toca as colunas nomeadas, e um `auto_now` de fora da lista pararia no
    # tempo sem nada acusar.
    peca.save(update_fields=[*respostas, "atualizada_em"])

    return redirect("pecas")
