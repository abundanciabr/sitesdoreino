"""A lista de cursos da escola e o gesto Novo curso: `/admin/escola/cursos/`.

A `cursos` e o `catalogo` sao dublados pelo `respx` com respostas NO FORMATO DO
CONTRATO congelado (`contracts/cursos.openapi.yaml`, operacoes `listCourses`,
`createCourse` e `putCourse`; `contracts/catalogo.openapi.yaml`, operacoes
`listProducts` e `createProduct`). Dois guardas leem os contratos do disco para
que a tela e o contrato nao possam divergir em silencio.

O que cada promessa custa, se cair:

1. **A lista mostra os cursos com a regra de avanco em portugues e o nome do
   produto.** Sem ela o mantenedor olha `por_laudo` e `id-do-produto` e nao sabe
   quem entra no curso nem como a proxima aula abre.
2. **"Nao sei" e "nao tem" sao telas diferentes** (a licao do painel da escola).
   Curso sem produto diz que ninguem entra ainda; catalogo fora do ar diz que
   nao deu para ler o nome. As duas frases mandam para lados opostos.
3. **Novo curso funciona nos dois caminhos**: escolhendo um produto que ja
   existe, e criando um produto novo com o nome do curso. O segundo e uma
   sequencia de duas portas, e a metade dela e o caso perigoso.
4. **Produto criado e curso recusado nao fica pela metade.** A tela diz que o
   produto ja existe e manda apertar de novo, e `createProduct` e idempotente
   pelo apelido, entao reenviar nao duplica nada.
5. **A regra de avanco nao tem valor padrao marcado**, e o servidor recusa o
   envio sem ela. Um padrao faria a escolha errada parecer escolha, e ninguem
   veria o erro ate o aluno bater numa porta fechada.
6. **Falha de qualquer porta vira frase em portugues dizendo o que fazer**, e
   nada e gravado sem resposta.
7. **O editor nao entra mais por uma constante.** `CURSO_PADRAO` nao existe, e
   o painel da escola leva a esta lista, nao a um curso escrito no codigo.
8. **As abas de Parte so aparecem quando ha mais de uma Parte** na lista: um
   curso novo, todo na Parte I, nao mostra secao nenhuma.
"""

import re
from pathlib import Path

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.auditoria.models import Registro

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
CATALOGO = "http://catalogo:8000/api/catalogo"
CURSOS = "http://cursos:8000/api/cursos"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"
DONO_ID = "id-opaco-123"
SITE_ID = "site-mesh"
CONTRATOS = Path(__file__).resolve().parents[3] / "contracts"

PRODUTO_ID = "produto-primeiros-dolares"
PRODUTO_NOME = "Primeiros Dolares com Roblox"


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
# AS PORTAS DUBLADAS
# ---------------------------------------------------------------------------
def _dentro() -> Client:
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": DONO_ID,
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


def _curso(
    slug="profissional",
    nome="O curso do livro",
    *,
    progressao="por_laudo",
    produto_id=PRODUTO_ID,
    total=34,
    publicadas=3,
) -> dict:
    return {
        "slug": slug,
        "nome": nome,
        "estado": "rascunho",
        "progressao": progressao,
        "produto_id": produto_id,
        "total_de_aulas": total,
        "aulas_publicadas": publicadas,
    }


def _mock_cursos(cursos=None, status=200):
    return respx.get(f"{CURSOS}/cursos", params={"site_id": SITE_ID}).mock(
        return_value=httpx.Response(
            status, json=[_curso()] if cursos is None else cursos
        )
    )


def _mock_produtos(produtos=None, status=200):
    corpo = (
        [{"id": PRODUTO_ID, "name": PRODUTO_NOME, "price_cents": 0, "active": True}]
        if produtos is None
        else produtos
    )
    return respx.get(f"{CATALOGO}/produtos").mock(
        return_value=httpx.Response(status, json=corpo)
    )


def _tela():
    return reverse("escola_cursos")


