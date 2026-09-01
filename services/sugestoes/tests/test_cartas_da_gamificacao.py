"""As quatro cartas de celebração ganham voz na tela do sininho.

**O fato existia; a voz não.** Desde a Sessão B (30/08/2026) a célula
`gamificacao` escreve quatro cartas de celebração e elas chegam à caixa central
como qualquer outra. Esta tela, porém, só sabia desenhar dois assuntos: as
quatro caíam TODAS no cartão do `desconhecido`, e quem subia de nível lia *"este
recado é de um tipo que esta tela ainda não sabe mostrar"*. Ou seja: a
plataforma comemorava em silêncio e ainda pedia desculpa por isso.

**A decisão de desenho, e ela não se reabre:** o `nivel` é o campo autoritativo;
o `titulo_slug` só escolhe o TOM. O slug é DERIVADO (`slugify(titulo)` em
`gamificacao/cartas.py`), então "Aprendiz de Ateliê" chega como
`aprendiz-de-atelie`, e desfazê-lo programaticamente produz lixo visível ao
aluno ("Aprendiz De Atelie"). Por isso um mapa explícito com fallback fail-open,
a mesma forma que `SITUACAO_ROTULOS` e `VINCULO_ROTULOS` já usam nesta tela.

**Os dois guardas que carregam este arquivo:**

1. **Nenhuma das quatro pode estourar `NoReverseMatch`.** O cartão de sugestão
   monta o título com `{% url 'sugestao' aviso.sugestao_id %}`; qualquer carta
   sem `suggestion_id` que caia nele derruba a PÁGINA INTEIRA em 500, para essa
   carta e para todas as outras que a pessoa já tinha. Por isso os quatro
   cartões novos não têm link nenhum, como o de matrícula já não tem.

2. **O fail-visível não pode ser desfeito por um `startswith` guloso.** Um
   assunto `gamificacao.*` que esta tela ainda NÃO conheça tem de continuar
   caindo no `desconhecido`. Um prefixo goloso desenharia o cartão errado em vez
   de admitir a ignorância, e o ramo do desconhecido só protege enquanto for
   possível cair nele.

Contrato dos parâmetros: `contracts/eventos/notificacao.devida.v1.json`. Nada
aqui inventa campo que não esteja lá.
"""

import datetime

import httpx
import pytest
from django.urls import reverse

from apps.core.avisos import (
    ASSUNTO_CONQUISTA,
    ASSUNTO_DESTAQUE,
    ASSUNTO_MARCO,
    ASSUNTO_MATRICULA,
    ASSUNTO_NIVEL,
    _item_para_o_template,
)

pytestmark = pytest.mark.django_db

QUATRO = (ASSUNTO_NIVEL, ASSUNTO_CONQUISTA, ASSUNTO_MARCO, ASSUNTO_DESTAQUE)

#: Parâmetros mínimos válidos de cada assunto, exatamente como o contrato os
#: exige. Só os obrigatórios: os opcionais têm testes próprios logo abaixo.
MINIMO = {
    ASSUNTO_NIVEL: {"nivel": 3, "titulo_slug": "modelador"},
    ASSUNTO_CONQUISTA: {"conquista_slug": "primeira-obra"},
    ASSUNTO_MARCO: {"conquista_slug": "primeiro-dolar"},
    ASSUNTO_DESTAQUE: {"destaque_id": "d-42"},
}


def _carta(assunto, parametros, *, id_="900", lido=False):
    return {
        "id": id_,
        "assunto": assunto,
        "parametros": parametros,
        "ator_id": None,
        "lido_em": "2026-09-01T10:00:00+00:00" if lido else None,
        "criado_em": "2026-09-01T09:00:00+00:00",
    }


def _responde_com(rede, cartas):
    rede.notificacoes_avisos.mock(
        return_value=httpx.Response(200, json={"itens": cartas, "proximo_cursor": None})
    )


# ------------------------------------------- (a) as quatro saem do desconhecido


