"""A tela `/admin/escola/jornadas/` — as sequências de mensagens da escola.

O que estes guardas protegem, e cada um deles é uma promessa que já custou
alguma coisa a este projeto ou ao mantenedor:

1. **A METADE QUE FAZ A TELA VALER: o que foi BARRADO, e por quê.** É a parte
   mais fácil de cortar por engano, porque a tela "funciona" sem ela. Sem essa
   metade, *"por que o aluno X não recebeu?"* fica sem resposta e o mantenedor
   olha para o silêncio.
2. **O vocabulário é de leigo.** "Barrada pela régua", nunca "rate limit
   exceeded". Um guarda mede isso pelo texto que sai na tela.
3. **Publicar diz, na hora, que quem já está no meio termina com o texto
   antigo** — com o NÚMERO da versão que nasceu. Sem essa frase ele troca a
   frase, vê um aluno receber a antiga, e conclui que a correção não pegou.
4. **Desligar diz quantas pessoas continuam recebendo.** Desligar significa que
   ninguém NOVO entra; sugerir que tudo parou seria mentira.
5. **As três recusas do contrato viram três frases diferentes**, e nenhuma é um
   erro cru: sem versão publicada (409), publicação concorrente (409) e par sem
   o grau de escrita (403).
6. **Esta tela não guarda nada.** Tudo é calculado da porta, pelo contrato
   congelado, nunca do banco da outra célula nem de uma cópia local.
7. **Nada de dado pessoal.** A `mensageria` manda só o id opaco, e a tela não
   inventa um nome que não tem de onde vir.
8. **Fail-OPEN na leitura, fail-CLOSED na escrita.** Sem o par de tokens a tela
   abre dizendo o que falta; ela nunca diz "salvei" sem ter salvado.
9. **A porta continua sendo a porta.** Sem crachá, nada disto responde.
"""

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.auditoria.models import Registro

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
CATALOGO = "http://catalogo:8000/api/catalogo"
MENSAGERIA = "http://mensageria:8000/api/mensageria"
JORNADAS = f"{MENSAGERIA}/jornadas"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"
DONO_ID = "id-opaco-123"
DE_FORA = "estranho@exemplo.com"
SITE_ID = "site-mesh"
INSCRICAO = "11111111-2222-3333-4444-555555555555"


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    monkeypatch.setenv("CATALOGO_API_URL", CATALOGO)
    monkeypatch.setenv("TOKEN_CATALOGO", "token-do-par-admin-catalogo")
    monkeypatch.setenv("MENSAGERIA_API_URL", MENSAGERIA)
    monkeypatch.setenv("MENSAGERIA_API_TOKEN", "token-do-par-admin-mensageria")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


def _pessoa(email: str) -> dict:
    return {
        "autenticado": True,
        "id": DONO_ID,
        "nome_exibido": "Fulano",
        "papel": None,
        "email": email,
    }


def _com_cookie() -> Client:
    c = Client()
    c.defaults["HTTP_COOKIE"] = COOKIE
    return c


def _dentro(email: str = DONO) -> Client:
    respx.get(SESSAO).mock(return_value=httpx.Response(200, json=_pessoa(email)))
    return _com_cookie()


def _mock_site():
    return respx.get(f"{CATALOGO}/sites/by-host/testserver").mock(
        return_value=httpx.Response(200, json={"id": SITE_ID, "host": "testserver"})
    )


def _resumo(*, ativa=False, versao=3, versoes=3, slug="boas-vindas"):
    return {
        "slug": slug,
        "gatilho": "identidade.pessoa-cadastrada",
        "ativa": ativa,
        "criada_em": "2026-09-01T10:00:00+00:00",
        "versoes": versoes,
        "versao_publicada": (
            None
            if versao is None
            else {"numero": versao, "publicada_em": "2026-09-02T10:00:00+00:00"}
        ),
    }


def _mock_lista(**kwargs):
    return respx.get(JORNADAS).mock(
        return_value=httpx.Response(
            200, json={"site_id": SITE_ID, "jornadas": [_resumo(**kwargs)]}
        )
    )


