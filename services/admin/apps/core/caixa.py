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

from django.shortcuts import render
from django.views.decorators.http import require_GET

from .clients import CaixaClient

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


def _dias(desde: str, agora: datetime) -> int:
    """Dias entre uma data do contrato e agora.

    O contrato manda texto ISO com fuso; `fromisoformat` o entende desde o
    Python 3.11. Um `strptime` com formato cravado quebraria no dia em que o
    provedor mudasse de microssegundos para segundos — e o contrato não promete
    a precisão, promete o formato.
    """
    try:
        quando = datetime.fromisoformat(desde)
    except ValueError:
        return 0
    if quando.tzinfo is None:
        quando = quando.replace(tzinfo=tz.utc)
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


@require_GET
def quem_espera(request):
    quadro = CaixaClient().ideias(por_email=_email(request))
    if quadro is None:
        return render(request, "admin/caixa_esperando.html", {"nao_respondeu": True})

    agora = datetime.now(tz.utc)
    ideias = _enriquecer(quadro["ideias"], agora)
    em_aberto = [i for i in ideias if i["status"] not in JA_RESPONDIDAS]
    # Gente esperando primeiro; entre iguais, o silêncio mais longo.
    em_aberto.sort(key=lambda i: (-i["pessoas"], -i["parada_ha"]))

    respondidas = sorted(
        (i for i in ideias if i["status"] in JA_RESPONDIDAS),
        key=lambda i: i["parada_desde"],
        reverse=True,
    )[:ENTREGAS_RECENTES]

    # "De onde vem a espera" conta IDEIAS, e o rótulo na tela diz isso. Contar
    # PESSOAS por motivo exigiria deduplicar quem está atrás de duas ideias em
    # motivos diferentes, e essa dedução só existe do lado da Caixa (é por isso
    # que os três números do topo viajam prontos, e estes não).
    motivos = [
        ("assinar", "esperando você assinar"),
        ("chegando", "ninguém da equipe olhou ainda"),
        ("construindo", "robô construindo"),
        ("lendo", "na fila, andando normal"),
        ("pode-comecar", "assinada, esperando um robô"),
    ]

    return render(
        request,
        "admin/caixa_esperando.html",
        {
            "quadro": quadro["quadro"],
            "ideias": em_aberto,
            "gente_esperando": quadro.get("pessoas_esperando", 0),
            "silencio_medio": quadro.get("silencio_medio_em_dias"),
            "em_silencio_demais": quadro.get("pessoas_em_silencio_demais", 0),
            "limiar": DIAS_DE_SILENCIO_DEMAIS,
            "respondidas": respondidas,
            "filas": [
                {
                    "rotulo": rotulo,
                    "chave": chave,
                    "ideias": sum(1 for i in em_aberto if i["coluna"] == chave),
                }
                for chave, rotulo in motivos
            ],
            "maior_plateia": em_aberto[0]["pessoas"] if em_aberto else 1,
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
