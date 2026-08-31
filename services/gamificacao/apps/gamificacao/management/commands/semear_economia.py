"""Semeia a economia da gamificação — e semeia TUDO DESLIGADO.

POR QUE UM COMANDO, E NÃO UMA MIGRAÇÃO DE DADOS
-----------------------------------------------
Mesma decisão do `semear_areas` do fórum, pelo mesmo motivo medido lá: migração
de dados entra no banco de TODO teste, e qualquer fixture que criasse uma regra
com slug natural colidiria. Semear é CONTEÚDO, não esquema.

E há a razão de dono: a partir do momento em que estas linhas existem, elas são
do mantenedor. Uma migração as recriaria em todo ambiente novo, inclusive as que
ele tivesse apagado de propósito. Um comando roda quando alguém manda.

POR QUE TUDO NASCE `ativa=False`
--------------------------------
A economia é DADO (lei §10.5): ajustar é UPDATE + versão, anunciado e nunca
retroativo. Se semear já ligasse as regras, um `deploy` viraria uma mudança de
economia sem ninguém decidir nada, e a escola descobriria pela reclamação dos
alunos. Ligar uma regra é decisão do mantenedor, com data e aviso.

A calibração fina dos números é a decisão 4 da Sessão A: a escala de referência
do parecer 6 fica como ponto de partida, com a propriedade que importa
preservada, que é validação humana valer cerca de dez vezes o consumo. As regras
que carregam essa proporção são as do fórum (resposta aceita, ajuda validada), e
elas NÃO estão aqui: os quatro eventos `forum.*` só se congelam na Sessão B, e
semear regra para evento que não existe seria promessa em tabela.

IDEMPOTENTE, E QUE NÃO PISA EM CIMA DE EDIÇÃO HUMANA
----------------------------------------------------
`get_or_create` pelo par (site, slug), e sem atualizar o que já existe. Se o
mantenedor mudar um número ou desligar uma linha, rodar de novo não desfaz.

O QUE NÃO É SEMEADO, DE PROPÓSITO
---------------------------------
- **Regra de login.** Login vale 0 XP, sempre (decisão fechada 7 da Sessão A), e
  a garantia é a AUSÊNCIA de regra, não uma regra valendo zero.
- **Marco pagando XP.** Todo marco entra com `pontos=0`, e o banco recusa o
  contrário (`marco_real_rende_zero_xp`).
- **Escudo na loja.** Ele é 1 por mês, automático e grátis, e mora na
  `Sequencia`. Não existe item de loja para ele, nem por Cristais.
"""

from django.core.management.base import BaseCommand

from apps.gamificacao.models import (
    ConquistaDefinicao,
    ItemCosmetico,
    LigaDefinicao,
    MissaoDefinicao,
    NivelDefinicao,
    RegraDePontuacao,
)

# (nivel, xp_necessario, titulo, titulo_feminino)
# Curva acelerada no comecinho: os primeiros degraus custam pouco de propósito,
# porque é ali que a pessoa decide se isto vale o tempo dela. Os títulos não
# falam a língua de credencial (nada de "certificado", "profissional"): a base
# é Aprendiz, Oficial, Mestre de Ateliê.
NIVEIS = [
    (1, 0, "Aprendiz", "Aprendiz"),
    (2, 50, "Aprendiz de Ateliê", "Aprendiz de Ateliê"),
    (3, 150, "Modelador", "Modeladora"),
    (4, 350, "Modelador de Ateliê", "Modeladora de Ateliê"),
    (5, 700, "Oficial", "Oficial"),
    (6, 1200, "Oficial de Ateliê", "Oficial de Ateliê"),
    (7, 2000, "Artesão", "Artesã"),
    (8, 3200, "Artesão de Ateliê", "Artesã de Ateliê"),
    (9, 5000, "Mestre", "Mestra"),
    (10, 7500, "Mestre de Ateliê", "Mestra de Ateliê"),
]

