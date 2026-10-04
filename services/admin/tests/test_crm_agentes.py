"""A área dos agentes do CRM (`/admin/crm/agentes/`): trabalhos, última
decisão, versão da estratégia, custo e gasto do mês; e as estratégias por
papel, com ativar e voltar à anterior.

Os testes que leem os registros dos agentes precisam do app `apps.comercial`
(o coordenador). Sem ele, a página diz que a capacidade ainda não está
disponível — e isso também é testado aqui.
"""
from decimal import Decimal

import httpx
import pytest
import respx
from django.apps import apps as django_apps
from django.db import DatabaseError
from django.test import Client
from django.urls import reverse

from apps.auditoria.models import Registro
from apps.core import crm_agentes

SESSAO = "http://identidade:8000/interno/sessao/completa"
OPORTUNIDADE = "24e45be2-77bb-4a32-a388-78d2ce9adcad"

com_comercial = pytest.mark.skipif(
    not django_apps.is_installed("apps.comercial"),
    reason="o app apps.comercial (coordenador) ainda não está neste ramo",
)


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", "http://identidade:8000/interno")
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-identidade-teste")
    settings.ADMIN_EMAILS = "dono@example.com"


def dentro():
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={"autenticado": True, "id": "operador-real", "nome_exibido": "Dono", "email": "dono@example.com", "papel": None},
        )
    )
    c = Client()
    c.defaults["HTTP_COOKIE"] = "meshcraft_sessao=teste"
    return c


def test_visitante_nao_chega():
    assert Client().get(reverse("crm_agentes")).status_code == 302


@respx.mock
def test_sem_a_equipe_comercial_a_pagina_diz_que_ainda_nao_esta_disponivel(monkeypatch):
    monkeypatch.setattr(crm_agentes, "comercial_disponivel", lambda: False)
    c = dentro()
    r = c.get(reverse("crm_agentes"))
    assert r.status_code == 200
    assert "ainda não está disponível" in r.content.decode()
    r = c.post(reverse("crm_agentes_ativar", args=[1]), {"motivo": "x"})
    assert r.status_code == 302 and "recado=indisponivel" in r["Location"]
    r = c.post(reverse("crm_agentes_voltar", args=["abordagem"]))
    assert r.status_code == 302 and "recado=indisponivel" in r["Location"]


@respx.mock
def test_falha_ao_ler_os_registros_vira_aviso_e_nao_erro_500(monkeypatch):
    monkeypatch.setattr(crm_agentes, "comercial_disponivel", lambda: True)

    def quebra():
        raise DatabaseError("tabela ausente")

    monkeypatch.setattr(crm_agentes, "_modelos", quebra)
    r = dentro().get(reverse("crm_agentes"))
    assert r.status_code == 200
    assert "Não foi possível ler os registros dos agentes" in r.content.decode()


@respx.mock
def test_o_quadro_do_crm_leva_aos_agentes(monkeypatch):
    monkeypatch.setenv("LEADS_API_URL", "http://leads:8000/api/leads")
    monkeypatch.setenv("LEADS_API_TOKEN", "token-de-teste")
    respx.get("http://leads:8000/api/leads/crm").mock(return_value=httpx.Response(503))
    r = dentro().get(reverse("crm"))
    assert reverse("crm_agentes") in r.content.decode()


def test_contexto_resumido_e_curto():
    resumo = crm_agentes.contexto_resumido(
        {"oportunidade": "abc", "vazio": "", "perfil": {"resumo": "x" * 300}, "a": 1, "b": 2, "c": 3, "d": 4}
    )
    assert resumo[0] == ("oportunidade", "abc")
    assert all(chave != "vazio" for chave, _ in resumo)
    assert len(resumo) <= 5
    assert all(len(valor) <= 90 for _, valor in resumo)


# --- com o coordenador -------------------------------------------------------


def _trabalho(estado, n, **campos):
    from apps.comercial.models import TrabalhoComercial

    return TrabalhoComercial.objects.create(
        tipo=campos.pop("tipo", "atender_mensagem"),
        papel=campos.pop("papel", "atendimento"),
        estado=estado,
        chave_idempotencia=f"teste-painel-{estado}-{n}",
        **campos,
    )


