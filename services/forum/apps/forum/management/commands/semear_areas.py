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

AS PERMISSÕES MUDARAM EM 30/08/2026, E QUEM MUDOU FOI O MANTENEDOR
------------------------------------------------------------------
A pergunta que estava em aberto (lei §6.3 — *"quem escreve nas áreas
públicas?"*) foi respondida por ele em 30/08/2026, registro `20260830-021`:
**em página pública, só a escola fala; onde aluno escreve, exige login; e só
aluno matriculado escreve.** O motivo declarado é o público desta escola:
criança e adolescente não ficam expostos a estranho. O preço, aceito por ele na
mesma escolha: o fórum sai do alcance de buscador.

Na prática isto virou o seed abaixo: **`duvidas` e `mostre-seu-trabalho`, que
nasceram públicas, agora são de ALUNOS.** A única área que continua pública é
`avisos`, porque nela quem publica é a equipe — ou seja, a página que o mundo
inteiro lê é só a voz da escola.

A lei §5 continua mandando áreas MISTAS, e continua sendo o que estas quatro
dão: o visitante enxerga uma, o aluno enxerga quatro.

**Não é este comando que fecha o que já estava aberto.** Ele é idempotente e de
propósito não atualiza o que existe (não pisa em edição humana), então as áreas
que já nasceram em produção não seriam alcançadas por ele. Quem as fecha é a
migração `0002_pagina_publica_so_a_escola_fala`, e é lá que a restrição do banco
torna a combinação proibida impossível. Guarda: `tests/test_semear_areas.py`.
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
        # De ALUNOS, e não pública: é aqui que o aluno escreve, e mensagem de
        # aluno não aparece em página aberta a estranhos (decisão de
        # 30/08/2026). Quem tem cadastro sem matrícula não enxerga.
        Area.Visibilidade.ALUNOS,
        Area.QuemEscreve.ALUNO,
    ),
    (
        "mostre-seu-trabalho",
        "Mostre seu trabalho",
        "O que você está construindo. Modelo pela metade também conta: é vendo "
        "o meio do caminho que se aprende o caminho.",
        20,
        # A parte mais exposta da escola vira a mais fechada: aqui aparecem
        # rosto, nome de jogo e trabalho de criança.
        Area.Visibilidade.ALUNOS,
        Area.QuemEscreve.ALUNO,
    ),
    (
        "avisos",
        "Avisos da escola",
        "O que a escola precisa contar para todo mundo: turmas, mudanças, datas. "
        "Só a equipe publica aqui.",
        30,
        # A ÚNICA que continua pública, e ela só pode continuar porque quem
        # escreve aqui é a equipe. A restrição do banco
        # (`pagina_publica_so_a_escola_fala`) recusaria qualquer outra
        # combinação.
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
