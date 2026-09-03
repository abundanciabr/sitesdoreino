"""A repetição do envio da imagem — e, sobretudo, quando ela NÃO acontece.

Este arquivo existe porque repetição automática é a peça que mais facilmente
vira arma nesta casa. A `armadilhas/209` é o registro do dia em que virou: uma
vacina de retry declarou "falha PERMANENTE" sobre uma VPS viva e o deploy
DESISTIU de uma entrega que teria subido na tentativa seguinte.

As três decisões travadas aqui, e nenhuma delas seria pega por um teste que só
perguntasse "ele repete?":

1. **Resposta definitiva para na PRIMEIRA.** O registro dizendo `denied` é um
   fato, não um soluço. Repetir três vezes trocaria um diagnóstico certo por
   um vermelho com cara de problema de rede.
2. **Silêncio repete.** `unknown blob` foi o caso real do PR #897: a imagem
   construída, o upload morto no meio, e a MESMA imagem subindo na repetição.
3. **O que o arquivo não reconhece repete, e nunca vira "permanente".** É a
   209 ao pé da letra: não saber não pode virar veredito.

E o vermelho continua vermelho: esgotadas as tentativas, o exit é 1. Uma vacina
que engolisse a falha seria o falso-verde padrão 1 da RETROSPECTIVA-FASE-D.
"""

import sys
from pathlib import Path

import pytest

CI = Path(__file__).resolve().parents[1]
RAIZ = CI.parent
sys.path.insert(0, str(CI))

from enviar_a_imagem import (  # noqa: E402
    DEFINITIVO,
    DESCONHECIDO,
    ENGASGO,
    TENTATIVAS,
    classificar,
    enviar,
    main,
)

TAG = "ghcr.io/abundanciabr/plataforma-funil:abc123"


class Registro:
    """Um registro de mentira, que falha as `quantas` primeiras vezes.

    Guarda as chamadas para o teste poder medir QUANTAS tentativas houve — é
    isso, e não o valor de retorno, que separa "parou na hora" de "repetiu".
    """

    def __init__(self, saida_de_erro: str, quantas: int):
        self.saida_de_erro = saida_de_erro
        self.quantas = quantas
        self.chamadas = 0

    def __call__(self, tag: str):
        self.chamadas += 1
        if self.chamadas <= self.quantas:
            return 1, self.saida_de_erro
        return 0, "abc123: digest: sha256:... size: 1234"


@pytest.fixture
def sem_pausa():
    """As pausas são reais no deploy e irrelevantes aqui.

    Sem isto a suíte esperaria 40 s por caso — e teste lento é teste que
    alguém acaba desligando.
    """
    return lambda _segundos: None


# ------------------------------------------- 1. o que NÃO se repete


ERROS_DEFINITIVOS = [
    ("denied: permission_denied: write_package", "credencial sem permissão"),
    ("unauthorized: authentication required", "token vencido"),
    ("manifest unknown", "tag que não existe"),
    ("no space left on device", "disco cheio do runner"),
]


@pytest.mark.parametrize("saida,motivo", ERROS_DEFINITIVOS)
def test_resposta_definitiva_para_na_primeira_tentativa(saida, motivo, sem_pausa):
    """O registro respondeu "não". Isso é diagnóstico, e diagnóstico não se repete.

    A medição que importa é `chamadas == 1`: o valor de retorno seria `False`
    de qualquer jeito depois de três tentativas, e um teste que olhasse só ele
    passaria com a vacina gastando 40 s para chegar ao mesmo lugar.
    """
    registro = Registro(saida, quantas=TENTATIVAS + 5)
    assert enviar(TAG, empurrar=registro, dormir=sem_pausa) is False, motivo
    assert registro.chamadas == 1, (
        f"{motivo}: o registro deu uma resposta clara e a vacina repetiu assim "
        f"mesmo — isso troca um diagnóstico certo por um palpite de rede"
    )


def test_uma_recusa_no_meio_do_ruido_de_rede_continua_sendo_recusa(sem_pausa):
    """A ordem da classificação, medida.

    Uma saída de `docker push` traz várias linhas. Se um `denied` vier junto de
    um `i/o timeout`, quem vence é a resposta definitiva — senão uma credencial
    errada sairia com cara de soluço e alguém pediria rerun para sempre.
    """
    saida = (
        "3cf536b3e643: Retrying in 2 seconds\ni/o timeout\ndenied: permission_denied"
    )
    assert classificar(saida) == DEFINITIVO
    registro = Registro(saida, quantas=TENTATIVAS + 5)
    assert enviar(TAG, empurrar=registro, dormir=sem_pausa) is False
    assert registro.chamadas == 1


# ------------------------------------------- 2. o que se repete


def test_o_unknown_blob_do_pr_897_sobe_na_repeticao(sem_pausa):
    """O caso REAL que originou este arquivo, reproduzido.

    Deploy do PR #897, 02/09/2026: imagem construída e nomeada, `docker push`
    morto no meio com `unknown blob`, e a MESMA imagem subindo na repetição
    sem uma vírgula de código mudar.
    """
    registro = Registro("5f70bf18a086: Pushing\nunknown blob", quantas=1)
    assert enviar(TAG, empurrar=registro, dormir=sem_pausa) is True
    assert registro.chamadas == 2, "devia ter subido na segunda"


