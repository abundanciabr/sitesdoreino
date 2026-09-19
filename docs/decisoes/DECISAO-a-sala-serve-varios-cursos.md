publico-para-ia: true

# DECISÃO: a sala de aula serve vários cursos, e criar um curso é gesto do Admin

**Data:** 7 de setembro de 2026
**Quem decidiu:** o mantenedor, em pergunta estruturada, na sessão que mediu o que
faltava para o curso "Primeiros Dólares com Roblox" funcionar.

## §1 A regra, em uma frase

**A sala de aula serve quantos cursos a escola vender.** Um curso nasce na tela do
Admin, com o seu produto, a sua regra de avanço e a sua lista de módulos e aulas.
O conteúdo de cada aula continua entrando pelo editor, e só por ele.

## §2 As três respostas dele, que são a assinatura desta lei

A pergunta nasceu de uma medição: em 7 de setembro de 2026 a sala conhecia UM
curso (o do livro, apelido `profissional`), e os 132 alunos matriculados no
"Primeiros Dólares com Roblox" recebiam, ao abrir a sala, a tela "Este curso não
é o seu". Nada na fila construía a sala deles. Ele respondeu:

| Pergunta | Resposta dele |
|---|---|
| O que os 132 alunos do curso 1 devem ver na sala? | *"quero criar uma estrutura que sirva para vários cursos e não apenas para um único curso, de modo que seja fácil de criar outros cursos depois"* |
| No curso 1, como o aluno passa de uma aula para a próxima? | **Livre: a próxima abre ao terminar a anterior**, sabendo que isso exige uma exceção, assinada por ele, à regra do laudo, valendo só para o curso que a pedir |
| Onde estão os vídeos do curso 1? | **No YouTube, não listados** |

A primeira resposta não era uma das opções oferecidas. É a que manda: o pedido
não é "uma sala para o curso 1", é **uma sala que serve N cursos**, e o curso 1 é
o primeiro a passar por ela.

## §3 O que muda na lei que já existia

1. **"Um curso por site no lançamento"** (`PLANO-CELULA-CURSOS.md` §4) deixa de
   valer. A célula `cursos` passa a guardar vários cursos por site, resolvidos
   sempre pelo par site + apelido, como o endereço já faz desde 6 de setembro.
2. **[INV-CUR-P2] "A porta só abre por laudo" ganha uma segunda regra, por
   curso.** Cada curso declara a sua `progressao`: `por_laudo` (o padrão, e a
   regra do livro: a próxima aula abre com o laudo da professora) ou `livre` (a
   próxima aula abre quando o próprio aluno conclui a anterior, com as pausas
   registradas). O núcleo do invariante não muda: **em nenhum dos dois a porta
   abre por data, por XP ou por pagamento**, e a função de cada regra recusa o
   curso da outra. Quem escolhe a regra é o mantenedor, no cadastro do curso.
   Esta é a exceção que ele assinou na segunda resposta; o critério de morte 10
   do plano ("qualquer invariante do §9 precisar de exceção") foi cumprido:
   parou-se, e a decisão foi reaberta com ele.
3. **A estrutura de um curso (partes, blocos e aulas) vira dado que entra pela
   porta de máquina**, e não só pelo semeador do livro. O semeador continua
   sendo a fonte da estrutura do `profissional`, porque ela é fato público do
   livro; os outros cursos recebem a estrutura pela tela. O texto das aulas
   continua fora de arquivo e de migração ([INV-CUR-C2] intacto).
4. **Os números de aula deixam de ser só E00..E32 e EB.** O padrão passa a ser
   de 1 a 3 letras ou dígitos, único por curso; os blocos vão de A a Z; as três
   partes continuam sendo o vocabulário do contrato. O livro cabe na regra nova
   sem mudar uma vírgula.
5. **Cadastrar um produto também vira gesto da porta do catálogo**, porque um
   curso é um produto (lei de 6 de setembro) e "fácil de criar" não combina com
   bloco de colar no servidor a cada curso novo.

## §4 O que o mantenedor vê, do começo ao fim

