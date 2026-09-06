# apps/core/robos.py — a aba "Os robôs": o quadro da fila, calculado, nunca digitado
"""A quarta aba da gestão da Caixa, esperada desde 28/08/2026.

Ela ficou apagada na tela ("falta a fonte de dados, não a tela") até a fonte
existir de verdade: a FILA DE TRABALHO (`fila/` na raiz do repositório, fase 2
do plano de 29/08/2026 — desenho em
`docs/consultorias/central-de-orquestracao/VEREDITO.md`).

## De onde vêm os dados — e por que esta célula NÃO recalcula nada

| O quê | De onde | Quem escreveu |
|---|---|---|
| O quadro (estados) | `fila_embutida/estados.json` | `ci/fila.py listar --json`, no build (escritor único) |
| As tarefas/eventos | `fila_embutida/tarefas|eventos/` | os robôs, por PR |
| A régua das esperas | `fila_embutida/regua.json` | `ci/medir_tempos.py` (a régua viva) |
| Os estouros | `fila_embutida/esperas/resumo-*.json` | `ci/exportar_esperas.py` (curado e redigido) |
| Ao vivo (reservas/PRs) | api.github.com, DO NAVEGADOR | o servidor do GitHub |

Recalcular estados aqui seria a segunda definição de "em que pé está" — a
mesma dupla contagem que `caixa.py` evita nos números da mesa. O retrato é o
do último deploy, e a página DIZ isso (carimbo de geração à vista); o que é
de agora (reservas do almoxarife, PRs abertos) o navegador do dono pergunta
direto ao GitHub — o repositório é público de propósito, zero backend novo.

## O CSP desta rota

A porta manda `script-src 'self'` em toda resposta (`porta.py`, via
`setdefault` — resposta que traz o próprio CSP vence). Esta página tem uma
ilha de script embutida (o bloco "ao vivo"), então o CSP dela declara o hash
da ilha — o MESMO desenho de `painel.py`, e pelo mesmo motivo: `'unsafe-inline'`
nunca entra. A diferença única: `connect-src` inclui `https://api.github.com`,
senão o navegador bloquearia a pergunta ao GitHub e o bloco "ao vivo" morreria
em silêncio (falha silenciosa é a pior — RETROSPECTIVA-FASE-D §1).
"""

import base64
import hashlib
import json
import re
from pathlib import Path

from django.shortcuts import render
from django.views.decorators.http import require_GET

RAIZ_DA_CELULA = Path(__file__).resolve().parent.parent.parent

# Em produção só a primeira existe (o deploy embute); num checkout, nenhuma —
# e a página diz que a fila não veio, em vez de fingir fila vazia. Não há
# fallback para `<repo>/fila/` de propósito: os ESTADOS são materializados no
# build (`estados.json`), e um fallback que recalculasse aqui seria a segunda
# definição que o cabeçalho proíbe.
CANDIDATOS = (RAIZ_DA_CELULA / "fila_embutida",)

