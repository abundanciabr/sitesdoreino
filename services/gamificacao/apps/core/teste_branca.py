"""Reinício recuperável da Faixa Branca da própria conta administrativa."""
import gzip
import hashlib
import json

from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from django.utils.html import format_html
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from ninja.errors import HttpError

from apps.gamificacao.models import (
    AnexoDaJornada, BackupDoReinicioDasFaixas, FaixaDoAluno, JornadaPessoal,
    LancamentoDeXP, PerfilJogador, RegistroDaJornada,
)
from apps.gamificacao.motor import recalcular
from .acesso import e_admin
from .inventario import _dono
from .perfil import perfil_de

BONUS = Q(regra_slug__in=[f'bonus-inicio-etapa-{n}' for n in range(1, 5)]) | Q(regra_slug='bonus-faixa-amarela')


def chave(pessoa):
    return 'teste-branca-checks-20261011-' + hashlib.sha256(pessoa.encode()).hexdigest()[:16]


def _copiar(pessoa, site, nome, jornada):
    dados = {
        'inicio': jornada.inicio, 'declaracao': jornada.declaracoes.get('2'),
        'confirmacao': jornada.confirmacoes_sequenciais.get('2'),
        'celebracao': jornada.celebracao_pendente,
        'celebracoes': PerfilJogador.objects.get(pessoa_id=pessoa, site_id=site).celebracoes_pendentes,
        'xp': list(LancamentoDeXP.objects.filter(pessoa_id=pessoa, site_id=site).filter(BONUS)
                   .exclude(origem_event_id__startswith='teste-branca:').values('pk', 'origem_event_id', 'status')),
        'anexos': list(AnexoDaJornada.objects.filter(pessoa_id=pessoa, site_id=site, passo=2).values_list('pk', flat=True)),
        'faixa': list(FaixaDoAluno.objects.filter(pessoa_id=pessoa, site_id=site, ordem=2).values('pk', 'estado')),
    }
    corpo = gzip.compress(json.dumps(dados, cls=DjangoJSONEncoder, ensure_ascii=False).encode(), mtime=0)
    copia = BackupDoReinicioDasFaixas.objects.create(
        site_id=site, chave=nome, conteudo=corpo, sha256=hashlib.sha256(corpo).hexdigest(),
        contagens={'pessoas': 1, 'xp': len(dados['xp']), 'anexos': len(dados['anexos'])}, criado_em=timezone.now(),
    )
    _ler(BackupDoReinicioDasFaixas.objects.get(pk=copia.pk))
    return copia, dados


def _ler(copia):
    corpo = bytes(copia.conteudo)
    if hashlib.sha256(corpo).hexdigest() != copia.sha256:
        raise ValueError('A cópia não conferiu. Seu avanço foi preservado.')
    return json.loads(gzip.decompress(corpo))


def _arquivar(pessoa, site):
    # Os registros continuam no banco. A origem distinta permite repetir os
    # gestos do teste sem duplicar os créditos antigos.
    for xp in LancamentoDeXP.objects.filter(pessoa_id=pessoa, site_id=site).filter(BONUS).exclude(origem_event_id__startswith='teste-branca:'):
        xp.origem_event_id = f'teste-branca:{xp.pk}'
        xp.status = 'estornado'
        xp.save(update_fields=['origem_event_id', 'status'])
    for anexo in AnexoDaJornada.objects.filter(pessoa_id=pessoa, site_id=site, passo=2):
        passo = 1000
        while AnexoDaJornada.objects.filter(pessoa_id=pessoa, site_id=site, passo=passo, sha256=anexo.sha256).exists():
            passo += 1
        anexo.passo = passo
        anexo.save(update_fields=['passo'])
    FaixaDoAluno.objects.filter(pessoa_id=pessoa, site_id=site, ordem=2).update(estado='revertida')


