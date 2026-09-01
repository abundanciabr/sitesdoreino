"""As duas telas dos marcos: a do aluno que envia, e a da equipe que decide.

O caminho que a TAR-088 construiu não tinha porta: existia o serviço e nenhuma
tela. Este arquivo trava as duas que nasceram, e sobretudo a fechadura da
segunda.

O QUE ESTÁ TRAVADO AQUI:

1. **A área da equipe é fail-CLOSED.** Lista de ids vazia recusa todo mundo,
   inclusive o mantenedor. É a lei da célula §5 virando teste: *"reconhecer não é
   autorizar"* — o `papel` que a identidade devolve é de exibição, e usá-lo aqui
   seria abrir a fila para quem a plataforma chama de professor em qualquer outro
   contexto.
2. **O papel de quem decide sai do SERVIDOR.** Um campo escondido no formulário
   seria uma etiqueta que o próprio navegador escreve, e a auditoria de um marco
   contestado passaria a valer o que vale um campo que qualquer um edita.
3. **A tela do aluno conta a devolução**, que é a única forma de ele saber:
   devolver não gera aviso no sininho, porque só boa notícia vira carta.
4. **Visitante não leva erro** — vê a mesma página com um convite para entrar.
5. **A recusa vira frase, nunca 500.**
"""

from __future__ import annotations

import pytest
from django.test import Client

from apps.core import equipe as porta_da_equipe
from apps.gamificacao.models import (
    Concessao,
    ConquistaDefinicao,
    PedidoDeValidacao,
    Pessoa,
)
from apps.gamificacao.validacao import pedir_validacao

pytestmark = pytest.mark.django_db

SITE = "site-de-teste"
ALUNO = "pes-aluno"
PROFESSOR = "pes-professor"


@pytest.fixture(autouse=True)
def site_e_sessao(monkeypatch):
    """O site vem do env; quem é a pessoa vem da identidade. Os dois em dublê.

    `quem_e` e `site_atual` são o contato desta célula com o resto da
    plataforma. Trocá-los aqui deixa o teste medir a TELA, e não a rede — uma
    suíte que precisasse da identidade de pé ficaria vermelha por motivo alheio.
    """
    monkeypatch.setattr("apps.core.views.site_atual", lambda: SITE)
    monkeypatch.setenv("URL_DE_ENTRADA", "https://exemplo.test/entrar")
    monkeypatch.setenv("URL_DA_CAPA", "https://exemplo.test/")


def _entrar_como(monkeypatch, pessoa_id: str | None):
    monkeypatch.setattr("apps.core.views.quem_e", lambda request: pessoa_id)


def _da_equipe(monkeypatch, *ids: str):
    monkeypatch.setenv(porta_da_equipe.VARIAVEL, ",".join(ids))
    # O aviso de lista vazia é uma vez por processo; zerar a marca deixa cada
    # teste medir o estado que ele mesmo montou.
    porta_da_equipe._ja_avisei_que_a_lista_esta_vazia = False


def _marco(**campos) -> ConquistaDefinicao:
    base = {
        "slug": "portfolio-publicado",
        "site_id": SITE,
        "nome": "Portfólio no ar",
        "classe": ConquistaDefinicao.Classe.MARCO,
        "familia": ConquistaDefinicao.Familia.CARREIRA,
        "criterio": {"tipo": "manual"},
        "pontos": 0,
        "ativa": True,
    }
    base.update(campos)
    return ConquistaDefinicao.objects.create(**base)


# ------------------------------------------- 1. a tela do aluno


def test_visitante_ve_convite_e_nunca_erro(monkeypatch):
    _entrar_como(monkeypatch, None)

    resposta = Client().get("/marcos")

    assert resposta.status_code == 200
    assert "Entrar na escola" in resposta.content.decode()


