"""A FORJA: o medidor que só cresce, o teto, e o selo que não volta atrás.

O que está travado aqui, e por que cada coisa:

1. **Uma peça, uma linha.** Quem decide é a restrição do banco, e o código não
   perde a corrida com ela.
2. **O medidor SÓ CRESCE.** Não há caminho que o diminua, nem o de abrir a
   mesma peça de novo.
3. **O teto segura ANTES do banco**, e a `CheckConstraint` fica de último
   cinto. Os dois fatos são medidos separados de propósito: um teste que só
   olhasse a exceção passaria com a conferência apagada, porque o cinto
   produziria a mesma frase.
4. **Selar é caminho só de ida**, e o selo guarda o número congelado no
   instante do selamento.
5. **Visitante não leva erro**, e sem `SITE_ID` a página também não quebra.
6. **A forja de outra pessoa nunca é tocada.** É o guarda mais importante do
   arquivo: o gesto não recebe o id de uma linha, então não existe caminho a
   proteger, e este teste é o que garante que continua não existindo.
7. **A medalha das dez forjas cai sozinha**, agora que o fato existe.
"""

from __future__ import annotations

import logging

import pytest
from django.conf import settings
from django.db import IntegrityError, transaction
from django.test import Client

from apps.gamificacao.criterios import avaliar
from apps.gamificacao.forja import (
    ForjaRecusada,
    abertas_de,
    abrir,
    chave_do_desafio,
    mais_uma_tentativa,
    nome_da_peca,
    selar,
    seladas_de,
    texto_do_selo,
)
from apps.gamificacao.models import Concessao, ConquistaDefinicao, Forja, Pessoa

pytestmark = pytest.mark.django_db

SITE = "site-de-teste"
ALUNO = "pes-aluno"
OUTRA = "pes-outra-pessoa"


@pytest.fixture(autouse=True)
def site_e_sessao(monkeypatch):
    """O site vem do env; quem é a pessoa vem da identidade. Os dois em dublê."""
    monkeypatch.setattr("apps.core.views.site_atual", lambda: SITE)
    monkeypatch.setenv("URL_DE_ENTRADA", "https://exemplo.test/entrar")
    monkeypatch.setenv("URL_DA_CAPA", "https://exemplo.test/")


def _entrar_como(monkeypatch, pessoa_id: str | None):
    monkeypatch.setattr("apps.core.views.quem_e", lambda request: pessoa_id)


def _pessoa(id_da_plataforma: str = ALUNO) -> Pessoa:
    pessoa, _ = Pessoa.objects.get_or_create(
        id_da_plataforma=id_da_plataforma,
        defaults={"email": f"{id_da_plataforma}@exemplo.test"},
    )
    return pessoa


# ------------------------------------------- 1. a chave e o nome da peça


def test_a_chave_e_estavel_e_ignora_maiuscula_e_espaco_sobrando():
    """ "Chapéu de Mago" e "  chapéu de mago " são a MESMA peça.

    A chave é o que a restrição do banco compara. Se ela fosse sensível a
    maiúscula, a mesma peça viraria duas linhas e as tentativas do aluno se
    dividiriam entre elas sem nada avisar.
    """
    assert chave_do_desafio("Chapéu de Mago") == chave_do_desafio("  chapéu de mago ")


def test_a_chave_guarda_o_acento_e_a_tela_devolve_o_nome_em_portugues():
    """Sem `allow_unicode`, "chapéu" viraria "chapeu" na cara do aluno."""
    chave = chave_do_desafio("Chapéu de mago")

    assert chave == "chapéu-de-mago"
    assert nome_da_peca(chave) == "Chapéu de mago"


def test_nome_vazio_vira_frase_e_nunca_linha_no_banco():
    with pytest.raises(ForjaRecusada) as recusa:
        chave_do_desafio("   ")

    assert "nome da peça" in str(recusa.value)
    assert Forja.objects.count() == 0


