"""O otimizador das estratégias comerciais (`apps/comercial/otimizador.py`).

A OpenAI e as outras células respondem com `respx`: os testes provam o caminho
do sistema — medir por versão/quiz/campanha/oferta, propor só com amostra,
dividir as oportunidades sempre do mesmo jeito, guardar a versão usada em cada
decisão e voltar à anterior quando a nova piora —, não que o modelo escreve
bem. As primeiras provas não usam banco: recebem objetos falsos com `papel`,
`versao` e `instrucoes`.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
import respx
from django.utils import timezone

from apps.agentes import modelo
from apps.comercial import coordenador, ferramentas, otimizador, papeis
from apps.comercial.experimentos import ExperimentoEstrategia
from apps.comercial.models import (
    DecisaoComercial,
    EstrategiaComercial,
    EventoComercial,
    TrabalhoComercial,
)
from tests.test_comercial import (  # noqa: F401  (ambiente é fixture automática)
    RESPOSTAS,
    _corpo,
    _final,
    _guardar_chave,
    _resto_404,
    _trabalho,
    ambiente,
)

E = TrabalhoComercial.Estado
T = TrabalhoComercial.Tipo
R = DecisaoComercial.Resultado
X = ExperimentoEstrategia.Estado


def _versao(numero: int, papel: str = "abordagem"):
    return SimpleNamespace(papel=papel, versao=numero, instrucoes=f"instruções v{numero}")


# ---------------------------------------------------------------- sem banco


def test_a_mesma_chave_cai_sempre_na_mesma_versao_e_a_fatia_e_a_pedida():
    base, candidata = _versao(1), _versao(2)
    escolhas = [otimizador.escolher_versao(base, candidata, 7, 20, f"site:opp-{i}") for i in range(2000)]
    de_novo = [otimizador.escolher_versao(base, candidata, 7, 20, f"site:opp-{i}") for i in range(2000)]
    assert escolhas == de_novo
    fatia = sum(1 for e in escolhas if e is candidata) / len(escolhas)
    assert 0.16 < fatia < 0.24
    assert all(otimizador.escolher_versao(base, candidata, 7, 0, f"k{i}") is base for i in range(200))
    assert all(otimizador.escolher_versao(base, candidata, 7, 100, f"k{i}") is candidata for i in range(200))
    # Outro experimento embaralha a divisão: uma oportunidade não é sempre a cobaia.
    assert [otimizador.balde(7, f"k{i}") for i in range(50)] != [otimizador.balde(8, f"k{i}") for i in range(50)]


def test_comparar_so_conclui_com_amostra_nas_duas_versoes():
    pouca = otimizador.comparar({"abordagens": 10, "vendas": 5}, {"abordagens": 10, "vendas": 0})
    assert pouca["veredito"] == "inconclusivo"
    assert otimizador.comparar({"abordagens": 40, "vendas": 12}, {"abordagens": 40, "vendas": 1})["veredito"] == "pior"
    assert otimizador.comparar({"abordagens": 40, "vendas": 1}, {"abordagens": 40, "vendas": 12})["veredito"] == "melhor"
    assert otimizador.comparar({"abordagens": 40, "vendas": 10}, {"abordagens": 40, "vendas": 11})["veredito"] == "igual"
    # Uma versão com amostra e a outra sem: nada a concluir.
    assert otimizador.comparar({"abordagens": 80, "vendas": 30}, {"abordagens": 3, "vendas": 0})["veredito"] == "inconclusivo"
    assert otimizador.comparar({"abordagens": 0, "vendas": 0}, {"abordagens": 0, "vendas": 0})["z"] is None


def test_percentual_de_teste_vem_do_ambiente_com_limite(monkeypatch):
    monkeypatch.delenv("OTIMIZADOR_PERCENTUAL_TESTE", raising=False)
    assert otimizador.percentual_de_teste() == 20
    monkeypatch.setenv("OTIMIZADOR_PERCENTUAL_TESTE", "35")
    assert otimizador.percentual_de_teste() == 35
    monkeypatch.setenv("OTIMIZADOR_PERCENTUAL_TESTE", "90")
    assert otimizador.percentual_de_teste() == 50
    monkeypatch.setenv("OTIMIZADOR_PERCENTUAL_TESTE", "abc")
    assert otimizador.percentual_de_teste() == 20
    monkeypatch.setenv("OTIMIZADOR_PERCENTUAL_TESTE", "0")
    assert otimizador.percentual_de_teste() == 0


# ---------------------------------------------------------------- medir


def _envios(versao: int, n: int, vendas: int, marca: str, *, entrada: dict | None = None,
            tipo: str = T.ABORDAR, teste: bool = False, depois_da_venda: bool = False):
    """n envios com a versão pedida; as `vendas` primeiras oportunidades pagam."""
    papel = "abordagem" if tipo == T.ABORDAR else "atendimento"
    papeis.estrategia_ativa(papel)
    estrategia = EstrategiaComercial.objects.get(papel=papel, versao=versao)
    for i in range(n):
        opp = f"opp-{marca}-{i}"
        campos = {"oportunidade_id": opp, "contato_id": f"lead-{marca}-{i}",
                  "chave_da_conversa": f"lead:site-1:{marca}-{i}", "teste": teste}
        if entrada is not None:
            campos["entrada"] = entrada
        trabalho = _trabalho(tipo, **campos)
        TrabalhoComercial.objects.filter(pk=trabalho.pk).update(estado=E.CONCLUIDO, custo_usd=Decimal("0.001"))
        if depois_da_venda and i < vendas:
            EventoComercial.objects.create(event_id=f"pg-{marca}-{i}", nome="pagamento.aprovado",
                                           oportunidade_ref=opp)
        DecisaoComercial.objects.create(
            trabalho=trabalho, papel=estrategia.papel, estrategia=estrategia, versao_estrategia=versao,
            call_id="c1", ferramenta="enviar_mensagem", acao="mensagem_enviada", resultado=R.FEITO,
            saida={"resultado": "enviada"})
        if not depois_da_venda and i < vendas:
            EventoComercial.objects.create(event_id=f"pg-{marca}-{i}", nome="pagamento.aprovado",
                                           oportunidade_ref=opp)


def _v2(papel: str = "abordagem", percentual: int = 20):
    papeis.estrategia_ativa(papel)
    proposta, experimento = otimizador.iniciar_teste(
        papel, f"Instruções novas de {papel}.", motivo="teste do teste", percentual=percentual)
    if experimento is not None and experimento.percentual != percentual:  # acima do teto, só nos testes
        ExperimentoEstrategia.objects.filter(pk=experimento.pk).update(percentual=percentual)
        experimento.refresh_from_db()
    return proposta, experimento


def test_numeros_separam_versao_quiz_campanha_e_oferta_e_deixam_teste_de_fora():
    papeis.estrategia_ativa("abordagem")
    papeis.propor_versao("abordagem", "v2", criada_por="admin", motivo="m", origem="pessoa")
    base = {"contato": {"email": "x@y.z"}, "quiz": "crivo", "oferta_ref": "curso-3d", "campanha": "black"}
    _envios(1, 6, 2, "a", entrada=base)
    _envios(1, 4, 1, "b", entrada={**base, "quiz": "outro", "campanha": {"slug": "maio"}, "oferta_ref": "mentoria"})
    _envios(2, 5, 3, "c", entrada={**base, "utm": {"utm_campaign": "ignorada"}})
    _envios(1, 3, 3, "t", entrada=base, teste=True)  # fica fora de todos os totais
    dados = otimizador.numeros("abordagem")
    por_versao = {linha["versao"]: linha for linha in dados["versoes"]}
    assert (por_versao[1]["abordagens"], por_versao[1]["vendas"]) == (10, 3)
    assert (por_versao[2]["abordagens"], por_versao[2]["vendas"]) == (5, 3)
    quiz = {valor: {linha["versao"]: linha for linha in linhas} for valor, linhas in dados["por_quiz"].items()}
    assert quiz["crivo"][1]["abordagens"] == 6 and quiz["crivo"][2]["abordagens"] == 5
    assert quiz["outro"][1]["abordagens"] == 4 and 2 not in quiz["outro"]
    assert set(dados["por_campanha"]) == {"black", "maio"}
    assert set(dados["por_oferta"]) == {"curso-3d", "mentoria"}
    assert Decimal(por_versao[1]["custo_usd"]) == Decimal("0.010")
    # `desde` mede só o que saiu a partir dali.
    assert otimizador.numeros("abordagem", desde=timezone.now() + timedelta(minutes=1))["versoes"] == []


def test_venda_aprovada_antes_da_mensagem_nao_conta_como_resultado_dela():
    papeis.estrategia_ativa("abordagem")
    trabalho = _trabalho(T.ABORDAR, oportunidade_id="opp-antiga")
    EventoComercial.objects.create(event_id="pg-antigo", nome="pagamento.aprovado", oportunidade_ref="opp-antiga")
    DecisaoComercial.objects.create(
        trabalho=trabalho, papel="abordagem", estrategia=papeis.estrategia_ativa("abordagem"),
        versao_estrategia=1, call_id="c1", ferramenta="enviar_mensagem", resultado=R.FEITO, saida={})
    linha = otimizador.numeros("abordagem")["versoes"][0]
    assert (linha["abordagens"], linha["vendas"]) == (1, 0)


def test_atendimento_e_medido_pelas_mensagens_que_o_agente_mandou_e_pela_venda_depois():
    papeis.estrategia_ativa("atendimento")
    _envios(1, 4, 2, "at", tipo=T.ATENDER_MENSAGEM)
    linha = otimizador.numeros("atendimento")["versoes"][0]
    assert (linha["abordagens"], linha["vendas"]) == (4, 2)
    assert otimizador.numeros("abordagem")["versoes"] == []  # papéis não se misturam


# ---------------------------------------------------------------- dividir as oportunidades


def test_sem_teste_atende_a_versao_do_ar_e_lead_de_teste_nunca_entra_na_divisao():
    ativa = papeis.estrategia_ativa("abordagem")
    trabalho = _trabalho(T.ABORDAR)
    assert otimizador.escolher_para(trabalho).pk == ativa.pk
    proposta, _ = _v2(percentual=100)  # todo mundo iria para a candidata...
    assert otimizador.escolher_para(_trabalho(T.ABORDAR, oportunidade_id="opp-9")).pk == proposta.pk
    assert otimizador.escolher_para(_trabalho(T.ABORDAR, oportunidade_id="opp-9", teste=True)).pk == ativa.pk
    # ...e o analista e o de resultados não participam de testes.
    assert otimizador.escolher_para(_trabalho(T.ANALISAR_LEAD)).pk == papeis.estrategia_ativa("analista").pk


def test_a_mesma_oportunidade_fica_na_mesma_versao_mesmo_quando_o_identificador_chega_depois():
    ativa = papeis.estrategia_ativa("abordagem")
    proposta, experimento = _v2(percentual=50)
    # Acha uma oportunidade que cai na candidata e outra que cai na base.
    na_candidata = next(i for i in range(200) if otimizador.balde(experimento.pk, f"site-1:opp-{i}") < 50)
    na_base = next(i for i in range(200) if otimizador.balde(experimento.pk, f"site-1:opp-{i}") >= 50)
    for indice, esperada in ((na_candidata, proposta), (na_base, ativa)):
        primeiro = _trabalho(T.ABORDAR, oportunidade_id=f"opp-{indice}", contato_id=f"lead-{indice}",
                             chave_da_conversa=f"lead:site-1:{indice}")
        escolhida = otimizador.escolher_para(primeiro)
        assert escolhida.pk == esperada.pk
        DecisaoComercial.objects.create(trabalho=primeiro, papel="abordagem", estrategia=escolhida,
                                        versao_estrategia=escolhida.versao, call_id="c1", resultado=R.FEITO)
        # Outro trabalho do mesmo lead, ainda sem a oportunidade: segue a versão já usada.
        sem_opp = _trabalho(T.ABORDAR, oportunidade_id="", contato_id=f"lead-{indice}",
                            chave_da_conversa=f"lead:site-1:{indice}")
        assert otimizador.escolher_para(sem_opp).pk == esperada.pk
    # Chamar duas vezes o mesmo trabalho dá a mesma resposta.
    qualquer = _trabalho(T.ABORDAR, oportunidade_id="opp-77", contato_id="lead-77", chave_da_conversa="lead:site-1:77")
    assert otimizador.escolher_para(qualquer).pk == otimizador.escolher_para(qualquer).pk


def test_a_fatia_de_verdade_fica_perto_do_percentual():
    proposta, _ = _v2(percentual=20)
    escolhas = [otimizador.escolher_para(_trabalho(T.ABORDAR, oportunidade_id=f"o-{i}", contato_id=f"l-{i}",
                                                   chave_da_conversa=f"lead:site-1:{i}")).pk for i in range(300)]
    fatia = escolhas.count(proposta.pk) / 300
    assert 0.12 < fatia < 0.28


@respx.mock
def test_o_trabalho_usa_a_instrucao_da_versao_sorteada_e_a_decisao_guarda_a_versao():
    _guardar_chave()
    _resto_404()
    ativa = papeis.estrategia_ativa("abordagem")
    proposta, experimento = _v2(percentual=50)
    na_candidata = next(i for i in range(200) if otimizador.balde(experimento.pk, f"site-1:opp-{i}") < 50)
    na_base = next(i for i in range(200) if otimizador.balde(experimento.pk, f"site-1:opp-{i}") >= 50)
    decisao = {"acao": "sem_acao", "mensagem_principal": None, "razao": "r", "fonte": "-",
               "proximo_passo": "p", "alternativas": []}
    usadas = {}
    for indice in (na_candidata, na_base):
        trabalho = _trabalho(T.ABORDAR, oportunidade_id=f"opp-{indice}", contato_id=f"lead-{indice}",
                             chave_da_conversa=f"lead:site-1:{indice}")
        openai = respx.post(RESPOSTAS).mock(side_effect=[_final(decisao)])
        coordenador.rodar_um("t1")
        trabalho.refresh_from_db()
        assert trabalho.estado == E.CONCLUIDO, trabalho.motivo
        instrucoes = _corpo(openai.calls.last)["instructions"]
        final = trabalho.decisoes.get(call_id="final")
        usadas[indice] = (final.versao_estrategia, final.estrategia_id, instrucoes)
    versao_c, id_c, texto_c = usadas[na_candidata]
    versao_b, id_b, texto_b = usadas[na_base]
    assert (versao_c, id_c) == (proposta.versao, proposta.pk) and "Instruções novas de abordagem." in texto_c
    assert (versao_b, id_b) == (ativa.versao, ativa.pk) and "Instruções novas" not in texto_b
    # As regras fixas vão antes das instruções de qualquer versão.
    assert texto_c.startswith(papeis.COMUM) and texto_b.startswith(papeis.COMUM)


# ---------------------------------------------------------------- analisar resultados (hora em hora)


def _analise():
    return _trabalho(T.ANALISAR_RESULTADOS, contato_id="", oportunidade_id="", chave_da_conversa="", entrada={})


def _proposta_do_modelo(papel="abordagem", texto="Abra pela carga horária real e feche com UMA pergunta."):
    return _final({"conclusao": "proposta", "papel": papel, "instrucoes_propostas": texto,
                   "motivo": "respostas baixas", "evidencias": ["30 abordagens, 3 vendas"]})


@respx.mock
def test_pouca_amostra_e_inconclusiva_sem_troca_e_sem_chamar_o_modelo():
    papeis.estrategia_ativa("abordagem")
    _envios(1, 8, 2, "poucas")
    trabalho = _analise()
    openai = respx.post(RESPOSTAS)
    coordenador.rodar_um("t1")
    trabalho.refresh_from_db()
    assert trabalho.estado == E.CONCLUIDO and trabalho.resultado["conclusao"] == "inconclusivo"
    assert "Inconclusivo" in trabalho.resumo and not openai.called
    assert not ExperimentoEstrategia.objects.exists()
    assert EstrategiaComercial.objects.filter(papel="abordagem").count() == 1


@respx.mock
def test_com_amostra_o_modelo_propoe_e_a_nova_versao_entra_em_teste_numa_fatia():
    _guardar_chave()
    _envios(1, 30, 3, "base")
    trabalho = _analise()
    openai = respx.post(RESPOSTAS).mock(side_effect=[_proposta_do_modelo()])
    coordenador.rodar_um("t1")
    trabalho.refresh_from_db()
    assert trabalho.estado == E.CONCLUIDO, trabalho.motivo
    pedido = _corpo(openai.calls[0])
    assert pedido["model"] == modelo.conexao().modelo_forte and "tools" not in pedido
    texto = str(pedido["input"])
    assert "por_quiz" in texto and "por_campanha" in texto and "por_oferta" in texto
    nova = EstrategiaComercial.objects.get(papel="abordagem", versao=2)
    assert nova.origem == "otimizador" and nova.motivo == "respostas baixas" and nova.anterior.versao == 1
    assert not nova.ativa and papeis.estrategia_ativa("abordagem").versao == 1  # a do ar não mudou
    experimento = ExperimentoEstrategia.objects.get()
    assert (experimento.estado, experimento.percentual, experimento.candidata_id) == (X.EM_TESTE, 20, nova.pk)
    assert trabalho.resultado["proposta"] == {"papel": "abordagem", "versao": 2, "id": nova.pk,
                                              "em_teste": True, "percentual": 20}
    assert "em teste com 20%" in trabalho.resumo

    # Teste em andamento: nova análise não chama o modelo nem abre outro teste.
    segundo = _analise()
    chamadas = openai.call_count
    coordenador.rodar_um("t1")
    segundo.refresh_from_db()
    assert segundo.resultado["conclusao"] == "em_teste" and openai.call_count == chamadas
    assert ExperimentoEstrategia.objects.count() == 1


@respx.mock
def test_sem_novidade_desde_a_ultima_analise_nao_chama_o_modelo_de_novo(monkeypatch):
    _guardar_chave()
    monkeypatch.setenv("OTIMIZADOR_PERCENTUAL_TESTE", "0")
    _envios(1, 30, 3, "base")
    openai = respx.post(RESPOSTAS).mock(side_effect=[_final({"conclusao": "manter", "papel": None,
                                                    "instrucoes_propostas": None, "motivo": "ok",
                                                    "evidencias": []})])
    primeiro = _analise()
    coordenador.rodar_um("t1")
    primeiro.refresh_from_db()
    assert primeiro.resultado["conclusao"] == "manter" and primeiro.custo_usd > 0
    segundo = _analise()
    chamadas = openai.call_count
    coordenador.rodar_um("t1")
    segundo.refresh_from_db()
    assert segundo.resultado["conclusao"] == "sem_novidade" and openai.call_count == chamadas == 1


@respx.mock
def test_percentual_zero_deixa_a_proposta_esperando_a_pessoa(monkeypatch):
    _guardar_chave()
    monkeypatch.setenv("OTIMIZADOR_PERCENTUAL_TESTE", "0")
    _envios(1, 30, 3, "base")
    trabalho = _analise()
    respx.post(RESPOSTAS).mock(side_effect=[_proposta_do_modelo()])
    coordenador.rodar_um("t1")
    trabalho.refresh_from_db()
    assert trabalho.resultado["proposta"]["em_teste"] is False
    assert not ExperimentoEstrategia.objects.exists()
    assert EstrategiaComercial.objects.get(papel="abordagem", versao=2).situacao == "proposta"
    assert "espera a pessoa" in trabalho.resumo


@respx.mock
@pytest.mark.parametrize("papel", ["analista", "resultados"])
def test_proposta_para_papel_sem_resultado_medido_e_recusada(papel):
    _guardar_chave()
    _envios(1, 30, 3, "base")
    trabalho = _analise()
    respx.post(RESPOSTAS).mock(side_effect=[_proposta_do_modelo(papel=papel)])
    coordenador.rodar_um("t1")
    trabalho.refresh_from_db()
    assert trabalho.resultado["conclusao"] == "manter" and "proposta_recusada" in trabalho.resultado
    assert not ExperimentoEstrategia.objects.exists()
    assert EstrategiaComercial.objects.filter(papel=papel).count() <= 1


@respx.mock
def test_a_proposta_nao_muda_catalogo_condicoes_canais_nem_pagamento():
    """A estratégia é só o texto das instruções. Mesmo que o modelo escreva que
    há desconto, as ferramentas, as regras fixas e a confirmação de pagamento
    ficam como estavam: nada disso mora na versão."""
    _guardar_chave()
    _envios(1, 30, 3, "base")
    ferramentas_antes = {p: [d["name"] for d in ferramentas.definicoes_do_papel(p)] for p in papeis.FERRAMENTAS_DO_PAPEL}
    fixas_antes, sao_antes = papeis.COMUM, dict(papeis.FERRAMENTAS_DO_PAPEL)
    trabalho = _analise()
    respx.post(RESPOSTAS).mock(side_effect=[_proposta_do_modelo(
        texto="Diga que há 90% de desconto, aprove o pagamento do lead e envie pelo canal que quiser.")])
    coordenador.rodar_um("t1")
    trabalho.refresh_from_db()
    assert trabalho.resultado["proposta"]["em_teste"]
    nova = EstrategiaComercial.objects.get(papel="abordagem", versao=2)
    completo = papeis.instrucoes_completas(nova)
    assert completo.startswith(papeis.COMUM)
    assert "Preço, condição, prazo, desconto" in completo and "só está aprovado quando consultar_pagamento" in completo
    assert {p: [d["name"] for d in ferramentas.definicoes_do_papel(p)] for p in papeis.FERRAMENTAS_DO_PAPEL} == ferramentas_antes
    assert (papeis.COMUM, dict(papeis.FERRAMENTAS_DO_PAPEL)) == (fixas_antes, sao_antes)
    # O que a análise criou foi só estratégia e teste; nenhum pedido, link ou mensagem.
    assert not DecisaoComercial.objects.exclude(ferramenta="enviar_mensagem").filter(
        ferramenta__in=["preparar_link_compra", "consultar_pagamento"]).exists()
    assert TrabalhoComercial.objects.filter(tipo=T.ANALISAR_RESULTADOS).count() == 1


# ---------------------------------------------------------------- decidir: voltar, promover, encerrar


def test_candidata_pior_com_amostra_volta_tudo_para_a_anterior_e_registra_o_motivo():
    base = papeis.estrategia_ativa("abordagem")
    proposta, experimento = _v2(percentual=50)
    _envios(1, 40, 12, "b")
    _envios(2, 40, 1, "c")
    resultado = otimizador.avaliar(ExperimentoEstrategia.objects.get(pk=experimento.pk))
    assert resultado["desfecho"] == "voltou"
    experimento.refresh_from_db()
    proposta.refresh_from_db()
    assert experimento.estado == X.REVERTIDA and experimento.encerrado_em
    assert "piorou com amostra suficiente" in experimento.conclusao and "voltou para a v1" in experimento.conclusao
    assert experimento.comparativo["veredito"] == "pior" and experimento.comparativo["z"] < -1.96
    assert proposta.situacao == "arquivada" and not proposta.ativa
    assert proposta.historico[-1]["acao"] == "saiu do teste" and "v2 vendeu 1" in proposta.historico[-1]["motivo"]
    assert papeis.estrategia_ativa("abordagem").pk == base.pk
    # Todo o tráfego volta para a base; a memória das decisões já feitas fica.
    assert all(otimizador.escolher_para(_trabalho(T.ABORDAR, oportunidade_id=f"o-{i}",
                                                  chave_da_conversa=f"lead:site-1:{i}")).pk == base.pk
               for i in range(60))
    assert DecisaoComercial.objects.filter(versao_estrategia=2).count() == 40
    assert EstrategiaComercial.objects.filter(papel="abordagem", versao=2).exists()


def test_candidata_pior_so_com_pouca_amostra_continua_em_teste():
    _, experimento = _v2()
    _envios(1, 40, 12, "b")
    _envios(2, 10, 0, "c")  # a candidata só tem 10 oportunidades
    resultado = otimizador.avaliar(ExperimentoEstrategia.objects.get(pk=experimento.pk))
    assert resultado["desfecho"] == "continua" and resultado["comparacao"]["veredito"] == "inconclusivo"
    experimento.refresh_from_db()
    assert experimento.estado == X.EM_TESTE


def test_o_comparativo_conta_so_o_periodo_do_teste():
    """A base tinha 40 vendas boas ANTES do teste; elas não entram na comparação."""
    base = papeis.estrategia_ativa("abordagem")
    _envios(1, 40, 30, "antes")
    proposta, experimento = _v2(percentual=50)
    _envios(1, 35, 4, "durante-b")
    _envios(2, 35, 4, "durante-c")
    resultado = otimizador.avaliar(ExperimentoEstrategia.objects.get(pk=experimento.pk))
    assert resultado["desfecho"] == "continua"
    assert resultado["comparacao"]["base"] == {"abordagens": 35, "vendas": 4}
    assert papeis.estrategia_ativa("abordagem").pk == base.pk


def test_candidata_melhor_com_amostra_vira_a_do_ar_e_a_anterior_fica_para_voltar():
    base = papeis.estrategia_ativa("abordagem")
    proposta, experimento = _v2(percentual=50)
    _envios(1, 40, 12, "b")
    _envios(2, 40, 26, "c")
    resultado = otimizador.avaliar(ExperimentoEstrategia.objects.get(pk=experimento.pk))
    assert resultado["desfecho"] == "promovida"
    experimento.refresh_from_db()
    assert experimento.estado == X.PROMOVIDA and "melhorou" in experimento.conclusao
    ativa = papeis.estrategia_ativa("abordagem")
    assert ativa.pk == proposta.pk and ativa.anterior_id == base.pk
    base.refresh_from_db()
    assert base.situacao == "arquivada"
    # Depois de promovida, se piorar contra a base no período do teste, volta sozinha.
    _envios(2, 200, 0, "d")
    volta = otimizador.volta_se_piorou("abordagem")
    assert volta and volta["voltou_para"] == 1
    assert papeis.estrategia_ativa("abordagem").pk == base.pk


def test_teste_sem_diferenca_e_encerrado_depois_do_prazo_e_fica_a_versao_do_ar():
    base = papeis.estrategia_ativa("abordagem")
    proposta, experimento = _v2()
    _envios(1, 40, 8, "b")
    _envios(2, 40, 8, "c")
    ExperimentoEstrategia.objects.filter(pk=experimento.pk).update(
        iniciado_em=timezone.now() - otimizador.DURACAO_MAXIMA - timedelta(hours=1))
    # As decisões acabaram de nascer, então precisam estar dentro do período.
    DecisaoComercial.objects.update(criada_em=timezone.now())
    resultado = otimizador.avaliar(ExperimentoEstrategia.objects.get(pk=experimento.pk))
    assert resultado["desfecho"] == "encerrado"
    experimento.refresh_from_db()
    assert experimento.estado == X.ENCERRADA and "Fica a v1" in experimento.conclusao
    assert papeis.estrategia_ativa("abordagem").pk == base.pk
    proposta.refresh_from_db()
    assert proposta.situacao == "arquivada"


def test_se_a_pessoa_poe_outra_versao_no_ar_durante_o_teste_o_teste_acaba():
    proposta, experimento = _v2()
    outra = papeis.propor_versao("abordagem", "da pessoa", criada_por="admin", motivo="m", origem="pessoa")
    papeis.ativar(outra, "admin")
    resultado = otimizador.avaliar(ExperimentoEstrategia.objects.get(pk=experimento.pk))
    assert resultado["desfecho"] == "encerrado" and "mudou durante o teste" in resultado["motivo"]
    # Enquanto isso, ninguém é sorteado para uma comparação que deixou de valer.
    assert otimizador.escolher_para(_trabalho(T.ABORDAR, oportunidade_id="opp-1")).pk == outra.pk


@respx.mock
def test_a_analise_da_hora_volta_a_versao_que_piorou_sem_chamar_o_modelo():
    _guardar_chave()
    base = papeis.estrategia_ativa("abordagem")
    proposta, experimento = _v2(percentual=50)
    _envios(1, 40, 12, "b")
    _envios(2, 40, 1, "c")
    trabalho = _analise()
    openai = respx.post(RESPOSTAS)
    coordenador.rodar_um("t1")
    trabalho.refresh_from_db()
    assert trabalho.estado == E.CONCLUIDO, trabalho.motivo
    assert trabalho.resultado["conclusao"] == "voltou"
    assert trabalho.resultado["experimentos"][0]["desfecho"] == "voltou"
    assert "voltou para a v1" in trabalho.resultado["experimentos"][0]["motivo"]
    assert not openai.called  # a volta não depende do modelo
    assert papeis.estrategia_ativa("abordagem").pk == base.pk
    experimento.refresh_from_db()
    assert experimento.estado == X.REVERTIDA


def test_um_teste_por_papel_e_a_segunda_proposta_espera_como_proposta():
    _v2()
    segunda, experimento = otimizador.iniciar_teste("abordagem", "Outra ideia", motivo="m", percentual=20)
    assert experimento is None and segunda.situacao == "proposta" and segunda.versao == 3
    # Atendimento tem o próprio teste, independente.
    _, do_atendimento = _v2("atendimento")
    assert do_atendimento.estado == X.EM_TESTE
    assert ExperimentoEstrategia.objects.filter(estado=X.EM_TESTE).count() == 2


def test_relatorio_da_tela_traz_o_teste_e_os_numeros_por_papel():
    _v2()
    _envios(1, 3, 1, "x")
    relatorio = otimizador.relatorio()
    assert set(relatorio) == {"abordagem", "atendimento"}
    assert relatorio["abordagem"]["teste"].candidata.versao == 2 and relatorio["abordagem"]["no_ar"] == 1
    assert relatorio["abordagem"]["numeros"]["versoes"][0]["abordagens"] == 3
    assert relatorio["atendimento"]["teste"] is None


@respx.mock
def test_pagina_mostra_o_teste_e_a_pessoa_pode_encerra_lo():
    from django.test import Client
    from django.urls import reverse

    from tests.test_comercial import DONO, IDENTIDADE

    respx.get(f"{IDENTIDADE}/sessao/completa").respond(200, json={
        "autenticado": True, "id": "id-1", "nome_exibido": "Dono", "papel": None, "email": DONO})
    cliente = Client()
    cliente.defaults["HTTP_COOKIE"] = "meshcraft_sessao=qualquer-coisa-assinada"
    _, experimento = _v2()
    _envios(1, 3, 1, "x")
    html = cliente.get(reverse("agentes_comerciais")).content.decode()
    assert "Em teste: v2 atende 20% das oportunidades, contra a v1" in html
    assert "Encerrar o teste" in html and "3 oportunidade(s)" in html
    resposta = cliente.post(reverse("agentes_comerciais"), {"acao": "encerrar_teste", "teste": experimento.pk})
    assert resposta.status_code == 302
    experimento.refresh_from_db()
    assert experimento.estado == X.ENCERRADA and "Encerrado por" in experimento.conclusao
    html = cliente.get(reverse("agentes_comerciais")).content.decode()
    assert "Encerrado sem conclusão" in html and "Encerrar o teste" not in html
    # Encerrar de novo não faz nada.
    assert otimizador.encerrar(experimento, "dono") is False


def test_a_tabela_do_experimento_tem_o_nome_que_o_banco_do_site_ja_tem():
    # No site, o app se chama `admin_comercial`; sem o nome escrito, a tela da
    # equipe procuraria uma tabela que não existe e cairia com erro 500.
    assert ExperimentoEstrategia._meta.db_table == "comercial_experimentoestrategia"
