"""O casamento de telefone — a peça onde o cruzamento em lote erraria calado.

Os casos aqui não são hipóteses: são as formas que apareceram na lista real do
mantenedor (345 números, 02/09/2026) cruzadas com as formas que o formulário do
site aceita. Números fictícios, a mesma FORMA dos reais.
"""

from apps.core.telefone import (
    chave_de,
    digitos,
    numeros_no_texto,
    sufixo_de,
)


class TestAMesmaPessoaEscritaDeVariosJeitos:
    """Tudo isto tem de casar — é uma pessoa só, anotada por mãos diferentes."""

    FORMAS = [
        "11 99999-8888",  # como o mantenedor anota
        "(11) 99999-8888",  # como o site mostra
        "+55 11 99999-8888",  # como a pessoa digita no cadastro
        "5511999998888",  # como um export de WhatsApp entrega
        "55 (11) 99999 8888",
        "11999998888",
        " 11 99999-8888 ",  # com sobra de espaço de um copiar-colar
    ]

    def test_todas_as_formas_dao_a_mesma_chave(self):
        chaves = {chave_de(f) for f in self.FORMAS}
        assert len(chaves) == 1, f"deviam ser a mesma pessoa, viraram {chaves}"

    def test_o_nono_digito_nao_separa_a_pessoa_dela_mesma(self):
        # O MESMO aparelho, anotado antes e depois da mudança de 2012.
        assert chave_de("11 99999-8888") == chave_de("11 9999-8888")


class TestOQueNaoPodeCasar:
    """A direção de erro que importa: casar demais libera acesso a estranho."""

    def test_ddds_diferentes_sao_pessoas_diferentes(self):
        assert chave_de("11 99999-8888") != chave_de("21 99999-8888")

    def test_numeros_diferentes_no_mesmo_ddd(self):
        assert chave_de("11 99999-8888") != chave_de("11 99999-8889")

    def test_fixo_nao_vira_celular(self):
        # Se a canônica ACRESCENTASSE o nono dígito em vez de derrubá-lo, este
        # fixo viraria `11 93333-4444` — o telefone de outra pessoa.
        assert chave_de("11 3333-4444") == "1133334444"

    def test_campo_vazio_nao_e_uma_pessoa(self):
        # Duas fichas sem WhatsApp não são "a mesma pessoa". Quem chama filtra
        # o vazio; este teste fixa que o vazio é reconhecível.
        assert chave_de("") == ""
        assert chave_de("   ") == ""
        assert chave_de("sem número") == ""


class TestQuemNaoEBrasileiro:
    """9 dos 345 números da lista real. Eles não podem virar 'não achei'."""

    def test_portugal_nove_digitos_sobrevive_inteiro(self):
        # Nenhum dígito é derrubado: não tem 11 dígitos, não começa com 55.
        assert chave_de("913 456 789") == "913456789"

    def test_o_mesmo_numero_de_portugal_com_e_sem_ddi(self):
        # Com o DDI, `351` fica — e é isso que MANTÉM as duas formas
        # diferentes. É honesto: só o `55` é derrubado, porque só do Brasil
        # sabemos o que sobra. A tela cobre este caso pela sugestão dos 8
        # dígitos finais, que o mantenedor confirma com um clique.
        assert sufixo_de("+351 913 456 789") == sufixo_de("913 456 789")

    def test_numero_truncado_sem_ddd_nao_explode(self):
        # Dois vieram assim na lista real. Não casam por chave (falta o DDD),
        # mas ainda geram sugestão — que é exatamente o desfecho correto.
        assert chave_de("360-4477") == "3604477"
        assert sufixo_de("360-4477") == "3604477"

    def test_o_curto_demais_nao_sugere_nada(self):
        # Sugestão que casa com todo mundo é pior que sugestão nenhuma.
        assert sufixo_de("12345") == ""


class TestSugestaoNaoEIgualdade:
    def test_mesmo_final_com_ddd_diferente_sugere_mas_nao_casa(self):
        a, b = "11 99999-8888", "21 99999-8888"
        assert chave_de(a) != chave_de(b), "casar isto liberaria a pessoa errada"
        assert sufixo_de(a) == sufixo_de(b), "mas vale mostrar para ele conferir"


class TestLerOArquivoDoMantenedor:
    """O formato real do `turmas.txt`, que ninguém vai ser obrigado a arrumar."""

    COLADO = """
TURMA PILOTO:
11 99999-8888, 21 9999-7777, 31 98888-6666

TURMA 1:
41 3333-4444,
913 456 789,
+55 51 99876-5432
"""

    def test_acha_todos_os_numeros_e_ignora_os_titulos(self):
        achados = numeros_no_texto(self.COLADO)
        assert len(achados) == 6, achados
        # `TURMA 1` não pode ter virado o telefone `1`.
        assert not any(len(digitos(n)) < 7 for n in achados)

    def test_repetido_entra_uma_vez_so(self):
        # A lista real tinha um número em duas turmas. É uma pessoa.
        texto = "11 99999-8888, 21 9999-7777, +55 (11) 99999-8888"
        assert len(numeros_no_texto(texto)) == 2

    def test_a_primeira_grafia_e_a_que_fica(self):
        texto = "11 99999-8888, 5511999998888"
        assert numeros_no_texto(texto) == ["11 99999-8888"]

    def test_texto_vazio_devolve_lista_vazia_e_nao_explode(self):
        assert numeros_no_texto("") == []
        assert numeros_no_texto(None) == []
