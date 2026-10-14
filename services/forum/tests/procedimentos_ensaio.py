import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from datetime import timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from django.conf import settings
settings.configure(SECRET_KEY='ensaio-isolado', USE_TZ=True, INSTALLED_APPS=['apps.forum'],
    DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':':memory:'}},TOKEN_DO_EDITOR_FORUM='teste',
    DEFAULT_AUTO_FIELD='django.db.models.BigAutoField')
import django
django.setup()
from django.db import connection
from django.utils import timezone
from ninja.errors import HttpError
from apps.forum.models import Pessoa,Area,Topico,Mensagem,OutboxEvent
from apps.core.procedimentos import casos

class EnsaioForum(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with connection.schema_editor() as e:
            for m in (Pessoa,Area,Topico,Mensagem,OutboxEvent):
                e.create_model(m)

    def test_aceite_professor_site_atual_privacidade(self):
        a=Area.objects.create(slug='duvidas',nome='Dúvidas',visibilidade='publica',quem_escreve='equipe')
        pessoa=Pessoa.objects.create(id_da_plataforma='aluno',email='aluno@example.com')
        t=Topico.objects.create(area=a,autor=pessoa,titulo='Modelo gigante ao importar')
        Mensagem.objects.create(topico=t,autor=pessoa,texto='Erro na escala. CPF 123.456.789-00 aluno@example.com')
        m=Mensagem.objects.create(topico=t,publicado_pela_escola=True,texto='Aplicar escala')
        t.resposta_aceita=m;t.save()
        evento=OutboxEvent.objects.create(event='forum.resposta-aceita',payload={'site_id':'site',
            'topico_id':str(t.pk),'mensagem_id':str(m.pk),'marcada_por':'autor'})
        req=SimpleNamespace(auth='teste')
        self.assertEqual(casos(req,'site')['itens'],[])
        evento.payload['marcada_por']='professor';evento.save()
        dados=casos(req,'site')['itens']
        self.assertEqual(len(dados),1)
        self.assertNotIn('aluno@example.com',dados[0]['sintoma'])
        self.assertNotIn('123.456',dados[0]['sintoma'])
        self.assertEqual(casos(req,'outro-site')['itens'],[])
        t.resposta_aceita=None;t.save()
        self.assertEqual(casos(req,'site')['itens'],[])
        t.resposta_aceita=m;t.save()
        Topico.objects.filter(pk=t.pk).update(criado_em=timezone.now()-timedelta(days=15))
        self.assertEqual(casos(req,'site')['itens'],[])

    def test_outro_bearer_nao_le(self):
        with self.assertRaises(HttpError):
            casos(SimpleNamespace(auth='outro'),'site')

if __name__=='__main__':
    unittest.main()
