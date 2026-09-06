"""O sininho: quem interagiu com a ideia fica sabendo que ela andou.

EVO-21 escreveu o dado para o autor. **EVO-42 abre o leque**: autor, quem votou
e quem comentou — um `Aviso` por pessoa distinta, na mesma transação da mudança
de status. Lei: `docs/caixa-de-sugestoes/DECISAO-EVO-40-quem-aprova-e-quem-e-avisado.md`
§2, decidida pelo mantenedor em 25/08/2026.

O aviso NASCE junto com a mudança de status, cada pessoa vê a lista dos avisos
DELA, a contagem de não-lidos está disponível em toda página, e marcar como lido
é idempotente.

**O leque é escrito em LOTE, e isso é desenho, não otimização.** Uma sugestão
popular tem centenas de votantes; um `create()` por pessoa dentro do laço faria
o custo de mudar um status crescer com o tamanho da plateia, dentro de uma
transação que segura um `SELECT … FOR UPDATE` na linha da sugestão. São **três**
consultas, sempre: quem comentou, quem votou, e um `bulk_create`. O guarda que
impede a volta do laço é `tests/test_volume_dos_avisos.py`, que mede com 2 e com
20 interessados e exige o MESMO número — é a única forma de o desenho certo não
ser desfeito de boa-fé pelo próximo agente.

**A decisão que define este arquivo (mantenedor, 24/08/2026).** O plano original
mandava a célula `mensageria` avisar o aluno. Foi descartado com motivo medido:
a `mensageria` é feita para e-mail/WhatsApp, exige um destinatário e é organizada
em torno de *pedidos de compra* — e o envio de e-mail dela é um esqueleto vazio.
Pior: para ela mandar qualquer coisa, o e-mail do aluno teria de SAIR de dentro
da Caixa, desfazendo a `DECISAO-EVO-01` §3 (o e-mail vive numa linha só). O
aviso é, então, dentro da própria Caixa — que é o que a `ESPECIFICACAO-CELULA.md`
§10 já pedia: *"notificação in-app simples"*.

**Por que o aviso NÃO nasce do evento no Redis, embora o `sugestao.status-alterado`
exista desde o EVO-20 e carregue o `autor_da_sugestao_id`.** O evento existe para
o mundo de FORA (gamificação, analytics — que nascem depois). Consumir o próprio
evento para escrever na própria tabela seria mandar o fato dar uma volta pela
rede para voltar ao ponto de partida, e o preço é grande:

* **modo de falha novo** — Redis fora do ar deixaria o status mudado e o aluno
  sem aviso, e nada na Caixa indicaria a falta;
* **atraso** — o aluno só saberia depois do relay, não no ato;
* **e o pior: divergência possível.** Status e aviso passariam a poder discordar,
  e é exatamente isso que a transação existe para impedir.

Por isso `avisar_os_interessados()` é chamada DENTRO do `transaction.atomic()` de
`registrar_mudanca_de_status()` (`apps/core/moderacao.py`) — o mesmo lugar onde o
evento é escrito na outbox. Um rollback leva os três juntos: status, histórico e
**todos** os avisos.

**Fora daqui, de propósito:** e-mail/WhatsApp (decisão acima) e o sininho fora da
Caixa — o sino visível em qualquer página do site exige que o `funil` pergunte à
`sugestoes` quantos avisos a pessoa tem, o que é operação nova num contrato
CONGELADO. Isso não é decisão pendente, é **rito** pendente (RITOS §3, com o
mantenedor presente, nunca dentro de um lote) — está escrito na §2 da decisão.
Um sistema de notificações que vai crescer merece plano próprio, não uma extensão
improvisada desta tela.
"""

import logging
import time

from django.db import transaction
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.dateparse import parse_date, parse_datetime
from django.views.decorators.http import require_GET, require_POST

from apps.sugestoes.models import Aviso, Comentario, Identidade, Sugestao, Voto

from . import sessao as ses
from .clients import NotificacoesClient
from .participacao import exige_sessao, quadro_atual

logger = logging.getLogger(__name__)

PAGINA_AVISOS = "sugestoes/avisos.html"

# Os mesmos dicionários de rótulo que o resto da célula já usa — nunca um
# segundo vocabulário. `ver_avisos()` os usa para traduzir
# `parametros.status_anterior`/`status_novo`/`vinculo` (texto cru vindo da
# API) para o mesmo português que `get_..._display()` já produzia quando a
# leitura era local.
STATUS_ROTULOS = dict(Sugestao.Status.choices)
VINCULO_ROTULOS = dict(Aviso.Vinculo.choices)

# ---------------------------------------------------------------------------
# [ASSUNTOS] Uma carta diz DE QUE ela fala (`assunto`), e esta tela precisa
# saber desenhar cada um. Até 29/08/2026 existia um só — a Caixa era a única
# coisa que gerava aviso — e o desenho do cartão assumia isso em silêncio: ele
# monta o título com `{% url 'sugestao' aviso.sugestao_id %}`, que **estoura em
# NoReverseMatch** para qualquer carta sem `suggestion_id`.
#
# Ou seja: no dia em que a primeira carta de matrícula chegasse, esta página
# devolveria 500 — não um cartão feio, a página inteira. É por isso que este PR
# vem ANTES do que publica a carta.
# ---------------------------------------------------------------------------
ASSUNTO_SUGESTAO = "sugestao.status-alterado"
ASSUNTO_MATRICULA = "matricula.situacao-alterada"