@com_comercial
@respx.mock
def test_painel_mostra_grupos_ultima_decisao_versao_custo_e_limite():
    from apps.agentes.models import AutorizacaoDeGasto
    from apps.comercial import papeis
    from apps.comercial.models import DecisaoComercial

    AutorizacaoDeGasto.objects.all().delete()  # a migração 0002 já semeia uma autorização
    AutorizacaoDeGasto.objects.create(descricao="Robôs da equipe", destino="equipe", teto_mensal_usd=Decimal("10.00"), fonte="teste")
    estrategia = papeis.estrategia_ativa("atendimento")
    em_curso = _trabalho("executando", 1, oportunidade_id=OPORTUNIDADE, custo_usd=Decimal("0.250000"), motivo="")
    DecisaoComercial.objects.create(
        trabalho=em_curso, papel="atendimento", estrategia=estrategia, versao_estrategia=estrategia.versao,
        call_id="c1", acao="responder", ferramenta="consultar_oportunidade",
        contexto_usado={"pergunta": "Quanto custa o curso?"}, resultado="feito",
    )
    DecisaoComercial.objects.create(
        trabalho=em_curso, papel="atendimento", estrategia=estrategia, versao_estrategia=estrategia.versao,
        call_id="c2", acao="enviar_mensagem", ferramenta="enviar_whatsapp",
        contexto_usado={"canal": "whatsapp"}, resultado="incerto",
    )
    _trabalho("na_fila", 1, tipo="abordar", papel="abordagem")
    _trabalho("envio_incerto", 1)
    _trabalho("falhou", 1, motivo="O serviço de mensagens recusou o envio.")
    _trabalho("falhou", 2, motivo="Falha de teste escondida", teste=True)
    _trabalho("concluido", 1)

    r = dentro().get(reverse("crm_agentes"))
    html = r.content.decode()
    assert r.status_code == 200
    for texto in ("Em andamento · 1", "Na fila · 1", "Envio sem confirmação · 1", "Com falha · 1"):
        assert texto in html
    assert "enviar_whatsapp" in html and "Sem confirmação" in html
    assert "canal:</b> whatsapp" in html
    assert f"Estratégia: v{estrategia.versao}" in html
    assert "US$ 0.2500" in html or "US$ 0,2500" in html
    assert "O serviço de mensagens recusou o envio." in html
    assert "Falha de teste escondida" not in html
    assert "1 trabalho de teste fora desta lista" in html
    assert reverse("crm_oportunidade", args=[OPORTUNIDADE]) in html
    assert "Limite autorizado no mês (o mesmo dos robôs da equipe)" in html
    assert "10.00" in html or "10,00" in html

    r = dentro().get(reverse("crm_agentes"), {"testes": "mostrar"})
    assert "Falha de teste escondida" in r.content.decode()


@com_comercial
@respx.mock
def test_sem_limite_autorizado_a_pagina_diz_isso():
    from apps.agentes.models import AutorizacaoDeGasto

    AutorizacaoDeGasto.objects.all().delete()  # a migração 0002 já semeia uma autorização
    r = dentro().get(reverse("crm_agentes"))
    assert r.status_code == 200
    assert "Nenhum limite de gasto autorizado" in r.content.decode()


@com_comercial
@respx.mock
def test_estrategias_por_papel_nova_versao_voltar_e_ativar():
    from apps.comercial.models import EstrategiaComercial

    c = dentro()
    html = c.get(reverse("crm_agentes")).content.decode()
    for papel, nome in EstrategiaComercial.Papel.choices:
        assert f'id="papel-{papel}"' in html
        assert EstrategiaComercial.objects.get(papel=papel, ativa=True).versao == 1

    r = c.post(reverse("crm_agentes_nova", args=["abordagem"]), {"instrucoes": "Cumprimente pelo nome.", "motivo": "teste A", "ativar": "1"})
    assert r.status_code == 302 and "recado=nova_ativa" in r["Location"]
    v2 = EstrategiaComercial.objects.get(papel="abordagem", ativa=True)
    assert v2.versao == 2 and v2.instrucoes == "Cumprimente pelo nome."

    r = c.post(reverse("crm_agentes_voltar", args=["abordagem"]), {"motivo": "piorou"})
    assert "recado=voltou" in r["Location"]
    v1 = EstrategiaComercial.objects.get(papel="abordagem", ativa=True)
    assert v1.versao == 1
    assert any(m.get("motivo") == "piorou" for m in v1.historico)

    r = c.post(reverse("crm_agentes_ativar", args=[v2.pk]), {"motivo": "de novo"})
    assert "recado=ativada" in r["Location"]
    assert EstrategiaComercial.objects.get(papel="abordagem", ativa=True).versao == 2
    assert Registro.objects.filter(alvo__startswith="estrategia:abordagem").count() == 3

    html = c.get(reverse("crm_agentes") + "?recado=ativada").content.decode()
    assert "Versão posta no ar" in html
    assert "no ar: v2" in html and "Voltar à v1" in html


