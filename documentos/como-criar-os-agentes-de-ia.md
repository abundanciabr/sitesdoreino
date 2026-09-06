---
titulo: Os documentos do Meshcraft, lidos contra o que existe
publico: false
ordem: 23
---

# Os documentos do Meshcraft, lidos contra o que existe

Cada documento do projeto Meshcraft, lido inteiro e comparado com o código que está no ar. O que já existe, o que foi superado, e o que ainda não tem dono.

> Esta página **cresce**. O mantenedor traz os documentos aos poucos, e cada um ganha uma seção nova aqui, com a mesma forma: o que ele propõe, o que disso já está construído, e o que foi superado por uma decisão posterior. O placar abaixo é o resumo de todos.
>
> Os documentos originais moram fora deste repositório, em `sitesdoreino-docs/agentes-de-ia/`, porque são obra não lançada. Cada afirmação sobre o que já existe foi conferida no código, não na memória.

## O placar

| # | Documento | Lido em | O veredito, em uma linha |
|---|---|---|---|
| 1 | Como começar a criar os agentes | 6 set 2026 | O método vale inteiro; **um dos sete agentes já está no ar** |
| 2 | Antes de como começar (onde entra no site) | 6 set 2026 | Superado em dois pontos, e acertou em cheio no terceiro |
| 3 | Ajustar o que foi escrito ao que já existe | 6 set 2026 | **É o documento que fez o ajuste**: de 8 lotes, 6 já tinham dono |
| 4 a 10 | *a chegar* | | |

---

# O método, que é comum a todos

## A resposta em uma frase

Um agente é **uma Ficha de oito campos** que faz **uma coisa só**, lê **só o que a tarefa manda**, e entrega sempre terminando com o mesmo bloco: o que produzi, o que faltou, o que precisa ser conferido, de onde tirei, e o que a pessoa faz com isto. Ele nunca decide, nunca publica, e nunca pergunta no meio do trabalho.

É o mesmo desenho que o livro ensina na Encomenda 28, a Ficha de Delegação. O método aplica ao robô a regra que o curso ensina para delegar a gente, e essa simetria não é enfeite: é o que o torna explicável para quem vai usá-lo.

## Os oito campos da Ficha

| # | Campo | O que responde |
|---|---|---|
| 1 | O item | o que você faz, em uma frase, e o que você **não** faz |
| 2 | As referências | exatamente quais documentos você lê, e nada além |
| 3 | O degrau | seu nível de autonomia: A (autônomo), P (propõe), H (só prepara) |
| 4 | Os limites | as regras que você nunca quebra |
| 5 | A rubrica | como a sua saída vai ser avaliada, em critérios mensuráveis |
| 6 | O prazo e o checkpoint | o formato, o prazo, e a autoconferência antes de entregar |
| 7 | O valor | o orçamento de chamadas e de dinheiro |
| 8 | Em caso de dúvida | marcar e entregar, nunca perguntar no meio |

O que essa estrutura garante, e é a parte inteligente: **quando o agente erra, o erro é rastreável ao campo que faltava**. Não se corrige a saída; corrige-se a Ficha. Se ele erra três vezes do mesmo jeito, o problema é o campo 4.

## Os quatro limites que valem para todos

1. **Não inventa.** Todo campo cita a origem: arquivo, seção, trecho copiado, nunca parafraseado.
2. **Não preenche por dedução.** O que falta vira `[LACUNA]`; a escolha entre dois sentidos vira `[VERIFICAR]`.
3. **Não amolece regra.** "Nunca", "sempre", "não existe" continuam como estão.
4. **Não decide, não publica, não compara pessoas.**

## O bloco final, que é onde o método vira operação

Toda entrega termina com cinco linhas: **RESUMO · LACUNAS · A VERIFICAR · ORIGENS · PARA A PESSOA**. A última é a mais importante do método inteiro, porque nenhuma saída chega sem dizer o que uma pessoa faz com ela.

---

# Documento 1: Como começar a criar os agentes

## As três coisas exigidas antes do primeiro agente

