"""As restrições do banco de conteúdo, e a prova de que elas MORDEM, uma a uma.

Cada `UniqueConstraint`, cada `CheckConstraint` e a chave estrangeira composta
de `apps/cursos/models.py` e da migração `0001` existe porque uma regra que vive
só em código Python é uma promessa: basta um `objects.update()` na tela do
Admin (degrau 1.5), uma migração de dados ou um `psql` de madrugada para a
combinação proibida existir sem ninguém saber (`armadilhas/023`, `274`). Este
arquivo confere que o PostgreSQL recusa.

E mede o semeador pelo caminho da instalação (`call_command`): as contagens do
esqueleto, a distribuição das aulas pelos blocos, os 13 instrumentos da lei, e
a idempotência.

As tabelas da lei (a distribuição, os instrumentos, a ordem das 16 peças) estão
TRANSCRITAS aqui, de propósito, e não importadas do semeador nem do modelo: um
teste que importa a resposta do arquivo que ele mede não mede nada.
"""

from io import StringIO

import pytest
from django.apps import apps
from django.core.management import call_command
from django.db import IntegrityError

from apps.cursos.models import Aula, Bloco, Curso, Instrumento, Pausa, Peca

SITE = "escola-a"

# O plano §4, transcrito: as 16 peças da anatomia, na ordem canônica.
AS_16_PECAS_NA_ORDEM = (
    "pedido",
    "em_jogo",
    "voce_vai_conseguir",
    "recall",
    "par_de_comparacao",
    "erro_produtivo",
    "eu_faco",
    "nos_fazemos",
    "voce_faz",
    "drills",
    "erros_classicos",
    "regra_do_padrao",
    "critica_de_atelier",
    "checkpoint",
    "pagina_do_portfolio",
    "dicionario_cartao_respostas",
)
AS_2_INTERNAS = ("roteiro", "guia_do_mentor")
AS_SOB_DEMANDA = ("videoaula_em_texto",)

# O despacho do degrau 1.2, transcrito: letra -> (parte, aulas).
A_DISTRIBUICAO = {
    "A": (1, ["E00", "E01", "E02"]),
    "B": (1, ["E03", "E04", "E05"]),
    "C": (1, ["E06", "E07", "E08"]),
    "D": (1, ["E09", "E10"]),
    "E": (2, ["E11", "E12", "E13", "E14"]),
    "F": (2, ["E15", "E16"]),
    "G": (2, ["E17", "E18"]),
    "H": (2, ["E19", "E20", "E21"]),
    "I": (3, ["E22", "E23", "E24", "E25"]),
    "J": (3, ["E26", "E27"]),
    "K": (3, ["E28", "E29", "E30"]),
    "L": (3, ["E31", "E32", "EB"]),
}

# O plano §4, transcrito: slug -> (nome canônico, cartão).
OS_13_INSTRUMENTOS = {
    "studs": ("Teste STUDS", 1),
    "rubrica_de_encomenda": ("Rubrica de Encomenda", 2),
    "rubrica_de_produto": ("Rubrica de Produto", 3),
    "pronto_para_sair": ("Pronto para sair", 4),
    "validacao_no_motor": ("Validação no motor", 5),
    "prova_dos_3_movimentos": ("Prova dos 3 Movimentos", 6),
    "prova_das_5_expressoes": ("Prova das 5 Expressões", 7),
    "selo_ugc": ("Selo UGC", 8),
    "selo_ugc_personagem": ("Selo UGC de Personagem", 9),
    "ficha_de_serie": ("Ficha de Série", 10),
    "ficha_de_delegacao": ("Ficha de Delegação", 11),
    "revisao_de_estudio": ("Revisão de Estúdio", 12),
    "laudo_de_banca": ("Laudo de Banca", 13),
}


def cria_curso(site_id=SITE, slug="curso-x"):
    return Curso.objects.create(site_id=site_id, slug=slug, nome="Curso X")


def cria_bloco(curso, ordem=1, letra="A", parte=1):
    return Bloco.objects.create(curso=curso, ordem=ordem, letra=letra, parte=parte)


