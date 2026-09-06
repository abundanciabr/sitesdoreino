"""A sala serve SÓ o curso em que a pessoa está matriculada.

`DECISAO-cursos-matriculas-e-alunos.md` §1: ninguém é aluno do site, todo mundo
é aluno de um PRODUTO. Até 06/09/2026 a sala perguntava só "esta pessoa é
aluna?", e isso funcionava por coincidência enquanto havia um curso. No dia do
segundo, todo aluno do primeiro abriria o segundo digitando o endereço, sem
erro e sem aviso: é o defeito que a §2 daquela lei diz existir para impedir.

O que este arquivo protege:

1. **Matriculado no curso A, o curso B recusa**, o guarda que dá nome à
   tarefa, provado pelos dois endereços (o mapa e a aula).
2. **O curso próprio continua abrindo**, senão a cura seria fechar tudo.
3. **Curso sem produto apontado FECHA**, e é como todo curso nasce.
4. **Matrícula sem produto não é coringa**: ela não abre curso nenhum.
5. **Matrícula de outra escola não abre a sala desta.**
6. **O plantão não passa por aqui**: quem dá laudo não é aluno de nada.
7. **A sala não OFERECE curso alheio**: a tela de escolher e a de endereço
   desconhecido mostram os cursos da pessoa, e não os da escola.
8. **O comando que aponta o produto** faz o elo, é idempotente e não troca um
   produto já apontado sem que alguém peça.
"""

from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from django.urls import reverse
from django.utils import timezone

from apps.core import sessao
from apps.cursos.models import Aula, Bloco, Curso, Progresso

from tests.conftest import (
    ANA,
    COOKIE,
    PRODUTO_DE_OUTRO_CURSO,
    PRODUTO_DO_CURSO,
    SITE,
    dublar_matricula,
    dublar_sessao,
    publicar,
)

pytestmark = pytest.mark.django_db

A_FRASE_DE_OUTRO_CURSO = "Este curso não é o seu"
A_FRASE_DE_CURSO_SEM_PRODUTO = "Este curso ainda não está ligado às matrículas"


def corpo_de(resposta) -> str:
    if resposta.streaming:
        return b"".join(resposta.streaming_content).decode("utf-8")
    return resposta.content.decode("utf-8")


def o_outro_curso(*, produto: str = PRODUTO_DE_OUTRO_CURSO) -> Curso:
    """O curso do livro, com a E00 dele PUBLICADA e um segredo dentro.

    A E00 existe nos dois cursos porque a numeração das encomendas é POR curso,
    e é esse detalhe que faz o teste doer: um segundo curso vazio esconderia o
    defeito, porque quem entrasse por engano não acharia aula nenhuma lá e
    cairia de volta por acidente, com o teste verde.
    """
    curso = Curso.objects.create(
        site_id=SITE, slug="avancado", nome="Avançado", produto_id=produto
    )
    bloco = Bloco.objects.create(curso=curso, ordem=1, letra="A", parte=1)
    aula = Aula.objects.create(
        curso=curso,
        bloco=bloco,
        ordem=0,
        numero="E00",
        titulo_exibido="SEGREDO-DO-CURSO-2",
        estado=Aula.Estado.PUBLICADA,
        publicada_em=timezone.now(),
    )
    publicar(aula)
    return curso


# ------------------------------- 1. o curso do outro RECUSA, nos dois endereços
def test_matriculada_no_curso_a_o_mapa_do_curso_b_recusa(aluna, client):
    """**O guarda que dá nome à tarefa.** Ana tem matrícula no `profissional` e
    digita o endereço do `avancado`. Se este teste ficar verde com 200, todo
    aluno do primeiro curso lê o segundo, que é obra não lançada do mantenedor."""
    o_outro_curso()

    resposta = client.get(reverse("curso", args=["avancado"]), HTTP_COOKIE=COOKIE)

    assert resposta.status_code == 403
    corpo = corpo_de(resposta)
    assert A_FRASE_DE_OUTRO_CURSO in corpo
    assert "SEGREDO-DO-CURSO-2" not in corpo


def test_matriculada_no_curso_a_a_aula_do_curso_b_recusa(aluna, client):
    """A mesma porta guarda as duas telas: nenhum caminho entra pela aula."""
    o_outro_curso()

    resposta = client.get(
        reverse("aula-do-curso", args=["avancado", 1, "E00"]), HTTP_COOKIE=COOKIE
    )

    assert resposta.status_code == 403
    corpo = corpo_de(resposta)
    assert A_FRASE_DE_OUTRO_CURSO in corpo
    assert "SEGREDO-DO-CURSO-2" not in corpo


