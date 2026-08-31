"""O modelo de dados da gamificação — e, nele, as três promessas que viram banco.

Lei: `docs/decisoes/DECISAO-gamificacao.md`. Engenharia: o §3 de
`docs/decisoes/PLANO-CELULA-GAMIFICACAO.md`. Rastreabilidade das decisões de
produto: `docs/consultorias/gamificacao/VEREDITO.md`.

A HIERARQUIA QUE DECIDE TODO CONFLITO DE DESENHO
------------------------------------------------
**Realidade > Criação > Maestria > Comunidade > XP.** A espinha é a trilha de
marcos reais; o pacote estilo Duolingo é o andaime. Este arquivo é o andaime, e
sabe disso: `ConquistaDefinicao` recusa, no BANCO, que um marco real pague XP.

OS TRÊS INVARIANTES DA ECONOMIA MORAM AQUI, NÃO EM PROSA
--------------------------------------------------------
A lei §3 promete três coisas ao aluno e à família dele. Promessa em documento
apodrece (`docs/decisoes/RETROSPECTIVA-FASE-D.md` §2); por isso cada uma tem um
mecanismo neste arquivo, e um teste que reprova a publicação:

1. **Nada por dinheiro real.** Nenhum campo desta célula guarda dinheiro, e a
   forma como um Cristal NASCE é vocabulário fechado, conferido pelo
   PostgreSQL: `origem_de_cristal_no_vocabulario_fechado` +
   `cristal_positivo_nunca_vem_de_compra`. Guarda:
   `tests/test_inv_economia_nada_por_dinheiro_real.py` [INV-GAM1].
2. **Cosmético é só estética.** `ItemCosmetico` tem quatro tipos, todos
   visuais, e o banco recusa um quinto (`tipo_de_cosmetico_e_so_estetica`).
   Nenhuma tabela que calcula XP, nível ou liga conhece um cosmético. Guarda:
   `tests/test_inv_economia_cosmetico_e_so_estetica.py` [INV-GAM2].
3. **Aula nunca fica atrás de jogo.** Esta célula não sabe o que é uma aula:
   não há campo, modelo nem chave estrangeira que nomeie conteúdo educacional.
   Quem não consegue nomear uma aula não consegue trancá-la. Guarda:
   `tests/test_inv_economia_aula_nunca_atras_de_jogo.py` [INV-GAM3].

`site_id` EM TODA ENTIDADE, COM UMA EXCEÇÃO DECLARADA
-----------------------------------------------------
Lei 9 / [INV-P11]: o `site_id` acompanha toda entidade pública. Aqui ele está em
todas, **menos em `Pessoa`** — e a exceção é do desenho, não do esquecimento: o
espelho copia a identidade da PLATAFORMA, que é uma só por pessoa em todos os
sites (quem a emite é a célula `identidade`). A fronteira de site desta célula
mora no `PerfilJogador`, com `Unique(pessoa, site_id)` — exatamente como o §3 do
plano a desenhou. Quem faz valer, e quem mantém a exceção visível para sempre:
`tests/test_modelo_de_dados.py::test_site_id_em_toda_entidade`.

O QUE ESTE PR **NÃO** FAZ, DE PROPÓSITO
---------------------------------------
Ele é o PR 3 da escada do §6: tabelas, migração e semeadura. Não há motor de
XP, não há consumidor de evento, não há tela e não há porta de máquina. Toda
linha de economia nasce `ativa=False` — a economia é DADO (UPDATE + versão,
anunciado, nunca retroativo), e ligar uma regra é decisão do mantenedor, não
efeito colateral de um deploy.
"""

import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

# ---------------------------------------------------------------------------
# O DIA É A UNIDADE DA MECÂNICA, E ELE É O DIA DE SÃO PAULO
# ---------------------------------------------------------------------------
# `dia_local` no ledger, o dia ativo da Sequência, a janela das missões e o teto
# diário se decidem por `TIME_ZONE = "America/Sao_Paulo"` (`config/settings.py`).
# Esta função é o único lugar da célula que materializa "que dia foi isto": duas
# expressões da mesma conta divergem no primeiro dia em que alguém mexer numa
# delas, e aqui divergir significa quebrar a Sequência de quem não faltou
# (`armadilhas/099`).


def dia_local_de(momento) -> "timezone.datetime.date":
    """O DIA de São Paulo de um instante aware. Nunca `date()` cru do UTC."""
    return timezone.localdate(momento)


def id_do_site() -> models.CharField:
    """O campo de fronteira de site, um só, para não haver dois formatos.

    Texto opaco de 64, como TODO id que atravessa fronteira nesta plataforma —
    nunca `UUIDField`. Um `UUIDField` aqui criaria uma fronteira que não casa
    com a casa e obrigaria conversão silenciosa em cada consumidor
    (`services/sugestoes/apps/sugestoes/models.py`, correção 1).
    """
    return models.CharField(max_length=64, db_index=True)


class CriterioDesconhecido(ValidationError):
    """Critério de conquista fora do vocabulário fechado.

    Existe para que o critério de morte nº 1 da lei (§10: *"a célula virar motor
    de regras genérico ou ganhar uma DSL"*) tenha um lugar concreto onde
    acontece. O dia em que alguém precisar de um critério novo, ele acrescenta
    uma palavra a `CRITERIOS_ACEITOS` — e esse diff é visível. O dia em que
    alguém precisar de uma EXPRESSÃO, o pedido bate aqui, e a resposta é parar e
    reabrir a decisão com o mantenedor.
    """


# O vocabulário FECHADO dos critérios de conquista. Não é DSL, e a diferença é
# exatamente esta lista: um conjunto de palavras que um humano lê inteiro em
# cinco segundos, contra uma linguagem que ninguém audita.
CRITERIOS_ACEITOS = frozenset(
    {
        "manual",  # um adulto concede; não há conta automática
        "xp_acumulado",
        "nivel_alcancado",
        "semanas_de_sequencia",
        "missoes_cumpridas",
        "conquistas_da_familia",
        "forjas_seladas",
        "respostas_aceitas",
        "primeira_vez",  # medalha de estreia (primeiro quiz, primeira obra)
    }
)


# ---------------------------------------------------------------------------
# 1. QUEM É A PESSOA — o espelho, nunca a fonte da verdade
# ---------------------------------------------------------------------------


class Pessoa(models.Model):
    """O espelho local de quem joga. Molde: `services/forum` e `services/sugestoes`.

    Quem sabe quem é a pessoa é a célula `identidade`; quem sabe se ela é aluna é
    a célula `alunos`. Esta tabela guarda o mínimo para a gamificação conseguir
    dizer "de quem é este XP" sem uma chamada de rede por linha exibida.

    Guardar mais que isto violaria a Lei 2: dado de outra célula copiado sem
    necessidade vira uma segunda verdade que ninguém mantém. Em particular, aqui
    **não** entram idade, data de nascimento nem nome real: a escola é 18+ (lei
    §9, emendada em 30/08/2026) e nenhuma regra desta célula depende de saber
    quantos anos alguém tem.
    """

    # O id OPACO da plataforma, como a `identidade` o devolve. É a chave de
    # ligação com o resto do site — nunca o e-mail, que muda de dono.
    id_da_plataforma = models.CharField(max_length=64, primary_key=True)
    # Guardado porque `quiz.completado.v1` chega por E-MAIL: é por ele que o
    # motor de XP resolve o evento contra o espelho, ou pergunta à `identidade`
    # (`findPersonByEmail`, já congelada).
    email = models.EmailField(unique=True)
    nome_exibido = models.CharField(max_length=120, blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)
    vista_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "pessoas"

    def __str__(self) -> str:
        return self.nome_exibido or self.email