def _abrir(cliente=None):
    _mock_site()
    _mock_cursos()
    _mock_produtos()
    return (cliente or _dentro()).get(_tela())


# ---------------------------------------------------------------------------
# 1. A LISTA
# ---------------------------------------------------------------------------
@respx.mock
def test_a_lista_mostra_o_curso_com_a_regra_de_avanco_em_portugues():
    corpo = _abrir().content.decode()
    assert "O curso do livro" in corpo
    assert "profissional" in corpo
    assert "A próxima aula abre com o laudo da professora" in corpo
    # A palavra de máquina só existe como VALOR de campo: ninguém a lê na tela.
    assert "por_laudo" not in corpo.replace('value="por_laudo"', "")


@respx.mock
def test_a_lista_mostra_a_regra_livre_em_portugues():
    _mock_site()
    _mock_cursos([_curso(progressao="livre")])
    _mock_produtos()
    corpo = _dentro().get(_tela()).content.decode()
    assert "A próxima aula abre quando o aluno conclui a anterior" in corpo
    assert "livre" not in corpo.replace('value="livre"', "")


@respx.mock
def test_a_lista_mostra_o_nome_do_produto_casado_pelo_id():
    corpo = _abrir().content.decode()
    assert PRODUTO_NOME in corpo
    # O id do produto é vocabulário de máquina: quem lê a tela lê o NOME.
    assert PRODUTO_ID not in corpo.replace(f'value="{PRODUTO_ID}"', "")


@respx.mock
def test_curso_sem_produto_diz_que_ninguem_entra_ainda():
    _mock_site()
    _mock_cursos([_curso(produto_id="")])
    _mock_produtos()
    corpo = _dentro().get(_tela()).content.decode()
    assert "sem produto: ninguém entra ainda" in corpo


@respx.mock
def test_produto_que_o_catalogo_nao_lista_nao_vira_sem_produto():
    """Produto aposentado some da lista de ativos, e isso NÃO é "sem produto".

    As duas telas mandam para lados opostos: uma diz "aponte um produto", a
    outra diz "olhe o catálogo". Confundi-las faria o mantenedor apontar um
    produto novo num curso que já tinha o certo, e trocar quem entra nele.
    """
    _mock_site()
    _mock_cursos([_curso(produto_id="produto-aposentado")])
    _mock_produtos()
    corpo = _dentro().get(_tela()).content.decode()
    assert "sem produto: ninguém entra ainda" not in corpo
    assert "produto-aposentado" in corpo


@respx.mock
def test_a_lista_leva_ao_editor_de_aulas_daquele_curso():
    corpo = _abrir().content.decode()
    assert reverse("escola_aulas", kwargs={"curso": "profissional"}) in corpo
    assert "Escrever as aulas" in corpo


@respx.mock
def test_a_lista_conta_as_aulas_publicadas_e_o_total():
    corpo = _abrir().content.decode()
    assert "3 de 34" in corpo


@respx.mock
def test_escola_sem_curso_nenhum_convida_a_criar_o_primeiro():
    _mock_site()
    _mock_cursos([])
    _mock_produtos()
    corpo = _dentro().get(_tela()).content.decode()
    assert "Esta escola ainda não tem nenhum curso" in corpo
    # O formulário continua de pé: é justamente aqui que ele é a única saída.
    assert "Novo curso" in corpo


@respx.mock
def test_com_o_catalogo_fora_do_ar_a_lista_abre_e_o_formulario_se_cala():
    """Fail-OPEN na leitura: a lista abre, e o formulário diz por que não dá.

    Criar um curso passa pelo catálogo nos DOIS caminhos (escolher um produto
    ou criar um), então oferecer o formulário sem ele seria oferecer um botão
    que só falha depois de a pessoa digitar tudo.
    """
    _mock_site()
    _mock_cursos()
    _mock_produtos(status=503)
    resposta = _dentro().get(_tela())
    corpo = resposta.content.decode()
    assert resposta.status_code == 200
    assert "O curso do livro" in corpo
    assert "não consegui ler o nome do produto" in corpo
    assert "Escolha o curso" not in corpo
    assert "<form" in corpo.split("Novo curso")[0]  # os formulários de trocar
    assert "não consigo listar os produtos do catálogo agora" in corpo


