"""Cria as primeiras áreas do fórum — para ele deixar de nascer vazio.

POR QUE UM COMANDO, E NÃO UMA MIGRAÇÃO DE DADOS
-----------------------------------------------
Foi tentado como migração primeiro, e a suíte respondeu na hora: **20 testes
quebraram**, a maioria com `UniqueViolation` em `forum_area_slug_key`. Uma
migração de dados entra no banco de TODO teste, então cada fixture que criasse
uma área com nome natural (`duvidas`) colidiria — e todo teste que afirma "o
fórum vazio faz X" deixaria de poder existir.

Isso não é incômodo de teste, é sinal de desenho: **semear é conteúdo, não
esquema.** A casa já tinha decidido assim — `infra/semear-caixa.sh` inaugura o
quadro da Caixa por comando, não por migração.

E há a razão de dono: a partir do momento em que estas áreas existem, elas são
do mantenedor. Uma migração as recriaria em todo ambiente novo, inclusive as que
ele tivesse apagado de propósito. Um comando roda quando alguém manda.

IDEMPOTENTE, E QUE NÃO PISA EM CIMA DE EDIÇÃO HUMANA
----------------------------------------------------
`get_or_create` pelo `slug`, e **sem** atualizar o que já existe. Se ele
renomear "Dúvidas gerais" ou desativar uma área, rodar de novo não desfaz.
Semear é dar o primeiro empurrão, nunca ficar de dono.

AS PERMISSÕES FICAM NO LADO FECHADO, DE PROPÓSITO
--------------------------------------------------
A lei §5 manda áreas MISTAS, e é o que estas quatro dão: o visitante enxerga
três, o aluno enxerga quatro.

Mas *"quem escreve nas áreas públicas — só aluno, ou também quem tem cadastro
sem ter comprado?"* está EM ABERTO e é decisão do mantenedor (lei §6.3).
Semear com `cadastrado` tomaria essa decisão por ele — e justamente na opção
que exige anti-spam de verdade. Fica `aluno`, o lado seguro; mudar é uma linha
no dia em que ele responder. Guarda: `tests/test_semear_areas.py`.
"""

from django.core.management.base import BaseCommand

from apps.forum.models import Area

# (slug, nome, descrição, ordem, visibilidade, quem_escreve)
PRIMEIRAS = [
    (
        "duvidas",
        "Dúvidas gerais",
        "Travou no Studio, o script não roda, a peça não encaixa? Pergunte aqui. "
        "Dúvida respondida vira resposta para quem chegar depois.",
        10,
        Area.Visibilidade.PUBLICA,
        Area.QuemEscreve.ALUNO,
    ),
    (
        "mostre-seu-trabalho",
        "Mostre seu trabalho",
        "O que você está construindo. Modelo pela metade também conta — é vendo "
        "o meio do caminho que se aprende o caminho.",
        20,
        Area.Visibilidade.PUBLICA,
        Area.QuemEscreve.ALUNO,
    ),
    (
        "avisos",
        "Avisos da escola",
        "O que a escola precisa contar para todo mundo: turmas, mudanças, datas. "
        "Só a equipe publica aqui.",
        30,
        Area.Visibilidade.PUBLICA,
        Area.QuemEscreve.EQUIPE,
    ),
    (
        "sala-dos-alunos",
        "Sala dos alunos",
        "A área de quem está matriculado. Conversa de turma, combinados e o que "
        "não é para o mundo inteiro ler.",
        40,
        Area.Visibilidade.ALUNOS,
        Area.QuemEscreve.ALUNO,
    ),
]


class Command(BaseCommand):
    help = "Cria as primeiras áreas do fórum (idempotente; não altera o que já existe)"

    def handle(self, *args, **opcoes):
        criadas, mantidas = [], []
        for slug, nome, descricao, ordem, visibilidade, quem_escreve in PRIMEIRAS:
            _, nasceu = Area.objects.get_or_create(
                slug=slug,
                defaults={
                    "nome": nome,
                    "descricao": descricao,
                    "ordem": ordem,
                    "ativa": True,
                    "visibilidade": visibilidade,
                    "quem_escreve": quem_escreve,
                    "curso_id": "",
                },
            )
            (criadas if nasceu else mantidas).append(slug)

        for slug in criadas:
            self.stdout.write(f"  criada ....... {slug}")
        for slug in mantidas:
            self.stdout.write(f"  ja existia ... {slug} (nao toquei)")

        publicas = Area.objects.filter(
            ativa=True, visibilidade=Area.Visibilidade.PUBLICA
        ).count()
        total = Area.objects.filter(ativa=True).count()
        self.stdout.write(f"AREAS ATIVAS: {total} ({publicas} publicas)")
        # A linha que o pipeline procura. Só existe aqui, no fim do caminho
        # feliz — nunca no eco do script (`armadilhas/114`).
        self.stdout.write("SEMEADURA DO FORUM OK")
