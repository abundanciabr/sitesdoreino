"""Objeções reais minimizadas; originais nunca entram no repositório."""
import hashlib
import re
import uuid
from django.utils import timezone
from apps.core.models import RascunhoDeConfiguracao
from apps.core.clients import LeadsClient, CursosClient
from apps.core.crm_conversas import ConversasClient, OK
from apps.atendimento.models import Mensagem
from .banca_assinatura import assinatura

INDICIOS = re.compile(r'\?|não|nao|dúvida|duvida|medo|difícil|dificil|preço|preco|caro|tempo|dinheiro|renda|reembols|devol|cancel|garant|consegu|compr|mercado|vender|suporte', re.I)
REEMBOLSO = re.compile(r'reembols|devolu[çc]|cancel.*(?:compra|curso)|estorno', re.I)
VERSAO_SELECAO = 'banca-fontes-v2'
TESTE = re.compile(r'\b(?:ensaio|fict[ií]ci[oa]|teste t[eé]cnico|teste autorizado|confer[eê]ncia t[eé]cnica|apenas uma confer[eê]ncia|segunda rodada|test[-_]|teste[-_])', re.I)
MENU_AUTOMATICO = re.compile(r'escolha (?:abaixo|uma op[çc][aã]o)|lista de assuntos|toque em (?:tirar d[uú]vidas|escolher assunto)|vamos testar agora', re.I)


def parece_teste(texto, nomes=(), origem=''):
    return bool(TESTE.search(str(texto) + ' ' + str(origem)) or any(
        re.search(r'\b(?:teste|test|ensaio|admin|rob[oô])\b', str(n), re.I) for n in nomes if n))


