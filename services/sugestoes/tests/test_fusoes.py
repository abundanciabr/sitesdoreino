"""Juntar ideias, e poder desfazer (05/09/2026).

Pedido do mantenedor: prévia, confirmação e desfazer tudo. Lei em
`docs/decisoes/DECISAO-fundir-ideias.md`; a operação em `apps/core/fusoes.py`.

O que estes guardas protegem, em ordem de quanto dói perder:

1. **Quem votou nas duas não vira dois votos** — é o invariante da espec §8
   (V1.1) e o único que o banco sozinho não resolveria: sem o descarte
   deliberado, mover o voto estouraria o `unique_together` e a junção morreria
   no meio.
2. **Desfazer devolve de verdade** — votos movidos, votos descartados e
   comentários. É a diferença entre um botão que promete voltar atrás e um que
   só muda um rótulo.
3. **Desfazer não inventa** — voto que a pessoa TIROU depois da junção não
   volta. Ressuscitá-lo seria votar no lugar dela.
4. **A prévia não escreve nada.** É o que o mantenedor vê antes de decidir; se
   ela mexesse no banco, "ver como ficaria" já teria mudado a Caixa.
5. **A junção é tudo ou nada**, e o histórico de status sobrevive a ela.
6. **A URL da ideia absorvida continua resolvendo** (espec §8): ela não some,
   passa a apontar para onde foi.
"""

import pytest

from apps.core import fusoes
from apps.sugestoes.models import (
    Comentario,
    Fusao,
    HistoricoStatus,
    Identidade,
    Sugestao,
    Voto,
)


@pytest.fixture
def canonica(quadro, categoria, aluno):
    return Sugestao.objects.create(
        quadro=quadro,
        categoria=categoria,
        autor=aluno,
        titulo="Anatomia de cabelo para Roblox",
        problema="A anatomia de lá é diferente da real.",
    )


@pytest.fixture
def absorvida(quadro, categoria, outro_aluno):
    return Sugestao.objects.create(
        quadro=quadro,
        categoria=categoria,
        autor=outro_aluno,
        titulo="Tutorial de cabelo cacheado",
        problema="Cachos têm volume e mecha diferentes.",
    )


@pytest.fixture
def moderador(db):
    return Identidade.objects.create(
        email="mantenedor@meshcraft.test",
        nome_exibido="Mantenedor",
        id_da_plataforma="idt-do-mantenedor",
    )


def votar(sugestao, *pessoas):
    for pessoa in pessoas:
        Voto.objects.create(sugestao=sugestao, autor=pessoa)


def gente(db, quantas: int) -> list:
    return [
        Identidade.objects.create(email=f"p{i}@exemplo.test", nome_exibido=f"P{i}")
        for i in range(quantas)
    ]


# ---------------------------------------------------------------------------
# 1. A prévia: conta certo e não escreve nada
# ---------------------------------------------------------------------------


def test_a_previa_nao_soma_duas_vezes_quem_votou_nas_duas(
    db, canonica, absorvida, aluno, outro_aluno
):
    """O número que a tela mostra antes de confirmar."""
    ana, bruno, carla = gente(db, 3)
    votar(canonica, ana, bruno)
    votar(absorvida, bruno, carla)  # bruno votou nas duas

    previa = fusoes.previa(canonica_id=canonica.id, absorvidas_ids=[absorvida.id])

    assert previa["votos_hoje"] == 4
    assert previa["votos_depois"] == 3
    assert previa["votos_em_comum"] == 1
    assert previa["impedimento"] == ""


def test_a_previa_nao_escreve_nada(db, canonica, absorvida, aluno):
    antes_status = absorvida.status
    antes_votos = Voto.objects.count()

    fusoes.previa(canonica_id=canonica.id, absorvidas_ids=[absorvida.id])

    absorvida.refresh_from_db()
    assert absorvida.status == antes_status
    assert absorvida.sugestao_canonica_id is None
    assert Voto.objects.count() == antes_votos
    assert Fusao.objects.count() == 0


def test_a_previa_explica_o_impedimento_em_vez_de_sumir(db, canonica, absorvida):
    absorvida.arquivada_em = "2026-09-01T10:00:00+00:00"
    absorvida.save(update_fields=["arquivada_em"])

    previa = fusoes.previa(canonica_id=canonica.id, absorvidas_ids=[absorvida.id])

    assert "arquivada" in previa["impedimento"].lower()


