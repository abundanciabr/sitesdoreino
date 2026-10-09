"""As 13 faixas do aluno: progressão própria, sem XP e sem Cristais.

Quem alimenta: cinco fatos de outros serviços (itens 3D, Sandbox, Fila do
Dólar e rendimento real). Aqui nada toca em `PerfilJogador.xp_total`,
`nivel` ou `cristais_saldo`; a única escrita no perfil é a fila de
comemorações pendentes (e só no ao vivo).

Regras:
- Branca vale desde a entrada; é gravada na primeira avaliação da pessoa.
- Faixas 2, 3 e 4 vêm do primeiro fato de cada tipo, uma vez.
- Faixas 5 a 13 vêm do total ACUMULADO do livro de rendimento real.
- Faixa atual = MAIOR ordem alcançada; nenhuma exige as anteriores.
- Estorno que derruba o total abaixo do limite marca `revertida` (a linha
  fica); subir de novo volta a `alcancada` na mesma linha. Tudo no histórico.
- `historico=True` (carga de quem já existia) nunca avisa nem comemora.
"""

from __future__ import annotations

import logging
from datetime import timezone as dt_tz
from typing import Any

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .cartas import ASSUNTO_CONQUISTA, carta_de_celebracao
from .models import FaixaDoAluno, HistoricoDaFaixa, PerfilJogador, Pessoa, RendimentoRealLivro

logger = logging.getLogger(__name__)

# ordem, slug, nome, cores, conquista, meta em centavos (None = não é de dinheiro)
_DEFINICAO = [
    (1, "branca", "Branca", ["#f4f4f4"], "Começando do zero", None),
    (2, "branca-e-amarela", "Branca e amarela", ["#f4f4f4", "#f2c200"], "Primeiro item criado", None),
    (3, "amarela", "Amarela", ["#f2c200"], "Primeiro trabalho criado no Sandbox", None),
    (4, "laranja", "Laranja", ["#f08a00"], "Primeiro trabalho criado na Fila do Dólar", None),
    (5, "verde", "Verde", ["#2e9d4a"], "Primeiro dinheiro real ganho de um cliente real", 1),
    (6, "verde-e-azul", "Verde e azul", ["#2e9d4a", "#2b6fd6"], "R$ 25 ganhos de clientes reais", 2500),
    (7, "azul", "Azul", ["#2b6fd6"], "R$ 50 ganhos de clientes reais", 5000),
    (8, "azul-e-roxa", "Azul e roxa", ["#2b6fd6", "#7a3fc4"], "R$ 100 ganhos de clientes reais", 10000),
    (9, "roxa", "Roxa", ["#7a3fc4"], "R$ 200 ganhos de clientes reais", 20000),
    (10, "roxa-e-marrom", "Roxa e marrom", ["#7a3fc4", "#7a4a26"], "R$ 500 ganhos de clientes reais", 50000),
    (11, "marrom", "Marrom", ["#7a4a26"], "R$ 750 ganhos de clientes reais", 75000),
    (12, "marrom-e-preta", "Marrom e preta", ["#7a4a26", "#1d1d1d"], "R$ 1.000 ganhos de clientes reais", 100000),
    (13, "preta", "Preta", ["#1d1d1d"], "R$ 2.000 ganhos de clientes reais", 200000),
]
FAIXAS = [
    {"ordem": o, "slug": s, "nome": n, "cores": c, "conquista": q, "meta_cents": m}
    for (o, s, n, c, q, m) in _DEFINICAO
]
_POR_ORDEM = {f["ordem"]: f for f in FAIXAS}

# Origem legível ao aluno: sem nome de cliente, referência ou id.
ORIGENS = {
    "entrada": "Entrada na escola",
    "item": "Primeiro item salvo na prática 3D",
    "sandbox": "Primeiro trabalho criado no Sandbox",
    "fila": "Primeiro trabalho aceito na Fila do Dólar",
    "dinheiro": "Pagamento real de cliente confirmado",
}
_ORDEM_DO_FATO = {"item": 2, "sandbox": 3, "fila": 4}

#: Prefixo do slug enviado na carta (assunto `gamificacao.conquista-concedida`).
PREFIXO_DO_SLUG = "faixa-"


def _brl(cents: int) -> str:
    reais, cs = divmod(int(cents), 100)
    inteiro = f"{reais:,}".replace(",", ".")
    return f"R$ {inteiro},{cs:02d}"


