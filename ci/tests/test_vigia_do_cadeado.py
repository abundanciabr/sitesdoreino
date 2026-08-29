"""Guarda do VIGIA DO CADEADO — ele grita quando deve, e cala quando deve.

Vigia que nunca fica vermelho é decoração. Estes testes exercitam a função de
JULGAMENTO contra medições fabricadas — o "repositório de mentira" do resto de
`ci/tests` — porque julgar tem de ser exercitável sem rede: um teste que
depende da internet reprova por motivo errado e ensina a ignorá-lo.

A rede é exercitada de outro jeito, e está registrado no PR: `--host
expired.badssl.com` e `--host self-signed.badssl.com` reprovaram na mão antes
do merge, provando que o caminho de MEDIÇÃO também sabe ficar vermelho.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "ci"))

from vigia_do_cadeado import (  # noqa: E402
    DIAS_PARA_GRITAR,
    ROTAS,
    SITES,
    Medicao,
    a_vigiar,
    hosts_das_rotas,
    hosts_dos_sites,
    julgar,
)

HOJE = dt.date(2026, 8, 29)


def _saudavel(dias: int) -> Medicao:
    return Medicao(
        confia=True, vence_em=HOJE + dt.timedelta(days=dias), emissor="Let's Encrypt"
    )


# ---------------------------------------------------------------------------
# O que ele APROVA — e só isto.
# ---------------------------------------------------------------------------
def test_aprova_certificado_valido_e_folgado():
    assert julgar("meshcraft.top", _saudavel(90), HOJE) == []


def test_aprova_exatamente_na_regua_nao_um_dia_antes():
    # A fronteira é onde guarda mal escrito erra. `>= 21` passa; `20` grita.
    assert julgar("x.top", _saudavel(DIAS_PARA_GRITAR), HOJE) == []
    assert julgar("x.top", _saudavel(DIAS_PARA_GRITAR - 1), HOJE) != []


# ---------------------------------------------------------------------------
# O que ele REPROVA. Cada caso é um jeito real de o cadeado morrer.
# ---------------------------------------------------------------------------
def test_reprova_o_cracha_de_fabrica_e_o_chama_pelo_nome():
    # O incidente de 29/08/2026 (armadilhas/177): o www servindo o default do
    # Traefik com o site inteiro saudável ao lado. Se este teste ficar verde,
    # o vigia teria dormido naquele dia.
    queixas = julgar(
        "www.meshcraft.top", Medicao(confia=False, cracha_de_fabrica=True), HOJE
    )
    assert queixas != []
    assert "TRAEFIK DEFAULT CERT" in queixas[0]
    assert "armadilhas/018" in queixas[0]


def test_reprova_certificado_nao_confiavel():
    queixas = julgar(
        "x.top", Medicao(confia=False, erro="self-signed certificate"), HOJE
    )
    assert queixas != []
    assert "self-signed certificate" in queixas[0]


def test_reprova_certificado_ja_vencido_e_diz_ha_quantos_dias():
    queixas = julgar("x.top", _saudavel(-3), HOJE)
    assert queixas != []
    assert "VENCIDO há 3 dia" in queixas[0]


def test_reprova_quando_falta_pouco_porque_a_renovacao_ja_devia_ter_ocorrido():
    queixas = julgar("x.top", _saudavel(5), HOJE)
    assert queixas != []
    assert "não renovou" in queixas[0]


def test_reprova_quando_nao_conseguiu_medir():
    # INV-CI01: "não medi" jamais vira "está limpo".
    assert julgar("x.top", Medicao(confia=False, erro="não consegui medir: timeout"), HOJE) != []


def test_reprova_quando_confia_mas_nao_sabe_a_validade():
    # O caso mais traiçoeiro: metade da medição deu certo. Meia medição é
    # nenhuma medição.
    assert julgar("x.top", Medicao(confia=True, vence_em=None), HOJE) != []


# ---------------------------------------------------------------------------
# QUEM ele vigia — a lista tem de se manter sozinha, senão o vigia envelhece.
# ---------------------------------------------------------------------------
ROTAS_DE_MENTIRA = """
http:
  routers:
    funil:
      rule: "PathPrefix(`/`)"
    www-meshcraft:
      rule: "Host(`www.exemplo.top`) && !PathPrefix(`/api`)"
    webhooks:
      rule: "Host(`operacoes.exemplo.org`) && PathPrefix(`/api/x`)"
"""

SITES_DE_MENTIRA = {
    "sites": [
        {"host": "exemplo.top", "active": True},
        {"host": "desligado.top", "active": False},
    ]
}


def test_vigia_o_site_ativo_e_o_www_que_tem_rota_propria():
    vigiados, _ = a_vigiar(SITES_DE_MENTIRA, ROTAS_DE_MENTIRA)
    assert vigiados == ["exemplo.top", "www.exemplo.top"]


def test_nao_vigia_site_desligado():
    vigiados, _ = a_vigiar(SITES_DE_MENTIRA, ROTAS_DE_MENTIRA)
    assert "desligado.top" not in vigiados


def test_o_host_dispensado_e_DECLARADO_nunca_sumido_em_silencio():
    # A diferença entre "não meço isto, e eis o porquê" e uma omissão que
    # ninguém vê. A segunda é como um vigia vira decoração.
    _, dispensados = a_vigiar(SITES_DE_MENTIRA, ROTAS_DE_MENTIRA)
    assert any("operacoes.exemplo.org" in d for d in dispensados)


def test_www_sem_site_ativo_por_tras_nao_entra_escondido():
    rotas = 'http:\n  routers:\n    r:\n      rule: "Host(`www.forasteiro.top`)"\n'
    vigiados, dispensados = a_vigiar(SITES_DE_MENTIRA, rotas)
    assert "www.forasteiro.top" not in vigiados
    assert any("www.forasteiro.top" in d for d in dispensados)


def test_sites_json_malformado_levanta_em_vez_de_devolver_lista_vazia():
    # Lista vazia seria "0 hosts, todos passaram" — o falso-verde de vacuidade.
    with pytest.raises(AssertionError):
        hosts_dos_sites({"nada": []})


def test_extrai_host_de_regra_com_espacos_e_conjuncao():
    assert hosts_das_rotas('rule: "Host( `a.top` ) && PathPrefix(`/x`)"') == {"a.top"}


# ---------------------------------------------------------------------------
# A medição real: as fontes que estão no ar hoje.
# ---------------------------------------------------------------------------
def test_as_duas_fontes_existem_e_produzem_hosts_de_verdade():
    assert SITES.is_file(), f"registro de sites ausente: {SITES}"
    assert ROTAS.is_file(), f"tabela de rotas ausente: {ROTAS}"
    vigiados, _ = a_vigiar(
        json.loads(SITES.read_text(encoding="utf-8")),
        ROTAS.read_text(encoding="utf-8"),
    )
    # Sem isto, apagar uma das pontas deixaria o vigia "verde" por não ter o
    # que medir — e ninguém perceberia até o cadeado cair.
    assert vigiados, "a lista de hosts a vigiar saiu VAZIA"
    assert "meshcraft.top" in vigiados


def test_o_www_de_hoje_esta_sendo_vigiado():
    # O endereço que causou o incidente de 29/08/2026 não pode sair da lista
    # sem alguém passar por este teste.
    vigiados, _ = a_vigiar(
        json.loads(SITES.read_text(encoding="utf-8")),
        ROTAS.read_text(encoding="utf-8"),
    )
    assert "www.meshcraft.top" in vigiados
