"""O motor das sequências: as tabelas, e as travas que fazem cada promessa do
plano virar mecanismo em vez de disciplina.

Lei: `docs/decisoes/PLANO-SEQUENCIAS-DE-MENSAGENS.md` §5 (o modelo de dados) e
§4.1 (por que o motor mora DENTRO da `mensageria`). As dez correções que este
arquivo obedece, e o motivo de cada uma:
`docs/consultorias/sequencias-de-mensagens/VEREDITO.md`.

O QUE ESTE ARQUIVO **NÃO** FAZ, DE PROPÓSITO
--------------------------------------------
Ele é o degrau 2 da escada do §7: tabelas e travas. **Não manda mensagem, não
consome evento, não agenda e não tem régua.** A régua é a TAR-072; o motor que
inscreve e agenda é a TAR-073. Toda `Jornada` nasce `ativa=False`, e toda
`JornadaVersao` nasce **não publicada**: nada que este PR crie no banco pode
mandar carta para ninguém, nem por acidente de deploy.

AS QUATRO PROMESSAS QUE VIRARAM BANCO AQUI
------------------------------------------
Promessa em documento apodrece — é a categoria "garantia sem mecanismo" que a
`RETROSPECTIVA-FASE-D.md` §2 catalogou como a mais cara desta casa, e foi
exatamente nela que o próprio plano escorregou antes da consultoria. Cada
promessa abaixo tem um mecanismo NO POSTGRES, nunca só em `save()`
(`armadilhas/023`: um `queryset.update()` fura guarda escrita em Python):

1. **A mesma pessoa pode entrar na mesma jornada mais de uma vez na vida — mas
   nunca duas vezes ao mesmo tempo.** `uniq_inscricao_andando_por_jornada`, uma
   `UniqueConstraint` **PARCIAL** (`condition=Q(estado="andando")`). Total era o
   defeito que a consultoria achou: fazia a jornada "sumiu" rodar UMA VEZ na
   vida do aluno, e isso bloqueava uma das quatro sequências que o mantenedor
   escolheu (§8.6). O efeito de segunda ordem é pior que o primeiro e está
   escrito em `Inscricao`.

2. **Quem entrou na v1 termina a v1, e o texto não muda embaixo dele.** Duas
   peças, e uma só não bastava: a `Inscricao` aponta para a **versão**, nunca
   para a jornada; e uma versão publicada é **fisicamente imutável** — gatilho
   no banco recusa `UPDATE` e `DELETE` no `Passo` e no `TextoDoPasso` dela
   (migração `0001`). Sem o gatilho, "imutável" seria promessa: o mantenedor
   edita a frase de uma versão publicada e quem está no meio dela vê o texto
   trocar. Com ele, publicar é criar versão nova porque **não existe caminho
   para o contrário**.

3. **A versão a que a inscrição pertence é sempre uma versão DAQUELA jornada.**
   A trava parcial precisa comparar por JORNADA (senão a mesma pessoa andaria na
   v1 e na v2 ao mesmo tempo), e `UniqueConstraint` não atravessa chave
   estrangeira — daí a coluna `jornada` na `Inscricao`. Coluna denormalizada é
   coluna que mente no dia em que alguém a escreve errado, então a coerência é
   uma **chave estrangeira COMPOSTA** de verdade
   (`inscricao_versao_pertence_a_jornada`, na migração): o par
   `(jornada_versao_id, jornada_id)` só existe se existir na `JornadaVersao`.
   O Django 5.1 não modela chave composta; o Postgres a impõe do mesmo jeito, e
   ela sobrevive a `queryset.update()`, a `psql` e a qualquer código futuro.

4. **A trava do dinheiro não se toca.** `uniq_envio_por_order_tipo_canal`, em
   `apps/eventos/models.py`, continua exatamente como está. O motor a reusa com
   `order_id` sintético — e é POR ISSO que `Inscricao` e `Passo` têm chave
   primária UUID: o `order_id` sintético é `jornada:<inscricao_id>:<passo_id>`,
   que com dois UUIDs mede 81 caracteres e cabe nos 100 daquela coluna, sem uma
   linha de migração no fluxo de pagamento (§4.1).

A FRONTEIRA COM `apps/eventos`, QUE É CRITÉRIO DE MORTE
-------------------------------------------------------
O §10.7 do plano é explícito: `apps/jornadas` pode **criar a linha de
`EnvioRegistrado`, e nada mais**. Nenhum modelo deste arquivo tem chave
estrangeira para `apps.eventos`, e é de propósito — quem não consegue apontar
não consegue acoplar. Este PR nem chega a criar aquela linha: quem cria é o
motor (TAR-073).

NADA DE FRASE PRONTA FORA DO `TextoDoPasso`
-------------------------------------------
Lei 1 do §3: aviso é DADO. O `Passo` guarda `assunto` (vocabulário fechado, o do
contrato) e o `TextoDoPasso` guarda o texto **por idioma** — que é a leitura, não
o aviso gravado (§4.3). Nenhuma outra coluna deste arquivo aceita frase.
"""