# As QUATRO CARTAS DE CELEBRAÇÃO da gamificação (Sessão B, 30/08/2026). Elas já
# eram escritas e já chegavam aqui: até este PR caíam todas no cartão do
# `desconhecido`, e a pessoa que subiu de nível lia "esta tela ainda não sabe
# mostrar". O fato existia, a voz não.
#
# **Cada uma é uma constante, e a lista é FECHADA de propósito.** A tentação
# óbvia é `assunto.startswith("gamificacao.")` — e ela é um erro: o contrato
# pode ganhar um quinto assunto amanhã, e o prefixo guloso o desenharia com o
# cartão errado em vez de admitir que não o conhece. O ramo do `desconhecido` é
# fail-VISÍVEL, e ele só protege enquanto for possível cair nele.
ASSUNTO_NIVEL = "gamificacao.nivel-alcancado"
ASSUNTO_CONQUISTA = "gamificacao.conquista-concedida"
ASSUNTO_MARCO = "gamificacao.marco-validado"
ASSUNTO_DESTAQUE = "gamificacao.destaque-da-semana"

# O SELO DA ESCOLA NO PORTFÓLIO (Rito de Contrato de 06/09/2026, degrau 12 do
# corredor `CS-PAGES-0001`, critério AC-12). O aluno mandou o portfólio para a
# fila da escola e esperou um prazo de cinco dias úteis: esta é a carta que
# fecha essa espera.
#
# **Ela aprende a forma ANTES de a célula `pages` publicá-la**, e essa ordem é a
# mesma lição escrita no bloco [ASSUNTOS] logo acima: uma tela que só aprende o
# assunto depois é uma tela que mostra "ainda não sabe mostrar" para quem estava
# esperando resposta.
ASSUNTO_PORTFOLIO = "pages.portfolio-conferido"

#: Os títulos dos níveis NA PALAVRA DE QUEM LÊ. Mesma forma, e mesmo motivo, do
#: `SITUACAO_ROTULOS` logo abaixo: um mapa explícito, pequeno, com fallback
#: fail-open — **slug que não estiver aqui mostra a frase só com o número do
#: nível, nunca um rótulo chutado**.
#:
#: **Por que um mapa, e não desfazer o slug.** O `titulo_slug` da carta é
#: DERIVADO (`slugify(titulo)` em `gamificacao/cartas.py::carta_de_nivel`), então
#: ele já perdeu o acento e juntou as palavras: "Aprendiz de Ateliê" chega como
#: `aprendiz-de-atelie`. Reconstruí-lo programaticamente produz lixo visível ao
#: aluno ("Aprendiz De Atelie"), e é justamente o tipo de chute que a lei desta
#: tela proíbe.
#:
#: **Este mapa é um ESPELHO, e vai envelhecer.** A escada mora na tabela
#: `NIVEIS` de `gamificacao/management/commands/semear_economia.py`, célula que
#: esta aqui não pode ler em tempo de execução (Lei 3, e a constituição da
#: `sugestoes` lista `gamificacao` como proibida até de ler). O espelho é aceito
#: porque a divergência é INÓCUA por construção: nível renomeado ou nível novo
#: cai no fallback e a frase continua verdadeira, com o número. O que nunca pode
#: acontecer é o contrário, um rótulo desatualizado apresentado como certo.
#:
#: Só as formas masculinas estão aqui porque só elas são emitidas: o motor passa
#: `degrau.titulo` (`gamificacao/motor.py`), nunca `titulo_feminino`. Se um dia
#: passar, o slug feminino cai no fallback e a pessoa lê o número do nível, que
#: continua sendo verdade.
TITULO_DE_NIVEL_ROTULOS = {
    "aprendiz": "Aprendiz",
    "aprendiz-de-atelie": "Aprendiz de Ateliê",
    "modelador": "Modelador",
    "modelador-de-atelie": "Modelador de Ateliê",
    "oficial": "Oficial",
    "oficial-de-atelie": "Oficial de Ateliê",
    "artesao": "Artesão",
    "artesao-de-atelie": "Artesão de Ateliê",
    "mestre": "Mestre",
    "mestre-de-atelie": "Mestre de Ateliê",
}

#: O TOM de cada família de medalha. `familia` é opcional no contrato, e
#: ausência é "não informado", nunca erro: sem ela o cartão fica só com a frase
#: de sempre, que já é uma boa notícia inteira.
#:
#: O NOME da medalha não aparece em lugar nenhum, e isso é fronteira, não
#: esquecimento: ele mora na célula `gamificacao`, que esta tela não pode
#: consultar. Um cartão que celebrasse "sua medalha" sem saber qual seria menos
#: honesto do que um que celebra o fato e manda a pessoa olhar o perfil dela.
FAMILIA_DE_MEDALHA_FRASES = {
    "oficio": "É uma medalha de ofício, dessas que nascem do trabalho pronto.",
    "comunidade": "É uma medalha de comunidade, de quem apareceu quando alguém precisou.",
    "epoca": "É uma medalha de época, e ela só existe para quem estava por aqui agora.",
    "secreta": "É uma medalha secreta, e você achou o caminho sem ninguém contar.",
    "carreira": "É uma medalha de carreira, das que marcam o caminho inteiro.",
    "espelho": "É uma medalha de espelho, e ela compara você com você mesmo, mais ninguém.",
}

#: COM QUE AUTORIDADE o marco foi validado. O ID de quem validou nunca viaja na
#: carta (é a mesma regra do `ator_id` do envelope: guardar sim, mostrar não), e
#: por isso o cartão fala do PAPEL, jamais de uma pessoa. Opcional no contrato:
#: sem ele, o cartão simplesmente não diz quem conferiu.
VALIDADOR_DE_MARCO_FRASES = {
    "professor": "Quem conferiu foi um professor da escola.",
    "monitor": "Quem conferiu foi um monitor da escola.",
    "par": "Quem conferiu foi outro aluno, com a mesma régua de sempre.",
    "sistema": "A conferência foi automática, feita pela própria plataforma.",
}

