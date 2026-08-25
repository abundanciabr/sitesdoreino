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