# (slug, evento_gatilho, beneficiario, pontos, cristais, acoes_cheias_por_dia,
#  quarentena_horas)
# Só eventos JÁ CONGELADOS, mais a tomada futura da aula. Quarentena de 24h no
# que é social: se o conteúdo de origem for moderado, o estorno acontece antes
# de o número virar parte da identidade de alguém.
REGRAS = [
    ("quiz-aprovado", "quiz.completado.v1", "ator", 30, 0, 3, 0),
    ("sugestao-criada", "sugestao.criada.v1", "ator", 10, 0, 3, 24),
    ("voto-dado", "sugestao.voto-adicionado.v1", "ator", 2, 0, 10, 24),
    ("sugestao-votada", "sugestao.voto-adicionado.v1", "autor_do_alvo", 5, 0, 0, 24),
    (
        "sugestao-implementada",
        "sugestao.status-alterado.v2",
        "autor_do_alvo",
        40,
        5,
        0,
        0,
    ),
    # A TOMADA FUTURA do §3 do plano: uma linha, desligada, esperando o evento
    # nascer. Note a direção: a célula LÊ que a aula terminou. Nada aqui decide
    # se alguém pode assisti-la, e é isso que o terceiro invariante protege.
    ("aula-concluida", "aula.concluida.v1", "ator", 25, 0, 5, 0),
]

# (slug, nome, descricao, cadencia, categoria, meta, pontos, cristais)
# Nenhuma missão exige presença: não há missão de "entrar no site".
MISSOES = [
    (
        "primeiro-passo-do-dia",
        "Comece alguma coisa",
        "Abra o Studio e dê o primeiro passo de uma peça nova. Começar já conta.",
        "diaria",
        "criar",
        1,
        15,
        0,
    ),
    (
        "polir-uma-obra",
        "Melhore o que já existe",
        "Volte numa peça sua e deixe um detalhe melhor do que estava.",
        "diaria",
        "polir",
        1,
        15,
        0,
    ),
    (
        "responder-um-colega",
        "Ajude alguém a destravar",
        "Responda a dúvida de um colega com o que você já sabe.",
        "diaria",
        "ajudar",
        1,
        20,
        0,
    ),
    (
        "encomenda-da-semana",
        "Encomenda da Semana",
        "O desafio grande da semana, com briefing de cliente de verdade.",
        "semanal",
        "criar",
        1,
        120,
        10,
    ),
    (
        "dupla-da-semana",
        "Dupla da semana",
        "Duas pessoas, uma peça: combinem e entreguem juntos.",
        "dupla",
        "ajudar",
        2,
        60,
        5,
    ),
]

# (slug, nome, descricao, classe, familia, criterio,
#  envolve_dinheiro, exige_validador_da_equipe, secreta, pontos, cristais)
CONQUISTAS = [
    (
        "fundador",
        "Fundador",
        "Estava aqui no começo de tudo. Esta não volta.",
        "medalha",
        "epoca",
        {"tipo": "manual"},
        False,
        False,
        False,
        0,
        25,
    ),
    (
        "primeira-obra",
        "Primeira obra",
        "A primeira peça terminada. Todo mundo tem uma, e ninguém esquece.",
        "medalha",
        "oficio",
        {"tipo": "primeira_vez", "assunto": "obra"},
        False,
        False,
        False,
        50,
        5,
    ),
    (
        "dez-forjas",
        "Dez forjas",
        "Dez peças seladas com o medidor de tentativas. Insistência tem nome.",
        "medalha",
        "oficio",
        {"tipo": "forjas_seladas", "alvo": 10},
        False,
        False,
        False,
        80,
        10,
    ),
    (
        "mao-amiga",
        "Mão amiga",
        "Cinco respostas suas destravaram alguém. Ensinar é a maior prova.",
        "medalha",
        "comunidade",
        {"tipo": "respostas_aceitas", "alvo": 5},
        False,
        False,
        False,
        100,
        15,
    ),
    # OS MARCOS: a espinha. Todos com pontos=0, e o banco recusa o contrário.
    (
        "portfolio-publicado",
        "Portfólio no ar",
        "Suas obras reunidas num lugar que dá para mostrar a alguém.",
        "marco",
        "carreira",
        {"tipo": "manual"},
        False,
        False,
        False,
        0,
        0,
    ),
    (
        "primeiro-cliente",
        "Primeiro cliente",
        "Alguém confiou em você para fazer uma peça, e virou o seu primeiro cliente.",
        "marco",
        "carreira",
        {"tipo": "manual"},
        True,
        True,
        False,
        0,
        0,
    ),
    (
        "primeiros-dolares",
        "Primeiros dólares",
        "O primeiro dinheiro que o seu trabalho trouxe. A escola confere junto.",
        "marco",
        "carreira",
        {"tipo": "manual"},
        True,
        True,
        False,
        0,
        0,
    ),
]