#: QUEM da escola conferiu o portfólio. Vocabulário menor que o do marco, e o
#: contrato explica por quê: portfólio quem confere é sempre gente da escola,
#: então não existe `par` nem `sistema` aqui. Mesmo desenho, mesmo fallback: sem
#: o campo, o cartão não diz quem conferiu, e a frase que sobra continua inteira.
#:
#: **Hoje a `pages` não manda este campo**, e a razão está no contrato: ela
#: reconhece a equipe por uma lista de ids e não sabe qual deles é professor.
#: Este mapa existe porque a tela tem de saber desenhar a carta inteira antes de
#: alguém publicá-la, e porque voltar aqui custa uma liberação nominal do
#: mantenedor: a `sugestoes` é célula proibida pelo corredor daquela obra.
PAPEL_DE_QUEM_CONFERIU_FRASES = {
    "professor": "Quem olhou foi um professor da escola.",
    "monitor": "Quem olhou foi um monitor da escola.",
}

#: As situações de matrícula NA PALAVRA DE QUEM LÊ — o aluno, não o mantenedor.
#: O painel dele tem o próprio vocabulário ("Ativo — entra normalmente"), e a
#: duplicação aqui é deliberada: são duas plateias, e a frase que serve a uma
#: soa errada para a outra. O que NÃO pode divergir é a chave, que vem do
#: contrato do evento.
#:
#: Situação que não estiver aqui cai no rótulo cru, nunca numa chave chutada —
#: a mesma regra do `vinculo` ausente logo acima.
SITUACAO_ROTULOS = {
    "ativa": "Você é aluno",
    "reembolsada": "Reembolsado, e o acesso acabou",
    "suspensa": "Acesso pausado",
    "encerrada": "Acesso encerrado",
    "aguardando": "Na fila, esperando decisão",
    "recusada": "Pedido não aprovado",
}


class AvisoForaDaTransacao(Exception):
    """`avisar_os_interessados()` chamada sem transação aberta.

    Mesma forma — e mesmo motivo — do `EventoForaDaTransacao` do EVO-20
    (`apps/sugestoes/eventos.py`), que é a Lei 1 aplicada: em vez de confiar que
    todo ponto futuro de mudança de status se lembre do `atomic`, a própria
    função recusa a escrita. Um aviso gravado em autocommit sobrevive ao rollback
    do fato que o justifica — e aí a Caixa passa a dizer ao aluno que a ideia
    dele andou quando ela não andou.
    """


def interessados_em(sugestao) -> dict[str, str]:
    """Quem interagiu com a ideia → por qual vínculo. Distintos, em DUAS consultas.

    A ordem de preenchimento É a precedência de quem acumula papéis, e o
    `setdefault` é o que a impõe: autor primeiro, depois quem comentou, depois
    quem votou. Quem é as três coisas entra **uma vez**, como `AUTOR`.

    Um `set` de ids não bastaria — perderia o motivo, que é o que a tela precisa
    dizer. Um `dict` guarda os dois e ainda deduplica sozinho: não existe o
    caminho de código em que a mesma pessoa entre duas vezes, então a ausência
    de duplicata não depende de ninguém lembrar de filtrar.

    **Duas consultas, e não uma por pessoa.** As duas são `values_list` de uma
    coluna só: o que sobe para a memória é uma lista de ids opacos, nunca linhas
    inteiras de `Voto`/`Comentario` — e nunca a `Identidade`, que carrega e-mail
    (`DECISAO-EVO-01` §3). O `.distinct()` do comentário existe porque uma
    pessoa comenta várias vezes na mesma ideia; o do voto não existe porque o
    banco já o garante (`voto_unico_por_ator_e_sugestao`).

    **O `.order_by()` vazio antes do `.distinct()` não é enfeite.** `Comentario`
    tem `ordering = ["criado_em"]` no `Meta`, e o Django acrescenta a coluna de
    ordenação ao `SELECT DISTINCT` — o SQL vira
    `SELECT DISTINCT autor_id, criado_em`, que é distinto por PAR e portanto não
    deduplica pessoa nenhuma. Ainda voltaria certo daqui (o `dict` deduplica), só
    que trazendo uma linha por comentário e uma data que este código não tem o
    que fazer com ela. Limpar a ordenação devolve ao `DISTINCT` o sentido que o
    nome dele promete.
    """
    vinculos: dict[str, str] = {sugestao.autor_id: Aviso.Vinculo.AUTOR}
    for identidade_id in (
        Comentario.objects.filter(sugestao=sugestao)
        .order_by()
        .values_list("autor_id", flat=True)
        .distinct()
    ):
        vinculos.setdefault(identidade_id, Aviso.Vinculo.COMENTARIO)
    for identidade_id in Voto.objects.filter(sugestao=sugestao).values_list(
        "autor_id", flat=True
    ):
        vinculos.setdefault(identidade_id, Aviso.Vinculo.VOTO)
    return vinculos


def ids_de_plataforma(locais) -> dict[str, str]:
    """Id local → id da PLATAFORMA, para quem tiver. UMA consulta, sempre.

    O elo da Fase 1 (INV-SUG11) sendo usado pela primeira vez para falar com o
    resto da plataforma: a carta `notificacao.devida` endereça pelo id que
    qualquer célula entende, nunca pelo id local, que não significa nada fora
    daqui (PLANO-MESTRE §2).

    **Uma consulta para a plateia inteira, e não uma por pessoa.** É a mesma lei
    do `interessados_em` e do `bulk_create` dos avisos: esta função roda dentro
    da transação que segura o `SELECT … FOR UPDATE` da sugestão, e um `.get()`
    por votante alongaria a trava exatamente nas ideias que deram certo.
    `values_list` de duas colunas — a `Identidade` inteira NÃO sobe para a
    memória, porque ela carrega e-mail (`DECISAO-EVO-01` §3).

    **Quem não tem o id fica de fora do dicionário, e isso é a resposta certa.**
    São pessoas que não voltaram ao site desde a Fase 1 (25/08/2026): a linha
    delas ainda não foi casada. Elas continuam recebendo o `Aviso` local, que é
    o que a tela mostra hoje — o que não recebem é a carta, que ainda não tem
    consumidor. Na reentrada delas a porta grava o id, e a partir daí recebem.
    """
    return {
        local: plataforma
        for local, plataforma in Identidade.objects.filter(
            pk__in=list(locais), id_da_plataforma__isnull=False
        ).values_list("pk", "id_da_plataforma")
    }