def anonimizar(texto, nomes=()):
    texto = str(texto or '')
    texto = re.sub(r'https?://\S+|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '[contato omitido]', texto)
    for nome in sorted(set(nomes), key=len, reverse=True):
        if nome and len(nome.strip()) > 2:
            texto = re.sub(re.escape(nome.strip()), '[pessoa]', texto, flags=re.I)
            for parte in nome.split():
                if len(parte) > 2:
                    texto = re.sub(r'\b' + re.escape(parte) + r'\b', '[pessoa]', texto, flags=re.I)
    texto = re.sub(r'\b(?:\d[ .()/-]*){8,}\b', '[identificador omitido]', texto)
    texto = re.sub(r'(?i)\b(?:bearer\s+\S+|sk-[\w-]+|senha\s*[:=]\s*\S+|token\s*[:=]\s*\S+)', '[segredo omitido]', texto)
    return texto.strip()[:1200]


def registrar(site_id, fonte, texto, referencia, data='', produto=''):
    if fonte not in {'reembolso', 'suporte', 'quiz', 'comentário do lançamento'}:
        raise ValueError('Escolha a origem do relato real.')
    if not 10 <= len(texto.strip()) <= 1200 or not referencia.strip():
        raise ValueError('Informe o trecho real e uma referência da origem, sem dados pessoais.')
    if parece_teste(texto) or MENU_AUTOMATICO.search(texto):
        raise ValueError('Testes e menus automáticos não são evidências de compradores.')
    registro = {'id': uuid.uuid4().hex[:20], 'fonte': fonte, 'texto': anonimizar(texto),
                'referencia': anonimizar(referencia)[:200], 'data': data,
                'produto': anonimizar(produto)[:200], 'idioma': 'pt-br',
                'tema': 'reembolso' if fonte == 'reembolso' else 'objeção ou pergunta'}
    return RascunhoDeConfiguracao.objects.create(tipo='banca_evidencia', site_id=str(site_id),
        alvo=registro['id'], conteudo=registro)


def coletar(site_id):
    itens, cobertura = [], []
    def incluir(fonte, referencia, texto, data='', produto='', nomes=()):
        if parece_teste(texto, nomes) or MENU_AUTOMATICO.search(str(texto or '')):
            return
        texto = anonimizar(texto, nomes)
        if not texto or not INDICIOS.search(texto):
            return
        item = {'id': hashlib.sha256((fonte + ':' + str(referencia)).encode()).hexdigest()[:20],
                'fonte': fonte, 'texto': texto, 'data': str(data),
                'produto': anonimizar(produto, nomes), 'idioma': 'não identificado',
                'tema': 'reembolso' if REEMBOLSO.search(texto) else 'objeção ou pergunta'}
        itens.append(item)
    try:
        consulta = list(Mensagem.objects.filter(conversa__site_id=site_id, autor='aluno')
                        .select_related('conversa').order_by('-id')[:500])
        for m in consulta:
            if parece_teste(m.texto, (m.nome, m.conversa.nome), m.conversa.origem_conversa):
                continue
            incluir('suporte', m.pk, m.texto, m.criada_em.isoformat(), m.conversa.curso,
                    (m.nome, m.conversa.nome))
        cobertura.append({'fonte': 'suporte', 'estado': 'consultada', 'examinados': len(consulta),
                          'limite': '500 mensagens recentes, não o histórico inteiro'})
    except Exception as erro:
        cobertura.append({'fonte': 'suporte', 'estado': 'indisponível', 'motivo': type(erro).__name__})
    try:
        cliente = ConversasClient()
        estado, lista = cliente.listar(site_id, pagina=1)
        if estado != OK:
            raise ValueError('fonte indisponível')
        mensagens, falhas = 0, 0
        for c in lista['itens'][:30]:
            estado, dados = cliente.mensagens(site_id, c['id'], limite=50)
            if estado != OK:
                falhas += 1
                continue
            for m in dados['mensagens']:
                if m.get('autor') != 'pessoa' or m.get('direcao') != 'entrada':
                    continue
                mensagens += 1
                incluir('mensagens do lançamento', m.get('id'), m.get('texto'), m.get('ocorrida_em', ''),
                        nomes=(c.get('nome', ''), m.get('autor_nome', '')))
        cobertura.append({'fonte': 'mensagens do lançamento', 'estado': 'parcial' if falhas else 'consultada',
                          'examinados': mensagens, 'falhas': falhas, 'limite': 'até 30 conversas e 50 mensagens por conversa; origem de lançamento nem sempre identificada'})
    except Exception as erro:
        cobertura.append({'fonte': 'mensagens do lançamento', 'estado': 'indisponível', 'motivo': type(erro).__name__})
    try:
        cliente = LeadsClient()
        estado, lista = cliente.listar(site_id=site_id, origem='quiz', testes='ocultar', por_pagina=50)
        if estado != cliente.OK:
            raise ValueError('fonte indisponível')
        examinados, falhas = 0, 0
        for lead in lista['itens']:
            estado, ficha = cliente.ficha(lead['id'])
            if estado != cliente.OK or str(ficha.get('site_id')) != str(site_id):
                falhas += 1
                continue
            for quiz in ficha.get('quizzes', []):
                for i, resposta in enumerate(quiz.get('respostas', [])):
                    textos = [r.get('texto', '') for r in resposta.get('respostas', []) if isinstance(r, dict)]
                    if resposta.get('valor_livre'):
                        textos.append(resposta['valor_livre'])
                    for j, texto in enumerate(textos):
                        examinados += 1
                        incluir('quiz', f"{quiz.get('id')}:{i}:{j}", texto, quiz.get('atualizado_em', ''),
                                quiz.get('quiz_slug', ''), (lead.get('nome', ''), ficha.get('nome', '')))
        cobertura.append({'fonte': 'quiz', 'estado': 'parcial' if falhas else 'consultada',
                          'examinados': examinados, 'falhas': falhas, 'limite': '50 contatos recentes; opções escolhidas não são depoimentos livres'})
    except Exception as erro:
        cobertura.append({'fonte': 'quiz', 'estado': 'indisponível', 'motivo': type(erro).__name__})
    try:
        cliente = CursosClient()
        estado, dados = cliente.comentarios_das_aulas(site_id)
        if estado != cliente.OK:
            raise ValueError('fonte indisponível')
        for m in dados.get('itens', []):
            incluir('comentários de aulas', m.get('id'), m.get('texto'), m.get('criado_em', ''),
                    nomes=(m.get('autor_nome', ''), m.get('nome', '')))
        cobertura.append({'fonte': 'comentários de aulas', 'estado': 'consultada',
                          'examinados': len(dados.get('itens', [])), 'limite': 'primeira página; não são comentários de campanha'})
    except Exception as erro:
        cobertura.append({'fonte': 'comentários de aulas', 'estado': 'indisponível', 'motivo': type(erro).__name__})
    manuais = list(RascunhoDeConfiguracao.objects.filter(tipo='banca_evidencia', site_id=str(site_id)).order_by('-pk')[:250])
    itens.extend(r.conteudo for r in manuais)
    cobertura.append({'fonte': 'relatos registrados no painel', 'estado': 'consultada',
                      'examinados': len(manuais), 'limite': 'Trechos reais informados pela administração; autenticidade depende da origem registrada.'})
    cobertura.append({'fonte': 'reembolsos', 'estado': 'mensagens identificadas nas fontes acima',
                      'examinados': sum(i['tema'] == 'reembolso' for i in itens),
                      'limite': 'não inclui razões de estorno do provedor nem todas as fontes externas'})
    unicos = {}
    for item in itens:
        chave = assinatura(item['texto'].casefold())
        if chave not in unicos:
            unicos[chave] = {**item, 'ocorrencias': 1, 'referencias': [item['id']]}
        else:
            unicos[chave]['ocorrencias'] += 1
            unicos[chave]['referencias'].append(item['id'])
    corpus = {'coletado_em': timezone.now().isoformat(), 'itens': list(unicos.values())[:250],
              'cobertura': cobertura, 'limite': 'Amostra de mensagens, não estimativa de prevalência no público.'}
    corpus['selecao'] = 'Somente entradas da pessoa; testes identificáveis e textos de menus excluídos. A ausência de marcador não comprova a autenticidade de uma mensagem.'
    corpus['selecao_versao'] = VERSAO_SELECAO
    corpus['digest'] = assinatura(corpus)
    registro = RascunhoDeConfiguracao.objects.create(tipo='banca_corpus', site_id=str(site_id),
                  alvo=str(uuid.uuid4()), conteudo=corpus)
    return registro


def ultimo(site_id):
    return RascunhoDeConfiguracao.objects.filter(tipo='banca_corpus', site_id=str(site_id)).order_by('-pk').first()
