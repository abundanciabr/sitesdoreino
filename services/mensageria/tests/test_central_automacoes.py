"""Cenários que distinguem a Central da jornada legada."""
import uuid
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.conversas.models import Conversa, MensagemDaConversa
from apps.jornadas import central, motor
from apps.jornadas import central_api as api
from apps.jornadas.models import Entrega, Inscricao, Jornada, JornadaVersao, Passo, TextoDoPasso

pytestmark = pytest.mark.django_db


def test_historico_de_teste_usa_mensagem_real_e_nao_vaza_outro_site():
    jornada, _, _ = automacao(publicada=False)
    for site in ('s1', 's2'):
        conversa = Conversa.objects.create(site_id=site, canal='whatsapp', endereco='5511999999999')
        MensagemDaConversa.objects.create(conversa=conversa, direcao='saida', autor='agente',
            autor_id='central:teste:' + jornada.slug, texto='Teste', estado_envio='entregue',
            ocorrida_em=timezone.now(), chave_idempotencia='teste-real')
    detalhe = api.detalhe(None, jornada.slug, 's1')
    assert len(detalhe['testes']) == 1
    assert detalhe['testes'][0]['estado'] == 'entregue'
    assert detalhe['entregas'] == []


def automacao(*, publicada=True):
    jornada = Jornada.objects.create(site_id="s1", slug="central-1", gatilho="aula.concluida",
        ativa=publicada, central_entrada_aberta=publicada)
    versao = JornadaVersao.objects.create(jornada=jornada, numero=1,
        central_config={"central": True, "gatilho": "aula.concluida", "publico": "alunos",
                        "resposta": "pausar", "nome": "Aula"})
    passo = Passo.objects.create(jornada_versao=versao, ordem=1, atraso=timedelta(hours=2),
                                 classe="relacional", canais=["whatsapp"])
    TextoDoPasso.objects.create(passo=passo, idioma="pt-br", assunto_visivel="Aula", corpo="Olá!")
    if publicada:
        JornadaVersao.objects.filter(pk=versao.pk).update(publicada_em=timezone.now())
    return jornada, versao, passo


def test_rascunho_nao_inscreve_nem_envia(monkeypatch):
    automacao(publicada=False)
    monkeypatch.setattr("apps.jornadas.despacho._telefone_da_pessoa", lambda **_: (None, None, ""))
    assert central.inscrever_evento(gatilho="aula.concluida", site_id="s1",
        destinatario_id="aluno-1", event_id=uuid.uuid4(), contexto={"aluno_id": "aluno-1"}) == []
    assert not Inscricao.objects.exists()
    assert not Entrega.objects.exists()


def test_entrada_idempotente_ancorada_e_pausa_total(monkeypatch):
    jornada, _, _ = automacao()
    conversa = Conversa.objects.create(site_id="s1", canal="whatsapp", endereco="5511999999999")
    monkeypatch.setattr("apps.jornadas.despacho._telefone_da_pessoa", lambda **_: (None, None, ""))
    fato = uuid.uuid4()
    momento = timezone.now()
    argumentos = dict(gatilho="aula.concluida", site_id="s1", destinatario_id="aluno-1",
                     event_id=fato, contexto={"aluno_id": "aluno-1"}, conversa=conversa, momento=momento)
    primeira = central.inscrever_evento(**argumentos)[0]
    assert central.inscrever_evento(**argumentos)[0].id == primeira.id
    assert primeira.proximo_em == momento + timedelta(hours=2)
    jornada.central_pausada = True
    jornada.save(update_fields=["central_pausada"])
    assert list(motor.candidatas(momento + timedelta(hours=3))) == []
    jornada.central_pausada = False
    jornada.central_entrada_aberta = False
    jornada.save(update_fields=["central_pausada", "central_entrada_aberta"])
    assert list(motor.candidatas(momento + timedelta(hours=3))) == [primeira]
    assert central.inscrever_evento(gatilho="aula.concluida", site_id="s1",
        destinatario_id="aluno-2", event_id=uuid.uuid4(), contexto={"aluno_id": "aluno-2"},
        conversa=conversa) == []


