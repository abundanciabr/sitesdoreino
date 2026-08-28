# tests/test_inv_so_staff_modera.py  # [RECEITA:R5 v1]
"""INV-SUG06 — moderar é da equipe: aluno leva 403 em toda rota de moderação.

É a Definição de Pronto do MVP em pessoa (`ESPECIFICACAO-CELULA.md` §11):
*"endpoint de avaliação de produto retorna 403 para qualquer ator sem role de
staff"*. Até o EVO-12b esse invariante tinha uma forma mais forte, porque o
endpoint não existia — nenhuma rota da célula encostava na avaliação
(`test_inv_avaliacao_interna_fora_do_alcance.py`). Agora ele existe, e a
fronteira precisa ser medida onde ela passa.

**403, e não 302 para a porta.** Quem chega aqui sem crachá não é alguém que
esqueceu de entrar: já entrou, e não tem o papel. Mandá-lo para a tela de login
seria dizer "tente de novo" a quem não tem o que tentar — e esconderia, atrás de
um redirecionamento, a única resposta que diz a verdade.

**A lista de rotas vem do urlconf**, pelo atributo `exige_staff` que o decorador
deixa no objeto da view. Rota de moderação nova nasce dentro deste guarda sem
ninguém lembrar de cadastrá-la — é o mesmo desenho de
`test_inv_sem_sessao_nada.py`, e é o que mantém as três varreduras do urlconf
cobrindo o urlconf inteiro sem sobra.
"""

import pytest
from django.urls import NoReverseMatch, reverse

from apps.sugestoes.models import AvaliacaoInterna, HistoricoStatus, Sugestao

pytestmark = pytest.mark.django_db


def _rotas_de_moderacao() -> list[str]:
    from config.urls import urlpatterns

    return [
        rota.name
        for rota in urlpatterns
        if getattr(rota.callback, "exige_staff", False)
    ]


def _endereco(nome: str, sugestao) -> str:
    try:
        return reverse(nome)
    except NoReverseMatch:
        return reverse(nome, args=[sugestao.id])


def _bater(cliente, endereco) -> dict[str, int]:
    """Os dois métodos, porque cada rota só aceita um deles.

    Quem não aceita responde 405 no `require_GET`/`require_POST`, que é de fora
    do crachá. Exigir 403 nos dois seria exigir que o porteiro rodasse em
    requisição que a rota nem aceita — o guarda mediria o decorador errado.
    """
    return {
        "GET": cliente.get(endereco).status_code,
        "POST": cliente.post(endereco, {}).status_code,
    }


def test_ha_rotas_de_moderacao_para_medir():
    """Sanidade: um guarda que varre uma lista vazia é um guarda verde à toa.

    `changespecs` entrou no EVO-40, e é a única rota da célula com um SEGUNDO
    portão em cima do crachá (o mandato de aprovador, `SUGESTOES_APROVADORES`).
    Ela é rota de moderação como as outras, e a parede que ESTE arquivo mede é
    a de fora; a de dentro tem guarda próprio em `test_changespecs.py`.

    `mesa` entrou em 28/08/2026: a porta do painel de gestão. Ela não escreve
    nada e não tem segundo portão — o botão de assinar dela some para quem não
    aprova, mas quem guarda a AÇÃO continua sendo a rota `changespecs`.
    """
    assert sorted(_rotas_de_moderacao()) == [
        "avaliar",
        "changespecs",
        "fila",
        "mesa",
        "moderar",
        "mudar_status",
    ]


def test_aluno_com_sessao_leva_403_em_TODA_rota_de_moderacao(dentro, sugestao):
    for nome in _rotas_de_moderacao():
        codigos = _bater(dentro.client, _endereco(nome, sugestao))

        assert set(codigos.values()) <= {403, 405}, f"{nome}: {codigos}"
        assert 403 in codigos.values(), (
            f"a rota '{nome}' não recusou o aluno com 403: {codigos}. "
            "Moderar é da equipe (DoD do MVP, spec §11)."
        )