| O documento pede | Aqui é | Estado |
|---|---|---|
| **O cofre**: uma pasta versionada com os documentos-fonte | A **Biblioteca do Livro**, em `/admin/livro/`, no banco | Construída |
| **Ficha + esquema + teste de aceitação** por agente | A Ficha é o prompt; o esquema é o contrato congelado; o teste é a prova por sabotagem que esta casa exige de todo guarda | Construído |
| **Nada vai ao público sem uma pessoa** | Invariante com fiscal automático: a IA não tem nem campo onde guardar uma decisão | Construído e provado |

**A diferença do cofre merece explicação**, porque é a única exigência cumprida de um jeito diferente do imaginado. O documento supõe uma pasta no Git com todos os capítulos dentro. Este repositório é **público**. O texto do livro é obra não lançada, e por isso o cofre é o banco de dados, alcançado pela tela, e nunca um arquivo commitado.

## Os sete agentes, e onde cada um está

| # | Agente | O que faz | Estado aqui |
|---|---|---|---|
| 1 | **Extrator** | lê um documento-fonte e o decompõe em dados, citando a origem | É a tela de colar o sumário. **Registrado, não construído** |
| 2 | **Revisor de coerência** | confere remissões, nomes canônicos e números repetidos | Vira **código**, não IA. **Não construído** |
| 3 | **Guardião de fidelidade** | compara um derivado com a fonte e aponta onde o sentido mudou | O segundo agente de IA. **Não construído** |
| 4 | **Historiador** | registra tudo o que aconteceu | **Dissolvido**: já é o livro de ocorrências do painel |
| 5 | **Gerador de derivados** | produz o Cartão de 1 página e o quiz a partir do capítulo | **Não construído** |
| 6 | **Plantador de arquivos** | produz os arquivos de prática do Blender | **Não é software**: é trabalho de modelagem |
| 7 | **Assistente de laudo** | pré-preenche a avaliação de uma entrega, para a professora assinar | **No ar**, com a Ficha de oito campos e a Ficha de Série medida do dado |

### Por que o Assistente de laudo veio primeiro, e não por último

O documento o põe em sétimo, "só depois que a turma zero começar a enviar". A plataforma o construiu antes, porque ele é o gargalo real da operação e a célula da sala de aula precisava dele para fechar a fase do laudo. Nada se perdeu com a inversão: ele não depende de nenhum dos outros seis.

### Por que o Historiador não existe aqui

Porque já existe, com outro nome, e ter dois seria a doença que esta casa mais combate: o mesmo fato em dois lugares, começando a divergir no dia seguinte.

### Por que o Revisor de coerência vira código, e não IA

As seis coisas que ele confere são todas mecânicas: a remissão aponta para uma encomenda que existe, o instrumento está com o nome canônico, o número que se repete é igual em todas as ocorrências. Isso é comparação de listas, e uma IA faria pior, mais caro e sem garantia. **Chamar de agente o que um teste resolve é o desperdício mais silencioso deste método.**

## O protocolo de aceitação, que é o mesmo para todos

1. **Teste com sabotagem.** Antes do teste real, alguém planta um erro conhecido na entrada. O verificador precisa detectá-lo; o gerador, não reproduzi-lo. Sem isso, não se sabe se o verificador verifica.
2. **Amostra humana.** Dez saídas lidas por quem conhece a fonte. Zero invenção, nomes intactos.
3. **A Ficha de Série do agente**, medida do dado: cadência, retrabalho, conformidade.
4. **Quando a saída é devolvida**, a correção vai para a **Ficha**, nunca para a saída.
5. **Subir de degrau** só quando um lote fecha saudável.

O ponto 1 já é lei desta casa por outro caminho: todo guarda que entra no sistema precisa ser visto reprovando antes de ser aceito.

## Os erros que o próprio documento diz serem os mais prováveis