# (slug, tier, ordem, limiar_de_promocao, tamanho_do_grupo)
# Bronze, Prata, Ouro e Platina. DIAMANTE ESTÁ PROIBIDO (decisão 1 da Sessão A):
# ele colidiria com os Cristais, que são a moeda. O banco recusa um quinto tier.
# O limiar é ABSOLUTO, e não posição: ninguém desce por ter tido uma semana ruim.
LIGAS = [
    ("bronze", "bronze", 1, 300, 15),
    ("prata", "prata", 2, 500, 15),
    ("ouro", "ouro", 3, 800, 15),
    ("platina", "platina", 4, 1200, 15),
]

# (slug, nome, descricao, tipo, custo_em_cristais, sazonal)
# Quatro tipos, todos visuais. O sazonal volta todo ano e NÃO tem cronômetro.
COSMETICOS = [
    (
        "moldura-madeira",
        "Moldura de madeira",
        "Uma moldura simples de oficina para o seu retrato.",
        "moldura",
        50,
        False,
    ),
    (
        "titulo-forjador",
        "Forjador",
        "Um título para quem não desiste na décima tentativa.",
        "titulo",
        80,
        False,
    ),
    (
        "tema-noturno",
        "Ateliê à noite",
        "O tema escuro da sua página de conquistas.",
        "tema",
        120,
        False,
    ),
    (
        "bancada-de-madeira",
        "Bancada de madeira",
        "Uma bancada para o canto do seu Estúdio.",
        "decoracao_estudio",
        200,
        False,
    ),
    (
        "festa-junina",
        "Bandeirinhas",
        "Enfeite de junho. Some depois, e volta no ano que vem.",
        "decoracao_estudio",
        150,
        True,
    ),
]


