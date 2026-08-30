# `documentos/` — a área de documentos do site

Aqui moram os documentos que o **site publica**: uns para qualquer pessoa, outros
só para quem administra. Decidido pelo mantenedor em 29/08/2026; a lei é
`docs/decisoes/DECISAO-a-area-de-documentos.md`.

Não confundir com as outras pastas de texto do repositório, porque a diferença é
quem lê:

| Pasta | Para quem | Sai no site? |
|---|---|---|
| `documentos/` | pessoas — alunos e o mantenedor | **sim** |
| `docs/decisoes/` | quem constrói (agentes, e ele quando quer o porquê) | não |
| `armadilhas/` | agentes, memória de campo | não |
| `painel/ia/` | IAs de fora, pelo `/mapa-ia/` | sim, como texto puro |

## Um arquivo por documento, e o próprio arquivo diz quem pode ler

Cada documento é um `.md` com um cabeçalho no topo:

```markdown
---
titulo: Como funciona a entrada na escola
publico: true
ordem: 10
---

# Como funciona a entrada na escola

...
```

- **`titulo`** — o nome na lista e no topo da página. Obrigatório.
- **`publico`** — `true` sai em `meshcraft.top/docs/`, para qualquer pessoa.
  Qualquer outra coisa (`false`, ausente, escrita errada) fica **só** em
  `meshcraft.top/admin/documentos/`, atrás da porta.
- **`ordem`** — número que decide a posição na lista (menor primeiro).
  Ausente vale 1000, e aí a ordem entre os sem número é a alfabética do nome do
  arquivo.

**`publico` é fail-CLOSED, e essa é a regra que carrega a pasta.** Um documento
novo nasce PRIVADO. Para ele sair no site aberto alguém precisa escrever
`publico: true` — não existe caminho em que um texto escape para o mundo por
esquecimento ou por erro de digitação no cabeçalho.

## O que se escreve aqui, e o que não

**Escreva:** o que explica algo a uma pessoa — como a escola funciona, o que
acontece depois de pedir entrada, o mapa de um assunto.

**Não escreva:** o ESTADO do projeto. Quantos alunos existem, quem está na fila,
o que está pronto — isso é calculado, e o painel já responde. Um documento que
afirme número vira mentira no dia seguinte, e é a lei anti-duplicação do
`CLAUDE.md`: *nenhum fato do projeto mora em dois lugares*.

Quando um documento precisar falar de algo que o painel mostra ao vivo, **aponte
para a tela**, não copie o número. É o que a jornada do aluno faz.

## O nome do arquivo é o endereço

`documentos/como-funciona-a-entrada.md` sai em
`meshcraft.top/docs/como-funciona-a-entrada`. Só letras minúsculas, números e
hífen — o servidor recusa o resto, e renomear um arquivo **quebra o link que
alguém guardou**.

## O que o site aceita do Markdown

Um subconjunto pequeno e deliberado: títulos (`#` a `###`), parágrafos, listas
com `-`, `**negrito**`, `` `código` ``, citação com `>`, linha `---` e links
`[texto](endereço)`.

**Todo o texto é escapado ANTES de qualquer formatação.** HTML escrito dentro de
um documento aparece como texto na tela, nunca como marcação — é o que torna
impossível um documento injetar script na página, mesmo que alguém cole algo sem
pensar. Tabela, imagem e HTML cru **não** são suportados: se um documento
precisar deles, a conversa é sobre o renderizador, não sobre contornar.