def avisar_os_interessados(
    *, sugestao, status_anterior: str, status_novo: str, nota: str = ""
) -> list[Aviso]:
    """[INVARIANTE 1] Os avisos nascem na MESMA transação da mudança de status.

    A igualdade que o EVO-21 protegia era *"uma linha de `HistoricoStatus` ⇒ um
    `Aviso`"*. Desde o EVO-42 ela é *"⇒ um `Aviso` por interessado DISTINTO"* — e
    o guarda de atomicidade continua mordendo na forma nova, que é a parte cara
    de acertar: relaxar o guarda para acomodar o leque desfaria o motivo de ele
    existir.

    Quem recebe: autor, quem comentou e quem votou — **sem ressalva**, inclusive
    quando quem moderou foi uma dessas pessoas (alguém da equipe mexendo na
    própria ideia, ou tendo votado nela). Suprimir esse caso seria um ramo a mais
    e uma exceção que o guarda de atomicidade teria de conhecer.

    `nota` entra como veio: é a justificativa que a equipe escreveu sabendo que
    quem sugeriu vai ler (spec §10, e o `EXIGEM_JUSTIFICATIVA` do EVO-13). Ela
    alcança agora todo mundo que participou da conversa, que é o ponto da
    decisão: a resposta "não vamos fazer, e por quê" é para quem se importou.

    **`bulk_create` e não um laço de `create()`.** É UM `INSERT` para a plateia
    inteira, dentro de uma transação que já segura o `SELECT … FOR UPDATE` da
    sugestão — o desenho errado alonga essa trava proporcionalmente ao número de
    votantes, que é justamente o número que cresce quando a Caixa dá certo.
    """
    if not transaction.get_connection().in_atomic_block:
        raise AvisoForaDaTransacao(
            "avisar_os_interessados() foi chamada fora de transaction.atomic(). "
            "Os avisos têm de nascer na MESMA transação da mudança de status: sem "
            "isso, um rollback deixa gente avisada de algo que não aconteceu — e o "
            "aviso e o status passam a poder divergir."
        )
    return Aviso.objects.bulk_create(
        [
            Aviso(
                destinatario_id=destinatario_id,
                sugestao=sugestao,
                status_anterior=status_anterior,
                status_novo=status_novo,
                nota=nota,
                vinculo=vinculo,
            )
            for destinatario_id, vinculo in interessados_em(sugestao).items()
        ]
    )


def _meus(ator):
    """[INVARIANTE 2, histórico] O recorte por dono, num lugar só.

    **Desde a Fase 3/4 do sininho, NENHUMA view lê mais por aqui** — `sino()`
    e `ver_avisos()` passaram a ler de `NotificacoesClient` (a caixa central,
    `contracts/notificacoes.openapi.yaml`; `DECISAO-fase-2-do-sininho.md`
    §3). A função continua existindo porque `avisar_os_interessados()` acima
    continua escrevendo o `Aviso` LOCAL — rollback de segurança durante a
    transição (aposentar a tabela é a Fase 6, despacho próprio) — e porque
    ler o estado dessa cópia local segue útil para depuração/operação.
    `contar_nao_lidos()` abaixo é o mesmo caso.
    """
    return Aviso.objects.filter(destinatario=ator.identidade)


def contar_nao_lidos(ator) -> int:
    return _meus(ator).filter(lido_em__isnull=True).count()


# ---------------------------------------------------------------------------
# O sino: fail ABERTA — a MESMA regra do sino do `funil` (Escolha 2,
# `docs/decisoes/DECISAO-fase-4-do-sininho.md`). `notificacoes` fora do ar ⇒
# sem número, página abre normal, nunca 500. É a ponta OPOSTA de
# `ver_avisos()`, logo abaixo, que fail VISÍVEL — mesmo dado, duas telas,
# regras deliberadamente diferentes.
# ---------------------------------------------------------------------------

TTL_DO_RESUMO = 30
MAXIMO_EM_CACHE = 500
_CACHE_DE_RESUMO: dict = {}


def limpar_cache_de_resumo() -> None:
    """`tests/conftest.py::ambiente` chama isto a cada teste — o mesmo
    cuidado de `apps/core/sessao.py::limpar_caches` (armadilhas/026: cache de
    módulo vaza entre testes)."""
    _CACHE_DE_RESUMO.clear()


def _site_id_da_requisicao() -> "str | None":
    """O `site_id` desta requisição, pelo MESMO mecanismo que o resto da
    célula já usa para resolver o site dela (`participacao.quadro_atual()`)
    — nunca um segundo jeito de descobrir o site. `None` só quando o próprio
    `quadro_atual()` não consegue decidir (zero ou dois quadros no banco):
    problema de CADASTRO, não de rede — e o resto da célula já responde a
    isso com `Http404` (`ver_quadro`, `nova_sugestao`); aqui, dentro do sino
    fail-aberto, vira "sem número" em vez de derrubar a página.
    """
    try:
        return quadro_atual().site_id
    except Http404:
        return None


