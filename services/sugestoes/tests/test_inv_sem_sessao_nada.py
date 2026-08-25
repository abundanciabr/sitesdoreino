# tests/test_inv_sem_sessao_nada.py  # [RECEITA:R5 v1]
"""INV-SUG05 — sem sessão de aluno, nenhuma rota de participação acontece.

A Caixa é de quem tem matrícula (`DECISAO-EVO-01-identidade.md` §2): o Google
prova quem é, a `alunos` decide se pode. Se qualquer rota daqui respondesse a
anônimo, essa decisão inteira viraria enfeite — bastaria pular a porta.

**O guarda deriva a lista de rotas do próprio urlconf**, e é isso que o torna
durável: rota de participação nova nasce dentro dele, sem ninguém precisar
lembrar de cadastrá-la. As rotas públicas são poucas, nomeadas abaixo, e a
lista é conferida nos dois sentidos — uma rota que SAIA da lista pública sem
ganhar o decorador também derruba o guarda.

Detalhe que faz este teste medir o que promete: o `Client` do Django não impõe
CSRF por padrão (`enforce_csrf_checks=False`). Sem isso, todo POST anônimo
tomaria 403 do `CsrfViewMiddleware` **antes** de chegar à view, e o guarda
ficaria verde sem nunca ter testado o porteiro.
"""

import pytest
from django.urls import NoReverseMatch, URLPattern, URLResolver, reverse

from apps.sugestoes.models import Comentario, Sugestao, Voto

pytestmark = pytest.mark.django_db

# A porta e a sonda: tudo que existe para quem ainda não entrou (ou nunca
# entra, no caso do /healthz, que é máquina falando com máquina).
PUBLICAS = {"entrar", "entrar_google", "entrar_google_retorno", "sair", None}

# A superfície de MÁQUINA da célula (DECISAO-onde-mora-a-sessao): montada por
# `include()`, e por isso um `URLResolver` — não um `URLPattern` com callback.
# Ela fica fora do porteiro de SESSÃO de propósito, porque responde a uma
# pergunta diferente: quem CHAMA (Bearer do par), e não quem é a PESSOA.
#
# **Declarada aqui, nunca inferida.** Se o guarda simplesmente ignorasse todo
# `URLResolver`, bastaria alguém montar páginas por `include()` para a
# participação inteira sair da varredura sem ninguém notar — e o guarda
# continuaria verde. Por isso a lista é conferida por igualdade EXATA abaixo, e
# a proteção alternativa é medida do lado de fora, não prometida em comentário.
MONTAGENS_DE_MAQUINA = {"interno/"}


def _rotas():
    """Só as rotas de GENTE — as que têm view própria e porteiro de sessão."""
    from config.urls import urlpatterns

    return [rota for rota in urlpatterns if isinstance(rota, URLPattern)]


def test_toda_montagem_incluida_e_declarada_e_fechada_por_bearer(client):
    """O outro lado de `_rotas()`: o que ela filtra não pode ficar sem guarda.

    Duas afirmações, e as duas precisam ser verdade:

    1. **Nada entrou por `include()` sem declaração.** Igualdade exata, não
       `issubset` — montagem nova derruba este teste e obriga quem a criou a
       dizer aqui o que ela é e por que está fora do porteiro de sessão.
    2. **A montagem declarada é mesmo fechada**, medida como qualquer um a
       veria: sem o Bearer do par, 401. Sem esta metade, o item 1 viraria uma
       licença para tirar rota da varredura escrevendo o nome dela numa lista.
    """
    from config.urls import urlpatterns

    incluidas = {
        str(rota.pattern) for rota in urlpatterns if isinstance(rota, URLResolver)
    }
    assert incluidas == MONTAGENS_DE_MAQUINA, (
        f"montagens por include() no urlconf: {sorted(incluidas)}, declaradas: "
        f"{sorted(MONTAGENS_DE_MAQUINA)}. Montagem nova fica FORA da varredura "
        "de porteiro — declare-a aqui e prove que ela tem guarda própria."
    )

    anonimo = client.get("/interno/sessao")
    assert anonimo.status_code == 401, (
        "a superfície de máquina respondeu "
        f"{anonimo.status_code} a quem não apresentou o token do par."
    )


