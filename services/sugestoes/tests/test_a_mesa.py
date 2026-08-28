"""A Mesa (28/08/2026): a porta do painel mostra o que espera por uma pessoa.

Planta e motivo da escolha: `docs/paineis/painel-da-caixa-de-sugestoes/` e o
registro `20260828-002` do livro.

O que estes guardas medem é **a conta**, não a decoração: quais ideias sobem
para a mesa, em que ordem, e quem vê o botão de assinar. Todos provocam o estado
pela jornada de verdade (o clique da equipe muda o status; o POST do aprovador
registra o ChangeSpec) — um `objects.create()` continuaria verde no dia em que a
tela parasse de olhar para o que olha.

O crachá NÃO é testado aqui de propósito: `test_inv_so_staff_modera.py` deriva a
lista de rotas protegidas do próprio urlconf, então esta rota entrou lá sozinha.
Repetir a medição aqui daria duas verdades sobre a mesma coisa, e a que ninguém
mantém é a que fica errada.
"""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.gestao import DIAS_ATE_A_ANALISE_ENVELHECER
from apps.sugestoes.models import Sugestao


def envelhecer(sugestao, dias):
    """Empurra a ideia para trás no tempo — pelo `update()`, que é o único jeito.

    `criado_em` é `auto_now_add`: um `save()` não o reescreve. E `Sugestao` não é
    append-only (só `HistoricoStatus` e `ChangeSpecAprovado` são), então o
    `update()` aqui é legítimo e não fura guarda nenhum.
    """
    Sugestao.objects.filter(pk=sugestao.pk).update(
        criado_em=timezone.now() - timedelta(days=dias)
    )


def abrir(quem):
    resposta = quem.client.get(reverse("mesa"))
    assert resposta.status_code == 200, resposta.content
    return resposta.content.decode()


# ---------------------------------------------------------------------------
# O que sobe para a mesa, e o que não sobe
# ---------------------------------------------------------------------------


def test_ideia_planejada_sem_changespec_sobe_para_a_mesa(caixa, equipe, sugestao):
    """O corredor do EVO-40 visto do outro lado: `planejado` sem assinatura para."""
    caixa.mudar_status(sugestao, Sugestao.Status.PLANEJADO, nota="Vai entrar.")

    pagina = abrir(equipe)

    assert sugestao.titulo in pagina
    assert "espera a assinatura" in pagina or "só você pode tomar esta" in pagina


def test_ideia_planejada_com_changespec_sai_da_mesa(
    caixa, aprovador, sugestao, changespec
):
    """Assinado o corredor, a ideia deixa de esperar — e some da mesa sozinha.

    É a prova de que a lista é CALCULADA: ninguém a marcou como resolvida, e
    ninguém precisou lembrar de tirá-la de lugar nenhum.
    """
    caixa.mudar_status(sugestao, Sugestao.Status.PLANEJADO, nota="Vai entrar.")

    pagina = abrir(aprovador)

    assert sugestao.titulo not in pagina
    assert "A mesa está limpa" in pagina


def test_analise_recem_chegada_nao_incomoda_ninguem(equipe, sugestao):
    """Ideia nova em análise NÃO é pendência: a equipe tem a janela inteira."""
    pagina = abrir(equipe)

    assert sugestao.titulo not in pagina
    assert "A mesa está limpa" in pagina


def test_analise_esquecida_sobe_pelo_relogio(equipe, sugestao):
    """Passada a janela sem ninguém escrever nada, a ideia cobra sozinha."""
    envelhecer(sugestao, DIAS_ATE_A_ANALISE_ENVELHECER + 1)

    pagina = abrir(equipe)

    assert sugestao.titulo in pagina
    assert "ninguém da equipe leu esta ainda" in pagina


def test_analise_esquecida_mas_ja_avaliada_nao_sobe(equipe, sugestao):
    """O gatilho é a AUSÊNCIA de avaliação, não a idade sozinha."""
    envelhecer(sugestao, DIAS_ATE_A_ANALISE_ENVELHECER + 30)
    resposta = equipe.client.post(
        reverse("avaliar", args=[sugestao.id]),
        {
            "impacto_educacional": "4",
            "impacto_comercial": "3",
            "esforco_tecnico": "2",
            "notas": "Cabe no trimestre.",
            "decisao_produto": "Vamos fazer com modelo fixo.",
        },
    )
    assert resposta.status_code == 302, resposta.content

    pagina = abrir(equipe)

    assert sugestao.titulo not in pagina


