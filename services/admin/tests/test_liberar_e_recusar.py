"""Liberar e recusar quem está na fila — a PRIMEIRA escrita desta área.

`DECISAO-fila-de-liberacao` §8 fase 2. E, junto com ela, a auditoria que a
`DECISAO-celula-admin` §3 exige — no MESMO PR, que é a regra que o `LICOES.md`
desta célula fixou depois de a auditoria ter sido adiada uma vez.

**Os três testes que carregam o arquivo**, e nenhum deles é "o botão funciona":

1. `test_a_auditoria_registra_ate_o_que_nao_deu_certo`. Auditoria que só grava
   sucesso responde *"quem liberou?"* e não responde *"o que foi tentado
   aqui?"* — e é a segunda pergunta que alguém faz quando um aluno diz "eu fui
   liberado e continuo sem acesso". Uma decisão que a `alunos` não recebeu não
   deixa rastro nenhum LÁ (não há linha para carimbar), então ou fica aqui ou
   não fica em lugar nenhum.

2. `test_a_auditoria_e_append_only_no_BANCO`. O `save()` sobrescrito não
   impede nada (`armadilhas/079`): `QuerySet.update()` não o chama e `psql`
   não o conhece. O guarda mede o trigger, exercitando o caminho que passaria
   por baixo de qualquer proteção em Python.

3. `test_a_auditoria_nao_guarda_dado_pessoal_do_aluno`. O nome e o telefone de
   quem espera moram na `alunos`, e é ela quem decide quem os vê (lei da fila
   §5). Copiá-los para cá criaria um segundo lugar de onde vazar — e a linha de
   auditoria continua útil sem eles, porque o `alvo` cruza com a origem.

E `test_decidir_nao_atende_GET`: uma decisão que se aplica por GET é uma
decisão que um pré-carregador de link, um antivírus corporativo ou um crawler
autenticado tomam sozinhos. Aqui ela muda a vida de uma pessoa.
"""

import json

import httpx
import pytest
import respx
from django.db import DatabaseError, IntegrityError, transaction
from django.test import Client
from django.urls import reverse

from apps.auditoria.models import Registro

BASE = "http://identidade:8000/interno"
SESSAO = f"{BASE}/sessao/completa"
ALUNOS = "http://alunos:8000/api/alunos"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"
ID_DO_DONO = "id-opaco-123"
ALVO = "42"


@pytest.fixture(autouse=True)
def env(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", BASE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    monkeypatch.setenv("ALUNOS_API_URL", ALUNOS)
    monkeypatch.setenv("ALUNOS_API_TOKEN", "token-do-par-admin-alunos")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


def _dentro(email: str = DONO) -> Client:
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": ID_DO_DONO,
                "nome_exibido": "Fulano",
                "papel": None,
                "email": email,
            },
        )
    )
    c = Client()
    c.defaults["HTTP_COOKIE"] = COOKIE
    return c


def _decisao_responde(resposta):
    return respx.post(f"{ALUNOS}/pre-matriculas/{ALVO}/decisao").mock(
        return_value=resposta
    )


def _fila_vazia():
    """A LISTA, para os testes que abrem a tela depois de decidir.

    Sem isto, `respx.mock` estoura na primeira leitura da fila — e é justamente
    o que se quer dele: nenhuma chamada de rede desta célula passa sem alguém
    ter dito o que ela responde.
    """
    respx.get(f"{ALUNOS}/pre-matriculas").mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(f"{ALUNOS}/matriculas").mock(return_value=httpx.Response(200, json=[]))


def _decidir(client, **campos):
    # [CURSO] `product_id` é obrigatório para liberar desde 06/09/2026
    # ([INV-ALU-C1]). Entra aqui, no molde, para estes testes continuarem
    # medindo o que sempre mediram — a auditoria e os desfechos. A escolha do
    # curso em si é medida em `test_liberar_com_curso.py`.
    corpo = {"alvo": ALVO, "decisao": "liberar", "product_id": "prod-um"}
    corpo.update(campos)
    return client.post(reverse("escola_decidir"), corpo)


# ------------------------------------------------------------- o caminho feliz