def test_nome_grande_demais_e_recusado_e_nao_cortado_em_silencio():
    """Cortar em 64 faria duas peças diferentes virarem a mesma linha.

    O aluno veria as tentativas de uma somadas às da outra, e nada apontaria o
    motivo. Recusar com frase é o oposto: ele lê o que aconteceu e escolhe um
    apelido menor.
    """
    with pytest.raises(ForjaRecusada) as recusa:
        chave_do_desafio("peça " * 40)

    assert "grande demais" in str(recusa.value)


def test_o_selo_fala_portugues_no_singular_e_no_plural():
    assert texto_do_selo(1) == "forjada em 1 tentativa"
    assert texto_do_selo(13) == "forjada em 13 tentativas"


# ------------------------------------------- 2. uma peça, uma linha


def test_abrir_a_mesma_peca_duas_vezes_nao_cria_duas_linhas():
    pessoa = _pessoa()

    primeira = abrir(pessoa=pessoa, site_id=SITE, nome="Chapéu de Mago")
    segunda = abrir(pessoa=pessoa, site_id=SITE, nome="chapéu de mago")

    assert Forja.objects.count() == 1
    assert primeira.pk == segunda.pk


def test_quem_decide_que_nao_ha_duas_e_o_BANCO():
    """A restrição existe de verdade, e não é uma conferência em Python.

    Sem esta prova, `abrir` poderia estar segurando a duplicata sozinho por um
    `filter().first()` que perde toda corrida entre dois cliques simultâneos.
    """
    pessoa = _pessoa()
    Forja.objects.create(pessoa=pessoa, site_id=SITE, desafio_ref="chapéu", medidor=1)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Forja.objects.create(
                pessoa=pessoa, site_id=SITE, desafio_ref="chapéu", medidor=1
            )


def test_a_mesma_peca_de_duas_pessoas_sao_duas_forjas():
    """A restrição é por (pessoa, site, peça). Dois alunos forjam o mesmo chapéu."""
    abrir(pessoa=_pessoa(ALUNO), site_id=SITE, nome="Chapéu de mago")
    abrir(pessoa=_pessoa(OUTRA), site_id=SITE, nome="Chapéu de mago")

    assert Forja.objects.count() == 2


# ------------------------------------------- 3. o medidor SÓ CRESCE


def test_abrir_ja_conta_a_primeira_tentativa():
    """Ninguém forja uma peça em zero tentativas.

    Um selo dizendo "forjada em 0 tentativas" seria uma frase falsa impressa
    com orgulho, na página que o aluno mostra para os outros.
    """
    forja = abrir(pessoa=_pessoa(), site_id=SITE, nome="Chapéu")

    assert forja.medidor == 1


def test_cada_tentativa_soma_uma():
    pessoa = _pessoa()
    abrir(pessoa=pessoa, site_id=SITE, nome="Chapéu")

    for _ in range(3):
        mais_uma_tentativa(pessoa=pessoa, site_id=SITE, desafio_ref="chapéu")

    assert Forja.objects.get().medidor == 4


def test_abrir_de_novo_uma_peca_em_andamento_NAO_zera_o_medidor():
    """O caminho mais fácil de o medidor encolher, e ele está fechado.

    Reabrir a mesma peça é gesto comum: o aluno digita o apelido de novo sem
    lembrar que ela já está na bancada. Se isso a devolvesse para uma
    tentativa, o medidor deixaria de só crescer pela porta da frente.
    """
    pessoa = _pessoa()
    abrir(pessoa=pessoa, site_id=SITE, nome="Chapéu")
    for _ in range(4):
        mais_uma_tentativa(pessoa=pessoa, site_id=SITE, desafio_ref="chapéu")

    abrir(pessoa=pessoa, site_id=SITE, nome="Chapéu")

    assert Forja.objects.get().medidor == 5


# ------------------------------------------- 4. o teto, e o último cinto