@com_comercial
@respx.mock
def test_nova_versao_sem_texto_e_papel_inexistente_nao_mudam_nada():
    from apps.comercial.models import EstrategiaComercial

    c = dentro()
    c.get(reverse("crm_agentes"))
    antes = EstrategiaComercial.objects.count()
    r = c.post(reverse("crm_agentes_nova", args=["atendimento"]), {"instrucoes": "   "})
    assert "recado=vazia" in r["Location"]
    r = c.post(reverse("crm_agentes_nova", args=["inventado"]), {"instrucoes": "x"})
    assert "recado=papel" in r["Location"]
    r = c.post(reverse("crm_agentes_ativar", args=[999999]))
    assert "recado=nao_encontrada" in r["Location"]
    r = c.post(reverse("crm_agentes_nova", args=["resultados"]), {"instrucoes": "Compare por versão.", "motivo": "proposta"})
    assert "recado=nova" in r["Location"]
    assert EstrategiaComercial.objects.count() == antes + 1
    assert EstrategiaComercial.objects.get(papel="resultados", ativa=True).versao == 1
    r = c.post(reverse("crm_agentes_voltar", args=["resultados"]))
    assert "recado=sem_anterior" in r["Location"]


@com_comercial
@respx.mock
def test_trabalho_escolhido_mostra_todas_as_decisoes_e_retomar_devolve_a_fila():
    from apps.comercial.models import DecisaoComercial, TrabalhoComercial

    c = dentro()
    falhou = _trabalho("falhou", 9, motivo="Modelo fora do ar.")
    DecisaoComercial.objects.create(
        trabalho=falhou, papel="atendimento", call_id="d1", acao="consultar", ferramenta="consultar_contato",
        entrada={"oportunidade_ref": OPORTUNIDADE}, resultado="feito",
    )
    DecisaoComercial.objects.create(
        trabalho=falhou, papel="atendimento", call_id="d2", acao="responder", ferramenta="consultar_pagamento",
        resultado="indisponivel",
    )
    html = c.get(reverse("crm_agentes"), {"trabalho": falhou.pk}).content.decode()
    assert f"Trabalho #{falhou.pk}" in html
    assert "consultar_contato" in html and "consultar_pagamento" in html and "Capacidade indisponível" in html
    assert reverse("crm_agentes_retomar", args=[falhou.pk]) in html

    r = c.post(reverse("crm_agentes_retomar", args=[falhou.pk]))
    assert r.status_code == 302 and "recado=retomado" in r["Location"]
    falhou.refresh_from_db()
    assert falhou.estado == "na_fila"
    assert Registro.objects.filter(alvo=f"trabalho_comercial:{falhou.pk}").exists()

    concluido = _trabalho("concluido", 9)
    r = c.post(reverse("crm_agentes_retomar", args=[concluido.pk]))
    assert "recado=nao_retomado" in r["Location"]
    assert TrabalhoComercial.objects.get(pk=concluido.pk).estado == "concluido"
    r = c.post(reverse("crm_agentes_retomar", args=[999999]))
    assert "recado=nao_retomado" in r["Location"]
    # Um número de trabalho que não existe não derruba a página.
    assert c.get(reverse("crm_agentes"), {"trabalho": "999999"}).status_code == 200


@com_comercial
@respx.mock
def test_proposta_do_otimizador_aparece_para_por_no_ar_e_desligado_avisa(monkeypatch):
    from apps.comercial import papeis

    monkeypatch.setenv("COMERCIAL_AGENTES", "desligado")
    papeis.estrategia_ativa("abordagem")
    proposta = papeis.propor_versao("abordagem", "Fale da carga horária.", criada_por="agente:resultados",
                                    motivo="mais respostas na v1", origem="otimizador")
    html = dentro().get(reverse("crm_agentes")).content.decode()
    assert f"Proposta v{proposta.versao}" in html and "mais respostas na v1" in html
    assert reverse("crm_agentes_ativar", args=[proposta.pk]) in html
    assert "desligados neste ambiente" in html
    assert "enviar_mensagem" in html  # ferramentas do papel de abordagem


@respx.mock
def test_retomar_sem_a_equipe_comercial_nao_quebra(monkeypatch):
    monkeypatch.setattr(crm_agentes, "comercial_disponivel", lambda: False)
    r = dentro().post(reverse("crm_agentes_retomar", args=[1]))
    assert r.status_code == 302 and "recado=indisponivel" in r["Location"]