# ---------------------------------------------------------------------------
# 2. A junção
# ---------------------------------------------------------------------------


def test_quem_votou_nas_duas_nao_vira_dois_votos(db, canonica, absorvida, moderador):
    """O invariante da espec §8, e a razão de `votos_descartados` existir."""
    ana, bruno, carla = gente(db, 3)
    votar(canonica, ana, bruno)
    votar(absorvida, bruno, carla)

    fusoes.fundir(
        canonica_id=canonica.id,
        absorvidas_ids=[absorvida.id],
        nota="",
        por=moderador,
    )

    # POR NOME, e não só por número (`armadilhas/267`): contar 3 votos na
    # canônica passaria igual se a junção tivesse trocado quem são os três —
    # movido a carla e derrubado a ana, por exemplo. A lista de ids é a única
    # asserção em que uma implementação errada não consegue empatar com a certa.
    assert set(
        Voto.objects.filter(sugestao=canonica).values_list("autor_id", flat=True)
    ) == {ana.id, bruno.id, carla.id}
    assert Voto.objects.filter(sugestao=absorvida).count() == 0
    # E o voto repetido do bruno não sumiu do mapa: ele está anotado, e é isso
    # que permite devolvê-lo.
    absorcao = Fusao.objects.get().absorvidas.get()
    assert absorcao.votos_descartados == [bruno.id]
    assert sorted(absorcao.votos_movidos) == sorted([carla.id])


def test_a_ideia_absorvida_continua_existindo_e_aponta_para_onde_foi(
    db, canonica, absorvida, moderador
):
    """Espec §8: a URL da mesclada continua resolvendo."""
    fusoes.fundir(
        canonica_id=canonica.id, absorvidas_ids=[absorvida.id], nota="", por=moderador
    )

    absorvida.refresh_from_db()
    assert absorvida.status == Sugestao.Status.MESCLADO
    assert absorvida.sugestao_canonica_id == canonica.id
    assert Sugestao.objects.filter(pk=absorvida.pk).exists()


def test_a_juncao_escreve_historico_e_diz_para_onde_a_ideia_foi(
    db, canonica, absorvida, moderador
):
    fusoes.fundir(
        canonica_id=canonica.id, absorvidas_ids=[absorvida.id], nota="", por=moderador
    )

    linha = HistoricoStatus.objects.filter(sugestao=absorvida).latest("id")
    assert linha.status_novo == Sugestao.Status.MESCLADO
    assert str(canonica.id) in linha.nota


def test_os_comentarios_mudam_de_ideia_e_nenhum_se_perde(
    db, canonica, absorvida, aluno, moderador
):
    Comentario.objects.create(
        sugestao=absorvida, autor=aluno, texto="isso me trava também"
    )

    fusoes.fundir(
        canonica_id=canonica.id, absorvidas_ids=[absorvida.id], nota="", por=moderador
    )

    assert Comentario.objects.filter(sugestao=canonica).count() == 1
    assert Comentario.objects.filter(sugestao=absorvida).count() == 0
    assert Comentario.objects.count() == 1


def test_tres_ideias_numa_junção_so(db, quadro, categoria, aluno, moderador):
    outras = [
        Sugestao.objects.create(
            quadro=quadro,
            categoria=categoria,
            autor=aluno,
            titulo=f"Ideia {i}",
            problema="x",
        )
        for i in range(3)
    ]
    canonica, *absorvidas = outras

    fusao = fusoes.fundir(
        canonica_id=canonica.id,
        absorvidas_ids=[s.id for s in absorvidas],
        nota="mesmo pacote de gravação",
        por=moderador,
    )

    assert fusao.absorvidas.count() == 2
    assert all(
        Sugestao.objects.get(pk=s.pk).status == Sugestao.Status.MESCLADO
        for s in absorvidas
    )


def test_uma_ideia_ja_juntada_nao_entra_em_outra_juncao(
    db, canonica, absorvida, moderador
):
    fusoes.fundir(
        canonica_id=canonica.id, absorvidas_ids=[absorvida.id], nota="", por=moderador
    )

    with pytest.raises(fusoes.FusaoInvalida) as recusa:
        fusoes.fundir(
            canonica_id=canonica.id,
            absorvidas_ids=[absorvida.id],
            nota="",
            por=moderador,
        )

    assert "já foi juntada" in str(recusa.value)


