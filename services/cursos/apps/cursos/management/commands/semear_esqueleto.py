"""Semeia o ESQUELETO do curso: o que ja esta na lei, e nada do que e obra.

O QUE ENTRA, E O QUE NAO ENTRA DE PROPOSITO
--------------------------------------------
Entra o que o plano (`PLANO-CELULA-CURSOS.md` secao 4) ja diz em publico: um
curso (`meshcraft`, rascunho), os 12 blocos com letra e parte, as 34 aulas so
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
da aula, o slug do instrumento), sem atualizar o que ja existe. Rodar duas vezes
nao duplica nada; e se ele renomear um titulo pela tela, rodar de novo nao
desfaz. O esqueleto entra inteiro ou nao entra: a transacao e uma so.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.cursos.models import Aula, Bloco, Curso, Instrumento

SLUG_DO_CURSO = "meshcraft"
NOME_DO_CURSO = "Meshcraft"

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

        curso, curso_novo = Curso.objects.get_or_create(
            site_id=site, slug=SLUG_DO_CURSO, defaults={"nome": NOME_DO_CURSO}
        )

        blocos_novos = aulas_novas = 0
        ordem_da_aula = 0
        for ordem_do_bloco, (letra, parte, numeros) in enumerate(BLOCOS, start=1):
            bloco, novo = Bloco.objects.get_or_create(
                curso=curso,
                ordem=ordem_do_bloco,
                defaults={"letra": letra, "parte": parte},
            )
            blocos_novos += novo
            for numero in numeros:
                _, novo = Aula.objects.get_or_create(
                    curso=curso,
                    numero=numero,
                    defaults={
                        "bloco": bloco,
                        "ordem": ordem_da_aula,
                        "titulo_exibido": titulo_exibido(numero),
                    },
                )
                aulas_novas += novo
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
