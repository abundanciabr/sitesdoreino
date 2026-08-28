"""A auditoria da área administrativa — append-only, com trigger no banco.

**Por que ela existe, e por que AGORA:** `DECISAO-celula-admin.md` §3 exige que
toda escrita feita por esta área deixe rastro, e o `LICOES.md` da célula fixou o
momento — *"a auditoria entra no MESMO PR que a primeira escrita, ou num PR
imediatamente anterior a ela; nunca depois"*. Este PR traz a primeira escrita
(liberar e recusar quem está na fila), então ela entra aqui.

**O que esta tabela NÃO é, e a distinção decide o desenho.** Ela não é uma
segunda fonte de "quem é aluno" — esse fato mora na `alunos`, que já grava
`decidido_em`, `decidido_por` e `motivo_recusa` na própria matrícula. Duplicar
aquilo aqui criaria duas listas respondendo à mesma pergunta, que é a doença
que o `CLAUDE.md` proíbe.

O que ela guarda é outra coisa, que nada mais responde: **o que foi feito
ATRAVÉS desta área, por quem, e o que aconteceu** — inclusive as tentativas que
FALHARAM. Uma decisão que a `alunos` recusou não deixa rastro nenhum lá (não há
linha para carimbar), e é justamente esse caso que alguém vai querer reconstruir
quando um aluno disser "eu fui liberado e continuo sem acesso".

**Append-only com MECANISMO, não com disciplina** (`armadilhas/079`): o
`save()` sobrescrito é contornado por `QuerySet.update()`, por `psql` e por
qualquer código que não importe esta classe. Quem impede de verdade é o trigger
da migration `0001` — as três metades (UPDATE, DELETE e TRUNCATE) fechadas no
banco.
"""

from django.db import models


class Registro(models.Model):
    """Uma linha por AÇÃO tentada nesta área. Nunca editada, nunca apagada."""

    LIBERAR = "liberar"
    RECUSAR = "recusar"
    # [GESTAO] Mudar o estado de quem JÁ é aluno, ou corrigir os dados dele.
    # Verbo próprio, e não um `liberar` reaproveitado: quem for ler esta tabela
    # daqui a meses precisa distinguir "deixei entrar" de "mexi no cadastro".
    EDITAR = "editar"
    ACOES = [(LIBERAR, "liberar"), (RECUSAR, "recusar"), (EDITAR, "editar")]

    OK = "ok"
    RECUSADO_PELA_CELULA = "recusado"
    NAO_RESPONDEU = "nao_respondeu"
    DESFECHOS = [
        (OK, "ok"),
        (RECUSADO_PELA_CELULA, "recusado pela célula dona"),
        (NAO_RESPONDEU, "não respondeu"),
    ]

    quando = models.DateTimeField(auto_now_add=True)

    # QUEM: o e-mail é o identificador que o mantenedor consegue reconhecer numa
    # auditoria — e ele já é a chave de autorização desta célula
    # (`ADMIN_EMAILS`), então guardá-lo aqui não amplia o alcance do dado. O id
    # opaco vem junto porque e-mail pode mudar de dono numa organização; o id,
    # não.
    quem_email = models.EmailField()
    quem_id = models.CharField(max_length=64, blank=True, default="")

    acao = models.CharField(max_length=20, choices=ACOES)

    # SOBRE O QUÊ. `alvo` é o id da linha na `alunos` — um identificador opaco
    # de OUTRA célula, guardado como texto de propósito: não é chave estrangeira
    # e não pode virar uma (Lei 3), e o dia em que aquela linha for embora esta
    # continua contando o que aconteceu.
    alvo = models.CharField(max_length=64)
    # Sem PII do aluno: nem nome, nem telefone. Para saber de quem se trata,
    # cruza-se o `alvo` com a `alunos` — que é onde esse dado mora, e é ela
    # quem decide quem pode vê-lo (lei da fila §5).

    desfecho = models.CharField(max_length=20, choices=DESFECHOS)
    # O motivo da recusa é TEXTO DE PESSOA e faz parte do que foi feito: sem
    # ele, a linha diz "recusou" e não diz o que a pessoa recusada leu.
    detalhe = models.TextField(blank=True, default="")

    class Meta:
        indexes = [models.Index(fields=["-quando"])]

    def __str__(self) -> str:  # pragma: no cover - conveniência de shell
        return f"{self.quando:%Y-%m-%d %H:%M} {self.quem_email} {self.acao} {self.alvo}"