def test_resultado_incerto_so_sincroniza_mesmo_id(monkeypatch):
    jornada, versao, passo = automacao()
    conversa = Conversa.objects.create(site_id="s1", canal="whatsapp", endereco="5511999999999")
    inscricao = motor.inscrever(jornada, destinatario_id="a", site_id="s1", origem_event_id=uuid.uuid4())
    inscricao.central_conversa_id = conversa.id
    inscricao.save(update_fields=["central_conversa_id"])
    entrega = Entrega.objects.create(inscricao=inscricao, passo=passo, canal="whatsapp",
                                     previsto_para=timezone.now(), resultado="pendente", whatsapp_intencao=True)
    mensagem = MensagemDaConversa.objects.create(conversa=conversa, direcao="saida", autor="agente",
        texto="Olá!", estado_envio="desconhecido", ocorrida_em=timezone.now(),
        chave_idempotencia=f"central:{inscricao.id}:{passo.id}")
    monkeypatch.setattr("apps.conversas.envio.enviar", lambda **_: pytest.fail("envio incerto repetido"))
    central.processar_entrega(entrega)
    entrega.refresh_from_db()
    assert entrega.resultado == "resultado_desconhecido"
    assert conversa.mensagens.count() == 1
    assert conversa.mensagens.first().id == mensagem.id


def test_campo_ausente_bloqueia_personalizacao():
    with pytest.raises(ValueError, match="link"):
        central.preencher("Acesse {{link}}", {})
    assert central.preencher("Olá, {{nome}}", {"nome": "Ana"}) == "Olá, Ana"
    assert not central.publico_permite("curso:produto-a", {"curso_id": "produto-a"})
    assert central.publico_permite("curso:produto-a", {"produto_id": "produto-a", "curso_id": "pk-9"})
    assert not central.publico_permite("curso:produto-a", {"produto_id": "produto-b", "curso_id": "produto-a"})


def test_selecao_manual_nao_inscreve_outra_automacao():
    conversa = Conversa.objects.create(site_id="s1", canal="whatsapp", endereco="5511999999999")
    jornadas = []
    for slug in ("aviso-a", "aviso-b"):
        jornada = Jornada.objects.create(site_id="s1", slug=slug, gatilho="manual", ativa=True,
                                          central_entrada_aberta=True)
        versao = JornadaVersao.objects.create(jornada=jornada, numero=1,
            central_config={"central": True, "publico": "contatos", "gatilho": "manual"})
        Passo.objects.create(jornada_versao=versao, ordem=1, classe="relacional", canais=["whatsapp"])
        JornadaVersao.objects.filter(pk=versao.pk).update(publicada_em=timezone.now())
        jornadas.append(jornada)
    resultado = central.inscrever_evento(gatilho="manual", site_id="s1",
        destinatario_id=f"conversa:{conversa.id}", event_id=uuid.uuid4(), conversa=conversa,
        jornada_slug="aviso-a")
    assert len(resultado) == 1 and resultado[0].jornada_id == jornadas[0].id
    assert not Inscricao.objects.filter(jornada=jornadas[1]).exists()


def test_crud_versiona_sem_publicar_e_rejeita_ativacao_vazia(monkeypatch):
    monkeypatch.setattr(api, "_escrever", lambda request: None)
    criado = api.criar(None, api.CriarEntrada(site_id="s1", nome="Nova série"))
    assert criado["versao_atual"] == 1 and criado["versao_publicada"] is None
    slug = criado["slug"]
    with pytest.raises(Exception, match="versão sem passos"):
        api.acao(None, slug, api.AcaoEntrada(site_id="s1", acao="ativar"))
    rascunho = JornadaVersao.objects.get(jornada__slug=slug, numero=1)
    passo = Passo.objects.create(jornada_versao=rascunho, ordem=1, classe="relacional", canais=["whatsapp"])
    TextoDoPasso.objects.create(passo=passo, idioma="pt-br", assunto_visivel="Teste", corpo="Olá")
    with pytest.raises(Exception, match="gatilho"):
        api.acao(None, slug, api.AcaoEntrada(site_id="s1", acao="ativar"))
    assert JornadaVersao.objects.get(pk=rascunho.pk).publicada_em is None
    salvo = api.salvar(None, slug, api.SalvarEntrada(site_id="s1", versao_base=1,
        nome="Nova série 2", objetivo="Ajudar alunos", gatilho="aula.concluida",
        publico="alunos", resposta="pausar", roteiro="Ouça a dúvida.",
        passos=[{"ordem": 1, "atraso_segundos": 3600, "corpo": "Olá!"}]))
    assert salvo["versao_atual"] == 2 and salvo["versao_publicada"] is None
    with pytest.raises(Exception, match="versão base"):
        api.salvar(None, slug, api.SalvarEntrada(site_id="s1", versao_base=1,
            nome="Antigo", gatilho="aula.concluida", passos=[{"ordem": 1, "corpo": "X"}]))
    ativada = api.acao(None, slug, api.AcaoEntrada(site_id="s1", acao="ativar", versao=2))
    assert ativada["ativa"] and ativada["versao_publicada"] == 2
    assert JornadaVersao.objects.get(jornada__slug=slug, numero=1).publicada_em is None
    antigo = api.detalhe(None, slug, "s1", versao=1)
    assert antigo["config_exibida"]["nome"] == "Nova série"
    assert antigo["automacao"]["nome"] == "Nova série"
    assert antigo["automacao"]["versao_atual"] == 2


