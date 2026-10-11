"""Exclusão solicitada pelo dono do trabalho após as duas confirmações."""
from datetime import timedelta
import re

from django.db import transaction
from django.utils import timezone

from .sandbox import ErroSandbox
from .sandbox_models import (ParticipacaoSandbox, RespostaSandbox, MensagemSandbox,
    ArquivoSandbox, EntregaSandbox, AjusteSandbox, AnaliseArquivoSandbox, AnaliseEntregaSandbox)


def resumo(trabalho):
    return {
        'entregas': trabalho.entregas.count(),
        'arquivos': trabalho.arquivos.count(),
        'analises': AnaliseEntregaSandbox.objects.filter(entrega__participacao=trabalho).count(),
        'mensagens': trabalho.mensagens.count(),
    }


@transaction.atomic
def limpar(trabalho, prazo_confirmado):
    from apps.core.telas_marketplace import _pasta_privada

    p = ParticipacaoSandbox.objects.select_for_update().get(pk=trabalho.pk, site_id=trabalho.site_id)
    if p.prazo_ate.isoformat() != prazo_confirmado:
        raise ErroSandbox('Este trabalho já foi reiniciado. Abra novamente a confirmação de limpeza.')
    # Não reabre dois trabalhos simultâneos quando a pessoa já iniciou outro.
    outro_ativo = ParticipacaoSandbox.objects.filter(site_id=p.site_id, pessoa_id=p.pessoa_id,
        status__in=['em_producao', 'em_ajuste', 'entregue']).exclude(pk=p.pk).exists()
    if outro_ativo:
        raise ErroSandbox('Conclua o trabalho atual antes de reiniciar este teste.')
    arquivos = list(ArquivoSandbox.objects.filter(participacao=p))
    pasta = _pasta_privada().resolve()
    caminhos = []
    for arquivo in arquivos:
        if not re.fullmatch(r'[a-f0-9]{32}', arquivo.chave):
            raise ErroSandbox('Não foi possível localizar um dos arquivos privados para a limpeza.')
        caminho = pasta / arquivo.chave
        if caminho.is_symlink() or caminho.resolve().parent != pasta:
            raise ErroSandbox('Não foi possível localizar um dos arquivos privados para a limpeza.')
        caminhos.append(caminho)
    RespostaSandbox.objects.filter(participacao=p).delete()
    AnaliseArquivoSandbox.objects.filter(arquivo__participacao=p).delete()
    AnaliseEntregaSandbox.objects.filter(entrega__participacao=p).delete()
    AjusteSandbox.objects.filter(participacao=p).delete()
    ArquivoSandbox.objects.filter(participacao=p).delete()
    EntregaSandbox.objects.filter(participacao=p).delete()
    MensagemSandbox.objects.filter(participacao=p).delete()
    horas = float(p.termos.get('prazo_horas') or float(p.termos.get('prazo_dias') or 1) * 24)
    p.status = 'em_producao'
    p.prazo_ate = timezone.now() + timedelta(hours=horas)
    p.atraso_em = p.aprovado_em = p.mensagens_recolhidas_ate = None
    p.aprovado_por = ''
    p.save(update_fields=['status', 'prazo_ate', 'atraso_em', 'aprovado_em', 'aprovado_por', 'mensagens_recolhidas_ate'])
    # Sem cópia, lixeira ou exportação dos testes. O cache por conteúdo é
    # compartilhado pelo analisador; suas referências privadas foram excluídas.
    # A exclusão física ocorre só depois de confirmar a transação no banco.
    def excluir_anexos():
        for caminho in caminhos:
            caminho.unlink(missing_ok=True)
    transaction.on_commit(excluir_anexos)
    return p
