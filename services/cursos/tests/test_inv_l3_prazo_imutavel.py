"""Teste-guarda [INV-CUR-L3]: `prazo_em` de um envio nunca muda por API; o
estouro só se registra em `estourado_em`.

Lei: `PLANO-CELULA-CURSOS.md` §4 (`prazo_em` = `enviado_em` + 24 h,
imutável) e §9; a constituição da célula ("24 horas é constante, com teste.
`prazo_em` não muda por API; o estouro se registra em `estourado_em`. Não é
parâmetro") e o critério de morte da lei §11 ("o prazo de 24 horas como
parâmetro ou com botão de alongar").

Os dentes, e o que cada um mede:

1. **As 24 horas são constante** (`PRAZO_DE_REVISAO`), e o prazo nasce delas.
2. **Um prazo mandado na criação é ignorado**: o modelo calcula o seu.
3. **Atribuir e salvar recusa**, com e sem `update_fields`, nos dois campos.
4. **`update()` do queryset recusa**, nos dois campos.
5. **`bulk_update` recusa.**
6. **O banco recusa** um `UPDATE` cru que deixe o prazo diferente de
   `enviado_em` + 24 h: é o cadeado que vale para o `psql`.
7. **O estouro registra `estourado_em` e não alonga**: depois de
   `registrar_estouros`, `prazo_em` e `enviado_em` são os mesmos.
8. **Nenhum caminho de API tem prazo**: a assinatura de `entregar` é
   keyword-only e não tem parâmetro de prazo, de hora nem de estado; nenhuma
   tela, porta ou serviço atribui `prazo_em`/`enviado_em`.

Provado por mutação em 05/09/2026: apagar o `else` do `Envio.save()` deixa o
dente 3 vermelho (2 failed, um por campo); esvaziar `update()`/`bulk_update()`
de `EnviosQuerySet` deixa os dentes 4 e 5 vermelhos (3 failed: 2 de `update()`,
1 de `bulk_update()`). Restaurado, todos verdes (345 passed na suíte inteira,
em ambos os casos — nenhuma outra parte da célula depende do texto exato da
mensagem de exceção).
"""

from __future__ import annotations

import inspect
import re
from datetime import timedelta
from pathlib import Path

import pytest
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from apps.cursos import envio as checkpoint
from apps.cursos.models import PRAZO_DE_REVISAO, Envio, PrazoImutavel
from tests.conftest import entrega

pytestmark = pytest.mark.django_db

UMA_HORA = timedelta(hours=1)
CELULA = Path(__file__).resolve().parent.parent
FONTES_QUE_NAO_GRAVAM_PRAZO = (
    CELULA / "apps" / "core" / "views.py",
    CELULA / "apps" / "core" / "api.py",
    CELULA / "apps" / "cursos" / "envio.py",
    CELULA / "apps" / "cursos" / "progresso.py",
    CELULA / "apps" / "cursos" / "tasks.py",
)


@pytest.fixture
def envio(ana_pronta):
    return checkpoint.entregar(ana_pronta, **entrega())


def gravado(envio) -> tuple:
    """`(enviado_em, prazo_em)` como está no banco, e não na instância."""
    return Envio.objects.filter(pk=envio.pk).values_list("enviado_em", "prazo_em").get()


# 1
def test_as_24_horas_sao_constante_e_o_prazo_nasce_delas(envio):
    assert PRAZO_DE_REVISAO == timedelta(hours=24)
    assert envio.prazo_em == envio.enviado_em + timedelta(hours=24)
    assert gravado(envio) == (envio.enviado_em, envio.enviado_em + timedelta(hours=24))


# 2
def test_um_prazo_mandado_na_criacao_e_ignorado(ana_pronta):
    agora = timezone.now()
    envio = Envio.objects.create(
        pessoa=ana_pronta.pessoa,
        aula=ana_pronta.aula,
        numero=1,
        enviado_em=agora,
        prazo_em=agora + UMA_HORA,
        links=[],
        readme="x",
        laudo_do_aluno={},
    )
    assert envio.prazo_em == agora + PRAZO_DE_REVISAO
    assert gravado(envio) == (agora, agora + PRAZO_DE_REVISAO)


# 3
@pytest.mark.parametrize("campo", ["prazo_em", "enviado_em"])
def test_atribuir_e_salvar_recusa_e_nada_muda(envio, campo):
    antes = gravado(envio)
    setattr(envio, campo, getattr(envio, campo) + UMA_HORA)
    with pytest.raises(PrazoImutavel):
        envio.save()
    with pytest.raises(PrazoImutavel):
        envio.save(update_fields=[campo])
    assert gravado(envio) == antes


# 4
@pytest.mark.parametrize("campo", ["prazo_em", "enviado_em"])
def test_update_do_queryset_recusa(envio, campo):
    antes = gravado(envio)
    with pytest.raises(PrazoImutavel):
        Envio.objects.filter(pk=envio.pk).update(
            **{campo: getattr(envio, campo) + UMA_HORA}
        )
    assert gravado(envio) == antes


# 5
def test_bulk_update_recusa(envio):
    antes = gravado(envio)
    envio.prazo_em += UMA_HORA
    with pytest.raises(PrazoImutavel):
        Envio.objects.bulk_update([envio], ["prazo_em"])
    assert gravado(envio) == antes


# 6
def test_o_banco_recusa_um_prazo_que_nao_e_enviado_em_mais_24_horas(envio):
    antes = gravado(envio)
    with pytest.raises(IntegrityError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE cursos_envio SET prazo_em = prazo_em + interval '1 hour' "
                "WHERE id = %s",
                [envio.pk],
            )
    assert gravado(envio) == antes


# 7
def test_o_estouro_registra_e_nao_alonga(envio):
    agora = envio.prazo_em + 2 * UMA_HORA
    assert checkpoint.registrar_estouros(agora) == (envio.pk,)
    depois = Envio.objects.get(pk=envio.pk)
    assert depois.estourado_em == agora
    assert (depois.enviado_em, depois.prazo_em) == (envio.enviado_em, envio.prazo_em)


# 8
def test_entregar_nao_tem_parametro_de_prazo_de_hora_nem_de_estado():
    assinatura = inspect.signature(checkpoint.entregar)
    assert list(assinatura.parameters) == [
        "progresso",
        "links",
        "readme",
        "laudo_do_aluno",
    ]
    assert all(
        parametro.kind is inspect.Parameter.KEYWORD_ONLY
        for nome, parametro in assinatura.parameters.items()
        if nome != "progresso"
    )


def test_nenhuma_tela_porta_nem_servico_atribui_prazo_em_ou_enviado_em():
    atribuicao = re.compile(r"\b(prazo_em|enviado_em)\s*=(?!=)")
    for fonte in FONTES_QUE_NAO_GRAVAM_PRAZO:
        texto = fonte.read_text(encoding="utf-8")
        assert texto, f"{fonte.name} vazio: o guarda passaria no vazio"
        achado = atribuicao.search(texto)
        assert achado is None, f"{fonte.name} atribui {achado.group(1)}: [INV-CUR-L3]"