@com_comercial
@respx.mock
@pytest.mark.parametrize("valor", ["²", "٣", "9" * 40, "-1", " 1", "1e3", "１"])
def test_trabalho_com_valor_estranho_na_url_nao_derruba_a_pagina(valor):
    c = dentro()
    r = c.get(reverse("crm_agentes"), {"trabalho": valor})
    assert r.status_code == 200
    assert "Trabalho #" not in r.content.decode()


@com_comercial
@respx.mock
def test_voltar_duas_vezes_com_a_mesma_tela_nao_desfaz_a_volta():
    from apps.comercial import papeis
    from apps.comercial.models import EstrategiaComercial

    c = dentro()
    c.get(reverse("crm_agentes"))
    v2 = papeis.propor_versao("abordagem", "Versão 2.", criada_por="a", motivo="m", origem="painel")
    papeis.ativar(v2, "a", "m")
    html = c.get(reverse("crm_agentes")).content.decode()
    assert 'name="versao_no_ar" value="2"' in html
    corpo = {"motivo": "piorou", "versao_no_ar": "2"}
    r1 = c.post(reverse("crm_agentes_voltar", args=["abordagem"]), corpo)
    assert "recado=voltou" in r1["Location"]
    r2 = c.post(reverse("crm_agentes_voltar", args=["abordagem"]), corpo)
    assert "recado=mudou" in r2["Location"]
    assert EstrategiaComercial.objects.get(papel="abordagem", ativa=True).versao == 1


@com_comercial
@respx.mock
def test_guardar_o_mesmo_texto_duas_vezes_nao_cria_versao_repetida():
    from apps.comercial.models import EstrategiaComercial

    c = dentro()
    c.get(reverse("crm_agentes"))
    corpo = {"instrucoes": "Fale da carga horária.", "motivo": "teste"}
    c.post(reverse("crm_agentes_nova", args=["abordagem"]), corpo)
    c.post(reverse("crm_agentes_nova", args=["abordagem"]), corpo)
    assert EstrategiaComercial.objects.filter(papel="abordagem", instrucoes="Fale da carga horária.").count() == 1


def _em_paralelo(n, funcao):
    import threading

    from django.db import connection

    barreira = threading.Barrier(n)
    erros, resultados = [], []

    def roda(i):
        try:
            barreira.wait(timeout=10)
            resultados.append(funcao(i))
        except Exception as erro:  # noqa: BLE001
            erros.append(repr(erro))
        finally:
            connection.close()

    fios = [threading.Thread(target=roda, args=(i,)) for i in range(n)]
    for f in fios:
        f.start()
    for f in fios:
        f.join()
    return erros, resultados


def _fora_da_transacao(funcao):
    """Roda em outra thread, com conexão própria que confirma de verdade."""
    erros, resultados = _em_paralelo(1, lambda _i: funcao())
    assert erros == []
    return resultados[0]


@com_comercial
def test_duas_pessoas_ativando_ou_guardando_ao_mesmo_tempo_nao_dao_erro():
    """Threads de verdade, cada uma com a sua conexão, fora da transação do
    teste (o `flush` do pytest-django não pode truncar a auditoria, que é
    append-only). Por isso a preparação e a limpeza também rodam em thread."""
    from apps.comercial import papeis
    from apps.comercial.models import EstrategiaComercial

    def preparar():
        EstrategiaComercial.objects.filter(papel="abordagem").delete()
        papeis.estrategia_ativa("abordagem")
        a = papeis.propor_versao("abordagem", "A", criada_por="x", motivo="m", origem="painel")
        b = papeis.propor_versao("abordagem", "B", criada_por="x", motivo="m", origem="painel")
        return a, b

    def limpar():
        EstrategiaComercial.objects.filter(papel="abordagem").delete()

    def contar():
        return (
            EstrategiaComercial.objects.filter(papel="abordagem", ativa=True).count(),
            list(EstrategiaComercial.objects.filter(papel="abordagem").values_list("versao", flat=True)),
        )

    try:
        a, b = _fora_da_transacao(preparar)
        erros, _ = _em_paralelo(2, lambda i: papeis.ativar([a, b][i], f"p{i}", "m"))
        assert erros == []
        no_ar, _ = _fora_da_transacao(contar)
        assert no_ar == 1

        erros, _ = _em_paralelo(
            4, lambda i: papeis.propor_versao("abordagem", f"texto {i}", criada_por="x", motivo="m", origem="painel")
        )
        assert erros == []
        _, versoes = _fora_da_transacao(contar)
        assert len(versoes) == len(set(versoes)) == 7
    finally:
        _fora_da_transacao(limpar)
