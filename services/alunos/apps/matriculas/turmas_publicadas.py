"""Read published cohort names without rewriting enrollment history."""

import hashlib

from .models import Turma


def legacy_slug(nome):
    return "legacy-" + hashlib.sha256(nome.encode("utf-8")).hexdigest()[:20]


def mapa_de_nomes(matriculas):
    """Resolve cohorts for a batch using one query, scoped by site."""
    keys = {(m.site_id, m.turma) for m in matriculas if m.turma}
    if not keys:
        return {}
    rows = Turma.objects.filter(site_id__in={site for site, _ in keys}, published=True)
    by_slug = {(row.site_id, row.slug): row for row in rows}
    by_key = {
        (row.site_id, row.chave_matricula): row for row in rows if row.chave_matricula
    }
    by_name = {(row.site_id, row.nome): row for row in rows}
    resolved = {}
    for site_id, raw in keys:
        row = (
            by_slug.get((site_id, legacy_slug(raw)))
            or by_key.get((site_id, raw))
            or by_slug.get((site_id, raw))
            or by_name.get((site_id, raw))
        )
        resolved[(site_id, raw)] = row.nome if row else raw
    return resolved


def nome_para_exibir(matricula, nomes=None):
    if not matricula.turma:
        return None
    if nomes is None:
        nomes = mapa_de_nomes([matricula])
    return nomes.get((matricula.site_id, matricula.turma), matricula.turma)