@pytest.mark.parametrize(
    "saida",
    [
        "unknown blob",
        "blob upload unknown",
        "received unexpected HTTP status: 500 Internal Server Error",
        "502 Bad Gateway",
        "net/http: TLS handshake timeout",
        "read tcp: connection reset by peer",
        "unexpected EOF",
    ],
)
def test_o_silencio_do_registro_e_engasgo_e_nao_diagnostico(saida):
    assert classificar(saida) == ENGASGO


# --------------------------- 3. não saber nunca vira veredito (armadilhas/209)


def test_assinatura_desconhecida_repete_em_vez_de_desistir(sem_pausa):
    """A 209 ao pé da letra, e é a decisão mais importante deste arquivo.

    O caminho tentador é "não reconheço ⇒ é permanente, desiste". Foi
    exatamente assim que a 209 abandonou uma entrega que subiria: transformou
    ignorância em veredito, com uma frase que não deixava espaço para dúvida.

    Os dois erros possíveis aqui não custam o mesmo. Repetir sem reconhecer
    gasta cerca de um minuto e termina no mesmo vermelho; desistir sem
    reconhecer perde uma entrega e deixa a `main` sem chegar ao site, em
    silêncio.
    """
    registro = Registro("erro que ninguem ainda viu neste projeto", quantas=1)
    assert classificar("erro que ninguem ainda viu neste projeto") == DESCONHECIDO
    assert enviar(TAG, empurrar=registro, dormir=sem_pausa) is True
    assert registro.chamadas == 2, (
        "assinatura desconhecida tem de ser REPETIDA, nunca tratada como "
        "permanente — é a armadilhas/209 de cabeça para baixo"
    )


def test_o_log_avisa_quando_esta_repetindo_as_cegas(sem_pausa, capsys):
    """Repetir sem reconhecer é aceitável; repetir sem AVISAR, não.

    Sem esta linha no log, a próxima assinatura nova entraria na rotina de
    repetir para sempre e ninguém saberia que existe uma lista para atualizar.
    """
    enviar(
        TAG,
        empurrar=Registro("coisa nova e estranha", quantas=1),
        dormir=sem_pausa,
    )
    assert "NÃO reconhecida" in capsys.readouterr().out


# ------------------------------------------- 4. o vermelho continua vermelho


def test_esgotadas_as_tentativas_o_veredito_e_vermelho(sem_pausa):
    """Uma vacina que engolisse a falha seria o falso-verde padrão 1.

    Se as três tentativas falharem, a imagem nova NÃO está no registro e o site
    segue servindo a anterior. Verde aqui faria o mantenedor acreditar, no dia
    seguinte, que a versão nova estava no ar.
    """
    registro = Registro("unknown blob", quantas=TENTATIVAS + 5)
    assert enviar(TAG, empurrar=registro, dormir=sem_pausa) is False
    assert registro.chamadas == TENTATIVAS


def test_o_deploy_envia_pelo_script_e_nao_por_docker_push_cru():
    """A vacina só vale se o workflow REALMENTE passar por ela.

    Sem esta trava, `ci/enviar_a_imagem.py` seria código morto no dia em que
    alguém "simplificasse" o passo de volta para `docker push` — com a suíte
    inteira verde, porque os testes acima medem a função, não o deploy. É a
    diferença entre ter a peça e usá-la (a "garantia sem mecanismo" da
    RETROSPECTIVA-FASE-D).
    """
    import yaml

    deploy = yaml.safe_load(
        (RAIZ / ".github" / "workflows" / "deploy-celula.yml").read_text(
            encoding="utf-8"
        )
    )
    passos = [
        passo
        for job in deploy["jobs"].values()
        for passo in (job.get("steps") or [])
        if passo.get("run")
    ]
    comandos = "\n".join(passo["run"] for passo in passos)

    assert (
        "ci/enviar_a_imagem.py" in comandos
    ), "o deploy voltou a enviar a imagem sem a vacina do engasgo do registro"
    assert "docker push" not in comandos, (
        "sobrou um `docker push` cru no deploy — ele não repete, e foi assim "
        "que o PR #897 morreu com a imagem já construída"
    )
    # O build continua sozinho e SEM repetição: build quebrado é defeito de
    # código, e repetir esconde vermelho.
    assert "docker build" in comandos


def test_uma_tag_que_falha_derruba_o_comando_inteiro(monkeypatch):
    """Duas tags são enviadas, e as duas precisam chegar.

    A imagem sobe com `:sha` e `:main`. Se a segunda falhasse em silêncio, a
    VPS puxaria `:main` velho e o deploy ficaria verde apontando para a imagem
    anterior — falso-verde com todos os sinais parecendo normais.
    """
    import enviar_a_imagem

    monkeypatch.setattr(enviar_a_imagem, "enviar", lambda tag: tag.endswith(":sha"))
    assert main(["img:sha", "img:main"]) == 1
    assert main(["img:sha"]) == 0
