"""O beco virou fila — `docs/decisoes/DECISAO-fila-de-liberacao.md` (27/08/2026).

Até esta data, quem chegava logado no site e sem matrícula lia *"não encontramos
matrícula para esse e-mail"* e acabava ali: não existia, em lugar nenhum da
plataforma, um lugar onde esperar. O mantenedor bateu nessa tela com a própria
conta e decidiu que ela precisava de destino.

O que **não** mudou, e é o que os guardas de `test_inv_entrada_sem_matricula.py`
continuam medindo sem uma linha alterada: a recusa continua sendo 403, continua
nomeando o e-mail e continua oferecendo a troca de conta. O diagnóstico ficou; o
beco saiu.
"""

import pytest
from django.urls import reverse

from apps.sugestoes.models import Identidade
from tests.conftest import sessao_do_site

PESSOA = "quem.espera@exemplo.test"
PEDIDO = {
    "nome_completo": "Quem Espera",
    "whatsapp": "(96) 99999-0000",
}


@pytest.fixture
def na_porta(rede, db, quadro):
    """Alguém logado no site, sem matrícula, diante da porta.

    O `quadro` não é enfeite: é dele que sai o `site_id` do pedido.
    """
    rede.alunos_nao_conhece(PESSOA)
    return sessao_do_site(rede, email=PESSOA)


def pedir(pessoa, **campos):
    return pessoa.client.post(reverse("pedir_entrada"), {**PEDIDO, **campos})


# ---------------------------------------------------------------------------
# A tela: o "não" com destino
# ---------------------------------------------------------------------------


def test_quem_nao_tem_matricula_ve_o_formulario_e_nao_um_beco(na_porta):
    conteudo = na_porta.abrir().content.decode()

    assert f'action="{reverse("pedir_entrada")}"' in conteudo
    for campo in ("nome_completo", "whatsapp", "comprou_em", "turma"):
        assert f'name="{campo}"' in conteudo, f"falta o campo {campo}"
    assert "Pedir liberação" in conteudo


def test_o_formulario_e_uma_tela_so(na_porta):
    """Lei §6: quatro campos, um botão. A pessoa acabou de fazer login e está no
    pico da motivação — cada passo a mais é um ponto de desistência."""
    conteudo = na_porta.abrir().content.decode()

    assert conteudo.count('<form method="post"') <= 2, (
        "o formulário da fila virou várias etapas (ou apareceu um formulário a "
        "mais) — a decisão é UMA tela; o segundo <form> permitido é o 'sair'"
    )
    assert conteudo.count("Pedir liberação") == 1


def test_a_tela_diz_que_os_opcionais_sao_opcionais(na_porta):
    """Lei §6: são pistas de conferência, e a tela precisa dizer isso — para
    ninguém inventar um valor achando que é obrigatório."""
    conteudo = na_porta.abrir().content.decode()
    assert "opcionais" in conteudo
    assert "Deixe em branco" in conteudo


def test_a_porta_continua_recusando_quem_esta_na_fila(na_porta):
    """O elo com a Fase 1 da `alunos`: entrar na fila NÃO é entrar na Caixa.

    Do lado de lá, o status `aguardando` foi tirado da consulta que decide
    acesso; deste lado, o que se mede é o efeito — a pessoa que acabou de pedir
    continua vendo 403, não o quadro.
    """
    na_porta.rede.alunos_aceita_o_pedido()
    assert pedir(na_porta).status_code == 200

    assert na_porta.abrir().status_code == 403
    assert not na_porta.esta_dentro


# ---------------------------------------------------------------------------
# O que atravessa o fio
# ---------------------------------------------------------------------------


def test_o_pedido_leva_nome_whatsapp_e_o_email_da_sessao(na_porta):
    na_porta.rede.alunos_aceita_o_pedido()

    assert pedir(na_porta).status_code == 200

    pedido = na_porta.rede.um_pedido
    assert pedido["nome_completo"] == "Quem Espera"
    assert pedido["whatsapp"] == "(96) 99999-0000"
    assert pedido["email"] == PESSOA, (
        "o e-mail tem que vir da SESSÃO, nunca de um campo do formulário — "
        "senão qualquer um põe o endereço de outra pessoa na fila"
    )


