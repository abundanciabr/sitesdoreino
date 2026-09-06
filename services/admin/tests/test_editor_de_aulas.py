"""O editor de encomendas do curso: `/admin/escola/<curso>/parte-N/aulas/`.

A `cursos` é dublada pelo `respx` com respostas NO FORMATO DO CONTRATO
(`contracts/cursos.openapi.yaml`); dois guardas leem o contrato do disco para
que a tela e o contrato não possam divergir em silêncio. O que cada promessa
custa, se cair:

1. **A lista mostra as 34 e diz quantas estão publicadas.** Sem a contagem, o
   mantenedor abre 34 telas para saber o que os alunos já veem.
2. **As peças saem NA ORDEM do contrato**, cada uma com o aviso da sua
   categoria: as duas internas ("o aluno nunca vê") e a vídeo-aula em texto ("o
   aluno vê, mas fora da sequência"). Peça fora de ordem é a aula lida na ordem
   errada pelo aluno; aviso trocado é a professora escrevendo para quem não é.
3. **Salvar manda a encomenda INTEIRA** (as chaves obrigatórias do corpo do
   contrato, nem uma a mais) **e mostra a versão nova.** Corpo pela metade é
   422 em toda gravação; sem o número, a pessoa salva e não sabe se pegou.
4. **O 422 vira frase em português AO LADO do campo, e o rascunho volta
   inteiro.** Um 500 ou uma frase geral perde o texto de uma aula que não existe
   em outro lugar.
5. **Publicar chama `publishLesson` e mostra a data**, no fuso de quem lê.
6. **O travessão conta, lista e NÃO impede salvar** (decisão do mantenedor de
   04/09/2026): a obra se guarda como ele escreveu.
7. **O instrumento lê e grava; nome e cartão só se leem**, e o corpo enviado
   é exatamente o do contrato (mandar `nome_canonico` seria 422).
8. **Fail-OPEN na leitura, fail-CLOSED na escrita.** Sala fora do ar: a lista
   abre com a frase; par recusado: a frase nomeia o par; sem par no ambiente:
   nada vai à rede. Gravar sem resposta nunca vira "salvei".
9. **Esta célula não guarda nada e a porta continua sendo a porta.**
10. **O curso e a Parte moram no endereço** (TAR-211): a lista é agrupada nas
    três Partes e nos blocos do livro, a Parte que não casa com a encomenda
    recusa com o endereço certo, e a tela nunca chama as operações que varrem o
    site inteiro sem saber de curso.
"""

import json
import re
from pathlib import Path

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.auditoria.models import Registro
from apps.core import aulas as editor

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
CATALOGO = "http://catalogo:8000/api/catalogo"
CURSOS = "http://cursos:8000/api/cursos"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"
DONO_ID = "id-opaco-123"
DE_FORA = "estranho@exemplo.com"
SITE_ID = "site-mesh"
CONTRATO = Path(__file__).resolve().parents[3] / "contracts" / "cursos.openapi.yaml"

# As 34 encomendas do esqueleto da `cursos`: E00 a E32 e a bônus.
NUMEROS = [f"E{n:02d}" for n in range(33)] + ["EB"]
TIPOS = [tipo for tipo, _, _ in editor.PECAS]

# O slug do curso de hoje. Ele viaja no ENDEREÇO da tela e no caminho da porta:
# é o par site+slug que resolve o curso, nunca "o primeiro curso do site".
CURSO = "profissional"

# Os 12 blocos do livro, na ordem: letra, parte e as encomendas de cada um. É a
# mesma estrutura que a `cursos` semeia, e é ela que a lista agrupa na tela para
# quem está com o livro aberto ao lado.
BLOCOS = (
    ("A", 1, ("E00", "E01", "E02")),
    ("B", 1, ("E03", "E04", "E05")),
    ("C", 1, ("E06", "E07", "E08")),
    ("D", 1, ("E09", "E10")),
    ("E", 2, ("E11", "E12", "E13", "E14")),
    ("F", 2, ("E15", "E16")),
    ("G", 2, ("E17", "E18")),
    ("H", 2, ("E19", "E20", "E21")),
    ("I", 3, ("E22", "E23", "E24", "E25")),
    ("J", 3, ("E26", "E27")),
    ("K", 3, ("E28", "E29", "E30")),
    ("L", 3, ("E31", "E32", "EB")),
)
BLOCO_DA_AULA = {
    numero: {"letra": letra, "ordem": ordem, "parte": parte}
    for ordem, (letra, parte, numeros) in enumerate(BLOCOS, start=1)
    for numero in numeros
}


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
# O CONTRATO, LIDO DO DISCO
# ---------------------------------------------------------------------------
def _bloco_do_contrato(componente: str) -> str:
    texto = CONTRATO.read_text(encoding="utf-8")
    inicio = texto.index(f"\n    {componente}:\n")
    fim = texto.find("\n    ", inicio + len(componente) + 7)
    while fim != -1 and texto[fim + 5] == " ":
        fim = texto.find("\n    ", fim + 1)
    return texto[inicio : fim if fim != -1 else len(texto)]


def _enum_do_contrato(componente: str) -> list[str]:
    bloco = _bloco_do_contrato(componente)
    bloco = bloco[bloco.index("enum:") : bloco.index("type: string")]
    return re.findall(r"^\s*- (\S+)$", bloco, flags=re.M)


