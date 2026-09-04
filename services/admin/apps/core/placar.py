"""`/admin/placar/` — o andar zero do painel de gestão do negócio.

Nasceu em 03/09/2026 de manhã medindo o total de alunos; à noite do mesmo dia
o mantenedor reformulou a Meta Crucialmente Importante nº 1 (registro
`20260903-036`), e esta tela passou a responder DUAS perguntas com o MESMO
número de fichas:

- **a barra do mês:** quantas pessoas viraram alunas neste mês (zera todo dia
  1), com a meta do mês ao lado;
- **a meta grande, por cima:** de 0 para 500 pessoas somadas de 03/09 a
  15/12/2026, no formato das 4 Disciplinas da Execução (*de X para Y até
  quando*), com a linha reta dizendo se estamos ganhando ou perdendo.

## As leis desta tela, e de onde vêm

1. **Número sem cartão não aparece** (plano, §2). O cartão de uma métrica é um
   arquivo em `painel/cartoes/<nome>.json` que diz o que o número é, de onde
   vem, quem tem o direito de declará-lo e qual métrica o segura (o "par").
   Cartão ausente ou inválido ⇒ a página abre, DIZ o que faltou, e não mostra
   o número. Guarda: `tests/test_placar.py`.
2. **X é medido, nunca digitado**, e vem da célula `alunos`, por HTTP e em
   tempo real (decisão do mantenedor de 25/08/2026). A data que conta é
   `virou_aluno_em` (a liberação pela fila, ou a confirmação do pagamento),
   campo do Rito de Contrato de 03/09/2026 (PR #933). Nunca `comprou_em`, que
   é o que a pessoa digita ao pedir entrada.
3. **"Não sei" nunca vira zero.** A `alunos` fora do ar ⇒ *"não consigo
   contar"*. A lista chegou mas ainda sem o campo (a célula ainda não subiu o
   PR do rito) ⇒ *"a lista ainda não traz a data"*. Ficha sem data ⇒ contada à
   parte e dita na tela, nunca escondida (`RETROSPECTIVA-FASE-D.md`, padrão 1).
4. **Reembolsada não é compra.** A compra foi desfeita
   (`DECISAO-reembolso-tira-o-acesso.md`); a tela diz quantas foram.
5. **Quem ficou antes da partida não entra.** A turma liberada em lote pela
   lista de WhatsApp em 02/09/2026 é venda de outros meses (palavras do
   mantenedor: neste mês ainda não houve venda). A partida é 03/09.

## O que mora no cartão e o que NÃO mora

O **alvo** (Y), a **data** e a **partida** moram no cartão, porque são
parâmetros da régua, versionados por PR. O FATO de que o mantenedor decidiu
mora no livro (`painel/registros/`, tipo `decisao`). A meta do mês
(`alvo_do_mes`) é opcional: nula, a tela deriva a fatia da linha reta que cai
no mês; ele fixa um número quando quiser.

## O veredito, sem índice

Ganhando ou perdendo é a comparação de X com o **esperado de hoje** numa linha
reta da partida ao alvo. Não há ponderação, não há nota de 0 a 100: o plano
proíbe número composto no andar zero (§2), e o mantenedor marcou "sem
preferência" quando os documentos do Scale OS propuseram a nota; ficou a
regra da casa (registro `20260903-036`).
"""

from __future__ import annotations

import calendar
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from .clients import AlunosClient
from .painel import CANDIDATOS

#: A subpasta do painel onde moram os cartões. Viaja para a imagem junto com o
#: resto de `painel/` (o `deploy-celula` copia a pasta inteira).
PASTA_DOS_CARTOES = "cartoes"

