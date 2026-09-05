# apps/core/caixa.py — a gestão das ideias dos alunos, dentro do Admin
"""As três telas que conduzem a Caixa de Sugestões, agora em `/admin/caixa/`.

Lei: `docs/decisoes/DECISAO-a-gestao-da-caixa-mora-no-admin.md` (28/08/2026).
Decisão do mantenedor, na frase dele: *"não vamos espalhar painéis ou gestão por
aí, tudo será em /admin"*. As telas nasceram na célula `sugestoes` e mudaram de
casa; o desenho é o mesmo, escolhido por ele entre quatro modelos
(`docs/paineis/painel-da-caixa-de-sugestoes/`).

**Todo o agrupamento mora aqui, e nenhum fato.** A Caixa responde os FATOS de
cada ideia — votos, plateia, estado, datas, se tem avaliação, se tem ChangeSpec —
e este módulo decide colunas, ordem e o que é pendência. A divisão não é gosto:
com o agrupamento do outro lado, cada ajuste de layout viraria mudança de
contrato, e mudança de contrato aqui custa um Rito, isto é, uma conversa com o
mantenedor.

**A exceção são os três números de GENTE** (`pessoas_esperando`,
`silencio_medio_em_dias`, `pessoas_em_silencio_demais`), que viajam prontos
porque contam pessoas DISTINTAS entre várias ideias — e deste lado só existe a
contagem por ideia, que somada contaria duas vezes quem está atrás de duas.

**Fail-OPEN, por tile.** A Caixa fora do ar, ou o par de tokens ainda não
provisionado, deixa a tela com um aviso honesto e a página abre igual — nunca
lista vazia, que se leria como "não há ideia nenhuma". É a mesma escolha da tela
de alunos, e o inverso da porta: a porta decide ACESSO e fecha na dúvida; uma
tela de operação que não abre é inútil justamente quando você precisa dela.
"""

from datetime import datetime, timezone as tz

from urllib.parse import urlencode

from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.auditoria.models import Registro

from .clients import CaixaClient
from .views import _auditar

# As seis colunas da travessia, na ordem em que uma ideia as atravessa. Elas NÃO
# são os seis estados: dois deles partem em dois, porque é a partição que
# responde "de quem é a vez" — "ninguém leu" é diferente de "a equipe está
# lendo", e "esperando você assinar" é diferente de "assinada, pode começar".
COLUNAS = (
    ("chegando", "Chegando", "Ninguém da equipe leu ainda."),
    ("lendo", "A equipe está lendo", "Já tem avaliação interna escrita."),
    ("assinar", "Esperando você assinar", "Aprovada, sem documento de obra assinado."),
    ("pode-comecar", "Pode começar", "Assinada. Esperando um robô pegar."),
    ("construindo", "Robô construindo", "Alguém está com a mão nisto agora."),
    ("no-ar", "No ar", "Entregue."),
)

# Os três estados em que a pessoa JÁ recebeu a resposta dela. Recusada conta como
# respondida de propósito: um "não vamos fazer" explicado é resposta, e cobrá-la
# para sempre ensinaria a equipe a evitar recusar.
JA_RESPONDIDAS = ("implementado", "nao_planejado", "mesclado")

FORA_DO_TRILHO = ("nao_planejado", "mesclado")

# Quantos dias em "Em análise" sem ninguém escrever nada antes de a ideia subir
# para a mesa. Sete: é a mesma janela do freio de publicação do aluno (3 ideias a
# cada 7 dias), então quem gastou uma vaga da semana e não ouviu nada até a
# semana seguinte fechar já esperou um ciclo inteiro do próprio limite.
DIAS_ATE_A_ANALISE_ENVELHECER = 7

ENTREGAS_RECENTES = 3


def _momento(quando: str) -> "datetime | None":
    """Uma data do contrato como instante comparável, ou `None`.

    O contrato manda texto ISO com fuso; `fromisoformat` o entende desde o
    Python 3.11. Um `strptime` com formato cravado quebraria no dia em que o
    provedor mudasse de microssegundos para segundos — e o contrato não promete
    a precisão, promete o formato.

    Sem fuso, assume UTC: comparar um instante ingênuo com um consciente estoura
    `TypeError`, e derrubar a tela inteira por causa de um campo mal formado numa
    ideia é a pior resposta possível numa tela de operação.
    """
    try:
        instante = datetime.fromisoformat(quando)
    except ValueError:
        return None
    return instante if instante.tzinfo else instante.replace(tzinfo=tz.utc)


def _dias(desde: str, agora: datetime) -> int:
    """Dias entre uma data do contrato e agora."""
    quando = _momento(desde)
    if quando is None:
        return 0
    # Nunca negativo. Data no futuro acontece de verdade — relógio da máquina
    # fora de hora, fuso mal resolvido na borda — e "parada há -355142 dias"
    # não é um número esquisito: é uma frase sem sentido numa tela feita para
    # leigo. Zero é a leitura honesta: entrou agora.
    return max(0, (agora - quando).days)


