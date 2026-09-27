"""O laboratório (degrau 12 do plano do painel de gestão, §8).

O que cada grupo de guardas protege, e por que ele existe:

1. **O estado é CALCULADO, nunca digitado.** Rodando, passado do prazo e
   encerrado saem das datas e da existência do registro de resposta. Nenhum
   campo `status` em lugar nenhum: quem escreve o resultado não escolhe em que
   grupo o experimento cai.
2. **"Não deu para saber" tem nome próprio e NÃO conta como aprendizado.**
   Achatá-lo em "perdeu" ensinaria a casa a fazer experimentos que sempre
   respondem alguma coisa, que é a forma mais cara de mentir para si mesma.
3. **Uma conta só.** O 12º do placar de doze (`aprendizados-validados-no-ciclo`)
   e esta tela são a MESMA função. Duas contagens divergiriam no primeiro
   experimento, e as duas telas do mesmo painel diriam números diferentes sobre
   a mesma pergunta.
4. **Livro ausente nunca vira "nenhum experimento".** `None` é "não consegui
   olhar"; lista vazia é "olhei e não há". A tela diz coisas diferentes.
5. **Vazio é estado de primeira classe.** A tela nasceu vazia, e é esse o
   estado que o mantenedor vê no primeiro dia: ela explica o que é um
   experimento e como nasce o primeiro, em vez de mostrar uma lista em branco.
6. **Todo grupo termina num gesto que já existe** (régua 5 do §2 do plano): a
   reunião de segunda escreve registro, e a fila dos robôs vira tarefa.
7. **Os experimentos da página de oferta vêm do catálogo** (decisão 5 do
   mantenedor, 26/09/2026), com estado, hipótese, métrica, datas, decisão e
   vencedora, e cada um leva às telas de resultado e de decisão. Catálogo fora
   do ar é aviso com o que fazer, nunca "nenhum experimento"; página sem
   experimento diz isso e aponta o Novo experimento. O catálogo falso é o
   `respx`, nos endereços e na forma de `ExperimentoDaPagina` do contrato.
"""

from __future__ import annotations

import datetime as dt

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.core import doze, laboratorio

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
CATALOGO = "http://catalogo:8000/api/catalogo"
SITE_ID = "5d0c7a1e-2b3f-4c6d-8e9f-0a1b2c3d4e5f"
EXPERIMENTOS = f"{CATALOGO}/sites/{SITE_ID}/paginas/oferta/experimentos"
ID_ATIVO = "7c2d9e4f-1a3b-4c5d-8e6f-9a0b1c2d3e4f"
ID_ENCERRADO = "1f2e3d4c-5b6a-4978-8a9b-0c1d2e3f4a5b"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"
HOJE = dt.date(2026, 9, 20)
PARTIDA = dt.date(2026, 9, 3)


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"
    monkeypatch.setattr(laboratorio.timezone, "localdate", lambda: HOJE)


def _dentro() -> Client:
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "id-opaco-123",
                "nome_exibido": "Fulano",
                "papel": None,
                "email": DONO,
            },
        )
    )
    c = Client()
    c.defaults["HTTP_COOKIE"] = COOKIE
    return c


def _experimento(arquivo: str, quando: str, dias: int = 14, **extra) -> dict:
    base = {
        "arquivo": arquivo,
        "tipo": "medicao",
        "quando": quando,
        "titulo": f"Experimento {arquivo}",
        "responde_a": None,
        "vence_em_dias": dias,
        "problema": "ninguém confirma no mesmo dia",
        "hipotese": "avisar por mensagem corta a espera pela metade",
        "metrica": "liberacoes-em-48h",
        "guarda": "se alguém esperar mais de 3 dias, paramos",
        "veredito": None,
    }
    base.update(extra)
    return base


def _resultado(arquivo: str, quando: str, alvo: str, veredito: str) -> dict:
    return {
        "arquivo": arquivo,
        "tipo": "medicao",
        "quando": quando,
        "titulo": f"Resultado {arquivo}",
        "responde_a": alvo,
        "vence_em_dias": None,
        "problema": None,
        "hipotese": None,
        "metrica": None,
        "guarda": None,
        "veredito": veredito,
    }


# ----------------------------------------------------- 1. o estado é calculado


def test_o_estado_sai_das_datas_e_da_resposta_nunca_de_um_campo():
    registros = [
        _experimento("a", "2026-09-15", dias=14),  # vence 29/09: rodando
        _experimento("b", "2026-09-01", dias=7),  # venceu 08/09, sem resposta
        _experimento("c", "2026-09-05", dias=7),
        _resultado("c-fim", "2026-09-12", "c", "venceu"),
    ]
    lab = laboratorio.montar(registros, HOJE)

    assert [e["arquivo"] for e in lab["rodando"]] == ["a"]
    assert [e["arquivo"] for e in lab["vencidos"]] == ["b"]
    assert [e["arquivo"] for e in lab["encerrados"]] == ["c"]
    assert lab["total"] == 3
    assert lab["rodando"][0]["dias"] == 9, "faltam 9 dias para 29/09"