def _detalhe(numero=3):
    return {
        "site_id": SITE_ID,
        "slug": "boas-vindas",
        "gatilho": "identidade.pessoa-cadastrada",
        "ativa": True,
        "versao": {"numero": numero, "publicada_em": "2026-09-02T10:00:00+00:00"},
        "publicada": True,
        "passos": [
            {
                "passo_id": "aaaaaaaa-1111-2222-3333-444444444444",
                "ordem": 1,
                "atraso_segundos": 0,
                "janela_segundos": None,
                "assunto": "boas-vindas",
                "classe": "relacional",
                "canais": ["sino"],
                "condicao_slug": "",
                "textos": [
                    {
                        "idioma": "pt-br",
                        "assunto_visivel": "Que bom ter você aqui",
                        "corpo": "A sua conta está pronta.",
                    }
                ],
            },
            {
                "passo_id": "bbbbbbbb-1111-2222-3333-444444444444",
                "ordem": 2,
                "atraso_segundos": 172800,
                "janela_segundos": None,
                "assunto": "primeira-aula",
                "classe": "engajamento",
                "canais": ["sino", "email"],
                "condicao_slug": "ainda-nao-entrou-em-aula",
                "textos": [
                    {
                        "idioma": "pt-br",
                        "assunto_visivel": "A sua primeira aula",
                        "corpo": "Ela leva quinze minutos.",
                    }
                ],
            },
        ],
    }


def _mock_detalhe(numero=3):
    return respx.get(f"{JORNADAS}/boas-vindas").mock(
        return_value=httpx.Response(200, json=_detalhe(numero))
    )


def _mock_inscricoes(estado="andando", versao=3, total=1):
    return respx.get(f"{JORNADAS}/boas-vindas/inscricoes").mock(
        return_value=httpx.Response(
            200,
            json={
                "slug": "boas-vindas",
                "total": total,
                "inscricoes": [
                    {
                        "inscricao_id": INSCRICAO,
                        "destinatario_id": "pessoa-opaca-987",
                        "estado": estado,
                        "passo_atual": 2,
                        "versao_numero": versao,
                        "ancora_em": "2026-09-03T09:00:00+00:00",
                        "proximo_em": "2026-09-05T09:00:00+00:00",
                        "motivo_de_saida": "",
                        "criada_em": "2026-09-03T09:00:00+00:00",
                    }
                ],
            },
        )
    )


def _mock_entregas(entregas):
    return respx.get(f"{MENSAGERIA}/inscricoes/{INSCRICAO}/entregas").mock(
        return_value=httpx.Response(
            200,
            json={
                "inscricao_id": INSCRICAO,
                "estado": "andando",
                "entregas": entregas,
            },
        )
    )


def _entrega(resultado, motivo, *, canal="email", ordem=2, reagendado=None):
    return {
        "passo_id": "bbbbbbbb-1111-2222-3333-444444444444",
        "ordem": ordem,
        "canal": canal,
        "resultado": resultado,
        "motivo": motivo,
        "decidida_em": "2026-09-05T09:00:00+00:00",
        "previsto_para": "2026-09-05T09:00:00+00:00",
        "reagendado_para": reagendado,
        "enviado_em": None,
        "event_id": None,
    }


def _texto(resposta) -> str:
    return resposta.content.decode()


def _dentro_de_boas_vindas(cliente, **params):
    return cliente.get(
        reverse("escola_jornada_sequencia", args=["boas-vindas"]), params
    )


# ---------------------------------------------------------------------------
# 1. A LISTA
# ---------------------------------------------------------------------------
@pytest.mark.django_db
@respx.mock
def test_a_lista_mostra_a_sequencia_em_portugues():
    """O slug e o gatilho viram frase de gente. Nenhum dos dois sai cru."""
    _mock_site()
    _mock_lista(ativa=True)

    html = _texto(_dentro().get(reverse("escola_jornadas")))

    assert "Boas-vindas" in html
    assert "quando alguém termina o cadastro no site" in html
    assert "Ligada" in html
    assert "identidade.pessoa-cadastrada" not in html


