import pytest
from django.test import Client
from apps.core import comunidade_alunos as comunidade
from apps.core import comunidade_entrada
from apps.core.comunidade_modelos import PerfilDaComunidade
from apps.core.galeria_models import VotoDaGaleria

BASE='/galeria-publica/nova-20261014'
PUBLICO='/comunidade/nova-20261014'

@pytest.fixture
def aluno(monkeypatch,settings):
    settings.ADMIN_EMAILS='admin@example.test'
    def sessao(self,cookie):
        id='bia' if 'bia' in cookie else 'ana'
        return {'autenticado':True,'id':id,'email':id+'@example.test','nome_exibido':id.title()+' Real','papel':'admin'}
    monkeypatch.setattr('apps.core.clients.IdentidadeClient.sessao_completa',sessao)
    monkeypatch.setattr(comunidade,'site_de',lambda request:'site-a')
    monkeypatch.setattr(comunidade.AlunosClient,'alunos',lambda self,status=None:[
        {'site_id':'site-a','status':'ativa','email':'ana@example.test','origem':'liberado','nome_completo':'Nome privado Ana'},
        {'site_id':'site-a','status':'ativa','email':'bia@example.test','origem':'liberado','nome_completo':'Nome privado Bia'},
        {'site_id':'site-a','status':'ativa','email':'admin@example.test','origem':'liberado','nome_completo':'Admin privado'},
        {'site_id':'site-a','status':'ativa','email':'sem-perfil@example.test','origem':'liberado','nome_completo':'NOME PRIVADO SEM PERFIL'},
        {'site_id':'site-b','status':'ativa','email':'fora@example.test','origem':'liberado'},
    ])
    monkeypatch.setattr(comunidade_entrada,'_forum',lambda request:{'ranking':[],'conversas':[],'grupos':[]})
    return Client(HTTP_COOKIE='meshcraft_sessao=ana',HTTP_HOST='meshcraft.top')


def criar(cliente,**campos):
    return cliente.post(BASE+'/perfil',{'usuario':'ana.real','avatar':'azul',**campos})


def perfil(id,email=None,host='meshcraft.top',foto=b''):
    return PerfilDaComunidade.objects.create(site_host=host,identidade_id=id,email=email or id+'@example.test',nome=id.title(),usuario=id,avatar='' if foto else 'verde',foto=foto)


def test_visitante_abre_pagina_sem_bloqueio_e_sem_dados_privados():
    resposta=Client(HTTP_HOST='meshcraft.top').get(BASE)
    assert resposta.status_code == 200
    assert 'Sua comunidade.' in resposta.content.decode()
    assert 'Entrar na comunidade' in resposta.content.decode()
    assert 'Só admins' not in resposta.content.decode()
    assert 'noindex' in resposta['X-Robots-Tag']
    assert not PerfilDaComunidade.objects.exists()


def test_aluno_pode_configurar_e_persistir_perfil_real_sem_poderes_admin(aluno):
    primeira=aluno.get(BASE)
    assert primeira.status_code == 200
    assert 'Seu primeiro acesso' in primeira.content.decode()
    assert 'só admins' not in primeira.content.decode()
    assert PUBLICO+'/assets/comunidade.css' in primeira.content.decode()
    assert PUBLICO+'/assets/comunidade.js' in primeira.content.decode()
    resposta=criar(aluno,identidade_id='admin',email='forjado@example.test')
    assert resposta.status_code == 302 and resposta.url == PUBLICO
    p=PerfilDaComunidade.objects.get()
    assert (p.identidade_id,p.email,p.nome,p.usuario)==('ana','ana@example.test','Ana','ana.real')
    pagina=aluno.get(BASE)
    corpo=pagina.content.decode()
    assert pagina.status_code == 200
    assert '@ana.real' in corpo
    assert '/admin/' not in corpo
    assert 'Simulação' not in corpo
    assert 'NOME PRIVADO SEM PERFIL' not in corpo
    assert 'Nome privado Ana' not in corpo
    assert 'example.test' not in corpo
    assert aluno.get('/galeria-publica/assets/comunidade.css').status_code == 404


def test_nove_temas_persistem_sem_alterar_outro_perfil(aluno):
    criar(aluno)
    outro=perfil('bia')
    for tema,_ in comunidade_entrada.TEMAS:
        r=aluno.post(BASE+'/tema',{'tema':tema,'perfil_id':outro.pk})
        assert r.status_code == 302 and r.url == PUBLICO
        assert PerfilDaComunidade.objects.get(identidade_id='ana').tema == tema
    outro.refresh_from_db()
    assert outro.tema == 'apple'
    assert aluno.post(BASE+'/tema',{'tema':'inventado'}).status_code == 404


def test_diretorio_so_mostra_perfis_escolhidos_de_alunos_ativos_da_mesma_escola(aluno):
    criar(aluno)
    perfil('bia')
    perfil('admin')
    perfil('fora')
    perfil('outra-escola',email='bia@example.test',host='outra.example.test')
    corpo=aluno.get(BASE).content.decode()
    assert 'Bia' in corpo
    assert '2 perfis de alunos' in corpo
    assert 'Admin privado' not in corpo
    assert '@admin' not in corpo
    assert '@fora' not in corpo
    assert 'NOME PRIVADO SEM PERFIL' not in corpo