def _enriquecer(ideias, agora):
    """Acrescenta a cada ideia o que a TELA precisa e o contrato não promete."""
    for ideia in ideias:
        ideia["parada_ha"] = _dias(ideia.get("parada_desde", ""), agora)
        ideia["coluna"] = _coluna_de(ideia)
    return ideias


def _coluna_de(ideia) -> str:
    status = ideia.get("status")
    if status == "em_desenvolvimento":
        return "construindo"
    if status == "implementado":
        return "no-ar"
    if status == "planejado":
        return "pode-comecar" if ideia.get("tem_changespec") else "assinar"
    if status == "em_analise":
        return "lendo" if ideia.get("tem_avaliacao") else "chegando"
    return "fora-do-trilho"


# ---------------------------------------------------------------------------
# Aba 1 — A SUA MESA: uma decisão por vez
# ---------------------------------------------------------------------------


def esperando(ideias) -> list:
    """As duas coisas que só uma pessoa destrava — a definição, num lugar só.

    Toda tela do painel que precisa saber "quantas coisas esperam por mim"
    pergunta a esta função. Uma segunda contagem escrita à parte seria uma
    segunda definição, e a que ninguém olha é a que fica errada.
    """
    pendentes = []
    for ideia in ideias:
        if ideia["coluna"] == "assinar":
            pendentes.append({**ideia, "motivo": "assinatura"})
        elif (
            ideia["coluna"] == "chegando"
            and ideia["parada_ha"] >= DIAS_ATE_A_ANALISE_ENVELHECER
        ):
            pendentes.append({**ideia, "motivo": "triagem"})
    # Gente esperando primeiro, tempo parado depois — nesta ordem. Uma ideia com
    # 200 pessoas atrás parada há três dias custa mais silêncio à turma do que
    # uma com 4 pessoas parada há um mês.
    pendentes.sort(key=lambda i: (-i["pessoas"], -i["parada_ha"]))
    return pendentes


@require_GET
def mesa(request):
    quadro = CaixaClient().ideias(por_email=_email(request))
    if quadro is None:
        return render(request, "admin/caixa_mesa.html", {"nao_respondeu": True})

    agora = datetime.now(tz.utc)
    ideias = _enriquecer(quadro["ideias"], agora)
    decisoes = esperando(ideias)
    em_obra = [i for i in ideias if i["coluna"] == "construindo"]
    no_ar = sorted(
        (i for i in ideias if i["coluna"] == "no-ar"),
        key=lambda i: i["parada_desde"],
        reverse=True,
    )[:ENTREGAS_RECENTES]

    return render(
        request,
        "admin/caixa_mesa.html",
        {
            "quadro": quadro["quadro"],
            "primeira": decisoes[0] if decisoes else None,
            "depois": decisoes[1:],
            "total": len(decisoes),
            "em_obra": em_obra,
            "no_ar": no_ar,
            "pode_assinar": quadro.get("pode_assinar", False),
            "dias_ate_envelhecer": DIAS_ATE_A_ANALISE_ENVELHECER,
            "na_mesa": len(decisoes),
        },
    )


# ---------------------------------------------------------------------------
# Aba 2 — A TRAVESSIA: onde o trilho entope
# ---------------------------------------------------------------------------


@require_GET
def travessia(request):
    quadro = CaixaClient().ideias(por_email=_email(request))
    if quadro is None:
        return render(request, "admin/caixa_travessia.html", {"nao_respondeu": True})

    agora = datetime.now(tz.utc)
    ideias = _enriquecer(quadro["ideias"], agora)

    colunas = []
    for chave, titulo, explicacao in COLUNAS:
        na_coluna = [i for i in ideias if i["coluna"] == chave]
        dias = [i["parada_ha"] for i in na_coluna]
        colunas.append(
            {
                "chave": chave,
                "titulo": titulo,
                "explicacao": explicacao,
                "ideias": na_coluna,
                "total": len(na_coluna),
                # A média é do que está parado AGORA, não do que já passou por
                # ali — e o rótulo na tela diz isso. Tempo histórico de travessia
                # exigiria caminhar o histórico inteiro de cada ideia; chamar
                # esta média de "tempo médio de etapa" seria um número que parece
                # uma coisa e é outra.
                "parada_media": round(sum(dias) / len(dias)) if dias else None,
                "mais_velha": max(dias) if dias else None,
            }
        )

    saidas = [i for i in ideias if i["status"] in FORA_DO_TRILHO]
    com_gente = [c for c in colunas if c["parada_media"]]

    return render(
        request,
        "admin/caixa_travessia.html",
        {
            "quadro": quadro["quadro"],
            "colunas": colunas,
            "saidas": saidas,
            "no_trilho": sum(c["total"] for c in colunas),
            # O gargalo é CALCULADO (a maior espera média), nunca cravado — e
            # some quando não há espera nenhuma: alarme que toca sempre não é
            # alarme.
            "gargalo": (
                max(com_gente, key=lambda c: c["parada_media"]) if com_gente else None
            ),
            "na_mesa": len(esperando(ideias)),
        },
    )