@pytest.mark.django_db
@respx.mock
def test_sequencia_sem_texto_diz_que_nao_pode_ser_ligada():
    """`versao_publicada: null` é o estado NORMAL de uma recém-semeada, e a
    tela precisa dizer isso sem alarme — e dizer por que ligar não adianta."""
    _mock_site()
    _mock_lista(versao=None, versoes=0)

    html = _texto(_dentro().get(reverse("escola_jornadas")))

    assert "Ainda não tem nenhuma mensagem escrita" in html
    assert "não escreveria para ninguém" in html


@pytest.mark.django_db
@respx.mock
def test_sem_o_par_de_tokens_a_tela_abre_e_diz_o_que_falta():
    """Fail-OPEN na leitura. Uma tela de operação que não abre é inútil
    justamente quando você precisa dela — e uma tela VAZIA seria pior: diria
    "esta escola não tem sequência nenhuma" e o mandaria procurar o problema no
    lugar errado."""
    _mock_site()
    respx.get(JORNADAS).mock(return_value=httpx.Response(401, json={"detail": "nao"}))

    resposta = _dentro().get(reverse("escola_jornadas"))
    html = _texto(resposta)

    assert resposta.status_code == 503
    assert "Ainda não consigo falar com o motor das mensagens" in html
    assert "Nada do que está no ar mudou" in html
    # A prova de que ela não caiu numa tela vazia disfarçada de resposta.
    assert "Nenhuma sequência está ligada" not in html


# ---------------------------------------------------------------------------
# 2. O INTERRUPTOR — a primeira decisão do mantenedor no Rito
# ---------------------------------------------------------------------------
@pytest.mark.django_db
@respx.mock
def test_ligar_uma_sequencia_grava_e_deixa_rastro():
    _mock_site()
    _mock_lista(ativa=True)
    respx.post(f"{JORNADAS}/boas-vindas/ativa").mock(
        return_value=httpx.Response(
            200,
            json={
                "slug": "boas-vindas",
                "ativa": True,
                "mudou": True,
                "inscricoes_andando": 0,
                "versao_publicada": {"numero": 3, "publicada_em": None},
            },
        )
    )

    resposta = _dentro().post(
        reverse("escola_jornada_ligar"), {"slug": "boas-vindas", "ativa": "1"}
    )

    assert resposta.status_code == 302
    assert "recado=ligada" in resposta["Location"]
    linha = Registro.objects.get()
    assert linha.acao == Registro.LIGAR_SEQUENCIA
    assert linha.alvo == "boas-vindas"
    assert linha.desfecho == Registro.OK


@pytest.mark.django_db
@respx.mock
def test_desligar_diz_quantas_pessoas_continuam_recebendo():
    """A DECISÃO DO RITO, medida. Desligar significa que ninguém NOVO entra, e
    quem já está no meio termina o que começou. Uma tela que dissesse só
    "desligada" sugeriria que tudo parou, e isso é mentira."""
    _mock_site()
    _mock_lista(ativa=False)
    respx.post(f"{JORNADAS}/boas-vindas/ativa").mock(
        return_value=httpx.Response(
            200,
            json={
                "slug": "boas-vindas",
                "ativa": False,
                "mudou": True,
                "inscricoes_andando": 7,
                "versao_publicada": {"numero": 3, "publicada_em": None},
            },
        )
    )

    cliente = _dentro()
    resposta = cliente.post(
        reverse("escola_jornada_ligar"), {"slug": "boas-vindas", "ativa": "0"}
    )
    html = _texto(cliente.get(resposta["Location"]))

    assert "ninguém NOVO entra" in html
    assert "7 pessoas" in html
    assert "continua recebendo até o fim" in html


