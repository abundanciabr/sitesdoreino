"""A participação do aluno, de ponta a ponta — o comportamento do EVO-12b.

Os invariantes têm arquivo próprio (`test_inv_*.py`); aqui está o que a
`ESPECIFICACAO-CELULA.md` §10 promete ao aluno e que nenhum invariante cobre:
o ranking por total de votos, o filtro por categoria, a busca de possíveis
duplicatas ANTES de publicar, e a jornada inteira de uma pessoa numa sessão só.

A sessão vem sempre da porta de verdade (fixture `entrar_como`, que clica no
botão com o Google e a `alunos` dublados). Nenhum teste desta suíte assina um
cookie na mão: um atalho aqui seria uma suíte que continua verde no dia em que
a entrada parar de funcionar.
"""

import pytest
from django.urls import reverse

from apps.sugestoes.models import Categoria, Comentario, Sugestao, Voto

pytestmark = pytest.mark.django_db


def _conferir(cliente, titulo: str, **extra):
    """A primeira etapa do formulário: mostra parecidas, não cria nada."""
    return cliente.post(
        reverse("nova_sugestao"),
        {"titulo": titulo, "problema": "Doi assim.", "categoria": "curso", **extra},
    )


def _publicar(cliente, titulo: str, **extra):
    return _conferir(cliente, titulo, publicar="1", **extra)


def _ordem_no_quadro(corpo: str, titulos: list[str]) -> list[str]:
    """A ordem em que os títulos aparecem no HTML — o que a pessoa vê."""
    return sorted(titulos, key=corpo.index)


# ---------------------------------------------------------------------------
# A jornada inteira, numa sessão só (DoD do despacho)
# ---------------------------------------------------------------------------


def test_uma_sessao_de_aluno_de_ponta_a_ponta(entrar_como, categoria):
    aluno = entrar_como("joao.silva@exemplo.test", "João")

    # 1. o quadro, ainda vazio
    quadro = aluno.client.get(reverse("quadro"))
    assert quadro.status_code == 200
    assert "Ainda não há sugestões" in quadro.content.decode()

    # 2. conferir duplicatas — nada parecido, e nada criado
    conferencia = _conferir(aluno.client, "Legendas nas aulas")
    assert conferencia.status_code == 200
    assert "Nada parecido no quadro" in conferencia.content.decode()
    assert Sugestao.objects.count() == 0

    # 3. publicar
    criacao = _publicar(aluno.client, "Legendas nas aulas")
    assert criacao.status_code == 302
    sugestao = Sugestao.objects.get(titulo="Legendas nas aulas")
    assert criacao["Location"] == reverse("sugestao", args=[sugestao.id])
    assert sugestao.autor_id == aluno.identidade.id

    # 4. votar
    assert aluno.client.post(reverse("votar", args=[sugestao.id])).status_code == 302
    assert Voto.objects.filter(sugestao=sugestao).count() == 1

    # 5. desvotar — a linha some
    assert aluno.client.post(reverse("desvotar", args=[sugestao.id])).status_code == 302
    assert Voto.objects.filter(sugestao=sugestao).count() == 0

    # 6. votar de novo e comentar
    aluno.client.post(reverse("votar", args=[sugestao.id]))
    comentario = aluno.client.post(
        reverse("comentar", args=[sugestao.id]), {"texto": "Assisto no ônibus."}
    )
    assert comentario.status_code == 302
    assert Comentario.objects.get(sugestao=sugestao).texto == "Assisto no ônibus."

    # 7. a página da sugestão mostra tudo o que ele fez
    pagina = aluno.client.get(reverse("sugestao", args=[sugestao.id])).content.decode()
    assert "Legendas nas aulas" in pagina
    assert "Assisto no ônibus." in pagina
    assert "Tirar meu voto" in pagina

    # 8. e o quadro mostra a sugestão com o voto contado
    final = aluno.client.get(reverse("quadro")).content.decode()
    assert "Legendas nas aulas" in final
    assert "Ainda não há sugestões" not in final


# ---------------------------------------------------------------------------
# O ranking por total de votos (§10)
# ---------------------------------------------------------------------------


