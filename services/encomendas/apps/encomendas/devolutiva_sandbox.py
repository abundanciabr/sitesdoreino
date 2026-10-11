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
        if not p.entregas.filter(pk=entrega.pk).exists():
            return None  # A pessoa apagou este teste enquanto a análise terminava.
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
    if entrega.teste_mantenedor:
        return registrar(entrega, 'recebimento',
            f'Recebemos a versão {entrega.versao} como teste do mantenedor. A análise automática entrou na fila. '
            'Este envio não substitui a entrega do aluno, não altera sua faixa nem concede XP.')
    return registrar(entrega, 'recebimento',
        f'Recebemos a versão {entrega.versao} e seus arquivos. A análise automática entrou na fila. '
        'O resultado aparecerá neste trabalho e você receberá uma resposta nesta conversa. '
        'O horário da entrega está registrado. A realização será reconhecida após a avaliação automática terminar. '
        'Faixa e bônus de XP seguem a sequência da jornada, uma única vez. A fila não altera o horário de entrega.')


def conclusao(analise):
    avaliacao = analise.resultado.get('avaliacao') or {}
    titulos = {'atende': 'atende ao briefing', 'precisa_ajustes': 'precisa de ajustes',
               'inconclusiva': 'inconclusiva'}
    resultado = titulos.get(avaliacao.get('resultado'), 'comparação concluída')
    teste = analise.entrega.teste_mantenedor
    texto = (f'Avaliação automática da versão {analise.entrega.versao}: {resultado}. '
             + str(avaliacao.get('justificativa') or '')).strip()
    pendencias = lacunas(analise.resultado)
    if pendencias:
        texto += ('\nLeitura incompleta. Não foi possível examinar integralmente:\n'
                  + '\n'.join('- ' + nome for nome in pendencias[:12])
                  + '\nArquivos não examinados não foram considerados aprovados. '
                  'Uma falha do leitor não é uma reprovação do trabalho.')
    if teste:
        texto += ('\nTeste do mantenedor: este resultado se refere às amostras de teste, '
                  'não ao trabalho original do aluno. Não altera sua faixa nem concede XP.')
    else:
        texto += ('\nEste é o resultado da avaliação, sem aprovação manual posterior. '
                  'Se discordar, peça ajuda ao suporte. Confira as evidências no histórico. '
                  'Você pode corrigir os pontos indicados e enviar uma nova versão quando necessário. '
                  'O histórico e o horário do envio permanecem preservados. '
                  'A faixa e o bônus de XP chegam somente quando a análise reconhece a realização. '
                  'Os arquivos permanecem preservados.')
    revisao = len(analise.historico)
    return registrar(analise.entrega, f'resultado-automatico-v2-{revisao}', texto)


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
        avaliacao = analise.resultado.get('avaliacao') or {}
        if lacunas(analise.resultado) and not avaliacao:
            return 'Análise incompleta · confira os arquivos e envie uma nova versão'
        texto = {'atende': 'Avaliação automática: atende ao briefing',
                'precisa_ajustes': 'Avaliação automática: precisa de ajustes',
                'inconclusiva': 'Avaliação automática inconclusiva · confira as evidências'}.get(
                    avaliacao.get('resultado'), 'Análise automática concluída · confira o resultado')
        return texto + (' · leitura incompleta' if lacunas(analise.resultado) else '')
    if analise.estado in ('falha', 'falha_ia'):
        return 'Análise indisponível · arquivos recebidos e nova tentativa pendente'
    if analise.estado == 'comparando':
        return 'Análise em andamento · comparando com o briefing'
    if analise.estado == 'examinando':
        return 'Análise em andamento · examinando os arquivos'
    return 'Entrega recebida · na fila de análise'
