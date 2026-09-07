"""A tela `/admin/encomendas/parametros/`, os números que a Fila obedece.

O que estes guardas protegem:

1. **Esta tela não guarda nada.** Ela lê e grava na `encomendas`, que é a dona
   dos parâmetros. Uma cópia aqui seria o mesmo fato em dois lugares, e no dia
   em que as duas discordassem a tela mostraria um prazo e o aluno cumpriria
   outro. Nenhum número da lei mora neste repositório fora do semeador daquela
   célula, e o guarda de constante mágica de lá mede isso a cada PR.
2. **Mudar é ACRESCENTAR**, nunca sobrescrever: a tela manda valor, motivo e
   autor, e o autor é quem está logado, nunca um campo digitado.
3. **As chaves sem número aparecem, e a tela explica por quê.** As três do piso
   de preço nascem vazias de propósito; um campo em branco sem explicação no
   meio de trinta e quatro números pareceria defeito da tela.
4. **Cada gesto vira linha de auditoria**, inclusive quando a célula recusa. É a
   metade do rastro que só existe aqui: a recusa não escreve nada do outro lado.
5. **Grau de escrita ausente não vira erro cru.** A tela ABRE, mostra tudo, e o
   botão responde em português dizendo qual roteiro rodar (`armadilhas/318`).
6. **Par de tokens ausente abre a tela mesmo assim**, dizendo o que falta.
   Fail-OPEN na leitura: uma tela de operação que não abre é inútil justamente
   quando você precisa dela.
7. **A porta continua sendo a porta**: sem crachá, nada disto responde.
"""

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.auditoria.models import Registro

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
ENCOMENDAS = "http://encomendas:8000/api/encomendas"
PARAMETROS = f"{ENCOMENDAS}/parametros"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"


def _parametro(chave, tipo, descricao, vigente=None, historico=None):
    return {
        "chave": chave,
        "tipo": tipo,
        "descricao": descricao,
        "vigente": vigente,
        "historico": historico or ([vigente] if vigente else []),
    }


def _linha(
    valor, desde="2026-01-01T00:00:00Z", motivo="Valor inicial da lei.", quem=""
):
    return {"valor": valor, "desde": desde, "motivo": motivo, "quem": quem}


# O que a porta devolveria, no formato do contrato. As três do piso vêm com
# `vigente` nulo, que é como a célula as devolve de verdade.
RESPOSTA = [
    _parametro(
        "piso_por_nivel.iniciante", "centavos", "Piso sugerido do nível iniciante"
    ),
    _parametro(
        "relogio_da_oferta",
        "horas",
        "Horas úteis que o aluno tem para responder",
        vigente=_linha("3"),
    ),
    _parametro(
        "rodadas_de_negociacao",
        "inteiro",
        "Rodadas de proposta que cada lado tem",
        vigente=_linha(
            "4",
            desde="2026-09-06T10:00:00Z",
            motivo="Tres rodadas travavam.",
            quem="id-opaco-123",
        ),
        historico=[
            _linha(
                "4",
                desde="2026-09-06T10:00:00Z",
                motivo="Tres rodadas travavam.",
                quem="id-opaco-123",
            ),
            _linha("3"),
        ],
    ),
]


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    monkeypatch.setenv("ENCOMENDAS_API_URL", ENCOMENDAS)
    monkeypatch.setenv("ENCOMENDAS_API_TOKEN", "token-de-ler")
    monkeypatch.setenv("ENCOMENDAS_API_TOKEN_ESCRITA", "token-de-gravar")
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
    c = Client()
    c.defaults["HTTP_COOKIE"] = COOKIE
    return c


# ---------------------------------------------------------------------------
# 1. A tela lê pela porta, e não guarda nada
# ---------------------------------------------------------------------------


