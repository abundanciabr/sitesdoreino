"""Teste-guarda [INV-CUR-C2]: o conteúdo do curso entra pela porta de máquina,
nunca por migração que semeie texto.

Lei: `PLANO-CELULA-CURSOS.md` §9 e a constituição da célula (*"Nenhuma migração
semeia texto de aula"*). A razão é a `armadilhas/331`: este repositório é
PÚBLICO e o curso é obra não lançada do mantenedor. Uma migração com o texto de
uma aula dentro é um `.py` bem-comportado que passa em todo portão, e deixa o
curso legível em `github.com` para sempre, inclusive no histórico.

O guarda tem dois dentes, e os dois medem coisa diferente:

1. **Nenhuma migração desta célula roda código.** A lista é a que o `migrate`
   executa de verdade (o `MigrationLoader` lido do disco), e não uma varredura
   de texto: um `RunPython` disfarçado por `import` continua sendo um
   `RunPython` na lista de operações.
2. **Depois de migrar, o banco não tem peça nenhuma e nenhuma aula tem pedido.**
   É o dente que morde um `INSERT` por `RunSQL`, que o primeiro não vê.

Provado por mutação em 05/09/2026: um `RunPython` que cria uma aula com pedido e
uma peça deixa os três testes vermelhos; restaurado, verdes.
"""

from pathlib import Path

from django.db import migrations
from django.db.migrations.loader import MigrationLoader

from apps.cursos.models import Aula, Peca

PASTA_DAS_MIGRACOES = (
    Path(__file__).resolve().parent.parent / "apps" / "cursos" / "migrations"
)


def _migracoes_da_celula():
    """As migrações de `cursos` como o `migrate` as vê, lidas do disco."""
    loader = MigrationLoader(None, ignore_no_migrations=True)
    return {
        chave: migracao
        for chave, migracao in loader.disk_migrations.items()
        if chave[0] == "cursos"
    }


def test_a_celula_tem_migracao_e_o_loader_a_enxerga():
    """Sem isto, um guarda de "nenhuma migração roda código" passaria numa
    pasta vazia, que é o falso-verde clássico."""
    assert PASTA_DAS_MIGRACOES.is_dir()
    assert ("cursos", "0001_initial") in _migracoes_da_celula()


def test_nenhuma_migracao_desta_celula_roda_codigo():
    com_codigo = sorted(
        f"{app}.{nome}"
        for (app, nome), migracao in _migracoes_da_celula().items()
        if any(isinstance(op, migrations.RunPython) for op in migracao.operations)
    )
    assert com_codigo == [], (
        f"migração com RunPython nesta célula: {com_codigo}. [INV-CUR-C2]: a "
        "migração de esquema não roda código, e o conteúdo do curso entra pela "
        "tela do Admin pela porta de máquina, nunca por arquivo neste "
        "repositório público (armadilhas/331). O esqueleto (números, blocos, os "
        "13 instrumentos) entra por `semear_esqueleto`."
    )


def test_depois_de_migrar_nao_ha_nenhuma_peca(db):
    assert Peca.objects.count() == 0, (
        "há peça no banco recém-migrado: alguma migração semeou texto de aula "
        "([INV-CUR-C2], armadilhas/331)."
    )


def test_depois_de_migrar_nenhuma_aula_tem_pedido(db):
    com_pedido = list(Aula.objects.exclude(pedido="").values_list("numero", flat=True))
    assert com_pedido == [], (
        f"aula com pedido no banco recém-migrado: {com_pedido}. O pedido é texto "
        "do curso e entra pela tela ([INV-CUR-C2], armadilhas/331)."
    )