# ---------------------------------------------------------------------------
# Aba 3 — QUEM ESTÁ ESPERANDO: a unidade da tela é a pessoa
# ---------------------------------------------------------------------------

DIAS_DE_SILENCIO_DEMAIS = 30

# As cinco etapas em que uma ideia em aberto pode estar, ditas como FRASE: elas
# completam o título "de onde vem a espera" no mapa do lado direito da tela, e é
# por isso que começam em minúscula e explicam em vez de nomear.
MOTIVOS = (
    ("assinar", "esperando você assinar"),
    ("chegando", "ninguém da equipe olhou ainda"),
    ("construindo", "robô construindo"),
    ("lendo", "na fila, andando normal"),
    ("pode-comecar", "assinada, esperando um robô"),
)

# As MESMAS etapas com o nome curto que a aba da travessia já usa, e não a frase
# de `MOTIVOS`. As duas dizem a mesma coisa em lugares diferentes: no mapa da
# direita a frase completa o título "de onde vem a espera"; dentro de um seletor
# ela seria uma linha de 29 caracteres cortada pela metade. Reusar `COLUNAS` faz
# esta tela e a travessia chamarem cada etapa pelo mesmo nome, que é como o
# mantenedor a lê nas duas.
#
# "No ar" fica de fora porque é entrega, e esta lista peneira só o que está em
# aberto. Que as duas listas não divirjam em silêncio é guardado por
# `test_as_duas_listas_de_etapa_falam_das_mesmas_etapas`.
ETAPAS = tuple((chave, titulo) for chave, titulo, _ in COLUNAS if chave != "no-ar")


def _nascimento(ideia) -> float:
    """Quando a ideia chegou, em segundos, para poder ser invertida.

    Segundos e não `datetime` porque as oito ordens abaixo são pares simétricos,
    e o par de uma chave se escreve trocando o sinal dela — um instante não tem
    sinal para trocar.

    Data que o contrato não entregou no formato prometido vira zero, o começo de
    tudo: ela aparece no alto de "mais antigas" em vez de derrubar a lista
    inteira com uma exceção. Numa tela que existe para achar o que ficou
    esquecido, o dado estranho tem de ficar VISÍVEL.
    """
    quando = _momento(ideia.get("criada_em", ""))
    return quando.timestamp() if quando else 0.0


# Como o mantenedor pode ler a lista. Pedido dele em 05/09/2026, com as palavras
# "mais novas, mais antigas, mais votadas, menos votadas".
#
# **Em pares simétricos, sempre.** Um seletor em que alguns critérios viram e
# outros não obriga a pessoa a decorar quais — e a pergunta "por que este aqui
# não inverte?" não tem resposta boa. São quatro perguntas, cada uma com os dois
# lados: quanta gente, quanto silêncio, quando chegou, quantos votos.
#
# **Votos e gente são coisas diferentes, e por isso as duas existem:** `votos`
# conta quem clicou em votar; `pessoas` conta a plateia inteira — quem escreveu,
# votou ou comentou. É a plateia que mede o silêncio, e é por isso que ela é a
# ordem padrão desta tela.
#
# O desempate é "mais gente primeiro" — empate em qualquer critério cai na
# pergunta que a tela existe para responder, que é quantas pessoas estão atrás —
# e, nas duas ordens que JÁ são por gente, o silêncio mais longo.
ORDENS = (
    ("gente", "Mais gente esperando", lambda i: (-i["pessoas"], -i["parada_ha"])),
    ("menos-gente", "Menos gente esperando", lambda i: (i["pessoas"], -i["parada_ha"])),
    ("silencio", "Mais tempo em silêncio", lambda i: (-i["parada_ha"], -i["pessoas"])),
    (
        "menos-silencio",
        "Menos tempo em silêncio",
        lambda i: (i["parada_ha"], -i["pessoas"]),
    ),
    ("novas", "Mais novas", lambda i: (-_nascimento(i), -i["pessoas"])),
    ("antigas", "Mais antigas", lambda i: (_nascimento(i), -i["pessoas"])),
    ("votadas", "Mais votadas", lambda i: (-i["votos"], -i["pessoas"])),
    ("menos-votadas", "Menos votadas", lambda i: (i["votos"], -i["pessoas"])),
)

#: A ordem de sempre, e a que responde um endereço sem `?ordem=`: a mesma com
#: que esta tela nasceu em 28/08/2026.
ORDEM_PADRAO = "gente"

#: Derivados de `ORDENS` e `ETAPAS`, nunca escritos à mão: ordem ou etapa nova
#: entra numa linha só, e a peneira a conhece no mesmo instante. O seletor não
#: recebe `ORDENS` inteira porque a terceira posição é uma função — mandar uma
#: função para um template é pedir que ele não a use.
ORDENS_NA_TELA = tuple((chave, rotulo) for chave, rotulo, _ in ORDENS)
_COMO_ORDENAR = {chave: como for chave, _, como in ORDENS}
_ETAPAS = {chave for chave, _ in ETAPAS}


