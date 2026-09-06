"""Semeia o ESQUELETO do curso: o que ja esta na lei, e nada do que e obra.

O QUE ENTRA, E O QUE NAO ENTRA DE PROPOSITO
--------------------------------------------
Entra o que o plano (`PLANO-CELULA-CURSOS.md` secao 4) ja diz em publico: um
curso (`profissional`, rascunho), os 12 blocos com letra e parte, as 34 aulas so
com numero, ordem, bloco e titulo exibido, e os 13 instrumentos so com slug,
nome canonico e numero do cartao.

NAO entra nenhum pedido, nenhum cliente, nenhuma peca, nenhuma pausa, nenhum
nome de bloco, nenhuma escala de instrumento. Este repositorio e PUBLICO e o
curso e obra nao lancada do mantenedor (`armadilhas/331`): o texto entra pela
tela do Admin (degrau 1.5) pela porta de maquina (degrau 1.3). A ausencia aqui
e a decisao, nao esquecimento.

POR QUE UM COMANDO, E NAO UMA MIGRACAO DE DADOS
-----------------------------------------------
A mesma decisao do `semear_areas` do forum, do `semear_economia` da gamificacao
e do `semear_parametros` das encomendas: migracao de dados entra no banco de
TODO teste, e uma fixture que criasse uma aula colidiria com o teste que mede a
tabela vazia. E ha a razao de dono: a partir do primeiro INSERT, estas linhas
sao do mantenedor. Guarda: `tests/test_inv_c2_conteudo_so_pela_porta.py`.

IDEMPOTENTE, E QUE NAO PISA EM CIMA DE EDICAO HUMANA
-----------------------------------------------------
`get_or_create` pela chave natural (o slug do curso, a ordem do bloco, o numero
da aula, o slug do instrumento). Rodar duas vezes nao duplica nada, e o
esqueleto entra inteiro ou nao entra: a transacao e uma so.

ELE RECONCILIA A ESTRUTURA, E SO A ESTRUTURA (05/09/2026)
----------------------------------------------------------
Ate esta data ele nao atualizava NADA do que ja existia, e isso deixava um
buraco medido: o curso nasceu na VPS em 05/09, e corrigir a receita nao mudava
o bolo ja assado. Quando a estrutura do livro mudasse, o esqueleto de la ficava
para tras em silencio.

A partir daqui ele reconcilia, e a fronteira e dura:

  ESTRUTURA (ele escreve):  o slug e o nome do curso, a letra e a parte do
                            bloco, o bloco e a ordem de cada aula, `e_boss` e
                            `banca_nivel`. Sao fatos do LIVRO, publicos, e a
                            fonte deles e este arquivo.
  OBRA (ele NUNCA toca):    titulo_exibido, pedido, cliente, minimo,
                            aceito_quando, quiz, video_url, estado, versao,
                            publicada_em, as pecas, as pausas, o nome do bloco
                            e o titulo do Boss. Sao do mantenedor e entram pela
                            tela (`armadilhas/331`, [INV-CUR-C2]).

Guarda: `tests/test_semeador_reconcilia_estrutura.py` escreve obra, roda o
semeador de novo e prova que a obra continua intacta.

POR QUE NAO E UMA MIGRACAO DE DADOS: alem das razoes acima, o guarda
`test_nenhuma_migracao_desta_celula_roda_codigo` proibe `RunPython` nesta
celula, e reconciliar estrutura por migracao seria exatamente isso.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.cursos.models import Aula, Bloco, Curso, Instrumento

SLUG_DO_CURSO = "profissional"
NOME_DO_CURSO = "Profissional"

# Os 12 blocos na ordem (1 a 12): letra, parte, e as aulas de cada um. A ordem
# de cada aula e a posicao dela nesta lista, do zero: E00 e a ordem 0, E32 e a
# 32, e a bonus EB e a 33.
BLOCOS = (
    ("A", 1, ("E00", "E01", "E02")),
    ("B", 1, ("E03", "E04", "E05")),
    ("C", 1, ("E06", "E07", "E08")),
    ("D", 1, ("E09", "E10")),
    ("E", 2, ("E11", "E12", "E13", "E14")),
    ("F", 2, ("E15", "E16")),
    ("G", 2, ("E17", "E18")),
    ("H", 2, ("E19", "E20", "E21")),
    ("I", 3, ("E22", "E23", "E24", "E25")),
    ("J", 3, ("E26", "E27")),
    ("K", 3, ("E28", "E29", "E30")),
    ("L", 3, ("E31", "E32", "EB")),
)

# O BOSS de cada bloco, e ele NAO e "a ultima aula do bloco" (a hierarquia do
# livro, §3). Escrito na mao, encomenda por encomenda, porque a bonus EB fecha
# a lista do bloco L sem ser o Boss dele: deduzir "o ultimo" poria o Boss na
# encomenda errada, e o aluno estara com o livro aberto ao lado da tela.
COM_BOSS = (
    "E02",  # bloco A, "O Diorama"
    "E05",  # bloco B, "O Kit do Aventureiro"
    "E08",  # bloco C, "O Kit do Aventureiro no jogo"
    "E10",  # bloco D, a Encomenda da Semana real
    "E14",  # bloco E, "O Guarda-Roupa"
    "E16",  # bloco F, "A Garagem"
    "E18",  # bloco G, "A Vitrine Viva"
    "E21",  # bloco H, a maior encomenda real
    "E25",  # bloco I, "A Personagem"
    "E27",  # bloco J, "A Linha"
    "E30",  # bloco K, "O Estudio"
    "E32",  # bloco L, um mes sem uma peca propria
)

# A BANCA fecha cada Parte, na ultima encomenda dela (a hierarquia do livro,
# §2): E10 fecha a Parte I, E21 a II, E32 a III. O nivel e o mesmo numero da
# Parte, e o titulo conferido (Modelador Nivel 1, 2, 3) e da gamificacao.
BANCA_POR_AULA = {"E10": 1, "E21": 2, "E32": 3}

# Os 13 instrumentos: slug canonico, nome canonico, numero do cartao.
INSTRUMENTOS = (
    ("studs", "Teste STUDS", 1),
    ("rubrica_de_encomenda", "Rubrica de Encomenda", 2),
    ("rubrica_de_produto", "Rubrica de Produto", 3),
    ("pronto_para_sair", "Pronto para sair", 4),
    ("validacao_no_motor", "Validação no motor", 5),
    ("prova_dos_3_movimentos", "Prova dos 3 Movimentos", 6),
    ("prova_das_5_expressoes", "Prova das 5 Expressões", 7),
    ("selo_ugc", "Selo UGC", 8),
    ("selo_ugc_personagem", "Selo UGC de Personagem", 9),
    ("ficha_de_serie", "Ficha de Série", 10),
    ("ficha_de_delegacao", "Ficha de Delegação", 11),
    ("revisao_de_estudio", "Revisão de Estúdio", 12),
    ("laudo_de_banca", "Laudo de Banca", 13),
)


def titulo_exibido(numero: str) -> str:
    """O titulo que o aluno le: Encomenda 00 a Encomenda 32; a bonus e Encomenda Bônus."""
    if numero == "EB":
        return "Encomenda Bônus"
    return f"Encomenda {numero[1:]}"


class Command(BaseCommand):
    help = (
        "Semeia o esqueleto do curso: 1 curso, 12 blocos, 34 aulas e 13 "
        "instrumentos, sem nenhum texto. Idempotente."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--site",
            required=True,
            help="o site_id que recebe o curso (Lei 9: uma fabrica, N lojas)",
        )

    @transaction.atomic
    def handle(self, *args, **opcoes):
        site = opcoes["site"]

        # O curso de antes de 05/09/2026 nasceu com o slug `meshcraft`, quando
        # ainda nao se sabia que os niveis (basico, profissional, empresario)
        # seriam CURSOS. Reconciliar aqui, e nao por migracao, e o que mantem o
        # endereco `/cursos/<curso>/...` honesto sem quebrar o guarda que
        # proibe codigo em migracao desta celula.
        renomeados = Curso.objects.filter(site_id=site, slug="meshcraft").update(
            slug=SLUG_DO_CURSO, nome=NOME_DO_CURSO
        )

        curso, curso_novo = Curso.objects.get_or_create(
            site_id=site, slug=SLUG_DO_CURSO, defaults={"nome": NOME_DO_CURSO}
        )

        blocos_novos = aulas_novas = 0
        estrutura_corrigida = 0
        ordem_da_aula = 0
        for ordem_do_bloco, (letra, parte, numeros) in enumerate(BLOCOS, start=1):
            bloco, novo = Bloco.objects.get_or_create(
                curso=curso,
                ordem=ordem_do_bloco,
                defaults={"letra": letra, "parte": parte},
            )
            blocos_novos += novo
            if not novo and (bloco.letra, bloco.parte) != (letra, parte):
                bloco.letra, bloco.parte = letra, parte
                bloco.save(update_fields=["letra", "parte"])
                estrutura_corrigida += 1
            for numero in numeros:
                estrutural = {
                    "bloco": bloco,
                    "ordem": ordem_da_aula,
                    "e_boss": numero in COM_BOSS,
                    "banca_nivel": BANCA_POR_AULA.get(numero),
                }
                aula, novo = Aula.objects.get_or_create(
                    curso=curso,
                    numero=numero,
                    defaults={**estrutural, "titulo_exibido": titulo_exibido(numero)},
                )
                aulas_novas += novo
                if not novo:
                    # SO os quatro campos de `estrutural`. `titulo_exibido` fica
                    # de fora de proposito: ele e o texto que o aluno le, e uma
                    # vez escrito pela tela e obra do mantenedor.
                    mudou = [
                        campo
                        for campo, valor in estrutural.items()
                        if getattr(aula, campo) != valor
                    ]
                    if mudou:
                        for campo in mudou:
                            setattr(aula, campo, estrutural[campo])
                        aula.save(update_fields=mudou)
                        estrutura_corrigida += 1
                ordem_da_aula += 1

        instrumentos_novos = 0
        for slug, nome_canonico, cartao in INSTRUMENTOS:
            _, novo = Instrumento.objects.get_or_create(
                slug=slug, defaults={"nome_canonico": nome_canonico, "cartao": cartao}
            )
            instrumentos_novos += novo

        self.stdout.write(
            f"esqueleto: curso {'criado' if curso_novo else 'ja existia'}, "
            f"{blocos_novos} bloco(s) novo(s), {aulas_novas} aula(s) nova(s), "
            f"{instrumentos_novos} instrumento(s) novo(s) (site {site})."
        )
        if renomeados:
            self.stdout.write(
                f"  o curso `meshcraft` passou a se chamar `{SLUG_DO_CURSO}`."
            )
        if estrutura_corrigida:
            self.stdout.write(
                f"  estrutura do livro reconciliada em {estrutura_corrigida} "
                "linha(s) que ja existiam; nenhum texto seu foi tocado."
            )
