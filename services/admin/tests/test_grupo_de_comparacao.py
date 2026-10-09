"""O grupo de comparação: leads que ficam sem o agente para medir o efeito real dele.

Prova: percentual 0 não muda nada; 50% divide de forma estável; lead de comparação
não recebe abordagem do quiz, mas suas mensagens recebem atendimento; a tela de resultados diz
"ainda não dá para concluir" com amostra pequena; dado de um site não entra no outro;
o otimizador ignora o grupo; o percentual só muda com confirmação e deixa rastro.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import timedelta

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.auditoria.models import Registro
from apps.comercial import comparacao, coordenador, eventos, otimizador
from apps.comercial.models import (
    DecisaoComercial,
    MarcaDeComparacao,
    TrabalhoComercial,
)
from apps.core import crm_resultados

LEADS = "http://leads:8000/api/leads"
IDENTIDADE = "http://identidade:8000/interno"
DONO = "dono@exemplo.com"
E = TrabalhoComercial.Estado
T = TrabalhoComercial.Tipo


@pytest.fixture(autouse=True)
def ambiente(monkeypatch, settings):
    monkeypatch.setenv("LEADS_API_URL", LEADS)
    monkeypatch.setenv("LEADS_API_TOKEN", "token-do-par")
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    for nome in ("COMERCIAL_AGENTES", "MENSAGERIA_API_URL", "MENSAGERIA_API_TOKEN"):
        monkeypatch.delenv(nome, raising=False)
    settings.ADMIN_EMAILS = DONO


def _envelope(evento: str, data: dict) -> dict:
    return {"event": evento, "version": 1, "event_id": str(uuid.uuid4()),
            "occurred_at": timezone.now().isoformat(), "data": data}


def _quiz(email: str, site="site-1", sessao=None):
    return _envelope("quiz.completado", {
        "site_id": site, "quiz_slug": "crivo", "result_key": "iniciante", "version_key": "v3",
        "lead": {"email": email, "name": "Pessoa"}, "utm": {"utm_source": "instagram"},
        "submissao_id": str(uuid.uuid4()), "sessao": sessao or str(uuid.uuid4()), "respostas": []})


def _emails(quantos: int, prefixo="lead"):
    return [f"{prefixo}{i}@meshcraft.test" for i in range(quantos)]


def _do_grupo(grupo: str, site="site-1", percentual=50, prefixo="x") -> str:
    """Um e-mail que a conta põe neste grupo com este percentual."""
    for i in range(10000):
        email = f"{prefixo}{i}@meshcraft.test"
        if comparacao.grupo_do_contato(site, email, percentual) == grupo:
            return email
    raise AssertionError("não achou")


# ---------------------------------------------------------------- a conta


def test_percentual_zero_poe_todo_mundo_no_agente():
    assert comparacao.percentual() == 0
    assert {comparacao.grupo_do_contato("site-1", e, 0) for e in _emails(300)} == {comparacao.GRUPO_AGENTE}
    assert {comparacao.grupo_do_contato("site-1", e, comparacao.percentual()) for e in _emails(50)} == {
        comparacao.GRUPO_AGENTE}


def test_cinquenta_por_cento_divide_e_o_mesmo_lead_cai_sempre_no_mesmo_grupo():
    emails = _emails(400)
    primeira = [comparacao.grupo_do_contato("site-1", e, 50) for e in emails]
    segunda = [comparacao.grupo_do_contato("site-1", e, 50) for e in emails]
    assert primeira == segunda
    sem_agente = primeira.count(comparacao.GRUPO_COMPARACAO)
    assert 140 <= sem_agente <= 260  # perto da metade
    # Sem sorteio por execução: a conta é um hash fixo, o mesmo em qualquer máquina.
    soma = hashlib.sha256(b"grupo-de-comparacao:site-1:ana@meshcraft.test").hexdigest()
    esperado = comparacao.GRUPO_COMPARACAO if int(soma[:8], 16) % 100 < 50 else comparacao.GRUPO_AGENTE
    assert comparacao.grupo_do_contato("site-1", "ana@meshcraft.test", 50) == esperado
    # Quem cai na comparação com 20% também cai com 50% (o grupo só cresce).
    for e in emails:
        if comparacao.grupo_do_contato("site-1", e, 20) == comparacao.GRUPO_COMPARACAO:
            assert comparacao.grupo_do_contato("site-1", e, 50) == comparacao.GRUPO_COMPARACAO


def test_o_mesmo_email_em_outro_site_e_outra_pessoa_para_a_conta():
    email = _do_grupo(comparacao.GRUPO_COMPARACAO)
    outros = {comparacao.grupo_do_contato(f"site-{n}", email, 50) for n in range(40)}
    assert outros == {comparacao.GRUPO_COMPARACAO, comparacao.GRUPO_AGENTE}
    assert comparacao.chave_do_contato("site-1", email) != comparacao.chave_do_contato("site-2", email)


@pytest.mark.django_db
def test_marca_guarda_o_grupo_da_primeira_vez_mesmo_se_o_percentual_mudar():
    comparacao.definir_percentual(50, "dono")
    sem = _do_grupo(comparacao.GRUPO_COMPARACAO)
    assert comparacao.decidir("site-1", sem) == comparacao.GRUPO_COMPARACAO
    comparacao.definir_percentual(0, "dono")
    assert comparacao.decidir("site-1", sem) == comparacao.GRUPO_COMPARACAO  # não foi movido
    novo = _do_grupo(comparacao.GRUPO_COMPARACAO, prefixo="novo")
    assert comparacao.decidir("site-1", novo) == comparacao.GRUPO_AGENTE  # percentual 0 vale para quem chega agora
    assert MarcaDeComparacao.objects.count() == 2


@pytest.mark.django_db
def test_captura_parcial_e_quiz_da_mesma_sessao_ficam_no_mesmo_grupo():
    comparacao.definir_percentual(50, "dono")
    telefone = "11988887777"
    grupo = comparacao.decidir("site-1", telefone, sessao="s-1")
    email = _do_grupo(comparacao.GRUPO_COMPARACAO if grupo == comparacao.GRUPO_AGENTE else comparacao.GRUPO_AGENTE)
    assert comparacao.grupo_do_contato("site-1", email, 50) != grupo
    # Na conclusão a pessoa deixou o e-mail: a sessão manda, o grupo é o mesmo.
    assert comparacao.decidir("site-1", email, sessao="s-1") == grupo
    assert MarcaDeComparacao.objects.filter(site_id="site-1", sessao="s-1").count() == 2
    # Dado de outro site com a mesma sessão não herda o grupo.
    assert MarcaDeComparacao.objects.filter(site_id="site-2").count() == 0


@pytest.mark.django_db
def test_marca_nao_guarda_email_nem_telefone():
    comparacao.definir_percentual(50, "dono")
    comparacao.decidir("site-1", "ana@meshcraft.test", sessao="s-9")
    marca = MarcaDeComparacao.objects.get()
    assert "ana@meshcraft.test" not in str(marca.__dict__) and len(marca.chave) == 64


# ---------------------------------------------------------------- os gatilhos


@pytest.mark.django_db
def test_percentual_zero_nao_muda_nada_no_quiz():
    for email in _emails(12):
        eventos.tratar("eventos.quiz.completado", _quiz(email))
    assert TrabalhoComercial.objects.filter(tipo=T.ANALISAR_LEAD).count() == 12
    assert set(MarcaDeComparacao.objects.values_list("grupo", flat=True)) == {comparacao.GRUPO_AGENTE}


@pytest.mark.django_db
def test_lead_da_comparacao_nao_vira_trabalho_e_o_do_agente_continua_igual():
    comparacao.definir_percentual(50, "dono")
    sem = _do_grupo(comparacao.GRUPO_COMPARACAO, prefixo="sem")
    com = _do_grupo(comparacao.GRUPO_AGENTE, prefixo="com")
    assert eventos.tratar("eventos.quiz.completado", _quiz(sem)) is None
    trabalho = eventos.tratar("eventos.quiz.completado", _quiz(com))
    assert not TrabalhoComercial.objects.filter(chave_da_conversa__contains=sem).exists()
    assert trabalho.entrada["grupo"] == comparacao.GRUPO_AGENTE
    # A marca fica gravada para os dois.
    grupos = dict(MarcaDeComparacao.objects.values_list("chave", "grupo"))
    assert grupos[comparacao.chave_do_contato("site-1", sem)] == comparacao.GRUPO_COMPARACAO
    assert grupos[comparacao.chave_do_contato("site-1", com)] == comparacao.GRUPO_AGENTE
    # De novo (outro quiz, outra entrega): o mesmo lead, o mesmo grupo, ainda sem trabalho.
    assert eventos.tratar("eventos.quiz.completado", _quiz(sem)) is None
    assert TrabalhoComercial.objects.count() == 1


@pytest.mark.django_db
def test_captura_parcial_do_grupo_de_comparacao_nao_vira_trabalho_e_a_conclusao_tambem_nao():
    comparacao.definir_percentual(50, "dono")
    sem = _do_grupo(comparacao.GRUPO_COMPARACAO)
    parcial = {"site_id": "site-1", "sessao": "sess-77", "quiz_slug": "crivo", "version_key": "v3",
               "lead": {"email": sem, "name": "Ana"}, "respostas": [], "captura_id": "cap-7"}
    assert eventos.tratar("eventos.quiz.captura_parcial", _envelope("quiz.captura_parcial", parcial)) is None
    assert eventos.tratar("eventos.quiz.completado", _quiz(sem, sessao="sess-77")) is None
    assert not TrabalhoComercial.objects.exists()


def _mensagem(contato_id="lead-1", conversa="conv-1", site="site-1"):
    return _envelope("mensagem.recebida", {
        "conversa_id": conversa, "mensagem_id": str(uuid.uuid4()), "canal": "whatsapp", "site": site,
        "site_id": site, "lead": contato_id, "lead_ligacao": "ligada", "texto": "Preciso de ajuda",
        "estado_conversa": "agente"})


@pytest.mark.django_db
def test_mensagem_de_quem_esta_no_grupo_de_comparacao_tambem_recebe_atendimento():
    comparacao.definir_percentual(50, "dono")
    sem = _do_grupo(comparacao.GRUPO_COMPARACAO)
    comparacao.decidir("site-1", sem)
    comparacao.ligar_contato("site-1", sem, "lead-1")  # a ficha foi achada alguma vez
    trabalho = eventos.tratar("eventos.mensagem.recebida", _mensagem("lead-1"))
    assert trabalho is not None and trabalho.tipo == T.ATENDER_MENSAGEM
    # Outro lead, do grupo do agente, segue sendo atendido.
    com = _do_grupo(comparacao.GRUPO_AGENTE)
    comparacao.decidir("site-1", com)
    comparacao.ligar_contato("site-1", com, "lead-2")
    assert eventos.tratar("eventos.mensagem.recebida", _mensagem("lead-2", "conv-2")) is not None
    # O mesmo id de contato em outro site não herda o grupo.
    assert eventos.tratar("eventos.mensagem.recebida", _mensagem("lead-1", "conv-3", site="site-2")) is not None


@pytest.mark.django_db
@respx.mock
def test_primeira_mensagem_do_grupo_de_comparacao_chega_ao_atendente(monkeypatch):
    comparacao.definir_percentual(50, "dono")
    sem = _do_grupo(comparacao.GRUPO_COMPARACAO)
    comparacao.decidir("site-1", sem)  # marcada no quiz, sem conhecer o id do contato ainda
    ficha = respx.get(f"{LEADS}/leads/lead-1").respond(200, json={"id": "lead-1", "email": sem, "nome": "Ana"})
    respx.route(url__startswith="http://").respond(404, json={"detail": "sem esta rota"})
    chamadas = []
    def atender(trabalho):
        chamadas.append(trabalho.pk)
        coordenador.terminar(trabalho, E.CONCLUIDO)
    monkeypatch.setattr(coordenador, "_atender", atender)
    eventos.tratar("eventos.mensagem.recebida", _mensagem("lead-1"))
    assert TrabalhoComercial.objects.count() == 1

    trabalho = coordenador.rodar_um("t1")
    trabalho.refresh_from_db()
    assert ficha.called
    assert trabalho.estado == E.CONCLUIDO and chamadas == [trabalho.pk]
    assert eventos.tratar("eventos.mensagem.recebida", _mensagem("lead-1", "conv-1")) is not None
    assert TrabalhoComercial.objects.count() == 2


@pytest.mark.django_db
@respx.mock
@pytest.mark.parametrize("status", [500, 404])
def test_sem_a_ficha_a_mensagem_ainda_chega_ao_atendente(status, monkeypatch):
    comparacao.definir_percentual(50, "dono")
    sem = _do_grupo(comparacao.GRUPO_COMPARACAO)
    comparacao.decidir("site-1", sem)
    respx.get(f"{LEADS}/leads/lead-1").respond(status, json={"detail": "fora"})
    respx.route(url__startswith="http://").respond(404, json={"detail": "sem esta rota"})
    chamadas = []
    def atender(trabalho):
        chamadas.append(trabalho.pk)
        coordenador.terminar(trabalho, E.CONCLUIDO)
    monkeypatch.setattr(coordenador, "_atender", atender)
    eventos.tratar("eventos.mensagem.recebida", _mensagem("lead-1"))

    trabalho = coordenador.rodar_um("t1")
    trabalho.refresh_from_db()
    assert chamadas == [trabalho.pk] and trabalho.estado == E.CONCLUIDO


# ---------------------------------------------------------------- o otimizador


@pytest.mark.django_db
def test_otimizador_ignora_o_grupo_de_comparacao_nas_contas_de_versoes():
    def abordagem(grupo):
        trabalho, _ = coordenador.criar(
            T.ABORDAR, f"x:{uuid.uuid4().hex}", site_id="site-1", oportunidade_id=uuid.uuid4().hex[:8],
            entrada={"quiz": "crivo", "grupo": grupo}, estado=E.CONCLUIDO)
        DecisaoComercial.objects.create(trabalho=trabalho, papel="abordagem", versao_estrategia=1,
                                        call_id="c1", resultado="decidido")
        return trabalho

    abordagem("agente")
    abordagem("comparacao")
    abordagem("comparacao")
    linha = otimizador.numeros("abordagem")["versoes"]
    assert [(v["versao"], v["abordagens"]) for v in linha] == [(1, 1)]


# ---------------------------------------------------------------- a tela de resultados


def _oportunidade(site, email, quiz="crivo", campanha="primavera", n=[0]):
    n[0] += 1
    chaves = [comparacao.chave_do_contato(site, comparacao.quem_e(email))]
    return {"id": f"op-{n[0]}", "lead_id": f"l-{n[0]}", "quiz": quiz, "campanha": campanha,
            "criada_em": timezone.now().isoformat(), "site_id": site, "chaves_de_contato": chaves}


def _compra(oportunidade, oferta="of-crivo", liquido=1000):
    return {"pedido_id": f"p-{oportunidade['id']}", "oportunidade_id": oportunidade["id"],
            "lead_id": oportunidade["lead_id"], "quiz": oportunidade["quiz"], "campanha": oportunidade["campanha"],
            "oferta": oferta, "aprovado_em": timezone.now().isoformat(), "aprovado_centavos": liquido,
            "estornos_centavos": 0, "liquido_centavos": liquido, "recuperada": False, "revertida": False}


def _grupos_marcados(site, com: int, sem: int, vendas_com: int, vendas_sem: int):
    """Marca `com` leads do agente e `sem` da comparação; devolve (oportunidades, compras)."""
    comparacao.definir_percentual(50, "dono")
    ops, compras = [], []
    for grupo, quantos, vendas, prefixo in ((comparacao.GRUPO_AGENTE, com, vendas_com, "c"),
                                            (comparacao.GRUPO_COMPARACAO, sem, vendas_sem, "s")):
        for i in range(quantos):
            email = _do_grupo(grupo, site=site, prefixo=f"{prefixo}{site}{i}-")
            assert comparacao.decidir(site, email) == grupo
            op = _oportunidade(site, email)
            ops.append(op)
            if i < vendas:
                compras.append(_compra(op))
    return ops, compras


@pytest.mark.django_db
def test_amostra_pequena_diz_que_ainda_nao_da_para_concluir():
    ops, compras = _grupos_marcados("site-1", 6, 4, 2, 1)
    r = crm_resultados.comparacao_com_e_sem_agente({"oportunidades": ops, "compras": compras}, {})
    bloco = r["blocos"][0]
    assert bloco["geral"]["conclusivo"] is False
    assert bloco["geral"]["com"]["pessoas"] == 6 and bloco["geral"]["sem"]["pessoas"] == 4
    assert bloco["geral"]["com"]["compras"] == 2 and bloco["geral"]["sem"]["compras"] == 1
    assert bloco["geral"]["diferenca"]["conversao_pontos"] == round((2 / 6 - 1 / 4) * 100, 1)
    assert bloco["linhas"][0]["conclusivo"] is False and bloco["ofertas"][0]["conclusivo"] is False


@pytest.mark.django_db
def test_amostra_suficiente_nos_dois_grupos_conclui():
    minimo = crm_resultados.AMOSTRA_MINIMA_PESSOAS
    vendas = crm_resultados.AMOSTRA_MINIMA_VENDAS
    ops, compras = _grupos_marcados("site-1", minimo, minimo, vendas + 3, vendas)
    r = crm_resultados.comparacao_com_e_sem_agente({"oportunidades": ops, "compras": compras}, {})
    geral = r["blocos"][0]["geral"]
    assert geral["conclusivo"] is True and geral["com"]["suficiente"] and geral["sem"]["suficiente"]
    assert geral["diferenca"]["liquido_por_pessoa_centavos"] == round(1000 * (vendas + 3) / minimo) - round(
        1000 * vendas / minimo)


@pytest.mark.django_db
def test_dado_de_um_site_nao_entra_no_outro_nem_lead_sem_marca_entra():
    ops_a, compras_a = _grupos_marcados("site-a", 5, 3, 1, 1)
    ops_b, compras_b = _grupos_marcados("site-b", 4, 2, 0, 1)
    # Lead de antes do recurso: sem marca, fora da conta.
    antigo = _oportunidade("site-a", "antigo@meshcraft.test")
    dados = {"oportunidades": ops_a + ops_b + [antigo], "compras": compras_a + compras_b + [_compra(antigo)]}
    r = crm_resultados.comparacao_com_e_sem_agente(dados, {})
    assert r["varios_sites"] is True and r["marcados"] == 14
    por_site = {b["site_id"]: b["geral"] for b in r["blocos"]}
    assert (por_site["site-a"]["com"]["pessoas"], por_site["site-a"]["sem"]["pessoas"]) == (5, 3)
    assert (por_site["site-b"]["com"]["pessoas"], por_site["site-b"]["sem"]["pessoas"]) == (4, 2)
    assert por_site["site-a"]["com"]["compras"] == 1 and por_site["site-b"]["com"]["compras"] == 0
    # Filtrando um site, a marca do outro não vale.
    so_a = crm_resultados.comparacao_com_e_sem_agente(dados, {"site_id": "site-a"})
    assert [b["site_id"] for b in so_a["blocos"]] == ["site-a"]
    # O e-mail do site A com a chave do site B não casa com nada.
    email = _do_grupo(comparacao.GRUPO_COMPARACAO, site="site-a", prefixo="solto")
    comparacao.decidir("site-a", email)
    intruso = _oportunidade("site-b", email)
    assert crm_resultados.comparacao_com_e_sem_agente(
        {"oportunidades": [intruso], "compras": []}, {})["marcados"] == 0


@pytest.mark.django_db
def test_lead_marcado_com_percentual_zero_nao_entra_na_conta_dos_dois_grupos():
    # O coordenador ligado com percentual 0 (padrão) marca todo lead como "agente", sem par.
    antigos = []
    for i in range(5):
        email = f"zero{i}@meshcraft.test"
        assert comparacao.decidir("site-1", email) == comparacao.GRUPO_AGENTE
        antigos.append(_oportunidade("site-1", email))
    ops, compras = _grupos_marcados("site-1", 0, 1, 0, 0)
    r = crm_resultados.comparacao_com_e_sem_agente({"oportunidades": antigos + ops, "compras": compras}, {})
    assert r["marcados"] == 1
    assert r["blocos"][0]["geral"]["com"]["pessoas"] == 0 and r["blocos"][0]["geral"]["sem"]["pessoas"] == 1


@pytest.mark.django_db
def test_marca_de_teste_fica_fora_da_comparacao():
    comparacao.definir_percentual(50, "dono")
    email = _do_grupo(comparacao.GRUPO_COMPARACAO)
    comparacao.decidir("site-1", email, teste=True)
    r = crm_resultados.comparacao_com_e_sem_agente(
        {"oportunidades": [_oportunidade("site-1", email)], "compras": []}, {})
    assert r["marcados"] == 0


def _dentro():
    respx.get(f"{IDENTIDADE}/sessao/completa").mock(return_value=httpx.Response(200, json={
        "autenticado": True, "id": "operador-real", "nome_exibido": "Dono", "email": DONO, "papel": None}))
    c = Client()
    c.defaults["HTTP_COOKIE"] = "meshcraft_sessao=teste"
    return c


def _fatos(ops, compras):
    return {"moeda": "BRL", "filtros": {}, "totais": {
        "elegiveis": len(ops), "compradores": len(compras), "conversao": 0.1, "compras_aprovadas": len(compras),
        "compras_revertidas": 0, "compras_recuperadas": 0, "aprovado_centavos": 0, "estornos_centavos": 0,
        "liquido_centavos": 0},
        "por_quiz": [], "por_campanha": [], "por_oferta": [], "oportunidades": ops, "oportunidades_truncadas": False,
        "compras": compras, "testes_fora": {}}


@pytest.mark.django_db
@respx.mock
def test_tela_em_zero_diz_que_nada_foi_separado_e_com_amostra_pequena_diz_inconclusivo():
    respx.get(LEADS + "/resultados/comerciais").mock(return_value=httpx.Response(200, json=_fatos([], [])))
    html = _dentro().get(reverse("crm_resultados")).content.decode()
    assert "Com agente x sem agente (grupo de comparação)" in html
    assert "em 0%" in html and "nada foi separado" in html

    ops, compras = _grupos_marcados("site-1", 6, 4, 2, 1)
    respx.get(LEADS + "/resultados/comerciais").mock(return_value=httpx.Response(200, json=_fatos(ops, compras)))
    html = _dentro().get(reverse("crm_resultados")).content.decode()
    assert "Sem agente (comparação)" in html
    assert "ainda não dá para concluir" in html and "Amostra insuficiente" in html
    assert "Não é lucro" in html or "não é lucro" in html


# ---------------------------------------------------------------- mudar o percentual


@pytest.mark.django_db
@respx.mock
def test_percentual_so_muda_com_confirmacao_e_deixa_rastro_na_auditoria():
    cliente = _dentro()
    url = reverse("crm_agentes_comparacao")
    assert comparacao.percentual() == 0
    r = cliente.post(url, {"percentual": "30"})  # sem confirmar
    assert r.status_code == 302 and "comparacao_sem_confirmacao" in r["Location"]
    assert comparacao.percentual() == 0 and not Registro.objects.filter(alvo="grupo-de-comparacao").exists()
    for torto in ("abc", "", "-5", "51", "100", "1.5", "²", "٣"):
        r = cliente.post(url, {"percentual": torto, "confirmo": "1"})
        assert "comparacao_invalida" in r["Location"], torto
    assert comparacao.percentual() == 0

    r = cliente.post(url, {"percentual": "30", "confirmo": "1"})
    assert "comparacao_mudou" in r["Location"] and comparacao.percentual() == 30
    linha = Registro.objects.get(alvo="grupo-de-comparacao")
    assert "de 0% para 30%" in linha.detalhe and linha.desfecho == Registro.OK
    assert "comparacao_igual" in cliente.post(url, {"percentual": "30", "confirmo": "1"})["Location"]
    assert Registro.objects.filter(alvo="grupo-de-comparacao").count() == 1

    pagina = cliente.get(reverse("crm_agentes")).content.decode()
    assert "Grupo de comparação" in pagina and 'name="confirmo"' in pagina and 'value="30"' in pagina