def _endereco(nome: str, sugestao) -> str:
    try:
        return reverse(nome)
    except NoReverseMatch:
        return reverse(nome, args=[sugestao.id])


def test_toda_rota_nao_publica_carrega_o_porteiro():
    """A metade estática: o decorador está lá, em TODAS elas.

    Vale por si — uma rota que perca o `@exige_sessao` numa refatoração cai
    aqui mesmo que ninguém tenha escrito um teste de comportamento para ela.
    """
    desprotegidas = [
        rota.name
        for rota in _rotas()
        if rota.name not in PUBLICAS
        and not getattr(rota.callback, "exige_sessao", False)
    ]

    assert desprotegidas == [], (
        f"rotas sem @exige_sessao: {desprotegidas}. Toda participação exige "
        "sessão de aluno (DECISAO-EVO-01 §2)."
    )


def test_anonimo_e_mandado_para_a_porta_em_toda_rota_de_participacao(client, sugestao):
    """A metade de comportamento: o anônimo bate e é devolvido, em cada uma."""
    protegidas = [r.name for r in _rotas() if r.name not in PUBLICAS]
    assert protegidas, "o guarda não encontrou nenhuma rota protegida para medir"

    for nome in protegidas:
        endereco = _endereco(nome, sugestao)
        for resposta in (client.get(endereco), client.post(endereco, {})):
            assert resposta.status_code in (
                302,
                405,
            ), f"{nome} respondeu {resposta.status_code} a um anônimo"
            if resposta.status_code == 302:
                assert resposta["Location"] == reverse("entrar"), nome


def test_anonimo_nao_cria_sugestao_voto_nem_comentario(client, sugestao, categoria):
    antes = (Sugestao.objects.count(), Voto.objects.count(), Comentario.objects.count())

    client.post(
        reverse("nova_sugestao"),
        {
            "titulo": "Sugestão de quem não entrou",
            "problema": "nenhum",
            "categoria": "curso",
            "publicar": "1",
        },
    )
    client.post(reverse("votar", args=[sugestao.id]))
    client.post(reverse("comentar", args=[sugestao.id]), {"texto": "oi"})

    assert (
        Sugestao.objects.count(),
        Voto.objects.count(),
        Comentario.objects.count(),
    ) == antes


def test_anonimo_nao_ve_o_quadro_nem_o_texto_de_uma_sugestao(client, sugestao):
    """Nem LER é público: o quadro é a conversa de quem está matriculado."""
    quadro = client.get(reverse("quadro"))
    pagina = client.get(reverse("sugestao", args=[sugestao.id]))

    assert quadro.status_code == 302
    assert pagina.status_code == 302
    assert sugestao.titulo not in quadro.content.decode()
    assert sugestao.problema not in pagina.content.decode()


def test_depois_de_sair_a_pessoa_volta_a_ser_anonima(dentro, sugestao):
    """A sessão encerrada vale para a participação inteira, não só para a porta."""
    assert dentro.client.get(reverse("quadro")).status_code == 200

    dentro.client.post(reverse("sair"))

    assert dentro.client.get(reverse("quadro")).status_code == 302
    assert dentro.client.post(reverse("votar", args=[sugestao.id])).status_code == 302
    assert Voto.objects.count() == 0


def test_sessao_revogada_na_identidade_nao_vale_mais_aqui(dentro, sugestao):
    """A revogação mudou de casa junto com o login (25/08/2026).

    Antes, apagar a linha local derrubava o cookie na hora. Hoje a linha local
    é SNAPSHOT (renasce do casamento por e-mail — apagar ela não revoga nada);
    quem revoga é a `identidade`, e o que este guarda prova é que a revogação
    DE LÁ vale AQUI no request seguinte: sessão que o site não reconhece mais
    não participa de nada.
    """
    from apps.core import sessao as ses

    dentro.rede.sessoes.clear()  # a identidade "esqueceu" esta sessão
    ses.limpar_caches()  # e a janela de cache desta célula acabou

    assert dentro.client.get(reverse("quadro")).status_code == 302
    assert dentro.client.post(reverse("votar", args=[sugestao.id])).status_code == 302
    assert Voto.objects.count() == 0
