"""Rascunhos sustentados por dados existentes, nunca operações ou promessas."""
from django.utils import timezone
from .models import AgendaDoProduto


def preparar(conversa, contexto=None):
    from . import service
    contexto = contexto or {}
    ultima = conversa.mensagens.filter(autor='aluno').last()
    if not ultima:
        return {'resposta': '', 'fixo': True, 'lote': False, 'fontes': []}
    tipo = conversa.tipo
    produto = (conversa.interesse or {}).get('produto_id', '')
    resposta, lote, fontes, coberto = '', False, [], False
    if tipo == 16:
        resposta, lote, coberto = 'Olá! Como posso ajudar?', True, True
    elif tipo == 1:
        agenda = AgendaDoProduto.objects.filter(site_id=conversa.site_id, produto_id=produto).first() if produto else None
        if agenda and agenda.inicio:
            inicio = timezone.localtime(agenda.inicio)
            resposta = f'{agenda.produto_nome}: início em {inicio:%d/%m/%Y}, às {inicio:%H:%M} (horário de Brasília).'
            if agenda.detalhes:
                resposta += '\n\n' + agenda.detalhes
            lote, coberto = True, True
        else:
            resposta = 'Sobre qual evento, curso ou turma você quer confirmar a data?'
    elif tipo == 5:
        compras = [c for c in (contexto.get('crm') or {}).get('compras', []) if produto and produto in c.get('produtos', [])]
        if len(compras) == 1:
            resposta = 'A situação registrada para sua compra de ' + (conversa.interesse.get('nome') or 'este produto') + ' é: ' + str(compras[0].get('situacao') or 'não informada') + '.'
            coberto = True
        else:
            resposta = 'De qual produto é a compra que você quer consultar? Não envie dados de cartão ou documentos pelo chat.'
    if not resposta and tipo not in (13, 14, 15) and conversa.cor != 'vermelho':
        textos, _ = service.fontes_da_base(ultima.texto, conversa.site_id, conversa.assunto_id, conversa.curso)
        from .escala import normalizar
        exata = next((t for t in textos if normalizar(t.pergunta) == normalizar(ultima.texto)), None)
        if exata:
            resposta = exata.resposta
            fontes = [{'id': str(exata.pk), 'revisao': exata.revisao}]
            lote = tipo in (2, 3, 4, 7, 9)
            coberto = True
    if not resposta and tipo == 9 and (contexto.get('faixa') or {}).get('nome'):
        resposta = ('Sua faixa registrada é ' + str(contexto['faixa']['nome']) + '. '
            'A progressão segue os requisitos da sua trilha. Qual etapa você quer conferir?')
        coberto = True
    if not resposta:
        resposta = {
            2: 'O que aparece ao tentar entrar na sua conta? Descreva a mensagem, sem enviar senha ou códigos de acesso.',
            3: 'Qual é o curso e a aula que você está procurando?',
            4: 'Qual acesso você está aguardando e por qual canal esperava recebê-lo?',
            6: 'Qual produto você está tentando comprar? Vou conferir o caminho de compra que já existe.',
            7: 'A aprovação do cartão é decidida pelo provedor do pagamento. Qual mensagem apareceu? Não envie dados do cartão.',
            8: 'Qual produto você comprou e qual mensagem aparece ao tentar acessá-lo? Vou conferir a compra e o acesso.',
            9: 'Qual etapa da sua faixa você está tentando concluir? Descreva o que aparece na sua trilha.',
            10: 'Qual etapa você está tentando fazer e o que aconteceu ao tentar? Descreva a mensagem ou o resultado em texto.',
            11: 'Qual produto ou assunto você quer conhecer?',
            12: 'Em qual página ocorreu o problema e qual mensagem apareceu? Descreva em texto, sem enviar senhas ou códigos.',
            13: 'Sobre qual compra é o pedido de reembolso? A equipe vai conferir o caso antes de informar o próximo passo.',
            14: 'Descreva o que aconteceu com a compra para que a equipe possa conferir o caso.',
            15: 'Qual solicitação você deseja fazer sobre seus dados pessoais? Não envie documentos pelo chat.',
        }.get(tipo, 'Conte um pouco mais sobre o que você precisa para que a equipe possa ajudar.')
    modelo = resposta
    if conversa.nome and tipo != 16:
        from apps.core.templatetags.nomes_admin import primeiro_nome
        resposta = primeiro_nome(conversa.nome) + ',\n\n' + resposta
    return {'resposta': resposta[:6000], 'modelo': modelo, 'fixo': True, 'coberto': coberto, 'lote': lote and conversa.cor != 'vermelho',
        'fontes': fontes, 'mensagem_id': ultima.pk, 'produto_id': produto}
