"""A tela que recebe um capítulo inteiro: `/admin/escola/<curso>/aulas/<n>/capitulo/`.

NENHUM TRECHO DO CAPITULO DELE ENTRA AQUI. Os capítulos do curso são obra não
lançada do mantenedor e este repositório é público (`armadilhas/331`): o que
este arquivo usa é um capítulo de MENTIRA, sobre uma padaria, escrito para o
teste. O que ele copia do capítulo de verdade é só a FORMA, e são sete formas,
todas medidas no capítulo que ele mandou em 06/09/2026:

1. **Títulos em maiúsculas** (`## EU FACO`, `## NOS FAZEMOS`, `## VOCE FAZ`).
2. **Cauda depois do travessão** (`## Drill D07 — Da farinha ao forno`), que
   precisa ser cortada antes de comparar o nome.
3. **Os dois apelidos**: a Regra do Padrão, que vem com quatro palavras no
   meio do nome, e a Crítica de atelier, que ele escreve sem o circunflexo.
4. **A 16ª peça em três títulos separados e não seguidos**, com o Marco de
   carreira e o Boss entre eles.
5. **`###` dentro do "Eu faço"**, que é a armadilha central desta tela:
   quebrar em `###` picaria a maior peça do capítulo em vários pedaços.
6. **A linha `**Aceito quando:**`**, com os critérios separados por `·`.
7. **O Quiz numerado no Checkpoint** e as respostas lá embaixo, na peça 16.

A `cursos` é dublada pelo `respx` com respostas no formato do contrato
congelado. O que cada promessa custa, se cair:

1. **As 16 peças são reconhecidas pelo NOME, e só os `##` são peça.** Sem isso
   ele volta a encher 16 caixas a mão, 34 vezes.
2. **Peça que já tem texto NUNCA é sobrescrita**, e a prévia diz que
   preservou. É a promessa mais cara do arquivo.
3. **Peça que não casa NÃO é adivinhada**: vira aviso com o trecho à vista. É
   o único jeito de não perder texto dele em silêncio.
4. **O Guia de Produção não é importado.** Ele é a instrução de escrita dos
   outros capítulos, e entraria numa peça como se fosse conteúdo do curso.
5. **PREVER não grava nada** e **IMPORTAR grava pela porta de máquina**.
6. **Capítulo de outra encomenda é RECUSADO na gravação.** São 34 capítulos
   parecidos, e esse é o pior acidente possível nesta tela.
7. **A tela não guarda o capítulo** em lugar nenhum desta célula.
"""

import re

import httpx
import pytest
import respx
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from apps.core import capitulo as tela
from apps.core.aulas import PECAS

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
CATALOGO = "http://catalogo:8000/api/catalogo"
CURSOS = "http://cursos:8000/api/cursos"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"
SITE_ID = "site-mesh"
CURSO = "profissional"
AQUI = "E03"
OUTRA = "E04"

TIPOS = [tipo for tipo, _, _ in PECAS]