@pytest.mark.django_db
@respx.mock
def test_liberar_chega_a_alunos_com_quem_decidiu():
    rota = _decisao_responde(httpx.Response(200))
    r = _decidir(_dentro())

    assert r.status_code == 302
    assert r["Location"].endswith("?resultado=liberado")
    enviado = json.loads(rota.calls.last.request.read())
    assert enviado["decisao"] == "liberar"
    # Por ID de plataforma, e não por e-mail: e-mail muda de dono dentro de uma
    # organização; o id, não. É a auditoria de quem liberou quem do OUTRO lado.
    assert enviado["decidido_por"] == ID_DO_DONO
    # E sem motivo: liberar não tem por que carregar um campo vazio para o
    # outro lado — `additionalProperties` do contrato recusaria chave estranha,
    # e mandar `""` seria pedir para alguém gravar um motivo em branco.
    assert "motivo" not in enviado


@pytest.mark.django_db
@respx.mock
def test_recusar_leva_o_motivo_e_ele_fica_na_auditoria():
    rota = _decisao_responde(httpx.Response(200))
    _decidir(_dentro(), decisao="recusar", motivo="não achei sua compra")

    assert (
        json.loads(rota.calls.last.request.read())["motivo"] == "não achei sua compra"
    )
    linha = Registro.objects.get()
    assert linha.acao == Registro.RECUSAR
    assert linha.desfecho == Registro.OK
    # O motivo é parte do que foi feito: sem ele a linha diz "recusou" e não
    # diz o que a pessoa recusada leu.
    assert linha.detalhe == "não achei sua compra"


@pytest.mark.django_db
@respx.mock
def test_recusar_sem_motivo_nao_sai_para_a_rede_nem_inventa_auditoria():
    """A pessoa ficaria esperando sem saber por quê (lei da fila §7).

    Conferido AQUI e não só na `alunos`: a mensagem que o mantenedor precisa
    ler é sobre o formulário dele, e uma ida à rede para descobrir isso seria
    lentidão sem informação nova. E NÃO grava auditoria — não houve decisão
    sobre pessoa nenhuma, e ruído de formulário quebrado só atrapalha quem for
    ler este registro um dia.
    """
    rota = _decisao_responde(httpx.Response(200))
    r = _decidir(_dentro(), decisao="recusar", motivo="   ")

    assert r["Location"].endswith("?resultado=sem-motivo")
    assert not rota.called
    assert Registro.objects.count() == 0


# ------------------------------------------------- a auditoria registra TUDO


@pytest.mark.django_db
@respx.mock
@pytest.mark.parametrize(
    "resposta,desfecho,recado",
    [
        (httpx.Response(200), Registro.OK, "liberado"),
        (httpx.Response(409), Registro.RECUSADO_PELA_CELULA, "nao-valeu"),
        (httpx.Response(404), Registro.RECUSADO_PELA_CELULA, "nao-valeu"),
        (httpx.Response(500), Registro.NAO_RESPONDEU, "nao-deu"),
    ],
)
def test_a_auditoria_registra_ate_o_que_nao_deu_certo(resposta, desfecho, recado):
    _decisao_responde(resposta)
    r = _decidir(_dentro())

    linha = Registro.objects.get()
    assert linha.desfecho == desfecho
    assert linha.quem_email == DONO
    assert linha.alvo == ALVO
    assert r["Location"].endswith(f"?resultado={recado}")


@pytest.mark.django_db
@respx.mock
def test_a_alunos_fora_do_ar_vira_linha_de_auditoria_e_aviso_honesto():
    """ "Não respondeu" tem nome próprio, e não vira "recusado".

    A decisão PODE ter sido aplicada do outro lado. Dizer ao mantenedor "não
    deu certo" quando pode ter dado é como ele acaba decidindo duas vezes sobre
    a mesma pessoa — e a tela diz isso, com essas palavras.
    """
    _decisao_responde(httpx.Response(200)).side_effect = httpx.ConnectError("recusou")
    r = _decidir(_dentro())

    assert Registro.objects.get().desfecho == Registro.NAO_RESPONDEU
    assert r["Location"].endswith("?resultado=nao-deu")
    _fila_vazia()
    html = _dentro().get(r["Location"]).content.decode()
    assert "PODE ter" in html


@pytest.mark.django_db
@respx.mock
def test_sem_o_par_de_tokens_a_decisao_nao_some_em_silencio():
    """O estado de HOJE, até o provisionamento rodar: nem por isso a tentativa
    deixa de ser registrada."""
    import os

    os.environ.pop("ALUNOS_API_URL", None)
    r = _decidir(_dentro())
    assert Registro.objects.get().desfecho == Registro.NAO_RESPONDEU
    assert r["Location"].endswith("?resultado=nao-deu")


# ------------------------------------------------- append-only, no BANCO


