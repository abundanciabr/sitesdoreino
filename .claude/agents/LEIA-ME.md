# .claude/agents/ — as fichas dos robôs desta casa

> Nascida em 05/09/2026, degrau 1 do
> `docs/decisoes/PLANO-ORQUESTRACAO-AUTONOMA-DOS-ROBOS.md` (registro
> `20260905-013`). A lei desta pasta: **o rito fixo mora aqui; o brief só
> carrega o que muda de tarefa para tarefa.**

## O que é uma ficha

Um arquivo `<nome>.md` por papel, versionado no Git e alterado por PR. Ele tem
duas partes: um frontmatter que o harness lê, e um corpo em português que o
sub-agente segue como rito.

| Parte | Regra |
|---|---|
| `name` | igual ao nome do arquivo, sem `.md`; o teste confere |
| `description` | obrigatória; é por ela que a maestro escolhe a ficha |
| `tools` | a lista fechada do que aquele papel alcança; ficha sem lista herda tudo, inclusive escrita |
| `disallowedTools` | precisa negar `AskUserQuestion` e `Agent`, sempre, em toda ficha |
| `model` | declarado, nunca herdado; ficha sem `model` usa o modelo da maestro, que é o mais caro (CLAUDE.md, "O que uma chamada custa") |
| `effort`, `maxTurns` | o teto de esforço e de voltas daquele papel |

Campo fora da tabela de campos conhecidos é **ignorado em silêncio** pelo
harness: um erro de digitação não dá erro, só faz a ficha valer menos do que
parece. Por isso `ci/tests/test_fichas_de_robo.py` confere a lista de campos, e
não só o conteúdo.

## Por que o rito mora aqui e não no brief

O brief é redigido a cada tarefa. O que se repete em toda tarefa, copiado a
cada vez, envelhece em silêncio: a regra muda na lei, o brief antigo continua
mandando o contrário, e ninguém vê. A ficha é um arquivo só, passa por PR,
aparece no diff e tem teste. O brief fica com o que é daquela tarefa e de mais
nenhuma: célula, alvos, o que é somente leitura, a evidência exigida, o modelo
e o esforço recomendados.

## De onde vêm os papéis

As competências que esta casa precisa ter estão descritas, em prosa, em
`docs/consultorias/equipe-especialista/RELATORIO.md` (PARTE IV, entrega da
TAR-455). Elas não são copiadas para cá: fato nenhum mora em dois lugares, e
uma segunda lista só serviria para divergir da primeira.

Uma ficha é o degrau seguinte daquela prosa na Escada da Imposição
(CONSTITUICAO.md, Lei 1): o relatório é documento, que descreve o que um
especialista deveria conferir; a ficha é processo com portão, que se convoca
pelo nome e já vem com ferramentas limitadas e teste em cima. Nem toda
competência do relatório vira ficha, e uma ficha pode materializar mais de uma:
o `procurador`, por exemplo, pega o eixo de MEDIR de "Produto, aprendizagem e
experiência" e de "Integridade comercial e transacional".

## Quando convocar cada ficha

| Ficha | Convoque quando | NÃO convoque quando |
|---|---|---|
| `despacho` | há um pedaço de trabalho fechado que vira um PR, com alvos e evidência já decididos | falta decidir o que fazer, ou o pedido ainda não foi repartido em pedaços independentes |
| `revisor` | um PR existe e você quer a lista do que ele reprovaria, com arquivo e linha, antes do pedido de pouso | não há diff para ler, ou o que você quer é o conserto, e não o veredito |
| `escrivao` | sobrou um papel de julgamento depois do `make pr`: lição nova, bloqueio, incidente, decisão pedida ou respondida | é registro, recibo, evento ou reserva que o `make pr` já escreveu; ele não duplica o que a máquina fez |
| `procurador` | antes de fechar a fila de um pedido, para medir para onde o trabalho foi e o que o comprador e o aluno perderam | a pergunta é sobre código quebrado, e não sobre valor que não existe |

A ficha `procurador.md` nasce neste PR. Outras estão sendo escritas hoje, em
PRs irmãos: `provador`, `adversario`, `conferente` e `maquinista`. Enquanto o
PR de cada uma não pousar, a ficha não existe em `origin/main` e convocá-la
pelo nome falha: confira a pasta antes de escrever um brief que dependa dela.

## As duas regras que nenhuma ficha derruba

**Papel aqui é por TAREFA, nunca por marca de inteligência artificial.** Quem
executa uma ficha é quem pegou aquela tarefa. Nenhum fornecedor é dono de um
papel, e nenhuma ficha cita marca para dizer quem manda; se citar, está
descrevendo o acaso de quem estava livre, e isso não é lei.

**Sub-agente não cria sub-agente e não fala com o mantenedor.** O time é plano:
por isso toda ficha nega `Agent`. E quem pergunta ao mantenedor é a maestro; o
sub-agente que esbarra numa decisão dele escreve o bloqueio no balcão da fila,
deixa o registro com `precisa_do_dono: true` e devolve. Por isso toda ficha
nega `AskUserQuestion`. Abrir exceção assim é o resultado esperado, não falha.

Quem faz valer: `ci/tests/test_fichas_de_robo.py`.