# ---------------------------------------------------------------------------
# A ordem, e de quem é a vez
# ---------------------------------------------------------------------------


def test_a_mesa_ordena_por_gente_esperando(caixa, equipe, quadro, categoria, plateia):
    """Mais gente atrás vem primeiro — mesmo que a outra esteja parada há mais tempo.

    É a decisão de desenho escrita em `gestao.decisoes_da_mesa()`: uma ideia com
    muita gente parada há pouco custa mais silêncio à turma do que uma com pouca
    gente parada há muito.
    """
    pequena = caixa.publicar("Ideia de poucos")
    grande = caixa.publicar("Ideia de muitos")
    envelhecer(pequena, DIAS_ATE_A_ANALISE_ENVELHECER + 40)
    envelhecer(grande, DIAS_ATE_A_ANALISE_ENVELHECER + 1)
    plateia(pequena, votantes=2, marca="poucos")
    plateia(grande, votantes=30, marca="muitos")

    pagina = abrir(equipe)

    assert pagina.index("Ideia de muitos") < pagina.index("Ideia de poucos")


def test_so_quem_aprova_ve_o_botao_de_assinar(caixa, equipe, sugestao):
    """Estar na equipe dá o crachá de moderar, não o de autorizar obra.

    A tela não esconde o ITEM de quem não assina — a fila é da equipe inteira —,
    ela esconde o BOTÃO e escreve de quem é a vez. A regra não é copiada no
    template: sai de `e_aprovador()`, o mesmo portão da rota de registro.
    """
    caixa.mudar_status(sugestao, Sugestao.Status.PLANEJADO, nota="Vai entrar.")
    assinar = reverse("changespecs", args=[sugestao.id])

    pagina = abrir(equipe)

    assert sugestao.titulo in pagina
    assert assinar not in pagina
    assert "espera a assinatura de quem aprova" in pagina


def test_quem_aprova_ve_o_caminho_da_assinatura(caixa, aprovador, sugestao):
    caixa.mudar_status(sugestao, Sugestao.Status.PLANEJADO, nota="Vai entrar.")

    pagina = abrir(aprovador)

    assert reverse("changespecs", args=[sugestao.id]) in pagina
    assert "Ler o documento e assinar" in pagina


# ---------------------------------------------------------------------------
# A metade que não pede nada
# ---------------------------------------------------------------------------


def test_o_que_anda_sozinho_aparece_de_canto(caixa, equipe, sugestao, changespec):
    """Em obra e no ar ficam visíveis — mas fora da mesa, que é o ponto do desenho."""
    caixa.mudar_status(sugestao, Sugestao.Status.PLANEJADO, nota="Vai entrar.")
    caixa.mudar_status(sugestao, Sugestao.Status.EM_DESENVOLVIMENTO, nota="Começou.")

    pagina = abrir(equipe)

    assert "Andando sozinho" in pagina
    assert "em construção" in pagina
    assert sugestao.titulo in pagina
    assert "A mesa está limpa" in pagina


def test_a_mesa_vazia_nao_e_uma_tela_em_branco(equipe, quadro):
    """Um painel que só funciona cheio de problema treina a pessoa a não abri-lo."""
    pagina = abrir(equipe)

    assert "A mesa está limpa" in pagina
    assert "Isto é uma conta, não um relato" in pagina


def test_a_aba_que_nao_existe_diz_que_nao_existe(equipe, quadro):
    """Aba futura aparece apagada e sem link — nem escondida, nem mentindo.

    Mede "Os robôs", que segue sem tela: quando "A travessia" nasceu (aba 2), a
    medição antiga passou a olhar para um link de verdade e teria continuado verde
    sem provar nada.
    """
    pagina = abrir(equipe)

    assert "Os robôs" in pagina
    assert "aba futura" in pagina


@pytest.mark.parametrize("metodo", ["post", "put", "delete"])
def test_a_mesa_e_somente_leitura(equipe, quadro, metodo):
    """Ela não decide nada: assinar é do `changespecs`, mudar status é do `moderacao`."""
    resposta = getattr(equipe.client, metodo)(reverse("mesa"))

    assert resposta.status_code == 405