| Erro | Por que acontece | O que evita |
|---|---|---|
| Criar um agente geral que faz tudo | é o instinto | um agente, uma coisa; se a Ficha tem "e também", são dois agentes |
| Dar ao agente todos os documentos | "para ele ter contexto" | contexto demais é exatamente onde a invenção entra |
| Deixar o agente melhorar o texto | ele vai querer | toda frase precisa existir na fonte |
| Pular o teste com sabotagem | pressa | sem ele, o verificador é decorativo |
| Deixar a IA decidir os casos fáceis | o gargalo pressiona | a decisão é o produto do trabalho da pessoa |
| Corrigir a saída em vez da Ficha | é mais rápido na hora | três correções na saída significam que a Ficha está errada |

---

# Documento 2: Antes de como começar (onde o Meshcraft entra no site)

Ele diz que o Meshcraft entra como **quatro coisas**, e só uma vira parte nova do site.

| O que ele propõe | O que aconteceu |
|---|---|
| **1. O conteúdo** como arquivos no repositório, com portão automático | **Superado**: o repositório é público e a obra não pode entrar nele. O conteúdo mora no banco e entra pela tela |
| **2. Uma parte nova chamada `avaliacao`** | **Superado por decisão de 4 set**: virou **uma só**, `cursos`, que junta conteúdo, progresso, checkpoint e laudo |
| **3. A gestão no painel que já existe**, e não num aplicativo novo | **Certo, e ele acertou em cheio** |
| **4. Os agentes como sessões**, e os verificadores como portões automáticos | **Metade certa**; a outra metade cai por consequência do ponto 1 |

## O ponto mais importante desta leitura

O documento recomenda que os verificadores virem **portões automáticos**, isto é, testes que reprovam a entrega antes de ela existir.

**Isso só funciona se o conteúdo for arquivo no repositório.** Como ele mora no banco, um portão automático **não consegue enxergá-lo**. É a mesma armadilha que esta casa já pagou uma vez: um portão vigia arquivos, e texto que já está gravado no banco ele não vê, e nunca verá.

Por isso, aqui, os verificadores viram **botões na tela do editor**, ao lado do texto que eles conferem. Você aperta "Conferir coerência" antes de publicar a aula, e a recusa aparece ali. Não é escolha de gosto: é a única forma que alcança o texto onde ele realmente está.

## A colisão de nomes que ele levantou

Ele viu, com razão, que **"Encomenda" é um capítulo no livro e é o marketplace no site**, e recomendou chamar o capítulo de `licao` no código. A casa escolheu **`aula`**. O alerta estava certo; só o nome mudou.

---

# Documento 3: Ajustar o que foi escrito ao que já existe

**É este o documento que fez o ajuste.** Ele foi olhando lote por lote e perguntando *"isto já tem dono aqui dentro?"*.

## O ajuste foi feito por subtração

O número que resume tudo está no próprio documento:

> *"De 8 lotes, 6 se distribuem entre células existentes."*

O plano original tratava a "Fase 6" como **uma plataforma nova inteira**: fila de revisão, jornada do aluno, XP, medalhas, quizzes, portfólio, pares, Bancas, Marcos, telemetria. Na maioria dos casos, a resposta à pergunta acima era **sim, já tem dono**.

O que sobrou como domínio genuinamente novo foi **uma coisa só**: avaliar trabalho com instrumento, prazo, pares e Banca.

**E o ajuste foi ainda mais longe do que ele propunha.** Ele recomendava uma parte nova mais três a cinco extensões. A casa decidiu por **uma só**, porque separar "o curso" de "a avaliação do curso" faria duas partes conversarem o tempo todo sobre a mesma aula.

## O que ele acertou, e que hoje está construído com fiscal

| O que ele mandou | Como está hoje |
|---|---|
| Não criar uma parte do site chamada "meshcraft" | Nunca foi criada |
| O Historiador não existe: é o livro de ocorrências | O livro é o que registra tudo |
| O "Painel do Playbook" não vira aplicativo | Não virou; o painel calculado é o único |
| Nenhuma tela compara alunos, e isso vira teste | **Invariante com teste** |
| O prazo de 24 horas nunca alonga | **Invariante com teste** |
| A IA nunca guarda decisão, data ou carimbo | **Invariante provado por sabotagem** |
| Marcos e medalhas são da gamificação | A tomada já está ligada |
| Os avisos e o silêncio são da mensageria | A jornada de 14 e 30 dias existe |
| Pare e chame o mantenedor quando a decisão for dele | É o rito desta casa |

