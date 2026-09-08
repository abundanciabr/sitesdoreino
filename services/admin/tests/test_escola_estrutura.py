"""Colar os modulos e as aulas de um curso: `/admin/escola/<curso>/estrutura/`.

A `cursos` e dublada pelo `respx` com respostas NO FORMATO DO CONTRATO
congelado (`contracts/cursos.openapi.yaml`, operacoes `listLessons` e
`putCourseStructure`), e o `catalogo` responde o site do host. Dois guardas
leem o contrato do disco para que a tela e o contrato nao possam divergir em
silencio.

O que cada promessa custa, se cair:

1. **O interpretador acha o erro e diz a LINHA.** Sem isso, um texto de trinta
   modulos com uma linha torta vira um 422 generico da porta, e o mantenedor
   fica procurando onde. Cada erro tem teste proprio com a linha certa.
2. **PREVER nao escreve.** Se escrevesse, o botao que existe para olhar antes
   seria o botao que faz. O guarda mede a AUSENCIA da chamada de escrita.
3. **IMPORTAR manda o corpo certo**, com `nome` sempre preenchido e
   `boss_titulo` NULO quando a linha do modulo nao trouxe Boss. Nulo, no
   contrato, quer dizer nao mexer; vazio APAGARIA o titulo gravado.
4. **A Banca de quem ja existe viaja de volta.** A estrutura e a fonte dela por
   contrato, e mandar sem ela zeraria o nivel de Banca de toda aula que o
   tivesse, em silencio.
5. **Titulo escrito nao se sobrescreve, e a previa diz isso.** Um importador
   que apaga o que o mantenedor escreveu perde trabalho que so existe naquele
   banco.
6. **A recusa da porta aparece em portugues e nada foi gravado.** A sala grava
   tudo de uma vez ou nada, e a tela precisa dizer isso com todas as letras.
7. **O link da lista de cursos leva a esta tela.** Sem ele a tela existe e
   ninguem chega nela.
"""

import re
from pathlib import Path

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.auditoria.models import Registro
from apps.core.estrutura import casar, corpo_para_gravar, interpretar

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
CATALOGO = "http://catalogo:8000/api/catalogo"
CURSOS = "http://cursos:8000/api/cursos"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"
SITE_ID = "site-mesh"
CURSO = "primeiros-dolares"
CONTRATOS = Path(__file__).resolve().parents[3] / "contracts"