def test_o_teto_segura_o_medidor_e_a_frase_diz_o_limite():
    pessoa = _pessoa()
    Forja.objects.create(pessoa=pessoa, site_id=SITE, desafio_ref="chapéu", teto=3)
    for _ in range(3):
        mais_uma_tentativa(pessoa=pessoa, site_id=SITE, desafio_ref="chapéu")

    with pytest.raises(ForjaRecusada) as recusa:
        mais_uma_tentativa(pessoa=pessoa, site_id=SITE, desafio_ref="chapéu")

    assert "limite de 3 tentativas" in str(recusa.value)
    assert Forja.objects.get().medidor == 3


def test_a_conferencia_acontece_ANTES_do_banco(caplog):
    """A `CheckConstraint` é o último cinto, e este teste prova que ela não é o
    primeiro.

    A frase de recusa é a MESMA nos dois caminhos, de propósito (o aluno não
    tem o que fazer com a diferença) — e é por isso que olhar só a exceção
    seria falso-verde: apagar a conferência deixaria o banco produzir a mesma
    frase e o teste continuaria verde. O que separa os dois caminhos é o log:
    o cinto grita, a conferência não precisa gritar.
    """
    pessoa = _pessoa()
    Forja.objects.create(pessoa=pessoa, site_id=SITE, desafio_ref="chapéu", teto=1)
    mais_uma_tentativa(pessoa=pessoa, site_id=SITE, desafio_ref="chapéu")

    with caplog.at_level(logging.WARNING, logger="apps.gamificacao.forja"):
        with pytest.raises(ForjaRecusada):
            mais_uma_tentativa(pessoa=pessoa, site_id=SITE, desafio_ref="chapéu")

    assert "o banco recusou" not in caplog.text


def test_a_recusa_do_banco_vira_frase_e_nunca_erro_de_servidor(monkeypatch):
    """O último cinto é cinto, não abismo.

    Alguém pode baixar o teto por fora enquanto a transação corre. Chegar aqui
    é raro; virar 500 na cara do aluno não pode ser.
    """
    pessoa = _pessoa()
    abrir(pessoa=pessoa, site_id=SITE, nome="Chapéu")

    def recusar(*args, **kwargs):
        raise IntegrityError("o medidor da forja respeita o teto")

    monkeypatch.setattr(Forja, "save", recusar)

    with pytest.raises(ForjaRecusada):
        mais_uma_tentativa(pessoa=pessoa, site_id=SITE, desafio_ref="chapéu")


# ------------------------------------------- 5. selar é só de ida


def test_o_selo_grava_o_numero_congelado_no_instante_do_selamento():
    pessoa = _pessoa()
    abrir(pessoa=pessoa, site_id=SITE, nome="Chapéu")
    for _ in range(12):
        mais_uma_tentativa(pessoa=pessoa, site_id=SITE, desafio_ref="chapéu")

    forja = selar(pessoa=pessoa, site_id=SITE, desafio_ref="chapéu")

    assert forja.medidor == 13
    assert forja.selo == "forjada em 13 tentativas"
    assert forja.selada_em is not None


def test_o_selo_e_GRAVADO_e_nao_calculado_toda_vez():
    """Se o selo fosse derivado do medidor na hora de mostrar, mexer no medidor
    depois reescreveria o passado e o selo deixaria de ser prova de coisa
    nenhuma.

    O `update` cru aqui é o único jeito de simular isso: pela porta da frente
    não há caminho que mexa numa forja selada, e é essa a outra metade da lei.
    """
    pessoa = _pessoa()
    abrir(pessoa=pessoa, site_id=SITE, nome="Chapéu")
    for _ in range(2):
        mais_uma_tentativa(pessoa=pessoa, site_id=SITE, desafio_ref="chapéu")
    selar(pessoa=pessoa, site_id=SITE, desafio_ref="chapéu")

    Forja.objects.filter(desafio_ref="chapéu").update(medidor=99)

    assert Forja.objects.get().selo == "forjada em 3 tentativas"