def sino(request):
    """A contagem de não-lidos disponível em TODA página, sem view lembrar dela.

    Context processor (e não um item que cada view acrescenta ao contexto) pela
    Lei 1: um combinado de "não esqueça de pôr a contagem" seria esquecido pela
    primeira view escrita depois desta. A contagem é **preguiçosa** — o valor no
    contexto é um callable, que o Django só executa se o template pedir. Página
    que não mostra o sino não paga consulta nenhuma; a `entrar.html`, que nem
    estende a moldura, não paga nada.

    O sino desenhado é do EVO-31 (Lote 3). **Desde a Fase 4 do sininho, o
    dado vem de `GET /resumo`** (a caixa central), fail ABERTA: qualquer
    tropeço (config ausente, rede, HTTP≠200, JSON fora do contrato — tudo
    isso é `None` para `NotificacoesClient.obter_resumo`) vira "sem número",
    nunca uma página quebrada. Cache curto por `(destinatario_id, site_id)`,
    mesma ideia do `_CACHE_DE_AVISOS` do `funil` (PR #296): evita uma chamada
    HTTP por página vista pela mesma pessoa numa rajada de cliques — e o
    `None` (falha) também é cacheado, para uma `notificacoes` fora do ar não
    virar uma tentativa de rede por página durante todo o TTL.
    """

    def contagem() -> int:
        ator = ses.ator_atual(request)
        if ator is None:
            return 0
        destinatario_id = ator.identidade.id_da_plataforma
        if not destinatario_id:
            # Ainda não "casou" com a plataforma (INV-SUG11): não há por
            # quem perguntar à notificacoes. Mesma resposta do fail-open —
            # sem número, nunca erro.
            return 0
        site_id = _site_id_da_requisicao()
        if site_id is None:
            return 0

        agora = time.time()
        chave = (destinatario_id, site_id)
        hit = _CACHE_DE_RESUMO.get(chave)
        if hit and hit[0] > agora:
            return hit[1] or 0

        valor = NotificacoesClient().obter_resumo(
            destinatario_id=destinatario_id, site_id=site_id
        )
        if len(_CACHE_DE_RESUMO) >= MAXIMO_EM_CACHE:
            _CACHE_DE_RESUMO.clear()
        _CACHE_DE_RESUMO[chave] = (agora + TTL_DO_RESUMO, valor)
        return valor or 0

    return {"avisos_nao_lidos": contagem}


# ---------------------------------------------------------------------------
# A tela de avisos: fail VISÍVEL — a regra OPOSTA do sino (Escolha 2,
# `DECISAO-fase-4-do-sininho.md`). Esta página É a função dela: esconder uma
# falha em silêncio faria a pessoa achar que não tem avisos quando a caixa
# central é que está fora do ar. Vazio de verdade e falha são estados
# DIFERENTES, nunca o mesmo visual.
# ---------------------------------------------------------------------------

MENSAGEM_DE_FALHA = "Não consegui buscar seus avisos agora. Tente de novo em instantes."

# Teto de páginas ao seguir `proximo_cursor` — nunca esperado em uso normal
# desta Caixa; existe só para um laço não correr sem fim se a notificacoes
# devolver um cursor que nunca esvazia.
MAXIMO_DE_PAGINAS = 50


def _buscar_todos_os_avisos(
    *, destinatario_id: str, site_id: str
) -> "list[dict] | None":
    """Todas as páginas de `GET /avisos`, concatenadas — `None` se QUALQUER
    página falhar. Uma página só não pode virar metade da verdade: exibir as
    primeiras 20 e calar-se sobre o resto seria a mesma mentira que a
    Escolha 2 proíbe, só que disfarçada de paginação.
    """
    cliente = NotificacoesClient()
    itens: list[dict] = []
    cursor = ""
    for _ in range(MAXIMO_DE_PAGINAS):
        pagina = cliente.listar_avisos(
            destinatario_id=destinatario_id, site_id=site_id, cursor=cursor
        )
        if pagina is None:
            return None
        itens.extend(pagina["itens"])
        cursor = pagina.get("proximo_cursor") or ""
        if not cursor:
            break
    return itens


def _sugestoes_dos_avisos(itens: list[dict]) -> dict[str, dict]:
    """`suggestion_id` (de `parametros`) → o que a tela precisa saber da ideia:
    o título, e se ela foi apagada. UMA consulta para a plateia inteira de
    avisos, nunca uma por linha (o mesmo cuidado de N+1 que
    `select_related("sugestao")` já tinha antes desta migração).

    O título NÃO viaja na carta de propósito
    (`DECISAO-fase-2-do-sininho.md` §4: uma ideia renomeada deixaria avisos
    antigos mostrando o nome velho para sempre) — por isso a tela busca aqui,
    NA HORA DE LER, pelo `suggestion_id` opaco.

    **`apagada` vem junto pelo mesmo motivo, e é o que fecha o buraco achado
    em 31/08/2026 pelo mantenedor:** o apagamento definitivo destrói o
    conteúdo da ideia, mas a carta que já saiu vive na caixa central, cujo
    contrato congelado não tem operação de retirada. Sem este campo, quem
    recebeu o recado continuava vendo um cartão de título VAZIO — com a
    justificativa da equipe ainda legível ao lado — apontando para uma ideia
    que não existe mais. Isso contraria por escrito a promessa da
    `DECISAO-apagar-ideia.md`: *"desapareça até mesmo para quem a criou"*.
    """
    ids = {(item.get("parametros") or {}).get("suggestion_id") for item in itens}
    ids_numericos = [i for i in ids if i and str(i).isdigit()]
    if not ids_numericos:
        return {}
    return {
        str(pk): {"titulo": titulo, "apagada": apagada_em is not None}
        for pk, titulo, apagada_em in Sugestao.objects.filter(
            pk__in=ids_numericos
        ).values_list("id", "titulo", "apagada_em")
    }


def _sobre_ideia_apagada(item: dict, sugestoes: dict[str, dict]) -> bool:
    """Este aviso fala de uma ideia que foi apagada definitivamente?

    Carta de OUTRO assunto (matrícula, por exemplo) nunca cai aqui: ela não
    tem `suggestion_id`, e `sugestoes` não a conhece.

    `suggestion_id` que esta Caixa não acha também não cai — pode ser carta de
    outro quadro, e sumir com ela seria esconder um recado legítimo por não
    saber lê-lo. Esse caso segue no caminho de sempre, que mostra
    "(sugestão não encontrada)" e deixa a pessoa ver que existe algo ali.
    """
    id_da_ideia = str((item.get("parametros") or {}).get("suggestion_id") or "")
    return sugestoes.get(id_da_ideia, {}).get("apagada", False)


