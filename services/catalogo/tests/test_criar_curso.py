# tests/test_criar_curso.py
"""`criar_curso` — o caminho que faltava para um curso de verdade existir.

Até 06/09/2026 o único `Product` que nascia era o `curso-esqueleto` do
`seed_esqueleto`, que é peça de teste de ponta a ponta. A tela de liberar aluno
(`DECISAO-cursos-matriculas-e-alunos.md` §6) precisa oferecer uma lista, e a
lista estaria vazia, ou pior: ofereceria o curso falso, e o aluno abriria a sala
matriculado nele. Seria o mesmo erro que a lei quis impedir, entrando por outra
porta.

O que estes testes protegem:

- **o id sai na tela**, porque é ele que a matrícula guarda e é ele que o
  mantenedor cola no comando que aponta as matrículas antigas;
- **rodar duas vezes não duplica**, porque o comando é colado num bloco e
  ninguém lembra se já rodou;
- **rodar de novo com outro nome não renomeia em silêncio**, porque o nome é o
  que a pessoa lê na hora de escolher.
"""

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.produtos.models import Product

pytestmark = pytest.mark.django_db


def _rodar(apelido, nome):
    saida = StringIO()
    call_command("criar_curso", apelido, nome, stdout=saida)
    return saida.getvalue()


def test_cria_o_curso_e_imprime_o_id_que_a_matricula_guarda():
    saida = _rodar("profissional", "Profissional")

    curso = Product.objects.get(slug="profissional")
    assert curso.name == "Profissional"
    assert curso.active is True
    assert "✅ criado" in saida
    assert str(curso.id) in saida


def test_o_preco_nasce_em_zero_porque_quem_cobra_e_a_oferta():
    """Zero aqui significa "não está à venda por este produto", não "de graça".

    Quem cobra é a `Offer`, que é por site. Se um dia este padrão virar um preço
    de verdade, a plataforma passa a ter dois lugares dizendo quanto custa.
    """
    _rodar("profissional", "Profissional")

    assert Product.objects.get(slug="profissional").price_cents == 0


def test_rodar_duas_vezes_nao_duplica():
    _rodar("profissional", "Profissional")
    saida = _rodar("profissional", "Profissional")

    assert Product.objects.filter(slug="profissional").count() == 1
    assert "já existia" in saida


def test_rodar_de_novo_com_outro_nome_avisa_e_nao_renomeia():
    _rodar("profissional", "Profissional")

    saida = _rodar("profissional", "Outro Nome Qualquer")

    assert Product.objects.get(slug="profissional").name == "Profissional"
    assert "OUTRO nome" in saida
    assert "Nada foi alterado" in saida


def test_o_apelido_e_normalizado_para_minusculas():
    """Quem cola o comando pode escrever com maiúscula, e dois apelidos que só
    diferem no caixa alto seriam dois cursos onde deveria haver um."""
    _rodar("Profissional", "Profissional")

    assert Product.objects.filter(slug="profissional").count() == 1


@pytest.mark.parametrize("apelido, nome", [("", "Profissional"), ("   ", "  ")])
def test_apelido_ou_nome_vazio_para_e_ensina_o_que_fazer(apelido, nome):
    with pytest.raises(CommandError) as erro:
        _rodar(apelido, nome)

    assert "não podem ser vazios" in str(erro.value)
    assert "criar_curso profissional" in str(erro.value)
    assert not Product.objects.exists()


def test_renomear_troca_o_nome_e_diz_qual_era():
    """A opção existe porque não há tela de produto no painel.

    Sem ela, quem errasse o nome de um curso não teria caminho nenhum para
    corrigir, e a recusa apontaria para uma tela que não existe. A saída diz o
    nome ANTIGO junto do novo: quem renomeia por engano precisa saber o que
    tinha antes para desfazer.
    """
    _rodar("profissional", "Profissional")

    saida = StringIO()
    call_command(
        "criar_curso",
        "profissional",
        "Meshcraft Profissional",
        "--renomear",
        stdout=saida,
    )

    assert Product.objects.get(slug="profissional").name == "Meshcraft Profissional"
    assert "Profissional" in saida.getvalue()
    assert "Meshcraft Profissional" in saida.getvalue()


def test_a_recusa_ensina_o_comando_que_renomeia():
    """A mensagem tem de servir para colar, com o apelido e o nome já dentro."""
    _rodar("profissional", "Profissional")

    saida = _rodar("profissional", "Meshcraft Profissional")

    assert "--renomear" in saida
    assert "criar_curso profissional 'Meshcraft Profissional' --renomear" in saida


def test_renomear_num_curso_que_nao_existe_apenas_cria():
    """Pedir para renomear o que não existe não é erro: o desfecho pedido é o
    mesmo (o curso passa a ter aquele nome), e recusar aqui só faria o
    mantenedor rodar duas vezes."""
    saida = StringIO()
    call_command("criar_curso", "novo", "Curso Novo", "--renomear", stdout=saida)

    assert Product.objects.get(slug="novo").name == "Curso Novo"
    assert "✅ criado" in saida.getvalue()


def test_renomear_com_o_mesmo_nome_nao_finge_que_mudou():
    _rodar("profissional", "Profissional")

    saida = StringIO()
    call_command(
        "criar_curso", "profissional", "Profissional", "--renomear", stdout=saida
    )

    assert "já existia" in saida.getvalue()
    assert "renomeado" not in saida.getvalue()
