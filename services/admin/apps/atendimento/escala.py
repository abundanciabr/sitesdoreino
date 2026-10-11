"""Classificação e medição do atendimento; a cor nunca autoriza um envio."""
import re
import unicodedata
from contextvars import ContextVar
from datetime import timedelta

from django.core import signing
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import AgendaDoProduto, Configuracao, Conversa, Reabertura
from django.db.models.signals import post_save
from django.dispatch import receiver

_chamada = ContextVar('consumo_atendimento', default=None)


@receiver(post_save, sender='agentes.Consumo', dispatch_uid='atendimento.vincular_consumo')
def vincular_consumo(sender, instance, created, **kwargs):
    alvo = _chamada.get()
    if created and alvo and instance.origem == 'suporte':
        from .models import ConsumoDoAtendimento
        ConsumoDoAtendimento.objects.get_or_create(consumo=instance,
            defaults={'conversa_id': alvo[0], 'rodada': alvo[1]})


def chamar_modelo(conversa, **kwargs):
    from . import service
    token = _chamada.set((conversa.pk, conversa.rodada))
    try:
        return service.modelo.responder(**kwargs)
    finally:
        _chamada.reset(token)

TIPOS = {0: 'Revisão individual', 1: 'Data de evento', 2: 'Entrar na conta',
    3: 'Encontrar aula', 4: 'Receber acesso', 5: 'Situação do pagamento',
    6: 'Pix vencido', 7: 'Cartão recusado', 8: 'Pago sem acesso',
    9: 'Faixa e conquistas', 10: 'Dúvida técnica', 11: 'Outro produto',
    12: 'Problema no site', 13: 'Reembolso', 14: 'Contestação',
    15: 'Dados pessoais', 16: 'Cumprimento'}


def normalizar(texto):
    return ' '.join(re.findall(r'\w+', ''.join(c for c in unicodedata.normalize(
        'NFKD', str(texto).casefold()) if not unicodedata.combining(c))))


def classificar(conversa, texto):
    """Heurística conservadora, sem modelo pago e com vermelhos prioritários."""
    t = normalizar(texto)
    regras = [
        (15, r'\b(lgpd|dados pessoais|apaguem meus dados|apagar meus dados|excluir meus dados|exclusao dos meus dados)\b'),
        (14, r'\b(procon|processo|processar voces|advogado|contestacao|contestar|chargeback|fraude)\b'),
        (13, r'\b(reembolso|reembolsar|devolucao|devolver|dinheiro de volta|arrependimento|cancelar compra|cancelar a compra)\b'),
        (8, r'\b(paguei|pagamento aprovado|compra aprovada)\b.*\b(nao|sem|cade)\b'),
        (6, r'\bpix\b.*\b(venc|expir|novo|novamente|de novo)'),
        (7, r'\bcartao\b.*\b(recus|negad|nao pass|erro)'),
        (5, r'\b(pagamento|compra)\b.*\b(aprov|passou|situacao|status|confirm)|\b(meu pagamento|minha compra)\b'),
        (4, r'\b(nao recebi|nao chegou)\b.*\b(acesso|email|e mail|whatsapp|link)\b'),
        (2, r'\b(senha|login|entrar na conta|nao consigo entrar|recuperar acesso)\b'),
        (1, r'\b(quando|que dia|qual dia|horario|data|que horas)\b.*\b(comeca|inicio|evento|desafio|aula|curso)|\b(quando comeca|que horas comeca)\b'),
        (12, r'\b(erro|nao abre|nao carrega|travando|fora do ar|video nao)\b'),
        (3, r'\b(onde|cade|encontrar|continuar)\b.*\b(aula|curso|parei)\b'),
        (9, r'\b(faixa|conquista|certificado|xp|sandbox)\b'),
        (11, r'\b(outro curso|curso avancado|comprar curso|comprar outro|outro produto)\b'),
        (10, r'\b(blender|roblox|modelar|modelagem|exportar|textura|malha|mesh|vertices)\b'),
    ]
    tipo = next((n for n, padrao in regras if re.search(padrao, t)), 0)
    if re.fullmatch(r'(oi|ola|bom dia|boa tarde|boa noite|opa|tudo bem)[ !?.]*', t):
        tipo = 16
    cor = 'vermelho' if tipo in (13, 14, 15) else 'amarelo' if tipo in (0, 6, 8, 10, 12) else 'verde'
    if tipo == 1:
        produto = (conversa.interesse or {}).get('produto_id')
        if not produto or not AgendaDoProduto.objects.filter(site_id=conversa.site_id, produto_id=produto, inicio__isnull=False).exists():
            cor = 'amarelo'
    degrau = 'cobrar' if tipo in (13, 14) or re.search(r'\b(gerar|gere|criar|crie|emitir|emita)\b.*\b(pix|cobranca|pagamento)\b', t) else 'mostrar' if tipo in (2, 3, 4, 6, 7, 11, 16) else 'consultar'
    if degrau == 'cobrar':
        cor = 'vermelho'
    humor = 'irritado' if re.search(r'\b(absurdo|ridiculo|irritado|irritada|cansado|cansada|revoltado|revoltada|pessimo|vergonha)\b', t) else 'neutro'
    conversa.tipo, conversa.cor, conversa.degrau, conversa.humor = tipo, cor, degrau, humor
    conversa.classificada_em = timezone.now()
    if cor == 'vermelho' or humor == 'irritado' or conversa.rodada > 1:
        conversa.prioridade = 'alta'
    return conversa