def test_fotos_respeitam_dono_e_visibilidade_sem_expor_admin_ou_outra_escola(aluno):
    ana=perfil('ana',foto=b'foto-ana')
    bia=perfil('bia',foto=b'foto-bia')
    admin=perfil('admin',foto=b'foto-admin')
    fora=perfil('fora',foto=b'foto-fora')
    outra=perfil('outro-site',email='bia@example.test',host='outra.example.test',foto=b'foto-outra')
    assert aluno.get(BASE+f'/foto/{ana.pk}').content == b'foto-ana'
    assert aluno.get(BASE+f'/foto/{bia.pk}').content == b'foto-bia'
    for p in [admin,fora,outra]:
        assert aluno.get(BASE+f'/foto/{p.pk}').status_code == 404
    assert Client().get(BASE+f'/foto/{ana.pk}').status_code == 404


def test_falha_na_matricula_fecha_apenas_dados_de_colegas_e_nao_a_pagina(aluno,monkeypatch):
    criar(aluno)
    bia=perfil('bia',foto=b'foto-bia')
    monkeypatch.setattr(comunidade.AlunosClient,'alunos',lambda self,status=None:None)
    assert aluno.get(BASE).status_code == 200
    assert aluno.get(BASE+f'/foto/{bia.pk}').status_code == 404


def test_pagina_continua_acessivel_sem_matricula_ativa_sem_ampliar_dados_privados(aluno,monkeypatch):
    criar(aluno)
    bia=perfil('bia',foto=b'foto-bia')
    monkeypatch.setattr(comunidade.AlunosClient,'alunos',lambda self,status=None:[])
    assert aluno.get(BASE).status_code == 200
    assert '@bia' not in aluno.get(BASE).content.decode()
    assert aluno.get(BASE+f'/foto/{bia.pk}').status_code == 404


def test_recursos_publicos_da_nova_pagina_nao_abrem_arquivos_administrativos():
    c=Client(HTTP_HOST='meshcraft.top')
    for url in ['/assets/comunidade.css','/assets/comunidade.js','/assets/hero.png','/avatar/azul']:
        assert c.get(BASE+url).status_code == 200
    assert c.get(BASE+'/assets/percurso.html').status_code == 404
    assert c.get(BASE+'/assets/politica.json').status_code == 404
    assert c.get(BASE+'/avatar/inventado').status_code == 404


def test_nome_repetido_nao_altera_perfil_de_outra_pessoa(aluno):
    outro=perfil('bia')
    assert criar(aluno,usuario='bia').status_code == 409
    assert PerfilDaComunidade.objects.count() == 1
    outro.refresh_from_db()
    assert outro.usuario == 'bia'


def test_anonimo_nao_grava_perfil_e_get_nao_produz_efeitos():
    c=Client(HTTP_HOST='meshcraft.top')
    assert c.post(BASE+'/perfil',{'usuario':'falso','avatar':'azul'}).status_code == 302
    assert c.get(BASE+'/perfil').status_code == 405
    assert not PerfilDaComunidade.objects.exists()


def test_csrf_real_do_perfil_aluno(aluno):
    c=Client(enforce_csrf_checks=True,HTTP_HOST='meshcraft.top')
    c.cookies['meshcraft_sessao']='ana'
    assert criar(c).status_code == 403
    resposta=c.get(BASE,secure=True)
    token=resposta.cookies['admin_csrf'].value
    assert resposta.cookies['admin_csrf']['path'] == '/comunidade'
    c.cookies['admin_csrf']=token
    assert c.post(BASE+'/perfil',{'usuario':'ana','avatar':'azul'},HTTP_X_CSRFTOKEN=token,HTTP_REFERER='https://meshcraft.top'+PUBLICO,secure=True).status_code == 302


def test_endereco_novo_nao_e_divulgado_na_votacao_atual(aluno,monkeypatch):
    VotoDaGaleria.objects.create(pessoa_id='aluno-real',imagem='apple')
    monkeypatch.setattr('apps.core.galeria_comunidade.aluno',lambda request:{'id':'ana','nome':'Ana','email':'ana@example.test'})
    corpo=aluno.get('/galeria-publica').content.decode()
    assert corpo.count('class="modelo"') == 9
    assert PUBLICO not in corpo
    assert VotoDaGaleria.objects.count() == 1


def test_lista_publica_nao_abre_areas_administrativas():
    assert comunidade.caminho_publico(BASE)
    assert comunidade.caminho_publico(BASE+'/assets/comunidade.js')
    for url in ['/comunidade/percurso/','/comunidade/alunos-atual/','/docs/comunidade',BASE+'-admin',BASE+'/admin/documentos']:
        assert not comunidade.caminho_publico(url)