@pytest.mark.django_db
@respx.mock
def test_ligar_o_que_ja_estava_ligado_nao_finge_novidade():
    """`mudou: false` é resposta legítima, e a tela não pode celebrar por ela.
    Sem esta distinção, um duplo clique diria "liguei" duas vezes."""
    _mock_site()
    _mock_lista(ativa=True)
    respx.post(f"{JORNADAS}/boas-vindas/ativa").mock(
        return_value=httpx.Response(
            200,
            json={
                "slug": "boas-vindas",
                "ativa": True,
                "mudou": False,
                "inscricoes_andando": 2,
                "versao_publicada": {"numero": 3, "publicada_em": None},
            },
        )
    )

    cliente = _dentro()
    resposta = cliente.post(
        reverse("escola_jornada_ligar"), {"slug": "boas-vindas", "ativa": "1"}
    )
    html = _texto(cliente.get(resposta["Location"]))

    assert "Ela já estava ligada" in html
    assert "Sequência ligada." not in html


@pytest.mark.django_db
@respx.mock
def test_ligar_sem_versao_publicada_explica_em_portugues():
    """O 409 do contrato vira uma frase que diz o que fazer, e nunca um erro
    cru: ligada sem texto, a sequência apareceria como "no ar" e não escreveria
    para ninguém."""
    _mock_site()
    _mock_lista(versao=None, versoes=0)
    respx.post(f"{JORNADAS}/boas-vindas/ativa").mock(
        return_value=httpx.Response(409, json={"detail": "sem versao"})
    )

    resposta = _dentro().post(
        reverse("escola_jornada_ligar"), {"slug": "boas-vindas", "ativa": "1"}
    )
    html = _texto(resposta)

    assert resposta.status_code == 422
    assert "Não liguei, e o motivo é bom" in html
    assert "não tem mensagem nenhuma escrita para mandar" in html
    assert "Abra a sequência, escreva o texto do primeiro passo" in html
    assert "409" not in html
    assert Registro.objects.get().desfecho == Registro.RECUSADO_PELA_CELULA


@pytest.mark.django_db
@respx.mock
def test_par_so_de_leitura_diz_que_falta_a_permissao_de_escrita():
    """O 403 é o modo de falha que os DOIS conjuntos de token existem para
    tornar diagnosticável: a tela lê tudo certo e só a escrita recusa. Achatar
    isso em "não respondeu" mandaria o mantenedor procurar um problema de rede
    que não existe."""
    _mock_site()
    _mock_lista()
    respx.post(f"{JORNADAS}/boas-vindas/ativa").mock(
        return_value=httpx.Response(403, json={"detail": "sem grau"})
    )

    html = _texto(
        _dentro().post(
            reverse("escola_jornada_ligar"), {"slug": "boas-vindas", "ativa": "1"}
        )
    )

    assert "Consigo LER as sequências, mas não consigo mudá-las" in html
    assert "permissão de escrita" in html
    assert "Nada foi alterado" in html


# ---------------------------------------------------------------------------
# 3. UMA SEQUÊNCIA POR DENTRO, E O TEXTO EDITÁVEL
# ---------------------------------------------------------------------------
@pytest.mark.django_db
@respx.mock
def test_a_tela_de_dentro_mostra_os_passos_traduzidos():
    _mock_site()
    _mock_lista(ativa=True)
    _mock_detalhe()
    _mock_inscricoes()

    html = _texto(_dentro_de_boas_vindas(_dentro()))

    assert "Na hora em que a pessoa entra na sequência." in html
    assert "2 dias depois de entrar." in html
    assert "o sininho dentro do site" in html
    assert "Só sai para quem ainda não entrou em nenhuma aula." in html
    assert "De incentivo" in html
    # O cabeçalho do cartão é a frase que o ALUNO lê, e nunca o `assunto`, que é
    # vocabulário fechado de máquina (`jornada.passo`) e não diz nada a ninguém.
    assert "Mensagem 1: Que bom ter você aqui" in html
    assert "Mensagem 1: boas-vindas" not in html
    # Nenhum slug cru vaza para a tela do mantenedor.
    assert "ainda-nao-entrou-em-aula" not in html
    assert "engajamento" not in html