# OS GRUPOS DO QUADRO, na ordem em que aparecem na tela — e a ordem é POR
# URGÊNCIA PARA O MANTENEDOR, não a ordem do fluxo de trabalho. O que pode
# precisar dele vem primeiro; a história antiga vem por último e nasce fechada.
#
# Antes de 03/09/2026 esta ordem era a do fluxo (na fila → reivindicada → …
# → concluída), desenhada lado a lado como colunas de um kanban. Com 101
# tarefas na fila as colunas tinham 12, 2, 11 e SETENTA E SEIS cartões, e o
# mantenedor abriu a tela e disse que não conseguia acompanhá-la. Kanban de
# coluna serve para quem MOVE cartão; ele não move nenhum, ele quer saber o que
# parou esperando por ele.
#
# Cada grupo carrega cinco coisas para a tela:
#   estado     a chave do dado, vocabulário de CONTRATO de `ci/fila.py` — o
#              template casa por ela, e ela NUNCA muda por motivo de tela;
#   espera     só nos parados: qual das duas paradas é esta (`ci/fila.py`,
#              QUEM_DESTRAVA). Ausente nos demais, que casam só pelo estado;
#   rotulo     a mesma coisa em português de gente, que é o que se lê;
#   curto      o rótulo do placar de números lá em cima;
#   recolhida  nasce dentro de um `details` fechado (história, não pendência).
#
# A cor da borda diz AÇÃO EXIGIDA, nunca prioridade (consultoria:
# desenho-kanban-cores-Gemini). O âmbar existe num grupo só, e agora é verdade:
# até 06/09/2026 ele pintava as 27 paradas de uma vez, e SEIS delas eram dele.
COLUNAS = (
    {
        "estado": "bloqueada",
        "espera": "mantenedor",
        "rotulo": "Esperando uma decisão sua",
        "curto": "esperando VOCÊ",
        # Esta frase pôde ficar afirmativa porque o dado passou a responder.
        # A versão anterior era neutra por honestidade: dizia "umas esperam
        # outra tarefa, outras esperam uma decisão de gente" porque a fila não
        # guardava a diferença, e chutá-la aqui seria uma segunda definição de
        # "o que espera por você". A cura não foi escrever melhor: foi o evento
        # `bloqueada` passar a declarar quem destrava.
        #
        # Isto NÃO duplica a aba "Quem está esperando" (`caixa.esperando`): lá
        # são IDEIAS da Caixa de Sugestões esperando assinatura ou triagem, que
        # vêm da API da Caixa. Aqui são TAREFAS da fila de trabalho. Duas
        # perguntas diferentes, duas fontes diferentes, nenhum fato em comum.
        "explicacao": "Nenhum robô tira estas do lugar: elas dependem de uma autorização, uma decisão ou uma prova que só você pode dar. O que fazer em cada uma está escrito no cartão.",
        "cor": "ambar",
        "recolhida": False,
    },
    {
        "estado": "em execução",
        "rotulo": "O trabalho já está pronto, esperando conferência",
        "curto": "na conferência",
        "explicacao": "Um robô mandou o trabalho e a esteira está conferindo. Ninguém precisa fazer nada.",
        "cor": "roxo",
        "recolhida": False,
    },
    {
        "estado": "reivindicada",
        "rotulo": "Um robô pegou, e está com ela agora",
        "curto": "com um robô agora",
        "explicacao": "Reservou no servidor para nenhum outro robô pisar em cima, e ainda não mandou o trabalho.",
        "cor": "roxo",
        "recolhida": False,
    },
    {
        "estado": "na fila",
        "rotulo": "Esperando um robô pegar",
        "curto": "esperando um robô",
        "explicacao": "Prontas para trabalho. Ninguém pegou ainda.",
        "cor": "azul",
        "recolhida": False,
    },
    {
        "estado": "bloqueada",
        "espera": "fila",
        "rotulo": "Esperando outra tarefa terminar",
        "curto": "na corrente",
        "explicacao": "Cada uma depende de uma tarefa que vem antes dela, e se destrava sozinha quando aquela terminar. Nada aqui é seu.",
        # Recolhida, e é a mudança que mais muda a tela: em 06/09/2026 eram 13
        # cartões ocupando o topo com o mesmo âmbar de urgência das que
        # esperavam por ele. Corrente de trabalho é consulta, não notícia.
        "cor": "roxo",
        "recolhida": True,
    },
    {
        "estado": "concluída",
        "rotulo": "Já terminaram, com prova conferida",
        "curto": "já terminaram",
        "explicacao": "Cada uma traz o endereço do trabalho que a fechou. Clique para ver.",
        "cor": "verde",
        "recolhida": True,
    },
    {
        "estado": "cancelada",
        "rotulo": "Não vão mais ser feitas",
        "curto": "canceladas",
        "explicacao": "Alguém decidiu tirar da fila. O motivo fica no cartão.",
        "cor": "cinza",
        "recolhida": True,
    },
)