@require_GET
def quem_espera(request):
    quadro = CaixaClient().ideias(por_email=_email(request))
    if quadro is None:
        return render(request, "admin/caixa_esperando.html", {"nao_respondeu": True})

    agora = datetime.now(tz.utc)
    ideias = _enriquecer(quadro["ideias"], agora)
    em_aberto = [i for i in ideias if i["status"] not in JA_RESPONDIDAS]

    # A ordem e a etapa vêm da barra de endereço, por GET: ler uma lista de outro
    # jeito é LEITURA, e a query string é o que torna o resultado recarregável,
    # marcável e colável num recado. Mesma escolha da peneira da lista de alunos.
    #
    # Pedido desconhecido cai no padrão e a tela DIZ isso — nunca uma lista vazia
    # nem um valor ignorado em silêncio, que passaria a lista inteira por
    # "resultado do que você pediu".
    ordem_pedida = (request.GET.get("ordem") or "").strip()
    ordem = ordem_pedida if ordem_pedida in _COMO_ORDENAR else ORDEM_PADRAO
    etapa_pedida = (request.GET.get("etapa") or "").strip()
    etapa = etapa_pedida if etapa_pedida in _ETAPAS else ""

    em_aberto.sort(key=_COMO_ORDENAR[ordem])
    na_tela = [i for i in em_aberto if i["coluna"] == etapa] if etapa else em_aberto

    respondidas = sorted(
        (i for i in ideias if i["status"] in JA_RESPONDIDAS),
        key=lambda i: i["parada_desde"],
        reverse=True,
    )[:ENTREGAS_RECENTES]

    return render(
        request,
        "admin/caixa_esperando.html",
        {
            "quadro": quadro["quadro"],
            "ideias": na_tela,
            "gente_esperando": quadro.get("pessoas_esperando", 0),
            "silencio_medio": quadro.get("silencio_medio_em_dias"),
            "em_silencio_demais": quadro.get("pessoas_em_silencio_demais", 0),
            "limiar": DIAS_DE_SILENCIO_DEMAIS,
            "respondidas": respondidas,
            # "De onde vem a espera" conta IDEIAS, e o rótulo na tela diz isso.
            # Contar PESSOAS por motivo exigiria deduplicar quem está atrás de
            # duas ideias em motivos diferentes, e essa dedução só existe do lado
            # da Caixa (é por isso que os três números do topo viajam prontos, e
            # estes não).
            #
            # Contados sobre TUDO que está em aberto, e não sobre o que a peneira
            # deixou passar: com o filtro em "robô construindo", contar o filtrado
            # zeraria as outras quatro linhas — e o mapa que existe para dizer
            # onde a espera nasce viraria um espelho do próprio filtro.
            "filas": [
                {
                    "rotulo": rotulo,
                    "chave": chave,
                    "ideias": sum(1 for i in em_aberto if i["coluna"] == chave),
                }
                for chave, rotulo in MOTIVOS
            ],
            # A régua da barrinha é a MAIOR plateia em aberto — `max`, e não a
            # primeira da lista: fora da ordem padrão a primeira não é a maior, e
            # a barra passaria de 100%. Pela mesma razão é medida antes da
            # peneira: uma barra que muda de escala conforme o filtro deixa de
            # poder ser comparada com a que estava ali um clique atrás.
            "maior_plateia": max((i["pessoas"] for i in em_aberto), default=1) or 1,
            "na_mesa": len(esperando(ideias)),
            # O que a pessoa escolheu, devolvido aos seletores: uma peneira que se
            # apaga ao recarregar faz o mantenedor achar que está vendo a lista
            # inteira.
            "ordens": ORDENS_NA_TELA,
            "ordem_escolhida": ordem,
            "etapas": ETAPAS,
            "etapa_escolhida": etapa,
            "pedido_desconhecido": (
                ordem_pedida not in ("", ordem) or etapa_pedida not in ("", etapa)
            ),
            # Só a etapa esconde ideias; a ordem nunca esconde nada. É por isso
            # que "mostrando 3 de 17" e o vazio-por-peneira olham só para ela.
            "filtrando": bool(etapa),
            "total_em_aberto": len(em_aberto),
        },
    )


# ---------------------------------------------------------------------------
# A ideia por dentro — e as três ações que mudam alguma coisa
# ---------------------------------------------------------------------------
#
# As cinco fases que a equipe escolhe. `mesclado` fica FORA, e a razão é da
# Caixa, não desta tela: mesclar é uma operação transacional inteira (mover
# votos sem duplicar ator, preservar comentários, manter a URL antiga
# resolvendo), e oferecê-la aqui daria um jeito de marcar "mesclado" sem que
# nada tivesse sido mesclado. A Caixa recusa de qualquer forma; a tela não
# oferece para a recusa não ser a primeira notícia.
FASES = (
    ("em_analise", "Em análise"),
    ("planejado", "Planejado"),
    ("em_desenvolvimento", "Em desenvolvimento"),
    ("implementado", "Implementado"),
    ("nao_planejado", "Não vamos fazer"),
)

