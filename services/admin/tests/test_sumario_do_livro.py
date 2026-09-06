"""A tela que cola o sumário do livro: `/admin/escola/<curso>/sumario/`.

NENHUM TRECHO DO LIVRO ENTRA AQUI. O sumário de verdade é obra não lançada do
mantenedor e este repositório é público (`armadilhas/331`): o que este arquivo
usa é um sumário de MENTIRA, escrito para o teste, com a mesma FORMA do de
verdade (as molduras de bloco, a linha de encomenda com o título entre aspas, a
promessa recuada, as peças numeradas de 1 a 16, as sub-linhas do "Eu faço", as
linhas de Boss) e conteúdo inventado de ponta a ponta.

A `cursos` é dublada pelo `respx` com respostas no formato do contrato
congelado. O que cada promessa custa, se cair:

1. **O interpretador acha as encomendas, as peças e o que é próprio de cada
   uma**, casando a peça pelo NÚMERO. Sem isso o curso fica com 34 números e
   mais nada, e todo verificador que vier depois não tem o que verificar.
2. **Campo que já tem texto NUNCA é sobrescrito**, e a prévia diz que
   preservou. É a promessa mais cara do arquivo: um importador que apaga o que
   o mantenedor escreveu perde meses de trabalho que só existem naquele banco.
3. **PREVER não grava nada** e **IMPORTAR grava pela porta de máquina**, nunca
   no banco direto (esta célula não tem o banco da `cursos`, Lei 3).
4. **Encomenda em que nada mudaria não é enviada**: sem isso, importar duas
   vezes subiria a versão das 34 sem trocar uma letra.
5. **Encomenda que a porta não deixou LER não é gravada.** Gravar sem saber o
   que já estava lá é exatamente o que apagaria obra.
6. **A tela não guarda o sumário colado** em lugar nenhum desta célula.
"""

import re
from pathlib import Path

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.core import sumario as tela
from apps.core.aulas import PECAS

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
CATALOGO = "http://catalogo:8000/api/catalogo"
CURSOS = "http://cursos:8000/api/cursos"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"
SITE_ID = "site-mesh"
CURSO = "profissional"
CONTRATO = Path(__file__).resolve().parents[3] / "contracts" / "cursos.openapi.yaml"

TIPOS = [tipo for tipo, _, _ in PECAS]

# ---------------------------------------------------------------------------
# O SUMÁRIO DE MENTIRA — a forma do de verdade, o conteúdo inventado
# ---------------------------------------------------------------------------
# Duas encomendas de um bloco, com um Boss no fim. E00 exercita a peça sem
# texto próprio (a 4), a peça com sub-linhas (a 7), a peça que continua na
# linha de baixo (a 11) e a peça 13 com o nome da Parte I; E01 exercita a peça
# 13 com o nome da Parte III, que é a mesma peça com outra palavra.
SUMARIO_DE_MENTIRA = """## PARTE I — INVENTADA
*O vilão: nenhum · Degraus 1-3 · Título: Nível de mentira*

```
═══ BLOCO A — E00 · E01 ═════════════════════════════════════════════════════

E00 · "Faça um cubo de mentira."
     A promessa inventada desta encomenda de teste.
  1  O pedido — o Cliente Inventado
  4  Recall de 2 minutos
  5  Par de comparação — Figura 0.1: o cubo bom e o cubo ruim
     Figura 0.2: o mesmo cubo de outro ângulo
  7  Eu faço
        0.1  A primeira seção inventada
        0.2  A segunda seção inventada
 11  Erros clássicos — Errar o primeiro · Errar o segundo · Errar o
     terceiro, que continua nesta linha
 13  Crítica de atelier — a crítica inventada da Parte I
 16  Dicionário · Cartão de 1 página · Respostas

E01 · "Faça uma esfera de mentira."          ★ marca decorativa
     A segunda promessa inventada.
  1  O pedido — Personagem Inventada
 13  Revisão de estúdio — a revisão inventada da Parte III

 ── BOSS A — "O Boss Inventado" · Medalha: Medalha Inventada ────────────────
```
"""


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    monkeypatch.setenv("CATALOGO_API_URL", CATALOGO)
    monkeypatch.setenv("TOKEN_CATALOGO", "token-do-par-admin-catalogo")
    monkeypatch.setenv("CURSOS_API_URL", CURSOS)
    monkeypatch.setenv("CURSOS_API_TOKEN", "token-do-par-admin-cursos")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


