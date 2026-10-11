"""Escolhas privadas e revisáveis e requisitos do começo da jornada."""
import json

from django.utils import timezone
from django.urls import reverse

from .models import AnexoDaJornada, JornadaPessoal

MOTIVOS = (
    ('freelancer', 'Criar peças 3D para clientes', 'Experimente um objeto simples a partir de um pedido. Observe forma, proporção e organização dos arquivos.'),
    ('ugc', 'Criar meus próprios itens UGC', 'Comece com um acessório simples e escolha um detalhe que expresse seu estilo. Guarde uma imagem da primeira versão.'),
    ('jogo', 'Criar a parte visual do meu jogo', 'Escolha um objeto pequeno que seu cenário precisa. Modele primeiro a forma principal e depois acrescente um detalhe.'),
    ('estudio', 'Preparar meu futuro estúdio', 'Conclua uma peça pequena e organize as partes e os arquivos. Imagine como explicaria sua criação a um colaborador.'),
    ('descobrir', 'Experimentar e descobrir meu caminho', 'Escolha um objeto que desperte sua curiosidade. Faça uma versão simples e observe qual parte mais gostou de criar.'),
    ('outro', 'Tenho outro motivo', 'Escolha uma peça pequena relacionada à sua ideia. Comece pela forma principal e peça ajuda sobre uma dificuldade por vez.'),
)

COMPROMISSO_CURSO = (
    'Eu assumo o compromisso de concluir todas as etapas deste curso.\n'
    'Vou assistir às aulas, praticar e terminar os trabalhos.\n'
    'Vou enfrentar os desafios, buscar ajuda e seguir em frente.\n'
    'Vou transformar o motivo que escolhi em ação até concluir o curso.'
)


SONHOS = (
    ('autonomo', 'Trabalhar por conta própria'),
    ('tempo_livre', 'Ter mais tempo livre'),
    ('pc_gamer', 'Comprar um PC Gamer'),
    ('notebook', 'Comprar um Notebook'),
    ('iphone', 'Comprar um iPhone'),
    ('celular', 'Comprar um Celular'),
    ('carro_moto', 'Comprar um carro/moto'),
    ('qualidade_vida', 'Usufruir de qualidade de vida'),
    ('renda_extra', 'Ganhar uma renda extra'),
    ('ajudar_pessoas', 'Ajudar pessoas'),
    ('seguranca_familia', 'Garantir mais segurança para você e sua família'),
    ('ajudar_pais', 'Ajudar meus pais'),
    ('faculdade', 'Pagar a faculdade'),
    ('jogo_roblox', 'Criar meu próprio jogo no Roblox'),
    ('colecao_ugc', 'Lançar minha coleção de itens UGC'),
    ('estudio', 'Montar meu próprio estúdio de criação'),
    ('casa', 'Trabalhar de casa'),
    ('internacional', 'Trabalhar com pessoas de outros países'),
    ('viagens', 'Viajar e conhecer novos lugares'),
    ('espaco_criacao', 'Ter meu próprio espaço para estudar e criar'),
    ('independencia', 'Conquistar minha independência financeira'),
    ('economizar', 'Guardar dinheiro para realizar meus planos'),
    ('cursos', 'Investir em cursos e aprender novas habilidades'),
    ('portfolio', 'Criar um portfólio de que eu me orgulhe'),
    ('equipe_jogos', 'Participar de uma equipe de criação de jogos'),
)


def texto(dados, chave, limite):
    valor = str(dados.get(chave, '')).strip()
    if len(valor) > limite:
        raise ValueError(f'Use até {limite} caracteres neste campo.')
    return valor