def test_o_quadro_vem_ordenado_por_total_de_votos(entrar_como, categoria):
    autor = entrar_como("autor@exemplo.test", "Autor")
    _publicar(autor.client, "A menos votada")
    _publicar(autor.client, "A mais votada")
    _publicar(autor.client, "A do meio")
    ids = {s.titulo: s.id for s in Sugestao.objects.all()}

    for numero in range(3):
        pessoa = entrar_como(f"votante{numero}@exemplo.test", f"Votante {numero}")
        pessoa.client.post(reverse("votar", args=[ids["A mais votada"]]))
        if numero < 1:
            pessoa.client.post(reverse("votar", args=[ids["A do meio"]]))

    corpo = autor.client.get(reverse("quadro")).content.decode()

    assert _ordem_no_quadro(corpo, list(ids)) == [
        "A mais votada",
        "A do meio",
        "A menos votada",
    ]


def test_o_empate_e_desfeito_pela_mais_antiga(entrar_como, categoria):
    """Sem desempate determinístico o quadro "muda sozinho" entre dois cliques."""
    autor = entrar_como("autor@exemplo.test", "Autor")
    _publicar(autor.client, "Chegou primeiro")
    _publicar(autor.client, "Chegou depois")

    corpo = autor.client.get(reverse("quadro")).content.decode()

    assert _ordem_no_quadro(corpo, ["Chegou depois", "Chegou primeiro"]) == [
        "Chegou primeiro",
        "Chegou depois",
    ]


def test_o_voto_de_outra_pessoa_conta_no_quadro_de_quem_olha(entrar_como, categoria):
    autor = entrar_como("autor@exemplo.test", "Autor")
    _publicar(autor.client, "Pedido do autor")
    sugestao = Sugestao.objects.get()

    outra = entrar_como("outra@exemplo.test", "Outra")
    outra.client.post(reverse("votar", args=[sugestao.id]))

    corpo = autor.client.get(reverse("quadro")).content.decode()

    # Um voto contado, mas o botão de quem olha continua sendo "Votar" — o voto
    # é do ator da sessão, não do quadro.
    assert '<span class="votos">1</span>' in corpo
    assert "Tirar meu voto" not in corpo


# ---------------------------------------------------------------------------
# O filtro por categoria (§10)
# ---------------------------------------------------------------------------


def test_o_quadro_filtra_por_categoria(entrar_como, quadro, categoria):
    Categoria.objects.create(quadro=quadro, slug="blender", nome="Blender")
    autor = entrar_como("autor@exemplo.test", "Autor")
    _publicar(autor.client, "Coisa de curso", categoria="curso")
    _publicar(autor.client, "Coisa de Blender", categoria="blender")

    so_curso = autor.client.get(f"{reverse('quadro')}?categoria=curso").content.decode()

    assert "Coisa de curso" in so_curso
    assert "Coisa de Blender" not in so_curso


def test_categoria_inexistente_no_filtro_e_404(dentro, categoria):
    assert (
        dentro.client.get(f"{reverse('quadro')}?categoria=inventada").status_code == 404
    )


def test_categoria_desativada_some_da_criacao_mas_nao_invalida_o_que_existe(
    entrar_como, quadro, categoria
):
    """Spec §9: desativar OCULTA da criação; a sugestão antiga continua de pé."""
    antiga = Categoria.objects.create(quadro=quadro, slug="antiga", nome="Antiga")
    autor = entrar_como("autor@exemplo.test", "Autor")
    _publicar(autor.client, "Feita quando dava", categoria="antiga")

    Categoria.objects.filter(pk=antiga.pk).update(ativa=False)

    formulario = autor.client.get(reverse("nova_sugestao")).content.decode()
    assert 'value="antiga"' not in formulario

    recusa = _publicar(autor.client, "Tarde demais", categoria="antiga")
    assert recusa.status_code == 400
    assert not Sugestao.objects.filter(titulo="Tarde demais").exists()

    assert "Feita quando dava" in autor.client.get(reverse("quadro")).content.decode()


# ---------------------------------------------------------------------------
# A busca de possíveis duplicatas, ANTES de publicar (§10)
# ---------------------------------------------------------------------------


def test_a_conferencia_mostra_a_parecida_e_nao_cria_nada(entrar_como, categoria):
    autor = entrar_como("autor@exemplo.test", "Autor")
    _publicar(autor.client, "Legendas nas aulas gravadas")
    assert Sugestao.objects.count() == 1

    outra = entrar_como("outra@exemplo.test", "Outra")
    conferencia = _conferir(outra.client, "Colocar legendas nos vídeos")

    corpo = conferencia.content.decode()
    assert conferencia.status_code == 200
    assert "Isto já foi sugerido?" in corpo
    assert "Legendas nas aulas gravadas" in corpo
    assert Sugestao.objects.count() == 1  # a conferência não publica