def test_modelo_confirmacao_tem_gatilho_real_e_classe_transacional(monkeypatch):
    monkeypatch.setattr(api, "_escrever", lambda request: None)
    criada = api.criar(None, api.CriarEntrada(site_id="s1", nome="Matrícula", modelo="compra"))
    jornada = Jornada.objects.get(slug=criada["slug"], site_id="s1")
    versao = jornada.versoes.get(numero=1)
    assert versao.central_config["gatilho"] == "matricula.ativa"
    assert versao.passos.get().classe == "transacional"
    assert api.acao(None, jornada.slug, api.AcaoEntrada(site_id="s1", acao="ativar"))["ativa"]
    outra = api.criar(None, api.CriarEntrada(site_id="s1", nome="Campanha", modelo="campanha"))
    assert Jornada.objects.get(site_id="s1", slug=outra["slug"]).versoes.get().passos.get().classe == "relacional"


def test_inscricao_manual_api_escopada_e_idempotente(monkeypatch):
    monkeypatch.setattr(api, "_escrever", lambda request: None)
    conversa = Conversa.objects.create(site_id="s1", canal="whatsapp", endereco="5511999999999")
    outra = Conversa.objects.create(site_id="s2", canal="whatsapp", endereco="5511888888888")
    criado = api.criar(None, api.CriarEntrada(site_id="s1", nome="Aviso", modelo="operacional"))
    api.acao(None, criado["slug"], api.AcaoEntrada(site_id="s1", acao="ativar"))
    entrada = api.ParticipantesEntrada(site_id="s1", chave_idempotencia="lote-1", pessoas=[
        {"destinatario_id": f"conversa:{conversa.id}", "conversa_id": str(conversa.id)},
        {"destinatario_id": f"conversa:{outra.id}", "conversa_id": str(outra.id)},
    ])
    primeira = api.inscrever_participantes(None, criado["slug"], entrada)
    segunda = api.inscrever_participantes(None, criado["slug"], entrada)
    assert len(primeira["inscritos"]) == len(segunda["inscritos"]) == 1
    assert primeira["inscritos"][0]["inscricao_id"] == segunda["inscritos"][0]["inscricao_id"]
    assert len(primeira["recusados"]) == 1
    assert Inscricao.objects.filter(jornada__slug=criado["slug"]).count() == 1


def test_falha_confirmada_reusa_mensagem_e_incerta_nao_reenvia(monkeypatch):
    jornada, _, passo = automacao()
    conversa = Conversa.objects.create(site_id="s1", canal="whatsapp", endereco="5511999999999")
    inscricao = motor.inscrever(jornada, destinatario_id="a", site_id="s1", origem_event_id=uuid.uuid4())
    inscricao.central_conversa_id = conversa.id
    inscricao.save(update_fields=["central_conversa_id"])
    entrega = Entrega.objects.create(inscricao=inscricao, passo=passo, canal="whatsapp",
        previsto_para=timezone.now(), resultado="falhou", whatsapp_intencao=True)
    mensagem = MensagemDaConversa.objects.create(conversa=conversa, direcao="saida", autor="agente",
        texto="Olá!", estado_envio="falhou", ocorrida_em=timezone.now(),
        chave_idempotencia=f"central:{inscricao.id}:{passo.id}")
    chamadas = []
    def reenviar(**kwargs):
        chamadas.append(kwargs["chave_idempotencia"])
        mensagem.estado_envio = "aceito"
        mensagem.save(update_fields=["estado_envio"])
        return SimpleNamespace(resultado="enviada", mensagem=mensagem, detalhe="")
    monkeypatch.setattr("apps.conversas.envio.enviar", reenviar)
    central.processar_entrega(entrega)
    assert chamadas == []
    central.processar_entrega(entrega, permitir_falha=True)
    assert chamadas == [f"central:{inscricao.id}:{passo.id}"]
    entrega.refresh_from_db()
    assert entrega.resultado == "aceita_pelo_gateway" and conversa.mensagens.count() == 1