def cria_aula(curso, bloco, ordem=0, numero="E00", **extras):
    return Aula.objects.create(
        curso=curso,
        bloco=bloco,
        ordem=ordem,
        numero=numero,
        titulo_exibido=f"Encomenda {numero[1:]}",
        **extras,
    )


@pytest.fixture
def curso(db):
    return cria_curso()


@pytest.fixture
def bloco(curso):
    return cria_bloco(curso)


@pytest.fixture
def aula(curso, bloco):
    return cria_aula(curso, bloco)


# ---------------------------------------------------------------------------
# 1. O curso
# ---------------------------------------------------------------------------


def test_um_curso_por_slug_por_site(curso):
    with pytest.raises(IntegrityError, match="um_curso_por_slug_por_site"):
        cria_curso(slug=curso.slug)


def test_o_mesmo_slug_em_outro_site_e_outro_curso(curso):
    """Lei 9: uma fábrica, N lojas. O slug é único POR SITE, não na plataforma."""
    outro = cria_curso(site_id="escola-b", slug=curso.slug)
    assert outro.pk != curso.pk


@pytest.mark.parametrize("estado", ["publicada", "reprovado", ""])
def test_estado_de_curso_no_vocabulario_fechado(curso, estado):
    with pytest.raises(IntegrityError, match="estado_de_curso_no_vocabulario_fechado"):
        Curso.objects.filter(pk=curso.pk).update(estado=estado)


# ---------------------------------------------------------------------------
# 2. O bloco
# ---------------------------------------------------------------------------


def test_uma_ordem_por_bloco_por_curso(curso, bloco):
    with pytest.raises(IntegrityError, match="uma_ordem_por_bloco_por_curso"):
        cria_bloco(curso, ordem=bloco.ordem, letra="B")


def test_uma_letra_por_bloco_por_curso(curso, bloco):
    with pytest.raises(IntegrityError, match="uma_letra_por_bloco_por_curso"):
        cria_bloco(curso, ordem=2, letra=bloco.letra)


@pytest.mark.parametrize("ordem", [0, 13])
def test_ordem_de_bloco_entre_1_e_12(curso, ordem):
    with pytest.raises(IntegrityError, match="ordem_de_bloco_entre_1_e_12"):
        cria_bloco(curso, ordem=ordem)


@pytest.mark.parametrize("letra", ["M", "a", ""])
def test_letra_de_bloco_entre_a_e_l(curso, letra):
    with pytest.raises(IntegrityError, match="letra_de_bloco_entre_a_e_l"):
        cria_bloco(curso, letra=letra)


@pytest.mark.parametrize("parte", [0, 4])
def test_parte_de_bloco_e_1_2_ou_3(curso, parte):
    with pytest.raises(IntegrityError, match="parte_de_bloco_e_1_2_ou_3"):
        cria_bloco(curso, parte=parte)


# ---------------------------------------------------------------------------
# 3. A aula, e a unicidade que atravessa a chave estrangeira
# ---------------------------------------------------------------------------


def test_um_numero_por_aula_por_curso_mesmo_em_blocos_diferentes(curso, bloco, aula):
    """`Unique(curso, numero)` é por CURSO: a E00 no bloco B ainda é a E00.

    A unicidade atravessa a chave estrangeira do bloco, e é por isso que
    `Aula.curso` existe como coluna própria (`armadilhas/274`).
    """
    outro_bloco = cria_bloco(curso, ordem=2, letra="B")
    with pytest.raises(IntegrityError, match="um_numero_por_aula_por_curso"):
        cria_aula(curso, outro_bloco, ordem=99, numero=aula.numero)


def test_o_mesmo_numero_em_outro_curso_e_outra_aula(aula):
    outro_curso = cria_curso(slug="curso-y")
    outro_bloco = cria_bloco(outro_curso)
    assert cria_aula(outro_curso, outro_bloco, numero=aula.numero).pk != aula.pk


def test_uma_ordem_por_aula_por_curso(curso, bloco, aula):
    with pytest.raises(IntegrityError, match="uma_ordem_por_aula_por_curso"):
        cria_aula(curso, bloco, ordem=aula.ordem, numero="E01")