# As três notas da avaliação interna, com o rótulo que a TELA usa — e não o nome
# do campo com underscores trocados por espaço. Quem lê a recusa é o mantenedor,
# e ele nunca viu a palavra "impacto_educacional" em lugar nenhum.
NOTAS_DA_AVALIACAO = (
    ("impacto_educacional", "Ajuda o aluno a aprender"),
    ("impacto_comercial", "Ajuda a escola a vender"),
    ("esforco_tecnico", "Trabalho que dá"),
)
NOTA_MINIMA = 0
NOTA_MAXIMA = 5

# Os três campos que a correção alcança, com o nome que a TELA usa — e não
# `solucao_proposta` com o underscore trocado por espaço. Quem lê o rastro é o
# mantenedor, que nunca viu nome de campo em lugar nenhum. A chave é o nome real
# que o contrato devolve; o valor é português.
NOME_DO_CAMPO = {
    "titulo": "o nome da ideia",
    "problema": "o texto do problema",
    "solucao_proposta": "a solução proposta",
}


def _quem(request) -> dict:
    """Quem está agindo, na forma que o contrato da Caixa pede.

    Os três campos vêm da porta, que já resolveu a pessoa pela `identidade`. O
    `id` é o que atravessa a plataforma, e a Caixa precisa dele para poder
    AFIRMAR quem moderou ([INV-SUG12]) — sem ele a escrita é recusada com
    instrução, e não com erro.
    """
    admin = getattr(request, "admin", None) or {}
    return {
        "por_email": admin.get("email") or "",
        "por_nome": admin.get("nome") or "",
        "por_id_da_plataforma": admin.get("id") or "",
    }


@require_GET
def ideia(request, ideia_id: int):
    """Uma ideia por dentro: o que o aluno escreveu, a avaliação e a história."""
    corpo = CaixaClient().uma_ideia(ideia_id)
    if corpo is None:
        return render(request, "admin/caixa_ideia.html", {"nao_respondeu": True})

    agora = datetime.now(tz.utc)
    (enriquecida,) = _enriquecer([corpo], agora)
    # O rastro das correções, com o nome do campo já em português. A tradução
    # acontece AQUI e não no template porque um `{{ dicionario|lookup:chave }}`
    # exigiria filtro próprio — e porque campo que o contrato passe a devolver
    # sem tradução aparece como o nome cru, que é feio e visível, em vez de
    # sumir da tela como uma linha vazia.
    for linha in enriquecida.get("correcoes") or []:
        linha["o_que"] = NOME_DO_CAMPO.get(linha.get("campo"), linha.get("campo"))
    quadro = CaixaClient().ideias(por_email=_email(request)) or {}

    return render(
        request,
        "admin/caixa_ideia.html",
        {
            "ideia": enriquecida,
            "fases": FASES,
            "pode_assinar": quadro.get("pode_assinar", False),
            # O número da etiqueta da aba: a MESMA função das outras telas.
            "na_mesa": len(esperando(_enriquecer(quadro.get("ideias", []), agora))),
            "recado": request.GET.get("recado", ""),
            "erro": request.GET.get("erro", ""),
        },
    )


def _voltar(ideia_id: int, desfecho: str, recado: str):
    """Volta para a ideia dizendo o que aconteceu — sempre pela mesma porta.

    Redirecionar depois de um POST é o que impede o F5 de repetir a ação; e o
    recado viaja na URL porque esta célula não tem sessão de mensagens e não vai
    ganhar uma para isto.
    """
    campo = "recado" if desfecho == CaixaClient.OK else "erro"
    return HttpResponseRedirect(
        f"{reverse('caixa_ideia', args=[ideia_id])}?{urlencode({campo: recado})}"
    )


def _agir(request, ideia_id, acao, chamada, ok, alvo_extra=""):
    """O gesto comum das três ações: chamar, auditar e voltar dizendo.

    A auditoria acontece nos TRÊS desfechos, e o recusado é o que justifica ela
    existir: quando a Caixa diz não, nada é escrito lá — sem esta linha, o gesto
    não teria deixado rastro em lugar nenhum.
    """
    desfecho, recado = chamada()
    _auditar(
        request,
        acao,
        f"ideia:{ideia_id}{alvo_extra}",
        {
            CaixaClient.OK: Registro.OK,
            CaixaClient.RECUSADO: Registro.RECUSADO_PELA_CELULA,
        }.get(desfecho, Registro.NAO_RESPONDEU),
        detalhe=recado,
    )
    return _voltar(ideia_id, desfecho, ok if desfecho == CaixaClient.OK else recado)


@require_POST
def mover_ideia(request, ideia_id: int):
    fase = (request.POST.get("fase") or "").strip()
    nota = (request.POST.get("nota") or "").strip()
    if fase not in {valor for valor, _ in FASES}:
        return _voltar(
            ideia_id, CaixaClient.RECUSADO, "Escolha uma das fases da lista."
        )
    return _agir(
        request,
        ideia_id,
        Registro.MOVER_IDEIA,
        lambda: CaixaClient().mudar_status(
            ideia_id, status=fase, nota=nota, quem=_quem(request)
        ),
        "Pronto: a ideia mudou de fase, e todo mundo que interagiu com ela foi avisado.",
        alvo_extra=f":{fase}",
    )