# ONDE A TAREFA MEXE, dito em lugares que o mantenedor reconhece (03/09/2026).
#
# O campo `toca` da fila usa 24 nomes técnicos — `ci`, `mensageria`, `funil`,
# `.github`, `contracts`. Para quem escreve código eles são endereços; para o
# dono do negócio não são nada. Ele abriu a tela e disse que não estava
# conseguindo entender o que via, e "mexe em: ci" é parte do motivo.
#
# ISTO É TRADUÇÃO DE TELA, NÃO FONTE. O `toca` continua sendo o vocabulário de
# contrato da fila, intocado no dado: é ele que autoriza duas tarefas a rodarem
# em paralelo e é ele que `ci/conferencia_do_toca.py` compara com o diff. Aqui
# só se escolhe como escrever aquilo na tela, do mesmo jeito que `rotulo` faz
# com os estados.
#
# **A regra de ouro deste dicionário é FALHAR ABERTO**: nome que não está aqui
# aparece na tela como está, cru. Célula nova nasce a cada duas semanas neste
# projeto, e uma tradução que ESCONDESSE o desconhecido faria a tela mentir por
# omissão — o dono veria uma tarefa "sem lugar" em vez de um nome estranho, e
# nunca perguntaria. Nome estranho ele pergunta; ausência, não.
ONDE_ISSO_MEXE = {
    "admin": "a sua área de administração",
    "alunos": "o cadastro dos alunos",
    "catalogo": "o catálogo de cursos",
    "checkout": "a tela de pagamento",
    "escola": "a área do aluno",
    "forum": "o fórum",
    "funil": "as páginas que vendem",
    "gamificacao": "os pontos e as medalhas",
    "identidade": "o login e o cadastro",
    "mensageria": "os avisos e os e-mails",
    "notificacoes": "o sininho de avisos",
    "quiz": "o quiz",
    "sugestoes": "a Caixa de Sugestões",
    # A oficina: o aluno nunca vê nada disto, e por isso as sete entram com o
    # MESMO rótulo. Distinguir `ci` de `.github` na tela dele seria precisão
    # sem uso — ele não decide nada com base nessa diferença.
    ".github": "a fábrica (ferramenta dos robôs)",
    "armadilhas": "a fábrica (ferramenta dos robôs)",
    "ci": "a fábrica (ferramenta dos robôs)",
    "contracts": "a fábrica (ferramenta dos robôs)",
    "docs": "a fábrica (ferramenta dos robôs)",
    "fila": "a fábrica (ferramenta dos robôs)",
    "infra": "a fábrica (ferramenta dos robôs)",
    "painel": "o seu painel",
    "documentos": "os documentos do site",
}


def onde_isso_mexe(toca) -> list[str]:
    """Os lugares de uma tarefa, traduzidos, sem repetir e em ordem estável.

    `services/funil` e `funil` são o mesmo lugar para quem lê — o `toca` aceita
    as duas formas, e sem o corte a tela mostraria o lugar duas vezes.
    """
    lugares = []
    for nome in toca or []:
        curto = str(nome).rsplit("/", 1)[-1].removesuffix(".md")
        lugar = ONDE_ISSO_MEXE.get(curto, curto)
        if lugar not in lugares:
            lugares.append(lugar)
    return lugares


def e_deste_grupo(dados: dict, grupo: dict) -> bool:
    """A tarefa cai neste grupo da tela?

    Estado igual basta para cinco dos sete grupos. Os dois de PARADAS dividem o
    mesmo estado (`bloqueada`) e se separam por `espera`, que `ci/fila.py`
    calcula: `mantenedor` para quem declarou que só o dono destrava, `fila` para
    quem espera outra tarefa terminar.

    **Falha para o lado de MOSTRAR.** Uma parada cujo `espera` não é nenhum dos
    dois — dado de um build antigo, campo que um dia mude de nome — vai para o
    grupo do mantenedor, e não some. Um cartão a mais no bloco dele custa uma
    leitura; um cartão que desaparece da única tela que responde "em que pé
    está" custa uma tarefa esquecida, e ninguém nunca ficaria sabendo. É a mesma
    regra do `ONDE_ISSO_MEXE` acima, pelo mesmo motivo: o que a tela não
    reconhece ela mostra, nunca engole.
    """
    if dados.get("estado") != grupo["estado"]:
        return False
    esperado = grupo.get("espera")
    if esperado is None:
        return True
    if esperado == "mantenedor":
        return dados.get("espera") != "fila"
    return dados.get("espera") == esperado


