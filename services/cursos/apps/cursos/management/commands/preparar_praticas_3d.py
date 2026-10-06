import json,uuid
from pathlib import Path
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from apps.cursos.models import Curso,Aula,Base3D,Atividade3D,Jornada3D,Progresso

class Command(BaseCommand):
    help='Configura as práticas solicitadas pelo mantenedor sem apagar conteúdo ou progresso.'
    def handle(self,*args,**options):
        path=Path(__file__).resolve().parents[4]/'static/praticas-3d/catalogo.json'
        catalog=json.loads(path.read_text(encoding='utf8'))
        modelos=[f"{m['id']}@{m['versao']}" for m in catalog]
        with transaction.atomic():
            for m in catalog:
                Base3D.objects.get_or_create(chave=m['id'],versao=m['versao'],defaults={'dados':m})
            for curso in Curso.objects.filter(slug='desafio-como-ganhar-em-dolar-com-roblox'):
                # Current participants keep all their prior rights; no invented start date.
                for pessoa in Progresso.objects.filter(aula__curso=curso).values_list('pessoa_id',flat=True).distinct():
                    Jornada3D.objects.get_or_create(pessoa_id=pessoa,curso=curso,defaults={'legado':True,'inicio':None})
                primeira=curso.aulas.get(numero='PET')
                for numero,title in [('D03','Dia 3 — Atenda e confira um pedido fictício'),('F07','Dia 7 — Apresente seu item personalizado')]:
                    Aula.objects.get_or_create(curso=curso,numero=numero,defaults={'bloco':primeira.bloco,'ordem':100 if numero=='D03' else 101,'titulo_exibido':title,'estado':'publicada','publicada_em':timezone.now()})
                # Move by stable lesson IDs, preserving the old tree lesson and all pitches.
                ordem=['PET','D02','D03','01','02','03','F07','J01']
                for i,numero in enumerate(ordem):curso.aulas.filter(numero=numero).update(ordem=200+i)
                for i,numero in enumerate(ordem):curso.aulas.filter(numero=numero).update(ordem=i)
                titulos={1:'Escolha, personalize e guarde seu item',2:'Continue seu item: uma mudança de proporção',3:'Atenda um pedido fictício e confira sua decisão',4:'Seu item e o trabalho por encomenda',5:'Sua experiência e o próximo passo no Blender',6:'Seu projeto e a formação completa',7:'Apresente seu resultado final'}
                objetivos={1:'Você vai escolher uma base, mudar cores, explorar a vista e salvar sua personalização.',2:'Retome suas cores e compare uma mudança de forma. Salve a nova proporção.',3:'Simulação didática: personalize conforme um pedido fictício, confira e explique o que mudou.',4:'Retome seu item. O vídeo a seguir apresenta o caminho de trabalho por encomenda; personalizar aqui ainda não demonstra renda.',5:'Você já entendeu uma ação no navegador. No curso completo, a instalação e o trabalho no Blender são ensinados desde o começo.',6:'Veja seu projeto e conheça o método e a oferta apresentados no vídeo. Suas personalizações continuam acessíveis no Desafio.',7:'Dê um nome, escolha o enquadramento e salve a apresentação final. A conclusão não depende da compra do curso completo.'}
                for dia,numero in enumerate(ordem[:7],1):
                    aula=curso.aulas.get(numero=numero)
                    steps=['Veja o destino: seu próprio item com suas escolhas. Escolha a base que quer continuar.','Escolha a parte indicada pelo nome e personalize suas cores livremente.','Explore a vista e compare o resultado. Recuperar vista conserva suas escolhas.','Escolha um nome e clique em Salvar na minha conta. Espere a confirmação real.','Reconheça o que você mudou. O resultado continua neste quadro e em Meus itens.']
                    if dia==2:steps[1]='Use o controle de proporção. Observe a parte ficando mais larga ou mais estreita. Suas cores continuam iguais.'
                    if dia==3:steps[1]='Leia o pedido fictício. Mude a parte indicada para azul e aumente a proporção. Clique em Conferir meu pedido.'
                    if dia==7:steps[1]='Revise suas escolhas, dê um nome ao item e escolha a vista para a apresentação final.'
                    Atividade3D.objects.get_or_create(aula=aula,defaults={'id':uuid.uuid5(uuid.NAMESPACE_URL,f'meshcraft:atividade3d:{curso.site_id}:{curso.pk}:{aula.pk}'),'grupo':'desafio-item-original','dia':dia,'configuracao':{'titulo':titulos[dia],'objetivo':objetivos[dia],'modelos':modelos,'etapas':steps}})
                curso.aulas.filter(numero='PET').update(titulo_exibido='Dia 1 — Personalize e salve seu primeiro item 3D')
                curso.aulas.filter(numero='D02').update(titulo_exibido='Dia 2 — Continue seu item e mude uma proporção')
                # Legacy participants retain their access to the newly inserted days too.
                for j in Jornada3D.objects.filter(curso=curso,legado=True):
                    for n in ['D03','F07']:Progresso.objects.get_or_create(pessoa=j.pessoa,aula=curso.aulas.get(numero=n),defaults={'estado':'disponivel'})
            for curso in Curso.objects.filter(slug='primeiros-dolares'):
                aula=curso.aulas.filter(numero='01',estado='publicada').first()
                if aula:
                    Atividade3D.objects.get_or_create(aula=aula,defaults={'id':uuid.uuid5(uuid.NAMESPACE_URL,f'meshcraft:atividade3d:{curso.site_id}:{curso.pk}:{aula.pk}'),'grupo':'primeiros-dolares-experiencia','dia':1,'configuracao':{'titulo':'Experimente uma personalização 3D','objetivo':'Conheça uma base preparada e explore escolhas de aparência antes do trabalho no Blender. O conteúdo original da aula continua abaixo.','modelos':modelos,'complementar':True}})
        self.stdout.write('Catálogo e sete dias configurados. Árvore, vídeos, conteúdos e progressos preservados.')