def prioridade_compra(conversa, contexto):
    for compra in (contexto.get('crm') or {}).get('compras') or []:
        data = compra.get('pago_em_iso') or compra.get('pago_em')
        try:
            data = parse_datetime(data) if isinstance(data, str) else data
            if data and timezone.is_naive(data):
                data = timezone.make_aware(data)
            if data and timezone.now() - timedelta(days=7) <= data <= timezone.now():
                conversa.prioridade = 'alta'
                return
        except (TypeError, ValueError):
            continue


def registrar_classificacao(conversa, texto, contexto=None):
    with transaction.atomic():
        atual = Conversa.objects.select_for_update().get(pk=conversa.pk)
        ultima = atual.mensagens.filter(autor='aluno').last()
        if ultima and ultima.texto != texto:
            return
        classificar(atual, texto)
        if contexto:
            prioridade_compra(atual, contexto)
        campos = ('tipo', 'cor', 'degrau', 'humor', 'classificada_em', 'prioridade')
        atual.save(update_fields=campos)
        for campo in campos:
            setattr(conversa, campo, getattr(atual, campo))


def retrato(conversa):
    dados = {k: getattr(conversa, k) for k in ('tipo', 'cor', 'avaliacao', 'resolucao', 'motivo_encerramento')}
    for k in ('primeira_resposta_em', 'encerrada_em', 'resolvida_em'):
        data = getattr(conversa, k)
        dados[k] = data.isoformat() if data else None
    inicio = conversa.rodada_iniciada_em or (conversa.criada_em if conversa.rodada == 1 else None)
    dados['inicio'] = inicio.isoformat() if inicio else None
    return dados


def reabrir(conversa, motivo, quem):
    """Chamada sob o bloqueio da conversa; guarda a rodada anterior uma só vez."""
    if conversa.estado != 'encerrado':
        return False
    agora = timezone.now()
    Reabertura.objects.get_or_create(conversa=conversa, rodada=conversa.rodada,
        defaults={'quando': agora, 'motivo': motivo, 'quem': str(quem)[:100], 'anterior': retrato(conversa)})
    conversa.rodada += 1
    conversa.rodada_iniciada_em = agora
    conversa.primeira_resposta_em = None
    conversa.encerrada_em = None
    conversa.resolvida_em = None
    conversa.resolucao = ''
    conversa.motivo_encerramento = ''
    conversa.avaliacao = None
    conversa.resolvida_robo = False
    conversa.prioridade = 'alta'
    conversa.sugestao = {}
    conversa.estado = 'aguardando'
    return True


def encerrar(conversa, motivo='equipe', resolvido=False):
    agora = timezone.now()
    if conversa.estado != 'encerrado':
        conversa.encerrada_em = agora
        conversa.motivo_encerramento = motivo
    conversa.estado = 'encerrado'
    conversa.processar = False
    if resolvido:
        conversa.resolvida_em = agora
        conversa.resolucao = 'confirmada'


def manutencao():
    """Coleta começa com a implantação; o legado não recebe datas inventadas."""
    agora = timezone.now()
    Configuracao.objects.filter(medicao_iniciada_em__isnull=True).update(medicao_iniciada_em=agora)
    for c in Conversa.objects.filter(classificada_em__isnull=True).exclude(estado='encerrado')[:100]:
        with transaction.atomic():
            c = Conversa.objects.select_for_update().get(pk=c.pk)
            ultima = c.mensagens.filter(autor='aluno').last()
            if ultima:
                registrar_classificacao(c, ultima.texto)
                if c.assunto.modo == 'assistido' and c.mensagens.last().autor == 'aluno':
                    Conversa.objects.filter(pk=c.pk).update(processar=True)
    # A inferência só vale para encerramento humano com resposta e sete dias completos.
    ids = list(Conversa.objects.filter(estado='encerrado', motivo_encerramento='equipe',
        resolvida_em__isnull=True, encerrada_em__lte=agora-timedelta(days=7)).values_list('pk', flat=True)[:200])
    for pk in ids:
        with transaction.atomic():
            c = Conversa.objects.select_for_update().get(pk=pk)
            if c.estado != 'encerrado' or c.resolvida_em or not c.primeira_resposta_em:
                continue
            if c.mensagens.filter(autor='aluno', criada_em__gt=c.encerrada_em).exists():
                continue
            # Outra conversa do mesmo aluno e tipo também conta como retorno.
            if Conversa.objects.filter(site_id=c.site_id, pessoa_id=c.pessoa_id, tipo=c.tipo,
                criada_em__gt=c.encerrada_em, criada_em__lte=c.encerrada_em+timedelta(days=7)).exists():
                continue
            c.resolvida_em = c.encerrada_em + timedelta(days=7)
            c.resolucao = 'sem_retorno_7d'
            c.save(update_fields=['resolvida_em', 'resolucao'])
def token_tempo(quem, site, alvo):
    return signing.dumps({'quem': str(quem), 'site': site, 'alvo': str(alvo),
        'inicio': timezone.now().timestamp()}, salt='suporte-tempo')


def tempo_decorrido(token, quem, site, alvo):
    try:
        d = signing.loads(token, salt='suporte-tempo', max_age=4*3600)
        if (d['quem'], d['site'], d['alvo']) != (str(quem), site, str(alvo)):
            return None
        return round(max(0, timezone.now().timestamp() - d['inicio']), 3)
    except (signing.BadSignature, KeyError, TypeError, ValueError):
        return None
