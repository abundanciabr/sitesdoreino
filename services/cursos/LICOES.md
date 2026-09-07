# LICOES — célula cursos

Específico desta célula. Transversal vai em `armadilhas/` (raiz).

## A sala pergunta MATRÍCULAS, não categoria, e o 404 mudou de significado

**Contexto.** Até 06/09/2026 `apps/core/sessao.py` chamava
`AlunosClient.categoria_de(email)` e guardava um booleano `eh_aluno`. Com um curso
só isso funcionava por coincidência: "é aluno" era resposta suficiente porque só
havia uma sala. Com o segundo curso no ar, a pergunta certa passou a ser **de
qual curso**, e a porta mudou para `listEnrollments`
(`GET /alunos/{email}/matriculas`), que devolve `product_id` por matrícula.

**A armadilha que isso trouxe, e ela é da célula.** As duas operações dão
significados OPOSTOS ao mesmo 404, e as duas estão certas:

| operação | 404 significa |
|---|---|
| `getStudentStanding` (a antiga) | **não existe** — a porta responde `200 cadastrado` para quem não conhece |
| `listEnrollments` (a nova) | **resposta legítima** — "esta pessoa não tem matrícula nenhuma" |

Manter o `except` antigo trataria "não tem matrícula" como "não consegui
perguntar". Nesta célula, que é fail-closed por lei (`sessao.py`: não conseguir
conferir a matrícula NUNCA é "pode entrar"), isso fecharia a sala para quem tem
direito de entrar, em silêncio. A sabotagem que trata o 404 como falha derruba 5
testes, todos na frase da recusa.

**Decisão:** `AlunosClient.matriculas_de` classifica 404 como **lista vazia**, e
só erro de transporte vira `AlunosIndisponivel`. Os dois casos têm teste próprio,
e a régua para quem trocar de operação de novo está em `armadilhas/370`.

## O elo `Curso` ↔ produto é campo explícito, nunca o apelido

**Medido em 06/09/2026:** `Matricula.product_id` guarda o **UUID** do `Product` do
catálogo, e `Curso.slug` é o apelido que aparece no endereço
(`/cursos/profissional/`). **Nunca são o mesmo valor**, mesmo quando o apelido do
produto e o do curso coincidem — e eles coincidem hoje, o que torna o engano
fácil e caro.

Confiar no apelido exigiria perguntar ao catálogo a cada requisição, por uma
operação que o contrato congelado não tem. Por isso `Curso.produto_id` é campo, e
quem o preenche é o comando `apontar_o_produto_do_curso`: apontar o produto é ato
de instalação (uma vez por curso), e pôr isso na porta de máquina custaria um
Rito de Contrato para um gesto que ninguém repete.

**Curso sem produto apontado FECHA**, e a ausência é a decisão: curso fechado é
problema visível e recuperável com um comando; curso aberto por falta de
apontamento é o defeito invisível que a mudança inteira existe para matar.

## Migração desta célula não roda código

`test_nenhuma_migracao_desta_celula_roda_codigo` proíbe `RunPython` aqui.
Migração de esquema, sim; migração de dados, não. Quando um campo novo precisa
ser preenchido em linhas que já existem, o caminho é comando de gestão ou o
semeador — e o motivo é que o valor a gravar quase nunca é conhecível na hora de
escrever o código (o `product_id` é um UUID sorteado, diferente em cada
ambiente).

## Reordenar linhas com posição única: a aula estaciona, o bloco adia

**Medido em 07/09/2026, na TAR-266.** `putCourseStructure` reordena blocos e
aulas em lugar, e as duas tabelas têm `Unique(curso, ordem)`. Trocar dois de
posição (A vai para 2, B vai para 1) colide na PRIMEIRA gravação quando o banco
confere linha a linha: a suíte acusa `IntegrityError` em
`uma_ordem_por_aula_por_curso` no meio da transação, e nada do que vem depois
importa.

Há duas saídas, e cada tabela desta célula usa a que a faixa dela permite:

| tabela | faixa da ordem | saída |
|---|---|---|
| `Aula` | aberta (0..32767) | **estacionar**: todas sobem para acima do maior valor que a estrutura nova vai usar (`update(ordem=F("ordem") + deslocamento)`), e cada uma desce para a posição final; nenhuma gravação encontra outra linha na posição |
| `Bloco` | fechada (1..26) | **adiar**: `UniqueConstraint(..., deferrable=DEFERRED)`, e o banco confere no `COMMIT` |

**Por que não adiar as duas:** o semeador do livro e
`test_o_esqueleto_entra_inteiro_ou_nao_entra` dependem de a colisão da AULA
estourar NA LINHA, dentro de `call_command`; adiada, ela só apareceria no
`COMMIT`, que um teste nunca dá, e a prova da transação única viraria verde de
mentira (`armadilhas/358`). **Por que não estacionar as duas:** a ordem do
bloco não tem valor legal fora de 1..26, e com 26 blocos usados não sobra vaga.

Quem prova a recusa de uma restrição adiada força a conferência com
`connection.check_constraints()` dentro do `pytest.raises`
(`test_uma_ordem_por_bloco_por_curso`): sem isso o teste passa sabotado.

## O `max_length` da coluna não é o guarda, e o teste não pode medi-lo

`Aula.numero` tem `max_length=3` e `Bloco.letra` tem `max_length=1`. Um caso de
teste com `"1234"` ou `"AA"` reprova com `DataError: value too long`, ANTES de a
`CheckConstraint` ser avaliada, e o `pytest.raises(IntegrityError, match=...)`
fica vermelho pelo motivo errado (`armadilhas/226`). Os casos que provam a
restrição são os que CABEM na coluna e violam a regra (`"e00"`, `"E-1"`,
`"A 1"`, `""`); o tamanho é recusado com 422 pela porta, pelo `pattern` do
corpo, que é onde ele deve ser recusado.
