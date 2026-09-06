---
titulo: Como criar os agentes de IA da Meshcraft (setembro de 2026)
publico: false
ordem: 23
---

# Como criar os agentes de IA da Meshcraft (setembro de 2026)

O método do documento "Como começar a criar os agentes", lido inteiro e comparado, linha por linha, com o que a plataforma já tem construído.

> Escrito em 6 de setembro de 2026, a pedido do mantenedor: *"revise com calma o documento em busca de entender como vai funcionar e como devemos criar esses agentes"*. O documento original (30 KB, nove seções) mora fora deste repositório, em `sitesdoreino-docs/agentes-de-ia/`, porque é obra não lançada. O que está aqui é a leitura dele contra o código que está no ar, e cada afirmação sobre o que já existe foi conferida no código, não na memória.

## A resposta em uma frase

Um agente é **uma Ficha de oito campos** que faz **uma coisa só**, lê **só o que a tarefa manda**, e entrega sempre terminando com o mesmo bloco: o que produzi, o que faltou, o que precisa ser conferido, de onde tirei, e o que a pessoa faz com isto. Ele nunca decide, nunca publica, e nunca pergunta no meio do trabalho.

É o mesmo desenho que o livro ensina na Encomenda 28, a Ficha de Delegação. O documento aplica ao robô a regra que o curso ensina para delegar a gente, e essa simetria não é enfeite: é o que torna o método explicável para quem vai usá-lo.

## Como funciona, por dentro

### Os oito campos da Ficha

Toda Ficha tem a mesma anatomia, e ela é o prompt de sistema do agente:

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

### Os quatro limites que valem para todos

1. **Não inventa.** Todo campo cita a origem: arquivo, seção, trecho copiado, nunca parafraseado.
2. **Não preenche por dedução.** O que falta vira `[LACUNA]`; a escolha entre dois sentidos vira `[VERIFICAR]`.
3. **Não amolece regra.** "Nunca", "sempre", "não existe" continuam como estão.
4. **Não decide, não publica, não compara pessoas.**

### O bloco final, que é onde o método vira operação

Toda entrega termina com cinco linhas: **RESUMO · LACUNAS · A VERIFICAR · ORIGENS · PARA A PESSOA**. A última é a mais importante do método inteiro, porque nenhuma saída chega sem dizer o que uma pessoa faz com ela.

## As três coisas que o documento exige antes do primeiro agente

E onde cada uma está nesta plataforma, medido:

| O documento pede | Aqui é | Estado |
|---|---|---|
| **O cofre**: uma pasta versionada com os documentos-fonte | A **Biblioteca do Livro**, em `/admin/livro/`, no banco | Construída |
| **Ficha + esquema + teste de aceitação** por agente | A Ficha é o prompt; o esquema é o contrato congelado; o teste é a prova por sabotagem que esta casa exige de todo guarda | Construído |
| **Nada vai ao público sem uma pessoa** | Invariante com fiscal automático: a IA não tem nem campo onde guardar uma decisão | Construído e provado |

**A diferença do cofre merece explicação**, porque é a única exigência que a plataforma cumpre de um jeito diferente do que o documento imaginou. O documento supõe uma pasta no Git com todos os capítulos dentro. Este repositório é **público**. O texto do livro é obra não lançada, e por isso o cofre é o banco de dados, alcançado pela tela, e nunca um arquivo commitado. É uma decisão antiga da casa e não se reabre.

## Os sete agentes, e onde cada um está

O documento propõe uma ordem de criação. Esta é ela, com o estado real de cada um:

| # | Agente | O que faz | Estado aqui |
|---|---|---|---|
| 1 | **Extrator** | lê um documento-fonte e o decompõe em dados estruturados, citando a origem | É a tela de colar o sumário. **Registrado, não construído** |
| 2 | **Revisor de coerência** | confere remissões, nomes canônicos e números repetidos | Vira **código**, não IA. **Não construído** |
| 3 | **Guardião de fidelidade** | compara um derivado com a fonte e aponta onde o sentido mudou | O segundo agente de IA. **Não construído** |
| 4 | **Historiador** | registra tudo o que aconteceu | **Dissolvido**: já é o livro de ocorrências do painel |
| 5 | **Gerador de derivados** | produz o Cartão de 1 página e o quiz a partir do capítulo | **Não construído** |
| 6 | **Plantador de arquivos** | produz os arquivos de prática do Blender | **Não é software**: é trabalho de modelagem |
| 7 | **Assistente de laudo** | pré-preenche a avaliação de uma entrega, para a professora assinar | **No ar**, com a Ficha de oito campos e a Ficha de Série medida do dado |

### Por que o Assistente de laudo veio primeiro, e não por último

O documento o põe em sétimo, "só depois que a turma zero começar a enviar". A plataforma o construiu antes, e o motivo é bom: ele é o gargalo real da operação, e a célula da sala de aula precisava dele para fechar a fase do laudo. Nada se perdeu com a inversão, porque ele não depende de nenhum dos outros seis.

