# LICOES — célula cursos

Específico desta célula. Transversal vai em `armadilhas/` (raiz).

## O endereço de aula é escolhido pelo banco, não pela prévia do editor

**Medido em 11/09/2026, na edição das aulas avulsas.** A prévia do Admin pode
normalizar o título para um endereço legível, mas duas edições podem pedir o
mesmo valor antes de qualquer uma gravar. Consultar os endereços ocupados não
fecha essa janela.

O banco é a autoridade pela restrição `uma_aula_avulsa_por_slug_por_site`. A
porta calcula o menor sufixo livre, grava numa transação e, se a restrição
recusar uma disputa, consulta e tenta de novo. A prova usa duas conexões reais
do PostgreSQL paradas na mesma candidata: uma recebe `aula-disputada`, a outra
recebe `aula-disputada-2`. Tirar a repetição após `IntegrityError` derruba o
teste.

## O prefixo público mora no `reverse`, nunca no endereço digitado

**Medido em 11/09/2026, na edição das aulas avulsas.** As rotas da biblioteca
existem no urlconf como `aulas/<slug>`, mas a célula publica sob
`SCRIPT_NAME=/cursos`. Um link montado como `/aulas/<slug>` ignora esse prefixo
e a borda responde 404, embora a aula exista no banco. O caminho público é
`reverse("aula-avulsa", args=[slug])`, que produz
`/cursos/aulas/<slug>` quando o prefixo está configurado.

O teste da página sob `SCRIPT_NAME` precisa afirmar os dois lados: o endereço
revertido carrega `/cursos`, e o urlconf resolve o `path_info` sem esse trecho.
Escrever `/cursos` dentro de `urls.py` resolveria somente hoje e quebraria a
próxima mudança de montagem.

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

## A conferência que decide apagar mora dentro da transação que apaga, e tranca a linha

**Medido em 07/09/2026, na revisão do PR #1349.** A primeira versão de
`putCourseStructure` conferia o rastro de aluno (progresso, envio, registro de
pausa) das aulas que sumiram ANTES de abrir o `transaction.atomic()`. Entre o
SELECT e o DELETE havia uma janela, e um aluno começando a aula nessa janela
matava a porta em 500 (`ProtectedError`), nunca em 422.

O conserto é a conferência DENTRO do `atomic()`, com `select_for_update()` nas
aulas candidatas. O que a tranca compra não é o óbvio, e vale saber antes de
escrever o teste: **as chaves estrangeiras que o Django cria no Postgres são
`DEFERRABLE INITIALLY DEFERRED`**, então o INSERT do rastro NÃO segura a linha
da aula; só o COMMIT do aluno pede `FOR KEY SHARE` nela. Com a aula trancada
pela porta, o COMMIT do aluno espera a porta terminar, e o banco recusa o rastro
que apontaria para aula apagada. Um INSERT aberto do aluno não bloqueia a porta,
e um teste que espera isso reprova pelo motivo errado (aconteceu aqui).

**A prova honesta** (`test_enquanto_a_porta_tranca_as_aulas_o_rastro_do_aluno_espera`)
usa uma segunda conexão de verdade (`connections.create_connection("default")`,
porque apelido novo em `connections` é proibido pela classe de teste), pausa a
porta logo depois do `FOR UPDATE` com `connection.execute_wrapper`, e mede que o
COMMIT do aluno fica esperando. Duas sabotagens a derrubam: tirar o
`select_for_update()` (a pausa nunca acontece) e pôr a conferência numa
transação própria antes da que grava (a porta morre em `ProtectedError`).

**Duas condições do teste:** `@pytest.mark.django_db(transaction=True)`, porque
a segunda conexão só vê o que foi commitado; e `select_for_update()` não aceita
`.distinct()` nem os `LEFT JOIN` da conferência, então tranque as candidatas
numa consulta simples e confira o rastro por `pk__in` numa segunda.

## O nome do bloco é estrutura, o título da aula é obra

**Decisão da maestro em 07/09/2026, na mesma revisão.** As aulas casam pelo
NÚMERO, que é estável, e por isso `titulo_exibido` só preenche onde está vazio.
Os blocos casam pela LETRA, que é posicional: nasce um bloco na frente e o B
vira C. Com a regra "só preenche onde está vazio" para o nome do bloco, o bloco
que mudava de letra era apagado com o nome que a pessoa escreveu e o novo
nascia vazio, em silêncio.

Regra desde o PR #1349: em `BlocoDaEstruturaSchema`, `nome` e `boss_titulo` são
`str | None = None`. **Nulo ou ausente não mexe; texto grava; texto vazio
apaga.** A tela de colar traz os nomes nas linhas de módulo e manda o que
mostra, então nenhum bloco perde o nome ao mudar de letra. A prosa da porta e
dos dois campos diz exatamente isso, porque ela vira pedra no contrato
(`armadilhas/324`).

## O catálogo mostra todos os cursos, a porta decide quem entra

**Medido em 07/09/2026:** a raiz da célula (`/cursos/`) respondia 301 para o
mapa do único curso do site, e o aluno cuja matrícula é de um produto sem
`Curso` neste site era levado ao curso do livro sem pedir, sem tela que dissesse
por quê. O mantenedor mandou a raiz virar o catálogo (`apps/core/views.py::
catalogo`, `tests/test_catalogo_de_cursos.py`).

**A regra:** o catálogo lista TODOS os `Curso` do site (`enderecos.cursos_do_site`)
e nunca esconde um cartão; quem decide quem entra continua sendo a porta
(`_recusa_de_curso`), e o cartão só repete a decisão dela para não convidar para
uma porta que vai fechar. Esconder o curso alheio pareceria "esse curso não
existe"; oferecê-lo terminaria em 403. Mostrar sem botão, com a frase, é o meio.

**O que fica:** o 301 do endereço antigo de AULA (`/E00`, TAR-216) continua, e
`_curso_unico` existe só para ele. Só o 301 da raiz morreu.

## O teste dos Bosses parte dos títulos reais, não da lista que ele fiscaliza

**Medido em 10/09/2026, após o deploy do PR #1454 falhar.** O comando procurava
`Modificador Bevel e Triangulate`, enquanto a aula 31 se chamava `Comando Bevel
e Triangulate`. O teste importava `BOSSES_POR_MODULO` do próprio comando para
criar as aulas e, por isso, fabricava uma base que repetia o erro e ficava verde.

O guarda desta célula mantém uma fixture literal dos oito títulos conferidos na
tela administrativa. Assim, mudar a lista do comando sem corresponder ao curso
real reprova. A mesma prova roda o comando duas vezes e cria uma duplicata com
caixa e pontuação diferentes, para preservar idempotência, normalização e recusa
de ambiguidade sem gravação.