def test_o_site_id_vem_do_quadro_e_nao_de_uma_variavel(na_porta, quadro):
    """A Caixa descobre o próprio site pelo quadro desta requisição.

    Um env a mais aqui seria um segundo lugar guardando o mesmo fato — e o dia
    em que os dois discordassem, a pessoa entraria na fila de outro site.
    """
    na_porta.rede.alunos_aceita_o_pedido()
    pedir(na_porta)

    assert na_porta.rede.um_pedido["site_id"] == quadro.site_id


def test_os_opcionais_viajam_quando_preenchidos(na_porta):
    na_porta.rede.alunos_aceita_o_pedido()

    pedir(na_porta, comprou_em="2026-08-01", turma="Turma de agosto")

    pedido = na_porta.rede.um_pedido
    assert pedido["comprou_em"] == "2026-08-01"
    assert pedido["turma"] == "Turma de agosto"


def test_os_opcionais_em_branco_nao_viajam(na_porta):
    """O contrato declara `additionalProperties: false`; mandar chave vazia é
    depender de um detalhe de aceitação que não precisamos exercitar."""
    na_porta.rede.alunos_aceita_o_pedido()

    pedir(na_porta)

    assert set(na_porta.rede.um_pedido) == {
        "site_id",
        "email",
        "nome_completo",
        "whatsapp",
    }


# ---------------------------------------------------------------------------
# O recibo — e por que ele é lembrança, não verdade
# ---------------------------------------------------------------------------


def test_depois_de_pedir_a_pessoa_ve_o_recibo(na_porta):
    na_porta.rede.alunos_aceita_o_pedido()

    conteudo = pedir(na_porta).content.decode()

    assert "Seu pedido já está com a gente" in conteudo
    assert "Pedir liberação" not in conteudo, (
        "o formulário continuou na tela depois do envio — a pessoa não sabe se "
        "o pedido chegou e vai clicar de novo"
    )


def test_recarregar_a_porta_nao_devolve_o_formulario_vazio(na_porta):
    na_porta.rede.alunos_aceita_o_pedido()
    pedir(na_porta)

    conteudo = na_porta.abrir().content.decode()

    assert "Seu pedido já está com a gente" in conteudo
    assert "Pedir liberação" not in conteudo


def test_pedir_entrada_nao_reescreve_o_cookie_do_site(na_porta):
    """O guarda mais importante deste arquivo — e ele nasceu de um bug real.

    Esta célula usa `SESSION_COOKIE_NAME = "meshcraft_sessao"`, o MESMO cookie
    que a `identidade` assina para o site inteiro (é disso que o `sair` daqui
    depende para deslogar de tudo). Com `SESSION_ENGINE = signed_cookies`, uma
    única escrita em `request.session` reescreve aquele cookie com uma sessão
    DESTA célula — e a pessoa é deslogada do site ao clicar em "Pedir
    liberação". A primeira versão desta tela fazia exatamente isso: guardava a
    lembrança do pedido em `request.session`, e o teste de recarregar a página
    caiu com a porta devolvendo "visitante".

    A lembrança mora num cookie PRÓPRIO. O que se mede aqui é que a resposta
    não mexe no cookie alheio, e que a sessão do site continua valendo depois.
    """
    na_porta.rede.alunos_aceita_o_pedido()
    antes = na_porta.client.cookies["meshcraft_sessao"].value

    resposta = pedir(na_porta)

    assert "meshcraft_sessao" not in resposta.cookies, (
        "a resposta reescreveu o cookie de sessão do SITE — quem clicar em "
        "'Pedir liberação' vai ser deslogado da plataforma inteira"
    )
    assert na_porta.client.cookies["meshcraft_sessao"].value == antes
    assert (
        na_porta.abrir().status_code == 403
    ), "a sessão do site deixou de ser reconhecida depois do pedido"


def test_o_recibo_e_de_quem_pediu_e_nao_do_navegador(rede, db, quadro):
    """Trocar de conta no mesmo navegador não pode mostrar o recibo alheio.

    É por isso que a lembrança guarda o E-MAIL, e não um `True`.
    """
    rede.alunos_nao_conhece(PESSOA)
    rede.alunos_aceita_o_pedido()
    primeira = sessao_do_site(rede, email=PESSOA)
    pedir(primeira)

    outro = "outra.pessoa@exemplo.test"
    rede.alunos_nao_conhece(outro)
    primeira.rede.site_reconhece(
        primeira.client.cookies["meshcraft_sessao"].value, email=outro
    )

    conteudo = primeira.abrir().content.decode()
    assert "Pedir liberação" in conteudo, "mostrou o recibo de outra pessoa"


