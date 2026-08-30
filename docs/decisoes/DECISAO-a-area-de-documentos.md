# DECISÃO — a área de documentos do site

**Data:** 29/08/2026 · **Quem decidiu:** o mantenedor · **Estado:** valendo

## O pedido

> *"publica esse documento da jornada do aluno em uma área de docs do site"*

E, quando perguntado sobre onde:

> *"pode ser a Pública, mas quero que haja documentos públicos e outros
> documentos que apenas os administradores podem ver."*

## A tensão que essa frase resolve

O mapa da jornada já existe como **tela viva** em `/admin/escola/jornada/`, com
os números de agora. Publicar uma cópia congelada dele numa área de documentos
seria criar uma segunda verdade — e no dia em que uma regra mudasse, a cópia
passaria a mentir. É a lei anti-duplicação do `CLAUDE.md`: *nenhum fato do
projeto mora em dois lugares.*

A saída não é recusar a área de documentos: é **separar o que é documento do que
é estado**.

- **Documento** explica como algo funciona. Envelhece devagar, e quando
  envelhece, alguém o reescreve.
- **Estado** é quantos alunos existem, quem está na fila, o que já está pronto.
  Isso é calculado, o painel já responde, e um documento que o afirme vira
  mentira no dia seguinte.

Por isso o documento da jornada **não traz números** e aponta para a tela viva
quando precisa deles. A regra está escrita em `documentos/LEIA-ME.md`, para quem
escrever o próximo.

## §1 — Duas visibilidades, uma fonte

Os mesmos arquivos de `documentos/` servem as duas telas, e **é o próprio
documento que declara quem pode lê-lo** — uma linha `publico: true` no cabeçalho.

Duas listas — uma de públicos e outra de privados — discordariam no primeiro dia
em que alguém mexesse numa só. E a discordância aqui tem um lado caro: um texto
interno saindo para o mundo sem ninguém ter decidido isso.

## §2 — `publico` é fail-CLOSED

Ausente, escrito errado, `false`, `sim`, `1`, `yes`, cabeçalho aberto e nunca
fechado — **nada disso publica**. Só a igualdade exata com `true`.

Um documento novo **nasce privado**. Sair no site aberto exige uma linha escrita
de propósito, e é essa a diferença entre um texto sair para o mundo por decisão e
sair por descuido de digitação.

Guarda: `test_so_a_palavra_true_torna_um_documento_publico`, que exercita oito
jeitos plausíveis de alguém escrever "sim".

## §3 — Os dois endereços são diferentes por um motivo mecânico

| Tela | Endereço público | Caminho interno |
|---|---|---|
| pública | `meshcraft.top/docs/…` | `/docs/…` |
| administrativa | `meshcraft.top/admin/documentos/…` | `/documentos/…` |

A célula roda sob `SCRIPT_NAME=/admin`, e o Django **tira esse prefixo** do
`path_info`. Se as duas telas usassem o mesmo nome, `/admin/docs/x` e `/docs/x`
chegariam com o **mesmo caminho interno** — e a porta não teria como distinguir a
pública da privada. O público leria o privado.

Não é escolha de estilo; é a única forma que funciona. Guarda:
`test_os_dois_enderecos_nao_colidem`.

## §4 — A isenção da porta é por PREFIXO, e por que isso não é uma fresta

`/mapa-ia/` é isento por **lista exata**: lá, a decisão de "isto é público" mora
em `porta.py` e em lugar nenhum mais, e arquivo novo não fica público sozinho.

Aqui é diferente, e de propósito: a decisão mora **no documento**. Enumerar os
endereços em `porta.py` criaria uma segunda lista sobre o mesmo fato, e no dia em
que as duas discordassem, ou um documento público ficaria inacessível, ou —
o lado caro — alguém tiraria o `publico: true` achando que bastava.

O que impede o prefixo de virar fresta:

1. sob `/docs/` existem **exatamente duas rotas**, as duas de leitura, e as duas
   conferem `publico` antes de responder;
2. um guarda varre o urlconf e **reprova o CI** se aparecer uma terceira
   (`test_o_prefixo_publico_tem_so_as_duas_rotas`).

## §5 — Documento privado responde 404, nunca 403

Um 403 confirmaria que o arquivo existe, e a lista de documentos internos de uma
escola não é assunto de quem está do lado de fora. Para quem chega, um documento
privado e um endereço inventado são **a mesma coisa**.

## §6 — Escapa primeiro, formata depois

O renderizador aceita um subconjunto pequeno de Markdown (títulos, parágrafos,
listas, negrito, código, citação, linha, links) e **escapa o texto inteiro antes
de aplicar qualquer regra**. HTML escrito dentro de um documento aparece na tela
como texto.

Não é desconfiança de quem escreve — os documentos passam por PR. É a diferença
entre *"não deve acontecer"* e *"não pode acontecer"*, e é o que torna o `|safe`
dos dois templates seguro. A explicação está colada nos dois `|safe`, porque um
dia alguém vai ler só um deles.

Links são restritos a caminho interno ou `https://`. `javascript:` e `data:` não
viram link — e a recusa é silenciosa, virando texto: um link morto numa página é
melhor que um link que executa algo.

## §7 — Os dois primeiros documentos

- **`como-funciona-a-entrada`** (público) — para o ALUNO: o que acontece entre
  entrar com o Google e poder participar, os dois desfechos do pedido, o que cada
  situação quer dizer, e o que a escola guarda sobre ele.
- **`jornada-do-aluno`** (privado) — para o MANTENEDOR: as oito paradas, as doze
  passagens, onde ele mexe em cada uma. Fala de painel, de fila e de gestão; é
  escrito para quem administra, e por isso não é público.

A escolha de qual é qual **não** é sobre segredo — é sobre a quem o texto serve.
Um documento escrito para o operador confunde o aluno, e vice-versa.

## O que NÃO entra nesta pasta

`docs/decisoes/`, `armadilhas/` e `painel/ia/` continuam onde estão. São para
quem constrói, não para quem usa o site — e misturá-los aqui faria a lista pública
crescer com texto que ninguém de fora tem por que ler.