import uuid
from datetime import timedelta

from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils import timezone

# ---------------------------------------------------------------------------
# OS VOCABULÁRIOS FECHADOS
# ---------------------------------------------------------------------------
# `max_length` FOLGADO de propósito em todo campo de vocabulário fechado. O
# reflexo natural é dimensionar a coluna pela maior palavra existente, e ele
# custa duas coisas (`armadilhas/226`): quem recusa o valor inventado passa a ser
# o TAMANHO da coluna (`DataError`, que não diz qual lei foi violada) e, no dia
# em que uma palavra maior for acrescentada legitimamente, a proibição EVAPORA
# junto com o alargamento. Aqui quem recusa é sempre a `CheckConstraint`, e o
# vermelho do teste diz o nome dela.

# Onde uma mensagem pode sair. `sino` é a caixa de avisos dentro do site (a
# célula `notificacoes`); os outros dois saem da plataforma.
CANAIS = ("sino", "email", "whatsapp")

# A classe decide, ANTES de tudo, se a régua do §6 se aplica: `critica` e
# `transacional` passam POR FORA dela inteira. O cenário que essa ordem conserta
# é real e foi testado contra o texto anterior da régua: medalha às 10h barrando
# a liberação de matrícula às 18h (VEREDITO §1.6).
CLASSES = ("critica", "transacional", "relacional", "engajamento")

# O que aconteceu com uma entrega, por canal. Uma linha barrada NÃO se perde:
# ela guarda o motivo e o `reagendado_para` — é o que dá resposta à pergunta
# "por que o aluno X não recebeu no e-mail?" sem precisar de duas tabelas.
RESULTADOS = ("enviada", "pulada", "barrada_pela_regua", "barrada_por_preferencia")

# Um episódio de uma pessoa numa jornada. `saiu` é a pessoa que deixou de
# satisfazer a condição; `cancelada` é a jornada que foi interrompida por fora.
ESTADOS_DA_INSCRICAO = ("andando", "concluida", "saiu", "cancelada")

# O vocabulário de assuntos é FECHADO para que uma jornada nova não consiga
# inventar um assunto ruim (constituição da célula, §"A régua de quem recebe").
# A fonte da verdade é `contracts/eventos/notificacao.devida.v1.json`; esta
# tupla é a mesma lista dentro do banco, e `tests/test_jornadas_modelo_de_dados`
# prova que ela é SUBCONJUNTO do contrato — nunca o contrário, porque assunto
# novo no contrato pode ser de outra célula e não obriga jornada nenhuma.
ASSUNTOS = (
    "sugestao.status-alterado",
    "matricula.situacao-alterada",
    "gamificacao.nivel-alcancado",
    "gamificacao.conquista-concedida",
    "gamificacao.marco-validado",
    "gamificacao.destaque-da-semana",
    "jornada.passo",
)


def _escolhas(vocabulario):
    return [(v, v) for v in vocabulario]


def id_do_site() -> models.CharField:
    """A fronteira de site, num formato só para não haver dois.

    Texto opaco de 64, como todo id que atravessa fronteira nesta plataforma —
    nunca `UUIDField`. A `EnvioRegistrado` desta mesma célula usa 100 e é a
    exceção histórica: não se mexe nela (é a tabela do fluxo de dinheiro), e
    tabela nova nasce na convenção da casa.
    """
    return models.CharField(max_length=64, db_index=True)


def id_de_pessoa() -> models.CharField:
    """O id de PLATAFORMA de quem recebe — o que a célula `identidade` emite.

    NUNCA o e-mail, nunca o nome, nunca o telefone (`DECISAO-EVO-01` §3). Quem
    precisa falar com a pessoa PERGUNTA à `identidade` na hora do envio; guardar
    o contato aqui seria uma segunda casa de um dado que vive numa linha só.
    """
    return models.CharField(max_length=64, db_index=True)