## Onde ele foi superado, e por quê

1. **O conteúdo em arquivos no repositório.** Impossível: o repositório é público e o texto é obra não lançada.
2. **A parte nova chamada `avaliacao`.** Virou `cursos`, uma só.
3. **O capítulo se chamar `licao`.** A casa escolheu **`aula`**.
4. **O quiz do capítulo ir para a parte `quiz` do site.** A casa decidiu que **não**: o quiz de uma encomenda é campo da própria aula, cinco perguntas presas àquele capítulo.

## A parte dele que vale ouro e a casa ainda não tem

A **tabela de colisões de vocabulário**: dez palavras que significam uma coisa no livro e outra no código.

| Palavra | No livro | No site |
|---|---|---|
| encomenda | um capítulo (E00 a E32) | o marketplace de trabalhos reais |
| painel | o "Painel do Playbook" | o painel calculado de registros |
| fila | a fila de revisão de 24 h | a Fila do Primeiro Dólar |
| Marco | os 6 Marcos de carreira | um selo da gamificação |
| Ficha | Ficha de Série, de Delegação | fichas de outras partes do site |
| quiz | as 5 perguntas por aula | a parte do site chamada `quiz` |
| Mentor | o personagem e o avaliador | um papel de identidade |
| aluno | quem faz o curso | a parte do site que guarda matrícula |
| registro | os modelos R1/R3 do playbook | o livro de ocorrências |
| Historiador | o agente que registra | não existe |

Esse é exatamente o tipo de confusão que custa uma rodada de trabalho.

---

# O que os três, juntos, decidiram

1. **O conteúdo mora no banco, nunca no repositório.** O repositório é público e o livro é obra não lançada. É invariante com fiscal.
2. **Uma parte só do site serve o curso**, e não duas conversando sobre a mesma aula.
3. **Nada que a IA produz chega a alguém sem uma pessoa no meio.** A IA não tem nem onde guardar uma decisão.
4. **O que um teste resolve não vira agente.** Agente é para julgamento de sentido; o resto é portão ou botão.
5. **Não se cria um segundo lugar para uma verdade que já tem lugar.** Um painel, um livro de ocorrências, um dono por assunto.

# O que ainda não tem dono

- **Os capítulos**, que só o mantenedor pode trazer. Sem eles, os verificadores não têm o que verificar.
- **A tela de colar o sumário** (o Extrator), registrada e não construída.
- **O Revisor de coerência** e o **Guardião de fidelidade**.
- **O Gerador de derivados** (o Cartão de 1 página e o quiz).
- **A tabela de colisões de vocabulário**, que merece virar parte das leis da casa e hoje só existe naquele documento.

# Como conferir o que esta página afirma

| Afirmação | Como medir |
|---|---|
| A Ficha de oito campos está no agente que está no ar | procurar `A FICHA DO AGENTE` em `services/cursos/apps/cursos/agente.py` |
| O bloco final de cinco chaves existe | procurar `BLOCO_FINAL` no mesmo arquivo |
| A IA não tem onde guardar uma decisão | o invariante `INV-CUR-L4`, no arquivo de invariantes da raiz |
| Nenhuma tela compara alunos | `services/cursos/tests/test_inv_p1_nenhuma_tela_compara_alunos.py` |
| O prazo de 24 h nunca alonga | o invariante `INV-CUR-L3` |
| O cofre é o banco, não a pasta | a decisão do editor de documentos, em `docs/decisoes/` |

---

*Os documentos do Meshcraft, lidos contra o que existe · atualizado em 6 de setembro de 2026 · Três de dez lidos. Uma Ficha de oito campos, um agente por coisa, e a regra que atravessa tudo: a saída da máquina nunca chega sozinha a ninguém.*