@require_POST
def avaliar_ideia(request, ideia_id: int):
    """A avaliação interna. Nota fora de 0–5 é RECUSADA, nunca corrigida calada.

    Até 30/08/2026 esta tela fazia `max(0, min(5, ...))`: quem digitasse 9 via
    a página voltar dizendo "Avaliação guardada" com um 5 guardado, e quem
    digitasse "cinco" via um 0. A tela antiga da Caixa (`moderacao.avaliar`)
    recusava com uma frase em português — não é função a mais, é a diferença
    entre "não entendi o que você escreveu" e "escrevi outra coisa no seu
    lugar". Arredondar em silêncio é falso-verde de produto
    (`RETROSPECTIVA-FASE-D` §1): a resposta de sucesso descrevia um dado que
    ninguém pediu.
    """
    notas = {}
    for campo, rotulo in NOTAS_DA_AVALIACAO:
        cru = (request.POST.get(campo) or "").strip()
        try:
            valor = int(cru or 0)
        except ValueError:
            # -1 cai no mesmo lugar que 9 ou -3: uma frase só, porque para quem
            # preenche a diferença entre "não é número" e "é número demais" não
            # muda o que ele precisa fazer.
            valor = -1
        if not NOTA_MINIMA <= valor <= NOTA_MAXIMA:
            return _voltar(
                ideia_id,
                CaixaClient.RECUSADO,
                f"A nota de “{rotulo}” vai de {NOTA_MINIMA} a {NOTA_MAXIMA} — "
                "nada foi guardado.",
            )
        notas[campo] = valor

    campos = {
        **notas,
        "notas": (request.POST.get("notas") or "").strip(),
        "decisao_produto": (request.POST.get("decisao_produto") or "").strip(),
    }
    return _agir(
        request,
        ideia_id,
        Registro.AVALIAR_IDEIA,
        lambda: CaixaClient().avaliar(ideia_id, campos=campos, quem=_quem(request)),
        "Avaliação guardada. O aluno não vê nada disto.",
    )


@require_POST
def assinar_obra(request, ideia_id: int):
    campos = {
        "change_id": (request.POST.get("change_id") or "").strip(),
        "documento": (request.POST.get("documento") or "").strip(),
        "aprovado_por": (request.POST.get("aprovado_por") or "").strip(),
        "aprovado_em": (request.POST.get("aprovado_em") or "").strip(),
    }
    return _agir(
        request,
        ideia_id,
        Registro.ASSINAR_OBRA,
        lambda: CaixaClient().registrar_changespec(
            ideia_id, campos=campos, quem=_quem(request)
        ),
        "Assinado. A ideia já pode entrar em construção.",
        alvo_extra=f":{campos['change_id']}",
    )


@require_POST
def arquivar_ideia(request, ideia_id: int):
    """`DECISAO-arquivar-ideia.md`: some do quadro do aluno, nada se perde."""
    motivo = (request.POST.get("motivo") or "").strip()
    return _agir(
        request,
        ideia_id,
        Registro.ARQUIVAR_IDEIA,
        lambda: CaixaClient().arquivar(ideia_id, motivo=motivo, quem=_quem(request)),
        "Arquivada. Ela some do quadro do aluno; nada foi apagado, e dá para "
        "trazer de volta quando quiser.",
    )


@require_POST
def desarquivar_ideia(request, ideia_id: int):
    return _agir(
        request,
        ideia_id,
        Registro.DESARQUIVAR_IDEIA,
        lambda: CaixaClient().desarquivar(ideia_id, quem=_quem(request)),
        "Restaurada. A ideia volta a aparecer para o aluno, exatamente como estava.",
    )


@require_POST
def apagar_ideia(request, ideia_id: int):
    """`DECISAO-apagar-ideia.md`: sem volta, nem para quem criou.

    A confirmação ("tem certeza?") é só do lado do cliente (JavaScript no
    template) — decisão do mantenedor, pela fricção mínima. O servidor não
    tem como saber se a pessoa confirmou; o que ele garante é o resto: quem
    agiu, e a auditoria nos três desfechos, como as demais ações.
    """
    return _agir(
        request,
        ideia_id,
        Registro.APAGAR_IDEIA,
        lambda: CaixaClient().apagar(ideia_id, quem=_quem(request)),
        "Apagada para sempre. Título, texto, votos e comentários não existem "
        "mais em lugar nenhum — nem eu consigo trazer de volta.",
    )