def _matricula_para_o_template(item: dict, parametros: dict) -> dict:
    """[ASSUNTOS] O cartão de uma mudança de situação na escola.

    Sem link, de propósito: não há para onde levar. A ficha do aluno mora na
    célula `alunos` e a tela dela é a do MANTENEDOR — mandar a pessoa para lá
    seria oferecer uma porta que bate na cara, o defeito que a home já cometeu
    uma vez (`DECISAO-categorias-de-usuario`).

    O `matricula_id` chega na carta e **não vai para a tela**: ele existe para
    quem for reconstruir o histórico, e um identificador opaco no cartão de um
    aluno é ruído sobre um dado que ele não pode usar para nada.
    """
    nova = parametros.get("situacao_nova") or ""
    anterior = parametros.get("situacao_anterior") or ""
    return {
        "situacao_nova": nova,
        "situacao_nova_label": SITUACAO_ROTULOS.get(nova, nova),
        "situacao_anterior": anterior,
        "situacao_anterior_label": SITUACAO_ROTULOS.get(anterior, anterior),
    }


def _nivel_para_o_template(item: dict, parametros: dict) -> dict:
    """[GAMIFICAÇÃO] Subiu de nível.

    **O `nivel` é o campo autoritativo; o `titulo_slug` só escolhe o tom.** A
    frase se monta a partir do número, e o título entra por cima quando o slug
    está no mapa. Slug fora do mapa (ou ausente) não vira rótulo chutado: some,
    e sobra a frase com o número, que continua inteiramente verdadeira.

    **`nivel` ausente também é caso NORMAL, não erro.** Ele é obrigatório no
    contrato de hoje, mas a tela lê cartas que já estão gravadas na caixa
    central, e um contrato congelado não retroage sobre o que já foi escrito.
    Sem o número, o cartão diz que houve uma subida, sem dizer para onde: menos
    informação, nunca uma mentira nem um `nível ` com um buraco no fim da frase.
    """
    bruto = parametros.get("nivel")
    nivel = bruto if isinstance(bruto, int) and not isinstance(bruto, bool) else None
    slug = parametros.get("titulo_slug") or ""
    return {
        "nivel": nivel,
        # Só entra na tela quando o slug é conhecido E o número existe: um
        # título solto, sem o degrau a que pertence, não é frase de ninguém.
        "titulo_do_nivel": TITULO_DE_NIVEL_ROTULOS.get(slug, "") if nivel else "",
    }


def _conquista_para_o_template(item: dict, parametros: dict) -> dict:
    """[GAMIFICAÇÃO] Ganhou uma medalha.

    A medalha é o andaime, contado automaticamente pelo sistema — **não
    confundir com o MARCO**, que é a espinha, exige validação humana e vale zero
    XP. São dois assuntos no contrato justamente para esta tela poder falar de
    cada um com o peso certo, e é por isso que são dois cartões aqui.

    O `conquista_slug` **não vai para a tela**, pela mesma razão do
    `matricula_id`: é identificador opaco, e o NOME da medalha mora na célula
    `gamificacao`, que esta aqui não consulta.
    """
    return {
        "familia_frase": FAMILIA_DE_MEDALHA_FRASES.get(
            parametros.get("familia") or "", ""
        )
    }


def _marco_para_o_template(item: dict, parametros: dict) -> dict:
    """[GAMIFICAÇÃO] Um marco real foi validado.

    A carta mais importante do sistema, e a que menos XP carrega: marco rende
    ZERO. Ela existe porque marco passa por fila de validação com prazo, e quem
    mandou uma evidência e ficou esperando precisa saber que ela foi aceita.

    A evidência em si nunca viaja na carta e nunca aparece aqui: ela é privada,
    e nem os colegas a veem.
    """
    return {
        "validador_frase": VALIDADOR_DE_MARCO_FRASES.get(
            parametros.get("validador_papel") or "", ""
        )
    }


def _destaque_para_o_template(item: dict, parametros: dict) -> dict:
    """[GAMIFICAÇÃO] O professor destacou a obra.

    `semana` é a SEGUNDA-FEIRA da semana, e o contrato a manda como DATA e não
    como data-hora exatamente para ninguém converter fuso e exibir a semana
    errada (`armadilhas/099`). Por isso ela vira `datetime.date`, que o filtro
    `|date:` formata sem conversão nenhuma, e nunca um `datetime` ciente.

    Data ausente, vazia ou malformada some do cartão: a frase sem ela continua
    verdadeira, e uma semana errada seria pior do que semana nenhuma.
    """
    semana = None
    try:
        semana = parse_date(parametros.get("semana") or "")
    except ValueError:
        # Formato de data certo e dia impossível ("2026-02-31"): `parse_date`
        # levanta em vez de devolver None, e uma carta não pode derrubar a
        # página inteira de ninguém por causa de um caractere.
        semana = None
    return {"semana": semana}


def _portfolio_para_o_template(item: dict, parametros: dict) -> dict:
    """[PORTFÓLIO] A escola conferiu o portfólio, e o selo saiu.

    Quem chega aqui pediu a conferência e esperou numa fila com prazo, então a
    frase responde à pergunta que essa pessoa está fazendo há dias.

    O `portfolio_id` **não vai para a tela**, pela mesma razão do `matricula_id`
    e do `conquista_slug`: é identificador opaco, e o aluno não pode usá-lo para
    nada. O que ele quer saber está na Prancheta dele, e é para lá que a frase o
    manda, sem link (a Prancheta mora na célula `pages`, que esta tela não
    consulta, e um endereço escrito à mão aqui seria a segunda verdade sobre
    onde ela fica).
    """
    return {
        "papel_frase": PAPEL_DE_QUEM_CONFERIU_FRASES.get(
            parametros.get("conferido_por_papel") or "", ""
        )
    }