@respx.mock
def test_a_tela_mostra_o_que_a_celula_respondeu():
    respx.get(PARAMETROS).mock(return_value=httpx.Response(200, json=RESPOSTA))
    pagina = _dentro().get(reverse("parametros_da_fila"))
    assert pagina.status_code == 200
    corpo = pagina.content.decode()
    # A descrição vem da célula, não de uma tabela escrita nesta tela.
    assert "Horas úteis que o aluno tem para responder" in corpo
    assert "Rodadas de proposta que cada lado tem" in corpo
    # O valor de agora, com a unidade que o TIPO manda.
    assert "3" in corpo and "horas" in corpo
    # E a conta do cabeçalho sai do que voltou, nunca de um número escrito aqui.
    assert "2 de 3" in corpo


@respx.mock
def test_nenhum_numero_da_lei_vive_nesta_tela():
    """A prova de que esta tela não é uma segunda régua.

    Ela desenha o que a célula respondeu, aconteça o que acontecer. Com uma
    resposta de valores absurdos, a tela mostra os absurdos: se algum número
    estivesse escrito neste lado, ele apareceria aqui e a asserção cairia.
    """
    absurdo = [
        _parametro(
            "relogio_da_oferta",
            "horas",
            "Horas úteis que o aluno tem para responder",
            vigente=_linha("999"),
        )
    ]
    respx.get(PARAMETROS).mock(return_value=httpx.Response(200, json=absurdo))
    corpo = _dentro().get(reverse("parametros_da_fila")).content.decode()
    assert "999" in corpo
    assert "1 de 1" in corpo


@respx.mock
def test_a_chave_sem_numero_aparece_e_a_tela_explica():
    """O §9 numa tela: a chave existe, o número não, e a ausência é decisão.

    Sem esta seção, as três do piso ficariam invisíveis no meio de trinta e
    quatro cartões preenchidos, e o mantenedor nunca descobriria que pode
    gravá-las.
    """
    respx.get(PARAMETROS).mock(return_value=httpx.Response(200, json=RESPOSTA))
    corpo = _dentro().get(reverse("parametros_da_fila")).content.decode()
    assert "Esperando um número seu" in corpo
    assert "Piso sugerido do nível iniciante" in corpo
    assert "nenhuma proposta" in corpo


@respx.mock
def test_a_data_chega_em_portugues_e_nao_no_formato_da_maquina():
    """`2026-09-06T10:00:00Z` responde a uma maquina; `06/09/2026`, a uma pessoa.

    O instante e o dado que responde "desde quando este numero vale?", e uma
    tela que o mostrasse no formato do contrato deixaria o mantenedor
    decifrando pontuacao em vez de lendo uma data.
    """
    respx.get(PARAMETROS).mock(return_value=httpx.Response(200, json=RESPOSTA))
    corpo = _dentro().get(reverse("parametros_da_fila")).content.decode()
    assert "06/09/2026" in corpo
    assert "2026-09-06T10:00:00Z" not in corpo


@respx.mock
def test_o_historico_de_cada_numero_aparece():
    """Sem o histórico, "mudar é acrescentar" seria uma frase num documento."""
    respx.get(PARAMETROS).mock(return_value=httpx.Response(200, json=RESPOSTA))
    corpo = _dentro().get(reverse("parametros_da_fila")).content.decode()
    assert "Tres rodadas travavam." in corpo
    assert "O que este número já foi" in corpo


# ---------------------------------------------------------------------------
# 2. Gravar é acrescentar uma linha, com motivo e autor
# ---------------------------------------------------------------------------