def test_teste_usa_contexto_real_e_expõe_estado_da_mensagem(monkeypatch):
    jornada, versao, passo = automacao(publicada=False)
    texto = TextoDoPasso.objects.get(passo=passo)
    texto.corpo = "Olá, {{nome}}"
    texto.save(update_fields=["corpo"])
    JornadaVersao.objects.filter(pk=versao.pk).update(publicada_em=timezone.now())
    jornada.ativa = True
    jornada.save(update_fields=["ativa"])
    conversa = Conversa.objects.create(site_id="s1", canal="whatsapp", endereco="5511999999999")
    inscricao = motor.inscrever(jornada, destinatario_id="a", site_id="s1", origem_event_id=uuid.uuid4())
    inscricao.central_conversa_id, inscricao.central_contexto = conversa.id, {"nome": "Ana"}
    inscricao.save(update_fields=["central_conversa_id", "central_contexto"])
    enviados = []
    def falso_envio(**kwargs):
        enviados.append(kwargs["texto"])
        mensagem = MensagemDaConversa.objects.create(conversa=conversa, direcao="saida", autor="agente",
            texto=kwargs["texto"], estado_envio="aceito", ocorrida_em=timezone.now(),
            chave_idempotencia=kwargs["chave_idempotencia"])
        return SimpleNamespace(resultado="enviada", mensagem=mensagem, detalhe="")
    monkeypatch.setattr("apps.conversas.envio.enviar", falso_envio)
    resultado = central.testar(jornada=jornada, conversa=conversa, versao=versao,
                               chave_idempotencia="teste-ana")
    assert enviados == ["Olá, Ana"]
    assert resultado["estado"] == "aceito" and resultado["resultado"] == "enviada"


@pytest.mark.parametrize("estado", ["falhou", "desconhecido", "pendente"])
def test_pedido_humano_suspende_mesmo_sem_confirmacao(estado, monkeypatch):
    jornada, versao, _ = automacao(publicada=False)
    versao.central_config = {**versao.central_config, "resposta": "humano"}
    versao.save(update_fields=["central_config"])
    JornadaVersao.objects.filter(pk=versao.pk).update(publicada_em=timezone.now())
    jornada.ativa = True
    jornada.save(update_fields=["ativa"])
    conversa = Conversa.objects.create(site_id="s1", canal="whatsapp", endereco="5511999999999")
    inscricao = motor.inscrever(jornada, destinatario_id="a", site_id="s1",
        origem_event_id=uuid.uuid4(), momento=timezone.now() - timedelta(minutes=1))
    inscricao.central_conversa_id = conversa.id
    inscricao.save(update_fields=["central_conversa_id"])
    entrada = MensagemDaConversa.objects.create(conversa=conversa, direcao="entrada", autor="lead",
        texto="Quero falar com uma pessoa", estado_envio="recebida", ocorrida_em=timezone.now())
    confirmacao = MensagemDaConversa.objects.create(conversa=conversa, direcao="saida", autor="agente",
        texto="A equipe vai acompanhar", estado_envio=estado, ocorrida_em=timezone.now(),
        chave_idempotencia=f"central-humano:{entrada.id}")
    monkeypatch.setattr("apps.conversas.envio.enviar", lambda **_: SimpleNamespace(
        resultado="enviada", mensagem=confirmacao, detalhe=""))
    assert central.ao_resposta(entrada) == 1
    inscricao.refresh_from_db()
    conversa.refresh_from_db()
    assert inscricao.central_suspensa
    assert conversa.estado == "agente"
    assert conversa.mensagens.filter(chave_idempotencia=f"central-humano:{entrada.id}").count() == 1