@respx.mock
def test_a_sala_de_aula_fora_do_ar_diz_o_que_aconteceu_e_o_que_fazer():
    _mock_site()
    _mock_cursos(status=503)
    _mock_produtos()
    resposta = _dentro().get(_tela())
    assert resposta.status_code == 503
    assert "sala de aula" in resposta.content.decode()


@respx.mock
def test_sem_par_de_chaves_nada_vai_a_rede():
    """`armadilhas/097`: env ausente é frase na tela, nunca 500 nem ida à rede."""
    import os

    _mock_site()
    _mock_produtos()
    rota = _mock_cursos()
    os.environ.pop("CURSOS_API_URL")
    resposta = _dentro().get(_tela())
    assert resposta.status_code == 503
    assert not rota.called


# ---------------------------------------------------------------------------
# 2. NOVO CURSO
# ---------------------------------------------------------------------------
def _mock_criar_curso(status=201, corpo=None):
    return respx.post(f"{CURSOS}/cursos", params={"site_id": SITE_ID}).mock(
        return_value=httpx.Response(
            status, json=corpo if corpo is not None else _curso("modelagem-3d", "3D")
        )
    )


def _mock_criar_produto(status=201, corpo=None):
    return respx.post(f"{CATALOGO}/produtos").mock(
        return_value=httpx.Response(
            status,
            json=(
                corpo
                if corpo is not None
                else {
                    "id": "produto-novo",
                    "name": "Modelagem 3D",
                    "price_cents": 0,
                    "active": True,
                }
            ),
        )
    )


def _criar(**campos):
    _mock_site()
    _mock_cursos()
    _mock_produtos()
    dados = {
        "nome": "Modelagem 3D",
        "apelido": "modelagem-3d",
        "produto": PRODUTO_ID,
        "progressao": "livre",
    } | campos
    return _dentro().post(reverse("escola_curso_criar"), dados)


@respx.mock
@pytest.mark.django_db
def test_novo_curso_com_produto_que_ja_existe_chama_so_a_porta_do_curso():
    criar = _mock_criar_curso()
    produto = _mock_criar_produto()
    resposta = _criar()
    assert resposta.status_code == 200
    assert criar.called
    assert not produto.called
    corpo = criar.calls[0].request.content.decode()
    assert '"slug": "modelagem-3d"' in corpo.replace('":"', '": "')
    assert '"produto_id": "' + PRODUTO_ID + '"' in corpo.replace('":"', '": "')
    assert '"progressao": "livre"' in corpo.replace('":"', '": "')
    assert "O curso 3D foi criado" in resposta.content.decode()


@respx.mock
@pytest.mark.django_db
def test_novo_curso_com_produto_novo_cria_o_produto_e_depois_o_curso():
    produto = _mock_criar_produto()
    criar = _mock_criar_curso()
    resposta = _criar(produto="novo")
    assert produto.called and criar.called
    pedido = produto.calls[0].request.content.decode().replace('":"', '": "')
    assert '"slug": "modelagem-3d"' in pedido
    assert '"name": "Modelagem 3D"' in pedido
    assert '"produto_id": "produto-novo"' in criar.calls[
        0
    ].request.content.decode().replace('":"', '": "')
    assert resposta.status_code == 200


@respx.mock
@pytest.mark.django_db
def test_o_apelido_vazio_nasce_do_nome_no_servidor():
    criar = _mock_criar_curso()
    _criar(apelido="", nome="Modelagem 3D Avançada")
    corpo = criar.calls[0].request.content.decode().replace('":"', '": "')
    assert '"slug": "modelagem-3d-avancada"' in corpo