@never_cache
@csrf_protect
@require_http_methods(['GET', 'POST'])
def teste_branca(request):
    try:
        pessoa, site = _dono(request)
    except HttpError as erro:
        return HttpResponse(erro.message, status=erro.status_code)
    if not e_admin(request, pessoa):
        return HttpResponse('Acesso restrito ao administrador.', status=403)
    nome, mensagem = chave(pessoa), ''
    try:
        if request.method == 'POST':
            with transaction.atomic():
                perfil = perfil_de(pessoa, site)
                type(perfil).objects.select_for_update().get(pk=perfil.pk)
                j, _ = JornadaPessoal.objects.select_for_update().get_or_create(pessoa_id=pessoa, site_id=site)
                if str(j.revisao) != request.POST.get('revisao'):
                    raise ValueError('O avanço mudou em outra aba. Reabra esta tela antes de continuar.')
                if any(int(k) >= 3 and v for k, v in j.confirmacoes_sequenciais.items()) or FaixaDoAluno.objects.filter(pessoa_id=pessoa, site_id=site, ordem__gt=2, estado='alcancada').exists():
                    raise ValueError('Esta operação é limitada à Faixa Branca. O avanço nas outras faixas foi preservado.')
                copia = BackupDoReinicioDasFaixas.objects.filter(site_id=site, chave=nome).first()
                acao = request.POST.get('acao')
                alterou = True
                if acao == 'reiniciar' and not copia:
                    copia, anterior = _copiar(pessoa, site, nome, j)
                    _arquivar(pessoa, site)
                    j.inicio = {}
                    for campo in ('declaracoes', 'confirmacoes_sequenciais'):
                        valor = dict(getattr(j, campo)); valor.pop('2', None); setattr(j, campo, valor)
                    j.celebracao_pendente = {}
                    copia.aplicado_em = timezone.now(); copia.save(update_fields=['aplicado_em'])
                    mensagem = 'Faixa Branca pronta para testar desde Meu motivo. O avanço anterior está guardado.'
                elif acao == 'restaurar' and copia and not copia.contagens.get('restaurado_em'):
                    anterior = _ler(copia)
                    _copiar(pessoa, site, nome + '-teste', j)
                    _arquivar(pessoa, site)
                    j.inicio = anterior['inicio']
                    for campo, valor in (('declaracoes', anterior['declaracao']), ('confirmacoes_sequenciais', anterior['confirmacao'])):
                        registro = dict(getattr(j, campo)); registro.pop('2', None)
                        if valor: registro['2'] = valor
                        setattr(j, campo, registro)
                    j.celebracao_pendente = anterior['celebracao']
                    for xp in anterior['xp']:
                        LancamentoDeXP.objects.filter(pk=xp['pk'], pessoa_id=pessoa, site_id=site).update(origem_event_id=xp['origem_event_id'], status=xp['status'])
                    AnexoDaJornada.objects.filter(pk__in=anterior['anexos'], pessoa_id=pessoa, site_id=site).update(passo=2)
                    for faixa in anterior['faixa']:
                        FaixaDoAluno.objects.filter(pk=faixa['pk'], pessoa_id=pessoa, site_id=site).update(estado=faixa['estado'])
                    copia.contagens = {**copia.contagens, 'restaurado_em': timezone.now().isoformat()}
                    copia.save(update_fields=['contagens'])
                    mensagem = 'Seu avanço anterior foi restaurado. Os registros do teste também ficaram guardados.'
                elif acao not in ('reiniciar', 'restaurar'):
                    raise ValueError('Escolha uma ação nesta tela.')
                else:
                    alterou = False
                    mensagem = 'Esta operação já foi concluída. Nenhum avanço novo foi reiniciado.'
                if alterou:
                    j.revisao += 1
                    j.save(update_fields=['inicio', 'declaracoes', 'confirmacoes_sequenciais', 'celebracao_pendente', 'revisao', 'atualizada_em'])
                    perfil.refresh_from_db()
                    pendentes = [p for p in perfil.celebracoes_pendentes if not (p.get('tipo') == 'nivel-alcancado' or str(p.get('referencia', '')).startswith('faixa-'))]
                    if acao == 'restaurar':
                        pendentes += [p for p in anterior['celebracoes'] if p not in pendentes]
                    perfil.celebracoes_pendentes = pendentes
                    perfil.save(update_fields=['celebracoes_pendentes'])
                    recalcular(pessoa, site, celebrar=False)
                    RegistroDaJornada.objects.create(pessoa_id=pessoa, site_id=site, acao='teste-branca', dados={'acao': acao, 'backup': nome})
    except ValueError as erro:
        mensagem = str(erro)
    copia = BackupDoReinicioDasFaixas.objects.filter(site_id=site, chave=nome).first()
    j = JornadaPessoal.objects.filter(pessoa_id=pessoa, site_id=site).first()
    acao = 'restaurar' if copia else 'reiniciar'
    texto = 'Restaurar meu avanço anterior' if copia else 'Preparar minha Faixa Branca para o teste'
    resposta = HttpResponse(format_html(
        '<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Teste da minha Faixa Branca</title>'
        '<main style="font:18px/1.6 system-ui;max-width:700px;margin:60px auto;padding:24px;color:#102444"><h1>Teste da minha Faixa Branca</h1>'
        '<p>Apenas a conta administrativa aberta aqui. O avanço anterior fica guardado para recuperação. Respostas e arquivos continuam privados.</p>'
        '<p role="status">{}</p><form method="post"><input type="hidden" name="csrfmiddlewaretoken" value="{}"><input type="hidden" name="revisao" value="{}">'
        '<button name="acao" value="{}" style="padding:16px;border-radius:10px;background:#306bec;color:white;border:0;font:inherit">{}</button></form>'
        '<p><a href="/trilha/">Voltar à minha trilha</a></p></main></html>', mensagem, get_token(request), j.revisao if j else 0, acao, texto))
    resposta['Cache-Control'] = 'private, no-store'; resposta['X-Robots-Tag'] = 'noindex, nofollow'
    return resposta