def test_a_aula_nao_aponta_para_bloco_de_outro_curso(curso):
    """A coluna `Aula.curso` não pode mentir sobre `Aula.bloco.curso`.

    É a chave estrangeira COMPOSTA da migração `0001`. Sem ela, uma aula do
    curso X dentro de um bloco do curso Y passaria por `Unique(curso, numero)`
    sem tropeçar, e a unicidade que a coluna sustenta cairia junto.
    """
    bloco_de_outro = cria_bloco(cria_curso(slug="curso-y"))
    with pytest.raises(IntegrityError, match="aula_e_bloco_do_mesmo_curso"):
        cria_aula(curso, bloco_de_outro)


def test_a_chave_composta_sobrevive_a_um_queryset_update(aula):
    """`update()` não passa por `save()` (`armadilhas/023`), e a guarda vale igual."""
    outro_curso = cria_curso(slug="curso-y")
    with pytest.raises(IntegrityError, match="aula_e_bloco_do_mesmo_curso"):
        Aula.objects.filter(pk=aula.pk).update(curso=outro_curso)


@pytest.mark.parametrize("numero", ["E33", "e00", "E0", "EB2", ""])
def test_numero_de_aula_no_vocabulario_fechado(curso, bloco, numero):
    with pytest.raises(IntegrityError, match="numero_de_aula_no_vocabulario_fechado"):
        cria_aula(curso, bloco, numero=numero)


@pytest.mark.parametrize("nivel", [0, 4])
def test_banca_nivel_e_1_2_3_ou_nulo(curso, bloco, nivel):
    with pytest.raises(IntegrityError, match="banca_nivel_e_1_2_3_ou_nulo"):
        cria_aula(curso, bloco, banca_nivel=nivel)


def test_banca_nivel_aceita_os_tres_niveis_e_o_nulo(curso, bloco):
    for ordem, nivel in enumerate([None, 1, 2, 3]):
        cria_aula(curso, bloco, ordem=ordem, numero=f"E0{ordem}", banca_nivel=nivel)
    assert Aula.objects.filter(curso=curso).count() == 4


@pytest.mark.parametrize("estado", ["publicado", "reprovado"])
def test_estado_de_aula_no_vocabulario_fechado(aula, estado):
    with pytest.raises(IntegrityError, match="estado_de_aula_no_vocabulario_fechado"):
        Aula.objects.filter(pk=aula.pk).update(estado=estado)


def test_a_aula_aponta_para_um_instrumento_ou_para_nenhum(aula):
    assert aula.instrumento is None
    studs = Instrumento.objects.create(
        slug="studs", nome_canonico="Teste STUDS", cartao=1
    )
    aula.instrumento = studs
    aula.save(update_fields=["instrumento"])
    assert studs.aulas.get() == aula


# ---------------------------------------------------------------------------
# 4. A peça: as 16 da anatomia, mais duas internas, mais uma sob demanda
# ---------------------------------------------------------------------------


def test_a_ordem_canonica_tem_as_16_pecas_da_anatomia():
    assert tuple(Peca.ORDEM_CANONICA) == AS_16_PECAS_NA_ORDEM
    assert len(Peca.ORDEM_CANONICA) == 16


def test_as_duas_internas_ficam_fora_da_ordem_canonica():
    assert tuple(Peca.TIPOS_INTERNOS) == AS_2_INTERNAS
    assert not set(Peca.TIPOS_INTERNOS) & set(Peca.ORDEM_CANONICA)


def test_a_videoaula_em_texto_fica_fora_da_ordem_canonica():
    """A ANATOMIA NÃO CRESCEU PARA 17, e este é o guarda que impede que cresça.

    A vídeo-aula em texto é um TERCEIRO caso (`TIPOS_SOB_DEMANDA`): o aluno a vê,
    mas fora da sequência, por um botão embaixo do capítulo. As 16 são a anatomia
    que a lei da célula declara (`docs/decisoes/PLANO-CELULA-CURSOS.md` §4), e
    mudá-la é Rito, não conveniência de quem estiver passando por aqui.
    """
    assert tuple(Peca.TIPOS_SOB_DEMANDA) == AS_SOB_DEMANDA
    assert len(Peca.ORDEM_CANONICA) == 16
    assert "videoaula_em_texto" not in Peca.ORDEM_CANONICA
    assert not set(Peca.TIPOS_SOB_DEMANDA) & set(Peca.ORDEM_CANONICA)
    assert not set(Peca.TIPOS_SOB_DEMANDA) & set(Peca.TIPOS_INTERNOS)


