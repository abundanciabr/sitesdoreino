"""O reembolso tira o acesso — `docs/decisoes/DECISAO-reembolso-tira-o-acesso.md`.

**A regra já foi decidida DUAS vezes, em sentidos opostos, e é por isso que este
arquivo existe.** Em 24/08/2026 o mantenedor decidiu que `reembolsada` continua
dando acesso (*"quem já foi aluno mantém a voz"*); em 31/08/2026 ele mesmo
reverteu, ao encontrar o texto antigo publicado no site. Uma terceira mudança é
decisão dele, **nunca de um despacho**.

Se você chegou aqui achando que `reembolsada` fora de `STATUS_QUE_VALEM` é um
bug esquecido: não é. Leia a lei antes de "consertar".

**O que este arquivo mede, e que nenhum outro mede sozinho:**

1. a ficha reembolsada não abre a porta de acesso (`STATUS_QUE_VALEM`);
2. a pessoa é NOMEADA como `reembolsado` — e não cai em `cadastrado`, que seria
   mentira sobre ela e a devolveria ao formulário de pedir entrada como se
   nunca tivesse tido ficha;
3. a ficha CONTINUA existindo, porque a decisão foi *"só o acesso acaba"*;
4. o reembolsado não entra na fila, e a recusa mora na PORTA — não só na tela
   que esconde o formulário;
5. o ex-aluno continua podendo voltar, que é o que faz do item 4 uma decisão e
   não um corte por descuido.

**O item 3 é o que separa esta lei da de apagar.** Ele foi oferecido ao
mantenedor (`apagar a ficha de vez`) e recusado: a `DECISAO-a-ficha-nao-se-apaga.md`
continua valendo por inteiro.
"""

import pytest
from django.utils import timezone

from apps.matriculas.models import Matricula
from apps.matriculas.services import entrar_na_fila, matriculas_que_valem, situacao_de

ALGUEM = "reembolsado@example.com"


@pytest.fixture
def token_valido(settings):
    settings.TOKENS_ACEITOS = {"token-de-teste"}
    return "token-de-teste"


@pytest.fixture
def auth(token_valido):
    return {"HTTP_AUTHORIZATION": f"Bearer {token_valido}"}


def linha(email=ALGUEM, **campos):
    corpo = {
        "site_id": "site-1",
        "order_id": f"pedido-{campos.get('status', 'x')}-{timezone.now().timestamp()}",
        "email": email,
        "name": "Quem Pediu Reembolso",
        "status": Matricula.STATUS_REEMBOLSADA,
    }
    corpo.update(campos)
    return Matricula.objects.create(**corpo)


# ------------------------------------------------------------------ a decisão


def test_reembolsada_esta_fora_da_lista_que_da_acesso():
    """A asserção mais direta que existe sobre esta lei, e é de propósito.

    Ela não passa por HTTP, nem por banco: mede a CONSTANTE. Um teste de
    comportamento poderia continuar verde por um caminho lateral (um filtro
    escrito à mão em algum handler); este só fica verde se a fonte única da
    regra disser o que a lei diz.
    """
    assert Matricula.STATUS_REEMBOLSADA not in Matricula.STATUS_QUE_VALEM
    assert Matricula.STATUS_QUE_VALEM == (Matricula.STATUS_ATIVA,)
    # E o outro lado da mesma decisão: quem não dá acesso está declarado.
    assert Matricula.STATUS_REEMBOLSADA in Matricula.STATUS_SEM_ACESSO


@pytest.mark.django_db
def test_a_ficha_reembolsada_nao_abre_a_porta_de_acesso():
    linha()
    assert not matriculas_que_valem(ALGUEM).exists()


@pytest.mark.django_db
def test_a_pessoa_e_nomeada_reembolsada_e_nunca_cai_em_cadastrado():
    """O erro que esta categoria nasceu para não repetir.

    Até 28/08/2026 quem saía da escola voltava como `cadastrado`, e via o
    formulário de pedir entrada como se nunca tivesse pedido nada. Foi o
    mantenedor quem encontrou aquilo, na própria conta. A categoria nova evita
    a mesma tela errada para quem foi reembolsado — e a asserção é NOMINAL,
    porque `!= "aluno"` passaria com `cadastrado` também.
    """
    linha()
    assert situacao_de(ALGUEM) == {"categoria": "reembolsado", "na_fila": None}


