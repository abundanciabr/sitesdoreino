# tests/test_inv_sem_fk_para_fora.py  # [RECEITA:R5 v1]
"""INV-SUG03 — nenhuma FK desta célula aponta para fora do banco dela.

Spec §8 e Lei 3. Não é preferência de estilo: com um database e um role
Postgres **por célula** (`infra/provisionamento-postgres.sql`, medido na
`AUDITORIA-AS-IS.md` Q1), o Postgres simplesmente não sustenta uma constraint
de FK entre bancos diferentes. Uma FK escrita para fora não vira lentidão —
vira migration que não aplica.

Este é o guarda que impede a Lei 3 de ser furada **por acidente** daqui em
diante: ele varre os models de verdade, não uma lista mantida à mão. FK nova
para `django.contrib.*` ou para qualquer app que não seja desta célula reprova
sem ninguém precisar lembrar da regra.
"""

from django.apps import apps
from django.db.models import ForeignKey, ManyToManyField, OneToOneField


def _apps_desta_celula():
    """Derivado, nunca escrito à mão: os apps da célula são os que moram em
    `apps/` (é a convenção do `celula-template`). App novo entra no guarda
    sozinho — que é a diferença entre um portão e um lembrete."""
    return {
        config.label
        for config in apps.get_app_configs()
        if config.name.startswith("apps.")
    }


def test_o_guarda_nao_passa_no_vazio():
    """Sem isto, apagar `apps.sugestoes` do INSTALLED_APPS deixaria o teste
    abaixo verde por não ter nada a inspecionar."""
    labels = _apps_desta_celula()
    assert "sugestoes" in labels
    modelos = [m for m in apps.get_models() if m._meta.app_label in labels]
    assert len(modelos) >= 7, f"esperava os models da §6 da spec, achei {modelos}"


def test_nenhuma_foreign_key_aponta_para_fora_da_celula():
    labels = _apps_desta_celula()
    forasteiras = []

    for modelo in apps.get_models():
        if modelo._meta.app_label not in labels:
            continue
        for campo in modelo._meta.get_fields():
            if not isinstance(campo, (ForeignKey, OneToOneField, ManyToManyField)):
                continue
            alvo = campo.related_model._meta
            if alvo.app_label not in labels:
                forasteiras.append(f"{modelo._meta.label}.{campo.name} -> {alvo.label}")

    assert not forasteiras, (
        "FK saindo do banco da célula (Lei 3 / spec §8): "
        + ", ".join(forasteiras)
        + ". Referência a dado de outra célula é SNAPSHOT em coluna opaca "
        "(o que `Quadro.site_id` e `Quadro.produto_id` já são), nunca FK."
    )


def test_os_ids_inter_celula_sao_texto_opaco_e_nao_uuid():
    """A correção que a `AUDITORIA-AS-IS.md` (Q3) mediu contra a §6 da spec.
    Um `UUIDField` aqui criaria uma fronteira que não casa com a casa: em toda
    a plataforma `Site.id`/`product_id`/`site_id` são `type: string` **sem**
    `format: uuid` nos contratos."""
    from django.db.models import CharField, UUIDField

    from apps.sugestoes.models import Identidade, Quadro

    assert isinstance(Quadro._meta.get_field("site_id"), CharField)
    assert isinstance(Quadro._meta.get_field("produto_id"), CharField)
    assert isinstance(Identidade._meta.get_field("id"), CharField)

    labels = _apps_desta_celula()
    uuids = [
        f"{m._meta.label}.{c.name}"
        for m in apps.get_models()
        if m._meta.app_label in labels
        for c in m._meta.get_fields()
        if isinstance(c, UUIDField)
    ]
    assert not uuids, f"ID em UUIDField, divergindo da plataforma: {uuids}"


def test_o_email_vive_numa_linha_so():
    """EVO-01 §3: sugestão, voto e comentário apontam para `Identidade.id` —
    nunca para o e-mail. Dado pessoal espalhado por cada voto de cada pessoa é
    o que este guarda existe para impedir."""
    from django.db.models import EmailField

    from apps.sugestoes.models import Identidade

    labels = _apps_desta_celula()
    com_email = [
        m._meta.label
        for m in apps.get_models()
        if m._meta.app_label in labels
        for c in m._meta.get_fields()
        if isinstance(c, EmailField) or "email" in c.name
    ]
    assert com_email == [
        Identidade._meta.label
    ], f"e-mail fora da Identidade: {com_email}"