@respx.mock
@pytest.mark.django_db
def test_nome_que_nao_vira_apelido_nenhum_pede_o_apelido_em_vez_de_gravar():
    criar = _mock_criar_curso()
    resposta = _criar(apelido="", nome="!!! ???")
    assert not criar.called
    assert "escreva o apelido" in resposta.content.decode()


@respx.mock
@pytest.mark.django_db
def test_sem_escolher_a_regra_de_avanco_nada_e_gravado():
    criar = _mock_criar_curso()
    resposta = _criar(progressao="")
    assert not criar.called
    # A frase do ERRO, e nao a do <option> vazio do formulario: aquela aparece
    # em toda abertura da tela, e uma asseracao nela ficaria verde sabotada.
    assert "essa regra não tem valor padrão de propósito" in resposta.content.decode()


@respx.mock
def test_a_regra_de_avanco_nasce_sem_nenhuma_opcao_marcada():
    corpo = _abrir().content.decode()
    formulario = corpo[corpo.index("Novo curso") :]
    assert 'name="progressao" required' in formulario
    assert "selected" not in formulario


@respx.mock
@pytest.mark.django_db
def test_apelido_ja_usado_diz_isso_e_nao_inventa_outro():
    _mock_criar_curso(status=409, corpo={"detail": "já existe um curso profissional"})
    resposta = _criar()
    assert "já existe" in resposta.content.decode()


@respx.mock
@pytest.mark.django_db
def test_a_sala_recusar_o_curso_nao_inventa_sucesso():
    _mock_criar_curso(status=422, corpo={"detail": "o apelido está fora da forma"})
    resposta = _criar()
    corpo = resposta.content.decode()
    assert "não aceitou" in corpo
    assert "o apelido está fora da forma" in corpo
    assert "foi criado" not in corpo


@respx.mock
@pytest.mark.django_db
def test_a_sala_nao_responder_nunca_vira_criei():
    _mock_criar_curso(status=500, corpo={})
    resposta = _criar()
    corpo = resposta.content.decode()
    assert "Agora escreva as aulas" not in corpo
    assert "não sei se o curso foi criado" in corpo


@respx.mock
@pytest.mark.django_db
def test_produto_criado_e_curso_recusado_manda_apertar_de_novo():
    """O caso do meio: metade do gesto aconteceu, e a tela diz exatamente isso.

    `createProduct` é idempotente pelo apelido, então reenviar o formulário
    reaproveita o produto em vez de nascer um segundo com o mesmo nome. Sem
    esta frase o mantenedor não sabe se pode apertar de novo.
    """
    _mock_criar_produto()
    _mock_criar_curso(status=500, corpo={})
    corpo = _criar(produto="novo").content.decode()
    assert "O produto Modelagem 3D já existe no catálogo" in corpo
    assert "Aperte" in corpo


@respx.mock
@pytest.mark.django_db
def test_apelido_ja_e_de_outro_produto_para_antes_de_criar_o_curso():
    produto = _mock_criar_produto(
        status=409, corpo={"detail": "o apelido modelagem-3d já é do produto Outro"}
    )
    criar = _mock_criar_curso()
    corpo = _criar(produto="novo").content.decode()
    assert produto.called and not criar.called
    assert "já é do produto Outro" in corpo


@respx.mock
@pytest.mark.django_db
def test_o_catalogo_nao_responder_nao_cria_curso_orfao():
    produto = _mock_criar_produto(status=503, corpo={})
    criar = _mock_criar_curso()
    corpo = _criar(produto="novo").content.decode()
    assert produto.called and not criar.called
    assert "catálogo não respondeu" in corpo


@respx.mock
@pytest.mark.django_db
def test_criar_um_curso_deixa_linha_de_auditoria():
    _mock_criar_curso()
    _criar()
    linha = Registro.objects.get()
    assert linha.acao == Registro.CRIAR_CURSO
    assert linha.alvo == "modelagem-3d"
    assert linha.desfecho == Registro.OK
    assert linha.quem_email == DONO