def test_forja_selada_nao_aceita_mais_tentativa():
    pessoa = _pessoa()
    abrir(pessoa=pessoa, site_id=SITE, nome="Chapéu")
    selar(pessoa=pessoa, site_id=SITE, desafio_ref="chapéu")

    with pytest.raises(ForjaRecusada) as recusa:
        mais_uma_tentativa(pessoa=pessoa, site_id=SITE, desafio_ref="chapéu")

    assert "já está selada" in str(recusa.value)
    assert Forja.objects.get().medidor == 1


def test_selar_duas_vezes_e_recusa_e_o_primeiro_selo_permanece():
    """Recusa com frase, e não um segundo selo em silêncio.

    Fosse idempotente calado, um F5 depois de selar pareceria gesto novo. E o
    instante do selamento mudaria, o que é reescrever a história da peça.
    """
    pessoa = _pessoa()
    abrir(pessoa=pessoa, site_id=SITE, nome="Chapéu")
    primeira = selar(pessoa=pessoa, site_id=SITE, desafio_ref="chapéu")

    with pytest.raises(ForjaRecusada):
        selar(pessoa=pessoa, site_id=SITE, desafio_ref="chapéu")

    de_novo = Forja.objects.get()
    assert de_novo.selada_em == primeira.selada_em
    assert de_novo.selo == primeira.selo


def test_a_peca_selada_sai_da_bancada_e_entra_na_estante():
    pessoa = _pessoa()
    abrir(pessoa=pessoa, site_id=SITE, nome="Chapéu")
    abrir(pessoa=pessoa, site_id=SITE, nome="Espada")
    selar(pessoa=pessoa, site_id=SITE, desafio_ref="chapéu")

    assert [f.desafio_ref for f in abertas_de(pessoa, SITE)] == ["espada"]
    assert [f.desafio_ref for f in seladas_de(pessoa, SITE)] == ["chapéu"]


# ------------------------------------------- 6. a tela


def test_visitante_ve_convite_e_nunca_erro(monkeypatch):
    _entrar_como(monkeypatch, None)

    resposta = Client().get("/forja")

    assert resposta.status_code == 200
    assert "Entrar na escola" in resposta.content.decode()


def test_sem_site_id_a_pagina_nao_quebra(monkeypatch):
    """Falha ABERTA: `site_atual()` devolve `None` e a tela trata como visitante.

    Página sem selo é uma página; página quebrada não é. E é por ser uma falha
    silenciosa que ela precisa de guarda: sem `SITE_ID` no env, todo aluno some
    do mapa de uma vez e nenhuma tela avisa.
    """
    _entrar_como(monkeypatch, ALUNO)
    monkeypatch.setattr("apps.core.views.site_atual", lambda: None)

    resposta = Client().get("/forja")

    assert resposta.status_code == 200
    assert "Entrar na escola" in resposta.content.decode()


def test_a_tela_mostra_a_peca_o_numero_e_o_selo(monkeypatch):
    _entrar_como(monkeypatch, ALUNO)
    cliente = Client()

    cliente.post("/forja/registrar", {"gesto": "abrir", "nome": "Chapéu de mago"})
    for _ in range(2):
        cliente.post(
            "/forja/registrar", {"gesto": "tentativa", "peca": "chapéu-de-mago"}
        )

    corpo = cliente.get("/forja").content.decode()
    assert "Chapéu de mago" in corpo
    assert "3" in corpo

    cliente.post("/forja/registrar", {"gesto": "selar", "peca": "chapéu-de-mago"})

    corpo = cliente.get("/forja").content.decode()
    assert "forjada em 3 tentativas" in corpo