def _obrigatorias_do_contrato(componente: str) -> set[str]:
    bloco = _bloco_do_contrato(componente)
    # O `type: object` que fecha o componente é o que vem DEPOIS de `required:`;
    # os campos `escala` e `descritores` têm um `type: object` próprio, antes.
    inicio = bloco.index("required:")
    bloco = bloco[inicio : bloco.index("type: object", inicio)]
    return set(re.findall(r"^\s*- (\S+)$", bloco, flags=re.M))


# ---------------------------------------------------------------------------
# A PORTA DUBLADA
# ---------------------------------------------------------------------------
def _pessoa(email: str) -> dict:
    return {
        "autenticado": True,
        "id": DONO_ID,
        "nome_exibido": "Fulano",
        "papel": None,
        "email": email,
    }


def _dentro(email: str = DONO) -> Client:
    respx.get(SESSAO).mock(return_value=httpx.Response(200, json=_pessoa(email)))
    cliente = Client()
    cliente.defaults["HTTP_COOKIE"] = COOKIE
    return cliente


def _mock_site():
    return respx.get(f"{CATALOGO}/sites/by-host/testserver").mock(
        return_value=httpx.Response(200, json={"id": SITE_ID, "host": "testserver"})
    )


def _linha(numero: str, *, estado="rascunho", versao=1, publicada_em=None) -> dict:
    ordem = 33 if numero == "EB" else int(numero[1:])
    return {
        "numero": numero,
        "ordem": ordem,
        "titulo_exibido": (
            "Encomenda Bônus" if numero == "EB" else f"Encomenda {numero[1:]}"
        ),
        "bloco": BLOCO_DA_AULA[numero],
        "estado": estado,
        "versao": versao,
        "publicada_em": publicada_em,
        "e_boss": numero == "E07",
        "banca_nivel": 2 if numero == "E07" else None,
    }


def _aula(numero="E07", *, textos=None, pausas=None, **linha) -> dict:
    textos = textos or {}
    return _linha(numero, **linha) | {
        "pedido": "Um capacete para o cliente Gulliver.",
        "cliente": "Gulliver",
        "instrumento": "studs",
        "minimo": "Um capacete fechado.",
        "aceito_quando": ["Tem topologia limpa.", "Tem menos de 2 mil polígonos."],
        "quiz": [
            {"pergunta": "O que é um stud?", "resposta_modelo": "A unidade do Roblox."}
        ],
        "video_url": "https://exemplo.com/v/E07",
        "pecas": [{"tipo": tipo, "texto": textos.get(tipo, "")} for tipo in TIPOS],
        "pausas": pausas
        or [
            {
                "ordem": 1,
                "segundo": 90,
                "tipo": "faca_agora",
                "pede": "Abra o Studio",
                "campos": ["print", "nome"],
            }
        ],
    }


def _instrumento(versao=2) -> dict:
    return {
        "slug": "studs",
        "nome_canonico": "Teste STUDS",
        "cartao": 1,
        "escala": {"tamanho": {"minimo": 1, "maximo": 5}},
        "minimo_exercicio": "3 em tudo",
        "minimo_contrato": "4 em tudo",
        "secao_do_padrao": "§2",
        "descritores": {"tamanho": {"5": "exato", "3": "quase", "1": "fora"}},
        "versao": versao,
    }


def _mock_lista(aulas=None):
    return respx.get(
        f"{CURSOS}/cursos/{CURSO}/aulas", params={"site_id": SITE_ID}
    ).mock(
        return_value=httpx.Response(
            200, json=aulas if aulas is not None else [_linha(n) for n in NUMEROS]
        )
    )


def _mock_aula(aula=None, numero="E07"):
    return respx.get(
        f"{CURSOS}/cursos/{CURSO}/aulas/{numero}", params={"site_id": SITE_ID}
    ).mock(return_value=httpx.Response(200, json=aula or _aula(numero)))


def _mock_instrumentos():
    return respx.get(f"{CURSOS}/instrumentos").mock(
        return_value=httpx.Response(200, json=[_instrumento()])
    )


def _mock_instrumento(instrumento=None):
    return respx.get(f"{CURSOS}/instrumentos/studs").mock(
        return_value=httpx.Response(200, json=instrumento or _instrumento())
    )


def _texto(resposta) -> str:
    return resposta.content.decode()


def _formulario(**troca) -> dict:
    """O formulário do editor preenchido como a professora o mandaria: duas
    perguntas do quiz, uma pausa, TODAS as peças que a tela conhece (a lista sai
    de `editor.PECAS`, então peça nova entra aqui sozinha). As linhas vazias
    ficam vazias."""
    dados = {
        "pedido": "Um capacete para o cliente Gulliver.",
        "cliente": "Gulliver",
        "instrumento": "studs",
        "minimo": "Um capacete fechado.",
        "aceito_quando": "Tem topologia limpa.\r\n\r\nTem menos de 2 mil polígonos.\r\n",
        "video_url": "https://exemplo.com/v/E07",
        "e_boss": "1",
        "banca_nivel": "2",
        "quiz_1_pergunta": "O que é um stud?",
        "quiz_1_resposta_modelo": "A unidade do Roblox.",
        "quiz_2_pergunta": "Quantos studs tem um bloco?",
        "quiz_2_resposta_modelo": "Quatro.",
        "pausa_1_ordem": "1",
        "pausa_1_segundo": "90",
        "pausa_1_tipo": "faca_agora",
        "pausa_1_pede": "Abra o Studio",
        "pausa_1_campos": "print, nome",
    }
    for n in (3, 4, 5):
        dados[f"quiz_{n}_pergunta"] = ""
        dados[f"quiz_{n}_resposta_modelo"] = ""
    for n in (2, 3, 4):
        for campo in ("ordem", "segundo", "tipo", "pede", "campos"):
            dados[f"pausa_{n}_{campo}"] = ""
    for tipo in TIPOS:
        dados[f"peca_{tipo}"] = f"Texto da peça {tipo}.\r\nSegunda linha."
    return dados | troca


