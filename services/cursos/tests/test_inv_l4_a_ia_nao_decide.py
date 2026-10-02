"""Teste-guarda [INV-CUR-L4]: nenhuma decisão, data ou resposta à pergunta de
amanhã de manhã vem da IA.

Lei: `PLANO-CELULA-CURSOS.md` §9 ("`RascunhoDaIA` não tem esses campos, e o
teste sabota tentando gravá-los") e §7 (o Assistente de laudo é degrau H, "só
prepara"). Degrau 2.3 (TAR-157).

O INVARIANTE TEM DUAS METADES, E ESTE ARQUIVO PROVA AS DUAS
------------------------------------------------------------
1. **A FORMA**: não existe onde guardar. Nenhum campo de `RascunhoDaIA` nem
   de `agente.Sugestao` tem nome de decisão, de data de retorno ou de pergunta.
2. **O COMPORTAMENTO**: mesmo que a IA responda os três (e um modelo prestativo
   responde), eles não têm por onde chegar. A tela volta com a decisão sem
   marcar, a data em branco e a caixa desmarcada, e um laudo pedido sem decisão
   é recusado em vez de a decisão da IA preencher o buraco.

Provado por MUTAÇÃO em 05/09/2026, e o vermelho de cada uma caiu na ASSERÇÃO,
nunca na construção do teste (`armadilhas/195`):

* acrescentar `decisao = models.CharField(max_length=17, blank=True,
  default="")` a `RascunhoDaIA`, COM a migração junto, deixa vermelho
  `assert 'decis' not in 'decisao'`. A migração faz parte da sabotagem de
  propósito: sem ela o vermelho seria do banco fora de sincronia, e não da
  regra;
* acrescentar `decisao: str = ""` ao FIM de `agente.Sugestao` deixa vermelho o
  teste do dataclass. No fim, e com default, também de propósito: campo com
  default antes de campo sem default é `TypeError` no import, e aí nenhuma
  asserção chega a rodar;
* fazer `_preenchido_pela_ia` copiar decisão, data e pergunta para o
  formulário deixa 1 vermelho em
  `test_a_tela_volta_sem_decisao_sem_data_e_sem_a_caixa`;
* fazer `laudo.emitir` completar a decisão vazia com a do `conteudo` do
  rascunho deixa 1 vermelho em
  `test_laudo_sem_decisao_e_recusado_mesmo_com_rascunho_que_a_traz`.

Desfeitas as quatro, todos voltam a verde.
"""

from __future__ import annotations

import dataclasses

import pytest
from django.urls import reverse

from apps.cursos import agente
from apps.cursos import laudo as parecer
from apps.cursos.models import Laudo, RascunhoDaIA
from tests.conftest import (
    BETO,
    COOKIE,
    corpo_da_anthropic,
    dublar_a_anthropic,
    dublar_matricula,
    dublar_sessao,
    forcas_validas,
    mudanca_valida,
    notas_validas,
)

pytestmark = pytest.mark.django_db

# Os pedaços de nome que denunciam um campo de decisão, de data de retorno ou
# de resposta à pergunta de amanhã de manhã. São seis para cobrir as três
# coisas: um campo cujo nome contenha qualquer um deles é uma delas com outro
# nome.
PALAVRAS_PROIBIDAS = ("decis", "data", "pergunta", "amanha", "retorno", "veredito")

# O que a IA devolve nos testes desta suíte: a sugestão legítima MAIS os três
# campos que ela não pode decidir. Um modelo prestativo responde exatamente
# assim quando ninguém o impede, e é esse o cenário que interessa provar.
SUGESTAO_INTROMETIDA = {
    "notas": {
        "Acabamento": {"nota": 4, "frase": "O bevel do topo está uniforme."},
        "Proporção": {"nota": 5, "frase": "A altura bate com a referência."},
    },
    "forcas": [
        "O bevel das arestas ficou uniforme em todo o modelo.",
        "A escala bateu com a referência sem precisar de ajuste.",
        "O README explica o processo passo a passo.",
    ],
    "mudanca": {"texto": "Praticar UV na próxima entrega.", "aula_numero": "E01"},
    "reenvio": "",
    "resumo": "Rubrica e forças preparadas.",
    "lacunas": "nada",
    "a_verificar": "abrir o .blend e conferir o bevel",
    "origens": "o README e o Aceito quando",
    "para_a_pessoa": "[DECISÃO HUMANA] a decisão, a data e a pergunta",
    # Os três que este arquivo existe para provar que não chegam a lugar nenhum.
    "decisao": "aberto",
    "data_de_retorno": "2099-12-31",
    "sabe_o_que_fazer_amanha": True,
}


@pytest.fixture
def no_plantao(env_dos_pares, rede, envio_na_fila, monkeypatch):
    """Beto, na lista do plantão, com a chave da Anthropic presente."""
    monkeypatch.setenv("CURSOS_PROFESSORES", BETO["email"])
    monkeypatch.setenv(agente.VARIAVEL_DA_CHAVE, "sk-ant-de-mentira")
    dublar_sessao(rede, BETO)
    dublar_matricula(rede, BETO["email"], "cadastrado")
    return envio_na_fila