def test_o_vocabulario_de_peca_e_a_ordem_canonica_mais_as_internas():
    """O `TextChoices` declara as 16 NA ORDEM, depois as duas internas e por
    último a sob demanda: a tela que iterar `Peca.Tipo` mostra a anatomia na
    ordem certa sem segunda lista."""
    assert (
        tuple(Peca.Tipo.values) == AS_16_PECAS_NA_ORDEM + AS_2_INTERNAS + AS_SOB_DEMANDA
    )


def test_uma_peca_por_tipo_por_aula(aula):
    Peca.objects.create(aula=aula, tipo=Peca.Tipo.PEDIDO, texto="Um cubo.")
    with pytest.raises(IntegrityError, match="uma_peca_por_tipo_por_aula"):
        Peca.objects.create(aula=aula, tipo=Peca.Tipo.PEDIDO, texto="Outro cubo.")


@pytest.mark.parametrize("tipo", ["resumo", "PEDIDO", ""])
def test_tipo_de_peca_no_vocabulario_fechado(aula, tipo):
    with pytest.raises(IntegrityError, match="tipo_de_peca_no_vocabulario_fechado"):
        Peca.objects.create(aula=aula, tipo=tipo, texto="x")


def test_uma_aula_recebe_as_19_pecas(aula):
    for tipo in Peca.Tipo:
        Peca.objects.create(aula=aula, tipo=tipo, texto=f"# {tipo.label}")
    assert aula.pecas.count() == 19


def test_a_videoaula_em_texto_entra_e_sai_do_banco(aula):
    """O vocabulário FECHADO do banco aprendeu a palavra nova: sem a migração
    `0007`, este `create` seria IntegrityError com o `TextChoices` já certo."""
    Peca.objects.create(
        aula=aula,
        tipo=Peca.Tipo.VIDEOAULA_EM_TEXTO,
        texto="Oi, tudo bem? Hoje a gente vai modelar o cubo da vitrine.",
    )
    lida = aula.pecas.get(tipo="videoaula_em_texto")
    assert lida.texto.startswith("Oi, tudo bem?")


# ---------------------------------------------------------------------------
# 5. A pausa
# ---------------------------------------------------------------------------


def test_uma_ordem_por_pausa_por_aula(aula):
    Pausa.objects.create(aula=aula, ordem=1, segundo=10, tipo=Pausa.Tipo.FACA_AGORA)
    with pytest.raises(IntegrityError, match="uma_ordem_por_pausa_por_aula"):
        Pausa.objects.create(aula=aula, ordem=1, segundo=20, tipo=Pausa.Tipo.CERIMONIA)


@pytest.mark.parametrize("tipo", ["pausa", "erro", ""])
def test_tipo_de_pausa_no_vocabulario_fechado(aula, tipo):
    with pytest.raises(IntegrityError, match="tipo_de_pausa_no_vocabulario_fechado"):
        Pausa.objects.create(aula=aula, ordem=1, segundo=10, tipo=tipo)


def test_o_segundo_da_pausa_nunca_e_negativo(aula):
    Pausa.objects.create(aula=aula, ordem=1, segundo=0, tipo=Pausa.Tipo.ERRO_PRODUTIVO)
    with pytest.raises(IntegrityError, match="segundo"):
        Pausa.objects.create(aula=aula, ordem=2, segundo=-1, tipo=Pausa.Tipo.CERIMONIA)


# ---------------------------------------------------------------------------
# 6. O instrumento
# ---------------------------------------------------------------------------