@pytest.mark.django_db
@respx.mock
def test_publicar_diz_o_numero_da_versao_e_quem_termina_com_o_texto_antigo():
    """A SEGUNDA DECISÃO DO RITO, medida, e é o coração desta tela.

    Sem esta frase o mantenedor troca o texto, vê um aluno receber o antigo, e
    conclui que a correção não pegou. O número vem da própria porta.
    """
    _mock_site()
    _mock_lista(ativa=True, versao=4, versoes=4)
    respx.post(f"{JORNADAS}/boas-vindas/textos").mock(
        return_value=httpx.Response(
            200,
            json={
                "slug": "boas-vindas",
                "versao": 4,
                "publicada_em": "2026-09-04T12:00:00+00:00",
                "passo_id": "aaaaaaaa-1111-2222-3333-444444444444",
                "passos": 3,
            },
        )
    )
    _mock_detalhe(4)
    _mock_inscricoes(versao=4)

    cliente = _dentro()
    resposta = cliente.post(
        reverse("escola_jornada_publicar"),
        {
            "slug": "boas-vindas",
            "ordem": "1",
            "idioma": "pt-br",
            "assunto_visivel": "Que bom ter você aqui",
            "corpo": "A sua conta está pronta.",
            "versao_base": "3",
        },
    )
    assert resposta.status_code == 302
    html = _texto(cliente.get(resposta["Location"]))

    assert "Texto salvo, e ele nasceu como a versão 4." in html
    assert "termina com o texto" in html
    assert "vale para quem entrar a partir de agora" in html
    linha = Registro.objects.get()
    assert linha.acao == Registro.PUBLICAR_TEXTO
    assert "versao 4" in linha.detalhe


@pytest.mark.django_db
@respx.mock
def test_a_trava_contra_sobrescrever_quem_publicou_primeiro():
    """O 409 do `versao_base` NÃO pode virar "salvei". A tela recusa, explica, e
    manda recarregar — e o código da resposta prova que ela não fingiu."""
    _mock_site()
    _mock_lista(ativa=True)
    respx.post(f"{JORNADAS}/boas-vindas/textos").mock(
        return_value=httpx.Response(409, json={"detail": "outra publicacao"})
    )
    _mock_detalhe()
    _mock_inscricoes()

    resposta = _dentro().post(
        reverse("escola_jornada_publicar"),
        {
            "slug": "boas-vindas",
            "ordem": "1",
            "idioma": "pt-br",
            "assunto_visivel": "Outro título",
            "corpo": "Outro corpo",
            "versao_base": "2",
        },
    )
    html = _texto(resposta)

    assert resposta.status_code == 409
    assert "Não salvei, e o motivo é bom" in html
    assert "apagaria em silêncio" in html
    # O que a tela mostra é o que ESTÁ GRAVADO, nunca o texto recusado: uma
    # página que exibisse o recusado discordaria do motor.
    assert "Que bom ter você aqui" in html
    assert "Outro título" not in html


@pytest.mark.django_db
@respx.mock
def test_versao_antiga_nao_oferece_o_formulario_de_edicao():
    """A armadilha que esta tela evita por construção.

    Publicar copia a versão publicada CORRENTE, não a que está na tela. Oferecer
    o campo em cima de uma versão antiga faria o mantenedor achar que estava
    corrigindo AQUELA, quando estaria escrevendo por cima da atual.
    """
    _mock_site()
    _mock_lista(ativa=True, versao=4, versoes=4)
    respx.get(f"{JORNADAS}/boas-vindas", params={"versao": "2"}).mock(
        return_value=httpx.Response(200, json=_detalhe(2))
    )
    _mock_inscricoes(versao=2)

    html = _texto(_dentro_de_boas_vindas(_dentro(), ver_versao="2"))

    assert "Você está vendo a versão 2" in html
    assert 'name="assunto_visivel"' not in html
    assert "Ver a versão 4, que está valendo" in html
    # O texto daquela versão continua LEGÍVEL: é o que aquelas pessoas ainda
    # vão receber, e escondê-lo derrotaria o motivo de a tela abri-la.
    assert "A sua conta está pronta." in html