@respx.mock
def test_gravar_manda_valor_motivo_e_autor_pela_porta_de_escrita(db):
    rota = respx.put(f"{PARAMETROS}/rodadas_de_negociacao").mock(
        return_value=httpx.Response(200, json=_linha("5", quem="id-opaco-123"))
    )
    resposta = _dentro().post(
        reverse("parametros_da_fila_mudar"),
        {
            "chave": "rodadas_de_negociacao",
            "valor": "5",
            "motivo": "O piloto de papel mostrou que quatro nao bastam.",
        },
    )
    assert resposta.status_code == 302
    assert rota.called
    pedido = rota.calls[0].request
    import json as _json

    corpo = _json.loads(pedido.content)
    assert corpo["valor"] == "5"
    assert corpo["motivo"] == "O piloto de papel mostrou que quatro nao bastam."
    # O AUTOR é quem está logado, e não um campo que alguém digitou.
    assert corpo["quem"] == "id-opaco-123"
    # E é o crachá de ESCRITA que viaja, nunca o de leitura.
    assert pedido.headers["Authorization"] == "Bearer token-de-gravar"


@respx.mock
def test_gravar_deixa_linha_de_auditoria(db):
    respx.put(f"{PARAMETROS}/rodadas_de_negociacao").mock(
        return_value=httpx.Response(200, json=_linha("5"))
    )
    _dentro().post(
        reverse("parametros_da_fila_mudar"),
        {
            "chave": "rodadas_de_negociacao",
            "valor": "5",
            "motivo": "O piloto de papel mostrou que quatro nao bastam.",
        },
    )
    linha = Registro.objects.get()
    assert linha.acao == Registro.MUDAR_PARAMETRO
    assert linha.alvo == "rodadas_de_negociacao"
    assert linha.desfecho == Registro.OK
    assert linha.quem_email == DONO


@respx.mock
def test_a_recusa_da_celula_tambem_deixa_rastro(db):
    """A metade do rastro que só existe aqui.

    Quando a célula recusa, nada é escrito do outro lado (não há linha para
    carimbar). Sem esta linha, a tentativa de mexer na régua da fila não teria
    deixado rastro em lugar nenhum.
    """
    respx.get(PARAMETROS).mock(return_value=httpx.Response(200, json=RESPOSTA))
    respx.put(f"{PARAMETROS}/janela_inicio").mock(
        return_value=httpx.Response(
            400, json={"detail": "janela_inicio e uma hora do dia: use HH:MM"}
        )
    )
    resposta = _dentro().post(
        reverse("parametros_da_fila_mudar"),
        {
            "chave": "janela_inicio",
            "valor": "oito da manha",
            "motivo": "Queria escrever por extenso, para testar.",
        },
    )
    assert resposta.status_code == 422
    # A frase que a célula escreveu chega inteira ao mantenedor, e não uma
    # reescrita daqui que envelheceria calada.
    assert "use HH:MM" in resposta.content.decode()
    linha = Registro.objects.get()
    assert linha.acao == Registro.MUDAR_PARAMETRO
    assert linha.desfecho == Registro.RECUSADO_PELA_CELULA


@respx.mock
def test_motivo_vazio_nao_chega_a_celula(db):
    rota = respx.put(f"{PARAMETROS}/rodadas_de_negociacao")
    respx.get(PARAMETROS).mock(return_value=httpx.Response(200, json=RESPOSTA))
    resposta = _dentro().post(
        reverse("parametros_da_fila_mudar"),
        {"chave": "rodadas_de_negociacao", "valor": "5", "motivo": "   "},
    )
    assert resposta.status_code == 400
    assert not rota.called
    assert "escreva por que" in resposta.content.decode()


# ---------------------------------------------------------------------------
# 3. Os dois graus de crachá (`armadilhas/318`)
# ---------------------------------------------------------------------------