# ---------------------------------------------------------------------------
# O CAPITULO DE MENTIRA — a forma do de verdade, a padaria inventada
# ---------------------------------------------------------------------------
CAPITULO = """# Encomenda 03 — "Me entrega o pão já assado."

### Da massa ao forno: pesar, sovar, modelar, assar, embalar

[ABERTURA — página dupla: a fornada inventada em cima da tábua. Sem texto.]

## O pedido

A Padeira quer os pães prontos para a vitrine de sábado.

## O que está em jogo

Pão que murcha na vitrine não vende, e a vitrine é o que o cliente vê primeiro.

## O que você vai conseguir fazer

- Sovar até o ponto de véu.
- Assar sem deixar a base branca.

## Recall de 2 minutos

1. O que o fermento come?
2. Por que a massa descansa?

## Par de comparação

[FIGURA 3.1 — o pão bom e o pão murcho lado a lado. Legenda: "Mesma farinha."]

## Erro produtivo (antes da aula)

Asse sem pré-aquecer o forno e olhe a base do pão.

## EU FACO

Na minha primeira fornada eu queimei doze pães de uma vez só.

### 3.1 Pesar: a balança antes de tudo

Pese tudo em gramas, inclusive a água.

### 3.2 Sovar: o ponto de véu

Estique um pedaço da massa contra a luz e olhe se ela rasga.

### Solução do erro produtivo

A base branca era o forno frio, e não a farinha.

## NOS FAZEMOS — a fornada de sábado, da massa à vitrine

1. Pese a farinha. Você deve ver: o visor da balança parado.
2. Sove por dez minutos. Você deve ver: a massa lisa e sem grumos.

## VOCE FAZ — a encomenda da Padeira

Sem passo a passo. Entregue até sexta.

1. Três pães, cada um com a própria etiqueta.
2. Uma foto da vitrine montada, de frente.

**Aceito quando:** massa no ponto de véu · base dourada · etiqueta em cada pão · foto da vitrine.

## Drill D07 — Da farinha ao forno em 20 minutos, sem pressa

Cronômetro. Pese, sove, modele, asse. Meta da semana: abaixo de 20 minutos.

## Erros clássicos

1. **Forno frio.** Sintoma: base branca. Regra: pré-aqueça sempre, sem exceção.
2. **Sal junto do fermento.** Sintoma: massa que não cresce. Regra: sal por último.

## Regra que entra no Padrão da Padaria — §Fornada

Toda fornada sai com etiqueta, data e peso. Sem isso não é fornada, é pão solto.

## Crítica de atelier

Troque pães com um colega. Cada um prova o do outro e escreve três forças e uma
mudança, por escrito.

## Checkpoint MASSA — a primeira nota completa

- **Miolo** — o alvéolo abriu?
- **Assadura** — a base está dourada?

Mínimo para seguir: 8 de 10.

**Quiz** (respostas no fim)

1. O que o fermento come dentro da massa?
2. Por que a base fica branca no forno frio?
3. Quando usar farinha de força?

Confira as respostas só depois de responder as três de cabeça.

## Página do portfólio — Página 3

Título: "A fornada de sábado". Uma foto da vitrine e três linhas: peso, tempo
de forno, e onde a fornada foi vendida.

## Dicionário da Encomenda 03

- *sovar* — trabalhar a massa até ela ficar lisa
- *ponto de véu* — quando a massa estica sem rasgar

## Marco de carreira #7 — Primeira fornada vendida

Validação da Padeira: a vitrine esvaziou antes do meio-dia.

## Boss B — "A vitrine de sábado"

Três pães na vitrine, com etiqueta, provados pela banca da Padeira.

## Cartão de 1 página — Encomenda 03

Pesar · sovar · descansar · modelar · assar · embalar · etiquetar.

## Respostas

**Recall.** (1) O açúcar que a farinha solta. (2) Para o glúten relaxar.

**Quiz.** (1) O açúcar que a farinha solta. (2) Porque a base não recebe choque
de calor. (3) Quando a massa leva muita água.

---

## GUIA DE PRODUÇÃO — como todos os capítulos seguem este modelo

- **Ordem fixa das peças:** as 16 da Anatomia. Nunca pular, nunca trocar.
- **Voz:** "você" para o leitor, sempre.
"""

#: O mesmo capítulo com um título que não é peça nenhuma. Ele existe para
#: provar que a tela AVISA e não adivinha: se um dia ela chutar a peça mais
#: parecida, este teste cai.
COM_TITULO_ESTRANHO = CAPITULO.replace(
    "## Erros clássicos",
    "## Caderno de anotações da Padeira\n\nO que eu anotei na margem.\n\n"
    "## Erros clássicos",
)


# ---------------------------------------------------------------------------
# A PORTA DUBLADA
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _ambiente(monkeypatch, settings):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin-identidade")
    monkeypatch.setenv("CATALOGO_API_URL", CATALOGO)
    monkeypatch.setenv("TOKEN_CATALOGO", "token-do-par-admin-catalogo")
    monkeypatch.setenv("CURSOS_API_URL", CURSOS)
    monkeypatch.setenv("CURSOS_API_TOKEN", "token-do-par-admin-cursos")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


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