def _pessoa(pessoa_id: str) -> Pessoa:
    pessoa, _ = Pessoa.objects.get_or_create(
        id_da_plataforma=pessoa_id,
        defaults={"email": f"{pessoa_id}@desconhecido.invalid"},
    )
    return pessoa


def _historico_row(pessoa, site_id, ordem, anterior, novo, origem, event_id, historico, quando):
    HistoricoDaFaixa.objects.create(
        pessoa=pessoa,
        site_id=site_id,
        ordem=ordem,
        estado_anterior=anterior,
        estado_novo=novo,
        origem=origem,
        event_id=event_id or "",
        historico=historico,
        ocorrido_em=quando,
    )


def _garantir_branca(pessoa, site_id, event_id, historico, quando) -> None:
    if FaixaDoAluno.objects.filter(pessoa=pessoa, site_id=site_id, ordem=1).exists():
        return
    FaixaDoAluno.objects.create(
        pessoa=pessoa, site_id=site_id, ordem=1, estado=FaixaDoAluno.Estado.ALCANCADA,
        origem="entrada", alcancada_em=quando, event_id=event_id or "", historico=historico,
    )
    _historico_row(pessoa, site_id, 1, "", "alcancada", "entrada", event_id, historico, quando)


def _avisar(pessoa, site_id, ordem: int, event_id: str) -> None:
    """Carta + comemoração de tela. Só ao vivo; reutiliza o mecanismo existente."""
    faixa = _POR_ORDEM[ordem]
    slug = PREFIXO_DO_SLUG + faixa["slug"]
    carta_de_celebracao(
        site_id=site_id,
        destinatario_id=pessoa.id_da_plataforma,
        assunto=ASSUNTO_CONQUISTA,
        parametros={"conquista_slug": slug, "familia": "carreira"},
        origem_event_id=event_id or None,
    )
    perfil, _ = PerfilJogador.objects.get_or_create(pessoa=pessoa, site_id=site_id)
    pendente = {"tipo": "conquista-concedida", "referencia": slug}
    pendentes = list(perfil.celebracoes_pendentes or [])
    if pendente not in pendentes:
        pendentes.append(pendente)
        perfil.celebracoes_pendentes = pendentes
        perfil.save(update_fields=["celebracoes_pendentes", "atualizado_em"])


def _alcancar(pessoa, site_id, ordem, origem, event_id, historico, quando) -> bool:
    """Põe a faixa em `alcancada`. Devolve True se foi a PRIMEIRA vez (linha nova)."""
    linha = FaixaDoAluno.objects.filter(pessoa=pessoa, site_id=site_id, ordem=ordem).first()
    if linha is None:
        FaixaDoAluno.objects.create(
            pessoa=pessoa, site_id=site_id, ordem=ordem, estado="alcancada", origem=origem,
            alcancada_em=quando, event_id=event_id or "", historico=historico,
        )
        _historico_row(pessoa, site_id, ordem, "", "alcancada", origem, event_id, historico, quando)
        return True
    if linha.estado != FaixaDoAluno.Estado.ALCANCADA:
        anterior = linha.estado
        linha.estado = FaixaDoAluno.Estado.ALCANCADA
        linha.event_id = event_id or ""
        linha.save(update_fields=["estado", "event_id", "atualizada_em"])
        _historico_row(pessoa, site_id, ordem, anterior, "alcancada", origem, event_id, historico, quando)
    return False


def _reverter(pessoa, site_id, ordem, event_id, historico, quando) -> None:
    linha = FaixaDoAluno.objects.filter(pessoa=pessoa, site_id=site_id, ordem=ordem).first()
    if linha is None or linha.estado != FaixaDoAluno.Estado.ALCANCADA:
        return
    linha.estado = FaixaDoAluno.Estado.REVERTIDA
    linha.event_id = event_id or ""
    linha.save(update_fields=["estado", "event_id", "atualizada_em"])
    _historico_row(pessoa, site_id, ordem, "alcancada", "revertida", "dinheiro", event_id, historico, quando)


