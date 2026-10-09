"""`site_id` nas 12 tabelas filhas da prática e da fila interna (multissítio, INV-P11).

Elas nasceram sem a fronteira de site, mas nenhuma é de plataforma inteira: cada
linha é filha de outra que já diz a escola (participação, arquivo, entrega,
pedido, cliente ou saque). Aqui a coluna entra e as linhas que já existem copiam
o site da mãe. Quem vigia para sempre:
`tests/test_modelo_de_dados.py::test_site_id_em_toda_entidade`.
"""

from django.db import migrations, models
from django.db.models import OuterRef, Subquery

# (filha, coluna que aponta para a mãe, mãe). A ordem importa: as análises
# copiam de Arquivo e Entrega, que precisam já estar preenchidos.
FILHAS = [
    ("MensagemSandbox", "participacao_id", "ParticipacaoSandbox"),
    ("EntregaSandbox", "participacao_id", "ParticipacaoSandbox"),
    ("ArquivoSandbox", "participacao_id", "ParticipacaoSandbox"),
    ("AjusteSandbox", "participacao_id", "ParticipacaoSandbox"),
    ("RespostaSandbox", "participacao_id", "ParticipacaoSandbox"),
    ("AnaliseArquivoSandbox", "arquivo_id", "ArquivoSandbox"),
    ("AnaliseEntregaSandbox", "entrega_id", "EntregaSandbox"),
    ("PedidoClienteFila", "pedido_id", "PedidoMarketplace"),
    ("MovimentoOrcamentoFila", "cliente_id", "ClienteFila"),
    ("OrientacaoPrivadaFila", "pedido_id", "PedidoMarketplace"),
    ("CasoConversaFila", "pedido_id", "PedidoMarketplace"),
    ("ParcelaSaqueFila", "saque_id", "SaqueManualFila"),
]


def copiar_site_da_mae(apps, schema_editor):
    for filha, coluna, mae in FILHAS:
        Filha = apps.get_model("encomendas", filha)
        Mae = apps.get_model("encomendas", mae)
        site_da_mae = Mae.objects.filter(pk=OuterRef(coluna)).values("site_id")[:1]
        Filha.objects.filter(site_id="").update(site_id=Subquery(site_da_mae))


class Migration(migrations.Migration):
    dependencies = [("encomendas", "0026_carga_faixas")]
    operations = [
        *[
            migrations.AddField(
                model_name=filha.lower(),
                name="site_id",
                field=models.CharField(db_index=True, default="", max_length=64),
                preserve_default=False,
            )
            for filha, _, _ in FILHAS
        ],
        migrations.RunPython(copiar_site_da_mae, migrations.RunPython.noop),
    ]