_SCRIPT_EMBUTIDO = re.compile(
    rb"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.DOTALL | re.IGNORECASE
)


def diretorio_da_fila() -> Path | None:
    for candidato in CANDIDATOS:
        if (candidato / "estados.json").is_file():
            return candidato
    return None


def _ler_json(caminho: Path):
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _resumo_de_esperas(pasta: Path):
    """O resumo curado mais RECENTE (nome maior vence — carimbo no nome)."""
    resumos = sorted((pasta / "esperas").glob("resumo-*.json"))
    if not resumos:
        return None
    return _ler_json(resumos[-1])


def andamento(pasta: Path) -> dict:
    """Quando cada tarefa se mexeu pela última vez, e quantas terminaram por dia.

    **Por que isto existe.** Um quadro com 101 cartões responde "o quê", e não
    responde "isto está andando?". Sem essa segunda resposta o dono olha para
    76 tarefas concluídas e não sabe se são de ontem ou de um mês atrás — foi
    parte do que ele chamou de "não estou conseguindo acompanhar" em
    03/09/2026.

    **A fonte é a mesma pasta que o deploy embute** (`fila/eventos/`, copiada
    inteira por `deploy-celula.yml`), e cada evento já carrega `quando`. Nada
    aqui é recalculado nem inventado: só se conta o que a fila já escreveu.
    Estado continua sendo assunto de `estados.json`; isto é só o relógio.

    **Falha aberto.** Sem a pasta (num checkout, ou se o build parar de
    embutir), devolve vazio e a tela simplesmente não mostra as datas, em vez
    de quebrar. Data ausente é uma tela mais pobre; página 500 é uma tela que
    não existe.
    """
    ultima_mexida: dict[str, str] = {}
    terminadas_por_dia: dict[str, int] = {}

    for arquivo in sorted((pasta / "eventos").glob("*.json")):
        evento = _ler_json(arquivo)
        if not isinstance(evento, dict):
            continue
        tarefa, quando = evento.get("tarefa"), evento.get("quando")
        if not (tarefa and isinstance(quando, str)):
            continue
        dia = quando[:10]
        # Os arquivos vêm ordenados por nome, e o nome COMEÇA pelo carimbo de
        # tempo — então o último a passar por aqui é mesmo o mais recente.
        ultima_mexida[tarefa] = dia
        if evento.get("evento") == "concluida":
            terminadas_por_dia[dia] = terminadas_por_dia.get(dia, 0) + 1

    dias = sorted(terminadas_por_dia)
    total = sum(terminadas_por_dia.values())
    return {
        "ultima_mexida": ultima_mexida,
        "terminadas": total,
        "primeiro_dia": dias[0] if dias else None,
        "ultimo_dia": dias[-1] if dias else None,
        # Média sobre os dias em que houve conclusão — nunca sobre o calendário
        # inteiro, que inventaria zeros para dias que ninguém mediu.
        #
        # Sai como TEXTO, com vírgula: o Django escreveria o número do jeito do
        # Python ("15.2"), e ponto decimal numa tela em português é a marca de
        # que a página foi traduzida pela metade.
        "por_dia": (
            f"{round(total / len(dias), 1):.1f}".replace(".", ",") if dias else None
        ),
        "quantos_dias": len(dias),
    }


def em_portugues(segundos) -> str:
    """ "90" vira "1 minuto e meio"; "900" vira "15 minutos".

    A régua das esperas é medida em segundos porque é assim que se mede, e a
    tabela mostrava o número cru com um "s" colado. Para quem não trabalha com
    isso, "420s" não é um tempo: é um número. A conversão acontece SÓ aqui, na
    borda da tela — a medição não muda de unidade.
    """
    if not isinstance(segundos, (int, float)):
        return "não medido"
    segundos = int(segundos)
    if segundos < 90:
        return f"{segundos} segundos"
    minutos = segundos / 60
    if minutos < 60:
        # "1 minuto e meio" é mais legível que "1,5 minutos", e a meia hora é a
        # única fração que vale a pena escrever por extenso.
        if abs(minutos - round(minutos)) < 0.1:
            inteiros = round(minutos)
            return f"{inteiros} minuto" + ("s" if inteiros != 1 else "")
        if abs(minutos - int(minutos) - 0.5) < 0.1:
            inteiros = int(minutos)
            return (
                "meio minuto"
                if inteiros == 0
                else f"{inteiros} minuto{'s' if inteiros != 1 else ''} e meio"
            )
        return f"cerca de {round(minutos)} minutos"
    horas = round(segundos / 3600, 1)
    return f"{horas:g} hora" + ("s" if horas != 1 else "")