@pytest.mark.django_db
def test_so_o_acesso_acaba_e_a_ficha_continua_guardada():
    """A escolha explícita do mantenedor entre apagar e só tirar o acesso.

    Ele escolheu não apagar. Sem este teste, uma "limpeza" futura poderia
    passar a apagar a linha no reembolso e nada ficaria vermelho — e a linha é
    o que permite desfazer um reembolso lançado por engano, além de ser o que a
    `DECISAO-a-ficha-nao-se-apaga.md` promete a quem estuda aqui.
    """
    alvo = linha()
    assert Matricula.objects.filter(pk=alvo.pk).exists()
    assert Matricula.objects.get(pk=alvo.pk).status == Matricula.STATUS_REEMBOLSADA
    # Continua administrável pelo painel: é lá que ele religa com um clique.
    assert Matricula.STATUS_REEMBOLSADA in Matricula.STATUS_DE_GESTAO
    # E o prontuário continua sabendo que esta pessoa JÁ TEVE acesso um dia.
    assert Matricula.STATUS_REEMBOLSADA in Matricula.STATUS_QUE_JA_DERAM_ACESSO


# ------------------------------------------------ a fila, e as duas direções


@pytest.mark.django_db
def test_o_reembolsado_nao_entra_na_fila_pela_porta():
    """A decisão de "sem formulário de voltar" tem mecanismo, e não só HTML.

    A tela da Caixa esconde o formulário do reembolsado. Se a recusa vivesse só
    lá, um POST direto nesta porta a furaria — e regra que só existe em
    template é garantia sem mecanismo (`RETROSPECTIVA-FASE-D` §2), o segundo
    modo de falha mais frequente deste projeto.
    """
    linha()
    resultado, criada = entrar_na_fila(
        site_id="site-1",
        email=ALGUEM,
        nome_completo="Quem Pediu Reembolso",
        whatsapp="96999990000",
    )
    assert resultado is None and criada is False
    assert not Matricula.objects.filter(status=Matricula.STATUS_AGUARDANDO).exists()


@pytest.mark.django_db
def test_o_ex_aluno_continua_podendo_pedir_para_voltar():
    """O contraste que torna o teste acima uma DECISÃO, e não um corte.

    `encerrada` está fora de `STATUS_QUE_BARRAM_A_FILA` de propósito
    (`DECISAO-a-ficha-nao-se-apaga.md` §3): a escola é um lugar de onde se sai e
    para onde se volta. Sem este teste, alguém poderia "simplificar" a lista
    para *"todo mundo que já teve ficha"* e o ex-aluno perderia o caminho de
    volta sem que nada ficasse vermelho.
    """
    linha(email="ex-aluno@example.com", status=Matricula.STATUS_ENCERRADA)
    resultado, criada = entrar_na_fila(
        site_id="site-1",
        email="ex-aluno@example.com",
        nome_completo="Ex Aluno",
        whatsapp="96999990001",
    )
    assert resultado is not None
    assert resultado.status == Matricula.STATUS_AGUARDANDO


@pytest.mark.django_db
def test_quem_ja_tem_acesso_continua_barrado_pela_razao_de_sempre():
    """A metade ANTIGA do 409, que a metade nova não pode ter atropelado.

    `STATUS_QUE_BARRAM_A_FILA` cresceu; se alguém a tivesse escrito como
    `(STATUS_REEMBOLSADA,)` em vez de derivar de `STATUS_QUE_VALEM`, o aluno
    ativo passaria a poder entrar na fila — e apareceria no painel do
    mantenedor como se esperasse por uma decisão que já foi tomada.
    """
    linha(email="ativo@example.com", status=Matricula.STATUS_ATIVA)
    resultado, criada = entrar_na_fila(
        site_id="site-1",
        email="ativo@example.com",
        nome_completo="Aluno Ativo",
        whatsapp="96999990002",
    )
    assert resultado is None and criada is False


# ------------------------------------------------------------ o contrato vivo


@pytest.mark.django_db
def test_a_porta_de_matriculas_nao_devolve_mais_a_reembolsada(client, auth):
    """404, e não 200 com lista vazia: a porta responde sobre QUEM É ALUNO.

    Quem pergunta aqui está decidindo acesso, e uma lista vazia com 200 seria
    lida por um consumidor desatento como "consegui perguntar e não há nada" —
    que é o mesmo que 404 diz, mas por um caminho onde um bug de serialização
    passaria despercebido.
    """
    linha()
    assert client.get(
        f"/api/alunos/alunos/{ALGUEM}/matriculas", **auth
    ).status_code == (404)
