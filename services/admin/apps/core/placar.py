"""`/admin/placar/` — o andar zero do painel de gestão do negócio.

Nasceu em 03/09/2026 de manhã medindo o total de alunos; à noite do mesmo dia
o mantenedor reformulou a Meta Crucialmente Importante nº 1 (registro
`20260903-036`), e esta tela passou a responder DUAS perguntas com o MESMO
número de fichas:

- **a barra do mês:** quantas pessoas viraram alunas neste mês (zera todo dia
  1), com a meta do mês ao lado;
- **a meta grande, por cima:** as pessoas somadas de 03/09 a 15/12/2026, no
  formato das 4 Disciplinas da Execução (*de X para Y até quando*), com a régua
  do ciclo dizendo se estamos ganhando ou perdendo. O alvo NÃO é repetido neste
  texto: ele mora no cartão e já mudou duas vezes em 04/09/2026 (de 500 para
  1000). Número copiado para dentro de um docstring é a segunda verdade que
  ninguém lembra de corrigir.

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
(`alvo_do_mes`) é opcional: nula, a tela deriva a fatia da régua do ciclo que
cai no mês; ele fixa um número quando quiser.

Desde 04/09/2026 essa régua tem uma peça a mais, `semanas`: a CURVA do ciclo
(`DECISAO-o-calendario-do-ciclo.md`). Ela reparte a meta semana a semana, quase
zero no começo e pesada no fim, em vez de em partes iguais. O cartão que não
declara `semanas` continua medido em linha reta, como antes.

## O veredito, sem índice

Ganhando ou perdendo é a comparação de X com o **esperado de hoje**, que sai de
`esperado_em`: a curva de `semanas` quando o cartão a declara, e a linha reta da
partida ao alvo quando não. Não há ponderação, não há nota de 0 a 100: o plano
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

from .clients import AlunosClient, CatalogoClient
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
#: A direção da semana (degrau 2; regra em `direcao.py`): as duas medidas que a
#: casa move na semana. As duas olham a SALA DE ESPERA, que é a venda feita
#: fora do site: quem está nela já comprou e aguarda confirmação (correção do
#: mantenedor em 05/09/2026). O nome do primeiro arquivo é anterior a essa
#: correção e continua sendo a chave da foto do livro; o cartão explica a dívida.
CARTAO_DOS_PEDIDOS = "pedidos-de-entrada-por-semana"
CARTAO_DAS_48H = "liberacoes-em-48h"

#: O caminho da venda, ao lado das duas acesas e sem número nenhum: quem chega
#: na página e quem compra pelo próprio site. Nascem desenhados por decisão do
#: mantenedor de 05/09/2026, e ficam apagados enquanto o checkout estiver
#: congelado pela decisão dele de 22/08/2026. Aparecer apagado é o desenho, e
#: não uma falta: é como as estrelas-guia e os oito do placar de doze já nascem.
CARTOES_DO_CAMINHO_DA_VENDA = (
    "visitas-na-pagina-de-venda-por-semana",
    "compras-pelo-checkout-por-semana",
)

#: Os quatro tipos de número do plano (§2). Não existe tipo "composto": um
#: número composto é reconhecido pelo campo `componentes`, e nunca desce ao
#: andar zero.
TIPOS = ("resultado", "direcao", "par", "confianca")

#: `direcao` (Scale OS 1.2 §33, traduzido): custo subir é ruim, compras subir
#: é bom. Sem o campo a tela não sabe pintar a seta. Opcional por enquanto.
DIRECOES = ("subir", "descer", "faixa")

#: Por onde um número se abre (degrau 6, plano §4.2). O cartão declara em
#: `dimensoes` as que fazem sentido para ele; a tela que abre por dimensão é
#: dos degraus 9 e 10, e o campo entra antes para o cartão já dizer a verdade.
DIMENSOES = ("site", "turma", "mes-de-entrada", "canal")

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
    frescor = cartao.get("frescor_maximo")
    if frescor is not None and (
        not isinstance(frescor, int) or isinstance(frescor, bool) or frescor < 1
    ):
        problemas.append(
            "`frescor_maximo` é um inteiro de dias a partir de 1, ou ausente: "
            "passa disso e o número é dito como velho"
        )
    dimensoes = cartao.get("dimensoes")
    if dimensoes is not None and (
        not isinstance(dimensoes, list) or any(d not in DIMENSOES for d in dimensoes)
    ):
        problemas.append(
            f"`dimensoes` é uma lista entre {', '.join(DIMENSOES)}, ou ausente"
        )
    ruido = cartao.get("ruido")
    if ruido is not None and (
        isinstance(ruido, bool) or not isinstance(ruido, (int, float)) or ruido < 0
    ):
        problemas.append(
            "`ruido` é um número na unidade do cartão, zero ou maior, ou ausente: "
            "diferença até ele não é movimento"
        )
    problemas.extend(_validar_a_meta(cartao))
    problemas.extend(_validar_as_semanas(cartao))
    return problemas


def _validar_as_semanas(cartao: dict) -> list[str]:
    """A curva do ciclo: 14 faixas de datas, e a soma delas É a meta grande.

    A regra que importa é a última: **a soma dos alvos semanais tem de dar
    exatamente `alvo` menos `partida`**. Sem ela, a curva e a meta grande
    seriam duas verdades sobre o mesmo número, e no dia em que discordassem
    ninguém saberia qual está certa — o placar diria uma coisa e o calendário
    outra, os dois com ar de certeza. É a lei anti-duplicação do `CLAUDE.md`
    aplicada dentro de um arquivo só.

    As outras regras são o mínimo para a curva ser um calendário de verdade:
    faixas em ordem, sem sobreposição, cada uma com começo antes do fim.
    """
    semanas = cartao.get("semanas")
    if semanas is None:
        return []
    if not isinstance(semanas, list) or not semanas:
        return ["`semanas` é uma lista de faixas com pelo menos uma, ou ausente"]
    problemas: list[str] = []
    for i, s in enumerate(semanas):
        onde = f"semanas[{i}]"
        if not isinstance(s, dict):
            problemas.append(f"{onde} não é um objeto")
            continue
        for campo in ("n", "alvo"):
            v = s.get(campo)
            if not isinstance(v, int) or isinstance(v, bool) or v < 0:
                problemas.append(
                    f"{onde}: `{campo}` é um inteiro sem aspas, zero ou maior"
                )
        for campo in ("de", "ate"):
            if _data(s.get(campo)) is None:
                problemas.append(f"{onde}: `{campo}` é uma data AAAA-MM-DD")
    if problemas:
        return problemas

    for i, s in enumerate(semanas):
        de, ate = _data(s["de"]), _data(s["ate"])
        if ate < de:
            problemas.append(f"semanas[{i}]: `ate` vem antes de `de`")
        if i and _data(semanas[i - 1]["ate"]) >= de:
            problemas.append(
                f"semanas[{i}] começa em {s['de']}, antes de a anterior terminar: "
                "as faixas são de datas e não podem se sobrepor nem sair de ordem"
            )
    if problemas:
        return problemas

    if cartao.get("alvo") is None or cartao.get("partida") is None:
        return ["`semanas` exige a meta completa no cartão (`alvo` e `partida`)"]
    soma = sum(int(s["alvo"]) for s in semanas)
    esperado = int(cartao["alvo"]) - int(cartao["partida"])
    if soma != esperado:
        problemas.append(
            f"a soma das semanas é {soma} e a meta pede {esperado} "
            f"(`alvo` {cartao['alvo']} menos `partida` {cartao['partida']}): "
            "a curva não pode discordar da meta grande. Ajuste as semanas, ou "
            "o alvo, mas nunca deixe os dois números discordarem"
        )
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


def semanas_do_ciclo(cartao: dict) -> list[dict]:
    """As faixas de `semanas`, cada uma com o acumulado até o fim dela.

    Lista vazia quando o cartão não declara a curva, e aí `esperado_em` volta
    para a linha reta. A conta do acumulado mora AQUI e em nenhum outro lugar:
    a tela do calendário e a régua do placar leem a mesma função, senão as duas
    divergiriam no primeiro ajuste de meta.
    """
    cru = cartao.get("semanas")
    if not isinstance(cru, list) or not cru:
        return []
    faixas, acumulado = [], int(cartao.get("partida", 0))
    for s in cru:
        acumulado += int(s["alvo"])
        faixas.append(
            {
                "n": int(s["n"]),
                "de": _data(s["de"]),
                "ate": _data(s["ate"]),
                "alvo": int(s["alvo"]),
                "acumulado": acumulado,
                "rotulo": s.get("rotulo"),
            }
        )
    return faixas


def esperado_em(cartao: dict, dia: dt.date) -> int:
    """Quanto a meta espera ter no `dia`.

    **Com `semanas` no cartão, quem manda é a CURVA** (decisão do mantenedor de
    04/09/2026): dentro de uma semana o esperado sobe proporcionalmente aos dias
    já vividos dela; no buraco entre duas semanas, fica no acumulado da última
    que fechou; antes da primeira vale a partida; depois da última, o alvo.

    O passeio dentro da semana não é enfeite: sem ele o veredito
    ganhando/perdendo daria um pulo toda segunda e ficaria congelado o resto da
    semana, e a tela diria "ganhando" na terça de uma semana que ia terminar
    perdida.

    **Sem `semanas`, é a linha reta de sempre** — a regra antiga, intacta, para
    todo cartão com meta que não declara curva.
    """
    alvo = int(cartao["alvo"])
    partida = int(cartao["partida"])

    faixas = semanas_do_ciclo(cartao)
    if faixas:
        if dia < faixas[0]["de"]:
            return partida
        if dia > faixas[-1]["ate"]:
            return alvo
        anterior = partida
        for faixa in faixas:
            if dia > faixa["ate"]:
                anterior = faixa["acumulado"]
                continue
            if dia < faixa["de"]:
                # O buraco entre duas semanas (o fim de semana): o esperado é o
                # que a semana anterior fechou, nunca uma fatia da próxima.
                return anterior
            dias = (faixa["ate"] - faixa["de"]).days + 1
            vividos = (dia - faixa["de"]).days + 1
            return anterior + round(faixa["alvo"] * vividos / dias)
        return alvo

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
        {
            "admin": request.admin,
            **montar_o_placar(timezone.localdate(), site_de(request)),
        },
    )


def site_de(request) -> str | None:
    """O id do site desta requisição, pelo HOST — `None` se não deu para saber.

    [INV-P11] e o mesmo caminho de `menu.py` e `avisos.py`: o site sai do
    domínio pelo qual a requisição chegou, nunca de um id guardado aqui. Quem
    precisa dele é a memória (a `metricas` conta por site, Lei 9); o resto do
    placar não precisa, e por isso a falha aqui não estraga a tela — vira a
    frase "não sei de qual site perguntar" numa linha só.
    """
    site = CatalogoClient().site_por_host(request.get_host().split(":")[0].lower())
    return (site or {}).get("id")


def montar_o_placar(hoje: dt.date, site_id: str | None = None) -> dict:
    """Tudo que o placar mostra, calculado UMA vez por requisição.

    Existe como função porque DUAS telas leem o mesmo placar: `/admin/placar/`
    e o modo reunião (`/admin/reuniao/`, degrau 3). Duas montagens à mão
    divergiriam no primeiro bloco novo, e o mantenedor leria a que abrisse
    primeiro sem saber que a outra discorda.

    `site_id` é opcional e não tem default de mentira: sem ele a linha da
    memória diz que não soube de qual site perguntar, e todo o resto da tela
    continua igual.
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
    caminho_da_venda = []
    recusas_do_caminho_da_venda = []
    for nome in CARTOES_DO_CAMINHO_DA_VENDA:
        cartao, recusado = ler_cartao(nome, pasta)
        if cartao is None:
            recusas_do_caminho_da_venda.extend(recusado)
        else:
            caminho_da_venda.append(cartao)

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
    mudancas = None
    cartoes_de_latencia = {
        nome: ler_cartao(nome, pasta)[0]
        for nome in (
            "latencia-de-decisao",
            "latencia-de-execucao",
            "latencia-de-aprendizado",
        )
    }
    # O import é tardio pelo mesmo motivo dos de cima (o ciclo se fecha na view),
    # mas a LEITURA sai de dentro do `if meta`: "o que está sendo feito por este
    # número" não depende de o cartão da meta existir.
    from . import elo as elo_
    from . import latencias as lat_

    a_fila = lat_.ler_a_fila()
    trabalho = elo_.trabalho_por_cartao(a_fila)
    declaracao = elo_.resumo_da_declaracao(a_fila)

    if meta is not None:
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
        latencias = lat_.medir_as_latencias(registros, a_fila, hoje)

        from . import mudancas as mud_

        # Depois de tudo medido: a foto compara o que a tela MOSTRA.
        mudancas = mud_.o_que_mudou(
            {
                "contagem": contagem,
                "direcao": direcao,
                "doze": os_doze,
                "latencias": latencias,
                "meta": meta,
                "total": total,
                "cartao_pedidos": cartao_pedidos,
                "cartao_48h": cartao_48h,
                "cartoes_de_latencia": cartoes_de_latencia,
            },
            registros,
            hoje,
        )

    # FORA do `if meta`: a confiança nos dados não depende de haver cartão. Se
    # o cartão da meta faltar, a tela não mostra número nenhum — mas continua
    # podendo dizer se a memória da escola está recebendo fatos, que é
    # justamente o tipo de coisa que ninguém descobre olhando um número.
    from . import medicao as med_

    return {
        "medicao": med_.a_memoria(site_id, timezone.now()),
        "mudancas": mudancas,
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
        "caminho_da_venda": caminho_da_venda,
        "recusas_do_caminho_da_venda": recusas_do_caminho_da_venda,
        "direcao": direcao,
        "compromissos": compromissos,
        "trabalho": trabalho,
        "declaracao": declaracao,
    }