TEXTO = """# Modulo 1: Comece por aqui
01 Boas-vindas ao curso
02 Instale o programa

# Modulo 2: Seu primeiro modelo | Boss: A Cadeira
03 Blocagem
04 A Cadeira do atelie [boss]

## Parte 2
# Modulo 3: Vender no Roblox
05 A sua loja
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
# O INTERPRETADOR — sem rede, sem banco, sem Django
# ---------------------------------------------------------------------------
def test_o_texto_vira_modulos_com_letra_parte_e_aulas():
    blocos, erros = interpretar(TEXTO)
    assert erros == []
    assert [(b["letra"], b["parte"], b["nome"]) for b in blocos] == [
        ("A", 1, "Modulo 1: Comece por aqui"),
        ("B", 1, "Modulo 2: Seu primeiro modelo"),
        ("C", 2, "Modulo 3: Vender no Roblox"),
    ]
    assert [a["numero"] for a in blocos[0]["aulas"]] == ["01", "02"]
    assert blocos[2]["aulas"] == [
        {"numero": "05", "titulo": "A sua loja", "e_boss": False}
    ]


def test_o_boss_da_aula_e_o_titulo_do_boss_do_modulo_sao_coisas_diferentes():
    """`[boss]` marca a AULA; ` | Boss:` nomeia o Boss do MÓDULO.

    Confundi-los mandaria o nome do Boss para o campo da aula, e o campo do
    bloco ficaria nulo sem ninguém perceber.
    """
    blocos, _ = interpretar(TEXTO)
    assert blocos[1]["boss_titulo"] == "A Cadeira"
    assert blocos[1]["aulas"][1] == {
        "numero": "04",
        "titulo": "A Cadeira do atelie",
        "e_boss": True,
    }
    assert blocos[1]["aulas"][0]["e_boss"] is False


def test_modulo_sem_boss_leva_o_titulo_NULO_e_nao_vazio():
    """Nulo é NÃO MEXER; vazio APAGA o título gravado (contrato)."""
    blocos, _ = interpretar(TEXTO)
    assert blocos[0]["boss_titulo"] is None
    assert blocos[2]["boss_titulo"] is None


def test_o_numero_da_aula_vai_para_maiusculo():
    blocos, erros = interpretar("# Modulo\ne01 Uma aula")
    assert erros == []
    assert blocos[0]["aulas"][0]["numero"] == "E01"


def test_linha_em_branco_nao_atrapalha():
    blocos, erros = interpretar("\n\n# Modulo\n\n01 Uma aula\n\n")
    assert erros == []
    assert len(blocos[0]["aulas"]) == 1


@pytest.mark.parametrize(
    "texto, linha, pedaco",
    [
        ("01 Uma aula solta", 1, "antes do primeiro módulo"),
        ("# Modulo\n01 Uma\n01 Outra", 3, "já foi usado na linha 2"),
        ("# Modulo\n0001 Uma aula", 2, "três letras ou algarismos"),
        ("# Modulo\nIntroducao", 2, "Não reconheci esta linha"),
        ("# Modulo\n01", 2, "está sem nome"),
        ("# Modulo A\n# Modulo B\n01 Uma", 1, "ficou sem nenhuma aula"),
        ("## Parte 9\n# Modulo\n01 Uma", 1, "O livro tem três Partes"),
        ("## Outra coisa\n# Modulo\n01 Uma", 1, "eu só entendo Parte 1"),
        ("#\n01 Uma aula", 1, "abre um módulo sem nome"),
        ("# " + "N" * 121 + "\n01 Uma", 1, "cabem no máximo 120"),
        ("# Modulo\n01 " + "T" * 121, 2, "cabem no máximo 120"),
        ("# Modulo | Boss: " + "B" * 121 + "\n01 Uma", 1, "título do Boss"),
    ],
)
def test_cada_erro_do_texto_traz_a_linha_e_o_que_corrigir(texto, linha, pedaco):
    _, erros = interpretar(texto)
    assert erros, f"o texto {texto!r} devia acusar erro"
    assert erros[0]["linha"] == linha
    assert pedaco in erros[0]["frase"]


def test_os_erros_saem_todos_de_uma_vez_e_em_ordem_de_linha():
    """Um de cada vez faria o mantenedor colar, corrigir e colar de novo."""
    _, erros = interpretar("01 Solta\n# Modulo\n02 Uma\n02 Outra")
    assert [e["linha"] for e in erros] == [1, 4]


def test_mais_de_vinte_e_seis_modulos_nao_cabem_nas_letras():
    texto = "".join(f"# Modulo {i}\n{i:02d} Uma aula\n" for i in range(1, 29))
    _, erros = interpretar(texto)
    assert erros and "de A a Z" in erros[0]["frase"]


# ---------------------------------------------------------------------------
# O CORPO QUE VAI PARA A PORTA
# ---------------------------------------------------------------------------
def _aula_gravada(numero, titulo="", *, banca=None, estado="rascunho"):
    """Uma linha de `listLessons` no formato de `AulaDaListaSchema`."""
    return {
        "numero": numero,
        "ordem": 0,
        "titulo_exibido": titulo,
        "bloco": {"letra": "A", "ordem": 1, "parte": 1, "nome": "", "boss_titulo": ""},
        "estado": estado,
        "versao": 1,
        "publicada_em": None,
        "e_boss": False,
        "banca_nivel": banca,
    }


def test_o_corpo_leva_nome_sempre_e_boss_titulo_nulo_quando_nao_veio():
    blocos, _ = interpretar(TEXTO)
    corpo = corpo_para_gravar(blocos, [])
    primeiro = corpo["blocos"][0]
    assert primeiro["letra"] == "A"
    assert primeiro["parte"] == 1
    assert primeiro["nome"] == "Modulo 1: Comece por aqui"
    assert primeiro["boss_titulo"] is None
    assert corpo["blocos"][1]["boss_titulo"] == "A Cadeira"
    assert primeiro["aulas"][0] == {
        "numero": "01",
        "titulo": "Boas-vindas ao curso",
        "e_boss": False,
        "banca_nivel": None,
    }


def test_a_banca_de_quem_ja_existe_viaja_de_volta_intacta():
    """A estrutura é a FONTE da Banca por contrato: omiti-la zeraria o nível.

    Esta tela não tem campo de Banca, então o único jeito de não apagar o que
    está gravado é devolver o que a leitura trouxe.
    """
    blocos, _ = interpretar(TEXTO)
    corpo = corpo_para_gravar(blocos, [_aula_gravada("03", banca=2)])
    todas = {a["numero"]: a["banca_nivel"] for b in corpo["blocos"] for a in b["aulas"]}
    assert todas["03"] == 2
    assert todas["01"] is None


def test_o_corpo_so_tem_as_chaves_que_o_contrato_aceita():
    """`additionalProperties: false` nos dois esquemas: chave a mais é 422."""
    blocos, _ = interpretar(TEXTO)
    corpo = corpo_para_gravar(blocos, [])
    assert set(corpo) == {"blocos"}
    for bloco in corpo["blocos"]:
        assert set(bloco) == {"letra", "parte", "nome", "boss_titulo", "aulas"}
        for aula in bloco["aulas"]:
            assert set(aula) == {"numero", "titulo", "e_boss", "banca_nivel"}


# ---------------------------------------------------------------------------
# O CASAMENTO — o que a importação faria
# ---------------------------------------------------------------------------
def test_a_previa_separa_criar_de_preencher_de_preservar():
    blocos, _ = interpretar(TEXTO)
    modulos, _ = casar(
        blocos,
        [_aula_gravada("01", "O nome que eu mesmo escrevi"), _aula_gravada("02", "")],
    )
    aulas = {a["numero"]: a for m in modulos for a in m["aulas"]}
    assert aulas["01"]["acao"] == "preservar"
    assert aulas["01"]["titulo_que_fica"] == "O nome que eu mesmo escrevi"
    assert aulas["02"]["acao"] == "preencher"
    assert aulas["02"]["titulo_que_fica"] == "Instale o programa"
    assert aulas["03"]["acao"] == "criar"


def test_espaco_solto_no_titulo_gravado_nao_conta_como_nome_escrito():
    blocos, _ = interpretar(TEXTO)
    modulos, _ = casar(blocos, [_aula_gravada("01", "   ")])
    aulas = {a["numero"]: a for m in modulos for a in m["aulas"]}
    assert aulas["01"]["acao"] == "preencher"


def test_a_previa_diz_quais_aulas_sumiriam():
    blocos, _ = interpretar(TEXTO)
    _, a_apagar = casar(blocos, [_aula_gravada("99", "Aula velha")])
    assert a_apagar == [{"numero": "99", "titulo": "Aula velha", "publicada": False}]


# ---------------------------------------------------------------------------
# AS PORTAS DUBLADAS E A TELA
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
    cliente = Client()
    cliente.defaults["HTTP_COOKIE"] = COOKIE
    return cliente


def _mock_site():
    return respx.get(f"{CATALOGO}/sites/by-host/testserver").mock(
        return_value=httpx.Response(200, json={"id": SITE_ID, "host": "testserver"})
    )


def _mock_aulas(aulas=None, status=200):
    return respx.get(f"{CURSOS}/cursos/{CURSO}/aulas").mock(
        return_value=httpx.Response(status, json=aulas if aulas is not None else [])
    )


def _mock_estrutura(status=200, corpo=None):
    return respx.put(f"{CURSOS}/cursos/{CURSO}/estrutura").mock(
        return_value=httpx.Response(
            status,
            json=(
                corpo
                if corpo is not None
                else {
                    "blocos": [],
                    "blocos_criados": 3,
                    "aulas_criadas": 5,
                    "aulas_preservadas": 0,
                    "aulas_apagadas": 0,
                }
            ),
        )
    )


def _tela(nome="escola_estrutura"):
    return reverse(nome, kwargs={"curso": CURSO})


@respx.mock
def test_a_tela_abre_vazia_e_ensina_o_formato():
    _mock_site()
    leitura = _mock_aulas()
    corpo = _dentro().get(_tela()).content.decode()
    assert "Os módulos e as aulas do curso" in corpo
    assert "# Módulo 1: Comece por aqui" in corpo
    assert "01 Boas-vindas ao curso" in corpo
    # Abrir a tela não pergunta as aulas à sala: ainda não há texto para comparar.
    assert not leitura.called


@respx.mock
def test_prever_nao_chama_a_porta_de_ESCRITA():
    """O botão que existe para olhar antes não pode ser o botão que faz."""
    _mock_site()
    _mock_aulas()
    escrita = _mock_estrutura()
    resposta = _dentro().post(_tela("escola_estrutura_prever"), {"estrutura": TEXTO})
    assert resposta.status_code == 200
    assert not escrita.called
    corpo = resposta.content.decode()
    assert "3 módulo(s) e 5 aula(s)" in corpo
    assert "vai ser criada" in corpo


@respx.mock
def test_prever_mostra_o_nome_que_fica_e_o_que_foi_colado():
    _mock_site()
    _mock_aulas([_aula_gravada("01", "O nome que eu mesmo escrevi")])
    corpo = (
        _dentro()
        .post(_tela("escola_estrutura_prever"), {"estrutura": TEXTO})
        .content.decode()
    )
    assert "O nome que eu mesmo escrevi" in corpo
    assert "o nome que você escreveu" in corpo
    assert "no texto colado você escreveu: Boas-vindas ao curso" in corpo


@respx.mock
def test_prever_avisa_quais_aulas_sumiriam():
    _mock_site()
    _mock_aulas([_aula_gravada("99", "Aula velha")])
    corpo = (
        _dentro()
        .post(_tela("escola_estrutura_prever"), {"estrutura": TEXTO})
        .content.decode()
    )
    assert "vão sumir" in corpo
    assert "Aula velha" in corpo


@respx.mock
@pytest.mark.django_db
def test_importar_manda_o_corpo_do_contrato_e_mostra_as_contagens():
    _mock_site()
    _mock_aulas([_aula_gravada("03", banca=3)])
    escrita = _mock_estrutura()
    resposta = _dentro().post(_tela("escola_estrutura_importar"), {"estrutura": TEXTO})
    assert resposta.status_code == 200
    assert escrita.called

    import json

    enviado = json.loads(escrita.calls.last.request.content)
    assert escrita.calls.last.request.url.params["site_id"] == SITE_ID
    assert [b["letra"] for b in enviado["blocos"]] == ["A", "B", "C"]
    assert enviado["blocos"][0]["boss_titulo"] is None
    assert enviado["blocos"][1]["boss_titulo"] == "A Cadeira"
    banca = {
        a["numero"]: a["banca_nivel"] for b in enviado["blocos"] for a in b["aulas"]
    }
    assert banca["03"] == 3

    corpo = resposta.content.decode()
    assert "A estrutura do curso foi gravada." in corpo
    assert "3 módulo(s) novo(s), 5 aula(s) criada(s)" in corpo


@respx.mock
@pytest.mark.django_db
def test_importar_deixa_rastro_na_auditoria_sem_o_nome_de_nenhuma_aula():
    """A auditoria guarda QUANTOS, nunca a obra (`LICOES.md`, 28/08/2026)."""
    _mock_site()
    _mock_aulas()
    _mock_estrutura()
    _dentro().post(_tela("escola_estrutura_importar"), {"estrutura": TEXTO})
    registro = Registro.objects.get()
    assert registro.acao == Registro.IMPORTAR_ESTRUTURA
    assert registro.alvo == CURSO
    assert registro.desfecho == Registro.OK
    assert "3 módulo(s), 5 aula(s)" in registro.detalhe
    assert "Boas-vindas" not in registro.detalhe
    assert "A Cadeira" not in registro.detalhe


@respx.mock
@pytest.mark.django_db
def test_a_recusa_da_sala_aparece_em_portugues_e_nada_foi_gravado():
    _mock_site()
    _mock_aulas()
    _mock_estrutura(
        422,
        {"detail": "A aula 07 tem entregas de aluno e não pode ser apagada."},
    )
    resposta = _dentro().post(_tela("escola_estrutura_importar"), {"estrutura": TEXTO})
    assert resposta.status_code == 400
    corpo = resposta.content.decode()
    assert "A aula 07 tem entregas de aluno e não pode ser apagada." in corpo
    assert "Nada foi gravado, nem em parte:" in corpo
    assert Registro.objects.get().desfecho == Registro.RECUSADO_PELA_CELULA


@respx.mock
@pytest.mark.django_db
def test_a_sala_calada_na_escrita_vira_nao_sei_se_gravou():
    """Fail-closed na escrita: "não sei" nunca vira "não valeu"."""
    _mock_site()
    _mock_aulas()
    _mock_estrutura(500)
    resposta = _dentro().post(_tela("escola_estrutura_importar"), {"estrutura": TEXTO})
    assert resposta.status_code == 503
    assert "não sei dizer se a estrutura entrou" in resposta.content.decode()
    assert Registro.objects.get().desfecho == Registro.NAO_RESPONDEU


@respx.mock
def test_texto_com_erro_nao_chega_a_perguntar_nada_a_sala():
    _mock_site()
    leitura = _mock_aulas()
    escrita = _mock_estrutura()
    resposta = _dentro().post(
        _tela("escola_estrutura_importar"), {"estrutura": "01 Uma aula solta"}
    )
    assert resposta.status_code == 400
    assert not leitura.called and not escrita.called
    corpo = resposta.content.decode()
    assert "Linha 1:" in corpo
    assert "antes do primeiro módulo" in corpo


@respx.mock
def test_caixa_vazia_diz_o_que_fazer_e_nao_grava():
    _mock_site()
    escrita = _mock_estrutura()
    resposta = _dentro().post(_tela("escola_estrutura_prever"), {"estrutura": "   "})
    assert resposta.status_code == 400
    assert not escrita.called
    assert "Cole a lista dos módulos e das aulas" in resposta.content.decode()


@respx.mock
def test_curso_que_nao_existe_manda_voltar_a_lista():
    _mock_site()
    _mock_aulas(status=404)
    resposta = _dentro().post(_tela("escola_estrutura_prever"), {"estrutura": TEXTO})
    assert resposta.status_code == 404
    assert f"Não existe nenhum curso {CURSO}" in resposta.content.decode()


@respx.mock
def test_catalogo_calado_nao_chuta_um_site():
    respx.get(f"{CATALOGO}/sites/by-host/testserver").mock(
        return_value=httpx.Response(503)
    )
    resposta = _dentro().post(_tela("escola_estrutura_prever"), {"estrutura": TEXTO})
    assert resposta.status_code == 503
    assert "de qual escola é este curso" in resposta.content.decode()


@respx.mock
def test_a_tela_nao_guarda_o_texto_colado_e_o_devolve_na_caixa():
    _mock_site()
    _mock_aulas()
    corpo = (
        _dentro()
        .post(_tela("escola_estrutura_prever"), {"estrutura": TEXTO})
        .content.decode()
    )
    assert "Instale o programa" in corpo


@respx.mock
def test_a_lista_de_cursos_leva_a_esta_tela():
    respx.get(f"{CURSOS}/cursos", params={"site_id": SITE_ID}).mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "slug": CURSO,
                    "nome": "Primeiros Dolares com Roblox",
                    "estado": "rascunho",
                    "progressao": "livre",
                    "produto_id": "produto-1",
                    "total_de_aulas": 0,
                    "aulas_publicadas": 0,
                }
            ],
        )
    )
    respx.get(f"{CATALOGO}/produtos").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": "produto-1",
                    "name": "Primeiros Dolares",
                    "price_cents": 0,
                    "active": True,
                }
            ],
        )
    )
    _mock_site()
    corpo = _dentro().get(reverse("escola_cursos")).content.decode()
    assert _tela() in corpo
    assert "Módulos e aulas" in corpo


# ---------------------------------------------------------------------------
# OS DOIS GUARDAS DO CONTRATO
# ---------------------------------------------------------------------------
def test_a_porta_que_esta_tela_usa_existe_no_contrato_congelado():
    texto = (CONTRATOS / "cursos.openapi.yaml").read_text(encoding="utf-8")
    assert "putCourseStructure" in texto
    assert "/cursos/{curso}/estrutura:" in texto


def test_os_limites_desta_tela_sao_os_do_contrato():
    """`TETO` e `NUMERO` são cópias de valores que moram no contrato.

    Divergir deles faria a tela aceitar o que a porta recusa, e o mantenedor
    veria um 422 sobre a estrutura inteira em vez da linha errada.
    """
    from apps.core.estrutura import NUMERO, TETO

    texto = (CONTRATOS / "cursos.openapi.yaml").read_text(encoding="utf-8")
    trecho = texto[texto.index("    AulaDaEstruturaSchema:") :]
    trecho = trecho[: trecho.index("    EstruturaParaGravarSchema:")]
    assert re.search(r"pattern:\s*\^\[A-Z0-9\]\{1,3\}\$", trecho)
    assert NUMERO.pattern == "^[A-Z0-9]{1,3}$"
    assert f"maxLength: {TETO}" in trecho
