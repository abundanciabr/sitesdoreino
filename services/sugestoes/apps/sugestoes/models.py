# apps/sugestoes/models.py — o modelo de dados da Caixa de Sugestões (EVO-11)
"""Camada de dados da célula `sugestoes`.

Fonte: `docs/caixa-de-sugestoes/ESPECIFICACAO-CELULA.md` §5/§6 e
`docs/caixa-de-sugestoes/DECISAO-EVO-01-identidade.md` §3.

**Duas correções deliberadas sobre a §6 da spec**, ambas medidas antes de
escrever código (`AUDITORIA-AS-IS.md`, Q3 e tabela de divergências nº 2):

1. **Os IDs inter-célula NÃO são UUID.** A spec mostra `models.UUIDField()` em
   `tenant_id`/`produto_id`. Em toda esta plataforma o ID que atravessa
   fronteira é **string opaca** — `Site.id`, `Product.id`, `site_id`,
   `product_id` são `type: string` **sem** `format: uuid` nos contratos. Um
   `UUIDField` aqui criaria uma fronteira que não casa com a casa e obrigaria
   uma conversão silenciosa em cada consumidor.
2. **`tenant_id` chama-se `site_id`.** "Tenant" não existe no vocabulário desta
   plataforma; site existe (Lei 9), é resolvido do Host uma vez por requisição
   (CONV-SITE) e viaja nos eventos (INV-P11).

O que **não** mora aqui, de propósito: endpoint (EVO-12) e fluxo de login
(EVO-01 decidiu o desenho; o fluxo é despacho próprio). Desde o EVO-20 mora
aqui também a **outbox** (`OutboxEvent`) — a célula deixou de só guardar fatos
e passou a afirmá-los. Desde o EVO-21 mora aqui o `Aviso`: o mesmo fato, escrito
para o aluno ler dentro da própria Caixa.
"""

import secrets
import uuid

from django.db import models


def cunhar_id() -> str:
    """Cunha o identificador opaco de uma `Identidade`.

    Texto, nunca UUID — é a decisão do EVO-01 §3, e a forma escolhida
    (`token_urlsafe`) deixa isso impossível de confundir: nenhum consumidor
    consegue "reconhecer um UUID" e passar a tratá-lo como tal.
    """
    return secrets.token_urlsafe(16)


class RegistroImutavel(Exception):
    """Tentativa de editar ou apagar uma linha append-only.

    O banco também recusa (trigger da migration 0001) — esta exceção é a
    camada Python, que erra com mensagem legível antes de a requisição chegar
    ao Postgres. Ver `HistoricoStatus`.
    """


class CorredorAusente(Exception):
    """`planejado → em_desenvolvimento` sem ChangeSpec aprovado (EVO-40).

    Mora AQUI, e não em `apps/core/changespecs.py`, porque quem a levanta é o
    `Sugestao.save()` — o degrau que pega qualquer caminho Python, inclusive um
    `manage.py` escrito daqui a seis meses que nunca ouviu falar da moderação.
    `apps/sugestoes` não importa `apps/core`; é o contrário.
    """