1. Em `/admin/escola/cursos/`: a lista dos cursos da sala, e o botão **Novo
   curso**: nome, apelido, produto (um que já existe no catálogo, ou "criar um
   produto novo com este nome") e a regra de avanço, sem valor já marcado.
2. Em `/admin/escola/<curso>/estrutura/`: cola a lista de módulos e aulas num
   texto simples, aperta **Prever**, lê, aperta **Importar**.
3. Em `/admin/escola/<curso>/aulas/`: o editor que já existe, aula por aula: o
   link do vídeo do YouTube, o texto, publicar.
4. Do lado do aluno: `/cursos/` mostra os cursos DELE (um abre direto; dois
   pedem escolha), o mapa das aulas, a aula com o vídeo embutido, e, no curso
   livre, o botão **Concluir esta aula**, que abre a próxima na hora.

Para o curso 1 não há passo no servidor: o produto "Primeiros Dólares com
Roblox" já existe no catálogo desde 7 de setembro, e as 132 matrículas já
apontam para ele. Ele cria o curso na tela, escolhe esse produto, cola as aulas
e cola os links.

## §5 A escada

Cada degrau é uma tarefa na fila, e o estado se lê no balcão
(`python ci/fila.py listar --ao-vivo`), nunca aqui.

| Tarefa | Célula | O quê | Depende de |
|---|---|---|---|
| TAR-266 | cursos | a porta ganha `listCourses`, `createCourse`, `putCourse` e `putCourseStructure`; `Curso.progressao`; restrições relaxadas | nada |
| TAR-267 | catalogo | a porta ganha `createProduct` | nada |
| TAR-268 | contracts | Rito de Contrato da sala, pela maestro | TAR-266 |
| TAR-269 | contracts | Rito de Contrato do catálogo, pela maestro | TAR-267 |
| TAR-270 | cursos | a progressão livre: o gesto de concluir, a tela, o mapa, o [INV-CUR-P2] emendado | TAR-266 |
| TAR-271 | admin | a lista de cursos e o botão Novo curso; o editor entra por qualquer curso | TAR-268, TAR-269 |
| TAR-272 | admin | a tela de colar a estrutura | TAR-268, TAR-271 |

TAR-266 e TAR-267 correm em paralelo, cada uma na sua célula. Os dois Ritos
são da maestro, com o contrato nascido do export do ramo de cada porta, nunca
de cabeça, e cada PR de porta pousa depois do seu Rito (o precedente é o par
#1135 e #1136). TAR-270 corre na `cursos` depois da TAR-266. TAR-271 e TAR-272
correm em série na `admin`.

## §6 O que fica decidido e não se reabre por preferência de agente

- O curso do livro continua por laudo. Nada do caminho do laudo muda.
- A regra de avanço é dado do curso, escolhida no cadastro, sem valor padrão
  marcado na tela. Não existe terceira regra sem decisão nova dele.
- O conteúdo entra pela tela do Admin, pela porta de máquina, nunca por
  arquivo commitado nem por migração com texto ([INV-CUR-C2]).
- Os vídeos entram por link; YouTube e Vimeo embutem na aula, o resto aparece
  como link. A "pausa real" continua sendo o registro do aluno no minuto
  marcado, sem controlar o tocador.
- XP, medalha e Marco continuam da `gamificacao`; a regra de pontos por aula
  concluída continua desligada até ele ligar.
- Pagamento continua por último (diretiva de 22 de agosto): a entrada dos
  alunos de hoje é a liberação, e ela já pede o produto.

## §7 Critério de morte

Pare e reabra com o mantenedor se: uma porta de curso livre passar a depender
de data, XP ou pagamento; nascer uma terceira regra de avanço sem decisão dele;
a estrutura de um curso entrar por arquivo commitado; ou o texto de uma aula
aparecer em migração.

## Estado

| O quê | Estado | Onde se confere |
|---|---|---|
| Esta lei | decidida em 7 de setembro de 2026 | o registro no livro, o PR desta página |
| As sete tarefas | criadas na fila no mesmo PR | `python ci/fila.py listar --ao-vivo` |
| O curso 1 na sala | espera TAR-271 e TAR-272 no ar, e o gesto dele na tela | `/admin/escola/cursos/` |