# ---------------------------------------------------------------------------
# 4. A METADE QUE FAZ A TELA VALER: O QUE FOI BARRADO
# ---------------------------------------------------------------------------
@pytest.mark.django_db
@respx.mock
def test_barrada_pela_regua_aparece_com_o_motivo_que_a_regua_escreveu():
    """O guarda mais importante deste arquivo.

    Sem esta metade, "por que o aluno X não recebeu?" fica sem resposta e o
    mantenedor olha para o silêncio. O RÓTULO é traduzido aqui (vocabulário
    fechado do contrato); o MOTIVO sai verbatim, porque é texto livre da régua.
    """
    _mock_site()
    _mock_lista(ativa=True)
    _mock_detalhe()
    _mock_inscricoes()
    _mock_entregas(
        [
            _entrega(
                "barrada_pela_regua",
                "ja recebeu 1 hoje (teto de 1 por dia)",
                reagendado="2026-09-06T09:00:00+00:00",
            )
        ]
    )

    html = _texto(_dentro_de_boas_vindas(_dentro(), inscricao=INSCRICAO))

    assert "Barrada pela régua" in html
    assert "ja recebeu 1 hoje (teto de 1 por dia)" in html
    assert "O que a régua anotou" in html
    assert "Foi remarcada para 06/09/2026" in html
    assert "Barrada não é perdida" in html
    # "mensagem" não pluraliza acrescentando letra. O filtro com sufixo escrevia
    # "1 mensagemns", e só a prévia renderizada mostrou isso.
    assert "mensagemns" not in html
    assert "<b>1 mensagem</b>" in html
    assert "foi barrada," in html


@pytest.mark.django_db
@respx.mock
def test_a_tela_nunca_fala_a_lingua_da_maquina():
    """Ele é leigo. "Barrada pela régua", nunca "rate limit exceeded"."""
    _mock_site()
    _mock_lista(ativa=True)
    _mock_detalhe()
    _mock_inscricoes()
    _mock_entregas(
        [
            _entrega(
                "barrada_pela_regua", "fora da janela (22:14; vale das 08:00 as 20:00)"
            ),
            _entrega(
                "barrada_por_preferencia",
                "a pessoa silenciou engajamento no canal email",
            ),
        ]
    )

    html = _texto(_dentro_de_boas_vindas(_dentro(), inscricao=INSCRICAO))

    assert "Barrada por escolha da pessoa" in html
    assert "pediu para não receber este tipo de mensagem neste canal" in html
    # O vocabulário FECHADO do contrato nunca chega cru à tela dele.
    for palavra in ("barrada_pela_regua", "barrada_por_preferencia", "rate limit"):
        assert palavra not in html


@pytest.mark.django_db
@respx.mock
def test_uma_linha_por_canal_porque_sao_resultados_independentes():
    """Sino entregue e e-mail barrado no MESMO passo são dois fatos. Uma tela
    que mostrasse um só faria o mantenedor concluir a coisa errada sobre o
    outro."""
    _mock_site()
    _mock_lista(ativa=True)
    _mock_detalhe()
    _mock_inscricoes()
    _mock_entregas(
        [
            _entrega("enviada", "", canal="sino"),
            _entrega(
                "barrada_pela_regua",
                "ja recebeu 1 hoje (teto de 1 por dia)",
                canal="email",
            ),
        ]
    )

    html = _texto(_dentro_de_boas_vindas(_dentro(), inscricao=INSCRICAO))

    # A preposição contrai com o artigo, e é por isso que existe um segundo mapa
    # para o mesmo vocabulário fechado (`CANAL_POR`): "por o sininho" não é
    # português, e a prévia renderizada com dados reais é quem apanhou isso.
    assert "Mensagem 2, pelo sininho dentro do site" in html
    assert "Mensagem 2, por e-mail" in html
    assert "Enviada" in html
    assert "Barrada pela régua" in html