#: [ASSUNTOS] Assunto → quem desenha o cartão dele. Uma tabela, e não uma escada
#: de `if`, porque assunto novo passou a ser rotina: foram DOIS em 29/08, e mais
#: QUATRO em 01/09. A tabela também é o que torna barato o teste que mais
#: importa aqui — o de que um assunto FORA dela continua caindo no fail-visível.
_DESENHO_DO_CARTAO = {
    ASSUNTO_MATRICULA: _matricula_para_o_template,
    ASSUNTO_NIVEL: _nivel_para_o_template,
    ASSUNTO_CONQUISTA: _conquista_para_o_template,
    ASSUNTO_MARCO: _marco_para_o_template,
    ASSUNTO_DESTAQUE: _destaque_para_o_template,
    ASSUNTO_PORTFOLIO: _portfolio_para_o_template,
}


def _item_para_o_template(item: dict, sugestoes: dict[str, dict]) -> dict:
    """Um item de `GET /avisos` (a forma da API) → o dicionário que o
    template usa. Mesmos NOMES de campo que o `Aviso` (model) já expunha —
    `status_novo`, `vinculo`, `nota`, `criado_em`, `lido_em`, `id` — para a
    vestimenta do EVO-31 (`avisos.html`) precisar de troca mínima.

    **`vinculo` ausente (carta de antes de 27/08/2026, ou de um `Aviso` sem
    carta ainda) → rótulo genérico, NUNCA uma exceção por chave ausente** —
    é a lei do próprio campo (`contracts/eventos/notificacao.devida.v1.json`,
    descrição de `parametros.vinculo`: "a tela que lê trata ausência como
    'motivo não registrado'"). Aqui isso vira `vinculo_label=""`, e o
    template simplesmente não desenha o selo quando não há rótulo.
    """
    parametros = item.get("parametros") or {}
    assunto = item.get("assunto") or ""
    comum = {
        "id": item["id"],
        # [ASSUNTOS] É por ele que o template escolhe o cartão. Vem do contrato
        # da carta, e chega vazio nas cartas antigas — que são todas de sugestão
        # e caem no ramo padrão, como sempre caíram.
        "assunto": assunto or ASSUNTO_SUGESTAO,
        "lido_em": parse_datetime(item["lido_em"]) if item.get("lido_em") else None,
        "criado_em": parse_datetime(item["criado_em"]),
    }

    desenho = _DESENHO_DO_CARTAO.get(assunto)
    if desenho is not None:
        return {**comum, **desenho(item, parametros)}

    if assunto and assunto != ASSUNTO_SUGESTAO:
        # [ASSUNTOS] Assunto que esta tela NÃO conhece. O cartão diz isso, em vez
        # de desenhar um de sugestão vazio — que é o que aconteceria por
        # omissão, com "(sugestão não encontrada)" e um link para lugar nenhum.
        #
        # Fail-VISÍVEL, a mesma regra desta página inteira (Escolha 2 da
        # `DECISAO-fase-4-do-sininho`): a pessoa fica sabendo que existe um
        # recado para ela, e que somos nós que ainda não sabemos mostrá-lo.
        return {**comum, "assunto": assunto, "desconhecido": True}

    suggestion_id = str(parametros.get("suggestion_id") or "")
    status_novo = parametros.get("status_novo") or ""
    status_anterior = parametros.get("status_anterior") or ""
    vinculo = parametros.get("vinculo") or ""
    return {
        **comum,
        "sugestao_id": suggestion_id,
        "sugestao_titulo": (sugestoes.get(suggestion_id) or {}).get("titulo")
        or "(sugestão não encontrada)",
        "status_novo": status_novo,
        "status_novo_label": STATUS_ROTULOS.get(status_novo, status_novo),
        "status_anterior": status_anterior,
        "status_anterior_label": STATUS_ROTULOS.get(status_anterior, status_anterior),
        "vinculo": vinculo,
        "vinculo_label": VINCULO_ROTULOS.get(vinculo, ""),
        "nota": parametros.get("nota") or "",
    }


@require_GET
@exige_sessao
def ver_avisos(request, ator):
    """A lista dos avisos DESTA pessoa — lida da caixa central desde a Fase
    3/4 do sininho (`DECISAO-fase-2-do-sininho.md` §3), não mais do `Aviso`
    local. Ver o bloco acima: fail VISÍVEL, a regra oposta do sino.
    """
    destinatario_id = ator.identidade.id_da_plataforma
    site_id = quadro_atual().site_id
    itens = (
        _buscar_todos_os_avisos(destinatario_id=destinatario_id, site_id=site_id)
        if destinatario_id
        # Sem id de plataforma (INV-SUG11), não há por quem perguntar — a
        # pessoa nunca teve carta nenhuma endereçada a ela. Mesmo tratamento
        # da falha de rede: a tela avisa, nunca finge lista vazia.
        else None
    )

    if itens is None:
        logger.error(
            "ver_avisos: não deu para buscar os avisos de %s na notificacoes",
            ator.identidade.id,
        )
        return render(
            request,
            PAGINA_AVISOS,
            {"ator": ator, "falha": True, "avisos": [], "nao_lidos": 0},
            status=503,
        )

    sugestoes = _sugestoes_dos_avisos(itens)
    # A ideia apagada não deixa recado para trás. O corte é AQUI, na leitura, e
    # não na escrita, porque a carta já saiu: ela mora na caixa central, cujo
    # contrato congelado não tem operação de retirada (só listar e marcar como
    # lida). Filtrar na hora de ler é o que esta célula consegue fazer sozinha,
    # e é o mesmo desenho de `SugestaoQuerySet.visiveis()` — um corte de
    # visibilidade num lugar só, em vez de um campo novo em cada superfície.
    escondidos = [i for i in itens if _sobre_ideia_apagada(i, sugestoes)]
    itens = [i for i in itens if not _sobre_ideia_apagada(i, sugestoes)]
    _calar_o_sino(ator, escondidos)
    avisos = [_item_para_o_template(item, sugestoes) for item in itens]
    nao_lidos = sum(1 for item in itens if not item.get("lido_em"))

    return render(
        request,
        PAGINA_AVISOS,
        {"ator": ator, "falha": False, "avisos": avisos, "nao_lidos": nao_lidos},
    )