def test_slug_de_instrumento_e_unico(db):
    Instrumento.objects.create(slug="studs", nome_canonico="Teste STUDS", cartao=1)
    with pytest.raises(IntegrityError, match="slug"):
        Instrumento.objects.create(slug="studs", nome_canonico="Outro", cartao=2)


def test_cartao_de_instrumento_e_unico(db):
    Instrumento.objects.create(slug="studs", nome_canonico="Teste STUDS", cartao=1)
    with pytest.raises(IntegrityError, match="cartao"):
        Instrumento.objects.create(slug="outro", nome_canonico="Outro", cartao=1)


@pytest.mark.parametrize("cartao", [0, 14])
def test_cartao_de_instrumento_entre_1_e_13(db, cartao):
    with pytest.raises(IntegrityError, match="cartao_de_instrumento_entre_1_e_13"):
        Instrumento.objects.create(slug="x", nome_canonico="X", cartao=cartao)


# ---------------------------------------------------------------------------
# 7. A palavra que não existe
# ---------------------------------------------------------------------------


def test_a_palavra_reprovado_nao_existe_no_vocabulario():
    """O estado "reprovado" não existe ([INV-CUR-L2] nasce no degrau 2.2, mas a
    palavra já não entra aqui): nem como valor, nem como rótulo, em nenhuma
    coluna de escolha desta célula."""
    achados = []
    for modelo in apps.get_app_config("cursos").get_models():
        for campo in modelo._meta.get_fields():
            for valor, rotulo in getattr(campo, "choices", None) or []:
                if "reprovad" in f"{valor} {rotulo}".lower():
                    achados.append(f"{modelo.__name__}.{campo.name}={valor}")
    assert achados == []


# ---------------------------------------------------------------------------
# 8. O semeador, pelo caminho da instalação
# ---------------------------------------------------------------------------


def test_o_esqueleto_tem_as_contagens_da_lei(esqueleto):
    assert esqueleto.blocos.count() == 12
    assert esqueleto.aulas.count() == 34
    assert Instrumento.objects.count() == 13
    assert Peca.objects.count() == 0
    assert esqueleto.aulas.exclude(pedido="").count() == 0


def test_o_esqueleto_nasce_rascunho_e_sem_nenhum_texto(esqueleto):
    """A ausência é a decisão (`armadilhas/331`): nome de bloco, título de boss,
    pedido, cliente, mínimo, quiz, vídeo e instrumento chegam pela tela."""
    assert (esqueleto.nome, esqueleto.estado, esqueleto.versao) == (
        "Profissional",
        Curso.Estado.RASCUNHO,
        1,
    )
    assert esqueleto.blocos.exclude(nome="", boss_titulo="").count() == 0
    assert (
        esqueleto.aulas.exclude(
            pedido="",
            cliente="",
            minimo="",
            aceito_quando=[],
            quiz=[],
            video_url="",
            instrumento=None,
            estado=Aula.Estado.RASCUNHO,
            versao=1,
            publicada_em=None,
        ).count()
        == 0
    )
    assert Pausa.objects.count() == 0


def test_a_distribuicao_das_aulas_pelos_blocos(esqueleto):
    do_banco = {
        bloco.letra: (
            bloco.parte,
            list(bloco.aulas.order_by("ordem").values_list("numero", flat=True)),
        )
        for bloco in esqueleto.blocos.all()
    }
    assert do_banco == A_DISTRIBUICAO
    assert list(esqueleto.blocos.values_list("ordem", "letra")) == list(
        enumerate("ABCDEFGHIJKL", start=1)
    )


def test_a_ordem_o_numero_e_o_titulo_de_cada_aula(esqueleto):
    aulas = list(esqueleto.aulas.order_by("ordem"))
    assert [a.ordem for a in aulas] == list(range(34))
    assert [a.numero for a in aulas][:33] == [f"E{n:02d}" for n in range(33)]
    assert aulas[0].titulo_exibido == "Encomenda 00"
    assert aulas[32].titulo_exibido == "Encomenda 32"
    bonus = aulas[33]
    assert (bonus.numero, bonus.titulo_exibido, bonus.bloco.letra) == (
        "EB",
        "Encomenda Bônus",
        "L",
    )


