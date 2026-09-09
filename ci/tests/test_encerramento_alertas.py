"""A conclusão e a baixa viajam juntas, sem apagar alertas nem reescrever história."""

import copy
import json
from pathlib import Path

import pytest

import encerramento_alertas as guarda
from _nucleo import ErroDeInstrumentacao
from verificar_painel import Painel, registros_da_fonte


PR = "https://github.com/abundanciabr/sitesdoreino/pull/1474"
ALERTA = {
    "arquivo": "alerta", "tipo": "entrega", "gravidade": "ambar",
    "quando": "2026-09-09", "evidencia": PR, "responde_a": None,
}
VERDE = {
    "arquivo": "verde", "tipo": "medicao", "gravidade": "verde",
    "quando": "2026-09-09", "verificado_em": "2026-09-09",
    "evidencia": PR, "responde_a": None,
}


def livro(**mudancas):
    registros = {"alerta": copy.deepcopy(ALERTA), "verde": copy.deepcopy(VERDE)}
    registros["verde"].update(mudancas)
    return registros


def test_verde_do_mesmo_pr_exige_baixa_exata():
    erros = guarda.conferir_registros(livro(), {"verde"})
    assert len(erros) == 1
    assert 'responde_a: "alerta"' in erros[0]
    assert "painel/LEIA-ME.md" in erros[0]


def test_propria_conclusao_pode_fechar_alerta():
    assert guarda.conferir_registros(livro(responde_a="alerta", relacao="resolucao"), {"verde"}) == []


@pytest.mark.parametrize("alvo", [["alerta"], [], {}, 1, False])
def test_responde_a_nao_textual_nao_contorna_prova_por_coercao(alvo):
    erros = guarda.conferir_registros(livro(responde_a=alvo, gravidade="info"), {"verde"})
    assert any("identificador em texto ou null" in erro for erro in erros)


@pytest.mark.parametrize("mudancas", [
    {"gravidade": "info"}, {"gravidade": "ambar"}, {"gravidade": "vermelho"},
    {"evidencia": " "},
    {"verificado_em": None}, {"verificado_em": "ontem"}, {"verificado_em": "2026-09-08"},
])
def test_baixa_sem_prova_recusada(mudancas):
    registros = livro(responde_a="alerta", relacao="resolucao", **mudancas)
    assert any("baixa de alerta sem prova" in e for e in guarda.conferir_registros(registros, {"verde"}))


@pytest.mark.parametrize("url", [
    PR + "0", PR + "abc", PR + "/inventado", PR.replace("sitesdoreino", "outro"),
    PR.replace("github.com", "github.com.evil.example"),
    PR.replace("pull", "issues"), "https://example.org/" + PR, "https://[invalido/pull/1474",
])
def test_url_parecida_nao_inventa_identidade(url):
    assert guarda.conferir_registros(livro(evidencia=url), {"verde"}) == []


@pytest.mark.parametrize("url", [
    PR, PR + "#issuecomment-123", PR + "?foo=bar", PR + "/", PR + ";",
    PR + "/files", PR + "/commits", PR + "/checks",
])
def test_url_do_pr_com_fragmento_ou_pontuacao_mantem_identidade(url):
    assert guarda.conferir_registros(livro(evidencia=url), {"verde"})


def test_dois_alertas_fecham_no_mesmo_lote_sem_cobranca_circular():
    registros = livro(responde_a="alerta", relacao="resolucao")
    registros["outro-alerta"] = dict(ALERTA, arquivo="outro-alerta")
    registros["outra-baixa"] = dict(VERDE, arquivo="outra-baixa", responde_a="outro-alerta", relacao="resolucao")
    assert guarda.conferir_registros(registros, {"verde", "outra-baixa"}) == []
    del registros["outra-baixa"]
    assert any("outro-alerta" in e for e in guarda.conferir_registros(registros, {"verde"}))