def salvar_inicio(jornada, dados):
    try:
        revisao = int(dados.get('revisao', '-1'))
    except (ValueError, TypeError):
        raise ValueError('Reabra a página antes de salvar.') from None
    if revisao != jornada.revisao:
        raise ValueError('Seu registro mudou em outra aba. Suas respostas continuam na tela; confira a versão salva antes de tentar novamente.')
    inicio = dict(jornada.inicio)
    if dados['acao'] == 'inicio-motivo':
        motivo = texto(dados, 'motivo', 20)
        if motivo and motivo not in {m[0] for m in MOTIVOS}:
            raise ValueError('Escolha um dos caminhos ou escreva seu próprio motivo.')
        from .bonus_inicio import recebido

        ja_concluido = recebido(jornada.pessoa_id, jornada.site_id, 1) > 0
        mudou = inicio.get('motivo') != motivo
        # Revisar uma escolha não desfaz a tarefa cujo XP já foi recebido.
        if dados.get('concluir') == 'sim' or ja_concluido:
            if not motivo:
                raise ValueError('Escolha seu motivo para concluir esta etapa.')
            inicio['motivo_rascunho'] = False
        elif mudou or not inicio.get('motivo'):
            inicio['motivo_rascunho'] = True
        inicio.update(motivo=motivo, motivo_pessoal=texto(dados, 'motivo_pessoal', 280))
        # Clientes anteriores não apagam os novos campos privados.
        if 'motivo_outro' in dados:
            inicio['motivo_outro'] = texto(dados, 'motivo_outro', 280)
        if 'motivo_sonhos' in dados:
            try:
                sonhos = json.loads(texto(dados, 'motivo_sonhos', 2000))
            except (ValueError, TypeError):
                raise ValueError('Confira suas escolhas de futuro antes de salvar.') from None
            opcoes = {valor for valor, nome in SONHOS}
            if not isinstance(sonhos, list) or any(not isinstance(valor, str) or valor not in opcoes for valor in sonhos):
                raise ValueError('Escolha os sonhos na lista apresentada.')
            inicio['motivo_sonhos'] = list(dict.fromkeys(sonhos))
        if dados.get('motivo_etapa') in ('1', '2', '3'):
            inicio['motivo_etapa'] = int(dados['motivo_etapa'])
    elif dados['acao'] == 'inicio-compromisso':
        if not etapas_inicio(jornada.pessoa_id, jornada.site_id, jornada)[1]['liberada']:
            raise ValueError('Conclua seu motivo e receba o XP antes de assumir o compromisso.')
        if dados.get('compromisso_etapa') in ('1', '2'):
            inicio['compromisso_etapa'] = int(dados['compromisso_etapa'])
        if dados.get('assumir') == 'sim':
            # O novo compromisso não substitui o plano e as respostas anteriores.
            if not inicio.get('compromisso_curso_em'):
                inicio['compromisso_curso'] = COMPROMISSO_CURSO
                inicio['compromisso_curso_em'] = timezone.now().isoformat()
                inicio['compromisso_motivos'] = {chave: inicio.get(chave) for chave in
                    ('motivo', 'motivo_outro', 'motivo_pessoal', 'motivo_sonhos')}
            inicio['compromisso_etapa'] = 3
    elif dados['acao'] == 'inicio-plano':
        if not etapas_inicio(jornada.pessoa_id, jornada.site_id, jornada)[1]['liberada']:
            raise ValueError('Conclua seu motivo e receba o XP antes de definir o objetivo.')
        plano = {chave: texto(dados, chave, limite) for chave, limite in (
            ('sonho', 500), ('objetivo', 280), ('quando', 160),
            ('obstaculo', 280), ('plano_b', 280), ('compromisso', 1200),
        )}
        mudou = any(inicio.get(k, '') != plano[k] for k in ('objetivo', 'compromisso'))
        if mudou:
            inicio['confirmado_em'] = None
        if dados.get('assumir') == 'sim':
            if not plano['objetivo'] or not plano['compromisso']:
                raise ValueError('Escreva seu próximo objetivo e seu compromisso. Você também pode salvar um rascunho.')
            inicio['confirmado_em'] = timezone.now().isoformat()
        apoio = dados.get('apoio', jornada.apoio)
        from .jornada import APOIOS
        if apoio not in APOIOS:
            raise ValueError('Escolha como quer praticar agora.')
        jornada.apoio = apoio
        inicio.update(plano)
    elif dados['acao'] == 'inicio-item':
        if not etapas_inicio(jornada.pessoa_id, jornada.site_id, jornada)[2]['liberada']:
            raise ValueError('Assuma seu compromisso e receba o XP antes de criar o item.')
        inicio.setdefault('item_pronto_em', timezone.now().isoformat())
    else:
        raise ValueError('Escolha uma etapa do começo da jornada.')
    inicio['salvo_em'] = timezone.now().isoformat()
    jornada.inicio = inicio
    jornada.revisao += 1
    jornada.save(update_fields=['inicio', 'apoio', 'revisao', 'atualizada_em'])


def para_tela(jornada):
    inicio = dict(jornada.inicio) if jornada else {}
    motivo = next((m for m in MOTIVOS if m[0] == inicio.get('motivo')), MOTIVOS[4])
    return {**inicio, 'motivos': [{'valor': m[0], 'nome': m[1]} for m in MOTIVOS],
            'sonhos_opcoes': [{'valor': valor, 'nome': nome} for valor, nome in SONHOS],
            'pratica': motivo[2], 'apoio': jornada.apoio if jornada else 'guiado',
            'item_pronto': bool(inicio.get('item_pronto_em') or (jornada and jornada.declaracoes.get('2'))),
            'etapas': etapas_inicio(jornada.pessoa_id, jornada.site_id, jornada) if jornada else etapas_inicio(None, None, None)}