# ---------------------------------------------------------------------------
# A SEQUÊNCIA, E A VERSÃO QUE A CONGELA
# ---------------------------------------------------------------------------


class Jornada(models.Model):
    """A identidade ESTÁVEL de uma sequência — o que não muda quando o texto muda.

    O `slug` é o que viaja no evento (`jornada_slug`, no ramo `jornada.passo` do
    contrato) justamente porque é estável: o nome é editável pelo mantenedor e
    mudaria o sentido de avisos antigos.
    """

    site_id = id_do_site()
    slug = models.SlugField(max_length=80)

    # SEMPRE um evento — e a ausência também vira um. "Sumiu há cinco dias" não é
    # acontecimento, é a falta de um; a saída NÃO é abrir uma exceção aqui (um
    # campo `tipo_de_entrada`, com um ramo para condição temporal), é a varredura
    # PUBLICAR `aluno.inatividade-detectada.v1` e a jornada continuar sabendo só
    # de eventos (§5, VEREDITO §1.8). Esse contrato ainda não existe: nasce no
    # degrau 6b, em Rito com o mantenedor.
    gatilho = models.CharField(max_length=100)

    # Nasce DESLIGADA. Ligar uma sequência é decisão do mantenedor, nunca efeito
    # colateral de um deploy — a mesma escolha que a `gamificacao` fez com a
    # economia. Sem isto, o PR que semeia uma jornada a põe no ar sozinho.
    ativa = models.BooleanField(default=False)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site_id", "slug"], name="uniq_jornada_por_site_e_slug"
            ),
            models.CheckConstraint(
                condition=~models.Q(gatilho=""), name="jornada_tem_gatilho"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.slug}@{self.site_id}"


class JornadaVersao(models.Model):
    """Uma versão da sequência — e, depois de publicada, uma PEDRA.

    `publicada_em` nulo é rascunho: é onde o mantenedor mexe à vontade (degrau
    7). No instante em que ele publica, o gatilho
    `jornadas_versao_publicada_e_pedra` da migração passa a recusar `UPDATE` e
    `DELETE` nesta linha, nos `Passo` dela e nos `TextoDoPasso` deles. Publicar
    de novo é criar a versão SEGUINTE.

    Por que tanta força para uma promessa que parecia simples: sem o gatilho, o
    mantenedor troca a frase de boas-vindas numa terça à noite — que é
    exatamente o que a tela dele existe para permitir — e a troca alcança quem
    entrou na sequência ontem. As duas promessas do plano (ele edita quando
    quiser; ninguém vê o texto mudar embaixo de si) só são compatíveis porque
    a versão é imutável.
    """

    jornada = models.ForeignKey(
        Jornada, on_delete=models.PROTECT, related_name="versoes"
    )
    numero = models.PositiveIntegerField()
    publicada_em = models.DateTimeField(null=True, blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["jornada", "numero"], name="uniq_versao_por_jornada_e_numero"
            ),
            models.CheckConstraint(
                condition=models.Q(numero__gte=1), name="versao_comeca_no_um"
            ),
            # A âncora da chave estrangeira COMPOSTA que a `Inscricao` usa (ver o
            # item 3 do cabeçalho). Sozinha ela é redundante — `id` já é único —,
            # mas o Postgres exige um índice único sobre EXATAMENTE as colunas
            # referenciadas para aceitar a FK composta. Apagar esta linha derruba
            # a coerência da `Inscricao` sem que nada nesta classe pareça errado.
            models.UniqueConstraint(
                fields=["id", "jornada"], name="uniq_versao_id_com_jornada"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.jornada.slug} v{self.numero}"

    @property
    def publicada(self) -> bool:
        return self.publicada_em is not None


