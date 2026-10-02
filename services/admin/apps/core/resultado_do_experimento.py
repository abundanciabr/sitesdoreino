"""`/admin/placar/experimentos/<id>/resultado/`: a versão B ganhou, perdeu ou
ainda está coletando?

O miolo é puro (biblioteca padrão, sem dependência nova) e mora em cima; a
tela, que junta o catálogo (o experimento) e a medição (`countFunnel`), mora
embaixo. A regra vem do desenho comum do sistema de experimentos, com a
Emenda 1 valendo sobre ele, e da especificação publicada
(`documentos/plataforma-experimentacao-e-aprendizado-de-conversao.md`, §11,
§12 e §19).

## A conta

- N de cada braço são os **expostos** (quem viu a seção), nunca os sorteados;
  conversão é quem, exposto, clicou para o checkout.
- Efeito de B contra A, absoluto e relativo; p bicaudal do teste z de duas
  proporções com variância agrupada; intervalo de 95% da diferença sem agrupar.
- SRM por qui-quadrado contra os pesos, sobre atribuídos E sobre expostos,
  com alarme em p < 0,001. Duas variantes dão 1 grau de liberdade, e a cauda
  da qui-quadrado com 1 grau é `erfc(raiz(x / 2))`, exata.

## Horizonte fixo, sem espiar

O experimento nasce com `dias_planejados` e `n_por_braco_planejado`. Até o
último dia da janela `[iniciado_em, fim_planejado]` terminar, o veredito é
`coletando` e a conta de p e do intervalo **não é feita**: a tela mostra só
contagens, SRM e progresso. Olhar o p todo dia e parar quando ele cai abaixo de
0,05 fabrica vencedor falso. Depois do horizonte a janela não cresce mais, e a
mesma pergunta devolve sempre a mesma conta. Encerrado antes do horizonte, a
conta também não é feita, pela mesma razão.

## O veredito

- `coletando`: o horizonte ainda não passou.
- `inconclusivo (amostra insuficiente)`: passou, e algum braço ficou abaixo do
  N planejado.
- `inconclusivo`: a diferença cabe no acaso, B converteu menos que A, ou a
  divisão saiu torta (SRM em alarme ou visitantes com braço trocado acima do
  limite). Divisão torta mede defeito de sorteio, cache ou coleta, e não
  preferência de quem visita.
- `candidato à promoção`: amostra cheia, p < 0,05, B acima de A, divisão sã.
  Candidato, e não vencedor: a decisão continua de quem decide (§11).
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass
from statistics import NormalDist

from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from .clients import CatalogoClient, MedicaoClient
from .paginas import SLUG_DA_PAGINA, _site

ALFA = 0.05
PODER = 0.80
LIMIAR_DO_SRM = 0.001
#: O sorteio é determinístico por visitante, então braço trocado só nasce de
#: defeito (cache servindo a página de outra pessoa, por exemplo); até 1% dos
#: atribuídos dilui o efeito em cerca de 2% dele sem inverter o sinal, e acima
#: disso a contaminação já esconde um efeito do tamanho do planejado.
LIMITE_DE_TROCADOS = 0.01

_Z_DO_INTERVALO = NormalDist().inv_cdf(1 - ALFA / 2)
_Z_DO_PODER = NormalDist().inv_cdf(PODER)

COLETANDO = "coletando"
INCONCLUSIVO = "inconclusivo"
AMOSTRA_INSUFICIENTE = "inconclusivo (amostra insuficiente)"
CANDIDATO = "candidato à promoção"


@dataclass(frozen=True)
class Braco:
    variante_id: str
    peso: int
    atribuidos: int
    expostos: int
    convertidos: int

    @property
    def taxa(self) -> float | None:
        return self.convertidos / self.expostos if self.expostos else None


@dataclass(frozen=True)
class Comparacao:
    efeito_absoluto: float | None
    efeito_relativo: float | None
    ic95: tuple[float, float] | None
    p: float | None


@dataclass(frozen=True)
class Srm:
    base: str
    qui_quadrado: float | None
    p: float | None
    alarme: bool


@dataclass(frozen=True)
class Resultado:
    veredito: str
    motivo: str
    controle: Braco
    tratamento: Braco
    fim_planejado: dt.date
    dias_corridos: int
    dias_planejados: int
    n_por_braco_planejado: int
    srm_atribuidos: Srm
    srm_expostos: Srm
    trocados: int
    trocados_em_alarme: bool
    comparacao: Comparacao | None


def n_por_braco_planejado(taxa_base: float, mde: float) -> int:
    """Visitantes expostos por braço para detectar `mde` (absoluto) sobre
    `taxa_base`, com alfa 0,05 bicaudal e poder 0,8.

    A fórmula é a da DECISAO-a-pagina-real-antes-do-experimento, §3 (variância
    agrupada sob a hipótese nula), com o efeito dado em pontos absolutos, como o
    experimento guarda.
    """
    if not 0 < taxa_base < 1:
        raise ValueError(
            f"a taxa de base {taxa_base} precisa ficar entre 0 e 1, sem as pontas; "
            "use a fração medida hoje (por exemplo 0,1 para 10%)"
        )
    if mde <= 0:
        raise ValueError(
            f"o efeito mínimo detectável {mde} precisa ser positivo; "
            "diga quantos pontos de taxa a versão B precisa ganhar (por exemplo 0,02)"
        )
    tratado = taxa_base + mde
    if tratado >= 1:
        raise ValueError(
            f"a taxa de base somada ao efeito mínimo dá {tratado}, e taxa não passa "
            "de 1; diminua o efeito mínimo"
        )
    media = (taxa_base + tratado) / 2
    termo_nulo = _Z_DO_INTERVALO * math.sqrt(2 * media * (1 - media))
    termo_alternativo = _Z_DO_PODER * math.sqrt(
        taxa_base * (1 - taxa_base) + tratado * (1 - tratado)
    )
    return math.ceil(((termo_nulo + termo_alternativo) / mde) ** 2)


def comparar(controle: Braco, tratamento: Braco) -> Comparacao:
    """B contra A. Braço sem exposto não tem taxa, e então não há conta."""
    na, nb = controle.expostos, tratamento.expostos
    if not na or not nb:
        return Comparacao(None, None, None, None)
    pa, pb = controle.taxa, tratamento.taxa
    efeito = pb - pa
    relativo = efeito / pa if pa else None

    agrupada = (controle.convertidos + tratamento.convertidos) / (na + nb)
    erro_nulo = math.sqrt(agrupada * (1 - agrupada) * (1 / na + 1 / nb))
    # Erro zero só acontece com taxa agrupada 0 ou 1, e aí o efeito é zero.
    p = math.erfc(abs(efeito / erro_nulo) / math.sqrt(2)) if erro_nulo else 1.0

    erro = math.sqrt(pa * (1 - pa) / na + pb * (1 - pb) / nb)
    margem = _Z_DO_INTERVALO * erro
    return Comparacao(efeito, relativo, (efeito - margem, efeito + margem), p)


def srm(bracos: list[Braco], base: str) -> Srm:
    """Qui-quadrado da contagem `base` ("atribuidos" ou "expostos") contra os
    pesos. Duas variantes, 1 grau de liberdade."""
    if len(bracos) != 2:
        raise ValueError(f"o SRM daqui compara duas variantes, e vieram {len(bracos)}")
    observados = [getattr(b, base) for b in bracos]
    total = sum(observados)
    if total == 0:
        return Srm(base, None, None, False)
    soma_dos_pesos = sum(b.peso for b in bracos)
    qui = 0.0
    for braco, observado in zip(bracos, observados):
        esperado = total * braco.peso / soma_dos_pesos if soma_dos_pesos else 0
        if esperado == 0:
            if observado:
                return Srm(base, math.inf, 0.0, True)
            continue
        qui += (observado - esperado) ** 2 / esperado
    p = math.erfc(math.sqrt(qui / 2))
    return Srm(base, qui, p, p < LIMIAR_DO_SRM)


def avaliar(
    bracos: list[Braco],
    *,
    iniciado_em: dt.date,
    dias_planejados: int,
    n_por_braco_planejado: int,
    hoje: dt.date,
    trocados: int,
    encerrado_em: dt.date | None = None,
) -> Resultado:
    """O veredito do experimento. `controle` é a primeira variante em ordem de
    `variante_id` (`a`, no desenho comum)."""
    controle, tratamento = sorted(bracos, key=lambda b: b.variante_id)
    fim = iniciado_em + dt.timedelta(days=dias_planejados)
    srm_atribuidos = srm([controle, tratamento], "atribuidos")
    srm_expostos = srm([controle, tratamento], "expostos")
    atribuidos = controle.atribuidos + tratamento.atribuidos
    trocados_em_alarme = trocados > LIMITE_DE_TROCADOS * atribuidos

    def resultado(veredito: str, motivo: str, comparacao: Comparacao | None = None):
        return Resultado(
            veredito=veredito,
            motivo=motivo,
            controle=controle,
            tratamento=tratamento,
            fim_planejado=fim,
            dias_corridos=max(0, min((hoje - iniciado_em).days, dias_planejados)),
            dias_planejados=dias_planejados,
            n_por_braco_planejado=n_por_braco_planejado,
            srm_atribuidos=srm_atribuidos,
            srm_expostos=srm_expostos,
            trocados=trocados,
            trocados_em_alarme=trocados_em_alarme,
            comparacao=comparacao,
        )

    if encerrado_em is not None and encerrado_em < fim:
        return resultado(
            INCONCLUSIVO,
            f"O experimento foi encerrado em {encerrado_em:%d/%m/%Y}, antes do fim "
            f"planejado ({fim:%d/%m/%Y}). A conta não é feita: parar no meio e "
            "julgar pelo que se viu até ali é o jeito mais comum de declarar "
            "vencedor falso.",
        )
    if hoje <= fim:
        return resultado(
            COLETANDO,
            f"A janela vai até {fim:%d/%m/%Y}. Até lá esta tela mostra só quem "
            "entrou em cada versão, para ninguém decidir espiando o meio.",
        )

    comparacao = comparar(controle, tratamento)
    if min(controle.expostos, tratamento.expostos) < n_por_braco_planejado:
        return resultado(
            AMOSTRA_INSUFICIENTE,
            f"O planejado eram {n_por_braco_planejado} pessoas expostas em cada "
            "versão, e pelo menos uma ficou abaixo disso. Com menos gente, uma "
            "diferença do tamanho planejado passa despercebida.",
            comparacao,
        )
    if srm_atribuidos.alarme or srm_expostos.alarme or trocados_em_alarme:
        return resultado(
            INCONCLUSIVO,
            "A divisão de visitantes saiu diferente da planejada. Isso costuma "
            "ser defeito de sorteio, de cache ou de coleta, e não preferência de "
            "quem visita; a promoção fica bloqueada até a causa ser achada.",
            comparacao,
        )
    if comparacao.p < ALFA and comparacao.efeito_absoluto > 0:
        return resultado(
            CANDIDATO,
            f"A versão {tratamento.variante_id} converteu mais que a "
            f"{controle.variante_id}, com p abaixo de {ALFA}, amostra cheia e "
            "divisão sã. A decisão de promover continua sua.",
            comparacao,
        )
    if comparacao.p < ALFA:
        return resultado(
            INCONCLUSIVO,
            f"A versão {tratamento.variante_id} converteu menos que a "
            f"{controle.variante_id}, e a diferença não é acaso. Não há o que "
            "promover.",
            comparacao,
        )
    return resultado(
        INCONCLUSIVO,
        f"A diferença cabe no acaso (p de {_decimal(comparacao.p, 4)}, acima de "
        f"{ALFA}). A versão atual continua valendo.",
        comparacao,
    )


# ---------------------------------------------------------------------------
# A tela
# ---------------------------------------------------------------------------


def _decimal(valor: float, casas: int) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def _p(valor: float) -> str:
    """Um p com quatro casas; abaixo disso, "menos de 0,0001", e não um zero."""
    return "menos de 0,0001" if valor < 0.0001 else _decimal(valor, 4)


def _pontos(valor: float) -> str:
    """Diferença de taxas em pontos percentuais, com sinal."""
    return ("+" if valor > 0 else "") + _decimal(valor * 100, 2) + " pontos"


def _dia(valor: object) -> dt.date | None:
    """Data do catálogo. Instante com fuso vira o dia de São Paulo, que é o dia
    em que a medição conta."""
    if not isinstance(valor, str) or not valor:
        return None
    try:
        instante = dt.datetime.fromisoformat(valor)
    except ValueError:
        return None
    if timezone.is_aware(instante):
        return timezone.localtime(instante).date()
    return instante.date()


def _ler_experimento(corpo: dict) -> dict | str:
    """O experimento na forma que a conta usa, ou a frase do que faltou."""
    variantes = corpo.get("variantes")
    if not isinstance(variantes, list) or len(variantes) != 2:
        return "o resultado compara duas versões, e o experimento não tem duas"
    pesos = {}
    for variante in variantes:
        chave = variante.get("variante_id") if isinstance(variante, dict) else None
        peso = variante.get("peso") if isinstance(variante, dict) else None
        if not isinstance(chave, str) or not isinstance(peso, int):
            return "uma versão veio sem nome ou sem peso"
        pesos[chave] = peso
    dias = corpo.get("dias_planejados")
    n = corpo.get("n_por_braco_planejado")
    if not isinstance(dias, int) or dias <= 0 or not isinstance(n, int) or n <= 0:
        return "o experimento veio sem os dias ou sem o tamanho de amostra planejados"
    estado = corpo.get("estado")
    iniciado_em = _dia(corpo.get("iniciado_em"))
    encerrado_em = _dia(corpo.get("encerrado_em"))
    if estado == "ativo" and iniciado_em is None:
        return "o experimento está ativo, mas veio sem a data de início"
    if estado == "encerrado" and iniciado_em is not None and encerrado_em is None:
        return "o experimento foi encerrado, mas veio sem a data de encerramento"
    return {
        "estado": estado,
        "secao": corpo.get("secao") or "",
        "metrica_principal": corpo.get("metrica_principal") or "",
        "pesos": pesos,
        "dias_planejados": dias,
        "n_por_braco_planejado": n,
        "iniciado_em": iniciado_em,
        "encerrado_em": encerrado_em,
    }


def _ler_bracos(corpo: object, pesos: dict) -> tuple[list[Braco], int] | str:
    """Os dois braços da medição, ou a frase do que veio fora do combinado.
    Braço ausente com coleta é braço sem ninguém ainda, e conta zero."""
    variantes = corpo.get("variantes") if isinstance(corpo, dict) else None
    trocados = (
        corpo.get("visitantes_com_bracos_trocados") if isinstance(corpo, dict) else None
    )
    if not isinstance(variantes, list) or not isinstance(trocados, int):
        return "a medição respondeu sem as versões ou sem a contagem de braços trocados"
    contagens = {}
    for linha in variantes:
        chave = linha.get("variante_id") if isinstance(linha, dict) else None
        if chave not in pesos:
            return f"a medição contou uma versão que o experimento não tem ({chave})"
        numeros = [linha.get(c) for c in ("atribuidos", "expostos", "convertidos")]
        if not all(isinstance(x, int) and x >= 0 for x in numeros):
            return f"a versão {chave} veio com contagem que não é número"
        contagens[chave] = numeros
    bracos = [
        Braco(chave, peso, *contagens.get(chave, (0, 0, 0)))
        for chave, peso in pesos.items()
    ]
    return bracos, trocados


def _linhas(r: Resultado) -> list[dict]:
    maduro = r.comparacao is not None
    linhas = []
    for b in (r.controle, r.tratamento):
        linhas.append(
            {
                "variante_id": b.variante_id,
                "peso": _decimal(b.peso / 100, 0) + "%",
                "atribuidos": b.atribuidos,
                "expostos": b.expostos,
                "vistos": (
                    _decimal(b.expostos / b.atribuidos * 100, 1) + "%"
                    if b.atribuidos
                    else "sem ninguém"
                ),
                "faltam": max(0, r.n_por_braco_planejado - b.expostos),
                "convertidos": b.convertidos if maduro else None,
                "taxa": (
                    (
                        _decimal(b.taxa * 100, 2) + "%"
                        if b.taxa is not None
                        else "sem taxa"
                    )
                    if maduro
                    else None
                ),
            }
        )
    return linhas


def _conta(c: Comparacao | None) -> dict | None:
    if c is None or c.p is None:
        return None
    return {
        "efeito": _pontos(c.efeito_absoluto),
        "relativo": (
            ("+" if c.efeito_relativo > 0 else "")
            + _decimal(c.efeito_relativo * 100, 1)
            + "%"
            if c.efeito_relativo is not None
            else "não existe (a versão de controle não converteu ninguém)"
        ),
        "ic": f"de {_pontos(c.ic95[0])} a {_pontos(c.ic95[1])}",
        "p": _p(c.p),
    }


def _srm(s: Srm) -> dict:
    return {
        "alarme": s.alarme,
        "p": "sem ninguém ainda" if s.p is None else _p(s.p),
    }


def contar(site_id: str, corpo: dict, hoje: dt.date) -> dict:
    """Os braços que a medição contou, já avaliados, em `resultado`; ou o
    desfecho com nome de por que não deu. A tela e o `manage.py
    semear_experimento --acao medir` leem a contagem por aqui, e contam igual."""
    experimento = _ler_experimento(corpo)
    if isinstance(experimento, str):
        return {"estado": "fora-do-contrato", "frase": experimento}
    base = {"experimento": experimento}
    if experimento["iniciado_em"] is None:
        return {**base, "estado": "nao-comecou"}

    fim = experimento["iniciado_em"] + dt.timedelta(days=experimento["dias_planejados"])
    desde, ate = experimento["iniciado_em"], min(hoje, fim)
    base.update(desde=desde, ate=ate)
    desfecho, funil = MedicaoClient().funil(
        desde,
        ate,
        site_id,
        experimento_id=str(corpo.get("id") or ""),
        secao=experimento["secao"],
    )
    if desfecho != MedicaoClient.OK:
        return {**base, "estado": "medicao-nao-respondeu", "desfecho": desfecho}
    if funil["coleta"]["primeiro"] is None:
        return {**base, "estado": "sem-coleta"}
    lidos = _ler_bracos(funil, experimento["pesos"])
    if isinstance(lidos, str):
        return {**base, "estado": "fora-do-contrato", "frase": lidos}
    bracos, trocados = lidos

    resultado = avaliar(
        bracos,
        iniciado_em=experimento["iniciado_em"],
        dias_planejados=experimento["dias_planejados"],
        n_por_braco_planejado=experimento["n_por_braco_planejado"],
        hoje=hoje,
        trocados=trocados,
        encerrado_em=experimento["encerrado_em"],
    )
    return {**base, "estado": "contado", "resultado": resultado}


def calcular(site_id: str, corpo: dict, hoje: dt.date) -> dict:
    """O resultado de um experimento já lido do catálogo. Cada desfecho tem
    nome, e nenhum deles é zero."""
    contagem = contar(site_id, corpo, hoje)
    if contagem["estado"] != "contado":
        return contagem
    r = contagem.pop("resultado")
    return {
        **contagem,
        "estado": "resultado",
        "veredito": r.veredito,
        "motivo": r.motivo,
        "coletando": r.veredito == COLETANDO,
        "controle": r.controle.variante_id,
        "tratamento": r.tratamento.variante_id,
        "fim_planejado": r.fim_planejado,
        "dias_corridos": r.dias_corridos,
        "linhas": _linhas(r),
        "conta": _conta(r.comparacao),
        "srm_atribuidos": _srm(r.srm_atribuidos),
        "srm_expostos": _srm(r.srm_expostos),
        "trocados": r.trocados,
        "trocados_em_alarme": r.trocados_em_alarme,
    }


def veredito_do_experimento(site_id: str, experimento: dict) -> str | None:
    """O veredito para quem decide (frente F9d), ou `None` quando não deu para
    calcular: medição fora do ar, sem coleta, rascunho ou resposta torta."""
    return calcular(site_id, experimento, timezone.localdate()).get("veredito")


def montar(site: dict | None, experimento_id: str, hoje: dt.date) -> dict:
    """O que a tela mostra: o site do domínio, o experimento, e a conta."""
    if site is None:
        return {
            "estado": "catalogo-nao-respondeu",
            "frase": "não consegui saber de qual site é este endereço",
        }
    desfecho, corpo = CatalogoClient().experimento(
        site["id"], SLUG_DA_PAGINA, experimento_id
    )
    if desfecho == CatalogoClient.SEM_EXPERIMENTO:
        return {"estado": "sem-experimento"}
    if desfecho != CatalogoClient.OK:
        return {"estado": "catalogo-nao-respondeu", "frase": corpo}
    return calcular(site["id"], corpo, hoje)


@require_GET
def resultado_do_experimento(request, experimento_id):
    """A tela. Fail-OPEN, como as outras do placar: abre e DIZ o que faltou."""
    return render(
        request,
        "admin/resultado_do_experimento.html",
        {
            "admin": request.admin,
            "experimento_id": str(experimento_id),
            "tela": montar(_site(request), str(experimento_id), timezone.localdate()),
        },
    )