def total_real_cents(pessoa_id: str, site_id: str) -> int:
    """Soma do livro por rendimento (confirmações menos reversões).

    O líquido de CADA rendimento nunca fica abaixo de zero: uma reversão que
    chegou antes da confirmação (streams separados, sem ordem entre eles) fica
    gravada e anula a confirmação quando ela chegar; um estorno em excesso não
    vira crédito para outro rendimento.
    """
    por_ciclo = (
        RendimentoRealLivro.objects.filter(pessoa_id=pessoa_id, site_id=site_id)
        .values("rendimento_id", "ciclo")
        .annotate(t=Sum("valor_cents"))
    )
    # Só o ciclo mais alto de cada rendimento: a confirmação do valor novo que chega
    # antes da reversão do valor velho não soma com ele (sem faixa/aviso falsos).
    topo: dict[str, tuple[int, int]] = {}
    for linha in por_ciclo:
        rid, ciclo = linha["rendimento_id"], int(linha["ciclo"])
        if rid not in topo or ciclo > topo[rid][0]:
            topo[rid] = (ciclo, int(linha["t"] or 0))
    return sum(max(t, 0) for _, t in topo.values())


def _reavaliar_dinheiro(pessoa, site_id, event_id, historico, quando) -> None:
    total = total_real_cents(pessoa.id_da_plataforma, site_id)
    novas: list[int] = []
    for faixa in FAIXAS:
        meta = faixa["meta_cents"]
        if meta is None:
            continue
        if total >= meta:
            if _alcancar(pessoa, site_id, faixa["ordem"], "dinheiro", event_id, historico, quando):
                novas.append(faixa["ordem"])
        else:
            _reverter(pessoa, site_id, faixa["ordem"], event_id, historico, quando)
    # Um aviso só, pela mais alta recém-alcançada (um pagamento grande pode
    # cruzar várias faixas de uma vez).
    if novas and not historico:
        _avisar(pessoa, site_id, max(novas), event_id)


def registrar_fato(
    pessoa_id: str, site_id: str, fato: str, *, event_id: str, quando, historico: bool
) -> None:
    """Primeiro item / trabalho de Sandbox / trabalho da Fila. Fatos repetidos não mudam nada."""
    ordem = _ORDEM_DO_FATO[fato]
    with transaction.atomic():
        pessoa = _pessoa(pessoa_id)
        _garantir_branca(pessoa, site_id, event_id, historico, quando)
        if _alcancar(pessoa, site_id, ordem, fato, event_id, historico, quando) and not historico:
            _avisar(pessoa, site_id, ordem, event_id)


def registrar_rendimento(
    pessoa_id: str, site_id: str, *, event_id: str, rendimento_id: str,
    valor_cents: int, quando, historico: bool, ciclo: int = 1,
) -> bool:
    """Lança no livro (valor com sinal) e reavalia. False se o event_id já estava lá."""
    if not valor_cents:
        return False
    with transaction.atomic():
        pessoa = _pessoa(pessoa_id)
        _, criado = RendimentoRealLivro.objects.get_or_create(
            event_id=str(event_id),
            defaults={
                "pessoa": pessoa, "site_id": site_id, "rendimento_id": str(rendimento_id),
                "valor_cents": int(valor_cents), "ciclo": max(int(ciclo), 1), "ocorrido_em": quando, "historico": historico,
            },
        )
        if not criado:
            return False
        _garantir_branca(pessoa, site_id, event_id, historico, quando)
        _reavaliar_dinheiro(pessoa, site_id, str(event_id), historico, quando)
        return True


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------
def _falta_texto(proxima: dict, total: int) -> str:
    ordem = proxima["ordem"]
    if ordem == 2:
        return "Salve seu primeiro item na prática 3D."
    if ordem == 3:
        return "Crie seu primeiro trabalho no Sandbox."
    if ordem == 4:
        return "Aceite seu primeiro trabalho na Fila do Dólar."
    if ordem == 5:
        return "Receba o primeiro pagamento real de um cliente."
    return f"Faltam {_brl(proxima['meta_cents'] - total)} em pagamentos reais de clientes."