class Identidade(models.Model):
    """Quem é a pessoa, para esta célula — cunhada na primeira entrada.

    Lei do assunto: `DECISAO-EVO-01-identidade.md`. O Google prova QUEM É; a
    célula `alunos` decide SE PODE. A `sugestoes` nunca recebe ator pronto de
    ninguém e nunca lê o banco de `alunos`.

    **O e-mail vive AQUI e em nenhum outro lugar.** Sugestão, voto e
    comentário apontam para esta linha; nenhum deles guarda e-mail. É dado
    pessoal: uma pessoa que troque de endereço é uma linha editada, não um
    histórico reescrito.

    Desde a Fase 1 do `docs/notificacoes/PLANO-MESTRE.md` (25/08/2026) a linha
    guarda TAMBÉM `id_da_plataforma` — ver o campo, logo abaixo.
    """

    id = models.CharField(
        primary_key=True, max_length=64, default=cunhar_id, editable=False
    )
    # `unique` no e-mail (e não no par com `provedor`): a mesma pessoa entrando
    # amanhã por outro provedor — um código, por exemplo — precisa RECUPERAR
    # esta identidade, não cunhar uma segunda (EVO-01 §3).
    email = models.EmailField(unique=True)
    # [INV-SUG11] O id da MESMA pessoa na célula `identidade` — o único
    # identificador que atravessa a plataforma. A resposta de `getSessionFull`
    # já o entrega (`SessionFull.id`, contrato congelado) e a porta o descartava
    # até hoje; guardá-lo é a Fase 1 do plano de notificações, e sem ele nenhuma
    # caixa central consegue endereçar ninguém (PLANO-MESTRE §2).
    #
    # **`null=True`, e a escolha decide se a migration sobe.** Toda linha que já
    # existe em produção nasceu sem este dado, e no Postgres um índice único
    # trata cada `NULL` como distinto dos outros — mil linhas vazias convivem.
    # String vazia NÃO: `''` colide com `''`, e o `AddField` estouraria com
    # `duplicate key value violates unique constraint` na segunda linha antiga.
    # Daí o par que parece redundante e não é: `null=True` (o estado "ainda não
    # sei") **mais** o `CheckConstraint` abaixo, que impede o segundo jeito de
    # não saber. Um campo com duas formas de "vazio" é um campo que dois pedaços
    # de código consultam de jeitos diferentes.
    #
    # NÃO substitui o casamento por e-mail: `cunhar_ou_recuperar` continua
    # buscando por `email`, que é o que preservou a autoria inteira quando o
    # login mudou de casa (DECISAO-celula-de-identidade §3).
    id_da_plataforma = models.CharField(max_length=64, null=True, unique=True)
    provedor = models.CharField(max_length=20, default="google")
    nome_exibido = models.CharField(max_length=120, blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(id_da_plataforma=""),
                name="identidade_id_da_plataforma_nunca_vazio",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover - conveniência de admin/shell
        return self.nome_exibido or self.email


class Quadro(models.Model):
    """A fronteira de contexto: toda sugestão pertence a exatamente um quadro.

    Spec §5. `produto_id` nulo = quadro da plataforma inteira. Aceita NULL de
    propósito: aqui "vazio" e "todos os produtos" são estados DIFERENTES, e
    string vazia os confundiria. (Era a única coluna de texto nulável da célula
    até a Fase 1 do plano de notificações, que acrescentou
    `Identidade.id_da_plataforma` — lá o motivo é outro: unicidade parcial.)
    """

    site_id = models.CharField(max_length=64)
    produto_id = models.CharField(max_length=64, null=True, blank=True)
    nome = models.CharField(max_length=100)

    class Meta:
        indexes = [models.Index(fields=["site_id"])]

    def __str__(self) -> str:  # pragma: no cover
        return self.nome


class Categoria(models.Model):
    quadro = models.ForeignKey(
        Quadro, related_name="categorias", on_delete=models.CASCADE
    )
    slug = models.SlugField()
    nome = models.CharField(max_length=80)
    ordem = models.PositiveIntegerField(default=0)
    # Desativar OCULTA da criação; não invalida sugestão antiga (spec §9).
    ativa = models.BooleanField(default=True)

    class Meta:
        ordering = ["ordem", "slug"]
        constraints = [
            models.UniqueConstraint(
                fields=["quadro", "slug"], name="categoria_quadro_slug_unica"
            )
        ]

    def __str__(self) -> str:  # pragma: no cover
        return self.nome


class SugestaoQuerySet(models.QuerySet):
    def visiveis(self):
        """Sem as arquivadas — o recorte que toda superfície voltada para o
        aluno usa (`DECISAO-arquivar-ideia.md`).

        **Não é status, e por isso não é `Status`.** Arquivar não é uma decisão
        de produto sobre a ideia (isso é o trilho: planejado, não planejado...);
        é a equipe tirando algo de vista — spam, duplicata, pedido enviado por
        engano. A mesma lição de `DECISAO-a-ficha-nao-se-apaga.md` (a ficha do
        aluno nunca é apagada, só deixa de aparecer): a linha continua inteira,
        com voto, comentário e histórico, e só some do que o ALUNO alcança.

        A gestão (Admin) usa o manager padrão, sem este filtro: quem arquivou
        precisa conseguir achar a ideia de novo para desarquivar.
        """
        return self.filter(arquivada_em__isnull=True)


class Sugestao(models.Model):
    class Status(models.TextChoices):
        EM_ANALISE = "em_analise", "Em análise"
        PLANEJADO = "planejado", "Planejado"
        EM_DESENVOLVIMENTO = "em_desenvolvimento", "Em desenvolvimento"
        IMPLEMENTADO = "implementado", "Implementado"
        NAO_PLANEJADO = "nao_planejado", "Não planejado"
        MESCLADO = "mesclado", "Mesclado"

    quadro = models.ForeignKey(
        Quadro, related_name="sugestoes", on_delete=models.CASCADE
    )
    categoria = models.ForeignKey(
        Categoria, related_name="sugestoes", on_delete=models.PROTECT
    )
    # FK de verdade, e não campo opaco: `Identidade` mora NESTA célula e NESTE
    # banco. A Lei 3 proíbe FK cruzando banco de célula — dentro dele, a
    # integridade referencial é de graça. O atributo continua se chamando
    # `autor_id` (Django cria a coluna `autor_id` para a FK `autor`) e continua
    # sendo texto opaco, porque `Identidade.id` é texto opaco.
    autor = models.ForeignKey(
        "Identidade", related_name="sugestoes", on_delete=models.PROTECT
    )
    titulo = models.CharField(max_length=140)
    problema = models.TextField()
    solucao_proposta = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.EM_ANALISE
    )
    sugestao_canonica = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        related_name="mescladas",
        on_delete=models.SET_NULL,
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    # O arquivamento (`DECISAO-arquivar-ideia.md`, 29/08/2026). `NULL` = ativa —
    # e é o `NULL`, não um booleano ao lado, que decide `visiveis()` acima; um
    # booleano redundante poderia discordar do carimbo no primeiro `update()`
    # que tocasse um campo e esquecesse o outro.
    arquivada_em = models.DateTimeField(null=True, blank=True)
    arquivada_por = models.ForeignKey(
        "Identidade",
        null=True,
        blank=True,
        related_name="ideias_arquivadas",
        on_delete=models.PROTECT,
    )
    # Por que a equipe tirou isto de vista — texto livre, como a nota do
    # histórico de status. Vazio é o normal (nem toda arquivada precisa de
    # explicação escrita); a tela só a oferece como campo opcional.
    motivo_do_arquivamento = models.TextField(blank=True, default="")
    # O apagamento definitivo (`DECISAO-apagar-ideia.md`, 29/08/2026) — a
    # "lousa apagada": irreversível por fora (título, texto, votos e
    # comentários desaparecem para sempre), mas a LINHA fica, porque
    # `HistoricoStatus`/`ChangeSpecAprovado`/`Aviso` são `PROTECT` de
    # propósito e o Postgres tem um trigger recusando apagar o histórico
    # (EVO-11/EVO-40) — apagar a `Sugestao` de verdade quebraria os três
    # degraus dessa trava. Uma ideia apagada é SEMPRE também arquivada (ver
    # `apagar()`): `apagada_em` não entra em `visiveis()` porque nada
    # precisa filtrar duas vezes o que `arquivada_em` já esconde.
    apagada_em = models.DateTimeField(null=True, blank=True)
    apagada_por = models.ForeignKey(
        "Identidade",
        null=True,
        blank=True,
        related_name="ideias_apagadas",
        on_delete=models.PROTECT,
    )

    objects = SugestaoQuerySet.as_manager()

    class Meta:
        indexes = [models.Index(fields=["quadro", "status"])]

    def __str__(self) -> str:  # pragma: no cover
        return self.titulo

    def save(self, *args, **kwargs):
        """[INV-SUG10] Degrau 2 da trava do ChangeSpec — o que pega TODO
        caminho Python.

        A `ESPECIFICACAO-CELULA.md` §8 pede a validação "no `save()` ou no
        serializer", e é literalmente aqui. O degrau 1 é o ponto de
        estrangulamento (`registrar_mudanca_de_status`, em
        `apps/core/moderacao.py`), que recusa **antes de abrir a transação** e
        com uma frase que ensina o caminho; este degrau existe para o dia em
        que alguém escrever um SEGUNDO caminho — um comando de `manage.py`,
        uma correção em massa, um `python manage.py shell` às onze da noite.

        **Custa uma consulta por gravação de linha existente**, para saber o
        status anterior. É a única forma de o guarda não depender de quem
        chama: uma assinatura que recebesse `status_anterior` seria um guarda
        com porta dos fundos do tamanho da confiança em cada chamador. O preço
        é pago só em mudança de status (a criação de sugestão não passa por
        aqui: `_state.adding` é `True`), que acontece algumas vezes por dia.

        O que este degrau NÃO pega: `QuerySet.update(status=...)` e SQL cru —
        eles não passam por `save()` (`armadilhas/023`). Quem os pega é o
        degrau 3, o trigger `sugestoes_exige_changespec` da migration `0004`.
        """
        if not self._state.adding and self.status == self.Status.EM_DESENVOLVIMENTO:
            anterior = (
                Sugestao.objects.filter(pk=self.pk)
                .values_list("status", flat=True)
                .first()
            )
            if (
                anterior == self.Status.PLANEJADO
                and not ChangeSpecAprovado.objects.filter(sugestao_id=self.pk).exists()
            ):
                raise CorredorAusente(
                    f"INV-SUG10: a sugestão {self.pk} não tem ChangeSpec "
                    "aprovado registrado — 'planejado' não vira "
                    "'em_desenvolvimento' sem o corredor existir primeiro "
                    "(FORMATO-CHANGESPEC.md §5)."
                )
        return super().save(*args, **kwargs)