# ---------------------------------------------------------------------------
# A PORTA DUBLADA
# ---------------------------------------------------------------------------
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
    respx.get(f"{CATALOGO}/sites/by-host/testserver").mock(
        return_value=httpx.Response(200, json={"id": SITE_ID, "host": "testserver"})
    )
    cliente = Client()
    cliente.defaults["HTTP_COOKIE"] = COOKIE
    return cliente


def _linha(numero: str) -> dict:
    return {
        "numero": numero,
        "ordem": int(numero[1:]),
        "titulo_exibido": f"Encomenda {numero[1:]}",
        "bloco": {"letra": "A", "ordem": 1, "parte": 1},
        "estado": "rascunho",
        "versao": 1,
        "publicada_em": None,
        "e_boss": False,
        "banca_nivel": None,
    }


def _aula(numero: str, *, textos=None, cliente="") -> dict:
    textos = textos or {}
    return _linha(numero) | {
        "pedido": "",
        "cliente": cliente,
        "instrumento": "studs",
        "minimo": "Um mínimo inventado.",
        "aceito_quando": ["Uma condição inventada."],
        "quiz": [{"pergunta": "Pergunta?", "resposta_modelo": "Resposta."}],
        "video_url": "https://exemplo.com/v/inventado",
        "pecas": [{"tipo": t, "texto": textos.get(t, "")} for t in TIPOS],
        "pausas": [
            {
                "ordem": 1,
                "segundo": 90,
                "tipo": "faca_agora",
                "pede": "Abra o programa",
                "campos": ["nota"],
            }
        ],
    }


def _porta(aulas: dict, *, gravar=None):
    """A `cursos` dublada: a lista, cada encomenda, e a gravação.

    Devolve a lista de rotas de gravação, para os testes conferirem o que foi
    enviado (ou que NADA foi).
    """
    respx.get(f"{CURSOS}/cursos/{CURSO}/aulas").mock(
        return_value=httpx.Response(200, json=[_linha(n) for n in aulas])
    )
    for numero, corpo in aulas.items():
        respx.get(f"{CURSOS}/cursos/{CURSO}/aulas/{numero}").mock(
            return_value=httpx.Response(200, json=corpo)
        )
    return respx.put(url__regex=rf"{re.escape(CURSOS)}/cursos/{CURSO}/aulas/\w+").mock(
        side_effect=gravar or (lambda pedido: httpx.Response(200, json={"versao": 2}))
    )


def _url(nome: str) -> str:
    return reverse(nome, kwargs={"curso": CURSO})


# ---------------------------------------------------------------------------
# 1. O INTERPRETADOR
# ---------------------------------------------------------------------------
def test_o_interpretador_acha_as_encomendas_o_titulo_e_a_peca_pelo_numero():
    lido = tela.interpretar(SUMARIO_DE_MENTIRA)

    assert [e["numero"] for e in lido["encomendas"]] == ["E00", "E01"]
    primeira = lido["encomendas"][0]
    assert primeira["titulo"] == "Faça um cubo de mentira."
    # A peça 1 traz o cliente, e ele vai para o campo `cliente` da encomenda.
    assert primeira["cliente"] == "o Cliente Inventado"
    # A 5 é a quinta da ordem canônica; a 7 é a sétima. O nome não decide nada.
    assert primeira["pecas"]["par_de_comparacao"].startswith("Figura 0.1")
    assert primeira["pecas"]["eu_faco"].startswith("0.1  A primeira seção")
    # Peça sem texto próprio (`4  Recall de 2 minutos`) não vira campo nenhum.
    assert "recall" not in primeira["pecas"]


def test_a_peca_13_muda_de_nome_por_parte_e_cai_no_mesmo_tipo():
    """ "Crítica de atelier" e "Revisão de estúdio" são a MESMA peça do modelo.

    Casar pelo número resolve isto sem um mapa de apelidos. Se um dia o
    casamento voltar a ser pelo nome, este teste cai.
    """
    encomendas = tela.interpretar(SUMARIO_DE_MENTIRA)["encomendas"]

    assert (
        encomendas[0]["pecas"]["critica_de_atelier"] == "a crítica inventada da Parte I"
    )
    assert (
        encomendas[1]["pecas"]["critica_de_atelier"]
        == "a revisão inventada da Parte III"
    )