def test_os_13_instrumentos_da_lei(esqueleto):
    do_banco = {i.slug: (i.nome_canonico, i.cartao) for i in Instrumento.objects.all()}
    assert do_banco == OS_13_INSTRUMENTOS
    sem_escala = Instrumento.objects.filter(
        escala={}, descritores={}, minimo_exercicio="", minimo_contrato=""
    )
    assert sem_escala.count() == 13, "escala e descritores entram pela tela"


def test_semear_duas_vezes_nao_duplica_nada(esqueleto):
    saida = StringIO()
    call_command("semear_esqueleto", site=SITE, stdout=saida)
    assert (
        Curso.objects.count(),
        Bloco.objects.count(),
        Aula.objects.count(),
        Instrumento.objects.count(),
        Peca.objects.count(),
    ) == (1, 12, 34, 13, 0)
    assert "ja existia" in saida.getvalue()
    assert "0 bloco(s) novo(s), 0 aula(s) nova(s), 0 instrumento(s) novo(s)" in (
        saida.getvalue()
    )


def test_semear_nao_pisa_em_cima_de_edicao_humana(esqueleto):
    """Ele renomeou um título pela tela; rodar de novo não desfaz."""
    Aula.objects.filter(curso=esqueleto, numero="E00").update(
        titulo_exibido="Encomenda 00: o cubo"
    )
    call_command("semear_esqueleto", site=SITE, stdout=StringIO())
    assert (
        Aula.objects.get(curso=esqueleto, numero="E00").titulo_exibido
        == "Encomenda 00: o cubo"
    )


def test_a_semente_e_por_site(esqueleto):
    """Lei 9: semear a escola A não semeia a escola B; os instrumentos são de
    plataforma inteira e por isso não se repetem."""
    assert Curso.objects.filter(site_id="escola-b").count() == 0
    call_command("semear_esqueleto", site="escola-b", stdout=StringIO())
    assert Curso.objects.filter(site_id="escola-b").count() == 1
    assert Aula.objects.count() == 68
    assert Instrumento.objects.count() == 13


def test_o_esqueleto_entra_inteiro_ou_nao_entra(db):
    """Uma transação só: se a semeadura tropeça no meio, nada fica pela metade."""
    # Uma aula pré-existente ocupando a ordem 0 com um número que o esqueleto
    # não conhece: o semeador cria o bloco A, tenta criar a E00 na ordem 0 e
    # tropeça em `uma_ordem_por_aula_por_curso`. Nem o bloco nem os
    # instrumentos podem sobrar.
    #
    # Até 05/09/2026 este teste plantava um BLOCO com a letra errada. Desde que
    # o semeador passou a RECONCILIAR a estrutura do livro
    # (`test_semeador_reconcilia_estrutura.py`), aquele plantio deixou de
    # tropeçar: a letra errada agora é consertada, que é o comportamento que se
    # quer. O que este teste mede continua sendo a transação única, e por isso
    # ele passou a tropeçar num campo que a reconciliação NÃO toca.
    curso = Curso.objects.create(site_id=SITE, slug="profissional", nome="Profissional")
    # O bloco A já na posição certa, para a reconciliação não ter o que mudar
    # nele (a letra é limitada a A–L por `letra_de_bloco_entre_a_e_l`).
    bloco = Bloco.objects.create(curso=curso, ordem=1, letra="A", parte=1)
    # A E32 ocupando a ordem 0, que é da E00. O número precisa ser do
    # vocabulário fechado (`numero_de_aula_no_vocabulario_fechado`), e o
    # semeador só chega na E32 no fim: quando chegar, a E00 já terá tropeçado.
    Aula.objects.create(
        curso=curso, bloco=bloco, ordem=0, numero="E32", titulo_exibido="Fora do lugar"
    )
    with pytest.raises(IntegrityError, match="uma_ordem_por_aula_por_curso"):
        call_command("semear_esqueleto", site=SITE, stdout=StringIO())
    assert Aula.objects.count() == 1, "só a que já estava; nenhuma do esqueleto sobrou"
    assert Instrumento.objects.count() == 0
