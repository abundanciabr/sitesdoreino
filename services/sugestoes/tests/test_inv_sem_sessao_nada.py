# tests/test_inv_sem_sessao_nada.py  # [RECEITA:R5 v1]
"""Sem sessão de aluno, nenhuma rota de participação acontece.
A lista de rotas vem do urlconf; as públicas são poucas e declaradas aqui."""

import pytest
from django.urls import NoReverseMatch, URLPattern, URLResolver, reverse

from apps.sugestoes.models import Comentario, Sugestao, Voto

pytestmark = pytest.mark.django_db

# Rotas públicas: porta, sonda, CSS e pedido de entrada servem quem não tem sessão.
# `avisos` só redireciona para `/notificacoes`, que exige a sessão.
PUBLICAS = {
    "entrar",
    "entrar_google",
    "entrar_google_retorno",
    "pedir_entrada",
    "sair",
    "estatico",
    "avisos",
    None,
}

# Montagens por `include()` são a superfície de máquina (Bearer do par).
# A lista é conferida por igualdade exata e a proteção é medida de fora.
MONTAGENS_DE_MAQUINA = {"interno/"}


def _rotas():
    """Só as rotas de GENTE — as que têm view própria e porteiro de sessão."""
    from config.urls import urlpatterns

    return [rota for rota in urlpatterns if isinstance(rota, URLPattern)]


def test_toda_montagem_incluida_e_declarada_e_fechada_por_bearer(client):
    """Toda montagem por `include()` é declarada aqui e fechada: sem o Bearer do par,
    401."""
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
    """Toda rota fora de `PUBLICAS` carrega `@exige_sessao`."""
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


def test_a_rota_publica_de_estatico_so_serve_estatico(client):
    """O anônimo recebe a folha de estilo e nada mais: nenhuma fuga da árvore de
    estáticos."""
    css = client.get(reverse("estatico", kwargs={"caminho": "sugestoes/caixa.css"}))
    assert css.status_code == 200, "o rosto não é servido — em produção seria 404"
    assert b"--laranja" in b"".join(css.streaming_content)

    for fuga in ("../config/settings.py", "sugestoes/../../config/settings.py"):
        escapou = client.get(f"/static/{fuga}")
        assert escapou.status_code != 200, (
            f"/static/{fuga} respondeu 200: a rota pública saiu da árvore de "
            "estáticos e virou leitor de arquivos da célula."
        )


def test_a_rota_publica_de_pedido_de_entrada_nao_deixa_anonimo_entrar_na_fila(
    client, rede
):
    """Anônimo sem sessão do site volta à porta antes de qualquer chamada à `alunos`."""
    resposta = client.post(
        reverse("pedir_entrada"),
        {"nome_completo": "Robô Anônimo", "whatsapp": "(96) 99999-0000"},
    )

    assert resposta.status_code == 302
    assert resposta["Location"] == reverse("entrar")


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
    """A revogação feita na `identidade` vale aqui no request seguinte."""
    from apps.core import sessao as ses

    dentro.rede.sessoes.clear()  # a identidade "esqueceu" esta sessão
    ses.limpar_caches()  # e a janela de cache desta célula acabou

    assert dentro.client.get(reverse("quadro")).status_code == 302
    assert dentro.client.post(reverse("votar", args=[sugestao.id])).status_code == 302
    assert Voto.objects.count() == 0
