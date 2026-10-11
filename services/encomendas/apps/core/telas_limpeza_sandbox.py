"""Duas confirmações explícitas para apagar os testes do trabalho aberto."""
from django.core import signing
from django.db import IntegrityError
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from apps.core.telas_sandbox import _trabalho, _login, _falha, _voltar
from apps.encomendas import limpeza_sandbox, sandbox

SALT = 'sandbox.limpar-testes'


def _confirmacao(trabalho, pessoa, etapa):
    return {'trabalho': str(trabalho.pk), 'site': trabalho.site_id, 'pessoa': pessoa,
            'prazo': trabalho.prazo_ate.isoformat(), 'etapa': etapa}


@require_http_methods(['GET', 'POST'])
def limpar_testes(request, participacao_id):
    trabalho, pessoa, papel = _trabalho(request, participacao_id)
    if trabalho is None:
        return _login(request)
    etapa = 1
    if request.method == 'POST':
        try:
            etapa_enviada = int(request.POST.get('etapa', '0'))
            confirmacao = signing.loads(request.POST.get('confirmacao', ''), salt=SALT, max_age=900)
            if etapa_enviada not in (1, 2) or confirmacao != _confirmacao(trabalho, pessoa, etapa_enviada):
                raise ValueError
        except (ValueError, signing.BadSignature):
            return _falha(request, 'Abra Limpar testes novamente e confirme as duas etapas.',
                          papel=papel, trabalho=trabalho)
        if etapa_enviada == 2:
            try:
                limpeza_sandbox.limpar(trabalho, confirmacao['prazo'])
            except (sandbox.ErroSandbox, IntegrityError) as erro:
                texto = str(erro) if isinstance(erro, sandbox.ErroSandbox) else 'Já existe outro trabalho em andamento.'
                return _falha(request, texto, papel=papel, trabalho=trabalho)
            return _voltar('sandbox_trabalho', trabalho.pk,
                recado='Testes apagados. Arquivos, entregas, análises e conversa foram limpos. O prazo foi reiniciado.')
        etapa = 2
    resposta = render(request, 'sandbox/limpar_testes.html', {
        'trabalho': trabalho, 'papel': papel, 'etapa': etapa,
        'resumo': limpeza_sandbox.resumo(trabalho),
        'confirmacao': signing.dumps(_confirmacao(trabalho, pessoa, etapa), salt=SALT),
    })
    resposta['Cache-Control'] = 'private, no-store'
    return resposta