def test_historia_orfa_nao_bloqueia_trabalho_sem_relacao():
    registros = livro()
    assert guarda.conferir_registros(registros, set()) == []
    registros["novo"] = dict(VERDE, arquivo="novo", evidencia=PR + "0")
    assert guarda.conferir_registros(registros, {"novo"}) == []


def test_info_nao_afirma_conclusao_nem_cria_cobranca():
    assert guarda.conferir_registros(livro(gravidade="info"), {"verde"}) == []


def test_incidente_do_mesmo_pr_nao_e_confundido_com_recibo_de_entrega():
    registros = livro()
    registros["alerta"]["tipo"] = "incidente"
    assert guarda.conferir_registros(registros, {"verde"}) == []


def test_resposta_sem_prova_existente_nao_dispensa_nova_baixa():
    registros = livro()
    registros["resposta"] = dict(VERDE, responde_a="alerta", gravidade="info")
    assert guarda.conferir_registros(registros, {"verde"})


def test_instrumento_quebrado_vira_error_no_comando(monkeypatch, capsys):
    monkeypatch.setattr(guarda, "conferir", lambda *_: (_ for _ in ()).throw(ErroDeInstrumentacao("node ausente", "Instale Node.")))
    assert guarda.main() == 2
    assert "ERROR encerramento-alertas" in capsys.readouterr().out


def test_base_ausente_e_erro_de_instrumento():
    raiz = Path(__file__).resolve().parents[2]
    with pytest.raises(ErroDeInstrumentacao, match="não consegui ler a base"):
        guarda.conferir(Painel(raiz), "ref-que-nao-existe-encerramento-alertas")


def test_node_quebrado_nao_vira_sem_conclusoes(monkeypatch):
    raiz = Path(__file__).resolve().parents[2]
    executar = __import__("verificar_painel").executar

    def sem_node(comando, **kwargs):
        if comando[0] == "node":
            raise ErroDeInstrumentacao("node ausente", "Instale Node.")
        return executar(comando, **kwargs)

    monkeypatch.setattr("verificar_painel.executar", sem_node)
    with pytest.raises(ErroDeInstrumentacao, match="node ausente"):
        guarda.conferir(Painel(raiz), "HEAD")


def test_caso_real_041_recusa_orfao_aceita_baixas_e_preserva_alerta_legitimo():
    raiz = Path(__file__).resolve().parents[2]
    fonte = registros_da_fonte(Painel(raiz))
    cursos = "20260909-037-corrigir-situacao-ao-salvar-cursos"
    situacao = "20260909-039-corrigir-falso-erro-da-situacao"
    conclusao = "20260909-041-deploy-da-correcao-de-situacao-confirmado"
    registros = {ident: fonte[ident] for ident in (cursos, situacao, conclusao)}
    assert any(situacao in e for e in guarda.conferir_registros(registros, {conclusao}))
    assert registros[cursos]["responde_a"] is None
    registros[conclusao] = dict(registros[conclusao], responde_a=situacao, relacao="resolucao")
    registros["baixa-cursos"] = dict(VERDE, responde_a=cursos, relacao="resolucao", evidencia=PR.replace("1474", "1472"))
    registros["legitimo"] = dict(ALERTA, arquivo="legitimo", evidencia=PR + "0")
    assert guarda.conferir_registros(registros, {conclusao, "baixa-cursos"}) == []
    respondidos = {r.get("responde_a") for r in registros.values()}
    assert "legitimo" not in respondidos
    assert registros["legitimo"]["gravidade"] == "ambar"


@pytest.mark.parametrize("tipo", ["incidente", "nota", "medicao", "entrega"])
def test_comentario_novo_nao_e_baixa_nem_erro(tipo):
    registros = livro(responde_a="alerta", relacao="comentario", gravidade="info")
    registros["alerta"]["tipo"] = tipo
    assert guarda.conferir_registros(registros, {"verde"}) == []
    assert not guarda.baixa_comprovada(registros["verde"], registros["alerta"])