@require_POST
def corrigir_ideia(request, ideia_id: int):
    """`DECISAO-corrigir-o-texto-de-uma-ideia.md`: o erro de digitação some.

    Os três campos viajam inteiros, como o contrato pede — e esta tela NÃO
    calcula o que mudou. Quem calcula é a Caixa, comparando com o que está
    gravado agora; fazer a conta aqui seria decidir, com o texto que a página
    carregou minutos atrás, uma coisa que só a dona do dado sabe. Se nada mudou,
    a recusa dela chega pronta e em português, e é ela que aparece na tela.

    Sem `strip()` aqui pelo mesmo motivo: as réguas (nome obrigatório, 140
    caracteres, problema obrigatório) moram todas do outro lado, num lugar só.
    Uma segunda cópia delas nesta view seria a primeira a ficar desatualizada.
    """
    campos = {
        "titulo": request.POST.get("titulo") or "",
        "problema": request.POST.get("problema") or "",
        "solucao_proposta": request.POST.get("solucao_proposta") or "",
    }
    return _agir(
        request,
        ideia_id,
        Registro.CORRIGIR_IDEIA,
        lambda: CaixaClient().corrigir_texto(
            ideia_id, campos=campos, quem=_quem(request)
        ),
        "Texto corrigido. O aluno vê a versão nova sem nenhuma marca — e o que "
        "estava escrito antes fica guardado aqui embaixo, só para você.",
    )


# ---------------------------------------------------------------------------
# Aba 5 — EXPORTAR: a Caixa inteira em texto, para levar embora
# ---------------------------------------------------------------------------
#
# Nasceu em 02/09/2026, de um pedido que esbarrou numa parede: o mantenedor
# pediu uma análise das sugestões dos alunos, e o robô descobriu que não
# consegue ler UMA linha do que eles escreveram. Não é falta de permissão, é o
# desenho: o texto de uma ideia só existe atrás do login, e a porta da
# administração é dele. A mesma parede já estava no livro desde 31/08, com
# estas palavras (registro `20260831-002`): *"eu enxergo a contagem, não o
# conteúdo"*.
#
# O conserto de quem sabe menos seria pedir a ele que abrisse ideia por ideia e
# copiasse cada uma. Esta tela é o conserto de quem sabe mais: uma vez, um
# gesto, e a Caixa inteira vira texto que ele leva para onde quiser.
#
# TRÊS ESCOLHAS que parecem detalhe e não são:
#
# 1. **Sem o nome de quem escreveu.** As outras telas mostram, e devem: lá ele
#    decide sobre a ideia de uma pessoa, e saber de quem é faz parte. Aqui o
#    texto FOI FEITO PARA SAIR daqui — o próximo lugar onde ele vive é uma
#    conversa com uma IA, um documento, um e-mail. Nome de aluno não precisa
#    fazer essa viagem para a análise funcionar, e o que não precisa viajar não
#    viaja.
# 2. **Sem JavaScript.** A porta manda `script-src 'self'` em toda resposta
#    (`porta.py`) e esta célula não serve estático nenhum, então um botão
#    "copiar" custaria um arquivo servido e uma exceção na política. Um campo
#    de texto resolve o mesmo problema com zero risco: clicar dentro dele e
#    apertar Ctrl+A seleciona só o conteúdo dele, nunca a página em volta.
# 3. **O texto se explica sozinho.** O cabeçalho do que sai diz o que NÃO está
#    ali e por quê. Quem receber isto do outro lado — uma IA, daqui a um mês —
#    não tem como adivinhar que a contagem de comentários vem sem o texto dos
#    comentários, e análise que não sabe o que falta inventa o que falta.

# O nome humano de cada etapa, tirado das MESMAS colunas da travessia. Uma
# segunda tabela de rótulos aqui seria uma segunda definição de etapa, e a que
# ninguém olha é a que envelhece errada.
ETAPA_DA_COLUNA = {chave: titulo for chave, titulo, _ in COLUNAS}

# As duas saídas do trilho, em português de gente. `mesclado` não é "mesclado"
# para ninguém que não escreveu o código.
ETAPA_FORA_DO_TRILHO = {
    "nao_planejado": "Recusada",
    "mesclado": "Juntada a outra ideia",
}

RISCA = "=" * 66


def _plural(quantos: int, singular: str, plural: str) -> str:
    """`1 voto` / `2 votos` — sem o `|pluralize` do template, que aqui não existe."""
    return f"{quantos} {singular if quantos == 1 else plural}"


def _data_curta(iso: str) -> str:
    """Uma data do contrato em português, ou uma frase honesta se não der.

    O contrato promete o FORMATO ISO, não a precisão dele. `fromisoformat`
    aceita as duas formas que o Django emite; qualquer outra coisa vira texto
    dizendo que não sabemos, nunca um estouro no meio de uma exportação de 40
    ideias por causa de uma data torta.
    """
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m/%Y")
    except ValueError:
        return "data desconhecida"


def _etapa_de(ideia) -> str:
    if ideia["status"] in ETAPA_FORA_DO_TRILHO:
        return ETAPA_FORA_DO_TRILHO[ideia["status"]]
    return ETAPA_DA_COLUNA.get(ideia["coluna"], ideia["status"])