class Voto(models.Model):
    """Um ator vota no máximo uma vez por sugestão (spec §8).

    Desvotar **apaga a linha** — nunca marca inativa. Por isso não existe aqui
    nenhum campo `ativo`/`removido_em`: se existisse, a contagem de votos
    passaria a depender de um filtro que alguém pode esquecer, e a corrida de
    dois cliques (spec §9) deixaria de ser resolvida pelo banco.
    """

    sugestao = models.ForeignKey(
        Sugestao, related_name="votos", on_delete=models.CASCADE
    )
    autor = models.ForeignKey(
        "Identidade", related_name="votos", on_delete=models.PROTECT
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["sugestao", "autor"], name="voto_unico_por_ator_e_sugestao"
            )
        ]


class Comentario(models.Model):
    sugestao = models.ForeignKey(
        Sugestao, related_name="comentarios", on_delete=models.CASCADE
    )
    autor = models.ForeignKey(
        "Identidade", related_name="comentarios", on_delete=models.PROTECT
    )
    texto = models.TextField()
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["criado_em"]


class AppendOnlyQuerySet(models.QuerySet):
    """[armadilhas/023] `QuerySet.update()` NÃO passa por `Model.save()`.

    Guarda de imutabilidade escrito só no `save()` tem uma porta dos fundos
    larga: `Model.objects.filter(...).update(...)` e `bulk_update()` (que
    internamente chama este `update()`) mudariam a linha sem nunca tocar o
    modelo. As duas metades precisam existir.

    A mensagem sai de `self.model.__name__` e não de um nome cravado: desde o
    EVO-40 são DUAS as tabelas append-only desta célula, e um texto fixo faria
    a segunda acusar a primeira.
    """

    def update(self, **kwargs):
        raise RegistroImutavel(
            f"{self.model.__name__} é append-only: update() é proibido. "
            "Correção é um registro NOVO."
        )

    def delete(self):
        raise RegistroImutavel(
            f"{self.model.__name__} é append-only: delete() é proibido."
        )