def _corpo_esperado() -> dict:
    return {
        "pedido": "Um capacete para o cliente Gulliver.",
        "cliente": "Gulliver",
        "instrumento": "studs",
        "minimo": "Um capacete fechado.",
        "aceito_quando": ["Tem topologia limpa.", "Tem menos de 2 mil polígonos."],
        "quiz": [
            {"pergunta": "O que é um stud?", "resposta_modelo": "A unidade do Roblox."},
            {"pergunta": "Quantos studs tem um bloco?", "resposta_modelo": "Quatro."},
        ],
        "video_url": "https://exemplo.com/v/E07",
        "e_boss": True,
        "banca_nivel": 2,
        "pecas": [
            {"tipo": tipo, "texto": f"Texto da peça {tipo}.\nSegunda linha."}
            for tipo in TIPOS
        ],
        "pausas": [
            {
                "ordem": 1,
                "segundo": 90,
                "tipo": "faca_agora",
                "pede": "Abra o Studio",
                "campos": ["print", "nome"],
            }
        ],
    }


# ---------------------------------------------------------------------------
# 1. A LISTA
# ---------------------------------------------------------------------------
@pytest.mark.django_db
@respx.mock
def test_a_lista_mostra_as_34_encomendas_e_quantas_estao_publicadas():
    _mock_site()
    aulas = [_linha(n) for n in NUMEROS]
    aulas[0] = _linha(
        "E00", estado="publicada", versao=4, publicada_em="2026-09-05T13:30:00+00:00"
    )
    aulas[7] = _linha(
        "E07", estado="publicada", versao=2, publicada_em="2026-09-04T12:00:00+00:00"
    )
    _mock_lista(aulas)
    _mock_instrumentos()

    resposta = _dentro().get(reverse("escola_aulas", kwargs={"curso": CURSO}))
    html = _texto(resposta)

    assert resposta.status_code == 200
    # Todo link de encomenda leva o curso E a parte: é o endereço que diz, a
    # quem o abre, em que ponto do livro ele está.
    assert re.findall(
        r'href="/escola/profissional/parte-(\d)/aulas/(E\d\d|EB)/"', html
    ) == [(str(BLOCO_DA_AULA[n]["parte"]), n) for n in NUMEROS]
    assert "2 de 34" in html
    assert "Encomenda Bônus" in html
    # A data sai no fuso de quem lê (São Paulo), nunca em UTC cru.
    assert "05/09/2026 às 10:30" in html
    assert "2026-09-05T13:30" not in html
    assert "Cartão 1: " in html and "Teste STUDS" in html
    assert 'href="/escola/instrumentos/studs/"' in html


@pytest.mark.django_db
@respx.mock
def test_a_ordem_das_pecas_na_tela_e_a_do_contrato():
    """Na ordem canônica do contrato, com as duas internas avisadas. O guarda lê
    o `TipoDePeca` do arquivo congelado: se o contrato ganhar peça por Rito e
    esta tela não, este teste fica vermelho, e não a aula do aluno.

    POR QUE A COMPARAÇÃO NÃO É MAIS UMA IGUALDADE SIMPLES. No Rito de Contrato,
    o consumidor entra ANTES do contrato: o PR do contrato roda a suíte desta
    célula (a `admin` reivindica `painel/` em `celulas.yml`, e o registro do
    livro de todo PR mora lá), então esta tela precisa já conhecer a peça nova
    quando o contrato chega. Uma igualdade obriga os dois a entrarem no mesmo
    instante, o que nenhuma ordem de merge consegue. As duas afirmações abaixo
    valem nos dois mundos e continuam pegando o caso real:

    - a ordem canônica da tela é a do contrato nas peças que os dois já têm, e é
      isso que impede uma peça de trocar de lugar em silêncio;
    - a tela mostra TUDO que o contrato declara, e é isso que reprova quando o
      contrato ganhou peça e a tela não. Esta é a que o guarda existe para
      fazer.

    O que ela deixa de pegar, de propósito: peça que a tela mostra e o contrato
    ainda não declara. É exatamente o intervalo entre este PR e o do contrato.
    """
    _mock_site()
    _mock_aula()
    _mock_instrumentos()

    html = _texto(
        _dentro().get(reverse("escola_aula", kwargs={"curso": CURSO, "numero": "E07"}))
    )

    na_tela = re.findall(r'name="peca_([a-z_]+)"', html)
    do_contrato = _enum_do_contrato("TipoDePeca")
    # 18: as peças que a tela e o contrato já tinham juntos quando esta prova
    # foi escrita. É até onde a ORDEM está congelada dos dois lados.
    assert na_tela[:18] == do_contrato[:18]
    assert set(do_contrato) - set(na_tela) == set()
    assert html.count("o aluno nunca vê esta peça") == 2
    assert "Ficha do Guia do Mentor" in html and "Roteiro da aula" in html
    assert "E07: Encomenda 07" in html