class PerfilJogador(models.Model):
    """O estado do aluno num site: XP, nível, saldo e o que falta comemorar.

    **Os três números são DESNORMALIZADOS do ledger**, e isso é decisão, não
    atalho: a Base em `/conquistas` mostra nível e barra em toda visita, e somar
    o ledger inteiro a cada carregamento é a conta que fica lenta exatamente
    quando a escola cresce. A fonte da verdade continua sendo `LancamentoDeXP` e
    `MovimentoDeCristais`; o comando `reconciliar_perfis` (PR 8 da escada) é o
    que prova, de fora, que a cópia não mentiu.

    **Não há campo de MODO por idade, e a ausência é decisão registrada.** Este
    modelo nasceu em 30/08/2026 com um `modo` de duas faixas (júnior abaixo de
    13 anos, teen acima), porque a lei da célula previa Modo Júnior como trava
    de sistema. No mesmo dia o mantenedor declarou que a escola é 18+ e o §9 da
    `DECISAO-gamificacao.md` foi emendado: *"Não há Modo Júnior, não há faixa
    etária de 13 anos (…) e nenhum desenho novo deve assumir criança no
    sistema."* O campo saiu na migração `0002`, com o banco ainda vazio.

    Se a escola um dia admitir menores, o caminho é o que a lei escreve: a trava
    volta ao §9 ANTES de a funcionalidade que a exige ser ligada — e este
    docstring é onde o próximo a ler descobre que ela já existiu.
    """

    pessoa = models.ForeignKey(Pessoa, related_name="perfis", on_delete=models.PROTECT)
    site_id = id_do_site()

    xp_total = models.PositiveIntegerField(default=0)
    nivel = models.PositiveSmallIntegerField(default=1)
    cristais_saldo = models.PositiveIntegerField(default=0)

    modo_foco = models.BooleanField(default=False)
    # Opt-in, e o default fechado continua sendo o certo depois da emenda de
    # 30/08/2026: a razão deixou de ser trava por idade e passou a ser a que a
    # lei §9 dá para o Meu Estúdio, *"privacidade é de adulto também"*. Liga é
    # exposição entre pares; ninguém entra nela por omissão.
    participa_de_ligas = models.BooleanField(default=False)

    # A CELEBRAÇÃO VISCERAL MORA AQUI, E NÃO NA SESSÃO.
    # Quando o aluno sobe de nível ou valida um marco, a tela precisa saber
    # "esta pessoa já viu esta comemoração?". O caminho mais curto para guardar
    # isso é `request.session[...]` — que funciona em dev, passa em teste de
    # unidade e desloga a plataforma inteira em produção, sem erro em lugar
    # nenhum (`armadilhas/143`; [INV-P12]; guarda em
    # `tests/test_inv_gamificacao_nao_assina_sessao.py`).
    celebracoes_pendentes = models.JSONField(default=list, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["pessoa", "site_id"], name="um_perfil_por_pessoa_por_site"
            ),
            models.CheckConstraint(
                condition=models.Q(nivel__gte=1), name="nivel_comeca_em_um"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.pessoa_id}@{self.site_id} nv{self.nivel}"


# ---------------------------------------------------------------------------
# 2. A ECONOMIA É DADO — regras, níveis, missões, conquistas, ligas, cosméticos
# ---------------------------------------------------------------------------
# Tudo nesta seção nasce `ativa=False` e carrega `versao`. Ajustar a economia é
# UPDATE + versão, anunciado e nunca retroativo. Se um dia ajustar a economia
# exigir PR de código, isso é critério de morte (lei §10.5) — não é força de
# expressão: é para parar e reabrir a decisão com o mantenedor.