@respx.mock
def test_sem_grau_de_escrita_a_tela_ensina_o_passo_em_vez_de_dar_erro_cru(
    db, monkeypatch
):
    """O par tem o crachá de leitura, e só ele.

    A tela ABRE e mostra tudo (o mantenedor precisa dela justamente aí), e o
    botão de gravar responde em português dizendo qual roteiro rodar. Um 403 cru
    diante de um leigo é uma tela que não ensina nada.
    """
    monkeypatch.delenv("ENCOMENDAS_API_TOKEN_ESCRITA", raising=False)
    rota = respx.put(f"{PARAMETROS}/rodadas_de_negociacao")
    respx.get(PARAMETROS).mock(return_value=httpx.Response(200, json=RESPOSTA))
    resposta = _dentro().post(
        reverse("parametros_da_fila_mudar"),
        {
            "chave": "rodadas_de_negociacao",
            "valor": "5",
            "motivo": "O piloto de papel mostrou que quatro nao bastam.",
        },
    )
    assert resposta.status_code == 503
    # Nem chega a bater na porta: sem o crachá alto não há o que tentar.
    assert not rota.called
    corpo = resposta.content.decode()
    assert "provisionar-par-dos-parametros" in corpo
    assert "Nada foi mudado" in corpo
    # E o que está gravado continua na tela, inteiro.
    assert "Horas úteis que o aluno tem para responder" in corpo
    assert Registro.objects.get().desfecho == Registro.NAO_RESPONDEU


@respx.mock
def test_o_403_da_celula_vira_frase_que_ensina(db):
    """O crachá existe no env desta área e a célula não o aceita para gravar."""
    respx.get(PARAMETROS).mock(return_value=httpx.Response(200, json=RESPOSTA))
    respx.put(f"{PARAMETROS}/rodadas_de_negociacao").mock(
        return_value=httpx.Response(403, json={"detail": "grau insuficiente"})
    )
    resposta = _dentro().post(
        reverse("parametros_da_fila_mudar"),
        {
            "chave": "rodadas_de_negociacao",
            "valor": "5",
            "motivo": "O piloto de papel mostrou que quatro nao bastam.",
        },
    )
    assert resposta.status_code == 503
    corpo = resposta.content.decode()
    assert "crachá que está no servidor é o de LEITURA" in corpo
    assert "provisionar-par-dos-parametros" in corpo


# ---------------------------------------------------------------------------
# 4. Sem par, sem célula, sem crachá
# ---------------------------------------------------------------------------


@respx.mock
def test_sem_par_de_tokens_a_tela_abre_e_diz_o_que_falta(monkeypatch):
    monkeypatch.delenv("ENCOMENDAS_API_URL", raising=False)
    resposta = _dentro().get(reverse("parametros_da_fila"))
    assert resposta.status_code == 200
    assert (
        "Ainda não consigo falar com a Fila do Primeiro Dólar"
        in resposta.content.decode()
    )


@respx.mock
def test_celula_muda_nao_derruba_a_tela():
    respx.get(PARAMETROS).mock(return_value=httpx.Response(503))
    resposta = _dentro().get(reverse("parametros_da_fila"))
    assert resposta.status_code == 200
    assert "Ainda não consigo falar" in resposta.content.decode()


@respx.mock
@pytest.mark.django_db
def test_sem_cracha_ninguem_muda_numero_nenhum():
    """A ESCRITA é a que mais importa: ela muda o que a plataforma inteira obedece."""
    respx.get(SESSAO).mock(
        return_value=httpx.Response(200, json={"autenticado": False})
    )
    respx.get(PARAMETROS).mock(return_value=httpx.Response(200, json=RESPOSTA))
    gesto = respx.put(url__startswith=f"{PARAMETROS}/")

    resposta = Client().post(
        reverse("parametros_da_fila_mudar"),
        {
            "chave": "rodadas_de_negociacao",
            "valor": "5",
            "motivo": "O piloto de papel mostrou que quatro nao bastam.",
        },
    )

    assert resposta.status_code in (302, 403)
    assert not gesto.called, "a tela chamou as encomendas sem crachá"
    assert not Registro.objects.exists()


@respx.mock
@pytest.mark.django_db
def test_sem_cracha_a_tela_nem_abre():
    respx.get(SESSAO).mock(
        return_value=httpx.Response(200, json={"autenticado": False})
    )
    leitura = respx.get(PARAMETROS)
    resposta = Client().get(reverse("parametros_da_fila"))
    assert resposta.status_code in (302, 403)
    assert not leitura.called, "a tela leu as encomendas sem crachá"