def _csp(html: bytes) -> str:
    hashes = " ".join(
        "'sha256-"
        + base64.b64encode(hashlib.sha256(m.group(1)).digest()).decode()
        + "'"
        for m in _SCRIPT_EMBUTIDO.finditer(html)
    )
    return (
        "default-src 'self'; "
        f"script-src 'self' {hashes}; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; object-src 'none'; base-uri 'none'; "
        "form-action 'self'; frame-ancestors 'self'; "
        "connect-src 'self' https://api.github.com"
    )


@require_GET
def robos(request):
    pasta = diretorio_da_fila()
    if pasta is None:
        # Mesma lei do painel ausente: a página DIZ que a fila não veio (500),
        # nunca finge fila vazia — "não há trabalho" seria mentira.
        resposta = render(
            request, "admin/caixa_robos.html", {"fila_ausente": True}, status=500
        )
        resposta["Content-Security-Policy"] = _csp(resposta.content)
        return resposta

    estados = _ler_json(pasta / "estados.json") or {}
    relogio = andamento(pasta)
    ultima_mexida = relogio["ultima_mexida"]

    colunas = []
    for grupo in COLUNAS:
        cartoes = sorted(
            (
                {
                    "id": tid,
                    **dados,
                    "onde": onde_isso_mexe(dados.get("toca")),
                    "quando": ultima_mexida.get(tid),
                }
                for tid, dados in estados.items()
                if e_deste_grupo(dados, grupo)
            ),
            key=lambda c: c["id"],
            # A história vem do fim para o começo: quem abre as concluídas quer
            # ver o que acabou de acontecer, não a TAR-001 de 29/08. Os grupos
            # abertos (o que ainda pede trabalho) seguem na ordem de chegada.
            reverse=grupo["recolhida"],
        )
        colunas.append({**grupo, "cartoes": cartoes})

    # Quantas param a vida dele. Sai daqui, e não de uma contagem no template,
    # porque é a MESMA lista que o primeiro grupo já montou: contar de novo lá
    # seria a segunda definição de "o que espera por você" dentro da própria
    # página, e as duas divergiriam no dia em que o casamento mudasse.
    esperando_voce = next(
        (len(c["cartoes"]) for c in colunas if c.get("espera") == "mantenedor"), 0
    )

    # A régua (`ci/tempos_esperados.json`): {"medido_em", "esperas": {chave:
    # {rotulo, p50_s, p90_s, amostra}}}. A regra de honestidade dela viaja para
    # a tela: amostra pequena se declara, nunca se esconde.
    regua = _ler_json(pasta / "regua.json") or {}
    linhas_da_regua = [
        {
            "chave": chave,
            "rotulo": medida.get("rotulo") or chave,
            "p50": em_portugues(medida.get("p50_s")),
            "p90": em_portugues(medida.get("p90_s")),
            "amostra": medida.get("amostra"),
            "pouca_amostra": (medida.get("amostra") or 0) < 20,
        }
        for chave, medida in sorted((regua.get("esperas") or {}).items())
        if isinstance(medida, dict)
    ]

    resposta = render(
        request,
        "admin/caixa_robos.html",
        {
            "colunas": colunas,
            "esperando_voce": esperando_voce,
            "total": len(estados),
            "andamento": relogio,
            "esperas": _resumo_de_esperas(pasta),
            "regua": linhas_da_regua,
            "regua_medida_em": regua.get("medido_em"),
        },
    )
    resposta["Content-Security-Policy"] = _csp(resposta.content)
    return resposta