@pytest.mark.django_db
@respx.mock
def test_sem_ninguem_escolhido_a_tela_ensina_onde_perguntar():
    """A pergunta "por que fulano não recebeu?" precisa ter caminho visível.
    Sem este convite, a metade mais valiosa da tela ficaria escondida atrás de
    um clique que ninguém saberia dar."""
    _mock_site()
    _mock_lista(ativa=True)
    _mock_detalhe()
    _mock_inscricoes()

    html = _texto(_dentro_de_boas_vindas(_dentro()))

    assert "Por que alguém não recebeu?" in html
    assert "Ver o que saiu, e o que não saiu, para esta pessoa" in html


# ---------------------------------------------------------------------------
# 5. AS PROMESSAS QUE ATRAVESSAM A TELA
# ---------------------------------------------------------------------------
@pytest.mark.django_db
@respx.mock
def test_nenhum_dado_pessoal_chega_a_tela_nem_por_acidente():
    """A `mensageria` não guarda e não manda nome, e-mail nem telefone
    (invariante 1 do contrato). A tela mostra o id opaco como ele é, em vez de
    prometer um nome que não tem de onde vir.

    O guarda mede o caso PERIGOSO, e não o feliz: a porta manda campos a mais
    (como mandaria no dia em que alguém os acrescentasse do outro lado) e a tela
    tem de continuar mostrando só o id. Um teste que apenas conferisse a
    presença do id passaria por igual se esta tela desenhasse o que viesse.

    E ele mede no lugar CERTO. A primeira versão deste guarda olhava só o HTML,
    e a mutação que enfiava `{{ i.nome }}` no molde deixava-o VERDE: o que
    protege de verdade não é o molde, é a lista fechada de campos que
    `_linha_de_inscricao` monta — o que não estiver nela não chega ao template
    para ser desenhado. Um guarda que aponta para a peça errada não mede a
    promessa, mede o acaso.
    """
    from apps.core.sequencias import _linha_de_inscricao

    linha = _linha_de_inscricao(
        {
            "inscricao_id": INSCRICAO,
            "destinatario_id": "pessoa-opaca-987",
            "estado": "andando",
            "passo_atual": 2,
            "versao_numero": 3,
            "ancora_em": "2026-09-03T09:00:00+00:00",
            "proximo_em": "2026-09-05T09:00:00+00:00",
            "motivo_de_saida": "",
            "criada_em": "2026-09-03T09:00:00+00:00",
            "nome": "Maria de Tal",
            "email": "maria@exemplo.com",
            "whatsapp": "+5511999999999",
        }
    )
    assert set(linha) == {
        "inscricao_id",
        "destinatario_id",
        "estado",
        "estado_rotulo",
        "estado_explicacao",
        "passo_atual",
        "versao_numero",
        "proximo_em",
        "motivo_de_saida",
        "criada_em",
    }, (
        "a lista de campos que chegam ao molde deixou de ser fechada. Campo "
        "novo aqui é campo que a tela pode desenhar sem ninguém decidir, e "
        f"nesta porta isso é dado pessoal: {sorted(linha)}"
    )

    _mock_site()
    _mock_lista(ativa=True)
    _mock_detalhe()
    respx.get(f"{JORNADAS}/boas-vindas/inscricoes").mock(
        return_value=httpx.Response(
            200,
            json={
                "slug": "boas-vindas",
                "total": 1,
                "inscricoes": [
                    {
                        "inscricao_id": INSCRICAO,
                        "destinatario_id": "pessoa-opaca-987",
                        "estado": "andando",
                        "passo_atual": 2,
                        "versao_numero": 3,
                        "ancora_em": "2026-09-03T09:00:00+00:00",
                        "proximo_em": "2026-09-05T09:00:00+00:00",
                        "motivo_de_saida": "",
                        "criada_em": "2026-09-03T09:00:00+00:00",
                        "nome": "Maria de Tal",
                        "email": "maria@exemplo.com",
                        "whatsapp": "+5511999999999",
                    }
                ],
            },
        )
    )

    html = _texto(_dentro_de_boas_vindas(_dentro()))

    assert "pessoa-opaca-987" in html
    for vazamento in ("Maria de Tal", "maria@exemplo.com", "+5511999999999"):
        assert vazamento not in html