def test_o_aluno_nao_muda_status_nem_escreve_avaliacao(dentro, sugestao):
    """A metade que conta linhas: o 403 não pode ser tela em cima de escrita."""
    dentro.client.post(
        reverse("mudar_status", args=[sugestao.id]),
        {"status": Sugestao.Status.IMPLEMENTADO, "nota": "eu quis"},
    )
    dentro.client.post(
        reverse("avaliar", args=[sugestao.id]),
        {"impacto_educacional": 5, "notas": "escrito por quem não podia"},
    )

    sugestao.refresh_from_db()
    assert sugestao.status == Sugestao.Status.EM_ANALISE
    assert HistoricoStatus.objects.count() == 0
    assert AvaliacaoInterna.objects.count() == 0


def test_o_aluno_nao_ve_a_fila_nem_o_texto_da_avaliacao(dentro, sugestao, aluno):
    MARCA = "DECISAO-INTERNA-QUE-O-ALUNO-NUNCA-PODE-VER"
    AvaliacaoInterna.objects.create(
        sugestao=sugestao, notas=MARCA, decisao_produto=MARCA, avaliado_por=aluno
    )

    fila = dentro.client.get(reverse("fila"))
    pagina = dentro.client.get(reverse("moderar", args=[sugestao.id]))

    assert (fila.status_code, pagina.status_code) == (403, 403)
    assert sugestao.titulo not in fila.content.decode()
    assert MARCA not in pagina.content.decode()


def test_a_equipe_alcanca_as_mesmas_rotas(equipe, sugestao, lista_de_aprovadores):
    """O outro lado da mesma parede — sem isto, um 403 para todos passaria.

    `mudar_status` e `avaliar` recebem POST vazio de propósito: o que se mede
    aqui é o crachá, e a resposta 400 ("escolha um status da lista") já prova
    que a requisição atravessou o porteiro e chegou à view.

    **Por que esta pessoa também está na lista de aprovadores (EVO-40).** A
    rota `changespecs` tem dois portões, e este teste mede o PRIMEIRO. Sem o
    mandato, o 403 do segundo portão apareceria aqui e o guarda passaria a
    afirmar que a equipe não alcança uma rota que ela alcança — medindo o
    portão errado, com a mensagem errada. O segundo portão tem guarda dedicado
    (`test_changespecs.py::test_staff_que_nao_e_aprovador_leva_403`), e a
    lista continua nascendo VAZIA para todo o resto da suíte.
    """
    lista_de_aprovadores(equipe.email)

    for nome in _rotas_de_moderacao():
        codigos = _bater(equipe.client, _endereco(nome, sugestao))
        assert 403 not in codigos.values(), f"a equipe levou 403 em '{nome}': {codigos}"


def test_o_cracha_sai_com_a_variavel_de_ambiente(
    equipe, sugestao, monkeypatch, rede, matricula
):
    """O papel é DERIVADO a cada requisição (DECISAO-EVO-01 §4), nunca gravado.

    A promessa da decisão é "editar uma variável no servidor e reiniciar, sem
    migração e sem deploy". Se o papel viajasse no cookie, na linha local ou na
    resposta da `identidade`, tirar alguém da lista não tiraria o crachá de
    quem já estava dentro — e a promessa seria falsa no dia em que importa.

    Desde a mudança de casa do login a queda é ainda mais dura: quem sai da
    lista volta a ser conferido como aluno na `alunos`, NA REQUISIÇÃO SEGUINTE
    (antes, a matrícula só era conferida no login — o ex-staff sem matrícula
    ficava dentro até sair sozinho).
    """
    assert equipe.client.get(reverse("fila")).status_code == 200

    monkeypatch.delenv("SUGESTOES_STAFF_EMAILS")

    # Com matrícula, o ex-staff segue DENTRO — como aluno, sem moderação.
    rede.alunos_diz("equipe@meshcraft.test", [matricula])
    assert equipe.client.get(reverse("fila")).status_code == 403
    assert equipe.esta_dentro, "a sessão continua aberta — o que caiu foi o papel"
