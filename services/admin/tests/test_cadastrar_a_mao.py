"""Cadastrar alguém à mão — `DECISAO-cadastrar-alguem-a-mao.md`.

Até 29/08/2026 toda ficha nascia de um pedido da pessoa ou de uma compra. Um
aluno que não conseguisse usar o formulário do site simplesmente não tinha como
entrar — e o mantenedor não tinha o que fazer a respeito.

**As quatro coisas que este arquivo trava**, e nenhuma delas é "o cadastro
cadastra":

1. **É a MESMA porta de todo mundo.** A pessoa entra na fila
   (`POST /pre-matriculas`) e é liberada na sequência
   (`POST /pre-matriculas/{id}/decisao`). Uma porta nova, capaz de criar
   matrícula direto, seria uma segunda forma de virar aluno com outras regras —
   e as duas discordariam na primeira mudança de lei.

2. **A falha do meio é segura, visível e DITA.** Se a liberação não acontecer, a
   pessoa fica na fila, aparecendo na mesma tela com o botão *Liberar* do lado —
   e a mensagem diz isso, com um "não cadastre de novo" explícito. Um "não deu
   certo" genérico faria o mantenedor cadastrar duas vezes.

3. **A auditoria grava os DOIS passos, inclusive quando falham.** Mesma
   disciplina do resto da área: a linha é escrita depois de saber o desfecho e
   antes de responder, porque uma tentativa que não chegou não pode sumir.

4. **`não respondeu` nunca vira `recusado`.** A criação pode ter acontecido do
   outro lado; dizer "não deu certo" quando pode ter dado é como alguém acaba
   com duas fichas para a mesma pessoa.

E a conferência do formulário usa as MESMAS regras do site — se ela fosse mais
frouxa, a pessoa cadastrada à mão apareceria na lista com um telefone que o
formulário do site nunca teria aceitado.
"""

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.auditoria.models import Registro
from apps.core.views import conferir_cadastro

BASE = "http://identidade:8000/interno"
SESSAO = f"{BASE}/sessao/completa"
ALUNOS = "http://alunos:8000/api/alunos"
LISTA = f"{ALUNOS}/matriculas"
FILA = f"{ALUNOS}/pre-matriculas"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"
ID_DO_DONO = "id-opaco-123"
NOVA_LINHA = "77"

BOM = {
    "nome_completo": "Açainite Ferreira",
    "email": "Acainite@Exemplo.com",
    "whatsapp": "(96) 99999-0000",
    "turma": "Turma de agosto",
    "comprou_em": "2026-08-01",
    "site_id": "escola-a",
    # [CURSO] Obrigatório desde 06/09/2026 ([INV-ALU-C1]): este formulário
    # cadastra E libera no mesmo clique, e ninguém é aluno do site — todo mundo
    # é aluno de um produto. O que acontece SEM ele mora em
    # `test_liberar_com_curso.py`, junto com os outros três caminhos que
    # liberam; aqui ele é só o campo bem preenchido.
    "product_id": "prod-primeiros-dolares",
}


@pytest.fixture(autouse=True)
def env(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", BASE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    monkeypatch.setenv("ALUNOS_API_URL", ALUNOS)
    monkeypatch.setenv("ALUNOS_API_TOKEN", "token-do-par-admin-alunos")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


def _dentro() -> Client:
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": ID_DO_DONO,
                "nome_exibido": "Fulano",
                "papel": None,
                "email": DONO,
            },
        )
    )
    c = Client()
    c.defaults["HTTP_COOKIE"] = COOKIE
    return c


def _fila_responde(criar=None, liberar=None):
    criacao = respx.post(FILA).mock(
        return_value=criar
        or httpx.Response(201, json={"id": NOVA_LINHA, "status": "aguardando"})
    )
    liberacao = respx.post(f"{FILA}/{NOVA_LINHA}/decisao").mock(
        return_value=liberar or httpx.Response(200, json={"status": "ativa"})
    )
    return criacao, liberacao


