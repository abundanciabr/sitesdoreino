# DECISÃO — o editor de documentos no painel do admin

**Data:** 31/08/2026 · **Quem decidiu:** o mantenedor · **Estado:** valendo

## O pedido

> *"Crie uma parte no painel do admin para eu gerenciar / editar os documentos,
> tais como este: https://meshcraft.top/docs/como-funciona-a-entrada"*

## A frase parece de tela, e é sobre onde o dado mora

Até aqui um documento era um **arquivo** em `documentos/`, e o site só o lia
(`DECISAO-a-area-de-documentos.md`, 29/08/2026). O texto entrava pelo mesmo
caminho do código: um agente escrevia, as muralhas conferiam, e ele subia com a
próxima imagem.

Uma tela de edição não cabe nesse desenho, e o motivo é mecânico: **o disco do
container é remontado a cada atualização da plataforma**. Gravar a edição do
mantenedor no `.md` embutido a apagaria no deploy seguinte — sem erro, sem
alarme, sem ninguém ligar uma coisa à outra. É o pior formato de defeito que
esta casa conhece: o que some em silêncio.

## §1 — As três saídas que existiam, e a que ele escolheu

Consultado com as três na mesa, em 31/08/2026:

| Saída | O que ela custa |
|---|---|
| **o texto passa a morar no banco** | sai da conferência automática das muralhas |
| o texto continua em arquivo, e a tela abre um PR | não é instantâneo; exige uma chave do GitHub no servidor |
| os dois, banco e arquivo | o mesmo fato em dois lugares, que é a lei anti-duplicação |

**Ele escolheu o banco**, e a escolha é coerente com o que a casa já faz: o menu
do topo (`/admin/menu/`, 31/08/2026) também é dado de site editado por tela, e
as áreas do fórum também nasceram de um semeador e passaram a viver no banco.

A terceira saída foi recomendada CONTRA, e continua: manter o texto em dois
lugares é a doença que o `CLAUDE.md` proíbe, e no primeiro dia em que os dois
discordassem ninguém saberia qual está no ar.

## §2 — A pasta `documentos/` vira SEMENTE, e isso não é duplicação

A migração `0003` da célula `admin` lê a pasta **uma vez** e despeja os
documentos na tabela. Depois disso, quem responde *"o que este documento diz"* é
a tabela, e só ela. A pasta continua no repositório porque é de onde uma
instalação nova parte (um banco recriado do zero replica a migração e nasce com
os mesmos textos), e não porque alguém ainda a leia.

**É migração, e não `manage.py semear_documentos`, por uma diferença de
consequência.** Os semeadores desta casa são comandos que o mantenedor dispara
por um workflow, e isso funciona porque a ausência deles é invisível (uma área a
menos no fórum). Aqui a ausência seria `meshcraft.top/docs/`, uma página PÚBLICA
que já existe, ficando **vazia no ar** até alguém lembrar de apertar um botão.
Migração roda sozinha no `migrate` do boot.

**E ela roda uma vez, o que é a metade importante.** Fosse a semeadura um passo
de toda subida, um documento que o mantenedor apagasse pela tela voltaria do
túmulo no deploy seguinte. Migração tem memória de já ter rodado; comando não.

Guarda: `test_mexer_no_arquivo_da_pasta_NAO_muda_o_que_o_site_publica`, escrito
pelo avesso — ele fica vermelho se alguém religar a leitura ao disco.

## §3 — A regra do travessão desce do CI para a tela

`ci/travessao.py` vigia ARQUIVOS. Texto que o mantenedor digita numa tela e que
vai direto para o banco **nunca passa por ele** — e o limite já cobrou caro uma
vez, quando um travessão sobreviveu no fórum a uma varredura que se declarou
completa, porque estava gravado no banco e não em arquivo (registro
`20260830-051`).

Escolha dele, na mesma consulta: **a tela RECUSA salvar** e mostra a frase com
problema junto das quatro trocas. Não é rigor gratuito — é a mesma régua que os
arquivos já cumprem, aplicada onde o texto agora entra. É o padrão *fail-closed
na borda* da `RETROSPECTIVA-FASE-D`.

O conjunto de riscas é o MESMO de `ci/travessao.py`, e um guarda de fora mede os
dois juntos: duas listas divergiriam, e a que ficasse para trás seria a que
deixa passar.

## §4 — Arquivar e apagar são gestos diferentes, e é ele quem escolhe qual

Escolha dele: **os dois existem, separados.**

- **Arquivar** tira o documento do site na hora e guarda o texto inteiro.
  Reversível, e por isso não pede confirmação escrita.
- **Apagar de vez** destrói, e pede que ele digite o nome do documento —
  a mesma gramática de `DECISAO-apagar-ideia.md`.

Arquivar **não é despublicar**: `publico` continua gravado como estava, e é por
isso que a pergunta *"está no ar?"* virou uma propriedade própria (`no_ar`), e
não uma leitura de `publico`. Quem perguntar só por `publico` deixa um documento
arquivado visível no site, e um nome próprio é o que torna esse esquecimento
difícil.

## §5 — O que NÃO muda

- **`publico` continua fail-CLOSED.** Antes pela igualdade exata com `true` no
  cabeçalho; agora pelo default `False` da coluna. Documento novo nasce privado,
  e sair para o mundo continua exigindo um gesto de propósito.
- **Escapa primeiro, formata depois.** O renderizador continua aceitando um
  subconjunto pequeno de Markdown e escapando o texto antes de qualquer regra.
  Isso deixou de ser cinto e virou o cinto: até aqui o texto passava por PR, e
  daqui em diante ele entra por um formulário.
- **Os dois endereços continuam diferentes** (`/docs/…` público, `/documentos/…`
  atrás da porta), pelo motivo mecânico do §3 da lei anterior.
- **Toda escrita deixa rastro.** Verbos próprios na auditoria da célula, uma
  linha por gesto, como toda escrita desta área desde a primeira.

## §6 — O preço aceito, dito em voz alta

O texto dos documentos deixa de viver no Git. Não há mais `git log` de quem
mudou uma frase, e não há mais revisão em PR antes de um documento público
mudar.

O que entra no lugar: **o histórico de versões na própria tabela** (toda
gravação guarda o retrato anterior, com quem salvou e quando, e dá para voltar
atrás por uma tela) e **a auditoria da célula**. É menos do que o Git dá, e é
o que a decisão dele custa. Registrado aqui para que ninguém redescubra isto
como surpresa.