def _rascunhar(client, envio):
    return client.post(
        reverse("plantao-ficha", args=[envio.id]),
        {"gesto": "rascunhar"},
        HTTP_COOKIE=COOKIE,
    )


# ---------------------------------------------------------------------------
# 1. A FORMA: não existe onde guardar decisão, data nem pergunta
# ---------------------------------------------------------------------------


def test_o_rascunho_da_ia_nao_tem_campo_de_decisao_data_nem_pergunta():
    campos = {campo.name for campo in RascunhoDaIA._meta.get_fields()}
    for campo in campos:
        for proibido in PALAVRAS_PROIBIDAS:
            assert proibido not in campo, (
                f"{campo} guarda algo que é da professora, não da IA "
                "([INV-CUR-L4]): a decisão, a data de retorno e a pergunta de "
                "amanhã de manhã não se guardam num rascunho de máquina."
            )


def test_a_sugestao_do_agente_nao_tem_campo_de_decisao_data_nem_pergunta():
    for campo in dataclasses.fields(agente.Sugestao):
        for proibido in PALAVRAS_PROIBIDAS:
            assert proibido not in campo.name


# ---------------------------------------------------------------------------
# 2. O COMPORTAMENTO: a IA responde os três, e eles não chegam a lugar nenhum
# ---------------------------------------------------------------------------


def test_a_tela_volta_sem_decisao_sem_data_e_sem_a_caixa(
    no_plantao, client, monkeypatch
):
    """A IA mandou decisão, data e a pergunta respondida. A tela ignora as três.

    O que se lê no HTML é a prova: nenhum `checked` numa das três decisões,
    a data de retorno vazia, e a caixa da pergunta de amanhã de manhã sem
    marca. Os campos que ela PODE preencher (rubrica e forças) chegaram, e é
    isso que separa "o guarda funciona" de "a chamada falhou inteira".
    """
    dublar_a_anthropic(monkeypatch, corpo=corpo_da_anthropic(SUGESTAO_INTROMETIDA))
    tela = _rascunhar(client, no_plantao)
    html = tela.content.decode()

    assert tela.status_code == 200
    # o que ela pode: chegou
    assert "O bevel do topo está uniforme." in html
    assert "Praticar UV na próxima entrega." in html
    # o que ela não pode: nenhum dos três
    assert 'value="aberto" checked' not in html
    assert 'value="aberto_com_ajuste" checked' not in html
    assert 'value="devolvido" checked' not in html
    assert 'name="data_de_retorno" value=""' in html
    assert "2099" not in html
    assert 'name="sabe_o_que_fazer_amanha" value="sim" checked' not in html


def test_o_rascunho_guardado_nao_leva_a_decisao_da_ia(no_plantao, client, monkeypatch):
    """O que sobra no banco é a sugestão, e as três chaves ficaram de fora.

    O `conteudo` é a prova contra a qual a Ficha de Série é medida depois, e um
    "decisao" guardado ali seria a semente exata do degrau que a lei diz que
    nunca sobe: a IA decide os fáceis.
    """
    dublar_a_anthropic(monkeypatch, corpo=corpo_da_anthropic(SUGESTAO_INTROMETIDA))
    _rascunhar(client, no_plantao)

    rascunho = RascunhoDaIA.objects.get()
    assert set(rascunho.conteudo) == {
        "notas",
        "forcas",
        "mudanca",
        "mudancas",
        "reenvio",
        "bloco",
    }
    guardado = str(rascunho.conteudo)
    assert "aberto" not in guardado
    assert "2099-12-31" not in guardado


def test_laudo_sem_decisao_e_recusado_mesmo_com_rascunho_que_a_traz(
    no_plantao, professora
):
    """O buraco da decisão NUNCA é preenchido pelo rascunho.

    Este é o guarda que fecha a porta dos fundos: `emitir` recebe o rascunho, e
    o rascunho carrega uma decisão escrita à mão no `conteudo` (o pior caso
    imaginável). Sem a decisão vinda do formulário, o laudo é RECUSADO. Se
    algum dia alguém "aproveitar" o que está no rascunho para poupar um campo,
    é aqui que o vermelho aparece.
    """
    rascunho = RascunhoDaIA.objects.create(
        envio=no_plantao,
        conteudo={**SUGESTAO_INTROMETIDA, "bloco": {}},
        modelo=agente.MODELO,
    )
    with pytest.raises(parecer.LaudoRecusado, match="não existe"):
        parecer.emitir(
            no_plantao,
            avaliador=professora,
            papel=Laudo.Papel.PROFESSOR,
            notas=notas_validas(),
            forcas=forcas_validas(),
            mudanca=mudanca_valida(no_plantao.aula),
            decisao="",
            sabe_o_que_fazer_amanha=True,
            rascunho=rascunho,
        )
    assert Laudo.objects.count() == 0