def test_depois_de_conferir_a_pessoa_publica_assim_mesmo(entrar_como, categoria):
    """A busca informa; não bloqueia. Duas dores parecidas são duas dores."""
    autor = entrar_como("autor@exemplo.test", "Autor")
    _publicar(autor.client, "Legendas nas aulas gravadas")

    outra = entrar_como("outra@exemplo.test", "Outra")
    _conferir(outra.client, "Legendas nos vídeos ao vivo")
    publicacao = _publicar(outra.client, "Legendas nos vídeos ao vivo")

    assert publicacao.status_code == 302
    assert Sugestao.objects.count() == 2


def test_palavra_curta_demais_nao_casa_com_o_quadro_inteiro(entrar_como, categoria):
    """ "de", "com", "nas" casariam com tudo — e o que sempre casa não avisa nada."""
    autor = entrar_como("autor@exemplo.test", "Autor")
    _publicar(autor.client, "Exportar do Blender para o Studio")

    conferencia = _conferir(autor.client, "Um som de ar")

    assert "Nada parecido no quadro" in conferencia.content.decode()


def test_a_busca_nao_distingue_maiusculas(entrar_como, categoria):
    """`icontains`, não `contains`: quem escreve tudo em minúscula acha igual."""
    autor = entrar_como("autor@exemplo.test", "Autor")
    _publicar(autor.client, "Legendas nas aulas gravadas")

    corpo = _conferir(autor.client, "LEGENDAS por favor").content.decode()

    assert "Legendas nas aulas gravadas" in corpo


def test_a_busca_tambem_olha_o_texto_do_problema(entrar_como, categoria):
    """O título é curto; a dor está descrita embaixo dele."""
    autor = entrar_como("autor@exemplo.test", "Autor")
    autor.client.post(
        reverse("nova_sugestao"),
        {
            "titulo": "Assistir sem som",
            "problema": "Preciso de legendas no ônibus.",
            "categoria": "curso",
            "publicar": "1",
        },
    )

    corpo = _conferir(autor.client, "Legendas nos vídeos").content.decode()

    assert "Assistir sem som" in corpo


# ---------------------------------------------------------------------------
# O que o formulário recusa
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "campo,valor",
    [("titulo", ""), ("problema", ""), ("categoria", "nao-existe")],
)
def test_sugestao_incompleta_e_recusada_sem_gravar(dentro, categoria, campo, valor):
    dados = {
        "titulo": "Um título",
        "problema": "Um problema.",
        "categoria": "curso",
        "publicar": "1",
        campo: valor,
    }

    resposta = dentro.client.post(reverse("nova_sugestao"), dados)

    assert resposta.status_code == 400
    assert Sugestao.objects.count() == 0


def test_titulo_longo_demais_e_recusado(dentro, categoria):
    resposta = _publicar(dentro.client, "x" * 141)

    assert resposta.status_code == 400
    assert Sugestao.objects.count() == 0


def test_comentario_vazio_e_recusado_sem_gravar(dentro, sugestao):
    resposta = dentro.client.post(
        reverse("comentar", args=[sugestao.id]), {"texto": "   "}
    )

    assert resposta.status_code == 400
    assert Comentario.objects.count() == 0


def test_votar_numa_sugestao_que_nao_existe_e_404(dentro, categoria):
    assert dentro.client.post(reverse("votar", args=[99999])).status_code == 404


# ---------------------------------------------------------------------------
# O quadro, enquanto não existe CONV-SITE
# ---------------------------------------------------------------------------


def test_sem_quadro_semeado_a_caixa_diz_o_que_falta(dentro):
    """Fail-closed com diagnóstico — nunca uma página vazia sem explicação."""
    assert dentro.client.get(reverse("quadro")).status_code == 404


def test_com_dois_quadros_a_celula_para_em_vez_de_escolher_um(dentro, quadro):
    """Escolher "o primeiro" seria inventar um site padrão em silêncio (Lei 9)."""
    from apps.sugestoes.models import Quadro

    Quadro.objects.create(site_id="outro-site", nome="Quadro de outro site")

    assert dentro.client.get(reverse("quadro")).status_code == 404