def test_o_gesto_volta_pela_tela_e_nao_repete_com_F5(monkeypatch):
    """POST-redirect-GET. Sem ele, um F5 depois de somar somaria de novo, e o
    medidor que só cresce cresceria por engano, que é a única forma de esse
    número mentir.
    """
    _entrar_como(monkeypatch, ALUNO)

    resposta = Client().post("/forja/registrar", {"gesto": "abrir", "nome": "Chapéu"})

    assert resposta.status_code == 302
    assert resposta["Location"].endswith("?recado=forja-aberta")


def test_a_recusa_vira_frase_na_tela_e_nunca_500(monkeypatch):
    _entrar_como(monkeypatch, ALUNO)
    cliente = Client()
    cliente.post("/forja/registrar", {"gesto": "abrir", "nome": "Chapéu"})
    cliente.post("/forja/registrar", {"gesto": "selar", "peca": "chapéu"})

    resposta = cliente.post(
        "/forja/registrar", {"gesto": "tentativa", "peca": "chapéu"}, follow=True
    )

    assert resposta.status_code == 200
    assert "já está selada" in resposta.content.decode()


def test_visitante_que_posta_vai_para_a_entrada_sem_criar_nada(monkeypatch):
    _entrar_como(monkeypatch, None)

    resposta = Client().post("/forja/registrar", {"gesto": "abrir", "nome": "Chapéu"})

    assert resposta.status_code == 302
    assert Forja.objects.count() == 0


def test_o_formulario_atravessa_a_protecao_de_csrf_de_verdade(monkeypatch):
    """O formulário funciona no navegador, não só no cliente permissivo.

    O crachá vai no POTE de cookies do cliente, nunca em
    `headers={"cookie": ...}` — aquele cabeçalho substitui o pote inteiro e
    apaga o `csrftoken` que a página acabou de plantar, e a resposta vira 403
    com o token correto dentro do POST (`armadilhas/204`).
    """
    _entrar_como(monkeypatch, ALUNO)
    cliente = Client(enforce_csrf_checks=True)
    cliente.get("/forja")
    # O nome do cookie sai do `settings`, nunca escrito à mão: esta célula usa
    # `gamificacao_csrf` de propósito (um `csrftoken` genérico neste domínio
    # seria disputado por todas as células), e um literal aqui envelheceria
    # calado no dia em que esse nome mudasse.
    token = cliente.cookies[settings.CSRF_COOKIE_NAME].value

    resposta = cliente.post(
        "/forja/registrar",
        {"gesto": "abrir", "nome": "Chapéu", "csrfmiddlewaretoken": token},
    )

    assert resposta.status_code == 302
    assert Forja.objects.count() == 1


# ------------------------------------------- 7. a forja dos outros


def test_um_post_forjado_NUNCA_toca_a_forja_de_outra_pessoa(monkeypatch):
    """O guarda mais importante deste arquivo.

    O gesto não recebe o id de uma linha: o formulário manda o NOME da peça e o
    dono é sempre quem a sessão diz que é. Não há conferência de dono para
    alguém esquecer de escrever num caminho novo, porque não há caminho.
    """
    vitima = _pessoa(OUTRA)
    abrir(pessoa=vitima, site_id=SITE, nome="Chapéu de mago")
    for _ in range(4):
        mais_uma_tentativa(pessoa=vitima, site_id=SITE, desafio_ref="chapéu-de-mago")

    _entrar_como(monkeypatch, ALUNO)
    cliente = Client()
    cliente.post("/forja/registrar", {"gesto": "tentativa", "peca": "chapéu-de-mago"})
    cliente.post("/forja/registrar", {"gesto": "selar", "peca": "chapéu-de-mago"})

    dela = Forja.objects.get(pessoa=vitima)
    assert dela.medidor == 5
    assert dela.selada_em is None
    assert dela.selo == ""


def test_o_servico_recusa_a_peca_que_nao_e_sua():
    """A mesma trava, medida um degrau abaixo da tela.

    A view é uma porta; se um dia nascer outra (uma API, um comando), é esta
    função que continua sendo o guarda.
    """
    abrir(pessoa=_pessoa(OUTRA), site_id=SITE, nome="Chapéu")

    with pytest.raises(ForjaRecusada) as recusa:
        mais_uma_tentativa(pessoa=_pessoa(ALUNO), site_id=SITE, desafio_ref="chapéu")

    assert "entre as suas" in str(recusa.value)