def _aula(numero: str, *, textos=None, aceito=None, quiz=None) -> dict:
    textos = textos or {}
    return {
        "numero": numero,
        "ordem": int(numero[1:]),
        "titulo_exibido": f"Encomenda {numero[1:]}",
        "bloco": {"letra": "B", "ordem": 2, "parte": 1},
        "estado": "rascunho",
        "versao": 1,
        "publicada_em": None,
        "e_boss": False,
        "banca_nivel": None,
        "pedido": "",
        "cliente": "A Padeira",
        "instrumento": "studs",
        "minimo": "Um mínimo inventado.",
        "aceito_quando": aceito or [],
        "quiz": quiz or [],
        "video_url": "",
        "pecas": [{"tipo": t, "texto": textos.get(t, "")} for t in TIPOS],
        "pausas": [],
    }


def _porta(aula: dict, *, numero=AQUI, gravar=None):
    """A `cursos` dublada: a encomenda e a gravação dela."""
    respx.get(f"{CURSOS}/cursos/{CURSO}/aulas/{numero}").mock(
        return_value=httpx.Response(200, json=aula)
    )
    return respx.put(url__regex=rf"{re.escape(CURSOS)}/cursos/{CURSO}/aulas/\w+").mock(
        side_effect=gravar or (lambda pedido: httpx.Response(200, json={"versao": 2}))
    )


def _url(nome: str, numero: str = AQUI) -> str:
    return reverse(nome, kwargs={"curso": CURSO, "numero": numero})


# ---------------------------------------------------------------------------
# 1. O INTERPRETADOR — as sete formas do capítulo de verdade
# ---------------------------------------------------------------------------
def test_as_dezesseis_pecas_sao_reconhecidas_pelo_nome_e_nada_fica_de_fora():
    lido = tela.interpretar(CAPITULO)

    assert len(lido["pecas"]) == 16
    assert set(lido["pecas"]) == set(tela.PECAS_NUMERADAS)
    # A promessa que mais importa: nada foi jogado no balaio do "não coube".
    assert lido["nao_reconhecidos"] == []


def test_o_importador_de_capitulo_nunca_escreve_a_videoaula_em_texto():
    """A vídeo-aula é um documento SEPARADO do capítulo, e este importador só
    sabe ler capítulo (desenho do mantenedor, 06/09/2026).

    Ela existe como peça no contrato e no editor, então nada impediria este
    importador de casar um título homônimo com ela. Se casasse, um capítulo com
    a seção "A vídeo-aula, em texto" apagaria, calado, o texto que a professora
    escreveu à mão na outra tela. Aqui o título vira "não reconhecido", que é a
    resposta honesta: o importador não sabe o que fazer com ele.
    """
    lido = tela.interpretar(
        CAPITULO
        + """

## A vídeo-aula, em texto

Fala, gente. Hoje a gente modela um capacete.
"""
    )

    assert "videoaula_em_texto" not in lido["pecas"]
    assert [n["titulo"] for n in lido["nao_reconhecidos"]] == ["A vídeo-aula, em texto"]
    assert "videoaula_em_texto" not in tela.PECAS_NUMERADAS


def test_o_eu_faco_fica_inteiro_numa_peca_so_com_as_subsecoes_dentro():
    """`###` é subseção, não peça. Quebrar aqui picaria a maior peça em três."""
    eu_faco = tela.interpretar(CAPITULO)["pecas"]["eu_faco"]

    assert eu_faco["trechos"] == 1
    assert "### 3.1 Pesar: a balança antes de tudo" in eu_faco["texto"]
    assert "### 3.2 Sovar: o ponto de véu" in eu_faco["texto"]
    assert "### Solução do erro produtivo" in eu_faco["texto"]
    assert eu_faco["texto"].startswith("Na minha primeira fornada")


def test_os_titulos_em_maiusculas_e_com_cauda_casam_com_a_peca_certa():
    pecas = tela.interpretar(CAPITULO)["pecas"]

    assert pecas["eu_faco"]["titulos"] == ["EU FACO"]
    assert pecas["nos_fazemos"]["titulos"][0].startswith("NOS FAZEMOS —")
    assert pecas["voce_faz"]["titulos"][0].startswith("VOCE FAZ —")
    # Singular contra plural, e cauda depois do travessão, na mesma linha.
    assert pecas["drills"]["titulos"][0].startswith("Drill D07 —")