def test_o_aluno_envia_a_prova_e_o_pedido_entra_na_fila(monkeypatch):
    _entrar_como(monkeypatch, ALUNO)
    _marco()
    cliente = Client()

    resposta = cliente.post(
        "/marcos/enviar",
        {"slug": "portfolio-publicado", "evidencia": "meu-portfolio.test"},
    )

    assert resposta.status_code == 302
    pedido = PedidoDeValidacao.objects.get()
    assert pedido.pessoa_id == ALUNO
    assert pedido.evidencia == "meu-portfolio.test"
    assert pedido.estado == PedidoDeValidacao.Estado.EM_ANALISE
    # A prova nasce privada, e é a tela do aluno que não pode mudar isso.
    assert pedido.evidencia_privada is True


def test_a_tela_do_aluno_conta_a_devolucao_e_oferece_o_reenvio(monkeypatch):
    """A única forma de o aluno saber. Devolver não gera aviso no sininho."""
    _entrar_como(monkeypatch, ALUNO)
    marco = _marco()
    pessoa = Pessoa.objects.create(id_da_plataforma=ALUNO, email="a@exemplo.test")
    pedido = pedir_validacao(pessoa=pessoa, site_id=SITE, conquista=marco)
    from apps.gamificacao.validacao import devolver

    devolver(
        pedido=pedido,
        validador_id=PROFESSOR,
        validador_papel=Concessao.PapelDoValidador.PROFESSOR,
        motivo=PedidoDeValidacao.MotivoDaDevolucao.EVIDENCIA_ILEGIVEL,
    )

    corpo = Client().get("/marcos").content.decode()

    assert "A evidência não dá para ler" in corpo
    assert "Mandar de novo" in corpo


def test_pedir_duas_vezes_vira_frase_e_nao_erro(monkeypatch):
    _entrar_como(monkeypatch, ALUNO)
    _marco()
    cliente = Client()
    cliente.post("/marcos/enviar", {"slug": "portfolio-publicado", "evidencia": "x"})

    resposta = cliente.post(
        "/marcos/enviar", {"slug": "portfolio-publicado", "evidencia": "x"}, follow=True
    )

    assert resposta.status_code == 200
    assert "já está na fila" in resposta.content.decode()
    assert PedidoDeValidacao.objects.count() == 1


# ------------------------------------------- 2. a porta da equipe


def test_a_fila_recusa_quem_nao_esta_na_lista(monkeypatch):
    _entrar_como(monkeypatch, ALUNO)
    _da_equipe(monkeypatch, PROFESSOR)

    resposta = Client().get("/interno")

    assert resposta.status_code == 403
    assert "área é da equipe" in resposta.content.decode()


def test_lista_vazia_recusa_todo_mundo(monkeypatch):
    """Fail-CLOSED: env ausente não abre a porta, fecha.

    É o mesmo desenho de `TOKENS_ACEITOS` ao lado — e a direção importa: uma
    variável esquecida não pode virar permissão para o site inteiro julgar o
    marco dos outros.
    """
    _entrar_como(monkeypatch, PROFESSOR)
    _da_equipe(monkeypatch)

    assert Client().get("/interno").status_code == 403
    assert Client().post("/interno/decidir", {"pedido": 1}).status_code == 403


def test_visitante_tambem_e_recusado(monkeypatch):
    _entrar_como(monkeypatch, None)
    _da_equipe(monkeypatch, PROFESSOR)

    assert Client().get("/interno").status_code == 403


def test_a_equipe_ve_a_fila_e_aceita_em_um_clique(monkeypatch):
    _entrar_como(monkeypatch, PROFESSOR)
    _da_equipe(monkeypatch, PROFESSOR)
    marco = _marco()
    pessoa = Pessoa.objects.create(id_da_plataforma=ALUNO, email="a@exemplo.test")
    pedido = pedir_validacao(
        pessoa=pessoa, site_id=SITE, conquista=marco, evidencia="a prova"
    )

    corpo = Client().get("/interno").content.decode()
    assert "Portfólio no ar" in corpo
    assert "a prova" in corpo

    resposta = Client().post(
        "/interno/decidir", {"pedido": pedido.pk, "gesto": "aceitar"}
    )

    assert resposta.status_code == 302
    concessao = Concessao.objects.get()
    assert concessao.pessoa_id == ALUNO
    # O PAPEL VEM DO SERVIDOR: quem está na lista decide como equipe.
    assert concessao.validador_id == PROFESSOR
    assert concessao.validador_papel == Concessao.PapelDoValidador.PROFESSOR


