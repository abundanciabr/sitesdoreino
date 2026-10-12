"""Orientação do mantenedor em 12/10/2026; somente gestão administrativa."""

import datetime as dt

from django.utils import timezone

INICIO_ALUNOS = dt.date(2026, 10, 12)
PRAZO_ALUNOS = dt.date(2027, 12, 31)
META_ALUNOS = 10000
DOCUMENTO = "https://meshcraft.top/admin/documentos/principio-central-lancamentos-perpetuos-20261012"
TESE = (
    "Tráfego pago → quizzes → low, mid e high ticket → novos alunos na plataforma "
    "→ entrega de valor e aprendizado para melhorar o próximo lançamento. "
    "Os lançamentos se repetem semanalmente, em ciclos sucessivos de 12 semanas."
)


def orientacao_dos_robos():
    from .ciclo_produtos import PAINEIS

    return (
        "ORIENTAÇÃO CENTRAL DO MANTENEDOR — 12/10/2026. "
        + TESE
        + f" Primeiro ciclo: {PAINEIS['desafio']['meta']} vendas low ticket e "
        + f"{PAINEIS['curso']['meta']} vendas mid ticket (Curso Primeiros Dólares). "
        + "Até 31/12/2027: 10.000 pessoas únicas com compra pelo checkout do site ou "
        "liberação na escola marcada como nova venda paga a partir de 12/10/2026. "
        "Várias compras da mesma pessoa são vendas distintas e um único aluno. "
        "Não somar automaticamente a base antiga. As 12 semanas são o calendário "
        "dos lançamentos perpétuos, não um programa de descoberta ou duração de curso. "
        "Relacionar recomendações ao gargalo desse motor, preservando a entrega ao aluno. "
        "Distinguir evidência, hipótese e dado ausente; não inventar metas futuras, "
        "crescimento exponencial, lucro ou oferta high ticket. Esta orientação interna "
        "não deve ser incluída em mensagens aos clientes. Referência: " + DOCUMENTO
    )


def calendario(hoje):
    from .ciclo_produtos import INICIO, PAINEIS

    numero = max(0, (hoje - INICIO).days // 84)
    inicio = INICIO + dt.timedelta(days=84 * numero)
    semanas = []
    for n in range(12):
        de = inicio + dt.timedelta(weeks=n)
        ate = de + dt.timedelta(days=6)
        semanas.append(
            {
                "n": n + 1,
                "de": de,
                "ate": ate,
                "atual": de <= hoje <= ate,
                "low": (
                    PAINEIS["desafio"]["metas"][n] if numero == 0 and n < 10 else None
                ),
                "mid": PAINEIS["curso"]["metas"][n] if numero == 0 and n < 10 else None,
                "recuperacao": numero == 0 and n >= 10,
            }
        )
    return {
        "numero": numero + 1,
        "inicio": inicio,
        "fim": inicio + dt.timedelta(days=83),
        "proximo": inicio + dt.timedelta(days=84),
        "semanas": semanas,
    }


def contar_alunos(fichas, site_id, hoje):
    """Contagem acumulada por cadastro; a origem já inclui nova venda manual.

    Não depende de haver contato de CRM: uma compra confirmada do checkout
    também é elegível. Matrículas antigas nunca entram só por estarem ativas.
    """
    from .placar import dia_em_sao_paulo, vendeu_pelo_site

    if fichas is None or not site_id:
        return {
            "total": None,
            "motivo": "Não foi possível consultar as matrículas deste site.",
        }
    pessoas, vendas, incompletas = set(), 0, 0
    for ficha in fichas:
        if str(ficha.get("site_id")) != str(site_id):
            continue
        if not vendeu_pelo_site(ficha):
            continue
        dia = dia_em_sao_paulo(ficha.get("virou_aluno_em"))
        if dia is None:
            incompletas += 1
            continue
        if not INICIO_ALUNOS <= dia <= min(hoje, PRAZO_ALUNOS):
            continue
        email = str(ficha.get("email") or "").strip().casefold()
        if not email or "@" not in email:
            incompletas += 1
            continue
        pessoas.add(email)
        vendas += 1
    if incompletas:
        return {
            "total": None,
            "motivo": "Há compras sem data ou cadastro suficiente para uma contagem completa.",
        }
    return {
        "total": len(pessoas),
        "vendas": vendas,
        "faltam": max(0, META_ALUNOS - len(pessoas)),
        "percentual": min(100, len(pessoas) * 100 / META_ALUNOS),
    }


def resumo(hoje=None):
    from .ciclo_produtos import PAINEIS, numero

    return {
        "tese": TESE,
        "documento": DOCUMENTO,
        "meta": META_ALUNOS,
        "meta_texto": numero(META_ALUNOS),
        "low_texto": numero(PAINEIS["desafio"]["meta"]),
        "mid_texto": numero(PAINEIS["curso"]["meta"]),
        "inicio_alunos": INICIO_ALUNOS,
        "prazo_alunos": PRAZO_ALUNOS,
        "low": PAINEIS["desafio"]["meta"],
        "mid": PAINEIS["curso"]["meta"],
        "calendario": calendario(hoje or timezone.localdate()),
    }


def contexto(request):
    admin = getattr(request, "admin", None)
    return {"governanca": resumo()} if admin and not admin.get("equipe_apenas") else {}