def test_ideia_nao_se_junta_a_si_mesma(db, canonica, moderador):
    with pytest.raises(fusoes.FusaoInvalida):
        fusoes.fundir(
            canonica_id=canonica.id,
            absorvidas_ids=[canonica.id],
            nota="",
            por=moderador,
        )


# ---------------------------------------------------------------------------
# 3. Desfazer
# ---------------------------------------------------------------------------


def test_desfazer_devolve_votos_comentarios_e_status(
    db, canonica, absorvida, aluno, moderador
):
    """O guarda principal do pedido: desfazer tudo, e tudo volta ao lugar."""
    ana, bruno, carla = gente(db, 3)
    votar(canonica, ana, bruno)
    votar(absorvida, bruno, carla)
    Comentario.objects.create(sugestao=absorvida, autor=aluno, texto="também quero")
    status_antes = absorvida.status

    fusao = fusoes.fundir(
        canonica_id=canonica.id, absorvidas_ids=[absorvida.id], nota="", por=moderador
    )
    fusoes.desfazer(fusao_id=fusao.id, por=moderador)

    absorvida.refresh_from_db()
    assert absorvida.status == status_antes
    assert absorvida.sugestao_canonica_id is None
    # Os votos voltaram: carla (movida) e bruno (descartado, recriado).
    assert set(
        Voto.objects.filter(sugestao=absorvida).values_list("autor_id", flat=True)
    ) == {bruno.id, carla.id}
    assert set(
        Voto.objects.filter(sugestao=canonica).values_list("autor_id", flat=True)
    ) == {ana.id, bruno.id}
    assert Comentario.objects.filter(sugestao=absorvida).count() == 1


def test_desfazer_nao_ressuscita_voto_que_a_pessoa_tirou(
    db, canonica, absorvida, moderador
):
    """Honestidade: depois da junção a pessoa desvotou. Desfazer não vota por ela."""
    ana, carla = gente(db, 2)
    votar(canonica, ana)
    votar(absorvida, carla)

    fusao = fusoes.fundir(
        canonica_id=canonica.id, absorvidas_ids=[absorvida.id], nota="", por=moderador
    )
    Voto.objects.filter(sugestao=canonica, autor=carla).delete()  # ela desvotou

    fusoes.desfazer(fusao_id=fusao.id, por=moderador)

    assert not Voto.objects.filter(sugestao=absorvida, autor=carla).exists()
    assert Voto.objects.filter(sugestao=canonica).count() == 1


def test_desfazer_duas_vezes_e_recusado_com_frase(db, canonica, absorvida, moderador):
    fusao = fusoes.fundir(
        canonica_id=canonica.id, absorvidas_ids=[absorvida.id], nota="", por=moderador
    )
    fusoes.desfazer(fusao_id=fusao.id, por=moderador)

    with pytest.raises(fusoes.FusaoInvalida) as recusa:
        fusoes.desfazer(fusao_id=fusao.id, por=moderador)

    assert "já foi desfeita" in str(recusa.value)


def test_a_juncao_desfeita_sai_da_lista_do_que_da_para_desfazer(
    db, quadro, canonica, absorvida, moderador
):
    fusao = fusoes.fundir(
        canonica_id=canonica.id, absorvidas_ids=[absorvida.id], nota="", por=moderador
    )
    assert [f.id for f in fusoes.em_vigor(quadro)] == [fusao.id]

    fusoes.desfazer(fusao_id=fusao.id, por=moderador)

    assert fusoes.em_vigor(quadro) == []


def test_depois_de_desfazer_da_para_juntar_de_novo(db, canonica, absorvida, moderador):
    """O desfazer devolve a ideia ao mundo, e não a um limbo."""
    fusao = fusoes.fundir(
        canonica_id=canonica.id, absorvidas_ids=[absorvida.id], nota="", por=moderador
    )
    fusoes.desfazer(fusao_id=fusao.id, por=moderador)

    de_novo = fusoes.fundir(
        canonica_id=canonica.id, absorvidas_ids=[absorvida.id], nota="", por=moderador
    )

    assert de_novo.id != fusao.id
    absorvida.refresh_from_db()
    assert absorvida.status == Sugestao.Status.MESCLADO