class Passo(models.Model):
    """Uma mensagem da sequência, presa a UMA versão e imutável junto com ela.

    A chave primária é UUID porque ela SAI da célula: é o `passo_id` do ramo
    `jornada.passo` do contrato, o id opaco pelo qual o sininho busca o texto na
    hora de ler. Id sequencial atravessando fronteira conta quantos passos a
    escola tem para quem só devia ver o próprio aviso.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    jornada_versao = models.ForeignKey(
        JornadaVersao, on_delete=models.PROTECT, related_name="passos"
    )
    ordem = models.PositiveIntegerField()

    # Quanto tempo depois da ÂNCORA da inscrição este passo fica elegível — e
    # não "depois do passo anterior". A diferença tem consequência escrita no
    # §5: se a régua empurrou o passo 2 de D+2 para D+3, o passo 3 continua
    # saindo em D+5, porque o cronograma é ancorado em `Inscricao.ancora_em`.
    # Atraso da régua não empurra os passos seguintes.
    atraso = models.DurationField(default=timedelta(0))

    # Quanto tempo este passo continua fazendo sentido depois de ficar elegível.
    # Nulo é "não expira". LEIA COM CUIDADO: isto NÃO é uma janela de horário —
    # a janela de silêncio (nunca antes das 8h, nunca depois das 20h) é UMA SÓ,
    # do §6, e vale para toda entrega da célula. Janela por jornada seria a
    # "exceção só para esta jornada" que o §10.4 lista como critério de morte.
    # O §5 nomeia o campo apenas como `janela`; o significado aqui é o único
    # compatível com o §10.4, e está escrito para a TAR-073 não ter de adivinhar.
    janela = models.DurationField(null=True, blank=True)

    assunto = models.CharField(
        max_length=80, choices=_escolhas(ASSUNTOS), default="jornada.passo"
    )
    classe = models.CharField(max_length=32, choices=_escolhas(CLASSES))

    # Lista, e não um canal: sino entregue + e-mail devolvido + WhatsApp barrado
    # são TRÊS resultados independentes, e é por isso que a chave da `Entrega`
    # inclui o canal (VEREDITO §1.5).
    canais = ArrayField(models.CharField(max_length=32, choices=_escolhas(CANAIS)))

    # O nome de uma função Python registrada num dicionário ("já entrou em
    # alguma aula?"), reavaliada NO INSTANTE DO ENVIO — nunca no da inscrição.
    # Vazio é "sem condição". Condição nova é PR pequeno; uma linguagem de
    # fórmulas dentro do banco é o critério de morte §10.1.
    condicao_slug = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["jornada_versao", "ordem"],
                name="uniq_passo_por_versao_e_ordem",
            ),
            # O contrato diz `"ordem": {"minimum": 1}`; aqui é a mesma regra no
            # banco, para o passo zero não nascer e viajar.
            models.CheckConstraint(
                condition=models.Q(ordem__gte=1), name="passo_comeca_no_um"
            ),
            models.CheckConstraint(
                condition=models.Q(assunto__in=ASSUNTOS),
                name="passo_com_assunto_do_contrato",
            ),
            models.CheckConstraint(
                condition=models.Q(classe__in=CLASSES),
                name="passo_com_classe_conhecida",
            ),
            models.CheckConstraint(
                condition=models.Q(atraso__gte=timedelta(0)),
                name="passo_nao_espera_para_tras",
            ),
            models.CheckConstraint(
                condition=models.Q(canais__contained_by=list(CANAIS)),
                name="passo_so_usa_canais_conhecidos",
            ),
            # Passo sem canal nenhum é passo que nunca sai, e a varredura o
            # leria como pendente para sempre. A grafia é `~Q(canais=[])`, que
            # vira `NOT (canais = '{}')` — direto e sem intermediário.
            #
            # MEDIDO, porque a explicação natural aqui é falsa e quase entrou:
            # `canais__len__gt=0` TAMBÉM funciona pelo ORM. O Django não escreve
            # `array_length(canais, 1) > 0` cru — ele gera
            # `coalesce(array_length("canais", 1), 0) > 0`, e o `coalesce` é
            # justamente o que fecha o buraco. A armadilha existe, mas é do SQL
            # ESCRITO À MÃO: `CHECK (array_length(c, 1) > 0)` ACEITA o array
            # vazio, porque `array_length` de vazio é NULL, `NULL > 0` é NULL, e
            # `CHECK` que devolve NULL passa (conferido em psql: a linha entrou).
            # Vale para esta migração, que tem `RunSQL` de verdade lá dentro.
            models.CheckConstraint(
                condition=~models.Q(canais=[]), name="passo_sai_por_algum_canal"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.jornada_versao} passo {self.ordem}"


class TextoDoPasso(models.Model):
    """O texto que o mantenedor edita, um por idioma — a frase, na LEITURA.

    Não contradiz a lei 1 ("aviso é DADO, nunca frase pronta"): o que a lei
    proíbe é GRAVAR a frase no aviso, que é lido meses depois, possivelmente em
    outro idioma. Aqui a frase é o catálogo de onde a leitura nasce, no idioma de
    quem lê, na hora de ler (§4.3).

    O idioma é texto livre de propósito (`pt-br`, `en`, `es` hoje): fechar a
    lista faria um quarto idioma exigir migração de banco, e o projeto trata
    código de idioma pela FORMA, não por lista.
    """

    passo = models.ForeignKey(Passo, on_delete=models.CASCADE, related_name="textos")
    idioma = models.CharField(max_length=16)
    assunto_visivel = models.CharField(max_length=200)
    corpo = models.TextField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["passo", "idioma"], name="uniq_texto_por_passo_e_idioma"
            ),
            models.CheckConstraint(
                condition=~models.Q(idioma=""), name="texto_declara_o_idioma"
            ),
            models.CheckConstraint(
                condition=~models.Q(corpo=""), name="texto_tem_corpo"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.passo} [{self.idioma}]"


# ---------------------------------------------------------------------------
# A PESSOA DENTRO DA JORNADA
# ---------------------------------------------------------------------------


class Inscricao(models.Model):
    """Um EPISÓDIO de uma pessoa numa jornada — não a vida dela na jornada.

    A palavra "episódio" é a correção mais importante da consultoria. A trava
    era total (`unique(jornada, destinatario_id, site_id)`), e com ela quem sumiu
    em março, voltou e sumiu de novo em julho **batia na trava na segunda vez**:
    a jornada "sumiu há alguns dias" rodaria uma vez na vida de cada aluno, e ela
    é uma das quatro que o mantenedor escolheu.

    E reaproveitar a linha antiga não salvava, por um efeito de segunda ordem que
    é pior que o defeito: o `order_id` sintético é
    `jornada:<inscricao_id>:<passo_id>`, então repetir a inscrição repetiria o
    `order_id` — e o segundo episódio seria DESCARTADO COMO "JÁ ENVIADO", EM
    SILÊNCIO, pela trava do pagamento que o §4.1 reusa de propósito. Com a trava
    parcial, cada episódio é uma `Inscricao` nova, o `inscricao_id` muda, e o
    `order_id` volta a ser único sem tocar na constraint do dinheiro.

    A trava parcial não afrouxa nada: continua no banco, e continua impedindo —
    junto com o dedup por `event_id` — que um evento reentregue inscreva em dobro.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # As DUAS pontas, e as duas são necessárias. `jornada_versao` é a que decide
    # o conteúdo e é o motivo de o texto não mudar embaixo de quem já entrou.
    # `jornada` existe porque a trava parcial precisa comparar por jornada — a
    # mesma pessoa andando na v1 e na v2 ao mesmo tempo seria a mensagem em dobro
    # que a trava existe para impedir — e `UniqueConstraint` não atravessa chave
    # estrangeira. Que as duas concordem NÃO é disciplina: é a chave estrangeira
    # composta `inscricao_versao_pertence_a_jornada`, criada na migração.
    jornada_versao = models.ForeignKey(
        JornadaVersao, on_delete=models.PROTECT, related_name="inscricoes"
    )
    jornada = models.ForeignKey(
        Jornada, on_delete=models.PROTECT, related_name="inscricoes"
    )

    destinatario_id = id_de_pessoa()
    site_id = id_do_site()

    # A `ordem` do último passo entregue; 0 é "ainda não saiu nada".
    passo_atual = models.PositiveIntegerField(default=0)

    # OS CARIMBOS DE TEMPO, E POR QUE NÃO BASTA UM. `ancora_em` é quando o
    # episódio começou, e é dele que TODO passo conta o próprio atraso (§5).
    # `proximo_em` é quando o próximo passo fica elegível — é por ele que a
    # varredura procura, e é por isso que existe o índice composto lá embaixo.
    ancora_em = models.DateTimeField(default=timezone.now)
    proximo_em = models.DateTimeField(null=True, blank=True)

    estado = models.CharField(
        max_length=32, choices=_escolhas(ESTADOS_DA_INSCRICAO), default="andando"
    )
    motivo_de_saida = models.CharField(max_length=200, blank=True, default="")

    # O `event_id` do fato que inscreveu esta pessoa — a ponta que liga o
    # episódio ao acontecimento, e o que torna a inscrição auditável de fora.
    origem_event_id = models.UUIDField(null=True, blank=True)

    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # A TRAVA PARCIAL. A condição é o conserto inteiro: sem ela, o
            # episódio seguinte da mesma pessoa é recusado para sempre.
            models.UniqueConstraint(
                fields=["jornada", "destinatario_id", "site_id"],
                condition=models.Q(estado="andando"),
                name="uniq_inscricao_andando_por_jornada",
            ),
            models.CheckConstraint(
                condition=models.Q(estado__in=ESTADOS_DA_INSCRICAO),
                name="inscricao_com_estado_conhecido",
            ),
        ]
        indexes = [
            # Como a varredura da TAR-073 vai procurar: quem está andando e já
            # passou da hora. Sem ele a passada lê a tabela inteira.
            models.Index(
                fields=["estado", "proximo_em"], name="idx_inscricao_a_vencer"
            ),
        ]

    def save(self, *args, **kwargs):
        """Preenche `jornada` a partir da versão QUANDO ela não foi informada.

        Conveniência, e só isso: quem GARANTE a coerência é a chave estrangeira
        composta no banco. A diferença importa porque `armadilhas/023` já custou
        caro aqui — um `queryset.update()` não passa por `save()`, e uma guarda
        que só mora neste método é uma guarda que o primeiro `update()` fura.
        """
        if self.jornada_id is None and self.jornada_versao_id is not None:
            self.jornada_id = self.jornada_versao.jornada_id
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.destinatario_id} em {self.jornada_versao} ({self.estado})"