class RegistroAppendOnly(models.Model):
    """Os dois degraus Python do append-only, para quem precisar deles.

    Existe desde o EVO-40, quando a segunda tabela append-only desta célula
    nasceu (`ChangeSpecAprovado`). Antes disto os dois degraus moravam
    copiados dentro do `HistoricoStatus` — e cópia é o jeito de as duas
    envelhecerem separadas.

    **Os degraus 1 e 2 e nada mais.** O terceiro é o trigger no Postgres, que
    cada migração cria para a SUA tabela: uma classe Python não tem como
    prometer o que só o banco impõe (`armadilhas/079` — o collector do
    `CASCADE` apaga sem passar por nenhum dos dois primeiros).
    """

    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        # `_state.adding` é o único sinal confiável aqui: a chave é
        # `BigAutoField`, então checar `self.pk is None` daria falso-verde em
        # qualquer caminho que atribua o pk antes de gravar.
        if not self._state.adding:
            raise RegistroImutavel(
                f"{type(self).__name__} é append-only: esta linha já existe. "
                "Correção é um registro NOVO."
            )
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RegistroImutavel(
            f"{type(self).__name__} é append-only: delete() é proibido."
        )


class HistoricoStatus(RegistroAppendOnly):
    """Append-only: nenhuma linha é editada ou apagada depois de criada.

    A regra é imposta em **três degraus** (Lei 1 — empurrar a regra escada
    acima até onde ela fisicamente puder ir):

    1. `save()` recusa a segunda gravação da mesma linha;
    2. `AppendOnlyQuerySet` recusa `update()`/`delete()` em massa;
    3. **o Postgres recusa** — trigger `BEFORE UPDATE OR DELETE` criado na
       migration `0001_initial`. É o degrau que sobrevive a `cursor.execute`
       cru, a `psql` e a qualquer código futuro que não conheça esta classe.

    Os degraus 1 e 2 mudaram de casa no EVO-40 (`RegistroAppendOnly`), sem
    mudar de comportamento: a célula ganhou uma SEGUNDA tabela append-only e
    duas cópias do mesmo guarda envelheceriam separadas.

    A FK para `Sugestao` é `PROTECT`, não `CASCADE` como na §6 da spec: com
    `CASCADE`, apagar uma sugestão apagaria o histórico dela por dentro do
    collector do Django, que emite `DELETE` direto e **não** passa por
    `QuerySet.delete()`. A §8 da spec ("nenhuma linha é apagada") vence a §6.
    """

    sugestao = models.ForeignKey(
        Sugestao, related_name="historico", on_delete=models.PROTECT
    )
    status_anterior = models.CharField(
        max_length=20, choices=Sugestao.Status.choices, blank=True
    )
    status_novo = models.CharField(max_length=20, choices=Sugestao.Status.choices)
    nota = models.TextField(blank=True)
    alterado_por = models.ForeignKey(
        "Identidade", related_name="alteracoes_de_status", on_delete=models.PROTECT
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["criado_em", "id"]


class ChangeSpecAprovado(RegistroAppendOnly):
    """O corredor entre a decisão de produto e a implementação (EVO-40).

    Lei: `docs/caixa-de-sugestoes/FORMATO-CHANGESPEC.md` §3/§4/§5 e a última
    linha da §8 da `ESPECIFICACAO-CELULA.md` — *"`Sugestao.status` só sai de
    `PLANEJADO` para `EM_DESENVOLVIMENTO` se existir um ChangeSpec aprovado
    referenciando aquele `suggestion_id`"*.

    **Isto é um REGISTRO, não o documento.** O ChangeSpec de verdade mora em
    `docs/changespecs/`, no repositório, e a célula **não lê o repositório em
    runtime** (decisão do plano mestre). O que fica aqui é o mínimo que a trava
    precisa para existir sem adivinhar: qual sugestão, qual CHANGE-ID, onde
    está o documento, quem aprovou e quando — e, separado disto, quem trouxe
    esse fato para dentro da Caixa.

    **`aprovado_por` e `registrado_por` são coisas diferentes, e as duas
    importam.** O §1 do formato diz que a aprovação é humana e nominal; o
    registro é o ato de trazer essa aprovação para dentro do sistema. Hoje o
    mantenedor decidiu que só quem está em `SUGESTOES_APROVADORES` registra —
    então na prática são a mesma pessoa. O dado guarda os dois porque um dia
    pode não ser, e porque um campo só responderia "quem" a duas perguntas
    diferentes.

    **`aprovado_por` é NOME, nunca e-mail** (`DECISAO-EVO-01` §3: o e-mail vive
    numa linha só, a `Identidade`). Não é combinado: `registrar()` recusa um
    valor com `@`, e há guarda. Uma FK para `Identidade` também não serve — a
    pessoa que assina o documento pode não ter nunca entrado na Caixa.

    **Append-only, e pelo mesmo motivo do `HistoricoStatus`.** O §4 do formato:
    *"depois de aprovado, um ChangeSpec não é editado. Se o escopo mudar, nasce
    `CS-…-v2` com um campo `SUBSTITUI` apontando para o anterior"*. Aqui isso é
    uma linha NOVA, com o `change_id` da v2 — e o `SUBSTITUI` mora no
    documento, que é a autoridade. Guardar a corrente aqui seria a célula
    modelando o que ela decidiu não ler.

    Os três degraus, como no `HistoricoStatus`: `save()` e `AppendOnlyQuerySet`
    de `RegistroAppendOnly`, mais o trigger `BEFORE UPDATE OR DELETE` da
    migration `0004`.
    """

    # `PROTECT` como em toda referência desta célula: a sugestão não some por
    # baixo do corredor que autorizou o desenvolvimento dela.
    sugestao = models.ForeignKey(
        Sugestao, related_name="changespecs", on_delete=models.PROTECT
    )
    # `CS-{celula}-{sequencial}` (formato §3). NÃO é único sozinho: um mesmo
    # ChangeSpec pode referenciar várias sugestões (§2 — "se nasceu de várias
    # sugestões mescladas, referencia todas"). O par é que é único.
    change_id = models.CharField(max_length=60)
    # Onde o documento está: URL ou o caminho dele no repositório. Texto livre
    # com forma conferida em `registrar()` — link que não leva a lugar nenhum é
    # um corredor que ninguém consegue auditar.
    documento = models.CharField(max_length=300)
    aprovado_por = models.CharField(max_length=120)
    aprovado_em = models.DateField()
    registrado_por = models.ForeignKey(
        "Identidade", related_name="changespecs_registrados", on_delete=models.PROTECT
    )
    registrado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-registrado_em", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["sugestao", "change_id"],
                name="changespec_unico_por_sugestao",
            ),
            # O que a trava lê é a EXISTÊNCIA da linha. Estas duas checagens são
            # o que impede a existência de significar menos do que promete: uma
            # linha sem quem aprovou, ou sem para onde apontar, seria um
            # ChangeSpec "aprovado" por ninguém — exatamente o que o §4 do
            # formato chama de não-pronto.
            models.CheckConstraint(
                condition=~models.Q(aprovado_por=""),
                name="changespec_tem_quem_aprovou",
            ),
            models.CheckConstraint(
                condition=~models.Q(documento=""),
                name="changespec_tem_documento",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover - conveniência de admin/shell
        return f"{self.change_id} → sugestão {self.sugestao_id}"


class AvaliacaoInterna(models.Model):
    """Staff-only. Nunca exposta nem editável pelo aluno (spec §8).

    A garantia de que o aluno não a alcança é da camada HTTP (EVO-13) — aqui
    ela só existe separada da `Sugestao`, em tabela própria, para que nenhum
    serializer de aluno possa vazá-la por descuido de campo.
    """

    sugestao = models.OneToOneField(
        Sugestao, related_name="avaliacao", on_delete=models.CASCADE
    )
    impacto_educacional = models.PositiveSmallIntegerField(default=0)
    impacto_comercial = models.PositiveSmallIntegerField(default=0)
    esforco_tecnico = models.PositiveSmallIntegerField(default=0)
    notas = models.TextField(blank=True)
    decisao_produto = models.TextField(blank=True)
    # Nulo = ainda não avaliada. `PROTECT` (e não `SET_NULL`) porque apagar a
    # identidade de quem avaliou não pode transformar a avaliação em anônima
    # em silêncio.
    avaliado_por = models.ForeignKey(
        "Identidade",
        null=True,
        blank=True,
        related_name="avaliacoes",
        on_delete=models.PROTECT,
    )
    atualizado_em = models.DateTimeField(auto_now=True)


class Aviso(models.Model):
    """O sininho: quem interagiu com a ideia fica sabendo que ela andou.

    EVO-21 (o dado, só para o autor) → **EVO-42** (todo mundo que interagiu).

    A `ESPECIFICACAO-CELULA.md` §10 pede *"evento de mudança de status consumido
    por uma notificação in-app simples"*. **In-app, dentro da própria Caixa** —
    o mantenedor descartou em 24/08/2026 o caminho pela `mensageria`: ela precisa
    de um destinatário, e tirar o e-mail do aluno de dentro da Caixa desfaria a
    `DECISAO-EVO-01` §3 ("o e-mail vive numa linha só").

    **Por que colunas próprias, e não uma FK para a linha do `HistoricoStatus`
    que originou o aviso.** As duas tabelas guardam o mesmo fato para leitores
    diferentes, e é essa diferença que decide o desenho:

    * o `HistoricoStatus` é a **auditoria da equipe** — carrega `alterado_por`,
      que é quem moderou;
    * o `Aviso` é a **cópia do aluno** — e a única maneira de garantir que a
      tela dele nunca mostre quem moderou é a linha dele não ter esse dado.

    É a mesma lição que fez a `AvaliacaoInterna` nascer em tabela separada, e é
    a Virtude da Lei 3: *copiar dados — snapshots são sagrados*. `status_novo` e
    `nota` aqui não são espelho de estado mutável; são o retrato do que mudou
    naquele instante, exatamente como a linha do histórico.

    **`nota` é a primeira vez que a justificativa alcança quem sugeriu.** O
    `nao_planejado` exige justificativa desde o EVO-13 (`moderacao.py`) *"porque
    quem sugeriu vai ler"* — só que até aqui não havia nenhuma tela do aluno que
    a mostrasse. É esta.

    **`lido_em` (timestamp) e não `lido` (booleano):** um booleano responde "já
    viu?" e nada mais; o instante responde também "quando", que é o que torna
    `marcar como lido` verificavelmente idempotente — a segunda chamada não pode
    mexer no carimbo da primeira.

    **Quem recebe, desde o EVO-42: todos os que interagiram com a ideia** —
    autor, quem votou e quem comentou, um aviso por pessoa DISTINTA. É a
    `DECISAO-EVO-40-quem-aprova-e-quem-e-avisado.md` §2, e o EVO-21 já a tinha
    previsto: *"são mais linhas, com outro `destinatario`"*. A previsão estava
    certa — a forma não mudou; ganhou uma coluna (`vinculo`, abaixo).

    O contrato congelado do `sugestao.status-alterado` continua **não** levando
    a lista de votantes (lista sem teto dentro de evento), e continua sem
    precisar: o leque é resolvido aqui dentro, na mesma transação.

    **`vinculo`: por que o motivo é COLUNA e não uma derivação na leitura.** A
    tela precisa distinguir "sua ideia" de "ideia em que você votou/comentou" —
    sem isso o aluno recebe recado de coisa que não lembra ter tocado. As duas
    formas foram pesadas:

    * **derivar na leitura** (perguntar ao `Voto`/`Comentario` na hora de
      montar a página) é espelho de estado **mutável**: quem tira o voto
      amanhã vê o aviso de ontem mudar de explicação — ou perdê-la. O recado
      passaria a mentir sobre o passado, e ainda custaria consulta por página;
    * **coluna** é retrato do instante, como `status_novo` e `nota` já são. No
      dia em que a pessoa desvota, o aviso continua dizendo a verdade: *quando
      isto aconteceu, você tinha votado*.

    A segunda ganha porque é a Virtude da Lei 3 aplicada ao mesmo dado — e
    porque a alternativa quebra a regra que esta classe inteira encarna
    (*snapshots são sagrados*). Há guarda: `test_o_vinculo_sobrevive_ao_desvoto`.
    """

    class Vinculo(models.TextChoices):
        """Por que ESTA pessoa está recebendo ESTE aviso.

        A ordem aqui é a de PRECEDÊNCIA de quem acumula papéis (autor que
        também votou e comentou recebe **um** aviso, com o vínculo mais forte).
        Ser o autor vence tudo — a ideia é dela. Ter escrito vence ter votado:
        quem comentou pôs palavra na conversa, quem votou pôs um clique.
        """

        AUTOR = "autor", "Sua ideia"
        COMENTARIO = "comentario", "Ideia em que você comentou"
        VOTO = "voto", "Ideia em que você votou"

    # `PROTECT` nos dois, como em todo o resto da célula: nem a pessoa nem a
    # sugestão somem por baixo de um aviso. Sugestão, aliás, já não é apagada em
    # lugar nenhum — o `PROTECT` do `HistoricoStatus` (EVO-11) garante isso.
    destinatario = models.ForeignKey(
        "Identidade", related_name="avisos", on_delete=models.PROTECT
    )
    sugestao = models.ForeignKey(
        Sugestao, related_name="avisos", on_delete=models.PROTECT
    )
    status_anterior = models.CharField(
        max_length=20, choices=Sugestao.Status.choices, blank=True
    )
    status_novo = models.CharField(max_length=20, choices=Sugestao.Status.choices)
    nota = models.TextField(blank=True)
    # O default é `AUTOR` e ele NÃO é um chute sobre o futuro: é um fato sobre o
    # passado. Até o EVO-42 a única linha que esta tabela sabia escrever era a
    # do autor, então toda linha que já existe em produção É de autor — a
    # migração `0005` não precisa adivinhar nada. Quem escreve daqui em diante
    # passa por `avisar_os_interessados()`, que informa o vínculo sempre, e há
    # guarda medindo isso pelos três papéis.
    vinculo = models.CharField(
        max_length=20, choices=Vinculo.choices, default=Vinculo.AUTOR
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    # Nulo = não lido. O índice é sobre o par, porque a pergunta que a Caixa faz
    # a cada página é sempre a mesma: "quantos NÃO lidos desta pessoa?".
    lido_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-criado_em", "-id"]
        indexes = [models.Index(fields=["destinatario", "lido_em"])]

    def __str__(self) -> str:  # pragma: no cover - conveniência de admin/shell
        return f"aviso de {self.sugestao_id} para {self.destinatario_id}"


class OutboxEvent(models.Model):  # [RECEITA:R3 v1]
    """Uma linha por fato que a Caixa afirma ao resto da plataforma (EVO-20).

    Mora AQUI, e não num app `eventos` à parte, pela mesma decisão de orçamento
    que `pagamentos` tomou: `apps/sugestoes` é o único app desta célula com
    `models.py` + `migrations/`, e um app novo custaria outro
    `migrations/__init__.py` sem ganho arquitetural nenhum.

    `payload` guarda **só o campo `data`** do envelope. O envelope inteiro
    (`event`/`version`/`event_id`/`occurred_at`/`data`) é montado pelo relay,
    no instante da publicação — guardar o envelope pronto duplicaria em JSON o
    que já são colunas, e as duas cópias envelheceriam separadas.

    `event_id` é `UUIDField` **de propósito**, e é a única exceção ao guarda
    `test_os_ids_inter_celula_sao_texto_opaco_e_nao_uuid`: os quatro contratos
    congelados em `contracts/eventos/sugestao.*.v1.json` pedem
    `"format": "uuid"` neste campo — como TODO evento desta plataforma. A
    exceção não é afrouxamento; é o guarda deixando de valer onde o contrato
    diz o contrário, e o próprio guarda confere isso lendo o contrato.
    """

    event_id = models.UUIDField(default=uuid.uuid4, unique=True)
    event = models.CharField(max_length=100)  # ex.: "sugestao.criada"
    version = models.PositiveSmallIntegerField(default=1)
    payload = models.JSONField()  # SÓ o campo `data` do envelope
    occurred_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)
    # As chaves que este evento acrescenta ao ENVELOPE (o nível de cima), e não
    # ao `data`. Nasceu com o `ator_id` do Rito de Contrato de 26/08/2026, que
    # de propósito mora no envelope: qualquer célula lê "quem fez isto" sem
    # conhecer o formato do assunto (DECISAO-fase-2-do-sininho §4).
    #
    # POR QUE UM CAMPO GENÉRICO E NÃO UMA COLUNA `ator_id`. O relay monta o
    # envelope para TODOS os eventos, e os contratos são `additionalProperties:
    # false` no topo. Uma coluna `ator_id` obrigaria o relay a decidir, evento a
    # evento, se inclui a chave — e essa decisão seria uma SEGUNDA verdade sobre
    # os contratos, morando em código. Com este campo, quem emite (que conhece o
    # próprio contrato) declara o que vai no envelope, e o relay continua burro.
    #
    # `{}` nos eventos antigos ⇒ envelope byte-idêntico ao de antes. E note que
    # `{"ator_id": None}` é DIFERENTE de `{}`: a carta declara `ator_id` nulável
    # (fato de máquina não tem gente), então a chave presente com valor nulo é
    # informação, não ausência.
    envelope_extra = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [models.Index(fields=["published_at"])]

    def __str__(self) -> str:  # pragma: no cover - conveniência de admin/shell
        return f"{self.event}:{self.event_id}"