def _calar_o_sino(ator, escondidos: list[dict]) -> None:
    """Marca como lidos os recados que esta tela ACABOU de esconder.

    **O buraco que isto fecha, achado pelo mantenedor em 31/08/2026 e aberto
    pelo próprio conserto daquele dia.** O corte de visibilidade acima tira da
    tela o recado de uma ideia apagada; o número do sino, porém, é calculado
    pela caixa central (`obterResumo`), que não sabe de apagamento nenhum.
    Resultado: o sino dizia **1**, a pessoa clicava, e a lista abria vazia.

    E o pior, que só apareceu ao ler o código de perto: `nao_lidos` é somado
    DEPOIS do corte, então o botão "Marcar tudo como lido" — que aparece só
    `{% if nao_lidos %}` — **também some**. A pessoa ficava com um número que
    ela não tinha como zerar por caminho nenhum.

    **Por que isto NÃO é um Rito de Contrato.** O contrato congelado da caixa
    central não tem "retirar", e o registro `20260831-012` concluiu, com razão
    para o que se sabia então, que faltava operação nova. Mas as portas que já
    existem COMPÕEM o gesto (`armadilhas/293`): `marcarUmaComoLida` é
    idempotente e recebe o id do aviso, que está bem aqui na resposta de
    `listarAvisos`. Marcar o órfão como lido tira o número do sino sem inventar
    verbo nenhum, e sem contrato novo.

    **Por que no caminho de LEITURA, e não no apagamento.** Apagar uma ideia
    popular teria de varrer os avisos de cada interessado para achar os ids —
    o laço por pessoa que este arquivo inteiro existe para evitar (ver o
    cabeçalho, "o leque é escrito em LOTE"). Aqui os ids já vieram na resposta
    que a tela pediu de qualquer jeito, são no máximo os órfãos de UMA pessoa
    (quase sempre zero), e a chamada é idempotente: a segunda visita não custa
    nada. É reconciliação, não escrita de negócio.

    **Fail-ABERTO, e de propósito.** Esta é a tela que fail VISÍVEL na
    LISTAGEM (o comentário logo acima diz por quê: vazio e falha são estados
    diferentes). Mas calar o sino é efeito colateral de conforto: se a caixa
    central recusar ou sumir, a pessoa continua vendo a lista certa, e a
    próxima visita tenta de novo. Derrubar a página por isso trocaria um
    número teimoso por uma tela quebrada.
    """
    nao_lidos = [i for i in escondidos if not i.get("lido_em")]
    if not nao_lidos:
        return
    destinatario_id = ator.identidade.id_da_plataforma
    if not destinatario_id:
        return
    site_id = quadro_atual().site_id
    cliente = NotificacoesClient()
    for item in nao_lidos:
        aviso_id = item.get("id")
        if not aviso_id:
            continue
        if (
            cliente.marcar_uma_como_lida(
                destinatario_id=destinatario_id, site_id=site_id, id=str(aviso_id)
            )
            is not True
        ):
            logger.error(
                "calar_o_sino: nao deu para marcar %s (recado de ideia apagada) "
                "como lido; o numero do sino segue contando ate a proxima visita",
                aviso_id,
            )


@require_POST
@exige_sessao
def marcar_lido(request, ator, aviso_id):
    """[INVARIANTES 2 e 3] Só o dono marca, e marcar duas vezes é marcar uma
    — ambos garantidos agora pela notificacoes (`POST /marcar-lida`), não
    mais por `_meus()` local.

    **404 e não 403** continua a resposta ao chute de um `aviso_id` alheio.
    `NotificacoesClient.marcar_uma_como_lida` devolve `False` exatamente
    para esse caso (a notificacoes respondeu 404 — id inexistente ou de
    outra pessoa/site), distinto de `None` ("não sei": rede, config, 5xx).
    Só o primeiro vira 404 aqui; o segundo é logado e a pessoa volta para a
    lista normalmente — se a falha persistir, é a PRÓXIMA leitura de
    `ver_avisos()` que avisa (fail visível é da tela de listar, não deste
    botão).
    """
    destinatario_id = ator.identidade.id_da_plataforma
    if destinatario_id:
        site_id = quadro_atual().site_id
        resultado = NotificacoesClient().marcar_uma_como_lida(
            destinatario_id=destinatario_id, site_id=site_id, id=aviso_id
        )
        if resultado is False:
            raise Http404("aviso inexistente, ou de outra pessoa")
        if resultado is None:
            logger.error(
                "marcar_lido: não deu para marcar %s como lido (destinatário %s)",
                aviso_id,
                ator.identidade.id,
            )
    return HttpResponseRedirect(reverse("avisos"))


@require_POST
@exige_sessao
def marcar_tudo_lido(request, ator):
    """Escolha 3, `DECISAO-fase-4-do-sininho.md`: marcar TODOS os avisos não
    lidos de uma vez — funcionalidade NOVA (a leitura local nunca teve isto).

    Best-effort e silenciosa na falha, de propósito: perder este clique é
    baixo risco (o botão continua ali para tentar de novo), e é a tela de
    listar — não este botão — quem carrega a responsabilidade de AVISAR
    quando a notificacoes está fora do ar.
    """
    destinatario_id = ator.identidade.id_da_plataforma
    if destinatario_id:
        site_id = quadro_atual().site_id
        resultado = NotificacoesClient().marcar_todas_como_lidas(
            destinatario_id=destinatario_id, site_id=site_id
        )
        if resultado is None:
            logger.error(
                "marcar_tudo_lido: não deu para marcar tudo como lido (destinatário %s)",
                ator.identidade.id,
            )
    return HttpResponseRedirect(reverse("avisos"))
