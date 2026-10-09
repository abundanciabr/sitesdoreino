from copy import deepcopy

import pytest
from django.test import RequestFactory
from django.urls import reverse

from apps.encomendas import catalogo_curso, sandbox, fila_real
from apps.encomendas.models import ProjetoSandbox, ParticipacaoSandbox, ArquivoSandbox, EventoMarketplace, MovimentoMeshcoin
from apps.core import telas_sandbox, telas_fila_real, sessao
from tests.test_fila_real_marketplace import cenario  # noqa: F401


@pytest.mark.django_db
def test_rascunho_nao_troca_catalogo_nem_publica():
    antigo = sandbox.semear_projetos(site_id="escola-a")[0]
    antigos_ativos = set(ProjetoSandbox.objects.filter(site_id="escola-a", ativo=True).values_list("pk", flat=True))
    novos = catalogo_curso.preparar_projetos(site_id="escola-a")
    assert len(novos) == 9 and all(not p.ativo for p in novos)
    assert set(ProjetoSandbox.objects.filter(site_id="escola-a", ativo=True).values_list("pk", flat=True)) == antigos_ativos
    assert antigo.pk not in {p.pk for p in novos}


@pytest.mark.django_db
def test_ativacao_idempotente_preserva_trabalho_e_outro_site():
    antigo = sandbox.semear_projetos(site_id="escola-a")[0]
    antigo.prazo_dias, antigo.recompensa = 2, 10
    antigo.save()
    trabalho = sandbox.aceitar(site_id="escola-a", pessoa_id="aluno-a", projeto_id=antigo.pk)
    combinado = deepcopy(trabalho.termos)
    sandbox.semear_projetos(site_id="outra-escola")
    for _ in range(2):
        catalogo_curso.preparar_projetos(site_id="escola-a", ativar=True)
    trabalho.refresh_from_db()
    antigo.refresh_from_db()
    assert trabalho.termos == combinado and trabalho.status == "em_producao" and not antigo.ativo
    assert set(ProjetoSandbox.objects.filter(site_id="escola-a", ativo=True).values_list("slug", flat=True)) == catalogo_curso.SLUGS
    assert ProjetoSandbox.objects.filter(site_id="outra-escola", ativo=True).count() == 11


@pytest.mark.django_db
def test_aceite_usa_briefing_e_conclusao_nao_concede_meshcoin(monkeypatch):
    projetos = catalogo_curso.preparar_projetos(site_id="escola-a", ativar=True)
    p = sandbox.aceitar(site_id="escola-a", pessoa_id="aluno-a", projeto_id=projetos[0].pk, prazo_horas=24)
    assert p.termos["catalogo_curso"] == catalogo_curso.retrato(projetos[0].slug)
    assert p.termos["recompensa_tipo"] == "xp" and "recompensa" not in p.termos
    assert EventoMarketplace.objects.filter(tipo="encomendas.sandbox-trabalho-concluido.v1").count() == 0
    from apps.encomendas import analises_sandbox
    monkeypatch.setattr(analises_sandbox, "preparar", lambda *a, **k: None)
    arquivo = ArquivoSandbox.objects.create(site_id="escola-a", participacao=p, nome="modelo.blend", chave="teste-modelo", tamanho=10, mime="application/octet-stream", sha256="a" * 64)
    sandbox.entregar(site_id="escola-a", participacao_id=p.pk, pessoa_id="aluno-a", arquivos=[arquivo.pk])
    for _ in range(2):
        sandbox.aprovar(site_id="escola-a", participacao_id=p.pk, aprovador_id="equipe")
    assert MovimentoMeshcoin.objects.filter(participacao=p).count() == 0
    assert EventoMarketplace.objects.filter(tipo="encomendas.sandbox-trabalho-concluido.v1").count() == 1


@pytest.mark.django_db
def test_projeto_livre_preserva_item_no_aceite_e_exige_descricao():
    livre = next(p for p in catalogo_curso.preparar_projetos(site_id="escola-a", ativar=True) if p.categoria == "livre")
    with pytest.raises(sandbox.ErroSandbox):
        sandbox.aceitar(site_id="escola-a", pessoa_id="aluno-a", projeto_id=livre.pk, prazo_horas=48)
    assert not ParticipacaoSandbox.objects.filter(site_id="escola-a").exists()
    p = sandbox.aceitar(site_id="escola-a", pessoa_id="aluno-a", projeto_id=livre.pk, prazo_horas=48,
                        item_livre="Barco", descricao_livre="Barco de madeira, conforme minha referência.")
    assert p.termos["titulo"] == "Barco" and "Barco de madeira" in p.termos["briefing"]
    livre.briefing = "Descrição posterior"
    livre.save()
    p.refresh_from_db()
    assert "Descrição posterior" not in p.termos["briefing"]


@pytest.mark.django_db
def test_mesh_ja_concedido_permanece_no_historico_sem_credito_retroativo():
    from django.utils import timezone
    projeto = sandbox.semear_projetos(site_id="escola-a")[0]
    p = ParticipacaoSandbox.objects.create(site_id="escola-a", pessoa_id="aluno-antigo", projeto=projeto,
                                          termos={"recompensa": "50.00"}, status="aprovado",
                                          aceite_em=timezone.now(), prazo_ate=timezone.now())
    MovimentoMeshcoin.objects.create(site_id="escola-a", pessoa_id="aluno-antigo", participacao=p,
                                     valor=50, aprovador_id="escola")
    sandbox.aprovar(site_id="escola-a", participacao_id=p.pk, aprovador_id="escola")
    assert sandbox.saldo(site_id="escola-a", pessoa_id="aluno-antigo") == 50
    assert not EventoMarketplace.objects.filter(tipo="encomendas.sandbox-trabalho-concluido.v1").exists()