# ---------------------------------------------------------------------------
# O QUE SAIU, O QUE NÃO SAIU, E O QUE A PESSOA ACEITA RECEBER
# ---------------------------------------------------------------------------


class Entrega(models.Model):
    """O que foi — ou NÃO foi — entregue, por canal, e por quê.

    Guardar o que não saiu é o ponto da tabela, não um detalhe: sem estas linhas,
    a pergunta "por que o aluno X não recebeu no e-mail?" não tem resposta e o
    mantenedor fica olhando para o silêncio. Com elas, a tela do degrau 7
    responde "barrada pela régua: já tinha recebido uma hoje".
    """

    inscricao = models.ForeignKey(
        Inscricao, on_delete=models.PROTECT, related_name="entregas"
    )
    passo = models.ForeignKey(Passo, on_delete=models.PROTECT, related_name="entregas")
    canal = models.CharField(max_length=32, choices=_escolhas(CANAIS))

    decidida_em = models.DateTimeField(auto_now_add=True)
    previsto_para = models.DateTimeField()
    # Barrado pela régua NÃO se perde: reagenda para a próxima janela válida, e
    # a linha guarda para quando (§6.2).
    reagendado_para = models.DateTimeField(null=True, blank=True)
    enviado_em = models.DateTimeField(null=True, blank=True)

    resultado = models.CharField(max_length=48, choices=_escolhas(RESULTADOS))
    motivo = models.CharField(max_length=200, blank=True, default="")

    # O `event_id` da carta publicada (`notificacao.devida.v1`), quando houve
    # carta. Nulo enquanto nada saiu — e nulo para sempre no que foi barrado.
    event_id = models.UUIDField(null=True, blank=True)

    class Meta:
        constraints = [
            # O CANAL ESTÁ NA CHAVE, e não fora dela. `Passo.canais` é lista, e
            # uma linha por passo não representava sino entregue + e-mail
            # devolvido + WhatsApp barrado.
            models.UniqueConstraint(
                fields=["inscricao", "passo", "canal"],
                name="uniq_entrega_por_inscricao_passo_canal",
            ),
            models.CheckConstraint(
                condition=models.Q(canal__in=CANAIS), name="entrega_com_canal_conhecido"
            ),
            models.CheckConstraint(
                condition=models.Q(resultado__in=RESULTADOS),
                name="entrega_com_resultado_conhecido",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.passo} -> {self.canal}: {self.resultado}"


class Preferencia(models.Model):
    """O que a pessoa aceita receber, por canal e por CLASSE.

    Por classe, e não um `receber_email` booleano: o booleano funciona três meses
    e vira dívida no dia em que for preciso distinguir segurança de progresso de
    comunidade — e nesse dia já haverá gente com a preferência gravada, o que
    torna a migração uma adivinhação sobre o que cada um quis dizer.

    Vale lembrar de onde: silenciar `relacional` e `engajamento` silencia mesmo;
    `critica` e `transacional` passam por fora da régua inteira (§6.1), e é a
    régua da TAR-072 quem faz valer essa ordem — esta tabela só guarda a vontade.
    """

    destinatario_id = id_de_pessoa()
    site_id = id_do_site()
    canal = models.CharField(max_length=32, choices=_escolhas(CANAIS))
    classe = models.CharField(max_length=32, choices=_escolhas(CLASSES))
    aceita = models.BooleanField(default=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["destinatario_id", "site_id", "canal", "classe"],
                name="uniq_preferencia_por_pessoa_canal_classe",
            ),
            models.CheckConstraint(
                condition=models.Q(canal__in=CANAIS),
                name="preferencia_com_canal_conhecido",
            ),
            models.CheckConstraint(
                condition=models.Q(classe__in=CLASSES),
                name="preferencia_com_classe_conhecida",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.destinatario_id} {self.canal}/{self.classe}={self.aceita}"


# ---------------------------------------------------------------------------
# O QUE A JORNADA PRECISA SABER SOBRE O ALUNO, E O QUE ELE FEZ DEPOIS
# ---------------------------------------------------------------------------


class EstadoDoAluno(models.Model):
    """Uma PROJEÇÃO — nunca a fonte da verdade.

    As condições do §5 ("já entrou em aula?", "postou no fórum?") perguntam por
    fatos que não moram nesta célula. Sem esta tabela, cada condição vira chamada
    síncrona a outra célula: o `consome:` cresce a cada condição nova e a
    varredura vira multiplicação — 10 mil pessoas x 4 condições é 40 mil idas à
    rede numa passada.

    A Lei 7 (nenhum fato mora em dois lugares) continua respeitada, e a distinção
    é o que a salva: esta tabela é CALCULADA de eventos, e a autoridade sobre
    cada fato continua na célula de origem. Projeção operacional não é segunda
    fonte da verdade — mas isso precisa estar escrito, senão a próxima sessão lê
    como duplicação e tem razão.

    Quem a alimenta é o motor (TAR-073). Aqui ela nasce vazia.
    """

    destinatario_id = id_de_pessoa()
    site_id = id_do_site()
    ultima_atividade_em = models.DateTimeField(null=True, blank=True)
    ultima_aula_em = models.DateTimeField(null=True, blank=True)
    ultimo_post_em = models.DateTimeField(null=True, blank=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["destinatario_id", "site_id"],
                name="uniq_estado_do_aluno_por_pessoa_e_site",
            ),
        ]

    def __str__(self) -> str:
        return f"estado de {self.destinatario_id}@{self.site_id}"