# ---------------------------------------------------------------------------
# O que a tela recusa — e sem perder o que a pessoa digitou
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "campos,esperado",
    [
        pytest.param({"nome_completo": "  "}, "nome completo", id="sem-nome"),
        pytest.param({"whatsapp": ""}, "WhatsApp com DDD", id="sem-whatsapp"),
        pytest.param({"whatsapp": "99999"}, "não parece completo", id="whatsapp-curto"),
        pytest.param(
            {"comprou_em": "01/08/2026"}, "data da compra", id="data-fora-do-formato"
        ),
    ],
)
def test_pedido_incompleto_e_recusado_sem_chegar_na_alunos(na_porta, campos, esperado):
    """Nada sai para a rede: a fixture `rede` estoura em requisição não
    registrada (armadilhas/054), e aqui a da fila NÃO foi registrada."""
    resposta = pedir(na_porta, **campos)

    assert resposta.status_code == 400
    assert esperado in resposta.content.decode()
    assert na_porta.rede.pedidos == []


def test_a_recusa_devolve_o_que_a_pessoa_ja_tinha_digitado(na_porta):
    """Formulário que apaga o que a pessoa escreveu é formulário abandonado."""
    resposta = pedir(
        na_porta, whatsapp="", nome_completo="Maria da Silva", turma="Turma 3"
    )

    conteudo = resposta.content.decode()
    assert "Maria da Silva" in conteudo
    assert "Turma 3" in conteudo


def test_um_numero_de_verdade_com_formato_estranho_passa(na_porta):
    """A conferência do telefone é frouxa de propósito: ela existe para pegar
    'não tenho' e dedo escorregado, nunca para recusar um número real."""
    na_porta.rede.alunos_aceita_o_pedido()

    assert pedir(na_porta, whatsapp="+55 96 99999-0000").status_code == 200


# ---------------------------------------------------------------------------
# Quando a `alunos` não coopera — e a regra é NUNCA dizer "registrei"
# ---------------------------------------------------------------------------


def test_alunos_fora_do_ar_nao_finge_que_registrou(na_porta):
    na_porta.rede.alunos_fora_do_ar_no_pedido()

    resposta = pedir(na_porta)
    conteudo = resposta.content.decode()

    assert resposta.status_code == 503
    assert "NÃO foi registrado" in conteudo
    assert "problema nosso" in conteudo
    assert "Seu pedido já está com a gente" not in conteudo


def test_resposta_fora_do_contrato_tambem_fecha(na_porta):
    na_porta.rede.alunos_recusa_o_pedido(500)
    assert pedir(na_porta).status_code == 503


def test_payload_recusado_pela_alunos_nao_vira_recibo(na_porta):
    """422 é desacordo NOSSO com o contrato — problema de quem escreveu o
    código, não da pessoa. O que não pode acontecer é ela sair achando que está
    na fila."""
    na_porta.rede.alunos_recusa_o_pedido(422)

    resposta = pedir(na_porta)

    assert resposta.status_code == 503
    assert "Seu pedido já está com a gente" not in resposta.content.decode()


def test_depois_de_uma_falha_a_pessoa_pode_tentar_de_novo(na_porta):
    """A lembrança só é gravada quando o pedido REALMENTE entrou."""
    na_porta.rede.alunos_fora_do_ar_no_pedido()
    pedir(na_porta)

    assert "Pedir liberação" in na_porta.abrir().content.decode()


# ---------------------------------------------------------------------------
# As bordas da porta
# ---------------------------------------------------------------------------


def test_quem_ja_tem_matricula_e_mandado_para_a_porta(na_porta):
    """409 do contrato: o cache curto da porta ainda mostrava a resposta velha.
    Em no máximo um TTL ela abre sozinha."""
    na_porta.rede.alunos_ja_tem_matricula()

    resposta = pedir(na_porta)

    assert resposta.status_code == 302
    assert resposta["Location"] == reverse("entrar")