def test_o_formulario_nao_escolhe_o_papel_de_quem_decide(monkeypatch):
    """Um campo escondido `validador_papel=par` não muda nada: o servidor manda.

    Sem esta trava, a auditoria de um marco contestado valeria o que vale um
    campo que qualquer um edita no navegador.
    """
    _entrar_como(monkeypatch, PROFESSOR)
    _da_equipe(monkeypatch, PROFESSOR)
    marco = _marco(envolve_dinheiro=True, exige_validador_da_equipe=True)
    pessoa = Pessoa.objects.create(id_da_plataforma=ALUNO, email="a@exemplo.test")
    pedido = pedir_validacao(pessoa=pessoa, site_id=SITE, conquista=marco)

    Client().post(
        "/interno/decidir",
        {"pedido": pedido.pk, "gesto": "aceitar", "validador_papel": "par"},
    )

    assert Concessao.objects.get().validador_papel == (
        Concessao.PapelDoValidador.PROFESSOR
    )


def test_devolver_pela_tela_exige_motivo_da_lista(monkeypatch):
    _entrar_como(monkeypatch, PROFESSOR)
    _da_equipe(monkeypatch, PROFESSOR)
    marco = _marco()
    pessoa = Pessoa.objects.create(id_da_plataforma=ALUNO, email="a@exemplo.test")
    pedido = pedir_validacao(pessoa=pessoa, site_id=SITE, conquista=marco)

    resposta = Client().post(
        "/interno/decidir",
        {"pedido": pedido.pk, "gesto": "devolver", "motivo": "inventado"},
        follow=True,
    )

    assert resposta.status_code == 200
    assert "não é um dos motivos" in resposta.content.decode()
    pedido.refresh_from_db()
    assert pedido.estado == PedidoDeValidacao.Estado.EM_ANALISE

    Client().post(
        "/interno/decidir",
        {
            "pedido": pedido.pk,
            "gesto": "devolver",
            "motivo": PedidoDeValidacao.MotivoDaDevolucao.FALTA_EVIDENCIA,
        },
    )
    pedido.refresh_from_db()
    assert pedido.estado == PedidoDeValidacao.Estado.DEVOLVIDO


def test_a_equipe_de_uma_escola_nao_alcanca_o_pedido_de_outra(monkeypatch):
    """A fronteira de site é Lei 9, e uma tela é o lugar mais fácil de esquecê-la."""
    _entrar_como(monkeypatch, PROFESSOR)
    _da_equipe(monkeypatch, PROFESSOR)
    marco = ConquistaDefinicao.objects.create(
        slug="portfolio-publicado",
        site_id="outra-escola",
        nome="Portfólio no ar",
        classe=ConquistaDefinicao.Classe.MARCO,
        familia=ConquistaDefinicao.Familia.CARREIRA,
        criterio={"tipo": "manual"},
        pontos=0,
        ativa=True,
    )
    pessoa = Pessoa.objects.create(id_da_plataforma=ALUNO, email="a@exemplo.test")
    pedido = pedir_validacao(pessoa=pessoa, site_id="outra-escola", conquista=marco)

    assert list(Client().get("/interno").context["fila"]) == []

    resposta = Client().post(
        "/interno/decidir", {"pedido": pedido.pk, "gesto": "aceitar"}, follow=True
    )
    assert "não existe mais nesta escola" in resposta.content.decode()
    assert Concessao.objects.count() == 0
