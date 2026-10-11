"""Resposta privada ao trabalho indicado pelo mantenedor em 11/10/2026."""
from django.db import migrations


TRABALHO = '64a163d4-23aa-483d-a4c5-155f254225aa'


def responder(apps, schema_editor):
    banco = schema_editor.connection.alias
    Participacao = apps.get_model('encomendas', 'ParticipacaoSandbox')
    Entrega = apps.get_model('encomendas', 'EntregaSandbox')
    Analise = apps.get_model('encomendas', 'AnaliseEntregaSandbox')
    Resposta = apps.get_model('encomendas', 'RespostaSandbox')
    Mensagem = apps.get_model('encomendas', 'MensagemSandbox')
    p = Participacao.objects.using(banco).filter(pk=TRABALHO, status='entregue').first()
    if not p:
        return
    entrega = Entrega.objects.using(banco).filter(participacao=p).order_by('-versao').first()
    if not entrega or entrega.versao != 1:
        return
    a = Analise.objects.using(banco).filter(entrega=entrega, estado='concluida').first()
    if not a:
        return
    membros = [m for f in a.resultado.get('medidas_programas', [])
               for m in f.get('conteudo', {}).get('arquivos', [])]
    if not any(m.get('estado') == 'nao_examinado' and m.get('arquivo', '').lower().endswith('.pdf') for m in membros):
        return
    registro, _ = Resposta.objects.using(banco).get_or_create(
        participacao=p, origem='esclarecimento-20261011:' + str(entrega.pk), papel='ia',
        defaults={'site_id': p.site_id})
    if registro.mensagem_id:
        return
    texto = ('Revimos o que aconteceu com sua entrega. A versão 1 foi recebida em 08/10 às 19h12 '
        '(Brasília), dentro do prazo, e houve uma resposta automática às 19h13. '
        'A análise ficou incompleta: o ZIP enviado contém dois PDFs, que o leitor não conseguiu abrir; '
        'nenhum modelo 3D pôde ser examinado. Por isso ainda não existe uma avaliação da espada. '
        'Pedimos desculpas pela falta de clareza na resposta anterior.\n'
        'Para avaliar o trabalho, envie o modelo em .blend ou .glb, as texturas e o render de '
        'apresentação previstos no briefing. Você pode reunir esses arquivos em um ZIP. '
        'Use “Guardar arquivo” e depois “Enviar trabalho concluído” para registrar uma nova versão. '
        'Ela entrará na análise automática, e a resposta aparecerá nesta conversa. '
        'Seu envio original e seu horário permanecem preservados. Isso não é uma reprovação.')
    mensagem = Mensagem.objects.using(banco).create(
        site_id=p.site_id, participacao=p, ator_id='analise-automatica', papel='ia', texto=texto)
    registro.mensagem = mensagem
    registro.estado = 'concluida'
    registro.tentar_em = None
    registro.save(using=banco)


class Migration(migrations.Migration):
    dependencies = [('encomendas', '0028_categorias_do_curso')]
    operations = [migrations.RunPython(responder, migrations.RunPython.noop)]
