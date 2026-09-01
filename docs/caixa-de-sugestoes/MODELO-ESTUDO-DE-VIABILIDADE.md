# MODELO — estudo de viabilidade de uma sugestão

> Estação 2 de [`DA-IDEIA-A-OBRA.md`](DA-IDEIA-A-OBRA.md). Copie tudo abaixo da
> linha, preencha os `<campos>`, apague as instruções em itálico e salve em
> `docs/decisoes/PLANO-<assunto>.md`.
>
> **Quando usar:** sugestão que não cabe num PR. Se cabe, pule direto para o
> [`MODELO-DESPACHO.md`](MODELO-DESPACHO.md) — um estudo de viabilidade para
> trocar o texto de um botão é burocracia, e burocracia inútil ensina todo mundo
> a pular etapas que às vezes importam.
>
> **Ordem que não se inverte:** rode `python ci/reconhecer.py <termos>` ANTES de
> escrever a primeira linha. O §2 é o dossiê colado, e o §3 só existe porque o
> §2 mediu. Um estudo escrito de memória descreve o projeto que a sessão imagina.

---

# PLANO — <o que o aluno vai poder fazer, em linguagem de resultado>

**Nasceu de:** sugestão #<id> na Caixa (<N> votos) · <data>
**Estado:** estudo. Nada aqui está decidido enquanto o §6 não voltar respondido.

## §1 O pedido, decomposto

*A frase do aluno, literal e entre aspas, uma vez. Depois a decomposição em
partes numeradas — quase toda sugestão grande é de três a cinco pedidos
enrolados num só, e é a decomposição que revela que dois deles já existem.*

*Inclua o que ele disse SEM pedir: o Ricardo escreveu "procrastinei", e essa
palavra virou uma parte do plano que ele não tinha pedido.*

## §2 O que a casa já tem

*Cole aqui a saída de `python ci/reconhecer.py <termos>`, podada do que não
interessa. Depois, em três linhas de prosa: o que disso serve de molde, e o que
já resolve uma das partes do §1 com outro nome.*

## §3 O que não existe

*Uma lista curta, cada item com o CUSTO da ausência para este plano — nunca só
o nome da coisa que falta. "Não há upload de arquivo" é informação; "não há
upload, então toda parte com foto depende de uma decisão do mantenedor sobre
onde os arquivos moram e de um PR de infraestrutura" é o plano mudando.*

*Se o §2 disse SIM para uma capacidade que você duvida, MEÇA de novo antes de
escrever. Falso SIM apaga trabalho real da escada.*

## §4 Onde a coisa mora

*A fronteira: célula nova, ou dentro de qual célula existente. Duas opções, cada
uma com preço honesto (quantas entregas de fundação, se exige passo manual do
mantenedor, do que ela passa a depender), e a sua recomendação com o motivo.*

*Isto é decisão do mantenedor (`RUNBOOK-LOTES.md` §7): o estudo recomenda, não
decide. As perguntas que costumam decidir bem:*

- *o que esta coisa precisa sobreviver? (se a célula anfitriã puder ser
  desligada um dia, e a coisa não puder, a fronteira é própria)*
- *que preocupação nova ela traz? (disco, moderação de conteúdo, dado pessoal,
  dinheiro) — preocupação nova gosta de canto próprio*
- *que fato ela passa a guardar, e esse fato já mora em algum lugar? (dois
  donos do mesmo fato é o pecado 3 da Lei 3)*

## §5 A escada

| # | Entrega | O que muda para o aluno | Célula | Arqs |
|---|---|---|---|---|

*Regras da tabela:*
- *toda linha cabe no orçamento de 15 arquivos, ou declara por que é
  `arquitetural` (gênese de célula passa por natureza);*
- *"o que muda para o aluno" pode ser "nada" nas entregas de fundação, e escrever
  "nada" é honesto — o mantenedor precisa ver quantos degraus não têm efeito
  visível antes do primeiro que tem;*
- *as linhas do mantenedor (conversa, passo manual, texto que só ele escreve)
  entram na MESMA tabela, marcadas. Passo manual escondido numa nota de rodapé
  vira surpresa no meio do lote;*
- *a ordem respeita `PLANO-AREA-ADMIN` §6: provisionamento sozinho ANTES do
  passo manual, infra sozinho DEPOIS.*

## §6 O que volta para o mantenedor

*Lista numerada e curta. Cada item vira uma opção da pergunta estruturada, em
português simples, com a consequência prática de cada lado. Nada de jargão cru.*

## §7 O que ninguém pode inventar

*As travas que entram copiadas em cada brief: o que a lei já proíbe (veja a lista
de proibições da decisão relacionada), o que este desenho decidiu não fazer, e o
que parece adjacente e tentador. Campo obrigatório: um agente sem "fora de
escopo" preenche o vazio com a própria opinião.*

---

## Por que o estudo existe, em um parágrafo

Porque a alternativa é a sessão pular direto para a escada, e uma escada
construída sobre uma capacidade que não existe desaba no quinto degrau, com
metade das tarefas já na fila e o mantenedor já avisado de um prazo. O estudo é
barato (uma sessão), e a única coisa que ele produz de verdade é a lista de
perguntas certas para o dono — que é o recurso mais escasso do projeto.