def _bloco_da_ideia(ideia) -> list:
    """Uma ideia virada texto. Lista de linhas, para o chamador juntar."""
    linhas = [
        RISCA,
        f"IDEIA {ideia['id']} · {_plural(ideia['votos'], 'voto', 'votos')} · "
        f"{_plural(ideia['pessoas'], 'pessoa atrás dela', 'pessoas atrás dela')} · "
        f"{_plural(ideia['comentarios'], 'comentário', 'comentários')}",
        f"Título: {ideia['titulo']}",
        f"Categoria: {ideia['categoria']}",
        f"Etapa: {_etapa_de(ideia)}",
        f"Criada em {_data_curta(ideia['criada_em'])} · "
        f"nesta etapa há {_plural(ideia['parada_ha'], 'dia', 'dias')}",
    ]

    avaliacao = ideia.get("avaliacao")
    if avaliacao:
        notas = " · ".join(
            f"{rotulo.lower()}: {avaliacao.get(campo, 0)} de 5"
            for campo, rotulo in NOTAS_DA_AVALIACAO
        )
        linhas.append(f"Avaliação da equipe · {notas}")
        if avaliacao.get("decisao_produto"):
            linhas.append(f"Decisão de produto: {avaliacao['decisao_produto']}")
    else:
        linhas.append("Avaliação da equipe: ninguém escreveu nada ainda.")

    if ideia.get("motivo_da_saida"):
        linhas.append(f"Motivo que a pessoa recebeu: {ideia['motivo_da_saida']}")

    linhas += ["", "O que trava, nas palavras de quem escreveu:", ideia["problema"]]
    if ideia.get("solucao_proposta"):
        linhas += ["", "O que a pessoa propõe:", ideia["solucao_proposta"]]

    # A conversa embaixo da ideia. Ela entra depois do texto de quem sugeriu, e
    # não antes, porque é isso que ela é: gente respondendo a uma proposta que
    # já está na mesa. Sem nome, como tudo que sai por aqui — e o contrato nem
    # manda o nome, então não há o que esquecer de tirar.
    conversa = ideia.get("conversa") or []
    if conversa:
        linhas += ["", f"O que os outros disseram ({len(conversa)}):"]
        linhas += [f"  - {fala['texto']}" for fala in conversa]

    linhas.append("")
    return linhas


def texto_do_quadro(nome_do_quadro: str, ideias: list, agora: datetime) -> str:
    """A Caixa inteira em texto corrido, pronta para copiar.

    Mora no Python e não no template porque o que sai é TEXTO, e no template
    cada quebra de linha viraria uma briga com o HTML — aqui a quebra de linha
    É o formato.

    A ordem é a mais votada primeiro, e ela está dita no cabeçalho: ordem
    silenciosa em texto que vai para análise é uma opinião disfarçada de dado.
    """
    ordenadas = sorted(ideias, key=lambda i: (-i["votos"], -i["pessoas"], i["id"]))

    cabecalho = [
        f"CAIXA DE SUGESTÕES · {nome_do_quadro}",
        f"Exportado em {agora.strftime('%d/%m/%Y, %H:%M')} (UTC) "
        f"da área administrativa de meshcraft.top.",
        (
            f"{_plural(len(ordenadas), 'ideia no quadro', 'ideias no quadro')}, "
            "da mais votada para a menos votada."
            if ordenadas
            else "O quadro está VAZIO: nenhum aluno escreveu nada até agora."
        ),
        "",
        "O que não está neste texto, e por quê:",
        "· Quem escreveu cada ideia. Este texto foi feito para sair da área",
        "  administrativa, e a análise não precisa do nome de ninguém.",
        "· Quem escreveu cada comentário. O texto das falas vem inteiro, o nome",
        "  de quem falou não.",
        "· As ideias arquivadas e as apagadas. Arquivar é dizer que aquilo saiu",
        "  do quadro; apagar destrói o texto para sempre.",
        "",
    ]

    corpo = []
    for ideia in ordenadas:
        corpo += _bloco_da_ideia(ideia)

    return "\n".join(cabecalho + corpo + [RISCA, "FIM DA EXPORTAÇÃO."])


@require_GET
def exportar(request):
    quadro = CaixaClient().ideias(por_email=_email(request), com_conversa=True)
    if quadro is None:
        return render(request, "admin/caixa_exportar.html", {"nao_respondeu": True})

    agora = datetime.now(tz.utc)
    ideias = _enriquecer(quadro["ideias"], agora)

    return render(
        request,
        "admin/caixa_exportar.html",
        {
            "quadro": quadro["quadro"],
            "texto": texto_do_quadro(quadro["quadro"], ideias, agora),
            "total": len(ideias),
            "na_mesa": len(esperando(ideias)),
        },
    )


def _email(request) -> str:
    """O e-mail de quem está olhando — a porta já o resolveu pela `identidade`.

    Serve para UMA pergunta: esta pessoa pode assinar? A Caixa responde, e a tela
    usa a resposta para não desenhar um botão que já se sabe que será recusado. A
    recusa de verdade continua acontecendo lá, na escrita.

    `request.admin` está garantido em toda view não isenta (o middleware o
    monta), mas o `.get` com default existe para o caso de alguém chamar esta
    função de um caminho isento um dia — e "não sei o e-mail" tem de virar "não
    pode assinar", nunca um estouro.
    """
    return (getattr(request, "admin", None) or {}).get("email") or ""