def test_quem_ja_esta_dentro_nao_entra_na_fila(dentro):
    resposta = dentro.client.post(reverse("pedir_entrada"), PEDIDO)

    assert resposta.status_code == 302
    assert resposta["Location"] == reverse("entrar")
    assert dentro.rede.pedidos == []


def test_identidade_nao_e_cunhada_por_pedir_entrada(na_porta):
    """A linha local continua nascendo só para quem PODE participar."""
    na_porta.rede.alunos_aceita_o_pedido()
    pedir(na_porta)

    assert Identidade.objects.count() == 0


def test_pedir_entrada_nao_atende_GET(na_porta):
    """POST porque cria linha na fila do mantenedor: um GET seria disparado por
    qualquer pré-carregamento de link do navegador."""
    assert na_porta.client.get(reverse("pedir_entrada")).status_code == 405


def test_a_identidade_fora_do_ar_nao_registra_pedido(na_porta):
    """Falha FECHADA também aqui: sem saber QUEM é, não há e-mail a enfileirar."""
    na_porta.rede.central_fora_do_ar()

    resposta = pedir(na_porta)

    assert resposta.status_code == 503
    assert na_porta.rede.pedidos == []


# ---------------------------------------------------------------------------
# O ex-aluno que volta — `DECISAO-a-ficha-nao-se-apaga.md` §3 (29/08/2026)
#
# A tela dele mudou (`test_a_porta_explica_por_que_nao_abriu.py`); o CAMINHO,
# não. Estes dois testes existem para provar isso: se um dia alguém der ao
# "pedir para voltar" uma rota própria, os dois reprovam — e é bom que reprovem,
# porque duas portas para o mesmo fato discordam no primeiro caso de borda.
# ---------------------------------------------------------------------------


@pytest.fixture
def ex_aluno_na_porta(rede, db, quadro):
    """Quem JÁ FOI aluno, diante da porta, querendo voltar."""
    rede.alunos_diz_ex_aluno(PESSOA)
    return sessao_do_site(rede, email=PESSOA)


def test_o_ex_aluno_que_pede_para_voltar_entra_na_mesma_fila(ex_aluno_na_porta):
    """Mesma rota, mesmo corpo, mesma fila — só o texto da tela é outro."""
    ex_aluno_na_porta.rede.alunos_aceita_o_pedido()

    resposta = pedir(ex_aluno_na_porta)

    pedido = ex_aluno_na_porta.rede.um_pedido
    assert pedido["email"] == PESSOA
    assert pedido["nome_completo"] == PEDIDO["nome_completo"]
    assert "Seu pedido já está com a gente" in resposta.content.decode()


def test_pedir_para_voltar_nao_devolve_acesso_por_si(ex_aluno_na_porta):
    """O guarda que responde ao receio da lei de ontem.

    A `DECISAO-ex-aluno-e-a-porta-que-explica` §3 tinha recusado o formulário
    temendo que ele virasse um jeito de insistir contra uma decisão. A resposta
    da lei nova é que o pedido NÃO decide nada: ele espera decisão humana, como
    o de qualquer pessoa. Depois de pedir, a pessoa continua fora — 403 e
    recibo, nunca o quadro.
    """
    ex_aluno_na_porta.rede.alunos_aceita_o_pedido()

    pedir(ex_aluno_na_porta)
    depois = ex_aluno_na_porta.abrir()

    assert depois.status_code == 403
    assert not ex_aluno_na_porta.esta_dentro


def test_um_erro_de_digitacao_nao_troca_a_tela_do_ex_aluno(ex_aluno_na_porta):
    """A tela errada volta pela porta dos fundos se o `voltando` não viajar.

    Sem ele, quem errou o WhatsApp voltaria para "não encontramos matrícula
    para esse e-mail" — a tela de quem nunca entrou — e leria, no meio de um
    erro de digitação, que a escola nunca o conheceu.
    """
    resposta = ex_aluno_na_porta.client.post(
        reverse("pedir_entrada"), {"nome_completo": "", "whatsapp": ""}
    )
    conteudo = resposta.content.decode()

    assert resposta.status_code == 400
    assert "acesso à escola foi encerrado" in conteudo
    assert "Não encontramos matrícula" not in conteudo
    assert "Pedir para voltar" in conteudo