class RegraDePontuacao(models.Model):
    """O que paga XP, quanto, para quem, com que teto e com que quarentena.

    **O teto é SUAVE, nunca parede muda.** `acoes_cheias_por_dia` diz quantas
    ações do dia pagam o valor inteiro; depois disso o rendimento decresce até
    zero, e a tela DIZ isso. Uma parede silenciosa ("a partir da sexta, nada")
    ensina o aluno que o sistema é injusto, e ele não tem como saber que não é.

    **A quarentena existe por causa do XP social.** Ganho de curtir, votar ou
    responder fica `pendente` por N horas antes de virar definitivo, para que a
    moderação de um conteúdo removido consiga estornar antes de o número virar
    parte da identidade de alguém.

    A tomada de `aula.concluida.v1` prevista no plano é UMA LINHA semeada aqui.
    Note que isso é a célula LENDO um fato do curso, jamais o contrário: nada
    nesta tabela decide se alguém pode assistir a coisa alguma.
    """

    class Beneficiario(models.TextChoices):
        ATOR = "ator", "Quem fez a ação"
        AUTOR_DO_ALVO = "autor_do_alvo", "Quem escreveu o que foi votado ou aceito"

    slug = models.SlugField(max_length=60)
    site_id = id_do_site()
    # O nome do evento congelado, como ele chega: "quiz.completado.v1".
    evento_gatilho = models.CharField(max_length=100)
    beneficiario = models.CharField(
        max_length=13, choices=Beneficiario.choices, default=Beneficiario.ATOR
    )
    pontos = models.PositiveIntegerField(default=0)
    cristais = models.PositiveIntegerField(default=0)
    # 0 = sem teto. Acima de N ações no mesmo dia local, o rendimento decresce.
    acoes_cheias_por_dia = models.PositiveSmallIntegerField(default=0)
    # 0 = definitivo na hora. 24 a 72 para o XP social.
    quarentena_horas = models.PositiveSmallIntegerField(default=0)
    # UM CAMPO ESTREITO, E A ESTREITEZA É O PONTO — leia antes de "generalizar".
    #
    # O assunto `sugestao.status-alterado` é UM evento para SEIS status. Sem esta
    # coluna, a regra `sugestao-implementada` pagava 40 XP em CADA passo do funil
    # (em_analise → planejado → em_desenvolvimento → implementado = 160 por uma
    # sugestão só), porque o motor casava só pelo `evento_gatilho`. Medido em
    # 31/08/2026, antes de a regra ser ligada.
    #
    # **Vazio = qualquer status**, que é o comportamento de todas as outras
    # regras e de todos os outros assuntos. Preenchido, a regra só paga quando o
    # `data.status_novo` do evento for exatamente este texto.
    #
    # **POR QUE NÃO UM CAMPO DE CONDIÇÃO GENÉRICO** (`filtro`, `condicao`, um
    # JSON de `campo: valor`, uma expressão): porque isso é o CRITÉRIO DE MORTE
    # Nº 1 da lei — *"a célula virar motor de regras genérico ou ganhar uma
    # DSL"*. Um campo com nome concreto, que compara UM campo conhecido de UM
    # assunto conhecido, não é uma linguagem: é uma regra a mais, escrita por
    # extenso. No dia em que um segundo assunto precisar de qualificador, a
    # resposta certa continua sendo outra coluna com nome próprio — e se um dia
    # forem muitas, isso é sinal de parar e reabrir a decisão, não de inventar
    # uma gramática. Guarda: `tests/test_inv_economia_nao_vira_motor_generico.py`.
    quando_status_novo = models.CharField(max_length=30, blank=True, default="")

    ativa = models.BooleanField(default=False)
    versao = models.PositiveIntegerField(default=1)
    # A DATA da lei §10.5: "ajustar a economia é UPDATE + versão, ANUNCIADO e
    # NUNCA RETROATIVO". Até 31/08/2026 a promessa do "nunca retroativo" não
    # tinha mecanismo nenhum — o motor olhava só `ativa`, e um evento antigo
    # reentregue depois de alguém ligar a regra pagaria como se a regra sempre
    # tivesse valido. É a "garantia sem mecanismo" da RETROSPECTIVA-FASE-D, e
    # aqui ela vira coluna: o motor recusa fato ANTERIOR a esta data.
    #
    # `null` = regra que nunca foi ligada. Não é "vale desde sempre": regra
    # desligada não paga de qualquer jeito, e o dia em que ela for ligada é o
    # dia em que esta coluna nasce. O default NÃO é `auto_now_add` de
    # propósito — a data que importa é a de LIGAR, não a de cadastrar.
    vigente_desde = models.DateTimeField(null=True, blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["site_id", "slug"]
        constraints = [
            models.UniqueConstraint(
                fields=["site_id", "slug"], name="uma_regra_por_slug_por_site"
            ),
            # Ligada sem data seria justamente o buraco que a coluna veio
            # fechar: o motor não teria com o que comparar o fato e voltaria a
            # pagar retroativo, em silêncio. O banco recusa — invariante por
            # construção, não por lembrança de quem escreve o próximo `UPDATE`.
            models.CheckConstraint(
                condition=models.Q(ativa=False) | models.Q(vigente_desde__isnull=False),
                name="regra_ligada_tem_data_de_vigencia",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.slug} v{self.versao}"


class NivelDefinicao(models.Model):
    """Um degrau da escada: quanto XP ele pede e que TÍTULO ele dá. Só isso.

    **Este modelo é o corpo do terceiro invariante.** A tentação universal de
    sistema de níveis é "no nível 5 você desbloqueia o módulo avançado" — e é
    exatamente o que a lei §3.3 proíbe. Aqui um nível não tem onde guardar o que
    ele libera: os campos são o número, o XP e o título, e o guarda
    `tests/test_inv_economia_aula_nunca_atras_de_jogo.py` afirma que essa forma é
    FECHADA. Acrescentar `aulas_liberadas` deixa o teste vermelho na asserção.

    **Os títulos não falam a língua de credencial** (VEREDITO): a base é
    Aprendiz → Oficial → Mestre de Ateliê. Um título de nível que diga
    "certificado" ou "profissional" promete à família uma coisa que a escola não
    está entregando ali.
    """

    nivel = models.PositiveSmallIntegerField()
    site_id = id_do_site()
    xp_necessario = models.PositiveIntegerField()
    titulo = models.CharField(max_length=60)
    # Opcional, e opcional de propósito: quem não quiser flexionar não flexiona.
    titulo_feminino = models.CharField(max_length=60, blank=True, default="")
    ativa = models.BooleanField(default=False)
    versao = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["site_id", "nivel"]
        constraints = [
            models.UniqueConstraint(
                fields=["site_id", "nivel"], name="um_nivel_por_numero_por_site"
            ),
            models.CheckConstraint(
                condition=models.Q(nivel__gte=1), name="nivel_definido_comeca_em_um"
            ),
        ]

    def __str__(self) -> str:
        return f"nv{self.nivel} {self.titulo}"


class MissaoDefinicao(models.Model):
    """Uma missão diária, semanal ou de dupla. A semanal grande é a Encomenda.

    **Nenhuma missão exige presença diária**, e isso não é um campo que se
    desliga: não existe missão de "entrar no site". Login vale 0 XP, sempre
    (decisão fechada 7 da Sessão A), e uma missão de presença seria o mesmo
    incentivo entrando pela porta dos fundos.

    A `categoria` existe para forçar DIVERSIDADE: o motor (PR 11) sorteia
    missões de categorias diferentes, para o dia não virar três variações da
    mesma tarefa.
    """

    class Cadencia(models.TextChoices):
        DIARIA = "diaria", "Diária"
        SEMANAL = "semanal", "Semanal"
        DUPLA = "dupla", "De dupla"

    class Categoria(models.TextChoices):
        CRIAR = "criar", "Criar alguma coisa"
        APRENDER = "aprender", "Aprender alguma coisa"
        AJUDAR = "ajudar", "Ajudar alguém"
        POLIR = "polir", "Melhorar uma obra que já existe"
        MOSTRAR = "mostrar", "Mostrar o trabalho para alguém"

    slug = models.SlugField(max_length=60)
    site_id = id_do_site()
    nome = models.CharField(max_length=120)
    descricao = models.TextField(blank=True)
    cadencia = models.CharField(max_length=7, choices=Cadencia.choices)
    categoria = models.CharField(max_length=8, choices=Categoria.choices)
    meta = models.PositiveIntegerField(default=1)
    pontos = models.PositiveIntegerField(default=0)
    cristais = models.PositiveIntegerField(default=0)
    ativa = models.BooleanField(default=False)
    versao = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["site_id", "slug"]
        constraints = [
            models.UniqueConstraint(
                fields=["site_id", "slug"], name="uma_missao_por_slug_por_site"
            ),
            models.CheckConstraint(
                condition=models.Q(meta__gte=1), name="missao_pede_ao_menos_um_passo"
            ),
        ]

    def __str__(self) -> str:
        return self.nome


class ConquistaDefinicao(models.Model):
    """Medalha (andaime) ou MARCO real (espinha). O banco sabe a diferença.

    **`marco_real_rende_zero_xp` é a hierarquia da lei virando restrição.** A
    decisão 7 da Sessão A é literal: marco real vale ZERO XP. O motivo é o
    coração do produto — se conseguir o primeiro cliente pagasse 500 XP, o marco
    viraria mais um item do andaime, e o aluno aprenderia a perseguir o número
    em vez da coisa. O banco recusa a linha; não é convenção.

    **`marco_de_dinheiro_so_a_equipe_valida`** é o §9 da lei virando restrição:
    marco que envolve dinheiro é SEMPRE validado por alguém da equipe, com a
    evidência em camada privada. Trava que uma tela de administração futura não
    consegue afrouxar por engano.

    **Ela já teve uma faixa etária dentro, e perdê-la foi decisão.** Até
    30/08/2026 a restrição se chamava `marco_de_dinheiro_e_13mais_e_so_adulto_valida`
    e exigia também `faixa_etaria="13mais"`. O mantenedor declarou que a escola é
    18+ e o §9 foi emendado; a metade etária virou tautologia (numa escola só de
    adultos, "13 anos ou mais" não separa ninguém de ninguém) e saiu na migração
    `0002`. A metade que ficou mudou de RAZÃO, não de força: era proteção de
    menor, agora é qualidade e confiança no que a escola afirma.

    É por isso que o campo se chama `exige_validador_da_equipe` e não
    `..._adulto`: aqui todo mundo é adulto, inclusive o aluno. O que a trava
    separa é AUTORIDADE — `validador_papel` aceita `par`, e um par não fecha
    marco de dinheiro.
    """

    class Classe(models.TextChoices):
        MEDALHA = "medalha", "Medalha (andaime)"
        MARCO = "marco", "Marco real (espinha)"

    class Familia(models.TextChoices):
        OFICIO = "oficio", "Ofício"
        COMUNIDADE = "comunidade", "Comunidade"
        EPOCA = "epoca", "Época"
        SECRETA = "secreta", "Secreta"
        CARREIRA = "carreira", "Carreira"
        ESPELHO = "espelho", "Espelho (a própria evolução)"

    slug = models.SlugField(max_length=60)
    site_id = id_do_site()
    nome = models.CharField(max_length=120)
    descricao = models.TextField(blank=True)
    classe = models.CharField(max_length=7, choices=Classe.choices)
    familia = models.CharField(max_length=10, choices=Familia.choices)
    # Vocabulário FECHADO (`CRITERIOS_ACEITOS`), conferido no `save()`. Não é
    # DSL, e a diferença é o critério de morte nº 1 da lei.
    criterio = models.JSONField(default=dict, blank=True)
    envolve_dinheiro = models.BooleanField(default=False)
    exige_validador_da_equipe = models.BooleanField(default=False)
    secreta = models.BooleanField(default=False)
    pontos = models.PositiveIntegerField(default=0)
    cristais = models.PositiveIntegerField(default=0)
    ativa = models.BooleanField(default=False)
    versao = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["site_id", "slug"]
        constraints = [
            models.UniqueConstraint(
                fields=["site_id", "slug"], name="uma_conquista_por_slug_por_site"
            ),
            models.CheckConstraint(
                condition=~models.Q(classe="marco") | models.Q(pontos=0),
                name="marco_real_rende_zero_xp",
            ),
            models.CheckConstraint(
                condition=~models.Q(envolve_dinheiro=True)
                | models.Q(exige_validador_da_equipe=True),
                name="marco_de_dinheiro_so_a_equipe_valida",
            ),
        ]

    def save(self, *args, **kwargs):
        """A porta do vocabulário fechado — o degrau que pega QUALQUER caminho.

        Mora no `save()`, e não numa view, pelo mesmo motivo do
        `Sugestao.save()` da Caixa: um `manage.py` escrito daqui a seis meses,
        por alguém que nunca ouviu falar do critério de morte, passa por aqui.
        """
        tipo = (self.criterio or {}).get("tipo", "manual")
        if tipo not in CRITERIOS_ACEITOS:
            raise CriterioDesconhecido(
                f"critério {tipo!r} fora do vocabulário fechado. "
                "Critério novo é UMA palavra em CRITERIOS_ACEITOS, e o diff "
                "aparece. Se o que falta é uma EXPRESSÃO, pare: virar motor de "
                "regras genérico é critério de morte desta célula (lei §10)."
            )
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.nome


class LigaDefinicao(models.Model):
    """Bronze, Prata, Ouro e Platina. **Diamante está PROIBIDO.**

    Decisão 1 do mantenedor na Sessão A, e o motivo é de produto: Diamante
    colide com os Cristais, que são a MOEDA. Um aluno na "liga Diamante" com
    "Cristais" no bolso confunde as duas coisas, e a confusão empurra na direção
    exata que a lei proíbe (achar que se compra posição).

    A restrição `tier_de_liga_e_um_dos_quatro` põe a decisão no PostgreSQL:
    inserir `diamante` é recusado, venha de onde vier.

    **SEM REBAIXAMENTO, e por isso não existe campo para ele.** O limiar de
    promoção é ABSOLUTO (não é "os 3 primeiros sobem"): o aluno compete com um
    número, não com os colegas — e ninguém desce por ter tido uma semana ruim.
    """

    class Tier(models.TextChoices):
        BRONZE = "bronze", "Bronze"
        PRATA = "prata", "Prata"
        OURO = "ouro", "Ouro"
        PLATINA = "platina", "Platina"

    slug = models.SlugField(max_length=60)
    site_id = id_do_site()
    # O `max_length` é FOLGADO de propósito, e a folga é a decisão. Rente ao
    # maior valor do vocabulário, quem recusaria um valor inventado seria o
    # TAMANHO da coluna, com um `DataError` genérico — e a proteção evaporaria
    # no dia em que alguém alargasse a coluna por outro motivo, sem tocar em
    # restrição nenhuma. Com folga, quem recusa é a restrição NOMEADA lá
    # embaixo, e a mensagem do banco diz qual lei foi violada. Medido nesta
    # própria entrega: `diamante` (8 letras) morria num `max_length=7` antes de
    # a restrição que o proíbe chegar a rodar.
    tier = models.CharField(max_length=16, choices=Tier.choices)
    ordem = models.PositiveSmallIntegerField(default=0)
    # ABSOLUTO: "faça X pontos na semana e suba". Nunca "os N primeiros".
    limiar_de_promocao = models.PositiveIntegerField(default=0)
    tamanho_do_grupo = models.PositiveSmallIntegerField(default=15)
    ativa = models.BooleanField(default=False)
    versao = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["site_id", "ordem"]
        constraints = [
            models.UniqueConstraint(
                fields=["site_id", "slug"], name="uma_liga_por_slug_por_site"
            ),
            models.CheckConstraint(
                condition=models.Q(tier__in=["bronze", "prata", "ouro", "platina"]),
                name="tier_de_liga_e_um_dos_quatro",
            ),
        ]

    def __str__(self) -> str:
        return self.get_tier_display()


class ItemCosmetico(models.Model):
    """Um item de loja. Ele muda a APARÊNCIA, e não muda mais nada.

    **Este modelo é o corpo do segundo invariante.** Os quatro tipos são
    visuais, o banco recusa um quinto (`tipo_de_cosmetico_e_so_estetica`), e o
    guarda `tests/test_inv_economia_cosmetico_e_so_estetica.py` afirma que a FORMA
    do modelo é fechada: não há onde guardar um multiplicador de XP, um peso de
    ranking ou um destaque de visibilidade. Acrescentar
    `multiplicador_de_xp` deixa o teste vermelho na asserção.

    **O ESCUDO NÃO É ITEM DE LOJA** (decisão fechada 7 da Sessão A). Ele é 1 por
    mês, automático e grátis, e mora em `Sequencia.escudos`. Vender proteção de
    sequência é a mecânica que transforma um aluno em cliente ansioso, e ela
    está vetada por escrito.

    **`custo_em_cristais` não tem irmão em dinheiro**, e o guarda
    `tests/test_inv_economia_nada_por_dinheiro_real.py` afirma que nenhum campo
    desta célula nomeia dinheiro real. O sazonal volta todo ano e **não tem
    cronômetro**: item-relâmpago com contagem regressiva é o padrão de urgência
    vetado pelo ECA Digital.
    """

    class Tipo(models.TextChoices):
        TITULO = "titulo", "Título exibido ao lado do nome"
        MOLDURA = "moldura", "Moldura do retrato"
        TEMA = "tema", "Tema visual da página de conquistas"
        DECORACAO_ESTUDIO = "decoracao_estudio", "Decoração do Meu Estúdio"

    slug = models.SlugField(max_length=60)
    site_id = id_do_site()
    nome = models.CharField(max_length=120)
    descricao = models.TextField(blank=True)
    # O `max_length` é FOLGADO de propósito, e a folga é a decisão. Rente ao
    # maior valor do vocabulário, quem recusaria um valor inventado seria o
    # TAMANHO da coluna, com um `DataError` genérico — e a proteção evaporaria
    # no dia em que alguém alargasse a coluna por outro motivo, sem tocar em
    # restrição nenhuma. Com folga, quem recusa é a restrição NOMEADA lá
    # embaixo, e a mensagem do banco diz qual lei foi violada. Medido nesta
    # própria entrega: `diamante` (8 letras) morria num `max_length=7` antes de
    # a restrição que o proíbe chegar a rodar.
    tipo = models.CharField(max_length=32, choices=Tipo.choices)
    custo_em_cristais = models.PositiveIntegerField(default=0)
    sazonal = models.BooleanField(default=False)
    ativa = models.BooleanField(default=False)
    versao = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["site_id", "slug"]
        constraints = [
            models.UniqueConstraint(
                fields=["site_id", "slug"], name="um_cosmetico_por_slug_por_site"
            ),
            models.CheckConstraint(
                condition=models.Q(
                    tipo__in=["titulo", "moldura", "tema", "decoracao_estudio"]
                ),
                name="tipo_de_cosmetico_e_so_estetica",
            ),
        ]

    def __str__(self) -> str:
        return self.nome


# ---------------------------------------------------------------------------
# 3. OS LEDGERS — a fonte da verdade de XP e de Cristais
# ---------------------------------------------------------------------------


class LancamentoDeXP(models.Model):
    """O livro-razão do XP. Idempotente POR CONSTRUÇÃO, não por cuidado.

    `Unique(origem_event_id, regra_slug, pessoa)`: um evento reentregue não paga
    duas vezes porque o PostgreSQL não deixa, não porque alguém lembrou de
    conferir. A chave tem as três colunas porque UM evento pode legitimamente
    creditar duas pessoas por regras distintas (quem votou e quem escreveu).

    `dia_local` é MATERIALIZADO, e é a coluna de que sai "o aluno esteve ativo
    hoje". Derivá-la na consulta a partir de `occurred_at` daria respostas
    diferentes conforme o fuso de quem pergunta, e a Sequência quebraria para
    quem estuda tarde da noite (`armadilhas/099`).

    `pontos` é assinado: negativo é ESTORNO. Estornar é acrescentar linha, nunca
    apagar — o que aconteceu continua legível, que é o que permite explicar a um
    aluno por que o número dele mudou.
    """

    class Status(models.TextChoices):
        PENDENTE = "pendente", "Em quarentena"
        DEFINITIVO = "definitivo", "Definitivo"
        ESTORNADO = "estornado", "Estornado"

    pessoa = models.ForeignKey(
        Pessoa, related_name="lancamentos", on_delete=models.PROTECT
    )
    site_id = id_do_site()
    pontos = models.IntegerField()
    # Opaco: o id do evento que originou o crédito, como ele veio no envelope.
    origem_event_id = models.CharField(max_length=64)
    regra_slug = models.SlugField(max_length=60)
    # A VERSÃO da regra no instante do crédito. Sem ela, mudar a economia
    # reescreveria o passado — e mudança retroativa é o que a lei proíbe.
    regra_versao = models.PositiveIntegerField(default=1)
    occurred_at = models.DateTimeField()
    dia_local = models.DateField(db_index=True)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.DEFINITIVO
    )
    liberado_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["pessoa", "site_id", "dia_local"]),
            models.Index(fields=["status", "liberado_em"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["origem_event_id", "regra_slug", "pessoa"],
                name="um_lancamento_por_evento_por_regra_por_pessoa",
            ),
            # Quarentena sem data de liberação é quarentena eterna: o lançamento
            # ficaria `pendente` para sempre e o aluno nunca veria o ponto.
            models.CheckConstraint(
                condition=~models.Q(status="pendente")
                | models.Q(liberado_em__isnull=False),
                name="quarentena_tem_data_para_acabar",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.pontos:+d} {self.regra_slug} {self.dia_local}"


class MovimentoDeCristais(models.Model):
    """O livro-razão da MOEDA. **Cristais são earn-only por construção.**

    Este modelo é o corpo do primeiro invariante, e as restrições abaixo são a
    lei §3.1 escrita em PostgreSQL:

    - `origem_de_cristal_no_vocabulario_fechado` — a lista de jeitos de um
      Cristal nascer é fechada e mora no BANCO. Nem um `INSERT` à mão no `psql`
      numa madrugada de incidente consegue inventar `compra_com_dinheiro`.
    - `cristal_positivo_nunca_vem_de_compra` — todo Cristal que ENTRA veio de
      esforço (conquista, missão, sequência, ajuda validada) ou de uma correção
      auditável de um adulto da equipe.
    - `cristal_negativo_so_com_referencia_de_compra` — Cristal só SAI comprando
      um cosmético na loja, e a referência da compra fica gravada. É a frase do
      §3 do plano, literal.
    - `Unique(pessoa, site_id, referencia)` — a idempotência da moeda. Um evento
      reentregue não paga duas vezes.

    **Cristais são intransferíveis, e a garantia é a ausência de caminho:** não
    existe campo de destinatário, não existe transferência, e gorjeta entre
    alunos está vetada por escrito (lei §8). A intenção de agradecer sobrevive
    no botão Parabéns, que não move moeda nenhuma.

    O QUE ESTA TABELA AINDA NÃO SABE FAZER, e é de propósito: **estorno de
    Cristal por fraude**. O painel do professor (PR 13 da escada) vai precisar
    zerar ganho de quem burlou, e um débito assim não é compra na loja — ele
    não cabe nas restrições acima. Deixá-lo de fora HOJE é a escolha certa: a
    alternativa seria abrir agora uma porta de débito genérica, que é
    exatamente a porta por onde "comprar proteção" entraria depois disfarçada
    de novidade. Quando o PR 13 chegar, a decisão é dele, e ela passa por
    migração visível.
    """

    class Origem(models.TextChoices):
        CONQUISTA = "conquista", "Medalha ou marco concedido"
        MISSAO = "missao", "Missão cumprida"
        SEQUENCIA = "sequencia", "Semana de sequência fechada"
        AJUDA_VALIDADA = "ajuda_validada", "Ajuda validada pela comunidade"
        CORRECAO_DA_EQUIPE = "correcao_da_equipe", "Correção de um adulto da equipe"
        COMPRA_NA_LOJA = "compra_na_loja", "Gasto na loja de cosméticos"

    # As origens que fazem um Cristal NASCER. `COMPRA_NA_LOJA` é a única que o
    # faz sumir, e a única aceita num movimento negativo.
    ORIGENS_DE_GANHO = (
        Origem.CONQUISTA,
        Origem.MISSAO,
        Origem.SEQUENCIA,
        Origem.AJUDA_VALIDADA,
        Origem.CORRECAO_DA_EQUIPE,
    )
    ORIGEM_DE_GASTO = Origem.COMPRA_NA_LOJA
    # O prefixo que a referência de um GASTO carrega. Fica em constante para o
    # banco e o teste lerem a mesma palavra.
    PREFIXO_DE_COMPRA = "compra:"

    pessoa = models.ForeignKey(
        Pessoa, related_name="movimentos", on_delete=models.PROTECT
    )
    site_id = id_do_site()
    delta = models.IntegerField()
    # O `max_length` é FOLGADO de propósito, e a folga é a decisão. Rente ao
    # maior valor do vocabulário, quem recusaria um valor inventado seria o
    # TAMANHO da coluna, com um `DataError` genérico — e a proteção evaporaria
    # no dia em que alguém alargasse a coluna por outro motivo, sem tocar em
    # restrição nenhuma. Com folga, quem recusa é a restrição NOMEADA lá
    # embaixo, e a mensagem do banco diz qual lei foi violada. Medido nesta
    # própria entrega: `diamante` (8 letras) morria num `max_length=7` antes de
    # a restrição que o proíbe chegar a rodar.
    origem = models.CharField(max_length=32, choices=Origem.choices)
    # A chave de idempotência, opaca: "conquista:fundador", "compra:17".
    referencia = models.CharField(max_length=120)
    occurred_at = models.DateTimeField()
    dia_local = models.DateField(db_index=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["pessoa", "site_id", "referencia"],
                name="um_movimento_de_cristal_por_referencia",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    origem__in=[
                        "conquista",
                        "missao",
                        "sequencia",
                        "ajuda_validada",
                        "correcao_da_equipe",
                        "compra_na_loja",
                    ]
                ),
                name="origem_de_cristal_no_vocabulario_fechado",
            ),
            models.CheckConstraint(
                condition=~models.Q(delta__gt=0) | ~models.Q(origem="compra_na_loja"),
                name="cristal_positivo_nunca_vem_de_compra",
            ),
            models.CheckConstraint(
                condition=~models.Q(delta__lt=0)
                | models.Q(origem="compra_na_loja", referencia__startswith="compra:"),
                name="cristal_negativo_so_com_referencia_de_compra",
            ),
            models.CheckConstraint(
                condition=~models.Q(delta=0), name="movimento_de_cristal_nunca_e_zero"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.delta:+d} {self.origem} ({self.referencia})"