def _matricula(id_, site_id) -> dict:
    return {
        "id": id_,
        "site_id": site_id,
        "email": f"pessoa{id_}@exemplo.com",
        "nome_completo": f"Pessoa {id_}",
        "whatsapp": "",
        "turma": None,
        "comprou_em": None,
        "status": "ativa",
        "origem": "liberado",
        "criada_em": "2026-08-20T10:00:00Z",
    }


def _leituras_respondem(alunos=None):
    """As consultas que a TELA faz ao voltar do formulário.

    Separadas das de escrita porque a maioria dos testes daqui não abre a tela —
    e um mock a mais em cada um deles esconderia o que cada teste mede.
    """
    respx.get(FILA, params={"status": "aguardando"}).mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(FILA, params={"status": "recusada"}).mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(LISTA).mock(return_value=httpx.Response(200, json=alunos or []))


def _cadastrar(client, **mudancas):
    corpo = dict(BOM)
    corpo.update(mudancas)
    return client.post(reverse("escola_cadastrar"), corpo)


def _recado(resposta) -> str:
    return resposta["Location"].split("resultado=")[-1]


# ------------------------------------------- 1. é a mesma porta de todo mundo


@respx.mock
def test_cadastrar_poe_na_fila_e_libera_na_sequencia():
    """O teste que carrega este arquivo.

    Nenhuma porta nova: a pessoa faz o mesmo caminho de quem preenche o
    formulário do site, só que depressa.
    """
    criacao, liberacao = _fila_responde()
    resposta = _cadastrar(_dentro())

    assert criacao.called and liberacao.called
    assert _recado(resposta) == "cadastrado"

    enviado = criacao.calls[0].request.read().decode()
    assert '"escola-a"' in enviado
    assert "Turma de agosto" in enviado

    decisao = liberacao.calls[0].request.read().decode()
    assert '"liberar"' in decisao
    assert ID_DO_DONO in decisao, "quem liberou fica gravado do outro lado"


@respx.mock
def test_o_email_viaja_em_minusculas():
    """A Caixa pergunta por `email.strip().lower()`.

    Uma ficha gravada com maiúsculas seria liberada e continuaria invisível para
    ela — a pessoa veria "não encontramos matrícula" DEPOIS de ter sido
    aprovada, que é o pior desfecho possível deste formulário.
    """
    criacao, _ = _fila_responde()
    _cadastrar(_dentro())
    assert "acainite@exemplo.com" in criacao.calls[0].request.read().decode()


@respx.mock
def test_campo_opcional_em_branco_nao_viaja():
    """Turma e data em branco significam "não sei" — mandar `""` seria pedir ao
    outro lado para gravar uma turma vazia como se fosse um dado."""
    criacao, _ = _fila_responde()
    _cadastrar(_dentro(), turma="", comprou_em="")
    enviado = criacao.calls[0].request.read().decode()
    assert "turma" not in enviado
    assert "comprou_em" not in enviado


# --------------------------------------- 2. a falha do meio é segura e dita


@respx.mock
def test_liberacao_falhando_deixa_a_pessoa_na_fila_e_a_tela_diz_onde():
    """O desfecho mais importante deste formulário.

    A pessoa NÃO some: ela fica esperando na mesma tela, com o botão Liberar do
    lado. E a mensagem diz isso — um "não deu certo" genérico faria o mantenedor
    cadastrar de novo e criar confusão sobre a mesma pessoa.
    """
    criacao, liberacao = _fila_responde(liberar=httpx.Response(500))
    resposta = _cadastrar(_dentro())

    assert criacao.called and liberacao.called
    assert _recado(resposta) == "cadastrado-na-fila"


@respx.mock
def test_a_mensagem_da_falha_do_meio_manda_nao_cadastrar_de_novo():
    _fila_responde(liberar=httpx.Response(500))
    _leituras_respondem()
    cliente = _dentro()
    # SEGUE o redirecionamento: o recado viaja na query string, e um GET nu na
    # lista mostraria a tela sem ele — o teste passaria a medir outra página.
    html = cliente.get(_cadastrar(cliente)["Location"]).content.decode()
    assert "Não cadastre de novo" in html
    assert "na fila, esperando" in html


