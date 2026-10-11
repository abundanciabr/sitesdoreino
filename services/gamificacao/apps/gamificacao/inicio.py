"""Escolhas privadas e revisáveis e requisitos do começo da jornada."""
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
        inicio.update(motivo=motivo, motivo_pessoal=texto(dados, 'motivo_pessoal', 280))
    else:
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
    inicio['salvo_em'] = timezone.now().isoformat()
    jornada.inicio = inicio
    jornada.revisao += 1
    jornada.save(update_fields=['inicio', 'apoio', 'revisao', 'atualizada_em'])


def para_tela(jornada):
    inicio = dict(jornada.inicio) if jornada else {}
    motivo = next((m for m in MOTIVOS if m[0] == inicio.get('motivo')), MOTIVOS[4])
    return {**inicio, 'motivos': [{'valor': m[0], 'nome': m[1]} for m in MOTIVOS],
            'pratica': motivo[2], 'apoio': jornada.apoio if jornada else 'guiado'}


def requisitos_branca(jornada, tem_anexo):
    """Dados obrigatórios do começo; a jornada aplica a progressão sequencial."""
    inicio = jornada.inicio if jornada else {}
    preenchido = lambda chave: bool(str(inicio.get(chave) or '').strip())
    return {
        'motivo': preenchido('motivo'),
        'objetivo': preenchido('objetivo'),
        'compromisso': preenchido('compromisso') and bool(inicio.get('confirmado_em')),
        'item': bool(tem_anexo),
    }


def resumo_inicio(pessoa_id, site_id, faixas):
    """Retomada dos três passos a partir dos registros privados já existentes."""
    jornada = JornadaPessoal.objects.filter(pessoa_id=pessoa_id, site_id=site_id).first()
    inicio = jornada.inicio if jornada else {}
    motivo = bool(inicio.get('motivo'))
    confirmado = bool(inicio.get('confirmado_em'))
    arquivos = AnexoDaJornada.objects.filter(
        pessoa_id=pessoa_id, site_id=site_id, passo=2,
    ).count()
    primeiro_item = any(
        etapa['ordem'] == 2 and etapa['alcancada'] for etapa in faixas['lista']
    )
    concluido = motivo and confirmado and primeiro_item
    passo = 1 if concluido or not motivo else 2 if not confirmado else 3
    nome_rota = {1: 'inicio-motivo', 2: 'inicio-objetivo', 3: 'inicio-item'}[passo]
    titulo = {1: 'Meu motivo', 2: 'Meu objetivo e compromisso', 3: 'Meu primeiro item 3D'}[passo]
    return {
        'passo': passo,
        'titulo': titulo,
        'url': reverse(nome_rota),
        'iniciado': bool(inicio or arquivos or primeiro_item),
        'concluido': concluido,
        'quantidade_arquivos': arquivos,
    }