def test_os_dois_apelidos_pegam_o_que_a_normalizacao_nao_alcanca():
    pecas = tela.interpretar(CAPITULO)["pecas"]

    # A pertinência vem antes do conteúdo de propósito: tirar um apelido da
    # tabela precisa reprovar numa ASSERÇÃO, e não num KeyError montando a
    # comparação (`armadilhas/195`).
    assert "regra_do_padrao" in pecas
    assert "critica_de_atelier" in pecas
    assert pecas["regra_do_padrao"]["titulos"][0].startswith("Regra que entra no")
    assert pecas["critica_de_atelier"]["titulos"] == ["Crítica de atelier"]


def test_a_decima_sexta_peca_e_montada_dos_tres_trechos_na_ordem():
    peca = tela.interpretar(CAPITULO)["pecas"]["dicionario_cartao_respostas"]

    assert peca["trechos"] == 3
    assert peca["titulos"] == [
        "Dicionário da Encomenda 03",
        "Cartão de 1 página — Encomenda 03",
        "Respostas",
    ]
    # Cada trecho guarda o próprio título: sem eles ninguém sabe onde um acaba.
    assert "## Dicionário da Encomenda 03" in peca["texto"]
    assert "## Cartão de 1 página — Encomenda 03" in peca["texto"]
    assert "## Respostas" in peca["texto"]
    assert peca["texto"].index("Dicionário") < peca["texto"].index("Cartão")
    assert peca["texto"].index("Cartão") < peca["texto"].index("Respostas")


def test_o_aceito_quando_vira_lista_e_a_linha_continua_no_texto_da_peca():
    lido = tela.interpretar(CAPITULO)

    assert lido["aceito_quando"] == [
        "massa no ponto de véu",
        "base dourada",
        "etiqueta em cada pão",
        "foto da vitrine.",
    ]
    assert "**Aceito quando:**" in lido["pecas"]["voce_faz"]["texto"]


def test_o_quiz_casa_pergunta_com_resposta_pelo_numero():
    lido = tela.interpretar(CAPITULO)

    assert lido["quiz_incompleto"] is False
    assert [q["pergunta"] for q in lido["quiz"]] == [
        "O que o fermento come dentro da massa?",
        "Por que a base fica branca no forno frio?",
        "Quando usar farinha de força?",
    ]
    # A resposta (3) está na segunda linha do parágrafo de respostas, que ele
    # quebrou para caber na largura da página: ler só a primeira linha perderia
    # a última resposta em silêncio.
    assert lido["quiz"][1]["resposta_modelo"].startswith("Porque a base não recebe")
    assert lido["quiz"][2]["resposta_modelo"] == "Quando a massa leva muita água."
    # E o parágrafo depois do quiz não vira rabo da última pergunta.
    assert lido["quiz"][2]["pergunta"] == "Quando usar farinha de força?"


def test_o_quiz_sem_todas_as_respostas_nao_e_gravado_e_a_tela_diz_isso():
    """Inventar resposta é o pior desfecho: o contrato exige uma em cada item."""
    sem_a_terceira = CAPITULO.replace(
        "(3) Quando a massa leva muita água.", "e mais nada."
    )

    lido = tela.interpretar(sem_a_terceira)

    assert lido["quiz"] == []
    assert lido["quiz_incompleto"] is True
    assert "**Quiz** (respostas no fim)" in lido["pecas"]["checkpoint"]["texto"]


def test_o_guia_de_producao_o_marco_e_o_boss_sao_lidos_e_nao_viram_peca():
    lido = tela.interpretar(CAPITULO)

    lidos = [item["titulo"] for item in lido["nao_e_peca"]]
    assert any(t.startswith("Marco de carreira") for t in lidos)
    assert any(t.startswith("Boss B") for t in lidos)
    assert any(t.startswith("GUIA DE PRODUÇÃO") for t in lidos)
    # O Guia jamais entra numa peça: ele é o manual de escrita dos capítulos.
    for peca in lido["pecas"].values():
        assert "Ordem fixa das peças" not in peca["texto"]