class Efeito(models.Model):
    """O que a pessoa fez DEPOIS de receber (decisão do mantenedor, §8.8).

    Ela nasce junto do motor mesmo com a tela vindo só no degrau 11, e a razão é
    dura: reservar o lugar custa uma tabela agora; descobrir o efeito de
    mensagens que já saíram, sem tê-lo reservado, é impossível — o passado não
    volta para ser medido.

    O QUE ESTA TABELA NÃO É, E FOI ESCOLHA DELE: não há grupo de controle (ele
    recusou deliberadamente não ajudar parte dos alunos para medir a diferença) e
    não há rastreio de abertura ou clique — nada de pixel, nada de link
    reescrito. Consequência aceita e dita: os números mostram CORRELAÇÃO, NÃO
    CAUSA. Quem ler os números depois precisa saber disso, e é por isso que está
    aqui e não só no livro.
    """

    entrega = models.ForeignKey(
        Entrega, on_delete=models.CASCADE, related_name="efeitos"
    )
    # `efeitos` no plural, e não `efeito`, mesmo com a unicidade garantida:
    # é chave estrangeira, então o acesso reverso devolve um gerenciador, e
    # `entrega.efeito.voltou_em` estouraria. O plural avisa disso na hora de
    # escrever; `unique(entrega)` é quem garante que nunca haja dois.
    voltou_em = models.DateTimeField(null=True, blank=True)
    abriu_aula_em = models.DateTimeField(null=True, blank=True)
    concluiu_aula_em = models.DateTimeField(null=True, blank=True)
    postou_em = models.DateTimeField(null=True, blank=True)
    apurado_em = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["entrega"], name="uniq_efeito_por_entrega"),
        ]

    def __str__(self) -> str:
        return f"efeito de {self.entrega_id}"