# ---------------------------------------------------------------------------
# 4. A SEQUÊNCIA — semanal, com marca-d'água, e que regride em vez de zerar
# ---------------------------------------------------------------------------


class Sequencia(models.Model):
    """A chama, e ela é SEMANAL de propósito.

    **Marca-d'água, nunca linha por dia.** É o achado do fórum aplicado aqui
    (`MarcaDeLeitura`): guardar uma linha por aluno por dia faz milhões de linhas
    para responder "ele veio esta semana?". Aqui o estado da semana corrente são
    quatro números nesta linha, e o passado vira `HistoricoDeSequencia`.

    **Semana falhada sem escudo REGRIDE UM DEGRAU, nunca zera.** Zerar 30
    semanas por causa de uma gripe é a mecânica que ensina a pessoa que o
    esforço dela é frágil, e é a que produz o uso compulsivo que o ECA Digital
    mira (a escola é 18+, e o vício que aquela lei descreve não pede carteira
    de identidade). Regredir dói o suficiente para importar e pouco o bastante para não
    quebrar ninguém.

    **O escudo é 1 por mês, automático e GRÁTIS** (decisão fechada 7 da Sessão
    A). Ele mora aqui, e não em `ItemCosmetico`, porque não está à venda: nem
    por dinheiro, nem por Cristais.

    **Dia ativo = lançamento DEFINITIVO de XP de aprendizado no dia local.** Não
    nasce evento de presença, e login vale 0 XP: quem não estudou não ganhou
    dia, mesmo que tenha aberto o site dez vezes.
    """

    class Ritmo(models.TextChoices):
        LEVE = "leve", "Leve (3 dias por semana)"
        NORMAL = "normal", "Normal (5 dias por semana)"
        INTENSA = "intensa", "Intensa (7 dias por semana)"

    pessoa = models.ForeignKey(
        Pessoa, related_name="sequencias", on_delete=models.PROTECT
    )
    site_id = id_do_site()
    ritmo = models.CharField(max_length=7, choices=Ritmo.choices, default=Ritmo.LEVE)
    # A meta que o ALUNO escolheu. O padrão é 3, e é padrão de gentileza, não de
    # idade: sequência que começa exigindo cinco dias é sequência que quebra na
    # primeira semana cheia de quem trabalha.
    meta_dias = models.PositiveSmallIntegerField(default=3)
    dias_ativos_na_semana = models.PositiveSmallIntegerField(default=0)
    # A segunda-feira da semana corrente, em São Paulo.
    semana_corrente = models.DateField()
    semanas_atuais = models.PositiveIntegerField(default=0)
    recorde_semanas = models.PositiveIntegerField(default=0)
    # Permanente, e a única contagem que nunca regride: é a memória do esforço.
    dias_totais = models.PositiveIntegerField(default=0)
    escudos = models.PositiveSmallIntegerField(default=0)
    modo_ferias = models.BooleanField(default=False)
    ferias_ate = models.DateField(null=True, blank=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["pessoa", "site_id"], name="uma_sequencia_por_pessoa_por_site"
            ),
            models.CheckConstraint(
                condition=models.Q(meta_dias__gte=1, meta_dias__lte=7),
                name="meta_da_semana_cabe_numa_semana",
            ),
            models.CheckConstraint(
                condition=models.Q(dias_ativos_na_semana__lte=7),
                name="a_semana_tem_sete_dias",
            ),
            models.CheckConstraint(
                condition=models.Q(recorde_semanas__gte=models.F("semanas_atuais")),
                name="o_recorde_nunca_e_menor_que_a_sequencia_atual",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.pessoa_id}: {self.semanas_atuais} semanas"