@pytest.mark.django_db
@respx.mock
def test_a_videoaula_em_texto_tem_campo_proprio_e_aviso_que_nao_e_o_das_internas():
    """A vídeo-aula é a TERCEIRA categoria de peça, e a tela precisa dizer isso.

    As 16 da anatomia o aluno lê em sequência; as 2 internas ele nunca vê; esta
    ele VÊ, só que fora da sequência, por um botão embaixo do capítulo. O aviso
    das internas ("o aluno nunca vê esta peça") diria o contrário da verdade
    aqui, e a professora escreveria a peça achando que é bastidor. Por isso o
    aviso é outro, a caixa é outra, e a contagem do aviso interno segue em 2.
    """
    _mock_site()
    _mock_aula()
    _mock_instrumentos()

    html = _texto(
        _dentro().get(reverse("escola_aula", kwargs={"curso": CURSO, "numero": "E07"}))
    )

    assert 'name="peca_videoaula_em_texto"' in html
    assert "A vídeo-aula, em texto" in html
    assert "O aluno vê esta peça, mas fora da sequência." in html
    assert "não é uma das 16 peças do capítulo" in html
    # O aviso das internas não vazou para ela.
    assert html.count("o aluno nunca vê esta peça") == 2


# ---------------------------------------------------------------------------
# 2. O CURSO E A PARTE NO ENDEREÇO
# ---------------------------------------------------------------------------
@pytest.mark.django_db
@respx.mock
def test_a_lista_agrupa_nas_tres_partes_e_nos_blocos_na_ordem_do_livro():
    """As três Partes como seções, e dentro de cada uma os blocos por letra.

    É assim que a professora acha a encomenda com o livro aberto ao lado da
    tela. Uma lista corrida de 34 linhas obriga a contar de cabeça em que
    Parte cada uma cai, que é justamente o que o livro já responde.
    """
    _mock_site()
    _mock_lista()
    _mock_instrumentos()

    html = _texto(_dentro().get(reverse("escola_aulas", kwargs={"curso": CURSO})))

    esperado = []
    for parte, romano in ((1, "I"), (2, "II"), (3, "III")):
        esperado.append(f"Parte {romano}")
        esperado += [f"Bloco {letra}" for letra, p, _ in BLOCOS if p == parte]
    assert (
        re.findall(r'class="[^"]*(?:parte|bloco)-do-livro">([^<]+)<', html) == esperado
    )


@pytest.mark.django_db
@respx.mock
def test_o_endereco_com_a_parte_pede_a_porta_so_aquela_parte():
    _mock_site()
    _mock_instrumentos()
    da_parte = [n for n in NUMEROS if BLOCO_DA_AULA[n]["parte"] == 2]
    lista = respx.get(
        f"{CURSOS}/cursos/{CURSO}/aulas", params={"site_id": SITE_ID, "parte": "2"}
    ).mock(return_value=httpx.Response(200, json=[_linha(n) for n in da_parte]))

    resposta = _dentro().get(
        reverse("escola_aulas", kwargs={"curso": CURSO, "parte": "2"})
    )
    html = _texto(resposta)

    assert resposta.status_code == 200
    assert lista.calls.last.request.url.params["parte"] == "2"
    assert re.findall(r'class="[^"]*(?:parte|bloco)-do-livro">([^<]+)<', html) == [
        "Parte II",
        "Bloco E",
        "Bloco F",
        "Bloco G",
        "Bloco H",
    ]
    # E o caminho de volta para o curso inteiro continua a um clique.
    assert 'href="/escola/profissional/aulas/"' in html


@pytest.mark.django_db
@respx.mock
def test_a_parte_que_nao_casa_com_a_encomenda_recusa_e_diz_onde_ela_esta():
    """Endereço que aponta certo para a encomenda errada é pior que quebrado.

    A porta recusa com 404; a tela pergunta de novo SEM a parte para saber em
    qual a encomenda está de verdade (o `bloco.parte` do contrato, nunca o
    texto cru da recusa), e devolve o endereço certo pronto para clicar.
    """
    _mock_site()
    _mock_instrumentos()
    errada = respx.get(
        f"{CURSOS}/cursos/{CURSO}/aulas/E07",
        params={"site_id": SITE_ID, "parte": "2"},
    ).mock(
        return_value=httpx.Response(
            404,
            json={
                "detail": "a aula E07 não está na parte 2 do curso 'profissional': "
                "ela está na parte 1. Troque a parte do endereço para 1."
            },
        )
    )
    certa = _mock_aula()

    resposta = _dentro().get(
        reverse("escola_aula", kwargs={"curso": CURSO, "parte": "2", "numero": "E07"})
    )
    html = _texto(resposta)

    assert resposta.status_code == 404
    assert errada.call_count == 1 and certa.call_count == 1
    assert "Essa encomenda não está na Parte II" in html
    assert "Ela está na <b>Parte I</b>" in html
    assert 'href="/escola/profissional/parte-1/aulas/E07/"' in html
    # O recado cru da porta é para o robô, não para quem lê a tela.
    assert "não está na parte 2 do curso" not in html


