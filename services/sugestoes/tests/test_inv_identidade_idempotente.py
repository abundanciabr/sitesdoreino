"""[INVARIANTE] A mesma pessoa tem UMA linha local — e a linha ANTIGA é dela.

Duas metades, e a segunda é a que pagou a mudança de casa do login:

1. Idempotência (EVO-01 §3): dez visitas, uma linha. A garantia é do banco
   (`email` é `unique` + `get_or_create`), não de quem chama.
2. **Continuidade por e-mail (DECISAO-celula-de-identidade §3):** quem já era
   autor ANTES da virada — sugestões, votos, comentários apontando para a
   linha local — recupera exatamente aquela linha ao entrar pelo site. Foi
   este casamento que fez a migração de dados custar zero.
"""

from apps.sugestoes.models import Identidade, Sugestao
from tests.conftest import sessao_do_site


def test_visitas_repetidas_tem_uma_linha(entrar_como):
    primeira = entrar_como().identidade
    segunda = entrar_como().identidade
    assert primeira.id == segunda.id
    assert Identidade.objects.count() == 1


def test_nome_local_nao_e_sobrescrito_pelo_site(rede, db, matricula, entrar_como):
    """`nome_exibido` só é gravado na CUNHAGEM: o campo é editável pela pessoa,
    e o provedor não pode apagar essa escolha a cada visita."""
    pessoa = entrar_como(nome="João")
    Identidade.objects.filter(pk=pessoa.identidade.id).update(
        nome_exibido="Nome Escolhido"
    )

    de_novo = entrar_como(nome="João Do Google")

    assert de_novo.identidade.nome_exibido == "Nome Escolhido"


def test_autor_de_antes_da_virada_recupera_a_propria_linha(
    rede, db, matricula, quadro, categoria
):
    """A prova da continuidade: a sugestão antiga continua sendo DELE."""
    veterano = Identidade.objects.create(
        email="veterano@exemplo.test", nome_exibido="Veterano"
    )
    antiga = Sugestao.objects.create(
        quadro=quadro,
        categoria=categoria,
        autor=veterano,
        titulo="Sugestão de antes da virada",
        problema="Escrita quando o login ainda morava na Caixa.",
    )

    rede.alunos_diz("veterano@exemplo.test", [matricula])
    pessoa = sessao_do_site(rede, email="veterano@exemplo.test", nome="V. Do Site")
    assert pessoa.esta_dentro

    assert pessoa.identidade.id == veterano.id, "cunhou uma segunda pessoa"
    assert Identidade.objects.count() == 1
    antiga.refresh_from_db()
    assert antiga.autor_id == veterano.id
    assert (
        pessoa.identidade.nome_exibido == "Veterano"
    ), "a cunhagem sobrescreveu o nome de uma linha que já existia"
