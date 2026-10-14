"""Leitura para rascunhos do admin; não edita ou publica no fórum."""
from datetime import timedelta
import hashlib
import re
from django.utils import timezone
from ninja import Router
from apps.forum.models import Topico, Mensagem, OutboxEvent
from .editor import _so_admin

router = Router()


def _limpar(texto):
    texto = re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '[e-mail omitido]', texto or '')
    texto = re.sub(r'\b(?:\+?\d[ ().-]*?){10,19}\b', '[número omitido]', texto)
    texto = re.sub(r'(?i)\b(?:bearer\s+\S+|sk-[\w-]+|(?:senha|password|token|api[_ -]?key|secret)\s*[:=]\s*\S+)', '[segredo omitido]', texto)
    return re.sub(r'https?://[^\s<>]+', '[endereço no fio de origem]', texto)[:6000]


@router.get('/procedimentos/casos')
def casos(request, site_id: str, pagina: int = 1):
    _so_admin(request)
    inicio = timezone.now() - timedelta(days=14)
    # O evento conserva a autoridade da marca e o site. Ausência não é aprovação.
    eventos = OutboxEvent.objects.filter(event='forum.resposta-aceita', occurred_at__gte=inicio,
        payload__site_id=site_id, payload__marcada_por='professor')
    ids = [int(i) for i in eventos.values_list('payload__topico_id', flat=True) if str(i).isdigit()]
    base = Topico.objects.filter(pk__in=ids, criado_em__gte=inicio,
        estado=Topico.Estado.PUBLICADO, publicado_pela_escola=False,
        resposta_aceita__isnull=False, resposta_aceita__removida_em__isnull=True).select_related('resposta_aceita')
    pagina = max(1, pagina)
    total = base.count()
    itens = []
    for t in base.order_by('pk')[(pagina-1)*100:pagina*100]:
        # Uma marca antiga noutra resposta não valida a atual.
        if not eventos.filter(payload__topico_id=str(t.pk), payload__mensagem_id=str(t.resposta_aceita_id)).exists():
            continue
        pergunta = Mensagem.objects.filter(topico=t, removida_em__isnull=True).order_by('pk').first()
        if not pergunta:
            continue
        itens.append({'chave': str(t.pk), 'pessoa': hashlib.sha256(('meshcraft.top:'+str(t.autor_id)).encode()).hexdigest(),
            'titulo': _limpar(t.titulo), 'sintoma': _limpar(pergunta.texto),
            'solucao': _limpar(t.resposta_aceita.texto), 'confirmada': True,
            'ocorrida_em': t.criado_em.isoformat(), 'contexto': '',
            'referencia': f'https://meshcraft.top/forum/t/{t.pk}', 'publico': 'alunos'})
    return {'itens': itens, 'total': total, 'paginas': max(1, (total+99)//100), 'pagina': pagina}
