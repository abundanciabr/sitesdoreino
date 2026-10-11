"""Devolutiva persistente da análise, inclusive quando a IA não responde."""
from django.db import transaction

from .sandbox_models import MensagemSandbox, ParticipacaoSandbox, RespostaSandbox


def lacunas(resultado):
    pendencias = []
    for arquivo in (resultado or {}).get('medidas_programas', []):
        if arquivo.get('estado') != 'concluida':
            pendencias.append(arquivo.get('arquivo', 'Anexo'))
        for membro in arquivo.get('conteudo', {}).get('arquivos', []):
            if membro.get('estado') != 'concluida' or membro.get('aviso'):
                pendencias.append(membro.get('arquivo', arquivo.get('arquivo', 'Anexo')))
    return list(dict.fromkeys(pendencias))


def texto_campo(valor, campo):
    afirmacoes = {
        'encontrado': 'Identificado nas evidências abaixo.',
        'nao_encontrado': 'Não identificado nas evidências abaixo.',
        'inconclusivo': 'Não foi possível verificar com os arquivos examinados.',
    }
    if valor is True or str(valor).strip().lower() == 'true':
        return afirmacoes[campo]
    if valor is None or valor is False or str(valor).strip().lower() in ('false', 'none'):
        return ''
    return str(valor).strip()


def registrar(entrega, evento, texto):
    """Mensagem e comprovante únicos na mesma transação da entrega/resultado."""
    with transaction.atomic():
        p = ParticipacaoSandbox.objects.select_for_update().get(pk=entrega.participacao_id)
        registro, _ = RespostaSandbox.objects.get_or_create(
            participacao=p, origem=f'{evento}:{entrega.pk}', papel='ia',
            defaults={'site_id': p.site_id})
        if registro.mensagem_id:
            return registro.mensagem
        mensagem = MensagemSandbox.objects.create(
            site_id=p.site_id, participacao=p, ator_id='analise-automatica', papel='ia', texto=texto)
        registro.mensagem = mensagem
        registro.estado = 'concluida'
        registro.tentar_em = None
        registro.save()
        return mensagem


def recebimento(entrega):
    return registrar(entrega, 'recebimento',
        f'Recebemos a versão {entrega.versao} e seus arquivos. A análise automática entrou na fila. '
        'O resultado aparecerá neste trabalho e você receberá uma resposta nesta conversa. '
        'O horário de envio já está registrado; aguardar a análise não altera esse horário.')


def conclusao(analise):
    pendencias = lacunas(analise.resultado)
    if pendencias:
        texto = (f'A análise automática da versão {analise.entrega.versao} terminou incompleta. '
            'Não foi possível examinar integralmente estes arquivos:\n'
            + '\n'.join('- ' + nome for nome in pendencias[:12])
            + '\nIsso não é uma reprovação do seu trabalho. Confira o motivo na análise abaixo. '
            'Para um modelo 3D, o leitor atual abre .blend ou .glb e imagens PNG/JPG; '
            'você pode enviá-los diretamente ou em um ZIP com as texturas e a apresentação '
            'previstas no seu briefing. Guarde os arquivos e use “Enviar trabalho concluído” '
            'para registrar uma nova versão. O envio anterior permanece no histórico.')
    else:
        texto = (f'A análise automática da versão {analise.entrega.versao} foi concluída. '
            'A comparação com o briefing está no histórico de entregas, com as evidências '
            'e os pontos que puderam ou não ser verificados. A aprovação da escola é uma etapa separada.')
    return registrar(analise.entrega, 'resultado-automatico', texto)


def indisponivel(analise):
    return registrar(analise.entrega, 'analise-indisponivel',
        f'A análise automática da versão {analise.entrega.versao} encontrou uma falha. '
        'Seus arquivos e o horário de entrega continuam guardados. '
        'A fila tentará novamente; você também pode usar “Tentar análise desta versão novamente”. '
        'Essa falha não significa reprovação do trabalho.')


def situacao(analise):
    if analise is None:
        return 'Entrega recebida · na fila de análise'
    if analise.estado == 'concluida':
        if lacunas(analise.resultado):
            return 'Análise incompleta · confira os arquivos e envie uma nova versão'
        return 'Análise automática concluída · aguardando aprovação da escola'
    if analise.estado in ('falha', 'falha_ia'):
        return 'Análise indisponível · arquivos recebidos e nova tentativa pendente'
    if analise.estado == 'comparando':
        return 'Análise em andamento · comparando com o briefing'
    if analise.estado == 'examinando':
        return 'Análise em andamento · examinando os arquivos'
    return 'Entrega recebida · na fila de análise'