@respx.mock
def test_quem_ja_e_aluno_e_recusado_com_o_caminho_da_correcao():
    """409 da `alunos`: este e-mail já tem matrícula que vale.

    A tela manda procurar na lista — que é o que resolve —, em vez de sugerir
    tentar de novo, que nunca vai funcionar.
    """
    criacao, liberacao = _fila_responde(criar=httpx.Response(409, json={}))
    _leituras_respondem()
    cliente = _dentro()
    resposta = _cadastrar(cliente)

    assert criacao.called
    assert not liberacao.called, "não se libera o que não foi criado"
    assert _recado(resposta) == "cadastro-nao-valeu"
    assert "já é aluna" in cliente.get(resposta["Location"]).content.decode()


@respx.mock
def test_a_alunos_fora_do_ar_diz_que_o_cadastro_PODE_ter_sido_feito():
    """`não respondeu` nunca vira `recusado`.

    A criação pode ter acontecido do outro lado. Dizer "não deu certo" quando
    pode ter dado é como alguém acaba com duas fichas para a mesma pessoa.
    """
    respx.post(FILA).mock(side_effect=httpx.ConnectError("recusou"))
    _leituras_respondem()
    cliente = _dentro()
    resposta = _cadastrar(cliente)

    assert _recado(resposta) == "cadastro-nao-deu"
    html = cliente.get(resposta["Location"]).content.decode()
    assert "PODE ter sido feito" in html
    assert "antes de tentar de novo" in html


@respx.mock
def test_corpo_2xx_fora_do_contrato_nao_vira_sucesso():
    """*Status 2xx não é sucesso* (`RETROSPECTIVA-FASE-D.md` §4).

    Sem o id não há como liberar — e chamar isso de OK deixaria a pessoa parada
    na fila com a tela dizendo que ela já é aluna.
    """
    criacao, liberacao = _fila_responde(criar=httpx.Response(201, json={}))
    resposta = _cadastrar(_dentro())

    assert criacao.called
    assert not liberacao.called
    assert _recado(resposta) == "cadastro-nao-deu"


# ------------------------------------------------ 3. a auditoria grava tudo


@respx.mock
def test_a_auditoria_grava_o_cadastro_com_verbo_proprio():
    """ "Liberei quem pediu" e "cadastrei alguém que não pediu" são gestos
    diferentes, e quem ler esta tabela em meses precisa saber qual foi."""
    _fila_responde()
    _cadastrar(_dentro())

    linha = Registro.objects.get()
    assert linha.acao == Registro.CADASTRAR
    assert linha.desfecho == Registro.OK
    assert linha.quem_email == DONO
    assert linha.alvo == NOVA_LINHA


@respx.mock
def test_a_auditoria_grava_ate_o_que_nao_deu_certo():
    _fila_responde(liberar=httpx.Response(500))
    _cadastrar(_dentro())

    linha = Registro.objects.get()
    assert linha.acao == Registro.CADASTRAR
    assert linha.desfecho == Registro.NAO_RESPONDEU


@respx.mock
def test_a_auditoria_nao_guarda_o_nome_nem_o_telefone_de_ninguem():
    """A regra do §4 da `DECISAO-administradores-e-apagar`, valendo no verbo novo.

    Esta tabela é append-only por trigger. PII aqui é PII que nunca mais sai.
    """
    _fila_responde()
    _cadastrar(_dentro())

    linha = Registro.objects.get()
    tudo = f"{linha.alvo} {linha.detalhe}"
    assert "Açainite" not in tudo
    assert "99999-0000" not in tudo


