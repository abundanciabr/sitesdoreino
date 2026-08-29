# DECISÃO — o mapa da jornada do aluno

**Data:** 29/08/2026 · **Quem decidiu:** o mantenedor · **Estado:** valendo

## O pedido

> *"Aliás, você poderia criar um tipo de mapa da jornada do aluno para que
> ficasse mais fácil de gerenciá-los. No melhor padrão ouro da indústria, quero
> poder gerenciar os alunos (usuários) facilmente."*

Ele acabava de descobrir, com a própria conta, que **não sabia dizer em que
estado uma pessoa removida tinha ficado** — nem o que ela veria ao voltar. Os
estados existiam, cada um com a sua lei escrita; o que não existia era um lugar
onde eles aparecessem juntos.

## O que nasceu

`/admin/escola/jornada/` — quatro faixas na ordem em que uma pessoa as vive
(*Fora da escola · Pedindo entrada · Dentro da escola · Depois*), oito paradas,
e em cada uma: quem está ali, **o que a pessoa vê**, como se sai daquele ponto,
e quantas pessoas estão nele agora.

**"O que a pessoa vê" é a metade que faz o mapa ser útil.** Um mapa que só
nomeasse estados seria um diagrama — e o defeito que gerou o pedido foi
exatamente o mantenedor não saber o que esperar da tela de alguém.

## §1 — A cor responde uma pergunta só

A tarja de cada parada diz **entra** ou **não entra**. É a única pergunta que se
faz o dia todo sobre um aluno.

Verde e cinza aqui **não significam "bom" e "ruim"**: um ex-aluno não é um erro,
e um reembolsado entra (decisão do mantenedor de 24/08/2026 — quem já foi aluno
mantém a voz na Caixa). Significam a porta aberta e a porta fechada.

## §2 — Uma contagem, duas telas

Os números saem de `contar_a_escola()`, a **mesma função** que alimenta os
cartões de `/admin/escola/alunos/`.

Duas telas mostrando "quantos alunos existem" com duas contagens escritas à mão
divergiriam no primeiro estado novo — e o mantenedor leria a que abrisse
primeiro, sem saber que a outra discorda. É a lei anti-duplicação do `CLAUDE.md`
aplicada **dentro** da mesma célula, onde ela é mais fácil de esquecer.

Guarda: `test_a_jornada_e_a_lista_dizem_o_mesmo_numero`, que abre as duas telas
na mesma escola e compara.

## §3 — "Não há como contar" ≠ "contei e deu zero"

**Visitante** e **cadastrado** não têm matrícula. Não existe, em lugar nenhum do
sistema, como contá-los a partir das fichas — e um `0` ali seria a tela
afirmando que ninguém entrou no site hoje, que é uma frase que ela não tem como
saber. Eles aparecem com um travessão.

É a mesma distinção que os cartões da lista já faziam entre `None` e `0`, agora
com um terceiro caso nomeado: `contavel`. Três estados, três respostas — nunca
um número inventado para preencher o quadro.

## §4 — O mapa sobrevive à contagem

A `alunos` fora do ar deixa as paradas sem número e **a página abre igual**, com
um aviso honesto: *"O mapa está certo; os números é que não chegaram."*

O mapa descreve as **regras**, não as pessoas. Uma tela que sumisse junto com a
contagem seria uma tela que não sabe o que ela é.

## §5 — Ferramenta, não diagrama

Cada parada com estado leva para a lista **já filtrada**
(`/admin/escola/alunos/?estado=encerrada`). A diferença entre um diagrama e uma
ferramenta de gestão é o link — e é por isso que a busca e o filtro
(`PR #505`) precisaram existir antes desta tela.

## §6 — Onde a pergunta nasce, a resposta aparece

*"Como eu removo um aluno?"* é a pergunta que traz o mantenedor a esta tela. A
resposta certa **não é um botão**: é o seletor de situação, em *Ex-aluno*. A
página diz isso com todas as letras, junto com a lei de 29/08/2026 — nenhuma
ficha se apaga, e quem sai pode pedir para voltar.

## O que isto NÃO é

Não é o mapa em documento que abriu esta conversa (aquele foi o rascunho que o
mantenedor aprovou). O documento envelhece sozinho; esta tela lê o sistema.
Quando os dois discordarem, **o sistema vence**.

## Fatia 3 de 5

Continuam em aberto, cada uma no seu PR: cadastrar alguém à mão · avisar pelo
sino quando a situação muda.
