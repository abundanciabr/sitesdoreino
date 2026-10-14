"""Matrícula e pedido de acesso na entrada central do site."""

from urllib.parse import urlencode

from django import forms
from django.http import HttpResponseRedirect
from django.shortcuts import render

from apps.core.clients import AlunosClient, IdentidadeClient
from apps.core.middleware import limpar_cache_de_categoria
from apps.i18n.idiomas import caminho_publico


class PedidoDeAcesso(forms.Form):
    nome_completo = forms.CharField(max_length=200)
    whatsapp = forms.CharField(max_length=30)
    comprou_em = forms.DateField(required=False, input_formats=['%Y-%m-%d'])
    turma = forms.CharField(required=False, max_length=200)

    def clean_whatsapp(self):
        valor = self.cleaned_data['whatsapp']
        if not 10 <= len(''.join(c for c in valor if c.isdigit())) <= 15:
            raise forms.ValidationError('whatsapp')
        return valor


def endereco_do_login(request, destino):
    login = caminho_publico(request.i18n, request.idioma, '/login')
    return f'{login}?{urlencode({"next": destino})}'


def acesso_do_aluno(request, destino):
    """Identidade vem da sessão; matrícula e recibo vêm da mesma fila existente."""
    ator = request.ator
    if not ator:
        return None
    if ator.papel == 'staff':
        return HttpResponseRedirect(destino)

    email = IdentidadeClient().obter_email(request.META.get('HTTP_COOKIE', ''))
    alunos = AlunosClient()
    situacao = alunos.situacao_de(email) if email else None
    categoria = (situacao or {}).get('categoria')
    login = endereco_do_login(request, destino)
    if categoria == 'aluno':
        return HttpResponseRedirect(destino)

    fila = (situacao or {}).get('na_fila') or {}
    esperando = categoria == 'na_fila' and fila.get('estado') == 'aguardando'
    if categoria == 'na_fila' and fila.get('estado') not in ('aguardando', 'recusada'):
        categoria = None
    form = PedidoDeAcesso(request.POST if request.method == 'POST' else None)
    erro_envio = False
    status = 200 if categoria in ('cadastrado', 'ex_aluno', 'na_fila', 'pausado', 'reembolsado') else 503
    pode_pedir = categoria in ('cadastrado', 'ex_aluno')

    if request.method == 'POST' and pode_pedir:
        if form.is_valid():
            dados = form.cleaned_data
            resultado = alunos.criar_pre_matricula(
                site_id=request.site['id'], email=email,
                nome_completo=dados['nome_completo'], whatsapp=dados['whatsapp'],
                comprou_em=dados['comprou_em'].isoformat() if dados['comprou_em'] else '',
                turma=dados['turma'],
            )
            limpar_cache_de_categoria()
            if resultado in (alunos.RESULTADO_NA_FILA, alunos.RESULTADO_JA_TEM_MATRICULA):
                # PRG: o recibo é conferido novamente, sem reenviar o formulário.
                return HttpResponseRedirect(login)
            erro_envio, status = True, 502
        else:
            status = 400

    resposta = render(request, 'funil/acesso_aluno.html', {
        'email_do_acesso': email or '', 'categoria_do_acesso': categoria,
        'pode_pedir': pode_pedir, 'esperando_acesso': esperando,
        'fila_do_acesso': fila, 'form': form, 'erro_envio': erro_envio,
        'url_do_acesso': login,
        'url_trocar_conta': login + '&trocar=1',
    }, status=status)
    resposta['Cache-Control'] = 'private, no-store'
    resposta['X-Robots-Tag'] = 'noindex, nofollow'
    return resposta