@pytest.mark.parametrize("modelo", catalogo_curso.PROJETOS)
def test_pedido_real_parte_do_mesmo_briefing_sem_alterar_valor(modelo):
    categoria, titulo, valor, ajustes, briefing = fila_real._dados({
        "projeto_curso": modelo["slug"], "valor_reais": "137,50", "ajustes_inclusos": 2,
    })
    assert categoria == modelo["categoria"] and titulo == modelo["titulo"]
    assert briefing["observacoes"] == modelo["briefing"]
    assert briefing["entregaveis"] == modelo["entregaveis"]
    assert briefing["catalogo_curso"] == catalogo_curso.retrato(modelo["slug"])
    assert valor == 13750 and ajustes == 2 and briefing["prazo_horas"] == 48


def test_cliente_personaliza_sem_trocar_template_ou_condicoes_financeiras():
    _, titulo, valor, ajustes, briefing = fila_real._dados({
        "projeto_curso": "curso-carro", "titulo": "Carro vermelho",
        "descricao": "Carro vermelho de duas portas.", "entregaveis": ["Fonte Blender"],
        "valor_cents": 20000, "ajustes_inclusos": 1,
    })
    assert titulo == "Carro vermelho" and briefing["observacoes"] == "Carro vermelho de duas portas."
    assert briefing["catalogo_curso"]["titulo"] == "Carro"
    assert valor == 20000 and ajustes == 1


def test_categoria_e_modelo_inexistente_nao_geram_pedido():
    with pytest.raises(fila_real.ErroMarketplace):
        fila_real._dados({"projeto_curso": "nao-existe", "valor_cents": 10000})


def test_descricao_do_formulario_do_cliente_e_preservada():
    _, _, valor, _, briefing = fila_real._dados({
        "projeto_curso": "curso-carro", "titulo": "Carro vermelho", "briefing": "Meu carro vermelho.",
        "entregaveis": "Arquivo .blend", "valor_cents": 22000,
    })
    assert briefing["observacoes"] == "Meu carro vermelho." and valor == 22000


@pytest.mark.django_db
def test_conclusao_real_emite_fato_uma_vez_sem_alterar_recebivel(cenario):
    from tests.test_faixas_eventos_marketplace import _aprovado
    from apps.encomendas.models import OutboxMarketplace, RecebivelMarketplace
    pedido = _aprovado(valor="137,50")
    antes = RecebivelMarketplace.objects.values("valor_liquido_cents", "status").get(pedido=pedido)
    pedido.save()
    eventos = OutboxMarketplace.objects.filter(event="encomendas.fila-trabalho-concluido", payload__pedido_id=str(pedido.pk))
    assert eventos.count() == 1
    assert eventos.get().payload["pessoa_id"] == "aluno-autorizado"
    assert RecebivelMarketplace.objects.values("valor_liquido_cents", "status").get(pedido=pedido) == antes


@pytest.mark.django_db
def test_seis_categorias_iguais_no_sandbox_e_fila_real(client, monkeypatch):
    catalogo_curso.preparar_projetos(site_id="escola-a", ativar=True)
    monkeypatch.setattr(sessao, "quem_e", lambda req: "aluno-a")
    monkeypatch.setattr(sessao, "site_desta_instalacao", lambda: "escola-a")
    monkeypatch.setattr(telas_sandbox, "_aluno_atual", lambda *a: True)
    monkeypatch.setenv("IDS_DO_PLANTAO", "equipe")
    monkeypatch.setattr(telas_fila_real, "_entrada", lambda req: ("escola-a", "aluno-a"))
    monkeypatch.setattr(telas_fila_real, "_papel", lambda *a: "aluno")
    monkeypatch.setattr(fila_real, "catalogo", lambda **k: {"pedidos": [], "trabalhos": []})
    for chave, nome, descricao, arte in catalogo_curso.CATEGORIAS:
        a = client.get(reverse("sandbox_catalogo"), {"categoria": chave})
        b = telas_fila_real.catalogo(RequestFactory().get("/cliente/", {"categoria": chave}))
        assert a.status_code == b.status_code == 200
        assert nome in a.content.decode() and nome in b.content.decode()
        assert "MESH" not in a.content.decode() and "Meshcoin" not in a.content.decode()
    assert client.get(reverse("sandbox_catalogo"), {"categoria": "chapeus"}).status_code == 404


@pytest.mark.django_db
def test_projeto_livre_formulario_e_privacidade(client, monkeypatch):
    livre = next(p for p in catalogo_curso.preparar_projetos(site_id="escola-a", ativar=True) if p.categoria == "livre")
    monkeypatch.setattr(sessao, "quem_e", lambda req: "aluno-a")
    monkeypatch.setattr(sessao, "site_desta_instalacao", lambda: "escola-a")
    monkeypatch.setattr(telas_sandbox, "_aluno_atual", lambda *a: True)
    monkeypatch.setenv("IDS_DO_PLANTAO", "equipe")
    r = client.get(reverse("sandbox_confirmar", args=[livre.pk]))
    assert r.status_code == 200 and b'name="item_livre"' in r.content and b'name="descricao_livre"' in r.content
    r = client.post(reverse("sandbox_aceitar", args=[livre.pk]), {
        "aceito_termos": "sim", "prazo_horas": 48, "item_livre": "Barco", "descricao_livre": "Barco com vela.",
    })
    assert r.status_code == 302
    p = ParticipacaoSandbox.objects.get(pessoa_id="aluno-a", site_id="escola-a")
    monkeypatch.setattr(sessao, "quem_e", lambda req: "outro-aluno")
    assert client.get(reverse("sandbox_trabalho", args=[p.pk])).status_code == 404