def test_as_linhas_de_continuacao_entram_na_peca_que_estava_aberta():
    """As sub-linhas do "Eu faço" e a figura a mais do "Par de comparação".

    Sem isto, metade do que o sumário diz de cada encomenda some em silêncio:
    a primeira linha entraria e as de baixo virariam nada.
    """
    primeira = tela.interpretar(SUMARIO_DE_MENTIRA)["encomendas"][0]

    assert primeira["pecas"]["eu_faco"].splitlines() == [
        "0.1  A primeira seção inventada",
        "0.2  A segunda seção inventada",
    ]
    assert "Figura 0.2" in primeira["pecas"]["par_de_comparacao"]
    assert "terceiro, que continua nesta linha" in primeira["pecas"]["erros_classicos"]


def test_o_titulo_do_boss_e_lido_sem_a_medalha():
    assert tela.interpretar(SUMARIO_DE_MENTIRA)["bosses"] == [("A", "O Boss Inventado")]


def test_a_decoracao_depois_do_titulo_nao_entra_no_titulo():
    """`★ marca decorativa` fica de fora: o título é o que está entre aspas."""
    encomendas = tela.interpretar(SUMARIO_DE_MENTIRA)["encomendas"]

    assert encomendas[1]["titulo"] == "Faça uma esfera de mentira."


def test_texto_que_nao_e_um_sumario_nao_vira_encomenda_nenhuma():
    lido = tela.interpretar("Uma lista de compras.\n  1  arroz\n  2  feijão\n")

    assert lido["encomendas"] == []


def test_as_16_pecas_numeradas_sao_as_do_contrato_na_ordem():
    """O casamento é pelo número, então a ordem daqui É o contrato.

    Se a ordem canônica do contrato mudar e esta lista não mudar junto, todo
    texto do sumário entra na peça errada, calado. Por isso o teste lê o
    contrato do disco em vez de repetir a lista à mão.
    """
    texto = CONTRATO.read_text(encoding="utf-8")
    bloco = texto[texto.index("\n    TipoDePeca:") :]
    bloco = bloco[bloco.index("enum:") : bloco.index("type: string")]
    do_contrato = re.findall(r"^\s*- (\S+)$", bloco, flags=re.M)

    assert list(tela.PECAS_NUMERADAS) == do_contrato[:16]
    # As duas internas ficam de fora: o sumário não as tem, e o importador
    # nunca as toca.
    assert do_contrato[16:] == ["roteiro", "guia_do_mentor"]


# ---------------------------------------------------------------------------
# 2. A REGRA QUE NÃO SE NEGOCIA: campo escrito nunca é sobrescrito
# ---------------------------------------------------------------------------
def test_campo_ja_escrito_e_preservado_e_o_vazio_e_preenchido():
    """A promessa mais cara do arquivo, medida no casamento, sem rede."""
    encomenda = tela.interpretar(SUMARIO_DE_MENTIRA)["encomendas"][0]
    aula = _aula(
        "E00",
        cliente="Um cliente que EU escrevi",
        textos={"eu_faco": "O texto que EU escrevi, e que não pode sumir."},
    )

    casado = tela.casar(encomenda, aula)

    preservados = {c["campo"] for c in casado["preservar"]}
    assert any("Eu faço" in campo for campo in preservados)
    assert "Cliente" in preservados
    por_tipo = {p["tipo"]: p["texto"] for p in casado["corpo"]["pecas"]}
    assert por_tipo["eu_faco"] == "O texto que EU escrevi, e que não pode sumir."
    assert casado["corpo"]["cliente"] == "Um cliente que EU escrevi"
    # E o que estava vazio foi preenchido na mesma passada.
    assert por_tipo["par_de_comparacao"].startswith("Figura 0.1")


def test_espaco_em_branco_nao_conta_como_texto_escrito():
    """Um espaço solto é campo vazio para quem olha a tela."""
    encomenda = tela.interpretar(SUMARIO_DE_MENTIRA)["encomendas"][0]

    casado = tela.casar(encomenda, _aula("E00", textos={"eu_faco": "   \n  "}))

    por_tipo = {p["tipo"]: p["texto"] for p in casado["corpo"]["pecas"]}
    assert por_tipo["eu_faco"].startswith("0.1  A primeira seção")


def test_encomenda_sem_nada_a_preencher_nao_vira_corpo():
    """Sem isto, importar duas vezes subiria a versão das 34 sem mudar nada."""
    encomenda = tela.interpretar(SUMARIO_DE_MENTIRA)["encomendas"][0]
    cheia = _aula(
        "E00",
        cliente="já escrito",
        textos={tipo: "já escrito" for tipo in TIPOS},
    )

    casado = tela.casar(encomenda, cheia)

    assert casado["corpo"] is None
    assert casado["preencher"] == []


