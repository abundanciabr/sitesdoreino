"""Guarda do VIGIA DO SITE — ele grita quando a porta da loja não abre.

O vigia do cadeado mede se o certificado do site é válido. Nunca mediu se o
site RESPONDE: um Traefik com cadeado perfeito na frente de células mortas
passava no único olho externo que esta casa tinha. Este arquivo existe para
que a pergunta "o site está no ar?" tenha dono.

Como no irmão dele, o julgamento é exercitado contra respostas fabricadas —
teste que depende da internet reprova por motivo errado e ensina a ser
ignorado. A rede foi exercitada na mão e está registrada no PR: um host
inexistente produziu o aviso, e os hosts reais responderam 200.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "ci"))

import portao_de_deploy as pd  # noqa: E402
from vigia_do_site import (  # noqa: E402
    ROTAS,
    SITES,
    RESPOSTA_ESPERADA,
    Resposta,
    a_sondar,
    julgar,
    linha_de_estado,
    main,
    medir,
)

WORKFLOW = RAIZ / ".github" / "workflows" / "vigia-do-site.yml"


# ---------------------------------------------------------------------------
# O que ele APROVA — e só isto.
# ---------------------------------------------------------------------------
def test_aprova_o_host_que_entrega_a_pagina():
    assert julgar("meshcraft.top", Resposta(status=200, url_final="https://meshcraft.top/")) == []


# ---------------------------------------------------------------------------
# O que ele REPROVA. Cada caso é um jeito real de a loja amanhecer fechada.
# ---------------------------------------------------------------------------
def test_reprova_o_erro_do_servidor_e_diz_o_numero_recebido():
    # Célula viva e travada: o processo não morreu, então o `restart` do compose
    # não reage. Quem vê isto é o visitante — ou este vigia.
    queixas = julgar("meshcraft.top", Resposta(status=500))
    assert queixas != []
    assert "500" in queixas[0]


def test_reprova_o_portao_do_traefik_sem_ninguem_atras():
    queixas = julgar("meshcraft.top", Resposta(status=502))
    assert queixas != []
    assert "502" in queixas[0]


def test_reprova_a_raiz_que_virou_pagina_nao_encontrada():
    # A raiz sem oferta padrão responde 404 (contrato de infra/sites.json). O
    # cadeado estaria verde e a loja, fechada.
    queixas = julgar("meshcraft.top", Resposta(status=404))
    assert queixas != []
    assert "404" in queixas[0]


def test_reprova_quando_nao_conseguiu_medir():
    # INV-CI01: "não medi" jamais vira "está no ar".
    queixas = julgar("x.top", Resposta(erro="não consegui medir: timeout"))
    assert queixas != []
    assert "timeout" in queixas[0]


def test_reprova_a_medicao_pela_metade_e_a_chama_pelo_nome():
    # Sem status e sem erro não há medição nenhuma, e o silêncio não aprova.
    # A queixa precisa dizer ISSO: caída na régua do 200, ela sairia como
    # "respondeu None na raiz", que manda o leitor procurar defeito no servidor
    # quando o defeito é do próprio vigia.
    queixas = julgar("x.top", Resposta())
    assert queixas != []
    assert "pela metade" in queixas[0]


def test_a_linha_de_estado_diz_PASS_ou_FAIL_e_o_que_recebeu():
    assert "PASS" in linha_de_estado("x.top", Resposta(status=200, url_final="https://x.top/"))
    assert "FAIL" in linha_de_estado("x.top", Resposta(status=503))
    assert "FAIL" in linha_de_estado("x.top", Resposta(erro="não consegui medir: DNS"))


# ---------------------------------------------------------------------------
# A INSISTÊNCIA — soluço de rede não abre chamado, defeito estável não espera.
# ---------------------------------------------------------------------------
def test_insiste_com_pausa_quando_nao_conseguiu_medir(monkeypatch):
    tentativas = []
    pausas = []

    def _falha(host, timeout):
        tentativas.append(host)
        return Resposta(erro="não consegui medir: timeout")

    monkeypatch.setattr("vigia_do_site._uma_tentativa", _falha)
    monkeypatch.setattr("vigia_do_site.time.sleep", pausas.append)
    assert medir("x.top").erro is not None
    assert len(tentativas) > 1, "desistiu na primeira: um blip de rede abriria chamado"
    # Insistir sem pausa é insistir dentro do mesmo milissegundo, que mede o
    # mesmo instante três vezes e continua chamando isso de três medições.
    assert len(pausas) == len(tentativas) - 1
    assert all(pausa > 0 for pausa in pausas)


def test_nao_insiste_diante_de_um_defeito_estavel(monkeypatch):
    tentativas = []

    def _quinhentos(host, timeout):
        tentativas.append(host)
        return Resposta(status=500)

    monkeypatch.setattr("vigia_do_site._uma_tentativa", _quinhentos)
    monkeypatch.setattr("vigia_do_site.time.sleep", lambda _: None)
    assert medir("x.top").status == 500
    assert tentativas == ["x.top"], "repetir um 500 só atrasaria o alarme"


# ---------------------------------------------------------------------------
# QUEM ele sonda — a mesma lista do vigia do cadeado, para que os dois não
# possam discordar sobre quais endereços esta casa tem.
# ---------------------------------------------------------------------------
def test_sonda_os_hosts_de_verdade_que_estao_no_ar_hoje():
    sondados, _ = a_sondar(
        json.loads(SITES.read_text(encoding="utf-8")),
        ROTAS.read_text(encoding="utf-8"),
    )
    assert sondados, "a lista de hosts a sondar saiu VAZIA"
    assert "meshcraft.top" in sondados
    assert "www.meshcraft.top" in sondados


def test_o_host_dispensado_e_DECLARADO_nunca_sumido_em_silencio():
    sites = {"sites": [{"host": "exemplo.top", "active": True}]}
    rotas = 'rule: "Host(`operacoes.exemplo.org`) && PathPrefix(`/api/x`)"'
    sondados, dispensados = a_sondar(sites, rotas)
    assert "operacoes.exemplo.org" not in sondados
    assert any("operacoes.exemplo.org" in d for d in dispensados)


# ---------------------------------------------------------------------------
# O VEREDITO — e o falso-verde que o INV-CI01 existe para matar.
# ---------------------------------------------------------------------------
def test_lista_vazia_e_ERROR_nunca_PASS(monkeypatch, capsys):
    monkeypatch.setattr("vigia_do_site.a_sondar", lambda *a: ([], []))
    assert main([]) == 2
    assert "ERROR" in capsys.readouterr().out


def test_um_host_fora_do_ar_reprova_a_execucao_inteira(monkeypatch, capsys):
    monkeypatch.setattr("vigia_do_site.a_sondar", lambda *a: (["a.top", "b.top"], []))
    monkeypatch.setattr(
        "vigia_do_site.medir",
        lambda host, timeout=0: Resposta(status=200) if host == "a.top" else Resposta(status=503),
    )
    assert main([]) == 1
    saida = capsys.readouterr().out
    assert "FAIL" in saida
    assert "b.top" in saida


def test_todos_no_ar_aprova(monkeypatch):
    monkeypatch.setattr("vigia_do_site.a_sondar", lambda *a: (["a.top"], []))
    monkeypatch.setattr("vigia_do_site.medir", lambda host, timeout=0: Resposta(status=200))
    assert main([]) == 0


def test_a_regua_e_o_200_e_e_dela_que_sai_o_veredito():
    # Constante com nome bonito que ninguém consulta é decoração: o julgamento
    # tem de se mover quando ela se move.
    assert RESPOSTA_ESPERADA == 200
    assert julgar("x.top", Resposta(status=RESPOSTA_ESPERADA)) == []
    assert julgar("x.top", Resposta(status=RESPOSTA_ESPERADA + 1)) != []


# ---------------------------------------------------------------------------
# O PORTÃO DE DEPLOY — um vigia vermelho não pode trancar a porta por dentro.
# ---------------------------------------------------------------------------
def _linha_dos_conhecidos() -> str:
    fonte = Path(pd.__file__).read_text(encoding="utf-8")
    linhas = [ln for ln in fonte.splitlines() if "conhecidos = set(exigidos)" in ln]
    assert len(linhas) == 1, f"esperava UMA linha montando `conhecidos`, achei {len(linhas)}"
    return linhas[0]


def test_o_vigia_do_site_esta_em_conhecidos_e_NAO_em_exigidos():
    # O conserto de um site fora do ar É UMA PUBLICAÇÃO (armadilhas/180). Se o
    # vigia vermelho barrasse o deploy, ele trancaria a porta por dentro
    # justamente no dia em que o conserto precisa passar.
    assert "VIGIA_DO_SITE" in _linha_dos_conhecidos()
    fonte = Path(pd.__file__).read_text(encoding="utf-8")
    assert "VIGIA_DO_SITE: (" not in fonte, "vigia não é portão: fora de `exigidos`"
    assert pd.VIGIA_DO_SITE == ".github/workflows/vigia-do-site.yml"


def test_um_vermelho_do_vigia_do_site_nao_reprova_a_entrega():
    runs = [{"path": pd.VIGIA_DO_SITE, "conclusion": "failure", "databaseId": 1}]
    conhecidos = {pd.VIGIA_DO_SITE}
    assert pd.vermelhos_nao_previstos(runs, conhecidos).estado is not pd.Estado.FAIL


# ---------------------------------------------------------------------------
# A ESTEIRA — sem ela, o vigia é um script que ninguém roda.
# ---------------------------------------------------------------------------
def test_a_esteira_existe_acorda_pelo_relogio_e_chama_o_vigia():
    assert WORKFLOW.is_file(), f"esteira ausente: {WORKFLOW}"
    texto = WORKFLOW.read_text(encoding="utf-8")
    assert "cron:" in texto, "sem relógio, o vigia só roda quando alguém lembra"
    # `run:` colado, e não o nome solto: o comando aparece de novo no corpo da
    # issue, em "como conferir na mão", e a busca solta ficaria verde com uma
    # esteira que não chama vigia nenhum.
    assert "run: python ci/vigia_do_site.py" in texto
    assert "workflow_dispatch" in texto, "sem botão, ninguém confere na hora do incidente"