@pytest.mark.parametrize("assunto", QUATRO)
def test_os_quatro_assuntos_saem_do_ramo_desconhecido(assunto):
    """O guarda mais direto: hoje as quatro caem no cartão genérico. Depois
    deste PR, nenhuma delas pode voltar para lá."""
    item = _item_para_o_template(_carta(assunto, MINIMO[assunto]), {})

    assert "desconhecido" not in item, assunto
    assert item["assunto"] == assunto


@pytest.mark.parametrize("assunto", QUATRO)
def test_nenhuma_das_quatro_vira_cartao_de_sugestao(assunto):
    """Cair no ramo de sugestão é o que faz a página estourar: o título monta
    `{% url 'sugestao' aviso.sugestao_id %}` com um id que não existe."""
    item = _item_para_o_template(_carta(assunto, MINIMO[assunto]), {})

    assert "sugestao_id" not in item, assunto
    assert "status_novo_label" not in item, assunto


@pytest.mark.parametrize(
    "assunto,frase",
    [
        (ASSUNTO_NIVEL, "Você subiu de nível"),
        (ASSUNTO_CONQUISTA, "Você ganhou uma medalha"),
        (ASSUNTO_MARCO, "Seu marco foi aceito"),
        (ASSUNTO_DESTAQUE, "Sua obra foi destaque"),
    ],
)
def test_cada_assunto_desenha_o_SEU_cartao(dentro, rede, quadro, assunto, frase):
    _responde_com(rede, [_carta(assunto, MINIMO[assunto])])

    corpo = dentro.client.get(reverse("avisos")).content.decode()

    assert frase in corpo
    assert "ainda não sabe mostrar" not in corpo


# ------------------------------------------- (b) nenhuma derruba a página


@pytest.mark.parametrize("assunto", QUATRO)
def test_nenhuma_das_quatro_estoura_a_pagina(dentro, rede, quadro, assunto):
    """200 com a carta na lista, nunca 500. Se algum dos cartões novos ganhar um
    `{% url %}` que precise de id, este teste fica vermelho na hora."""
    _responde_com(rede, [_carta(assunto, MINIMO[assunto])])

    resposta = dentro.client.get(reverse("avisos"))

    assert resposta.status_code == 200, assunto
    assert "(sugestão não encontrada)" not in resposta.content.decode()


@pytest.mark.parametrize("assunto", QUATRO)
def test_toda_carta_de_celebracao_pode_ser_marcada_como_lida(
    dentro, rede, quadro, assunto
):
    """Aviso que a pessoa não consegue tirar da frente fica contando no sino
    para sempre, e sino que não zera é o que faz alguém parar de olhar."""
    _responde_com(rede, [_carta(assunto, MINIMO[assunto])])

    corpo = dentro.client.get(reverse("avisos")).content.decode()

    assert "Marcar como lido" in corpo, assunto


@pytest.mark.parametrize("assunto", QUATRO)
def test_nenhum_cartao_de_celebracao_leva_a_lugar_nenhum(dentro, rede, quadro, assunto):
    """Sem link de propósito: o perfil, a galeria e as medalhas moram na célula
    `gamificacao`, que esta tela não consulta. Mandar a pessoa para lá seria
    oferecer uma porta que bate na cara."""
    _responde_com(rede, [_carta(assunto, MINIMO[assunto])])

    corpo = dentro.client.get(reverse("avisos")).content.decode()
    cartao = corpo.split('<article class="aviso')[1].split("</article>")[0]

    assert "<a href" not in cartao, assunto


@pytest.mark.parametrize("assunto", QUATRO)
def test_identificador_opaco_nunca_chega_na_tela(dentro, rede, quadro, assunto):
    """`conquista_slug` e `destaque_id` existem para reconstruir o histórico.
    Um identificador opaco no cartão de um aluno é ruído sobre um dado que ele
    não pode usar para nada, exatamente como o `matricula_id` já é."""
    parametros = {**MINIMO[assunto]}
    for chave in ("conquista_slug", "destaque_id"):
        if chave in parametros:
            parametros[chave] = "sequencia-improvavel-42"
    _responde_com(rede, [_carta(assunto, parametros)])

    corpo = dentro.client.get(reverse("avisos")).content.decode()

    assert "sequencia-improvavel-42" not in corpo, assunto