@respx.mock
@pytest.mark.django_db
def test_a_auditoria_registra_tambem_a_tentativa_que_falhou():
    _mock_criar_curso(status=500, corpo={})
    _criar()
    linha = Registro.objects.get()
    assert linha.desfecho == Registro.NAO_RESPONDEU


# ---------------------------------------------------------------------------
# 3. TROCAR PRODUTO E TROCAR PROGRESSÃO
# ---------------------------------------------------------------------------
def _mock_alterar(slug="profissional", status=200, corpo=None):
    return respx.put(f"{CURSOS}/cursos/{slug}", params={"site_id": SITE_ID}).mock(
        return_value=httpx.Response(status, json=corpo or _curso())
    )


def _alterar(**campos):
    _mock_site()
    _mock_cursos()
    _mock_produtos()
    return _dentro().post(
        reverse("escola_curso_alterar"), {"curso": "profissional"} | campos
    )


@respx.mock
@pytest.mark.django_db
def test_trocar_o_produto_manda_so_o_produto():
    porta = _mock_alterar()
    resposta = _alterar(produto_id=PRODUTO_ID)
    assert porta.called
    corpo = porta.calls[0].request.content.decode()
    assert "produto_id" in corpo
    assert "progressao" not in corpo
    assert "O produto do curso profissional foi trocado" in resposta.content.decode()


@respx.mock
@pytest.mark.django_db
def test_trocar_a_progressao_manda_so_a_progressao():
    porta = _mock_alterar()
    resposta = _alterar(progressao="livre")
    corpo = porta.calls[0].request.content.decode()
    assert "progressao" in corpo
    assert "produto_id" not in corpo
    assert "A regra de avanço do curso profissional foi trocada" in (
        resposta.content.decode()
    )


@respx.mock
@pytest.mark.django_db
def test_trocar_sem_dizer_o_que_trocar_nao_chama_a_porta():
    porta = _mock_alterar()
    resposta = _alterar()
    assert not porta.called
    assert "Escolha o que trocar" in resposta.content.decode()


@respx.mock
@pytest.mark.django_db
def test_a_recusa_de_trocar_chega_em_portugues():
    _mock_alterar(status=422, corpo={"detail": "a progressão não é uma das duas"})
    corpo = _alterar(progressao="livre").content.decode()
    assert "não aceitou" in corpo
    assert "a progressão não é uma das duas" in corpo


@respx.mock
@pytest.mark.django_db
def test_trocar_um_curso_que_nao_existe_diz_isso():
    _mock_alterar(status=404, corpo={})
    corpo = _alterar(progressao="livre").content.decode()
    assert "Não existe nenhum curso" in corpo


@respx.mock
@pytest.mark.django_db
def test_trocar_deixa_linha_de_auditoria_com_o_campo_e_nunca_o_valor():
    """A auditoria guarda QUAIS campos mudaram, nunca o que foi escrito.

    Mesma regra do resto desta área (`LICOES.md`, 28/08/2026): a linha diz o
    gesto, e o valor mora do lado da célula dona.
    """
    _mock_alterar()
    _alterar(produto_id=PRODUTO_ID)
    linha = Registro.objects.get()
    assert linha.acao == Registro.EDITAR_CURSO
    assert linha.alvo == "profissional"
    assert "produto" in linha.detalhe
    assert PRODUTO_ID not in linha.detalhe


# ---------------------------------------------------------------------------
# 4. O EDITOR SEM A CONSTANTE, E O PAINEL DA ESCOLA
# ---------------------------------------------------------------------------
def test_o_editor_nao_entra_mais_por_uma_constante():
    from apps.core import aulas as editor

    assert not hasattr(editor, "CURSO_PADRAO")


@respx.mock
def test_o_painel_da_escola_leva_a_lista_de_cursos():
    corpo = _dentro().get(reverse("escola")).content.decode()
    assert _tela() in corpo
    assert "Cursos" in corpo