def test_experimento_vencido_que_ganha_resposta_sai_do_grupo_dos_vencidos():
    vencido = [_experimento("b", "2026-09-01", dias=7)]
    assert len(laboratorio.montar(vencido, HOJE)["vencidos"]) == 1

    fechado = vencido + [_resultado("b-fim", "2026-09-18", "b", "perdeu")]
    lab = laboratorio.montar(fechado, HOJE)
    assert lab["vencidos"] == []
    assert [e["arquivo"] for e in lab["encerrados"]] == ["b"]


def test_registro_comum_do_livro_nao_e_experimento():
    comuns = [
        {"arquivo": "x", "tipo": "entrega", "quando": "2026-09-10", "hipotese": None},
        # O caso real de 05/09/2026: veredito de deploy respondendo a uma
        # entrega. Ele é uma medição com responde_a, e NÃO é um experimento.
        {
            "arquivo": "y",
            "tipo": "medicao",
            "quando": "2026-09-10",
            "responde_a": "x",
            "hipotese": None,
            "veredito": None,
        },
    ]
    lab = laboratorio.montar(comuns, HOJE)
    assert lab["total"] == 0


# ------------------------------------- 2. "não deu para saber" tem nome próprio


def test_inconclusivo_aparece_com_nome_proprio_e_nao_conta_como_aprendizado():
    registros = [
        _experimento("a", "2026-09-05", dias=7),
        _resultado("a-fim", "2026-09-12", "a", "nao-deu-para-saber"),
    ]
    lab = laboratorio.montar(registros, HOJE)

    grupos = {g["chave"]: g for g in lab["por_veredito"]}
    assert grupos["nao-deu-para-saber"]["nome"] == "Não deu para saber"
    assert [e["arquivo"] for e in grupos["nao-deu-para-saber"]["itens"]] == ["a"]
    assert lab["encerrados"][0]["aprendeu"] is False
    assert laboratorio.aprendizados_validados(registros, PARTIDA) == 0


def test_venceu_e_perdeu_contam_igual_porque_os_dois_ensinam():
    registros = [
        _experimento("a", "2026-09-05", dias=7),
        _resultado("a-fim", "2026-09-12", "a", "venceu"),
        _experimento("b", "2026-09-06", dias=7),
        _resultado("b-fim", "2026-09-13", "b", "perdeu"),
        _experimento("c", "2026-09-07", dias=7),
        _resultado("c-fim", "2026-09-14", "c", "nao-deu-para-saber"),
    ]
    assert laboratorio.aprendizados_validados(registros, PARTIDA) == 2


def test_a_conta_e_pela_data_do_resultado_e_nao_pela_do_experimento():
    # A aposta é anterior ao ciclo; o aprendizado acontece quando alguém
    # escreve o veredito, e é aí que ele conta.
    antes = [
        _experimento("a", "2026-08-20", dias=30),
        _resultado("a-fim", "2026-09-10", "a", "venceu"),
    ]
    assert laboratorio.aprendizados_validados(antes, PARTIDA) == 1

    fora = [
        _experimento("b", "2026-08-01", dias=7),
        _resultado("b-fim", "2026-08-15", "b", "venceu"),
    ]
    assert laboratorio.aprendizados_validados(fora, PARTIDA) == 0


# ------------------------------------------------------------ 3. uma conta só


def test_o_doze_e_o_laboratorio_sao_a_mesma_funcao():
    assert doze.aprendizados_validados is laboratorio.aprendizados_validados


def test_o_numero_do_placar_de_doze_vem_do_laboratorio():
    registros = [
        _experimento("a", "2026-09-05", dias=7),
        _resultado("a-fim", "2026-09-12", "a", "venceu"),
    ]
    itens = doze.medir_os_doze(
        barra=None,
        por_mes=None,
        liberacao=None,
        registros=registros,
        partida_em=PARTIDA,
        hoje=HOJE,
    )
    por_nome = {i["nome"]: i for i in itens}
    assert por_nome["aprendizados-validados-no-ciclo"]["valor"] == 1
    assert por_nome["aprendizados-validados-no-ciclo"]["veredito"] == "medido"


# ----------------------------------------- 4. livro ausente não é livro vazio