def requisitos_branca(jornada, tem_anexo):
    """Dados obrigatórios do começo; a jornada aplica a progressão sequencial."""
    inicio = jornada.inicio if jornada else {}
    preenchido = lambda chave: bool(str(inicio.get(chave) or '').strip())
    motivo_concluido = preenchido('motivo') and not bool(inicio.get('motivo_rascunho'))
    if preenchido('motivo') and inicio.get('motivo_rascunho') and jornada:
        from .bonus_inicio import recebido
        # Reconhece revisões antigas afetadas sem reescrever respostas ou o ledger.
        motivo_concluido = recebido(jornada.pessoa_id, jornada.site_id, 1) > 0
    from .bonus_inicio import recebido
    compromisso_concluido = bool(inicio.get('compromisso_curso_em') or
        preenchido('compromisso') and inicio.get('confirmado_em') or
        jornada and recebido(jornada.pessoa_id, jornada.site_id, 2) > 0)
    return {
        'motivo': motivo_concluido,
        'objetivo': preenchido('objetivo') or compromisso_concluido,
        'compromisso': compromisso_concluido,
        'item': bool(inicio.get('item_pronto_em') or (jornada and jornada.declaracoes.get('2'))),
        'envio': bool(tem_anexo),
    }


def etapas_inicio(pessoa_id, site_id, jornada, tem_anexo=None):
    """Quatro tarefas sequenciais: dados privados e XP definitivo de cada gesto."""
    from .bonus_inicio import recebido

    if tem_anexo is None:
        tem_anexo = bool(jornada and AnexoDaJornada.objects.filter(
            pessoa_id=pessoa_id, site_id=site_id, passo=2,
        ).exists())
    requisitos = requisitos_branca(jornada, tem_anexo)
    inicio = jornada.inicio if jornada else {}
    declarada = bool(jornada and jornada.declaracoes.get('2') and
                     jornada.confirmacoes_sequenciais.get('2'))
    validas = (requisitos['motivo'],
               requisitos['objetivo'] and requisitos['compromisso'],
               requisitos['item'], requisitos['envio'] and declarada)
    em_andamento = (bool(inicio.get('motivo')),
                    any(inicio.get(k) for k in ('sonho', 'objetivo', 'compromisso', 'compromisso_etapa')),
                    requisitos['item'], bool(tem_anexo or (jornada and jornada.declaracoes.get('2'))))
    etapas = []
    anteriores_concluidas = True
    for indice, (valida, iniciada) in enumerate(zip(validas, em_andamento), start=1):
        xp = recebido(pessoa_id, site_id, indice) if jornada else 0
        concluida = bool(anteriores_concluidas and valida and xp > 0)
        bloqueada = not anteriores_concluidas
        estado = ('pendente' if bloqueada else 'concluido' if concluida else
                  'andamento' if iniciada else 'pendente')
        etapas.append({'etapa': indice, 'concluida': concluida,
                       'liberada': not bloqueada, 'bloqueada': bloqueada,
                       'dados_validos': bool(valida), 'xp_recebido': xp,
                       'estado': estado})
        anteriores_concluidas = concluida
    return etapas


def resumo_inicio(pessoa_id, site_id, faixas):
    """Retomada da primeira das quatro etapas ainda pendente."""
    jornada = JornadaPessoal.objects.filter(pessoa_id=pessoa_id, site_id=site_id).first()
    inicio = jornada.inicio if jornada else {}
    arquivos = AnexoDaJornada.objects.filter(pessoa_id=pessoa_id, site_id=site_id, passo=2).count()
    etapas = etapas_inicio(pessoa_id, site_id, jornada, arquivos > 0)
    concluido = etapas[3]['concluida']
    passo = next((etapa['etapa'] for etapa in etapas if not etapa['concluida']), 1)
    nome_rota = {1: 'inicio-motivo', 2: 'inicio-objetivo', 3: 'inicio-item', 4: 'inicio-envio'}[passo]
    titulo = {1: 'Meu motivo', 2: 'Meu compromisso', 3: 'Meu primeiro item 3D', 4: 'Enviar meu 3D'}[passo]
    return {
        'passo': passo,
        'titulo': titulo,
        'url': reverse(nome_rota),
        'iniciado': bool(inicio or arquivos or (jornada and jornada.declaracoes.get('2'))),
        'concluido': concluido,
        'quantidade_arquivos': arquivos,
    }