@respx.mock
def test_formulario_invalido_nao_grava_auditoria_nem_chama_a_alunos():
    """Nada foi tentado do outro lado — e uma linha aqui contaria uma ação que
    não existiu."""
    criacao, _ = _fila_responde()
    resposta = _cadastrar(_dentro(), whatsapp="123")

    assert not criacao.called
    assert Registro.objects.count() == 0
    assert _recado(resposta) == "cadastro-invalido"


# ------------------------------------------- 4. a conferência, e a tela


def test_a_conferencia_usa_as_mesmas_regras_do_site():
    """Mais frouxa aqui, e a pessoa cadastrada à mão aparece na lista com um
    telefone que o formulário do site nunca teria aceitado."""
    assert conferir_cadastro(BOM) == []

    sem_nome = conferir_cadastro({**BOM, "nome_completo": ""})
    assert any("nome completo" in e for e in sem_nome)

    zap_curto = conferir_cadastro({**BOM, "whatsapp": "9999"})
    assert any("não parece completo" in e for e in zap_curto)

    data_torta = conferir_cadastro({**BOM, "comprou_em": "01/08/2026"})
    assert any("dia/mês/ano" in e for e in data_torta)


def test_a_conferencia_devolve_TODOS_os_erros_de_uma_vez():
    """Corrigir um campo por envio é a forma mais rápida de alguém desistir."""
    vazio = {c: "" for c in BOM}
    assert len(conferir_cadastro(vazio)) >= 3


@respx.mock
def test_com_uma_escola_so_o_formulario_nao_pergunta_qual():
    """O identificador interno é ruído numa tela de leigo, e há um teste-guarda
    de 28/08 que o proíbe de aparecer aqui.

    Quem descobre a escola é o servidor, no envio. Perguntar ao mantenedor um
    dado que o sistema já sabe é o oposto do que este formulário existe para
    fazer.
    """
    _leituras_respondem([_matricula("1", "escola-a")])
    html = _dentro().get("/escola/alunos/").content.decode()

    assert "Cadastrar alguem a mao" in html
    assert "escola-a" not in html
    assert 'name="site_id"' not in html


@respx.mock
def test_sem_o_campo_o_servidor_descobre_a_escola_sozinho():
    """O outro lado do teste acima: o valor que não está na tela chega mesmo
    assim na `alunos`."""
    criacao, liberacao = _fila_responde()
    _leituras_respondem([_matricula("1", "escola-a")])
    resposta = _cadastrar(_dentro(), site_id="")

    assert _recado(resposta) == "cadastrado"
    assert '"escola-a"' in criacao.calls[0].request.read().decode()


@respx.mock
def test_com_a_escola_vazia_e_sem_campo_o_cadastro_para_e_explica():
    """Zero fichas: não há de onde derivar, e adivinhar seria pior que parar.

    O recado manda escrever o nome da escola — a tela mostra o campo justamente
    neste caso.
    """
    criacao, _ = _fila_responde()
    _leituras_respondem([])
    cliente = _dentro()
    resposta = _cadastrar(cliente, site_id="")

    assert not criacao.called
    assert _recado(resposta) == "cadastro-sem-escola"
    assert "de qual escola" in cliente.get(resposta["Location"]).content.decode()


@respx.mock
def test_com_duas_escolas_o_formulario_pergunta_qual():
    """As opções saem dos dados de hoje, nunca de uma lista configurada — uma
    lista própria seria uma segunda verdade sobre quais escolas existem."""
    _leituras_respondem([_matricula("1", "escola-a"), _matricula("2", "escola-b")])
    html = _dentro().get("/escola/alunos/").content.decode()

    assert "Cadastrar alguem a mao" in html
    assert '<option value="escola-a">' in html
    assert '<option value="escola-b">' in html
    assert 'name="site_id"' in html


@respx.mock
def test_a_rota_de_cadastrar_nao_atende_GET():
    """Gesto que muda a vida de alguém não se aplica por GET — um
    pré-carregador de link o tomaria sozinho."""
    assert _dentro().get(reverse("escola_cadastrar")).status_code == 405
