# 333 — Opção de pergunta estruturada que pede texto livre na descrição volta vazia

**Data:** 04/09/2026 · **Onde:** qualquer sessão que abra a caixa de pergunta
(`AskUserQuestion`) para o mantenedor · **Custo evitado:** uma rodada inteira
decidida com metade da resposta

## Sintoma

Você abre a caixa com a opção "Não, é outra pessoa" e escreve na descrição
dela: "me diga o papel dela na próxima mensagem". Ele clica na opção. A caixa
fecha, a sessão segue, e o papel dela nunca chega. Ele não digita nada, e está
certo: a caixa existe para ele **não** digitar. Você fica com a metade da
resposta que cabia num clique e decide o resto por dedução.

Medido em 04/09/2026: a pergunta "você e a autora do livro são a mesma
pessoa?" voltou "não, é outra pessoa", e o papel dela ficou sem resposta. O
plano da célula de cursos nomeou "a professora" pelo roadmap, não por ele.

## Causa

A caixa de pergunta é a lei da casa justamente porque ele é leigo e não deve
compor texto (`CLAUDE.md`, "qualquer coisa pendente vira pergunta
estruturada"). A descrição de uma opção é **explicação da consequência**, não
campo de entrada. Um pedido de texto livre escondido ali é uma pergunta sem
mecanismo: não existe caixa que a receba, e "na próxima mensagem" é uma
promessa que ninguém cobra.

## Solução

O que você precisa saber vira **pergunta própria, com opções**, nunca
instrução dentro da descrição de outra opção. Se uma resposta abre uma segunda
pergunta ("é outra pessoa" → "qual o papel dela?"), ou a segunda já vai na
mesma caixa com as respostas prováveis ("ela grava e avalia" · "ela só grava"
· "ela escreve e mais nada"), ou você abre outra caixa na hora, antes de
seguir. O único lugar onde texto livre entra é o "Outro" que a caixa já
oferece, e é ele que se nomeia: "escolha Outro e escreva o papel dela".

Régua para reler a caixa antes de abrir: **cada descrição diz o que acontece
se ele clicar ali. Se alguma pede algo dele, é uma pergunta disfarçada, e
pergunta se faz com opções.**
