"""Limpeza única autorizada em 11/10/2026, com cópia antes da exclusão.

Preserva registros financeiros e seus comprovantes; eles apenas deixam de
contar na nova progressão. O publicador faz também backup completo antes
das migrações. Nenhuma restauração de dados acontece ao reverter código.
"""
import gzip
import hashlib
import json
import os

from django.core import serializers
from django.db import migrations, models, transaction
from django.db.models import F, Q, Sum
from django.utils import timezone

CHAVE = 'reinicio-autorizado-20261011'
APAGAR = ('AnexoDaJornada', 'RegistroDaJornada', 'HistoricoDaFaixa', 'FaixaDoAluno')
BONUS = Q(regra_slug__startswith='bonus-inicio-etapa-') | Q(regra_slug__startswith='bonus-faixa-')


def reiniciar_site(apps, banco, site):
    """Repetir a operação não apaga o novo progresso."""
    alias = banco.alias
    modelos = {nome: apps.get_model('gamificacao', nome) for nome in (
        *APAGAR, 'JornadaPessoal', 'LancamentoDeXP', 'PerfilJogador',
        'RegraDePontuacao', 'NivelDefinicao', 'BackupDoReinicioDasFaixas',
        'RecebimentoDeclarado', 'RendimentoRealLivro',
    )}
    backup_model = modelos['BackupDoReinicioDasFaixas']
    with transaction.atomic(using=alias):
        if banco.vendor == 'postgresql':
            tabelas = sorted(m._meta.db_table for m in modelos.values())
            with banco.cursor() as cursor:
                cursor.execute('LOCK TABLE ' + ', '.join(banco.ops.quote_name(t) for t in tabelas)
                               + ' IN SHARE ROW EXCLUSIVE MODE')
        existente = backup_model.objects.using(alias).filter(site_id=site, chave=CHAVE).first()
        if existente and existente.aplicado_em:
            return existente
        if existente:
            raise RuntimeError('Cópia de reinício ainda não concluído; nenhum dado foi apagado.')
        agora = timezone.now()
        conjuntos = {nome: modelos[nome].objects.using(alias).filter(site_id=site).order_by('pk')
                     for nome in (*APAGAR, 'JornadaPessoal', 'PerfilJogador',
                                  'RecebimentoDeclarado', 'RendimentoRealLivro')}
        conjuntos['LancamentoDeXP'] = modelos['LancamentoDeXP'].objects.using(alias).filter(site_id=site).filter(BONUS).order_by('pk')
        conjuntos['RegraDePontuacao'] = modelos['RegraDePontuacao'].objects.using(alias).filter(site_id=site).filter(
            Q(slug__startswith='bonus-inicio-etapa-') | Q(slug__startswith='bonus-faixa-')
        ).order_by('pk')
        registros, contagens, pessoas = [], {}, set()
        for nome, consulta in conjuntos.items():
            linhas = list(consulta)
            contagens[nome] = len(linhas)
            pessoas.update(str(linha.pessoa_id) for linha in linhas if hasattr(linha, 'pessoa_id'))
            registros.extend(json.loads(serializers.serialize('json', linhas)))
        contagens['pessoas'] = len(pessoas)
        contagens['xp_das_faixas'] = conjuntos['LancamentoDeXP'].filter(status='definitivo').aggregate(total=Sum('pontos'))['total'] or 0
        bruto = json.dumps(registros, ensure_ascii=False, separators=(',', ':')).encode()
        compactado = gzip.compress(bruto, mtime=0)
        resumo = hashlib.sha256(compactado).hexdigest()
        backup = backup_model.objects.using(alias).create(
            site_id=site, chave=CHAVE, conteudo=compactado, sha256=resumo,
            contagens=contagens, criado_em=agora,
        )
        gravado = bytes(backup_model.objects.using(alias).get(pk=backup.pk).conteudo)
        if hashlib.sha256(gravado).hexdigest() != resumo or gzip.decompress(gravado) != bruto:
            raise RuntimeError('Cópia do reinício não conferida; limpeza cancelada.')
        for nome in APAGAR:
            conjuntos[nome].delete()
        conjuntos['LancamentoDeXP'].delete()
        conjuntos['JornadaPessoal'].update(
            meta_cents=None, proposito='', inicio={}, apoio='guiado', declaracoes={},
            confirmacoes_sequenciais={}, celebracao_pendente={},
            revisao=F('revisao') + 1, atualizada_em=agora,
        )
        # Valores, prints, versões, chaves e estados financeiros ficam intactos.
        for nome in ('RecebimentoDeclarado', 'RendimentoRealLivro'):
            conjuntos[nome].update(fora_da_progressao=True)
        conjuntos['RegraDePontuacao'].update(vigente_desde=agora)
        for perfil in conjuntos['PerfilJogador']:
            total = modelos['LancamentoDeXP'].objects.using(alias).filter(
                pessoa_id=perfil.pessoa_id, site_id=site, status='definitivo',
            ).aggregate(total=Sum('pontos'))['total'] or 0
            total = max(0, total)
            nivel = modelos['NivelDefinicao'].objects.using(alias).filter(
                site_id=site, ativa=True, xp_necessario__lte=total,
            ).order_by('-nivel').values_list('nivel', flat=True).first() or 1
            pendentes = [p for p in (perfil.celebracoes_pendentes or [])
                         if not (p.get('tipo') == 'nivel-alcancado'
                                 or str(p.get('referencia', '')).startswith('faixa-'))]
            modelos['PerfilJogador'].objects.using(alias).filter(pk=perfil.pk).update(
                xp_total=total, nivel=nivel, celebracoes_pendentes=pendentes, atualizado_em=agora,
            )
        backup.aplicado_em = timezone.now()
        backup.save(using=alias, update_fields=['aplicado_em'])
        return backup


def aplicar(apps, schema_editor):
    site = (os.environ.get('SITE_ID') or '').strip()
    if site:
        reiniciar_site(apps, schema_editor.connection, site)
    elif any(apps.get_model('gamificacao', nome).objects.using(schema_editor.connection.alias).exists()
             for nome in (*APAGAR, 'JornadaPessoal', 'PerfilJogador')):
        # Bancos vazios de teste não têm alunos a reiniciar. Num banco com
        # alunos, configuração ausente nunca significa operação concluída.
        raise RuntimeError('SITE_ID ausente: reinício não executado.')


class Migration(migrations.Migration):
    dependencies = [('gamificacao', '0017_confirmacoes_sequenciais')]
    operations = [
        migrations.AddField(model_name='recebimentodeclarado', name='fora_da_progressao',
                            field=models.BooleanField(default=False, db_default=False)),
        migrations.AddField(model_name='rendimentoreallivro', name='fora_da_progressao',
                            field=models.BooleanField(default=False, db_default=False)),
        migrations.CreateModel(
            name='BackupDoReinicioDasFaixas',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('site_id', models.CharField(max_length=64, db_index=True)),
                ('chave', models.CharField(max_length=64)),
                ('conteudo', models.BinaryField()),
                ('sha256', models.CharField(max_length=64)),
                ('contagens', models.JSONField(default=dict)),
                ('criado_em', models.DateTimeField()),
                ('aplicado_em', models.DateTimeField(null=True)),
            ],
            options={'constraints': [models.UniqueConstraint(fields=('site_id', 'chave'), name='um_backup_reinicio_faixas_por_site')]},
        ),
        migrations.RunPython(aplicar, migrations.RunPython.noop),
    ]