@pytest.mark.django_db
@respx.mock
def test_toda_chamada_leva_o_site_id():
    """CONSTITUICAO Lei 9. Sem `site_id` a porta responde 422, e chutar um site
    mostraria as sequências de outro domínio."""
    _mock_site()
    lista = _mock_lista(ativa=True)
    detalhe = _mock_detalhe()
    inscricoes = _mock_inscricoes()
    entregas = _mock_entregas([_entrega("enviada", "", canal="sino")])

    _dentro_de_boas_vindas(_dentro(), inscricao=INSCRICAO)

    for rota in (lista, detalhe, inscricoes, entregas):
        assert rota.called
        assert rota.calls.last.request.url.params["site_id"] == SITE_ID


@pytest.mark.django_db
@respx.mock
def test_a_tela_nao_guarda_nada_desta_celula():
    """Lei anti-duplicação do CLAUDE.md, medida onde ela é violável.

    Esta célula não pode ganhar uma tabela de sequências: seria o mesmo fato em
    dois lugares, e no dia em que os dois discordassem a tela mostraria um texto
    e o aluno receberia outro. As únicas tabelas daqui são a auditoria e a lista
    de administradores.
    """
    from django.apps import apps

    nomes = {m._meta.db_table for m in apps.get_models()}
    for proibida in ("jornada", "sequencia", "passo", "inscricao", "entrega"):
        assert not any(proibida in n for n in nomes), (
            f"apareceu uma tabela com '{proibida}' nesta célula: o dado das "
            f"sequências mora na `mensageria`, e cópia aqui é a lei "
            f"anti-duplicação sendo quebrada. Tabelas: {sorted(nomes)}"
        )


@pytest.mark.django_db
@respx.mock
def test_os_gestos_recusam_get():
    """Decisão que se aplica por GET é decisão que um pré-carregador de link, um
    antivírus corporativo ou um crawler autenticado tomam sozinhos — e uma
    destas duas muda o que sai para alunos de verdade."""
    cliente = _dentro()
    for nome in ("escola_jornada_ligar", "escola_jornada_publicar"):
        assert cliente.get(reverse(nome)).status_code == 405


@pytest.mark.django_db
@respx.mock
def test_quem_a_porta_recusa_nao_ve_sequencia_nenhuma():
    """A porta é a porta. E o 404 aqui NÃO é vacuamente verde: a MESMA rota, no
    MESMO teste, responde 200 para quem tem crachá. Caminho inexistente também
    dá 404, e sem a metade de cima este guarda passaria por acidente."""
    _mock_site()
    _mock_lista(ativa=True)
    respx.get(SESSAO).mock(
        side_effect=[
            httpx.Response(200, json=_pessoa(DONO)),
            httpx.Response(200, json=_pessoa(DE_FORA)),
        ]
    )
    cliente = _com_cookie()

    assert cliente.get(reverse("escola_jornadas")).status_code == 200
    assert cliente.get(reverse("escola_jornadas")).status_code == 404


@pytest.mark.django_db
@respx.mock
def test_sequencia_que_nao_existe_diz_isso_em_vez_de_quebrar():
    """E este 404 também não é vacuamente verde: a mesma rota, com um slug que
    EXISTE, responde 200 duas linhas acima. O que muda é só o slug pedido."""
    _mock_site()
    _mock_lista(ativa=True)
    _mock_detalhe()
    _mock_inscricoes()

    cliente = _dentro()
    assert _dentro_de_boas_vindas(cliente).status_code == 200

    resposta = cliente.get(reverse("escola_jornada_sequencia", args=["nao-existe"]))
    assert resposta.status_code == 404
    assert "Essa sequência não existe" in _texto(resposta)