def test_o_corpo_leva_o_que_estava_gravado_e_so_troca_os_vazios():
    """`putLesson` SUBSTITUI a encomenda inteira: o que não vai no corpo some.

    O quiz, as pausas, o mínimo e o "Aceito quando" não vêm do sumário, e
    precisam viajar de volta intactos ou seriam apagados pela importação.
    """
    encomenda = tela.interpretar(SUMARIO_DE_MENTIRA)["encomendas"][0]
    aula = _aula("E00")

    corpo = tela.casar(encomenda, aula)["corpo"]

    for campo in ("minimo", "aceito_quando", "quiz", "pausas", "video_url"):
        assert corpo[campo] == aula[campo], campo
    assert [p["tipo"] for p in corpo["pecas"]] == TIPOS


def test_o_corpo_tem_exatamente_as_chaves_obrigatorias_do_contrato():
    """Chave a menos é 422 em toda gravação; chave a mais também
    (`additionalProperties: false` em `AulaParaGravarSchema`)."""
    texto = CONTRATO.read_text(encoding="utf-8")
    bloco = texto[texto.index("\n    AulaParaGravarSchema:") :]
    bloco = bloco[
        bloco.index("required:") : bloco.index("type: object", bloco.index("required:"))
    ]
    obrigatorias = set(re.findall(r"^\s*- (\S+)$", bloco, flags=re.M))

    encomenda = tela.interpretar(SUMARIO_DE_MENTIRA)["encomendas"][0]
    corpo = tela.casar(encomenda, _aula("E00"))["corpo"]

    assert set(corpo) == obrigatorias


# ---------------------------------------------------------------------------
# 3. A TELA: PREVER não grava, IMPORTAR grava pela porta
# ---------------------------------------------------------------------------
@pytest.mark.django_db
@respx.mock
def test_a_tela_abre_vazia_sem_ir_a_sala_de_aula():
    lista = respx.get(f"{CURSOS}/cursos/{CURSO}/aulas")

    resposta = _dentro().get(_url("escola_sumario"))

    assert resposta.status_code == 200
    assert not lista.called


@pytest.mark.django_db
@respx.mock
def test_prever_mostra_o_que_faria_e_nao_grava_nada():
    gravar = _porta(
        {
            "E00": _aula("E00", textos={"eu_faco": "O texto que EU escrevi."}),
            "E01": _aula("E01"),
        }
    )

    resposta = _dentro().post(
        _url("escola_sumario_prever"), {"sumario": SUMARIO_DE_MENTIRA}
    )

    assert resposta.status_code == 200
    assert not gravar.called
    corpo = resposta.content.decode()
    assert "Vai preencher" in corpo
    assert "Deixado em paz" in corpo


@pytest.mark.django_db
@respx.mock
def test_importar_grava_pela_porta_de_maquina_e_preserva_o_que_ja_havia():
    enviados = []

    def guardar(pedido):
        import json

        enviados.append((str(pedido.url), json.loads(pedido.content)))
        return httpx.Response(200, json={"versao": 2})

    _porta(
        {
            "E00": _aula("E00", textos={"eu_faco": "O texto que EU escrevi."}),
            "E01": _aula("E01"),
        },
        gravar=guardar,
    )

    resposta = _dentro().post(
        _url("escola_sumario_importar"), {"sumario": SUMARIO_DE_MENTIRA}
    )

    assert resposta.status_code == 200
    assert len(enviados) == 2
    url, corpo = enviados[0]
    assert f"/cursos/{CURSO}/aulas/E00" in url and f"site_id={SITE_ID}" in url
    por_tipo = {p["tipo"]: p["texto"] for p in corpo["pecas"]}
    assert por_tipo["eu_faco"] == "O texto que EU escrevi."
    assert por_tipo["par_de_comparacao"].startswith("Figura 0.1")
    assert corpo["cliente"] == "o Cliente Inventado"


@pytest.mark.django_db
@respx.mock
def test_importar_nao_toca_na_encomenda_que_ja_esta_inteira():
    cheia = _aula(
        "E00", cliente="já escrito", textos={tipo: "já escrito" for tipo in TIPOS}
    )
    gravar = _porta({"E00": cheia, "E01": _aula("E01")})

    _dentro().post(_url("escola_sumario_importar"), {"sumario": SUMARIO_DE_MENTIRA})

    assert gravar.call_count == 1
    assert "E01" in str(gravar.calls[0].request.url)