#: A Meta Crucialmente Importante nº 1 (o ciclo), a barra do mês, o par que
#: segura as duas, e o total de alunos que desceu ao andar 1.
CARTAO_DA_META = "compras-no-ciclo"
CARTAO_DO_MES = "compras-no-mes"
CARTAO_DO_PAR = "alunos-ativos-30d"
CARTAO_DO_TOTAL = "alunos-na-plataforma"
#: A restrição desta semana (degrau 1 do plano; regra em `restricao.py`).
CARTAO_DA_RESTRICAO = "restricao-da-semana"
#: A direção da semana (degrau 2; regra em `direcao.py`): as duas medidas que
#: a casa move na semana e que antecipam a meta.
CARTAO_DOS_PEDIDOS = "pedidos-de-entrada-por-semana"
CARTAO_DAS_48H = "liberacoes-em-48h"

#: Os quatro tipos de número do plano (§2). Não existe tipo "composto": um
#: número composto é reconhecido pelo campo `componentes`, e nunca desce ao
#: andar zero.
TIPOS = ("resultado", "direcao", "par", "confianca")

#: `direcao` (Scale OS 1.2 §33, traduzido): custo subir é ruim, compras subir
#: é bom. Sem o campo a tela não sabe pintar a seta. Opcional por enquanto.
DIRECOES = ("subir", "descer", "faixa")

OBRIGATORIOS = (
    "nome",
    "tipo",
    "andar",
    "pergunta",
    "definicao",
    "formula",
    "autoridade",
    "dono",
    "frequencia",
    "versao",
    "desde",
)

#: Os status de gestão que contam como "comprou". `reembolsada` fica de fora:
#: a compra foi desfeita. Lista de PERMISSÃO, como a `STATUS_QUE_VALEM` da
#: `alunos`: status novo nasce fora dela e alguém decide.
STATUS_QUE_COMPRARAM = ("ativa", "suspensa", "encerrada")

#: O status que a `alunos` chama de aluno hoje (o mesmo do mapa da jornada).
STATUS_QUE_E_ALUNO = "ativa"

#: O campo do Rito de Contrato de 03/09/2026 (PR #933).
CAMPO_DA_DATA = "virou_aluno_em"

FUSO = ZoneInfo("America/Sao_Paulo")

#: Os blocos da capa, na ordem do plano (§3), e o TETO: a capa se recusa a
#: crescer. Realidade nova entra como cartão, não como bloco. O guarda mede o
#: template (`tests/test_capa.py`): cada `titulo-de-bloco` é um bloco.
BLOCOS_DA_CAPA = (
    "a barra do mês e a meta grande",
    "as estrelas-guia",
    "a direção da semana",
    "a restrição desta semana",
    "o placar de doze",
    "o par que segura a meta",
    "o que mudou (degrau 6)",
    "o laboratório (degrau 12)",
    "precisa de você e os robôs (atalhos)",
)
TETO_DE_BLOCOS = 9


def diretorio_dos_cartoes() -> Path | None:
    """`painel/cartoes/`, embutida ou de checkout; `None` se não veio."""
    for candidato in CANDIDATOS:
        pasta = candidato / PASTA_DOS_CARTOES
        if pasta.is_dir():
            return pasta
    return None