@respx.mock
def test_a_tela_de_um_instrumento_volta_para_a_lista_de_cursos():
    """Instrumento é de plataforma inteira: não tem curso, e a volta é a lista.

    Enquanto a volta era um curso escrito no código, ela levava ao curso errado
    em toda escola cujo primeiro curso não se chamasse `profissional`.
    """
    respx.get(f"{CURSOS}/instrumentos/studs").mock(
        return_value=httpx.Response(
            200,
            json={
                "slug": "studs",
                "nome_canonico": "Teste STUDS",
                "cartao": 1,
                "escala": {},
                "minimo_exercicio": "3",
                "minimo_contrato": "4",
                "secao_do_padrao": "§2",
                "descritores": {},
                "versao": 1,
            },
        )
    )
    corpo = (
        _dentro()
        .get(reverse("escola_instrumento", kwargs={"slug": "studs"}))
        .content.decode()
    )
    assert _tela() in corpo


# ---------------------------------------------------------------------------
# 5. AS ABAS DE PARTE SÓ QUANDO HÁ MAIS DE UMA
# ---------------------------------------------------------------------------
def _linha_de_aula(numero: str, parte: int, letra: str) -> dict:
    return {
        "numero": numero,
        "ordem": int(numero[1:]),
        "titulo_exibido": f"Encomenda {numero}",
        "bloco": {"letra": letra, "ordem": 1, "parte": parte},
        "estado": "rascunho",
        "versao": 1,
        "publicada_em": None,
        "e_boss": False,
        "banca_nivel": None,
    }


def _abrir_aulas(aulas):
    _mock_site()
    respx.get(f"{CURSOS}/cursos/novo/aulas", params={"site_id": SITE_ID}).mock(
        return_value=httpx.Response(200, json=aulas)
    )
    respx.get(f"{CURSOS}/instrumentos").mock(return_value=httpx.Response(200, json=[]))
    return (
        _dentro()
        .get(reverse("escola_aulas", kwargs={"curso": "novo"}))
        .content.decode()
    )


@respx.mock
def test_curso_de_uma_parte_so_nao_mostra_aba_de_parte_nenhuma():
    corpo = _abrir_aulas([_linha_de_aula("E01", 1, "A"), _linha_de_aula("E02", 1, "A")])
    assert "Encomenda E01" in corpo
    assert "Parte I" not in corpo
    assert "Ver só esta Parte" not in corpo


@respx.mock
def test_curso_de_duas_partes_mostra_as_abas():
    corpo = _abrir_aulas([_linha_de_aula("E01", 1, "A"), _linha_de_aula("E02", 2, "B")])
    assert "Parte I" in corpo
    assert "Parte II" in corpo
    assert "Ver só esta Parte" in corpo


# ---------------------------------------------------------------------------
# 6. OS GUARDAS DE CONTRATO — a tela e o contrato não divergem em silêncio
# ---------------------------------------------------------------------------
def test_os_campos_que_a_tela_manda_existem_no_contrato_do_curso():
    texto = (CONTRATOS / "cursos.openapi.yaml").read_text(encoding="utf-8")
    bloco = texto[texto.index("    CursoParaCriarSchema:") :][:1400]
    for campo in ("slug", "nome", "progressao", "produto_id"):
        assert re.search(rf"^\s+{campo}:$", bloco, flags=re.M), campo


def test_as_duas_regras_de_avanco_da_tela_sao_as_do_contrato():
    from apps.core.cursos import PROGRESSAO

    texto = (CONTRATOS / "cursos.openapi.yaml").read_text(encoding="utf-8")
    bloco = texto[texto.index("    Progressao:") :][:400]
    do_contrato = set(re.findall(r"^\s+- (\S+)$", bloco, flags=re.M))
    assert set(PROGRESSAO) == do_contrato


def test_o_corpo_do_produto_novo_e_o_do_contrato_do_catalogo():
    texto = (CONTRATOS / "catalogo.openapi.yaml").read_text(encoding="utf-8")
    bloco = texto[texto.index("    NewProduct:") :][:900]
    assert re.search(r"^\s+slug:$", bloco, flags=re.M)
    assert re.search(r"^\s+name:$", bloco, flags=re.M)
