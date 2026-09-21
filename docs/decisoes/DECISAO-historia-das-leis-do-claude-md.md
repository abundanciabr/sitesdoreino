# O porquê de cada lei do CLAUDE.md

Data: 21/09/2026. Decisão irmã: `docs/decisoes/DECISAO-claude-md-so-lei.md`,
que estabeleceu que o `CLAUDE.md` guarda lei e nada mais.

O `CLAUDE.md` é lido inteiro por toda sessão de toda IA da casa, e por isso tem
teto em bytes (`ci/padrao_de_trabalho.py`). Quando o teto aperta, a saída barata
é apagar lei, e apagar lei é o único erro desta cirurgia que ninguém percebe
depois. Este arquivo existe para que a saída barata nunca seja necessária: o que
OBRIGA fica no `CLAUDE.md`, o que EXPLICA mora aqui.

Cada bloco abaixo tem o nome exato da seção do `CLAUDE.md` de onde o texto veio,
o trecho movido sem uma vírgula de reescrita, e o que ele explicava. A 1ª seção,
o Padrão de Trabalho, não entra: ela é conferida frase a frase por um portão e
não pode perder um caractere.

## Antes de começar qualquer tarefa: leia as armadilhas

Movido: "JSON com até 3 lições de 500 caracteres e origens."

Descrevia o formato da resposta do consultor de armadilhas. A obrigação é
consultar; o formato da saída quem mostra é a própria saída.

## O clone principal é espelho, não bancada

Movido: "A abertura atualiza o espelho quando seguro."

Explicava por que o clone principal costuma estar em dia sem ninguém puxar: a
abertura da bancada faz isso sozinha quando a árvore está limpa. É um fato sobre
a ferramenta, não uma ordem ao agente.

## Todo pedido do mantenedor é um lote

Movido: "Contrato congelado/CODEOWNERS: mandato escrito."

Este é o único trecho movido que era regra, e ele saiu porque tinha virado uma
cópia velha e contraditória da regra viva. A seção "Integração automática" diz,
desde 20/09/2026, que a palavra do mantenedor "vale onde ele a deu: dita na
sessão vale tanto quanto digitada no site". A cópia aqui continuava exigindo
mandato "escrito", e duas leis sobre a mesma coisa, uma delas desatualizada,
ensinam o agente a escolher a que lhe convier. A regra segue inteira, e mais
forte, em "Integração automática": contrato congelado e CODEOWNERS exigem a
palavra do mantenedor, e quem a recebeu transcreve `Mandato-do-mantenedor:` na
descrição do PR com o pedido, os caminhos autorizados e a origem.

## O que uma chamada custa

Nada movido. A seção é comando e regra, sem uma linha de explicação.

## Este projeto é para ser feito completo — nunca proponha a versão minimalista

Movido: "duração não desencoraja" e "desde 19/09/2026" (a data do escopo).

O primeiro era o motivo da regra: a regra 3 vale em quantos PRs forem precisos, e
o tamanho da empreitada nunca foi argumento para entregar menos. O segundo era a
data em que o foco passou a ser só o `meshcraft.top`, registrada em
`docs/decisoes/DECISAO-foco-em-meshcraft.md`. O escopo continua na lei; a data de
quando ele mudou é história.

## Nenhum texto publicado sai com travessão

Movido: "vírgula para explicação, parênteses para acessório, dois-pontos para
fechamento, aspas para fala", "Leia em voz alta" e "(forum/0003)".

Os três primeiros são o cardápio de substituições que resolve quase todo
travessão, e o quarto é o teste que pega o resto: se a frase tropeça na boca, a
pontuação está errada. A proibição e o alcance continuam na lei; isto é o ofício.
O "(forum/0003)" era o exemplo da migração que consertou texto já semeado no
banco, prova de que o portão mede arquivos e não linhas de banco de dados.

## O livro de ocorrências é obrigatório, não opcional

Movido: "painéis em arquivos/ são lápides."

Explicava por que existem painéis antigos parados em `painel/arquivos/`: eles não
são código vivo nem dívida, são registro do que a casa já mostrou. Ninguém os
atualiza e ninguém os apaga.

## Integração automática

Movido: "a main permanece protegida."

Era a garantia dada ao leitor assustado com a frase anterior: o pouso é
automático, sem revisor e sem gesto da maestro, mas a `main` continua com a
proteção nativa do GitHub por trás. Quem faz valer essa proteção é o próprio
GitHub, não uma linha do `CLAUDE.md`.

## O que você entrega para ele mora no site

Nada movido. Três frases, todas obrigação.

## Como trabalhar com o mantenedor

Movido: "Poupar pergunta nunca foi poupar informação. Não perguntar é não
transferir decisão sua; nunca dispensa instruir." e "Calar o próximo passo para
não incomodar é falha, não cortesia."

Este é o porquê mais caro da casa, e por isso fica escrito por extenso. A casa
proíbe que a IA pergunte ao mantenedor o que ela mesma pode decidir ou descobrir.
O agente lê essa proibição e conclui a coisa errada: que falar menos é servir
melhor. Não é. A proibição é sobre DECISÃO, nunca sobre INFORMAÇÃO. Ele não
precisa escolher por você, mas precisa saber o que aconteceu, o que trava, o que
destrava e quanto leva. O agente que entrega um resultado e cala o próximo passo
não poupou o mantenedor: passou a ele o trabalho de adivinhar. A obrigação que
sobrou na lei é a que se cobra: toda proibição de perguntar obriga a dizer no
fecho o que vem depois.

## Plano na abertura, contas no fecho

Movido: "terminar no veredito deixa a tarefa parada" e "é a mesma contradição".

O primeiro era o motivo de **Instruções** ser bloco obrigatório: uma prestação de
contas que acaba no veredito deixa o mantenedor com um resultado na mão e nenhum
próximo passo, e a tarefa para ali. O segundo ligava o PRONTO sobre medição
vermelha ao PRONTO com caixa aberta, dito na frase anterior: nos dois casos o
agente declara pronto o que ele mesmo acabou de medir como não pronto.

## Mapa do projeto para IA

Nada movido. Três frases, todas obrigação.