def test_handoff_incerto_reconcilia_mesma_confirmacao(monkeypatch):
    jornada, versao, _ = automacao(publicada=False)
    versao.central_config = {**versao.central_config, "resposta": "humano"}
    versao.save(update_fields=["central_config"])
    JornadaVersao.objects.filter(pk=versao.pk).update(publicada_em=timezone.now())
    jornada.ativa = True
    jornada.save(update_fields=["ativa"])
    conversa = Conversa.objects.create(site_id="s1", canal="whatsapp", endereco="5511999999999")
    inscricao = motor.inscrever(jornada, destinatario_id="a", site_id="s1",
        origem_event_id=uuid.uuid4(), momento=timezone.now() - timedelta(minutes=1))
    inscricao.central_conversa_id = conversa.id
    inscricao.save(update_fields=["central_conversa_id"])
    entrada = MensagemDaConversa.objects.create(conversa=conversa, direcao="entrada", autor="lead",
        texto="Pessoa", estado_envio="recebida", ocorrida_em=timezone.now())
    confirmacao = MensagemDaConversa.objects.create(conversa=conversa, direcao="saida", autor="agente",
        texto="Equipe", estado_envio="desconhecido", ocorrida_em=timezone.now(),
        chave_idempotencia=f"central-humano:{entrada.id}")
    monkeypatch.setattr("apps.conversas.envio.enviar", lambda **_: SimpleNamespace(
        resultado="enviada", mensagem=confirmacao, detalhe=""))
    central.ao_resposta(entrada)
    confirmacao.estado_envio = "aceito"
    confirmacao.save(update_fields=["estado_envio"])
    monkeypatch.setattr("apps.conversas.envio.enviar", lambda **_: pytest.fail("confirmacao repetida"))
    assert central.reconciliar_handoffs() == 1
    conversa.refresh_from_db()
    assert conversa.estado == "pessoa" and conversa.mensagens.count() == 2


def test_roteiro_episodio_concluido_recente_ate_encerrar_e_sem_duplicar():
    conversa = Conversa.objects.create(site_id="s1", canal="whatsapp", endereco="5511999999999")
    jornada = Jornada.objects.create(site_id="s1", slug="recuperar-acesso", gatilho="manual", ativa=True,
                                      central_entrada_aberta=True)
    versao = JornadaVersao.objects.create(jornada=jornada, numero=1,
        central_config={"central": True, "nome": "Recuperação", "gatilho": "manual",
                        "roteiro": "Use solicitar_recuperacao_acesso após confirmar o pedido.", "resposta": "humano"})
    Passo.objects.create(jornada_versao=versao, ordem=1, classe="relacional", canais=["whatsapp"])
    JornadaVersao.objects.filter(pk=versao.pk).update(publicada_em=timezone.now())
    episodios = []
    for i in range(2):
        episodio = Inscricao.objects.create(jornada=jornada,
            jornada_versao=versao, destinatario_id=f"conversa:{conversa.id}", site_id="s1",
            central_conversa_id=conversa.id, origem_event_id=uuid.uuid4(),
            estado="concluida", passo_atual=1, proximo_em=None)
        Inscricao.objects.filter(pk=episodio.pk).update(criada_em=timezone.now() - timedelta(days=2 - i))
        episodios.append(episodio)
    contexto = api.contexto_da_conversa(None, str(conversa.id), "s1")
    assert len(contexto["automacoes"]) == 1
    assert contexto["automacoes"][0]["inscricao_id"] == str(episodios[-1].id)
    assert "solicitar_recuperacao_acesso" in contexto["automacoes"][0]["roteiro"]
    jornada.ativa = False
    jornada.save(update_fields=["ativa"])
    assert api.contexto_da_conversa(None, str(conversa.id), "s1")["automacoes"] == []


def test_humano_tambem_usa_episodio_concluido(monkeypatch):
    conversa = Conversa.objects.create(site_id="s1", canal="whatsapp", endereco="5511999999999")
    jornada = Jornada.objects.create(site_id="s1", slug="recuperar", gatilho="manual", ativa=True)
    versao = JornadaVersao.objects.create(jornada=jornada, numero=1,
        central_config={"central": True, "resposta": "humano", "gatilho": "manual"})
    JornadaVersao.objects.filter(pk=versao.pk).update(publicada_em=timezone.now())
    episodio = Inscricao.objects.create(jornada=jornada, jornada_versao=versao,
        destinatario_id=f"conversa:{conversa.id}", site_id="s1", central_conversa_id=conversa.id,
        origem_event_id=uuid.uuid4(), estado="concluida", ancora_em=timezone.now() - timedelta(hours=1))
    entrada = MensagemDaConversa.objects.create(conversa=conversa, direcao="entrada", autor="lead",
        texto="Preciso de uma pessoa", estado_envio="recebida", ocorrida_em=timezone.now())
    saida = MensagemDaConversa.objects.create(conversa=conversa, direcao="saida", autor="agente",
        texto="Vamos ajudar", estado_envio="aceito", ocorrida_em=timezone.now(),
        chave_idempotencia=f"central-humano:{entrada.id}")
    monkeypatch.setattr("apps.conversas.envio.enviar", lambda **_: SimpleNamespace(
        resultado="enviada", mensagem=saida, detalhe=""))
    assert central.ao_resposta(entrada) == 1
    episodio.refresh_from_db()
    conversa.refresh_from_db()
    assert episodio.central_suspensa and conversa.estado == "pessoa"