# --------------------------- (c) parâmetro ausente, e (d) slug fora do mapa


def test_o_nivel_manda_e_o_titulo_do_mapa_acompanha():
    item = _item_para_o_template(
        _carta(ASSUNTO_NIVEL, {"nivel": 2, "titulo_slug": "aprendiz-de-atelie"}), {}
    )

    assert item["nivel"] == 2
    assert item["titulo_do_nivel"] == "Aprendiz de Ateliê"


def test_slug_FORA_do_mapa_mostra_so_o_numero_do_degrau(dentro, rede, quadro):
    """(d) Fail-OPEN, e é a regra que existe porque o slug é derivado: desfazer
    `aprendiz-de-atelie` programaticamente produziria "Aprendiz De Atelie" na
    cara do aluno. Título desconhecido some; o número continua verdadeiro."""
    _responde_com(
        rede,
        [
            _carta(
                ASSUNTO_NIVEL, {"nivel": 11, "titulo_slug": "titulo-que-ninguem-criou"}
            )
        ],
    )

    corpo = dentro.client.get(reverse("avisos")).content.decode()

    assert "Você chegou ao nível" in corpo
    assert "11" in corpo
    assert "titulo-que-ninguem-criou" not in corpo
    assert "Titulo Que Ninguem Criou" not in corpo


def test_carta_de_nivel_SEM_titulo_slug_nao_quebra_nem_deixa_buraco(
    dentro, rede, quadro
):
    """(c) Chave ausente é caso NORMAL: cartas antigas existem, e um contrato
    congelado não retroage sobre o que já foi gravado."""
    _responde_com(rede, [_carta(ASSUNTO_NIVEL, {"nivel": 5})])

    resposta = dentro.client.get(reverse("avisos"))
    corpo = resposta.content.decode()

    assert resposta.status_code == 200
    assert "Você chegou ao nível" in corpo
    # Sem título, a frase termina no número: nunca "nível 5, ." com o vazio no meio.
    assert ", ." not in corpo


def test_carta_de_nivel_SEM_nivel_ainda_diz_algo_verdadeiro(dentro, rede, quadro):
    """(c) O caso mais duro: sem o número não dá para dizer QUAL degrau, e a
    saída não é exceção nem string vazia atravessando a tela. É uma frase mais
    curta que continua inteiramente verdadeira."""
    _responde_com(rede, [_carta(ASSUNTO_NIVEL, {"titulo_slug": "modelador"})])

    resposta = dentro.client.get(reverse("avisos"))
    corpo = resposta.content.decode()

    assert resposta.status_code == 200
    assert "Você alcançou um nível novo." in corpo
    assert "Você chegou ao nível" not in corpo
    # Título sem o degrau a que pertence não é frase de ninguém.
    assert "Modelador" not in corpo


def test_nivel_que_nao_e_numero_nao_derruba_a_pagina():
    """Fail-closed no dado, fail-open na tela: o contrato pede `integer`, mas a
    tela lê o que já está gravado, e um valor torto vira "nível novo" em vez de
    um TypeError na renderização de todo mundo."""
    for torto in ("3", None, True, {"n": 3}):
        item = _item_para_o_template(_carta(ASSUNTO_NIVEL, {"nivel": torto}), {})
        assert item["nivel"] is None, torto
        assert item["titulo_do_nivel"] == ""


@pytest.mark.parametrize(
    "assunto", (ASSUNTO_CONQUISTA, ASSUNTO_MARCO, ASSUNTO_DESTAQUE)
)
def test_cartas_SEM_nenhum_parametro_nao_quebram(dentro, rede, quadro, assunto):
    """(c) Nem `{}` derruba a página. O cartão perde a nuance opcional e mantém
    a boa notícia inteira, que é o que a pessoa precisa ler."""
    _responde_com(rede, [_carta(assunto, {})])

    resposta = dentro.client.get(reverse("avisos"))

    assert resposta.status_code == 200, assunto
    assert "ainda não sabe mostrar" not in resposta.content.decode(), assunto


