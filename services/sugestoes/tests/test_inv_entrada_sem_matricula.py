"""[INVARIANTE] Sem matrícula não participa — e a tela NOMEIA o e-mail.

A pessoa pode estar LOGADA NO SITE (a `identidade` a reconhece) e ainda assim
não ter voz na Caixa: entrar no site é ser reconhecido; participar daqui exige
matrícula ou crachá (`DECISAO-EVO-01` §2, preservada pela
`DECISAO-celula-de-identidade`). O e-mail na tela é a única informação que
torna a recusa resolvível pela própria pessoa (§5): quem comprou com outro
endereço precisa VER com qual entrou.
"""

from django.urls import reverse

from apps.sugestoes.models import Identidade
from tests.conftest import sessao_do_site

PESSOA = "sem.matricula@exemplo.test"


def test_logado_no_site_sem_matricula_leva_recado_com_o_email(rede, db):
    rede.alunos_nao_conhece(PESSOA)
    pessoa = sessao_do_site(rede, email=PESSOA)

    resposta = pessoa.abrir()

    assert resposta.status_code == 403, resposta.content
    conteudo = resposta.content.decode()
    assert "Não encontramos matrícula" in conteudo
    assert PESSOA in conteudo, "a tela precisa NOMEAR o e-mail (EVO-01 §5)"
    assert "Entrar com outra conta Google" in conteudo, (
        "quem levou um não precisa do botão logo abaixo para tentar com a "
        "outra conta — tela de erro sem saída é acesso negado seco"
    )


def test_lista_vazia_de_matriculas_tambem_e_recusa(rede, db):
    rede.alunos_diz(PESSOA, [])
    pessoa = sessao_do_site(rede, email=PESSOA)

    assert pessoa.abrir().status_code == 403


def test_recusa_nao_cunha_identidade_local(rede, db):
    """A linha local só nasce para quem PODE participar: cunhar na recusa
    encheria o snapshot de gente que nunca teve voz aqui."""
    rede.alunos_nao_conhece(PESSOA)
    sessao_do_site(rede, email=PESSOA).abrir()

    assert Identidade.objects.count() == 0


def test_sem_matricula_nenhuma_rota_de_participacao_roda(rede, db, quadro):
    rede.alunos_nao_conhece(PESSOA)
    pessoa = sessao_do_site(rede, email=PESSOA)

    resposta = pessoa.client.get(reverse("quadro"))
    assert resposta.status_code == 302
    assert resposta["Location"] == reverse("entrar")


def test_a_tela_de_recusa_nao_e_um_beco(rede, db):
    """A recusa precisa ter SAÍDA — auditoria de 25/08/2026.

    Antes, a única ação era "Entrar com outra conta Google", e escolher a
    MESMA conta devolvia à MESMA tela: loop, sem volta ao site e sem como
    encerrar a sessão. Quem chegava aqui vindo do site em espanhol ficava
    preso numa página em português, sem porta.
    """
    rede.alunos_nao_conhece(PESSOA)
    pessoa = sessao_do_site(rede, email=PESSOA)

    conteudo = pessoa.abrir().content.decode()

    assert 'href="/"' in conteudo, "não há volta ao site"
    assert 'action="/entrar/sair"' in conteudo, "não há como encerrar a sessão"
    assert "Entrar com outra conta Google" in conteudo, "sumiu a troca de conta"


def test_a_recusa_confirma_que_o_login_FUNCIONOU_antes_da_ma_noticia(rede, db):
    """ "Você ESTÁ no site como X" — e não "você entrou com X".

    A diferença é pequena e importante: lida depressa, a frase antiga parecia
    dizer que a ENTRADA falhou. Ela não falhou — o que faltou foi matrícula
    para esta área específica.
    """
    rede.alunos_nao_conhece(PESSOA)
    pessoa = sessao_do_site(rede, email=PESSOA)

    conteudo = pessoa.abrir().content.decode()

    assert "Você está no site como" in conteudo
    assert "área de alunos" in conteudo, "não explica que a Caixa é área de aluno"


def test_visitante_sem_sessao_nao_ve_botao_de_sair_morto(rede, db, client):
    """Quem nunca entrou não tem o que encerrar — e um botão morto é pior que
    botão nenhum."""
    conteudo = client.get("/entrar").content.decode()

    assert 'action="/entrar/sair"' not in conteudo
    assert "Entrar com Google" in conteudo