class UsoDeEscudo(models.Model):
    """A semana em que o escudo entrou no lugar da falha. Auditável.

    Existe separado da `Sequencia` para o aluno conseguir VER o que aconteceu
    ("sua semana foi protegida"), em vez de o número simplesmente não cair.
    Mecânica que age em silêncio é mecânica que ninguém confia.
    """

    pessoa = models.ForeignKey(
        Pessoa, related_name="escudos_usados", on_delete=models.PROTECT
    )
    site_id = id_do_site()
    semana = models.DateField()
    usado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-semana"]
        constraints = [
            models.UniqueConstraint(
                fields=["pessoa", "site_id", "semana"],
                name="um_escudo_por_semana_por_pessoa",
            ),
        ]


class HistoricoDeSequencia(models.Model):
    """Uma linha por semana FECHADA. O passado, para a tela poder contar a história."""

    class Desfecho(models.TextChoices):
        CUMPRIDA = "cumprida", "Meta cumprida"
        PROTEGIDA = "protegida", "Falhou, mas o escudo segurou"
        REGREDIU = "regrediu", "Falhou e regrediu um degrau"
        FERIAS = "ferias", "Modo férias"

    pessoa = models.ForeignKey(
        Pessoa, related_name="historico_de_sequencia", on_delete=models.PROTECT
    )
    site_id = id_do_site()
    semana = models.DateField()
    dias_ativos = models.PositiveSmallIntegerField(default=0)
    meta_dias = models.PositiveSmallIntegerField(default=3)
    desfecho = models.CharField(max_length=9, choices=Desfecho.choices)
    semanas_apos = models.PositiveIntegerField(default=0)
    fechada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-semana"]
        constraints = [
            models.UniqueConstraint(
                fields=["pessoa", "site_id", "semana"],
                name="uma_linha_de_historico_por_semana",
            ),
        ]