def test_o_titulo_o_subtitulo_e_o_boss_sao_lidos_para_a_previa_mostrar():
    lido = tela.interpretar(CAPITULO)

    assert lido["numero"] == "03"
    assert lido["titulo"] == "Me entrega o pão já assado."
    assert lido["subtitulo"].startswith("Da massa ao forno:")
    assert lido["boss"] == {"letra": "B", "titulo": "A vitrine de sábado"}
    assert lido["abertura"].startswith("[ABERTURA")


def test_titulo_que_nao_casa_vira_aviso_com_o_trecho_e_nunca_e_adivinhado():
    lido = tela.interpretar(COM_TITULO_ESTRANHO)

    assert [x["titulo"] for x in lido["nao_reconhecidos"]] == [
        "Caderno de anotações da Padeira"
    ]
    assert lido["nao_reconhecidos"][0]["trecho"] == "O que eu anotei na margem."
    # E o texto dele não foi parar em peça nenhuma.
    for peca in lido["pecas"].values():
        assert "anotei na margem" not in peca["texto"]


# ---------------------------------------------------------------------------
# 2. A TELA — prever, importar, e o que ela recusa
# ---------------------------------------------------------------------------
@respx.mock
@pytest.mark.django_db
def test_prever_mostra_o_que_entraria_e_nao_grava_nada():
    cliente = _dentro()
    gravacao = _porta(_aula(AQUI))

    resposta = cliente.post(_url("escola_capitulo_prever"), {"capitulo": CAPITULO})

    assert resposta.status_code == 200
    assert not gravacao.called
    pagina = resposta.content.decode()
    assert "16 peça(s) reconhecida(s)" in pagina
    assert "Vai preencher" in pagina


@respx.mock
@pytest.mark.django_db
def test_importar_grava_as_dezesseis_pecas_pela_porta_de_maquina():
    cliente = _dentro()
    gravacao = _porta(_aula(AQUI))

    resposta = cliente.post(_url("escola_capitulo_importar"), {"capitulo": CAPITULO})

    assert resposta.status_code == 200
    assert gravacao.called
    corpo = gravacao.calls[0].request.read().decode()
    assert "ponto de véu" in corpo
    assert "Ordem fixa das peças" not in corpo
    assert "gravada, versão 2" in resposta.content.decode()


@respx.mock
@pytest.mark.django_db
def test_peca_que_ja_tem_texto_nunca_e_sobrescrita_e_a_tela_diz_que_preservou():
    cliente = _dentro()
    gravacao = _porta(_aula(AQUI, textos={"eu_faco": "O que eu ja tinha escrito."}))

    resposta = cliente.post(_url("escola_capitulo_importar"), {"capitulo": CAPITULO})

    corpo = gravacao.calls[0].request.read().decode()
    assert "O que eu ja tinha escrito." in corpo
    assert "Na minha primeira fornada" not in corpo
    assert "Deixada em paz" in resposta.content.decode()


@respx.mock
@pytest.mark.django_db
def test_encomenda_com_tudo_escrito_nao_e_gravada_e_a_versao_nao_sobe():
    cliente = _dentro()
    cheia = {tipo: "Texto que ja estava aqui." for tipo in tela.PECAS_NUMERADAS}
    gravacao = _porta(
        _aula(
            AQUI,
            textos=cheia,
            aceito=["Um critério que já estava aqui."],
            quiz=[{"pergunta": "Ja escrita?", "resposta_modelo": "Sim."}],
        )
    )

    resposta = cliente.post(_url("escola_capitulo_importar"), {"capitulo": CAPITULO})

    assert not gravacao.called
    assert "Nada a fazer nesta encomenda." in resposta.content.decode()