def test_a_forja_de_outra_ESCOLA_tambem_e_intocavel():
    """A fronteira de site é Lei 9, e uma tela é o lugar mais fácil de esquecê-la."""
    pessoa = _pessoa()
    abrir(pessoa=pessoa, site_id="outra-escola", nome="Chapéu")

    with pytest.raises(ForjaRecusada):
        mais_uma_tentativa(pessoa=pessoa, site_id=SITE, desafio_ref="chapéu")


# ------------------------------------------- 8. a medalha que passou a cair


def test_a_medalha_das_dez_forjas_cai_com_dez_pecas_seladas():
    """O fato que faltava desde o degrau 12. A medalha existe desde então e
    esperava por ele.

    Nenhuma regra de medalha foi escrita nesta entrega: `criterios._valor_forjas`
    já contava forjas seladas. O que faltava era alguém selar uma.
    """
    ConquistaDefinicao.objects.create(
        slug="dez-forjas",
        site_id=SITE,
        nome="Dez forjas",
        classe=ConquistaDefinicao.Classe.MEDALHA,
        familia=ConquistaDefinicao.Familia.OFICIO,
        criterio={"tipo": "forjas_seladas", "alvo": 10},
        pontos=80,
        cristais=0,
        ativa=True,
    )
    pessoa = _pessoa()

    for numero in range(9):
        abrir(pessoa=pessoa, site_id=SITE, nome=f"peça {numero}")
        selar(pessoa=pessoa, site_id=SITE, desafio_ref=f"peça-{numero}")
    assert avaliar(ALUNO, SITE) == [], "nove ainda não são dez"

    abrir(pessoa=pessoa, site_id=SITE, nome="peça dez")
    selar(pessoa=pessoa, site_id=SITE, desafio_ref="peça-dez")

    assert Concessao.objects.filter(conquista__slug="dez-forjas").count() == 1


def test_selar_concede_a_medalha_na_hora_sem_esperar_outro_numero_mexer():
    """A Forja vale ZERO XP, então ela nunca passa por `motor.recalcular` — que
    é onde todo o resto do sistema avalia critérios.

    Sem a chamada ao motor dentro de `selar`, a medalha só cairia na próxima vez
    que algum OUTRO número da pessoa mudasse, e o aluno que só forja peças
    esperaria por ela para sempre.
    """
    ConquistaDefinicao.objects.create(
        slug="primeira-forja",
        site_id=SITE,
        nome="Primeira forja",
        classe=ConquistaDefinicao.Classe.MEDALHA,
        familia=ConquistaDefinicao.Familia.OFICIO,
        criterio={"tipo": "forjas_seladas", "alvo": 1},
        pontos=0,
        cristais=0,
        ativa=True,
    )
    pessoa = _pessoa()
    abrir(pessoa=pessoa, site_id=SITE, nome="Chapéu")

    selar(pessoa=pessoa, site_id=SITE, desafio_ref="chapéu")

    assert Concessao.objects.filter(conquista__slug="primeira-forja").count() == 1


def test_a_forja_nao_paga_XP_nenhum():
    """Pagar insistência em pontos ensinaria a inflar o número de tentativas,
    que é exatamente o número que o selo existe para tornar honesto.
    """
    from apps.gamificacao.models import LancamentoDeXP

    pessoa = _pessoa()
    abrir(pessoa=pessoa, site_id=SITE, nome="Chapéu")
    for _ in range(5):
        mais_uma_tentativa(pessoa=pessoa, site_id=SITE, desafio_ref="chapéu")
    selar(pessoa=pessoa, site_id=SITE, desafio_ref="chapéu")

    assert LancamentoDeXP.objects.count() == 0