### Por que o Historiador não existe aqui

Porque já existe, com outro nome, e ter dois seria a doença que esta casa mais combate: o mesmo fato em dois lugares, começando a divergir no dia seguinte. O livro de ocorrências do painel registra cada entrega, cada decisão e cada incidente, e é calculado, não mantido à mão.

### Por que o Revisor de coerência vira código, e não IA

As seis coisas que ele confere são todas mecânicas: a remissão aponta para uma encomenda que existe, o instrumento está com o nome canônico, o número que se repete é igual em todas as ocorrências. Isso é comparação de listas, e uma IA faria pior, mais caro e sem garantia. **Chamar de agente o que um teste resolve é o desperdício mais silencioso deste método.**

## A diferença que mais importa entre o documento e esta plataforma

O documento imagina cada agente como **uma conversa de chat**: alguém abre um projeto, anexa os arquivos do cofre, cola a Ficha, recebe a saída e a copia de volta para onde ela precisa morar.

Aqui eles viram **botões dentro das telas onde a pessoa já está**. O Assistente de laudo não é um chat: é o botão "Rascunhar laudo", no formulário do plantão, ao lado dos campos que a professora já ia preencher. Ela aperta, lê, corrige e assina, sem sair da página.

Isso elimina o passo mais frágil do desenho original, que é o copia-e-cola humano entre o agente e o lugar onde a coisa mora. Cada travessia dessas é uma chance de perder um pedaço, de colar na aula errada, ou de publicar sem ler.

## O protocolo de aceitação, que é o mesmo para todos

1. **Teste com sabotagem.** Antes do teste real, alguém planta um erro conhecido na entrada. O verificador precisa detectá-lo; o gerador, não reproduzi-lo. Sem isso, não se sabe se o verificador verifica.
2. **Amostra humana.** Dez saídas lidas por quem conhece a fonte. Zero invenção, nomes intactos.
3. **A Ficha de Série do agente**, medida do dado: cadência, retrabalho, conformidade.
4. **Quando a saída é devolvida**, a correção vai para a **Ficha**, nunca para a saída.
5. **Subir de degrau** só quando um lote fecha saudável.

O ponto 1 já é lei desta casa por outro caminho: todo guarda que entra no sistema precisa ser visto reprovando antes de ser aceito. É a mesma ideia, e aqui ela é mecânica.

## Os erros que o próprio documento diz serem os mais prováveis

| Erro | Por que acontece | O que evita |
|---|---|---|
| Criar um agente geral que faz tudo | é o instinto | um agente, uma coisa; se a Ficha tem "e também", são dois agentes |
| Dar ao agente todos os documentos | "para ele ter contexto" | contexto demais é exatamente onde a invenção entra |
| Deixar o agente melhorar o texto | ele vai querer | toda frase precisa existir na fonte |
| Pular o teste com sabotagem | pressa | sem ele, o verificador é decorativo |
| Deixar a IA decidir os casos fáceis | o gargalo pressiona | a decisão é o produto do trabalho da pessoa |
| Corrigir a saída em vez da Ficha | é mais rápido na hora | três correções na saída significam que a Ficha está errada |

O primeiro desses erros a plataforma já evita por construção: um agente, uma tela, um botão.

## O que vem a seguir, e em que ordem

A ordem do documento começa pelo Extrator porque **nada funciona sem o conteúdo**. Aqui é igual:

1. **A tela de colar o sumário.** É o Extrator na forma desta casa: o mantenedor cola o sumário do livro uma vez, vê uma prévia do que será preenchido e do que será preservado, e confirma. Está registrado na fila e é o próximo passo.
2. **O Revisor de coerência**, em código. Barato, e pega erro de remissão antes de o aluno ver.
3. **O Guardião de fidelidade**, o segundo agente de IA, no molde do primeiro.
4. **O Gerador de derivados**, que produz o Cartão de 1 página e o quiz a partir do capítulo.

Nenhum deles depende de decisão nova do mantenedor, exceto o modelo de IA e o custo de cada agente novo, que é sempre pergunta a ele com o número na mesa.

## Como conferir o que este documento afirma

| Afirmação | Como medir |
|---|---|
| A Ficha de oito campos está no agente que está no ar | procurar `A FICHA DO AGENTE` em `services/cursos/apps/cursos/agente.py` |
| O bloco final de cinco chaves existe | procurar `BLOCO_FINAL` no mesmo arquivo |
| A IA não tem onde guardar uma decisão | o invariante `INV-CUR-L4`, no arquivo de invariantes da raiz |
| O cofre é o banco, não a pasta | a decisão do editor de documentos, em `docs/decisoes/` |

---

*Como criar os agentes de IA da Meshcraft · 6 de setembro de 2026 · Uma Ficha de oito campos, um agente por coisa, e a regra que atravessa tudo: a saída da máquina nunca chega sozinha a ninguém.*