def situacao_das_faixas(pessoa_id: str, site_id: str) -> dict[str, Any]:
    """Situação das 13 faixas de uma pessoa num site (só leitura, nada é gravado)."""
    linhas = {
        f.ordem: f
        for f in FaixaDoAluno.objects.filter(pessoa_id=pessoa_id, site_id=site_id)
    }
    total = total_real_cents(pessoa_id, site_id)
    lista = []
    for faixa in FAIXAS:
        linha = linhas.get(faixa["ordem"])
        if linha is None and faixa["ordem"] == 1:
            alcancada, estado, quando, origem = True, "alcancada", None, ORIGENS["entrada"]
        elif linha is None:
            alcancada, estado, quando, origem = False, "nao-alcancada", None, None
        else:
            alcancada = linha.estado == FaixaDoAluno.Estado.ALCANCADA
            estado = linha.estado
            quando = linha.alcancada_em if alcancada else None
            origem = ORIGENS.get(linha.origem) if alcancada else None
        lista.append({
            "ordem": faixa["ordem"], "nome": faixa["nome"], "cores": list(faixa["cores"]),
            "conquista": faixa["conquista"], "alcancada": alcancada, "estado": estado,
            "alcancada_em": quando, "origem": origem,
        })
    atual = max((f for f in lista if f["alcancada"]), key=lambda f: f["ordem"])
    proxima = None
    if atual["ordem"] < 13:
        p = _POR_ORDEM[atual["ordem"] + 1]
        dinheiro = None
        if p["meta_cents"] is not None:
            meta = p["meta_cents"]
            dinheiro = {
                "total_cents": total,
                "meta_cents": meta,
                "falta_cents": max(meta - total, 0),
                "fracao_pct": min(100, int(total * 100 // meta)),
            }
        proxima = {
            "ordem": p["ordem"], "nome": p["nome"], "cores": list(p["cores"]),
            "conquista": p["conquista"], "falta_texto": _falta_texto(p, total),
            "dinheiro": dinheiro,
        }
    return {
        "atual": {k: atual[k] for k in ("ordem", "nome", "cores", "conquista", "alcancada_em", "origem")},
        "proxima": proxima,
        "faixas": lista,
        "total_real_cents": total,
    }


# ---------------------------------------------------------------------------
# Handlers dos 5 eventos (recebem o ENVELOPE inteiro)
# ---------------------------------------------------------------------------
def _ler(envelope: dict, *campos: str):
    data = envelope.get("data") or {}
    site_id = data.get("site_id")
    pessoa_id = data.get("pessoa_id")
    event_id = envelope.get("event_id")
    if not (site_id and pessoa_id and event_id) or any(data.get(c) in (None, "") for c in campos):
        logger.warning("faixas: evento %s (%s) incompleto, ignorado", event_id, envelope.get("event"))
        return None
    quando = parse_datetime(str(data.get("ocorrido_em") or ""))
    if quando is None:
        from .motor import _quando

        quando = _quando(envelope) or timezone.now()
    if timezone.is_naive(quando):
        quando = timezone.make_aware(quando, dt_tz.utc)
    return str(pessoa_id), str(site_id), str(event_id), quando, bool(data.get("historico")), data


def _tratar_fato(fato: str, campo_id: str):
    def handler(envelope: dict) -> None:
        lido = _ler(envelope, campo_id)
        if lido is None:
            return
        pessoa_id, site_id, event_id, quando, historico, _ = lido
        registrar_fato(pessoa_id, site_id, fato, event_id=event_id, quando=quando, historico=historico)

    return handler


ao_item_criado = _tratar_fato("item", "item_id")
ao_sandbox_trabalho_criado = _tratar_fato("sandbox", "trabalho_id")
ao_fila_trabalho_aceito = _tratar_fato("fila", "pedido_id")


def _ciclo(data: dict) -> int:
    try:
        return max(int(data.get("ciclo") or 1), 1)
    except (TypeError, ValueError):
        return 1


def ao_rendimento_real_confirmado(envelope: dict) -> None:
    lido = _ler(envelope, "rendimento_id", "valor_cents")
    if lido is None:
        return
    pessoa_id, site_id, event_id, quando, historico, data = lido
    valor = int(data["valor_cents"])
    if valor <= 0:
        logger.warning("faixas: rendimento confirmado %s com valor não positivo", event_id)
        return
    registrar_rendimento(
        pessoa_id, site_id, event_id=event_id, rendimento_id=str(data["rendimento_id"]),
        valor_cents=valor, quando=quando, historico=historico, ciclo=_ciclo(data),
    )


def ao_rendimento_real_revertido(envelope: dict) -> None:
    lido = _ler(envelope, "rendimento_id", "valor_cents")
    if lido is None:
        return
    pessoa_id, site_id, event_id, quando, historico, data = lido
    valor = int(data["valor_cents"])
    if valor <= 0:
        logger.warning("faixas: reversão %s com valor não positivo", event_id)
        return
    registrar_rendimento(
        pessoa_id, site_id, event_id=event_id, rendimento_id=str(data["rendimento_id"]),
        valor_cents=-valor, quando=quando, historico=historico, ciclo=_ciclo(data),
    )