# ---------------------------------------------------------------------------
# 5. A FORJA — o medidor de esforço, que vale ZERO XP
# ---------------------------------------------------------------------------


class Forja(models.Model):
    """Quantas tentativas a obra custou. O selo diz "forjada em 14 tentativas".

    **O nome é FORJA, não Têmpera** — decisão 2 do mantenedor na Sessão A. Onde
    o plano e o VEREDITO dizem Têmpera, leia Forja.

    **Vale ZERO XP, e não tem onde guardar XP.** É o único medidor do sistema
    que celebra a INSISTÊNCIA, e pagá-lo em pontos ensinaria a inflar o número
    de tentativas. O prêmio é o selo, que vira atributo exibível da obra: a
    pessoa mostra que errou treze vezes antes de acertar, e isso é o oposto de
    esconder o esforço.

    **O medidor só cresce** (tentativa, pedido de feedback, revisão), com teto
    por desafio para o número não virar competição de quem clica mais.
    """

    pessoa = models.ForeignKey(Pessoa, related_name="forjas", on_delete=models.PROTECT)
    site_id = id_do_site()
    # Opaco: esta célula não é dona do catálogo de desafios.
    desafio_ref = models.CharField(max_length=64)
    medidor = models.PositiveIntegerField(default=0)
    teto = models.PositiveIntegerField(default=99)
    selada_em = models.DateTimeField(null=True, blank=True)
    selo = models.CharField(max_length=120, blank=True, default="")
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["pessoa", "site_id", "desafio_ref"],
                name="uma_forja_por_desafio_por_pessoa",
            ),
            models.CheckConstraint(
                condition=models.Q(medidor__lte=models.F("teto")),
                name="o_medidor_da_forja_respeita_o_teto",
            ),
        ]

    def __str__(self) -> str:
        return f"forja {self.desafio_ref}: {self.medidor}"


