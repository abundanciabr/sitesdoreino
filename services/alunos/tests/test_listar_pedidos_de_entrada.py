"""A lista de quem pediu entrada: o agrupamento, a contagem e o filtro que recusa.

Quatro fatos que este comando precisa garantir, e que um erro em qualquer um
deles produziria uma lista errada com cara de certa:

1. **A unidade é a PESSOA, não a matrícula.** Quem tem dois cursos aparece uma
   vez, com a situação do pedido mais recente. Contar linhas daria um total
   maior que a quantidade de gente, e um total que não bate ensina quem lê a
   ignorar o relatório inteiro.
2. **`--exceto` tira quem SÓ tem aquela situação.** Alguém com um pedido
   recusado e outro ativo é aluno, e continua na lista. Filtrar por linha
   apagaria essa pessoa da concessão sem ninguém perceber.
3. **Situação que não existe é RECUSA, nunca filtro vazio.** É o guarda mais
   importante daqui: `--exceto recusadas` (com o "s" a mais) aceito em silêncio
   não excluiria ninguém, e a lista sairia maior do que quem a leu imaginava.
4. **O formato de máquina imprime e-mails e nada mais.** Cabeçalho, total ou
   linha em branco na saída viraria um "e-mail" na lista de quem a consome.
"""

from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.matriculas.models import Matricula

pytestmark = pytest.mark.django_db

SITE = "site-de-teste"
OUTRO_SITE = "site-da-vizinha"


def _pedido(email: str, status: str, *, site: str = SITE, nome: str = "") -> Matricula:
    """Uma linha de pedido. `order_id` único porque a coluna é `unique` global."""
    return Matricula.objects.create(
        site_id=site,
        order_id=f"ordem-{Matricula.objects.count()}-{email}-{status}",
        email=email,
        name=nome or f"Pessoa {email.split('@')[0]}",
        status=status,
    )


def _rodar(*, exceto: str | None = None, formato: str | None = None) -> str:
    saida = StringIO()
    argumentos = ["--site", SITE]
    if exceto is not None:
        argumentos += ["--exceto", exceto]
    if formato is not None:
        argumentos += ["--formato", formato]
    call_command("listar_pedidos_de_entrada", *argumentos, stdout=saida)
    return saida.getvalue()


# ------------------------------------------- 1. o agrupamento e a contagem


def test_agrupa_por_situacao_e_conta_cada_grupo():
    _pedido("ana@exemplo.test", Matricula.STATUS_ATIVA)
    _pedido("bruno@exemplo.test", Matricula.STATUS_ATIVA)
    _pedido("carla@exemplo.test", Matricula.STATUS_AGUARDANDO)
    _pedido("dario@exemplo.test", Matricula.STATUS_RECUSADA)

    saida = _rodar()

    assert "Pedidos de entrada no site 'site-de-teste': 4 pessoa(s)." in saida
    assert "ativa (2):" in saida
    assert "aguardando (1):" in saida
    assert "recusada (1):" in saida
    assert "TOTAL na lista: 4 pessoa(s)." in saida


def test_grupo_vazio_aparece_com_zero_em_vez_de_sumir():
    """Grupo que some da tela some justamente quando é a notícia importante.

    "encerrada (0)" é o que diz a quem lê que ninguém saiu da escola. Uma saída
    condicional deixaria essa pergunta sem resposta, e quem lê concluiria o que
    quisesse.
    """
    _pedido("ana@exemplo.test", Matricula.STATUS_ATIVA)

    saida = _rodar()

    assert "encerrada (0):" in saida
    assert "suspensa (0):" in saida


def test_quem_tem_dois_cursos_aparece_uma_vez_com_a_situacao_mais_recente():
    """A unidade é a pessoa. Contar linhas daria um total que não bate com gente."""
    _pedido("ana@exemplo.test", Matricula.STATUS_AGUARDANDO)
    _pedido("ana@exemplo.test", Matricula.STATUS_ATIVA)

    saida = _rodar()

    assert "1 pessoa(s)." in saida
    assert "ativa (1):" in saida
    assert "aguardando (0):" in saida
    assert saida.count("ana@exemplo.test") == 1


def test_o_mesmo_email_em_caixas_diferentes_e_a_mesma_pessoa():
    """Caixa baixa só para COMPARAR: o e-mail impresso é o que está gravado."""
    _pedido("Ana@Exemplo.test", Matricula.STATUS_AGUARDANDO)
    _pedido("ana@exemplo.test", Matricula.STATUS_ATIVA)

    saida = _rodar()

    assert "1 pessoa(s)." in saida
    assert "ana@exemplo.test" in saida


def test_pedido_de_outro_site_nao_entra_na_lista():
    _pedido("ana@exemplo.test", Matricula.STATUS_ATIVA)
    _pedido("vizinha@exemplo.test", Matricula.STATUS_ATIVA, site=OUTRO_SITE)

    saida = _rodar()

    assert "1 pessoa(s)." in saida
    assert "vizinha@exemplo.test" not in saida


def test_escola_sem_ninguem_diz_zero_em_vez_de_ficar_muda():
    saida = _rodar()

    assert "0 pessoa(s)." in saida
    assert "TOTAL na lista: 0 pessoa(s)." in saida


# ------------------------------------------- 2. o filtro