@pytest.mark.django_db
@respx.mock
def test_o_editor_a_gravacao_e_a_publicacao_levam_o_curso_e_a_parte_a_porta():
    _mock_site()
    _mock_instrumentos()
    caminho = f"{CURSOS}/cursos/{CURSO}/aulas/E07"
    leitura = respx.get(caminho).mock(return_value=httpx.Response(200, json=_aula()))
    gravacao = respx.put(caminho).mock(
        return_value=httpx.Response(200, json=_aula(versao=9))
    )
    publicacao = respx.post(f"{caminho}/publicar").mock(
        return_value=httpx.Response(200, json=_linha("E07", estado="publicada"))
    )

    cliente = _dentro()
    endereco = {"curso": CURSO, "parte": "1", "numero": "E07"}
    cliente.get(reverse("escola_aula", kwargs=endereco))
    salvou = cliente.post(reverse("escola_aula_salvar", kwargs=endereco), _formulario())
    publicou = cliente.post(
        reverse("escola_aula_publicar", kwargs=endereco), {"confirmo": "1"}
    )

    for rota in (leitura, gravacao, publicacao):
        assert rota.call_count >= 1
        params = rota.calls.last.request.url.params
        assert (params["site_id"], params["parte"]) == (SITE_ID, "1")
    # E o POST-redirect-GET volta para o endereço com a parte, nunca sem ela.
    assert salvou["Location"].startswith("/escola/profissional/parte-1/aulas/E07/")
    assert publicou["Location"].startswith("/escola/profissional/parte-1/aulas/E07/")


@pytest.mark.django_db
@respx.mock
def test_a_tela_nunca_chama_as_operacoes_que_nao_sabem_de_curso():
    """`listSiteLessons` e as três irmãs varrem o site inteiro.

    Com dois cursos no mesmo site elas devolvem as aulas dos dois misturadas,
    e nenhuma tela consegue dizer de qual curso cada linha é. Este guarda deixa
    as quatro armadas e prova que nenhuma foi tocada.
    """
    _mock_site()
    _mock_instrumentos()
    sem_curso = [
        respx.get(f"{CURSOS}/aulas").mock(return_value=httpx.Response(200, json=[])),
        respx.get(f"{CURSOS}/aulas/E07").mock(
            return_value=httpx.Response(200, json=_aula())
        ),
        respx.put(f"{CURSOS}/aulas/E07").mock(
            return_value=httpx.Response(200, json=_aula())
        ),
        respx.post(f"{CURSOS}/aulas/E07/publicar").mock(
            return_value=httpx.Response(200, json=_linha("E07"))
        ),
    ]
    _mock_lista()
    _mock_aula()
    respx.put(f"{CURSOS}/cursos/{CURSO}/aulas/E07").mock(
        return_value=httpx.Response(200, json=_aula())
    )
    respx.post(f"{CURSOS}/cursos/{CURSO}/aulas/E07/publicar").mock(
        return_value=httpx.Response(200, json=_linha("E07", estado="publicada"))
    )

    cliente = _dentro()
    cliente.get(reverse("escola_aulas", kwargs={"curso": CURSO}))
    cliente.get(reverse("escola_aula", kwargs={"curso": CURSO, "numero": "E07"}))
    cliente.post(
        reverse("escola_aula_salvar", kwargs={"curso": CURSO, "numero": "E07"}),
        _formulario(),
    )
    cliente.post(
        reverse("escola_aula_publicar", kwargs={"curso": CURSO, "numero": "E07"}),
        {"confirmo": "1"},
    )

    assert [rota.call_count for rota in sem_curso] == [0, 0, 0, 0]


@pytest.mark.django_db
@respx.mock
def test_o_curso_que_nao_existe_naquele_site_e_404_com_a_frase():
    _mock_site()
    respx.get(f"{CURSOS}/cursos/oficina/aulas", params={"site_id": SITE_ID}).mock(
        return_value=httpx.Response(
            404, json={"detail": "o curso 'oficina' não existe no site 'site-mesh'"}
        )
    )

    resposta = _dentro().get(reverse("escola_aulas", kwargs={"curso": "oficina"}))
    html = _texto(resposta)

    assert resposta.status_code == 404
    assert "Não existe nenhum curso <b>oficina</b> nesta escola." in html
    assert "site-mesh" not in html


@pytest.mark.django_db
@respx.mock
def test_a_parte_sem_encomenda_nenhuma_diz_isso_em_vez_de_tela_vazia():
    _mock_site()
    _mock_instrumentos()
    respx.get(
        f"{CURSOS}/cursos/{CURSO}/aulas", params={"site_id": SITE_ID, "parte": "3"}
    ).mock(return_value=httpx.Response(200, json=[]))

    resposta = _dentro().get(
        reverse("escola_aulas", kwargs={"curso": CURSO, "parte": "3"})
    )
    html = _texto(resposta)

    assert resposta.status_code == 200
    assert "A Parte III deste curso ainda não tem nenhuma encomenda." in html
    assert 'href="/escola/profissional/aulas/"' in html


@pytest.mark.django_db
@respx.mock
def test_a_encomenda_fora_das_tres_partes_e_avisada_e_nao_vira_curso_vazio():
    """Parte fora do vocabulário do contrato não cabe em seção nenhuma.

    A encomenda some das seções, e a tela precisa dizer isso em voz alta. O
    que ela NÃO pode dizer é que o curso está vazio: ele tem encomenda, e
    quem lê iria procurar do lado errado.
    """
    _mock_site()
    _mock_instrumentos()
    torta = _linha("E07")
    torta["bloco"] = {"letra": "Z", "ordem": 99, "parte": 9}
    _mock_lista([torta])

    resposta = _dentro().get(reverse("escola_aulas", kwargs={"curso": CURSO}))
    html = _texto(resposta)

    assert resposta.status_code == 200
    assert "1 encomenda(s) não estão em nenhuma das três" in html
    assert "Este curso ainda não tem nenhuma encomenda." not in html