# ---------------------------------------------------------------------------
# 6. CONQUISTAS CONCEDIDAS, VALIDAÇÃO E CONSENTIMENTO
# ---------------------------------------------------------------------------


class Concessao(models.Model):
    """Esta pessoa tem esta conquista. Com quem validou, e com que permissão de mostrar.

    **`consentimento` nasce PRIVADO** (decisão fechada 7 da Sessão A): nada é
    exposto sem ação explícita do aluno. O default fechado é o que impede uma
    tela nova de publicar a conquista de alguém por omissão — e continua sendo a
    regra depois da emenda de 30/08/2026, com a razão que a lei §9 dá por
    escrito: privacidade é de adulto também.

    **`validador_id` + `validador_papel` são a auditoria.** Quando um marco é
    contestado, a pergunta é "quem disse que sim?", e ela precisa ter resposta
    meses depois. `sistema` é o único papel sem pessoa por trás, e a restrição
    `concessao_humana_diz_quem_validou` recusa qualquer outro papel sem nome.

    `Unique(pessoa, conquista)` faz o backfill ser RE-EXECUTÁVEL: rodar
    `conceder_fundador` duas vezes não concede duas medalhas.
    """

    class PapelDoValidador(models.TextChoices):
        PROFESSOR = "professor", "Professor"
        MONITOR = "monitor", "Monitor"
        PAR = "par", "Um colega"
        SISTEMA = "sistema", "O sistema (conta automática)"

    class Consentimento(models.TextChoices):
        PRIVADO = "privado", "Só a pessoa vê"
        TURMA = "turma", "A turma vê"
        PUBLICO = "publico", "Aparece no Meu Estúdio público"

    pessoa = models.ForeignKey(
        Pessoa, related_name="concessoes", on_delete=models.PROTECT
    )
    site_id = id_do_site()
    conquista = models.ForeignKey(
        ConquistaDefinicao, related_name="concessoes", on_delete=models.PROTECT
    )
    concedida_em = models.DateTimeField(auto_now_add=True)
    origem_event_id = models.CharField(max_length=64, blank=True, default="")
    validador_id = models.CharField(max_length=64, blank=True, default="")
    validador_papel = models.CharField(
        max_length=9,
        choices=PapelDoValidador.choices,
        default=PapelDoValidador.SISTEMA,
    )
    consentimento = models.CharField(
        max_length=7, choices=Consentimento.choices, default=Consentimento.PRIVADO
    )

    class Meta:
        ordering = ["-concedida_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["pessoa", "conquista"], name="uma_concessao_por_pessoa"
            ),
            models.CheckConstraint(
                condition=models.Q(validador_papel="sistema")
                | ~models.Q(validador_id=""),
                name="concessao_humana_diz_quem_validou",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.pessoa_id}: {self.conquista_id}"


class PedidoDeValidacao(models.Model):
    """A fila da escadinha de três degraus: o autor marca, o monitor confere, o adulto entra no que envolve dinheiro.

    **"Em análise" nunca parece recusa**, e por isso é o estado inicial e tem
    nome de espera, não de dúvida. A DEVOLUÇÃO é privada e exige motivo
    ESTRUTURADO (`motivo_da_devolucao_e_obrigatorio`): "não" sem razão, vindo de
    um colega, é bullying com verniz de processo.

    **`evidencia_privada` nasce `True`.** Marco de dinheiro carrega print de
    pagamento, conversa com cliente, às vezes o nome de um adulto. Isso jamais
    passa por revisão de par. O default fechado é o que impede uma tela futura
    de vazar por omissão.

    **`devolucoes` e `escalado_para_adulto` são o anti-anel.** N devoluções de
    pares escalam para adulto: se um grupo combinar de recusar o trabalho de
    alguém, o caminho termina numa pessoa da equipe, não no aluno.
    """

    class Tipo(models.TextChoices):
        MARCO = "marco", "Marco de carreira"
        OBRA = "obra", "Obra para a galeria"
        AJUDA = "ajuda", "Ajuda prestada a um colega"

    class Estado(models.TextChoices):
        EM_ANALISE = "em_analise", "Em análise"
        ACEITO = "aceito", "Aceito"
        DEVOLVIDO = "devolvido", "Devolvido com o que falta"

    class MotivoDaDevolucao(models.TextChoices):
        FALTA_EVIDENCIA = "falta_evidencia", "Falta a evidência"
        EVIDENCIA_ILEGIVEL = "evidencia_ilegivel", "A evidência não dá para ler"
        FORA_DO_CRITERIO = "fora_do_criterio", "Ainda não cumpre o critério"
        PRECISA_DE_ADULTO = "precisa_de_adulto", "Precisa de um adulto da equipe"

    pessoa = models.ForeignKey(Pessoa, related_name="pedidos", on_delete=models.PROTECT)
    site_id = id_do_site()
    tipo = models.CharField(max_length=5, choices=Tipo.choices)
    conquista = models.ForeignKey(
        ConquistaDefinicao,
        related_name="pedidos",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    evidencia = models.TextField(blank=True)
    evidencia_privada = models.BooleanField(default=True)
    estado = models.CharField(
        max_length=10, choices=Estado.choices, default=Estado.EM_ANALISE
    )
    # O SLA da lei: 48h úteis para respostas, 5 dias úteis para marcos. A data
    # mora na linha porque uma fila sem prazo é uma fila que envelhece calada.
    prazo_ate = models.DateTimeField(null=True, blank=True)
    atribuido_a = models.CharField(max_length=64, blank=True, default="")
    motivo_da_devolucao = models.CharField(
        max_length=18, choices=MotivoDaDevolucao.choices, blank=True, default=""
    )
    devolucoes = models.PositiveSmallIntegerField(default=0)
    escalado_para_adulto = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)
    respondido_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["prazo_ate", "criado_em"]
        indexes = [models.Index(fields=["site_id", "estado", "prazo_ate"])]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(estado="devolvido")
                | ~models.Q(motivo_da_devolucao=""),
                name="motivo_da_devolucao_e_obrigatorio",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.tipo} de {self.pessoa_id}: {self.estado}"