@pytest.mark.parametrize("tipo", ["incidente", "nota", "medicao"])
def test_resolucao_de_qualquer_alerta_exige_prova(tipo):
    registros = livro(responde_a="alerta", relacao="resolucao", evidencia=" ")
    registros["alerta"]["tipo"] = tipo
    assert any("sem prova" in e for e in guarda.conferir_registros(registros, {"verde"}))


def test_prova_da_tarefa_errada_nao_fecha_ocorrencia():
    registros = livro(responde_a="alerta", relacao="resolucao", tarefa="TAR-293")
    registros["alerta"]["tarefa"] = "TAR-292"
    assert not guarda.baixa_comprovada(registros["verde"], registros["alerta"])
    assert guarda.conferir_registros(registros, {"verde"})


@pytest.mark.parametrize("verificado,esperado", [
    ("2026-09-09T14:59:59Z", False), ("2026-09-09T15:00:00Z", True),
    ("2026-09-09T12:00:00-03:00", True), ("2026-09-09", False),
])
def test_ordem_temporal_preserva_hora_e_fuso(verificado, esperado):
    registros = livro(responde_a="alerta", relacao="resolucao", verificado_em=verificado)
    registros["alerta"]["quando"] = "2026-09-09T15:00:00Z"
    assert guarda.baixa_comprovada(registros["verde"], registros["alerta"]) is esperado


def test_historico_comprovado_sem_alvo_nao_abre_obrigacao():
    historico = dict(VERDE, tipo="incidente", relacao="historico")
    assert guarda.conferir_registros({"verde": historico}, {"verde"}) == []
    historico["evidencia"] = None
    assert guarda.conferir_registros({"verde": historico}, {"verde"})


def test_historico_nao_esconde_obrigacao_existente():
    registros = livro(responde_a="alerta", tipo="incidente", relacao="historico")
    assert guarda.conferir_registros(registros, {"verde"})
    assert not guarda.baixa_comprovada(registros["verde"], registros["alerta"])


def test_relacao_explicita_impede_adaptador_legado_no_registro_novo():
    registros = livro(responde_a="alerta")
    assert any("resposta nova exige relacao" in e for e in guarda.conferir_registros(registros, {"verde"}))
    assert guarda.conferir_registros(registros, set()) == []


def test_verde_comentario_nao_quita_entrega_nem_afirma_conclusao():
    registros = livro(relacao="comentario")
    assert guarda.conferir_registros(registros, {"verde"}) == []
    registros["outro"] = dict(VERDE, arquivo="outro")
    assert guarda.conferir_registros(registros, {"outro"})