def test_exceto_tira_o_grupo_e_conta_quem_ficou_de_fora():
    _pedido("ana@exemplo.test", Matricula.STATUS_ATIVA)
    _pedido("dario@exemplo.test", Matricula.STATUS_RECUSADA)

    saida = _rodar(exceto="recusada")

    assert "1 pessoa(s)." in saida
    assert "ficaram de fora, porque só têm pedido recusada (1):" in saida
    assert "dario@exemplo.test" in saida
    assert "TOTAL na lista: 1 pessoa(s)." in saida


def test_quem_foi_recusado_uma_vez_e_aluno_agora_continua_na_lista():
    """`--exceto` tira quem SÓ tem aquela situação, e a diferença não é sutil.

    Filtrar linha a linha apagaria da concessão uma pessoa que é aluna hoje,
    porque ela um dia teve um pedido negado. Ninguém perceberia: ela
    simplesmente não receberia a medalha.
    """
    _pedido("ana@exemplo.test", Matricula.STATUS_RECUSADA)
    _pedido("ana@exemplo.test", Matricula.STATUS_ATIVA)

    saida = _rodar(exceto="recusada")

    assert "1 pessoa(s)." in saida
    assert "ativa (1):" in saida
    assert "ficaram de fora, porque só têm pedido recusada (0):" in saida


def test_sem_exceto_ninguem_fica_de_fora_e_a_secao_nem_aparece():
    """Sem opção, o comando não tem política própria: lista todo mundo."""
    _pedido("dario@exemplo.test", Matricula.STATUS_RECUSADA)

    saida = _rodar()

    assert "recusada (1):" in saida
    assert "ficaram de fora" not in saida


def test_exceto_aceita_virgula_e_repeticao_como_uma_pessoa_escreveria():
    _pedido("ana@exemplo.test", Matricula.STATUS_ATIVA)
    _pedido("dario@exemplo.test", Matricula.STATUS_RECUSADA)
    _pedido("elza@exemplo.test", Matricula.STATUS_ENCERRADA)

    saida = _rodar(exceto="recusada, encerrada")

    assert "1 pessoa(s)." in saida
    assert "ficaram de fora, porque só têm pedido recusada, encerrada (2):" in saida


# ------------------------------------------- 3. a recusa que mais importa


def test_situacao_inventada_recusa_alto_em_vez_de_filtrar_nada():
    """O guarda central: um nome errado não pode virar um filtro vazio.

    `--exceto recusadas` aceito em silêncio deixaria os recusados DENTRO da
    lista, e quem leu a linha de comando teria certeza do contrário. Erro que
    aumenta a lista de quem recebe algo precisa falhar alto.
    """
    _pedido("dario@exemplo.test", Matricula.STATUS_RECUSADA)

    with pytest.raises(CommandError) as recusa:
        _rodar(exceto="recusadas")

    assert "PAROU POR SEGURANÇA" in str(recusa.value)
    assert "'recusadas'" in str(recusa.value)
    assert "recusada" in str(recusa.value)
    assert "Nada foi listado." in str(recusa.value)


def test_uma_situacao_certa_junto_de_uma_errada_tambem_recusa():
    """Metade certa não é certa: a recusa vale para o pedido inteiro."""
    _pedido("ana@exemplo.test", Matricula.STATUS_ATIVA)

    with pytest.raises(CommandError, match="PAROU POR SEGURANÇA"):
        _rodar(exceto="recusada,inventada")


# ------------------------------------------- 4. o formato de máquina


def test_formato_emails_imprime_so_emails_um_por_linha():
    """A saída alimenta um `$(...)` de script: qualquer enfeite vira um e-mail."""
    _pedido("ana@exemplo.test", Matricula.STATUS_ATIVA)
    _pedido("carla@exemplo.test", Matricula.STATUS_AGUARDANDO)

    saida = _rodar(formato="emails")

    linhas = [linha for linha in saida.splitlines() if linha.strip()]
    assert linhas == ["ana@exemplo.test", "carla@exemplo.test"]
    assert len(saida.splitlines()) == 2
    assert "pessoa(s)" not in saida
    assert "TOTAL" not in saida


def test_formato_emails_respeita_o_mesmo_filtro_da_tela():
    """Os dois formatos são a MESMA verdade. Discordar aqui seria o pior defeito.

    Uma lista que a tela mostra sem alguém e a máquina consome com essa pessoa
    dentro faria o mantenedor aprovar uma coisa e a plataforma executar outra.
    """
    _pedido("ana@exemplo.test", Matricula.STATUS_ATIVA)
    _pedido("dario@exemplo.test", Matricula.STATUS_RECUSADA)

    saida = _rodar(exceto="recusada", formato="emails")

    assert saida.splitlines() == ["ana@exemplo.test"]


def test_formato_emails_de_escola_vazia_sai_vazio_de_verdade():
    saida = _rodar(formato="emails")

    assert saida.strip() == ""


def test_formato_emails_nao_repete_quem_tem_dois_cursos():
    _pedido("ana@exemplo.test", Matricula.STATUS_ATIVA)
    _pedido("ana@exemplo.test", Matricula.STATUS_AGUARDANDO)

    saida = _rodar(formato="emails")

    assert saida.splitlines() == ["ana@exemplo.test"]


# ------------------------------------------- 5. só lê


def test_o_comando_nao_escreve_nada_no_banco():
    """Rodar duas vezes dá a mesma resposta, e o banco não muda entre elas."""
    _pedido("ana@exemplo.test", Matricula.STATUS_ATIVA)
    antes = Matricula.objects.count()

    primeira = _rodar()
    segunda = _rodar()

    assert primeira == segunda
    assert Matricula.objects.count() == antes