# ---------------------------------------------------------------------------
# 3. SALVAR
# ---------------------------------------------------------------------------
@pytest.mark.django_db
@respx.mock
def test_salvar_manda_a_encomenda_inteira_e_mostra_a_versao_nova():
    _mock_site()
    _mock_instrumentos()
    # Salvar não lê a aula antes de gravar: o corpo é o formulário. A leitura
    # acontece só na tela que vem depois, e ela já devolve a versão 8.
    salva = _aula(versao=8)
    _mock_aula(salva)
    gravacao = respx.put(
        f"{CURSOS}/cursos/{CURSO}/aulas/E07", params={"site_id": SITE_ID}
    ).mock(return_value=httpx.Response(200, json=salva))

    cliente = _dentro()
    resposta = cliente.post(
        reverse("escola_aula_salvar", kwargs={"curso": CURSO, "numero": "E07"}),
        _formulario(),
    )

    assert resposta.status_code == 302
    assert gravacao.call_count == 1
    chamada = gravacao.calls.last.request
    assert chamada.headers["Authorization"] == "Bearer token-do-par-admin-cursos"
    corpo = json.loads(chamada.content)
    assert set(corpo) == _obrigatorias_do_contrato("AulaParaGravarSchema")
    assert corpo == _corpo_esperado()

    html = _texto(cliente.get(resposta["Location"]))
    assert "Encomenda salva, e ela ficou na versão 8." in html
    assert "continua em rascunho" in html
    linha = Registro.objects.get()
    assert (linha.acao, linha.alvo, linha.desfecho) == (
        Registro.EDITAR_AULA,
        "E07",
        Registro.OK,
    )
    assert linha.detalhe == "versao 8; 0 frase(s) com travessao"


@pytest.mark.django_db
@respx.mock
def test_a_recusa_da_porta_vira_frase_ao_lado_do_campo_e_devolve_o_rascunho():
    """Os três formatos de erro que a `cursos` emite: o vocabulário fechado do
    pydantic (traduzido), o texto livre dela (verbatim) e o teto de tamanho
    (com o número). Cada um pendurado no campo certo, e o texto de volta."""
    _mock_site()
    _mock_aula()
    _mock_instrumentos()
    respx.put(f"{CURSOS}/cursos/{CURSO}/aulas/E07", params={"site_id": SITE_ID}).mock(
        return_value=httpx.Response(
            422,
            json={
                "detail": [
                    {
                        "type": "int_parsing",
                        "loc": ["body", "payload", "pausas", 0, "segundo"],
                        "msg": "Input should be a valid integer",
                    },
                    {
                        "type": "value_error",
                        "loc": ["body", "payload", "instrumento"],
                        "msg": "Value error, o instrumento 'x' não existe; os slugs são: studs",
                    },
                    {
                        "type": "string_too_long",
                        "loc": ["body", "payload", "cliente"],
                        "msg": "String should have at most 120 characters",
                        "ctx": {"max_length": 120},
                    },
                ]
            },
        )
    )

    resposta = _dentro().post(
        reverse("escola_aula_salvar", kwargs={"curso": CURSO, "numero": "E07"}),
        _formulario(
            pausa_1_segundo="um minuto e meio",
            instrumento="x",
            peca_pedido="Este texto não pode se perder.",
        ),
    )
    html = _texto(resposta)

    assert resposta.status_code == 422
    assert "Pausa da linha 1: o segundo precisa ser um número inteiro." in html
    assert (
        "O instrumento: o instrumento &#x27;x&#x27; não existe; os slugs são: studs."
        in html
    )
    assert "O cliente passa do tamanho que a sala de aula aceita (120 letras)." in html
    assert "Nada foi gravado" in html
    assert "Este texto não pode se perder." in html
    assert 'value="um minuto e meio"' in html
    assert "Input should be" not in html and "422" not in html
    linha = Registro.objects.get()
    assert linha.desfecho == Registro.RECUSADO_PELA_CELULA
    # A auditoria guarda QUAIS campos, nunca o texto da aula.
    assert linha.detalhe == "recusou: instrumento, cliente, pausas"
    assert "Gulliver" not in linha.detalhe


@pytest.mark.django_db
@respx.mock
def test_salvar_com_a_sala_fora_do_ar_devolve_o_rascunho_e_nao_diz_que_salvou():
    """Fail-CLOSED na escrita: "não sei se gravou" é a verdade, e o texto fica
    na tela para tentar de novo, com as listas fechadas inteiras."""
    _mock_site()
    respx.get(f"{CURSOS}/cursos/{CURSO}/aulas/E07", params={"site_id": SITE_ID}).mock(
        side_effect=httpx.ConnectError("caiu")
    )
    respx.get(f"{CURSOS}/instrumentos").mock(side_effect=httpx.ConnectError("caiu"))
    respx.put(f"{CURSOS}/cursos/{CURSO}/aulas/E07", params={"site_id": SITE_ID}).mock(
        side_effect=httpx.ConnectError("caiu")
    )

    resposta = _dentro().post(
        reverse("escola_aula_salvar", kwargs={"curso": CURSO, "numero": "E07"}),
        _formulario(peca_pedido="Este texto não pode se perder."),
    )
    html = _texto(resposta)

    assert resposta.status_code == 503
    assert "Não sei se a encomenda foi gravada" in html
    assert "Este texto não pode se perder." in html
    assert '<option value="faca_agora" selected>Faça agora</option>' in html
    assert "Encomenda salva" not in html
    assert Registro.objects.get().desfecho == Registro.NAO_RESPONDEU