def test_a_recusa_nao_deixa_rastro_de_progresso_no_curso_alheio(aluna, client):
    """Recusar e criar a porta E00 do curso alheio seria recusar pela metade:
    a pessoa não entra hoje e aparece como aluna dele para sempre."""
    outro = o_outro_curso()
    client.get(reverse("curso", args=["avancado"]), HTTP_COOKIE=COOKIE)
    assert Progresso.objects.filter(aula__curso=outro).count() == 0


# ------------------------------------- 2. o curso PRÓPRIO continua abrindo
def test_o_curso_da_matricula_abre_normalmente(aluna, client):
    """Fechar tudo não é curar: com o outro curso no ar, o dela continua o dela."""
    o_outro_curso()
    resposta = client.get(reverse("curso", args=["profissional"]), HTTP_COOKIE=COOKIE)
    assert resposta.status_code == 200
    assert "Entre. Entregue. Receba." in corpo_de(resposta)


def test_matriculada_nos_dois_cursos_abre_os_dois(
    env_dos_pares, rede, esqueleto, client
):
    """Uma pessoa pode ter várias matrículas, uma por produto (lei §1)."""
    dublar_sessao(rede, ANA)
    o_outro_curso()
    dublar_matricula(
        rede, ANA["email"], produtos=[PRODUTO_DO_CURSO, PRODUTO_DE_OUTRO_CURSO]
    )

    assert (
        client.get(
            reverse("curso", args=["profissional"]), HTTP_COOKIE=COOKIE
        ).status_code
        == 200
    )
    assert (
        client.get(reverse("curso", args=["avancado"]), HTTP_COOKIE=COOKIE).status_code
        == 200
    )


# ------------------------------- 3. curso sem produto apontado FECHA
def test_curso_sem_produto_apontado_nao_abre_para_ninguem(
    env_dos_pares, rede, esqueleto, client
):
    """É como TODO curso nasce, e a decisão está escrita em `models.py`: um
    curso que não diz de qual produto é não pode ser conferido, e nesta casa
    não conseguir conferir FECHA. Abrir seria o defeito de volta, e invisível."""
    esqueleto.produto_id = ""
    esqueleto.save(update_fields=["produto_id"])
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"])

    resposta = client.get(reverse("curso", args=["profissional"]), HTTP_COOKIE=COOKIE)

    assert resposta.status_code == 403
    assert A_FRASE_DE_CURSO_SEM_PRODUTO in corpo_de(resposta)
    assert Progresso.objects.count() == 0


# ------------------------- 4. matrícula sem produto não abre curso nenhum
def test_matricula_sem_produto_nao_e_coringa(env_dos_pares, rede, esqueleto, client):
    """A `alunos` ainda cria matrícula paga com `product_id` vazio (lei §3, e é
    a TAR-225). Vazio significa "não sei de qual produto", e tratá-lo como
    coringa abriria TODOS os cursos: o defeito com outro nome."""
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"], produtos=[""])

    resposta = client.get(reverse("curso", args=["profissional"]), HTTP_COOKIE=COOKIE)

    assert resposta.status_code == 403
    assert A_FRASE_DE_OUTRO_CURSO in corpo_de(resposta)


def test_a_matricula_sem_produto_nao_entra_no_conjunto_de_produtos(env_dos_pares):
    """O conjunto do `Ator` é DADO com significado, e mede-se onde ele nasce.

    A recusa da tela acima ficaria verde com o vazio dentro do conjunto, porque
    o curso alvo tem produto e `""` não é igual a ele. Medido em 06/09/2026,
    sabotando a peneira: nenhum teste de tela caiu. Isto aqui é o que cai, e
    a peneira existe pelo próprio conjunto: um "conjunto de produtos" que
    contém o vazio mente para quem o ler, hoje na contagem de cursos da pessoa
    e amanhã em qualquer tela que os liste."""
    uma_ativa_sem_produto = [
        {"site_id": SITE, "order_id": "ord-1", "product_id": "", "status": "ativa"}
    ]
    assert sessao._produtos_deste_site(uma_ativa_sem_produto) == frozenset()


# --------------------------- 5. matrícula de OUTRA escola não abre esta sala
def test_matricula_de_outra_escola_nao_abre_a_sala_desta(
    env_dos_pares, rede, esqueleto, client
):
    """[INV-P11]: a fronteira de site vale para a matrícula como vale para o
    curso. O produto é o mesmo; a escola, não."""
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"], site="escola-b")

    resposta = client.get(reverse("curso", args=["profissional"]), HTTP_COOKIE=COOKIE)

    assert resposta.status_code == 403
    assert A_FRASE_DE_OUTRO_CURSO in corpo_de(resposta)