def validar(cartao: object) -> list[str]:
    """Os defeitos de um cartão, em português. Lista vazia = cartão válido.

    Cada regra abaixo é uma linha do plano (§2), e a mensagem diz o conserto:
    quem vai lê-la é o robô que escreveu o cartão errado.
    """
    if not isinstance(cartao, dict):
        return ["o cartão não é um objeto JSON"]
    problemas: list[str] = []
    for campo in OBRIGATORIOS:
        valor = cartao.get(campo)
        if valor is None or (isinstance(valor, str) and not valor.strip()):
            problemas.append(f"campo `{campo}` ausente ou vazio")
    if cartao.get("tipo") not in TIPOS:
        problemas.append(f"`tipo` deve ser um de {', '.join(TIPOS)}")
    andar = cartao.get("andar")
    if not isinstance(andar, int) or isinstance(andar, bool) or not 0 <= andar <= 4:
        problemas.append("`andar` é um inteiro de 0 a 4, sem aspas")
    if cartao.get("componentes") and andar == 0:
        problemas.append(
            "número composto (tem `componentes`) nunca desce ao andar 0: "
            "o placar mostra a coisa, não uma nota sobre a coisa"
        )
    if andar == 0 and cartao.get("tipo") == "resultado" and not cartao.get("acao"):
        # Scale OS 1.1 §2 e §132, virado regra: "se este número mudar, alguém
        # faz algo diferente?" Um número no andar zero sem `acao` é um número
        # que só se olha, e o andar zero é o que pede gesto.
        problemas.append(
            "número de resultado no andar 0 exige `acao`: o que fazer quando "
            "ele estiver abaixo do esperado (o andar zero pede gesto, não olhar)"
        )
    if cartao.get("tipo") != "confianca" and not cartao.get("par"):
        problemas.append(
            "toda métrica que pode ser forçada tem um `par` que a segura; "
            "só o tipo `confianca` dispensa"
        )
    if "fonte" not in cartao:
        problemas.append("campo `fonte` ausente (use null se a fonte não existe)")
    elif cartao.get("fonte") is None and not cartao.get("sem_fonte_porque"):
        problemas.append(
            "`fonte` nula exige `sem_fonte_porque`: um número sem fonte precisa "
            "dizer em voz alta por que ainda não existe"
        )
    direcao = cartao.get("direcao")
    if direcao is not None and direcao not in DIRECOES:
        problemas.append(f"`direcao` deve ser um de {', '.join(DIRECOES)}")
    versao = cartao.get("versao")
    if not isinstance(versao, int) or isinstance(versao, bool) or versao < 1:
        problemas.append("`versao` é um inteiro a partir de 1, sem aspas")
    alvo_do_mes = cartao.get("alvo_do_mes")
    if alvo_do_mes is not None and (
        not isinstance(alvo_do_mes, int)
        or isinstance(alvo_do_mes, bool)
        or alvo_do_mes < 0
    ):
        problemas.append("`alvo_do_mes` é um inteiro sem aspas, ou null")
    problemas.extend(_validar_a_meta(cartao))
    return problemas


def _validar_a_meta(cartao: dict) -> list[str]:
    """Alvo, data e partida andam juntos: ou os quatro existem, ou nenhum."""
    campos = ("alvo", "ate", "partida", "partida_em")
    presentes = [c for c in campos if cartao.get(c) is not None]
    if not presentes:
        return []
    if len(presentes) != len(campos):
        faltam = [c for c in campos if c not in presentes]
        return [
            "uma meta é `alvo` + `ate` + `partida` + `partida_em`, os quatro "
            f"juntos; faltou: {', '.join(faltam)}"
        ]
    problemas: list[str] = []
    for c in ("alvo", "partida"):
        v = cartao[c]
        if not isinstance(v, int) or isinstance(v, bool) or v < 0:
            problemas.append(f"`{c}` é um inteiro sem aspas")
    for c in ("ate", "partida_em"):
        if _data(cartao[c]) is None:
            problemas.append(f"`{c}` é uma data AAAA-MM-DD")
    if not problemas and _data(cartao["ate"]) <= _data(cartao["partida_em"]):
        problemas.append("`ate` precisa vir depois de `partida_em`")
    return problemas


def _data(texto: object) -> dt.date | None:
    try:
        return dt.date.fromisoformat(str(texto))
    except (TypeError, ValueError):
        return None


def ler_cartao(nome: str, pasta: Path | None = None) -> tuple[dict | None, list[str]]:
    """`(cartao, problemas)`. Cartão só volta se for válido; senão, `None` + o porquê."""
    pasta = pasta if pasta is not None else diretorio_dos_cartoes()
    if pasta is None:
        return None, ["a pasta `painel/cartoes/` não veio nesta versão do site"]
    caminho = pasta / f"{nome}.json"
    if not caminho.is_file():
        return None, [f"o cartão `{nome}` não existe em `painel/cartoes/`"]
    try:
        cartao = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError) as erro:
        return None, [f"o cartão `{nome}` não é JSON válido: {erro}"]
    problemas = validar(cartao)
    if problemas:
        return None, [f"cartão `{nome}`: {p}" for p in problemas]
    if cartao.get("nome") != nome:
        return None, [f"cartão `{nome}`: o campo `nome` diz `{cartao.get('nome')}`"]
    return cartao, []