def test_a_familia_da_medalha_escolhe_o_tom(dentro, rede, quadro):
    _responde_com(
        rede,
        [_carta(ASSUNTO_CONQUISTA, {"conquista_slug": "achou", "familia": "secreta"})],
    )

    corpo = dentro.client.get(reverse("avisos")).content.decode()

    assert "Ela já está guardada no seu perfil." in corpo
    assert "É uma medalha secreta" in corpo


def test_familia_desconhecida_some_em_vez_de_virar_chave_chutada():
    """A mesma regra do `vinculo` e da `situacao` ausentes: nunca uma chave
    chutada, nunca uma exceção."""
    item = _item_para_o_template(
        _carta(ASSUNTO_CONQUISTA, {"conquista_slug": "x", "familia": "inventada"}), {}
    )

    assert item["familia_frase"] == ""


def test_o_marco_diz_o_PAPEL_de_quem_validou_nunca_um_nome(dentro, rede, quadro):
    """O ID de quem validou não viaja na carta, e a tela do aluno diz "a
    equipe" desde sempre. O papel é o máximo que se pode dizer."""
    _responde_com(
        rede,
        [
            _carta(
                ASSUNTO_MARCO, {"conquista_slug": "m", "validador_papel": "professor"}
            )
        ],
    )

    corpo = dentro.client.get(reverse("avisos")).content.decode()

    assert "Alguém conferiu o que você enviou, e o marco agora é seu." in corpo
    assert "Quem conferiu foi um professor da escola." in corpo


def test_a_semana_do_destaque_e_DATA_e_nao_converte_fuso(dentro, rede, quadro):
    """`semana` é a segunda-feira, em `America/Sao_Paulo`, e o contrato a manda
    como DATA justamente para ninguém converter fuso e exibir a semana errada
    (armadilhas/099). `datetime.date` é imune ao `|date:` do template."""
    item = _item_para_o_template(
        _carta(ASSUNTO_DESTAQUE, {"destaque_id": "d", "semana": "2026-08-25"}), {}
    )
    assert item["semana"] == datetime.date(2026, 8, 25)

    _responde_com(
        rede, [_carta(ASSUNTO_DESTAQUE, {"destaque_id": "d", "semana": "2026-08-25"})]
    )
    corpo = dentro.client.get(reverse("avisos")).content.decode()

    assert "galeria da semana de" in corpo
    assert "25/08/2026" in corpo


@pytest.mark.parametrize("torta", ["", "ontem", "2026-02-31", "2026-08-25T10:00:00Z"])
def test_semana_ausente_ou_torta_some_em_vez_de_estourar(dentro, rede, quadro, torta):
    """Semana errada seria pior do que semana nenhuma. `2026-02-31` é o caso
    traiçoeiro: `parse_date` LEVANTA `ValueError` nele, em vez de devolver
    `None`, e sem o `try` isso derrubaria a página inteira da pessoa."""
    _responde_com(
        rede, [_carta(ASSUNTO_DESTAQUE, {"destaque_id": "d", "semana": torta})]
    )

    resposta = dentro.client.get(reverse("avisos"))
    corpo = resposta.content.decode()

    assert resposta.status_code == 200, torta
    assert "Um professor escolheu o seu trabalho para a galeria da semana." in corpo
    assert "galeria da semana de" not in corpo


# ------------------- (e) o fail-visível NÃO pode ser desfeito por um prefixo


def test_assunto_de_gamificacao_AINDA_desconhecido_continua_no_fail_visivel():
    """**O guarda que impede o conserto errado.** A tentação óbvia é
    `assunto.startswith("gamificacao.")`, e ela é um erro: o contrato pode
    ganhar um quinto assunto amanhã, e o prefixo guloso o desenharia com o
    cartão errado em vez de admitir que não o conhece.

    O ramo do desconhecido é fail-VISÍVEL, e ele só protege enquanto for
    possível cair nele.
    """
    item = _item_para_o_template(_carta("gamificacao.coisa-que-ninguem-previu", {}), {})

    assert item["desconhecido"] is True
    assert "sugestao_id" not in item


def test_assunto_de_gamificacao_desconhecido_nao_derruba_a_pagina(dentro, rede, quadro):
    _responde_com(rede, [_carta("gamificacao.coisa-que-ninguem-previu", {})])

    resposta = dentro.client.get(reverse("avisos"))
    corpo = resposta.content.decode()

    assert resposta.status_code == 200
    assert "ainda não sabe mostrar" in corpo
    assert "problema é nosso, não seu" in corpo