def test_sem_curso_nenhum_dela_a_recusa_manda_falar_com_a_escola(
    env_dos_pares, rede, esqueleto, client
):
    """O endereço antigo, para quem não é aluna de curso nenhum DESTA escola.

    Não há para onde mandá-la, e a tela sem lista não pode virar uma tela muda:
    a recusa diz o que houve (a compra chegou sem dizer qual curso) e o que
    fazer (falar com a escola)."""
    o_outro_curso()
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"], site="escola-b")

    resposta = client.get(reverse("mapa"), HTTP_COOKIE=COOKIE)

    assert resposta.status_code == 403
    corpo = corpo_de(resposta)
    assert A_FRASE_DE_OUTRO_CURSO in corpo
    assert "fale com a escola" in corpo
    assert 'href="/profissional/"' not in corpo


# ---------------------------------- 6. o plantão não passa por esta porta
def test_o_professor_entra_no_plantao_sem_matricula_de_curso_nenhum(
    env_dos_pares, rede, esqueleto, client, monkeypatch
):
    """Quem dá laudo não é aluno de nada, e a mudança não pode tê-lo trancado
    do lado de fora."""
    monkeypatch.setenv("CURSOS_PROFESSORES", ANA["email"])
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"], "cadastrado")

    resposta = client.get(reverse("plantao"), HTTP_COOKIE=COOKIE)

    assert resposta.status_code == 200


# ------------------- 7. a sala não OFERECE curso de que a pessoa não é aluna
def test_a_tela_de_escolher_nao_oferece_curso_alheio(aluna, client):
    """Com dois cursos no site e um só dela, não há o que escolher: oferecer o
    outro seria a sala convidando para uma porta que ela mesma vai fechar."""
    o_outro_curso()
    resposta = client.get(reverse("mapa"), HTTP_COOKIE=COOKIE)
    corpo = corpo_de(resposta)
    assert 'href="/avancado/"' not in corpo


def test_o_endereco_desconhecido_mostra_os_cursos_dela_e_nao_os_da_escola(
    aluna, client
):
    o_outro_curso()
    corpo = corpo_de(
        client.get(reverse("curso", args=["nao-existe"]), HTTP_COOKIE=COOKIE)
    )
    assert 'href="/profissional/"' in corpo
    assert 'href="/avancado/"' not in corpo


def test_a_recusa_do_curso_alheio_aponta_o_curso_dela(aluna, client):
    """Uma recusa que não diz para onde ir manda a pessoa adivinhar."""
    o_outro_curso()
    corpo = corpo_de(
        client.get(reverse("curso", args=["avancado"]), HTTP_COOKIE=COOKIE)
    )
    assert 'href="/profissional/"' in corpo


# ---------------------------- 8. o comando que faz o elo, do lado da máquina
def apontar(**opcoes) -> str:
    saida = StringIO()
    call_command("apontar_o_produto_do_curso", stdout=saida, **opcoes)
    return saida.getvalue()


def test_o_comando_aponta_o_produto_e_a_sala_passa_a_abrir(
    env_dos_pares, rede, esqueleto, client
):
    """O caminho inteiro, da máquina até a tela: o curso nasce sem produto, o
    comando o aponta, e a mesma pessoa que era recusada entra."""
    esqueleto.produto_id = ""
    esqueleto.save(update_fields=["produto_id"])
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"])
    endereco = reverse("curso", args=["profissional"])
    assert client.get(endereco, HTTP_COOKIE=COOKIE).status_code == 403

    apontar(site=SITE, curso="profissional", produto=PRODUTO_DO_CURSO)

    assert client.get(endereco, HTTP_COOKIE=COOKIE).status_code == 200


def test_o_comando_e_idempotente(esqueleto):
    saida = apontar(site=SITE, curso="profissional", produto=PRODUTO_DO_CURSO)
    assert "ja estava apontado" in saida
    esqueleto.refresh_from_db()
    assert esqueleto.produto_id == PRODUTO_DO_CURSO


def test_o_comando_recusa_trocar_o_produto_em_silencio(esqueleto):
    """Trocar o produto troca QUEM ENTRA no curso, e uma tecla errada no meio
    de um id de 36 letras não pode virar isso sem ninguém ver."""
    with pytest.raises(CommandError) as recusa:
        apontar(site=SITE, curso="profissional", produto=PRODUTO_DE_OUTRO_CURSO)
    assert "--trocar" in str(recusa.value)
    esqueleto.refresh_from_db()
    assert esqueleto.produto_id == PRODUTO_DO_CURSO


def test_o_comando_troca_quando_alguem_pede(esqueleto):
    apontar(
        site=SITE, curso="profissional", produto=PRODUTO_DE_OUTRO_CURSO, trocar=True
    )
    esqueleto.refresh_from_db()
    assert esqueleto.produto_id == PRODUTO_DE_OUTRO_CURSO


def test_o_comando_recusa_curso_que_nao_existe_e_diz_quais_existem(esqueleto):
    with pytest.raises(CommandError) as recusa:
        apontar(site=SITE, curso="nao-existe", produto=PRODUTO_DO_CURSO)
    assert "profissional" in str(recusa.value)
    assert "Nada foi alterado" in str(recusa.value)
