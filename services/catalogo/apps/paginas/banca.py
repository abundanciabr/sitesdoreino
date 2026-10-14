"""Conteúdo congelado e comprovantes da banca; nenhuma crítica aprova vendas."""
import copy
import hashlib
import json

from ninja.errors import HttpError
from .models import Page, PageDraft, Experimento, BancaRegistro


def digest(conteudo):
    return hashlib.sha256(json.dumps(conteudo, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def fotografia(page, origem='publicada', experimento_id='', variante=''):
    publicada = page.ultima_versao
    if origem == 'rascunho':
        draft = PageDraft.objects.filter(page=page).first()
        if not draft or not draft.secoes:
            raise HttpError(409, 'Esta página não tem rascunho com conteúdo.')
        secoes, versao = draft.secoes, draft.base_version
    else:
        if not publicada:
            raise HttpError(409, 'Esta página não tem versão publicada.')
        secoes, versao = publicada.secoes, publicada.version
    secoes = copy.deepcopy(secoes)
    if origem == 'variante':
        exp = Experimento.objects.filter(pk=experimento_id, page=page).first()
        if not exp:
            raise HttpError(404, 'Experimento não encontrado nesta página.')
        v = exp.variantes.filter(variante_id=variante).first()
        if not v:
            raise HttpError(404, 'Variante não encontrada.')
        # Ao iniciar o catálogo atualiza o controle a com o texto publicado atual.
        if variante != 'a' or exp.estado != Experimento.RASCUNHO:
            for secao in secoes:
                if secao['nome'] == exp.secao:
                    secao['slots'][exp.slot] = v.valor
    elif origem not in {'publicada', 'rascunho'}:
        raise HttpError(422, 'Origem inválida.')
    oferta = page.offer
    conteudo = {'site_id': str(page.site_id), 'page_id': str(page.id),
                'slug': page.slug, 'idioma': page.site.default_language or 'pt-br',
                'version': versao, 'secoes': secoes,
                'oferta': ({'slug': oferta.slug, 'version': oferta.version,
                            'price_cents': oferta.price_cents,
                            'produto': oferta.product.name} if oferta else None)}
    return {'conteudo': conteudo, 'assinatura': digest(conteudo), 'origem': origem,
            'experimento_id': str(experimento_id), 'variante': variante}


def conferir_experimento(exp):
    if not BancaRegistro.objects.filter(site_id=exp.page.site_id, exigida=True).exists():
        return
    # A página fica travada junto com o experimento durante a ativação.
    Page.objects.select_for_update().get(pk=exp.page_id)
    for v in exp.variantes.all():
        foto = fotografia(exp.page, 'variante', str(exp.pk), v.variante_id)
        if not BancaRegistro.objects.filter(page=exp.page, assinatura=foto['assinatura'],
                                            completa=True).exists():
            raise HttpError(409, 'Rode a banca completa sobre o conteúdo atual da variante '
                            + v.variante_id + ' antes de iniciar. A banca não aprova a página.')
