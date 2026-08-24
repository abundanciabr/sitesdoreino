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

O que **não** mora aqui, de propósito: endpoint (EVO-12), fluxo de login
(EVO-01 decidiu o desenho; o fluxo é despacho próprio) e outbox/eventos
(Lote 2, EVO-20). Esta camada só guarda fatos.
"""

import secrets

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


class Identidade(models.Model):
    """Quem é a pessoa, para esta célula — cunhada na primeira entrada.

    Lei do assunto: `DECISAO-EVO-01-identidade.md`. O Google prova QUEM É; a
    célula `alunos` decide SE PODE. A `sugestoes` nunca recebe ator pronto de
    ninguém e nunca lê o banco de `alunos`.

    **O e-mail vive AQUI e em nenhum outro lugar.** Sugestão, voto e
    comentário apontam para esta linha; nenhum deles guarda e-mail. É dado
    pessoal: uma pessoa que troque de endereço é uma linha editada, não um
    histórico reescrito.
    """

    id = models.CharField(
        primary_key=True, max_length=64, default=cunhar_id, editable=False
    )
    # `unique` no e-mail (e não no par com `provedor`): a mesma pessoa entrando
    # amanhã por outro provedor — um código, por exemplo — precisa RECUPERAR
    # esta identidade, não cunhar uma segunda (EVO-01 §3).
    email = models.EmailField(unique=True)
    provedor = models.CharField(max_length=20, default="google")
    nome_exibido = models.CharField(max_length=120, blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:  # pragma: no cover - conveniência de admin/shell
        return self.nome_exibido or self.email


class Quadro(models.Model):
    """A fronteira de contexto: toda sugestão pertence a exatamente um quadro.

    Spec §5. `produto_id` nulo = quadro da plataforma inteira. É a única
    coluna de texto desta célula que aceita NULL, e de propósito: aqui "vazio"
    e "todos os produtos" são estados DIFERENTES, e string vazia os
    confundiria.
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

    class Meta:
        indexes = [models.Index(fields=["quadro", "status"])]

    def __str__(self) -> str:  # pragma: no cover
        return self.titulo


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
    """

    def update(self, **kwargs):
        raise RegistroImutavel(
            "HistoricoStatus é append-only: update() é proibido. "
            "Correção de histórico é um registro NOVO."
        )

    def delete(self):
        raise RegistroImutavel("HistoricoStatus é append-only: delete() é proibido.")


class HistoricoStatus(models.Model):
    """Append-only: nenhuma linha é editada ou apagada depois de criada.

    A regra é imposta em **três degraus** (Lei 1 — empurrar a regra escada
    acima até onde ela fisicamente puder ir):

    1. `save()` recusa a segunda gravação da mesma linha;
    2. `AppendOnlyQuerySet` recusa `update()`/`delete()` em massa;
    3. **o Postgres recusa** — trigger `BEFORE UPDATE OR DELETE` criado na
       migration `0001_initial`. É o degrau que sobrevive a `cursor.execute`
       cru, a `psql` e a qualquer código futuro que não conheça esta classe.

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

    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        ordering = ["criado_em", "id"]

    def save(self, *args, **kwargs):
        # `_state.adding` é o único sinal confiável aqui: a chave é
        # `BigAutoField`, então checar `self.pk is None` daria falso-verde em
        # qualquer caminho que atribua o pk antes de gravar.
        if not self._state.adding:
            raise RegistroImutavel(
                "HistoricoStatus é append-only: esta linha já existe. "
                "Correção de histórico é um registro NOVO."
            )
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RegistroImutavel("HistoricoStatus é append-only: delete() é proibido.")


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