# ------------------------------------------------------------------ a contagem


def dia_em_sao_paulo(texto: object) -> dt.date | None:
    """O DIA de um instante ISO com fuso, em America/Sao_Paulo (`armadilhas/099`).

    `None` para nulo, vazio, ilegível ou sem fuso: a tela conta essas fichas à
    parte. Instante sem fuso não diz em que dia caiu, e isso não se adivinha.
    """
    if not texto:
        return None
    try:
        instante = dt.datetime.fromisoformat(str(texto).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if instante.tzinfo is None:
        return None
    return instante.astimezone(FUSO).date()


def contar_compras(
    alunos: list[dict] | None, partida_em: dt.date, hoje: dt.date
) -> dict:
    """As fichas que viraram alunas, contadas de UMA lista: o ciclo, o mês,
    as sem data, as reembolsadas, e o total de alunos de hoje.

    `ciclo`/`mes` são `None` quando não dá para contar: lista ausente
    (`alunos is None`) ou lista sem o campo (`campo_ausente`, a célula ainda
    não subiu o PR do rito). Zero só quando contou e deu zero.
    """
    vazio = {
        "ciclo": None,
        "mes": None,
        "sem_data": None,
        "reembolsadas": None,
        "total_de_alunos": None,
        "campo_ausente": False,
    }
    if alunos is None:
        return vazio
    total_de_alunos = sum(1 for a in alunos if a.get("status") == STATUS_QUE_E_ALUNO)
    if alunos and not any(CAMPO_DA_DATA in a for a in alunos):
        return {**vazio, "total_de_alunos": total_de_alunos, "campo_ausente": True}
    inicio_do_mes = hoje.replace(day=1)
    ciclo = mes = sem_data = reembolsadas = 0
    for a in alunos:
        dia = dia_em_sao_paulo(a.get(CAMPO_DA_DATA))
        if a.get("status") == "reembolsada":
            if dia is not None and partida_em <= dia <= hoje:
                reembolsadas += 1
            continue
        if a.get("status") not in STATUS_QUE_COMPRARAM:
            continue
        if dia is None:
            sem_data += 1
            continue
        if not partida_em <= dia <= hoje:
            continue
        ciclo += 1
        if dia >= inicio_do_mes:
            mes += 1
    return {
        "ciclo": ciclo,
        "mes": mes,
        "sem_data": sem_data,
        "reembolsadas": reembolsadas,
        "total_de_alunos": total_de_alunos,
        "campo_ausente": False,
    }


# ------------------------------------------------------------------- a conta


def esperado_em(cartao: dict, dia: dt.date) -> int:
    """Onde a linha reta da partida ao alvo passa no `dia` (antes da partida
    vale a partida; depois do fim vale o alvo)."""
    alvo = int(cartao["alvo"])
    partida = int(cartao["partida"])
    ate = _data(cartao["ate"])
    partida_em = _data(cartao["partida_em"])
    total = (ate - partida_em).days
    decorridos = min(max((dia - partida_em).days, 0), total)
    return partida + round((alvo - partida) * decorridos / total) if total > 0 else alvo


def calcular_placar(cartao: dict, x: int | None, hoje: dt.date) -> dict:
    """A conta do andar zero, pura, sem rede e sem relógio próprio.

    Devolve um dicionário com `veredito` em uma destas palavras:
    `nao-consigo-contar` · `sem-alvo` · `cumprida` · `vencida` · `ganhando` ·
    `perdendo`. A tela traduz cada uma para uma frase; o teste confere a palavra.
    """
    base = {
        "x": x,
        "alvo": cartao.get("alvo"),
        "ate": cartao.get("ate"),
        "partida": cartao.get("partida"),
        "partida_em": cartao.get("partida_em"),
        "esperado_hoje": None,
        "distancia": None,
        "dias_restantes": None,
        "ritmo_por_semana": None,
    }
    if x is None:
        return {**base, "veredito": "nao-consigo-contar"}
    if cartao.get("alvo") is None:
        return {**base, "veredito": "sem-alvo"}

    alvo = int(cartao["alvo"])
    ate = _data(cartao["ate"])
    esperado = esperado_em(cartao, hoje)
    dias_restantes = max((ate - hoje).days, 0)
    faltam = alvo - x
    semanas = dias_restantes / 7
    # Quantas pessoas por semana faltam para chegar lá: a única conta que vira
    # gesto na segunda-feira (a "aposta da semana" do plano, §4).
    ritmo = round(faltam / semanas, 1) if faltam > 0 and semanas > 0 else None

    if x >= alvo:
        veredito = "cumprida"
    elif hoje > ate:
        veredito = "vencida"
    elif x >= esperado:
        veredito = "ganhando"
    else:
        veredito = "perdendo"
    return {
        **base,
        "esperado_hoje": esperado,
        "distancia": faltam,
        "dias_restantes": dias_restantes,
        "ritmo_por_semana": ritmo,
        "veredito": veredito,
    }


def calcular_o_mes(
    cartao_do_mes: dict, meta: dict | None, x: int | None, hoje: dt.date
) -> dict:
    """A barra do mês: quantas viraram alunas neste mês, contra a meta do mês.

    A meta do mês é `alvo_do_mes` do cartão; nula, é a fatia da linha reta do
    ciclo que cai neste mês (o esperado no último dia do mês menos o esperado
    na véspera do dia 1). Sem ciclo com alvo, só a contagem, sem veredito.
    """
    ultimo_dia = hoje.replace(day=calendar.monthrange(hoje.year, hoje.month)[1])
    inicio = hoje.replace(day=1)
    alvo = cartao_do_mes.get("alvo_do_mes")
    derivada = False
    if alvo is None and meta is not None and meta.get("alvo") is not None:
        vespera = inicio - dt.timedelta(days=1)
        alvo = esperado_em(meta, ultimo_dia) - esperado_em(meta, vespera)
        derivada = True
    resultado = {
        "x": x,
        "alvo": alvo,
        "alvo_derivado": derivada,
        "mes": hoje.strftime("%m/%Y"),
        "ultimo_dia": ultimo_dia,
        "dias_restantes": (ultimo_dia - hoje).days,
        "esperado_hoje": None,
        "veredito": None,
    }
    if x is None:
        resultado["veredito"] = "nao-consigo-contar"
    elif alvo is None:
        resultado["veredito"] = "sem-alvo"
    elif x >= alvo:
        resultado["veredito"] = "cumprida"
    else:
        # A linha reta DENTRO do mês: esperado hoje = alvo × dias passados / dias do mês.
        dias_do_mes = (ultimo_dia - inicio).days + 1
        passados = (hoje - inicio).days + 1
        esperado = round(alvo * passados / dias_do_mes)
        resultado["esperado_hoje"] = esperado
        resultado["veredito"] = "ganhando" if x >= esperado else "perdendo"
    return resultado


@require_GET
def placar(request):
    """O andar zero. Fail-OPEN na rede (a página abre), fail-CLOSED no cartão
    (o número não aparece sem ele)."""
    return render(
        request,
        "admin/placar.html",
        {"admin": request.admin, **montar_o_placar(timezone.localdate())},
    )


def montar_o_placar(hoje: dt.date) -> dict:
    """Tudo que o placar mostra, calculado UMA vez por requisição.

    Existe como função porque DUAS telas leem o mesmo placar: `/admin/placar/`
    e o modo reunião (`/admin/reuniao/`, degrau 3). Duas montagens à mão
    divergiriam no primeiro bloco novo, e o mantenedor leria a que abrisse
    primeiro sem saber que a outra discorda.
    """
    pasta = diretorio_dos_cartoes()
    meta, recusas = ler_cartao(CARTAO_DA_META, pasta)
    mes, recusas_do_mes = ler_cartao(CARTAO_DO_MES, pasta)
    par, recusas_do_par = ler_cartao(CARTAO_DO_PAR, pasta)
    total, _recusas_do_total = ler_cartao(CARTAO_DO_TOTAL, pasta)

    # Import tardio de propósito: `restricao` e `direcao` importam deste módulo
    # (a leitura de fuso e a lista de status), e o ciclo se fecha aqui, na view.
    from . import direcao as dir_
    from .restricao import escolher_restricao, medir_liberacao

    cartao_da_restricao, recusas_da_restricao = ler_cartao(CARTAO_DA_RESTRICAO, pasta)
    cartao_pedidos, recusas_pedidos = ler_cartao(CARTAO_DOS_PEDIDOS, pasta)
    cartao_48h, recusas_48h = ler_cartao(CARTAO_DAS_48H, pasta)

    from . import doze as doze_

    contagem = None
    resultado = None
    barra = None
    restricao = None
    direcao = None
    compromissos = None
    os_doze = None
    estrelas = None
    confianca_dos_doze = None
    latencias = None
    if meta is not None:
        from . import latencias as lat_

        partida_em = _data(meta.get("partida_em")) or hoje
        cliente = AlunosClient()
        # UMA leitura de cada porta por requisição: a contagem, a restrição, a
        # direção e os doze olham as MESMAS listas, senão discordariam entre si
        # por um segundo de diferença.
        alunos = cliente.alunos()
        aguardando = cliente.fila("aguardando")
        recusados = cliente.fila("recusada")
        registros = dir_.ler_registros()
        contagem = contar_compras(alunos, partida_em, hoje)
        resultado = calcular_placar(meta, contagem["ciclo"], hoje)
        if mes is not None:
            barra = calcular_o_mes(mes, meta, contagem["mes"], hoje)
        medida = medir_liberacao(aguardando, recusados, alunos, hoje)
        if cartao_da_restricao is not None:
            restricao = escolher_restricao(medida, cartao_da_restricao)
        if cartao_pedidos is not None and cartao_48h is not None:
            direcao = dir_.calcular_direcao(
                cartao_pedidos,
                cartao_48h,
                meta,
                dir_.medir_pedidos(aguardando, recusados, alunos, hoje),
                dir_.medir_liberacoes_em_48h(aguardando, alunos, hoje),
                hoje,
            )
            compromissos = dir_.compromissos(registros, hoje)
        os_doze = doze_.medir_os_doze(
            barra=barra,
            por_mes=doze_.compras_por_mes(alunos, partida_em),
            liberacao=medida,
            registros=registros,
            partida_em=partida_em,
            hoje=hoje,
            pasta=pasta,
        )
        confianca_dos_doze = doze_.confianca(os_doze)
        estrelas = [d for d in os_doze if d["nome"] in doze_.ESTRELAS]
        latencias = lat_.medir_as_latencias(registros, lat_.ler_a_fila(), hoje)

    return {
        "latencias": latencias,
        "doze": os_doze,
        "estrelas": estrelas,
        "confianca_dos_doze": confianca_dos_doze,
        "hoje": hoje,
        "meta": meta,
        "recusas": recusas,
        "mes": mes,
        "recusas_do_mes": recusas_do_mes,
        "par": par,
        "recusas_do_par": recusas_do_par,
        "total": total,
        "contagem": contagem,
        "placar": resultado,
        "barra": barra,
        "cartao_da_restricao": cartao_da_restricao,
        "recusas_da_restricao": recusas_da_restricao,
        "restricao": restricao,
        "cartao_pedidos": cartao_pedidos,
        "cartao_48h": cartao_48h,
        "recusas_da_direcao": recusas_pedidos + recusas_48h,
        "direcao": direcao,
        "compromissos": compromissos,
    }