# ---------------------------------------------------------------------------
# 4. PUBLICAR
# ---------------------------------------------------------------------------
@pytest.mark.django_db
@respx.mock
def test_publicar_chama_a_porta_e_mostra_a_data():
    _mock_site()
    _mock_instrumentos()
    publicada = _aula(
        estado="publicada", versao=3, publicada_em="2026-09-05T13:30:00+00:00"
    )
    # Publicar não lê a aula antes; a tela que vem depois já a lê publicada.
    _mock_aula(publicada)
    publicacao = respx.post(
        f"{CURSOS}/cursos/{CURSO}/aulas/E07/publicar", params={"site_id": SITE_ID}
    ).mock(
        return_value=httpx.Response(
            200, json=_linha("E07", estado="publicada", versao=3)
        )
    )

    cliente = _dentro()
    resposta = cliente.post(
        reverse("escola_aula_publicar", kwargs={"curso": CURSO, "numero": "E07"}),
        {"confirmo": "1"},
    )

    assert resposta.status_code == 302
    assert publicacao.call_count == 1
    html = _texto(cliente.get(resposta["Location"]))
    assert "Encomenda publicada." in html
    assert "Publicada em <b>05/09/2026 às 10:30</b>" in html
    assert "não há o que publicar de novo" in html
    linha = Registro.objects.get()
    assert (linha.acao, linha.desfecho) == (Registro.PUBLICAR_AULA, Registro.OK)


@pytest.mark.django_db
@respx.mock
def test_publicar_sem_a_caixa_marcada_nao_chama_a_porta():
    _mock_site()
    _mock_aula()
    _mock_instrumentos()
    publicacao = respx.post(f"{CURSOS}/cursos/{CURSO}/aulas/E07/publicar").mock(
        return_value=httpx.Response(200, json=_linha("E07", estado="publicada"))
    )

    resposta = _dentro().post(
        reverse("escola_aula_publicar", kwargs={"curso": CURSO, "numero": "E07"}), {}
    )

    assert resposta.status_code == 400
    assert publicacao.call_count == 0
    assert "marque a caixa de confirmação" in _texto(resposta)
    assert Registro.objects.count() == 0


# ---------------------------------------------------------------------------
# 5. O TRAVESSÃO
# ---------------------------------------------------------------------------
@pytest.mark.django_db
@respx.mock
def test_o_travessao_conta_e_lista_mas_nao_impede_salvar():
    _mock_site()
    _mock_instrumentos()
    com_riscas = {
        "pedido": "O cliente quer um capacete — fechado.",
        "recall": "Lembre da aula passada – a dos studs.",
    }
    respx.get(f"{CURSOS}/cursos/{CURSO}/aulas/E07", params={"site_id": SITE_ID}).mock(
        return_value=httpx.Response(200, json=_aula(textos=com_riscas, versao=2))
    )
    gravacao = respx.put(
        f"{CURSOS}/cursos/{CURSO}/aulas/E07", params={"site_id": SITE_ID}
    ).mock(return_value=httpx.Response(200, json=_aula(textos=com_riscas, versao=2)))

    cliente = _dentro()
    resposta = cliente.post(
        reverse("escola_aula_salvar", kwargs={"curso": CURSO, "numero": "E07"}),
        _formulario(peca_pedido=com_riscas["pedido"], peca_recall=com_riscas["recall"]),
    )

    assert resposta.status_code == 302
    assert gravacao.call_count == 1
    assert Registro.objects.get().detalhe == "versao 2; 2 frase(s) com travessao"

    html = _texto(cliente.get(resposta["Location"]))
    assert "Encomenda salva" in html
    assert "2 frases com travessão." in html
    assert "Guardei do jeito que você escreveu." in html
    assert "peça &quot;O pedido&quot;, linha 1" in html
    assert "peça &quot;Recall&quot;, linha 1" in html
    assert "travessão (—)" in html and "meia-risca (–)" in html


# ---------------------------------------------------------------------------
# 6. O INSTRUMENTO
# ---------------------------------------------------------------------------
@pytest.mark.django_db
@respx.mock
def test_instrumento_le_e_grava_e_o_nome_e_o_cartao_so_se_leem():
    respx.get(f"{CURSOS}/instrumentos/studs").mock(
        side_effect=[
            httpx.Response(200, json=_instrumento(versao=2)),
            httpx.Response(200, json=_instrumento(versao=3)),
        ]
    )
    gravacao = respx.put(f"{CURSOS}/instrumentos/studs").mock(
        return_value=httpx.Response(200, json=_instrumento(versao=3))
    )

    cliente = _dentro()
    html = _texto(cliente.get(reverse("escola_instrumento", args=["studs"])))
    assert "<h1>Cartão 1: Teste STUDS</h1>" in html
    assert 'name="nome_canonico"' not in html and 'name="cartao"' not in html
    assert "&quot;tamanho&quot;" in html

    resposta = cliente.post(
        reverse("escola_instrumento_salvar", args=["studs"]),
        {
            "escala": '{"tamanho": {"minimo": 1, "maximo": 5}}',
            "minimo_exercicio": "3 em tudo",
            "minimo_contrato": "4 em tudo",
            "secao_do_padrao": "§2",
            "descritores": '{"tamanho": {"5": "exato"}}',
        },
    )

    assert resposta.status_code == 302
    corpo = json.loads(gravacao.calls.last.request.content)
    assert set(corpo) == _obrigatorias_do_contrato("InstrumentoParaGravarSchema")
    assert corpo["escala"] == {"tamanho": {"minimo": 1, "maximo": 5}}
    assert "Instrumento salvo, e ele ficou na versão 3." in _texto(
        cliente.get(resposta["Location"])
    )
    linha = Registro.objects.get()
    assert (linha.acao, linha.alvo, linha.desfecho) == (
        Registro.EDITAR_INSTRUMENTO,
        "studs",
        Registro.OK,
    )