@pytest.mark.django_db
@respx.mock
def test_encomenda_que_a_porta_nao_deixou_ler_nao_e_gravada():
    """Fail-closed: sem saber o que estava lá, gravar poderia apagar obra."""
    respx.get(f"{CURSOS}/cursos/{CURSO}/aulas").mock(
        return_value=httpx.Response(200, json=[_linha("E00"), _linha("E01")])
    )
    respx.get(f"{CURSOS}/cursos/{CURSO}/aulas/E00").mock(
        return_value=httpx.Response(500)
    )
    respx.get(f"{CURSOS}/cursos/{CURSO}/aulas/E01").mock(
        return_value=httpx.Response(200, json=_aula("E01"))
    )
    gravar = respx.put(
        url__regex=rf"{re.escape(CURSOS)}/cursos/{CURSO}/aulas/\w+"
    ).mock(return_value=httpx.Response(200, json={"versao": 2}))

    resposta = _dentro().post(
        _url("escola_sumario_importar"), {"sumario": SUMARIO_DE_MENTIRA}
    )

    assert gravar.call_count == 1
    assert "E01" in str(gravar.calls[0].request.url)
    assert "Não consegui ler" in resposta.content.decode()


@pytest.mark.django_db
@respx.mock
def test_encomenda_do_sumario_que_nao_existe_no_curso_e_dita_e_ignorada():
    gravar = _porta({"E00": _aula("E00")})

    resposta = _dentro().post(
        _url("escola_sumario_prever"), {"sumario": SUMARIO_DE_MENTIRA}
    )

    assert not gravar.called
    corpo = resposta.content.decode()
    assert "não existem neste curso" in corpo
    assert "E01" in corpo


@pytest.mark.django_db
@respx.mock
def test_caixa_vazia_e_texto_sem_encomenda_nao_vao_a_porta():
    lista = respx.get(f"{CURSOS}/cursos/{CURSO}/aulas")
    cliente = _dentro()

    vazia = cliente.post(_url("escola_sumario_prever"), {"sumario": "   "})
    torto = cliente.post(_url("escola_sumario_importar"), {"sumario": "qualquer coisa"})

    assert vazia.status_code == 400 and torto.status_code == 400
    assert not lista.called
    assert "Cole o sumário" in vazia.content.decode()
    assert "Não achei nenhuma encomenda" in torto.content.decode()


@pytest.mark.django_db
@respx.mock
def test_sala_de_aula_fora_do_ar_nao_vira_gravacao():
    respx.get(f"{CURSOS}/cursos/{CURSO}/aulas").mock(return_value=httpx.Response(500))
    gravar = respx.put(
        url__regex=rf"{re.escape(CURSOS)}/cursos/{CURSO}/aulas/\w+"
    ).mock(return_value=httpx.Response(200, json={"versao": 2}))

    resposta = _dentro().post(
        _url("escola_sumario_importar"), {"sumario": SUMARIO_DE_MENTIRA}
    )

    assert resposta.status_code == 503
    assert not gravar.called


@pytest.mark.django_db
@respx.mock
def test_o_texto_colado_volta_para_a_caixa_e_nao_fica_guardado_nesta_celula():
    """A obra do mantenedor não mora aqui (`armadilhas/331`).

    A prova é dupla: o texto volta na página (para o segundo gesto), e nenhuma
    tabela desta célula ganhou uma linha com ele.
    """
    from django.apps import apps

    _porta({"E00": _aula("E00"), "E01": _aula("E01")})
    antes = {
        modelo: modelo.objects.count()
        for modelo in apps.get_app_config("core").get_models()
    }

    resposta = _dentro().post(
        _url("escola_sumario_prever"), {"sumario": SUMARIO_DE_MENTIRA}
    )

    assert "Faça um cubo de mentira." in resposta.content.decode()
    assert {m: m.objects.count() for m in antes} == antes


@pytest.mark.django_db
@respx.mock
def test_a_tela_nunca_chama_as_operacoes_que_nao_sabem_de_curso():
    """As irmãs sem curso varrem o site inteiro e misturariam dois cursos."""
    sem_curso = respx.get(f"{CURSOS}/aulas")
    _porta({"E00": _aula("E00"), "E01": _aula("E01")})

    _dentro().post(_url("escola_sumario_importar"), {"sumario": SUMARIO_DE_MENTIRA})

    assert not sem_curso.called


def test_a_porta_fecha_para_quem_nao_e_admin():
    """A tela mora dentro do `/admin/`, e quem autoriza é a porta desta área."""
    resposta = Client().get(_url("escola_sumario"))

    assert resposta.status_code in (302, 403)