def test_livro_ausente_e_none_e_nunca_lista_vazia():
    assert laboratorio.montar(None, HOJE) is None
    assert laboratorio.aprendizados_validados(None, PARTIDA) is None
    assert laboratorio.montar([], HOJE)["total"] == 0
    assert laboratorio.aprendizados_validados([], PARTIDA) == 0


@respx.mock
def test_a_tela_diz_que_nao_olhou_quando_o_livro_nao_veio(monkeypatch):
    monkeypatch.setattr(laboratorio, "ler_registros", lambda: None)
    corpo = _dentro().get(reverse("laboratorio")).content.decode()

    assert "Não consegui olhar." in corpo
    assert "Ainda não há nenhum experimento" not in corpo, (
        "a tela afirmou que não há experimentos sem ter conseguido ler o livro: "
        "é o falso-verde que este ramo existe para impedir"
    )


# --------------------------------------------- 5. e 6. a tela vazia, e o gesto


@respx.mock
def test_a_tela_nasce_vazia_explicando_o_que_e_um_experimento(monkeypatch):
    monkeypatch.setattr(laboratorio, "ler_registros", lambda: [])
    resposta = _dentro().get(reverse("laboratorio"))
    corpo = resposta.content.decode()

    assert resposta.status_code == 200
    assert "Ainda não há nenhum experimento" in corpo
    assert "o problema que dói hoje" in corpo and "a hipótese" in corpo
    assert reverse("reuniao") in corpo, "o vazio termina no gesto que cria o primeiro"


@respx.mock
def test_a_tela_mostra_os_quatro_grupos_e_os_gestos(monkeypatch):
    registros = [
        _experimento("a", "2026-09-15", dias=14),
        _experimento("b", "2026-09-01", dias=7),
        _experimento("c", "2026-09-05", dias=7),
        _resultado("c-fim", "2026-09-12", "c", "venceu"),
        _experimento("d", "2026-09-06", dias=7),
        _resultado("d-fim", "2026-09-13", "d", "nao-deu-para-saber"),
    ]
    monkeypatch.setattr(laboratorio, "ler_registros", lambda: registros)
    corpo = _dentro().get(reverse("laboratorio")).content.decode()

    assert "Rodando agora" in corpo
    assert "Passaram do prazo e ninguém escreveu o resultado" in corpo
    assert "Venceu (1)" in corpo and "Perdeu (0)" in corpo
    assert "Não deu para saber (1)" in corpo
    assert reverse("reuniao") in corpo, "o gesto de fechar o que venceu de prazo"
    assert reverse("caixa_robos") in corpo, "o gesto de virar tarefa o que venceu"


@respx.mock
def test_os_selos_de_prazo_leem_certo_em_um_dia_no_dia_e_depois(monkeypatch):
    """Os três defeitos que só a prévia renderizada pegou (05/09/2026).

    "faltam 1 dias" e "faltam 0 dias" passam por qualquer suíte verde; e o selo
    do vencido dizia "venceu em 08/09", que na mesma tela onde existe o veredito
    "Venceu" fazia um experimento atrasado parecer um experimento bem-sucedido.
    """
    registros = [
        _experimento("um-dia", "2026-09-14", dias=7),  # vence 21/09: falta 1 dia
        _experimento("hoje", "2026-09-13", dias=7),  # vence 20/09: vence hoje
        _experimento("passou", "2026-09-01", dias=7),  # venceu 08/09
    ]
    monkeypatch.setattr(laboratorio, "ler_registros", lambda: registros)
    corpo = _dentro().get(reverse("laboratorio")).content.decode()

    assert "falta 1 dia<" in corpo and "faltam 1 dia" not in corpo
    assert "vence hoje" in corpo and "faltam 0 dias" not in corpo
    assert "o prazo terminou em 08/09/2026" in corpo
    assert (
        "venceu em" not in corpo
    ), "o selo do atrasado não pode usar a palavra do veredito de sucesso"


@respx.mock
def test_a_tela_nao_conjuga_verbo_em_contagem_zerada(monkeypatch):
    monkeypatch.setattr(laboratorio, "ler_registros", lambda: [])
    corpo = _dentro().get(reverse("laboratorio")).content.decode()

    # `pluralize` do Django trata zero como PLURAL, e contagem com verbo colado
    # sai torta justamente no caso que mais aparece ("0 experimentos venceram").
    for torto in ("experimentos venceram", "experimentos perderam", "0 experimento "):
        assert torto not in corpo


# ------------------------------- 7. os experimentos da página, lidos do catálogo