@pytest.mark.django_db
@respx.mock
def test_a_auditoria_e_append_only_no_BANCO():
    """`QuerySet.update()` e `.delete()` passam por baixo de qualquer `save()`.

    Este teste NÃO chama o model: ele usa exatamente os caminhos que um
    override em Python não vê. Quem recusa é o trigger da migration `0001`.
    """
    _decisao_responde(httpx.Response(200))
    _decidir(_dentro())
    linha = Registro.objects.get()

    # `DatabaseError` (o pai) e a MENSAGEM, em vez da classe exata: é o que
    # torna este guarda honesto nos dois bancos. A primeira versão exigia
    # `IntegrityError` e reprovou no CI — o Postgres levantava `ProgrammingError`
    # porque o `RAISE EXCEPTION` não dizia o código do erro. O trigger foi
    # corrigido (ERRCODE 23000, os dois viram `IntegrityError`) E a asserção
    # afrouxou para a classe-pai: travar a classe exata é travar um detalhe do
    # driver, não a promessa.
    for operacao in (
        lambda: Registro.objects.filter(pk=linha.pk).update(desfecho=Registro.OK),
        lambda: Registro.objects.filter(pk=linha.pk).delete(),
    ):
        with pytest.raises(DatabaseError) as erro, transaction.atomic():
            operacao()
        assert "append-only" in str(erro.value)
        assert isinstance(erro.value, IntegrityError), (
            "o banco recusou, mas com a classe errada — quem escrever um "
            "`except IntegrityError` daqui a meses não vai pegar isto"
        )

    assert Registro.objects.count() == 1


@pytest.mark.django_db
@respx.mock
def test_a_auditoria_nao_guarda_dado_pessoal_do_aluno():
    """Nome e telefone moram na `alunos`, e é ela quem decide quem os vê.

    A linha continua útil sem eles: o `alvo` cruza com a origem. Asserção por
    conjunto EXATO de campos — campo novo com qualquer nome fica vermelho até
    alguém decidir explicitamente.
    """
    _decisao_responde(httpx.Response(200))
    _decidir(_dentro(), decisao="recusar", motivo="não achei")

    campos = {c.name for c in Registro._meta.get_fields()}
    assert campos == {
        "id",
        "quando",
        "quem_email",
        "quem_id",
        "acao",
        "alvo",
        "desfecho",
        "detalhe",
    }


# ------------------------------------------------------------- a borda


@respx.mock
def test_decidir_nao_atende_GET():
    assert _dentro().get(reverse("escola_decidir")).status_code == 405


@respx.mock
def test_decidir_sem_csrf_e_recusado():
    """A porta desta célula roda DEPOIS do CSRF, de propósito.

    Sem este guarda, um site qualquer poderia postar aqui usando o cookie de
    sessão do mantenedor e liberar quem quisesse.
    """
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
    rigoroso = Client(enforce_csrf_checks=True)
    rigoroso.defaults["HTTP_COOKIE"] = COOKIE
    resposta = rigoroso.post(
        reverse("escola_decidir"), {"alvo": ALVO, "decisao": "liberar"}
    )
    assert resposta.status_code == 403


@pytest.mark.django_db
@respx.mock
def test_quem_nao_esta_na_lista_nao_decide_nada():
    r = _decidir(_dentro("estranho@exemplo.com"))
    assert r.status_code == 404
    assert Registro.objects.count() == 0


@pytest.mark.django_db
@respx.mock
@pytest.mark.parametrize("decisao", ["", "apagar", "LIBERAR", "liberar; drop"])
def test_decisao_fora_do_vocabulario_nao_faz_nada(decisao):
    """Lista de PERMISSÃO, não de exclusão: verbo novo nasce sem efeito."""
    rota = _decisao_responde(httpx.Response(200))
    _decidir(_dentro(), decisao=decisao)
    assert not rota.called
    assert Registro.objects.count() == 0


@respx.mock
def test_o_recado_da_tela_nunca_ecoa_a_querystring():
    """XSS refletido numa área de operação.

    O que vem do navegador é só uma CHAVE; o texto sai de um conjunto fechado
    no código. O teste manda o payload e exige que ele NÃO apareça.
    """
    payload = "<script>alert(1)</script>"
    _fila_vazia()
    html = (
        _dentro()
        .get(f"{reverse('escola_alunos')}?resultado={payload}")
        .content.decode()
    )
    assert "alert(1)" not in html
    assert "<script>alert" not in html
