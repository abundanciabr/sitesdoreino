"""`/admin/placar/` — o andar zero do painel de gestão do negócio (03/09/2026).

O plano é `docs/decisoes/PLANO-PAINEL-DE-GESTAO.md`; esta tela é o degrau 0 da
escada dele (§9). O que ela responde, numa tela de celular: **estamos ganhando
ou perdendo a Meta Crucialmente Importante?** A meta, decidida pelo mantenedor
em 03/09/2026, é o número de alunos na plataforma, no formato das 4 Disciplinas
da Execução: *de X para Y até quando*.

## As três leis desta tela, e de onde vêm

1. **Número sem cartão não aparece** (plano, §2). O cartão de uma métrica é um
   arquivo em `painel/cartoes/<nome>.json` que diz o que o número é, de onde
   vem, quem tem o direito de declará-lo e qual métrica o segura (o "par").
   Cartão ausente ou inválido ⇒ a página abre, DIZ o que faltou, e não mostra
   o número. É o mesmo desenho do painel do dono, que recusa registro inválido
   em vez de desenhá-lo torto. Guarda: `tests/test_placar.py`.
2. **X é medido, nunca digitado.** Vem da mesma leitura que o mapa da jornada
   usa (`views.contar_a_escola`), pela célula `alunos`, por HTTP e em tempo
   real: a decisão do mantenedor de 25/08/2026 (`PLANO-AREA-ADMIN.md` §5). Duas
   contagens divergiriam no primeiro estado novo.
3. **"Não sei" nunca vira zero.** A `alunos` fora do ar deixa a tela dizendo
   *"não consigo contar"*, com todas as letras. Um zero ali afirmaria que a
   escola está vazia (`RETROSPECTIVA-FASE-D.md`, padrão 1).

## O que mora no cartão e o que NÃO mora

O **alvo** (Y), a **data** e a **partida** (o X do dia em que a meta foi
fixada) moram no cartão, porque são parâmetros da régua, versionados por PR
como qualquer regra de cálculo. O FATO de que o mantenedor decidiu o alvo mora
no livro (`painel/registros/`, tipo `decisao`, citando o PR que mudou o
cartão). Um lugar para a régua, um lugar para o acontecimento: nenhum fato em
dois lugares.

Enquanto o alvo não existe, o cartão diz `null` e a tela diz "aguardando o
mantenedor". Isso não é falha: é a pendência dele, à vista.

## O veredito, sem índice

Ganhando ou perdendo é a comparação de X com o **esperado de hoje** numa linha
reta da partida ao alvo. Não há ponderação, não há nota de 0 a 100: o plano
proíbe número composto no andar zero (§2), e a régua mais simples é a que o
mantenedor consegue conferir de cabeça.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from .clients import AlunosClient
from .painel import CANDIDATOS
from .views import contar_a_escola

#: A subpasta do painel onde moram os cartões. Viaja para a imagem junto com o
#: resto de `painel/` (o `deploy-celula` copia a pasta inteira).
PASTA_DOS_CARTOES = "cartoes"

#: O cartão da Meta Crucialmente Importante nº 1 e o do seu par.
CARTAO_DA_META = "alunos-na-plataforma"
CARTAO_DO_PAR = "alunos-ativos-30d"

#: Os quatro tipos de número do plano (§2). Não existe tipo "composto": um
#: número composto é reconhecido pelo campo `componentes`, e nunca desce ao
#: andar zero.
TIPOS = ("resultado", "direcao", "par", "confianca")

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

#: Quantos alunos a contagem da escola chama de "aluno". A chave é a mesma da
#: `contar_a_escola`, e é a lista de PERMISSÃO da `alunos` que decide quem entra
#: nela (`DECISAO-fila-de-liberacao.md`).
CHAVE_DA_CONTAGEM = "ativos"


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
    versao = cartao.get("versao")
    if not isinstance(versao, int) or isinstance(versao, bool) or versao < 1:
        problemas.append("`versao` é um inteiro a partir de 1, sem aspas")
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
    partida = int(cartao["partida"])
    ate = _data(cartao["ate"])
    partida_em = _data(cartao["partida_em"])
    total = (ate - partida_em).days
    decorridos = min(max((hoje - partida_em).days, 0), total)
    esperado = (
        partida + round((alvo - partida) * decorridos / total) if total > 0 else alvo
    )
    dias_restantes = max((ate - hoje).days, 0)
    faltam = alvo - x
    semanas = dias_restantes / 7
    # Quantos alunos por semana faltam para chegar lá: a única conta que vira
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


@require_GET
def placar(request):
    """O andar zero. Fail-OPEN na rede (a página abre), fail-CLOSED no cartão
    (o número não aparece sem ele)."""
    pasta = diretorio_dos_cartoes()
    meta, recusas = ler_cartao(CARTAO_DA_META, pasta)
    par, recusas_do_par = ler_cartao(CARTAO_DO_PAR, pasta)

    resultado = None
    if meta is not None:
        contagens, _filas, _alunos = contar_a_escola(AlunosClient())
        resultado = calcular_placar(
            meta, contagens.get(CHAVE_DA_CONTAGEM), timezone.localdate()
        )

    return render(
        request,
        "admin/placar.html",
        {
            "admin": request.admin,
            "meta": meta,
            "recusas": recusas,
            "par": par,
            "recusas_do_par": recusas_do_par,
            "placar": resultado,
        },
    )