@respx.mock
@pytest.mark.django_db
def test_capitulo_de_outra_encomenda_e_recusado_antes_de_gravar():
    """O pior acidente possível aqui: 34 capítulos parecidos, um número só."""
    cliente = _dentro()
    gravacao = _porta(_aula(OUTRA), numero=OUTRA)

    resposta = cliente.post(
        _url("escola_capitulo_importar", OUTRA), {"capitulo": CAPITULO}
    )

    assert resposta.status_code == 400
    assert not gravacao.called
    pagina = resposta.content.decode()
    assert "este capítulo não é o desta encomenda" in pagina
    assert "Encomenda 03" in pagina


@respx.mock
@pytest.mark.django_db
def test_o_arquivo_enviado_vale_e_a_caixa_e_ignorada():
    cliente = _dentro()
    gravacao = _porta(_aula(AQUI))
    arquivo = SimpleUploadedFile(
        "e03.md", CAPITULO.encode("utf-8"), content_type="text/markdown"
    )

    resposta = cliente.post(
        _url("escola_capitulo_importar"), {"capitulo": "", "arquivo": arquivo}
    )

    assert resposta.status_code == 200
    assert gravacao.called
    assert "ponto de véu" in gravacao.calls[0].request.read().decode()


@respx.mock
@pytest.mark.django_db
@pytest.mark.parametrize(
    "envio, esperado",
    [
        ({"capitulo": "   "}, "Cole o capítulo na caixa ou escolha um arquivo"),
        (
            {"arquivo": SimpleUploadedFile("c.pdf", b"%PDF-1.4", "application/pdf")},
            "não é um arquivo de texto",
        ),
        (
            {"arquivo": SimpleUploadedFile("c.md", b"", "text/markdown")},
            "está vazio",
        ),
        (
            {"arquivo": SimpleUploadedFile("c.md", "peça".encode("cp1252"))},
            "codificação",
        ),
    ],
)
def test_cada_envio_que_nao_serve_diz_o_que_houve_e_o_que_fazer(envio, esperado):
    cliente = _dentro()
    gravacao = _porta(_aula(AQUI))

    resposta = cliente.post(_url("escola_capitulo_importar"), envio)

    assert resposta.status_code == 400
    assert not gravacao.called
    assert esperado in resposta.content.decode()


@respx.mock
@pytest.mark.django_db
def test_texto_sem_peca_nenhuma_diz_quais_nomes_a_tela_procura():
    cliente = _dentro()
    gravacao = _porta(_aula(AQUI))

    resposta = cliente.post(
        _url("escola_capitulo_importar"), {"capitulo": "Uma lista de compras.\nPão."}
    )

    assert resposta.status_code == 400
    assert not gravacao.called
    pagina = resposta.content.decode()
    assert "Não reconheci nenhuma peça neste texto" in pagina
    assert "Crítica de ateliê" in pagina


@respx.mock
@pytest.mark.django_db
def test_sala_de_aula_fora_do_ar_nao_grava_e_explica_em_portugues():
    cliente = _dentro()
    respx.get(f"{CURSOS}/cursos/{CURSO}/aulas/{AQUI}").mock(
        side_effect=httpx.ConnectError("caiu")
    )
    gravacao = respx.put(
        url__regex=rf"{re.escape(CURSOS)}/cursos/{CURSO}/aulas/\w+"
    ).mock(return_value=httpx.Response(200, json={"versao": 2}))

    resposta = cliente.post(_url("escola_capitulo_importar"), {"capitulo": CAPITULO})

    assert resposta.status_code == 503
    assert not gravacao.called
    assert "Nada foi gravado" in resposta.content.decode()


@respx.mock
@pytest.mark.django_db
def test_a_tela_nao_guarda_o_capitulo_em_lugar_nenhum_desta_celula():
    """Obra não lançada dele não vira linha de banco nem arquivo aqui."""
    from django.apps import apps

    cliente = _dentro()
    _porta(_aula(AQUI))
    antes = {
        modelo: modelo.objects.count()
        for modelo in apps.get_models()
        if modelo._meta.app_label != "auditoria"
    }

    cliente.post(_url("escola_capitulo_importar"), {"capitulo": CAPITULO})

    for modelo, quantos in antes.items():
        assert modelo.objects.count() == quantos, modelo