# ---------------------------------------------------------------------------
# 7. PROGRESSO — missões, ligas e a confiança interna
# ---------------------------------------------------------------------------


class ProgressoDeMissao(models.Model):
    """Quanto falta nesta missão, nesta janela. Linha PREGUIÇOSA (Lei 7).

    A linha nasce no PRIMEIRO incremento, nunca na abertura da janela. Criar
    progresso zerado para toda missão de todo aluno todo dia é escrever milhares
    de linhas por nada, e a maioria delas nunca sairia do zero.
    """

    pessoa = models.ForeignKey(
        Pessoa, related_name="progressos", on_delete=models.PROTECT
    )
    site_id = id_do_site()
    missao = models.ForeignKey(
        MissaoDefinicao, related_name="progressos", on_delete=models.PROTECT
    )
    # O dia (diária) ou a segunda-feira (semanal) da janela, em São Paulo.
    janela = models.DateField()
    progresso = models.PositiveIntegerField(default=0)
    cumprida_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-janela"]
        constraints = [
            models.UniqueConstraint(
                fields=["pessoa", "missao", "janela"],
                name="um_progresso_por_missao_por_janela",
            ),
        ]


class GrupoDaSemana(models.Model):
    """Um punhado de alunos disputando a mesma semana. ~15 pessoas, nunca o mundo.

    **Ranking global público, vitalício ou indexável está vetado** (lei §8). O
    grupo é pequeno, dura uma semana e não sai daqui: a tela mostra o topo e a
    VIZINHANÇA do aluno, e nunca o último lugar.
    """

    site_id = id_do_site()
    liga = models.ForeignKey(
        LigaDefinicao, related_name="grupos", on_delete=models.PROTECT
    )
    semana = models.DateField()
    codigo = models.CharField(max_length=32)

    class Meta:
        ordering = ["-semana"]
        constraints = [
            models.UniqueConstraint(
                fields=["site_id", "liga", "semana", "codigo"],
                name="um_grupo_por_codigo_por_semana",
            ),
        ]


class ParticipacaoNaLiga(models.Model):
    """A inscrição de um aluno num grupo da semana. Preguiçosa, e sem rebaixamento.

    `pontos_da_semana` é XP da semana COM teto diário — nunca XP bruto, para uma
    maratona de um dia não decidir a semana inteira. **Marco real fica de fora**
    (ele vale 0 XP, então nem chega aqui): a espinha do sistema não compete.

    Não existe campo `rebaixado`, e a ausência é a decisão: o limiar de promoção
    é ABSOLUTO e ninguém desce.
    """

    pessoa = models.ForeignKey(
        Pessoa, related_name="participacoes", on_delete=models.PROTECT
    )
    site_id = id_do_site()
    grupo = models.ForeignKey(
        GrupoDaSemana, related_name="participacoes", on_delete=models.PROTECT
    )
    pontos_da_semana = models.PositiveIntegerField(default=0)
    promovido = models.BooleanField(default=False)
    inscrita_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-pontos_da_semana"]
        constraints = [
            models.UniqueConstraint(
                fields=["pessoa", "grupo"], name="uma_participacao_por_grupo"
            ),
        ]


class Aquisicao(models.Model):
    """Este aluno tem este cosmético, e talvez esteja usando.

    A compra move Cristais pelo `MovimentoDeCristais` — e é lá, não aqui, que o
    banco recusa qualquer forma de pagar com dinheiro. `Unique(pessoa, item)`
    impede pagar duas vezes pela mesma moldura.
    """

    pessoa = models.ForeignKey(
        Pessoa, related_name="aquisicoes", on_delete=models.PROTECT
    )
    site_id = id_do_site()
    item = models.ForeignKey(
        ItemCosmetico, related_name="aquisicoes", on_delete=models.PROTECT
    )
    equipado = models.BooleanField(default=False)
    adquirida_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-adquirida_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["pessoa", "item"], name="uma_aquisicao_por_item_por_pessoa"
            ),
        ]


class ConfiancaDaComunidade(models.Model):
    """O peso INTERNO de reputação de ajuda. **Nunca exposto, em tela nenhuma.**

    Serve para o sistema decidir a quem pedir uma validação de par, e é isso. No
    momento em que virar número visível, ele vira placar — e placar de "quanto
    você ajuda" produz ajuda encenada. A lei §8 já proíbe pontos de
    personalidade; este campo é o vizinho perigoso deles, e por isso a regra
    dele é a invisibilidade.
    """

    pessoa = models.ForeignKey(
        Pessoa, related_name="confianca", on_delete=models.PROTECT
    )
    site_id = id_do_site()
    peso = models.IntegerField(default=0)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["pessoa", "site_id"], name="uma_confianca_por_pessoa_por_site"
            ),
        ]


# ---------------------------------------------------------------------------
# 8. A OUTBOX — molde byte-a-byte de `services/sugestoes` [RECEITA:R3 v1]
# ---------------------------------------------------------------------------


class OutboxEvent(models.Model):  # [RECEITA:R3 v1]
    """Uma linha por fato que a gamificação afirma ao resto da plataforma.

    Nasce **sem ninguém emitindo nada**: o relay e as cartas de celebração são o
    PR 9 da escada. Ela entra agora porque outbox instalada depois é migração na
    tabela que já cresceu, e porque o molde precisa ser o mesmo da Caixa — dois
    formatos de envelope na mesma plataforma são dois formatos a depurar.

    `payload` guarda **só o campo `data`** do envelope; o envelope inteiro é
    montado pelo relay no instante da publicação. `event_id` é `UUIDField` de
    propósito: todo evento desta plataforma pede `"format": "uuid"` neste campo,
    e é a mesma exceção declarada em `services/sugestoes`.
    """

    event_id = models.UUIDField(default=uuid.uuid4, unique=True)
    event = models.CharField(max_length=100)
    version = models.PositiveSmallIntegerField(default=1)
    payload = models.JSONField()
    site_id = id_do_site()
    occurred_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)
    # As chaves que este evento acrescenta ao ENVELOPE (o nível de cima), e não
    # ao `data` — o `ator_id` do Rito de Contrato de 26/08/2026 mora aqui.
    envelope_extra = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [models.Index(fields=["published_at"])]

    def __str__(self) -> str:
        return f"{self.event}:{self.event_id}"