def _catalogo(monkeypatch, resposta: httpx.Response) -> None:
    """O catálogo falso: o site deste domínio e a resposta de `listExperiments`."""
    monkeypatch.setenv("CATALOGO_API_URL", CATALOGO)
    monkeypatch.setenv("TOKEN_CATALOGO", "token-do-par-admin-catalogo")
    monkeypatch.setattr(laboratorio, "ler_registros", lambda: [])
    respx.get(f"{CATALOGO}/sites/by-host/testserver").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": SITE_ID,
                "host": "testserver",
                "name": "Meshcraft",
                "active": True,
            },
        )
    )
    respx.get(EXPERIMENTOS).mock(return_value=resposta)


def _da_pagina(experimento_id: str, estado: str, **mais) -> dict:
    """Um `ExperimentoDaPagina` na forma do contrato."""
    corpo = {
        "id": experimento_id,
        "site_id": SITE_ID,
        "slug": "oferta",
        "secao": "cubo",
        "slot": "headline",
        "hipotese": f"Hipótese do experimento {estado}.",
        "metrica_principal": "cta_checkout",
        "taxa_base": 0.1,
        "mde": 0.03,
        "n_por_braco_planejado": 1600,
        "dias_planejados": 21,
        "estado": estado,
        "decisao": None,
        "vencedora": None,
        "criado_em": "2026-09-01T15:00:00Z",
        "iniciado_em": "2026-09-02T15:00:00Z",
        "fim_planejado": "2026-09-23T15:00:00Z",
        "encerrado_em": None,
        "variantes": [
            {"variante_id": "a", "peso": 5000, "valor": "Texto no ar"},
            {"variante_id": "b", "peso": 5000, "valor": "Texto novo"},
        ],
    }
    corpo.update(mais)
    return corpo


@respx.mock
def test_a_tela_mostra_os_experimentos_da_pagina_lidos_do_catalogo(monkeypatch):
    _catalogo(
        monkeypatch,
        httpx.Response(
            200,
            json=[
                _da_pagina(ID_ATIVO, "ativo"),
                _da_pagina(
                    ID_ENCERRADO,
                    "encerrado",
                    decisao="promover",
                    vencedora="b",
                    encerrado_em="2026-09-24T15:00:00Z",
                ),
            ],
        ),
    )
    resposta = _dentro().get(reverse("laboratorio"))
    corpo = resposta.content.decode()

    assert resposta.status_code == 200
    assert "Experimentos da página de oferta" in corpo
    assert "Hipótese do experimento ativo." in corpo
    assert "Hipótese do experimento encerrado." in corpo
    assert "Ativo" in corpo and "Encerrado" in corpo
    assert "Entrada no checkout" in corpo, "a métrica sai com o nome, não com a chave"
    for data in ("01/09/2026", "02/09/2026", "23/09/2026", "24/09/2026"):
        assert data in corpo, f"a data {data} do experimento não apareceu"
    assert "Promover" in corpo, "a decisão do encerrado"
    assert "Vencedora: versão b" in corpo
    for experimento_id in (ID_ATIVO, ID_ENCERRADO):
        assert reverse("resultado_do_experimento", args=[experimento_id]) in corpo
        assert reverse("decisao_do_experimento", args=[experimento_id]) in corpo
    assert reverse("experimentos") in corpo


@respx.mock
def test_catalogo_fora_do_ar_avisa_o_que_fazer_e_nunca_diz_nenhum(monkeypatch):
    _catalogo(monkeypatch, httpx.Response(503))
    resposta = _dentro().get(reverse("laboratorio"))
    corpo = resposta.content.decode()

    assert resposta.status_code == 200, "a tela abre e diz o que não conseguiu ver"
    assert "Não consegui ler os experimentos da página." in corpo
    assert "Recarregue esta tela" in corpo, "o aviso diz o que fazer"
    assert "Esta página ainda não tem experimento" not in corpo, (
        "a tela afirmou que a página não tem experimento sem ter conseguido "
        "perguntar ao catálogo"
    )


@respx.mock
def test_sem_catalogo_configurado_avisa_e_nunca_diz_nenhum(monkeypatch):
    monkeypatch.delenv("CATALOGO_API_URL", raising=False)
    monkeypatch.setattr(laboratorio, "ler_registros", lambda: [])
    corpo = _dentro().get(reverse("laboratorio")).content.decode()

    assert "Não consegui ler os experimentos da página." in corpo
    assert "Esta página ainda não tem experimento" not in corpo


@respx.mock
def test_pagina_sem_experimento_diz_isso_e_aponta_o_novo(monkeypatch):
    _catalogo(monkeypatch, httpx.Response(200, json=[]))
    corpo = _dentro().get(reverse("laboratorio")).content.decode()

    assert "Esta página ainda não tem experimento" in corpo
    assert reverse("experimento_novo") in corpo
    assert "Não consegui ler os experimentos da página." not in corpo