@pytest.mark.django_db
@respx.mock
def test_instrumento_com_json_torto_nao_vai_para_a_porta():
    _mock_instrumento()
    gravacao = respx.put(f"{CURSOS}/instrumentos/studs").mock(
        return_value=httpx.Response(200, json=_instrumento(versao=3))
    )

    resposta = _dentro().post(
        reverse("escola_instrumento_salvar", args=["studs"]),
        {
            "escala": "{oops",
            "minimo_exercicio": "3",
            "minimo_contrato": "4",
            "secao_do_padrao": "§2",
            "descritores": "",
        },
    )
    html = _texto(resposta)

    assert resposta.status_code == 422
    assert gravacao.call_count == 0
    assert "A escala não é um JSON válido" in html
    assert (
        "Os descritores não pode ficar vazio; para deixar sem nada, escreva {}." in html
    )
    assert "Não mandei nada para a sala de aula" in html
    assert 'value="3"' in html


@pytest.mark.django_db
@respx.mock
def test_a_volta_do_instrumento_leva_a_lista_ate_quando_a_tela_e_um_erro():
    """O link de voltar é o de cima da tela, e vale nas TRÊS caras dela.

    O instrumento não é de curso nenhum (o contrato não o escopa), então a
    volta é para a lista do curso por onde se entra. Nas duas telas de erro
    esse link fica fora de qualquer condição do gabarito: se o endereço não
    chegar, ele vira `href=""` e recarrega a própria tela do erro.
    """
    respx.get(f"{CURSOS}/instrumentos/studs").mock(
        side_effect=[
            httpx.Response(404, json={"detail": "não existe"}),
            httpx.ConnectError("caiu"),
        ]
    )

    cliente = _dentro()
    nao_existe = cliente.get(reverse("escola_instrumento", args=["studs"]))
    caiu = cliente.get(reverse("escola_instrumento", args=["studs"]))

    assert (nao_existe.status_code, caiu.status_code) == (404, 503)
    for resposta in (nao_existe, caiu):
        assert 'href="/escola/profissional/aulas/"' in _texto(resposta)


# ---------------------------------------------------------------------------
# 7. A SALA DE AULA FORA DO AR, EM TRÊS CARAS
# ---------------------------------------------------------------------------
@pytest.mark.django_db
@respx.mock
def test_com_a_sala_de_aula_fora_do_ar_a_lista_abre_com_a_frase():
    _mock_site()
    respx.get(f"{CURSOS}/cursos/{CURSO}/aulas").mock(
        side_effect=httpx.ConnectError("caiu")
    )

    resposta = _dentro().get(reverse("escola_aulas", kwargs={"curso": CURSO}))
    html = _texto(resposta)

    assert resposta.status_code == 503
    assert "A sala de aula não respondeu." in html
    assert "Nada do que está guardado mudou" in html
    assert "Esta escola ainda não tem nenhuma encomenda" not in html


@pytest.mark.django_db
@respx.mock
def test_sem_token_aceito_a_tela_diz_que_a_sala_recusou_a_admin():
    _mock_site()
    respx.get(f"{CURSOS}/cursos/{CURSO}/aulas").mock(
        return_value=httpx.Response(401, json={"detail": "Unauthorized"})
    )

    resposta = _dentro().get(reverse("escola_aulas", kwargs={"curso": CURSO}))
    html = _texto(resposta)

    assert resposta.status_code == 503
    assert "A sala de aula recusou a admin: confira o par." in html
    assert "Unauthorized" not in html


@pytest.mark.django_db
@respx.mock
def test_sem_o_par_no_ambiente_a_tela_diz_o_que_falta_sem_ir_a_rede(monkeypatch):
    monkeypatch.delenv("CURSOS_API_TOKEN")
    _mock_site()
    porta = respx.get(f"{CURSOS}/cursos/{CURSO}/aulas").mock(
        return_value=httpx.Response(200, json=[])
    )

    resposta = _dentro().get(reverse("escola_aulas", kwargs={"curso": CURSO}))
    html = _texto(resposta)

    assert resposta.status_code == 503
    assert "Ainda não consigo falar com a sala de aula." in html
    assert "CURSOS_API_URL e CURSOS_API_TOKEN" in html
    assert porta.call_count == 0


@pytest.mark.django_db
@respx.mock
def test_a_encomenda_que_nao_existe_e_404_e_nao_500():
    _mock_site()
    respx.get(f"{CURSOS}/cursos/{CURSO}/aulas/E99", params={"site_id": SITE_ID}).mock(
        return_value=httpx.Response(404, json={"detail": "a aula E99 não existe"})
    )

    resposta = _dentro().get(
        reverse("escola_aula", kwargs={"curso": CURSO, "numero": "E99"})
    )

    assert resposta.status_code == 404
    assert "Essa encomenda não existe" in _texto(resposta)


# ---------------------------------------------------------------------------
# 8. A PORTA CONTINUA SENDO A PORTA
# ---------------------------------------------------------------------------
@pytest.mark.django_db
@respx.mock
def test_quem_nao_esta_na_lista_nao_ve_o_editor():
    _mock_site()
    porta = _mock_lista()

    resposta = _dentro(DE_FORA).get(reverse("escola_aulas", kwargs={"curso": CURSO}))

    assert resposta.status_code == 404
    assert porta.call_count == 0