class Command(BaseCommand):
    help = (
        "Semeia a economia da gamificacao (niveis, regras, missoes, conquistas, "
        "ligas e cosmeticos). Idempotente. TUDO nasce desligado."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--site",
            required=True,
            help="o site_id que recebe as linhas (Lei 9: uma fabrica, N lojas)",
        )

    def handle(self, *args, **opcoes):
        site = opcoes["site"]
        placar = {}

        placar["niveis"] = self._semear(
            NivelDefinicao,
            [
                (
                    {"site_id": site, "nivel": nivel},
                    {
                        "xp_necessario": xp,
                        "titulo": titulo,
                        "titulo_feminino": feminino,
                        "ativa": False,
                        "versao": 1,
                    },
                    f"nivel {nivel}",
                )
                for nivel, xp, titulo, feminino in NIVEIS
            ],
        )

        placar["regras"] = self._semear(
            RegraDePontuacao,
            [
                (
                    {"site_id": site, "slug": slug},
                    {
                        "evento_gatilho": evento,
                        "beneficiario": quem,
                        "pontos": pontos,
                        "cristais": cristais,
                        "acoes_cheias_por_dia": cheias,
                        "quarentena_horas": quarentena,
                        "ativa": False,
                        "versao": 1,
                    },
                    slug,
                )
                for slug, evento, quem, pontos, cristais, cheias, quarentena in REGRAS
            ],
        )

        placar["missoes"] = self._semear(
            MissaoDefinicao,
            [
                (
                    {"site_id": site, "slug": slug},
                    {
                        "nome": nome,
                        "descricao": descricao,
                        "cadencia": cadencia,
                        "categoria": categoria,
                        "meta": meta,
                        "pontos": pontos,
                        "cristais": cristais,
                        "ativa": False,
                        "versao": 1,
                    },
                    slug,
                )
                for (
                    slug,
                    nome,
                    descricao,
                    cadencia,
                    categoria,
                    meta,
                    pontos,
                    cristais,
                ) in MISSOES
            ],
        )

        placar["conquistas"] = self._semear(
            ConquistaDefinicao,
            [
                (
                    {"site_id": site, "slug": slug},
                    {
                        "nome": nome,
                        "descricao": descricao,
                        "classe": classe,
                        "familia": familia,
                        "criterio": criterio,
                        "envolve_dinheiro": dinheiro,
                        "exige_validador_da_equipe": da_equipe,
                        "secreta": secreta,
                        "pontos": pontos,
                        "cristais": cristais,
                        "ativa": False,
                        "versao": 1,
                    },
                    slug,
                )
                for (
                    slug,
                    nome,
                    descricao,
                    classe,
                    familia,
                    criterio,
                    dinheiro,
                    da_equipe,
                    secreta,
                    pontos,
                    cristais,
                ) in CONQUISTAS
            ],
        )

        placar["ligas"] = self._semear(
            LigaDefinicao,
            [
                (
                    {"site_id": site, "slug": slug},
                    {
                        "tier": tier,
                        "ordem": ordem,
                        "limiar_de_promocao": limiar,
                        "tamanho_do_grupo": tamanho,
                        "ativa": False,
                        "versao": 1,
                    },
                    slug,
                )
                for slug, tier, ordem, limiar, tamanho in LIGAS
            ],
        )

        placar["cosmeticos"] = self._semear(
            ItemCosmetico,
            [
                (
                    {"site_id": site, "slug": slug},
                    {
                        "nome": nome,
                        "descricao": descricao,
                        "tipo": tipo,
                        "custo_em_cristais": custo,
                        "sazonal": sazonal,
                        "ativa": False,
                        "versao": 1,
                    },
                    slug,
                )
                for slug, nome, descricao, tipo, custo, sazonal in COSMETICOS
            ],
        )

        for familia, (criadas, mantidas) in placar.items():
            self.stdout.write(
                f"  {familia:12s} criadas: {criadas:3d}   ja existiam: {mantidas:3d}"
            )

        ligadas = self._contar_ligadas(site)
        if ligadas:
            # Nunca deveria acontecer numa semeadura limpa. Se acontecer, foi o
            # mantenedor ligando (o que e legitimo) ou alguem ligando por codigo
            # (o que e critério de morte). Dizer em voz alta e mais barato que
            # descobrir depois.
            self.stdout.write(
                f"ATENCAO: {ligadas} linha(s) ja estao LIGADAS neste site. "
                "Semear nao liga nada; alguem ligou antes."
            )
        else:
            self.stdout.write("TUDO DESLIGADO: nenhuma linha ativa neste site.")

        # A linha que o pipeline procura. Só existe aqui, no fim do caminho
        # feliz, e nunca no eco do script (`armadilhas/114`).
        self.stdout.write("SEMEADURA DA ECONOMIA OK")

    def _semear(self, modelo, linhas):
        criadas = mantidas = 0
        for chave, valores, _rotulo in linhas:
            _, nasceu = modelo.objects.get_or_create(**chave, defaults=valores)
            if nasceu:
                criadas += 1
            else:
                mantidas += 1
        return criadas, mantidas

    def _contar_ligadas(self, site):
        return sum(
            modelo.objects.filter(site_id=site, ativa=True).count()
            for modelo in (
                NivelDefinicao,
                RegraDePontuacao,
                MissaoDefinicao,
                ConquistaDefinicao,
                LigaDefinicao,
                ItemCosmetico,
            )
        )