EXEMPLOS = json.loads((Path(__file__).resolve().parents[2] / "painel/testes/casos_resolucao.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("caso", EXEMPLOS["casos"], ids=lambda c: c["nome"])
def test_mesmos_exemplos_da_logica_javascript(caso):
    assert guarda.baixa_comprovada(dict(EXEMPLOS["resposta"], **caso["resposta"]), dict(EXEMPLOS["alvo"], **caso["alvo"])) is caso["esperado"]



def test_tentativa_de_entrega_nao_cria_outra_obrigacao():
    registros = livro(responde_a="alerta", relacao="resolucao")
    registros["tentativa"] = dict(ALERTA, arquivo="tentativa", relacao="comentario", responde_a="alerta")
    assert guarda.conferir_registros(registros, {"verde", "tentativa"}) == []
PEDIDO = {
    "arquivo": "pedido", "precisa_do_dono": True, "gravidade": "info",
    "porque_so_voce": "A contratação cria uma despesa que só você pode autorizar.",
    "proximo_passo": "Autorizar ou recusar a contratação pelo valor apresentado.",
    "se_eu_nao_decidir": "O serviço atual continua funcionando com a capacidade atual.",
    "recomendacao": "Manter o serviço atual, pois atende à demanda medida.",
    "reversivel": False, "impacto": "alto",
}


def test_novo_pedido_completo_passa_sem_mudar_o_livro():
    registros = {"pedido": copy.deepcopy(PEDIDO)}
    antes = copy.deepcopy(registros)
    assert guarda.conferir_registros(registros, {"pedido"}) == []
    assert registros == antes


@pytest.mark.parametrize("campo", [
    "porque_so_voce", "proximo_passo", "se_eu_nao_decidir", "recomendacao",
])
@pytest.mark.parametrize("valor", [None, "", "  ", False, [], {}])
def test_novo_pedido_exige_cada_texto_e_ensina_corrigir(campo, valor):
    registro = dict(PEDIDO, **{campo: valor})
    erros = guarda.conferir_registros({"pedido": registro}, {"pedido"})
    assert any(campo in e and "painel/LEIA-ME.md" in e for e in erros)


@pytest.mark.parametrize("campo,valor", [
    ("reversivel", None), ("reversivel", "false"), ("reversivel", 0),
    ("impacto", None), ("impacto", "urgente"),
])
def test_novo_pedido_exige_reversibilidade_e_impacto(campo, valor):
    erros = guarda.conferir_registros({"pedido": dict(PEDIDO, **{campo: valor})}, {"pedido"})
    assert any(campo in e for e in erros)


def test_pedido_historico_incompleto_nao_bloqueia_novo_alerta_tecnico():
    registros = {
        "antigo": {"precisa_do_dono": True},
        "tecnico": {"precisa_do_dono": False, "gravidade": "vermelho",
                    "detalhe": "O teste falhou; o robô corrigirá a validação da entrada."},
    }
    antes = copy.deepcopy(registros)
    assert guarda.conferir_registros(registros, {"tecnico"}) == []
    assert registros == antes


def test_pedido_novo_com_data_antiga_nao_escapa_do_portao():
    registro = {"precisa_do_dono": True, "quando": "2020-01-01"}
    assert guarda.conferir_registros({"novo": registro}, {"novo"})


@pytest.mark.parametrize("caso", EXEMPLOS["complementos"], ids=lambda c: c["nome"])
def test_complemento_mesmos_exemplos_javascript(caso):
    alvo = dict(EXEMPLOS["alvo"])
    principal = dict(ALERTA, arquivo="principal", quando="2026-09-09T16:00:00Z")
    resposta = dict(EXEMPLOS["resposta"], arquivo="vinculo", relacao="complemento", ocorrencia="principal", gravidade="info", verificado_em="2026-09-09T17:00:00Z")
    resposta.update(caso["resposta"])
    registros = {r["arquivo"]: r for r in [alvo, principal, resposta]}
    assert bool(guarda.complementos_comprovados(registros).get("ocorrencia")) is caso["esperado"]
    assert bool(guarda.conferir_registros(registros, {"vinculo"})) is not caso["esperado"]


def test_complemento_ciclico_e_ultimo_invalido_nao_apagam_fatos():
    registros = {"a": dict(ALERTA, arquivo="a"), "b": dict(ALERTA, arquivo="b")}
    vinculo = dict(VERDE, arquivo="v", relacao="complemento", gravidade="info", responde_a="a", ocorrencia="b")
    registros["v"] = vinculo
    assert guarda.complementos_comprovados(registros) == {"a": "b"}
    registros["ruim"] = dict(vinculo, arquivo="ruim", evidencia="", ocorrencia="ausente")
    assert guarda.complementos_comprovados(registros) == {"a": "b"}
    registros["volta"] = dict(vinculo, arquivo="volta", responde_a="b", ocorrencia="a")
    assert guarda.complementos_comprovados(registros) == {}


def test_cadeia_e_destinos_ambiguos_nao_produzem_efeito_parcial():
    registros = {i: dict(ALERTA, arquivo=i) for i in ["a", "b", "c"]}
    registros["v"] = dict(VERDE, arquivo="v", relacao="complemento", gravidade="info", responde_a="a", ocorrencia="b")
    registros["w"] = dict(registros["v"], arquivo="w", ocorrencia="c")
    assert guarda.complementos_comprovados(registros) == {}
    registros["w"]["responde_a"] = "b"
    assert guarda.complementos_comprovados(registros) == {}
