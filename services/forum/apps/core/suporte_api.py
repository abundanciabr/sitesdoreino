"""Questões vindas do suporte, após confirmação humana; autoria da escola."""
import json
import re
from uuid import UUID
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from ninja import Router, Schema, Field
from ninja.errors import HttpError
from apps.forum.models import Area, Topico, Mensagem, RascunhoDeTopico
from .editor import _so_admin

router=Router()


class Busca(Schema):
    q:str=Field(default='',max_length=500)


class Publicacao(Schema):
    referencia:str
    area_slug:str=Field(max_length=60)
    titulo:str=Field(min_length=5,max_length=180)
    pergunta:str=Field(min_length=1,max_length=12000)
    resposta:str=Field(min_length=1,max_length=12000)
    topico_id:int|None=None


def url(topico):
    return 'https://meshcraft.top/forum/t/'+str(topico.pk)


@router.post('/buscar')
def buscar(request,dados:Busca):
    _so_admin(request)
    areas=Area.objects.filter(ativa=True)
    consulta=Topico.objects.filter(area__in=areas,estado='publicado',trancado=False)
    termos=re.findall(r'\w{4,}',dados.q)[:8]
    filtro=Q(pk__in=[])
    for termo in termos:filtro|=Q(titulo__icontains=termo)
    consulta=consulta.filter(filtro)
    return {'areas':list(areas.values('slug','nome','visibilidade','curso_id')),
      'topicos':[{'id':t.pk,'titulo':t.titulo,'area':t.area.slug,'url':url(t)} for t in consulta.select_related('area')[:12]]}


@router.post('/publicar')
def publicar(request,dados:Publicacao):
    _so_admin(request)
    try:referencia=UUID(dados.referencia)
    except ValueError:raise HttpError(422,'Prévia inválida')
    # Mesmo pedido, mesma linha do rascunho. A trava também cobre reenvio concorrente.
    with transaction.atomic():
        previa,_=RascunhoDeTopico.objects.get_or_create(pk=referencia,defaults={
            'area_slug':dados.area_slug,'titulo':dados.titulo,
            'texto':json.dumps({'pergunta':dados.pergunta,'resposta':dados.resposta,'topico_id':dados.topico_id},ensure_ascii=False)})
        previa=RascunhoDeTopico.objects.select_for_update().get(pk=referencia)
        if previa.publicado_em and previa.topico_id:
            return {'url':url(previa.topico),'topico_id':previa.topico_id,'repetido':True}
        area=Area.objects.filter(slug=dados.area_slug,ativa=True).first()
        if not area:raise HttpError(422,'Escolha uma área ativa')
        if dados.topico_id:
            topico=Topico.objects.select_for_update().filter(pk=dados.topico_id,area=area,estado='publicado',trancado=False).first()
            if not topico:raise HttpError(422,'O tópico precisa estar aberto e pertencer à área escolhida')
            resposta=Mensagem.objects.create(topico=topico,autor=None,publicado_pela_escola=True,
                texto='Pergunta recebida pelo suporte:\n\n'+dados.pergunta+'\n\nResposta da escola:\n\n'+dados.resposta)
        else:
            topico=Topico.objects.create(area=area,autor=None,publicado_pela_escola=True,titulo=dados.titulo,estado='publicado')
            pergunta=Mensagem.objects.create(topico=topico,autor=None,publicado_pela_escola=True,texto=dados.pergunta)
            pergunta.indexar_para_busca()
            resposta=Mensagem.objects.create(topico=topico,autor=None,publicado_pela_escola=True,texto=dados.resposta)
        resposta.indexar_para_busca()
        if not topico.resposta_aceita_id:topico.resposta_aceita=resposta
        topico.ultima_atividade_em=timezone.now();topico.save(update_fields=['resposta_aceita','ultima_atividade_em'])
        previa.topico=topico;previa.publicado_em=timezone.now();previa.save(update_fields=['topico','publicado_em'])
        return {'url':url(topico),'topico_id':topico.pk,'repetido':False}