# ------------------------- (f) os dois assuntos antigos, byte a byte como antes


def test_a_carta_de_sugestao_continua_exatamente_como_antes(dentro, rede, sugestao):
    """Regressão: o cartão de sempre, com o link de sempre."""
    _responde_com(
        rede,
        [
            _carta(
                "sugestao.status-alterado",
                {
                    "suggestion_id": str(sugestao.id),
                    "status_anterior": "em_analise",
                    "status_novo": "planejado",
                    "vinculo": "autor",
                },
            )
        ],
    )

    corpo = dentro.client.get(reverse("avisos")).content.decode()

    assert sugestao.titulo in corpo
    assert reverse("sugestao", args=[sugestao.id]) in corpo
    assert "Planejado" in corpo


def test_a_carta_de_matricula_continua_exatamente_como_antes(dentro, rede, quadro):
    _responde_com(
        rede,
        [
            _carta(
                ASSUNTO_MATRICULA,
                {
                    "matricula_id": "7",
                    "situacao_anterior": "aguardando",
                    "situacao_nova": "ativa",
                },
            )
        ],
    )

    corpo = dentro.client.get(reverse("avisos")).content.decode()

    assert "Sua situação na escola mudou" in corpo
    assert "Você é aluno" in corpo
    assert "Na fila, esperando decisão" in corpo


def test_as_SETE_cartas_convivem_na_mesma_pagina(dentro, rede, sugestao):
    """A prova de que os ramos não se atrapalham: os dois de sempre, os quatro
    novos e o desconhecido, todos na mesma lista, e a página em pé."""
    cartas = [
        _carta(
            "sugestao.status-alterado",
            {"suggestion_id": str(sugestao.id), "status_novo": "planejado"},
            id_="1",
        ),
        _carta(
            ASSUNTO_MATRICULA, {"matricula_id": "7", "situacao_nova": "ativa"}, id_="2"
        ),
        _carta(ASSUNTO_NIVEL, {"nivel": 9, "titulo_slug": "mestre"}, id_="3"),
        _carta(
            ASSUNTO_CONQUISTA, {"conquista_slug": "c", "familia": "oficio"}, id_="4"
        ),
        _carta(ASSUNTO_MARCO, {"conquista_slug": "m"}, id_="5"),
        _carta(ASSUNTO_DESTAQUE, {"destaque_id": "d"}, id_="6"),
        _carta("gamificacao.coisa-que-ninguem-previu", {}, id_="7"),
    ]
    _responde_com(rede, cartas)

    resposta = dentro.client.get(reverse("avisos"))
    corpo = resposta.content.decode()

    assert resposta.status_code == 200
    assert sugestao.titulo in corpo
    assert "Você é aluno" in corpo
    assert "Você chegou ao nível" in corpo and "Mestre" in corpo
    assert "É uma medalha de ofício" in corpo
    assert "Seu marco foi aceito" in corpo
    assert "Sua obra foi destaque" in corpo
    assert "ainda não sabe mostrar" in corpo
    assert corpo.count('<article class="aviso') == 7


# ------------------------------------------------- a lei do texto publicado


def test_nenhuma_frase_das_quatro_cartas_tem_travessao(dentro, rede, quadro):
    """Lei do projeto desde 30/08/2026: nenhum texto publicado sai com
    travessão. Estas frases são exatamente o tipo de texto que ela cobre, e um
    aluno as lê. O portão do CI vigia `templates/`; este teste vigia o que a
    tela RENDERIZA, incluindo as frases que nascem em `avisos.py`."""
    for assunto in QUATRO:
        _responde_com(rede, [_carta(assunto, MINIMO[assunto])])
        corpo = dentro.client.get(reverse("avisos")).content.decode()
        visivel = corpo.split('<div class="avisos">')[1]
        for risca in ("—", "–", "―", "&mdash;", "&#8212;"):
            assert risca not in visivel, f"{assunto} tem {risca!r}"
