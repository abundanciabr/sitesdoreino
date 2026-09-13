"""A conclusão e a baixa viajam juntas, sem apagar alertas nem reescrever história."""

import copy
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
    assert guarda.conferir_registros(livro(responde_a="alerta"), {"verde"}) == []


@pytest.mark.parametrize("alvo", [["alerta"], [], {}, 1, False])
def test_responde_a_nao_textual_nao_contorna_prova_por_coercao(alvo):
    erros = guarda.conferir_registros(livro(responde_a=alvo, gravidade="info"), {"verde"})
    assert any("identificador em texto ou null" in erro for erro in erros)


@pytest.mark.parametrize("mudancas", [
    {"gravidade": "info"}, {"gravidade": "ambar"}, {"gravidade": "vermelho"},
    {"evidencia": " "}, {"evidencia": PR + "0"},
    {"verificado_em": None}, {"verificado_em": "ontem"}, {"verificado_em": "2026-09-08"},
])
def test_baixa_sem_prova_recusada(mudancas):
    registros = livro(responde_a="alerta", **mudancas)
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
    registros = livro(responde_a="alerta")
    registros["outro-alerta"] = dict(ALERTA, arquivo="outro-alerta")
    registros["outra-baixa"] = dict(VERDE, arquivo="outra-baixa", responde_a="outro-alerta")
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
    registros[conclusao] = dict(registros[conclusao], responde_a=situacao)
    registros["baixa-cursos"] = dict(VERDE, responde_a=cursos, evidencia=PR.replace("1474", "1472"))
    registros["legitimo"] = dict(ALERTA, arquivo="legitimo", evidencia=PR + "0")
    assert guarda.conferir_registros(registros, {conclusao, "baixa-cursos"}) == []
    respondidos = {r.get("responde_a") for r in registros.values()}
    assert "legitimo" not in respondidos
    assert registros["legitimo"]["gravidade"] == "ambar"


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
